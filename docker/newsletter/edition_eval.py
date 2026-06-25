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


# Value-domains mirrored from the migration-045 DDL CHECKs (EVAL-01). The DB CHECKs are
# authoritative; these Python guards exist because the in-memory test stub does not enforce
# them. Mirroring the FULL domains (not just nullness) closes the silent-zero gap: a numeric
# `0` or empty-string verdict (`0 is not None` / `"" is not None`) is rejected here exactly
# as the DB `verdict IN (...)` CHECK would reject it — the no-silent-zero invariant this
# milestone exists to enforce (EVAL-02 / WR-01).
_EVAL_STATUSES = ("ok", "error")
_VERDICTS = ("passed", "held_fabrication", "held_voice", "escalated")
_PIPELINE_VERSIONS = ("single_pass", "block_v1")
_LAYERS = ("deterministic", "judge")


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
) -> str:
    """Write ONE fail-loud row to `edition_evals` and return the inserted id.

    Always returns the inserted id (str) on success, or raises — never returns None
    (a write that did not land is surfaced loudly, WR-02).

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
    # Mirror the DDL's pipeline_version / layer CHECK domains BEFORE the insert (the stub
    # won't): a bad enum would otherwise reach the DB and raise far from the call site.
    if pipeline_version not in _PIPELINE_VERSIONS:
        raise ValueError(
            f"pipeline_version must be one of {_PIPELINE_VERSIONS}, got {pipeline_version!r}"
        )
    if layer not in _LAYERS:
        raise ValueError(f"layer must be one of {_LAYERS}, got {layer!r}")

    # Python mirror of edition_evals_verdict_iff_ok (D-09 a/b) — STRENGTHENED to the full
    # value-domains (WR-01): an 'ok' eval's verdict must be a real verdict string IN the
    # enum (so a numeric 0 or "" — which pass `is not None` — are rejected, never a silent
    # zero); an errored eval carries a non-empty reason + NULL verdict (an empty error string
    # is not a real reason). This is exactly what the DB CHECK + `verdict IN (...)` enforce.
    ok_shape = eval_status == "ok" and verdict in _VERDICTS and error is None
    err_shape = (
        eval_status == "error"
        and verdict is None
        and isinstance(error, str)
        and error.strip() != ""
    )
    if not (ok_shape or err_shape):
        raise ValueError(
            "verdict-iff-ok violation: 'ok' requires (verdict IN "
            f"{_VERDICTS} AND error NULL); 'error' requires (verdict NULL AND a non-empty "
            f"error reason); got eval_status={eval_status!r} verdict={verdict!r} "
            f"error={error!r}"
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

    # Fail-loud on a successful-but-empty insert (WR-02): an insert that raised no exception
    # but returned no row is NOT a silent no-op the caller may continue past — that is the
    # same silent-data-loss class as a swallowed exception (D-09 c). Surface it loudly.
    if not result.data:
        logger.error(
            "edition_evals insert returned no row for newsletter_id=%s layer=%s attempt=%s",
            newsletter_id,
            layer,
            attempt,
        )
        raise RuntimeError(
            "edition_evals insert returned no row (no exception raised) for "
            f"newsletter_id={newsletter_id} layer={layer} attempt={attempt} — refusing to "
            "report a write that did not land (fail-loud, WR-02)"
        )
    return result.data[0]["id"]


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
