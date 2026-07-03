---
phase: 27-eval-persistence-governed-agent
plan: 03
subsystem: infra
tags: [supabase, migration, llm-proxy, governance, agent-wallet, bcrypt, key-mint, edition_evals, mcp-apply]

# Dependency graph
requires:
  - phase: 27-eval-persistence-governed-agent
    plan: 01
    provides: "the authored migration 045_edition_evals.sql (SECTION 1 table DDL + SECTION 2 governed agent seed with the <bcrypt-hash> placeholder) — the substitution + apply target"
provides:
  - "live edition_evals table in Supabase (project zxzaaqfowtqvmsbitqpu) with the verdict-iff-ok CHECK, UNIQUE(newsletter_id,layer,attempt), and idx_edition_evals_trend"
  - "live governed edition_eval proxy agent (agent_registry + agent_wallets_v2) — hard-capped reject-on-cap wallet (5000/weekly, allow_negative=false, balance 25000)"
  - "LLM_PROXY_EVAL_KEY plaintext in gitignored config/.env (eval agent's own identity, D-15) + its committed bcrypt-hash audit record in migration 045"
  - "a proven settled governed cycle: a real proxy call as edition_eval debits the capped wallet and writes a wallet_transactions llm_call row"
affects: [phase-28-deterministic-eval, phase-29-judge-eval, phase-30, phase-31]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "mint-first → substitute-hash → deliver-to-.env → MCP-apply → settled-call-proof (D-12/D-13/D-14)"
    - "committed bcrypt hash as the audit record of a live internal proxy key (029 precedent)"

key-files:
  created: []
  modified:
    - "supabase/migrations/045_edition_evals.sql (real $2b$12$ bcrypt hash substituted for the placeholder)"
    - "config/.env (LLM_PROXY_EVAL_KEY appended — gitignored, plaintext never committed)"

key-decisions:
  - "Verified a SETTLED governed cycle (wallet debit + llm_call ledger row), not container-up (D-14)"
  - "Applied ONLY migration 045 via the Supabase MCP tool (not db push); 043 carry-over left out of scope"
  - "Used deepseek-chat (a seeded allowed_model) for the minimal proof call — cheapest, 1 sat spent"

patterns-established:
  - "Governed eval agent: all eval LLM calls run under LLM_PROXY_EVAL_KEY identity, NOT the newsletter key (D-15)"
  - "Reject-on-cap is a SAFE failure (proxy 402 → eval_status='error' → escalated), never a silent pass (D-02)"

requirements-advanced: [EVAL-01, GOV-01, GOV-02]
---

## Plan 27-03 — Realize the table + governed agent LIVE

`autonomous: false` — three blocking `checkpoint:human-action` tasks, all worktree-unsafe and
orchestrator/operator-owned on the main tree. Executed by the orchestrator directly (not a worktree
subagent), with explicit operator approval before the consequential live actions (migration apply +
real spend).

### What shipped

**Task 1 — key mint + hash substitution + .env delivery (committed `d0572b1`)**
- Minted a new proxy key for agent `edition_eval` in the `ap_edition_eval_<hex>` scheme (matching the
  five existing agent keys).
- Computed its `bcrypt.hashpw(..., gensalt(rounds=12))` → `$2b$12$…` hash (the form `proxy.py`
  `authenticate_agent` validates via `bcrypt.checkpw`) and substituted it for the literal
  `<bcrypt-hash>` placeholder in SECTION 2 of `045_edition_evals.sql`. The committed hash is the audit
  record of the live key (D-13, 029 precedent).
- Appended `LLM_PROXY_EVAL_KEY=<plaintext>` to gitignored `config/.env`. The plaintext is **absent**
  from the migration file (only its hash), absent from `docker/docker-compose.yml` (GOV-02 "never in
  compose"; the newsletter container reads it via the existing `env_file`), and never logged.

**Task 2 — MCP-apply migration 045 to live Supabase (project `zxzaaqfowtqvmsbitqpu`)**
- Read-only pre-flight confirmed prerequisites: `newsletters` FK target exists, the migration-034
  governance columns are present (6/6), `edition_evals` did not yet exist, no pre-existing
  `edition_eval` agent row — a clean idempotent apply.
- Applied via the Supabase MCP tool `apply_migration` (name `045_edition_evals`) — **not** `db push`,
  and **not** the unapplied 043 carry-over.
- Post-apply confirmation queries (all passed):
  - `edition_evals` exists with `edition_evals_verdict_iff_ok` CHECK, the UNIQUE(newsletter_id,layer,attempt)
    constraint, and `idx_edition_evals_trend`.
  - `agent_registry.edition_eval`: `is_active=true`, `allowed_models=[deepseek-chat, claude-sonnet-4-6]`,
    `access_tier=internal`, api_key_hash is a `$2b$12$` bcrypt hash.
  - `agent_wallets_v2.edition_eval`: `allow_negative=false`, `spending_cap_sats=5000`,
    `spending_cap_window='weekly'`, `uncapped=false`, `on_cap_behavior='reject'`, `balance_sats=25000`
    (cap_or_uncapped CHECK satisfied since 5000>0).

**Task 3 — settled proxy-call proof (governed cycle, not container-up — D-14)**
- One minimal real call through `llm-proxy:8200` (`POST /v1/chat/completions`, `model=deepseek-chat`,
  `max_tokens=1`) authenticating as `edition_eval` with the plaintext key.
- Result: **HTTP 200** (no 401 auth error, no 402 cap error), valid completion returned.
- Settlement confirmed: `agent_wallets_v2.balance_sats` = **24999** (strictly < 25000), and a
  `wallet_transactions` row for `edition_eval` with `transaction_type='llm_call'`, `amount_sats=1`
  (positive spend), `metadata.model='deepseek-chat'` (a seeded allowed_model — no allowlist rejection).

### Verification

| Gate | Result |
|------|--------|
| Task 1 automated gate (placeholder gone, `$2b$` present, key in .env, .env gitignored, key absent from compose) | PASS |
| Plaintext-leak check (key absent from migration + compose) | PASS |
| Task 2 MCP queries (table + CHECK + UNIQUE + index + agent + wallet GOV-02 values) | PASS |
| Task 3 settled call (200, balance < 25000, wallet_transactions llm_call row, allowed model) | PASS |
| Phase regression: `pytest tests/test_27_edition_eval.py` still green against its stub | PASS (9 passed) |

### Deviations / notes

- **Transaction ledger table**: the plan's acceptance criterion named "agent_transactions"; the proxy
  actually records LLM spend in `wallet_transactions` (`transaction_type='llm_call'`, batched async
  flush). The settle proof is satisfied there. `agent_transactions` is the inter-agent payment ledger,
  not the LLM-spend ledger.
- The `wallet_transactions.balance_after_sats` snapshot (24997) differs by 2 from the final
  `balance_sats` (24999) — normal reserve→settle accounting (reserve held an estimate, settle refunded
  the difference). Both are below the 25000 start; the debit is real.
- Requirements EVAL-01 / GOV-01 / GOV-02 are now realized **live** (table + governed agent + settled
  cycle); final REQUIREMENTS.md closure is the verifier/phase-complete step.

### Self-Check: PASSED
- File `045_edition_evals.sql` has the real `$2b$12$` hash, no placeholder (committed `d0572b1`).
- `edition_evals` table + governed `edition_eval` agent confirmed live via MCP.
- Settled proxy call returned 200 and debited the capped wallet (24999 < 25000) with a `wallet_transactions` `llm_call` row.
