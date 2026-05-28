---
phase: 04-hub-block-and-status-renderer
plan: 01
subsystem: ui
tags: [frontend, spa, router, design-tokens, hash-routing, supabase]

# Dependency graph
requires:
  - phase: 01-render-stack-diagnostic
    provides: SPA architecture lock — extend app.js hash router, no SSR/new container
  - phase: 02-economy-map-schema-seven-block-seed
    provides: economy_map schema (blocks/block_body_versions/timeline_entries), live_tension seed placeholder, maturity enum
  - phase: 03-design-tokens
    provides: data-accent → --accent-tier cascade, .maturity-pill + .timeline-entry token surface in style-map.css
provides:
  - "Three new hash-routed view containers (#map-view / #block-view / #status-view) under <main>, pre-hidden, each wrapping a .content-area"
  - "Quiet nav Map link (.nav-map-link) in the nav-left cluster (D-04)"
  - "Nine map-surface layout CSS selector groups in style-map.css (nav-map-link, tier-label, block-tile, block-header, block-tension, block-body, evolution, timeline-show-all, status-row)"
  - "app.js router branches for #/map/<slug>, #/map, #/status with #/map/ ordered before #/map"
  - "Three async stub loaders (loadHub/loadBlock/loadStatus) that flip view visibility via showView()"
  - "Extended showView() enumerating all five view containers + hiding the mode toggle on map routes (D-03)"
  - "Five module constants Wave 2 consumes: HUB_STORYLINE, STATUS_PAGE_HEADER, MATURITY_STAGE, TIER_LABELS, LIVE_TENSION_PLACEHOLDER"
affects: [04-02-hub-renderer, 04-03-block-renderer, 04-04-status-renderer, 04-05-idle-poll]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Hash-route ordering: longer prefix (#/map/) matched before shorter (#/map) in getRoute()"
    - "View visibility centralized in showView() — single enumeration of all containers, no parallel helpers"
    - "Map-route mode-toggle hide folded into showView() with defensive null-checks"
    - "Map-surface layout CSS extends style-map.css in place (no style-hub.css split); all tier accents via var(--accent-tier) cascade"
    - "Stub loaders call showView() so the shell works before Wave 2 renderers ship"

key-files:
  created: []
  modified:
    - docker/web/site/index.html
    - docker/web/site/style-map.css
    - docker/web/site/app.js

key-decisions:
  - "HUB_STORYLINE seeded with the PROJECT.md-aligned draft (114 chars); Wave 2 plan 02 may revise"
  - "Extended style-map.css in place per D-19 (file landed at 348 lines, under the ~300/350 soft cap after comment compaction)"
  - "Mode-toggle hide implemented via JS style.display inside showView() (not a body CSS class) — keeps the visibility decision co-located"

patterns-established:
  - "Hash-route ordering note: longer prefix before shorter to avoid startsWith() swallowing"
  - "showView() is the single source of view-container visibility + map-route chrome (mode toggle) toggling"

requirements-completed: [RNDR-01, RNDR-02, RNDR-03]

# Metrics
duration: 5min
completed: 2026-05-28
---

# Phase 4 Plan 01: Shared Infra and Shell Summary

**SPA shell wired for the economy-map surface: three hash-routed view containers, nine design-token layout selectors, and the router/showView/constant plumbing Wave 2 renderers plug into — shipped without any data reads yet.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-28T07:08:42Z
- **Completed:** 2026-05-28T07:14:04Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- index.html gained three sibling view containers (`#map-view`, `#block-view`, `#status-view`) under `<main>`, each pre-hidden and wrapping a `.content-area`; block-view carries a `← Map` back-link and `#block-content` injection target. A quiet `.nav-map-link` anchor sits in the nav-left cluster (D-04).
- style-map.css extended with nine layout selector groups (nav-map-link, tier-label, block-tile, block-header, block-tension, block-body, evolution, timeline-show-all, status-row), each with a divider + markup-contract comment, all consuming `var(--accent-tier)` via the Phase 3 cascade. Phase 3 token surface (lines 1-148) untouched.
- app.js router resolves `#/map/<slug>`, `#/map`, `#/status` (with `#/map/` ordered first), dispatches three async stub loaders, and `showView()` now enumerates all five containers plus hides the mode toggle + subtitle on map routes. Five module constants exported for Wave 2.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend index.html — view containers + nav Map link** - `19238c6` (feat)
2. **Task 2: Extend style-map.css — nine layout selector groups** - `2f5b144` (feat)
3. **Task 3: Extend app.js — constants, router, showView, switch + stub loaders** - `82b9f64` (feat)

## Files Created/Modified
- `docker/web/site/index.html` - +19 lines: three view containers under `<main>` + `.nav-map-link` (now 97 lines)
- `docker/web/site/style-map.css` - +200 lines: nine map-surface layout selector groups appended after the Phase 3 token surface (now 348 lines)
- `docker/web/site/app.js` - +64 lines: five constants, three getRoute() branches, extended showView(), three switch cases + three stub loaders (now 378 lines)

## Wave 2 Symbol Dependencies

- **HUB_STORYLINE** → plan 02 (hub renderer header)
- **STATUS_PAGE_HEADER** → plan 04 (status hero/header)
- **MATURITY_STAGE** → plans 02 + 03 + 04 (maturity pill `data-stage` resolution)
- **TIER_LABELS** → plans 02 + 04 (tier grouping headings)
- **LIVE_TENSION_PLACEHOLDER** → plan 03 (empty-state tension hide via exact string match)
- **CSS selectors** (`.tier-label`, `.block-tile` → plan 02; `.block-header`, `.block-tension`, `.block-body`, `.evolution`, `.timeline-show-all` → plan 03; `.status-row` → plan 04)
- **View containers** (`#map-view`, `#map-view .content-area` → plan 02; `#block-content` → plan 03; `#status-content` → plan 04)
- **Stub loaders** (loadHub → plan 02; loadBlock → plan 03; loadStatus → plan 04 — each replaces the stub body with the real query+render)

## Decisions Made
- HUB_STORYLINE seeded with the PROJECT.md-aligned draft (114 chars, under the 200-char cap): "Synthesis with editorial integrity. Eight blocks, seven shipped, one deferred — the agent economy as a living map." Wave 2 plan 02 may revise.
- Extended style-map.css in place per D-19 / PATTERNS §4 rather than splitting to style-hub.css.
- Mode-toggle hide done via `style.display` inside `showView()` (not a body CSS class), co-locating the visibility decision with the other view toggles per the Discretion item.

## Deviations from Plan

None — plan executed exactly as written. (The HUB_STORYLINE string used the planner's suggested draft verbatim; not a deviation.)

The Task 2 line-count soft cap (`< 350`) was initially exceeded (395 lines) because the markup-contract comment blocks were verbose. Comments were compacted to 1-2 lines each (every group retains its divider + a `Markup contract:` line, satisfying the acceptance criteria); CSS rules were unchanged. Final: 348 lines. This was tuning within the plan's stated constraint, not a scope change.

The Task 3 verify's awk-based ordering regexes (`#\/map.[^/]`) are imprecise and both matched the same line; the actual code ordering was confirmed correct via line-numbered grep (`#/map/` at line 111, bare `#/map` at line 114) and a headless route-logic smoke test. No code change needed.

## Issues Encountered
None.

## Verification Performed
- index.html: grep exact-count checks (1 each of map-view/block-view/status-view/nav-map-link/block-content) + `html.parser` clean parse.
- style-map.css: all 9 selectors present, 13 `var(--accent-tier)` references (≥6 required), 348 lines (<350), zero deletions to the Phase 3 token surface, 10 markup-contract comments, balanced braces (53 rules).
- app.js: all grep checks pass, HUB_STORYLINE 114 chars (≤200), `#/map/` ordered before `#/map` (lines 111<114), `node --check` + `new Function()` parse clean, `python3 -m http.server` serves app.js/index.html with HTTP 200, headless logic test confirms all five routes resolve correctly with slug extraction and mode-toggle hidden on the three map routes.

## User Setup Required
None — no external service configuration required. The new view containers are still empty (renderers ship in Wave 2); manual browser verification of the full surface happens after Wave 4 deploy.

## Next Phase Readiness
- Wave 2 renderers (plans 02 hub / 03 block / 04 status) can run in parallel: each plugs its query+render into one stub loader, emits markup matching its assigned CSS selectors and view container, and consumes the relevant module constants. None touches the same code region as another (loaders are separate functions; CSS selectors are distinct; view containers are distinct).
- No blockers. The data path (`sb.schema('economy_map').from(...)`) is a Phase 2 prerequisite, untouched by this plan.

## Self-Check: PASSED

- Files verified present: index.html, style-map.css, app.js, 04-01-SUMMARY.md
- Commits verified in git: 19238c6, 2f5b144, 82b9f64, 79dcd1d

---
*Phase: 04-hub-block-and-status-renderer*
*Completed: 2026-05-28*
