# The Agent Economy: living reference articles — build spec (v2)

A set of recurrently- and partially-autonomously-updated reference articles mapping
the agent economy into structural building blocks, tied together by one master
storyline, fed by the AgentPulse newsletter pipeline.

This document is a build handoff for Claude Code. It pins the **contracts** — schema,
loop steps, design tokens, commands — and deliberately leaves prompt wording and
implementation choices to Claude Code per the usual working pattern (intent over
over-specification). Where a section says "Claude Code decides," that is intentional.

---

## 0. The autonomy boundary (read first — it is the spine)

The system has exactly one rule that everything else serves:

> **Intake is autonomous. Publishing is gated.**
> Timeline entries are appended automatically with no human in the loop, because a
> mis-tagged dated entry is a cheap, visible, reversible error. Canonical body
> re-synthesis is generated automatically but published only on human approval,
> because a degraded body is an expensive, silent error — exactly the failure class
> that produced the 27-day wallet bug.

Every design decision below follows from this. Autonomy where errors are cheap and
visible; a gate where they are expensive and silent. The body is never overwritten
in place — re-synthesis produces a new *version* in `draft` status that goes live
only when approved.

---

## 1. Storyline & taxonomy (unchanged from v1 — summary)

**Storyline:** The agent economy is the project of building, for autonomous software,
the trust and coordination infrastructure humans took centuries to build — in years,
and without us in the loop. Editorial flag: **capability is solved; trust and
coordination are not.**

**Blocks (two tiers + optional frame):**

- Substrate (can an agent act at all?): `identity-trust`, `memory-context`,
  `payments-settlement`
- Behavior (what does it do once it can?): `autonomy-control`,
  `negotiation-coordination`, `governance-accountability`, `psychology-disposition`
- Optional frame: `regulation-legal` (ships as closing frame, not a peer; lightly
  populated until the EU AI Act tracker feeds it)

Per-block accent maps to tier: Substrate = teal, Behavior = purple, Psychology =
coral (deliberately distinct — it is the block that differentiates this map),
Regulation = neutral gray.

---

## 2. Phase 0 — validate the render stack (FIRST deliverable, diagnostic only)

The existing `aiagentspulse.com` render path is unknown and must be confirmed before
the renderer (section 6) is designed. This is a **diagnostic prompt**, no code
changes:

- Inspect how the live archive at `aiagentspulse.com` is served from the Hetzner box:
  static generated files vs. server-rendered, which container/service, which
  framework, where HTML is emitted, how a new edition page currently gets published.
- Report: the stack, the publish mechanism, where templates live, and whether the
  block pages can reuse that exact path (preferred) or need a sibling route.
- Do not build anything. Output is a short findings report that fills in section 6.

Everything downstream assumes block pages reuse the existing publish path. If Phase 0
finds that is impossible, revisit section 6 before proceeding.

---

## 3. Data contract

New isolated Supabase schema: `economy_map` (mirrors the `eu_ai_act` isolation
pattern; direct PostgREST calls use `Accept-Profile: economy_map`). Use direct
PostgREST HTTP, never supabase-py `.in_()` (known silent-failure bug).

### 3.1 `blocks`
One row per building block. Holds identity and current maturity; does NOT hold body
text (that is versioned separately).

| column | type | notes |
|---|---|---|
| `slug` | text PK | e.g. `payments-settlement` |
| `tier` | text | `substrate` \| `behavior` \| `frame` |
| `title` | text | display name |
| `subtitle` | text | one-line hub caption |
| `accent` | text | `teal` \| `purple` \| `coral` \| `gray` |
| `sort_order` | int | hub ordering |
| `live_tension` | text | the current unresolved-debate framing (editable) |
| `maturity` | text | enum, see 3.4 |
| `current_body_version_id` | uuid FK → `block_body_versions.id` | points at the live published body; nullable until first publish |
| `last_synthesized_at` | timestamptz | |
| `created_at` | timestamptz | |

### 3.2 `block_body_versions`
Append-only version history of the canonical body. Re-synthesis inserts; never updates
prior rows.

| column | type | notes |
|---|---|---|
| `id` | uuid PK | |
| `block_slug` | text FK → `blocks.slug` | |
| `body_md` | text | the synthesized canonical body, markdown |
| `status` | text | `draft` \| `published` \| `superseded` |
| `synthesized_from_through` | timestamptz | timeline entries up to this moment were absorbed |
| `proposed_maturity` | text | synthesizer's maturity call for this version |
| `validator_report` | jsonb | sentinel results (see 4.4) |
| `created_at` | timestamptz | |
| `published_at` | timestamptz | null until approved |

Publishing a version: set its `status=published`, set the prior published version to
`superseded`, update `blocks.current_body_version_id` and `blocks.maturity`. One
transaction.

### 3.3 `timeline_entries`
Append-only narrative ledger. This is the memory of each block. Never updated, never
deleted (corrections are new entries).

| column | type | notes |
|---|---|---|
| `id` | uuid PK | |
| `block_slug` | text FK → `blocks.slug` | may be `unsorted` (see 5.2) |
| `event_date` | date | when the thing happened (not when ingested) |
| `what_shifted` | text | the change, one or two sentences |
| `why_it_mattered` | text | one line |
| `source_url` | text | original source |
| `source_edition_id` | text | FK to the newsletter edition that produced it — always set for traceability |
| `tag_confidence` | numeric | 0–1, classifier confidence in `block_slug` |
| `created_at` | timestamptz | ingest time |

### 3.4 Maturity enum
Controlled vocabulary, measured as "how close to the human-infrastructure equivalent":
`nascent` → `emerging` → `contested` → `consolidating` → `mature`. Five stops; renders
as a five-segment pill on hub and block pages.

---

## 4. The synthesis loop (state machine — the autonomous core)

Per block, the loop that keeps the canonical body current. Steps are pinned; the
synthesis *prompt itself* is NOT pinned here — it lives in an identity file
(`economy_map/synth_identity.md`) hot-reloaded via mtime, so voice can iterate without
redeploys (same pattern as the other agents).

### 4.1 Trigger
A block becomes eligible for re-synthesis when **either**:
- it has accumulated ≥ `N` new `timeline_entries` since `last_synthesized_at`
  (default `N=5`, configurable per block), OR
- `≥ T` days have passed since `last_synthesized_at` with ≥ 1 new entry
  (default `T=30`).

Trigger evaluation runs on a schedule (Claude Code decides: cron vs. existing
orchestration poll). Manual override via `/map-synth <block>` (section 7).

### 4.2 Input assembly
The synthesizer receives, for the block:
- the current `published` body (`body_md`),
- ALL `timeline_entries` since the prior version's `synthesized_from_through`,
  ordered by `event_date`,
- the block's `live_tension`,
- the block's current `maturity`.

It does NOT receive cluster labels alone — it receives the concrete entries (the Fix 3
lesson: concrete inputs, not abstract labels, prevent recycled output).

### 4.3 Generation
Single editorial LLM call, Claude Sonnet (consistent with the strategic editor
choice; routed through the LLM proxy at `http://llm-proxy:8200` for budget governance
— do NOT call the Anthropic API directly, that was the RivalScope workaround we are
not repeating). Output: a rewritten `body_md` plus a `proposed_maturity`.

### 4.4 Validation (the sentinels — this is what makes autonomy safe)
Before a generated body is written even as a draft, a validator checks and records a
`validator_report`:
- **tension preserved**: the live-tension section still exists and is non-trivial
  (the body did not silently drop the unresolved debate).
- **length floor**: body is not shorter than `floor` (default 60% of prior published
  length) — guards against homogenization/collapse.
- **maturity jump guard**: if `proposed_maturity` differs from current by more than
  one stop, flag it `requires_attention=true` rather than accepting silently.
- **structure intact**: the six-part skeleton headings are all present (section 5.3).

A failed sentinel does NOT block creation of the draft — it annotates it. The draft is
still created (so you can see what happened) but the Telegram card surfaces the flags
loudly. **Silence is the enemy; a flagged draft is the goal.**

### 4.5 Proposal & gate
Valid or flagged, the result is written as a `draft` version and a Telegram card fires
(section 7) showing: block, proposed maturity (with delta), sentinel flags, and a diff
summary vs. the live body. Nothing goes live here.

### 4.6 Publish
On `/map-approve <version_id>`: the transaction in 3.2 runs, the page re-renders
(section 6), `last_synthesized_at` updates. On `/map-reject <version_id>`: status set
to `superseded`, no live change, the timeline entries remain unabsorbed and will be
re-included in the next synthesis.

---

## 5. Intake (fully autonomous)

### 5.1 Source
The newsletter pipeline, at the point where an edition's events/clusters are finalized,
emits timeline candidates. Each finalized tier-1 event is classified to a block.

### 5.2 Classification + confidence floor
A classifier (DeepSeek V3 is fine here — bulk classification, cost-efficient, routed
through the proxy) assigns each event a `block_slug` and a `tag_confidence`. The
sentinel for fully-auto intake:
- `tag_confidence ≥ floor` (default 0.6): write directly to that block's timeline.
- `tag_confidence < floor`: write with `block_slug='unsorted'`. The `unsorted` bucket
  surfaces in `/map-pending` for a one-tap reassignment — a low-confidence event is
  visible, never silently misfiled.

Every entry carries `source_edition_id`. An entry is append-only; a wrong tag is fixed
by adding a corrective entry or reassigning from `unsorted`, never by mutating history.

### 5.3 Per-block page skeleton (fixed order)
Both the synthesizer's output and the renderer assume this order:
1. What it is
2. Why it's hard
3. The live tension
4. Where it stands today (the synthesized body proper)
5. Evolution (rendered from `timeline_entries`, newest or oldest first — Claude Code
   decides default, but it must be the dated ledger, not a prose rewrite)
6. Maturity indicator

---

## 6. Renderer contract (shape confirmed in Phase 0)

> **Phase 1 findings (2026-05-26):** This section's "shape confirmed in Phase 0"
> clause is fulfilled by `.planning/phases/01-render-stack-diagnostic/01-FINDINGS.md`.
> Findings confirm: block pages reuse the existing publish path via new hash routes
> in `docker/web/site/app.js`; no sibling route is needed; the publish-path for
> block bodies is a DB write to `economy_map.block_body_versions` (same pattern as
> newsletter editions). See `01-FINDINGS.md` §3 for the recommendation and §4 for
> known unknowns deferred to Phase 2.

Given a block slug, assemble: `blocks` row + current published `body_md` + all
`timeline_entries` for the slug + maturity. Emit a page following the section-5.3
skeleton, reusing the existing site's publish path (per Phase 0 findings).

- **Hub page** (`/` or `/map`): the storyline header + the seven-block visual + each
  block's maturity pill, linking to block pages.
- **Block pages** (`/map/<slug>`): the full skeleton.
- **Status page** (`/status`): all blocks' maturity at a glance — same data as the hub
  pills, denser. The hub and status read the same maturity source.

Re-render is triggered by a publish (4.6) and by an intake that adds a timeline entry
(the Evolution section is live data, so a new entry shows immediately even before the
next body re-synthesis — this is how the page "talks about evolution" continuously,
not just at synthesis time).

---

## 7. Control surface (Telegram — the human gate)

Mirrors the existing X approval flow. Signatures:

- `/map-status` — all blocks, tier, maturity pill, count of unabsorbed timeline
  entries, count of pending drafts.
- `/map-pending` — drafts awaiting approval + `unsorted` timeline entries awaiting a
  block assignment.
- `/map-approve <version_id>` — publish a draft body version (runs 4.6).
- `/map-reject <version_id>` — supersede a draft, no live change.
- `/map-assign <entry_id> <block_slug>` — move an `unsorted` entry to a block.
- `/map-entry <block_slug> <text>` — manual timeline drop (for things the pipeline
  didn't catch); fills `what_shifted`, prompts for `why_it_mattered` or accepts inline.
- `/map-synth <block_slug>` — force re-synthesis now, ignoring the trigger thresholds.
- `/map-tension <block_slug> <text>` — update a block's `live_tension` (the one piece
  of editorial framing that should stay in human hands).

---

## 8. Design tokens (deliberately minimal for v1)

Substance over design for v1. Only the tokens that encode *information* are pinned;
everything else is system default and explicitly deferred to a v2 design pass. This is
a choice, not an omission.

Pin exactly three things:

### 8.1 Tier accent colors (information: maps block → tier, matches the hub)
```css
:root {
  --accent-teal:   #0F6E56; /* substrate */
  --accent-purple: #534AB7; /* behavior */
  --accent-coral:  #993C1D; /* psychology */
  --accent-gray:   #5F5E5A; /* regulation / frame */
}
```

### 8.2 Maturity pill (information: controlled vocabulary, five stops)
Five segments, left-to-right fill by stop: `nascent`(1) → `emerging`(2) →
`contested`(3) → `consolidating`(4) → `mature`(5). Filled segments use the block's tier
accent; empty segments use a neutral border. Same component on hub, block page, and
status page — one source of truth.

### 8.3 Timeline entry format (information: consistency is what makes evolution readable)
Each entry renders as:
```
<event_date> · <what_shifted>
            <why_it_mattered>   [source ↗]
```
Date is the anchor; `what_shifted` is the lede; `why_it_mattered` is the one-line
significance; source links out. Fixed across all blocks.

**Everything else** — body font, page width, spacing, nav chrome — inherits the
existing site / system default. No bespoke typography in v1. Defer to v2 once the
machine works.

---

## 9. Build order (suggested sequencing — risk/dependency ordered)

Following the usual pattern: schema first (manual in Supabase), then parallel
non-conflicting application work, then sequential dependent pieces.

1. **Phase 0 diagnostic** (section 2) — render-stack findings. Blocks section 6.
2. **Schema** (section 3) — create `economy_map`, all four objects, seed the seven
   blocks + their `live_tension` and `subtitle`. Manual in Supabase.
3. **Parallel round A** (independent):
   - Intake classifier + confidence floor + `unsorted` handling (section 5).
   - Renderer for hub + block + status, reading live data (section 6), with timeline
     rendering working off real seeded entries.
   - Telegram command scaffolding (section 7), read-only commands first
     (`/map-status`, `/map-pending`).
4. **Sequential** (depends on A):
   - Synthesis loop (section 4) — trigger, assembly, generation, validator, draft
     write. Depends on schema + proxy.
   - Approval commands (`/map-approve`, `/map-reject`) wired to the publish
     transaction. Depends on synthesis loop existing.
5. **Observe** each piece independently before layering the next (the
   sequence-fixes-by-risk principle). In particular, watch the first few auto-syntheses
   for homogenization before trusting the cadence.

---

## 10. Open decisions still on Diego

The four decisions below were originally listed as open. They were resolved during
project initialization (2026-05-26) — see `.planning/PROJECT.md` Key Decisions and
`.planning/REQUIREMENTS.md` Out of Scope for the locked outcomes.

- **Negotiation block**: ✓ Resolved — graduate it. Negotiation starts as a section
  inside Payments; promotes to its own block once real bid/ask behavior exists.
- **Regulation block at launch**: ✓ Resolved — ship as lightly-populated closing
  frame. EU AI Act tracker feeds it over time.
- **Synthesis thresholds**: ✓ Resolved — global defaults `N=5/T=30`. Per-block
  tuning deferred to v2 unless data forces it.
- **Evolution order**: ✓ Resolved — newest-first as the default render order.
