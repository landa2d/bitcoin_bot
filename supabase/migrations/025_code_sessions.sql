-- Code Sessions — tracks Claude Code coding sessions triggered from Telegram
CREATE TABLE IF NOT EXISTS public.code_sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, review, approved, rejected, merged, error, timeout
    repo_alias TEXT NOT NULL,
    repo_path TEXT,
    github_remote TEXT,
    branch_name TEXT,
    default_branch TEXT DEFAULT 'main',
    instruction TEXT NOT NULL,
    followup_instructions JSONB DEFAULT '[]',
    wallet_agent_name TEXT,
    max_turns INT DEFAULT 20,
    timeout_minutes INT DEFAULT 15,
    budget_usd NUMERIC(6,2) DEFAULT 3.00,
    diff_summary TEXT,
    diff_stats TEXT,
    files_changed JSONB DEFAULT '[]',
    claude_summary TEXT,
    claude_output_path TEXT,
    cost_sats INT DEFAULT 0,
    pr_url TEXT,
    pr_number INT,
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_code_sessions_status ON public.code_sessions (status);
CREATE INDEX IF NOT EXISTS idx_code_sessions_repo ON public.code_sessions (repo_alias);
