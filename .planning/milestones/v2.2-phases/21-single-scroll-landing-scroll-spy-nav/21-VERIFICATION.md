---
phase: 21-single-scroll-landing-scroll-spy-nav
verified: 2026-06-11T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 1
overrides:
  - must_have: "The persistent nav is a scroll-spy: as the user scrolls the landing, the active section's nav tab highlights (IntersectionObserver, rootMargin '-50% 0px -50% 0px'); clicking a nav tab smooth-scrolls to that section (CSS scroll-behavior, reduced-motion-gated)."
    reason: "The rootMargin literal '-50% 0px -50% 0px' was deliberately changed post-verify to a thin ~1px band ~96px below the viewport top (rebuilt on resize) so the short #signals placeholder section is highlighted correctly. The GOAL — scroll-spy highlights the active section as the user scrolls — is BETTER satisfied. IntersectionObserver + single observer + static-literal LANDING_SECTION_IDS + .active/aria-current parity all present. Operator-approved 2026-06-11 (commit 7e4a341)."
    accepted_by: "operator"
    accepted_at: "2026-06-11T00:00:00Z"
---

# Phase 21: Single-Scroll Landing + Scroll-Spy Nav Verification Report

**Phase Goal:** The four top-level sections (newsletter / about / agent-economy / signals) render on ONE single-scroll landing with a scroll-spy nav that tracks the active section, matching the mockup — while individual editions and block pages remain deep-linkable detail routes, and the WIDTH-01 + RHYTHM-01 foundation is re-verified holistically on the assembled scroll page.
**Verified:** 2026-06-11T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The four top-level sections render on ONE single-scroll landing page (stacked `<section>` anchors inside `#landing`), in the LOCKED order Newsletter -> Signals -> Agent-Economy -> About, replacing separate top-level routes. | VERIFIED | `<main id="landing">` with `<section id="newsletter">` (line 59), `<section id="signals">` (line 82), `<section id="map">` (line 102), `<section id="about">` (line 117) in exact DOM order; nav bare-anchor tabs in locked order confirmed; old `view:'map'` / `hash.startsWith('#/about')` detail routes absent. |
| 2 | Individual editions (`#/edition/<n>`) and block pages (`#/map/<slug>`) remain deep-linkable DETAIL routes; opening one hides the landing and renders the standalone detail view. | VERIFIED | `getRoute()` tests `#/map/` and `#/edition/` FIRST (lines 215-225) returning `mode:'detail'`; `showDetail()` hides `#landing` and shows exactly one detail container; WR-02 fix normalizes legacy `#/map` and `#/about` hashes to bare-section landing entries (lines 231-232). |
| 3 | The persistent nav is a scroll-spy: the active section's nav tab highlights via IntersectionObserver as the user scrolls; clicking a nav tab smooth-scrolls to that section (CSS scroll-behavior, reduced-motion-gated). | VERIFIED (override) | `initScrollSpy()` builds ONE `IntersectionObserver` with a computed rootMargin (thin ~1px band 96px below viewport top, rebuilt on resize — height-robust replacement for the original `-50% 0px -50% 0px` literal); LANDING_SECTION_IDS static-literal array present; `.active` + `aria-current` toggled via `setActiveTabForSection`; `html { scroll-behavior: smooth; }` + `@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }` in style-base.css; rootMargin literal changed per operator-approved correctness fix (commit 7e4a341). |
| 4 | Opening a detail route leaves the landing; returning restores the landing with scroll position preserved via `landingScrollY`; sticky header does not overlap section heading on anchor jump. | VERIFIED | `landingScrollY` declared at module scope (line 140); stashed in detail branch (`landing.style.display !== 'none'` guard, line 1252-1253); `cameFromDetail` one-shot flag (line 145) guards restore; `window.scrollTo({ top: Math.min(landingScrollY, maxY), behavior: 'auto' })` with clamp + reset (lines 1286-1287); WR-03 `skipScroll` param prevents double-scroll under `scroll-behavior:smooth`; `#landing > section { scroll-margin-top: calc(60px + var(--space-md)); }` in style-base.css. |

**Score:** 4/4 truths verified (1 override applied on Truth 3 for rootMargin literal change)

### Deferred Items

None. The `#signals` placeholder section is intentionally a static shell — its data feed is owned by Phase 24 (SIGNAL-01..04). This is not a gap; it is explicitly documented in the plan and REQUIREMENTS.md traceability.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docker/web/site/index.html` | `id="landing"` wrapper + 4 stacked `<section>` + bare-anchor nav + static `#signals` shell; detail containers outside `#landing` with `display:none` | VERIFIED | All 9 automated gates passed: `id="landing"`, `id="signals"`, 4 tab href/data-tab pairs in locked order, brand `#/`, zero `source_posts`, 3 `display:none` detail containers. |
| `docker/web/site/app.js` | Two-mode `getRoute()`; `route()` mode branch; `showLanding()`/`showDetail()`/`ensureLandingDataLoaded()`; `initScrollSpy()` (IntersectionObserver); `landingScrollY`/`cameFromDetail` module vars; scroll-restore; `LANDING_SECTION_IDS` static-literal array | VERIFIED | `node --check` passes; all Plan 01 and Plan 02 Task 1 automated gates pass; `window.scrollTo` uses object form `{top, behavior:'auto'}` per WR-03/WR-04 fixes (the literal `window.scrollTo(0, landingScrollY)` check was superseded by the code-review improvements — behavior is correct). |
| `docker/web/site/style-base.css` | `html{scroll-behavior:smooth}` + reduced-motion gate + `#landing>section{scroll-margin-top:...}` + `#landing>section+section{border-top:...}` | VERIFIED | All 8 automated gates passed; rules written as compact single-line CSS (gate-friendly); token-only (`--line-strong`/`--space-*`); no new `.active` rule; `body > header` sticky rule unchanged. Width-consistency additions (`#landing .prose`, `#landing .wide .wide`) from operator live-verify iteration also present. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| index.html nav `<a href="#newsletter/signals/map/about">` | `getRoute()` landing-section allowlist regex | URL hash → `hashchange` | WIRED | `/^#(newsletter|signals|map|about)$/.test(hash)` at line 237; anchored, cannot match slashed detail hashes |
| `getRoute()` `mode:'landing'` / `mode:'detail'` | `route()` mode branch | `r.mode === 'detail'` | WIRED | Line 1250: `if (r.mode === 'detail') { ... } else { showLanding(...) }` |
| `route()` landing branch | `showLanding()` | `showLanding(r.section, willRestore)` | WIRED | Line 1279: call with skipScroll param for WR-03 |
| `route()` detail branch | `showDetail()` via loaders | `loadEdition`/`loadBlock`/`loadStatus`/`handleUnsubscribe` → `showDetail(...)` | WIRED | Lines 442, 511, 810, 1006 |
| Scroll position on the landing | Active nav `.tab` | `IntersectionObserver` → `setActiveTabForSection` → `classList.toggle('active')` + `aria-current` | WIRED | `initScrollSpy()` at line 1214; `setActiveTabForSection` at line 1186 |
| Detail → back navigation | Restored landing scroll position | `window.scrollTo({ top: Math.min(landingScrollY, maxY), behavior:'auto' })` | WIRED | Lines 1285-1287; guarded by `willRestore` (cameFromDetail + !isExplicitSectionAnchor + landingScrollY > 0) |
| Nav anchor click | Smooth scroll to section | CSS `scroll-behavior: smooth` + `scroll-margin-top: calc(60px + var(--space-md))` | WIRED | Lines 296 and 301 in style-base.css |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `app.js` loadList() | `window.currentNewsletterList` | `sb.from('newsletters').in('status', ['published','preview'])` (line 389) | Yes — live Supabase query | FLOWING |
| `app.js` loadHub() | hub/tier-card DOM | `sb.from('blocks')` + economy_map schema (pre-existing; unchanged this phase) | Yes — pre-existing query | FLOWING |
| `index.html` `#signals` shell | static only | None (intentional — Phase 24 fills) | N/A — intentional static stub | STATIC (intentional, plan-mandated) |
| `ensureLandingDataLoaded()` | `landingDataLoaded` flag + `landingDataLoadedPromise` | `Promise.all([loadList(), loadHub()])` | Yes — both return async DB results | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `node --check` syntax validation | `node --check docker/web/site/app.js` | exit 0 | PASS |
| `getRoute('#/')` → landing mode | grep on `mode: 'landing'` in app.js | PASS | PASS |
| `getRoute('#/edition/30')` → detail mode | grep on `mode: 'detail'` in app.js | PASS | PASS |
| Anchored allowlist regex present | grep `/^#(newsletter\|signals\|map\|about)$/` | PASS | PASS |
| `window.scrollTo` with `behavior:'auto'` (WR-03 fix) | grep on `landingScrollY, maxY), behavior: 'auto'` | PASS (object form) | PASS |
| CSS scroll-behavior smooth single-line | grep single-line rule body | PASS | PASS |
| `initScrollSpy()` called in DOMContentLoaded | grep DOMContentLoaded block | `initScrollSpy()` at line 1299 | PASS |
| `setActiveTab` only in detail branch | grep all `setActiveTab(` calls (non-def, non-section) | Only at line 1256 (detail branch) | PASS |
| No `showView('list')` / `showView('map')` in non-comment code | grep + comment filter | 0 occurrences | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SCROLL-01 | 21-01-PLAN.md | Four top-level sections on ONE single-scroll landing page; editions/blocks stay deep-linkable detail routes | SATISFIED | `#landing` wrapper with 4 stacked `<section>` (locked order) in index.html; two-mode router in app.js; detail routes (`#/edition/`, `#/map/`) tested first and return `mode:'detail'`; `showLanding()`/`showDetail()` split; legacy routes normalized (WR-02) |
| SCROLL-02 | 21-02-PLAN.md | Scroll-spy nav (IntersectionObserver); smooth-scroll + reduced-motion gate; detail→back scroll restore; sticky-header offset | SATISFIED | `initScrollSpy()` with single IntersectionObserver (height-robust rootMargin, operator-approved); `setActiveTabForSection` with `.active`+`aria-current`; CSS smooth-scroll + reduced-motion gate; `scroll-margin-top` offset; `landingScrollY` restore with WR-03/WR-04 fixes |

No orphaned requirements. REQUIREMENTS.md maps SCROLL-01 and SCROLL-02 exclusively to Phase 21. All other Phase 21 requirements (WIDTH-01, RHYTHM-01 holistic re-verify) were carried from Phase 20 and confirmed by the operator live-render sign-off on 2026-06-11.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app.js` | 46 | `const LIVE_TENSION_PLACEHOLDER = 'TBD — set via /map-tension'` | INFO | Pre-existing constant (present before Phase 21; the token `TBD` is the EDITORIAL VALUE stored in the DB, not a code debt marker — the constant is used at line 908 in a functional equality check); not introduced by Phase 21 |

No unresolved `FIXME`, `XXX`, or unreferenced debt markers introduced by this phase. No placeholder/stub anti-patterns in phase-modified files beyond the intentional static `#signals` shell (plan-mandated, SIGNAL-04-compliant).

### Human Verification Required

Task 3 (deploy + holistic live-render verification of SCROLL-01/SCROLL-02 + folded WIDTH-01/RHYTHM-01) was a `checkpoint:human-verify` blocking gate in 21-02-PLAN.md. This gate has been completed:

- Operator holistic live-render sign-off: **APPROVED 2026-06-11**
- Two width-consistency fix iterations (commits `77da515`, `33cef15`) redeployed + re-verified
- Code-review WR-01..WR-04 fixes (commit `e4a54eb`) redeployed + re-verified
- Scroll-spy height-robustness fix (commit `7e4a341`) redeployed + re-verified

No remaining human verification items.

### Gaps Summary

No gaps. All four ROADMAP success criteria are satisfied:

1. Single-scroll landing with scroll-spy nav and locked section order — SATISFIED in code and confirmed on live render.
2. Editions and block pages stay deep-linkable detail routes with back-to-landing scroll restore — SATISFIED: two-mode router, detail containers outside `#landing`, `landingScrollY` + `cameFromDetail` restore with WR-03/WR-04 guards.
3. WIDTH-01 and RHYTHM-01 hold holistically — SATISFIED: operator approved the assembled landing live render (including two width-fix iterations); CSS section-rhythm rule and `#landing .prose` / `#landing .wide .wide` overrides present in style-base.css.
4. No regression: mode toggle, subscribe form, existing deep links, maturity pill — SATISFIED: `showDetail` hides the hero/toggle; detail containers `display:none` by default; backlinks re-pointed from `#/map` to `#map` (commit `a000039`); `body > header` sticky rule byte-unchanged.

The only material deviation from PLAN frontmatter must_haves is the `rootMargin` literal change (Truth 3), which is an operator-approved correctness improvement (override applied above). The `window.scrollTo` form change (plan said `window.scrollTo(0, landingScrollY)`; code uses `window.scrollTo({ top: ..., behavior: 'auto' })`) is likewise a code-review improvement (WR-03/WR-04), not a gap — the restore behavior is correctly implemented and tested.

---

_Verified: 2026-06-11T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
