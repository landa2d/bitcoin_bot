---
gsd_state_version: 1.0
milestone: v2.3
milestone_name: Pre-Publish Evaluation Step
status: completed
stopped_at: Phase 30 COMPLETE (verified passed) — eval ARMED report-only 2026-07-02 (enabled=true/enforce=false, operator-directed); calibration window ~2 editions, then operator flips enforce=true. Next Phase 31 (SURF).
last_updated: "2026-07-02T19:18:18.332Z"
last_activity: 2026-07-02
progress:
  total_phases: 6
  completed_phases: 5
  total_plans: 16
  completed_plans: 16
  percent: 83
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-22 — Current Milestone: v2.3 Pre-Publish Evaluation Step)

**Core value:** Synthesis with editorial integrity — autonomous ingestion accelerates output, but every consequential publication is gated by human approval. Silence and homogenization are the failure modes to design against.
**Current focus:** Phase 30 COMPLETE + eval LIVE in report-only mode (`enabled=true`/`enforce=false`, armed 2026-07-02 operator-directed). Calibration window: observe ~2 editions' `edition_evals` verdicts, then operator flips `enforce=true` (30-04 Task 6). Next: Phase 31 — Surfacing & Escalation.

## Current Position

Phase: 31
Plan: Not started
Status: Ready to plan (Phase 30 complete, verification passed)
Last activity: 2026-07-02

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

- [Phase 27]: Phase 27 Plan 01: authored migration 045 (edition_evals DDL SECTION 1 + governed edition_eval agent seed SECTION 2) as ONE sectioned idempotent SQL file; table DDL verbatim from REQUIREMENTS.md (JSONB-only, no spec-01 materialized columns, D-04/D-07); agent api_key_hash left as the literal placeholder for orchestrator substitution + MCP apply in 27-03 (D-12/D-13).
- [Phase 27]: EVAL-01/GOV-01/GOV-02 left Pending after 27-01: this plan only AUTHORS SQL text; live realization (MCP apply + edition_eval key mint to config/.env LLM_PROXY_EVAL_KEY) is orchestrator-owned in 27-03, so requirement closure is deferred to phase end (fail-loud accuracy over premature mark-complete).
- [Phase 27]: Phase 27 Plan 02: shipped `docker/newsletter/edition_eval.py` (`write_eval_row` + `read_evals_by_newsletter` + `read_eval_trend` + `LLM_PROXY_EVAL_KEY` identity getter — NO LLM call) and `tests/test_27_edition_eval.py` (9 deterministic fixture cases vs an in-memory Supabase stub). EVAL-02 structural half + EVAL-03 realized in CODE: verdict-iff-ok validated in Python BEFORE insert (mirror of the DB CHECK), errored evals write `eval_status='error'`+reason+NULL verdict (never a silent zero), insert failure logs ERROR `exc_info=True`+re-raises (never swallowed), `.eq()`-only reads (no in-list filter). NO caller wired into `newsletter_poller.py` (D-08 — first real caller is Phase 28). EVAL-02 left Pending (its Telegram-delivery half is Phase 30/31, D-10); EVAL-03 left Pending to close with the phase after 27-03 (consistent with the 27-01 fail-loud-accuracy posture).
- [Phase 28]: Plan 01: shipped docker/newsletter/deterministic_gate.py (run_deterministic_gate emit-only orchestrator + arXiv-membership GATE-04 + entity-merge per-source GATE-05, reusing verify_draft per D-04) + tests/test_28_deterministic_gate.py (14 GATE-01/04/05/08 cases vs the REAL module). Flags contract {fabrication,unverified,mechanical,meta} locked (migration 045 shape; unverified first-class D-01, emit-only D-05). GATE-01/04/05/08 closure deferred to phase end (build-only/report-only; runs-on-every-edition short-circuit is Phase 30) per the 27-01/27-02 fail-loud-accuracy posture.
- [Phase 28]: Plan 02: shipped the GATE-02/03 network-liveness layer in deterministic_gate.py (GitHub /repos repo+star classifier + URL HEAD classifier) implementing the locked D-01 three-outcome taxonomy (404/410->fabricated, transient 5xx/quota-403/timeout->first-class unverified, 200->verified), D-02 retry-once-on-transient (never on 404), D-03 per-run dedup cache shared across both layers; +13 GitHub/URL/SSRF tests vs an injected fake httpx client (no live egress). GATE-02/03 closure deferred to phase end (build-only/report-only; live poller wiring is Phase 30) per the 27/28-01 fail-loud-accuracy posture.
- [Phase 28]: Plan 02: SSRF guard _is_safe_public_url (security-critical) rejects non-http(s) schemes + loopback/RFC-1918/link-local(incl 169.254.169.254 metadata)/unique-local IPs + the compose internal-service denylist + *.internal, routing unsafe URLs to unverified(reason=unsafe_host) with ZERO fetch (call-counter asserted); GITHUB_TOKEN read from env/param, sent only to api.github.com over HTTPS, never logged/in flags (meta.github_token_present is a bool); the network layer runs ONLY when an http_client is injected (no default client) to preserve the Plan-01 zero-egress contract.
- [Phase 28]: Plan 03: shipped GATE-06 (single-hash `# ` H1 detection + version-appropriate title-echo + reading-mode-label leak via the tunable READING_MODE_LABELS blacklist; bare "impact"/"Technical" deliberately NOT blacklisted to avoid prose false positives) and GATE-07 (D-06 normalized-exact recycled-closer + per-token duplicated-stat vs the FULL prior edition, reusing the imported `_STATISTIC` regex — no new number regex; `prior_edition=None`/empty is a clean skip, never raises) in deterministic_gate.py. Mechanical flags land under `mechanical`, never `fabrication` (editorial miss, never a hard hold). READING_MODE_LABELS comment notes Phase 30 report-only tunability (open question A1).
- [Phase 28]: Plan 03: golden-draft integration suite proves GATE-01..08 + D-01 end-to-end against the historical worst offenders (ed-36 MCP-auth study, ed-34 GroupMemBench, fake arXiv, 404 github repo, dead URL, transient-5xx->unverified, recycled closer, duplicated stat, leaked AUDIENCE: label) on the REAL module with an injected fake httpx client (zero live egress); BOTH GATE-08 fact-base paths (single-pass input_data + block_v1 blocks) exercised. Aggregated flags {fabrication,unverified,mechanical,meta} — unverified NON-EMPTY + DISTINCT from fabrication (D-01 "an error is not evidence"), top-level keys EXACTLY the four (fits migration 045 deterministic_flags JSONB; JSON round-trip asserted), NO verdict (emit-only D-05). test_28 56/56 green; test_26/27 regression green.
- [Phase 28]: GATE-06/07 marked complete (detection cores fully realized + proven by tests on the real module). GATE-01..05/08 detection is proven by the golden suite but their runs-on-every-edition / live-egress / hold-action closure is Phase 30 wiring (report-only/build-only this phase, D-05) — phase-end verification reconciles the remaining GATE requirements (consistent with the 27/28-01/02 fail-loud-accuracy posture).
- [Phase 29]: Plan 01: shipped docker/newsletter/judge_loop.py (PURE run_layer2 module — fail-loud entry guard JUDGE-01, _merged_config over DEFAULT_CONFIG, DEFAULT_FILLER_BLACKLIST verbatim, _count_filler_hits, both-bodies min() threshold engine _compute_failing_dims D-04/D-05/D-08) + the 5-dim exemplar-anchored Sonnet judge (both bodies ONE call D-08, parse_llm_json + schema-reject->one-retry->status='error' JUDGE-05, attempt-0 verdicts passed/escalated) + config edition_eval block (continuity_fail_below=4). tests/test_29_judge_loop.py 12 cases on the REAL module w/ OpenAI-shape _FakeLLM, zero egress; test_26/27/28 104 regression green. JUDGE-01..05 cores BUILT+PROVEN; requirement closure deferred to phase end (Plans 02/03 + verify) per the 27/28 fail-loud-accuracy posture. N=2 revise loop + held_voice/held_fabrication are Plan 02 (documented NotImplementedError seam).
- [Phase 29]: Plan 02: shipped the bounded N=2 feedback-rewrite loop in judge_loop.py — _revise_draft (targeted both-body revise via _llm_call + _fact_base_source_texts guardrail, D-07/D-08, NOT a full writer re-run), _build_feedback (structured per-dim feedback + explicit continuity bridge D-06 + mechanical-rides-only-when-a-dim-fails D-12, fabrication never present), _select_best_attempt (D-11 fewest-fails->highest-summed->latest, attempt-0 a candidate) + the full run_layer2 loop (revise only attempt_no>0 -> at most 2 revises/3 judged; passed/escalated/held_voice; no best-effort publish LOOP-02; pure LOOP-05 4-key contract). Replaced the Plan-01 NotImplementedError seam; Plan-03 per-rewrite Layer-1 re-check (D-01/D-02/D-03) is a marked insertion point. test_29 19 passed; test_26/27/28 104 regression green. LOOP-01/02 cores BUILT+PROVEN; closure deferred to phase end.
- [Phase ?]: Phase 29 Plan 03: the per-rewrite Layer-1 re-check is gated on an injected http_client — run_deterministic_gate's verify_draft flags all-caps placeholder revise bodies (TECH/NEW/REVISED) as tier1 fabrications, so gating on a client preserves the zero-egress contract + the 19 prior tests (which inject none) AND satisfies every D-01/02/03 acceptance (all inject a fake client); production always injects a real httpx.Client so the re-check is always active live.
- [Phase ?]: Phase 29 Plan 03: _CachingHTTPClient (D-01, Open Q1 Option a) memoizes GET/HEAD on (method,url) so the Phase-28 per-call dedup cache persists across N=2 attempts; a raised delegate (timeout/connect) is NOT cached (only unverified, which never holds). held_fabrication keeps the fabrication-clean attempt-0 draft (D-02); unverified/mechanical on the re-check ride to reverify_flags telemetry only (D-03).
- [Phase ?]: Phase 29 Plan 03: _persistable_attempt strips internal failing/summed_score/draft so each attempt maps 1:1 onto the edition_eval row-write params; verdict-iff-ok proven by calling the REAL write_eval_row in-test. Requirement closure (JUDGE/LOOP) deferred to phase-end /gsd-verify-work per the 27/28/29 fail-loud-accuracy posture.
- [Phase 30]: Plan 01: authored migration 046 (first-class do_not_publish + do_not_publish_reason columns on newsletters, ADD COLUMN IF NOT EXISTS house style, SQL-first operator-apply banner, schema-only no backfill per D-13) — AUTHORED NOT APPLIED: apply is the 30-04 operator MCP runbook, so WIRE-02 stays Pending (fail-loud accuracy).
- [Phase 30]: Plan 01: guarded BOTH processor publish gates (publish_newsletter + scheduled_auto_publish_newsletter) on the do_not_publish column via in-Python .get('do_not_publish', False) — apply-order-robust belt-and-suspenders behind the status='held' exclusion (D-01/WIRE-04); auto-publish select widened to '*'; logs edition+fixed label only, never the raw reason (T-30-LOG); processor eval-ref count held at 0 (WIRE-05). WIRE-04/05 closure deferred to phase-end verify.
- [Phase 30]: Plan 02: shipped the `run_edition_eval` orchestrator + 4 helpers in newsletter_poller.py (the "dumb sequencer" body 30-03 wires in) + tests/test_30_orchestration.py (9 cases on the REAL module w/ injected fakes + in-memory Supabase stub, zero egress/DB). Sequences run_deterministic_gate → fabrication short-circuit (ZERO run_layer2, D-09) → run_layer2 → verdict; SAME injected httpx.Client to BOTH modules (D-08); GOVERNED edition_eval client via `_build_eval_llm_client`→`_get_eval_api_key` (GOV-01, NEVER the newsletter Claude client, key never logged); fail-open-but-loud — llm_client=None outage + any eval exception → eval_status='error' row + ONE `_alert_operator` + `{verdict:'escalated',ran:False}`, NEVER re-raises (D-06/D-07); persists EVERY layer/attempt via `_persistable_attempt` 1:1 respecting verdict-iff-ok (LOOP-03/D-14); held_voice reason carries per-dim NAME+SCORE+bounded judge_feedback excerpt, details carries per-dim judge_scores (WIRE-03/D-10). NO status/do_not_publish UPDATE here (action is 30-03). `_alert_operator` is the interim loud Telegram path (Phase 31 hardens via send_telegram); `_read_edition_eval_config` reads enabled/enforce (D-15). test_30 9/9 + test_27/28/29 124 regression green. WIRE-01/05/06 cores built+proven; closure DEFERRED to phase-end verify (the two-save-point wiring is 30-03; enabled/enforce not yet read at a save point) per the fail-loud-accuracy posture.
- [Phase 30]: Plan 03: wired `run_edition_eval` into BOTH generation save points in newsletter_poller.py. PRIMARY (save_newsletter, after the Phase-D block): enabled-gated invocation with ONE `httpx.Client(timeout=15.0)` threaded to both eval modules (D-08) + governed edition_eval client + GITHUB_TOKEN; verdict→action on the primary row_id — held_fabrication/held_voice flip `status='held'`+`do_not_publish`+reason ONLY under enforce=true (report-only surfaces an `[EVAL would-have-held]` alert with NO flip, D-15), passed flips nothing (Monday human gate unchanged, WIRE-04), escalated is a no-op (orchestrator already alerted, D-12); whole block fail-open (logs ERROR+continues, D-06), flip skipped when row_id is None; reason surfaced verbatim = labels/counts/dim-scores/bounded-excerpt only (T-30-LOG). BLOCK_V1 A/B (process_task): D-02 reconciliation moved do_not_publish OUT of data_snapshot to the top-level migration-046 column (one canonical home) + captured bp_row_id + ran run_edition_eval TELEMETRY-ONLY (return discarded, no flip/no alert on the always-held shadow row, D-14). Ships DORMANT (enabled=false live) — first live invocation needs LLM_PROXY_EVAL_KEY mint (27-03) + MCP-apply 045/046 (30-04). Deviation: re-derived the primary fact base from the Phase-D branch (robust to an early Phase-D exception) instead of reusing the leaked `verification_input` binding — functionally identical. WIRE-01/02/03/04/06 wired+acted-upon; closure DEFERRED to phase-end verify per the 27/28/29/30-01/30-02 fail-loud-accuracy posture. test_30 9/9 + test_27/28/29 124 regression green (133 total).

### Pending Todos

7 carried-forward backend todos in `.planning/todos/pending/` (v1.0 follow-ups — analyst/governance/intake/research/phase-review). Out of v2.3 eval scope; parked in the ROADMAP Backlog (candidate for a later backend-hardening pass).

### Blockers/Concerns

**✅ RESOLVED 2026-06-24 — P1 single-pass newsletter writer broken (Friday-edition risk).** Root cause was NOT "empty content" — it was a BRITTLE JSON extractor. The writer did `content[0].text.strip()`, stripped markdown fences ONLY when `text.startswith("\`\`\`")`, then `json.loads()`. `claude-sonnet-4-6` frames the large writer output stochastically (bare / `\`\`\`json`-fenced / occasionally prose-prefixed); any framing that wasn't bare-or-leading-fence skipped the strip and `json.loads` failed at "char 0". Refuted the "empty/non-text/multi-block" theory by inspecting 7 real responses (always ONE fully-populated text block). Fix (commit `bdb45ee`, debug `resolved/single-pass-writer-empty.md`): shared `response_text()` + `parse_llm_json()` (raw → fenced → first balanced `{...}`, string-aware; **FAIL LOUD** with logged snippet, never silent-empty) at all 3 JSON sites + the writer; deployed via scoped `newsletter` rebuild. Verified end-to-end on the real prod path: processor-built current-data task → running poller drafted **edition 103 single-pass draft** (id `f2b9537e…`, 14,255-char body) with no writer parse failure. 22 new tests + 69 regression green. Friday 2026-06-26 single-pass edition will generate. (Optional follow-up: bump `qualitative_review`/`editorial_prepass` `max_tokens=1024` — verbose 16-issue reviews truncate and trip the new non-blocking fail-loud log; pre-existing, harmless.)

Key reconciled facts (still current): the true fact base only exists in-memory at the two newsletter-service save points; `edition_evals` does not exist (design-only, migration 045); `newsletters` has no `do_not_publish` column on the main row; `send_telegram` is fail-soft today (silent `return` on unset env). Audit specs `docs/audit/specs/01_eval_harness.md` (R5) + `07_continuity_and_exemplars.md` (R4) are the implementation reference.

Carry-over advisories (non-blocking, pre-existing): service_role leak in tracked `.claude/settings.local.json` (DEF-17-01 — recommend rotation + scrub + gitignore); migration 043 unapplied on live (live list jumps 042→044). ✅ Newsletter image drift RESOLVED — the Phase 26 rebuilds ship current code incl. the Phase 19 apostrophe guard. ✅ Proxy `TIMEOUT_ANTHROPIC` raised 120→240s (was 504'ing the writer call) and deployed.

**Phase 26 Plan 01 concern — ✅ RESOLVED in Plan 03:** the processor's `setdefault` shadowing was fixed via **Option C** (operator-approved loader-authoritative merge in `process_task`), and the deeper blocker — exemplars never loaded because `data_snapshot.operator_written` is a JSON **boolean** (not the string `'true'` the CONTEXT assumed) — was fixed in `_le_is_operator_written`. Live result: 8 exemplars flow, Phase E scores. The D-12/D-13 `lead_theme` backfill (editions 25–28) + `published_at` verification (all 7) are done (operator-confirmed, via MCP; persists).

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

Last session: 2026-07-02 (/gsd-execute-phase 30 — 30-04 Tasks 1–4 EXECUTED + verified; STOPPED at Task 5 decision gate)
Stopped at: Phase 30 COMPLETE (verification passed) — eval ARMED report-only 2026-07-02
Resume file: .planning/phases/30-sequencer-wiring-hold-action-activation-gate/30-04-PLAN.md
Next: **PHASE 30 COMPLETE + EVAL LIVE (REPORT-ONLY).** All 4 plans done; verification `passed` (13/13 code must-haves + activation addendum); code review 0-critical (WR-01/WR-03/IN-01 fixed @84f639d; WR-02 deploy-ordering honored — 046 applied before the rebuild; IN-02 test deferred). Activation evidence (30-04-SUMMARY.md): key bcrypt-matches 045 hash + live registry; migrations 045 (2026-06-25) + 046 (2026-07-02) applied via MCP with CHECK/UNIQUE/columns confirmed live; settled governed `claude-sonnet-4-6` proxy call (wallet 25000→24998, reject-on-cap 5000/weekly); newsletter+processor rebuilt on the main tree carrying 84f639d; `edition_eval.enabled=true`/`enforce=false` flipped and verified INSIDE the running container (live ro config mount — no restart needed; rollback = enabled=false). **CALIBRATION WINDOW (open):** next generation (Fri 2026-07-03) should write 1–2 `edition_evals` rows per draft (primary + block_v1 telemetry) with NO eval-driven status flip; would-have-held alerts are report-only. After ~2 editions, review verdicts vs `edition_eval.*` thresholds → operator flips `enforce=true` (30-04 Task 6 — the ONLY remaining 30-04 item, deliberate). Follow-up (optional): IN-02 test on the enforce-gated flip; REQUIREMENTS traceability nit (deferred REV/AB/TUNE/OBS-01 IDs absent from the table — milestone-close curation). Next phase: **31 — Surfacing & Escalation** (SURF-01..03: harden send_telegram fail-loud, Friday-notify eval summary via plain select, live `/newsletter_eval` Gato command + `isGatoBrainCommand` allowlist + gato rebuild — worktree-UNSAFE steps orchestrator-owned). `/gsd-discuss-phase 31` or `/gsd-plan-phase 31`.

## Operator Next Steps

- **Phase 30 activation (30-04, when ready — worktree-UNSAFE, main tree only):** mint `LLM_PROXY_EVAL_KEY` + bcrypt-substitute into `045 §2` (the pending 27-03), MCP-apply migrations 045 + 046, verify a settled governed proxy call, scoped-rebuild `newsletter`+`processor` (AFTER 046), then flip `edition_eval.enabled=true`/`enforce=false` for a ~2-edition report-only window before arming `enforce=true`. Runbook: `.planning/phases/30-sequencer-wiring-hold-action-activation-gate/30-04-PLAN.md`. Do NOT rebuild newsletter before 046 lands (code-review WR-02).
- After activation: `/gsd-verify-work 30` to reconcile the deferred WIRE-01..06 closures and rerun phase verification to `passed`, then proceed to Phase 31 (Surfacing & Escalation).

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
| Phase 27 P01 | 10min | 2 tasks | 1 files |
| Phase 27 P02 | ~12min | 2 tasks | 2 files (edition_eval.py helper + 9-case fixture test) |
| Phase 28 P01 | 12min | 2 tasks | 2 files |
| Phase 28 P02 | 7min | 2 tasks | 2 files |
| Phase 28 P03 | ~15min | 3 tasks | 2 files (GATE-06/07 + golden integration suite; phase-closing) |
| Phase 29 P29-01 | 14min | 2 tasks | 3 files |
| Phase 29 P29-02 | 8min | 2 tasks | 2 files |
| Phase 29 P29-03 | 17min | 2 tasks | 2 files |
| Phase 30 P01 | ~8min | 2 tasks | 2 files |
| Phase 30 P02 | ~16min | 2 tasks (Task 2 TDD: test→feat) | 2 files (run_edition_eval orchestrator + co-located unit suite) |
| Phase 30 P03 | ~8min | 2 tasks | 1 files |
