-- Migration 034: governance caps + on-cap behavior (LLM-proxy DB-based governance)
-- Phase 04.1 / Prod↔Main Reconciliation + LLM-Proxy Governance Migration.
-- Couples with the proxy.py edits in plan 04.1-01 — the proxy reads the new
-- agent_wallets_v2 columns added here and emits the new fail-loud event_type
-- that this migration must whitelist in the governance_events CHECK.
--
-- This migration does five things, idempotently (re-runnable):
--   - SECTION 1: extend agent_wallets_v2 with uncapped / on_cap_behavior / downgrade_map (D-02/D-04)
--   - SECTION 2: backfill the exact canonical caps from governance_config.json (D-01)
--   - SECTION 3: data-driven uncapped sweep — every null-cap agent NOT in the five
--                capped agents is marked uncapped=TRUE so it does not hard-reject post-cutover (D-03/D-04)
--   - SECTION 4: structural fail-loud CHECK — (cap>0) OR uncapped — added AFTER the
--                backfill so existing null-cap rows do not violate it mid-migration (operator pref: structure > app)
--   - SECTION 5: extend the closed governance_events.event_type CHECK to include the
--                new fail-loud 'cap_missing' type (D-03 / load-bearing for fail-loud actually persisting)
--
-- NOTE (D-09): governance_config.json stays in the repo as audit trail only. proxy.py
-- reads ONLY the DB columns added here — no file fallback. The cap values below are
-- the verbatim canonical values from docker/llm-proxy/governance_config.json.
--
-- The operator-runnable verification gate that asserts this migration landed correctly
-- on prod is owned by
-- .planning/phases/04.1-prod-main-reconciliation-llm-proxy-governance-migration-brin/04.1-CANARY.md
-- (executed by plan 04.1-02 AFTER applying this migration + deploying the new proxy.py).
--
-- IMPORTANT: this migration is NOT applied by plan 04.1-01 — it is authored here and
-- applied to live Supabase by plan 04.1-02, gated by the canary.

-- ═══════════════════════════════════════════════════════
-- SECTION 1 — Schema extension on agent_wallets_v2 (D-02 / D-04)
-- ═══════════════════════════════════════════════════════
-- agent_wallets_v2.spending_cap_sats is nullable today (023:30) — the D-03 hazard.
-- These three columns make the on-cap behavior and the explicit uncapped opt-in
-- first-class, DB-readable state (proxy uses select("*") so they surface automatically).
--   uncapped         — the ONLY legal way to run without a cap (D-04 explicit opt-in).
--   on_cap_behavior  — per-agent behavior when the cap is hit: reject (default) or downgrade (D-02).
--   downgrade_map    — old_model -> new_model JSONB map consumed by the downgrade behavior (D-02).

ALTER TABLE agent_wallets_v2
    ADD COLUMN IF NOT EXISTS uncapped BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE agent_wallets_v2
    ADD COLUMN IF NOT EXISTS on_cap_behavior TEXT NOT NULL DEFAULT 'reject'
        CHECK (on_cap_behavior IN ('reject', 'downgrade'));

ALTER TABLE agent_wallets_v2
    ADD COLUMN IF NOT EXISTS downgrade_map JSONB NOT NULL DEFAULT '{}'::jsonb;

-- ═══════════════════════════════════════════════════════
-- SECTION 2 — Cap backfill (D-01) — exact canonical values from governance_config.json
-- ═══════════════════════════════════════════════════════
-- Rows already exist on prod (audit 2026-05-28). analyst is currently 1000 in the DB
-- and MUST become 28000; processor/research/newsletter/gato are null and MUST be set.
-- Explicit per-agent UPDATEs — deliberately NOT a conflict-ignoring upsert (a skip-on-conflict
-- clause would bypass the analyst correction and leave the others null). UPDATE always writes;
-- re-running just re-asserts the canonical values.

UPDATE agent_wallets_v2
SET spending_cap_sats = 28000,
    spending_cap_window = 'daily',
    on_cap_behavior = 'reject',
    uncapped = FALSE,
    updated_at = NOW()
WHERE agent_name = 'analyst';

UPDATE agent_wallets_v2
SET spending_cap_sats = 1000,
    spending_cap_window = 'daily',
    on_cap_behavior = 'reject',
    uncapped = FALSE,
    updated_at = NOW()
WHERE agent_name = 'processor';

UPDATE agent_wallets_v2
SET spending_cap_sats = 5000,
    spending_cap_window = 'weekly',
    on_cap_behavior = 'reject',
    uncapped = FALSE,
    updated_at = NOW()
WHERE agent_name = 'research';

UPDATE agent_wallets_v2
SET spending_cap_sats = 2000,
    spending_cap_window = 'weekly',
    on_cap_behavior = 'reject',
    uncapped = FALSE,
    updated_at = NOW()
WHERE agent_name = 'newsletter';

-- gato: downgrade-on-cap (D-02). When the 50000/daily cap is hit, the proxy downgrades
-- claude-sonnet-4-20250514 -> deepseek-chat instead of rejecting. This preserves the
-- pre-cutover governance_config.json behavior ("on_cap_exceeded": "downgrade_model").
UPDATE agent_wallets_v2
SET spending_cap_sats = 50000,
    spending_cap_window = 'daily',
    on_cap_behavior = 'downgrade',
    uncapped = FALSE,
    downgrade_map = '{"claude-sonnet-4-20250514": "deepseek-chat"}'::jsonb,
    updated_at = NOW()
WHERE agent_name = 'gato';

-- ═══════════════════════════════════════════════════════
-- SECTION 3 — Uncapped sweep (D-03 / D-04) — data-driven, not hand-enumerated
-- ═══════════════════════════════════════════════════════
-- Under D-03 every agent must carry EITHER a numeric cap OR an explicit uncapped=TRUE.
-- The audit found prod agents with null caps that are NOT in the five capped agents
-- above (lab_data-provider, rivalscope, all code_*, most lab_*). They are operator-created
-- and may grow, so this is a single predicate-driven UPDATE keyed on the null-cap state —
-- NOT a hand-enumerated list. After this, no agent is left in the illegal ambiguous state
-- (null cap AND not uncapped), so the new proxy will not hard-reject them on their next call.
-- rivalscope is deferred for its negative-balance anomaly but still needs uncapped=TRUE
-- here so it does not hard-reject post-cutover.
-- The NOT IN guard protects the five capped agents in case a transient run order leaves
-- one of them temporarily null (it never should after SECTION 2, but the guard is cheap).
UPDATE agent_wallets_v2
SET uncapped = TRUE,
    on_cap_behavior = 'reject',
    updated_at = NOW()
WHERE spending_cap_sats IS NULL
  AND uncapped = FALSE
  AND agent_name NOT IN ('analyst', 'processor', 'research', 'newsletter', 'gato');

-- ═══════════════════════════════════════════════════════
-- SECTION 4 — Structural fail-loud invariant (operator preference: structure > application)
-- ═══════════════════════════════════════════════════════
-- Make the illegal ambiguous state UNREPRESENTABLE at the DB level: a row must carry
-- a positive cap OR be explicitly uncapped. Added AFTER the backfill + sweep so no
-- existing row violates it mid-migration. Guarded so re-running does not error
-- (mirrors the 033:119-138 / 004 DO $$ … EXCEPTION duplicate_object pattern for
-- ADD CONSTRAINT replay safety regardless of Postgres ADD CONSTRAINT IF NOT EXISTS support).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM information_schema.table_constraints
         WHERE constraint_name = 'agent_wallets_v2_cap_or_uncapped'
           AND table_name      = 'agent_wallets_v2'
    ) THEN
        BEGIN
            ALTER TABLE agent_wallets_v2
                ADD CONSTRAINT agent_wallets_v2_cap_or_uncapped
                CHECK ((spending_cap_sats IS NOT NULL AND spending_cap_sats > 0) OR uncapped = TRUE);
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END;
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════
-- SECTION 5 — governance_events.event_type CHECK extension (load-bearing for fail-loud)
-- ═══════════════════════════════════════════════════════
-- The proxy's fail-loud path (D-03) emits a NEW event_type for the illegal missing-cap /
-- unknown-agent case. The chosen string is:
--
--     FAIL-LOUD EVENT TYPE  ==>  'cap_missing'
--
-- Task 2 (proxy.py) MUST pass EXACTLY 'cap_missing' to _emit_governance_event. If these
-- two strings ever drift, the closed CHECK at 023:69-72 rejects the insert and
-- _emit_governance_event swallows the exception (proxy.py:279-280) — re-creating the exact
-- silent-failure class this phase exists to kill. The downgrade path reuses the existing
-- 'model_downgrade' type (already in the list below), so no new type is needed for that.
--
-- governance_events may have been created by either 020 (no event_type CHECK) or
-- 023 (closed CHECK list). The LIVE prod CHECK (verified 2026-05-28 against project
-- zxzaaqfowtqvmsbitqpu) carries SEVEN values — the 023 six PLUS 'system_audit' (added by
-- later prod drift; 2 existing rows use it, last seen 2026-04-30). We DROP the existing
-- CHECK and re-add it preserving ALL seven live values PLUS the new 'cap_missing'. Dropping
-- 'system_audit' would (a) fail this ALTER outright (existing rows violate the new CHECK)
-- and (b) silently reject future system_audit inserts — re-creating the silent-failure
-- class this phase exists to kill. Guarded so re-running is safe (drop existing, re-add only if absent).
DO $$
DECLARE
    v_constraint_name TEXT;
BEGIN
    -- Find any existing CHECK constraint on governance_events.event_type and drop it.
    SELECT con.conname INTO v_constraint_name
      FROM pg_constraint con
      JOIN pg_class rel ON rel.oid = con.conrelid
     WHERE rel.relname = 'governance_events'
       AND con.contype = 'c'
       AND pg_get_constraintdef(con.oid) ILIKE '%event_type%';

    IF v_constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE governance_events DROP CONSTRAINT %I', v_constraint_name);
    END IF;

    -- Re-add the canonical (extended) CHECK including the new 'cap_missing' fail-loud type.
    BEGIN
        ALTER TABLE governance_events
            ADD CONSTRAINT governance_events_event_type_check
            CHECK (event_type IN (
                'cap_hit',
                'model_downgrade',
                'rate_limit',
                'balance_low',
                'balance_exhausted',
                'fallback_triggered',
                'system_audit',
                'cap_missing'
            ));
    EXCEPTION WHEN duplicate_object THEN
        NULL;
    END;
END $$;

-- VERIFY pointer (033 convention): the canary that proves all of the above landed on
-- prod is .planning/phases/04.1-prod-main-reconciliation-llm-proxy-governance-migration-brin/04.1-CANARY.md
-- (plan 04.1-02 runs it after applying this migration + deploying proxy.py).
