# Phase 28 — Deferred / Out-of-Scope Items

Discovered during execution; NOT fixed (out of this phase's scope per the executor scope boundary).

## Pre-existing test-suite failures (environment / live-DB, unrelated to Phase 28)

Observed when running the full `tests/` suite. None import `deterministic_gate` (a brand-new
standalone module with no wiring this phase, D-05), so none are caused by Phase 28. They are
environmental gaps in this execution host:

| Test(s) | Cause | Category |
|---------|-------|----------|
| `tests/test_llm_proxy.py` (collection error) | `ModuleNotFoundError: uvicorn` | missing dev package |
| `tests/test_1d_radar_section.py`, `tests/test_4b_prediction_monitoring.py` (collection errors) | missing deps / import-time setup | missing dev package |
| `tests/test_3c_newsletters.py::test_run_1/2/3` | `NoneType.rpc` / postgrest `APIError` (no live Supabase) | needs live DB |
| `tests/test_newsletter_quality.py::test_run_quality_checks_clean_newsletter`, `::test_resolved_predictions_not_flagged` | pre-existing quality-check assertions | pre-existing |
| `tests/test_schemas.py::TestProactiveAnalysisInput::*` | pydantic `ValidationError` (schema drift) | pre-existing |
| conftest warning: `could not pre-import research_agent: No module named 'anthropic'` | missing `anthropic` package | missing dev package |

The Phase 28 plan's regression gate (`tests/test_26_continuity_loader.py`,
`tests/test_27_edition_eval.py`) plus the new `tests/test_28_deterministic_gate.py` are all
green (40/40). Recommend a separate environment-hardening / pre-existing-test pass — out of
scope for the v2.3 eval milestone.
