# Roadmap: AgentPulse — The Agent Economy (Living Reference Articles)

## Overview

Ten phases ordered by the build spec's risk/dependency chain (section 9). The journey starts with a diagnostic-only audit of the existing `aiagentspulse.com` publish stack (no code changes), then lays the `economy_map` schema and seeds the seven blocks as the foundation everything else builds on. Design tokens and the renderer follow — establishing the visible surface before the autonomous machinery turns on. The intake classifier and a read-only Telegram scaffold give the operator situational awareness next, then the synthesis loop core wires up the generation engine. Validation sentinels land before the gated-publish transaction, because flags must exist to surface in the approval card. The autonomy boundary — atomic publish via `/map-approve` / `/map-reject` — closes the loop. Final phase ships the remaining write commands that put editorial framing (`live_tension`, manual entries, forced re-synth) back in human hands. Every phase preserves the spine: intake autonomous, publishing gated; append-only data; sentinels flag, never block; all LLM calls through `llm-proxy:8200`; all `economy_map` access via direct PostgREST.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Render-Stack Diagnostic** - Audit how `aiagentspulse.com` is served and how new pages reach production; no code changes
- [ ] **Phase 2: `economy_map` Schema + Seven-Block Seed** - Isolated schema with append-only timeline and version tables, seven blocks seeded
- [ ] **Phase 3: Design Tokens** - Tier accent CSS variables, maturity pill component, fixed timeline entry format
- [ ] **Phase 4: Hub, Block, and Status Renderer** - Six-part block pages, hub with seven-block visual, status page, live-on-insert re-render
- [ ] **Phase 5: Intake Classifier + `unsorted` Handling** - Newsletter pipeline emits classified, traceable timeline entries via LLM proxy
- [ ] **Phase 6: Telegram Read-Only Scaffolding** - `/map-status` and `/map-pending` give operator situational awareness
- [ ] **Phase 7: Synthesis Loop Core** - Trigger evaluation, input assembly, Sonnet generation with hot-reloadable identity, draft writes
- [ ] **Phase 8: Validation Sentinels** - Tension/length/maturity/structure flags annotate drafts without blocking; visible on Telegram cards
- [ ] **Phase 9: Gated Publishing + Approval Commands** - Atomic publish transaction wired to `/map-approve` and `/map-reject`
- [ ] **Phase 10: Operator Write Commands** - `/map-assign`, `/map-entry`, `/map-synth`, `/map-tension` complete the control surface

## Phase Details

### Phase 1: Render-Stack Diagnostic
**Goal**: Operator knows exactly how `aiagentspulse.com` is served and how new pages reach production before any renderer code is written
**Depends on**: Nothing (first phase)
**Requirements**: DIAG-01, DIAG-02, DIAG-03, DIAG-04
**Success Criteria** (what must be TRUE):
  1. Findings report names the service/container/framework responsible for serving `aiagentspulse.com` and pinpoints the HTML emission point
  2. The current publish mechanism for a new edition page is documented end-to-end (file write path, cache invalidation if any, deploy trigger)
  3. A clear recommendation exists on whether block pages reuse the existing publish path (preferred) or require a sibling route, with rationale
  4. Section 6 of the build spec is filled with the findings before any renderer work begins
  5. Zero application code changes were made during this phase (diagnostic-only confirmed)
**Plans**: 1 plan
Plans:
- [ ] 01-01-PLAN.md — Render-Stack Findings (describe-only diagnostic): produce `01-FINDINGS.md` + by-reference annotation to build spec §6
**UI hint**: yes

### Phase 2: `economy_map` Schema + Seven-Block Seed
**Goal**: An isolated, append-only Supabase schema exists with seven seeded blocks and an atomic publish transaction, accessible via direct PostgREST
**Depends on**: Phase 1
**Requirements**: SCHM-01, SCHM-02, SCHM-03, SCHM-04, SCHM-05, SCHM-06, SCHM-07, SCHM-08
**Success Criteria** (what must be TRUE):
  1. `economy_map` schema exists in Supabase and responds to direct PostgREST queries with the `Accept-Profile: economy_map` header (mirroring the `eu_ai_act` pattern); supabase-py `.in_()` is not used anywhere in the new code
  2. Seven blocks are queryable: three Substrate (identity-trust, memory-context, payments-settlement), three Behavior (autonomy-control, governance-accountability, psychology-disposition), one Frame (regulation-legal); each carries `live_tension`, `subtitle`, `tier`, `accent`, `sort_order`; negotiation-coordination exists as a section inside payments-settlement, not its own block
  3. The atomic publish transaction (Postgres function) flips a `block_body_versions` row to `published`, supersedes the prior published row, and updates `blocks.current_body_version_id` and `blocks.maturity` in a single transaction — verifiable by manual SQL exercise
  4. `block_body_versions` and `timeline_entries` reject UPDATE attempts on their content columns (append-only enforced); `unsorted` is accepted as a valid `block_slug` for low-confidence timeline entries
  5. Maturity enum (`nascent` → `emerging` → `contested` → `consolidating` → `mature`) is the only accepted value for `blocks.maturity` and `block_body_versions.proposed_maturity`
**Plans**: TBD

### Phase 3: Design Tokens
**Goal**: A minimal token system encoding only the information-bearing visual elements (tier accent, maturity pill, timeline format) is shipped as shared CSS
**Depends on**: Phase 1
**Requirements**: TOKN-01, TOKN-02, TOKN-03, TOKN-04
**Success Criteria** (what must be TRUE):
  1. Four tier accent colors exist as CSS custom properties — `--accent-teal: #0F6E56` (substrate), `--accent-purple: #534AB7` (behavior), `--accent-coral: #993C1D` (psychology), `--accent-gray: #5F5E5A` (regulation/frame) — and render correctly in a standalone preview
  2. Maturity pill component renders five segments (nascent → emerging → contested → consolidating → mature) with left-to-right fill, tier-accented, from a single shared component (one source of truth for hub/block/status)
  3. Timeline entry format is pinned and rendered consistently: `<event_date> · <what_shifted>` on one line, `<why_it_mattered> [source ↗]` on the second line
  4. Body font, page width, spacing, and nav chrome inherit existing site / system defaults — no bespoke typography is introduced
**Plans**: TBD
**UI hint**: yes

### Phase 4: Hub, Block, and Status Renderer
**Goal**: The hub, block, and status pages render live `economy_map` data through the existing `aiagentspulse.com` publish path, with Evolution sections updating on every new timeline entry
**Depends on**: Phase 2, Phase 3
**Requirements**: RNDR-01, RNDR-02, RNDR-03, RNDR-04, RNDR-05, RNDR-06, RNDR-07
**Success Criteria** (what must be TRUE):
  1. Operator can visit the hub URL (`/map` or `/`) and see the storyline header, seven-block visual, and a tier-accented maturity pill per block linking to its block page
  2. Operator can visit any block page (`/map/<slug>`) and see the six-part skeleton: (1) What it is, (2) Why it's hard, (3) The live tension, (4) Where it stands today (synthesized body), (5) Evolution (timeline entries, newest-first), (6) Maturity indicator
  3. Operator can visit `/status` and see all seven blocks' maturity at a glance, reading the same source as the hub pills (verified by changing one block's maturity in DB and seeing both surfaces update consistently)
  4. Inserting a new `timeline_entries` row causes the affected block page's Evolution section to re-render without waiting for the next synthesis (verified by manual insert + page check)
  5. Block pages publish via the existing `aiagentspulse.com` path identified in Phase 1 (no sibling route was introduced unless Phase 1 required it)
**Plans**: TBD
**UI hint**: yes

### Phase 5: Intake Classifier + `unsorted` Handling
**Goal**: The newsletter pipeline autonomously emits classified, fully-traceable timeline entries; low-confidence entries land in `unsorted` rather than being dropped or guessed
**Depends on**: Phase 2
**Requirements**: INTK-01, INTK-02, INTK-03, INTK-04, INTK-05
**Success Criteria** (what must be TRUE):
  1. When a newsletter edition's tier-1 events/clusters are finalized, a timeline candidate is emitted per event (verifiable by watching `timeline_entries` grow within seconds of an edition completing)
  2. The classifier (DeepSeek V3) assigns a `block_slug` and a `tag_confidence` score to each event, with the LLM call routed through `http://llm-proxy:8200` (no direct DeepSeek SDK call); routing is verified by an llm-proxy log line per classification
  3. Events with `tag_confidence >= 0.6` write to the named block's timeline; events below the floor write to `unsorted` (verifiable on a deliberately-ambiguous test event)
  4. Every emitted entry carries `source_edition_id` populated with the originating newsletter edition's id, enabling traceback (verifiable by SQL join on `newsletter_editions`)
  5. Attempting to UPDATE a prior timeline entry row's content fails; corrections require new INSERTs (append-only enforced)
**Plans**: TBD

### Phase 6: Telegram Read-Only Scaffolding
**Goal**: Operator can see the state of the map and what's waiting for them, entirely via Telegram, before any write commands exist
**Depends on**: Phase 2, Phase 5
**Requirements**: CMD-01, CMD-02
**Success Criteria** (what must be TRUE):
  1. Operator runs `/map-status` and gets a single Telegram message listing all seven blocks with tier, maturity pill rendering, count of unabsorbed timeline entries, and count of pending drafts
  2. Operator runs `/map-pending` and gets a Telegram message listing every draft awaiting approval (with `version_id`) and every `unsorted` entry awaiting assignment (with `entry_id`)
  3. Both commands route through Gato → Gato Brain in the same pattern as the existing `/x-*` family (no parallel infrastructure)
  4. Neither command can mutate `economy_map` data (read-only verified by code review)
**Plans**: TBD

### Phase 7: Synthesis Loop Core
**Goal**: Per-block synthesis runs autonomously on threshold triggers, calls Claude Sonnet through llm-proxy with a hot-reloadable identity, and lands a new `block_body_versions` row as `draft`
**Depends on**: Phase 2, Phase 5
**Requirements**: SYNT-01, SYNT-02, SYNT-03, SYNT-04, SYNT-05, SYNT-06
**Success Criteria** (what must be TRUE):
  1. The trigger evaluator marks a block as eligible when `>= N=5` new timeline entries exist since `last_synthesized_at` OR `>= T=30 days` have passed with at least one new entry — verifiable by seeding test data and observing eligibility
  2. When eligible, the loop assembles the input from the current `published` body, all `timeline_entries` since `synthesized_from_through` ordered by `event_date`, the block's `live_tension`, and the current `maturity` — concrete entries are present in the prompt, never bare cluster labels
  3. Synthesis makes a single editorial LLM call to Claude Sonnet routed through `http://llm-proxy:8200`; direct Anthropic SDK calls are absent (verified by code review + a per-call llm-proxy log line)
  4. Editing `economy_map/synth_identity.md` on disk changes the next synthesis call's system prompt without a service restart (mtime-based hot reload verified by file touch + observed prompt change)
  5. Every successful synthesis writes one new `block_body_versions` row with status `draft`, a populated `body_md`, and a `proposed_maturity`; nothing about the live `published` row changes yet
**Plans**: TBD

### Phase 8: Validation Sentinels
**Goal**: Every synthesized draft is annotated with structured flags that surface loudly on the operator's Telegram card; flags never block draft creation
**Depends on**: Phase 7
**Requirements**: VLDT-01, VLDT-02, VLDT-03, VLDT-04, VLDT-05, VLDT-06
**Success Criteria** (what must be TRUE):
  1. The "tension preserved" sentinel writes `validator_report.tension_preserved=false` to the draft when the live-tension section is missing or trivialized post-synthesis (verifiable on a crafted regression test)
  2. The "length floor" sentinel writes `validator_report.length_below_floor=true` when the new body is shorter than 60% of the prior published length
  3. The "maturity jump guard" sets `requires_attention=true` on the draft when `proposed_maturity` differs from current `blocks.maturity` by more than one stop on the enum
  4. The "structure intact" sentinel writes `validator_report.structure_missing=[<heading_list>]` if any of the six skeleton headings is absent from the synthesized body
  5. A failing sentinel never aborts draft creation; the draft always lands with annotations, and `/map-pending` plus the per-draft Telegram card surface all raised flags visibly (silence is the enemy — verified by forcing each sentinel to fire and confirming the card shows it)
**Plans**: TBD

### Phase 9: Gated Publishing + Approval Commands
**Goal**: The autonomy boundary is closed — every body is `draft` until the operator runs `/map-approve`, which executes the atomic publish transaction; `/map-reject` supersedes a draft without mutating anything else
**Depends on**: Phase 2, Phase 7, Phase 8
**Requirements**: GATE-01, GATE-02, GATE-03, GATE-04, CMD-03, CMD-04
**Success Criteria** (what must be TRUE):
  1. Synthesis never writes a `published` row directly; every new body lands as `draft` and stays there until explicit operator action (verifiable by inspecting any synthesis run's DB writes)
  2. Operator runs `/map-approve <version_id>` and the atomic publish transaction (from Phase 2) flips that row to `published`, supersedes the prior published row, updates `blocks.current_body_version_id` and `blocks.maturity`, updates `last_synthesized_at`, and triggers a block-page re-render — all-or-nothing
  3. Operator runs `/map-reject <version_id>` and the row's status becomes `superseded`; the timeline entries it consumed remain unabsorbed (i.e., the next synthesis will see them again); no live page changes
  4. Rejected drafts are never deleted — `superseded` is terminal, the row remains queryable for audit (verifiable by SQL after a `/map-reject`)
  5. Both commands run only for the verified Telegram owner and return a confirmation message on success or a typed error on failure
**Plans**: TBD

### Phase 10: Operator Write Commands
**Goal**: The operator's editorial framing levers — manual entry, unsorted reassignment, forced re-synthesis, live-tension updates — are accessible from Telegram
**Depends on**: Phase 6, Phase 7, Phase 9
**Requirements**: CMD-05, CMD-06, CMD-07, CMD-08
**Success Criteria** (what must be TRUE):
  1. Operator runs `/map-assign <entry_id> <block_slug>` and an `unsorted` timeline entry is moved to the named block (implemented as a new entry referencing the prior, never an UPDATE) — visible in `/map-pending` immediately after
  2. Operator runs `/map-entry <block_slug> <text>` and a new timeline entry is created with `what_shifted` populated; the command prompts for or accepts inline `why_it_mattered` and lands the entry as append-only
  3. Operator runs `/map-synth <block_slug>` and the synthesis loop runs immediately for that block, ignoring `N` and `T` thresholds; a new `draft` row appears within the call timeout
  4. Operator runs `/map-tension <block_slug> <text>` and the block's `live_tension` field updates; the change is visible on the next render of the block page (editorial framing remains in human hands)
  5. All four commands route through the same Gato → Gato Brain pattern as `/map-approve` and require Telegram owner verification
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Render-Stack Diagnostic | 0/1 | Plans drafted | - |
| 2. `economy_map` Schema + Seven-Block Seed | 0/TBD | Not started | - |
| 3. Design Tokens | 0/TBD | Not started | - |
| 4. Hub, Block, and Status Renderer | 0/TBD | Not started | - |
| 5. Intake Classifier + `unsorted` Handling | 0/TBD | Not started | - |
| 6. Telegram Read-Only Scaffolding | 0/TBD | Not started | - |
| 7. Synthesis Loop Core | 0/TBD | Not started | - |
| 8. Validation Sentinels | 0/TBD | Not started | - |
| 9. Gated Publishing + Approval Commands | 0/TBD | Not started | - |
| 10. Operator Write Commands | 0/TBD | Not started | - |
