---
phase: 10-operator-write-commands
plan: 01
subsystem: database

# Dependency graph
requires:
  - phase: 06/07 economy_map schema
    provides: "economy_map.timeline_entries + timeline_entries_append_only() trigger (migration 033 §6/§10), block_body_versions draft lifecycle + idx_block_body_versions_status (033 §5), blocks.live_tension (033 §4)"
provides:
  - "Migration 040: economy_map.synth_requests queue table (pending→processing→done/failed, queryable error/version_id); timeline_entries.reassigned_to_entry_id/reassigned_from_entry_id mutable lifecycle columns + trigger exemption; four SECURITY DEFINER write RPCs (reassign_timeline_entry, insert_manual_timeline_entry, set_block_live_tension, enqueue_synth_request)"
  - "Migration 041: uq_block_body_versions_one_open_draft partial UNIQUE index — the WR-01 duplicate-draft structural backstop (own migration, D-07)"
  - "All applied live to prod ref zxzaaqfowtqvmsbitqpu and confirmed by drift-check (migration section) + schema smoke + trigger negative test"
affects: [10-02 gato_brain write commands (calls the four RPCs + reassigned-is-null reads), 10-03 processor drain poller (drains synth_requests, relies on the unique index + 23505 backstop)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Append-only trigger exemption by full-body re-emit: content columns stay IS DISTINCT FROM → RAISE; only the new reassigned_* lifecycle columns are left UPDATE-able (the block_body_versions status/published_at precedent)"
    - "SECURITY DEFINER write RPC boilerplate: SET search_path = economy_map, public + REVOKE ALL FROM PUBLIC + GRANT EXECUTE TO service_role, typed plpgsql params only (no string interpolation), CREATE OR REPLACE full-body re-emit"
    - "Single-winner reassignment gate: source SELECT requires block_slug='unsorted' AND reassigned_to_entry_id IS NULL, empty RETURNING → typed RAISE (cannot re-file an already-filed entry)"
    - "Partial UNIQUE index as a check-then-act race backstop (WHERE status='draft'): paired with a 23505 benign-skip in the writer"

key-files:
  created:
    - supabase/migrations/040_operator_write_commands_schema.sql
    - supabase/migrations/041_block_body_versions_unique_open_draft.sql
  modified: []

key-decisions:
  - "Entry-insert RPC named insert_manual_timeline_entry(p_slug, p_what_shifted, p_why_it_mattered); synth-enqueue RPC named enqueue_synth_request(p_slug) RETURNS uuid — gato_brain Plan 02 must use these exact names in its allowlist + params"
  - "Reassign copy uses tag_confidence = NULL (operator authority is not a classifier score, D-05) and copies event_date + provenance verbatim (NOT today)"
  - "synth_requests CHECK pins status to exactly {pending, processing, done, failed} — the drain poller (Plan 03) must never write any other value (a stray 'skipped' would hit a 23514 and make the failure invisible)"
  - "synth_requests is service_role-only (no RLS, no anon); explicit GRANT ALL TO service_role added because 033's blanket GRANT only covered tables existing at its apply time"
  - "041 shipped as its OWN migration (D-07), not folded into 040"

patterns-established:
  - "Operator write RPCs validate slugs/eligibility with typed RAISE (block % not found / not an unsorted entry) so gato_brain can map each to distinct UX"

requirements-completed: [CMD-05, CMD-06, CMD-07, CMD-08]

# Metrics
duration: ~20min
completed: 2026-06-03
---

# Phase 10 Plan 01: operator-write-command schema Summary

**Migrations 040 (synth_requests queue + reassign lifecycle + trigger exemption + four SECURITY DEFINER write RPCs) and 041 (uq_block_body_versions_one_open_draft partial UNIQUE index) authored, committed, and applied live to prod ref `zxzaaqfowtqvmsbitqpu` — drift-clean (migrations), schema-smoke verified, trigger negative test passing.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-06-03
- **Tasks:** 3 (Tasks 1-2 autonomous authoring by executor; Task 3 operator-gated MCP apply by orchestrator)
- **Files created:** 2 migrations

## Accomplishments

- **Migration 040** — five concerns following the 033/038 precedents:
  - `economy_map.synth_requests` table: `pending→processing→done/failed` CHECK lifecycle, queryable `error`/`version_id` columns, partial `idx_synth_requests_pending` for cheap drain polling.
  - `timeline_entries.reassigned_to_entry_id` / `reassigned_from_entry_id` — two nullable, mutable lifecycle columns.
  - `timeline_entries_append_only()` re-emitted full-body: every content column still RAISEs on change; the two `reassigned_*` columns left UPDATE-able (trigger, not RLS — service_role bypasses RLS).
  - Four SECURITY DEFINER RPCs (each `SET search_path = economy_map, public` + `REVOKE ALL FROM PUBLIC` + `GRANT EXECUTE TO service_role`, typed params only): `reassign_timeline_entry`, `insert_manual_timeline_entry`, `set_block_live_tension`, `enqueue_synth_request`.
- **Migration 041** — `uq_block_body_versions_one_open_draft ON economy_map.block_body_versions (block_slug) WHERE status = 'draft'`, the WR-01 structural backstop, as its own migration (D-07).
- **Applied live** via Supabase MCP `apply_migration` (040 then 041, NOT `supabase db push`).

## Verification

- Per-task grep gates: `MIGRATION_040_OK` (search_path pin count == 4) and `MIGRATION_041_OK` both pass.
- `scripts/drift-check.sh` migration section: all migrations ≥033 — including 040 + 041 — confirmed applied; RPC-drift section clean (no public function with empty search_path).
- Schema smoke (live `execute_sql`): `synth_requests` table present (1), `reassigned_*` columns present (2), `uq_block_body_versions_one_open_draft` index present (1), four RPCs present (4).
- Trigger negative test (rolled-back transaction): a content-column UPDATE on `timeline_entries` RAISEs; a `reassigned_to_entry_id` UPDATE succeeds.

## Issues / Notes

- **Pre-existing, out-of-scope drift:** `scripts/drift-check.sh` reports a `HARD DRIFT` line for `lab-data-provider` (code 2026-04-10 newer than its running image 2026-03-27). This service is untouched by Phase 10 and the drift predates this work — a known outstanding deploy item, not a Phase 10 regression.
- The executor authored Tasks 1-2 and stopped at the blocking checkpoint (no MCP access); the orchestrator performed the live apply, drift-check, and schema verification, then wrote this SUMMARY.

## Self-Check: PASSED
