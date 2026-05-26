# Requirements: AgentPulse — The Agent Economy (Living Reference Articles)

**Defined:** 2026-05-26
**Milestone:** The Agent Economy — living reference articles (build spec v2)
**Core Value:** Synthesis with editorial integrity. Autonomous ingestion accelerates output; consequential publications stay gated. Silence and homogenization are the failure modes to design against.

## v1 Requirements

### Diagnostic (Phase 0 — no code changes)

- [ ] **DIAG-01**: Inspect how `aiagentspulse.com` is served from the Hetzner box — identify static vs. server-rendered, container/service, framework, HTML emission point
- [ ] **DIAG-02**: Document the publish mechanism — how a new edition page currently gets to production
- [ ] **DIAG-03**: Locate templates and confirm whether block pages can reuse the same publish path (preferred) or need a sibling route
- [ ] **DIAG-04**: Findings report fills section 6 of the build spec before any renderer work begins

### Schema (`economy_map`)

- [ ] **SCHM-01**: Create isolated `economy_map` schema following the `eu_ai_act` pattern; access via direct PostgREST with `Accept-Profile: economy_map`
- [ ] **SCHM-02**: `blocks` table — identity, current maturity, `current_body_version_id` FK; never holds body text
- [ ] **SCHM-03**: `block_body_versions` table — append-only canonical body history with `draft`/`published`/`superseded` status, `validator_report` jsonb, `proposed_maturity`
- [ ] **SCHM-04**: `timeline_entries` table — append-only narrative ledger with `block_slug`, `event_date`, `what_shifted`, `why_it_mattered`, `source_url`, `source_edition_id`, `tag_confidence`
- [ ] **SCHM-05**: Maturity enum: `nascent` → `emerging` → `contested` → `consolidating` → `mature`
- [ ] **SCHM-06**: Atomic publish transaction — flip version status, supersede prior, update `blocks.current_body_version_id` and `blocks.maturity` in one transaction
- [ ] **SCHM-07**: Seed seven blocks with `live_tension`, `subtitle`, `tier`, `accent`, `sort_order` — three Substrate, three Behavior, one Frame (regulation-legal)
- [ ] **SCHM-08**: `unsorted` is a valid `block_slug` for low-confidence timeline entries

### Intake (autonomous)

- [ ] **INTK-01**: Newsletter pipeline emits timeline candidates at the point an edition's events/clusters are finalized (each finalized tier-1 event)
- [ ] **INTK-02**: Classifier (DeepSeek V3, routed via `llm-proxy:8200`) assigns `block_slug` and `tag_confidence` to each event
- [ ] **INTK-03**: `tag_confidence ≥ 0.6` → write directly to that block's timeline; below → write to `unsorted`
- [ ] **INTK-04**: Every entry carries `source_edition_id` for traceability
- [ ] **INTK-05**: Append-only enforcement — corrections are new entries, never mutations of prior rows

### Synthesis loop (per block, the autonomous core)

- [ ] **SYNT-01**: Trigger evaluation — eligible when `≥ N=5` new entries since `last_synthesized_at` OR `≥ T=30 days` with ≥1 new entry
- [ ] **SYNT-02**: Trigger runs on a schedule (cron or existing orchestration poll); implementation choice deferred to executor
- [ ] **SYNT-03**: Input assembly — current `published` body, all `timeline_entries` since prior `synthesized_from_through` (ordered by `event_date`), `live_tension`, current `maturity` — concrete entries, never cluster labels alone
- [ ] **SYNT-04**: Generation — single editorial LLM call, Claude Sonnet, routed through `http://llm-proxy:8200` (no direct Anthropic SDK)
- [ ] **SYNT-05**: Synthesis prompt lives in `economy_map/synth_identity.md`, hot-reloaded via mtime — voice iterates without redeploys
- [ ] **SYNT-06**: Output is a rewritten `body_md` plus a `proposed_maturity`

### Validation sentinels

- [ ] **VLDT-01**: **Tension preserved** — live-tension section still exists and is non-trivial post-synthesis
- [ ] **VLDT-02**: **Length floor** — body not shorter than 60% of prior published length
- [ ] **VLDT-03**: **Maturity jump guard** — `proposed_maturity` differs from current by >1 stop → flag `requires_attention=true`
- [ ] **VLDT-04**: **Structure intact** — all six skeleton headings present
- [ ] **VLDT-05**: Failed sentinels annotate (`validator_report` jsonb) but do not block draft creation — silence is the enemy
- [ ] **VLDT-06**: Telegram card surfaces flags loudly so a flagged draft is the visible outcome

### Gated publishing

- [ ] **GATE-01**: Every synthesized body lands as a `draft` version; nothing goes live without explicit approval
- [ ] **GATE-02**: `/map-approve <version_id>` runs the atomic publish transaction, triggers re-render, updates `last_synthesized_at`
- [ ] **GATE-03**: `/map-reject <version_id>` sets status to `superseded`, leaves timeline entries unabsorbed for the next synthesis
- [ ] **GATE-04**: Versioned-not-overwritten — rejected drafts persist as `superseded`, never deleted

### Renderer (per Phase 0 findings)

- [ ] **RNDR-01**: Hub page (`/map` or `/`) — storyline header + seven-block visual + per-block maturity pill linking to block pages
- [ ] **RNDR-02**: Block page (`/map/<slug>`) — six-part skeleton: (1) What it is, (2) Why it's hard, (3) The live tension, (4) Where it stands today (synthesized body), (5) Evolution (timeline entries, newest-first), (6) Maturity indicator
- [ ] **RNDR-03**: Status page (`/status`) — all blocks' maturity at a glance, same data source as hub pills
- [ ] **RNDR-04**: Hub and status read the same maturity source (one source of truth)
- [ ] **RNDR-05**: Block pages reuse the existing `aiagentspulse.com` publish path (per Phase 0)
- [ ] **RNDR-06**: Re-render is triggered by both a publish (4.6) AND a timeline entry insert — Evolution section is live data
- [ ] **RNDR-07**: Evolution section default order is newest-first across all blocks

### Telegram control surface (`/map-*`)

- [ ] **CMD-01**: `/map-status` — all blocks, tier, maturity pill, count of unabsorbed timeline entries, count of pending drafts
- [ ] **CMD-02**: `/map-pending` — drafts awaiting approval + `unsorted` entries awaiting assignment
- [ ] **CMD-03**: `/map-approve <version_id>` — publish draft body via atomic transaction
- [ ] **CMD-04**: `/map-reject <version_id>` — supersede draft, no live change
- [ ] **CMD-05**: `/map-assign <entry_id> <block_slug>` — move `unsorted` entry to a block
- [ ] **CMD-06**: `/map-entry <block_slug> <text>` — manual timeline drop; fills `what_shifted`, prompts/accepts inline for `why_it_mattered`
- [ ] **CMD-07**: `/map-synth <block_slug>` — force re-synthesis now, ignoring trigger thresholds
- [ ] **CMD-08**: `/map-tension <block_slug> <text>` — update a block's `live_tension`

### Design tokens (v1 — only what encodes information)

- [ ] **TOKN-01**: Tier accent colors as CSS custom properties — `--accent-teal: #0F6E56` (substrate), `--accent-purple: #534AB7` (behavior), `--accent-coral: #993C1D` (psychology), `--accent-gray: #5F5E5A` (regulation/frame)
- [ ] **TOKN-02**: Maturity pill component — five segments (nascent→emerging→contested→consolidating→mature), left-to-right fill using tier accent; same component on hub/block/status (single source of truth)
- [ ] **TOKN-03**: Timeline entry format — `<event_date> · <what_shifted>` line, `<why_it_mattered> [source ↗]` line; fixed across all blocks
- [ ] **TOKN-04**: Body font, page width, spacing, nav chrome inherit existing site / system default — no bespoke typography v1

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Negotiation Block Graduation

- **NEGB-01**: Promote `negotiation-coordination` from a section inside `payments-settlement` to its own block once real bid/ask behavior exists
- **NEGB-02**: Backfill timeline entries from payments into the new block where applicable

### Per-Block Threshold Tuning

- **TUNE-01**: Per-block override of `N` (entry threshold) — Payments may want N=3, Psychology may want N=8
- **TUNE-02**: Per-block override of `T` (time threshold) — Payments weekly, Psychology quarterly
- **TUNE-03**: Configuration surface (Telegram or env) to set/inspect per-block thresholds

### Design v2 Pass

- **DSGN-01**: Bespoke typography for body text and headings
- **DSGN-02**: Page width / spacing / nav chrome customized to the project's identity
- **DSGN-03**: Hub seven-block visual upgraded beyond minimal token-only treatment

### EU AI Act Integration

- **EUAI-01**: Wire the existing `eu_ai_act` schema/tracker as a feed into the `regulation-legal` block timeline
- **EUAI-02**: Classifier extension to route AI-regulation events from this source

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Bespoke typography / page chrome for v1 | Substance over design; pin only information-encoding tokens, inherit the rest. v2 design pass after the machine works. |
| Negotiation as its own block at launch | 80% future-tense today; lives as a section in Payments until real bid/ask behavior exists |
| Per-block synthesis threshold tuning at launch | Ship global N=5/T=30; revisit only if data forces per-block cadence |
| Oldest-first timeline rendering | Newest-first feels live; matches editorial flag of an evolving map |
| Direct Anthropic SDK calls from synthesis | The RivalScope workaround we're not repeating. Always route through `llm-proxy:8200` |
| In-place body mutation | Append-only `block_body_versions`; prevents silent degradation |
| Mutating timeline history | Append-only ledger; corrections are new entries, `unsorted` reassignments leave the source untouched |
| Holding regulation block until tracker feeds it | Ship as lightly-populated closing frame; establishes the slot |
| External cache layer / message broker for synthesis | Single Linux server + Supabase polling matches existing arch; no infra changes |
| Auto-publish on validation pass | Every body is `draft` until human approval — autonomy boundary is non-negotiable for the body |
| Deleting rejected drafts | `superseded` is the terminal state; visibility into rejected work matters |

## Traceability

Every v1 requirement is mapped to exactly one phase. Coverage: 52/52.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DIAG-01 | Phase 1 | Pending |
| DIAG-02 | Phase 1 | Pending |
| DIAG-03 | Phase 1 | Pending |
| DIAG-04 | Phase 1 | Pending |
| SCHM-01 | Phase 2 | Pending |
| SCHM-02 | Phase 2 | Pending |
| SCHM-03 | Phase 2 | Pending |
| SCHM-04 | Phase 2 | Pending |
| SCHM-05 | Phase 2 | Pending |
| SCHM-06 | Phase 2 | Pending |
| SCHM-07 | Phase 2 | Pending |
| SCHM-08 | Phase 2 | Pending |
| TOKN-01 | Phase 3 | Pending |
| TOKN-02 | Phase 3 | Pending |
| TOKN-03 | Phase 3 | Pending |
| TOKN-04 | Phase 3 | Pending |
| RNDR-01 | Phase 4 | Pending |
| RNDR-02 | Phase 4 | Pending |
| RNDR-03 | Phase 4 | Pending |
| RNDR-04 | Phase 4 | Pending |
| RNDR-05 | Phase 4 | Pending |
| RNDR-06 | Phase 4 | Pending |
| RNDR-07 | Phase 4 | Pending |
| INTK-01 | Phase 5 | Pending |
| INTK-02 | Phase 5 | Pending |
| INTK-03 | Phase 5 | Pending |
| INTK-04 | Phase 5 | Pending |
| INTK-05 | Phase 5 | Pending |
| CMD-01 | Phase 6 | Pending |
| CMD-02 | Phase 6 | Pending |
| SYNT-01 | Phase 7 | Pending |
| SYNT-02 | Phase 7 | Pending |
| SYNT-03 | Phase 7 | Pending |
| SYNT-04 | Phase 7 | Pending |
| SYNT-05 | Phase 7 | Pending |
| SYNT-06 | Phase 7 | Pending |
| VLDT-01 | Phase 8 | Pending |
| VLDT-02 | Phase 8 | Pending |
| VLDT-03 | Phase 8 | Pending |
| VLDT-04 | Phase 8 | Pending |
| VLDT-05 | Phase 8 | Pending |
| VLDT-06 | Phase 8 | Pending |
| GATE-01 | Phase 9 | Pending |
| GATE-02 | Phase 9 | Pending |
| GATE-03 | Phase 9 | Pending |
| GATE-04 | Phase 9 | Pending |
| CMD-03 | Phase 9 | Pending |
| CMD-04 | Phase 9 | Pending |
| CMD-05 | Phase 10 | Pending |
| CMD-06 | Phase 10 | Pending |
| CMD-07 | Phase 10 | Pending |
| CMD-08 | Phase 10 | Pending |

**Coverage:**
- v1 requirements: 52 total
- Mapped to phases: 52 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-26*
*Last updated: 2026-05-26 — traceability populated by gsd-roadmapper (10 phases, FINE granularity)*
