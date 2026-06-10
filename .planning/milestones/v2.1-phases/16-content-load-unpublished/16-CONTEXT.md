# Phase 16: Content Load (unpublished) - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Land all in-scope canonical bodies (hub `agent-economy` + the 7 reconciled blocks) into `economy_map` as **unpublished drafts** (`status='draft'`), using the `.md` YAML frontmatter as the metadata source of truth — content is present in the store with **zero change for live visitors**, and the load **refuses to land anything blank or partial**.

Requirements: **LOAD-01** (all bodies loaded as unsorted/unpublished, frontmatter is truth, zero visitor change), **LOAD-02** (fail loud on any missing/empty required field; no blank/partial block), **LOAD-03** (existing rows corrected via canonical-body-rewrite, never raw UPDATE on append-only columns; no duplicate rows).

**In scope:** migration `043` (structure) + a standalone body loader (content) + a negative-path test. **Out of scope:** cross-link/preview verification (Phase 17), the publish RPC (Phase 18), any UI redesign, any pipeline/proxy/agent-service change.
</domain>

<decisions>
## Implementation Decisions

Decisions below were resolved with the operator on 2026-06-08. They sit **on top of** the locked Phase-15 contract + reconciliation (see "Locked upstream" — do not re-litigate).

### Load packaging & artifacts

- **D-01 — Bodies via a standalone Python PostgREST loader.** The 8 markdown bodies are inserted as `block_body_versions` drafts by a **standalone one-shot script** (e.g. `scripts/load_economy_map_content.py`) using direct PostgREST + `Content-Profile: economy_map`. The `.md` files stay the source of truth (bodies are NOT copied into SQL). The script is **self-contained** — it carries its own ~15-line PostgREST insert function rather than importing from the processor module (avoids triggering the processor's module-level init). It is **never wired into the processor scheduler** — honors "no pipeline / proxy / agent-service changes." Matches the standing "migration owns structure; write-path owns editorial copy" pattern.

- **D-02 — Migration `043` owns ALL `blocks`-row structure, in one atomic transaction.** A single migration carries: (a) the D-04 tier-CHECK relax (admit a `'hub'` sentinel tier), (b) the new **hub `blocks` row** (`slug='agent-economy'`, `tier='hub'`, `sort_order=0`), (c) the new **`negotiation-coordination` `blocks` row** (`tier='behavior'`, `sort_order=5`), and (d) the **`sort_order` reshuffle** — highest-first (`regulation-legal` 7→8, `psychology` 6→7, `governance` 5→6) **then** insert `negotiation` at the now-vacant 5, so the `UNIQUE(sort_order)` constraint never transiently collides. `blocks` has no append-only trigger, so these are permitted writes.

- **D-03 — Run order: migration `043` first (orchestrator-applied via Supabase MCP), loader second.** The orchestrator applies `043` via the Supabase MCP tool (NOT from a worktree executor — live migration apply is orchestrator-owned per prod-cutover discipline). Only then does the standalone loader run, so every `block_body_versions.block_slug` FK target (incl. the new hub + negotiation rows) already exists. **The loader inserts bodies only** — it creates no `blocks` rows.

### Fail-loud & no-change proof

- **D-04 — Pre-flight validate ALL 8 inputs, then insert (no partial load).** The loader parses + validates all 8 `.md` files **up front** and **halts before any insert** if any one fails; only a fully-valid batch proceeds to insertion. Directly satisfies SC#2 "lands no blank or partial block" — a broken input rejects the whole batch.

- **D-05 — Required-field gate = full metadata + non-empty body + valid post-remap maturity.** Per file the gate requires: `slug` (present and in the locked roster), `title`, `subtitle`, `tier` (block) / `type=hub` (hub), `order`, and — for blocks — `maturity`; **plus `body_md` non-empty after stripping whitespace** (the DB `NOT NULL` does NOT catch `''` — the loader must); **plus the post-remap `proposed_maturity` ∈ the 5-member live enum** (`nascent/emerging/contested/consolidating/mature`). The **hub is special-cased** (no `tier`/`maturity` in its frontmatter). Faithful to LOAD-02's "any missing/empty required field."

- **D-06 — Ship a deliberately-broken-fixture negative test.** The phase includes a negative-path test that runs the loader against a deliberately-broken input (empty body and/or null/invalid maturity) and confirms it **halts loud and lands nothing** — a real demonstration the gate fires, not just an assertion that the guard exists.

- **D-07 — Prove SC#1 with a before/after anon-perspective read.** Capture the anon-visible state before and after the load (anon-key `SELECT` on `economy_map.blocks` + published `block_body_versions` counts, or the rendered `#/map`) and show they're **identical** — the loaded drafts add zero published rows because the anon RLS policy is `status='published'`. Concrete SC#1 evidence, not RLS reasoning alone.

### Claude's Discretion

Two gray areas were surfaced but the operator chose not to deep-dive them. Recommended defaults below; planner/researcher may refine against the live schema, keeping fail-loud intact.

- **Re-run / partial-failure idempotency (recommended: idempotent skip-if-open-draft).** Because D-04 validates-all-before-any-insert, a *validation* failure lands nothing. A partial load can only occur on an insert-time/transport failure mid-batch. Recommend the loader be **re-runnable to complete the remainder**: skip a slug that already has an open `status='draft'` body (reuse the `block_has_open_draft()` logic). Migration `041`'s one-open-draft `UNIQUE` index (raises `23505`) is the structural backstop either way. Planner pins the exact recovery posture.
- **Fields the frontmatter omits (recommended defaults).** `live_tension` (NOT NULL on `blocks`) → the seed placeholder `'TBD — set via /map-tension'` (033:73), populated later via the command surface. Hub `proposed_maturity` (NOT NULL on `block_body_versions`, hub has no `maturity`) → `'nascent'` (the `blocks` default; the hub never renders a maturity pill — `tier='hub'` is excluded from all grids). `accent` (NOT NULL `CHECK accent IN ('teal','purple','coral','gray')`) for the new hub + negotiation rows → planner picks (the D-04 reconciliation example used hub `accent='gray'`). Existing-row metadata (`title`/`subtitle`/`tier`) → frontmatter is the source of truth, and the seed already matches target order per `15-RECONCILIATION.md`; a verify-and-correct-if-mismatch via a permitted `blocks` UPDATE is low-risk discretion.

### Locked upstream (Phase 15 — carry forward, DO NOT re-decide)

- **P15-D-01:** `building → emerging` maturity remap applied **at load time** for the 3 substrate slugs (`identity-trust`/`memory-context`/`payments-settlement`) — no `ALTER TYPE`, no `app.js` change.
- **P15-D-02:** `regulation-legal` stays **deferred / body-less** — only the structural `sort_order 7→8` bump touches it; no content/publish write.
- **P15-D-03:** `negotiation-coordination` is a **new behavior block** at `sort_order 5`; collision-free reshuffle to `{1..8}`.
- **P15-D-04:** Hub gets a DB-served home via **Option A** (relax the tier CHECK to admit `'hub'`); reuse `publish_block_version` + `marked.parse` **unchanged**; graceful fallback to the existing `HUB_STORYLINE` constant pre-publish.
- **P15-D-06:** Direct PostgREST + `Accept-Profile`/`Content-Profile` (never supabase-py `.in_()`); canonical-body-rewrite path (never a raw UPDATE on append-only columns); fail-loud on any missing field; branch + `/diff` + web-only scoped `agentpulse-web` deploy.
- Loaded body status is **`'draft'`** — the contract clarified "unsorted/unpublished" = `draft`; there is no `'unsorted'` body status (that concept is for `timeline_entries.block_slug='unsorted'` only).
- The operator **approval gate is satisfied** (`15-APPROVAL.md`, verdict: approved 2026-06-08) — Phase 16 is cleared to write.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The brief, requirements & verification target (read first)
- `.planning/docs/EXECUTION_BRIEF.md` — the read-before-write brief. §1 canonical roster, §3 sequencing (load → preview → publish), §4 standing constraints (PostgREST, append-only, fail-loud, scoped deploy).
- `.planning/REQUIREMENTS.md` — LOAD-01, LOAD-02, LOAD-03 (this phase).
- `.planning/ROADMAP.md` §"Phase 16" — goal + the 4 success criteria (the verification target).

### Phase 15 locked inputs (the contract this phase executes from)
- `.planning/phases/15-inventory-roster-reconciliation/15-CONTRACT.md` — the live `economy_map` storage + serve contract: `blocks` columns + 3-tier CHECK + `accent`/`live_tension` NOT NULL; the 2 append-only triggers (NONE on `blocks`); the atomic `publish_block_version` RPC; anon published-only RLS; the verified 5-member `maturity` enum (`building` is NOT a member).
- `.planning/phases/15-inventory-roster-reconciliation/15-RECONCILIATION.md` — per-slug disposition, the collision-free `sort_order` reshuffle to `{1..8}`, the D-04 Option-A hub accommodation, flags F-1/F-2/F-3.
- `.planning/phases/15-inventory-roster-reconciliation/15-CONTEXT.md` — decisions D-01..D-06 (carried forward above).
- `.planning/phases/15-inventory-roster-reconciliation/15-APPROVAL.md` — the operator read-before-write approval gating this phase's writes.

### Canonical content (metadata source of truth)
- `.planning/docs/00-hub.md` — hub `agent-economy` (frontmatter: slug/type/title/subtitle/order — **no tier, no maturity**; subject of D-04).
- `.planning/docs/01-identity-trust.md … 07-psychology-disposition.md` — the 7 block bodies. **YAML frontmatter (slug/tier/title/subtitle/order/maturity) is the metadata source of truth.** `maturity: building` on 01/02/03 is **remapped to `emerging` at load** (P15-D-01) — do NOT edit the docs.

### The live schema (document/verify against these; the migration sources)
- `supabase/migrations/033_economy_map_schema.sql` — core contract: `maturity` ENUM (§3), `blocks` (slug UNIQUE, tier CHECK, `accent` CHECK, `live_tension` NOT NULL seeded `'TBD — set via /map-tension'`, `sort_order` UNIQUE, `maturity` DEFAULT nascent), `block_body_versions` (append-only trigger; `status` draft/published/superseded; `proposed_maturity` NOT NULL pinned; `body_md` NOT NULL), RLS (anon sees only `status='published'`), the 7-block seed (§13).
- `supabase/migrations/039_publish_block_version_watermark_null_guard.sql` — the authoritative publish RPC body (Phase 18 reuses unchanged).
- `supabase/migrations/041_block_body_versions_unique_open_draft.sql` — the one-open-draft `UNIQUE` index (idempotency backstop).
- Next migration number is **`043`** (highest present is `042_reassign_timeline_entry_slug_validation.sql`).

### The live serve path (frontend — no edit this phase)
- `docker/web/site/app.js` — `MATURITY_STAGE` (l.38, `emerging`→stage 2), `renderMaturityPill` (l.391, unknown→stage 1), `renderHub` (tier grids exclude any non-substrate/behavior/frame tier → hub excluded from grids), block body via `marked.parse` (l.586). **No `app.js` change in Phase 16** (D-04 render work is Phase 17 scope).

### Project decision record
- `.planning/PROJECT.md` — Key Decisions (regulation = closing frame; append-only `block_body_versions`; schema isolation via direct PostgREST; sentinels flag-never-block).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`economy_map_insert_block_body_version(row)`** (`docker/processor/agentpulse_processor.py:3174`) — the exact draft-INSERT path (direct PostgREST, `Content-Profile: economy_map`, omits `status` so DB default `'draft'` applies, raises on non-2xx). The standalone loader **replicates this ~15-line function** rather than importing it (D-01).
- **`_economy_map_get(table, params)`** (`:3088`) — schema-READ helper (`Accept-Profile: economy_map`, raises on non-2xx) — the model for the loader's reads and the D-07 anon snapshot.
- **`block_has_open_draft(slug)`** (`:3124`) — open-draft existence check — the basis for the recommended idempotent skip-if-present re-run posture.
- **`publish_block_version` RPC** (migration 039) — reused **unchanged** in Phase 18; not called here.

### Established Patterns
- **Append-only is trigger-enforced on `block_body_versions` + `timeline_entries`, NOT on `blocks`** — so the `sort_order` reshuffle + new-row INSERTs in migration `043` are permitted plain writes; body *corrections* (LOAD-03) must use the canonical-body-rewrite path (new draft → publish), never a raw UPDATE.
- **RLS is the read boundary** — anon sees only `status='published'` bodies, so the Phase-16 draft load is invisible to visitors until Phase 18 (underpins SC#1 / D-07).
- **Purpose-scoped writers** (tight write surface, threat T-07-WS) — the loader keeps a single narrow insert function, not a generic schema-agnostic writer.
- **Empty-string is not NULL** — `body_md`/`live_tension` are NOT NULL but `''` passes; explicit non-empty guards live in app code (D-05).

### Integration Points
- **Migration `043`** is the only schema write; applied via Supabase MCP by the orchestrator (no worktree). Run sequentially / no-worktree (scoped-rebuild-worktree-unsafe lesson).
- **The standalone loader** runs against the live DB after `043`; its FK targets (hub + negotiation `blocks` rows) are created by `043`.
- **No service rebuild** is required for the load itself (the loader is one-shot; no running-service code changes). Phase 17 handles the render/preview wiring.
</code_context>

<specifics>
## Specific Ideas

**The two-artifact plan this phase locks:**

1. **Migration `043`** (orchestrator applies via Supabase MCP, FIRST, one atomic transaction):
   - tier-CHECK relax → admit `'hub'`
   - INSERT hub `blocks` row (`agent-economy`, `tier='hub'`, `sort_order=0`)
   - INSERT `negotiation-coordination` `blocks` row (`tier='behavior'`, `sort_order=5`)
   - `sort_order` reshuffle, highest-first: `regulation-legal` 7→8, `psychology` 6→7, `governance` 5→6, then `negotiation` lands at 5 → final `{1..8}` contiguous, collision-free
2. **Standalone loader** (`scripts/load_economy_map_content.py`, runs SECOND, bodies only):
   - parse all 8 `.md`; **pre-flight validate all** (full metadata + non-empty body + valid post-remap maturity); halt-loud on any failure
   - apply `building → emerging` remap before insert
   - insert 8 `block_body_versions` drafts via direct PostgREST
   - recommended: idempotent skip-if-open-draft for safe re-run
3. **Negative-path test** — deliberately-broken fixture proves the loader halts and lands nothing.
4. **SC#1 evidence** — before/after anon-perspective read shows `#/map` unchanged.
</specifics>

<deferred>
## Deferred Ideas

- **Phase 17 (LINK-01 / PREV-01 / HUB-01) — render, cross-links & preview:** the `renderHub` change to fetch + `marked.parse` the hub's body, cross-block `#/map/<slug>` link resolution, the non-published preview route, cards-vs-prose-links, and any distinct visual treatment for `nascent` blocks. All presentation/wiring — out of Phase 16.
- **Phase 18 (PUB-01) — gated batch publish:** the `publish_block_version` RPC run + web-only scoped deploy. Phase 16 loads drafts only; nothing publishes here.
- **EU AI Act tracker → `regulation-legal` body:** the deferred frame slot (P15-D-02) is fed by a future milestone (EUAI-01/02), not now.
- **Evolution timeline content:** bodies load with empty timelines; intake fills them weekly. No manual timeline authoring this milestone.

### Reviewed Todos (not folded)
The 7 pending todos (`.planning/todos/pending/`) were already reviewed in Phase 15 — all are v1.0 backend follow-ups (analyst predictions title-expire, soft-cap allow-negative hardening, pay-endpoint transfer RPC, phase-05/06/07 review follow-ups, research trigger file permissions). **None overlap** the `economy_map` content/load domain; parked in the ROADMAP backlog.
</deferred>

---

*Phase: 16-content-load-unpublished*
*Context gathered: 2026-06-08*
