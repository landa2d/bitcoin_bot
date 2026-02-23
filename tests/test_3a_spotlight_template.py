#!/usr/bin/env python3
"""
TEST 3A: Spotlight Template Formatting

Validates that the Newsletter Agent correctly formats the Research Agent's
structured Spotlight data into editorial prose, preserving thesis/prediction
and following all formatting rules. Also tests graceful handling when
Spotlight is absent.
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

NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
PROC_DIR = Path(__file__).resolve().parent.parent / "docker" / "processor"
sys.path.insert(0, str(NL_DIR))
sys.path.insert(0, str(PROC_DIR))

os.environ.setdefault(
    "OPENCLAW_DATA_DIR",
    str(Path(__file__).resolve().parent.parent / "data" / "openclaw"),
)

import newsletter_poller as nl

OPENCLAW = Path(os.environ["OPENCLAW_DATA_DIR"])

CLEANUP_IDS: list[str] = []

HEDGE_PHRASES = [
    "it remains to be seen", "time will tell", "only time will tell",
    "it could go either way", "may or may not", "the jury is still out",
]
AI_PHRASES = [
    "it's worth noting", "in the rapidly evolving", "as we navigate",
    "in conclusion", "a myriad of", "it's important to understand",
    "there are several factors",
]
EDITORIAL_MARKERS = [
    "we believe", "we think", "our take", "our prediction",
    "we expect", "we're watching", "our view",
]

FALLBACK_SPOTLIGHT = {
    "topic_name": "MCP Protocol Governance",
    "mode": "spotlight",
    "thesis": "MCP is winning the protocol war for agent interop, but its "
              "lack of formal governance will force enterprise adopters to "
              "fork the spec within 12 months — fragmenting the ecosystem "
              "it was meant to unify.",
    "evidence": "MCP adoption doubled in the last 30 days with 47 new "
                "integrations announced. GitHub stars crossed 25k. Three "
                "enterprise vendors (Salesforce, ServiceNow, Databricks) "
                "have all committed to MCP support. However, the spec is "
                "still governed informally by Anthropic with no RFC process, "
                "no versioning policy, and no clear IP licensing framework.",
    "counter_argument": "MCP's informal governance is actually its strength "
                        "right now. Formal governance slows things down, and "
                        "the protocol is still evolving rapidly. Early "
                        "standardization killed many protocols. De facto "
                        "standards led by a strong steward (Anthropic) may "
                        "converge faster than committee-driven specs.",
    "prediction": "By Q3 2026, at least two major enterprise forks of MCP "
                  "will emerge, each adding proprietary extensions for "
                  "auth, audit logging, and compliance that the base spec "
                  "doesn't address. This will create a 'dialect problem' "
                  "similar to early SQL implementations.",
    "builder_implications": "If you're building on MCP today, abstract your "
                           "integration behind an adapter layer. Don't "
                           "assume the spec is stable. Watch the "
                           "enterprise forks — they'll signal which "
                           "extensions become de facto requirements.",
    "sources_used": [
        {"url": "https://github.com/anthropics/mcp", "label": "MCP repo"},
        {"url": "https://a16z.com/mcp-analysis", "label": "a16z analysis"},
    ],
}


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def init():
    """Initialise Supabase + OpenAI clients."""
    from supabase import create_client
    from openai import OpenAI
    from dotenv import dotenv_values

    vals = dotenv_values(env_path)
    url = vals.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = (vals.get("SUPABASE_SERVICE_KEY") or vals.get("SUPABASE_KEY")
           or os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY"))
    oai = vals.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")

    nl.supabase = create_client(url, key)
    nl.client = OpenAI(api_key=oai)

    nl._identity_cache = None
    nl._identity_mtime = 0
    nl._skill_cache = None
    nl._skill_mtime = 0

    identity_path = nl.AGENT_DIR / "IDENTITY.md"
    skill_path = nl.SKILL_DIR / "SKILL.md"
    print(f"  IDENTITY.md: {identity_path}  exists={identity_path.exists()}")
    print(f"  SKILL.md:    {skill_path}  exists={skill_path.exists()}")

    identity_text = nl.load_identity(nl.AGENT_DIR)
    has_spotlight_prompt = "Spotlight" in identity_text
    print(f"  Identity has Spotlight instructions: {has_spotlight_prompt}")
    if not has_spotlight_prompt:
        print("  *** WARNING: IDENTITY.md missing Spotlight section — results will be unreliable ***")

    skill_text = nl.load_skill(nl.SKILL_DIR)
    print(f"  Skill loaded: {len(skill_text)} chars")
    return nl.supabase


def fetch_or_create_spotlight(supabase) -> dict:
    """Return the latest spotlight_history row, or insert a fallback."""
    result = supabase.table("spotlight_history") \
        .select("*") \
        .order("created_at", desc=True) \
        .limit(1) \
        .execute()

    if result.data:
        row = result.data[0]
        print(f"  Found existing spotlight: '{row.get('topic_name')}' (id={row['id'][:8]}...)")
        return row

    print("  No spotlight_history entry — inserting fallback test row...")
    insert = supabase.table("spotlight_history").insert({
        "topic_name": FALLBACK_SPOTLIGHT["topic_name"],
        "mode": FALLBACK_SPOTLIGHT["mode"],
        "thesis": FALLBACK_SPOTLIGHT["thesis"],
        "evidence": FALLBACK_SPOTLIGHT["evidence"],
        "counter_argument": FALLBACK_SPOTLIGHT["counter_argument"],
        "prediction": FALLBACK_SPOTLIGHT["prediction"],
        "builder_implications": FALLBACK_SPOTLIGHT["builder_implications"],
        "sources_used": FALLBACK_SPOTLIGHT["sources_used"],
        "issue_number": 997,
    }).execute()
    row = insert.data[0]
    CLEANUP_IDS.append(row["id"])
    print(f"  Inserted fallback spotlight (id={row['id'][:8]}..., issue=997)")
    return row


def build_minimal_input(spotlight_dict: dict | None, edition: int = 998) -> dict:
    """Build a minimal but realistic input_data payload for the Newsletter Agent."""
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    opps = nl.supabase.table("opportunities") \
        .select("*").eq("status", "draft") \
        .gte("confidence_score", 0.3) \
        .order("confidence_score", desc=True).limit(5).execute()
    opps_data = opps.data or []

    clusters = nl.supabase.table("problem_clusters") \
        .select("*").gte("created_at", week_ago) \
        .gte("opportunity_score", 0.3) \
        .order("opportunity_score", desc=True).limit(8).execute()
    clusters_data = clusters.data or []

    signals = [
        {"type": "cluster", "theme": c.get("theme", ""),
         "description": c.get("description", ""),
         "opportunity_score": c.get("opportunity_score", 0)}
        for c in clusters_data
    ]

    curious = nl.supabase.table("trending_topics") \
        .select("*").gte("extracted_at", week_ago) \
        .order("novelty_score", desc=True).limit(5).execute()

    tools = nl.supabase.table("tool_stats") \
        .select("*").order("mentions_7d", desc=True).limit(8).execute()

    te = nl.supabase.table("topic_evolution") \
        .select("*").order("last_updated", desc=True).limit(10).execute()

    try:
        predictions = nl.supabase.table("predictions") \
            .select("*").in_("status", ["active", "confirmed", "faded"]) \
            .order("created_at", desc=True).limit(8).execute()
    except Exception:
        predictions = type("R", (), {"data": []})()  # empty fallback

    tl = nl.supabase.table("source_posts") \
        .select("*").like("source", "thought_leader_%") \
        .gte("scraped_at", week_ago).order("scraped_at", desc=True).limit(10).execute()

    radar = [t for t in (te.data or []) if t.get("current_stage") == "emerging"][:4]

    payload = {
        "edition_number": edition,
        "section_a_opportunities": opps_data,
        "section_b_emerging": signals,
        "section_c_curious": curious.data or [],
        "predictions": predictions.data or [],
        "trending_tools": tools.data or [],
        "tool_warnings": [],
        "clusters": clusters_data[:5],
        "topic_evolution": te.data or [],
        "radar_topics": radar,
        "thought_leader_content": tl.data or [],
        "stats": {
            "posts_count": 80, "problems_count": 40,
            "tools_count": len(tools.data or []),
            "new_opps_count": len(opps_data),
            "emerging_signals_count": len(signals),
            "trending_topics_count": len(curious.data or []),
            "source_breakdown": {"moltbook": 25, "hackernews": 30, "github": 15,
                                 "rss_premium": 5, "thought_leaders": 5},
            "total_posts_all_sources": 80,
            "topic_stages": {"emerging": len(radar), "debating": 2, "building": 1},
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

    if spotlight_dict is not None:
        payload["spotlight"] = spotlight_dict
    else:
        payload["spotlight"] = None
        payload["_note_spotlight"] = "NO SPOTLIGHT THIS ISSUE. The Research Agent did not produce output. Do NOT include a Spotlight section at all — skip directly from Cold open to The Big Insight."

    return payload


def call_newsletter(input_data: dict) -> dict:
    budget = {"max_llm_calls": 6, "max_seconds": 300, "max_subtasks": 2, "max_retries": 2}
    return nl.generate_newsletter("write_newsletter", input_data, budget)


def extract_spotlight_section(md: str) -> str | None:
    """Extract just the Spotlight section from the full newsletter markdown."""
    m = re.search(
        r'(?:^|\n)(#{2,3}\s*(?:\d+\.?\s*)?Spotlight.*?)(?=\n#{2,3}\s|\Z)',
        md, re.DOTALL | re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()

    sections = re.split(r'\n(?=#{2,3}\s)', md)
    if len(sections) >= 2:
        first_body = sections[1] if sections[0].strip() == "" else sections[0]
        for sec in sections[:2]:
            lower = sec.lower()
            if ("we believe" in lower or "our take" in lower) and \
               ("counter" in lower or "however" in lower or "but " in lower) and \
               ("builder" in lower or "build" in lower):
                return sec.strip()
    return None


# ────────────────────────────────────────────────────────────────────
# Checks
# ────────────────────────────────────────────────────────────────────

def check_headline(spotlight_text: str, thesis: str) -> tuple[str, str]:
    lines = [l.strip() for l in spotlight_text.split("\n") if l.strip()]
    if not lines:
        return "FAIL", "no text found"

    header_line = lines[0]
    if header_line.startswith("## "):
        header_line = lines[1] if len(lines) > 1 else ""

    is_bold = header_line.startswith("**") and "**" in header_line[2:]
    if not is_bold:
        return "FAIL", f"headline not bold: {header_line[:60]}"

    bold_match = re.match(r'\*\*(.+?)\*\*', header_line)
    headline_text = bold_match.group(1).strip() if bold_match else header_line.replace("**", "").strip()

    has_verb = False
    verbs = ["is", "are", "will", "won't", "can't", "should", "must",
             "means", "forces", "creates", "signals", "proves", "reveals",
             "threatens", "demands", "requires", "drives", "hits", "makes"]
    for v in verbs:
        if f" {v} " in f" {headline_text.lower()} ":
            has_verb = True
            break

    is_topic_label = len(headline_text.split()) < 5 and not has_verb
    if is_topic_label:
        return "FAIL", f"headline looks like a topic label, not a claim: '{headline_text}'"

    return "PASS", headline_text


def check_no_bullets(text: str) -> tuple[str, list[str]]:
    bullet_lines = re.findall(r'(?:^|\n)\s*[-*•]\s+\S', text)
    if bullet_lines:
        return "FAIL", [b.strip() for b in bullet_lines[:3]]
    return "PASS", []


def check_no_numbered_lists(text: str) -> tuple[str, list[str]]:
    numbered = re.findall(r'(?:^|\n)\s*\d+[\.\)]\s+\S', text)
    if numbered:
        return "FAIL", [n.strip() for n in numbered[:3]]
    return "PASS", []


def check_no_subheaders(text: str) -> tuple[str, list[str]]:
    lines = text.split("\n")
    subheaders = []
    first_line = True
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and first_line:
            first_line = False
            continue
        first_line = False
        if stripped.startswith("### ") or stripped.startswith("#### "):
            subheaders.append(stripped)
    if subheaders:
        return "FAIL", subheaders[:3]
    return "PASS", []


def check_no_source_list(text: str) -> tuple[str, str]:
    patterns = [r'(?:^|\n)\s*Sources?\s*:', r'(?:^|\n)\s*References?\s*:',
                r'(?:^|\n)\s*\[.*?\]\(http']
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return "FAIL", re.search(p, text, re.IGNORECASE).group(0).strip()
    return "PASS", ""


def check_word_count(text: str) -> tuple[str, int]:
    clean = re.sub(r'^##.*\n', '', text).strip()
    words = len(clean.split())
    if words < 200:
        return "FAIL", words
    if words > 650:
        return "FAIL", words
    if words < 350 or words > 550:
        return "WARN", words
    return "PASS", words


def check_paragraphs(text: str) -> tuple[str, int]:
    clean = re.sub(r'^##.*\n', '', text).strip()
    paragraphs = [p.strip() for p in clean.split("\n\n") if p.strip()]
    count = len(paragraphs)
    if count < 3:
        return "FAIL", count
    if count > 6:
        return "WARN", count
    return "PASS", count


def check_structure_content(text: str) -> tuple[str, list[str]]:
    """Check that tension words appear somewhere in the body."""
    issues = []
    tension_words = ["but", "however", "yet", "although", "despite",
                     "counter", "risk", "challenge", "concern"]
    lower = text.lower()
    found_tension = any(f" {w} " in f" {lower} " or f" {w}," in f" {lower}," for w in tension_words)
    if not found_tension:
        issues.append("no tension/counter-argument language found")
    return ("PASS" if not issues else "FAIL"), issues


def check_thesis_preserved(spotlight_text: str, original_thesis: str) -> tuple[str, str]:
    """Verify the thesis claim appears (possibly reworded) in the output."""
    thesis_words = set(original_thesis.lower().split())
    spotlight_lower = spotlight_text.lower()
    key_nouns = [w for w in thesis_words if len(w) > 4 and w.isalpha()]
    if not key_nouns:
        return "PASS", "no key words to check"
    matches = sum(1 for w in key_nouns if w in spotlight_lower)
    ratio = matches / len(key_nouns)
    if ratio < 0.3:
        return "FAIL", f"only {matches}/{len(key_nouns)} thesis keywords found ({ratio:.0%})"
    return "PASS", f"{matches}/{len(key_nouns)} thesis keywords found ({ratio:.0%})"


def check_prediction_preserved(spotlight_text: str, original_prediction: str) -> tuple[str, str]:
    pred_words = set(original_prediction.lower().split())
    spotlight_lower = spotlight_text.lower()
    key_nouns = [w for w in pred_words if len(w) > 4 and w.isalpha()]
    if not key_nouns:
        return "PASS", "no key words to check"
    matches = sum(1 for w in key_nouns if w in spotlight_lower)
    ratio = matches / len(key_nouns)
    if ratio < 0.25:
        return "FAIL", f"only {matches}/{len(key_nouns)} prediction keywords ({ratio:.0%})"
    return "PASS", f"{matches}/{len(key_nouns)} prediction keywords ({ratio:.0%})"


def check_editorial_voice(text: str) -> tuple[str, list[str]]:
    lower = text.lower()
    found = [m for m in EDITORIAL_MARKERS if m in lower]
    if not found:
        return "FAIL", []
    return "PASS", found


def check_ai_phrases(text: str) -> tuple[str, list[str]]:
    lower = text.lower()
    found = [p for p in AI_PHRASES if p in lower]
    return ("FAIL" if found else "PASS"), found


def check_hedging(text: str) -> tuple[str, list[str]]:
    lower = text.lower()
    found = [h for h in HEDGE_PHRASES if h in lower]
    return ("FAIL" if found else "PASS"), found


# ────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  TEST 3A: Spotlight Template Formatting")
    print("=" * 70)

    # ── Step 1: Init & data ─────────────────────────────────────
    print("\n--- Step 1: Verify Spotlight data availability ---")
    supabase = init()
    spotlight_row = fetch_or_create_spotlight(supabase)

    issue_number = spotlight_row.get("issue_number", "?")
    print(f"\n  Issue number: {issue_number}")
    print(f"  Thesis:       {(spotlight_row.get('thesis') or '')[:120]}...")
    print(f"  Evidence:     {(spotlight_row.get('evidence') or '')[:120]}...")
    print(f"  Counter-arg:  {(spotlight_row.get('counter_argument') or '')[:120]}...")
    print(f"  Prediction:   {(spotlight_row.get('prediction') or '')[:120]}...")
    print(f"  Builder impl: {(spotlight_row.get('builder_implications') or '')[:120]}...")

    spotlight_input = {
        "topic_name": spotlight_row.get("topic_name", ""),
        "mode": spotlight_row.get("mode", "spotlight"),
        "thesis": spotlight_row.get("thesis", ""),
        "evidence": spotlight_row.get("evidence", ""),
        "counter_argument": spotlight_row.get("counter_argument", ""),
        "prediction": spotlight_row.get("prediction", ""),
        "builder_implications": spotlight_row.get("builder_implications", ""),
        "sources_used": spotlight_row.get("sources_used", []),
    }

    # ── Step 2: Generate newsletter WITH Spotlight ──────────────
    print("\n--- Step 2: Generate newsletter with Spotlight ---")
    input_with = build_minimal_input(spotlight_input, edition=998)
    t0 = time.time()
    result_with = call_newsletter(input_with)
    elapsed_with = time.time() - t0

    md_with = result_with.get("content_markdown", "")
    tg_with = result_with.get("content_telegram", "")

    print(f"  Generated in {elapsed_with:.1f}s")
    print(f"  Title: {result_with.get('title', '?')}")
    print(f"  Markdown: {len(md_with)} chars, Telegram: {len(tg_with)} chars")

    spotlight_section = extract_spotlight_section(md_with)

    # ── Step 3: Validate format rules ───────────────────────────
    results: dict[str, tuple[str, ...]] = {}

    if spotlight_section:
        results["headline_claim"] = check_headline(spotlight_section, spotlight_input["thesis"])
        results["no_bullets"] = check_no_bullets(spotlight_section)
        results["no_numbered_lists"] = check_no_numbered_lists(spotlight_section)
        results["no_subheaders"] = check_no_subheaders(spotlight_section)
        results["no_source_list"] = check_no_source_list(spotlight_section)
        results["word_count"] = check_word_count(spotlight_section)
        results["paragraph_structure"] = check_paragraphs(spotlight_section)
        results["structure_content"] = check_structure_content(spotlight_section)
        results["thesis_preserved"] = check_thesis_preserved(spotlight_section, spotlight_input["thesis"])
        results["prediction_preserved"] = check_prediction_preserved(spotlight_section, spotlight_input["prediction"])
        results["editorial_voice"] = check_editorial_voice(spotlight_section)
        results["no_ai_phrases"] = check_ai_phrases(spotlight_section)
        results["no_hedging"] = check_hedging(spotlight_section)
    else:
        for key in ["headline_claim", "no_bullets", "no_numbered_lists",
                     "no_subheaders", "no_source_list", "word_count",
                     "paragraph_structure", "structure_content",
                     "thesis_preserved", "prediction_preserved",
                     "editorial_voice", "no_ai_phrases", "no_hedging"]:
            results[key] = ("FAIL", "Spotlight section not found in newsletter output")

    # ── Step 4: Generate newsletter WITHOUT Spotlight ───────────
    print("\n--- Step 5: Test missing Spotlight behavior ---")
    input_without = build_minimal_input(None, edition=999)
    t0 = time.time()
    result_without = call_newsletter(input_without)
    elapsed_without = time.time() - t0

    md_without = result_without.get("content_markdown", "")
    print(f"  Generated in {elapsed_without:.1f}s")

    missing_spotlight_section = extract_spotlight_section(md_without)
    has_placeholder = bool(re.search(
        r'spotlight.*(?:missing|unavailable|skipped|none|n/a|no spotlight)',
        md_without, re.IGNORECASE,
    ))
    has_orphan_header = bool(re.search(r'##\s*\d*\.?\s*Spotlight\s*$', md_without, re.MULTILINE | re.IGNORECASE))

    if missing_spotlight_section or has_placeholder or has_orphan_header:
        missing_reason = []
        if missing_spotlight_section:
            missing_reason.append("Spotlight section still present")
        if has_placeholder:
            missing_reason.append("placeholder text found")
        if has_orphan_header:
            missing_reason.append("orphan Spotlight header found")
        results["missing_graceful"] = ("FAIL", "; ".join(missing_reason))
    else:
        results["missing_graceful"] = ("PASS", "correctly omitted")

    # ── Step 5: Cleanup ────────────────────────────────────────
    for sid in CLEANUP_IDS:
        try:
            supabase.table("spotlight_history").delete().eq("id", sid).execute()
        except Exception:
            pass
    if CLEANUP_IDS:
        print(f"\n  Cleaned up {len(CLEANUP_IDS)} test spotlight rows")

    # ── Step 6: Summary ────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  === SPOTLIGHT TEMPLATE TEST ===")
    print(f"{'='*70}")

    print(f"\n  Formatted Spotlight:")
    print(f"  {'-'*60}")
    if spotlight_section:
        for line in spotlight_section.split("\n"):
            print(f"  {line}")
    else:
        print("  [Spotlight section NOT found in output]")
    print(f"  {'-'*60}")

    print(f"\n  First 500 chars of newsletter WITHOUT Spotlight:")
    print(f"  {'-'*60}")
    for line in md_without[:500].split("\n"):
        print(f"  {line}")
    print(f"  {'-'*60}")

    print(f"\n  Format checks:")

    label_map = {
        "headline_claim": "Headline is a claim",
        "no_bullets": "No bullet points",
        "no_numbered_lists": "No numbered lists",
        "no_subheaders": "No sub-headers",
        "no_source_list": "No source list",
        "word_count": "Word count",
        "paragraph_structure": "Paragraph structure",
        "structure_content": "Tension / counter-arg",
        "thesis_preserved": "Thesis preserved",
        "prediction_preserved": "Prediction preserved",
        "editorial_voice": "Editorial voice present",
        "no_ai_phrases": "No AI phrases",
        "no_hedging": "No hedging",
        "missing_graceful": "Missing Spotlight graceful",
    }

    pass_count = 0
    fail_count = 0
    warn_count = 0

    for key in label_map:
        status, detail = results.get(key, ("SKIP", ""))
        label = label_map[key]

        if key == "word_count" and isinstance(detail, int):
            detail_str = f"[{detail} words]"
        elif isinstance(detail, list):
            detail_str = f"[{', '.join(str(d) for d in detail)}]" if detail else ""
        else:
            detail_str = f"[{detail}]" if detail else ""

        if status == "PASS":
            pass_count += 1
        elif status == "FAIL":
            fail_count += 1
        elif status == "WARN":
            warn_count += 1

        print(f"  - {label + ':':<28s} {status} {detail_str}")

    print(f"\n  Summary: {pass_count} PASS, {warn_count} WARN, {fail_count} FAIL")

    output_dir = Path(__file__).resolve().parent / "newsletter_test_results"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "3a_with_spotlight.md").write_text(md_with)
    (output_dir / "3a_without_spotlight.md").write_text(md_without)
    print(f"  Full outputs saved to: {output_dir.name}/")

    if fail_count == 0:
        print(f"\n  SPOTLIGHT TEMPLATE: READY")
    else:
        print(f"\n  SPOTLIGHT TEMPLATE: NEEDS ITERATION ({fail_count} failures)")


if __name__ == "__main__":
    main()
