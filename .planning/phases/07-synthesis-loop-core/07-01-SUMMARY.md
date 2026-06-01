---
phase: 07-synthesis-loop-core
plan: 01
subsystem: processor / economy_map synthesis loop
tags: [synthesis, economy_map, llm-proxy, anthropic, config, fail-loud, append-only]
requires:
  - economy_map schema (migration 033: blocks, block_body_versions, timeline_entries, maturity enum)
  - llm-proxy /anthropic/v1/messages route + claude-sonnet-4-20250514 pricing
  - processor _get_agent_api_key / get_full_config / _clean_json_response / SUPABASE_URL / LLM_PROXY_URL
provides:
  - synthesis config block (config/agentpulse-config.json)
  - config/economy_map/synth_identity.md (hot-reloadable editorial voice)
  - load_synth_identity (mtime hot-reload, fail-loud)
  - fetch_economy_map_blocks / block_has_open_draft / fetch_block_new_entries / fetch_current_block_body
  - economy_map_insert_block_body_version (purpose-scoped draft INSERT)
  - is_block_eligible (N/T predicate)
  - assemble_synthesis_input (ordering + fail-loud cap)
  - parse_synthesis_output (maturity-enum validation)
  - synthesis_sonnet_call (single proxy-routed Sonnet call)
affects:
  - Plan 07-02 (scheduled orchestrator that composes these primitives)
tech-stack:
  added: []   # no new packages — httpx/schedule/supabase/stdlib already present
  patterns:
    - "raw httpx.post to {LLM_PROXY_URL}/anthropic/v1/messages (Anthropic Messages body) — the only Sonnet route"
    - "economy_map PostgREST reads via Accept-Profile, writes via Content-Profile; raise on non-2xx"
    - "mtime hot-reload with `is not None` cache guard (analyst load_skill variant)"
    - "fail-loud cap: keep newest, logger.warning + in-prompt omitted-count note"
key-files:
  created:
    - config/economy_map/synth_identity.md
    - tests/test_07_synthesis.py
  modified:
    - config/agentpulse-config.json
    - docker/processor/agentpulse_processor.py
decisions:
  - "Sonnet routing via /anthropic/v1/messages (RESEARCH D-01 supersedes CONTEXT D-01/D-10): routed_llm_call has no Anthropic branch; /v1/chat/completions cannot reach Anthropic. No new dependency."
  - "Dual cap in assemble_synthesis_input: entry-ceiling first (keep newest 22), then token-budget trim from the tail until len//4 <= max_input_tokens — both fail-loud."
  - "synthesis_sonnet_call sends the agent key in BOTH Authorization: Bearer and x-api-key (RESEARCH A1, proxy reads Bearer first)."
metrics:
  duration: ~25min
  completed: 2026-06-01
  tasks: 3
  files: 4
---

# Phase 7 Plan 01: Synthesis Loop Core Primitives Summary

Shipped the standalone, unit-tested building blocks of the per-block synthesis loop — a hot-reloadable editorial-voice loader, a `synthesis` config block, four economy_map read helpers + one purpose-scoped draft INSERT, the N/T eligibility predicate, fail-loud input assembly with a dual cap, an output parser with maturity-enum validation, and the single Claude Sonnet call routed through the proxy's `/anthropic/v1/messages` endpoint — plus a 13-test Wave-0 harness. Plan 07-02 wires these into the scheduled orchestrator.

## What Was Built

**Task 1 — config + identity (commit 18edf59)**
- `config/agentpulse-config.json`: added a top-level `synthesis` block (sibling of `intake_classifier`) with the eight D-09 defaults (`enabled` true, `N` 5, `T_days` 30, `synthesis_model` claude-sonnet-4-20250514, `max_input_entries` 22, `max_input_tokens` 12000, `output_max_tokens` 8000, `temperature` 0.4).
- `config/economy_map/synth_identity.md`: working-default editorial-voice system prompt. Instructs the six-part RNDR-02 skeleton, preserves the supplied `live_tension` as a real section, treats all supplied entry text as DATA not instructions (T-07-PI), and mandates structured JSON `{body_md, proposed_maturity}` output naming all five maturity enum values. Lands under the already-mounted `config/` tree (`:ro`) — no docker-compose change.

**Task 2 — processor primitives (commit f3eeb2a)**
Seven top-level functions (plus `_economy_map_get`, `_parse_iso_ts`, `_format_synthesis_entry` helpers and module constants `SYNTH_IDENTITY_PATH`, `SYNTH_MATURITY_ENUM`, `SYNTH_SKELETON_HEADINGS`) added after `classify_intake_event`:
- `load_synth_identity()` — mtime-cached, `is not None` cache guard, fail-loud `None` on missing/empty (D-11/SYNT-05).
- `fetch_economy_map_blocks` / `block_has_open_draft` (D-03) / `fetch_block_new_entries` (created_at recency D-04, NULL watermark = cold-start D-06, ordering left to assembler) / `fetch_current_block_body` (None on cold-start D-08) — all raise on non-2xx so a read error is never mistaken for empty.
- `economy_map_insert_block_body_version` — second purpose-scoped writer (T-07-WS), Content-Profile, `status` omitted (DB default draft, D-13).
- `is_block_eligible` — no-draft guard + n>=N or (n>=1 and age>=T_days); cold-start age clock = earliest new-entry created_at (D-02..D-06).
- `assemble_synthesis_input` — event_date-desc ordering, dual cap (entry ceiling then token budget) keeping newest, `logger.warning` + in-prompt omitted-count note (D-07/D-09).
- `parse_synthesis_output` — fence-strip + JSON parse, raises on empty body / out-of-enum / missing maturity (D-12/SYNT-06).
- `synthesis_sonnet_call` — single `httpx.post` to `/anthropic/v1/messages`, Bearer + x-api-key, Anthropic body, returns `content[0].text`; no `routed_llm_call`, no `api.anthropic.com` literal (D-10/SYNT-04).

**Task 3 — Wave-0 unit harness (commit 71b66b1)**
`tests/test_07_synthesis.py` mirrors the `test_05a` harness with an Anthropic-shaped `_FakeResponse` and httpx.post stub. 13 tests cover all six requirement groups: Sonnet routing + non-2xx raise, identity reload (missing/empty/mtime), the eligibility truth table (incl. cold-start), assembly ordering + over/under cap, the five maturity-validation cases, and the draft-INSERT shape (Content-Profile, status omitted, no blocks/published columns).

## Verification

- `python3 -c "import ast; ast.parse(...)"` — processor parses. ✅
- `synthesis` block has all eight keys at documented defaults. ✅
- `python3 tests/test_07_synthesis.py` — 13/13 green standalone. ✅
- `python3 tests/test_05a_intake_classifier.py` — 6/6 green (no regression). ✅
- No `routed_llm_call` in any synthesis function; no `api.anthropic.com` literal anywhere. ✅
- All 13 test functions confirmed pytest-collectable (no required positional args; `tmp_path_factory` defaults to `None`). ✅

## Deviations from Plan

**1. [Rule 3 — Environment] pytest not installed in the execution sandbox**
- **Found during:** Task 3 verification (`python3 -m pytest tests/test_07_synthesis.py -q`).
- **Issue:** The sandbox has no `pytest` module and is externally-managed (PEP 668); installing it would require `--break-system-packages`, which risks the system Python and is a package-manager install (excluded from auto-fix per the executor's Rule 3 exclusion).
- **Resolution:** Did NOT force-install. The standalone runner is the primary Wave-0 gate per RESEARCH ("Quick run command: `python3 tests/test_07_synthesis.py`") and passes 13/13. The tests are written pytest-compatible (plain `def test_*`, the single fixture-style arg defaults to `None`), and collectability was verified by importing the module and asserting no test function requires a positional arg. The `python3 -m pytest` gate will pass in CI/an environment where pytest is present.
- **Files modified:** none (environmental, not a code defect).
- **Commit:** n/a.

## Known Stubs

None. All functions are fully wired against live economy_map tables / the proxy route; the only deliberately-unconnected piece is the orchestrator that calls them, which is explicitly Plan 07-02's scope (the plan isolates primitives in Wave 0 for unit testing before composition).

## Notes for Plan 07-02

- The orchestrator should: load identity (skip cycle on `None`), `fetch_economy_map_blocks`, per-block `block_has_open_draft` + `fetch_block_new_entries(slug, block["last_synthesized_at"])` → `is_block_eligible` → `fetch_current_block_body` → `assemble_synthesis_input` → `synthesis_sonnet_call(identity, assembled["prompt"], cfg)` → `parse_synthesis_output` → `economy_map_insert_block_body_version`.
- `synthesized_from_through` on the INSERT must be the run wall-clock (`datetime.now(timezone.utc).isoformat()`), NOT the newest entry's date (Pitfall 5).
- Per-block try/except so one bad block never aborts the cycle; wrap with `log_pipeline_start/log_pipeline_end('synthesize_blocks')`.
- Cadence is SYNT-02 executor discretion (RESEARCH recommends daily or every 6h, avoiding the Friday newsletter slots).
