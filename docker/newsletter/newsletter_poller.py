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
from supabase import create_client, Client
from openai import OpenAI

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


def fetch_pending_tasks(limit: int = 5):
    return (
        supabase.table("agent_tasks")
        .select("*")
        .eq("status", "pending")
        .eq("assigned_to", AGENT_NAME)
        .order("priority", desc=False)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )


def mark_task_status(task_id: str, status: str, **fields):
    payload = {"status": status, **fields}
    supabase.table("agent_tasks").update(payload).eq("id", task_id).execute()


def generate_newsletter(task_type: str, input_data: dict, budget_config: dict) -> dict:
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

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=4096,
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
    supabase.table("newsletters").insert(row).execute()
    logger.info(f"Saved newsletter edition #{edition} to Supabase (status=draft)")

    # Save local markdown
    md_file = NEWSLETTERS_DIR / f"brief_{edition}_{date_str}.md"
    md_file.write_text(result.get("content_markdown", ""))
    logger.info(f"Saved local file: {md_file.name}")


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

    # Mark in progress
    mark_task_status(task_id, "in_progress", started_at=datetime.now(timezone.utc).isoformat())

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

    # Inject budget constraints
    budget = get_budget_config(AGENT_NAME, task_type)
    input_data["budget"] = budget
    logger.info(f"Budget for {task_type}: {budget}")

    try:
        # Generate newsletter via OpenAI
        result = generate_newsletter(task_type, input_data, budget)

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
            tasks = fetch_pending_tasks().data or []
            for task in tasks:
                process_task(task)
        except Exception as e:
            logger.error(f"Poll loop error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
