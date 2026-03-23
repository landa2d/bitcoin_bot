# LLM Proxy — Claude Code Prompts (Phases 1-3)

## Execution Guide

Prompts marked **PARALLEL** can run in separate Claude Code sessions simultaneously.
Prompts marked **SEQUENTIAL** depend on previous prompts completing first.
Each prompt has a "verify before running" check.

---

## PHASE 1: Build the Proxy

---

### Prompt 1A — Supabase Schema
**Mode:** SEQUENTIAL (run first)
**Run via:** Supabase MCP or SQL Editor

```
Run these migrations in Supabase:

-- Agent registry
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

-- Wallet v2
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

-- Transaction ledger
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

-- Spending windows
CREATE TABLE agent_spending_windows (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_name TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_type TEXT NOT NULL,
    total_spent_sats BIGINT DEFAULT 0,
    call_count INTEGER DEFAULT 0,
    UNIQUE(agent_name, window_start, window_type)
);

-- Governance events
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

Verify:
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('agent_registry', 'agent_wallets_v2', 'wallet_transactions', 'agent_spending_windows', 'governance_events');
-- Should return 5 rows

SELECT routine_name FROM information_schema.routines WHERE routine_schema = 'public' AND routine_name IN ('reserve_agent_balance', 'settle_agent_balance');
-- Should return 2 rows
```

---

### Prompt 1B — Core Proxy Service
**Mode:** PARALLEL with 1A (write code while schema deploys)
**Verify before running:** None — this creates new files

```
Create a new FastAPI service at docker/llm-proxy/ that acts as a transparent proxy between agents and LLM providers.

Read my existing codebase first to understand:
- How other services are structured in docker/ (Dockerfile patterns, docker-compose setup)
- How Supabase is accessed (connection patterns, env variables in config/.env)
- The existing agent names: processor, analyst, research, newsletter, gato

The proxy service needs:

1. FastAPI app in docker/llm-proxy/proxy.py (or appropriate structure)

2. Three protocol endpoints that transparently forward requests:
   - POST /v1/chat/completions — OpenAI-compatible format. Forward to OpenAI or DeepSeek based on model name.
   - POST /v1/embeddings — OpenAI embeddings format. Forward to OpenAI.
   - POST /anthropic/v1/messages — Anthropic Messages API format. Forward to Anthropic.
   
   The proxy must NOT parse or modify request bodies beyond changing the API key. It's a dumb pipe — forward byte-for-byte. Provider-specific features (prompt caching, JSON mode, tool definitions) must pass through unchanged.

3. Agent identity via API key:
   - The agent sends its proxy key in the Authorization header (same place as a normal API key)
   - The proxy looks up the key hash in agent_registry to identify the agent
   - If key not found or agent is inactive, return 401

4. Model-to-provider routing table (load from config):
   {
       "deepseek-chat": {"provider": "deepseek", "base_url": "https://api.deepseek.com/v1", "env_key": "DEEPSEEK_API_KEY"},
       "gpt-4o": {"provider": "openai", "base_url": "https://api.openai.com/v1", "env_key": "OPENAI_API_KEY"},
       "gpt-4o-mini": {"provider": "openai", "base_url": "https://api.openai.com/v1", "env_key": "OPENAI_API_KEY"},
       "text-embedding-3-large": {"provider": "openai", "base_url": "https://api.openai.com/v1", "env_key": "OPENAI_API_KEY"},
       "claude-sonnet-4-20250514": {"provider": "anthropic", "base_url": "https://api.anthropic.com", "env_key": "ANTHROPIC_AGENT_KEY"}
   }

5. Reserve-settle wallet flow:
   BEFORE forwarding: call reserve_agent_balance() RPC to atomically deduct estimated cost
   - Estimated costs per model (sats): deepseek-chat=2, gpt-4o-mini=5, gpt-4o=50, claude-sonnet-4=80, text-embedding-3-large=1
   - For internal agents (allow_negative=true in their wallet), reservation always succeeds
   - For external agents, if balance insufficient return 402
   
   AFTER response: call settle_agent_balance() RPC to adjust for actual cost
   - Calculate actual cost from response token usage (use per-token USD rates from pricing config)
   - If provider call fails, settle with actual=0 (full refund of reservation)

6. Async log writes (non-blocking, after response is returned to agent):
   - Insert into wallet_transactions (transaction_type='llm_call')
   - Insert into llm_call_log (reuse existing table schema if it exists, otherwise create a compatible one)
   - If Supabase write fails, add to an in-memory retry queue (max 1000 entries, log a warning if queue is full)

7. Streaming support:
   - For POST /v1/chat/completions: check if request has stream=true
   - If streaming with OpenAI-compatible provider: inject stream_options={"include_usage": true} before forwarding, then intercept the final SSE chunk to extract usage
   - If streaming with Anthropic: capture usage from the message_delta event
   - For non-streaming: extract usage from response.usage directly

8. Rate limiting:
   - In-memory sliding window counter per agent (dict of deques with timestamps)
   - Check agent_registry.rate_limit_rpm before forwarding
   - Return 429 if exceeded

9. Request size limits:
   - 1MB max for /v1/chat/completions
   - 512KB max for /v1/embeddings
   - Return 413 if exceeded

10. Connection pooling:
    - Use httpx.AsyncClient with Limits(max_connections=50, max_keepalive_connections=20)
    - Shared client instance, not created per request
    - Timeouts: 30s for chat completions, 10s for embeddings, 30s for Anthropic messages

11. Health endpoint: GET /v1/proxy/health
    Returns {"status": "ok", "uptime_seconds": N}
    This is called by agents to check if the proxy is alive before sending requests.

12. Metrics endpoint: GET /v1/proxy/metrics (require admin API key)
    Returns JSON with: request counts by endpoint, error counts by provider, latency percentiles (p50/p95/p99), wallet operation counts, async queue depth, memory usage, active connections.

13. Configuration via environment variables (read from config/.env):
    - SUPABASE_URL, SUPABASE_SERVICE_KEY (or whatever the existing env var names are — check config/.env)
    - OPENAI_API_KEY, ANTHROPIC_AGENT_KEY, DEEPSEEK_API_KEY
    - LLM_PROXY_PORT (default 8200)
    - LLM_PROXY_ADMIN_KEY (for /metrics and /stats endpoints)

14. Dockerfile following the same patterns as other services in docker/
15. Add the service to docker-compose.yml on the same network as other agents

After creating the service, verify it starts without errors. Test the health endpoint. Do NOT connect any agents yet.
```

---

### Prompt 1C — Test Suite
**Mode:** SEQUENTIAL (depends on 1B proxy existing)
**Verify before running:** Proxy service starts, /health returns ok

```
Create a test suite for the LLM proxy at docker/llm-proxy/tests/ (or tests/test_proxy.py depending on project conventions).

Read the proxy code you just created to understand its structure.

The test suite needs:

1. UNIT TESTS (no external API calls):
   - API key validation: valid key returns agent identity, invalid key returns 401, inactive agent returns 401
   - Balance reservation: sufficient balance succeeds, insufficient balance fails, allow_negative bypasses check
   - Settlement: overpayment refunds difference, underpayment charges difference, failed call refunds fully
   - Rate limiting: requests within limit pass, requests over limit return 429, window slides correctly
   - Cost calculation: verify sats and USD costs for each model against the pricing table
   - Request size validation: oversized requests return 413
   - Model routing: each model name maps to the correct provider URL

2. INTEGRATION TESTS (hit real APIs — mark these so they can be skipped in CI):
   - Forward a simple chat completion to OpenAI through the proxy, verify the response is valid and matches what a direct call would return
   - Forward a simple message to Anthropic through the proxy, verify the response is valid
   - Forward an embedding request through the proxy, verify dimensions match
   - Verify that after each call, a wallet_transaction exists in Supabase with correct agent_name, model, and cost
   - Verify the wallet balance was deducted correctly

3. STREAMING TESTS (hit real APIs):
   - Forward a streaming chat completion, verify all chunks arrive and usage is extracted from the final chunk
   - Verify wallet deduction happens after stream completes

4. FAILURE TESTS:
   - Send a request with an invalid model name, verify a clear error is returned (not a proxy crash)
   - Send a request when the provider returns a 500, verify the reservation is refunded
   - Mock Supabase being unavailable for log writes, verify the request still completes (async logging fails gracefully)

5. GOVERNANCE TESTS (these will be more useful in Phase 3, but set up the framework now):
   - Placeholder tests for cap enforcement, model downgrade, reject behavior

To set up test data, the test suite should:
- Create a test agent in agent_registry with a known API key
- Create a test wallet with a known balance
- Clean up after tests

Use pytest. Make integration tests skippable with a --skip-integration flag.

Run the unit tests and report results. Run integration tests if API keys are available and report results.
```

---

### Prompt 1D — Seed Internal Agents + Test With Processor
**Mode:** SEQUENTIAL (depends on 1A schema + 1B proxy + 1C tests passing)
**Verify before running:** Schema exists, proxy starts, unit tests pass

```
I need to register the 5 internal agents in the proxy and test with the Processor agent.

1. Generate 5 proxy API keys (random 32-char hex strings prefixed with "ap_"):
   - ap_processor_<random>
   - ap_analyst_<random>
   - ap_research_<random>
   - ap_newsletter_<random>
   - ap_gato_<random>

2. For each agent, insert into agent_registry:
   - agent_type: 'internal'
   - api_key_hash: bcrypt hash of the key
   - access_tier: 'internal'
   - allowed_models: '{}' (empty = all allowed)
   - rate_limit_rpm: NULL (no limit for internal)

3. For each agent, insert into agent_wallets_v2:
   - Match the current deposits from agent_wallets (processor=100000, analyst=50000, research=50000, newsletter=50000, gato=100000)
   - allow_negative: TRUE (simulation mode for internal agents)

4. Store the plaintext proxy keys somewhere secure (print them out, I'll add them to config/.env)

5. Now test with Processor only:
   - Find where the Processor creates its LLM client (should be in docker/processor/agentpulse_processor.py)
   - Show me what environment variables it uses for the API base URL and key
   - Tell me exactly what to change in config/.env or docker-compose.yml to point the Processor at the proxy
   - Do NOT make the change yet — just show me what needs to change

6. After I confirm and make the env change, I'll restart the processor. Then verify:
   - Run the processor pipeline
   - Check: does the proxy log show 5 incoming requests from agent "processor"?
   - Check: does wallet_transactions have 5 new entries?
   - Check: does the processor's wallet balance reflect the deductions?
   - Check: does the processor's output (source_posts, problems, etc.) look normal? (The proxy should be invisible to the agent's behavior)
```

---

## PHASE 2: Migrate All Agents (Parallel Run)

---

### Prompt 2A — Migrate Remaining Agents
**Mode:** SEQUENTIAL (depends on Processor test succeeding in 1D)
**Verify before running:** Processor works through the proxy with correct wallet deductions

```
The Processor is successfully running through the LLM proxy. Now migrate the remaining 4 agents.

For each agent (analyst, research, newsletter, gato), I need you to:

1. Read the agent's source code and find where it creates its LLM client(s)
2. Identify ALL LLM client creation points — some agents may create multiple clients for different providers (e.g., Gato uses Claude for chat, DeepSeek for routing, OpenAI for embeddings)
3. For each client, tell me the exact env variable change needed to point at the proxy

Important considerations per agent:
- ANALYST: Uses deepseek-chat. Currently creates an OpenAI-compatible client. Should be straightforward — just change base_url and api_key env vars.
- RESEARCH: Uses Anthropic Claude directly via the Anthropic SDK. The proxy's /anthropic/v1/messages endpoint handles this. Change the Anthropic base_url to http://llm-proxy:8200/anthropic and the API key to the proxy key.
- NEWSLETTER: Uses both gpt-4o-mini and gpt-4o. Should work with OpenAI-compatible proxy endpoint. Check the _load_pricing() path issue (this was a known bug where estimated_cost was always $0) — since the proxy now handles cost tracking, this bug becomes irrelevant, but flag if the newsletter still tries to log costs independently.
- GATO (gato_brain): Uses Claude (Anthropic SDK), DeepSeek (OpenAI-compatible for routing), and OpenAI (for embeddings). This agent has THREE different LLM clients that ALL need to point at the proxy. Map each one:
  - Claude chat → http://llm-proxy:8200/anthropic with proxy key
  - DeepSeek routing → http://llm-proxy:8200/v1 with proxy key
  - OpenAI embeddings → http://llm-proxy:8200/v1 with proxy key

4. Also add fallback env vars for each agent (direct provider URLs + real keys) in case the proxy goes down. These won't be used in normal operation but document them.

5. Do NOT remove log_llm_call() from any agent yet — we're running both systems in parallel.

6. For the docker-compose.yml, make sure all agent containers have the llm-proxy service as a dependency (depends_on with a health check condition).

Output a clear summary: for each agent, the exact env var changes needed in config/.env or docker-compose.yml.
```

---

### Prompt 2B — Parallel Run Comparison Script
**Mode:** PARALLEL with 2A (write script while env changes are being planned)
**Verify before running:** None — creates a new script

```
Create a Python script compare_tracking.py that compares the old agent-side tracking with the new proxy-side tracking to verify they match.

Context:
- Old tracking: agents write to llm_call_log table via log_llm_call()
- New tracking: proxy writes to wallet_transactions table
- Both should record the same calls during the parallel run period

The script should:

1. Accept a time window: --from "2026-03-15 00:00" --to "2026-03-16 00:00"

2. Query both tables for that window:
   - From llm_call_log: agent_name, model, created_at, input_tokens, output_tokens
   - From wallet_transactions WHERE transaction_type='llm_call': agent_name, metadata->>'model', created_at, metadata->>'input_tokens', metadata->>'output_tokens'

3. Match calls by: agent_name + model + timestamp within 5-second window

4. Report:
   - Total calls in llm_call_log: N
   - Total calls in wallet_transactions: N
   - Matched: N
   - Proxy-only (tracked by proxy but not by agent): N — list them
   - Agent-only (tracked by agent but not by proxy): N — list them
   - Cost discrepancies: calls where sats differ by >10%
   
5. Verdict:
   - PASS if matched >= 99% and zero agent-only calls
   - WARN if matched 95-99%
   - FAIL if matched < 95% or any agent-only calls (means the proxy is missing calls)

6. Print the report to stdout and save as compare_results_<timestamp>.json

Read the actual schema of both tables before writing the queries — column names may differ from what I've described. Adjust accordingly.
```

---

### Prompt 2C — Execute Parallel Run and Verify
**Mode:** SEQUENTIAL (depends on 2A env changes applied and agents restarted)
**Verify before running:** All 5 agents are pointing at the proxy. Old log_llm_call() still active.

```
All agents are now routing through the proxy while also still logging via the old log_llm_call() system.

I need to verify everything works:

1. Trigger a full pipeline run (or wait for the next scheduled one)

2. After the pipeline completes, run compare_tracking.py for the pipeline's time window

3. Check the following per agent:
   - PROCESSOR: Should see exactly 5 deepseek-chat calls in proxy logs. Match old logs.
   - ANALYST: Should see deepseek-chat calls for prediction monitoring. Count should match old logs.
   - NEWSLETTER: Should see gpt-4o-mini and/or gpt-4o calls. Previously estimated_cost was $0 in old logs — proxy should now have accurate costs.
   - RESEARCH: If it ran, should see claude-sonnet-4 calls. If it didn't run (no items in research_queue), that's expected — note it.
   - GATO: If any Telegram messages came in, should see claude-sonnet-4 + deepseek-chat + embedding calls. This is the most important verification — Gato previously had ZERO tracking.

4. Check wallet balances: do the deductions make sense for the calls made?

5. If compare_tracking.py reports PASS:
   - Remove log_llm_call() from all agent codebases (processor, analyst, research, newsletter)
   - Remove the old wallet deduction code from each agent
   - Keep the llm_call_log table as-is (historical data, don't drop it)
   - The proxy is now the single source of truth for all cost tracking

6. If compare_tracking.py reports WARN or FAIL:
   - DO NOT remove old tracking
   - Report the mismatches — which agents, which calls were missed
   - We'll debug before proceeding

Run one more pipeline cycle after removing old tracking to confirm the proxy catches everything on its own.
```

---

## PHASE 3: Governance Engine

---

### Prompt 3A — Spending Windows and Cap Enforcement
**Mode:** SEQUENTIAL (depends on Phase 2 complete — proxy is sole tracking system)
**Verify before running:** compare_tracking.py returned PASS, old logging removed

```
Add spending cap enforcement to the LLM proxy.

Context:
- The proxy already handles reserve-settle for wallet balance
- The agent_spending_windows and governance_events tables exist
- Governance rules will be stored in a governance_config JSON file initially (we'll move to Supabase later)

1. Create a governance config file at docker/llm-proxy/governance_config.json:
{
    "analyst": {
        "spending_cap_sats": 28000,
        "spending_cap_window": "daily",
        "max_calls_per_minute": 10,
        "allowed_models": ["deepseek-chat"],
        "on_cap_exceeded": "reject",
        "alert_at_pct": 80
    },
    "processor": {
        "spending_cap_sats": 1000,
        "spending_cap_window": "daily",
        "max_calls_per_minute": 20,
        "allowed_models": ["deepseek-chat"],
        "on_cap_exceeded": "reject",
        "alert_at_pct": 90
    },
    "research": {
        "spending_cap_sats": 5000,
        "spending_cap_window": "weekly",
        "max_calls_per_minute": 5,
        "allowed_models": ["claude-sonnet-4-20250514"],
        "on_cap_exceeded": "reject",
        "alert_at_pct": 90
    },
    "newsletter": {
        "spending_cap_sats": 2000,
        "spending_cap_window": "weekly",
        "max_calls_per_minute": 10,
        "allowed_models": ["gpt-4o", "gpt-4o-mini"],
        "on_cap_exceeded": "reject",
        "alert_at_pct": 90
    },
    "gato": {
        "spending_cap_sats": 50000,
        "spending_cap_window": "daily",
        "max_calls_per_minute": 30,
        "allowed_models": ["claude-sonnet-4-20250514", "deepseek-chat", "text-embedding-3-large"],
        "on_cap_exceeded": "downgrade_model",
        "downgrade_map": {"claude-sonnet-4-20250514": "deepseek-chat"},
        "alert_at_pct": 70
    }
}

2. Add spending window tracking to the proxy request flow:
   - BEFORE the reserve call, query agent_spending_windows for the current window
   - If current window spend + estimated cost > spending_cap_sats, trigger the on_cap_exceeded action
   - AFTER settlement, increment the spending window counter

3. Implement governance actions:
   - "reject": Return 402 with cap info, window spend, reset time
   - "downgrade_model": 
     a. Look up the downgrade_map for the requested model
     b. Check if the request fits the downgraded model's context window (use max_context_tokens from pricing config)
     c. If it fits: forward to the cheaper model, add response headers X-Model-Downgraded=true, X-Original-Model=<original>, X-Actual-Model=<downgraded>
     d. If it doesn't fit: fall back to "reject" action
     e. Log a governance_event with type 'model_downgrade'
   - "alert": Allow the call but log a governance_event with type 'cap_hit'. (We'll wire Telegram alerts later)

4. Implement alert_at_pct: when window spend reaches this percentage of the cap, log a governance_event with type 'balance_low'. This is a warning, not a block.

5. Implement allowed_models check: if the agent requests a model not in its allowed_models list, return 403 with a clear error message.

6. Load governance config on startup with a 60-second reload check (re-read the file if modified). This allows changing caps without restarting the proxy.

Test:
- Verify analyst hits its daily cap after 14,000 sats of calls (28000 / 2 sats per call = 14,000 calls). Since it's at 200 calls/day post-fix, it shouldn't hit the cap in normal operation. Simulate by temporarily setting cap to 10 sats and making 6 calls.
- Verify Gato gets explicit downgrade headers when its cap is hit.
- Verify an agent requesting a model not in allowed_models gets a 403.
- Check governance_events table has entries for each test.
```

---

### Prompt 3B — Wallet Data Migration
**Mode:** PARALLEL with 3A
**Verify before running:** Phase 2 complete

```
Migrate data from the old agent_wallets table to the new agent_wallets_v2 table.

1. Read the current agent_wallets table schema and data:
   SELECT * FROM agent_wallets;

2. The agent_wallets_v2 table already has rows for each agent (created in Prompt 1D). Update them with historical deposit/spend data from the old table:
   - Copy total_deposited and total_spent values
   - Set balance to match the old table's current balance
   - Keep allow_negative=TRUE for all internal agents

3. Also migrate any useful data from the old wallet transaction history (if it exists in a separate table) into wallet_transactions. If there's no separate transaction table, just document the cutoff: "Historical data before [date] is in agent_wallets, data after [date] is in wallet_transactions."

4. Verify balances match:
   SELECT a.agent_name, a.balance_sats as old_balance, b.balance_sats as new_balance
   FROM agent_wallets a
   JOIN agent_wallets_v2 b ON a.agent_name = b.agent_name;

5. Do NOT drop the old agent_wallets table yet — keep it as a reference.
```

---

## Execution Map

```
Week 1:
┌──────────────────────────────────────────────────────┐
│ 1A (schema) ──────────────────────────────┐          │
│ 1B (proxy code) ─── parallel with 1A ─────┤          │
│                                            ▼          │
│                              1C (test suite)          │
│                                     │                 │
│                                     ▼                 │
│                              1D (seed agents          │
│                                  + test processor)    │
└──────────────────────────────────────────────────────┘

Week 1-2:
┌──────────────────────────────────────────────────────┐
│ 2A (plan env changes for all agents)                  │
│ 2B (comparison script) ─── parallel with 2A           │
│                                     │                 │
│            [Apply env changes, restart agents]         │
│                                     │                 │
│                                     ▼                 │
│                              2C (parallel run          │
│                                  + verify + cutover)   │
└──────────────────────────────────────────────────────┘

Week 2:
┌──────────────────────────────────────────────────────┐
│ 3A (governance engine)                                │
│ 3B (wallet migration) ─── parallel with 3A            │
└──────────────────────────────────────────────────────┘
```

**Total prompts: 7**
**Parallelizable pairs: 1A+1B, 2A+2B, 3A+3B**
**Critical path: 1A → 1B → 1C → 1D → 2A → 2C → 3A**

After Phase 3: observe one full pipeline cycle with governance active. Verify spending caps work, downgrades fire correctly, and wallet balances are accurate. Then proceed to Phases 4-6 (self-reporting, external agents, service passthroughs).
