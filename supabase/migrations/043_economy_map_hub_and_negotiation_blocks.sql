-- Migration 043: economy_map hub + negotiation blocks-row structure.
-- Phase 16 content-load-unpublished / Plan 16-01 (lands D-02 + D-04).
--
-- This migration owns ALL blocks-row STRUCTURE for the Phase 16 content load, in ONE
-- atomic transaction. It is the structural prerequisite the standalone body loader
-- (Plan 02/03) depends on: every block_body_versions.block_slug FK target the loader
-- writes (the new hub + negotiation rows) must already exist before the loader runs.
-- The loader inserts BODIES ONLY and creates zero blocks rows — this file carries no
-- body content (no block_body_versions, no body_md).
--
-- economy_map.blocks has NO append-only trigger (the 2 append-only triggers in 033 §8
-- are on block_body_versions + timeline_entries only), so the UPDATE/INSERT writes here
-- are permitted plain writes by design (D-02).
--
-- It performs, in this exact order:
--   (a) Tier-CHECK relax — admit a 'hub' sentinel tier (D-04 Option-A hub accommodation;
--       the original inline CHECK at 033:68 is `tier IN ('substrate','behavior','frame')`
--       and is auto-named blocks_tier_check by Postgres).
--   (b) sort_order reshuffle — HIGHEST-FIRST, and BEFORE the INSERT. sort_order is UNIQUE
--       (033:72), so the reshuffle MUST run highest-target-first to vacate slot 5 without
--       ever transiently colliding the UNIQUE constraint: regulation-legal 7→8, then
--       psychology-disposition 6→7, then governance-accountability 5→6 (this frees slot 5).
--   (c) INSERT the hub (sort_order=0) + negotiation (sort_order=5) rows into the now
--       collision-free order space — final {0..8} contiguous.
--
-- Idempotency: DROP CONSTRAINT IF EXISTS + ON CONFLICT (slug) DO NOTHING make the
-- migration safe to replay; ON CONFLICT (slug) DO NOTHING (NOT DO UPDATE) so a re-run
-- never clobbers operator-set live_tension / editorial copy (033:398-400 convention).

-- (a) Tier-CHECK relax: admit the 'hub' sentinel tier (027:4-6 DROP-then-ADD idiom).
ALTER TABLE economy_map.blocks DROP CONSTRAINT IF EXISTS blocks_tier_check;
ALTER TABLE economy_map.blocks ADD CONSTRAINT blocks_tier_check
  CHECK (tier IN ('substrate','behavior','frame','hub'));

-- (b) Collision-free sort_order reshuffle — HIGHEST-FIRST, BEFORE the INSERT.
-- sort_order is UNIQUE (033:72); vacate slot 5 for negotiation without a transient collision.
UPDATE economy_map.blocks SET sort_order = 8 WHERE slug = 'regulation-legal';          -- live 7→8
UPDATE economy_map.blocks SET sort_order = 7 WHERE slug = 'psychology-disposition';     -- live 6→7
UPDATE economy_map.blocks SET sort_order = 6 WHERE slug = 'governance-accountability';  -- live 5→6 (vacates slot 5)

-- (c) INSERT the two new blocks rows at the now-vacant order space (hub=0, negotiation=5).
-- title/subtitle are taken VERBATIM from the .md frontmatter (the metadata source of truth):
--   hub          → .planning/docs/00-hub.md
--   negotiation  → .planning/docs/05-negotiation-coordination.md  (apostrophe SQL-escaped as '')
-- accent: hub='gray' (D-04 reconciliation example); negotiation='coral' (behavior palette;
--   accent has no UNIQUE constraint, so sharing 'coral' with psychology is permitted).
-- live_tension: the seed placeholder 'TBD — set via /map-tension' (033:73 / D-05), populated
--   later via the /map-tension command surface.
INSERT INTO economy_map.blocks
    (slug, tier, title, subtitle, accent, sort_order, live_tension, maturity)
VALUES
    ('agent-economy',             'hub',      'The Agent Economy',         'Capability is solved. Trust and coordination are not.', 'gray',  0, 'TBD — set via /map-tension', 'nascent'::economy_map.maturity),
    ('negotiation-coordination',  'behavior', 'Negotiation & Coordination', 'The market between strangers that doesn''t exist yet.',  'coral', 5, 'TBD — set via /map-tension', 'nascent'::economy_map.maturity)
ON CONFLICT (slug) DO NOTHING;
