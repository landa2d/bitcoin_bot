# Phase 15: Inventory & Roster Reconciliation - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Document the **live** `economy_map` storage + serve contract (from the running schema, not assumed) and resolve the per-slug roster diff vs the canonical docs with an explicit, operator-approved disposition for each.

**This phase WRITES NOTHING to `economy_map`.** Its deliverable is (a) the documented contract — block data shape, the append-only trigger behavior, the atomic publish RPC, the maturity enum, the tier model, and the hub serve path — and (b) a per-slug reconciliation plan, presented for operator approval *before* Phase 16 loads anything ("read before writing, I approve" — EXECUTION_BRIEF §0, success criterion #4).

Requirements: INV-01 (contract), INV-02 (maturity enum), ROST-01 (roster diff).
</domain>

<decisions>
## Implementation Decisions

The four reconciliation calls below were resolved with the operator on 2026-06-08. All four locked the recommended disposition.

### Maturity enum reconciliation (INV-02)
- **D-01:** The live enum (migration `033` §3, also app.js `MATURITY_STAGE`) is **`nascent, emerging, contested, consolidating, mature`**. The docs' `building` is **not a member** — a `block_body_versions` insert with `proposed_maturity = 'building'` is rejected by the enum, and the pill mis-fills an unknown value as stage 1. **Resolution: explicit, operator-approved remap `building → emerging`**, applied **at load time** (Phase 16), so the three substrate blocks (`identity-trust`, `memory-context`, `payments-settlement`) load with `proposed_maturity = 'emerging'` (stage-2 pill). **No `ALTER TYPE`, no app.js change.** `contested` and `nascent` pass through unchanged. INV-02 is satisfied: the mismatch is surfaced and resolved here, never silently remapped downstream.

### Roster — `regulation-legal` + tier model (ROST-01)
- **D-02:** The live seed has `regulation-legal` (tier `frame`, seeded sort_order 7); the docs omit it. **Disposition: keep it as a deferred frame slot** — the seeded row stays **unpublished / body-less** this milestone and continues to render as a DEFERRED card. **The tier model stays at 3 (`substrate` / `behavior` / `frame`)** — app.js already renders all three tier sections; nothing collapses to 2 tiers. Aligns with the standing decision "regulation ships as a lightly-populated closing frame; the EU AI Act tracker feeds it over time" (PROJECT.md Key Decisions). **No content/publish write to this row** (a structural sort_order bump per D-03 is the only permitted touch).

### Roster — `negotiation-coordination` (ROST-01)
- **D-03:** The docs add `negotiation-coordination` (tier `behavior`, maturity `nascent`, order 5); it is **absent from the live seed** (v1.0 deliberately kept it as a section inside Payments). **Disposition: first-publish as a new behavior block.** Insert at `sort_order` 5 and **reshuffle** `governance-accountability` → 6 and `psychology-disposition` → 7 to match the doc order. **Collision note:** `regulation-legal` is seeded at sort_order 7, which now collides with `psychology-disposition` → 7; bump `regulation-legal` to **8** (structural sort_order-only update — keeps frame after behavior; does **not** violate D-02's "body-less / unpublished"). `blocks.sort_order` is a plain column (the append-only triggers guard `block_body_versions` and `timeline_entries`, **not** `blocks`), so the reshuffle is a permitted `UPDATE`.

### Hub serve path (INV-01)
- **D-04:** The hub `agent-economy` (`type: hub`, **no tier**) cannot be a `blocks` row (`tier ... NOT NULL CHECK (tier IN (...))`), and is **not currently DB-served** — `#/map` renders the hardcoded `HUB_STORYLINE` constant (escapeHtml'd plain text) above the grid. **Resolution: give the hub a DB-served home + markdown render, gated by the same `publish_block_version` RPC as the blocks** (honors the spine — every consequential publication goes through the gate). The **render side reuses the existing `marked.parse` block-body path** (app.js:586) — free, **no net-new UI capability**. The **net-new** work is (1) a *minimal* schema accommodation so the hub body can live in `block_body_versions` (e.g. relax the tier CHECK to admit a hub sentinel tier / nullable tier, or an equivalent hub home) and (2) a small `renderHub` change to fetch and `marked.parse` the hub's published body in place of / above the storyline. **The exact storage mechanism is for the researcher to pin against the live schema** (success criterion: documented from the live system). The existing XSS-via-markdown disposition (threat T-04-03-01, compensating control = operator publish gate) carries over unchanged.

### Standing constraints reaffirmed (the spine)
- **D-05:** Phase 15 produces a contract doc + reconciliation plan only — **no `economy_map` writes**; the plan is gated on operator approval before Phase 16.
- **D-06:** All `economy_map` access via **direct PostgREST + `Accept-Profile`** (never supabase-py `.in_()`); corrections via the **canonical-body-rewrite** path (never a raw UPDATE on append-only columns); **fail-loud** on any missing field; **branch + `/diff` + web-only scoped `agentpulse-web` rebuild** — no pipeline / proxy / agent-service changes.

### Claude's Discretion
- The **exact** hub schema accommodation (relaxed tier CHECK + sentinel tier vs nullable tier vs a dedicated hub home) is delegated to the researcher/planner — D-04 fixes the *path* (DB-served + RPC-gated + `marked.parse` reuse), not the precise DDL.
- The concrete sort_order renumbering mechanic (per D-03) is the planner's, provided the result is collision-free and frame sorts after behavior.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The brief & requirements (read first)
- `.planning/docs/EXECUTION_BRIEF.md` — the read-before-write brief. §0 = the inventory checklist this phase satisfies; §1 = canonical roster table; §4 = standing constraints; §5 = the open items resolved in this CONTEXT.
- `.planning/REQUIREMENTS.md` — INV-01, INV-02, ROST-01 (this phase); LOAD/LINK/PREV/HUB/PUB (downstream).
- `.planning/ROADMAP.md` — Phase 15 goal + the 4 success criteria (the verification target).

### Canonical content (metadata source of truth)
- `.planning/docs/00-hub.md` — hub `agent-economy` (no tier; subject of D-04).
- `.planning/docs/01-identity-trust.md … 07-psychology-disposition.md` — the 7 block bodies. **YAML frontmatter (slug/tier/title/subtitle/order/maturity) is the metadata source of truth** — use it, don't re-derive. `building` maturity on 01/02/03 is remapped per D-01.

### The live contract (document from these, verify against the live DB)
- `supabase/migrations/033_economy_map_schema.sql` — **the core contract**: `economy_map.maturity` ENUM (§3, the 5 values), `economy_map.blocks` (slug UNIQUE, `tier ... NOT NULL CHECK (substrate/behavior/frame)`, `maturity` DEFAULT nascent, `current_body_version_id`, `sort_order`), `block_body_versions` (append-only trigger; status draft/published/superseded; `proposed_maturity` pinned), `timeline_entries` (append-only), `publish_block_version()` RPC (atomic draft→published + supersede + sync maturity), RLS (anon sees only `status='published'` bodies + non-`unsorted` timeline), and the 7-block seed.
- `supabase/migrations/038_publish_block_version_watermark.sql`, `039_..._null_guard.sql` — publish RPC + watermark refinements.
- `supabase/migrations/040_operator_write_commands_schema.sql` — `synth_requests` queue + write RPCs + `reassigned_*` lifecycle.
- `supabase/migrations/041_block_body_versions_unique_open_draft.sql` — UNIQUE open-draft index (one open draft per slug).
- `supabase/migrations/042_reassign_timeline_entry_slug_validation.sql` — reassign hardening.

### The live serve path (frontend)
- `docker/web/site/app.js` — `MATURITY_STAGE` (l.38) + `TIER_LABELS` (l.41); `renderMaturityPill` (l.391, unknown→stage 1); `renderHub` (l.~420–503: reads `economy_map.blocks`, tier-groups, renders hardcoded `HUB_STORYLINE` above 3 tier grids); `loadBlock`/`renderBlock` (l.505–604: body from `block_body_versions.body_md` via `current_body_version_id`, RLS-gated to published, `marked.parse` at l.586).

### Project decision record
- `.planning/PROJECT.md` — Key Decisions table (regulation = closing frame; negotiation-in-Payments; append-only `block_body_versions`; schema isolation via direct PostgREST; sentinels flag-never-block) and the v2.0/v2.1 context.
- `.planning/codebase/ARCHITECTURE.md`, `STRUCTURE.md`, `CONVENTIONS.md` — service/data-flow maps.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`marked.parse(bodyMd)`** (app.js:250 for newsletter, :586 for block bodies) — the markdown renderer is **already loaded and is the live block-body render path**. D-04's hub render reuses it verbatim — markdown rendering is NOT a net-new UI capability.
- **`publish_block_version(p_version_id)` RPC** (migration 033) — the single atomic publish path (draft→published, supersede prior, point block at new version, sync maturity). Reused unchanged for blocks; D-04 routes the hub through it too.
- **`renderHub` / tier grouping** (app.js:~420–503) — already renders all 3 tiers (substrate/behavior/frame) and DEFERRED cards for body-less blocks; D-02's `regulation-legal` already renders correctly here today.
- **`renderMaturityPill` + `MATURITY_STAGE`** (app.js:38, 391) — maps the 5 enum values to a 1–5 fill; `emerging` → stage 2 (so D-01's remapped substrate blocks render correctly with no frontend change).

### Established Patterns
- **Append-only is trigger-enforced on `block_body_versions` + `timeline_entries`, NOT on `blocks`** — so D-03's `sort_order` reshuffle (and the regulation 7→8 bump) are permitted plain `UPDATE`s; body corrections, however, must use the canonical-body-rewrite path (new version + publish), never a raw UPDATE.
- **RLS is the read boundary** — anon only sees `status='published'` bodies; loading as unsorted/unpublished (Phase 16) is invisible to visitors until the publish RPC runs (Phase 18). Underpins D-05's "no visitor-facing change."
- **Seed idempotency** is `ON CONFLICT (slug) DO NOTHING` — adding `negotiation-coordination` (D-03) is a *new* structural row, not a re-seed.

### Integration Points
- **Hub schema home (D-04, net-new):** the hub body needs to live in `block_body_versions`, which FKs `block_slug → blocks(slug)` and requires a non-null tier. Minimal accommodation needed (researcher pins exact DDL). This is the only schema change reconciliation strictly requires.
- **`negotiation-coordination` (D-03):** a new `blocks` INSERT + `sort_order` UPDATEs on governance/psychology/regulation — likely a small migration (next number `043`) or a guarded structural insert; the body loads via the normal Phase 16 path.
- **Maturity remap (D-01):** applied entirely in the Phase 16 loader (frontmatter `building` → `emerging` before insert) — zero schema/frontend change.
</code_context>

<specifics>
## Specific Ideas

**Reconciled roster (the target state this phase locks):**

| order | slug | tier | maturity (loaded) | disposition |
|---|---|---|---|---|
| 0 | `agent-economy` (hub) | — (DB-served home per D-04) | — | first-publish (DB + `marked.parse`, RPC-gated) |
| 1 | `identity-trust` | substrate | `emerging` (was `building`) | first-publish |
| 2 | `memory-context` | substrate | `emerging` (was `building`) | first-publish |
| 3 | `payments-settlement` | substrate | `emerging` (was `building`) | first-publish |
| 4 | `autonomy-control` | behavior | `contested` | first-publish |
| 5 | `negotiation-coordination` | behavior | `nascent` | **new block** (graduated) |
| 6 | `governance-accountability` | behavior | `contested` | first-publish (sort_order 5→6) |
| 7 | `psychology-disposition` | behavior | `nascent` | first-publish (sort_order 6→7) |
| 8 | `regulation-legal` | frame | (unchanged) | **kept deferred** — body-less, sort_order 7→8 |

Result: **8 published bodies** (hub + 7 doc blocks) + `regulation-legal` retained as a deferred frame card = **9 block-level entries**, **3 tiers**.
</specifics>

<deferred>
## Deferred Ideas

- **Phase 17 (HUB-01) — presentation:** hub block-list as **cards vs prose links**, how much hub prose renders above the grid, and **distinct visual treatment for `nascent` blocks** beyond the pill. Explicitly out of Phase 15 — these are presentation decisions for Phase 17.
- **Evolution timeline content:** block bodies publish with possibly-empty timelines; intake fills them weekly. No manual timeline authoring this milestone (future requirement).
- **EU AI Act tracker → `regulation-legal` body:** the deferred frame slot (D-02) gets fed by the EU AI Act integration in a future milestone (EUAI-01/02), not now.

### Reviewed Todos (not folded)
The 7 pending todos (`.planning/todos/pending/`) were checked against this phase — all are **v1.0 backend follow-ups** (analyst predictions title-expire, soft-cap allow-negative hardening, pay-endpoint transfer RPC, phase-05/06/07 review follow-ups, research trigger file permissions). **None overlap** the `economy_map` content/roster domain; out of v2.1 content scope, parked in the ROADMAP backlog.
</deferred>

---

*Phase: 15-inventory-roster-reconciliation*
*Context gathered: 2026-06-08*
