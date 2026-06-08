---
phase: 11-design-system-nav-shell
plan: 01
subsystem: ui
tags: [css, design-tokens, css-custom-properties, source-serif-4, ibm-plex-mono, google-fonts, vanilla-js-spa]

# Dependency graph
requires:
  - phase: v1.0 frontend (docker/web/site)
    provides: existing vanilla-JS SPA (index.html + style-shared.css + style-map.css + app.js hash router), Caddy CSP already whitelisting Google Fonts origins
provides:
  - New style-base.css token layer — single light :root palette (one violet accent #5b3df5), --serif/--mono font-stack tokens, 4px-grid spacing tokens, 3/7/8/10 radius tokens
  - Serif 18px/1.62 body base + .page-title / .eyebrow display classes (D-02)
  - Google Fonts <link> (Source Serif 4 + IBM Plex Mono, weights 400/600 only) loaded first in index.html <head>
  - style-shared.css de-darkened — dark body.technical/body.strategic var blocks retired, body-level Courier removed, legacy nav/back-link rules deleted
affects: [12-newsletter-section-restyle, 13-agent-economy-grid, 14-about-stub-polish]

# Tech tracking
tech-stack:
  added: [Source Serif 4 (Google Fonts), IBM Plex Mono (Google Fonts)]
  patterns:
    - "CSS theming via :root custom properties (never body.x-scoped palettes — specificity bug D-04 forbids)"
    - "Load-order-as-cascade-control: style-base.css <link> first, before style-shared.css/style-map.css (no build step)"
    - "Two-family type system: --serif for reading, --mono for UI chrome only; weights 400/600 only"

key-files:
  created: [docker/web/site/style-base.css]
  modified: [docker/web/site/index.html, docker/web/site/style-shared.css]

key-decisions:
  - "style-base.css authored as a new first-loaded stylesheet; dark body.technical/strategic var blocks deleted (not shadowed) so :root wins (D-04)"
  - "Residual component Courier New in style-shared.css migrated to var(--mono) rather than left in place — required to satisfy the Task 3 verify gate (ugrep grep -vq semantics) and the acceptance criterion that the file contain no 'Courier New' string"
  - "Google Fonts <link> trimmed to weights 400;600 only (500/700 deliberately not requested) per UI-SPEC weight policy; CSP untouched"

patterns-established:
  - "Pattern 1: One light-mode :root palette, one accent, no per-tier/mode accent flip"
  - "Pattern 2: --mono (IBM Plex Mono) is the canonical chrome font token; serif body via --serif"

requirements-completed: [COLOR-01, COLOR-02, TYPE-01, TYPE-02, TYPE-03]

# Metrics
duration: 8min
completed: 2026-06-04
---

# Phase 11 Plan 01: Design System Foundation Summary

**New style-base.css token layer — single light-mode violet-accent :root palette, Source Serif 4 / IBM Plex Mono typography with 18px/1.62 serif body + .page-title/.eyebrow display classes — loaded first in index.html, with the dark body.technical/strategic var blocks and body-level Courier retired from style-shared.css so the new palette actually takes effect (D-04).**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-06-04T17:37Z (approx)
- **Completed:** 2026-06-04T17:45:01Z
- **Tasks:** 3
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments
- Authored `style-base.css`: single light `:root` palette (11 tokens, one violet accent `#5b3df5`), `--serif`/`--mono` font-stack tokens, 4px-grid spacing tokens, 3/7/8/10 radius tokens, serif 18px/1.62 body base, and `.page-title` / `.eyebrow` display classes — weights 400/600 only, no second hue, no Courier (COLOR-01/02, TYPE-01/02/03, D-02).
- Wired the Google Fonts `<link>` (Source Serif 4 + IBM Plex Mono, weights `400;600` only, `display=swap`) plus two preconnects, and loaded `style-base.css` **first** — before `style-shared.css`/`style-map.css` — making load order the cascade control (D-04). CSP/Caddyfile untouched.
- Retired the dark dual-accent `body.technical` / `body.strategic` var blocks, removed the body-level `Courier New` font, and deleted the legacy `.top-nav` family + `.back-link` rules from `style-shared.css` (the D-04 hard constraint) while preserving the `*` reset and `.mode-transitioning`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Author style-base.css — :root tokens + serif typography + display/eyebrow classes** - `c61faad` (feat)
2. **Task 2: Wire Google Fonts + load style-base.css first in index.html <head>** - `aa82fa5` (feat)
3. **Task 3: Retire dark var blocks + Courier body + nav/back-link in style-shared.css (D-04)** - `6d429b2` (feat)

## Files Created/Modified
- `docker/web/site/style-base.css` (created, 72 lines) — single light `:root` palette + spacing/radius tokens + serif 18px/1.62 body + `.page-title`/`.eyebrow` display classes.
- `docker/web/site/index.html` (modified) — added Google Fonts `<link>` (400;600) + 2 preconnects + `style-base.css` link first in `<head>`.
- `docker/web/site/style-shared.css` (modified, −123/+29) — deleted dark `body.technical`/`body.strategic` blocks, removed body-level Courier, deleted `.top-nav` family + `.back-link`, migrated residual component Courier → `var(--mono)`; `*` reset + `.mode-transitioning` preserved.

## Decisions Made
- **Migrate residual Courier → `var(--mono)` (vs. leave in place):** The plan's Task 3 *action* text said to delete only the body-level Courier and leave component-rule Courier (acceptable under batch-deploy). However, the binding Task 3 `<verify>` gate and its `<acceptance_criteria>` both require `style-shared.css` to contain **no** `Courier New` string. Under this environment's `grep` (ugrep), `grep -vq "Courier New"` only exits 0 when the pattern is fully absent. To make the gate PASS and satisfy the acceptance criterion, every `font-family: 'Courier New', monospace;` was replaced with `font-family: var(--mono);` (IBM Plex Mono — the chrome successor token defined in style-base.css and mandated by UI-SPEC §Typography). This is cascade-correct and matches the SPEC's two-family system. Tracked below as a Rule 3 deviation.
- Reworded the three retirement comments so they no longer contain the literal `.top-nav` / `.back-link` / `Courier New` tokens, keeping the absence checks unambiguous.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Migrated residual component `Courier New` → `var(--mono)` to satisfy the Task 3 verify gate**
- **Found during:** Task 3 (Retire dark var blocks + Courier body in style-shared.css)
- **Issue:** The plan action said component-rule `Courier New` could remain, but the task's `<verify>` gate (`grep -vq "Courier New"`, evaluated by this environment's ugrep) and `<acceptance_criteria>` ("no longer contains the string `Courier New`") both require the string to be globally absent from the file. With ~18 component rules still using Courier, the gate failed.
- **Fix:** Replaced every `font-family: 'Courier New', monospace;` declaration with `font-family: var(--mono);` (IBM Plex Mono chrome token from style-base.css — the SPEC-mandated mono successor). Also stripped the literal `Courier New` from the body-rule comment.
- **Files modified:** docker/web/site/style-shared.css
- **Verification:** Task 3 gate now returns PASS; `grep -F "Courier New"` finds zero matches; 18 rules now resolve `var(--mono)`; `*` reset + `.mode-transitioning` preserved; style-map.css untouched.
- **Committed in:** `6d429b2` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking).
**Impact on plan:** The change is gate-driven and SPEC-aligned (IBM Plex Mono is the contracted chrome font); it advances rather than deviates from the design intent. These component rules are owned by Phases 12–13 and may still render rough locally between phases (acceptable under batch-deploy, D-01). No scope creep beyond the edited file.

## Issues Encountered
- **`grep` is aliased to `ugrep` in this environment**, which (a) treats leading `--token` as an option (worked around with `grep -F -e`) and (b) gives `grep -vq PATTERN` "pattern fully absent" semantics rather than GNU grep's "any line lacks pattern". The second behavior is what made the Task 3 gate require total Courier removal — resolved as the Rule 3 deviation above. All three task gates PASS as written.

## User Setup Required
None - no external service configuration required. Google Fonts load via the existing CSP whitelist (Caddyfile unchanged); no env vars, no build step, no deploy this phase (D-01 batch deploy).

## Next Phase Readiness
- Token foundation is ready: every later v2.0 phase restyles on top of `style-base.css` `:root` tokens, the serif/mono type system, and the `.page-title`/`.eyebrow` classes.
- Plan 02 (same phase) adds the sticky 3-tab nav shell + back-control styles into `style-base.css`, the `<header>` markup + tabs in `index.html`, and the route→active-tab wiring in `app.js` (NAV-01..04). The legacy `.top-nav`/`.back-link` rules it supersedes are already gone.
- Known acceptable rough edge (D-01 batch-deploy): newsletter/article/map component rules in `style-shared.css`/`style-map.css` now resolve against the light `:root` and `var(--mono)`; Phases 12–13 own their final restyle. No live deploy performed.

## Self-Check: PASSED

- Files: style-base.css, index.html, style-shared.css, 11-01-SUMMARY.md all FOUND on disk.
- Commits: c61faad, aa82fa5, 6d429b2 all FOUND in git log.
- All three task `<verify>` grep gates return PASS.

---
*Phase: 11-design-system-nav-shell*
*Completed: 2026-06-04*
