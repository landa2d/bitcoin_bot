# Phase 15 — `economy_map` Storage + Serve Contract (INV-01, INV-02)

**Assembled:** 2026-06-08
**Source authority:** in-tree migration SQL (`033`, `038`, `039`, `041`) + `docker/web/site/app.js` (CONTEXT D-05). No live `SELECT` issued; no write performed.
**Citation key:** `(033:LINE)` = `supabase/migrations/033_economy_map_schema.sql`; `(039:LINE)` = `supabase/migrations/039_publish_block_version_watermark_null_guard.sql`; `(041:LINE)` = `supabase/migrations/041_block_body_versions_unique_open_draft.sql`; `(app.js:LINE)` = `docker/web/site/app.js`.

This is the live contract a downstream reader can verify without reading code. Phase 16/18 execute from it. Every stated fact carries its source line.

---

## Block data contract (economy_map.blocks)

The block's identity, ordering, maturity, and pointer-to-current-body live in `economy_map.blocks` (033 §4, table at 033:65–78). The 8 load-relevant columns:

| Column | Type | Constraint | Source |
|--------|------|-----------|--------|
| `slug` | TEXT | **NOT NULL UNIQUE** — the seven slugs; FK target for `block_body_versions.block_slug` | (033:67) |
| `tier` | TEXT | **NOT NULL `CHECK (tier IN ('substrate','behavior','frame'))`** — exactly 3 tiers, no `'hub'`, no NULL | (033:68) |
| `title` | TEXT | NOT NULL | (033:69) |
| `subtitle` | TEXT | NOT NULL — one-line hub caption | (033:70) |
| `accent` | TEXT | NOT NULL `CHECK (accent IN ('teal','purple','coral','gray'))` | (033:71) |
| `sort_order` | INTEGER | **NOT NULL UNIQUE** — a PLAIN updatable column, **NO append-only trigger** | (033:72) |
| `maturity` | `economy_map.maturity` (ENUM) | **NOT NULL DEFAULT `'nascent'`** — synced by the publish RPC | (033:74) |
| `current_body_version_id` | UUID | FK → `block_body_versions(id) ON DELETE SET NULL`, **nullable** — points at the live published body | (033:75, 129–133) |

**Key fact:** `economy_map.blocks` has **NO append-only trigger** — the two append-only triggers (033 §8) are on the *content* tables only. Therefore `sort_order` (and `maturity`, `current_body_version_id`, `last_synthesized_at`, `live_tension`) are permitted plain `UPDATE`s. This is the load-bearing fact for the D-03 reshuffle: the `sort_order` renumbering is a permitted column update, not a body-rewrite. (`live_tension` is NOT NULL, seeded with the placeholder `'TBD — set via /map-tension'` (033:73, 406–414); `last_synthesized_at` is a nullable watermark advanced by the publish RPC (033:76).)

---

## Body storage (economy_map.block_body_versions)

The block **body lives here, not in `blocks`** (033 §5, table at 033:94–105). Each row is one synthesis attempt; the live body is reached via `blocks.current_body_version_id`.

| Column | Type | Constraint | Mutability |
|--------|------|-----------|-----------|
| `block_slug` | TEXT | NOT NULL **FK → `blocks(slug)` `ON DELETE RESTRICT`** | **pinned** (immutable post-insert) (033:96) |
| `body_md` | TEXT | NOT NULL | **pinned** (033:97) |
| `status` | TEXT | NOT NULL DEFAULT `'draft'` **`CHECK (status IN ('draft','published','superseded'))`** | **lifecycle (mutable by RPC)** (033:98–99) |
| `proposed_maturity` | `economy_map.maturity` | **NOT NULL** | **pinned at insert** (033:100) |
| `published_at` | TIMESTAMPTZ | nullable | lifecycle (mutable by RPC) (033:103) |

**Status is TEXT + CHECK, not a Postgres ENUM** — the three values `draft` / `published` / `superseded` (033:98–99). The `maturity` ENUM and the `status` CHECK are different mechanisms.

**`proposed_maturity` is pinned (append-only) AND NOT NULL** (033:100). Consequence for D-01: the `building→emerging` remap **MUST produce a valid enum member at INSERT time** — the append-only trigger forbids any later UPDATE of `proposed_maturity` (033:194–196), so there is no "fix it after insert" path; the loader must substitute before the INSERT.

**Migration-041 invariant — at most ONE open draft per slug:** `CREATE UNIQUE INDEX uq_block_body_versions_one_open_draft ON block_body_versions (block_slug) WHERE status = 'draft'` (041:20–21). At most one `draft` row per `block_slug` at a time; the processor catches the resulting `23505` as a logged benign skip. Relevant to Phase 16 loading the hub + the new negotiation block — each slug may hold only one open draft.

---

## Append-only triggers — what they guard

There are **exactly 2** append-only triggers (`grep -v '^--' 033 | grep -c "CREATE TRIGGER"` = 2):

| Trigger | Table | Fires on | Behavior |
|---------|-------|----------|----------|
| `block_body_versions_append_only_trg` | `block_body_versions` | `BEFORE UPDATE OR DELETE` (033:209–211) | DELETE always raises (033:183–185); UPDATE raises if any of `body_md` / `synthesized_from_through` / `proposed_maturity` / `validator_report` / `block_slug` change (033:188–202). **`status` and `published_at` ARE allowed to change** — this is what lets the publish RPC flip draft→published. |
| `timeline_entries_append_only_trg` | `timeline_entries` | `BEFORE UPDATE OR DELETE` (033:251–253) | DELETE always raises; UPDATE raises on **any** column change — fully immutable (033:224–244). |

**There is NO trigger on `economy_map.blocks`** — confirmed by absence (`grep "TRIGGER.*ON economy_map.blocks" 033` returns nothing); only the two `CREATE TRIGGER` statements above exist, both naming the content tables. This is why the D-03 `sort_order` reshuffle is permitted.

**Why triggers, not RLS** (033 §8 comment, 033:166–175): content immutability must hold **against `service_role`**, which **bypasses RLS by design** — the agents use `SUPABASE_SERVICE_KEY`. RLS cannot bind `service_role`; only a `BEFORE UPDATE/DELETE` trigger can. (033:170 records the lineage: "The pipeline that produced the 27-day silent wallet bug ran as service_role." Structural-over-application, fail-loud.)

---

## Atomic publish RPC (publish_block_version)

**Signature:** `economy_map.publish_block_version(p_version_id uuid) RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = economy_map, public` (039:33–38). `SET search_path` is the T-02 search-path-hijack mitigation pinned on the SECURITY DEFINER function (039:37).

**Service_role-only:** `REVOKE ALL ... FROM PUBLIC` (039:81) then `GRANT EXECUTE ... TO service_role` (039:82).

**Current authoritative body = migration 039.** 033 was the original (033:267–307, which stamped `last_synthesized_at = NOW()` at 033:304); 038 introduced the watermark; **039 added the COALESCE NULL-guard** and is the body to document. (033's RPC is superseded by 039 via `CREATE OR REPLACE FUNCTION` — same signature, new body.)

The atomic **4 steps**, all one PL/pgSQL function call = **one transaction** (either all commit or all roll back):

1. **Atomic draft→published flip** — `UPDATE block_body_versions SET status='published', published_at=NOW() WHERE id=p_version_id AND status='draft' RETURNING block_slug, proposed_maturity, synthesized_from_through` (039:49–55). The `AND status='draft'` + `RETURNING` is the **single-winner race property**: a concurrent publish-race loses (empty RETURNING).
2. **Fail-loud** — `IF v_slug IS NULL THEN RAISE EXCEPTION 'version % not found or not in draft status'` (039:58–59). Not-found / not-draft surfaces as a typed exception, never a silent no-op.
3. **Supersede the prior published version for that slug** — `UPDATE block_body_versions SET status='superseded' WHERE block_slug=v_slug AND status='published' AND id<>p_version_id` (039:63–67).
4. **Point the block at the new version + sync maturity + advance watermark** — `UPDATE blocks SET current_body_version_id=p_version_id, maturity=v_maturity, last_synthesized_at=COALESCE(v_synthesized_from_through, last_synthesized_at) WHERE slug=v_slug` (039:73–77). The COALESCE NULL-guard (039:76) leaves the watermark unchanged when the draft's `synthesized_from_through` is NULL (the cold-start sentinel) — a missing window bound declines to advance, never resets.

The append-only trigger is **not** implicated: steps 1/3 mutate only the lifecycle columns (`status`, `published_at`) and step 4 writes a *different* table (`blocks`, untriggered).

(`reject_block_version(p_version_id uuid)` is the sibling RPC: SECURITY DEFINER, service_role-only, flips the draft → `superseded` and stops (033:319–342) — unchanged since 033.)

---

## Read boundary (RLS — what anon sees)

RLS is the read boundary; `service_role` bypasses it (033 §11). The anon SELECT policies (033:356–376):

| Table | anon SELECT policy | Effect | Source |
|-------|--------------------|--------|--------|
| `blocks` | `USING (true)` | anon sees **all** block rows, including deferred / body-less | (033:361–364) |
| `block_body_versions` | `USING (status = 'published')` | anon sees **only published bodies** — drafts/superseded invisible | (033:367–370) |
| `timeline_entries` | `USING (block_slug <> 'unsorted')` | anon sees all classified entries; `'unsorted'` hidden | (033:373–376) |

The `block_body_versions` published-only policy (033:370) is the reason a Phase-16 unpublished load is **invisible to visitors** until the Phase-18 publish RPC runs. PostgREST needs BOTH the RLS pass AND a table grant — `GRANT SELECT ... TO anon` (033:384–386) and `GRANT USAGE ON SCHEMA economy_map TO anon` (033:25).

---

## Hub serve path (current)

The `#/map` landing renders the **hardcoded `HUB_STORYLINE` JS constant** (app.js:32: `'Synthesis with editorial integrity. Eight blocks, seven shipped, one deferred …'`), emitted **`escapeHtml`'d as plain text** at app.js:496 (`'<div class="hub-storyline">' + escapeHtml(HUB_STORYLINE) + '</div>'`). **The hub is NOT DB-served today** — no `block_body_versions` row backs it.

Block bodies, by contrast, render via **`marked.parse(bodyMd)`** at app.js:586 — fetched by `current_body_version_id`, RLS-gated to published (the only markdown-execution path on a block page). `renderHub` groups blocks by tier and emits three grids; **any row whose `tier` is not one of the three is silently excluded from all grids** (the literal `b.tier === 'substrate'|'behavior'|'frame'` filters).

(The D-04 accommodation that gives the hub a DB-served home — relax the tier CHECK to admit a `'hub'` sentinel tier, reuse `publish_block_version` + `marked.parse` unchanged — is documented in `15-RECONCILIATION.md §D-04`, **not** here. This section records only the *current* serve behavior.)

---

## Maturity enum (INV-02)

The live `economy_map.maturity` ENUM has **5 members, verbatim in order** (033:46–52):

```
nascent, emerging, contested, consolidating, mature
```

**`building` is NOT a member.** A `block_body_versions` INSERT with `proposed_maturity = 'building'` is **rejected loud by the enum** at write time (`invalid input value for enum`) — confirmed by `building` being absent from the 033 enum definition. This is the structural backstop the D-01 remap front-runs.

On the render side, `MATURITY_STAGE` (app.js:38) maps `{ nascent: 1, emerging: 2, contested: 3, consolidating: 4, mature: 5 }` — so `emerging → stage 2`. `renderMaturityPill` falls back **unknown → stage 1** via `MATURITY_STAGE[b.maturity] || 1` (app.js:396) — the *silent* mis-fill (a stray `building` would render as stage 1) that the D-01 remap prevents.

**INV-02 resolution (D-01):** the docs' `building` maturity — carried by the three substrate slugs `identity-trust` / `memory-context` / `payments-settlement` — is an **operator-approved remap to `emerging`, applied at LOAD time (Phase 16)**, before the `block_body_versions` INSERT. **No `ALTER TYPE`, no app.js change.** `contested` and `nascent` are already members and pass through unchanged (mapping to stage 3 / stage 1). End-to-end: load substitutes `building→emerging` → publish RPC step 4 syncs `blocks.maturity = 'emerging'` → `MATURITY_STAGE['emerging'] = 2` → correct stage-2 pill. The mismatch is surfaced and resolved here, never silently remapped downstream.

**Flag F-2:** ROADMAP SC#2 / Phase-17 verification wording still says the preview pills show `building` — after D-01 the substrate trio renders **`emerging`** (stage 2). Phase-17's verification text should read `emerging` for slugs 1/2/3. (Documentation-consistency note, not a code defect; D-01 is the authoritative resolution.)

---

*This contract is documented from the in-tree migration SQL (`033`/`038`/`039`/`041`) + `app.js` — the authoritative source per CONTEXT D-05. No live `SELECT` was issued, and this plan performs no write to `economy_map`, applies no migration, and edits no `app.js`.*
