# Roadmap: AgentPulse — The Agent Economy (Living Reference Articles)

## Milestones

- ✅ **v1.0 Agent Economy Map** — Phases 1–10 + 4.1 (shipped 2026-06-04) — full details: [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 Frontend Redesign** — Phases 11–14 (shipped 2026-06-08) — full details: [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md)
- 🚧 **v2.1 Agent Economy Content** — Phases 15–18 (planning) — fill the v2.0 grid with the hub + 7 block bodies and publish in one gated batch.

_Active milestone: v2.1. Next milestone: run `/gsd-new-milestone` (questioning → research → requirements → roadmap)._

## Phases

<details>
<summary>✅ v1.0 Agent Economy Map (Phases 1–10 + 4.1) — SHIPPED 2026-06-04 — 11 phases, 29 plans</summary>

- [x] Phase 1: Render-Stack Diagnostic (1/1) — completed 2026-05-26
- [x] Phase 2: `economy_map` Schema + Seven-Block Seed (2/2) — completed 2026-05-27
- [x] Phase 3: Design Tokens (3/3) — completed 2026-05-27
- [x] Phase 4: Hub, Block, and Status Renderer (6/6) — completed 2026-05-28
- [x] Phase 4.1: Prod↔Main Reconciliation + LLM-Proxy Governance Migration (3/3) — completed 2026-05-28
- [x] Phase 5: Intake Classifier + `unsorted` Handling (3/3) — completed 2026-05-28
- [x] Phase 6: Telegram Read-Only Scaffolding (2/2) — completed 2026-05-30
- [x] Phase 7: Synthesis Loop Core (2/2) — completed 2026-06-01
- [x] Phase 8: Validation Sentinels (2/2) — completed 2026-06-02
- [x] Phase 9: Gated Publishing + Approval Commands (2/2) — completed 2026-06-03
- [x] Phase 10: Operator Write Commands (3/3) — completed 2026-06-04

Full phase details, goals, success criteria, and per-plan breakdown archived in [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md).

</details>

<details>
<summary>✅ v2.0 Frontend Redesign (Phases 11–14) — SHIPPED 2026-06-08 — 4 phases, 8 plans</summary>

UI-only redesign of the public `aiagentspulse.com` SPA: persistent stateful 3-tab nav shell, editorial Source Serif 4 / IBM Plex Mono typography, single light-mode violet accent (replacing the dark map theme), the Agent Economy as a responsive grouped card grid, a Newsletter-only mode toggle, and a "What is AgentPulse" About page. Frontend-only — no backend/pipeline/Supabase/content changes. Deployed live via the scoped `agentpulse-web` rebuild.

- [x] Phase 11: Design System + Nav Shell (2/2) — completed 2026-06-04 (NAV-01..04, TYPE-01..03, COLOR-01..02)
- [x] Phase 12: Newsletter Section Restyle (2/2) — completed 2026-06-04 (TGL-01, TGL-02)
- [x] Phase 13: Agent Economy Grid (2/2) — completed 2026-06-05 (MAP-01..04)
- [x] Phase 14: About Stub + Polish Pass (2/2) — completed 2026-06-08 (ABOUT-01, POLISH-01)

Full phase details, goals, success criteria, and per-plan breakdown archived in [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md).

</details>

### 🚧 v2.1 Agent Economy Content (Phases 15–18)

Fill the v2.0 grid — currently 5/7 blocks unpublished — with real editorial content: load the hub `agent-economy` + 7 block bodies into `economy_map` as unpublished, wire the `#/map/<slug>` cross-block links, verify on a non-published preview route, then publish live in ONE operator-approved batch. Content-only — no UI redesign, no pipeline / proxy / agent-service changes. Honors the spine: intake/load is reversible and unpublished by default; **publishing is the final gated, operator-approved step.** Direct PostgREST + `Accept-Profile` (no `.in_()`); append-only trigger → canonical-body-rewrite (never raw UPDATE); fail-loud on missing fields; branch + `/diff` + web-only scoped deploy.

- [x] **Phase 15: Inventory & Roster Reconciliation** — Confirm the live storage/serve contract + maturity enum, and resolve the per-slug roster diff before any write (read-before-write, operator-approved plan). (completed 2026-06-08)
- [x] **Phase 16: Content Load (unpublished)** — Load all 8 canonical bodies into `economy_map` as unsorted/unpublished, fail-loud on missing fields, correct existing rows via the rewrite path — zero change for live visitors. (completed 2026-06-08)
- [x] **Phase 17: Cross-link Wiring & Preview** — Make every `#/map/<slug>` cross-block + hub→block link resolve, and verify the loaded-but-unpublished content end-to-end on a non-published preview route. (completed 2026-06-09)
- [ ] **Phase 18: Gated Batch Publish** — Publish the content live via the existing atomic publish RPC in ONE operator-approved batch (web-only scoped deploy).

## Phase Details

### Phase 15: Inventory & Roster Reconciliation

**Goal**: The live `economy_map` storage + serve contract is documented from the running system (not assumed), and the per-slug roster diff vs the docs is resolved with an explicit, operator-approved disposition — so no write happens before the contract and the roster are locked.
**Depends on**: Nothing (first v2.1 phase; v2.0 renderer already shipped)
**Requirements**: INV-01, INV-02, ROST-01
**Success Criteria** (what must be TRUE):

  1. The block data contract (slug / tier / title / subtitle / order / maturity / body / timeline), the append-only trigger behavior, and the atomic publish RPC are each documented from the live schema — a reader can see exactly how a block is stored and published without reading code.
  2. The live `maturity` enum is verified against the three doc values (`building` / `contested` / `nascent`); any mismatch is surfaced explicitly with a resolution, never silently remapped.
  3. The roster diff is resolved per slug with a written disposition (first-publish vs body-rewrite vs retire): `negotiation-coordination` (added; v2.0-deferred), the live `regulation-legal` (omitted from docs), and the tier model (docs' 2 tiers vs the live 3) each have a decision.
  4. The reconciliation plan is presented for operator approval before any block is written — the "read before writing, I approve" gate from the brief is satisfied.**Plans**: 2 plans

**Wave 1**

  - [x] 15-01-PLAN.md — Write 15-CONTRACT.md (live storage+serve contract + verified maturity enum: INV-01/INV-02) and 15-RECONCILIATION.md (per-slug roster disposition + D-04 hub pin + D-03 collision-free reshuffle: ROST-01)

**Wave 2** *(blocked on Wave 1 completion)*

  - [x] 15-02-PLAN.md — Operator-approval gate: present both docs, record the read-before-write approval before any Phase 16 write (SC#4)

### Phase 16: Content Load (unpublished)

**Goal**: All in-scope canonical bodies (hub `agent-economy` + the reconciled blocks) land in `economy_map` as unsorted/unpublished, using the YAML frontmatter as the metadata source of truth — content is present in the store with zero change for live visitors, and the load refuses to land anything blank or partial.
**Depends on**: Phase 15 (roster + contract + enum locked)
**Requirements**: LOAD-01, LOAD-02, LOAD-03
**Success Criteria** (what must be TRUE):

  1. Every in-scope body is present in `economy_map` as unsorted/unpublished, with metadata (slug/tier/title/subtitle/order/maturity) taken verbatim from the frontmatter — and the live `#/map` is unchanged for visitors (nothing newly visible).
  2. The load halts loud with a clear error on any missing/empty required field (empty body, null maturity) and lands no blank or partial block — a deliberately broken input is rejected, not published.
  3. Existing live rows for matching slugs are corrected via the canonical-body-rewrite path (the append-only trigger is respected — no raw UPDATE), and no duplicate block rows are created for any slug.
  4. All `economy_map` access in the load uses direct PostgREST + `Accept-Profile` (no supabase-py `.in_()`).

**Plans**: 3 plans

**Wave 1** *(parallel — no file overlap)*

  - [x] 16-01-PLAN.md — Migration 043 (structure): tier-CHECK relax → admit `'hub'`, INSERT hub + negotiation `blocks` rows, collision-free highest-first `sort_order` reshuffle to {0..8}; orchestrator applies via Supabase MCP (LOAD-01)
  - [x] 16-02-PLAN.md — Standalone PostgREST body loader (`scripts/load_economy_map_content.py`): validate-all-then-insert, `building→emerging` remap, idempotent skip-if-open-draft + deliberately-broken-fixture negative test (LOAD-01, LOAD-02, LOAD-03)

**Wave 2** *(blocked on Wave 1 — 043 live + loader authored)*

  - [x] 16-03-PLAN.md — Run the loader against the live DB after 043 is applied; capture the SC#1 before/after anon-perspective evidence (zero new published rows) + record the LOAD-03 canonical-body-rewrite posture and idempotent re-run (LOAD-01, LOAD-03)

### Phase 17: Cross-link Wiring & Preview

**Goal**: The loaded-but-unpublished content renders correctly and is fully navigable on a non-published preview route — every `#/map/<slug>` cross-block link and every hub→block click-through resolves to the right page, maturity pills render the three values, and the hub presents as the `#/map` landing without a duplicated block list — proving the content is publish-ready before any publish.
**Depends on**: Phase 16 (content loaded)
**Requirements**: LINK-01, PREV-01, HUB-01
**Success Criteria** (what must be TRUE):

  1. Every `#/map/<slug>` cross-block link inside the bodies resolves to the correct block page, and the hub's block entries are clickable through to their deep-dive pages (no dead or mis-routed links).
  2. The loaded-but-unpublished content renders correctly on a non-published preview route — maturity pills show the three values (`building` / `contested` / `nascent`) and cross-links + hub→block click-through work end-to-end — with the live published site still unchanged.
  3. The hub renders as the `#/map` landing: thesis + two-tier framing as the intro above the block grid, with the block list appearing once (cards), not duplicated as both prose links and cards.
  4. Any router/renderer fix needed to make existing links resolve stays content-scoped — no net-new UI feature is introduced (the v2.0 renderer is reused, not redesigned).

**Plans**: 2 plans

**Wave 1**

  - [x] 17-01-PLAN.md — Content-scoped app.js render path: dormant PREVIEW_ENABLED flag (D-04), read-only draft-fetch fallback in loadBlock (D-03), hub draft-body intro + Tier-1/Tier-2 prose-list trim in renderHub (D-06a/c) — ships a prod no-op (LINK-01, PREV-01, HUB-01)

**Wave 2** *(blocked on Wave 1 — renders the path under test)*

  - [x] 17-02-PLAN.md — Fail-loud cross-link harness (D-05) + service_role-key diff guard (D-02), local elevated preview container (D-01/D-02), operator manual click-through checkpoint (PREV-01, LINK-01, HUB-01)

### Phase 18: Gated Batch Publish

**Goal**: The reconciled, loaded, preview-verified content goes live in ONE operator-approved batch via the existing atomic publish RPC and a web-only scoped deploy — afterward the hub renders at `#/map` and every published block renders at `#/map/<slug>` with the full reading surface.
**Depends on**: Phase 17 (preview-verified, publish-ready)
**Requirements**: PUB-01
**Success Criteria** (what must be TRUE):

  1. The content is published live via the existing atomic publish RPC in ONE operator-approved batch — the publish is explicitly gated (operator approves the batch before it goes live), never a blind/full deploy.
  2. After publish, the hub renders at `#/map` (filling the previously 5/7-unpublished grid) and every published block renders at `#/map/<slug>` with back arrow, title, subtitle, maturity pill, and body.
  3. The deploy is web-only and scoped (branch + `/diff` + the `agentpulse-web` rebuild) — the pipeline, LLM proxy, and agent services are untouched.

**Plans**: TBD

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Render-Stack Diagnostic | v1.0 | 1/1 | Complete | 2026-05-26 |
| 2. economy_map Schema + Seed | v1.0 | 2/2 | Complete | 2026-05-27 |
| 3. Design Tokens | v1.0 | 3/3 | Complete | 2026-05-27 |
| 4. Hub/Block/Status Renderer | v1.0 | 6/6 | Complete | 2026-05-28 |
| 4.1. Prod Reconciliation + Governance | v1.0 | 3/3 | Complete | 2026-05-28 |
| 5. Intake Classifier | v1.0 | 3/3 | Complete | 2026-05-28 |
| 6. Telegram Read-Only Scaffolding | v1.0 | 2/2 | Complete | 2026-05-30 |
| 7. Synthesis Loop Core | v1.0 | 2/2 | Complete | 2026-06-01 |
| 8. Validation Sentinels | v1.0 | 2/2 | Complete | 2026-06-02 |
| 9. Gated Publishing + Approval | v1.0 | 2/2 | Complete | 2026-06-03 |
| 10. Operator Write Commands | v1.0 | 3/3 | Complete | 2026-06-04 |
| 11. Design System + Nav Shell | v2.0 | 2/2 | Complete | 2026-06-04 |
| 12. Newsletter Section Restyle | v2.0 | 2/2 | Complete | 2026-06-04 |
| 13. Agent Economy Grid | v2.0 | 2/2 | Complete | 2026-06-05 |
| 14. About Stub + Polish Pass | v2.0 | 2/2 | Complete | 2026-06-08 |
| 15. Inventory & Roster Reconciliation | v2.1 | 2/2 | Complete    | 2026-06-08 |
| 16. Content Load (unpublished) | v2.1 | 3/3 | Complete    | 2026-06-08 |
| 17. Cross-link Wiring & Preview | v2.1 | 2/2 | Complete    | 2026-06-09 |
| 18. Gated Batch Publish | v2.1 | 0/? | Not started | - |

## Backlog

Parked for a future milestone — **not scheduled, not for now**. Surfaces at next `/gsd-new-milestone` planning. Source-of-truth detail lives in `.planning/todos/pending/`.

### Backend follow-ups (candidate: a backend-hardening milestone)

Carried forward from v1.0; out of v2.0 (frontend) scope.

- analyst predictions `title` expire bug (P2)
- soft-cap allow-negative hardening (P5)
- pay-endpoint 500 activation E2E — RPC root-cause fixed in migration 037 (P2)
- phase-05 intake-classifier review follow-ups WR02/04/05 (P4)
- research trigger file permissions (P4)

### Agent Economy content (separate workstream, drafts already staged)

Surfaced by the v2.0 live-site UAT: 5 of 7 economy-map blocks are unpublished (deferred), so the map reads as one column and the hub storyline subtitle is stale. Publishing the bodies un-defers them.

- Publish the hub + 7 block bodies to the live `#/map` (drafts staged untracked in `.planning/docs/00-hub.md … 07-*.md` + `EXECUTION_BRIEF.md`).
