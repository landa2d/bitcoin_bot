#!/usr/bin/env python3
"""
Phase 30 / Plan 02 — unit suite for `newsletter_poller.run_edition_eval` (the eval orchestrator).

Locks the "dumb sequencer" contract BEFORE Plan 30-03 wires it into the two save points. The
orchestrator sequences the three ALREADY-BUILT modules (deterministic_gate → judge_loop →
edition_eval) and returns a verdict object; it NEVER flips newsletter status (that is 30-03).

This imports the REAL `newsletter_poller` module (conftest-preloaded) — no re-implementation (the
test_19 rule; a copy could pass while production regresses). The three eval seams are injected by
patching the module attributes the orchestrator lazy-imports at call time:
`deterministic_gate.run_deterministic_gate`, `judge_loop.run_layer2`, `edition_eval.write_eval_row`,
plus the module-global `newsletter_poller._alert_operator`. `write_eval_row` is the REAL fail-loud
helper (recorded via a thin wrapper) writing to an in-memory Supabase stub — so verdict-iff-ok is
enforced for real. ZERO live egress, ZERO live DB.
"""
import sys
from pathlib import Path

import pytest

# Put docker/newsletter on sys.path and import the REAL production modules (mirrors test_29).
NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
if str(NL_DIR) not in sys.path:
    sys.path.insert(0, str(NL_DIR))

import newsletter_poller as nl          # noqa: E402 — the REAL orchestrator (conftest-preloaded)
import deterministic_gate as gate       # noqa: E402 — the Layer-1 gate seam
import judge_loop as jl                 # noqa: E402 — the Layer-2 judge seam
import edition_eval as ee               # noqa: E402 — the REAL fail-loud persistence helper


# ──────────────────────────────────────────────────────────────────────────────
# In-memory Supabase stub (only `edition_evals` inserts) + fixture builders.
# ──────────────────────────────────────────────────────────────────────────────


class _FakeTable:
    def __init__(self, store):
        self._store = store
        self._payload = None

    def insert(self, payload):
        self._payload = payload
        return self

    def execute(self):
        row = dict(self._payload)
        row.setdefault("id", f"id-{len(self._store) + 1}")
        self._store.append(row)
        return type("_R", (), {"data": [row]})()


class _FakeSupabase:
    def __init__(self):
        self.rows = []

    def table(self, name):
        assert name == "edition_evals", f"unexpected table {name!r}"
        return _FakeTable(self.rows)


def _draft():
    return {
        "title": "Test Edition",
        "title_impact": "Test Edition (Impact)",
        "content_markdown": "Technical body prose.",
        "content_markdown_impact": "Impact body prose.",
        "pipeline_version": "single_pass",
    }


def _fact_base():
    return {"premium_source_posts": [], "clusters": []}


def _prior_context():
    return {"empty": False, "previous_editions": [{"edition_number": 5}],
            "exemplars": [], "exemplars_status": "scored"}


def _prior_edition():
    return {"content_markdown": "prior tech", "content_markdown_impact": "prior impact",
            "edition_number": 5}


def _clean_flags():
    return {"fabrication": [], "unverified": [], "mechanical": [], "meta": {}}


def _attempt(attempt, *, eval_status="ok", error=None, judge_scores=None, feedback=None,
             reverify_flags=None, failing=None, sats=0, model_calls=None):
    """A run_layer2 attempt row (with the internal-only keys `_persistable_attempt` strips)."""
    return {
        "attempt": attempt,
        "eval_status": eval_status,
        "error": error,
        "judge_scores": judge_scores,
        "feedback": feedback,
        "reverify_flags": reverify_flags if reverify_flags is not None else {},
        "sats": sats,
        "model_calls": model_calls or [],
        "failing": failing or [],       # internal-only (D-11)
        "summed_score": 0,              # internal-only
        "draft": {},                    # internal-only
    }


def _run(sb, **overrides):
    kwargs = dict(
        pipeline_version="single_pass", newsletter_id="nl-1", edition=42,
        config={}, llm_client=object(), http_client=object(),
    )
    kwargs.update(overrides)
    return nl.run_edition_eval(sb, _draft(), _fact_base(), _prior_context(), _prior_edition(),
                               **kwargs)


@pytest.fixture
def harness(monkeypatch):
    """Record every write_eval_row call (delegating to the REAL helper → verdict-iff-ok is enforced)
    and every operator alert; hand back a fresh in-memory Supabase stub."""
    record = []
    real_write = ee.write_eval_row

    def _spy_write(supabase, **kwargs):
        record.append(kwargs)
        return real_write(supabase, **kwargs)   # REAL fail-loud helper → in-memory stub

    monkeypatch.setattr(ee, "write_eval_row", _spy_write)

    alerts = []
    monkeypatch.setattr(nl, "_alert_operator", lambda m: alerts.append(m))

    return type("_H", (), {"record": record, "alerts": alerts, "sb": _FakeSupabase()})()


# ──────────────────────────────────────────────────────────────────────────────
# Tests.
# ──────────────────────────────────────────────────────────────────────────────


def test_fabrication_short_circuits_no_layer2(harness, monkeypatch):
    """A non-empty fabrication flag → held_fabrication, run_layer2 NEVER called (D-09)."""
    fab = {"fabrication": [{"kind": "github_repo", "version": "technical"}],
           "unverified": [], "mechanical": [], "meta": {}}
    monkeypatch.setattr(gate, "run_deterministic_gate", lambda *a, **k: fab)
    layer2_calls = []
    monkeypatch.setattr(jl, "run_layer2", lambda *a, **k: layer2_calls.append(1))

    res = _run(harness.sb)

    assert res["verdict"] == "held_fabrication"
    assert res["ran"] is True
    assert layer2_calls == []  # short-circuit: Layer 2 NEVER ran
    det_rows = [r for r in harness.record if r["layer"] == "deterministic"]
    assert any(r.get("verdict") == "held_fabrication" for r in det_rows)


def test_judge_passed_persists_det_and_judge_rows(harness, monkeypatch):
    """Fabrication clean + judge 'passed' → verdict passed; a clean det row + >=1 judge row."""
    monkeypatch.setattr(gate, "run_deterministic_gate", lambda *a, **k: _clean_flags())
    passed = {
        "final_draft": _draft(), "verdict": "passed", "selected_attempt": 0,
        "attempts": [_attempt(0, judge_scores={"technical": {}, "impact": {}},
                              reverify_flags=_clean_flags())],
    }
    monkeypatch.setattr(jl, "run_layer2", lambda *a, **k: passed)

    res = _run(harness.sb)

    assert res["verdict"] == "passed"
    det = [r for r in harness.record if r["layer"] == "deterministic"]
    judge = [r for r in harness.record if r["layer"] == "judge"]
    assert any(r.get("verdict") == "passed" for r in det)   # 'passed' == Layer-1 clean
    assert len(judge) >= 1
    assert all(r.get("verdict") == "passed" for r in judge if r["eval_status"] == "ok")


def test_held_voice_reason_carries_scores_and_feedback(harness, monkeypatch):
    """held_voice reason carries each failing dim NAME + numeric SCORE + a judge_feedback excerpt
    (WIRE-03/D-10 — NOT labels-only); details carries the per-dimension judge_scores dict; every
    attempt is persisted (LOOP-03 telemetry)."""
    monkeypatch.setattr(gate, "run_deterministic_gate", lambda *a, **k: _clean_flags())
    scores = {
        "technical": {"continuity": {"score": 2, "evidence": "no bridge"},
                      "specificity": {"score": 2, "evidence": "vague"}},
        "impact": {"continuity": {"score": 3, "evidence": "weak bridge"},
                   "specificity": {"score": 2, "evidence": "vague"}},
    }
    hv = {
        "final_draft": _draft(), "verdict": "held_voice", "selected_attempt": 2,
        "attempts": [
            _attempt(0, judge_scores=scores, feedback="fb0", failing=["continuity", "specificity"]),
            _attempt(1, judge_scores=scores, feedback="fb1", failing=["continuity", "specificity"]),
            _attempt(2, judge_scores=scores,
                     feedback="- continuity: add a bridge sentence to the prior edition\n"
                              "- specificity: name the exact entities",
                     failing=["continuity", "specificity"]),
        ],
    }
    monkeypatch.setattr(jl, "run_layer2", lambda *a, **k: hv)

    res = _run(harness.sb)

    assert res["verdict"] == "held_voice"
    # dimension NAMES present
    assert "continuity" in res["reason"]
    assert "specificity" in res["reason"]
    # numeric SCORE present (worst-body min: continuity=2, specificity=2)
    assert "2" in res["reason"]
    # a NON-EMPTY judge_feedback excerpt present (sourced from the selected attempt's feedback)
    assert "bridge" in res["reason"]
    # details carries the full per-dimension judge_scores dict
    assert res["details"]["judge_scores"] == scores
    # every attempt persisted, one judge row each (LOOP-03 telemetry)
    judge_rows = [r for r in harness.record if r["layer"] == "judge"]
    assert len(judge_rows) == 3


def test_layer2_exception_fails_open_no_raise(harness, monkeypatch):
    """run_layer2 raising → error row + one operator alert + verdict escalated ran False; NO raise."""
    monkeypatch.setattr(gate, "run_deterministic_gate", lambda *a, **k: _clean_flags())

    def _boom(*a, **k):
        raise RuntimeError("judge blew up")

    monkeypatch.setattr(jl, "run_layer2", _boom)

    res = _run(harness.sb)   # must NOT raise

    assert res["verdict"] == "escalated"
    assert res["ran"] is False
    assert len(harness.alerts) == 1
    err_rows = [r for r in harness.record if r["eval_status"] == "error"]
    assert len(err_rows) >= 1


def test_layer2_escalated_alerts_once(harness, monkeypatch):
    """A clean (non-exception) 'escalated' verdict → one operator alert (D-12), verdict propagated."""
    monkeypatch.setattr(gate, "run_deterministic_gate", lambda *a, **k: _clean_flags())
    esc = {
        "final_draft": _draft(), "verdict": "escalated", "selected_attempt": 0,
        "attempts": [_attempt(0, eval_status="error", error="judge schema-invalid after retry",
                              reverify_flags=_clean_flags())],
    }
    monkeypatch.setattr(jl, "run_layer2", lambda *a, **k: esc)

    res = _run(harness.sb)

    assert res["verdict"] == "escalated"
    assert len(harness.alerts) == 1


def test_governed_identity_passthrough(harness, monkeypatch):
    """The exact injected llm_client + http_client instances reach run_layer2 (caller owns identity)."""
    monkeypatch.setattr(gate, "run_deterministic_gate", lambda *a, **k: _clean_flags())
    captured = {}

    def _spy_layer2(draft, fact_base, prior_context, det_flags, config, llm_client,
                    *, http_client=None, github_token=None):
        captured["llm_client"] = llm_client
        captured["http_client"] = http_client
        return {"final_draft": draft, "verdict": "passed", "selected_attempt": 0,
                "attempts": [_attempt(0, judge_scores={}, reverify_flags=det_flags)]}

    monkeypatch.setattr(jl, "run_layer2", _spy_layer2)

    sentinel_llm = object()
    sentinel_http = object()
    _run(harness.sb, llm_client=sentinel_llm, http_client=sentinel_http)

    assert captured["llm_client"] is sentinel_llm
    assert captured["http_client"] is sentinel_http


def test_build_eval_client_uses_governed_key_source_assert():
    """Source-level: _build_eval_llm_client uses the governed key getter, never the module client."""
    import inspect
    src = inspect.getsource(nl._build_eval_llm_client)
    assert "_get_eval_api_key" in src
    assert "claude_client" not in src


def test_llm_client_none_is_outage(harness, monkeypatch):
    """llm_client None (eval key unset) → error row + one alert + escalated ran False, NO run_layer2."""
    layer2_calls = []
    monkeypatch.setattr(jl, "run_layer2", lambda *a, **k: layer2_calls.append(1))
    gate_calls = []
    monkeypatch.setattr(gate, "run_deterministic_gate",
                        lambda *a, **k: gate_calls.append(1) or _clean_flags())

    res = _run(harness.sb, llm_client=None)

    assert res["verdict"] == "escalated"
    assert res["ran"] is False
    assert layer2_calls == []
    assert len(harness.alerts) == 1
    err_rows = [r for r in harness.record if r["eval_status"] == "error"]
    assert len(err_rows) == 1


def test_no_status_or_do_not_publish_update_in_orchestrator():
    """run_edition_eval computes a verdict but NEVER flips status/do_not_publish (that is 30-03)."""
    import inspect
    src = inspect.getsource(nl.run_edition_eval)
    assert "do_not_publish" not in src
    assert "status" not in src or "\"status\": \"held\"" not in src
