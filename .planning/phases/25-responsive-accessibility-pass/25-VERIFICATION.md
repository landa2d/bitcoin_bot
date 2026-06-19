---
phase: 25-responsive-accessibility-pass
verified: 2026-06-19T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 25: Responsive & Accessibility Pass — Verification Report

**Phase Goal:** The whole redesigned surface holds up on small screens and for keyboard/assistive users — every grid and row reflows correctly at the breakpoints, scroll-spy is keyboard- and motion-safe, focus is always visible, motion is reduced on request, and every link is a real anchor — verified holistically across the single-scroll landing and the detail routes the milestone touched.

**Verified:** 2026-06-19
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | All grids and rows reflow responsively at breakpoints: map 3→2→1, nav condenses on mobile, signal/archive rows stack date-above-headline below the mobile breakpoint | ✓ VERIFIED | `.grid` is `repeat(3,1fr)` desktop (style-shared.css:400); collapses `repeat(2,1fr)` @880px (:477), `1fr` @600px (:478). `.made-cols` collapses `1fr` @880px (:1145). Nav condense `@media (max-width:600px)` with `flex-wrap:wrap` + tabs `overflow-x:auto` (style-base.css:256-266). `.row` @600px places `.date` in `grid-row:1` (kicker) and unnamed content wrapper in `grid-row:2` (style-shared.css:269-274). No stale `640` in style-base.css. |
| 2 | Keyboard focus visible everywhere — `:focus-visible` violet outline on nav, list rows, links, subscribe email — scroll-spy nav keyboard-operable | ✓ VERIFIED | `#subscribe-email:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; … }` (style-shared.css:929-934). No bare `:focus { outline: none }` for that selector. `.row:focus-visible` (:257-261), `.view-all:focus-visible` (:303-307), `.card:focus-visible` (:447-450) all present. Nav tabs are real `<a href="#…">` elements (index.html:28-31) — keyboard-activatable natively. Operator sign-off confirmed visible outlines on all targets including subscribe email. |
| 3 | `prefers-reduced-motion` respected — hover lifts/transitions suppressed, scroll-spy smooth-scroll suppressed, theme fade suppressed (D-11 cascade win) | ✓ VERIFIED | Canonical global reset at style-base.css:314-320: `*, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; }`. D-11 doubled-class override `.mode-transitioning.mode-transitioning` (specificity 0,2,0) at style-base.css:327-332 beats the `(0,1,0) !important` theme transition at style-shared.css:32. Operator live-render sign-off confirmed theme toggle produces no fade, hover lifts suppressed, scroll-spy jumps. |
| 4 | Every link across the landing + touched routes is a real `<a>` element — no click-handler-only pseudo-links | ✓ VERIFIED | Archive rows: `renderList` returns `<a href="#/edition/…" class="row">` (app.js:495). Signal rows: `renderSignals` returns `<a … class="row signal-row" target="_blank" rel="noopener noreferrer">` (app.js:631). Block cards: `<a href="#/map/…">` (app.js:999). Nav tabs: `<a href="#newsletter|signals|map|about">` (index.html:28-31). `view-all` is a `<button>` (action, not navigation — correct). `timeline-show-all` is a `<button onclick="expandTimeline()">` (correct). The only `addEventListener('click')` in app.js is on the view-all button (line 648). No `<div onclick>` or `<span onclick>` pseudo-links found via `grep -a`. |

**Score: 4/4 truths verified**

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docker/web/site/style-shared.css` | `#subscribe-email:focus-visible` violet outline; `.row <=600px` date-above-headline reflow | ✓ VERIFIED | Both present. `#subscribe-email:focus-visible` rule at line 929 with `outline: 2px solid var(--accent)`, no bare `:focus { outline: none }`. `.row @media (max-width:600px)` block at lines 269-274 with `grid-row:1` date kicker, `grid-row:2` content wrapper, affordance column kept (`grid-column:1; grid-row:1/span 2`). |
| `docker/web/site/style-base.css` | Nav condense `@media` at 600px; canonical `prefers-reduced-motion` global reset + D-11 doubled-class override | ✓ VERIFIED | Nav condense at `@media (max-width:600px)` (line 256), zero stale `640` in file. Canonical reset at lines 314-320 with all four `!important` declarations. D-11 override at lines 327-332 with comment warning against simplification. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `style-shared.css` `.row @media(max-width:600px)` | `renderList` AND `renderSignals` row output | Single shared `.row` rule — no per-render JS change (D-09) | ✓ WIRED | Both `renderList` (app.js:495) and `renderSignals` (app.js:631) emit elements with `class="row"`, inheriting the shared 600px reflow. `app.js` has zero diff across the three task commits (9037db0, c910d2b, 0350c86). |
| `style-base.css` `prefers-reduced-motion` reset | `style-shared.css:32` `.mode-transitioning *` `!important` theme transition | Doubled-class `.mode-transitioning.mode-transitioning` (specificity 0,2,0 beats 0,1,0) | ✓ WIRED | The `!important` theme transition at style-shared.css:32 specificity `(0,1,0)` is out-specified by the doubled selector at style-base.css:327-332 specificity `(0,2,0)`. Comment explicitly names the target and warns against "simplifying" the doubled class. `setMode()` applies `.mode-transitioning` to `<body>` (app.js:289 per code review), confirming the override is load-bearing. |

---

### Data-Flow Trace (Level 4)

Not applicable. This phase is CSS-only (static authored rules). No dynamic data rendering was introduced; verification was of CSS behavior at fixed viewport widths and under OS accessibility preferences.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Nav condense breakpoint is 600px, not 640px | `grep -q 'max-width:600px' style-base.css && ! grep -q '640' style-base.css && echo PASS` | PASS | ✓ PASS |
| `.row` date-above-headline reflow uses `grid-row:1` | `grep -q 'span:not(.num):not(.date)' style-shared.css && grep -A5 'max-width: 600px' style-shared.css \| grep -q 'grid-row: 1' && echo PASS` | PASS | ✓ PASS |
| `#subscribe-email:focus-visible` with `outline: 2px solid var(--accent)` | `grep -A3 '#subscribe-email:focus-visible' style-shared.css \| grep -q 'outline: 2px solid var(--accent)' && echo PASS` | PASS | ✓ PASS |
| Canonical reduced-motion global reset present with D-11 override | `grep -q 'mode-transitioning.mode-transitioning' style-base.css && grep -A8 'prefers-reduced-motion' style-base.css \| grep -q 'transition-duration: 0.01ms' && echo PASS` | PASS | ✓ PASS |
| app.js untouched across task commits (D-09) | `git diff 9037db0~1..0350c86 -- docker/web/site/app.js` | empty diff | ✓ PASS |

---

### Probe Execution

No probes declared for this phase (CSS-only delta, no runnable entry points). Step 7c: SKIPPED.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RESP-01 | 25-01, 25-02 | All grids and rows reflow responsively — map 3→2→1, nav condenses on mobile, signal/archive rows stack (date above headline) below the mobile breakpoint | ✓ SATISFIED | Grid collapse at 880px/600px in style-shared.css:477-478; `.made-cols` at 880px (:1145); nav at 600px (style-base.css:256); date-above-headline `.row` 600px block (style-shared.css:269-274). Operator live-render confirmation at canonical viewports (~375/~768/~1280px). |
| A11Y-01 | 25-01, 25-02 | Keyboard focus visible (`:focus-visible` violet outline), `prefers-reduced-motion` respected, and every link is a real `<a>` element | ✓ SATISFIED | `#subscribe-email:focus-visible`, `.row:focus-visible`, `.view-all:focus-visible`, `.card:focus-visible` all present. Canonical reduced-motion global reset with D-11 cascade win. All navigational elements are real `<a>` elements; interactive actions are `<button>` elements. Operator sign-off confirmed live focus visibility and reduced-motion behavior. |

**Coverage: 2/2 requirements satisfied. No orphaned requirements.**

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| style-shared.css | 932 | `border-radius: var(--radius-sm)` redundantly re-declared in `:focus-visible` block (already set on base rule at :919) | ℹ Info | Inert — the input's radius does not change on focus. Flagged in 25-REVIEW.md as IN-02. No behavioral impact. |
| style-shared.css | 269-274 | Date rendered visually above headline (`grid-row:1`) but appears after content in DOM order | ℹ Info | Not a WCAG violation — the entire `.row` is a single `<a>` whose accessible name is read in DOM order (date last); meaning is preserved. Flagged in 25-REVIEW.md as IN-01. |
| style-base.css | 256 | Nav wrap breakpoint lowered 640→600px (WR-01 from 25-REVIEW.md) — may leave 601–640px band potentially overflow-prone | ⚠ Warning | Advisory only. This is the locked D-05 operator decision (nav condenses at the same 600px line rows stack). WR-01 contradicts a locked, operator-approved design decision. Per phase instructions, this advisory finding does not constitute a blocking gap. The operator confirmed live render passed at canonical viewports. |

No debt markers (TBD/FIXME/XXX) found in modified files.

---

### Human Verification Completed

The live-render acceptance gate (Plan 25-02 Task 3) was a `checkpoint:human-verify` gate requiring operator approval. The operator sign-off is recorded in `25-02-SUMMARY.md`:

> "Task 3 — Live-render sign-off (human-verify, APPROVED): Operator confirmed all three groups on the live site:
> 1. Responsive reflow at ~375/~768/~1280px (3→2→1 grid, About grid 1-col @mobile, nav condensed scrollable tab row, date-above-headline rows with affordance kept, nav condenses at the same ~600px line).
> 2. Keyboard focus: visible violet `:focus-visible` outlines on nav/rows/links and the subscribe email input (the named D-02 regression closed); scroll-spy nav keyboard-operable.
> 3. OS reduced-motion: theme toggle produces NO color fade (D-11 cascade win proven live), hover lifts suppressed, scroll-spy jumps instead of smooth-scrolls."

No pending human verification items remain.

---

### Gaps Summary

No gaps. All four must-have truths are VERIFIED against source code evidence:

1. Grid/row/nav responsive reflow — fully implemented in CSS at the correct breakpoints, both CSS files modified exactly as specified.
2. Focus visibility — `#subscribe-email:focus-visible` ring present, no bare `:focus { outline: none }` regression, all interactive elements have `:focus-visible` outlines.
3. `prefers-reduced-motion` — canonical global reset with D-11 cascade win are both in place and structurally sound.
4. Real `<a>` elements — all navigational elements use genuine anchor semantics; the only click handlers are on `<button>` elements (view-all, timeline-show-all).

The WR-01 code review advisory (nav breakpoint 601–640px overflow potential) contradicts the locked D-05 operator decision and is not a blocking gap.

---

_Verified: 2026-06-19_
_Verifier: Claude (gsd-verifier)_
