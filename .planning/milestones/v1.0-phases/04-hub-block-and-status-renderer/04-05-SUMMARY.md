---
phase: 04-hub-block-and-status-renderer
plan: 05
subsystem: ui
tags: [frontend, spa, lifecycle, polling, evolution, timeline, supabase, economy-map]

# Dependency graph
requires:
  - phase: 04-hub-block-and-status-renderer
    plan: 01
    provides: "SPA shell — #block-view, .evolution / .timeline-show-all CSS, loadBlock() stub, hash router branches"
  - phase: 04-hub-block-and-status-renderer
    plan: 03
    provides: "loadBlock(slug) success path (renderBlock + scrollTo), module-level timelineExpanded flag, renderTimelineEntries(entries, expanded), window.currentBlock / window.currentTimelineEntries stash, #evolution-entries container, expandTimeline() one-shot"
  - phase: 02-economy-map-schema-seven-block-seed
    provides: "economy_map.timeline_entries schema, RLS anon-read (block_slug != 'unsorted')"
provides:
  - "startEvolutionPoll(slug) — starts a fresh visibility-aware 60s setInterval after defensively clearing any prior handle; wired at the tail of loadBlock()'s success path"
  - "stopEvolutionPoll() — idempotent clearInterval + null-reset of the module handle"
  - "pollEvolution(slug) — async work fn: visibility guard + #/map/<slug> hash race re-check, re-queries ONLY economy_map.timeline_entries (limit 30 when collapsed, unbounded when expanded per D-11), wholesale-replaces #evolution-entries innerHTML via renderTimelineEntries, syncs the Show-all button"
  - "evolutionPollHandle — module-level setInterval handle (null when no poll active)"
  - "second hashchange listener (sibling to route) — stops the poll on any navigation away from #/map/"
  - "visibilitychange listener — optional immediate catch-up refresh on tab re-focus"
affects: [04-06-deploy]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "First setInterval / clearInterval lifecycle in app.js (no prior analog — PATTERNS §'No analog found' first-in-file precedent)"
    - "First document.visibilityState guard in app.js — short-circuits the work fn while the tab is backgrounded (D-07)"
    - "Two sibling hashchange listeners (routing + poll-cleanup) — idle-poll cleanup kept separate from main routing per PATTERNS §'#8 Init'"
    - "Wholesale innerHTML replacement on re-query (no DOM diffing) — matches renderArticle/renderList idiom, the PATTERNS §'No analog found' mitigation for list re-render"
    - "Captured-slug race guard: pollEvolution re-checks window.location.hash.startsWith('#/map/' + slug) before doing work, so an in-flight tick from a prior block short-circuits"

key-files:
  created:
    - .planning/phases/04-hub-block-and-status-renderer/04-05-SUMMARY.md
  modified:
    - docker/web/site/app.js

key-decisions:
  - "Included the optional visibilitychange immediate-refresh listener (D-07 RECOMMENDATION). Cost is ~10 lines; it eliminates the 'I just came back to the tab, where is my new entry' lag without changing the 60s cadence floor. Guarded on visible + evolutionPollHandle !== null + window.currentBlock + #/map/ prefix so it only fires when a block-page poll is genuinely active."
  - "pollEvolution Show-all button handling is THREE-WAY (not append-only): when collapsed AND result hit the 30-cap AND no button exists → append one (createElement + onclick=expandTimeline); when expanded AND a leftover button exists → remove it; otherwise no-op. This keeps the button in sync if the entry count crosses the 30-cap boundary between ticks, and mirrors expandTimeline()'s one-shot button removal."
  - "Used 'Interval handle for...' (not 'setInterval handle for...') in the Addition-1 comment so the file contains exactly ONE line matching the literal substring 'setInterval' — the actual call. The plan's recommended comment text contained the word 'setInterval', which would have tripped the plan's own `grep -c setInterval == 1` acceptance check (the check counts lines, and the criterion's true intent is 'exactly one setInterval CALL')."
  - "Removed two backtick characters from new comments (inline-code-style emphasis around 'slug'). The plan's verify uses `! grep -q '`'` which fails on ANY backtick; rewording to plain prose keeps the file at exactly ONE backtick (the pre-existing regex char-class in renderList, documented by plan 04-03), introducing zero new backticks."
  - "Used `node --check` for the parse gate instead of the plan's `node -e \"new Function(...)\"` — plan 04-03's SUMMARY documented that new Function() throws on the file's top-level `const` declarations under node v20. node --check parses the file in module/script context correctly. Same realization plan 04-02 and 04-03 made; not a code change."

patterns-established:
  - "Idle-poll lifecycle (start/stop/poll + visibility + hashchange) is now the in-file precedent for any future block-page background refresh"

requirements-completed: [RNDR-06]

# Metrics
duration: 5min
completed: 2026-05-28
---

# Phase 4 Plan 05: Idle Poll Lifecycle Summary

**The Evolution section on block pages is now live data: `loadBlock(slug)` starts a visibility-aware 60-second idle poll that re-queries ONLY `economy_map.timeline_entries`, repaints `#evolution-entries` wholesale via the plan 04-03 `renderTimelineEntries`, respects the `timelineExpanded` show-all state, and tears itself down on navigation away — so a new timeline insert appears within ~60s without the operator leaving and returning (RNDR-06), with zero Realtime (D-05) and zero cost while the tab is backgrounded (D-07).**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-28
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added module-level `var evolutionPollHandle = null;` directly after the plan 04-03 `var timelineExpanded = false;` — the single setInterval handle (D-05/D-06/D-07).
- Added three top-level functions (declared before `function route()`, alongside the other map functions): `stopEvolutionPoll()` (idempotent clearInterval + null-reset), `async function pollEvolution(slug)`, and `function startEvolutionPoll(slug)` (defensive `stopEvolutionPoll()` then a 60000ms `setInterval` whose non-async callback fire-and-forgets `pollEvolution`).
- `pollEvolution(slug)` carries two guards before any work: `document.visibilityState !== 'visible'` (D-07 backgrounded-tab short-circuit) and `!window.location.hash.startsWith('#/map/' + slug)` (race re-check — an in-flight tick from a block the operator just left short-circuits). It then re-queries ONLY `sb.schema('economy_map').from('timeline_entries')` — never `blocks`, never `block_body_versions` (D-06) — chaining `.limit(30)` only when `!timelineExpanded` (D-11), stashes `window.currentTimelineEntries`, and wholesale-replaces `#evolution-entries` innerHTML via `renderTimelineEntries(data, timelineExpanded)`.
- Wired `startEvolutionPoll(slug);` as the final line of `loadBlock()`'s success path (after `renderBlock(...)` + `window.scrollTo(0, 0)`). The block-not-found error branch returns before this line, so the poll only starts on success.
- Added a SECOND `hashchange` listener (sibling to the existing `window.addEventListener('hashchange', route)`, not merged into it) that calls `stopEvolutionPoll()` whenever the new hash does NOT start with `'#/map/'`.
- Added the optional `visibilitychange` listener (D-07 recommendation) that fires an immediate `pollEvolution(window.currentBlock.slug)` catch-up when the tab returns to visible AND a poll is active AND the hash is still under `#/map/`.

## pollEvolution Show-all button handling (final structure)

Three-way, not append-only:
1. **Collapsed + cap hit + no button present** → create a fresh `<button class="timeline-show-all" onclick="expandTimeline()">Show all (N or more) ↓</button>` and append it to `.evolution`. This handles the case where the entry count crossed the 30 boundary between ticks (a block that had < 30 entries now has exactly 30 → the button must appear).
2. **Expanded + leftover button present** → `btn.remove()` (mirrors `expandTimeline()`'s one-shot removal).
3. **Otherwise** → no-op (button already correct, or collapsed with < 30 entries so no button wanted).

The button markup, glyph (`↓`), and `onclick="expandTimeline()"` exactly match the plan 04-03 `renderBlock` emission so a poll-created button is indistinguishable from a render-created one.

## Race conditions identified during implementation

- **Primary (T-04-05-04): poll tick fires after navigation to a different block but before the old handle was cleared.** Mitigated by the `if (!window.location.hash.startsWith('#/map/' + slug)) return;` re-check at the top of `pollEvolution` — the captured `slug` is compared against the live hash, so a stale in-flight tick from the prior block short-circuits and writes nothing. `startEvolutionPoll`'s defensive `stopEvolutionPoll()` closes the window further (the new block's loader clears the old interval before registering the new one). Verified in the headless smoke test (hash-mismatch tick skips the render).
- **Secondary: navigate away to the hub between a tick firing and the work fn running.** Same `#/map/<slug>` prefix re-check covers it — the hub hash `#/map` does not start with `#/map/identity-trust`, so the work short-circuits. The sibling hashchange listener also calls `stopEvolutionPoll()` on the hub navigation, so the interval stops entirely.

## Task Commits

1. **Task 1: Add the idle poll lifecycle to app.js and wire it from loadBlock** — `5bb1dd2` (feat)

## Files Created/Modified

- `docker/web/site/app.js` — +96 lines: `var evolutionPollHandle = null;` (module state); `stopEvolutionPoll` / `pollEvolution` / `startEvolutionPoll` (before `route()`); `startEvolutionPoll(slug);` appended to `loadBlock`'s success path; one new `hashchange` poll-cleanup listener + one `visibilitychange` listener appended after the existing routing listener.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking verification-grep collision] Reworded the Addition-1 comment to avoid a false `setInterval` count.**
- **Found during:** Task 1 verification.
- **Issue:** The plan's Addition-1 recommended comment text contained the word "setInterval" (`// setInterval handle for the block-page Evolution refresh`). The plan's own acceptance grep is `grep -c "setInterval" == 1` (counting lines), but the criterion's stated intent is "exactly one setInterval CALL across the whole file". The recommended comment + the real call = 2 matched lines → the literal grep failed even though there is exactly one call.
- **Fix:** Changed the comment to "Interval handle for the block-page Evolution refresh poll". The file now has exactly one line matching `setInterval` (the call at the `setInterval(function() {...}, 60000)` site). Verified `grep -c setInterval == 1`.
- **Files modified:** docker/web/site/app.js
- **Commit:** 5bb1dd2

**2. [Rule 3 - Blocking verification-grep collision] Removed two backtick characters from new comments.**
- **Found during:** Task 1 verification.
- **Issue:** I initially wrote two comments using inline-code-style backticks around "slug" (e.g. "...for `slug` and..."). The plan's verify includes `! grep -q '`'` which fails on ANY backtick anywhere in the file. The file already legitimately contains one backtick (a regex char-class `/[#*_\[\]`>]/` in the pre-existing `renderList`, documented by plan 04-03 — not a template literal). My two new backticks would have pushed the count to 3 and tripped the check.
- **Fix:** Reworded both comments to plain prose ("for the given slug"). The file is back to exactly one backtick (the pre-existing regex char-class). Zero template literals introduced. Verified `grep -c '`' == 1`.
- **Files modified:** docker/web/site/app.js
- **Commit:** 5bb1dd2

> Note: both deviations are comment-text adjustments to satisfy the plan's literal grep gates while preserving the acceptance criteria's true intent ("exactly one setInterval CALL", "zero template literals"). No behavioral code change. The `node --check` parse gate substitution (vs the plan's `new Function`) is the same harness realization plans 04-02 and 04-03 documented — within scope, not a deviation.

## Threat Model Acceptances / Mitigations

- **T-04-05-01 (operator-side DoS — runaway poll) — MITIGATED.** 60s cadence floor; `document.visibilityState !== 'visible'` skips the query while backgrounded; the sibling hashchange listener calls `stopEvolutionPoll()` on navigation away from any `#/map/<slug>`; `startEvolutionPoll` defensively clears any prior handle so a double-`loadBlock` cannot leak two intervals.
- **T-04-05-02 (DB-side DoS — many tabs) — ACCEPTED.** 60s × 7 blocks × N tabs is well under PostgREST capacity; RLS-bounded reads are cheap.
- **T-04-05-03 (XSS via wholesale innerHTML re-emit) — MITIGATED.** The poll re-invokes the SAME `renderTimelineEntries` from plan 04-03 — every DB string `escapeHtml`'d, source anchors carry `rel="noopener noreferrer" target="_blank"`. Only the trigger changed; the markup-emission contract is unchanged.
- **T-04-05-04 (race: stale tick after navigation) — MITIGATED.** `#/map/<slug>` prefix re-check inside `pollEvolution` + defensive `stopEvolutionPoll()` in `startEvolutionPoll` (detailed above).

## Verification Performed

- All plan grep checks pass: `var evolutionPollHandle`, `function startEvolutionPoll`, `function stopEvolutionPoll`, `async function pollEvolution`, exactly 1 `setInterval`, `60000`, ≥1 `clearInterval`, `document.visibilityState`, exactly 2 `hashchange` listeners, `evolution-entries`, `startEvolutionPoll(slug)`, zero `sb.channel(`, exactly 1 backtick (pre-existing, zero new), clean `node --check` parse.
- Acceptance-criteria greps: the three functions are top-level declarations (column 0, no nesting); `pollEvolution`'s body queries ONLY `from('timeline_entries')` and contains NO `from('blocks')`/`from('block_body_versions')`; `pollEvolution` contains the `if (!timelineExpanded) query = query.limit(30)` D-11 check; the new hashchange listener calls `stopEvolutionPoll()` on non-`#/map/` hashes; `startEvolutionPoll(slug)` sits after the block-not-found `return;` in `loadBlock`.
- Headless smoke test (eval with faked DOM + supabase query builder, mirroring plan 04-03's harness): interval registered exactly once at 60000ms; collapsed poll renders 30 entries (limit honored); Show-all button appended when the 30-cap is hit and no button exists; hidden-tab visibility guard skips the render; hash-mismatch race guard skips the render; `stopEvolutionPoll()` calls `clearInterval`.

## Known Stubs

None. `startEvolutionPoll`, `stopEvolutionPoll`, and `pollEvolution` are fully implemented and wired into `loadBlock`. The behavioral browser verification (DevTools Network observation of the 60s tick, SQL-insert visibility, tab-switch pause, hub-navigation stop, block-to-block handoff) happens at the Wave 4 deploy checkpoint (plan 04-06) per the plan's `<verification>` section — this is post-deploy manual verification, not a stub.

## Threat Flags

None — this plan introduces no new network endpoint, auth path, file access, or schema change. It re-uses the existing plan 04-03 `timeline_entries` read shape against the same anon client under the same RLS posture.

## Next Phase Readiness

- Plan 04-06 (deploy) can rebuild the `web` container; the idle poll is the last code addition for the Evolution live-data half of RNDR-06. The publish-path half is satisfied by D-05's next-navigation baseline (a newly published body shows on next nav).
- No blockers.

## Self-Check: PASSED

- Files verified present: `docker/web/site/app.js`, `.planning/phases/04-hub-block-and-status-renderer/04-05-SUMMARY.md`
- Commit verified in git: `5bb1dd2`

---
*Phase: 04-hub-block-and-status-renderer*
*Completed: 2026-05-28*
