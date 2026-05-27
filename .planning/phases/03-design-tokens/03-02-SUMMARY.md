---
phase: 03-design-tokens
plan: 02
subsystem: web-frontend
tags: [design-tokens, preview, standalone-html, verification-artifact]
dependency-graph:
  requires:
    - 03-01 (style-map.css contract — .maturity-pill, .timeline-entry, data-accent, --accent-tier)
    - style-shared.css (mode-toggle styles, container max-width, body.technical/strategic variable blocks)
    - Caddyfile (file_server matches /tokens-preview.html before SPA try_files fallback)
  provides:
    - "ROADMAP SC#1 verification artifact: deployable standalone preview rendering 4 accents, 5 maturity stages, 3 timeline-entry edge cases"
    - "Operator-reviewable surface for spot-checking on-dark contrast variants in technical mode"
    - "Phase 3's deliverable that proves the CSS contract Phase 4 will consume"
  affects:
    - docker/web/site/ (one new file added; no other file changed)
    - "Plan 03-03 (deploy) — rebuilds the web container so /tokens-preview.html becomes reachable at aiagentspulse.com/tokens-preview.html"
tech-stack:
  added:
    - "Standalone (non-SPA) HTML file pattern in docker/web/site/ (first of its kind alongside index.html)"
  patterns:
    - "Deliberate SPA bypass: no app.js, no Supabase CDN, no __SUPABASE_*__ placeholders"
    - "Inline minimal setMode() — body-class swap only (no localStorage, no URL param, no re-render hooks)"
    - "CSS-variable cascade leveraged via body.technical/strategic + [data-accent] from style-map.css"
key-files:
  created:
    - docker/web/site/tokens-preview.html
  modified: []
decisions:
  - "Honored D-11 default — preview ships as a deployable static file, not an out-of-tree .planning/ artifact"
  - "Honored 'Other Claude discretions' empty-source rule — source-null sample has neither data-source attribute nor <a class=\"timeline-source\"> element"
  - "Literal ↗ glyph (U+2197) used in markup, not &#8599; or SVG (CONTEXT.md preference)"
  - "8 swatches achieved via 4 swatch elements × 2-mode toggle (operator clicks Technical/Strategic to observe both pinned-base hex and on-dark variant) — alternative dual-render-in-DOM was rejected to avoid duplicating cascade-driven state"
  - "Wrapped Section 3 in data-accent=\"teal\" so .timeline-source tints exercise the var(--accent-tier, var(--accent)) cascade defined in 03-01"
metrics:
  duration_minutes: 4
  tasks_completed: 2
  files_created: 1
  files_modified: 0
  lines_added: 169
completed: 2026-05-27
---

# Phase 3 Plan 02: Tokens Preview Page Summary

Created `docker/web/site/tokens-preview.html` — a 169-line standalone deployable HTML file that renders every visual surface Phase 3 ships (4 tier-accent swatches with on-dark variants, 20 maturity-pill renders across 4 accents × 5 stages, 3 timeline-entry samples covering normal / source-null / long-text-wrap edge cases) with a mode toggle identical to edition pages so the operator can verify the on-dark contrast variants in technical mode. The page deliberately bypasses the SPA — no app.js, no Supabase CDN, no `__SUPABASE_*__` placeholders — and is served directly by Caddy's `file_server` (matches before `try_files` SPA fallback). This is the verification artifact for ROADMAP SC#1.

## Tasks Executed

| Task | Commit | Description |
| ---- | ------ | ----------- |
| 1 | `723a41e` | Scaffold tokens-preview.html shell: head with both stylesheets, body.technical default, mode-toggle markup, inline setMode() body-class swap, empty `<main id="preview-main">` container |
| 2 | `3a15d0e` | Populate `<main id="preview-main">` with 3 sections: 4 tier-accent swatches, 4×5 maturity-pill grid (20 instances), 3 timeline-entry samples (normal + source-null + long-text wrap) |

## Verification Results

| Check | Expected | Actual | Result |
| ----- | -------- | ------ | ------ |
| File exists | yes | yes | PASS |
| Starts with `<!DOCTYPE html>` | yes | yes | PASS |
| `<link rel="stylesheet" href="/style-shared.css">` present | yes | yes | PASS |
| `<link rel="stylesheet" href="/style-map.css">` present | yes | yes | PASS |
| `<body class="technical">` (default to dark) | yes | yes | PASS |
| `<title>AgentPulse — Design Tokens Preview</title>` | yes | yes | PASS |
| Mode-toggle buttons with `onclick="setMode(...)"` | 2 | 2 | PASS |
| Inline `function setMode(mode)` defined | yes | yes | PASS |
| `class="maturity-pill"` count | 20 | 20 | PASS |
| `data-stage="1"` through `="5"` count each | 4 | 4 each | PASS |
| `class="timeline-entry"` count | 3 | 3 | PASS |
| `class="timeline-source"` count | 2 | 2 | PASS |
| Literal `source ↗` occurrences | ≥ 4 | 4 | PASS |
| `data-accent="teal"` count | ≥ 6 | 8 | PASS |
| `data-accent="purple"/coral/gray` count | ≥ 6 | 6 each | PASS |
| `__SUPABASE_URL__` count | 0 | 0 | PASS |
| `__SUPABASE_ANON_KEY__` count | 0 | 0 | PASS |
| `/app.js` references | 0 | 0 | PASS |
| `supabase-js` references | 0 | 0 | PASS |
| File line count | ≥ 80 (must_haves) | 169 | PASS |
| `data-stage="5"` substring present (must_haves contains) | yes | yes | PASS |

## Output Confirmations (from plan `<output>` block)

- **File line count of tokens-preview.html:** 169 lines
- **Zero SPA-wiring placeholders:** confirmed via `grep -c __SUPABASE_URL__ docker/web/site/tokens-preview.html` returns 0 (also 0 for `__SUPABASE_ANON_KEY__`, `/app.js`, `supabase-js`)
- **20-pill grid + 3-entry timeline present:** confirmed via `grep -c 'class="maturity-pill"'` returns 20, `grep -c 'class="timeline-entry"'` returns 3
- **Final visual verification waits on Plan 03-03 deployment:** correct — the file lives in the repo but is not yet served by the running web container. Plan 03-03 rebuilds the container and surfaces `aiagentspulse.com/tokens-preview.html` for live operator review.

## Files Touched

| File | Change | Lines |
| ---- | ------ | ----- |
| `docker/web/site/tokens-preview.html` | created | +169 |

## Deviations from Plan

None — plan executed exactly as written. Both tasks' action blocks were applied verbatim (Task 1 written, Task 2 used Edit to replace the `<main id="preview-main"></main>` placeholder with the populated three-section block).

## Authentication Gates

None.

## Known Stubs

None. The preview is a verification surface; all rendered content (sample timeline text, hex labels) is intentional static fixture content, not stub data. Sample external URLs use `example.com` (IANA reserved per RFC 2606) so no real third-party domain is implicitly advertised.

## Self-Check

Both task commits verified present in branch history:

- `723a41e feat(03-02): scaffold tokens-preview.html shell with mode toggle`
- `3a15d0e feat(03-02): populate preview with 8 swatches, 20 pills, 3 timeline entries`

`docker/web/site/tokens-preview.html` confirmed present (169 lines, file_size > 0).

## Self-Check: PASSED

## What's Next

- **Plan 03-03** rebuilds the `web` container (`docker compose up -d --build web`) so `/tokens-preview.html` is served at `aiagentspulse.com/tokens-preview.html`. The Caddyfile already routes static files before the SPA fallback (Phase 1 §1 + Caddyfile lines 11–12), so no Caddyfile edit is needed.
- **Operator visual review** at `aiagentspulse.com/tokens-preview.html` closes ROADMAP SC#1 ("standalone preview renders the four tier accent colors correctly across both modes"). The operator should verify each accent renders in both modes by toggling Technical/Strategic and observing the swatches + pill colors swap.
- **Phase 4** consumes the same CSS contract (`data-accent`, `data-stage`, `.timeline-entry`) when wiring map hash routes in `app.js`. This preview is the spec Phase 4 verifies against.
