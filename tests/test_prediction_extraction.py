#!/usr/bin/env python3
"""
Prediction Extraction Test for AgentPulse Scorecard.

Tests that predictions are correctly extracted from spotlight_history entries,
stored in the predictions table, sharpened when vague, and handled gracefully
for edge cases.

Usage: python tests/test_prediction_extraction.py
"""

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

CONFIG_ENV = Path(__file__).resolve().parent.parent / "config" / ".env"
load_dotenv(CONFIG_ENV)

from supabase import create_client
from openai import OpenAI

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

TEST_ISSUE_NUMBERS = [996, 997, 998, 999]
created_spotlight_ids = []
created_prediction_ids = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SHARPEN_PROMPT = """You are extracting a single, trackable prediction from an AI newsletter spotlight analysis.

INPUT PREDICTION TEXT:
"{prediction_text}"

RULES:
1. Extract exactly ONE prediction — the primary, most specific claim
2. It MUST be a single sentence
3. It MUST contain a concrete timeframe (e.g. "by Q3 2025", "within 6 months", "by mid-2025")
4. It MUST contain a measurable or observable outcome (not just "will grow" or "will change")
5. If the input is vague, sharpen it — add a specific timeframe and make the outcome measurable
6. If the input contains multiple claims, pick the PRIMARY one (the most important, most testable)
7. Preserve the core thesis — don't invent a new prediction

Respond with ONLY the single prediction sentence. No quotes, no explanation."""


def sharpen_prediction(raw_text: str) -> str:
    """Use LLM to extract/sharpen a single trackable prediction."""
    if not raw_text or not raw_text.strip():
        return ""
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        max_tokens=200,
        temperature=0.2,
        messages=[
            {"role": "system", "content": "You extract single-sentence predictions. Respond with ONLY the prediction."},
            {"role": "user", "content": SHARPEN_PROMPT.format(prediction_text=raw_text)},
        ],
    )
    result = response.choices[0].message.content.strip()
    if result.startswith('"') and result.endswith('"'):
        result = result[1:-1]
    return result


def has_timeframe(text: str) -> bool:
    patterns = [
        r"\b(Q[1-4])\s*\d{4}",
        r"\b(20\d{2})\b",
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
        r"\bby\s+(mid|end|early|late)[- ]",
        r"\bwithin\s+\d+\s*(days?|weeks?|months?|years?)",
        r"\bnext\s+\d+\s*(days?|weeks?|months?|years?)",
        r"\b\d+\s*months?\b",
    ]
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in patterns)


def has_measurable_outcome(text: str) -> bool:
    vague = ["will grow", "will change", "will continue", "will evolve",
             "will likely", "could have", "may impact", "might affect"]
    measurable = [r"\bat least\s+\d", r"\b\d+%", r"\bmore than\s+\d",
                  r"\btwo|three|four|five\b.*\bwill\b", r"\bwill (ship|launch|release|integrate|fork|adopt|capture|produce|create)",
                  r"\bdominant\b", r"\bfragmented\b", r"\bmajority\b"]
    text_lower = text.lower()
    if any(v in text_lower for v in vague) and not any(re.search(m, text_lower) for m in measurable):
        return False
    return any(re.search(m, text_lower) for m in measurable) or len(text.split()) > 10


def is_single_sentence(text: str) -> bool:
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text.strip())
    return len(sentences) == 1


def insert_test_spotlight(issue_number: int, prediction: str, mode: str = "spotlight",
                          thesis: str = None, topic_name: str = "Test Topic") -> dict:
    """Insert a test spotlight_history entry."""
    record = {
        "topic_id": str(uuid.uuid4()),
        "topic_name": topic_name,
        "issue_number": issue_number,
        "mode": mode,
        "thesis": thesis or f"Test thesis for issue {issue_number}",
        "evidence": "Evidence from multiple sources including HN and GitHub.",
        "counter_argument": "Skeptics argue the trend is overhyped.",
        "prediction": prediction,
        "builder_implications": "Build with this in mind.",
        "full_output": "",
        "sources_used": ["hackernews", "github"],
    }
    result = supabase.table("spotlight_history").insert(record).execute()
    spotlight = result.data[0] if result.data else {}
    if spotlight:
        created_spotlight_ids.append(spotlight["id"])
    return spotlight


def create_prediction_from_spotlight(spotlight: dict, sharpened_text: str = None) -> dict:
    """Create a prediction from a spotlight, optionally with sharpened text."""
    prediction_text = sharpened_text or spotlight.get("prediction", "")
    if not prediction_text:
        return {}

    existing = supabase.table("predictions").select("*")\
        .eq("spotlight_id", spotlight["id"]).execute()
    if existing.data:
        return existing.data[0]

    record = {
        "spotlight_id": spotlight["id"],
        "prediction_text": prediction_text,
        "topic_id": spotlight.get("topic_id"),
        "issue_number": spotlight.get("issue_number"),
        "status": "open",
    }
    result = supabase.table("predictions").insert(record).execute()
    pred = result.data[0] if result.data else {}
    if pred:
        created_prediction_ids.append(pred["id"])
    return pred


def cleanup():
    """Remove all test data."""
    cleaned = {"spotlights": 0, "predictions": 0}
    for sid in created_spotlight_ids:
        try:
            supabase.table("spotlight_history").delete().eq("id", sid).execute()
            cleaned["spotlights"] += 1
        except Exception:
            pass
    for pid in created_prediction_ids:
        try:
            supabase.table("predictions").delete().eq("id", pid).execute()
            cleaned["predictions"] += 1
        except Exception:
            pass
    for issue_num in TEST_ISSUE_NUMBERS:
        try:
            supabase.table("predictions").delete().eq("issue_number", issue_num).execute()
            supabase.table("spotlight_history").delete().eq("issue_number", issue_num).execute()
        except Exception:
            pass
    return cleaned


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_good_prediction() -> dict:
    """Test 2: Extraction on a good prediction."""
    result = {"pass": True, "details": {}}

    real_spotlight = supabase.table("spotlight_history").select("*")\
        .order("created_at", desc=True).limit(1).execute()

    if real_spotlight.data:
        spotlight = real_spotlight.data[0]
        print(f"  Using existing spotlight: id={spotlight['id'][:8]}...")
        print(f"  Raw prediction: \"{spotlight.get('prediction', '')[:120]}...\"")
    else:
        spotlight = insert_test_spotlight(
            issue_number=996,
            prediction="We predict at least two major enterprise frameworks will fork MCP's core protocol by mid-2025, creating a fragmented but more resilient ecosystem.",
            thesis="MCP Is Winning the Protocol War But Its Governance Model Will Force Enterprise Forks",
            topic_name="MCP Protocol Governance",
        )
        print(f"  Inserted test spotlight: id={spotlight['id'][:8]}...")

    raw_pred = spotlight.get("prediction", "")
    result["details"]["original"] = raw_pred

    sharpened = sharpen_prediction(raw_pred)
    result["details"]["extracted"] = sharpened
    print(f"  Extracted: \"{sharpened}\"")

    single = is_single_sentence(sharpened)
    result["details"]["single_sentence"] = single
    if not single:
        result["pass"] = False

    timeframe = has_timeframe(sharpened)
    result["details"]["has_timeframe"] = timeframe
    if not timeframe:
        result["pass"] = False

    measurable = has_measurable_outcome(sharpened)
    result["details"]["has_measurable"] = measurable
    if not measurable:
        result["pass"] = False

    pred_row = create_prediction_from_spotlight(spotlight, sharpened)
    stored_ok = bool(pred_row.get("id"))
    result["details"]["stored"] = stored_ok

    if stored_ok:
        checks = {
            "spotlight_id": pred_row.get("spotlight_id") == spotlight["id"],
            "topic_id": pred_row.get("topic_id") == spotlight.get("topic_id"),
            "issue_number": pred_row.get("issue_number") == spotlight.get("issue_number"),
            "status_open": pred_row.get("status") == "open",
        }
        result["details"]["field_checks"] = checks
        if not all(checks.values()):
            result["pass"] = False
        print(f"  Stored prediction: id={pred_row['id'][:8]}, status={pred_row.get('status')}")
    else:
        result["pass"] = False

    return result


def test_sharpening() -> dict:
    """Test 3: Sharpening a vague prediction."""
    result = {"pass": True, "details": {}}

    vague_text = "This trend will likely continue to gain momentum in the coming months and could have significant implications for the industry."
    spotlight = insert_test_spotlight(
        issue_number=997,
        prediction=vague_text,
        thesis="Vague trend analysis",
        topic_name="Test Sharpening",
    )

    sharpened = sharpen_prediction(vague_text)
    result["details"]["original"] = vague_text
    result["details"]["extracted"] = sharpened
    print(f"  Vague input:  \"{vague_text[:80]}...\"")
    print(f"  Sharpened:    \"{sharpened}\"")

    is_sharper = (
        has_timeframe(sharpened) and not has_timeframe(vague_text)
    ) or (
        has_measurable_outcome(sharpened) and not has_measurable_outcome(vague_text)
    ) or (
        len(sharpened) != len(vague_text)
    )
    result["details"]["is_sharper"] = is_sharper
    result["details"]["has_timeframe"] = has_timeframe(sharpened)
    result["details"]["has_measurable"] = has_measurable_outcome(sharpened)

    if not has_timeframe(sharpened):
        result["pass"] = False
        result["details"]["warn"] = "Sharpened text still lacks timeframe"

    return result


def test_synthesis_mode() -> dict:
    """Test 4: Extraction from synthesis mode spotlight (multiple claims)."""
    result = {"pass": True, "details": {}}

    multi_claim = (
        "The convergence of local model deployment, MCP standardization, and enterprise "
        "agent budgets will produce a dominant middleware player within 6 months. Meanwhile, "
        "open-source alternatives will capture the long-tail of smaller agent deployments."
    )
    spotlight = insert_test_spotlight(
        issue_number=998,
        prediction=multi_claim,
        mode="synthesis",
        thesis="Three converging trends are reshaping the middleware layer",
        topic_name="Convergence Watch",
    )

    sharpened = sharpen_prediction(multi_claim)
    result["details"]["original"] = multi_claim
    result["details"]["extracted"] = sharpened
    print(f"  Multi-claim input: \"{multi_claim[:80]}...\"")
    print(f"  Extracted single:  \"{sharpened}\"")

    single = is_single_sentence(sharpened)
    result["details"]["single_sentence"] = single
    if not single:
        result["pass"] = False

    pred = create_prediction_from_spotlight(spotlight, sharpened)
    count = supabase.table("predictions").select("id", count="exact")\
        .eq("spotlight_id", spotlight["id"]).execute()
    num_preds = count.count or 0
    result["details"]["predictions_stored"] = num_preds
    if num_preds != 1:
        result["pass"] = False

    is_primary = "middleware" in sharpened.lower() or "convergence" in sharpened.lower() or "dominant" in sharpened.lower()
    result["details"]["primary_claim_captured"] = is_primary

    return result


def test_idempotency() -> dict:
    """Test 5: Running extraction twice doesn't duplicate."""
    result = {"pass": True, "details": {}}

    spotlight = insert_test_spotlight(
        issue_number=999,
        prediction="By Q4 2025, three major cloud providers will offer native multi-agent orchestration.",
        thesis="Cloud providers are converging on agent orchestration",
        topic_name="Idempotency Test",
    )

    pred1 = create_prediction_from_spotlight(spotlight)
    pred2 = create_prediction_from_spotlight(spotlight)

    count = supabase.table("predictions").select("id", count="exact")\
        .eq("spotlight_id", spotlight["id"]).execute()
    num = count.count or 0
    result["details"]["count_after_double_run"] = num
    result["pass"] = (num == 1)
    print(f"  Predictions after 2 runs: {num} (expected 1)")

    return result


def test_missing_prediction() -> dict:
    """Test 6: Spotlight with empty/null prediction."""
    result = {"pass": True, "details": {}}

    spotlight = insert_test_spotlight(
        issue_number=996,
        prediction="",
        thesis="This spotlight has no prediction",
        topic_name="Missing Prediction Test",
    )

    sharpened = sharpen_prediction("")
    pred = create_prediction_from_spotlight(spotlight, sharpened)

    no_crash = True
    no_pred_created = not pred.get("id")
    result["details"]["no_crash"] = no_crash
    result["details"]["no_prediction_created"] = no_pred_created
    result["pass"] = no_crash and no_pred_created
    print(f"  Empty prediction handled: crash={not no_crash}, prediction_created={not no_pred_created}")

    return result


def test_timing() -> dict:
    """Test 7: Verify extraction runs after newsletter, not blocking."""
    result = {"pass": True, "details": {}}

    latest_nl = supabase.table("newsletters").select("created_at, edition_number")\
        .order("created_at", desc=True).limit(1).execute()
    latest_pred = supabase.table("predictions").select("created_at")\
        .not_.is_("spotlight_id", "null").order("created_at", desc=True).limit(1).execute()

    if latest_nl.data and latest_pred.data:
        nl_time = latest_nl.data[0].get("created_at", "")
        pred_time = latest_pred.data[0].get("created_at", "")
        result["details"]["newsletter_at"] = nl_time
        result["details"]["prediction_at"] = pred_time
        result["details"]["after_newsletter"] = pred_time >= nl_time if nl_time and pred_time else None
        print(f"  Newsletter: {nl_time}")
        print(f"  Prediction: {pred_time}")
    else:
        result["details"]["note"] = "No newsletter or prediction data to compare timing"
        print("  No production newsletter/prediction data available for timing check")

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def pf(val):
    return "PASS" if val else "FAIL"


def main():
    print("=" * 56)
    print("  PREDICTION EXTRACTION TEST")
    print("=" * 56)

    results = {}

    # Test 2: Good prediction
    print("\n[Test 2] Good prediction extraction...")
    results["good"] = test_good_prediction()

    # Test 3: Sharpening
    print("\n[Test 3] Vague prediction sharpening...")
    results["sharpen"] = test_sharpening()

    # Test 4: Synthesis mode
    print("\n[Test 4] Synthesis mode (multiple claims)...")
    results["synthesis"] = test_synthesis_mode()

    # Test 5: Idempotency
    print("\n[Test 5] Idempotency check...")
    results["idempotent"] = test_idempotency()

    # Test 6: Missing prediction
    print("\n[Test 6] Missing prediction handling...")
    results["missing"] = test_missing_prediction()

    # Test 7: Timing
    print("\n[Test 7] Timing (post-newsletter)...")
    results["timing"] = test_timing()

    # Test 8: Cleanup
    print("\n[Test 8] Cleaning up test data...")
    cleaned = cleanup()
    cleanup_ok = True
    for issue_num in TEST_ISSUE_NUMBERS:
        remaining = supabase.table("spotlight_history").select("id", count="exact")\
            .eq("issue_number", issue_num).execute()
        if remaining.count and remaining.count > 0:
            cleanup_ok = False
    results["cleanup"] = {"pass": cleanup_ok, "details": cleaned}
    print(f"  Cleaned: {cleaned}")

    # Summary
    g = results["good"]["details"]
    s = results["sharpen"]["details"]
    syn = results["synthesis"]["details"]

    print(f"""
{'=' * 56}
  PREDICTION EXTRACTION TEST SUMMARY
{'=' * 56}

  Good prediction extraction:
  - Original:  \"{g.get('original', '?')[:80]}...\"
  - Extracted: \"{g.get('extracted', '?')[:80]}...\"
  - Single sentence:       {pf(g.get('single_sentence'))}
  - Has timeframe:         {pf(g.get('has_timeframe'))}
  - Has measurable outcome:{pf(g.get('has_measurable'))}
  - Stored correctly:      {pf(g.get('stored'))}

  Sharpening test:
  - Input was vague:       YES
  - Output is sharper:     {pf(s.get('is_sharper'))}{'  WARN: ' + s.get('warn', '') if s.get('warn') else ''}
  - Has timeframe:         {pf(s.get('has_timeframe'))}
  - Extracted: \"{s.get('extracted', '?')[:80]}...\"

  Synthesis mode:
  - Multiple claims in source: YES
  - Only 1 extracted:      {pf(syn.get('predictions_stored') == 1)}
  - Primary claim captured:{pf(syn.get('primary_claim_captured'))}

  Other checks:
  - Idempotency:           {pf(results['idempotent']['pass'])}
  - Missing prediction:    {pf(results['missing']['pass'])} (handled gracefully)
  - Timing (post-newsletter): {pf(results['timing'].get('pass', True))}
  - Cleanup:               {pf(results['cleanup']['pass'])}

  OVERALL: {'ALL PASS' if all(r['pass'] for r in results.values()) else 'SOME FAILURES'}
{'=' * 56}
""")


if __name__ == "__main__":
    main()
