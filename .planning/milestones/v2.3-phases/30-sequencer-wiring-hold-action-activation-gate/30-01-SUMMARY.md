---
phase: 30-sequencer-wiring-hold-action-activation-gate
plan: 01
subsystem: newsletter-eval / publish-gate
tags: [migration, do_not_publish, publish-gate, processor, schema, defense-in-depth]
requires:
  - migration 045 (edition_evals) — sibling persistence surface (prior phase)
provides:
  - "newsletters.do_not_publish + do_not_publish_reason first-class columns (authored, migration 046)"
  - "processor publish-gate structural hold guard on the do_not_publish column (both gates)"
affects:
  - "docker/processor/agentpulse_processor.py (publish_newsletter, scheduled_auto_publish_newsletter)"
  - "the hold-action write target for the poller verdict step (Plan 30-03)"
tech-stack:
  added: []
  patterns:
    - "ADD COLUMN IF NOT EXISTS + COMMENT ON COLUMN (migration-020 house style)"
    - "SQL-first / MCP-apply / no-worktree operator banner (migration-045 house style)"
    - "in-Python .get('do_not_publish', False) apply-order-robust column guard"
key-files:
  created:
    - supabase/migrations/046_do_not_publish_columns.sql
  modified:
    - docker/processor/agentpulse_processor.py
decisions:
  - "Migration 046 authored, NOT applied — apply is the operator-owned 30-04 MCP runbook"
  - "Schema-only, no data-migration backfill — DEFAULT false covers new rows; historical always-held A/B rows stay as-is (D-13)"
  - "Publish-gate guard reads the column in-Python (.get default False) so it is robust to migration-046 apply ordering"
  - "Log only edition number + a fixed label on a held row, never the raw do_not_publish_reason prose (T-30-LOG)"
metrics:
  duration: ~8min
  tasks: 2
  files: 2
  completed: 2026-07-01
---

# Phase 30 Plan 01: Sequencer Wiring — do_not_publish Column & Publish-Gate Guard Summary

Authored migration 046 (first-class `do_not_publish` + `do_not_publish_reason` columns on `newsletters`) and hardened BOTH Processor publish gates to refuse a held row by reading that column — structural defense-in-depth behind the existing `status='held'` exclusion, with zero eval logic added to the Processor (it stays a dumb sequencer).

## What Was Built

### Task 1 — Migration 046 (`supabase/migrations/046_do_not_publish_columns.sql`)
- Single `ALTER TABLE newsletters` adding two re-apply-safe columns:
  - `ADD COLUMN IF NOT EXISTS do_not_publish boolean NOT NULL DEFAULT false`
  - `ADD COLUMN IF NOT EXISTS do_not_publish_reason text`
- `COMMENT ON COLUMN` for both (the do_not_publish flag = the hard-hold the publish gate honors; the reason = the human-readable hold cause).
- Copied the migration-020 `ADD COLUMN IF NOT EXISTS` house style and the migration-045 SQL-FIRST / MCP-apply / do-NOT-`supabase db push` / do-NOT-apply-from-worktree operator banner (project ref `zxzaaqfowtqvmsbitqpu`).
- Schema-only: no `INSERT`/`UPDATE`/`DELETE`. Backfill deliberately omitted (D-13) — `DEFAULT false` covers every new row and the historical always-`held` A/B shadow rows are already status-excluded, so touching historical rows is unnecessary risk.
- Gives hold state exactly ONE canonical, queryable home (today `do_not_publish` lives only inside `data_snapshot` JSONB on the block_v1 A/B rows).
- **AUTHORED, NOT APPLIED** — the live MCP apply is the operator-owned Plan 30-04 activation runbook.

### Task 2 — Processor publish-gate guards (`docker/processor/agentpulse_processor.py`)
- `publish_newsletter` (~L5877): immediately after `newsletter = draft.data[0]`, an `if newsletter.get('do_not_publish'):` guard logs a WARNING (edition number + fixed label only) and `return {'error': 'held: do_not_publish set'}` WITHOUT sending Telegram/email or flipping status.
- `scheduled_auto_publish_newsletter` (~L10647): widened the narrow `select('id, edition_number, created_at')` to `select('*')` (ordering-agnostic — avoids naming a column that may not exist pre-046-apply) and added the same guard, returning early before calling `publish_newsletter()`.
- Reads the column via in-Python `.get('do_not_publish', False)` so an absent column (pre-046-apply) defaults False → publishes as before; a present-and-true column → held. Robust to migration apply ordering.
- The existing `.in_('status', [...])` filters and the `<1h` freshness guard are unchanged — the guard is purely additive belt-and-suspenders (a mis-statused-but-held row still cannot ship, D-01/WIRE-04).
- No eval/LLM/retry logic added: the Processor eval-ref count stays 0 (WIRE-05). It only reads the column and owns the publish gate.

## Verification Evidence

| Check | Result |
|-------|--------|
| Task 1 automated gate (file + both columns + banner) | GATE-PASS |
| `ADD COLUMN IF NOT EXISTS` count (non-comment) | 2 |
| `COMMENT ON COLUMN` count | 2 |
| DML statements (non-comment) | 0 |
| Task 2 automated gate (AST parse + guard count 2 + eval-ref 0) | GATE-PASS |
| `grep -c "get('do_not_publish'"` in processor | 2 |
| Processor eval-ref count (`run_layer2\|run_deterministic_gate\|run_edition_eval\|import edition_eval\|import judge_loop`) | 0 |
| `.in_('status', [...])` publish-gate filters | unchanged |
| AST parse of processor | exits 0 |

## Deviations from Plan

None — plan executed exactly as written. No auto-fixes, no architectural changes, no auth gates.

## Requirement Status (deferred to phase-end verify)

WIRE-02 / WIRE-04 / WIRE-05 remain **Pending** — consistent with the phase's established fail-loud-accuracy posture (Phases 27/28/29). This plan authors the column and installs the publish-gate defense-in-depth, but:
- WIRE-02's live column depends on the operator MCP apply of migration 046 (Plan 30-04), not this plan.
- WIRE-04's `pass`-does-not-auto-publish + the hold ACTION that WRITES `do_not_publish` live in the `newsletter_poller` sequencer (Plans 30-02/03), not this plan.
- WIRE-05 is a keep-it-0 invariant realized/preserved here (eval-ref count 0), but its full "poller calls both layers" clause is Plans 30-02/03.

Closure reconciled at phase-end `/gsd-verify-work`.

## Notes for Downstream Plans

- The status-flip / hold-action UPDATE target for the poller verdict step (Plan 30-03) is now `newsletters.do_not_publish` + `do_not_publish_reason` (the columns authored here). Reconcile the block_v1 A/B row's JSONB `data_snapshot.do_not_publish` to the new top-level column (D-02) in that plan.
- Migration 046 must be MCP-applied (Plan 30-04) before the column-read guards see a real value live; until then the `.get` default False keeps publish behavior unchanged (rollback-safe).

## Self-Check: PASSED

- FOUND: `supabase/migrations/046_do_not_publish_columns.sql`
- FOUND: `docker/processor/agentpulse_processor.py`
- FOUND: commit `01d073b` (Task 1 — migration 046)
- FOUND: commit `a41b74a` (Task 2 — processor publish-gate guards)
- TASK1 GATE-PASS + TASK2 GATE-PASS re-confirmed against live code
