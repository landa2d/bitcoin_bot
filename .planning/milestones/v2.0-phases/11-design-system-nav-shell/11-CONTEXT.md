# Phase 11: Design System + Nav Shell - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the **shared design-system layer** that every later v2.0 section restyle reuses:

1. **One light-mode CSS-variable palette** (`:root`) replacing the dark, mode-coupled theme — warm off-white bg, surface/ink scale, a single violet accent (COLOR-01/02).
2. **The Source Serif 4 / IBM Plex Mono typography system** — serif for everything you read (body + titles), mono for UI chrome only, one serif heading style, no monospace body, weights 400/600 only (TYPE-01/02/03).
3. **The persistent sticky 3-tab nav shell** — brand · Newsletter / Agent Economy / What is AgentPulse · Subscribe — with hash-route-derived active state on nested pages and a `← Back to [section]` control (NAV-01/02/03/04).

Vanilla-JS SPA in `docker/web/site/` (`index.html` + hand-authored CSS + `app.js` hash router); no React/Tailwind/shadcn. Ships via the v1.0-proven scoped `agentpulse-web` Docker rebuild — no new infra.

**This phase does NOT:** restyle the newsletter list/article (Phase 12), relocate the mode toggle (Phase 12), render the economy grid (Phase 13), add the `#/about` route/page (Phase 14), or touch any backend/pipeline/Supabase/content/subscribe logic.

</domain>

<decisions>
## Implementation Decisions

### Ship & Deploy Boundary
- **D-01:** **Batch deploy.** Build and verify phases 11–14 **locally**; run the scoped `agentpulse-web` rebuild and ship to the live public site **once, after Phase 14**. Consequence: the public site never shows a half-migrated state, so **Phase 11 is NOT responsible for defensively polishing views that phases 12–14 own** (newsletter list/article, map tiles, About). Those may render visually rough on the new base locally between 11 and 14 — that is expected and acceptable.

### Hero & Mode-Toggle Handling
- **D-02:** Phase 11 ships the nav shell, the `:root` token layer, **and the display/eyebrow serif type CSS classes** (`.page-title` `clamp(30px,5vw,46px)`/600; `.eyebrow` 11px mono kicker) — but **leaves the existing global `.hero` DOM** (`hero-headline` / `hero-date` / `.mode-toggle` / `mode-subtitle`) **structurally in place, recolored to the light palette.** It does **not** restructure the hero into the mockup's per-view eyebrow+page-title and does **not** move or restructure the mode toggle. That restructure + toggle relocation into the Newsletter section is **Phase 12 (TGL-01)**. Keeps Phase 11 a pure "shell + tokens" unit and avoids double-touching the newsletter views.

### Nav Shell Responsive Behavior
- **D-03:** **Mobile (≤640px): wrap tabs to a scrollable row.** Brand + Subscribe stay on the top row; the three tabs drop to a **full-width, horizontally-scrollable** row. Adopt the mockup's mechanism as intent: `.nav{flex-wrap:wrap}` + `.tabs{flex-basis:100%;overflow-x:auto}` (adapt, don't copy markup). This responsive behavior is decided **here** because the shell is built once and inherited by every later view.

### CSS Organization & Cleanup
- **D-04 (Claude's discretion — user said "you decide"):** **New base stylesheet, gut the rest progressively.** Add a new `style-base.css` (or similarly named) holding the `:root` light palette + typography + nav-shell styles, loaded **first** in `index.html` (before `style-shared.css` / `style-map.css`). **Hard constraint (not optional):** Phase 11 **must retire the dark `body.technical` / `body.strategic` color-variable blocks** in `style-shared.css` and remove the `Courier New` body font — otherwise their higher specificity overrides `:root` and COLOR-01/TYPE-01 never take effect. Tier-accent cleanup in `style-map.css` and other component cruft is **deferred** to whichever later phase (12/13) touches those views — smallest per-phase blast radius, consistent with batch-deploy.

### Claude's Discretion
- **D-04** (CSS file org) was an explicit "you decide." Flexibility retained on exact file name and load order; the **dark mode-scoped var retirement in Phase 11 is fixed**, not discretionary.

### Planner Notes (surfaced during codebase scout — implementation details, not new decisions)
- **Theme/mode decoupling:** `setMode()` (`app.js` ~68) keeps adding `body.technical`/`body.strategic` for **content re-render** (`renderArticle`/`renderList`), but after decoupling those classes **no longer drive theme** — the new palette must live under `:root`, never under `body.technical/strategic` selectors. One accent in both newsletter modes (no mode-flip).
- **Active-tab state from the route, not the click:** derive the active tab from the **current hash route** via `getRoute()` (`app.js` ~115) so deep links and nested pages light the right tab. Implement as one route→section function called inside `route()` (~742) on load and on every `hashchange`. Use the UI-SPEC route→tab table verbatim.
- **About tab ships, route doesn't (yet):** the "What is AgentPulse" tab renders in Phase 11, but `getRoute()` has no `#/about` case until Phase 14 — it currently falls through to the list view. Because of batch-deploy this is a **local-only no-op**, no live dead tab. (Phase 14 adds the route + stub per ABOUT-01.)
- **Subscribe reuse:** the Subscribe button **must invoke the existing `scrollToSubscribe()`** (`app.js` ~283) — do not build a new subscribe mechanism (NAV-01).
- **Verification is local/manual:** no JS test framework exists; v1.0 used manual live-smoke. Verify the four ROADMAP success criteria by loading the site locally (e.g. the local `agentpulse-web` container) — not on prod (batch-deploy).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design contract (READ FIRST — locks all visual/interaction specifics)
- `.planning/phases/11-design-system-nav-shell/11-UI-SPEC.md` — **The locked, approved design contract.** Exact color hex + the 7-item accent-reservation list; serif(4)/mono(3) type scale at weights 400/600; spacing tokens (4px grid) + radius set (3/7/8/10); the full Nav Shell Contract (structure, active-state mechanism + route→tab table, back-control copy); the Copywriting Contract (locked verbatim strings); the Font Loading block (Google Fonts `<link>`, 400/600 only); and the "What This Replaces" migration inventory. Do not re-derive any of this — it is settled.

### Milestone intent & requirements
- `.planning/docs/REDESIGN_BRIEF.md` — milestone brief; goals in priority order, the "inventory + confirm plan before editing" gate, and the out-of-scope list (§Out of scope).
- `.planning/docs/agentpulse-redesign-mockup.html` — visual reference for **intent, not markup to copy**. Source of the responsive nav rule (`@media(max-width:640px)` → D-03) and the per-view `.eyebrow` + serif `.page-title` structure (Phase 12 target).
- `.planning/REQUIREMENTS.md` — Phase 11 satisfies **NAV-01..04, TYPE-01..03, COLOR-01..02**. (TGL-01/02 → P12, MAP-01..04 → P13, ABOUT-01/POLISH-01 → P14; DARK-01/ABOUT-02 deferred to v-next.)
- `.planning/ROADMAP.md` §"Phase 11: Design System + Nav Shell" — goal + the 4 success criteria that define done.

### Codebase (the surface this phase edits)
- `docker/web/site/index.html` — current `.top-nav` (brand + `.nav-map-link` "Map" + Subscribe), the global `.hero` (toggle lives here today), and the five view containers (`list-/reader-/map-/block-/status-view`).
- `docker/web/site/app.js` — `getRoute()` (~115), `route()` (~742, on load + `hashchange`), `showView()` (~135), `setMode()` (~68), `scrollToSubscribe()` (~283).
- `docker/web/site/style-shared.css` — holds the dark `body.technical`/`body.strategic` color-var blocks + `Courier New` body (both retired in Phase 11) + `.top-nav` styling.
- `docker/web/site/style-map.css` — tier-accent palette (retired progressively, later phases).
- `docker/web/Caddyfile` — CSP **already whitelists** `fonts.googleapis.com` / `fonts.gstatic.com`, so the Google-Fonts `<link>` works with zero infra change (per UI-SPEC Font Loading; do not switch to self-hosting without a CSP edit).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`getRoute()` / `route()` (hash router)** — already maps hashes to views and runs on load + every `hashchange`; the route→active-tab function hooks directly into this. No new routing library needed.
- **`scrollToSubscribe()`** — the existing subscribe flow the new Subscribe button reuses verbatim (NAV-01).
- **`showView()`** — central view-toggler; the back-control visibility and active-tab update belong alongside this per-route logic.
- **Caddyfile CSP** — pre-whitelisted for Google Fonts; the UI-SPEC font `<link>` drops into `<head>` with no server change.

### Established Patterns
- **CSS custom properties drive theme**, but currently scoped under `body.technical`/`body.strategic` (dark/light coupled to the mode toggle). Phase 11 moves the palette to `:root` and decouples it from mode.
- **Defensive null-checks** on `document.getElementById/querySelector` before use (PATTERNS convention seen in `showView`) — follow it for new nav/back-control wiring.
- **Hand-authored CSS, no build step** — new `style-base.css` is just another `<link>`; load order in `index.html` is the cascade control.

### Integration Points
- New sticky 3-tab `<header>` **replaces `.top-nav`** in `index.html`; the `.nav-map-link` "Map" text link is removed (its destination becomes the Agent Economy tab — NAV-04).
- Active-tab toggling wires into `route()` (load + `hashchange`) using the UI-SPEC route→tab table.
- `← Back to [section]` control replaces the existing `← All editions` / `← Map` back-links in the nested views (NAV-03).
- The light palette must override the retired `body.technical/strategic` var blocks — i.e. those blocks are deleted, not merely shadowed.

</code_context>

<specifics>
## Specific Ideas

- The **mockup** (`agentpulse-redesign-mockup.html`) is the intent reference for two patterns specifically: its `@media(max-width:640px)` nav behavior (→ D-03) and its per-view `.eyebrow` + `.page-title` structure (the Phase 12 target; Phase 11 only defines the type classes, per D-02).
- Google Fonts loaded via the exact UI-SPEC `<link>` — Source Serif 4 + IBM Plex Mono, **weights 400 & 600 only** (500/700 deliberately not requested).

</specifics>

<deferred>
## Deferred Ideas

- **Per-view eyebrow + serif page-title restructure + mode-toggle relocation into Newsletter** → **Phase 12** (TGL-01/02). Phase 11 only defines the display/eyebrow type classes and recolors the existing hero.
- **Economy 2-col grouped card grid + tier-accent cleanup in `style-map.css`** → **Phase 13** (MAP-01..04).
- **`#/about` route + About stub page + site-wide spacing/radius polish pass** → **Phase 14** (ABOUT-01, POLISH-01).
- **Dark-mode variant (DARK-01)** and **richer About w/ pipeline diagram (ABOUT-02)** → v-next, explicitly out of v2.0.

None — discussion stayed within phase scope. (No pending todos folded: the 7 carried-forward todos are all v1.0 backend follow-ups, none in v2.0 frontend scope.)

</deferred>

---

*Phase: 11-design-system-nav-shell*
*Context gathered: 2026-06-04*
