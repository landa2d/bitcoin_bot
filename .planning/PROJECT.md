# AgentPulse

## What This Is

A multi-agent intelligence platform for the AI agent economy: eight cooperating Docker services (Telegram-facing bot, conversational middleware, background processor, analyst, newsletter writer, research agent, LLM proxy, web frontend) that ingest content, synthesize findings, and publish daily-to-weekly outputs (newsletters, X posts, briefings) for the operator. Controlled via Telegram commands; deployed on a single Linux server with Supabase as the shared data store.

## Core Value

**Synthesis with editorial integrity.** Autonomous ingestion and drafting accelerate the operator's output, but every consequential publication is gated by human approval — silence and homogenization are the failure modes to design against.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ **Newsletter pipeline (block-based, 5-phase)** — Phase A→Prepass→B→C→D→E, dual versions (technical/impact), 0 T1 fabrications on Edition 34 — existing
- ✓ **Multi-source content ingestion** — RSS (15+ feeds, tier-aware filtering), HN, Moltbook, X (14 source accounts) — existing
- ✓ **X distribution pipeline** — surface → operator review via Telegram → approved-only post via tweepy, weekly $5 X API budget cap — existing
- ✓ **LLM proxy with budget governance** — per-agent API keys, wallet reserve/settle, rate limiting, model routing (DeepSeek/OpenAI/Anthropic) — existing
- ✓ **Telegram operator control surface** — intent router (6 intents), corpus probe (pgvector), code engine, CTO commands — existing
- ✓ **Analyst + Research polling pipelines** — async tasks via Supabase queues, Tavily web enrichment — existing
- ✓ **Static web frontend** — `aiagentspulse.com` archive served from Hetzner via Caddy — existing
- ✓ **Schema isolation pattern** — `eu_ai_act` schema via `Accept-Profile` header, direct PostgREST (sidesteps supabase-py `.in_()` silent failures) — existing
- ✓ **Agent Economy Map (v1.0)** — autonomous-intake, human-gated living-reference surface on `aiagentspulse.com`: hub/block/status renderers in `app.js`, append-only `economy_map` schema with seven seeded blocks, design-token CSS (tier accents, maturity pills, fixed timeline format), per-block synthesis loop with hot-reloadable identity + N/T triggers, deterministic validation sentinels (flag-never-block), and a full owner-gated `/map-*` Telegram surface (status/pending/approve/reject/assign/entry/synth/tension). All LLM via `llm-proxy:8200`; all `economy_map` access via direct PostgREST. Shipped + archived 2026-06-04 — see MILESTONES.md for the per-phase detail.

### Active

<!-- Current milestone: v2.0 Frontend Redesign — UI-only public-site redesign (see .planning/docs/REDESIGN_BRIEF.md + agentpulse-redesign-mockup.html). REQ detail in REQUIREMENTS.md. -->

**Navigation** *(validated Phase 11, 2026-06-04 — operator UAT)*
- [x] **NAV-01**: Every page shows a persistent sticky top bar — brand (left), three section tabs (Newsletter / Agent Economy / What is AgentPulse), Subscribe button (right)
- [x] **NAV-02**: The current section's tab stays visually active on nested pages (a single edition keeps Newsletter active; a single block keeps Agent Economy active)
- [x] **NAV-03**: Every nested page (single edition, single block) shows a `← Back to [section]` control at top-left
- [x] **NAV-04**: A reader can reach any section from any other in one click; the old plain "Map" link is replaced by the Agent Economy tab

**Typography** *(validated Phase 11 — foundation; article-prose serif lands Phase 12)*
- [x] **TYPE-01**: Body and reading text + titles render in Source Serif 4; no monospace body paragraphs anywhere on the site *(base serif body shipped; newsletter article-prose conversion is Phase 12)*
- [x] **TYPE-02**: Monospace (IBM Plex Mono) is reserved for UI chrome only — eyebrow/label, metadata (Edition # · date), tab labels, buttons, tags, code
- [x] **TYPE-03**: One serif heading style at ~18px body / ~1.6 line-height; the second monospace heading treatment is removed

**Color** *(validated Phase 11, 2026-06-04 — palette applied site-wide incl. legacy-token bridge)*
- [x] **COLOR-01**: A single light-mode palette (warm off-white bg, surfaces, ink scale, violet accent) is defined via CSS variables and applied site-wide, replacing the dark map theme
- [x] **COLOR-02**: One accent only — used for links, active tab, card borders, and progress dots; no second brand color

**Mode toggle**
- [x] **TGL-01**: The Technical/Strategic mode toggle appears only inside the Newsletter section (list + article) and is removed from any global/shared position — *validated in Phase 12 (list-route scoped per D-01; article inherits persisted mode)*
- [x] **TGL-02**: The active mode shows a filled accent and a hint line below ("Architecture, code, implementation" vs "Markets, strategy, implications") — *validated in Phase 12*

**Agent Economy map** *(validated Phase 13, 2026-06-05 — operator-approved; 10/10 must-haves verified in code, 6 browser items persisted in 13-HUMAN-UAT.md for batch-deploy verify per D-01)*
- [x] **MAP-01**: The Agent Economy renders as a responsive grid (2 columns desktop, 1 column mobile, tight ~16px gaps) instead of one long vertical scroll
- [x] **MAP-02**: Each block is a bordered card — serif title, one-line description, progress dots, 3px accent left-border, subtle hover lift
- [x] **MAP-03**: Cards are grouped under small section labels using the canonical block taxonomy from the data source (not the mockup's placeholder blocks)
- [x] **MAP-04**: Deferred/incomplete blocks span full width with a DEFERRED tag and empty progress dots

**About**
- [ ] **ABOUT-01**: A nav-reachable "What is AgentPulse" page exists, stubbed with the existing about copy (deeper pipeline-diagram content deferred)

**Spacing & polish**
- [ ] **POLISH-01**: Vertical rhythm is tightened and radii are consistent (~7–10px) across cards, toggle, and buttons — minimalist but not sparse

### Out of Scope

<!-- Explicit boundaries with reasoning to prevent re-adding. -->

- **Dark mode in this redesign pass** — Ship the single light-mode violet system first; dark mode is noted but deferred (avoids doubling the token/QA surface mid-redesign).
- **Backend / pipeline / Supabase / content changes (v2.0)** — v2.0 is frontend-only. Dual-mode *content* logic is unchanged; only the mode toggle's placement and styling move. No data-model, schema, or synthesis changes.
- **Deferred backend v2 items kept separate (this milestone)** — Negotiation-block graduation, per-block synthesis tuning, and EU AI Act tracker integration stay parked; the operator chose to keep UI and backend scopes in separate milestones.
- **Richer "What is AgentPulse" content / pipeline diagram** — About ships as a stub of existing copy; the pipeline diagram is a separate later iteration.
- **Mockup's placeholder block taxonomy** — The grid uses the canonical 7-block list/grouping from the data source, not the mockup's illustrative Substrate/Coordination blocks (Discovery, Orchestration, Marketplaces); the mockup is a reference for intent, not markup to copy.
- **Negotiation as its own block at launch** — Today it would be 80% future-tense. Lives as a section inside Payments; graduates to its own block when real bid/ask behavior exists.
- **Per-block synthesis threshold tuning at launch** — Ship global defaults N=5/T=30; revisit per-block tuning (Payments weekly cadence, Psychology quarterly) only if data forces it later.
- **Oldest-first timeline rendering** — Newest-first is the default; feels live, matches the editorial flag of an evolving map.
- **Direct Anthropic SDK calls from synthesis** — All LLM calls route through `llm-proxy:8200` for budget governance. The RivalScope direct-call workaround is the anti-pattern we're not repeating.
- **In-place body mutation** — `block_body_versions` is append-only; re-synthesis inserts new versions, never overwrites. Prevents the silent-degradation failure class.
- **Mutating timeline history** — Corrections are new entries with reference to the prior; `unsorted` entries are reassigned, not edited. Prevents the silent-misfile failure class.
- **External cache layer / message broker** — Single Linux server, Supabase polling and HTTP only. Matches existing architecture; introducing infrastructure is yak shaving until a measurable need surfaces.

## Context

**Existing system the milestone plugs into:**
- Newsletter pipeline (block-based, 5-phase) is the upstream source — finalized tier-1 events emit timeline candidates at the point each edition completes (see `docker/newsletter/newsletter_poller.py`, block pipeline modules)
- LLM Proxy (`docker/llm-proxy/proxy.py`, port 8200) is the mandatory gateway for all LLM calls with budget governance — per-agent `ap_<agent>_<hash>` keys, wallet reserve/settle pattern
- Supabase schema isolation pattern already exists (`eu_ai_act` schema, `Accept-Profile` header for direct PostgREST) — reused for `economy_map`
- Telegram operator control surface (Gato → Gato Brain) is the gating mechanism — `/x-*` family is the closest analog for the `/map-*` family
- 42 existing migrations in `supabase/migrations/` (v1.0 added through 042)

**v2.0 redesign context (frontend):**
- The public site is a vanilla, hash-routed SPA — `docker/web/site/app.js` (~785 lines) — with views: newsletter list (`#/`), reader (`#/edition/N`), economy map (`#/map`), single block (`#/map/<slug>`), status (`#/status`), unsubscribe. Styling is split across `style.css`, `style-shared.css`, `style-builder.css` (technical mode), `style-impact.css` (strategic mode), and the dark `style-map.css`.
- A Technical/Strategic mode toggle and `technical`/`strategic` body classes already drive dual-mode content; v2.0 relocates and restyles the toggle but does not change the content logic. There is currently no persistent top nav and no "About" page — both are added by the redesign.
- v2.0 redesigns this surface per `.planning/docs/REDESIGN_BRIEF.md` + `agentpulse-redesign-mockup.html` (reference for intent, not code to copy). Publish path is the v1.0-proven scoped web rebuild (single `agentpulse-web` container) — no new infra.

**Recent history that shapes design:**
- Block pipeline shipped May 2026 — Phase D verification drove fabrications from 27 to 0 by enforcing grounding against block-derived facts. The sentinel-validator pattern mirrors this learning directly.
- Fix 3 (extraction prompt rework, May 2026) — silent failure cascade where a mis-specified prompt produced 0.06% hit rate AND a UUID type mismatch silently dropped every insert. Drives the design principle: silence is the enemy; a flagged draft beats a missing one.
- 27-day wallet bug — expensive silent error → the explicit autonomy boundary: cheap-and-visible errors run unattended; expensive-and-silent errors get gated.
- supabase-py `.in_()` silent-failure bug — drives the direct-PostgREST mandate for the new schema.

**Storyline:** The agent economy is the project of building, for autonomous software, the trust and coordination infrastructure humans took centuries to build — in years, and without us in the loop. Editorial flag: **capability is solved; trust and coordination are not.**

## Constraints

- **Architecture**: Single Linux server, Docker Compose orchestration, Supabase as shared store — no Kubernetes, no message broker, no external cache. New work integrates here.
- **LLM access**: All model calls route through `http://llm-proxy:8200`. Direct provider SDK calls are forbidden (budget governance + the RivalScope lesson).
- **Schema access**: `economy_map` tables accessed via direct PostgREST HTTP with `Accept-Profile: economy_map` header. Do not use supabase-py `.in_()` (silent failure).
- **Frontend-only (v2.0)**: No backend, pipeline, Supabase, or content/data changes. Dual-mode *content* logic is unchanged — only the mode toggle's placement and styling move.
- **One light-mode accent system (v2.0)**: A single violet accent across all sections (links, active tab, card borders, dots); dark mode deferred. Reuse the existing publish path; the mockup is a reference for intent, not markup to copy.
- **Publish path**: Public-site changes ship via the existing `aiagentspulse.com` scoped web rebuild (single `agentpulse-web` container) confirmed in v1.0 Phase 0 — no new infra.
- **Editorial framing in human hands**: `live_tension` and synthesis prompt voice (via `synth_identity.md`) stay operator-controlled; the loop synthesizes, the operator frames.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| v2.0 redesign: single light-mode violet accent replaces the dark map theme | One coherent system across all sections; dark mode deferred to avoid doubling the token/QA surface | — Pending |
| v2.0 redesign: Source Serif 4 body + IBM Plex Mono for chrome only | Editorial readability; ends monospace body paragraphs; one serif heading style | — Pending |
| v2.0 redesign: persistent 3-tab nav with stateful active state on nested pages | One-click reachability + always-know-where-you-are; "Map" becomes the Agent Economy tab | — Pending |
| v2.0 scope: frontend-only; deferred backend v2 items kept in separate milestones | Lower risk, single concern; the redesign brief mandates backend untouched | — Pending |
| Economy map uses the canonical data-source taxonomy, not mockup placeholders | The mockup is intent reference only; the real block list/grouping drives the grid | — Pending |
| Negotiation as section inside Payments at launch | 80% future-tense today; graduate to own block when real bid/ask behavior exists | — Pending |
| Regulation ships as lightly-populated closing frame | Establishes the slot in the map; EU AI Act tracker feeds it over time | — Pending |
| Global synthesis defaults N=5/T=30 (no per-block tuning yet) | Ship simple; revisit only if data forces per-block cadence | — Pending |
| Timeline order: newest-first | Feels live; matches editorial flag of an evolving map | — Pending |
| Append-only `block_body_versions` + `timeline_entries` | Eliminates silent-degradation failure class (the 27-day wallet bug pattern) | ✓ Good (v1.0) |
| Schema isolation via `economy_map` + direct PostgREST | Mirrors `eu_ai_act` pattern; sidesteps supabase-py `.in_()` silent failure | ✓ Good (v1.0) |
| Sentinels flag, never block | Silence is the enemy; a flagged draft beats a missing draft | ✓ Good (v1.0) |
| Synthesis via `llm-proxy:8200` (no direct Anthropic SDK) | Budget governance + the RivalScope anti-pattern is the lesson | ✓ Good (v1.0) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-05 — Phase 13 (Agent Economy Grid) complete + operator-approved: the Agent Economy hub (`#/map`) re-rendered as a responsive 2-col (1-col mobile) grouped card grid on the Phase 11 light/serif system — bordered cards (serif title/desc, 3px violet accent stripe, hover lift), canonical SUBSTRATE/BEHAVIOR/FRAME tier grouping from live `economy_map.blocks`, full-width DEFERRED cards with empty dots + `· DEFERRED` tag, and a serif "The Agent Economy" in-content header (MAP-01..04, D-04/D-05/D-06). Plan 02 de-darkened the block reading view + `#/status` onto the serif/light single-accent system (TYPE-01 serif body prose, no Courier, no `data-accent`) and retired `style-map.css` entirely (delete-and-fold complete; cascade = style-base.css + style-shared.css). Code review: 0 blockers, 1 advisory warning (escapeHtml attr-context hardening — currently safe), 3 info. 10/10 must-haves verified in code; 6 browser checks persisted in 13-HUMAN-UAT.md for batch-deploy verify per D-01. Next: Phase 14 (About Stub + Polish Pass). Phase 12 (Newsletter Section Restyle) complete + operator-verified: Newsletter list + article restyled onto the serif/light system (TYPE-01 serif reading text, 0 mono body), the Technical/Strategic toggle relocated to the Newsletter list route only (TGL-01, D-01) with a filled-accent segmented pill + mono hint line (TGL-02), and a magazine article header. Next: Phase 13 (Agent Economy Grid — re-render the map as a responsive 2-col grouped card grid, replacing the current long vertical scroll). Phase 11 (Design System + Nav Shell) complete + operator-verified: light-mode token palette, Source Serif 4 / IBM Plex Mono typography, and the persistent stateful 3-tab sticky nav shell with ← Back controls (NAV-01..04, TYPE-01..03, COLOR-01..02). A minimal `#/about` stub was pulled forward (full page = Phase 14). — Milestone v2.0 (Frontend Redesign) started. UI-only public-site redesign per `.planning/docs/REDESIGN_BRIEF.md` + `agentpulse-redesign-mockup.html`: persistent 3-tab nav with stateful active state, Source Serif 4 / IBM Plex Mono typography, a single light-mode violet accent (replacing the dark map theme), the Agent Economy as a 2-col grouped grid, a new "What is AgentPulse" About stub, and a spacing/polish pass. Backend / pipeline / Supabase / content untouched; deferred backend v2 items (negotiation graduation, per-block tuning, EU AI Act tracker) kept in separate milestones. Phase numbering continues from 11. v1.0 (Agent Economy Map) shipped + archived 2026-06-04 — see MILESTONES.md.*

*Milestone v1.0 close (2026-06-04) — Phase 10 complete (operator write commands — MILESTONE v1.0 COMPLETE, 11/11 phases). The operator's editorial-framing levers went live on Telegram: `/map-assign`, `/map-entry`, `/map-synth`, `/map-tension` (CMD-05..08), all owner-gated and routed through the allowlist-guarded `_economy_map_rpc` helper. Migration 040 added the `synth_requests` queue + `timeline_entries.reassigned_*` lifecycle + 4 SECURITY DEFINER write RPCs; 041 the open-draft UNIQUE index; 042 hardened `reassign_timeline_entry`. Phase 9 (2026-06-03) closed the autonomy boundary end-to-end with owner-gated `/map-approve` + `/map-reject` and the watermark advancing from the approved draft's `synthesized_from_through`. See MILESTONES.md + RETROSPECTIVE.md for the full v1.0 record.*
