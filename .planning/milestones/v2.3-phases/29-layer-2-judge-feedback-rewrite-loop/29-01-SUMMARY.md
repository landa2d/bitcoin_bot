---
phase: 29-layer-2-judge-feedback-rewrite-loop
plan: 01
subsystem: testing
tags: [newsletter, eval, llm-judge, sonnet, editorial-voice, pure-module, fail-loud, tdd]

# Dependency graph
requires:
  - phase: 26-continuity-exemplar-context
    provides: "load_edition_context() -> prior_context {previous_editions, exemplars, empty} — the judge's continuity anchor + n/a (D-05) driver"
  - phase: 27-eval-persistence-governed-agent
    provides: "edition_eval.py write_eval_row param contract (telemetry maps 1:1) + LLM_PROXY_EVAL_KEY governed identity (GOV-01)"
  - phase: 28-layer-1-deterministic-gate
    provides: "deterministic_gate.run_deterministic_gate (Plan-02 per-rewrite re-check) + _fact_base_source_texts (revise guardrail); test_28 fake-httpx + fixture shapes"
provides:
  - "docker/newsletter/judge_loop.py: PURE run_layer2(...) module — signature + fail-loud entry guard (JUDGE-01)"
  - "5-dimension exemplar-anchored Sonnet judge scoring BOTH bodies in one call (JUDGE-02/03/04), with the JUDGE-05 schema-reject -> one-retry -> escalated contract"
  - "config-tunable both-bodies threshold engine _compute_failing_dims (D-04/D-05/D-08) + deterministic filler pre-pass _count_filler_hits"
  - "attempt-0 run_layer2 verdicts (passed / escalated); N=2 revise loop is a documented Plan-02 extension point"
  - "config/agentpulse-config.json edition_eval block (continuity_fail_below=4)"
affects: [phase-30-sequencer-wiring, phase-31-surfacing, judge_loop-plan-02-n2-loop, judge_loop-plan-03-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure eval module (no supabase/no live proxy/no write) generalizing phase_e_voice_check from 1 dim to 5×2 bodies"
    - "Injected governed llm_client (edition_eval identity) — module never constructs a client or references a provider key"
    - "Robust parse_llm_json + structural schema gate -> one retry -> fail-loud escalated (never a fabricated 0)"
    - "Interface-first: signature + entry guard + threshold engine locked in Plan 01; N=2 loop consumes the failing-dim set in Plan 02"

key-files:
  created:
    - "docker/newsletter/judge_loop.py"
    - "tests/test_29_judge_loop.py"
  modified:
    - "config/agentpulse-config.json"

key-decisions:
  - "Module filename judge_loop.py (Claude's discretion); edition_eval.py stays the persistence helper (not overloaded)"
  - "Judge output schema: both-bodies {technical,impact} × 5 dims, each {score, evidence, exemplar_before, exemplar_after}; continuity accepts string 'n/a' ONLY when not applicable (D-05)"
  - "One judge call per pipeline_version scoring both bodies (D-08); temperature 0.2 / max_tokens 1500 (config-tunable)"
  - "Both-bodies worst-case via min(technical, impact) < fail_below; hedging ALSO fails on max filler hits >= hedging_filler_hits_max (D-04 combination)"
  - "n/a continuity is exempt from the evidence/exemplar schema requirement (nothing to bridge); numeric continuity requires evidence like every other dim"
  - "attempt-0 emits passed/escalated only; a failing attempt-0 raises a documented NotImplementedError (Plan-02 seam) rather than emitting a wrong verdict"

patterns-established:
  - "Pattern: governed-identity discipline grep-verified (0 references to the newsletter service's own client / provider key)"
  - "Pattern: no brittle triple-backtick fence strip anywhere — parse_llm_json (context=layer2_judge) only"

requirements-completed: []  # JUDGE-01..05 cores BUILT + PROVEN here; closure deferred to phase end (after Plans 02/03 + verify), consistent with the 27/28 fail-loud-accuracy posture

# Metrics
duration: 14min
completed: 2026-07-01
---

# Phase 29 Plan 01: Layer-2 Judge + Scoring Core Summary

**Pure `run_layer2(...)` module — fail-loud entry guard + a 5-dimension exemplar-anchored Sonnet judge (both bodies, one call, schema-reject→retry→escalated) + a config-tunable both-bodies threshold engine — with the `edition_eval` config block (continuity_fail_below=4).**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-07-01
- **Completed:** 2026-07-01
- **Tasks:** 2
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments
- **`docker/newsletter/judge_loop.py`** (NEW) — the PURE Layer-2 module (D-09): `run_layer2(draft, fact_base, prior_context, det_flags, config, llm_client, *, http_client=None, github_token=None)` with the fail-loud entry guard (JUDGE-01: a non-empty `det_flags['fabrication']` raises `ValueError` — Layer 2 never runs on a fabricated draft), `DEFAULT_CONFIG` + `_merged_config` deep-merge, `DEFAULT_FILLER_BLACKLIST` (verbatim IDENTITY.md), `_count_filler_hits`, and the both-bodies threshold engine `_compute_failing_dims`.
- **The 5-dimension judge** (`_build_judge_prompt` + `_validate_judge_response` + `_judge_draft`) — scores technical + impact bodies 1-5 across continuity/hedging_filler/clickbait/repeated_subtopics/specificity in ONE call per pipeline_version (D-08), each dim requiring a numeric score + quoted evidence + before/after exemplar. Reuses `_llm_call` (proxied) + `parse_llm_json` (robust, fail-loud). JUDGE-05 contract: schema-reject → one retry → `status='error'` → verdict `escalated` (never a fabricated 0).
- **attempt-0 `run_layer2` verdicts** — `escalated` on an un-scoreable judge; `passed` when no dimension fails; the N=2 targeted-revise loop is a documented Plan-02 extension point (explicit `NotImplementedError`, no wrong verdict emitted).
- **`config/agentpulse-config.json`** — new top-level `edition_eval` block with the operator-confirmed `continuity_fail_below=4` and the D-04 thresholds verbatim.
- **`tests/test_29_judge_loop.py`** — 12 tests on the REAL module with an OpenAI-shape `_FakeLLM` FIFO client (anthropic absent → OpenAI branch); zero live egress. Covers JUDGE-01 guard, filler combination, both-bodies min, continuity n/a exclusion, both-bodies one-call scoring, schema-reject→retry→escalated, and the clean all-pass → passed path.

## Task Commits

Each task was committed atomically:

1. **Task 1: config `edition_eval` + module scaffold + entry guard + filler pre-pass + threshold engine + test harness** — `9cf175f` (feat)
2. **Task 2: 5-dimension exemplar-anchored judge + schema-reject→retry→error + attempt-0 run_layer2** — `09fa81c` (feat)

**Plan metadata:** (final docs commit — this SUMMARY + STATE + ROADMAP)

## Files Created/Modified
- `docker/newsletter/judge_loop.py` - PURE Layer-2 judge + scoring core; `run_layer2` signature, entry guard, config merge, filler pre-pass, threshold engine, 5-dim judge + schema gate, attempt-0 verdicts.
- `tests/test_29_judge_loop.py` - 12-case suite on the real module; `_FakeLLM` FIFO client + canned both-bodies×5-dim judge JSON builders; `_FakeHTTPClient` carried for Plan 03's gate re-check.
- `config/agentpulse-config.json` - new `edition_eval` block (enabled/enforce false, max_attempts 2, judge/revise model+params, thresholds with continuity_fail_below=4, filler_blacklist []).

## Decisions Made
- **Judge schema shape (Claude's discretion, JUDGE-05-compliant):** both-bodies `{technical,impact}` × 5 dims, each `{score, evidence, exemplar_before, exemplar_after}`; `continuity.score` may be the string `"n/a"` only when not applicable (D-05), and an n/a continuity is exempt from the evidence/exemplar requirement (there is nothing to bridge to) — every numeric dimension still requires evidence + before/after exemplar.
- **One call per pipeline_version, temperature 0.2, max_tokens 1500** (config-tunable) — mirrors `phase_e_voice_check`'s 0.2 and keeps the audience pair coherent (D-08).
- **Threshold combination (D-04):** `min(technical, impact) < fail_below` per dim; `hedging_filler` additionally fails on `max(tech_hits, impact_hits) >= hedging_filler_hits_max`.
- **attempt-0 only emits `passed`/`escalated`;** a failing attempt-0 raises a documented `NotImplementedError` (Plan-02 seam) rather than shipping a wrong `held_voice`/`passed`.

## Deviations from Plan

None - plan executed exactly as written.

Two documentation-wording adjustments (not behavioral deviations): the module docstring's anti-pattern warnings were reworded to describe the brittle fence-strip and the wrong-wallet identity WITHOUT their literal token strings, so the plan's own discipline greps (`grep -c "startswith('\`\`\`')..."` and `grep -c "claude_client\|OPENAI_API_KEY"`) return 0 as the acceptance criteria require. The disciplines themselves are honored in code (parse_llm_json used; no provider-key/default-client reference).

## Issues Encountered
None. All verify gates green on first author (after the docstring grep-wording adjustment above).

## Known Stubs (intentional, Plan-02 resolved)
- `run_layer2` raises `NotImplementedError("N=2 targeted-revise rewrite loop — implemented in Plan 02 ...")` when attempt-0 has failing dimensions. This is a deliberate interface-first extension point (not a data-flow stub): Plan 02 replaces it with the revise loop that consumes the `failing` set this plan computes. Emitting a verdict here without the revise loop would be a wrong verdict — the plan explicitly sanctions the stub.
- `_attempt_row` sets `sats=0` / `model_calls=[]` — the per-call token/sat mapping is finalized in Plan 03 (telemetry-only; no gate depends on it, RESEARCH A3).

## Verification Evidence
- `python3 -c "import json; json.load(open('config/agentpulse-config.json'))"` → OK (config stays valid JSON).
- `python3 -c "import ast; ast.parse(open('docker/newsletter/judge_loop.py').read())"` → OK (CLAUDE.md syntax gate).
- `pytest tests/test_29_judge_loop.py -q` → **12 passed**.
- No-regression: `pytest tests/test_26_continuity_loader.py tests/test_27_edition_eval.py tests/test_28_deterministic_gate.py -q` → **104 passed**.
- Source disciplines (grep): `parse_llm_json` imported (not re-rolled); `context="layer2_judge"` present; 0 brittle triple-backtick strips; 0 wrong-wallet identity references.

## Next Phase Readiness
- The `run_layer2(...)` signature, judge output schema, `_compute_failing_dims` failing-dim contract, and attempt-0 telemetry shape are locked — Plan 02 builds the N=2 loop (`_revise_draft`, per-rewrite `run_deterministic_gate` re-check with the carried `http_client` dedup cache, D-02 `held_fabrication`, D-11 `_select_best_attempt`) on this stable base.
- Requirement closure (JUDGE-01..05) deferred to phase end (after Plans 02/03 + `/gsd-verify-work`), consistent with the operator-validated 27/28 fail-loud-accuracy posture: the judge/scoring cores are fully realized + proven here; live sequencer invocation + short-circuit are Phase 30 (WIRE).
- Still pending (separate, orchestrator/operator-owned, worktree-UNSAFE): Phase 27 Plan 03 — mint the `edition_eval` key + MCP-apply migration 045 — before any Phase-30 LIVE invocation.

## Self-Check: PASSED

---
*Phase: 29-layer-2-judge-feedback-rewrite-loop*
*Completed: 2026-07-01*
