---
phase: 10-operator-write-commands
plan: 03
subsystem: infra
tags: [processor, schedule, economy_map, postgrest, synthesis, fail-loud, drain-poller]

# Dependency graph
requires:
  - phase: 10-operator-write-commands (Plan 10-01)
    provides: "economy_map.synth_requests table (status CHECK {pending,processing,done,failed}, version_id, error cols) + migration 041 uq_block_body_versions_one_open_draft partial UNIQUE index"
  - phase: 10-operator-write-commands (Plan 10-02)
    provides: "gato_brain /map-synth handler that validates + enqueues a pending synth_requests row and acks '~30s'"
  - phase: 07 (synthesis)
    provides: "synthesize_block / synthesize_blocks_poller / economy_map_insert_block_body_version / block_has_open_draft / load_synth_identity / log_pipeline_start-end"
provides:
  - "force=True bypass on synthesize_block (skips N/T eligibility ONLY, never the open-draft guard)"
  - "23505 benign-skip around the draft INSERT (lost check-then-act race → logged skip, never abort)"
  - "synth_request_drain_poller — fail-loud, per-request-isolated drain of pending synth_requests"
  - "economy_map_update_synth_request — purpose-scoped PostgREST PATCH writer for the request status lifecycle"
  - "scheduled_synth_request_drain wrapper registered at schedule.every(30).seconds (cadence pinned to gato_brain's ~30s ack)"
affects: [operator-write-commands, map-synth, economy_map, synthesis]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cross-service trigger via DB request-queue + short processor poll (no HTTP surface on processor)"
    - "Terminal status mapped onto a closed CHECK set: skip/race → failed+explanatory error, never an out-of-set value that would self-conceal via 23514"
    - "force flag bypasses ONLY the eligibility predicate, never the open-draft invariant (defense-in-depth backstop)"

key-files:
  created: []
  modified:
    - "docker/processor/agentpulse_processor.py"

key-decisions:
  - "Drain cadence pinned to schedule.every(30).seconds to match gato_brain's '~30s' /map-synth ack (cross-plan coupling)"
  - "Open-draft / lost-23505-race skip mapped to status='failed' with an explanatory error string — NEVER a 'skipped' status value (would hit migration 040's 23514 CHECK and make the failure invisible, violating D-03)"
  - "force=True bypasses ONLY is_block_eligible (N/T); block_has_open_draft stays a hard guard (D-02)"
  - "23505/duplicate-key INSERT failures converted to a logged benign skip in-memory dict; non-23505 still raise BlockSynthesisError (fail-loud preserved)"

patterns-established:
  - "Pattern 1: synth-request drain poller mirrors synthesize_blocks_poller's fail-loud skeleton exactly (supabase guard → config-enable → log_pipeline_start FIRST → identity/key fail-loud → per-item isolation → log_pipeline_end)"
  - "Pattern 2: purpose-scoped economy_map writer (economy_map_update_synth_request) for the request status lifecycle, never a generic schema-agnostic writer; direct PostgREST, never supabase-py"

requirements-completed: [CMD-07]

# Metrics
duration: ~12min
completed: 2026-06-03
---

# Phase 10 Plan 03: Synth-Request Drain Poller Summary

**Processor-side cross-service /map-synth mechanism: a 30s `schedule` drain of pending `economy_map.synth_requests` running `synthesize_block(force=True)` (N/T bypassed, open-draft invariant intact), writing a queryable terminal status within the migration-040 CHECK set, plus a 23505 benign-skip backstop on the draft INSERT.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-03T20:43:00Z (approx)
- **Completed:** 2026-06-03T20:47:00Z
- **Tasks:** 3
- **Files modified:** 1

## Accomplishments
- `synthesize_block` gained `force: bool = False`; under `force=True` only the `is_block_eligible` N/T predicate is bypassed (D-01) while `block_has_open_draft` stays a hard guard (D-02) — an open draft under force returns a skip, never a second draft. Default callers are byte-for-byte identical.
- 23505 benign-skip wrapped around `economy_map_insert_block_body_version`: a `23505`/`duplicate key` `RuntimeError` (migration 041's unique index on a lost race) converts to a logged skip returning `{'status': 'skipped', 'reason': 'race-lost-open-draft'}`; non-23505 still raises `BlockSynthesisError` (D-07, fail-loud preserved).
- `synth_request_drain_poller()` added, mirroring `synthesize_blocks_poller`'s fail-loud skeleton exactly: `if not supabase` → config-enable → `log_pipeline_start('synth_request_drain')` FIRST → `load_synth_identity()` None fail-loud → `_get_agent_api_key()` missing fail-loud → per-request try/except isolation → `log_pipeline_end`.
- Pending requests read via direct PostgREST (`status=eq.pending`, `order=created_at.asc`, `Accept-Profile: economy_map`); each request marked `processing`, block fetched by slug, `synthesize_block(..., force=True)` called.
- Terminal status mapped onto the closed migration-040 CHECK set `{pending,processing,done,failed}`: genuine synthesis → `done` + `version_id`; open-draft/lost-race skip → `failed` with an explanatory queryable error (NEVER `'skipped'`); genuine exception → `failed` with `error=str(e)`, `logger.error(exc_info=True)`.
- `economy_map_update_synth_request` purpose-scoped PATCH writer added (Content-Profile: economy_map, fail-loud non-2xx, never supabase-py).
- `scheduled_synth_request_drain` thin wrapper added and registered at `schedule.every(30).seconds` — cadence PINNED to gato_brain's `~30s` ack (Plan 02 cross-plan coupling).
- Processor rebuilt scoped, healthy, and the drain observed firing on its 30s interval.

## Task Commits

Each task was committed atomically:

1. **Task 1: force bypass + 23505 benign-skip in synthesize_block** - `aac5613` (feat)
2. **Task 2: synth_request_drain_poller + economy_map_update_synth_request** - `798a6b0` (feat)
3. **Task 3: scheduled_synth_request_drain wrapper + schedule.every(30).seconds registration + processor rebuild** - `72d98d0` (feat)

## Files Created/Modified
- `docker/processor/agentpulse_processor.py` - Added `force` param + 23505 benign-skip to `synthesize_block`; added `economy_map_update_synth_request` writer, `synth_request_drain_poller`, `scheduled_synth_request_drain` wrapper, and the `schedule.every(30).seconds` registration.

## Decisions Made
- **Cadence = 30s (not the full 30-60s range):** pinned to gato_brain's `~30s` /map-synth ack so the two plans stay consistent (cross-plan coupling enforced by the objective).
- **Skip → `failed` with explanatory error:** the open-draft / lost-23505-race "skipped synthesis" case is written as `status='failed'` with a non-null, operator-queryable error (e.g. "open draft already exists — no synthesis performed; approve or reject the existing draft via /map-pending"). Writing `'skipped'` was explicitly avoided — it would hit migration 040's 23514 CHECK and make the failed forced-synth invisible, the exact fail-loud-governance violation D-03 guards against.
- **`'done'` reserved for genuine synthesis only;** every other terminal outcome is `failed` (queryable, never silent).
- **Per-request status-write also wrapped:** the `failed` PATCH in the exception path is itself try/except'd so a failed status write logs loud (the run row still records `failed`) rather than aborting the drain.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None. The grep gate for `status=eq.pending` matched the docstring (which uses the bare form) as well as the param dict — both intentional. Drain fired at 20:46:37, ~32s after the scheduler configured at 20:46:05, confirming the 30s interval.

## User Setup Required
None - no external service configuration required. Migrations 040/041 were already applied to the production DB (per the objective).

## Next Phase Readiness
- CMD-07 processor side is complete: gato_brain enqueues (Plan 02), the processor drains within ~30s and produces a `draft`, and the request row carries a queryable terminal status.
- Phase 10 wave-2 (gato_brain write handlers / migrations in Plans 01-02) is the remaining surface; this plan closes the SC3 cross-service synth loop.
- End-to-end validation (`/map-synth <slug>` → draft in `/map-pending` → request `done` with version_id) is an end-of-phase check; processor health + empty-queue drain firing is confirmed.

## Self-Check: PASSED

- `docker/processor/agentpulse_processor.py` present (modified): FOUND
- Commit `aac5613`: FOUND
- Commit `798a6b0`: FOUND
- Commit `72d98d0`: FOUND
- ast.parse: PASSED after each task
- Grep gates: BYPASS_AND_SKIP_OK, DRAIN_POLLER_OK, SCHEDULER_OK all passed
- Processor: healthy; drain fired on 30s interval (`Synth-request drain: {'drained': 0, ...}`)

---
*Phase: 10-operator-write-commands*
*Completed: 2026-06-03*
