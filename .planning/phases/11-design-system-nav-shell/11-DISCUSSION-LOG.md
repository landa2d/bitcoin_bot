# Phase 11: Design System + Nav Shell - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-04
**Phase:** 11-design-system-nav-shell
**Areas discussed:** Ship boundary, Hero + toggle, Mobile nav, CSS cleanup

**Framing:** The approved `11-UI-SPEC.md` already locks all visual/interaction specifics (palette, type scale, spacing/radius tokens, nav structure, active-state, back-control copy, copywriting, migration inventory). Discussion was therefore scoped to **implementation scope, sequencing, and handoff** — the decisions the UI-SPEC leaves open.

---

## Ship boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Batch 11–14, ship once | Verify each phase locally; deploy the agentpulse-web rebuild only after Phase 14. Public site never shows a half-migrated state; Phase 11 can leave later-owned views rough. | ✓ |
| Ship Phase 11 live now | Deploy the shell immediately; Phase 11 must defensively restyle un-touched views so the live site stays coherent (adds scope to 11). | |

**User's choice:** Batch 11–14, ship once.
**Notes:** Keeps Phase 11 tightly scoped to the shell; later-owned views (newsletter list/article, map tiles, About) may render rough on the new base locally between 11 and 14 — expected and acceptable since nothing goes live until 14.

---

## Hero + toggle

| Option | Description | Selected |
|--------|-------------|----------|
| Recolor + define classes only | Phase 11 ships the nav shell, tokens, and the display/eyebrow type CSS classes, but leaves the existing hero DOM + global toggle structurally in place (recolored light). Phase 12 restructures + relocates the toggle. | ✓ |
| Restructure hero now | Phase 11 also rebuilds the hero into the mockup's per-view eyebrow + page-title; toggle stays put (recolored) until Phase 12 moves it. | |

**User's choice:** Recolor + define classes only.
**Notes:** Phase 11 = pure shell. The per-view eyebrow+page-title restructure and the toggle relocation into Newsletter are Phase 12 (TGL-01); Phase 11 must not move or restructure the toggle, only recolor and define the `.page-title`/`.eyebrow` type classes.

---

## Mobile nav

| Option | Description | Selected |
|--------|-------------|----------|
| Wrap tabs to scroll row | At ≤640px, brand + Subscribe stay on the top row and the 3 tabs drop to a full-width, horizontally-scrollable row. Matches the mockup (`.nav{flex-wrap:wrap}`, `.tabs{overflow-x:auto}`). | ✓ |
| Single condensed row | Keep brand + tabs + Subscribe on one line at all widths, shrinking tab padding/font to fit. | |

**User's choice:** Wrap tabs to scroll row.
**Notes:** Decided here because the shell is built once and inherited by every later view. Adopt the mockup mechanism as intent, not verbatim markup.

---

## CSS cleanup

| Option | Description | Selected |
|--------|-------------|----------|
| New base file, gut rest progressively | Add a new tokens+shell stylesheet (style-base.css) loaded first; retire the dark mode-scoped color vars now, defer tier-accent/component cleanup to later phases. | ✓ (Claude's discretion) |
| Rewrite shared/map in place now | Replace the dark palette + Courier in style-shared.css and retire tier accents in style-map.css during Phase 11. | |

**User's choice:** "You decide" → Claude chose **New base file, gut rest progressively**.
**Notes:** Hard constraint surfaced during discussion and accepted: regardless of file org, Phase 11 must retire the dark `body.technical`/`body.strategic` color-var blocks (else they override `:root` and COLOR-01 fails). Tier-accent cleanup in `style-map.css` deferred to whichever later phase touches those views — smallest per-phase blast radius, consistent with batch-deploy.

---

## Claude's Discretion

- **CSS organization (D-04):** user said "you decide." Chose a new `style-base.css` loaded first + progressive cleanup of the rest. Flexibility retained on exact file name/load order; the dark mode-scoped var retirement in Phase 11 is fixed, not discretionary.
- **Planner notes (not decisions):** captured during scout — theme/mode decoupling in `setMode()`, active-tab derived from route not click, About tab ships but `#/about` route lands in Phase 14 (local-only no-op until then), Subscribe reuses `scrollToSubscribe()`, verification is local/manual.

## Deferred Ideas

- Per-view eyebrow + serif page-title restructure + mode-toggle relocation into Newsletter → Phase 12 (TGL-01/02).
- Economy 2-col grouped card grid + tier-accent cleanup in `style-map.css` → Phase 13 (MAP-01..04).
- `#/about` route + About stub page + site-wide spacing/radius polish pass → Phase 14 (ABOUT-01, POLISH-01).
- Dark-mode variant (DARK-01), richer About w/ pipeline diagram (ABOUT-02) → v-next, out of v2.0.
