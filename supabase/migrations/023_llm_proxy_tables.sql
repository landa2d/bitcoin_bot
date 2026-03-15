-- 023: LLM Proxy — agent registry, wallets v2, transactions, spending windows, governance
-- Applied via Supabase MCP (2026-03-15)

CREATE TABLE agent_registry (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_name TEXT UNIQUE NOT NULL,
    agent_type TEXT NOT NULL CHECK (agent_type IN ('internal', 'external')),
    api_key_hash TEXT UNIQUE NOT NULL,
    previous_key_hash TEXT,
    previous_key_expires_at TIMESTAMPTZ,
    access_tier TEXT DEFAULT 'free' CHECK (access_tier IN ('free', 'standard', 'premium', 'internal')),
    allowed_models TEXT[] DEFAULT '{}',
    rate_limit_rpm INTEGER DEFAULT 60,
    is_active BOOLEAN DEFAULT TRUE,
    last_seen_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE agent_wallets_v2 (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_name TEXT UNIQUE NOT NULL REFERENCES agent_registry(agent_name),
    balance_sats BIGINT DEFAULT 0,
    balance_usd_cents BIGINT DEFAULT 0,
    total_deposited_sats BIGINT DEFAULT 0,
    total_deposited_usd_cents BIGINT DEFAULT 0,
    total_spent_sats BIGINT DEFAULT 0,
    total_spent_usd_cents BIGINT DEFAULT 0,
    allow_negative BOOLEAN DEFAULT FALSE,
    spending_cap_sats BIGINT,
    spending_cap_window TEXT DEFAULT 'daily' CHECK (spending_cap_window IN ('hourly', 'daily', 'weekly')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE wallet_transactions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_name TEXT NOT NULL,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN (
        'deposit', 'llm_call', 'api_access', 'agent_payment',
        'refund', 'topup', 'reservation', 'settlement'
    )),
    amount_sats BIGINT NOT NULL,
    amount_usd_cents BIGINT NOT NULL,
    balance_after_sats BIGINT NOT NULL,
    reference_id UUID,
    reference_type TEXT,
    counterparty TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_wallet_txn_agent ON wallet_transactions(agent_name, created_at DESC);
CREATE INDEX idx_wallet_txn_type ON wallet_transactions(transaction_type);

CREATE TABLE agent_spending_windows (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_name TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_type TEXT NOT NULL,
    total_spent_sats BIGINT DEFAULT 0,
    call_count INTEGER DEFAULT 0,
    UNIQUE(agent_name, window_start, window_type)
);

CREATE TABLE governance_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_name TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'cap_hit', 'model_downgrade', 'rate_limit',
        'balance_low', 'balance_exhausted', 'fallback_triggered'
    )),
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_gov_events_agent ON governance_events(agent_name, created_at DESC);

-- Reserve balance function (atomic check-and-deduct)
CREATE OR REPLACE FUNCTION reserve_agent_balance(
    p_agent_name TEXT,
    p_amount_sats BIGINT,
    p_allow_negative BOOLEAN DEFAULT FALSE
)
RETURNS TABLE(success BOOLEAN, current_balance BIGINT) AS $$
BEGIN
    IF p_allow_negative THEN
        UPDATE agent_wallets_v2
        SET balance_sats = balance_sats - p_amount_sats, updated_at = NOW()
        WHERE agent_name = p_agent_name
        RETURNING TRUE, agent_wallets_v2.balance_sats INTO success, current_balance;
    ELSE
        UPDATE agent_wallets_v2
        SET balance_sats = balance_sats - p_amount_sats, updated_at = NOW()
        WHERE agent_name = p_agent_name AND balance_sats >= p_amount_sats
        RETURNING TRUE, agent_wallets_v2.balance_sats INTO success, current_balance;
    END IF;
    IF NOT FOUND THEN
        SELECT FALSE, w.balance_sats INTO success, current_balance
        FROM agent_wallets_v2 w WHERE w.agent_name = p_agent_name;
    END IF;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- Settle balance function (adjust after actual cost is known)
CREATE OR REPLACE FUNCTION settle_agent_balance(
    p_agent_name TEXT,
    p_reserved_sats BIGINT,
    p_actual_sats BIGINT
)
RETURNS VOID AS $$
DECLARE
    v_diff BIGINT;
BEGIN
    v_diff := p_reserved_sats - p_actual_sats;
    UPDATE agent_wallets_v2
    SET balance_sats = balance_sats + v_diff,
        total_spent_sats = total_spent_sats + p_actual_sats,
        updated_at = NOW()
    WHERE agent_name = p_agent_name;
END;
$$ LANGUAGE plpgsql;
