# Requirements: AgentPulse — v2.3 Pre-Publish Evaluation Step

**Defined:** 2026-06-22
**Core Value:** Synthesis with editorial integrity — autonomous ingestion accelerates output, but every consequential publication is gated by human approval. Silence and homogenization are the failure modes to design against.
**System map:** `.planning/research/INVENTORY.md` · **Source spec:** operator milestone command (authoritative) + audit `docs/audit/specs/01_eval_harness.md` (R5) + `07_continuity_and_exemplars.md` (R4, implementation reference).

> **Spine for this milestone:** the eval runs *after generation, before publish*. A hard deterministic gate catches fabrication/mechanical errors (hold + escalate, **never** rewrite); an LLM-judge + bounded feedback-rewrite loop catches voice/editorial misses. **Passing the eval does NOT auto-publish — the Monday human gate is unchanged.** Both layers run in the **newsletter service** at the two generation save points (the only place the true fact base lives); the **Processor stays a dumb sequencer** with no LLM calls and no retry/rewrite state.

---

## v1 Requirements (this milestone)

### CTX — Continuity & Exemplar Context (audit R4 — Phase 1, dependency of the judge)

- [x] **CTX-01**: A `load_edition_context()` loader returns the last 3 published editions' `{edition_number, title, primary_theme, opening_excerpt, weeks_ago}` using plain `.eq('status','published')` (no `.in_()`).
- [x] **CTX-02**: The loader returns operator-approved exemplar paragraphs (≥40 words, non-header/list) from the most recent published editions, capped at `exemplar_paras`.
- [x] **CTX-03**: On zero published editions the loader returns an explicit `{previous_editions:[], exemplars:[], empty:true}` and logs a WARNING — never a bare `{}` indistinguishable from "not loaded"; generation still completes (fail-loud-but-not-fatal).
- [x] **CTX-04**: The continuity context + exemplars are injected so both writer paths (single-pass + block) and the eval judge receive them; an upstream-provided `narrative_context` still wins (`setdefault`).
- [x] **CTX-05**: The Phase E voice check produces a real score with ≥1 observation instead of the "skipped / No exemplars provided" sentinel (resurrected by the exemplar feed).

### GATE — Layer 1 Deterministic Gate (no LLM; runs on every edition, short-circuits)

- [x] **GATE-01**: The deterministic gate runs on every edition (both versions) before any LLM judge/rewrite and short-circuits to hold+escalate on any fabrication flag with **zero** LLM or rewrite attempts.
- [x] **GATE-02**: Every owner/repo and `github.com/owner/repo` reference is checked against the live GitHub API (token via env if present for 5000/hr, else unauthenticated): 404 → flag fabricated; 200 with a draft star-count differing >20% from `stargazers_count` → flag.
- [x] **GATE-03**: Every URL gets a HEAD request (5s timeout); connection failure or 4xx/5xx → flag.
- [x] **GATE-04**: Every named study/benchmark/paper title and arXiv ID asserted in the draft is cross-checked against the edition's source fact base; no matching ingested source → flag fabricated. (Targets the worst offenders: invented "MCP authentication security study", "GroupMemBench", fake arXiv IDs.)
- [x] **GATE-05**: Entity-merge — a named entity (e.g. owner/repo) not present verbatim in any single source is flagged; attributes from two sources must not be merged into one fabricated entity.
- [x] **GATE-06**: Mechanical — an H1/edition title echoed in the body is flagged (body must start at `## Read This, Skip the Rest`); reading-mode labels leaked into the body ("IMPACT / STRATEGIC READING MODE", etc.) are flagged.
- [x] **GATE-07**: Mechanical — recycled closer lines and numeric stats duplicated verbatim from the previous published edition are flagged.
- [x] **GATE-08**: The gate verifies against the **correct** fact base — `blocks` for block_v1, `input_data` for single-pass — read in-memory at the two generation save points (reusing the existing dual-fact-base wiring), never a reconstructed/wrong fact base.

### JUDGE — Layer 2 LLM Judge (Sonnet via proxy; only if Layer 1 found no fabrication)

- [x] **JUDGE-01**: Layer 2 runs only when Layer 1 found no fabrication (fabrication short-circuits before any LLM call, saving tokens).
- [x] **JUDGE-02**: A Sonnet judge (via `llm-proxy:8200`, editorial-synthesis model `claude-sonnet-4-6`) scores each draft version 1–5 per dimension, each anchored by a concrete before/after exemplar in the prompt (exemplars, not a bare rubric checklist).
- [x] **JUDGE-03**: Cross-edition continuity — the lead MUST contain an explicit bridge to a prior edition; score **1** if absent regardless of thematic connection; the judge is given the last 3 editions' angles to verify the bridge is real and accurate.
- [x] **JUDGE-04**: The remaining dimensions are scored with exemplar anchoring: hedging filler; clickbait/second-person fear hooks (strategic = professor voice: concept-first, defines terms on first use); repeated sub-topics from the previous edition; specificity (named entities, numbers tied to timelines, a falsifiable prediction where the format calls for it).
- [x] **JUDGE-05**: A judge response without the required quoted evidence / before-after exemplars is rejected (schema-validated, one retry, then `eval_status='error'`); a verdict is computed from per-dimension pass thresholds (config-tunable — proposed defaults below).

### LOOP — Layer 2 Feedback-Rewrite Loop (standalone module the sequencer calls)

- [x] **LOOP-01**: On any dimension failing threshold, the writer is re-called with the draft PLUS structured, specific feedback — which dimensions failed, the judge's specific reason, and the exemplar of the fix ("no bridge to edition N-1; add a lead sentence connecting to last week's permissions-bottleneck thread", not "improve continuity").
- [x] **LOOP-02**: The rewritten draft is re-evaluated; the loop terminates hard at **N=2 attempts max**; after 2 failed attempts it stops and does **not** publish best-effort.
- [x] **LOOP-03**: Every attempt's per-dimension scores + feedback are logged to `edition_evals`; if attempt 2 does not beat attempt 1, that signal (judge feedback too vague) is surfaced.
- [x] **LOOP-04**: Mechanical-only Layer-1 flags (no fabrication) may be passed into the rewrite loop as feedback; fabrication flags **never** enter the loop.
- [x] **LOOP-05**: The loop is a standalone eval-phase module; the sequencer passes in the draft + source fact base, the module runs the loop internally and returns the final draft + a verdict object — loop internals are never exposed to the Processor and no retry state lives outside the module.

### EVAL — Persistence & Telemetry (`edition_evals`, migration 045 — SQL-first)

- [x] **EVAL-01**: A new `edition_evals` table persists, per edition per attempt: newsletter/edition id + number, attempt number, timestamp, layer (`deterministic`/`judge`), deterministic flags (jsonb), per-dimension judge scores (jsonb), judge feedback (text), final verdict (`passed`/`held_fabrication`/`held_voice`/`escalated`). DDL applied by the operator via MCP after review (proposed DDL below).
- [x] **EVAL-02**: Fail-loud — an eval that errors writes `eval_status='error'` + reason, never a silent zero score; a proxy 402 (cap hit) is an error state, not a zero; the eval-row write failing is logged ERROR + Telegram-alerted, never swallowed. No bare excepts.
- [x] **EVAL-03**: All `edition_evals` reads/writes use plain supabase-py `.eq()` (no `.in_()`).

### GOV — Governed Eval Agent (budget via proxy)

- [x] **GOV-01**: A governed `edition_eval` agent routes all model calls through `llm-proxy:8200` (Sonnet via `/anthropic/v1/messages`, DeepSeek via `/v1/chat/completions`); no direct provider SDK calls.
- [x] **GOV-02**: The eval agent has its own `agent_registry` + `agent_wallets_v2` rows with `allow_negative=false`, a hard `spending_cap_sats` weekly window, `on_cap_behavior='reject'`, `uncapped=false` — it hard-stops on budget (a runaway eval loop has no editorial value). Key delivered via `.env` (`LLM_PROXY_EVAL_KEY`), never in compose.

### WIRE — Sequencer Wiring, Hold Action & Activation Gate

- [ ] **WIRE-01**: The eval is invoked from the `newsletter_poller` sequencer at the two generation save points (single-pass save return + block_v1 insert); an eval failure does not fail the generation task (wrapped: write the error row + continue).
- [ ] **WIRE-02**: Any fabrication flag → the newsletter row is set `status='held'` with `do_not_publish=true` and a detailed `do_not_publish_reason`; operator notified via Gato; the rewrite loop is **not** entered.
- [ ] **WIRE-03**: Layer-2 fail after N attempts → real `held` + Gato escalation with the final per-dimension scores + feedback (never a silent best-effort publish).
- [ ] **WIRE-04**: A `pass` verdict does **not** auto-publish — the edition proceeds to the unchanged human review gate (Monday review unchanged).
- [ ] **WIRE-05**: The Processor contains no LLM calls and no retry/rewrite state — it triggers generation, owns the publish gate, and surfaces eval verdicts via a plain select; the deterministic gate + eval module (both layers) live in the newsletter service where the fact base exists, called by the `newsletter_poller` sequencer.
- [ ] **WIRE-06**: Automated holds are gated by a config `enforce` flag (default `false` / report-only) so thresholds are calibrated against real drafts before any auto-hold fires; the operator explicitly flips `enforce:true`. The whole step is rollback-safe (`enabled:false` disables invocation; tables/agent rows may remain).

### SURF — Surfacing & Escalation (Gato)

- [ ] **SURF-01**: Hold/escalation notifications reuse `send_telegram` and are hardened so a held edition never silently fails to alert (assert/log when `TELEGRAM_BOT_TOKEN`/`TELEGRAM_OWNER_ID` are unset; loud on send failure, not a silent no-op).
- [ ] **SURF-02**: The Friday newsletter notify includes a compact per-draft eval summary (verdict + headline metrics) read from `edition_evals` via a plain select (no LLM in the Processor).
- [ ] **SURF-03**: A `/newsletter_eval` Gato command renders the current edition's eval (per-dimension scores + before/after voice exemplars) and `/newsletter_eval trend` renders recent editions' verdicts; the command is added to `isGatoBrainCommand` in `inject-gato-brain.mjs` (+ gato rebuild) so it isn't a dead command.

---

## Proposed eval thresholds & verdict mapping (operator to confirm/tune at the plan gate)

Config under `agentpulse-config.json → edition_eval` (operator-tunable). A dimension "fails" below its threshold; "passes" at or above.

| Dimension | Source | Fail (triggers rewrite/hold) | Pass |
|---|---|---|---|
| **Cross-edition continuity** | JUDGE-03 | bridge **absent** → score 1 = hard fail | bridge present + accurate, ≥4 |
| **Hedging filler** | JUDGE-04 (+ deterministic filler-blacklist hits) | score <3 **or** ≥3 blacklist hits | ≥4 and <3 hits |
| **Clickbait / fear-hook (professor voice)** | JUDGE-04 | score <3 | ≥4 (3 = warn) |
| **Repeated sub-topics** | JUDGE-04 | score <3 (repeats prior edition) | ≥4 |
| **Specificity** | JUDGE-04 | score <3 | ≥4 (3 = warn) |

**Verdict (worst-triggered wins):**

- `held_fabrication` — any Layer-1 fabrication flag (GitHub 404 / dead URL / unsourced study / arXiv / entity-merge). No rewrite. *(GATE-01, WIRE-02)*
- `passed` — Layer 1 clean AND all judge dimensions pass within N≤2 attempts. → normal human gate, no auto-publish. *(WIRE-04)*
- `held_voice` — Layer 1 clean but a judge dimension still fails after N=2 rewrite attempts → held + escalate. *(LOOP-02, WIRE-03)*
- `escalated` — the eval could not complete reliably (`eval_status='error'`: proxy down/402-cap/schema-invalid-after-retry) → loud, surfaced to the human; does **not** itself hold the draft (an error is not evidence). *(EVAL-02)*

**Activation:** report-only (`enforce:false`) for the first 2 editions to calibrate; operator flips `enforce:true` to arm auto-hold (WIRE-06). Until then, verdicts are recorded + surfaced but no status flips.

---

## Proposed DDL — `supabase/migrations/045_edition_evals.sql` (SQL-FIRST — operator reviews, then applies via MCP)

```sql
-- 045_edition_evals.sql  (next free number; 044 is highest applied)
CREATE TABLE edition_evals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    newsletter_id   UUID NOT NULL REFERENCES newsletters(id) ON DELETE CASCADE,
    edition_number  INT  NOT NULL,
    pipeline_version TEXT NOT NULL CHECK (pipeline_version IN ('single_pass','block_v1')),
    attempt         INT  NOT NULL DEFAULT 0,          -- 0 = initial eval; 1,2 = rewrite re-evals
    layer           TEXT NOT NULL CHECK (layer IN ('deterministic','judge')),
    eval_status     TEXT NOT NULL CHECK (eval_status IN ('ok','error')),
    error           TEXT,                              -- iff eval_status='error'
    verdict         TEXT CHECK (verdict IN ('passed','held_fabrication','held_voice','escalated')),
    -- fail-loud invariant: a verdict exists iff the eval ran
    CONSTRAINT edition_evals_verdict_iff_ok CHECK (
        (eval_status = 'ok'    AND verdict IS NOT NULL AND error IS NULL) OR
        (eval_status = 'error' AND verdict IS NULL     AND error IS NOT NULL)
    ),
    deterministic_flags JSONB NOT NULL DEFAULT '{}'::jsonb,  -- {fabrication:[...], mechanical:[...]}
    judge_scores        JSONB NOT NULL DEFAULT '{}'::jsonb,  -- {continuity:1, filler:4, ...} + before/after exemplars
    judge_feedback      TEXT,                                -- structured feedback passed to the rewrite
    sats_spent          INT  NOT NULL DEFAULT 0,
    model_calls         JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{model,purpose,sats}] audit trail
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (newsletter_id, layer, attempt)             -- one row per draft per layer per attempt
);
CREATE INDEX idx_edition_evals_trend ON edition_evals (edition_number DESC, pipeline_version);

-- governed eval agent (hash minted at key-time; model id is the non-EOL claude-sonnet-4-6)
INSERT INTO agent_registry (agent_name, agent_type, api_key_hash, access_tier, allowed_models, rate_limit_rpm, is_active)
VALUES ('edition_eval','internal','<bcrypt-hash>','internal',
        ARRAY['deepseek-chat','claude-sonnet-4-6'], 10, TRUE);
INSERT INTO agent_wallets_v2 (agent_name, balance_sats, total_deposited_sats, allow_negative,
                              spending_cap_sats, spending_cap_window, uncapped, on_cap_behavior, downgrade_map)
VALUES ('edition_eval', 25000, 25000, FALSE, 5000, 'weekly', FALSE, 'reject', '{}'::jsonb);
```

*Differs from spec 01's DDL: per-attempt rows (`attempt` + `UNIQUE(newsletter_id,layer,attempt)`) to support the rewrite-loop telemetry the milestone command requires, and the milestone's verdict taxonomy. `claude-sonnet-4-20250514` → `claude-sonnet-4-6` (EOL fix).*

---

## Future Requirements (deferred, tracked not scheduled)

- **REV-01** — operator-edit capture (`edition_revisions` append-only table; spec 01 G-07): capture operator edits at publish as a revision trail. Additive telemetry, not core to the gate.
- **AB-01** — quantitative single-pass vs block_v1 A/B comparison surfaced as a trend.
- **TUNE-01** — per-dimension / per-pipeline threshold auto-tuning from accumulated `edition_evals` history.
- **OBS-01** — eval-trend regression alerting (audit R8 observability).

## Out of Scope

| Feature | Reason |
|---------|--------|
| Auto-publish on eval pass | Explicitly excluded — the Monday human gate is unchanged (WIRE-04). |
| Auto-rewriting fabrication failures | Fabrication is expensive + silent; a rewrite only produces a more plausible hallucination. Hard stop → human (GATE-01). |
| LLM calls or retry/rewrite state in the Processor | Architectural rule — Processor stays a dumb sequencer (WIRE-05). |
| Applying schema before operator DDL approval | Process rule — SQL-first, operator applies via MCP. |
| Flipping `block_pipeline.enabled` to primary | The eval runs on whatever path produces the draft (single-pass published + block_v1 A/B); it does not change which path is primary. |
| Docker / unrelated-agent changes beyond the named wiring | Scope guard — only the files the spec names (newsletter, processor notify+held-guard, gato_brain command, gato allowlist, compose env passthrough, config, migration). |
| supabase-py `.in_()` | Known silent-failure bug — plain `.eq()` only. |
| Migration 043 application | Pre-existing unapplied migration; out of scope (carry-over). |

## Traceability

Every v1 requirement maps to exactly one phase. No orphans, no duplicates.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CTX-01 | Phase 26 — Continuity & Exemplar Context | Complete |
| CTX-02 | Phase 26 — Continuity & Exemplar Context | Complete |
| CTX-03 | Phase 26 — Continuity & Exemplar Context | Complete |
| CTX-04 | Phase 26 — Continuity & Exemplar Context | Complete |
| CTX-05 | Phase 26 — Continuity & Exemplar Context | Complete |
| EVAL-01 | Phase 27 — Eval Persistence & Governed Agent | Complete |
| EVAL-02 | Phase 27 — Eval Persistence & Governed Agent | Complete |
| EVAL-03 | Phase 27 — Eval Persistence & Governed Agent | Complete |
| GOV-01 | Phase 27 — Eval Persistence & Governed Agent | Complete |
| GOV-02 | Phase 27 — Eval Persistence & Governed Agent | Complete |
| GATE-01 | Phase 28 — Layer 1 Deterministic Gate | Complete |
| GATE-02 | Phase 28 — Layer 1 Deterministic Gate | Complete |
| GATE-03 | Phase 28 — Layer 1 Deterministic Gate | Complete |
| GATE-04 | Phase 28 — Layer 1 Deterministic Gate | Complete |
| GATE-05 | Phase 28 — Layer 1 Deterministic Gate | Complete |
| GATE-06 | Phase 28 — Layer 1 Deterministic Gate | Complete |
| GATE-07 | Phase 28 — Layer 1 Deterministic Gate | Complete |
| GATE-08 | Phase 28 — Layer 1 Deterministic Gate | Complete |
| JUDGE-01 | Phase 29 — Layer 2 Judge + Feedback-Rewrite Loop | Complete |
| JUDGE-02 | Phase 29 — Layer 2 Judge + Feedback-Rewrite Loop | Complete |
| JUDGE-03 | Phase 29 — Layer 2 Judge + Feedback-Rewrite Loop | Complete |
| JUDGE-04 | Phase 29 — Layer 2 Judge + Feedback-Rewrite Loop | Complete |
| JUDGE-05 | Phase 29 — Layer 2 Judge + Feedback-Rewrite Loop | Complete |
| LOOP-01 | Phase 29 — Layer 2 Judge + Feedback-Rewrite Loop | Complete |
| LOOP-02 | Phase 29 — Layer 2 Judge + Feedback-Rewrite Loop | Complete |
| LOOP-03 | Phase 29 — Layer 2 Judge + Feedback-Rewrite Loop | Complete |
| LOOP-04 | Phase 29 — Layer 2 Judge + Feedback-Rewrite Loop | Complete |
| LOOP-05 | Phase 29 — Layer 2 Judge + Feedback-Rewrite Loop | Complete |
| WIRE-01 | Phase 30 — Sequencer Wiring, Hold Action & Activation Gate | Pending |
| WIRE-02 | Phase 30 — Sequencer Wiring, Hold Action & Activation Gate | Pending |
| WIRE-03 | Phase 30 — Sequencer Wiring, Hold Action & Activation Gate | Pending |
| WIRE-04 | Phase 30 — Sequencer Wiring, Hold Action & Activation Gate | Pending |
| WIRE-05 | Phase 30 — Sequencer Wiring, Hold Action & Activation Gate | Pending |
| WIRE-06 | Phase 30 — Sequencer Wiring, Hold Action & Activation Gate | Pending |
| SURF-01 | Phase 31 — Surfacing & Escalation | Pending |
| SURF-02 | Phase 31 — Surfacing & Escalation | Pending |
| SURF-03 | Phase 31 — Surfacing & Escalation | Pending |

**Coverage:**

- v1 requirements: **37 total** (CTX×5, GATE×8, JUDGE×5, LOOP×5, EVAL×3, GOV×2, WIRE×6, SURF×3)
- Mapped to phases: **37/37** ✓ (no orphans, no duplicates)
- Unmapped: **0**

**Per-phase distribution:**
| Phase | Requirements | Count |
|-------|--------------|-------|
| 26 — Continuity & Exemplar Context | CTX-01..05 | 5 |
| 27 — Eval Persistence & Governed Agent | EVAL-01..03, GOV-01..02 | 5 |
| 28 — Layer 1 Deterministic Gate | GATE-01..08 | 8 |
| 29 — Layer 2 Judge + Feedback-Rewrite Loop | JUDGE-01..05, LOOP-01..05 | 10 |
| 30 — Sequencer Wiring, Hold Action & Activation Gate | WIRE-01..06 | 6 |
| 31 — Surfacing & Escalation | SURF-01..03 | 3 |

*Requirements defined: 2026-06-22*
*Last updated: 2026-06-22 — traceability populated by roadmap creation (Phases 26–31, 37/37 mapped).*
