-- Migration 047: promote_block_edition — atomic promotion of the block-pipeline
-- A/B shadow row to the public edition series (quick task 260706-lim).
--
-- Backs the owner-gated `/newsletter_promote <edition#> [confirm]` Telegram
-- command (gato_brain `handle_newsletter_promote`). Replaces the operator's
-- error-prone MANUAL SQL promotion workflow, which missed the migration-046
-- `do_not_publish` COLUMN and blocked edition #34's auto-publish on 2026-07-06.
--
-- SQL-FIRST — the operator/orchestrator applies this via MCP after DDL review
-- (project ref zxzaaqfowtqvmsbitqpu). The APPLY is an orchestrator-owned MCP
-- step, NOT the authoring task. Do NOT apply this from a worktree and do NOT
-- run `supabase db push`. Until this is applied, the command's confirm path
-- 404s on the missing RPC (expected).
--
-- ============================================================================
-- 1. BRIDGE SCOPE (operator-approved + LOCKED 2026-07-06)
-- ============================================================================
-- This command is designed to be RETIRED when `block_pipeline.enabled=true`
-- cuts the block pipeline over to primary. Cut-over criteria:
--   (1) two consecutive Fridays with symmetric evals on both paths, no crashes;
--   (2) block pipeline Phase D fabrications entirely stop-list FPs on both weeks;
--   (3) block fact-base persistence shipped;
--   (4) block pipeline angles meet the "editing not rewriting" threshold;
--   (5) live-proof of the block-primary eval path.
-- Target flip: 2026-08-01. If the criteria don't hold by then, reassess
-- upgrading this command to keeper scope.
--
-- ============================================================================
-- 2. DEFINITIVE SHADOW-MARKER INVENTORY (6)
-- ============================================================================
-- The block-pipeline A/B shadow row carries SIX markers; promotion must account
-- for every one of them (this inventory is the durable record):
--   1. status = 'held'
--   2. title prefix '[BLOCK PIPELINE A/B]' on title AND title_impact
--   3. do_not_publish COLUMN (canonical home since migration 046, 2026-07-02)
--   4. data_snapshot.do_not_publish (retired pre-046 location)
--   5. data_snapshot.ab_comparison
--   6. content_telegram absent (NOT a hold marker — see limitation below)
-- HISTORY NOTE: migration 046 moved do_not_publish's canonical home from
-- data_snapshot to the column; the operator's manual promotion workflow
-- tracked the OLD location and missed the column, which blocked edition #34's
-- auto-publish on 2026-07-06. This RPC clears both homes atomically.
--
-- ============================================================================
-- 3. KNOWN LIMITATION (decided 2026-07-06)
-- ============================================================================
-- Promoted rows have no content_telegram; publish falls back to
-- content_markdown[:4000]. Generating content_telegram at promotion time would
-- duplicate that fallback byte-for-byte, so it is deliberately NOT done at
-- bridge scope; a proper Telegram digest is keeper/LLM work.
--
-- ============================================================================
-- Atomicity contract: the plpgsql function body is ONE transaction — any
-- RAISE EXCEPTION rolls back EVERYTHING (partial promotion is impossible,
-- T-PROM-02). SECURITY DEFINER with a pinned search_path (T-PROM-03 — the
-- transfer_between_agents RPC broke on an empty search_path; never repeat it).

CREATE OR REPLACE FUNCTION promote_block_edition(
    p_shadow_id uuid,
    p_primary_id uuid,
    p_new_edition_number int,
    p_reason text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_shadow newsletters%ROWTYPE;
    v_primary newsletters%ROWTYPE;
BEGIN
    -- Validation 1: shadow row exists AND is actually a shadow.
    SELECT * INTO v_shadow FROM newsletters WHERE id = p_shadow_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'promote_block_edition: shadow row % not found', p_shadow_id;
    END IF;
    IF NOT (
        v_shadow.data_snapshot->>'ab_comparison' = 'true'
        OR v_shadow.title LIKE '[BLOCK PIPELINE A/B]%'
    ) THEN
        RAISE EXCEPTION
            'promote_block_edition: row % is not a block-pipeline A/B shadow (no ab_comparison marker, no [BLOCK PIPELINE A/B] title prefix)',
            p_shadow_id;
    END IF;

    -- Validation 2: primary row exists.
    SELECT * INTO v_primary FROM newsletters WHERE id = p_primary_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'promote_block_edition: primary row % not found', p_primary_id;
    END IF;

    -- Validation 3: the target public edition number is not already published.
    IF EXISTS (
        SELECT 1 FROM newsletters
        WHERE edition_number = p_new_edition_number AND status = 'published'
    ) THEN
        RAISE EXCEPTION
            'promote_block_edition: edition number % is already used by a published row',
            p_new_edition_number;
    END IF;

    -- Mutation A: promote the shadow row to the public edition series.
    -- Strips the '[BLOCK PIPELINE A/B] ' prefix (21 chars + trailing space →
    -- substring from 22), clears BOTH do_not_publish homes (column + retired
    -- data_snapshot key), drops ab_comparison, and stamps the promotion
    -- metadata using the operator's EXISTING manual-promotion key names
    -- (promoted_at / promotion_reason / promoted_from_held /
    -- replaces_single_pass_draft) — do not rename them.
    -- Deliberately NOT touched: do_not_publish_reason (the publish gate reads
    -- only the boolean + status; a stale reason string is cosmetic).
    UPDATE newsletters SET
        title = CASE
            WHEN title LIKE '[BLOCK PIPELINE A/B] %' THEN substring(title from 22)
            ELSE title
        END,
        title_impact = CASE
            WHEN title_impact LIKE '[BLOCK PIPELINE A/B] %' THEN substring(title_impact from 22)
            ELSE title_impact  -- NULL stays NULL; unprefixed stays as-is
        END,
        edition_number = p_new_edition_number,
        status = 'draft',
        do_not_publish = false,
        data_snapshot = (data_snapshot - 'ab_comparison' - 'do_not_publish')
            || jsonb_build_object(
                'promoted_at', now(),
                'promotion_reason', p_reason,
                'promoted_from_held', true,
                'replaces_single_pass_draft', p_primary_id::text
            )
    WHERE id = p_shadow_id;

    -- Mutation B: supersede the single-pass primary.
    UPDATE newsletters SET
        status = 'held',
        data_snapshot = data_snapshot
            || jsonb_build_object('superseded_by', p_shadow_id::text)
    WHERE id = p_primary_id;

    RETURN jsonb_build_object(
        'shadow_id', p_shadow_id,
        'new_edition_number', p_new_edition_number,
        'primary_id', p_primary_id,
        'primary_status', 'held'
    );
END;
$$;

COMMENT ON FUNCTION promote_block_edition(uuid, uuid, int, text) IS
    'Atomic bridge-scope promotion of the block-pipeline A/B shadow row to the public edition series; supersedes the single-pass primary. Backs /newsletter_promote (quick 260706-lim). Retire at block_pipeline.enabled=true cut-over (target 2026-08-01).';
