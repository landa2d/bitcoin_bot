---
phase: 04-hub-block-and-status-renderer
plan: 04
subsystem: ui
tags: [frontend, spa, renderer, status, maturity, supabase, economy-map]

# Dependency graph
requires:
  - phase: 04-hub-block-and-status-renderer
    plan: 01
    provides: "SPA shell — #status-view + #status-content target, showView('status') extension, STATUS_PAGE_HEADER / TIER_LABELS / MATURITY_STAGE module constants, loadStatus() stub, .status-row CSS"
  - phase: 04-hub-block-and-status-renderer
    plan: 02
    provides: "First sb.schema('economy_map').from('blocks') read idiom + confirmed column list (status mirrors/trims it); tierSection helper shape"
  - phase: 04-hub-block-and-status-renderer
    plan: 03
    provides: "renderMaturityPill(b) hoisted to module scope — status reuses the single shared definition (does NOT re-declare)"
  - phase: 02-economy-map-schema-seven-block-seed
    provides: "economy_map.blocks (slug/title/subtitle/accent/tier/sort_order/maturity/last_synthesized_at), RLS anon-read posture, seven-block seed"
  - phase: 03-design-tokens
    provides: ".maturity-pill / [data-accent] → --accent-tier cascade, .tier-label + .status-row layout selectors in style-map.css"
provides:
  - "loadStatus() — single sb.schema('economy_map').from('blocks') query (trimmed column list) ordered by sort_order asc, same source as the hub (RNDR-04), no defensive RLS filter"
  - "renderStatus(data) — three tier sections (SUBSTRATE/BEHAVIOR/FRAME) of NON-clickable status rows: maturity pill + title + optional subtitle + last_synthesized_at affordance ('synthesized <date>' / 'never synthesized')"
  - "Source-level RNDR-04 evidence: three economy_map.blocks reads now exist (hub + block-page + status), hub and status sharing the identical query shape"
affects: [04-06-deploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Status renderer reuses the renderHub composition idiom (filter-by-tier in JS + tierSection helper) against the same blocks query — RNDR-04 single-source-of-truth realized in code"
    - "Status rows are <div class=\"status-row\">, NOT <a> — status is the snapshot surface, hub owns navigation (D-15)"
    - "Trimmed .select() column list (no live_tension, no current_body_version_id) — status renders only what a snapshot row needs"
    - "Computed synthText ('synthesized <date>' / 'never synthesized') passes through escapeHtml for defense-in-depth even though formatDate already produced it"

key-files:
  created:
    - .planning/phases/04-hub-block-and-status-renderer/04-04-SUMMARY.md
  modified:
    - docker/web/site/app.js

key-decisions:
  - "loadStatus() .select() column list: slug,title,subtitle,accent,tier,sort_order,maturity,last_synthesized_at — the trim plan 04-02 anticipated (drops live_tension + current_body_version_id from the hub's full set, neither of which a status row renders). The KEY shape — sb.schema('economy_map').from('blocks')...order('sort_order', { ascending: true }) — is identical to loadHub, which is the RNDR-04 contract."
  - "Reused the module-scoped renderMaturityPill (hoisted by plan 04-03) directly — did NOT re-declare (acceptance criterion: exactly one definition; confirmed count = 1)."
  - "Used the same tierSection(label, blocks) helper shape as renderHub (with the defensive empty-array skip) rather than inlining three sections — DRY, source still emits the literal <section class=\"tier-section\"> / <h2 class=\"tier-label\"> markup the verifier greps for. Functionally identical to the plan's step-5 inlined example."
  - "window.currentStatusBlocks stashed for symmetry with the other loaders even though status has no v1 re-render hooks (no setMode dependency, no poll)."

patterns-established:
  - "Third and final economy_map.blocks reader in app.js — completes the hub + block + status renderer trio for Phase 4"

requirements-completed: [RNDR-03, RNDR-04]

# Metrics
duration: 2min
completed: 2026-05-28
---

# Phase 4 Plan 04: Status Renderer Summary

**The maturity snapshot is now operator-visible: `loadStatus()` reads all seven `economy_map.blocks` in one ordered query — the SAME query shape the hub uses (RNDR-04 single source of truth) — and `renderStatus()` paints three tier sections of non-clickable rows, each a maturity pill + title + optional subtitle + a "synthesized <date>" / "never synthesized" affordance.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-28T07:33:36Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Replaced the no-op `loadStatus()` stub (shipped by plan 04-01) with a real loader: a single `sb.schema('economy_map').from('blocks').select('slug,title,subtitle,accent,tier,sort_order,maturity,last_synthesized_at').order('sort_order', { ascending: true })` query (D-16), an error guard that writes "Status data unavailable." into `#status-content` and still sets the `STATUS_PAGE_HEADER` hero, a `window.currentStatusBlocks` stash, hero update to `STATUS_PAGE_HEADER` + `'updated ' + formatDate(NOW)` (D-02), then `renderStatus(data)`. No defensive `.eq('status', ...)` filter — RLS is the boundary (D-17).
- Added `renderStatus(data)`: groups blocks by tier in JS (the query is already sort_order-ascending so seed order is preserved), and writes three tier sections to `#status-content`.
- Each row is a `<div class="status-row" data-accent="{accent}">` (NOT an `<a>` — D-15: status is the snapshot surface, hub owns navigation) wrapping the maturity pill, `<div class="status-title">`, a conditional `<div class="status-subtitle">` (only when subtitle is truthy), and a `<time class="status-synth">`. The `data-accent` drives the left-border stripe via the `--accent-tier` cascade.
- The synth affordance computes `'synthesized ' + formatDate(last_synthesized_at)` when non-null, `'never synthesized'` when null (D-15). In the v1 all-null seed state every row reads "never synthesized".
- Reused the module-scoped `renderMaturityPill(b)` (hoisted by plan 04-03) — did not re-declare; the function still exists exactly once in the file.
- Every DB string (`accent`, `title`, `subtitle`) and the computed `synthText` passes through `escapeHtml()`. No template literals introduced — single-quote + `+` concatenation throughout. No `setMode()` hooks and no poll (status does not depend on technical/strategic mode and has no live-update requirement — RNDR-06 is scoped to the block page's Evolution section).

## Task Commits

1. **Task 1: Implement loadStatus() + renderStatus() inside app.js** — `e17bbf7` (feat)

## Files Created/Modified

- `docker/web/site/app.js` — +73/−1 lines: `loadStatus()` body replaced; new `renderStatus(data)` with inner `renderStatusRow` and `tierSection` helpers, placed where the stub lived (before `function route()`). File now 677 lines.

## Output Notes (for downstream plans)

- **Final `.select()` column list (loadStatus):** `slug,title,subtitle,accent,tier,sort_order,maturity,last_synthesized_at`. Compared to plan 04-02's `loadHub` list (`slug,title,subtitle,accent,tier,sort_order,maturity,live_tension,current_body_version_id,last_synthesized_at`), status drops `live_tension` and `current_body_version_id` — neither is rendered in a status row. This is exactly the trim plan 04-02's SUMMARY anticipated.
- **RNDR-04 source-level evidence:** `app.js` now contains three `economy_map.blocks` reads — `loadHub()` (line ~364, chained), `loadBlock()` (line ~447, inline), and `loadStatus()` (line ~587, chained). The hub and status reads share the identical query shape (`sb.schema('economy_map').from('blocks')...order('sort_order', { ascending: true })`), differing only in the trimmed status column list. This is the source-of-truth precondition for RNDR-04; the runtime cross-check (mutate one block's maturity in DB → both hub and status reflect it on next nav) is plan 04-06's deploy-time activity.
- **DOM container assumption:** zero gaps — plan 04-01 provided `#status-content` exactly as needed.

## Decisions Made

- Trimmed the status `.select()` to the eight columns a status row uses (dropped `live_tension`, `current_body_version_id`) — the query SHAPE (same table, same schema, same order) is what RNDR-04 requires, not an identical column list.
- Reused the module-scoped `renderMaturityPill` (hoisted by plan 04-03) directly rather than re-declaring — satisfies "exactly one definition" and forward-compatible.
- Used the `tierSection(label, blocks)` helper (same shape as renderHub, with the defensive empty-array skip) rather than three inlined sections — DRY, and the source still emits the literal `<section class="tier-section">` / `<h2 class="tier-label">` markup the verifier greps for.

## Deviations from Plan

None — plan executed exactly as written. The renderer follows the loadList()/renderList() four-step idiom, reuses the renderHub tier-grouping pattern, matches the tokens-preview.html pill contract via the shared helper, and honors all referenced decisions (D-02, D-15, D-16, D-17).

## Threat Model Acceptances

- **T-04-04-01 (XSS via DB strings) — MITIGATED.** `block.title`, `block.subtitle`, `block.accent`, and the computed `synthText` (which embeds `formatDate(last_synthesized_at)`) all pass through `escapeHtml()` before string-concat → innerHTML. `maturity` is escaped inside the shared `renderMaturityPill` (`aria-label` + `data-accent`). No DB string reaches innerHTML unescaped; status renders no markdown (no `marked.parse` path), so there is no escapeHtml bypass on this surface at all.
- **T-04-04-02 (Information Disclosure — maturity values public) — ACCEPTED.** Same disposition as plan 04-02 T-04-02-03: the seven blocks are public editorial surface; RLS authorizes anon reads.
- **T-04-04-03 (DoS — tight #/status refresh loop) — ACCEPTED.** No state mutation; one cheap RLS-bounded PostgREST read (7 rows) per nav. Same risk envelope as the hub.

## Issues Encountered

The plan's `<verify>` block contained two heuristic checks that produced false positives against this codebase's idiomatic method-chaining, both reconciled without code change (identical to the reconciliations plans 04-02 and 04-03 documented):

- **`grep -cE 'sb\.schema(.economy_map.).from(.blocks.)'` expecting ≥ 2** counts single-line matches only and reports **1** — it catches just the inline block-page query (line 447). The hub and status queries are chained across multiple lines (`.schema('economy_map')` and `.from('blocks')` on separate lines), so the single-line grep cannot see them. The TRUE contract was verified with a multiline-aware `grep -ozP` (count = 3 reads: hub + block-page + status) and by direct inspection of the hub (lines 364-368) and status (lines 587-591) query blocks — both share the identical `.schema('economy_map').from('blocks')...order('sort_order', { ascending: true })` shape. RNDR-04 source-level evidence is present.
- **`node -e "new Function(...)"` parse check** fails on the file's top-level `const` declarations under node v20 (the same edge case plans 04-02/04-03 hit). Used `node --check docker/web/site/app.js` instead — clean parse.

## Verification Performed

- All plan grep checks pass: `async function loadStatus`, `function renderStatus`, `sb.schema('economy_map').from('blocks')`, `STATUS_PAGE_HEADER`, `TIER_LABELS.substrate/.behavior/.frame`, `class="status-row"`, `class="status-title"`, `class="status-synth"`, `never synthesized`, `function renderMaturityPill`.
- No executable RLS-redundant filters in `loadStatus`/`renderStatus` — the only `.eq('status'` match in the status region is inside an explanatory comment documenting its deliberate absence (same pattern plans 04-02/04-03 used).
- `status-row` is preceded by `<div` (not `<a>`) — rows are non-clickable per D-15.
- `escapeHtml` appears 4× inside `renderStatusRow` (accent, title, subtitle, synthText); `status-subtitle` is conditional on truthy `b.subtitle`; `STATUS_PAGE_HEADER` referenced in both `updateHero` calls (error + success paths).
- `renderMaturityPill` declared exactly once (count = 1) and invoked inside `renderStatusRow`.
- Only one backtick in the file (pre-existing regex char-class at line 167 in `renderList`, untouched) — no template literals introduced.
- `node --check docker/web/site/app.js` → clean parse.
- Headless VM smoke test (4-block fixture across all three tiers) confirmed: three tier-section headings from `TIER_LABELS`; exactly 4 `status-row` divs (no anchors); 4 maturity pills × 5 segs = 20 segs; correct `data-stage` per `MATURITY_STAGE`; null `last_synthesized_at` → "never synthesized"; non-null → "synthesized May 21, 2026"; title escaped (`Id &amp; Trust`); subtitle rendered when present; null-subtitle row omits the `status-subtitle` div.

## Known Stubs

None. `loadStatus` and `renderStatus` are fully implemented. The "never synthesized" labels are intentional D-15 v1 empty-state behavior (no synthesis has run yet — the entire state until Phase 7/9 synthesis + approval ship), not stubs.

## User Setup Required

None — no external service configuration. The status renderer becomes operator-visible after the Wave 4 deploy (plan 04-06) rebuilds the `web` container. End-to-end browser verification (visit `#/status`; "Maturity Snapshot" + today's date hero; three tier headings; seven non-clickable rows in correct sort_order; each row's 1/5 pill + "never synthesized"; one PostgREST GET with `Accept-Profile: economy_map`; the RNDR-04 mutate-and-cross-check) happens at that checkpoint per the plan's `<verification>` section.

## Next Phase Readiness

- Plan 04-06 (deploy) has the full renderer trio in place: hub (04-02), block (04-03), and status (04-04) all read `economy_map.blocks` through the shared `sb.schema('economy_map')` idiom. The RNDR-04 runtime cross-check (mutate one block's maturity → both hub and status reflect it on next nav) is now technically grounded — the same query shape exists on both surfaces.
- No blockers. The `#status-content` contract held with zero shell changes; the third and final `economy_map.blocks` reader is now in production code.

## Self-Check: PASSED

- Files verified present: `docker/web/site/app.js`, `.planning/phases/04-hub-block-and-status-renderer/04-04-SUMMARY.md`
- Commit verified in git: `e17bbf7`

---
*Phase: 04-hub-block-and-status-renderer*
*Completed: 2026-05-28*
