---
created: 2026-05-28T11:54:47Z
updated: 2026-05-28T11:54:47Z
title: analyst expire_stale_predictions references non-existent predictions.title column
area: analyst
priority: P2
phase_candidate: false
files:
  - docker/analyst/analyst_poller.py
---

## Problem

analyst logs `ERROR: Failed to expire overdue predictions: column predictions.title does not
exist (42703)` on its poll loop (`expire_stale_predictions()`, analyst_poller.py:1119-1173,
specifically the overdue-expire query near :1150).

## Triage (confirmed) — writes are fine; only housekeeping is broken

- The `predictions` table has **no `title` column** (columns are `prediction`, `prediction_text`,
  `confidence`, `status`, `target_date`, …). The expire-overdue query selects/filters on a
  `title` that doesn't exist.
- **Predictions ARE being written** — 30 rows, last write 2026-05-28 11:53 (minutes ago,
  post-cutover). The write path is unaffected.
- The error is caught + logged (non-fatal). Only effect: **overdue predictions don't auto-expire**
  (they stay open past `target_date`). Data-hygiene bug, not a write failure.

## Fix direction

Fix the overdue/stale-expire query in `expire_stale_predictions()` to use the real column
(likely `prediction_text` or drop the `title` reference entirely; confirm against the live
schema). Low severity — no data loss, just stale open predictions.
