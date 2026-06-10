---
phase: 16-content-load-unpublished
verified: 2026-06-08T18:00:00Z
status: passed
score: 12/12 must-haves verified
overrides_applied: 0
---

# Phase 16: Content Load (Unpublished) Verification Report

**Phase Goal:** All in-scope canonical bodies (hub `agent-economy` + the reconciled blocks) land in `economy_map` as unsorted/unpublished, using the YAML frontmatter as the metadata source of truth — content is present in the store with zero change for live visitors, and the load refuses to land anything blank or partial.

**Verified:** 2026-06-08T18:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Visitor-facing published-body count is identical before and after the load (zero new published rows) | VERIFIED | Live anon-key read: `[identity-trust, governance-accountability]` — 2 rows, same as the BEFORE snapshot in `16-LOAD-EVIDENCE.md`. Independently confirmed. |
| 2 | All 8 in-scope canonical bodies are present in `economy_map.block_body_versions` as `status='draft'`, each exactly once | VERIFIED | Live service-role read: 8 in-scope slugs each present once as `draft` (plus `regulation-legal` = 9 total). |
| 3 | Substrate trio (`identity-trust`, `memory-context`, `payments-settlement`) carry `proposed_maturity='emerging'` (the `building→emerging` remap landed) | VERIFIED | Live read confirms all three show `emerging`. |
| 4 | The tier CHECK admits `'hub'` — the agent-economy row exists, proving the constraint was relaxed | VERIFIED | `agent-economy` row with `tier='hub'` confirmed live at `sort_order=0`. |
| 5 | `economy_map.blocks` has 9 rows with `sort_order` contiguous {0..8}, `agent-economy` at 0 (hub), `negotiation-coordination` at 5 (behavior) | VERIFIED | Live query returns exactly 9 rows, sort_order 0..8 sequential, correct slugs/tiers. |
| 6 | The loader validates all inputs up front and halts before any insert if any one fails (no partial load) | VERIFIED | `validate_all` collects ALL failures and raises before any POST. `test_load_lands_nothing_when_gate_fires` (pytest 4 passed in 0.03s) proves zero POSTs land when the gate fires, with dummy env so the env-gate is bypassed — validation is the real gate. |
| 7 | The loader rejects an empty/whitespace-only `body_md` and an out-of-enum `proposed_maturity` | VERIFIED | Tests A and B (`test_load_halts_on_empty_body`, `test_load_halts_on_invalid_maturity`) both pass. Source: `validate_all` checks `body.strip() == ""` and `maturity not in LIVE_MATURITY`. |
| 8 | The loader inserts bodies via direct PostgREST (`Content-Profile: economy_map`), omits `status`, and never writes a `blocks` row | VERIFIED | Source confirms `Content-Profile: economy_map` in `insert_block_body_version`; `status` absent from `build_payload`; no `INSERT INTO economy_map.blocks` anywhere in the loader. |
| 9 | The loader applies `building→emerging` before insert and uses `Accept-Profile` for reads (no `supabase-py`) | VERIFIED | `MATURITY_REMAP = {"building": "emerging"}` applied in `computed_maturity()`; `Accept-Profile: economy_map` in `_economy_map_get`; `grep "from supabase import"` returns no matches. |
| 10 | Existing live rows for matching slugs are corrected via canonical-body-rewrite path (no raw UPDATE; no duplicate block rows) | VERIFIED | `16-LOAD-EVIDENCE.md` documents: corrections via `reject_block_version()` RPC (status-only `draft→superseded`), then a fresh draft insert. No raw body UPDATE. The one-open-draft UNIQUE index (migration 041) backs no-duplicate guarantee. Idempotent re-run: `inserted=0 skipped=8`. |
| 11 | The loader is idempotent — re-run exits 0 and skips all 8 via `block_has_open_draft` | VERIFIED | `16-LOAD-EVIDENCE.md` records `DONE: inserted=0 skipped=8 dry_run=False` on re-run. |
| 12 | The migration contains no `block_body_versions` inserts and no `body_md` (bodies are the loader's job) | VERIFIED | `grep "INSERT INTO economy_map.block_body_versions"` and `grep "body_md"` on migration 043 both return no SQL-level matches; the only references are in comments confirming the absence. |

**Score:** 12/12 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/migrations/043_economy_map_hub_and_negotiation_blocks.sql` | Tier-CHECK relax + hub/negotiation INSERT + highest-first reshuffle; no body content | VERIFIED | 55-line file. All acceptance criteria met: `blocks_tier_check` present; hub (`agent-economy`, `hub`, sort_order=0) and negotiation (`negotiation-coordination`, `behavior`, sort_order=5) INSERTs with `ON CONFLICT (slug) DO NOTHING`; reshuffle runs highest-first (regulation→8, psychology→7, governance→6) before INSERT; `::economy_map.maturity` cast used; no `block_body_versions`, no `body_md`. |
| `scripts/load_economy_map_content.py` | Standalone PostgREST body loader: validate-all-then-insert, `building→emerging`, idempotent skip-if-open-draft | VERIFIED | 380 lines. Parses with `ast.parse` (exit 0). Glob `[0-9][0-9]-*.md` with `EXPECTED_COUNT=8` assert on default dir. `Content-Profile` + `Accept-Profile` present. No `from supabase import`. `validate_all` defined (collect-all-failures). `MATURITY_REMAP={"building":"emerging"}`. `LIVE_MATURITY` 5-member set. `build_payload` keys exactly `{block_slug, body_md, proposed_maturity}`. Never writes `economy_map.blocks`. |
| `tests/test_16_content_load.py` | Negative-path test: broken fixture halts loader, zero POSTs captured | VERIFIED | 173 lines. Imports via `sys.path.insert(0, str(_ROOT / "scripts"))` + `import load_economy_map_content as loader`. Tests A/B/C/D all pass (`4 passed in 0.03s`). Test C sets dummy env vars (env-gate bypassed), monkeypatches `httpx.post`, asserts both validation gate fired AND `captured["posts"] == []`. |
| `.planning/phases/16-content-load-unpublished/16-LOAD-EVIDENCE.md` | SC#1 before/after anon-perspective evidence + loaded-draft inventory + idempotency note | VERIFIED | 99-line document. BEFORE=2/AFTER=2 anon published-body count recorded. +2 structural blocks delta explained. 8-slug draft inventory with per-slug maturity and disposition. LOAD-03 posture documented. `inserted=0 skipped=8` idempotent re-run recorded. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `043_economy_map_hub_and_negotiation_blocks.sql` | `economy_map.blocks` | `ALTER TABLE + INSERT + UPDATE` (no append-only trigger on blocks) | VERIFIED | Migration applied live via Supabase Management API (PAT). 9-row contiguous sort_order confirmed by independent live query. |
| `scripts/load_economy_map_content.py` | `economy_map.block_body_versions` | Direct PostgREST POST (`Content-Profile: economy_map`), status omitted | VERIFIED | Live load ran HOST-SIDE (`inserted=8 skipped=0`). 8 drafts present in live DB as confirmed by independent read. |
| `tests/test_16_content_load.py` | `scripts/load_economy_map_content.py` | `import load_economy_map_content as loader` + monkeypatched `httpx.post` | VERIFIED | Import confirmed in source at line 34. Captured-posts assertion at line 151. |
| `16-LOAD-EVIDENCE.md` | anon-key SELECT on `economy_map` | Before/after published-row count comparison | VERIFIED | BEFORE=2, AFTER=2 published-body count confirmed both from evidence file and independently via live anon-key read. |

---

## Data-Flow Trace (Level 4)

Not applicable to this phase. The artifacts are a one-shot migration, a standalone loader script, a test file, and an evidence document — not components rendering dynamic data from a live data path. The data-flow is the loader itself: YAML frontmatter → `validate_all` → `build_payload` → `insert_block_body_version` → `block_body_versions` table. The live DB read confirms data flows to the store.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Test suite passes without live DB | `python3 -m pytest tests/test_16_content_load.py -q` | `4 passed in 0.03s` | PASS |
| Loader parses without syntax errors | `python3 -c "import ast; ast.parse(...)"` | Exit 0 | PASS |
| 8 in-scope draft bodies present in live DB | Service-role PostgREST `GET block_body_versions?status=eq.draft` | 8 in-scope slugs (+ regulation-legal = 9 total) | PASS |
| Anon published-body count unchanged | Anon-key PostgREST `GET block_body_versions?status=eq.published` | 2 rows (identity-trust, governance-accountability) | PASS |
| 9 blocks contiguous sort_order 0..8 | Service-role PostgREST `GET blocks?order=sort_order.asc` | 9 rows, sort_order 0..8, hub at 0, negotiation at 5 | PASS |
| Substrate trio carry `emerging` maturity | Within draft inventory read | identity-trust/memory-context/payments-settlement all `emerging` | PASS |

---

## Probe Execution

No `probe-*.sh` scripts declared for this phase. Step 7c: N/A.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| LOAD-01 | Plans 01, 02, 03 | All canonical bodies loaded into `economy_map` as unpublished, frontmatter as metadata source of truth, zero change for live visitors | SATISFIED | 8 drafts in live DB; anon published count = 2 (unchanged); substrate trio = emerging; hub = nascent |
| LOAD-02 | Plan 02 | Load fails loud on any missing/empty required field — halts with clear error, never lands blank/partial block | SATISFIED | `validate_all` collects all failures before any POST; pytest 4/4 pass including Test C (zero-POST proof); empty-body and invalid-maturity both raise |
| LOAD-03 | Plans 02, 03 | Existing live rows corrected via canonical-body-rewrite path (not raw UPDATE); no duplicate block rows | SATISFIED | Stale drafts superseded via `reject_block_version` RPC (status-only, trigger-legal); no raw body UPDATE; UNIQUE-open-draft index (041) enforces no duplicates; idempotent re-run `skipped=8` |

All three requirements for Phase 16 are SATISFIED.

---

## Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|------------|
| `043_economy_map_hub_and_negotiation_blocks.sql` lines 47, 52, 53 | `TBD` in SQL string literals | INFO | These are `'TBD — set via /map-tension'` SQL data values in the `live_tension` column INSERT — operator-authored seed placeholders per the Phase 15/16 design (populated at runtime via `/map-tension` command). NOT code debt markers. No unresolved code debt. |

The review (16-REVIEW.md) found 0 criticals and 4 warnings. Per the verification instructions, the warnings WR-02/03/04 were fixed in commit `14ff518` before verification. WR-01 (missing explicit `BEGIN;/COMMIT;` in the migration) was accepted as documented: the migration was applied via the Supabase Management API `/database/query` endpoint which wraps multi-statement queries in an implicit pg-meta transaction — atomicity holds for the actual apply mechanism used. No `TBD`/`FIXME`/`XXX` debt markers exist in the files. No BLOCKER anti-patterns.

---

## Human Verification Required

None. All acceptance criteria for this phase are verifiable programmatically or through recorded live-DB evidence (real before/after anon-key reads). The phase does not produce any user-facing UI changes (the loaded drafts are invisible to visitors per RLS). No human verification is needed to proceed.

---

## Gaps Summary

No gaps. All 12 must-have truths verified; all 4 artifacts verified as substantive and wired; all 3 requirement IDs (LOAD-01, LOAD-02, LOAD-03) satisfied; tests pass; live DB state independently confirmed.

---

_Verified: 2026-06-08T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
