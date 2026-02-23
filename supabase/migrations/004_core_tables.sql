-- Migration 004: Core tables missing from initial schema
-- All tables use CREATE TABLE IF NOT EXISTS for safe re-runs.
-- Schema inferred from production Python code (processor, analyst, newsletter).

-- ============================================================================
-- SOURCE POSTS: Multi-source ingestion (HN, GitHub, RSS, Thought Leaders)
-- ============================================================================

CREATE TABLE IF NOT EXISTS source_posts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source          TEXT NOT NULL,                          -- hackernews, github, rss_*, thought_leader_*
    source_id       TEXT NOT NULL,                          -- Original ID from the source
    source_url      TEXT,
    source_tier     INTEGER DEFAULT 3,                      -- 1=authority, 2=curated, 3=community
    title           TEXT,
    body            TEXT,
    author          TEXT,
    score           FLOAT DEFAULT 0,                        -- HN score, GitHub stars, RSS tier
    comment_count   INTEGER DEFAULT 0,
    tags            TEXT[] DEFAULT '{}',
    metadata        JSONB,
    scraped_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_source_posts_source ON source_posts(source);
CREATE INDEX IF NOT EXISTS idx_source_posts_scraped ON source_posts(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_posts_score ON source_posts(score DESC);
CREATE INDEX IF NOT EXISTS idx_source_posts_tier ON source_posts(source_tier);
CREATE INDEX IF NOT EXISTS idx_source_posts_thought_leader
    ON source_posts(source) WHERE source LIKE 'thought_leader_%';

-- ============================================================================
-- AGENT TASKS: Work queue for all agents
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type       TEXT NOT NULL,
    assigned_to     TEXT NOT NULL,                          -- analyst, newsletter, processor, gato
    created_by      TEXT,
    priority        INTEGER DEFAULT 5,                      -- lower = higher priority
    status          TEXT DEFAULT 'pending',                 -- pending, in_progress, completed, failed
    input_data      JSONB,
    output_data     JSONB,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_assigned ON agent_tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_assigned_status
    ON agent_tasks(assigned_to, status);                    -- composite for polling queries
CREATE INDEX IF NOT EXISTS idx_agent_tasks_created ON agent_tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_priority ON agent_tasks(priority ASC, created_at ASC);

-- ============================================================================
-- AGENT DAILY USAGE: Budget tracking per agent per day
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_daily_usage (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name              TEXT NOT NULL,
    date                    DATE NOT NULL,
    llm_calls_used          INTEGER DEFAULT 0,
    subtasks_created        INTEGER DEFAULT 0,
    proactive_alerts_sent   INTEGER DEFAULT 0,
    total_cost_estimate     FLOAT DEFAULT 0,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (agent_name, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_usage_agent_date ON agent_daily_usage(agent_name, date DESC);

-- ============================================================================
-- ANALYSIS RUNS: Results from the Analyst agent
-- ============================================================================

CREATE TABLE IF NOT EXISTS analysis_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_type            TEXT NOT NULL,                      -- full_analysis, deep_dive, proactive_analysis
    trigger             TEXT,                               -- task, scheduled, manual
    status              TEXT DEFAULT 'running',             -- running, completed, failed
    reasoning_steps     JSONB,
    key_findings        JSONB,
    analyst_notes       TEXT,
    confidence_level    TEXT DEFAULT 'medium',              -- high, medium, low
    caveats             JSONB,
    flags               JSONB,
    metadata            JSONB,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_type_created
    ON analysis_runs(run_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_status ON analysis_runs(status);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_completed ON analysis_runs(completed_at DESC);

-- ============================================================================
-- NEWSLETTERS: Published and draft newsletters
-- ============================================================================

CREATE TABLE IF NOT EXISTS newsletters (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edition_number      INTEGER NOT NULL,
    title               TEXT NOT NULL,
    content_markdown    TEXT,
    content_telegram    TEXT,
    data_snapshot       JSONB,                              -- input_data used to generate it
    status              TEXT DEFAULT 'draft',               -- draft, published
    published_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_newsletters_edition ON newsletters(edition_number DESC);
CREATE INDEX IF NOT EXISTS idx_newsletters_status ON newsletters(status);

-- ============================================================================
-- TOPIC EVOLUTION: Lifecycle tracking for problem cluster topics
-- ============================================================================

CREATE TABLE IF NOT EXISTS topic_evolution (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_key       TEXT NOT NULL UNIQUE,                   -- normalized slug, e.g. "agent_payments"
    snapshots       JSONB DEFAULT '[]',                     -- array of weekly snapshot objects
    current_stage   TEXT DEFAULT 'emerging',                -- emerging, building, debating, consolidating, mature, declining
    first_seen      TIMESTAMPTZ DEFAULT NOW(),
    last_updated    TIMESTAMPTZ DEFAULT NOW(),
    stage_changed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_topic_evolution_key ON topic_evolution(topic_key);
CREATE INDEX IF NOT EXISTS idx_topic_evolution_stage ON topic_evolution(current_stage);

-- ============================================================================
-- CROSS SIGNALS: Cross-pipeline intelligence signals from the Analyst
-- ============================================================================

CREATE TABLE IF NOT EXISTS cross_signals (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_type         TEXT,                               -- tool_problem_match, sentiment_opportunity, trend_convergence
    description         TEXT,
    strength            FLOAT,                              -- 0.0 to 1.0
    reasoning           TEXT,
    problem_cluster_id  UUID REFERENCES problem_clusters(id),
    tool_name           TEXT,
    opportunity_id      UUID REFERENCES opportunities(id),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cross_signals_type ON cross_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_cross_signals_created ON cross_signals(created_at DESC);

-- ============================================================================
-- PREDICTIONS: Trackable predictions from newsletters and analyst
-- ============================================================================

CREATE TABLE IF NOT EXISTS predictions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_type     TEXT DEFAULT 'opportunity',         -- opportunity, emerging_signal, spotlight
    title               TEXT,
    description         TEXT,
    prediction_text     TEXT,                               -- the exact prediction statement
    initial_confidence  FLOAT DEFAULT 0.5,
    current_score       FLOAT DEFAULT 0.5,
    status              TEXT DEFAULT 'open',                -- open, flagged, confirmed, refuted, partially_correct, expired, faded, wrong, active
    tracking_history    JSONB DEFAULT '[]',
    evidence_notes      TEXT,
    resolution_notes    TEXT,
    newsletter_edition  INTEGER,
    opportunity_id      UUID REFERENCES opportunities(id),
    cluster_id          UUID,
    topic_id            TEXT,
    issue_number        INTEGER,
    scorecard_issue     INTEGER,
    spotlight_id        UUID,                               -- FK added post-migration-002 below
    flagged_at          TIMESTAMPTZ,
    resolved_at         TIMESTAMPTZ,
    last_tracked        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_status_created
    ON predictions(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(status);
CREATE INDEX IF NOT EXISTS idx_predictions_topic ON predictions(topic_id);
CREATE INDEX IF NOT EXISTS idx_predictions_opportunity ON predictions(opportunity_id);

-- ============================================================================
-- TRENDING TOPICS: Interesting topics extracted for newsletter Curious Corner
-- ============================================================================

CREATE TABLE IF NOT EXISTS trending_topics (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title                   TEXT NOT NULL,
    description             TEXT,
    topic_type              TEXT DEFAULT 'technical',       -- technical, cultural, business
    source_post_ids         TEXT[] DEFAULT '{}',
    engagement_score        FLOAT DEFAULT 0,
    novelty_score           FLOAT DEFAULT 0,
    why_interesting         TEXT,
    metadata                JSONB,
    featured_in_newsletter  BOOLEAN DEFAULT FALSE,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trending_topics_created ON trending_topics(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trending_topics_featured ON trending_topics(featured_in_newsletter);

-- ============================================================================
-- AGENT NEGOTIATIONS: Multi-agent negotiation tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_negotiations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requesting_agent    TEXT NOT NULL,
    responding_agent    TEXT NOT NULL,
    request_task_id     UUID REFERENCES agent_tasks(id),
    response_task_id    UUID REFERENCES agent_tasks(id),
    request_summary     TEXT,
    quality_criteria    TEXT,
    needed_by           TIMESTAMPTZ,
    status              TEXT DEFAULT 'open',                -- open, follow_up, closed, timed_out
    criteria_met        BOOLEAN,
    response_summary    TEXT,
    round               INTEGER DEFAULT 1,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    closed_at           TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_negotiations_status ON agent_negotiations(status);
CREATE INDEX IF NOT EXISTS idx_negotiations_created ON agent_negotiations(created_at DESC);

-- ============================================================================
-- Add spotlight_id FK to predictions (spotlight_history created in migration 002)
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'predictions_spotlight_id_fkey'
          AND table_name = 'predictions'
    ) THEN
        BEGIN
            ALTER TABLE predictions
                ADD CONSTRAINT predictions_spotlight_id_fkey
                FOREIGN KEY (spotlight_id) REFERENCES spotlight_history(id);
        EXCEPTION WHEN others THEN
            NULL; -- safe: spotlight_history may not exist if 002 hasn't run yet
        END;
    END IF;
END $$;
