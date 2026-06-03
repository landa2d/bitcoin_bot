-- Migration 040: operator write-command schema for Phase 10.
-- Phase 10 operator-write-commands / Plan 10-01.
--
-- Lands the foundational economy_map schema for the four operator write commands so that
-- gato_brain (Plan 02) and the processor drain poller (Plan 03) fail-loud against an
-- existing schema rather than a missing one. Five concerns, each following the migration
-- 033 / 038 precedents verbatim:
--   1. synth_requests table (D-01/D-03) — the cross-service /map-synth request queue,
--      pending → processing → done/failed lifecycle; a failed forced-synth is QUERYABLE
--      (error column), never a silent drop ("the wallet bug" lesson).
--   2. timeline_entries.reassigned_to_entry_id / reassigned_from_entry_id (D-04) — two
--      nullable, MUTABLE lifecycle columns for /map-assign reassignment.
--   3. timeline_entries_append_only() trigger re-emit (D-04) — full 033 body UNCHANGED
--      (every CONTENT column still pinned), simply WITHOUT guards on the two new
--      reassigned_* lifecycle columns, leaving them UPDATE-able. The exact
--      block_body_versions precedent (content pinned, lifecycle free). Trigger, NOT RLS —
--      service_role bypasses RLS by design (033 §8 loud comment, the historical failure actor).
--   4/5. Four SECURITY DEFINER RPCs (D-04/D-05/D-06/D-08), each pinning
--      the mandatory T-02 search-path pin (economy_map, public) and
--      REVOKE ALL FROM PUBLIC; GRANT EXECUTE TO service_role:
--        - reassign_timeline_entry(p_entry_id, p_block_slug)  → /map-assign (D-04/D-05)
--        - insert_manual_timeline_entry(p_slug, p_what_shifted, p_why_it_mattered) → /map-entry (D-06)
--        - set_block_live_tension(p_slug, p_text)             → /map-tension (D-08)
--        - enqueue_synth_request(p_slug)                      → /map-synth enqueue (D-01/D-03)
--
-- The WR-01 partial UNIQUE open-draft index ships SEPARATELY in migration 041 (D-07 —
-- its own operator-approved migration track). Do NOT fold it here.
--
-- All RPC bodies use typed plpgsql parameters only — NEVER string-interpolated values (T-10-04).
-- All RPCs are CREATE OR REPLACE full-body re-emits (idempotent; never an ALTER FUNCTION ... SET shim — 038:26-28).

-- ═══════════════════════════════════════════════════════
-- SECTION 1 — economy_map.synth_requests (D-01/D-03)
-- ═══════════════════════════════════════════════════════
-- The cross-service request queue for /map-synth. gato_brain enqueues a 'pending' row;
-- the processor drain poller marks it 'processing', then 'done' (with the resulting draft
-- version_id) or 'failed' (with a queryable error). Lifecycle-status + created_at shape
-- mirrors block_body_versions (033 §5); the queryable failed status mirrors pipeline_runs
-- (D-03). A failed forced-synth must be as visible as a failed autonomous cycle — never
-- a silent drop.
--
-- block_slug is intentionally NOT a FK (mirrors timeline_entries 033:150): slug validation
-- lives in gato_brain's seven-block allowlist + the enqueue RPC, and decoupling avoids a
-- lock dependency on blocks during the drain.

CREATE TABLE IF NOT EXISTS economy_map.synth_requests (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    block_slug  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','processing','done','failed')),  -- D-03 lifecycle
    version_id  UUID,                                                        -- the resulting draft on 'done'
    error       TEXT,                                                        -- the failure reason on 'failed' (queryable — never a silent drop, D-03)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ
);

-- Partial index so the drain poll (status = 'pending') is cheap — mirrors 033:109-110.
CREATE INDEX IF NOT EXISTS idx_synth_requests_pending
    ON economy_map.synth_requests(created_at) WHERE status = 'pending';

-- ═══════════════════════════════════════════════════════
-- SECTION 2 — timeline_entries reassign lifecycle columns (D-04)
-- ═══════════════════════════════════════════════════════
-- Two nullable, MUTABLE lifecycle pointers for /map-assign reassignment, mirroring the
-- block_body_versions status/published_at lifecycle-column precedent (033 §5/§8):
--   - reassigned_to_entry_id: set on the ORIGINAL when it is re-filed under a named block.
--   - reassigned_from_entry_id: set on the new COPY, pointing back at the original (provenance).
-- The append-only trigger (Section 3) exempts ONLY these two columns; all CONTENT columns
-- stay fully immutable.

ALTER TABLE economy_map.timeline_entries
    ADD COLUMN IF NOT EXISTS reassigned_to_entry_id UUID;
ALTER TABLE economy_map.timeline_entries
    ADD COLUMN IF NOT EXISTS reassigned_from_entry_id UUID;

-- ═══════════════════════════════════════════════════════
-- SECTION 3 — timeline_entries_append_only() trigger exemption (D-04)
-- ═══════════════════════════════════════════════════════
-- APPEND-ONLY ENFORCEMENT — INTENTIONALLY NOT RLS (033 §8 loud comment).
-- service_role bypasses RLS by design; content immutability must hold AGAINST service_role.
-- A future developer WILL try to "simplify" this to RLS. Do not.
--
-- This is a full-body re-emit of the 033:213-248 trigger, UNCHANGED in its content guards
-- (block_slug, event_date, what_shifted, why_it_mattered, source_url, source_edition_id,
-- tag_confidence all still RAISE on IS DISTINCT FROM; DELETE still forbidden). It simply
-- does NOT add guards for the two new reassigned_* lifecycle columns, leaving them
-- UPDATE-able — the exact block_body_versions precedent (content pinned, lifecycle free).

CREATE OR REPLACE FUNCTION economy_map.timeline_entries_append_only()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- DELETE is never allowed on this table.
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'timeline_entries is append-only (DELETE not permitted)';
    END IF;

    -- For UPDATE: every CONTENT column is pinned. The reassigned_to_entry_id /
    -- reassigned_from_entry_id lifecycle columns are intentionally NOT guarded here (D-04).
    IF NEW.block_slug IS DISTINCT FROM OLD.block_slug THEN
        RAISE EXCEPTION 'timeline_entries.block_slug is append-only';
    END IF;
    IF NEW.event_date IS DISTINCT FROM OLD.event_date THEN
        RAISE EXCEPTION 'timeline_entries.event_date is append-only';
    END IF;
    IF NEW.what_shifted IS DISTINCT FROM OLD.what_shifted THEN
        RAISE EXCEPTION 'timeline_entries.what_shifted is append-only (was %, now %)', OLD.what_shifted, NEW.what_shifted;
    END IF;
    IF NEW.why_it_mattered IS DISTINCT FROM OLD.why_it_mattered THEN
        RAISE EXCEPTION 'timeline_entries.why_it_mattered is append-only';
    END IF;
    IF NEW.source_url IS DISTINCT FROM OLD.source_url THEN
        RAISE EXCEPTION 'timeline_entries.source_url is append-only';
    END IF;
    IF NEW.source_edition_id IS DISTINCT FROM OLD.source_edition_id THEN
        RAISE EXCEPTION 'timeline_entries.source_edition_id is append-only';
    END IF;
    IF NEW.tag_confidence IS DISTINCT FROM OLD.tag_confidence THEN
        RAISE EXCEPTION 'timeline_entries.tag_confidence is append-only';
    END IF;

    RETURN NEW;
END;
$$;

-- Trigger definition unchanged from 033:250-253 (re-asserted for idempotent replay safety).
DROP TRIGGER IF EXISTS timeline_entries_append_only_trg ON economy_map.timeline_entries;
CREATE TRIGGER timeline_entries_append_only_trg
BEFORE UPDATE OR DELETE ON economy_map.timeline_entries
FOR EACH ROW EXECUTE FUNCTION economy_map.timeline_entries_append_only();

-- ═══════════════════════════════════════════════════════
-- SECTION 4 — economy_map.reassign_timeline_entry (RPC; D-04/D-05 → /map-assign)
-- ═══════════════════════════════════════════════════════
-- Atomically re-files an 'unsorted' timeline entry under a named block as a NEW row
-- referencing the prior, and marks the original reassigned. Reassignment is a *filing*
-- action, NOT a new event: the copy preserves provenance (event_date, what_shifted,
-- why_it_mattered, source_url, source_edition_id copied verbatim — NOT today's date, D-05).
-- tag_confidence is set to NULL on the copy: operator assignment is authoritative, not a
-- classifier score (D-05 Discretion — NULL chosen over 1.0; tag_confidence semantics are
-- "classifier confidence", and an operator filing has no classifier behind it).
--
-- Single-winner gate (033:285-291 pattern): the source SELECT requires the entry to be
-- currently block_slug = 'unsorted' AND reassigned_to_entry_id IS NULL; otherwise the
-- RETURNING is empty and a typed exception is RAISEd — cannot re-file an already-filed or
-- already-reassigned entry (T-10-03).

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
    -- not-yet-reassigned entry. Empty RETURNING → the entry is not eligible (single-winner).
    SELECT event_date, what_shifted, why_it_mattered, source_url, source_edition_id
      INTO v_event_date, v_what_shifted, v_why_it_mattered, v_source_url, v_source_edition_id
      FROM economy_map.timeline_entries
     WHERE id                     = p_entry_id
       AND block_slug             = 'unsorted'
       AND reassigned_to_entry_id IS NULL;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'timeline entry % is not an unsorted, un-reassigned entry', p_entry_id;
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

-- ═══════════════════════════════════════════════════════
-- SECTION 5 — economy_map.insert_manual_timeline_entry (RPC; D-06 → /map-entry)
-- ═══════════════════════════════════════════════════════
-- Manual append-only timeline drop for things the pipeline missed. INSERTs one
-- timeline_entries row with what_shifted + why_it_mattered (both NOT NULL),
-- event_date = CURRENT_DATE (today — this IS a manual drop, not a provenance copy),
-- source_url / source_edition_id NULL, tag_confidence NULL (no classifier).
-- Rejects 'unsorted' (a manual entry is always filed) and any unknown slug with a typed error.

CREATE OR REPLACE FUNCTION economy_map.insert_manual_timeline_entry(
    p_slug text,
    p_what_shifted text,
    p_why_it_mattered text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = economy_map, public
AS $$
DECLARE
    v_new_id uuid;
BEGIN
    -- Reject the unsorted backlog as a manual-drop target (a manual entry is filed by the operator).
    IF p_slug = 'unsorted' THEN
        RAISE EXCEPTION 'manual timeline entries cannot target the unsorted backlog';
    END IF;

    -- Reject unknown slugs with a typed error (block must exist).
    IF NOT EXISTS (SELECT 1 FROM economy_map.blocks WHERE slug = p_slug) THEN
        RAISE EXCEPTION 'block % not found', p_slug;
    END IF;

    INSERT INTO economy_map.timeline_entries
        (block_slug, event_date, what_shifted, why_it_mattered, source_url, source_edition_id, tag_confidence)
    VALUES
        (p_slug, CURRENT_DATE, p_what_shifted, p_why_it_mattered, NULL, NULL, NULL)
    RETURNING id INTO v_new_id;

    RETURN v_new_id;
END;
$$;

REVOKE ALL ON FUNCTION economy_map.insert_manual_timeline_entry(text, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION economy_map.insert_manual_timeline_entry(text, text, text) TO service_role;

-- ═══════════════════════════════════════════════════════
-- SECTION 6 — economy_map.set_block_live_tension (RPC; D-08 → /map-tension)
-- ═══════════════════════════════════════════════════════
-- Updates a block's live_tension — the editorial framing reserved for humans. blocks has
-- NO append-only trigger (033:73 annotates live_tension "mutated via /map-tension"), so this
-- is a plain mutable UPDATE. Typed unknown-slug error via IF NOT FOUND.

CREATE OR REPLACE FUNCTION economy_map.set_block_live_tension(p_slug text, p_text text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = economy_map, public
AS $$
BEGIN
    UPDATE economy_map.blocks
       SET live_tension = p_text
     WHERE slug = p_slug;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'block % not found', p_slug;
    END IF;
END;
$$;

REVOKE ALL ON FUNCTION economy_map.set_block_live_tension(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION economy_map.set_block_live_tension(text, text) TO service_role;

-- ═══════════════════════════════════════════════════════
-- SECTION 7 — economy_map.enqueue_synth_request (RPC; D-01/D-03/D-09 → /map-synth)
-- ═══════════════════════════════════════════════════════
-- Enqueues a forced-synthesis request. Preferred over a direct table INSERT per D-09 (all
-- gato_brain writes go through a SECURITY DEFINER RPC behind the allowlist). The slug
-- allowlist + open-draft precondition are validated synchronously in gato_brain BEFORE
-- this RPC is called (D-03); this RPC is the durable enqueue and returns the request id.

CREATE OR REPLACE FUNCTION economy_map.enqueue_synth_request(p_slug text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = economy_map, public
AS $$
DECLARE
    v_request_id uuid;
BEGIN
    INSERT INTO economy_map.synth_requests (block_slug, status)
    VALUES (p_slug, 'pending')
    RETURNING id INTO v_request_id;

    RETURN v_request_id;
END;
$$;

REVOKE ALL ON FUNCTION economy_map.enqueue_synth_request(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION economy_map.enqueue_synth_request(text) TO service_role;

-- ═══════════════════════════════════════════════════════
-- SECTION 8 — Grants on the new synth_requests table
-- ═══════════════════════════════════════════════════════
-- GRANT ALL ON ALL TABLES (033 §12) only covered tables existing at 033 apply time; the new
-- synth_requests table needs an explicit service_role grant. No anon access (this is an
-- internal request queue, not browser-facing). RLS deliberately not enabled — service_role
-- is the only actor and bypasses RLS anyway; access control is via the REVOKE/GRANT on the
-- enqueue RPC + service_role-only table grant.

GRANT ALL ON economy_map.synth_requests TO service_role;

-- ═══════════════════════════════════════════════════════
-- SECTION 9 — Closing
-- ═══════════════════════════════════════════════════════
-- End migration 040: synth_requests table, timeline_entries reassign lifecycle columns +
-- trigger exemption, and the four SECURITY DEFINER write RPCs landed. The WR-01 partial
-- UNIQUE open-draft index ships separately in migration 041 (D-07).
