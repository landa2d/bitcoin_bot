-- Migration 039: guard the publish watermark against a NULL draft watermark
-- (code-review CR-01 follow-up to migration 038). Phase 09 / Plan 09-01.
--
-- ROOT CAUSE (CR-01): migration 038 Step 4 set
--   blocks.last_synthesized_at = v_synthesized_from_through
-- unconditionally. economy_map.block_body_versions.synthesized_from_through is
-- NULLABLE (033:101 — TIMESTAMPTZ with no NOT NULL constraint). The current
-- synthesis writer always populates it (processor.synthesize_block sets the run
-- wall-clock), so this is latent today — but any draft row with a NULL
-- synthesized_from_through (a future writer, a manual/test insert) would overwrite
-- the block watermark with NULL. NULL is the cold-start sentinel: the next
-- synthesis recency filter `created_at > last_synthesized_at` then degenerates and
-- re-reads the entire timeline — re-introducing the exact double-count bug 038 was
-- written to fix.
--
-- FIX: COALESCE the new watermark against the existing one, so a NULL draft
-- watermark leaves blocks.last_synthesized_at unchanged (neither skip nor
-- re-count relative to the current state) rather than clobbering it to NULL. The
-- publish still succeeds — a missing window bound must never fail an otherwise
-- valid approval, only decline to advance the watermark.
--
-- WHY SAFE: identical blast radius to 038 — writes ONLY economy_map.blocks (a
-- lifecycle table, no append-only trigger); the block_body_versions append-only
-- trigger (033 §8) guards synthesized_from_through on the VERSIONS table, which is
-- only READ here. T-09-04 disposition unchanged (accepted).
--
-- D-01a SCOPE FENCE preserved: no WR-01 duplicate-draft UNIQUE / partial index is
-- created here (still deferred to Phase 10). reject_block_version untouched.
--
-- Idempotent: CREATE OR REPLACE FUNCTION is safe to re-run; full body re-emit
-- (NOT an ALTER FUNCTION ... SET shim).

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
    -- CR-01 guard: COALESCE so a NULL draft watermark never clobbers the block's
    -- existing watermark (a missing window bound declines to advance, never resets).
    UPDATE economy_map.blocks
       SET current_body_version_id = p_version_id,
           maturity                = v_maturity,
           last_synthesized_at     = COALESCE(v_synthesized_from_through, last_synthesized_at)
     WHERE slug = v_slug;
END;
$$;

REVOKE ALL ON FUNCTION economy_map.publish_block_version(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION economy_map.publish_block_version(uuid) TO service_role;
