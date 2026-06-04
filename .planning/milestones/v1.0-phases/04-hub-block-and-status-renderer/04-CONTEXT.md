# Phase 4: Hub, Block, and Status Renderer - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend the existing single-page application at `docker/web/site/app.js` with three new hash-routed views — `#/map` (hub), `#/map/<slug>` (block page), and `#/status` (maturity overview) — that read live `economy_map` data through the `supabase-js` anon client and render the seven blocks across hub/block/status surfaces using the Phase 3 design tokens. The phase delivers:

(a) **Hub** with a hardcoded storyline header, tier-grouped seven-block visual (substrate / behavior / frame), and per-block maturity pills linking to block pages;
(b) **Block pages** with the wrapper composition Title → live tension → body_md → Evolution, maturity pill inline in the title row, empty-state hiding of tension + body until populated, and a 30-newest cap on the Evolution timeline with a "Show all" expand button;
(c) **Status page** reading the same `blocks.maturity` source as the hub pills (one source of truth — RNDR-04);
(d) **Live-data Evolution section** via a hybrid mechanism: next-navigation pull as baseline + visibility-aware 60s idle poll while on a block page, scoped to `timeline_entries` only (body and other static block fields are NOT re-fetched on the idle poll).

**Out:** Writing block body content (Phase 7 — synthesis); classifying timeline entries into blocks (Phase 5 — intake); Telegram operator commands (Phases 6/9/10); `live_tension` authoring (Phase 10 — `/map-tension`); bespoke typography / page chrome (deferred to v2 design pass); Supabase Realtime push subscriptions (v2 polish — hybrid poll covers RNDR-06 for v1); per-mode block body variants (would require a `body_md_impact` column — v2).

</domain>

<decisions>
## Implementation Decisions

### URL surface + SPA shell coexistence
- **D-01:** `#/map` (hub), `#/map/<slug>` (block page), `#/status` (status page) are **new hash routes** added to the existing `app.js` router. The bare domain `/#/` continues to serve the edition list **unchanged**; `#/edition/N` continues to serve the edition reader **unchanged**. Phase 4 extends, does not replace. (Locks RNDR-05: existing publish path reused per Phase 1 §3.)
- **D-02:** **Keep the existing hero** (`.hero`, `#hero-headline`, `#hero-date`) on all three new map routes. `updateHero()` sets contextual headline + date per route:
  - `#/map` → storyline header (hardcoded — see D-12) + `'updated ' + last-touched timestamp` (or omit date if not available)
  - `#/map/<slug>` → `blocks.title` + (`'synthesized ' + last_synthesized_at` if non-null, else omit date)
  - `#/status` → `'Maturity Snapshot'` + `'updated ' + NOW()` (or omit)
- **D-03:** **Hide the technical/strategic mode toggle on map routes.** `block_body_versions` has a single `body_md` column in v1 — there is no per-mode variant. Showing the toggle on map pages is misleading UI. Implementation: `setMapToggleVisibility(false)` on hub/block/status, `true` on list/reader. The **body class itself stays** (technical or strategic from prior nav / localStorage default `'technical'`) so the `--accent-tier` cascade resolves correctly via Phase 3's `body.technical [data-accent]` / `body.strategic [data-accent]` rules.
- **D-04:** **Add a quiet `Map` text link to the nav-left cluster** between `AGENTPULSE` and the existing whitespace: nav becomes `[AGENTPULSE · Map] ... [SUBSCRIBE]`. Plain anchor styled with `color: var(--text-secondary)` (not a primary button). `href="#/map"`. Discoverability surface for both operator and visitors; no toggle/active-state styling in v1 — the active-route highlight is a v2 polish.

### Re-render mechanism (RNDR-06)
- **D-05:** **Hybrid pull + idle-poll, no Realtime in v1.** Next-navigation read is the baseline — every hashchange to `#/map/<slug>` runs the full block-page query (blocks row + current published body + timeline_entries). RNDR-06 is satisfied because a new entry shows on next view; the operator does not have to wait for the next synthesis run. Realtime push subscriptions are explicitly deferred to v2 polish (acceptable complexity tradeoff for v1).
- **D-06:** **Idle poll scope is the Evolution section only.** When on a block page, a `setInterval` re-runs the timeline-entries query (`sb.schema('economy_map').from('timeline_entries').select(...).eq('block_slug', slug).order('event_date', { ascending: false }).limit(30)`) and diffs against the rendered DOM. The block's `blocks` row, `live_tension`, and `body_md` are **NOT** re-fetched on the idle poll — body changes are publish-driven (Phase 9, far less frequent than timeline appends) and show on next navigation. This trims the poll cost and matches the editorial cadence.
- **D-07:** **Poll cadence: 60 seconds, visibility-aware.** `setInterval(pollEvolution, 60000)` fires on block-page load. A `visibilitychange` listener pauses the interval when `document.visibilityState === 'hidden'` (operator switches tabs) and resumes on visible. A `hashchange` listener clears the interval when the operator navigates away from `#/map/<slug>`. Worst-case lag is ~60 seconds when the operator is actively reading; zero cost when the tab is backgrounded.

### Block page presentation
- **D-08:** **Wrapper composition order: Title → live tension → body_md → Evolution.** Tension leads as the editorial hook before any synthesized prose (the stakes frame the substance). Body comes next; carries Sections 1/2/4 of the six-part skeleton ("What it is", "Why it's hard", "Where it stands today") as h2 headings inside `body_md` — the renderer trusts the synthesis prompt (Phase 7) to author them. Evolution follows the body as the historical ledger. Maturity is the inline pill (see D-09).
- **D-09:** **Maturity pill lives inline in the title row, right-aligned.** Not a sectioned element in the main flow. Markup: `<header class="block-header" data-accent="{accent}"><h1>{title}</h1><div class="maturity-pill" data-stage="{1..5 from maturity enum}" aria-label="Maturity: {maturity} ({stage} of 5)"><span class="seg"></span>×5</div></header>` (the pill component is the Phase 3 contract). Maps the Phase 2 `economy_map.maturity` enum to `data-stage`: nascent=1, emerging=2, contested=3, consolidating=4, mature=5.
- **D-10:** **Empty-state behavior — quiet hide of unpopulated sections.** When `blocks.live_tension === 'TBD — set via /map-tension'` (the seed placeholder), the tension card is **not rendered**. When `blocks.current_body_version_id` is `null`, the body section is **not rendered**. Title + maturity pill + Evolution **always render**. No "under construction" banner — quiet absence, not scaffolding. (This is the entire v1 state until Phase 7+9 ship synthesis and approval.)
- **D-11:** **Evolution timeline cap: 30 newest, expandable.** Initial query uses `.limit(30).order('event_date', { ascending: false })` and renders the `.timeline-entry` components in newest-first order (RNDR-07). Below the rendered list, if the count returned equals 30, append a button `<button class="timeline-show-all">Show all (N entries) ↓</button>`. On click, run a second unbounded query and replace the list. Show-all is one-shot per page-load (no re-collapse). When the idle poll (D-06) fires, it respects the current expand state — if the user clicked "Show all", the poll re-queries unbounded; otherwise it re-queries with `limit 30`.

### Hub layout + storyline source
- **D-12:** **Storyline header is hardcoded in `app.js`.** A string constant near the top of the file (`const HUB_STORYLINE = '...';`) holds the editorial copy, with a comment marking it as operator-editable copy (e.g., `// Editorial: edit this string + PR + redeploy to update`). No new schema, no new RPC, no Telegram command in this phase. Updates ship via PR + the existing `scripts/deploy.sh` web rule. (Deferred: a `/map-storyline` Telegram command — v2 operator polish; if it lands, the header source moves to `economy_map.site_copy` and the hub queries it on load.)
- **D-13:** **Hub layout grouped by tier (3 + 3 + 1).** Three sections in display order:
  - **SUBSTRATE** (sort_order 1–3): identity-trust, memory-context, payments-settlement
  - **BEHAVIOR** (sort_order 4–6): autonomy-control, governance-accountability, psychology-disposition
  - **FRAME** (sort_order 7): regulation-legal

  Each section has a small tier-label heading (e.g., `<h2 class="tier-label">SUBSTRATE</h2>`) above the block tiles. Inside each section, blocks render in `sort_order` ascending. The renderer SORTS in JS after a single query: `sb.schema('economy_map').from('blocks').select('*').order('sort_order', { ascending: true })`, then groups by `tier`.
- **D-14:** **Block tile content: title + subtitle + maturity pill; whole tile is the link target.** Each tile is an `<a href="#/map/{slug}" data-accent="{accent}" class="block-tile">` wrapping:
  - `<h3 class="tile-title">{title}</h3>` (blocks.title)
  - `<p class="tile-subtitle">{subtitle}</p>` (blocks.subtitle)
  - `<div class="maturity-pill" data-stage="{n}" aria-label="..."><span class="seg"></span>×5</div>` (Phase 3 component)

  Tier accent renders as a **left-border stripe** via `data-accent` resolving `--accent-tier`. The entire tile is clickable (anchor wraps everything). No subtitle hover hide; subtitle is always visible for clarity during the empty v1 state.

### Status page
- **D-15:** **Status page is a simplified hub.** `/#/status` queries the same `economy_map.blocks` row set as the hub (`SELECT slug, title, subtitle, accent, tier, sort_order, maturity, last_synthesized_at`) and renders one row per block with: maturity pill + title + (optional) subtitle + `last_synthesized_at` timestamp ("synthesized 2026-05-21" or "never synthesized"). Same tier grouping (3 + 3 + 1) as the hub. Same single source of truth for `maturity` (RNDR-04 — verified by changing one block's maturity in the DB and seeing both surfaces update on next navigation). No links from status rows to block pages in v1 (status is the snapshot surface; the hub is the navigation surface) — flag for v2 polish if operator wants both.

### Carrying forward from prior phases
- **D-16:** **Data path:** every query uses `sb.schema('economy_map').from(...)` against the existing anon-key client (`sb` at `app.js:7`). No direct PostgREST, no new client construction. The `Accept-Profile: economy_map` header is set automatically by supabase-js. Phase 2 D-09 + Phase 2 D-24 (exposed-schemas allowlist) are prerequisites — if browser reads return empty, that is a Phase 2 regression, not a Phase 4 bug.
- **D-17:** **RLS posture is the security boundary** (Phase 2 D-05/D-06/D-07). The anon-key client sees only `block_body_versions WHERE status = 'published'` and `timeline_entries WHERE block_slug != 'unsorted'`. The renderer DOES NOT need to filter for status or block_slug in its queries — RLS already does it. Defensive filters in JS are redundant.
- **D-18:** **Markdown rendering:** body_md uses the existing `marked` library loaded at `index.html:75` — `document.getElementById('block-body').innerHTML = marked.parse(body_md)`. Same pattern as `renderArticle()` for editions. No new dependency.
- **D-19:** **CSS surface:** `.maturity-pill`, `.timeline-entry`, `[data-accent]`, `[data-stage]` selectors and `--accent-tier` are all already in `style-map.css` (Phase 3, deployed). Phase 4 only adds **new** selectors for layout: `.block-tile`, `.tier-label`, `.block-header`, `.block-tension`, `.block-body`, `.evolution`, `.timeline-show-all`, `.status-row`. These go either into `style-map.css` (extending it) or into a new `style-hub.css` — the planner picks; the existing `style-map.css` is the simpler choice. No bespoke typography (TOKN-04 still in force — body font stays Courier New from `style-shared.css`).
- **D-20:** **Deploy:** existing `scripts/deploy.sh` web rule (Phase 1 §3) detects `docker/web/` changes and rebuilds the `web` container. Phase 4 ships via the same path.

### Claude's Discretion (planner picks)
- Exact wording of the hub `HUB_STORYLINE` string — Claude can draft an initial version that the operator edits in code review. Tone matches `PROJECT.md`: "Synthesis with editorial integrity. Eight blocks, seven shipped, one deferred; the agent economy as a living map." Or similar — keep it under 200 chars.
- File organization for new CSS (extend `style-map.css` vs new `style-hub.css`). Default: extend `style-map.css` to keep the map surface in one stylesheet. Planner may split if the file passes ~300 lines.
- Empty-state copy for hub tiles when `last_synthesized_at` is null — default: omit any "last synthesized" affordance on the tile (tile shows only title + subtitle + pill). Status page handles the synthesis-recency surface.
- Exact `setMapToggleVisibility()` mechanism — could be a CSS class on body (`body.map-route .mode-toggle { display: none; }`) or a JS `style.display` toggle on hashchange. Planner picks the simpler approach for the existing toggle DOM.
- DOM containers: extend `<main>` in `index.html` with new view containers (`<div id="map-view" style="display:none"></div>`, etc.) and let `showView()` extend its enum to cover the new views. Same pattern as the existing `#list-view` / `#reader-view`.
- Whether to add a "back to map" affordance on block pages (a `← Map` link next to the title, mirroring the existing `← All editions` link on the reader). Default: yes, since it's the conventional escape hatch and matches the existing pattern.

</decisions>

<specifics>
## Particular References

### Phase 4 visual contract (locked by Phase 3)
- `docker/web/site/style-map.css` — `.maturity-pill[data-stage="N"] .seg:nth-child(-n+N)`, `.timeline-entry` two-line format, `[data-accent]` resolves `--accent-tier`. Phase 4 emits the matching markup; doesn't touch the existing selectors.
- Phase 4 maturity-stage mapping: `nascent=1`, `emerging=2`, `contested=3`, `consolidating=4`, `mature=5`. This mapping lives in `app.js` (e.g., `const MATURITY_STAGE = { nascent: 1, emerging: 2, contested: 3, consolidating: 4, mature: 5 }`) and is the **only** Phase-4-owned token for the pill.

### Editorial copy that lives in `app.js` (not the DB)
- `HUB_STORYLINE` — the storyline header at the top of `#/map`. Hardcoded, operator edits via PR.
- `STATUS_PAGE_HEADER` — for `#/status` hero or inline header (e.g., `'Maturity Snapshot'`). Hardcoded, same edit path.
- Tier labels — `'SUBSTRATE'` / `'BEHAVIOR'` / `'FRAME'`. Hardcoded uppercase strings in the renderer.

### Schema fields Phase 4 reads
- `economy_map.blocks`: `slug`, `tier`, `title`, `subtitle`, `accent`, `sort_order`, `maturity`, `live_tension`, `current_body_version_id`, `last_synthesized_at`
- `economy_map.block_body_versions`: `id`, `block_slug`, `body_md`, `status` (RLS-filtered to `published`)
- `economy_map.timeline_entries`: `block_slug`, `event_date`, `what_shifted`, `why_it_mattered`, `source_url` (RLS-filtered to `block_slug != 'unsorted'`)

### Live-tension placeholder string (Phase 2 D-21)
- The renderer detects the seed placeholder via exact string match: `if (block.live_tension === 'TBD — set via /map-tension') { /* hide tension card */ }`. Phase 10's `/map-tension` command writes a real value; until then, the card stays hidden.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 outputs (architecture lock)
- `.planning/phases/01-render-stack-diagnostic/01-FINDINGS.md` — §1 (SPA architecture confirmed); §3 (block-page publish path recommendation: extend `app.js` with new hash routes, no new container/SSR); §5 (Phase 4 bridge — what's locked, what Phase 4 owns).

### Phase 2 outputs (data contract)
- `.planning/phases/02-economy-map-schema-seven-block-seed/02-CONTEXT.md` — D-02 (Accept-Profile pattern), D-05/D-06/D-07 (RLS posture), D-13 (`blocks` is not append-only — `live_tension`, `maturity`, `current_body_version_id`, `last_synthesized_at` are mutable), D-21 (`live_tension` seed placeholder), D-23 (the seven blocks with tier/accent/sort_order).
- `supabase/migrations/033_economy_map_schema.sql` — actual schema. Read sections 4, 6, 8 (blocks, block_body_versions, timeline_entries DDL).

### Phase 3 outputs (visual contract)
- `.planning/phases/03-design-tokens/03-CONTEXT.md` — D-04 (`data-accent` selector key), D-05 (slug → accent override for `psychology-disposition` → coral), D-06 (selector isolation from edition pages).
- `docker/web/site/style-map.css` — the actual stylesheet. Phase 4 emits markup that matches its selectors: `.maturity-pill[data-stage="N"]`, `.timeline-entry`, `.timeline-line1`, `.timeline-line2`, `.timeline-source`, `[data-accent="..."]`, `.timeline-entry:not([data-source]) .timeline-source`.
- `docker/web/site/tokens-preview.html` — reference markup for the pill and timeline-entry. Phase 4's renderer should emit matching structure.

### Build spec (source of truth)
- `.planning/docs/economy-map-build-spec-v2.md` §5.3 (six-part skeleton — informational; the renderer trusts body_md to carry headings 1/2/4); §6 (renderer contract; Phase 1 fulfilled the "shape confirmed in Phase 0" clause).

### Project / milestone context
- `.planning/PROJECT.md` — constraint: "all synthesis LLM calls route through `llm-proxy:8200`" (not applicable to Phase 4 — the renderer reads, doesn't synthesize); "editorial framing in human hands" (the storyline header in D-12 honors this — operator owns it via PR).
- `.planning/REQUIREMENTS.md` §RNDR-01..07 — the seven phase requirements.
- `.planning/ROADMAP.md` §"Phase 4" — five success criteria.

### Codebase analog files (read before writing code)
- `docker/web/site/app.js` — existing SPA structure: `getRoute()` (lines 89–98), `route()` (lines 299–307), `showView()` (lines 100–104), `loadList()` and `loadEdition()` as query/render analogs, `setMode()` for the mode toggle pattern. Phase 4 extends these — does NOT rewrite.
- `docker/web/site/index.html` — DOM containers: `#list-view`, `#reader-view`, `.hero`, `.mode-toggle`. Phase 4 adds new `<div id="map-view">`, `<div id="block-view">`, `<div id="status-view">` siblings under `<main>`.
- `docker/web/site/style-shared.css` — the inherited typography (Courier New body, Georgia headlines, max-width 720px container). Phase 4 inherits all of this verbatim; no new typography rules (TOKN-04 still in force).

</canonical_refs>

<deferred>
## Deferred Ideas

Captured during discussion; NOT in Phase 4 scope.

| Idea | Status | Rationale |
|------|--------|-----------|
| Supabase Realtime push subscriptions on `timeline_entries` for instant Evolution updates | Deferred to v2 polish | D-05 — hybrid pull + idle-poll covers RNDR-06 for v1 with much lower implementation complexity. Promote when v1 ships and operator wants sub-second feel. |
| Per-mode block body content (`body_md_impact` column + technical/strategic toggle on block pages) | Deferred to v2 | D-03 — `block_body_versions` has one `body_md` in v1. Adding a parallel column requires Phase 2 schema extension + Phase 7 synthesis fork + UI re-enable. Defer until milestone-level decision on whether the strategic/technical lens applies to map content. |
| `/map-storyline` Telegram command to edit hub storyline header without redeploy | Deferred to v2 operator polish | D-12 — hardcoded in `app.js` for v1; promotes naturally to `economy_map.site_copy` table + command surface in v2 if the operator wants no-deploy edits. |
| Block-page sub-route `/map/<slug>/timeline` for full timeline history as its own page | Deferred — revisit if needed | D-11 — 30-cap + "Show all" button handles v1. If a block accumulates 100+ entries and the "Show all" UX becomes awkward, promote to a sub-route. |
| Crawlable URLs / SSR / share-card metadata | Out of v1 scope per build spec §8 | Hash routes don't reach the server; SEO and rich-link previews require SSR or static rendering. Build spec explicitly defers; v2 design pass owns. |
| "Last synthesized at" stamp on hub tiles | Deferred to v2 polish | D-14 — hub tiles stay minimal (title + subtitle + pill). Status page surfaces synthesis-recency. Promote if operator wants the hub to double as a status overview. |
| Active-route highlight on the nav "Map" link | Deferred to v2 polish | D-04 — quiet text link in v1, no toggle/active styling. Promote with a generic nav-active treatment when v2 nav polish happens. |
| Status page rows linking to block pages | Deferred to v2 polish | D-15 — status is a snapshot in v1; hub owns navigation. Promote if operator wants both surfaces to be navigation entry points. |
| Tier-grouping in `app.js` based on a `tiers` config (not hardcoded "SUBSTRATE/BEHAVIOR/FRAME") | Defer — not load-bearing | The three tiers are stable (Phase 2 D-23 locked); a config doesn't earn its complexity in v1. Promote only if v2 adds a fourth tier. |
| Negotiation as its own block + own block page | Deferred to v2 milestone | Per `.planning/PROJECT.md` Out of Scope + ROADMAP — negotiation lives inside `payments-settlement` until real bid/ask behavior exists. |
| Bespoke typography / page chrome for map surfaces | Deferred to v2 design pass | TOKN-04 (Phase 3) and `.planning/PROJECT.md` Out of Scope — substance over design for v1. |

</deferred>