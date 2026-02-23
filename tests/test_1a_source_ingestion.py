#!/usr/bin/env python3
"""
TEST 1A: Thought Leader Source Ingestion
Tests RSS scraping, deduplication, dual routing, and error handling for 6 thought leader feeds.
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

env_path = Path(__file__).resolve().parent.parent / 'config' / '.env'
load_dotenv(env_path)

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("FATAL: SUPABASE_URL or SUPABASE_KEY not set")
    sys.exit(1)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

proc_dir = Path(__file__).resolve().parent.parent / 'docker' / 'processor'
sys.path.insert(0, str(proc_dir))

EXPECTED_SOURCES = {
    'deeplearning_ai': 'DeepLearning.AI (Andrew Ng)',
    'simon_willison': 'Simon Willison',
    'latent_space': 'Latent Space',
    'swyx': 'Swyx',
    'langchain_blog': 'LangChain Blog (Harrison Chase)',
    'ethan_mollick': 'Ethan Mollick (One Useful Thing)',
}

REQUIRED_METADATA_FIELDS = ['source_name', 'source_tier', 'topics_detected', 'content_summary', 'published_at']


def get_thought_leader_posts(feed_key: str = None, days_back: int = 30) -> list:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
    query = sb.table('source_posts').select('*')
    if feed_key:
        query = query.eq('source', f'thought_leader_{feed_key}')
    else:
        query = query.like('source', 'thought_leader_%')
    result = query.gte('scraped_at', cutoff).order('scraped_at', desc=True).execute()
    return result.data or []


def count_thought_leader_posts(feed_key: str = None) -> int:
    query = sb.table('source_posts').select('id', count='exact')
    if feed_key:
        query = query.eq('source', f'thought_leader_{feed_key}')
    else:
        query = query.like('source', 'thought_leader_%')
    result = query.execute()
    return result.count or 0


def run_scrape():
    import agentpulse_processor as proc
    proc.load_dotenv(env_path)
    proc.SUPABASE_URL = SUPABASE_URL
    proc.SUPABASE_KEY = SUPABASE_KEY
    proc.supabase = sb
    return proc.scrape_thought_leaders()


def test_ingestion():
    """Step 1-2: Run scraper and verify items exist for each source."""
    print("--- Step 1: Running thought leader scrape ---")
    result = run_scrape()
    scrape_results = result.get('results', {})
    print(f"  Feeds scraped: {result.get('feeds_scraped', 0)}/{len(EXPECTED_SOURCES)}")
    print(f"  Total articles: {result.get('total_articles', 0)}")

    feed_errors = {}
    for fk, v in scrape_results.items():
        if isinstance(v, dict) and 'error' in v:
            feed_errors[fk] = v['error']

    if feed_errors:
        print(f"  Feed errors: {json.dumps(feed_errors, indent=4, default=str)}")

    print("\n--- Step 2: Verifying ingested items ---")
    source_results = {}

    for feed_key, display_name in EXPECTED_SOURCES.items():
        posts = get_thought_leader_posts(feed_key)
        count = len(posts)
        latest_title = posts[0]['title'] if posts else 'N/A'
        latest_time = posts[0].get('scraped_at', 'N/A') if posts else 'N/A'

        field_issues = []
        if posts:
            p = posts[0]
            if p.get('source_tier') != 2:
                field_issues.append(f"source_tier={p.get('source_tier')} (expected 2)")
            meta = p.get('metadata', {})
            for f in REQUIRED_METADATA_FIELDS:
                if f not in meta or meta[f] is None:
                    field_issues.append(f"metadata.{f} missing")
            if not p.get('title'):
                field_issues.append("title missing")
            if not p.get('source_url'):
                field_issues.append("source_url missing")

        if count > 0 and not field_issues:
            status = 'PASS'
        elif count == 0 and feed_key in feed_errors:
            status = f'WARN (unreachable)'
        else:
            status = 'FAIL'

        source_results[feed_key] = {
            'name': display_name, 'count': count,
            'latest': latest_title[:60], 'time': latest_time,
            'status': status, 'issues': field_issues,
        }

    print(f"\n  {'Source':<35} {'Items':>5}  {'Latest Item':<62} Status")
    print(f"  {'-'*35} {'-'*5}  {'-'*62} {'-'*6}")
    for fk, r in source_results.items():
        print(f"  {r['name']:<35} {r['count']:>5}  {r['latest']:<62} {r['status']}")
        if r['issues']:
            print(f"    Issues: {', '.join(r['issues'])}")

    return source_results


def test_dual_routing():
    """Step 3: Verify dual routing — Analyst normal scan + Research Agent filter."""
    print("\n--- Step 3: Dual routing test ---")

    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    all_posts = sb.table('source_posts').select('source, source_tier')\
        .gte('scraped_at', week_ago)\
        .order('scraped_at', desc=True)\
        .limit(200)\
        .execute()

    tl_in_all = [p for p in (all_posts.data or []) if str(p.get('source', '')).startswith('thought_leader_')]
    print(f"  3a. Analyst scan: {len(all_posts.data or [])} total posts, {len(tl_in_all)} are thought_leader")
    analyst_ok = len(tl_in_all) > 0

    tl_only = sb.table('source_posts').select('id', count='exact')\
        .like('source', 'thought_leader_%')\
        .gte('scraped_at', week_ago)\
        .execute()
    research_count = tl_only.count or 0
    print(f"  3b. Research Agent filter: {research_count} thought_leader posts found")
    research_ok = research_count > 0

    status = 'PASS' if analyst_ok and research_ok else 'FAIL'
    print(f"  Dual routing: {status}")
    return status


def test_dedup():
    """Step 4: Run scraper twice, verify no duplicates created."""
    print("\n--- Step 4: Deduplication test ---")

    count_before = count_thought_leader_posts()
    print(f"  Count before second scrape: {count_before}")

    run_scrape()
    time.sleep(2)

    count_after = count_thought_leader_posts()
    print(f"  Count after second scrape:  {count_after}")

    new_items = count_after - count_before
    status = 'PASS' if new_items == 0 else 'FAIL'
    print(f"  New items created: {new_items} — {status}")
    return status


def test_error_handling():
    """Step 5: Simulate one bad feed, verify others still work."""
    print("\n--- Step 5: Error handling test ---")

    import agentpulse_processor as proc
    proc.supabase = sb

    original_url = proc.THOUGHT_LEADER_FEEDS['swyx']['url']
    proc.THOUGHT_LEADER_FEEDS['swyx']['url'] = 'https://invalid-url-that-does-not-exist.example.com/feed.xml'

    try:
        result = proc.scrape_thought_leaders()
        feeds_ok = result.get('feeds_scraped', 0)
        swyx_result = result.get('results', {}).get('swyx', {})
        swyx_failed = isinstance(swyx_result, dict) and 'error' in swyx_result

        reachable_without_swyx = sum(
            1 for k, v in result.get('results', {}).items()
            if k != 'swyx' and (isinstance(v, int) or (isinstance(v, dict) and 'error' not in v))
        )

        print(f"  Feeds scraped: {feeds_ok}/{len(EXPECTED_SOURCES)}")
        print(f"  Swyx (bad URL) failed: {swyx_failed}")
        print(f"  Other reachable feeds: {reachable_without_swyx}")

        pipeline_survived = feeds_ok >= 1
        swyx_isolated = swyx_failed or (isinstance(swyx_result, int) and swyx_result == 0)

        status = 'PASS' if pipeline_survived and swyx_isolated else 'FAIL'
        print(f"  Pipeline survived bad feed: {pipeline_survived}")
        print(f"  Bad feed isolated: {swyx_isolated}")
        print(f"  Error handling: {status}")
    finally:
        proc.THOUGHT_LEADER_FEEDS['swyx']['url'] = original_url

    return status


if __name__ == '__main__':
    print("\n=== TEST 1A: Thought Leader Source Ingestion ===\n")

    source_results = test_ingestion()
    dual_status = test_dual_routing()
    dedup_status = test_dedup()
    error_status = test_error_handling()

    print("\n=== SUMMARY ===")
    print(f"\n  {'Source':<35} {'Items':>5}  Status")
    print(f"  {'-'*35} {'-'*5}  {'-'*6}")
    for fk, r in source_results.items():
        print(f"  {r['name']:<35} {r['count']:>5}  {r['status']}")

    print(f"\n  Dual routing test:    {dual_status}")
    print(f"  Dedup test:           {dedup_status}")
    print(f"  Error handling test:  {error_status}")

    pass_count = sum(1 for r in source_results.values() if r['status'] == 'PASS')
    warn_count = sum(1 for r in source_results.values() if r['status'].startswith('WARN'))
    fail_count = sum(1 for r in source_results.values() if r['status'] == 'FAIL')

    infra_pass = dual_status == 'PASS' and dedup_status == 'PASS' and error_status == 'PASS'
    code_ok = pass_count >= 2 and fail_count == 0 and infra_pass

    print(f"\n  Sources: {pass_count} PASS, {warn_count} WARN (network), {fail_count} FAIL")
    print(f"  Overall: {'ALL CODE TESTS PASS' if code_ok else 'SOME FAILURES'}")
    if warn_count > 0:
        print(f"  Note: {warn_count} feeds unreachable from this network — test on server for full coverage")
    print()
    sys.exit(0 if code_ok else 1)
