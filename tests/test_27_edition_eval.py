#!/usr/bin/env python3
"""
Phase 27 / Plan 02 — deterministic fixture suite for `edition_eval.write_eval_row`
and the `.eq()`-only readers.

Locks the D-08/D-09 fail-loud persistence contract BEFORE any Phase 28/29 caller spends
real eval budget through this helper:
  - the ok-row write (eval_status='ok', verdict NOT NULL, error NULL),
  - the error-row write (eval_status='error', verdict NULL, reason set) — proven to be a
    real error state, never a silent 0 score,
  - the verdict-iff-ok ValueError raised BEFORE any insert (the Python mirror of the DB
    CHECK; the in-memory stub does not enforce DB CHECKs),
  - the loud-raise-on-write-failure (ERROR logged + the original exception re-raised),
  - `.eq()`-only reads (the stub OMITS the supabase-py in-list filter so any accidental
    use would raise AttributeError — EVAL-03 / T-27-07).

This test imports the REAL `edition_eval` module (no re-implementation — the
test_19_smartquote rule / threat T-27-08). A copy could pass while production regresses.
`edition_eval.py` imports only stdlib and takes `supabase` as a parameter, so — unlike
the schemas-importing pollers — no conftest preload is needed; a plain sys.path insert
makes the REAL module importable. Every assertion runs against an in-memory Supabase
stub — never the live DB, never the network (threat: test must not touch live data).
"""
import logging
import sys
from pathlib import Path

import pytest

# Mirror test_26_continuity_loader.py's wiring: put docker/newsletter on sys.path and
# import the REAL production module. edition_eval imports only stdlib (logging, os) and
# has no `schemas` dependency, so no conftest preload is required.
NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
if str(NL_DIR) not in sys.path:
    sys.path.insert(0, str(NL_DIR))

import edition_eval as ee  # noqa: E402  — the REAL production module

# The id the insert stub reads back (mirrors newsletter_poller's insert-that-captures-id).
INSERT_ID = "00000000-0000-0000-0000-000000000001"


# ──────────────────────────────────────────────────────────────────────────────
# In-memory Supabase stub. Extends test_26's shape with `.insert(payload)` that
# CAPTURES the payload (so a test can assert the column contract) and whose
# `.execute()` returns data=[{'id': INSERT_ID}]. The fluent read chain
# (.select/.eq/.order/.limit) returns the queued read data on `.execute()`.
# It DELIBERATELY OMITS an in-list filter method, so any accidental use of the
# supabase-py in-filter raises AttributeError (EVAL-03 / T-27-07). No network,
# no credentials, never touches the live project.
# ──────────────────────────────────────────────────────────────────────────────


class _StubResult:
    def __init__(self, data):
        self.data = data


class _StubQuery:
    def __init__(self, captured, read_data):
        self._captured = captured      # shared list: inserted payloads, in order
        self._read_data = read_data    # data returned by a read .execute()
        self._is_insert = False

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def insert(self, payload):
        self._is_insert = True
        self._captured.append(payload)
        return self

    def execute(self):
        if self._is_insert:
            return _StubResult([{"id": INSERT_ID}])
        return _StubResult(self._read_data)

    # NOTE: NO in-list filter method is defined here — accidental use raises
    # AttributeError, documenting the EVAL-03 contract structurally.


class StubSupabase:
    """Minimal Supabase double. `captured` collects every inserted payload (FIFO);
    `read_data` is the `.data` list returned by a read `.execute()`."""

    def __init__(self, read_data=None):
        self.captured = []
        self._read_data = read_data if read_data is not None else []

    def table(self, name):
        return _StubQuery(self.captured, self._read_data)


class _RaisingQuery:
    """An insert whose `.execute()` raises — drives the loud-raise-on-write-failure test."""

    def insert(self, payload):
        return self

    def execute(self):
        raise RuntimeError("simulated supabase insert failure")


class RaisingSupabase:
    def table(self, name):
        return _RaisingQuery()


# Common kwargs for a valid ok-row write (each test overrides what it exercises).
def _ok_kwargs(**overrides):
    base = dict(
        newsletter_id="nid-1",
        edition_number=31,
        pipeline_version="single_pass",
        attempt=0,
        layer="deterministic",
        eval_status="ok",
        verdict="passed",
    )
    base.update(overrides)
    return base


# ══════════════════════════════════════════════════════════════════════════════
# Case 1 — the ok-row write: eval_status='ok', verdict NOT NULL, error NULL (D-09)
# ══════════════════════════════════════════════════════════════════════════════


def test_ok_row_write_returns_id_and_captures_clean_verdict():
    stub = StubSupabase()
    row_id = ee.write_eval_row(stub, **_ok_kwargs())
    assert row_id == INSERT_ID, "write_eval_row must return the inserted id"
    payload = stub.captured[0]
    assert payload["eval_status"] == "ok"
    assert payload["verdict"] == "passed"
    assert payload["error"] is None


# ══════════════════════════════════════════════════════════════════════════════
# Case 2 — the error-row write is NOT a silent zero (D-09 a/b)
# ══════════════════════════════════════════════════════════════════════════════


def test_error_row_is_an_error_state_not_a_silent_zero():
    """A proxy 402 / cap-hit writes eval_status='error' + a reason + a NULL verdict —
    never a silent 0 score. sats_spent=0 is a spend figure, NOT a verdict/score."""
    stub = StubSupabase()
    ee.write_eval_row(
        stub,
        newsletter_id="nid-err",
        edition_number=31,
        pipeline_version="block_v1",
        attempt=0,
        layer="judge",
        eval_status="error",
        error="proxy 402 cap hit",
        verdict=None,
    )
    payload = stub.captured[0]
    assert payload["eval_status"] == "error"
    assert payload["error"] == "proxy 402 cap hit"
    assert payload["verdict"] is None            # NOT a numeric 0 masquerading as a score
    assert payload["verdict"] != 0
    assert payload["sats_spent"] == 0            # a spend figure, never the verdict


# ══════════════════════════════════════════════════════════════════════════════
# Case 3 — verdict-iff-ok rejections raise ValueError BEFORE any insert (D-09)
# ══════════════════════════════════════════════════════════════════════════════


def test_error_status_with_a_verdict_raises_before_insert():
    stub = StubSupabase()
    with pytest.raises(ValueError):
        ee.write_eval_row(
            stub, **_ok_kwargs(eval_status="error", verdict="passed", error="boom")
        )
    assert stub.captured == [], "validation must precede the insert — no row captured"


def test_ok_status_without_a_verdict_raises_before_insert():
    stub = StubSupabase()
    with pytest.raises(ValueError):
        ee.write_eval_row(stub, **_ok_kwargs(eval_status="ok", verdict=None))
    assert stub.captured == []


def test_unknown_eval_status_raises_before_insert():
    stub = StubSupabase()
    with pytest.raises(ValueError):
        ee.write_eval_row(stub, **_ok_kwargs(eval_status="bogus"))
    assert stub.captured == []


# ══════════════════════════════════════════════════════════════════════════════
# Case 4 — loud-raise-on-write-failure: ERROR logged + original exception re-raised
# ══════════════════════════════════════════════════════════════════════════════


def test_write_failure_logs_error_and_reraises(caplog):
    stub = RaisingSupabase()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError):
            ee.write_eval_row(
                stub, **_ok_kwargs(newsletter_id="nid-loud", attempt=2, layer="judge")
            )
    # the failure is loud (D-09 c): an ERROR naming the failure + the newsletter_id
    assert any(
        "edition_evals write failed" in r.getMessage() for r in caplog.records
    ), "write failure must log an ERROR, never be swallowed"
    assert any("nid-loud" in r.getMessage() for r in caplog.records)


# ══════════════════════════════════════════════════════════════════════════════
# Case 5 — `.eq()`-only reads; the stub omits the in-list filter (EVAL-03 / T-27-07)
# ══════════════════════════════════════════════════════════════════════════════


def test_reads_use_eq_only_and_never_an_in_filter():
    rows = [{"edition_number": 31, "verdict": "passed", "pipeline_version": "block_v1"}]
    stub = StubSupabase(read_data=rows)
    assert ee.read_evals_by_newsletter(stub, "nid-1") == rows
    assert ee.read_eval_trend(stub, "block_v1") == rows
    # The stub deliberately omits the supabase-py in-list filter, so accidental use would
    # raise AttributeError. Documenting the contract: the query object has no such method.
    q = stub.table("edition_evals")
    assert not hasattr(q, "in_"), "stub must omit the in-list filter so accidental use raises"


def test_readers_return_empty_list_on_no_rows():
    stub = StubSupabase(read_data=[])
    assert ee.read_evals_by_newsletter(stub, "nid-none") == []
    assert ee.read_eval_trend(stub, "single_pass") == []


# ══════════════════════════════════════════════════════════════════════════════
# Case 6 — default JSONB shaping for an ok-row written without the JSONB kwargs
# ══════════════════════════════════════════════════════════════════════════════


def test_default_jsonb_shaping():
    stub = StubSupabase()
    ee.write_eval_row(stub, **_ok_kwargs())
    payload = stub.captured[0]
    assert payload["deterministic_flags"] == {}
    assert payload["judge_scores"] == {}
    assert payload["model_calls"] == []
    assert payload["judge_feedback"] is None


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
