---
phase: 25-responsive-accessibility-pass
plan: 01
subsystem: ui
tags: [css, responsive, accessibility, focus-visible, prefers-reduced-motion, breakpoints, cascade-specificity]

# Dependency graph
requires:
  - phase: 21-single-scroll-landing-scroll-spy-nav
    provides: "smooth-scroll + scroll-only reduced-motion gate (style-base.css) this plan generalizes; #landing section rhythm"
  - phase: 24-signals-section
    provides: ".row signal-row family + .view-all :focus-visible (the second row type the shared 600px reflow now serves)"
  - phase: 23-distinct-newsletter-excerpts
    provides: ".row indexed-row grid (num · content-wrapper · date) the date-above-headline reflow restacks"
provides:
  - "#subscribe-email :focus-visible violet outline (A11Y-01 keyboard-focus regression closed — D-02)"
  - "Shared .row <=600px date-above-headline reflow for BOTH archive and signal rows, affordance column retained (D-07/D-08/D-09)"
  - "Nav condense breakpoint aligned to 600px (two-tier system: mobile 600 / tablet 880 — D-05)"
  - "Canonical prefers-reduced-motion global reset that out-specifies the !important theme transition (D-10/D-11)"
affects: [25-02 holistic live-render verification, future a11y-hardening phase]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Doubled-class cascade override (.mode-transitioning.mode-transitioning = (0,2,0)) to beat an !important rule that loads later in source order without resorting to load-order tricks"
    - "Single shared .row grid rule serving multiple JS render functions (renderList + renderSignals) so a mobile reflow lands once, app.js untouched"

key-files:
  created: []
  modified:
    - "docker/web/site/style-shared.css — #subscribe-email:focus-visible (D-02); rewritten .row <=600px date-above-headline reflow (D-07/D-08/D-09)"
    - "docker/web/site/style-base.css — nav condense @media 640->600 (D-05); canonical reduced-motion reset + D-11 out-specifying override (D-10/D-11)"

key-decisions:
  - "Used --radius-sm (not the row's --radius-dot) for #subscribe-email:focus-visible to match the input's existing corner radius"
  - "Kept border-color: var(--accent) on the focus state as a complementary cue alongside the load-bearing outline"
  - "Affordance column (.num) spans both grid rows (grid-row: 1 / span 2) at <=600px so date kicker + content stay column-aligned"

patterns-established:
  - "Reduced-motion global reset (animation/transition-duration 0.01ms + scroll-behavior auto, all !important) is the canonical motion gate; the doubled-class override is the documented cascade-win companion for the theme transition"
  - "Breakpoint literals stay aligned px values (mobile 600 / tablet 880), never CSS custom properties in @media (D-06 — raw CSS, no build step)"

requirements-completed: [RESP-01, A11Y-01]

# Metrics
duration: 3min
completed: 2026-06-17
---

# Phase 25 Plan 01: Responsive & Accessibility Conformance Fixes Summary

**Four CSS-only conformance fixes: subscribe-input :focus-visible ring, shared date-above-headline row reflow for both row types, nav breakpoint aligned to 600px, and a canonical reduced-motion reset that out-specifies the !important theme transition.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-06-17T16:08:56Z
- **Completed:** 2026-06-17T16:11:03Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- **D-02 keyboard focus:** replaced the `#subscribe-email:focus { outline: none; }` regression with the canonical `:focus-visible` violet outline (`2px var(--accent)`, offset `3px`, `--radius-sm`) matching `.row`/`.view-all`/`.card`.
- **D-07/D-08/D-09 row reflow:** rewrote the shared `.row` `<=600px` rule so the mono `.date` is a kicker on `grid-row: 1` ABOVE the content wrapper (`grid-row: 2`), with the affordance column retained (`.num` `grid-column: 1`, spanning both rows). One rule serves both `renderList` (archive) and `renderSignals` (signal) rows; `app.js` untouched.
- **D-05 nav breakpoint:** moved the responsive-nav condense `@media` from `640px` to `600px` (comment + condition) so the nav condenses at the same width rows stack and grids collapse (two-tier: mobile 600 / tablet 880); wrap-to-scrollable behavior unchanged (D-12).
- **D-10/D-11 reduced motion:** replaced the scroll-only gate with the canonical `*, *::before, *::after` reset (`animation-duration`/`transition-duration: 0.01ms`, `animation-iteration-count: 1`, `scroll-behavior: auto`, all `!important`) and added the doubled-class `.mode-transitioning.mode-transitioning` override `(0,2,0)` that out-specifies the `(0,1,0) !important` theme transition at `style-shared.css:32`, so reduced-motion suppresses the theme fade regardless of source order.

## Task Commits

Each task was committed atomically:

1. **Task 1: D-02 visible keyboard focus on subscribe email** - `9037db0` (fix)
2. **Task 2: D-07/D-08/D-09 date-above-headline row reflow** - `c910d2b` (feat)
3. **Task 3: D-05 nav breakpoint + D-10/D-11 reduced-motion reset** - `0350c86` (feat)

**Plan metadata:** _(this commit)_ (docs: complete plan)

## Files Created/Modified
- `docker/web/site/style-shared.css` - `#subscribe-email:focus-visible` violet outline (D-02); rewritten `.row` `<=600px` date-above-headline reflow (D-07/D-08/D-09).
- `docker/web/site/style-base.css` - nav condense `@media` `640px`->`600px` (D-05); canonical `prefers-reduced-motion` global reset + doubled-class cascade-win override (D-10/D-11).

## Decisions Made
- Used `var(--radius-sm)` (not `--radius-dot`) for the subscribe-input focus ring to match the input's own corner radius; kept `border-color: var(--accent)` as a complementary cue.
- At `<=600px`, `.num` spans `grid-row: 1 / span 2` so the affordance stays aligned across the date kicker and the content rows.
- Reduced-motion reset comment explicitly names the override target (`style-shared.css:32 .mode-transitioning * !important`) and warns against "simplifying" the doubled class away, since it is the load-bearing cascade win.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Nav-comment rewording to satisfy the strict no-`640` gate**
- **Found during:** Task 3 (nav breakpoint + reduced-motion)
- **Issue:** The Task 3 verify gate asserts `! grep -q '640'` against the WHOLE file. My first comment rewrite described the change as "Breakpoint moved 640->600", which reintroduced the literal `640` and failed the gate.
- **Fix:** Reworded the comment to "Breakpoint lowered to 600 (D-05)" — describing only the new value — so no `640` remains anywhere in `style-base.css`.
- **Files modified:** docker/web/site/style-base.css (Task 3 commit, pre-commit)
- **Verification:** Task 3 gate re-run returns PASS; `grep -n '640' style-base.css` returns nothing.
- **Committed in:** `0350c86` (folded into the Task 3 commit before it was made)

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** The plan already mandated removing the stale `640` from the nav block; the fix only adjusted comment wording to comply with the stricter whole-file gate. No behavioral or scope change.

## Issues Encountered
None beyond the deviation above — both other task gates passed first try.

## User Setup Required
None - no external service configuration required. CSS-only source edits; deploy (scoped `web` rebuild) + live operator sign-off are Plan 25-02, orchestrator-owned.

## Next Phase Readiness
- All four named RESP-01/A11Y-01 source fixes landed; `git diff` confirms ONLY `style-shared.css` + `style-base.css` changed, `app.js` has zero diff (D-09), and no new hex literals were introduced (RHYTHM-01).
- Scope ceiling (D-01) honored: no new ARIA/landmarks/skip-link/contrast/alt-text rules.
- **Source authored != requirement satisfied.** RESP-01/A11Y-01 stay UNCHECKED until Plan 25-02's holistic live-render verification at the canonical viewports (~375px / ~768px / ~1280px) proves: the date renders above the headline on both row types, the nav condenses at 600px with no overflow band, the subscribe input shows the keyboard focus ring, and reduced-motion actually suppresses the theme fade (the D-11 cascade win is asserted in source here; live proof is 25-02).

## Self-Check: PASSED

- FOUND: `.planning/phases/25-responsive-accessibility-pass/25-01-SUMMARY.md`
- FOUND commits: `9037db0` (Task 1), `c910d2b` (Task 2), `0350c86` (Task 3), `9818c56` (plan metadata)
- Confirmed: only `docker/web/site/style-shared.css` + `style-base.css` changed across the task commits; `app.js` zero diff; no new hex literals; STATE.md/ROADMAP.md NOT touched (orchestrator-owned).

---
*Phase: 25-responsive-accessibility-pass*
*Completed: 2026-06-17*
