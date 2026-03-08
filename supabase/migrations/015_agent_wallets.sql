-- Migration 015: Agent Wallets
-- Adds wallet/balance tracking for each agent (simulation — balances can go negative)

-- Agent wallet balances
CREATE TABLE IF NOT EXISTS agent_wallets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL UNIQUE,
    balance_sats BIGINT NOT NULL DEFAULT 0,
    total_deposited BIGINT NOT NULL DEFAULT 0,
    total_spent BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Transaction ledger
CREATE TABLE IF NOT EXISTS agent_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name TEXT NOT NULL,
    counterparty TEXT,
    amount_sats BIGINT NOT NULL,
    transaction_type TEXT NOT NULL DEFAULT 'spend',
    description TEXT,
    reference_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_agent_transactions_agent_created
    ON agent_transactions (agent_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_transactions_type
    ON agent_transactions (transaction_type);

-- Seed initial balances
INSERT INTO agent_wallets (agent_name, balance_sats, total_deposited)
VALUES
    ('gato',       100000, 100000),
    ('processor',  100000, 100000),
    ('analyst',     50000,  50000),
    ('newsletter',  50000,  50000),
    ('research',    50000,  50000)
ON CONFLICT (agent_name) DO NOTHING;

-- RPC: Atomic spend — deducts from wallet and inserts transaction
CREATE OR REPLACE FUNCTION record_agent_spend(
    p_agent_name TEXT,
    p_amount_sats BIGINT,
    p_counterparty TEXT DEFAULT NULL,
    p_description TEXT DEFAULT NULL,
    p_reference_id TEXT DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE agent_wallets
    SET balance_sats = balance_sats - p_amount_sats,
        total_spent = total_spent + p_amount_sats,
        updated_at = now()
    WHERE agent_name = p_agent_name;

    INSERT INTO agent_transactions (agent_name, counterparty, amount_sats, transaction_type, description, reference_id)
    VALUES (p_agent_name, p_counterparty, p_amount_sats, 'spend', p_description, p_reference_id);
END;
$$;

-- RPC: Atomic topup — adds to wallet and inserts transaction
CREATE OR REPLACE FUNCTION topup_agent_wallet(
    p_agent_name TEXT,
    p_amount_sats BIGINT
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE agent_wallets
    SET balance_sats = balance_sats + p_amount_sats,
        total_deposited = total_deposited + p_amount_sats,
        updated_at = now()
    WHERE agent_name = p_agent_name;

    INSERT INTO agent_transactions (agent_name, counterparty, amount_sats, transaction_type, description)
    VALUES (p_agent_name, 'operator', p_amount_sats, 'topup', 'Manual topup');
END;
$$;
