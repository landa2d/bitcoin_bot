---
phase: 29-layer-2-judge-feedback-rewrite-loop
verified: 2026-07-01T12:30:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 29: Layer-2 Judge + Feedback-Rewrite Loop Verification Report

**Phase Goal:** A standalone Layer-2 eval module — a Sonnet judge that scores each draft version 1–5 across exemplar-anchored dimensions (cross-edition continuity bridge, hedging filler, clickbait/fear-hook vs professor voice, repeated sub-topics, specificity) plus a bounded N=2 feedback-rewrite loop — runs only when Layer 1 is fabrication-clean, returns the final draft + a verdict object, and never exposes loop internals or retry state to the Processor.
**Verified:** 2026-07-01T12:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Layer 2 runs only when Layer 1 found no fabrication (fabrication short-circuits before any LLM call) | VERIFIED | `judge_loop.py:681-685`: `if det_flags.get("fabrication"): raise ValueError(...)` before any `_llm_call` invocation. Test `test_guard_and_shortcircuit` asserts ValueError on a non-empty fabrication list AND verifies clean path returns `passed` with exactly one judge call (no revise, no pre-call egress). |
| 2 | A Sonnet judge scores each version 1–5 per dimension, each anchored by a concrete before/after exemplar; cross-edition continuity scores 1 if the lead lacks an explicit accurate bridge; remaining dimensions are exemplar-anchored | VERIFIED | `JUDGE_SYSTEM` + `JUDGE_PROMPT` at lines 191-220 require `score`, `evidence`, `exemplar_before`, `exemplar_after` for every dimension in both bodies. `_validate_judge_response` (line 264) enforces this schema and raises `ValueError` on any missing or empty field. The prompt explicitly states "the lead MUST bridge to a prior edition's theme; a missing/absent bridge scores 1." Test `test_judge_scores_both_bodies` asserts both `technical` and `impact` bodies present for all 5 dims with numeric score + non-empty evidence/exemplars in exactly ONE LLM call (D-08). |
| 3 | A judge response missing required quoted evidence / before-after exemplars is rejected (schema-validated, one retry, then eval_status='error'); a verdict is computed from per-dimension, config-tunable pass thresholds | VERIFIED | `_judge_draft` (line 306) loops `for attempt_i in (1, 2)` — one call + one retry — then returns `{"status":"error", ...}` on persistent failure. `run_layer2` maps that to `verdict="escalated"`, `judge_scores=None` (never a fabricated 0). `_compute_failing_dims` reads per-dim thresholds from `cfg["thresholds"]`. Tests `test_schema_reject_retry_then_error` (2-call recovery + 2-fail escalation), `test_filler_hit_combination` (config-tunable hedging combination) pass. |
| 4 | On any dimension failing threshold the writer is re-called with structured specific feedback (which dimensions failed + judge's reason + exemplar of the fix); mechanical-only Layer-1 flags may enter the loop, fabrication flags never do | VERIFIED | `_build_feedback` (line 410) emits per-dim evidence + before/after exemplar for every failing dim. Line 811: `feedback = _build_feedback(scores, failing, det_flags.get("mechanical") or None, ...)` — mechanical rides only when `failing` is non-empty (D-12); the fabrication list is never passed. `_compute_failing_dims` never reads mechanical flags. Tests `test_mechanical_only_passed` (mechanical-only → passed, zero revises), `test_mechanical_rides_feedback` (mechanical note in revise user message when dim fails), `test_revise_called_with_feedback` (structured feedback in revise prompt) all pass. |
| 5 | The rewrite is re-evaluated; the loop terminates hard at N=2 attempts max (no best-effort publish); every attempt's per-dimension scores + feedback map to edition_evals row writes; the module returns final draft + verdict with no retry state living outside it | VERIFIED | `range(0, cfg["max_attempts"] + 1)` at line 715 with `max_attempts=2` yields attempts 0,1,2 (at most 2 revises). After loop exhaustion: `verdict="held_voice"` with `_select_best_attempt` (D-11), never `passed`. `_persistable_attempt` (line 546) maps 1:1 to `write_eval_row` params, stripping internal `failing`/`summed_score`/`draft` keys. Return shape is exactly `{final_draft, verdict, selected_attempt, attempts}` (LOOP-05). Module contains zero `write_eval_row`/`import supabase`/`create_client` references (purity grep returns 0). Tests `test_n2_hard_stop` (exactly 2 revises, 3 judged, `held_voice`), `test_return_contract_maps_to_write_eval_row` (REAL `write_eval_row` called per attempt via `_StubSupabase`, verdict-iff-ok proven), `test_telemetry_all_attempts` (all 3 attempts with scores + feedback in telemetry, `selected_attempt=1` not 2) all pass. |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docker/newsletter/judge_loop.py` | Module with `run_layer2` signature + all helper functions | VERIFIED | 826 lines. Contains: `run_layer2`, `_judge_draft`, `_validate_judge_response`, `_build_feedback`, `_revise_draft`, `_CachingHTTPClient`, `_select_best_attempt`, `_compute_failing_dims`, `_count_filler_hits`, `_persistable_attempt`. AST parse passes. |
| `tests/test_29_judge_loop.py` | Test harness importing the REAL module; `_FakeLLM` FIFO client; 15+ VALIDATION selectors | VERIFIED | 31 tests (28 planned + 3 additional WR-01/WR-02 fix proofs). All 31 pass. Imports `import judge_loop as jl` (the REAL module). `_FakeLLM` FIFO client at line 130. |
| `config/agentpulse-config.json` | Top-level `edition_eval` block with `continuity_fail_below=4` | VERIFIED | `edition_eval` block present at line 135. `continuity_fail_below: 4`, `max_attempts: 2`, `judge_model: "claude-sonnet-4-6"`. Valid JSON (parse check passes). |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `judge_loop.py` | `newsletter_poller.py` | `from newsletter_poller import parse_llm_json` | VERIFIED | Line 32. `parse_llm_json` called at lines 323 (`context="layer2_judge"`) and 497 (`context="layer2_revise"`). No brittle triple-backtick strip patterns found. |
| `judge_loop.py` | `block_pipeline.py` | `from block_pipeline import _llm_call` | VERIFIED | Line 33. `_llm_call` used in `_judge_draft` (line 319) and `_revise_draft` (line 493). |
| `judge_loop.py` | `deterministic_gate.py` | `from deterministic_gate import run_deterministic_gate, _fact_base_source_texts` | VERIFIED | Line 34. `run_deterministic_gate` called at line 734 (per-rewrite re-check, `prior_edition=None`). `_fact_base_source_texts` called at line 482 (revise guardrail). |
| `run_layer2` verdict | `config edition_eval.thresholds` | `cfg["thresholds"][_FAIL_BELOW_KEY[dim]]` (D-04) | VERIFIED | `_compute_failing_dims` reads `cfg["thresholds"]["continuity_fail_below"]` etc. `_merged_config` deep-merges caller config over `DEFAULT_CONFIG`. `continuity_fail_below=4` in both config and `DEFAULT_CONFIG`. |
| `run_layer2 attempts[]` | `edition_eval.write_eval_row` | `_persistable_attempt` 1:1 mapping (Phase 30 persists; module does not call it) | VERIFIED | `_persistable_attempt` at line 546 strips internal keys and maps to 8 persistable fields. `write_eval_row` is never referenced in `judge_loop.py` (purity grep: 0 hits). The REAL `write_eval_row` is called in `test_return_contract_maps_to_write_eval_row` against `_StubSupabase` to prove the mapping. |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Syntax check — module parses | `python3 -c "import ast; ast.parse(open('docker/newsletter/judge_loop.py').read())"` | exit 0 | PASS |
| Full test suite | `python3 -m pytest tests/test_29_judge_loop.py -q` | 31 passed in 0.05s | PASS |
| Regression — phases 26/27/28 | `python3 -m pytest tests/test_26_continuity_loader.py tests/test_27_edition_eval.py tests/test_28_deterministic_gate.py -q` | 104 passed in 0.10s | PASS |
| Config JSON valid | `python3 -c "import json; json.load(open('config/agentpulse-config.json'))"` | exit 0 | PASS |
| Purity grep: no supabase/write_eval_row/create_client | `grep -c "write_eval_row\|import supabase\|create_client" docker/newsletter/judge_loop.py` | 0 | PASS |
| No brittle fence strip | `grep -c "startswith\('\`\`\`'\)\|split\('\`\`\`'\)" docker/newsletter/judge_loop.py` | 0 | PASS |
| No wrong-wallet identity | `grep -c "claude_client\|OPENAI_API_KEY" docker/newsletter/judge_loop.py` | 0 | PASS |
| No full writer re-run | `grep -c "generate_newsletter\|generate_from_blocks" docker/newsletter/judge_loop.py` | 0 | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| JUDGE-01 | 29-01 | Layer 2 runs only when Layer 1 found no fabrication | SATISFIED | Entry guard at `judge_loop.py:681-685`. `test_guard_and_shortcircuit` passes. |
| JUDGE-02 | 29-01 | Sonnet judge scores BOTH bodies 1–5 per dimension with evidence + exemplars in ONE call | SATISFIED | `_judge_draft` + `JUDGE_PROMPT` + `_validate_judge_response`. `test_judge_scores_both_bodies` (ONE call, both bodies, all 5 dims, evidence+exemplars verified) passes. |
| JUDGE-03 | 29-01 | Cross-edition continuity: score 1 when bridge absent; judge given last-3-editions angles; n/a when no prior editions | SATISFIED | `_render_prior_editions` injects prior_editions into the judge prompt. `JUDGE_PROMPT` requires bridge or score 1. `_validate_judge_response` accepts `"n/a"` only when `not continuity_applicable`. Tests `test_continuity_na_excluded` and `test_continuity_absent_triggers` pass. |
| JUDGE-04 | 29-01 | Remaining dimensions exemplar-anchored; hedging also fails on filler hit count; config-tunable | SATISFIED | `_compute_failing_dims` reads config thresholds. Hedging combination: `dim_fails = dim_fails or (max_hits >= thresholds["hedging_filler_hits_max"])`. Tests `test_filler_hit_combination`, `test_compute_failing_dims_below_threshold`, `test_compute_failing_both_bodies_min` pass. |
| JUDGE-05 | 29-01 | Schema-reject → one retry → `eval_status='error'`; verdict from config-tunable thresholds | SATISFIED | `_judge_draft` tries exactly twice; returns `{"status":"error"}` on persistent failure; `run_layer2` maps to `verdict="escalated"`, `judge_scores=None`. `test_schema_reject_retry_then_error` and `test_validate_judge_response_rejects_missing_evidence` pass. |
| LOOP-01 | 29-02 | Failing dim → targeted revise with structured per-dim feedback (dim + reason + fix exemplar); mechanical may ride | SATISFIED | `_build_feedback` + `_revise_draft`. Feedback names the dim, quotes evidence, renders before/after exemplar. `_fact_base_source_texts` guardrail in `_revise_draft`. Both bodies rewritten as unit (D-08). Tests `test_revise_called_with_feedback`, `test_build_feedback_continuity_bridge_and_no_fabrication` pass. |
| LOOP-02 | 29-02 | Rewrite re-evaluated; loop terminates hard at N=2; no best-effort publish | SATISFIED | `range(0, cfg["max_attempts"] + 1)` with `max_attempts=2`. N=2 exhaustion → `held_voice`. `test_n2_hard_stop` asserts exactly 2 revise calls, 3 judged attempts, `verdict="held_voice"`. |
| LOOP-03 | 29-03 | Every attempt's scores + feedback in telemetry; attempt-2-not-beating-1 surfaced via `selected_attempt` | SATISFIED | `_persistable_attempt` fields include `judge_scores`, `feedback`, `reverify_flags`. `attempts[-1]["feedback"] = feedback` at line 815 records the feedback that produced the NEXT attempt. `test_telemetry_all_attempts` asserts all 3 attempts have scores+feedback and `selected_attempt=1` (not 2). |
| LOOP-04 | 29-03 | Mechanical-only → `passed`, no rewrite; mechanical rides feedback only when dim fails; fabrication never enters loop | SATISFIED | `_compute_failing_dims` never reads mechanical flags. `_build_feedback` receives `det_flags.get("mechanical")` only when `failing` is non-empty (line 811). Tests `test_mechanical_only_passed` and `test_mechanical_rides_feedback` pass. |
| LOOP-05 | 29-03 | Standalone module; returns `{final_draft, verdict, selected_attempt, attempts}`; no retry state outside | SATISFIED | `run_layer2` returns exactly the 4-key dict. `_persistable_attempt` strips internal keys. No supabase, no `write_eval_row` in module. `test_return_contract_maps_to_write_eval_row` calls the REAL `write_eval_row` per projected attempt and asserts verdict-iff-ok. |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `judge_loop.py` | 27 | `import json` unused (all JSON parsing via `parse_llm_json`) | Info | None — does not affect behavior; `re` at line 28 has `# noqa: F401` |

**REVIEW finding status** (from `29-REVIEW.md`):

- WR-01 (filler-triggered feedback quotes clean sentence): FIXED in code — `_unique_filler_matches` helper (line 396-407) and `_build_feedback` (lines 443-451) emit the exact banned phrases when hedging fails on hit count with passing score. Tests `test_wr01_build_feedback_filler_only_names_phrases` and `test_wr01_filler_only_failure_names_phrases_end_to_end` prove the fix.
- WR-02 (silent fabrication skip when no http_client): FIXED in code — `logger.warning` at lines 764-768 fires whenever a revise occurs without an injected `http_client`. Test `test_wr02_warns_when_revising_without_http_client` proves the warning fires. The deliberate deviation (re-check gated on injected client) is documented in 03-SUMMARY with the rationale: `run_deterministic_gate` flags all-caps placeholder revise bodies in tests as tier1 fabrications, which would regress the zero-egress suite. Phase 30 always injects a real `httpx.Client`, so the re-check is always active in production.
- IN-01 through IN-05: informational only; no behavioral impact or safety risk.

No TBD/FIXME/XXX debt markers found in any of the 3 phase files.

---

### Human Verification Required

None. The VALIDATION.md `Manual-Only Verifications` table is empty. All phase behaviors have automated verification. Live proxy calls, `edition_evals` writes, threshold calibration against real drafts, and sequencer wiring are Phase 30 by design and out of scope for this build-only phase.

---

### Gaps Summary

No gaps. All 5 success criteria and all 10 requirements (JUDGE-01..05, LOOP-01..05) are implemented in `docker/newsletter/judge_loop.py` and proven by the 31-test suite on the REAL module. The 3 additional tests beyond the SUMMARY's count of 28 are quality improvements: they prove the WR-01 and WR-02 review fixes shipped in the code.

Scope-correct items that are NOT gaps:
- Live `edition_evals` DB writes: Phase 30 (D-09/D-10 — module is pure by design)
- Container rebuild: Phase 30 (BUILD-ONLY phase)
- Sequencer wiring at the two generation save points: Phase 30 (WIRE-01..06)
- Surfacing / Gato commands: Phase 31 (SURF-01..03)
- REQUIREMENTS.md checkboxes for JUDGE-*/LOOP-* remain `[ ]`: these are closed HERE (the codebase evidence satisfies every must-have); the markdown was intentionally not updated per the 27/28/29 fail-loud-accuracy posture that defers requirement closure to verifier confirmation.

---

_Verified: 2026-07-01T12:30:00Z_
_Verifier: Claude (gsd-verifier)_
