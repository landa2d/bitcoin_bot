---
phase: 08-validation-sentinels
plan: 01
subsystem: processor / economy_map synthesis
tags: [validation-sentinels, economy_map, synthesis, append-only, fail-loud]
requires:
  - "Phase 7 synthesis primitives (parse_synthesis_output, synthesize_block, economy_map_insert_block_body_version)"
  - "migration 033 block_body_versions.validator_report jsonb (append-only trigger)"
provides:
  - "run_sentinels(body_md, prior_body_md, block, proposed_maturity) -> validator_report dict"
  - "SYNTH_MATURITY_ORDER ordered maturity sequence for ordinal distance"
  - "every synthesized draft lands with a populated validator_report (VLDT-01..05)"
affects:
  - "Phase 8 Plan 02 (gato_brain /map-pending flag rendering, VLDT-06)"
tech-stack:
  added: []
  patterns:
    - "deterministic sentinels — no LLM call (D-05 defers the judge to v2)"
    - "fail-loud-but-never-block (VLDT-05): log loud + record sentinel_errors, never raise"
    - "write-at-INSERT (D-02) — append-only trigger forbids post-insert annotation"
key-files:
  created: []
  modified:
    - "docker/processor/agentpulse_processor.py"
    - "tests/test_07_synthesis.py"
decisions:
  - "D-01: WR-02 skeleton hard raise removed; structure becomes a VLDT-04 annotating sentinel"
  - "D-07: SYNTH_MATURITY_ORDER added as ordered list; SYNTH_MATURITY_ENUM stays a set"
  - "VLDT-05: sentinel compute errors force requires_attention + record sentinel_errors note"
metrics:
  duration: 3min
  completed: 2026-06-02
---

# Phase 8 Plan 01: Validation Sentinels (compute + wiring) Summary

Compute the four deterministic validation sentinels plus a `requires_attention` rollup at synthesis time, write them atomically into the new draft's `validator_report` jsonb before the INSERT, and convert the Phase 7 WR-02 skeleton-missing hard gate into an annotating sentinel — so editorial risk is made VISIBLE without ever blocking a draft from landing.

## What Was Built

- **`SYNTH_MATURITY_ORDER`** — a module-level ordered list `["nascent","emerging","contested","consolidating","mature"]` next to `SYNTH_MATURITY_ENUM` (which stays a `set` for membership). Used for VLDT-03 ordinal distance — never `.index()` on the set (D-07).
- **WR-02 raise removed** from `parse_synthesis_output` (and the docstring clause): a body missing skeleton headings no longer raises/skips. Empty-body, invalid-maturity, and missing-maturity raises are kept (genuinely unusable model output) (D-01).
- **`run_sentinels(body_md, prior_body_md, block, proposed_maturity) -> dict`** — a pure-compute primitive mirroring the Phase 7 style (top-level def, decision-ID-citing docstring, returns a plain dict, no class). Returns `{tension_preserved, length_below_floor, structure_missing, maturity_jump, requires_attention}` (+ `sentinel_errors` only on error):
  - **VLDT-04** structure: `structure_missing = [h for h in SYNTH_SKELETON_HEADINGS if h.lower() not in body_md.lower()]` (idiom lifted from the removed gate).
  - **VLDT-01** tension: a `## The live tension` section scanner (`_extract_section_body`); `tension_preserved=False` when the section is absent, below a 40-char floor, equals the real placeholder `'TBD — set via /map-tension'`, or verbatim-echoes `block.live_tension`.
  - **VLDT-02** length: cold-start (`prior_body_md` None/blank) → `False`/N/A, never divide; else `len(new)/len(prior) < 0.60` (D-06).
  - **VLDT-03** maturity_jump: `abs(SYNTH_MATURITY_ORDER.index(proposed) - SYNTH_MATURITY_ORDER.index(block.maturity))` (D-07).
  - **D-04** rollup: `requires_attention = (not tension_preserved) or length_below_floor or (maturity_jump > 1) or bool(structure_missing) or bool(sentinel_errors)`.
  - **VLDT-05**: each sentinel wrapped in try/except — logs loudly with `exc_info=True`, records a `sentinel_errors` note, applies a conservative attention-surfacing default, and never raises.
- **`synthesize_block` wiring** — `run_sentinels(...)` is called between `parse_synthesis_output` and the INSERT, reusing `prior_body_md` already in scope (no second `fetch_current_block_body`). `validator_report` added to the insert payload so it is written atomically at INSERT (D-02). The `economy_map_insert_block_body_version` docstring now enumerates `validator_report`; the function body (forwards `json=row`) is unchanged.
- **Tests** — deleted `test_parse_output_raises_on_missing_skeleton`; added `test_parse_output_keeps_partial_skeleton` (D-01) plus eight `run_sentinels` tests covering VLDT-01 (absent/placeholder/verbatim-echo), VLDT-02 (below-floor + cold-start N/A), VLDT-03 (jump>1 fires / adjacent step does not), and the VLDT-04 + D-04 rollup. Updated `test_insert_block_body_version_shape` exact-key-set + row fixture to include `validator_report`, and refreshed the `_run_all()` manual-runner list.

## GATE-01 (autonomy boundary) preserved

`run_sentinels` is pure compute — no PostgREST verb, no LLM call, no touch of `blocks.maturity` / `blocks.current_body_version_id` / any published row. The only DB change is the existing draft INSERT payload gaining one key.

## Verification

- `python3 -c "import ast; ast.parse(...)"` on the processor — passes (run after Task 1 and Task 2).
- `python3 -m pytest tests/test_07_synthesis.py -q` — **29 passed**.
- Manual runner `python3 tests/test_07_synthesis.py` — **All 29 passed**.
- `grep` confirms `run_sentinels(` is called inside `synthesize_block` (line 3631) before the INSERT and `"validator_report": validator_report` appears in the payload (line 3642).
- `SYNTH_MATURITY_ENUM` remains a `set`; `SYNTH_MATURITY_ORDER` is the new ordered list. No new PostgREST verb introduced.

## Deviations from Plan

None — plan executed exactly as written. (pytest was not installed in the environment; installed via `pip install --user --break-system-packages pytest` to run the suite — a tooling step, not a code/plan deviation.)

## Threat Flags

None. No new security surface beyond the planned `validator_report` dict crossing into the existing draft INSERT (T-08-01/02/03 mitigations applied: pure-compute string scans, no eval/shell/SQL-building, fail-loud-non-blocking error handling, GATE-01 draft-only).

## Self-Check: PASSED

- FOUND: docker/processor/agentpulse_processor.py (modified, `def run_sentinels` present)
- FOUND: tests/test_07_synthesis.py (modified, sentinel tests present)
- FOUND commit 4c10a58 (Task 1), 87f7752 (Task 2), d0fcbf6 (Task 3)
