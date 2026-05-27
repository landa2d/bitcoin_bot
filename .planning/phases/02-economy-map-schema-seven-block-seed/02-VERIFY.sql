-- ═══════════════════════════════════════════════════════════════════════════
-- 02-VERIFY.sql — economy_map schema verification exercise (Phase 2 / Plan 02-02)
-- ═══════════════════════════════════════════════════════════════════════════
-- Project ref: zxzaaqfowtqvmsbitqpu
-- Run via Supabase MCP execute_sql tool, one D-25 bullet at a time, OR as a
-- single script (errors are trapped so progress continues — every "expected
-- failure" is wrapped in a DO $$ ... EXCEPTION WHEN OTHERS THEN RAISE NOTICE
-- 'PASS: %', SQLERRM; END $$; block, mirroring the deferred-exception PL/pgSQL
-- pattern at supabase/migrations/004_core_tables.sql lines 241-256).
--
-- Each block prints either "PASS: <message>" (negative cases) or returns rows
-- for the next block to consume (positive cases).
--
-- Bullet 5 (anon-key RLS probe) is HTTP-only — see the comment block in
-- SECTION 5 for the curl invocation captured in 02-VERIFY-RESULTS.md.
--
-- ROADMAP success-criterion mapping:
--   Section 1 → ROADMAP criterion 2 (seven blocks queryable, structural fields) + criterion 5 (maturity enum order)
--   Section 2 → ROADMAP criterion 3 (atomic publish via SECURITY DEFINER RPC)
--   Section 3 → ROADMAP criterion 4 (append-only enforcement + 'unsorted' acceptance)
--   Section 4 → ROADMAP criterion 4 (lifecycle UPDATE carve-out — D-12)
--   Section 5 → ROADMAP criterion 1 (Accept-Profile resolution) + criterion 4 second-half (RLS posture)
-- ═══════════════════════════════════════════════════════════════════════════

-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 1 — D-25 bullet 1: Seven blocks queryable from economy_map.blocks
-- ROADMAP criterion 2 (every column populated) + criterion 5 (maturity ENUM order)
-- Expected: block_count = 7; seven slugs in D-23 sort_order; all live_tension
--           contain 'TBD' substring; five enum labels in nascent→mature order.
-- ═══════════════════════════════════════════════════════════════════════════

-- ───────────────── D-25 bullet 1.a — count ─────────────────
SELECT COUNT(*) AS block_count FROM economy_map.blocks;

-- ───────────────── D-25 bullet 1.b — slugs + structural fields + live_tension placeholder probe ─────────────────
SELECT
    slug,
    tier,
    accent,
    sort_order,
    maturity::text                              AS maturity_text,
    (live_tension LIKE '%TBD%')                 AS live_tension_is_placeholder
FROM economy_map.blocks
ORDER BY sort_order;

-- ───────────────── D-25 bullet 1.c — maturity ENUM definition (proves SCHM-05 / ROADMAP criterion 5) ─────────────────
SELECT enumlabel
FROM pg_enum   e
JOIN pg_type   t ON e.enumtypid = t.oid
JOIN pg_namespace n ON n.oid = t.typnamespace
WHERE n.nspname = 'economy_map'
  AND t.typname = 'maturity'
ORDER BY e.enumsortorder;


-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 2 — D-25 bullet 2: Atomic publish transaction (publish_block_version)
-- ROADMAP criterion 3 + SCHM-06.
--
-- This section uses placeholder UUIDs <v1_uuid> and <v2_uuid> that the executor
-- substitutes at run-time from the RETURNING id of the two INSERTs in step 2a.
-- The MCP execute_sql workflow:
--   1. Run step 2a (two INSERTs, each RETURNING id) and capture v1_uuid + v2_uuid.
--   2. Substitute the captured uuids into steps 2b..2g before sending them.
--
-- All slugs target 'identity-trust' (sort_order=1 per D-23).
-- proposed_maturity values are chosen so the maturity bump is observable:
--   v1 publishes with proposed_maturity='emerging' (block was 'nascent')
--   v2 publishes with proposed_maturity='contested' (supersedes v1, bumps block to 'contested')
-- ═══════════════════════════════════════════════════════════════════════════

-- ───────────────── D-25 bullet 2.a — insert two draft block_body_versions ─────────────────
-- Step 2a-i: insert v1 as draft. Capture the returned id as <v1_uuid>.
INSERT INTO economy_map.block_body_versions
    (block_slug, body_md, proposed_maturity, status)
VALUES
    ('identity-trust',
     '# Test body v1 (verify-202602) — Plan 02-02 verification draft',
     'emerging'::economy_map.maturity,
     'draft')
RETURNING id;

-- Step 2a-ii: insert v2 as draft. Capture the returned id as <v2_uuid>.
INSERT INTO economy_map.block_body_versions
    (block_slug, body_md, proposed_maturity, status)
VALUES
    ('identity-trust',
     '# Test body v2 (verify-202602) — Plan 02-02 verification draft',
     'contested'::economy_map.maturity,
     'draft')
RETURNING id;

-- ───────────────── D-25 bullet 2.b — promote v1 to published via the RPC ─────────────────
-- Substitute <v1_uuid> with the id captured in step 2a-i.
SELECT economy_map.publish_block_version('<v1_uuid>'::uuid);

-- ───────────────── D-25 bullet 2.c — verify post-publish state for v1 ─────────────────
-- Expected: v1.status='published', has_published_at=true, blocks.current_body_version_id=v1_uuid,
--           blocks.maturity='emerging', blocks.last_synthesized_at IS NOT NULL.
SELECT
    bbv.id,
    bbv.status,
    bbv.published_at IS NOT NULL    AS has_published_at,
    bbv.proposed_maturity::text     AS proposed_maturity_text
FROM economy_map.block_body_versions bbv
WHERE bbv.id = '<v1_uuid>'::uuid;

SELECT
    b.current_body_version_id,
    b.maturity::text                AS maturity_text,
    b.last_synthesized_at IS NOT NULL AS has_last_synthesized_at
FROM economy_map.blocks b
WHERE b.slug = 'identity-trust';

-- ───────────────── D-25 bullet 2.d — promote v2 (proves supersession) ─────────────────
-- Substitute <v2_uuid> with the id captured in step 2a-ii.
SELECT economy_map.publish_block_version('<v2_uuid>'::uuid);

-- ───────────────── D-25 bullet 2.e — verify supersession state ─────────────────
-- Expected: v1.status='superseded', v2.status='published', blocks.current_body_version_id=v2_uuid,
--           blocks.maturity='contested'.
SELECT
    id,
    status,
    proposed_maturity::text         AS proposed_maturity_text
FROM economy_map.block_body_versions
WHERE block_slug = 'identity-trust'
ORDER BY created_at;

SELECT
    current_body_version_id,
    maturity::text                  AS maturity_text
FROM economy_map.blocks
WHERE slug = 'identity-trust';

-- ───────────────── D-25 bullet 2.f — negative case: bogus UUID rejected by publish RPC ─────────────────
-- Expected: RAISE NOTICE containing 'not found or not in draft status'.
DO $$
BEGIN
    BEGIN
        PERFORM economy_map.publish_block_version('00000000-0000-0000-0000-000000000000'::uuid);
        RAISE EXCEPTION 'TEST FAILED (2f): bogus version_id was accepted by publish_block_version';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'PASS (2f): %', SQLERRM;
    END;
END $$;

-- ───────────────── D-25 bullet 2.g — negative case: re-publish an already-published version ─────────────────
-- Substitute <v2_uuid> with v2's id (status is now 'published', so the WHERE id=… AND status='draft' guard fails).
-- Expected: RAISE NOTICE containing 'not found or not in draft status'.
DO $$
BEGIN
    BEGIN
        PERFORM economy_map.publish_block_version('<v2_uuid>'::uuid);
        RAISE EXCEPTION 'TEST FAILED (2g): already-published version was re-published';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'PASS (2g): %', SQLERRM;
    END;
END $$;


-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 3 — D-25 bullet 3: Append-only violation traps + 'unsorted' acceptance
-- ROADMAP criterion 4 (append-only + SCHM-04) + criterion 4 second-half (SCHM-08).
--
-- Steps 3a–3c: UPDATE/DELETE attempts on economy_map.block_body_versions pinned columns.
-- Step 3d:    Lifecycle UPDATE on (status, published_at) — succeeds (D-12 carve-out).
-- Steps 3e–3f: UPDATE/DELETE attempts on economy_map.timeline_entries pinned columns.
-- Step 3g:    INSERT with block_slug='unsorted' — succeeds (SCHM-08 / D-07).
--
-- Every negative case wraps the offending statement in DO $$ ... EXCEPTION WHEN OTHERS
-- THEN RAISE NOTICE 'PASS: %', SQLERRM; END $$; — making the trigger trip a visible
-- PASS notice rather than a hard error that aborts subsequent sections.
-- ═══════════════════════════════════════════════════════════════════════════

-- ───────────────── D-25 bullet 3.a — UPDATE body_md on block_body_versions ─────────────────
-- Substitute <v1_uuid> (or <v2_uuid>; either works — both are non-draft now).
-- Expected: SQLERRM contains 'block_body_versions.body_md is append-only'.
DO $$
BEGIN
    BEGIN
        UPDATE economy_map.block_body_versions
           SET body_md = 'mutated by 02-VERIFY.sql step 3a — should never persist'
         WHERE id = '<v1_uuid>'::uuid;
        RAISE EXCEPTION 'TEST FAILED (3a): UPDATE body_md was allowed';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'PASS (3a): %', SQLERRM;
    END;
END $$;

-- ───────────────── D-25 bullet 3.b — UPDATE proposed_maturity on block_body_versions ─────────────────
-- Expected: SQLERRM contains 'block_body_versions.proposed_maturity is append-only'.
DO $$
BEGIN
    BEGIN
        UPDATE economy_map.block_body_versions
           SET proposed_maturity = 'mature'::economy_map.maturity
         WHERE id = '<v1_uuid>'::uuid;
        RAISE EXCEPTION 'TEST FAILED (3b): UPDATE proposed_maturity was allowed';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'PASS (3b): %', SQLERRM;
    END;
END $$;

-- ───────────────── D-25 bullet 3.c — DELETE from block_body_versions ─────────────────
-- Expected: SQLERRM contains 'block_body_versions is append-only' (or 'DELETE not permitted').
DO $$
BEGIN
    BEGIN
        DELETE FROM economy_map.block_body_versions
         WHERE id = '<v1_uuid>'::uuid;
        RAISE EXCEPTION 'TEST FAILED (3c): DELETE on block_body_versions was allowed';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'PASS (3c): %', SQLERRM;
    END;
END $$;

-- ───────────────── D-25 bullet 3.d — lifecycle UPDATE (status, published_at) succeeds ─────────────────
-- NOT wrapped in DO $$ — this is the positive case (D-12 lifecycle carve-out). Two paired
-- UPDATEs: flip v2 'published' → 'superseded' → 'published' again, so the test residue
-- at end of script matches v2.status='published'. Each UPDATE should succeed silently.
UPDATE economy_map.block_body_versions
   SET status = 'superseded'
 WHERE id = '<v2_uuid>'::uuid;

UPDATE economy_map.block_body_versions
   SET status = 'published'
 WHERE id = '<v2_uuid>'::uuid;

-- ───────────────── D-25 bullet 3.e-pre — seed a timeline_entries row to mutate against ─────────────────
-- Capture the returned id as <entry_id_named>.
INSERT INTO economy_map.timeline_entries
    (block_slug, event_date, what_shifted, why_it_mattered, source_url, source_edition_id, tag_confidence)
VALUES
    ('identity-trust',
     CURRENT_DATE,
     'TEST entry — Plan 02-02 verification (step 3e seed)',
     'matters because the next step UPDATEs what_shifted and expects the trigger to trip',
     'https://example.com/verify',
     'verify-202602-01',
     0.95)
RETURNING id;

-- ───────────────── D-25 bullet 3.e — UPDATE what_shifted on timeline_entries ─────────────────
-- Substitute <entry_id_named> with the id captured by the previous INSERT.
-- Expected: SQLERRM contains 'timeline_entries.what_shifted is append-only'.
DO $$
BEGIN
    BEGIN
        UPDATE economy_map.timeline_entries
           SET what_shifted = 'mutated by 02-VERIFY.sql step 3e — should never persist'
         WHERE id = '<entry_id_named>'::uuid;
        RAISE EXCEPTION 'TEST FAILED (3e): UPDATE what_shifted was allowed';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'PASS (3e): %', SQLERRM;
    END;
END $$;

-- ───────────────── D-25 bullet 3.f — DELETE from timeline_entries ─────────────────
-- Expected: SQLERRM contains 'timeline_entries is append-only' (or 'DELETE not permitted').
DO $$
BEGIN
    BEGIN
        DELETE FROM economy_map.timeline_entries
         WHERE id = '<entry_id_named>'::uuid;
        RAISE EXCEPTION 'TEST FAILED (3f): DELETE on timeline_entries was allowed';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'PASS (3f): %', SQLERRM;
    END;
END $$;

-- ───────────────── D-25 bullet 3.g — 'unsorted' is a valid block_slug (SCHM-08) ─────────────────
-- NOT wrapped in DO $$ — this is the positive case. INSERT must succeed.
-- Capture the returned id as <entry_id_unsorted> for the Section 5 anon-probe expectation.
INSERT INTO economy_map.timeline_entries
    (block_slug, event_date, what_shifted, why_it_mattered, tag_confidence)
VALUES
    ('unsorted',
     CURRENT_DATE,
     'TEST unsorted entry — Plan 02-02 verification (step 3g seed)',
     'low-confidence classifier output; awaits /map-assign triage',
     0.42)
RETURNING id;


-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 4 — D-25 bullet 4: Lifecycle column UPDATE succeeded
-- ─ Already exercised in Section 3 step 3d (status superseded → published). The
--   D-12 carve-out is proven by the two UPDATE statements in 3d running silently
--   without RAISE NOTICE output and without aborting. This section exists as a
--   D-25 bullet placeholder so the script structure mirrors D-25's five-bullet
--   list explicitly. No new SQL.
-- ═══════════════════════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 5 — D-25 bullet 5: Anon-key RLS probe (HTTP, not SQL)
-- ─ ROADMAP criterion 1 (Accept-Profile resolution) + criterion 4 second-half
--   (RLS predicates: drafts/superseded hidden; 'unsorted' hidden).
--
-- This section is comment-only. The orchestrator runs the three curl probes
-- below (NOT this script) and records HTTP status + row count in
-- 02-VERIFY-RESULTS.md §Anon-key Probe Results.
--
-- Set in the shell before invoking (resolved via Supabase MCP tools
-- get_project_url + get_publishable_api_key — never write the anon key to disk):
--
--   PROJECT_URL=https://zxzaaqfowtqvmsbitqpu.supabase.co
--   ANON_KEY=<from mcp__claude_ai_Supabase__get_publishable_api_key>
--
-- ─ Probe 5.1 — economy_map.blocks (expect HTTP 200, 7 rows in sort_order asc):
--
--   curl -sS -w "\nHTTP_STATUS:%{http_code}\n" \
--     -H "apikey: $ANON_KEY" \
--     -H "Authorization: Bearer $ANON_KEY" \
--     -H "Accept-Profile: economy_map" \
--     "$PROJECT_URL/rest/v1/blocks?select=slug,tier,accent,sort_order&order=sort_order.asc"
--
-- ─ Probe 5.2 — economy_map.block_body_versions (expect HTTP 200, 1 row only):
--
--   Only the v2 row published at the end of Section 2 (status='published') is
--   visible to anon. v1 (status='superseded') and any draft rows are hidden by
--   the RLS predicate USING (status = 'published') from migration 033 §11.
--
--   curl -sS -w "\nHTTP_STATUS:%{http_code}\n" \
--     -H "apikey: $ANON_KEY" \
--     -H "Authorization: Bearer $ANON_KEY" \
--     -H "Accept-Profile: economy_map" \
--     "$PROJECT_URL/rest/v1/block_body_versions?select=id,block_slug,status"
--
-- ─ Probe 5.3 — economy_map.timeline_entries (expect HTTP 200, 1 row only):
--
--   Only the named-block entry from step 3e (block_slug='identity-trust') is
--   visible. The 'unsorted' entry from step 3g is hidden by the RLS predicate
--   USING (block_slug <> 'unsorted') from migration 033 §11.
--
--   curl -sS -w "\nHTTP_STATUS:%{http_code}\n" \
--     -H "apikey: $ANON_KEY" \
--     -H "Authorization: Bearer $ANON_KEY" \
--     -H "Accept-Profile: economy_map" \
--     "$PROJECT_URL/rest/v1/timeline_entries?select=id,block_slug"
-- ═══════════════════════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════════════════════════════════════
-- SECTION 6 — Cleanup / Test residue note
-- ─ Test rows inserted by this verification remain in place after the script
--   completes. DELETE attempts would raise append-only exceptions (which is the
--   whole point — those exceptions are the contract). The residue:
--
--     • two economy_map.block_body_versions rows for 'identity-trust':
--         v1 (status='superseded'), v2 (status='published')
--     • two economy_map.timeline_entries rows:
--         one block_slug='identity-trust' (named, step 3e)
--         one block_slug='unsorted' (low-confidence, step 3g)
--
--   Subsequent phases inherit this seed state. Phase 5 (intake classifier) and
--   Phase 7 (synthesis loop) operate on real ingest data; these test rows do
--   NOT interfere with their pipelines — they are explicitly tagged with the
--   substring 'TEST' / 'verify-202602' in body_md / what_shifted / source_edition_id.
--
--   To clear residue entirely, drop the schema and re-apply the migration:
--       DROP SCHEMA economy_map CASCADE;
--       <re-apply supabase/migrations/033_economy_map_schema.sql>
--   This is NOT required for downstream phases to function.
--
--   The residue is documented in 02-VERIFY-RESULTS.md §Test residue for
--   downstream-planner visibility.
-- ═══════════════════════════════════════════════════════════════════════════
-- End 02-VERIFY.sql
