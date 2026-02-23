#!/usr/bin/env python3
"""
TEST 1C: Research Agent Prompt Quality
Picks a real trending topic, builds context, calls Claude, and validates output quality.
Run once — do NOT iterate on the prompt.
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

SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / 'templates' / 'research' / 'IDENTITY.md'
SYSTEM_PROMPT = SYSTEM_PROMPT_PATH.read_text(encoding='utf-8')

HEDGE_PHRASES = [
    "it remains to be seen", "time will tell", "it could go either way",
    "it's worth noting", "in the rapidly evolving",
]
AI_VOICE_PHRASES = [
    "in the rapidly evolving landscape", "it's important to note",
    "as we navigate", "at the end of the day", "a myriad of",
]
TENSION_WORDS = ["but", "however", "despite", "yet", "although", "—", "while", "even though"]
TIMEFRAME_PATTERNS = [
    r'\bmonths?\b', r'\bquarters?\b', r'\bQ[1-4]\b', r'\bweeks?\b',
    r'\b202[5-9]\b', r'\b2030\b', r'\bH[12]\b', r'\b\d{1,2}/\d{4}\b',
    r'\b\d+\s*days?\b', r'\byears?\b',
]


def pick_topic():
    """Step 1: Pick the best topic from topic_evolution, or fall back to problem_clusters."""
    print("--- Step 1: Picking topic ---")

    result = sb.table('topic_evolution')\
        .select('*')\
        .order('last_updated', desc=True)\
        .limit(30)\
        .execute()

    topics = result.data or []

    if topics:
        def get_velocity(t):
            snaps = t.get('snapshots') or []
            if len(snaps) >= 2:
                return snaps[-1].get('mentions', 0) - snaps[-2].get('mentions', 0)
            elif snaps:
                return snaps[-1].get('mentions', 0)
            return 0

        preferred = [t for t in topics if t.get('current_stage') in ('debating', 'building')]
        preferred.sort(key=get_velocity, reverse=True)

        if preferred:
            topic = preferred[0]
            print(f"  Found preferred topic in '{topic.get('current_stage')}' phase")
        else:
            topics.sort(key=get_velocity, reverse=True)
            topic = topics[0]
            print(f"  No debating/building topics; using highest-velocity topic")

        velocity = get_velocity(topic)
        print(f"  Topic: {topic.get('topic_key')}")
        print(f"  Phase: {topic.get('current_stage')}")
        print(f"  Velocity: {velocity}")
        return topic, velocity

    print("  topic_evolution is empty — falling back to problem_clusters")
    clusters = sb.table('problem_clusters')\
        .select('*')\
        .order('opportunity_score', desc=True)\
        .limit(10)\
        .execute()

    if not clusters.data:
        print("  No data in problem_clusters either. Cannot proceed.")
        sys.exit(1)

    cluster = clusters.data[0]
    topic = {
        'topic_key': cluster.get('theme', 'unknown').lower().replace(' ', '_'),
        'current_stage': 'debating',
        'snapshots': [{'mentions': int((cluster.get('opportunity_score', 0.5)) * 10)}],
    }
    velocity = int((cluster.get('opportunity_score', 0.5)) * 10)
    print(f"  Topic (from clusters): {topic['topic_key']}")
    print(f"  Phase: {topic['current_stage']} (inferred)")
    print(f"  Score proxy: {velocity}")
    return topic, velocity


def build_context(topic):
    """Step 2: Build a realistic context payload."""
    print("\n--- Step 2: Building context payload ---")

    topic_key = topic.get('topic_key', '')
    search_terms = topic_key.replace('_', ' ').split()

    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()

    general_posts = sb.table('source_posts')\
        .select('title, body, source, source_url, score, tags')\
        .gte('scraped_at', week_ago)\
        .order('score', desc=True)\
        .limit(200)\
        .execute()

    general_relevant = []
    for p in (general_posts.data or []):
        text = f"{p.get('title', '')} {p.get('body', '')}".lower()
        if any(term.lower() in text for term in search_terms):
            if not str(p.get('source', '')).startswith('thought_leader_'):
                general_relevant.append(p)

    tl_posts = sb.table('source_posts')\
        .select('title, body, source, source_url, score, tags, metadata')\
        .like('source', 'thought_leader_%')\
        .gte('scraped_at', two_weeks_ago)\
        .order('scraped_at', desc=True)\
        .limit(100)\
        .execute()

    tl_relevant = []
    for p in (tl_posts.data or []):
        text = f"{p.get('title', '')} {p.get('body', '')}".lower()
        if any(term.lower() in text for term in search_terms):
            tl_relevant.append(p)

    print(f"  General sources matching: {len(general_relevant)}")
    print(f"  Thought leader sources matching: {len(tl_relevant)}")

    if not general_relevant and not tl_relevant:
        print("  WARNING: No matching sources found. Using broader data as fallback.")
        general_relevant = (general_posts.data or [])[:15]
        tl_relevant = (tl_posts.data or [])[:10]
        print(f"  Fallback: {len(general_relevant)} general, {len(tl_relevant)} thought leader")

    def format_posts(posts, label):
        lines = [f"\n=== {label} ({len(posts)} items) ==="]
        for p in posts[:20]:
            lines.append(f"\n[{p.get('source', '?')}] {p.get('title', 'Untitled')}")
            url = p.get('source_url', '')
            if url:
                lines.append(f"URL: {url}")
            body = (p.get('body') or '')[:400]
            if body:
                lines.append(body)
        return '\n'.join(lines)

    context_text = format_posts(general_relevant, "GENERAL SOURCES")
    context_text += format_posts(tl_relevant, "THOUGHT LEADER SOURCES")

    snaps = topic.get('snapshots') or []
    latest_snap = snaps[-1] if snaps else {}

    context_payload = {
        'topic_name': topic_key.replace('_', ' ').title(),
        'topic_id': topic_key,
        'lifecycle_phase': topic.get('current_stage', 'unknown'),
        'velocity': latest_snap.get('mentions', 0),
        'source_diversity': len(set(
            p.get('source', '') for p in general_relevant + tl_relevant
        )),
        'general_source_count': len(general_relevant),
        'thought_leader_source_count': len(tl_relevant),
        'context': context_text,
    }

    return context_payload, len(general_relevant), len(tl_relevant)


def call_research_agent(context_payload):
    """Step 3: Call Claude with the Research Agent system prompt."""
    print("\n--- Step 3: Calling Claude ---")

    user_message = f"""Analyze this topic for the AgentPulse Spotlight section.

Topic: {context_payload['topic_name']}
Lifecycle Phase: {context_payload['lifecycle_phase']}
Velocity: {context_payload['velocity']} mentions
Source Diversity: {context_payload['source_diversity']} distinct sources
General sources: {context_payload['general_source_count']}
Thought leader sources: {context_payload['thought_leader_source_count']}

{context_payload['context']}

Respond with valid JSON only, following the output format in your instructions."""

    response = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text
    print(f"  Response received ({len(raw_text)} chars)")
    print(f"  Tokens: {response.usage.input_tokens} in, {response.usage.output_tokens} out")

    return raw_text


def parse_response(raw_text):
    """Step 4: Parse JSON and validate structure."""
    print("\n--- Step 4: Parsing response ---")

    json_match = re.search(r'\{[\s\S]*\}', raw_text)
    if not json_match:
        print("  FATAL: No JSON object found in response")
        return None

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        print(f"  FATAL: Invalid JSON: {e}")
        return None

    print("  JSON parsed successfully")
    return data


def validate_structure(data):
    """Step 4 continued: Validate required fields."""
    issues = []

    thesis = data.get('thesis', '')
    if not thesis:
        issues.append("thesis missing")
    elif thesis.count('.') > 2:
        issues.append(f"thesis looks like a paragraph ({thesis.count('.')} sentences)")

    evidence = data.get('evidence', '')
    if not evidence:
        issues.append("evidence missing")
    elif len(evidence.split()) < 100:
        issues.append(f"evidence too short ({len(evidence.split())} words, need 100+)")

    counter = data.get('counter_argument', '')
    if not counter:
        issues.append("counter_argument missing")
    elif len(counter.split()) < 50:
        issues.append(f"counter_argument too short ({len(counter.split())} words, need 50+)")

    prediction = data.get('prediction', '')
    if not prediction:
        issues.append("prediction missing")
    else:
        has_timeframe = any(re.search(p, prediction, re.IGNORECASE) for p in TIMEFRAME_PATTERNS)
        if not has_timeframe:
            issues.append("prediction has no timeframe")

    builder = data.get('builder_implications', '')
    if not builder:
        issues.append("builder_implications missing")
    elif len(builder.split()) < 30:
        issues.append(f"builder_implications too short ({len(builder.split())} words, need 30+)")

    sources = data.get('key_sources', [])
    if not sources or len(sources) < 2:
        issues.append(f"key_sources has {len(sources)} URLs (need 2+)")

    return issues


def quality_checks(data):
    """Step 5: Automated quality checks."""
    results = {}

    thesis = data.get('thesis', '').lower()
    has_tension = any(w in thesis for w in TENSION_WORDS)
    results['thesis_tension'] = ('PASS' if has_tension else 'FAIL', [] if has_tension else ['No tension word found in thesis'])

    all_text = ' '.join([
        data.get('thesis', ''), data.get('evidence', ''),
        data.get('counter_argument', ''), data.get('prediction', ''),
        data.get('builder_implications', ''),
    ]).lower()

    found_hedges = [h for h in HEDGE_PHRASES if h in all_text]
    results['hedge_language'] = ('PASS' if not found_hedges else 'FAIL', found_hedges)

    found_ai = [a for a in AI_VOICE_PHRASES if a in all_text]
    results['ai_voice'] = ('PASS' if not found_ai else 'FAIL', found_ai)

    prediction = data.get('prediction', '')
    has_number = bool(re.search(r'\d+', prediction))
    has_named = bool(re.search(r'[A-Z][a-z]+(?:\s[A-Z][a-z]+)*', prediction))
    has_time = any(re.search(p, prediction, re.IGNORECASE) for p in TIMEFRAME_PATTERNS)
    specific = has_number or has_named or has_time
    results['prediction_specificity'] = ('PASS' if specific else 'FAIL', [])

    has_bullets = bool(re.search(r'(?:^|\n)\s*[-*•]\s', all_text)) or bool(re.search(r'(?:^|\n)\s*\d+[.)]\s', all_text))
    results['no_bullet_points'] = ('PASS' if not has_bullets else 'FAIL', ['Bullet points or numbered lists found'] if has_bullets else [])

    return results


if __name__ == '__main__':
    print("\n=== TEST 1C: Research Agent Prompt Quality ===\n")

    topic, velocity = pick_topic()
    context_payload, gen_count, tl_count = build_context(topic)
    raw_text = call_research_agent(context_payload)
    data = parse_response(raw_text)

    if not data:
        print("\nFATAL: Could not parse response. Raw text:")
        print(raw_text)
        sys.exit(1)

    struct_issues = validate_structure(data)
    checks = quality_checks(data)

    print("\n" + "=" * 60)
    print("=== RESEARCH AGENT TEST OUTPUT ===")
    print("=" * 60)
    print(f"Topic: {context_payload['topic_name']}")
    print(f"Phase: {context_payload['lifecycle_phase']}")
    print(f"Sources used: {gen_count} general, {tl_count} thought leader")
    print()

    print(f"THESIS: {data.get('thesis', 'MISSING')}")
    print()
    print(f"EVIDENCE: {data.get('evidence', 'MISSING')}")
    print()
    print(f"COUNTER-ARGUMENT: {data.get('counter_argument', 'MISSING')}")
    print()
    print(f"PREDICTION: {data.get('prediction', 'MISSING')}")
    print()
    print(f"BUILDER IMPLICATIONS: {data.get('builder_implications', 'MISSING')}")
    print()
    sources = data.get('key_sources', [])
    print(f"KEY SOURCES: ({len(sources)} URLs)")
    for s in sources:
        print(f"  - {s}")

    print()
    print("=" * 60)
    print("=== QUALITY CHECKS ===")
    print("=" * 60)

    struct_status = 'PASS' if not struct_issues else 'FAIL'
    print(f"  Structure:              {struct_status}", end='')
    if struct_issues:
        print(f" ({'; '.join(struct_issues)})")
    else:
        print()

    for check_name, (status, details) in checks.items():
        label = check_name.replace('_', ' ').title()
        print(f"  {label:<24} {status}", end='')
        if details:
            print(f" ({'; '.join(str(d) for d in details)})")
        else:
            print()

    print()
    print("=" * 60)
    print("=== MANUAL REVIEW NEEDED ===")
    print("=" * 60)
    print("Read the output above and ask yourself:")
    print("1. Would I forward this to a smart friend in AI?")
    print("2. Is the thesis specific enough to be wrong?")
    print("3. Does the counter-argument make me think 'huh, maybe they're wrong'?")
    print("4. Would a builder change their plans based on the implications?")
    print()

    all_pass = struct_status == 'PASS' and all(s == 'PASS' for s, _ in checks.values())
    print(f"Automated checks: {'ALL PASS' if all_pass else 'SOME FLAGS — review above'}")
    print()
