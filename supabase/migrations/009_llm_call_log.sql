-- 009_llm_call_log.sql — Per-call LLM cost tracking
-- Provides granular visibility into which agents/tasks/models consume budget.

CREATE TABLE IF NOT EXISTS llm_call_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name      TEXT NOT NULL,
    task_type       TEXT NOT NULL,
    model           TEXT NOT NULL,
    provider        TEXT NOT NULL,
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    total_tokens    INTEGER DEFAULT 0,
    estimated_cost  FLOAT DEFAULT 0,
    duration_ms     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_call_log_agent_date
    ON llm_call_log(agent_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_call_log_model
    ON llm_call_log(model, created_at DESC);

-- Summary view for quick cost dashboards
CREATE OR REPLACE VIEW llm_cost_summary AS
SELECT
    agent_name,
    model,
    task_type,
    COUNT(*) as call_count,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    ROUND(SUM(estimated_cost)::numeric, 4) as total_cost,
    ROUND(AVG(estimated_cost)::numeric, 6) as avg_cost_per_call,
    MIN(created_at)::date as first_call,
    MAX(created_at)::date as last_call
FROM llm_call_log
GROUP BY agent_name, model, task_type
ORDER BY total_cost DESC;
