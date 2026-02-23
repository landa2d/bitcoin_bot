-- Migration 005: Missing database indexes for query performance
-- These indexes support polling agents and common query patterns.
-- All are safe to run online (no table locks on Postgres index creation with IF NOT EXISTS).

-- agent_tasks: composite index for polling queries (assigned_to + status)
-- Already partially covered by individual indexes in 004, but the composite is critical
-- for the claim_agent_task() function which filters on both columns.
CREATE INDEX IF NOT EXISTS idx_agent_tasks_assigned_status
    ON agent_tasks(assigned_to, status);

-- newsletters: edition lookup (used in prepare_newsletter_data and publish_newsletter)
CREATE INDEX IF NOT EXISTS idx_newsletters_edition
    ON newsletters(edition_number DESC);

-- predictions: composite for monitoring queries (status + created_at)
CREATE INDEX IF NOT EXISTS idx_predictions_status_created
    ON predictions(status, created_at DESC);

-- analysis_runs: composite for latest-run queries (run_type + created_at)
CREATE INDEX IF NOT EXISTS idx_analysis_runs_type_created
    ON analysis_runs(run_type, created_at DESC);

-- source_posts: compound index for staleness/recency filtering with tier
CREATE INDEX IF NOT EXISTS idx_source_posts_tier_scraped
    ON source_posts(source_tier, scraped_at DESC);

-- opportunities: index for newsletter staleness logic (appearances + score)
CREATE INDEX IF NOT EXISTS idx_opportunities_appearances
    ON opportunities(newsletter_appearances ASC, confidence_score DESC);
