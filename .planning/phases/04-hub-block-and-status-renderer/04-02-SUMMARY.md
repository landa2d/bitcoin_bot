---
phase: 04-hub-block-and-status-renderer
plan: 02
subsystem: ui
tags: [frontend, spa, renderer, hub, supabase, economy-map]

# Dependency graph
requires:
  - phase: 04-hub-block-and-status-renderer
    plan: 01
    provides: "SPA shell — #map-view container with .content-area, showView('map') extension hiding the mode toggle, module constants (HUB_STORYLINE, MATURITY_STAGE, TIER_LABELS), loadHub() stub"
  - phase: 02-economy-map-schema-seven-block-seed
    provides: "economy_map.blocks (slug/title/subtitle/accent/tier/sort_order/maturity/live_tension/current_body_version_id/last_synthesized_at), RLS anon-read posture, seven-block seed"
  - phase: 03-design-tokens
    provides: ".maturity-pill / [data-accent] / --accent-tier cascade, .tier-label + .block-tile layout selectors in style-map.css"
provides:
  - "loadHub() — single sb.schema('economy_map').from('blocks') query ordered by sort_order asc, no defensive RLS filter"
  - "renderHub(data) — three tier sections (SUBSTRATE/BEHAVIOR/FRAME) of anchor-style block tiles, each with title + subtitle + 5-segment maturity pill, plus a hub-storyline preface"
  - "Confirmed column list for economy_map.blocks reads (plan 04-04 status can mirror/trim it)"
affects: [04-04-status-renderer, 04-06-deploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "supabase-js v2 .schema('economy_map').from('blocks') sets Accept-Profile automatically — first economy_map read in app.js"
    - "Renderer composes via small in-function helpers (renderTile / renderMaturityPill / tierSection) returning single-quoted string-concat HTML — no template literals"
    - "Maturity pill emits exactly 5 <span class=\"seg\"></span> children; fill keyed off data-stage by Phase 3 CSS"
    - "Empty tier array skipped to avoid a dangling tier-label heading (defensive)"

key-files:
  created:
    - .planning/phases/04-hub-block-and-status-renderer/04-02-SUMMARY.md
  modified:
    - docker/web/site/app.js

key-decisions:
  - "HUB_STORYLINE kept verbatim from plan 04-01 (114 chars): 'Synthesis with editorial integrity. Eight blocks, seven shipped, one deferred — the agent economy as a living map.' — not revised"
  - "Column list passed to .select(): slug,title,subtitle,accent,tier,sort_order,maturity,live_tension,current_body_version_id,last_synthesized_at (full set per plan; plan 04-04 status needs only slug,title,subtitle,accent,tier,sort_order,maturity,last_synthesized_at)"
  - "Hub 'updated' stamp derived from the latest non-null last_synthesized_at across all blocks (ISO string-sort); omitted entirely in the all-null v1 state"
  - "Tier sections emitted via a tierSection(label, blocks) helper (called 3x) rather than three inlined blocks — DRY, source still contains the literal section/tier-label markup the verifier greps for, and adds the defensive empty-array skip"

patterns-established:
  - "First economy_map.blocks browser read lands the sb.schema('economy_map') idiom that plan 04-03 (block) and 04-04 (status) reuse"

requirements-completed: [RNDR-01, RNDR-04]

# Metrics
duration: 3min
completed: 2026-05-28
---

# Phase 4 Plan 02: Hub Renderer Summary

**The economy-map hub is now operator-visible: `loadHub()` reads all seven `economy_map.blocks` in one ordered query and `renderHub()` paints three tier sections of anchor tiles — title, subtitle, and a 5-segment maturity pill each — under a hardcoded storyline preface.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-28T07:20:12Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Replaced the no-op `loadHub()` stub (shipped by plan 04-01) with a real loader: a single `sb.schema('economy_map').from('blocks').select(...).order('sort_order', { ascending: true })` query (D-16), an error guard that writes "Map data unavailable." into `#map-view .content-area` and still sets the storyline hero, `window.currentBlocks` stash, then `renderHub(data)`. No defensive `.eq('status', ...)` / `.neq('block_slug', ...)` filter — RLS is the boundary (D-17).
- Added `renderHub(data)`: computes the hero ("updated <date>" from the latest non-null `last_synthesized_at`, omitted when all null), groups blocks by tier in JS (the query is already sort_order-ascending so seed order is preserved), and writes the storyline preface + three tier sections to `#map-view .content-area`.
- Each tile is a single `<a href="#/map/{slug}" data-accent="{accent}" class="block-tile">` wrapping `<h3 class="tile-title">`, `<p class="tile-subtitle">`, and a maturity pill — the whole tile is the link (D-14). The pill matches the canonical `tokens-preview.html` markup exactly: 5 `<span class="seg"></span>` children, `data-stage` resolved via `MATURITY_STAGE[b.maturity] || 1`, `data-accent` + `aria-label` set.
- Every DB string (`title`, `subtitle`, `accent`, `maturity`) passes through `escapeHtml()`; `slug` is `encodeURIComponent`'d into the href (T-04-02-01 / T-04-02-02 mitigations). No template literals introduced — single-quote + `+` concatenation throughout.

## Task Commits

1. **Task 1: Implement loadHub() + renderHub() inside app.js** — `f3fa403` (feat)

## Files Created/Modified

- `docker/web/site/app.js` — +79/-1 lines: `loadHub()` body replaced; new `renderHub(data)` with inner `renderTile`, `renderMaturityPill`, and `tierSection` helpers, placed where the stub lived (before `function route()`). File now 457 lines.

## Output Notes (for downstream plans)

- **Final HUB_STORYLINE:** unchanged from plan 04-01's draft — `Synthesis with editorial integrity. Eight blocks, seven shipped, one deferred — the agent economy as a living map.` (114 chars).
- **Exact `.select()` column list:** `slug,title,subtitle,accent,tier,sort_order,maturity,live_tension,current_body_version_id,last_synthesized_at`. Plan 04-04 (status) reads from the same `economy_map.blocks` source for RNDR-04 one-source-of-truth and may trim to `slug,title,subtitle,accent,tier,sort_order,maturity,last_synthesized_at` (drops `live_tension` and `current_body_version_id`, which the status row does not use).
- **DOM container assumptions:** zero gaps — plan 04-01 provided `#map-view > .content-area` exactly as needed; the render target `document.getElementById('map-view').querySelector('.content-area')` resolved with no shell changes required.

## Decisions Made

- Kept `HUB_STORYLINE` verbatim (the planner's draft was already PROJECT.md-aligned and under the 200-char cap).
- Derived the hub "updated" stamp from the newest non-null `last_synthesized_at` via ISO string-sort; in the v1 all-null state the date is omitted (correct empty-state per D-02).
- Used a `tierSection(label, blocks)` helper rather than three inlined section blocks. It keeps the source DRY, folds in the defensive "skip empty array" guard (step 5), and still emits the literal `<section class="tier-section">` / `<h2 class="tier-label">` markup the verifier greps for. Functionally identical to the plan's step-6 inlined example.

## Deviations from Plan

None — plan executed exactly as written. The renderer follows the loadList()/renderList() four-step idiom, matches the tokens-preview.html pill contract, and honors all referenced decisions (D-02, D-13, D-14, D-16, D-17).

## Issues Encountered

The plan's `<verify>` block contained two heuristic checks that produced false positives against an idiomatic implementation; both were reconciled without code change:

- **seg-count check** used `grep -cE` (counts matching *lines*), but the canonical pill markup puts all 5 `<span class="seg">` on one line (matching `tokens-preview.html` line 78). Verified the true contract with occurrence-count grep (`grep -oE ... | wc -l` → 5).
- **template-literal check** (`! grep -q '\``) flagged a single pre-existing backtick at line 164 — inside a regex character class in `renderList()` (shipped before Phase 4, untouched). No template literal was introduced; confirmed the only backtick is the pre-existing regex one.
- The plan's `node -e "new Function(...)"` parse check fails on top-level `const` under node v20; used the correct validator `node --check` instead — clean parse.

## Verification Performed

- `loadHub` + `renderHub` exist; schema query present (multiline-aware regex `\.schema\('economy_map'\)\s*\.from\('blocks'\)`); `order('sort_order', { ascending: true })`; full column list present.
- No `.eq('status')` / `.neq('block_slug')` filter inside `loadHub` (only the explanatory comment references the absence).
- Three `TIER_LABELS.*` references; `<section class="tier-section">` + `<h2 class="tier-label">` markup present; tile markup `class="block-tile"` + `class="maturity-pill"` present.
- 5 `<span class="seg"></span>` occurrences per pill; `escapeHtml(b.title)`, `escapeHtml(b.subtitle)`, `escapeHtml(b.accent)`, `escapeHtml(b.maturity)` all present; `data-stage` via `MATURITY_STAGE[b.maturity] || 1`.
- `updateHero(HUB_STORYLINE, dateText)` on the success path; render target `document.getElementById('map-view').querySelector('.content-area')`.
- `node --check` clean parse; no new template literals.

## User Setup Required

None. The hub becomes operator-visible after the Wave 4 deploy (plan 04-06) rebuilds the `web` container. Manual browser verification (`#/map` shows the storyline, three tier headings, seven tiles in seed order, one PostgREST GET with `Accept-Profile: economy_map`) happens at that end-to-end checkpoint.

## Next Phase Readiness

- Plan 04-04 (status) can mirror the `economy_map.blocks` read shape established here for RNDR-04 one-source-of-truth; the column list above is the reference.
- No blockers. The `#map-view .content-area` contract held with zero shell changes; the `sb.schema('economy_map')` data path is now exercised in production code.

## Self-Check: PASSED

- Files verified present: `docker/web/site/app.js`, `04-02-SUMMARY.md`
- Commit verified in git: `f3fa403`
