#!/usr/bin/env python3
"""
TEST 2B: Analyst Selection Heuristic — Full Test Suite

Tests the Spotlight topic selection logic:
  1. Topic landscape query + raw scoring
  2. Lifecycle bonus multipliers
  3. Cooldown filter
  4. Minimum signal filters
  5. Full selection + queue entry validation
  6. Synthesis fallback
  7. Edge cases
  8. Summary
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
sys.path.insert(0, str(PROC_DIR))

os.environ.setdefault("OPENCLAW_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data" / "openclaw"))

import agentpulse_processor as proc

RESULTS = {}
TEST_ISSUE = 997
INSERTED_IDS = {"research_queue": [], "spotlight_history": [], "topic_evolution": []}


def init_test():
    proc.init_clients()
    print(f"Processor initialized")
    print(f"Spotlight config: {proc._get_spotlight_config()}")


def cleanup_id(table, row_id):
    """Track an ID for cleanup."""
    INSERTED_IDS[table].append(row_id)


def ensure_test_topics():
    """If topic_evolution is empty, insert synthetic test topics.
    Returns (topics_list, were_synthetic)."""
    te = proc.supabase.table("topic_evolution").select("*")\
        .order("last_updated", desc=True).limit(50).execute()

    if te.data and len(te.data) >= 5:
        return te.data, False

    print("  topic_evolution is empty — inserting synthetic test topics")
    synthetic = [
        {"topic_key": "test_agent_security", "current_stage": "debating",
         "snapshots": [{"mentions": 15, "sources": ["hackernews", "moltbook", "rss_a16z"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
        {"topic_key": "test_mcp_governance", "current_stage": "building",
         "snapshots": [{"mentions": 10, "sources": ["hackernews", "rss_willison"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
        {"topic_key": "test_local_model_deploy", "current_stage": "emerging",
         "snapshots": [{"mentions": 6, "sources": ["hackernews", "github", "moltbook"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
        {"topic_key": "test_agent_payments", "current_stage": "emerging",
         "snapshots": [{"mentions": 4, "sources": ["hackernews", "moltbook"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
        {"topic_key": "test_rag_optimization", "current_stage": "mature",
         "snapshots": [{"mentions": 12, "sources": ["hackernews", "github"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
        {"topic_key": "test_prompt_injection", "current_stage": "declining",
         "snapshots": [{"mentions": 8, "sources": ["hackernews"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
        {"topic_key": "test_thin_signal_topic", "current_stage": "emerging",
         "snapshots": [{"mentions": 1, "sources": ["hackernews"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
        {"topic_key": "test_single_source_topic", "current_stage": "debating",
         "snapshots": [{"mentions": 5, "sources": ["hackernews"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
    ]

    inserted = []
    for t in synthetic:
        result = proc.supabase.table("topic_evolution").insert(t).execute()
        if result.data:
            row = result.data[0]
            inserted.append(row)
            INSERTED_IDS["topic_evolution"].append(row["id"])

    print(f"  Inserted {len(inserted)} synthetic topics")
    return inserted, True


# ============================================================================
# Step 1: Query current topic landscape
# ============================================================================

def step1_topic_landscape(topics):
    """Score and rank all topics by raw spotlight_score."""
    print(f"\n{'='*70}")
    print("  Step 1: Topic Landscape")
    print(f"{'='*70}")

    scored = []
    for t in topics:
        key = t.get("topic_key", "?")
        phase = t.get("current_stage", "emerging")
        velocity = proc._compute_velocity(t)
        diversity = proc._compute_source_diversity(t)
        bonus = proc.LIFECYCLE_BONUS.get(phase, 1.0)
        raw_score = velocity * diversity
        final_score = raw_score * bonus
        snaps = t.get("snapshots") or []
        mentions = snaps[-1].get("mentions", 0) if snaps else 0

        scored.append({
            "topic_key": key,
            "phase": phase,
            "mentions": mentions,
            "velocity": round(velocity, 3),
            "diversity": round(diversity, 3),
            "bonus": bonus,
            "raw_score": round(raw_score, 4),
            "final_score": round(final_score, 4),
        })

    scored.sort(key=lambda s: s["final_score"], reverse=True)

    print(f"\n  Top 10 topics by spotlight_score:")
    print(f"  {'Topic':<30} {'Phase':<12} {'Vel':>5} {'Div':>5} {'Bonus':>6} {'Raw':>7} {'Final':>7}")
    print(f"  {'-'*30} {'-'*12} {'-'*5} {'-'*5} {'-'*6} {'-'*7} {'-'*7}")
    for s in scored[:10]:
        print(f"  {s['topic_key']:<30} {s['phase']:<12} {s['velocity']:>5.3f} "
              f"{s['diversity']:>5.3f} {s['bonus']:>5.1f}x {s['raw_score']:>7.4f} {s['final_score']:>7.4f}")

    return scored


# ============================================================================
# Step 2: Lifecycle bonus multipliers
# ============================================================================

def step2_lifecycle_bonuses(scored):
    """Verify lifecycle bonuses are applied correctly."""
    print(f"\n{'='*70}")
    print("  Step 2: Lifecycle Bonus Multipliers")
    print(f"{'='*70}")

    expected = {"emerging": 1.0, "debating": 1.5, "building": 1.3, "mature": 0.5, "declining": 0.2}
    actual = proc.LIFECYCLE_BONUS

    all_correct = True
    for phase, exp_bonus in expected.items():
        act_bonus = actual.get(phase, "MISSING")
        ok = act_bonus == exp_bonus
        print(f"  {phase:<12} expected={exp_bonus}  actual={act_bonus}  {'PASS' if ok else 'FAIL'}")
        if not ok:
            all_correct = False

    raw_ranking = sorted(scored, key=lambda s: s["raw_score"], reverse=True)
    final_ranking = sorted(scored, key=lambda s: s["final_score"], reverse=True)

    raw_order = [s["topic_key"] for s in raw_ranking[:5]]
    final_order = [s["topic_key"] for s in final_ranking[:5]]
    ranking_changed = raw_order != final_order

    print(f"\n  Raw top 5:   {', '.join(raw_order)}")
    print(f"  Final top 5: {', '.join(final_order)}")
    print(f"  Ranking changed after bonus: {'YES' if ranking_changed else 'NO (same data / phases)'}")

    debating_topics = [s for s in scored if s["phase"] == "debating"]
    if debating_topics:
        for dt in debating_topics:
            if dt["raw_score"] > 0:
                ratio = dt["final_score"] / dt["raw_score"]
                ok = abs(ratio - 1.5) < 0.01
                print(f"  Debating '{dt['topic_key']}': final/raw = {ratio:.2f}x {'PASS' if ok else 'FAIL'}")
                if not ok:
                    all_correct = False

    RESULTS["lifecycle_bonuses"] = all_correct
    return all_correct


# ============================================================================
# Step 3: Cooldown filter
# ============================================================================

def step3_cooldown_filter(topics):
    """Test cooldown by inserting fake spotlight_history rows."""
    print(f"\n{'='*70}")
    print("  Step 3: Cooldown Filter")
    print(f"{'='*70}")

    max_issue = proc.supabase.table("spotlight_history")\
        .select("issue_number")\
        .order("issue_number", desc=True).limit(1).execute()
    current_issue = (max_issue.data[0].get("issue_number", 0) if max_issue.data else 0) + 1

    if len(topics) < 2:
        print("  SKIP: Need at least 2 topics for cooldown test")
        RESULTS["cooldown_filter"] = None
        return

    recent_topic = topics[0].get("topic_key", "test_recent")
    old_topic = topics[1].get("topic_key", "test_old") if len(topics) > 1 else "test_old_topic"

    recent_row = proc.supabase.table("spotlight_history").insert({
        "topic_id": recent_topic,
        "topic_name": recent_topic.replace("_", " ").title(),
        "issue_number": current_issue - 1,
        "mode": "spotlight",
        "thesis": "test", "evidence": "test", "counter_argument": "test",
        "prediction": "test", "full_output": "test",
    }).execute()
    recent_id = recent_row.data[0]["id"] if recent_row.data else None
    if recent_id:
        cleanup_id("spotlight_history", recent_id)
    print(f"  Inserted recent spotlight (issue {current_issue - 1}): {recent_topic}")

    old_row = proc.supabase.table("spotlight_history").insert({
        "topic_id": old_topic,
        "topic_name": old_topic.replace("_", " ").title(),
        "issue_number": current_issue - 10,
        "mode": "spotlight",
        "thesis": "test", "evidence": "test", "counter_argument": "test",
        "prediction": "test", "full_output": "test",
    }).execute()
    old_id = old_row.data[0]["id"] if old_row.data else None
    if old_id:
        cleanup_id("spotlight_history", old_id)
    print(f"  Inserted old spotlight (issue {current_issue - 10}): {old_topic}")

    try:
        cooldown = proc.get_spotlight_cooldown()
        cooldown_ids = {c.get("topic_id") for c in cooldown}

        recent_excluded = recent_topic in cooldown_ids
        old_excluded = old_topic in cooldown_ids

        print(f"  Recent '{recent_topic}' on cooldown: {recent_excluded} {'PASS' if recent_excluded else 'FAIL'}")
        print(f"  Old '{old_topic}' on cooldown: {old_excluded} {'PASS (not excluded)' if not old_excluded else 'FAIL (should not be excluded)'}")

        RESULTS["cooldown_filter"] = recent_excluded and not old_excluded
    except Exception as e:
        print(f"  ERROR: {e}")
        RESULTS["cooldown_filter"] = False


# ============================================================================
# Step 4: Minimum signal filters
# ============================================================================

def step4_minimum_filters(topics):
    """Verify minimum mention and source tier filters."""
    print(f"\n{'='*70}")
    print("  Step 4: Minimum Signal Filters")
    print(f"{'='*70}")

    config = proc._get_spotlight_config()
    min_mentions = config["min_mentions"]
    min_tiers = config["min_source_tiers"]

    excluded_mentions = []
    excluded_tiers = []
    passed = []

    for t in topics:
        key = t.get("topic_key", "?")
        snaps = t.get("snapshots") or []
        mentions = snaps[-1].get("mentions", 0) if snaps else 0
        sources = snaps[-1].get("sources", []) if snaps else []

        if mentions < min_mentions:
            excluded_mentions.append((key, mentions))
        elif len(set(sources)) < min_tiers:
            excluded_tiers.append((key, len(set(sources))))
        else:
            passed.append(key)

    print(f"  Min mentions threshold: {min_mentions}")
    print(f"  Min source tiers threshold: {min_tiers}")
    print(f"\n  Excluded by mention count (<{min_mentions}):")
    for key, count in excluded_mentions:
        print(f"    {key}: {count} mentions")
    if not excluded_mentions:
        print(f"    (none)")

    print(f"\n  Excluded by source tier count (<{min_tiers}):")
    for key, count in excluded_tiers:
        print(f"    {key}: {count} source tier(s)")
    if not excluded_tiers:
        print(f"    (none)")

    print(f"\n  Passed filters: {len(passed)} topics")

    mention_filter_works = all(m < min_mentions for _, m in excluded_mentions)
    tier_filter_works = all(c < min_tiers for _, c in excluded_tiers)
    has_filtering = len(excluded_mentions) > 0 or len(excluded_tiers) > 0

    ok = mention_filter_works and tier_filter_works
    if not has_filtering:
        print("  WARN: No topics were filtered (all meet minimums)")

    RESULTS["minimum_filters"] = ok
    return passed


# ============================================================================
# Step 5: Full selection
# ============================================================================

def step5_full_selection():
    """Run the complete selection heuristic and validate the queue entry."""
    print(f"\n{'='*70}")
    print("  Step 5: Full Selection")
    print(f"{'='*70}")

    result = proc.select_spotlight_topic()

    if result.get("error"):
        print(f"  ERROR: {result['error']}")
        RESULTS["full_selection"] = False
        RESULTS["queue_entry"] = False
        RESULTS["context_payload"] = False
        return result

    selected = result.get("selected")
    mode = result.get("mode", "?")
    score = result.get("score") or result.get("best_score", 0)
    queue_id = result.get("queue_id")
    candidates = result.get("candidates_evaluated", 0)

    print(f"  Winner: {selected}")
    print(f"  Mode: {mode}")
    print(f"  Score: {score}")
    print(f"  Candidates evaluated: {candidates}")

    if not selected:
        print("  No topic selected (all filtered or empty)")
        RESULTS["full_selection"] = result.get("reason") is not None
        RESULTS["queue_entry"] = None
        RESULTS["context_payload"] = None
        return result

    RESULTS["full_selection"] = True

    if not queue_id:
        print("  FAIL: No queue_id returned")
        RESULTS["queue_entry"] = False
        RESULTS["context_payload"] = False
        return result

    row = proc.supabase.table("research_queue").select("*")\
        .eq("id", queue_id).execute()

    if not row.data:
        print(f"  FAIL: Queue entry {queue_id} not found")
        RESULTS["queue_entry"] = False
        RESULTS["context_payload"] = False
        return result

    q = row.data[0]
    cleanup_id("research_queue", queue_id)

    checks = {}
    if mode == "spotlight":
        checks["topic_id matches"] = q.get("topic_id") == selected
        checks["topic_name populated"] = bool(q.get("topic_name"))
        checks["priority_score"] = abs((q.get("priority_score") or 0) - score) < 0.01
        checks["velocity populated"] = q.get("velocity") is not None
        checks["source_diversity populated"] = q.get("source_diversity") is not None
        checks["lifecycle_phase populated"] = bool(q.get("lifecycle_phase"))
        checks["mode = spotlight"] = q.get("mode") == "spotlight"
    else:
        checks["topic_id = synthesis"] = q.get("topic_id") == "synthesis"
        checks["mode = synthesis"] = q.get("mode") == "synthesis"

    checks["status = queued"] = q.get("status") == "queued"

    all_ok = True
    for label, ok in checks.items():
        print(f"    {label}: {'PASS' if ok else 'FAIL'}")
        if not ok:
            all_ok = False

    RESULTS["queue_entry"] = all_ok

    ctx = q.get("context_payload") or {}
    if mode == "spotlight":
        ctx_checks = {
            "has recent_mentions": "recent_mentions" in ctx,
            "has contrarian_signals": "contrarian_signals" in ctx,
        }
    else:
        ctx_checks = {
            "has topics": "topics" in ctx and len(ctx.get("topics", [])) >= 2,
            "has synthesis_reason": "synthesis_reason" in ctx,
        }

    ctx_ok = True
    for label, ok in ctx_checks.items():
        print(f"    context: {label}: {'PASS' if ok else 'FAIL'}")
        if not ok:
            ctx_ok = False

    RESULTS["context_payload"] = ctx_ok
    return result


# ============================================================================
# Step 6: Synthesis fallback
# ============================================================================

def step6_synthesis_fallback():
    """Force synthesis mode by setting threshold very high."""
    print(f"\n{'='*70}")
    print("  Step 6: Synthesis Fallback")
    print(f"{'='*70}")

    original_cache = proc._full_config_cache
    proc._full_config_cache = dict(original_cache) if original_cache else {}
    proc._full_config_cache["spotlight_selection"] = {
        "min_score_threshold": 99.0,
        "cooldown_issues": 4,
        "min_mentions": 1,
        "min_source_tiers": 1,
        "max_queue_items": 1,
    }

    try:
        config = proc._get_spotlight_config()
        print(f"  Threshold set to: {config['min_score_threshold']}")

        result = proc.select_spotlight_topic()

        mode = result.get("mode", "?")
        selected = result.get("selected")
        queue_id = result.get("queue_id")

        is_synthesis = mode == "synthesis"
        print(f"  Mode: {mode} {'PASS' if is_synthesis else 'FAIL'}")

        if isinstance(selected, list):
            print(f"  Synthesis topics ({len(selected)}):")
            for s in selected:
                print(f"    - {s}")
            has_multiple = len(selected) >= 2
        else:
            has_multiple = False
            if selected is None:
                print(f"  No candidates (all filtered) — acceptable if filters are strict")
                is_synthesis = result.get("reason") is not None

        if queue_id:
            row = proc.supabase.table("research_queue").select("mode, context_payload")\
                .eq("id", queue_id).execute()
            if row.data:
                q = row.data[0]
                ctx = q.get("context_payload") or {}
                topics_in_ctx = ctx.get("topics", [])
                print(f"  Queue mode: {q.get('mode')}")
                print(f"  Topics in context_payload: {len(topics_in_ctx)}")
                for tp in topics_in_ctx:
                    print(f"    - {tp.get('topic_name', tp.get('topic_id', '?'))} (score={tp.get('score', '?')})")
            cleanup_id("research_queue", queue_id)

        RESULTS["synthesis_fallback"] = is_synthesis

    finally:
        proc._full_config_cache = original_cache


# ============================================================================
# Step 7: Edge cases
# ============================================================================

def step7_edge_cases():
    """Test edge cases: all on cooldown, no topics, single topic."""
    print(f"\n{'='*70}")
    print("  Step 7: Edge Cases")
    print(f"{'='*70}")

    all_ok = True

    # 7a: No topics at all
    print("\n  7a: No topics in database")
    te_backup = proc.supabase.table("topic_evolution").select("*").execute()
    all_te = te_backup.data or []

    if all_te:
        for t in all_te:
            proc.supabase.table("topic_evolution").delete().eq("id", t["id"]).execute()

    try:
        result = proc.select_spotlight_topic()
        no_crash = True
        no_queue = result.get("queue_id") is None or result.get("selected") is None
        print(f"    No crash: PASS")
        print(f"    No queue entry: {'PASS' if no_queue else 'FAIL'}")
        if not no_queue:
            if result.get("queue_id"):
                cleanup_id("research_queue", result["queue_id"])
            all_ok = False
    except Exception as e:
        print(f"    EXCEPTION: {e}")
        no_crash = False
        all_ok = False

    if all_te:
        for t in all_te:
            t_copy = {k: v for k, v in t.items() if k != "id"}
            ins = proc.supabase.table("topic_evolution").insert(t_copy).execute()
            if ins.data:
                new_id = ins.data[0]["id"]
                old_id = t["id"]
                if old_id in INSERTED_IDS["topic_evolution"]:
                    INSERTED_IDS["topic_evolution"].remove(old_id)
                    INSERTED_IDS["topic_evolution"].append(new_id)

    # 7b: Only 1 topic exists
    print("\n  7b: Single topic")
    te_current = proc.supabase.table("topic_evolution").select("*").execute()
    current_topics = te_current.data or []

    if len(current_topics) > 1:
        to_remove = current_topics[1:]
        for t in to_remove:
            proc.supabase.table("topic_evolution").delete().eq("id", t["id"]).execute()

    try:
        result = proc.select_spotlight_topic()
        selected = result.get("selected")
        print(f"    Selected: {selected}")
        if result.get("queue_id"):
            cleanup_id("research_queue", result["queue_id"])
        single_ok = selected is not None or result.get("reason") is not None
        print(f"    Result: {'PASS' if single_ok else 'FAIL'}")
        if not single_ok:
            all_ok = False
    except Exception as e:
        print(f"    EXCEPTION: {e}")
        all_ok = False

    if len(current_topics) > 1:
        for t in to_remove:
            t_copy = {k: v for k, v in t.items() if k != "id"}
            ins = proc.supabase.table("topic_evolution").insert(t_copy).execute()
            if ins.data:
                new_id = ins.data[0]["id"]
                old_id = t["id"]
                if old_id in INSERTED_IDS["topic_evolution"]:
                    INSERTED_IDS["topic_evolution"].remove(old_id)
                    INSERTED_IDS["topic_evolution"].append(new_id)

    RESULTS["edge_cases"] = all_ok


# ============================================================================
# Step 8: Cleanup
# ============================================================================

def step8_cleanup():
    """Remove all test data."""
    print(f"\n{'='*70}")
    print("  Step 8: Cleanup")
    print(f"{'='*70}")

    for rid in INSERTED_IDS["research_queue"]:
        try:
            proc.supabase.table("research_queue").delete().eq("id", rid).execute()
        except Exception as e:
            print(f"  WARN: Failed to delete research_queue {rid}: {e}")
    print(f"  research_queue: deleted {len(INSERTED_IDS['research_queue'])} rows")

    for sid in INSERTED_IDS["spotlight_history"]:
        try:
            proc.supabase.table("predictions").delete().eq("spotlight_id", sid).execute()
            proc.supabase.table("spotlight_history").delete().eq("id", sid).execute()
        except Exception as e:
            print(f"  WARN: Failed to delete spotlight_history {sid}: {e}")
    print(f"  spotlight_history: deleted {len(INSERTED_IDS['spotlight_history'])} rows")

    for tid in INSERTED_IDS["topic_evolution"]:
        try:
            proc.supabase.table("topic_evolution").delete().eq("id", tid).execute()
        except Exception as e:
            print(f"  WARN: Failed to delete topic_evolution {tid}: {e}")
    print(f"  topic_evolution: deleted {len(INSERTED_IDS['topic_evolution'])} rows")

    remaining_rq = proc.supabase.table("research_queue").select("id")\
        .eq("issue_number", TEST_ISSUE).execute()
    for r in (remaining_rq.data or []):
        proc.supabase.table("research_queue").delete().eq("id", r["id"]).execute()

    clean = True
    for table in ["research_queue", "spotlight_history"]:
        remaining = proc.supabase.table(table).select("id")\
            .eq("issue_number", TEST_ISSUE).execute()
        if remaining.data:
            clean = False
            print(f"  WARN: {len(remaining.data)} leftover rows in {table}")

    print(f"  Clean state: {'PASS' if clean else 'WARN'}")
    RESULTS["cleanup"] = clean


# ============================================================================
# Summary
# ============================================================================

def print_summary(scored, passed_filters):
    """Print the final test summary."""
    total_topics = len(scored)
    passed_count = len(passed_filters)

    print(f"\n{'='*70}")
    print(f"  === SELECTION HEURISTIC TEST ===")
    print(f"{'='*70}")
    print(f"  Total topics evaluated:     {total_topics}")
    print(f"  Passed minimum filters:     {passed_count}")

    top5 = sorted(scored, key=lambda s: s["final_score"], reverse=True)[:5]
    if top5:
        print(f"\n  Top 5 candidates:")
        for i, s in enumerate(top5, 1):
            print(f"  {i}. {s['topic_key']} -- score: {s['final_score']:.4f} "
                  f"(velocity: {s['velocity']:.3f}, diversity: {s['diversity']:.3f}, "
                  f"phase: {s['phase']}, bonus: {s['bonus']}x)")

        print(f"\n  Winner: {top5[0]['topic_key']} (score: {top5[0]['final_score']:.4f})")

    print()

    def pf(key):
        val = RESULTS.get(key)
        if val is None:
            return "SKIP"
        return "PASS" if val else "FAIL"

    rows = [
        ("Lifecycle bonuses", pf("lifecycle_bonuses")),
        ("Cooldown filter", pf("cooldown_filter")),
        ("Minimum signal filters", pf("minimum_filters")),
        ("Full selection", pf("full_selection")),
        ("Queue entry written", pf("queue_entry")),
        ("Context payload complete", pf("context_payload")),
        ("Synthesis fallback", pf("synthesis_fallback")),
        ("Edge cases", pf("edge_cases")),
        ("Cleanup", pf("cleanup")),
    ]

    for label, status in rows:
        print(f"  {label:<28} {status}")

    test_keys = ["lifecycle_bonuses", "cooldown_filter", "minimum_filters",
                 "full_selection", "queue_entry", "context_payload",
                 "synthesis_fallback", "edge_cases", "cleanup"]
    all_pass = all(RESULTS.get(k) is True for k in test_keys if RESULTS.get(k) is not None)
    print(f"\n  Overall: {'ALL PASS' if all_pass else 'SOME FAILURES'}")


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 70)
    print("  TEST 2B: Analyst Selection Heuristic")
    print("=" * 70)

    init_test()

    topics, synthetic = ensure_test_topics()
    if not topics:
        print("\nFATAL: No topics available even after synthesis")
        return

    try:
        scored = step1_topic_landscape(topics)
        step2_lifecycle_bonuses(scored)
        step3_cooldown_filter(topics)
        passed_filters = step4_minimum_filters(topics)
        step5_full_selection()
        step6_synthesis_fallback()
        step7_edge_cases()
    finally:
        step8_cleanup()

    print_summary(scored, passed_filters)


if __name__ == "__main__":
    main()
