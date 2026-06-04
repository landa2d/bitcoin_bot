---
phase: 09-gated-publishing-approval-commands
plan: 01
subsystem: database

# Dependency graph
requires:
  - phase: 06/07 economy_map schema
    provides: "economy_map.publish_block_version RPC (migration 033 §9) + block_body_versions.synthesized_from_through pinned column"
provides:
  - "Migration 038: economy_map.publish_block_version re-emitted so approval advances blocks.last_synthesized_at from the approved draft's synthesized_from_through (D-01), never NOW()"
  - "Live RPC now carries the exact watermark semantics — Plan 09-02 can verify SC2 against the correct contract, not a NOW() false positive"
affects: [09-02 gated-publishing-approval-commands, phase-10-duplicate-draft-unique-index]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Full-body CREATE OR REPLACE FUNCTION re-emit for RPC body changes (NOT the ALTER FUNCTION ... SET shim used by 035/037, which only repairs a search_path GUC)"
    - "Watermark advances from the draft's pinned synthesized_from_through, so the next synthesis cycle's `created_at > last_synthesized_at` filter resumes exactly where the approved window ended"

key-files:
  created:
    - supabase/migrations/038_publish_block_version_watermark.sql
  modified: []

key-decisions:
  - "D-01: advance last_synthesized_at from the approved draft's synthesized_from_through, eliminating the synth→approve-window skip/double-count (IN-04 correctness contract)"
  - "D-01a scope fence: the WR-01 duplicate-draft UNIQUE/partial index is deliberately NOT folded in — stays deferred to Phase 10"
  - "Full body re-emit via CREATE OR REPLACE FUNCTION, not an ALTER FUNCTION shim — the latter only fixes a GUC and is the wrong tool for a body change"

patterns-established:
  - "RPC body amendments re-emit the whole function verbatim with minimal targeted edits, preserving SECURITY DEFINER, search_path, REVOKE/GRANT lines"

requirements-completed: [GATE-02]

# Metrics
duration: ~15min
completed: 2026-06-03
---

# Phase 9 Plan 01: publish_block_version Watermark Amendment Summary

**Migration 038 re-emits `economy_map.publish_block_version` so approval advances `blocks.last_synthesized_at` from the approved draft's pinned `synthesized_from_through` (D-01), never `NOW()` — applied live and drift-clean.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-06-03
- **Tasks:** 2 (Task 1 autonomous; Task 2 operator-gated MCP apply)
- **Files modified:** 1 created

## Accomplishments

- Wrote migration 038 as a FULL `CREATE OR REPLACE FUNCTION` re-emit of `economy_map.publish_block_version` (not an `ALTER FUNCTION ... SET` shim), changing exactly three things from migration 033 §9:
  1. Added `v_synthesized_from_through timestamptz;` to the DECLARE block.
  2. Extended Step 1's `RETURNING` to capture `synthesized_from_through INTO v_synthesized_from_through`.
  3. Set Step 4 `last_synthesized_at = v_synthesized_from_through` (replacing `NOW()`).
- Preserved `RETURNS void`, `LANGUAGE plpgsql`, `SECURITY DEFINER`, `SET search_path = economy_map, public`, and both `REVOKE ALL ... FROM PUBLIC` + `GRANT EXECUTE ... TO service_role` lines unchanged (T-09-01, T-09-02 hardening carried forward).
- Left Step 2 (typed RAISE on `v_slug IS NULL`) and Step 3 (supersede prior published) untouched; did NOT touch `reject_block_version`; added NO UNIQUE/partial index (D-01a scope fence).
- Applied migration 038 live to project `zxzaaqfowtqvmsbitqpu` via Supabase MCP `apply_migration` (operator-approved orchestrator action, prod-cutover discipline — NOT a shell CLI command, NOT `supabase db push`).
- Confirmed `scripts/drift-check.sh` reports `038_publish_block_version_watermark applied` and "no public function has an empty search_path".

## Task Commits

1. **Task 1: Write migration 038 amending the publish RPC watermark (D-01)** - `35b3a8c` (feat)
2. **Task 2: Apply migration 038 live via Supabase MCP + drift-check** - DB-only operator-gated action (no source commit; live database mutation verified by drift-check)

**Plan metadata:** docs commit (this SUMMARY)

## Files Created/Modified

- `supabase/migrations/038_publish_block_version_watermark.sql` - D-01 watermark amendment: re-emits `economy_map.publish_block_version` to advance `blocks.last_synthesized_at` from the approved draft's `synthesized_from_through` instead of `NOW()`.

## must_haves Verification

All four truths are now TRUE:

1. **Migration 038 exists and re-emits the FULL function body via `CREATE OR REPLACE` (not an ALTER FUNCTION shim)** — confirmed: file contains `CREATE OR REPLACE FUNCTION economy_map.publish_block_version(p_version_id uuid)` with the complete body (lines 30-74).
2. **The amended RPC sets `blocks.last_synthesized_at` from `synthesized_from_through`, never `NOW()`** — confirmed: Step 4 reads `last_synthesized_at = v_synthesized_from_through` (line 71); file contains no `last_synthesized_at = NOW()`.
3. **Migration 038 is applied live and drift-check reports no drift for `publish_block_version`** — confirmed: applied via Supabase MCP `apply_migration` to `zxzaaqfowtqvmsbitqpu`; `scripts/drift-check.sh` reports `038_publish_block_version_watermark applied` and a clean search_path audit.
4. **The `block_body_versions` append-only trigger is not violated — only `blocks` (a lifecycle table) is written** — confirmed: `synthesized_from_through` is only READ (Step 1 RETURNING); the only write target is `economy_map.blocks` (T-09-04, accepted).

### Live RPC spot-check (pg_get_functiondef via Supabase MCP)

- `step4_uses_watermark = true` — Step 4 assigns `last_synthesized_at = v_synthesized_from_through`.
- `step4_uses_now = false` — no `NOW()` watermark assignment remains in the live body.
- `step1_captures_watermark = true` — Step 1 RETURNING captures `synthesized_from_through` into `v_synthesized_from_through`.

## Decisions Made

- **D-01 watermark from draft, not wall-clock** — advancing from `synthesized_from_through` makes the approval-time watermark exact, so the next synthesis cycle's `created_at > last_synthesized_at` filter never skips or double-counts entries created in the synth→approve window (IN-04 correctness contract / GATE-02).
- **D-01a scope fence** — the WR-01 duplicate-draft UNIQUE/partial index was deliberately kept out of this migration; it remains deferred to Phase 10. Migration 038 changes only the watermark assignment.
- **Full body re-emit over ALTER shim** — chose `CREATE OR REPLACE FUNCTION` (verbatim re-emit with three targeted edits) because a body change cannot be expressed by the `ALTER FUNCTION ... SET` GUC-only shim used in 035/037.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The Task 2 live apply was an operator-approved orchestrator MCP action (Supabase `apply_migration`, prod-cutover discipline) and is already complete.

## Next Phase Readiness

- Plan 09-02 can now verify SC2 (gated-publishing approval command watermark behavior) against the correct live RPC semantics — the false-positive risk against the old `NOW()` body is eliminated.
- Phase 10 still owns the deferred WR-01 duplicate-draft UNIQUE/partial index (D-01a).

## Self-Check: PASSED

- `supabase/migrations/038_publish_block_version_watermark.sql` — FOUND.
- Commit `35b3a8c` (Task 1, migration 038) — FOUND in git log.
- Live drift-check confirms `038_publish_block_version_watermark applied` with a clean search_path audit; live `pg_get_functiondef` spot-check confirms watermark semantics (step4_uses_watermark=true, step4_uses_now=false, step1_captures_watermark=true).

---
*Phase: 09-gated-publishing-approval-commands*
*Completed: 2026-06-03*
