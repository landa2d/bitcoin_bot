# Phase 16 — Load Evidence (SC#1 before/after + loaded-draft inventory)

**Captured:** 2026-06-08T17:38Z
**DB:** `economy_map` schema, project `zxzaaqfowtqvmsbitqpu` (LIVE)
**Loader:** `scripts/load_economy_map_content.py` run HOST-SIDE: `source /root/bitcoin_bot/config/.env && python3 /root/bitcoin_bot/scripts/load_economy_map_content.py`
**Access:** direct PostgREST + `Accept-Profile`/`Content-Profile: economy_map` (no supabase-py `.in_()`). Anon reads use `SUPABASE_ANON_KEY`; service reads/writes use `SUPABASE_SERVICE_KEY`.

---

## SC#1 — Anon-perspective BEFORE / AFTER (the visitor-facing no-change proof)

The proof that the draft load is invisible to visitors: the anon-key **published-body** count is identical before and after the load. (Drafts are invisible to anon — RLS on `block_body_versions` is `status='published'`.)

| Anon-key read | BEFORE (pre-load) | AFTER (post-load) | Δ |
|---|---|---|---|
| published `block_body_versions` (count) | **2** | **2** | **0** ✅ |
| published slugs | `identity-trust`, `governance-accountability` | `identity-trust`, `governance-accountability` | unchanged |
| visible `blocks` (count) | 9 | 9 | 0 |

**BEFORE == AFTER on the published-body count → zero new published rows → the live `#/map` renders no new content for visitors. SC#1 satisfied by a real before/after read, not RLS reasoning alone.**

### The +2 blocks delta is STRUCTURE, not content (expected)

The anon `blocks` count is **9** in both snapshots. It rose from the pre-phase **7** to **9** earlier in this phase via **migration 043** (Plan 16-01) — the new `agent-economy` (hub) and `negotiation-coordination` rows. Anon sees `blocks` rows (RLS `USING (true)`), but **those two new rows have no _published_ body**, so `#/map` renders no new content from them. The delta is metadata structure (sort_order/title), not visitor-facing body content. The published-body count — the thing that actually drives rendered content — is unchanged (2 → 2).

---

## Loaded-draft inventory (8 in-scope slugs, each present exactly once)

Service-role `GET /rest/v1/block_body_versions?status=eq.draft` after the load:

| # | slug | proposed_maturity | disposition |
|---|------|-------------------|-------------|
| 1 | agent-economy | nascent | first-publish (new hub) |
| 2 | identity-trust | **emerging** | canonical-body-rewrite (had published body; building→emerging) |
| 3 | memory-context | **emerging** | corrected (stale draft superseded → fresh canonical; building→emerging) |
| 4 | payments-settlement | **emerging** | first-publish draft (building→emerging) |
| 5 | autonomy-control | contested | corrected (stale draft superseded → fresh canonical) |
| 6 | negotiation-coordination | nascent | first-publish (new block) |
| 7 | governance-accountability | contested | canonical-body-rewrite (had published body) |
| 8 | psychology-disposition | nascent | corrected (stale draft superseded → fresh canonical) |

- All 8 in-scope slugs present as `status='draft'`, **each exactly once** (no duplicate per slug — the migration-041 UNIQUE-open-draft index backs this).
- **Substrate trio (identity-trust / memory-context / payments-settlement) all carry `proposed_maturity='emerging'`** — the `building → emerging` remap (P15-D-01) landed.
- Out of scope: `regulation-legal` keeps its pre-existing 2026-06-04 draft, untouched (P15-D-02 — deferred/body-less frame slug; only the structural `sort_order 7→8` bump in 043 touched it). Total open drafts in the table: 9 (8 in-scope + regulation-legal).

---

## LOAD-03 correction posture (no raw UPDATE; canonical-body-rewrite; no duplicates)

Per-slug correction disposition for this load:

- **First-publish (no prior body):** `agent-economy`, `payments-settlement`, `negotiation-coordination` — fresh draft inserted.
- **Canonical-body-rewrite over a published body:** `identity-trust`, `governance-accountability` — a NEW draft was inserted (the prior published row is left intact; the new draft is published in Phase 18). No raw UPDATE.
- **Stale-draft correction:** `memory-context`, `autonomy-control`, `psychology-disposition` — see deviation below.

**No raw `UPDATE` was issued against any append-only body column.** The append-only trigger (`033 §8`) forbids `DELETE` and pins `body_md`/`proposed_maturity`/`block_slug`/etc.; only the lifecycle columns (`status`/`published_at`) may change. The only status transitions issued were via the purpose-built `economy_map.reject_block_version(version_id)` RPC (`draft → superseded`, status-only).

---

## Deviation — pre-existing stale drafts (operator-approved)

**Finding (surfaced before any live write):** A dry-run revealed 3 in-scope slugs — `memory-context`, `autonomy-control`, `psychology-disposition` — already held **open drafts dated 2026-06-04** (v2.0-era), with **different bodies** from the current canonical docs and **wrong maturity** for two (`memory-context` and `autonomy-control` were `nascent`; canon is `emerging`/`contested`). The plan's `skip-if-open-draft` idempotency (designed for the loader's *own* partial-run recovery) would have **silently skipped** these 3 — leaving 3 canonical bodies unloaded. Body comparison (sha) confirmed all 3 differed from canon.

**Resolution (operator decision: "Reject stale, then load"):**
1. Captured BEFORE anon snapshot (above).
2. Called `reject_block_version()` on the 3 stale draft version IDs → each `draft → superseded` (HTTP 204; status-only transition via the purpose-built RPC — trigger-legal, NOT a raw body UPDATE; the canonical-body-rewrite path):
   - `memory-context` `b6f2e359-6e2f-4886-929a-af28c94f277c`
   - `autonomy-control` `f36c9ad4-0bec-44d7-b0aa-f4bbbdc62f26`
   - `psychology-disposition` `62dfd3ab-57f5-4491-9b8c-00b8e921bbb8`
3. Ran the loader → all 8 in-scope canonical bodies inserted as fresh drafts (`inserted=8 skipped=0`, exit 0).

This is fully LOAD-03-compliant: corrections went via canonical-body-rewrite (new draft after superseding the stale one), no raw UPDATE on an append-only column, and at most one open draft per slug.

---

## Idempotent re-run check

Re-ran the loader once more (HOST-SIDE) after the load:

```
DONE: inserted=0 skipped=8 dry_run=False
```

All 8 in-scope slugs **skipped** (skip-if-open-draft) — no second draft per slug, no `23505` crash. The load is safely re-runnable.

---

## Run log (chronological)

1. `--dry-run` pre-flight → surfaced the 3 stale-draft skips (finding above).
2. BEFORE anon snapshot captured (published=2, blocks=9).
3. `reject_block_version` × 3 → stale drafts superseded (open drafts among the 3 = 0).
4. Loader live run → `inserted=8 skipped=0` (exit 0); substrate trio = emerging.
5. AFTER anon snapshot captured (published=2, blocks=9) → **BEFORE == AFTER**.
6. Idempotent re-run → `inserted=0 skipped=8`.

*Phase: 16-content-load-unpublished · Plan 03 · 2026-06-08*
