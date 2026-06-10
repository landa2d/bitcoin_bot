# Roadmap: AgentPulse — The Agent Economy (Living Reference Articles)

## Milestones

- ✅ **v1.0 Agent Economy Map** — Phases 1–10 + 4.1 (shipped 2026-06-04) — full details: [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 Frontend Redesign** — Phases 11–14 (shipped 2026-06-08) — full details: [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md)
- ✅ **v2.1 Agent Economy Content** — Phases 15–18 (shipped 2026-06-09) — full details: [`milestones/v2.1-ROADMAP.md`](milestones/v2.1-ROADMAP.md)
- 🚧 **v2.2 Landing Redesign + Signals Feed** — Phases 19–24 (planning) — re-skin the public site to the new editorial mockup across the existing separate-route SPA, fix four live-site defects, and add a tier-1 Signals feed.

_Active milestone: v2.2. Phase numbering continues from 18._

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

<details>
<summary>✅ v2.1 Agent Economy Content (Phases 15–18) — SHIPPED 2026-06-09 — 4 phases, 10 plans</summary>

Filled the v2.0 grid with real editorial content: loaded the hub `agent-economy` + 7 block bodies into `economy_map` as unpublished (migration 043 + a standalone PostgREST loader), wired every `#/map/<slug>` cross-link, verified on a flag-gated preview route, then published all 8 in-scope bodies live in ONE operator-approved batch via the atomic `publish_block_version` RPC. Content-only — no UI redesign, no pipeline/proxy/agent-service changes. `regulation-legal` kept deferred.

- [x] Phase 15: Inventory & Roster Reconciliation (2/2) — completed 2026-06-08 (INV-01, INV-02, ROST-01)
- [x] Phase 16: Content Load (unpublished) (3/3) — completed 2026-06-08 (LOAD-01, LOAD-02, LOAD-03)
- [x] Phase 17: Cross-link Wiring & Preview (2/2) — completed 2026-06-09 (LINK-01, PREV-01, HUB-01)
- [x] Phase 18: Gated Batch Publish (3/3) — completed 2026-06-09 (PUB-01)

Full phase details, goals, success criteria, and per-plan breakdown archived in [`milestones/v2.1-ROADMAP.md`](milestones/v2.1-ROADMAP.md).

</details>

### 🚧 v2.2 Landing Redesign + Signals Feed (Phases 19–24)

Re-skin the public `aiagentspulse.com` SPA to the new editorial mockup **across the existing separate-route structure** (NOT single-scroll), fix the four live-site defects the redesign brief calls out, and add a new tier-1 Signals feed. The 7 work groups consolidate into 6 phases, ordered **low-to-high risk, each independently shippable** — every phase ends in a branch + `/diff` per work group + a prod↔main drift check + a scoped `docker compose up -d --build web` (no `--delete`) + operator approval before any deploy.

**NOT frontend-only (unlike v2.0).** Two phases reach the backend and are deliberately isolated from the pure-CSS work: **Phase 19** (smart-quotes) touches the content write-path + a scoped reviewed data backfill; **Phase 23** (Signals) adds the milestone's only Supabase migration (an anon RLS policy on `source_posts`). Everything else lives in `docker/web/site/` (`app.js`, `style-base.css`, `style-shared.css` — the other CSS files are legacy/unloaded; markdown renders via `marked.js`, CDN, no typographer).

**The spine (from PROJECT.md):** keep separate routes (preserve v2.0's 3-tab nav shell + ← Back pattern; add a Signals tab); all LLM via `llm-proxy:8200`; `economy_map`/isolated-schema access via direct PostgREST + `Accept-Profile` (never supabase-py `.in_()`); append-only — corrections via the canonical-body-rewrite path, never a raw UPDATE; fail-loud on missing fields; the apostrophe backfill is a scoped reviewed UPDATE shown before/after on ONE edition first, never a blind find-replace.

- [ ] **Phase 19: Smart-Quote / Apostrophe Corruption Fix** — Root-cause the apostrophe→straight-quote corruption (renderer has no typographer, so it is in stored markdown / the write path), fix forward + a scoped reviewed backfill of existing editions, guarded by a regression test. (QUOTE-01, QUOTE-02)
- [ ] **Phase 20: Width Tokens & Centering Foundation** — Introduce the two coexisting, both-centered max-widths (`--measure` narrow prose, `--wide` grids) that kill the dead left gutter, and establish the token-only color + section-rhythm baseline everything downstream sits on. (WIDTH-01, RHYTHM-01)
- [ ] **Phase 21: Per-Route Visual Fixes** — Three non-conflicting per-route fixes on the new width foundation: edition-header de-dup, the Agent Economy 3-col grid + maturity legend, and the About pipeline-vs-supporting agent grid + approval callout. (HEAD-01, GRID-01, GRID-02, AGENTS-01)
- [ ] **Phase 22: Distinct Newsletter Excerpts** — Strip the boilerplate "Read This, Skip the Rest" intro at render and pull the first genuinely-distinct sentence into the indexed-row archive format — no schema change. (EXCERPT-01)
- [ ] **Phase 23: Signals Feed** — A new `#/signals` route + nav tab listing tier-1 `source_posts` newest-first (capped, external links), gated on the milestone's one Supabase migration: a read-only, tier-1-scoped anon RLS policy on `source_posts`, fail-loud if absent. (SIGNAL-01, SIGNAL-02, SIGNAL-03, SIGNAL-04)
- [ ] **Phase 24: Responsive & Accessibility Pass** — A holistic cross-cutting verification: all grids/rows reflow (3→2→1, nav condenses, rows stack date-above-headline) and keyboard focus is visible / motion-reduced / every link is a real `<a>`. (RESP-01, A11Y-01)

## Phase Details

### Phase 19: Smart-Quote / Apostrophe Corruption Fix

**Goal**: The highest-visibility live-site bug is gone — edition bodies render apostrophes correctly everywhere, the root cause is documented (not papered over), the write path is fixed so it cannot recur, existing editions are backfilled via a scoped reviewed UPDATE, and a regression test locks it.
**Depends on**: Nothing (first v2.2 phase; isolated content-integrity fix, ships first per the brief)
**Requirements**: QUOTE-01, QUOTE-02
**Success Criteria** (what must be TRUE):

  1. Edition 30 (and other backfilled editions) render `Cash App's`, `It's`, `world's`, `agent's` correctly on the live site — zero straight-double-quote-in-place-of-apostrophe corruption in the body.
  2. The root cause is written down: a query of the raw stored `body_md` shows whether the corruption is at storage (write path) or render, and the chosen fix follows from that finding (render-layer if data is clean; write-path-first-then-backfill if data is corrupt).
  3. Newly generated editions come out clean — the write path is fixed so the corruption stops recurring, not just hidden at render.
  4. A regression test feeds `it's` and `the agent's wallet` through the fixed path and asserts the output contains an apostrophe and zero stray `"` — the corruption cannot silently regress.

**Notes**: Backend phase — content pipeline + a scoped data backfill, NOT frontend-only. Spine: the backfill is a scoped, reviewed UPDATE shown before/after on ONE edition first (operator approval), never a blind table-wide find-replace; append-only/canonical-rewrite discipline applies to any body correction; fail-loud rather than silently default. `marked.js` (CDN) runs with no typographer, so a render-layer smartquote transform is unlikely to be the cause — diagnose stored bytes first.**Plans**: 2 plans
**Wave 1**

- [ ] 19-01-diagnose-and-fix-write-path-PLAN.md — Diagnose root cause from raw stored bytes, fix the write path, regression test (QUOTE-01, QUOTE-02)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 19-02-scoped-reviewed-backfill-PLAN.md — Scoped reviewed backfill of existing editions (operator-gated, before/after on edition 30 first) + content-service rebuild (QUOTE-01)

### Phase 20: Width Tokens & Centering Foundation

**Goal**: The dead left gutter is gone — on a wide viewport content is centered, with narrow prose for reading copy and a wider container for everything tiled — and the token-only color system + section-rhythm rules are established as the shared baseline every later visual phase builds on.
**Depends on**: Phase 19 (independent, but sequenced after the isolated content fix per low-to-high-risk order)
**Requirements**: WIDTH-01, RHYTHM-01
**Success Criteria** (what must be TRUE):

  1. On a wide monitor there is no large empty band on the left — content is centered, not pinned center-left.
  2. Edition body + intro copy hold a readable ~60–70-char line via a narrow centered prose width (`--measure`); the newsletter list, map grid, Signals, and card grids use a wider centered container (`--wide`).
  3. No surface uses a hardcoded color — every color themes from the existing CSS variable system (warm off-white + violet).
  4. Section rhythm reads as a hierarchy: one full-strength rule between major sections, hairline (`0.5px`) rules within.

**Notes**: Foundational — everything downstream sits on these width tokens, so it lands before the per-route fixes. RHYTHM-01 (token-only colors + section rhythm) is applied site-wide but is established and verified holistically HERE as the baseline; later phases conform to it rather than redefining it. Frontend-only (`style-base.css` / `style-shared.css` / `app.js` class application). Mockup is intent reference only.
**Plans**: TBD
**UI hint**: yes

### Phase 21: Per-Route Visual Fixes

**Goal**: Three independent per-route defects are fixed on the new width foundation: an edition page states its number/date/mode exactly once, the Agent Economy map tiles cleanly as a legible 3-column scale, and the About page reads as an ordered pipeline + an unordered supporting layer with the human-approval line as its own callout.
**Depends on**: Phase 20 (sits on the width tokens + rhythm baseline)
**Requirements**: HEAD-01, GRID-01, GRID-02, AGENTS-01
**Success Criteria** (what must be TRUE):

  1. An edition page H1 contains only the headline; the edition number, date, and mode (Technical/Strategic) appear exactly once, in the meta line below the title (the `— Edition #N | <date>` suffix is stripped at render if baked into stored data, never mutated in storage).
  2. The Agent Economy map renders as a 3-column grid on desktop (collapsing 3→2 at ≤880px → 1 at ≤600px), with a maturity legend under the heading and each block's filled-segment count matching its stored `economy_map` maturity value.
  3. The About page shows the pipeline agents (Processor / Analyst / Research / Newsletter) as an ordered numbered sequence and the supporting layer (Gato / LLM proxy / web) as an unordered bulleted list — no orphaned single card — with "nothing publishes without human approval" rendered as its own distinct violet callout.

**Notes**: Three non-conflicting per-route fixes share this phase per the brief (Tasks 3/4/5 touch different routes, no file contention). HEAD-01 strips at render — no stored-data mutation (consistent with v2.0, which appends edition/date at render). GRID-02 reads `economy_map` maturity via the existing renderer / direct PostgREST + `Accept-Profile` (never `.in_()`); read-only, no schema change. Frontend-only.
**Plans**: TBD
**UI hint**: yes

### Phase 22: Distinct Newsletter Excerpts

**Goal**: The archive list stops showing the same opening words on consecutive editions — the boilerplate intro is skipped and each row shows a genuinely-distinct first sentence in the indexed-row format — with no schema or pipeline change.
**Depends on**: Phase 20 (uses the `--wide` container + indexed-row treatment)
**Requirements**: EXCERPT-01
**Success Criteria** (what must be TRUE):

  1. Editions 29 and 30 show different preview text in the archive list (the recurring "Read This, Skip the Rest" header + shared intro sentence are skipped, and the first genuinely-distinct sentence is shown).
  2. The list renders in the indexed-row format — number · title · one-line summary · date — which structurally prevents the duplicate-excerpt class.
  3. The fix is strip-at-render only: no `newsletters` schema change, no stored `summary` field, no content-pipeline change (the stored `summary` path is explicitly deferred to EXCERPT-F1).

**Notes**: Frontend-only, strip-at-render (operator-confirmed decision). The cleaner stored-`summary` path is the deferred EXCERPT-F1 future requirement, intentionally out of this milestone.
**Plans**: TBD
**UI hint**: yes

### Phase 23: Signals Feed

**Goal**: A new Signals section exists — its own `#/signals` route and nav tab listing tier-1 `source_posts` newest-first as safe external links — backed by the milestone's one Supabase migration: a read-only, tier-1-scoped anon RLS policy on `source_posts` that fails loud rather than silently rendering an empty feed.
**Depends on**: Phase 20 (Signals uses the `--wide` container + indexed-row pattern) and Phase 23's own RLS migration
**Requirements**: SIGNAL-01, SIGNAL-02, SIGNAL-03, SIGNAL-04
**Success Criteria** (what must be TRUE):

  1. Visiting `#/signals` shows tier-1 `source_posts` newest-first, capped to ~12–15, with a "view all signals" affordance so a heavy news week can't make the section enormous.
  2. Each Signals row is a real external `<a>` showing date · headline · source domain, opening off-site safely (`target="_blank"` + `rel="noopener noreferrer"`) with an `↗` hover affordance.
  3. Signals is reachable from a tab in the persistent v2.0 nav shell (consistent with the existing tabs + ← Back pattern), deep-linkable at `#/signals`.
  4. The anon key can read tier-1 `source_posts` via a new read-only, tier-1-scoped RLS policy; if that policy is absent the feed fails loud (surfaced error), never silently renders empty.

**Notes**: Backend phase — the milestone's ONLY Supabase migration (next in sequence after 043), deliberately isolated from the pure-CSS phases. The migration grants a narrow, read-only, tier-1-scoped anon SELECT on `source_posts` (currently anon-blocked) — fail-loud on absence is a hard requirement (the empty-feed-on-missing-policy failure mode is exactly the silent-failure class the spine guards against). New `#/signals` route + nav tab in `app.js`; rows are real `<a>` (A11Y consistency carried into Phase 24's holistic pass). Deploy gated: branch + `/diff` + scoped web rebuild + operator approval; migration applied by the orchestrator (worktree-unsafe), not a worktree executor.
**Plans**: TBD
**UI hint**: yes

### Phase 24: Responsive & Accessibility Pass

**Goal**: The whole redesigned surface holds up on small screens and for keyboard/assistive users — every grid and row reflows correctly at the breakpoints, focus is always visible, motion is reduced on request, and every link is a real anchor — verified holistically across all the routes the milestone touched.
**Depends on**: Phases 20, 21, 22, 23 (verifies the responsive + a11y behavior of everything built before it)
**Requirements**: RESP-01, A11Y-01
**Success Criteria** (what must be TRUE):

  1. All grids and rows reflow responsively at the breakpoints: the map collapses 3→2→1, the nav condenses on mobile, and signal/archive rows stack (date above headline) below the mobile breakpoint.
  2. Keyboard focus is visible everywhere — a `:focus-visible` violet outline appears as you tab through nav, list rows, and links.
  3. `prefers-reduced-motion` is respected (hover lifts / transitions suppressed when the user requests reduced motion).
  4. Every link across the touched routes is a real `<a>` element (no click-handler-only pseudo-links) — keyboard- and screen-reader-navigable.

**Notes**: Cross-cutting requirements applied throughout every phase but verified holistically HERE as the final responsive/a11y pass over the whole redesigned surface (the natural place to confirm them end-to-end rather than re-checking each per-route phase). Frontend-only (`style-base.css` / `style-shared.css` media queries + `:focus-visible` / `prefers-reduced-motion` rules + an `<a>` audit). Deploy gated: branch + `/diff` + scoped web rebuild + operator approval.
**Plans**: TBD
**UI hint**: yes

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
| 15. Inventory & Roster Reconciliation | v2.1 | 2/2 | Complete | 2026-06-08 |
| 16. Content Load (unpublished) | v2.1 | 3/3 | Complete | 2026-06-08 |
| 17. Cross-link Wiring & Preview | v2.1 | 2/2 | Complete | 2026-06-09 |
| 18. Gated Batch Publish | v2.1 | 3/3 | Complete | 2026-06-09 |
| 19. Smart-Quote / Apostrophe Corruption Fix | v2.2 | 0/2 | Planned | - |
| 20. Width Tokens & Centering Foundation | v2.2 | 0/? | Not started | - |
| 21. Per-Route Visual Fixes | v2.2 | 0/? | Not started | - |
| 22. Distinct Newsletter Excerpts | v2.2 | 0/? | Not started | - |
| 23. Signals Feed | v2.2 | 0/? | Not started | - |
| 24. Responsive & Accessibility Pass | v2.2 | 0/? | Not started | - |

## Backlog

Parked for a future milestone — **not scheduled, not for now**. Surfaces at next `/gsd-new-milestone` planning. Source-of-truth detail lives in `.planning/todos/pending/`.

### v2.2 future requirements (deferred this milestone)

Tracked in `.planning/REQUIREMENTS.md` → Future Requirements.

- **EXCERPT-F1** — stored `summary` field on `newsletters`, emitted by the Newsletter agent at generation time (the cleaner long-term excerpt path; deferred in favor of strip-at-render — touches schema + pipeline + backfill).
- **SIGNAL-F1** — a full Signals archive page behind the "view all signals" affordance (if the capped feed proves insufficient).
- **WIDTH-F1** — single-page-scroll landing with scroll-spy nav (the mockup's literal form; deferred in favor of separate routes for SEO / deep-linking / lower risk).
- **THEME-F1** — dark-mode variant of the light palette (DARK-01, carried from v2.0).
- **THEME-F2** — richer About page with a pipeline/architecture diagram (ABOUT-02, carried from v2.0).

### Backend follow-ups (candidate: a backend-hardening milestone)

Carried forward from v1.0; out of v2.0/v2.1/v2.2 (frontend + scoped-touch) scope.

- analyst predictions `title` expire bug (P2)
- soft-cap allow-negative hardening (P5)
- pay-endpoint 500 activation E2E — RPC root-cause fixed in migration 037 (P2)
- phase-05 intake-classifier review follow-ups WR02/04/05 (P4)
- research trigger file permissions (P4)
