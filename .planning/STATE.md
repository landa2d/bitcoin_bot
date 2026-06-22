---
gsd_state_version: 1.0
milestone: v2.3
milestone_name: Pre-Publish Evaluation Step
status: executing
stopped_at: Phase 26 Plan 02 complete
last_updated: "2026-06-22T20:58:00.000Z"
last_activity: 2026-06-22 -- Phase 26 Plan 02 (deterministic fixture test for load_edition_context) complete
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 3
  completed_plans: 2
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-22 — Current Milestone: v2.3 Pre-Publish Evaluation Step)

**Core value:** Synthesis with editorial integrity — autonomous ingestion accelerates output, but every consequential publication is gated by human approval. Silence and homogenization are the failure modes to design against.
**Current focus:** Phase 26 — continuity-exemplar-context

## Current Position

Phase: 26 (continuity-exemplar-context) — EXECUTING
Plan: 3 of 3
Status: Plans 01–02 complete (loader + injection + Phase E resurrection; deterministic D-16 fixture suite — 10 passing cases against the REAL loader); Plan 03 (operator backfill + live trigger, worktree-unsafe) next
Last activity: 2026-06-22 -- Phase 26 Plan 02 complete (eb0c5dc)

## Roadmap (v2.3 — Phases 26–31)

**Milestone goal:** Insert an automated, two-layer evaluation step *between* newsletter draft generation and publish — a hard deterministic gate (fabrication/mechanical → hold+escalate, never rewrite) and an LLM-judge + bounded N=2 feedback-rewrite loop (voice/editorial) — so errors are caught (and where safe, auto-corrected) before the operator's Monday review. **Passing the eval does NOT auto-publish; the Monday human gate is unchanged.** Audit R5 (+ a new Layer-2 judge→rewrite loop) with R4 (continuity + exemplar loader) folded in as Phase 26.

| Phase | Goal | Requirements |
|-------|------|--------------|
| 26. Continuity & Exemplar Context | `load_edition_context()` feeds prior-edition angles + operator-approved exemplars to both writer paths AND the judge; fail-loud-but-not-fatal on empty; resurrects the dead Phase E voice check (audit R4, judge dependency, lowest-risk additive) | CTX-01..05 |
| 27. Eval Persistence & Governed Agent | Migration 045 `edition_evals` (per-attempt, fail-loud, `verdict-iff-ok` CHECK) + a governed `edition_eval` proxy agent (own hard-capped reject-on-cap wallet, key via `.env`). SQL-first/operator-applied; this phase first realizes the fail-loud-no-silent-zero + no-`.in_()` invariants | EVAL-01..03, GOV-01..02 |
| 28. Layer 1 Deterministic Gate | No-LLM fabrication (live GitHub repo+star, URL HEAD liveness, arXiv-ID, named-study-vs-fact-base, entity-merge) + mechanical-editorial checks (H1/title echo, mode-label leak, recycled closer, dup-stat-vs-prior) against the CORRECT in-memory fact base; short-circuits to hold+escalate on any fabrication flag with zero LLM/rewrite. Report-only this phase | GATE-01..08 |
| 29. Layer 2 Judge + Feedback-Rewrite Loop | Standalone module: Sonnet judge (`claude-sonnet-4-6` via proxy) scores 1–5 on exemplar-anchored dimensions (continuity bridge, hedging, clickbait/voice, repeated sub-topics, specificity) + bounded N=2 rewrite loop; runs only when Layer 1 is fabrication-clean; returns final draft + verdict, no retry state outside the module | JUDGE-01..05, LOOP-01..05 |
| 30. Sequencer Wiring, Hold Action & Activation Gate | `newsletter_poller` invokes gate+module at the two save points, acts on verdicts (fabrication→held+do_not_publish; Layer-2 fail→held+escalate; pass→unchanged human gate, never auto-publish) behind a report-only `enforce` flag the operator flips; Processor stays a dumb sequencer (no LLM/retry state); rollback-safe | WIRE-01..06 |
| 31. Surfacing & Escalation | Hardened `send_telegram` hold/escalation alerts (never a silent no-op) + Friday-notify per-draft eval summary (plain select, no Processor LLM) + live `/newsletter_eval` (+ `trend`) Gato command (added to `isGatoBrainCommand` + gato rebuild) | SURF-01..03 |

**Coverage:** 37/37 v2.3 requirements mapped — no orphans, no duplicates. Per-phase: CTX×5 / (EVAL×3+GOV×2) / GATE×8 / (JUDGE×5+LOOP×5) / WIRE×6 / SURF×3.

**Execution order:** 26 → 27 → 28 → 29 → 30 → 31 (low-to-high risk; additive before invasive). Phase 27 is an independent additive core (may proceed in parallel with 26) but the harness layers 28/29/30 depend on it.

**Phase nature:** Backend milestone — no `ui_phase` (no web/frontend keyword matches; Telegram command surface is not web UI). Mostly newsletter-service work at the two generation save points (`docker/newsletter/newsletter_poller.py` + new eval/loader modules). Worktree-unsafe / orchestrator-owned steps: Phase 27 (migration 045 MCP apply + `edition_eval` key mint) and Phase 31 (`inject-gato-brain.mjs` allowlist + gato rebuild). All migrations SQL-first, operator-applied via MCP.

**Standing milestone invariants (apply throughout — operator-confirmed 2026-06-22):**

- Both eval layers run in the **newsletter service** at the two generation save points (the only place the true fact base lives — `input_data` for single-pass, `blocks_data` for block_v1; gone by publish time). The `newsletter_poller` is the dumb sequencer.
- The literal **Processor stays a dumb sequencer**: triggers generation, owns the publish gate, surfaces verdicts via a plain select. **No LLM, no retry/rewrite state in the Processor.**
- All LLM via `llm-proxy:8200` (Sonnet `claude-sonnet-4-6` via `/anthropic/v1/messages`; DeepSeek via `/v1/chat/completions`). No direct provider SDK calls.
- Fail loud: NULL ≠ intent; no bare excepts; eval error → `eval_status='error'` + reason, never a silent zero. No supabase-py `.in_()`.
- SQL-first: migrations authored in-phase, applied by the operator via MCP. Scoped rebuilds use service names; worktree-unsafe steps orchestrator/operator-owned on the main tree.
- Fabrication is a HARD stop (held + escalate, never rewrite). Passing the eval NEVER auto-publishes (Monday human gate unchanged). Auto-hold gated behind a report-only `enforce` flag the operator activates.

## Accumulated Context

### Decisions

Operator decisions locked at v2.3 start (2026-06-22, in PROJECT.md → Current Milestone; reconciled against `.planning/research/INVENTORY.md`):

- **Eval runs in the newsletter service at generation time** (NOT literally in the Processor) — the only place the true fact base lives in memory (`input_data`/`blocks_data`, unrecoverable at publish time). Honors "Processor stays a dumb sequencer, no LLM/retry-state."
- **R4 (continuity + exemplar loader) folded in as Phase 26** — a hard dependency of the Layer-2 continuity/voice judge (JUDGE-03 needs prior-edition angles; JUDGE-02 needs exemplars).
- **`edition_evals` = per-attempt telemetry** (supports the rewrite loop): `(edition id/number, attempt, layer, deterministic flags jsonb, judge scores jsonb, feedback, verdict, eval_status)` with the `verdict-iff-ok` CHECK + `UNIQUE(newsletter_id, layer, attempt)`. SQL-first; next migration number = 045 (044 highest applied; 043 unapplied carry-over, out of scope).
- **Milestone command is authoritative**; audit specs 01 (R5) / 07 (R4) are the implementation reference (wiring points, `verify_draft` reuse, governed-agent seeding pattern, fail-loud rules). Sonnet model = `claude-sonnet-4-6` (spec 01's `claude-sonnet-4-20250514` is EOL).
- **Activation discipline:** report-only (`enforce:false`) for the first ~2 editions to calibrate thresholds against real drafts, then the operator explicitly flips `enforce:true`. Whole step rollback-safe (`enabled:false` disables invocation).
- **Loader contract locked by fixtures (Phase 26 Plan 02):** `tests/test_26_continuity_loader.py` (10 cases) imports the REAL `nl.load_edition_context` (no reimplementation) and asserts the AS-IMPLEMENTED 4-key contract — `previous_editions / exemplars / exemplars_status('scored'|'not_scored') / empty` — proving the three distinguishable degrade states (empty corpus / empty-operator-pool / scored) against an in-memory Supabase stub, never the live DB. The empty-corpus WARNING literal `"continuity context empty"` is asserted; `weeks_ago` is proven OMITTED on null `published_at`; `primary_theme` is proven sourced from `data_snapshot.lead_theme` (D-07), `None` when absent.

Open items to resolve in discuss/plan (do NOT decide unilaterally):

- **Eval thresholds** (JUDGE-05 / Phase 29): the per-dimension pass thresholds under `agentpulse-config.json → edition_eval` (proposed defaults in REQUIREMENTS.md — continuity hard-fail-on-absent-bridge, hedging <3 or ≥3 blacklist hits, clickbait/specificity <3, repeated-subtopics <3). Operator confirms/tunes at the Phase 29 plan gate.
- **`edition_eval` wallet sizing** (GOV-02 / Phase 27): the exact `spending_cap_sats` weekly window + starting balance (DDL proposes 5000/weekly, balance 25000). Confirm at the Phase 27 plan gate.
- **Layer-1 fabrication check tuning** (Phase 28): the GitHub star-count drift threshold (proposed >20%), the URL HEAD timeout (proposed 5s), and the named-study/arXiv match heuristic against the in-memory fact base. Known DB fixtures: edition 36 ("MCP authentication"), edition 34 ("GroupMemBench").
- **`do_not_publish` column shape** (WIRE-02 / Phase 30): `do_not_publish` + `do_not_publish_reason` on a *main* `newsletters` row is net-new (today `do_not_publish` lives only inside `data_snapshot`). Decide column-add (a small migration) vs. JSONB at the Phase 30 plan gate.

Standing v1.0 decisions still in force (PROJECT.md Key Decisions table): all LLM via `llm-proxy:8200` (no direct provider SDK); schema isolation via direct PostgREST + `Accept-Profile` (never supabase-py `.in_()`); append-only data; fail-loud governance (NULL ≠ intent, no bare excepts); sentinels flag-never-block; autonomy where cheap/reversible, human gates where expensive/silent.

### Pending Todos

7 carried-forward backend todos in `.planning/todos/pending/` (v1.0 follow-ups — analyst/governance/intake/research/phase-review). Out of v2.3 eval scope; parked in the ROADMAP Backlog (candidate for a later backend-hardening pass).

### Blockers/Concerns

None for v2.3 start. System map present + verified (`.planning/research/INVENTORY.md`, 3 parallel code-reading agents + live Supabase reads). Key reconciled facts: the true fact base only exists in-memory at the two newsletter-service save points; `edition_evals` does not exist (design-only, migration 045); `newsletters` has no `do_not_publish` column on the main row; `send_telegram` is fail-soft today (silent `return` on unset env). Audit specs `docs/audit/specs/01_eval_harness.md` (R5) + `07_continuity_and_exemplars.md` (R4) are the implementation reference.

Carry-over advisories (non-blocking, pre-existing): service_role leak in tracked `.claude/settings.local.json` (DEF-17-01 — recommend rotation + scrub + gitignore); migration 043 unapplied on live (live list jumps 042→044); newsletter image drift (Phase 19 commit `437cdb1`, unrebuilt) — note any v2.3 newsletter rebuild ships the corrected apostrophe guard.

**Phase 26 Plan 01 concern (for Plan 03 live D-17 + the D-12/D-13 backfill):**
- **Live exemplar-flow:** the processor pre-populates `input_data['narrative_context']` (without `exemplars`) when creating the `write_newsletter` task (`agentpulse_processor.py:5615`). The locked `setdefault` injection (CTX-04/D-14) means that upstream context wins, so the loader's `exemplars` may NOT reach the `generate_from_blocks` call sites in live operation — Phase E could stay `not_scored` despite 7 operator editions. Plan 03's live trigger MUST verify `voice_score.score > 0`; if exemplars don't flow, decide between (a) processor stops pre-populating, (b) merge exemplars into an existing narrative_context, or (c) make the newsletter loader authoritative. Implemented per the locked must-have, flagged here rather than silently worked around. (See `26-01-SUMMARY.md` → Issues Encountered.)
- **Data-hygiene backfill (D-12/D-13) outstanding:** `data_snapshot.lead_theme` on operator editions 25–28 + `published_at` non-null verification on all 7 — a worktree-unsafe Supabase MCP mutation, operator/orchestrator-owned, NOT in the code plan. Plan 03's bridge/`weeks_ago` quality depends on it.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260609-fpc | Fix duplicate block title on `#/map/<slug>` — `renderBlock` strips the body's leading `# <Title>` H1; deployed via scoped `agentpulse-web` rebuild | 2026-06-09 | 19115b2 | [260609-fpc-fix-duplicate-block-title-on-map-slug](./quick/260609-fpc-fix-duplicate-block-title-on-map-slug/) |
| 260609-ivq | Map page rendering fixes (3): prose rhythm, hub duplicate-title de-dup, maturity-pill/nav overlap. Deployed via scoped `agentpulse-web` rebuild | 2026-06-09 | 9e350f3 | [260609-ivq-map-page-rendering-fixes-hub-duplicate-t](./quick/260609-ivq-map-page-rendering-fixes-hub-duplicate-t/) |
| 260612-kh9 | Proxy governance wiring (audit spec 02 / R1): x-proxy-env compose anchor, processor OPENAI_BASE_URL → proxy, direct-SDK fallbacks deleted, require_env guards, ap_ keys compose→.env. 7 services rebuilt healthy | 2026-06-12 | 1fd56ca | [260612-kh9-implement-audit-spec-02-proxy-governance](./quick/260612-kh9-implement-audit-spec-02-proxy-governance/) |
| 260619-i3k | Tab gutter + detail-route width (2 live-site defects): `.content-area` block-only padding restores the gutter; detail routes widened to `.content-area wide`. Deployed via scoped `agentpulse-web` rebuild | 2026-06-19 | abeaa43,8e0dd6d | [260619-i3k-fix-tab-gutter-and-detail-width](./quick/260619-i3k-fix-tab-gutter-and-detail-width/) |
| 260619-ko8 | Swap EOL Claude model `claude-sonnet-4-20250514` → `claude-sonnet-4-6` (31 refs / 10 files incl. governance `allowed_models`+`downgrade_map`); scoped rebuild of newsletter/research/processor/gato_brain/llm-proxy; re-queued + verified edition #102 draft via two settled `claude-sonnet-4-6` calls | 2026-06-19 | 267a6a5 | [260619-ko8-swap-eol-claude-model-claude-sonnet-4-20](./quick/260619-ko8-swap-eol-claude-model-claude-sonnet-4-20/) |

## Deferred Items

Items acknowledged and carried forward:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| v2.3 future — Edit capture | `edition_revisions` append-only operator-edit trail (REV-01, spec 01 G-07) | Deferred — additive telemetry, not core to the gate | 2026-06-22 |
| v2.3 future — A/B | Quantitative single-pass vs block_v1 A/B comparison as a trend (AB-01) | Deferred — eval runs on both paths; comparison is a later surface | 2026-06-22 |
| v2.3 future — Tuning | Per-dimension/per-pipeline threshold auto-tuning from `edition_evals` history (TUNE-01) | Deferred — ship fixed config thresholds first | 2026-06-22 |
| v2.3 future — Observability | Eval-trend regression alerting (OBS-01, audit R8) | Deferred — surface verdicts first, alert on trends later | 2026-06-22 |
| v2.2 future — Excerpts | Stored `summary` field on `newsletters` (EXCERPT-F1) | Deferred — strip-at-render shipped v2.2 | 2026-06-10 |
| v2.2 future — Signals | Full Signals archive page (SIGNAL-F1) | Deferred — capped feed shipped v2.2 | 2026-06-10 |
| v-next — Dark mode | Dark-mode variant of the light palette (THEME-F1) | Deferred — light mode shipped v2.0 | 2026-06-04 |
| v-next — Richer About | Pipeline/architecture diagram on About (THEME-F2) | Deferred — About ships as the stub + agent-grid | 2026-06-04 |
| v-next — Per-block tuning | Synthesis threshold overrides per block (TUNE-01..03, economy_map) | Deferred — kept separate from these milestones | 2026-05-26 |
| v-next — EU AI Act | Wire `eu_ai_act` tracker into regulation-legal block (EUAI-01/02) | Deferred — out of scope | 2026-05-26 |

### Backend follow-ups (candidate: a later backend-hardening pass)

Carried forward from v1.0; out of v2.0/v2.1/v2.2 scope and not in the v2.3 eval scope (detail in `.planning/todos/pending/`).

| Item | Priority |
|------|----------|
| analyst predictions `title` expire bug | P2 |
| soft-cap allow-negative hardening | P5 |
| pay-endpoint 500 activation E2E (RPC root-cause fixed m037) | P2 |
| phase-05 intake-classifier review follow-ups WR02/04/05 | P4 |
| research trigger file permissions | P4 |
| migration 043 unapplied on live (042→044 gap) | P3 |

## Session Continuity

Last session: 2026-06-22T20:58:00.000Z
Stopped at: Phase 26 Plan 02 complete (deterministic fixture suite)
Resume file: .planning/phases/26-continuity-exemplar-context/26-03-PLAN.md
Next: Execute Phase 26 Plan 03 (Wave 3) — operator-confirmed `data_snapshot.lead_theme` backfill on operator editions 25–28 + `published_at` non-null verification on all 7 (D-12/D-13, worktree-unsafe Supabase MCP) THEN the live generation trigger end-to-end verify (D-17/D-18). Plan 03's live run MUST confirm exemplars actually reach Phase E (`voice_score.score > 0`, ≥1 observation) given the upstream `narrative_context` pre-population + `setdefault` (see 26-01-SUMMARY Issues).

## Operator Next Steps

- Review the v2.3 ROADMAP (Phases 26–31) — `/gsd-plan-phase 26` to begin, or revise the roadmap if the phase shape/ordering needs adjustment.

## Performance Metrics

| Phase | Plan | Duration | Notes |
|-------|------|----------|-------|
| Phase 19 P01 | ~10min | 3 tasks | 3 files |
| Phase 19 P02 | ~5min | 3 tasks | 1 file (confirm-and-close; no DB mutation) |
| Phase 20 P01 | ~4min | 3 tasks | 4 files (width tokens + .prose/.wide axes) |
| Phase 21 P01 | ~6min | 3 tasks | 2 files |
| Phase 23 P01 | ~14min | 3 tasks | 2 files |
| Phase 24 P01 | ~3min | 1 task | 1 file (migration 044 — signals_feed view) |
| Phase 24 P02 | ~2min | 2 tasks | 3 files (frontend signals fetch/render) |
| Phase 26 P01 | 8min | 3 tasks | 2 files |
| Phase 26 P02 | ~6min | 1 task | 1 file (deterministic fixture test — 10 cases vs the REAL loader) |
