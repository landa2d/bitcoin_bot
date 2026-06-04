---
status: partial
phase: 09-gated-publishing-approval-commands
source: [09-VERIFICATION.md]
started: 2026-06-03
updated: 2026-06-03
---

## Current Test

gato_brain rebuilt 2026-06-03 (image current, healthy) — commands are LIVE; run the 3 checks below over Telegram.

## Tests

### 1. Non-owner refusal over live Telegram
expected: A non-owner Telegram account running `/map-approve <uuid>` or `/map-reject <uuid>` receives the owner-only refusal and NO publish/reject occurs (the RPC is never called). The verified owner running the same command proceeds.
result: [pending]

### 2. Live /map-approve round-trip (watermark correctness)
expected: Owner runs `/map-approve <draft_version_id>`; the bot replies with the maturity `<old>→<new>` transition and the `https://aiagentspulse.com/#/map/<slug>` URL. Querying the DB afterward shows the row flipped to `published`, the prior published row `superseded`, `blocks.current_body_version_id`/`maturity` repointed, and `blocks.last_synthesized_at` set to the approved draft's `synthesized_from_through` (NOT the approval wall-clock). Block page re-renders within ~60s.
result: PASS (2026-06-03) — owner approved draft c998aee6 (governance-accountability) over live Telegram; bot confirmed publish + live URL. DB verified: version status=published, blocks.current_body_version_id repointed to the approved version, maturity nascent. **D-01 watermark proof:** approved at 14:25:44 but blocks.last_synthesized_at set to 10:48:59.701818 (the draft's synthesized_from_through) — a 3.6h gap, proving the watermark uses synthesized_from_through NOT NOW() (migrations 038+039 live). GATE-02 + CMD-03 + SC2 confirmed live. (No prior published row to supersede — cold-start block.)

### 3. Live /map-reject round-trip (entries unabsorbed)
expected: Owner runs `/map-reject <draft_version_id>`; the bot confirms the draft is superseded and its timeline entries return to the next synthesis. DB shows the row `status='superseded'` (never deleted), no `blocks.*` mutation, and the next synthesis cycle re-reads the previously-consumed entries.
result: PASS (2026-06-03) — owner rejected draft cd185b83 (governance-accountability) over live Telegram; bot confirmed "superseded; entries return". DB verified: row status=superseded (not deleted), blocks.current_body_version_id/maturity/last_synthesized_at all unchanged, 6 entries still unabsorbed, 0 open drafts. GATE-03 + GATE-04 + CMD-04 confirmed live.

## Summary

total: 3
passed: 2
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps

(none — these are live E2E confirmations, not implementation gaps. All 5 success criteria are verified in code + the live DB. Blocked only on the gato_brain deploy.)
