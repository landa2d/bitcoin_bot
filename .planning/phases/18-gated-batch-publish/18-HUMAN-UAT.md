---
status: partial
phase: 18-gated-batch-publish
source: [18-VERIFICATION.md]
started: 2026-06-09T11:00:00Z
updated: 2026-06-09T11:00:00Z
---

## Current Test

[awaiting human confirmation]

## Tests

### 1. Block-detail-page subtitle element (ROADMAP SC-2 wording)
expected: EITHER (a) the block page at `#/map/<slug>` (e.g. https://aiagentspulse.com/#/map/identity-trust) renders the block subtitle as a visible element below the title — satisfying the SC-2 "subtitle" wording literally; OR (b) the operator confirms the existing v2.0 surface (back arrow + title + maturity pill + body, with the subtitle shown on the hub grid tile but not repeated on the deep-dive page) is the accepted "full reading surface" for this milestone. The subtitle IS rendered on the hub grid at `#/map` (`tile-subtitle`, app.js:592); `renderBlock` intentionally omits it on the detail page (pre-existing since Phase 13 commit ae6f4a3; the identical surface was operator-approved in the Phase-17 preview click-through). Phase 18 published content into this renderer and did not change the block surface.
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
