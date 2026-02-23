-- Migration 003: Atomic task claiming via FOR UPDATE SKIP LOCKED
-- Eliminates race condition where two workers could claim the same pending task.

CREATE OR REPLACE FUNCTION claim_agent_task(
    p_assigned_to TEXT,
    p_limit       INT DEFAULT 1
)
RETURNS SETOF agent_tasks
LANGUAGE sql
AS $$
    UPDATE agent_tasks
    SET    status     = 'in_progress',
           started_at = NOW()
    WHERE  id IN (
        SELECT id
        FROM   agent_tasks
        WHERE  status      = 'pending'
          AND  assigned_to = p_assigned_to
        ORDER BY priority ASC, created_at ASC
        LIMIT p_limit
        FOR UPDATE SKIP LOCKED
    )
    RETURNING *;
$$;

CREATE OR REPLACE FUNCTION claim_research_task(
    p_limit INT DEFAULT 1
)
RETURNS SETOF research_queue
LANGUAGE sql
AS $$
    UPDATE research_queue
    SET    status     = 'in_progress',
           started_at = NOW()
    WHERE  id IN (
        SELECT id
        FROM   research_queue
        WHERE  status = 'queued'
        ORDER BY priority_score DESC
        LIMIT p_limit
        FOR UPDATE SKIP LOCKED
    )
    RETURNING *;
$$;
