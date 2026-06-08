---
phase: 11-design-system-nav-shell
plan: 02
subsystem: ui
tags: [nav-shell, sticky-header, css-custom-properties, vanilla-js-spa, hash-router, route-derived-active-state]

# Dependency graph
requires:
  - phase: 11-01 (design-system token layer)
    provides: style-base.css :root token layer (--accent/--accent-soft/--accent-ink/--ink-soft/--line/--mono/--radius-sm/--radius-btn/--space-* etc.), serif 18px/1.62 body, .page-title/.eyebrow classes, dark body.technical/strategic var blocks + body-level Courier already retired, style-base.css loaded first in index.html
provides:
  - Persistent sticky 3-tab <header> nav shell (brand · Newsletter / Agent Economy / What is AgentPulse · Subscribe) replacing the old .top-nav
  - Route-derived active-tab state — setActiveTab(view) wired into route() (runs on load + every hashchange), driven by getRoute() not by clicks (NAV-02)
  - ← Back to [section] back-control copy on reader (Back to Newsletter) and block (Back to the map) views (NAV-03)
  - Sticky-header / tab / .tab.active / .brand+.dot / .subscribe / .backlink / ≤640px responsive CSS appended to style-base.css
affects: [12-newsletter-section-restyle, 13-agent-economy-grid, 14-about-stub-polish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Route-derived active nav state: setActiveTab(getRoute().view) toggles .active + aria-current inside route(); never click-derived"
    - "Tabs are plain hash links (#/ #/map #/about) driven by the real hash router — NOT the mockup's data-view/go() click router"
    - "Defensive null-checks on querySelectorAll('.tab') before use (showView idiom); no-op safely when no tabs"
    - "Nav-shell theme under :root tokens only (no body.x-scoped selectors); two locked literals (header bg + active-tab border)"

key-files:
  created: []
  modified:
    - docker/web/site/index.html
    - docker/web/site/app.js
    - docker/web/site/style-base.css

key-decisions:
  - "Tab center region uses a .tabs wrapper with margin-right:auto to push Subscribe right (flex), so the D-03 ≤640px media query can set .tabs{order:3;flex-basis:100%;overflow-x:auto} cleanly"
  - "data-tab attribute (newsletter/map/about) is the stable JS hook so setActiveTab matches without parsing href"
  - "#/about tab ships now though getRoute() has no #/about case (falls through to list) — local-only no-op under batch-deploy D-01; route lands Phase 14"
  - "Status-view back-control NOT added this plan: status-view has no static back-link in index.html and renderStatus() renders only tier sections; the plan's action scope covers only the reader/block static back-links, and the status ← Back to the map copy is left for MANUAL local verification (D-01), not a grep gate"

requirements-completed: [NAV-01, NAV-02, NAV-03, NAV-04]

# Metrics
duration: 2min
completed: 2026-06-04
---

# Phase 11 Plan 02: Nav Shell Summary

**Persistent sticky 3-tab nav shell — brand · Newsletter / Agent Economy / What is AgentPulse · Subscribe — replacing the old .top-nav, with route-derived active-tab state (setActiveTab wired into the existing hash router's route()), ← Back to [section] back-controls, the retired plain Map link, and a ≤640px wrap-to-scrollable-row responsive nav, all styled against the Plan-01 :root tokens.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-06-04T17:50:02Z
- **Completed:** 2026-06-04T17:52Z (approx)
- **Tasks:** 3
- **Files modified:** 3 (0 created, 3 modified)

## Accomplishments
- **index.html**: replaced `.top-nav` (brand + plain `.nav-map-link` Map + Subscribe) with a sticky `<header>` containing a `.brand` (9px `.dot` + `AGENTPULSE` wordmark linking `#/`), a `.tabs` group of three `class="tab"` anchors in locked order/copy (`Newsletter` href="#/" data-tab="newsletter", `Agent Economy` href="#/map" data-tab="map", `What is AgentPulse` href="#/about" data-tab="about"), and a `SUBSCRIBE` button retaining `onclick="scrollToSubscribe()"`. Deleted the plain Map link (NAV-04). Swapped the reader back-link `← All editions` → `← Back to Newsletter` and the block back-link `← Map` → `← Back to the map`, both moved to `class="backlink"`. Hero + mode toggle left structurally intact (D-02); view containers / subscribe / footer / scripts untouched.
- **app.js**: added top-level `setActiveTab(view)` mapping the `getRoute()` view → tab per the UI-SPEC table verbatim (`list`/`reader`→`newsletter`, `map`/`block`/`status`→`map`, `about`→`about`, `unsubscribe`→none), toggling `.active` + `aria-current="page"` on `.tab` elements by `dataset.tab` with defensive null-checks. Wired `setActiveTab(r.view)` inside `route()` right after `var r = getRoute();` — runs on load and every `hashchange` via the existing registration (no new listener). `getRoute()` and `scrollToSubscribe()` unchanged.
- **style-base.css**: appended (after the Plan-01 token/typography block) the sticky `header` (translucent `rgba(250,248,245,.86)` bg + `backdrop-filter` blur + `1px solid var(--line)` bottom border, `z-index:50`), `.nav` flex row, `.brand`/`.dot`, `.tabs`, `.tab` (rest weight **400** — UI-SPEC override of mockup's 500), `.tab.active` (`var(--accent-soft)` bg + `var(--accent-ink)` text + `#ddd2ff` border + 600), `.subscribe` (solid `var(--accent)` → `var(--accent-ink)` hover, `var(--radius-btn)`), `.backlink` (mono 12.5/400 → `var(--accent-ink)` hover), and the `@media(max-width:640px)` D-03 block (`.nav{flex-wrap:wrap}` + `.tabs{order:3;flex-basis:100%;overflow-x:auto}`). All `:root` tokens except the two locked literals; weights 400/600 only; no `body.x`-scoped selectors.

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace .top-nav with sticky 3-tab header + swap back-link copy (index.html)** — `d71a8c5` (feat)
2. **Task 2: Add route-derived setActiveTab() and wire into route() (app.js)** — `f667f4b` (feat)
3. **Task 3: Append sticky header / tab / backlink / responsive nav styles (style-base.css)** — `18bb06c` (feat)

## Files Created/Modified
- `docker/web/site/index.html` (modified, +17/−11) — sticky `<header>` nav shell replacing `.top-nav`; `← Back to Newsletter` / `← Back to the map` back-links with `.backlink` class; old `.nav-map-link` deleted; hero + toggle intact.
- `docker/web/site/app.js` (modified, +32) — top-level `setActiveTab(view)` + `setActiveTab(r.view)` call inside `route()`; getRoute/scrollToSubscribe untouched; no duplicate listeners.
- `docker/web/site/style-base.css` (modified, +123) — sticky nav-shell / tab(400 rest / 600 active) / `.subscribe` / `.backlink` / ≤640px D-03 responsive styles, all referencing `:root` tokens.

## Decisions Made
- **`.tabs` wrapper with `margin-right:auto`** pushes the Subscribe button to the right in the flex `.nav` row, which also makes the D-03 mobile media query clean (`.tabs{order:3;flex-basis:100%;overflow-x:auto}` drops the tabs to a full-width scrollable row while brand + Subscribe stay on the top row).
- **`data-tab` is the JS hook**, not the href — `setActiveTab` matches `el.dataset.tab` against the mapped target so it never parses or interpolates the hash into markup (keeps the T-11-03 threat at "accept": class-toggle + setAttribute only, no innerHTML/no hash-to-DOM).
- **Status-view back-control deferred to manual verification, not implemented here.** The block/reader back-links are static HTML and grep-verified. The status view (`#/status`) has no static back-link in `index.html`, and `renderStatus()` renders only the three tier sections into `#status-content` (no back-control markup). The plan's Task 1 action scope explicitly covers only the reader/block static back-links; its acceptance criteria note the status `← Back to the map` copy is confirmed by MANUAL local verification (load `#/status`) under D-01, not the grep gate. No status back-link was added (it would exceed this plan's stated edit scope and there is no existing JS-rendered back-control to re-copy). Flagged here for the Phase-11 local verification pass / a later plan.

## Deviations from Plan
None — plan executed exactly as written. All three tasks were implemented per their `<action>` and `<acceptance_criteria>`; every `<verify>` gate (including `node --check docker/web/site/app.js`) returned PASS. No Rule 1–4 deviations were triggered.

## Verification (local-only, D-01 batch deploy — NO build/deploy this phase)
- **Task 1 grep gate:** PASS — `Agent Economy`, `What is AgentPulse`, `scrollToSubscribe()`, `Back to Newsletter`, `Back to the map` present; `nav-map-link` and `All editions` absent. Hero (`hero-headline`/`mode-toggle`/`mode-subtitle`) present; old `Map</a>` plain link gone; 3 `class="tab"` elements.
- **Task 2 gate:** PASS — `node --check docker/web/site/app.js` exits 0; `function setActiveTab` defined; `setActiveTab(r.view)` called inside `route()` (line 776); `dataset.tab` used. DOMContentLoaded count unchanged (1); no new hashchange listener; getRoute()/scrollToSubscribe() unchanged.
- **Task 3 gate:** PASS — `position:sticky`, `backdrop-filter`, `.tab.active`, `max-width:640px`, `overflow-x:auto`, `.backlink` all present. Locked literals `rgba(250,248,245,.86)` + `#ddd2ff` present; `.tab` rest `font-weight:400`; `var(--accent-soft)`/`var(--radius-btn)`/`var(--mono)` referenced; zero `font-weight:500`/`:700`; zero `body.technical`/`body.strategic` selectors.
- **Manual local checks (not grep-gated, D-01):** loading `#/edition/{n}` lights Newsletter; `#/map/{slug}` and `#/status` light Agent Economy; `#/` lights Newsletter (route-derived active state); the status view's `← Back to the map` copy (see Decisions — not implemented this plan); narrow viewport ≤640px tab wrap. These require loading the site in a browser/local container and are deferred to the Phase-11 local verification pass.
- **No build/deploy command run** (D-01): no `docker compose ... up --build`, no deploy script.

## Known Stubs
None. The `#/about` tab is an intentional ship-ahead (route added Phase 14 per ABOUT-01) — documented in CONTEXT D-02/Planner Notes as a local-only no-op under batch-deploy, not a stub blocking this plan's goal (the nav shell is fully functional for the three live routes).

## Issues Encountered
- **`grep` aliased to `ugrep`** in this environment (carried over from Plan 01): leading `← …` / `--` patterns and `grep -vq` semantics differ from GNU grep. Worked around by using `grep -qF` (fixed-string) for all literal checks. All task gates return PASS as written.

## User Setup Required
None — no external service configuration, no env vars, no build step, no deploy this phase (D-01 batch deploy). The nav shell is static markup + a class-toggling router hook + CSS; no new network call, endpoint, dependency, or credential path (Subscribe reuses `scrollToSubscribe()` verbatim).

## Next Phase Readiness
- The persistent sticky shell is in place and is the foundation every later v2.0 section inherits: Phase 12 (newsletter restyle + mode-toggle relocation, TGL-01/02) restyles the list/article views beneath this header and relocates the toggle out of the hero; Phase 13 (Agent Economy grid, MAP-01..04) renders the economy cards under the Agent Economy tab; Phase 14 (ABOUT-01) adds the `#/about` route + stub that the already-shipped `What is AgentPulse` tab points to.
- Route-derived active state already lights the correct tab for every existing route; when Phase 14 adds the `#/about` case to `getRoute()`, `setActiveTab` lights the About tab with zero further wiring (the `about`→`about` mapping is already present).
- Known acceptable rough edge (D-01 batch-deploy): the newsletter/article/map component rules in `style-shared.css`/`style-map.css` still render rough on the new light base locally between phases; Phases 12–13 own their final restyle. No live deploy performed.

## Self-Check: PASSED

- Files: index.html, app.js, style-base.css, 11-02-SUMMARY.md all FOUND on disk.
- Commits: d71a8c5, f667f4b, 18bb06c all FOUND in git log.
- All three task `<verify>` grep gates return PASS; `node --check docker/web/site/app.js` exits 0.

---
*Phase: 11-design-system-nav-shell*
*Completed: 2026-06-04*
