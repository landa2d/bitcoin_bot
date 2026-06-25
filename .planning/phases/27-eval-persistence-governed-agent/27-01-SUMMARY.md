---
phase: 27-eval-persistence-governed-agent
plan: 01
subsystem: database
tags: [supabase, postgres, migration, llm-proxy, governance, agent-wallet, edition_evals]

# Dependency graph
requires:
  - phase: 26-continuity-exemplar-context
    provides: "the continuity/exemplar loader whose Phase-29 judge will write through this table (no hard dependency; independent additive core)"
provides:
  - "supabase/migrations/045_edition_evals.sql — authored (NOT applied): SECTION 1 edition_evals DDL + SECTION 2 governed edition_eval agent seed"
  - "edition_evals table shape (JSONB-only, verdict-iff-ok CHECK, UNIQUE(newsletter_id, layer, attempt), idx_edition_evals_trend) — the persistence surface Phases 28/29 write through"
  - "governed edition_eval agent_registry + agent_wallets_v2 seed (hard-capped 5000/weekly, reject-on-cap, claude-sonnet-4-6) with the <bcrypt-hash> placeholder pending orchestrator substitution in 27-03"
affects: [27-02 (edition_eval.py persistence helper targets this table shape), 27-03 (orchestrator substitutes the real hash + MCP-applies this file + mints LLM_PROXY_EVAL_KEY), 28 (deterministic gate writes rows), 29 (judge writes rows + calls proxy as edition_eval), 31 (trend reader / Friday-notify select)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Sectioned idempotent migration (034 banner style): SECTION 1 CREATE TABLE IF NOT EXISTS + inline CHECK/UNIQUE; SECTION 2 INSERT ... ON CONFLICT (agent_name) DO UPDATE (029 seed pattern)"
    - "Structural fail-loud: a silent-zero / verdict-without-eval row is UNREPRESENTABLE via the edition_evals_verdict_iff_ok CHECK"
    - "Committed-bcrypt-hash agent seed with an unsubstituted <bcrypt-hash> placeholder until orchestrator key-mint (029 precedent, D-12/D-13)"

key-files:
  created:
    - "supabase/migrations/045_edition_evals.sql"
  modified: []

key-decisions:
  - "Authored migration 045 as ONE sectioned idempotent file (D-11); table DDL verbatim from REQUIREMENTS.md — JSONB-only, no spec-01 materialized columns (D-04/D-07)"
  - "api_key_hash left as the literal <bcrypt-hash> placeholder — orchestrator mints the key + substitutes the real hash + MCP-applies in 27-03 (D-12/D-13); no hash invented here"
  - "EVAL-01/GOV-01/GOV-02 NOT marked complete — this plan only AUTHORS SQL; live realization is orchestrator-owned in 27-03, so requirement closure is deferred to phase end (fail-loud accuracy over premature mark-complete)"

patterns-established:
  - "edition_evals row contract: per-draft per-layer per-attempt telemetry; eval error => eval_status='error' + reason + NULL verdict (never a silent zero)"
  - "governed 6th capped agent (edition_eval) joins analyst/processor/research/newsletter/gato as reject-on-cap; spending_cap_sats=5000>0 satisfies the migration-034 cap_or_uncapped CHECK"

requirements-completed: []  # EVAL-01/GOV-01/GOV-02 ADVANCED (SQL authored) but left Pending — closed at phase end after the 27-03 MCP apply + key mint. EVAL-02/EVAL-03 are plan 27-02 scope.

# Metrics
duration: ~6min
completed: 2026-06-25
---

# Phase 27 Plan 01: Eval Persistence & Governed Agent (Migration 045) Summary

**Authored `supabase/migrations/045_edition_evals.sql` — a sectioned, idempotent, SQL-first migration: SECTION 1 the JSONB-only `edition_evals` per-attempt telemetry table with the fail-loud `verdict-iff-ok` CHECK + `UNIQUE(newsletter_id, layer, attempt)` + `idx_edition_evals_trend`, SECTION 2 the governed `edition_eval` proxy-agent seed (hard-capped 5000/weekly reject-on-cap wallet, `claude-sonnet-4-6`) with the `<bcrypt-hash>` placeholder left unsubstituted for the 27-03 orchestrator apply.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-06-25T15:04Z (approx)
- **Completed:** 2026-06-25T15:10Z
- **Tasks:** 2
- **Files modified:** 1 (created)

## Accomplishments
- SECTION 1: `edition_evals` table authored verbatim from the authoritative REQUIREMENTS.md DDL (lines 103-126) — JSONB-only (`deterministic_flags`, `judge_scores`, `model_calls`), the named `edition_evals_verdict_iff_ok` CHECK making a silent-zero / verdict-without-eval row unrepresentable, `UNIQUE(newsletter_id, layer, attempt)` (per-attempt, NOT spec-01's `UNIQUE(newsletter_id)`), and `idx_edition_evals_trend (edition_number DESC, pipeline_version)`. `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` make it re-apply-safe.
- SECTION 2: governed `edition_eval` agent seed — `agent_registry` (`internal` tier, `ARRAY['deepseek-chat','claude-sonnet-4-6']`, rpm 10) + `agent_wallets_v2` (`allow_negative=FALSE`, `spending_cap_sats=5000`, `'weekly'`, `uncapped=FALSE`, `on_cap_behavior='reject'`, `downgrade_map='{}'::jsonb`, balance/deposited 25000), both with `ON CONFLICT (agent_name) DO UPDATE` idempotency (029 pattern). Satisfies the migration-034 `agent_wallets_v2_cap_or_uncapped` CHECK (5000 > 0).
- No spec-01 materialized columns (`tier1_count`/`voice_score`/…), no `edition_revisions` (REV-01 deferred), no EOL `claude-sonnet-4-20250514` (D-07). `api_key_hash` left as the literal `<bcrypt-hash>` placeholder (D-12/D-13).

## Task Commits

Each task was committed atomically:

1. **Task 1: SECTION 1 — edition_evals table, constraints, trend index** - `9556543` (feat)
2. **Task 2: SECTION 2 — governed edition_eval agent seed (registry + wallet)** - `8322031` (feat)

_Note: Task 2's commit also adjusted two header/SECTION-2 comment lines so the literal tokens `<bcrypt-hash>` and `ON CONFLICT (agent_name) DO UPDATE` appear only in the SQL statements (the Task 2 verify gate counts those lines exactly — see Issues)._

## Files Created/Modified
- `supabase/migrations/045_edition_evals.sql` (created, 111 lines) - Two-section SQL-first migration: SECTION 1 `edition_evals` DDL + constraints + trend index; SECTION 2 governed `edition_eval` agent_registry + agent_wallets_v2 seed. Authored only — NOT applied (27-03 substitutes the real hash + MCP-applies).

## Decisions Made
- **One sectioned idempotent file (D-11):** SECTION 1 borrows the 034 banner/idempotency house style; SECTION 2 borrows the 029 seed + `ON CONFLICT DO UPDATE` shape. Sections are independently re-runnable.
- **DDL verbatim from REQUIREMENTS.md, JSONB-only (D-04/D-07):** materialized per-dimension columns rejected to avoid the dual-write "which is canonical?" drift hazard and hard-coding tunable config names into the schema.
- **Placeholder hash, not invented (D-12/D-13):** `<bcrypt-hash>` stays literal; the orchestrator mints the `ap_edition_eval_<…>` key, substitutes the real bcrypt hash, delivers the plaintext to `config/.env` as `LLM_PROXY_EVAL_KEY`, and MCP-applies in 27-03.
- **Requirements left Pending:** EVAL-01/GOV-01/GOV-02 are ADVANCED (SQL authored) but not closed — the migration-file-existing is NOT the table-existing, and the agent is not live until the 27-03 apply + key mint. Closure deferred to phase end (consistent with the milestone's fail-loud/accuracy posture). EVAL-02/EVAL-03 belong to plan 27-02 (the persistence helper).

## Deviations from Plan

None - plan executed exactly as written. (No deviation rules triggered: no bugs, no missing critical functionality, no blocking issues, no architectural changes. Pure SQL authoring — no package installs, no LLM calls, no migration apply.)

## Issues Encountered
- On first authoring, two literal tokens leaked into comment lines: `<bcrypt-hash>` appeared in the header comment (2 matching lines, gate wants 1) and `ON CONFLICT (agent_name) DO UPDATE` appeared in a SECTION 2 comment (3 matching lines, gate wants 2). The Task 2 automated verify gate uses `grep -c` line counts, so the comments would have failed it. Reworded both comments (header → "the literal bcrypt-hash placeholder"; SECTION 2 → "the 029 on-conflict-do-update idempotency pattern") so the exact tokens appear only in the actual SQL statements. Both verify gates then returned PASS. Resolved within Task 2 before its commit.

## Verification

Both plan `<verify><automated>` gates run against the live file return **PASS**:
- **Task 1 gate:** `edition_evals_verdict_iff_ok` present, `UNIQUE (newsletter_id, layer, attempt)` present, `idx_edition_evals_trend` present, forbidden-column count (`tier1_count|voice_score|baseline_newsletter_id|edition_revisions`) = 0 → PASS.
- **Task 2 gate:** `<bcrypt-hash>` count = 1, `claude-sonnet-4-20250514` count = 0, `claude-sonnet-4-6` present, `INSERT INTO agent_wallets_v2` present, `'reject'` present, `ON CONFLICT (agent_name) DO UPDATE` count = 2 → PASS.
- File exists (`pathlib`), 111 lines (> 60 min_lines), all GOV-02 wallet tokens present (`allow_negative`, `spending_cap_sats`, `5000`, `'weekly'`, `uncapped`, `on_cap_behavior`, `'reject'`, `downgrade_map`, `25000`).

## Self-Check: PASSED
- `supabase/migrations/045_edition_evals.sql` — FOUND
- Commit `9556543` (Task 1) — FOUND in git log
- Commit `8322031` (Task 2) — FOUND in git log

## User Setup Required
None for this plan. (The orchestrator/operator key-mint + `config/.env` `LLM_PROXY_EVAL_KEY` delivery + MCP migration apply happen in plan 27-03 — worktree-unsafe, `autonomous: false`.)

## Next Phase Readiness
- The authoritative table shape + agent seed text are locked, so **plan 27-02** can build `docker/newsletter/edition_eval.py` (`write_eval_row()` + readers) against a stable column contract, and **plan 27-03** can substitute the real bcrypt hash into SECTION 2 and MCP-apply.
- Reminder for 27-03 (carried from the plan + CONTEXT D-12/D-13): the migration file existing is NOT the table existing — import/syntax checks pass without the apply; 27-03 must actually MCP-apply migration 045 and verify a settled `edition_eval` proxy call. Do NOT use `supabase db push`.

---
*Phase: 27-eval-persistence-governed-agent*
*Completed: 2026-06-25*
