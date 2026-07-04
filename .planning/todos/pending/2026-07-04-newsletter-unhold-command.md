---
created: 2026-07-04T09:00:00Z
updated: 2026-07-04T09:00:00Z
title: /newsletter_unhold operator command — release a held edition (PRE-ENFORCE BLOCKER)
area: gato_brain/processor
priority: P1
phase_candidate: true
files:
  - docker/gato_brain/gato_brain.py
  - docker/gato/inject-gato-brain.mjs
  - docker/processor/agentpulse_processor.py
---

## Problem

There is NO operator path to release a held edition. Both publish paths refuse a
`do_not_publish` row (`agentpulse_processor.py:5886` manual, `:10944` auto-publish) and no
Telegram command clears the flag — releasing a wrongly-held edition today means editing the
database by hand.

**Why this blocks `enforce=true`:** under enforcement, a false-positive fabrication hold
silences the newsletter with no operator escape hatch — the exact "silence" failure mode the
project's core value names. Must ship BEFORE the enforce flip (see
`2026-07-03-flip-eval-enforce-after-calibration.md`).

## Shape

- Owner-gated `/newsletter_unhold <edition#>` in gato_brain (direct dispatch before the intent
  router, mirroring `/newsletter_eval` — D-12 owner-gate BEFORE any read/write).
- Clears `do_not_publish` + restores `status='draft'` on the targeted row; logs a fixed label
  with edition number only (T-30-LOG); confirms to the operator with what the eval had flagged
  (so the release is an informed decision).
- MUST be added to `isGatoBrainCommand` in `inject-gato-brain.mjs` + gato rebuild (the Phase 9
  dead-command landmine).
- Consider requiring a confirm token (e.g. `/newsletter_unhold 104 confirm`) since this
  overrides a fabrication verdict.
