#!/usr/bin/env python3
"""
TEST 2A: Research Agent Core — Full Integration Test

Tests the end-to-end Research Agent pipeline:
  1. Setup (insert test queue item with real topic data)
  2. Queue pickup
  3. Source gathering
  4. Thesis generation (LLM call)
  5. Storage (spotlight_history)
  6. Completion lifecycle
  7. Synthesis mode
  8. Error handling
  9. Cleanup
  10. Summary
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

# Import the Research Agent module directly
RESEARCH_DIR = Path(__file__).resolve().parent.parent / "docker" / "research"
sys.path.insert(0, str(RESEARCH_DIR))

os.environ.setdefault("OPENCLAW_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data" / "openclaw"))

import research_agent as ra

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

ra.SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "templates" / "research" / "IDENTITY.md"

TEST_ISSUE = 998
RESULTS = {}
spotlight_output = {}
synthesis_output = {}


def init_test():
    """Initialize clients without sys.exit on failure."""
    from supabase import create_client
    import anthropic

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("FATAL: SUPABASE_URL or SUPABASE_KEY not set")
        sys.exit(1)
    if not ANTHROPIC_API_KEY:
        print("FATAL: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    ra.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    ra.claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    print(f"Clients initialized (model: {ra.MODEL})")
    print(f"System prompt: {ra.SYSTEM_PROMPT_PATH}")


def pick_topic():
    """Pick a real topic from problem_clusters or topic_evolution."""
    te = ra.supabase.table("topic_evolution").select("*")\
        .order("last_updated", desc=True).limit(30).execute()

    if te.data:
        preferred = [t for t in te.data if t.get("current_stage") in ("debating", "building")]
        if preferred:
            preferred.sort(key=lambda t: (t.get("snapshots") or [{}])[-1].get("mentions", 0), reverse=True)
            return preferred[0].get("topic_key"), preferred[0], "topic_evolution"

        te.data.sort(key=lambda t: (t.get("snapshots") or [{}])[-1].get("mentions", 0), reverse=True)
        return te.data[0].get("topic_key"), te.data[0], "topic_evolution"

    clusters = ra.supabase.table("problem_clusters").select("*")\
        .order("opportunity_score", desc=True).limit(10).execute()

    if clusters.data:
        c = clusters.data[0]
        topic_key = c.get("theme", "unknown").lower().replace(" ", "_").replace("-", "_")
        return topic_key, c, "problem_clusters"

    return None, None, "none"


def build_context_payload(topic_key, topic_data, source_type):
    """Build a realistic context_payload from actual source_posts."""
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    search_terms = [w for w in topic_key.replace("_", " ").split() if len(w) >= 3]

    posts = ra.supabase.table("source_posts")\
        .select("title, body, source, source_url, score")\
        .gte("scraped_at", week_ago)\
        .order("score", desc=True).limit(200).execute()

    matches = []
    for p in (posts.data or []):
        text = f"{p.get('title', '')} {p.get('body', '')}".lower()
        if any(t in text for t in search_terms):
            matches.append({
                "source": p.get("source", "unknown"),
                "title": p.get("title", ""),
                "summary": (p.get("body") or "")[:200],
                "url": p.get("source_url", ""),
            })

    if not matches:
        matches = [{"source": p.get("source", "?"), "title": p.get("title", "?"),
                     "summary": (p.get("body") or "")[:200], "url": p.get("source_url", "")}
                    for p in (posts.data or [])[:10]]

    topic_name = topic_key.replace("_", " ").title()
    return {
        "topic_id": topic_key,
        "topic_name": topic_name,
        "priority_score": 0.75,
        "velocity": len(matches),
        "source_diversity": len(set(m.get("source") for m in matches)),
        "lifecycle_phase": "debating",
        "recent_mentions": matches[:5],
        "contrarian_signals": [],
        "related_topics": [],
    }


# ============================================================================
# Test Steps
# ============================================================================

def step1_setup():
    """Step 1: Insert a test item into research_queue."""
    print("\n--- Step 1: Setup ---")

    topic_key, topic_data, source = pick_topic()
    if not topic_key:
        print("  FATAL: No topics available")
        return None, None

    print(f"  Source: {source}")
    print(f"  Topic: {topic_key}")

    ctx = build_context_payload(topic_key, topic_data, source)
    print(f"  Context: {len(ctx.get('recent_mentions', []))} mentions, "
          f"{ctx.get('source_diversity', 0)} distinct sources")

    record = {
        "topic_id": topic_key,
        "topic_name": ctx["topic_name"],
        "priority_score": ctx["priority_score"],
        "velocity": ctx["velocity"],
        "source_diversity": ctx["source_diversity"],
        "lifecycle_phase": ctx["lifecycle_phase"],
        "context_payload": ctx,
        "mode": "spotlight",
        "status": "queued",
        "issue_number": TEST_ISSUE,
    }

    result = ra.supabase.table("research_queue").insert(record).execute()
    queue_item = result.data[0] if result.data else None

    if queue_item:
        print(f"  Queue item inserted: {queue_item['id']}")
    else:
        print("  FATAL: Failed to insert queue item")
        return None, None

    return queue_item, ctx


def step2_queue_pickup(queue_item):
    """Step 2: Test queue polling picks up the item."""
    print("\n--- Step 2: Queue Pickup ---")

    polled = ra.poll_queue()
    if not polled:
        print("  FAIL: poll_queue returned None")
        return False

    if polled["id"] != queue_item["id"]:
        print(f"  WARN: Polled different item ({polled['id']}), expected {queue_item['id']}")
        print(f"  Polled topic: {polled.get('topic_name')}, priority: {polled.get('priority_score')}")

    print(f"  Polled item: {polled['id']}")

    ra.update_queue_status(polled["id"], "in_progress")

    check = ra.supabase.table("research_queue").select("status, started_at")\
        .eq("id", queue_item["id"]).execute()

    if not check.data:
        print("  FAIL: Could not verify status update")
        return False

    row = check.data[0]
    status_ok = row.get("status") == "in_progress"
    started_ok = row.get("started_at") is not None

    print(f"  Status: {row.get('status')} {'PASS' if status_ok else 'FAIL'}")
    print(f"  started_at: {row.get('started_at')} {'PASS' if started_ok else 'FAIL'}")

    RESULTS["queue_pickup"] = status_ok and started_ok
    return status_ok and started_ok


def step3_source_gathering(queue_item):
    """Step 3: Test source gathering."""
    print("\n--- Step 3: Source Gathering ---")

    topic_id = queue_item.get("topic_id", "")
    topic_name = queue_item.get("topic_name", "Unknown")
    ctx = queue_item.get("context_payload")

    sources = ra.gather_sources(topic_id, topic_name, ctx)

    gen_count = len(sources.get("general", []))
    tl_count = len(sources.get("thought_leaders", []))
    gh_count = len(sources.get("github", []))
    total = sources.get("total_sources", 0)

    print(f"  General sources:        {gen_count}")
    print(f"  Thought leader sources: {tl_count}")
    print(f"  GitHub sources:         {gh_count}")
    print(f"  Total:                  {total}")

    gen_pass = gen_count >= 1
    if not gen_pass:
        print("  FAIL: No general sources found")
    if tl_count == 0:
        print("  WARN: No thought leader sources (may be topic-dependent)")

    print("\n  Top 3 sources:")
    for p in sources.get("general", [])[:3]:
        print(f"    [{p.get('source', '?')}] {p.get('title', '?')[:60]}")

    RESULTS["source_gathering"] = gen_pass
    RESULTS["source_counts"] = {"general": gen_count, "thought_leader": tl_count, "github": gh_count}
    return sources


def step4_thesis_generation(queue_item, sources):
    """Step 4: Test thesis generation via LLM."""
    global spotlight_output
    print("\n--- Step 4: Thesis Generation ---")

    context = ra.build_context_window(queue_item, sources)
    print(f"  Context window: {len(context)} chars")

    start = time.time()
    thesis_data, usage = ra.generate_thesis(context, queue_item.get("mode", "spotlight"))
    elapsed = time.time() - start

    print(f"  Duration: {elapsed:.1f}s")
    print(f"  Tokens: {usage.get('input_tokens', 0)} in + {usage.get('output_tokens', 0)} out")

    if not thesis_data:
        print("  FAIL: thesis generation returned None")
        RESULTS["thesis_generation"] = False
        RESULTS["thesis_time"] = elapsed
        return None

    print(f"\n  Parsed output fields:")
    issues = []

    thesis = thesis_data.get("thesis", "")
    sentences = len([s for s in re.split(r'[.!?]+', thesis) if s.strip()])
    if sentences > 2:
        issues.append(f"thesis has {sentences} sentences (max 2)")
    print(f"    thesis: {len(thesis)} chars, {sentences} sentence(s) {'PASS' if sentences <= 2 else 'FAIL'}")

    evidence = thesis_data.get("evidence", "")
    ev_words = len(evidence.split())
    if ev_words < 100:
        issues.append(f"evidence only {ev_words} words (need 100+)")
    print(f"    evidence: {ev_words} words {'PASS' if ev_words >= 100 else 'FAIL'}")

    counter = thesis_data.get("counter_argument", "")
    ca_words = len(counter.split())
    if ca_words < 50:
        issues.append(f"counter_argument only {ca_words} words (need 50+)")
    print(f"    counter_argument: {ca_words} words {'PASS' if ca_words >= 50 else 'FAIL'}")

    prediction = thesis_data.get("prediction", "")
    timeframe_pats = [r"\bmonths?\b", r"\bquarters?\b", r"\bQ[1-4]\b", r"\bweeks?\b",
                      r"\b202[5-9]\b", r"\byears?\b", r"\bby\s+(end|mid|early)\b"]
    has_time = any(re.search(p, prediction, re.IGNORECASE) for p in timeframe_pats)
    if not has_time:
        issues.append("prediction has no timeframe")
    print(f"    prediction: {'has' if has_time else 'NO'} timeframe {'PASS' if has_time else 'FAIL'}")

    builder = thesis_data.get("builder_implications", "")
    bi_words = len(builder.split())
    if bi_words < 30:
        issues.append(f"builder_implications only {bi_words} words (need 30+)")
    print(f"    builder_implications: {bi_words} words {'PASS' if bi_words >= 30 else 'FAIL'}")

    key_sources = thesis_data.get("key_sources", [])
    if len(key_sources) < 2:
        issues.append(f"key_sources has {len(key_sources)} entries (need 2+)")
    print(f"    key_sources: {len(key_sources)} entries {'PASS' if len(key_sources) >= 2 else 'FAIL'}")

    spotlight_output.update(thesis_data)

    passed = len(issues) == 0
    if issues:
        print(f"\n  Structure issues: {'; '.join(issues)}")

    RESULTS["thesis_generation"] = True
    RESULTS["output_structure"] = passed
    RESULTS["output_issues"] = issues
    RESULTS["thesis_time"] = elapsed
    return thesis_data


def step5_storage(queue_item, thesis_data, sources):
    """Step 5: Test storage in spotlight_history."""
    print("\n--- Step 5: Storage ---")

    usage_stats = {"input_tokens": 0, "output_tokens": 0, "model": ra.MODEL}
    spotlight = ra.store_spotlight(queue_item, thesis_data, usage_stats)

    if not spotlight:
        print("  FAIL: store_spotlight returned None")
        RESULTS["storage"] = False
        return None

    sid = spotlight.get("id", "?")
    print(f"  spotlight_history row id: {sid}")

    row = ra.supabase.table("spotlight_history").select("*").eq("id", sid).execute()
    if not row.data:
        print("  FAIL: Could not read back spotlight_history row")
        RESULTS["storage"] = False
        return None

    s = row.data[0]
    checks = {
        "research_queue_id links": s.get("research_queue_id") == queue_item["id"],
        "thesis populated": bool(s.get("thesis")),
        "evidence populated": bool(s.get("evidence")),
        "counter_argument populated": bool(s.get("counter_argument")),
        "prediction populated": bool(s.get("prediction")),
        "full_output populated": bool(s.get("full_output")),
        "sources_used is list": isinstance(s.get("sources_used"), list) and len(s.get("sources_used", [])) >= 1,
    }

    all_pass = True
    for label, ok in checks.items():
        status = "PASS" if ok else "FAIL"
        print(f"    {label}: {status}")
        if not ok:
            all_pass = False

    RESULTS["storage"] = all_pass
    return spotlight


def step6_completion(queue_item):
    """Step 6: Test completion lifecycle."""
    print("\n--- Step 6: Completion Lifecycle ---")

    ra.update_queue_status(queue_item["id"], "completed")

    row = ra.supabase.table("research_queue").select("status, started_at, completed_at")\
        .eq("id", queue_item["id"]).execute()

    if not row.data:
        print("  FAIL: Could not read queue item")
        RESULTS["completion"] = False
        return

    r = row.data[0]
    status_ok = r.get("status") == "completed"
    completed_at = r.get("completed_at")
    started_at = r.get("started_at")

    completed_ok = completed_at is not None
    order_ok = True

    if started_at and completed_at:
        try:
            sa = started_at.replace("Z", "+00:00") if started_at.endswith("Z") else started_at
            ca = completed_at.replace("Z", "+00:00") if completed_at.endswith("Z") else completed_at
            s_dt = datetime.fromisoformat(sa)
            c_dt = datetime.fromisoformat(ca)
            delta = (c_dt - s_dt).total_seconds()
            order_ok = delta >= 0
            print(f"  Total processing time: {delta:.1f}s")
        except Exception:
            print("  WARN: Could not parse timestamps for ordering check")
            delta = 0

    print(f"  Status = completed: {'PASS' if status_ok else 'FAIL'}")
    print(f"  completed_at set: {'PASS' if completed_ok else 'FAIL'}")
    print(f"  completed_at > started_at: {'PASS' if order_ok else 'FAIL'}")

    RESULTS["completion"] = status_ok and completed_ok and order_ok


def step7_synthesis():
    """Step 7: Test synthesis mode."""
    global synthesis_output
    print("\n--- Step 7: Synthesis Mode ---")

    clusters = ra.supabase.table("problem_clusters").select("theme, opportunity_score")\
        .order("opportunity_score", desc=True).limit(5).execute()

    topics_for_synthesis = []
    for c in (clusters.data or [])[:3]:
        topics_for_synthesis.append({
            "topic_id": c.get("theme", "?").lower().replace(" ", "_"),
            "topic_name": c.get("theme", "?"),
            "score": c.get("opportunity_score", 0),
            "phase": "emerging",
            "velocity": 0.5,
        })

    if len(topics_for_synthesis) < 3:
        print("  SKIP: Not enough topics for synthesis")
        RESULTS["synthesis"] = None
        return

    topic_names = [t["topic_name"] for t in topics_for_synthesis]
    print(f"  Topics: {', '.join(topic_names)}")

    context_payload = {
        "topics": topics_for_synthesis,
        "recent_mentions": [],
        "synthesis_reason": "Test: forced synthesis mode",
    }

    synth_record = {
        "topic_id": "synthesis",
        "topic_name": "Landscape Synthesis",
        "priority_score": 0.4,
        "context_payload": context_payload,
        "mode": "synthesis",
        "status": "queued",
        "issue_number": TEST_ISSUE,
    }

    result = ra.supabase.table("research_queue").insert(synth_record).execute()
    synth_item = result.data[0] if result.data else None

    if not synth_item:
        print("  FAIL: Could not insert synthesis queue item")
        RESULTS["synthesis"] = False
        return

    print(f"  Queue item: {synth_item['id']}")

    ra.update_queue_status(synth_item["id"], "in_progress")

    sources = ra.gather_synthesis_sources(synth_item)
    print(f"  Sources gathered: {sources.get('total_sources', 0)} total")

    context = ra.build_context_window(synth_item, sources)
    thesis_data, usage = ra.generate_thesis(context, "synthesis")

    if not thesis_data:
        print("  FAIL: Synthesis thesis generation returned None")
        ra.update_queue_status(synth_item["id"], "failed")
        RESULTS["synthesis"] = False
        return

    mode_ok = thesis_data.get("mode") == "synthesis"
    print(f"  Mode in output: {thesis_data.get('mode')} {'PASS' if mode_ok else 'FAIL'}")

    usage_stats = {"input_tokens": usage.get("input_tokens", 0),
                   "output_tokens": usage.get("output_tokens", 0), "model": ra.MODEL}
    spotlight = ra.store_spotlight(synth_item, thesis_data, usage_stats)

    if spotlight:
        stored = ra.supabase.table("spotlight_history").select("mode")\
            .eq("id", spotlight["id"]).execute()
        stored_mode = stored.data[0].get("mode") if stored.data else "?"
        print(f"  spotlight_history mode: {stored_mode} {'PASS' if stored_mode == 'synthesis' else 'FAIL'}")

    all_text = (thesis_data.get("evidence", "") + " " + thesis_data.get("thesis", "")).lower()
    topics_found = sum(1 for tn in topic_names if tn.lower() in all_text)
    topics_check = topics_found >= 2
    print(f"  Topic names in output: {topics_found}/3 {'PASS' if topics_check else 'WARN'}")

    synthesis_output.update(thesis_data)

    ra.update_queue_status(synth_item["id"], "completed")

    RESULTS["synthesis"] = mode_ok and topics_check
    print(f"\n  SYNTHESIS THESIS: {thesis_data.get('thesis', 'MISSING')}")


def step8_error_handling():
    """Step 8: Test error handling with bad input."""
    print("\n--- Step 8: Error Handling ---")

    bad_record = {
        "topic_id": "test_nonexistent_topic_xyz",
        "topic_name": "Nonexistent Topic XYZ",
        "priority_score": 0.01,
        "context_payload": {},
        "mode": "spotlight",
        "status": "queued",
        "issue_number": TEST_ISSUE,
    }

    result = ra.supabase.table("research_queue").insert(bad_record).execute()
    bad_item = result.data[0] if result.data else None

    if not bad_item:
        print("  FAIL: Could not insert bad queue item")
        RESULTS["error_handling"] = False
        return

    print(f"  Bad queue item: {bad_item['id']}")

    try:
        ra.update_queue_status(bad_item["id"], "in_progress")
        sources = ra.gather_sources("test_nonexistent_topic_xyz", "Nonexistent Topic XYZ", {})
        total = sources.get("total_sources", 0)
        print(f"  Sources found: {total}")

        if total == 0:
            ra.update_queue_status(bad_item["id"], "completed",
                                   context_payload={"_warning": "no_sources_found"})
            print("  Agent handled empty sources gracefully (completed with warning)")
        else:
            context = ra.build_context_window(bad_item, sources)
            thesis_data, usage = ra.generate_thesis(context, "spotlight")
            if thesis_data:
                ra.store_spotlight(bad_item, thesis_data, {"input_tokens": 0, "output_tokens": 0, "model": ra.MODEL})
                ra.update_queue_status(bad_item["id"], "completed")
                print("  Agent produced output even with bad topic")
            else:
                ra.update_queue_status(bad_item["id"], "failed",
                                       context_payload={"_error": "thesis_generation_failed"})
                print("  Agent marked as failed (thesis generation failed)")

        no_crash = True
        print("  No crash: PASS")
    except Exception as e:
        print(f"  EXCEPTION (should not happen): {e}")
        try:
            ra.update_queue_status(bad_item["id"], "failed",
                                   context_payload={"_error": str(e)})
        except Exception:
            pass
        no_crash = False

    row = ra.supabase.table("research_queue").select("status")\
        .eq("id", bad_item["id"]).execute()
    final_status = row.data[0].get("status") if row.data else "?"
    status_ok = final_status in ("completed", "failed")
    print(f"  Final status: {final_status} {'PASS' if status_ok else 'FAIL'}")

    RESULTS["error_handling"] = no_crash and status_ok


def step9_cleanup():
    """Step 9: Clean up all test data."""
    print("\n--- Step 9: Cleanup ---")

    # Delete predictions linked to test spotlights first
    test_spotlights = ra.supabase.table("spotlight_history")\
        .select("id").eq("issue_number", TEST_ISSUE).execute()
    for s in (test_spotlights.data or []):
        try:
            ra.supabase.table("predictions").delete()\
                .eq("spotlight_id", s["id"]).execute()
        except Exception:
            pass

    sh = ra.supabase.table("spotlight_history").delete()\
        .eq("issue_number", TEST_ISSUE).execute()
    sh_deleted = len(sh.data) if sh.data else 0
    print(f"  spotlight_history deleted: {sh_deleted} rows")

    rq = ra.supabase.table("research_queue").delete()\
        .eq("issue_number", TEST_ISSUE).execute()
    rq_deleted = len(rq.data) if rq.data else 0
    print(f"  research_queue deleted: {rq_deleted} rows")

    remaining_sh = ra.supabase.table("spotlight_history").select("id")\
        .eq("issue_number", TEST_ISSUE).execute()
    remaining_rq = ra.supabase.table("research_queue").select("id")\
        .eq("issue_number", TEST_ISSUE).execute()

    clean = len(remaining_sh.data or []) == 0 and len(remaining_rq.data or []) == 0
    print(f"  No test data remains: {'PASS' if clean else 'FAIL'}")

    RESULTS["cleanup"] = clean


def step10_summary():
    """Step 10: Print summary."""
    topic = spotlight_output.get("topic_name", spotlight_output.get("topic_id", "?"))

    print(f"\n{'='*60}")
    print(f"=== RESEARCH AGENT CORE TEST ===")
    print(f"{'='*60}")
    print(f"Topic tested: {topic}")
    print()

    def pf(key, extra=""):
        val = RESULTS.get(key)
        if val is None:
            return "SKIP"
        return f"{'PASS' if val else 'FAIL'}{extra}"

    sc = RESULTS.get("source_counts", {})
    source_extra = f" ({sc.get('general', 0)} general, {sc.get('thought_leader', 0)} thought_leader, {sc.get('github', 0)} github)" if sc else ""
    issues = RESULTS.get("output_issues", [])
    issue_extra = f" ({'; '.join(issues)})" if issues else ""
    time_extra = f" (took {RESULTS.get('thesis_time', 0):.1f}s)" if RESULTS.get("thesis_time") else ""

    rows = [
        ("Queue pickup", pf("queue_pickup")),
        ("Source gathering", pf("source_gathering") + source_extra),
        ("Thesis generation", pf("thesis_generation") + time_extra),
        ("Output structure", pf("output_structure") + issue_extra),
        ("Storage", pf("storage")),
        ("Completion lifecycle", pf("completion")),
        ("Synthesis mode", pf("synthesis")),
        ("Error handling", pf("error_handling")),
        ("Cleanup", pf("cleanup")),
    ]

    for label, status in rows:
        print(f"  {label:<24} {status}")

    print(f"\n{'='*60}")
    print(f"=== GENERATED SPOTLIGHT (for manual review) ===")
    print(f"{'='*60}")
    print(f"THESIS: {spotlight_output.get('thesis', 'MISSING')}")
    print(f"\nEVIDENCE: {(spotlight_output.get('evidence', 'MISSING'))[:200]}...")
    print(f"\nCOUNTER: {(spotlight_output.get('counter_argument', 'MISSING'))[:200]}...")
    print(f"\nPREDICTION: {spotlight_output.get('prediction', 'MISSING')}")
    print(f"\nBUILDER: {(spotlight_output.get('builder_implications', 'MISSING'))[:200]}...")

    if synthesis_output:
        print(f"\n{'='*60}")
        print(f"=== SYNTHESIS OUTPUT (for manual review) ===")
        print(f"{'='*60}")
        print(f"THESIS: {synthesis_output.get('thesis', 'MISSING')}")

    test_keys = ["queue_pickup", "source_gathering", "thesis_generation",
                  "output_structure", "storage", "completion", "synthesis", "error_handling", "cleanup"]
    all_pass = all(RESULTS.get(k) is True for k in test_keys if RESULTS.get(k) is not None)
    print(f"\n{'='*60}")
    print(f"Overall: {'ALL PASS' if all_pass else 'SOME FAILURES'}")
    print(f"{'='*60}")


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 60)
    print("  TEST 2A: Research Agent Core — Full Integration")
    print("=" * 60)

    init_test()

    # Step 1: Setup
    queue_item, ctx = step1_setup()
    if not queue_item:
        print("\nFATAL: Setup failed, cannot continue")
        return

    try:
        # Step 2: Queue Pickup
        step2_queue_pickup(queue_item)

        # Step 3: Source Gathering
        sources = step3_source_gathering(queue_item)

        # Step 4: Thesis Generation
        thesis_data = step4_thesis_generation(queue_item, sources)

        # Step 5: Storage
        if thesis_data:
            step5_storage(queue_item, thesis_data, sources)
        else:
            print("\n--- Step 5: Storage ---")
            print("  SKIP: No thesis data")
            RESULTS["storage"] = False

        # Step 6: Completion
        step6_completion(queue_item)

        # Step 7: Synthesis
        step7_synthesis()

        # Step 8: Error Handling
        step8_error_handling()

    finally:
        # Step 9: Cleanup (always runs)
        step9_cleanup()

    # Step 10: Summary
    step10_summary()


if __name__ == "__main__":
    main()
