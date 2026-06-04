# Roadmap: AgentPulse — The Agent Economy (Living Reference Articles)

## Milestones

- ✅ **v1.0 Agent Economy Map** — Phases 1–10 + 4.1 (shipped 2026-06-04) — full details: [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md)
- 🚧 **v2.0 Frontend Redesign** — Phases 11–14 (in progress) — UI-only public-site redesign per [`docs/REDESIGN_BRIEF.md`](docs/REDESIGN_BRIEF.md)

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

### 🚧 v2.0 Frontend Redesign (In Progress)

**Milestone Goal:** A UI-only redesign of the public `aiagentspulse.com` SPA — a persistent, stateful 3-tab nav shell; editorial Source Serif 4 / IBM Plex Mono typography; a single light-mode violet accent replacing the dark map theme; the Agent Economy as a tight 2-column grouped grid; a relocated Newsletter-only mode toggle; and a "What is AgentPulse" About stub. **Frontend-only** — no backend, pipeline, Supabase, or content/data changes; the dual-mode *content* logic is unchanged (only the toggle's placement and styling move). Phases restyle on top of one shared design-system shell (Phase 11), each later phase a coherent visual unit. Ships via the v1.0-proven scoped `agentpulse-web` rebuild — no new infra. The mockup is a reference for intent, not markup to copy.

- [x] **Phase 11: Design System + Nav Shell** - Single light-mode token palette, Source Serif 4 / IBM Plex Mono typography, and the persistent stateful 3-tab nav shell with back-arrow that every later view reuses (completed 2026-06-04)
- [ ] **Phase 12: Newsletter Section Restyle** - Restyle the edition list + article on the new shell and relocate the Technical/Strategic mode toggle into the Newsletter section only
- [ ] **Phase 13: Agent Economy Grid** - Re-render the map as a responsive 2-column grouped card grid driven by the canonical data-source block taxonomy, with deferred-block treatment
- [ ] **Phase 14: About Stub + Polish Pass** - Add the nav-reachable "What is AgentPulse" stub and apply the site-wide spacing/radius consistency pass

## Phase Details

### Phase 11: Design System + Nav Shell

**Goal**: Establish the shared design-system layer — one light-mode CSS-variable palette, the Source Serif 4 / IBM Plex Mono typography system, and the persistent 3-tab nav shell with stateful active state and back-arrow — that every later section restyle reuses. This mirrors v1.0's foundation-first discipline: the brief's "inventory the current frontend + confirm the plan before editing" gate is satisfied here before any section is restyled.
**Depends on**: Nothing (first phase of v2.0; builds on the existing v1.0 SPA)
**Requirements**: NAV-01, NAV-02, NAV-03, NAV-04, TYPE-01, TYPE-02, TYPE-03, COLOR-01, COLOR-02
**Success Criteria** (what must be TRUE):

  1. Every page shows a persistent sticky top bar — brand (left), three section tabs (Newsletter / Agent Economy / What is AgentPulse), Subscribe button (right) — and a reader can reach any section from any other in one click; the old plain "Map" link is gone, replaced by the Agent Economy tab.
  2. The current section's tab stays visually active on nested pages (a single edition keeps Newsletter active; a single block keeps Agent Economy active), and every nested page shows a `← Back to [section]` control at top-left.
  3. Body and reading text + titles render in Source Serif 4 with no monospace body paragraphs anywhere; IBM Plex Mono appears only on UI chrome (eyebrow/label, metadata, tab labels, buttons, tags), and a single ~18px / ~1.6-line-height serif heading style is used (the second monospace heading treatment is gone).
  4. A single light-mode palette (warm off-white bg, surfaces, ink scale, one violet accent) is defined via CSS variables and applied site-wide, replacing the dark map theme; the accent appears on links and the active tab and nowhere is a second brand color used.

**Plans**: 2 plansPlans:
**Wave 1**

- [x] 11-01-PLAN.md — Design-system foundation: style-base.css :root tokens + Source Serif 4 / IBM Plex Mono typography + Google-Fonts link; retire dark var blocks + Courier body (COLOR-01/02, TYPE-01/02/03)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 11-02-PLAN.md — Sticky 3-tab nav shell: header markup, route-derived active tab, ← Back to [section] control, mobile wrap, Subscribe reuses scrollToSubscribe() (NAV-01/02/03/04)

**UI hint**: yes

### Phase 12: Newsletter Section Restyle

**Goal**: Restyle the Newsletter edition list and article views on the new design-system shell, and relocate the Technical/Strategic mode toggle so it lives only inside the Newsletter section — without changing any dual-mode content logic (only the toggle's placement and styling move).
**Depends on**: Phase 11
**Requirements**: TGL-01, TGL-02
**Success Criteria** (what must be TRUE):

  1. The Technical/Strategic mode toggle appears only inside the Newsletter section (both list and article views) and no longer occupies any global or shared position; switching mode still re-renders the same dual-mode content as before.
  2. The active mode shows a filled accent and a hint line below it ("Architecture, code, implementation" for Technical; "Markets, strategy, implications" for Strategic).
  3. The edition list and single-article views render in the new serif typography and light-mode palette, reading cleanly with no monospace body paragraphs.

**Plans**: TBD
**UI hint**: yes

### Phase 13: Agent Economy Grid

**Goal**: Re-render the Agent Economy section as a tight, responsive card grid grouped by the canonical block taxonomy from the live data source, replacing the long vertical scroll so related blocks are visible together with minimal scrolling.
**Depends on**: Phase 11
**Requirements**: MAP-01, MAP-02, MAP-03, MAP-04
**Success Criteria** (what must be TRUE):

  1. The Agent Economy renders as a responsive grid — 2 columns on desktop, 1 on mobile, with tight ~16px gaps — instead of one long vertical scroll, fitting more blocks above the fold.
  2. Each block is a bordered card with a serif title, one-line description, progress dots, a 3px accent left-border, and a subtle hover lift.
  3. Cards are grouped under small section labels using the canonical block taxonomy from the data source (the live `economy_map.blocks` grouping), not the mockup's placeholder blocks.
  4. Any deferred/incomplete block spans the full grid width with a DEFERRED tag and empty progress dots.

**Plans**: TBD
**UI hint**: yes

### Phase 14: About Stub + Polish Pass

**Goal**: Add the nav-reachable "What is AgentPulse" page (stubbed with the existing about copy) and apply the site-wide spacing/radius consistency pass that tightens vertical rhythm across cards, toggle, and buttons — completing the minimalist-but-not-sparse feel.
**Depends on**: Phase 11, Phase 12, Phase 13
**Requirements**: ABOUT-01, POLISH-01
**Success Criteria** (what must be TRUE):

  1. A "What is AgentPulse" page is reachable from the nav tab and renders the existing about copy as a stub (the deeper pipeline-diagram content is intentionally deferred).
  2. Vertical rhythm is tightened and radii are consistent (~7–10px) across cards, the toggle, and buttons site-wide — minimalist but not sparse.
  3. The full site (Newsletter, Agent Economy, About) reads as one coherent system: single accent, one serif heading style, consistent spacing and radii throughout.

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 11 → 12 → 13 → 14

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
| 11. Design System + Nav Shell | v2.0 | 2/2 | Complete    | 2026-06-04 |
| 12. Newsletter Section Restyle | v2.0 | 0/TBD | Not started | - |
| 13. Agent Economy Grid | v2.0 | 0/TBD | Not started | - |
| 14. About Stub + Polish Pass | v2.0 | 0/TBD | Not started | - |
