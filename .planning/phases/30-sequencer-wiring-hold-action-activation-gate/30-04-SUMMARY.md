---
phase: 30-sequencer-wiring-hold-action-activation-gate
plan: 04
status: complete
completed: 2026-07-02
key-files:
  created: []
  modified:
    - config/agentpulse-config.json (edition_eval.enabled false→true; enforce stays false)
requirements: [WIRE-06]
---

# Plan 30-04 Summary — Live-Activation Runbook (executed)

The operator-owned activation runbook is EXECUTED through Task 5 (report-only arming). Tasks 1–4
were executed by a prior session on 2026-07-02 ~13:58–14:03 UTC (recorded in commit `3a2f42b`);
this session independently re-verified every acceptance criterion against the live DB and running
containers before arming Task 5. All steps ran on the MAIN TREE (no worktree). Task 6 (arm
`enforce=true`) is deliberately PENDING — post-calibration, after ~2 report-only editions.

## Task 1 — edition_eval key ✓ (verified, not re-minted)

- `LLM_PROXY_EVAL_KEY=ap_edition_eval_…` (48 chars) present in `config/.env`; gitignored
  (`git check-ignore` passes); zero occurrences in `docker-compose.yml`; never committed
  (`git log -S` empty).
- `045_edition_evals.sql` §2 carries a real bcrypt hash (no `<bcrypt-hash>` placeholder).
- **Cryptographic match:** `bcrypt.checkpw(env_key, 045_hash)` → True; live
  `agent_registry.edition_eval.api_key_hash` prefix `$2b$12$f5GdntnlKYDfQ` matches the committed 045 hash.

## Task 2 — migrations 045 + 046 applied via MCP ✓

- Live `list_migrations`: `20260625161823 045_edition_evals`, `20260702135811 046_do_not_publish_columns`.
- `edition_evals` exists with the verdict-iff-ok CHECK (2 verdict CHECK constraints) +
  `UNIQUE(newsletter_id, layer, attempt)`.
- `newsletters.do_not_publish` boolean NOT NULL DEFAULT false + `do_not_publish_reason` text — both live.
- `agent_registry` + `agent_wallets_v2` each have the `edition_eval` row: `is_active=true`,
  `allowed_models=[deepseek-chat, claude-sonnet-4-6]`, `allow_negative=false`,
  `on_cap_behavior='reject'`, `uncapped=false`, cap 5000 sats/weekly, balance 24998/25000 deposited.
- WR-02 ordering honored: 046 applied (13:58) BEFORE the rebuild (~14:03).

## Task 3 — settled governed proxy call ✓

Two settled `wallet_transactions` rows (`transaction_type='llm_call'`) for `edition_eval`:
- 2026-06-25: `deepseek-chat`, 1 sat (Phase 27 era).
- **2026-07-02 13:58:53: `claude-sonnet-4-6` via the anthropic endpoint** (the exact judge
  model + path), 1 sat, 14 in / 4 out tokens — wallet decremented 25000→24998
  (`total_spent_sats=2`). No 401/402. Governed cycle proven end-to-end with the current key.

## Task 4 — scoped rebuild newsletter + processor ✓ (main tree)

- Both containers healthy (`Up`, healthcheck passing; poller process running).
- Running images verified to carry the FULL Phase 30 code **including the review fixes
  (`84f639d`)**: newsletter `/home/openclaw/newsletter_poller.py` has `def run_edition_eval` (1)
  and `suppress_alerts` ×7; processor has `get('do_not_publish'` ×2. `LLM_PROXY_EVAL_KEY` set in
  the newsletter container env.

## Task 5 — armed REPORT-ONLY ✓ (decision: arm-report-only, operator-directed 2026-07-02)

- `config/agentpulse-config.json → edition_eval.enabled=true`, `enforce=false`.
- Config reaches the container via the read-only `../config` mount and is read at call time —
  flip verified visible INSIDE the running newsletter container with no restart.
- Pending observation (next generation, Fri 2026-07-03): 1–2 `edition_evals` rows per draft with
  `eval_status='ok'`, would-have-held alerts if any, and NO eval-driven status flip.

## Task 6 — arm enforce=true: PENDING (by design)

After ~2 report-only editions, review the `edition_evals` verdict distribution vs the config
thresholds; tune `edition_eval.*` if would-have-held calls look wrong; then flip `enforce=true`
to arm auto-hold. Rollback at any point: `enforce=false` (or `enabled=false` to go fully dormant).

## Rollback

`edition_eval.enabled=false` in `config/agentpulse-config.json` disables all invocation
immediately (live-mounted, read per call). No schema/container rollback needed.

## Self-Check: PASSED
