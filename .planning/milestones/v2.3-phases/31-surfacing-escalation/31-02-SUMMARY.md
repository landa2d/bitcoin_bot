---
phase: 31-surfacing-escalation
plan: 02
subsystem: newsletter-eval-surfacing
tags: [telegram, notify, edition_evals, eval, report-only, processor, pytest, fail-loud]

# Dependency graph
requires:
  - phase: 31-surfacing-escalation
    plan: 01
    provides: "send_telegram is a bool-returning fail-loud function (True/False, never raises) — the contract this notify's critical-caller check depends on"
  - phase: 30-sequencer-wiring-hold-action-activation-gate
    provides: "eval armed report-only (enabled=true/enforce=false); edition_evals rows persisted per draft per layer per attempt"
  - phase: 27-eval-persistence-governed-agent
    provides: "edition_evals table (045) + read_evals_by_newsletter/read_eval_trend .eq()-only semantics mirrored here"
provides:
  - "_read_edition_evals(supabase, edition_number): edition-keyed .eq()-only reader returning all rows across both pipeline_versions/layers/attempts (no LLM in the Processor)"
  - "_format_notify_eval_section(eval_rows, enforce): pure compact formatter — D-05 single_pass-first, D-06 mechanical-always, D-07 no-eval line, D-08 report-only tag; labels/counts/scores only"
  - "scheduled_notify_newsletter appends the per-draft eval section, is fail-open-but-loud, and checks send_telegram's bool return (D-03 critical caller)"
  - "tests/test_31_notify_eval.py: 20 tests (reader .eq()-only structural proof, formatter D-05/06/07/08 + no-leak, notify seam D-03/fail-open/no-LLM)"
affects: [SURF-03 /newsletter_eval command (mirrors the .eq()-only read locally), 31-04 deploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Processor-local .eq()-only edition_evals reader mirroring edition_eval.py read semantics (services are self-contained; no cross-container import)"
    - "Pure notify formatter (supabase/LLM-free) that groups eval rows by pipeline_version and renders labels/counts/scores only — never judge evidence/exemplar prose (T-31-04 leak boundary)"
    - "Fail-open-but-loud eval section: an eval-render error ERRORs [EVAL-NOTIFY] but never suppresses the Friday notify"

key-files:
  created:
    - tests/test_31_notify_eval.py
  modified:
    - docker/processor/agentpulse_processor.py

key-decisions:
  - "D-05: single_pass (publishable primary) leads, block_v1 telemetry follows — fixed _NOTIFY_PIPELINE_ORDER"
  - "D-06: mechanical count ALWAYS printed even on a passed verdict (honors P29 D-12); det-row supplies fabrication/unverified/mechanical counts, final judge row supplies per-dim min(technical,impact) scores + attempts-used = max attempt + 1"
  - "D-07: a pipeline_version with no rows renders `⚠ no eval recorded for this draft` — the block is never omitted (NULL != intent)"
  - "D-08: effective verdict prefers the final judge verdict, falls back to the deterministic verdict when the judge never ran (so a Layer-1 held_fabrication also triggers the report-only tag); `⚠ WOULD HAVE HELD (report-only)` at the TOP of the block while enforce=False, plain held verdict when enforce=True"
  - "D-03: the Friday notify checks send_telegram's bool return and CRITICAL-logs [EVAL-ALERT] CRITICAL — Friday notify on delivery failure"
  - "enforce read via the existing get_full_config() accessor (plain, monkeypatchable), default False if absent"

patterns-established:
  - "Effective-verdict resolution: judge-row-wins with a deterministic-row fallback so held_fabrication (Layer-1, no judge row) is still recognized by the D-08 report-only tag"
  - "Leak-boundary formatter: reads only .get('score') from judge_scores + len() of deterministic_flags lists — never evidence/exemplar/feedback keys (proven by a sentinel-absence test)"

requirements-completed: [SURF-02]

# Metrics
duration: 22min
completed: 2026-07-02
---

# Phase 31 Plan 02: Friday-Notify Eval Summary (SURF-02) Summary

**Extended the processor's static Friday 12:00 UTC newsletter notify into the operator's weekly calibration instrument: a compact per-draft eval section (both pipeline_versions) read from `edition_evals` via a plain `.eq()`-only select — verdict + per-dimension judge scores + fabrication/unverified/mechanical counts (mechanical always shown, even on `passed`), an explicit `⚠ no eval recorded` line for a missing draft, and a prominent `⚠ WOULD HAVE HELD (report-only)` tag while `enforce=false` — with no LLM in the Processor and a `send_telegram` bool-return critical-caller check.**

## Performance

- **Duration:** ~22 min
- **Completed:** 2026-07-02
- **Tasks:** 2
- **Files modified:** 1 modified (processor), 1 created (test)

## Accomplishments

- `_read_edition_evals(supabase, edition_number) -> list`: an edition-keyed `.eq()`-only select (`.eq("edition_number", ...).order("pipeline_version").order("attempt")`) returning ALL rows across BOTH `pipeline_version`s and both layers/attempts in ONE read; `result.data or []`. Mirrors `edition_eval.read_evals_by_newsletter` semantics locally (services can't import across containers). NO `.in_()`, NO LLM.
- `_format_notify_eval_section(eval_rows, enforce) -> str`: a PURE formatter (no supabase, no LLM). Groups rows by `pipeline_version`, renders single_pass then block_v1 (D-05). Per block: the deterministic-layer row supplies `fabrication/unverified/mechanical` counts (mechanical ALWAYS printed, even on `passed` — D-06); the highest-`attempt` judge-layer row supplies the verdict, per-dimension `min(technical, impact)` scores across the five voice dims, and `attempts used = max attempt + 1`. A pipeline_version with no rows renders `⚠ no eval recorded for this draft` (D-07); a `held_*` verdict with `enforce=False` prepends `⚠ WOULD HAVE HELD (report-only)` at the top of the block (D-08). Renders labels/counts/scores ONLY — never judge evidence/exemplar/feedback prose (T-31-04).
- `scheduled_notify_newsletter` extended: `if not supabase: return` guard; locate the current draft's `edition_number` via the pre-existing `newsletters` `.in_('status')` lookup (acceptable — only the new eval read is `.eq()`-only); read `edition_eval.enforce` from `get_full_config()` (default False); append the eval section after the static notify text. The eval-section build is wrapped fail-open-but-loud (an eval-render error ERRORs `[EVAL-NOTIFY]` and still sends the static notify). Checks `send_telegram`'s bool return and `logger.critical("[EVAL-ALERT] CRITICAL — Friday notify delivery FAILED for edition #%s", ...)` on `False` (D-03, edition number only per T-30-LOG). No LLM/retry state added (WIRE-05).
- `tests/test_31_notify_eval.py`: 20 tests — reader `.eq()`-only (a table-aware StubSupabase whose `edition_evals` chain OMITS `.in_()`, so an accidental in-list filter raises AttributeError structurally); formatter D-05/D-06/D-07/D-08 + worst-of-both-bodies scoring + `n/a` continuity + a sentinel-absence no-leak test; the notify seam (message content, both delivery outcomes with the D-03 CRITICAL log, fail-open on an eval-read exception, the no-supabase guard, and a `routed_llm_call`-must-not-fire WIRE-05 guard).

## Task Commits

Each task was committed atomically:

1. **Task 1: .eq()-only edition_evals reader + pure notify formatter (+13 tests)** - `a47c7fd` (feat)
2. **Task 2: wire eval section into scheduled_notify_newsletter + critical-caller check (+7 seam tests)** - `6bdd820` (feat)

## Files Created/Modified

- `docker/processor/agentpulse_processor.py` - new module-level `_read_edition_evals` (`.eq()`-only), `_notify_worst_dim_score` (leak-safe per-dim min), `_format_notify_eval_section` (pure), and the extended `scheduled_notify_newsletter` (eval section + fail-open + D-03 critical-caller check). Constants `_NOTIFY_PIPELINE_ORDER` (D-05 order) and `_NOTIFY_JUDGE_DIMENSIONS` (the five judge dims).
- `tests/test_31_notify_eval.py` - the SURF-02 unit + seam suite using the test_31_send_telegram harness bootstrap (real processor module, table-aware in-memory Supabase stub, `caplog` label assertions). ZERO live egress, ZERO live DB.

## Decisions Made

- **Effective verdict = judge-first with a deterministic fallback.** The plan specifies the final verdict comes from the highest-attempt judge row, but a Layer-1 `held_fabrication` holds BEFORE the judge runs (no judge row exists). To make D-08 recognize `held_fabrication` too, the formatter falls back to the deterministic-layer verdict when no judge row is present. A deterministic-only held draft correctly shows `⚠ WOULD HAVE HELD (report-only)` + `scores: (judge did not run)`.
- **`enforce` read via `get_full_config()`** (the existing cached config accessor the processor already uses) rather than a bespoke fresh-read path — it is the accessor the plan points to, is monkeypatchable for the seam test, and keeps the change minimal. A mid-week `enforce` flip is reflected on the next processor restart (the flip is 30-04 Task 6, an operator action typically paired with a deploy).
- **The `newsletters` `.in_('status')` lookup is kept as-is** (pre-existing/acceptable per the plan); ONLY the new `edition_evals` read is `.eq()`-only. The reader's docstring references the in-list filter as an anti-pattern in prose (not as a call) so the "no `.in_(` in the reader body" acceptance grep stays clean.

## Deviations from Plan

None - plan executed exactly as written. (The judge-first-with-deterministic-fallback verdict resolution is an implementation detail the plan's D-08 requires — it names both `held_fabrication` and `held_voice`, and `held_fabrication` originates on the deterministic layer — not a scope deviation.)

## Threat Surface

No new security-relevant surface beyond the plan's `<threat_model>`. The two mitigations owned by this plan are satisfied: T-31-04 (info disclosure) — the formatter renders labels/counts/scores only, proven by a sentinel-absence no-leak test; T-31-05/06 (silent-failure / hidden-missing-eval) — the reader is `.eq()`-only (structurally proven), a missing eval renders `⚠ no eval recorded`, and an eval-render error is fail-open-but-loud.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The `.eq()`-only edition_evals read pattern and the row-shape handling (deterministic_flags counts, both-bodies judge_scores) are established for SURF-03's `/newsletter_eval` gato_brain handler to mirror locally.
- Deploy of this change is DEFERRED to plan 31-04 (worktree-unsafe scoped `processor` rebuild, orchestrator-owned on the main tree). The D-13 acceptance there is a manual notify-path invocation. No `docker compose` build was run in this worktree.

## Self-Check: PASSED

- FOUND: `docker/processor/agentpulse_processor.py`
- FOUND: `tests/test_31_notify_eval.py`
- FOUND commit `a47c7fd` (Task 1), `6bdd820` (Task 2)
- Acceptance greps verified: `def _read_edition_evals` ×1, `def _format_notify_eval_section` ×1; the `_read_edition_evals` body contains NO `.in_(`; `scheduled_notify_newsletter` calls both helpers ×1 each; `[EVAL-ALERT] CRITICAL — Friday notify` present; NO `routed_llm_call`/proxy ref in the notify region; no stub patterns in added lines.
- Suite: 20/20 `test_31_notify_eval` pass; 10/10 `test_31_send_telegram` still pass; regression `test_27_edition_eval` + `test_30_orchestration` green (54 passed total); `ast.parse` syntax check OK.

---
*Phase: 31-surfacing-escalation*
*Completed: 2026-07-02*
