#!/usr/bin/env python3
"""
Phase 27 / Plan 02 — fail-loud persistence helper for the `edition_evals` table.

This is the thin persistence surface both eval layers (Phases 28/29) write through
rather than re-implementing the contract inline (D-08). It encodes the milestone-wide
fail-loud / no-silent-zero invariant (EVAL-02) and the no-in-list-filter rule (EVAL-03):

  - write_eval_row() writes ONE edition_evals row per draft per layer per attempt.
    An eval that errored writes eval_status='error' + a non-null `error` reason and a
    NULL verdict — NEVER a silent zero score (a proxy 402 / cap-hit is an error state,
    not a `0`). (D-09 a/b)
  - The Python-side verdict-iff-ok validation mirrors the DB
    `edition_evals_verdict_iff_ok` CHECK and runs BEFORE any insert, raising ValueError
    on any inconsistent (eval_status / verdict / error) combination — the in-memory test
    stub does not enforce DB CHECKs, so the helper must.
  - A failed insert is logged ERROR with exc_info=True and re-raised — never a bare
    except, never swallowed; a caller cannot silently continue as if the row landed.
    (D-09 c)
  - read_evals_by_newsletter() and read_eval_trend() use plain supabase-py `.eq()` only —
    the known supabase-py in-list filter (the silent-failure bug) is used NOWHERE in this
    module (EVAL-03). (D-09 d)

This phase makes NO LLM calls and wires NO caller into the live newsletter path. The
LLM_PROXY_EVAL_KEY identity getter below is established for the Phase 28 judge's proxy
calls (the eval agent's OWN governed identity, D-15) but is NEVER invoked here.
"""
import logging
import os

# Reuse the newsletter service's logger name so eval telemetry threads into the same
# log stream the operator already watches.
logger = logging.getLogger("newsletter-agent")

# The eval agent's OWN governed proxy identity (D-15 / GOV-01 / GOV-02). This is a
# SEPARATE wallet from the newsletter service's agent key — it must NOT reuse the
# newsletter service's own identity. The Phase 28 judge passes this key explicitly on its
# `llm-proxy:8200` calls so the proxy attributes spend to the `edition_eval` agent. NOT
# called this phase (no LLM calls in Phase 27); no anthropic/OpenAI client is built here.
LLM_PROXY_EVAL_KEY = os.getenv("LLM_PROXY_EVAL_KEY")


def _get_eval_api_key() -> str | None:
    """Return the eval agent's own LLM_PROXY_EVAL_KEY (D-15), or None if unset.

    This is the `edition_eval` identity for the Phase 28 judge's governed proxy calls —
    NOT the newsletter service's identity. It is read fresh from the environment so a
    late-bound `.env` value is picked up. The key is NEVER logged. Not invoked in
    Phase 27 (no LLM calls this phase).
    """
    return os.getenv("LLM_PROXY_EVAL_KEY") or None


# Allowed eval_status values mirrored from the migration-045 DDL (EVAL-01). The DB CHECK
# is authoritative; this Python guard exists because the in-memory test stub does not
# enforce DB CHECKs.
_EVAL_STATUSES = ("ok", "error")


def write_eval_row(
    supabase,
    *,
    newsletter_id,
    edition_number,
    pipeline_version,
    attempt,
    layer,
    eval_status,
    verdict=None,
    error=None,
    deterministic_flags=None,
    judge_scores=None,
    judge_feedback=None,
    sats_spent=0,
    model_calls=None,
) -> str | None:
    """Write ONE fail-loud row to `edition_evals` and return the inserted id.

    `supabase` is the FIRST positional param (mirrors load_edition_context) so callers —
    and the fixture test's in-memory stub — pass the client explicitly; there is no
    module-global client.

    Fail-loud contract (D-09), enforced BEFORE the insert:
      - eval_status MUST be one of ('ok', 'error')                 -> else ValueError.
      - eval_status='ok'    => verdict NOT NULL AND error NULL      (a real eval ran).
      - eval_status='error' => verdict NULL     AND error NOT NULL  (an error is never a 0).
        Any other (eval_status / verdict / error) combination raises ValueError — the
        Python mirror of the DB `edition_evals_verdict_iff_ok` CHECK (the stub won't
        enforce it).

    On insert failure: log ERROR (exc_info=True, naming newsletter_id/layer/attempt — never
    the api key) and re-raise the original exception. Never swallowed (D-09 c / T-27-04).
    """
    if eval_status not in _EVAL_STATUSES:
        raise ValueError(
            f"eval_status must be one of {_EVAL_STATUSES}, got {eval_status!r}"
        )

    # Python mirror of edition_evals_verdict_iff_ok (D-09 a/b): a verdict exists IFF the
    # eval ran cleanly; an errored eval carries a reason + NULL verdict, never a silent 0.
    ok_shape = eval_status == "ok" and verdict is not None and error is None
    err_shape = eval_status == "error" and verdict is None and error is not None
    if not (ok_shape or err_shape):
        raise ValueError(
            "verdict-iff-ok violation: 'ok' requires (verdict NOT NULL AND error NULL); "
            "'error' requires (verdict NULL AND error NOT NULL); got "
            f"eval_status={eval_status!r} verdict={verdict!r} error={error!r}"
        )

    payload = {
        "newsletter_id": newsletter_id,
        "edition_number": edition_number,
        "pipeline_version": pipeline_version,
        "attempt": attempt,
        "layer": layer,
        "eval_status": eval_status,
        "error": error,
        "verdict": verdict,
        "deterministic_flags": deterministic_flags if deterministic_flags is not None else {},
        "judge_scores": judge_scores if judge_scores is not None else {},
        "judge_feedback": judge_feedback,
        "sats_spent": sats_spent,
        "model_calls": model_calls if model_calls is not None else [],
    }

    try:
        result = supabase.table("edition_evals").insert(payload).execute()
    except Exception:
        # DIVERGE from the poller's fail-SOFT telemetry inserts: the eval-row write is
        # fail-LOUD. A swallowed write would let a caller continue as if the governance
        # telemetry landed — the exact silent-data-loss class this milestone fights
        # (D-09 c / T-27-04). Name only newsletter_id/layer/attempt; never the api key.
        logger.error(
            "edition_evals write failed for newsletter_id=%s layer=%s attempt=%s",
            newsletter_id,
            layer,
            attempt,
            exc_info=True,
        )
        raise

    return result.data[0]["id"] if result.data else None


def read_evals_by_newsletter(supabase, newsletter_id) -> list:
    """Return all eval rows for one newsletter, ordered by attempt — `.eq()` only (EVAL-03)."""
    result = (
        supabase.table("edition_evals")
        .select("*")
        .eq("newsletter_id", newsletter_id)
        .order("attempt")
        .execute()
    )
    return result.data or []


def read_eval_trend(supabase, pipeline_version, limit=8) -> list:
    """Return the recent verdict trend for one pipeline_version, newest edition first.

    Powers Phase 31's SURF-03 trend render. `.eq()` only — the supabase-py in-list filter
    is never used on a list of edition numbers (EVAL-03 / the known silent-failure bug);
    Python parses the returned `judge_scores` JSONB dicts where per-dimension detail is
    needed (D-06).
    """
    result = (
        supabase.table("edition_evals")
        .select(
            "edition_number, pipeline_version, layer, attempt, eval_status, "
            "verdict, judge_scores, sats_spent, created_at"
        )
        .eq("pipeline_version", pipeline_version)
        .order("edition_number", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []
