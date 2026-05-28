---
phase: 05-intake-classifier-unsorted-handling
plan: 01
subsystem: api
tags: [llm-proxy, deepseek, postgrest, economy_map, classifier, httpx]

# Dependency graph
requires:
  - phase: 02-economy-map-schema-seven-block-seed
    provides: economy_map.timeline_entries table, append-only trigger, 'unsorted' validity, seven block slugs
provides:
  - config-driven intake_classifier.confidence_floor (0.6) + enabled flag (D-06)
  - economy_map_insert_timeline_entry() PostgREST INSERT helper (Content-Profile: economy_map)
  - economy_map_edition_already_emitted() PostgREST existence-check helper (Accept-Profile: economy_map, D-08)
  - INTAKE_CLASSIFIER_PROMPT + INTAKE_CLASSIFIER_SYSTEM_MSG (classify-only, anti-prompt-injection)
  - classify_intake_event() proxy-routed DeepSeek classifier returning {block_slug, tag_confidence} (INTK-02)
affects: [05-02 intake poller, 05-03 verification tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "economy_map PostgREST access from Python via httpx with Content-Profile/Accept-Profile headers (first in-tree Python analog)"
    - "Proxy-routed LLM call: HTTP POST to LLM_PROXY_URL/v1/chat/completions with processor agent key, distinct from SDK-direct routed_llm_call"

key-files:
  created:
    - tests/test_05a_intake_classifier.py
  modified:
    - config/agentpulse-config.json
    - docker/processor/agentpulse_processor.py

key-decisions:
  - "Built the classifier call against LLM_PROXY_URL (httpx POST) rather than routed_llm_call, because routed_llm_call calls provider SDKs directly and cannot produce the proxy-side evidence ROADMAP criterion 2 requires"
  - "Scoped the economy_map helpers to timeline_entries only (no generic schema-agnostic writer) per threat T-05-02"
  - "Classifier raises on all failures (no internal 'unsorted' fallback) — Plan 02 owns the D-05 unsorted routing"

patterns-established:
  - "Pattern 1: economy_map writes/reads from the processor use direct httpx PostgREST with the schema-profile header and SUPABASE_SERVICE_KEY, never supabase-py .schema()/.in_()"
  - "Pattern 2: governed LLM calls that must leave proxy-side evidence go through LLM_PROXY_URL/v1/chat/completions with the agent key, not the SDK dispatcher"

requirements-completed: [INTK-02]

# Metrics
duration: ~25min
completed: 2026-05-28
---

# Phase 5 Plan 01: Intake Classifier Contracts Summary

**Config-driven 0.6 confidence floor, two timeline_entries PostgREST helpers (Content/Accept-Profile economy_map), and a proxy-routed DeepSeek classify_intake_event() returning {block_slug, tag_confidence} — the three fixed contracts Plans 02/03 build against.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-28T18:12Z
- **Completed:** 2026-05-28T18:20Z
- **Tasks:** 3
- **Files modified:** 3 (2 modified, 1 created)

## Accomplishments
- Added `intake_classifier` config section (`enabled: true`, `confidence_floor: 0.6`) — the D-06 tunable floor readable without redeploy.
- Built the first in-tree Python `economy_map` write/read path: `economy_map_insert_timeline_entry()` (INSERT, `Content-Profile: economy_map`, `Prefer: return=representation`, raises on non-2xx) and `economy_map_edition_already_emitted()` (existence check, `Accept-Profile: economy_map`, returns bool — the D-08 idempotency primitive), both scoped to `timeline_entries`, using `SUPABASE_SERVICE_KEY` and httpx, no supabase-py `.schema()`/`.in_()`.
- Added `INTAKE_CLASSIFIER_PROMPT` / `INTAKE_CLASSIFIER_SYSTEM_MSG` (classify-only output, anti-prompt-injection framing per T-05-01) and `classify_intake_event()` which POSTs to `{LLM_PROXY_URL}/v1/chat/completions` with the processor agent key and `deepseek-chat` (INTK-02), returns the parsed `{block_slug, tag_confidence}` on 2xx, and raises on any failure (no internal unsorted fallback).
- Added a standalone test (`tests/test_05a_intake_classifier.py`, 6 tests) proving proxy routing, fence-wrapped JSON parsing, and the raise-on-failure contract.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add config-driven confidence floor (D-06)** - `4e5085c` (feat)
2. **Task 2: economy_map PostgREST helpers (insert + existence-check)** - `119537d` (feat)
3. **Task 3 (TDD): proxy-routed DeepSeek classifier + prompt constant (INTK-02)**
   - `b4a322e` (test — RED gate)
   - `cdb42d9` (feat — GREEN gate)

_Plan metadata commit (this SUMMARY) follows._

## Files Created/Modified
- `config/agentpulse-config.json` - Added top-level `intake_classifier` section (`enabled`, `confidence_floor: 0.6`).
- `docker/processor/agentpulse_processor.py` - Added two `economy_map` PostgREST helpers, `INTAKE_CLASSIFIER_PROMPT` + `INTAKE_CLASSIFIER_SYSTEM_MSG`, and `classify_intake_event()`.
- `tests/test_05a_intake_classifier.py` - New: 6 unit tests for the classifier's proxy routing, JSON parsing, and failure-raising behavior.

## Decisions Made
- **Proxy HTTP path over `routed_llm_call`:** The plan (and PATTERNS open item 4a) flagged that `routed_llm_call()` calls provider SDKs directly and so cannot satisfy ROADMAP criterion 2 ("verified by proxy-side evidence"). The classifier therefore POSTs to `{LLM_PROXY_URL}/v1/chat/completions` with the processor agent key — the proxy stamps `X-Proxy-Request-Id`/`X-Proxy-Agent` and records a `wallet_transactions` row, which is the required evidence.
- **Helpers scoped to `timeline_entries` only:** No generic schema-agnostic writer, keeping the service_role write surface tight (threat T-05-02). No UPDATE/DELETE helper (append-only stays trigger-enforced).
- **Classifier raises, never falls back:** Per D-05, the unsorted routing (below-floor → unsorted; error → unsorted with NULL confidence) is Plan 02's job. The classifier surfaces failures so Plan 02's per-event handler can route them.

## Deviations from Plan

None - plan executed exactly as written. (The `classify_intake_event` docstring mentions the words "routed_llm_call" and "unsorted" in explanatory prose stating they are NOT used; both are absent from the executable body, confirmed via AST-level grep of the function body excluding the docstring.)

## TDD Gate Compliance
Task 3 (`tdd="true"`) followed RED → GREEN:
- RED: `test(05-01)` commit `b4a322e` — tests fail because `classify_intake_event`/`INTAKE_CLASSIFIER_PROMPT` do not exist.
- GREEN: `feat(05-01)` commit `cdb42d9` — implementation added; all 6 tests pass.
- No REFACTOR commit needed (function is minimal and mirrors the established `MULTISOURCE_EXTRACTION_PROMPT` pattern).

## Issues Encountered
- **pytest not installed / `schedule` + `tweepy` missing in this environment:** The test was written to run standalone (`python3 tests/test_05a_intake_classifier.py`) and stubs the missing module-level imports, mirroring the live-harness shape from `test_phase2_integration.py`. It also primes `proc._model_config_cache` from the repo's `config/agentpulse-config.json` so `get_model('extraction')` resolves to `deepseek-chat` exactly as in the deployed processor (which reads a hardcoded `/home/openclaw/...` path absent here). All 6 tests pass.

## User Setup Required
None - no external service configuration required. (Runtime exercise of `classify_intake_event` and the PostgREST helpers requires the deployed processor with `SUPABASE_URL`/`SUPABASE_SERVICE_KEY`/`AGENT_API_KEY` env and the llm-proxy reachable — these already exist in the deployed environment.)

## Next Phase Readiness
- Plan 02 (intake poller) can now: read the floor via `get_full_config().get("intake_classifier", {}).get("confidence_floor", 0.6)`, call `classify_intake_event(event, allowed_slugs)`, use `economy_map_edition_already_emitted(edition_id)` for the D-08 pre-emit skip, and `economy_map_insert_timeline_entry(entry)` for the write. All four contracts are fixed.
- No blockers. The classifier's allowed-slug list is supplied by the caller (Plan 02 fetches the seven slugs from `economy_map.blocks` or hard-lists them).

## Self-Check: PASSED

---
*Phase: 05-intake-classifier-unsorted-handling*
*Completed: 2026-05-28*
