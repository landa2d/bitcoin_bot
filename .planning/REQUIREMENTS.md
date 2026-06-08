# Requirements — Milestone v2.1: Agent Economy Content

**Goal:** Publish the Agent Economy hub + 7 block bodies live on `aiagentspulse.com/#/map`, with the hub's blocks clickable through to their deep-dive pages — filling the v2.0 grid (currently 5/7 blocks unpublished) with real editorial content.

**Source content:** `.planning/docs/00-hub.md` … `07-psychology-disposition.md` (+ `EXECUTION_BRIEF.md`). YAML frontmatter (slug/tier/title/subtitle/order/maturity) is the metadata source of truth.

**The spine (standing constraints):** Intake/load is reversible and unpublished by default; **publishing is the gated, operator-approved step**. Direct PostgREST + `Accept-Profile` for `economy_map` (never supabase-py `.in_()`); append-only trigger — corrections via the canonical-body-rewrite path, never a raw UPDATE; fail-loud on any missing field; branch + `/diff` + web-only scoped deploy — no pipeline / proxy / agent-service changes.

## v2.1 Requirements

### Inventory & Roster Reconciliation
<!-- The brief's section 0 + 5: confirm the contract and resolve the slug/tier diff BEFORE any load. -->
- [ ] **INV-01**: The current `economy_map` storage + serve contract is confirmed before any write — block data contract (slug/tier/title/subtitle/order/maturity/body/timeline), the append-only trigger behavior, and the atomic publish RPC are documented from the live schema (not assumed).
- [ ] **INV-02**: The maturity enum is verified against the three doc values (`building` / `contested` / `nascent`); any mismatch with the live enum is surfaced and resolved explicitly — never silently remapped.
- [ ] **ROST-01**: The block-roster diff vs the live map is resolved with an explicit per-slug disposition before load — `negotiation-coordination` (added; v2.0-deferred), the live `regulation-legal` (omitted from docs; retire vs keep), and the tier model (docs' 2 tiers vs the live 3) — first-publish vs body-rewrite vs retire decided for each.

### Content Load (unpublished)
- [ ] **LOAD-01**: All canonical bodies (hub `agent-economy` + the in-scope blocks) are loaded into `economy_map` as unsorted/unpublished, using the frontmatter as the metadata source of truth — content lands with zero change for live visitors.
- [ ] **LOAD-02**: The load fails loud on any missing/empty required field (empty body, null maturity) — it halts with a clear error and never lands a blank or partial block.
- [ ] **LOAD-03**: Existing live rows for matching slugs are corrected via the canonical-body-rewrite path (not a raw UPDATE the append-only trigger rejects); no duplicate block rows are created.

### Cross-link Wiring & Preview
- [ ] **LINK-01**: Every `#/map/<slug>` cross-block link inside the bodies resolves to the correct block page, and the hub's block entries are clickable through to their deep-dive pages.
- [ ] **PREV-01**: The loaded-but-unpublished content renders correctly on a non-published preview route before any publish — maturity pills show the three values, cross-links resolve, and hub→block click-through works end-to-end.

### Hub Presentation
- [ ] **HUB-01**: The hub renders as the `#/map` landing — thesis + two-tier framing as the intro above the block grid, with the block list appearing once (cards preferred), not duplicated as both prose links and cards.

### Gated Publish
- [ ] **PUB-01**: The content is published live via the existing atomic publish RPC in ONE operator-approved batch (web-only scoped deploy) — afterward the hub renders at `#/map` and every published block renders at `#/map/<slug>` with back arrow, title, subtitle, maturity pill, and body.

## Future Requirements (deferred)
- Evolution timeline content — intake fills the per-block append-only timeline weekly; bodies publish now with timelines that may be empty. No manual timeline authoring this milestone.
- Distinct visual treatment for `nascent`-maturity blocks beyond the pill (open item — default is pill-only unless discuss-phase decides otherwise).
- Carried-forward v1.0 backend todos (analyst title bug, soft-cap hardening, pay-endpoint E2E, phase-05 review follow-ups, research perms) — out of this content milestone; in the ROADMAP backlog.

## Out of Scope
- **Pipeline / proxy / agent-service changes** — content-publish only; the brief forbids touching the pipeline, LLM proxy, or agent services.
- **New frontend features / restyle** — the v2.0 renderer already displays hub + blocks correctly (verified in v2.0 UAT); this milestone fills it with content, it does not change the UI. Router/renderer bug-fixes needed to make existing links resolve are in scope under LINK-01; net-new UI is not.
- **Schema redesign** — reuse the existing append-only `economy_map` schema and publish RPC; no migration beyond what reconciliation strictly requires.
- **Blind/full deploy** — never a blanket `scripts/deploy.sh`; web-only scoped, branch + diff + approved batch publish.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| INV-01 | Phase 15 | Pending |
| INV-02 | Phase 15 | Pending |
| ROST-01 | Phase 15 | Pending |
| LOAD-01 | Phase 16 | Pending |
| LOAD-02 | Phase 16 | Pending |
| LOAD-03 | Phase 16 | Pending |
| LINK-01 | Phase 17 | Pending |
| PREV-01 | Phase 17 | Pending |
| HUB-01 | Phase 17 | Pending |
| PUB-01 | Phase 18 | Pending |
