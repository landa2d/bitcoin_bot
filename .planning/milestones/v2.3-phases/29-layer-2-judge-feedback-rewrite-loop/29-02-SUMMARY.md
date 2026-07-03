---
phase: 29-layer-2-judge-feedback-rewrite-loop
plan: 02
subsystem: testing
tags: [newsletter, eval, llm-judge, rewrite-loop, sonnet, targeted-revise, pure-module, fail-loud, tdd]

# Dependency graph
requires:
  - phase: 29-layer-2-judge-feedback-rewrite-loop
    plan: 01
    provides: "run_layer2 signature + entry guard (JUDGE-01), _judge_draft (both-bodies ONE call, JUDGE-05 schema gate), _compute_failing_dims (D-04/D-05/D-08 failing-dim set), _attempt_row telemetry shape, DEFAULT_CONFIG/_merged_config, config edition_eval block"
  - phase: 28-layer-1-deterministic-gate
    provides: "deterministic_gate._fact_base_source_texts (the D-07 revise source-facts guardrail, both fact-base shapes); run_deterministic_gate (the Plan-03 per-rewrite re-check, imported/reserved)"
provides:
  - "docker/newsletter/judge_loop.py: _revise_draft (targeted both-body revise + _fact_base_source_texts guardrail, D-07/D-08), _build_feedback (structured per-dim feedback + explicit continuity bridge D-06 + mechanical-rides param D-12), _select_best_attempt (D-11) + _summed_score, and the FULL bounded N=2 loop in run_layer2 (passed / escalated / held_voice)"
  - "tests/test_29_judge_loop.py: revise_called_with_feedback, build_feedback_continuity_bridge, n2_hard_stop, continuity_absent_triggers, both_bodies_fail_together, best_attempt_selection, held_voice_returns_best (7 new cases)"
affects: [phase-30-sequencer-wiring, judge_loop-plan-03-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Targeted revise (writer-agnostic _llm_call), NOT a full writer re-run — one fn serves single_pass + block_v1 (D-07)"
    - "Bounded N=2 loop: range(0, max_attempts+1); revise only when attempt_no>0 → at most 2 revises, judge scores up to 3 drafts (Pitfall 5)"
    - "held_voice returns the BEST attempt (fewest fails → highest summed score → latest), consuming the per-attempt scoring — not the latest (D-11)"
    - "No best-effort publish: N=2 exhaustion → held_voice; judge error → escalated (returns clean attempt-0); fail-loud throughout"

key-files:
  created: []
  modified:
    - "docker/newsletter/judge_loop.py"
    - "tests/test_29_judge_loop.py"

key-decisions:
  - "_build_feedback signature is (judge_scores, failing, mechanical) per the plan — the continuity bridge instruction is generic ('bridge to the previous edition's theme') + the judge's own exemplar_after (which already encodes the specific N-1 theme, since the judge is shown prior editions); prior_context is NOT re-threaded into _build_feedback"
  - "The worst (lower-scoring) body's evidence/exemplar drives per-dim feedback (_worst_body_entry); the mechanical list is rendered via _describe_mechanical (telemetry-shaped dict → 'kind: detail'), fabrication list is NEVER passed"
  - "run_layer2 returns EXACTLY {final_draft, verdict, selected_attempt, attempts} (LOOP-05); the selected attempt's still-failing dims are recorded in attempts[selected].failing (internal-only telemetry), not a new top-level key"
  - "Judge error at any attempt → escalated, final_draft = the fabrication-clean attempt-0 draft (A2 — the only draft guaranteed clean until Plan 03 adds the per-rewrite Layer-1 re-check)"
  - "_revise_draft is fail-loud: parse_llm_json + a both-bodies non-empty presence check raise on an incomplete revise (no silent half-rewrite); the loop does not yet map a revise failure to escalated (not in this plan's scope; bodies are always valid in tests)"

patterns-established:
  - "Revise/judge call purpose is read off the SYSTEM prompt in tests ('Fix EXACTLY' = revise, 'editorial judge' = judge) since both share claude-sonnet-4-6 — enables the exactly-2-revise / 3-judge assertions"
  - "Plan-03 gate re-check insertion point is a clearly-marked comment inside the attempt_no>0 branch (D-01/D-02/D-03), not a stub call"

requirements-completed: []  # LOOP-01/LOOP-02 cores BUILT + PROVEN here; closure deferred to phase end (after Plan 03 + verify), consistent with the 27/28/29-01 fail-loud-accuracy posture

# Metrics
duration: 8min
completed: 2026-07-01
---

# Phase 29 Plan 02: Layer-2 Feedback-Rewrite Loop Summary

**The bounded N=2 feedback-rewrite loop on top of Plan 01's judge: a targeted both-body revise (`_revise_draft`) with the `_fact_base_source_texts` guardrail, structured per-dimension feedback (`_build_feedback`, explicit continuity bridge), best-attempt selection (`_select_best_attempt`, D-11), and the full `passed`/`escalated`/`held_voice` loop that replaces the Plan-01 `NotImplementedError` seam — targeted revise, hard N=2 cap, no best-effort publish.**

## Performance
- **Duration:** ~8 min
- **Started / Completed:** 2026-07-01
- **Tasks:** 2 (both `tdd="true"`)
- **Files modified:** 2 (0 created)

## Accomplishments
- **`_build_feedback(judge_scores, failing, mechanical)`** — STRUCTURED per-dimension revise feedback (LOOP-01): for each failing dim it names the dimension, quotes the judge's offending `evidence`, and renders the `exemplar_before`→`exemplar_after` fix pattern (never the vague "improve X"). A failing `continuity` dim emits an EXPLICIT bridge-to-prior-edition instruction (D-06 — severity ≠ rewrite-eligibility). The optional `mechanical` list rides along only here and only when `failing` is non-empty (D-12); the fabrication list is never passed (fabrication never enters the loop, LOOP-04). Helpers `_worst_body_entry` (offending body) + `_describe_mechanical` (telemetry dict → note).
- **`_revise_draft(draft, feedback, fact_base, llm_client, cfg)`** — the TARGETED both-body revise (D-07/D-08): builds `source_facts = _fact_base_source_texts(fact_base)` (the same guardrail accessor the gate uses — one fn serves single_pass AND block_v1), sends the structured feedback + both current bodies + the source facts to a single `_llm_call` (Sonnet), parses via `parse_llm_json(context="layer2_revise")`, and returns a NEW draft with BOTH bodies replaced as a unit while `title`/`title_impact`/`pipeline_version` pass through. NOT a full writer re-run. Fail-loud on an incomplete revise (both-bodies non-empty presence check).
- **`_select_best_attempt(ok_attempts)` + `_summed_score(judge_scores)`** — the D-11 tie-break: fewest failing dims → highest summed per-dimension score across both bodies → latest attempt; attempt-0 IS a candidate. `_attempt_row` now carries the internal-only `summed_score` + `draft` keys (not persisted / not `write_eval_row` params).
- **The full N=2 loop in `run_layer2`** — replaced the Plan-01 attempt-0 `NotImplementedError` seam with `for attempt_no in range(0, cfg["max_attempts"] + 1)`: revise only when `attempt_no > 0` (at most 2 revises, judge scores up to 3 drafts — Pitfall 5). `passed` when a rewrite fixes every failing dim; `escalated` (returning the clean attempt-0 draft) on a judge error; after N=2 still failing → `held_voice` with the BEST attempt (D-11), NO best-effort publish (LOOP-02). Returns the pure `{final_draft, verdict, selected_attempt, attempts}` (LOOP-05). The Plan-03 per-rewrite Layer-1 re-check (D-01/D-02/D-03) is a clearly-marked insertion point inside the `attempt_no>0` branch.
- **`tests/test_29_judge_loop.py`** — 7 new cases on the REAL module with the OpenAI-shape `_FakeLLM` FIFO client (zero egress): `revise_called_with_feedback` (D-07/D-08 structured feedback + both-bodies replace + titles untouched + source-facts guardrail), `build_feedback_continuity_bridge_and_no_fabrication` (D-06 bridge, no fabrication leak, mechanical rides), `n2_hard_stop` (exactly 2 revises + 3 judged, held_voice, LOOP-05 key set), `continuity_absent_triggers` (D-06 → passed at attempt 1, 1 revise, bridge in feedback), `both_bodies_fail_together` (impact-only fail → both bodies revised, D-08), `best_attempt_selection` (unit D-11 + tie cases), `held_voice_returns_best_not_latest` (e2e D-11 — selected_attempt=1, not the latest 2).

## Task Commits
1. **RED (both tasks): failing tests for targeted revise, feedback builder + N=2 loop** — `3aa642f` (test)
2. **Task 1 GREEN: targeted revise call + structured feedback builder (LOOP-01, D-07, D-08)** — `31b76fd` (feat)
3. **Task 2 GREEN: N=2 rewrite loop + best-attempt selection + held_voice/passed (LOOP-02, D-06, D-11)** — `df86805` (feat)

**Plan metadata:** (final docs commit — this SUMMARY + STATE + ROADMAP + deferred-items)

## Files Created/Modified
- `docker/newsletter/judge_loop.py` — added `_build_feedback`, `_revise_draft`, `_worst_body_entry`, `_describe_mechanical`, `_select_best_attempt`, `_summed_score`, `REVISE_SYSTEM`/`REVISE_PROMPT`; extended `_attempt_row` (internal `summed_score`/`draft`); replaced the attempt-0 `NotImplementedError` seam with the full N=2 loop in `run_layer2`.
- `tests/test_29_judge_loop.py` — added 7 cases + `_revise_json`/`_revise_calls`/`_judge_calls` helpers.

## Decisions Made
- **`_build_feedback` keeps the plan's `(judge_scores, failing, mechanical)` signature** — it does NOT receive `prior_context`. The continuity feedback pairs a generic explicit bridge instruction ("Add a lead sentence bridging to the previous edition's theme") with the judge's own `exemplar_after`, which already encodes the specific N-1 theme (the judge is shown the prior editions). This satisfies D-06 "bridge to edition N-1's <theme>, not 'improve continuity'" without re-threading `prior_context`.
- **`run_layer2` returns EXACTLY the 4-key contract** `{final_draft, verdict, selected_attempt, attempts}` (LOOP-05). The selected attempt's still-failing dims are recorded in `attempts[selected]["failing"]` (internal telemetry), not as a new top-level key — keeping the pure shape.
- **Judge error → `escalated`, `final_draft` = the fabrication-clean attempt-0 draft** (A2): until Plan 03 adds the per-rewrite Layer-1 re-check, attempt-0 is the only draft guaranteed clean.
- **`_revise_draft` is fail-loud** (parse + both-bodies presence check) but the loop does not yet map a revise failure to `escalated` — out of this plan's scope; every test supplies valid revise JSON.
- **Revise-vs-judge call purpose read off the SYSTEM prompt in tests** (both share `claude-sonnet-4-6`) — enables the exactly-2-revise / 3-judge assertions (Pitfall 5).

## Deviations from Plan

None - plan executed exactly as written. Both tasks followed RED→GREEN TDD; all acceptance greps and gates pass.

## Known Stubs
- **Plan-03 insertion point (marked comment, not a stub call):** inside the `attempt_no > 0` branch, the per-rewrite `run_deterministic_gate` re-check (D-01), the `held_fabrication` abort keeping attempt-0 (D-02), and the `unverified`/`mechanical`-ride (D-03) are a documented insertion point. This is plan-sanctioned (Plan 02 explicitly defers the safety re-check to Plan 03); the loop currently judges the rewrite directly. `run_deterministic_gate` stays imported/reserved for Plan 03.
- **`_attempt_row` `sats=0` / `model_calls=[]`** — the per-call token/sat mapping is Plan 03 (telemetry-only; no gate depends on it), carried unchanged from Plan 01.

## TDD Gate Compliance
- RED gate: `3aa642f` (`test(29-02)`) — all 7 new tests confirmed failing (`AttributeError: no _build_feedback`, `NotImplementedError` from the Plan-01 seam, `AttributeError: no _select_best_attempt`) before any implementation.
- GREEN gates: `31b76fd` (`feat`, Task 1) and `df86805` (`feat`, Task 2) — each satisfies its `<automated>` verify gate. Gate sequence `test(...) → feat(...) → feat(...)` present in git log.

## Verification Evidence
- `python3 -c "import ast; ast.parse(open('docker/newsletter/judge_loop.py').read())"` → OK (CLAUDE.md syntax gate).
- Task 1 gate: `pytest -k "revise_called_with_feedback or build_feedback" -x -q` → 2 passed.
- Task 2 gate: `pytest -k "n2_hard_stop or continuity_absent_triggers or both_bodies_fail_together or best_attempt_selection" -x -q` → 4 passed.
- Full module: `pytest tests/test_29_judge_loop.py -q` → **19 passed** (12 Plan-01 regression + 7 new).
- No-regression: `pytest tests/test_26_continuity_loader.py tests/test_27_edition_eval.py tests/test_28_deterministic_gate.py -q` → **104 passed**.
- Source disciplines (grep): `_fact_base_source_texts` reused (revise guardrail); `context="layer2_revise"` present; **0** `generate_newsletter`/`generate_from_blocks` (targeted revise, D-07); **0** brittle triple-backtick fence strips; `NotImplementedError` seam removed (0).

## Out-of-Scope / Deferred
- The full `tests/` run surfaces pre-existing failures in modules that do NOT import `judge_loop` (`test_llm_proxy` missing `uvicorn`; `test_1d_radar_section`/`test_4b` missing `anthropic`; `test_schemas`/`test_newsletter_quality` schema/quality drift). Logged to `deferred-items.md`; NOT fixed (SCOPE BOUNDARY — pre-existing, unrelated to this plan's two files).

## Next Phase Readiness
- Plan 03 wires the per-rewrite `run_deterministic_gate` re-check at the marked insertion point (D-01/D-02 `held_fabrication` keeping attempt-0, D-03 `unverified` telemetry-only) and finalizes the `sats`/`model_calls` telemetry mapping onto `write_eval_row`. `_revise_draft`, `_build_feedback`, `_select_best_attempt`, and the N=2 loop control are the stable base.
- LOOP-01..05 cores are BUILT + PROVEN here; requirement closure is deferred to phase end (after Plan 03 + `/gsd-verify-work`), consistent with the operator-validated 27/28/29-01 fail-loud-accuracy posture. Live sequencer invocation + persistence + verdict action are Phase 30 (WIRE); the `edition_eval` key-mint + migration-045 MCP apply (Phase 27 Plan 03) remain the worktree-unsafe prerequisite for the first LIVE call.

## Self-Check: PASSED
- Files exist: `docker/newsletter/judge_loop.py`, `tests/test_29_judge_loop.py` — FOUND.
- Commits exist: `3aa642f`, `31b76fd`, `df86805` — FOUND.
- Symbols: `_revise_draft`, `_build_feedback`, `_select_best_attempt` — FOUND.
- Gates: AST OK; 19/19 test_29 green; 104/104 test_26/27/28 green.

---
*Phase: 29-layer-2-judge-feedback-rewrite-loop*
*Completed: 2026-07-01*
