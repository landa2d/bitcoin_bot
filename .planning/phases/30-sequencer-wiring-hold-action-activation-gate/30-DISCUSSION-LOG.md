# Phase 30: Sequencer Wiring, Hold Action & Activation Gate - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-01
**Phase:** 30-sequencer-wiring-hold-action-activation-gate
**Areas discussed:** do_not_publish storage, Wire-vs-activate boundary, Eval-error & report-only alerts, Which draft the hold gates

---

## do_not_publish storage (WIRE-02)

| Option | Description | Selected |
|--------|-------------|----------|
| New columns (migration 046) | Add `do_not_publish boolean` + `do_not_publish_reason text` as first-class columns on `newsletters` via a new migration; publish gate reads the column. Queryable, structural, operator-applied migration. | ✓ |
| JSONB in data_snapshot | Keep the flag nested in `data_snapshot` JSONB (as the A/B shadow row does today); no migration, non-first-class. | |

**User's choice:** New columns (migration 046) — **enriched:** `do_not_publish boolean NOT NULL DEFAULT false` + `do_not_publish_reason text`; publish gate reads the column directly; **AND reconcile the existing A/B shadow-row `data_snapshot.do_not_publish` JSONB flag so hold state has exactly ONE canonical home, not two.**
**Notes:** The reconciliation is a hard requirement — no parallel truth. Captured as D-01 + D-02.

---

## Wire-vs-activate boundary (WIRE-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Wire-only, arm separately | Phase 30 = worktree-safe wiring shipped `enabled=false`; live arming (27-03 key-mint + MCP-apply 045/046 + flip enabled) is a separate operator-owned runbook step. | ✓ |
| Include activation in Phase 30 | Phase 30 also performs 27-03 + MCP-applies migrations + flips to report-only as its own completion. | |

**User's choice:** Wire-only, arm separately.
**Notes:** Matches the 27/28/29 build-then-activate posture; keeps the worktree-unsafe migration/key steps operator-owned. Captured as D-03 + D-04 (with the full activation runbook).

---

## Eval-error & report-only alerts (WIRE-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-open + alert operator | Eval error → error row + draft proceeds to normal human gate (never blocks generation), BUT Gato-notify the operator that the eval didn't run; report-only "would-have-held" verdicts ARE surfaced to Gato. | ✓ |
| Fail-open, silent | Eval error → error row + proceed, no operator ping; report-only verdicts only written to `edition_evals`. | |
| Hold on eval error | Treat an eval error as a soft hold pending operator review. | |

**User's choice:** Fail-open + alert operator.
**Notes:** "An error is not evidence" (never blocks generation) balanced with fail-loud on the *outage*. Captured as D-06 + D-07 + D-12.

---

## Which draft the hold gates

| Option | Description | Selected |
|--------|-------------|----------|
| Primary draft; block_v1 telemetry | Hold-action targets the single-pass/primary publish draft; block_v1 A/B eval is telemetry-only (recorded, never flips publish state). | ✓ |
| Gate both drafts | Apply hold-action to both the primary draft and the always-held block_v1 shadow row. | |

**User's choice:** Primary draft; block_v1 telemetry.
**Notes:** Both save points are still evaluated (for A/B trend telemetry); only the primary draft's verdict flips publish state. Captured as D-13 + D-14.

## Claude's Discretion

- Exact Gato alert copy/format and any dedup/rate-limiting (hardened `send_telegram` is Phase 31 SURF).
- Whether migration 046 backfills historical rows beyond `DEFAULT false`.
- Precise placement of the invocation calls inside `process_task` / `save_newsletter` and how the primary `newsletter_id` threads to the status flip.

## Deferred Ideas

- Phase 31 (SURF): hardened `send_telegram`, Friday-notify per-draft eval summary, live `/newsletter_eval` Gato command, escalation-alert copy/dedup.
- v2.3-future: `edition_revisions` edit trail (REV-01), quantitative A/B trend (AB-01), threshold auto-tuning (TUNE-01), eval-trend regression alerting (OBS-01).
- Reviewed-not-folded todos: analyst predictions title bug, soft-cap allow-negative, pay-endpoint RPC (all v1.0 backend backlog, weak 0.6 matches).
