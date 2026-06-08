---
phase: 16-content-load-unpublished
plan: 02
subsystem: economy_map content load
tags: [loader, postgrest, fail-loud, validate-all, idempotent, negative-test]
requires:
  - "Migration 043 (Plan 01) applied — FK targets (hub + negotiation blocks rows) must exist before the loader runs (Plan 03)"
provides:
  - "scripts/load_economy_map_content.py — standalone PostgREST bodies-only draft loader"
  - "tests/test_16_content_load.py — negative-path proof (halts loud, lands nothing)"
affects:
  - "economy_map.block_body_versions (draft inserts only, run gated to Plan 03)"
tech-stack:
  added: []
  patterns:
    - "Direct PostgREST + Content-Profile (write) / Accept-Profile (read) — no supabase-py"
    - "validate-ALL-then-insert fail-loud gate (collect all failures, raise before any POST)"
    - "Purpose-scoped writer (single narrow block_body_versions insert; threat T-16-WS)"
    - "Idempotent skip-if-open-draft (replicated block_has_open_draft)"
key-files:
  created:
    - scripts/load_economy_map_content.py
    - tests/test_16_content_load.py
  modified: []
decisions:
  - "Loader is self-contained: REPLICATES the 3 processor functions (D-01), never imports them"
  - "Pinned glob [0-9][0-9]-*.md selects exactly the 8 numbered bodies; count==8 assert gated on the default DOCS_DIR"
  - "DOCS_DIR override hook (env ECONOMY_MAP_DOCS_DIR / module attr) so the test points at a fixture dir"
metrics:
  duration: ~12m
  completed: 2026-06-08
---

# Phase 16 Plan 02: Standalone economy_map Body Loader Summary

Authored a self-contained PostgREST bodies-only draft loader (`scripts/load_economy_map_content.py`) that parses the 8 numbered canonical `.md` bodies, validates the whole batch up front (validate-all-then-insert, D-04), applies the `building→emerging` remap (P15-D-01), and inserts `block_body_versions` drafts via direct PostgREST with `Content-Profile: economy_map` (status omitted) — plus a deliberately-broken-fixture negative test proving the validation gate halts loud and lands zero POSTs (D-06). No live DB was touched; the actual run is Plan 03's orchestrator-gated job.

## What Was Built

### Task 1 — `scripts/load_economy_map_content.py` (commit `d6b3b14`)
Standalone one-shot loader, self-contained per D-01 (replicates, does NOT import, the 3 processor functions). Imports: `yaml, os, sys, glob, httpx` — no `from supabase import`.

**Function names (Plan 03 + the test drive these):**
- `_economy_map_get(table, params)` — READ helper, `Accept-Profile: economy_map`, raises on non-2xx (replicated from `agentpulse_processor.py:3088`)
- `block_has_open_draft(slug)` — idempotent skip query (`{"block_slug": "eq.<slug>", "status": "eq.draft", "select": "id", "limit": 1}`) (replicated from `:3124`)
- `insert_block_body_version(row)` — WRITE path, `Content-Profile: economy_map`, status OMITTED, raises on non-2xx (replicated from `:3174`)
- `parse_doc(path)` — frontmatter (`---`/`---`) + body parse → record dict
- `computed_maturity(record)` — hub → `'nascent'`; block → `MATURITY_REMAP.get(raw, raw)`
- `validate_all(records)` — the D-04 pre-flight gate (collect ALL failures, raise `ValueError` before any POST)
- `discover_docs()` — globs the pinned pattern; count==8 assert on the default dir
- `build_payload(record)` — exactly `{block_slug, body_md, proposed_maturity}`
- `main()` — env gate → discover → parse → validate_all → per-record skip-if-open-draft / insert; `--dry-run` supported

**Module-level constants:** `LOCKED_ROSTER` (8 slugs), `MATURITY_REMAP = {"building": "emerging"}`, `LIVE_MATURITY = {nascent, emerging, contested, consolidating, mature}` (exact 5-member set), `HUB_MATURITY = "nascent"`, `INPUT_GLOB = "[0-9][0-9]-*.md"`, `EXPECTED_COUNT = 8`.

**Pinned input glob:** `[0-9][0-9]-*.md` — selects exactly the 8 numbered bodies (`00-hub.md`..`07-psychology-disposition.md`) and excludes the three frontmatter-less docs in the same dir (`EXECUTION_BRIEF.md`, `REDESIGN_BRIEF.md`, `economy-map-build-spec-v2.md`). The count==8 assertion is gated on the **default** `DOCS_DIR` only.

**DOCS_DIR / fixture-override hook (Plan 03 + test rely on this):** `DOCS_DIR = os.getenv("ECONOMY_MAP_DOCS_DIR", ".planning/docs")` — overridable via the env var or by setting the module attribute `loader.DOCS_DIR` at runtime. The count==8 gate is bypassed for any non-default dir so a fixture dir can carry a different count.

**HOST-SIDE run command (NOT a docker-exec — the loader is not copied into the processor container):**
```
source /root/bitcoin_bot/config/.env && python3 /root/bitcoin_bot/scripts/load_economy_map_content.py
```
Add `--dry-run` to validate + skip-check only (no POST).

### Task 2 — `tests/test_16_content_load.py` (commit `81387ef`)
Negative-path test, imports the loader via `sys.path.insert(0, str(_ROOT / "scripts"))` + `import load_economy_map_content as loader`. Uses the codebase flag/try/except/assert idiom (NOT `pytest.raises`).
- **Test A** `test_load_halts_on_empty_body` — `validate_all` raises on a whitespace-only `body_md`.
- **Test B** `test_load_halts_on_invalid_maturity` — `validate_all` raises on an out-of-enum post-remap maturity (`'legendary'`).
- **Test C** `test_load_lands_nothing_when_gate_fires` — broken fixture tmp dir + DUMMY `SUPABASE_URL`/`SUPABASE_KEY` (env-gate passes) + monkeypatched `httpx.post` capturing URLs → asserts BOTH the validation gate fired AND the captured POST list stays empty (the load lands nothing BECAUSE validation halted it, not the env-gate short-circuit — D-04/D-06).
- **Test D** `test_valid_batch_passes_gate` — positive control: a fully-valid batch passes `validate_all` unraised.

## Verification Results

- `python3 -c "import ast; ast.parse(...)"` on the loader — exit 0.
- Plan Task 1 grep suite (`Content-Profile`, `Accept-Profile`, no `from supabase import`, `building`, `validate_all`, pinned `[0-9][0-9]-*.md`) — **ALL PASS**.
- `grep "rest/v1/blocks"` — no match (loader never writes a `blocks` row).
- `build_payload` keys verified exactly `{block_slug, body_md, proposed_maturity}`; `status`/`published_at`/`current_body_version_id`/`maturity` absent from the payload; `building→emerging` remap confirmed.
- **`python3 -m pytest tests/test_16_content_load.py -q` → 4 passed in 0.03s**, WITHOUT a live DB.
- Behavioral spot-check: real `.planning/docs` parses 8 records, `validate_all` passes, identity-trust maturity → `emerging`, hub → `nascent`; empty body and invalid maturity both raise. Test C confirmed to halt at the **validation gate** (env-gate passed) with zero POSTs.

## Deviations from Plan

None — plan executed exactly as written. No Rule 1/2/3 auto-fixes were needed.

## Threat Surface

No new threat surface beyond the plan's `<threat_model>`. The loader keeps a single narrow `block_body_versions` insert (T-16-WS mitigated), passes body/frontmatter as JSON payload values via `httpx ... json=row` (no SQL surface, T-16-INJ mitigated), halts the whole batch loud on any gate failure (T-16-FL mitigated, proven by Test C), and rejects out-of-enum post-remap maturity (T-16-MAT mitigated).

## Known Stubs

None. The loader is complete and self-contained; the only deferred action is the live run against the DB, which is Plan 03's orchestrator-gated job (depends on migration 043 from Plan 01).

## Orchestrator Notes (state ownership)

Per the executor's critical overrides for this sequential phase: `.planning/STATE.md` and `.planning/ROADMAP.md` were **NOT modified by this agent** — the orchestrator owns those writes. (An unstaged ` M .planning/STATE.md` is present in the working tree; its diff is the orchestrator's own "Phase 16 execution started" marker written at wave start — left untouched, not staged/committed/reverted by this agent.) The gsd-sdk is not on this agent's PATH; the state/roadmap/requirements update steps from execute-plan.md were intentionally SKIPPED. Only the two code files and this SUMMARY.md were committed.

## Self-Check: PASSED

- `scripts/load_economy_map_content.py` — FOUND
- `tests/test_16_content_load.py` — FOUND
- `.planning/phases/16-content-load-unpublished/16-02-SUMMARY.md` — FOUND
- Commit `d6b3b14` (Task 1 loader) — FOUND
- Commit `81387ef` (Task 2 test) — FOUND
- Commit `f4c3c64` (SUMMARY docs) — FOUND
- STATE.md/ROADMAP.md not modified by this agent (the working-tree ` M STATE.md` is the orchestrator's own wave-start write) — VERIFIED
