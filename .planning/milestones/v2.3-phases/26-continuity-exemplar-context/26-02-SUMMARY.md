---
phase: 26-continuity-exemplar-context
plan: 02
subsystem: testing
tags: [pytest, fixtures, supabase-stub, continuity, exemplars, fail-loud, regression]

# Dependency graph
requires:
  - phase: 26-01 (continuity + exemplar loader)
    provides: load_edition_context(supabase, limit, exemplar_paras) with an explicit `supabase` param + the three-state exemplars_status contract (the testability seam this plan exercises)
  - phase: v2.2 (Phase 19 test harness)
    provides: conftest `_preload_poller` (newsletter_poller cached in sys.modules w/ correct schemas) + the test_19_smartquote "import the REAL fn, never reimplement" pattern
provides:
  - tests/test_26_continuity_loader.py — 10 fixture-driven cases pinning load_edition_context's return shape + both degrade paths
  - an in-memory Supabase stub (.table/.select/.eq/.order/.limit/.execute) reusable for future loader tests
  - a regression net: a production regression in the loader fails the suite (no local re-implementation)
affects: [27-eval-persistence, 29-layer2-judge, 30-sequencer-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Test imports the REAL production loader via the conftest-preloaded newsletter_poller (test_19 rule) — a copy could pass while production regresses"
    - "In-memory Supabase stub exposing only the loader's fluent chain, FIFO-queued .execute() responses — degrade paths reproducible without a live DB"
    - "Assert against the AS-IMPLEMENTED contract (4-key dict incl. exemplars_status), not the plan's guessed 3-key shape"

key-files:
  created:
    - tests/test_26_continuity_loader.py
  modified: []

key-decisions:
  - "Assert the real 4-key contract (previous_editions/exemplars/exemplars_status/empty) as a subset — NOT the plan's literal 3-key `{previous_editions:[],exemplars:[],empty:True}` which the implemented empty_marker (with exemplars_status='not_scored') would have failed"
  - "Isolate D-05's non-header rule from the word-count gate with a >=40-word paragraph whose first line is a header — proving header-exclusion is not merely length"
  - "Three states proven mutually distinguishable in one test; the not_scored marker asserted as an enum string, never a numeric Phase E score:0"

patterns-established:
  - "StubSupabase(*responses) — each positional arg is one .execute().data list, FIFO-popped; one response suffices for the single-query loader, queue extends for future multi-read loaders"
  - "_edition(...) factory carrying every column the loader reads (edition_number/title/title_impact/content_markdown/content_markdown_impact/data_snapshot/published_at)"

requirements-completed: [CTX-01, CTX-02, CTX-03, CTX-05]

# Metrics
duration: ~6min
completed: 2026-06-22
---

# Phase 26 Plan 02: Continuity Loader Fixture Test Summary

**A 10-case deterministic pytest suite that imports the REAL `load_edition_context` and pins its return shape plus both fail-loud degrade paths (empty corpus / empty-operator-pool) against an in-memory Supabase stub — no live DB, so a production regression fails the suite before any live generation budget is spent.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-06-22T20:50:42Z
- **Completed:** 2026-06-22T20:58Z (approx)
- **Tasks:** 1
- **Files modified:** 1 (created)

## Accomplishments
- Created `tests/test_26_continuity_loader.py` — 10 passing cases covering the full D-16 set: return shape, D-07 `lead_theme` theme sourcing, D-09 `weeks_ago` omission on null `published_at`, D-01 `operator_written` filtering, D-05 >=40-word non-header/non-list paragraph filtering, the CTX-03 empty-corpus WARNING + explicit marker + no-raise, and the D-02/D-03 empty-operator-pool "not scored" path.
- Imports the REAL `nl.load_edition_context` via the conftest-preloaded `newsletter_poller` (mirroring `test_19_smartquote.py:32-39`), with a `NL_DIR` sys.path belt-and-suspenders fallback — zero local re-implementation, so a loader regression fails the suite.
- Built a reusable in-memory `StubSupabase` exposing only the loader's fluent chain (`.table().select().eq().order().limit().execute()`) with FIFO-queued `.data` responses — the degrade paths are reproducible with no network, no credentials, never touching the live project (threats T-26-T1/T-26-T2 mitigated).
- Proved the three loader states are mutually distinguishable: corpus-empty (`empty=True`) vs empty-operator-pool (`empty=False`, both `exemplars_status='not_scored'`) vs scored (`exemplars` populated) — and that the marker is an enum string, never a numeric Phase E `score:0`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Build the deterministic fixture test for load_edition_context** — `eb0c5dc` (test)

**Plan metadata:** committed with SUMMARY/STATE/ROADMAP (docs: complete plan)

## Files Created/Modified
- `tests/test_26_continuity_loader.py` — NEW. 10 cases + `StubSupabase`/`_StubQuery`/`_StubResult` doubles + an `_edition(...)` row factory + long-prose fixtures. Imports the real loader; contains no `def load_edition_context`.

## Decisions Made
- **Assert the AS-IMPLEMENTED 4-key contract, not the plan's guessed 3-key shape.** The plan text said the empty-corpus path "returns exactly `{'previous_editions': [], 'exemplars': [], 'empty': True}`", but 26-01's `empty_marker` is a 4-key dict that also carries `exemplars_status: 'not_scored'`. Per the executor brief ("assert against the contract as actually implemented, not a guessed one"), the test asserts the three required keys' values AND `exemplars_status == 'not_scored'` as a subset, rather than an `== {3-key}` equality that would FALSE-FAIL against real production. (CLAUDE.md-aligned: the gate verifies real code, not a guess.)
- **Isolate the D-05 non-header rule from the length gate.** Beyond the plain header/list/short/long mix, the fixture includes a >=40-word paragraph whose first line is `### Section Heading` and asserts it is still excluded — proving header-exclusion is driven by the regex, not merely by falling under 40 words.
- **Single `.execute()` response suffices** (the loader issues exactly one published-set read), but `StubSupabase` queues responses FIFO so a future multi-read loader stays testable without rework.

## Deviations from Plan

None — plan executed exactly as written. The one judgment call (asserting the real 4-key empty_marker as a subset rather than the plan's literal 3-key equality) is the executor brief's explicit instruction to assert the implemented contract, not a deviation from intended behavior — the test still proves `previous_editions:[]`, `exemplars:[]`, `empty:True` for the empty-corpus case as required.

## Issues Encountered
None. The conftest preload made `newsletter_poller` importable with the correct `schemas` on first run; all 10 cases passed on the first execution (`pytest ... -v` exit 0, 0.03s).

## User Setup Required
None — pure Python test against in-memory fixtures. No external service configuration, no package installs (reuses the existing pytest + conftest harness).

## Next Phase Readiness
- **Plan 03 (Wave 3) — ready, with a standing live-flow caveat.** The loader contract is now pinned deterministically, so Plan 03's live trigger can focus on the things fixtures cannot prove: (1) the operator-confirmed `data_snapshot.lead_theme` backfill on editions 25–28 + `published_at` non-null verification on all 7 (D-12/D-13, worktree-unsafe Supabase MCP, operator/orchestrator-owned), and (2) the D-17 verification that `exemplars` actually reach Phase E (`voice_score.score > 0`, ≥1 observation) given the upstream `narrative_context` pre-population + `setdefault` flagged in 26-01-SUMMARY → Issues. This test proves the loader RETURNS exemplars when operator editions exist; it cannot prove they FLOW through the live injection — that is Plan 03's job.
- **Downstream (Phases 27/29/30):** the locked three-state contract (`scored` / `not_scored` / `empty`) is the same signal the Layer-2 judge and the sequencer will branch on; this suite is the regression guard for it.

## Self-Check: PASSED
- Files: FOUND `tests/test_26_continuity_loader.py`
- Commits: FOUND `eb0c5dc`
- Gate: `python3 -m pytest tests/test_26_continuity_loader.py -v` exits 0, 10 passed. Acceptance: 0 local `def load_edition_context`; imports `newsletter_poller`; 12 `nl.load_edition_context` call sites; the literal `"continuity context empty"` WARNING asserted; `weeks_ago` omission + `primary_theme` sourcing cases present.

---
*Phase: 26-continuity-exemplar-context*
*Completed: 2026-06-22*
