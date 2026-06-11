# Phase 21: Single-Scroll Landing + Scroll-Spy Nav - Research

**Researched:** 2026-06-11
**Domain:** Vanilla-JS SPA navigation refactor (hash router → two-mode landing/detail) + IntersectionObserver scroll-spy, frontend-only (`docker/web/site/`)
**Confidence:** HIGH (the codebase is fully read and quoted; the scroll-spy pattern is in the operator-approved mockup verbatim; no new packages)

## Summary

Phase 21 is a **navigation-architecture refactor of one file's router**, not a visual redesign. Today `app.js` is a route-per-view SPA: `getRoute()` parses the hash, `route()` switches on a `view` string, `showView()` toggles `display:none` on six sibling `#*-view` containers, and `setActiveTab()` highlights the matching nav tab. Four of those views (`list`, `about`, `map`, plus a new `signals`) are **top-level** and must merge into ONE always-rendered single-scroll landing with section anchors (`#index`/`#made`/`#map`/`#signals` per the mockup) and an `IntersectionObserver` scroll-spy. Two views (`reader` = `#/edition/<n>`, `block` = `#/map/<slug>`) are **detail** routes that MUST stay deep-linkable, render standalone, and on "← Back" restore the landing with scroll position preserved.

The lowest-risk path keeps the existing `getRoute()`/`route()` dispatch shape and adds a **mode discriminator**: a hash is either a *landing* hash (`#/`, empty, or a bare section anchor like `#map`/`#signals`) or a *detail* hash (`#/edition/<n>`, `#/map/<slug>`). On a landing hash, show the single `#landing` container (which stacks the four sections), let the browser scroll to the anchored section (with a `scroll-margin-top` offset for the sticky header), and let the scroll-spy `IntersectionObserver` drive nav-active. On a detail hash, hide the landing, show the detail container, and stash the landing's `window.scrollY` so Back can restore it. The mockup's scroll-spy script (lines 501-510) is copy-adaptable almost verbatim. The `#status` route is an orphan deep-link (no nav tab) — keep it as a detail-style route, unchanged.

**Primary recommendation:** Refactor `getRoute()` to return `{ mode: 'landing'|'detail', ... }`; render all four landing sections once into a single `#landing` wrapper (the four existing `#list-view`/`#about-view`/`#map-view` + a new `#signals` section restructured as stacked `<section id="…">` anchors); wire the mockup's `IntersectionObserver(rootMargin:'-50% 0px -50% 0px')` scroll-spy to drive nav-active on the landing; preserve landing `scrollY` in a module variable (+ a `popstate`/`hashchange` restore) for detail→back; ship `#signals` as a static placeholder shell (Phase 24 fills the data). Add `scroll-margin-top` to sections and `scroll-behavior:smooth` (gated by `prefers-reduced-motion`) in CSS. **No new packages, no backend, no migration.**

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Hash-route parsing (landing vs detail discrimination) | Browser / Client (`app.js` `getRoute`) | — | Hash routing is client-only; Caddy `try_files … /index.html` already serves the SPA for any path |
| Single-scroll landing assembly (stack 4 sections) | Browser / Client (`app.js` render + `index.html` DOM) | CSS (`style-*.css` section rhythm) | Sections are DOM containers toggled/assembled in the client; rhythm is CSS |
| Scroll-spy active-nav highlight | Browser / Client (`IntersectionObserver`) | CSS (`.active` nav style) | IO is a client API; the visual state is the existing `.tab.active` / `.nav-links a.active` rule |
| Smooth-scroll to section on nav click | Browser / Client + CSS | — | `scroll-behavior:smooth` (CSS) or `scrollIntoView({behavior})` (JS); anchor href does the navigation |
| Sticky-header offset on anchor jump | CSS (`scroll-margin-top`/`scroll-padding-top`) | — | Pure CSS; no JS needed for the offset |
| Detail-route render (edition/block) | Browser / Client (`loadEdition`/`loadBlock`) | API (Supabase anon REST) | Unchanged — these already fetch + render standalone |
| Landing scroll-position restore on Back | Browser / Client (module var + history) | — | Client-only; no persistence beyond the session |
| Signals DATA + anon RLS | API / Database (Phase 24) | — | **NOT this phase** — Phase 21 ships the empty shell only |

## Standard Stack

**No new libraries.** This phase uses only what is already loaded by `index.html` and browser-native APIs. The "stack" is the platform.

### Core
| Library / API | Version | Purpose | Why Standard |
|---------------|---------|---------|--------------|
| `IntersectionObserver` (browser-native) | Baseline (all modern browsers since ~2019) | Scroll-spy: fire when a section crosses the viewport-center line, toggle nav `.active` | The mockup uses it verbatim (`.planning/docs/agentpulse-redesign (1).html:503`); the performant, idiomatic scroll-spy primitive (no scroll-event polling) `[CITED: developer.mozilla.org IntersectionObserver]` |
| `Element.scrollIntoView({behavior})` / CSS `scroll-behavior` | Baseline | Smooth-scroll to a section on nav click | Already used in `app.js:389` (`scrollToSubscribe`) — established in-codebase idiom `[VERIFIED: codebase grep]` |
| CSS `scroll-margin-top` | Baseline | Offset anchor-jump landing point so the sticky header doesn't overlap the section top | Pure-CSS sticky-header offset — no JS rootMargin math needed for the *jump* (IO rootMargin is separate, for the *highlight*) `[CITED: developer.mozilla.org scroll-margin-top]` |
| `marked` (CDN, unpinned `@latest`) | v15.x live (was v15.0.12 per STATE Phase 19) | Markdown → HTML for edition + block bodies | **Unchanged this phase.** Detail routes only. Do NOT touch. `[VERIFIED: codebase index.html:169]` |
| `@supabase/supabase-js@2` (CDN) | v2 | anon REST reads (editions, blocks, map) | **Unchanged this phase.** No new queries in Phase 21 (Signals data is Phase 24). `[VERIFIED: codebase index.html:168]` |

### Supporting
| Library / API | Purpose | When to Use |
|---------------|---------|-------------|
| `window.matchMedia('(prefers-reduced-motion: reduce)')` | Detect reduced-motion to gate smooth-scroll | If smooth-scroll is done in JS (`scrollIntoView`), branch `behavior:'auto'` under reduced-motion. If done in CSS (`scroll-behavior`), the existing `@media (prefers-reduced-motion: reduce)` block handles it — **prefer CSS** so it is declarative and matches the mockup (`:231`). |
| `history.replaceState` / `hashchange` | Already the router's navigation substrate | Reuse for landing↔detail transitions; `setMode()` already uses `history.replaceState` (`app.js:147`) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Always-render all 4 landing sections | Lazy-render a section on first scroll-into-view | Lazy-render adds IO complexity + a fetch-on-scroll race; the list/map already fetch on load and the about/signals shell is static. **Always-render is simpler and the data volumes are tiny** (one editions list, 7 map blocks). Recommend always-render. |
| Reuse existing `#list-view`/`#map-view`/`#about-view` containers as the landing sections | Build fresh `<section>` markup from scratch | Reuse preserves every Phase 12-20 CSS selector (`.article-entry`, `.card`, `.tier-section`, `.about p`, `.agent-row`) and all render functions untouched. **Reuse — rename/wrap the containers as anchored sections, do not rebuild.** |
| CSS `scroll-behavior:smooth` for nav clicks | JS `scrollIntoView({behavior:'smooth'})` per click handler | CSS is declarative, fewer event handlers, and the reduced-motion media query disables it for free. JS gives finer control but needs manual reduced-motion branching. **Prefer CSS; fall back to JS only if a precise offset is needed beyond `scroll-margin-top`.** |

**Installation:** None. No `npm install`. No CDN additions. No `package.json` in this service.

**Version verification:** N/A — zero new packages. The two CDN scripts (`supabase-js@2`, `marked`) are unchanged and out of scope.

## Package Legitimacy Audit

> **Not applicable.** Phase 21 installs **zero** external packages. No `npm install`, no new CDN `<script>`, no PyPI/crates dependency. The web service has no `package.json` — `index.html` loads two pinned-by-major CDN scripts (`@supabase/supabase-js@2`, `marked`) that are **unchanged** by this phase. slopcheck/registry verification is moot.

**Packages removed due to slopcheck [SLOP] verdict:** none (no packages)
**Packages flagged as suspicious [SUS]:** none (no packages)

## Architecture Patterns

### System Architecture Diagram

```
                        ┌─────────────────────────────────────────────┐
   URL hash change ───► │  getRoute(hash)  → { mode, ... }            │
   (click / deep-link)  │  ───────────────────────────────────────── │
                        │  mode = 'landing'  if hash ∈                │
                        │    { '', '#/', '#index','#signals',         │
                        │      '#map','#made' }      ◄── bare anchors │
                        │  mode = 'detail'   if hash ∈                │
                        │    { '#/edition/<n>', '#/map/<slug>',       │
                        │      '#/status', '#/unsubscribe' }          │
                        └───────────────┬─────────────────────────────┘
                                        │
                 ┌──────────────────────┴───────────────────────┐
                 ▼                                               ▼
   ┌─────────────────────────────┐              ┌──────────────────────────────┐
   │  LANDING mode               │              │  DETAIL mode                 │
   │  ─────────────────────────  │              │  ──────────────────────────  │
   │  show #landing (one page)   │              │  stash landingScrollY        │
   │  hide all detail views      │              │  show the detail #*-view     │
   │  4 stacked <section>:       │              │  hide #landing               │
   │   #index  (newsletter list) │              │  loadEdition()/loadBlock()   │
   │   #made   (about)           │              │   → Supabase anon REST       │
   │   #map    (agent-economy)   │              │   → marked.parse (body)      │
   │   #signals(SHELL/placeholder)│             │  window.scrollTo(0,0)        │
   │  scroll to anchored section │              │  ← Back link → landing hash  │
   │   (scroll-margin-top offset)│              │     → restore landingScrollY │
   │  IntersectionObserver       │              └──────────────────────────────┘
   │   (rootMargin -50%/-50%)    │                            │
   │   → toggle nav .active      │ ◄──────── back-to-landing ─┘
   └─────────────────────────────┘
            │
            ▼  fetch on load (always-render, tiny payloads)
   ┌─────────────────────────────────────────────┐
   │ Supabase anon REST                           │
   │  • newsletters (list)   → #index             │
   │  • economy_map.blocks   → #map               │
   │  • #made / #signals = static shell (no fetch │
   │    in P21; Signals data is Phase 24)         │
   └─────────────────────────────────────────────┘
```

### Component Responsibilities (file → role)

| File | Current role | Phase 21 change |
|------|--------------|-----------------|
| `docker/web/site/app.js` | Hash router (`getRoute`/`route`/`showView`/`setActiveTab`) + per-view loaders | **PRIMARY.** Add landing/detail mode discrimination; render 4 sections into one `#landing`; add scroll-spy IO + scroll-restore. |
| `docker/web/site/index.html` | Nav markup + 6 sibling `#*-view` containers | Wrap the 4 top-level views in a `#landing` container as `<section id="index/made/map/signals">`; add nav anchors for the sections; add a `#signals` placeholder shell. |
| `docker/web/site/style-base.css` | Tokens, `.prose`/`.wide` axes, sticky `body > header`, nav/tab styles | Add `scroll-margin-top` (sticky offset), `scroll-behavior:smooth` (reduced-motion-gated), section-boundary rhythm between landing sections. |
| `docker/web/site/style-shared.css` | Component styles (list/card/about/timeline) | Minimal — section-rhythm rules between stacked landing sections if not already covered by Phase 20's `tier-section`/`content-area` boundaries. |

### Pattern 1: Two-mode hash router (landing vs detail)
**What:** `getRoute()` returns a discriminated mode; `route()` branches on it. Keep the existing parse logic; add the mode field.
**When to use:** Every hash change + initial load.
**Example (recommended shape — adapt to in-codebase idiom):**
```javascript
// Source: derived from existing app.js getRoute() (:188-209) + route() (:1055-1068)
// LANDING hashes: '', '#', '#/', and bare section anchors '#index'/'#signals'/'#map'/'#made'
// DETAIL hashes: '#/edition/<n>', '#/map/<slug>', '#/status', '#/unsubscribe'
function getRoute() {
    var hash = window.location.hash || '';
    // Detail routes FIRST (most specific). '#/map/' must be tested before '#map'.
    if (hash.startsWith('#/map/'))      return { mode:'detail', view:'block',  slug: hash.split('/')[2] };
    if (hash.startsWith('#/edition/'))  return { mode:'detail', view:'reader', edition: parseInt(hash.split('/')[2]) };
    if (hash.startsWith('#/status'))    return { mode:'detail', view:'status' };
    if (hash.startsWith('#/unsubscribe')) return { mode:'detail', view:'unsubscribe' };
    // Landing — a bare section anchor (or root) all resolve to the one landing page.
    // The section to scroll to is the bare anchor id (default 'index').
    var section = /^#(index|signals|map|made)$/.test(hash) ? hash.slice(1) : 'index';
    return { mode:'landing', section: section };
}
```
**Critical ordering note:** `#/map/<slug>` (detail) and `#map` (landing section anchor) are distinct — the existing code already tests `#/map/` (with trailing slash) before `#/map`. Preserve that ordering. The landing's Agent-Economy section anchor is a **bare** `#map`; the block detail route is `#/map/<slug>`. They do not collide because the bare anchor has no `/`.

### Pattern 2: Always-render the landing, scroll to the anchored section
**What:** On a landing hash, the `#landing` container (with all 4 sections already in the DOM) is shown; the browser scrolls to the bare-anchor section. Fetch-on-load for list + map runs once; about + signals are static.
**When to use:** Landing mode.
**Example:**
```javascript
// Source: derived from existing loadList/loadHub + showView pattern
function showLanding(section) {
    document.getElementById('landing').style.display = 'block';
    hideAllDetailViews();                 // status/reader/block/unsubscribe → display:none
    ensureLandingDataLoaded();            // idempotent: loadList()+loadHub() once, guard with a flag
    // Scroll to the section. scroll-margin-top (CSS) handles the sticky-header offset.
    var el = document.getElementById(section);
    if (el) el.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });
    else window.scrollTo(0, 0);
}
```
**Note:** Prefer doing the smooth-scroll declaratively via CSS `scroll-behavior` + native anchor jump if possible, so JS doesn't have to branch on reduced-motion. But on *programmatic* scroll (deep-link load), `scrollIntoView` is needed; branch its `behavior` on `prefersReducedMotion()`.

### Pattern 3: Scroll-spy via IntersectionObserver (mockup pattern, verbatim-adaptable)
**What:** One observer watches the four section elements; when a section crosses the viewport-center line (`rootMargin:'-50% 0px -50% 0px'` → an invisible 1px-tall band at 50% height), its nav anchor gets `.active`.
**When to use:** Once, on landing init. Disconnect when leaving landing mode (or leave observing — the nav is hidden on detail anyway; but disconnect is cleaner and avoids spurious toggles while the landing is `display:none`, which suppresses intersections).
**Example:**
```javascript
// Source: .planning/docs/agentpulse-redesign (1).html:501-510 (operator-approved mockup, VERBATIM pattern)
// Adapted: nav anchors are the existing .tab elements (data-tab) OR new bare-anchor <a href="#map"> links.
var links = document.querySelectorAll('.nav-links a:not(.sub)');   // mockup selector — adapt to AgentPulse .tabs/.tab
var sections = ['index', 'signals', 'map', 'made'].map(function(id){ return document.getElementById(id); });
var obs = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
        if (e.isIntersecting) {
            links.forEach(function(l){ l.classList.toggle('active', l.getAttribute('href') === '#' + e.target.id); });
        }
    });
}, { rootMargin: '-50% 0px -50% 0px' });
sections.forEach(function(s){ s && obs.observe(s); });
```
**Verified pattern:** `rootMargin:'-50% 0px -50% 0px'` (top -50%, bottom -50%) is the canonical "single line at viewport center" scroll-spy technique — the active section is whichever one straddles the midline. `[VERIFIED: smashingmagazine.com + cssscript.com scroll-spy articles + mockup]`. Note IO options are **read-only after construction** — if the nav height changes responsively in a way that needs a different offset, you'd disconnect+rebuild; the `-50%` percentage approach sidesteps this because it is viewport-relative, not header-pixel-relative.

### Pattern 4: Detail-route coexistence + landing scroll restore
**What:** Entering a detail route stashes the landing's `scrollY` in a module variable; returning to a landing hash restores it (instead of `scrollTo(0,0)`).
**When to use:** On every landing→detail and detail→landing transition.
**Example:**
```javascript
// Source: net-new; uses the existing module-var + history.replaceState idiom (setMode :144-147)
var landingScrollY = 0;        // module-scoped, like timelineExpanded (:134)

function route() {
    var r = getRoute();
    if (r.mode === 'detail') {
        // Only stash if we are LEAVING the landing (it is currently visible).
        if (document.getElementById('landing').style.display !== 'none') {
            landingScrollY = window.scrollY;
        }
        // ... existing detail dispatch: loadEdition / loadBlock / loadStatus / handleUnsubscribe
        setActiveTabForDetail(r.view);   // map detail→tab (reader→Newsletter, block/status→Agent Economy)
    } else {
        showLanding(r.section);
        // If we arrived from a detail route at the ROOT landing hash (not a specific
        // section anchor), restore the stashed scroll position instead of jumping to top.
        if (r.section === 'index' && landingScrollY > 0 && cameFromDetail) {
            window.scrollTo(0, landingScrollY);
        }
        // scroll-spy IO drives nav-active here; no setActiveTab() call needed on landing.
    }
}
```
**Scroll-restore options (pick one, document the choice):**
1. **Module variable (recommended, simplest):** `landingScrollY` lives for the page session. Survives any number of detail round-trips. Lost on full reload (acceptable — a reload at `#/` legitimately starts at top). This matches the codebase's "module-scoped global" idiom (`timelineExpanded`, `evolutionPollHandle`).
2. **`history.scrollRestoration='manual'` + `history.state`:** More robust across the browser Back button specifically, but more surface area. The "← Back" links in the codebase are `<a href="#/">` (not `history.back()`), so they fire `hashchange`, not `popstate` — a module var on `hashchange` covers them. Recommend option 1; note option 2 as the upgrade if browser-Back behavior proves insufficient.
3. **`sessionStorage`:** Survives reload, but the landing-at-top-on-reload behavior is actually desirable, so this is over-engineering. **Avoid.**

**Nav active-state while on a detail route:** The mockup's scroll-spy only runs on the landing. On a detail route the landing is hidden, so IO fires nothing. Use the **existing `setActiveTab()` route→tab map** (`app.js:1029-1051`) for detail routes: `reader → Newsletter`, `block/status → Agent Economy`. This preserves the Phase-11 NAV-02 "active tab reflects where you are" behavior on detail pages. On the landing, let IO own the active state (do NOT also call `setActiveTab` — they'd fight).

### Anti-Patterns to Avoid
- **Rebuilding the four sections from scratch:** Throws away every Phase 12-20 CSS selector and render function. Reuse the existing `#list-view`/`#about-view`/`#map-view` DOM as the section bodies.
- **Running the scroll-spy IO while the landing is `display:none`:** A `display:none` ancestor means **zero** intersections fire, so the observer is silent on detail routes (this is fine), but it also means on the *first* landing show after a detail route, you may need a manual nav-active sync until the first scroll. Mitigate by setting the initial `.active` from `getRoute().section` when `showLanding` runs, then letting IO take over.
- **Calling `setActiveTab()` AND the scroll-spy on the landing:** They will race and flicker. Landing → IO owns active; Detail → `setActiveTab` owns active.
- **Hardcoding the sticky-header pixel offset in IO `rootMargin`:** Use the viewport-percentage `-50%` approach (resilient to the header's responsive height) for the *highlight*, and CSS `scroll-margin-top` for the *jump* offset.
- **Touching `marked.parse`, the mode toggle, or the subscribe form:** Out of scope. These are detail-route / global chrome and must render byte-identically.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Detect which section is active on scroll | A `scroll` event listener that measures every section's `getBoundingClientRect()` per frame | `IntersectionObserver` (mockup pattern) | IO is async, fires only on threshold crossings, no layout-thrash; scroll listeners jank on every pixel `[CITED: developer.mozilla.org]` |
| Smooth-scroll to a section | A `requestAnimationFrame` easing loop | CSS `scroll-behavior:smooth` (+ `scroll-margin-top`), or `scrollIntoView({behavior:'smooth'})` | Native, GPU-accelerated, reduced-motion-aware for free via the media query |
| Sticky-header offset on anchor jump | JS that reads header height and adjusts `scrollTo` | CSS `scroll-margin-top: <header-height>` on the sections | Declarative, no JS, no resize listener |
| Reduced-motion handling | A custom motion-pref state machine | `@media (prefers-reduced-motion: reduce){ scroll-behavior:auto }` (already in mockup `:231`) | One CSS rule; the mockup already does exactly this |
| Markdown → HTML (detail bodies) | Anything | `marked` (already loaded) | Unchanged; not in scope |

**Key insight:** Everything Phase 21 needs is a browser-native primitive the mockup already demonstrates. The risk is **not** in the scroll-spy (it's ~10 lines, proven in the mockup) — it's in the **router refactor** correctly distinguishing the bare-anchor landing hashes from the slashed detail hashes without breaking the 7 existing routes or the deep links. Spend the engineering care there.

## Runtime State Inventory

> Phase 21 is a frontend navigation refactor with **no rename, no migration, no datastore key change**. It touches only client-side routing + DOM + CSS. The runtime-state categories below are checked explicitly per protocol.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | **None.** No DB writes, no key/collection rename. The only reads are the unchanged `newsletters` + `economy_map.blocks` queries. | None |
| Live service config | **None.** No external-service config embeds a route string. Caddy `try_files {path} /index.html` already serves any path; hash routes are client-only and never reach Caddy. | None — verified by reading `docker/web/Caddyfile` |
| OS-registered state | **None.** No OS task/process references a web route. | None |
| Secrets/env vars | **None new.** `__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` are sed-substituted into `app.js` at container start (`entrypoint.sh`) — **this substitution must keep working** after the app.js edit (the placeholder strings on lines 4-5 must remain literally present and untouched). | Verify the two placeholder literals survive the edit (they live in a section Phase 21 does not modify) |
| Build artifacts | **Container image only.** The site is `COPY site/ /srv/` baked at image build; a scoped `docker compose up -d --build web` rebuild ships the new `app.js`/`index.html`/CSS. No egg-info / compiled artifact. | Orchestrator-owned scoped rebuild (worktree-unsafe — see Deploy) |

**The canonical question — "after every file is updated, what runtime systems still have the old behavior cached?":** Only the running `agentpulse-web` container (serving the old baked `/srv/app.js`). A scoped `web` rebuild replaces it. There is no CDN-edge cache, no service-worker (none registered — verified: no SW in `index.html`), and the browser will re-fetch `app.js` (Caddy serves it without a long-cache header by default). Nothing else holds stale routing state.

## Common Pitfalls

### Pitfall 1: Bare-anchor `#map` vs slashed-detail `#/map/<slug>` route collision
**What goes wrong:** A naive `hash.startsWith('#map')` would match `#/map/...`? No — but `hash === '#map'` vs `hash.startsWith('#/map/')` must be tested in the right order. The landing Agent-Economy anchor is `#map` (no slash); the block detail is `#/map/<slug>` (slash). The current code already tests `#/map/` before `#/map` — preserve that, and add the bare `#map` test in the **landing** branch only.
**Why it happens:** The mockup uses bare anchors (`#map`); the existing detail route uses slashed paths (`#/map/<slug>`). Mixing the two namespaces in one router is the core complexity of the phase.
**How to avoid:** Test the **slashed/detail** patterns FIRST (they have `/`), fall through to the **bare-anchor/landing** patterns. The regex `/^#(index|signals|map|made)$/` (anchored `^…$`) cannot match `#/map/foo`. Use anchored matches for the bare anchors.
**Warning signs:** Clicking the Agent-Economy nav scrolls AND tries to load a block; or deep-linking `#/map/identity-trust` lands on the map section instead of the block page.

### Pitfall 2: Sticky-header overlaps the section top on anchor jump
**What goes wrong:** Clicking a nav anchor scrolls the section to `top:0`, but the 60px sticky `body > header` covers the section's first line (eyebrow/title hidden under the nav).
**Why it happens:** Native anchor jump and `scrollIntoView({block:'start'})` align to the viewport top, ignoring the sticky header.
**How to avoid:** `scroll-margin-top: <header-height + breathing room>` (e.g. `calc(60px + var(--space-md))`) on each landing `<section>` (or `scroll-padding-top` on `html`/the scroll container). This is the standard sticky-offset fix `[CITED: developer.mozilla.org scroll-margin-top]`. The header is `position:sticky; top:0` on `body > header` (`style-base.css:142`) — measure its rendered height (nav padding `12px` + content ≈ 56-60px).
**Warning signs:** Section heading hidden behind the nav after a click or deep-link.

### Pitfall 3: Scroll-spy fires zero events while landing is `display:none`
**What goes wrong:** On a detail route the landing is hidden; the IO observes nothing (correct). But when you return to the landing, the nav-active state may be stale (showing the last detail tab) until the first scroll triggers an intersection.
**Why it happens:** `IntersectionObserver` does not fire for elements inside a `display:none` subtree.
**How to avoid:** In `showLanding(section)`, set the initial nav-active explicitly from the target `section` (manually toggle the matching anchor `.active`) BEFORE the IO takes over on the next scroll. Or, simpler: re-observe/force a sync by reading `getBoundingClientRect` once after show. Recommend the explicit initial-toggle — it's deterministic.
**Warning signs:** Returning from an edition to the landing shows "Agent Economy" highlighted while sitting on the Newsletter section.

### Pitfall 4: The sed-substitution placeholders get clobbered
**What goes wrong:** `entrypoint.sh` does `sed -i "s|__SUPABASE_URL__|…"` on `/srv/app.js`. If the refactor accidentally removes/renames the `const SUPABASE_URL = '__SUPABASE_URL__'` lines (4-5), the app loads with a literal placeholder → `createClient('__SUPABASE_URL__')` → dead SPA (the exact failure in MEMORY `reference_web_static_preview_substitution`).
**Why it happens:** Large `app.js` edits can touch the top-of-file config block.
**How to avoid:** Phase 21 changes are in the router/render region (`getRoute` onward); leave lines 1-7 untouched. Verify the two placeholder literals are still present post-edit. The preview path also depends on this (`?preview=1` before the `#` — MEMORY `reference_economy_map_preview_flag_url`).
**Warning signs:** Blank page; console error `Invalid URL: __SUPABASE_URL__`.

### Pitfall 5: Mode toggle / subscribe / `body > header` sticky scoping regress
**What goes wrong:** The Technical/Strategic toggle is **list-scoped** today (`showView()` shows it only on `list` — `app.js:224-234`). On a single-scroll landing the Newsletter section is always present, so the toggle's show/hide logic must be re-homed to "visible whenever the landing is shown" (or pinned to the Newsletter section). The subscribe form + footer live OUTSIDE `<main>` (always visible) and must stay so. The `body > header` sticky scoping (NOT bare `header`) fixed the maturity-pill overlap (MEMORY `260609-ivq`) — must not regress.
**Why it happens:** `showView()`'s per-route show/hide assumptions break when four routes become one page.
**How to avoid:** Replace the `showView()` toggle/hero gating with landing-vs-detail gating. The toggle belongs to the Newsletter section — keep it rendered within `#index`. Keep `body > header` selector exactly (do not reintroduce bare `header{position:sticky}`).
**Warning signs:** Toggle disappears; toggle appears on a block page; maturity pill rides up over the nav again.

### Pitfall 6: Section order — mockup vs current nav
**What goes wrong:** The mockup order is **Index (Newsletter) → Signals → Map → About(made)** (`:502` `['index','signals','map','made']`). The current nav is **Newsletter → Agent Economy → About** (no Signals). The ROADMAP success criterion says the landing scrolls "newsletter list → about → agent-economy → signals." These two orderings **disagree** (mockup puts Signals 2nd and About last; ROADMAP puts About 2nd and Signals last).
**Why it happens:** The mockup and the roadmap success-criteria text were written at different moments.
**How to avoid:** **This is a decision the planner/operator must lock** (see Open Questions #1). Recommend following the **mockup order** (Index → Signals → Map → About) since the mockup is the form reference the operator approved, BUT flag the ROADMAP-text discrepancy explicitly so it's a conscious choice, not a silent divergence. Either order is a pure markup-order + nav-link-order change; the scroll-spy `sections` array must match whatever order is chosen.
**Warning signs:** Nav links in a different order than the sections scroll; scroll-spy highlights the wrong tab because the `sections` array order ≠ DOM order.

### Pitfall 7: Signals shell rendered as a broken fetch instead of an honest placeholder
**What goes wrong:** If the `#signals` shell attempts to fetch `source_posts` (which is anon-RLS-blocked until Phase 24), it renders an empty/error feed silently — a fail-loud violation (the exact silent-empty-feed failure class the spine guards against, per SIGNAL-04).
**Why it happens:** Over-eager "wire it up now" instinct.
**How to avoid:** Ship `#signals` as a **static placeholder** (a heading + an eyebrow + a one-line "coming soon"/empty-state, OR just the section scaffold with no data call). **Do NOT call Supabase for `source_posts` in Phase 21.** Phase 24 adds the RLS migration + the fetch + the fail-loud guard. The seam: Phase 21 = anchor + heading + empty container; Phase 24 = populate it.
**Warning signs:** A Supabase 401/empty-array on `source_posts` in the console during Phase 21; an empty Signals list that looks like a bug.

## Code Examples

### Reduced-motion-safe smooth scroll (CSS — preferred)
```css
/* Source: .planning/docs/agentpulse-redesign (1).html:231 + scroll-margin pattern */
html { scroll-behavior: smooth; }
/* Sticky-header offset for anchor jumps (header ≈ 60px). Apply to the landing sections. */
#landing > section { scroll-margin-top: calc(60px + var(--space-md)); }
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
}
```

### Reduced-motion check (JS — only if programmatic scroll is needed)
```javascript
// Source: MDN matchMedia + mockup reduced-motion intent
function prefersReducedMotion() {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}
```

### Nav anchors for the landing (index.html)
```html
<!-- Source: adapt existing nav (index.html:21-25) to bare section anchors.
     Order = the LOCKED section order (see Open Q #1). Keep .tab/.subscribe classes. -->
<div class="tabs">
    <a href="#index"   class="tab" data-tab="newsletter">Newsletter</a>
    <a href="#signals" class="tab" data-tab="signals">Signals</a>
    <a href="#map"     class="tab" data-tab="map">Agent Economy</a>
    <a href="#made"    class="tab" data-tab="about">What is AgentPulse</a>
</div>
```
**Note:** The brand link `<a href="#/" class="brand">` (`index.html:17`) → `#/` resolves to landing `section:'index'` and scrolls to top — keep it.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `scroll` event + `getBoundingClientRect` polling for scroll-spy | `IntersectionObserver` | IO baseline ~2019 | No jank; the mockup + this phase use IO `[CITED: MDN]` |
| JS-eased smooth scroll | CSS `scroll-behavior:smooth` + `scroll-margin-top` | Baseline ~2020-2021 | Declarative, reduced-motion-aware via media query |
| Route-per-view SPA (current AgentPulse) | Hybrid: single-scroll landing for top-level + deep-link detail routes | This phase | Preserves SEO/deep-linking for editions+blocks while merging the top-level tabs |

**Deprecated/outdated:** Nothing being removed. The `#/status` route stays (orphan deep-link, no tab). The `#/unsubscribe` utility route stays. `marked`/`supabase-js` unchanged.

## Concrete Per-File Change Map

> Implementation-ready scope. The planner can task directly off this.

### `docker/web/site/index.html`
1. **Nav (`:21-25`):** Change the three `<a href="#/">`/`href="#/map"`/`href="#/about"` tabs to bare section anchors (`#index`/`#map`/`#made`) and **add a `#signals` anchor**. Order = LOCKED order (Open Q #1). Keep `class="tab"` + `data-tab`. Keep brand `#/` and the `.subscribe` button.
2. **Landing wrapper:** Wrap the four top-level view containers in a single `<div id="landing">` (or `<main id="landing">`), restructured as four `<section>` with `id="index"/"signals"/"map"/"made"`:
   - `#index` = the existing `.hero` (`:39-49`) + `#list-view` (`:53-55`) (Newsletter list + mode toggle).
   - `#signals` = **NEW static shell** — `.wide` > `.prose` eyebrow+heading + an empty `.wide` container (no data call). Placeholder copy acceptable.
   - `#map` = the existing `#map-view` content (`:68-70`).
   - `#made` = the existing `#about-view` content (`:93-137`).
3. **Detail containers:** `#reader-view` (`:58-63`), `#block-view` (`:73-78`), `#status-view` (`:81-86`), `#unsubscribe` (handled in `#reader-view`) stay as **siblings OUTSIDE `#landing`**, shown only in detail mode.
4. **Subscribe + footer (`:142-166`):** Leave OUTSIDE `<main>`/landing (always visible) — unchanged.
5. **Config block (`:1-7` of app.js, not html)** — N/A here, but do not touch the script tags (`:168-170`).

### `docker/web/site/app.js`
1. **`getRoute()` (`:188-209`):** Add `mode:'landing'|'detail'`; add bare-anchor section detection (Pattern 1). Preserve detail-route ordering (`#/map/` before bare `#map`).
2. **`route()` (`:1055-1068`):** Branch on `r.mode`. Landing → `showLanding(r.section)` + scroll-restore; Detail → existing `loadEdition`/`loadBlock`/`loadStatus`/`handleUnsubscribe` + `setActiveTab` for detail.
3. **`showView()` (`:211-235`):** Refactor into `showLanding()` + `showDetail(view)`. The toggle/hero/`.mode-toggle`/`.mode-subtitle` gating (`:224-234`) moves to "visible on landing, hidden on detail" (the toggle stays in `#index`).
4. **`setActiveTab()` (`:1029-1051`):** Keep the route→tab map for **detail** routes (reader→newsletter, block/status→map). On landing, the scroll-spy IO owns `.active` — do NOT call `setActiveTab` on landing.
5. **NEW:** `landingScrollY` module var (near `:134`); `initScrollSpy()` (IO setup, Pattern 3); `ensureLandingDataLoaded()` idempotent guard (calls `loadList()`+`loadHub()` once); `prefersReducedMotion()` helper.
6. **`loadList()`/`loadHub()` (`:267`, `:481`):** These call `showView('list'/'map')` at the top (`:268`, `:482`). In landing mode they must NOT hide sibling sections — refactor so the loaders only render into their section's container, and visibility is owned by `showLanding`/`showDetail`. **This is the trickiest edit** — the loaders currently assume route-per-view via `showView`.
7. **`loadEdition()`/`loadBlock()`/`loadStatus()`:** Mostly unchanged (detail routes). They call `showView('reader'/'block'/'status')` — re-point to `showDetail(view)`. The Evolution poll (`startEvolutionPoll`, `:1015`) and its `hashchange` cleanup (`:1083-1087`) stay (block detail only).
8. **Init (`:1070-1075`):** After `route()`, call `initScrollSpy()` once (observers persist; observing hidden sections is harmless/silent).

### `docker/web/site/style-base.css`
1. Add `html { scroll-behavior:smooth }` + `@media (prefers-reduced-motion:reduce){ html{scroll-behavior:auto} }` (Code Examples).
2. Add `scroll-margin-top` on the landing sections (Pitfall 2).
3. Section-boundary rhythm between stacked landing sections (RHYTHM-01 — one full-strength `1px var(--line-strong)` rule between major sections; the mockup uses `section + section { border-top }` `:88`). Phase 20 already has `tier-section`/`content-area` boundaries; extend the pattern to `#landing > section + section`.
4. Keep `body > header` sticky selector exactly (Pitfall 5).

### `docker/web/site/style-shared.css`
- Minimal. Only if a landing-section needs a wrapper-rhythm rule not covered by base. The `#signals` placeholder may need a small empty-state style (or reuse `.entry-preview`/`.eyebrow`).

## Assumptions Log

> Claims needing operator/planner confirmation before they become locked decisions.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The landing section order should follow the **mockup** (Index → Signals → Map → About), NOT the ROADMAP success-criteria text (Newsletter → About → Agent-Economy → Signals). | Pitfall 6, Open Q #1 | Wrong scroll order; nav-link order mismatch. **Must be locked in planning/discuss.** |
| A2 | The four landing sections should be **always-rendered** (not lazy on scroll). | Pattern 2, Alternatives | Lazy-render adds complexity; if data volumes grow this could revisit, but tiny payloads make always-render safe. |
| A3 | Landing scroll-restore via a **module variable** (option 1) is sufficient; `history.scrollRestoration` upgrade is unneeded. | Pattern 4 | If browser-Back (vs the in-page "← Back" `<a href="#/">`) needs restore, option 2 may be required. The codebase's Back links are anchors (hashchange), so the module var covers them. |
| A4 | The `#signals` shell ships as a **static placeholder with no Supabase call** (Phase 24 adds data + RLS). | Pitfall 7, Signals seam | A premature fetch = silent empty feed = fail-loud violation (SIGNAL-04). |
| A5 | The bare section anchor for About is `#made` (mockup) — OR the team may prefer `#about` for clarity. The mockup uses `#made`; the existing route was `#/about`. | Code Examples, index.html nav | Cosmetic; pick one and keep nav href ↔ section id ↔ scroll-spy array consistent. Recommend `#about` (clearer than the mockup's `#made`) unless the operator wants mockup-exact. |
| A6 | `#/status` stays a **detail-style deep-link route** with no nav tab (unchanged from today — it never had a tab). | Pattern 1, route map | If the operator wants Status folded into the landing, that's a different scope (not in SCROLL-01). Keep as-is. |
| A7 | Sticky header rendered height is ~60px (nav padding 12px top/bottom + ~12.5px mono content). The exact `scroll-margin-top` value should be measured against the live render. | Pitfall 2 | A wrong value over/under-offsets the anchor jump; trivially tunable. |

**If this table needs nothing locked:** A1 (section order) is the one genuine decision — everything else is a recommendation the planner can adopt as-is.

## Open Questions

1. **Section order: mockup vs ROADMAP text.** (A1)
   - What we know: Mockup `:502` = `['index','signals','map','made']` (Newsletter, Signals, Map, About). ROADMAP success criterion = "newsletter list → about → agent-economy → signals."
   - What's unclear: Which order ships.
   - Recommendation: Follow the **mockup** (the operator-approved form reference) and flag the ROADMAP-text discrepancy in the plan so it's a conscious choice. The scroll-spy `sections` array + nav-link order + DOM order must all agree with whatever is locked.

2. **About anchor id: `#made` (mockup) vs `#about` (clearer).** (A5)
   - Recommendation: `#about` for readability; keep nav href ↔ section id ↔ IO array in sync. Low-stakes.

3. **Does the operator want browser-Back (not just the in-page "← Back" link) to restore scroll?**
   - What we know: All "← Back" controls in the codebase are `<a href="#/">`/`href="#/map">` (hashchange), which the module-var restore covers.
   - Recommendation: Ship module-var restore (covers the in-app Back links). Note `history.scrollRestoration='manual'` as the upgrade if the hardware Back button proves insufficient at verification.

## Environment Availability

> Frontend-only, browser-native APIs + already-loaded CDN scripts. No new external tooling.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `IntersectionObserver` | Scroll-spy (SCROLL-02) | ✓ (browser baseline) | Native | None needed — universally supported in target browsers; mockup already relies on it |
| CSS `scroll-behavior` / `scroll-margin-top` | Smooth-scroll + sticky offset | ✓ (browser baseline) | Native | Graceful: without it, anchor jumps are instant (still functional) |
| `marked` (CDN) | Detail bodies (unchanged) | ✓ | v15.x | N/A — not in scope |
| `@supabase/supabase-js@2` (CDN) | List/map reads (unchanged) | ✓ | v2 | N/A — not in scope |
| Docker + `docker compose` (deploy) | Scoped `web` rebuild | ✓ | per host | N/A |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None (CSS scroll APIs degrade gracefully to instant jumps).

## Validation Architecture

> `nyquist_validation` is enabled (config `workflow.nyquist_validation: true`). This service has **no automated test framework** — it is a static-served vanilla-JS SPA with no test harness, no `package.json`, no jest/vitest/playwright. The project's Python `pytest` suite (`tests/`) covers backend services, NOT `docker/web/site/`.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | **None for the web frontend.** (Python `pytest` exists but covers backend services only — not `app.js`/CSS.) |
| Config file | none — see Wave 0 |
| Quick run command | n/a (no web test harness) |
| Full suite command | `cd /root/bitcoin_bot && python3 -m pytest tests/` (backend only — does NOT exercise Phase 21 changes) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCROLL-01 | 4 top-level sections render on one landing; editions/blocks stay deep-linkable | syntax + manual | `node --check docker/web/site/app.js` (parse-only) + live render | ⚠️ syntax-only automatable |
| SCROLL-01 | `getRoute()` correctly discriminates landing vs detail hashes | unit (if harness added) | — | ❌ Wave 0 (no harness) |
| SCROLL-02 | Scroll-spy highlights active section; smooth-scroll on click; back-to-landing scroll restore; reduced-motion-safe | manual (live, orchestrator-owned) | — | ❌ manual-only |

**Reality:** Phase 21 is verified **primarily by live-render operator verification** (orchestrator-owned, post scoped `web` rebuild — the established pattern for every Phase 11-20 UI change per STATE). The mechanical gate is `node --check app.js` (syntax) — JS syntax errors in this CDN-script-only app are otherwise caught only at browser load. There is no DOM test runner in this repo.

### Sampling Rate
- **Per task commit:** `node --check docker/web/site/app.js` (catch syntax errors before they reach the browser). Mirror the CLAUDE.md Python idiom (`python3 -c "import ast; ast.parse(...)"`) for JS.
- **Per wave merge:** Visual spot-check of the assembled landing in a substituted preview container (the `__SUPABASE_URL__` sed path — MEMORY `reference_web_static_preview_substitution`).
- **Phase gate:** Orchestrator-owned live-render verification after the scoped `web` rebuild (the WIDTH-01/RHYTHM-01 holistic re-verify also lands here per ROADMAP).

### Wave 0 Gaps
- [ ] No JS unit-test harness for `app.js` `getRoute()` mode discrimination. **Recommendation:** Do NOT introduce a test framework for one phase (out of milestone scope, adds a build step this static service deliberately avoids). Instead, gate on `node --check` (syntax) + a documented manual route-matrix check (deep-link each of `#/`, `#index`, `#signals`, `#map`, `#made`, `#/edition/30`, `#/map/identity-trust`, `#/status`, `#/unsubscribe?id=x` and confirm the right mode/render). Record the matrix in the plan's verification steps.
- [ ] No framework install — **intentionally none.** The service is static-served; adding jsdom/vitest contradicts the "no build step, hand-authored CSS/JS" convention (style-base.css header comment confirms this).

*(If the planner wants belt-and-suspenders: a single `node --check` gate + the manual deep-link matrix is the right-sized validation for a vanilla-JS static SPA — proportional to the Nyquist principle without over-tooling a buildless service.)*

## Security Domain

> `security_enforcement: true`, `security_asvs_level: 1` (config). This is a **presentation/navigation change** with **no new trust boundary, no new input path, no new sink** — but verified explicitly below against `app.js`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Public read-only site; anon key only |
| V3 Session Management | no | No sessions (no auth) |
| V4 Access Control | no (Phase 21) | Signals RLS is **Phase 24**; Phase 21 adds NO data fetch. Anon-read RLS is the existing boundary for editions/blocks (unchanged). |
| V5 Input Validation | **yes (verify)** | The new input path is the **URL hash** parsed by `getRoute()`. It is already split/parsed defensively (`parseInt` on edition, `split('/')[2]` on slug). The new bare-anchor regex `/^#(index|signals|map|made)$/` is an **allowlist** — anything else falls to the default landing. No hash value reaches an HTML sink. |
| V6 Cryptography | no | None |

### Known Threat Patterns for {vanilla-JS static SPA + hash routing}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via a new `innerHTML` sink for section anchors | Tampering | **None introduced.** Phase 21 adds NO new `innerHTML` with hash-derived content. Section ids are static literals in markup, not user-derived. The hash never flows into `innerHTML`. (Existing `escapeHtml`/`safeHttpUrl`/`marked` sinks are unchanged — `app.js:426`, `:435`, `:321`.) |
| Open redirect via hash | Tampering | N/A — hash navigation is in-page only; no `location.href=` from hash. |
| `scrollIntoView`/IO abuse | — | None — these operate on static `getElementById(staticId)`, never on hash-derived ids. |
| CSP regression | Tampering | The Caddy CSP (`connect-src https://*.supabase.co`) is **unchanged** — no new origins, no new inline-script needs beyond the existing `'unsafe-inline'`. The scroll-spy is in the bundled `app.js` (`script-src 'self'`), not a new inline script. Do not add new external origins. |

**Net security delta: zero new attack surface.** The single new input (URL hash → bare-anchor allowlist) is validated by an anchored regex allowlist; no hash value reaches any HTML/JS/URL sink. Confirm at code review that the section ids passed to `getElementById`/`scrollIntoView` are static literals (or from the `getRoute()` allowlist), never raw `location.hash`.

## Sources

### Primary (HIGH confidence)
- `docker/web/site/app.js` (full read, 1101 lines) — current router (`getRoute`/`route`/`showView`/`setActiveTab`), all loaders/renderers, Evolution poll, the `scrollToSubscribe` smooth-scroll idiom. THE code being refactored.
- `docker/web/site/index.html` (full read) — nav markup (`:15-28`), the six `#*-view` containers, the Phase-20 `.wide`/`.prose` axis wrappers, subscribe/footer outside `<main>`.
- `docker/web/site/style-base.css` + `style-shared.css` (full read) — `--measure`/`--wide`/`--gutter` tokens, `body > header` sticky scoping (`:142`), `.tab.active`, section-rhythm rules, all component styles the landing sections reuse.
- `.planning/docs/agentpulse-redesign (1).html` (full read) — THE target. Scroll-spy script (`:501-510`, `rootMargin:'-50% 0px -50% 0px'`), section structure (`#index`/`#signals`/`#map`/`#made`), nav anchors (`:247-253`), `prefers-reduced-motion` rule (`:231`), `:focus-visible` (`:234`).
- `.planning/REQUIREMENTS.md` — SCROLL-01/02 full text + cross-cutting RESP-01/A11Y-01/RHYTHM-01.
- `.planning/ROADMAP.md` (Phase 21 details `:126-140`; Phases 22-25 for downstream ownership).
- `.planning/STATE.md` — hybrid-pivot decision, standing constraints, Phase 20 foundation, the route-format + deploy gotchas.
- `docker/web/Caddyfile`, `entrypoint.sh`, `Dockerfile` — SPA `try_files` fallback, the `__SUPABASE_URL__` sed-substitution, the `COPY site/ /srv/` build, CSP.
- `CLAUDE.md` + project MEMORY — deploy discipline (scoped `web` rebuild, service key `web`, no `--delete`), web static-preview substitution, preview-flag URL idiom, maturity-pill/nav overlap fix.

### Secondary (MEDIUM confidence — verified against primary)
- Smashing Magazine "Building a Dynamic Header with Intersection Observer", CSS-Script "Sticky Navigation ScrollSpy", FreeCodeCamp forum (sticky-header-offset) — confirm the `rootMargin:'-50% …'` viewport-center scroll-spy technique + `scroll-margin-top` sticky offset as standard practice. Cross-verified with the mockup which uses the identical pattern.

### Tertiary (LOW confidence)
- None. Every load-bearing claim is verified against the codebase or the operator-approved mockup.

## Metadata

**Confidence breakdown:**
- Current architecture map: **HIGH** — full `app.js`/`index.html`/CSS read and quoted with line numbers.
- Router refactor approach: **HIGH** — derived directly from the existing `getRoute`/`route` shape; the two-mode change is additive, not a rewrite.
- Scroll-spy implementation: **HIGH** — the exact pattern is in the operator-approved mockup and cross-verified as standard practice.
- Detail-route + scroll restore: **MEDIUM-HIGH** — module-var approach is sound and matches the codebase idiom; the only open variable is whether browser-Back (vs in-page Back links) needs the `history.scrollRestoration` upgrade (flagged, low risk).
- Signals shell seam: **HIGH** — clearly bounded by the ROADMAP (Phase 24 owns data+RLS); placeholder-only is explicit.
- Pitfalls: **HIGH** — drawn from the real codebase (sed substitution, `body > header` scoping, route ordering, toggle scoping) and project MEMORY.

**Research date:** 2026-06-11
**Valid until:** 2026-07-11 (stable — vanilla-JS + browser-native APIs + a fixed codebase; no fast-moving dependency)
