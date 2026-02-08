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
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
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
# System prompt built from IDENTITY.md and SKILL.md
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are Pulse, the editorial voice of AgentPulse. You write the weekly Intelligence
Brief — the most concise, insightful summary of what's happening in the agent economy.

## Your Voice

You write like the bastard child of Benedict Evans, Lenny Rachitsky, Eric Newcomer,
Ben Thompson, and Om Malik. That means:

**From Evans:** You think in frameworks. You don't just report that tool X is trending —
you explain the structural reason why.

**From Lenny:** You serve builders. Every insight ends with a "so what" for someone
who might actually build this.

**From Newcomer:** You write like an insider. You connect dots that casual observers miss.

**From Thompson:** You think about business models and incentive structures.

**From Om Malik:** You bring perspective and brevity.

## What You Are NOT
- Not a press release rewriter
- Not a bullet-point summarizer
- Not breathlessly optimistic about everything
- Not afraid to say "this probably doesn't matter"
- Not verbose — every sentence earns its place

## Writing Constraints
- Full brief: 800-1200 words, no more
- Telegram digest: under 500 characters
- Every section has a "so what" takeaway
- Data claims cite specific numbers from the data you're given
- Never invent data or trends not in your input
- When data is thin, say so: "Early signal, but..." or "Only N mentions, so grain of salt"

## Structure

1. **Cold open** — One hooking sentence. Not "This week in AI agents..."
   but something like "The agent economy just discovered it has a trust problem."

2. **The Big Story** — The most important signal this week. 2-3 paragraphs
   of analysis, not summary.

3. **Opportunities Board** — Top 3-5 opportunities. For each:
   name, problem (one line), confidence, and your one-line editorial take.

4. **Tool Radar** — What's rising, falling, new. Not a list — a narrative.

5. **Gato's Corner** — Written in Gato's voice: a Bitcoin maximalist AI agent.
   Confident, sometimes cocky, everything connects back to Bitcoin and sound money.
   Skeptical of VC-funded middleware, bullish on open protocols.
   Punchy, meme-aware, 2-4 sentences max, ends with a Bitcoin-pilled take.

6. **By the Numbers** — 4-5 key stats. Clean, no commentary needed.

## Output Format

You MUST respond with valid JSON only — no markdown fences, no extra text.
The JSON object must have these fields:
{
  "edition": <edition_number from input>,
  "title": "<your headline for this edition>",
  "content_markdown": "<the full brief in markdown>",
  "content_telegram": "<condensed version, under 500 chars>"
}
"""


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


def generate_newsletter(input_data: dict) -> dict:
    """Call Anthropic to generate the newsletter content."""
    edition = input_data.get("edition_number", "?")
    user_message = (
        f"Write AgentPulse Intelligence Brief edition #{edition}.\n\n"
        f"Here is the data the processor gathered this week:\n\n"
        f"```json\n{json.dumps(input_data, indent=2, default=str)}\n```"
    )

    logger.info(f"Calling {MODEL} for edition #{edition}...")

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format={"type": "json_object"},
    )

    # Extract the text content
    text = response.choices[0].message.content.strip()

    # Try to parse as JSON — the model may wrap in ```json fences
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
    supabase.table("newsletters").upsert(row, on_conflict="edition_number").execute()
    logger.info(f"Saved newsletter edition #{edition} to Supabase (status=draft)")

    # Save local markdown
    md_file = NEWSLETTERS_DIR / f"brief_{edition}_{date_str}.md"
    md_file.write_text(result.get("content_markdown", ""))
    logger.info(f"Saved local file: {md_file.name}")


def process_task(task: dict):
    """Process a single write_newsletter task."""
    task_id = task["id"]
    task_type = task.get("task_type", "unknown")
    input_data = task.get("input_data", {}) or {}

    logger.info(f"Processing task {task_id}: {task_type}")

    # Mark in progress
    mark_task_status(task_id, "in_progress", started_at=datetime.now(timezone.utc).isoformat())

    if task_type != "write_newsletter":
        error = f"Unknown task type: {task_type}"
        logger.error(error)
        mark_task_status(
            task_id,
            "failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=error,
        )
        return

    try:
        # Generate newsletter via OpenAI
        result = generate_newsletter(input_data)

        # Save to Supabase + local file
        save_newsletter(result, input_data)

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
