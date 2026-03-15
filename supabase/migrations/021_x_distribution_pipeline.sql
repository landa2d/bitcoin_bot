-- Migration 021: X Content Distribution Pipeline
-- Tables for content candidate surfacing, watchlist, and API budget tracking

-- ═══════════════════════════════════════════════════════
-- x_content_candidates — surfaced content for X posting
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS x_content_candidates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz DEFAULT now(),
    content_type text NOT NULL CHECK (content_type IN ('sharp_take', 'newsletter_thread', 'engagement_reply', 'prediction')),
    status text NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate', 'approved', 'rejected', 'posted', 'expired', 'failed')),
    source_url text,
    source_summary text,
    suggested_angle text,
    suggested_tags text[],
    draft_content text,
    final_content text,
    scheduled_for timestamptz,
    posted_at timestamptz,
    x_post_id text,
    verification_status text DEFAULT 'pending' CHECK (verification_status IN ('pending', 'verified', 'flagged')),
    verification_notes text,
    operator_notes text,
    engagement_data jsonb,
    language text DEFAULT 'en' CHECK (language IN ('en', 'es')),
    daily_index int  -- ephemeral index for Telegram approval (1, 2, 3...)
);

CREATE INDEX idx_x_candidates_status ON x_content_candidates (status);
CREATE INDEX idx_x_candidates_content_type ON x_content_candidates (content_type);
CREATE INDEX idx_x_candidates_created ON x_content_candidates (created_at DESC);

-- ═══════════════════════════════════════════════════════
-- x_watchlist — X accounts to monitor for engagement
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS x_watchlist (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    x_handle text UNIQUE NOT NULL,
    display_name text,
    priority int DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    category text,
    notes text,
    active boolean DEFAULT true,
    created_at timestamptz DEFAULT now(),
    last_checked_at timestamptz
);

CREATE INDEX idx_x_watchlist_active ON x_watchlist (active) WHERE active = true;

-- ═══════════════════════════════════════════════════════
-- x_api_budget — per-request cost tracking for X API
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS x_api_budget (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz DEFAULT now(),
    week_start date NOT NULL,
    operation_type text NOT NULL,
    endpoint text,
    estimated_cost numeric(10,6) DEFAULT 0,
    request_count int DEFAULT 1,
    notes text
);

CREATE INDEX idx_x_budget_week ON x_api_budget (week_start);

-- RLS policies (agents use service_role, so these are for safety)
ALTER TABLE x_content_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE x_watchlist ENABLE ROW LEVEL SECURITY;
ALTER TABLE x_api_budget ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access" ON x_content_candidates FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON x_watchlist FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON x_api_budget FOR ALL USING (true) WITH CHECK (true);
