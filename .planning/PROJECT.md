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
- [x] **REQ-SYNTH-LOOP** (SYNT-01/SYNT-02): Per-block synthesis triggers when ≥N new entries or ≥T days with ≥1 new entry; default `N=5/T=30` global — **Validated in Phase 7: synthesis-loop-core** (`is_block_eligible` + `synthesize_blocks_poller` on a daily `schedule` job; no-draft guard + `created_at` watermark recency; 21/21 test harness)
- [x] **REQ-SYNTH-IDENT** (SYNT-05): Synthesis prompt lives in hot-reloadable `economy_map/synth_identity.md` (mtime-based), not in code — **Validated in Phase 7** (`load_synth_identity` mtime cache + `is not None` guard; fail-loud `None` on missing/empty aborts the cycle with a durable `failed` run row)
- [x] **REQ-SYNTH-ROUTE** (SYNT-04): All synthesis LLM calls route through `llm-proxy:8200` (no direct Anthropic SDK calls — the RivalScope workaround we're not repeating) — **Validated in Phase 7** (`synthesis_sonnet_call` raw `httpx.post` to `{LLM_PROXY_URL}/anthropic/v1/messages`; zero `api.anthropic.com` / `routed_llm_call` in synthesis, code-review + test confirmed)
- [x] **REQ-SENTINEL-TENSION** (VLDT-01): Validator flags if the live-tension section is missing or trivialized post-synthesis — **Validated in Phase 8: validation-sentinels** (`run_sentinels` deterministic check: `_extract_section_body` for the `## The live tension` heading; flags `tension_preserved=false` on absent / <40-char / placeholder / verbatim-echo of `blocks.live_tension`; LLM "shallow-but-present" judge deferred to v2 per D-05)
- [x] **REQ-SENTINEL-LENGTH** (VLDT-02): Validator flags if synthesized body is shorter than 60% of prior published length — **Validated in Phase 8** (char-ratio `len(new)/len(prior) < 0.60`; cold-start with no prior published body → N/A, never a false flag, never divides)
- [x] **REQ-SENTINEL-MATURITY** (VLDT-03): Maturity jumps >1 stop flag `requires_attention=true` rather than auto-accept — **Validated in Phase 8** (absolute ordinal distance on `SYNTH_MATURITY_ORDER`; `>1` feeds the D-04 `requires_attention` rollup)
- [x] **REQ-SENTINEL-STRUCTURE** (VLDT-04): Six-part skeleton headings must all be present in synthesized output — **Validated in Phase 8** (heading-aware `structure_missing` via `_extract_section_body`, not substring — agrees with the tension check; this annotates, no longer blocks: the Phase 7 WR-02 missing-headings raise was removed per D-01)
- [x] **REQ-GATE-DRAFT**: Synthesized bodies always land as `draft` versions; Telegram card surfaces flags; nothing goes live without `/map-approve` — **Validated in Phase 9: gated-publishing-approval-commands** (draft-landing GATE-01 from Phase 7; flag-surfacing from Phase 8; owner-gated `/map-approve` + `/map-reject` shipped Phase 9 — `access_tier=='owner'` gate before any RPC, parameterized PostgREST RPC-POST to the Phase 2 atomic transactions, D-05 typed errors. Migrations 038+039 amend the publish watermark to advance from the approved draft's `synthesized_from_through` (D-01) with a COALESCE null-guard. Verified live: `/map-reject`→superseded (entries unabsorbed), `/map-approve`→published with watermark = synth-time not NOW() (3.6h-gap proof). Non-owner-refusal E2E deferred to live UAT; gate covered by the 15-test suite.)
- [ ] **REQ-PUBLISH-ATOMIC**: Approving a version flips its status, supersedes prior, updates `blocks.current_body_version_id` and `blocks.maturity` in one transaction
- [ ] **REQ-VERSION-IMMUTABLE**: `block_body_versions` is append-only — re-synthesis inserts; rejected drafts are superseded, not deleted
- [x] **REQ-RENDER-HUB** (RNDR-01): Hub page (`/map`) shows storyline header + seven-block visual + maturity pills with links to block pages — **Validated in Phase 4: hub-block-and-status-renderer** (`loadHub`/`renderHub` in `app.js`; live + operator-verified at aiagentspulse.com/#/map)
- [x] **REQ-RENDER-BLOCK** (RNDR-02): Block page (`/map/<slug>`) renders six-part skeleton (What it is → Why hard → Live tension → Where it stands → Evolution → Maturity) — **Validated in Phase 4** (renderer structurally complete; the six body headings come from synthesis `body_md` — full visual confirmation deferred to Phase 7, tracked in 04-HUMAN-UAT.md)
- [x] **REQ-RENDER-STATUS** (RNDR-03): Status page (`/status`) shows all blocks' maturity at a glance — same source as hub pills — **Validated in Phase 4** (`loadStatus`/`renderStatus`, identical `economy_map.blocks` query shape as hub)
- [x] **REQ-RENDER-LIVE** (RNDR-06): New timeline entry triggers re-render of the Evolution section without waiting for next synthesis — **Validated in Phase 4** (60s visibility-aware idle poll; operator-verified live insert appeared within 60s)
- [x] **REQ-RENDER-REUSE** (RNDR-05): Block pages publish via the existing `aiagentspulse.com` publish path (per Phase 0 findings) — **Validated in Phase 4** (scoped web rebuild, single `agentpulse-web` container, no new infra)
- [x] **REQ-TIMELINE-NEWEST** (RNDR-07): Evolution section renders newest-first across all blocks (controlled vocabulary, consistent default) — **Validated in Phase 4** (`.order('event_date', { ascending: false })` across all three query sites)
- [x] **REQ-CMD-STATUS** (CMD-01): `/map-status` — all blocks, tier, maturity pill, unabsorbed entry count, pending draft count — **Validated in Phase 6: telegram-read-only-scaffolding** (`handle_map_status` in `gato_brain.py`; live + smoke-verified against seeded seven-block data after scoped rebuild)
- [x] **REQ-CMD-PENDING** (CMD-02): `/map-pending` — drafts awaiting approval + `unsorted` entries awaiting assignment — **Validated in Phase 6** (`handle_map_pending`; full UUIDs + pre-filled write lines + explicit empty states; read-only by construction, code-review-confirmed)
- [ ] **REQ-CMD-APPROVE**: `/map-approve <version_id>` — publish a draft via atomic transaction
- [ ] **REQ-CMD-REJECT**: `/map-reject <version_id>` — supersede a draft, leave entries unabsorbed
- [x] **REQ-CMD-ASSIGN** (CMD-05): `/map-assign <entry_id> <block_slug>` — move `unsorted` entry to a block — **Validated in Phase 10: operator-write-commands** (owner-gated `handle_map_assign` → `reassign_timeline_entry` RPC: atomic INSERT-copy + UPDATE-original, provenance preserved, `FOR UPDATE` single-winner + server-side slug validation (migration 042, CR-01/WR-04); `reassigned_to_entry_id IS NULL` filter drops it from `/map-pending` immediately)
- [x] **REQ-CMD-ENTRY** (CMD-06): `/map-entry <block_slug> <text>` — manual timeline drop for things the pipeline missed — **Validated in Phase 10** (`handle_map_entry` splits on ` | `, both halves required, → `insert_manual_timeline_entry` RPC, append-only, dated today)
- [x] **REQ-CMD-SYNTH** (CMD-07): `/map-synth <block_slug>` — force re-synthesis now, ignoring trigger thresholds — **Validated in Phase 10** (`handle_map_synth` open-draft precondition (D-02) → `enqueue_synth_request`; processor `synth_request_drain_poller` on `schedule.every(30).seconds` runs `synthesize_block(force=True)` bypassing only the N/T predicate; migration 041 unique index + 23505 benign-skip backstop; orphaned-`processing` reclaim → terminal `failed` (WR-01); queryable terminal status per D-03)
- [x] **REQ-CMD-TENSION** (CMD-08): `/map-tension <block_slug> <text>` — update a block's `live_tension` (the editorial framing reserved for humans) — **Validated in Phase 10** (`handle_map_tension` → `set_block_live_tension` RPC; plain mutable UPDATE on `blocks`, visible on next render)
- [ ] **REQ-SCHEMA-ISOLATE**: All map tables live in `economy_map` schema; access via direct PostgREST with `Accept-Profile: economy_map`
- [ ] **REQ-SEED-BLOCKS**: Seven blocks seeded — three Substrate (identity-trust, memory-context, payments-settlement), three Behavior (autonomy-control, governance-accountability, psychology-disposition), one Frame (regulation-legal); negotiation-coordination starts as a section inside payments-settlement
- [x] **REQ-TOKENS-TIER**: Three tier accent colors pinned (teal/purple/coral/gray); applied via CSS custom properties — **Validated in Phase 3: design-tokens** (shipped 4 base + 4 on-dark variants in `docker/web/site/style-map.css`, WCAG AA against `#0a0a0f`)
- [x] **REQ-TOKENS-PILL**: Maturity pill component — five segments (nascent→emerging→contested→consolidating→mature), tier-accented fill, shared across hub/block/status — **Validated in Phase 3: design-tokens** (`.maturity-pill` + `[data-stage="N"] .seg:nth-child(-n+N)` rules in `style-map.css`)
- [x] **REQ-TOKENS-TIMELINE**: Timeline entry format pinned — `<event_date> · <what_shifted> / <why_it_mattered> [source ↗]` — consistent across all blocks — **Validated in Phase 3: design-tokens** (`.timeline-entry` two-line CSS contract with literal `↗` glyph)
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
*Last updated: 2026-06-04 — Phase 10 complete (operator write commands — MILESTONE v1.0 COMPLETE, 11/11 phases). The operator's editorial-framing levers are now live on Telegram: `/map-assign`, `/map-entry`, `/map-synth`, `/map-tension` (CMD-05..08), all owner-gated-first and routed through the generalized allowlist-guarded `_economy_map_rpc` helper. Migration 040 added the `synth_requests` queue, `timeline_entries.reassigned_*` lifecycle columns + trigger exemption, and 4 SECURITY DEFINER write RPCs; 041 added the WR-01 unique open-draft index; code-review follow-up 042 hardened `reassign_timeline_entry` (server-side slug validation + `FOR UPDATE`). Processor gained a 30s synth-request drain poller (force-synth bypasses N/T but never the open-draft invariant; orphaned-`processing` reclaim + 23505 benign-skip keep it fail-loud per D-03). All migrations applied live; gato_brain + processor rebuilt healthy. 5/5 success criteria verified in code; code review 1 Critical / 5 Warning / 2 Info — CR-01/WR-01/WR-02/WR-03/WR-04 fixed before verification, WR-05 accepted by design (frozen status CHECK set), 2 info deferred. 5 live-Telegram smoke items tracked in 10-HUMAN-UAT.md (status: partial). Pre-existing drift remaining: lab-data-provider image stale; REQUIREMENTS traceability table missing 10 v2-deferred IDs (NEGB/TUNE/DSGN/EUAI — out of v1.0 scope). Next: `/gsd-complete-milestone` to archive v1.0, or `/gsd-new-milestone` for v2.*

*Phase 9 (2026-06-03) — gated publishing + approval commands: the autonomy boundary is now CLOSED end-to-end. Owner-gated `/map-approve` + `/map-reject` added to gato_brain — `access_tier=='owner'` gate before any RPC, a parameterized PostgREST RPC-POST helper (`Content-Profile: economy_map`, allowlisted fn) calling the Phase 2 atomic `publish_block_version` / `reject_block_version`, and all five D-05 typed confirmation/error cases. Migration 038 amended the publish watermark to advance from the approved draft's `synthesized_from_through` (D-01, the IN-04 fix), and code-review CR-01 → migration 039 added a COALESCE null-guard so a NULL draft watermark never clobbers the block's. Both migrations applied live. 5/5 must-haves verified; 15/15 command tests. Code review 1 Critical / 2 Warning / 2 Info — CR-01/WR-01/IN-01/IN-02 fixed before verification, WR-02 accepted by design. DEPLOYED this session (scoped rebuilds): gato_brain, gato (OpenClaw — fixed a latent allowlist bug that had blocked the ENTIRE `/map-*` surface, incl. Phase 6/8 reads, from ever reaching gato_brain over Telegram), and processor (first-time cutover of the Phase 7/8 synthesis pipeline, which had never been deployed). Live UAT: `/map-reject` PASS (superseded, entries unabsorbed) and `/map-approve` PASS with the D-01 watermark proven (watermark = synth-time, a 3.6h gap from the approval instant). Non-owner-refusal live UAT deferred (needs a 2nd Telegram account; gate is unit-tested). Pre-existing drift remaining: lab-data-provider image stale; REQUIREMENTS traceability table missing 10 future-phase IDs. Next: Phase 10 — operator write commands (manual `/map-synth`, `/map-assign` for the unsorted queue, plus the deferred WR-01 duplicate-draft UNIQUE index))*
