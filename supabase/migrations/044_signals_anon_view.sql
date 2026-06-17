-- Migration 044: public.signals_feed — narrow anon read path for tier-1 source links.
-- Phase 24 signals-section / Plan 24-01 (lands SIGNAL-04; encodes D-01 / D-02 / D-04).
--
-- This migration opens the milestone's ONLY new anon read path: a view exposing a
-- deliberately-narrow slice of source_posts so the public site's #signals feed can
-- render real tier-1 links. It performs, in this exact order:
--   (a) CREATE OR REPLACE the view public.signals_feed over source_posts.
--   (b) GRANT SELECT on that view to the anon role.
--
-- What it exposes (D-01): ONLY the 5 whitelisted columns — id, title, source_url,
-- source, scraped_at — for tier-1, genuinely-linkable rows. The column ceiling lives
-- HERE, in the view body, NOT in the frontend select: RLS is row-level and cannot hide
-- columns, so the operator's rule "RLS can't hide columns" is satisfied structurally by
-- the explicit column list. body (full scraped text — copyright/leak risk), metadata
-- (internal extraction JSONB), score, author, comment_count, and tags are therefore
-- never reachable by the anon key through this view.
--
-- What it does NOT touch (D-01): the base source_posts table is untouched. RLS stays
-- ENABLED with no anon policy (006:21), so anon reading source_posts directly returns
-- zero rows. This file emits no ALTER TABLE / CREATE POLICY against source_posts.
--
-- Execution-rights rationale (LOAD-BEARING): this is a security-DEFINER view — the
-- Postgres default. Do NOT add an invoker-rights clause. A plain CREATE OR REPLACE VIEW
-- runs as the view owner (the migration role = postgres = the source_posts owner), which
-- bypasses the base-table RLS and returns the whitelisted set. An invoker-rights view
-- would instead run as the calling anon role, hit source_posts' RLS-with-no-anon-policy,
-- and return ZERO rows forever — a silent, permanently-empty feed (a fail-loud violation).
-- The exposure boundary is the column list + WHERE clause below, NOT RLS.
--
-- Row ceiling: WHERE source_tier = 1 (D-01 — tier-1 authority sources only; 1=authority,
-- 2=curated, 3=community per 004:14) AND source_url IS NOT NULL (D-02 — every Signals row
-- must BE a safe external link, so only genuinely-linkable rows count toward the cap).
-- Ordering: newest-first, scraped_at DESC with id DESC as a stable tie-break (D-04).
-- scraped_at is the only reliable temporal column (source_posts has no published_at; any
-- source-published date lives in the unexposed metadata JSONB). This predicate is backed
-- by idx_source_posts_tier_scraped (source_tier, scraped_at DESC) from migration 005 —
-- no new index is needed.
--
-- Idempotency: CREATE OR REPLACE VIEW + GRANT SELECT are replay-safe (re-running this
-- migration redefines the same view and re-grants the same privilege, no-op on a match).
--
-- Live apply note: the LIVE apply of this migration is orchestrator-owned and lands in
-- Plan 24-03 (worktree-unsafe). This file is source only.

CREATE OR REPLACE VIEW public.signals_feed AS
SELECT id, title, source_url, source, scraped_at
FROM source_posts
WHERE source_tier = 1
  AND source_url IS NOT NULL
ORDER BY scraped_at DESC, id DESC;

GRANT SELECT ON public.signals_feed TO anon;
