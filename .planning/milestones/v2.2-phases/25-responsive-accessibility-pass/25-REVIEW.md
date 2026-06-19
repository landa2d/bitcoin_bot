---
phase: 25-responsive-accessibility-pass
reviewed: 2026-06-17T17:30:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - docker/web/site/style-base.css
  - docker/web/site/style-shared.css
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 25: Code Review Report

**Reviewed:** 2026-06-17T17:30:00Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed the four CSS-only deltas in `style-base.css` and `style-shared.css` against `52ed4ea`:
the `#subscribe-email:focus-visible` ring (D-02), the `≤600px` `.row` date-above-headline reflow
(D-07/08/09), the nav condense breakpoint move 640→600px (D-05), and the `prefers-reduced-motion`
global reset with the doubled-class `.mode-transitioning.mode-transitioning` override (D-10/D-11).

Three of the four changes are correct and well-constructed:

- **Reduced-motion reset (D-10/D-11):** The cascade reasoning is sound. `.mode-transitioning *`
  (specificity 0,1,0, `!important`, loaded later in `style-shared.css`) genuinely out-ranks the bare
  `*` reset (0,0,0). The doubled-class `.mode-transitioning.mode-transitioning *` (0,2,0) correctly
  wins on specificity regardless of source order and suppresses `transition-duration`. Verified
  `.mode-transitioning` is still applied to `<body>` in `setMode()` (`app.js:289`), so the override
  is load-bearing, not vestigial. `scroll-behavior:auto !important` on `*` correctly overrides the
  un-`!important` `html { scroll-behavior:smooth }` at `style-base.css:298`. No defect.
- **`#subscribe-email:focus-visible` (D-02):** A genuine a11y improvement — replaces the
  `:focus { outline:none }` regression. `:focus-visible` matches text inputs on both mouse and
  keyboard focus, so the `border-color:var(--accent)` behavior is preserved; in browsers lacking
  `:focus-visible` the rule drops gracefully and the UA outline shows (still accessible). No defect.
- **`.row` mobile reflow (D-07/08/09):** Verified against the real DOM in both `renderList`
  (`app.js:495-502`) and `renderSignals` (`app.js:631-638`). Both rows have exactly three direct
  `<span>` children, so `.row > span:not(.num):not(.date)` targets only the content wrapper, and the
  explicit `grid-row`/`grid-column` placement (num spanning rows 1–2, date row 1, content row 2) is
  internally consistent. No layout defect.

The one substantive concern is the nav breakpoint move (WR-01): lowering the wrap threshold is the
wrong direction for the nav specifically, and it newly exposes the 601–640px band to horizontal
overflow.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: Nav wrap breakpoint lowered 640→600px removes the scrollable-tabs fallback in the 601–640px band, exposing it to horizontal overflow

**File:** `docker/web/site/style-base.css:256`
**Issue:**
The nav condense `@media` query was lowered from `max-width:640px` to `max-width:600px` to "align
with the row-stack / grid-collapse line." But the nav's wrapping behavior is the opposite problem
from the grid's: the grid *narrows* as the viewport shrinks, whereas the nav's single-row content is
*fixed-wide* and needs to wrap *earlier*, not later.

The desktop nav holds four long tab labels plus the brand and the SUBSCRIBE button, all on one
non-wrapping flex line:
- `.brand` has `flex-shrink:0` (`:171`) and `.subscribe` has `flex-shrink:0` (`:226`) — neither shrinks.
- `.tabs` is the only shrinkable child, but its children are `white-space:nowrap` inline-flex tabs
  (`:193`), so its min-content width ≈ the sum of all four labels and it cannot shrink below that.
- The four labels are long: `Newsletter`, `Signals`, `Agent Economy`, `What is AgentPulse`
  (`index.html:28-31`).

At IBM Plex Mono advance (~0.6em) the single-row content totals roughly **~780px** (brand ~110px +
tabs ~490px + SUBSCRIBE ~105px + nav padding/gaps ~75px). The page has no `overflow-x:hidden` guard
on `body`/`html`, and `.tabs { overflow-x:auto }` exists **only inside the `≤600px` block**
(`:264`). Therefore, between the wrap breakpoint and ~780px the nav line overflows the viewport and
produces a horizontal scrollbar.

Before this change the wrap fired at ≤640px, so the 601–640px range got the safe full-width
scrollable-tabs layout. After this change that range stays in the overflow-prone single-row layout.
(The ~640–780px overflow band, including iPad-portrait 768px, is pre-existing and out of the phase
delta — but it is the reason lowering the breakpoint moves in the wrong direction.)

Note: exact overflow depends on rendered font metrics and cannot be confirmed without a live render;
per the project's "verify render bugs end-to-end" rule this should be checked at 600–640px (and at
768px) in a browser. The arithmetic above is strong evidence it overflows.

**Fix:** Decouple the nav wrap threshold from the content/grid 600px line — the nav needs to wrap at
a *wider* viewport than the grid collapses, not the same one. Keep (or raise) the nav breakpoint,
e.g.:
```css
/* Nav condenses earlier than the grid — its single-row content is fixed-wide. */
@media (max-width: 880px) {   /* match the tablet/grid-3→2 line, not the mobile 600 line */
  .nav { flex-wrap: wrap; }
  .tabs { order: 3; flex-basis: 100%; margin-right: 0; overflow-x: auto; }
}
```
Alternatively, add overflow resilience that applies above 600px too (allow `.tabs` to scroll, or let
the nav wrap) so the 601–640px / tablet range degrades gracefully instead of overflowing.

## Info

### IN-01: `.row` mobile reflow creates a visual order (date-above-title) that diverges from source order (date-after-content)

**File:** `docker/web/site/style-shared.css:269-274`
**Issue:**
The reflow uses `grid-row` to render `.date` in row 1 (visually above) and the content wrapper in
row 2 (below), but in DOM order the content `<span>` precedes `.date` (`app.js:497-501`,
`app.js:633-637`). This is a visual-vs-DOM order divergence (WCAG 1.3.2 territory). Because the
entire `.row` is a single `<a>` and a screen reader reads its accessible name as one string in DOM
order (`"34, Title, summary, June 17"`), the meaning is preserved and this is **not** a violation —
but it is worth recording in an explicit accessibility pass since the on-screen order (date first)
differs from the announced order (date last).
**Fix:** No change required for correctness. If strict source/visual parity is desired, emit the
`.date` node before the content `<span>` in `renderList`/`renderSignals` and drop the `grid-row`
juggling — but this is optional and out of scope for a CSS-only phase.

### IN-02: Redundant `border-radius` declaration in the focus-visible rule

**File:** `docker/web/site/style-shared.css:932`
**Issue:**
`#subscribe-email:focus-visible` re-declares `border-radius: var(--radius-sm)`, which is already set
on the base `#subscribe-email` rule (`:919`). The input's radius does not change on focus, so the
declaration is inert.
**Fix:** Drop the `border-radius` line from the `:focus-visible` block (keep `outline`,
`outline-offset`, and `border-color`). Purely cosmetic cleanup.

---

_Reviewed: 2026-06-17T17:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
