# Phase 29 — Deferred / Out-of-Scope Items

Discovered during execution of plan 29-02. These are PRE-EXISTING and UNRELATED to the
Layer-2 judge/loop work (none of these test files import `judge_loop`). Logged per the
SCOPE BOUNDARY rule — NOT fixed in this plan.

## Pre-existing full-`tests/` suite failures (unrelated to Phase 29)

Confirmed at commit `df86805` (this plan's tip); root causes are missing optional test-env
packages and unrelated code/schema drift. My changes touched only
`docker/newsletter/judge_loop.py` + `tests/test_29_judge_loop.py`.

| Test file | Symptom | Root cause | Owner |
|-----------|---------|------------|-------|
| `tests/test_llm_proxy.py` | collection ERROR | `ModuleNotFoundError: No module named 'uvicorn'` (proxy import) — pkg not installed in this test env | env / infra |
| `tests/test_1d_radar_section.py` | collection ERROR (5) | `ModuleNotFoundError: No module named 'anthropic'` — pkg not installed in test env (RESEARCH already notes `anthropic` absent here, by design) | env / infra |
| `tests/test_4b_prediction_monitoring.py` | ERROR (2) | import/collection error (same env class) | env / infra |
| `tests/test_schemas.py::TestProactiveAnalysisInput` | 2 failed | `pydantic ValidationError` — schema/model drift unrelated to newsletter eval | backend |
| `tests/test_newsletter_quality.py` | 2 failed | quality-check assertion drift (`assert 7 == 0`, `assert 2 == 1`) — pre-existing, not judge_loop | backend |

**In-scope suites for this plan — all GREEN:**
- `tests/test_29_judge_loop.py` → 19 passed
- `tests/test_26_continuity_loader.py tests/test_27_edition_eval.py tests/test_28_deterministic_gate.py` → 104 passed

These pre-existing failures are candidates for the later backend-hardening / test-env pass
already tracked in STATE.md; not part of the v2.3 eval milestone scope.
