# Phase 4: Hub, Block, and Status Renderer — Discussion Log

**Discussion date:** 2026-05-27
**Mode:** default (single-question turns per area; 3–4 turns per area)
**Areas selected:** all 4 (Hub URL + SPA shell coexistence, Live re-render mechanism, Block page presentation, Hub seven-block visual + storyline header)
**Status:** complete

---

## Area 1 — Hub URL + SPA shell coexistence

### Q1: Where does the hub live, and what happens to the existing edition-list home?

**Options presented:**
- `/map` coexists; `/` stays edition list
- `/` becomes hub; editions move to `/editions`
- Operator-only map; `/` unchanged

**User selected:** `/map` coexists; `/` stays edition list

**Note:** Selected with the previewed URL map (`#/`, `#/edition/N`, `#/map`, `#/map/<slug>`, `#/status`) and nav shape (`[AGENTPULSE · Map] [SUBSCRIBE]`). Drives D-01 + D-04.

### Q2: What happens to the existing hero on `/map`, `/map/<slug>`, `/status`?

**Options presented:**
- Reuse the hero with map-specific copy
- Hide hero on map pages; render header inline
- Keep hero, drop the mode toggle on map pages

**User selected:** Keep hero, drop the mode toggle on map pages

**Note:** Rationale endorsed by user: block_body_versions has one body in v1 with no per-mode variant. Hero kept for visual continuity. Drives D-02 + D-03. Mode toggle hidden via a `setMapToggleVisibility(false)` mechanism; body class still drives the token cascade.

### Q3: How discoverable is `/map` from the existing site?

**Options presented:**
- Add 'Map' link to nav
- Operator-only via direct URL
- Footer link only

**User selected:** Add 'Map' link to nav

**Note:** Confirms a quiet text link in the nav-left cluster, not a primary button or toggle. Drives D-04.

---

## Area 2 — Live re-render mechanism (RNDR-06)

### Q1: How should the Evolution section detect new timeline entries while the operator is on a block page?

**Options presented:**
- Next-navigation read (pull)
- Supabase Realtime subscription (push)
- Hybrid: pull on navigation + light poll while idle

**User selected:** Hybrid: pull on navigation + light poll while idle

**Note:** Drives D-05 (hybrid mechanism, no Realtime in v1). Realtime push deferred to v2.

### Q2: Hybrid poll cadence — how often / what scope?

**Options presented:**
- 60s, after first 60s on page
- 30s, immediately
- Visibility-aware: 30s when tab visible, off when hidden
- Only the Evolution section, not the whole block

**User selected:** Only the Evolution section, not the whole block

**Note:** The user picked the scope-defining option first, signaling that poll target matters more than cadence. The poll re-queries timeline_entries only — block body / live_tension / blocks row are NOT re-fetched. Drives D-06.

### Q3: And the cadence — how often does the Evolution-only poll fire?

**Options presented:**
- 60s, visibility-aware
- 30s, visibility-aware
- 60s flat (no visibility check)

**User selected:** 60s, visibility-aware

**Note:** Drives D-07. `visibilitychange` listener pauses interval when tab hidden; `hashchange` listener clears interval on route change.

---

## Area 3 — Block page presentation

### Q1: Block page wrapper composition — what's the visible order?

**Options presented:**
- Title → pill → tension → body → Evolution
- Title → pill → body → tension → Evolution
- Title → tension → body → Evolution; pill in sidebar/inline

**User selected:** Title → tension → body → Evolution; pill in sidebar/inline

**Note:** Tension leads as the editorial hook before any synthesized prose. Pill moves into the title row (right-aligned), not the main flow. Drives D-08 + D-09.

### Q2: Empty-state behavior — in v1 no block has a published body yet (until Phase 7+9 ship). What does the block page render?

**Options presented:**
- Show the wrapper; placeholder under body
- Hide tension + body until populated; show Evolution + pill
- Show 'Under construction' banner until first synthesis

**User selected:** Hide tension + body until populated; show Evolution + pill

**Note:** Quiet absence, not scaffolding. Renderer detects the seed placeholder `'TBD — set via /map-tension'` on `live_tension` and `null` on `current_body_version_id`. Drives D-10.

### Q3: Evolution timeline cap on the block page — limit or show all?

**Options presented:**
- Show all entries, no cap
- Cap at 30 newest; 'Show all' button to expand
- Cap at 30 newest; full history at `/map/<slug>/timeline`

**User selected:** Cap at 30 newest; 'Show all' button to expand

**Note:** Drives D-11. Show-all is one-shot per page load. Sub-route alternative deferred — promote only if a block accumulates enough entries that the expand UX becomes awkward.

---

## Area 4 — Hub seven-block visual + storyline header

### Q1: How are the seven blocks visually arranged on the hub?

**Options presented:**
- Grouped by tier (3+3+1)
- Flat list in sort_order
- Grid (4-column or 3-3-1)

**User selected:** Grouped by tier (3+3+1)

**Note:** Drives D-13. Three sections — SUBSTRATE, BEHAVIOR, FRAME — with tier-label headings. Blocks render in sort_order ascending within each section.

### Q2: Storyline header (top of `/#/map`) — where does the editorial copy come from?

**Options presented:**
- Hardcoded in `app.js` (Claude-authored initial copy; operator edits in code)
- DB-driven via a new `economy_map.site_copy` table
- Defer — ship the hub without storyline header in v1

**User selected:** Hardcoded in `app.js`

**Note:** Drives D-12. Simplest; ships as a string constant near the top of `app.js`. DB-driven option (`/map-storyline` Telegram command + `economy_map.site_copy` table) explicitly deferred to v2 operator polish.

### Q3: Block tile content on the hub — what's inside each of the 7 tiles?

**Options presented:**
- Title + subtitle + maturity pill; whole tile is the link
- Title + pill only; subtitle hidden until hover
- Title + subtitle + pill + `last_synthesized_at`

**User selected:** Title + subtitle + maturity pill; whole tile is the link

**Note:** Drives D-14. Anchor wraps the entire tile. Tier accent renders as a left-border stripe via `data-accent`. Subtitle always visible (clarity during empty v1 state).

---

## Deferred Ideas (captured for later phases)

| Idea | Surfaced via | Status |
|------|--------------|--------|
| Supabase Realtime push subscriptions | Area 2 Q1 alternative | Deferred to v2 polish |
| Per-mode block body (`body_md_impact`) + toggle | Area 1 Q2 implication | Deferred to v2 |
| `/map-storyline` Telegram command | Area 4 Q2 alternative | Deferred to v2 operator polish |
| `/map/<slug>/timeline` sub-route | Area 3 Q3 alternative | Deferred — revisit only if needed |
| Crawlable URLs / SSR / share-card metadata | Phase 1 §4.3 carried forward | Out of v1 (build spec §8) |
| "Last synthesized" stamp on hub tiles | Area 4 Q3 alternative | Deferred to v2 polish |
| Active-route highlight on nav "Map" link | Area 1 Q3 implication | Deferred to v2 polish |
| Status rows linking to block pages | Discretion in D-15 | Deferred to v2 polish |
| Tier-grouping driven by config | Discretion adjacent to D-13 | Defer — not load-bearing |

---

## Claude's Discretion (planner picks)

- Exact wording of `HUB_STORYLINE` string — draft an initial version following PROJECT.md tone.
- File organization for new CSS (extend `style-map.css` vs new `style-hub.css`) — default extend.
- Empty-state for hub tiles when `last_synthesized_at` is null — default omit any "last synthesized" affordance from the tile.
- Exact `setMapToggleVisibility()` mechanism — CSS class on body vs JS style toggle.
- DOM containers in `index.html` — extend `<main>` with new view siblings.
- Whether to add a "← Map" affordance on block pages — default yes, mirrors existing `← All editions` pattern.

---

*End of discussion log. Canonical decisions live in `04-CONTEXT.md`; this log is for human reference.*
