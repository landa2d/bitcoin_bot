# Phase 27: Eval Persistence & Governed Agent - Context

**Gathered:** 2026-06-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the **persistence + budget core** that both eval layers (Phases 28–30) write through — and **nothing in the live newsletter path changes this phase**. Two deliverables plus a thin helper:

1. **Migration 045 `edition_evals`** — one fail-loud row per draft per layer per attempt (`newsletter_id` + `edition_number`, `pipeline_version`, `attempt`, `layer`, `eval_status`, `verdict`, `deterministic_flags` jsonb, `judge_scores` jsonb, `judge_feedback`, `sats_spent`, `model_calls` jsonb) with the `verdict-iff-ok` CHECK and `UNIQUE(newsletter_id, layer, attempt)`. SQL-first; operator-applied via MCP after DDL review.
2. **A governed `edition_eval` proxy agent** — its own `agent_registry` + `agent_wallets_v2` rows, hard-capped, reject-on-cap, key delivered via `.env` (`LLM_PROXY_EVAL_KEY`), all model calls through `llm-proxy:8200`.
3. **A fail-loud persistence helper** (new `docker/newsletter/edition_eval.py`) — `write_eval_row()` + a reader — encoding the EVAL-02/EVAL-03 contract, plus a deterministic fixture test. This is the surface Phases 28/29 will call; it exists and is tested here even though the first real caller lands in Phase 28.

**Scope anchor (EVAL-01..03, GOV-01..02):** the table, the agent, and the persistence helper. Building the deterministic gate (Phase 28), the judge/rewrite loop (Phase 29), the sequencer wiring + hold action (Phase 30), or the Gato surfacing (Phase 31) is **out of scope**. This phase first realizes the milestone-wide **fail-loud / no-silent-zero** invariant and the **no-`.in_()`** rule for all eval reads/writes.

**Independent additive core:** depends on nothing hard (may proceed in parallel with Phase 26, which is already complete). The harness layers 28/29/30 depend on this — the table + agent + helper must exist before anything writes to the table or calls the proxy as `edition_eval`.

</domain>

<decisions>
## Implementation Decisions

### Eval-agent wallet sizing (GOV-02)
- **D-01:** Wallet seeded at **`spending_cap_sats = 5000`, `spending_cap_window = 'weekly'`, `balance_sats = total_deposited_sats = 25000`** (the REQUIREMENTS.md DDL default). With `allow_negative=false`, `on_cap_behavior='reject'`, `uncapped=false`. Rationale: worst-case Friday spend (both single_pass + block_v1 drafts failing and each needing 2 full-writer rewrites + re-judges) is ≈1,600 sats/edition — the single-pass writer call alone is ~322 sats / ~84k input tokens — so 5000/weekly is ~3× the worst case and more in the typical case. 25000 balance = ~5 weeks of cap as buffer.
- **D-02:** **Reject-on-cap is a SAFE failure, by design.** If the cap trips mid-eval the proxy returns 402 → the eval records `eval_status='error'` → `escalated` verdict (loud, surfaced, **does not hold the draft** — an error is not evidence). So erring low risks only false escalations, not silent passes; erring high weakens the "a runaway eval loop has no editorial value" guard. The cap is live even during the report-only activation window (report-only governs the *hold action*, not the budget).
- **D-03:** **Re-tune the cap after the report-only editions.** The first ~2 editions run `enforce:false` (WIRE-06, Phase 30) and will yield REAL per-edition sats data; the operator re-checks 5000/weekly against actual spend before arming. The DDL default is the calibration starting point, not a final number.

### Table shape (EVAL-01)
- **D-04:** **JSONB-only, per the authoritative REQUIREMENTS.md DDL** — do NOT add spec-01's materialized headline columns (`tier1_count`, `voice_score`, `filler_hits`, `continuity`, `structural_violations`, `regression`, …). Top-level typed columns stay: `id`, `newsletter_id`, `edition_number`, `pipeline_version`, `attempt`, `layer`, `eval_status`, `error`, `verdict`, `sats_spent`, `created_at`. Variable-shape evidence is JSONB/TEXT: `deterministic_flags` jsonb (`{fabrication:[...], mechanical:[...]}`), `judge_scores` jsonb (`{continuity:1, filler:4, ...}` + before/after exemplars), `model_calls` jsonb (`[{model,purpose,sats}]`), `judge_feedback` text.
- **D-05:** Rationale (two fail-loud reasons): (a) the judge's **dimension set is config-tunable** (Phase 29, under `agentpulse-config.json → edition_eval`) — materializing per-dimension columns would hard-code tunable config names into the schema; (b) a materialized-column-plus-JSONB-source pair creates a **"which is canonical?" dual-write drift hazard**, exactly the silent-failure class this milestone fights.
- **D-06:** Phase 31's needs are already met by the top-level columns: the verdict-trend (`SURF-03`) is a plain select on `verdict` + `edition_number`; the Friday-notify "headline metrics" (`SURF-02`) and per-dimension render (`SURF-03`) parse the `judge_scores` JSONB **dict in Python** that the select already returns (cheap, no `.in_()`). SQL aggregation over per-dimension scores is **not** required this milestone — `TUNE-01` / `OBS-01` (auto-tuning, trend-regression alerting) are already-deferred future requirements; revisit materialized analytics columns there if/when SQL aggregation is actually needed.
- **D-07:** **DDL fidelity locked to REQUIREMENTS.md, NOT spec-01.** Per-attempt rows (`attempt INT DEFAULT 0` + `UNIQUE(newsletter_id, layer, attempt)`), verdict taxonomy `passed / held_fabrication / held_voice / escalated`, the `edition_evals_verdict_iff_ok` CHECK (`ok` ⇒ verdict NOT NULL + error NULL; `error` ⇒ verdict NULL + error NOT NULL), `pipeline_version IN ('single_pass','block_v1')`, `layer IN ('deterministic','judge')`, `eval_status IN ('ok','error')`, index `idx_edition_evals_trend (edition_number DESC, pipeline_version)`. Model id is `claude-sonnet-4-6` (spec-01's `claude-sonnet-4-20250514` is EOL). **`edition_revisions` is NOT in this phase** (deferred as REV-01).

### Persistence helper scope (EVAL-02, EVAL-03)
- **D-08:** **Ship the fail-loud persistence helper THIS phase** — new `docker/newsletter/edition_eval.py` with `write_eval_row(...)` (writes one `edition_evals` row) + a reader (by `newsletter_id`, and a trend reader by `edition_number DESC` for Phase 31). It is the "core both layers write through": Phases 28/29 import and call it rather than re-implementing persistence. Built and tested here even though the first real caller is Phase 28 — mirrors the Phase 26 precedent (loader + fixture test built ahead of its downstream judge consumer).
- **D-09:** **Fail-loud write contract** the helper encodes and the test proves: (a) an eval that errored writes `eval_status='error'` + a non-null `error` reason and a NULL verdict — never a silent zero score; (b) a proxy 402 / cap-hit is an **error state**, never a `0`; (c) the eval-row write itself failing **logs ERROR (`exc_info=True`) and raises / returns an explicit error — never a bare `except`, never swallowed**, so a caller cannot silently continue; (d) all reads/writes use plain supabase-py `.eq()` — **no `.in_()`** anywhere.
- **D-10:** **EVAL-02's "Telegram-alerted on write failure" splits across phases — by design, noted so EVAL-02 is not falsely closed.** Phase 27 delivers the *structural* half (loud log + raise, never swallowed). The *Telegram-delivery* half is wired where the machinery exists: Phase 30 (the `newsletter_poller` sequencer wraps the eval and surfaces failures) + Phase 31 (`SURF-01` hardens `send_telegram`, which lives in the **Processor** — the newsletter service has NO telegram path today, and duplicating one here would fork the very `send_telegram` SURF-01 exists to harden). Do not build a newsletter→Telegram path in this phase.

### Migration packaging & key-mint sequencing (GOV-01, GOV-02)
- **D-11:** **One sectioned, idempotent file `supabase/migrations/045_edition_evals.sql`** (034-style sections): **SECTION 1** = `CREATE TABLE` (guarded for re-apply safety) + the CHECK/UNIQUE constraints + the trend index; **SECTION 2** = `INSERT … agent_registry` + `INSERT … agent_wallets_v2` using **`ON CONFLICT (agent_name) DO UPDATE`** (029 pattern) so re-apply is safe. Sections are independently runnable if a re-seed is ever needed.
- **D-12:** **Key-mint is worktree-unsafe / orchestrator-owned on the main tree** (a worktree executor cannot mint keys or apply migrations). Sequence: orchestrator **mints the `edition_eval` key first** (generates the `ap_edition_eval_<…>` key + its bcrypt hash), **substitutes the real bcrypt hash into SECTION 2** of the migration file, delivers the plaintext key to `config/.env` as `LLM_PROXY_EVAL_KEY` (**never** in compose, per Spec 02 / GOV-02), then **MCP-applies the whole file**.
- **D-13:** **Commit the real bcrypt hash in the migration file** (the 029 precedent — `029_rivalscope_agent.sql` committed its literal hash; bcrypt is one-way and the key is an internal proxy key). The committed file is the audit record of which key-hash is live, keeping the migration self-contained and reproducible.
- **D-14:** **Verify via a settled proxy call, not container-up.** After apply + mint, prove the agent works end-to-end with one `curl`/test call through `llm-proxy:8200` as `edition_eval` and confirm it **settles** in `agent_wallets_v2` / wallet transactions (the governed-cycle discipline). The `agent_wallets_v2_cap_or_uncapped` CHECK (migration 034) is satisfied because `spending_cap_sats=5000 (>0)`.

### Eval-agent proxy identity (GOV-01)
- **D-15:** The eval module must call the proxy under its **own `edition_eval` identity** (`LLM_PROXY_EVAL_KEY`), **NOT** the newsletter service's `newsletter` agent key. The newsletter container today resolves a single agent identity via `_get_agent_api_key()` (`AGENT_API_KEY` env → else `agent_api_keys` table for `AGENT_NAME='newsletter'`); the governed-budget point of GOV-02 is a **separate** wallet, so the eval module reads `LLM_PROXY_EVAL_KEY` and passes it explicitly on its proxy calls. (Mechanism — env-read vs a second `agent_api_keys` lookup — is the planner's call; the *identity separation* is locked.)

### Claude's Discretion
- The reader helper's exact signature/return shape (by `newsletter_id`; a trend reader by `edition_number DESC, pipeline_version`), as long as both use `.eq()`-only and return enough for Phase 31's render.
- The exact `write_eval_row()` parameter surface — it takes the column contract (identity + status + verdict + the JSONB dicts), not the layers' internal flag/score shapes (those stay loosely-typed dicts).
- Whether the guarded table DDL uses `CREATE TABLE IF NOT EXISTS` vs a `DO $$ … duplicate_object` guard (034 style) — planner's call, as long as re-apply is safe.
- The exact key-mint command / how 029's bcrypt hash was generated — researcher confirms the proxy's `ap_<agent>_<hash>` mint mechanic before the orchestrator runs it.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 27 source specs (authoritative)
- `.planning/REQUIREMENTS.md` §EVAL / §GOV + **"Proposed DDL — `supabase/migrations/045_edition_evals.sql`"** — the **authoritative** locked WHAT (EVAL-01..03, GOV-01..02) and the per-attempt DDL this phase implements verbatim (overrides spec-01's DDL shape).
- `.planning/ROADMAP.md` §"Phase 27: Eval Persistence & Governed Agent" — goal, depends-on, success criteria (1–4), notes (migration numbering, verdict taxonomy, worktree-unsafe steps).

### Implementation reference (pattern source — superseded on DDL shape by REQUIREMENTS.md)
- `docs/audit/specs/01_eval_harness.md` (audit R5) — the agent/wallet **seeding pattern**, the fail-loud rules (error-row, proxy-402-is-error, write-failure-is-loud), the proxy call patterns (`synthesis_sonnet_call` via `/anthropic/v1/messages`; DeepSeek via `/v1/chat/completions`), and the execution-group ordering (apply → mint → seed → verify). **Note the divergences locked by REQUIREMENTS.md:** per-attempt rows + `UNIQUE(newsletter_id, layer, attempt)` (spec-01 was `UNIQUE(newsletter_id)`), verdict taxonomy `passed/held_fabrication/held_voice/escalated` (spec-01 was `pass/warn/fail`), JSONB-only (no spec-01 materialized columns), `claude-sonnet-4-6` (spec-01's model is EOL), and **no `edition_revisions` table** (REV-01 deferred).

### Seeding / governance pattern precedents (read before authoring the migration)
- `supabase/migrations/029_rivalscope_agent.sql` — the canonical agent-seed migration: `agent_registry` + `agent_wallets_v2` INSERTs with `ON CONFLICT (agent_name) DO UPDATE`, a committed bcrypt hash, `internal` tier. The template for SECTION 2.
- `supabase/migrations/034_governance_caps_and_oncap_behavior.sql` — the `agent_wallets_v2` schema (`uncapped`, `on_cap_behavior` CHECK `IN ('reject','downgrade')`, `downgrade_map`), the `agent_wallets_v2_cap_or_uncapped` structural CHECK the eval row must satisfy, and the house **idempotency style** (sectioned `DO $$ … EXCEPTION duplicate_object`).

### Prior phase context (the loader this core will eventually feed the judge)
- `.planning/phases/26-continuity-exemplar-context/26-CONTEXT.md` — Phase 26 is complete; its loader + exemplars feed the Phase 29 judge that writes through this table. Establishes the **deterministic-fixture-test-against-an-in-memory-Supabase-stub** pattern D-08's test should mirror (`tests/test_26_continuity_loader.py`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Agent seed migration template:** `supabase/migrations/029_rivalscope_agent.sql` — copy its `agent_registry` + `agent_wallets_v2` INSERT shape and `ON CONFLICT … DO UPDATE` idempotency for SECTION 2 (adjust columns to GOV-02: `allow_negative=FALSE`, `spending_cap_sats=5000`, `spending_cap_window='weekly'`, `on_cap_behavior='reject'`, `uncapped=FALSE`, `downgrade_map='{}'::jsonb`).
- **Idempotent sectioned migration template:** `034_governance_caps_and_oncap_behavior.sql` — the section structure + `DO $$ … duplicate_object` guards for re-apply safety, and the `agent_wallets_v2` column set the seed writes to.
- **Fixture-test pattern:** `tests/test_26_continuity_loader.py` — imports the REAL module function (no re-implementation) and asserts against an in-memory Supabase stub (never the live DB). D-08's `edition_eval.py` test should mirror this: prove the ok-row write, the error-row write (verdict NULL + reason, CHECK respected), the loud-raise-on-write-failure, and `.eq()`-only reads.

### Established Patterns
- **`.eq()` only — never `.in_()`** (known silent-failure bug). All `edition_evals` reads/writes (EVAL-03).
- **All LLM via `llm-proxy:8200`** — Sonnet via `/anthropic/v1/messages` (httpx, status-checked), DeepSeek via `/v1/chat/completions`. No direct provider SDK. The newsletter service already routes its own LLM this way (`newsletter_poller.py`).
- **Per-service agent identity** resolved via `_get_agent_api_key()` (`newsletter_poller.py:206-215`): `AGENT_API_KEY` env → else `agent_api_keys` table for `AGENT_NAME`. The eval module needs a **separate** identity (`LLM_PROXY_EVAL_KEY`) — see D-15.
- **Migrations are SQL-first**, authored in-phase, applied by the operator via MCP (project ref `zxzaaqfowtqvmsbitqpu`). Next free number is **045** (044 = highest applied `signals_anon_view`; **043 is an unapplied carry-over, out of scope** — live list jumps 042→044).

### Integration Points (where this core will be consumed later — NOT wired this phase)
- `docker/newsletter/edition_eval.py` (new) — the helper module; home for `write_eval_row()` + readers, and (in Phases 28/29) the deterministic gate + judge/loop.
- `docker/newsletter/newsletter_poller.py` — the two generation save points the **sequencer** (Phase 30) will call the eval from: single-pass save return (~`:2078` primary / the A/B path at `:2269`) and the block_v1 insert. **No wiring here in Phase 27** — the helper just exists.
- `docker/processor/agentpulse_processor.py` — owns `send_telegram` (fail-soft today) and the Friday notify; the alert-delivery + surfacing (D-10) lands here in Phases 30/31, not now.

### Current state (live DB, project ref `zxzaaqfowtqvmsbitqpu`)
- **`edition_evals` does not exist** (design-only) — no code references it yet (confirmed: `grep -rln edition_evals docker/` is empty). Nothing depends on it; the phase is purely additive.
- `agent_wallets_v2` carries the `uncapped` / `on_cap_behavior` / `downgrade_map` columns + the `cap_or_uncapped` CHECK (from migration 034). The 5 capped agents (analyst/processor/research/newsletter/gato) are the existing pattern; `edition_eval` joins them as a 6th capped, reject-on-cap agent.
- `config/.env` already holds `LLM_PROXY_<SERVICE>_KEY` for processor/analyst/research/newsletter/gato/admin/labdata. `LLM_PROXY_EVAL_KEY` is **net-new** (minted this phase).

</code_context>

<specifics>
## Specific Ideas

- The operator's consistent posture (carried from Phase 26 and the milestone invariants): **fail-loud over convenience.** Every decision here picks the loud/explicit path — reject-on-cap that escalates rather than silently passing (D-02), no silent-zero on error (D-09), raise-not-swallow on write failure (D-09/D-10), and JSONB-only to avoid a canonical-source drift hazard (D-05).
- **Authority order is firm:** REQUIREMENTS.md (the milestone command) is authoritative; audit spec-01 is the *pattern* reference only. Where they diverge (DDL shape, verdict taxonomy, model id, `edition_revisions`), REQUIREMENTS.md wins (D-07).
- The report-only activation window (Phase 30) is reframed as **doubling as wallet-cap calibration** (D-03): it produces the real spend data that confirms or re-tunes the 5000/weekly default before any auto-hold arms.

</specifics>

<deferred>
## Deferred Ideas

- **Materialized analytics columns / SQL aggregation over per-dimension scores** → `TUNE-01` (per-dimension/per-pipeline threshold auto-tuning) + `OBS-01` (eval-trend regression alerting), both already-deferred v2.3 future requirements. Revisit a typed-column shape only if/when SQL aggregation is genuinely needed there.
- **`edition_revisions` operator-edit-capture table** (spec-01 G-07) → `REV-01`, already deferred. Not in migration 045.

### Reviewed Todos (not folded)
- **`2026-06-24-single-pass-writer-empty-response-claude-sonnet-4-6.md`** (match score 0.9) — the **P1 single-pass writer empty-response** bug (Friday-edition risk). Reviewed, **NOT folded**: it's a generation-path JSON-parse bug orthogonal to building the eval table/agent; it has its own debug task and is tracked as a STATE.md blocker. (Relevant *context* only — the eval will eventually score this writer's output — but the fix is not Phase 27 work.)
- **`2026-05-28-harden-soft-caps-allow-negative.md`** (match score 0.6) — soft-cap `allow_negative` hardening. Reviewed, **NOT folded**: concerns the *other 5* soft-capped agents; `edition_eval` is `allow_negative=false` by design (GOV-02), so this phase doesn't touch it.
- Two further keyword-only matches (`pay-endpoint RPC search_path`, `phase-05 review follow-ups`) — unrelated false positives, not folded.

</deferred>

---

*Phase: 27-eval-persistence-governed-agent*
*Context gathered: 2026-06-24*
