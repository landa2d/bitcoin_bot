# Roadmap: AgentPulse — The Agent Economy (Living Reference Articles)

## Milestones

- ✅ **v1.0 Agent Economy Map** — Phases 1–10 + 4.1 (shipped 2026-06-04) — full details: [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 Frontend Redesign** — Phases 11–14 (shipped 2026-06-08) — full details: [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md)
- ✅ **v2.1 Agent Economy Content** — Phases 15–18 (shipped 2026-06-09) — full details: [`milestones/v2.1-ROADMAP.md`](milestones/v2.1-ROADMAP.md)
- ✅ **v2.2 Landing Redesign + Signals Feed** — Phases 19–25 (shipped 2026-06-19) — full details: [`milestones/v2.2-ROADMAP.md`](milestones/v2.2-ROADMAP.md)
- 🚧 **v2.3 Pre-Publish Evaluation Step** — Phases 26–31 (in progress, started 2026-06-22)

_Active milestone: **v2.3 — Pre-Publish Evaluation Step** (Phases 26–31). Phase numbering continues from 25._

## Phases

<details>
<summary>✅ v1.0 Agent Economy Map (Phases 1–10 + 4.1) — SHIPPED 2026-06-04 — 11 phases, 29 plans</summary>

- [x] Phase 1: Render-Stack Diagnostic (1/1) — completed 2026-05-26
- [x] Phase 2: `economy_map` Schema + Seven-Block Seed (2/2) — completed 2026-05-27
- [x] Phase 3: Design Tokens (3/3) — completed 2026-05-27
- [x] Phase 4: Hub, Block, and Status Renderer (6/6) — completed 2026-05-28
- [x] Phase 4.1: Prod↔Main Reconciliation + LLM-Proxy Governance Migration (3/3) — completed 2026-05-28
- [x] Phase 5: Intake Classifier + `unsorted` Handling (3/3) — completed 2026-05-28
- [x] Phase 6: Telegram Read-Only Scaffolding (2/2) — completed 2026-05-30
- [x] Phase 7: Synthesis Loop Core (2/2) — completed 2026-06-01
- [x] Phase 8: Validation Sentinels (2/2) — completed 2026-06-02
- [x] Phase 9: Gated Publishing + Approval Commands (2/2) — completed 2026-06-03
- [x] Phase 10: Operator Write Commands (3/3) — completed 2026-06-04

Full phase details, goals, success criteria, and per-plan breakdown archived in [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md).

</details>

<details>
<summary>✅ v2.0 Frontend Redesign (Phases 11–14) — SHIPPED 2026-06-08 — 4 phases, 8 plans</summary>

UI-only redesign of the public `aiagentspulse.com` SPA: persistent stateful 3-tab nav shell, editorial Source Serif 4 / IBM Plex Mono typography, single light-mode violet accent (replacing the dark map theme), the Agent Economy as a responsive grouped card grid, a Newsletter-only mode toggle, and a "What is AgentPulse" About page. Frontend-only — no backend/pipeline/Supabase/content changes. Deployed live via the scoped `agentpulse-web` rebuild.

- [x] Phase 11: Design System + Nav Shell (2/2) — completed 2026-06-04 (NAV-01..04, TYPE-01..03, COLOR-01..02)
- [x] Phase 12: Newsletter Section Restyle (2/2) — completed 2026-06-04 (TGL-01, TGL-02)
- [x] Phase 13: Agent Economy Grid (2/2) — completed 2026-06-05 (MAP-01..04)
- [x] Phase 14: About Stub + Polish Pass (2/2) — completed 2026-06-08 (ABOUT-01, POLISH-01)

Full phase details, goals, success criteria, and per-plan breakdown archived in [`milestones/v2.0-ROADMAP.md`](milestones/v2.0-ROADMAP.md).

</details>

<details>
<summary>✅ v2.1 Agent Economy Content (Phases 15–18) — SHIPPED 2026-06-09 — 4 phases, 10 plans</summary>

Filled the v2.0 grid with real editorial content: loaded the hub `agent-economy` + 7 block bodies into `economy_map` as unpublished (migration 043 + a standalone PostgREST loader), wired every `#/map/<slug>` cross-link, verified on a flag-gated preview route, then published all 8 in-scope bodies live in ONE operator-approved batch via the atomic `publish_block_version` RPC. Content-only — no UI redesign, no pipeline/proxy/agent-service changes. `regulation-legal` kept deferred.

- [x] Phase 15: Inventory & Roster Reconciliation (2/2) — completed 2026-06-08 (INV-01, INV-02, ROST-01)
- [x] Phase 16: Content Load (unpublished) (3/3) — completed 2026-06-08 (LOAD-01, LOAD-02, LOAD-03)
- [x] Phase 17: Cross-link Wiring & Preview (2/2) — completed 2026-06-09 (LINK-01, PREV-01, HUB-01)
- [x] Phase 18: Gated Batch Publish (3/3) — completed 2026-06-09 (PUB-01)

Full phase details, goals, success criteria, and per-plan breakdown archived in [`milestones/v2.1-ROADMAP.md`](milestones/v2.1-ROADMAP.md).

</details>

<details>
<summary>✅ v2.2 Landing Redesign + Signals Feed (Phases 19–25) — SHIPPED 2026-06-19 — 7 phases, 17 plans</summary>

Re-skinned the public `aiagentspulse.com` SPA to the new editorial mockup — the four top-level sections (newsletter / signals / agent-economy / about) merged into ONE single-scroll landing with an `IntersectionObserver` scroll-spy nav, while individual editions (`#/edition/<n>`) and block pages (`#/map/<slug>`) stayed deep-linkable detail routes — fixed the four live-site defects the redesign brief called out, and added a new tier-1 Signals feed. NOT frontend-only: Phase 19 touched the newsletter write-path (+ a confirm-and-close storage scan, no backfill needed) and Phase 24 added the milestone's one Supabase migration (a security-definer anon `signals_feed` view over tier-1 `source_posts`). Deployed live via gated, drift-checked, operator-approved scoped `web` rebuilds throughout.

- [x] Phase 19: Smart-Quote / Apostrophe Corruption Fix (2/2) — completed 2026-06-10 (QUOTE-01, QUOTE-02)
- [x] Phase 20: Width Tokens & Centering Foundation (2/2) — completed 2026-06-11 (WIDTH-01, RHYTHM-01)
- [x] Phase 21: Single-Scroll Landing + Scroll-Spy Nav (2/2) — completed 2026-06-11 (SCROLL-01, SCROLL-02)
- [x] Phase 22: Per-Section Visual Fixes (4/4) — completed 2026-06-12 (HEAD-01, GRID-01, GRID-02, AGENTS-01)
- [x] Phase 23: Distinct Newsletter Excerpts (2/2) — completed 2026-06-16 (EXCERPT-01)
- [x] Phase 24: Signals Section (3/3) — completed 2026-06-17 (SIGNAL-01..04)
- [x] Phase 25: Responsive & Accessibility Pass (2/2) — completed 2026-06-19 (RESP-01, A11Y-01)

Full phase details, goals, success criteria, and per-plan breakdown archived in [`milestones/v2.2-ROADMAP.md`](milestones/v2.2-ROADMAP.md).

</details>

### 🚧 v2.3 Pre-Publish Evaluation Step (Phases 26–31) — IN PROGRESS

**Milestone Goal:** Insert an automated, two-layer evaluation step *between* newsletter draft generation and publish — a hard **deterministic gate** that catches fabrication/mechanical errors (hold + escalate, **never** rewrite) and an **LLM-judge + bounded N=2 feedback-rewrite loop** that catches voice/editorial misses — so these errors are caught (and where safe, auto-corrected) at machine speed before the operator's Monday review. **Passing the eval does NOT auto-publish; the existing human gate is unchanged.** This is audit roadmap item **R5** (`docs/audit/specs/01_eval_harness.md`) + a new Layer-2 judge→rewrite loop, with audit **R4** (`07_continuity_and_exemplars.md`) folded in as Phase 26.

**Ordering rationale (low-to-high risk; additive before invasive):** CTX (additive continuity/exemplar loader, dependency of the judge) → EVAL/GOV (the table + governed agent the harness writes through) → GATE (Layer 1 deterministic, no LLM, short-circuits) → JUDGE+LOOP (Layer 2 LLM judge + rewrite loop) → WIRE (sequencer invocation + held action + report-only `enforce` gate) → SURF (operator-facing surfacing + escalation; gato rebuild). Each phase is independently shippable / rollback-safe.

**Standing milestone invariants (carried into EVERY phase — operator-confirmed 2026-06-22):**

- Both eval layers run in the **newsletter service** at the two generation save points (single-pass save return + block_v1 insert) — the only place the true fact base exists in memory (`input_data` for single-pass, `blocks_data` for block_v1). The `newsletter_poller` is the dumb sequencer.
- The literal **Processor stays a dumb sequencer**: it triggers generation, owns the publish gate, and surfaces eval verdicts via a plain select. **No LLM calls, no retry/rewrite state in the Processor.**
- All LLM via `llm-proxy:8200` (Sonnet `claude-sonnet-4-6` via `/anthropic/v1/messages`; DeepSeek via `/v1/chat/completions`). No direct provider SDK calls.
- **Fail loud:** NULL ≠ intent; no bare excepts; eval error → `eval_status='error'` + reason, never a silent zero. No supabase-py `.in_()`.
- **SQL-first:** migrations authored in-phase, applied by the operator via MCP. Scoped rebuilds use service names; migration-apply / key-mint / gato-rebuild steps are worktree-unsafe and orchestrator/operator-owned on the main tree.
- Fabrication is a **HARD stop** (held + escalate, never rewrite). Passing the eval **never** auto-publishes (Monday human gate unchanged). Auto-hold is gated behind a report-only `enforce` flag the operator activates.

- [x] **Phase 26: Continuity & Exemplar Context** — `load_edition_context()` feeds prior-edition angles + operator-approved exemplars to both writer paths and the judge; resurrects the dead Phase E voice check (CTX-01..05) (completed 2026-06-24)
- [x] **Phase 27: Eval Persistence & Governed Agent** — migration 045 `edition_evals` (per-attempt, fail-loud) + a governed, hard-capped `edition_eval` proxy agent (EVAL-01..03, GOV-01..02) (completed 2026-06-25)
- [ ] **Phase 28: Layer 1 Deterministic Gate** — no-LLM fabrication (GitHub/URL/arXiv/named-study/entity-merge) + mechanical-editorial checks against the correct in-memory fact base, short-circuits to hold+escalate (GATE-01..08)
- [ ] **Phase 29: Layer 2 Judge + Feedback-Rewrite Loop** — standalone module: Sonnet judge on exemplar-anchored dimensions + bounded N=2 rewrite loop, returns final draft + verdict (JUDGE-01..05, LOOP-01..05)
- [ ] **Phase 30: Sequencer Wiring, Hold Action & Activation Gate** — invoke gate+module at the two save points, act on verdicts (held/do_not_publish), behind a report-only `enforce` flag; Processor stays dumb (WIRE-01..06)
- [ ] **Phase 31: Surfacing & Escalation** — hardened `send_telegram` alerts + Friday-notify eval summary + live `/newsletter_eval` Gato command (+ allowlist + gato rebuild) (SURF-01..03)

## Phase Details

### Phase 26: Continuity & Exemplar Context

**Goal**: A `load_edition_context()` loader feeds prior published editions' angles and operator-approved exemplar paragraphs into both writer paths (single-pass + block) and the (downstream) eval judge — fail-loud-but-not-fatal on an empty corpus — and resurrects the dead Phase E voice check. This is audit R4, the hard dependency of the Layer-2 continuity/voice judge, and the lowest-risk, purely-additive change.
**Depends on**: Nothing (first phase of the milestone; builds on the existing newsletter service)
**Requirements**: CTX-01, CTX-02, CTX-03, CTX-04, CTX-05
**Success Criteria** (what must be TRUE):

  1. `load_edition_context()` returns the last 3 published editions' `{edition_number, title, primary_theme, opening_excerpt, weeks_ago}` using plain `.eq('status','published')` (never `.in_()`).
  2. The loader returns operator-approved exemplar paragraphs (≥40 words, non-header/list) from the most recent published editions, capped at `exemplar_paras`.
  3. On zero published editions the loader returns an explicit `{previous_editions:[], exemplars:[], empty:true}` and logs a WARNING — never a bare `{}` indistinguishable from "not loaded" — and generation still completes.
  4. Both writer paths AND the eval judge receive the continuity context + exemplars; an upstream-provided `narrative_context` still wins via `setdefault`.
  5. The Phase E voice check produces a real score with ≥1 observation instead of the "skipped / No exemplars provided" sentinel.**Plans**: 3 plans (Wave 1 autonomous code, Wave 2 autonomous fixture test, Wave 3 operator/orchestrator-owned live)

**Wave 1**

  - [x] 26-01-PLAN.md — Loader + injection + avoided-themes feed + exemplars pass-through + Phase E "not scored" resurrection (CTX-01..05) [Wave 1, autonomous]

**Wave 2** *(blocked on Wave 1 completion)*

  - [x] 26-02-PLAN.md — Deterministic fixture test for load_edition_context, D-16 case set (CTX-01..03,05) [Wave 2, autonomous, depends 26-01]

**Wave 3** *(blocked on Wave 2 completion)*

  - [x] 26-03-PLAN.md — Operator-confirmed lead_theme backfill (D-12/D-13) + live generation trigger end-to-end verify (D-17/D-18) (CTX-04,05) [Wave 3, worktree-unsafe]

**Notes**: Newsletter service only; no LLM new call surface (the loader is DB reads + injection). Fail-loud-but-not-fatal: an empty corpus warns and continues, never aborts generation. No `.in_()` (CTX-01 uses `.eq('status','published')`). Resurrecting Phase E (CTX-05) closes the audit-noted dead voice check; reference `docs/audit/specs/07_continuity_and_exemplars.md`.

### Phase 27: Eval Persistence & Governed Agent

**Goal**: The `edition_evals` table (migration 045) and a governed `edition_eval` proxy agent exist — the fail-loud persistence + budget core that both eval layers write through. The migration is SQL-first (authored in-phase, operator-applied via MCP after DDL review); the agent has its own hard-capped, reject-on-cap wallet. This phase first realizes the milestone-wide fail-loud-no-silent-zero invariant and the no-`.in_()` rule for all eval reads/writes.
**Depends on**: Nothing hard (an independent additive core; may proceed in parallel with Phase 26). The harness layers (Phases 28, 29, 30) depend on this phase — the table + agent must exist before anything writes to the table or calls the proxy.
**Requirements**: EVAL-01, EVAL-02, EVAL-03, GOV-01, GOV-02
**Success Criteria** (what must be TRUE):

  1. Migration 045 creates `edition_evals` (one row per draft per attempt: newsletter id + edition number, `pipeline_version`, attempt, layer, `eval_status`, verdict, deterministic flags jsonb, judge scores jsonb, judge feedback, sats/model-call audit) with the `verdict-iff-ok` CHECK + the `UNIQUE(newsletter_id, layer, attempt)` constraint, applied by the operator via MCP after DDL review.
  2. An eval that errors writes `eval_status='error'` + reason — a proxy 402/cap-hit is an error state, never a zero score; an eval-row write that fails is logged ERROR + Telegram-alerted, never swallowed; no bare excepts.
  3. All `edition_evals` reads/writes use plain supabase-py `.eq()` (no `.in_()`).
  4. A governed `edition_eval` agent (its own `agent_registry` + `agent_wallets_v2` rows, `allow_negative=false`, weekly `spending_cap_sats`, `on_cap_behavior='reject'`, `uncapped=false`) routes all model calls through `llm-proxy:8200` (Sonnet via `/anthropic/v1/messages`, DeepSeek via `/v1/chat/completions`) with no direct provider SDK calls; the key is delivered via `.env` (`LLM_PROXY_EVAL_KEY`), never in compose.

**Plans**: 3 plans (Wave 1 autonomous code/SQL authoring + helper/test in parallel, Wave 2 orchestrator/operator-owned key-mint + MCP apply + settled-call verify)

**Wave 1** *(parallel — no file overlap)*

  - [x] 27-01-PLAN.md — Author migration 045 `edition_evals.sql`: SECTION 1 (table + verdict-iff-ok CHECK + UNIQUE(newsletter_id,layer,attempt) + trend index) + SECTION 2 (governed `edition_eval` agent seed, GOV-02 wallet, `<bcrypt-hash>` placeholder) (EVAL-01, GOV-01, GOV-02) [Wave 1, autonomous]
  - [x] 27-02-PLAN.md — `docker/newsletter/edition_eval.py` fail-loud `write_eval_row` + `.eq()`-only readers + LLM_PROXY_EVAL_KEY identity getter, and `tests/test_27_edition_eval.py` deterministic fixture suite (EVAL-02, EVAL-03) [Wave 1, autonomous] (completed 2026-06-25)

**Wave 2** *(blocked on 27-01; worktree-unsafe, orchestrator/operator-owned)*

  - [x] 27-03-PLAN.md — Mint the `edition_eval` key + substitute the real bcrypt hash into 045 + deliver `LLM_PROXY_EVAL_KEY` to `config/.env`; MCP-apply migration 045; verify a settled proxy call as `edition_eval` (EVAL-01 live, GOV-01, GOV-02) [Wave 2, autonomous:false]

**Notes**: SQL-FIRST + cross-cutting persistence core. Sequential / partly worktree-unsafe: the migration apply (MCP) + the agent key mint are orchestrator/operator-owned on the main tree (a worktree executor cannot apply migrations or mint keys). Next free migration number is 045 (044 is highest applied; 043 is an unapplied carry-over, out of scope). Verdict taxonomy: `passed` / `held_fabrication` / `held_voice` / `escalated`. Reference `docs/audit/specs/01_eval_harness.md` for the agent/wallet seeding pattern.

### Phase 28: Layer 1 Deterministic Gate

**Goal**: A deterministic gate (no LLM) runs on every edition (both versions) before any LLM judge/rewrite, verifying against the **correct** in-memory fact base, and flags fabrication (live GitHub repo + star-count, URL liveness HEAD, arXiv-ID validation, named-study/benchmark-vs-fact-base, entity-merge / verbatim-in-a-single-source) plus mechanical editorial misses (H1/title echo in body, reading-mode-label leak, recycled closer vs prior edition, stat duplicated verbatim from prior edition) — short-circuiting to hold+escalate on any fabrication flag with **zero** LLM or rewrite attempts. Built and proven report-only first (the actual hold action lands in Phase 30 behind the `enforce` flag).
**Depends on**: Phase 27 (persists deterministic-layer rows to `edition_evals`; reuses the fail-loud + no-`.in_()` persistence patterns)
**Requirements**: GATE-01, GATE-02, GATE-03, GATE-04, GATE-05, GATE-06, GATE-07, GATE-08
**Success Criteria** (what must be TRUE):

  1. The gate runs on every edition (both versions) before any LLM judge/rewrite and short-circuits on any fabrication flag with zero LLM or rewrite attempts.
  2. Fabrication checks fire: every owner/repo + `github.com/owner/repo` ref checked against the live GitHub API (404 → fabricated; >20% star-count drift → flag); every URL HEAD-checked with a 5s timeout (connection failure or 4xx/5xx → flag); every named study/benchmark/paper title + arXiv ID cross-checked against the edition's fact base (no matching ingested source → fabricated); entity-merge flagged (a named entity not present verbatim in any single source).
  3. Mechanical checks fire: an H1/edition title echoed in the body is flagged (body must start at `## Read This, Skip the Rest`); leaked reading-mode labels are flagged; recycled closer lines and stats duplicated verbatim from the previous published edition are flagged.
  4. The gate verifies against the correct fact base — `blocks` for block_v1, `input_data` for single-pass — read in-memory at the two generation save points (reusing the existing dual-fact-base wiring), never a reconstructed/wrong fact base.

**Plans**: TBD
**Notes**: Newsletter service only; no LLM (Layer 1 is deterministic and short-circuits before any model call — the token-saving core of the design). Resolves the operator's "Phase D verified against the wrong fact base" warning (GATE-08): the gate must run inline at the two generation save points where `input_data`/`blocks_data` live (unrecoverable at publish time). Extends, not replaces, the existing `verify_draft` (Phase D). Known DB fixtures for the named-study check: edition 36 ("MCP authentication"), edition 34 ("GroupMemBench"). Run report-only this phase; the consequential hold action is wired in Phase 30.

### Phase 29: Layer 2 Judge + Feedback-Rewrite Loop

**Goal**: A standalone Layer-2 eval module — a Sonnet judge that scores each draft version 1–5 across exemplar-anchored dimensions (cross-edition continuity bridge, hedging filler, clickbait/fear-hook vs professor voice, repeated sub-topics, specificity) plus a bounded N=2 feedback-rewrite loop — runs only when Layer 1 is fabrication-clean, returns the final draft + a verdict object, and never exposes loop internals or retry state to the Processor.
**Depends on**: Phase 26 (continuity context + exemplars), Phase 27 (`edition_evals` table + governed agent), Phase 28 (Layer 1 short-circuits before any Layer-2 LLM call — build + prove Layer 1 first)
**Requirements**: JUDGE-01, JUDGE-02, JUDGE-03, JUDGE-04, JUDGE-05, LOOP-01, LOOP-02, LOOP-03, LOOP-04, LOOP-05
**Success Criteria** (what must be TRUE):

  1. Layer 2 runs only when Layer 1 found no fabrication (fabrication short-circuits before any LLM call, saving tokens).
  2. A Sonnet judge (via `llm-proxy:8200`, `claude-sonnet-4-6`) scores each version 1–5 per dimension, each anchored by a concrete before/after exemplar; cross-edition continuity scores **1** if the lead lacks an explicit, accurate bridge to a prior edition (judge given the last 3 editions' angles); the remaining dimensions (hedging, clickbait/professor-voice, repeated sub-topics, specificity) are exemplar-anchored.
  3. A judge response missing the required quoted evidence / before-after exemplars is rejected (schema-validated, one retry, then `eval_status='error'`); a verdict is computed from per-dimension, config-tunable pass thresholds.
  4. On any dimension failing threshold the writer is re-called with structured, specific feedback (which dimensions failed + the judge's specific reason + the exemplar of the fix); mechanical-only Layer-1 flags may enter the loop, fabrication flags **never** do.
  5. The rewrite is re-evaluated; the loop terminates hard at **N=2 attempts max** (no best-effort publish); every attempt's per-dimension scores + feedback are logged to `edition_evals` (attempt-2-not-beating-attempt-1 surfaced); the module returns the final draft + verdict with no retry state living outside it.

**Plans**: TBD
**Notes**: Newsletter service only; standalone eval-phase module the sequencer calls (the sequencer passes draft + fact base, the module runs the loop internally). All LLM via the proxy on the governed `edition_eval` agent. Judge + loop are tightly coupled (the loop re-evals via the judge) → one phase. Thresholds are config-tunable under `agentpulse-config.json → edition_eval` (operator confirms/tunes at the plan gate; proposed defaults in REQUIREMENTS.md). Reference `docs/audit/specs/01_eval_harness.md`.

### Phase 30: Sequencer Wiring, Hold Action & Activation Gate

**Goal**: The `newsletter_poller` sequencer invokes the deterministic gate, then the Layer-2 module, at the two generation save points and acts on the returned verdicts — fabrication → `status='held'` + `do_not_publish=true` + reason + Gato notify (rewrite loop NOT entered); Layer-2 fail after N → real held + Gato escalation; pass → unchanged human gate (never auto-publish) — all behind a report-only `enforce` flag the operator explicitly flips, with the Processor staying a dumb sequencer (no LLM, no retry/rewrite state) and the whole step rollback-safe.
**Depends on**: Phase 28 (Layer 1 gate), Phase 29 (Layer 2 module)
**Requirements**: WIRE-01, WIRE-02, WIRE-03, WIRE-04, WIRE-05, WIRE-06
**Success Criteria** (what must be TRUE):

  1. The eval is invoked from the `newsletter_poller` sequencer at both save points (single-pass save return + block_v1 insert); an eval failure does not fail the generation task (wrapped — write the error row + continue).
  2. Any fabrication flag → the newsletter row is set `status='held'` with `do_not_publish=true` and a detailed `do_not_publish_reason`, the operator is notified via Gato, and the rewrite loop is not entered.
  3. A Layer-2 fail after N attempts → real `held` + Gato escalation with the final per-dimension scores + feedback; a `pass` verdict does NOT auto-publish (the edition proceeds to the unchanged Monday human review gate).
  4. The Processor contains no LLM calls and no retry/rewrite state — both layers live in the newsletter service, called by the sequencer; the Processor only triggers generation, owns the publish gate, and surfaces eval verdicts via a plain select.
  5. Automated holds are gated by a config `enforce` flag (default `false` / report-only) the operator explicitly flips to `true`; the whole step is rollback-safe (`enabled:false` disables invocation; tables/agent rows may remain).

**Plans**: TBD
**Notes**: The invasive phase — wires the gate + module into the live generation path and the held mechanism. `do_not_publish`/`do_not_publish_reason` on a *main* edition is net-new (today `do_not_publish` lives only inside `data_snapshot`; `held` is set by hand). Activation discipline: report-only for the first ~2 editions to calibrate thresholds against real drafts, then the operator flips `enforce:true`. Honors "Processor stays a dumb sequencer" (WIRE-05) — no LLM/retry state leaks into the Processor. Reference `docs/audit/specs/01_eval_harness.md` for the wiring points.

### Phase 31: Surfacing & Escalation

**Goal**: Operator-facing eval surfacing and escalation — hold/escalation alerts via a hardened `send_telegram` (never a silent no-op), a compact per-draft eval summary in the Friday newsletter notify (plain select, no Processor LLM), and a live `/newsletter_eval` (+ `trend`) Gato command wired into the `isGatoBrainCommand` allowlist so it is not a dead command.
**Depends on**: Phase 30 (the held mechanism + verdicts must exist to surface and escalate them); reads `edition_evals` from Phase 27
**Requirements**: SURF-01, SURF-02, SURF-03
**Success Criteria** (what must be TRUE):

  1. Hold/escalation notifications reuse `send_telegram`, hardened so a held edition never silently fails to alert (assert/log when `TELEGRAM_BOT_TOKEN`/`TELEGRAM_OWNER_ID` are unset; loud on send failure, not a silent no-op).
  2. The Friday newsletter notify includes a compact per-draft eval summary (verdict + headline metrics) read from `edition_evals` via a plain select (no LLM in the Processor).
  3. `/newsletter_eval` renders the current edition's eval (per-dimension scores + before/after voice exemplars) and `/newsletter_eval trend` renders recent editions' verdicts; the command is added to `isGatoBrainCommand` in `inject-gato-brain.mjs` (+ gato rebuild) so it isn't a dead command.

**Plans**: TBD
**Notes**: Worktree-unsafe — the `/newsletter_eval` command needs the `inject-gato-brain.mjs` allowlist edit + a gato rebuild (and a gato_brain handler), both orchestrator/operator-owned on the main tree (the known OpenClaw command-forwarding allowlist landmine: a gato_brain handler is dead over Telegram until allowlisted + gato rebuilt). The Friday-notify summary (SURF-02) is a plain select in the Processor — no LLM, honoring WIRE-05. `send_telegram` hardening (SURF-01) closes the fail-soft gap (today it silently `return`s when env vars are unset).

## Progress

**Execution Order:** Phases execute in numeric order: 26 → 27 → 28 → 29 → 30 → 31

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. Render-Stack Diagnostic | v1.0 | 1/1 | Complete | 2026-05-26 |
| 2. economy_map Schema + Seed | v1.0 | 2/2 | Complete | 2026-05-27 |
| 3. Design Tokens | v1.0 | 3/3 | Complete | 2026-05-27 |
| 4. Hub/Block/Status Renderer | v1.0 | 6/6 | Complete | 2026-05-28 |
| 4.1. Prod Reconciliation + Governance | v1.0 | 3/3 | Complete | 2026-05-28 |
| 5. Intake Classifier | v1.0 | 3/3 | Complete | 2026-05-28 |
| 6. Telegram Read-Only Scaffolding | v1.0 | 2/2 | Complete | 2026-05-30 |
| 7. Synthesis Loop Core | v1.0 | 2/2 | Complete | 2026-06-01 |
| 8. Validation Sentinels | v1.0 | 2/2 | Complete | 2026-06-02 |
| 9. Gated Publishing + Approval | v1.0 | 2/2 | Complete | 2026-06-03 |
| 10. Operator Write Commands | v1.0 | 3/3 | Complete | 2026-06-04 |
| 11. Design System + Nav Shell | v2.0 | 2/2 | Complete | 2026-06-04 |
| 12. Newsletter Section Restyle | v2.0 | 2/2 | Complete | 2026-06-04 |
| 13. Agent Economy Grid | v2.0 | 2/2 | Complete | 2026-06-05 |
| 14. About Stub + Polish Pass | v2.0 | 2/2 | Complete | 2026-06-08 |
| 15. Inventory & Roster Reconciliation | v2.1 | 2/2 | Complete | 2026-06-08 |
| 16. Content Load (unpublished) | v2.1 | 3/3 | Complete | 2026-06-08 |
| 17. Cross-link Wiring & Preview | v2.1 | 2/2 | Complete | 2026-06-09 |
| 18. Gated Batch Publish | v2.1 | 3/3 | Complete | 2026-06-09 |
| 19. Smart-Quote / Apostrophe Corruption Fix | v2.2 | 2/2 | Complete | 2026-06-10 |
| 20. Width Tokens & Centering Foundation | v2.2 | 2/2 | Complete | 2026-06-11 |
| 21. Single-Scroll Landing + Scroll-Spy Nav | v2.2 | 2/2 | Complete | 2026-06-11 |
| 22. Per-Section Visual Fixes | v2.2 | 4/4 | Complete | 2026-06-12 |
| 23. Distinct Newsletter Excerpts | v2.2 | 2/2 | Complete | 2026-06-16 |
| 24. Signals Section | v2.2 | 3/3 | Complete | 2026-06-17 |
| 25. Responsive & Accessibility Pass | v2.2 | 2/2 | Complete | 2026-06-19 |
| 26. Continuity & Exemplar Context | v2.3 | 3/3 | Complete    | 2026-06-24 |
| 27. Eval Persistence & Governed Agent | v2.3 | 3/3 | Complete    | 2026-06-25 |
| 28. Layer 1 Deterministic Gate | v2.3 | 0/TBD | Not started | - |
| 29. Layer 2 Judge + Feedback-Rewrite Loop | v2.3 | 0/TBD | Not started | - |
| 30. Sequencer Wiring, Hold Action & Activation Gate | v2.3 | 0/TBD | Not started | - |
| 31. Surfacing & Escalation | v2.3 | 0/TBD | Not started | - |

## Backlog

Parked for a future milestone — **not scheduled, not for now**. Surfaces at next `/gsd-new-milestone` planning. Source-of-truth detail lives in `.planning/todos/pending/`.

### v2.3 future requirements (deferred this milestone)

Tracked in `.planning/REQUIREMENTS.md` → Future Requirements.

- **REV-01** — operator-edit capture (`edition_revisions` append-only table; spec 01 G-07): capture operator edits at publish as a revision trail. Additive telemetry, not core to the gate.
- **AB-01** — quantitative single-pass vs block_v1 A/B comparison surfaced as a trend.
- **TUNE-01** — per-dimension / per-pipeline threshold auto-tuning from accumulated `edition_evals` history.
- **OBS-01** — eval-trend regression alerting (audit R8 observability).

### v2.2 future requirements (deferred earlier)

Tracked in `.planning/milestones/v2.2-REQUIREMENTS.md` → Future Requirements.

- **EXCERPT-F1** — stored `summary` field on `newsletters`, emitted by the Newsletter agent at generation time (the cleaner long-term excerpt path; deferred in favor of strip-at-render — touches schema + pipeline + backfill).
- **SIGNAL-F1** — a full Signals archive page behind the "view all signals" affordance (if the capped feed proves insufficient).
- **THEME-F1** — dark-mode variant of the light palette (DARK-01, carried from v2.0).
- **THEME-F2** — richer About page with a pipeline/architecture diagram (ABOUT-02, carried from v2.0).

### Backend follow-ups (candidate: a later backend-hardening pass)

Carried forward from v1.0; out of v2.0/v2.1/v2.2 scope and not in the v2.3 eval scope.

- analyst predictions `title` expire bug (P2)
- soft-cap allow-negative hardening (P5)
- pay-endpoint 500 activation E2E — RPC root-cause fixed in migration 037 (P2)
- phase-05 intake-classifier review follow-ups WR02/04/05 (P4)
- research trigger file permissions (P4)
- migration 043 (`economy_map_hub_and_negotiation_blocks`) unapplied on live (carry-over; live migrations list jumps 042→044)
