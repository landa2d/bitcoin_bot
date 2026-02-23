#!/usr/bin/env python3
"""
TEST 2D: Research Agent Output Quality Report

Evaluates whether the Research Agent produces genuinely interesting, opinionated
analysis across 5 different topic types. Prints ALL outputs in full for manual review.

Checks: Structure, Voice, Conviction, Sources, and Synthesis-specific validation.
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

# ============================================================================
# Constants
# ============================================================================

HEDGE_PHRASES = [
    "it remains to be seen", "time will tell", "it could go either way",
    "may or may not", "only time will tell", "the jury is still out",
]
AI_PHRASES = [
    "in the rapidly evolving landscape", "it's worth noting", "as we navigate",
    "at the end of the day", "a myriad of", "it's important to understand",
    "in conclusion", "there are several factors",
]
WEAK_OPENINGS = [
    "this is an interesting development", "there are several", "it's important to",
]
TENSION_WORDS = [
    "but", "however", "despite", "yet", "although", "while", "even though",
]
TIMEFRAME_PATTERNS = [
    r"\bQ[1-4]\b", r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b",
    r"\b202[5-9]\b", r"\b2030\b", r"\bby\s+(?:end|mid|early)\b",
    r"\bmonths?\b", r"\bquarters?\b", r"\bweeks?\b",
]

CLEANUP_IDS = {"topic_evolution": []}


# ============================================================================
# Init
# ============================================================================

def init():
    proc.init_clients()
    ra.supabase = proc.supabase

    from dotenv import dotenv_values
    vals = dotenv_values(env_path)
    import anthropic
    key = vals.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if key:
        ra.claude_client = anthropic.Anthropic(api_key=key)


def _velocity(t):
    snaps = t.get("snapshots") or []
    return snaps[-1].get("mentions", 0) if snaps else 0


def _sources_list(t):
    snaps = t.get("snapshots") or []
    return snaps[-1].get("sources", []) if snaps else []


def get_topics():
    te = proc.supabase.table("topic_evolution").select("*")\
        .order("last_updated", desc=True).limit(50).execute()
    if te.data and len(te.data) >= 3:
        return te.data, False

    clusters = proc.supabase.table("problem_clusters").select("*")\
        .order("opportunity_score", desc=True).limit(20).execute()

    topics = []
    for c in (clusters.data or []):
        theme = c.get("theme", "unknown")
        topics.append({
            "topic_key": theme.lower().replace(" ", "_").replace("-", "_"),
            "current_stage": "debating",
            "snapshots": [{"mentions": c.get("total_mentions", 3), "sources": ["hackernews", "moltbook"]}],
        })
    if topics:
        return topics, True

    synthetic = [
        {"topic_key": "agent_security_models", "current_stage": "debating",
         "snapshots": [{"mentions": 14, "sources": ["hackernews", "moltbook", "rss_a16z"]}]},
        {"topic_key": "mcp_protocol_governance", "current_stage": "building",
         "snapshots": [{"mentions": 9, "sources": ["hackernews", "github"]}]},
        {"topic_key": "local_model_deployment", "current_stage": "emerging",
         "snapshots": [{"mentions": 4, "sources": ["hackernews", "moltbook", "github"]}]},
        {"topic_key": "rag_pipeline_optimization", "current_stage": "mature",
         "snapshots": [{"mentions": 11, "sources": ["hackernews", "github"]}]},
        {"topic_key": "agent_payment_rails", "current_stage": "emerging",
         "snapshots": [{"mentions": 5, "sources": ["hackernews", "moltbook"]}]},
    ]
    inserted = []
    for t in synthetic:
        t["last_updated"] = datetime.now(timezone.utc).isoformat()
        r = proc.supabase.table("topic_evolution").insert(t).execute()
        if r.data:
            inserted.append(r.data[0])
            CLEANUP_IDS["topic_evolution"].append(r.data[0]["id"])
    return inserted or synthetic, True


# ============================================================================
# Topic Pickers (A-E)
# ============================================================================

def pick_A_debating(topics):
    """Highest velocity topic in debating phase."""
    debating = [t for t in topics if t.get("current_stage") in ("debating", "building")]
    debating.sort(key=_velocity, reverse=True)
    if debating:
        return debating[0]
    topics_sorted = sorted(topics, key=_velocity, reverse=True)
    return topics_sorted[0] if topics_sorted else None


def pick_B_emerging_thin(topics):
    """Emerging topic with fewest mentions (thin signal)."""
    emerging = [t for t in topics if t.get("current_stage") == "emerging"]
    emerging.sort(key=_velocity)
    if emerging:
        return emerging[0]
    topics_sorted = sorted(topics, key=_velocity)
    return topics_sorted[0] if topics_sorted else None


def pick_C_technical(topics):
    """A technical/infrastructure topic."""
    tech_kw = ["protocol", "framework", "sdk", "api", "tool", "infra", "runtime",
               "mcp", "docker", "kubernetes", "vector", "rag", "embedding",
               "deploy", "serving", "orchestrat", "security", "credential", "pipeline"]
    tech = [t for t in topics if any(kw in t.get("topic_key", "").lower() for kw in tech_kw)]
    tech.sort(key=_velocity, reverse=True)
    if tech:
        return tech[0]
    return topics[min(2, len(topics) - 1)] if len(topics) > 2 else topics[0] if topics else None


def pick_D_contrarian(topics):
    """Topic where thought leaders have different takes from general sources."""
    week_ago = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    tl = proc.supabase.table("source_posts")\
        .select("title, source, tags")\
        .like("source", "thought_leader_%")\
        .gte("scraped_at", week_ago).limit(200).execute()

    topic_tls = {}
    for p in (tl.data or []):
        for tag in (p.get("tags") or []):
            topic_tls.setdefault(tag.lower(), set()).add(p.get("source", ""))

    multi = {k: v for k, v in topic_tls.items() if len(v) >= 2}
    if multi:
        best_tag = max(multi, key=lambda k: len(multi[k]))
        for t in topics:
            if best_tag in t.get("topic_key", "").lower():
                return t

    return topics[min(4, len(topics) - 1)] if len(topics) > 4 else topics[-1] if topics else None


def pick_E_synthesis(topics):
    """Top 3 emerging topics for synthesis mode."""
    if len(topics) < 3:
        return None
    return topics[:3]


TOPIC_PICKERS = [
    ("A", "debating", "Highest velocity debating topic", pick_A_debating),
    ("B", "emerging", "Emerging topic with thin signal", pick_B_emerging_thin),
    ("C", "technical", "Technical/infrastructure topic", pick_C_technical),
    ("D", "contrarian", "Thought leader disagreement topic", pick_D_contrarian),
    ("E", "synthesis", "Synthesis mode (3 topics)", pick_E_synthesis),
]


# ============================================================================
# Run the Research Agent pipeline for one topic
# ============================================================================

def run_research(topic, mode="spotlight", synthesis_topics=None):
    """Run the full RA pipeline: gather sources, build context, call LLM."""
    if mode == "synthesis" and synthesis_topics:
        topic_name = "Landscape Synthesis"
        topic_id = "synthesis"
        queue_item = {
            "id": "test-quality",
            "topic_id": topic_id,
            "topic_name": topic_name,
            "lifecycle_phase": "synthesis",
            "mode": "synthesis",
            "context_payload": {
                "topics": [
                    {"topic_id": t.get("topic_key"), "topic_name": t.get("topic_key", "").replace("_", " ").title()}
                    for t in synthesis_topics
                ]
            },
        }
        sources = ra.gather_synthesis_sources(queue_item)
    else:
        topic_key = topic.get("topic_key", "unknown")
        topic_name = topic_key.replace("_", " ").title()
        queue_item = {
            "id": "test-quality",
            "topic_id": topic_key,
            "topic_name": topic_name,
            "lifecycle_phase": topic.get("current_stage", "unknown"),
            "mode": "spotlight",
        }
        sources = ra.gather_sources(topic_key, topic_name)

    context = ra.build_context_window(queue_item, sources)

    t0 = time.time()
    data, usage = ra.generate_thesis(context, mode=mode)
    elapsed = time.time() - t0

    return data, usage, sources, elapsed


# ============================================================================
# Quality Checks
# ============================================================================

def check_structure(data):
    """STRUCTURE CHECKS: fields present, lengths, timeframe."""
    issues = []
    required = ["thesis", "evidence", "counter_argument", "prediction", "builder_implications"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        issues.append(f"missing fields: {missing}")

    thesis = data.get("thesis", "")
    sentences = len([s for s in re.split(r'[.!?]+', thesis) if s.strip()])
    if sentences > 2:
        issues.append(f"thesis has {sentences} sentences (max 2)")

    evidence = data.get("evidence", "")
    ev_words = len(evidence.split())
    if ev_words < 100:
        issues.append(f"evidence only {ev_words} words (need 100+)")

    counter = data.get("counter_argument", "")
    ca_words = len(counter.split())
    if ca_words < 50:
        issues.append(f"counter-argument only {ca_words} words (need 50+)")

    prediction = data.get("prediction", "")
    has_time = any(re.search(p, prediction, re.IGNORECASE) for p in TIMEFRAME_PATTERNS)
    if not has_time:
        issues.append("prediction missing timeframe")

    builder = data.get("builder_implications", "")
    bi_words = len(builder.split())
    if bi_words < 30:
        issues.append(f"builder implications only {bi_words} words (need 30+)")

    return len(issues) == 0, issues


def check_voice(data):
    """VOICE CHECKS: hedging, AI phrases, weak openings, bullet points."""
    issues = []
    all_text = " ".join([
        data.get("thesis", ""), data.get("evidence", ""),
        data.get("counter_argument", ""), data.get("prediction", ""),
        data.get("builder_implications", ""),
    ]).lower()

    hedges = [h for h in HEDGE_PHRASES if h in all_text]
    if hedges:
        issues.append(f"hedging: {hedges}")

    ai = [a for a in AI_PHRASES if a in all_text]
    if ai:
        issues.append(f"AI phrases: {ai}")

    weak = [w for w in WEAK_OPENINGS if all_text.startswith(w) or f"\n{w}" in all_text]
    if weak:
        issues.append(f"weak openings: {weak}")

    if re.search(r"(?:^|\n)\s*[-*\u2022\d]+[.)]\s", all_text):
        issues.append("bullet points or numbered lists found")

    return len(issues) == 0, issues


def check_conviction(data):
    """CONVICTION CHECKS: tension, prediction specificity, counter ratio, both-sides."""
    issues = []

    thesis = data.get("thesis", "").lower()
    has_tension = any(f" {w} " in f" {thesis} " for w in TENSION_WORDS)
    if not has_tension:
        issues.append("thesis lacks tension word (but/however/despite/yet/although/while)")

    prediction = data.get("prediction", "")
    has_number = bool(re.search(r"\d+", prediction))
    has_named = bool(re.search(r"[A-Z][a-z]+(?:\s[A-Z][a-z]+)*", prediction))
    has_quarter = bool(re.search(r"Q[1-4]|(?:January|February|March|April|May|June|July|August|September|October|November|December)", prediction))
    has_by_date = bool(re.search(r"by\s+\w+\s+\d{4}", prediction, re.IGNORECASE))
    specifics = sum([has_number, has_named, has_quarter or has_by_date])
    if specifics < 2:
        issues.append(f"prediction lacks specifics (number={has_number}, entity={has_named}, date={has_quarter or has_by_date})")

    evidence = data.get("evidence", "")
    counter = data.get("counter_argument", "")
    if evidence and counter:
        ratio = len(counter.split()) / max(len(evidence.split()), 1)
        if ratio < 0.4:
            issues.append(f"counter-argument is only {ratio:.0%} of evidence length (need 40%+)")

    all_text = " ".join([data.get(k, "") for k in ["thesis", "evidence", "counter_argument"]]).lower()
    if "on one hand" in all_text and "on the other hand" in all_text:
        if not any(w in all_text for w in ["we believe", "our take", "i think", "the evidence suggests"]):
            issues.append("both-sides language without taking a position")

    return len(issues) == 0, issues


def check_sources(data, has_tl_topic=False):
    """SOURCE CHECKS: URLs, thought leader refs, tier diversity."""
    issues = []

    key_sources = data.get("key_sources", [])
    urls = [s for s in key_sources if isinstance(s, str) and s.startswith("http")]
    if len(urls) < 2:
        issues.append(f"only {len(urls)} source URLs (need 2+)")

    if has_tl_topic:
        all_text = " ".join([data.get(k, "") for k in ["evidence", "counter_argument"]]).lower()
        tl_refs = any(kw in all_text for kw in [
            "thought leader", "wrote", "argues", "according to", "noted", "pointed out",
            "simon willison", "swyx", "a16z", "andreessen", "karpathy",
        ])
        if not tl_refs:
            issues.append("no thought leader reference in evidence (Topic D)")

    return len(issues) == 0, issues


def check_synthesis(data, topic_names):
    """SYNTHESIS CHECKS: all topics mentioned, single claim, true synthesis."""
    issues = []

    full_text = " ".join([data.get(k, "") for k in
                          ["thesis", "evidence", "counter_argument", "prediction", "builder_implications"]]).lower()

    mentioned = []
    not_mentioned = []
    for name in topic_names:
        name_parts = name.lower().replace("_", " ").split()
        if any(part in full_text for part in name_parts if len(part) >= 4):
            mentioned.append(name)
        else:
            not_mentioned.append(name)

    if not_mentioned:
        issues.append(f"topics not mentioned in output: {not_mentioned}")

    thesis = data.get("thesis", "")
    and_count = thesis.lower().count(" and ")
    if and_count >= 2:
        issues.append(f"thesis may be 3 statements joined by 'and' ({and_count} 'and's)")

    return len(issues) == 0, issues


# ============================================================================
# Print full output for one topic
# ============================================================================

def print_full_output(label, letter, topic_info, data, usage, sources, elapsed,
                      struct_ok, struct_issues, voice_ok, voice_issues,
                      conv_ok, conv_issues, src_ok, src_issues,
                      synth_ok=None, synth_issues=None):
    topic_name = topic_info.get("name", "?")
    phase = topic_info.get("phase", "?")
    vel = topic_info.get("velocity", 0)
    src_count = sources.get("total_sources", 0)

    print(f"\n{'='*70}")
    print(f"  TOPIC {letter}: {topic_name} ({phase}, velocity: {vel}, {src_count} sources)")
    print(f"  Processing time: {elapsed:.1f}s")
    print(f"  Tokens: {usage.get('input_tokens', 0)} in + {usage.get('output_tokens', 0)} out")
    print(f"{'='*70}")

    print(f"\n  THESIS:\n  {data.get('thesis', 'MISSING')}")

    print(f"\n  EVIDENCE:")
    ev = data.get("evidence", "MISSING")
    for line in ev.split("\n"):
        print(f"  {line}")

    print(f"\n  COUNTER-ARGUMENT:")
    ca = data.get("counter_argument", "MISSING")
    for line in ca.split("\n"):
        print(f"  {line}")

    print(f"\n  PREDICTION:\n  {data.get('prediction', 'MISSING')}")

    print(f"\n  BUILDER IMPLICATIONS:")
    bi = data.get("builder_implications", "MISSING")
    for line in bi.split("\n"):
        print(f"  {line}")

    ks = data.get("key_sources", [])
    print(f"\n  KEY SOURCES ({len(ks)}):")
    for s in ks:
        print(f"    {s}")

    print(f"\n  QUALITY SCORES:")

    def _pf(ok, issues, label):
        status = "PASS" if ok else "FAIL"
        detail = f" [{'; '.join(str(i) for i in issues)}]" if issues else ""
        print(f"    {label:<14} {status}{detail}")

    _pf(struct_ok, struct_issues, "Structure:")
    _pf(voice_ok, voice_issues, "Voice:")
    _pf(conv_ok, conv_issues, "Conviction:")
    _pf(src_ok, src_issues, "Sources:")
    if synth_ok is not None:
        _pf(synth_ok, synth_issues, "Synthesis:")


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 70)
    print("  TEST 2D: Research Agent Output Quality Report")
    print("=" * 70)

    init()

    topics, synthetic = get_topics()
    print(f"  Topics available: {len(topics)} ({'synthetic' if synthetic else 'real data'})")

    results = []
    all_issues = []

    for letter, ttype, desc, picker in TOPIC_PICKERS:
        print(f"\n{'#'*70}")
        print(f"  Selecting Topic {letter}: {desc}")
        print(f"{'#'*70}")

        if letter == "E":
            synthesis_topics = picker(topics)
            if not synthesis_topics:
                print(f"  SKIP: Not enough topics for synthesis")
                results.append({"letter": letter, "type": ttype, "skipped": True})
                continue

            names = [t.get("topic_key", "?").replace("_", " ").title() for t in synthesis_topics]
            print(f"  Selected: {', '.join(names)}")
            for st in synthesis_topics:
                print(f"    - {st.get('topic_key')}: {st.get('current_stage', '?')}, "
                      f"velocity={_velocity(st)}, sources={_sources_list(st)}")

            data, usage, sources, elapsed = run_research(None, mode="synthesis", synthesis_topics=synthesis_topics)

            if not data:
                print(f"  FAIL: No output from Research Agent")
                results.append({"letter": letter, "type": ttype, "skipped": False, "failed": True})
                continue

            struct_ok, struct_issues = check_structure(data)
            voice_ok, voice_issues = check_voice(data)
            conv_ok, conv_issues = check_conviction(data)
            src_ok, src_issues = check_sources(data)
            synth_ok, synth_issues = check_synthesis(data, [t.get("topic_key", "") for t in synthesis_topics])

            topic_info = {"name": "Synthesis: " + " + ".join(names), "phase": "synthesis",
                          "velocity": sum(_velocity(t) for t in synthesis_topics)}

            print_full_output(desc, letter, topic_info, data, usage, sources, elapsed,
                              struct_ok, struct_issues, voice_ok, voice_issues,
                              conv_ok, conv_issues, src_ok, src_issues,
                              synth_ok, synth_issues)

            overall = struct_ok and voice_ok and conv_ok
            if synth_ok is not None:
                overall = overall and synth_ok
            results.append({
                "letter": letter, "type": ttype, "topic": topic_info["name"],
                "structure": struct_ok, "voice": voice_ok, "conviction": conv_ok,
                "sources": src_ok, "synthesis": synth_ok, "overall": overall,
                "issues": struct_issues + voice_issues + conv_issues + src_issues + (synth_issues or []),
            })
            all_issues.extend(struct_issues + voice_issues + conv_issues + src_issues + (synth_issues or []))

        else:
            topic = picker(topics)
            if not topic:
                print(f"  SKIP: No suitable topic found")
                results.append({"letter": letter, "type": ttype, "skipped": True})
                continue

            tk = topic.get("topic_key", "?")
            phase = topic.get("current_stage", "?")
            vel = _velocity(topic)
            srcs = _sources_list(topic)
            print(f"  Selected: {tk}")
            print(f"    phase={phase}, velocity={vel}, sources={srcs}")

            data, usage, sources, elapsed = run_research(topic, mode="spotlight")

            if not data:
                print(f"  FAIL: No output from Research Agent")
                results.append({"letter": letter, "type": ttype, "skipped": False, "failed": True})
                continue

            struct_ok, struct_issues = check_structure(data)
            voice_ok, voice_issues = check_voice(data)
            conv_ok, conv_issues = check_conviction(data)
            is_tl_topic = (letter == "D")
            src_ok, src_issues = check_sources(data, has_tl_topic=is_tl_topic)

            topic_info = {"name": tk.replace("_", " ").title(), "phase": phase,
                          "velocity": vel}

            print_full_output(desc, letter, topic_info, data, usage, sources, elapsed,
                              struct_ok, struct_issues, voice_ok, voice_issues,
                              conv_ok, conv_issues, src_ok, src_issues)

            overall = struct_ok and voice_ok and conv_ok
            results.append({
                "letter": letter, "type": ttype, "topic": topic_info["name"],
                "structure": struct_ok, "voice": voice_ok, "conviction": conv_ok,
                "sources": src_ok, "overall": overall,
                "issues": struct_issues + voice_issues + conv_issues + src_issues,
            })
            all_issues.extend(struct_issues + voice_issues + conv_issues + src_issues)

    # =========== Comparative Summary ===========

    print(f"\n\n{'='*70}")
    print(f"  === RESEARCH AGENT QUALITY REPORT ===")
    print(f"{'='*70}")

    def _pf(val):
        if val is None:
            return "SKIP"
        return "PASS" if val else "FAIL"

    header = f"  {'Topic':<8} {'Type':<12} {'Structure':<11} {'Voice':<7} {'Conviction':<12} {'Sources':<9} {'Overall':<8}"
    print(header)
    print(f"  {'-'*8} {'-'*12} {'-'*11} {'-'*7} {'-'*12} {'-'*9} {'-'*8}")

    pass_count = 0
    run_count = 0
    for r in results:
        if r.get("skipped"):
            print(f"  {r['letter']:<8} {r['type']:<12} {'SKIP':<11} {'SKIP':<7} {'SKIP':<12} {'SKIP':<9} {'SKIP':<8}")
            continue
        if r.get("failed"):
            print(f"  {r['letter']:<8} {r['type']:<12} {'FAIL':<11} {'FAIL':<7} {'FAIL':<12} {'FAIL':<9} {'FAIL':<8}")
            run_count += 1
            continue

        run_count += 1
        overall = _pf(r.get("overall"))
        synth = r.get("synthesis")
        overall_label = overall
        if synth is not None and not synth:
            overall_label = "MIXED"
        if r.get("overall"):
            pass_count += 1
            overall_label = "PASS"
        elif any(r.get(k) for k in ["structure", "voice", "conviction"]):
            overall_label = "MIXED"

        print(f"  {r['letter']:<8} {r['type']:<12} {_pf(r.get('structure')):<11} "
              f"{_pf(r.get('voice')):<7} {_pf(r.get('conviction')):<12} "
              f"{_pf(r.get('sources')):<9} {overall_label:<8}")

    # Common issues
    from collections import Counter
    issue_counter = Counter()
    for issue in all_issues:
        key = issue.split(":")[0] if ":" in issue else issue.split("(")[0].strip()
        issue_counter[key] += 1

    repeated = {k: v for k, v in issue_counter.items() if v >= 2}
    if repeated:
        print(f"\n  Common issues across outputs:")
        for issue, count in sorted(repeated.items(), key=lambda x: -x[1]):
            print(f"    - {issue} (x{count})")

    # Prompt improvement suggestions
    suggestions = []
    if any("tension" in str(i) for i in all_issues):
        suggestions.append("Strengthen thesis tension requirement: add more examples of tension words in IDENTITY.md")
    if any("hedging" in str(i) for i in all_issues):
        suggestions.append("Add stronger anti-hedging examples in the forbidden patterns section")
    if any("AI phrases" in str(i) for i in all_issues):
        suggestions.append("Expand the blacklist of AI-sounding phrases in the voice section")
    if any("prediction lacks specifics" in str(i) for i in all_issues):
        suggestions.append("Add explicit requirement for number + entity + date in predictions")
    if any("counter-argument" in str(i) and "length" in str(i) for i in all_issues):
        suggestions.append("Increase minimum counter-argument length requirement in IDENTITY.md")
    if any("bullet" in str(i) for i in all_issues):
        suggestions.append("Strengthen the prose-only requirement, explicitly forbid bullet points")
    if any("source URLs" in str(i) for i in all_issues):
        suggestions.append("Add explicit instruction to include at least 3 source URLs in key_sources")

    if suggestions:
        print(f"\n  Prompt improvement suggestions:")
        for s in suggestions:
            print(f"    - {s}")

    ready = pass_count >= 4 or (run_count > 0 and pass_count / max(run_count, 1) >= 0.8)
    print(f"\n  READY FOR PHASE 3: {'YES' if ready else 'NO'} ({pass_count}/{run_count} topics pass overall)")

    # Cleanup synthetic topics
    for tid in CLEANUP_IDS["topic_evolution"]:
        try:
            proc.supabase.table("topic_evolution").delete().eq("id", tid).execute()
        except Exception:
            pass


if __name__ == "__main__":
    main()
