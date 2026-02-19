-- ============================================================================
-- AgentPulse Schema for Supabase
-- Run this in the Supabase SQL Editor
-- ============================================================================

-- Enable UUID extension (usually already enabled)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- RAW DATA: Moltbook Posts
-- ============================================================================

CREATE TABLE moltbook_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    moltbook_id TEXT UNIQUE NOT NULL,          -- Original ID from Moltbook
    author_name TEXT,
    author_id TEXT,
    title TEXT,
    content TEXT NOT NULL,
    submolt TEXT,                               -- e.g., "bitcoin", "agents", etc.
    post_type TEXT DEFAULT 'post',              -- 'post' or 'comment'
    parent_post_id TEXT,                        -- For comments, the parent post
    upvotes INT DEFAULT 0,
    downvotes INT DEFAULT 0,
    comment_count INT DEFAULT 0,
    moltbook_created_at TIMESTAMPTZ,            -- When created on Moltbook
    scraped_at TIMESTAMPTZ DEFAULT NOW(),       -- When we scraped it
    raw_json JSONB,                             -- Full API response for reference
    processed BOOLEAN DEFAULT FALSE             -- Has this been analyzed?
);

CREATE INDEX idx_posts_moltbook_id ON moltbook_posts(moltbook_id);
CREATE INDEX idx_posts_scraped ON moltbook_posts(scraped_at DESC);
CREATE INDEX idx_posts_submolt ON moltbook_posts(submolt);
CREATE INDEX idx_posts_processed ON moltbook_posts(processed);
CREATE INDEX idx_posts_created ON moltbook_posts(moltbook_created_at DESC);

-- ============================================================================
-- PIPELINE 1: Problem Extraction
-- ============================================================================

CREATE TABLE problems (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    description TEXT NOT NULL,                  -- The extracted problem statement
    category TEXT,                              -- e.g., "tools", "infrastructure", "payments"
    keywords TEXT[],                            -- Key terms for matching
    signal_phrases TEXT[],                      -- The actual phrases found ("I wish...", etc.)
    source_post_ids UUID[],                     -- Posts where this was found
    frequency_count INT DEFAULT 1,              -- How many times mentioned
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    is_validated BOOLEAN DEFAULT FALSE,         -- Has market validation been run?
    validation_score FLOAT,                     -- 0-1 score after validation
    metadata JSONB
);

CREATE INDEX idx_problems_category ON problems(category);
CREATE INDEX idx_problems_frequency ON problems(frequency_count DESC);
CREATE INDEX idx_problems_validated ON problems(is_validated);

-- ============================================================================
-- PIPELINE 1: Problem Clusters
-- ============================================================================

CREATE TABLE problem_clusters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    theme TEXT NOT NULL,                        -- Cluster name/theme
    description TEXT,                           -- What this cluster represents
    problem_ids UUID[],                         -- Problems in this cluster
    total_mentions INT DEFAULT 0,               -- Sum of frequency counts
    avg_recency_days FLOAT,                     -- How recent are the mentions?
    market_validation JSONB,                    -- Validation results
    opportunity_score FLOAT,                    -- Computed opportunity score
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_clusters_score ON problem_clusters(opportunity_score DESC);

-- ============================================================================
-- PIPELINE 1: Opportunities
-- ============================================================================

CREATE TABLE opportunities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cluster_id UUID REFERENCES problem_clusters(id),
    title TEXT NOT NULL,                        -- Opportunity name
    problem_summary TEXT,                       -- What problem this solves
    proposed_solution TEXT,                     -- High-level solution
    business_model TEXT,                        -- SaaS, API, marketplace, etc.
    target_market TEXT,                         -- Who would buy this
    market_size_estimate TEXT,                  -- Rough TAM
    why_now TEXT,                               -- Why this timing makes sense
    competitive_landscape TEXT,                 -- Existing solutions
    confidence_score FLOAT,                     -- 0-1 confidence
    pitch_brief TEXT,                           -- Mini pitch deck text
    status TEXT DEFAULT 'draft',                -- draft, reviewed, archived
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_opportunities_status ON opportunities(status);
CREATE INDEX idx_opportunities_score ON opportunities(confidence_score DESC);

-- ============================================================================
-- PIPELINE 2: Tool Mentions (for future Investment Scanner)
-- ============================================================================

CREATE TABLE tool_mentions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tool_name TEXT NOT NULL,                    -- Normalized tool name
    tool_name_raw TEXT,                         -- As mentioned in post
    post_id UUID REFERENCES moltbook_posts(id),
    context TEXT,                               -- Surrounding text
    sentiment_score FLOAT,                      -- -1 to 1
    sentiment_label TEXT,                       -- positive, negative, neutral
    is_recommendation BOOLEAN DEFAULT FALSE,   -- Did they recommend it?
    is_complaint BOOLEAN DEFAULT FALSE,         -- Did they complain about it?
    alternative_mentioned TEXT,                 -- "switched from X to Y"
    mentioned_at TIMESTAMPTZ,
    metadata JSONB
);

CREATE INDEX idx_tools_name ON tool_mentions(tool_name);
CREATE INDEX idx_tools_sentiment ON tool_mentions(sentiment_score);
CREATE INDEX idx_tools_date ON tool_mentions(mentioned_at DESC);

-- ============================================================================
-- SYSTEM: Pipeline Runs
-- ============================================================================

CREATE TABLE pipeline_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pipeline TEXT NOT NULL,                     -- 'scrape', 'extract_problems', 'cluster', etc.
    status TEXT DEFAULT 'running',              -- running, completed, failed
    trigger_type TEXT,                          -- 'manual', 'scheduled'
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    items_processed INT DEFAULT 0,
    items_created INT DEFAULT 0,
    error_log TEXT,
    results JSONB,                              -- Summary of results
    metadata JSONB
);

CREATE INDEX idx_runs_pipeline ON pipeline_runs(pipeline);
CREATE INDEX idx_runs_status ON pipeline_runs(status);
CREATE INDEX idx_runs_started ON pipeline_runs(started_at DESC);

-- ============================================================================
-- VIEWS: Useful aggregations
-- ============================================================================

-- Top problems by frequency (last 30 days)
CREATE OR REPLACE VIEW top_problems_recent
WITH (security_invoker = on) AS
SELECT 
    p.*,
    pc.theme as cluster_theme
FROM problems p
LEFT JOIN problem_clusters pc ON p.id = ANY(pc.problem_ids)
WHERE p.last_seen > NOW() - INTERVAL '30 days'
ORDER BY p.frequency_count DESC
LIMIT 50;

-- Opportunity leaderboard
CREATE OR REPLACE VIEW opportunity_leaderboard
WITH (security_invoker = on) AS
SELECT 
    o.*,
    pc.theme as cluster_theme,
    pc.total_mentions
FROM opportunities o
JOIN problem_clusters pc ON o.cluster_id = pc.id
WHERE o.status != 'archived'
ORDER BY o.confidence_score DESC, pc.total_mentions DESC;

-- ============================================================================
-- FUNCTIONS: Utility functions
-- ============================================================================

-- Function to update problem frequency when new mentions found
CREATE OR REPLACE FUNCTION increment_problem_frequency(
    p_id UUID,
    new_post_ids UUID[]
)
RETURNS VOID AS $$
BEGIN
    UPDATE problems
    SET 
        frequency_count = frequency_count + array_length(new_post_ids, 1),
        source_post_ids = source_post_ids || new_post_ids,
        last_seen = NOW()
    WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get scraping stats
CREATE OR REPLACE FUNCTION get_scrape_stats()
RETURNS TABLE (
    total_posts BIGINT,
    posts_today BIGINT,
    posts_this_week BIGINT,
    unique_submolts BIGINT,
    unprocessed_posts BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_posts,
        COUNT(*) FILTER (WHERE scraped_at > NOW() - INTERVAL '1 day')::BIGINT as posts_today,
        COUNT(*) FILTER (WHERE scraped_at > NOW() - INTERVAL '7 days')::BIGINT as posts_this_week,
        COUNT(DISTINCT submolt)::BIGINT as unique_submolts,
        COUNT(*) FILTER (WHERE processed = FALSE)::BIGINT as unprocessed_posts
    FROM moltbook_posts;
END;
$$ LANGUAGE plpgsql;
