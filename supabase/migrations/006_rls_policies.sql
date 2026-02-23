-- Migration 006: Row-Level Security (RLS) policies
--
-- Strategy:
--   - service_role key: bypasses RLS entirely (fine for all agents — they use service_role)
--   - anon key: read-only on newsletters and spotlight_history (public web archive)
--   - anon key: NO access to agent_tasks, predictions, agent_daily_usage, or any internal tables
--
-- IMPORTANT: Test with service_role key before enabling to confirm agents are not locked out.
-- All agents already use SUPABASE_SERVICE_KEY which bypasses RLS — this is safe to enable.

-- ============================================================================
-- Enable RLS on all tables
-- ============================================================================

ALTER TABLE moltbook_posts       ENABLE ROW LEVEL SECURITY;
ALTER TABLE problems             ENABLE ROW LEVEL SECURITY;
ALTER TABLE problem_clusters     ENABLE ROW LEVEL SECURITY;
ALTER TABLE opportunities        ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_mentions        ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_posts         ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_tasks          ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_daily_usage    ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_runs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE newsletters          ENABLE ROW LEVEL SECURITY;
ALTER TABLE topic_evolution      ENABLE ROW LEVEL SECURITY;
ALTER TABLE cross_signals        ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions          ENABLE ROW LEVEL SECURITY;
ALTER TABLE trending_topics      ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_negotiations   ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_queue       ENABLE ROW LEVEL SECURITY;
ALTER TABLE spotlight_history    ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- NEWSLETTERS: Public read (anon), service_role full access (via bypass)
-- ============================================================================

DROP POLICY IF EXISTS newsletters_anon_read ON newsletters;
CREATE POLICY newsletters_anon_read ON newsletters
    FOR SELECT
    TO anon
    USING (status = 'published');

-- ============================================================================
-- SPOTLIGHT HISTORY: Public read for published spotlights
-- ============================================================================

DROP POLICY IF EXISTS spotlight_history_anon_read ON spotlight_history;
CREATE POLICY spotlight_history_anon_read ON spotlight_history
    FOR SELECT
    TO anon
    USING (true);

-- ============================================================================
-- All other tables: deny anon access (no policy = deny by default with RLS enabled)
-- Service role bypasses RLS, so agents are unaffected.
-- ============================================================================

-- Explicitly document the intent with DENY-all policies for sensitive tables.
-- (RLS enabled + no matching policy = automatic deny for anon/authenticated)

-- agent_tasks: agents only (service_role bypasses)
-- agent_daily_usage: internal only
-- predictions: internal only (future: expose selected fields in web archive)
-- analysis_runs: internal only
-- agent_negotiations: internal only

-- ============================================================================
-- NOTE: authenticated role (Supabase dashboard users) also gets no access
-- to internal tables. If dashboard access is needed, grant explicitly:
--   CREATE POLICY dashboard_read ON agent_tasks FOR SELECT TO authenticated USING (true);
-- ============================================================================
