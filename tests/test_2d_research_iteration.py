#!/usr/bin/env python3
"""
TEST 2D: Research Agent — 5-Scenario Test Suite with Scoring and Prompt Iteration

Runs 5 distinct test scenarios through the Research Agent system prompt,
scores each output on 6 quality criteria, identifies weaknesses, and
saves all results for comparison across prompt iterations.

Usage:
    python tests/test_2d_research_iteration.py                   # run all 5 tests
    python tests/test_2d_research_iteration.py --test 1          # run single test
    python tests/test_2d_research_iteration.py --test 4          # synthesis mode
    python tests/test_2d_research_iteration.py --rerun 1         # rerun test 1 after prompt change
    python tests/test_2d_research_iteration.py --compare          # compare across iterations
"""

import os
import sys
import json
import re
import time
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client
import anthropic

env_path = Path(__file__).resolve().parent.parent / "config" / ".env"
load_dotenv(env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

PROMPT_PATH = Path(__file__).resolve().parent.parent / "templates" / "research" / "IDENTITY.md"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "tests" / "research_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "claude-sonnet-4-20250514"

HEDGE_PHRASES = [
    "it remains to be seen", "time will tell", "it could go either way",
    "it's worth noting", "in the rapidly evolving", "only time will tell",
    "the jury is still out", "remains unclear",
]
AI_VOICE_PHRASES = [
    "in the rapidly evolving landscape", "it's important to note",
    "as we navigate", "at the end of the day", "a myriad of",
    "this is an interesting development", "there are several factors",
    "in conclusion", "it is worth noting that", "needless to say",
    "paradigm shift", "game-changer", "transformative potential",
]
TENSION_WORDS = ["but", "however", "despite", "yet", "although", "—", "while", "even though", "whereas", "nevertheless"]
TIMEFRAME_PATTERNS = [
    r"\bmonths?\b", r"\bquarters?\b", r"\bQ[1-4]\b", r"\bweeks?\b",
    r"\b202[5-9]\b", r"\b2030\b", r"\bH[12]\b", r"\b\d+\s*days?\b",
    r"\byears?\b", r"\bby\s+(end|mid|early)\b",
]

sb = None
claude = None


def init_clients():
    global sb, claude
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("FATAL: SUPABASE_URL or SUPABASE_KEY not set")
        sys.exit(1)
    if not ANTHROPIC_API_KEY:
        print("FATAL: ANTHROPIC_API_KEY not set")
        sys.exit(1)
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def load_prompt():
    if not PROMPT_PATH.exists():
        print(f"FATAL: System prompt not found at {PROMPT_PATH}")
        sys.exit(1)
    return PROMPT_PATH.read_text(encoding="utf-8")


def get_prompt_version():
    """Hash first 500 chars + line count as a quick version fingerprint."""
    text = load_prompt()
    import hashlib
    h = hashlib.md5(text.encode()).hexdigest()[:8]
    return f"v{len(text.splitlines())}_{h}"


# ============================================================================
# Helpers: topic_evolution → problem_clusters fallback
# ============================================================================

def _topic_from_cluster(cluster):
    """Convert a problem_cluster row into a topic_evolution-shaped dict."""
    theme = cluster.get("theme", "unknown")
    return {
        "topic_key": theme.lower().replace(" ", "_").replace("-", "_"),
        "current_stage": "debating",
        "snapshots": [{"mentions": cluster.get("total_mentions", 1),
                       "sources": ["moltbook", "hackernews"]}],
        "_original_cluster": cluster,
    }


def _get_all_topics():
    """Return topic_evolution rows, falling back to problem_clusters."""
    te = sb.table("topic_evolution").select("*")\
        .order("last_updated", desc=True).limit(50).execute()
    if te.data:
        return te.data, "topic_evolution"

    clusters = sb.table("problem_clusters").select("*")\
        .order("opportunity_score", desc=True).limit(30).execute()
    if clusters.data:
        return [_topic_from_cluster(c) for c in clusters.data], "problem_clusters"

    return [], "none"


def _velocity(t):
    snaps = t.get("snapshots") or []
    return snaps[-1].get("mentions", 0) if snaps else 0


# ============================================================================
# Topic Pickers — one per test scenario
# ============================================================================

def pick_test1_debating():
    """Test 1: High-signal debating topic — the ideal happy path."""
    topics, source = _get_all_topics()

    debating = [t for t in topics if t.get("current_stage") in ("debating", "building")]
    debating.sort(key=_velocity, reverse=True)

    if debating:
        topic = debating[0]
        return topic, "spotlight", f"[{source}] Highest-velocity debating topic: {topic.get('topic_key')}"

    if topics:
        topics.sort(key=_velocity, reverse=True)
        return topics[0], "spotlight", f"[{source}] Highest-velocity topic: {topics[0].get('topic_key')}"

    return None, None, "No topics found"


def pick_test2_emerging_thin():
    """Test 2: Emerging topic with thin signal (few mentions)."""
    topics, source = _get_all_topics()

    emerging = [t for t in topics if t.get("current_stage") == "emerging"]
    thin = [t for t in emerging if 1 <= _velocity(t) <= 8]
    thin.sort(key=_velocity)

    if thin:
        topic = thin[0]
        return topic, "spotlight", f"[{source}] Thin-signal emerging ({_velocity(topic)} mentions): {topic.get('topic_key')}"

    if not emerging:
        all_sorted = sorted(topics, key=_velocity)
        low_signal = [t for t in all_sorted if _velocity(t) <= 5]
        if low_signal:
            topic = low_signal[0]
            return topic, "spotlight", f"[{source}] Low-signal fallback ({_velocity(topic)} mentions): {topic.get('topic_key')}"

    if topics:
        topics_sorted = sorted(topics, key=_velocity)
        return topics_sorted[0], "spotlight", f"[{source}] Lowest-velocity fallback: {topics_sorted[0].get('topic_key')}"

    return None, None, "No topics found"


def pick_test3_technical():
    """Test 3: Technical infrastructure topic (protocol/framework/tooling)."""
    tech_keywords = ["protocol", "framework", "sdk", "api", "tool", "infra", "runtime",
                     "mcp", "docker", "kubernetes", "vector", "rag", "embedding",
                     "fine-tun", "deploy", "serving", "orchestrat", "security",
                     "credential", "infrastructure"]

    topics, source = _get_all_topics()

    tech_topics = [t for t in topics if any(kw in t.get("topic_key", "").lower() for kw in tech_keywords)]
    tech_topics.sort(key=_velocity, reverse=True)

    if tech_topics:
        return tech_topics[0], "spotlight", f"[{source}] Technical topic: {tech_topics[0].get('topic_key')}"

    if len(topics) >= 3:
        return topics[2], "spotlight", f"[{source}] Fallback (3rd topic): {topics[2].get('topic_key')}"

    if topics:
        return topics[-1], "spotlight", f"[{source}] Fallback (last): {topics[-1].get('topic_key')}"

    return None, None, "No topics found"


def pick_test4_synthesis():
    """Test 4: Synthesis mode with 3 topics."""
    topics, source = _get_all_topics()

    if len(topics) < 3:
        return None, None, "Not enough topics for synthesis (need 3)"

    chosen = topics[:3]
    combined = {
        "topic_key": "+".join(t.get("topic_key", "?") for t in chosen),
        "current_stage": "synthesis",
        "snapshots": [{"mentions": sum(_velocity(t) for t in chosen)}],
        "_synthesis_topics": chosen,
    }
    names = [t.get("topic_key", "?").replace("_", " ").title() for t in chosen]
    return combined, "synthesis", f"[{source}] Synthesis of 3 topics: {', '.join(names)}"


def pick_test5_disagreement():
    """Test 5: Topic where thought leaders disagree, or diverse-source topic."""
    week_ago = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    tl_posts = sb.table("source_posts")\
        .select("title, body, source, source_url, tags")\
        .like("source", "thought_leader_%")\
        .gte("scraped_at", week_ago)\
        .order("scraped_at", desc=True).limit(200).execute()

    topic_sources = {}
    for p in (tl_posts.data or []):
        source_name = p.get("source", "")
        for tag in (p.get("tags") or []):
            tag_l = tag.lower()
            topic_sources.setdefault(tag_l, set()).add(source_name)

    multi = {k: v for k, v in topic_sources.items() if len(v) >= 2}
    if multi:
        best = max(multi, key=lambda k: len(multi[k]))
        topics, source = _get_all_topics()
        for t in topics:
            if best in t.get("topic_key", "").lower():
                return t, "spotlight", f"[{source}] Multi-TL topic '{best}' ({len(multi[best])} TLs): {t.get('topic_key')}"

    topics, source = _get_all_topics()
    if len(topics) >= 5:
        return topics[4], "spotlight", f"[{source}] Fallback (5th topic): {topics[4].get('topic_key')}"
    elif topics:
        return topics[-1], "spotlight", f"[{source}] Fallback (last): {topics[-1].get('topic_key')}"

    return None, None, "No topics available"


PICKERS = {
    1: ("High-signal debating topic", pick_test1_debating),
    2: ("Emerging topic with thin signal", pick_test2_emerging_thin),
    3: ("Technical infrastructure topic", pick_test3_technical),
    4: ("Synthesis mode (3 topics)", pick_test4_synthesis),
    5: ("Thought leader disagreement", pick_test5_disagreement),
}


# ============================================================================
# Context Building
# ============================================================================

def gather_sources(topic, mode):
    """Build context string from real source_posts data."""
    if mode == "synthesis" and topic.get("_synthesis_topics"):
        return _gather_synthesis_sources(topic)

    topic_key = topic.get("topic_key", "")
    search_terms = [w for w in topic_key.replace("_", " ").split() if len(w) >= 3]

    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    two_weeks = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()

    general = sb.table("source_posts")\
        .select("title, body, source, source_url, score, tags")\
        .gte("scraped_at", week_ago)\
        .order("score", desc=True).limit(200).execute()

    general_rel = []
    for p in (general.data or []):
        text = f"{p.get('title', '')} {p.get('body', '')}".lower()
        if any(t in text for t in search_terms):
            if not str(p.get("source", "")).startswith("thought_leader_"):
                general_rel.append(p)

    tl = sb.table("source_posts")\
        .select("title, body, source, source_url, score, tags, metadata")\
        .like("source", "thought_leader_%")\
        .gte("scraped_at", two_weeks)\
        .order("scraped_at", desc=True).limit(100).execute()

    tl_rel = []
    for p in (tl.data or []):
        text = f"{p.get('title', '')} {p.get('body', '')}".lower()
        if any(t in text for t in search_terms):
            tl_rel.append(p)

    if not general_rel and not tl_rel:
        general_rel = (general.data or [])[:15]
        tl_rel = (tl.data or [])[:10]

    context = _format_section("GENERAL SOURCES", general_rel[:20])
    context += _format_section("THOUGHT LEADER SOURCES (Tier 1)", tl_rel[:15])

    return context, len(general_rel), len(tl_rel)


def _gather_synthesis_sources(topic):
    """Build context for synthesis mode across 3 topics."""
    sub_topics = topic.get("_synthesis_topics", [])
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    all_posts = sb.table("source_posts")\
        .select("title, body, source, source_url, score")\
        .gte("scraped_at", week_ago)\
        .order("score", desc=True).limit(300).execute()

    sections = []
    total_gen = 0
    total_tl = 0

    for st in sub_topics:
        key = st.get("topic_key", "")
        terms = [w for w in key.replace("_", " ").split() if len(w) >= 3]
        matched = []
        for p in (all_posts.data or []):
            text = f"{p.get('title', '')} {p.get('body', '')}".lower()
            if any(t in text for t in terms):
                matched.append(p)

        name = key.replace("_", " ").title()
        phase = st.get("current_stage", "?")
        sections.append(f"\n=== TOPIC: {name} (phase: {phase}) — {len(matched)} sources ===")
        for p in matched[:10]:
            sections.append(f"\n[{p.get('source', '?')}] {p.get('title', 'Untitled')}")
            body = (p.get("body") or "")[:300]
            if body:
                sections.append(body)
        total_gen += len(matched)

    return "\n".join(sections), total_gen, total_tl


def _format_section(header, posts):
    if not posts:
        return f"\n=== {header} ===\n(no matching items)\n"
    lines = [f"\n=== {header} ({len(posts)} items) ==="]
    for p in posts:
        lines.append(f"\n[{p.get('source', '?')}] {p.get('title', 'Untitled')}")
        url = p.get("source_url", "")
        if url:
            lines.append(f"URL: {url}")
        body = (p.get("body") or "")[:400]
        if body:
            lines.append(body)
    return "\n".join(lines)


# ============================================================================
# LLM Call
# ============================================================================

def call_research_agent(topic, context_text, mode, gen_count, tl_count):
    """Send topic + context to Claude with the Research Agent system prompt."""
    system_prompt = load_prompt()
    topic_key = topic.get("topic_key", "unknown")
    topic_name = topic_key.replace("_", " ").title()
    phase = topic.get("current_stage", "unknown")
    snaps = topic.get("snapshots") or []
    mentions = snaps[-1].get("mentions", 0) if snaps else 0

    if mode == "synthesis":
        sub = topic.get("_synthesis_topics", [])
        sub_names = [t.get("topic_key", "?").replace("_", " ").title() for t in sub]
        user_msg = f"""Analyze these related topics for a SYNTHESIS Spotlight.

Topics: {', '.join(sub_names)}
Mode: synthesis
Combined mentions: {mentions}
General sources: {gen_count}
Thought leader sources: {tl_count}

{context_text}

Respond with valid JSON only, following the output format in your instructions. Set mode to "synthesis"."""
    else:
        user_msg = f"""Analyze this topic for the AgentPulse Spotlight section.

Topic: {topic_name}
Lifecycle Phase: {phase}
Velocity: {mentions} mentions
Source Diversity: {gen_count + tl_count} sources ({gen_count} general, {tl_count} thought leader)

{context_text}

Respond with valid JSON only, following the output format in your instructions."""

    start = time.time()
    response = claude.messages.create(
        model=MODEL,
        max_tokens=2500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_msg}],
    )
    elapsed = time.time() - start

    raw = response.content[0].text
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "elapsed_seconds": round(elapsed, 1),
        "model": MODEL,
    }
    return raw, usage


# ============================================================================
# Parsing and Scoring
# ============================================================================

def parse_output(raw_text):
    json_match = re.search(r"\{[\s\S]*\}", raw_text)
    if not json_match:
        return None
    try:
        return json.loads(json_match.group())
    except json.JSONDecodeError:
        return None


def score_output(data, mode="spotlight"):
    """Score the output on 6 criteria, each 1-5. Returns dict of scores + details."""
    scores = {}

    # 1. Thesis Test — specific enough to be wrong?
    thesis = data.get("thesis", "")
    s1 = 1
    details1 = []
    if thesis:
        has_tension = any(w in thesis.lower() for w in TENSION_WORDS)
        sentence_count = thesis.count(".") + thesis.count("!") + thesis.count("?")
        word_count = len(thesis.split())
        if has_tension:
            s1 += 2
        else:
            details1.append("no tension word")
        if word_count <= 40:
            s1 += 1
            details1.append(f"concise ({word_count} words)")
        else:
            details1.append(f"too long ({word_count} words)")
        if sentence_count <= 2:
            s1 += 1
        else:
            details1.append(f"multi-sentence ({sentence_count})")
    else:
        details1.append("MISSING")
    scores["thesis_quality"] = (min(s1, 5), details1)

    # 2. Prediction Test — specific and falsifiable?
    prediction = data.get("prediction", "")
    s2 = 1
    details2 = []
    if prediction:
        has_time = any(re.search(p, prediction, re.IGNORECASE) for p in TIMEFRAME_PATTERNS)
        has_number = bool(re.search(r"\d+", prediction))
        has_named = bool(re.search(r"[A-Z][a-z]+(?:\s[A-Z][a-z]+)*", prediction))
        vague = any(v in prediction.lower() for v in [
            "will continue", "is likely to", "will probably", "might see",
            "could potentially", "is expected to grow",
        ])
        if has_time:
            s2 += 1
            details2.append("has timeframe")
        else:
            details2.append("no timeframe")
        if has_number:
            s2 += 1
            details2.append("has number")
        if has_named:
            s2 += 1
        if not vague:
            s2 += 1
        else:
            details2.append("vague language detected")
    else:
        details2.append("MISSING")
    scores["prediction_specificity"] = (min(s2, 5), details2)

    # 3. Voice Test — analyst vs language model?
    all_text = " ".join([
        data.get("thesis", ""), data.get("evidence", ""),
        data.get("counter_argument", ""), data.get("prediction", ""),
        data.get("builder_implications", ""),
    ]).lower()

    s3 = 5
    details3 = []
    found_hedge = [h for h in HEDGE_PHRASES if h in all_text]
    found_ai = [a for a in AI_VOICE_PHRASES if a in all_text]
    has_bullets = bool(re.search(r"(?:^|\n)\s*[-*•]\s", all_text))
    if found_hedge:
        s3 -= len(found_hedge)
        details3.append(f"hedge: {found_hedge}")
    if found_ai:
        s3 -= len(found_ai)
        details3.append(f"ai_voice: {found_ai}")
    if has_bullets:
        s3 -= 1
        details3.append("bullet points found")
    if not details3:
        details3.append("clean voice")
    scores["voice_quality"] = (max(s3, 1), details3)

    # 4. Counter-Argument Test — real or performative?
    counter = data.get("counter_argument", "")
    s4 = 1
    details4 = []
    if counter:
        word_count = len(counter.split())
        if word_count >= 80:
            s4 += 2
            details4.append(f"substantive ({word_count} words)")
        elif word_count >= 50:
            s4 += 1
            details4.append(f"adequate ({word_count} words)")
        else:
            details4.append(f"thin ({word_count} words)")

        strawman_signals = ["some might argue", "critics may say", "skeptics point out",
                            "one could argue", "some people think"]
        is_strawman = any(s in counter.lower() for s in strawman_signals)
        if not is_strawman:
            s4 += 1
            details4.append("not strawman")
        else:
            details4.append("possible strawman framing")

        has_specifics = bool(re.search(r"[A-Z][a-z]+", counter)) and len(counter) > 100
        if has_specifics:
            s4 += 1
    else:
        details4.append("MISSING")
    scores["counter_argument_quality"] = (min(s4, 5), details4)

    # 5. Evidence Quality — woven prose vs list?
    evidence = data.get("evidence", "")
    s5 = 1
    details5 = []
    if evidence:
        word_count = len(evidence.split())
        if word_count >= 200:
            s5 += 1
            details5.append(f"substantial ({word_count} words)")
        elif word_count >= 100:
            details5.append(f"adequate ({word_count} words)")
        else:
            details5.append(f"thin ({word_count} words)")

        has_bullets_ev = bool(re.search(r"(?:^|\n)\s*[-*•]\s", evidence))
        if not has_bullets_ev:
            s5 += 1
            details5.append("prose format")
        else:
            details5.append("uses bullet points")

        source_refs = len(re.findall(r"(?:according to|per|from|at|via|reported by|wrote|said|argues)", evidence.lower()))
        if source_refs >= 3:
            s5 += 2
            details5.append(f"{source_refs} source references")
        elif source_refs >= 1:
            s5 += 1
            details5.append(f"{source_refs} source reference(s)")
        else:
            details5.append("no source references in prose")
    else:
        details5.append("MISSING")
    scores["evidence_quality"] = (min(s5, 5), details5)

    # 6. Builder Implications — actionable?
    builder = data.get("builder_implications", "")
    s6 = 1
    details6 = []
    if builder:
        word_count = len(builder.split())
        if word_count >= 60:
            s6 += 1
        elif word_count < 30:
            details6.append(f"too short ({word_count} words)")

        action_words = ["should", "consider", "build", "avoid", "invest", "prepare",
                        "start", "stop", "watch", "test", "evaluate", "adopt", "migrate"]
        action_count = sum(1 for w in action_words if w in builder.lower())
        if action_count >= 2:
            s6 += 2
            details6.append(f"{action_count} action words")
        elif action_count >= 1:
            s6 += 1
            details6.append(f"{action_count} action word(s)")
        else:
            details6.append("no action language")

        if not any(v in builder.lower() for v in ["theoretical", "it remains", "time will tell"]):
            s6 += 1
    else:
        details6.append("MISSING")
    scores["builder_actionability"] = (min(s6, 5), details6)

    total = sum(s for s, _ in scores.values())
    max_total = len(scores) * 5

    return {
        "scores": {k: v[0] for k, v in scores.items()},
        "details": {k: v[1] for k, v in scores.items()},
        "total": total,
        "max": max_total,
        "pct": round(total / max_total * 100, 1),
        "weakest": min(scores, key=lambda k: scores[k][0]),
    }


# ============================================================================
# Single Test Runner
# ============================================================================

def run_test(test_num):
    """Run a single test scenario. Returns result dict."""
    if test_num not in PICKERS:
        print(f"Unknown test number: {test_num}")
        return None

    label, picker = PICKERS[test_num]
    print(f"\n{'='*70}")
    print(f"  TEST {test_num}: {label}")
    print(f"{'='*70}")

    topic, mode, description = picker()
    if not topic:
        print(f"  SKIP: {description}")
        return {"test": test_num, "label": label, "skipped": True, "reason": description}

    print(f"  {description}")
    print(f"  Mode: {mode}")

    context_text, gen_count, tl_count = gather_sources(topic, mode)
    print(f"  Sources: {gen_count} general, {tl_count} thought leader")
    print(f"  Context: {len(context_text)} chars")

    if len(context_text) < 200:
        print("  WARNING: Very little context available")

    print(f"  Calling {MODEL}...")
    raw_text, usage = call_research_agent(topic, context_text, mode, gen_count, tl_count)
    print(f"  Response: {len(raw_text)} chars, {usage['input_tokens']}+{usage['output_tokens']} tokens, {usage['elapsed_seconds']}s")

    data = parse_output(raw_text)
    if not data:
        print("  FATAL: Could not parse JSON from response")
        return {
            "test": test_num, "label": label, "skipped": False,
            "parse_error": True, "raw_text": raw_text[:500],
        }

    scoring = score_output(data, mode)

    print(f"\n  --- OUTPUT ---")
    print(f"  THESIS: {data.get('thesis', 'MISSING')}")
    print(f"  PREDICTION: {data.get('prediction', 'MISSING')}")
    print(f"  MODE: {data.get('mode', '?')}")
    print(f"  KEY SOURCES: {len(data.get('key_sources', []))}")

    print(f"\n  --- SCORES ({scoring['total']}/{scoring['max']} = {scoring['pct']}%) ---")
    for criterion, score in scoring["scores"].items():
        details = scoring["details"].get(criterion, [])
        bar = "#" * score + "." * (5 - score)
        detail_str = f"  ({'; '.join(str(d) for d in details)})" if details else ""
        print(f"  {criterion:<28} [{bar}] {score}/5{detail_str}")

    print(f"\n  Weakest area: {scoring['weakest']}")

    return {
        "test": test_num,
        "label": label,
        "topic_key": topic.get("topic_key", "?"),
        "mode": mode,
        "description": description,
        "sources": {"general": gen_count, "thought_leader": tl_count},
        "usage": usage,
        "output": data,
        "scoring": scoring,
        "prompt_version": get_prompt_version(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================================
# Result Persistence
# ============================================================================

def save_result(result):
    """Save a single test result to disk."""
    pv = result.get("prompt_version", "unknown")
    test_num = result.get("test", 0)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"test{test_num}_{pv}_{ts}.json"
    path = RESULTS_DIR / filename
    path.write_text(json.dumps(result, indent=2, default=str))
    print(f"  Result saved: {filename}")
    return path


def save_run_summary(results):
    """Save a summary of the full run."""
    pv = results[0].get("prompt_version", "unknown") if results else "unknown"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    summary = {
        "prompt_version": pv,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tests_run": len(results),
        "tests_passed": sum(1 for r in results if not r.get("skipped") and not r.get("parse_error")),
        "results": [],
    }

    for r in results:
        if r.get("skipped") or r.get("parse_error"):
            summary["results"].append({"test": r["test"], "status": "skipped" if r.get("skipped") else "parse_error"})
            continue
        s = r.get("scoring", {})
        summary["results"].append({
            "test": r["test"],
            "label": r.get("label"),
            "topic": r.get("topic_key"),
            "total_score": s.get("total"),
            "pct": s.get("pct"),
            "weakest": s.get("weakest"),
        })

    valid = [r for r in results if r.get("scoring")]
    if valid:
        avg_pct = sum(r["scoring"]["pct"] for r in valid) / len(valid)
        summary["average_score_pct"] = round(avg_pct, 1)

        all_weakest = [r["scoring"]["weakest"] for r in valid]
        from collections import Counter
        weakest_counts = Counter(all_weakest)
        summary["most_common_weakness"] = weakest_counts.most_common(1)[0][0]

        best = max(valid, key=lambda r: r["scoring"]["pct"])
        summary["best_test"] = {"test": best["test"], "pct": best["scoring"]["pct"]}

    filename = f"run_summary_{pv}_{ts}.json"
    path = RESULTS_DIR / filename
    path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nRun summary saved: {filename}")

    # Also save the best output as benchmark if score >= 70%
    if valid:
        best = max(valid, key=lambda r: r["scoring"]["pct"])
        if best["scoring"]["pct"] >= 70:
            bench_path = RESULTS_DIR / "benchmark_best_output.json"
            bench_path.write_text(json.dumps({
                "prompt_version": pv,
                "test": best["test"],
                "topic": best.get("topic_key"),
                "score_pct": best["scoring"]["pct"],
                "output": best.get("output"),
                "scoring": best.get("scoring"),
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2, default=str))
            print(f"Benchmark saved: benchmark_best_output.json (score: {best['scoring']['pct']}%)")

    return summary


def compare_runs():
    """Compare results across prompt iterations."""
    summaries = sorted(RESULTS_DIR.glob("run_summary_*.json"))
    if not summaries:
        print("No run summaries found. Run tests first.")
        return

    print(f"\n{'='*70}")
    print("  PROMPT ITERATION COMPARISON")
    print(f"{'='*70}")
    print(f"  {'Version':<20} {'Avg%':>6} {'Tests':>6} {'Weakest':<28}")
    print(f"  {'-'*20} {'-'*6} {'-'*6} {'-'*28}")

    for sp in summaries:
        data = json.loads(sp.read_text())
        pv = data.get("prompt_version", "?")
        avg = data.get("average_score_pct", 0)
        tests = data.get("tests_run", 0)
        weak = data.get("most_common_weakness", "?")
        print(f"  {pv:<20} {avg:>5.1f}% {tests:>6} {weak:<28}")

    print()


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Research Agent 5-Scenario Test Suite")
    parser.add_argument("--test", type=int, help="Run a single test (1-5)")
    parser.add_argument("--rerun", type=int, help="Rerun a specific test after prompt change")
    parser.add_argument("--compare", action="store_true", help="Compare results across prompt versions")
    args = parser.parse_args()

    if args.compare:
        compare_runs()
        return

    init_clients()
    pv = get_prompt_version()
    print(f"Prompt version: {pv}")
    print(f"Results dir: {RESULTS_DIR}")

    if args.test or args.rerun:
        test_num = args.test or args.rerun
        result = run_test(test_num)
        if result:
            save_result(result)
        return

    # Run all 5 tests
    print(f"\n{'#'*70}")
    print(f"  FULL TEST SUITE — 5 Scenarios")
    print(f"  Prompt: {pv}")
    print(f"{'#'*70}")

    results = []
    for test_num in range(1, 6):
        result = run_test(test_num)
        if result:
            save_result(result)
            results.append(result)

    if results:
        summary = save_run_summary(results)

        print(f"\n{'='*70}")
        print(f"  FINAL SUMMARY")
        print(f"{'='*70}")
        print(f"  Prompt version: {pv}")
        print(f"  Tests run: {summary.get('tests_run')}")
        avg = summary.get("average_score_pct")
        if avg is not None:
            print(f"  Average score: {avg}%")
        weak = summary.get("most_common_weakness")
        if weak:
            print(f"  Most common weakness: {weak}")
        best = summary.get("best_test")
        if best:
            print(f"  Best test: #{best['test']} ({best['pct']}%)")

        print(f"\n  Next steps:")
        if avg and avg < 70:
            print(f"  1. Focus on: {weak}")
            print(f"  2. Edit {PROMPT_PATH.name} to address this weakness")
            print(f"  3. Rerun: python tests/test_2d_research_iteration.py --rerun <test_num>")
        else:
            print(f"  System prompt is performing well. Review outputs manually for voice quality.")


if __name__ == "__main__":
    main()
