---
status: partial
phase: 04-hub-block-and-status-renderer
source: [04-VERIFICATION.md]
started: 2026-05-28T08:19:00Z
updated: 2026-05-28T08:19:00Z
---

## Current Test

[awaiting human testing — both items are forward-looking, see notes]

## Tests

### 1. RNDR-02 six-part skeleton renders once body_md is populated
expected: When Phase 7 delivers a published body version, the six named sections — (1) What it is, (2) Why it's hard, (3) Live tension, (4) Where it stands today, (5) Evolution, (6) Maturity indicator — are all visible on a block page.
result: [pending — blocked on Phase 7 synthesis; all 7 blocks currently have current_body_version_id = null, so .block-body is correctly hidden]

### 2. CR-01 (source_url XSS vector) tracked for remediation
expected: A follow-up task exists to add safeHttpUrl() scheme validation before href/data-source emit in renderTimelineEntries(). Until then, no javascript:/data: URLs should reach timeline_entries.source_url.
result: RESOLVED — fixed in commit 2e20612 (safeHttpUrl() http(s) allowlist gates href + data-source), re-reviewed clean (04-REVIEW.md critical: 0), redeployed to prod. Todo moved to .planning/todos/completed/.

## Summary

total: 2
passed: 1
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
