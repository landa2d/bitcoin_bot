# Phase 28: Layer 1 Deterministic Gate - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-30
**Phase:** 28-layer-1-deterministic-gate
**Areas discussed:** Network-failure semantics, Reuse vs. rebuild verify_draft, Phase 28 scope boundary, Mechanical checks (GATE-06/07)

---

## Network-failure semantics (GATE-02/03)

| Option | Description | Selected |
|--------|-------------|----------|
| Distinguish dead vs. unreachable | 404/410/GitHub-404 → fabrication; timeout/5xx/rate-limit → unverified (escalate, not fabrication); retry once on transient | ✓ |
| Literal GATE-03 — any failure flags | Any connection failure or 4xx/5xx → flag fabricated | |
| You decide | — | |

**User's choice:** Option 1, with refinements — distinguish definitive-dead (flag fabrication) from unreachable (record unverified, escalate, never fabrication); retry once on transient only, never retry a 404; and keep `unverified` a visible distinct state, **not folded into pass**.
**Notes:** Honors the milestone's "an error is not evidence." Overrides GATE-03's literal "5xx → flag" wording for the transient/unreachable case.

### Network batching (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Dedup + per-run cache | Unique repos/URLs checked once, reused; sequential | ✓ |
| Dedup + bounded concurrency | Same dedup, small async pool | |
| Check every occurrence inline | No dedup | |

**User's choice:** Dedup + per-run cache (sequential).

---

## Reuse vs. rebuild verify_draft (GATE-04/05)

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse verify_draft + add network layer | verify_draft() is the fabrication engine; add only network-liveness + GATE-08 adapter | ✓ |
| Reuse engine but harden entity-merge | Same, plus explicit single-source-verbatim check for GATE-05 | |
| Build a fresh standalone checker | Re-implement claim extraction from scratch | |

**User's choice:** Reuse verify_draft + add network layer.
**Notes:** Inherits the calibrated ~0-FP stop-list. GATE-05 single-source semantics + the block fact-base shape flagged as researcher items rather than re-asked (option 2's concern preserved as a research TODO, not dropped).

---

## Phase 28 scope boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Build-only, defer all wiring to Phase 30 | Standalone module + golden-draft tests; no poller wiring/persistence/rebuild | ✓ |
| Build + report-only wire now | Also invoke at save points + write deterministic edition_evals row (container rebuild) | |
| You decide | — | |

**User's choice:** Build-only, defer all wiring to Phase 30.
**Notes:** "Report-only this phase" = the gate is designed to only emit flags. Keeps Phase 28 worktree-safe; WIRE-01 invocation is explicitly Phase 30.

---

## Mechanical checks (GATE-06/07)

| Option | Description | Selected |
|--------|-------------|----------|
| Normalized-exact | lowercase + whitespace-collapse + strip trailing punctuation, then exact match vs. previous edition | ✓ |
| Fuzzy similarity threshold | similarity score (token-overlap / Levenshtein) | |
| You decide | — | |

**User's choice:** Normalized-exact.
**Notes:** Fits GATE-07's "verbatim" wording + the deterministic/no-tuning posture. GATE-06 leak strings + body-start marker derivation flagged as a researcher item.

---

## Claude's Discretion

- Internal flags-object shape (beyond matching migration 045's `deterministic_flags` JSONB); how `unverified` is represented distinctly from `fabricated`.
- Golden-draft test fixtures + mocked network responses (seed ed-36 MCP-auth, ed-34 GroupMemBench, fake arXiv, 404 repo, dead URL, transient-5xx→unverified, recycled closer, leaked mode label).
- Sequential network execution (concurrency pool deferred).

## Deferred Ideas

- Verdict actions / `enforce` flag / sequencer invocation / `edition_evals` persistence → Phase 30 (WIRE).
- LLM judge + rewrite loop → Phase 29 (JUDGE/LOOP).
- Fuzzy recycling detection — rejected this phase.
- Bounded-concurrency network checks — deferred.
