# Phase 29: Layer 2 Judge + Feedback-Rewrite Loop - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-01
**Phase:** 29-layer-2-judge-feedback-rewrite-loop
**Areas discussed:** Rewrite re-verification, Pass thresholds & verdict, Rewrite mechanism, Module scope & output

---

## Rewrite re-verification (safety)

### How much of Layer 1 do we re-run on each rewrite?

| Option | Description | Selected |
|--------|-------------|----------|
| Full Layer 1 re-run | Complete deterministic gate on every rewrite; new fabrication → abort → held_fabrication; dedup cache means only new refs hit network | ✓ |
| Local-only re-check | Only offline checks (fact-base/arXiv/entity-merge); skip network GitHub/URL | |
| Judge-only re-eval | Trust the writer; only re-run the Sonnet judge | |

**User's choice:** Full Layer 1 re-run.

### Abort case — verdict + which draft stays on the row when a rewrite introduces fabrication?

| Option | Description | Selected |
|--------|-------------|----------|
| held_fabrication + keep clean attempt-0 | Loudest verdict; keep the last fabrication-clean draft; rejected attempt's flags → telemetry only | ✓ |
| held_voice + keep clean attempt-0 | Treat as a voice failure that couldn't be fixed; less alarming verdict | |
| held_fabrication + keep the fabricated draft | Maximally transparent but leaves a live fabrication one approve away | |

**User's choice:** held_fabrication + keep clean attempt-0.
**Notes:** Never leave a live fabrication one accidental approve away from publishing.

---

## Pass thresholds & verdict

### Adopt the proposed thresholds, or tune now?

| Option | Description | Selected |
|--------|-------------|----------|
| Adopt defaults as-is | REQUIREMENTS.md table verbatim as config defaults; calibrate in the P30 report-only window | ✓ |
| Tune now | Change one or more thresholds before writing config | |
| You decide | Claude picks from identity files + historical offenders | |

**User's choice:** Adopt defaults as-is.

### Continuity edges — no-prior-edition case + does a continuity fail rewrite or hold?

| Option | Description | Selected |
|--------|-------------|----------|
| n/a when no prior; fail → rewrite | Score n/a + exclude from verdict when no prior edition; hard-fail triggers the normal rewrite loop; held_voice only after N=2 | ✓ |
| n/a when no prior; fail → immediate held | Same n/a rule but continuity fail skips the loop straight to held_voice | |
| Hard-fail even when no prior | Keep score-1 hard fail regardless (would hold every empty-corpus edition) | |

**User's choice:** Option 1.
**Notes:** Hard-fail governs severity, not whether it gets a rewrite — keep those distinct. n/a handling consistent with P26 empty:true / P28 prior_edition=None.

---

## Rewrite mechanism

### How does the loop re-call the writer with feedback?

| Option | Description | Selected |
|--------|-------------|----------|
| Targeted revise call | Surgical "revise, fix exactly these issues" Sonnet call; grounded with fact base + anti-fabrication guardrail; writer-agnostic | ✓ |
| Full writer re-run | Re-invoke generate_newsletter / generate_from_blocks with feedback; regenerate from scratch | |
| Hybrid | Targeted revise for most dims; full re-run only for continuity | |

**User's choice:** Targeted revise call.

### Body granularity — how are the technical + impact bodies judged/rewritten?

| Option | Description | Selected |
|--------|-------------|----------|
| Score both, rewrite only the failing body | Judge both; rewrite only the body that failed | |
| Score both, rewrite both as a unit | Judge both; if either fails, rewrite both together to keep them in sync | ✓ |
| Technical body only | Judge + rewrite content_markdown only | |

**User's choice:** Score both, rewrite both as a unit.

---

## Module scope & output

### Who persists the per-attempt edition_evals rows?

| Option | Description | Selected |
|--------|-------------|----------|
| Pure module; Phase 30 persists | Module is a pure function returning verdict + telemetry; P30 sequencer persists all rows + acts. Mirrors P28's emit-only gate | ✓ |
| Module persists its own judge rows | Module takes a supabase client, writes layer='judge' rows internally (stub-tested); closes LOOP-03 in P29 | |

**User's choice:** Pure module; Phase 30 persists. (Confirms Phase 29 is build-only.)

### held_voice after N=2 — which attempt's draft is returned?

| Option | Description | Selected |
|--------|-------------|----------|
| Best-scoring attempt | Fewest failing dimensions (tie → highest sum → latest); verdict names selected attempt + still-failing dims | ✓ |
| Latest attempt (attempt 2) | Always return the final rewrite | |
| Original attempt 0 | Return the pre-loop draft; rewrites advisory-only | |

**User's choice:** Best-scoring attempt.
**Notes:** This is the choice that actually consumes the per-attempt scoring LOOP-03 produces — attempt 2 isn't guaranteed to beat attempt 1.

### Do mechanical-only Layer-1 flags trigger a rewrite?

| Option | Description | Selected |
|--------|-------------|----------|
| Surface as warn, no forced rewrite | No rewrite unless a judge dimension independently fails; else recorded + surfaced, verdict stays passed | ✓ |
| Trigger a rewrite | Any mechanical flag forces a rewrite even when the judge passes | |
| Hold as held_voice | Treat an unresolved mechanical flag as a hold | |

**User's choice:** Surface as warn, no forced rewrite.
**Notes:** Ride along as extra feedback if a judge dimension independently triggers the loop; otherwise recorded in deterministic_flags, verdict stays passed. **Condition:** confirm they're surfaced to the operator in the Phase 31 review path so "operator fixes at review" is actually true (captured as a Phase 31 dependency).

## Claude's Discretion

- Judge output/evidence schema shape (score + quoted evidence + before/after exemplar), subject to JUDGE-05's reject→retry→error contract.
- Module filename/location (keep edition_eval.py as the persistence helper).
- Deterministic filler-blacklist source + how its hit-count combines with the Sonnet hedging score.
- Judge temperature/max_tokens; one-call-vs-split judge (subject to D-08 + the cap).
- Internal shape of the returned attempts telemetry + verdict object.

## Deferred Ideas

- Phase 30 (WIRE): live invocation, all edition_evals persistence, verdict action, enforce flag, threshold calibration.
- Phase 31 (SURF) dependency: surface mechanical-only flags on a passed verdict in the review path.
- Full writer re-run as the rewrite mechanism (rejected D-07; revisit if targeted revise proves weak).
- warn/passed_with_warnings verdict state (not in the locked taxonomy; not added).
