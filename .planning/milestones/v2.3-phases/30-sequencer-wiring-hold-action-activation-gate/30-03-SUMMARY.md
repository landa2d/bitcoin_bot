---
phase: 30-sequencer-wiring-hold-action-activation-gate
plan: 03
subsystem: newsletter
tags: [eval-wiring, hold-action, enforce-gate, do-not-publish, telemetry, ab-comparison, fail-open]

# Dependency graph
requires:
  - phase: 30-02
    provides: "run_edition_eval orchestrator + _read_edition_eval_config / _build_eval_llm_client / _alert_operator / _fetch_prior_published_edition helpers"
  - phase: 30-01
    provides: "migration 046 do_not_publish + do_not_publish_reason columns on newsletters (authored, operator-applied in 30-04) + processor publish-gate guards"
provides:
  - "save_newsletter: primary-draft eval invocation (enabled-gated) + enforce-gated status='held'+do_not_publish+reason flip on the primary row_id; report-only would-have-held alert; passed=no flip; escalated=already-alerted"
  - "block_v1 A/B save point: do_not_publish reconciled to the top-level migration-046 column (one canonical home, D-02) + telemetry-only run_edition_eval on the always-held shadow row (D-14)"
affects: [30-04-activation-runbook, 31-surfacing-escalation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One httpx.Client(timeout=15.0) per save point, the SAME instance threaded to both eval modules via run_edition_eval (D-08 live network re-check active)"
    - "enabled gates INVOCATION (rollback-safe); enforce gates the STATUS FLIP only — report-only computes+persists+alerts but never flips (D-15)"
    - "Fail-open wrapper around the whole primary-eval block: logs ERROR and continues — the row is already inserted, generation never breaks on an eval/action error (D-06)"

key-files:
  created: []
  modified:
    - "docker/newsletter/newsletter_poller.py — save_newsletter primary eval+hold action; block_v1 A/B do_not_publish reconciliation + telemetry-only eval"

key-decisions:
  - "Primary eval lives INSIDE save_newsletter (self-contained, uses the local row_id) — no caller change at the process_task save site; the fact base is re-derived from the same Phase-D branch (robust to an early Phase-D exception) rather than reusing the leaked verification_input binding"
  - "held reason surfaced verbatim in the operator alert + do_not_publish_reason — it is built inside run_edition_eval from category labels/counts (+ per-dim scores + bounded judge_feedback excerpt for held_voice), never raw draft prose (T-30-LOG)"
  - "block_v1 A/B eval is telemetry-only: run_edition_eval is called and its return DISCARDED — no status flip, no would-have-held alert on the always-held shadow row (D-14); only the primary draft's verdict drives publish state (D-13)"
  - "Ships DORMANT (enabled=false live): the whole primary-eval block and the A/B telemetry eval are behind _read_edition_eval_config().get('enabled', False); first LIVE invocation still needs the operator to mint LLM_PROXY_EVAL_KEY (27-03) + MCP-apply 045/046 (30-04)"

patterns-established:
  - "Verdict→action table at the primary save point: held_fabrication/held_voice → (enforce) flip+escalate / (report-only) would-have-held alert; passed → no-op (WIRE-04); escalated → no-op (orchestrator already alerted, D-12)"
  - "do_not_publish has exactly ONE canonical home — the top-level migration-046 column; the A/B JSONB flag was moved out of data_snapshot (D-02, no read/write drift)"

requirements-completed: []  # WIRE-01/02/03/04/06 now WIRED at both save points + acted-upon; closure DEFERRED to phase-end verify (ships dormant, 30-04 activation + key mint pending) — consistent with the 27/28/29/30-01/30-02 fail-loud-accuracy posture

# Metrics
duration: ~8min
completed: 2026-07-01
---

# Phase 30 Plan 03: Sequencer Wiring + Hold Action Summary

**The consequential wiring step: `run_edition_eval` is now invoked at both generation save points and its verdict is acted upon — an enforce-gated `status='held'`+`do_not_publish`+reason flip on the primary draft (report-only surfaces a would-have-held alert with no flip), a pass never auto-publishes, and the block_v1 A/B row is fully evaluated as telemetry-only — all behind `enabled` (invocation) and `enforce` (auto-hold) so it ships dormant and rollback-safe.**

## Performance

- **Duration:** ~8 min
- **Completed:** 2026-07-01
- **Tasks:** 2 (both `type=auto`)
- **Files modified:** 1 (`docker/newsletter/newsletter_poller.py`)

## Accomplishments
- **Task 1 — primary-draft eval + enforce-gated hold** (`save_newsletter`, after the Phase-D block): reads `cfg = _read_edition_eval_config()`; when `enabled=true` re-derives the fact base from the identical Phase-D branch (`block_v1` vs `single_pass`, D-13), builds the `draft` dict, binds `prior_context = input_data.get('narrative_context') or {}`, fetches the prior published edition, builds the GOVERNED `edition_eval` client, opens ONE `with httpx.Client(timeout=15.0) as hc:` and calls `run_edition_eval(..., newsletter_id=row_id, http_client=hc, github_token=os.getenv('GITHUB_TOKEN'))`. Acts on `verdict_obj['verdict']` on the PRIMARY `row_id`: `held_fabrication`/`held_voice` → under `enforce=true` an `[EVAL HELD]` alert AND `update({'status':'held','do_not_publish':True,'do_not_publish_reason':reason})`; under `enforce=false` an `[EVAL would-have-held]` alert with NO flip (D-15). `passed` → no flip (WIRE-04); `escalated` → no-op (orchestrator already alerted, D-12). Whole block in a try/except-continue (fail-open, D-06); the flip is skipped when `row_id is None`.
- **Task 2 — A/B reconciliation + telemetry-only block_v1 eval** (`process_task` A/B path): moved `do_not_publish` OUT of `bp_row['data_snapshot']` to a TOP-LEVEL `bp_row["do_not_publish"] = True` (the migration-046 column, one canonical home, D-02) and deleted the data_snapshot copy — the row stays `status='held'`, only the flag's HOME moved. Captured `bp_row_id` from the insert result and ran `run_edition_eval` on the `ab_verification_input` fact base as TELEMETRY-ONLY — the return is discarded, NO status flip, NO would-have-held alert on the always-held shadow row (D-14). Runs inside the existing A/B try/except-continue.
- **Ships dormant:** both invocations are gated on `_read_edition_eval_config().get('enabled', False)` (live config `enabled=false`), so the deployed behavior is a byte-for-byte no-op until the operator arms it (30-04). Auto-hold additionally gated on `enforce` (live `false`).

## Task Commits

Each task was committed atomically:

1. **Task 1: primary-draft eval + enforce-gated hold in save_newsletter** — `6648d3f` (feat)
2. **Task 2: A/B do_not_publish reconciliation + telemetry-only block_v1 eval** — `42b3067` (feat)

**Plan metadata:** (this SUMMARY + STATE + ROADMAP) — final docs commit.

## Files Created/Modified
- `docker/newsletter/newsletter_poller.py` — Task 1 inserted the primary eval + verdict→action block immediately after the Phase-D verification block in `save_newsletter`; Task 2 reconciled the `bp_row` `do_not_publish` home and added the telemetry-only block_v1 eval after the A/B insert.

## Decisions Made
- **Primary eval is self-contained in `save_newsletter`** — it uses the function-local `row_id` directly, so no caller change was needed at the `process_task` save site (`save_newsletter(...)` return still discarded there). The fact base is **re-derived** from the same two-branch logic rather than reusing the Phase-D `verification_input` binding, so an early Phase-D exception cannot leak a stale/undefined binding into the eval.
- **`reason` surfaced verbatim** in both the alert and `do_not_publish_reason` — it is built inside `run_edition_eval` from category labels/counts (and, for `held_voice`, failing-dimension names + per-dim scores + a bounded one-line `judge_feedback` excerpt), never raw draft prose (T-30-LOG).
- **Block eval telemetry-only** — `run_edition_eval` is called and its return **discarded**; the always-held shadow row's verdict must never influence what ships (D-14). Only the primary draft's verdict drives publish state (D-13).
- **Requirement closure deferred** — WIRE-01/02/03/04/06 are now fully WIRED and acted-upon, but the plan ships dormant (`enabled=false`) and the first live invocation still needs the 30-04 activation runbook (key mint + MCP-apply 045/046). Closure is left to phase-end `/gsd-verify-work`, consistent with the 27/28/29/30-01/30-02 fail-loud-accuracy posture.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Re-derived the primary fact base instead of reusing `verification_input`**
- **Found during:** Task 1
- **Issue:** The plan says `bind fact_base = verification_input`, but `verification_input` is assigned inside the Phase-D `try` block. If Phase-D raised before that assignment (e.g. the `from verification import verify_draft` import failed), the eval block would hit a `NameError` on a leaked/undefined binding.
- **Fix:** Re-derived the fact base with the identical two-branch logic (`block_v1` blocks dict vs `single_pass` `input_data`) inside the eval block — functionally identical to `verification_input`, but robust to an early Phase-D exception. This is Analog A ("copy this branch verbatim") applied defensively.
- **Files modified:** docker/newsletter/newsletter_poller.py
- **Verification:** AST parse exits 0; `pipeline_version` derived identically; full gate green.
- **Committed in:** `6648d3f`

---

**Total deviations:** 1 auto-fixed (defensive fact-base re-derivation).
**Impact on plan:** No behavior change vs the plan's intent — the same fact base is passed, just resolved robustly. No scope creep; all acceptance criteria and both verification gates pass.

## Issues Encountered
None. Both `<verify><automated>` gates passed on the first run after each edit; the 30-02 helpers were used unchanged and `tests/test_30_orchestration.py` (9/9) plus the 27/28/29 regression (124) stayed green (133 total).

## Known Stubs
None. The eval invocations are behind `enabled=false` by design (rollback-safe dormancy, D-03/D-15 — documented in PROJECT/STATE as the activation discipline), not placeholders. No hardcoded UI-facing empties, no TODO/placeholder text introduced.

## Threat Flags
None net-new. All security-relevant surface is already in the plan's `<threat_model>`: the enforce-gated status flip on the primary `row_id` only (T-30-HOLD), the pass→no-UPDATE path (T-30-AUTOPUB/WIRE-04), the single-canonical-home `do_not_publish` (T-30-DRIFT/D-02), the label/count/dim-only alert + reason text (T-30-LOG), and the discarded-verdict block telemetry eval (T-30-SHADOW/D-14). No package installs (T-30-SC). No new network endpoint, auth path, or schema change beyond the already-authored migration 046 columns.

## Next Phase Readiness
- **30-04** (the activation runbook, operator-owned): MCP-apply migrations 045 + 046, mint `LLM_PROXY_EVAL_KEY` (27-03), scoped `newsletter` rebuild, then arm via `edition_eval.enabled=true` (report-only) for ~2 editions before flipping `enforce=true`. The wiring this plan landed is inert until then.
- **31 (Surfacing & Escalation):** hardens the interim `_alert_operator` Telegram path via the shared `send_telegram`, adds the Friday per-draft eval summary + the `/newsletter_eval` Gato command. The verdict→action + `edition_evals` telemetry it surfaces are now produced at both save points.

## Self-Check: PASSED
- `docker/newsletter/newsletter_poller.py` — FOUND (primary eval + block telemetry eval present)
- Commits `6648d3f`, `42b3067` — both FOUND in git log
- Gates: `python3 -c "import ast; ..."` exits 0; `run_edition_eval(` ≥2×; `with httpx.Client(timeout=15.0) as hc` present; `'do_not_publish': True` (Task 1 update) + `"do_not_publish": True` (Task 2 bp_row top-level) present; `get('enforce'` present; `bp_row_id` captured; `pytest tests/test_30_orchestration.py -q` → 9 passed; regression `test_27/28/29` → 124 passed (133 total).

---
*Phase: 30-sequencer-wiring-hold-action-activation-gate*
*Completed: 2026-07-01*
