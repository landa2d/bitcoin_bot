# Phase 30: Sequencer Wiring, Hold Action & Activation Gate - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the two already-built eval layers — the Phase-28 Layer-1 deterministic gate (`run_deterministic_gate`) and the Phase-29 Layer-2 judge + N=2 rewrite loop (`run_layer2`) — into the `newsletter_poller` sequencer at the two generation save points, and act on the returned verdicts: hold + `do_not_publish` + Gato escalation on fabrication/voice failures, unchanged human gate on pass, all behind a report-only `enforce` flag. The Processor stays a dumb sequencer (no LLM, no retry/rewrite state). The whole step is rollback-safe (`enabled=false` disables invocation). Requirements: **WIRE-01..06.**

**In scope:** the poller-side invocation of both eval layers at the two save points; the verdict→status/`do_not_publish`/escalation mapping; migration 046 (net-new `do_not_publish` columns); the `enabled`/`enforce` gating semantics; fail-open-but-loud eval-error handling; the operator-owned live-activation runbook.

**Out of scope (own phases):** hardened `send_telegram` + Friday-notify per-draft eval summary + live `/newsletter_eval` Gato command → **Phase 31 (SURF)**. Threshold auto-tuning, `edition_revisions` edit trail, quantitative A/B trend surface → deferred v2.3-future items.
</domain>

<decisions>
## Implementation Decisions

### Hold-state persistence (WIRE-02)
- **D-01:** Migration **046** adds `do_not_publish boolean NOT NULL DEFAULT false` + `do_not_publish_reason text` as **first-class columns** on `newsletters`. The publish gate reads the **column** directly — not nested JSONB. (Queryable, structural — honors the "structural over application enforcement" preference.)
- **D-02:** **Hold state has exactly ONE canonical home.** The existing A/B shadow-row `data_snapshot.do_not_publish` JSONB flag (currently the *only* place `do_not_publish` lives, at `newsletter_poller.py` ~line 2690) is reconciled to the new column: code that writes/reads `data_snapshot.do_not_publish` moves to the column. No two-homes drift — the JSONB flag must not remain a second source of truth.

### Completion boundary & live activation (WIRE-06)
- **D-03:** Phase 30 delivers the **worktree-safe wiring** shipped `edition_eval.enabled=false` (fully dormant, rollback-safe). "Done" does NOT require a live edition to have run — consistent with the 27/28/29 build-then-activate posture.
- **D-04:** Live arming is an **explicit operator-owned runbook** (NOT worktree execution), authored in the plan as an orchestrator/operator step:
  1. **Phase 27-03 (still pending)** — mint the `edition_eval` proxy key → bcrypt hash substituted into `045_edition_evals.sql` §2, write `LLM_PROXY_EVAL_KEY` to `config/.env`.
  2. **MCP-apply** migration 045 (edition_evals table + governed agent) **and** migration 046 (do_not_publish columns).
  3. **Verify** a settled governed proxy call on the `edition_eval` agent (the first live prerequisite).
  4. Flip `edition_eval.enabled=true`, keep `enforce=false` → the **report-only calibration window** (~first 2 editions).
  5. Later, operator flips `enforce=true` to arm auto-hold.

### Eval invocation & failure semantics (WIRE-01, WIRE-05)
- **D-05:** The `newsletter_poller` sequencer invokes Layer-1 gate then `run_layer2` at the **two save points** (single-pass save-return + block_v1 A/B insert). The **Processor stays a dumb sequencer** — no LLM calls, no retry/rewrite state; it triggers generation, owns the publish gate, and surfaces verdicts via a plain select (WIRE-05).
- **D-06:** **Fail-open on eval-infrastructure error.** Wrap the eval call so any exception / `eval_status='error'` writes the error row and the **generation task CONTINUES**; the draft proceeds to the unchanged Monday human gate — an eval error NEVER blocks generation ("an error is not evidence", consistent with Layer-1's `unverified` telemetry-only rule).
- **D-07:** **…but the outage is LOUD.** When the eval fails to run, Gato-notify the operator that the eval didn't run (fail-loud on the *outage*, not on the draft). Never a silent no-op.
- **D-08:** `run_layer2` MUST be called with a **real `httpx.Client` injected** — the Phase-29 load-bearing note (`29-03-SUMMARY.md`): the per-rewrite fabrication re-check is gated on an injected client, and Phase 29's WR-02 fix emits a loud `logger.warning` if it's omitted. Phase 30 must inject one so the re-check is active live.

### Verdict → action mapping (WIRE-02/03/04)
- **D-09:** `held_fabrication` (any Layer-1 fabrication flag) → primary draft `status='held'` + `do_not_publish=true` + a detailed `do_not_publish_reason` + Gato escalation; the rewrite loop is **not** entered.
- **D-10:** `held_voice` (Layer-2 dimension still failing after N=2) → `held` + `do_not_publish` + Gato escalation carrying the final per-dimension scores + feedback (never a silent best-effort publish).
- **D-11:** `passed` → **no auto-publish**; the edition proceeds to the unchanged Monday human review gate (WIRE-04).
- **D-12:** `escalated` / eval error → fail-open (D-06) + operator alert (D-07); draft proceeds to the normal human gate.

### Hold target & telemetry scope
- **D-13:** Hold-action (`status='held'` + `do_not_publish`) acts **only on the single-pass / primary publish draft** (`save_newsletter`, the row that reaches the Monday gate and can publish). The block_v1 A/B row is already an always-held shadow.
- **D-14:** **Both save points are still fully EVALUATED** (Layer-1 + judge run on each so the A/B trend telemetry is complete); the block_v1 eval is **telemetry-only** — recorded per-attempt to `edition_evals`, it never flips publish state. Only the primary draft's verdict drives a status change.

### Report-only vs enforce semantics (WIRE-06)
- **D-15:** `enabled` controls **invocation** (false = don't invoke at all → rollback-safe). `enforce` controls **auto-hold** (false = report-only: compute verdict + write `edition_evals` rows + surface "would-have-held" verdicts to Gato, but NO status / `do_not_publish` flip). Ship `enabled=false`; the report-only window precedes the operator flipping `enforce=true`.

### Claude's Discretion
- Exact Gato alert copy/format and any alert dedup/rate-limiting — planner-level detail (hardened `send_telegram` is Phase 31 SURF).
- Whether migration 046 backfills historical rows beyond the `DEFAULT false` (A/B shadow rows may be left as historical or backfilled to the column — low-risk, planner decides).
- Precise placement of the invocation calls inside `process_task` / `save_newsletter` and how the primary-draft `newsletter_id` is threaded to the status flip.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone & eval specs
- `docs/audit/specs/01_eval_harness.md` — audit R5 eval-harness spec; the implementation reference for wiring points, `verify_draft` reuse, and verdict semantics.
- `.planning/REQUIREMENTS.md` — WIRE-01..06 (lines ~61-66), the verdict definitions (`held_fabrication` / `passed` / `held_voice`, lines ~90-92), and the Activation note (line ~95).
- `.planning/research/INVENTORY.md` — the reconciled live-system map (the two save points, where the fact base lives in memory, `send_telegram` fail-soft today, no `do_not_publish` column today).

### Code to wire into
- `docker/newsletter/newsletter_poller.py` — the sequencer. Key sites: `save_newsletter` (~line 1658, the single shared insert for BOTH single-pass and block-primary; row built ~1707, insert ~1720, `status='draft'`, no `do_not_publish` field today); `process_task` (~line 2304); the A/B block path (~lines 2597-2700, the always-held shadow `bp_row` insert that currently sets `data_snapshot.do_not_publish=True`).
- `docker/newsletter/judge_loop.py` — Phase 29 `run_layer2(...)`; **inject a real `httpx.Client`** (see `29-03-SUMMARY.md`).
- `docker/newsletter/deterministic_gate.py` — Phase 28 `run_deterministic_gate(...)`, the Layer-1 gate (emit-only `{fabrication, unverified, mechanical, meta}`).
- `docker/newsletter/edition_eval.py` — Phase 27 persistence: `write_eval_row` / `read_evals_by_newsletter` / `read_eval_trend` / the `LLM_PROXY_EVAL_KEY` identity getter.
- `config/agentpulse-config.json` → `edition_eval` block — already carries `enabled` (false), `enforce` (false), `max_attempts` (2), judge/revise model params, `thresholds`, `filler_blacklist`.

### Schema / activation
- `supabase/migrations/045_edition_evals.sql` — `edition_evals` table + governed `edition_eval` agent seed; the **27-03 prerequisite** (needs key/bcrypt substitution + MCP apply before any live run).
- `supabase/migrations/046_*.sql` — **NEW this phase:** `do_not_publish` + `do_not_publish_reason` columns on `newsletters` (authored in-phase, SQL-first, operator-applied via MCP).
- `.planning/phases/29-layer-2-judge-feedback-rewrite-loop/29-03-SUMMARY.md` — the load-bearing `http_client` injection requirement (D-08).

### Standing invariants
- `.planning/STATE.md` → "Standing milestone invariants" — Processor-stays-dumb-sequencer, all-LLM-via-proxy, fail-loud (NULL ≠ intent), SQL-first migrations, fabrication = hard stop, pass never auto-publishes.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `run_deterministic_gate` (Phase 28), `run_layer2` (Phase 29), `write_eval_row` (Phase 27) — the three finished building blocks; Phase 30 only *sequences* them, adds no new eval logic.
- `edition_eval` config block already exists with `enabled`/`enforce`/`thresholds`/`max_attempts` — the wiring just reads these flags (no new config schema needed beyond confirming shape).
- `send_telegram` — the Gato alert path used for holds/escalations. **Fail-soft today** (silent `return` on unset env); D-07 requires holds NOT be a silent no-op, and Phase 31 hardens it.

### Established Patterns
- Both eval layers run in the **newsletter service at generation time** — the only place the true fact base exists in-memory (`input_data` for single-pass, `blocks_data` for block_v1; gone by publish time).
- `save_newsletter` is the single shared insert for both write paths — guarding/threading the primary `newsletter_id` here covers both single-pass and block-primary.
- Migrations are SQL-first, **operator-applied via MCP** — worktree-unsafe; the plan's activation runbook owns 045/046 apply (orchestrator/operator on the main tree).
- The A/B block path already writes `do_not_publish` (in `data_snapshot`) — the reconciliation target for D-02.

### Integration Points
- **Single-pass / primary save-return** (`save_newsletter`, insert ~line 1720): gate + judge on the `input_data` fact base → verdict → status/`do_not_publish` flip on the **primary** row (D-13).
- **block_v1 A/B insert** (~line 2700): gate + judge on the `blocks_data` fact base → **telemetry-only** `edition_evals` rows (D-14); no publish-state change (row is already always-held).
- Verdict surfacing to the operator (Friday notify / plain select) is **Phase 31**, not here — Phase 30 stops at the hold + escalation alert.
</code_context>

<specifics>
## Specific Ideas

- **One canonical home for hold state** (operator, explicit): the `do_not_publish` column is the single source of truth; the A/B shadow-row JSONB flag is reconciled to it, not left as a parallel truth.
- **Fail-open-but-loud**: a broken eval must never block a newsletter from drafting, but an eval *outage* must page the operator — the failure mode to design against is a silently-not-running gate.
- **`run_layer2` needs a real `httpx.Client`** so the Phase-29 per-rewrite fabrication re-check is actually live (not the zero-egress test path).
</specifics>

<deferred>
## Deferred Ideas

- **Phase 31 (SURF):** hardened `send_telegram` hold/escalation alerts (never a silent no-op), Friday-notify per-draft eval summary (plain select, no Processor LLM), live `/newsletter_eval` (+ `trend`) Gato command (needs `isGatoBrainCommand` allowlist + gato rebuild). Exact escalation-alert copy/dedup also lands here.
- **v2.3-future (already in STATE Deferred Items):** `edition_revisions` operator-edit trail (REV-01), quantitative single-pass-vs-block_v1 A/B comparison trend (AB-01), per-dimension threshold auto-tuning from history (TUNE-01), eval-trend regression alerting (OBS-01).

### Reviewed Todos (not folded)
- `2026-05-28-analyst-predictions-title-expire-bug.md` (analyst predictions `title` expire bug) — weak keyword match (0.6), v1.0 backend backlog, unrelated to eval wiring.
- `2026-05-28-harden-soft-caps-allow-negative.md` (soft-cap allow-negative hardening) — weak match, governance backlog, out of scope.
- `2026-05-28-pay-endpoint-500-transfer-rpc-search-path.md` (transfer_between_agents RPC) — weak match, tooling backlog, out of scope.

</deferred>

---

*Phase: 30-sequencer-wiring-hold-action-activation-gate*
*Context gathered: 2026-07-01*
