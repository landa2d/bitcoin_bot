# Phase 15 — Per-Slug Roster Reconciliation (ROST-01)

**Assembled:** 2026-06-08
**Source authority:** CONTEXT D-01..D-06 (locked decisions), `15-RESEARCH.md §ROST-01 / §D-04`, the live seed `supabase/migrations/033_economy_map_schema.sql §13`, and the doc frontmatters `.planning/docs/00-hub.md … 07-psychology-disposition.md` (the metadata source of truth).

This is the per-slug reconciliation plan that Phase 16+ **executes** (documented HERE, executed THERE). Every disposition cites the `D-NN` decision it implements. **Phase 15 writes nothing to `economy_map`, applies no migration, edits no `app.js`** — this reconciliation is the operator-approval target gating Phase 16.

---

## Reconciled roster — per-slug disposition

One row for ALL 9 block-level entries (hub + 8). Values copied from CONTEXT §specifics; loaded maturity reflects the D-01 remap.

| order | slug | tier | maturity (loaded) | disposition | decision |
|---|---|---|---|---|---|
| 0 | `agent-economy` (hub) | hub (DB-served home per D-04) | — | first-publish (DB + `marked.parse`, RPC-gated) | D-04 |
| 1 | `identity-trust` | substrate | `emerging` (was `building`) | first-publish | D-01 |
| 2 | `memory-context` | substrate | `emerging` (was `building`) | first-publish | D-01 |
| 3 | `payments-settlement` | substrate | `emerging` (was `building`) | first-publish | D-01 |
| 4 | `autonomy-control` | behavior | `contested` | first-publish | — |
| 5 | `negotiation-coordination` | behavior | `nascent` | **new block** (graduated, was a section in Payments) | D-03 |
| 6 | `governance-accountability` | behavior | `contested` | first-publish (sort_order 5→6) | D-03 |
| 7 | `psychology-disposition` | behavior | `nascent` | first-publish (sort_order 6→7) | D-03 |
| 8 | `regulation-legal` | frame | (unchanged) | **kept deferred** — body-less, sort_order 7→8 | D-02 |

**Result:** **8 published bodies** (hub + 7 doc blocks) + `regulation-legal` retained as a deferred frame card = **9 block-level entries**, **3 tiers**.

The doc frontmatter `order` values already equal the CONTEXT target order (negotiation=5, governance=6, psychology=7 — confirmed in `05/06/07-*.md`). The docs are authored *in target state*; the reconciliation reshuffles the **live seed** (governance 5→6, psychology 6→7, +negotiation at 5, regulation 7→8) to match. The hub (`00-hub.md`) carries `type: hub` and **no `tier` / no `maturity`** frontmatter — consistent with D-04's "no tier."

---

## Tier model decision (D-02)

The tier model **STAYS at 3** — `substrate` / `behavior` / `frame` (the live `blocks.tier` CHECK, 033:68). It does **NOT** collapse to the docs' 2-tier framing; `app.js renderHub` already renders all three tier grids, so nothing needs to change there for the tier model.

`regulation-legal` (seeded `frame`, sort_order 7) is **kept as a deferred frame slot** — it stays **unpublished / body-less** this milestone and renders as a **DEFERRED card** (the `renderHub` deferred path for body-less blocks). It is fed later by the EU AI Act tracker (a future milestone, EUAI-01/02 — out of scope here). Per D-02, the **only permitted touch** to its row is the structural `sort_order 7→8` bump (per D-03) — **no content/publish write**, so the deferred/body-less invariant is preserved. (There is intentionally **no `08-regulation-legal.md` doc** — flag F-3 below.)

---

## D-03 sort_order reshuffle — collision-free map

`blocks.sort_order` is `INTEGER NOT NULL UNIQUE` (033:72). The target inserts `negotiation-coordination` at 5 and shifts everything behind it up by one.

| slug | before (live seed) | after (target) | operation |
|---|---|---|---|
| `identity-trust` | 1 | 1 | unchanged |
| `memory-context` | 2 | 2 | unchanged |
| `payments-settlement` | 3 | 3 | unchanged |
| `autonomy-control` | 4 | 4 | unchanged |
| `negotiation-coordination` | (absent) | **5** | **INSERT** (new behavior block, D-03) |
| `governance-accountability` | 5 | **6** | UPDATE +1 (5 → 6) |
| `psychology-disposition` | 6 | **7** | UPDATE +1 (6 → 7) |
| `regulation-legal` | 7 | **8** | UPDATE +1 (7 → 8; frame bump, D-03; stays body-less per D-02) |

**Final ordered set = {1,2,3,4,5,6,7,8}** — 8 distinct values, contiguous, no gaps, no duplicates — **collision-free** (the contiguous sequence 1-2-3-4-5-6-7-8). Frame (`regulation-legal` = 8) sorts strictly after the highest behavior (`psychology-disposition` = 7).

**Execution note (Phase 16, NOT executed here):** because `sort_order` is `UNIQUE`, the three `+1` UPDATEs must not transiently collide with an existing value. The existing rows must move **highest-first** — `regulation-legal 7→8`, then `psychology 6→7`, then `governance 5→6` — **then** INSERT `negotiation` at the now-vacant 5; or run all moves inside one transaction with a deferrable unique constraint. The highest-first mechanic needs no deferrable constraint and is the safer option. This is a Phase-16 *write* detail; Phase 15 only documents that the reshuffle is **collision-free** and **permitted** (`blocks` has no append-only trigger — 033 §8 guards only `block_body_versions` + `timeline_entries`).

---

## D-04 hub schema accommodation (pinned for Phase 16)

**Problem:** the hub `agent-economy` has `type: hub` and **no tier**; `blocks.tier` is `NOT NULL CHECK (tier IN ('substrate','behavior','frame'))` (033:68), and `block_body_versions.block_slug` FKs `blocks(slug) ON DELETE RESTRICT` (033:96). So the hub body **cannot live in `block_body_versions` without a `blocks` row**, which cannot exist without a valid `tier`.

**Pinned accommodation = Option A: relax the tier CHECK to add a `'hub'` sentinel tier** (a clean, separately-reviewable new migration in Phase 16 — e.g. `043`, `DROP CONSTRAINT blocks_tier_check` then `ADD CONSTRAINT blocks_tier_check CHECK (tier IN ('substrate','behavior','frame','hub'))`).

**Why Option A over the alternatives:**

- **vs Option B (nullable tier — `ALTER COLUMN tier DROP NOT NULL`) — REJECTED:** Option B drops `NOT NULL` for **every** block row to accommodate one hub row, opening a **silent tier-less-block surface** — a future buggy insert of a tier-less *block* (not hub) would slip past the column constraint and vanish from all grids. This violates fail-loud / structural-over-application: a missing tier should be **loud**, not a valid NULL. Option A keeps `tier NOT NULL` and makes "hub" an explicit, greppable, enumerated value.
- **vs Option C (dedicated hub table + parallel RPC) — REJECTED:** Option C is **net-new FK + RLS + RPC + append-only trigger** (a parallel `publish_hub_version` or a polymorphic rewrite of the SECURITY DEFINER publish path). It **violates D-04's explicit "reuse `publish_block_version` unchanged"** and maximizes blast radius on the governance path the spine warns against — for the smallest gain.

**Consequences that make Option A safe (D-04):**
- The hub becomes an **ordinary `blocks` row** — `slug='agent-economy'`, `tier='hub'`, `sort_order=0`, `accent='gray'`, `live_tension='TBD — set via /map-tension'`, `maturity` default.
- Its body lives in `block_body_versions` under the **existing FK** (no net-new FK).
- **`publish_block_version` works UNCHANGED** — it is slug-generic; step 4's `UPDATE blocks ... WHERE slug=v_slug` (039:73–77) finds the hub row. (No net-new RPC; reuse the existing gated RPC.)
- **`renderHub`'s three `tier === 'substrate'|'behavior'|'frame'` filters naturally EXCLUDE the hub row** from all grids — **no card duplication** (the hub does not appear as a card in its own grid).
- **Render reuses `marked.parse`** (app.js:586) with a **graceful fallback** to the existing `HUB_STORYLINE` constant (app.js:32) when no published hub body exists — preserving today's behavior pre-publish. (No net-new UI capability; the markdown render path already exists.)
- The hub body is **RLS-gated** by the existing `status='published'` anon policy (033:370) exactly like every block (no net-new RLS).

The existing **XSS-via-markdown disposition** (threat T-04-03-01, compensating control = operator publish gate via the RPC) **carries over unchanged**, because the hub publishes through the same gated RPC (D-04 routes the hub through it).

**Explicitly: this DDL is NOT applied in Phase 15** — Option A is the **instruction for Phase 16**. Cite D-04.

---

## Doc-vs-live divergence flags

The three divergences from `15-RESEARCH.md §ROST-01` — each a documentation-consistency note, **not a code defect**:

- **F-1 (expected / benign):** doc frontmatter `maturity: building` on slugs 1/2/3 (`identity-trust` / `memory-context` / `payments-settlement`) vs the loaded `emerging`. This is the **intended D-01 remap**, not an error — the **Phase-16 loader** is the single point that substitutes `building→emerging` before the `block_body_versions` INSERT. The frontmatter is left as-is (CONTEXT canonical_refs: frontmatter is the metadata source of truth, "remapped per D-01"). The planner must ensure the loader does the substitution, **not a doc edit**.
- **F-2 (ROADMAP / Phase-17 wording lag):** ROADMAP SC#2 and Phase-17 SC#2 still say the preview pills show `building`. After D-01 the three substrate pills render **`emerging`** (stage 2), not `building`. Phase-17's verification text should read **`emerging`** for slugs 1/2/3. (D-01 is the authoritative resolution; this is a text-consistency note only.)
- **F-3 (no `08-regulation-legal.md` doc):** intentional per D-02 — `regulation-legal` stays a **deferred, body-less frame card**. No `08-regulation-legal.md` is expected this milestone; the EU AI Act tracker feeds the slot later.

---

*This reconciliation is the **operator-approval target** — no `economy_map` write happens until it is approved (D-05). Phase 16 executes the load/reshuffle and applies the Option-A hub-tier migration; Phase 18 runs the publish RPC. Phase 15 writes nothing: no migration applied, no `app.js` edit, no `economy_map` write.*
