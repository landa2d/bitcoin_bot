# Phase 20: Width Tokens & Centering Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-10
**Phase:** 20-width-tokens-centering-foundation
**Areas discussed:** Width values & nav alignment (1 of 4 offered; the other 3 deferred to brief/mockup defaults)

---

## Gray-area selection

| Area offered | Description | Selected to discuss |
|--------------|-------------|---------------------|
| Width values & nav alignment | mockup values + nav width | ✓ |
| Prose vs wide — edge cases | hero/edition-header bands | (default: brief map) |
| Section-rhythm hierarchy | where strong vs hairline rules land | (default: ROADMAP rule) |
| Gutter cause: verify vs assume | confirm left-pin before fix | (default: verify-first) |

**User's choice:** Discuss only "Width values & nav alignment"; accept recorded defaults for the rest.

---

## Width token values

| Option | Description | Selected |
|--------|-------------|----------|
| Adopt mockup values | `--measure: 64ch`, `--wide: 1080px`, `--gutter: clamp(1.25rem,5vw,3.5rem)` | ✓ |
| Adopt but widen --wide | same measure/gutter, wider grid container (1140–1200px) | |
| You decide | mockup values, adjust only on conflict | |

**User's choice:** Adopt mockup values verbatim.
**Notes:** Replaces the current single 720px `.container`. Naming mismatch (brief `--container-wide` vs mockup `--wide`) to be reconciled to `--wide`/`.wide`.

## Nav / chrome width

| Option | Description | Selected |
|--------|-------------|----------|
| Nav → --wide 1080px | nav shares the wide content axis (mockup `<nav class="nav wide">`) | ✓ |
| Keep nav at 880px | content 1080px, nav stays narrower centered | |

**User's choice:** Nav → `--wide` 1080px (one centered axis).
**Notes:** Nav currently `max-width:880px` in style-base.css:125 — change to `--wide`.

---

## Claude's Discretion

- Exact CSS class names + per-route application in app.js (honoring D-01..D-06).
- Retire vs repurpose the legacy `.container` (720px) as `.prose`.
- The stray `#fff` (style-shared.css:100) + nav on-accent white — tokenize or keep.
- Prose-vs-wide boundary bands, section-rhythm "major vs within" mapping, and the
  gutter-cause pinpoint were deferred by the operator to the brief/mockup defaults +
  a verify-first research directive (D-04, D-05, D-06).

## Deferred Ideas

None new — discussion stayed within WIDTH-01 / RHYTHM-01 scope. Two keyword-matched
backend todos were reviewed and NOT folded (unrelated to a CSS phase).
