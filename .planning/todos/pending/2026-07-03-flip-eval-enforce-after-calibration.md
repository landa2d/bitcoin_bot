---
created: 2026-07-03T08:20:00Z
updated: 2026-07-03T08:20:00Z
title: Flip edition_eval enforce=true after ~2-edition report-only calibration window (30-04 Task 6)
area: newsletter/config
priority: P1
phase_candidate: false
files:
  - config/agentpulse-config.json
---

## Action

The v2.3 pre-publish eval has been LIVE in report-only mode since 2026-07-02
(`edition_eval.enabled=true`, `enforce=false`). The remaining activation step — deliberately
operator-owned (Phase 30 plan 30-04 Task 6) — is:

1. Observe ~2 editions' verdicts in `edition_evals` (now legible without SQL via the Friday
   notify eval section and the `/newsletter_eval` + `/newsletter_eval trend` Telegram commands,
   Phase 31). Watch for `⚠ WOULD HAVE HELD (report-only)` tags: confirm they flag real problems,
   not false positives.
2. When calibrated, set `edition_eval.enforce=true` in `config/agentpulse-config.json`.
   Config is read per-call via the live ro `../config` mount — NO rebuild needed.
3. Rollback if needed: `enforce=false` (or `enabled=false` to disarm entirely).

## Why a todo

Milestone v2.3 closes with this pending — the calibration window needs real Friday editions,
which arrive after the archive. This todo keeps the flip from getting lost. The newsletter
container has deliberately NOT been rebuilt since the window opened (Phase 31 D-14); scoped
rebuilds of other services are fine, but avoid rebuilding `newsletter` until enforce is flipped
unless a change requires it.
