#!/usr/bin/env python3
"""
INTEGRATION SMOKE TEST: Full Phase 1
Quick check that all Phase 1 pieces connect. NOT a full newsletter generation.
"""

import os
import sys
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client
import anthropic

env_path = Path(__file__).resolve().parent.parent / 'config' / '.env'
load_dotenv(env_path)

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("FATAL: SUPABASE_URL or SUPABASE_KEY not set")
    sys.exit(1)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

RESEARCH_PROMPT = (Path(__file__).resolve().parent.parent / 'templates' / 'research' / 'IDENTITY.md').read_text(encoding='utf-8')

results = {}
errors = {}


def check_source_ingestion():
    """1. Check thought_leader sources ingested recently."""
    print("--- 1. Source Ingestion ---")

    day_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    recent = sb.table('source_posts')\
        .select('source', count='exact')\
        .like('source', 'thought_leader_%')\
        .gte('scraped_at', day_ago)\
        .execute()
    recent_count = recent.count or 0

    weekly = sb.table('source_posts')\
        .select('source')\
        .like('source', 'thought_leader_%')\
        .gte('scraped_at', week_ago)\
        .execute()

    by_source = {}
    for p in (weekly.data or []):
        src = p.get('source', '?')
        by_source[src] = by_source.get(src, 0) + 1

    print(f"  Last 24h: {recent_count} items")
    print(f"  Last 7d by source:")
    for src, count in sorted(by_source.items()):
        label = src.replace('thought_leader_', '')
        print(f"    {label}: {count}")

    total_sources = len(by_source)
    total_items = sum(by_source.values())

    if total_items == 0:
        results['ingestion'] = 'FAIL'
        errors['ingestion'] = 'No thought_leader items found in last 7 days'
        print(f"  FAIL: no items found")
    elif total_sources < 2:
        results['ingestion'] = 'WARN'
        errors['ingestion'] = f'Only {total_sources} sources have data (some feeds unreachable from this network)'
        print(f"  WARN: only {total_sources} sources ({total_items} total items)")
    else:
        results['ingestion'] = 'PASS'
        print(f"  PASS: {total_sources} sources, {total_items} items")


def check_analyst_awareness():
    """2. Check Analyst can see thought_leader items with correct weighting.
    
    The real Analyst does a SEPARATE query for thought_leader content
    (source LIKE 'thought_leader_%'), not a general score-sorted scan.
    We replicate both query paths here.
    """
    print("\n--- 2. Analyst Awareness ---")

    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    # Path A: Analyst's dedicated thought_leader query (as in prepare_analysis_package)
    tl_posts = sb.table('source_posts')\
        .select('source, source_tier, score')\
        .like('source', 'thought_leader_%')\
        .gte('scraped_at', week_ago)\
        .order('scraped_at', desc=True)\
        .limit(20)\
        .execute()
    tl_count = len(tl_posts.data or [])

    # Path B: General multi-source scan (thought leaders mixed in)
    all_posts = sb.table('source_posts')\
        .select('source, source_tier, score')\
        .gte('scraped_at', week_ago)\
        .limit(500)\
        .execute()
    tl_in_general = [p for p in (all_posts.data or []) if str(p.get('source', '')).startswith('thought_leader_')]

    print(f"  Path A (dedicated TL query): {tl_count} items")
    print(f"  Path B (general scan, 500 limit): {len(all_posts.data or [])} total, {len(tl_in_general)} TL")

    if tl_count == 0:
        results['analyst'] = 'FAIL'
        errors['analyst'] = 'No thought_leader items found via dedicated query'
        print(f"  FAIL: thought_leader items not visible")
        return

    tiers = [p.get('source_tier') for p in (tl_posts.data or [])]
    scores = [p.get('score') for p in (tl_posts.data or [])]
    tier_ok = all(t == 2 for t in tiers)
    score_ok = all(s is not None and s >= 1 for s in scores)

    print(f"  Tiers: {set(tiers)} (expect {{2}})")
    print(f"  Score range: {min(scores)}-{max(scores)} (expect >= 1)")

    if tier_ok and score_ok:
        results['analyst'] = 'PASS'
        print(f"  PASS: {tl_count} items with tier=2, score >= 1")
    else:
        results['analyst'] = 'FAIL'
        errors['analyst'] = f'Tier ok: {tier_ok}, Score ok: {score_ok}'
        print(f"  FAIL: weighting incorrect")


def check_schema_readiness():
    """3. Insert and delete test rows in new tables."""
    print("\n--- 3. Schema Readiness ---")

    table_results = {}

    try:
        rq = sb.table('research_queue').insert({
            'topic_id': 'smoke-test', 'topic_name': 'Smoke Test',
            'priority_score': 0.1, 'status': 'queued', 'issue_number': 9999,
        }).execute()
        rq_id = rq.data[0]['id']
        sb.table('research_queue').delete().eq('id', rq_id).execute()
        table_results['research_queue'] = 'OK'
    except Exception as e:
        table_results['research_queue'] = f'ERROR: {e}'

    try:
        rq2 = sb.table('research_queue').insert({
            'topic_id': 'smoke-test-sh', 'topic_name': 'SH Test',
            'priority_score': 0.1, 'status': 'queued', 'issue_number': 9999,
        }).execute()
        rq2_id = rq2.data[0]['id']

        sh = sb.table('spotlight_history').insert({
            'research_queue_id': rq2_id,
            'topic_id': 'smoke-test-sh', 'topic_name': 'SH Test',
            'issue_number': 9999, 'thesis': 'T', 'evidence': 'E',
            'counter_argument': 'C', 'prediction': 'P', 'full_output': 'F',
        }).execute()
        sh_id = sh.data[0]['id']
        sb.table('spotlight_history').delete().eq('id', sh_id).execute()
        sb.table('research_queue').delete().eq('id', rq2_id).execute()
        table_results['spotlight_history'] = 'OK'
    except Exception as e:
        table_results['spotlight_history'] = f'ERROR: {e}'

    try:
        pred = sb.table('predictions').insert({
            'topic_id': 'smoke-test-pred',
            'prediction_text': 'Smoke test prediction',
            'issue_number': 9999, 'status': 'open',
        }).execute()
        pred_id = pred.data[0]['id']
        sb.table('predictions').delete().eq('id', pred_id).execute()
        table_results['predictions'] = 'OK'
    except Exception as e:
        table_results['predictions'] = f'ERROR: {e}'

    all_ok = all(v == 'OK' for v in table_results.values())
    for table, status in table_results.items():
        print(f"  {table}: {status}")

    if all_ok:
        results['schema'] = 'PASS'
        print(f"  PASS: all tables operational")
    else:
        results['schema'] = 'FAIL'
        errors['schema'] = '; '.join(f'{t}: {s}' for t, s in table_results.items() if s != 'OK')
        print(f"  FAIL: see errors above")


def check_radar_generation():
    """4. Query emerging topics and generate Radar."""
    print("\n--- 4. Radar Generation ---")

    te = sb.table('topic_evolution').select('*').order('last_updated', desc=True).limit(30).execute()
    topics = te.data or []

    if not topics:
        clusters = sb.table('problem_clusters')\
            .select('theme, opportunity_score')\
            .order('opportunity_score', desc=True)\
            .limit(10)\
            .execute()
        topics = []
        for i, c in enumerate(clusters.data or []):
            topics.append({
                'topic_key': c.get('theme', '').lower().replace(' ', '_'),
                'current_stage': 'emerging' if i < 5 else 'debating',
                'snapshots': [{'mentions': int(c.get('opportunity_score', 0.5) * 10)}],
                '_display_name': c.get('theme', ''),
            })
        print(f"  topic_evolution empty; synthesized {len(topics)} from problem_clusters")

    emerging = [t for t in topics if t.get('current_stage') == 'emerging']
    print(f"  Emerging topics: {len(emerging)}")

    if not emerging:
        results['radar'] = 'PASS'
        print(f"  PASS: no emerging topics, radar correctly skipped")
        return

    candidates = emerging[:4]
    names = [c.get('_display_name') or c.get('topic_key', '?').replace('_', ' ').title() for c in candidates]

    if not claude:
        results['radar'] = 'WARN'
        errors['radar'] = 'No ANTHROPIC_API_KEY for LLM generation'
        print(f"  WARN: skipping LLM call (no API key)")
        return

    prompt = f"""Write "On Our Radar" items. For each topic, write exactly: **Topic Name** -- one punchy sentence (under 30 words).

Topics: {', '.join(names)}

Respond with ONLY the formatted items, one per line."""

    try:
        resp = claude.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        radar_text = resp.content[0].text.strip()
        lines = [l for l in radar_text.split('\n') if l.strip()]
        print(f"  Generated {len(lines)} radar items")
        for l in lines:
            print(f"    {l.strip()[:100]}")

        if lines:
            results['radar'] = 'PASS'
            print(f"  PASS: radar generated with {len(lines)} items")
        else:
            results['radar'] = 'FAIL'
            errors['radar'] = 'LLM returned empty radar'
            print(f"  FAIL: empty response")
    except Exception as e:
        results['radar'] = 'FAIL'
        errors['radar'] = str(e)
        print(f"  FAIL: {e}")


def check_research_agent():
    """5. Build context from real data, call Research Agent, validate output."""
    print("\n--- 5. Research Agent Prompt ---")

    if not claude:
        results['research'] = 'WARN'
        errors['research'] = 'No ANTHROPIC_API_KEY'
        print(f"  WARN: skipping (no API key)")
        return

    clusters = sb.table('problem_clusters')\
        .select('theme, description, opportunity_score')\
        .order('opportunity_score', desc=True)\
        .limit(1)\
        .execute()

    if not clusters.data:
        results['research'] = 'FAIL'
        errors['research'] = 'No data in problem_clusters to build context'
        print(f"  FAIL: no data")
        return

    topic = clusters.data[0]
    topic_name = topic.get('theme', 'Unknown')
    search_terms = topic_name.lower().split()

    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    posts = sb.table('source_posts')\
        .select('title, body, source, source_url')\
        .gte('scraped_at', week_ago)\
        .order('score', desc=True)\
        .limit(100)\
        .execute()

    relevant = [p for p in (posts.data or []) if any(t in f"{p.get('title','')} {p.get('body','')}".lower() for t in search_terms)]
    if not relevant:
        relevant = (posts.data or [])[:15]

    context_lines = []
    for p in relevant[:15]:
        context_lines.append(f"[{p.get('source','?')}] {p.get('title','Untitled')}")
        body = (p.get('body') or '')[:300]
        if body:
            context_lines.append(body)

    print(f"  Topic: {topic_name}")
    print(f"  Context posts: {len(relevant)}")

    user_msg = f"""Analyze this topic for the AgentPulse Spotlight.

Topic: {topic_name}
Lifecycle Phase: debating
Velocity: 8 mentions
Source Diversity: {len(set(p.get('source','') for p in relevant))} sources

{chr(10).join(context_lines)}

Respond with valid JSON only."""

    try:
        resp = claude.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=1500,
            system=RESEARCH_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = resp.content[0].text
        print(f"  Response: {len(raw)} chars, {resp.usage.output_tokens} tokens")

        json_match = re.search(r'\{[\s\S]*\}', raw)
        if not json_match:
            results['research'] = 'FAIL'
            errors['research'] = 'No JSON in response'
            print(f"  FAIL: no JSON found")
            return

        data = json.loads(json_match.group())
        required = ['thesis', 'evidence', 'counter_argument', 'prediction', 'builder_implications']
        missing = [f for f in required if not data.get(f)]

        if missing:
            results['research'] = 'FAIL'
            errors['research'] = f'Missing fields: {missing}'
            print(f"  FAIL: missing {missing}")
        else:
            print(f"  Thesis: {data['thesis'][:100]}...")
            results['research'] = 'PASS'
            print(f"  PASS: all required fields present")

    except json.JSONDecodeError as e:
        results['research'] = 'FAIL'
        errors['research'] = f'Invalid JSON: {e}'
        print(f"  FAIL: bad JSON: {e}")
    except Exception as e:
        results['research'] = 'FAIL'
        errors['research'] = str(e)
        print(f"  FAIL: {e}")


if __name__ == '__main__':
    print("\n=== PHASE 1 INTEGRATION SMOKE TEST ===\n")

    check_source_ingestion()
    check_analyst_awareness()
    check_schema_readiness()
    check_radar_generation()
    check_research_agent()

    print("\n" + "=" * 50)
    print("=== PHASE 1 INTEGRATION SMOKE TEST ===")
    print("=" * 50)

    labels = {
        'ingestion': 'Thought leader ingestion',
        'analyst': 'Analyst sees new sources',
        'schema': 'Schema operational',
        'radar': 'Radar generation',
        'research': 'Research Agent prompt',
    }

    all_pass = True
    for key, label in labels.items():
        status = results.get(key, 'NOT RUN')
        line = f"  {label + ':':<30} {status}"
        if key in errors:
            line += f"  ({errors[key]})"
        print(line)
        if status not in ('PASS', 'WARN'):
            all_pass = False

    ready = all_pass
    print(f"\n  READY FOR PHASE 2: {'YES' if ready else 'NO'}")

    if not ready:
        print("\n  Fix the failures above before proceeding to Phase 2.")

    warn_count = sum(1 for v in results.values() if v == 'WARN')
    if warn_count:
        print(f"\n  Note: {warn_count} WARN results are acceptable for local testing.")
        print(f"  Re-run on server for full coverage.")

    print()
    sys.exit(0 if ready else 1)
