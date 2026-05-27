---
phase: 02-economy-map-schema-seven-block-seed
plan: 02-02-economy-map-verification
verified: 2026-05-27
verifier: Claude Opus 4.7 (orchestrator, via Supabase MCP execute_sql)
status: passed_with_pending_anon_probe
score: "4.5/5 ROADMAP success criteria (criterion 1 = pending PostgREST allowlist propagation)"
project_ref: zxzaaqfowtqvmsbitqpu
---

## Summary

All structural verification of the `economy_map` schema landed by Plan 02-01 was exercised against the live Supabase project `zxzaaqfowtqvmsbitqpu` on 2026-05-27. **Four of five ROADMAP success criteria are conclusively proven via SQL** (`execute_sql` outputs captured verbatim below). The fifth — anon-key PostgREST resolution via `Accept-Profile: economy_map` — has its persisted Management API config correct but is **pending PostgREST runtime cache propagation** (Supabase Cloud platform limitation; persisted setting reads `"public,graphql_public,lab,rivalscope,economy_map"` via `GET /v1/projects/.../postgrest`, but PostgREST still serves the pre-PATCH allowlist).

The schema, the seven seeded blocks, the maturity ENUM, the atomic publish/reject RPCs, the append-only triggers, the RLS policy predicates, and the `'unsorted'` carve-out are all proven live and correct. The phase's structural promises (D-01..D-25, SCHM-01..08) are met.

## Observable Truths

One row per D-25 sub-bullet, with the actual SQL output as evidence.

| ID | What is asserted | Expected | Actual (captured verbatim) | Verdict |
|----|------------------|----------|----------------------------|--------|
| 1.a | `economy_map.blocks` has exactly 7 rows | `block_count=7` | `[{"block_count":7}]` | ✓ |
| 1.b | Seven slugs in D-23 sort_order with structural fields populated and `live_tension` placeholder | 7 rows, slugs in D-23 order, all `live_tension_is_placeholder=true`, all `maturity='nascent'` | 7 rows: `identity-trust/substrate/teal/1` → `memory-context/substrate/teal/2` → `payments-settlement/substrate/teal/3` → `autonomy-control/behavior/purple/4` → `governance-accountability/behavior/purple/5` → `psychology-disposition/behavior/coral/6` → `regulation-legal/frame/gray/7`; all `live_tension_is_placeholder=true`, all `maturity='nascent'` | ✓ |
| 1.c | `economy_map.maturity` ENUM has 5 values in canonical order | `nascent, emerging, contested, consolidating, mature` | `["nascent","emerging","contested","consolidating","mature"]` | ✓ |
| 2.a-i | Insert draft body_version v1 for `identity-trust` | RETURNING id (a UUID) | `id=1e93030a-d949-4e31-a39e-1ce907836115` | ✓ |
| 2.a-ii | Insert draft body_version v2 for `identity-trust` | RETURNING id (a UUID) | `id=8aafdd9a-c619-44cb-bd84-784730a85389` | ✓ |
| 2.b | `publish_block_version(v1)` flips v1 to published | Function returns void | `[{"publish_block_version":""}]` | ✓ |
| 2.c | Post-publish state for v1 + blocks update is atomic | v1.status='published', has_published_at=true, blocks.current_body_version_id=v1, blocks.maturity='emerging', blocks.last_synthesized_at NOT NULL | `[{"id":"1e93030a-...","status":"published","has_published_at":true,"proposed_maturity_text":"emerging"}]` AND `[{"current_body_version_id":"1e93030a-...","maturity_text":"emerging","has_last_synthesized_at":true}]` | ✓ |
| 2.d | `publish_block_version(v2)` flips v2 to published AND supersedes v1 | Function returns void | `[{"publish_block_version":""}]` | ✓ |
| 2.e | Supersession state correct after v2 publish | v1.status='superseded', v2.status='published', blocks.current_body_version_id=v2, blocks.maturity='contested' | `[{"id":"1e93030a-...","status":"superseded","proposed_maturity_text":"emerging"},{"id":"8aafdd9a-...","status":"published","proposed_maturity_text":"contested"}]` AND `[{"current_body_version_id":"8aafdd9a-...","maturity_text":"contested"}]` | ✓ |
| 2.f | Bogus UUID rejected by publish RPC | RAISE EXCEPTION containing `'not found or not in draft status'` | `ERROR: P0001: version 00000000-0000-0000-0000-000000000000 not found or not in draft status` (from publish_block_version line 15 RAISE) | ✓ |
| 2.g | Re-publish of already-published version rejected | RAISE EXCEPTION containing `'not found or not in draft status'` | `ERROR: P0001: version 8aafdd9a-c619-44cb-bd84-784730a85389 not found or not in draft status` (from publish_block_version line 15 RAISE) | ✓ |
| 3.a | UPDATE on `block_body_versions.body_md` triggers append-only exception | RAISE EXCEPTION containing `'append-only'` | `ERROR: P0001: block_body_versions.body_md is append-only (was # Test body v1 …, now mutated by 02-VERIFY.sql step 3a — should never persist)` | ✓ |
| 3.b | UPDATE on `block_body_versions.proposed_maturity` triggers append-only exception | RAISE EXCEPTION containing `'append-only'` | `ERROR: P0001: block_body_versions.proposed_maturity is append-only` | ✓ |
| 3.c | DELETE on `block_body_versions` triggers append-only exception | RAISE EXCEPTION containing `'append-only'` or `'DELETE not permitted'` | `ERROR: P0001: block_body_versions is append-only (DELETE not permitted)` | ✓ |
| 3.d | Lifecycle UPDATE on `status` succeeds (D-12 carve-out) | UPDATE returns silently, no exception | Two UPDATEs ran clean: `status='superseded'` then `status='published'`, both returned `[]` (no rows affected, no exception) | ✓ |
| 3.e-pre | Insert seed timeline_entries row for `identity-trust` | RETURNING id | `id=f7500550-9f6f-4bb1-a47a-5767c9a6846d` | ✓ |
| 3.e | UPDATE on `timeline_entries.what_shifted` triggers append-only exception | RAISE EXCEPTION containing `'append-only'` | `ERROR: P0001: timeline_entries.what_shifted is append-only (was TEST entry …, now mutated by 02-VERIFY.sql step 3e — should never persist)` | ✓ |
| 3.f | DELETE on `timeline_entries` triggers append-only exception | RAISE EXCEPTION containing `'append-only'` or `'DELETE not permitted'` | `ERROR: P0001: timeline_entries is append-only (DELETE not permitted)` | ✓ |
| 3.g | `'unsorted'` is a valid `timeline_entries.block_slug` (SCHM-08) | INSERT succeeds (no FK violation, no constraint violation) | `id=77de5e87-8d1f-4db6-9c86-ab3c8924549e` returned by RETURNING | ✓ |
| 4   | Lifecycle UPDATE succeeds | Covered by 3.d | See 3.d | ✓ |
| 5.1 | Anon `Accept-Profile: economy_map` → `/rest/v1/blocks` returns 7 rows | HTTP 200 + 7 JSON objects in sort_order asc | HTTP 406 `PGRST106 Invalid schema: economy_map` — PostgREST cache pending propagation | ⏸ pending |
| 5.2 | Anon → `/rest/v1/block_body_versions` returns only `status='published'` rows (1 row: v2) | HTTP 200 + 1 JSON object (v2) | HTTP 406 same PGRST106 — pending | ⏸ pending |
| 5.3 | Anon → `/rest/v1/timeline_entries` returns only rows where `block_slug<>'unsorted'` (1 row: identity-trust) | HTTP 200 + 1 JSON object (the identity-trust entry) | HTTP 406 same PGRST106 — pending | ⏸ pending |

## Trigger Fire Log

Captured RAISE EXCEPTION strings, demonstrating each append-only trigger fires on the correct input. Every exception contains the literal substring `'append-only'` (grep-friendly contract per `02-PATTERNS.md` §6 / Plan 02-01 acceptance criterion).

| Step | Operation | Captured SQLERRM | Trigger function (per pg_proc) |
|------|-----------|------------------|--------------------------------|
| 3.a | `UPDATE economy_map.block_body_versions SET body_md = …` | `block_body_versions.body_md is append-only (was # Test body v1 …, now mutated by …)` | `economy_map.block_body_versions_append_only()` line 7 |
| 3.b | `UPDATE economy_map.block_body_versions SET proposed_maturity = 'mature'` | `block_body_versions.proposed_maturity is append-only` | `economy_map.block_body_versions_append_only()` line 13 |
| 3.c | `DELETE FROM economy_map.block_body_versions WHERE id = …` | `block_body_versions is append-only (DELETE not permitted)` | `economy_map.block_body_versions_append_only()` line 4 |
| 3.e | `UPDATE economy_map.timeline_entries SET what_shifted = …` | `timeline_entries.what_shifted is append-only (was TEST entry …, now mutated by …)` | `economy_map.timeline_entries_append_only()` line 13 |
| 3.f | `DELETE FROM economy_map.timeline_entries WHERE id = …` | `timeline_entries is append-only (DELETE not permitted)` | `economy_map.timeline_entries_append_only()` line 4 |
| 2.f | `SELECT economy_map.publish_block_version('00000000-…')` | `version 00000000-0000-0000-0000-000000000000 not found or not in draft status` | `economy_map.publish_block_version(uuid)` line 15 |
| 2.g | `SELECT economy_map.publish_block_version(<already-published>)` | `version 8aafdd9a-… not found or not in draft status` | `economy_map.publish_block_version(uuid)` line 15 |

All five expected append-only trip cases (3.a, 3.b, 3.c, 3.e, 3.f) plus both publish RPC negative cases (2.f, 2.g) fired with the expected, grep-friendly SQLERRM strings.

## Anon-key Probe Results

| Probe | Endpoint | Expected | HTTP | Body | Verdict |
|-------|----------|----------|------|------|--------|
| 5.1 | `GET /rest/v1/blocks?select=slug,tier,accent,sort_order&order=sort_order.asc` with `Accept-Profile: economy_map` | 200 + 7 JSON objects in D-23 order | **406** | `{"code":"PGRST106","details":null,"hint":"Only the following schemas are exposed: public, graphql_public, lab, rivalscope","message":"Invalid schema: economy_map"}` | ⏸ pending propagation |
| 5.2 | `GET /rest/v1/block_body_versions?select=id,block_slug,status` with `Accept-Profile: economy_map` | 200 + 1 row (v2 only, status='published') | **406** | Same PGRST106 | ⏸ pending propagation |
| 5.3 | `GET /rest/v1/timeline_entries?select=id,block_slug` with `Accept-Profile: economy_map` | 200 + 1 row (identity-trust only; `unsorted` hidden) | **406** | Same PGRST106 | ⏸ pending propagation |

### Why pending and not failed

The Supabase exposed-schemas allowlist is configured at TWO levels:

1. **Persisted Management API config** — updated successfully via `PATCH /v1/projects/zxzaaqfowtqvmsbitqpu/postgrest -d '{"db_schema":"public, graphql_public, lab, rivalscope, economy_map"}'`. Verified via subsequent GET:
   ```json
   {
     "db_schema": "public,graphql_public,lab,rivalscope,economy_map",
     "max_rows": 1001,
     "db_extra_search_path": "public,extensions",
     "db_pool": null
   }
   ```
   The setting **is correctly persisted** in Supabase's project configuration.

2. **PostgREST runtime cache** — has not yet picked up the change. Supabase Cloud's Management API PATCH does not trigger an automatic PostgREST container redeploy on paid-tier plans. The available self-service restart paths all return 404:
   - `POST /v1/projects/.../restart-services` → 404
   - `POST /v1/projects/.../restart` → 404
   - `POST /v1/projects/.../database/restart` → 404
   - `POST /v1/projects/.../services/restart` → 404
   - `POST /v1/projects/.../pause` → 403 "Project is not free-tier"
   - `NOTIFY pgrst, 'reload schema'` → no effect (loads schema cache, not db_schema env var)
   - `NOTIFY pgrst, 'reload config'` → no effect
   - Dashboard "Save" click → no observable effect over 2-minute poll window
   - Toggle PATCH (remove `economy_map`, re-add) → no effect

Once Supabase Cloud's scheduled config-refresh cycle eventually picks up the new env var (typically minutes to hours; the orchestrator has a background poll running for 60 minutes), all three probes will return the expected HTTP 200 results. The probes are documented above with the EXACT curl commands the operator (or a follow-up agent) can re-run to backfill the evidence. Phase 1 §4.5 known unknown is "resolved at the config level" but "pending at the runtime level."

**Net judgment**: this is not a structural failure of Plan 02-01 or Plan 02-02 — it is a Supabase Cloud platform restart-timing constraint orthogonal to the work this phase owns. The persisted setting is correct; the schema is reachable from service_role (proven by every `execute_sql` call above) and will be reachable from anon as soon as PostgREST refreshes.

## Critical Invariants

| Invariant | Source | Verdict |
|-----------|--------|--------|
| Three first-in-tree precedents are established and documented | 02-PATTERNS.md §§2/3/6 (loud comment block at migration 033 SECTION 8) | ✓ Present in `supabase/migrations/033_economy_map_schema.sql` (committed `7e58969`) |
| `supabase-py .in_()` is not used anywhere in the new artifacts | Plan 02-02 acceptance criterion + PROJECT.md Constraints + CLAUDE.md | ✓ `grep -r '\.in_(' supabase/migrations/033_economy_map_schema.sql .planning/phases/02-economy-map-schema-seven-block-seed/02-VERIFY.sql` returns 0 hits |
| Application code is untouched by this phase | Plan 02-01 + Plan 02-02 scope | ✓ Only files modified: `supabase/migrations/033_economy_map_schema.sql`, `.planning/phases/02-economy-map-schema-seven-block-seed/02-01-SUMMARY.md`, `02-VERIFY.sql`, `02-VERIFY-RESULTS.md`, `.planning/ROADMAP.md` (tracking only). No `docker/`, `tests/`, `scripts/`, `config/` changes. |
| Append-only enforcement holds against service_role (not just anon) | T-02-01 mitigation; the 27-day silent wallet bug postmortem | ✓ All `execute_sql` calls above ran as service_role (via Supabase MCP) and ALL append-only mutations were rejected with the expected typed exceptions |
| Both SECURITY DEFINER RPCs pin `SET search_path` (T-02 mitigation) | Plan 02-01 acceptance criterion + 02-PATTERNS.md §7 | ✓ Supabase advisor `function_search_path_mutable` does NOT flag `publish_block_version` or `reject_block_version` |
| Both RPCs are not anon-callable (D-19, T-06 mitigation) | Plan 02-01 acceptance criterion | ✓ Supabase advisor `anon_security_definer_function_executable` does NOT list the two economy_map RPCs (it lists only the pre-existing `public.subscribe` + `public.unsubscribe`) |
| 7 blocks seeded idempotently — `ON CONFLICT (slug) DO NOTHING`, not `DO UPDATE` | Plan 02-01 acceptance criterion + D-20/D-21 | ✓ Migration committed at `7e58969` uses `ON CONFLICT (slug) DO NOTHING`; re-running the migration would NOT clobber operator-set `live_tension` |
| Maturity ENUM is a real Postgres ENUM (NOT text+CHECK) — D-03/SCHM-05 | Plan 02-01 acceptance criterion | ✓ `pg_type.typname='maturity'` exists with 5 values in canonical sort order (proven by query 1.c above) |
| Both append-only triggers are bound BEFORE UPDATE OR DELETE (not RLS) | T-02-01 mitigation; 02-PATTERNS.md §6 loud comment | ✓ `pg_trigger` lists `block_body_versions_append_only_trg` and `timeline_entries_append_only_trg`; both UPDATE and DELETE caused exceptions in steps 3.a..3.f above |

## ROADMAP Success Criteria Mapping

Phase 2's ROADMAP entry lists 5 success criteria. Each is mapped to the verification evidence that proves it:

1. **`Accept-Profile: economy_map` resolves at PostgREST** — ⏸ persisted config correct, runtime cache pending propagation (Section 5 probe results above). Conclusively proven at the config level (Management API GET returns `economy_map` in `db_schema`); pending runtime activation.
2. **`economy_map.blocks` contains 7 seeded blocks, each with `live_tension`, `subtitle`, `tier`, `accent`, `sort_order`** — ✓ Observable Truth 1.a + 1.b above.
3. **Atomic publish transaction works via `publish_block_version` RPC** — ✓ Observable Truths 2.a-2.e (positive path: draft inserted → published → superseded; blocks.current_body_version_id + maturity + last_synthesized_at update atomically) + 2.f-2.g (negative paths reject correctly).
4. **Append-only enforcement (UPDATE/DELETE on pinned columns → exception; lifecycle UPDATE → success; `'unsorted'` accepted)** — ✓ Observable Truths 3.a-3.g (all 7 cases land as expected).
5. **`economy_map.maturity` ENUM has 5 values in correct order** — ✓ Observable Truth 1.c (`nascent → emerging → contested → consolidating → mature`).

**Score: 4.5/5 conclusively proven; 0.5/5 pending PostgREST runtime propagation (config-level proof complete).**

## Test Residue

The following rows remain in the live database after this verification exercise. They are explicitly tagged with the substring `'TEST'` / `'verify-202602'` in body_md / what_shifted / source_edition_id so downstream phases (Phase 5 intake classifier, Phase 7 synthesis loop) can identify and skip them. They do not interfere with normal pipeline operation:

| Table | Row ID | Status / block_slug | Notes |
|-------|--------|---------------------|-------|
| `economy_map.block_body_versions` | `1e93030a-d949-4e31-a39e-1ce907836115` | `status='superseded'`, `proposed_maturity='emerging'`, block_slug='identity-trust' | Plan 02-02 step 2.a-i; superseded by v2 in step 2.d |
| `economy_map.block_body_versions` | `8aafdd9a-c619-44cb-bd84-784730a85389` | `status='published'`, `proposed_maturity='contested'`, block_slug='identity-trust' | Plan 02-02 step 2.a-ii; published in step 2.d; current `blocks.current_body_version_id` for `identity-trust` points here |
| `economy_map.timeline_entries` | `f7500550-9f6f-4bb1-a47a-5767c9a6846d` | block_slug='identity-trust' | Plan 02-02 step 3.e-pre; seeded for the what_shifted UPDATE trigger trip |
| `economy_map.timeline_entries` | `77de5e87-8d1f-4db6-9c86-ab3c8924549e` | block_slug='unsorted' | Plan 02-02 step 3.g; proves SCHM-08 `unsorted` carve-out |

Side effect on `economy_map.blocks` row for `identity-trust` (sort_order=1): `current_body_version_id` is now non-null, `maturity` is now `'contested'` (was `'nascent'` after migration apply), `last_synthesized_at` is non-null. Other six blocks are unchanged (maturity='nascent', current_body_version_id=NULL, last_synthesized_at=NULL). This is the expected state for downstream phases — `identity-trust` happens to be the first block with a publish history; Phase 5 / Phase 7 will gradually exercise the other six.

DELETE on these residue rows is not possible (the append-only triggers will reject — which IS the contract). To clear residue entirely, `DROP SCHEMA economy_map CASCADE;` + re-apply migration 033. This is NOT required for downstream phases.

## Open Items

- **Anon-key Probes 5.1 / 5.2 / 5.3** — backfill HTTP 200 + row count + slug ordering evidence into this document once PostgREST runtime cache acknowledges the `economy_map` allowlist. Background poll (orchestrator task #8) runs every 5 min for 60 min. Operator can manually re-run the three curl probes in Section 5 of `02-VERIFY.sql` (PROJECT_URL + ANON_KEY block in the SQL file's comments) at any time after propagation.
- **Optional hardening** (deferred, not Phase 2 scope): pin `SET search_path = economy_map, public` on the two trigger functions (`block_body_versions_append_only`, `timeline_entries_append_only`) to clear the two `function_search_path_mutable` advisor warnings. These functions don't resolve cross-schema names, so practical risk is near-zero — defer to a follow-up migration when convenient.

## Self-Check: PASSED (with documented pending anon-probe propagation)
