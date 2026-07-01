# Phase 29: Layer 2 Judge + Feedback-Rewrite Loop - Research

**Researched:** 2026-07-01
**Domain:** Pure Python eval module (newsletter service) — LLM-judge scoring + bounded feedback-rewrite loop, unit-tested with mocked proxy client + fake httpx. Build-only (mirrors Phase 28).
**Confidence:** HIGH — every reused engine was read at source and its import + call contract was executed/confirmed in the actual test environment.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (D-01..D-12 — research THESE, no alternatives)

- **D-01 — Full Layer-1 re-run on EVERY rewrite** via `run_deterministic_gate(...)` before accepting a rewrite. The P28 per-run dedup cache should be carried across attempts (shared `http_client`) so only newly-introduced entities/URLs hit the network. Closes the "specificity pushes writer to invent a stat" hole.
- **D-02 — A rewrite that introduces a NEW fabrication flag → abort immediately.** Verdict `held_fabrication`. The edition KEEPS the last fabrication-CLEAN draft (attempt 0); the fabricated rewrite is NEVER kept. Rejected attempt's flags/scores go to telemetry only.
- **D-03 — `unverified` follows P28 D-01:** first-class visible "could not verify" (timeout/5xx/rate-limit/conn error, retry-once then settle). NEVER folded into fabrication; NEVER aborts the loop or holds. "An error is not evidence."
- **D-04 — Adopt REQUIREMENTS.md per-dimension thresholds + worst-triggered-wins mapping VERBATIM** as config defaults under `agentpulse-config.json → edition_eval`. Keys stay config-tunable. Report-only Phase-30 window is the designed calibration window.
- **D-05 — Continuity scored `n/a` and EXCLUDED from the verdict when there is no prior published edition** (loader `empty:true` / no `previous_editions`). Judge is told "no prior editions" so it doesn't fabricate a bridge.
- **D-06 — A continuity hard-fail (bridge absent → score 1) TRIGGERS the normal rewrite loop** ("add a lead sentence bridging to edition N-1's [theme]"); becomes `held_voice` only after N=2. Severity ≠ rewrite-eligibility.
- **D-07 — The loop re-calls the writer via a TARGETED revise call** (dedicated "revise this draft, fix exactly these issues, change nothing else" Sonnet call via `llm-proxy:8200` `/anthropic/v1/messages`, `claude-sonnet-4-6`, `edition_eval` identity). Input = current draft + per-dimension failure feedback + source fact base + "introduce NO entity/number not in these sources" guardrail. NOT a full writer re-run. Writer-agnostic (serves single_pass AND block_v1).
- **D-08 — The judge scores BOTH body versions** (technical `content_markdown` + impact `content_markdown_impact`); one judge call per `pipeline_version`. If EITHER body fails any dimension, the revise rewrites BOTH bodies together as a unit. Per-body scores retained in telemetry.
- **D-09 — Phase 29 is BUILD-ONLY (mirrors Phase 28).** Ship a standalone PURE module — `run_layer2(draft, fact_base, prior_context, det_flags, config, llm_client) -> {final_draft, verdict, attempts:[{attempt, judge_scores, feedback, reverify_flags, sats, model_calls}, ...]}` — plus a unit-test suite (mocked proxy client + fake httpx for the reused gate). NO supabase client, NO `edition_evals` write, NO live invocation, NO container rebuild.
- **D-10 — Persistence + action are Phase 30's.** The sequencer persists EVERY attempt row (`layer='judge'`) + acts on the verdict behind the `enforce` flag. Returned `attempts` telemetry MUST carry enough for Phase 30 to fill `write_eval_row(...)` per attempt.
- **D-11 — On `held_voice` after N=2:** return the attempt with the FEWEST failing dimensions (tie → highest summed per-dimension score → latest). Verdict records which attempt was selected + which dims it still fails; ALL attempts' scores stay in telemetry.
- **D-12 — Mechanical-only Layer-1 flags do NOT force a rewrite.** They ride as extra rewrite feedback ONLY when a judge dimension independently triggers the loop (LOOP-04's "may"). Otherwise recorded in `deterministic_flags` and the verdict stays `passed`. (Phase-31 dependency: surface mechanical-only flags even on `passed`.)

### Claude's Discretion (research options, recommend)
- Judge output/evidence schema shape (per-dimension: numeric score + quoted draft evidence + before/after exemplar), as long as JUDGE-05's contract holds (missing evidence/exemplars → schema-reject → one retry → `eval_status='error'`).
- Module filename/location (e.g. `docker/newsletter/judge_loop.py` or `layer2_judge.py`); keep `edition_eval.py` as the persistence helper (do not overload it).
- The deterministic filler-blacklist pre-pass source (identity-file blacklist) + how its hit-count combines with the Sonnet hedging score (`score <3` OR `≥3 hits`).
- Judge temperature / max_tokens; one judge call vs split calls (subject to D-08's both-bodies-per-`pipeline_version` + the cap).
- Internal shape of the returned `attempts` telemetry + verdict object (must carry enough for Phase 30).
- Sequential vs. minimal-concurrency network re-checks inside the reused gate (inherits P28 sequential default).

### Deferred Ideas (OUT OF SCOPE)
- **Phase 30 (WIRE):** invoke the gate + `run_layer2(...)` at the two save points; persist every attempt row + the initial deterministic row via `write_eval_row`; act on verdicts (held/`do_not_publish`/Gato escalation); the report-only→armed `enforce` flag; threshold calibration.
- **Phase 31 (SURF):** operator-facing surfacing/escalation. **Operator-flagged dependency (D-12):** the review path MUST surface mechanical-only flags even on a `passed` verdict.
- Full writer re-run as the rewrite mechanism — rejected (D-07 chose targeted revise).
- `warn`/`passed_with_warnings` verdict state — not in the locked taxonomy; not added.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| JUDGE-01 | Layer 2 runs only when Layer 1 found no fabrication | §Pattern 5 (fail-loud entry guard: `det_flags['fabrication'] == []` asserted; short-circuit is Phase 30's — the module refuses if mis-called) |
| JUDGE-02 | Sonnet judge (`claude-sonnet-4-6` via proxy) scores each version 1–5 per dimension, exemplar-anchored | §Pattern 2 (judge prompt/schema generalizing `phase_e_voice_check`); §Code Examples 1 |
| JUDGE-03 | Cross-edition continuity → score 1 if bridge absent; judge given last 3 editions' angles | §Pattern 2 (continuity dimension); §Pattern 6 (n/a exclusion, D-05); `prior_context` from `load_edition_context` |
| JUDGE-04 | Remaining dims (hedging, clickbait/professor-voice, repeated sub-topics, specificity) exemplar-anchored | §Pattern 2 (5-dimension schema); §Config Keys (filler-hit combination) |
| JUDGE-05 | Judge response missing evidence/exemplars → schema-reject → one retry → `eval_status='error'`; verdict from config-tunable thresholds | §Pattern 3 (schema validation + robust parse via `parse_llm_json`); §Pattern 7 (verdict computation) |
| LOOP-01 | On any dimension failing → re-call writer with structured specific feedback | §Pattern 4 (targeted revise, D-07); §Code Examples 2 |
| LOOP-02 | Rewrite re-evaluated; hard stop at N=2; no best-effort publish | §Pattern 5 (loop control); §Pattern 8 (D-11 best-attempt, not "latest") |
| LOOP-03 | Every attempt's scores + feedback logged to `edition_evals`; attempt-2-not-beating-1 surfaced | §Pattern 9 (telemetry shape maps to `write_eval_row`); write itself is Phase 30 (D-10) |
| LOOP-04 | Mechanical-only flags MAY enter the loop; fabrication flags NEVER | §Pattern 5 (D-12 feedback-only); §Pattern 7 (mechanical → `passed`) |
| LOOP-05 | Standalone module; sequencer passes draft + fact base; returns final draft + verdict; no retry state outside | §Pattern 1 (module signature); §Pattern 9 (return contract) |
</phase_requirements>

## Summary

Phase 29 builds `run_layer2(...)`, a **pure** function in `docker/newsletter/` that (1) runs a Sonnet judge over both body versions of a fabrication-clean draft, scoring five exemplar-anchored voice dimensions 1–5 with quoted evidence + before/after exemplars, (2) drives a bounded **N=2** feedback-rewrite loop through a **targeted revise call** (not a full writer re-run), (3) re-runs the Phase-28 deterministic gate on every rewrite and **aborts to `held_fabrication`** (keeping the clean attempt-0 draft) if a rewrite invents anything, and (4) returns a verdict + full per-attempt telemetry. It writes nothing, calls no live proxy, and rebuilds no container — first live invocation is Phase 30.

The heavy lifting is **reuse, not net-new**. Four already-built engines are imported verbatim and all confirmed importable in the actual test env: `deterministic_gate.run_deterministic_gate` (the Layer-1 re-check, D-01), `block_pipeline._llm_call` (the unified proxied Anthropic/OpenAI call for judge + revise), `newsletter_poller.parse_llm_json` (the robust JSON parser that fixes the Phase-26 char-0 fence-strip bug — do NOT reuse `phase_e_voice_check`'s brittle inline strip), and `deterministic_gate._fact_base_source_texts` (per-source fact text for the revise "use only these facts" guardrail). The judge itself is a generalization of `phase_e_voice_check` (exemplar-anchored, JSON-out, fail-loud "not scored") from one dimension to five, with a strict schema-validation gate enforcing JUDGE-05.

The single genuinely-new architectural decision is the **cross-attempt dedup cache** (D-01): `run_deterministic_gate` builds its dedup cache fresh per call, so a naive re-run refetches every URL. Two viable options are documented (§Open Question 1); the recommended one is a thin module-owned caching HTTP-client wrapper — safe because only `fabrication` (404/star-drift, never affected by the retry interaction) is consequential, while `unverified` never holds or aborts.

**Primary recommendation:** Ship `docker/newsletter/judge_loop.py` exposing `run_layer2(draft, fact_base, prior_context, det_flags, config, llm_client, *, http_client=None, github_token=None)`, importing the four engines above; add an `edition_eval` block to `agentpulse-config.json` with the thresholds verbatim from REQUIREMENTS.md; unit-test on the REAL module with a FIFO-queue fake `llm_client` (OpenAI-shape) + the Phase-28 `_FakeHTTPClient`, covering all 13 fixtures in §Validation Architecture.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Voice/editorial scoring (5 dims, both bodies) | Newsletter service (Python, pure fn) | LLM Proxy (Sonnet) | Judge is a taste call — needs Sonnet; runs where the fact base lives (invariant) |
| Targeted revise (fix exactly these issues) | Newsletter service (pure fn) | LLM Proxy (Sonnet) | Writer-agnostic revise; one call serves single_pass + block_v1 (D-07) |
| Per-rewrite fabrication re-check | Newsletter service (reused `run_deterministic_gate`) | GitHub API / URL HEAD (via injected `http_client`) | Safety re-run must use the SAME Layer-1 engine (D-01); network is SSRF-guarded already |
| Verdict computation (worst-triggered-wins) | Newsletter service (pure fn) | — | Deterministic mapping from thresholds; no LLM, no DB (D-05 emit posture) |
| Persistence of attempt rows + verdict action | **Phase 30 (sequencer)** — NOT this phase | Supabase | D-09/D-10: module is pure; sequencer is sole persistence + action owner |
| LLM budget governance (per-call spend) | LLM Proxy (`edition_eval` wallet) | — | GOV-01/02: judge + revise route through proxy under `edition_eval` identity, hard-capped |

## Standard Stack

This is a build-only phase in an existing service. **No new external packages.** The "stack" is the set of reused in-repo engines the module imports. All four were confirmed importable in the actual test env (`python3 -c 'import ...'` succeeded).

### Core (reused engines — import, do not rebuild)
| Symbol | File:line | Purpose | Why reuse |
|--------|-----------|---------|-----------|
| `run_deterministic_gate(draft, fact_base, prior_edition, *, http_client, github_token) -> {fabrication, unverified, mechanical, meta}` | `docker/newsletter/deterministic_gate.py:93` | Layer-1 re-check on every rewrite (D-01) | The exact engine that gates whether Layer 2 runs at all; re-running it on rewrites closes the fabrication-via-rewrite hole [VERIFIED: read at source + import OK] |
| `_llm_call(client, model, system, user, temperature=0.3, max_tokens=3000) -> str` | `docker/newsletter/block_pipeline.py:26` | Unified proxied Anthropic/OpenAI call for judge + revise | Auto-detects `anthropic.Anthropic` → `/anthropic` messages path; falls back to OpenAI-compatible (`.chat.completions`) for the mocked test client [VERIFIED: read at source] |
| `parse_llm_json(text, *, context) -> dict` | `docker/newsletter/newsletter_poller.py:777` | Robust JSON extraction (raw → fenced → first-balanced-object), FAILS LOUD | Fixes the Phase-26 char-0 fence-strip bug; the judge/revise MUST use this, not `phase_e_voice_check`'s brittle `startswith('```')` strip [VERIFIED: read at source + `nl.parse_llm_json` callable in test env] |
| `_fact_base_source_texts(fact_base) -> list[str]` | `docker/newsletter/deterministic_gate.py:245` | Per-source fact text for BOTH fact-base shapes | Feeds the revise "introduce NO entity/number not in these sources" guardrail (D-07) from the same accessor the gate uses [VERIFIED: read at source] |

### Supporting (reference patterns / identity)
| Symbol | File:line | Purpose | When to use |
|--------|-----------|---------|-------------|
| `phase_e_voice_check(draft, exemplars, llm_client, model)` | `docker/newsletter/block_pipeline.py:404` | The closest existing judge analog (exemplar-anchored, JSON-out, distinguishable `not_scored`) | Pattern source for the 5-dimension judge — generalize it; do NOT reuse its inline JSON strip (§Pitfall 1) |
| `_get_eval_api_key() -> str \| None` / `LLM_PROXY_EVAL_KEY` | `docker/newsletter/edition_eval.py:43` / `:40` | `edition_eval` governed proxy identity (GOV-01) | Phase 30 uses it to construct the injected `llm_client`; the module documents the requirement (§Pitfall 4) |
| `write_eval_row(supabase, *, newsletter_id, edition_number, pipeline_version, attempt, layer, eval_status, verdict, error, deterministic_flags, judge_scores, judge_feedback, sats_spent, model_calls)` | `docker/newsletter/edition_eval.py:66` | Phase-30 WRITE SURFACE | The module does NOT call it (D-09/D-10) — its telemetry must map 1:1 onto these params (§Pattern 9) |
| filler-phrase blacklist | `data/openclaw/agents/newsletter/agent/IDENTITY.md:13-18` | Deterministic filler pre-pass source | Seed `DEFAULT_FILLER_BLACKLIST` verbatim; override via `config.edition_eval.filler_blacklist` (§Config Keys) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Targeted revise (`_llm_call`) | Full writer re-run (`generate_newsletter`/`generate_from_blocks`) | Rejected by D-07 — writer-specific (2 code paths), higher fabrication risk, more expensive. Revisit only if revise proves too weak on continuity in calibration. |
| Reuse `parse_llm_json` | Copy a robust parser into the module | Violates the reuse rule (test_19/test_27) — a copy can pass while prod regresses. `parse_llm_json` is importable in the test env. |
| Own caching HTTP wrapper (D-01) | Re-run gate fresh each attempt (rebuild cache) | Simpler but refetches unchanged refs each rewrite (defeats D-01 "cheap for common case"). See §Open Question 1. |

**Installation:** none — no new dependencies. Test env confirms `httpx 0.28.1`, `pytest 9.0.3` present; `anthropic` is NOT installed in the test env (guarded to `None` in both `newsletter_poller.py:30-32` and `block_pipeline.py:18-21`), which is why the mocked `llm_client` must use the OpenAI-compatible shape (§Pitfall 2).

## Package Legitimacy Audit

**Not applicable — this phase installs zero external packages.** The module imports only stdlib (`json`, `re`, `logging`, `typing`) and four in-repo modules (all read at source this session). No `npm install` / `pip install` / registry fetch occurs. slopcheck N/A.

## Architecture Patterns

### System Architecture Diagram

```
                 Phase 30 sequencer (NOT this phase)
                          │  passes draft + fact_base + det_flags(clean) + prior_context + config + llm_client(edition_eval identity)
                          ▼
        ┌─────────────────────────────────────────────────────────────┐
        │  run_layer2(...)  [PURE — no DB, no live proxy, no rebuild]   │
        │                                                               │
        │  entry guard: assert det_flags['fabrication'] == []  ─────────┼─► ValueError (mis-wired; "an error is not evidence")
        │                                                               │
        │  attempt 0 = passed-in draft ──► JUDGE ─────────────┐         │
        │                                    │(judge JSON)    │         │
        │                          parse_llm_json + schema    │         │
        │                          ├─ invalid → 1 retry ──────┤         │
        │                          │            └─ invalid → eval_status='error' ─► verdict=escalated ─┐
        │                          ▼                          │         │                              │
        │              verdict computation (D-04/05/12)        │         │                              │
        │              ├─ no failing dims → verdict=passed ────┼─────────┼──────────────────────────────┤
        │              └─ some dim fails → build feedback      │         │                              │
        │                          │  (LOOP-04: + mechanical)  │         │                              ▼
        │                          ▼                           │         │                     return {final_draft,
        │   ┌──► REVISE both bodies (_llm_call, Sonnet) ────────┘         │                       verdict, attempts,
        │   │        │ (targeted; guardrail = _fact_base_source_texts)   │                       selected_attempt}
        │   │        ▼                                                    │
        │   │   RE-VERIFY: run_deterministic_gate(rewrite, fact_base,     │
        │   │              prior_edition, http_client, github_token)      │
        │   │        ├─ fabrication ≠ [] → verdict=held_fabrication ──────┼─► final_draft = attempt-0 (CLEAN); rewrite → telemetry only
        │   │        ├─ unverified/mechanical → telemetry only (D-03)     │
        │   │        └─ clean → JUDGE the rewrite ─────────────────┐      │
        │   │                                                      │      │
        │   └──────────────── loop while attempt < 2 ◄─────────────┘      │
        │        after N=2 still failing → verdict=held_voice,            │
        │        final_draft = BEST attempt (D-11: fewest fails →         │
        │        highest summed score → latest)                          │
        └─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities
| Function (recommended) | Responsibility | Reuses |
|------------------------|----------------|--------|
| `run_layer2(...)` | Orchestrator: entry guard, loop control, verdict, telemetry assembly | all below |
| `_judge_draft(draft, prior_context, exemplars, llm_client, config)` | ONE judge call scoring both bodies × 5 dims; parse + schema-validate + 1 retry (JUDGE-05) | `_llm_call`, `parse_llm_json` |
| `_validate_judge_response(parsed, *, continuity_applicable)` | Schema gate: both bodies × 5 dims, each with numeric score + evidence + before/after exemplar | — (net-new) |
| `_revise_draft(draft, feedback, fact_base, llm_client, config)` | Targeted both-body revise with source-facts guardrail (D-07/D-08) | `_llm_call`, `parse_llm_json`, `_fact_base_source_texts` |
| `_count_filler_hits(text, blacklist)` | Deterministic filler pre-pass (free string match) | — (net-new, seed from IDENTITY.md) |
| `_compute_failing_dims(judge_scores, filler_hits, config, *, continuity_applicable)` | Per-dimension threshold logic (D-04), both-bodies worst-case, continuity n/a exclusion (D-05) | — (net-new) |
| `_select_best_attempt(attempts)` | D-11 tie-break: fewest fails → highest summed score → latest | — (net-new) |

### Recommended Project Structure
```
docker/newsletter/
├── judge_loop.py        # NEW — run_layer2 + helpers (recommended name; layer2_judge.py acceptable)
tests/
└── test_29_judge_loop.py  # NEW — REAL module, FIFO fake llm_client + Phase-28 _FakeHTTPClient
config/
└── agentpulse-config.json # EDIT — add "edition_eval" block (thresholds verbatim; §Config Keys)
```

### Pattern 1: Module signature (LOOP-05, D-09)
**What:** One pure entry point; loop state never escapes it.
```python
# docker/newsletter/judge_loop.py
def run_layer2(
    draft: dict,            # {title, title_impact, content_markdown, content_markdown_impact, pipeline_version}
    fact_base: dict,        # the ALREADY-CORRECT base for this version (single_pass input_data OR {blocks:...})
    prior_context: dict,    # load_edition_context() output: {previous_editions:[...], exemplars:[...], empty:bool}
    det_flags: dict,        # attempt-0 run_deterministic_gate() result (MUST be fabrication-clean — asserted)
    config: dict,           # config['edition_eval'] thresholds/models (see §Config Keys)
    llm_client,             # edition_eval-identity Anthropic client (proxy) — Phase 30 injects; tests mock
    *,
    http_client=None,       # injected httpx.Client for the reused gate's re-check (fake in tests)
    github_token=None,      # forwarded to run_deterministic_gate
) -> dict:
    """Returns {final_draft, verdict, selected_attempt, attempts:[...]}. Pure: no DB, no live invocation."""
```
**Note:** `http_client`/`github_token` are ADDED to the D-09 signature sketch because D-01's re-check needs them (CONTEXT explicitly says "a fake httpx client where the module reuses `run_deterministic_gate`"). Both are keyword-only, defaulting to `None`, mirroring the gate's own seam.

### Pattern 2: The 5-dimension exemplar-anchored judge (JUDGE-02/03/04)
**What:** Generalize `phase_e_voice_check` from `{score, observations}` to a both-bodies × 5-dimension structured object; each dimension requires a numeric score + quoted draft evidence + before/after exemplar.
**Recommended judge output schema (Claude's discretion — this shape satisfies JUDGE-05):**
```json
{
  "technical": {
    "continuity":         {"score": 1, "evidence": "<quoted lead sentence>", "exemplar_before": "...", "exemplar_after": "..."},
    "hedging_filler":     {"score": 4, "evidence": "...", "exemplar_before": "...", "exemplar_after": "..."},
    "clickbait":          {"score": 3, "evidence": "...", "exemplar_before": "...", "exemplar_after": "..."},
    "repeated_subtopics": {"score": 5, "evidence": "...", "exemplar_before": "...", "exemplar_after": "..."},
    "specificity":        {"score": 2, "evidence": "...", "exemplar_before": "...", "exemplar_after": "..."}
  },
  "impact": { "...same five dimensions..." }
}
```
**Continuity n/a (D-05):** when `prior_context.get('empty')` or no `previous_editions`, the judge prompt states "NO prior published editions exist — score `continuity` as the string `\"n/a\"` and do not invent a bridge"; the schema accepts `"n/a"` for `continuity` ONLY, and `_compute_failing_dims` excludes it.
**Prompt anchoring:** inject the last 3 editions' angles (`prior_context.previous_editions[*].title/opening_excerpt/weeks_ago` — the shape `editorial_prepass_from_blocks` already consumes at `block_pipeline.py:517-525`) + the operator exemplars (`prior_context.exemplars`). Must-catch targets (from CONTEXT specifics): missing bridge, hedging filler, second-person clickbait/fear hooks vs concept-first professor voice, sub-topics repeated from last edition, vague/unfalsifiable specificity.
**When to use:** ONE call per `pipeline_version` scoring both bodies (D-08) — cheaper and keeps the audience pair coherent. Temperature low (recommend 0.2, matching `phase_e_voice_check`'s 0.2); `max_tokens` ~1500 (5 dims × 2 bodies × evidence+exemplars).

### Pattern 3: Robust parse + schema-reject → retry → error (JUDGE-05)
**What:** Parse with `parse_llm_json` (NOT the brittle inline strip), then structurally validate; one retry on invalid, then `eval_status='error'` → `escalated`.
```python
from newsletter_poller import parse_llm_json  # importable in test env (conftest preloads it; also imports standalone)

def _judge_draft(draft, prior_context, llm_client, config) -> dict:
    continuity_applicable = not (prior_context.get("empty") or not prior_context.get("previous_editions"))
    system, user = _build_judge_prompt(draft, prior_context, continuity_applicable, config)
    for attempt_i in (1, 2):  # 1 call + at most 1 retry (JUDGE-05)
        try:
            text = _llm_call(llm_client, config["judge_model"], system, user,
                             temperature=config["judge_temperature"], max_tokens=config["judge_max_tokens"])
            parsed = parse_llm_json(text, context="layer2_judge")   # FAILS LOUD, never silent-empty
            _validate_judge_response(parsed, continuity_applicable=continuity_applicable)  # raises on missing evidence/exemplar
            return {"status": "ok", "scores": parsed}
        except (json.JSONDecodeError, SchemaError, Exception) as e:
            last_err = e
            continue
    return {"status": "error", "error": f"judge schema-invalid after retry: {last_err}"}
```
**Anti-pattern:** reusing `phase_e_voice_check`'s `if text.startswith('```')` strip (`block_pipeline.py:428-432`) — that is the exact framing that produced Phase-26's char-0 failure. Use `parse_llm_json`.

### Pattern 4: Targeted revise (LOOP-01, D-07, D-08)
**What:** A dedicated "fix exactly these issues, change nothing else, invent nothing" both-body call — NOT a writer re-run.
```python
def _revise_draft(draft, feedback, fact_base, llm_client, config) -> dict:
    source_facts = _fact_base_source_texts(fact_base)   # reuse the gate's accessor (D-07 guardrail)
    system = ("You are revising a published-quality newsletter draft. Fix EXACTLY the issues listed. "
              "Change nothing else. You may ONLY use entities, numbers, and claims present in SOURCE FACTS. "
              "Introduce NO new entity or number. Return JSON {content_markdown, content_markdown_impact}.")
    user = _render_revise_prompt(draft, feedback, source_facts)   # both bodies + per-dim failures + before/after exemplars
    text = _llm_call(llm_client, config["revise_model"], system, user,
                     temperature=config["revise_temperature"], max_tokens=config["revise_max_tokens"])
    bodies = parse_llm_json(text, context="layer2_revise")
    return {**draft,
            "content_markdown": bodies["content_markdown"],
            "content_markdown_impact": bodies["content_markdown_impact"]}
```
**Both-bodies as a unit (D-08):** if EITHER body failed any dim, revise BOTH so audience renderings never drift. Titles (`title`/`title_impact`) are separate DB columns and stay unchanged (the continuity bridge lives in the lead of the body).

### Pattern 5: The N=2 loop + fail-loud entry guard (JUDGE-01, LOOP-02/04, D-02/D-06/D-12)
```python
# entry guard — the module is only ever called on a fabrication-clean draft (JUDGE-01 is Phase-30's short-circuit)
if det_flags.get("fabrication"):
    raise ValueError("run_layer2 called with a non-empty fabrication list — "
                     "Layer 1 must short-circuit before Layer 2 (mis-wired caller)")

attempts = []
current = draft
reverify = det_flags                      # attempt 0's flags are the passed-in gate result
for attempt_no in range(0, config["max_attempts"] + 1):   # 0,1,2 → judge up to 3 drafts, revise up to 2×
    if attempt_no > 0:
        current = _revise_draft(current, feedback, fact_base, llm_client, config)     # LOOP-01
        reverify = run_deterministic_gate(current, fact_base, prior_edition,          # D-01 re-check
                                          http_client=http_client, github_token=github_token)
        if reverify["fabrication"]:                                                   # D-02
            attempts.append(_attempt_row(attempt_no, judge=None, feedback=feedback,
                                         reverify=reverify, status="ok"))
            return _result(final_draft=draft, verdict="held_fabrication",             # KEEP attempt-0
                           selected_attempt=0, attempts=attempts)
        # unverified / mechanical on reverify → telemetry only (D-03) — never abort/hold
    judged = _judge_draft(current, prior_context, llm_client, config)                 # JUDGE-02
    if judged["status"] == "error":                                                   # JUDGE-05
        attempts.append(_attempt_row(attempt_no, judge=None, feedback=None,
                                     reverify=reverify, status="error", error=judged["error"]))
        return _result(final_draft=draft, verdict="escalated", selected_attempt=0, attempts=attempts)
    filler = {v: _count_filler_hits(current[body], config["filler_blacklist"]) for v, body in _BODIES}
    failing = _compute_failing_dims(judged["scores"], filler, config, continuity_applicable=...)
    attempts.append(_attempt_row(attempt_no, judge=judged["scores"], feedback=None,
                                 reverify=reverify, failing=failing, status="ok"))
    if not failing:
        return _result(final_draft=current, verdict="passed", selected_attempt=attempt_no, attempts=attempts)
    feedback = _build_feedback(judged["scores"], failing, det_flags["mechanical"])    # LOOP-04 / D-12
# N=2 exhausted, still failing (LOOP-02: no best-effort publish)
best = _select_best_attempt(attempts)                                                # D-11
return _result(final_draft=best["draft"], verdict="held_voice",
               selected_attempt=best["attempt"], attempts=attempts)
```
**D-12 (mechanical-only → passed):** mechanical flags are read ONLY into `_build_feedback` and ONLY when `failing` is non-empty; they never appear in the `failing` set and never move the verdict off `passed`.

### Pattern 6: Continuity n/a exclusion (D-05, JUDGE-03)
`continuity_applicable = not (prior_context.get('empty') or not prior_context.get('previous_editions'))`. When False: the judge is told no prior editions exist and scores continuity `"n/a"`; `_compute_failing_dims` skips continuity entirely (never a fail, never counted in D-11's summed score). Consistent with P26 `empty:true` and P28 `prior_edition=None`.

### Pattern 7: Verdict computation (D-04/D-05/D-11/D-12)
Worst-triggered-wins across the terminal states, computed as they are reached:
1. `held_fabrication` — a rewrite's `run_deterministic_gate` returns any `fabrication` (D-02). Terminal; keep attempt-0.
2. `escalated` — a judge call is schema-invalid after retry, or the proxy errors/402 (an error is not evidence; does NOT hold). Terminal.
3. `held_voice` — Layer 1 clean, N=2 exhausted, ≥1 dimension still fails on the best attempt (D-11). Terminal.
4. `passed` — all dims pass within N≤2; mechanical-only flags stay `passed` (D-12).
Per-dimension fail = a body's score `< fail_below` (or continuity n/a → excluded, or hedging `filler_hits ≥ filler_hits_max`); a dimension fails for the pipeline_version if EITHER body fails (D-08 → use `min(technical, impact)`).

### Pattern 8: D-11 best-attempt selection (LOOP-03 telemetry consumed)
```python
def _select_best_attempt(ok_attempts):   # only status='ok', non-fabricated, fully-judged attempts (0,1,2)
    return sorted(ok_attempts, key=lambda a: (
        len(a["failing"]),                 # fewest failing dims (primary)
        -a["summed_score"],                # highest summed per-dim score across both bodies (tie-break 1)
        -a["attempt"],                     # latest (tie-break 2)
    ))[0]
```
attempt-0 IS a candidate — attempt 2 is not guaranteed to beat it.

### Pattern 9: Attempt/verdict telemetry → `write_eval_row` mapping (D-10, LOOP-03)
Each attempt object carries exactly what Phase 30 feeds `write_eval_row(... layer='judge', attempt=k ...)`:
```python
attempt = {
    "attempt": k,                     # -> attempt
    "eval_status": "ok"|"error",      # -> eval_status
    "error": None|str,                # -> error (iff eval_status='error')
    "judge_scores": {...}|None,       # -> judge_scores  (both-bodies × 5 dims + evidence/exemplars)
    "feedback": str|None,             # -> judge_feedback (the structured revise feedback that produced the NEXT attempt)
    "reverify_flags": {fabrication,unverified,mechanical,meta}|None,  # -> deterministic_flags (attempt-0 = det_flags)
    "sats": int,                      # -> sats_spent (best-effort; proxy is authoritative — §Open Q2)
    "model_calls": [{"model","purpose","input_tokens","output_tokens","sats_est"}],  # -> model_calls
    # internal-only (not persisted): "failing", "summed_score", "draft"
}
```
Top-level: `{final_draft, verdict, selected_attempt, attempts:[...]}`. **Verdict-per-row (Phase-30 mapping, documented not implemented):** all `ok` judge rows for the edition carry the single top-level `verdict` (the `attempt` column disambiguates); an `error` attempt writes `eval_status='error'`, `verdict=NULL`, `error=...` — matching `write_eval_row`'s `verdict-iff-ok` guard (`edition_eval.py:121-134`).

### Anti-Patterns to Avoid
- **Reusing `phase_e_voice_check`'s JSON strip** — brittle; use `parse_llm_json` (§Pitfall 1).
- **Reusing the newsletter service's `claude_client`** — it authenticates as the `newsletter` agent (`newsletter_poller.py:294-296` uses `OPENAI_API_KEY`), wrong wallet. Judge/revise MUST use the `edition_eval` identity (§Pitfall 4).
- **Rebuilding the gate / claim extractor / stop-list** — import `run_deterministic_gate`; re-rolling regresses the Edition-34 ~0-FP calibration.
- **Folding `unverified` into a hold** — D-03: never aborts, never holds.
- **Making the module impure** — no supabase, no `write_eval_row`, no live proxy client construction inside `run_layer2` (Phase 30 owns those).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Layer-1 re-check on rewrites | A new fabrication checker | `deterministic_gate.run_deterministic_gate` | Same engine that gated entry; identical taxonomy (D-01) |
| Proxied Sonnet call (judge + revise) | A raw `httpx` POST to `/anthropic/v1/messages` | `block_pipeline._llm_call` | Handles Anthropic vs OpenAI-compatible clients; the mocked test client works via the OpenAI branch |
| LLM JSON parsing | `text.startswith('```')` strip | `newsletter_poller.parse_llm_json` | The Phase-26 char-0 bug; `parse_llm_json` tries raw→fence→balanced and fails loud |
| "Only these facts" guardrail for revise | New per-source extractor | `deterministic_gate._fact_base_source_texts` | Handles both fact-base shapes (blocks vs input_data) already |
| Filler detection | An LLM sub-call | `_count_filler_hits` string match on IDENTITY.md blacklist | Free, exact, unarguable; combines with the Sonnet hedging score per D-04 |
| Fake httpx for tests | `monkeypatch` of the real network | The Phase-28 `_FakeHTTPClient` (`tests/test_28_deterministic_gate.py:135`) | Proven FIFO/last-sticky double with `.calls` for retry/dedup asserts; zero egress |

**Key insight:** Almost everything this module "does" already exists in the newsletter service. The net-new surface is small: the judge prompt/schema, the revise prompt, `_compute_failing_dims`, `_select_best_attempt`, `_count_filler_hits`, and the loop orchestration. Every I/O boundary is a reused, already-tested engine.

## Common Pitfalls

### Pitfall 1: Copying `phase_e_voice_check`'s JSON strip
**What goes wrong:** Sonnet frames the judge JSON with a prose preamble; `startswith('```')` misses it; `json.loads` fails at char 0; the judge silently reads as "not scored" or crashes.
**Why it happens:** `phase_e_voice_check` (`block_pipeline.py:428-432`) predates the Phase-26 fix.
**How to avoid:** Use `parse_llm_json(text, context=...)` everywhere the judge/revise parse.
**Warning signs:** any `startswith('```')` or `.split('```')` in the new module.

### Pitfall 2: Mocking the judge with an `anthropic.Anthropic` instance
**What goes wrong:** `anthropic` is NOT installed in the test env, so you cannot construct that client; and `_llm_call` branches on `isinstance(client, anthropic.Anthropic)`.
**Why it happens:** production uses the Anthropic client; tests naïvely mirror it.
**How to avoid:** the mocked `llm_client` mimics the OpenAI-compatible shape (`client.chat.completions.create(...).choices[0].message.content`); with `anthropic=None` the `if anthropic and isinstance(...)` guard short-circuits to the OpenAI branch (`block_pipeline.py:33`), returning the canned text. [VERIFIED: `anthropic` import fails in test env; `block_pipeline` imports OK because it guards it]
**Warning signs:** `import anthropic` in the test file.

### Pitfall 3: The cross-attempt dedup cache does not persist for free
**What goes wrong:** `run_deterministic_gate` builds `cache = {}` fresh inside each call (`deterministic_gate.py:214`); re-running it on a rewrite refetches every URL/repo — the opposite of D-01's "cheap for the common case."
**Why it happens:** the gate's dedup is per-call by design (P28 was a single-shot gate).
**How to avoid:** wrap the injected `http_client` in a module-owned memoizing shim (recommended) so unchanged refs are served from cache across attempts; OR accept the refetch (bounded: ≤2 re-runs, sequential, 5s timeouts). See §Open Question 1 — this is the one genuinely-new design decision.
**Warning signs:** a rewrite test where `_FakeHTTPClient.calls` grows on every attempt for unchanged URLs.

### Pitfall 4: Judge/revise spend billed to the wrong wallet
**What goes wrong:** reusing `newsletter_poller.claude_client` bills the `newsletter` agent, not `edition_eval` — breaks GOV-01/02's hard-capped governance.
**Why it happens:** it's the obvious in-scope Claude client.
**How to avoid:** the injected `llm_client` must authenticate as `edition_eval`. Phase 30 constructs `anthropic.Anthropic(api_key=_get_eval_api_key(), base_url=f"{LLM_PROXY_URL}/anthropic")`. The pure module documents this requirement; it does NOT build the client itself (D-09).
**Warning signs:** any reference to `claude_client` or `OPENAI_API_KEY` in `judge_loop.py`.

### Pitfall 5: Off-by-one in N=2
**What goes wrong:** "N=2 attempts max" (LOOP-02) means at most 2 REWRITES → the judge scores up to 3 drafts (attempt 0 + 2 rewrites), and there are exactly 2 revise calls. Looping `range(3)` for revises would do 3 rewrites.
**How to avoid:** loop `attempt_no in range(0, max_attempts+1)`; revise only when `attempt_no > 0`; assert exactly ≤2 `_llm_call(purpose='revise')` in the "fails every attempt" test.

## Code Examples

### Example 1: Judge prompt skeleton (generalized from `phase_e_voice_check`)
```python
# Source pattern: docker/newsletter/block_pipeline.py:378-441 (PHASE_E_PROMPT + phase_e_voice_check)
JUDGE_SYSTEM = ("You are the editorial judge for AgentPulse. Score each draft version 1-5 on five "
                "voice dimensions. For EVERY dimension you MUST return a numeric score, a quoted "
                "sentence of EVIDENCE from the draft, and a before/after EXEMPLAR showing the fix. "
                "Respond ONLY with valid JSON.")
JUDGE_PROMPT = """PRIOR EDITIONS (verify the continuity bridge is real and accurate):
{prior_editions}          # empty -> "NO prior editions exist. Score continuity as \"n/a\"."
EXEMPLARS (target voice):
{exemplars}
TECHNICAL BODY:
{content_markdown}
IMPACT BODY:
{content_markdown_impact}
Dimensions: continuity (lead MUST bridge to a prior edition; absent -> 1), hedging_filler,
clickbait (professor voice = concept-first, defines terms, no 2nd-person fear hooks),
repeated_subtopics (vs last edition), specificity (named entities, dated numbers, falsifiable prediction).
Return JSON: {{"technical": {{<dim>: {{"score":N,"evidence":"...","exemplar_before":"...","exemplar_after":"..."}}}}, "impact": {{...}}}}"""
```

### Example 2: Filler-hit combination (D-04, JUDGE-04)
```python
# DEFAULT_FILLER_BLACKLIST seeded verbatim from data/openclaw/agents/newsletter/agent/IDENTITY.md:13-18
DEFAULT_FILLER_BLACKLIST = [
    "navigating without a map", "wake-up call", "smart businesses are already",
    "sifting through the narrative", "elevated urgency", "the landscape is shifting",
    "builders should leverage", "as we move forward", "the evidence suggests",
    "in today's rapidly evolving", "it remains to be seen", "only time will tell",
]
def _count_filler_hits(text, blacklist):
    low = text.lower()
    return sum(low.count(phrase.lower()) for phrase in blacklist)
# hedging fails if (min(tech,impact) hedging score < hedging_fail_below) OR (max filler hits >= filler_hits_max)
```

### Example 3: Fake `llm_client` for tests (OpenAI-shape, FIFO)
```python
# tests/test_29_judge_loop.py — the mocked proxy client (anthropic is None in test env → OpenAI branch)
class _Msg:            __slots__=("content",);  # .content
class _Choice:         # .message.content
    def __init__(self, text): self.message = type("M", (), {"content": text})()
class _Resp:
    def __init__(self, text): self.choices=[_Choice(text)]; self.usage=None
class _FakeLLM:
    def __init__(self, *responses): self._q=list(responses); self.calls=[]
    class _CC:
        def __init__(self, outer): self._o=outer
        def create(self, *, model, messages, temperature, max_tokens, **k):
            self._o.calls.append({"model":model,"messages":messages})
            return _Resp(self._o._q.pop(0) if len(self._o._q)>1 else self._o._q[0])
    @property
    def chat(self): return type("Chat",(),{"completions": _FakeLLM._CC(self)})()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `phase_e_voice_check` inline `startswith('```')` JSON strip | `parse_llm_json` (raw→fence→balanced, fail-loud) | Phase 26 (2026-06-24, commit bdb45ee) | The judge/revise MUST use the new parser; the old one caused char-0 empty-content failures |
| spec 01 verdict taxonomy `pass/warn/fail`, model `claude-sonnet-4-20250514`, one row per newsletter | REQUIREMENTS.md `passed/held_fabrication/held_voice/escalated`, `claude-sonnet-4-6`, per-attempt rows | v2.3 milestone (2026-06-22) | REQUIREMENTS.md OVERRIDES spec 01 on conflict; no `warn` state (D-12) |
| Layer-1 gate as single-shot | Re-runnable on rewrites (D-01) | Phase 29 | Cache-persistence gap surfaces (§Open Q1) |

**Deprecated/outdated:** spec 01's `warn` verdict, `edition_revisions` (REV-01 deferred), the spec-01 dimension set (regression-vs-baseline, structural compliance) — Phase 29's judge is the 5 voice dimensions in REQUIREMENTS.md, not spec 01's 5.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Continuity `fail_below` default = 4 (fail if score < 4: absent=1 and weak 2-3 both trigger a rewrite), matching REQUIREMENTS line-78 "fails below threshold" + "pass ≥4". A stricter reading is "only score==1 hard-fails." | §Config Keys / Pattern 7 | Over-/under-triggers continuity rewrites. Operator confirms at plan gate (D-04 explicitly invites this — report-only window calibrates it). LOW blast radius (config-tunable, report-only first). |
| A2 | On `escalated` (judge un-scoreable), `run_layer2` returns the **attempt-0** draft as `final_draft` (last fully-evaluated clean draft). CONTEXT does not pin which draft an escalated result returns. | §Pattern 5/7 | If the operator prefers "return best-scored-so-far," the returned draft differs. Escalated does NOT hold, so the human still reviews; LOW risk. |
| A3 | `sats` per attempt is best-effort ESTIMATED from `config` pricing × Anthropic `response.usage` tokens; the proxy's `wallet_transactions` settle is authoritative (proxy spend is batched, not returned per-call). | §Pattern 9 / Open Q2 | `sats_spent` telemetry may differ ±from actual settle. Phase 30 can reconcile. LOW — telemetry only, no gate depends on it. |
| A4 | The `edition_eval` config block is added to `agentpulse-config.json` in **Phase 29** (worktree-safe file edit; no rebuild). It could be argued into Phase 30. | §Config Keys | If planners defer it to Phase 30, the module still works via `DEFAULT_*` constants. LOW. |
| A5 | The module imports `parse_llm_json` from `newsletter_poller` at load; the test relies on it being importable (conftest preloads it AND it imports standalone — both verified). | §Pattern 3 | If a future refactor makes `newsletter_poller` un-importable in tests, test_29 breaks. Mitigated: guarded `anthropic` import already makes it work. LOW. |

**If this table were empty:** it is not — A1 (continuity threshold) is the one item the planner should route to the operator at the plan gate per D-04; the rest are low-risk defaults.

## Open Questions

1. **Cross-attempt dedup cache (D-01) — how to actually persist it?**
   - What we know: `run_deterministic_gate` builds `cache={}` per call (`deterministic_gate.py:214`); the gate takes NO cache param. So a naive re-run refetches all refs.
   - What's unclear: whether to (a) inject a memoizing `http_client` wrapper (module-owned; keys `(method,url)`→snapshot; served on repeat), or (b) accept the refetch (≤2 re-runs, sequential, 5s timeouts, targeted rewrites barely change ref sets).
   - Recommendation: **Option (a)**, a thin `_CachingHTTPClient` wrapping the injected client. It is SAFE for correctness: only `fabrication` outcomes (404 / >20% star-drift) are consequential, and those are stable under caching (404 is never retried; a 200 stays 200). The only interaction — caching a transient 5xx neuters the gate's within-run retry-once — affects `unverified` only, which never holds/aborts (D-03). A test asserts `_FakeHTTPClient.calls` does NOT grow for an unchanged URL across attempts. Fall back to (b) if the wrapper proves fiddly.

2. **Per-call `sats` for `model_calls`/`sats_spent`.** The proxy settles spend in `wallet_transactions` (batched), not returned per HTTP call. Recommendation: record `response.usage` tokens + a config-priced `sats_est`; treat the proxy settle as authoritative (A3). Phase 30 can reconcile against the wallet.

3. **`prior_edition` for the re-check vs `prior_context` for the judge.** `run_deterministic_gate(draft, fact_base, prior_edition, ...)` needs the FULL prior body (GATE-07), while the judge needs `prior_context` (angles/excerpts/exemplars from `load_edition_context`). These are TWO different prior inputs. Recommendation: `run_layer2` accepts `prior_context` (judge) and derives/receives `prior_edition` for the gate. Simplest: pass `prior_edition=None` to the re-check if Phase 30 hasn't fetched the full body — the gate skips GATE-07 cleanly (`deterministic_gate.py:809`), and GATE-07 is mechanical-only (never fabrication), so it cannot cause a `held_fabrication` false-abort. Confirm with the planner whether the re-check needs GATE-07 at all (recommend: no — pass `prior_edition=None` to the re-check; the fabrication signal is what matters for D-02).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pytest | unit tests | ✓ | 9.0.3 | — |
| httpx | fake-client typing / real gate | ✓ | 0.28.1 | — |
| `anthropic` SDK | production judge client (Phase 30) | ✗ in test env | — | guarded to `None`; tests use OpenAI-shape mock (by design) |
| `newsletter_poller` importable | `parse_llm_json` reuse | ✓ | — (guards anthropic) | conftest preloads it; also imports standalone |
| `deterministic_gate` / `block_pipeline` importable | engine reuse | ✓ | — | both import cleanly in test env |
| `LLM_PROXY_EVAL_KEY` in `config/.env` | GOV-01 identity (Phase 30 live) | ✓ | `ap_edition_eval_...` present | — |
| `edition_evals` table + `edition_eval` proxy agent registered | **Phase 30 live invocation only** | ✗ (Phase 27 Plan 03 — key-mint + MCP-apply — is STILL PENDING per STATE.md) | — | **Irrelevant to Phase 29** (build-only, mocked). BLOCKS the FIRST LIVE call in Phase 30 — flag to Phase 30 planning. |

**Missing dependencies with no fallback (for THIS phase):** none — every Phase-29 unit-test dependency is present.
**Missing dependencies with fallback:** `anthropic` (mock via OpenAI-shape — intended); the live proxy agent registration (Phase-30 concern, not Phase 29).

## Validation Architecture

> Nyquist enabled (no `workflow.nyquist_validation:false` found; `.planning/config.json` treated as enabled).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | none — no pytest.ini/pyproject/tox.ini/setup.cfg pytest config detected |
| Quick run command | `cd /root/bitcoin_bot && python3 -m pytest tests/test_29_judge_loop.py -x -q` |
| Full suite command | `cd /root/bitcoin_bot && python3 -m pytest tests/` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| JUDGE-01 | entry guard: non-empty `fabrication` in `det_flags` → ValueError; clean → judge runs, no revise on all-pass | unit | `pytest tests/test_29_judge_loop.py -k guard_and_shortcircuit` | ❌ Wave 0 |
| JUDGE-02 | judge scores both bodies × 5 dims 1–5 with evidence+exemplars (mocked JSON) | unit | `-k judge_scores_both_bodies` | ❌ Wave 0 |
| JUDGE-03 | continuity=1 when bridge absent triggers loop; judge given prior angles | unit | `-k continuity_absent_triggers` | ❌ Wave 0 |
| JUDGE-04 | hedging fails on score<3 OR ≥3 filler hits; specificity/clickbait <3 | unit | `-k filler_hit_combination` | ❌ Wave 0 |
| JUDGE-05 | schema-reject → 1 retry → recover (ok) AND stay-invalid → eval_status='error' → escalated | unit | `-k schema_reject_retry_then_error` | ❌ Wave 0 |
| LOOP-01 | failing dim → exactly one revise call with structured per-dim feedback | unit | `-k revise_called_with_feedback` | ❌ Wave 0 |
| LOOP-02 | fails every attempt → exactly 2 revises, hard stop at N=2, no 3rd revise | unit | `-k n2_hard_stop` | ❌ Wave 0 |
| LOOP-03 | every attempt's judge_scores+feedback present; attempt-2-not-beating-1 surfaced via selected_attempt | unit | `-k telemetry_all_attempts` | ❌ Wave 0 |
| LOOP-04 | mechanical-only + no failing dim → passed, no revise; mechanical rides feedback when a dim fails | unit | `-k mechanical_only_passed` / `-k mechanical_rides_feedback` | ❌ Wave 0 |
| LOOP-05 | pure return contract `{final_draft, verdict, selected_attempt, attempts}`; each attempt maps to write_eval_row params | unit | `-k return_contract_maps_to_write_eval_row` | ❌ Wave 0 |
| D-02 | rewrite introduces fabrication (fake httpx 404) → held_fabrication, final_draft==attempt-0 | unit | `-k held_fabrication_keeps_attempt0` | ❌ Wave 0 |
| D-03 | reverify unverified (fake httpx 5xx) → never aborts/holds; recorded in reverify_flags | unit | `-k unverified_never_holds` | ❌ Wave 0 |
| D-05 | prior_context.empty → continuity n/a excluded; no-bridge draft passes | unit | `-k continuity_na_excluded` | ❌ Wave 0 |
| D-08 | impact body fails, technical passes → dim counts as failing, both bodies revised | unit | `-k both_bodies_fail_together` | ❌ Wave 0 |
| D-11 | held_voice returns fewest-fails attempt; tie→highest summed score; tie→latest | unit | `-k best_attempt_selection` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_29_judge_loop.py -x -q`
- **Per wave merge:** `python3 -m pytest tests/test_29_judge_loop.py tests/test_28_deterministic_gate.py -q` (guards no regression against the reused gate)
- **Phase gate:** full `python3 -m pytest tests/` green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_29_judge_loop.py` — the entire suite (covers JUDGE-01..05, LOOP-01..05 + D-02/03/05/08/11). Import the REAL `judge_loop` via `sys.path.insert(NL_DIR)`; reuse the `_FakeHTTPClient` from `tests/test_28_deterministic_gate.py:135` and add the `_FakeLLM` FIFO client (§Code Examples 3).
- [ ] No new conftest fixture needed — conftest already preloads `newsletter_poller`; `deterministic_gate`/`block_pipeline` import standalone.
- Framework install: none — pytest present.

## Security Domain

> `security_enforcement` treated as enabled (no explicit `false`). The module consumes untrusted LLM-generated draft text and issues outbound requests through the reused gate.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Judge/revise outputs validated by `_validate_judge_response` + `parse_llm_json` (fail-loud, one retry, then error) — never trust raw LLM JSON |
| V6 Cryptography | no | No secrets handled in the module; `LLM_PROXY_EVAL_KEY` lives in the injected client (Phase 30), never in `judge_loop.py` |
| V10 Malicious Code / SSRF | yes (inherited) | The rewrite re-check reuses `run_deterministic_gate` whose `_is_safe_public_url` SSRF guard (`deterministic_gate.py:411`) already blocks internal hosts / private IPs / metadata endpoints — the module MUST NOT add its own network egress |
| V7 Error Handling / Logging | yes | Fail-loud: schema-invalid → `escalated` (not a fabricated 0); never log the eval key or raw draft prose at INFO |

### Known Threat Patterns for {LLM-judge + rewrite loop}
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Rewrite hallucinates a new entity/stat (specificity pressure) | Tampering | Full Layer-1 re-run on every rewrite → `held_fabrication`, keep clean attempt-0 (D-01/D-02) |
| Prompt-injection in draft prose triggers outbound fetch to internal host | Info disclosure / SSRF | Inherited `_is_safe_public_url` in the reused gate; module adds no raw egress |
| Judge returns a bare score with no evidence (unauditable) | Repudiation | `_validate_judge_response` rejects → retry → `escalated` (JUDGE-05) |
| Runaway rewrite loop burns budget | DoS | N=2 hard cap (LOOP-02) + `edition_eval` wallet `on_cap_behavior='reject'` (GOV-02); a 402 → `escalated`, never holds |
| Silent zero score masking a failed eval | Tampering | Fail-loud: `eval_status='error'` + reason, never a fabricated 0 (mirrors `phase_e_voice_check` `not_scored`) |

## Sources

### Primary (HIGH confidence — read at source this session)
- `docker/newsletter/deterministic_gate.py` — `run_deterministic_gate`:93, `_fact_base_source_texts`:245, per-call `cache`:214, `_is_safe_public_url`:411, GATE-07 skip:809
- `docker/newsletter/edition_eval.py` — `write_eval_row`:66, `_get_eval_api_key`:43, `LLM_PROXY_EVAL_KEY`:40, verdict-iff-ok:121-134, `_VERDICTS`:61
- `docker/newsletter/block_pipeline.py` — `_llm_call`:26 (anthropic-vs-OpenAI branch:33), `phase_e_voice_check`:404 + JSON strip:428-432, `PHASE_E_PROMPT`:378, prior-editions rendering:517-525, `generate_from_blocks`:572
- `docker/newsletter/newsletter_poller.py` — `parse_llm_json`:777, `_JSON_FENCE_RE`:732, `_first_balanced_object`:748, `MODEL`/`STRATEGIC_MODEL`:56-57, `claude_client` construction:294-296, anthropic guard:30-32
- `tests/test_28_deterministic_gate.py` — `_FakeHTTPClient`:135, `_stub_dns` autouse:44, import preamble:37-41, fixture builders:64-113
- `tests/conftest.py` — `_preload_poller("newsletter_poller.py")`:95
- `data/openclaw/agents/newsletter/agent/IDENTITY.md:12-18` — filler blacklist (verbatim)
- `.planning/REQUIREMENTS.md` — JUDGE-01..05, LOOP-01..05, thresholds table:80-95, verdict taxonomy:88-93, migration-045 DDL:99-137
- `.planning/phases/29.../29-CONTEXT.md` — D-01..D-12 (authoritative)
- `.planning/phases/28.../28-PATTERNS.md` — the test + reuse patterns to mirror
- `docs/audit/specs/01_eval_harness.md` — judge output contract, `synthesis_sonnet_call` pattern, filler pre-pass (REQUIREMENTS.md overrides on conflict)

### Verification runs (this session)
- `python3 -c 'import newsletter_poller; parse_llm_json callable' → OK`; `import deterministic_gate → OK`; `import block_pipeline → OK`; `import anthropic → ImportError` (guarded); `httpx 0.28.1`, `pytest 9.0.3`; `config.edition_eval → MISSING` (must be added); `LLM_PROXY_EVAL_KEY` present in `config/.env`.

### Secondary / carried decisions
- `.planning/phases/26.../27.../28...-CONTEXT.md` (carry-forward: empty:true, dedup cache, dual fact base, fail-loud, `.eq()`-only)
- `.planning/STATE.md` — Phase 27 Plan 03 (key-mint/MCP-apply) STILL PENDING → blocks Phase-30 live only

## Config Keys (question 8 — exact keys to add)

Add to `config/agentpulse-config.json` a top-level `edition_eval` block (currently ABSENT — verified). Module reads `config['edition_eval']`, merging over module `DEFAULT_*` constants so the pure function is robust to a partial config.
```jsonc
"edition_eval": {
  "enabled": false,          // Phase 30 invocation gate (rollback-safe)
  "enforce": false,          // Phase 30 report-only → armed (WIRE-06)
  "max_attempts": 2,         // LOOP-02 N=2
  "judge_model": "claude-sonnet-4-6",
  "judge_temperature": 0.2,
  "judge_max_tokens": 1500,
  "revise_model": "claude-sonnet-4-6",
  "revise_temperature": 0.3,
  "revise_max_tokens": 3000,
  "thresholds": {            // "fails below" per dim — VERBATIM intent from REQUIREMENTS.md:80-86
    "continuity_fail_below": 4,        // absent=1 & weak 2-3 trigger; pass ≥4  [A1 — operator confirms at plan gate]
    "hedging_fail_below": 3,           // score <3 → fail
    "hedging_filler_hits_max": 3,      // OR ≥3 filler-blacklist hits → fail
    "clickbait_fail_below": 3,         // <3 fail (3=warn, surfaced not triggered)
    "repeated_subtopics_fail_below": 3,
    "specificity_fail_below": 3,       // <3 fail (3=warn)
    "warn_below": 4                    // informational surface only; never triggers a rewrite/hold
  },
  "filler_blacklist": [ /* verbatim IDENTITY.md:13-18, or omit to use DEFAULT_FILLER_BLACKLIST */ ]
}
```
**Filler-hit combination (D-04):** the hedging dimension fails iff `min(technical_hedging, impact_hedging) < hedging_fail_below` **OR** `max(technical_filler_hits, impact_filler_hits) >= hedging_filler_hits_max`. The filler count is deterministic (free string match); the score is the Sonnet judgment — combined per D-04.

## Metadata

**Confidence breakdown:**
- Reused-engine contracts (signatures, return shapes, importability): HIGH — read at source + executed imports.
- Module architecture (loop, verdict, telemetry mapping): HIGH — derived directly from locked D-01..D-12 + `write_eval_row` params.
- Config threshold defaults: MEDIUM — thresholds are verbatim from REQUIREMENTS.md, but the continuity `fail_below` encoding (A1) is an operator-confirm at the plan gate (D-04 invites this).
- Cross-attempt dedup cache (D-01): MEDIUM — the gap is confirmed (per-call cache); the recommended wrapper is sound but is the one net-new design decision (Open Q1).

**Research date:** 2026-07-01
**Valid until:** ~2026-08-01 (stable — in-repo engines; only churn risk is a `newsletter_poller`/`deterministic_gate` refactor).
