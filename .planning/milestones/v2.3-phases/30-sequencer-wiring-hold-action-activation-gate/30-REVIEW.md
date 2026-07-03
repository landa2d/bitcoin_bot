---
phase: 30-sequencer-wiring-hold-action-activation-gate
reviewed: 2026-07-01T17:40:32Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - docker/newsletter/newsletter_poller.py
  - docker/processor/agentpulse_processor.py
  - supabase/migrations/046_do_not_publish_columns.sql
  - tests/test_30_orchestration.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 30: Code Review Report

**Reviewed:** 2026-07-01T17:40:32Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Scoped to the Phase 30 diff since `6fc95b9`: the eval sequencer (`run_edition_eval` + 8 helpers), the two save-point invocations in `save_newsletter` / `process_task`, the two `do_not_publish` publish-gate guards in the processor, migration 046, and the orchestration test suite.

I verified every phase invariant against the code and found them **structurally sound**:

- **Fail-open-but-loud** holds — the `run_edition_eval` body is fully wrapped; the outage path (`llm_client is None`), the fabrication short-circuit, the Layer-2 exception path, and the outer `except` all write an `eval_status='error'` (or `held_fabrication`) telemetry row, alert once, and return a verdict object. Both the outage handler's `write_eval_row`/`_alert_operator` are individually guarded so a telemetry-or-alert failure still returns.
- **Governed identity** holds — `_build_eval_llm_client` reads `edition_eval._get_eval_api_key()`, never `claude_client`; the key is passed only to `anthropic.Anthropic(api_key=...)` and is logged as a boolean fact only. Test `test_build_eval_client_uses_governed_key_source_assert` locks this.
- **enforce-gating** holds — the `status='held' + do_not_publish=true` UPDATE fires only under `cfg.get('enforce')` and only for `held_*` verdicts; `passed`/`escalated` flip nothing. Report-only surfaces a would-have-held alert with no flip.
- **Processor stays dumb** — the two guards are pure `.get('do_not_publish')` column reads; no eval module is imported/called.
- **Log-injection hygiene** holds — `reason` / alert / `do_not_publish_reason` are built from category labels, counts, dimension names, per-dim scores, and a single-lined 240-char judge-critique excerpt — never raw draft prose.

No BLOCKER-class defects (no crash of the save path, no security gap, no auto-publish leak, no ledger corruption). Three WARNINGs concern robustness/deploy-ordering and operator-alert doubling; two INFOs are cosmetic/coverage.

## Warnings

### WR-01: Lazy imports sit outside the `try`, so `run_edition_eval` can re-raise — violating its documented "NEVER re-raise" contract

**File:** `docker/newsletter/newsletter_poller.py:483-487`
**Issue:** The three seam imports are placed *before* the `try:` block:

```python
def run_edition_eval(...):
    """... NEVER re-raises — an eval error must not block generation ..."""
    from deterministic_gate import run_deterministic_gate
    from judge_loop import run_layer2, _persistable_attempt
    from edition_eval import write_eval_row

    try:
        ...
```

An `ImportError` (a syntax error or a missing transitive dependency in any of the three eval modules) propagates *out* of `run_edition_eval` — directly contradicting the docstring and the phase's fail-open-but-loud invariant that the unit "NEVER re-raises." Both current call sites happen to wrap the call in a broad `try/except` (`save_newsletter` line 2108, `process_task` line 3124), so the save path will not crash *today*; but the unit-level guarantee that a future caller (or the Plan 31 SURF wiring) may rely on is broken, and an import failure escapes without writing an `eval_status='error'` telemetry row or paging the operator.
**Fix:** Move the three imports inside the `try` so an import failure is caught by the fail-open handler:

```python
def run_edition_eval(...):
    try:
        from deterministic_gate import run_deterministic_gate
        from judge_loop import run_layer2, _persistable_attempt
        from edition_eval import write_eval_row
        # (a) ...
```

### WR-02: The always-on A/B `bp_row` insert writes a top-level `do_not_publish` column that only exists after migration 046 — deploy-ordering coupling

**File:** `docker/newsletter/newsletter_poller.py:3076-3092` (write); `supabase/migrations/046_do_not_publish_columns.sql`
**Issue:** Phase 30 moves `do_not_publish` out of the `data_snapshot` JSONB and into a top-level column on the A/B shadow row:

```python
bp_row = {
    ...
    "status": "held",
    "do_not_publish": True,      # now a top-level column, NOT inside data_snapshot
    "data_snapshot": { "ab_comparison": True, ... },  # do_not_publish removed
}
insert_res = supabase.table("newsletters").insert(bp_row).execute()
```

Unlike everything else in Phase 30, this write is **not gated by the `edition_eval.enabled` flag** — it is on the always-on `ab_comparison` path. Migration 046 is authored-but-unapplied by design (operator applies it via the 30-04 MCP runbook). If the newsletter service is rebuilt with this code *before* 046 is applied, PostgREST rejects the insert (`PGRST204: Could not find the 'do_not_publish' column`), the enclosing A/B `try/except` (line 3124) swallows it as non-blocking, and the block_v1 A/B comparison + eval telemetry row is **silently lost** until the migration lands. Per project memory this A/B row is deliberately kept for v2.3 block_v1 eval, so losing it is a real regression, and it echoes the recorded "ship governance schema + code atomically" rule. Note: the processor-side *reads* correctly use `.get(...)` (robust to an absent column); only this *write* hard-depends on the DDL. This is distinct from "migration not applied" — the finding is the code/DDL ordering coupling on an ungated path.
**Fix:** Sequence the 30-04 runbook so 046 is applied via MCP **before** the newsletter service is rebuilt with this code; or, until the column is confirmed present, keep writing the A/B hold flag inside `data_snapshot` (JSONB accepts it unconditionally) and only promote to the top-level column post-apply.

### WR-03: The "telemetry-only" block_v1 shadow eval still pages the operator via `run_edition_eval`'s internal alerts, double-paging per edition on outage/escalation

**File:** `docker/newsletter/newsletter_poller.py:3096-3121` (telemetry call); internal alerts at `newsletter_poller.py:539-540` (escalated) and the outage/except handlers
**Issue:** The block_v1 telemetry call is documented as "NEVER act on the verdict — NO status flip and NO would-have-held alert," and it does discard the return value. But `run_edition_eval` itself calls `_alert_operator` internally on the `escalated` verdict (D-12), on the `llm_client is None` outage (D-07), and in the outer `except` handler. The telemetry caller cannot suppress those. Consequently, for a single single-pass-primary edition with `ab_comparison=true`, when the eval key is unset (or the eval escalates) the operator receives **two** pages for the same edition ("eval did not run for edition #N" from the primary eval *and* from the shadow eval) plus two `eval_status='error'` rows. This mildly conflicts with the phase's "alert the operator once" intent and the telemetry path's own stated "no alert" contract, and risks alert fatigue during the enabled-but-key-not-yet-minted activation window.
**Fix:** Add a `suppress_alerts`/`telemetry_only` keyword to `run_edition_eval` (default False) that the shadow-row call sets True, gating the `_alert_operator` calls; the error/telemetry rows still persist for A/B completeness. Alternatively, dedupe operator pages per edition number in `_alert_operator`.

## Info

### IN-01: `_dim_score` can render `dim=None` into the held_voice reason / `do_not_publish_reason`

**File:** `docker/newsletter/newsletter_poller.py:439-448` (`_dim_score`), consumed at `:534-538`
**Issue:** `_dim_score` returns `None` when a failing dimension has no numeric score across both bodies (e.g. a stray non-numeric `"n/a"` — `judge_loop` allows `continuity.score == "n/a"` per D-05). The held_voice reason then reads `"held_voice: continuity=None"`, which is surfaced to the operator (Telegram alert) and stored in `do_not_publish_reason`. This is cosmetic — the failing-dim set normally excludes non-applicable continuity — but a mixed/edge case yields an unhelpful `None`.
**Fix:** Render a placeholder when the score is missing, e.g. `score = _dim_score(sel_scores, dim); dim_parts.append(f"{dim}={score if score is not None else 'n/a'}")`.

### IN-02: The enforce-gated hold action (status flip) and the telemetry shadow eval have no automated coverage

**File:** `tests/test_30_orchestration.py` (whole suite); untested wiring at `docker/newsletter/newsletter_poller.py:2152-2172` and `:3096-3121`
**Issue:** The suite comprehensively locks the `run_edition_eval` orchestrator unit (verdict-iff-ok, fail-open, governed-identity passthrough, no-status-flip), which is appropriate. But the Plan 30-03 wiring it feeds — the `enforce=true` `status='held' + do_not_publish=True` UPDATE, the report-only would-have-held branch, and the block_v1 telemetry call — has no unit/integration test. These are the branches that actually mutate publish state, and a regression there (e.g. an accidental flip under `enforce=false`, or writing to the wrong `row_id`) would not be caught. Not a defect in the code as written, but a coverage gap on the highest-consequence path.
**Fix:** Add a focused test around the `save_newsletter` eval block that stubs `run_edition_eval` to return each verdict and asserts (a) no `.update` under `enforce=false`, (b) exactly the `{status, do_not_publish, do_not_publish_reason}` UPDATE keyed on `row_id` under `enforce=true` for `held_*`, and (c) no flip for `passed`/`escalated`.

---

## Resolution (orchestrator, 2026-07-01)

| Finding | Disposition | Evidence |
|---------|-------------|----------|
| WR-01 (fail-loud: re-raise on ImportError) | **FIXED** — commit `84f639d` | Lazy imports moved inside the `run_edition_eval` try; AST confirms 0 `raise` in the function, imports inside try. |
| WR-03 (double-page on shadow eval) | **FIXED** — commit `84f639d` | `suppress_alerts=False` kwarg added; block_v1 telemetry call passes `suppress_alerts=True`; error/telemetry rows still persist. |
| IN-01 (`dim=None` in operator reason) | **FIXED** — commit `84f639d` | held_voice reason renders `n/a` when a failing dim has no numeric score. |
| WR-02 (A/B insert hard-depends on unapplied 046) | **DOCUMENTED (deploy-ordering)** — no code change | Zero live exposure: the newsletter container runs pre-30 code until the ordered 30-04 rebuild, which applies 046 (Task 2) before rebuilding newsletter (Task 4). A code "fix" would revert the locked D-02 one-canonical-home decision; the 30-04 Task-4 runbook note was strengthened to make the newsletter-side coupling explicit. Operator decides at activation whether to dual-write. |
| IN-02 (no test on the enforce-gated flip) | **DEFERRED (follow-up)** — no code change | The flip branch is verifier-traced but not unit-tested; a proper test needs extracting a `_apply_primary_verdict` seam or a heavy `save_newsletter` integration harness. Recommended as a follow-up test; not a fail-loud/data-loss item. |

Fixes verified: 144 eval tests green (test_30 + 26–29 regression), AST clean.

---

_Reviewed: 2026-07-01T17:40:32Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
