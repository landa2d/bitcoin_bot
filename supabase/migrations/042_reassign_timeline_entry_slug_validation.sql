-- Migration 042: harden economy_map.reassign_timeline_entry (Phase 10 code-review CR-01 + WR-04).
-- Phase 10 operator-write-commands / Plan 10-01 follow-up.
--
-- Re-emits reassign_timeline_entry (migration 040 §4) as a full-body CREATE OR REPLACE with
-- two integrity fixes. The RPC is SECURITY DEFINER and runs as service_role, which BYPASSES
-- RLS — so the RPC body is the actual integrity boundary, never the gato_brain application
-- allowlist (MEMORY: "structural over application enforcement … service_role bypasses RLS,
-- the historical failure actor"). The four changes from 040, all AFTER the NOT FOUND gate:
--
--   CR-01 — server-side target-slug validation (mirrors insert_manual_timeline_entry §5):
--     * reject p_block_slug = 'unsorted' (re-filing to the backlog re-creates the very state
--       /map-assign exists to drain);
--     * reject an unknown slug via IF NOT EXISTS (SELECT 1 FROM economy_map.blocks ...).
--     Without these, any service_role caller (a future processor path, a direct RPC, or a
--     drift between gato_brain's hardcoded _ECONOMY_MAP_BLOCK_SLUGS and the blocks seed) can
--     file an UNDELETABLE orphan timeline row under a non-existent/backlog block (the table
--     is append-only — the spurious row cannot be removed).
--
--   WR-04 — single-flight lock: add FOR UPDATE to the Step-1 source SELECT so the original
--     row is locked for the transaction. Without it, two concurrent /map-assign calls on one
--     entry id (operator double-tap / retry) can both pass the SELECT, both INSERT a copy,
--     and both UPDATE — producing TWO undeletable filed entries for one unsorted item. The
--     lock makes the 'unsorted AND reassigned_to_entry_id IS NULL' gate a true single-winner.
--
-- Everything else (signature, RETURNS uuid, SECURITY DEFINER, SET search_path, provenance
-- copy, tag_confidence NULL, the original-marking UPDATE, REVOKE/GRANT) is unchanged from 040.

CREATE OR REPLACE FUNCTION economy_map.reassign_timeline_entry(p_entry_id uuid, p_block_slug text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = economy_map, public
AS $$
DECLARE
    v_event_date        date;
    v_what_shifted      text;
    v_why_it_mattered   text;
    v_source_url        text;
    v_source_edition_id text;
    v_new_id            uuid;
BEGIN
    -- Step 1: capture the original's content, gated on it being a currently-unsorted,
    -- not-yet-reassigned entry, LOCKED for the transaction (WR-04 single-flight). Empty
    -- RETURNING → the entry is not eligible (single-winner).
    SELECT event_date, what_shifted, why_it_mattered, source_url, source_edition_id
      INTO v_event_date, v_what_shifted, v_why_it_mattered, v_source_url, v_source_edition_id
      FROM economy_map.timeline_entries
     WHERE id                     = p_entry_id
       AND block_slug             = 'unsorted'
       AND reassigned_to_entry_id IS NULL
       FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'timeline entry % is not an unsorted, un-reassigned entry', p_entry_id;
    END IF;

    -- CR-01: the reassignment target must be a real, non-backlog block. The DB is the
    -- boundary (service_role bypasses RLS); do not rely on the gato_brain allowlist alone.
    IF p_block_slug = 'unsorted' THEN
        RAISE EXCEPTION 'cannot reassign an entry back to the unsorted backlog';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM economy_map.blocks WHERE slug = p_block_slug) THEN
        RAISE EXCEPTION 'block % not found', p_block_slug;
    END IF;

    -- Step 2: INSERT the new row under the target slug, preserving provenance (D-05) and
    -- linking back to the original. tag_confidence NULL — operator authority, not a score.
    INSERT INTO economy_map.timeline_entries
        (block_slug, event_date, what_shifted, why_it_mattered, source_url, source_edition_id, tag_confidence, reassigned_from_entry_id)
    VALUES
        (p_block_slug, v_event_date, v_what_shifted, v_why_it_mattered, v_source_url, v_source_edition_id, NULL, p_entry_id)
    RETURNING id INTO v_new_id;

    -- Step 3: mark the original reassigned (the permitted lifecycle-column UPDATE, D-04).
    UPDATE economy_map.timeline_entries
       SET reassigned_to_entry_id = v_new_id
     WHERE id = p_entry_id;

    RETURN v_new_id;
END;
$$;

REVOKE ALL ON FUNCTION economy_map.reassign_timeline_entry(uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION economy_map.reassign_timeline_entry(uuid, text) TO service_role;
