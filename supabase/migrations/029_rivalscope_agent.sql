-- 029: Register RivalScope agent in LLM proxy
-- Routes RivalScope's LLM calls through the proxy for cost tracking

INSERT INTO agent_registry (agent_name, agent_type, api_key_hash, access_tier, allowed_models, rate_limit_rpm, is_active)
VALUES (
    'rivalscope',
    'internal',
    '$2b$12$eyHGcM/tClhT2hGNJNPyjuUP6HFbq9DtKostcFQWttHdg1knV8aFC',
    'internal',
    ARRAY['deepseek-chat', 'claude-sonnet-4-20250514'],
    30,
    TRUE
)
ON CONFLICT (agent_name) DO UPDATE SET
    api_key_hash = EXCLUDED.api_key_hash,
    allowed_models = EXCLUDED.allowed_models,
    is_active = TRUE;

INSERT INTO agent_wallets_v2 (agent_name, balance_sats, total_deposited_sats, allow_negative, spending_cap_sats, spending_cap_window)
VALUES (
    'rivalscope',
    50000,
    50000,
    TRUE,
    10000,
    'daily'
)
ON CONFLICT (agent_name) DO UPDATE SET
    spending_cap_sats = 10000,
    spending_cap_window = 'daily';
