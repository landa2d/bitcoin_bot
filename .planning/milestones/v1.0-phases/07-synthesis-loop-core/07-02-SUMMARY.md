---
phase: 07-synthesis-loop-core
plan: 02
subsystem: processor / economy_map synthesis loop
tags: [synthesis, economy_map, scheduler, llm-proxy, anthropic, fail-loud, draft-only, gate-01]

# Dependency graph
requires:
  - phase: 07-01
    provides: "load_synth_identity, fetch_economy_map_blocks/block_has_open_draft/fetch_block_new_entries/fetch_current_block_body, economy_map_insert_block_body_version, is_block_eligible, assemble_synthesis_input, parse_synthesis_output, synthesis_sonnet_call, synthesis config block, synth_identity.md"
provides:
  - "synthesize_block — per-block eligibility -> assemble -> ONE Sonnet call -> parse -> ONE draft INSERT (draft-only, GATE-01)"
  - "synthesize_blocks_poller — fail-loud orchestrator iterating the seven blocks with per-block error isolation + run logging"
  - "scheduled_synthesize_blocks — thin wrapper registered on the processor schedule (daily 07:00 UTC, SYNT-02)"
  - "End-to-end poller tests proving GATE-01 draft-only, the D-03 no-draft guard, fail-loud identity/key aborts, and per-block isolation"
affects:
  - "Phase 8 (sentinels) and Phase 9 (/map-approve) — consume the status='draft' block_body_versions rows this loop emits"

# Tech tracking
tech-stack:
  added: []   # no new packages — httpx/schedule/supabase/stdlib already present
  patterns:
    - "Orchestrator poller mirroring classify_intake_poller: supabase guard + config.enabled flag + fail-loud governance gates + per-item try/except + log_pipeline_start/end"
    - "synthesized_from_through = run wall-clock (datetime.now(timezone.utc).isoformat()), NOT the newest entry date (Pitfall 5)"
    - "Schedule slot chosen to avoid the Friday newsletter (08:00/08:30/11:00/12:00) and Monday publish (11:00/11:15/11:30) slots"

key-files:
  created: []
  modified:
    - docker/processor/agentpulse_processor.py
    - tests/test_07_synthesis.py

key-decisions:
  - "Synthesis cadence: daily at 07:00 UTC (SYNT-02 executor discretion). Once-a-day is sufficient because the no-draft + N/T eligibility guards make most days a cheap no-op; 07:00 sits after the 06:00 daily jobs and clear of every newsletter slot, and is not the 30-min intake minute."
  - "Identity gate runs BEFORE log_pipeline_start (a None-identity abort is a loud no-run, not a 'failed' run row); the missing-key gate runs AFTER (it marks the run failed for visibility, since a keyless run would 401 every Sonnet call)."

patterns-established:
  - "Per-block try/except isolation: one block's read/call/parse/insert failure is logged (exc_info) + counted failed + skipped, never aborting the cycle."
  - "Draft-only autonomy boundary (GATE-01) enforced at the call site: synthesize_block writes ONLY the purpose-scoped block_body_versions draft INSERT; never blocks.maturity / current_body_version_id / a published row — asserted by an end-to-end 'zero /blocks writes' test."

requirements-completed: [SYNT-01, SYNT-02, SYNT-03, SYNT-04, SYNT-05, SYNT-06]

# Metrics
duration: ~20min
completed: 2026-06-01
---

# Phase 7 Plan 02: Synthesis Loop Orchestrator Summary

**The autonomous editorial spine turned on: a scheduled per-block synthesis cycle that drafts one `block_body_versions` row per eligible block via a single Sonnet call, fail-loud on a missing voice or key, draft-only so the published surface and `blocks.*` are never touched (GATE-01).**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-06-01T19:20:00Z (approx)
- **Completed:** 2026-06-01T19:24:00Z (approx)
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments

- Composed the Plan 07-01 primitives into `synthesize_block` (eligibility → assemble → ONE Sonnet call → parse/validate → ONE draft INSERT) and `synthesize_blocks_poller` (fail-loud orchestrator over the seven blocks with per-block isolation and run logging).
- Registered `scheduled_synthesize_blocks` on the processor schedule at a daily 07:00 UTC slot that avoids every newsletter/publish slot (SYNT-02).
- Proved the autonomy boundary (GATE-01 draft-only), the D-03 no-draft guard, the D-11/fail-loud identity and missing-key aborts, and per-block error isolation with five end-to-end poller tests — 18/18 synthesis tests green, Phase-5 intake suite still 6/6.

## Task Commits

1. **Task 1: synthesize_block + synthesize_blocks_poller orchestrator** - `559957c` (feat)
2. **Task 2: scheduled wrapper + registration; end-to-end poller tests** - `17f2dd0` (feat)

_(Task 1 carries `tdd="true"`; the plan structures the end-to-end poller tests into Task 2 — see Deviations.)_

## Files Created/Modified

- `docker/processor/agentpulse_processor.py` — added `synthesize_block`, `synthesize_blocks_poller` (after `synthesis_sonnet_call`), `scheduled_synthesize_blocks` (after `scheduled_classify_intake`), and the `schedule.every().day.at("07:00").do(scheduled_synthesize_blocks)` registration in `main()`.
- `tests/test_07_synthesis.py` — appended a poller harness (`_GetResponse`, `_install_poller_stubs`/`_restore_poller`, `_one_block`) and five end-to-end tests; wired them into `_run_all`.

## How It Works

`synthesize_blocks_poller()`:
1. Guards `if not supabase`; reads `cfg = get_full_config().get('synthesis', {})`; returns `{'disabled': True}` if `synthesis.enabled` is false (no run logged).
2. `load_synth_identity()` — `None` ⇒ logs + returns `{'error': 'synth_identity unavailable'}` (never synthesize voiceless, D-11). This gate runs before `log_pipeline_start` so a misconfig is a loud no-run, not a phantom failed row.
3. `log_pipeline_start('synthesize_blocks')`; then `_get_agent_api_key()` — falsy ⇒ logs + `log_pipeline_end(run_id, 'failed', ...)` + returns `{'error': 'missing agent api key'}` (a keyless run would 401 every Sonnet call; fail-loud governance).
4. `fetch_economy_map_blocks()`; iterate each block in its own try/except, accumulating `{eligible, synthesized, skipped, failed}`; `log_pipeline_end(run_id, 'completed', totals)`.

`synthesize_block(block, cfg, identity_text)`:
- Reads the open-draft flag (`block_has_open_draft`, D-03) and new entries (`fetch_block_new_entries` on the block's `last_synthesized_at` watermark; NULL ⇒ cold-start, D-06).
- `is_block_eligible(...)` with `N`/`T_days` from cfg; ineligible ⇒ returns a `skipped/ineligible` result with **zero** Sonnet calls.
- Eligible ⇒ `fetch_current_block_body` (None cold-start) → `assemble_synthesis_input` → ONE `synthesis_sonnet_call(identity_text, prompt, cfg)` → `parse_synthesis_output` → `economy_map_insert_block_body_version({block_slug, body_md, proposed_maturity, synthesized_from_through})` where `synthesized_from_through = datetime.now(timezone.utc).isoformat()` (run wall-clock, Pitfall 5). `status` is omitted (DB default `draft`, D-13). No write touches `blocks.*` or a published row.

## Verification

- `python3 -c "import ast; ast.parse(...)"` — processor parses. PASS
- `grep` gates: `synthesize_block` + `synthesize_blocks_poller` defined, `log_pipeline_start('synthesize_blocks')` wired, no `blocks.*`/`current_body_version_id` write inside `synthesize_block`, `scheduled_synthesize_blocks` defined + registered exactly once. PASS
- `python3 tests/test_07_synthesis.py` — **18/18 green** (13 Plan-01 unit + 5 new poller end-to-end). PASS
- `python3 tests/test_05a_intake_classifier.py` — **6/6 green** (no regression). PASS
- Pytest-collectability: all 18 synthesis test functions have zero required positional args (verified by reflection) — the `python3 -m pytest` gate will pass where pytest is present.
- GATE-01 asserted: the eligible-cold-start test confirms exactly one POST to `/anthropic/v1/messages` and exactly one POST to `/block_body_versions` (status key absent, Content-Profile economy_map, no published/blocks columns), and zero requests target `/blocks`.

## Deviations from Plan

**1. [Plan structure — not a code deviation] Task 1 is `tdd="true"` but its end-to-end test lives in Task 2.**
- **Context:** Task 1 carries `tdd="true"`, but the plan deliberately assigns the end-to-end poller tests to Task 2 (`must_haves.artifacts` lists the poller test under `tests/test_07_synthesis.py`, and Task 2's `<action>` is "Append end-to-end tests"). The MVP+TDD runtime gate was NOT active (the orchestrator did not pass `MVP_MODE`/`TDD_MODE`), so the implement-then-test ordering the plan prescribes was followed rather than a strict per-task RED/GREEN split.
- **Resolution:** Implemented `synthesize_block`/`synthesize_blocks_poller` in Task 1 (committed `559957c`), then added the five end-to-end tests in Task 2 (committed `17f2dd0`). Both task commits are `feat` (the test commit also adds the scheduled registration, the dominant change). All behavior is test-covered before the plan closes.

**2. [Rule 3 — Environment, inherited from 07-01] pytest not installed in the sandbox.**
- **Found during:** Task 2 verification (`python3 -m pytest tests/test_07_synthesis.py tests/test_05a_intake_classifier.py -q`).
- **Issue:** The sandbox has no `pytest` module and is PEP 668 externally-managed; installing it is a package-manager install excluded from auto-fix (executor Rule 3 exclusion), and the same constraint was documented in 07-01.
- **Resolution:** Did NOT force-install. Ran the primary standalone gate (`python3 tests/test_07_synthesis.py` ⇒ 18/18; `python3 tests/test_05a_intake_classifier.py` ⇒ 6/6) and verified by reflection that all 18 synthesis tests are pytest-collectable (no required positional args), so the pytest gate will pass in CI/any environment where pytest is present.
- **Files modified:** none (environmental).
- **Commit:** n/a.

## Known Stubs

None. `synthesize_block`/`synthesize_blocks_poller` are fully wired against the live economy_map tables and the proxy Sonnet route and are scheduled on the processor. The deploy (operator-approved `docker compose up -d --build processor`) is explicitly out of scope for this plan per the plan's `<verification>`.

## Threat Flags

None. No new network endpoint, auth path, file-access pattern, or trust-boundary schema change beyond the plan's `<threat_model>` was introduced — the loop writes only the already-specified draft INSERT and reads only the already-specified economy_map tables/proxy route.

## Notes for Phase 8 / Phase 9

- Each eligible block produces exactly one `block_body_versions` row with `status='draft'` (DB default), populated `body_md`, a validated `proposed_maturity` (one of the five enum values), and `synthesized_from_through` = the run wall-clock ISO timestamp.
- The published row and `blocks.maturity`/`blocks.current_body_version_id` are never mutated by this loop — promotion is the operator's gate (Phase 9 `/map-approve`).
- The D-03 no-draft guard means at most one in-flight draft per block; a Phase-9 reject should clear/re-open eligibility for the next cycle.

## Self-Check: PASSED

- Files: `docker/processor/agentpulse_processor.py`, `tests/test_07_synthesis.py`, `.planning/phases/07-synthesis-loop-core/07-02-SUMMARY.md` — all present.
- Commits: `559957c` (Task 1), `17f2dd0` (Task 2) — both in git history on the worktree branch.
