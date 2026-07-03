---
phase: 30-sequencer-wiring-hold-action-activation-gate
verified: 2026-07-01T17:30:00Z
status: passed
score: 13/13 must-haves verified (code); 30-04 activation EXECUTED 2026-07-02 (Tasks 1-5 verified live; Task 6 enforce-arming post-calibration by design)
overrides_applied: 0
human_verification:
  - test: "Mint the governed edition_eval proxy key and write LLM_PROXY_EVAL_KEY to config/.env (Phase 27-03 still pending). Substitute the real bcrypt hash into supabase/migrations/045_edition_evals.sql SECTION 2 (replace the <bcrypt-hash> placeholder)."
    expected: "045_edition_evals.sql SECTION 2 no longer contains the literal <bcrypt-hash>. `grep -q LLM_PROXY_EVAL_KEY config/.env` succeeds. The key does NOT appear in docker-compose.yml or git."
    why_human: "Key minting requires the operator to run the proxy key-mint flow and write secrets to config/.env (gitignored, not automatable)."
  - test: "MCP-apply migration 045_edition_evals.sql (after bcrypt hash substitution) and 046_do_not_publish_columns.sql to the live Supabase DB (project ref zxzaaqfowtqvmsbitqpu) via the Supabase MCP tool. Do NOT use `supabase db push`. Do NOT apply from a worktree."
    expected: "`list_tables` shows `edition_evals` with the verdict-iff-ok CHECK + UNIQUE(newsletter_id, layer, attempt). `agent_registry` + `agent_wallets_v2` each have an `edition_eval` row (allow_negative=false, on_cap_behavior='reject'). `newsletters` has `do_not_publish` (boolean NOT NULL DEFAULT false) + `do_not_publish_reason` (text) columns."
    why_human: "Schema changes to the live Supabase DB require operator action via the MCP tool after DDL review. Cannot automate without operator approval."
  - test: "Issue a minimal claude-sonnet-4-6 call through http://llm-proxy:8200/anthropic/v1/messages authenticating with LLM_PROXY_EVAL_KEY. Confirm HTTP 200 and that the call SETTLED (a wallet_transactions row for edition_eval exists and the edition_eval wallet balance decremented). If 402/cap-hit or 401, HALT and fix before proceeding."
    expected: "HTTP 200 response. A wallet_transactions row (transaction_type='llm_call') exists for edition_eval. agent_wallets_v2.edition_eval balance has decremented."
    why_human: "Requires a live proxy + minted key + applied migration 045. Cannot verify without all three live preconditions. A mis-seeded identity must not proceed to arming."
  - test: "Scoped-rebuild newsletter + processor on the MAIN TREE (/root/bitcoin_bot/docker, NOT a worktree): `cd /root/bitcoin_bot/docker && docker compose up -d --build newsletter processor`. Migration 046 must already be applied before the processor rebuild."
    expected: "`docker compose ps` shows agentpulse-newsletter + agentpulse-processor healthy. Newsletter poller process running (`pgrep -f newsletter_poller.py` passes)."
    why_human: "Requires Docker access and must run on the main tree (worktree-unsafe). Sequence dependency: 046 must be applied first."
  - test: "Flip edition_eval.enabled=true, keep enforce=false in config/agentpulse-config.json. Run the next newsletter generation. Verify 1-2 edition_evals rows appear per draft (eval_status='ok') and NO newsletter row had its status flipped to held by the eval (report-only calibration window)."
    expected: "edition_eval.enabled=true AND enforce=false in config. After next generation: edition_evals rows present, eval_status='ok', no eval-driven newsletter status change."
    why_human: "Requires a live newsletter generation cycle to produce evidence. The report-only calibration window must be observed against real drafts before arming enforce=true."
  - test: "(LATER — after ~2 report-only editions) Review accumulated edition_evals rows. Decide: flip enforce=true to arm auto-hold, or tune thresholds first. If arming: set edition_eval.enforce=true. After the next edition that trips a fabrication/voice fail: verify the primary row flips status='held' + do_not_publish=true, an [EVAL HELD] operator alert fires, and the publish gates refuse it. Verify a passed edition still reaches the normal Monday human gate with no auto-publish (WIRE-04)."
    expected: "With enforce=true: a failing edition is held+blocked; a passing edition is not auto-published. Rollback = set enforce=false."
    why_human: "Requires operator judgment on calibration data and deliberate arming decision. End-to-end live behavior (hold action + alert + publish gate refusal) cannot be verified without a live generation cycle."
---

# Phase 30: Sequencer Wiring, Hold Action & Activation Gate — Verification Report

**Phase Goal:** newsletter_poller invokes gate+module at the two save points, acts on verdicts (fabrication→held+do_not_publish; Layer-2 fail→held+escalate; pass→unchanged human gate, never auto-publish) behind a report-only `enforce` flag the operator flips; Processor stays a dumb sequencer (no LLM/retry state); rollback-safe.

**Verified:** 2026-07-01T17:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Scope Declaration

Phase 30 has four plans. Plans 30-01, 30-02, 30-03 are code plans — all complete with SUMMARYs. Plan 30-04 is `autonomous: false`, the operator-owned live-activation runbook (key mint + MCP-apply migrations 045+046 + scoped rebuild + flag flip). Plan 30-04 has no SUMMARY by design — the operator has deliberately deferred it to a dedicated activation session. All 13 code must-haves are VERIFIED below. The 30-04 activation items are classified as `human_verification` (operator-pending, not code gaps).

---

## Goal Achievement

### Observable Truths (Code Plans 30-01 / 30-02 / 30-03)

| # | Plan | Truth | Status | Evidence |
|---|------|-------|--------|----------|
| 1 | 30-01 | `newsletters` has first-class `do_not_publish` + `do_not_publish_reason` columns (migration 046) | VERIFIED | `supabase/migrations/046_do_not_publish_columns.sql` exists; `ADD COLUMN IF NOT EXISTS do_not_publish boolean NOT NULL DEFAULT false` and `ADD COLUMN IF NOT EXISTS do_not_publish_reason text` present; `COMMENT ON COLUMN` for both; operator banner present; schema-only (no DML); `ADD COLUMN IF NOT EXISTS` count == 2 (non-comment lines). |
| 2 | 30-01 | Both processor publish gates refuse to publish a row whose `do_not_publish` column is true | VERIFIED | `publish_newsletter` (line 5882) and `scheduled_auto_publish_newsletter` (line 10666) both have `if newsletter.get('do_not_publish'):` guards with early return/warning; `grep -c "get('do_not_publish'"` == 2; `scheduled_auto_publish_newsletter` selects `'*'` (ordering-agnostic). |
| 3 | 30-01 | The Processor calls no eval logic — it only reads the column and owns the publish gate | VERIFIED | `grep -c "run_layer2\|run_deterministic_gate\|run_edition_eval\|import edition_eval\|import judge_loop"` on the processor returns 0. AST parse exits 0. |
| 4 | 30-02 | `run_edition_eval` sequences Layer-1 gate then Layer-2 judge and never lets an eval error block generation | VERIFIED | Function at newsletter_poller.py:469; outer try/except catches all exceptions and RETURNS without re-raise (AST confirms 0 bare re-raises inside run_edition_eval). Inner guard on telemetry/alert failures ensures the return still executes. |
| 5 | 30-02 | Layer 2 is called with a governed `edition_eval`-identity LLM client and a real injected httpx.Client | VERIFIED | `_build_eval_llm_client()` at line 329 calls `edition_eval._get_eval_api_key()` and constructs `anthropic.Anthropic(api_key=eval_key, base_url=f"{LLM_PROXY_URL}/anthropic")`; never references `claude_client`. `run_layer2` called with `http_client=http_client` at line 530. Test `test_governed_identity_passthrough` confirms the exact injected instances reach run_layer2. |
| 6 | 30-02 | A fabrication flag short-circuits to `held_fabrication` with no Layer-2 LLM call | VERIFIED | `det.get("fabrication")` check at line 511 returns early with verdict `held_fabrication` before any `run_layer2` call. Test `test_fabrication_short_circuits_no_layer2` asserts `layer2_calls == []` — passes. |
| 7 | 30-02 | An eval outage writes an `eval_status='error'` row AND loudly alerts the operator, then returns without raising | VERIFIED | Both the `llm_client is None` path (lines 491-499) and the outer except (lines 585-603) write an error row + call `_alert_operator` + return. `_alert_operator` ERROR-logs (never a silent return) when TELEGRAM_* are unset. Test `test_llm_client_none_is_outage` and `test_layer2_exception_fails_open_no_raise` both pass. |
| 8 | 30-02 | `enabled=false` means the eval is never invoked (rollback-safe) | VERIFIED | Live `config/agentpulse-config.json` has `edition_eval.enabled=false`; both save points guard on `cfg.get('enabled', False)` (lines 2110 and 3104). `_read_edition_eval_config()` returns `{}` (enables=False default) when the block is absent. |
| 9 | 30-03 | The eval runs at the primary save point (`save_newsletter`) and the block_v1 A/B save point, only when `enabled=true` | VERIFIED | `run_edition_eval` invoked at line 2140 (primary) and line 3113 (block A/B); both gated by `cfg.get('enabled', False)`. `grep -c "run_edition_eval("` == 3 (definition + 2 call sites). |
| 10 | 30-03 | A `held_fabrication` or `held_voice` verdict on the PRIMARY draft flips `status='held'` + `do_not_publish=true` + reason ONLY when `enforce=true`; otherwise a would-have-held alert with no flip | VERIFIED | Line 2153: `if cfg.get('enforce', False):` gates the `supabase.table('newsletters').update({'status':'held','do_not_publish':True,'do_not_publish_reason':reason})` call. The `else` branch at line 2169 calls `_alert_operator("[EVAL would-have-held]...")` with no DB update. |
| 11 | 30-03 | A `passed` verdict flips nothing — the edition proceeds to the unchanged Monday human gate (no auto-publish) | VERIFIED | The verdict→action block has no UPDATE branch for `passed`; only `held_fabrication`/`held_voice` trigger the enforce branch. Comment at line 2176 explicitly notes: `# verdict == 'passed' → no flip (unchanged Monday human gate, WIRE-04)`. |
| 12 | 30-03 | The block_v1 A/B eval is telemetry-only — it writes `edition_evals` rows but never flips publish state | VERIFIED | `run_edition_eval` is called at line 3113 with its return value discarded (no assignment, no verdict→action block, no alert). The always-held `bp_row` has `status='held'` unchanged; only `bp_row_id` capture and the enabled guard precede the call. |
| 13 | 30-03 | `do_not_publish` has exactly one canonical home: the A/B row's `data_snapshot.do_not_publish` JSONB flag is moved to the top-level column | VERIFIED | `bp_row` sets `"do_not_publish": True` as a top-level key (line 3081). The `data_snapshot` dict at line 3082 contains no `do_not_publish` key — grep `data_snapshot.*do_not_publish` in newsletter_poller.py returns no matches. |

**Score:** 13/13 code truths VERIFIED

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/migrations/046_do_not_publish_columns.sql` | both columns + operator banner + schema-only | VERIFIED | 29 lines; `ADD COLUMN IF NOT EXISTS` ×2 (non-comment); `COMMENT ON COLUMN` ×2; no INSERT/UPDATE/DELETE; MCP-apply banner present |
| `docker/processor/agentpulse_processor.py` | `do_not_publish` guards in both publish gates; zero eval refs | VERIFIED | 2 `get('do_not_publish')` guards; 0 eval-module references; AST parse OK |
| `docker/newsletter/newsletter_poller.py` | `run_edition_eval` + 4 helpers + both save points wired | VERIFIED | `run_edition_eval` at line 469; `_build_eval_llm_client` at 329; `_alert_operator` at 365; `_read_edition_eval_config` at 312; `_fetch_prior_published_edition` at 400; primary call at 2140; A/B call at 3113; AST parse OK |
| `tests/test_30_orchestration.py` | 9-case unit suite over the real module; zero egress | VERIFIED | 9/9 pass (`pytest tests/test_30_orchestration.py -q`); tests fabrication short-circuit, pass/held_voice persistence, fail-open, governed identity, llm_client=None outage, and structural invariant (no .update in orchestrator) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `processor:publish_newsletter` | `newsletters.do_not_publish` | in-Python `.get('do_not_publish', False)` guard on fetched row | VERIFIED | Line 5882; early return `{'error': 'held: do_not_publish set'}` when truthy |
| `processor:scheduled_auto_publish_newsletter` | `newsletters.do_not_publish` | in-Python `.get('do_not_publish', False)` guard; `select('*')` widened | VERIFIED | Lines 10650 + 10666; `select('*')` ordering-agnostic; early return when truthy |
| `newsletter_poller.py:run_edition_eval` | `judge_loop.run_layer2` | governed `llm_client` + injected `http_client` | VERIFIED | Line 528-531: `run_layer2(draft, fact_base, prior_context, det, config, llm_client, http_client=http_client, ...)` |
| `newsletter_poller.py:_build_eval_llm_client` | `edition_eval._get_eval_api_key` | `LLM_PROXY_EVAL_KEY` governed identity | VERIFIED | Line 341: `from edition_eval import _get_eval_api_key` (lazy-import); test `test_build_eval_client_uses_governed_key_source_assert` passes |
| `newsletter_poller.py:save_newsletter` | `run_edition_eval + newsletters.status/do_not_publish` | enforce-gated UPDATE on primary `row_id` | VERIFIED | Lines 2109-2178; enforce gate at 2153; update at 2158-2162; skip when `row_id is None` |
| `newsletter_poller.py:A/B path` | `run_edition_eval` (telemetry-only) | `bp_row_id` captured from insert; return discarded | VERIFIED | Lines 3093-3121; `insert_res.data[0]['id']`; no verdict→action; no alert |
| `bp_row` | `newsletters.do_not_publish` column (canonical home) | top-level key, NOT inside `data_snapshot` | VERIFIED | Line 3081: `"do_not_publish": True` at bp_row root; grep `data_snapshot.*do_not_publish` returns 0 matches |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `test_30_orchestration.py` 9-case suite | `python3 -m pytest tests/test_30_orchestration.py -q` | 9 passed in 0.02s | PASS |
| Phase 27/28/29 regression (124 tests) | `python3 -m pytest tests/test_27_edition_eval.py tests/test_28_deterministic_gate.py tests/test_29_judge_loop.py -q` | 124 passed in 0.13s | PASS |
| Processor AST parse | `python3 -c "import ast; ast.parse(open('docker/processor/agentpulse_processor.py').read())"` | exits 0 | PASS |
| newsletter_poller AST parse | `python3 -c "import ast; ast.parse(open('docker/newsletter/newsletter_poller.py').read())"` | exits 0 | PASS |
| Processor eval-ref count | `grep -c "run_layer2\|run_deterministic_gate\|run_edition_eval\|import edition_eval\|import judge_loop" docker/processor/agentpulse_processor.py` | 0 | PASS |
| Processor `do_not_publish` guard count | `grep -c "get('do_not_publish'"` on processor | 2 | PASS |
| Migration 046 schema-only | grep non-comment DML (INSERT/UPDATE/DELETE) in 046 | 0 | PASS |
| run_edition_eval call count | `grep -c "run_edition_eval(" newsletter_poller.py` | 3 (def + 2 call sites) | PASS |
| httpx.Client injections | `grep -n "with httpx.Client(timeout=15.0)"` | 2 (line 2139 + 3112) | PASS |
| do_not_publish not in data_snapshot | `grep "data_snapshot.*do_not_publish"` | 0 matches | PASS |
| run_edition_eval no bare re-raise | AST walk for `ast.Raise(exc=None)` inside function | 0 bare re-raises | PASS |
| enforce gate present | `grep -n "get('enforce'"` in newsletter_poller | line 2153 (status flip gate) | PASS |
| enabled gate in config (ships dormant) | `grep "enabled" config/agentpulse-config.json` | `"enabled": false` | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| WIRE-01 | 30-02, 30-03 | Eval invoked at both save points; fail-open | SATISFIED | Truths 9 + 4 verified; both call sites confirmed; outer try/except never re-raises |
| WIRE-02 | 30-01, 30-03 | Fabrication → held + do_not_publish + reason | SATISFIED (code) | Truths 1, 2, 10 verified; live activation (column applied to DB) is operator-pending (30-04) |
| WIRE-03 | 30-02, 30-03 | Layer-2 fail → held + escalation with per-dim scores+feedback | SATISFIED (code) | Truth 10 + test `test_held_voice_reason_carries_scores_and_feedback` passes; held_voice reason format verified |
| WIRE-04 | 30-01, 30-03 | Pass verdict does not auto-publish | SATISFIED | Truth 11 + 2 verified; no UPDATE branch for 'passed'; publish gate guard is additive |
| WIRE-05 | 30-01, 30-02 | Processor has no eval logic | SATISFIED | Truth 3 verified; 0 eval-module references in processor |
| WIRE-06 | 30-02, 30-03, 30-04 | enforce flag (default false); enabled flag (rollback-safe); operator flips | SATISFIED (code) / operator-pending (activation) | Truths 8 + 10 verified for code; `enabled=false`/`enforce=false` in live config; 30-04 activation steps are human_verification items |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `docker/newsletter/newsletter_poller.py` | 3380, 3428 | `TBD — set via /map-tension` | INFO (pre-existing) | Unrelated to Phase 30; references the `/map-tension` command feature (pre-existing from earlier phases, not introduced by any Phase 30 commit — confirmed by `git diff` on all 4 Phase 30 commits). No blocker. |

No blockers. No Phase-30-introduced debt markers.

---

### Human Verification Required

#### 1. Mint LLM_PROXY_EVAL_KEY + bcrypt hash substitution in migration 045 (Phase 27-03 prerequisite)

**Test:** Mint `ap_edition_eval_<hash>` for the `edition_eval` agent via the proxy key-mint flow. Substitute the real bcrypt hash into `supabase/migrations/045_edition_evals.sql` SECTION 2 (replace `<bcrypt-hash>` placeholder). Write `LLM_PROXY_EVAL_KEY=ap_edition_eval_<...>` to `config/.env` (gitignored — never committed, never in docker-compose.yml).

**Expected:** `045_edition_evals.sql` contains no literal `<bcrypt-hash>`. `grep -q LLM_PROXY_EVAL_KEY config/.env` succeeds. `git check-ignore config/.env` confirms gitignored.

**Why human:** Key minting is an operator action requiring the proxy key-mint flow and secure delivery to config/.env.

---

#### 2. MCP-apply migrations 045 + 046 to the live Supabase DB

**Test:** Via the Supabase MCP tool (project ref zxzaaqfowtqvmsbitqpu), on the MAIN TREE only — NEVER `supabase db push`, NEVER from a worktree. Apply `045_edition_evals.sql` (after Task 1 bcrypt substitution), then `046_do_not_publish_columns.sql`. 046 must be applied before the processor scoped rebuild so the widened publish-gate select is column-safe.

**Expected:** `list_tables` shows `edition_evals` with verdict-iff-ok CHECK + UNIQUE(newsletter_id, layer, attempt). `agent_registry` + `agent_wallets_v2` each have an `edition_eval` row. `newsletters` has `do_not_publish` (boolean NOT NULL DEFAULT false) + `do_not_publish_reason` (text) columns.

**Why human:** Schema changes to the live Supabase DB require operator action via MCP after DDL review. Automated verification cannot reach the live DB without operator credentials.

---

#### 3. Verify a settled governed edition_eval proxy call

**Test:** From the host or newsletter container, issue one minimal `claude-sonnet-4-6` call through `http://llm-proxy:8200/anthropic/v1/messages` authenticating with `LLM_PROXY_EVAL_KEY`. Confirm HTTP 200 and SETTLED — a `wallet_transactions` row (`transaction_type='llm_call'`) for `edition_eval` and a decrement of the `agent_wallets_v2.edition_eval` balance. A 402/cap-hit or 401 → HALT and fix before proceeding.

**Expected:** HTTP 200. `wallet_transactions` row for `edition_eval`. Balance decremented.

**Why human:** Requires live proxy + minted key + applied migration 045. Cannot verify without all three live preconditions in place.

---

#### 4. Scoped-rebuild newsletter + processor containers on the MAIN TREE

**Test:** On the MAIN TREE (`/root/bitcoin_bot/docker`), operator-owned: `cd /root/bitcoin_bot/docker && docker compose up -d --build newsletter processor`. Migration 046 must already be applied (item 2) before this rebuild.

**Expected:** `docker compose ps` shows `agentpulse-newsletter` + `agentpulse-processor` healthy. Newsletter poller running (`pgrep -f newsletter_poller.py` passes).

**Why human:** Docker rebuild must run on the main tree (worktree-unsafe), requires Docker access, and has a sequencing dependency on migration 046 being applied first.

---

#### 5. Arm report-only calibration window (flip enabled=true, keep enforce=false)

**Test:** In `config/agentpulse-config.json`, set `edition_eval.enabled=true`, leave `enforce=false`. Run the next newsletter generation. Check `edition_evals` for 1-2 rows per draft with `eval_status='ok'` and verify NO newsletter row had its status flipped to `held` by the eval (report-only — zero eval-driven status changes).

**Expected:** `edition_eval.enabled=true` AND `enforce=false` in config. After next generation: `edition_evals` rows present, no eval-driven newsletter status change.

**Why human:** Requires a live newsletter generation cycle. The report-only calibration window must be observed against real drafts before arming enforce=true. Human judgment on verdict quality is needed.

---

#### 6. (LATER, after ~2 calibration editions) Arm auto-hold by flipping enforce=true

**Test:** After reviewing accumulated `edition_evals` rows and confirming verdict quality, set `edition_eval.enforce=true` in config (or tune thresholds first if verdicts look mis-calibrated). After the next edition that trips a fabrication/voice fail: verify the primary row flips `status='held'` + `do_not_publish=true`, an `[EVAL HELD]` operator alert fires, and the publish gates refuse it. Verify a passed edition still reaches the normal Monday human gate with no auto-publish.

**Expected:** With enforce=true: failing edition is held+blocked; passing edition is not auto-published. Rollback = set enforce=false.

**Why human:** Deliberate arming decision requiring operator judgment on real calibration data. End-to-end live behavior (hold action + alert + publish gate refusal) cannot be verified without a live generation cycle.

---

### Gaps Summary

No code gaps. All 13 code must-haves from Plans 30-01, 30-02, 30-03 are VERIFIED. The phase ships its CODE goal in full — the eval wiring is in place, gated dormant behind `enabled=false`, and rollback-safe.

The 6 human verification items above are the 30-04 live-activation runbook steps that the operator deliberately deferred. They are not code gaps; they are the intentional "arm it when ready" sequence per D-03/D-04 (Phase 30 delivers wiring shipped dormant — live invocation requires the operator to mint the key, apply schema, and flip the flag).


## Activation Addendum (2026-07-02, operator-directed)

The six human_verification items above were EXECUTED and verified live (see `30-04-SUMMARY.md`
for full evidence): (1) key verified — bcrypt match between config/.env key, 045 §2 hash, and the
live agent_registry hash; (2) migrations 045+046 applied via MCP (list_migrations shows both;
CHECK/UNIQUE/columns confirmed live); (3) settled governed claude-sonnet-4-6 call on 2026-07-02
(wallet 25000→24998, wallet_transactions llm_call row); (4) newsletter+processor rebuilt on the
main tree AFTER 046 (running images carry the 84f639d review fixes); (5) armed REPORT-ONLY —
`enabled=true`/`enforce=false`, flip verified inside the running container. Item (6) — flipping
`enforce=true` — is the deliberate post-calibration operator action after ~2 report-only editions
and is NOT a phase gap (WIRE-06's deliverable is the operator-flippable report-only gate, which is
live). Status upgraded human_needed → passed.


---

_Verified: 2026-07-01T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
