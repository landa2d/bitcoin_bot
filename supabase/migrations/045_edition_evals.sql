-- Migration 045: edition_evals persistence + governed edition_eval proxy agent
-- Phase 27 (v2.3 Pre-Publish Evaluation Step) — Eval Persistence & Governed Agent.
--
-- This migration stands up the persistence + budget core both eval layers
-- (Phases 28–30) write through, in ONE sectioned, idempotent (re-runnable) file (D-11):
--   - SECTION 1: the `edition_evals` per-attempt telemetry table with the fail-loud
--                `verdict-iff-ok` CHECK, the UNIQUE(newsletter_id, layer, attempt)
--                constraint, and the idx_edition_evals_trend index (EVAL-01 / D-04 / D-07).
--   - SECTION 2: the governed `edition_eval` proxy agent (agent_registry + agent_wallets_v2)
--                with its hard-capped, reject-on-cap wallet (GOV-01 / GOV-02 / D-01).
--
-- SQL-FIRST — the operator applies this via MCP after DDL review (project ref
-- zxzaaqfowtqvmsbitqpu). The SECTION 2 api_key_hash is the literal `<bcrypt-hash>`
-- placeholder here; the orchestrator mints the real ap_edition_eval_<…> key, substitutes
-- the real bcrypt hash, and MCP-applies the whole file in plan 27-03 (D-12 / D-13).
-- Do NOT apply this from a worktree and do NOT run `supabase db push`.
--
-- The table DDL (columns, the verdict-iff-ok CHECK, the per-attempt UNIQUE, the trend
-- index) is verbatim from the authoritative REQUIREMENTS.md DDL — that block overrides
-- spec-01 on shape/taxonomy/model-id (D-07). 034 supplies the idempotency house style.

-- ═══════════════════════════════════════════════════════
-- SECTION 1 — edition_evals table + constraints + trend index (EVAL-01 / D-04 / D-07)
-- ═══════════════════════════════════════════════════════
-- One fail-loud row per draft per layer per attempt. JSONB-only for the variable-shape
-- evidence (D-04/D-05): NO materialized per-dimension headline columns — the judge's
-- dimension set is config-tunable (Phase 29) and a materialized-plus-JSONB pair would
-- create a "which is canonical?" dual-write drift hazard. `CREATE TABLE IF NOT EXISTS`
-- makes the whole statement (incl. the inline CHECK + UNIQUE constraints) re-apply-safe
-- in one shot (D-11 discretion).

CREATE TABLE IF NOT EXISTS edition_evals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    newsletter_id   UUID NOT NULL REFERENCES newsletters(id) ON DELETE CASCADE,
    edition_number  INT  NOT NULL,
    pipeline_version TEXT NOT NULL CHECK (pipeline_version IN ('single_pass','block_v1')),
    attempt         INT  NOT NULL DEFAULT 0,          -- 0 = initial eval; 1,2 = rewrite re-evals
    layer           TEXT NOT NULL CHECK (layer IN ('deterministic','judge')),
    eval_status     TEXT NOT NULL CHECK (eval_status IN ('ok','error')),
    error           TEXT,                              -- iff eval_status='error'
    verdict         TEXT CHECK (verdict IN ('passed','held_fabrication','held_voice','escalated')),
    -- fail-loud invariant: a verdict exists iff the eval ran (no silent-zero row possible)
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

CREATE INDEX IF NOT EXISTS idx_edition_evals_trend ON edition_evals (edition_number DESC, pipeline_version);
