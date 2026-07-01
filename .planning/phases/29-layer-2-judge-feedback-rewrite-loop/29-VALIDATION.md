---
phase: 29
slug: layer-2-judge-feedback-rewrite-loop
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-01
---

# Phase 29 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `29-RESEARCH.md` § Validation Architecture (lines 484–523). **Build-only phase (D-09):**
> `run_layer2(...)` is a PURE function — no supabase client, no `edition_evals` write, no live invocation,
> no container rebuild. All network is MOCKED via an injected fake `httpx` client (reused from
> `tests/test_28_deterministic_gate.py`) and an injected fake `llm_client` (FIFO OpenAI-shape); there is
> **no live egress** and **no live proxy call** in any Phase 29 test. First live invocation is Phase 30.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 (repo standard; `tests/conftest.py` configured) |
| **Config file** | `tests/conftest.py` (sys.path + schemas-collision workaround; preloads `newsletter_poller`) |
| **Quick run command** | `cd /root/bitcoin_bot && python3 -m pytest tests/test_29_judge_loop.py -x -q` |
| **Full suite command** | `cd /root/bitcoin_bot && python3 -m pytest tests/` |
| **Estimated runtime** | ~10 seconds (pure function + mocked network + mocked LLM — no I/O) |

**Import pattern for the new test** (mirror `tests/test_28_deterministic_gate.py:37-41`):
```python
import sys
from pathlib import Path
NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
if str(NL_DIR) not in sys.path:
    sys.path.insert(0, str(NL_DIR))
import judge_loop            # the REAL module — never re-implement
```
`judge_loop` imports `run_deterministic_gate` (`deterministic_gate`), `_llm_call` (`block_pipeline`), and
`parse_llm_json` (`newsletter_poller` — the Phase-26 char-0 fix; do **NOT** reuse `phase_e_voice_check`'s
brittle strip). `conftest.py` preloads `newsletter_poller`; `deterministic_gate`/`block_pipeline` import
standalone once `NL_DIR` is on the path. `anthropic` is un-installed in the test env (guarded to `None`) —
tests inject an **OpenAI-shape** fake `llm_client`, never an `anthropic.Anthropic` instance.

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_29_judge_loop.py -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/test_29_judge_loop.py tests/test_28_deterministic_gate.py -q` (guards no regression against the reused Layer-1 gate)
- **Before `/gsd-verify-work`:** Full suite (`python3 -m pytest tests/`) must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Requirement Verification Map

> Keyed by requirement (task/plan IDs finalize at planning). Every phase requirement + every testable
> locked-decision behavior maps to an automated pytest command in the single new suite
> `tests/test_29_judge_loop.py`. `File Exists` is ❌ Wave 0 — the whole suite is authored in this phase.

| Requirement | Behavior | Threat Ref | Test Type | Automated Command | File Exists | Status |
|-------------|----------|------------|-----------|-------------------|-------------|--------|
| JUDGE-01 | Entry guard: non-empty `fabrication` in `det_flags` → module never calls the judge (short-circuit, ValueError/guard); clean → judge runs, no revise when all-pass | — | unit | `pytest tests/test_29_judge_loop.py -k guard_and_shortcircuit -x` | ❌ W0 | ⬜ pending |
| JUDGE-02 | Judge scores BOTH bodies × 5 dims 1–5 with quoted evidence + before/after exemplars (mocked judge JSON); one call per `pipeline_version` | T-29-NOEVID | unit | `pytest tests/test_29_judge_loop.py -k judge_scores_both_bodies -x` | ❌ W0 | ⬜ pending |
| JUDGE-03 | Continuity=1 when lead bridge absent → triggers loop; judge is handed the last-3-editions angles | — | unit | `pytest tests/test_29_judge_loop.py -k continuity_absent_triggers -x` | ❌ W0 | ⬜ pending |
| JUDGE-04 | Hedging fails on `score<3` **OR** `≥3` deterministic filler hits; clickbait/specificity `<3` fail (3=warn surfaced) | — | unit | `pytest tests/test_29_judge_loop.py -k filler_hit_combination -x` | ❌ W0 | ⬜ pending |
| JUDGE-05 | Schema-reject → ONE retry → recover (ok) AND stay-invalid → `eval_status='error'` → `escalated` (never a fabricated 0) | T-29-NOEVID / T-29-ZERO | unit | `pytest tests/test_29_judge_loop.py -k schema_reject_retry_then_error -x` | ❌ W0 | ⬜ pending |
| LOOP-01 | Any failing dim → exactly ONE targeted revise call carrying structured per-dim feedback (which dims + reason + fix exemplar) | — | unit | `pytest tests/test_29_judge_loop.py -k revise_called_with_feedback -x` | ❌ W0 | ⬜ pending |
| LOOP-02 | Fails every attempt → exactly 2 revises, hard stop at N=2, no 3rd revise, no best-effort publish | T-29-DOS | unit | `pytest tests/test_29_judge_loop.py -k n2_hard_stop -x` | ❌ W0 | ⬜ pending |
| LOOP-03 | Every attempt's `judge_scores`+`feedback` present in telemetry; attempt-2-not-beating-1 surfaced via `selected_attempt` | — | unit | `pytest tests/test_29_judge_loop.py -k telemetry_all_attempts -x` | ❌ W0 | ⬜ pending |
| LOOP-04 | Mechanical-only + no failing dim → `passed`, no revise; mechanical rides into feedback ONLY when a judge dim independently fails; fabrication flags never enter the loop | — | unit | `pytest tests/test_29_judge_loop.py -k "mechanical_only_passed or mechanical_rides_feedback" -x` | ❌ W0 | ⬜ pending |
| LOOP-05 | Pure return contract `{final_draft, verdict, selected_attempt, attempts:[...]}`; each attempt maps 1:1 onto `write_eval_row` params; no retry state outside the module | — | unit | `pytest tests/test_29_judge_loop.py -k return_contract_maps_to_write_eval_row -x` | ❌ W0 | ⬜ pending |
| D-02 | Rewrite introduces a NEW fabrication (fake httpx 404) → abort → verdict `held_fabrication`, `final_draft == attempt-0` clean draft (never the fabricated rewrite) | T-29-FABRW | unit | `pytest tests/test_29_judge_loop.py -k held_fabrication_keeps_attempt0 -x` | ❌ W0 | ⬜ pending |
| D-03 | Reverify `unverified` (fake httpx 5xx/timeout) → never aborts/holds; recorded in `reverify_flags` telemetry only | T-29-FABRW | unit | `pytest tests/test_29_judge_loop.py -k unverified_never_holds -x` | ❌ W0 | ⬜ pending |
| D-05 | `prior_context.empty` (no prior published edition) → continuity scored n/a + EXCLUDED from verdict; a no-bridge draft passes | — | unit | `pytest tests/test_29_judge_loop.py -k continuity_na_excluded -x` | ❌ W0 | ⬜ pending |
| D-08 | Impact body fails a dim, technical passes → dim counts as failing; the revise rewrites BOTH bodies together as a unit | — | unit | `pytest tests/test_29_judge_loop.py -k both_bodies_fail_together -x` | ❌ W0 | ⬜ pending |
| D-11 | `held_voice` after N=2 returns the FEWEST-failing-dims attempt (tie → highest summed score → latest); verdict records selected attempt + still-failing dims | — | unit | `pytest tests/test_29_judge_loop.py -k best_attempt_selection -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Threat refs map to each plan's `<threat_model>` STRIDE register: T-29-FABRW (rewrite hallucinates a new entity/stat), T-29-SSRF (draft prompt-injection → outbound fetch, mitigated by the inherited gate SSRF guard — module adds no egress), T-29-NOEVID (judge bare-score with no evidence), T-29-DOS (runaway rewrite loop burns budget), T-29-ZERO (silent zero masking a failed eval). T-29-SC (zero new packages) accepted.*

---

## Wave 0 Requirements

- [ ] `tests/test_29_judge_loop.py` — the entire suite (JUDGE-01..05, LOOP-01..05 + D-02/03/05/08/11). Imports the REAL `judge_loop` via `sys.path.insert(NL_DIR)`; **reuses** the `_FakeHTTPClient` from `tests/test_28_deterministic_gate.py:135` (queue of `(status_code, json)` per URL + call-counter, raises `httpx.TimeoutException`/`ConnectError` on demand) for the reused Layer-1 re-check.
- [ ] `_FakeLLM` — a new FIFO fake `llm_client` (OpenAI-shape `.chat.completions.create(...)` returning canned judge/revise JSON in order) so the pure module never hits the proxy. Asserts revise-call count for N=2 (LOOP-02) and feedback contents (LOOP-01).
- [ ] Golden fixtures — small technical+impact markdown body pairs paired with a minimal `fact_base` dict; canned judge JSON per attempt to drive: fabrication short-circuit, schema-reject→retry→error, continuity absent/n-a, N=2 hard stop, held_fabrication (fake 404 on a rewrite ref), held_voice best-attempt tie-breaks, mechanical-only-stays-passed, both-bodies-revised.
- [ ] No new conftest fixture needed — conftest already preloads `newsletter_poller`; `deterministic_gate`/`block_pipeline` import standalone. No framework install (pytest 9.0.3 present).

*Golden-fixture design:* reuse the Phase-28 fake-httpx double for the reused gate; add the FIFO `_FakeLLM`. Canned judge responses are hand-authored JSON matching the judge schema (score + quoted evidence + before/after exemplar per dim, per body) so schema-validation (JUDGE-05) and threshold logic (D-04) are exercised deterministically.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| — | — | — | — |

*All phase behaviors have automated verification.* The live proxy call (judge/revise under the `edition_eval` identity), the `edition_evals` write, and threshold calibration against real drafts are intentionally **not** Phase-29 targets — they are Phase 30 (WIRE) with the operator report-only window. The `continuity_fail_below=4` default (operator-confirmed at this plan gate, 2026-07-01) is config-tunable and calibrated in Phase 30's report-only window.

---

## Validation Sign-Off

- [x] All requirements have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (single fast suite covers all)
- [x] Wave 0 covers all MISSING references (the new test file + `_FakeLLM` FIFO client; `_FakeHTTPClient` reused from test_28)
- [x] No watch-mode flags (`-x -q` only)
- [x] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-01
