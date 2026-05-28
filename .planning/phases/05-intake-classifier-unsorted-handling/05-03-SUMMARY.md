---
phase: 05-intake-classifier-unsorted-handling
plan: 03
subsystem: tests
tags: [tests, economy_map, timeline_entries, append-only, intake, classifier, postgrest, llm-proxy]

# Dependency graph
requires:
  - phase: 05-intake-classifier-unsorted-handling
    plan: 01
    provides: economy_map_insert_timeline_entry(), classify_intake_event(), INTAKE_BLOCK_SLUGS_FALLBACK, intake_classifier.confidence_floor
  - phase: 05-intake-classifier-unsorted-handling
    plan: 02
    provides: classify_intake_for_edition() route decision (floor compare + D-05 unsorted routing)
  - phase: 02-economy-map-schema-seven-block-seed
    provides: economy_map.timeline_entries append-only trigger (migration 033)
provides:
  - tests/test_05_intake.py — machine-verifiable proofs of INTK-05 (append-only), criterion 3 (below-floor routing), D-05 (error → NULL confidence), criterion 2 / SC-2 (proxy-routing evidence)
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Standalone test (no pytest) mirroring tests/test_05a_intake_classifier.py: stubs heavy imports, primes _model_config_cache, _run_all() prints PASS/SKIP/FAIL"
    - "Structural append-only proof: assert the migration-033 trigger SQL rejects UPDATE/DELETE (mirrors tests/test_migrations.py text-assertion style) — non-destructive, no live mutation"
    - "Offline route-decision test: monkeypatch classify_intake_event + economy_map_edition_already_emitted + economy_map_insert_timeline_entry to capture the INSERT payload built by Plan 02's classify_intake_for_edition"

key-files:
  created:
    - tests/test_05_intake.py
  modified: []

key-decisions:
  - "Test A (append-only) proven STRUCTURALLY by default (migration-033 trigger-text assertion) instead of a live INSERT→UPDATE→DELETE — this host is production and the operator preferred not mutating the shared append-only timeline_entries table; the live UPDATE/DELETE-fail check is opt-in behind INTK05_LIVE_DB=1"
  - "Tests B/C call Plan 02's classify_intake_for_edition (the route decision lives there) and capture the INSERT payload via a monkeypatched economy_map_insert_timeline_entry — fully offline, no secrets needed"
  - "Test D uses the durable DB-evidence substitute (wallet_transactions increment for the processor agent) for proxy-routing proof, because classify_intake_event does not surface response headers to its caller; skips cleanly when the proxy/agent-key are absent"

patterns-established:
  - "Append-only guarantees can be regression-guarded structurally (migration SQL assertion) when a live mutation attempt is unsafe on a production append-only table"

requirements-completed: [INTK-05]

# Metrics
duration: ~30min
completed: 2026-05-28
---

# Phase 5 Plan 03: Intake Spine Guarantee Tests Summary

**One standalone test file (`tests/test_05_intake.py`) that machine-verifies the three spine guarantees Phase 5 must uphold: the economy_map.timeline_entries append-only trigger rejects UPDATE and DELETE (INTK-05 / criterion 5), a below-floor classification routes to `'unsorted'` with recorded confidence and a classifier error routes to `'unsorted'` with NULL confidence via Plan 02's `classify_intake_for_edition` (criterion 3 / D-05), and a live classification carries durable proxy-routing evidence via Plan 01's `classify_intake_event` (criterion 2 / SC-2) — all passing or skipping cleanly without secrets, with no production mutation.**

## Performance
- **Duration:** ~30 min
- **Tasks:** 1
- **Files modified:** 1 (created)

## Accomplishments
- **Test A — append-only (INTK-05 / criterion 5):** `test_append_only_trigger_rejects_update_and_delete` asserts the migration-033 SQL defines `economy_map.timeline_entries_append_only()` raising on `DELETE` and on each pinned content-column `UPDATE` (`block_slug`, `event_date`, `what_shifted`, `why_it_mattered`, `source_url`, `source_edition_id`, `tag_confidence`), wired `BEFORE UPDATE OR DELETE ON economy_map.timeline_entries`. This is the structural mitigation for threat T-05-10 (a future "simplify to RLS" regression fails this assertion). A second test, `test_append_only_live_update_and_delete_fail`, attempts a real UPDATE+DELETE against an existing row and asserts both 4xx — opt-in behind `INTK05_LIVE_DB=1` (default skip; non-destructive because the BEFORE trigger rejects before any mutation).
- **Test B — below-floor routing (criterion 3):** `test_below_floor_routes_to_unsorted_with_recorded_confidence` stubs `classify_intake_event` to return a valid named slug at `floor − 0.2`, calls Plan 02's `classify_intake_for_edition`, and asserts the captured INSERT payload has `block_slug == 'unsorted'` with the exact recorded `tag_confidence` (flagged-not-dropped, D-07 below-floor slug not persisted).
- **Test C — error-path NULL confidence (D-05):** `test_classifier_error_routes_to_unsorted_with_null_confidence` stubs `classify_intake_event` to raise, asserts exactly one INSERT with `block_slug == 'unsorted'`, `tag_confidence is None`, and the event content (`what_shifted`, `source_edition_id`) preserved — proving an event is never silently dropped on classifier failure.
- **Test D — proxy-routing evidence (criterion 2 / SC-2):** `test_live_classifier_leaves_proxy_routing_evidence` reads the processor agent's `wallet_transactions` count before/after a live `classify_intake_event` through `http://llm-proxy:8200`, polling for the increment (the proxy's `async_log_transaction` batched write). Promotes SC-2 from operator-verified to machine-verifiable; skips cleanly when SUPABASE/agent-key/proxy secrets are absent.
- File runs standalone (`python3 tests/test_05_intake.py`) — pytest is not installed and the host is PEP-668 externally-managed — and is also pytest-collectable (the skip helper uses `pytest.skip` under pytest, a `_Skip` exception standalone).

## Task Commits
1. **Task 1: Author the append-only + confidence-routing + proxy-routing-evidence tests** — `56edb32` (test)

_Plan metadata commit (this SUMMARY) follows._

## Files Created/Modified
- `tests/test_05_intake.py` — New: 5 test functions (structural append-only, opt-in live append-only, below-floor routing, error-path NULL, live proxy evidence) + standalone `_run_all()` runner. No production-code or migration change.

## Decisions Made
- **Structural append-only proof as the default (vs live INSERT→UPDATE→DELETE):** The plan's Test A described inserting a throwaway `timeline_entries` row then attempting UPDATE/DELETE. This host IS production and the `<db_safety>` directive plus the project memory (structural-over-application enforcement) prefer not mutating the shared, append-only, never-deletable `timeline_entries` table. The append-only trigger fires `BEFORE UPDATE OR DELETE` and RAISEs, so the guarantee is fully provable from the migration SQL without any live write. The live UPDATE/DELETE-fail attempt is preserved but gated behind `INTK05_LIVE_DB=1` (default skip, non-destructive since the trigger blocks the op before mutation). This satisfies the criterion-5 acceptance gate while honoring the production-safety constraint. **(Deviation — see below.)**
- **Tests B/C capture the INSERT payload (Option B-preferred from the plan):** `classify_intake_for_edition` returns a counts dict, not the routed entries, so the test monkeypatches `economy_map_insert_timeline_entry` to record the exact dict the poller builds — keeping Tests B/C offline and asserting on the real route decision, not a re-implementation.
- **Test D uses wallet_transactions DB evidence (the plan's durable substitute):** `classify_intake_event` returns only the parsed `{block_slug, tag_confidence}` dict; it does not expose the `X-Proxy-Request-Id` response header to its caller. Per the plan's stated fallback, Test D asserts the durable `wallet_transactions` increment instead.

## Deviations from Plan

### Auto-fixed / safety-driven adjustments

**1. [Rule 2 / db_safety - production-safety] Test A proven structurally by default; live UPDATE/DELETE made opt-in**
- **Found during:** Task 1 verification run.
- **Issue:** The plan's Test A inserts a throwaway row into the live, append-only, never-deletable `economy_map.timeline_entries` (a production table on this host), then attempts UPDATE/DELETE. The `<db_safety>` directive and project memory ("structural over application enforcement") caution against live production mutation; the inserted row would be permanent (DELETE is blocked by the very trigger under test), and even the UPDATE/DELETE *attempts* are mutations against a shared prod table.
- **Fix:** Default Test A (`test_append_only_trigger_rejects_update_and_delete`) proves the guarantee structurally by asserting the migration-033 trigger SQL rejects DELETE and content-column UPDATE (mirrors `tests/test_migrations.py` style) — zero DB access, zero mutation, and a genuine regression guard for T-05-10. The live INSERT was dropped entirely (no marker row is ever written). The live UPDATE/DELETE-fail check (`test_append_only_live_update_and_delete_fail`) is retained against an *existing* row, gated behind `INTK05_LIVE_DB=1` (default skip), and is itself non-destructive (the BEFORE trigger aborts the op before any change).
- **Why this still satisfies the plan:** The plan's acceptance criterion is "a test asserts an UPDATE of `what_shifted` on a `timeline_entries` row FAILS and a DELETE FAILS — INTK-05 / criterion 5." The structural test asserts exactly the trigger that produces those failures (the `... is append-only` RAISEs on DELETE and content UPDATE), and the opt-in live test asserts the runtime 4xx. INTK-05 / criterion 5 is proven; no production data is touched by default.
- **Files modified:** `tests/test_05_intake.py`
- **Commit:** `56edb32`

## Verification Performed
- `python3 -c "import ast; ast.parse(open('tests/test_05_intake.py').read())"` — exits 0.
- `python3 tests/test_05_intake.py` (run from the worktree) — **3 passed, 2 skipped, 0 failed** (exit 0):
  - PASS `test_append_only_trigger_rejects_update_and_delete` (structural INTK-05).
  - SKIP `test_append_only_live_update_and_delete_fail` (opt-in `INTK05_LIVE_DB=1` not set).
  - PASS `test_below_floor_routes_to_unsorted_with_recorded_confidence` (criterion 3).
  - PASS `test_classifier_error_routes_to_unsorted_with_null_confidence` (D-05).
  - SKIP `test_live_classifier_leaves_proxy_routing_evidence` (proxy `llm-proxy:8200` unreachable from host / no agent key — clean skip, no proxy call made).
- Acceptance-criteria greps: `classify_intake_for_edition` = 5 (≥1), `X-Proxy-Request-Id|wallet_transactions` = 10 (≥1), `skip` = 16 (≥1), `.schema(` = 0, `.in_(` = 0, artifact `contains: "append_only"` present.
- No production-code, config, or migration file modified (only `tests/test_05_intake.py` created).

## pytest-vs-standalone note
The plan's `<verify>` block names `python3 -m pytest tests/test_05_intake.py -v`, but pytest is NOT installed in this environment and the host is PEP-668 externally-managed (cannot `pip install`). Per the `<testing_convention>` directive (which overrides), the file runs standalone via `python3 tests/test_05_intake.py` with a `_run_all()` PASS/SKIP/FAIL runner, mirroring `tests/test_05a_intake_classifier.py`. It remains pytest-collectable (skip helper detects pytest), so the plan's command would also work if pytest were present.

## Issues Encountered
- **Initial Write landed in the main repo, not the worktree:** the first `Write` used an absolute path under `/root/bitcoin_bot/tests/` which resolves to the main checkout, not the worktree root (#3099). Detected via `git status` showing the file as untracked in the main repo while empty in the worktree; the file was moved into the worktree (`tests/test_05_intake.py`), re-run there (3 passed / 2 skipped), and committed on the per-agent branch. No main-repo commit was made.

## Threat Surface Scan
No new security-relevant surface. The test only reads a local migration SQL file (Test A default), monkeypatches in-process functions (Tests B/C), and — only when live secrets exist — reads `wallet_transactions` and (opt-in) attempts a rejected UPDATE/DELETE. It mitigates T-05-10 (append-only regression) and T-05-12 (proxy-bypass regression) as machine checks.

## Self-Check: PASSED

---
*Phase: 05-intake-classifier-unsorted-handling*
*Completed: 2026-05-28*
