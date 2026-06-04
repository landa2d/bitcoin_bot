---
status: partial
phase: 10-operator-write-commands
source: [10-VERIFICATION.md]
started: 2026-06-03T00:00:00Z
updated: 2026-06-03T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. /map-assign moves an unsorted entry off the backlog
expected: Owner runs `/map-assign <entry_id> <block_slug>` → confirmation returned; the assigned entry no longer appears in `/map-pending` (filtered by `reassigned_to_entry_id IS NULL`).
result: [pending]

### 2. /map-entry append-only entry + delimiter parsing
expected: `/map-entry <slug> <what_shifted> | <why_it_mattered>` with both halves → "✅ Added a manual timeline entry". Without the ` | ` delimiter or an empty second half → usage hint showing the correct format.
result: [pending]

### 3. /map-synth forced synthesis + open-draft refusal
expected: First `/map-synth <slug>` → "Queued — draft appears within ~30s". A draft row appears within the 30s drain interval. A second `/map-synth <slug>` while that draft is still open → refused with the "already has a pending draft — approve or reject it first via /map-pending" message (open-draft invariant never bypassed).
result: [pending]

### 4. /map-tension updates live_tension and renders
expected: `/map-tension <slug> <text>` → "✅ Updated live tension"; the new `live_tension` text appears on the next render of the block page (~60s).
result: [pending]

### 5. Owner gate on all four commands
expected: Running any of `/map-assign`, `/map-entry`, `/map-synth`, `/map-tension` from a non-owner account → owner-only refusal, with NO DB side-effect (the gate is the first statement in each handler).
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
