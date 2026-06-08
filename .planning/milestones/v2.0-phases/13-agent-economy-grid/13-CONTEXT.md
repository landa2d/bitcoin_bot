# Phase 13: Agent Economy Grid - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Re-render the **Agent Economy** section as a tight, responsive **2-column grouped card grid** driven by the canonical `economy_map.blocks` tier taxonomy — replacing the current long vertical scroll so related blocks sit together with minimal scrolling (MAP-01..04). **Frontend-only** — no backend/pipeline/Supabase/content/schema changes; the grid reads the *existing* block fields.

**In scope (confirmed this discussion):**
1. **Hub grid** — the `renderHub()` output becomes a responsive 2-col-desktop / 1-col-mobile card grid (~16px gaps), grouped under the existing `substrate / behavior / frame` mono section labels, with the full-width DEFERRED treatment (MAP-01..04).
2. **Single-block detail view** (`renderBlock()`) — restyled onto the serif/light system as a **restrained system pass** (NOT a second magazine treatment): serif body prose, light surfaces, progress dots in place of the maturity pill, existing structure (header / live-tension card / markdown body / Evolution timeline) restyled rather than redesigned. Pairs with the hub the way Phase 12 paired list + article.
3. **`#/status` view** (`renderStatus()`) — **light de-dark pass only**: strip the dark bg / `Courier New` / per-tier accent so a deep-link renders cleanly on the light system. No layout redesign (it is no longer a nav tab — deep-link-only in the new shell).
4. Consequent **`style-map.css` cleanup** — the dark theme is de-darkened across all three of its consumer views (hub tiles, block detail, status). Exact disposition (delete-and-fold into `style-base`/`style-shared` vs lighten-in-place) is planner/UI-SPEC discretion.

**This phase does NOT:** change any data fetch / schema / block content / synthesis logic; add or remove blocks; change the maturity or body data; touch the Newsletter views (Phase 12, done) or the About page (Phase 14); add a `status` column or any new DB field (the DEFERRED rule is derived from existing data); deploy to prod (batch deploy ships after Phase 14, per Phase 11 D-01).

</domain>

<decisions>
## Implementation Decisions

Visual/pixel-level specifics are deferred to the downstream **UI-SPEC** (`/gsd-ui-phase 13`); these decisions set the direction it must honor. The mockup is an **intent reference, not markup to copy** — and its placeholder block names (Substrate / Coordination / Marketplaces) are explicitly NOT ours.

### Restyle scope (the area discussed)
- **D-01: Scope = hub grid + single-block detail view.** Phase 13 restyles BOTH the Agent Economy hub (the new card grid) AND the per-block reading view — the full "Agent Economy section," mirroring how Phase 12 restyled list + article together. Chosen over hub-only because batch-deploy means any view left on the dark `style-map.css` ships looking broken, and clicking a block from the new grid must not drop into a dark/Courier page.
- **D-02: `#/status` = light de-dark pass.** Strip dark bg / Courier / tier-accent so a deep-link renders on the light system; no layout redesign. It is no longer a nav tab (the 3 tabs are Newsletter / Agent Economy / About) and nothing links to it — but it shares `style-map.css` rules with D-01's views, so de-darkening it is cheap insurance against a broken-looking deep-link.
- **D-03: Block detail = restrained system pass, not a second magazine.** The block reading view adopts the design system (serif body prose — same migration as Phase 12's article; light surfaces; dots replacing the pill) but KEEPS its existing structure (header, live-tension card, markdown body via `marked.parse`, Evolution timeline) restyled, not redesigned. No mono-kicker/display-title/lead/blockquote magazine layer — that stays a Newsletter-only treatment. Fits a reference reading view (only 2 of 7 blocks have a body today).

### Deferred-block rule (MAP-04 — editorial, operator-decided)
- **D-04: DEFERRED = no synthesized body.** A block is rendered DEFERRED (full grid width, "DEFERRED" tag, empty progress dots) when **`current_body_version_id is null`** (equivalently `last_synthesized_at is null`). Data-derived, requires no schema change, and **self-updating** — a block leaves the DEFERRED state the moment it is first synthesized. Chosen over a hardcoded editorial list (which would diverge from real content state) and over `maturity === 'nascent'` (which marks 6/7 and ties deferral to maturity rather than whether prose exists).
- **D-04a (consequence, accepted):** With today's data this marks **5 of 7 blocks DEFERRED** (only `identity-trust` and `governance-accountability` have bodies), so the live grid is mostly full-width rows until more blocks fill in. Accepted as honest + on-brand with the project's "silence is the enemy — show what isn't written yet" value. The 2-col grid structure must still be built correctly so it densifies automatically as synthesis fills blocks.

### Tier accents (defaulted — COLOR-02 already locks this; not re-discussed)
- **D-05: Collapse the 4 tier colors to the single violet accent.** The map's current per-tier `teal / purple / coral / gray` accents (`style-map.css` `--accent-tier` cascade) are replaced by the single `--accent` violet on card left-borders (3px) and progress dots, per the Phase 11 COLOR-02 lock ("one accent only … card borders, progress dots; no second brand color"). Tiers are distinguished **only by their mono section label** — no per-tier color survives. The `data-accent` attribute / on-dark variant machinery is retired with the dark theme.

### Section header (defaulted; planner/UI-SPEC discretion on exact treatment)
- **D-06: Mockup-style serif page-title + mono sub-line.** Adopt a serif page-title ("The Agent Economy") + a mono sub-line for the hub, matching Phase 12's D-07 minimal-header pattern (reuse the Phase 11 `.page-title` / `.eyebrow` classes). Keep the existing `HUB_STORYLINE` as a one-line editorial frame. Exact wording, whether the sub-line carries an "updated {date}" stamp, and storyline placement are UI-SPEC discretion within the system.

### Progress dots (implementation note, not a new decision)
- The existing 5-segment `renderMaturityPill()` (`MATURITY_STAGE` 1–5, keyed off `maturity`) **is** the "progress dots" of MAP-02/MAP-04 — repurpose it: filled dots = maturity stage on a normal card; all-empty dots on a DEFERRED card. Reused verbatim by hub + block detail; only its color source changes (per D-05) from `--accent-tier` to `--accent`.

### Claude's Discretion / left to UI-SPEC + planner
- `style-map.css` disposition (delete-and-fold vs lighten-in-place) — D-01..D-03 require it de-darkened; the file boundary is mechanical.
- Grid CSS structure: per-tier-section grid vs one continuous grid; how an odd block count (substrate/behavior each have 3) and the full-width DEFERRED cards (`grid-column: 1 / -1`) flow; mobile 1-col collapse. Default to the mockup's per-section-grid + `span2`-style full-width mechanism (intent, not copied markup).
- Exact gap / radius (~7–10px) / hover-lift values, card internal spacing, DEFERRED tag styling, section-label casing — UI-SPEC, within the Phase 11 token system.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design system (reused, locked by earlier phases — do not re-derive)
- `.planning/phases/11-design-system-nav-shell/11-UI-SPEC.md` — locked palette hexes, the 7-item single-accent reservation list (COLOR-02), serif/mono type scale (weights 400/600), spacing (4px grid) + radius tokens (3/7/8/10), and the `.page-title` / `.eyebrow` display classes the hub header reuses.
- `docker/web/site/style-base.css` — the Phase 11 `:root` light-token layer + reusable display classes; loaded first (cascade control).
- `.planning/phases/12-newsletter-section-restyle/12-CONTEXT.md` — the serif-prose migration pattern (TYPE-01: mono→serif on body `p/ul/ol/li/td`) the block-detail body reuses (D-03); the D-07 minimal-header pattern the hub header mirrors (D-06).

### Milestone intent & requirements
- `.planning/docs/REDESIGN_BRIEF.md` §5 "Agent Economy map" (2-col grid, ~16px gaps, bordered card with serif title + one-line description + progress dots, 3px `--accent` left-border, mono section labels using OUR grouping, deferred = full-width + DEFERRED tag + empty dots), §4 (one accent only), §57–58 (~7–10px radius, minimalist not sparse), §68 (more blocks above the fold).
- `.planning/docs/agentpulse-redesign-mockup.html` — visual **intent** reference only. Relevant CSS: `.grid` (`repeat(2,1fr)`), `.card`, `.card.span2{grid-column:1/-1}` (deferred full-width), `.dots i` / `.dots i.fill`, `.section-label`, mobile `@media(max-width:640px){.grid{grid-template-columns:1fr}}`. Its block NAMES are placeholders — use ours.
- `.planning/REQUIREMENTS.md` — MAP-01, MAP-02, MAP-03, MAP-04 (this phase).
- `.planning/ROADMAP.md` §"Phase 13: Agent Economy Grid" — goal + 4 success criteria.
- `.planning/PROJECT.md` — "Editorial framing in human hands" constraint (why D-04 was operator-decided); out-of-scope notes (Regulation = lightly-populated closing frame; Negotiation folded into Payments, not its own block; mockup placeholder taxonomy is NOT ours).

### Codebase (the surface this phase edits)
- `docker/web/site/app.js` — `renderHub()` (`:430`, already tier-grouped; convert tier-sections → card grid + DEFERRED treatment), `renderTile()` (`:447`, the `.block-tile` anchor → card), `renderMaturityPill()` (`:391`, = the progress dots; recolor to `--accent`), `renderBlock()` (`:540`, the block reading view — restrained pass), `renderStatus()` (`:672`, de-dark pass), `TIER_LABELS` (`:41`), `MATURITY_STAGE` (`:38`), `LIVE_TENSION_PLACEHOLDER` (`:46`, tension hidden while placeholder — all 7 are today). **Do not** change the `economy_map` fetch logic or add status filters (RLS is the boundary, per the existing D-16/D-17 comments).
- `docker/web/site/style-map.css` (348 lines) — the **dark theme to retire/lighten**: per-tier accent hex + on-dark variants (`:20`–`:43`), `.maturity-pill` segment fills keyed off `--accent-tier` (`:55`–`:75`), `Courier New` on `.tier-label` and block surfaces (`:161`, `:176`), `.block-tile` (`:194`), `.tier-section` / `.tier-label` (`:172`+). This file's three consumer views (hub, block, status) are exactly Phase 13's scope.
- `docker/web/site/index.html` — `#map-view` (`.content-area`), `#block-view` (`#block-content` + static `← Back to the map` backlink), `#status-view` (`#status-content`). The 3-tab nav (`:22`–`:25`) has no `#/status` tab (confirms D-02's "deep-link-only").
- `docker/web/site/style-shared.css` — where lightened map/block/status rules may land (planner discretion on file org).

### Live data (read-only reference — confirms D-04 / D-04a)
- `economy_map.blocks` (7 rows). Has-body (`current_body_version_id` not null): `identity-trust` (contested), `governance-accountability` (nascent) — render as normal cards. No body → DEFERRED: `memory-context`, `payments-settlement`, `autonomy-control`, `psychology-disposition`, `regulation-legal`. **No `status` column exists** (columns: id, slug, tier, title, subtitle, accent, sort_order, live_tension, maturity, current_body_version_id, last_synthesized_at, created_at). `live_tension` is the placeholder on all 7 (tension card hidden everywhere today). Access via direct PostgREST + `Accept-Profile: economy_map` (supabase-js `.schema('economy_map')` in `app.js`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`renderHub()` already groups by the canonical taxonomy** (`app.js:430`) — `substrate / behavior / frame` filtered arrays + `<section class="tier-section"><h2 class="tier-label">`. MAP-03 ("grouped under section labels using the canonical block taxonomy") is *already satisfied structurally*; Phase 13 restyles tier-sections into the grid, it does not re-derive the grouping.
- **`renderMaturityPill()`** (`app.js:391`) — a 5-segment indicator keyed off `MATURITY_STAGE[maturity]` (1–5). This IS the MAP-02 "progress dots." Reuse for hub + block detail; only the fill color source changes (D-05). Empty dots (stage 0 / no fill) = the DEFERRED card state (MAP-04).
- **Phase 11 `.page-title` / `.eyebrow`** classes — ready-made serif display + mono kicker for the hub header (D-06).
- **Phase 12's serif-prose migration** — the exact `p/ul/ol/li` mono→serif rules the block-detail markdown body reuses (D-03).

### Established Patterns
- **Hand-authored CSS, no build step** — cascade order in `index.html` is the control (`style-base.css` first). New/lightened rules are just more `<link>`/sections.
- **`data-accent` + `--accent-tier` cascade** is the dark theme's per-tier coloring mechanism — Phase 13 RETIRES it (D-05); cards use the single `--accent`. Don't keep the `[data-accent]` selectors alive on the light system.
- **Whole-anchor click target** (`.block-tile` is one `<a href="#/map/{slug}">`) — preserve this when converting the tile to a card (the card is the link).
- **No monospace body paragraphs** (TYPE-01) — block-detail body prose is serif; mono stays for chrome/labels/metadata/code only.
- **No defensive status filters on `blocks`** — RLS is the boundary (per the existing D-16/D-17 comments). Don't add `.eq('status',...)`.

### Integration Points
- The grid replaces the tier-section vertical stack inside `#map-view .content-area`; the DEFERRED full-width card uses `grid-column: 1 / -1` within its tier's grid.
- The block-detail restyle sits under the existing static `← Back to the map` backlink in `#block-view`; `renderBlock()` keeps emitting header/tension/body/evolution, just on restyled CSS.
- De-darkening `#status-view` touches the same `style-map.css` tier-section/tier-label rules the hub uses — change once, both benefit.

</code_context>

<specifics>
## Specific Ideas

- Grid intent from the mockup: 2-col desktop grid, ~16px gaps, bordered cards with a 3px violet left-border, subtle hover lift, mono section labels, deferred card full-width with a mono "· DEFERRED" tag and all-empty dots; mobile collapses to 1 column. (Intent — not markup to copy; block names are ours.)
- DEFERRED state today: 5 of 7 cards (memory-context, payments-settlement, autonomy-control, psychology-disposition, regulation-legal). Normal cards: identity-trust, governance-accountability.
- Block detail stays a "restrained" reading view — one serif display style, no second magazine layer; the magazine treatment is Newsletter-only.

</specifics>

<deferred>
## Deferred Ideas

- **Full restyle of the `#/status` view** — done only as a light de-dark pass this phase (D-02); a proper status-page redesign (and re-linking it into the nav, if ever wanted) is out of scope and not currently needed (it's deep-link-only).
- **A real `status`/`deferred` data column** — explicitly NOT added (frontend-only); the DEFERRED state is derived from `current_body_version_id` (D-04). If the editorial model later needs an explicit "intentionally parked" flag distinct from "not yet synthesized," that's a backend change for a future milestone.
- **Negotiation as its own block / Regulation as a richer frame** — backend/content evolution, parked in v-next per PROJECT.md out-of-scope; the grid simply reflects whatever `economy_map.blocks` contains.
- **Site-wide spacing/radius polish pass + About page** → Phase 14 (POLISH-01, ABOUT-01). Phase 13 applies the grid's own radii within the system but the global consistency sweep is Phase 14.
- **Dark mode (DARK-01)** → v-next, out of v2.0.

### Reviewed Todos (not folded)
The 7 pending todos in `.planning/todos/pending/` are all v1.0 **backend** follow-ups (analyst `predictions.title` bug, soft spending-cap hardening, `transfer_between_agents` RPC search_path, Phase 05 intake-classifier review follow-ups, economy-map telegram/synthesis, research stale-trigger). None touch the v2.0 frontend grid — reviewed and **not folded**, consistent with the Phase 11/12 decision.

</deferred>

---

*Phase: 13-agent-economy-grid*
*Context gathered: 2026-06-04*
