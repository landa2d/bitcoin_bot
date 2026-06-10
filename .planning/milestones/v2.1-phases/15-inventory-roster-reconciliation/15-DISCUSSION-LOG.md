# Phase 15: Inventory & Roster Reconciliation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-08
**Phase:** 15-inventory-roster-reconciliation
**Areas discussed:** Maturity enum, regulation-legal + tiers, Negotiation block, Hub serve path

---

## Maturity enum (`building`)

| Option | Description | Selected |
|--------|-------------|----------|
| Remap building→emerging | Map `building`→`emerging` (stage-2 pill). No schema/frontend change; explicit operator-approved remap (not silent). 3 substrate pills read 'emerging'. | ✓ |
| Add `building` to the enum | ALTER TYPE + update app.js MATURITY_STAGE. Keeps the authored word verbatim; costs a migration + an app.js edit. | |
| Remap to a different value | Map to another existing value (nascent/contested/consolidating/mature). | |

**User's choice:** Remap `building` → `emerging`.
**Notes:** Live enum confirmed from migration 033 §3 = `nascent, emerging, contested, consolidating, mature`; app.js `MATURITY_STAGE` matches. `building` would be rejected by the enum on insert (fail-loud) and mis-render as stage 1. Remap applied at load time (Phase 16); satisfies INV-02 (surfaced, not silently remapped).

---

## regulation-legal + tier model

| Option | Description | Selected |
|--------|-------------|----------|
| Keep as deferred frame slot | Seeded row stays unpublished/body-less; renders as a DEFERRED card; 3 tiers preserved. Matches prior 'closing frame / EU AI Act feeds it later' decision. No write. | ✓ |
| Retire it — collapse to 2 tiers | Drop the frame tier to match the docs' substrate/behavior model; removes the regulation slot. | |

**User's choice:** Keep as a deferred frame slot (3 tiers retained).
**Notes:** Live seed (033) has `regulation-legal` (frame, sort_order 7). app.js hardcodes 3 tier sections, so "2 vs 3 tiers" reduces to keep/retire this single row. Kept; no content write. (A structural sort_order bump 7→8 follows from the negotiation reshuffle — see below.)

---

## Negotiation block

| Option | Description | Selected |
|--------|-------------|----------|
| First-publish as a new block | Add a new behavior block + load body; insert at order 5, shift governance→6, psychology→7. Graduates from 'section inside Payments'. | ✓ |
| Keep deferred | Don't publish the standalone block; the doc goes unused; map stays 7 blocks. | |

**User's choice:** First-publish `negotiation-coordination` as a new behavior block.
**Notes:** Absent from the live seed (v1.0 kept it inside Payments); ROST-01 explicitly reopens it. Order reshuffle creates a sort_order-7 collision with regulation-legal → bump regulation to 8 (structural UPDATE only; `blocks` is not append-only-trigger-guarded).

---

## Hub serve path

| Option | Description | Selected |
|--------|-------------|----------|
| DB row + markdown render | Minimal schema home for the hub body + render via the block `marked.parse` path; gated by the publish RPC. Heaviest, but full article renders and stays in the gated model. | ✓ |
| Replace the JS constant (app.js edit) | Swap `HUB_STORYLINE` for the doc intro. Light, but not DB-served, not RPC-gated, plain-text only (escapeHtml). | |
| Keep storyline; defer full hub body | Ship the existing one-line storyline + grid; the rich 00-hub.md article doesn't fully go live. | |

**User's choice:** DB-served + markdown-rendered, gated by the publish RPC.
**Notes:** Hub (`type: hub`, no tier) can't be a `blocks` row (tier CHECK NOT NULL); `#/map` currently renders the hardcoded `HUB_STORYLINE` constant. Post-decision finding that de-risks it: `marked.parse` is **already** the live block-body render path (app.js:586), so the render side is reuse, not net-new UI — only a minimal schema home for the hub body is net-new. Exact DDL delegated to the researcher. XSS-via-markdown posture (T-04-03-01, operator publish gate) carries over.

---

## Claude's Discretion

- Exact hub schema accommodation (relaxed tier CHECK + sentinel tier vs nullable tier vs dedicated hub home) — delegated to researcher/planner; D-04 fixes the path, not the DDL.
- Concrete sort_order renumbering mechanic (per the negotiation reshuffle) — planner's, provided it's collision-free and frame sorts after behavior.

## Deferred Ideas

- Phase 17 (HUB-01): hub cards vs prose links; how much hub prose above the grid; distinct visual treatment for `nascent` blocks beyond the pill.
- Evolution timeline content (intake fills weekly; bodies publish with possibly-empty timelines).
- EU AI Act tracker → `regulation-legal` body (future milestone; the deferred frame slot is the placeholder).
- 7 pending v1.0 backend todos — reviewed, none match this phase's domain; parked in the ROADMAP backlog.
