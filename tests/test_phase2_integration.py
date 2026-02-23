#!/usr/bin/env python3
"""
INTEGRATION SMOKE TEST: Full Phase 2

Simulates a complete newsletter cycle from Analyst selection through
Research Agent output. Does NOT clean up data so Phase 3 can use it.

  1. Analyst cycle (selection heuristic)
  2. Handoff verification (queue + trigger)
  3. Research Agent processing
  4. Spotlight quality validation
  5. Pipeline state cleanliness
  6. Newsletter Agent readiness
  7. Summary
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / "config" / ".env"
load_dotenv(env_path)

PROC_DIR = Path(__file__).resolve().parent.parent / "docker" / "processor"
RESEARCH_DIR = Path(__file__).resolve().parent.parent / "docker" / "research"
sys.path.insert(0, str(PROC_DIR))
sys.path.insert(0, str(RESEARCH_DIR))

os.environ.setdefault("OPENCLAW_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data" / "openclaw"))

import agentpulse_processor as proc

_orig_exit = sys.exit
sys.exit = lambda *a, **kw: (_ for _ in ()).throw(SystemExit(0))
try:
    import importlib
    ra = importlib.import_module("research_agent")
except SystemExit:
    pass
sys.exit = _orig_exit

RESULTS = {}
SYNTH_TOPIC_IDS = []

# Quality check constants (reused from test_2d)
HEDGE_PHRASES = [
    "it remains to be seen", "time will tell", "it could go either way",
    "may or may not", "only time will tell", "the jury is still out",
]
AI_PHRASES = [
    "in the rapidly evolving landscape", "it's worth noting", "as we navigate",
    "at the end of the day", "a myriad of", "it's important to understand",
    "in conclusion", "there are several factors",
]
TENSION_WORDS = ["but", "however", "despite", "yet", "although", "while", "even though"]
TIMEFRAME_PATTERNS = [
    r"\bQ[1-4]\b", r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b",
    r"\b202[5-9]\b", r"\b2030\b", r"\bby\s+\w+\s+\d{4}", r"\bmonths?\b", r"\bquarters?\b",
]


def init():
    proc.init_clients()
    ra.supabase = proc.supabase

    from dotenv import dotenv_values
    vals = dotenv_values(env_path)
    import anthropic
    key = vals.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if key:
        ra.claude_client = anthropic.Anthropic(api_key=key)

    ra.TRIGGER_DIR = proc.RESEARCH_TRIGGER_DIR
    print(f"  Clients initialized")


def ensure_topics():
    """Make sure topic_evolution has data."""
    te = proc.supabase.table("topic_evolution").select("id").limit(3).execute()
    if te.data and len(te.data) >= 3:
        return False

    synthetic = [
        {"topic_key": "integ_agent_security", "current_stage": "debating",
         "snapshots": [{"mentions": 14, "sources": ["hackernews", "moltbook", "rss_a16z"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
        {"topic_key": "integ_mcp_governance", "current_stage": "building",
         "snapshots": [{"mentions": 9, "sources": ["hackernews", "github"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
        {"topic_key": "integ_local_models", "current_stage": "emerging",
         "snapshots": [{"mentions": 5, "sources": ["hackernews", "moltbook", "github"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
    ]
    for t in synthetic:
        r = proc.supabase.table("topic_evolution").insert(t).execute()
        if r.data:
            SYNTH_TOPIC_IDS.append(r.data[0]["id"])
    print(f"  Inserted {len(synthetic)} synthetic topics")
    return True


# ============================================================================
# Step 1: Analyst selection
# ============================================================================

def step1_analyst_selection():
    print(f"\n{'='*70}")
    print("  Step 1: Analyst Selection Cycle")
    print(f"{'='*70}")

    for f in proc.RESEARCH_TRIGGER_DIR.glob("research-trigger-*.json"):
        f.unlink(missing_ok=True)

    t0 = time.time()
    result = proc.select_spotlight_topic()
    elapsed = time.time() - t0

    selected = result.get("selected")
    mode = result.get("mode", "?")
    score = result.get("score") or result.get("best_score", 0)
    queue_id = result.get("queue_id")
    trigger_file = result.get("trigger_file")

    print(f"  Selected: {selected}")
    print(f"  Mode: {mode}")
    print(f"  Score: {score}")
    print(f"  Queue ID: {queue_id}")
    print(f"  Trigger: {trigger_file}")
    print(f"  Elapsed: {elapsed:.2f}s")

    ok = selected is not None and queue_id is not None
    RESULTS["analyst_selection"] = ok
    return result, elapsed


# ============================================================================
# Step 2: Verify handoff
# ============================================================================

def step2_verify_handoff(selection_result):
    print(f"\n{'='*70}")
    print("  Step 2: Handoff Verification")
    print(f"{'='*70}")

    queue_id = selection_result.get("queue_id")
    trigger_file = selection_result.get("trigger_file")

    if not queue_id:
        print("  FAIL: No queue_id")
        RESULTS["research_queue_entry"] = False
        RESULTS["trigger_handoff"] = False
        return

    q = proc.supabase.table("research_queue").select("*")\
        .eq("id", queue_id).execute()

    if not q.data:
        print(f"  FAIL: Queue entry {queue_id} not found")
        RESULTS["research_queue_entry"] = False
    else:
        row = q.data[0]
        checks = {
            "status = queued": row.get("status") == "queued",
            "topic_name present": bool(row.get("topic_name")),
            "mode present": row.get("mode") in ("spotlight", "synthesis"),
        }
        all_ok = all(checks.values())
        for label, ok in checks.items():
            print(f"    {label}: {'PASS' if ok else 'FAIL'}")
        RESULTS["research_queue_entry"] = all_ok

    if trigger_file:
        trigger_path = proc.RESEARCH_TRIGGER_DIR / trigger_file
        exists = trigger_path.exists()
        print(f"  Trigger file exists: {exists}")
        if exists:
            data = json.loads(trigger_path.read_text())
            print(f"    trigger_type: {data.get('trigger_type')}")
            print(f"    research_queue_id: {data.get('research_queue_id')}")
            print(f"    topic_name: {data.get('topic_name')}")
            print(f"    mode: {data.get('mode')}")
            RESULTS["trigger_handoff"] = data.get("research_queue_id") == queue_id
        else:
            RESULTS["trigger_handoff"] = False
    else:
        print("  WARN: No trigger file")
        RESULTS["trigger_handoff"] = False


# ============================================================================
# Step 3: Run Research Agent
# ============================================================================

def step3_research_agent(selection_result):
    print(f"\n{'='*70}")
    print("  Step 3: Research Agent Processing")
    print(f"{'='*70}")

    queue_id = selection_result.get("queue_id")
    if not queue_id:
        print("  SKIP: No queue_id")
        RESULTS["research_processing"] = False
        return None

    t0 = time.time()

    item = ra.check_triggers()
    if not item:
        item = ra.poll_queue()
    if not item:
        print("  FAIL: Could not pick up queue item")
        RESULTS["research_processing"] = False
        return None

    print(f"  Picked up: {item.get('topic_name', '?')} (mode={item.get('mode', '?')})")

    ra.update_queue_status(queue_id, "in_progress")

    topic_id = item.get("topic_id", "")
    topic_name = item.get("topic_name", "")
    mode = item.get("mode", "spotlight")
    context_payload = item.get("context_payload")

    if mode == "synthesis":
        sources = ra.gather_synthesis_sources(item)
    else:
        sources = ra.gather_sources(topic_id, topic_name, context_payload)

    total = sources.get("total_sources", 0)
    print(f"  Sources: {total}")

    context = ra.build_context_window(item, sources)
    thesis_data, usage = ra.generate_thesis(context, mode=mode)

    elapsed = time.time() - t0

    if not thesis_data:
        print(f"  FAIL: No thesis generated ({elapsed:.1f}s)")
        ra.update_queue_status(queue_id, "failed",
            context_payload={**(context_payload or {}), "_error": "no_thesis"})
        RESULTS["research_processing"] = False
        return None

    print(f"  Thesis generated in {elapsed:.1f}s")
    print(f"  Tokens: {usage.get('input_tokens', 0)} in + {usage.get('output_tokens', 0)} out")

    spotlight = ra.store_spotlight(item, thesis_data, usage)

    if spotlight:
        ra.update_queue_status(queue_id, "completed")
        print(f"  Spotlight stored: {spotlight.get('id', '?')}")
        RESULTS["research_processing"] = True
    else:
        ra.update_queue_status(queue_id, "failed",
            context_payload={**(context_payload or {}), "_error": "store_failed"})
        print(f"  FAIL: Spotlight storage failed")
        RESULTS["research_processing"] = False

    return spotlight


# ============================================================================
# Step 4: Spotlight quality
# ============================================================================

def step4_spotlight_quality(spotlight):
    print(f"\n{'='*70}")
    print("  Step 4: Spotlight Quality Validation")
    print(f"{'='*70}")

    if not spotlight:
        print("  SKIP: No spotlight")
        RESULTS["spotlight_quality"] = False
        return

    print(f"\n  THESIS:\n  {spotlight.get('thesis', 'MISSING')}")

    print(f"\n  EVIDENCE:")
    for line in (spotlight.get("evidence") or "MISSING").split("\n"):
        print(f"  {line}")

    print(f"\n  COUNTER-ARGUMENT:")
    for line in (spotlight.get("counter_argument") or "MISSING").split("\n"):
        print(f"  {line}")

    print(f"\n  PREDICTION:\n  {spotlight.get('prediction', 'MISSING')}")

    print(f"\n  BUILDER IMPLICATIONS:")
    for line in (spotlight.get("builder_implications") or "MISSING").split("\n"):
        print(f"  {line}")

    issues = []

    required = ["thesis", "evidence", "counter_argument", "prediction"]
    missing = [f for f in required if not spotlight.get(f)]
    if missing:
        issues.append(f"missing fields: {missing}")

    thesis = spotlight.get("thesis", "")
    has_tension = any(f" {w} " in f" {thesis.lower()} " for w in TENSION_WORDS)
    if not has_tension:
        issues.append("thesis lacks tension word")

    evidence = spotlight.get("evidence", "")
    if len(evidence.split()) < 80:
        issues.append(f"evidence too short ({len(evidence.split())} words)")

    prediction = spotlight.get("prediction", "")
    has_time = any(re.search(p, prediction, re.IGNORECASE) for p in TIMEFRAME_PATTERNS)
    if not has_time:
        issues.append("prediction missing timeframe")

    all_text = " ".join([spotlight.get(k, "") for k in required]).lower()
    hedges = [h for h in HEDGE_PHRASES if h in all_text]
    ai = [a for a in AI_PHRASES if a in all_text]
    if hedges:
        issues.append(f"hedging: {hedges}")
    if ai:
        issues.append(f"AI phrases: {ai}")

    ok = len(issues) <= 1
    print(f"\n  Quality: {'PASS' if ok else 'WARN'}", end="")
    if issues:
        print(f" ({'; '.join(issues)})")
    else:
        print()

    RESULTS["spotlight_quality"] = ok


# ============================================================================
# Step 5: Pipeline state
# ============================================================================

def step5_pipeline_state(selection_result, spotlight):
    print(f"\n{'='*70}")
    print("  Step 5: Pipeline State Cleanliness")
    print(f"{'='*70}")

    queue_id = selection_result.get("queue_id")
    checks = {}

    if queue_id:
        q = proc.supabase.table("research_queue").select("status, completed_at")\
            .eq("id", queue_id).execute()
        if q.data:
            checks["queue status = completed"] = q.data[0].get("status") == "completed"
            checks["completed_at populated"] = bool(q.data[0].get("completed_at"))
        else:
            checks["queue entry found"] = False

    triggers = list(proc.RESEARCH_TRIGGER_DIR.glob("research-trigger-*.json"))
    checks["trigger files cleaned"] = len(triggers) == 0
    print(f"  Trigger files remaining: {len(triggers)}")

    if spotlight:
        checks["spotlight has thesis"] = bool(spotlight.get("thesis"))
        checks["spotlight has evidence"] = bool(spotlight.get("evidence"))
        checks["spotlight has prediction"] = bool(spotlight.get("prediction"))
        checks["spotlight has full_output"] = bool(spotlight.get("full_output"))

    all_ok = True
    for label, ok in checks.items():
        print(f"    {label}: {'PASS' if ok else 'FAIL'}")
        if not ok:
            all_ok = False

    RESULTS["pipeline_state"] = all_ok


# ============================================================================
# Step 6: Newsletter readiness
# ============================================================================

def step6_newsletter_readiness(spotlight):
    print(f"\n{'='*70}")
    print("  Step 6: Newsletter Agent Readiness")
    print(f"{'='*70}")

    try:
        edition_result = proc.supabase.rpc("next_newsletter_edition").execute()
        edition_number = edition_result.data if edition_result.data else 1
    except Exception:
        existing = proc.supabase.table("newsletters").select("id", count="exact").execute()
        edition_number = (existing.count or 0) + 1

    print(f"  Next edition: #{edition_number}")

    nl_spotlight = proc._fetch_latest_spotlight_for_newsletter(edition_number)
    spotlight_ready = nl_spotlight is not None
    spotlight_headline = ""
    if nl_spotlight:
        spotlight_headline = (nl_spotlight.get("thesis") or "")[:80]
        print(f"  Spotlight: \"{spotlight_headline}...\" -- READY")
    else:
        print(f"  Spotlight: not found -- MISSING")

    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    signals_result = proc.supabase.table("problem_clusters")\
        .select("id", count="exact")\
        .gte("created_at", week_ago).execute()
    signals_count = signals_result.count or 0
    print(f"  Signals: {signals_count} items -- {'READY' if signals_count > 0 else 'EMPTY'}")

    te = proc.supabase.table("topic_evolution").select("topic_key, current_stage")\
        .order("last_updated", desc=True).limit(20).execute()
    emerging = [t for t in (te.data or []) if t.get("current_stage") == "emerging"]
    print(f"  Radar: {len(emerging)} emerging topics -- {'READY' if emerging else 'EMPTY'}")

    ok = spotlight_ready
    RESULTS["newsletter_ready"] = ok

    return {
        "edition": edition_number,
        "spotlight_headline": spotlight_headline,
        "signals_count": signals_count,
        "radar_count": len(emerging),
    }


# ============================================================================
# Summary
# ============================================================================

def print_summary(selection_result, spotlight, elapsed_selection, newsletter_info):
    print(f"\n{'='*70}")
    print(f"  === PHASE 2 INTEGRATION TEST ===")
    print(f"{'='*70}")

    def pf(key):
        val = RESULTS.get(key)
        if val is None:
            return "SKIP"
        return "PASS" if val else "FAIL"

    selected = selection_result.get("selected", "?")
    mode = selection_result.get("mode", "?")

    rows = [
        ("Analyst selection", f"{pf('analyst_selection')} -- selected: {selected} ({mode})"),
        ("Research queue entry", pf("research_queue_entry")),
        ("Trigger handoff", pf("trigger_handoff")),
        ("Research Agent processing", pf("research_processing")),
        ("Spotlight quality", pf("spotlight_quality")),
        ("Pipeline state clean", pf("pipeline_state")),
        ("Newsletter Agent ready", pf("newsletter_ready")),
    ]

    for label, status in rows:
        print(f"  {label:<28} {status}")

    if newsletter_info:
        print(f"\n  Newsletter would contain:")
        if newsletter_info.get("spotlight_headline"):
            print(f"    Spotlight: \"{newsletter_info['spotlight_headline']}...\"")
        else:
            print(f"    Spotlight: (none)")
        print(f"    Signals: {newsletter_info.get('signals_count', 0)} items")
        print(f"    Radar: {newsletter_info.get('radar_count', 0)} topics")

    issue = spotlight.get("issue_number", "?") if spotlight else "?"
    spotlight_id = spotlight.get("id", "?") if spotlight else "?"
    print(f"\n  Spotlight ID: {spotlight_id}")
    print(f"  Issue number: {issue}")
    print(f"  NOTE: Test data NOT cleaned up -- Phase 3 can use issue #{issue}")

    test_keys = ["analyst_selection", "research_queue_entry", "trigger_handoff",
                 "research_processing", "spotlight_quality", "pipeline_state", "newsletter_ready"]
    all_pass = all(RESULTS.get(k) is True for k in test_keys if RESULTS.get(k) is not None)
    print(f"\n  READY FOR PHASE 3: {'YES' if all_pass else 'NO'}")


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 70)
    print("  INTEGRATION SMOKE TEST: Full Phase 2")
    print("=" * 70)

    init()
    ensure_topics()

    selection_result, elapsed_selection = step1_analyst_selection()

    step2_verify_handoff(selection_result)

    spotlight = step3_research_agent(selection_result)

    step4_spotlight_quality(spotlight)

    step5_pipeline_state(selection_result, spotlight)

    newsletter_info = step6_newsletter_readiness(spotlight)

    print_summary(selection_result, spotlight, elapsed_selection, newsletter_info)

    for tid in SYNTH_TOPIC_IDS:
        try:
            proc.supabase.table("topic_evolution").delete().eq("id", tid).execute()
        except Exception:
            pass


if __name__ == "__main__":
    main()
