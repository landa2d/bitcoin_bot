# Phase 12: Newsletter Section Restyle - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-04
**Phase:** 12-newsletter-section-restyle
**Areas discussed:** Toggle placement & form, Edition list item style, Article reading view, Newsletter header restructure

Selection method: presented 4 gray areas → user requested token-accurate HTML samples → a throwaway mockup gallery (`/tmp/ap-mockups/index.html`) rendered every variant with the real Phase 11 palette/fonts → user picked one variant per area by label.

---

## Toggle placement & form

| Option | Description | Selected |
|--------|-------------|----------|
| Segmented accent pill, list + article | Pill, active = filled violet + hint line, in both views | |
| Keep two-button toggle, relocated | Current two-button control moved into Newsletter | |
| Toggle in list only | Toggle on the list; article inherits the chosen mode, no toggle | ✓ (placement) |
| A1 · Segmented accent pill (form) | One pill, active segment filled violet, hint line below | ✓ (form) |
| A2 · Two-button restyled (form) | Two separate buttons | |

**User's choice:** Placement = **list only**; Form = **A1 segmented accent pill**.
**Notes:** Article reading view gets no toggle of its own (mode persists; switch from the list). Active = filled `--accent` + mono hint line (TGL-02).

---

## Edition list item style

| Option | Description | Selected |
|--------|-------------|----------|
| B1 · Restyled rows | Kicker (EDITION # · date) · serif title link · excerpt, tightened | ✓ |
| B2 · Bordered cards | 2-col card grid, hover lift, accent left-border | |
| B3 · Title-first dense rows | Edition # · date · serif title only, no excerpt | |

**User's choice:** **B1 — restyled rows.**
**Notes:** Keep the existing `.article-entry` anatomy; add the date to the kicker; serif + light palette + tighter rhythm.

---

## Article reading view

| Option | Description | Selected |
|--------|-------------|----------|
| C1 · Clean serif column | Narrow measure, subtle links, minimal chrome | |
| C2 · Richer magazine | Big display title, lead emphasis, styled blockquotes + code | ✓ |
| C3 · Recolor + serif only | Keep current structure, just serif + light palette | |

**User's choice:** **C2 — richer magazine.**
**Notes:** Constrained to the minimalist single-serif-display system (one display style, weights 400/600, no second family). Body prose serif (no mono paragraphs); `code`/`pre` may use mono. PREVIEW banner retained, restyled.

---

## Newsletter header restructure

| Option | Description | Selected |
|--------|-------------|----------|
| D1 · Eyebrow + serif page-title | Mono eyebrow over serif page-title (mockup pattern) | |
| D2 · Keep & recolor hero | Keep WEEKLY INTELLIGENCE BRIEFING tagline + headline | |
| D3 · Minimal header | Serif page-title + metadata line only, no eyebrow/tagline | ✓ |

**User's choice:** **D3 — minimal header** (list view). Article header = the C2 magazine title treatment.
**Notes:** Drops the "WEEKLY INTELLIGENCE BRIEFING" tagline and the eyebrow; A1 toggle pill sits beneath the minimal header.

## Claude's Discretion

- Exact DOM mechanism for the hero restructure (repurpose vs. hide the global `.hero`; behavior on non-Newsletter routes Phase 13 owns) — planner/UI-SPEC.
- Excerpt length, spacing/radius values, link underline, byline format — within the chosen variants + Phase 11 tokens.

## Deferred Ideas

- In-article mode switch (out by D-01; small follow-up if wanted later).
- Agent Economy grid + `style-map.css` cleanup → Phase 13.
- Full About page + site-wide polish + backdrop-filter fallback → Phase 14.
- Dark mode / richer About → v-next.
- 7 matched todos = v1.0 backend follow-ups, reviewed and not folded.
