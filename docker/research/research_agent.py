#!/usr/bin/env python3
"""
AgentPulse Research Agent — Conviction-Driven Thesis Builder

Standalone processor that:
1. Polls research_queue for highest-priority queued item
2. Gathers multi-tier source material
3. Calls Anthropic Claude with the Research Agent system prompt
4. Parses structured thesis output
5. Stores result in spotlight_history
6. Updates queue status through its lifecycle

Runs as a Docker service alongside the other AgentPulse processors.
"""

import json
import logging
import os
import re
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from pydantic import ValidationError
from supabase import create_client, Client

from schemas import SpotlightOutput

load_dotenv()

# ============================================================================
# Configuration
# ============================================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENCLAW_DATA_DIR = os.getenv("OPENCLAW_DATA_DIR", "/home/openclaw/.openclaw")

MODEL = os.getenv("RESEARCH_MODEL", "claude-sonnet-4-20250514")
POLL_INTERVAL = int(os.getenv("RESEARCH_POLL_INTERVAL", "60"))
MAX_SOURCE_TOKENS = int(os.getenv("RESEARCH_MAX_SOURCE_TOKENS", "8000"))
MAX_GENERATION_TOKENS = int(os.getenv("RESEARCH_MAX_GENERATION_TOKENS", "2000"))
SOURCE_WINDOW_GENERAL = int(os.getenv("RESEARCH_SOURCE_WINDOW_GENERAL", "7"))
SOURCE_WINDOW_TL = int(os.getenv("RESEARCH_SOURCE_WINDOW_TL", "14"))
MAX_EXECUTION_TIME = int(os.getenv("RESEARCH_MAX_EXECUTION_TIME", "300"))
RETRY_ON_FAILURE = int(os.getenv("RESEARCH_RETRY_ON_FAILURE", "1"))

LOG_DIR = Path(OPENCLAW_DATA_DIR) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "research-agent.log"),
    ],
)
logger = logging.getLogger("research-agent")

supabase: Client | None = None
claude_client: anthropic.Anthropic | None = None

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent / "IDENTITY.md"
_system_prompt_cache: str | None = None
_system_prompt_mtime: float = 0

REQUIRED_OUTPUT_FIELDS = ["thesis", "evidence", "counter_argument", "prediction", "builder_implications"]

WORKSPACE = Path(OPENCLAW_DATA_DIR) / "workspace"
TRIGGER_DIR = WORKSPACE / "agentpulse" / "queue" / "research"
TRIGGER_DIR.mkdir(parents=True, exist_ok=True)

running = True


def handle_shutdown(signum, frame):
    global running
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    running = False


signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


# ============================================================================
# Initialization
# ============================================================================

def init():
    global supabase, claude_client

    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized")
    else:
        logger.error("SUPABASE_URL or SUPABASE_KEY missing — cannot start")
        sys.exit(1)

    if ANTHROPIC_API_KEY:
        claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        logger.info(f"Anthropic client initialized (model: {MODEL})")
    else:
        logger.error("ANTHROPIC_API_KEY missing — cannot start")
        sys.exit(1)


def load_system_prompt() -> str:
    global _system_prompt_cache, _system_prompt_mtime

    if not SYSTEM_PROMPT_PATH.exists():
        logger.warning(f"System prompt not found at {SYSTEM_PROMPT_PATH}, using embedded fallback")
        return "You are the AgentPulse Research Agent. Produce a sharp, opinionated thesis with structured JSON output."

    mtime = SYSTEM_PROMPT_PATH.stat().st_mtime
    if _system_prompt_cache and mtime == _system_prompt_mtime:
        return _system_prompt_cache

    _system_prompt_cache = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    _system_prompt_mtime = mtime
    logger.info("System prompt loaded/reloaded")
    return _system_prompt_cache


# ============================================================================
# Queue Management
# ============================================================================

def poll_queue() -> dict | None:
    """Atomically claim the highest-priority queued item via FOR UPDATE SKIP LOCKED."""
    result = supabase.rpc("claim_research_task", {"p_limit": 1}).execute()
    return result.data[0] if result.data else None


def update_queue_status(queue_id: str, status: str, **extra):
    update = {"status": status}
    if status == "in_progress":
        update["started_at"] = datetime.now(timezone.utc).isoformat()
    elif status in ("completed", "failed"):
        update["completed_at"] = datetime.now(timezone.utc).isoformat()
    update.update(extra)

    supabase.table("research_queue").update(update).eq("id", queue_id).execute()
    logger.info(f"Queue {queue_id}: status -> {status}")


# ============================================================================
# Source Gathering
# ============================================================================

def gather_sources(topic_id: str, topic_name: str, context_payload: dict | None = None) -> dict:
    """Pull source material from all tiers for the given topic."""
    search_terms = topic_name.lower().replace("_", " ").split()
    now = datetime.now(timezone.utc)

    general_cutoff = (now - timedelta(days=SOURCE_WINDOW_GENERAL)).isoformat()
    tl_cutoff = (now - timedelta(days=SOURCE_WINDOW_TL)).isoformat()

    general_posts = []
    tl_posts = []
    github_posts = []

    try:
        result = supabase.table("source_posts")\
            .select("title, body, source, source_url, score, tags")\
            .gte("scraped_at", general_cutoff)\
            .order("score", desc=True)\
            .limit(200)\
            .execute()

        for p in (result.data or []):
            text = f"{p.get('title', '')} {p.get('body', '')}".lower()
            if not any(term in text for term in search_terms):
                continue
            src = p.get("source", "")
            if src.startswith("thought_leader_"):
                continue
            elif src == "github":
                github_posts.append(p)
            else:
                general_posts.append(p)

        general_posts = general_posts[:20]
        github_posts = github_posts[:10]
    except Exception as e:
        logger.warning(f"General source gathering failed: {e}")

    try:
        result = supabase.table("source_posts")\
            .select("title, body, source, source_url, score, tags, metadata")\
            .like("source", "thought_leader_%")\
            .gte("scraped_at", tl_cutoff)\
            .order("scraped_at", desc=True)\
            .limit(100)\
            .execute()

        for p in (result.data or []):
            text = f"{p.get('title', '')} {p.get('body', '')}".lower()
            if any(term in text for term in search_terms):
                tl_posts.append(p)

        tl_posts = tl_posts[:15]
    except Exception as e:
        logger.warning(f"Thought leader source gathering failed: {e}")

    lifecycle_context = None
    try:
        te = supabase.table("topic_evolution")\
            .select("*")\
            .eq("topic_key", topic_id)\
            .limit(1)\
            .execute()
        if te.data:
            lifecycle_context = te.data[0]
    except Exception as e:
        logger.warning(f"Topic lifecycle lookup failed: {e}")

    total = len(general_posts) + len(tl_posts) + len(github_posts)
    logger.info(f"Sources gathered: {len(general_posts)} general, {len(tl_posts)} TL, {len(github_posts)} GitHub = {total} total")

    return {
        "general": general_posts,
        "thought_leaders": tl_posts,
        "github": github_posts,
        "lifecycle": lifecycle_context,
        "analyst_context": context_payload,
        "total_sources": total,
    }


def gather_synthesis_sources(queue_item: dict) -> dict:
    """For synthesis mode: gather sources for the top 3 emerging topics."""
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=SOURCE_WINDOW_GENERAL)).isoformat()

    te = supabase.table("topic_evolution")\
        .select("*")\
        .eq("current_stage", "emerging")\
        .order("last_updated", desc=True)\
        .limit(3)\
        .execute()

    topics = te.data or []
    if not topics:
        te = supabase.table("topic_evolution")\
            .select("*")\
            .order("last_updated", desc=True)\
            .limit(3)\
            .execute()
        topics = te.data or []

    all_posts = []
    topic_names = []
    for t in topics:
        key = t.get("topic_key", "")
        topic_names.append(key.replace("_", " ").title())
        terms = key.replace("_", " ").split()

        result = supabase.table("source_posts")\
            .select("title, body, source, source_url, score")\
            .gte("scraped_at", cutoff)\
            .order("score", desc=True)\
            .limit(50)\
            .execute()

        for p in (result.data or []):
            text = f"{p.get('title', '')} {p.get('body', '')}".lower()
            if any(term in text for term in terms):
                all_posts.append(p)

    logger.info(f"Synthesis sources: {len(all_posts)} posts across topics: {topic_names}")

    return {
        "general": all_posts[:30],
        "thought_leaders": [],
        "github": [],
        "lifecycle": None,
        "analyst_context": queue_item.get("context_payload"),
        "total_sources": len(all_posts[:30]),
        "synthesis_topics": topic_names,
    }


# ============================================================================
# Context Window Builder
# ============================================================================

def build_context_window(queue_item: dict, sources: dict) -> str:
    """Format sources into a context string for the LLM, respecting token budget."""
    topic_name = queue_item.get("topic_name", "Unknown")
    lifecycle_phase = queue_item.get("lifecycle_phase", "unknown")
    mode = queue_item.get("mode", "spotlight")

    sections = []
    sections.append(f"Topic: {topic_name}")
    sections.append(f"Lifecycle Phase: {lifecycle_phase}")
    sections.append(f"Mode: {mode}")
    sections.append(f"Source Diversity: {sources['total_sources']} items across {_count_distinct_sources(sources)} sources")

    if sources.get("synthesis_topics"):
        sections.append(f"Synthesis Topics: {', '.join(sources['synthesis_topics'])}")

    if sources.get("analyst_context"):
        ctx = sources["analyst_context"]
        if isinstance(ctx, dict):
            sections.append(f"\n=== ANALYST CONTEXT ===\n{json.dumps(ctx, indent=2, default=str)[:1000]}")
        else:
            sections.append(f"\n=== ANALYST CONTEXT ===\n{str(ctx)[:1000]}")

    if sources.get("lifecycle"):
        lc = sources["lifecycle"]
        snaps = lc.get("snapshots") or []
        sections.append(f"\n=== LIFECYCLE DATA ===")
        sections.append(f"Stage: {lc.get('current_stage', 'unknown')}")
        sections.append(f"Snapshots: {len(snaps)}")
        if snaps:
            latest = snaps[-1]
            sections.append(f"Latest: mentions={latest.get('mentions', 0)}")

    char_budget = MAX_SOURCE_TOKENS * 4

    tl_text = _format_source_section("THOUGHT LEADER SOURCES (Tier 1.5)", sources.get("thought_leaders", []))
    general_text = _format_source_section("GENERAL SOURCES (Tier 2-3)", sources.get("general", []))
    github_text = _format_source_section("GITHUB ACTIVITY (Tier 4)", sources.get("github", []))

    remaining = char_budget - len("\n".join(sections))
    for section_text in [tl_text, general_text, github_text]:
        if remaining <= 0:
            break
        truncated = section_text[:remaining]
        sections.append(truncated)
        remaining -= len(truncated)

    return "\n".join(sections)


def _format_source_section(header: str, posts: list) -> str:
    if not posts:
        return f"\n=== {header} ===\n(no items)"
    lines = [f"\n=== {header} ({len(posts)} items) ==="]
    for p in posts:
        lines.append(f"\n[{p.get('source', '?')}] {p.get('title', 'Untitled')}")
        url = p.get("source_url", "")
        if url:
            lines.append(f"URL: {url}")
        body = (p.get("body") or "")[:400]
        if body:
            lines.append(body)
    return "\n".join(lines)


def _count_distinct_sources(sources: dict) -> int:
    all_sources = set()
    for key in ["general", "thought_leaders", "github"]:
        for p in sources.get(key, []):
            all_sources.add(p.get("source", "unknown"))
    return len(all_sources)


# ============================================================================
# LLM Thesis Generation
# ============================================================================

def generate_thesis(context: str, mode: str = "spotlight") -> tuple[dict | None, dict]:
    """Call Claude with the Research Agent prompt. Returns (parsed_data, usage_stats)."""
    system_prompt = load_system_prompt()

    if mode == "synthesis":
        extra_instruction = "\n\nThis is a SYNTHESIS mode request. Connect the topics into a bigger picture thesis. Set mode='synthesis' in your output."
    else:
        extra_instruction = ""

    user_msg = f"""Analyze the following topic data and produce a structured Spotlight thesis.{extra_instruction}

{context}

Respond with valid JSON only, following the output format in your instructions."""

    usage_stats = {"input_tokens": 0, "output_tokens": 0, "model": MODEL, "retries": 0}

    for attempt in range(1 + RETRY_ON_FAILURE):
        try:
            response = claude_client.messages.create(
                model=MODEL,
                max_tokens=MAX_GENERATION_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )

            usage_stats["input_tokens"] = response.usage.input_tokens
            usage_stats["output_tokens"] = response.usage.output_tokens

            raw = response.content[0].text
            logger.info(f"LLM response: {len(raw)} chars, {response.usage.input_tokens}+{response.usage.output_tokens} tokens")

            parsed = parse_thesis_output(raw)
            if parsed:
                return parsed, usage_stats

            logger.warning(f"Output parsing failed on attempt {attempt + 1}")
            usage_stats["retries"] = attempt + 1

        except Exception as e:
            logger.error(f"LLM call failed (attempt {attempt + 1}): {e}")
            usage_stats["retries"] = attempt + 1
            if attempt < RETRY_ON_FAILURE:
                time.sleep(5)

    return None, usage_stats


def validate_llm_output(raw: dict, model_cls: type) -> object:
    """Validate LLM output. On failure, constructs partial model and logs."""
    try:
        return model_cls.model_validate(raw)
    except ValidationError as e:
        logger.warning(f"LLM output validation errors ({model_cls.__name__}): {e}")
        valid_fields = {k: raw[k] for k in model_cls.model_fields if k in raw}
        return model_cls.model_construct(**valid_fields)


def parse_thesis_output(raw_text: str) -> dict | None:
    """Extract JSON from the LLM response and validate via Pydantic."""
    json_match = re.search(r"\{[\s\S]*\}", raw_text)
    if not json_match:
        logger.warning("No JSON object found in response")
        return None

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON: {e}")
        return None

    validated = validate_llm_output(data, SpotlightOutput)
    result = validated.model_dump()

    # Flag partial output (missing required thesis fields)
    missing = [f for f in REQUIRED_OUTPUT_FIELDS if not result.get(f)]
    if missing:
        logger.warning(f"Missing required fields: {missing}")
        result["_partial"] = True
        result["_missing"] = missing

    return result


# ============================================================================
# Result Storage
# ============================================================================

def store_spotlight(queue_item: dict, thesis_data: dict, usage_stats: dict) -> dict | None:
    """Store the completed thesis in spotlight_history."""
    full_output_parts = []
    for field in ["thesis", "evidence", "counter_argument", "prediction", "builder_implications"]:
        val = thesis_data.get(field, "")
        if val:
            label = field.replace("_", " ").title()
            full_output_parts.append(f"## {label}\n\n{val}")

    full_output = "\n\n".join(full_output_parts)

    sources_used = []
    for url in thesis_data.get("key_sources", []):
        sources_used.append({"url": url})

    record = {
        "research_queue_id": queue_item["id"],
        "topic_id": thesis_data.get("topic_id", queue_item.get("topic_id", "")),
        "topic_name": thesis_data.get("topic_name", queue_item.get("topic_name", "")),
        "issue_number": queue_item.get("issue_number", 0) or 0,
        "mode": thesis_data.get("mode", queue_item.get("mode", "spotlight")),
        "thesis": thesis_data.get("thesis", ""),
        "evidence": thesis_data.get("evidence", ""),
        "counter_argument": thesis_data.get("counter_argument", ""),
        "prediction": thesis_data.get("prediction", ""),
        "builder_implications": thesis_data.get("builder_implications", ""),
        "full_output": full_output,
        "sources_used": sources_used,
    }

    try:
        result = supabase.table("spotlight_history").insert(record).execute()
        spotlight = result.data[0] if result.data else None

        if spotlight and thesis_data.get("prediction"):
            _create_prediction(spotlight, thesis_data, queue_item)

        logger.info(f"Spotlight stored: {spotlight['id'] if spotlight else 'unknown'}")
        return spotlight
    except Exception as e:
        logger.error(f"Failed to store spotlight: {e}")
        return None


PREDICTION_EXTRACTOR_PROMPT = """You are a prediction extractor. Given a Spotlight analysis prediction, extract the single most specific, falsifiable prediction. Output ONLY the prediction as a single sentence. It must include a timeframe and a specific, measurable outcome. If the original prediction is too vague, sharpen it while staying true to the original intent.

Rules:
- One sentence only
- Must contain a concrete timeframe (e.g. "within 90 days", "by Q3 2025", "by mid-2026")
- Must contain a measurable outcome (numbers, named entities, specific events)
- If the input contains multiple predictions, extract the PRIMARY one that ties the analysis together
- Do NOT add caveats or hedging — state it as a claim"""


def _create_prediction(spotlight: dict, thesis_data: dict, queue_item: dict):
    """Extract a sharpened falsifiable prediction via LLM and store it."""
    raw_prediction = thesis_data.get("prediction", "")
    if not raw_prediction or not raw_prediction.strip():
        logger.warning("No prediction field in Spotlight output — skipping extraction")
        return

    extracted = _extract_prediction(raw_prediction)

    needs_sharpening = False
    if not extracted:
        logger.warning("Prediction extraction returned nothing — storing raw prediction with flag")
        extracted = raw_prediction
        needs_sharpening = True

    evidence_notes = None
    if needs_sharpening:
        evidence_notes = "needs_sharpening: original prediction was too vague for automated extraction"

    try:
        supabase.table("predictions").insert({
            "spotlight_id": spotlight["id"],
            "topic_id": thesis_data.get("topic_id", queue_item.get("topic_id", "")),
            "prediction_text": extracted,
            "issue_number": queue_item.get("issue_number", 0) or 0,
            "status": "open",
            "evidence_notes": evidence_notes,
        }).execute()
        logger.info(f"Prediction stored (sharpened={not needs_sharpening}): {extracted[:80]}...")
    except Exception as e:
        logger.warning(f"Failed to store prediction: {e}")


def _extract_prediction(raw_prediction: str) -> str | None:
    """Use Claude to sharpen a raw prediction into a single falsifiable sentence."""
    try:
        response = claude_client.messages.create(
            model=MODEL,
            max_tokens=200,
            system=PREDICTION_EXTRACTOR_PROMPT,
            messages=[{"role": "user", "content": raw_prediction}],
        )

        extracted = response.content[0].text.strip()
        extracted = extracted.strip('"').strip("'")

        logger.info(f"Prediction extraction: {response.usage.input_tokens}+{response.usage.output_tokens} tokens")

        if len(extracted) < 10 or len(extracted) > 500:
            logger.warning(f"Extracted prediction length suspect ({len(extracted)} chars)")
            return None

        return extracted

    except Exception as e:
        logger.warning(f"Prediction extraction LLM call failed: {e}")
        return None


# ============================================================================
# Main Processing Loop
# ============================================================================

def check_triggers() -> dict | None:
    """Check for trigger files from the Analyst/Processor. Returns trigger data or None."""
    try:
        trigger_files = sorted(TRIGGER_DIR.glob("research-trigger-*.json"))
    except Exception:
        return None

    for trigger_path in trigger_files:
        try:
            trigger_data = json.loads(trigger_path.read_text())
            queue_id = trigger_data.get("research_queue_id")
            if not queue_id:
                logger.warning(f"Trigger file missing queue_id: {trigger_path.name}")
                trigger_path.unlink(missing_ok=True)
                continue

            result = supabase.table("research_queue")\
                .select("*")\
                .eq("id", queue_id)\
                .limit(1)\
                .execute()

            if not result.data:
                logger.warning(f"Queue item {queue_id} not found for trigger {trigger_path.name}")
                trigger_path.unlink(missing_ok=True)
                continue

            item = result.data[0]
            if item.get("status") != "queued":
                logger.info(f"Queue item {queue_id} already {item.get('status')}, removing trigger")
                trigger_path.unlink(missing_ok=True)
                continue

            logger.info(f"Trigger received, starting research: {trigger_data.get('topic_name', 'Unknown')}")
            trigger_path.unlink(missing_ok=True)
            logger.info(f"Trigger file cleaned up: {trigger_path.name}")
            return item

        except Exception as e:
            logger.error(f"Error processing trigger {trigger_path.name}: {e}")
            try:
                trigger_path.unlink(missing_ok=True)
            except Exception:
                pass

    return None


def process_one() -> bool:
    """Process the single highest-priority queued item. Returns True if work was done."""
    triggered = check_triggers()
    item = triggered or poll_queue()
    if not item:
        return False

    queue_id = item["id"]
    topic_name = item.get("topic_name", "Unknown")
    topic_id = item.get("topic_id", "")
    mode = item.get("mode", "spotlight")

    logger.info(f"Processing: '{topic_name}' (mode={mode}, priority={item.get('priority_score')})")
    # Items from poll_queue() are already in_progress (claimed atomically via RPC).
    # Items surfaced by check_triggers() are fetched by ID and need explicit marking.
    if triggered:
        update_queue_status(queue_id, "in_progress")

    start_time = time.time()

    try:
        if mode == "synthesis":
            sources = gather_synthesis_sources(item)
        else:
            sources = gather_sources(topic_id, topic_name, item.get("context_payload"))

        if sources["total_sources"] == 0:
            logger.warning(f"No sources found for '{topic_name}'")

        elapsed = time.time() - start_time
        if elapsed > MAX_EXECUTION_TIME:
            logger.warning(f"Timeout after source gathering ({elapsed:.0f}s)")
            update_queue_status(queue_id, "completed",
                                context_payload={**(item.get("context_payload") or {}), "_warning": "timeout_after_gathering"})
            return True

        context = build_context_window(item, sources)
        logger.info(f"Context window: {len(context)} chars")

        thesis_data, usage_stats = generate_thesis(context, mode)

        elapsed = time.time() - start_time
        logger.info(f"Token usage: {usage_stats['input_tokens']} in + {usage_stats['output_tokens']} out (elapsed: {elapsed:.1f}s)")

        if not thesis_data:
            logger.error(f"Thesis generation failed for '{topic_name}'")
            update_queue_status(queue_id, "failed",
                                context_payload={**(item.get("context_payload") or {}),
                                                 "_error": "thesis_generation_failed",
                                                 "_usage": usage_stats})
            return True

        if thesis_data.get("_partial"):
            logger.warning(f"Partial output stored (missing: {thesis_data.get('_missing')})")

        spotlight = store_spotlight(item, thesis_data, usage_stats)

        if spotlight:
            update_queue_status(queue_id, "completed")
            logger.info(f"Research complete, stored in spotlight_history: {spotlight.get('id', 'unknown')}")
            logger.info(f"Completed: '{topic_name}' in {time.time() - start_time:.1f}s")
        else:
            logger.error(f"Research failed: spotlight storage failed for '{topic_name}'")
            update_queue_status(queue_id, "failed",
                                context_payload={**(item.get("context_payload") or {}),
                                                 "_error": "spotlight_storage_failed"})

    except Exception as e:
        logger.error(f"Unhandled error processing '{topic_name}': {e}", exc_info=True)
        try:
            update_queue_status(queue_id, "failed",
                                context_payload={**(item.get("context_payload") or {}),
                                                 "_error": str(e)})
        except Exception:
            pass

    return True


def run_poll_loop():
    """Main polling loop."""
    logger.info(f"Research Agent starting (poll interval: {POLL_INTERVAL}s)")

    while running:
        try:
            did_work = process_one()
            if not did_work:
                logger.debug("No queued items, sleeping...")
        except Exception as e:
            logger.error(f"Poll loop error: {e}", exc_info=True)

        for _ in range(POLL_INTERVAL):
            if not running:
                break
            time.sleep(1)

    logger.info("Research Agent shut down")


def run_once():
    """Process one item and exit."""
    did_work = process_one()
    if not did_work:
        logger.info("No queued items to process")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AgentPulse Research Agent")
    parser.add_argument("--mode", choices=["watch", "once"], default="watch",
                        help="'watch' polls continuously, 'once' processes one item and exits")
    args = parser.parse_args()

    init()

    if args.mode == "once":
        run_once()
    else:
        run_poll_loop()
