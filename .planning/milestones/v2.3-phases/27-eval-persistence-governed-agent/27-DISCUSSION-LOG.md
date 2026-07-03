# Phase 27: Eval Persistence & Governed Agent - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-24
**Phase:** 27-eval-persistence-governed-agent
**Areas discussed:** Wallet sizing, Table shape, Persistence scope, Migration packaging

---

## Wallet sizing (GOV-02)

| Option | Description | Selected |
|--------|-------------|----------|
| 5000/weekly, 25000 balance | DDL default; ~3× worst-case headroom; weekly window matches research/newsletter; re-tune after report-only editions yield real spend | ✓ |
| 8000/weekly, 25000 balance | Higher headroom for the rewrite loop spec-01 didn't account for (~5× worst case); weaker runaway guard | |
| Defer exact number to plan gate | Lock the shape; planner computes a sats estimate from real pricing + worst-case call graph | |

**User's choice:** 5000/weekly, 25000 balance.
**Notes:** Reject-on-cap is a safe failure (402 → eval_status='error' → escalated, doesn't hold the draft). The report-only activation window (Phase 30) doubles as cap calibration — real per-edition sats data confirms/re-tunes 5000/weekly before arming.

---

## Table shape (EVAL-01)

| Option | Description | Selected |
|--------|-------------|----------|
| JSONB-only (REQUIREMENTS DDL) | Top-level identity/verdict/status/sats columns; deterministic_flags + judge_scores + model_calls JSONB; judge_feedback TEXT. Phase 31 parses JSONB in Python. Dimension set stays config-tunable; no column↔JSONB drift | ✓ |
| Add materialized headline columns | Adopt spec-01's typed columns (voice_score, continuity, tier1_count…) for SQL aggregation — but those analytics (TUNE-01/OBS-01) are deferred, and it couples schema to tunable dimension names + risks drift | |
| You decide at plan gate | Lock JSONB-only direction; planner confirms against exact Phase 31 render needs | |

**User's choice:** JSONB-only (REQUIREMENTS DDL).
**Notes:** Two fail-loud reasons drove it: config-tunable dimension set + the dual-write canonical-source hazard. Phase 31's verdict-trend uses the top-level `verdict` column; per-dimension render parses `judge_scores` JSONB. DDL fidelity locked to REQUIREMENTS.md (per-attempt rows, verdict taxonomy passed/held_fabrication/held_voice/escalated, claude-sonnet-4-6), NOT spec-01.

---

## Persistence scope (EVAL-02, EVAL-03)

### Q1 — Helper deliverable

| Option | Description | Selected |
|--------|-------------|----------|
| Ship helper + fixture test now | New docker/newsletter/edition_eval.py: write_eval_row() + reader, full fail-loud contract, deterministic fixture test (Phase 26 stub pattern) proving EVAL-01/02/03. The core both layers call | ✓ |
| Table + agent only | 045 + minted agent + proxy smoke-test only; helper lands in Phase 28 with its first caller. Leaner, but EVAL-02/03 verified later | |

**User's choice:** Ship helper + fixture test now.

### Q2 — EVAL-02 "Telegram-alert on write failure" (newsletter service has no telegram path)

| Option | Description | Selected |
|--------|-------------|----------|
| Loud-log + raise now; Telegram in 30/31 | Helper guarantees the structural half (log ERROR + raise, never swallowed, no bare except). Telegram delivery wired where the sequencer + hardened send_telegram live (Phase 30/31). No duplicated telegram path | ✓ |
| Build a minimal newsletter→Telegram alert now | Direct Bot-API httpx alert in the newsletter container (needs env passthrough); satisfies EVAL-02 literally but forks the send_telegram SURF-01 exists to harden | |

**User's choice:** Loud-log + raise now; Telegram in 30/31.
**Notes:** Noted explicitly so EVAL-02 is not falsely marked "done" — the loud-not-swallowed half is Phase 27; the Telegram-delivery half is Phase 30 (sequencer wrap) + Phase 31 (SURF-01 hardens send_telegram, which lives in the Processor).

---

## Migration packaging & key-mint sequencing (GOV-01, GOV-02)

| Option | Description | Selected |
|--------|-------------|----------|
| One sectioned, idempotent file | 045_edition_evals.sql, 034-style: SECTION 1 table (guarded CREATE + CHECK/UNIQUE/index), SECTION 2 agent seed (ON CONFLICT DO UPDATE, 029 pattern). Mint key first → substitute real hash → MCP-apply → verify via settled proxy call | ✓ |
| Split: table migration + separate seed | Pure table DDL committed + applied independently; seed run after mint. Matches spec-01's literal order but fragments "migration 045" | |
| You decide at plan gate | Lock the sequencing invariant; planner picks file layout + confirms the mint mechanic | |

**User's choice:** One sectioned, idempotent file.
**Notes:** Commit the real bcrypt hash (029 precedent — the file is the audit record of the live key-hash). Key-mint is worktree-unsafe/orchestrator-owned. Verify via a settled proxy call as edition_eval, not container-up. The cap_or_uncapped CHECK (034) is satisfied (cap=5000>0).

---

## Claude's Discretion

- Reader helper signature/return shape (by newsletter_id; trend reader by edition_number DESC, pipeline_version) — `.eq()`-only.
- `write_eval_row()` parameter surface — takes the column contract, not the layers' internal flag/score shapes.
- Guarded table DDL style (`CREATE TABLE IF NOT EXISTS` vs `DO $$ … duplicate_object`) — re-apply must be safe.
- Exact key-mint command / how 029's bcrypt hash was generated — researcher confirms the proxy `ap_<agent>_<hash>` mechanic.
- Eval-agent proxy-identity wiring mechanism (env-read vs second `agent_api_keys` lookup) — identity SEPARATION (own LLM_PROXY_EVAL_KEY, not the newsletter key) is locked; the mechanism is the planner's call.

## Deferred Ideas

- Materialized analytics columns / SQL aggregation → TUNE-01 / OBS-01 (already-deferred future requirements).
- `edition_revisions` operator-edit-capture table → REV-01 (already deferred; not in 045).
- Reviewed-not-folded todos: P1 single-pass writer empty-response bug (0.9, separate debug task), soft-cap allow-negative hardening (0.6, concerns the other 5 agents), + 2 unrelated keyword matches.
