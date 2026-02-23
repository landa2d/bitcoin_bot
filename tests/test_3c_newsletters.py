#!/usr/bin/env python3
"""
TEST 3C: Newsletter Generation — 3 Test Runs

  1. Happy Path:      Real data with Spotlight
  2. Synthesis Mode:  High threshold → synthesis Spotlight
  3. Missing Spotlight: Newsletter without Spotlight section

Each run generates a full newsletter and evaluates quality.
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
NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
sys.path.insert(0, str(PROC_DIR))
sys.path.insert(0, str(RESEARCH_DIR))
sys.path.insert(0, str(NL_DIR))

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

import newsletter_poller as nl

RESULTS_DIR = Path(__file__).resolve().parent / "newsletter_test_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

CLEANUP_IDS = {"research_queue": [], "spotlight_history": [], "topic_evolution": [], "agent_tasks": []}


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

    from openai import OpenAI
    oai_key = vals.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    nl.supabase = proc.supabase
    nl.client = OpenAI(api_key=oai_key)

    print("  All clients initialized")


def ensure_topics():
    te = proc.supabase.table("topic_evolution").select("id").limit(3).execute()
    if te.data and len(te.data) >= 3:
        return
    synthetic = [
        {"topic_key": "nl_test_agent_security", "current_stage": "debating",
         "snapshots": [{"mentions": 14, "sources": ["hackernews", "moltbook", "rss_a16z"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
        {"topic_key": "nl_test_mcp_governance", "current_stage": "building",
         "snapshots": [{"mentions": 9, "sources": ["hackernews", "github"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
        {"topic_key": "nl_test_local_models", "current_stage": "emerging",
         "snapshots": [{"mentions": 5, "sources": ["hackernews", "moltbook", "github"]}],
         "last_updated": datetime.now(timezone.utc).isoformat()},
    ]
    for t in synthetic:
        r = proc.supabase.table("topic_evolution").insert(t).execute()
        if r.data:
            CLEANUP_IDS["topic_evolution"].append(r.data[0]["id"])
    print(f"  Inserted {len(synthetic)} synthetic topics")


def generate_spotlight(mode="spotlight"):
    """Run the selection + research pipeline and return the spotlight data."""
    for f in proc.RESEARCH_TRIGGER_DIR.glob("research-trigger-*.json"):
        f.unlink(missing_ok=True)

    result = proc.select_spotlight_topic()
    queue_id = result.get("queue_id")
    if queue_id:
        CLEANUP_IDS["research_queue"].append(queue_id)

    if not queue_id:
        print(f"    No topic selected: {result.get('reason', '?')}")
        return None

    item = ra.check_triggers() or ra.poll_queue()
    if not item:
        return None

    ra.update_queue_status(queue_id, "in_progress")
    topic_id = item.get("topic_id", "")
    topic_name = item.get("topic_name", "")
    item_mode = item.get("mode", "spotlight")

    if item_mode == "synthesis":
        sources = ra.gather_synthesis_sources(item)
    else:
        sources = ra.gather_sources(topic_id, topic_name, item.get("context_payload"))

    context = ra.build_context_window(item, sources)
    thesis_data, usage = ra.generate_thesis(context, mode=item_mode)

    if not thesis_data:
        ra.update_queue_status(queue_id, "failed")
        return None

    spotlight = ra.store_spotlight(item, thesis_data, usage)
    if spotlight:
        ra.update_queue_status(queue_id, "completed")
        CLEANUP_IDS["spotlight_history"].append(spotlight["id"])
        return spotlight
    else:
        ra.update_queue_status(queue_id, "failed")
        return None


def build_newsletter_input(spotlight_data=None):
    """Build the input_data dict that the Newsletter Agent would receive."""
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    opps = proc.supabase.table("opportunities").select("*")\
        .eq("status", "draft").gte("confidence_score", 0.3)\
        .order("confidence_score", desc=True).limit(5).execute()

    signals = proc.supabase.table("problem_clusters").select("*")\
        .gte("created_at", week_ago)\
        .gte("opportunity_score", 0.3)\
        .order("opportunity_score", desc=True).limit(10).execute()

    curious = proc.supabase.table("trending_topics").select("*")\
        .gte("extracted_at", week_ago)\
        .order("novelty_score", desc=True).limit(8).execute()

    predictions = proc.supabase.table("predictions").select("*")\
        .in_("status", ["active", "confirmed", "faded"])\
        .order("current_score", desc=True).limit(10).execute()

    tools = proc.supabase.table("tool_stats").select("*")\
        .order("mentions_7d", desc=True).limit(10).execute()

    te = proc.supabase.table("topic_evolution").select("*")\
        .order("last_updated", desc=True).limit(15).execute()

    tl = proc.supabase.table("source_posts").select("*")\
        .like("source", "thought_leader_%")\
        .gte("scraped_at", week_ago)\
        .order("scraped_at", desc=True).limit(20).execute()

    radar = [t for t in (te.data or []) if t.get("current_stage") == "emerging"][:4]

    try:
        edition_result = proc.supabase.rpc("next_newsletter_edition").execute()
        edition_number = edition_result.data if edition_result.data else 99
    except Exception:
        edition_number = 99

    spotlight_formatted = None
    if spotlight_data:
        spotlight_formatted = {
            "topic_name": spotlight_data.get("topic_name", ""),
            "mode": spotlight_data.get("mode", "spotlight"),
            "thesis": spotlight_data.get("thesis", ""),
            "evidence": spotlight_data.get("evidence", ""),
            "counter_argument": spotlight_data.get("counter_argument", ""),
            "prediction": spotlight_data.get("prediction", ""),
            "builder_implications": spotlight_data.get("builder_implications", ""),
            "sources_used": spotlight_data.get("sources_used", []),
        }

    return {
        "edition_number": edition_number,
        "section_a_opportunities": opps.data or [],
        "section_b_emerging": [
            {"type": "cluster", "theme": c.get("theme", ""), "description": c.get("description", ""),
             "opportunity_score": c.get("opportunity_score", 0)}
            for c in (signals.data or [])
        ],
        "section_c_curious": curious.data or [],
        "predictions": predictions.data or [],
        "trending_tools": tools.data or [],
        "tool_warnings": [],
        "clusters": (signals.data or [])[:5],
        "topic_evolution": te.data or [],
        "radar_topics": radar,
        "spotlight": spotlight_formatted,
        "thought_leader_content": tl.data or [],
        "stats": {
            "posts_count": 100,
            "problems_count": 50,
            "tools_count": len(tools.data or []),
            "new_opps_count": len(opps.data or []),
            "emerging_signals_count": len(signals.data or []),
            "trending_topics_count": len(curious.data or []),
            "source_breakdown": {"moltbook": 30, "hackernews": 40, "github": 20, "rss_premium": 5, "thought_leaders": 5},
            "total_posts_all_sources": 100,
            "topic_stages": {"emerging": len(radar), "debating": 3, "building": 2},
        },
        "freshness_rules": {
            "excluded_opportunity_ids": [],
            "max_returning_items_section_a": 2,
            "min_new_items_section_a": 1,
            "section_b_new_only": True,
            "section_c_new_only": True,
            "returning_items_require_new_angle": True,
        },
    }


def call_newsletter_agent(input_data):
    """Call the Newsletter Agent's generation function directly."""
    budget = {"max_llm_calls": 6, "max_seconds": 300, "max_subtasks": 2, "max_retries": 2}
    t0 = time.time()
    result = nl.generate_newsletter("write_newsletter", input_data, budget)
    elapsed = time.time() - t0
    return result, elapsed


# ============================================================================
# Quality Checks
# ============================================================================

def check_spotlight_quality(md):
    """Check Spotlight section quality in the markdown."""
    issues = []

    spotlight_match = re.search(r'##\s*(?:2\.\s*)?Spotlight(.*?)(?=\n##\s|\Z)', md, re.DOTALL | re.IGNORECASE)
    if not spotlight_match:
        return None, ["Spotlight section not found"]

    text = spotlight_match.group(1).strip()
    words = len(text.split())

    if words < 200:
        issues.append(f"too short ({words} words, need 400+)")
    if words > 600:
        issues.append(f"too long ({words} words, max 500)")

    if re.search(r'(?:^|\n)\s*[-*\u2022]\s', text):
        issues.append("contains bullet points")

    ai_phrases = ["it remains to be seen", "in the rapidly evolving landscape",
                  "it's worth noting", "as we navigate", "a myriad of"]
    found = [p for p in ai_phrases if p in text.lower()]
    if found:
        issues.append(f"AI phrases: {found}")

    lines = text.strip().split("\n")
    headline = lines[0] if lines else ""
    if not headline.startswith("**") and not headline.startswith("#"):
        issues.append("headline not bold/formatted")

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) > 6:
        issues.append(f"too many paragraphs ({len(paragraphs)}, max 5)")

    return len(issues) == 0, issues


def check_signals_quality(md, spotlight_topic=None):
    """Check Signals section quality."""
    issues = []

    signals_match = re.search(
        r'##\s*(?:\d+\.\s*)?(?:Emerging\s+Signals|Signals)(.*?)(?=\n##\s|\Z)', md, re.DOTALL | re.IGNORECASE)
    if not signals_match:
        return None, ["Signals section not found"]

    text = signals_match.group(1).strip()

    items = re.findall(r'\*\*[^*]+\*\*', text)
    if len(items) < 2:
        issues.append(f"only {len(items)} items (need 2+)")

    if spotlight_topic and spotlight_topic.lower() in text.lower():
        issues.append(f"overlaps with Spotlight topic '{spotlight_topic}'")

    return len(issues) == 0, issues


def check_radar_quality(md):
    """Check Radar section quality."""
    issues = []

    radar_match = re.search(
        r'##\s*(?:\d+\.\s*)?(?:On Our\s+)?Radar(.*?)(?=\n##\s|\Z)', md, re.DOTALL | re.IGNORECASE)
    if not radar_match:
        return None, ["Radar section not found (may be skipped if <3 topics)"]

    text = radar_match.group(1).strip()
    items = re.findall(r'\*\*[^*]+\*\*', text)
    if len(items) < 2:
        issues.append(f"only {len(items)} radar items")

    return len(issues) == 0, issues


def check_overall(md):
    """Check overall newsletter quality."""
    issues = []

    words = len(md.split())
    if words < 500:
        issues.append(f"newsletter very short ({words} words)")
    if words > 2000:
        issues.append(f"newsletter very long ({words} words)")

    read_time = words / 200
    if read_time < 2:
        issues.append(f"estimated read time only {read_time:.1f}min (expect 5-8)")

    sections_found = re.findall(r'^##\s+', md, re.MULTILINE)
    if len(sections_found) < 3:
        issues.append(f"only {len(sections_found)} sections found")

    return len(issues) == 0, issues


def print_quality_report(run_name, md, spotlight_topic=None, has_spotlight=True):
    """Print the full quality checklist for a newsletter."""
    print(f"\n  {'='*60}")
    print(f"  QUALITY CHECKLIST: {run_name}")
    print(f"  {'='*60}")

    if has_spotlight:
        sp_ok, sp_issues = check_spotlight_quality(md)
        if sp_ok is None:
            print(f"  Spotlight:       SKIP (not found)")
        else:
            print(f"  Spotlight:       {'PASS' if sp_ok else 'FAIL'}", end="")
            if sp_issues:
                print(f" [{'; '.join(sp_issues)}]")
            else:
                print()
    else:
        sp_present = bool(re.search(r'Spotlight', md, re.IGNORECASE))
        if sp_present:
            print(f"  No Spotlight:    FAIL (Spotlight section found but should be absent)")
        else:
            print(f"  No Spotlight:    PASS (correctly omitted)")

    sig_ok, sig_issues = check_signals_quality(md, spotlight_topic)
    if sig_ok is None:
        print(f"  Signals:         SKIP ({sig_issues[0] if sig_issues else '?'})")
    else:
        print(f"  Signals:         {'PASS' if sig_ok else 'FAIL'}", end="")
        if sig_issues:
            print(f" [{'; '.join(sig_issues)}]")
        else:
            print()

    rad_ok, rad_issues = check_radar_quality(md)
    if rad_ok is None:
        print(f"  Radar:           SKIP ({rad_issues[0] if rad_issues else '?'})")
    else:
        print(f"  Radar:           {'PASS' if rad_ok else 'FAIL'}", end="")
        if rad_issues:
            print(f" [{'; '.join(rad_issues)}]")
        else:
            print()

    ov_ok, ov_issues = check_overall(md)
    print(f"  Overall:         {'PASS' if ov_ok else 'WARN'}", end="")
    if ov_issues:
        print(f" [{'; '.join(ov_issues)}]")
    else:
        print()

    words = len(md.split())
    print(f"  Word count:      {words}")
    print(f"  Est. read time:  {words/200:.1f} min")


# ============================================================================
# Test Runs
# ============================================================================

def test_run_1_happy_path():
    """Test Run 1: Full pipeline with real data and Spotlight."""
    print(f"\n{'#'*70}")
    print(f"  TEST RUN 1: Happy Path")
    print(f"{'#'*70}")

    print("\n  Generating spotlight...")
    spotlight = generate_spotlight()

    if spotlight:
        topic = spotlight.get("topic_name", "?")
        print(f"  Spotlight generated: {topic}")
        print(f"    Thesis: {(spotlight.get('thesis') or '')[:100]}...")
    else:
        print("  WARNING: No spotlight generated — test will proceed without")

    print("\n  Building newsletter input...")
    input_data = build_newsletter_input(spotlight)
    print(f"    Opportunities: {len(input_data['section_a_opportunities'])}")
    print(f"    Signals: {len(input_data['section_b_emerging'])}")
    print(f"    Radar: {len(input_data['radar_topics'])}")
    print(f"    Spotlight: {'present' if input_data['spotlight'] else 'missing'}")

    print("\n  Calling Newsletter Agent...")
    result, elapsed = call_newsletter_agent(input_data)

    title = result.get("title", "?")
    md = result.get("content_markdown", "")
    tg = result.get("content_telegram", "")

    print(f"  Generated in {elapsed:.1f}s")
    print(f"  Title: {title}")
    print(f"  Markdown: {len(md)} chars")
    print(f"  Telegram: {len(tg)} chars")

    print(f"\n  {'='*60}")
    print(f"  FULL NEWSLETTER OUTPUT")
    print(f"  {'='*60}")
    for line in md.split("\n"):
        print(f"  {line}")

    if tg:
        print(f"\n  {'='*60}")
        print(f"  TELEGRAM DIGEST")
        print(f"  {'='*60}")
        print(f"  {tg}")

    spotlight_topic = spotlight.get("topic_name") if spotlight else None
    print_quality_report("Happy Path", md, spotlight_topic, has_spotlight=bool(spotlight))

    path = RESULTS_DIR / "test_run_1_happy_path.md"
    path.write_text(md)
    print(f"\n  Saved to: {path.name}")

    return result, md


def test_run_2_synthesis():
    """Test Run 2: Force synthesis mode with high threshold."""
    print(f"\n{'#'*70}")
    print(f"  TEST RUN 2: Synthesis Mode")
    print(f"{'#'*70}")

    original_cache = proc._full_config_cache
    proc._full_config_cache = dict(original_cache) if original_cache else {}
    proc._full_config_cache["spotlight_selection"] = {
        "min_score_threshold": 99.0,
        "cooldown_issues": 4, "min_mentions": 1, "min_source_tiers": 1, "max_queue_items": 1,
    }

    try:
        print("\n  Generating synthesis spotlight (threshold=99.0)...")
        spotlight = generate_spotlight(mode="synthesis")

        if spotlight:
            mode = spotlight.get("mode", "?")
            print(f"  Spotlight generated (mode={mode})")
            print(f"    Thesis: {(spotlight.get('thesis') or '')[:100]}...")
        else:
            print("  WARNING: No synthesis spotlight generated")

        print("\n  Building newsletter input...")
        input_data = build_newsletter_input(spotlight)

        print("\n  Calling Newsletter Agent...")
        result, elapsed = call_newsletter_agent(input_data)

        md = result.get("content_markdown", "")

        print(f"  Generated in {elapsed:.1f}s")
        print(f"  Title: {result.get('title', '?')}")

        print(f"\n  {'='*60}")
        print(f"  FULL NEWSLETTER OUTPUT")
        print(f"  {'='*60}")
        for line in md.split("\n"):
            print(f"  {line}")

        spotlight_topic = spotlight.get("topic_name") if spotlight else None
        print_quality_report("Synthesis Mode", md, spotlight_topic, has_spotlight=bool(spotlight))

        path = RESULTS_DIR / "test_run_2_synthesis.md"
        path.write_text(md)
        print(f"\n  Saved to: {path.name}")

        return result, md

    finally:
        proc._full_config_cache = original_cache


def test_run_3_missing_spotlight():
    """Test Run 3: Newsletter without Spotlight section."""
    print(f"\n{'#'*70}")
    print(f"  TEST RUN 3: Missing Spotlight")
    print(f"{'#'*70}")

    print("\n  Building newsletter input WITHOUT spotlight...")
    input_data = build_newsletter_input(spotlight_data=None)

    print(f"    Opportunities: {len(input_data['section_a_opportunities'])}")
    print(f"    Signals: {len(input_data['section_b_emerging'])}")
    print(f"    Spotlight: None (simulating Research Agent failure)")

    print("\n  Calling Newsletter Agent...")
    result, elapsed = call_newsletter_agent(input_data)

    md = result.get("content_markdown", "")

    print(f"  Generated in {elapsed:.1f}s")
    print(f"  Title: {result.get('title', '?')}")

    print(f"\n  {'='*60}")
    print(f"  FULL NEWSLETTER OUTPUT")
    print(f"  {'='*60}")
    for line in md.split("\n"):
        print(f"  {line}")

    print_quality_report("Missing Spotlight", md, has_spotlight=False)

    has_broken_refs = bool(re.search(r'spotlight|Spotlight.*(?:missing|unavailable|none)', md, re.IGNORECASE))
    if has_broken_refs:
        print(f"  Broken references: WARN (references to missing Spotlight found)")
    else:
        print(f"  Broken references: PASS (no references to missing Spotlight)")

    path = RESULTS_DIR / "test_run_3_missing_spotlight.md"
    path.write_text(md)
    print(f"\n  Saved to: {path.name}")

    return result, md


# ============================================================================
# Cleanup and Summary
# ============================================================================

def cleanup():
    print(f"\n{'='*70}")
    print(f"  Cleanup")
    print(f"{'='*70}")

    for rid in CLEANUP_IDS["research_queue"]:
        try:
            proc.supabase.table("research_queue").delete().eq("id", rid).execute()
        except Exception:
            pass
    print(f"  research_queue: {len(CLEANUP_IDS['research_queue'])} rows")

    for sid in CLEANUP_IDS["spotlight_history"]:
        try:
            proc.supabase.table("predictions").delete().eq("spotlight_id", sid).execute()
            proc.supabase.table("spotlight_history").delete().eq("id", sid).execute()
        except Exception:
            pass
    print(f"  spotlight_history: {len(CLEANUP_IDS['spotlight_history'])} rows")

    for tid in CLEANUP_IDS["topic_evolution"]:
        try:
            proc.supabase.table("topic_evolution").delete().eq("id", tid).execute()
        except Exception:
            pass
    print(f"  topic_evolution: {len(CLEANUP_IDS['topic_evolution'])} rows")

    for f in proc.RESEARCH_TRIGGER_DIR.glob("research-trigger-*.json"):
        f.unlink(missing_ok=True)
    print(f"  Trigger files: cleaned")


def main():
    print("=" * 70)
    print("  TEST 3C: Newsletter Generation — 3 Test Runs")
    print("=" * 70)

    init()
    ensure_topics()

    try:
        r1, md1 = test_run_1_happy_path()
        r2, md2 = test_run_2_synthesis()
        r3, md3 = test_run_3_missing_spotlight()
    finally:
        cleanup()

    print(f"\n{'='*70}")
    print(f"  === SHIP DECISION ===")
    print(f"{'='*70}")
    print(f"  Test Run 1 (Happy Path):      Generated ({len(md1.split())} words)")
    print(f"  Test Run 2 (Synthesis):        Generated ({len(md2.split())} words)")
    print(f"  Test Run 3 (Missing Spotlight): Generated ({len(md3.split())} words)")
    print(f"\n  All 3 newsletters saved to: {RESULTS_DIR}")
    print(f"  Review each one manually to make the ship decision.")
    print(f"\n  Ship criteria:")
    print(f"    - At least 2/3 runs produce a newsletter you'd be proud to send")
    print(f"    - Spotlight passes the 'forwarding test'")
    print(f"    - No critical formatting or pipeline issues")


if __name__ == "__main__":
    main()
