---
phase: 04-hub-block-and-status-renderer
plan: 03
subsystem: ui
tags: [frontend, spa, renderer, block, timeline, evolution, supabase, economy-map]

# Dependency graph
requires:
  - phase: 04-hub-block-and-status-renderer
    plan: 01
    provides: "SPA shell — #block-view + #block-content target, ← Map back-link static markup, showView('block') extension, LIVE_TENSION_PLACEHOLDER / MATURITY_STAGE constants, loadBlock() stub, .block-header/.block-tension/.block-body/.evolution/.timeline-show-all CSS"
  - phase: 04-hub-block-and-status-renderer
    plan: 02
    provides: "First sb.schema('economy_map').from('blocks') read idiom; renderMaturityPill markup (was nested inside renderHub — this plan hoisted it to module scope)"
  - phase: 02-economy-map-schema-seven-block-seed
    provides: "economy_map.blocks / block_body_versions / timeline_entries schema, RLS anon-read posture (published body versions + block_slug != 'unsorted'), live_tension seed placeholder (D-21)"
  - phase: 03-design-tokens
    provides: ".maturity-pill / .timeline-entry / [data-accent] → --accent-tier token surface; tokens-preview.html canonical markup"
provides:
  - "loadBlock(slug) — three-query orchestrator (blocks single + timeline_entries limit 30 newest-first via Promise.all, conditional block_body_versions by current_body_version_id), graceful timeline-failure degradation, window.currentBlock / window.currentTimelineEntries stash for the Wave 3 idle poll"
  - "renderBlock(block, bodyMd, entries) — six-part composition Title → tension → body → Evolution with D-10 empty-state hiding"
  - "renderTimelineEntries(entries, expanded) — newest-first timeline markup, source-null graceful variant, factored out for plan 04-05 idle-poll reuse"
  - "expandTimeline() — one-shot unbounded re-query at the 30-cap (D-11)"
  - "renderMaturityPill(b) hoisted to module scope — single shared definition for renderHub + renderBlock (+ renderStatus in plan 04-04)"
  - "module-level timelineExpanded flag — the expand-state contract plan 04-05 reads during the idle poll"
affects: [04-04-status-renderer, 04-05-idle-poll, 04-06-deploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Promise.all over coordinated economy_map reads (blocks + timeline_entries) with array-element destructuring (var pair = await Promise.all([...]); pair[0]/pair[1]) — first parallel-query pattern in app.js"
    - "Conditional second-stage fetch (block_body_versions) gated by an FK column from the first query"
    - "Empty-state hide via exact-string match (live_tension !== LIVE_TENSION_PLACEHOLDER) and truthiness (bodyMd) — quiet absence, no scaffolding (D-10)"
    - "body_md is the sole escapeHtml bypass (marked.parse), mirroring renderArticle(); all other DB strings escapeHtml'd"
    - "Outbound timeline-source anchors hardened with rel='noopener noreferrer' target='_blank'"
    - "renderMaturityPill hoisted from a nested inner function (plan 04-02) to module scope so multiple renderers share one definition"

key-files:
  created:
    - .planning/phases/04-hub-block-and-status-renderer/04-03-SUMMARY.md
  modified:
    - docker/web/site/app.js

key-decisions:
  - "renderMaturityPill was previously defined by plan 04-02 as a NESTED inner function inside renderHub(); this plan HOISTED it to module scope (placed near escapeHtml/formatDate) and removed the nested copy — so renderBlock can reference the same helper and the function exists exactly once (acceptance criterion). renderHub still calls renderMaturityPill(b) unchanged; behavior is identical."
  - "LIVE_TENSION_PLACEHOLDER exact-match comparison uses the single em-dash character '—' (U+2014), matching Phase 2 D-21 seed exactly — confirmed 1 U+2014 occurrence in the constant, no hyphen-minus substitution."
  - "Source-link glyph is the literal '↗' (source ↗) matching the style-map.css / tokens-preview.html contract; show-all glyph is the literal '↓' (Show all (N or more) ↓) matching style-map.css line 298. The plan's &uarr;/&darr; were XML-doc entities, not the intended runtime output."
  - "Show-all count label reads 'Show all (30 or more) ↓' at the cap (total unknown until expansion) — matches D-11 intent; expandTimeline() then renders the unbounded result and removes the button (one-shot)."
  - "Promise.all destructured via array indexing (pair[0]/pair[1]) rather than var [a,b] = ... — both parse clean, but indexing avoids any tooling edge case and reads consistently in the classic-script file."

patterns-established:
  - "First Promise.all coordinated-read pattern in app.js — plan 04-05's idle poll re-uses renderTimelineEntries() against the same timeline query shape"
  - "renderMaturityPill module-scope hoist is the shared-helper precedent plan 04-04 (status) follows"

requirements-completed: [RNDR-02, RNDR-07]

# Metrics
duration: 3min
completed: 2026-05-28
---

# Phase 4 Plan 03: Block Renderer Summary

**Block pages are now operator-visible: `loadBlock(slug)` fires the blocks row + 30 newest timeline entries in parallel (plus a conditional published-body fetch), and `renderBlock()` paints the Title → tension → body → Evolution composition with quiet empty-state hiding and a 30-cap "Show all" expand — every block renders even with no body and placeholder tension.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-28T07:25:44Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Replaced the no-op `loadBlock(slug)` stub (plan 04-01) with a real three-query orchestrator: a `blocks` single-row read keyed by `slug` and a `timeline_entries` read (`.eq('block_slug', slug).order('event_date', { ascending: false }).limit(30)`) fired together via `Promise.all`, then a conditional `block_body_versions` fetch only when `current_body_version_id` is non-null. Block-not-found writes "Block not found." + a "Block Not Found" hero and returns; timeline failures degrade gracefully (block still renders with `[]` entries). Stashes `window.currentBlock` / `window.currentTimelineEntries` and resets `timelineExpanded = false` on every entry (the Wave 3 plan 04-05 idle-poll contract).
- Added `renderBlock(block, bodyMd, entries)` — the six-part composition (D-08): always-render `<header class="block-header" data-accent="...">` with the inline maturity pill; conditional `<section class="block-tension">` hidden on the `LIVE_TENSION_PLACEHOLDER` seed (D-10); conditional `<section class="block-body">` rendered via `marked.parse(bodyMd)` and hidden when no body version (D-10); always-render `<section class="evolution">` with the entry list and the `.timeline-show-all` button when the result hit the 30-cap and not yet expanded (D-11).
- Added `renderTimelineEntries(entries, expanded)` — newest-first markup matching `tokens-preview.html` (with-source lines 114-125, source-null lines 128-137). With a non-empty `source_url`: `<article data-source>` + a `<a class="timeline-source" target="_blank" rel="noopener noreferrer">source ↗</a>`. With null/empty `source_url`: bare `<article class="timeline-entry">`, no `data-source` attribute, no source anchor. Empty array → "No timeline entries yet." Factored out so plan 04-05 re-uses it.
- Added `expandTimeline()` (top-level, callable from inline `onclick`) — one-shot: sets `timelineExpanded = true`, re-queries unbounded, replaces `#evolution-entries` innerHTML, removes the show-all button.
- Hoisted `renderMaturityPill(b)` from the nested inner function it was (inside plan 04-02's `renderHub`) up to module scope (near `escapeHtml`/`formatDate`) and removed the duplicate — so both `renderHub` and `renderBlock` share one definition and the function exists exactly once.
- Every DB string (`title`, `live_tension`, `what_shifted`, `why_it_mattered`, `source_url` in both `href` and `data-source`, `accent`, `maturity`) passes through `escapeHtml()`; `body_md` is the only path through `marked.parse()`. No template literals introduced; no RLS-redundant `.eq('status', 'published')` / `.neq('block_slug', 'unsorted')` filters (only explanatory comments reference their absence).

## Task Commits

1. **Task 1: Implement loadBlock(slug) + renderBlock() inside app.js** — `67a8d2e` (feat)

## Files Created/Modified

- `docker/web/site/app.js` — +158/−10 lines: `renderMaturityPill` hoisted to module scope; `var timelineExpanded = false;` added near `currentMode`; nested `renderMaturityPill` removed from `renderHub`; `loadBlock` body + `renderBlock` + `renderTimelineEntries` + `expandTimeline` added (replacing the stub).

## Output Notes (for downstream plans)

- **renderMaturityPill provenance:** plan 04-02 originally added `renderMaturityPill` as a NESTED inner function inside `renderHub()`. This plan (04-03) **hoisted it to module scope** and removed the nested copy, because `renderBlock()` also needs it and the acceptance criterion requires exactly one definition. `renderHub` still calls `renderMaturityPill(b)` — identical behavior, now resolving the module-scoped function. Plan 04-04 (status) should likewise call the existing module-scoped `renderMaturityPill` (do NOT re-declare).
- **LIVE_TENSION_PLACEHOLDER em-dash:** the exact-match comparison string contains a single em-dash `—` (U+2014), matching Phase 2 D-21 (`'TBD — set via /map-tension'`). Verified: 1 U+2014 occurrence, no hyphen-minus substitution. The tension card is hidden when `block.live_tension === LIVE_TENSION_PLACEHOLDER`.
- **Glyphs:** source link uses the literal `↗` (`source ↗`); the show-all button uses the literal `↓` (`Show all (30 or more) ↓`) — both match the `style-map.css` / `tokens-preview.html` contract (the plan's `&uarr;`/`&darr;` were XML-document entities, not intended runtime output).
- **window stash contract for plan 04-05:** `window.currentBlock` (the blocks row), `window.currentTimelineEntries` (the rendered entry array), and module-level `timelineExpanded` (false on each `loadBlock` entry, true after expand) are all set — the idle poll reads `timelineExpanded` to choose `.limit(30)` vs unbounded and calls `renderTimelineEntries(...)` to repaint `#evolution-entries`.

## Decisions Made

- Hoisted `renderMaturityPill` to module scope and removed plan 04-02's nested copy (rationale above). This is the cleanest way to satisfy both "exists exactly once" and "renderBlock can call it"; it is also forward-compatible with plan 04-04's status pill.
- Used array-index destructuring of `Promise.all` (`var pair = await Promise.all([...]); blockRes = pair[0]; timelineRes = pair[1];`) instead of `var [a, b] = ...` — equivalent and parse-clean in the classic-script file, reads clearly with the subsequent error guards.
- Kept the show-all label as "Show all (N or more) ↓" at the cap (total unknown pre-expansion), matching D-11's stated intent.

## Deviations from Plan

None — plan executed exactly as written. The `renderMaturityPill` module-scope hoist + nested-copy removal is the planned mitigation the task action explicitly called for ("the EXECUTOR for whichever plan runs second checks if `function renderMaturityPill` already exists and skips the declaration... To minimize duplication, the executor should declare `function renderMaturityPill(b)` once at module top"). Since plan 04-02 had placed it nested rather than at module scope, hoisting was the correct realization of that instruction — within plan scope, not a deviation.

## Threat Model Acceptances

- **T-04-03-01 (XSS via markdown) — ACCEPTED with residual flag.** `body_md` flows through `marked.parse()` → `innerHTML` (the only escapeHtml bypass, same precedent as `renderArticle()` line 169 → 210). `marked` at its CDN defaults escapes `<script>` but permits inline HTML in markdown, so a future malicious synthesis prompt-injection could embed an inline event handler (e.g. `<img onerror>`). Phase 4 does NOT switch `marked` to a sanitizer — that is a Phase 7 (synthesis prompt) / Phase 8 (validator) concern. The compensating control is the operator-as-final-arbiter Phase 9 publish gate: no `body_md` reaches an anon reader without human approval, and RLS only exposes `status='published'` versions. Residual risk is accepted for v1.
- **T-04-03-02 (open redirect via source_url) — MITIGATED.** Timeline-source anchors carry `rel="noopener noreferrer" target="_blank"` (window opener severed, referrer not leaked). Scheme validation is the Phase 5 intake owner's job, not this renderer's.
- **T-04-03-03 (XSS via plain DB strings) — MITIGATED.** All seven non-body strings pass through `escapeHtml()` before string-concat, including `source_url` in the `data-source` attribute.

## Issues Encountered

- The plan's `<verify>` block included `node -e "new Function(...)"` which fails on the file's top-level `const` declarations under node v20 (the same edge case plan 04-02 documented). Used `node --check` instead — clean parse. No code change.
- The headless smoke test's first run failed because the fake `window.location` was not URL-stringifiable for `getInitialMode()`'s `new URL(window.location)` call (a harness setup issue, not a code defect); fixed the harness and confirmed all render behaviors. A second harness iteration was needed because top-level `const` (LIVE_TENSION_PLACEHOLDER) declared inside `eval()` is not visible to outer references — exposed it via `global.__T` and confirmed the hide logic. None of these reflect a code issue; the production module references its own module-scoped constants correctly.

## Verification Performed

- All plan grep checks pass: `loadBlock`, `renderBlock`, `renderTimelineEntries`, `expandTimeline`, `var timelineExpanded`, `Promise.all`, `from('blocks').select`, `from('timeline_entries').select`, `.order('event_date', { ascending: false }).limit(30)`, `from('block_body_versions').select`, `LIVE_TENSION_PLACEHOLDER`, `marked.parse(bodyMd)`, `rel="noopener noreferrer"`, `target="_blank"`, `class="timeline-show-all"`, `class="block-header"`, `class="block-tension"`, `class="block-body"`, `class="evolution"`, `function renderMaturityPill`.
- `renderMaturityPill` declared exactly once (count = 1). RLS-redundant filters: 2 `eq('status', 'published')` + 1 `neq('block_slug'` matches are ALL inside `//` comments documenting their deliberate absence (lines 442/443/465) — zero executable filters (same pattern plan 04-02 used).
- `escapeHtml` appears 6× inside `renderTimelineEntries` (≥3 required); `target="_blank"` present; show-all conditional `entries.length === 30 && !timelineExpanded` present; `window.currentBlock` / `window.currentTimelineEntries` assignments present in `loadBlock`.
- Only one backtick in the file (pre-existing regex char-class at line 167 in `renderList`, untouched) — no template literals introduced.
- `node --check docker/web/site/app.js` → clean parse.
- Headless smoke test confirmed: pill = 5 segs + correct data-stage; with-source entry has `data-source` + `noopener noreferrer` + `_blank`; null-source entry omits both `data-source` and `timeline-source`; empty entries → "No timeline entries yet."; placeholder tension HIDDEN; null body HIDDEN; Evolution ALWAYS present; header title escaped (`Id &amp; Trust`); real tension SHOWN; body SHOWN via marked.parse; show-all button "Show all (30 or more) ↓" appears at the 30-cap; LIVE_TENSION_PLACEHOLDER === `'TBD — set via /map-tension'` (U+2014).

## Known Stubs

None. `loadBlock`, `renderBlock`, `renderTimelineEntries`, and `expandTimeline` are fully implemented. The "No timeline entries yet." message and hidden tension/body sections are intentional D-10 empty-state behavior (the entire v1 state until Phase 5 intake + Phase 7/9 synthesis ship), not stubs.

## User Setup Required

None — no external service configuration. The renderer becomes operator-visible after the Wave 4 deploy (plan 04-06) rebuilds the `web` container. End-to-end browser verification (visit `#/map/identity-trust`, insert test timeline rows, exercise the 30-cap show-all) happens at that checkpoint per the plan's `<verification>` section.

## Next Phase Readiness

- Plan 04-04 (status) can call the now-module-scoped `renderMaturityPill` directly (do not re-declare) and mirror the `economy_map.blocks` read shape.
- Plan 04-05 (idle poll) has its full contract: `window.currentBlock`, `window.currentTimelineEntries`, `timelineExpanded`, and `renderTimelineEntries(entries, expanded)` are all in place; the poll re-queries `timeline_entries` only and repaints `#evolution-entries`.
- No blockers.

## Self-Check: PASSED

- Files verified present: `docker/web/site/app.js`, `.planning/phases/04-hub-block-and-status-renderer/04-03-SUMMARY.md`
- Commit verified in git: `67a8d2e`

---
*Phase: 04-hub-block-and-status-renderer*
*Completed: 2026-05-28*
