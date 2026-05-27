-- Migration 033: economy_map schema for Agent Economy living reference articles
-- Phase 2 / The Agent Economy — first isolated-schema migration in this repo.
-- Future agents reference this file as the canonical example for eu_ai_act-style schema isolation (see CONTEXT.md D-04).
--
-- This one-shot migration lands the entire structural foundation for Phase 2:
--   - The economy_map schema + grants
--   - The maturity ENUM type (first real Postgres enum in this repo)
--   - Three tables: blocks, block_body_versions, timeline_entries
--   - Append-only BEFORE UPDATE/DELETE triggers on the two content tables
--   - Two SECURITY DEFINER RPCs: publish_block_version + reject_block_version
--   - Row-Level Security policies for the anon role
--   - Schema- and table-level grants
--   - Idempotent seed of the seven blocks
--
-- Conclusive verification of all five ROADMAP success criteria is owned by
-- .planning/phases/02-economy-map-schema-seven-block-seed/02-VERIFY.sql (Plan 02-02).

-- ═══════════════════════════════════════════════════════
-- SECTION 2 — Schema + role grants (first in-tree precedent per CONTEXT.md D-04)
-- ═══════════════════════════════════════════════════════
-- GRANT USAGE is required for Accept-Profile: economy_map reads from PostgREST to
-- resolve — without it, anon cannot enter the schema even if RLS would allow the row.

CREATE SCHEMA IF NOT EXISTS economy_map;
GRANT USAGE ON SCHEMA economy_map TO anon, authenticated, service_role;

-- ═══════════════════════════════════════════════════════
-- SECTION 3 — Maturity ENUM (first in-tree real Postgres enum per D-03 / SCHM-05)
-- ═══════════════════════════════════════════════════════
-- Repo convention elsewhere is text + CHECK (col IN (…)) — see migration 021 line 10.
-- This migration deliberately breaks from that for maturity per D-03: a real ENUM is
-- strongly typed at the DB level, so a future migration cannot accept an invalid
-- value without dropping the type, which is loud and reviewable.
--
-- Order matters: nascent → emerging → contested → consolidating → mature.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_type t
          JOIN pg_namespace n ON n.oid = t.typnamespace
         WHERE t.typname = 'maturity'
           AND n.nspname = 'economy_map'
    ) THEN
        CREATE TYPE economy_map.maturity AS ENUM (
            'nascent',
            'emerging',
            'contested',
            'consolidating',
            'mature'
        );
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════
-- SECTION 4 — economy_map.blocks (SCHM-02, SCHM-07, D-13)
-- ═══════════════════════════════════════════════════════
-- The seven canonical blocks live here. Identity / current_body_version_id / maturity
-- / live_tension live here; bodies live in block_body_versions and are pointed to
-- via current_body_version_id. live_tension is operator-managed (Phase 10 /map-tension).
--
-- Note: tier is text + CHECK (small, stable set) — enums reserved for maturity per D-03.

CREATE TABLE IF NOT EXISTS economy_map.blocks (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug                        TEXT NOT NULL UNIQUE,                                       -- the seven slugs from CONTEXT.md D-23
    tier                        TEXT NOT NULL CHECK (tier IN ('substrate','behavior','frame')),
    title                       TEXT NOT NULL,
    subtitle                    TEXT NOT NULL,                                              -- one-line hub caption per D-23
    accent                      TEXT NOT NULL CHECK (accent IN ('teal','purple','coral','gray')),
    sort_order                  INTEGER NOT NULL UNIQUE,                                    -- 1..7 from D-23
    live_tension                TEXT NOT NULL,                                              -- placeholder at seed; mutated via /map-tension (D-13)
    maturity                    economy_map.maturity NOT NULL DEFAULT 'nascent',            -- updated by publish_block_version
    current_body_version_id     UUID,                                                       -- FK added after block_body_versions exists (Section 6)
    last_synthesized_at         TIMESTAMPTZ,                                                -- nullable; populated by publish_block_version
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_blocks_tier ON economy_map.blocks(tier);
CREATE INDEX IF NOT EXISTS idx_blocks_sort_order ON economy_map.blocks(sort_order);

-- ═══════════════════════════════════════════════════════
-- SECTION 5 — economy_map.block_body_versions (SCHM-03)
-- ═══════════════════════════════════════════════════════
-- Append-only history of canonical block bodies. Each row is one synthesis attempt.
-- Pinned columns (D-11): body_md, synthesized_from_through, proposed_maturity,
-- validator_report, block_slug. Lifecycle columns (D-12, mutable): status, published_at.
--
-- The append-only invariant on the pinned columns is enforced by a BEFORE UPDATE OR
-- DELETE trigger (Section 8), NOT by RLS. See the loud comment block in Section 8 for
-- the rationale.

CREATE TABLE IF NOT EXISTS economy_map.block_body_versions (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    block_slug                  TEXT NOT NULL REFERENCES economy_map.blocks(slug) ON DELETE RESTRICT,  -- pinned per D-11
    body_md                     TEXT NOT NULL,                                                          -- pinned per D-11
    status                      TEXT NOT NULL DEFAULT 'draft'
                                CHECK (status IN ('draft','published','superseded')),                  -- lifecycle column per D-12
    proposed_maturity           economy_map.maturity NOT NULL,                                          -- pinned per D-11
    synthesized_from_through    TIMESTAMPTZ,                                                            -- pinned per D-11 (upper bound of entry window consumed)
    validator_report            JSONB NOT NULL DEFAULT '{}'::jsonb,                                    -- pinned per D-11 (populated by Phase 8 sentinels)
    published_at                TIMESTAMPTZ,                                                            -- lifecycle column per D-12
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_block_body_versions_slug_status
    ON economy_map.block_body_versions(block_slug, status);
CREATE INDEX IF NOT EXISTS idx_block_body_versions_status
    ON economy_map.block_body_versions(status) WHERE status = 'draft';   -- partial index for /map-pending queries

-- ═══════════════════════════════════════════════════════
-- SECTION 6 — Cross-table FK: blocks.current_body_version_id → block_body_versions.id
-- ═══════════════════════════════════════════════════════
-- Deferred to here because block_body_versions did not exist when blocks was created.
-- Wrapped in DO $$ … EXCEPTION pattern (mirrors 004 lines 241–256) for replay safety
-- regardless of whether ADD CONSTRAINT IF NOT EXISTS is supported on the Postgres version.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM information_schema.table_constraints
         WHERE constraint_name = 'blocks_current_body_version_id_fkey'
           AND table_schema   = 'economy_map'
           AND table_name     = 'blocks'
    ) THEN
        BEGIN
            ALTER TABLE economy_map.blocks
                ADD CONSTRAINT blocks_current_body_version_id_fkey
                FOREIGN KEY (current_body_version_id)
                REFERENCES economy_map.block_body_versions(id)
                ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END;
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════
-- SECTION 7 — economy_map.timeline_entries (SCHM-04, SCHM-08, D-11)
-- ═══════════════════════════════════════════════════════
-- Append-only narrative ledger. Every column is pinned (D-11) — this table is fully
-- immutable post-INSERT. The block_slug is intentionally NOT a foreign key because
-- 'unsorted' is a valid value (SCHM-08 / D-07) for low-confidence classifier output
-- awaiting Phase 10 /map-assign triage.

CREATE TABLE IF NOT EXISTS economy_map.timeline_entries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    block_slug          TEXT NOT NULL,                          -- NOT a FK: 'unsorted' is valid (SCHM-08 / D-07)
    event_date          DATE NOT NULL,
    what_shifted        TEXT NOT NULL,
    why_it_mattered     TEXT NOT NULL,
    source_url          TEXT,
    source_edition_id   TEXT,                                   -- text for cross-schema flexibility (NOT a FK to public.newsletters)
    tag_confidence      NUMERIC(3,2),                           -- 0.00..1.00; populated by Phase 5 classifier (INTK-03)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_timeline_entries_block_slug_event_date
    ON economy_map.timeline_entries(block_slug, event_date DESC);   -- newest-first per REQ-TIMELINE-NEWEST / RNDR-07

-- ═══════════════════════════════════════════════════════
-- SECTION 8 — Append-only triggers (FIRST IN-TREE PRECEDENT — D-10 / D-14)
-- ═══════════════════════════════════════════════════════
-- APPEND-ONLY ENFORCEMENT — INTENTIONALLY NOT RLS
-- ═══════════════════════════════════════════════════════
-- Content immutability must hold AGAINST service_role, not just anon.
-- service_role bypasses RLS by design (see migration 006 strategy comment).
-- The pipeline that produced the 27-day silent wallet bug ran as service_role.
-- See `.planning/PROJECT.md` "Recent history that shapes design".
--
-- Therefore: BEFORE UPDATE / BEFORE DELETE triggers, NOT a stricter RLS policy.
-- A future developer WILL try to "simplify" this to RLS. Do not.
-- ═══════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION economy_map.block_body_versions_append_only()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- DELETE is never allowed on this table.
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'block_body_versions is append-only (DELETE not permitted)';
    END IF;

    -- For UPDATE: only the lifecycle columns (status, published_at) may change.
    IF NEW.body_md IS DISTINCT FROM OLD.body_md THEN
        RAISE EXCEPTION 'block_body_versions.body_md is append-only (was %, now %)', OLD.body_md, NEW.body_md;
    END IF;
    IF NEW.synthesized_from_through IS DISTINCT FROM OLD.synthesized_from_through THEN
        RAISE EXCEPTION 'block_body_versions.synthesized_from_through is append-only';
    END IF;
    IF NEW.proposed_maturity IS DISTINCT FROM OLD.proposed_maturity THEN
        RAISE EXCEPTION 'block_body_versions.proposed_maturity is append-only';
    END IF;
    IF NEW.validator_report IS DISTINCT FROM OLD.validator_report THEN
        RAISE EXCEPTION 'block_body_versions.validator_report is append-only';
    END IF;
    IF NEW.block_slug IS DISTINCT FROM OLD.block_slug THEN
        RAISE EXCEPTION 'block_body_versions.block_slug is append-only';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS block_body_versions_append_only_trg ON economy_map.block_body_versions;
CREATE TRIGGER block_body_versions_append_only_trg
BEFORE UPDATE OR DELETE ON economy_map.block_body_versions
FOR EACH ROW EXECUTE FUNCTION economy_map.block_body_versions_append_only();

CREATE OR REPLACE FUNCTION economy_map.timeline_entries_append_only()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- DELETE is never allowed on this table.
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'timeline_entries is append-only (DELETE not permitted)';
    END IF;

    -- For UPDATE: every column on this table is pinned (no lifecycle columns).
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

DROP TRIGGER IF EXISTS timeline_entries_append_only_trg ON economy_map.timeline_entries;
CREATE TRIGGER timeline_entries_append_only_trg
BEFORE UPDATE OR DELETE ON economy_map.timeline_entries
FOR EACH ROW EXECUTE FUNCTION economy_map.timeline_entries_append_only();

-- ═══════════════════════════════════════════════════════
-- SECTION 9 — economy_map.publish_block_version (RPC; D-15..D-17 / D-19 / SCHM-06)
-- ═══════════════════════════════════════════════════════
-- SECURITY DEFINER so service_role-only callers (Phase 9 /map-approve) can flip
-- draft → published, supersede prior published rows, and update the parent block in
-- one atomic transaction.
--
-- SET search_path = economy_map, public is a T-02 mitigation NOT present in the
-- 013/015 in-tree analogs: it pins schema resolution so a hostile caller cannot
-- poison the search_path and resolve economy_map.blocks to an attacker-owned shadow
-- table. Phase 2 establishes this safer pattern (see 02-PATTERNS.md §7).

CREATE OR REPLACE FUNCTION economy_map.publish_block_version(p_version_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = economy_map, public
AS $$
DECLARE
    v_slug      text;
    v_maturity  economy_map.maturity;
BEGIN
    -- Step 1: atomic draft → published flip. RETURNING is empty if the row is not
    -- found or not in draft status — that's how concurrent publish-races lose
    -- (T-02-05 mitigation, single-winner property).
    UPDATE economy_map.block_body_versions
       SET status        = 'published',
           published_at  = NOW()
     WHERE id     = p_version_id
       AND status = 'draft'
    RETURNING block_slug, proposed_maturity
      INTO v_slug, v_maturity;

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

    -- Step 4: point the block at the new current version + sync maturity + bump timestamp.
    UPDATE economy_map.blocks
       SET current_body_version_id = p_version_id,
           maturity                = v_maturity,
           last_synthesized_at     = NOW()
     WHERE slug = v_slug;
END;
$$;

REVOKE ALL ON FUNCTION economy_map.publish_block_version(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION economy_map.publish_block_version(uuid) TO service_role;

-- ═══════════════════════════════════════════════════════
-- SECTION 10 — economy_map.reject_block_version (RPC; D-16 / D-18 / D-19)
-- ═══════════════════════════════════════════════════════
-- SECURITY DEFINER for the same reasons as publish. Body intentionally simpler:
-- mark the draft as superseded and stop — timeline entries for this block remain
-- unabsorbed, and the next synthesis pass re-reads them (D-18; Phase 9 GATE-03).

CREATE OR REPLACE FUNCTION economy_map.reject_block_version(p_version_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = economy_map, public
AS $$
DECLARE
    v_slug text;
BEGIN
    UPDATE economy_map.block_body_versions
       SET status = 'superseded'
     WHERE id     = p_version_id
       AND status = 'draft'
    RETURNING block_slug
      INTO v_slug;

    IF v_slug IS NULL THEN
        RAISE EXCEPTION 'version % not found or not in draft status', p_version_id;
    END IF;
END;
$$;

REVOKE ALL ON FUNCTION economy_map.reject_block_version(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION economy_map.reject_block_version(uuid) TO service_role;

-- ═══════════════════════════════════════════════════════
-- SECTION 11 — Row-Level Security (D-05 / D-06 / D-07; T-02-03 / T-02-04 mitigations)
-- ═══════════════════════════════════════════════════════
-- Strategy:
--   - service_role bypasses RLS by design (D-08; agents use SUPABASE_SERVICE_KEY —
--     inheriting the migration 006 posture, no change here).
--   - anon-read policies define what the browser sees.
--   - Drafts and 'unsorted' entries are hidden from anon by RLS.
--   - Content immutability is enforced by the triggers above (Section 8), not RLS —
--     RLS cannot bind service_role.
--   - No public-schema filtered views: anon uses Accept-Profile: economy_map (D-09).

ALTER TABLE economy_map.blocks               ENABLE ROW LEVEL SECURITY;
ALTER TABLE economy_map.block_body_versions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE economy_map.timeline_entries     ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS blocks_anon_read ON economy_map.blocks;
CREATE POLICY blocks_anon_read ON economy_map.blocks
    FOR SELECT
    TO anon
    USING (true);

DROP POLICY IF EXISTS block_body_versions_anon_read ON economy_map.block_body_versions;
CREATE POLICY block_body_versions_anon_read ON economy_map.block_body_versions
    FOR SELECT
    TO anon
    USING (status = 'published');

DROP POLICY IF EXISTS timeline_entries_anon_read ON economy_map.timeline_entries;
CREATE POLICY timeline_entries_anon_read ON economy_map.timeline_entries
    FOR SELECT
    TO anon
    USING (block_slug <> 'unsorted');

-- ═══════════════════════════════════════════════════════
-- SECTION 12 — Table-level grants
-- ═══════════════════════════════════════════════════════
-- PostgREST requires BOTH an RLS pass AND a SELECT GRANT — the grant on the new
-- schema must be explicit (unlike public, where anon already has grants).

GRANT SELECT ON economy_map.blocks               TO anon;
GRANT SELECT ON economy_map.block_body_versions  TO anon;
GRANT SELECT ON economy_map.timeline_entries     TO anon;

GRANT ALL ON ALL TABLES IN SCHEMA economy_map TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA economy_map TO service_role;

-- ═══════════════════════════════════════════════════════
-- SECTION 13 — Seven-block idempotent seed (D-20..D-23)
-- ═══════════════════════════════════════════════════════
-- Structural fields are locked (slugs, tiers, accents, sort_orders per D-23);
-- live_tension carries the grep-friendly placeholder 'TBD — set via /map-tension'
-- per D-21 — Phase 10 /map-tension is the only path that mutates it.
--
-- ON CONFLICT (slug) DO NOTHING is the right idempotency posture (NOT DO UPDATE)
-- because re-running the migration must NOT clobber operator-set live_tension copy
-- (D-20 / D-21).

INSERT INTO economy_map.blocks
    (slug, tier, title, subtitle, accent, sort_order, live_tension, maturity)
VALUES
    -- Substrate (tier=substrate, accent=teal)
    ('identity-trust',            'substrate', 'Identity & Trust',            'Who is the agent and why should we believe them?',                              'teal',   1, 'TBD — set via /map-tension', 'nascent'::economy_map.maturity),
    ('memory-context',            'substrate', 'Memory & Context',            'What does the agent remember, and what shapes its judgment?',                   'teal',   2, 'TBD — set via /map-tension', 'nascent'::economy_map.maturity),
    ('payments-settlement',       'substrate', 'Payments & Settlement',       'How do agents pay each other (and negotiate to do so)?',                        'teal',   3, 'TBD — set via /map-tension', 'nascent'::economy_map.maturity),
    -- Behavior (tier=behavior, accents purple+coral)
    ('autonomy-control',          'behavior',  'Autonomy & Control',          'Where does the agent get to decide, and where is it gated?',                    'purple', 4, 'TBD — set via /map-tension', 'nascent'::economy_map.maturity),
    ('governance-accountability', 'behavior',  'Governance & Accountability', 'Who is on the hook when an agent acts?',                                        'purple', 5, 'TBD — set via /map-tension', 'nascent'::economy_map.maturity),
    ('psychology-disposition',    'behavior',  'Psychology & Disposition',    'What kind of mind is the agent, and how does it behave under pressure?',        'coral',  6, 'TBD — set via /map-tension', 'nascent'::economy_map.maturity),
    -- Frame (tier=frame, accent=gray)
    ('regulation-legal',          'frame',     'Regulation & Legal',          'What does the legal frame around the agent economy look like?',                 'gray',   7, 'TBD — set via /map-tension', 'nascent'::economy_map.maturity)
ON CONFLICT (slug) DO NOTHING;

-- ═══════════════════════════════════════════════════════
-- SECTION 14 — Closing
-- ═══════════════════════════════════════════════════════
-- End migration 033: economy_map schema landed. Verification exercised in .planning/phases/02-economy-map-schema-seven-block-seed/02-VERIFY.sql (Plan 02-02).
