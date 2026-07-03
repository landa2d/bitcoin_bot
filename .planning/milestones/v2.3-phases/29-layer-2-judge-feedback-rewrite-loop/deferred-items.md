# Phase 29 — Deferred / Out-of-Scope Items

Discovered during execution of plans 29-02 / 29-03. These are PRE-EXISTING and UNRELATED to the
Layer-2 judge/loop work (none of these test files import `judge_loop` — grep-verified: the ONLY
file importing `judge_loop` is `tests/test_29_judge_loop.py`). Logged per the SCOPE BOUNDARY rule
— NOT fixed in this plan.

## Pre-existing full-`tests/` suite failures (unrelated to Phase 29)

Root causes are missing optional test-env packages, unset runtime env vars, and unrelated
code/schema drift. This plan's changes touched ONLY `docker/newsletter/judge_loop.py` +
`tests/test_29_judge_loop.py` (an isolated NEW module + its test), so none of these can be a
regression from this plan. The 29-02 table (collection errors + schema/quality drift) was captured
when `pytest tests/` INTERRUPTED at the first collection error; running with
`--continue-on-collection-errors` at 29-03 surfaces the fuller landscape (all env/integration).

| Test file | Symptom | Root cause | Owner |
|-----------|---------|------------|-------|
| `tests/test_llm_proxy.py` | collection ERROR | `ModuleNotFoundError: No module named 'uvicorn'` (proxy import) — pkg not installed in this test env | env / infra |
| `tests/test_1d_radar_section.py` | collection ERROR (5) | `ModuleNotFoundError: No module named 'anthropic'` — pkg not installed in test env (RESEARCH already notes `anthropic` absent here, by design) | env / infra |
| `tests/test_4b_prediction_monitoring.py` | ERROR (2) | import/collection error (same env class) | env / infra |
| `tests/test_schemas.py::TestProactiveAnalysisInput` | 2 failed | `pydantic ValidationError` — schema/model drift unrelated to newsletter eval | backend |
| `tests/test_newsletter_quality.py` | 2 failed | quality-check assertion drift (`assert 7 == 0`, `assert 2 == 1`) — pre-existing, not judge_loop | backend |
| `tests/test_05_intake.py::test_live_classifier_leaves_proxy_routing_evidence` | 1 failed | `RuntimeError: OPENAI_BASE_URL / DEEPSEEK...` — needs proxy env vars set at runtime | env / infra |
| `tests/test_07_synthesis.py::test_sonnet_call_routes_through_anthropic_messages` | 1 failed | model-routing assertion (`claude-s...`) — live-routing integration test | env / infra |
| `tests/test_1a_source_ingestion.py` | 3 failed | `AttributeError: module 'agentpulse_processor' has no attribute 's...'` — processor module drift | backend |
| `tests/test_3c_newsletters.py` | 3 failed | `AttributeError: 'NoneType' object has no attribute 'rpc'` / postgrest `APIError: column p...` — needs a live Supabase connection | env / infra |

Full-suite tally at 29-03 tip (`--continue-on-collection-errors`): **12 failed, 401 passed, 1
skipped, 8 errors** — every failure/error is in the table above (env/integration/drift), none in a
`judge_loop`-importing module.

**In-scope suites for this plan — all GREEN:**
- `tests/test_29_judge_loop.py` → 28 passed (19 from 29-01/02 + 3 D-01/02/03 re-check + 6 telemetry/mechanical/golden)
- `tests/test_26_continuity_loader.py tests/test_27_edition_eval.py tests/test_28_deterministic_gate.py` → 104 passed

These pre-existing failures are candidates for the later backend-hardening / test-env pass
already tracked in STATE.md; not part of the v2.3 eval milestone scope.
