#!/usr/bin/env python3
"""
Phase 31 Plan 03 (SURF-03) — /newsletter_eval owner-gated eval deep view.

Unit coverage for the gato_brain handler + local `.eq()`-only readers + detail/trend
formatters added in plan 31-03:

  - D-12 owner gate: a non-owner tier gets an owner-only refusal and NO eval row read
    ever occurs (StubSupabase.captured stays empty) — T-31-07.
  - D-09 no-args: targets the latest edition that HAS edition_evals rows; an empty
    edition_evals store returns the explicit "No eval has run for any edition yet."
  - D-09 <edition#> arg: `/newsletter_eval 103` reads via `.eq("edition_number", 103)`
    (an accidental `.in_()` would raise AttributeError against the stub — EVAL-03).
  - D-10 detail: a held_voice edition renders per-dim score lines for ALL five dims AND,
    for the failing dim, the judge's evidence/exemplar_before/exemplar_after each bounded
    to <=300 chars; a passed edition renders score-only dims BUT still lists the
    deterministic `mechanical` flags (P29 D-12).
  - D-11 trend: `/newsletter_eval trend` renders <=8 lines, each carrying edition #,
    pipeline_version, verdict, attempts, and fab/unv/mech counts.

Run standalone (no pytest required):  python3 tests/test_31_newsletter_eval_handler.py
No live database / proxy / network — a `.eq()`-only StubSupabase double is the only backend.
"""
import os
import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Stub third-party + sibling modules gato_brain imports at module level but which
# are not needed for these unit tests, so it imports in a bare env (mirrors the
# test_09_gated_publishing harness shape). init_clients() is only called from
# __main__, so no live supabase/anthropic client is created on import.
# ---------------------------------------------------------------------------
for _name in ("schedule", "tweepy", "resend"):
    if _name not in sys.modules:
        try:
            __import__(_name)
        except Exception:
            sys.modules[_name] = types.ModuleType(_name)

try:
    import markdown  # noqa: F401
except Exception:
    _m = types.ModuleType("markdown")
    _m.markdown = lambda *a, **k: ""
    sys.modules["markdown"] = _m

for _stub in (
    "code_commands", "cto_commands", "corpus_probe", "intent_router",
    "query_templates", "web_search",
):
    if _stub not in sys.modules:
        sys.modules[_stub] = types.ModuleType(_stub)

if "anthropic" not in sys.modules:
    _anth = types.ModuleType("anthropic")
    _anth.Anthropic = type("Anthropic", (), {"__init__": lambda self, *a, **k: None})
    sys.modules["anthropic"] = _anth

if "fastapi" not in sys.modules:
    try:
        import fastapi  # noqa: F401
    except Exception:
        _fa = types.ModuleType("fastapi")

        class _Stub:
            def __init__(self, *a, **k):
                pass

            def __call__(self, *a, **k):
                def _deco(fn=None, *aa, **kk):
                    return fn
                return _deco

            def __getattr__(self, name):
                return _Stub()

        _fa.FastAPI = _Stub
        _fa.HTTPException = type("HTTPException", (Exception,), {"__init__": lambda self, *a, **k: None})
        _fa.Header = lambda *a, **k: None
        _fa.Query = lambda *a, **k: None
        _fa.Request = _Stub
        sys.modules["fastapi"] = _fa

if "pydantic" not in sys.modules:
    try:
        import pydantic  # noqa: F401
    except Exception:
        _pyd = types.ModuleType("pydantic")
        _pyd.BaseModel = type("BaseModel", (), {})
        sys.modules["pydantic"] = _pyd

if "supabase" not in sys.modules:
    try:
        import supabase  # noqa: F401
    except Exception:
        _sb = types.ModuleType("supabase")
        _sb.create_client = lambda *a, **k: object()
        _sb.Client = object
        sys.modules["supabase"] = _sb

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "service-role-test-key")

sys.path.insert(0, str(_ROOT / "docker" / "gato_brain"))
import gato_brain as gb  # noqa: E402


# ===========================================================================
# `.eq()`-only StubSupabase double — applies eq filter + order + limit so the
# two-read latest-with-rows path resolves correctly. Structurally proves EVAL-03:
# _StubQuery defines NO `.in_()` — an accidental in-list filter raises AttributeError.
# ===========================================================================
class _StubResult:
    def __init__(self, data):
        self.data = data


class _StubQuery:
    def __init__(self, rows, captured):
        self._rows = list(rows)
        self._captured = captured
        self._eq = []
        self._orders = []
        self._limit = None

    def select(self, *a, **k):
        return self

    def eq(self, col, val):
        self._eq.append((col, val))
        self._captured.append(("eq", col, val))
        return self

    def order(self, col, desc=False, **k):
        self._orders.append((col, desc))
        self._captured.append(("order", col, desc))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        rows = [r for r in self._rows if all(r.get(c) == v for c, v in self._eq)]
        for col, desc in reversed(self._orders):
            rows = sorted(rows, key=lambda r: (r.get(col) is None, r.get(col)), reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return _StubResult(rows)

    # NOTE: NO in_ method — accidental `.in_()` raises AttributeError (EVAL-03).


class StubSupabase:
    def __init__(self, rows=None):
        self._rows = rows or []
        self.captured = []

    def table(self, name):
        return _StubQuery(self._rows, self.captured)


# ===========================================================================
# Row builders
# ===========================================================================
_DIMS = ("continuity", "hedging_filler", "clickbait", "repeated_subtopics", "specificity")


def _dim_entry(score, evidence="", before="", after=""):
    return {"score": score, "evidence": evidence, "exemplar_before": before, "exemplar_after": after}


def _judge_scores(overrides=None):
    """Both-bodies judge schema; every dim scores 5 unless overridden by {(body, dim): entry}."""
    overrides = overrides or {}
    js = {"technical": {}, "impact": {}}
    for body in ("technical", "impact"):
        for dim in _DIMS:
            js[body][dim] = _dim_entry(5)
    for (body, dim), entry in overrides.items():
        js[body][dim] = entry
    return js


def _det_row(edition, pv, verdict, *, mechanical=None, fabrication=None, unverified=None):
    return {
        "edition_number": edition,
        "pipeline_version": pv,
        "layer": "deterministic",
        "attempt": 0,
        "eval_status": "ok",
        "verdict": verdict,
        "deterministic_flags": {
            "fabrication": fabrication or [],
            "unverified": unverified or [],
            "mechanical": mechanical or [],
            "meta": {},
        },
        "judge_scores": {},
    }


def _judge_row(edition, pv, verdict, attempt, judge_scores):
    return {
        "edition_number": edition,
        "pipeline_version": pv,
        "layer": "judge",
        "attempt": attempt,
        "eval_status": "ok",
        "verdict": verdict,
        "deterministic_flags": {},
        "judge_scores": judge_scores,
    }


def _det_error_row(edition, pv, error="deterministic gate outage"):
    """A deterministic-layer error row (eval outage): NULL verdict + `{}` flags (WR-03)."""
    return {
        "edition_number": edition,
        "pipeline_version": pv,
        "layer": "deterministic",
        "attempt": 0,
        "eval_status": "error",
        "verdict": None,
        "error": error,
        "deterministic_flags": {},
        "judge_scores": {},
    }


def _judge_error_row(edition, pv, attempt, error="judge call timed out"):
    """A judge-layer error row: NULL verdict + empty scores (WR-03)."""
    return {
        "edition_number": edition,
        "pipeline_version": pv,
        "layer": "judge",
        "attempt": attempt,
        "eval_status": "error",
        "verdict": None,
        "error": error,
        "deterministic_flags": {},
        "judge_scores": {},
    }


_LONG = "This sentence is deliberately padded. " * 20  # ~760 chars, > 300


def _passed_edition_rows(edition=200):
    """A clean `passed` edition with a mechanical flag on the deterministic row."""
    mech = [{"kind": "h1_in_body", "version": "technical"}]
    return [
        _det_row(edition, "single_pass", "passed", mechanical=mech),
        _judge_row(edition, "single_pass", "passed", 0, _judge_scores()),
    ]


def _held_voice_edition_rows(edition=201):
    """A `held_voice` edition — clickbait fails (score 2 < 3) with long evidence/exemplars."""
    fail = _dim_entry(2, evidence=_LONG, before=_LONG, after=_LONG)
    scores = _judge_scores({("technical", "clickbait"): fail, ("impact", "clickbait"): fail})
    return [
        _det_row(edition, "single_pass", "passed"),
        _judge_row(edition, "single_pass", "held_voice", 0, scores),
        _judge_row(edition, "single_pass", "held_voice", 1, scores),
        _judge_row(edition, "single_pass", "held_voice", 2, scores),
    ]


# ===========================================================================
# D-12 owner gate (T-31-07)
# ===========================================================================
def test_non_owner_refused_and_no_read():
    stub = StubSupabase(rows=_passed_edition_rows())
    out = gb.handle_newsletter_eval("/newsletter_eval", access_tier="free", supabase_client=stub)
    assert "owner" in out.lower()
    assert stub.captured == [], "non-owner /newsletter_eval must NOT read any eval row"


def test_non_owner_subscriber_refused():
    stub = StubSupabase(rows=_passed_edition_rows())
    out = gb.handle_newsletter_eval(
        "/newsletter_eval trend", access_tier="subscriber", supabase_client=stub
    )
    assert "owner" in out.lower()
    assert stub.captured == []


# ===========================================================================
# D-09 no-args latest-with-rows + explicit no-eval-anywhere message
# ===========================================================================
def test_no_args_renders_latest_edition_with_rows():
    # Two editions present; the newest (201) must be the one rendered (D-09).
    rows = _passed_edition_rows(200) + _held_voice_edition_rows(201)
    stub = StubSupabase(rows=rows)
    out = gb.handle_newsletter_eval("/newsletter_eval", access_tier="owner", supabase_client=stub)
    assert "Edition #201" in out
    assert "Edition #200" not in out


def test_no_eval_anywhere_message():
    stub = StubSupabase(rows=[])
    out = gb.handle_newsletter_eval("/newsletter_eval", access_tier="owner", supabase_client=stub)
    assert out == "No eval has run for any edition yet."


# ===========================================================================
# D-09 <edition#> arg reads via .eq("edition_number", N) — never .in_()
# ===========================================================================
def test_edition_arg_reads_by_edition_eq():
    stub = StubSupabase(rows=_passed_edition_rows(103))
    out = gb.handle_newsletter_eval(
        "/newsletter_eval 103", access_tier="owner", supabase_client=stub
    )
    assert "Edition #103" in out
    assert ("eq", "edition_number", 103) in stub.captured
    # No in-list filter anywhere on the read path.
    assert not any(c[0] == "in_" for c in stub.captured)


def test_edition_arg_not_found():
    stub = StubSupabase(rows=_passed_edition_rows(200))
    out = gb.handle_newsletter_eval(
        "/newsletter_eval 999", access_tier="owner", supabase_client=stub
    )
    assert "No eval found for edition #999" in out


# ===========================================================================
# D-10 detail — failing dim renders bounded evidence/exemplars; all 5 dims scored
# ===========================================================================
def test_held_voice_detail_all_dims_and_bounded_evidence():
    stub = StubSupabase(rows=_held_voice_edition_rows(201))
    out = gb.handle_newsletter_eval("/newsletter_eval", access_tier="owner", supabase_client=stub)
    # Verdict surfaced.
    assert "held_voice" in out
    # A per-dimension score line for ALL five dims.
    for dim in _DIMS:
        assert f"{dim}: technical=" in out, f"missing score line for {dim}"
    # The failing clickbait dim renders evidence + before/after.
    assert "evidence:" in out and "before:" in out and "after:" in out
    # Each quoted excerpt is bounded to <=300 chars. Inspect each quoted segment.
    import re

    for seg in re.findall(r'"([^"]*)"', out):
        assert len(seg) <= 300, f"excerpt exceeded 300 chars: len={len(seg)}"


# ===========================================================================
# D-10 / P29 D-12 — a passed edition stays score-only but STILL lists mechanical flags
# ===========================================================================
def test_passed_detail_lists_mechanical_flags_and_no_failing_evidence():
    stub = StubSupabase(rows=_passed_edition_rows(200))
    out = gb.handle_newsletter_eval("/newsletter_eval", access_tier="owner", supabase_client=stub)
    assert "passed" in out
    # Mechanical flags listed even on a passed verdict (P29 D-12).
    assert "mechanical flags" in out
    assert "h1_in_body" in out
    # Score-only: no failing-dim evidence/exemplar block for an all-5 edition.
    assert "evidence:" not in out
    assert "before:" not in out


# ===========================================================================
# WR-03 — eval_status='error' rows: surface the reason; never render clean
# ===========================================================================
def test_detail_deterministic_error_renders_error_line_not_clean_flags():
    """WR-03: a deterministic ERROR row must NOT render as `mechanical flags: none`; it shows the
    bounded error reason + an explicit unavailable line instead."""
    rows = [_det_error_row(300, "single_pass", error="verify_draft crashed")]
    out = gb._format_eval_detail(rows)

    assert "⚠ eval ERROR: verify_draft crashed" in out
    assert "mechanical flags: none" not in out
    assert "deterministic gate errored" in out


def test_detail_prefers_ok_judge_scores_over_higher_attempt_error():
    """WR-03: an OK judge attempt supplies scores/verdict even when a later attempt ERRORED."""
    ok = _judge_row(301, "single_pass", "held_voice", 0, _judge_scores())
    err = _judge_error_row(301, "single_pass", 1, error="retry judge 500")
    rows = [_det_row(301, "single_pass", "passed"), ok, err]
    out = gb._format_eval_detail(rows)

    assert "verdict: held_voice" in out             # OK judge verdict wins, not the error NULL
    assert "n/a" not in out.split("verdict:")[1].split("\n")[0]  # verdict line is not 'n/a'
    assert "⚠ eval ERROR: retry judge 500" in out
    # Real per-dim scores render (from the OK attempt), not a "no judge scores recorded" fallback.
    assert "continuity: technical=" in out
    assert "(no judge scores recorded" not in out


def test_detail_error_reason_bounded_to_200_chars():
    """WR-03: the surfaced error reason renders at most 200 chars of the reason."""
    long_reason = "E" * 500
    rows = [_det_error_row(302, "single_pass", error=long_reason)]
    out = gb._format_eval_detail(rows)

    err_line = next(ln for ln in out.splitlines() if "⚠ eval ERROR:" in ln)
    reason = err_line.split("⚠ eval ERROR: ", 1)[1]
    assert len(reason) == 200
    assert long_reason not in out


# ===========================================================================
# D-11 trend — <=8 lines, each with edition/pipeline/verdict/attempts/flag counts
# ===========================================================================
def test_trend_lines_shape_and_cap():
    rows = []
    for ed in range(190, 200):  # 10 editions -> more than the 8-line cap
        rows.extend(_passed_edition_rows(ed))
    stub = StubSupabase(rows=rows)
    out = gb.handle_newsletter_eval(
        "/newsletter_eval trend", access_tier="owner", supabase_client=stub
    )
    trend_lines = [ln for ln in out.splitlines() if ln.strip().startswith("#")]
    assert 0 < len(trend_lines) <= 8, f"expected <=8 trend lines, got {len(trend_lines)}"
    for ln in trend_lines:
        assert "single_pass" in ln
        assert "passed" in ln
        assert "attempts=" in ln
        assert "fab=" in ln and "unv=" in ln and "mech=" in ln


def test_trend_empty_message():
    stub = StubSupabase(rows=[])
    out = gb.handle_newsletter_eval(
        "/newsletter_eval trend", access_tier="owner", supabase_client=stub
    )
    assert "No eval trend" in out


# ===========================================================================
# EVAL-03 structural — the stub (and thus the read path) has no in-list filter
# ===========================================================================
def test_stub_query_has_no_in_list_method():
    q = _StubQuery([], [])
    assert not hasattr(q, "in_"), "the read path must never rely on .in_() (EVAL-03)"


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import traceback

    _tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    _failed = 0
    for _t in _tests:
        try:
            _t()
            print(f"PASS {_t.__name__}")
        except Exception:
            _failed += 1
            print(f"FAIL {_t.__name__}")
            traceback.print_exc()
    print(f"\n{len(_tests) - _failed}/{len(_tests)} passed")
    sys.exit(1 if _failed else 0)
