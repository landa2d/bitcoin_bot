---
status: partial
phase: 12-newsletter-section-restyle
source: [12-VERIFICATION.md]
started: 2026-06-04T20:52:42Z
updated: 2026-06-04T20:52:42Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Toggle pill visual rendering (list view)
expected: On the Newsletter list view, the active segment (Technical or Strategic) shows a solid filled violet (`var(--accent)`) background with white text at weight 600; the inactive segment is `--ink-soft`; the pill wrapper has a visible 1px border (`var(--line-strong)`).
result: [pending]

### 2. Mode switching interaction + hint line copy
expected: Switching Technical ⇄ Strategic on the list view immediately updates the hint line below the pill to "Architecture, code, implementation" (Technical) / "Markets, strategy, implications" (Strategic), and the filled segment moves to the newly-active side; the list re-renders the same dual-mode content as before.
result: [pending]

### 3. Reader view — no toggle, magazine header visible
expected: On a single-edition (reader) route, no Technical/Strategic pill appears; the article header renders a mono kicker ("Edition #N · Technical|Strategic"), a large serif display title, and a one-line mono byline below it.
result: [pending]

### 4. Edition list — serif body + date-bearing kicker
expected: Each list row kicker reads "EDITION #N · {date}" (e.g. "EDITION #34 · June 1, 2026"), not just the edition number; all body text, excerpts, and article prose render in Source Serif 4 — no IBM Plex Mono paragraph text anywhere.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
