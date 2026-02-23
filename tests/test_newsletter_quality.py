#!/usr/bin/env python3
"""
Newsletter Quality Review — generates 3 test newsletters under different conditions
and runs comparative quality analysis.

Usage: python tests/test_newsletter_quality.py
"""

import json
import os
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

CONFIG_ENV = Path(__file__).resolve().parent.parent / "config" / ".env"
load_dotenv(CONFIG_ENV)

from supabase import create_client
from openai import OpenAI

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("NEWSLETTER_MODEL", "gpt-4o")

IDENTITY_PATH = Path(__file__).resolve().parent.parent / "templates" / "newsletter" / "IDENTITY.md"
SKILL_PATH = Path(__file__).resolve().parent.parent / "skills" / "agentpulse" / "SKILL.md"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

AI_PHRASES = [
    "it's worth noting", "in the rapidly evolving", "as we navigate",
    "in conclusion", "it is important to note", "at the end of the day",
    "in today's landscape", "the landscape of", "transformative potential",
    "game-changing", "revolutionary", "unprecedented",
]
HEDGE_PHRASES = [
    "it remains to be seen", "time will tell", "only time will tell",
    "could potentially", "may or may not", "it's hard to say",
]


# ---------------------------------------------------------------------------
# Data Gathering (mirrors prepare_newsletter_data)
# ---------------------------------------------------------------------------

def gather_newsletter_data() -> dict:
    """Fetch current newsletter input data from Supabase."""
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    opps = supabase.table("opportunities").select("*").eq("status", "draft").gte("confidence_score", 0.3).execute()
    opps_raw = opps.data or []
    for opp in opps_raw:
        appearances = opp.get("newsletter_appearances", 0) or 0
        eff = opp.get("confidence_score", 0) * (0.7 ** appearances)
        lf = opp.get("last_featured_at")
        lr = opp.get("last_reviewed_at")
        if lf and lr and lr > lf:
            eff *= 1.3
        opp["effective_score"] = round(eff, 4)
        opp["is_returning"] = appearances > 0
        opp["last_edition_featured"] = lf
    opps_raw.sort(key=lambda x: x.get("effective_score", 0), reverse=True)
    opportunities = opps_raw[:5]

    emerging_problems = supabase.table("problems").select("*").gte("first_seen", week_ago).lt("frequency_count", 5).order("first_seen", desc=True).limit(10).execute()
    emerging_clusters = supabase.table("problem_clusters").select("*").gte("created_at", week_ago).gte("opportunity_score", 0.3).order("opportunity_score", desc=True).limit(10).execute()

    seen = set()
    signals = []
    for c in (emerging_clusters.data or []):
        theme = c.get("theme", "")
        if theme not in seen:
            seen.add(theme)
            signals.append({"type": "cluster", "theme": theme, "description": c.get("description"), "opportunity_score": c.get("opportunity_score")})
    for p in (emerging_problems.data or []):
        desc = p.get("description", "")
        if desc not in seen:
            seen.add(desc)
            signals.append({"type": "problem", "theme": desc, "description": desc, "category": p.get("category")})
    signals = signals[:10]

    curious = supabase.table("trending_topics").select("*").gte("extracted_at", week_ago).eq("featured_in_newsletter", False).order("novelty_score", desc=True).limit(8).execute()

    tools = supabase.table("tool_stats").select("*").order("mentions_7d", desc=True).limit(10).execute()
    warnings = supabase.table("tool_stats").select("*").lt("avg_sentiment", -0.3).gte("total_mentions", 3).execute()
    clusters = supabase.table("problem_clusters").select("*").gte("created_at", week_ago).order("opportunity_score", desc=True).limit(10).execute()
    predictions = supabase.table("predictions").select("*").in_("status", ["active", "confirmed", "faded"]).order("status", desc=False).limit(10).execute()

    topic_evo = supabase.table("topic_evolution").select("*").order("last_updated", desc=True).limit(15).execute()
    topic_evo_data = topic_evo.data or []

    tl_posts = supabase.table("source_posts").select("*").like("source", "thought_leader_%").gte("scraped_at", week_ago).order("scraped_at", desc=True).limit(20).execute()

    # Radar
    signals_themes = {(s.get("theme") or "").lower() for s in signals}
    radar = [t for t in topic_evo_data if t.get("current_stage") == "emerging" and t.get("topic_key", "").replace("_", " ") not in signals_themes]
    radar.sort(key=lambda t: (t.get("snapshots") or [{}])[-1].get("mentions", 0), reverse=True)
    if len(radar) < 3:
        fill = [t for t in topic_evo_data if t.get("current_stage") == "debating" and t.get("topic_key", "").replace("_", " ") not in signals_themes and t not in radar]
        radar.extend(fill)
    radar = radar[:4]

    # Spotlight
    spotlight = None
    try:
        sl = supabase.table("spotlight_history").select("*").order("created_at", desc=True).limit(1).execute()
        if sl.data:
            s = sl.data[0]
            spotlight = {
                "topic_name": s.get("topic_name", ""),
                "mode": s.get("mode", "spotlight"),
                "thesis": s.get("thesis", ""),
                "evidence": s.get("evidence", ""),
                "counter_argument": s.get("counter_argument", ""),
                "prediction": s.get("prediction", ""),
                "builder_implications": s.get("builder_implications", ""),
                "sources_used": s.get("sources_used", []),
            }
    except Exception:
        pass

    # Stats
    source_stats = {}
    for src in ["moltbook", "hackernews", "github"]:
        c = supabase.table("source_posts").select("id", count="exact").eq("source", src).gte("scraped_at", week_ago).execute()
        source_stats[src] = c.count or 0
    rss_c = supabase.table("source_posts").select("id", count="exact").like("source", "rss_%").gte("scraped_at", week_ago).execute()
    source_stats["rss_premium"] = rss_c.count or 0
    tl_c = supabase.table("source_posts").select("id", count="exact").like("source", "thought_leader_%").gte("scraped_at", week_ago).execute()
    source_stats["thought_leaders"] = tl_c.count or 0

    preds = predictions.data or []
    confirmed = sum(1 for p in preds if p.get("status") == "confirmed")
    faded = sum(1 for p in preds if p.get("status") == "faded")
    active = sum(1 for p in preds if p.get("status") == "active")
    resolved = confirmed + faded
    accuracy = round(confirmed / resolved * 100) if resolved > 0 else None

    topic_stages = {}
    for t in topic_evo_data:
        st = t.get("current_stage", "unknown")
        topic_stages[st] = topic_stages.get(st, 0) + 1

    edition = 900  # test edition

    return {
        "edition_number": edition,
        "section_a_opportunities": opportunities,
        "section_b_emerging": signals,
        "section_c_curious": curious.data or [],
        "predictions": preds,
        "trending_tools": tools.data or [],
        "tool_warnings": warnings.data or [],
        "clusters": clusters.data or [],
        "thought_leader_content": tl_posts.data or [],
        "topic_evolution": topic_evo_data,
        "radar_topics": radar,
        "spotlight": spotlight,
        "stats": {
            "posts_count": sum(source_stats.values()),
            "source_breakdown": source_stats,
            "total_posts_all_sources": sum(source_stats.values()),
            "active_predictions": active,
            "prediction_accuracy": accuracy,
            "topic_stages": topic_stages,
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


# ---------------------------------------------------------------------------
# Newsletter Generation
# ---------------------------------------------------------------------------

def load_text(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def generate(input_data: dict, label: str) -> dict:
    """Call the LLM to generate a newsletter, return parsed result."""
    identity = load_text(IDENTITY_PATH)
    skill = load_text(SKILL_PATH)

    system_prompt = f"{identity}\n\n---\n\nSKILL REFERENCE:\n{skill}"
    system_prompt += "\n\nYou MUST respond with valid JSON only — no markdown fences, no extra text."

    user_msg = (
        f"TASK TYPE: write_newsletter\n\n"
        f"BUDGET: {{\"max_llm_calls\": 6, \"max_seconds\": 300}}\n\n"
        f"INPUT DATA:\n{json.dumps(input_data, indent=2, default=str)}"
    )

    print(f"\n  Generating {label}...", end=" ", flush=True)
    t0 = time.time()
    response = openai_client.chat.completions.create(
        model=MODEL,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
    )
    elapsed = time.time() - t0
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    result = json.loads(text)
    if "result" in result and isinstance(result["result"], dict):
        result = result["result"]

    tokens = response.usage.total_tokens if response.usage else 0
    print(f"done ({elapsed:.1f}s, {tokens} tokens)")
    return result


# ---------------------------------------------------------------------------
# Quality Analysis Helpers
# ---------------------------------------------------------------------------

def word_count(text: str) -> int:
    return len(text.split()) if text else 0


def count_phrases(text: str, phrases: list) -> list:
    text_lower = text.lower()
    return [p for p in phrases if p in text_lower]


def count_bullets(text: str) -> int:
    return len(re.findall(r"^\s*[-*•]\s", text, re.MULTILINE))


def extract_sections(md: str) -> dict:
    """Split markdown into named sections based on ## headers."""
    sections = {}
    current = "_preamble"
    lines = []
    for line in md.split("\n"):
        m = re.match(r"^#{1,3}\s+(.+)", line)
        if m:
            if lines:
                sections[current] = "\n".join(lines)
            current = m.group(1).strip()
            lines = []
        else:
            lines.append(line)
    if lines:
        sections[current] = "\n".join(lines)
    return sections


def find_spotlight_section(sections: dict) -> str | None:
    for key, val in sections.items():
        if "spotlight" in key.lower() or any(
            kw in key.lower() for kw in ["deep dive", "editorial"]
        ):
            return val
    for key, val in sections.items():
        if key == "_preamble" and word_count(val) > 200:
            return val
    return None


def signals_substantive(sections: dict) -> tuple[int, int]:
    """Count how many signal items have >15 words each."""
    for key, val in sections.items():
        if "signal" in key.lower() or "emerging" in key.lower():
            items = re.split(r"\n(?=\*\*|\d+\.)", val.strip())
            total = len(items)
            substantive = sum(1 for i in items if word_count(i) > 15)
            return substantive, total
    return 0, 0


def radar_unique_vs_signals(sections: dict) -> bool:
    sig_text = ""
    radar_text = ""
    for key, val in sections.items():
        if "signal" in key.lower() or "emerging" in key.lower():
            sig_text = val.lower()
        if "radar" in key.lower():
            radar_text = val.lower()
    if not radar_text or not sig_text:
        return True
    radar_words = set(re.findall(r"\b\w{5,}\b", radar_text))
    sig_words = set(re.findall(r"\b\w{5,}\b", sig_text))
    overlap = radar_words & sig_words
    filler = {"about", "which", "their", "these", "being", "would", "could", "should", "other", "where", "there", "agent", "agents"}
    meaningful_overlap = overlap - filler
    return len(meaningful_overlap) < len(radar_words) * 0.5


# ---------------------------------------------------------------------------
# Content Extraction
# ---------------------------------------------------------------------------

def extract_markdown(result: dict) -> str:
    """Extract readable newsletter text from the LLM's structured JSON response."""
    # Direct markdown field
    for key in ("content_markdown", "markdown", "full_text", "newsletter_text"):
        if isinstance(result.get(key), str) and len(result[key]) > 100:
            return result[key]

    # Nested under 'result' key
    if isinstance(result.get("result"), dict):
        return extract_markdown(result["result"])

    # Nested under 'newsletter' key
    if isinstance(result.get("newsletter"), dict):
        return extract_markdown(result["newsletter"])

    # Structured sections in 'content' dict
    content = result.get("content") or result.get("content_full") or result
    if isinstance(content, dict):
        return _assemble_from_dict(content)

    # Sections as a list
    if isinstance(content, list):
        return _assemble_from_list(content)

    # content is already a string
    if isinstance(content, str) and len(content) > 100:
        return content

    # Last resort: check if 'sections' key exists
    if isinstance(result.get("sections"), list):
        return _assemble_from_list(result["sections"])

    return ""


def _assemble_from_dict(d: dict) -> str:
    """Assemble markdown from a dict of section_name -> text or nested objects."""
    parts = []
    section_order = [
        "cold_open", "spotlight", "big_insight", "the_big_insight",
        "top_opportunities", "opportunities", "emerging_signals", "signals",
        "on_our_radar", "radar", "curious_corner", "the_curious_corner",
        "tool_radar", "tools", "prediction_tracker", "predictions",
        "gatos_corner", "gato", "by_the_numbers", "stats",
    ]
    # Content may have a 'sections' list inside
    if isinstance(d.get("sections"), list):
        return _assemble_from_list(d["sections"])

    ordered_keys = []
    for sk in section_order:
        for key in d:
            if sk in key.lower().replace(" ", "_").replace("'", "") and key not in ordered_keys:
                ordered_keys.append(key)
    for key in d:
        if key not in ordered_keys and key not in ("edition", "edition_number", "title", "budget_usage"):
            ordered_keys.append(key)

    for key in ordered_keys:
        val = d[key]
        header = key.replace("_", " ").title()
        if isinstance(val, str) and val.strip():
            if key == "cold_open":
                parts.append(f"*{val.strip()}*\n")
            else:
                parts.append(f"## {header}\n\n{val.strip()}\n")
        elif isinstance(val, dict):
            raw_t = val.get("text") or val.get("content") or val.get("body") or ""
            if isinstance(raw_t, list):
                raw_t = "\n".join(str(x) for x in raw_t)
            text = str(raw_t)
            title = val.get("title") or val.get("headline") or header
            if text.strip():
                parts.append(f"## {title}\n\n{text.strip()}\n")
            elif isinstance(val.get("items"), list):
                parts.append(f"## {title}\n")
                for item in val["items"]:
                    if isinstance(item, str):
                        parts.append(f"- {item}")
                    elif isinstance(item, dict):
                        t = item.get("title") or item.get("name") or item.get("topic") or ""
                        desc = item.get("description") or item.get("text") or item.get("analysis") or ""
                        parts.append(f"**{t}** -- {desc}" if t else f"- {desc}")
                parts.append("")
        elif isinstance(val, list):
            parts.append(f"## {header}\n")
            for item in val:
                if isinstance(item, str):
                    parts.append(f"- {item}")
                elif isinstance(item, dict):
                    t = item.get("title") or item.get("name") or item.get("topic") or ""
                    desc = item.get("description") or item.get("text") or item.get("analysis") or ""
                    parts.append(f"**{t}** -- {desc}" if t else f"- {desc}")
            parts.append("")

    return "\n".join(parts)


def _assemble_from_list(sections: list) -> str:
    """Assemble markdown from a list of section dicts."""
    parts = []
    for section in sections:
        if isinstance(section, dict):
            title = section.get("title") or section.get("name") or section.get("section") or ""
            raw_text = section.get("text") or section.get("content") or section.get("body") or ""
            if isinstance(raw_text, list):
                raw_text = "\n".join(str(x) for x in raw_text)
            text = str(raw_text)
            items = section.get("items") or []
            if title.lower().startswith("cold"):
                parts.append(f"*{text.strip()}*\n" if text else "")
            elif text.strip():
                parts.append(f"## {title}\n\n{text.strip()}\n")
            elif items:
                parts.append(f"## {title}\n")
                for item in items:
                    if isinstance(item, str):
                        parts.append(f"- {item}")
                    elif isinstance(item, dict):
                        t = item.get("title") or item.get("name") or item.get("topic") or ""
                        desc = item.get("description") or item.get("text") or item.get("analysis") or ""
                        parts.append(f"**{t}** -- {desc}" if t else f"- {desc}")
                parts.append("")
        elif isinstance(section, str):
            parts.append(section)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  AGENTPULSE NEWSLETTER QUALITY REVIEW")
    print("=" * 60)

    print("\n[1/5] Gathering current data from Supabase...")
    base_data = gather_newsletter_data()

    data_summary = {
        "opportunities": len(base_data["section_a_opportunities"]),
        "signals": len(base_data["section_b_emerging"]),
        "curious": len(base_data["section_c_curious"]),
        "radar": len(base_data["radar_topics"]),
        "spotlight": base_data["spotlight"] is not None,
        "thought_leaders": len(base_data.get("thought_leader_content", [])),
        "predictions": len(base_data.get("predictions", [])),
    }
    print(f"  Data gathered: {json.dumps(data_summary, indent=4)}")

    # ── Newsletter A: Best case (full pipeline) ──
    print("\n[2/5] Generating newsletters...")
    data_a = json.loads(json.dumps(base_data, default=str))
    data_a["edition_number"] = 900
    result_a = generate(data_a, "Newsletter A — Full Pipeline (Best Case)")

    # ── Newsletter B: Synthesis mode (force no single-topic spotlight) ──
    data_b = json.loads(json.dumps(base_data, default=str))
    data_b["edition_number"] = 901
    if data_b.get("spotlight"):
        data_b["spotlight"]["mode"] = "synthesis"
        data_b["spotlight"]["thesis"] = (
            "Three converging trends — agent interoperability protocols, "
            "autonomous payment rails, and LLM-native developer tooling — "
            "are colliding this month in ways that will reshape who captures "
            "value in the AI stack."
        )
        data_b["spotlight"]["evidence"] = (
            "MCP adoption doubled in enterprise environments. Lightning-based "
            "agent escrow saw 40% more mentions. LangChain and CrewAI both "
            "shipped multi-agent orchestration updates in the same week."
        )
        data_b["spotlight"]["counter_argument"] = (
            "Skeptics argue these are still toy demos — enterprise agent "
            "deployments remain single-agent in 90%+ of cases, and payment "
            "volumes are negligible."
        )
        data_b["spotlight"]["prediction"] = (
            "Within 6 months, at least two major cloud providers will ship "
            "native multi-agent orchestration, and the standalone orchestration "
            "layer companies will face existential pressure."
        )
    else:
        data_b["spotlight"] = {
            "mode": "synthesis",
            "topic_name": "Convergence Watch",
            "thesis": "Three converging trends are colliding this month in ways that will reshape the AI stack.",
            "evidence": "MCP adoption doubled. Agent escrow mentions up 40%. Multi-agent orchestration shipped by two major frameworks.",
            "counter_argument": "Enterprise deployments remain 90%+ single-agent.",
            "prediction": "Within 6 months, two major cloud providers ship native multi-agent orchestration.",
            "builder_implications": "Build for interop now — the walled-garden window is closing.",
            "sources_used": [],
        }
    result_b = generate(data_b, "Newsletter B — Synthesis Mode")

    # ── Newsletter C: No Spotlight (research agent disabled) ──
    data_c = json.loads(json.dumps(base_data, default=str))
    data_c["edition_number"] = 902
    data_c["spotlight"] = None
    result_c = generate(data_c, "Newsletter C — No Spotlight")

    # ── Extract content ──
    newsletters = {
        "A": result_a,
        "B": result_b,
        "C": result_c,
    }

    md = {}
    for k, r in newsletters.items():
        content = extract_markdown(r)
        if not content:
            print(f"  Newsletter {k}: WARNING — could not extract content (keys: {list(r.keys())})")
        else:
            print(f"  Newsletter {k}: extracted {word_count(content)} words")
        md[k] = content

    # ── Print full newsletters ──
    print("\n\n[3/5] Full newsletter output:\n")
    labels = {
        "A": "NEWSLETTER A — FULL PIPELINE (Best Case)",
        "B": "NEWSLETTER B — SYNTHESIS MODE",
        "C": "NEWSLETTER C — NO SPOTLIGHT",
    }
    for k in ("A", "B", "C"):
        content = md[k]
        wc = word_count(content)
        read_min = round(wc / 200, 1)
        sections = extract_sections(content)
        section_names = [s for s in sections if s != "_preamble"]

        print(f"\n{'#' + '=' * 56 + '#'}")
        print(f"|  {labels[k]:<54}|")
        print(f"{'#' + '=' * 56 + '#'}\n")
        print(content)
        print(f"\n  Word count: {wc} | Read time: ~{read_min} min")
        print(f"  Sections: {', '.join(section_names)}")

        spotlight_text = find_spotlight_section(sections)
        if spotlight_text and k != "C":
            sp_wc = word_count(spotlight_text)
            print(f"  Spotlight: {sp_wc} words")

        sig_sub, sig_total = signals_substantive(sections)
        print(f"  Signals: {sig_sub}/{sig_total} substantive (>15 words)")
        print(f"  Radar unique vs signals: {'YES' if radar_unique_vs_signals(sections) else 'NO'}")

    print(f"\n{'#' + '=' * 56 + '#'}")

    # ── Comparative Analysis ──
    print("\n\n[4/5] Comparative Analysis")
    print("=" * 56)

    # Spotlight Comparison (A vs B)
    sections_a = extract_sections(md["A"])
    sections_b = extract_sections(md["B"])
    sections_c = extract_sections(md["C"])

    sp_a = find_spotlight_section(sections_a) or ""
    sp_b = find_spotlight_section(sections_b) or ""

    tension_words = ["but", "however", "yet", "although", "despite", "tension", "risk", "challenge", "paradox", "dilemma"]

    def count_tension(text):
        t = text.lower()
        return sum(1 for w in tension_words if f" {w} " in f" {t} ")

    print("\n── SPOTLIGHT COMPARISON (A vs B) ──")
    headline_a = next((k for k in sections_a if k != "_preamble"), "?")
    headline_b = next((k for k in sections_b if k != "_preamble"), "?")
    print(f"  A headline: {headline_a}")
    print(f"  B headline: {headline_b}")
    print(f"  Tension words — A: {count_tension(sp_a)}, B: {count_tension(sp_b)}")
    if headline_a.lower()[:30] == headline_b.lower()[:30]:
        print("  WARNING: Headlines are very similar — may feel repetitive")
    else:
        print("  Headlines are different — good variety")

    print("\n── NEWSLETTER COMPLETENESS ──")
    wc_a = word_count(md["A"])
    wc_c = word_count(md["C"])
    spotlight_contribution = wc_a - wc_c
    print(f"  A (full): {wc_a} words | C (no spotlight): {wc_c} words")
    print(f"  Spotlight adds: ~{spotlight_contribution} words ({round(spotlight_contribution/max(wc_a,1)*100)}% of total)")
    print(f"  C feels complete: {'YES — still substantial' if wc_c >= 500 else 'NO — feels thin'}")

    # ── Quality Metrics ──
    print("\n── OVERALL QUALITY ──\n")
    metrics = {}
    for k in ("A", "B", "C"):
        content = md[k]
        ai_found = count_phrases(content, AI_PHRASES)
        hedge_found = count_phrases(content, HEDGE_PHRASES)
        sections = extract_sections(content)
        sp = find_spotlight_section(sections) or ""
        bullets = count_bullets(sp) if k != "C" else None
        sig_sub, sig_total = signals_substantive(sections)
        radar_ok = radar_unique_vs_signals(sections)
        metrics[k] = {
            "words": word_count(content),
            "read_time": round(word_count(content) / 200, 1),
            "ai_phrases": len(ai_found),
            "ai_list": ai_found,
            "hedge_phrases": len(hedge_found),
            "hedge_list": hedge_found,
            "spotlight_bullets": bullets,
            "signals_substantive": f"{sig_sub}/{sig_total}",
            "radar_unique": "YES" if radar_ok else "NO",
        }

    # ── Summary Table ──
    print("\n[5/5] Quality Summary\n")
    print("=" * 56)
    print("  NEWSLETTER QUALITY REVIEW")
    print("=" * 56)

    header = f"  {'':20s} | {'NL A':>12s} | {'NL B':>12s} | {'NL C':>12s}"
    sep =    f"  {'-'*20}-+-{'-'*12}-+-{'-'*12}-+-{'-'*12}"
    print(header)
    print(sep)

    def row(label, key, fmt=str):
        a = fmt(metrics["A"][key])
        b = fmt(metrics["B"][key])
        c = fmt(metrics["C"][key])
        print(f"  {label:20s} | {a:>12s} | {b:>12s} | {c:>12s}")

    row("Total words", "words", str)
    row("Read time", "read_time", lambda x: f"~{x} min")
    row("AI phrases found", "ai_phrases", str)
    row("Hedge phrases", "hedge_phrases", str)
    row("Bullets in Spotlight", "spotlight_bullets", lambda x: str(x) if x is not None else "N/A")
    row("Signals substantive", "signals_substantive")
    row("Radar unique", "radar_unique")

    print()
    for k in ("A", "B", "C"):
        m = metrics[k]
        if m["ai_list"]:
            print(f"  NL {k} — AI phrases: {m['ai_list']}")
        if m["hedge_list"]:
            print(f"  NL {k} — Hedge phrases: {m['hedge_list']}")

    print(f"""
{'=' * 56}
  MANUAL REVIEW QUESTIONS
{'=' * 56}
  Read all 3 newsletters above and answer:
  1. Would you subscribe to this newsletter based on Newsletter A?
  2. Would you forward the Spotlight to a colleague?
  3. Does Newsletter B (synthesis) feel as strong as A, or noticeably weaker?
  4. Does Newsletter C feel complete, or does the missing Spotlight leave a gap?
  5. Is the overall tone consistent across sections?
  6. Does the Radar section make you curious about what's coming next week?

  SHIP DECISION: Ready to send to real readers?  YES / NO
  If NO, list what needs to improve before shipping.
{'=' * 56}
""")


if __name__ == "__main__":
    main()
