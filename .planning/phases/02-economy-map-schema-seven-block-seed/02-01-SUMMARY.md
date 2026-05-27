---
plan: 02-01-economy-map-migration
phase: 02-economy-map-schema-seven-block-seed
status: complete
completed: 2026-05-27
requirements: [SCHM-01, SCHM-02, SCHM-03, SCHM-04, SCHM-05, SCHM-06, SCHM-07, SCHM-08]
---

## What was built

`supabase/migrations/033_economy_map_schema.sql` — one self-contained 420-line migration that lands the entire structural foundation for the Agent Economy living reference articles. Applied to live Supabase project `zxzaaqfowtqvmsbitqpu` via `mcp__claude_ai_Supabase__apply_migration` on 2026-05-27.

The migration creates, in one file:

- **`economy_map` schema** + `GRANT USAGE` to `anon`, `authenticated`, `service_role`
- **`economy_map.maturity` ENUM** (5 values, ordered: `nascent → emerging → contested → consolidating → mature`)
- **Three tables**:
  - `blocks` — 7 canonical rows (one per Agent Economy block), CHECK constraints on `tier`/`accent`
  - `block_body_versions` — append-only history of synthesized block bodies; pinned columns (D-11): `body_md`, `synthesized_from_through`, `proposed_maturity`, `validator_report`, `block_slug`; lifecycle columns (D-12): `status`, `published_at`
  - `timeline_entries` — fully append-only narrative ledger; `block_slug` is NOT a FK (per SCHM-08, `'unsorted'` is valid)
- **Two `BEFORE UPDATE OR DELETE` triggers** (`block_body_versions_append_only_trg`, `timeline_entries_append_only_trg`) — enforce content immutability against service_role (which bypasses RLS by design). The trigger functions raise typed exceptions with grep-friendly `'append-only'` substrings.
- **Two `SECURITY DEFINER` RPCs** (`publish_block_version`, `reject_block_version`) — both pin `SET search_path = economy_map, public` (T-02 mitigation, NEW pattern not present in 013/015 in-tree analogs); both have `REVOKE ALL FROM PUBLIC` + `GRANT EXECUTE TO service_role` only (D-19, T-06 mitigation)
- **RLS posture** (D-05/D-06/D-07; T-03/T-04 mitigations):
  - `blocks_anon_read`: `USING (true)` — block frames public
  - `block_body_versions_anon_read`: `USING (status = 'published')` — drafts hidden
  - `timeline_entries_anon_read`: `USING (block_slug <> 'unsorted')` — low-confidence entries operator-only
- **Schema/table grants** — `SELECT` to `anon` on all three tables; `ALL ON ALL TABLES` to `service_role`
- **Idempotent 7-block seed** with `ON CONFLICT (slug) DO NOTHING` (D-20 — re-runs do NOT clobber operator-set `live_tension`)

## Key files

- **Created**: `supabase/migrations/033_economy_map_schema.sql` (420 lines, 25KB)
- **Read-only references** during execution: `supabase/migrations/004_core_tables.sql`, `006_rls_policies.sql`, `013_unsubscribe_rpc.sql`, `015_agent_wallets.sql`, `024_x_source_accounts.sql`, `021_x_distribution_pipeline.sql`, `032_prepass_tracking_justification_and_staleness.sql`

## Three first-in-tree precedents established

This migration introduces three patterns that did not exist in the repo before — future agents will reference `02-PATTERNS.md` §§2/3/6 to find these:

1. **`CREATE SCHEMA IF NOT EXISTS`** + cross-role `GRANT USAGE` — first isolated schema in the repo (per D-04; required for `Accept-Profile: economy_map` resolution)
2. **`CREATE TYPE … AS ENUM`** wrapped in a replay-safe `DO $$ … pg_type IF NOT EXISTS … END $$` block — first real Postgres ENUM (per D-03/SCHM-05; deliberately diverges from migration 021 line 10's `text + CHECK` pattern)
3. **`BEFORE UPDATE OR DELETE` trigger** with the loud comment block — append-only enforcement that BINDS service_role (RLS does not). The MANDATORY 9-line comment ("INTENTIONALLY NOT RLS … the 27-day silent wallet bug ran as service_role … future developer WILL try to simplify to RLS. Do not.") is committed verbatim from 02-PATTERNS.md §6.

## Verification (live database)

All six sanity queries from Task 3 returned the expected results when run against `zxzaaqfowtqvmsbitqpu`:

| Check | Expected | Actual |
|-------|----------|--------|
| 4a `COUNT(*) FROM economy_map.blocks` | 7 | 7 ✓ |
| 4b 7 slugs in D-23 order | identity-trust, memory-context, payments-settlement, autonomy-control, governance-accountability, psychology-disposition, regulation-legal | ✓ all tiers/accents/sort_orders match; all `maturity='nascent'` |
| 4c `information_schema.routines` security_type | publish_block_version=DEFINER, reject_block_version=DEFINER, trigger fns=INVOKER | ✓ |
| 4d `pg_trigger` for economy_map | block_body_versions_append_only_trg, timeline_entries_append_only_trg | ✓ both registered |
| 4e `pg_policy` predicates | blocks_anon_read=true, block_body_versions_anon_read=`(status='published')`, timeline_entries_anon_read=`(block_slug<>'unsorted')` | ✓ all 3 match D-05/06/07 |
| 4f maturity enum order | nascent, emerging, contested, consolidating, mature | ✓ |

Supabase advisor (security): the two SECURITY DEFINER RPCs are NOT flagged for `function_search_path_mutable` — confirms `SET search_path = economy_map, public` took effect (T-02 mitigation lands as designed). The two `SECURITY INVOKER` trigger functions are flagged as a minor hardening note (no cross-schema name resolution, near-zero practical risk; deferred — would require an ALTER FUNCTION migration to set their search_path).

## Phase 1 §4.5 — partially resolved

Per D-24, Phase 1 §4.5 known unknown is the Supabase exposed-schemas allowlist. Status as of completion:

- **Management API `db_schema` value** — PATCHed to include `economy_map`. Verified persisted via `GET /v1/projects/zxzaaqfowtqvmsbitqpu/postgrest`: `"db_schema": "public, graphql_public, lab, rivalscope, economy_map"`. ✓
- **PostgREST runtime cache** — STILL serves the pre-PATCH allowlist (`PGRST106` 406 on `Accept-Profile: economy_map`). This is a Supabase Cloud platform quirk: the Management API PATCH persists the config but does NOT trigger a PostgREST container redeploy. Available restart endpoints (`/restart-services`, `/database/restart`, `/services/restart`, etc.) return `Cannot POST` on the paid plan; pause endpoint is free-tier-only.
- **Mitigation** — toggle PATCH (remove + re-add) attempted; no effect. Dashboard "Save" click attempted; no effect. Background poll set up to detect when Supabase's eventual config-reload cycle propagates (anywhere from minutes to hours).
- **Net status**: persisted setting is correct, PostgREST runtime cache is stale, anon-key probe (D-25 case 4) is **pending propagation**. Plan 02-02 will run all SQL-level verification cases via `execute_sql` immediately and backfill the anon-probe evidence into `02-VERIFY-RESULTS.md` once PostgREST acknowledges the new allowlist.

## SCHM requirements covered

- **SCHM-01** — `economy_map` schema exists ✓
- **SCHM-02** — `economy_map.blocks` table with all expected columns ✓
- **SCHM-03** — `economy_map.block_body_versions` table with pinned columns + lifecycle columns ✓
- **SCHM-04** — `economy_map.timeline_entries` table ✓
- **SCHM-05** — `economy_map.maturity` ENUM with 5 values in correct order ✓
- **SCHM-06** — `publish_block_version` + `reject_block_version` RPCs queryable, SECURITY DEFINER, atomic ✓
- **SCHM-07** — 7 blocks seeded in D-23 order ✓
- **SCHM-08** — `'unsorted'` is a valid `timeline_entries.block_slug` (no FK to `blocks.slug`) ✓

## Seven block slugs (in D-23 sort_order)

1. `identity-trust` (substrate, teal)
2. `memory-context` (substrate, teal)
3. `payments-settlement` (substrate, teal)
4. `autonomy-control` (behavior, purple)
5. `governance-accountability` (behavior, purple)
6. `psychology-disposition` (behavior, coral)
7. `regulation-legal` (frame, gray)

All seeded with `live_tension = 'TBD — set via /map-tension'` (grep-friendly placeholder per D-21) and `maturity = 'nascent'` (per D-20). The `/map-tension` command (Phase 10) is the only path that mutates `live_tension`.

## Notable deviations from plan

- **Task 3 + Task 4 MCP execution**: The plan instructed the `gsd-executor` agent to call `mcp__claude_ai_Supabase__apply_migration` directly, but the agent's tool schema strips MCP tools (known Claude Code upstream issue anthropics/claude-code#13898). The orchestrator (with MCP access) executed Tasks 3 + 4 instead. The executor wrote the migration in Task 2 and committed it; the orchestrator applied the migration, ran sanity queries, and surfaced results to the operator for the human-verify checkpoint. Operator approved 2026-05-27.

- **Task 4 partial closure**: The exposed-schemas allowlist is persisted at the platform-config level (Management API GET confirms `economy_map` is in `db_schema`) but PostgREST's runtime cache has not yet picked it up. This is documented as "pending PostgREST propagation" rather than a misconfiguration — the work that Phase 2 owned (persist the setting + verify it's stored correctly) is done; the propagation timing is a Supabase Cloud platform constraint.

## What enables Plan 02-02

- Live database schema is queryable via Supabase MCP `execute_sql` for all 5 D-25 verification cases (publish-RPC exercise, append-only trigger trips, RLS probe with draft rows, anon-probe for cases where PostgREST is needed).
- Migration file at `supabase/migrations/033_economy_map_schema.sql` is the canonical reference for the SQL queries in `02-VERIFY.sql`.
- 7 blocks present in `economy_map.blocks` — Plan 02-02 can immediately INSERT test draft rows into `block_body_versions` to exercise the publish/reject RPCs.

## Open items (carried out of phase scope)

- Background poll watching for PostgREST allowlist propagation (Task #8 in orchestrator's task list). Once HTTP 200 lands, anon-probe evidence backfills into `02-VERIFY-RESULTS.md`.
- Optional hardening (not blocking Phase 2): pin `SET search_path` on the two trigger functions to clear the two `function_search_path_mutable` advisor warnings. Practical risk near-zero (functions only reference `OLD`/`NEW` columns on the row being touched, no cross-schema name resolution). Defer to a follow-up migration if/when convenient.

## Self-Check: PASSED
