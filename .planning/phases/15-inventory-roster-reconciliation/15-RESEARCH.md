# Phase 15: Inventory & Roster Reconciliation - Research

**Researched:** 2026-06-08
**Domain:** Postgres schema contract (Supabase `economy_map`), append-only triggers, SECURITY DEFINER publish RPC, RLS, static SPA serve path (`app.js`). No-write documentation + reconciliation-plan phase.
**Confidence:** HIGH (every claim below is read directly from in-tree migration SQL and `app.js`; see provenance tags)

> **DB-probe disclosure:** `config/.env` contains Supabase credentials, but this phase is **no-write** and the migration files are the declared authoritative source (CONTEXT D-05/D-06; ROADMAP SC#1 "documented from the live schema"). All facts below are `[VERIFIED: migration SQL]` or `[VERIFIED: app.js]` — read from the canonical migration/serve files in this repo, which are the source the schema was applied from. No live `SELECT` was issued. Per the orchestrator instruction, the migration SQL is treated as authoritative and research proceeds without blocking. Any divergence between these files and the deployed DB would be a deployment drift bug, out of scope for this read-only phase — but Phase 16's loader will fail loud against the live enum/CHECK if drift exists, which is the correct backstop.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01 (maturity remap):** Live enum is `nascent, emerging, contested, consolidating, mature` (migration 033 §3, app.js `MATURITY_STAGE`). Docs' `building` is **not a member**. Resolution: explicit operator-approved remap `building → emerging`, applied **at load time (Phase 16)**, so the three substrate blocks (`identity-trust`, `memory-context`, `payments-settlement`) load with `proposed_maturity = 'emerging'` (stage-2 pill). **No `ALTER TYPE`, no app.js change.** `contested`/`nascent` pass through unchanged.
- **D-02 (regulation-legal + tier model):** Keep `regulation-legal` (tier `frame`, seeded sort_order 7) as a **deferred frame slot** — stays unpublished / body-less, renders as a DEFERRED card. **Tier model stays at 3** (`substrate`/`behavior`/`frame`). No content/publish write to this row — only the structural sort_order bump (D-03) touches it.
- **D-03 (negotiation-coordination):** Docs add `negotiation-coordination` (tier `behavior`, maturity `nascent`, order 5); absent from the live seed. Disposition: **first-publish as a new behavior block** at `sort_order 5`, and **reshuffle** `governance-accountability` → 6, `psychology-disposition` → 7. **Collision:** `regulation-legal` seeded at 7 now collides → bump to **8** (structural sort_order-only update). `blocks.sort_order` is plain/UPDATE-able (append-only triggers guard `block_body_versions` + `timeline_entries`, **not** `blocks`).
- **D-04 (hub serve path):** Hub `agent-economy` (`type: hub`, **no tier**) cannot be a `blocks` row (`tier NOT NULL CHECK`). Currently NOT DB-served — `#/map` renders the hardcoded `HUB_STORYLINE` constant. Resolution: give the hub a DB-served home + markdown render, **gated by the same `publish_block_version` RPC**. Reuse the existing `marked.parse` block-body path (app.js:586). Net-new work: (1) a *minimal* schema accommodation so the hub body can live in `block_body_versions`, (2) a small `renderHub` change to fetch + `marked.parse` the hub's published body. **Exact DDL delegated to researcher** (recommended below). Existing XSS-via-markdown disposition (T-04-03-01, operator publish gate is the compensating control) carries over unchanged.
- **D-05:** Phase 15 produces a contract doc + reconciliation plan only — **no `economy_map` writes**; plan gated on operator approval before Phase 16.
- **D-06:** All `economy_map` access via direct PostgREST + `Accept-Profile` (never supabase-py `.in_()`); corrections via canonical-body-rewrite (never raw UPDATE on append-only columns); fail-loud on missing fields; branch + `/diff` + web-only scoped `agentpulse-web` rebuild — no pipeline / proxy / agent-service changes.

### Claude's Discretion
- The **exact** hub schema accommodation (relaxed tier CHECK + sentinel tier vs nullable tier vs dedicated hub home) — D-04 fixes the *path*, not the DDL. Recommendation pinned in §D-04 below.
- The concrete sort_order renumbering mechanic (per D-03), provided the result is collision-free and frame sorts after behavior. Mapping pinned in §ROST-01 below.

### Deferred Ideas (OUT OF SCOPE)
- **Phase 17 (HUB-01) presentation:** cards vs prose links, hub prose above grid, distinct `nascent` visual treatment — presentation decisions for Phase 17, not 15.
- **Evolution timeline content:** bodies publish with possibly-empty timelines; intake fills weekly. No manual timeline authoring this milestone.
- **EU AI Act tracker → `regulation-legal` body:** the deferred frame slot gets fed by a future milestone (EUAI-01/02), not now.
- **7 pending v1.0 backend todos:** none overlap the `economy_map` content/roster domain; parked in backlog.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INV-01 | Confirm the live `economy_map` storage + serve contract (block data contract, append-only trigger behavior, atomic publish RPC) from the live schema, not assumed. | §INV-01 below fully documents every column/constraint, the two append-only triggers and exactly which tables they guard, the `publish_block_version` RPC signature + atomic 4-step behavior (033 + 038/039 watermark refinement), RLS anon visibility, and the hub serve path. |
| INV-02 | Verify the maturity enum against the three doc values (`building`/`contested`/`nascent`); surface and resolve any mismatch explicitly. | §INV-02 below pins the 5 enum members verbatim from 033 §3, confirms `building` is NOT a member, confirms `MATURITY_STAGE` maps `emerging→2` and unknown→stage 1, and validates the D-01 `building→emerging` remap end-to-end (load-time + pill render). |
| ROST-01 | Resolve the block-roster diff per slug with an explicit disposition before load. | §ROST-01 below documents the seed facts (which blocks seeded, tiers, sort_orders, `ON CONFLICT (slug) DO NOTHING`), cross-checks the 00-07 doc frontmatters against the CONTEXT reconciled roster (flags the one expected divergence), and gives the collision-free before/after sort_order map for the D-03 reshuffle. |
</phase_requirements>

## Summary

This is a **no-write documentation + reconciliation-plan phase**. The deliverable is (a) the documented live `economy_map` contract and (b) a per-slug roster disposition presented for operator approval before Phase 16 writes anything. All four reconciliation calls (D-01..D-04) are pre-locked in CONTEXT; this research **verifies each against the authoritative migration SQL and `app.js`** and pins the two delegated specifics (D-04 hub DDL, D-03 sort_order mechanic).

Every CONTEXT claim verified cleanly against the live SQL with **one expected, benign divergence to flag**: ROADMAP SC#2 / Phase 17 SC#2 still describe the preview pills as showing "`building`/`contested`/`nascent`", but D-01 remaps `building→emerging` at load time, so the substrate pills will actually render **`emerging`** (stage-2). This is the *intended* result of D-01 — the ROADMAP wording predates the reconciliation decision. The planner should note that Phase 17's verification text must read `emerging` for the three substrate blocks, not `building`.

**Primary recommendation:** For D-04, adopt the **minimal "relax the tier CHECK + hub sentinel tier" accommodation** (Option A below) — it admits a single `('hub')`-tier `blocks` row for slug `agent-economy`, lets the hub body live in `block_body_versions` under the existing FK, routes through `publish_block_version` **unchanged**, and renders via `marked.parse` **unchanged**. It is the smallest DDL that satisfies D-04's "reuse RPC + marked.parse" constraint, and the new sentinel tier is naturally excluded from the three tier grids by `renderHub`'s existing `tier === 'substrate'|'behavior'|'frame'` filters (no card duplication).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Block/hub data storage + immutability invariant | Database / Storage (Postgres `economy_map`) | — | Append-only enforced by triggers (must bind service_role, which bypasses RLS); tier/maturity by CHECK/ENUM. Structural, not app-layer (memory: structural-over-application). |
| Publish gate (draft→published, atomic) | Database / Storage (`publish_block_version` SECURITY DEFINER RPC) | — | Single atomic transaction; the spine's "publishing is gated" lives here. |
| Read boundary (what anon sees) | Database / Storage (RLS policies) | — | anon sees only `status='published'` bodies + non-`unsorted` timeline entries. |
| Block/hub HTML render | Browser / Client (`app.js` SPA via Caddy) | CDN / Static (Caddy serve) | Static SPA reads `economy_map` over PostgREST with `Accept-Profile`; markdown→HTML via `marked.parse` client-side. |
| Maturity stage mapping (enum→pill fill) | Browser / Client (`MATURITY_STAGE` in `app.js`) | — | Pure presentation lookup; unknown enum → stage 1. |
| Roster reconciliation decision | (this phase — documentation) | — | No tier owns it at runtime; it is an operator-approved plan, not code. |

## Standard Stack

This phase installs **no packages** (read-only documentation). The relevant existing stack:

### Core (already in tree)
| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| Supabase Postgres | project `zxzaaqfowtqvmsbitqpu` | `economy_map` schema home (blocks / block_body_versions / timeline_entries) | The shared store; schema-isolated per 033 (D-04 precedent). `[VERIFIED: CLAUDE.md + 033]` |
| PostgREST (`Accept-Profile: economy_map`) | bundled w/ Supabase | anon read path; supabase-js `.schema('economy_map')` sets the header | D-06 mandates this path; `.in_()` silently fails on isolated schema (memory). `[VERIFIED: app.js:420,518]` |
| `marked` (client-side) | loaded in `app.js` | markdown → HTML for block + newsletter bodies | Already the live render path (app.js:250, 586). D-04 reuses it verbatim. `[VERIFIED: app.js]` |
| Caddy 2-alpine | — | static serve of `docker/web/site` | Existing `agentpulse-web` service; web-only scoped rebuild per D-06. `[VERIFIED: CLAUDE.md]` |

**Installation:** None. No `npm install` / `pip install` for this phase.

## Package Legitimacy Audit

**Not applicable** — this phase installs no external packages. It documents the live schema and produces a reconciliation plan; all referenced components (Postgres, PostgREST, `marked`, Caddy) are pre-existing in the deployed system. No slopcheck / registry verification required.

## INV-01 — Live storage + serve contract

> All facts `[VERIFIED: migration SQL]` (033, 038, 039, 040, 041) and `[VERIFIED: app.js]` unless tagged otherwise.

### `economy_map.blocks` (033 §4, lines 65–81)

| Column | Type | Constraint | Notes |
|--------|------|-----------|-------|
| `id` | UUID | PK, `DEFAULT gen_random_uuid()` | |
| `slug` | TEXT | **NOT NULL UNIQUE** | the seven slugs; FK target for `block_body_versions.block_slug` |
| `tier` | TEXT | **NOT NULL `CHECK (tier IN ('substrate','behavior','frame'))`** | **Confirmed: exactly 3 tiers.** No `'hub'`, no NULL. This is the constraint D-04 must accommodate. |
| `title` | TEXT | NOT NULL | |
| `subtitle` | TEXT | NOT NULL | one-line hub caption |
| `accent` | TEXT | NOT NULL `CHECK (accent IN ('teal','purple','coral','gray'))` | render accent (Phase 13 dropped per-tier accent attr but column persists) |
| `sort_order` | INTEGER | **NOT NULL UNIQUE** | **Plain UPDATE-able column** — no append-only trigger on `blocks`. The `UNIQUE` constraint is what forces the D-03 reshuffle to be collision-free. |
| `live_tension` | TEXT | NOT NULL | placeholder at seed (`'TBD — set via /map-tension'`); mutated only via Phase 10 `/map-tension` |
| `maturity` | `economy_map.maturity` (ENUM) | NOT NULL `DEFAULT 'nascent'` | synced by `publish_block_version` from the published version's `proposed_maturity` |
| `current_body_version_id` | UUID | FK → `block_body_versions(id) ON DELETE SET NULL` (added 033 §6) | nullable; points at the live published body |
| `last_synthesized_at` | TIMESTAMPTZ | nullable | watermark; advanced by publish RPC (038/039) |
| `created_at` | TIMESTAMPTZ | NOT NULL `DEFAULT NOW()` | |

Indexes: `idx_blocks_tier`, `idx_blocks_sort_order`.

**KEY CONFIRMATION for D-03:** `blocks.sort_order` is a plain column on a table **with no append-only trigger** (the triggers in 033 §8 are on `block_body_versions` and `timeline_entries` only). The `sort_order` reshuffle and the regulation `7→8` bump are therefore **permitted plain `UPDATE`s** — confirmed against 033 §8 trigger definitions (lines 208–211, 250–253). `[VERIFIED: migration SQL 033 §4, §8]`

### `economy_map.block_body_versions` (033 §5, lines 94–110; +041)

| Column | Type | Constraint | Append-only? |
|--------|------|-----------|--------------|
| `id` | UUID | PK | — |
| `block_slug` | TEXT | NOT NULL **FK → `blocks(slug)` `ON DELETE RESTRICT`** | **pinned** (immutable post-insert) |
| `body_md` | TEXT | NOT NULL | **pinned** |
| `status` | TEXT | NOT NULL `DEFAULT 'draft'` **`CHECK (status IN ('draft','published','superseded'))`** | **lifecycle (mutable by RPC)** |
| `proposed_maturity` | `economy_map.maturity` | **NOT NULL** | **pinned** |
| `synthesized_from_through` | TIMESTAMPTZ | nullable | **pinned** (watermark upper bound; read by publish RPC) |
| `validator_report` | JSONB | NOT NULL `DEFAULT '{}'::jsonb` | **pinned** |
| `published_at` | TIMESTAMPTZ | nullable | **lifecycle (mutable by RPC)** |
| `created_at` | TIMESTAMPTZ | NOT NULL `DEFAULT NOW()` | — |

**Status enum confirmed: `draft`, `published`, `superseded`** (TEXT + CHECK, not a Postgres ENUM). `[VERIFIED: 033:98-99]`

**`proposed_maturity` is pinned (append-only) and NOT NULL** — so the load-time D-01 remap must produce a valid enum member at INSERT time; the trigger forbids any later UPDATE of it. `[VERIFIED: 033:100, 194-196]`

**UNIQUE open-draft (migration 041):** `CREATE UNIQUE INDEX uq_block_body_versions_one_open_draft ON block_body_versions (block_slug) WHERE status = 'draft'` — **at most one `draft` row per `block_slug` at a time.** This is the structural backstop for the check-then-act race; the processor catches the resulting `23505` as a logged benign skip. Relevant to Phase 16/18 loading the hub + new negotiation block: each slug may hold only one open draft. `[VERIFIED: 041:20-21]`

Indexes: `idx_block_body_versions_slug_status` (composite), `idx_block_body_versions_status WHERE status='draft'` (partial; the non-unique analog 041 upgrades).

### `economy_map.timeline_entries` (033 §7, lines 148–161)

Fully append-only (every column pinned — no lifecycle columns). `block_slug` is intentionally **NOT a FK** because `'unsorted'` is a valid value (low-confidence classifier output awaiting `/map-assign`). Out of Phase 15's write scope but documented for the contract: anon RLS hides `block_slug = 'unsorted'`. `[VERIFIED: 033:148-161, 372-376]`

### Append-only triggers (033 §8) — which tables they guard

| Trigger | Table | Fires on | Behavior |
|---------|-------|----------|----------|
| `block_body_versions_append_only_trg` | `economy_map.block_body_versions` | `BEFORE UPDATE OR DELETE` | DELETE always raises; UPDATE raises if any of `body_md / synthesized_from_through / proposed_maturity / validator_report / block_slug` change. **`status` and `published_at` ARE allowed to change** (lifecycle columns) — this is what lets `publish_block_version` flip draft→published. |
| `timeline_entries_append_only_trg` | `economy_map.timeline_entries` | `BEFORE UPDATE OR DELETE` | DELETE always raises; UPDATE raises on any column change (fully immutable). |

**No trigger on `economy_map.blocks`.** Confirmed by absence — only the two `CREATE TRIGGER` statements above exist in 033, both naming the content tables. This is the load-bearing fact for D-03. `[VERIFIED: 033 §8, lines 177-253]`

**Why triggers, not RLS (033 §8 comment block):** immutability must hold **against service_role**, which bypasses RLS by design. The agents use `SUPABASE_SERVICE_KEY`. RLS cannot bind service_role; a BEFORE UPDATE/DELETE trigger can. (Matches the memory: structural-over-application; service_role is the historical failure actor — "the 27-day silent wallet bug ran as service_role.") `[VERIFIED: 033:166-175]`

### `publish_block_version(p_version_id uuid)` RPC — signature + atomic behavior

**Current authoritative body: migration 039** (full re-emit; 038 introduced the watermark, 039 added the NULL-guard COALESCE; 033 was the original). Signature stable across all three:

```
economy_map.publish_block_version(p_version_id uuid) RETURNS void
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = economy_map, public
```

Grants: `REVOKE ALL ... FROM PUBLIC; GRANT EXECUTE ... TO service_role` — **service_role-only**. `[VERIFIED: 039:81-82]`

Atomic 4-step body (single transaction):
1. **`UPDATE block_body_versions SET status='published', published_at=NOW() WHERE id=p_version_id AND status='draft' RETURNING block_slug, proposed_maturity, synthesized_from_through`** — the `AND status='draft'` + `RETURNING` is the single-winner property: concurrent publish-races lose (empty RETURNING). `[VERIFIED: 039:50-55]`
2. If `v_slug IS NULL` → `RAISE EXCEPTION 'version % not found or not in draft status'` (typed fail-loud). `[VERIFIED: 039:58-59]`
3. **`UPDATE block_body_versions SET status='superseded' WHERE block_slug=v_slug AND status='published' AND id<>p_version_id`** — supersedes the prior published version for that slug. `[VERIFIED: 039:64-67]`
4. **`UPDATE blocks SET current_body_version_id=p_version_id, maturity=v_maturity, last_synthesized_at=COALESCE(v_synthesized_from_through, last_synthesized_at) WHERE slug=v_slug`** — points the block at the new version, syncs maturity from the version's `proposed_maturity`, and advances the watermark to the draft's pinned `synthesized_from_through` (039's COALESCE leaves it unchanged when the draft watermark is NULL — the cold-start sentinel). `[VERIFIED: 039:73-77]`

**Atomicity:** all four UPDATEs are one PL/pgSQL function call = one transaction; either all commit or all roll back. The append-only trigger is **not** implicated because Step 1/3 only mutate the lifecycle columns (`status`, `published_at`) and Step 4 writes a *different* table (`blocks`, untriggered). `[VERIFIED: 038:17-21, 039:24-28]`

`reject_block_version(p_version_id uuid)` (033 §10): SECURITY DEFINER, service_role-only; flips the draft → `superseded` and stops (timeline entries stay unabsorbed for the next synthesis pass). `[VERIFIED: 033:319-342]`

### RLS — what anon sees (033 §11, lines 356–386)

| Table | anon SELECT policy | Effect |
|-------|--------------------|--------|
| `blocks` | `USING (true)` | anon sees **all** block rows (including deferred / body-less). |
| `block_body_versions` | `USING (status = 'published')` | anon sees **only published bodies** — drafts/superseded invisible. This is why Phase 16's unpublished load is invisible to visitors until Phase 18 runs the RPC. |
| `timeline_entries` | `USING (block_slug <> 'unsorted')` | anon sees all classified entries; `'unsorted'` hidden. |

Plus table-level `GRANT SELECT ... TO anon` (PostgREST needs BOTH an RLS pass AND a grant) and `GRANT USAGE ON SCHEMA economy_map TO anon` (033 §2, §12). service_role gets `GRANT ALL` and bypasses RLS. `[VERIFIED: 033:356-389]`

### Hub serve path (`app.js`) — current behavior

- `HUB_STORYLINE` (app.js:32) is a **hardcoded JS constant** (`'Synthesis with editorial integrity. Eight blocks, seven shipped, one deferred…'`), rendered **`escapeHtml`'d** (plain text, NOT markdown) inside `renderHub` at app.js:496 (`'<div class="hub-storyline">' + escapeHtml(HUB_STORYLINE) + '</div>'`). **The hub is NOT DB-served today.** `[VERIFIED: app.js:32, 496]`
- `loadHub` / `renderHub` (app.js:~413–503): one query — `sb.schema('economy_map').from('blocks').select('slug,title,subtitle,accent,tier,sort_order,maturity,live_tension,current_body_version_id,last_synthesized_at').order('sort_order', {ascending:true})`. Then groups by `tier` into `substrateBlocks / behaviorBlocks / frameBlocks` (filter `b.tier === '...'`), and emits three `tierSection(...)` grids under the `hub-storyline`. **Any row whose tier is not one of the three is silently excluded from all grids** — relevant to D-04. `[VERIFIED: app.js:420-499]`
- Block body render (`renderBlock`, app.js:~505–604): fetches `block_body_versions.body_md` via `current_body_version_id` (D-17: **no** defensive `.eq('status','published')` — RLS already gates anon to published), then `marked.parse(bodyMd)` at **app.js:586** (the only markdown-execution path on a block page). Body hidden when null/missing (D-10). `[VERIFIED: app.js:535-586]`

## INV-02 — Maturity ENUM verification

### Exact ENUM members (033 §3, lines 46–52)

```sql
CREATE TYPE economy_map.maturity AS ENUM (
    'nascent', 'emerging', 'contested', 'consolidating', 'mature'
);
```

**Confirmed members (ordered): `nascent`, `emerging`, `contested`, `consolidating`, `mature`.** `[VERIFIED: 033:46-52]`

**`'building'` is NOT a member.** A `block_body_versions` INSERT with `proposed_maturity = 'building'` is rejected by the enum type at write time (loud `invalid input value for enum`). This is the structural backstop the D-01 remap front-runs. `[VERIFIED: 033:46-52, 033:100]`

### `MATURITY_STAGE` mapping (app.js:38) and unknown handling

```js
const MATURITY_STAGE = { nascent: 1, emerging: 2, contested: 3, consolidating: 4, mature: 5 };
```
- **`emerging → 2`** — confirmed. `[VERIFIED: app.js:38]`
- `renderMaturityPill` (app.js:391–400): `var stage = deferred ? 0 : (MATURITY_STAGE[b.maturity] || 1)`. **Unknown / missing maturity → stage 1** (the `|| 1` fallback). So a stray `'building'` that somehow reached the pill would mis-fill as stage 1, silently — exactly the failure D-01 prevents. Deferred (body-less) blocks force `data-stage="0"`. `[VERIFIED: app.js:391-400]`

### D-01 remap validation (`building → emerging`)

End-to-end the remap is correct and requires **no schema and no app.js change**:
1. **Load time (Phase 16):** the three substrate frontmatters carry `maturity: building`; the loader substitutes `emerging` before the `block_body_versions` INSERT, so `proposed_maturity = 'emerging'` (a valid enum member — passes the enum + the NOT-NULL pinned constraint). `[VERIFIED: 033:46-52, 033:100]`
2. **Publish (Phase 18):** `publish_block_version` Step 4 syncs `blocks.maturity = proposed_maturity = 'emerging'`. `[VERIFIED: 039:73-76]`
3. **Render:** `MATURITY_STAGE['emerging'] = 2` → stage-2 pill, correct. `[VERIFIED: app.js:38]`
4. `contested` and `nascent` are already members and map to 3 / 1 respectively — pass through unchanged. `[VERIFIED: app.js:38, 033:46-52]`

**INV-02 satisfied:** the mismatch (`building` ∉ enum) is surfaced here and resolved with an explicit operator-approved remap, never silently downstream. The `MATURITY_STAGE` unknown→1 fallback is the silent-failure mode that the remap removes.

## ROST-01 — Roster diff resolution

### Live seed facts (033 §13, lines 402–415)

`INSERT INTO economy_map.blocks (...) VALUES (...) ON CONFLICT (slug) DO NOTHING` — **idempotency posture is `DO NOTHING`** (not `DO UPDATE`), to avoid clobbering operator-set `live_tension` on replay. Adding `negotiation-coordination` is therefore a *new structural row*, not a re-seed (no conflict to swallow). `[VERIFIED: 033:402-415]`

Seven seeded blocks (slug / tier / accent / **seeded sort_order**):

| sort_order (seed) | slug | tier | accent | maturity (seed) |
|---|---|---|---|---|
| 1 | `identity-trust` | substrate | teal | nascent |
| 2 | `memory-context` | substrate | teal | nascent |
| 3 | `payments-settlement` | substrate | teal | nascent |
| 4 | `autonomy-control` | behavior | purple | nascent |
| 5 | `governance-accountability` | behavior | purple | nascent |
| 6 | `psychology-disposition` | behavior | coral | nascent |
| **7** | **`regulation-legal`** | **frame** | **gray** | **nascent** |

**Confirmed: `regulation-legal` IS seeded — tier `frame`, sort_order 7, accent gray.** `[VERIFIED: 033:414]`
**Confirmed: `negotiation-coordination` is NOT in the seed** (no VALUES row for it). `[VERIFIED: 033:402-415]`
All seven seed with `maturity DEFAULT 'nascent'` and `live_tension = 'TBD — set via /map-tension'`. (Note: the seed `maturity` is `nascent` for all; the *editorial* maturity comes later from the published version's `proposed_maturity`, sourced from the doc frontmatter — see the doc-vs-context check below.)

### Doc frontmatter (00-07) vs CONTEXT §specifics reconciled roster

| order | slug | doc tier | doc maturity | CONTEXT roster tier | CONTEXT loaded maturity | Match? |
|---|---|---|---|---|---|---|
| 0 | `agent-economy` (hub) | (none — `type: hub`) | (none) | — (DB-served home, D-04) | — | ✅ hub has no tier/maturity, as expected |
| 1 | `identity-trust` | substrate | **building** | substrate | `emerging` (was building) | ✅ (D-01 remap) |
| 2 | `memory-context` | substrate | **building** | substrate | `emerging` (was building) | ✅ (D-01 remap) |
| 3 | `payments-settlement` | substrate | **building** | substrate | `emerging` (was building) | ✅ (D-01 remap) |
| 4 | `autonomy-control` | behavior | contested | behavior | contested | ✅ |
| 5 | `negotiation-coordination` | behavior | nascent | behavior | nascent | ✅ (new block, D-03) |
| 6 | `governance-accountability` | behavior | contested | behavior | contested | ✅ |
| 7 | `psychology-disposition` | behavior | nascent | behavior | nascent | ✅ |
| 8 | `regulation-legal` | (no doc — omitted) | — | frame | (unchanged / body-less) | ✅ (kept deferred, D-02) |

**Doc frontmatter `order` already equals the CONTEXT target order** (negotiation=5, governance=6, psychology=7). The docs are authored *in target state*; the reconciliation reshuffles the **live seed** (governance 5→6, psychology 6→7, +negotiation at 5) to match the docs. No frontmatter mismatch with the CONTEXT roster — they are consistent.

**Flags (divergences worth the planner's attention):**
- **F-1 (expected, benign):** doc frontmatter `maturity: building` on slugs 1/2/3 vs CONTEXT loaded `emerging`. This is the *intended* D-01 remap, not an error — the loader (Phase 16) is the single point that substitutes `building→emerging`. The frontmatter is left as-is (CONTEXT canonical_refs says frontmatter is the metadata source of truth and is "remapped per D-01"). The planner must ensure the Phase 16 loader does this substitution, not a doc edit.
- **F-2 (ROADMAP wording lag — flag to planner):** ROADMAP SC#2 (Phase 15) and Phase 17 SC#2 still say preview pills show "`building`/`contested`/`nascent`". After D-01 the three substrate pills render **`emerging`** (stage 2), not `building`. The reconciliation correctly resolves `building`; the ROADMAP/Phase-17 verification text should read `emerging` for the substrate trio. (This is a documentation-consistency note, not a code defect — D-01 is the authoritative resolution.)
- **F-3 (no doc for `regulation-legal`):** intentional per D-02 — it stays a deferred, body-less frame card. No `08-regulation-legal.md` is expected this milestone (EU AI Act tracker feeds it later).

### D-03 reshuffle — before/after sort_order map (collision-free proof)

`blocks.sort_order` is `INTEGER NOT NULL UNIQUE`. The target state inserts `negotiation-coordination` at 5 and shifts everything behind it up by one.

| slug | before (live seed) | after (target) | operation |
|---|---|---|---|
| `identity-trust` | 1 | 1 | unchanged |
| `memory-context` | 2 | 2 | unchanged |
| `payments-settlement` | 3 | 3 | unchanged |
| `autonomy-control` | 4 | 4 | unchanged |
| `negotiation-coordination` | (absent) | **5** | **INSERT** (new behavior block, D-03) |
| `governance-accountability` | 5 | **6** | UPDATE +1 |
| `psychology-disposition` | 6 | **7** | UPDATE +1 |
| `regulation-legal` | 7 | **8** | UPDATE +1 (frame bump, D-03; stays body-less per D-02) |

**Final ordered set: {1,2,3,4,5,6,7,8}** — 8 distinct values, no gaps, no duplicates. **Collision-free.** Frame (`regulation-legal`=8) sorts strictly after the highest behavior (`psychology-disposition`=7). ✅ `[VERIFIED: target derived from 033 seed + CONTEXT D-03]`

**Collision-avoidance execution note (for the planner, not a decision):** because `sort_order` is `UNIQUE`, the three `+1` UPDATEs must not transiently collide with an existing value. The seed currently occupies 1–7; inserting `negotiation` at 5 while 5/6/7 are taken requires either (a) shift the three existing rows **highest-first** — `regulation-legal 7→8`, then `psychology 6→7`, then `governance 5→6` — then INSERT negotiation at 5 (each step lands on a now-vacant value); or (b) perform all moves inside one transaction where the UNIQUE check is deferrable. Option (a) needs no deferrable constraint and is the safer mechanic. Either is a Phase 16 implementation detail; both yield the collision-free final set above. (This is a *write* operation — executed in Phase 16, not Phase 15. Phase 15 only documents that it is collision-free and permitted.)

## D-04 — Hub schema accommodation (pinned recommendation)

**Problem restated:** the hub `agent-economy` has `type: hub` and **no tier**; `blocks.tier` is `NOT NULL CHECK (tier IN ('substrate','behavior','frame'))`, and `block_body_versions.block_slug` FKs `blocks(slug)` — so the hub body cannot live in `block_body_versions` without a `blocks` row, which cannot exist without a valid tier. D-04 requires: DB-served hub body, gated by `publish_block_version` **unchanged**, rendered by `marked.parse` **unchanged**. The exact DDL is delegated to the researcher.

### Concrete minimal DDL options

#### Option A — Relax tier CHECK + add `'hub'` sentinel tier  ★ RECOMMENDED

DDL (a single new migration, e.g. `043`):
```sql
-- Admit a single hub sentinel tier so the hub can be a blocks row.
ALTER TABLE economy_map.blocks DROP CONSTRAINT IF EXISTS blocks_tier_check;
ALTER TABLE economy_map.blocks
    ADD CONSTRAINT blocks_tier_check
    CHECK (tier IN ('substrate','behavior','frame','hub'));
-- (accent CHECK already admits 'gray'; the hub can reuse 'gray' or any allowed accent.)
```
Then the hub becomes an ordinary `blocks` row (`slug='agent-economy'`, `tier='hub'`, `sort_order=0`, `accent='gray'`, `live_tension='TBD — set via /map-tension'`, `maturity` default), its body lands in `block_body_versions` under the existing FK, and `publish_block_version('agent-economy' draft)` works **with zero RPC change** (the RPC is slug-generic).

- **FK implications:** none new — `block_body_versions.block_slug='agent-economy'` satisfies the existing FK once the hub `blocks` row exists. ✅
- **RLS implications:** none — the hub body is gated by the existing `status='published'` anon policy exactly like every block. ✅
- **RPC implications:** **none** — `publish_block_version` operates on `p_version_id`→`block_slug` generically; Step 4's `UPDATE blocks ... WHERE slug=v_slug` finds the hub row. ✅ (Reuses RPC unchanged, the explicit D-04 requirement.)
- **`renderHub` implications:** small + safe. `renderHub`'s three tier filters (`tier === 'substrate'|'behavior'|'frame'`) **naturally exclude** the `'hub'` row from all three grids — **no card duplication** (the hub does not appear as a card in its own grid). The net-new `renderHub` change is: fetch the hub's published `body_md` (via the hub row's `current_body_version_id`, RLS-gated) and `marked.parse` it in place of / above the `escapeHtml(HUB_STORYLINE)` line at app.js:496. `marked.parse` is reused verbatim (the app.js:586 path). When no published hub body exists, fall back to the existing `HUB_STORYLINE` constant (graceful, preserves today's behavior pre-publish).
- **`MATURITY_STAGE` / pill:** the hub need not render a maturity pill; `renderHub`'s card emitter is per-tier-grid, and the hub is excluded from the grids, so no pill is emitted for it. ✅
- **Cost:** one `ALTER ... CHECK` migration + a ~5-line `renderHub` fetch/parse change. Smallest DDL that satisfies "reuse RPC + marked.parse unchanged."

#### Option B — Nullable `tier` (hub = NULL tier)

DDL:
```sql
ALTER TABLE economy_map.blocks ALTER COLUMN tier DROP NOT NULL;
-- CHECK still admits only the 3 values for non-null; NULL becomes the hub marker.
```
- **FK:** none new. **RPC:** unchanged (slug-generic). **RLS:** unchanged.
- **`renderHub`:** the three `tier === '...'` filters already exclude `NULL` (`null === 'substrate'` is false), so no grid duplication — same property as Option A.
- **Downside vs A:** drops a `NOT NULL` invariant on **every** block row to accommodate one hub row. A future buggy insert of a tier-less *block* (not hub) would silently slip past the column constraint and vanish from all grids — a silent-failure surface. Option A keeps `NOT NULL` and makes "hub" an explicit, greppable, enumerated value. **Less safe** (violates the structural-over-application / fail-loud preference: a missing tier should be loud, not a valid NULL). Not recommended.

#### Option C — Dedicated hub home (separate table, e.g. `economy_map.hub`)

DDL:
```sql
CREATE TABLE economy_map.hub (
    slug TEXT PRIMARY KEY DEFAULT 'agent-economy',
    current_body_version_id UUID REFERENCES economy_map.hub_body_versions(id) ...
);
CREATE TABLE economy_map.hub_body_versions ( ... append-only trigger ... );
-- plus a hub-specific publish_hub_version() RPC, RLS, grants, indexes.
```
- **FK/RLS/RPC:** **all net-new** — a parallel append-only trigger, a parallel publish RPC (or a generalization of `publish_block_version`), parallel RLS + grants. This **violates D-04's explicit "reuse `publish_block_version` unchanged"** unless the existing RPC is rewritten to be polymorphic across two tables (a larger, riskier change to a SECURITY DEFINER function on the publish path — exactly the kind of governance-path change the spine warns against).
- **`renderHub`:** needs a separate query against `hub_body_versions`. More code than A.
- **Verdict:** maximal blast radius for the smallest gain. Rejected — it neither reuses the RPC nor minimizes DDL.

### Recommendation

**Adopt Option A** (relax tier CHECK + `'hub'` sentinel tier). It is the minimal DDL that:
- reuses `publish_block_version` **unchanged** (D-04 requirement) ✅
- reuses `marked.parse` **unchanged** (D-04 requirement; app.js:586 path) ✅
- adds **no** net-new FK / RLS / RPC / append-only trigger ✅
- keeps `tier NOT NULL` (preserves the fail-loud invariant for *block* rows; the hub is an explicit enumerated value, not a NULL gap) ✅
- requires only a ~5-line `renderHub` fetch-and-`marked.parse` change with a graceful fall back to the existing `HUB_STORYLINE` when unpublished ✅

The existing XSS-via-markdown disposition (T-04-03-01 — compensating control = operator publish gate via the RPC) carries over unchanged, because the hub body publishes through the same gated RPC as every block. `[VERIFIED against: 033 tier CHECK, FK, RPC; app.js renderHub filters]`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic publish (draft→published + supersede + sync) | A multi-statement client-side sequence | `publish_block_version(p_version_id)` RPC | One SECURITY DEFINER transaction, single-winner race property, watermark advance. Re-implementing client-side loses atomicity. `[VERIFIED: 039]` |
| Content immutability | App-layer "don't UPDATE this" checks | The existing append-only triggers | service_role bypasses RLS/app checks; only triggers bind it. Memory: structural-over-application. `[VERIFIED: 033 §8]` |
| Markdown → HTML for the hub | A new renderer / different lib | `marked.parse` (app.js:586) | Already loaded, already the block-body path; D-04 mandates reuse. `[VERIFIED: app.js]` |
| Hub schema home | A whole new table + RPC + trigger (Option C) | One relaxed tier CHECK + sentinel tier (Option A) | Reuses RPC + marked.parse; no net-new governance-path code. |
| One-open-draft-per-slug guard | A processor read-then-insert lock | UNIQUE partial index `uq_block_body_versions_one_open_draft` (041) | DB-enforced; processor catches `23505` as benign skip. `[VERIFIED: 041]` |

**Key insight:** the entire publish/immutability/read-gate surface is already structurally enforced in Postgres. Phase 15 documents it; Phase 16/18 should call into it, never re-implement it client-side.

## Runtime State Inventory

> This is a documentation/reconciliation phase (no writes). The runtime state that the *downstream* phases (16/18) will touch is inventoried here so the reconciliation plan is complete.

| Category | Items Found | Action Required (downstream, NOT this phase) |
|----------|-------------|------------------|
| Stored data (DB) | `economy_map.blocks` holds 7 seeded rows (sort_order 1–7); `block_body_versions` and `timeline_entries` content state not probed (no-write phase). The 7 seed rows carry `live_tension='TBD'` and `maturity='nascent'`. | Phase 16: INSERT `negotiation-coordination`; UPDATE sort_orders (governance 5→6, psychology 6→7, regulation 7→8); INSERT 8 published-pending bodies (hub + 7 docs) into `block_body_versions`. Phase 18: run publish RPC per version. **None in Phase 15.** |
| Live service config | None — no external service (n8n, Datadog, Task Scheduler) embeds the roster. The roster lives entirely in `economy_map` + the static `app.js` constants. | None. |
| OS-registered state | None — no cron/systemd/Task Scheduler entry references block slugs. | None. |
| Secrets / env vars | None renamed. `SUPABASE_SERVICE_KEY` (agents) and the anon key (frontend) are unchanged; no key references a block slug. | None. |
| Build artifacts | `docker/web/site/app.js` is served by Caddy (`agentpulse-web`). The `HUB_STORYLINE` constant is a build-time literal — D-04's `renderHub` change (Phase 16/17) requires a **web-only scoped rebuild** (`agentpulse-web`) per D-06. No Python service rebuild. | Phase 16/17: web-only scoped rebuild after the `renderHub` edit. **None in Phase 15.** |

**Verified-nothing categories:** Live service config, OS-registered state, and secrets each verified empty — the roster is confined to `economy_map` (DB) + `app.js` (static), with no third surface caching block slugs.

## Common Pitfalls

### Pitfall 1: Treating the sort_order reshuffle as blocked by append-only
**What goes wrong:** Assuming the append-only triggers protect `blocks.sort_order` and routing the reshuffle through a body-rewrite.
**Why it happens:** The triggers are prominent in 033; easy to over-generalize "this schema is append-only" to all three tables.
**How to avoid:** The triggers are on `block_body_versions` and `timeline_entries` **only** (033 §8). `blocks` has no trigger — `sort_order`, `maturity`, `live_tension`, `current_body_version_id`, `last_synthesized_at` are all plain UPDATE-able. Confirmed above.
**Warning sign:** A plan that proposes a "canonical-body-rewrite" to change a sort_order.

### Pitfall 2: `sort_order` UNIQUE transient collision during the reshuffle
**What goes wrong:** UPDATE `governance 5→6` while `psychology` still occupies 6 → `23505` unique violation.
**How to avoid:** Move highest-first (regulation 7→8, psychology 6→7, governance 5→6) then INSERT negotiation at 5; or wrap in one txn with a deferrable unique constraint. (Phase 16 mechanic — documented here so the plan accounts for it.)
**Warning sign:** A plan that UPDATEs sort_orders lowest-first without a deferrable constraint.

### Pitfall 3: Leaving `building` to reach the DB or the pill
**What goes wrong:** Loading a body with `proposed_maturity='building'` → enum-reject (loud, at least) OR a stray `building` reaching `MATURITY_STAGE` → silent stage-1 mis-fill.
**How to avoid:** Apply the D-01 remap in the Phase 16 loader *before* the INSERT; never depend on the pill's `|| 1` fallback to "handle" it.
**Warning sign:** Any code path that passes frontmatter `maturity` to the DB or the pill without the `building→emerging` substitution.

### Pitfall 4: Adding a defensive `.eq('status','published')` to the hub fetch
**What goes wrong:** Duplicating the RLS gate in the client (the D-17 anti-pattern) — brittle and a maintenance trap.
**How to avoid:** Mirror the block-body path (app.js:535–586): fetch by `current_body_version_id`, let anon RLS gate to published. The hub fetch should follow the same no-defensive-filter pattern.
**Warning sign:** A `renderHub` change that filters status client-side.

### Pitfall 5: Folding the hub-tier CHECK relax into an unrelated migration
**What goes wrong:** Combining the D-04 `ALTER ... CHECK` with the D-03 INSERT/UPDATE migration obscures the operator-approved scope (the 040/041 precedent deliberately keeps WR-01 in its own migration).
**How to avoid:** Ship the tier-CHECK relax (D-04) and the roster reshuffle (D-03) as cleanly-scoped, individually reviewable migrations — consistent with the scoped-approved-deploys discipline (memory).
**Warning sign:** One mega-migration `043` doing both the schema relax and the data reshuffle without section fences.

## Code Examples

### Verifying the live enum members (read-only, for the contract doc)
```sql
-- Source: 033 §3, lines 46-52 (authoritative). Live equivalent:
SELECT e.enumlabel
  FROM pg_enum e
  JOIN pg_type t ON t.oid = e.enumtypid
  JOIN pg_namespace n ON n.oid = t.typnamespace
 WHERE t.typname = 'maturity' AND n.nspname = 'economy_map'
 ORDER BY e.enumsortorder;
-- expected: nascent, emerging, contested, consolidating, mature
```

### The atomic publish RPC body (current = migration 039)
```sql
-- Source: supabase/migrations/039_publish_block_version_watermark_null_guard.sql
-- (signature stable since 033; 038 added watermark, 039 added COALESCE null-guard)
CREATE OR REPLACE FUNCTION economy_map.publish_block_version(p_version_id uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = economy_map, public AS $$
DECLARE v_slug text; v_maturity economy_map.maturity; v_synthesized_from_through timestamptz;
BEGIN
  UPDATE economy_map.block_body_versions
     SET status='published', published_at=NOW()
   WHERE id=p_version_id AND status='draft'
  RETURNING block_slug, proposed_maturity, synthesized_from_through
    INTO v_slug, v_maturity, v_synthesized_from_through;
  IF v_slug IS NULL THEN RAISE EXCEPTION 'version % not found or not in draft status', p_version_id; END IF;
  UPDATE economy_map.block_body_versions
     SET status='superseded'
   WHERE block_slug=v_slug AND status='published' AND id<>p_version_id;
  UPDATE economy_map.blocks
     SET current_body_version_id=p_version_id, maturity=v_maturity,
         last_synthesized_at=COALESCE(v_synthesized_from_through, last_synthesized_at)
   WHERE slug=v_slug;
END; $$;
```

### Recommended D-04 hub accommodation (Option A)
```sql
-- Minimal: admit a 'hub' sentinel tier so the hub body lives in block_body_versions
-- and publishes through the existing publish_block_version RPC unchanged.
ALTER TABLE economy_map.blocks DROP CONSTRAINT IF EXISTS blocks_tier_check;
ALTER TABLE economy_map.blocks
  ADD CONSTRAINT blocks_tier_check CHECK (tier IN ('substrate','behavior','frame','hub'));
```
```js
// renderHub change (sketch): fetch hub published body, marked.parse it, else fall back.
// reuses the app.js:586 marked.parse path verbatim; RLS gates anon to published.
var hubBody = /* sb.schema('economy_map').from('block_body_versions')
                  .select('body_md').eq('id', hubRow.current_body_version_id).single() */;
var hubHtml = hubBody && hubBody.body_md
  ? marked.parse(hubBody.body_md)
  : '<div class="hub-storyline">' + escapeHtml(HUB_STORYLINE) + '</div>'; // graceful fallback
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `publish_block_version` stamps `last_synthesized_at = NOW()` (033) | Stamps the draft's pinned `synthesized_from_through`, COALESCE-guarded (038→039) | migrations 038 (Jun 2) → 039 (Jun 3) | The publish RPC body to document is **039**, not 033. Watermark advances exactly; NULL draft watermark declines to advance. |
| Non-unique `draft` partial index (033) | UNIQUE one-open-draft-per-slug (041) | migration 041 (Jun 3) | At most one open draft per slug; loader must not create a second draft for a slug. |

**Not deprecated, just refined:** `reject_block_version` and all RLS/grants/triggers are unchanged since 033.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The deployed DB exactly matches migrations 033–042 (no out-of-band drift). | DB-probe disclosure | If the live enum/CHECK differs from the SQL, Phase 16's loader fails loud against the live constraint — caught, not silent. Low risk; the migration files are the declared source per CONTEXT D-05. |
| A2 | `renderHub` excludes a non-{substrate,behavior,frame} tier from all grids (so Option A's `'hub'` row shows no card). | D-04 Option A | `[VERIFIED: app.js:450-452, 498-499]` — the filters are literal `tier === '...'` equality, so a `'hub'` row is excluded. Reclassified to verified; retained here only because the *consequence* (no duplication) is inferred. Low risk. |

**Otherwise:** every structural claim is `[VERIFIED: migration SQL]` or `[VERIFIED: app.js]` — read directly from the in-tree authoritative files. The two assumptions above are the only non-VERIFIED items.

## Open Questions

1. **Does the hub need a maturity pill / sort_order in `renderHub`?**
   - What we know: Option A gives the hub row a `sort_order` (0 recommended) and a default `maturity`; `renderHub` excludes it from the tier grids, so neither is rendered as a card today.
   - What's unclear: whether Phase 17 presentation wants any hub-level visual treatment (explicitly deferred to Phase 17 per CONTEXT).
   - Recommendation: set `sort_order=0`, `maturity` default, `accent='gray'` on the hub row for completeness; leave all *presentation* of the hub (prose vs cards, pill) to Phase 17. Phase 15 only documents the home.

2. **ROADMAP SC#2 / Phase 17 SC#2 wording (`building` vs `emerging`).**
   - What we know: D-01 is the authoritative resolution; the pills will read `emerging` for the three substrate blocks.
   - What's unclear: whether the ROADMAP text gets corrected now or is just understood as superseded by D-01.
   - Recommendation: flag F-2 in the reconciliation doc so the operator/planner updates Phase 17's verification text to expect `emerging` for slugs 1/2/3. No code impact.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Migration SQL files (033–042) | INV-01/02, ROST-01 contract | ✓ | in-tree | — (authoritative source) |
| `docker/web/site/app.js` | INV-01 serve path, D-04 | ✓ | in-tree | — |
| 00-07 doc frontmatters | ROST-01 roster | ✓ | in-tree | — |
| Live Supabase (probe) | (optional verification only) | creds present in `config/.env`, but **not used** — no-write phase | — | Migration SQL is authoritative (CONTEXT D-05) |

**Missing dependencies with no fallback:** None. All artifacts needed to document the contract and resolve the roster are in-tree.
**Missing dependencies with fallback:** Live DB probe deliberately skipped; the migration SQL is the declared authoritative source.

## Validation Architecture

> `workflow.nyquist_validation` was not located as explicitly `false`; treated as enabled. This phase is **no-write documentation** — "validation" here means *checkable acceptance of the RESEARCH/plan artifacts and the documented contract facts against the in-tree source*, not a code test suite. There is no application code to unit-test in Phase 15.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None for this phase (no executable deliverable). Repo test runner is `pytest` (`tests/`), not exercised here. |
| Config file | none — see Wave 0 |
| Quick run command | `grep`/`sed` assertions against the migration SQL + app.js (below) |
| Full suite command | Manual operator review of the reconciliation doc + the four success criteria (ROADMAP §Phase 15 SC 1–4) |

### Phase Requirements → Validation Map
| Req / SC | Behavior to confirm | Validation type | Checkable command | Exists? |
|----------|---------------------|-----------------|-------------------|---------|
| INV-01 (SC#1) | blocks columns + the 3-tier CHECK documented from live SQL | assertion | `grep -n "CHECK (tier IN ('substrate','behavior','frame'))" supabase/migrations/033_economy_map_schema.sql` | ✅ matches line 68 |
| INV-01 | append-only triggers guard `block_body_versions` + `timeline_entries` only (not `blocks`) | assertion | `grep -nc "CREATE TRIGGER" supabase/migrations/033_economy_map_schema.sql` → 2; `grep -n "ON economy_map.blocks" 033...` returns no trigger | ✅ (2 triggers, neither on blocks) |
| INV-01 | publish RPC is atomic 4-step, service_role-only, current body = 039 | assertion | `grep -n "GRANT EXECUTE ON FUNCTION economy_map.publish_block_version" supabase/migrations/039_*.sql` | ✅ line 82 |
| INV-01 | anon sees only `status='published'` bodies | assertion | `grep -n "USING (status = 'published')" supabase/migrations/033_*.sql` | ✅ line 370 |
| INV-01 | hub served via hardcoded `HUB_STORYLINE`, blocks via `marked.parse` gated to published | assertion | `grep -n "HUB_STORYLINE\|marked.parse" docker/web/site/app.js` | ✅ lines 32/496 + 250/586 |
| INV-02 (SC#2) | enum members = nascent/emerging/contested/consolidating/mature; `building` absent; emerging→2; unknown→1 | assertion | `grep -n "'nascent',\|'emerging',\|MATURITY_STAGE\|building" ...` ; confirm no `building` token in 033 enum | ✅ |
| ROST-01 (SC#3) | regulation-legal seeded frame@7; negotiation NOT seeded; ON CONFLICT DO NOTHING | assertion | `grep -n "regulation-legal\|negotiation-coordination\|ON CONFLICT (slug) DO NOTHING" supabase/migrations/033_*.sql` | ✅ (reg present @7, neg absent, line 415) |
| ROST-01 | doc frontmatters match CONTEXT roster (modulo D-01 remap) | review | diff the §ROST-01 frontmatter table above vs CONTEXT §specifics — F-1/F-2/F-3 are the only deltas, all expected | ✅ documented |
| ROST-01 | reshuffle map is collision-free {1..8} | review | the §ROST-01 before/after table yields 8 distinct contiguous values | ✅ proven |
| D-04 | recommended accommodation reuses RPC + marked.parse unchanged | review | Option A DDL touches only the tier CHECK; RPC + app.js:586 unchanged | ✅ documented |
| SC#4 | reconciliation plan presented for operator approval before any write | gate | the plan is the deliverable; Phase 15 writes nothing to `economy_map` (verify: no migration `043+` applied, no PostgREST write in this phase) | ✅ by construction (no-write) |

### Sampling Rate
- **Per artifact:** run the `grep` assertions above against the in-tree files — each is < 1s, deterministic.
- **Phase gate:** operator reviews the documented contract + the per-slug disposition table and the four ROADMAP success criteria before approving Phase 16.

### Wave 0 Gaps
- None — there is no code to test in Phase 15. The validation is assertion-of-documented-facts (the `grep` commands above) plus operator review of the four success criteria. No `pytest` file, no fixture, no framework install needed for this no-write phase.

## Security Domain

> `security_enforcement` not set `false`; included. This is a no-write/no-new-code phase, so the security surface is the *documented* one (carried into 16/18), not net-new.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control (existing, documented) |
|---------------|---------|-----------------------------------------|
| V1 Architecture | yes | Schema isolation (`economy_map` + `Accept-Profile`); publish gate as the spine's enforcement point. |
| V4 Access Control | yes | RLS (anon read-only, published-only bodies, non-unsorted timeline) + `publish_block_version` REVOKE PUBLIC / GRANT service_role. service_role bypasses RLS → immutability via triggers, not RLS. `[VERIFIED: 033 §8/§11]` |
| V5 Input Validation | yes | `tier`/`accent`/`status` CHECKs; `maturity` ENUM (rejects `building` loudly); D-01 remap is the validated substitution at the loader boundary. |
| V6 Cryptography | no | none introduced. |
| V7 Error Handling/Logging | yes | RPC `RAISE EXCEPTION` on not-found/not-draft (fail-loud, per the wallet-bug lesson). |
| V5.3 Output Encoding (XSS) | yes | `marked.parse` is the markdown→HTML path; the documented disposition (T-04-03-01) is **compensating control = operator publish gate**. Carries over unchanged to the hub (D-04 routes the hub through the same gate). |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation (existing) |
|---------|--------|---------------------------------|
| Stored XSS via block/hub markdown body | Tampering / Elevation | Operator publish gate (`publish_block_version`) is the compensating control (T-04-03-01); only operator-approved bodies reach anon. |
| service_role mutating immutable content | Tampering | BEFORE UPDATE/DELETE triggers (bind service_role; RLS cannot). `[VERIFIED: 033 §8]` |
| search_path hijack of the SECURITY DEFINER RPC | Elevation | `SET search_path = economy_map, public` pinned on the RPC (T-02). `[VERIFIED: 039:37]` |
| Concurrent publish race (double-publish) | Tampering | Single-winner `AND status='draft' ... RETURNING` + UNIQUE one-open-draft (041). |
| Tier-less/NULL block slipping past constraints | Tampering | Option A keeps `tier NOT NULL` and enumerates `'hub'` (vs Option B's nullable tier, which opens this surface). Reason Option A is recommended over B. |

## Sources

### Primary (HIGH confidence — in-tree authoritative)
- `supabase/migrations/033_economy_map_schema.sql` — schema, enum (§3), blocks (§4), block_body_versions (§5), FK (§6), timeline_entries (§7), append-only triggers (§8), publish/reject RPCs (§9/§10), RLS (§11), grants (§12), seed (§13).
- `supabase/migrations/038_publish_block_version_watermark.sql` — watermark advance (RPC body refinement).
- `supabase/migrations/039_publish_block_version_watermark_null_guard.sql` — **current** publish RPC body (COALESCE null-guard).
- `supabase/migrations/040_operator_write_commands_schema.sql` — synth_requests / write RPCs / reassigned lifecycle (context).
- `supabase/migrations/041_block_body_versions_unique_open_draft.sql` — UNIQUE one-open-draft-per-slug index.
- `supabase/migrations/042_reassign_timeline_entry_slug_validation.sql` — reassign hardening (context).
- `docker/web/site/app.js` — `HUB_STORYLINE` (32), `MATURITY_STAGE` (38), `renderMaturityPill` (391), `renderHub` (420–503), `renderBlock`/`marked.parse` (505–604), status renderer (692+).
- `.planning/docs/00-hub.md … 07-psychology-disposition.md` — roster frontmatters (slug/tier/title/subtitle/order/maturity).
- `.planning/phases/15-inventory-roster-reconciliation/15-CONTEXT.md` — D-01..D-06, reconciled roster table.
- `.planning/ROADMAP.md` §Phase 15 — goal + 4 success criteria. `.planning/REQUIREMENTS.md` — INV-01/02, ROST-01.

### Secondary / Tertiary
- None. No web search performed — every fact is sourced from in-tree authoritative files appropriate for a contract-documentation phase.

## Metadata

**Confidence breakdown:**
- INV-01 contract: HIGH — read column-by-column from 033/038/039/041 and app.js.
- INV-02 enum: HIGH — enum members + `MATURITY_STAGE` read verbatim; `building` absence confirmed by grep.
- ROST-01 roster: HIGH — seed VALUES, `ON CONFLICT`, frontmatters, and the collision-free reshuffle all derived from source.
- D-04 recommendation: HIGH on the constraint analysis (CHECK/FK/RPC/RLS read directly); MEDIUM only on the *preference* between A and B (a judgment call — A recommended on fail-loud grounds).

**Research date:** 2026-06-08
**Valid until:** 2026-07-08 (stable — schema migrations are append-only and the contract is locked; revisit if a migration ≥043 lands).
