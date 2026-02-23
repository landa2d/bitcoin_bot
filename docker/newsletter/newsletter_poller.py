#!/usr/bin/env python3
"""
Newsletter agent — direct Anthropic integration.

Polls Supabase agent_tasks for write_newsletter tasks, calls the Anthropic API
to generate the newsletter, saves results to Supabase, and marks the task done.
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError
from supabase import create_client, Client
from openai import OpenAI

from schemas import TASK_INPUT_SCHEMAS, NewsletterOutput

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AGENT_NAME = os.getenv("AGENT_NAME", "newsletter")
OPENCLAW_DATA_DIR = os.getenv("OPENCLAW_DATA_DIR", "/home/openclaw/.openclaw")
POLL_INTERVAL = int(os.getenv("NEWSLETTER_POLL_INTERVAL", "30"))
MODEL = os.getenv("NEWSLETTER_MODEL", "gpt-4o")

WORKSPACE = Path(OPENCLAW_DATA_DIR) / "workspace"
NEWSLETTERS_DIR = WORKSPACE / "agentpulse" / "newsletters"

# Logging
LOG_DIR = Path(OPENCLAW_DATA_DIR) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "newsletter-poller.log"),
    ],
)
logger = logging.getLogger("newsletter-agent")

supabase: Client | None = None
client: OpenAI | None = None

# ---------------------------------------------------------------------------
# Identity + Skill loading (from disk, with mtime caching)
# ---------------------------------------------------------------------------

AGENT_DIR = Path(OPENCLAW_DATA_DIR) / "agents" / "newsletter" / "agent"
SKILL_DIR = Path(OPENCLAW_DATA_DIR) / "skills" / "newsletter"

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
            "You are Pulse, the editorial voice of AgentPulse. "
            "Write the weekly Intelligence Brief as valid JSON."
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


def init():
    global supabase, client
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Supabase not configured (SUPABASE_URL / SUPABASE_KEY missing)")
        return False
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set — cannot generate newsletters")
        return False
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    client = OpenAI(api_key=OPENAI_API_KEY)
    return True


def ensure_dirs():
    NEWSLETTERS_DIR.mkdir(parents=True, exist_ok=True)


def fetch_pending_tasks(limit: int = 5) -> list[dict]:
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


def generate_newsletter(task_type: str, input_data: dict, budget_config: dict) -> dict:
    """Call OpenAI with identity + skill as system prompt, task + data as user message."""

    identity = load_identity(AGENT_DIR)
    skill = load_skill(SKILL_DIR)

    system_prompt = f"{identity}\n\n---\n\nSKILL REFERENCE:\n{skill}"
    system_prompt += (
        "\n\nYou MUST respond with valid JSON only — no markdown fences, no extra text."
        "\n\nCRITICAL RULES — CHECK BEFORE WRITING EACH SECTION:"
        "\n1. SPOTLIGHT (section 2): If `spotlight` is null OR missing from input_data,"
        " OMIT the ENTIRE section — no header, no placeholder text, no explanation."
        " Go directly from the Cold open to section 3 The Big Insight."
        "\n2. ON OUR RADAR (section 6): If `radar_topics` has fewer than 3 items,"
        " OMIT the ENTIRE section — no header, no 'nothing to report' note."
        " Skip from section 5 straight to section 7."
        "\n3. SECTION ORDER: Write every required section in order and complete it"
        " before moving on. Required: Cold open, One Number (if data supports), 3, 4, 5,"
        " 7, 8, Who's Moving, 9, 10. Never stop before completing section 10 (Gato's Corner)."
        "\n4. SECTION 3 BIG INSIGHT: The first line of the body MUST be the thesis in"
        " **bold markdown** — e.g. `**Your thesis here**`. Thesis must be falsifiable."
        "\n5. GATO'S CORNER (section 10): ALWAYS write this. It is the last section."
        " NEVER omit it. A newsletter without Gato's Corner is a failed newsletter."
        "\n6. SECTION 2 SPOTLIGHT WORD COUNT: If spotlight IS present, the section body"
        " MUST be 400-500 words. Under 350 is a hard failure — expand before moving on."
        "\n7. ONE NUMBER: If a real, sourceable data point exists in input_data stats or"
        " analyst_insights, include it as `## One Number` after the Cold open."
        " Format: `**[Number]** — [one sentence]`. NEVER fabricate a number."
        "\n8. WHO'S MOVING: After Tool Radar, always write a `## Who's Moving` section"
        " with 2-3 bullets: `**[Entity]** — [one sentence]`. Pull from analyst_insights,"
        " clusters, or trending_tools. Minimum 1 real entry."
        "\n9. NO PLACEHOLDER TEXT: Never end a section with 'Watch for...', 'investigation"
        " underway', or any incomplete sentence. Complete every entry or cut it entirely."
        "\n10. FILLER PHRASES BANNED: Delete any instance of: 'navigating without a map',"
        " 'wake-up call', 'smart businesses are already', 'sifting through the narrative',"
        " 'elevated urgency'. Write like a reporter, not a business deck."
    )

    user_msg = (
        f"TASK TYPE: {task_type}\n\n"
        f"BUDGET: {json.dumps(budget_config)}\n\n"
        f"INPUT DATA:\n{json.dumps(input_data, indent=2, default=str)}"
    )

    logger.info(f"Calling {MODEL} for {task_type}...")

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=16000,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
    )

    text = response.choices[0].message.content.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    result = json.loads(text)

    # The LLM may wrap content in a "result" key following the SKILL.md output format
    if "result" in result and isinstance(result["result"], dict):
        inner = result["result"]
        # Merge budget_usage and negotiation_request to top level if present
        for extra_key in ("budget_usage", "negotiation_request"):
            if extra_key in result:
                inner[extra_key] = result[extra_key]
        result = inner

    logger.info(f"Newsletter generated: \"{result.get('title', '?')}\"")
    return result


def save_newsletter(result: dict, input_data: dict):
    """Save newsletter to Supabase and local file."""
    edition = result.get("edition", input_data.get("edition_number", 0))
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Upsert into newsletters table
    row = {
        "edition_number": edition,
        "title": result.get("title", f"Edition #{edition}"),
        "content_markdown": result.get("content_markdown", ""),
        "content_telegram": result.get("content_telegram", ""),
        "data_snapshot": input_data,
        "status": "draft",
    }
    try:
        supabase.table("newsletters").insert(row).execute()
        logger.info(f"Saved newsletter edition #{edition} to Supabase (status=draft)")
    except Exception as e:
        logger.error(f"Failed to insert newsletter #{edition} into Supabase: {e}")

    # Save local markdown
    md_file = NEWSLETTERS_DIR / f"brief_{edition}_{date_str}.md"
    try:
        md_file.write_text(result.get("content_markdown", ""))
        logger.info(f"Saved local file: {md_file.name}")
    except OSError as e:
        logger.error(f"Failed to write newsletter file {md_file}: {e}")


# ---------------------------------------------------------------------------
# Negotiation request handling
# ---------------------------------------------------------------------------

def handle_negotiation_request(result: dict, task_id: str):
    """If the Newsletter agent requests enrichment, create the negotiation and task."""
    if not supabase:
        return

    negotiation_req = result.get("negotiation_request")
    if not negotiation_req:
        return
    if not isinstance(negotiation_req, dict):
        logger.warning(f"negotiation_request is not a dict (got {type(negotiation_req).__name__}) — skipping")
        return

    target_agent = negotiation_req.get("target_agent", "analyst")
    request_summary = negotiation_req.get("request", "")
    quality_criteria = negotiation_req.get("min_quality", "")
    needed_by = negotiation_req.get("needed_by")
    enrichment_task_type = negotiation_req.get("task_type", "enrich_for_newsletter")
    enrichment_input = negotiation_req.get("input_data", {})

    try:
        # Create the negotiation record via the processor task type
        neg_result = supabase.table("agent_tasks").insert({
            "task_type": "create_negotiation",
            "assigned_to": "processor",
            "created_by": AGENT_NAME,
            "priority": 2,
            "input_data": {
                "requesting_agent": AGENT_NAME,
                "responding_agent": target_agent,
                "request_task_id": task_id,
                "request_summary": request_summary,
                "quality_criteria": quality_criteria,
                "needed_by": needed_by,
            },
        }).execute()
        logger.info(f"Created create_negotiation task for {AGENT_NAME} → {target_agent}")

        # Create the enrichment task for the target agent
        supabase.table("agent_tasks").insert({
            "task_type": enrichment_task_type,
            "assigned_to": target_agent,
            "created_by": AGENT_NAME,
            "priority": 2,
            "input_data": {
                **enrichment_input,
                "negotiation_request": {
                    "requesting_agent": AGENT_NAME,
                    "request_summary": request_summary,
                    "quality_criteria": quality_criteria,
                    "needed_by": needed_by,
                },
            },
        }).execute()
        logger.info(f"Created {enrichment_task_type} task for {target_agent}")

    except Exception as e:
        logger.error(f"Failed to handle negotiation request: {e}")


# ---------------------------------------------------------------------------
# Scorecard — "Looking Back" blurb generation
# ---------------------------------------------------------------------------

LOOKBACK_PROMPT = """You are writing a brief lookback for the AgentPulse newsletter. Be honest and direct. No defensive language. If the prediction was wrong, say so plainly. If right, state it without gloating. Keep it to 3-4 sentences maximum.

Original thesis: "{thesis}"
Our prediction (Issue #{issue_number}): "{prediction_text}"
What actually happened: "{resolution_notes}"
Assessment: {status}

Write the lookback blurb. Start with "In Issue #{issue_number}, we predicted..." or similar. End with an honest one-sentence assessment of what we got right and wrong. Output ONLY the blurb text, no JSON, no formatting."""

MAX_LOOKBACKS_PER_ISSUE = 2


def generate_scorecard(current_issue_number: int) -> list[str]:
    """Fetch resolved predictions and generate Looking Back blurbs. Returns list of blurb strings."""
    try:
        resolved = supabase.table("predictions")\
            .select("*, spotlight_history(*)")\
            .in_("status", ["confirmed", "refuted", "partially_correct"])\
            .is_("scorecard_issue", "null")\
            .order("resolved_at", desc=True)\
            .limit(MAX_LOOKBACKS_PER_ISSUE)\
            .execute()
    except Exception as e:
        logger.error(f"Failed to fetch resolved predictions for scorecard: {e}")
        return []

    if not resolved.data:
        logger.info("No resolved predictions — skipping Scorecard")
        return []

    logger.info(f"Generating scorecard for {len(resolved.data)} resolved predictions")
    blurbs = []

    for prediction in resolved.data:
        pred_id = prediction.get("id", "")
        pred_text = prediction.get("prediction_text", "")
        issue_num = prediction.get("issue_number", "?")
        status = prediction.get("status", "unknown")
        resolution_notes = prediction.get("resolution_notes", "No details available.")

        spotlight = prediction.get("spotlight_history") or {}
        thesis = spotlight.get("thesis", pred_text)

        blurb = generate_lookback_blurb(
            thesis=thesis,
            prediction_text=pred_text,
            issue_number=issue_num,
            resolution_notes=resolution_notes,
            status=status,
        )

        if blurb:
            blurbs.append(blurb)
            try:
                supabase.table("predictions").update({
                    "scorecard_issue": current_issue_number,
                }).eq("id", pred_id).execute()
                logger.info(f"Marked prediction {pred_id[:8]} as included in scorecard (issue {current_issue_number})")
            except Exception as e:
                logger.error(f"Failed to mark prediction {pred_id[:8]} scorecard_issue: {e}")

    return blurbs


def generate_lookback_blurb(thesis: str, prediction_text: str, issue_number, resolution_notes: str, status: str) -> str | None:
    """Generate a single Looking Back blurb via LLM."""
    prompt = LOOKBACK_PROMPT.format(
        thesis=thesis,
        issue_number=issue_number,
        prediction_text=prediction_text,
        resolution_notes=resolution_notes,
        status=status,
    )

    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )

        blurb = response.choices[0].message.content.strip()

        if blurb.startswith('"') and blurb.endswith('"'):
            blurb = blurb[1:-1]

        tokens = response.usage.total_tokens if response.usage else 0
        logger.info(f"Lookback blurb generated ({tokens} tokens): {blurb[:60]}...")
        return blurb

    except Exception as e:
        logger.error(f"Failed to generate lookback blurb for issue #{issue_number}: {e}")
        return None


def format_scorecard_section(blurbs: list[str]) -> str:
    """Format scorecard blurbs into the Looking Back newsletter section."""
    if not blurbs:
        return ""

    parts = ["\n\n---\n\n## Looking Back\n"]
    for blurb in blurbs:
        parts.append(f"\n{blurb}\n")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Task processing
# ---------------------------------------------------------------------------

def get_budget_config(agent_name: str, task_type: str) -> dict:
    """Read budget limits for a given agent + task type from agentpulse-config.json."""
    defaults = {
        "max_llm_calls": 6,
        "max_seconds": 300,
        "max_subtasks": 2,
        "max_retries": 2,
    }

    config_path = Path(OPENCLAW_DATA_DIR) / "config" / "agentpulse-config.json"
    try:
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
        else:
            return defaults
    except Exception:
        return defaults

    budgets = config.get("budgets", {})
    task_budget = budgets.get(agent_name, {}).get(task_type, {})
    return {k: task_budget.get(k, defaults[k]) for k in defaults}


def process_task(task: dict):
    """Process a single newsletter task."""
    task_id = task["id"]
    task_type = task.get("task_type", "unknown")
    input_data = task.get("input_data", {}) or {}

    logger.info(f"Processing task {task_id}: {task_type}")

    # Task is already in_progress — claimed atomically by fetch_pending_tasks()

    supported = {"write_newsletter", "revise_newsletter"}
    if task_type not in supported:
        error = f"Unknown task type: {task_type}"
        logger.error(error)
        mark_task_status(
            task_id,
            "failed",
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

    # Inject budget constraints
    budget = get_budget_config(AGENT_NAME, task_type)
    input_data["budget"] = budget
    logger.info(f"Budget for {task_type}: {budget}")

    try:
        # Generate newsletter via OpenAI
        raw_result = generate_newsletter(task_type, input_data, budget)
        validated = validate_llm_output(raw_result, NewsletterOutput)
        result = validated.model_dump()

        # Generate scorecard (Looking Back) if resolved predictions exist
        edition = result.get("edition", input_data.get("edition_number", 0))
        try:
            scorecard_blurbs = generate_scorecard(edition)
            if scorecard_blurbs:
                scorecard_md = format_scorecard_section(scorecard_blurbs)
                if result.get("content_markdown"):
                    result["content_markdown"] += scorecard_md
                if result.get("content_telegram"):
                    result["content_telegram"] += scorecard_md
                logger.info(f"Appended {len(scorecard_blurbs)} Looking Back blurb(s) to newsletter")
        except Exception as e:
            logger.error(f"Scorecard generation failed (non-blocking): {e}")

        # Save to Supabase + local file
        save_newsletter(result, input_data)

        # Handle negotiation requests (e.g. enrichment from Analyst)
        handle_negotiation_request(result, task_id)

        # Mark task completed
        mark_task_status(
            task_id,
            "completed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            output_data=result,
        )
        logger.info(f"Task {task_id} completed successfully")

    except json.JSONDecodeError as e:
        error = f"Failed to parse model response as JSON: {e}"
        logger.error(error)
        mark_task_status(
            task_id,
            "failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=error,
        )
    except Exception as e:
        error = f"Unexpected error: {e}"
        logger.error(error)
        mark_task_status(
            task_id,
            "failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=str(e),
        )


def main():
    ensure_dirs()
    if not init():
        logger.error("Initialization failed — exiting")
        return

    logger.info(f"Newsletter agent started (model={MODEL}, poll={POLL_INTERVAL}s)")

    identity_text = load_identity(AGENT_DIR)
    logger.info(f"Identity loaded from {AGENT_DIR}: {len(identity_text)} chars")
    skill_text = load_skill(SKILL_DIR)
    logger.info(f"Skill loaded from {SKILL_DIR}: {len(skill_text)} chars")

    while True:
        try:
            tasks = fetch_pending_tasks()
            for task in tasks:
                process_task(task)
        except Exception as e:
            logger.error(f"Poll loop error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
