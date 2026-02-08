#!/usr/bin/env python3
"""
Newsletter task poller.

Bridges Supabase agent_tasks to file-based queue for the Newsletter agent.
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
AGENT_NAME = os.getenv("AGENT_NAME", "newsletter")
OPENCLAW_DATA_DIR = os.getenv("OPENCLAW_DATA_DIR", "/home/openclaw/.openclaw")
POLL_INTERVAL = int(os.getenv("NEWSLETTER_POLL_INTERVAL", "30"))

WORKSPACE = Path(OPENCLAW_DATA_DIR) / "workspace"
QUEUE_DIR = WORKSPACE / "agentpulse" / "queue"
RESPONSES_DIR = QUEUE_DIR / "responses"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("newsletter-poller")

supabase: Client | None = None


def init_supabase():
    global supabase
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Supabase not configured (SUPABASE_URL / SUPABASE_KEY missing)")
        return False
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return True


def ensure_dirs():
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)


def fetch_pending_tasks(limit: int = 5):
    return supabase.table("agent_tasks") \
        .select("*") \
        .eq("status", "pending") \
        .eq("assigned_to", AGENT_NAME) \
        .order("priority", desc=False) \
        .order("created_at", desc=False) \
        .limit(limit) \
        .execute()


def mark_task_status(task_id: str, status: str, **fields):
    payload = {"status": status, **fields}
    supabase.table("agent_tasks").update(payload).eq("id", task_id).execute()


def write_task_file(task: dict):
    task_id = task["id"]
    task_type = task.get("task_type", "unknown")
    input_data = task.get("input_data", {}) or {}

    filename = f"newsletter_{task_id}.json"
    path = QUEUE_DIR / filename

    payload = {
        "task": task_type,
        "params": input_data,
        "task_id": task_id,
        "assigned_to": task.get("assigned_to"),
        "created_by": task.get("created_by"),
        "created_at": task.get("created_at"),
    }

    path.write_text(json.dumps(payload, indent=2, default=str))
    logger.info(f"Wrote task file: {path.name}")


def process_responses():
    for response_file in RESPONSES_DIR.glob("newsletter_*.result.json"):
        try:
            task_id = response_file.stem.replace(".result", "").replace("newsletter_", "")
            response = json.loads(response_file.read_text())
            success = response.get("success", True)

            if success:
                output_data = response.get("result", response)
                mark_task_status(
                    task_id,
                    "completed",
                    completed_at=datetime.utcnow().isoformat(),
                    output_data=output_data,
                )
                logger.info(f"Marked task {task_id} completed")
            else:
                error_message = response.get("error") or response.get("result") or "Unknown error"
                mark_task_status(
                    task_id,
                    "failed",
                    completed_at=datetime.utcnow().isoformat(),
                    error_message=str(error_message),
                )
                logger.error(f"Marked task {task_id} failed: {error_message}")

            # Remove response file after processing
            response_file.unlink(missing_ok=True)

            # Attempt to remove task file if it still exists
            task_file = QUEUE_DIR / f"newsletter_{task_id}.json"
            if task_file.exists():
                task_file.unlink()

        except Exception as e:
            logger.error(f"Failed processing response {response_file.name}: {e}")


def main():
    ensure_dirs()
    if not init_supabase():
        return

    logger.info("Newsletter poller started")
    while True:
        try:
            # Fetch and enqueue tasks
            tasks = fetch_pending_tasks().data or []
            for task in tasks:
                task_id = task["id"]
                logger.info(f"Processing task {task_id}: {task.get('task_type')}")
                mark_task_status(task_id, "in_progress", started_at=datetime.utcnow().isoformat())
                write_task_file(task)

            # Process responses from queue
            process_responses()

        except Exception as e:
            logger.error(f"Poller loop error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
