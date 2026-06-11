---
phase: 21-single-scroll-landing-scroll-spy-nav
plan: 01
subsystem: web-frontend
tags: [navigation, hash-router, single-scroll, scroll-spy-foundation, app.js, index.html]
dependency_graph:
  requires:
    - "Phase 20 width/rhythm foundation (.prose/.wide axes, --measure/--wide/--gutter, body > header sticky) — layout-agnostic, carries over unchanged"
    - "Existing Phase 12-20 top-level view DOM (#list-view/#map-view/#about-view) + render fns (loadList/loadHub/renderHub/renderList) — REUSED verbatim as section bodies"
  provides:
    - "Two-mode hash router (getRoute() -> {mode:'landing'|'detail'}); route() mode branch; showLanding()/showDetail() split; ensureLandingDataLoaded() guard; landingScrollY module var"
    - "Single-scroll #landing wrapper in index.html with 4 stacked <section> (newsletter/signals/map/about) + bare-anchor nav + static #signals shell"
    - "The structural foundation Plan 02 consumes (scroll-spy IntersectionObserver, scroll-margin-top CSS, scroll-restore, smooth-scroll)"
  affects:
    - "Plan 02 (scroll-spy IO + scroll-restore + smooth-scroll CSS + holistic WIDTH-01/RHYTHM-01 re-verify) builds directly on landingScrollY, the 4-section array order, and the showLanding/showDetail split"
    - "Phase 24 (Signals data + anon tier-1 RLS migration) fills the #signals shell's #signals-list container"
tech_stack:
  added: []
  patterns:
    - "Two-mode discriminated-union hash router (mode:'landing'|'detail') — additive over the existing getRoute()/route()/showView() shape"
    - "Anchored allowlist regex /^#(newsletter|signals|map|about)$/ for bare-anchor landing-section detection (Security V5 — no hash value reaches a DOM sink)"
    - "Idempotent one-shot data-load guard (landingDataLoaded flag) — same flag-guarded side-effect idiom as timelineExpanded/evolutionPollHandle"
key_files:
  created: []
  modified:
    - "docker/web/site/index.html — bare-anchor nav + <main id=\"landing\"> with 4 stacked <section> reusing existing DOM + static #signals shell; detail containers moved outside #landing"
    - "docker/web/site/app.js — two-mode getRoute(); route() mode branch; showView() split into showLanding()/showDetail(); ensureLandingDataLoaded(); landingScrollY + landingDataLoaded module vars; loaders decoupled + re-pointed to showDetail()"
decisions:
  - "Anchor ids = self-describing #newsletter/#signals/#map/#about (CONTEXT-locked over the mockup's #index/#made); nav href == section id == (Plan-02) scroll-spy array"
  - "Section DOM/nav order = LOCKED mockup order Newsletter -> Signals -> Agent-Economy -> About (Signals 2nd by operator design)"
  - "#signals ships as a PURE static shell (no Supabase fetch, no source-feed read, no new <script>) — Phase 24 owns the data + RLS migration (Pitfall 7 / SIGNAL-04)"
  - "Detail-container backlinks 'Back to the map' re-pointed from #/map (a removed route) to the bare #map landing anchor — required for coherence under the new namespace"
metrics:
  duration: ~6min
  completed: 2026-06-11
  tasks: 3
  files: 2
  commits: 3
---

# Phase 21 Plan 01: Single-Scroll Landing Router Refactor (SCROLL-01) Summary

Refactored `app.js`'s hash router into a two-mode model (`mode:'landing'|'detail'`) and restructured `index.html` so the four top-level sections (Newsletter / Signals / Agent-Economy / About) render on ONE single-scroll `#landing` page while editions (`#/edition/<n>`) and block pages (`#/map/<slug>`) stay deep-linkable detail routes — the structural foundation Plan 02's scroll-spy + scroll-restore consume.

## What Was Built

**Task 1 — `index.html` single-scroll restructure (commit `a000039`):**
- Nav: changed the three slashed-route tabs (`#/`, `#/map`, `#/about`) to bare section anchors and added a Signals tab, in the LOCKED order `#newsletter` → `#signals` → `#map` → `#about`. Kept `class="tab"` + `data-tab` join keys (reused by `setActiveTab` for detail and the Plan-02 scroll-spy IO) and the brand `<a href="#/" class="brand">`.
- Wrapped the four top-level views in `<main id="landing">` as four stacked `<section>` (`#newsletter`/`#signals`/`#map`/`#about`), REUSING the existing `#list-view`/`#map-view`/`#about-view` DOM verbatim — every Phase 12-20 CSS selector + render fn preserved.
- Moved the `.hero` (Technical/Strategic mode-toggle host) inside `#newsletter` so the toggle is physically section-scoped (TGL-01).
- Added the static `#signals` placeholder shell (eyebrow → page-title → page-sub → empty `#signals-list` container) on the `.prose` axis — no Supabase fetch, no source-feed read, no new `<script>`.
- Moved the detail containers (`#reader-view`/`#block-view`/`#status-view`) to siblings OUTSIDE `#landing`, each keeping its `style="display:none"` default. Subscribe section + footer unchanged.

**Task 2 — two-mode `getRoute()` + `route()` mode branch + `landingScrollY` (commit `4941e57`):**
- `getRoute()` now returns a `{mode:'landing'|'detail'}` discriminator. Detail routes (block/reader/status/unsubscribe) are tested FIRST and tagged `mode:'detail'`; the old plain `#/map` (`view:'map'`) and `#/about` (`view:'about'`) top-level detail routes were REMOVED (those views are landing sections now). The `#/map/<slug>` block detail stays (tested first, with the trailing slash).
- The landing fallthrough uses an ANCHORED allowlist regex `/^#(newsletter|signals|map|about)$/` so `#/map/<slug>` can never match the bare `#map` anchor (Pitfall 1). Default section = `newsletter`.
- `route()` branches on `r.mode`: detail → stash `landingScrollY = window.scrollY` (only when leaving a currently-visible landing), `setActiveTab` (detail-only now), then dispatch; landing → `showLanding(r.section)` with NO `setActiveTab` (the Plan-02 scroll-spy IO owns landing active state — avoids the race/flicker Anti-Pattern).
- Declared `var landingScrollY = 0;` at module scope with the commented-global idiom.

**Task 3 — `showView()` split + loader decoupling (commit `040bdc7`):**
- Split `showView()` into `showLanding(section)` (show `#landing`, hide the 3 detail containers, load data once, SHOW the toggle/subtitle/`.hero`) and `showDetail(view)` (hide `#landing`, show exactly one detail container, HIDE the toggle/hero). The toggle/hero gating was re-homed off the old `viewName === 'list'` gate to landing-mode-true (Pitfall 5 / TGL-01).
- Added `ensureLandingDataLoaded()` — an idempotent one-shot guard (`landingDataLoaded` flag) calling `loadList()` + `loadHub()` once.
- Decoupled `loadList()`/`loadHub()` from view-switching: dropped the `showView('list'/'map')` first line so the loaders only RENDER into their container; visibility is owned by `showLanding`.
- Re-pointed the detail loaders: `loadEdition`/`handleUnsubscribe` → `showDetail('reader'/'unsubscribe')`, `loadBlock` → `showDetail('block')`, `loadStatus` → `showDetail('status')`.

## Verification

Each task's `<verify><automated>` gate was run against live code and confirmed PASS before its commit:
- **Task 1:** `#landing` + `#signals` present; all four `href`/`data-tab` pairs in order; brand `#/` intact; zero `source_posts` reference; ≥3 `display:none` detail defaults. PASS.
- **Task 2:** `node --check` passes; both `mode:'landing'`/`mode:'detail'` present; anchored allowlist regex present; old plain-`#/map` + `#/about` detail routes absent in non-comment code; `landingScrollY` declared; both `__SUPABASE_*__` placeholders intact. PASS.
- **Task 3:** `node --check` passes; `showLanding`/`showDetail`/`ensureLandingDataLoaded` defined; zero non-comment `showView('list'/'map')`; `.from('newsletters')` + `.in('status', ['published', 'preview'])` byte-identical; no live `.eq('status','published')`; `.eq('status'` count = 11; `__SUPABASE_URL__` placeholder intact. PASS.

Live-render verification (deep-link route matrix, holistic WIDTH-01/RHYTHM-01 re-verify) is Plan 02 / orchestrator-owned, post the scoped `web` rebuild — NOT run here (this plan is source-only).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Re-pointed the two detail-container "Back to the map" backlinks from `#/map` to `#map`**
- **Found during:** Task 1
- **Issue:** `#reader-view`/`#block-view`/`#status-view` carried `<a href="#/map">` backlinks, but Task 2 removes `#/map` as a route — a `#/map` hash now falls to the default landing section (`newsletter`), not the Agent-Economy section. The backlinks would land users on the wrong section.
- **Fix:** Re-pointed the two map backlinks (`#block-view`, `#status-view`) to the bare `#map` landing anchor, which correctly resolves to the Agent-Economy landing section under the new namespace. The reader backlink (`#/`) was left unchanged — `#/` correctly resolves to the landing.
- **Files modified:** `docker/web/site/index.html`
- **Commit:** `a000039`

### Comment-wording adjustments (no behavior change)

Two explanatory comments I added in Task 1 (`#signals` shell) and Task 3 (`loadList`/`loadHub`) initially contained the literal tokens `source_posts` and `.eq('status','published')`, which tripped the absence/count gates (the gates assert ZERO `source_posts` in `index.html` and a frozen `.eq('status'` count of 11). Reworded to "source feed" / "published-status filter" / "status filter" — same documented meaning, gates green. No code or behavior change.

## Scope Boundaries Honored

- SOURCE-ONLY: no `docker compose` build/deploy run (that is Plan 02, orchestrator-owned).
- The `app.js` config block (lines 1-7) and both `__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` placeholder literals are byte-identical.
- No new Supabase query, no new defensive `.eq('status','published')` filter (D-17 — RLS is the boundary). The existing `.in('status', ['published','preview'])` loadList filter + the 3 flag-gated `.eq('status','draft')` preview paths are byte-identical; `.eq('status'` count stays 11.
- `#signals` is a pure static shell — zero `source_posts` reference, no fetch, no new `<script>` (Phase 24 owns the data + RLS).
- The existing top-level view DOM was REUSED as section bodies — no section body rebuilt.
- The `body > header` sticky scoping, the mode toggle, and the subscribe form are untouched.

## Known Stubs

**`#signals` static placeholder shell (`docker/web/site/index.html`, `<section id="signals">`)** — INTENTIONAL and plan-mandated. The `#signals-list` container is empty with a "coming soon" empty-state line; it has no data source wired. This is the deliberate Phase 24 seam: Phase 24 ships the anon tier-1 RLS migration on the source table + the fail-loud fetch that fills this container. Wiring data here in Phase 21 would violate fail-loud/SIGNAL-04 (a premature anon fetch on the RLS-blocked table renders silently empty). Documented in 21-CONTEXT.md §"Signals shell seam" and the plan's `must_haves`.

## Threat Surface Scan

No new security-relevant surface introduced. The only new input path (URL hash → bare-anchor landing-section detection) is matched by an ANCHORED allowlist regex `/^#(newsletter|signals|map|about)$/`; anything outside the allowlist falls to the static-literal default section `newsletter`. No hash value reaches `getElementById`/`scrollIntoView`/`innerHTML` — section ids passed to DOM APIs are static literals. The `#signals` shell makes no fetch (T-21-02 mitigated). The `__SUPABASE_*__` substitution path is untouched (T-21-03 mitigated). Zero package installs (T-21-SC). Consistent with the plan's `<threat_model>` — no flags.
