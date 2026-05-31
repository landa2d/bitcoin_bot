# Phase 7: Synthesis Loop Core - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-31
**Phase:** 7-synthesis-loop-core
**Areas discussed:** Loop placement, Trigger semantics, Input assembly, synth_identity.md

---

## Gray-area selection

All four selected: Loop placement, Trigger semantics, Input assembly, synth_identity.md.

---

## Loop placement

| Option | Description | Selected |
|--------|-------------|----------|
| Processor | Autonomous-spine home (scheduled jobs, intake, routed_llm_call, circuit breaker) | (resolved ✓) |
| Newsletter service | Owns Sonnet block_pipeline + /anthropic proxy path | |
| You decide | — | ✓ → Processor |

**User's choice:** You decide → resolved to **Processor**. Rationale: matches Phase-5 intake
precedent, one autonomous home, routed_llm_call routes Sonnet via proxy; newsletter block_pipeline is
edition-specific. Researcher to confirm routed_llm_call handles Sonnet, else port the /anthropic
client into the processor (placement unchanged).

---

## Trigger semantics

### Watermark column

| Option | Description | Selected |
|--------|-------------|----------|
| synthesized_from_through | Precise consumed-watermark, survives rejection | |
| last_synthesized_at only | Wall-clock of last publish; single column | ✓ |
| You decide | — | |

**User's choice:** last_synthesized_at only.
**Notes:** Because last_synthesized_at only advances on publish (Phase 9), added a **"no pending
draft" eligibility guard** (D-03) so the single-column choice can't pile up duplicate drafts; dovetails
with Phase 9 reject (re-eligible, re-feed entries).

### Recency column + cold-start

| Option | Description | Selected |
|--------|-------------|----------|
| event_date; cold-start at N or T | Editorial date | |
| created_at; cold-start at N or T | Ingestion time | |
| You decide | — | ✓ |

**User's choice:** You decide → resolved to **created_at for the recency comparison** (wall-clock
consistency with last_synthesized_at; event_date can be backdated), **event_date for in-prompt
ordering** (SYNT-03/RNDR-07). Cold-start (NULL): all entries count, eligible at ≥5 or ≥1 after 30d
since earliest entry.

---

## Input assembly

### Cold-start (no prior body)

| Option | Description | Selected |
|--------|-------------|----------|
| Entries + maturity, no body | Synthesize first body from entries even with placeholder tension | ✓ |
| Skip until tension set | Couple first synthesis to operator setting live_tension | |
| You decide | — | |

**User's choice:** Entries + maturity, no body. Produce 6-part skeleton body_md + proposed_maturity;
proceed against placeholder live_tension (loop synthesizes, operator frames).

### High-volume

| Option | Description | Selected |
|--------|-------------|----------|
| All since watermark, capped by tokens | Token-budget bound; log omitted (fail-loud) | (resolved ✓) |
| Hard cap per call | Fixed N most-recent | |
| You decide | — | ✓ → token-capped |

**User's choice:** You decide → resolved to **all since watermark, token-budget capped**,
most-recent-first when over budget, **log the omitted count** (never silent). Researcher sets the
exact budget / max_tokens / entry ceiling.

---

## synth_identity.md

Initial questions (ship-default vs placeholder; file vs DB) were paused for clarification — the user
asked for a plain-language explanation, then chose **Q1 = working default + hot-reload** and
**Q2 = database-backed**. Claude pushed back on Q2: database storage deviates from the LOCKED
requirement SYNT-05 (which mandates a FILE hot-reloaded by mtime) and adds a table + command better
suited to Phase 10. A confirmation question was re-asked.

| Option | Description | Selected |
|--------|-------------|----------|
| File (recommended) | Working-default file, mtime hot-reload (analyst pattern), fail-loud if missing; /map-identity editor deferred to Phase 10 | ✓ |
| Database-backed | economy_map table edited via Telegram now; amends SYNT-05 | |

**User's final choice:** **File** at `config/economy_map/synth_identity.md`, working default,
mounted into processor, mtime hot-reload, fail-loud skip if missing/empty. Phone-editing deferred to a
Phase-10 `/map-identity` command that writes to the same file.

---

## Claude's Discretion

- proposed_maturity output format (structured JSON vs tagged) — must validate against the enum,
  fail-loud on invalid (D-12).
- Schedule cadence / poll slot (SYNT-02 defers to executor).
- Exact token budget / output max_tokens / entry ceiling (D-09, researcher).
- routed_llm_call vs ported /anthropic client (D-01, researcher).
- Prompt template / skeleton wording (newsletter voice + RNDR-02 six-part skeleton).

## Deferred Ideas

- `/map-identity` voice editor → Phase 10.
- Sentinels / validator_report / flag card → Phase 8.
- /map-approve, /map-reject, atomic publish, last_synthesized_at advance, re-render → Phase 9.
- Per-block N/T tuning → v2.

*No scope creep surfaced. None of the 6 pending todos matched this phase; none folded.*
