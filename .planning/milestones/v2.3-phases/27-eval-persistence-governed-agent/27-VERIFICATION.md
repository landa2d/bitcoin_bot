---
phase: 27-eval-persistence-governed-agent
verified: 2026-06-25T17:30:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
deferred:
  - truth: "SC2 Telegram-alert half: an eval-row write that fails is logged ERROR + Telegram-alerted"
    addressed_in: "Phase 30 (WIRE-03) and Phase 31 (SURF-01)"
    evidence: "Phase 31 success criteria SURF-01: 'Hold/escalation notifications reuse send_telegram and are hardened so a held edition never silently fails to alert'. D-10 (locked decision) explicitly assigns Telegram delivery to Phases 30/31. Scoping notes confirm EVAL-02's Telegram half is Phase 30/31 by design."
---

# Phase 27: Eval Persistence & Governed Agent Verification Report

**Phase Goal:** The `edition_evals` table (migration 045) and a governed `edition_eval` proxy agent exist — the fail-loud persistence + budget core both eval layers write through. SQL-first (authored in-phase, operator-applied via MCP after DDL review); the agent has its own hard-capped, reject-on-cap wallet. Realizes the milestone-wide fail-loud / no-silent-zero invariant and the no-`.in_()` rule for all eval reads/writes.
**Verified:** 2026-06-25T17:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | Migration 045 creates `edition_evals` with all per-attempt columns, `verdict-iff-ok` CHECK, `UNIQUE(newsletter_id, layer, attempt)`, applied via MCP after DDL review | VERIFIED | File confirmed at `supabase/migrations/045_edition_evals.sql` (116 lines); all 12 required columns present verbatim from REQUIREMENTS.md DDL; `edition_evals_verdict_iff_ok` CHECK present; `UNIQUE (newsletter_id, layer, attempt)` present; `idx_edition_evals_trend` present; real `$2b$12$` bcrypt hash present (placeholder gone); live DB existence confirmed by orchestrator pre-flight |
| SC2 | An eval that errors writes `eval_status='error'` + reason — proxy 402 is an error state never a zero score; failed eval-row write is logged ERROR (never swallowed; no bare excepts) | VERIFIED (Phase 27 scope); Telegram-alert half deferred → Phase 30/31 | `write_eval_row` validates error-row shape (eval_status='error' + non-empty error string + NULL verdict) before insert; `exc_info=True` appears 3× in module; try/except re-raises (no swallow); 15/15 tests pass including `test_write_failure_logs_error_and_reraises` and `test_empty_insert_result_raises_loudly`; `.in_(` count = 0 throughout module |
| SC3 | All `edition_evals` reads/writes use plain supabase-py `.eq()` (no `.in_()`) | VERIFIED | `grep -c '.in_(' docker/newsletter/edition_eval.py` = 0; test stub deliberately omits `in_` method so accidental use raises `AttributeError`; `test_reads_use_eq_only_and_never_an_in_filter` asserts `not hasattr(q, 'in_')` |
| SC4 | A governed `edition_eval` agent with its own registry + wallet rows, `allow_negative=false`, weekly `spending_cap_sats`, `on_cap_behavior='reject'`, `uncapped=false`; key via `.env` `LLM_PROXY_EVAL_KEY`, never in compose | VERIFIED | Live DB confirmed by orchestrator: `allow_negative=false`, `spending_cap_sats=5000`, `spending_cap_window='weekly'`, `uncapped=false`, `on_cap_behavior='reject'`, `balance_sats` started 25000 and decremented to 24999 on first settled call; `grep -c 'LLM_PROXY_EVAL_KEY' docker/docker-compose.yml` = 0; `grep -c '^LLM_PROXY_EVAL_KEY=' config/.env` = 1; `git check-ignore config/.env` confirms gitignored |

**Score:** 4/4 truths verified

---

### Deferred Items

Items not yet met at Phase 27 scope but explicitly addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | SC2 Telegram-alert half: "a failed eval-row write is logged ERROR + Telegram-alerted" | Phase 31 (SURF-01), Phase 30 (WIRE-03) | Phase 31 SURF-01: "Hold/escalation notifications reuse `send_telegram` and are hardened so a held edition never silently fails to alert." Locked decision D-10 assigns Telegram delivery to Phases 30/31. Scoping notes: "EVAL-02's Telegram-alert half and a live caller are explicitly assigned to later phases (28/30/31) by design." The persistence helper raises loudly on write failure — the caller that wraps `send_telegram` is Phase 30's scope. |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/migrations/045_edition_evals.sql` | SECTION 1 DDL + SECTION 2 agent seed | VERIFIED | 116 lines; all REQUIREMENTS.md DDL columns present; `edition_evals_verdict_iff_ok` CHECK present; `UNIQUE (newsletter_id, layer, attempt)` present; `idx_edition_evals_trend` present; `$2b$12$` real bcrypt hash substituted; `<bcrypt-hash>` placeholder gone (count = 0); no spec-01 materialized columns (`tier1_count|voice_score|baseline_newsletter_id|edition_revisions` count = 0) |
| `docker/newsletter/edition_eval.py` | `write_eval_row` + readers + identity getter; no `.in_()`; no newsletter_poller reference | VERIFIED | 217 lines; syntax clean (`ast.parse`); `write_eval_row` defined × 1; `read_evals_by_newsletter` defined × 1; `read_eval_trend` defined × 1; `_get_eval_api_key` defined × 1; `.in_(` = 0; `exc_info=True` = 3; `newsletter_poller` = 0; `_get_agent_api_key` = 0; `AGENT_NAME` = 0; `LLM_PROXY_EVAL_KEY` present |
| `tests/test_27_edition_eval.py` | 15-test deterministic fixture suite; imports REAL module; in-memory stub | VERIFIED | 333 lines; 15 tests collected and passed (`pytest tests/test_27_edition_eval.py -v` → 15 passed in 0.02s); `import edition_eval` × 1; `pytest.raises(ValueError)` × 8; `caplog` × 7; `def in_` = 0; `StubSupabase` + `RaisingSupabase` + `EmptyInsertSupabase` stubs present |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/test_27_edition_eval.py` | `docker/newsletter/edition_eval.py` | `import edition_eval as ee` (real module via sys.path insert) | VERIFIED | `import edition_eval` confirmed in test file; module confirmed importable with all 3 functions callable; no re-implementation in test |
| `supabase/migrations/045_edition_evals.sql` SECTION 2 wallet seed | `agent_wallets_v2_cap_or_uncapped` CHECK (migration 034) | `spending_cap_sats=5000 > 0` satisfies cap-or-uncapped invariant | VERIFIED | `spending_cap_sats=5000` present in INSERT VALUES; `uncapped=FALSE`; 5000 > 0 satisfies the 034 CHECK; live wallet row confirmed by orchestrator |
| `config/.env` `LLM_PROXY_EVAL_KEY` | `agent_registry.api_key_hash` (committed bcrypt hash) | `proxy.py` `bcrypt.checkpw` authenticates the edition_eval agent | VERIFIED | Plaintext in gitignored `.env` confirmed (count=1); hash in migration file is `$2b$12$` form; orchestrator confirmed HTTP 200 settled call as `edition_eval` (proves bcrypt.checkpw passed) |

---

### Data-Flow Trace (Level 4)

Not applicable — `edition_eval.py` is a persistence helper (write + read functions), not a rendering component. It takes `supabase` as an explicit parameter and has no module-global client that could be a silent data source. The readers return `.data or []` directly. No rendering of dynamic data in this phase.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Module importable with all public functions | `python3 -c "import sys; sys.path.insert(0, 'docker/newsletter'); import edition_eval; ..."` | All 4 functions callable; `in_` absent from module namespace | PASS |
| 15-test suite green | `python3 -m pytest tests/test_27_edition_eval.py -v` | 15 passed in 0.02s | PASS |
| Migration 045 DDL checks | `grep -c` / `grep -q` battery on all key tokens | verdict-iff-ok CHECK present; UNIQUE present; trend index present; forbidden columns = 0; EOL model = 0; real bcrypt hash present; ON CONFLICT count = 2 | PASS |
| Key delivery / compose isolation | `grep -c '^LLM_PROXY_EVAL_KEY=' config/.env`; `grep -c 'LLM_PROXY_EVAL_KEY' docker/docker-compose.yml`; `git check-ignore config/.env` | `.env` = 1; compose = 0; gitignored confirmed | PASS |
| CR-01 fix: wallet ON CONFLICT excludes ledger fields | Manual read of `ON CONFLICT (agent_name) DO UPDATE` clause in SECTION 2 | Update sets only: `allow_negative`, `spending_cap_sats`, `spending_cap_window`, `uncapped`, `on_cap_behavior`, `downgrade_map` — `balance_sats` and `total_deposited_sats` are NOT in the update list | PASS |
| WR-01 fix: full value-domain validation | `grep -n '_VERDICTS\|_PIPELINE_VERSIONS\|_LAYERS'` in `edition_eval.py` | `_VERDICTS`, `_PIPELINE_VERSIONS`, `_LAYERS`, `_EVAL_STATUSES` tuples defined at module level; validation uses `verdict in _VERDICTS` (not `is not None`) rejecting `0` and `""`; confirmed by `test_ok_status_with_numeric_zero_verdict_raises_before_insert` | PASS |
| WR-02 fix: empty insert raises | `grep -n 'insert returned no row\|raise RuntimeError'` in `edition_eval.py` | Lines 173-182: ERROR logged + `RuntimeError` raised on `not result.data`; confirmed by `test_empty_insert_result_raises_loudly` | PASS |

---

### Probe Execution

Not applicable — no `probe-*.sh` files declared or found for this phase. The phase's verification contract uses pytest + grep gates, all confirmed above.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| EVAL-01 | 27-01-PLAN.md | `edition_evals` table (per-attempt, all columns, verdict-iff-ok CHECK, UNIQUE, index), applied via MCP | VERIFIED | DDL confirmed in migration file; live table existence confirmed by orchestrator; all column/constraint checks pass |
| EVAL-02 | 27-02-PLAN.md | Fail-loud write: `eval_status='error'` + reason on error; logged ERROR + no bare excepts; Telegram-alert (Phase 30/31) | VERIFIED (Phase 27 scope) | `write_eval_row` validates and re-raises; `exc_info=True` × 3; no bare excepts confirmed; 15 tests pass; Telegram half deferred per D-10 |
| EVAL-03 | 27-02-PLAN.md | All `edition_evals` reads/writes use `.eq()` only (no `.in_()`) | VERIFIED | `.in_(` = 0 in module; test stub omits `in_` method; `test_reads_use_eq_only_and_never_an_in_filter` passes |
| GOV-01 | 27-01-PLAN.md, 27-03-PLAN.md | Governed `edition_eval` agent routes all model calls through `llm-proxy:8200` | VERIFIED | Agent rows live in Supabase (orchestrator confirmed); settled proxy call returned HTTP 200 debiting the wallet (governed cycle proven); `LLM_PROXY_EVAL_KEY` identity getter in `edition_eval.py` for Phase 28 judge's proxy calls |
| GOV-02 | 27-01-PLAN.md, 27-03-PLAN.md | Own `agent_registry` + `agent_wallets_v2` rows; `allow_negative=false`, `spending_cap_sats=5000/weekly`, `on_cap_behavior='reject'`, `uncapped=false`; key via `.env`, never in compose | VERIFIED | All wallet governance values confirmed live; compose check = 0; `.env` present; gitignored; committed hash is `$2b$12$` bcrypt (audit record, per 029 precedent) |

---

### Anti-Patterns Found

No debt markers or blocking anti-patterns found in any Phase 27 file.

| File | Pattern | Severity | Finding |
|------|---------|----------|---------|
| `supabase/migrations/045_edition_evals.sql` | TBD/FIXME/XXX/TODO/HACK scan | — | None found |
| `docker/newsletter/edition_eval.py` | TBD/FIXME/XXX/TODO/HACK scan | — | None found |
| `tests/test_27_edition_eval.py` | TBD/FIXME/XXX/TODO/HACK scan | — | None found |

**Advisory only (WR-03, deferred per review):** `read_eval_trend` has no `layer` filter and `limit` counts rows not distinct editions. With `UNIQUE(newsletter_id, layer, attempt)`, one edition can produce multiple rows (2 layers × up to 3 attempts), so `limit=8` may return only 2-4 distinct editions. This is a known advisory with no consumer yet (Phase 31 SURF-03 is the first reader). Deferred intentionally per 27-REVIEW.md — no data loss, no current consumer. Not a blocker for Phase 27's goal.

---

### Human Verification Required

None. All live-DB items (table existence, agent rows, settled proxy call, wallet debit) were pre-confirmed by the orchestrator via MCP queries and are provided as verified facts in the phase submission. All code artifacts are programmatically verifiable and have been verified above.

---

### Gaps Summary

No gaps. All Phase 27 must-haves are verified. The only open item is the SC2 Telegram-alert half, which is explicitly deferred to Phase 30/31 by locked decision D-10 and confirmed by Phase 31 SURF-01 in the ROADMAP. This is a planned phase boundary, not a gap.

The code-review findings CR-01 (wallet ledger corruption on re-apply), WR-01 (numeric-zero verdict bypass), and WR-02 (silent None on empty insert) were all fixed in commit `9e71a49` before this verification — each fix is confirmed present in the production file and covered by the 15-test suite.

---

_Verified: 2026-06-25T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
