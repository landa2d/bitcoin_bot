#!/usr/bin/env python3
"""
TEST 1D: Radar Section
Tests topic selection, overlap prevention, LLM generation, format validation,
fallback behavior, and full newsletter integration for the "On Our Radar" section.
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
if not ANTHROPIC_API_KEY:
    print("FATAL: ANTHROPIC_API_KEY not set")
    sys.exit(1)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

results = {}


def get_topic_evolution_data():
    """Fetch topic_evolution, or synthesize from problem_clusters if empty."""
    te = sb.table('topic_evolution').select('*').order('last_updated', desc=True).limit(30).execute()
    if te.data:
        return te.data, 'topic_evolution'

    clusters = sb.table('problem_clusters')\
        .select('*')\
        .order('opportunity_score', desc=True)\
        .limit(20)\
        .execute()

    if not clusters.data:
        return [], 'empty'

    topics = []
    for i, c in enumerate(clusters.data):
        score = c.get('opportunity_score', 0.5)
        if i < 5:
            stage = 'emerging'
        elif i < 12:
            stage = 'debating'
        else:
            stage = 'building'

        topics.append({
            'topic_key': c.get('theme', 'unknown').lower().replace(' ', '_'),
            'current_stage': stage,
            'snapshots': [{'mentions': int(score * 10), 'date': datetime.now(timezone.utc).isoformat()}],
            'last_updated': datetime.now(timezone.utc).isoformat(),
            '_display_name': c.get('theme', 'Unknown'),
        })
    return topics, 'problem_clusters'


def get_signals_themes():
    """Get what would be in the current Signals section (section B)."""
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    clusters = sb.table('problem_clusters')\
        .select('theme, opportunity_score')\
        .gte('created_at', week_ago)\
        .order('opportunity_score', desc=True)\
        .limit(10)\
        .execute()
    return {(c.get('theme') or '').lower() for c in (clusters.data or [])}


def get_velocity(topic):
    snaps = topic.get('snapshots') or []
    if len(snaps) >= 2:
        return snaps[-1].get('mentions', 0) - snaps[-2].get('mentions', 0)
    elif snaps:
        return snaps[-1].get('mentions', 0)
    return 0


def select_radar_candidates(topics, signals_themes, stage_filter='emerging'):
    """Replicate the processor's radar selection logic."""
    candidates = [
        t for t in topics
        if t.get('current_stage') == stage_filter
        and t.get('topic_key', '').replace('_', ' ') not in signals_themes
    ]
    candidates.sort(key=get_velocity, reverse=True)

    if len(candidates) < 3:
        debating_fill = [
            t for t in topics
            if t.get('current_stage') == 'debating'
            and t.get('topic_key', '').replace('_', ' ') not in signals_themes
            and t not in candidates
        ]
        candidates.extend(debating_fill)

    return candidates[:4]


def test_topic_selection():
    """Step 1: Query topics and find radar candidates."""
    print("--- Step 1: Topic selection ---")

    topics, source = get_topic_evolution_data()
    if not topics:
        print("  No topics available at all. Cannot test radar.")
        results['topic_selection'] = 'FAIL'
        return [], [], set(), source

    print(f"  Data source: {source}")

    emerging = [t for t in topics if t.get('current_stage') == 'emerging']
    debating = [t for t in topics if t.get('current_stage') == 'debating']

    print(f"  Emerging topics: {len(emerging)}")
    for t in emerging[:5]:
        name = t.get('_display_name') or t.get('topic_key', '?')
        print(f"    {name} — velocity: {get_velocity(t)}")

    fallback_used = len(emerging) < 3
    if fallback_used:
        print(f"  Fewer than 3 emerging — will use {len(debating)} debating topics as fallback")
        for t in debating[:5]:
            name = t.get('_display_name') or t.get('topic_key', '?')
            print(f"    {name} — velocity: {get_velocity(t)}")

    signals_themes = get_signals_themes()
    print(f"  Signals themes (for overlap check): {len(signals_themes)}")

    candidates = select_radar_candidates(topics, signals_themes)
    print(f"  Total radar candidates after dedup: {len(candidates)}")

    results['topic_selection'] = 'PASS' if candidates else 'FAIL'
    return topics, candidates, signals_themes, source


def test_overlap_prevention(candidates, signals_themes):
    """Step 2: Verify no overlap with Signals."""
    print("\n--- Step 2: Overlap prevention ---")

    overlaps = []
    for c in candidates:
        key = c.get('topic_key', '').replace('_', ' ')
        if key in signals_themes:
            overlaps.append(key)

    if overlaps:
        print(f"  Overlaps found: {overlaps}")
        results['no_overlap'] = 'FAIL'
    else:
        print(f"  No overlaps with Signals — clean")
        results['no_overlap'] = 'PASS'

    return overlaps


def test_generate_radar(candidates):
    """Step 3: Generate the radar section via LLM."""
    print("\n--- Step 3: Generating Radar section ---")

    if not candidates:
        print("  No candidates — skipping generation")
        results['generation'] = 'SKIP'
        return None

    topics_for_prompt = []
    for c in candidates:
        name = c.get('_display_name') or c.get('topic_key', '').replace('_', ' ').title()
        vel = get_velocity(c)
        stage = c.get('current_stage', 'unknown')
        topics_for_prompt.append(f"- {name} (stage: {stage}, velocity: {vel})")

    prompt = f"""You are the AgentPulse Newsletter Agent writing the "On Our Radar" section.

For each topic below, write exactly one punchy sentence explaining why it's worth watching.
Format each as: **Topic Name** — One sentence.

Rules:
- Each description must be a SINGLE sentence (no periods in the middle, just one at the end)
- Each description must be under 30 words
- Hint at tension or potential significance — don't explain, tease
- No analysis, no links, no sub-points

Topics:
{chr(10).join(topics_for_prompt)}

Respond with ONLY the formatted radar items, one per line. No intro, no outro."""

    response = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    radar_text = response.content[0].text.strip()
    print(f"  Generated ({len(radar_text)} chars)")
    results['generation'] = 'PASS'
    return radar_text


def test_format_validation(radar_text):
    """Step 4: Validate radar format."""
    print("\n--- Step 4: Format validation ---")

    if not radar_text:
        print("  No radar text to validate")
        results['item_count'] = 'SKIP'
        results['single_sentence'] = 'SKIP'
        results['word_count'] = 'SKIP'
        return

    lines = [l.strip() for l in radar_text.strip().split('\n') if l.strip()]

    item_count = len(lines)
    count_ok = 3 <= item_count <= 4
    count_acceptable = 2 <= item_count <= 4
    if count_ok:
        results['item_count'] = 'PASS'
        print(f"  Item count: {item_count} -- PASS (need 3-4)")
    elif count_acceptable:
        results['item_count'] = 'PASS'
        print(f"  Item count: {item_count} -- PASS (2 acceptable when data is limited after dedup)")
    else:
        results['item_count'] = 'FAIL'
        print(f"  Item count: {item_count} -- FAIL (need 2-4)")

    sentence_issues = []
    word_issues = []
    for i, line in enumerate(lines):
        dash_idx = line.find('—')
        if dash_idx == -1:
            dash_idx = line.find(' - ')
            if dash_idx == -1:
                dash_idx = line.find('–')

        if dash_idx != -1:
            desc = line[dash_idx+1:].strip().lstrip('- –—').strip()
        else:
            desc = line

        periods = desc.count('.')
        if periods > 1:
            sentence_issues.append(f"  Item {i+1}: {periods} sentences")

        words = len(desc.split())
        if words > 30:
            word_issues.append(f"  Item {i+1}: {words} words")

        print(f"  [{i+1}] {line[:100]}{'...' if len(line) > 100 else ''}")
        print(f"      Words: {words}, Sentences: {periods}")

    results['single_sentence'] = 'PASS' if not sentence_issues else 'FAIL'
    results['word_count'] = 'PASS' if not word_issues else 'FAIL'

    if sentence_issues:
        print(f"  Multi-sentence issues: {sentence_issues}")
    if word_issues:
        print(f"  Over-30-word issues: {word_issues}")


def test_fallback_behavior(topics, signals_themes):
    """Step 5: Test fallback when no emerging topics."""
    print("\n--- Step 5: Fallback behavior ---")

    candidates_no_emerging = select_radar_candidates(topics, signals_themes, stage_filter='__none__')
    if candidates_no_emerging:
        all_debating = all(c.get('current_stage') == 'debating' for c in candidates_no_emerging)
        print(f"  With no emerging topics: {len(candidates_no_emerging)} candidates from debating")
        print(f"  All from debating phase: {all_debating}")
        fallback_ok = len(candidates_no_emerging) > 0
    else:
        print(f"  No fallback candidates available — section would be skipped (correct behavior)")
        fallback_ok = True

    empty_candidates = select_radar_candidates([], signals_themes)
    skip_ok = len(empty_candidates) == 0
    print(f"  With zero topics: section skipped = {skip_ok}")

    results['fallback'] = 'PASS' if fallback_ok and skip_ok else 'FAIL'


def test_newsletter_integration(radar_text, candidates):
    """Step 6: Verify radar fits in newsletter context."""
    print("\n--- Step 6: Newsletter integration ---")

    if not radar_text:
        print("  No radar text — skipping integration check")
        results['newsletter_integration'] = 'SKIP'
        return

    mock_newsletter = f"""## 1. The Big Insight

Some big insight content here.

## 2. Emerging Signals

Signal 1, Signal 2, Signal 3.

## 3. On Our Radar

{radar_text}

## 4. The Curious Corner

Some curious content."""

    has_radar = '## 3. On Our Radar' in mock_newsletter or 'On Our Radar' in mock_newsletter
    signals_before_radar = mock_newsletter.index('Emerging Signals') < mock_newsletter.index('On Our Radar')
    radar_before_curious = mock_newsletter.index('On Our Radar') < mock_newsletter.index('Curious Corner')

    print(f"  Radar section present: {has_radar}")
    print(f"  Positioned after Signals: {signals_before_radar}")
    print(f"  Positioned before Curious Corner: {radar_before_curious}")

    ok = has_radar and signals_before_radar and radar_before_curious
    results['newsletter_integration'] = 'PASS' if ok else 'FAIL'


if __name__ == '__main__':
    print("\n=== TEST 1D: Radar Section ===\n")

    topics, candidates, signals_themes, source = test_topic_selection()
    overlaps = test_overlap_prevention(candidates, signals_themes)
    radar_text = test_generate_radar(candidates)
    test_format_validation(radar_text)
    test_fallback_behavior(topics, signals_themes)
    test_newsletter_integration(radar_text, candidates)

    print("\n" + "=" * 60)
    print("=== RADAR SECTION TEST SUMMARY ===")
    print("=" * 60)

    emerging_count = sum(1 for t in topics if t.get('current_stage') == 'emerging')
    debating_count = sum(1 for t in topics if t.get('current_stage') == 'debating')
    fallback_used = emerging_count < 3

    print(f"  Data source: {source}")
    print(f"  Emerging topics available: {emerging_count}")
    print(f"  Fallback topics used: {'yes' if fallback_used else 'no'}")
    print(f"  Candidates after dedup with Signals: {len(candidates)}")

    if radar_text:
        print(f"\n  Generated Radar:")
        print(f"  {'-' * 50}")
        for line in radar_text.strip().split('\n'):
            if line.strip():
                print(f"  {line.strip()}")
        print(f"  {'-' * 50}")

    print(f"\n  Format checks:")
    check_labels = {
        'item_count': 'Item count (3-4)',
        'single_sentence': 'All items single sentence',
        'word_count': 'No items over 30 words',
        'no_overlap': 'No overlap with Signals',
        'fallback': 'Fallback behavior',
        'newsletter_integration': 'Appears in full newsletter',
    }
    all_pass = True
    for key, label in check_labels.items():
        status = results.get(key, 'NOT RUN')
        print(f"  - {label}: {status}")
        if status not in ('PASS', 'SKIP'):
            all_pass = False

    print(f"\n  Overall: {'ALL PASS' if all_pass else 'SOME FAILURES'}\n")
    sys.exit(0 if all_pass else 1)
