---
phase: 07-synthesis-loop-core
verified: 2026-06-01T20:15:00Z
status: passed
score: 15/15 must-haves verified
overrides_applied: 0
---

# Phase 7: Synthesis Loop Core Verification Report

**Phase Goal:** Per-block synthesis runs autonomously on threshold triggers, calls Claude Sonnet through llm-proxy with a hot-reloadable identity, and lands a new `block_body_versions` row as `draft`.
**Verified:** 2026-06-01T20:15:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Editing `synth_identity.md` on disk changes the next synthesis call's system prompt with no service restart (mtime hot-reload) | VERIFIED | `load_synth_identity` at line 3051: mtime-cached with `is not None` guard; re-reads on mtime change. `test_identity_loads_and_hot_reloads` PASS confirms mtime-trigger re-read. |
| 2 | A missing or empty `synth_identity.md` causes the loader to return None and the caller to skip the cycle (fail-loud, never voiceless synthesis) | VERIFIED | Lines 3065-3075: missing => `logger.error` + return None; empty-after-strip => `logger.error` + return None. Poller line 3531-3537 aborts with a durable `failed` run row (WR-05 fixed in commit 60e9fc6). Tests `test_identity_loads_and_hot_reloads` and `test_poller_aborts_loud_on_none_identity` both PASS. |
| 3 | The eligibility predicate marks a block eligible at >= N=5 new entries since last_synthesized_at, OR >= T=30 days with >= 1 new entry, and never when a draft already exists | VERIFIED | `is_block_eligible` lines 3210-3241: has_draft => False; n>=N => True; n>=1 AND age>=T_days => True. `test_eligibility_truth_table` covers all cases including zero-entries => False. PASS. |
| 4 | Recency counts entries by created_at > last_synthesized_at (D-02 watermark column, D-04 created_at recency; NULL watermark => all entries / cold-start), never by event_date | VERIFIED | `fetch_block_new_entries` lines 3133-3149: filters `created_at=gt.{watermark}` when watermark is not None; omits filter when None (cold-start). event_date is used only for prompt ordering in assembler. Test confirms cold-start cold-start behavior. |
| 5 | Input assembly passes concrete entry content (event_date, what_shifted, why_it_mattered, source_url) ordered by event_date newest-first, never bare cluster labels | VERIFIED | `_format_synthesis_entry` line 3244 formats all four fields. `assemble_synthesis_input` sorts by event_date desc (line 3272). `test_assembly_orders_newest_first_and_under_cap` asserts field-level ordering. PASS. |
| 6 | When unabsorbed entries exceed the cap, the most-recent up to the cap are kept and the omitted count is logged AND noted in the prompt (never a silent drop) | VERIFIED | Lines 3276 (entry ceiling), 3310-3313 (token trim); both trigger `logger.warning` + in-prompt note via `_build` at line 3299-3303. `test_assembly_over_cap_keeps_newest_and_notes_omission` asserts "3 older entries omitted" in prompt and omitted_count=3. PASS. |
| 7 | The single editorial call targets `{LLM_PROXY_URL}/anthropic/v1/messages` with the agent key and model claude-sonnet-4-20250514; no direct api.anthropic.com call and no routed_llm_call usage | VERIFIED | `synthesis_sonnet_call` line 3370 constructs `f"{LLM_PROXY_URL}/anthropic/v1/messages"`. No `api.anthropic.com` literal anywhere in processor (grep confirms). No `routed_llm_call` in any synthesis function. `test_sonnet_call_routes_through_anthropic_messages` asserts URL, both auth headers, and model. PASS. |
| 8 | Output parse validates proposed_maturity against the five-value enum and raises (caller skips, never defaults) on invalid/missing/empty body_md | VERIFIED | `parse_synthesis_output` lines 3342-3353: raises ValueError on empty body, out-of-enum maturity, missing maturity, and (WR-02 fix) missing skeleton sections. Four dedicated tests PASS. |
| 9 | A scheduled processor job (registered via the schedule library) runs the synthesis cycle autonomously, iterating all seven blocks | VERIFIED | `scheduled_synthesize_blocks` at line 10424; registered at line 10860: `schedule.every().day.at("07:00").do(scheduled_synthesize_blocks)`. Comment cites SYNT-02 and documents slot rationale (avoids Friday/Monday newsletter slots). |
| 10 | For each block the loop evaluates eligibility (no-draft guard + N/T predicate), and when eligible assembles input, makes ONE Sonnet call via the proxy, parses+validates output, and INSERTs exactly one block_body_versions row with status draft | VERIFIED | `synthesize_block` lines 3425-3493: sequential: has_draft check → entries fetch → eligibility → assemble → ONE Sonnet call → parse → ONE INSERT. `test_poller_eligible_block_drafts_one_row_no_published_write` asserts exactly 1 Sonnet POST + 1 INSERT. PASS. |
| 11 | An ineligible block is skipped; a per-block error (read/call/parse) is logged and skipped without aborting the whole cycle | VERIFIED | Ineligible path returns `{status: 'skipped'}` (line 3458-3463). Poller lines 3554-3576: each block in its own try/except; exception increments failed and continues. `test_poller_isolates_one_failing_block` proves the other block is still processed. PASS. |
| 12 | Every successful synthesis writes one new draft row with populated body_md and a valid proposed_maturity, and synthesized_from_through set to the run wall-clock timestamp | VERIFIED | Lines 3476-3482: `synthesized_from_through = datetime.now(timezone.utc).isoformat()` (Pitfall 5 correct). `test_poller_eligible_block_drafts_one_row_no_published_write` asserts `synthesized_from_through` present. INSERT shape test confirms 4-key payload. PASS. |
| 13 | Nothing about the live published row, blocks.maturity, or blocks.current_body_version_id changes (GATE-01 draft-only invariant upheld) | VERIFIED | `economy_map_insert_block_body_version` targets only `/block_body_versions`, omits status (DB default draft), omits `published_at`/`current_body_version_id`/`maturity`. Test asserts zero POST requests target `/blocks`. PASS. |
| 14 | A missing/empty synth_identity.md aborts the cycle loudly (no voiceless synthesis); a missing agent key aborts the run loudly (no silent no-op) | VERIFIED | Both gates now run AFTER `log_pipeline_start` (WR-05 fix, commit 60e9fc6, line 3527 before line 3530). Both paths call `log_pipeline_end(run_id, 'failed', ...)`. `test_poller_aborts_loud_on_none_identity` and `test_poller_aborts_loud_on_missing_key` PASS. |
| 15 | The poller records a pipeline run via log_pipeline_start/log_pipeline_end with totals (eligible/synthesized/skipped/failed) | VERIFIED | `log_pipeline_start('synthesize_blocks')` at line 3527; `log_pipeline_end(run_id, 'completed', totals)` at line 3578; `log_pipeline_end(run_id, 'failed', ...)` on error paths. Totals dict at line 3549. Test stubs confirm both calls made. |

**Score:** 15/15 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `config/economy_map/synth_identity.md` | Working-default editorial voice system prompt (operator-controlled, hot-reloaded) | VERIFIED | 104 lines; contains all six RNDR-02 skeleton headings, all five maturity enum values, body_md/proposed_maturity JSON format, data-not-instructions instruction, live_tension preservation rule. min_lines=15 exceeded. |
| `config/agentpulse-config.json` | synthesis config block (enabled, N, T_days, synthesis_model, max_input_entries, max_input_tokens, output_max_tokens, temperature) | VERIFIED | All 8 D-09 keys at exact documented defaults (enabled:true, N:5, T_days:30, synthesis_model:claude-sonnet-4-20250514, max_input_entries:22, max_input_tokens:12000, output_max_tokens:8000, temperature:0.4). Sibling of `intake_classifier`. |
| `docker/processor/agentpulse_processor.py` | load_synth_identity, synthesis Sonnet call, output parser, economy_map read/insert helpers, eligibility predicate, input assembly; synthesize_block, synthesize_blocks_poller, scheduled_synthesize_blocks, schedule registration | VERIFIED | All 14 functions defined (line refs: 3051, 3083, 3107, 3119, 3133, 3152, 3169, 3199, 3210, 3244, 3254, 3329, 3357, 3425, 3496, 10424); schedule at line 10860. Processor parses (python3 -c "import ast; ast.parse..." confirms). |
| `tests/test_07_synthesis.py` | Unit harness covering all requirement groups; contains synthesize_blocks_poller end-to-end tests | VERIFIED | 21 tests (13 Plan-01 unit + 5 Plan-02 poller end-to-end + 3 WR-02/03/04 fixes). All 21 PASS standalone. `/anthropic/v1/messages` literal present in test assertions. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `synthesis_sonnet_call` | `{LLM_PROXY_URL}/anthropic/v1/messages` | `httpx.post` with Bearer + x-api-key | VERIFIED | Line 3370; test captures and asserts URL ends with `/anthropic/v1/messages`. |
| `load_synth_identity` | `config/economy_map/synth_identity.md` | `Path.stat().st_mtime` cached read | VERIFIED | Line 3062: `p.stat().st_mtime`; cache guard `is not None` at line 3063. |
| `economy_map_insert_block_body_version` | `economy_map.block_body_versions` | PostgREST POST with `Content-Profile: economy_map` | VERIFIED | Line 3186: `"Content-Profile": "economy_map"`. Test asserts header and URL. |
| `main() schedule registration` | `scheduled_synthesize_blocks` | `schedule.every().day.at("07:00").do(scheduled_synthesize_blocks)` | VERIFIED | Line 10860 matches the pattern exactly. |
| `synthesize_blocks_poller` | `economy_map_insert_block_body_version` | one draft INSERT per eligible+synthesized block | VERIFIED | `synthesize_block` calls `economy_map_insert_block_body_version` at line 3477; end-to-end test asserts exactly 1 INSERT POST per eligible block. |
| `synthesize_block` | `synthesis_sonnet_call` | single editorial call per eligible block | VERIFIED | Line 3472: `raw = synthesis_sonnet_call(identity_text, assembled["prompt"], cfg)` inside the eligible branch. |

### Data-Flow Trace (Level 4)

The synthesis pipeline is a write pipeline, not a render pipeline. Data flows: economy_map reads (blocks/entries/body) → assembly → Sonnet call → parse → draft INSERT. All data I/O is via stubbed httpx in tests; all production paths verified by code inspection and confirmed by the test harness.

| Stage | Data Variable | Source | Produces Real Data | Status |
|-------|---------------|--------|--------------------|--------|
| `fetch_economy_map_blocks` | blocks list | PostgREST GET `economy_map.blocks` | Yes — raises on non-2xx | FLOWING |
| `fetch_block_new_entries` | new_entries | PostgREST GET `economy_map.timeline_entries` with `created_at=gt.{watermark}` filter | Yes — raises on non-2xx | FLOWING |
| `synthesis_sonnet_call` | raw LLM text | `{LLM_PROXY_URL}/anthropic/v1/messages` httpx POST | Yes — raises on non-2xx or empty content | FLOWING |
| `economy_map_insert_block_body_version` | inserted draft row | PostgREST POST `economy_map.block_body_versions` | Yes — raises on non-2xx | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 21 synthesis tests pass standalone | `python3 tests/test_07_synthesis.py` | 21/21 passed | PASS |
| Processor file parses without syntax errors | `python3 -c "import ast; ast.parse(open('docker/processor/agentpulse_processor.py').read())"` | `processor parses OK` | PASS |
| synthesis config block has all 8 D-09 keys at exact defaults | `python3 -c "import json; c=json.load(...); s=c['synthesis']; assert s['N']==5 and s['T_days']==30 ..."` | `synthesis config: all 8 keys at documented defaults` | PASS |
| `/anthropic/v1/messages` route present in processor (not reverted) | `grep -c 'anthropic/v1/messages' agentpulse_processor.py` | 1 occurrence at line 3370 (live code); 2 in comments/docstrings | PASS |
| No `api.anthropic.com` literal in processor | `grep 'api.anthropic.com' agentpulse_processor.py` | 0 results | PASS |
| No `routed_llm_call` in any synthesis function | `grep 'routed_llm_call' agentpulse_processor.py \| grep -i synth` | 0 results | PASS |
| Schedule registration present | `grep "do(scheduled_synthesize_blocks)" agentpulse_processor.py` | line 10860 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| SYNT-01 | 07-01, 07-02 | Trigger evaluation — eligible when >=N=5 new entries since last_synthesized_at OR >=T=30 days with >=1 new entry | SATISFIED | `is_block_eligible` implements exact D-02/D-05/D-06 predicate; eligibility truth table test PASS |
| SYNT-02 | 07-02 | Trigger runs on a schedule | SATISFIED | `schedule.every().day.at("07:00").do(scheduled_synthesize_blocks)` at line 10860 |
| SYNT-03 | 07-01, 07-02 | Input assembly — current published body, timeline entries since prior synthesized_from_through (ordered by event_date), live_tension, current maturity — concrete entries, never cluster labels | SATISFIED | `assemble_synthesis_input` includes all four concrete entry fields, live_tension, maturity, six skeleton headings; ordered event_date desc |
| SYNT-04 | 07-01, 07-02 | Single editorial LLM call, Claude Sonnet, routed through `http://llm-proxy:8200` | SATISFIED | `synthesis_sonnet_call` uses `httpx.post` to `{LLM_PROXY_URL}/anthropic/v1/messages`; model `claude-sonnet-4-20250514` |
| SYNT-05 | 07-01, 07-02 | Synthesis prompt lives in `economy_map/synth_identity.md`, hot-reloaded via mtime | SATISFIED | `load_synth_identity` with `st_mtime` cache; `is not None` guard for correct mtime comparison |
| SYNT-06 | 07-01, 07-02 | Output is a rewritten body_md plus a proposed_maturity | SATISFIED | `parse_synthesis_output` validates both; INSERT payload carries both fields |

All six phase-7 requirement IDs (SYNT-01 through SYNT-06) are SATISFIED.

Note: GATE-01 ("every synthesized body lands as a draft version") is mapped to Phase 9 in REQUIREMENTS.md, not Phase 7. Phase 7 enforces the draft-only invariant as a design constraint, and the implementation correctly upholds it, but it is not listed in this phase's `requirements:` frontmatter. It is verified here as a must-have truth (Truth #13) per the Plan 07-02 frontmatter, not as a Phase 7 requirement claim.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `config/economy_map/synth_identity.md` | 52 | `TBD` in prose | Info | This is intentional example text explaining what the system sees when a block's live_tension placeholder is "TBD — set via /map-tension". It is data content for the LLM, not a code debt marker. Not a blocker. |

No unreferenced `TBD`/`FIXME`/`XXX` debt markers found in the Python code. No stub implementations found in synthesis functions. All functions are substantive.

**Code-review warnings resolved before phase close (commit 60e9fc6):**
- WR-02: `parse_synthesis_output` now validates all six skeleton headings (raises ValueError on missing sections)
- WR-03: `synthesis_sonnet_call` raises descriptive `RuntimeError` on empty 200 content
- WR-04: `BlockSynthesisError` carries `eligible=True` so the poller correctly counts eligible-but-failed blocks
- WR-05: Both fail-loud gates (identity + key) now run after `log_pipeline_start` so both leave durable `failed` pipeline_runs rows

**Intentionally deferred (recorded in `.planning/todos/pending/2026-06-01-phase07-review-followups-wr01-in01-04.md`):**
- WR-01: DB-level UNIQUE index for one-open-draft-per-block — latent under single-threaded daily schedule; deferred to Phase 9/10 on the operator-approved migration track (when `/map-synth` manual trigger makes concurrency plausible)
- IN-01 through IN-04: latent quality/observability items with no Phase 7 action required

### Human Verification Required

None. All must-haves were verifiable programmatically. The synthesis loop is draft-only and requires no running service for verification.

### Gaps Summary

No gaps. All 15 must-have truths are VERIFIED, all artifacts are substantive and wired, all six requirement IDs are satisfied, the test suite runs 21/21 clean, and the code-review blocking warnings were fixed before phase close.

---

_Verified: 2026-06-01T20:15:00Z_
_Verifier: Claude (gsd-verifier)_
