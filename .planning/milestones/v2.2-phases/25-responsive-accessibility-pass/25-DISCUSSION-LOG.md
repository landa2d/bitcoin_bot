# Phase 25: Responsive & Accessibility Pass - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-17
**Phase:** 25-Responsive & Accessibility Pass
**Areas discussed:** Pass scope & ceiling, Breakpoint strategy, Mobile row stack order, Reduced-motion scope

---

## Pass Scope & Ceiling

| Option | Description | Selected |
|--------|-------------|----------|
| Strict to brief + regressions | Close exactly the brief's items (3 reflow + 3 a11y) + fix obvious regressions found en route (e.g. `#subscribe-email` `outline:none` → `:focus-visible` violet outline). No new ARIA/skip-link/contrast scope. | ✓ |
| Brief + light a11y hardening | Also add a skip-to-content link and verify landmark structure; no full WCAG audit. | |
| Full WCAG-style audit | Contrast, ARIA, alt text, screen-reader pass across the whole SPA. | |

**User's choice:** Strict to brief + regressions
**Notes:** Most reflow/focus pieces already shipped incrementally in Phases 20–24, so this is a verify-and-close-gaps pass, not new construction. Broader WCAG work deferred (see Deferred Ideas).

---

## Breakpoint Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Align nav to 600 (two tiers) | Standardize on mobile=600px + tablet=880px; move nav condense 640→600 so everything "mobile" flips at one line; leave the correct 880/600 grid tiers. | ✓ |
| Leave as-is, verify only | Keep nav @640 / rows·grids @600 / map 3→2 @880; accept the 40px inconsistency band. | |
| Defer to plan/live-render | Let the planner pick the nav breakpoint from where the nav actually overflows. | |

**User's choice:** Align nav to 600 (two tiers)
**Notes:** Flagged the technical constraint up front — raw CSS, no build step, and `@media` queries can't read custom properties, so "shared breakpoint tokens" means aligned literal px + a documented convention, not real variables.

---

## Mobile Row Stack Order

| Option | Description | Selected |
|--------|-------------|----------|
| Date above headline (match brief) | Date becomes a mono kicker line ABOVE the headline on mobile; left affordance (num/↗) stays. Applies to both `renderList` + `renderSignals` via shared `.row`. | ✓ |
| Keep date below (current) | Leave today's 600px reflow — date in grid-column 2 + margin-top, BELOW the title. | |
| Date above, drop the left affordance | Date-above AND collapse the left num/↗ column for a cleaner two-line stack. | |

**User's choice:** Date above headline (match brief)
**Notes:** Resolves the sharpest brief-vs-code discrepancy — the current code (`style-shared.css:265-266`) puts the date below; the brief says above. Left affordance retained.

---

## Reduced-Motion Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Global reduce-motion reset | Canonical `@media (prefers-reduced-motion: reduce) { *,::before,::after { animation/transition-duration: 0.01ms !important; scroll-behavior:auto } }` — all motion honors the preference, incl. the `!important` theme transition + hover transitions. | ✓ |
| Scroll only (current) + verify | Keep just the existing scroll-behavior gate; accept sub-0.4s hover transitions still run. | |
| Middle: named motion only | Suppress scroll + theme transition + transforms, leave low-risk color/opacity hovers. | |

**User's choice:** Global reduce-motion reset
**Notes:** Plan must verify the reset wins over the existing `!important` theme transition at `style-shared.css:32` (both `!important` — cascade order / specificity pitfall).

---

## Claude's Discretion

- **Nav condense behavior** — operator confirmed the default: keep the existing wrap-tabs-to-scrollable-row condense (no hamburger / relabel), only its breakpoint moves to 600px.
- **Live-render verification viewports** — planner/verifier picks canonical widths (~375 / ~768 / ~1280) and any nav-breakpoint fine-tuning within the two-tier intent.
- **"Real `<a>`" audit** — rows + map blocks already render as `<a>`; `view-all` correctly a `<button>`. Verify no click-handler `<div>`-as-link slipped in; no JS change expected.

## Deferred Ideas

- Broader WCAG / a11y hardening (contrast audit, ARIA landmarks, alt text, skip-to-content link, screen-reader pass) — explicitly out of this phase per the scope decision; candidate for a future dedicated a11y-hardening effort.
