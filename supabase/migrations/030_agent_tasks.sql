-- Agent task queue: cross-service task delegation (processor → newsletter, analyst, etc.)

CREATE TABLE IF NOT EXISTS agent_tasks (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type   text NOT NULL,
    assigned_to text NOT NULL,
    created_by  text NOT NULL DEFAULT 'processor',
    status      text NOT NULL DEFAULT 'pending',
    priority    int  NOT NULL DEFAULT 5,
    input_data  jsonb DEFAULT '{}'::jsonb,
    output_data jsonb,
    error_message text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    started_at  timestamptz,
    completed_at timestamptz
);

-- Indexes for the poll pattern (claim pending tasks by agent)
CREATE INDEX idx_agent_tasks_poll
    ON agent_tasks (assigned_to, status, priority, created_at)
    WHERE status = 'pending';

CREATE INDEX idx_agent_tasks_type_created
    ON agent_tasks (task_type, created_at);

-- Atomic claim function: FOR UPDATE SKIP LOCKED prevents double-pickup
CREATE OR REPLACE FUNCTION claim_agent_task(p_assigned_to text, p_limit int DEFAULT 5)
RETURNS SETOF agent_tasks
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH claimed AS (
        SELECT id
        FROM agent_tasks
        WHERE assigned_to = p_assigned_to
          AND status = 'pending'
        ORDER BY priority DESC, created_at ASC
        LIMIT p_limit
        FOR UPDATE SKIP LOCKED
    )
    UPDATE agent_tasks t
    SET status = 'in_progress',
        started_at = now()
    FROM claimed c
    WHERE t.id = c.id
    RETURNING t.*;
END;
$$;

-- RLS: service-role key bypasses RLS, but enable it for safety
ALTER TABLE agent_tasks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access"
    ON agent_tasks
    FOR ALL
    USING (true)
    WITH CHECK (true);
