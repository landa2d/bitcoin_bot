---
created: 2026-07-04T09:00:00Z
updated: 2026-07-04T09:00:00Z
title: Grounding rewrite — one bounded removal-only iteration before a fabrication hold (auto-fix)
area: newsletter
priority: P3
phase_candidate: true
files:
  - docker/newsletter/newsletter_poller.py
  - docker/newsletter/judge_loop.py
  - docker/newsletter/deterministic_gate.py
---

## Problem

Layer-1 fabrication currently holds immediately — the writer never gets a chance to fix even
trivially-removable flags (delete 2 citations, drop a few name-drops). Under `enforce=true`
that's a missed edition for something a one-line deletion fixes. Operator raised this
2026-07-04; the design answer preserves the hard-stop as the TERMINAL state but allows one
automated attempt first.

## Design (operator-discussed 2026-07-04)

- On a fabrication verdict: ONE bounded rewrite with a REMOVAL-ONLY instruction — "delete or
  explicitly ground these itemized claims from the fact base; do NOT rephrase them" — feeding
  the exact flag list (entities/arXiv IDs/merge suspects).
- Re-run the FULL deterministic gate on the rewrite (machinery exists — Phase 29 D-02 already
  re-gates judge-loop rewrites). Clean → continue to the judge as normal. ANY fabrication
  remaining or newly introduced → hold exactly as today (fail-safe unchanged).
- Rationale guardrails (why fabrication normally skips rewrite — must survive this feature):
  flags are samples not an inventory; rewrites can INTRODUCE fabrication (observed live
  2026-07-03: a judge-loop rewrite added 4 fabrication flags); the hold remains the terminal
  state; a rewrite must never convert detected fabrication into undetected fabrication —
  hence removal-only phrasing + full re-gate.
- This CHANGES a locked milestone invariant ("fabrication → hold, never rewrite", operator-
  confirmed 2026-06-22) — needs explicit operator sign-off at implementation time, and should
  NOT ship mid-calibration (it changes the gate's semantics and muddies the data).

## Sizing signal

Build only if calibration shows fabrication holds are frequent AND mostly of the
trivially-removable kind. If the writer-grounding constraint (companion todo
2026-07-04-writer-grounding-constraint.md) makes holds rare, this may be unnecessary.
