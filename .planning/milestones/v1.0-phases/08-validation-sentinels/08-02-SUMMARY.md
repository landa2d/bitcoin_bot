---
phase: 08-validation-sentinels
plan: 02
subsystem: gato_brain / economy_map /map-pending render
tags: [validation-sentinels, economy_map, gato-brain, telegram, read-only, VLDT-06]
requires:
  - "08-01 run_sentinels -> validator_report {tension_preserved, length_below_floor, structure_missing, maturity_jump, requires_attention, sentinel_errors?}"
  - "Phase 6 handle_map_pending + get_draft_versions read-only /map-pending surface (D-09)"
provides:
  - "get_draft_versions select extended to validator_report (the upstream data the renderer needs)"
  - "/map-pending surfaces each draft's sentinel flags loudly (⚠ REQUIRES ATTENTION + serious-first detail, or ✓ clean) — VLDT-06"
  - "_render_validator_flags(report) -> list[str] read-only flag formatter (D-08)"
affects:
  - "Phase 9 per-draft approval card (the flag surface this card will build on)"
tech-stack:
  added: []
  patterns:
    - "render-only / read-only by construction (no new PostgREST write verb, GET-only select extension — D-09)"
    - "loud-not-silent: a flagged draft is the visible outcome; sentinel_errors surfaced as a flag line (VLDT-05)"
    - "honest concrete detail — render what the report actually carries (bool/int), never fabricate a from→to direction the renderer doesn't fetch"
key-files:
  created: []
  modified:
    - "docker/gato_brain/gato_brain.py"
decisions:
  - "D-08: serious-first flag order = sentinel_errors → structure → tension → maturity → length"
  - "length flag rendered as 'length below floor (< 60% of prior)' — run_sentinels stores a bool, not the ratio, and /map-pending fetches no bodies"
  - "maturity rendered as 'maturity jump (Δ<n> stages — review)' — report stores absolute ordinal distance only, no direction"
metrics:
  duration: 5min
  completed: 2026-06-02
---

# Phase 8 Plan 02: /map-pending Sentinel Flag Surfacing (VLDT-06) Summary

Surface the Phase 8 validation sentinels loudly on the operator's `/map-pending` approval inbox: each draft with `requires_attention=true` now renders a `⚠ REQUIRES ATTENTION` headline plus an indented, concrete, serious-first per-flag detail list; a clean draft renders a quiet `✓ clean`. The change is render-only and read-only by construction — a flagged draft becomes the VISIBLE outcome (silence is the enemy).

## What Was Built

- **`get_draft_versions` select extended** (Task 1) — `"id,block_slug"` → `"id,block_slug,validator_report"` so `handle_map_pending` can read each draft's flags. Without this the renderer reads `None` and shows no flags (the PATTERNS.md easy-to-miss upstream change). The GET-only path, `Accept-Profile: economy_map`, and the fail-loud non-2xx guard are untouched (D-09 read-only by construction).
- **`_render_validator_flags(report) -> list[str]`** (Task 2) — a pure string formatter of the validator_report 08-01 wrote at INSERT. Reads keys `requires_attention`, `sentinel_errors`, `structure_missing`, `tension_preserved`, `maturity_jump`, `length_below_floor` (exact names confirmed against 08-01-SUMMARY.md / `run_sentinels`):
  - **Clean** (`requires_attention` falsy AND no `sentinel_errors`) → `     ✓ clean`.
  - **Flagged** → `   ⚠ REQUIRES ATTENTION` headline + indented detail lines, **serious first (D-08):** `sentinel_errors` (a check that silently failed is the worst case — VLDT-05) → `missing headings: <list>` (structure) → `tension trivialized` → `maturity jump (Δ<n> stages — review)` (only when `maturity_jump > 1`) → `length below floor (< 60% of prior)`.
- **Wired into `handle_map_pending`** — after the existing `version: <id>  →  /map-approve <id>` line, per draft, `lines.extend(_render_validator_flags(v.get("validator_report") or {}))`. The version + `/map-approve` forward-contract line, the UNSORTED AWAITING ASSIGNMENT section, and the `CHAR_BUDGET` truncation net are all preserved.

## Honest-detail decisions (concrete detail bounded by what the report carries)

The pinned D-08 mockup uses illustrative values (`nascent→contested (+2)`, `48% of prior`). `run_sentinels` (08-01) stores `maturity_jump` as an **absolute ordinal int** (no from→to direction) and `length_below_floor` as a **bool** (no ratio), and `/map-pending` deliberately fetches no bodies. Rather than fabricate a direction/percentage the renderer does not have, the flags render the real available detail: `maturity jump (Δ<n> stages — review)` and `length below floor (< 60% of prior)`. The structure, tension, and sentinel-error flags render the mockup wording verbatim from the data present. This keeps the surface loud and concrete without inventing values.

## GATE-01 / read-only by construction preserved (T-08-R1)

Render-only: the only data change is the `get_draft_versions` `select` string; no new PostgREST verb, no `Content-Profile`, no write branch (httpx.get + `Accept-Profile: economy_map` only). `_render_validator_flags` is pure string formatting of an already-fetched dict — no DB access, no `eval`/shell. T-08-R3 (large/malformed report) stays covered by the existing `CHAR_BUDGET` net + downstream 4000-char split.

## Verification

- `python3 -c "import ast; ast.parse(open('docker/gato_brain/gato_brain.py').read())"` — passes (run after each task).
- `grep` confirms `get_draft_versions` selects `validator_report` and `handle_map_pending` emits `REQUIRES ATTENTION`.
- `python3 -m pytest tests/test_gato_brain_e2e.py tests/test_07_synthesis.py -q` — **29 passed**.
- Manual render sanity (AST-extracted helper): clean report → `['     ✓ clean']`; fully-flagged report → `⚠ REQUIRES ATTENTION` + serious-first `missing headings`, `tension trivialized`, `maturity jump (Δ2 stages — review)`, `length below floor (< 60% of prior)`; `sentinel_errors` report → error line surfaced first; empty `{}` report → `✓ clean`.

## Deviations from Plan

None on code. The flag-detail wording for maturity/length adapts the illustrative mockup values to the report's actual bool/int shape (documented above) — the D-08 concept (concrete, serious-first, loud) holds.

Out of scope (not caused by this change, left untouched): full `python3 -m pytest tests/` has 13 pre-existing collection ERRORs from missing optional deps (`anthropic`, etc.) in unrelated service test modules. Not a regression from this plan.

## Threat Flags

None. No new security surface — the only network change is one column added to an existing GET select (T-08-R1 mitigation: no new verb / Content-Profile); flag text is short operator-only diagnostic copy (T-08-R2 accepted); truncation net intact (T-08-R3).

## Self-Check: PASSED

- FOUND: docker/gato_brain/gato_brain.py (modified — `_render_validator_flags` present, `select` includes `validator_report`, `handle_map_pending` extended)
- FOUND commit 252e868 (Task 1: get_draft_versions select extension)
- FOUND commit 62dfb0b (Task 2: handle_map_pending flag rendering)
