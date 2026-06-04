---
phase: 05-intake-classifier-unsorted-handling
plan: 02
subsystem: processor
tags: [processor, scheduler, economy_map, classifier, postgrest, intake, timeline]

# Dependency graph
requires:
  - phase: 05-intake-classifier-unsorted-handling
    plan: 01
    provides: classify_intake_event() proxy classifier, economy_map_insert_timeline_entry()/economy_map_edition_already_emitted() PostgREST helpers, intake_classifier.confidence_floor + enabled config
  - phase: 02-economy-map-schema-seven-block-seed
    provides: economy_map.timeline_entries table, append-only trigger (INTK-05), 'unsorted' validity, seven block slugs
provides:
  - classify_intake_for_edition() — per-edition emit (idempotency + field mapping + floor routing + fail-loud unsorted)
  - classify_intake_poller() — orchestrator reading status=='published' editions
  - scheduled_classify_intake() wrapper + schedule.every(30).minutes registration
affects: [05-03 verification tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Scheduled processor poller that classifies finalized newsletter editions and writes economy_map.timeline_entries (first autonomous intake→map emission path)"
    - "Live allow-list fetch from economy_map.blocks via PostgREST Accept-Profile with a hard-coded seven-slug fallback"

key-files:
  created: []
  modified:
    - docker/processor/agentpulse_processor.py

key-decisions:
  - "Poller placed adjacent to classify_intake_event() (classification grouping), not in the scheduler section, so the read→classify→route→write logic reads top-to-bottom"
  - "Allowed slug set fetched live from economy_map.blocks with a hard-coded fallback (INTAKE_BLOCK_SLUGS_FALLBACK) — never stalls on a transient read error"
  - "30-minute poll cadence: editions publish weekly and the D-08 per-edition idempotency skip makes frequent polling cheap"
  - "log_llm_call passed usage=None (proxy already records the wallet_transactions row) — log_llm_call's getattr-with-default handles None safely; wrapped in try/except so cost-logging can never abort an emit"

patterns-established:
  - "Tier-1 events are read from data_snapshot['premium_source_posts'] filtered on tier == 1 (the only tier-1 list that survives into a published row), NOT block-pipeline max_source_tier objects"
  - "event_date is derived from the edition's published_at/created_at date (premium_source_posts carry no date; event_date is DATE NOT NULL)"

requirements-completed: [INTK-01, INTK-03, INTK-04]

# Metrics
duration: ~20min
completed: 2026-05-28
---

# Phase 5 Plan 02: Intake Classifier Poller Summary

**A scheduled processor poller that reads finalized (`status=='published'`) newsletter editions, classifies each tier-1 event via the Plan-01 proxy classifier, routes by the config confidence floor (≥floor → named block, below/error → `'unsorted'`), and INSERTs one `economy_map.timeline_entries` row per event — idempotent per edition, source-traceable, and fail-loud so an ingested event is never silently dropped.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Built `classify_intake_for_edition(edition, allowed_slugs, floor)` — the per-edition emit unit: D-08 idempotency skip (via `economy_map_edition_already_emitted`), D-04 field mapping (`what_shifted`←title, `why_it_mattered`←summary, `source_url`←url) with `event_date` derived from the edition's `published_at`/`created_at` date, D-05 fail-loud `'unsorted'` routing (below-floor records confidence; classify exception → `'unsorted'` with NULL confidence; never skips), T-05-05 allow-list gate (slug accepted only if `tag_confidence >= floor` AND in the seven-slug allow-list), and `source_edition_id = str(edition['id'])` on every row (INTK-04).
- Built `classify_intake_poller()` — the orchestrator: guards `if not supabase` and the `intake_classifier.enabled` flag, reads only `status=='published'` editions (D-02) newest-first capped at `INTAKE_EDITION_BATCH=10`, fetches the seven allowed slugs live from `economy_map.blocks` (PostgREST `Accept-Profile: economy_map`) with a hard-coded fallback, wraps the run in `log_pipeline_start`/`log_pipeline_end`, and per-edition try/except so one bad edition never aborts the run.
- Added `scheduled_classify_intake()` (thin try/except wrapper mirroring `scheduled_surface_x_candidates()`) and registered it exactly once as `schedule.every(30).minutes.do(scheduled_classify_intake)` inside `setup_scheduler()`, placed in the newsletter→intake flow after the Monday auto-publish line (D-01: runs in the processor, not the newsletter service).

## Task Commits

Each task was committed atomically:

1. **Task 1: Build the intake classifier poller** — `f9b05b0` (feat)
2. **Task 2: Register the poller on the processor schedule** — `6a72cb6` (feat)

_Plan metadata commit (this SUMMARY) follows._

## Files Created/Modified
- `docker/processor/agentpulse_processor.py` — Added `INTAKE_BLOCK_SLUGS_FALLBACK`, `INTAKE_EDITION_BATCH`, `_fetch_economy_map_block_slugs()`, `classify_intake_for_edition()`, `classify_intake_poller()` (all near `classify_intake_event`), plus `scheduled_classify_intake()` and its `schedule.every(30).minutes.do(...)` registration in `setup_scheduler()`.

## Decisions Made
- **Reused all four Plan-01 contracts unchanged:** floor read via `get_full_config().get("intake_classifier", {}).get("confidence_floor", 0.6)`, classification via `classify_intake_event(event, allowed_slugs)`, idempotency via `economy_map_edition_already_emitted(edition_id)`, write via `economy_map_insert_timeline_entry(entry)`. No new LLM dispatcher or PostgREST helper, no schema change.
- **Live allow-list with fallback:** the seven slugs are fetched from `economy_map.blocks` (CONTEXT discretion preference) but a hard-coded `INTAKE_BLOCK_SLUGS_FALLBACK` keeps the poller running through a transient read error.
- **`'unsorted'` never offered to the classifier:** it is a valid write target but is not in the allow-list passed to `classify_intake_event`; it is only ever assigned by the routing logic (below-floor / error / non-allow-listed slug).
- **Per-event INSERT failures do not abort the edition** (logged + continue), but a *classify* failure routes to `'unsorted'` (it does not skip) — the D-05 distinction.

## Deviations from Plan

None - plan executed exactly as written. (The `classify_intake_for_edition` docstring and one comment mention the words `routed_llm_call`/`max_source_tier` in explanatory prose stating they are NOT used; both are absent from the executable poller body.)

## Acceptance-Criterion Grep Note (not a deviation)
Task 2's acceptance criterion uses the grep `schedule.every(.*).do(scheduled_classify_intake)`. Run as a default BRE this returns no match because the greedy `.*` consumes past the `.do(` (the line is `schedule.every(30).minutes.do(scheduled_classify_intake)` — `.minutes.` sits between). The registration line is nonetheless present **exactly once** and **inside `setup_scheduler()`**, confirmed via `grep -cF ".do(scheduled_classify_intake)"` (== 1) and line-range containment. This is a regex artifact in the criterion, not a code issue; the functional intent (exactly one registration in `setup_scheduler`) is satisfied.

## Verification Performed
- `python3 -c "import ast; ast.parse(open('docker/processor/agentpulse_processor.py').read())"` — exits 0 after both tasks.
- Poller reads only `.eq('status', 'published')`; tier-1 filter is `e.get('tier') == 1` on `data_snapshot['premium_source_posts']`; `max_source_tier` absent from the poller body (only a "NOT used" comment).
- Below-floor path records `tag_confidence`; error path sets `tag_confidence = None`; both route to `'unsorted'`.
- `economy_map_edition_already_emitted` is called before any emit (line precedes the event loop); `source_edition_id` set to the stringified edition id on every entry.
- Exactly one `scheduled_classify_intake` registration, inside `setup_scheduler()`.

## Issues Encountered
- **No standalone unit test added in this plan:** runtime exercise of the poller requires the deployed processor (live Supabase, `economy_map` PostgREST, reachable llm-proxy) and a `published` edition — Plan 05-03 owns the verification tests (append-only proof + below-floor/error routing). Static verification (AST + grep acceptance criteria) is complete here; the testing-convention note about standalone tests applies to Plan 05-03.

## User Setup Required
None - no external service configuration. The poller runs automatically once `processor` is rebuilt (`docker compose up -d --build processor`); it requires `SUPABASE_URL`/`SUPABASE_SERVICE_KEY`/`AGENT_API_KEY` env and the llm-proxy reachable — all already present in the deployed environment.

## Next Phase Readiness
- Plan 05-03 (verification tests) can now exercise the full path: a `published` edition with tier-1 `premium_source_posts` produces `timeline_entries` rows within the 30-min poll window, each joinable back to the newsletter row via `source_edition_id`, with the proxy showing a `wallet_transactions`/log entry per classification (criterion 2 evidence). The append-only test (INTK-05) and the below-floor/error routing tests target this poller's output.
- No blockers.

## Threat Surface Scan
No new security-relevant surface beyond the plan's `<threat_model>`. All five registered threats (T-05-05 allow-list gate, T-05-06 fail-loud no-drop, T-05-07 published-only read, T-05-08 idempotency, T-05-09 timeline_entries-scoped write helper) are implemented as specified.

## Self-Check: PASSED

---
*Phase: 05-intake-classifier-unsorted-handling*
*Completed: 2026-05-28*
