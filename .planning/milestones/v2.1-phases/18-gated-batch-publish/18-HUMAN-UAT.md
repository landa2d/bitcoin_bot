---
status: resolved
phase: 18-gated-batch-publish
source: [18-VERIFICATION.md]
started: 2026-06-09T11:00:00Z
updated: 2026-06-09T11:00:00Z
---

## Current Test

[resolved — operator accepted the existing surface]

## Tests

### 1. Block-detail-page subtitle element (ROADMAP SC-2 wording)
expected: EITHER (a) the block page at `#/map/<slug>` (e.g. https://aiagentspulse.com/#/map/identity-trust) renders the block subtitle as a visible element below the title — satisfying the SC-2 "subtitle" wording literally; OR (b) the operator confirms the existing v2.0 surface (back arrow + title + maturity pill + body, with the subtitle shown on the hub grid tile but not repeated on the deep-dive page) is the accepted "full reading surface" for this milestone. The subtitle IS rendered on the hub grid at `#/map` (`tile-subtitle`, app.js:592); `renderBlock` intentionally omits it on the detail page (pre-existing since Phase 13 commit ae6f4a3; the identical surface was operator-approved in the Phase-17 preview click-through). Phase 18 published content into this renderer and did not change the block surface.
result: PASSED (Outcome B) — operator accepted the existing v2.0 block-detail surface (title + maturity pill + body; subtitle on the hub grid tiles) as the "full reading surface" for the v2.1 milestone (2026-06-09). No renderer change; the SC-2 "subtitle" wording is satisfied by the hub-tile subtitle.

## Summary

total: 1
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

None — the single item was resolved by operator acceptance (Outcome B). The literal "subtitle on the block detail page" is deferred as a possible future renderer enhancement, NOT a v2.1 gap.
