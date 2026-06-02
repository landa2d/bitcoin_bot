-- Migration 038: advance the publish watermark from the approved draft's pinned
-- synthesized_from_through (D-01, the IN-04 correctness contract) — NOT NOW().
-- Phase 09 gated-publishing-approval-commands / Plan 09-01.
--
-- ROOT CAUSE (the IN-04 double-count / skip contract): the next synthesis cycle's
-- recency filter is `created_at > last_synthesized_at`. Migration 033 §9 Step 4 stamped
-- the block watermark with the wall-clock approval instant. But timeline entries created
-- in the window BETWEEN synthesis (which pins `synthesized_from_through` on the draft) and
-- operator approval are then either skipped (NOW() > their created_at, so the next
-- cycle's `created_at > last_synthesized_at` excludes them) or double-counted —
-- depending on ordering. The fix: advance the block's watermark to the EXACT upper
-- bound of the entry window the approved draft actually consumed
-- (`block_body_versions.synthesized_from_through`), so the next cycle resumes precisely
-- where this draft's window ended. No window entry is lost or re-counted.
--
-- WHY SAFE: this RPC writes ONLY `economy_map.blocks` — a lifecycle table with no
-- append-only trigger. The `block_body_versions` append-only trigger (033 §8) guards
-- `synthesized_from_through` against UPDATE/DELETE on the VERSIONS table; here that
-- column is only READ (Step 1 RETURNING) and the value is written to a different table
-- (blocks.last_synthesized_at). The trigger is not implicated (T-09-04, accepted).
--
-- D-01a SCOPE FENCE: the WR-01 duplicate-draft UNIQUE / partial index is deliberately
-- NOT folded into this migration. It stays deferred to Phase 10. This migration changes
-- ONLY the watermark assignment in publish_block_version; no index is created here.
--
-- Idempotent: CREATE OR REPLACE FUNCTION is safe to re-run. This is a full body re-emit,
-- NOT an ALTER FUNCTION ... SET shim (the 035/037 analog only repairs a search_path GUC
-- and is the wrong tool for a body change).

CREATE OR REPLACE FUNCTION economy_map.publish_block_version(p_version_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = economy_map, public
AS $$
DECLARE
    v_slug                      text;
    v_maturity                  economy_map.maturity;
    v_synthesized_from_through  timestamptz;
BEGIN
    -- Step 1: atomic draft → published flip. RETURNING is empty if the row is not
    -- found or not in draft status — that's how concurrent publish-races lose
    -- (T-02-05 mitigation, single-winner property). Also capture the draft's pinned
    -- synthesized_from_through (the upper bound of the entry window this draft consumed)
    -- so Step 4 can advance the block watermark exactly (D-01).
    UPDATE economy_map.block_body_versions
       SET status        = 'published',
           published_at  = NOW()
     WHERE id     = p_version_id
       AND status = 'draft'
    RETURNING block_slug, proposed_maturity, synthesized_from_through
      INTO v_slug, v_maturity, v_synthesized_from_through;

    -- Step 2: surface the not-found / not-draft case as a typed exception.
    IF v_slug IS NULL THEN
        RAISE EXCEPTION 'version % not found or not in draft status', p_version_id;
    END IF;

    -- Step 3: supersede any prior published version for the same block.
    UPDATE economy_map.block_body_versions
       SET status = 'superseded'
     WHERE block_slug = v_slug
       AND status     = 'published'
       AND id        <> p_version_id;

    -- Step 4: point the block at the new current version + sync maturity + advance the
    -- watermark to the approved draft's pinned synthesized_from_through (D-01), NOT NOW().
    UPDATE economy_map.blocks
       SET current_body_version_id = p_version_id,
           maturity                = v_maturity,
           last_synthesized_at     = v_synthesized_from_through
     WHERE slug = v_slug;
END;
$$;

REVOKE ALL ON FUNCTION economy_map.publish_block_version(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION economy_map.publish_block_version(uuid) TO service_role;
