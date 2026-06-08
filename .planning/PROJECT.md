# AgentPulse

## What This Is

A multi-agent intelligence platform for the AI agent economy: eight cooperating Docker services (Telegram-facing bot, conversational middleware, background processor, analyst, newsletter writer, research agent, LLM proxy, web frontend) that ingest content, synthesize findings, and publish daily-to-weekly outputs (newsletters, X posts, briefings) for the operator. Controlled via Telegram commands; deployed on a single Linux server with Supabase as the shared data store.

## Core Value

**Synthesis with editorial integrity.** Autonomous ingestion and drafting accelerate the operator's output, but every consequential publication is gated by human approval — silence and homogenization are the failure modes to design against.

## Current Milestone: v2.1 Agent Economy Content

**Goal:** Publish the Agent Economy hub + 7 block bodies live on `aiagentspulse.com/#/map`, with the hub's blocks clickable through to their deep-dive pages — filling the v2.0 grid (currently 5/7 blocks unpublished) with real editorial content.

**Target work:**
- Load 8 canonical markdown bodies (hub `agent-economy` + 7 blocks) into `economy_map` as unsorted/unpublished — content lands, visitors unaffected
- Verify `#/map/<slug>` cross-block links + hub→block click-through on a non-published preview route; maturity pills render the 3 values (building / contested / nascent)
- Publish via the existing atomic publish RPC in ONE operator-approved batch (web-only scoped deploy)

**Open items for discuss-phase (per EXECUTION_BRIEF.md — do not decide unilaterally):**
- ✓ **Roster diff vs the live map — RESOLVED in Phase 15** (operator-approved 2026-06-08; `15-RECONCILIATION.md`): keep the live 3-tier model (substrate/behavior/frame, D-02); `negotiation-coordination` first-published as a NEW behavior block (D-03); `regulation-legal` KEPT DEFERRED (body-less frame card, sort_order 8, D-02); the D-03 collision-free `{1..8}` sort_order reshuffle and the D-04 Option-A hub-tier accommodation (relax tier CHECK + `'hub'` sentinel) are pinned for Phase 16.
- ✓ **Maturity enum — RESOLVED in Phase 15** (INV-02): live enum is `nascent/emerging/contested/consolidating/mature`; `building` is NOT a member → the docs' `building` (substrate slugs 1/2/3) is an operator-approved `building→emerging` remap applied at Phase-16 load time (no `ALTER TYPE`, no app.js change). Flag F-2: the substrate pills render `emerging` (stage 2), not `building` — Phase-17 verification text should expect `emerging`.
- **Still open:** Hub block list as cards (preferred) vs prose links; whether `nascent` blocks get distinct visual treatment — deferred to Phase 17 per the Phase-15 approval.

**Standing constraints (the spine):** direct PostgREST + `Accept-Profile` for `economy_map` (never supabase-py `.in_()`); append-only trigger — corrections via the canonical-body-rewrite path, not raw UPDATE; fail-loud on any missing field; branch + `/diff` + web-only scoped deploy — no pipeline / proxy / agent-service changes.

**Source content:** `.planning/docs/00-hub.md` … `07-psychology-disposition.md` (+ `EXECUTION_BRIEF.md`). Frontmatter (slug/tier/title/subtitle/order/maturity) is the metadata source of truth.

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
- ✓ **Frontend Redesign (v2.0)** — UI-only public-site redesign shipped live to `aiagentspulse.com` 2026-06-08 (scoped `agentpulse-web` cutover): a light-mode CSS-variable design system (`style-base.css` :root tokens, Source Serif 4 / IBM Plex Mono, single violet accent replacing the dark map theme), a persistent stateful 3-tab nav shell with `← Back` controls and route-derived active state, the Newsletter list/article restyled with the Technical/Strategic toggle scoped to the Newsletter section, the Agent Economy re-rendered as a responsive grouped card grid (`style-map.css` retired → 2-sheet cascade), and a real "What is AgentPulse" About page + a site-wide radius/spacing token sweep. Frontend-only — backend/pipeline/Supabase/content untouched; verified in code (8/8 plans) + end-to-end over public HTTPS. Browser perceptual/editorial sign-off (Phase 13/14 HUMAN-UAT) deferred to the live-site walk. (NAV-01..04, TYPE-01..03, COLOR-01..02, TGL-01/02, MAP-01..04, ABOUT-01, POLISH-01) — v2.0

### Active

<!-- No active milestone. v1.0 + v2.0 shipped. Next milestone requirements are defined via /gsd-new-milestone (questioning → research → requirements → roadmap). -->

_None — v2.0 shipped. Start the next milestone with `/gsd-new-milestone`; its requirements land here._

**Carried-forward backend follow-ups** (out of v2.0 frontend scope; tracked in `.planning/todos/pending/`, candidates for a backend milestone):
- analyst predictions title-expire bug (P2); soft-cap allow-negative hardening (P5); pay-endpoint 500 activation E2E — RPC root-cause fixed in m037 (P2); phase-05 intake-classifier review follow-ups WR02/04/05 (P4); research trigger file permissions (P4).

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
*Last updated: 2026-06-08 after v2.0 (Frontend Redesign) milestone — SHIPPED + closed (deployed live to aiagentspulse.com via scoped agentpulse-web cutover; all 4 phases / 8 plans validated; tagged v2.0). Phase 14 (About Stub + Polish Pass) complete + operator-approved: the `#/about` route now renders the real "What is AgentPulse" page (eyebrow → serif title → mono page-sub → 3 accuracy-guarded prose paragraphs → a 5-pill agent row: Processor/Analyst/Research/Newsletter/Gato; Gato Brain / LLM Proxy / Web described in prose) on the Phase-11 token system, with net-new fully token-anchored CSS (`.about`/`.agent-row`/`.agent-pill`/`.an`/`.ad`, single-accent, static non-interactive pills) (ABOUT-01, D-01..D-03). Plan 02 ran the POLISH-01 consistency sweep: the three subscribe-form 6px radii snapped to role tokens so the D-05 confirmation gate passes over the full live cascade (all 17 radii tokenized incl. the new agent-pill), and 11 off-grid vertical-rhythm literals across 10 surfaces re-anchored onto `--space-*` tokens (D-04/D-05). CSS-only; `app.js`/`style-base.css` untouched. Code review: 0 blockers, 1 advisory warning (dead `.about-lede` rule in `style-base.css`, out of plan scope), 3 info. 7/7 must-haves verified in code; 4 browser/editorial items persisted in 14-HUMAN-UAT.md for the batch-deploy verify (D-06). **This was the final v2.0 phase — all 4 phases (11–14) executed; the operator-approved batch deploy + accumulated 11/12/13/14 browser-UAT is the remaining ship step.** Phase 13 (Agent Economy Grid) complete + operator-approved: the Agent Economy hub (`#/map`) re-rendered as a responsive 2-col (1-col mobile) grouped card grid on the Phase 11 light/serif system — bordered cards (serif title/desc, 3px violet accent stripe, hover lift), canonical SUBSTRATE/BEHAVIOR/FRAME tier grouping from live `economy_map.blocks`, full-width DEFERRED cards with empty dots + `· DEFERRED` tag, and a serif "The Agent Economy" in-content header (MAP-01..04, D-04/D-05/D-06). Plan 02 de-darkened the block reading view + `#/status` onto the serif/light single-accent system (TYPE-01 serif body prose, no Courier, no `data-accent`) and retired `style-map.css` entirely (delete-and-fold complete; cascade = style-base.css + style-shared.css). Code review: 0 blockers, 1 advisory warning (escapeHtml attr-context hardening — currently safe), 3 info. 10/10 must-haves verified in code; 6 browser checks persisted in 13-HUMAN-UAT.md for batch-deploy verify per D-01. Next: Phase 14 (About Stub + Polish Pass). Phase 12 (Newsletter Section Restyle) complete + operator-verified: Newsletter list + article restyled onto the serif/light system (TYPE-01 serif reading text, 0 mono body), the Technical/Strategic toggle relocated to the Newsletter list route only (TGL-01, D-01) with a filled-accent segmented pill + mono hint line (TGL-02), and a magazine article header. Next: Phase 13 (Agent Economy Grid — re-render the map as a responsive 2-col grouped card grid, replacing the current long vertical scroll). Phase 11 (Design System + Nav Shell) complete + operator-verified: light-mode token palette, Source Serif 4 / IBM Plex Mono typography, and the persistent stateful 3-tab sticky nav shell with ← Back controls (NAV-01..04, TYPE-01..03, COLOR-01..02). A minimal `#/about` stub was pulled forward (full page = Phase 14). — Milestone v2.0 (Frontend Redesign) started. UI-only public-site redesign per `.planning/docs/REDESIGN_BRIEF.md` + `agentpulse-redesign-mockup.html`: persistent 3-tab nav with stateful active state, Source Serif 4 / IBM Plex Mono typography, a single light-mode violet accent (replacing the dark map theme), the Agent Economy as a 2-col grouped grid, a new "What is AgentPulse" About stub, and a spacing/polish pass. Backend / pipeline / Supabase / content untouched; deferred backend v2 items (negotiation graduation, per-block tuning, EU AI Act tracker) kept in separate milestones. Phase numbering continues from 11. v1.0 (Agent Economy Map) shipped + archived 2026-06-04 — see MILESTONES.md.*

*Milestone v2.1 (Agent Economy Content) — Phase 15 (Inventory & Roster Reconciliation) complete + operator-approved 2026-06-08 (verified passed, 7/7 must-haves). A no-write documentation phase: `15-CONTRACT.md` documents the live `economy_map` storage + serve contract from the running schema (block columns + 3-tier CHECK, the 2 append-only triggers and exactly which tables they guard, the atomic `publish_block_version` RPC = migration 039, anon published-only RLS, the hardcoded-`HUB_STORYLINE` serve path) and the verified 5-member maturity enum (`building`∉enum → operator-approved `building→emerging` remap at Phase-16 load, no `ALTER TYPE`); `15-RECONCILIATION.md` locks the per-slug roster (3-tier model kept, `negotiation-coordination` new block, `regulation-legal` kept deferred, D-03 collision-free `{1..8}` sort_order reshuffle, D-04 Option-A hub-tier accommodation pinned for Phase 16). `15-APPROVAL.md` records the read-before-write gate. Phase boundary held: no migration ≥043, no `app.js` edit, no `economy_map` write (highest migration is 042). Review docs also rendered to HTML for operator review (`.planning/tools/md_to_html.py`). Next: Phase 16 (Content Load — unpublished).*

*Milestone v1.0 close (2026-06-04) — Phase 10 complete (operator write commands — MILESTONE v1.0 COMPLETE, 11/11 phases). The operator's editorial-framing levers went live on Telegram: `/map-assign`, `/map-entry`, `/map-synth`, `/map-tension` (CMD-05..08), all owner-gated and routed through the allowlist-guarded `_economy_map_rpc` helper. Migration 040 added the `synth_requests` queue + `timeline_entries.reassigned_*` lifecycle + 4 SECURITY DEFINER write RPCs; 041 the open-draft UNIQUE index; 042 hardened `reassign_timeline_entry`. Phase 9 (2026-06-03) closed the autonomy boundary end-to-end with owner-gated `/map-approve` + `/map-reject` and the watermark advancing from the approved draft's `synthesized_from_through`. See MILESTONES.md + RETROSPECTIVE.md for the full v1.0 record.*
