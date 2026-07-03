#!/usr/bin/env python3
"""
Phase 31 / Plan 02 — SURF-02 unit suite for the Friday-notify eval summary.

Locks the two new processor helpers + the extended scheduled_notify_newsletter:

  Task 1 — the .eq()-only edition-keyed reader + the pure compact formatter
    - `_read_edition_evals` uses `.eq("edition_number", ...)` and NO `.in_()` (EVAL-03):
      the edition_evals stub OMITS an in-list filter, so an accidental `.in_()` raises
      AttributeError — the contract is proven structurally (mirrors test_27's StubSupabase).
    - `_format_notify_eval_section` (PURE): single_pass renders before block_v1 (D-05); a
      `passed` draft STILL prints a mechanical count (D-06); a pipeline_version with no rows
      prints `⚠ no eval recorded for this draft` (D-07); a held verdict with enforce=False
      prints `⚠ WOULD HAVE HELD (report-only)` at the top of its block, and with enforce=True
      prints the plain held verdict (D-08); the render leaks NO evidence/exemplar prose (T-31-04).

  Task 2 — scheduled_notify_newsletter seam
    - appends the eval section to the static notify text (both pipeline_versions);
    - is a hold/eval-critical caller: a `False` send_telegram return CRITICAL-logs
      `[EVAL-ALERT] CRITICAL — Friday notify ...` (D-03);
    - an eval-read exception is fail-open-but-loud: the static notify still sends.

Imports the REAL `agentpulse_processor` module (the test_31_send_telegram harness bootstrap) —
no re-implementation. ZERO live egress, ZERO live DB.

Run:  python3 -m pytest tests/test_31_notify_eval.py -q
"""
import logging
import os
import sys
import types
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent

# Stub third-party modules the processor imports at module level but which are not
# needed for these unit tests (mirrors tests/test_31_send_telegram.py's harness shape).
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

os.environ.setdefault("OPENCLAW_DATA_DIR", "/tmp/openclaw_test_31")

sys.path.insert(0, str(_ROOT / "docker" / "processor"))
import agentpulse_processor as proc  # noqa: E402


# ---------------------------------------------------------------------------
# In-memory Supabase double. `edition_evals` uses a query chain that DELIBERATELY
# OMITS an in-list filter (accidental `.in_()` → AttributeError, EVAL-03), and
# records every filter call so a test can assert `.eq("edition_number", ...)` was
# used. The `newsletters` chain keeps the pre-existing `.in_('status')` lookup (that
# path is acceptable; ONLY the new edition_evals read must be .eq()-only).
# ---------------------------------------------------------------------------
class _StubResult:
    def __init__(self, data):
        self.data = data


class _EvalQuery:
    """edition_evals chain — .eq()-only; NO .in_() (accidental use → AttributeError)."""

    def __init__(self, read_data, calls):
        self._read_data = read_data
        self._calls = calls

    def select(self, *a, **k):
        self._calls.append(("select", a))
        return self

    def eq(self, *a, **k):
        self._calls.append(("eq", a))
        return self

    def order(self, *a, **k):
        self._calls.append(("order", a))
        return self

    def limit(self, *a, **k):
        self._calls.append(("limit", a))
        return self

    def execute(self):
        return _StubResult(self._read_data)

    # NOTE: NO in-list filter method — accidental `.in_()` raises AttributeError (EVAL-03).


class _NewslettersQuery:
    """newsletters lookup chain — the pre-existing `.in_('status')` path is allowed here."""

    def __init__(self, read_data):
        self._read_data = read_data

    def select(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        return _StubResult(self._read_data)


class StubSupabase:
    def __init__(self, eval_rows=None, newsletters=None, eval_raises=False):
        self._eval_rows = eval_rows if eval_rows is not None else []
        self._newsletters = newsletters if newsletters is not None else []
        self._eval_raises = eval_raises
        self.eval_calls = []

    def table(self, name):
        if name == "edition_evals":
            if self._eval_raises:
                raise RuntimeError("simulated edition_evals read failure")
            return _EvalQuery(self._eval_rows, self.eval_calls)
        return _NewslettersQuery(self._newsletters)


def _has_record(caplog, substr, level=None):
    for r in caplog.records:
        if substr in r.getMessage():
            if level is None or r.levelno == level:
                return True
    return False


# ---------------------------------------------------------------------------
# Row builders mirroring the migration-045 edition_evals shape.
# ---------------------------------------------------------------------------
def _det_row(pv, verdict, *, attempt=0, fabrication=0, unverified=0, mechanical=0, edition=103):
    return {
        "edition_number": edition,
        "pipeline_version": pv,
        "layer": "deterministic",
        "attempt": attempt,
        "eval_status": "ok",
        "verdict": verdict,
        "deterministic_flags": {
            "fabrication": [{"i": i} for i in range(fabrication)],
            "unverified": [{"i": i} for i in range(unverified)],
            "mechanical": [{"i": i} for i in range(mechanical)],
            "meta": {},
        },
        "judge_scores": {},
    }


def _judge_row(pv, verdict, *, attempt=0, scores=None, edition=103):
    """A judge-layer row. `scores` is the both-bodies schema; each cell carries evidence +
    exemplar prose the formatter MUST NOT leak."""
    if scores is None:
        scores = _clean_scores()
    return {
        "edition_number": edition,
        "pipeline_version": pv,
        "layer": "judge",
        "attempt": attempt,
        "eval_status": "ok",
        "verdict": verdict,
        "deterministic_flags": {},
        "judge_scores": scores,
        "judge_feedback": "SECRET_FEEDBACK draft prose that must never leak",
    }


def _det_error_row(pv, *, attempt=0, error="deterministic gate outage", edition=103):
    """A deterministic-layer error row (eval outage): NULL verdict + `{}` flags (WR-03)."""
    return {
        "edition_number": edition,
        "pipeline_version": pv,
        "layer": "deterministic",
        "attempt": attempt,
        "eval_status": "error",
        "verdict": None,
        "error": error,
        "deterministic_flags": {},
        "judge_scores": {},
    }


def _judge_error_row(pv, *, attempt=0, error="judge call timed out", edition=103):
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


def _cell(score):
    return {
        "score": score,
        "evidence": "SECRET_EVIDENCE quoted draft sentence",
        "exemplar_before": "SECRET_BEFORE prose",
        "exemplar_after": "SECRET_AFTER prose",
    }


def _clean_scores(**dim_overrides):
    dims = {d: 5 for d in proc._NOTIFY_JUDGE_DIMENSIONS}
    dims.update(dim_overrides)
    return {
        "technical": {d: _cell(v) for d, v in dims.items()},
        "impact": {d: _cell(v) for d, v in dims.items()},
    }


# Leak sentinels planted in the judge rows above — none may appear in the render (T-31-04).
_LEAK_SENTINELS = (
    "SECRET_EVIDENCE", "SECRET_BEFORE", "SECRET_AFTER", "SECRET_FEEDBACK",
    "evidence", "exemplar_before", "exemplar_after",
)


# ===========================================================================
# Task 1 — _read_edition_evals: .eq()-only, edition-keyed
# ===========================================================================
def test_read_edition_evals_returns_rows_and_uses_eq():
    rows = [_det_row("single_pass", "passed"), _judge_row("single_pass", "passed")]
    stub = StubSupabase(eval_rows=rows)

    out = proc._read_edition_evals(stub, 103)

    assert out == rows
    # The edition-keyed .eq() was used (an accidental .in_() would have raised below).
    assert ("eq", ("edition_number", 103)) in stub.eval_calls


def test_read_edition_evals_empty_returns_list():
    stub = StubSupabase(eval_rows=[])
    assert proc._read_edition_evals(stub, 999) == []


def test_edition_evals_query_has_no_in_filter():
    """Structural EVAL-03 proof: the edition_evals chain omits `.in_()` entirely — an accidental
    in-list filter raises AttributeError, exactly as the .in_() silent-failure anti-pattern must."""
    stub = StubSupabase(eval_rows=[])
    q = stub.table("edition_evals").select("*")
    assert not hasattr(q, "in_")
    with pytest.raises(AttributeError):
        q.in_("edition_number", [103])


# ===========================================================================
# Task 1 — _format_notify_eval_section: D-05/D-06/D-07/D-08 + no-leak
# ===========================================================================
def test_passed_draft_still_prints_mechanical_count():
    """D-06: a `passed` single_pass draft STILL prints a mechanical count line (P29 D-12)."""
    rows = [
        _det_row("single_pass", "passed", mechanical=2),
        _judge_row("single_pass", "passed"),
    ]
    out = proc._format_notify_eval_section(rows, enforce=False)

    assert "verdict: passed" in out
    assert "mechanical=2" in out
    assert "fabrication=0" in out


def test_missing_pipeline_version_prints_no_eval_line():
    """D-07: a pipeline_version with no rows renders the explicit warning — never omitted."""
    rows = [_det_row("single_pass", "passed"), _judge_row("single_pass", "passed")]
    out = proc._format_notify_eval_section(rows, enforce=False)

    # block_v1 has no rows in `rows` → its block is present with the warning line.
    assert "Telemetry (block_v1)" in out
    assert "⚠ no eval recorded for this draft" in out


def test_empty_eval_rows_renders_both_no_eval_blocks():
    """No rows at all → BOTH pipeline_version blocks render the no-eval warning (never a blank)."""
    out = proc._format_notify_eval_section([], enforce=False)
    assert out.count("⚠ no eval recorded for this draft") == 2
    assert "Primary (single_pass)" in out
    assert "Telemetry (block_v1)" in out


def test_would_have_held_tag_when_report_only():
    """D-08: held_voice + enforce=False → `⚠ WOULD HAVE HELD (report-only)` at the TOP of its block."""
    rows = [
        _det_row("single_pass", "held_voice"),
        _judge_row("single_pass", "held_voice", scores=_clean_scores(clickbait=1)),
    ]
    out = proc._format_notify_eval_section(rows, enforce=False)

    assert "⚠ WOULD HAVE HELD (report-only)" in out
    # The tag sits ABOVE the verdict line inside the single_pass block.
    assert out.index("⚠ WOULD HAVE HELD (report-only)") < out.index("verdict: held_voice")
    assert "(report-only)" in out.splitlines()[1]  # header also flags report-only


def test_held_verdict_plain_when_enforce_true():
    """D-08: with enforce=True the held verdict renders plainly — NO report-only tag."""
    rows = [
        _det_row("single_pass", "held_voice"),
        _judge_row("single_pass", "held_voice", scores=_clean_scores(clickbait=1)),
    ]
    out = proc._format_notify_eval_section(rows, enforce=True)

    assert "⚠ WOULD HAVE HELD (report-only)" not in out
    assert "verdict: held_voice" in out
    assert "(report-only)" not in out  # header is plain when enforce=True


def test_held_fabrication_deterministic_only_gets_tag():
    """A Layer-1 held_fabrication with NO judge row still resolves the effective verdict from the
    deterministic row → the report-only tag fires (D-08 covers held_fabrication too)."""
    rows = [_det_row("single_pass", "held_fabrication", fabrication=3)]
    out = proc._format_notify_eval_section(rows, enforce=False)

    assert "⚠ WOULD HAVE HELD (report-only)" in out
    assert "verdict: held_fabrication" in out
    assert "fabrication=3" in out
    assert "scores: (judge did not run)" in out


def test_single_pass_renders_before_block_v1():
    """D-05: single_pass leads, block_v1 telemetry follows."""
    rows = [
        _det_row("block_v1", "passed"),
        _judge_row("block_v1", "passed"),
        _det_row("single_pass", "passed"),
        _judge_row("single_pass", "passed"),
    ]
    out = proc._format_notify_eval_section(rows, enforce=False)
    assert out.index("Primary (single_pass)") < out.index("Telemetry (block_v1)")


def test_attempts_used_is_max_attempt_plus_one():
    """attempts used = max judge attempt + 1; the FINAL (highest-attempt) judge row supplies scores."""
    rows = [
        _det_row("single_pass", "passed"),
        _judge_row("single_pass", "held_voice", attempt=0, scores=_clean_scores(clickbait=1)),
        _judge_row("single_pass", "passed", attempt=1, scores=_clean_scores()),
    ]
    out = proc._format_notify_eval_section(rows, enforce=False)

    assert "attempts used: 2" in out
    assert "verdict: passed" in out  # the highest-attempt judge verdict wins


def test_dimension_scores_use_worst_of_both_bodies():
    """Each dim renders min(technical, impact); a stray n/a continuity renders `n/a`, not a crash."""
    scores = _clean_scores(clickbait=3)
    scores["impact"]["clickbait"]["score"] = 1  # worst-of-both → 1
    scores["technical"]["continuity"]["score"] = "n/a"
    scores["impact"]["continuity"]["score"] = "n/a"
    rows = [_det_row("single_pass", "passed"), _judge_row("single_pass", "passed", scores=scores)]

    out = proc._format_notify_eval_section(rows, enforce=False)

    assert "clickbait=1" in out
    assert "continuity=n/a" in out


def test_notify_prefers_ok_judge_over_higher_attempt_error(monkeypatch):
    """WR-03: an OK judge attempt supplies the verdict/scores even when a later attempt ERRORED —
    the error row must not shadow the good data. The error reason is still surfaced."""
    rows = [
        _det_row("single_pass", "passed"),
        _judge_row("single_pass", "passed", attempt=0, scores=_clean_scores(clickbait=4)),
        _judge_error_row("single_pass", attempt=1, error="retry judge call 500"),
    ]
    out = proc._format_notify_eval_section(rows, enforce=False)

    assert "verdict: passed" in out           # OK verdict wins, not the error row's NULL
    assert "clickbait=4" in out               # real scores render, not `?`
    assert "verdict: unknown" not in out
    assert "⚠ eval ERROR: retry judge call 500" in out


def test_notify_deterministic_error_not_clean_zeros():
    """WR-03: a deterministic ERROR row must NOT render as `fabrication=0 unverified=0
    mechanical=0` — it shows the error line + an explicit unavailable-counts line instead."""
    rows = [_det_error_row("single_pass", error="verify_draft crashed")]
    out = proc._format_notify_eval_section(rows, enforce=False)

    assert "⚠ eval ERROR: verify_draft crashed" in out
    assert "fabrication=0 unverified=0 mechanical=0" not in out
    assert "deterministic gate errored" in out


def test_notify_error_reason_bounded_to_200_chars():
    """WR-03: the surfaced error reason is bounded — never more than 200 chars of the reason."""
    long_reason = "E" * 500
    rows = [_det_error_row("single_pass", error=long_reason)]
    out = proc._format_notify_eval_section(rows, enforce=False)

    err_line = next(ln for ln in out.splitlines() if ln.startswith("⚠ eval ERROR:"))
    reason = err_line[len("⚠ eval ERROR: "):]
    assert len(reason) == 200
    assert long_reason not in out  # the full 500-char reason never renders


def test_formatter_leaks_no_evidence_or_exemplar_prose():
    """T-31-04: the render carries labels/counts/scores ONLY — never judge evidence/exemplar/feedback."""
    rows = [
        _det_row("single_pass", "held_voice", mechanical=1),
        _judge_row("single_pass", "held_voice", scores=_clean_scores(clickbait=1)),
        _det_row("block_v1", "passed"),
        _judge_row("block_v1", "passed"),
    ]
    out = proc._format_notify_eval_section(rows, enforce=False)

    for sentinel in _LEAK_SENTINELS:
        assert sentinel not in out, f"leaked {sentinel!r} into the compact notify"


# ===========================================================================
# Task 2 — scheduled_notify_newsletter seam (D-03 critical caller + fail-open)
# ===========================================================================
_DRAFT_ROW = [{"id": "nl-1", "edition_number": 103, "status": "draft"}]


def _wire_config(monkeypatch, enforce):
    monkeypatch.setattr(proc, "get_full_config", lambda: {"edition_eval": {"enforce": enforce}})


def test_notify_appends_eval_section_to_static_text(monkeypatch):
    """The Friday notify = the static line + the eval section (both pipeline_versions), with D-06
    mechanical-on-passed, D-07 no-eval for a missing block, and D-08 report-only tag."""
    eval_rows = [
        _det_row("single_pass", "held_voice", mechanical=1),
        _judge_row("single_pass", "held_voice", scores=_clean_scores(clickbait=1)),
    ]  # block_v1 has NO rows → D-07 line
    monkeypatch.setattr(proc, "supabase", StubSupabase(eval_rows=eval_rows, newsletters=_DRAFT_ROW))
    _wire_config(monkeypatch, enforce=False)
    sent = []
    monkeypatch.setattr(proc, "send_telegram", lambda m, **k: sent.append(m) or True)

    proc.scheduled_notify_newsletter()

    assert len(sent) == 1
    msg = sent[0]
    assert "New AgentPulse Brief is ready for review" in msg   # static line preserved
    assert "🧪 Pre-publish eval" in msg                          # eval section appended
    assert "mechanical=1" in msg                                # D-06
    assert "⚠ WOULD HAVE HELD (report-only)" in msg             # D-08 (enforce=False)
    assert "⚠ no eval recorded for this draft" in msg           # D-07 (block_v1 missing)


def test_notify_no_report_only_tag_when_enforce_true(monkeypatch):
    """With enforce=True the held verdict renders plainly in the notify (no report-only tag)."""
    eval_rows = [
        _det_row("single_pass", "held_voice"),
        _judge_row("single_pass", "held_voice", scores=_clean_scores(clickbait=1)),
    ]
    monkeypatch.setattr(proc, "supabase", StubSupabase(eval_rows=eval_rows, newsletters=_DRAFT_ROW))
    _wire_config(monkeypatch, enforce=True)
    sent = []
    monkeypatch.setattr(proc, "send_telegram", lambda m, **k: sent.append(m) or True)

    proc.scheduled_notify_newsletter()

    assert "⚠ WOULD HAVE HELD (report-only)" not in sent[0]
    assert "verdict: held_voice" in sent[0]


def test_notify_critical_logs_on_delivery_failure(monkeypatch, caplog):
    """D-03/WR-05: a `False` send_telegram return CRITICAL-logs `[EVAL-ALERT] CRITICAL — Friday
    notify` AND does NOT log the "notification sent" INFO (the INFO must only fire on success)."""
    monkeypatch.setattr(proc, "supabase", StubSupabase(eval_rows=[], newsletters=_DRAFT_ROW))
    _wire_config(monkeypatch, enforce=False)
    monkeypatch.setattr(proc, "send_telegram", lambda m, **k: False)
    caplog.set_level(logging.DEBUG)

    proc.scheduled_notify_newsletter()

    assert _has_record(caplog, "[EVAL-ALERT] CRITICAL — Friday notify", level=logging.CRITICAL)
    # WR-05: the success INFO must NOT claim "sent" alongside a delivery failure.
    assert not _has_record(caplog, "Newsletter notification sent")


def test_notify_no_critical_when_delivery_ok(monkeypatch, caplog):
    """When the notify delivers (True), NO CRITICAL log fires AND the "sent" INFO fires (WR-05)."""
    monkeypatch.setattr(proc, "supabase", StubSupabase(eval_rows=[], newsletters=_DRAFT_ROW))
    _wire_config(monkeypatch, enforce=False)
    monkeypatch.setattr(proc, "send_telegram", lambda m, **k: True)
    caplog.set_level(logging.DEBUG)

    proc.scheduled_notify_newsletter()

    assert not _has_record(caplog, "[EVAL-ALERT] CRITICAL")
    # WR-05: the "sent" INFO fires ONLY after a True send_telegram return.
    assert _has_record(caplog, "Newsletter notification sent", level=logging.INFO)


def test_notify_fail_open_on_eval_read_exception(monkeypatch, caplog):
    """Fail-open-but-loud: an eval-read exception still sends the STATIC notify + ERROR-logs."""
    monkeypatch.setattr(
        proc, "supabase", StubSupabase(eval_raises=True, newsletters=_DRAFT_ROW)
    )
    _wire_config(monkeypatch, enforce=False)
    sent = []
    monkeypatch.setattr(proc, "send_telegram", lambda m, **k: sent.append(m) or True)
    caplog.set_level(logging.DEBUG)

    proc.scheduled_notify_newsletter()

    assert len(sent) == 1
    assert "New AgentPulse Brief is ready for review" in sent[0]   # static notify still sent
    assert "🧪 Pre-publish eval" not in sent[0]                     # eval section suppressed on error
    assert _has_record(caplog, "[EVAL-NOTIFY]", level=logging.ERROR)


def test_notify_no_supabase_guard_returns(monkeypatch, caplog):
    """Guard: with no supabase client the notify returns without calling send_telegram, and it
    ERROR-logs the skip instead of a silent bare return + never claims "sent" (WR-05)."""
    monkeypatch.setattr(proc, "supabase", None)
    called = []
    monkeypatch.setattr(proc, "send_telegram", lambda m, **k: called.append(m) or True)
    caplog.set_level(logging.DEBUG)

    proc.scheduled_notify_newsletter()

    assert called == []
    # WR-05: the supabase-None skip is now fail-loud (ERROR) and never logs "notification sent".
    assert _has_record(caplog, "[EVAL-NOTIFY] supabase unavailable", level=logging.ERROR)
    assert not _has_record(caplog, "Newsletter notification sent")


def test_notify_no_llm_call_added(monkeypatch):
    """WIRE-05: the notify path adds NO LLM call — routed_llm_call must never be invoked."""
    monkeypatch.setattr(proc, "supabase", StubSupabase(eval_rows=[], newsletters=_DRAFT_ROW))
    _wire_config(monkeypatch, enforce=False)
    monkeypatch.setattr(proc, "send_telegram", lambda m, **k: True)

    def _boom(*a, **k):
        raise AssertionError("scheduled_notify_newsletter must not call routed_llm_call (WIRE-05)")

    monkeypatch.setattr(proc, "routed_llm_call", _boom)

    proc.scheduled_notify_newsletter()  # must not raise


# ===========================================================================
# WR-04 — eval-bearing notify is sent PLAIN TEXT (no parse_mode='Markdown')
# ===========================================================================
def test_notify_eval_bearing_message_sent_plain(monkeypatch):
    """WR-04: the Friday notify carrying the eval section is sent with plain=True so the
    underscore-heavy tokens (single_pass, held_voice, hedging_filler, repeated_subtopics)
    render verbatim instead of being mangled by parse_mode='Markdown' underscore-parity."""
    eval_rows = [
        _det_row("single_pass", "held_voice", mechanical=1),
        _judge_row("single_pass", "held_voice", scores=_clean_scores(clickbait=1)),
    ]
    monkeypatch.setattr(proc, "supabase", StubSupabase(eval_rows=eval_rows, newsletters=_DRAFT_ROW))
    _wire_config(monkeypatch, enforce=False)
    captured = {}

    def _capture(m, *, plain=False):
        captured["message"] = m
        captured["plain"] = plain
        return True

    monkeypatch.setattr(proc, "send_telegram", _capture)

    proc.scheduled_notify_newsletter()

    assert captured["plain"] is True, "eval-bearing notify must be sent plain (WR-04)"
    assert "🧪 Pre-publish eval" in captured["message"]
    # The underscore-heavy labels are present unescaped (plain send needs no escaping).
    assert "single_pass" in captured["message"]
    assert "held_voice" in captured["message"]


def test_notify_static_only_uses_default_markdown_path(monkeypatch):
    """WR-04: when the eval section is NOT present (eval-read error → static notify only) the
    default plain=False path is used — the plain-text route is scoped to eval-bearing sends so
    no other send_telegram behavior changes."""
    monkeypatch.setattr(proc, "supabase", StubSupabase(eval_raises=True, newsletters=_DRAFT_ROW))
    _wire_config(monkeypatch, enforce=False)
    captured = {}

    def _capture(m, *, plain=False):
        captured["message"] = m
        captured["plain"] = plain
        return True

    monkeypatch.setattr(proc, "send_telegram", _capture)

    proc.scheduled_notify_newsletter()

    assert captured["plain"] is False, "static-only notify keeps the default Markdown path"
    assert "🧪 Pre-publish eval" not in captured["message"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
