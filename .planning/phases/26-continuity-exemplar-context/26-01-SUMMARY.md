---
phase: 26-continuity-exemplar-context
plan: 01
subsystem: newsletter
tags: [continuity, exemplars, voice-check, supabase, narrative-context, fail-loud]

# Dependency graph
requires:
  - phase: v2.2 (newsletter pipeline, block_v1 A/B path)
    provides: generate_from_blocks(exemplars=…) param, Phase E voice check, narrative_context consumers (single-pass writer, block prepass)
provides:
  - load_edition_context(supabase, limit=3, exemplar_paras=8) loader in newsletter_poller.py
  - narrative_context + avoided_themes injection via setdefault in process_task
  - exemplars= passed at BOTH generate_from_blocks call sites (primary block + live A/B)
  - Phase E "not scored" resurrection (no more silent score:0 on absent exemplars)
affects: [27-eval-persistence, 28-layer1-gate, 29-layer2-judge, 30-sequencer-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Three-state loader contract: empty corpus (empty=True) / empty operator pool (exemplars_status='not_scored') / scored — distinguishable, never a silent zero"
    - "Fail-loud-but-not-fatal: degraded corpus warns + returns explicit empty marker, never raises into generation"
    - "setdefault injection so an upstream-provided narrative_context wins (CTX-04/D-14)"

key-files:
  created: []
  modified:
    - docker/newsletter/newsletter_poller.py
    - docker/newsletter/block_pipeline.py

key-decisions:
  - "exemplars_status ('scored'|'not_scored') is the distinguishable exemplar-pool marker — top-level on the context, distinct from empty-corpus (empty=True) and from a real Phase E score:0"
  - "Phase E 'not scored' marker = {score:None, status:'not_scored'} at both empty-exemplar branches; genuine-error branch keeps score:0 (D-04)"
  - "primary_theme from data_snapshot.lead_theme only; weeks_ago omitted on null published_at; opening_excerpt strips leading section header (D-07/D-09/D-10)"

patterns-established:
  - "Loader takes supabase as an explicit param (not the module global) so degrade paths are fixture-testable without a live DB (Plan 02 depends on this signature)"
  - "Module-level _le_* helpers (_le_opening_excerpt, _le_weeks_ago, _le_is_exemplar_paragraph) reuse the verification.py header/word-count idioms"

requirements-completed: [CTX-01, CTX-02, CTX-03, CTX-04, CTX-05]

# Metrics
duration: ~8min
completed: 2026-06-22
---

# Phase 26 Plan 01: Continuity & Exemplar Context Summary

**`load_edition_context` loader feeds prior-edition continuity + operator-written voice exemplars into both writer paths and Phase E, with a three-state fail-loud contract that resurrects the dead Phase E voice check (no more silent `score:0`).**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-06-22T20:25Z (approx)
- **Completed:** 2026-06-22T20:31Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- Added `load_edition_context(supabase, limit=3, exemplar_paras=8)` — one published-set `.eq('status','published')` read building `previous_editions` (all published, oldest-first) + operator-written-only `exemplars`, with three distinguishable states (empty corpus / empty operator pool / scored).
- Wired the loader into `process_task` via `setdefault('narrative_context', …)` and fed the previously-unfed `avoided_themes` from the last 3 `newsletter_prepass_tracking.chosen_angle` rows.
- Passed `exemplars=` at BOTH `generate_from_blocks` call sites — the primary block path AND the live A/B path (the one that runs today with `enabled:false`/`ab_comparison:true`).
- Resurrected Phase E: both empty-exemplar branches now return `{score:None, status:'not_scored'}` instead of a silent `score:0`; the genuine `Voice check failed` error branch is untouched.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add the load_edition_context loader** — `596b8d5` (feat)
2. **Task 2: Inject narrative_context + avoided-themes + omit null Theme** — `536232e` (feat)
3. **Task 3: Pass exemplars at both call sites + resurrect Phase E** — `e38cd7c` (feat)

**Plan metadata:** committed with SUMMARY/STATE/ROADMAP/REQUIREMENTS (docs: complete plan)

## Files Created/Modified
- `docker/newsletter/newsletter_poller.py` — new `load_edition_context` loader + `_le_*` helpers; `process_task` narrative_context/avoided_themes injection; D-08 Theme-omit in the single-pass continuity block; `exemplars=` at both call sites.
- `docker/newsletter/block_pipeline.py` — Phase E empty-exemplar guard (`phase_e_voice_check`) and `generate_from_blocks` default now return a distinguishable "not scored" verdict (not `score:0`).

## Decisions Made
- **Exemplar-pool marker = `exemplars_status` enum** ('scored' / 'not_scored') on the returned context (Claude's Discretion per D-02): unambiguously distinct from both `empty:True` (corpus empty) and a real Phase E `score:0`.
- **Phase E "not scored" shape = `{score:None, status:'not_scored', observations:[…]}`** (D-04). `score:None` is provably not `score:0`, so the block_pipeline `"score": 0` count drops 3 → 1 (only the genuine-error branch remains).
- **Paragraph split = blank-line `re.split(r'\n\s*\n', md)`** (Claude's Discretion, D-05) with `len(para.split()) >= 40` word filter and header/list exclusion via local `_LE_SECTION_HEADER`/`_LE_BOLD_HEADER`/`_LE_LIST_ITEM` patterns mirroring `verification.py:96-97`.

## Deviations from Plan

None — plan executed exactly as written. (Two of my own in-code comments initially contained the literal substrings `.in_(` and `continuity context empty`, which tripped the `grep -c` verify gates; I reworded the comments — these were gate-string hygiene corrections within the same task, not behavioral deviations.)

## Issues Encountered

**Live exemplar-flow concern for Plan 03 (D-17) — flagged, NOT auto-changed.**
The processor pre-populates `input_data['narrative_context']` when it creates the `write_newsletter` task (`agentpulse_processor.py:5615`), and that upstream context carries `previous_editions`/`recent_spotlights` but **no `exemplars`**. Because this plan's locked must-have (CTX-04 / D-14) mandates `setdefault` so "an upstream-provided narrative_context wins," the upstream context will win in live operation and the loader's `exemplars` may therefore **not reach the `generate_from_blocks` call sites** — leaving Phase E in the `not_scored` state even though 7 operator-written editions exist.

- I implemented `setdefault` exactly as the locked decision requires (changing it to an unconditional assignment or a merge would contradict CTX-04/D-14 and is an architectural call, not an auto-fix).
- **Plan 03's live D-17 trigger MUST confirm exemplars actually flow into Phase E** (`voice_score.score > 0`, ≥1 observation). If they do not, the operator/planner decides between: (a) the processor stops pre-populating `narrative_context`, (b) the injection merges `exemplars` into any existing `narrative_context` instead of full `setdefault`, or (c) the newsletter-service loader is made authoritative. This is surfaced loudly per the milestone's fail-loud spine rather than silently worked around.

## Data-Hygiene Backfill (D-12/D-13) — operator/orchestrator-owned, NOT in this plan

This plan modifies only the two `.py` files. The `data_snapshot.lead_theme` backfill on operator-written editions **25, 26, 27, 28** (30–32 already have it) + `published_at` non-null verification on all 7 operator editions is a **live-data mutation = worktree-unsafe, orchestrator/operator-owned via Supabase MCP** (D-13), and Plan 03's bridge/`weeks_ago` quality depends on it. It is intentionally absent from this code plan.

## User Setup Required

None for this plan's code. **Operator action carried forward (D-12/D-13):** apply the `lead_theme` backfill (editions 25–28, operator-confirmed candidate themes) + verify `published_at` non-null on all 7 operator editions via MCP before Plan 03's live trigger.

## Next Phase Readiness
- **Plan 02 (Wave 2):** the loader's explicit `supabase` param + three-state contract are ready for the deterministic fixture suite (D-16 cases: shape, operator_written filtering, ≥40-word/non-header/list filtering, empty-corpus, empty-operator-pool not-scored).
- **Plan 03 (Wave 3):** ready for the live trigger — but see the Issues concern above: the live run must confirm exemplars actually reach Phase E given the upstream `narrative_context` pre-population + `setdefault`.
- Downstream Phase 29 (Layer-2 judge) gets `previous_editions` angles + `exemplars` from the same loader output.

## Self-Check: PASSED
- Files: FOUND `docker/newsletter/newsletter_poller.py`, FOUND `docker/newsletter/block_pipeline.py`
- Commits: FOUND `596b8d5`, FOUND `536232e`, FOUND `e38cd7c`
- All plan `<verification>` gates pass: `ast.parse` OK (both files); `load_edition_context`==1; poller `.in_(`==1; block_pipeline `"score": 0`==1; poller `exemplars=`==2; `setdefault('narrative_context'`==1; `setdefault('avoided_themes'`==1.

---
*Phase: 26-continuity-exemplar-context*
*Completed: 2026-06-22*
