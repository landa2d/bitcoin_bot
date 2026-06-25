---
phase: 27-eval-persistence-governed-agent
plan: 02
subsystem: newsletter
tags: [python, supabase, persistence, fail-loud, eval, edition_evals, pytest, fixture-test, governance]

# Dependency graph
requires:
  - phase: 27-eval-persistence-governed-agent
    plan: 01
    provides: "the authoritative edition_evals column contract (JSONB-only, verdict-iff-ok CHECK, UNIQUE(newsletter_id,layer,attempt)) this helper's payload matches exactly"
provides:
  - "docker/newsletter/edition_eval.py — write_eval_row() + read_evals_by_newsletter() + read_eval_trend() + the LLM_PROXY_EVAL_KEY identity getter (no LLM call this phase)"
  - "the fail-loud persistence surface Phases 28/29 import and CALL rather than re-implementing (D-08)"
  - "tests/test_27_edition_eval.py — a 9-case deterministic fixture suite locking the D-09 fail-loud contract + .eq()-only against an in-memory stub"
affects: [27-03 (phase-end requirement closure for EVAL-02/EVAL-03), 28 (deterministic gate writes rows via write_eval_row), 29 (judge writes per-attempt rows + calls the proxy as edition_eval using LLM_PROXY_EVAL_KEY), 30 (sequencer wraps write_eval_row + acts on verdicts), 31 (read_eval_trend powers SURF-03 + the Friday-notify select)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Standalone stdlib-only persistence helper taking `supabase` as the FIRST positional param (no module-global client) — mirrors load_edition_context so the fixture test passes an in-memory stub"
    - "Structural fail-loud in code: verdict-iff-ok validated in Python BEFORE the insert (mirror of the DB edition_evals_verdict_iff_ok CHECK; the stub does not enforce DB CHECKs)"
    - "Fail-LOUD divergence from the poller's fail-SOFT telemetry inserts: insert failure logs ERROR exc_info=True then re-raises — never a bare except, never swallowed (D-09c)"
    - ".eq()-only DB access; the supabase-py in-list filter is used nowhere (EVAL-03); the test stub OMITS it so accidental use raises AttributeError"
    - "Identity separation (D-15): the eval module reads its OWN LLM_PROXY_EVAL_KEY, never the newsletter service's agent key"

key-files:
  created:
    - "docker/newsletter/edition_eval.py"
    - "tests/test_27_edition_eval.py"
  modified: []

key-decisions:
  - "write_eval_row signature: supabase first-positional + keyword-only column contract (identity + status + verdict + loosely-typed JSONB dicts), returns the inserted id (str|None) — Claude's-discretion surface locked per CONTEXT D-08/D-15"
  - "Python verdict-iff-ok validation runs BEFORE the insert and raises ValueError on any (eval_status/verdict/error) mismatch — the in-memory stub can't enforce the DB CHECK, so the helper must (D-09)"
  - "errored evals write eval_status='error' + non-null reason + NULL verdict — never a silent 0; sats_spent=0 is a spend figure, never a verdict/score (D-09 a/b)"
  - "NO caller wired into newsletter_poller.py and NO LLM call this phase (D-08): the helper just exists + is tested; the LLM_PROXY_EVAL_KEY getter is established for the Phase 28 judge but never invoked here"
  - "EVAL-02/EVAL-03 left Pending in REQUIREMENTS.md (not marked complete): EVAL-02's Telegram-delivery half is Phase 30/31 (D-10) and EVAL-03 closes at phase end after 27-03 — consistent with the 27-01 fail-loud-accuracy-over-premature-mark-complete posture"

patterns-established:
  - "edition_eval.py is THE persistence surface: Phases 28/29 import write_eval_row/readers, never re-implement the insert/select/.eq() inline"
  - "fixture test imports the REAL module (test_19_smartquote rule / T-27-08) and asserts against an in-memory Supabase stub — never the live DB/network"

requirements-completed: []  # EVAL-02 (structural half) + EVAL-03 REALIZED IN CODE this plan but left Pending — EVAL-02's Telegram half is Phase 30/31 (D-10); closure deferred to phase end after 27-03 (matches 27-01 posture)

# Metrics
duration: ~12min
completed: 2026-06-25
---

# Phase 27 Plan 02: Eval Persistence Helper + Fixture Test Summary

**Shipped `docker/newsletter/edition_eval.py` — the fail-loud persistence surface both eval layers (Phases 28/29) will write through: a `write_eval_row()` that validates the `verdict-iff-ok` contract in Python BEFORE the insert (errored evals carry `eval_status='error'`+reason+NULL verdict, never a silent zero; an insert failure logs ERROR `exc_info=True` then re-raises, never swallowed), `.eq()`-only `read_evals_by_newsletter()` + `read_eval_trend()` readers (no in-list filter anywhere), and a separate `LLM_PROXY_EVAL_KEY` identity getter for the Phase 28 judge — plus `tests/test_27_edition_eval.py`, a 9-case deterministic fixture suite that imports the REAL module and proves the whole D-09 contract against an in-memory Supabase stub. No LLM calls, no live-path wiring.**

## Performance
- **Duration:** ~12 min
- **Completed:** 2026-06-25
- **Tasks:** 2 (both `type="auto"`; Task 1 `tdd="true"` — TDD mode inactive per config, so built module then its fixture test)
- **Files created:** 2

## Accomplishments
- **`docker/newsletter/edition_eval.py` (176 lines):**
  - `write_eval_row(supabase, *, newsletter_id, edition_number, pipeline_version, attempt, layer, eval_status, verdict=None, error=None, deterministic_flags=None, judge_scores=None, judge_feedback=None, sats_spent=0, model_calls=None) -> str | None` — `supabase` first-positional (no module-global client, mirrors `load_edition_context`). Validates fail-loud BEFORE the insert: `ValueError` if `eval_status` not in `('ok','error')`; `ValueError` unless `(ok ⇒ verdict NOT NULL AND error NULL)` or `(error ⇒ verdict NULL AND error NOT NULL)` — the Python mirror of the DB `edition_evals_verdict_iff_ok` CHECK. Builds the full column payload (defaults `deterministic_flags→{}`, `judge_scores→{}`, `model_calls→[]`), inserts via `.table('edition_evals').insert(payload).execute()`, reads back `result.data[0]['id']`. On insert failure: `logger.error("edition_evals write failed for newsletter_id=%s layer=%s attempt=%s", …, exc_info=True)` then `raise` — DIVERGES from the poller's fail-SOFT telemetry inserts (D-09c / T-27-04). The api key is never logged.
  - `read_evals_by_newsletter(supabase, newsletter_id)` — `.select('*').eq('newsletter_id', …).order('attempt')`, returns `.data or []`.
  - `read_eval_trend(supabase, pipeline_version, limit=8)` — `.select(<9 cols>).eq('pipeline_version', …).order('edition_number', desc=True).limit(limit)`, returns `.data or []`; powers Phase 31's SURF-03.
  - `LLM_PROXY_EVAL_KEY = os.getenv("LLM_PROXY_EVAL_KEY")` + `_get_eval_api_key() -> str | None` — the eval agent's OWN governed identity (D-15) for the Phase 28 judge; NOT invoked this phase, and deliberately does NOT reuse the newsletter service's agent-key resolution.
- **`tests/test_27_edition_eval.py` (261 lines, 9 tests, all green):** imports the REAL `edition_eval` module via a sys.path insert (no conftest preload needed — the module is stdlib-only and takes `supabase` as a param). In-memory `StubSupabase` captures inserted payloads and returns `data=[{'id': …}]`; a separate `RaisingSupabase` drives the loud-raise test; the stub OMITS the in-list filter so accidental use raises `AttributeError`. Proves: ok-row write (returns id; payload `eval_status='ok'`/`verdict='passed'`/`error=None`); error-row-not-silent-zero (`verdict is None`, `verdict != 0`, `sats_spent==0` is a spend not a verdict); three verdict-iff-ok `ValueError` rejections each with no payload captured; loud-raise-on-write-failure (`pytest.raises(RuntimeError)` + ERROR `caplog` naming the failure + `newsletter_id`); `.eq()`-only reads (no in-list filter, `not hasattr(q, 'in_')`); empty-list reads; default JSONB shaping (`{}`/`{}`/`[]`/`None`).

## Task Commits
Each task committed atomically:
1. **Task 1: `docker/newsletter/edition_eval.py` (write_eval_row + readers + identity getter)** — `064db44` (feat)
2. **Task 2: `tests/test_27_edition_eval.py` (9-case deterministic fixture suite)** — `9d9a3fe` (test)

## Files Created/Modified
- `docker/newsletter/edition_eval.py` (created, 176 lines) — fail-loud persistence helper. Imports only stdlib (`logging`, `os`). No reference to the newsletter poller / its agent-key resolution; no LLM client built.
- `tests/test_27_edition_eval.py` (created, 261 lines) — deterministic fixture suite, 9 tests, all green.

## Decisions Made
- **Signature surface (Claude's discretion, CONTEXT D-08):** `supabase` first-positional + keyword-only column contract; returns `str | None` (the read-back id, `None` if the stub/DB returns no rows — honest about the analog's `if result.data else None` shape). The layers' internal flag/score shapes stay loosely-typed dicts passed straight into the JSONB columns.
- **Python verdict-iff-ok mirror (D-09):** validation runs before the insert and raises `ValueError`, because the in-memory test stub (and any pre-DB caller) cannot rely on the DB CHECK to reject a silent-zero/verdict-without-eval row.
- **No live-path wiring, no LLM call (D-08 / phase boundary):** the helper exists + is tested ahead of its first real caller (Phase 28), mirroring the Phase 26 loader-built-ahead-of-judge precedent. `newsletter_poller.py` is untouched.
- **Requirement closure deferred (fail-loud accuracy):** EVAL-02's structural half (loud log + raise, never swallowed) and EVAL-03 (`.eq()`-only, no in-list filter) are realized in code + locked by the fixture suite this plan — but EVAL-02 also requires the Telegram-delivery half, which D-10 explicitly assigns to Phases 30/31 (the newsletter service has no Telegram path; `send_telegram` lives in the Processor). So neither requirement is marked complete in REQUIREMENTS.md yet; both close at phase end after 27-03, consistent with 27-01's posture.

## Deviations from Plan
None — plan executed exactly as written. No deviation rules triggered (no bugs, no missing critical functionality, no blocking issues, no architectural changes; no package installs; no LLM calls; no migration apply).

## Threat-Model Coverage
All four `mitigate` dispositions in the plan's threat register are realized + test-proven; no new security surface beyond the plan's threat model was introduced.
- **T-27-04 (silent data loss):** insert failure logs ERROR `exc_info=True` + re-raises → `test_write_failure_logs_error_and_reraises`.
- **T-27-05 (silent-zero):** errored rows carry `eval_status='error'`+reason+NULL verdict; `ValueError` on any mismatch before insert → `test_error_row_is_an_error_state_not_a_silent_zero` + the three rejection tests.
- **T-27-06 (api-key disclosure):** `LLM_PROXY_EVAL_KEY` is read but NEVER logged; the ERROR line names only `newsletter_id/layer/attempt`.
- **T-27-07 (.in_ silent-failure):** `.eq()`-only across the module (grep gate = 0); the stub omits the in-list filter so accidental use raises `AttributeError`.
- **T-27-08 (test re-implements the helper):** the suite imports the REAL `edition_eval` module (grep asserts `import edition_eval`).

## Verification
Both plan `<verify><automated>` gates return **PASS** against the live files:
- **Task 1 gate:** `ast.parse` OK; `def write_eval_row(` count = 1; `\.in_(` count = 0; `exc_info=True` present; `LLM_PROXY_EVAL_KEY` present; `_get_agent_api_key|newsletter_poller` count = 0 → **PASS**. (Also confirmed: both readers present, `AGENT_NAME` count = 0, 176 lines > 70 min_lines.)
- **Task 2 gate:** `pytest tests/test_27_edition_eval.py` exits 0 (**9 tests**, ≥ 6); `import edition_eval` present; `pytest.raises(ValueError)` present; `caplog` present; `def in_` count = 0 → **PASS**.
- **Regression smoke (`python3 -m pytest tests/`):** the new module + test are import-isolated and green. Pre-existing/environmental failures unrelated to this plan: `tests/test_llm_proxy.py` + `tests/test_1d_radar_section.py` + `tests/test_4b_prediction_monitoring.py` error on missing `uvicorn`/`anthropic` deps (this env), and `tests/test_newsletter_quality.py::test_resolved_predictions_not_flagged` (the tracked P2 analyst-predictions bug) + `tests/test_schemas.py::TestProactiveAnalysisInput` assertion failures reproduce at the parent commit and reference none of my files (additive-only change: `git diff` touches only the 2 new files). Out of scope per the executor scope boundary.

## Self-Check: PASSED
- `docker/newsletter/edition_eval.py` — FOUND
- `tests/test_27_edition_eval.py` — FOUND
- Commit `064db44` (Task 1) — FOUND in git log
- Commit `9d9a3fe` (Task 2) — FOUND in git log

## User Setup Required
None for this plan. (The `edition_eval` key mint + `config/.env` `LLM_PROXY_EVAL_KEY` delivery + MCP migration-045 apply + settled-proxy-call verify happen in plan 27-03 — worktree-unsafe, `autonomous: false`, orchestrator/operator-owned.)

## Next Phase Readiness
- The fail-loud persistence surface is locked + test-proven, so **plan 27-03** can mint the key, substitute the real bcrypt hash into 045 SECTION 2, MCP-apply, and verify a settled `edition_eval` proxy call — then run the phase-end requirement-closure pass (EVAL-01/EVAL-02/EVAL-03/GOV-01/GOV-02).
- **Phase 28** can import `write_eval_row` (deterministic-layer rows) and **Phase 29** can import it + the readers and call the proxy under `LLM_PROXY_EVAL_KEY` — none of them re-implement persistence (D-08).
- Reminder (carried from D-15 / PATTERNS "No Analog"): when Phases 28/29 add LLM calls, build a dedicated proxy-pointed client keyed on `LLM_PROXY_EVAL_KEY` (Sonnet via `/anthropic`, DeepSeek via `/v1`) — do NOT reuse the newsletter service's direct `deepseek_client` or its agent identity.

---
*Phase: 27-eval-persistence-governed-agent*
*Completed: 2026-06-25*
