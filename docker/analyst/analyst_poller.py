#!/usr/bin/env python3
"""
Analyst agent — direct OpenAI integration.

Polls Supabase agent_tasks for analyst tasks, calls the OpenAI API
to run multi-step intelligence analysis, persists results to Supabase
(analysis_runs, opportunities, cross_signals), and marks the task done.
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError
from supabase import create_client, Client
from openai import OpenAI

from schemas import TASK_INPUT_SCHEMAS, AnalystOutput

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AGENT_NAME = os.getenv("AGENT_NAME", "analyst")
OPENCLAW_DATA_DIR = os.getenv("OPENCLAW_DATA_DIR", "/home/openclaw/.openclaw")
POLL_INTERVAL = int(os.getenv("ANALYST_POLL_INTERVAL", "15"))
MODEL = os.getenv("ANALYST_MODEL", "gpt-4o")

WORKSPACE = Path(OPENCLAW_DATA_DIR) / "workspace"
ANALYSIS_DIR = WORKSPACE / "agentpulse" / "analysis"

# Prediction monitoring
PREDICTION_MAX_OPEN = int(os.getenv("PREDICTION_MAX_OPEN", "20"))
PREDICTION_STALE_DAYS = int(os.getenv("PREDICTION_STALE_DAYS", "180"))

# Logging
LOG_DIR = Path(OPENCLAW_DATA_DIR) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "analyst-poller.log"),
    ],
)
logger = logging.getLogger("analyst-agent")

supabase: Client | None = None
client: OpenAI | None = None

# ---------------------------------------------------------------------------
# Identity + Skill loading (from disk, with mtime caching)
# ---------------------------------------------------------------------------

AGENT_DIR = Path(OPENCLAW_DATA_DIR) / "agents" / "analyst" / "agent"
SKILL_DIR = Path(OPENCLAW_DATA_DIR) / "skills" / "analyst"

_identity_cache: str | None = None
_identity_mtime: float = 0

_skill_cache: str | None = None
_skill_mtime: float = 0


def load_identity(agent_dir: Path) -> str:
    """Load IDENTITY.md + SOUL.md from agent_dir, caching by mtime."""
    global _identity_cache, _identity_mtime
    identity_path = agent_dir / "IDENTITY.md"

    current_mtime = identity_path.stat().st_mtime if identity_path.exists() else 0

    if _identity_cache and current_mtime == _identity_mtime:
        return _identity_cache

    parts = []
    if identity_path.exists():
        parts.append(identity_path.read_text(encoding="utf-8"))
        _identity_mtime = current_mtime

    soul_path = agent_dir / "SOUL.md"
    if soul_path.exists():
        parts.append(f"\n---\n\n{soul_path.read_text(encoding='utf-8')}")

    if parts:
        _identity_cache = "\n\n".join(parts)
    else:
        logger.warning(f"Identity files not found in {agent_dir} — using fallback")
        _identity_cache = (
            "You are the Analyst agent for AgentPulse. "
            "Analyze the data provided and return structured findings as valid JSON."
        )

    return _identity_cache


def load_skill(skill_dir: Path) -> str:
    """Load SKILL.md from skill_dir, caching by mtime."""
    global _skill_cache, _skill_mtime
    skill_path = skill_dir / "SKILL.md"

    current_mtime = skill_path.stat().st_mtime if skill_path.exists() else 0

    if _skill_cache is not None and current_mtime == _skill_mtime:
        return _skill_cache

    if skill_path.exists():
        _skill_cache = skill_path.read_text(encoding="utf-8")
        _skill_mtime = current_mtime
    else:
        logger.warning(f"SKILL.md not found in {skill_dir}")
        _skill_cache = ""

    return _skill_cache


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init():
    global supabase, client
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Supabase not configured (SUPABASE_URL / SUPABASE_KEY missing)")
        return False
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set — cannot run analysis")
        return False
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    client = OpenAI(api_key=OPENAI_API_KEY)
    return True


def ensure_dirs():
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Budget config
# ---------------------------------------------------------------------------

_budget_config_cache: dict | None = None


def get_budget_config(agent_name: str, task_type: str) -> dict:
    """Read budget limits for a given agent + task type from agentpulse-config.json."""
    global _budget_config_cache

    defaults = {
        "max_llm_calls": 5,
        "max_seconds": 180,
        "max_subtasks": 2,
        "max_retries": 1,
    }

    if _budget_config_cache is None:
        config_path = Path(OPENCLAW_DATA_DIR) / "config" / "agentpulse-config.json"
        try:
            if config_path.exists():
                with open(config_path) as f:
                    _budget_config_cache = json.load(f)
            else:
                logger.warning(f"Budget config not found at {config_path}, using defaults")
                _budget_config_cache = {}
        except Exception as e:
            logger.warning(f"Failed to read budget config: {e}, using defaults")
            _budget_config_cache = {}

    budgets = _budget_config_cache.get("budgets", {})
    task_budget = budgets.get(agent_name, {}).get(task_type, {})

    return {k: task_budget.get(k, defaults[k]) for k in defaults}


def log_llm_call(agent_name, task_type, model, usage, duration_ms=0):
    """Log an LLM call with token counts and estimated cost."""
    try:
        pricing = (_budget_config_cache or {}).get("pricing", {}).get(model, {})
        input_tok = getattr(usage, 'input_tokens', 0) or getattr(usage, 'prompt_tokens', 0) or 0
        output_tok = getattr(usage, 'output_tokens', 0) or getattr(usage, 'completion_tokens', 0) or 0
        total_tok = input_tok + output_tok
        cost = (input_tok * pricing.get("input", 0) + output_tok * pricing.get("output", 0)) / 1_000_000

        supabase.table("llm_call_log").insert({
            "agent_name": agent_name,
            "task_type": task_type,
            "model": model,
            "provider": pricing.get("provider", "unknown"),
            "input_tokens": input_tok,
            "output_tokens": output_tok,
            "total_tokens": total_tok,
            "estimated_cost": round(cost, 6),
            "duration_ms": duration_ms,
        }).execute()
    except Exception as e:
        logger.warning(f"Failed to log LLM call: {e}")


def is_daily_budget_exhausted(agent_name: str) -> bool:
    """Return True if this agent has hit its daily LLM call limit."""
    if not supabase:
        return False

    config_path = Path(OPENCLAW_DATA_DIR) / "config" / "agentpulse-config.json"
    try:
        with open(config_path) as f:
            config = json.load(f)
        max_calls = config.get("budgets", {}).get("global", {}).get("max_daily_llm_calls", 100)
    except Exception:
        max_calls = 100

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        row = (
            supabase.table("agent_daily_usage")
            .select("llm_calls_used")
            .eq("agent_name", agent_name)
            .eq("date", today)
            .execute()
        )
        if row.data:
            used = row.data[0].get("llm_calls_used", 0) or 0
            if used >= max_calls:
                logger.warning(
                    f"Daily LLM budget exhausted for {agent_name}: "
                    f"{used}/{max_calls} calls used today — skipping task"
                )
                return True
    except Exception as e:
        logger.warning(f"Could not check daily budget for {agent_name}: {e}")
    return False


def increment_daily_usage(agent_name: str, llm_calls: int = 0, subtasks: int = 0, alerts: int = 0):
    """Upsert today's usage row for the given agent in agent_daily_usage."""
    if not supabase:
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        existing = (
            supabase.table("agent_daily_usage")
            .select("*")
            .eq("agent_name", agent_name)
            .eq("date", today)
            .execute()
        )

        if existing.data:
            row = existing.data[0]
            supabase.table("agent_daily_usage").update({
                "llm_calls_used": (row.get("llm_calls_used", 0) or 0) + llm_calls,
                "subtasks_created": (row.get("subtasks_created", 0) or 0) + subtasks,
                "proactive_alerts_sent": (row.get("proactive_alerts_sent", 0) or 0) + alerts,
            }).eq("id", row["id"]).execute()
        else:
            supabase.table("agent_daily_usage").insert({
                "agent_name": agent_name,
                "date": today,
                "llm_calls_used": llm_calls,
                "subtasks_created": subtasks,
                "proactive_alerts_sent": alerts,
                "total_cost_estimate": 0,
            }).execute()

    except Exception as e:
        logger.error(f"Failed to increment daily usage for {agent_name}: {e}")


def check_stale_tasks():
    """Force-fail tasks stuck in_progress longer than 2x their budget max_seconds."""
    if not supabase:
        return

    try:
        in_progress = (
            supabase.table("agent_tasks")
            .select("*")
            .eq("status", "in_progress")
            .eq("assigned_to", AGENT_NAME)
            .execute()
        )

        now = datetime.now(timezone.utc)

        for task in in_progress.data or []:
            started_at = task.get("started_at")
            if not started_at:
                continue

            # Parse started_at timestamp
            try:
                if started_at.endswith("Z"):
                    started_at = started_at.replace("Z", "+00:00")
                started_dt = datetime.fromisoformat(started_at)
                if started_dt.tzinfo is None:
                    started_dt = started_dt.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue

            task_type = task.get("task_type", "unknown")
            budget = get_budget_config(AGENT_NAME, task_type)
            timeout_seconds = budget["max_seconds"] * 2

            elapsed = (now - started_dt).total_seconds()
            if elapsed > timeout_seconds:
                logger.warning(
                    f"Task {task['id']} ({task_type}) exceeded safety timeout "
                    f"({elapsed:.0f}s > {timeout_seconds}s) — force-failing"
                )
                mark_task_status(
                    task["id"],
                    "failed",
                    completed_at=now.isoformat(),
                    error_message="budget_timeout",
                )

    except Exception as e:
        logger.error(f"Error checking stale tasks: {e}")


# ---------------------------------------------------------------------------
# Task polling
# ---------------------------------------------------------------------------

def fetch_pending_tasks(limit: int = 3) -> list[dict]:
    """Atomically claim up to `limit` pending tasks via FOR UPDATE SKIP LOCKED."""
    result = supabase.rpc(
        "claim_agent_task",
        {"p_assigned_to": AGENT_NAME, "p_limit": limit},
    ).execute()
    return result.data or []


def validate_task_input(task_type: str, input_data: dict) -> None:
    """Validate inbound task input. Raises ValidationError on bad input (fail fast)."""
    schema = TASK_INPUT_SCHEMAS.get(task_type)
    if schema is None:
        logger.warning(f"No input schema for task_type='{task_type}', skipping validation")
        return
    schema.model_validate(input_data)


def validate_llm_output(raw: dict, model_cls: type) -> object:
    """Validate LLM output. On failure, constructs partial model and logs."""
    try:
        return model_cls.model_validate(raw)
    except ValidationError as e:
        logger.warning(f"LLM output validation errors ({model_cls.__name__}): {e}")
        valid_fields = {k: raw[k] for k in model_cls.model_fields if k in raw}
        return model_cls.model_construct(**valid_fields)


def mark_task_status(task_id: str, status: str, **fields):
    payload = {"status": status, **fields}
    supabase.table("agent_tasks").update(payload).eq("id", task_id).execute()


# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------

def run_analysis(task_type: str, input_data: dict, budget_config: dict) -> dict:
    """Call OpenAI with identity + skill as system prompt, task + data as user message."""

    identity = load_identity(AGENT_DIR)
    skill = load_skill(SKILL_DIR)

    system_prompt = f"{identity}\n\n---\n\nSKILL REFERENCE:\n{skill}"
    system_prompt += "\n\nYou MUST respond with valid JSON only — no markdown fences, no extra text."

    user_msg = (
        f"TASK TYPE: {task_type}\n\n"
        f"BUDGET: {json.dumps(budget_config)}\n\n"
        f"INPUT DATA:\n{json.dumps(input_data, indent=2, default=str)}"
    )

    logger.info(f"Calling {MODEL} for {task_type}...")

    _t0 = time.time()
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=8192,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    log_llm_call("analyst", task_type, MODEL, response.usage, int((time.time() - _t0) * 1000))

    text = response.choices[0].message.content.strip()

    # Clean markdown fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    result = json.loads(text)
    logger.info(f"Analysis complete: {result.get('executive_summary', '?')[:100]}...")
    return result


# ---------------------------------------------------------------------------
# Persist results to Supabase
# ---------------------------------------------------------------------------

def persist_analysis_run(analysis: dict):
    """Insert a row into analysis_runs."""
    try:
        self_critique = analysis.get("self_critique", {})
        supabase.table("analysis_runs").insert({
            "run_type": analysis.get("run_type", "full_analysis"),
            "trigger": "task",
            "status": "completed",
            "reasoning_steps": analysis.get("reasoning_steps"),
            "key_findings": analysis.get("key_findings"),
            "analyst_notes": analysis.get("executive_summary"),
            "confidence_level": self_critique.get("confidence_level", "medium"),
            "caveats": self_critique.get("caveats", []),
            "flags": self_critique.get("additional_data_needed", []),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        logger.info("Inserted analysis_runs row")
    except Exception as e:
        logger.error(f"Failed to insert analysis_runs: {e}")


def update_opportunities(analysis: dict):
    """Update opportunities with analyst reasoning."""
    for opp in analysis.get("opportunities", []):
        opp_id = opp.get("id")
        if not opp_id:
            continue
        try:
            # Read current review_count to increment
            current = (
                supabase.table("opportunities")
                .select("review_count")
                .eq("id", opp_id)
                .limit(1)
                .execute()
            )
            current_count = (current.data[0].get("review_count") or 0) if current.data else 0

            supabase.table("opportunities").update({
                "confidence_score": opp.get("confidence_score"),
                "analyst_reasoning": opp.get("reasoning_chain"),
                "analyst_confidence_notes": json.dumps(opp.get("downgrade_factors", [])),
                "signal_sources": opp.get("signal_sources"),
                "last_reviewed_at": datetime.now(timezone.utc).isoformat(),
                "review_count": current_count + 1,
            }).eq("id", opp_id).execute()
            logger.info(f"Updated opportunity {opp_id}")
        except Exception as e:
            logger.error(f"Failed to update opportunity {opp_id}: {e}")


def persist_cross_signals(analysis: dict):
    """Insert cross-pipeline signals."""
    for signal in analysis.get("cross_signals", []):
        try:
            row = {
                "signal_type": signal.get("type"),
                "description": signal.get("description"),
                "strength": signal.get("strength"),
                "reasoning": signal.get("reasoning"),
            }
            if signal.get("cluster_id"):
                row["problem_cluster_id"] = signal["cluster_id"]
            if signal.get("tool_name"):
                row["tool_name"] = signal["tool_name"]
            if signal.get("opportunity_id"):
                row["opportunity_id"] = signal["opportunity_id"]

            supabase.table("cross_signals").insert(row).execute()
            logger.info(f"Inserted cross_signal: {signal.get('type')}")
        except Exception as e:
            logger.error(f"Failed to insert cross_signal: {e}")


def save_analysis_report(analysis: dict):
    """Save a local markdown analysis report."""
    try:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        run_type = analysis.get("run_type", "analysis")
        filename = f"{run_type}_{date_str}.md"

        summary = analysis.get("executive_summary", "No summary")
        findings = analysis.get("key_findings", [])
        critique = analysis.get("self_critique", {})

        content = f"# Analysis Report — {date_str}\n\n"
        content += f"## Executive Summary\n\n{summary}\n\n"
        content += f"## Confidence: {critique.get('confidence_level', '?')}\n\n"

        if findings:
            content += "## Key Findings\n\n"
            for i, f in enumerate(findings, 1):
                content += f"{i}. **{f.get('finding', '?')}** ({f.get('significance', '?')})\n"
                content += f"   Evidence: {', '.join(f.get('evidence', []))}\n\n"

        caveats = critique.get("caveats", [])
        if caveats:
            content += "## Caveats\n\n"
            for c in caveats:
                content += f"- {c}\n"

        (ANALYSIS_DIR / filename).write_text(content)
        logger.info(f"Saved analysis report: {filename}")
    except Exception as e:
        logger.error(f"Failed to save analysis report: {e}")


# ---------------------------------------------------------------------------
# Proactive alert handling
# ---------------------------------------------------------------------------

def handle_proactive_alert(analysis: dict, task_type: str):
    """If the Analyst flagged a proactive alert, create a send_alert task."""
    if task_type != "proactive_analysis":
        return
    if not analysis.get("alert"):
        return
    if not supabase:
        return

    alert_message = analysis.get("alert_message", "Anomaly confirmed by Analyst (no details provided)")
    try:
        supabase.table("agent_tasks").insert({
            "task_type": "send_alert",
            "assigned_to": "processor",
            "created_by": "analyst",
            "priority": 1,
            "input_data": {
                "alert_message": alert_message,
                "anomaly_type": analysis.get("anomaly_type"),
                "details": analysis.get("alert_details", {}),
            },
        }).execute()
        logger.info(f"Created send_alert task: {alert_message[:80]}...")
        increment_daily_usage(AGENT_NAME, alerts=1)
    except Exception as e:
        logger.error(f"Failed to create send_alert task: {e}")


# ---------------------------------------------------------------------------
# Autonomous data requests
# ---------------------------------------------------------------------------

def handle_data_requests(analysis: dict, parent_task_id: str):
    """Create subtasks for any data_requests the Analyst included in its response."""
    if not supabase:
        return

    data_requests = analysis.get("data_requests")
    if not data_requests:
        return

    for request in data_requests:
        req_type = request.get("type")
        try:
            if req_type == "targeted_scrape":
                supabase.table("agent_tasks").insert({
                    "task_type": "targeted_scrape",
                    "assigned_to": "processor",
                    "created_by": "analyst",
                    "priority": 1,
                    "input_data": {
                        "submolts": request.get("submolts", []),
                        "posts_per_submolt": request.get("posts_per", 50),
                        "reason": request.get("reason", "analyst_data_request"),
                        "parent_task_id": parent_task_id,
                    },
                }).execute()
                logger.info(
                    f"Created targeted_scrape subtask for analyst "
                    f"(submolts={request.get('submolts', [])})"
                )
                increment_daily_usage(AGENT_NAME, subtasks=1)
            else:
                logger.warning(f"Unknown data_request type: {req_type}")
        except Exception as e:
            logger.error(f"Failed to create subtask for data_request ({req_type}): {e}")


# ---------------------------------------------------------------------------
# Negotiation response handling
# ---------------------------------------------------------------------------

def handle_negotiation_response(analysis: dict, task: dict, task_id: str):
    """If this task was part of a negotiation, respond to it via the processor."""
    if not supabase:
        return

    input_data = task.get("input_data", {}) or {}
    negotiation_req = input_data.get("negotiation_request")
    if not negotiation_req:
        return

    # The negotiation_id may be in the input_data or we look it up
    negotiation_id = input_data.get("negotiation_id")

    # Determine if the analyst met the quality criteria
    criteria_met = analysis.get("negotiation_criteria_met", True)
    response_summary = analysis.get("negotiation_response_summary", analysis.get("executive_summary", ""))

    try:
        supabase.table("agent_tasks").insert({
            "task_type": "respond_to_negotiation",
            "assigned_to": "processor",
            "created_by": AGENT_NAME,
            "priority": 2,
            "input_data": {
                "negotiation_id": negotiation_id,
                "response_task_id": task_id,
                "criteria_met": criteria_met,
                "response_summary": response_summary,
            },
        }).execute()
        logger.info(
            f"Created respond_to_negotiation task for negotiation {negotiation_id} "
            f"(criteria_met={criteria_met})"
        )
    except Exception as e:
        logger.error(f"Failed to create negotiation response task: {e}")


# ---------------------------------------------------------------------------
# Task processing
# ---------------------------------------------------------------------------

def process_task(task: dict):
    """Process a single analyst task."""
    task_id = task["id"]
    task_type = task.get("task_type", "unknown")
    input_data = task.get("input_data", {}) or {}

    logger.info(f"Processing task {task_id}: {task_type}")

    # Task is already in_progress — claimed atomically by fetch_pending_tasks()

    # Validate task type
    supported = {"full_analysis", "deep_dive", "review_opportunity", "proactive_analysis", "enrich_for_newsletter"}
    if task_type not in supported:
        error = f"Unknown task type: {task_type}"
        logger.error(error)
        mark_task_status(
            task_id, "failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=error,
        )
        return

    # Validate input schema (fail fast on malformed input)
    try:
        validate_task_input(task_type, input_data)
    except ValidationError as e:
        error = f"Input validation: {e}"
        logger.error(error)
        mark_task_status(
            task_id, "failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=error,
        )
        return

    # Inject budget constraints so the LLM knows its limits
    budget = get_budget_config(AGENT_NAME, task_type)
    input_data["budget"] = budget
    logger.info(f"Budget for {task_type}: {budget}")

    # Check global daily LLM budget before making any API calls
    if is_daily_budget_exhausted(AGENT_NAME):
        mark_task_status(
            task_id, "failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message="daily_budget_exhausted",
        )
        return

    try:
        # Run the analysis via OpenAI
        raw_analysis = run_analysis(task_type, input_data, budget)
        validated = validate_llm_output(raw_analysis, AnalystOutput)
        analysis = validated.model_dump()

        # Persist results to Supabase
        persist_analysis_run(analysis)
        update_opportunities(analysis)
        persist_cross_signals(analysis)
        save_analysis_report(analysis)

        # Track budget usage from the response
        budget_usage = analysis.get("budget_usage")
        if budget_usage:
            logger.info(
                f"Budget usage for {task_id}: "
                f"llm_calls={budget_usage.get('llm_calls_used', 0)}, "
                f"time={budget_usage.get('elapsed_seconds', 0)}s, "
                f"retries={budget_usage.get('retries_used', 0)}"
            )
            increment_daily_usage(
                AGENT_NAME,
                llm_calls=budget_usage.get("llm_calls_used", 0),
                subtasks=budget_usage.get("subtasks_created", 0),
            )
        else:
            # Even without explicit tracking, count at least 1 LLM call
            increment_daily_usage(AGENT_NAME, llm_calls=1)

        # Handle autonomous data requests from the Analyst
        handle_data_requests(analysis, task_id)

        # Handle proactive alert flag (for proactive_analysis tasks)
        handle_proactive_alert(analysis, task_type)

        # Handle negotiation responses (if this task was part of a negotiation)
        handle_negotiation_response(analysis, task, task_id)

        # Mark task completed
        mark_task_status(
            task_id, "completed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            output_data=analysis,
        )
        logger.info(f"Task {task_id} completed successfully")

    except json.JSONDecodeError as e:
        error = f"Failed to parse model response as JSON: {e}"
        logger.error(error)
        mark_task_status(
            task_id, "failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=error,
        )
    except Exception as e:
        error = f"Unexpected error: {e}"
        logger.error(error)
        mark_task_status(
            task_id, "failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=str(e),
        )


# ---------------------------------------------------------------------------
# Prediction monitoring
# ---------------------------------------------------------------------------

PREDICTION_ASSESSMENT_PROMPT = """You are evaluating whether new evidence affects an existing prediction.

Prediction: "{prediction_text}"
Made in issue #{issue_number} on {created_at}

New evidence from the last 7 days:
{evidence_summary}

Assess:
1. Does this evidence CONFIRM the prediction, CONTRADICT it, or is it NEUTRAL?
2. How significant is this evidence? (low / medium / high)
3. If significant, summarize in 2-3 sentences what happened and how it relates to the prediction.

Output as JSON:
{{"direction": "confirms" | "contradicts" | "neutral", "significance": "low" | "medium" | "high", "evidence_summary": "..."}}"""


def monitor_predictions():
    """Check open predictions against recent source material. Flags HIGH significance only."""
    if not supabase or not client:
        return

    try:
        expire_stale_predictions()
    except Exception as e:
        logger.error(f"Stale prediction expiry failed: {e}")

    try:
        result = supabase.table("predictions")\
            .select("*")\
            .eq("status", "open")\
            .order("created_at", desc=True)\
            .limit(PREDICTION_MAX_OPEN)\
            .execute()
        open_predictions = result.data or []
    except Exception as e:
        logger.error(f"Failed to fetch open predictions: {e}")
        return

    if not open_predictions:
        logger.debug("No open predictions to monitor")
        return

    logger.info(f"Monitoring {len(open_predictions)} open predictions")

    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=7)).isoformat()

    try:
        recent = supabase.table("source_posts")\
            .select("title, body, source, source_url, tags")\
            .gte("scraped_at", cutoff)\
            .order("score", desc=True)\
            .limit(200)\
            .execute()
        recent_items = recent.data or []
    except Exception as e:
        logger.error(f"Failed to fetch recent items for prediction monitoring: {e}")
        return

    if not recent_items:
        logger.info("No recent items — skipping prediction monitoring")
        return

    total_tokens = 0
    flagged_count = 0

    for prediction in open_predictions:
        try:
            tokens = assess_and_flag(prediction, recent_items)
            total_tokens += tokens
            if tokens < 0:
                flagged_count += 1
                total_tokens += abs(tokens)
        except Exception as e:
            logger.error(f"Error assessing prediction {prediction.get('id', '?')}: {e}")

    logger.info(f"Prediction monitoring done: {len(open_predictions)} checked, {flagged_count} flagged, ~{total_tokens} tokens used")
    increment_daily_usage(AGENT_NAME, llm_calls=len(open_predictions))


def assess_and_flag(prediction: dict, recent_items: list) -> int:
    """Assess one prediction against recent items. Returns token count (negative if flagged)."""
    pred_id = prediction.get("id", "")
    topic_id = prediction.get("topic_id", "")
    pred_text = prediction.get("prediction_text", "")

    if not pred_text:
        return 0

    search_terms = topic_id.lower().replace("_", " ").split() if topic_id else pred_text.lower().split()[:5]

    related = []
    for item in recent_items:
        text = f"{item.get('title', '')} {item.get('body', '')}".lower()
        if any(term in text for term in search_terms if len(term) > 2):
            related.append(item)

    if not related:
        return 0

    evidence_lines = []
    for item in related[:10]:
        src = item.get("source", "?")
        title = item.get("title", "Untitled")
        body = (item.get("body") or "")[:200]
        evidence_lines.append(f"[{src}] {title}\n{body}")

    evidence_text = "\n\n".join(evidence_lines)

    prompt = PREDICTION_ASSESSMENT_PROMPT.format(
        prediction_text=pred_text,
        issue_number=prediction.get("issue_number", "?"),
        created_at=prediction.get("created_at", "?"),
        evidence_summary=evidence_text,
    )

    try:
        _t0 = time.time()
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        log_llm_call("analyst", "prediction_assessment", MODEL, response.usage, int((time.time() - _t0) * 1000))

        tokens_used = (response.usage.total_tokens if response.usage else 0)
        raw = response.choices[0].message.content.strip()

        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        assessment = json.loads(raw)

        significance = assessment.get("significance", "low")
        direction = assessment.get("direction", "neutral")
        summary = assessment.get("evidence_summary", "")

        logger.info(f"Prediction {pred_id[:8]}: {direction}/{significance}")

        if significance == "high" and direction != "neutral":
            existing_notes = prediction.get("evidence_notes") or ""
            new_note = f"[{direction}] {summary}"
            combined_notes = f"{existing_notes}\n{new_note}".strip() if existing_notes else new_note

            supabase.table("predictions").update({
                "status": "flagged",
                "evidence_notes": combined_notes,
                "flagged_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", pred_id).execute()
            logger.info(f"FLAGGED prediction {pred_id[:8]}: {direction} -- {summary[:80]}")
            return -tokens_used

        return tokens_used

    except Exception as e:
        logger.error(f"LLM assessment failed for prediction {pred_id[:8]}: {e}")
        return 0


def expire_stale_predictions():
    """Auto-close predictions older than PREDICTION_STALE_DAYS as 'expired'."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=PREDICTION_STALE_DAYS)).isoformat()

    try:
        stale = supabase.table("predictions")\
            .select("id")\
            .eq("status", "open")\
            .lt("created_at", cutoff)\
            .execute()

        for pred in (stale.data or []):
            supabase.table("predictions").update({
                "status": "expired",
                "resolution_notes": f"Auto-expired after {PREDICTION_STALE_DAYS} days with no resolution",
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", pred["id"]).execute()

        if stale.data:
            logger.info(f"Expired {len(stale.data)} stale predictions (>{PREDICTION_STALE_DAYS} days)")
    except Exception as e:
        logger.error(f"Failed to expire stale predictions: {e}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    ensure_dirs()
    if not init():
        logger.error("Initialization failed — exiting")
        return

    logger.info("=" * 50)
    logger.info(f"  Analyst agent started (model={MODEL}, poll={POLL_INTERVAL}s)")
    logger.info("=" * 50)

    identity_text = load_identity(AGENT_DIR)
    logger.info(f"Identity loaded from {AGENT_DIR}: {len(identity_text)} chars")
    skill_text = load_skill(SKILL_DIR)
    logger.info(f"Skill loaded from {SKILL_DIR}: {len(skill_text)} chars")

    while True:
        try:
            check_stale_tasks()
            tasks = fetch_pending_tasks()
            for task in tasks:
                process_task(task)
        except Exception as e:
            logger.error(f"Poll loop error: {e}")

        try:
            monitor_predictions()
        except Exception as e:
            logger.error(f"Prediction monitoring error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
