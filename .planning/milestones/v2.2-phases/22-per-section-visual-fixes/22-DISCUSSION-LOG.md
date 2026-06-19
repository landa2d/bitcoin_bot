# Phase 22: Per-Section Visual Fixes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-11
**Phase:** 22-per-section-visual-fixes
**Areas discussed:** Edition meta line (HEAD-01), Map legend + deferred card (GRID-01/02)

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Edition meta line (HEAD-01) | Eyebrow fate + single meta-line shape + title-suffix strip | ✓ |
| Map legend + deferred card (GRID-01/02) | Legend scale + placement; deferred card in 3-col | ✓ |
| About copy accuracy (AGENTS-01) | Gato-vs-Gato-Brain copy reconciliation + approval-line de-dup | (left to Claude's recommendation) |

**Notes:** Phase is tightly specified by the brief + mockup, so only a few choices remained
open. Operator chose to discuss HEAD-01 and GRID-01/02; AGENTS-01 left to recommendation
(mockup `made-cols` layout is locked by the requirement; only copy accuracy was open).

---

## Edition meta line (HEAD-01)

Background: the reader chrome already states edition/mode TWICE (eyebrow above the title +
byline below), separate from any baked title suffix. The requirement fixes edition/date/mode
to appear exactly once, in a meta line BELOW the title, with the H1 = headline only.

| Option | Description | Selected |
|--------|-------------|----------|
| Drop the eyebrow entirely | H1 gets its own air; single byline below carries edition/date/mode. Matches "appears once" most literally. | ✓ |
| Keep a non-edition kicker | Retain the eyebrow slot stripped of edition/mode (e.g. a constant "NEWSLETTER" kicker); preserves the magazine-eyebrow rhythm, costs one more line. | |

**User's choice:** Drop the eyebrow entirely.
**Notes:** Byline below keeps the existing `Edition #N · date · Mode` format. Title-suffix
strip is render-only (defensive regex in `getModeTitle`, both title + title_impact), never
mutating storage; research confirms from stored bytes whether the suffix is baked + its exact
separator (Phase-19 byte-check discipline).

---

## Map legend + deferred card (GRID-01/02)

Background: mockup confirms keeping the 3 tier-sections, each → 3-col. Two open choices: the
legend scale, and how the single deferred `frame`-tier card behaves in a 3-col grid.

### Legend scale

| Option | Description | Selected |
|--------|-------------|----------|
| 5-segment (match the real pills) | Legend mirrors the cards' actual 5-segment pill, so the scale it explains == the scale on each card. | ✓ |
| 3-bar (mockup verbatim) | Use the mockup's illustrative 3-bar legend; visually lighter but wouldn't match the cards' 5 segments. | |

**User's choice:** 5-segment (match the real pills).
**Notes:** Placed once, under the "The Agent Economy" heading. Token-only colors (RHYTHM-01).

### Deferred (regulation-legal) card in 3-col

| Option | Description | Selected |
|--------|-------------|----------|
| Keep full-width (closing band) | Deferred card spans all 3 columns as today; reads as the map's "lightly-populated closing frame". | ✓ |
| Single 1/3 tile | Normal card width; uniform grid but one narrow card sits alone with two empty columns beside it. | |

**User's choice:** Keep full-width (closing band).
**Notes:** No change to the deferred-detection logic (`!current_body_version_id`).

---

## Claude's Discretion

- AGENTS-01 layout + copy: use the mockup's `made-cols` (numbered 01–04 pipeline / bulleted
  supporting + violet `.approval` callout); de-dup the approval line from intro prose P2;
  surface the Gato-vs-"Gato Brain" wording as an operator-reviewable accuracy point at
  plan/verify (not silently dropped).
- Exact CSS class names, legend markup/sizing, the strip-at-render regex (after the stored-
  byte confirm), and where the 3→2→880 / 2→1→600 breakpoints live.

## Deferred Ideas

None new — discussion stayed within HEAD-01 / GRID-01 / GRID-02 / AGENTS-01 scope. (Excerpts
= Phase 23; Signals data + RLS = Phase 24; holistic responsive/a11y = Phase 25.)
