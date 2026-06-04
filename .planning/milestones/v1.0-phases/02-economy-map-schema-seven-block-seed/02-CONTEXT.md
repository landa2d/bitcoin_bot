# Phase 2: `economy_map` Schema + Seven-Block Seed - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Land the isolated `economy_map` Supabase schema with three tables (`blocks`, `block_body_versions`, `timeline_entries`), a maturity enum, structurally-enforced append-only semantics on content columns, and an atomic publish transaction exposed via two RPC functions. Seed the seven blocks with their structural fields. Add the schema to Supabase's exposed-schemas allowlist and prove the contract by exercising publish / reject / append-only-violation paths via SQL.

**Out:** rendering the data (Phase 4), classifying into blocks (Phase 5), invoking publish from Telegram (Phase 9), and authoring real `live_tension` editorial copy (Phase 10 — `/map-tension`).

</domain>

<decisions>
## Implementation Decisions

### Schema + access pattern (locked upstream — restated for downstream agents)
- **D-01:** Single Supabase migration (`033_economy_map_schema.sql`, the next sequential number after the current head `032_prepass_tracking_justification_and_staleness.sql`). One file lands everything: schema, tables, enum, triggers, functions, grants, seed.
- **D-02:** Schema name is `economy_map`. Access from the browser is `supabase-js .schema('economy_map').from(...)`, which sets `Accept-Profile: economy_map` on the underlying PostgREST request. Access from Python agents is direct PostgREST HTTP with the same header (NOT `supabase-py.in_()` — known silent-failure bug). No `public`-schema wrapper views.
- **D-03:** Maturity enum is a real Postgres `CREATE TYPE economy_map.maturity AS ENUM ('nascent','emerging','contested','consolidating','mature')` — typed, not text + CHECK. `blocks.maturity` and `block_body_versions.proposed_maturity` both use it.
- **D-04:** This migration **establishes** the in-tree precedent for the spec'd `eu_ai_act`-style isolation pattern. Per Phase 1 findings §4.4, no prior `eu_ai_act` migration exists in this repo; future agents reference `033_economy_map_schema.sql` as the canonical example for isolated-schema work.

### RLS posture
- **D-05:** Anon (browser) role gets `SELECT` on `economy_map.blocks` (all rows).
- **D-06:** Anon gets `SELECT` on `economy_map.block_body_versions` **only `WHERE status = 'published'`** — mirrors `migration 006_rls_policies.sql` `newsletters_anon_read` policy (`USING (status = 'published')`). Drafts and superseded versions are invisible to the browser.
- **D-07:** Anon gets `SELECT` on `economy_map.timeline_entries` **only `WHERE block_slug != 'unsorted'`** — low-confidence entries stay operator-only until triaged via `/map-assign` (Phase 10).
- **D-08:** `service_role` bypasses RLS (full access). The agents already use `SUPABASE_SERVICE_KEY` per migration 006 strategy comment; no change to that posture.
- **D-09:** No `public`-schema filtered views. The browser uses `Accept-Profile: economy_map` directly. Phase 4 reads via `sb.schema('economy_map')`.
- **Framing:** The publish gate is *structurally enforced, not application-enforced* — RLS is the structural guarantee that a draft never reaches the browser, even on application bugs.

### Append-only enforcement
- **D-10:** **`BEFORE UPDATE` and `BEFORE DELETE` triggers** on `block_body_versions` and `timeline_entries` — NOT RLS. Rationale: `service_role` bypasses RLS, and `service_role` (the pipeline) is the actor that produced the 27-day silent wallet bug. The append-only guarantee must hold against it.
- **D-11:** Pinned (immutable post-INSERT) columns:
  - `block_body_versions`: `body_md`, `synthesized_from_through`, `proposed_maturity`, `validator_report`, `block_slug`
  - `timeline_entries`: `block_slug`, `event_date`, `what_shifted`, `why_it_mattered`, `source_url`, `source_edition_id`, `tag_confidence`
- **D-12:** Lifecycle columns allowed to change (UPDATE permitted): `block_body_versions.status`, `block_body_versions.published_at`. Everything else on those two tables is pinned.
- **D-13:** `economy_map.blocks` is NOT append-only. `current_body_version_id`, `maturity`, `last_synthesized_at`, `live_tension` all UPDATE freely. The publish RPCs and `/map-tension` write here.
- **D-14:** Trigger function `raise_unless_only_lifecycle_changed()` (or similar) compares `OLD.*` vs `NEW.*` per column with `IS DISTINCT FROM` and raises a typed exception (e.g., `RAISE EXCEPTION 'block_body_versions.body_md is append-only (was %, now %)'`). The migration carries a loud comment block explaining the service_role-bypass rationale and cites the silent-failure postmortem.

### Atomic publish + reject API
- **D-15:** Two `SECURITY DEFINER` functions inside `economy_map`:
  - `economy_map.publish_block_version(p_version_id uuid) RETURNS void`
  - `economy_map.reject_block_version(p_version_id uuid) RETURNS void`
- **D-16:** Both functions are `LANGUAGE plpgsql SECURITY DEFINER`, called by Phase 9 (`/map-approve`, `/map-reject`) via `supabase.rpc('publish_block_version', { p_version_id: ... })`. This matches the existing `claim_agent_task` pattern in `migration 003_atomic_task_claiming.sql`.
- **D-17:** `publish_block_version` body atomically:
  1. `UPDATE economy_map.block_body_versions SET status='published', published_at=NOW() WHERE id=p_version_id AND status='draft' RETURNING block_slug, proposed_maturity INTO v_slug, v_maturity;`
  2. `IF v_slug IS NULL THEN RAISE EXCEPTION 'version not found or not in draft status'; END IF;`
  3. Supersede prior published: `UPDATE economy_map.block_body_versions SET status='superseded' WHERE block_slug=v_slug AND status='published' AND id<>p_version_id;`
  4. Point block at new + sync maturity + bump `last_synthesized_at`: `UPDATE economy_map.blocks SET current_body_version_id=p_version_id, maturity=v_maturity, last_synthesized_at=NOW() WHERE slug=v_slug;`
- **D-18:** `reject_block_version` body atomically:
  1. `UPDATE economy_map.block_body_versions SET status='superseded' WHERE id=p_version_id AND status='draft' RETURNING block_slug INTO v_slug;`
  2. `IF v_slug IS NULL THEN RAISE EXCEPTION 'version not found or not in draft status'; END IF;`
  3. (No further changes — timeline entries for this block remain unabsorbed; the next synthesis re-reads them.)
- **D-19:** Both functions: `REVOKE ALL ON FUNCTION ... FROM PUBLIC;` then `GRANT EXECUTE ON FUNCTION ... TO service_role;`. `anon` does NOT have EXECUTE — publish is service_role-only.

### Block seed
- **D-20:** Seven blocks INSERTed at the bottom of the migration, idempotent via `ON CONFLICT (slug) DO NOTHING`. Structural fields hardcoded in SQL: `slug`, `tier`, `title`, `subtitle`, `accent`, `sort_order`, `maturity` (always `'nascent'`).
- **D-21:** `live_tension` is seeded with the placeholder string `'TBD — set via /map-tension'`. The seven blocks become queryable immediately (satisfying ROADMAP success criterion 2 — every column has a value), but the editorial copy itself is operator-authored at runtime through the Phase 10 `/map-tension` command. **Framing:** *migration owns structure; command surface owns editorial copy.*
- **D-22:** No external YAML/JSON seed file. The structural fields are in SQL; editorial copy is in the DB (operator-managed).
- **D-23:** The seven blocks with their structural fields:

| `slug` | `tier` | `title` | `subtitle` (one-line hub caption) | `accent` | `sort_order` |
|--------|--------|---------|----------------------------------|----------|-------------|
| `identity-trust` | `substrate` | Identity & Trust | Who is the agent and why should we believe them? | `teal` | 1 |
| `memory-context` | `substrate` | Memory & Context | What does the agent remember, and what shapes its judgment? | `teal` | 2 |
| `payments-settlement` | `substrate` | Payments & Settlement | How do agents pay each other (and negotiate to do so)? | `teal` | 3 |
| `autonomy-control` | `behavior` | Autonomy & Control | Where does the agent get to decide, and where is it gated? | `purple` | 4 |
| `governance-accountability` | `behavior` | Governance & Accountability | Who is on the hook when an agent acts? | `purple` | 5 |
| `psychology-disposition` | `behavior` | Psychology & Disposition | What kind of mind is the agent, and how does it behave under pressure? | `coral` | 6 |
| `regulation-legal` | `frame` | Regulation & Legal | What does the legal frame around the agent economy look like? | `gray` | 7 |

   The planner / executor may refine the subtitle wording during implementation (these are first-pass captions) — the slugs, tiers, accents, and sort orders are locked.

### Exposed-schemas allowlist (Phase 1 known unknown §4.5 — resolved here)
- **D-24:** The Supabase exposed-schemas allowlist (Settings → API → Exposed schemas) MUST include `economy_map` before browser reads work. This is a one-time dashboard setting, NOT a SQL migration. Phase 2's plan includes a `[BLOCKING]` task to update the allowlist (preferably via the Supabase MCP tool if it supports schema-exposure config; otherwise a documented manual dashboard step) and a verification probe that confirms an anon `SELECT economy_map.blocks` over PostgREST returns rows. If the probe fails, the phase does not pass.

### Schema verification (success-criterion proof)
- **D-25:** A SQL exercise script (`.planning/phases/02-economy-map-schema-seven-block-seed/02-VERIFY.sql` or executed via `supabase.execute_sql` MCP) exercises and records expected outcomes for:
  1. Seven blocks queryable from `economy_map.blocks` (count + slug list).
  2. Atomic publish: insert a draft `block_body_versions` row → call `publish_block_version` → assert status flips, prior published superseded, `blocks.current_body_version_id` + `blocks.maturity` updated. Verify by SQL inspection.
  3. Append-only violation: attempt `UPDATE block_body_versions SET body_md = 'x' WHERE id = ...` → assert raises exception. Same for `timeline_entries.what_shifted`. Same for `DELETE`.
  4. Lifecycle column UPDATEs (status, published_at) succeed.
  5. RLS check via anon-key: drafts and `unsorted` entries do NOT appear in `SELECT *`; published bodies and named-block entries do.

   Results from this script are captured in `02-VERIFY-RESULTS.md` as the structured proof for ROADMAP success criteria 3, 4, and 5.

### Claude's Discretion
- Exact SQL formatting / column ordering in the migration — follow the existing `migrations/004_core_tables.sql` style (CREATE TABLE IF NOT EXISTS, indexes after table body, UNIQUE constraints inline).
- Naming of helper functions and triggers (e.g., `block_body_versions_append_only_trg`, `reject_content_update()` — pick what's readable).
- Whether to add additional indexes beyond the primary keys + foreign keys (e.g., `idx_timeline_entries_block_slug_event_date`). Add only if there's an obvious query path; don't over-index v1.
- Exact wording of the exception messages (just make them grep-friendly so verification can assert on them).
- Whether `live_tension` placeholder is the literal string `'TBD — set via /map-tension'` or some variant — pick something obviously non-final.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Build spec (source of truth)
- `.planning/docs/economy-map-build-spec-v2.md` §3 — Data contract: `blocks`, `block_body_versions`, `timeline_entries` table shapes; maturity enum (3.4).
- `.planning/docs/economy-map-build-spec-v2.md` §4 — Synthesis loop; explains *why* `validator_report` is jsonb and *why* `proposed_maturity` matters at publish time.
- `.planning/docs/economy-map-build-spec-v2.md` §5 — Intake; explains *why* `unsorted` is a valid block_slug.
- `.planning/docs/economy-map-build-spec-v2.md` §9 — Build order; confirms Phase 2's dependency-position.

### Project / milestone context
- `.planning/PROJECT.md` — Constraints (LLM-proxy mandate, schema isolation via PostgREST, autonomy boundary). Key Decisions table.
- `.planning/REQUIREMENTS.md` §Schema — SCHM-01..08 (formal requirements). §Out of Scope: in-place body mutation, mutating timeline history, deleting rejected drafts.
- `.planning/ROADMAP.md` §"Phase 2" — Five success criteria.

### Phase 1 outputs (immediately upstream)
- `.planning/phases/01-render-stack-diagnostic/01-FINDINGS.md` §4.1 — Anon-role read of non-public schema via Accept-Profile (Phase 2 validates).
- `.planning/phases/01-render-stack-diagnostic/01-FINDINGS.md` §4.4 — In-tree precedent for the `eu_ai_act` isolation pattern (Phase 2 establishes).
- `.planning/phases/01-render-stack-diagnostic/01-FINDINGS.md` §4.5 — Exposed-schemas allowlist (Phase 2 prerequisite; see D-24).

### Codebase analog files (read before writing new migration)
- `supabase/migrations/006_rls_policies.sql` — Canonical RLS posture: anon-read on published `newsletters` (mirrored in D-06). Note the strategy comment block.
- `supabase/migrations/003_atomic_task_claiming.sql` — Canonical `SECURITY DEFINER` + `LANGUAGE sql` atomic-mutation function pattern (mirrored in D-15..D-18).
- `supabase/migrations/004_core_tables.sql` — SQL style: `CREATE TABLE IF NOT EXISTS`, default values, indexes after table body.
- `supabase/migrations/013_unsubscribe_rpc.sql` — `CREATE OR REPLACE FUNCTION ... LANGUAGE plpgsql SECURITY DEFINER` minimal example.
- `supabase/migrations/015_agent_wallets.sql` — Reference for the "27-day silent wallet bug" postmortem domain referenced in D-10. (Note: this is the WALLET table; the bug pattern is referenced in PROJECT.md "Recent history that shapes design".)
- `supabase/migrations/032_prepass_tracking_justification_and_staleness.sql` — Most recent migration (next number is `033`).

### Existing client patterns
- `docker/web/site/app.js` — `sb = window.supabase.createClient(...)` global client; current schema queries use the public schema. Phase 2 doesn't modify this file — Phase 4 will add `.schema('economy_map')` calls.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Migration file format and idiomatic ordering** — comment header → CREATE TYPE / CREATE TABLE IF NOT EXISTS → indexes → triggers/functions → grants → seed data. Mirror `004_core_tables.sql` + `003_atomic_task_claiming.sql`.
- **`SECURITY DEFINER` RPC pattern** — `claim_agent_task` / `unsubscribe` show the exact shape. Reuse verbatim for `publish_block_version` and `reject_block_version`.
- **RLS strategy comment** — `006_rls_policies.sql` opens with a block explaining the `service_role` bypass strategy. The Phase 2 migration's append-only trigger needs an equivalent block explaining why triggers (not RLS) enforce immutability against `service_role` (see D-10 / D-14).

### Established Patterns
- **Schema isolation via `Accept-Profile`** — the build spec references `eu_ai_act` as precedent, but Phase 1 §4.4 confirmed there is no in-tree `eu_ai_act` migration. Phase 2's migration becomes the first concrete instance.
- **Append-only via trigger** — no in-tree precedent yet; this is the first table in the repo to enforce immutability at the database level. The pattern is straightforward but new for this codebase, so the migration's loud comment block matters: it documents the design rationale for the next developer who'd otherwise wonder why RLS isn't enough.
- **Idempotent seed via `ON CONFLICT DO NOTHING`** — matches the `source_posts` pattern in `004_core_tables.sql` (`UNIQUE (source, source_id)` enforces idempotency on re-runs).

### Integration Points
- **No application code changes in Phase 2** — only the migration file, the SQL verification script, and the verification-results doc. No edits to `docker/web/site/app.js`, no edits to processor / gato_brain / newsletter. Phase 5 (intake) is the first Phase to write Python that touches `economy_map`; Phase 4 is the first Phase to read from it from the browser. Phase 2 stays inside the database boundary.
- **Supabase MCP `apply_migration` / `execute_sql`** is the tool path for running the migration and the verification script. The Supabase project ref is `zxzaaqfowtqvmsbitqpu` (per `CLAUDE.md`).

</code_context>

<specifics>
## Specific Ideas

- **Migration filename:** `supabase/migrations/033_economy_map_schema.sql` (next sequential after `032`).
- **Loud comment for append-only trigger:** the migration must include a comment block before the trigger that explicitly says: "intentional: content immutability must hold against service_role; see silent-failure postmortem (27-day wallet bug pattern documented in `.planning/PROJECT.md` 'Recent history that shapes design')." Future agents WILL try to "simplify" this to an RLS policy if the rationale isn't loud.
- **`live_tension` placeholder string** — pick something obviously non-final so it's grep-able in production (e.g., `'TBD — set via /map-tension'`). Phase 10's `/map-tension` is the only path to set the real copy; this is documented in D-21.
- **Exposed-schemas allowlist update** — the planner should investigate whether Supabase MCP's project-config tools expose this setting. If yes, the plan's allowlist task can be autonomous. If no, the task is `autonomous: false` with a clear manual-step description (Dashboard → Settings → API → Exposed schemas → add `economy_map` → save).

</specifics>

<deferred>
## Deferred Ideas

- **Per-block synthesis thresholds (`TUNE-01..03`)** — already in REQUIREMENTS.md "v2" section. Out of v1 scope; Phase 2 ships global thresholds (handled by Phase 7, not Phase 2).
- **`negotiation-coordination` as its own block** — already deferred (PROJECT.md, REQUIREMENTS.md NEGB-01/02). Negotiation stays a section *inside* `payments-settlement` for v1.
- **Supabase Realtime subscriptions on `timeline_entries`** — possible re-render trigger for Phase 4, mentioned in Phase 1 §5. Phase 2 does not need to enable realtime; Phase 4 owns that choice.
- **Column-level GRANT revoke as defense-in-depth** — discussed as a hybrid layer over the trigger and rejected (D-10): the trigger alone is the source of truth. If a future migration adds new roles, the trigger continues to bind them; per-column GRANTs would need maintenance.
- **Foreign key on `timeline_entries.source_edition_id` to `public.newsletters(id)`** — the build spec keeps it as `text` for cross-schema flexibility. Not adding a strict FK in v1; reconsider if traceability holes appear in production.
- **Custom Postgres exceptions / SQLSTATEs for trigger raises** — using generic `RAISE EXCEPTION` is fine; bespoke SQLSTATEs are a v2 concern if downstream wants to programmatically distinguish "append-only violation" from other 22000-class errors.

</deferred>

---

*Phase: 02-economy-map-schema-seven-block-seed*
*Context gathered: 2026-05-26*
