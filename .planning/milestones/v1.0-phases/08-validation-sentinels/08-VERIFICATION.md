---
phase: 08-validation-sentinels
verified: 2026-06-02T19:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 8: Validation Sentinels Verification Report

**Phase Goal:** Every synthesized draft is annotated with structured flags that surface loudly on the operator's Telegram card; flags never block draft creation
**Verified:** 2026-06-02T19:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Tension preserved sentinel writes `tension_preserved=false` when live-tension section is missing or trivialized | VERIFIED | `run_sentinels` lines 3453-3470 in processor; `_extract_section_body` extracts the `## The live tension` section; returns False on absent section, below 40-char floor, placeholder text, or verbatim echo of `block.live_tension`; tests: `test_sentinel_tension_absent_section`, `test_sentinel_tension_placeholder`, `test_sentinel_tension_verbatim_echo` — all pass |
| 2 | Length floor sentinel writes `length_below_floor=true` when new body < 60% of prior published length; N/A on cold-start | VERIFIED | `run_sentinels` lines 3472-3484; cold-start guard (`prior_body_md is None or not prior_body_md.strip()`) returns False without dividing; else `len(new)/len(prior) < 0.60`; tests: `test_sentinel_length_below_floor`, `test_sentinel_length_coldstart_na` — all pass |
| 3 | Maturity jump guard sets `requires_attention=true` when `proposed_maturity` differs from current `blocks.maturity` by more than one stop | VERIFIED | `run_sentinels` lines 3486-3496 uses `SYNTH_MATURITY_ORDER.index()` ordinal distance; D-04 rollup at 3498-3505 fires `requires_attention` when `maturity_jump > 1`; test: `test_sentinel_maturity_jump` asserts jump=2 fires attention and jump=1 does not — passes |
| 4 | Structure intact sentinel writes `structure_missing=[<heading_list>]` when any of the six skeleton headings is absent | VERIFIED | `run_sentinels` lines 3443-3451 uses heading-aware `_extract_section_body` (NOT substring match) — detects real `## ` headings only; returns `None` when heading is absent; test: `test_sentinel_flags_missing_structure` — passes |
| 5 | A failing sentinel never aborts draft creation; draft always lands with annotations; `/map-pending` surfaces all raised flags visibly | VERIFIED | Each sentinel individually wrapped in try/except; on error: logs `exc_info=True`, appends to `sentinel_errors`, applies conservative safe default (attention-surfacing); `requires_attention=True` includes `bool(sentinel_errors)` in rollup; `run_sentinels` never raises; `validator_report` in INSERT payload (lines 3640-3652); `_render_validator_flags` in `handle_map_pending` at line 1872; sentinel_errors surface first in serious-first ordering |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docker/processor/agentpulse_processor.py` | `run_sentinels` helper + `SYNTH_MATURITY_ORDER` + `synthesize_block` wiring + insert payload extension; WR-02 raise removed | VERIFIED | `SYNTH_MATURITY_ORDER` at line 3043; `run_sentinels` at line 3399; `_extract_section_body` at line 3371; `_SYNTH_TENSION_HEADING`/`_SYNTH_TENSION_PLACEHOLDER` at 3362-3368; `synthesize_block` calls `run_sentinels` at line 3640 before INSERT at 3646; `validator_report` in INSERT payload at line 3651; WR-02 raise absent from `parse_synthesis_output` (confirmed lines 3336-3359) |
| `tests/test_07_synthesis.py` | VLDT-04 sentinel tests replacing the WR-02 skeleton-raise test; insert-shape test updated for `validator_report` | VERIFIED | `test_parse_output_raises_on_missing_skeleton` DELETED; `test_parse_output_keeps_partial_skeleton` added at line 323 (D-01 no-raise behavior); 8 `run_sentinels` tests added (lines 336-436 covering VLDT-01/02/03/04 + D-04 rollup); `test_insert_block_body_version_shape` updated at line 477 to include `validator_report` in exact-key-set assertion; 29 tests collected and all pass |
| `docker/gato_brain/gato_brain.py` | `get_draft_versions` select extended to `validator_report`; `handle_map_pending` flag rendering per D-08 | VERIFIED | `get_draft_versions` selects `"id,block_slug,validator_report"` at line 1669; `_render_validator_flags` defined at line 1739; wired in `handle_map_pending` at line 1872 via `lines.extend(_render_validator_flags(v.get("validator_report") or {}))` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `synthesize_block` | `run_sentinels` | call between `parse_synthesis_output` and INSERT | VERIFIED | Line 3640: `validator_report = run_sentinels(parsed["body_md"], prior_body_md, block, parsed["proposed_maturity"])` appears between `parsed = parse_synthesis_output(raw)` (line 3635) and `economy_map_insert_block_body_version(...)` (line 3646) |
| `run_sentinels` output | `economy_map_insert_block_body_version` payload | `validator_report` key passed at INSERT time | VERIFIED | Line 3651: `"validator_report": validator_report` in the INSERT dict; docstring at line 3180 enumerates `validator_report` among payload keys |
| `get_draft_versions` | `block_body_versions.validator_report` | select string includes `validator_report` | VERIFIED | Line 1669: `"select": "id,block_slug,validator_report"` |
| `handle_map_pending` | draft `validator_report` | per-draft read + flag formatting | VERIFIED | Line 1872: `lines.extend(_render_validator_flags(v.get("validator_report") or {}))` inside the per-draft loop |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `_render_validator_flags` | `report` dict | `v.get("validator_report")` from `get_draft_versions` PostgREST GET | Reads `validator_report` written by `run_sentinels` at INSERT time from `block_body_versions` | FLOWING |
| `synthesize_block` → INSERT | `validator_report` | `run_sentinels(parsed["body_md"], prior_body_md, block, parsed["proposed_maturity"])` | Computed from real parsed body + prior body + block metadata | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 29-test sentinel suite passes | `python3 -m pytest tests/test_07_synthesis.py -q` | 29 passed in 0.05s | PASS |
| `_render_validator_flags` emits `REQUIRES ATTENTION` | source grep + code structure verified | "REQUIRES ATTENTION" found in gato_brain.py at line 1791 | PASS |
| `_render_validator_flags` emits `✓ clean` on empty report | source grep confirmed | `"     ✓ clean"` at line 1771 | PASS |
| `run_sentinels` before INSERT in `synthesize_block` | grep + line-range read | `run_sentinels(...)` at line 3640, INSERT at line 3646 | PASS |
| `validator_report` in INSERT payload | grep | `"validator_report": validator_report` at line 3651 | PASS |
| Syntax check — processor | `python3 -c "import ast; ast.parse(...)"` | PASS | PASS |
| Syntax check — gato_brain | `python3 -c "import ast; ast.parse(...)"` | PASS | PASS |

### Probe Execution

No probes declared for this phase. Step 7c: SKIPPED (no probe scripts found).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| VLDT-01 | 08-01-PLAN.md | Tension preserved — live-tension section exists and is non-trivial post-synthesis | SATISFIED | `run_sentinels` VLDT-01 block lines 3453-3470; 3 dedicated tests pass |
| VLDT-02 | 08-01-PLAN.md | Length floor — body not shorter than 60% of prior published length | SATISFIED | `run_sentinels` VLDT-02 block lines 3472-3484; cold-start guard confirmed; 2 dedicated tests pass |
| VLDT-03 | 08-01-PLAN.md | Maturity jump guard — proposed_maturity differs from current by >1 stop | SATISFIED | `run_sentinels` VLDT-03 block lines 3486-3496; ordinal distance via `SYNTH_MATURITY_ORDER.index()`; 1 dedicated test passes |
| VLDT-04 | 08-01-PLAN.md | Structure intact — all six skeleton headings present | SATISFIED | `run_sentinels` VLDT-04 block lines 3443-3451; heading-aware via `_extract_section_body`; 1 dedicated test passes |
| VLDT-05 | 08-01-PLAN.md | Failed sentinels annotate but do not block draft creation | SATISFIED | Each sentinel individually try/except; `sentinel_errors` note added; `requires_attention=True` on any error; `run_sentinels` never raises; draft INSERT always proceeds from `synthesize_block`; fail-loud-but-never-block confirmed |
| VLDT-06 | 08-02-PLAN.md | Telegram card surfaces flags loudly so a flagged draft is the visible outcome | SATISFIED | `_render_validator_flags` at gato_brain line 1739; wired in `handle_map_pending` at line 1872; `⚠ REQUIRES ATTENTION` headline + serious-first indented per-flag detail; `✓ clean` for unflagged drafts |

All 6 phase-8 requirements satisfied. No orphaned requirements for this phase.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

No TBD/FIXME/XXX markers found in files modified by this phase. No stub implementations detected. No hardcoded empty data. The code review (08-REVIEW.md) identified WR-01 (structure check using naive substring matching) — however, the **actual code at line 3444-3446 already uses the heading-aware `_extract_section_body` approach** the reviewer recommended as the fix. The review appears to have been based on an intermediate draft or cited incorrect line numbers. The codebase-as-shipped is not affected by WR-01. Code review WR-02 (misleading unused variable in `test_sentinel_length_below_floor`) and IN-01..IN-03 are minor quality/maintainability notes with no impact on correctness; none represent blockers.

### Human Verification Required

None. All success criteria are verifiable programmatically.

### Deferred Items

None. All 6 VLDT requirements are fully implemented and verified in this phase.

---

## Gaps Summary

No gaps. All 5 ROADMAP success criteria and all 6 VLDT requirements are satisfied by the actual code in the repository.

The phase invariant — **flags annotate, never block** — is fully implemented:
- `run_sentinels` is pure compute, never raises, wraps each sentinel individually
- `validator_report` is computed before the INSERT and written atomically (D-02)
- `parse_synthesis_output` no longer raises on missing headings (D-01 confirmed)
- `handle_map_pending` surfaces every raised flag via `_render_validator_flags`, serious-first
- Read-only-by-construction preserved in gato_brain (GET-only, Accept-Profile, no write verb added)

---

_Verified: 2026-06-02T19:00:00Z_
_Verifier: Claude (gsd-verifier)_
