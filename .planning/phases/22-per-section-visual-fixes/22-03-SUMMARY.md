---
phase: 22-per-section-visual-fixes
plan: 03
subsystem: ui
tags: [css-grid, responsive, economy-map, maturity-pill, frontend, supabase-js]

# Dependency graph
requires:
  - phase: 22-per-section-visual-fixes
    provides: "22-01 (app.js eyebrow removal / EDITION_SUFFIX_RE) + 22-02 (style-shared.css made-cols CSS) — this plan is Wave 2, additive to both shared files"
  - phase: 20-width-tokens-centering-foundation
    provides: ".prose/.wide width axes + --space-*/--measure tokens the legend sits on"
  - phase: 21-single-scroll-landing-scroll-spy-nav
    provides: "the single-scroll #landing the #map section lives in (renderHub render target)"
provides:
  - "Agent Economy #map tier grids render 3-col on desktop (GRID-01), collapsing 3→2 at ≤880px → 1 at ≤600px"
  - "deferred frame block stays full-width spanning all 3 columns (D-08)"
  - "a single maturity legend under the page-title mirroring the real 5-seg .maturity-pill so its scale equals the cards' (GRID-02)"
  - "token-only .legend / .legend-label CSS — style-shared.css stays hex-free (RHYTHM-01)"
affects: [22-04, "phase 25 holistic responsive/a11y pass", "future #map section work"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Static decorative sample reuses a real component's markup (legend mirrors .maturity-pill data-stage=1) to guarantee scale equality without a second bar system"
    - "Responsive grid collapse via two compact single-line @media rules (3→2 ≤880px, 1 ≤600px) replacing a single mobile rule"

key-files:
  created: []
  modified:
    - docker/web/site/style-shared.css
    - docker/web/site/app.js

key-decisions:
  - "Consolidated the breakpoints by replacing the prior single mobile collapse rule with two single-line @media rules (D-06 discretion: where the breakpoints live)"
  - "Legend reuses the real .maturity-pill data-stage=1 markup verbatim (5 .seg) rather than inventing a second bar system — scale equality IS GRID-02 (D-07)"
  - "Legend pill is aria-hidden decorative; the surrounding mono labels carry meaning"
  - "No new economy_map query added — per-card fill stays MATURITY_STAGE[b.maturity], existing sb.schema('economy_map') read untouched (D-09, read-only)"

patterns-established:
  - "Pattern 1: A legend/key that must equal a live component's scale should reuse that component's exact markup + CSS (static instance), not a hand-drawn approximation"
  - "Pattern 2: Token-only CSS rules written as compact single-line bodies so `[^}]*` verification gates match; comments avoid literal strings that trip negative greps (e.g. no '640px' in a comment)"

requirements-completed: [GRID-01, GRID-02]

# Metrics
duration: ~10min
completed: 2026-06-12
---

# Phase 22 Plan 03: Agent Economy Map 3-Col Grid + Maturity Legend Summary

**The #map tier grids now render 3-col (collapsing 3→2 at ≤880px → 1 at ≤600px) with the deferred frame card full-width, and a single maturity legend under the heading mirrors the real 5-segment .maturity-pill so its scale literally equals the cards'.**

## Performance

- **Duration:** ~10 min
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `.grid` base rule changed `repeat(2, 1fr)` → `repeat(3, 1fr)` for 3-col desktop (GRID-01 / D-06); the only `.grid` consumer is the map's `tierSection`, so the change is map-scoped.
- The single mobile collapse rule replaced by two single-line breakpoints: `@media (max-width: 880px)` → `repeat(2, 1fr)` and `@media (max-width: 600px)` → `1fr` (3→2→1 collapse).
- `.card-deferred { grid-column: 1 / -1; }` left unchanged — the `frame`/regulation-legal block still spans all 3 columns as the map's closing frame (D-08).
- A maturity legend inserted ONCE in `renderHub`'s `.prose` header, directly after the page-title and before `subline`, reusing the real `.maturity-pill data-stage="1"` 5-`.seg` markup (■ □ □ □ □) so its scale equals the cards' (GRID-02 / D-07).
- Token-only `.legend` / `.legend-label` CSS appended (mono/--ink-faint chrome + --space-* spacing); style-shared.css remains hex-free (RHYTHM-01).

## Task Commits

Each task was committed atomically:

1. **Task 1: Tier grid 2→3 columns + responsive 3/2/1 breakpoints (GRID-01 / D-06 / D-08)** - `d38488b` (feat)
2. **Task 2: Maturity legend mirroring the real 5-seg pill + token-only .legend CSS (GRID-02 / D-07 / D-09)** - `4491ba2` (feat)

_Plan metadata commit added by the orchestrator (tracking is orchestrator-owned for this sequential run)._

## Files Created/Modified
- `docker/web/site/style-shared.css` - `.grid` → repeat(3,1fr); prior single mobile rule replaced by 3→2 (≤880px) / 1 (≤600px) breakpoints; net-new token-only `.legend` / `.legend-label` rules. `.card-deferred` unchanged.
- `docker/web/site/app.js` - `renderHub` emits a static `<div class="legend">` (Maturity label + real 5-seg `.maturity-pill data-stage="1"` + "nascent → established" label) once inside the `.prose` header. economy_map read, tierSection, grid column count, and deferred logic all unchanged.

## Decisions Made
- **Breakpoint placement (D-06 discretion):** Replaced the prior single mobile collapse rule in place with two compact single-line `@media` rules rather than scattering new media queries — keeps the responsive logic for `.grid` co-located.
- **Legend form (D-07):** Mirrors the real 5-segment pill (not the mockup's 3-bar sketch) so the legend's filled+empty scale equals the cards'. Reused `.maturity-pill`/`.seg` verbatim; no second bar system.
- **Read-only (D-09):** No new economy_map query/fetch; the legend is a static `data-stage="1"` sample. Per-card fill remains `MATURITY_STAGE[b.maturity]`, already correct in code.

## Deviations from Plan

None - plan executed exactly as written.

Note: during Task 1 the automated gate (`! grep '640px'`) initially failed because an explanatory comment I wrote contained the literal "@640px". Reworded the comment to "the prior single mobile rule" before committing — this was a verification-gate adjustment within the same task, not a code/behavior deviation. Both task gates printed PASS before their commits.

## Issues Encountered
- Task 1 gate first failed on the `! grep '640px'` clause due to the string "640px" appearing in a code comment (not in any media query). Resolved by rewording the comment; gate then printed PASS. No functional impact.

## Known Stubs
None. The legend is an intentional STATIC decorative sample (D-07 / D-09) — its `data-stage="1"` is a fixed scale key, not a stubbed data source. Per-card maturity fill is live via `MATURITY_STAGE[b.maturity]`.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Source changes are complete and syntax-validated (`node --check` passes on app.js). Live render verification (3 columns on desktop, 2 at ≤880px, 1 at ≤600px; legend visible once under the heading with matching scale; per-block pill fill == stored maturity) is owned by plan 22-04 (orchestrator-owned scoped `web` rebuild — worktree-unsafe).
- No backend, schema, or migration changes; no new attack surface (static legend string + a pure CSS column-count change; existing escaped economy_map read untouched).

---
*Phase: 22-per-section-visual-fixes*
*Completed: 2026-06-12*
