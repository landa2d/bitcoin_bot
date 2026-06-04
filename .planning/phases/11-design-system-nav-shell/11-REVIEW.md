---
phase: 11-design-system-nav-shell
reviewed: 2026-06-04T18:30:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - docker/web/site/style-base.css
  - docker/web/site/style-shared.css
  - docker/web/site/index.html
  - docker/web/site/app.js
findings:
  critical: 2
  warning: 4
  info: 2
  total: 8
status: remediated
remediated: 2026-06-04
---

# Phase 11: Code Review Report

**Reviewed:** 2026-06-04T18:30:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 11 introduces the light-mode design-system token layer (`style-base.css`), a sticky 3-tab nav shell, route-derived active-tab logic, and deletes the legacy dark `body.technical`/`body.strategic` variable blocks from `style-shared.css`.

Two BLOCKER-class defects were found, both introduced by this phase's commits:

1. **Broken CSS-variable cascade (regression).** The deleted dark blocks were the *only* definition site for ~18 design tokens (`--text-primary`, `--text-secondary`, `--border`, `--toggle-bg`, `--btn-text`, `--input-bg`, etc.). `style-base.css` re-defines only `--accent` and `--bg`. The remaining 16 are now consumed but never defined across `style-shared.css` and `style-map.css`, so all body/article text color, borders, toggle/input/button backgrounds, and the bottom-bar resolve to nothing. The light-mode design the phase set out to ship does not actually render.
2. **The "What is AgentPulse" tab is non-functional.** `#/about` has no `getRoute()` case, no `route()` switch case, and no view container. Clicking it falls through to the list view, highlights the *Newsletter* tab instead of About, and the `about: 'about'` entry in `setActiveTab` is unreachable dead code. The About tab can never become active.

The narrower nav pieces (`setActiveTab` toggle/aria-current logic for newsletter/map, backlinks, `--accent-tier` cascade in `style-map.css`) are correct. The `escapeHtml` + `safeHttpUrl` XSS gating in app.js is sound. Findings below.

## Critical Issues

### CR-01: Deleted dark var-blocks leave 16 design tokens undefined — light-mode styling does not render

**File:** `docker/web/site/style-shared.css:14-15` (and 60+ other consumers); root cause `docker/web/site/style-shared.css:5-9` (deleted blocks) + `docker/web/site/style-base.css:10-41` (incomplete replacement)

**Issue:**
Commit `6d429b2` deleted the `body.technical` and `body.strategic` blocks that were the sole definition site for the entire token palette. `style-base.css` `:root` only re-introduces `--accent` and `--bg`. Every other token these stylesheets reference is now undefined.

Verified consumed-but-never-defined (across `style-shared.css` + the loaded `style-map.css`):
`--text-primary`, `--text-secondary`, `--text-body`, `--text-hint`, `--border`, `--toggle-bg`, `--toggle-inactive`, `--btn-text`, `--btn-bg`, `--input-bg`, `--code-bg`, `--pre-bg`, `--blockquote-bg`, `--bar-bg`, `--bar-border`, `--bar-text`, `--btn-secondary-border`.

Concrete breakage — `style-shared.css:15` sets the base `body { color: var(--text-primary); }`. With `--text-primary` undefined and no fallback, `color` resolves to the inherited/initial value (black), but every surface relying on `--border` (content-area top rule, article tables, subscribe input, bottom-bar), `--toggle-bg` (mode toggle), `--btn-text`/`--btn-bg` (`.toggle-btn.active`, `#subscribe-btn`), and `--input-bg` (`#subscribe-email`) renders transparent/unstyled. The phase's stated goal — "the single light `:root` palette now lives in style-base.css" — is not met; the palette is incomplete.

Note `body { background: var(--bg); }` is now declared in BOTH files: `style-base.css:50` (`#faf8f5`, valid) and `style-shared.css:14` (still valid since `--bg` is defined). Not a conflict, but the duplication signals the migration was only half-applied.

**Fix:** Add the missing light-mode token definitions to the `:root` block in `style-base.css` (the file the phase designates as the single palette source). Example:
```css
:root {
  /* existing tokens … */
  --text-primary:#1a1916;          /* alias of --ink */
  --text-secondary:#55514a;        /* alias of --ink-soft */
  --text-body:#1a1916;
  --text-hint:#8a857c;
  --border:#e7e2da;                /* alias of --line */
  --toggle-bg:#efeaff;
  --toggle-inactive:#55514a;
  --btn-bg:#5b3df5;
  --btn-text:#ffffff;
  --input-bg:#ffffff;
  --code-bg:#efeaff;
  --pre-bg:#f3f0ea;
  --blockquote-bg:#f3f0ea;
  --bar-bg:#ffffff;
  --bar-border:#e7e2da;
  --bar-text:#55514a;
  --btn-secondary-border:#d8d2c7;
}
```
Re-point legacy consumers at the new canonical tokens (`--ink`, `--line`, etc.) where they already exist, or keep the aliases above. Then visually verify list view, reader view, mode toggle, and subscribe form actually render with the light palette.

### CR-02: `#/about` route is unimplemented — "What is AgentPulse" tab dead-ends to the newsletter list and highlights the wrong tab

**File:** `docker/web/site/index.html:26`, `docker/web/site/app.js:115-133` (`getRoute`), `docker/web/site/app.js:747-769` (`setActiveTab`), `docker/web/site/app.js:777-784` (`route` switch)

**Issue:**
The nav shell ships a third tab linking to `#/about`:
```html
<a href="#/about" class="tab" data-tab="about">What is AgentPulse</a>
```
But the router has no `#/about` handling. `getRoute()` (lines 115-133) has cases for `#/map/`, `#/map`, `#/status`, `#/edition/`, `#/unsubscribe`, and otherwise returns `{ view: 'list' }`. There is no `about` case, no `about` switch arm in `route()` (lines 777-784), and no `about-view` container in `index.html`.

Consequences when the operator clicks the tab:
1. `getRoute()` returns `{ view: 'list' }`.
2. `setActiveTab('list')` highlights the **Newsletter** tab (`VIEW_TO_TAB.list === 'newsletter'`), not About.
3. `route()` calls `loadList()` — the newsletter list renders under an `#/about` URL.

The About tab therefore can **never** receive `.active` / `aria-current="page"`, breaking the nav-shell's core contract (NAV-02 route→tab active state) and accessibility. The `about: 'about'` entry in `VIEW_TO_TAB` (app.js:754) is unreachable dead code — no route ever yields `view: 'about'`.

**Fix:** Either implement the route or remove the tab so the shell is honest. To implement (minimal):
```js
// getRoute(), before the final `return { view: 'list' }`:
if (hash.startsWith('#/about')) {
    return { view: 'about' };
}
```
```js
// route() switch:
case 'about': loadAbout(); break;
```
Add an `#about-view` container to `index.html`, handle it in `showView()` (add the `about` line + include it in the non-map toggle logic), and provide a `loadAbout()` renderer. If About content is not ready this phase, remove the tab (and the `about` entry in `VIEW_TO_TAB`) rather than shipping a tab that mis-highlights and dead-ends.

## Warnings

### WR-01: `showView()` does not handle `view: 'about'` — view containers won't reset

**File:** `docker/web/site/app.js:135-150`

**Issue:** Tied to CR-02. Even if a `#/about` route is added, `showView()` only toggles `list-view`, `reader-view`, `map-view`, `block-view`, `status-view`. There is no `about-view` line, and `'about'` is not classified in `isMapRoute`. An `about` view would leave whichever view was previously visible still displayed (or all hidden), and the mode toggle would remain shown. This is a latent gap that must be closed as part of the CR-02 fix.

**Fix:** When implementing the about route, add:
```js
document.getElementById('about-view').style.display = viewName === 'about' ? 'block' : 'none';
```
and decide whether the mode toggle should be hidden on the about page (likely yes — it is not a newsletter-mode surface).

### WR-02: Residual `'Courier New'` literals in `style-map.css` contradict the design-system mono token

**File:** `docker/web/site/style-map.css:161,176,216,288,307,337,344` (referenced; not in the edited file set)

**Issue:** The phase's intent (per CLAUDE.md and phase context) is "residual component Courier New migrated to `var(--mono)`." `style-shared.css` was correctly migrated, but the still-loaded `style-map.css` retains seven `font-family: 'Courier New', monospace;` declarations. These hub/block/status surfaces will render in Courier New instead of the IBM Plex Mono design token, producing inconsistent UI chrome typography across the very views the nav shell links to. `style-map.css` was outside this phase's listed file set, so this is a scope/coverage gap rather than a defect in the four reviewed files, but it undermines the stated design-system goal.

**Fix:** Replace the seven `'Courier New', monospace` declarations in `style-map.css` with `var(--mono)`. Track explicitly if deferred to a later phase, since the map/block/status pages are reachable from the new nav.

### WR-03: Technical-mode `--accent-tier` now uses on-dark accents against a light background

**File:** `docker/web/site/style-map.css:40-43` (cascade), interacting with `docker/web/site/style-base.css` light `:root` and `body class="technical"` (`docker/web/site/index.html:14`)

**Issue:** `setMode()` still toggles `body.technical`/`body.strategic`, and the body defaults to `class="technical"`. `style-map.css:40-43` maps `body.technical [data-accent=…]` to the `*-on-dark` accent variants (`#4FCBA8`, `#9D95E8`, etc.), which were calibrated for the now-deleted dark `#0a0a0f` background ("contrast 9.99:1 against `#0a0a0f`"). Against the new light `--bg: #faf8f5`, those light/desaturated on-dark accents will have markedly lower contrast and may fail WCAG AA for the pill/border/source affordances on hub and block pages in the default technical mode. The cascade itself resolves (body class is preserved), so this is a color-correctness issue, not a broken selector.

**Fix:** Out of this phase's four-file scope, but flag for the map-restyle phase: in a single light-mode design, the `body.technical` vs `body.strategic` accent split is obsolete — collapse `--accent-tier` to the light `*-base` hex for both modes (or to the new `--accent`), and re-audit contrast against `#faf8f5`.

### WR-04: Backdrop-filter header has no opaque fallback — unreadable on browsers without `backdrop-filter`

**File:** `docker/web/site/style-base.css:79-87`

**Issue:** The sticky header uses `background: rgba(250,248,245,.86)` plus `backdrop-filter: blur(10px)`. On browsers/contexts where `backdrop-filter` is unsupported or disabled, the header is 86%-opaque but **not** blurred, so list/article content scrolling underneath shows through behind the nav text, hurting legibility of the brand, tabs, and Subscribe button. Combined with CR-01 (text colors undefined), the nav chrome could be hard to read.

**Fix:** Either raise the base opacity to fully opaque as the no-blur fallback, or use an `@supports` guard:
```css
header { background: var(--bg); } /* opaque fallback */
@supports ((backdrop-filter: blur(10px)) or (-webkit-backdrop-filter: blur(10px))) {
  header { background: rgba(250,248,245,.86); }
}
```

## Info

### IN-01: `.brand-wordmark` span is unstyled (harmless)

**File:** `docker/web/site/index.html:21`

**Issue:** `<span class="brand-wordmark">AGENTPULSE</span>` has no CSS rule in any loaded stylesheet. It inherits the `.brand` font/weight/color, so it renders correctly today, but the dedicated class is dead. Either add a rule (if distinct styling was intended) or drop the class.

**Fix:** Remove the unused class, or add a `.brand-wordmark { … }` rule if the wordmark is meant to differ from the dot+brand baseline.

### IN-02: `body { line-height }` declared in two files with different values

**File:** `docker/web/site/style-base.css:49` (`1.62`) vs `docker/web/site/style-shared.css:17` (`1.6`)

**Issue:** `style-base.css` sets `body { line-height:1.62 }` (TYPE-01) and `style-shared.css` sets `body { line-height:1.6 }`. Both are `body` selectors with equal specificity; the later-loaded `style-shared.css` wins, so the body line-height is actually `1.6`, not the intended `1.62`. Minor, but the design token is silently overridden — the opposite of the "base loaded first so it wins" comment at `style-base.css:4`. (The cascade comment is misleading: for equal-specificity `body` rules, *last* wins, not *first*.)

**Fix:** Remove `line-height: 1.6;` from `style-shared.css:17` so the `style-base.css` reading base (`1.62`) takes effect, or reconcile the two intentionally.

---

## Orchestrator Disposition (2026-06-04)

Reviewed each finding on merit (not blindly applied). Two classes: real regressions fixed before phase verification (per the operator's fail-loud / fix-blockers-before-verify guidance); planned/scoped-out items documented as accepted deferrals tracked to their owning phase.

| ID | Verdict | Action |
|----|---------|--------|
| **CR-01** | **Real blocker — FIXED** | Confirmed 17 component tokens orphaned (global chrome: text scale, borders, footer bottom-bar, subscribe CTA+input, code/quote surfaces, mode toggle) — defeated COLOR-01 "site-wide". Added a legacy-token compatibility bridge in `style-base.css :root` mapping all 17 onto the existing light palette (no new hues; COLOR-02 intact). Verified **zero** consumed-but-undefined custom properties remain across the three loaded stylesheets. Commit `4edd217`. |
| **CR-02** | **Accepted deferral → Phase 14** | NOT a defect to fix here. The `#/about` tab is *intentionally* forward-wired per Plan 11-02 Task 1 ("`#/about` … the route lands in Phase 14. Do NOT add the route here") under batch-deploy (D-01, nothing ships until the milestone is complete). The `about` mapping in `setActiveTab` is intentional forward-compat. Route + view + stub are **ABOUT-01 (Phase 14)**. |
| **WR-01** | **Accepted deferral → Phase 14** | Paired with CR-02 — `showView()` gains its `about` branch when the route lands in Phase 14. |
| **WR-02** | **Deferred → Phase 13** | `style-map.css` Courier→`var(--mono)` migration. Plan 11-01 Task 3 explicitly scoped `style-map.css` out ("Do NOT touch style-map.css at all this phase"); the map/block/status restyle is **Phase 13 (Agent Economy grid)**. Acceptable "rough between phases" under D-01. |
| **WR-03** | **Deferred → Phase 13** | `body.technical` `*-on-dark` tier accents on the light bg (WCAG risk) live entirely in `style-map.css` on the hub/block pages — the Phase 13 restyle target. Collapse the technical/strategic accent split to light `*-base` and re-audit contrast there. Accepted inter-phase rough-edge under batch-deploy. |
| **WR-04** | **Deferred → Phase 14 polish (POLISH-01)** | Header `backdrop-filter` opaque fallback. Minor progressive-enhancement; the bg is already 86% opaque. UI-SPEC locked the `.86` value; the `@supports` fallback fits the Phase 14 site-wide polish pass. |
| **IN-01** | **Accepted (no action)** | `.brand-wordmark` inherits `.brand` and renders correctly; harmless dead class. |
| **IN-02** | **FIXED** | `style-shared.css` body `line-height` `1.6` → `1.62` so the TYPE-03 spec value wins (shared's body rule loads after base's). Commit `4edd217`. |

Net: both blockers resolved (CR-01 fixed in-code; CR-02 is a documented planned deferral, not a regression). All deferrals are tracked to Phase 13/14 requirements already on the roadmap.

---

_Reviewed: 2026-06-04T18:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
