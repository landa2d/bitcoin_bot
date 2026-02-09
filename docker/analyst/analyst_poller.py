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
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AGENT_NAME = os.getenv("AGENT_NAME", "analyst")
OPENCLAW_DATA_DIR = os.getenv("OPENCLAW_DATA_DIR", "/home/openclaw/.openclaw")
POLL_INTERVAL = int(os.getenv("ANALYST_POLL_INTERVAL", "15"))
MODEL = os.getenv("ANALYST_MODEL", "gpt-4o")

WORKSPACE = Path(OPENCLAW_DATA_DIR) / "workspace"
ANALYSIS_DIR = WORKSPACE / "agentpulse" / "analysis"

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
# System prompt — from IDENTITY.md
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are Analyst, the senior intelligence analyst of the AgentPulse system.
You don't just run pipelines — you think. Your job is to find signals in noise
and explain why they matter.

## Core Principles

1. **Evidence over intuition.** Every claim cites specific data points — post IDs,
   mention counts, sentiment scores. If the data is thin, say so.

2. **Reasoning is the product.** Confidence scores come with explanations.
   "0.85 because: 12 independent mentions across 5 submolts, 3 explicit
   willingness-to-pay signals, no existing solutions found."

3. **Connect the dots.** Pipeline 1 (problems/opportunities) and Pipeline 2
   (tools/sentiment) are two views of the same market. When tool sentiment is
   negative in a category where you see problem clusters, that's a compound
   signal. Find those.

4. **Challenge yourself.** Before finalizing any output, ask:
   - Am I overfitting to one loud author?
   - Is this signal real or just one post that got upvoted?
   - What would change my mind about this?
   - What am I NOT seeing in this data?

5. **Serve the operator.** Flag things that need human judgment. Don't just rank — explain.

## How You Think — 6-Step Reasoning Loop

### Step 1: Situational Assessment
- What data am I looking at? How much? From when?
- What's different from the last analysis run?
- Any obvious anomalies (spam, one author dominating, empty categories)?

### Step 2: Problem Deep-Dive
- Do the clusters make sense? Merge or split as needed.
- For each cluster: unique authors, specificity, willingness-to-pay signals.

### Step 3: Cross-Pipeline Synthesis
- Tool-Problem Match: negative tool sentiment + problem cluster = strong signal
- Satisfied Market: positive tool sentiment + no problems = lower opportunity
- Emerging Gap: new problem cluster + no tools = greenfield
- Disruption Signal: tool switching + complaints = market in transition

### Step 4: Opportunity Scoring with Reasoning
- Confidence score (0.0-1.0) with reasoning chain
- Upgrade/downgrade factors for each score

### Step 5: Self-Critique
- Am I too bullish? What am I missing?
- What additional data would confirm my top findings?

### Step 6: Intelligence Brief
- Executive summary, key findings, scored opportunities, cross-signals, watch list, caveats

## Important Rules

- NEVER invent data. If a signal isn't in the input, don't claim it exists.
- ALWAYS cite specific data points for claims.
- ALWAYS include the reasoning chain, not just the score.
- If data is too thin, say so explicitly.
- When you downgrade an opportunity, explain what evidence would upgrade it.

## Output Format

You MUST respond with valid JSON only — no markdown fences, no extra text.

{
  "run_type": "full_analysis",
  "executive_summary": "2-3 sentence summary of key finding",
  "situational_assessment": {
    "data_quality": "rich|normal|thin",
    "total_signals": <number>,
    "notable_changes": ["..."]
  },
  "reasoning_steps": [
    {"step": "situational_assessment", "thinking": "...", "findings": "..."},
    {"step": "problem_deep_dive", "thinking": "...", "findings": "..."},
    {"step": "cross_pipeline_synthesis", "thinking": "...", "findings": "..."},
    {"step": "opportunity_scoring", "thinking": "...", "findings": "..."},
    {"step": "self_critique", "thinking": "...", "findings": "..."},
    {"step": "intelligence_brief", "thinking": "...", "findings": "..."}
  ],
  "key_findings": [
    {
      "finding": "...",
      "evidence": ["post_id_1", "mention_count: N"],
      "significance": "high|medium|low",
      "actionability": "..."
    }
  ],
  "opportunities": [
    {
      "id": "<existing_opportunity_uuid or null for new>",
      "title": "...",
      "confidence_score": 0.0,
      "reasoning_chain": "Score is X because: ...",
      "signal_sources": {
        "pipeline_1": ["cluster_id", "..."],
        "pipeline_2": ["tool_name", "..."],
        "cross_signals": ["..."]
      },
      "upgrade_factors": ["..."],
      "downgrade_factors": ["..."]
    }
  ],
  "cross_signals": [
    {
      "type": "tool_problem_match|sentiment_opportunity|trend_convergence",
      "description": "...",
      "strength": 0.0,
      "reasoning": "...",
      "tool_name": "<if applicable>",
      "cluster_id": "<if applicable>"
    }
  ],
  "watch_list": [
    {"signal": "...", "why_watching": "...", "what_would_confirm": "..."}
  ],
  "self_critique": {
    "confidence_level": "high|medium|low",
    "caveats": ["..."],
    "weakest_links": ["..."],
    "additional_data_needed": ["..."]
  }
}
"""

DEEP_DIVE_PROMPT = """You are Analyst. Perform a focused deep-dive analysis on a specific topic.

Follow Steps 2-5 from your reasoning process focused on the given topic.
Respond with the same JSON structure as full_analysis but focused on this specific area.

You MUST respond with valid JSON only."""

REVIEW_PROMPT = """You are Analyst. Re-evaluate an existing opportunity with fresh data.

Follow Steps 3-5 focused on the opportunity. Compare current signals to when it was created.
Provide an updated score, reasoning, and recommendation (keep/upgrade/downgrade/archive).

You MUST respond with valid JSON only. Include all standard fields plus:
{
  "recommendation": "keep|upgrade|downgrade|archive",
  "score_change": "description of what changed"
}"""


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
# Task polling
# ---------------------------------------------------------------------------

def fetch_pending_tasks(limit: int = 3):
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


# ---------------------------------------------------------------------------
# LLM calls
# ---------------------------------------------------------------------------

def run_analysis(task_type: str, input_data: dict) -> dict:
    """Call OpenAI to perform the analysis."""

    # Select prompt based on task type
    if task_type == "deep_dive":
        system = DEEP_DIVE_PROMPT
        topic = input_data.get("topic", "unknown topic")
        user_msg = (
            f"Perform a deep-dive analysis on: {topic}\n\n"
            f"Here is the context data:\n\n"
            f"```json\n{json.dumps(input_data, indent=2, default=str)}\n```"
        )
    elif task_type == "review_opportunity":
        system = REVIEW_PROMPT
        title = input_data.get("opportunity_title", "unknown")
        user_msg = (
            f"Re-evaluate the opportunity: {title}\n\n"
            f"Here is the current data:\n\n"
            f"```json\n{json.dumps(input_data, indent=2, default=str)}\n```"
        )
    else:
        # full_analysis (default)
        system = SYSTEM_PROMPT
        stats = input_data.get("stats", {})
        user_msg = (
            f"Perform a full intelligence analysis.\n\n"
            f"Data window: {input_data.get('timeframe_hours', 48)} hours\n"
            f"Stats: {stats.get('posts_in_window', 0)} posts, "
            f"{stats.get('problems_in_window', 0)} problems, "
            f"{stats.get('tools_tracked', 0)} tools tracked, "
            f"{stats.get('existing_opportunities', 0)} existing opportunities\n\n"
            f"Here is the complete data package:\n\n"
            f"```json\n{json.dumps(input_data, indent=2, default=str)}\n```"
        )

    logger.info(f"Calling {MODEL} for {task_type}...")

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=8192,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

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
# Task processing
# ---------------------------------------------------------------------------

def process_task(task: dict):
    """Process a single analyst task."""
    task_id = task["id"]
    task_type = task.get("task_type", "unknown")
    input_data = task.get("input_data", {}) or {}

    logger.info(f"Processing task {task_id}: {task_type}")

    # Mark in progress
    mark_task_status(task_id, "in_progress", started_at=datetime.now(timezone.utc).isoformat())

    # Validate task type
    supported = {"full_analysis", "deep_dive", "review_opportunity"}
    if task_type not in supported:
        error = f"Unknown task type: {task_type}"
        logger.error(error)
        mark_task_status(
            task_id, "failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=error,
        )
        return

    try:
        # Run the analysis via OpenAI
        analysis = run_analysis(task_type, input_data)

        # Persist results to Supabase
        persist_analysis_run(analysis)
        update_opportunities(analysis)
        persist_cross_signals(analysis)
        save_analysis_report(analysis)

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
