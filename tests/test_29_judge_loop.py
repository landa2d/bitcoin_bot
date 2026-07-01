#!/usr/bin/env python3
"""
Phase 29 / Plan 01 — unit suite for `judge_loop.run_layer2` (Layer-2 judge + scoring core).

Locks the Layer-2 module contract BEFORE any Phase 30 caller wires it into `newsletter_poller`:
  - JUDGE-01: `run_layer2` refuses a mis-wired caller — a non-empty `det_flags['fabrication']`
    raises ValueError (Layer 1 must short-circuit first),
  - JUDGE-04: the config-tunable both-bodies threshold engine (`_compute_failing_dims`) — a
    dimension fails for the version if EITHER body fails (`min` worst-case, D-08); the hedging
    dimension ALSO fails on the deterministic filler-hit combination (D-04),
  - JUDGE-03 / D-05: continuity is EXCLUDED from the failing set on an empty corpus,
  - JUDGE-02 / JUDGE-05 (Task 2): the exemplar-anchored judge scores both bodies in ONE call,
    schema-rejects a response missing evidence/exemplars, retries once, then escalates.

This imports the REAL `judge_loop` module (no re-implementation — the test_19 rule). A copy
could pass while production regresses. `judge_loop` imports `parse_llm_json` from
`newsletter_poller` (conftest preloads it), `_llm_call` from `block_pipeline`, and
`run_deterministic_gate` from `deterministic_gate` — all importable once NL_DIR is on sys.path.
NO network, NO live proxy: every judge call runs against the in-memory OpenAI-shape `_FakeLLM`
(FIFO canned JSON); the reused httpx fake is carried for Plan 03's re-check. Zero live egress.
"""
import json
import sys
from pathlib import Path

import pytest

# Put docker/newsletter on sys.path and import the REAL production module.
NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
if str(NL_DIR) not in sys.path:
    sys.path.insert(0, str(NL_DIR))

import judge_loop as jl  # noqa: E402 — the REAL production module
import deterministic_gate as gate  # noqa: E402 — the reused Layer-1 engine (DNS-patched in _stub_dns)


@pytest.fixture(autouse=True)
def _stub_dns(monkeypatch):
    """Zero-egress SSRF-guard resolver stub (mirrors tests/test_28_deterministic_gate.py:44-54).

    The Plan-03 per-rewrite re-check re-runs `run_deterministic_gate`, whose URL-layer SSRF guard
    RESOLVES every dotted host; without this stub the reverify tests would perform REAL DNS (live
    egress, T-28-04). Patch the symbol on the `deterministic_gate` module `judge_loop` imports so
    every host resolves to ONE public IP by default — the whole suite has ZERO live egress."""
    monkeypatch.setattr(gate, "_resolve_host", lambda host: ["93.184.216.34"])  # a public IP


# ──────────────────────────────────────────────────────────────────────────────
# Fixture builders — draft + fact_base shapes identical to what run_layer2 consumes
# (mirrors tests/test_28_deterministic_gate.py:64-113; kept self-contained so this
# suite carries no cross-file fixture coupling).
# ──────────────────────────────────────────────────────────────────────────────


def _make_draft(*, title="Test Edition", title_impact="Test Edition (Impact)",
                content_markdown="Technical body prose.", content_markdown_impact="Impact body prose.",
                pipeline_version="block_v1"):
    return {
        "title": title,
        "title_impact": title_impact,
        "content_markdown": content_markdown,
        "content_markdown_impact": content_markdown_impact,
        "pipeline_version": pipeline_version,
    }


def _single_pass_fact_base(*, premium_source_posts=None, section_b_emerging=None,
                           clusters=None, trending_tools=None, predictions=None):
    return {
        "premium_source_posts": premium_source_posts or [],
        "section_b_emerging": section_b_emerging or [],
        "clusters": clusters or [],
        "trending_tools": trending_tools or [],
        "predictions": predictions or [],
    }


def _block_fact_base(*, blocks=None, tracked_entity_signals=None,
                     trending_tools=None, predictions=None):
    return {
        "blocks": blocks or [{"description": "", "named_entities": []}],
        "tracked_entity_signals": tracked_entity_signals or [],
        "trending_tools": trending_tools or [],
        "predictions": predictions or [],
    }


def _clean_det_flags():
    """A fabrication-CLEAN Layer-1 gate result (the only shape run_layer2 accepts)."""
    return {"fabrication": [], "unverified": [], "mechanical": [], "meta": {}}


def _applicable_prior():
    """A prior_context with a prior edition → continuity applies (judge scores it numerically)."""
    return {
        "empty": False,
        "previous_editions": [
            {"edition_number": 5, "title": "Prior angle", "opening_excerpt": "last week", "weeks_ago": 1},
        ],
        "exemplars": ["An exemplar paragraph in the target voice."],
        "exemplars_status": "scored",
    }


def _empty_prior():
    """An empty corpus → continuity is n/a and excluded (D-05)."""
    return {"empty": True, "previous_editions": [], "exemplars": [], "exemplars_status": "not_scored"}


# ──────────────────────────────────────────────────────────────────────────────
# Test doubles.
#   _FakeLLM   — OpenAI-shape FIFO proxy client (anthropic is None in the test env → the
#                OpenAI branch of block_pipeline._llm_call is exercised). Records `.calls`.
#   _FakeHTTPClient — the test_28 httpx double, carried verbatim for Plan 03's gate re-check.
# ──────────────────────────────────────────────────────────────────────────────


class _Choice:
    def __init__(self, text):
        self.message = type("_M", (), {"content": text})()


class _Resp:
    def __init__(self, text):
        self.choices = [_Choice(text)]
        self.usage = None


class _FakeLLM:
    """FIFO OpenAI-shape client. Each `.chat.completions.create(...)` pops the next canned
    response string (last one is sticky, reused for every further call) and records the call."""

    def __init__(self, *responses):
        self._q = list(responses)
        self.calls = []

    class _CC:
        def __init__(self, outer):
            self._o = outer

        def create(self, *, model, messages, temperature, max_tokens, **k):
            self._o.calls.append({"model": model, "messages": messages})
            text = self._o._q.pop(0) if len(self._o._q) > 1 else self._o._q[0]
            return _Resp(text)

    @property
    def chat(self):
        return type("_Chat", (), {"completions": _FakeLLM._CC(self)})()


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json


class _FakeHTTPClient:
    """{url: [outcome, ...]} FIFO with last-element-sticky semantics (test_28 shape). Carried
    for the Plan-03 dedup-cache assert; unused in Plans 01/02 (no gate re-check yet)."""

    def __init__(self, responses=None):
        self._responses = {k: list(v) for k, v in (responses or {}).items()}
        self.calls = []

    def _next(self, url):
        self.calls.append(url)
        queue = self._responses.get(url)
        if not queue:
            raise AssertionError(f"_FakeHTTPClient: no queued response for {url!r}")
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(outcome, Exception):
            raise outcome
        code, json_data = outcome
        return _FakeResponse(code, json_data)

    def get(self, url, *, headers=None, timeout=None, **kwargs):
        return self._next(url)

    def head(self, url, *, timeout=None, follow_redirects=None, **kwargs):
        return self._next(url)


# ──────────────────────────────────────────────────────────────────────────────
# Canned-judge-JSON builders — emit a valid both-bodies × 5-dim judge payload with the
# per-dimension scores a test passes in (default score used for unspecified dims).
# ──────────────────────────────────────────────────────────────────────────────


def _dim_entry(score):
    return {
        "score": score,
        "evidence": "a quoted sentence from the draft",
        "exemplar_before": "a weaker phrasing",
        "exemplar_after": "a sharper phrasing",
    }


def _body_scores(overrides=None, *, default=5, continuity_na=False):
    overrides = overrides or {}
    out = {}
    for dim in jl._DIMENSIONS:
        if dim == "continuity" and continuity_na:
            out[dim] = {"score": "n/a", "evidence": "no prior editions",
                        "exemplar_before": "n/a", "exemplar_after": "n/a"}
        else:
            out[dim] = _dim_entry(overrides.get(dim, default))
    return out


def _judge_payload(*, technical=None, impact=None, default=5, continuity_na=False):
    return {
        "technical": _body_scores(technical, default=default, continuity_na=continuity_na),
        "impact": _body_scores(impact, default=default, continuity_na=continuity_na),
    }


def _judge_json(**kwargs):
    return json.dumps(_judge_payload(**kwargs))


def _judge_json_missing_evidence():
    """A schema-INVALID judge payload: one dimension lacks the required `evidence` (JUDGE-05)."""
    payload = _judge_payload()
    del payload["technical"]["hedging_filler"]["evidence"]
    return json.dumps(payload)


def _revise_json(*, content_markdown="REVISED technical body",
                 content_markdown_impact="REVISED impact body"):
    """A canned targeted-revise output: BOTH bodies rewritten as a unit (D-08)."""
    return json.dumps({"content_markdown": content_markdown,
                       "content_markdown_impact": content_markdown_impact})


def _revise_calls(llm):
    """The subset of `_FakeLLM.calls` whose SYSTEM prompt marks it as a targeted revise (not a
    judge). Judge + revise share the same model, so the call purpose is read off the system
    prompt ("Fix EXACTLY ..." only appears in the revise system)."""
    return [c for c in llm.calls if "fix exactly" in c["messages"][0]["content"].lower()]


def _judge_calls(llm):
    return [c for c in llm.calls if "editorial judge" in c["messages"][0]["content"].lower()]


# ══════════════════════════════════════════════════════════════════════════════
# JUDGE-01 — fail-loud entry guard
# ══════════════════════════════════════════════════════════════════════════════


def test_guard_and_shortcircuit():
    """A non-empty `det_flags['fabrication']` is a mis-wired caller → hard ValueError. Layer 2
    must NEVER run (and never auto-revise) a draft that carries a live fabrication (JUDGE-01).
    Conversely, a clean all-pass judge on a fabrication-clean draft returns `passed` at
    attempt 0 with NO revise call."""
    draft = _make_draft()
    det = {"fabrication": [{"kind": "tier1_entity", "value": "FakeCorp"}],
           "unverified": [], "mechanical": [], "meta": {}}
    with pytest.raises(ValueError, match="fabrication"):
        jl.run_layer2(draft, _block_fact_base(), _applicable_prior(), det, {}, _FakeLLM("{}"))

    # Clean all-pass canned judge (every dim 5) → passed at attempt 0, exactly one judge call.
    llm = _FakeLLM(_judge_json(default=5))
    out = jl.run_layer2(draft, _block_fact_base(), _applicable_prior(),
                        _clean_det_flags(), {}, llm)
    assert out["verdict"] == "passed"
    assert out["selected_attempt"] == 0
    assert len(out["attempts"]) == 1
    assert out["attempts"][0]["eval_status"] == "ok"
    assert len(llm.calls) == 1  # judge only — no revise call (attempt 0 clean)


def test_guard_rejects_non_dict_draft():
    """A wrong/missing draft surfaces as a clear contract error (not a bare AttributeError)."""
    with pytest.raises(ValueError, match="draft must be a dict"):
        jl.run_layer2("not a draft", _block_fact_base(), _applicable_prior(),
                      _clean_det_flags(), {}, _FakeLLM("{}"))


# ══════════════════════════════════════════════════════════════════════════════
# JUDGE-04 / D-04 — deterministic filler pre-pass + threshold engine
# ══════════════════════════════════════════════════════════════════════════════


def test_count_filler_hits():
    """Case-insensitive count of every blacklist-phrase occurrence."""
    text = ("As we move forward, it remains to be seen where this goes. "
            "AS WE MOVE FORWARD, nothing is certain.")
    hits = jl._count_filler_hits(text, jl.DEFAULT_FILLER_BLACKLIST)
    assert hits == 3  # "as we move forward" ×2 (case-insensitive) + "it remains to be seen" ×1


def test_filler_hit_combination():
    """D-04: hedging fails on the deterministic filler combination even with a passing score
    (score >= hedging_fail_below but hits >= hedging_filler_hits_max)."""
    cfg = jl._merged_config({})
    scores = _judge_payload(technical={"hedging_filler": 4}, impact={"hedging_filler": 4})
    # 3 filler hits on the technical body >= hedging_filler_hits_max (3) → fails despite score 4.
    failing = jl._compute_failing_dims(scores, {"technical": 3, "impact": 0}, cfg,
                                       continuity_applicable=True)
    assert "hedging_filler" in failing
    # Score 4 + 0 hits → not failing.
    failing2 = jl._compute_failing_dims(scores, {"technical": 0, "impact": 0}, cfg,
                                        continuity_applicable=True)
    assert "hedging_filler" not in failing2


def test_compute_failing_dims_below_threshold():
    """A dimension whose score is below its fail_below threshold is in the failing set; a
    passing dimension is not."""
    cfg = jl._merged_config({})
    scores = _judge_payload(technical={"specificity": 2}, impact={"specificity": 2})
    failing = jl._compute_failing_dims(scores, {"technical": 0, "impact": 0}, cfg,
                                       continuity_applicable=True)
    assert "specificity" in failing
    assert "clickbait" not in failing


def test_compute_failing_both_bodies_min():
    """D-08: a dimension fails for the version if EITHER body fails (worst-case via min) —
    impact score 2 + technical score 5 → the dimension fails."""
    cfg = jl._merged_config({})
    scores = _judge_payload(technical={"clickbait": 5}, impact={"clickbait": 2})
    failing = jl._compute_failing_dims(scores, {"technical": 0, "impact": 0}, cfg,
                                       continuity_applicable=True)
    assert "clickbait" in failing


def test_continuity_na_compute():
    """D-05: continuity scores 1 (hard-fail) when applicable, but is EXCLUDED entirely when the
    corpus is empty (never a fail, never counted)."""
    cfg = jl._merged_config({})
    # Applicable + continuity 1 → in failing (continuity_fail_below defaults to 4).
    scores = _judge_payload(technical={"continuity": 1}, impact={"continuity": 1})
    failing = jl._compute_failing_dims(scores, {"technical": 0, "impact": 0}, cfg,
                                       continuity_applicable=True)
    assert "continuity" in failing
    # Not applicable + continuity "n/a" (other dims clean) → continuity excluded, nothing fails.
    scores_na = _judge_payload(default=5, continuity_na=True)
    failing_na = jl._compute_failing_dims(scores_na, {"technical": 0, "impact": 0}, cfg,
                                          continuity_applicable=False)
    assert "continuity" not in failing_na
    assert failing_na == []


def test_merged_config_partial_and_blacklist_fallback():
    """A partial `edition_eval` merges over DEFAULT_CONFIG; an empty filler_blacklist falls back
    to DEFAULT_FILLER_BLACKLIST (RESEARCH A4)."""
    cfg = jl._merged_config({"edition_eval": {"judge_temperature": 0.9,
                                              "thresholds": {"specificity_fail_below": 5}}})
    assert cfg["judge_temperature"] == 0.9           # caller override
    assert cfg["judge_model"] == "claude-sonnet-4-6"  # default preserved
    assert cfg["thresholds"]["specificity_fail_below"] == 5      # merged threshold
    assert cfg["thresholds"]["continuity_fail_below"] == 4       # default threshold preserved
    assert cfg["filler_blacklist"] == jl.DEFAULT_FILLER_BLACKLIST  # empty → fallback


# ══════════════════════════════════════════════════════════════════════════════
# JUDGE-02 / D-08 — the 5-dimension judge scores both bodies in ONE call
# ══════════════════════════════════════════════════════════════════════════════


def test_judge_scores_both_bodies():
    """One judge call per pipeline_version scores BOTH bodies across all five dimensions, each
    with a numeric score + non-empty evidence + before/after exemplar (JUDGE-02, D-08)."""
    llm = _FakeLLM(_judge_json(default=4))
    draft = _make_draft(content_markdown="tech body", content_markdown_impact="impact body")
    cfg = jl._merged_config({})
    result = jl._judge_draft(draft, _applicable_prior(), llm, cfg)
    assert result["status"] == "ok"
    scores = result["scores"]
    for body in ("technical", "impact"):
        assert set(scores[body].keys()) == set(jl._DIMENSIONS)
        for dim in jl._DIMENSIONS:
            entry = scores[body][dim]
            assert isinstance(entry["score"], (int, float))
            assert entry["evidence"].strip()
            assert entry["exemplar_before"].strip()
            assert entry["exemplar_after"].strip()
    assert len(llm.calls) == 1  # exactly ONE call for both bodies (D-08)
    # The single call carried BOTH bodies in the prompt.
    user_msg = llm.calls[0]["messages"][-1]["content"]
    assert "TECHNICAL BODY" in user_msg and "IMPACT BODY" in user_msg


# ══════════════════════════════════════════════════════════════════════════════
# JUDGE-05 — schema-reject → one retry → error → escalated (never a fabricated 0)
# ══════════════════════════════════════════════════════════════════════════════


def test_schema_reject_retry_then_error():
    """A judge response missing evidence is schema-rejected and retried ONCE; a valid retry
    recovers `ok` after exactly 2 calls, and two invalids escalate — never a fabricated 0."""
    draft = _make_draft()
    cfg = jl._merged_config({})

    # invalid (missing evidence) → valid: recovers ok after exactly 2 calls.
    llm_ok = _FakeLLM(_judge_json_missing_evidence(), _judge_json(default=5))
    recovered = jl._judge_draft(draft, _applicable_prior(), llm_ok, cfg)
    assert recovered["status"] == "ok"
    assert len(llm_ok.calls) == 2

    # two invalids → judge status error → run_layer2 maps to verdict 'escalated' (does NOT hold).
    llm_err = _FakeLLM(_judge_json_missing_evidence(), _judge_json_missing_evidence())
    out = jl.run_layer2(draft, _block_fact_base(), _applicable_prior(),
                        _clean_det_flags(), {}, llm_err)
    assert out["verdict"] == "escalated"
    assert out["selected_attempt"] == 0
    assert out["attempts"][0]["eval_status"] == "error"
    assert out["attempts"][0]["error"] and "schema-invalid" in out["attempts"][0]["error"]
    assert out["attempts"][0]["judge_scores"] is None  # never a fabricated 0
    assert len(llm_err.calls) == 2  # 1 + 1 retry, no revise


def test_validate_judge_response_rejects_missing_evidence():
    """`_validate_judge_response` raises on a dimension missing quoted evidence (JUDGE-05)."""
    payload = _judge_payload()
    del payload["impact"]["specificity"]["exemplar_after"]
    with pytest.raises(ValueError, match="exemplar_after"):
        jl._validate_judge_response(payload, continuity_applicable=True)


# ══════════════════════════════════════════════════════════════════════════════
# JUDGE-03 / D-05 — continuity n/a excluded on an empty corpus (no bridge fabricated)
# ══════════════════════════════════════════════════════════════════════════════


def test_continuity_na_excluded():
    """With an empty corpus the judge scores continuity "n/a" (other dims ≥4); run_layer2
    excludes continuity from the verdict and returns `passed` — no bridge fabricated (D-05)."""
    draft = _make_draft()
    llm = _FakeLLM(_judge_json(default=4, continuity_na=True))
    out = jl.run_layer2(draft, _block_fact_base(), _empty_prior(),
                        _clean_det_flags(), {}, llm)
    assert out["verdict"] == "passed"
    assert out["selected_attempt"] == 0
    assert len(llm.calls) == 1  # judge only, no revise
    # The judge was told no prior editions exist (so it does not fabricate a bridge).
    user_msg = llm.calls[0]["messages"][-1]["content"]
    assert "NO prior published editions exist" in user_msg


# ══════════════════════════════════════════════════════════════════════════════
# LOOP-01 / D-07 / D-08 — targeted revise call + structured feedback builder (Plan 02 Task 1)
# ══════════════════════════════════════════════════════════════════════════════


def test_revise_called_with_feedback():
    """LOOP-01/D-07/D-08: a failing dimension drives a TARGETED revise (not a full writer
    re-run). The revise call's user message carries the failing dimension name + the judge's
    quoted evidence/exemplar (structured feedback, not "improve X") AND the source-facts
    guardrail; the returned draft has BOTH bodies replaced from the revise JSON while
    title/title_impact stay unchanged (D-08)."""
    draft = _make_draft(title="Keep Title", title_impact="Keep Impact Title",
                        content_markdown="original tech body",
                        content_markdown_impact="original impact body")
    scores = _judge_payload(technical={"specificity": 2}, impact={"specificity": 2})
    feedback = jl._build_feedback(scores, ["specificity"], None)

    # Structured feedback names the dim + carries the judge evidence/exemplar (not vague).
    assert "specificity" in feedback
    assert "a quoted sentence from the draft" in feedback   # the judge evidence
    assert "a sharper phrasing" in feedback                 # the judge exemplar_after
    assert "improve specificity" not in feedback.lower()

    fact_base = _block_fact_base(
        blocks=[{"description": "OpenAI shipped Agents SDK", "named_entities": ["OpenAI"]}])
    llm = _FakeLLM(_revise_json())
    cfg = jl._merged_config({})
    revised = jl._revise_draft(draft, feedback, fact_base, llm, cfg)

    # BOTH bodies replaced as a unit (D-08); titles untouched.
    assert revised["content_markdown"] == "REVISED technical body"
    assert revised["content_markdown_impact"] == "REVISED impact body"
    assert revised["title"] == "Keep Title"
    assert revised["title_impact"] == "Keep Impact Title"

    # Exactly one (revise) call; its user message carried the structured feedback + source facts.
    assert len(llm.calls) == 1
    user_msg = llm.calls[0]["messages"][-1]["content"]
    assert "specificity" in user_msg
    assert "a sharper phrasing" in user_msg                 # judge exemplar rode into the prompt
    assert "OpenAI shipped Agents SDK" in user_msg          # the _fact_base_source_texts guardrail


def test_build_feedback_continuity_bridge_and_no_fabrication():
    """D-06: a failing continuity dim yields an EXPLICIT bridge-to-prior-edition instruction (not
    the vague "improve continuity"). Fabrication-shaped flags NEVER appear in the feedback;
    mechanical flags ride along only when a judge dim fails (D-12)."""
    scores = _judge_payload(technical={"continuity": 1}, impact={"continuity": 1})
    feedback = jl._build_feedback(scores, ["continuity"], None)
    low = feedback.lower()
    assert "bridge" in low                     # explicit bridge instruction (D-06)
    assert "continuity" in low
    assert "improve continuity" not in low     # NOT the vague phrasing
    assert "FakeCorp" not in feedback          # no fabrication value leaks in (only mechanical rides)

    # Mechanical rides along when a dim independently fails (LOOP-04/D-12) — but never fabrication.
    scores2 = _judge_payload(technical={"specificity": 2}, impact={"specificity": 2})
    fb2 = jl._build_feedback(scores2, ["specificity"],
                             [{"kind": "recycled_closer", "detail": "closer echoes prior edition"}])
    assert "recycled_closer" in fb2 or "closer echoes prior edition" in fb2
    assert "FakeCorp" not in fb2


# ══════════════════════════════════════════════════════════════════════════════
# LOOP-02 / D-06 / D-08 / D-11 — the N=2 loop + best-attempt selection (Plan 02 Task 2)
# ══════════════════════════════════════════════════════════════════════════════


def test_n2_hard_stop():
    """LOOP-02 / Pitfall 5: a draft failing EVERY attempt terminates HARD at N=2 →
    verdict='held_voice', EXACTLY 2 revise calls (no 3rd), and 3 judged attempts in telemetry
    (attempt 0 + 2 rewrites). No best-effort publish."""
    draft = _make_draft()
    j = _judge_json(technical={"specificity": 2}, impact={"specificity": 2})
    r = _revise_json()
    llm = _FakeLLM(j, r, j, r, j)   # J0, R1, J1, R2, J2
    out = jl.run_layer2(draft, _block_fact_base(), _applicable_prior(), _clean_det_flags(), {}, llm)

    assert out["verdict"] == "held_voice"
    assert len(_revise_calls(llm)) == 2                                  # exactly 2 revises, no 3rd
    assert len(_judge_calls(llm)) == 3                                   # judge scored 3 drafts
    ok_attempts = [a for a in out["attempts"] if a["eval_status"] == "ok"]
    assert len(ok_attempts) == 3
    assert set(out.keys()) == {"final_draft", "verdict", "selected_attempt", "attempts"}  # LOOP-05 shape


def test_continuity_absent_triggers():
    """D-06 / LOOP-01: a continuity hard-fail (bridge absent → score 1) TRIGGERS the rewrite
    loop; the attempt-1 revise that adds the bridge → verdict='passed', selected_attempt=1,
    EXACTLY 1 revise call, and the revise feedback carried a bridge instruction."""
    draft = _make_draft()
    j_fail = _judge_json(technical={"continuity": 1}, impact={"continuity": 1})
    r = _revise_json()
    j_pass = _judge_json(default=5)
    llm = _FakeLLM(j_fail, r, j_pass)
    out = jl.run_layer2(draft, _block_fact_base(), _applicable_prior(), _clean_det_flags(), {}, llm)

    assert out["verdict"] == "passed"
    assert out["selected_attempt"] == 1
    revises = _revise_calls(llm)
    assert len(revises) == 1
    assert "bridge" in revises[0]["messages"][-1]["content"].lower()    # D-06 bridge instruction


def test_both_bodies_fail_together():
    """D-08: an impact-only dimension failure (impact specificity 2, technical 5) still counts as
    failing (worst-case min) and fires a revise that rewrites BOTH bodies as a unit."""
    draft = _make_draft(content_markdown="tech", content_markdown_impact="impact")
    j_fail = _judge_json(technical={"specificity": 5}, impact={"specificity": 2})
    r = _revise_json(content_markdown="NEW TECH", content_markdown_impact="NEW IMPACT")
    j_pass = _judge_json(default=5)
    llm = _FakeLLM(j_fail, r, j_pass)
    out = jl.run_layer2(draft, _block_fact_base(), _applicable_prior(), _clean_det_flags(), {}, llm)

    assert out["verdict"] == "passed"
    assert out["selected_attempt"] == 1
    assert len(_revise_calls(llm)) == 1
    # BOTH bodies were rewritten together (D-08).
    assert out["final_draft"]["content_markdown"] == "NEW TECH"
    assert out["final_draft"]["content_markdown_impact"] == "NEW IMPACT"


def test_best_attempt_selection():
    """D-11: `_select_best_attempt` returns the FEWEST-failing attempt (not necessarily the
    latest); ties break by highest summed per-dimension score, then by latest attempt."""
    a0 = {"attempt": 0, "eval_status": "ok", "failing": ["a", "b"], "summed_score": 30, "draft": {"id": 0}}
    a1 = {"attempt": 1, "eval_status": "ok", "failing": ["a"], "summed_score": 40, "draft": {"id": 1}}
    a2 = {"attempt": 2, "eval_status": "ok", "failing": ["a", "b"], "summed_score": 45, "draft": {"id": 2}}
    assert jl._select_best_attempt([a0, a1, a2])["attempt"] == 1    # fewest fails, NOT latest

    # Tie on failing count → highest summed score wins.
    b0 = {"attempt": 0, "eval_status": "ok", "failing": ["a"], "summed_score": 30, "draft": {}}
    b1 = {"attempt": 1, "eval_status": "ok", "failing": ["a"], "summed_score": 50, "draft": {}}
    b2 = {"attempt": 2, "eval_status": "ok", "failing": ["a"], "summed_score": 40, "draft": {}}
    assert jl._select_best_attempt([b0, b1, b2])["attempt"] == 1    # highest summed score

    # Full tie (failing count AND summed score) → latest wins.
    c1 = {"attempt": 1, "eval_status": "ok", "failing": ["a"], "summed_score": 40, "draft": {}}
    c2 = {"attempt": 2, "eval_status": "ok", "failing": ["a"], "summed_score": 40, "draft": {}}
    assert jl._select_best_attempt([c1, c2])["attempt"] == 2        # latest on a full tie


def test_held_voice_returns_best_not_latest():
    """D-11 end-to-end: with N=2 exhausted, held_voice returns the BEST attempt (fewest fails),
    NOT the latest. attempt-1 fails 1 dim; attempts 0 and 2 fail 2 dims → selected_attempt=1 and
    final_draft is attempt-1's revised body."""
    draft = _make_draft()
    j0 = _judge_json(technical={"specificity": 2, "clickbait": 2},
                     impact={"specificity": 2, "clickbait": 2})       # 2 failing dims
    r1 = _revise_json(content_markdown="ATTEMPT1 TECH", content_markdown_impact="ATTEMPT1 IMPACT")
    j1 = _judge_json(technical={"specificity": 2}, impact={"specificity": 2})   # 1 failing dim
    r2 = _revise_json(content_markdown="ATTEMPT2 TECH", content_markdown_impact="ATTEMPT2 IMPACT")
    j2 = _judge_json(technical={"specificity": 2, "clickbait": 2},
                     impact={"specificity": 2, "clickbait": 2})       # 2 failing dims
    llm = _FakeLLM(j0, r1, j1, r2, j2)
    out = jl.run_layer2(draft, _block_fact_base(), _applicable_prior(), _clean_det_flags(), {}, llm)

    assert out["verdict"] == "held_voice"
    assert out["selected_attempt"] == 1                              # best = fewest fails, not latest (2)
    assert out["final_draft"]["content_markdown"] == "ATTEMPT1 TECH"


# ══════════════════════════════════════════════════════════════════════════════
# D-01 / D-02 / D-03 — per-rewrite Layer-1 re-check (Plan 03 Task 1)
#   The rewrite is untrusted LLM output. EVERY rewrite is re-verified by re-running the SAME
#   deterministic engine (run_deterministic_gate) BEFORE it is re-judged. A NEW fabrication is a
#   hard abort that keeps the clean attempt-0 draft (D-02); a transient network error is visible
#   telemetry that never holds (D-03); an unchanged ref is served from the cross-attempt dedup
#   cache (D-01). All three inject the reused test_28 _FakeHTTPClient (zero live egress).
# ══════════════════════════════════════════════════════════════════════════════


def test_held_fabrication_keeps_attempt0():
    """D-01/D-02: attempt-0 is fabrication-clean but fails a voice dim; the attempt-1 revise
    INTRODUCES a `github.com/owner/newrepo` that the fake client 404s → the per-rewrite Layer-1
    re-check aborts to verdict='held_fabrication', `final_draft` is the ORIGINAL attempt-0 draft
    (NEVER the fabricated rewrite), and the rejected rewrite's flags live in telemetry ONLY."""
    draft = _make_draft(content_markdown="original clean technical prose about agents",
                        content_markdown_impact="original clean impact prose about agents")
    j0 = _judge_json(technical={"specificity": 2}, impact={"specificity": 2})   # fail → triggers revise
    r_fab = _revise_json(content_markdown="the tool now lives at github.com/owner/newrepo",
                         content_markdown_impact="the tool now lives at github.com/owner/newrepo")
    llm = _FakeLLM(j0, r_fab)
    fake = _FakeHTTPClient({"https://api.github.com/repos/owner/newrepo": [(404, {})]})
    out = jl.run_layer2(draft, _block_fact_base(), _applicable_prior(), _clean_det_flags(), {},
                        llm, http_client=fake)

    assert out["verdict"] == "held_fabrication"
    assert out["selected_attempt"] == 0
    # final_draft is the ORIGINAL fabrication-clean attempt-0 draft, NEVER the fabricated rewrite.
    assert out["final_draft"]["content_markdown"] == "original clean technical prose about agents"
    assert "newrepo" not in out["final_draft"]["content_markdown"]
    # the rejected rewrite's flags are in telemetry ONLY (the judge never scored it).
    rejected = out["attempts"][-1]
    assert rejected["attempt"] == 1
    assert rejected["reverify_flags"]["fabrication"]         # non-empty — the invented repo
    assert rejected["judge_scores"] is None                 # never judged (aborted before judging)
    # exactly one judge + one revise call — the fabricated rewrite is NEVER judged.
    assert len(_judge_calls(llm)) == 1
    assert len(_revise_calls(llm)) == 1


def test_unverified_never_holds():
    """D-03: the attempt-1 revise introduces a URL the fake client 5xx's → the re-check records
    `unverified` but NEVER aborts and NEVER holds ('an error is not evidence'). The loop proceeds,
    the attempt-1 draft passes, and the `unverified` entry appears in that attempt's reverify_flags
    (never folded into fabrication)."""
    draft = _make_draft()
    j_fail = _judge_json(technical={"specificity": 2}, impact={"specificity": 2})
    r_unv = _revise_json(content_markdown="the team shipped an update, see https://example.com/missing",
                         content_markdown_impact="the team shipped an update, see https://example.com/missing")
    j_pass = _judge_json(default=5)
    llm = _FakeLLM(j_fail, r_unv, j_pass)
    fake = _FakeHTTPClient({"https://example.com/missing": [(500, {})]})
    out = jl.run_layer2(draft, _block_fact_base(), _applicable_prior(), _clean_det_flags(), {},
                        llm, http_client=fake)

    assert out["verdict"] == "passed"                        # unverified NEVER holds/aborts (D-03)
    assert out["selected_attempt"] == 1
    reverify = out["attempts"][1]["reverify_flags"]
    assert reverify["unverified"]                            # the 5xx URL recorded as unverified
    assert not reverify["fabrication"]                       # never folded into fabrication (D-03)


def test_dedup_cache_calls_do_not_grow():
    """D-01 (Pitfall 3): the SAME github ref appears in BOTH rewrites; the module-owned
    _CachingHTTPClient persists the Phase-28 dedup cache ACROSS attempts, so an unchanged ref is
    fetched ONCE (attempt-1 re-check) and served from cache on attempt-2 — `_FakeHTTPClient.calls`
    does NOT grow for that url across attempts."""
    draft = _make_draft()
    j_fail = _judge_json(technical={"specificity": 2}, impact={"specificity": 2})
    r = _revise_json(content_markdown="the update is live, see github.com/owner/liverepo",
                     content_markdown_impact="the update is live, see github.com/owner/liverepo")
    llm = _FakeLLM(j_fail, r, j_fail, r, j_fail)             # J0,R1,J1,R2,J2 → held_voice (2 revises)
    fake = _FakeHTTPClient({"https://api.github.com/repos/owner/liverepo": [(200, {"stargazers_count": 100})]})
    out = jl.run_layer2(draft, _block_fact_base(), _applicable_prior(), _clean_det_flags(), {},
                        llm, http_client=fake)

    assert out["verdict"] == "held_voice"
    gh_calls = [c for c in fake.calls if "owner/liverepo" in c]
    assert len(gh_calls) == 1                                # fetched once, cache-served on attempt-2 (D-01)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
