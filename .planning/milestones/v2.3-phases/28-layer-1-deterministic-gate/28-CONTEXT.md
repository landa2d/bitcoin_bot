# Phase 28: Layer 1 Deterministic Gate - Context

**Gathered:** 2026-06-30
**Status:** Ready for planning

<domain>
## Phase Boundary

A **no-LLM** deterministic gate (GATE-01..08) that takes a generated draft + its source fact base (+ the previous published edition) and returns a structured **flags object** — fabrication checks (live GitHub repo+star, URL liveness, arXiv-ID / named-study vs. fact base, entity-merge) and mechanical-editorial checks (H1/title echo, reading-mode-label leak, recycled closer, duplicated stat). The gate **only produces flags — it never acts** ("report-only this phase").

**In scope:** the standalone gate module + functions + a golden-draft test suite (mocked network).
**Out of scope (→ Phase 30 WIRE):** invoking the gate from `newsletter_poller`, writing `edition_evals` rows, the `enforce` flag, acting on verdicts (status flips / Gato escalation), any newsletter-container rebuild. LLM judging is Phase 29.
</domain>

<decisions>
## Implementation Decisions

### Network-failure semantics (GATE-02, GATE-03)
- **D-01:** Three distinct deterministic outcomes per network check — do NOT collapse them:
  - **confirmed-fabricated** → HTTP **404 / 410** (and GitHub API **404** for a repo) → a fabrication flag.
  - **unverified** → timeout, connection-refused, **5xx**, GitHub **rate-limit / 403-quota** → a distinct, **visible** state recorded on the flags object; surfaces as `escalated`/error — **never** a fabrication flag and **never** folded into "pass."
  - **verified-ok** → 200 (and, for GitHub, star-count within the >20% band when the draft asserts a count).
  - This honors the milestone spine "an error is not evidence" and overrides GATE-03's literal "connection failure or 4xx/5xx → flag" wording (a transient 5xx / rate-limit is unverified, not fabricated).
- **D-02:** Retry **once** on a *transient* failure (timeout / 5xx / connection error) before settling on `unverified`. **Never** retry a definitive 404.
- **D-03:** Dedup + per-run cache: extract the unique set of owner/repo refs and URLs, check each **exactly once**, reuse the result for every occurrence. Checks run **sequentially** (no LLM, modest count per edition; bounds the GitHub rate budget). The GitHub token is read from env if present (5000/hr) else unauthenticated, per GATE-02.

### Fabrication-check reuse (GATE-04, GATE-05)
- **D-04:** **Reuse `verify_draft()` (`docker/newsletter/verification.py`) as the fabrication engine** — its tier-1 (named entity not in any source), tier-2 (stats), and existing arXiv-ID pattern cover GATE-04 (study/arXiv) and GATE-05 (entity-merge). This inherits the calibrated ~0-tier-1-FP stop-list (Edition-34-tuned). Phase 28 adds ONLY the new network-liveness layer (D-01..D-03) + a GATE-08 fact-base adapter on top. Do NOT rebuild claim extraction or duplicate the stop-list.

### Phase 28 scope boundary
- **D-05:** **Build-only.** Ship a standalone gate module — e.g. `run_deterministic_gate(draft, fact_base, prior_edition) -> flags` — whose returned flags object matches migration 045's `deterministic_flags` JSONB shape, plus a golden-draft test suite (mocked network). **No** `newsletter_poller` wiring, **no** `edition_evals` write, **no** container rebuild this phase — all invocation/persistence/`enforce`/verdict-action deferred to Phase 30 (WIRE-01..06). "Report-only this phase" = the gate is *designed* to only emit flags, calibrated against golden drafts before it ever touches the live path. Keeps Phase 28 worktree-safe.

### Mechanical checks (GATE-06, GATE-07)
- **D-06:** Recycled-closer / duplicated-stat detection uses **normalized-exact** matching against the **previous published edition**: lowercase + collapse whitespace + strip trailing punctuation, then exact-match the closer line and each numeric-stat token (number+unit). **No fuzzy similarity threshold** (it would introduce tuning this phase defers and risks FP on common editorial phrasing) — fits GATE-07's "verbatim" wording and the deterministic/no-LLM/no-tuning posture.

### Claude's Discretion
- Internal shape of the flags object beyond matching `deterministic_flags` JSONB (per-check sub-keys, how `unverified` is represented vs `fabricated`).
- The golden-draft test fixtures (seed at least: ed-36 invented "MCP authentication" study, ed-34 "GroupMemBench", a fake arXiv ID, a dead URL/404 repo, a transient-5xx→unverified case, a recycled closer, a leaked reading-mode label) with mocked network responses.
- Sequential network execution (chosen over a concurrency pool — revisit only if a real edition is link-heavy enough to matter; it isn't latency-critical).

### Reviewed Todos (not folded)
- `2026-05-28-analyst-predictions-title-expire-bug.md` — generic keyword match ("title"); unrelated to the deterministic gate.
- `2026-05-28-pay-endpoint-500-transfer-rpc-search-path.md` — agent→agent payments RPC; unrelated.
- `2026-05-28-phase05-review-followups-wr02-wr04-wr05.md` — intake-classifier follow-ups; unrelated.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The authoritative WHAT + thresholds
- `.planning/REQUIREMENTS.md` §GATE-01..08 — the gate requirements (lines 21-30), the locked thresholds (GitHub star-drift **>20%**, URL HEAD **5s**, token-via-env), the verdict taxonomy (`held_fabrication`/`passed`/`held_voice`/`escalated`, lines 88-95), and the "Out of Scope" boundary. Authoritative on shape/taxonomy.
- `docs/audit/specs/01_eval_harness.md` — the eval-harness design reference: `verify_draft()` reuse (cites `verification.py:483-719`), the two save points (single-pass `~:2226`, A/B insert `~:2327`), the **dual-fact-base wiring** (`newsletter_poller.py:1611-1659` and `:2270-2294`), and the "reads those reports rather than recomputing when present" guidance. Implementation reference (the milestone command + REQUIREMENTS override it on conflicts).

### Reusable engine + persistence shape
- `docker/newsletter/verification.py` — `verify_draft(prose, input_data)` (the fabrication engine to reuse — tier-1/tier-2/arXiv/link-coverage), `_extract_claims_from_prose`, `_build_block_list`, the arXiv-ID pattern (`~:108`).
- `docker/newsletter/newsletter_poller.py` — `run_quality_checks()` (`~:882`) + `validate_required_sections` / `validate_fabrication_signals` / `qualitative_review` (mechanical/structural reuse for GATE-06); the two generation save points + the dual-fact-base wiring (GATE-08).
- `supabase/migrations/045_edition_evals.sql` — the `deterministic_flags` JSONB column the gate's output object must be shaped to fit (written in Phase 30).

### Prior locked decisions (carry forward)
- `.planning/phases/27-eval-persistence-governed-agent/27-CONTEXT.md` — fail-loud / no-silent-zero, `.eq()`-only, the `edition_eval.py` persistence helper + governed agent (the Phase 30 write surface), "an error is not evidence."

### Researcher TODOs (flag, then verify against code — not operator decisions)
1. **GATE-05 single-source semantics:** confirm whether `verify_draft()` tier-1 checks "present in **any** source" vs. GATE-05's "present verbatim in a **single** source" (no cross-source attribute merge). If tier-1 is any-source, add a thin entity-merge refinement on top — do NOT rebuild the engine.
2. **Block fact-base shape (GATE-08):** confirm whether `verify_draft()` accepts the `blocks` (block_v1) fact base directly or needs an adapter; single-pass uses `input_data`. The gate must verify against the **correct** fact base per version.
3. **GATE-06 concrete strings:** derive from code the exact reading-mode-label leak strings (e.g. "IMPACT/STRATEGIC/TECHNICAL READING MODE") and confirm the canonical body-start marker `## Read This, Skip the Rest` + the edition-title/H1 format used for the echo check.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `verification.py::verify_draft()` — the calibrated fabrication engine (tier-1 = named entity not in any source; tier-2 = unsourced stats; arXiv-ID filtering; link coverage). The core of GATE-04/05; reuse, don't rebuild (D-04).
- `newsletter_poller.py::run_quality_checks()` + `validate_*` — mechanical/structural checks reusable for GATE-06 (section/structure validation, fabrication-signal scan).
- Phase 26 `load_edition_context()` — returns recent published editions; candidate source for the "previous published edition" GATE-07 compares against (researcher to confirm it exposes the closer line / stats, or whether a fuller prior-edition fetch is needed — but the gate takes `prior_edition` as a param, so the *source* is a Phase-30 wiring concern).

### Established Patterns
- No-LLM determinism for Layer 1 (regex + network + fact-base matching); the calibrated stop-list must be preserved (FP-regression risk if duplicated).
- Dual fact base: `input_data` (single-pass) vs. `blocks` (block_v1) — GATE-08 demands the correct one per version.

### Integration Points
- None this phase (build-only, D-05). The gate function's signature + flags-object shape are the contract Phase 30 will wire at the two save points and persist via `edition_eval.write_eval_row(... layer='deterministic' ...)`.
</code_context>

<specifics>
## Specific Ideas

- The gate's purpose is to catch the historical worst offenders: invented "MCP authentication security study" (ed-36), "GroupMemBench" (ed-34), fake arXiv IDs, dead/404 GitHub repos — these are the must-pass golden-draft fixtures.
- `unverified` must remain a first-class, visible outcome — the operator explicitly does not want it silently treated as a pass.
</specifics>

<deferred>
## Deferred Ideas

- Acting on verdicts (status flips, `do_not_publish`, Gato escalation), the `enforce` report-only→armed flag, the sequencer invocation at the two save points, and `edition_evals` persistence of the deterministic layer → **Phase 30 (WIRE-01..06)**.
- The LLM judge + feedback-rewrite loop → **Phase 29 (JUDGE/LOOP)**.
- Fuzzy/similarity-based recycling detection — explicitly rejected for this phase (D-06); revisit only if normalized-exact proves too weak in calibration.
- Bounded-concurrency network checks — deferred; sequential is sufficient (D-03 discretion).
</deferred>

---

*Phase: 28-layer-1-deterministic-gate*
*Context gathered: 2026-06-30*
