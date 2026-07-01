# Phase 29: Layer 2 Judge + Feedback-Rewrite Loop - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning

<domain>
## Phase Boundary

A **standalone, pure Layer-2 eval module** in the newsletter service: a Sonnet judge that scores each draft version 1–5 across exemplar-anchored dimensions (cross-edition continuity bridge, hedging filler, clickbait/fear-hook vs. professor voice, repeated sub-topics, specificity) **plus** a bounded **N=2** feedback-rewrite loop. It runs **only when Layer 1 is fabrication-clean**, and returns the final draft + a verdict object with all per-attempt telemetry — never exposing loop internals or live retry state to the sequencer/Processor.

**In scope:** the standalone module (`run_layer2(...)`), the Sonnet judge prompt(s) + schema validation, the targeted revise call, the N=2 loop with per-rewrite Layer-1 re-verification, the verdict computation, and a unit-test suite (mocked proxy client; fake httpx for the reused gate).

**Out of scope (→ Phase 30 WIRE):** invoking the module from `newsletter_poller`, writing any `edition_evals` rows (deterministic **and** judge), acting on verdicts (status flips / `do_not_publish` / Gato escalation), the `enforce` flag, any newsletter-container rebuild. **Out of scope (→ Phase 31 SURF):** the operator-facing surfacing/escalation of verdicts and flags (with one operator-flagged dependency captured below).

**Build-only, like Phase 28:** the module is *designed and unit-tested* this phase; its first live invocation is Phase 30. This keeps Phase 29 worktree-safe (no migration, no key mint, no rebuild, no live DB write).
</domain>

<decisions>
## Implementation Decisions

### Rewrite re-verification — safety (Area 1)
- **D-01: Full Layer 1 re-run on EVERY rewrite** before accepting it into the next judge round. Reuse `run_deterministic_gate(...)` (Phase 28) on the rewritten draft. The **per-run dedup cache (P28 D-03) is carried across attempts** so unchanged owner/repo + URL refs reuse cached results — only *newly-introduced* entities/URLs actually hit the network (cheap for the common case). This closes the "the `specificity` dimension pushes the writer to add a named entity/number → invents a stat" hole, which is exactly when a rewrite would fabricate.
- **D-02: A rewrite that introduces a NEW fabrication flag → abort the loop immediately.** Verdict = **`held_fabrication`** (loudest signal; tells the operator "the rewrite hallucinated"). The edition row keeps the **last fabrication-CLEAN draft (attempt 0)** — **never** the fabricated rewrite. The rejected attempt's flags + scores go to the returned telemetry **only** (the operator can see what was invented, but a live fabrication is never left one accidental approve away from publishing — the operator's standing posture).
- **D-03: `unverified` on a rewrite ref follows P28 D-01** — a first-class, visible "could not verify" state (timeout / 5xx / rate-limit / connection error, retry-once then settle). It is **never** folded into fabrication and **never** aborts the loop or holds the draft; it surfaces as an escalated/error-adjacent signal. "An error is not evidence."

### Thresholds & verdict (Area 2)
- **D-04: Adopt the REQUIREMENTS.md proposed per-dimension thresholds + worst-triggered-wins verdict mapping VERBATIM** as the config defaults under `agentpulse-config.json → edition_eval`. Keys stay **config-tunable**. The **Phase-30 report-only window** (`enforce:false`, first ~2 editions) is the *designed* calibration window — tuning before any real judge output exists is guessing. (Defaults: continuity bridge absent → score 1 hard fail / present+accurate ≥4; hedging <3 **or** ≥3 filler-blacklist hits; clickbait/specificity <3 [3=warn]; repeated sub-topics <3.)
- **D-05: Continuity scored `n/a` and EXCLUDED from the verdict when there is no prior published edition** (loader returns `empty:true` / no `previous_editions`). Consistent with P26 `empty:true` and P28 `prior_edition=None`. Never hold an edition for a bridge that *cannot* exist (fail-loud, not fail-stupid). The judge is told "no prior editions" so it doesn't fabricate a bridge.
- **D-06: A continuity hard-fail (bridge absent → score 1) TRIGGERS the normal rewrite loop** with explicit `"add a lead sentence bridging to edition N-1's [theme]"` feedback; it only becomes `held_voice` after **N=2** failed attempts (consistent with LOOP-01 "any dimension failing → re-call the writer"). **Hard-fail governs SEVERITY (how bad), NOT rewrite-eligibility (whether it gets a rewrite) — the two are kept distinct** *(operator framing)*. Continuity is the most mechanical dimension to auto-fix (one bridge sentence), so it must get its rewrite chance.

### Rewrite mechanism (Area 3)
- **D-07: The loop re-calls the writer via a TARGETED revise call** — a dedicated `"revise this draft, fix exactly these issues, change nothing else"` Sonnet call (via `llm-proxy:8200` `/anthropic/v1/messages`, `claude-sonnet-4-6`, under the `edition_eval` identity). Input = current draft + per-dimension **failure feedback** (which dimensions, the judge's specific reason, the fix exemplar) + **the source fact base** + an explicit **"introduce NO entity/number not present in these sources"** guardrail. **NOT** a full writer re-run (`generate_newsletter` / `generate_from_blocks`). Rationale: writer-agnostic → **ONE** revise function serves both `single_pass` and `block_v1`; preserves verified facts (lowest fabrication risk, reinforcing D-01); cheaper; stays well within the 5000-sat/wk eval cap.
- **D-08: The judge scores BOTH body versions** (technical `content_markdown` + impact `content_markdown_impact`) — one judge call per `pipeline_version` returns per-dimension scores for both bodies (mirrors P28 running both bodies through the gate). **If EITHER body fails any dimension, the revise call rewrites BOTH bodies together as a unit**, to keep the two audience renderings coherent. Per-body scores are retained in the attempt telemetry.

### Module scope & output (Area 4)
- **D-09: Phase 29 is BUILD-ONLY (mirrors Phase 28).** Ship a standalone **PURE** module — signature-sketch `run_layer2(draft, fact_base, prior_context, det_flags, config, llm_client) -> {final_draft, verdict, attempts:[{attempt, judge_scores, feedback, reverify_flags, sats, model_calls}, ...]}` — plus a unit-test suite with a **mocked proxy client** (and a fake `httpx` client where the module reuses `run_deterministic_gate`). **NO** supabase client, **NO** `edition_evals` write, **NO** live invocation, **NO** container rebuild this phase.
- **D-10: Persistence + action are Phase 30's.** The `newsletter_poller` sequencer persists EVERY attempt row (`layer='judge'`) + the initial deterministic-layer row + acts on the returned verdict (status flip / escalation) behind the `enforce` flag. **BOTH eval layers are pure functions; the sequencer is the sole persistence + action owner.** LOOP-03's "logged to `edition_evals`" write completes in Phase 30 — the same posture as the GATE-* rows in Phase 28 (a deferred write, **not** a gap). The returned `attempts` telemetry must carry enough for Phase 30 to fill `write_eval_row(...)` per attempt.
- **D-11: On `held_voice` after N=2** (no fabrication, a voice dimension still fails), the module returns the attempt with the **FEWEST failing dimensions** (tie → **highest summed per-dimension score** → **latest**). The verdict records **which attempt was selected + which dimension(s) it still fails**; ALL attempts' scores remain in the returned telemetry. Rationale *(operator)*: this is the choice that actually *consumes* the per-attempt scoring LOOP-03 produces — attempt 2 is **not** guaranteed to beat attempt 1.
- **D-12: Mechanical-only Layer-1 flags do NOT force a rewrite.** (No fabrication; judge passes all dimensions.) They ride along as **extra rewrite feedback ONLY when a judge dimension *independently* triggers the loop** (LOOP-04's "may"). Otherwise they are recorded in `deterministic_flags` and the verdict stays **`passed`** (the locked taxonomy has no 'warn' state; mechanical is neither fabrication nor a failed voice dimension). **Operator condition:** these mechanical-only flags MUST be surfaced in the **Phase 31** review path *even on a `passed` verdict* — otherwise "operator fixes at review" is a false promise. Captured as a Phase 31 dependency (see Deferred).

### Claude's Discretion
- The judge output/evidence **schema shape** (per-dimension: numeric score + quoted draft evidence + before/after exemplar), as long as JUDGE-05's contract holds: a response missing the required quoted evidence / before-after exemplars is **schema-rejected → one retry → then `eval_status='error'`**.
- **Module filename/location** (e.g. `docker/newsletter/judge_loop.py` or `layer2_judge.py`); keep `edition_eval.py` as the persistence helper (do not overload it).
- The **deterministic filler-blacklist pre-pass** source (identity-file blacklist) + how its hit-count combines with the Sonnet hedging score per the D-04 threshold (`score <3` **OR** `≥3 hits`).
- Judge **temperature / max_tokens**; whether one judge call scores all dimensions or split calls — subject to D-08's both-bodies-per-`pipeline_version` intent + the cap.
- Internal shape of the returned `attempts` telemetry + verdict object, provided it carries enough for Phase 30 to persist per-attempt rows and act on the final verdict.
- Sequential vs. minimal-concurrency network re-checks inside the reused gate (inherits P28's sequential default).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The authoritative WHAT + thresholds + verdict taxonomy
- `.planning/REQUIREMENTS.md` §JUDGE-01..05 + §LOOP-01..05 (lines 32–46) — the locked requirements; the **"Proposed eval thresholds & verdict mapping"** table (lines 76–95, adopted verbatim per D-04); the verdict taxonomy `passed`/`held_fabrication`/`held_voice`/`escalated`; and the "Out of Scope" boundary (no auto-publish on pass, no rewriting fabrication, no LLM/retry-state in the Processor). **Authoritative on shape/taxonomy/thresholds.**
- `.planning/ROADMAP.md` §"Phase 29: Layer 2 Judge + Feedback-Rewrite Loop" (lines 183–197) — goal, depends-on (26/27/28), success criteria 1–5, and the standing milestone invariants (lines 85–92): fabrication = hard stop, passing ≠ auto-publish, both layers in the newsletter service, Processor stays a dumb sequencer, all LLM via proxy, fail-loud/no-`.in_()`.

### Implementation reference (pattern source — REQUIREMENTS.md overrides on conflict)
- `docs/audit/specs/01_eval_harness.md` — the eval-harness design reference: the Sonnet judge output contract ("score **plus two concrete before/after exemplars**; a score without quoted evidence is rejected — schema-validated, one retry, then `eval_status='error'`"), the `synthesis_sonnet_call` proxy pattern (`/anthropic/v1/messages`, httpx, status-checked), the deterministic filler-hit pre-pass idea, and the fail-loud rules (proxy-402-is-error, write-failure-is-loud). **Diverges (REQUIREMENTS.md wins):** verdict taxonomy, per-attempt rows, `claude-sonnet-4-6` (spec's model is EOL).

### Reused engines + the persistence write-surface (Phase 30 fills these; the module must fit their contracts)
- `docker/newsletter/deterministic_gate.py` — `run_deterministic_gate(draft, fact_base, prior_edition, *, http_client, github_token) -> {fabrication, unverified, mechanical, meta}` (`:93`). The Layer-1 engine the module re-runs on each rewrite (D-01); Layer 2 keys off `fabrication == []` to run at all, and reads `mechanical` for D-12. **`unverified` is first-class** (D-03).
- `docker/newsletter/edition_eval.py` — `write_eval_row(supabase, *, newsletter_id, edition_number, pipeline_version, attempt, layer, eval_status, verdict, error, deterministic_flags, judge_scores, judge_feedback, sats_spent, model_calls)` (`:66`) — the Phase-30 write surface. The module does **not** call it (D-09/D-10) but its returned `attempts` telemetry must map cleanly onto these params. Also `_get_eval_api_key()` (`:43`) — the `LLM_PROXY_EVAL_KEY` identity getter the judge/revise calls use (GOV-01).
- `docker/newsletter/block_pipeline.py` — `_llm_call(client, model, system, user, temperature, max_tokens)` (`:26`, unified Anthropic/OpenAI-compatible proxied call); **`phase_e_voice_check(draft, exemplars, llm_client, model)` (`:404`) — the closest existing judge analog** (exemplar-anchored, JSON-out, fail-loud "not_scored" — the pattern for the Sonnet judge). Writers: `generate_from_blocks(...)` (`:572`, block_v1).
- `docker/newsletter/newsletter_poller.py` — `generate_newsletter(task_type, input_data, budget_config)` (`:1158`, single-pass writer); `MODEL`/`STRATEGIC_MODEL` = `claude-sonnet-4-6` (`:56–57`); `routed_llm_call` (`:2051`). Two generation save points (Phase 30 wiring, not this phase).

### Prior locked decisions (carry forward — do not re-litigate)
- `.planning/phases/28-layer-1-deterministic-gate/28-CONTEXT.md` — the emit-only pure-gate posture (mirrored by D-09), the three network outcomes (D-01/D-03: confirmed-fabricated vs `unverified` vs verified-ok), the dedup cache (D-03), the dual-fact-base contract (`blocks` vs `input_data`).
- `.planning/phases/27-eval-persistence-governed-agent/27-CONTEXT.md` — the governed `edition_eval` agent (`LLM_PROXY_EVAL_KEY`, reject-on-cap **is safe**: 402 → `escalated`, never holds), the `write_eval_row` fail-loud contract, `.eq()`-only, "an error is not evidence."
- `.planning/phases/26-continuity-exemplar-context/26-CONTEXT.md` — `load_edition_context()` supplies the judge's `prior_context` (last 3 published editions' angles/excerpts + operator-approved exemplars; `empty:true` on zero corpus, driving D-05).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `deterministic_gate.py::run_deterministic_gate()` — reused verbatim for the per-rewrite Layer-1 re-check (D-01). Emit-only; the module interprets its flags. Inject the same `http_client` across attempts so the dedup cache persists.
- `block_pipeline.py::phase_e_voice_check()` — the template for the Sonnet judge: exemplar-anchored prompt, JSON output, distinguishable fail (`not_scored`) never a fake zero. The judge generalizes this to 5 dimensions + required before/after exemplars.
- `block_pipeline.py::_llm_call()` — the unified proxied LLM call helper; reuse for both judge and revise calls (Anthropic path → `/anthropic/v1/messages`).
- `edition_eval.py::write_eval_row()` + `_get_eval_api_key()` — the eval identity + write contract the module's telemetry must fit (write itself is Phase 30).
- `load_edition_context()` (Phase 26) — supplies `prior_context` (previous_editions angles + exemplars) to the judge; already injected into both writer paths.

### Established Patterns
- **All LLM via `llm-proxy:8200`** under the governed `edition_eval` identity (`LLM_PROXY_EVAL_KEY`); Sonnet `claude-sonnet-4-6` via `/anthropic/v1/messages`. No direct provider SDK.
- **Fail-loud / no silent zero:** a failed/uncertain eval is a distinguishable state (`not_scored` / `eval_status='error'` → `escalated`), never a fabricated 0. `.eq()` only, no `.in_()`.
- **Both bodies processed** (technical + impact) — every reuse (gate, judge, revise) handles the pair (D-08).
- **Dual fact base:** `input_data` (single_pass) vs `blocks`-dict (block_v1); the module trusts the handed `fact_base` (GATE-08 contract) and passes it to the gate re-check + the revise guardrail.

### Integration Points
- **None live this phase** (build-only, D-09). The `run_layer2(...)` signature + the returned `{final_draft, verdict, attempts:[...]}` shape are the contract Phase 30 wires at the two save points (after the fabrication-clean deterministic gate) and persists via `write_eval_row(... layer='judge', attempt=k ...)`.

</code_context>

<specifics>
## Specific Ideas

- **Safety-first on rewrites:** the operator explicitly wants the rewrite path hardened against introducing fabrication — hence full Layer-1 re-run on every rewrite (D-01) and keep-the-clean-draft on abort (D-02). A held draft must never carry a live fabrication one approve away from publishing.
- **Severity ≠ rewrite-eligibility** (operator framing, D-06): a hard-fail score (continuity=1) means "very bad," not "skip the rewrite." Every failing dimension gets its N=2 chance.
- **Consume the telemetry you build:** held_voice returns the *best* attempt, not the latest (D-11) — the per-attempt scoring exists to be used, not just logged.
- **Coherent audience pair:** rewrite both bodies as a unit (D-08) so technical + impact never drift.
- The judge's must-catch targets (from the identity voice rules + the historical offenders): missing cross-edition bridge, hedging filler, second-person clickbait/fear hooks (vs. concept-first professor voice), sub-topics repeated from last edition, and vague/unfalsifiable specificity.

</specifics>

<deferred>
## Deferred Ideas

- **Phase 30 (WIRE-01..06):** invoke the gate + `run_layer2(...)` at the two generation save points; persist every attempt row (`layer='judge'`) + the initial deterministic row via `write_eval_row`; act on verdicts (`held` / `do_not_publish` / Gato escalation); the report-only→armed `enforce` flag; threshold calibration against the first ~2 real editions. All of the module's *persistence and action* live here.
- **Phase 31 (SURF) — operator-flagged dependency (D-12):** the review path (Friday notify SURF-02 + `/newsletter_eval` SURF-03) MUST surface mechanical-only Layer-1 flags **even when the verdict is `passed`**, so the "operator fixes mechanical nits at review" promise is real. Today SURF-02/03 only promise verdict + per-dimension scores + voice exemplars; ensure passed-with-mechanical-flags is included. **Flag this to Phase 31 planning.**
- **Full writer re-run as the rewrite mechanism** — rejected for this phase (D-07 chose targeted revise); revisit only if targeted revise proves too weak on continuity in calibration.
- **`warn`/`passed_with_warnings` verdict state** — not in the locked taxonomy; not added. Mechanical nits ride in `deterministic_flags` on a `passed` verdict instead (D-12).

### Reviewed Todos (not folded)
All 7 pending todos were reviewed against Phase 29 scope; **none folded** — all are unrelated backend follow-ups:
- `2026-05-28-analyst-predictions-title-expire-bug.md` — analyst column bug; unrelated.
- `2026-05-28-harden-soft-caps-allow-negative.md` — soft-cap hardening for the *other* agents; `edition_eval` is `allow_negative=false` by design.
- `2026-05-28-pay-endpoint-500-transfer-rpc-search-path.md` — agent→agent payments RPC; unrelated.
- `2026-05-28-phase05-review-followups-wr02-wr04-wr05.md` — intake-classifier follow-ups; unrelated.
- `2026-05-28-research-trigger-file-permissions.md` — research file-queue perms; unrelated.
- `2026-05-30-phase06-review-followups-wr01-wr02.md` / `2026-06-01-phase07-review-followups-wr01-in01-04.md` — earlier-phase review follow-ups; unrelated.

</deferred>

---

*Phase: 29-layer-2-judge-feedback-rewrite-loop*
*Context gathered: 2026-07-01*
