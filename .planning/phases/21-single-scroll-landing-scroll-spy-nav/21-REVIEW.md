---
phase: 21-single-scroll-landing-scroll-spy-nav
reviewed: 2026-06-11T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - docker/web/site/app.js
  - docker/web/site/index.html
  - docker/web/site/style-base.css
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: resolved
resolution:
  warnings_fixed: 4
  warnings_commit: e4a54eb
  info_deferred: 4
  note: "All 4 WARNINGs (WR-01..04) fixed in e4a54eb (operator-approved 2026-06-11) + redeployed/re-verified. The 4 INFO items are non-blocking maintainability nits, deferred (IN-03 .about-lede is a pre-existing carry-over advisory)."
---

# Phase 21: Code Review Report

**Reviewed:** 2026-06-11T00:00:00Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the Phase 21 single-scroll landing + scroll-spy refactor across `app.js` (two-mode hash router, `showLanding`/`showDetail`/`ensureLandingDataLoaded`/`initScrollSpy`/scroll-restore), `index.html` (the `#landing` restructure with 4 stacked sections + static `#signals` shell), and `style-base.css` (net-new scroll/rhythm CSS).

The phase's security-critical and architectural constraints all hold:

- **Router allowlist is correctly anchored.** `/^#(newsletter|signals|map|about)$/` cannot match slashed detail hashes — verified by exhaustive input testing (`#/map/foo` resolves to `view:'block'`, never the bare `#map` anchor). Detail routes (`#/map/`, `#/status`, `#/edition/`, `#/unsubscribe`) are tested before the landing fallthrough. No hash value reaches a DOM sink — section ids passed to `getElementById`/`observe` are static literals from `LANDING_SECTION_IDS`, never `location.hash`.
- **Scroll-spy is a single observer**, registered once at init, observing only the four static-literal section ids; `setActiveTabForSection` replicates the `.active` + `aria-current` pair with parity to `setActiveTab`. No duplicate registration or leak.
- **Supabase placeholders intact** (`__SUPABASE_URL__` / `__SUPABASE_ANON_KEY__`). The `#signals` shell has ZERO Supabase fetch and no `source_posts` read. No new economy_map query and no new defensive `.eq('status','published')` filter was added — D-17 (RLS-is-the-boundary) is respected. The only `.in('status', [...])` filters are pre-existing on the `newsletters` table.
- **CSS scoping is correct.** The `#landing .prose` width override is scoped to `#landing` only; detail-route reading prose (`#reader-view`/`#block-view` `.content-area.prose`, all siblings outside `#landing`) keeps the centered 64ch measure. Phase-20 width tokens and the `body > header` sticky rule are untouched.

No blocking defects. The findings below are correctness/robustness concerns (deep-link scroll timing, a deep-link regression for the removed top-level routes, scroll-restore animation behavior) plus maintainability items.

## Warnings

### WR-01: Deep-link to a non-first section scrolls before async content loads, landing at the wrong position

**File:** `docker/web/site/app.js:254,281-286`
**Issue:** `showLanding()` calls `ensureLandingDataLoaded()` (which fires `loadList()` and `loadHub()` as un-awaited async fetches) and then **synchronously** calls `sectionEl.scrollIntoView({ block: 'start' })`. On a fresh deep-link load to `#map`, `#signals`, or `#about` (when `landingDataLoaded` is still false), the `#newsletter` list and the `#map` grid are empty at scroll time. The scroll fires against the collapsed layout; when the fetches resolve and inject the list rows / tier-card grid above (or into) the target section, the document grows and the scroll offset becomes stale — the user lands above the intended section heading. The `#newsletter` (first section, top) case is unaffected because its target is the top of the document; the bug bites every section below it.
**Fix:** Re-run the scroll once the landing data has rendered, e.g. have `ensureLandingDataLoaded()` return the load promise(s) and re-scroll on settle, or re-scroll after a `requestAnimationFrame` post-render. Minimal approach:
```js
function showLanding(section) {
    // ...visibility toggles...
    var loaded = landingDataLoaded;
    ensureLandingDataLoaded();
    // ...toggle/hero/setActiveTabForSection...
    var sectionEl = document.getElementById(section);
    function go() {
        if (sectionEl) sectionEl.scrollIntoView({ block: 'start' });
        else window.scrollTo(0, 0);
    }
    go();
    // If we just kicked off the first data load, re-scroll after content lands.
    if (!loaded && section !== 'newsletter') {
        Promise.all([loadListPromise, loadHubPromise]).then(go);
    }
}
```
(Requires `ensureLandingDataLoaded`/`loadList`/`loadHub` to expose their promises.)

### WR-02: Removed top-level routes `#/map` and `#/about` silently fall through to the Newsletter section (deep-link regression)

**File:** `docker/web/site/app.js:211-228`
**Issue:** Before this phase, `#/map` resolved to the map view and `#/about` to the about view. After the refactor, neither matches the anchored allowlist (`#/map` and `#/about` contain a slash) and neither matches a detail prefix (`#/map/` requires a trailing slash; `#/about` has no handler), so both fall through to `section:'newsletter'`. Verified: `getRoute('#/map')` and `getRoute('#/about')` both return `{mode:'landing', section:'newsletter'}`. Any stale bookmark, browser history entry, or externally shared link to the old `#/map`/`#/about` top-level routes now lands silently on the Newsletter section instead of the map/about content — a confusing, unsignalled redirect rather than scrolling to the corresponding section. (No external surface in `processor`/`newsletter` emits these links, so blast radius is stale client-side history/bookmarks only.)
**Fix:** Normalize the legacy slashed top-level hashes to their bare-anchor equivalents in `getRoute()` (or via a redirect on load), so an old `#/map` lands on the map section:
```js
// Legacy top-level route compatibility: #/map -> #map, #/about -> #about
if (hash === '#/map') return { mode: 'landing', section: 'map' };
if (hash === '#/about') return { mode: 'landing', section: 'about' };
```
Place these AFTER the `#/map/` detail check so block deep-links are unaffected.

### WR-03: Scroll-restore competes with `scrollIntoView` under `scroll-behavior: smooth`

**File:** `docker/web/site/app.js:281-286,1230-1237` and `docker/web/site/style-base.css:296`
**Issue:** On a detail→back return to the root hash (`#/`), `showLanding('newsletter')` runs `sectionEl.scrollIntoView({ block: 'start' })` (line 283) and then `route()` immediately runs `window.scrollTo(0, landingScrollY)` (line 1236) to restore the stashed position. With `html { scroll-behavior: smooth }` (style-base.css:296) now globally in effect, both scrolls follow the CSS smooth behavior in spec-compliant browsers (the legacy 2-arg `scrollTo(x, y)` form follows the scrolling box's `scroll-behavior`). The result is a visible animated scroll from the top down to the restored offset — and two competing smooth animations issued back-to-back in the same frame — rather than the intended instant restore. Outcome is browser-dependent and janky; the restore can also visibly "fly" past content.
**Fix:** Force an explicit instant behavior on the restore (and ideally skip the intermediate `scrollIntoView` when a restore is pending), e.g.:
```js
if (returningFromDetail && !isExplicitSectionAnchor && landingScrollY > 0) {
    window.scrollTo({ top: landingScrollY, behavior: 'auto' });
}
```
Better: pass `returningFromDetail` into `showLanding` so it skips the section `scrollIntoView` entirely when a scroll restore will run, avoiding the double-scroll.

### WR-04: `landingScrollY > 0` guard cannot restore a non-trivial position captured as 0, and never re-validates staleness

**File:** `docker/web/site/app.js:1209-1211,1235`
**Issue:** `landingScrollY` is captured only when leaving a currently-visible landing (`landing.style.display !== 'none'`). The restore guard is `landingScrollY > 0`. Two edge cases: (1) If the user opened a detail route from the very top of the landing (`scrollY === 0`), the back-return correctly stays at top — harmless. (2) More importantly, `landingScrollY` is never reset to `0` after a successful restore or on a fresh landing entry, so it persists across the session. Combined with `cameFromDetail` being the real gate, the `> 0` check is redundant-but-mostly-harmless; however, if a future change captures `landingScrollY` and then the document shrinks (e.g., list fetch returns fewer rows than when captured), `window.scrollTo(0, landingScrollY)` overshoots to the document's clamped max with no re-validation. This is a latent fragility in the module-var restore approach.
**Fix:** Reset `landingScrollY = 0` after restoring, and clamp/guard the restore against the current document height:
```js
if (returningFromDetail && !isExplicitSectionAnchor && landingScrollY > 0) {
    var maxY = document.documentElement.scrollHeight - window.innerHeight;
    window.scrollTo({ top: Math.min(landingScrollY, Math.max(0, maxY)), behavior: 'auto' });
    landingScrollY = 0;
}
```

## Info

### IN-01: Two divergent join keys for the same active-tab logic

**File:** `docker/web/site/app.js:1134-1135,1163`
**Issue:** `setActiveTab()` (detail routes) selects the active tab via `el.dataset.tab === targetTab`, while `setActiveTabForSection()` (landing) selects via `el.getAttribute('href') === '#' + sectionId`. Both produce equivalent results given the current markup (where `data-tab` and the bare-anchor `href` agree), but they rely on two independent invariants. A future edit to either the `href` or the `data-tab` of a nav anchor could desync the two code paths.
**Fix:** Pick one join key for both functions (prefer `data-tab`, which is the documented "join key" in the index.html comment) so the two paths stay in lockstep.

### IN-02: Dead entries in `VIEW_TO_TAB`

**File:** `docker/web/site/app.js:1123,1128`
**Issue:** `setActiveTab()` is now only invoked from the detail branch of `route()` with `r.view` ∈ {`reader`, `unsubscribe`, `block`, `status`}. The `list:` and `about:` keys in `VIEW_TO_TAB` are no longer reachable (those views became landing sections handled by the scroll-spy). Harmless but misleading dead code.
**Fix:** Remove the unreachable `list` and `about` entries, or add a comment that `setActiveTab` is detail-route-only.

### IN-03: Stale `.about-lede` rule no longer has a markup target

**File:** `docker/web/site/style-base.css:275-282`
**Issue:** `.about-lede` styles an element that does not appear in the current `#about` section markup (the about copy uses `.about` / `.body-soft`, not `.about-lede`). This was likely already dormant pre-phase, but the about-section restructure in this phase makes it clearly dead.
**Fix:** Remove `.about-lede` if no route renders it, or confirm it is used by a dynamically-rendered surface.

### IN-04: Scroll-spy leaves no tab active when the page bottom (subscribe/footer) is at the viewport center

**File:** `docker/web/site/app.js:1182-1195`
**Issue:** The IntersectionObserver observes only the four `#landing` sections. The `#subscribe-section` and `footer.bottom-bar` live outside `#landing` and are not observed. When the user scrolls to the bottom so that the subscribe/footer region straddles the `-50%/-50%` midline band, no observed section is intersecting, so no `isIntersecting` event fires and the last-set tab (`about`) simply stays highlighted. This is acceptable "sticky-last" behavior, but it means the active tab does not reflect that the user has scrolled past the navigable sections.
**Fix:** Optional. If desired, observe a sentinel or clear the active tab when no section is intersecting; otherwise document the sticky-last behavior as intended.

---

_Reviewed: 2026-06-11T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
