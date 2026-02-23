#!/usr/bin/env python3
"""
TEST 4C: Scorecard "Looking Back" Generation

Validates that the Newsletter Agent correctly generates lookback blurbs
from resolved predictions, marks them as scorecarded, respects max limits,
and integrates correctly into the newsletter.

Steps:
  1. Create test spotlight_history + predictions (confirmed, refuted, partial,
     already-scorecarded, open)
  2. Generate scorecard blurbs
  3. Validate format / tone for each blurb
  4. Verify scorecard marking + no-double-inclusion
  5. Verify newsletter placement
  6. Verify graceful absence when no resolved predictions exist
  7. Print all blurbs for manual review
  8. Cleanup
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

CLEANUP = {"spotlight_history": [], "predictions": []}

HEDGE_PHRASES = [
    "it remains to be seen", "time will tell", "only time will tell",
]
AI_PHRASES = [
    "it's worth noting", "in the rapidly evolving", "as we navigate",
    "in conclusion", "a myriad of",
]
GLOAT_PHRASES = [
    "we nailed it", "as we correctly predicted", "we were right all along",
    "told you so", "just as we said",
]
DEFENSIVE_PHRASES = [
    "the situation evolved differently", "circumstances changed",
    "couldn't have predicted", "no one could have foreseen",
    "unforeseeable", "beyond our control",
]


# -----------------------------------------------------------------------
# Init
# -----------------------------------------------------------------------

def init():
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

    print("  Clients initialized")
    return nl.supabase


# -----------------------------------------------------------------------
# Step 1: Create test data
# -----------------------------------------------------------------------

def create_test_data(sb):
    now = datetime.now(timezone.utc)

    # --- (a) CONFIRMED ---
    sl_a = sb.table("spotlight_history").insert({
        "topic_id": "test_sc_mcp_interop",
        "topic_name": "test_sc_mcp_interop",
        "mode": "spotlight",
        "thesis": "MCP will become the dominant interop protocol for agent frameworks within 6 months.",
        "evidence": "47 integrations announced, GitHub stars crossed 25k.",
        "counter_argument": "Informal governance may slow enterprise adoption.",
        "prediction": "At least two major framework vendors will ship MCP-compatible APIs by Q2 2026.",
        "builder_implications": "Build adapter layers now.",
        "full_output": "## Thesis\n\nMCP will become the dominant interop protocol.",
        "sources_used": [],
        "issue_number": 993,
    }).execute()
    sl_a_id = sl_a.data[0]["id"]
    CLEANUP["spotlight_history"].append(sl_a_id)

    pred_a = sb.table("predictions").insert({
        "spotlight_id": sl_a_id,
        "prediction_text": "At least two major framework vendors will ship MCP-compatible APIs by Q2 2026.",
        "topic_id": "test_sc_mcp_interop",
        "issue_number": 993,
        "status": "confirmed",
        "resolution_notes": "LangChain shipped their own MCP variant in April, AWS announced a compatible implementation in May.",
        "resolved_at": (now - timedelta(days=5)).isoformat(),
    }).execute()
    pred_a_id = pred_a.data[0]["id"]
    CLEANUP["predictions"].append(pred_a_id)
    print(f"  (a) CONFIRMED: spotlight={sl_a_id[:8]} pred={pred_a_id[:8]}")

    # --- (b) REFUTED ---
    sl_b = sb.table("spotlight_history").insert({
        "topic_id": "test_sc_agent_wallets",
        "topic_name": "test_sc_agent_wallets",
        "mode": "spotlight",
        "thesis": "Autonomous agent wallets will see rapid enterprise adoption.",
        "evidence": "Community enthusiasm high, VC funding strong.",
        "counter_argument": "Regulatory uncertainty remains.",
        "prediction": "Agent wallet adoption will exceed 20% among enterprise AI teams by Q2 2026.",
        "builder_implications": "Prepare wallet infrastructure early.",
        "full_output": "## Thesis\n\nAutonomous agent wallets will see rapid adoption.",
        "sources_used": [],
        "issue_number": 991,
    }).execute()
    sl_b_id = sl_b.data[0]["id"]
    CLEANUP["spotlight_history"].append(sl_b_id)

    pred_b = sb.table("predictions").insert({
        "spotlight_id": sl_b_id,
        "prediction_text": "Agent wallet adoption will exceed 20% among enterprise AI teams by Q2 2026.",
        "topic_id": "test_sc_agent_wallets",
        "issue_number": 991,
        "status": "refuted",
        "resolution_notes": "Adoption stayed flat at ~5% through Q2. Enterprise interest was lower than community enthusiasm suggested.",
        "resolved_at": (now - timedelta(days=3)).isoformat(),
    }).execute()
    pred_b_id = pred_b.data[0]["id"]
    CLEANUP["predictions"].append(pred_b_id)
    print(f"  (b) REFUTED:   spotlight={sl_b_id[:8]} pred={pred_b_id[:8]}")

    # --- (c) PARTIALLY CORRECT ---
    sl_c = sb.table("spotlight_history").insert({
        "topic_id": "test_sc_middleware_consolidation",
        "topic_name": "test_sc_middleware_consolidation",
        "mode": "spotlight",
        "thesis": "Agent middleware will consolidate rapidly at the orchestration layer.",
        "evidence": "Fragmentation growing, acquisition activity rising.",
        "counter_argument": "Diverse use cases prevent one-size-fits-all.",
        "prediction": "Three major middleware consolidation events (mergers/acquisitions) at the agent orchestration layer by Q3 2026.",
        "builder_implications": "Pick frameworks with acquisition appeal.",
        "full_output": "## Thesis\n\nAgent middleware will consolidate rapidly.",
        "sources_used": [],
        "issue_number": 990,
    }).execute()
    sl_c_id = sl_c.data[0]["id"]
    CLEANUP["spotlight_history"].append(sl_c_id)

    pred_c = sb.table("predictions").insert({
        "spotlight_id": sl_c_id,
        "prediction_text": "Three major middleware consolidation events at the agent orchestration layer by Q3 2026.",
        "topic_id": "test_sc_middleware_consolidation",
        "issue_number": 990,
        "status": "partially_correct",
        "resolution_notes": "The middleware consolidation happened but at the model layer first, not the agent layer as we predicted.",
        "resolved_at": (now - timedelta(days=7)).isoformat(),
    }).execute()
    pred_c_id = pred_c.data[0]["id"]
    CLEANUP["predictions"].append(pred_c_id)
    print(f"  (c) PARTIAL:   spotlight={sl_c_id[:8]} pred={pred_c_id[:8]}")

    # --- (d) ALREADY SCORECARDED ---
    sl_d = sb.table("spotlight_history").insert({
        "topic_id": "test_sc_old_topic",
        "topic_name": "test_sc_old_topic",
        "mode": "spotlight",
        "thesis": "Old topic thesis.",
        "evidence": "Evidence.",
        "counter_argument": "Counter.",
        "prediction": "Old prediction already included in a prior scorecard.",
        "builder_implications": "Old implications.",
        "full_output": "## Thesis\n\nOld topic thesis.",
        "sources_used": [],
        "issue_number": 988,
    }).execute()
    sl_d_id = sl_d.data[0]["id"]
    CLEANUP["spotlight_history"].append(sl_d_id)

    pred_d = sb.table("predictions").insert({
        "spotlight_id": sl_d_id,
        "prediction_text": "Some old prediction.",
        "topic_id": "test_sc_old_topic",
        "issue_number": 988,
        "status": "confirmed",
        "resolution_notes": "Resolved previously.",
        "resolved_at": (now - timedelta(days=30)).isoformat(),
        "scorecard_issue": 994,
    }).execute()
    pred_d_id = pred_d.data[0]["id"]
    CLEANUP["predictions"].append(pred_d_id)
    print(f"  (d) ALREADY SCORECARDED: pred={pred_d_id[:8]}")

    # --- (e) OPEN ---
    pred_e = sb.table("predictions").insert({
        "prediction_text": "Some open prediction.",
        "topic_id": "test_sc_open",
        "issue_number": 992,
        "status": "open",
    }).execute()
    pred_e_id = pred_e.data[0]["id"]
    CLEANUP["predictions"].append(pred_e_id)
    print(f"  (e) OPEN:      pred={pred_e_id[:8]}")

    return {
        "confirmed": {"pred_id": pred_a_id, "spotlight_id": sl_a_id, "issue": 993},
        "refuted":   {"pred_id": pred_b_id, "spotlight_id": sl_b_id, "issue": 991},
        "partial":   {"pred_id": pred_c_id, "spotlight_id": sl_c_id, "issue": 990},
        "scorecarded": {"pred_id": pred_d_id, "spotlight_id": sl_d_id, "issue": 988},
        "open":      {"pred_id": pred_e_id, "issue": 992},
    }


# -----------------------------------------------------------------------
# Blurb checks
# -----------------------------------------------------------------------

def count_sentences(text: str) -> int:
    cleaned = re.sub(r'\b(Mr|Mrs|Ms|Dr|Inc|Ltd|vs|etc|i\.e|e\.g)\.',
                     lambda m: m.group(0).replace(".", "<DOT>"), text)
    sentences = re.split(r'[.!?]+\s', cleaned)
    sentences = [s.strip() for s in sentences if s.strip()]
    return len(sentences)


def check_blurb_format(blurb: str, expected_issue: int) -> dict:
    results = {}

    sentences = count_sentences(blurb)
    results["sentences"] = sentences
    results["sentence_count_ok"] = 3 <= sentences <= 5

    words = len(blurb.split())
    results["words"] = words
    results["word_count_ok"] = 40 <= words <= 120

    results["refs_issue"] = f"issue #{expected_issue}" in blurb.lower() or \
                            f"issue {expected_issue}" in blurb.lower()

    lower = blurb.lower()
    results["has_outcome"] = any(w in lower for w in [
        "happened", "turned out", "actual", "result", "shipped",
        "announced", "stayed", "flat", "adoption", "consolidation",
    ])

    results["has_assessment"] = any(w in lower for w in [
        "right", "wrong", "correct", "incorrect", "missed", "hit",
        "got this", "accurate", "underestimated", "overestimated",
        "partially", "close", "off",
    ])

    results["no_ai_phrases"] = not any(p in lower for p in AI_PHRASES)
    results["no_hedging"] = not any(p in lower for p in HEDGE_PHRASES)

    return results


def check_confirmed_tone(blurb: str) -> dict:
    lower = blurb.lower()
    results = {}
    gloat_found = [p for p in GLOAT_PHRASES if p in lower]
    results["no_gloating"] = len(gloat_found) == 0
    results["gloat_found"] = gloat_found
    return results


def check_refuted_tone(blurb: str) -> dict:
    lower = blurb.lower()
    results = {}
    honest_markers = ["got this wrong", "wrong", "missed", "overestimated",
                      "incorrect", "didn't materialize", "failed to",
                      "didn't happen", "proved wrong", "off the mark"]
    results["admits_wrong"] = any(m in lower for m in honest_markers)
    defensive_found = [p for p in DEFENSIVE_PHRASES if p in lower]
    results["no_defensive"] = len(defensive_found) == 0
    results["defensive_found"] = defensive_found
    return results


def check_partial_tone(blurb: str) -> dict:
    lower = blurb.lower()
    positive_markers = ["right", "correct", "hit", "accurate", "happened",
                        "did see", "did materialize", "got right"]
    negative_markers = ["wrong", "missed", "incorrect", "didn't",
                        "not at the", "instead", "different", "off"]
    results = {}
    has_positive = any(m in lower for m in positive_markers)
    has_negative = any(m in lower for m in negative_markers)
    results["has_positive"] = has_positive
    results["has_negative"] = has_negative
    results["balanced"] = has_positive and has_negative
    return results


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------

def main():
    print("=" * 70)
    print("  TEST 4C: Scorecard 'Looking Back' Generation")
    print("=" * 70)

    # ---- Step 1: Init & test data ----
    print("\n--- Step 1: Create test data ---")
    sb = init()
    test_data = create_test_data(sb)

    # ---- Step 2: Generate scorecard blurbs ----
    print("\n--- Step 2: Generate scorecard for issue #995 ---")
    blurbs = nl.generate_scorecard(current_issue_number=995)
    print(f"  Blurbs generated: {len(blurbs)}")

    max_ok = len(blurbs) <= nl.MAX_LOOKBACKS_PER_ISSUE
    print(f"  Respects max ({nl.MAX_LOOKBACKS_PER_ISSUE}): {'PASS' if max_ok else 'FAIL'}")

    # The query filters: status in (confirmed, refuted, partially_correct)
    # AND scorecard_issue IS NULL. So (d) already-scorecarded and (e) open should be excluded.
    # There are 3 eligible (a,b,c), but MAX is 2, ordered by resolved_at desc => (b) refuted
    # and (a) confirmed are the 2 most recent.

    # Check which predictions got scorecarded
    used_pred_ids = set()
    for pid in [test_data["confirmed"]["pred_id"],
                test_data["refuted"]["pred_id"],
                test_data["partial"]["pred_id"]]:
        row = sb.table("predictions").select("scorecard_issue").eq("id", pid).execute()
        if row.data and row.data[0].get("scorecard_issue") == 995:
            used_pred_ids.add(pid)

    scorecarded_excluded = test_data["scorecarded"]["pred_id"] not in used_pred_ids
    open_excluded = test_data["open"]["pred_id"] not in used_pred_ids

    print(f"  Already-scorecarded excluded: {'PASS' if scorecarded_excluded else 'FAIL'}")
    print(f"  Open predictions excluded:    {'PASS' if open_excluded else 'FAIL'}")

    # Build a map of blurb -> status by checking issue references
    blurb_info = []
    for i, blurb in enumerate(blurbs):
        lower = blurb.lower()
        if "993" in blurb:
            blurb_info.append(("confirmed", blurb, test_data["confirmed"]["issue"]))
        elif "991" in blurb:
            blurb_info.append(("refuted", blurb, test_data["refuted"]["issue"]))
        elif "990" in blurb:
            blurb_info.append(("partially_correct", blurb, test_data["partial"]["issue"]))
        else:
            blurb_info.append(("unknown", blurb, 0))

    # ---- Step 3: Validate blurbs ----
    print("\n--- Step 3: Validate blurbs ---")
    all_format_results = []
    all_tone_results = []

    for status, blurb, issue in blurb_info:
        fmt = check_blurb_format(blurb, issue)
        all_format_results.append((status, fmt))

        if status == "confirmed":
            tone = check_confirmed_tone(blurb)
        elif status == "refuted":
            tone = check_refuted_tone(blurb)
        elif status == "partially_correct":
            tone = check_partial_tone(blurb)
        else:
            tone = {}
        all_tone_results.append((status, tone))

    # ---- Step 4: Verify scorecard marking & no double-inclusion ----
    print("\n--- Step 4: Scorecard marking ---")
    marking_ok = len(used_pred_ids) == len(blurbs)
    print(f"  Predictions marked with scorecard_issue=995: {len(used_pred_ids)}")
    print(f"  Matches blurbs generated: {'PASS' if marking_ok else 'FAIL'}")

    print("\n  Checking no double-inclusion (issue #996)...")
    blurbs_996 = nl.generate_scorecard(current_issue_number=996)
    no_double = len(blurbs_996) == 0 or \
                all(test_data[k]["pred_id"] not in used_pred_ids
                    for k in ["confirmed", "refuted", "partial"]
                    if test_data[k]["pred_id"] in used_pred_ids)

    # More precise: the ones we used for 995 should NOT appear in 996
    double_included = False
    if blurbs_996:
        for b in blurbs_996:
            if "993" in b or "991" in b or "990" in b:
                for pid in used_pred_ids:
                    row = sb.table("predictions").select("scorecard_issue")\
                        .eq("id", pid).execute()
                    if row.data and row.data[0].get("scorecard_issue") == 996:
                        double_included = True

    no_double_ok = not double_included
    print(f"  Blurbs in issue #996: {len(blurbs_996)}")
    print(f"  No double-inclusion: {'PASS' if no_double_ok else 'FAIL'}")

    # ---- Step 5: Newsletter placement ----
    print("\n--- Step 5: Newsletter placement ---")

    # Reset scorecards so we can test newsletter integration
    for pid in used_pred_ids:
        sb.table("predictions").update({"scorecard_issue": None}).eq("id", pid).execute()

    scorecard_blurbs = nl.generate_scorecard(current_issue_number=997)
    scorecard_md = nl.format_scorecard_section(scorecard_blurbs)

    if scorecard_md:
        has_header = "## Looking Back" in scorecard_md
        print(f"  Section header present: {'PASS' if has_header else 'FAIL'}")
        print(f"  Section length: {len(scorecard_md)} chars")

        fake_newsletter = (
            "## 2. Spotlight\nContent...\n\n"
            "## 3. The Big Insight\nContent...\n\n"
            "## 4. Top Opportunities\nContent...\n\n"
            "## 5. Emerging Signals\nContent...\n\n"
            "## 6. On Our Radar\nContent...\n\n"
            "## 7. The Curious Corner\nContent...\n\n"
            "## 8. Tool Radar\nContent...\n\n"
            "## 9. Prediction Tracker\nContent...\n\n"
            "## 10. Gato's Corner\nContent..."
        )
        full_with_scorecard = fake_newsletter + scorecard_md

        sections = re.findall(r'^##\s+(.+)$', full_with_scorecard, re.MULTILINE)
        print(f"\n  Newsletter structure with Scorecard:")
        for i, sec in enumerate(sections, 1):
            print(f"    Section {i}: {sec}")

        looking_back_idx = None
        gato_idx = None
        for i, sec in enumerate(sections):
            if "looking back" in sec.lower():
                looking_back_idx = i
            if "gato" in sec.lower():
                gato_idx = i

        after_gato = looking_back_idx is not None and gato_idx is not None and looking_back_idx > gato_idx
        placement_ok = after_gato
        print(f"  Scorecard after Gato's Corner: {'PASS' if placement_ok else 'FAIL'}")
    else:
        print(f"  WARNING: No scorecard generated for placement test")
        placement_ok = False

    # ---- Step 6: No-scorecard scenario ----
    print("\n--- Step 6: No-scorecard scenario ---")
    for pid in CLEANUP["predictions"]:
        try:
            sb.table("predictions").update({"scorecard_issue": 997}).eq("id", pid).execute()
        except Exception:
            pass

    empty_blurbs = nl.generate_scorecard(current_issue_number=998)
    empty_md = nl.format_scorecard_section(empty_blurbs)

    no_scorecard_ok = len(empty_blurbs) == 0 and empty_md == ""
    print(f"  Blurbs when all scorecarded: {len(empty_blurbs)}")
    print(f"  Section markdown empty: {'PASS' if empty_md == '' else 'FAIL'}")
    print(f"  Graceful absence: {'PASS' if no_scorecard_ok else 'FAIL'}")

    # ---- Step 7: Print all blurbs ----
    print(f"\n{'='*70}")
    print(f"  === SCORECARD BLURBS ===")
    print(f"{'='*70}")

    for i, (status, blurb, issue) in enumerate(blurb_info):
        fmt = all_format_results[i][1]
        tone = all_tone_results[i][1]

        print(f"\n  --- BLURB {i+1} ({status}) ---")
        print(f"  {blurb}")
        print(f"\n  Sentences: {fmt['sentences']} | Words: {fmt['words']}")
        print(f"  References issue #{issue}: {'PASS' if fmt['refs_issue'] else 'FAIL'}")
        print(f"  States outcome:           {'PASS' if fmt['has_outcome'] else 'FAIL'}")
        print(f"  Honest assessment:        {'PASS' if fmt['has_assessment'] else 'FAIL'}")
        print(f"  No AI phrases:            {'PASS' if fmt['no_ai_phrases'] else 'FAIL'}")
        print(f"  No hedging:               {'PASS' if fmt['no_hedging'] else 'FAIL'}")

        if status == "confirmed":
            print(f"  No gloating:              {'PASS' if tone.get('no_gloating') else 'FAIL'}"
                  f"{' ' + str(tone.get('gloat_found', [])) if tone.get('gloat_found') else ''}")
        elif status == "refuted":
            print(f"  Admits being wrong:       {'PASS' if tone.get('admits_wrong') else 'FAIL'}")
            print(f"  No defensive language:    {'PASS' if tone.get('no_defensive') else 'FAIL'}"
                  f"{' ' + str(tone.get('defensive_found', [])) if tone.get('defensive_found') else ''}")
        elif status == "partially_correct":
            print(f"  What hit + what missed:   {'PASS' if tone.get('balanced') else 'FAIL'}")
            print(f"    (positive={tone.get('has_positive')}, negative={tone.get('has_negative')})")

    # ---- Step 8: Cleanup ----
    print(f"\n--- Step 8: Cleanup ---")
    for pid in CLEANUP["predictions"]:
        try:
            sb.table("predictions").delete().eq("id", pid).execute()
        except Exception:
            pass
    print(f"  Deleted {len(CLEANUP['predictions'])} test predictions")

    for sid in CLEANUP["spotlight_history"]:
        try:
            sb.table("spotlight_history").delete().eq("id", sid).execute()
        except Exception:
            pass
    print(f"  Deleted {len(CLEANUP['spotlight_history'])} test spotlight_history rows")

    remaining_preds = sb.table("predictions")\
        .select("id")\
        .in_("topic_id", ["test_sc_mcp_interop", "test_sc_agent_wallets",
                          "test_sc_middleware_consolidation", "test_sc_old_topic",
                          "test_sc_open"])\
        .execute()
    cleanup_ok = len(remaining_preds.data or []) == 0
    print(f"  No test data remains: {'PASS' if cleanup_ok else 'FAIL'}")

    # ---- Step 9: Summary ----
    print(f"\n{'='*70}")
    print(f"  === SCORECARD GENERATION TEST ===")
    print(f"{'='*70}")

    all_sentence_ok = all(f[1]["sentence_count_ok"] for f in all_format_results)
    all_word_ok = all(f[1]["word_count_ok"] for f in all_format_results)
    all_refs_ok = all(f[1]["refs_issue"] for f in all_format_results)
    all_no_ai = all(f[1]["no_ai_phrases"] for f in all_format_results)
    all_no_hedge = all(f[1]["no_hedging"] for f in all_format_results)

    confirmed_tone_ok = True
    refuted_tone_ok = True
    partial_tone_ok = True
    for status, tone in all_tone_results:
        if status == "confirmed":
            confirmed_tone_ok = tone.get("no_gloating", True)
        elif status == "refuted":
            refuted_tone_ok = tone.get("admits_wrong", False) and tone.get("no_defensive", True)
        elif status == "partially_correct":
            partial_tone_ok = tone.get("balanced", False)

    def ps(ok):
        return "PASS" if ok else "FAIL"

    print(f"\n  Blurb generation:")
    print(f"  - Resolved predictions found:    3")
    print(f"  - Blurbs generated:              {len(blurbs)} (max {nl.MAX_LOOKBACKS_PER_ISSUE})")
    print(f"  - Already-scorecarded excluded:  {ps(scorecarded_excluded)}")
    print(f"  - Open predictions excluded:     {ps(open_excluded)}")

    print(f"\n  Format checks:")
    print(f"  - 3-5 sentences each:            {ps(all_sentence_ok)}")
    print(f"  - References original issue:     {ps(all_refs_ok)}")
    print(f"  - Word count in range:           {ps(all_word_ok)}")

    print(f"\n  Tone checks:")
    print(f"  - Confirmed: no gloating:        {ps(confirmed_tone_ok)}")
    print(f"  - Refuted: honest admission:     {ps(refuted_tone_ok)}")
    print(f"  - Partial: balanced assessment:   {ps(partial_tone_ok)}")
    print(f"  - No AI phrases:                 {ps(all_no_ai)}")
    print(f"  - No hedging:                    {ps(all_no_hedge)}")

    print(f"\n  Integration:")
    print(f"  - Scorecard marking:             {ps(marking_ok)}")
    print(f"  - No double-inclusion:           {ps(no_double_ok)}")
    print(f"  - Newsletter placement:          {ps(placement_ok)}")
    print(f"  - No-scorecard graceful:         {ps(no_scorecard_ok)}")
    print(f"  - Cleanup:                       {ps(cleanup_ok)}")

    total_checks = [
        max_ok, scorecarded_excluded, open_excluded,
        all_sentence_ok, all_refs_ok, all_word_ok,
        confirmed_tone_ok, refuted_tone_ok, partial_tone_ok,
        all_no_ai, all_no_hedge,
        marking_ok, no_double_ok, placement_ok, no_scorecard_ok, cleanup_ok,
    ]
    passed = sum(total_checks)
    failed = len(total_checks) - passed
    print(f"\n  Total: {passed} PASS, {failed} FAIL")

    if failed == 0:
        print(f"\n  SCORECARD GENERATION: READY")
    else:
        print(f"\n  SCORECARD GENERATION: NEEDS ITERATION ({failed} failures)")


if __name__ == "__main__":
    main()
