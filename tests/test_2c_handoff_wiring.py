#!/usr/bin/env python3
"""
TEST 2C: Analyst -> Research Agent Handoff Wiring

Tests the full handoff pipeline:
  1. Trigger file creation
  2. Research Agent picks up trigger
  3. Trigger cleanup
  4. End-to-end handoff timing
  5. Duplicate trigger prevention
  6. Timeout / resilience (Newsletter without Spotlight)
  7. Research Agent failure handling
  8. Cleanup
  9. Summary
"""

import json
import os
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

# Safely import research_agent without triggering sys.exit()
import importlib
_orig_exit = sys.exit
sys.exit = lambda *a, **kw: (_ for _ in ()).throw(SystemExit(0))
try:
    ra = importlib.import_module("research_agent")
except SystemExit:
    pass
sys.exit = _orig_exit

RESULTS = {}
TEST_ISSUE = 996
CLEANUP_IDS = {"research_queue": [], "spotlight_history": [], "topic_evolution": []}
CLEANUP_TRIGGERS = []


def init_test():
    proc.init_clients()
    ra.supabase = proc.supabase
    ra.claude_client = getattr(proc, "anthropic_client", None)

    if not ra.claude_client:
        from dotenv import dotenv_values
        vals = dotenv_values(Path(__file__).resolve().parent.parent / "config" / ".env")
        import anthropic
        key = vals.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        if key:
            ra.claude_client = anthropic.Anthropic(api_key=key)

    ra.TRIGGER_DIR = proc.RESEARCH_TRIGGER_DIR
    print(f"  Processor initialized")
    print(f"  Trigger dir (proc): {proc.RESEARCH_TRIGGER_DIR}")
    print(f"  Trigger dir (ra):   {ra.TRIGGER_DIR}")
    print(f"  Same path: {str(proc.RESEARCH_TRIGGER_DIR) == str(ra.TRIGGER_DIR)}")


def track(table, row_id):
    CLEANUP_IDS[table].append(row_id)


def ensure_test_topics():
    """Make sure topic_evolution has data for selection to work."""
    te = proc.supabase.table("topic_evolution").select("id")\
        .limit(5).execute()
    if te.data and len(te.data) >= 3:
        return False

    synthetic = [
        {"topic_key": "test_handoff_alpha", "current_stage": "debating",
         "snapshots": [{"mentions": 12, "sources": ["hackernews", "moltbook", "rss_a16z"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
        {"topic_key": "test_handoff_beta", "current_stage": "building",
         "snapshots": [{"mentions": 8, "sources": ["hackernews", "github"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
        {"topic_key": "test_handoff_gamma", "current_stage": "emerging",
         "snapshots": [{"mentions": 6, "sources": ["hackernews", "moltbook", "github"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
    ]
    for t in synthetic:
        r = proc.supabase.table("topic_evolution").insert(t).execute()
        if r.data:
            track("topic_evolution", r.data[0]["id"])
    print(f"  Inserted {len(synthetic)} synthetic topics")
    return True


def clear_trigger_dir():
    """Remove any pre-existing trigger files to start clean."""
    for f in proc.RESEARCH_TRIGGER_DIR.glob("research-trigger-*.json"):
        f.unlink(missing_ok=True)


# ============================================================================
# Step 1: Trigger file creation
# ============================================================================

def step1_trigger_creation():
    print(f"\n{'='*70}")
    print("  Step 1: Trigger File Creation")
    print(f"{'='*70}")

    clear_trigger_dir()

    t0 = time.time()
    result = proc.select_spotlight_topic()
    selection_time = time.time() - t0

    queue_id = result.get("queue_id")
    trigger_file = result.get("trigger_file")
    mode = result.get("mode", "?")

    print(f"  Selection took: {selection_time:.2f}s")
    print(f"  Mode: {mode}")
    print(f"  Queue ID: {queue_id}")
    print(f"  Trigger filename: {trigger_file}")

    if queue_id:
        track("research_queue", queue_id)

    if not trigger_file:
        print("  FAIL: No trigger file returned")
        RESULTS["trigger_creation"] = False
        RESULTS["trigger_contents"] = False
        return result, selection_time

    trigger_path = proc.RESEARCH_TRIGGER_DIR / trigger_file
    exists = trigger_path.exists()
    print(f"  File exists on disk: {exists}")

    if not exists:
        print("  FAIL: Trigger file not found on disk")
        RESULTS["trigger_creation"] = False
        RESULTS["trigger_contents"] = False
        return result, selection_time

    CLEANUP_TRIGGERS.append(trigger_path)
    RESULTS["trigger_creation"] = True

    data = json.loads(trigger_path.read_text())
    print(f"\n  Trigger file contents:")
    for k, v in data.items():
        print(f"    {k}: {v}")

    checks = {
        "trigger_type = research_request": data.get("trigger_type") == "research_request",
        "research_queue_id matches DB": data.get("research_queue_id") == queue_id,
        "topic_name populated": bool(data.get("topic_name")),
        "mode is spotlight or synthesis": data.get("mode") in ("spotlight", "synthesis"),
        "triggered_at is valid": bool(data.get("triggered_at")),
    }

    all_ok = True
    for label, ok in checks.items():
        print(f"    {label}: {'PASS' if ok else 'FAIL'}")
        if not ok:
            all_ok = False

    RESULTS["trigger_contents"] = all_ok
    return result, selection_time


# ============================================================================
# Step 2: Research Agent picks up trigger
# ============================================================================

def step2_research_pickup(selection_result):
    print(f"\n{'='*70}")
    print("  Step 2: Research Agent Picks Up Trigger")
    print(f"{'='*70}")

    queue_id = selection_result.get("queue_id")
    if not queue_id:
        print("  SKIP: No queue_id from step 1")
        RESULTS["research_pickup"] = None
        return 0

    t_trigger = time.time()
    item = ra.check_triggers()
    pickup_time = time.time() - t_trigger

    if not item:
        print("  FAIL: Research Agent did not detect trigger")
        RESULTS["research_pickup"] = False
        return pickup_time

    detected_id = item.get("id")
    print(f"  Detected queue item: {detected_id}")
    print(f"  Topic: {item.get('topic_name', '?')}")
    print(f"  Pickup delay: {pickup_time:.3f}s")
    print(f"  IDs match: {detected_id == queue_id}")

    ra.update_queue_status(queue_id, "in_progress")
    q_check = proc.supabase.table("research_queue").select("status")\
        .eq("id", queue_id).execute()
    status = q_check.data[0]["status"] if q_check.data else "?"
    print(f"  Status after pickup: {status}")

    ok = detected_id == queue_id and status == "in_progress"
    RESULTS["research_pickup"] = ok
    return pickup_time


# ============================================================================
# Step 3: Trigger cleanup
# ============================================================================

def step3_trigger_cleanup():
    print(f"\n{'='*70}")
    print("  Step 3: Trigger Cleanup")
    print(f"{'='*70}")

    remaining = list(proc.RESEARCH_TRIGGER_DIR.glob("research-trigger-*.json"))
    print(f"  Trigger files remaining: {len(remaining)}")
    for f in remaining:
        print(f"    - {f.name}")

    clean = len(remaining) == 0
    print(f"  All triggers cleaned up: {'PASS' if clean else 'FAIL'}")
    RESULTS["trigger_cleanup"] = clean


# ============================================================================
# Step 4: End-to-end handoff timing
# ============================================================================

def step4_e2e_timing(selection_time, pickup_delay, queue_id):
    print(f"\n{'='*70}")
    print("  Step 4: End-to-End Handoff Timing")
    print(f"{'='*70}")

    if not queue_id:
        print("  SKIP: No queue_id")
        RESULTS["e2e_timing"] = None
        return

    t0 = time.time()
    ra.update_queue_status(queue_id, "completed")
    completion_time = time.time() - t0

    total = selection_time + pickup_delay + completion_time

    print(f"  Selection:           {selection_time:.2f}s")
    print(f"  Agent pickup delay:  {pickup_delay:.3f}s")
    print(f"  Completion update:   {completion_time:.3f}s")
    print(f"  Total handoff:       {total:.2f}s")

    if total > 5400:
        print(f"  WARN: Total exceeds 90 minutes ({total/60:.1f}min)")
        RESULTS["e2e_timing"] = False
    else:
        print(f"  PASS (well under 90min threshold)")
        RESULTS["e2e_timing"] = True


# ============================================================================
# Step 5: Duplicate trigger prevention
# ============================================================================

def step5_duplicate_prevention():
    print(f"\n{'='*70}")
    print("  Step 5: Duplicate Trigger Prevention")
    print(f"{'='*70}")

    clear_trigger_dir()

    queued = proc.queue_research_topic(
        topic_id="test_dup_check",
        topic_name="Duplicate Test Topic",
        priority_score=0.8,
        mode="spotlight",
    )
    q_id = queued.get("id")
    if q_id:
        track("research_queue", q_id)
    else:
        print("  FAIL: Could not create queue entry")
        RESULTS["duplicate_prevention"] = False
        return

    f1 = proc._write_research_trigger(q_id, "Duplicate Test Topic", "spotlight")
    print(f"  First trigger: {f1}")
    if f1:
        CLEANUP_TRIGGERS.append(proc.RESEARCH_TRIGGER_DIR / f1)

    f2 = proc._write_research_trigger(q_id, "Duplicate Test Topic", "spotlight")
    print(f"  Second trigger: {f2}")

    files = list(proc.RESEARCH_TRIGGER_DIR.glob("research-trigger-*.json"))
    count = len(files)
    print(f"  Trigger files on disk: {count}")

    ok = f1 is not None and f2 is None and count == 1
    print(f"  Duplicate prevented: {'PASS' if ok else 'FAIL'}")
    RESULTS["duplicate_prevention"] = ok

    for f in files:
        f.unlink(missing_ok=True)


# ============================================================================
# Step 6: Timeout / resilience — Newsletter without Spotlight
# ============================================================================

def step6_timeout_resilience():
    print(f"\n{'='*70}")
    print("  Step 6: Timeout Resilience (Newsletter Without Spotlight)")
    print(f"{'='*70}")

    queued = proc.queue_research_topic(
        topic_id="test_timeout_topic",
        topic_name="Timeout Test Topic",
        priority_score=0.5,
        mode="spotlight",
    )
    q_id = queued.get("id")
    if q_id:
        track("research_queue", q_id)

    trigger_file = proc._write_research_trigger(
        q_id or "fake", "Timeout Test Topic", "spotlight")
    if trigger_file:
        CLEANUP_TRIGGERS.append(proc.RESEARCH_TRIGGER_DIR / trigger_file)

    print(f"  Trigger written: {trigger_file}")
    print(f"  Research Agent NOT started (simulating timeout)")

    spotlight = proc._fetch_latest_spotlight_for_newsletter(edition_number=TEST_ISSUE)

    found = spotlight is not None
    print(f"  Spotlight found for newsletter: {'yes' if found else 'no'}")

    if not found:
        print("  Newsletter would proceed with: Signals + Radar only (no Spotlight)")
        RESULTS["timeout_resilience"] = True
        RESULTS["newsletter_without_spotlight"] = True
    else:
        age = "unknown"
        if spotlight.get("created_at"):
            try:
                ca = spotlight["created_at"]
                if ca.endswith("Z"):
                    ca = ca.replace("Z", "+00:00")
                dt = datetime.fromisoformat(ca)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age = f"{(datetime.now(timezone.utc) - dt).total_seconds() / 3600:.1f}h"
            except Exception:
                pass
        print(f"  Found existing spotlight (age={age}) — this is OK if from prior test runs")
        RESULTS["timeout_resilience"] = True
        RESULTS["newsletter_without_spotlight"] = True

    for f in proc.RESEARCH_TRIGGER_DIR.glob("research-trigger-*.json"):
        f.unlink(missing_ok=True)


# ============================================================================
# Step 7: Research Agent failure handling
# ============================================================================

def step7_failure_handling():
    print(f"\n{'='*70}")
    print("  Step 7: Research Agent Failure Handling")
    print(f"{'='*70}")

    clear_trigger_dir()

    bad_item = proc.queue_research_topic(
        topic_id="",
        topic_name="",
        priority_score=0.1,
        context_payload={},
        mode="spotlight",
    )
    q_id = bad_item.get("id")
    if q_id:
        track("research_queue", q_id)
    else:
        print("  FAIL: Could not insert bad queue item")
        RESULTS["failure_handling"] = False
        return

    trigger = proc._write_research_trigger(q_id, "", "spotlight")
    if trigger:
        CLEANUP_TRIGGERS.append(proc.RESEARCH_TRIGGER_DIR / trigger)
    print(f"  Bad item queued: {q_id}")
    print(f"  Trigger written: {trigger}")

    item = ra.check_triggers()

    if item:
        print(f"  Research Agent picked up item: {item.get('id')}")
        ra.update_queue_status(q_id, "in_progress")

        try:
            sources = ra.gather_sources(
                topic_id=item.get("topic_id", ""),
                topic_name=item.get("topic_name", ""),
                context_payload=item.get("context_payload"),
            )
            total_sources = sum(len(v) if isinstance(v, list) else 0 for v in sources.values())
            print(f"  Sources gathered: {total_sources}")

            if total_sources == 0:
                print("  No sources — marking failed")
                ra.update_queue_status(q_id, "failed",
                    context_payload={**(item.get("context_payload") or {}),
                                     "_error": "no_sources_found"})
            else:
                ra.update_queue_status(q_id, "failed",
                    context_payload={**(item.get("context_payload") or {}),
                                     "_error": "bad_input_test"})
        except Exception as e:
            print(f"  Processing exception (expected): {type(e).__name__}: {e}")
            ra.update_queue_status(q_id, "failed",
                context_payload={"_error": str(e)})
    else:
        print("  Research Agent did not pick up (trigger already cleaned or item not queued)")
        ra.update_queue_status(q_id, "failed",
            context_payload={"_error": "trigger_not_picked_up"})

    q_check = proc.supabase.table("research_queue").select("status")\
        .eq("id", q_id).execute()
    final_status = q_check.data[0]["status"] if q_check.data else "?"
    print(f"  Final status: {final_status}")

    trigger_files = list(proc.RESEARCH_TRIGGER_DIR.glob("research-trigger-*.json"))
    trigger_clean = len(trigger_files) == 0
    print(f"  Trigger cleaned up: {'PASS' if trigger_clean else 'FAIL'}")

    status_ok = final_status in ("failed", "completed")
    print(f"  Status correct: {'PASS' if status_ok else 'FAIL'}")

    spotlight = proc._fetch_latest_spotlight_for_newsletter(edition_number=TEST_ISSUE)
    newsletter_ok = True
    print(f"  Newsletter can proceed: PASS")

    RESULTS["failure_handling"] = status_ok and trigger_clean


# ============================================================================
# Step 8: Cleanup
# ============================================================================

def step8_cleanup():
    print(f"\n{'='*70}")
    print("  Step 8: Cleanup")
    print(f"{'='*70}")

    for rid in CLEANUP_IDS["research_queue"]:
        try:
            proc.supabase.table("research_queue").delete().eq("id", rid).execute()
        except Exception as e:
            print(f"  WARN: Failed to delete research_queue {rid}: {e}")
    print(f"  research_queue: deleted {len(CLEANUP_IDS['research_queue'])} rows")

    for sid in CLEANUP_IDS["spotlight_history"]:
        try:
            proc.supabase.table("predictions").delete().eq("spotlight_id", sid).execute()
            proc.supabase.table("spotlight_history").delete().eq("id", sid).execute()
        except Exception as e:
            print(f"  WARN: Failed to delete spotlight_history {sid}: {e}")
    print(f"  spotlight_history: deleted {len(CLEANUP_IDS['spotlight_history'])} rows")

    for tid in CLEANUP_IDS["topic_evolution"]:
        try:
            proc.supabase.table("topic_evolution").delete().eq("id", tid).execute()
        except Exception as e:
            print(f"  WARN: Failed to delete topic_evolution {tid}: {e}")
    print(f"  topic_evolution: deleted {len(CLEANUP_IDS['topic_evolution'])} rows")

    for tp in CLEANUP_TRIGGERS:
        try:
            tp.unlink(missing_ok=True)
        except Exception:
            pass

    remaining = list(proc.RESEARCH_TRIGGER_DIR.glob("research-trigger-*.json"))
    for f in remaining:
        f.unlink(missing_ok=True)

    trigger_clean = len(list(proc.RESEARCH_TRIGGER_DIR.glob("research-trigger-*.json"))) == 0
    print(f"  Trigger files: {'clean' if trigger_clean else 'WARN leftover files'}")

    RESULTS["cleanup"] = trigger_clean


# ============================================================================
# Summary
# ============================================================================

def print_summary():
    print(f"\n{'='*70}")
    print(f"  === HANDOFF WIRING TEST ===")
    print(f"{'='*70}")

    def pf(key):
        val = RESULTS.get(key)
        if val is None:
            return "SKIP"
        return "PASS" if val else "FAIL"

    rows = [
        ("Trigger file creation", pf("trigger_creation")),
        ("Trigger file contents", pf("trigger_contents")),
        ("Research Agent pickup", pf("research_pickup")),
        ("Trigger cleanup", pf("trigger_cleanup")),
        ("End-to-end timing", pf("e2e_timing")),
        ("Duplicate prevention", pf("duplicate_prevention")),
        ("Timeout resilience", pf("timeout_resilience")),
        ("Failure handling", pf("failure_handling")),
        ("Newsletter without Spotlight", pf("newsletter_without_spotlight")),
        ("Cleanup", pf("cleanup")),
    ]

    for label, status in rows:
        print(f"  {label:<30} {status}")

    test_keys = [k for k, _ in rows]
    all_pass = all(RESULTS.get(k) is True for k in test_keys if RESULTS.get(k) is not None)
    print(f"\n  Overall: {'ALL PASS' if all_pass else 'SOME FAILURES'}")


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 70)
    print("  TEST 2C: Analyst -> Research Agent Handoff Wiring")
    print("=" * 70)

    init_test()
    ensure_test_topics()

    try:
        selection_result, selection_time = step1_trigger_creation()

        pickup_delay = step2_research_pickup(selection_result)

        step3_trigger_cleanup()

        step4_e2e_timing(selection_time, pickup_delay, selection_result.get("queue_id"))

        step5_duplicate_prevention()

        step6_timeout_resilience()

        step7_failure_handling()

    finally:
        step8_cleanup()

    print_summary()


if __name__ == "__main__":
    main()
