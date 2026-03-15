-- Migration 020: Agent Self-Awareness
-- Adds API key auth, spending caps, and governance event tracking
-- for the /v1/proxy/wallet/{agent_name}/summary endpoint.

-- ─── Agent API Keys ─────────────────────────────────────────────────
-- Maps bearer tokens to agent names for proxy authentication.
CREATE TABLE IF NOT EXISTS agent_api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name  TEXT NOT NULL,
    api_key     TEXT NOT NULL UNIQUE,
    is_admin    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_api_keys_key ON agent_api_keys (api_key);

-- Seed one key per agent + one admin key (rotate in prod)
INSERT INTO agent_api_keys (agent_name, api_key, is_admin) VALUES
    ('gato',       'ak_gato_' || encode(gen_random_uuid()::text::bytea, 'hex'), FALSE),
    ('processor',  'ak_proc_' || encode(gen_random_uuid()::text::bytea, 'hex'), FALSE),
    ('analyst',    'ak_analyst_' || encode(gen_random_uuid()::text::bytea, 'hex'), FALSE),
    ('newsletter', 'ak_news_' || encode(gen_random_uuid()::text::bytea, 'hex'), FALSE),
    ('research',   'ak_research_' || encode(gen_random_uuid()::text::bytea, 'hex'), FALSE),
    ('admin',      'ak_admin_' || encode(gen_random_uuid()::text::bytea, 'hex'), TRUE)
ON CONFLICT (api_key) DO NOTHING;

-- ─── Spending Caps ──────────────────────────────────────────────────
-- Per-agent spending caps (sats per window).
CREATE TABLE IF NOT EXISTS agent_spending_caps (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name      TEXT NOT NULL UNIQUE,
    cap_sats        BIGINT NOT NULL DEFAULT 28000,
    window          TEXT NOT NULL DEFAULT 'daily',   -- 'daily' or 'weekly'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed defaults
INSERT INTO agent_spending_caps (agent_name, cap_sats, window) VALUES
    ('gato',       50000, 'daily'),
    ('processor',  50000, 'daily'),
    ('analyst',    28000, 'daily'),
    ('newsletter', 28000, 'daily'),
    ('research',   28000, 'daily')
ON CONFLICT (agent_name) DO NOTHING;

-- ─── Governance Events ──────────────────────────────────────────────
-- Tracks cap hits, budget overrides, manual topups, etc.
CREATE TABLE IF NOT EXISTS governance_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name  TEXT NOT NULL,
    event_type  TEXT NOT NULL,          -- 'cap_hit', 'topup', 'cap_change', 'budget_override'
    detail      JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_governance_events_agent_created
    ON governance_events (agent_name, created_at DESC);
