---
phase: 03-design-tokens
plan: 01
subsystem: web/design-tokens
tags: [css, design-tokens, accent-tier, maturity-pill, timeline-entry, wcag-aa]
requires: []
provides:
  - "Tier-accent CSS contract (data-accent → --accent-tier resolution)"
  - "Maturity-pill component CSS (data-stage 1..5 fill via nth-child)"
  - "Timeline-entry two-line format with literal ↗ glyph"
affects:
  - docker/web/site/style-map.css
tech-stack:
  added: []
  patterns:
    - "Two-variant tokens (-base / -on-dark) selected by body.{strategic,technical} × [data-accent]"
    - "Structural CSS fill via :nth-child(-n+N) keyed by data-stage attribute"
    - "Variable cascade with fallback: var(--accent-tier, var(--accent))"
    - "Defensive empty-state rule via :not([data-source])"
key-files:
  created:
    - docker/web/site/style-map.css
  modified: []
decisions:
  - "On-dark variants chosen: teal #4FCBA8 (9.99:1), purple #9D95E8 (7.37:1), coral #E89072 (7.45:1), gray #B0AEA8 (9.10:1) — all exceed WCAG AA for text (4.5:1) and non-text (3:1) against #0a0a0f"
  - "Selector key is data-accent (not data-tier) so the seeded blocks.accent column flows verbatim including psychology=coral override"
  - "Components (.maturity-pill, .timeline-entry) are class-keyed, not nested under [data-accent] — the --accent-tier cascade handles tier-specificity automatically"
  - "Literal ↗ glyph (U+2197) appears in markup-contract comment, not generated via ::before — Phase 4 emits the glyph in source-link text"
metrics:
  duration: "single session"
  completed: 2026-05-27
  tasks: 2
  files_modified: 1
  lines_added: 148
---

# Phase 03 Plan 01: Tier-Accent Tokens + Component Contracts Summary

**One-liner:** Single CSS file (`style-map.css`, 148 lines) shipping four tier-accent tokens with WCAG-AA on-dark variants, a `[data-stage=N]` maturity-pill fill contract, and a pinned two-line timeline-entry format — zero typography or page-chrome rules introduced.

## What Shipped

`docker/web/site/style-map.css` is the single Phase 3 stylesheet. It layers onto `style-shared.css` and activates only inside elements carrying `data-accent="teal|purple|coral|gray"`. Edition pages (`#list-view`, `#reader-view`) are unaffected because they never gain `data-accent` (D-06 isolation).

### Section 1: File header
Documents the data-attribute contract Phase 4 will emit (`data-accent`, `data-stage`, `data-source`) and the tier-accent mapping per `blocks.accent` Phase 2 D-23.

### Section 2: `:root` token block (8 custom properties)

**Base hex (pinned verbatim from TOKN-01 / D-05):**
| Token | Value | Tier |
|-------|-------|------|
| `--accent-teal-base` | `#0F6E56` | substrate (identity-trust, memory-context, payments-settlement) |
| `--accent-purple-base` | `#534AB7` | behavior (autonomy-control, governance-accountability) |
| `--accent-coral-base` | `#993C1D` | psychology (deliberate distinction) |
| `--accent-gray-base` | `#5F5E5A` | frame (regulation-legal) |

**On-dark variants (planner-chosen, WCAG-measured against `#0a0a0f`):**
| Token | Value | Contrast | WCAG result |
|-------|-------|----------|-------------|
| `--accent-teal-on-dark` | `#4FCBA8` | 9.99:1 | passes AA text (4.5:1) and non-text (3:1) |
| `--accent-purple-on-dark` | `#9D95E8` | 7.37:1 | passes AA text and non-text |
| `--accent-coral-on-dark` | `#E89072` | 7.45:1 | passes AA text and non-text |
| `--accent-gray-on-dark` | `#B0AEA8` | 9.10:1 | passes AA text and non-text |

Minimum margin above AA text threshold: **7.37 / 4.5 ≈ 1.6×**.

### Section 3: `--accent-tier` resolution
Eight rules — four under `body.strategic [data-accent="..."]` mapping to the `-base` variants, four under `body.technical [data-accent="..."]` mapping to the `-on-dark` variants. Descendants (pill segments, timeline source links) inherit `--accent-tier` via the cascade.

### Section 4: `.maturity-pill` (TOKN-02)
- Inline-flex container, 2px gap, vertical-align middle
- `.seg` defaults: 18×8 px, transparent background, `var(--border)` outline, 2px radius
- Five `[data-stage="N"] .seg:nth-child(-n+N)` rules fill segments 1..N with `var(--accent-tier)`
- No `:hover` / interactive states (informational only)

### Section 5: `.timeline-entry` (TOKN-03)
- Two-line format: line 1 = `<time> · <what>`; line 2 = `<why>` + optional `source ↗`
- Line 2 uses `display: flex; justify-content: space-between` so source right-anchors
- `.timeline-source` color cascades through `var(--accent-tier, var(--accent))` — tier-tinted inside `data-accent`, falls back to mode accent outside
- `:not([data-source]) .timeline-source { display: none }` defensive rule for empty-source variant (markup omits the `<a>` element when `source_url` is null)
- Literal `↗` (U+2197) documented in markup-contract comment; CSS does not generate the glyph

## TOKN-04 Self-Check (typography / chrome inheritance)

| Constraint | Result |
|------------|--------|
| `font-family:` declarations | 0 |
| `max-width:` declarations | 0 |
| Top-nav / page-chrome rules | 0 |
| `data-tier` references (wrong key) | 0 |

Courier New body font, 720px container width, and nav chrome continue to inherit from `style-shared.css` per TOKN-04 / D-08.

## Acceptance Criteria

- [x] `docker/web/site/style-map.css` exists, 148 lines, opens with `/* === AgentPulse — Economy-Map Design Tokens === */`
- [x] 4 base + 4 on-dark CSS custom properties on `:root` with pinned hex values
- [x] 8 `--accent-tier` resolution rules (`body.{strategic,technical}` × 4 accent values)
- [x] `.maturity-pill` + `.seg` + 5 `[data-stage="N"] .seg:nth-child(-n+N)` rules
- [x] `.timeline-entry` two-line format with `.timeline-line1`, `.timeline-line2`, `.timeline-date`, `.timeline-sep`, `.timeline-what`, `.timeline-why`, `.timeline-source` selectors
- [x] Literal `source ↗` (U+2197) in markup-contract comment
- [x] `.timeline-entry:not([data-source]) .timeline-source { display: none }` present
- [x] `var(--accent-tier, var(--accent))` fallback cascade on `.timeline-source`
- [x] Zero `font-family:` / `max-width:` / `data-tier` occurrences

## Requirements Closed

- **TOKN-01** — Four base + four on-dark CSS custom properties shipped, base hex pinned verbatim per D-05
- **TOKN-02** — `.maturity-pill` + `.seg` + `[data-stage="N"]` contract ready for hub/block/status reuse
- **TOKN-03** — `.timeline-entry` two-line format with literal `↗` glyph pinned
- **TOKN-04** — Zero typography / container-width / page-chrome rules introduced; inheritance from `style-shared.css` preserved

## Commits

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Tier-accent tokens + `--accent-tier` resolution (Sections 1-3) | `36a6aa0` |
| 2 | Maturity-pill + timeline-entry components (Sections 4-5) | `a30711e` |

## Deviations from Plan

None — plan executed exactly as written. All hex values, selectors, and contrast ratios match the planner's specification verbatim.

## Threat Flags

None — this plan only writes CSS to `docker/web/site/style-map.css`. No new endpoints, auth paths, schema changes, or trust-boundary surface. T-03-01 mitigation (selector scope confined to `data-accent` / `.maturity-pill` / `.timeline-entry` — none of which exist on edition pages) is satisfied by construction.

## Self-Check: PASSED

- File exists: `docker/web/site/style-map.css`
- Commits exist: `36a6aa0`, `a30711e`
- No stub patterns (TODO/FIXME/placeholder/coming soon) present
- Plan-level verification: only one file modified (`git diff --name-only HEAD~2 HEAD` confirms)
