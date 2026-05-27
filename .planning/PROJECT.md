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

### Active

<!-- Current milestone: The Agent Economy — living reference articles (build spec v2). -->

- [ ] **REQ-INTAKE-AUTO**: Every finalized tier-1 newsletter event is auto-classified to a block with a confidence floor; entries below floor land in `unsorted` for one-tap reassignment
- [ ] **REQ-INTAKE-TRACE**: Every timeline entry carries `source_edition_id` for full traceability back to the newsletter that produced it
- [ ] **REQ-LEDGER-APPEND**: Timeline is append-only — corrections are new entries, history is never mutated
- [ ] **REQ-SYNTH-LOOP**: Per-block synthesis triggers when ≥N new entries or ≥T days with ≥1 new entry; default `N=5/T=30` global
- [ ] **REQ-SYNTH-IDENT**: Synthesis prompt lives in hot-reloadable `economy_map/synth_identity.md` (mtime-based), not in code
- [ ] **REQ-SYNTH-ROUTE**: All synthesis LLM calls route through `llm-proxy:8200` (no direct Anthropic SDK calls — the RivalScope workaround we're not repeating)
- [ ] **REQ-SENTINEL-TENSION**: Validator flags if the live-tension section is missing or trivialized post-synthesis
- [ ] **REQ-SENTINEL-LENGTH**: Validator flags if synthesized body is shorter than 60% of prior published length
- [ ] **REQ-SENTINEL-MATURITY**: Maturity jumps >1 stop flag `requires_attention=true` rather than auto-accept
- [ ] **REQ-SENTINEL-STRUCTURE**: Six-part skeleton headings must all be present in synthesized output
- [ ] **REQ-GATE-DRAFT**: Synthesized bodies always land as `draft` versions; Telegram card surfaces flags; nothing goes live without `/map-approve`
- [ ] **REQ-PUBLISH-ATOMIC**: Approving a version flips its status, supersedes prior, updates `blocks.current_body_version_id` and `blocks.maturity` in one transaction
- [ ] **REQ-VERSION-IMMUTABLE**: `block_body_versions` is append-only — re-synthesis inserts; rejected drafts are superseded, not deleted
- [ ] **REQ-RENDER-HUB**: Hub page (`/map`) shows storyline header + seven-block visual + maturity pills with links to block pages
- [ ] **REQ-RENDER-BLOCK**: Block page (`/map/<slug>`) renders six-part skeleton (What it is → Why hard → Live tension → Where it stands → Evolution → Maturity)
- [ ] **REQ-RENDER-STATUS**: Status page (`/status`) shows all blocks' maturity at a glance — same source as hub pills
- [ ] **REQ-RENDER-LIVE**: New timeline entry triggers re-render of the Evolution section without waiting for next synthesis
- [ ] **REQ-RENDER-REUSE**: Block pages publish via the existing `aiagentspulse.com` publish path (per Phase 0 findings)
- [ ] **REQ-TIMELINE-NEWEST**: Evolution section renders newest-first across all blocks (controlled vocabulary, consistent default)
- [ ] **REQ-CMD-STATUS**: `/map-status` — all blocks, tier, maturity pill, unabsorbed entry count, pending draft count
- [ ] **REQ-CMD-PENDING**: `/map-pending` — drafts awaiting approval + `unsorted` entries awaiting assignment
- [ ] **REQ-CMD-APPROVE**: `/map-approve <version_id>` — publish a draft via atomic transaction
- [ ] **REQ-CMD-REJECT**: `/map-reject <version_id>` — supersede a draft, leave entries unabsorbed
- [ ] **REQ-CMD-ASSIGN**: `/map-assign <entry_id> <block_slug>` — move `unsorted` entry to a block
- [ ] **REQ-CMD-ENTRY**: `/map-entry <block_slug> <text>` — manual timeline drop for things the pipeline missed
- [ ] **REQ-CMD-SYNTH**: `/map-synth <block_slug>` — force re-synthesis now, ignoring trigger thresholds
- [ ] **REQ-CMD-TENSION**: `/map-tension <block_slug> <text>` — update a block's `live_tension` (the editorial framing reserved for humans)
- [ ] **REQ-SCHEMA-ISOLATE**: All map tables live in `economy_map` schema; access via direct PostgREST with `Accept-Profile: economy_map`
- [ ] **REQ-SEED-BLOCKS**: Seven blocks seeded — three Substrate (identity-trust, memory-context, payments-settlement), three Behavior (autonomy-control, governance-accountability, psychology-disposition), one Frame (regulation-legal); negotiation-coordination starts as a section inside payments-settlement
- [ ] **REQ-TOKENS-TIER**: Three tier accent colors pinned (teal/purple/coral/gray); applied via CSS custom properties
- [ ] **REQ-TOKENS-PILL**: Maturity pill component — five segments (nascent→emerging→contested→consolidating→mature), tier-accented fill, shared across hub/block/status
- [ ] **REQ-TOKENS-TIMELINE**: Timeline entry format pinned — `<event_date> · <what_shifted> / <why_it_mattered> [source ↗]` — consistent across all blocks
- [ ] **REQ-PHASE0-DIAGNOSTIC**: Render-stack diagnostic delivered FIRST (no code changes) — confirms `aiagentspulse.com` publish mechanism before renderer design

### Out of Scope

<!-- Explicit boundaries with reasoning to prevent re-adding. -->

- **Bespoke typography / page chrome for v1** — Pin only tokens that encode information (tier colors, maturity pill, timeline format); body font, page width, spacing inherit defaults. Substance over design; defer to v2 once the machine works.
- **Negotiation as its own block at launch** — Today it would be 80% future-tense. Lives as a section inside Payments; graduates to its own block when real bid/ask behavior exists.
- **Per-block synthesis threshold tuning at launch** — Ship global defaults N=5/T=30; revisit per-block tuning (Payments weekly cadence, Psychology quarterly) only if data forces it in v2.
- **Oldest-first timeline rendering** — Newest-first is the default; feels live, matches the editorial flag of an evolving map.
- **Direct Anthropic SDK calls from synthesis** — All LLM calls route through `llm-proxy:8200` for budget governance. The RivalScope direct-call workaround is the anti-pattern we're not repeating.
- **In-place body mutation** — `block_body_versions` is append-only; re-synthesis inserts new versions, never overwrites. Prevents the silent-degradation failure class.
- **Mutating timeline history** — Corrections are new entries with reference to the prior; `unsorted` entries are reassigned, not edited. Prevents the silent-misfile failure class.
- **Holding regulation block until tracker feeds it** — Ship as lightly-populated closing frame now; the EU AI Act tracker pipeline will feed it over time.
- **External cache layer / message broker for synthesis** — Single Linux server, Supabase polling and HTTP only. Matches existing architecture; introducing infrastructure is yak shaving until a measurable need surfaces.

## Context

**Existing system the milestone plugs into:**
- Newsletter pipeline (block-based, 5-phase) is the upstream source — finalized tier-1 events emit timeline candidates at the point each edition completes (see `docker/newsletter/newsletter_poller.py`, block pipeline modules)
- LLM Proxy (`docker/llm-proxy/proxy.py`, port 8200) is the mandatory gateway for all LLM calls with budget governance — per-agent `ap_<agent>_<hash>` keys, wallet reserve/settle pattern
- Supabase schema isolation pattern already exists (`eu_ai_act` schema, `Accept-Profile` header for direct PostgREST) — reuse for `economy_map`
- Telegram operator control surface (Gato → Gato Brain) is the gating mechanism — `/x-*` family is the closest analog for the `/map-*` family
- 27 existing migrations in `supabase/migrations/`; new milestone adds at least one (`028_economy_map_schema.sql` or similar)

**Recent history that shapes design:**
- Block pipeline shipped May 2026 — Phase D verification drove fabrications from 27 to 0 by enforcing grounding against block-derived facts. The sentinel-validator pattern in section 4.4 mirrors this learning directly.
- Fix 3 (extraction prompt rework, May 2026) — silent failure cascade where a mis-specified prompt produced 0.06% hit rate AND a UUID type mismatch silently dropped every insert. Drives the design principle: silence is the enemy; a flagged draft beats a missing one.
- 27-day wallet bug (referenced in the build spec) — expensive silent error → the explicit autonomy boundary: cheap-and-visible errors run unattended; expensive-and-silent errors get gated.
- supabase-py `.in_()` silent-failure bug — drives the direct-PostgREST mandate for the new schema.

**Storyline:** The agent economy is the project of building, for autonomous software, the trust and coordination infrastructure humans took centuries to build — in years, and without us in the loop. Editorial flag: **capability is solved; trust and coordination are not.**

## Constraints

- **Architecture**: Single Linux server, Docker Compose orchestration, Supabase as shared store — no Kubernetes, no message broker, no external cache. New work integrates here.
- **LLM access**: All model calls route through `http://llm-proxy:8200`. Direct provider SDK calls are forbidden (budget governance + the RivalScope lesson).
- **Schema access**: `economy_map` tables accessed via direct PostgREST HTTP with `Accept-Profile: economy_map` header. Do not use supabase-py `.in_()` (silent failure).
- **Synthesis model**: Claude Sonnet for editorial synthesis (consistent with newsletter prose). DeepSeek V3 for bulk classification (cost-efficient). Both routed via proxy.
- **Publish path**: Block pages must reuse the existing `aiagentspulse.com` publish mechanism. Phase 0 diagnostic confirms the path before renderer design.
- **Autonomy boundary (the spine)**: Intake is autonomous; publishing is gated. Every design choice serves this rule. Append-only data structures + draft-then-approve flow + flagged-not-blocked validation.
- **Editorial framing in human hands**: `live_tension` and synthesis prompt voice (via `synth_identity.md`) stay operator-controlled; the loop synthesizes, the operator frames.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Negotiation as section inside Payments at launch | 80% future-tense today; graduate to own block when real bid/ask behavior exists | — Pending |
| Regulation ships as lightly-populated closing frame | Establishes the slot in the map; EU AI Act tracker feeds it over time | — Pending |
| Global synthesis defaults N=5/T=30 (no per-block tuning v1) | Ship simple; revisit only if data forces per-block cadence | — Pending |
| Timeline order: newest-first | Feels live; matches editorial flag of an evolving map | — Pending |
| Append-only `block_body_versions` + `timeline_entries` | Eliminates silent-degradation failure class (the 27-day wallet bug pattern) | — Pending |
| Schema isolation via `economy_map` + direct PostgREST | Mirrors `eu_ai_act` pattern; sidesteps supabase-py `.in_()` silent failure | — Pending |
| Synthesizer voice hot-reload via `synth_identity.md` | Iterate voice without redeploys; matches existing agent identity pattern | — Pending |
| Phase 0 diagnostic-only render-stack audit before renderer build | Existing `aiagentspulse.com` publish path is unknown; reusing it is preferred but must be confirmed | — Pending |
| Sentinels flag, never block | Silence is the enemy; a flagged draft beats a missing draft | — Pending |
| Synthesis via `llm-proxy:8200` (no direct Anthropic SDK) | Budget governance + the RivalScope anti-pattern is the lesson | — Pending |

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
*Last updated: 2026-05-27 — Phase 2 complete (economy_map schema + 7-block seed + atomic publish RPC + append-only triggers landed; downstream phases 3, 5, 7, 9 inherit a structurally-sound data layer)*
