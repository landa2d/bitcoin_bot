---
phase: 10-operator-write-commands
plan: 02
subsystem: api
tags: [gato_brain, telegram, economy_map, postgrest, rpc, owner-gate, fastapi]

# Dependency graph
requires:
  - phase: 10-operator-write-commands (Plan 01)
    provides: "migration 040 RPCs (reassign_timeline_entry, insert_manual_timeline_entry, set_block_live_tension, enqueue_synth_request), synth_requests table, timeline_entries.reassigned_* lifecycle columns; migration 041 one-open-draft unique index — all applied live"
  - phase: 09-gated-publishing-approval-commands
    provides: "the owner-gate-first write-command pattern, _economy_map_rpc allowlist-guarded RPC-POST helper, _validate_version_id arg-validation template, _economy_map_get read helper"
provides:
  - "Four owner-gated Telegram write commands: /map-assign, /map-entry, /map-synth, /map-tension"
  - "Generalized _economy_map_rpc(fn, params: dict) helper with a six-RPC allowlist"
  - "_ECONOMY_MAP_BLOCK_SLUGS seven-slug input-validation allowlist"
  - "reassigned_to_entry_id is.null filter on the /map-pending unsorted backlog reads"
  - "Synth-request enqueue side of /map-synth (the processor drain poller is Plan 03)"
affects: [10-operator-write-commands-plan-03, processor-synth-request-drain]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Owner-gate-first → strict arg-validate (slug allowlist) → read precondition → allowlist-guarded RPC POST → typed-error UX (D-09/D-10)"
    - "Stateless single-shot multi-arg parsing: re-split parts[1] inside each handler; ' | ' delimiter for /map-entry"

key-files:
  created: []
  modified:
    - docker/gato_brain/gato_brain.py

key-decisions:
  - "Drain-cadence ack pinned to ~30s in /map-synth to stay consistent with Plan 03's schedule.every(30).seconds"
  - "tag_confidence and provenance handling live entirely in the migration-040 RPCs; gato_brain only validates + forwards params"
  - "Open-draft precondition uses a direct _economy_map_get on block_body_versions (status=eq.draft) and refuses without enqueuing (D-02)"

patterns-established:
  - "Generalized allowlist-guarded RPC helper: allowlist check BEFORE URL build; json=params; non-(200,204) RAISEs RuntimeError(resp.text) (fail-loud)"
  - "_validate_block_slug returns (slug, None) | (None, hint); reused as a typed unknown-slug message source on RPC block-not-found RAISEs"

requirements-completed: [CMD-05, CMD-06, CMD-07, CMD-08]

# Metrics
duration: ~12min
completed: 2026-06-03
---

# Phase 10 Plan 02: Operator Write Commands (gato_brain wiring) Summary

**Four owner-gated Telegram write commands — `/map-assign`, `/map-entry`, `/map-synth`, `/map-tension` — wired into gato_brain through a generalized allowlist-guarded `_economy_map_rpc`, a seven-block slug allowlist, and a `reassigned_to_entry_id IS NULL` backlog filter; gato_brain rebuilt and healthy.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-03T20:28Z (approx)
- **Completed:** 2026-06-03T20:41Z
- **Tasks:** 3
- **Files modified:** 1 (`docker/gato_brain/gato_brain.py`, +276/-17)

## Accomplishments
- Generalized `_economy_map_rpc(fn, version_id)` → `_economy_map_rpc(fn, params: dict)`, posting `json=params`, with the allowlist check still BEFORE the URL is built, `Content-Profile: economy_map` preserved, and non-(200,204) still RAISEing `RuntimeError(resp.text)` (fail-loud). Allowlist widened from 2 to 6 RPC names (the four migration-040 names verbatim). Both legacy call sites migrated to `{"p_version_id": version_id}`.
- Added `_ECONOMY_MAP_BLOCK_SLUGS` (seven canonical slugs, excludes `unsorted`) as the boundary input-validation allowlist.
- Added four `handle_map_*` handlers, each `(parts, access_tier)`, each owner-gated FIRST (D-09), with per-command validators and the five-case D-10 typed-error UX. `/map-synth` performs the open-draft GET precondition and refuses to enqueue when a draft exists (D-02).
- Wired dispatch (four `elif` branches) + extended the "Available:" fallthrough to all eight verbs; added `"reassigned_to_entry_id": "is.null"` to both `get_unsorted_entries` and `get_unsorted_count` so reassigned originals leave `/map-pending` immediately (D-04 SC1).
- Rebuilt `gato_brain` (scoped `docker compose up -d --build gato_brain`); container reports `Up (healthy)`, `/health` 200, clean uvicorn startup.

## Task Commits

1. **Task 1: Generalize `_economy_map_rpc` + widen allowlist + slug allowlist + migrate call sites** - `4936147` (feat)
2. **Task 2: Four owner-gated `handle_map_*` handlers + validators + open-draft precondition** - `9f70d5b` (feat)
3. **Task 3: Dispatch + Available fallthrough + unsorted `is.null` filter + rebuild** - `f34a2a5` (feat)

## Files Created/Modified
- `docker/gato_brain/gato_brain.py` - Generalized RPC helper + slug allowlist; four new write handlers + validators; dispatch/Available wiring; `is.null` filter on the two unsorted reads.

## Decisions Made
- **Drain cadence ack pinned to ~30s** in `handle_map_synth` per the cross-plan coupling note (Plan 03 registers `schedule.every(30).seconds`).
- **`/map-entry` delimiter is `' | '`** (D-06 Discretion), both halves required, otherwise a format usage hint.
- **RPC block-not-found RAISE** (`"not found"`) maps to the unknown-slug message in `/map-entry` and `/map-tension`; the reassign `"not an unsorted, un-reassigned entry"` RAISE maps to a distinct already-actioned message in `/map-assign`. All other failures re-raise to the top-level `Command failed: <e>` (D-10 case e).

## Deviations from Plan

None - plan executed exactly as written. All RPC names and parameter names match migration 040 verbatim (`reassign_timeline_entry(p_entry_id, p_block_slug)`, `insert_manual_timeline_entry(p_slug, p_what_shifted, p_why_it_mattered)`, `set_block_live_tension(p_slug, p_text)`, `enqueue_synth_request(p_slug)`).

## Issues Encountered
None.

## Known Stubs
None. The synth-request enqueue side is intentionally only the producer; the consumer (processor drain poller) is Plan 03's scope, not a stub — the enqueue durably lands a `pending` row in `economy_map.synth_requests` (migration 040, live).

## User Setup Required
None - no external service configuration required. Migrations 040/041 were applied live in Plan 01.

## Next Phase Readiness
- gato_brain side of CMD-05..08 is live and owner-gated. `/map-synth` enqueues `synth_requests` rows that **Plan 03's processor drain poller** (`schedule.every(30).seconds`) must consume; until Plan 03 ships, a queued synth request will sit `pending` (queryable, never a silent drop).
- Manual smoke (end-of-phase): owner runs each command → confirmation; non-owner → owner-only refusal; `unsorted`/unknown slug → typed rejection; `/map-synth` on a block with an open draft → refusal pointer to `/map-pending`.

## Self-Check: PASSED

- SUMMARY.md present at `.planning/phases/10-operator-write-commands/10-02-SUMMARY.md`
- `docker/gato_brain/gato_brain.py` present
- Commits `4936147`, `9f70d5b`, `f34a2a5` all present in git history
- Grep gates: RPC_GENERALIZED_OK, HANDLERS_OK, DISPATCH_OK
- `ast.parse` passes after every task
- gato_brain rebuilt scoped and reporting `Up (healthy)`

---
*Phase: 10-operator-write-commands*
*Completed: 2026-06-03*
