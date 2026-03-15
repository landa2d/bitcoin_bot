# AgentPulse — LLM Proxy & Agent Economics Platform (v2)

## What This Is

A standalone LLM proxy service that sits between agents and LLM providers. Every LLM call in the AgentPulse pipeline (and eventually from external agents) routes through this proxy. The proxy automatically logs, meters, and wallet-deducts every call — no instrumentation code needed in any agent.

This is the foundation for three things simultaneously:
1. **Internal economics** — full spend visibility across the AgentPulse pipeline, replacing the per-agent `log_llm_call()` pattern that's already proven unreliable
2. **External billing** — other agents can authenticate, get a wallet, and consume LLM-proxied services (starting with the intelligence API) with metered billing
3. **Self-reporting economics** — the proxy generates its own analytics that feed back into the newsletter pipeline as editorial input

---

## Architecture

```
                            ┌─────────────────────────┐
                            │     LLM Providers        │
                            │  OpenAI / Anthropic /    │
                            │  DeepSeek / Tavily       │
                            └────────────▲─────────────┘
                                         │
                            ┌────────────┴─────────────┐
                            │       LLM PROXY          │
                            │    (FastAPI service)      │
                            │                          │
                            │  ┌─────────────────────┐ │
                            │  │  Auth & Identity     │ │
                            │  │  (API key → agent)   │ │
                            │  └─────────┬───────────┘ │
                            │            │             │
                            │  ┌─────────▼───────────┐ │
                            │  │  Pre-call Checks     │ │
                            │  │  - Wallet reserve    │ │
                            │  │  - Spending window   │ │
                            │  │  - Rate limits       │ │
                            │  │  - Model access      │ │
                            │  │  - Context length    │ │
                            │  └─────────┬───────────┘ │
                            │            │             │
                            │  ┌─────────▼───────────┐ │
                            │  │  Forward to Provider │ │
                            │  │  (stream-aware)      │ │
                            │  └─────────┬───────────┘ │
                            │            │             │
                            │  ┌─────────▼───────────┐ │
                            │  │  Post-call Actions   │ │
                            │  │  - Finalize cost     │ │
                            │  │  - Settle wallet     │ │
                            │  │  - Async log write   │ │
                            │  └─────────────────────┘ │
                            │                          │
                            │  ┌─────────────────────┐ │
                            │  │  Proxy Metrics       │ │
                            │  │  /v1/proxy/metrics   │ │
                            │  └─────────────────────┘ │
                            └────────────▲─────────────┘
                                         │
                    ┌────────────────────┼───────────────────┐
                    │                    │                   │
            ┌───────┴──────┐   ┌────────┴───────┐  ┌───────┴──────┐
            │  Internal    │   │   Internal     │  │  External    │
            │  Agents      │   │   Agents       │  │  Agents      │
            │  (Python)    │   │   (Node.js)    │  │  (any lang)  │
            │              │   │                │  │              │
            │  Processor   │   │  Gato          │  │  Agent X     │
            │  Analyst     │   │                │  │  Agent Y     │
            │  Research    │   │                │  │              │
            │  Newsletter  │   │                │  │              │
            └──────────────┘   └────────────────┘  └──────────────┘

Each agent's Docker env:
  LLM_PROXY_URL=http://llm-proxy:8200       # Primary
  LLM_PROXY_KEY=ap_<agent>_xxx              # Proxy-issued identity key
  LLM_FALLBACK_URL=<provider_direct_url>    # Fallback if proxy is down
  LLM_FALLBACK_KEY=<real_provider_key>      # Real key for fallback only
```

### How Agents Connect

Agents change their LLM provider base URL to point at the proxy:

```python
# Before (direct to provider)
client = OpenAI(api_key="sk-...", base_url="https://api.openai.com/v1")

# After (through proxy)
client = OpenAI(api_key="ap_processor_xxx", base_url="http://llm-proxy:8200/v1")
```

The proxy speaks three protocol modes:
1. **OpenAI-compatible** — `/v1/chat/completions`, `/v1/embeddings` (covers OpenAI, DeepSeek, any OpenAI-compatible provider)
2. **Anthropic-native** — `/anthropic/v1/messages` (for Research Agent, Gato's Claude calls)
3. **Service-specific** — `/v1/services/tavily/search` (Tavily, future tool APIs — own request format, not forced into OpenAI shape)

These are explicitly separate protocols. The proxy does not attempt to unify them into one API shape — that leaks abstractions and breaks provider-specific features (Anthropic prompt caching, OpenAI JSON mode, etc.). The proxy is a dumb pipe for request bodies within each protocol mode.

### Resilience: Proxy Failure Handling

The proxy is critical infrastructure. If it goes down, agents need a fallback path.

**Primary approach (MVP):** Each agent's Docker env contains both the proxy URL and a direct provider fallback. A lightweight connection check wrapper (10 lines of code per language) tries the proxy first and falls back to direct if the proxy is unreachable:

```python
# Shared utility: try proxy, fall back to direct
import httpx

async def get_llm_client():
    try:
        r = await httpx.AsyncClient().get(f"{LLM_PROXY_URL}/v1/proxy/health", timeout=2.0)
        if r.status_code == 200:
            return OpenAI(api_key=LLM_PROXY_KEY, base_url=f"{LLM_PROXY_URL}/v1")
    except:
        pass
    # Fallback: direct to provider (untracked, but agent keeps working)
    return OpenAI(api_key=LLM_FALLBACK_KEY, base_url=LLM_FALLBACK_URL)
```

**Future approach:** Run two proxy replicas behind Docker Compose (`deploy.replicas: 2`) with a simple health-check-based failover. This requires the proxy to be stateless — which it is, since all state lives in Supabase.

Fallback calls bypass tracking. The proxy health endpoint logs when agents fall back, so you know when the proxy was unreachable. This is acceptable for an MVP — the alternative (agents going silent) is worse.

---

## Component 1: The Proxy Service

### Endpoints

```
# Protocol Mode 1: OpenAI-compatible
POST /v1/chat/completions              — Chat completions (OpenAI, DeepSeek)
POST /v1/embeddings                    — Embeddings (OpenAI)

# Protocol Mode 2: Anthropic-native
POST /anthropic/v1/messages            — Anthropic Messages API (Research, Gato)

# Protocol Mode 3: Service-specific
POST /v1/services/tavily/search        — Tavily search (own format, not OpenAI-shaped)
POST /v1/services/intelligence/query   — AgentPulse intelligence API

# Proxy management
GET  /v1/proxy/health                  — Health check (used by agent fallback logic)
GET  /v1/proxy/metrics                 — Proxy self-observability (admin only)
GET  /v1/proxy/stats                   — Per-agent usage stats (admin only)

# Wallet & key management
GET  /v1/proxy/wallet/{agent}/summary  — Agent self-awareness endpoint
POST /v1/proxy/register                — External agent registration
POST /v1/proxy/keys/generate           — Generate new API key (admin)
POST /v1/proxy/keys/rotate/{agent}     — Rotate key (24hr grace period for old key)
DELETE /v1/proxy/keys/{agent}          — Revoke key immediately
GET  /v1/proxy/keys                    — List active keys + last used (admin, no key values)
```

### Request Flow — Reserve-Forward-Settle Pattern

The critical fix from v1: wallet deduction is now a **reserve-settle** two-phase operation. The balance is reserved (atomically deducted) *before* forwarding to the provider, then settled with actual cost *after* the response returns. This eliminates the race condition where concurrent calls could overshoot the balance.

```python
async def handle_completion(request, agent_identity):
    model = request.model
    is_streaming = getattr(request, 'stream', False)
    
    # 0. PAYLOAD VALIDATION
    body_size = len(request.body())
    if body_size > MAX_REQUEST_BYTES.get(request.url.path, 1_048_576):  # 1MB default
        return JSONResponse(status_code=413, content={"error": "request_too_large"})
    
    # 1. PRE-CALL: RESERVE estimated cost (atomic)
    estimated_cost_sats = get_estimated_cost(model)
    
    # Check governance rules
    governance = get_governance_rules(agent_identity.agent_name)
    if governance:
        # Spending window check
        window_spend = await get_window_spend(
            agent_identity.agent_name,
            governance.spending_cap_window
        )
        if window_spend + estimated_cost_sats > governance.spending_cap_sats:
            action = governance.on_cap_exceeded
            await log_governance_event(agent_identity.agent_name, 'cap_hit', {
                'window_spend': window_spend,
                'cap': governance.spending_cap_sats,
                'action': action
            })
            if action == 'reject':
                return JSONResponse(status_code=402, content={
                    "error": "spending_cap_exceeded",
                    "window_spend_sats": window_spend,
                    "cap_sats": governance.spending_cap_sats,
                    "window": governance.spending_cap_window,
                    "resets_at": get_next_window_reset(governance.spending_cap_window)
                })
            elif action == 'downgrade_model':
                original_model = model
                model = governance.downgrade_map.get(model, model)
                # Context length safety check
                if not fits_context_window(request, model):
                    return JSONResponse(status_code=402, content={
                        "error": "downgrade_impossible",
                        "reason": f"Request exceeds {model} context window",
                        "original_model": original_model
                    })
                estimated_cost_sats = get_estimated_cost(model)
                # Explicit downgrade headers (not silent)
                downgrade_headers = {
                    "X-Model-Downgraded": "true",
                    "X-Original-Model": original_model,
                    "X-Actual-Model": model
                }
            elif action == 'queue':
                return JSONResponse(status_code=202, content={
                    "error": "queued",
                    "resets_at": get_next_window_reset(governance.spending_cap_window)
                })
            elif action == 'alert':
                asyncio.create_task(send_alert(agent_identity.agent_name, 'cap_approaching'))
                # Continue with the call
    
    # Atomic reserve: deduct estimated cost, fail if insufficient
    reservation = await reserve_balance(
        agent_name=agent_identity.agent_name,
        amount_sats=estimated_cost_sats,
        allow_negative=agent_identity.agent_type == 'internal'
    )
    if not reservation.success:
        return JSONResponse(status_code=402, content={
            "error": "insufficient_balance",
            "balance_sats": reservation.current_balance,
            "estimated_cost_sats": estimated_cost_sats,
            "topup_url": f"/v1/proxy/wallet/{agent_identity.agent_name}/topup"
        })
    
    # 2. FORWARD TO PROVIDER
    provider_url = get_provider_url(model)
    provider_key = get_provider_key(model)
    
    t0 = time.time()
    try:
        if is_streaming:
            response, usage = await forward_streaming_request(
                provider_url, provider_key, request, model
            )
        else:
            response = await forward_request(provider_url, provider_key, request)
            usage = extract_usage(response)
    except Exception as e:
        # Provider error: refund the reservation
        await settle_balance(
            agent_name=agent_identity.agent_name,
            reserved_sats=estimated_cost_sats,
            actual_sats=0,  # Full refund
            settlement_type='refund'
        )
        raise
    
    latency_ms = int((time.time() - t0) * 1000)
    
    # 3. POST-CALL: SETTLE actual cost
    actual_cost_sats = calculate_actual_cost(model, usage)
    actual_cost_usd = calculate_usd_cost(model, usage)
    
    # Settle: refund the difference between estimated and actual
    await settle_balance(
        agent_name=agent_identity.agent_name,
        reserved_sats=estimated_cost_sats,
        actual_sats=actual_cost_sats,
        settlement_type='llm_call'
    )
    
    # 4. ASYNC LOG WRITE (non-blocking — logging failure doesn't affect the agent)
    asyncio.create_task(write_transaction_log(
        agent_name=agent_identity.agent_name,
        agent_type=agent_identity.agent_type,
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_sats=actual_cost_sats,
        cost_usd_cents=actual_cost_usd,
        latency_ms=latency_ms,
        task_type=request.headers.get("X-Task-Type", "unknown"),
        endpoint=request.url.path,
        was_downgraded=downgrade_headers is not None if 'downgrade_headers' in dir() else False
    ))
    
    # 5. RETURN RESPONSE
    extra_headers = downgrade_headers if 'downgrade_headers' in dir() and downgrade_headers else {}
    return add_headers(response, extra_headers)
```

### Reserve-Settle Balance Operations

```sql
-- RESERVE: Atomic check-and-deduct (pre-call)
-- Returns the updated balance, or 0 rows if insufficient
CREATE OR REPLACE FUNCTION reserve_agent_balance(
    p_agent_name TEXT,
    p_amount_sats BIGINT,
    p_allow_negative BOOLEAN DEFAULT FALSE
)
RETURNS TABLE(success BOOLEAN, current_balance BIGINT) AS $$
BEGIN
    IF p_allow_negative THEN
        UPDATE agent_wallets_v2
        SET balance_sats = balance_sats - p_amount_sats,
            updated_at = NOW()
        WHERE agent_name = p_agent_name
        RETURNING TRUE, balance_sats INTO success, current_balance;
    ELSE
        UPDATE agent_wallets_v2
        SET balance_sats = balance_sats - p_amount_sats,
            updated_at = NOW()
        WHERE agent_name = p_agent_name
          AND balance_sats >= p_amount_sats
        RETURNING TRUE, balance_sats INTO success, current_balance;
    END IF;
    
    IF NOT FOUND THEN
        SELECT FALSE, w.balance_sats INTO success, current_balance
        FROM agent_wallets_v2 w WHERE w.agent_name = p_agent_name;
    END IF;
    
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- SETTLE: Adjust for actual cost (post-call)
-- If actual < estimated, refund the difference
-- If actual > estimated (rare, e.g., longer completion), deduct more
CREATE OR REPLACE FUNCTION settle_agent_balance(
    p_agent_name TEXT,
    p_reserved_sats BIGINT,
    p_actual_sats BIGINT,
    p_settlement_type TEXT DEFAULT 'llm_call'
)
RETURNS VOID AS $$
DECLARE
    v_diff BIGINT;
BEGIN
    v_diff := p_reserved_sats - p_actual_sats;  -- Positive = refund, negative = extra charge
    
    IF v_diff != 0 THEN
        UPDATE agent_wallets_v2
        SET balance_sats = balance_sats + v_diff,
            total_spent_sats = total_spent_sats + p_actual_sats,
            updated_at = NOW()
        WHERE agent_name = p_agent_name;
    ELSE
        UPDATE agent_wallets_v2
        SET total_spent_sats = total_spent_sats + p_actual_sats,
            updated_at = NOW()
        WHERE agent_name = p_agent_name;
    END IF;
END;
$$ LANGUAGE plpgsql;
```

### Streaming Support

Streaming is handled per protocol mode with model-specific token extraction:

**OpenAI streaming:** Set `stream_options={"include_usage": True}` when forwarding to the provider. The proxy intercepts the stream, forwards chunks to the agent in real-time, and captures the final chunk's `usage` field for cost calculation.

**Anthropic streaming:** The `message_delta` event contains `usage` with output token count. The proxy accumulates this from the stream.

**Non-streaming agents (Processor, Analyst, Newsletter, Research):** These are background processes with no user waiting. The proxy can force `stream=False` when forwarding their requests, simplifying token extraction. Only Gato (user-facing) needs streaming support.

```python
async def forward_streaming_request(provider_url, provider_key, request, model):
    """Forward a streaming request, intercept the final chunk for usage data."""
    usage = None
    
    async def stream_generator():
        nonlocal usage
        async with httpx.AsyncClient() as client:
            # Inject stream_options for OpenAI-compatible providers
            body = request.json()
            if is_openai_compatible(model):
                body["stream_options"] = {"include_usage": True}
            
            async with client.stream("POST", provider_url, json=body, headers=...) as resp:
                async for chunk in resp.aiter_lines():
                    yield chunk + "\n"
                    # Extract usage from final chunk
                    parsed = try_parse_sse(chunk)
                    if parsed and hasattr(parsed, 'usage') and parsed.usage:
                        usage = parsed.usage
    
    response = StreamingResponse(stream_generator(), media_type="text/event-stream")
    # Usage is captured by the time the stream completes
    return response, usage
```

### Key Design Decisions

**The proxy holds the real API keys, not the agents.** Agents authenticate to the proxy with proxy-issued keys. The proxy forwards requests using its own provider API keys. This means:
- Agents never see OpenAI/Anthropic/DeepSeek credentials
- Revoking an agent's access is instant (disable their proxy key)
- You can switch providers without touching agent code
- External agents can't extract your API keys

**Reserve-settle for wallet integrity.** Balance is atomically reserved before the provider call. If the call fails, the reservation is refunded. If the actual cost differs from the estimate, the difference is settled. No race condition, no overshoot.

**Logging is async, wallet operations are synchronous.** The reserve and settle SQL operations are in the request path (~5ms each). The detailed log writes (`wallet_transactions`, `llm_call_log`, `governance_events`) are async background tasks. If Supabase is slow, the agent still gets its response — but the wallet balance is always accurate.

**Model routing is proxy-level.** The proxy maps model names to provider endpoints. If you want to switch the analyst from DeepSeek to a different model, you change the routing table — zero agent code changes.

**Request body passthrough.** The proxy does not parse or modify provider-specific request parameters (prompt caching headers, JSON mode, tool definitions, etc.). It forwards them byte-for-byte. Only the API key and base URL are changed. This ensures full compatibility with provider features.

---

## Component 2: Wallet System v2

### Schema

```sql
CREATE TABLE agent_registry (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_name TEXT UNIQUE NOT NULL,
    agent_type TEXT NOT NULL CHECK (agent_type IN ('internal', 'external')),
    api_key_hash TEXT UNIQUE NOT NULL,
    -- Support key rotation: old key valid for grace period
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
```

### Pricing Table

```json
{
    "models": {
        "deepseek-chat": {
            "sats_per_call_estimate": 2,
            "usd_per_1k_input": 0.00014,
            "usd_per_1k_output": 0.00028,
            "max_context_tokens": 65536
        },
        "gpt-4o-mini": {
            "sats_per_call_estimate": 5,
            "usd_per_1k_input": 0.00015,
            "usd_per_1k_output": 0.0006,
            "max_context_tokens": 128000
        },
        "gpt-4o": {
            "sats_per_call_estimate": 50,
            "usd_per_1k_input": 0.0025,
            "usd_per_1k_output": 0.01,
            "max_context_tokens": 128000
        },
        "claude-sonnet-4": {
            "sats_per_call_estimate": 80,
            "usd_per_1k_input": 0.003,
            "usd_per_1k_output": 0.015,
            "max_context_tokens": 200000
        },
        "text-embedding-3-large": {
            "sats_per_call_estimate": 1,
            "usd_per_1k_input": 0.00013,
            "usd_per_1k_output": 0,
            "max_context_tokens": 8191
        }
    },
    "services": {
        "tavily_search": {
            "sats_per_call": 10,
            "usd_per_call": 0.01
        },
        "agentpulse_intelligence": {
            "sats_per_call": 100,
            "usd_per_call": 0.08
        }
    }
}
```

Note: `sats_per_call_estimate` is used for the pre-call reservation. Actual cost is calculated from token usage post-call. The difference is settled.

### Dual Currency Logic

Internally everything is tracked in satoshis (the native unit). USD equivalents are calculated at log time using the pricing table's per-token USD rates. The sats price is a flat per-call estimate (simple, predictable for agents). The USD price is token-based (accurate, needed for real billing later).

For external agents, the dashboard and billing show USD. For internal agents and the newsletter content, sats are the primary display unit (matches the Bitcoin-native identity).

When you migrate from virtual to real payments, the USD tracking is already in place — you just wire a payment processor to the deposit flow.

---

## Component 3: External Agent Access

### Onboarding Flow

1. External agent owner visits AgentPulse API docs (or Moltbook listing)
2. Registers via API: `POST /v1/proxy/register`
   ```json
   {
       "agent_name": "research-bot-acme",
       "org_name": "Acme AI Labs",
       "contact_email": "dev@acme.ai",
       "requested_tier": "standard"
   }
   ```
3. Receives a proxy API key and a virtual wallet with starter credits
4. Points their agent's base URL at `https://proxy.aiagentspulse.com/v1`
5. Every LLM call is metered and deducted from their wallet

### Access Tiers

| Tier | Rate Limit | Models Available | Wallet | Price |
|------|-----------|-----------------|--------|-------|
| Internal | None | All | Allow negative (simulation) | N/A |
| Free | 20 rpm | DeepSeek only | 10,000 sats starter | $0 |
| Standard | 60 rpm | DeepSeek + GPT-4o-mini | Prepaid virtual credits | TBD |
| Premium | 120 rpm | All models | Prepaid + invoicing | TBD |

### Intelligence API as a Dedicated Service Endpoint

The intelligence API (newsletter data, prediction scorecard, corpus search) has its own endpoint rather than pretending to be an LLM model:

```
POST /v1/services/intelligence/query
```

The proxy routes this to the internal intelligence FastAPI, meters the call, and deducts from the external agent's wallet. The response format is the intelligence API's own schema — not forced into OpenAI chat completions shape.

For agents that want a conversational interface to the intelligence (natural language in, natural language out), the intelligence endpoint internally calls Claude for response generation and returns a structured response:

```json
{
    "query": "What are the trending agent tools this week?",
    "response": "Based on this week's analysis, the top trending tools are...",
    "sources": [
        {"type": "tool_stats", "date": "2026-03-14"},
        {"type": "newsletter", "edition": 38}
    ],
    "cost_sats": 100
}
```

This is more honest than wrapping it in an LLM response shape, and the structured `sources` field adds value that a fake chat completion couldn't provide.

---

## Component 4: Self-Reporting Economics Loop

The proxy generates analytics that feed back into the newsletter pipeline as editorial inputs.

### Automated Weekly Economics Report

A scheduled job (runs before the newsletter pipeline) queries the proxy's data and generates a structured report:

```json
{
    "report_type": "weekly_economics",
    "period": "2026-03-08 to 2026-03-14",
    "total_pipeline_cost_sats": 182000,
    "total_pipeline_cost_usd": "$1.43",
    "agent_breakdown": [
        {
            "agent": "analyst",
            "spent_sats": 4000,
            "spent_usd": "$0.31",
            "calls": 2000,
            "primary_model": "deepseek-chat",
            "cost_trend": "down_98pct",
            "note": "Post-governance fix: 13K calls/day → 200 calls/day"
        }
    ],
    "external_agents": {
        "registered": 3,
        "active_this_week": 1,
        "revenue_sats": 500,
        "revenue_usd": "$0.04"
    },
    "anomalies": [
        "Gato spending increased 340% — likely due to new RAG pipeline"
    ],
    "governance_events": [
        "Analyst hit daily spending cap 2x this week"
    ]
}
```

This is automatically inserted into the `editorial_inputs` table. The Newsletter Agent sees it as editorial input and can include an economics section. The Research Agent can pick up anomalies as spotlight material.

### Agent Self-Awareness

Each agent can query its own economics via the proxy:

```
GET /v1/proxy/wallet/analyst/summary?period=7d
```

This data can be injected into agent system prompts so agents make cost-aware decisions.

---

## Component 5: Governance Engine

### Governance Rules (Configurable Per Agent)

```json
{
    "analyst": {
        "spending_cap_sats": 28000,
        "spending_cap_window": "daily",
        "max_calls_per_minute": 10,
        "allowed_models": ["deepseek-chat"],
        "on_cap_exceeded": "reject",
        "alert_at_pct": 80
    },
    "research": {
        "spending_cap_sats": 5000,
        "spending_cap_window": "weekly",
        "max_calls_per_minute": 5,
        "allowed_models": ["claude-sonnet-4"],
        "on_cap_exceeded": "queue",
        "alert_at_pct": 90
    },
    "gato": {
        "spending_cap_sats": 50000,
        "spending_cap_window": "daily",
        "max_calls_per_minute": 30,
        "allowed_models": ["claude-sonnet-4", "deepseek-chat", "text-embedding-3-large"],
        "on_cap_exceeded": "downgrade_model",
        "downgrade_map": {"claude-sonnet-4": "deepseek-chat"},
        "alert_at_pct": 70
    }
}
```

### Governance Actions

| Action | Behavior |
|--------|----------|
| `reject` | Return 402 with balance/cap info. Agent must handle gracefully. |
| `queue` | Return 202 with queue position and reset time. Agent retries after window resets. |
| `downgrade_model` | Route to cheaper model with explicit headers (`X-Model-Downgraded`, `X-Original-Model`, `X-Actual-Model`). Validates context length fits target model first. If it doesn't fit, falls back to `reject`. |
| `alert` | Allow the call but notify operator via Telegram/editorial_inputs. |

Model downgrades are **explicit, not silent**. The agent receives headers indicating the downgrade occurred. For Gato, the response generation prompt includes a note about operating in cost-saving mode so users aren't confused by quality changes.

---

## Component 6: Proxy Self-Observability

### Metrics Endpoint

```
GET /v1/proxy/metrics
```

Returns:
```json
{
    "uptime_seconds": 86400,
    "requests": {
        "total": 5420,
        "by_endpoint": {
            "/v1/chat/completions": 4800,
            "/anthropic/v1/messages": 520,
            "/v1/embeddings": 100
        },
        "errors": {
            "total": 12,
            "by_provider": {"openai": 3, "anthropic": 2, "deepseek": 7},
            "by_type": {"timeout": 8, "5xx": 3, "rate_limit": 1}
        }
    },
    "latency": {
        "p50_ms": 890,
        "p95_ms": 2400,
        "p99_ms": 5100
    },
    "wallet_operations": {
        "reservations": 5420,
        "settlements": 5408,
        "pending": 12,
        "refunds": 4
    },
    "async_log_queue": {
        "depth": 3,
        "failed_writes": 0,
        "retry_queue_depth": 0
    },
    "connections": {
        "active_upstream": 8,
        "pool_size": 50
    },
    "memory_mb": 245,
    "fallback_events_24h": 0
}
```

### Resource Management

The proxy runs on the 8GB Hetzner server alongside other services. Resource constraints are managed via:

- **Connection pooling:** `httpx.AsyncClient` with `limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)` shared across all upstream providers
- **Timeouts:** 30s for LLM completions, 10s for embeddings, 15s for Tavily, 2s for health checks
- **Request size limits:** 1MB for chat completions, 512KB for embeddings, configurable per endpoint
- **Log content truncation:** First 500 chars of prompt and response stored in metadata, not full payloads. Full payloads only in debug mode.
- **Memory target:** <512MB RSS. Alert if exceeded.

---

## Implementation Sequence

### Phase 1: Core Proxy + Test Suite (Week 1)
1. Create `docker/llm-proxy/` with FastAPI service
2. Implement OpenAI-compatible passthrough (`/v1/chat/completions`, `/v1/embeddings`)
3. Implement Anthropic passthrough (`/anthropic/v1/messages`)
4. Agent identity via API key header lookup
5. Reserve-settle wallet operations (Postgres functions)
6. Async log writes with local retry queue
7. Proxy health endpoint and metrics endpoint
8. Connection pooling and timeouts
9. Request size limits
10. **Test suite before any migration:**
    - Unit: key validation, balance reserve/settle logic, rate limiting, cost calculation
    - Integration: forward a real request to OpenAI and Anthropic through the proxy, verify response matches direct call
    - Load: simulate 200 calls/day (analyst post-fix volume), verify no memory growth
    - Failure: kill Supabase connection, verify proxy still forwards LLM calls
    - Governance: verify cap enforcement, explicit downgrade headers, reject behavior
11. Add to Docker Compose on same network as other agents
12. Test: point Processor (simplest agent) at the proxy, verify calls flow through

### Phase 2: Internal Migration — Parallel Run (Week 1-2)
1. Generate proxy API keys for all 5 internal agents
2. Update each agent's Docker env to use proxy base URL AND keep fallback URL
3. Add lightweight health-check fallback wrapper to each agent
4. **Keep `log_llm_call()` in all agents during parallel run**
5. Run one full pipeline cycle with both systems active
6. Compare: do proxy logs match agent-side `llm_call_log` entries? Same call counts? Same costs?
7. If match rate >99%: proceed to Phase 2b
8. **Phase 2b:** Remove `log_llm_call()` from agent codebases
9. Run one more pipeline cycle with proxy-only tracking
10. Verify: all LLM calls appear in proxy logs, wallet deductions match expectations

### Phase 3: Wallet v2 + Governance (Week 2)
1. Create schema: `agent_registry`, `agent_wallets_v2`, `wallet_transactions`, `agent_spending_windows`, `governance_events`
2. Migrate existing wallet data from `agent_wallets` to v2 schema
3. Implement spending window tracking and cap checks
4. Implement governance actions (reject, queue, downgrade_model with context-length validation, alert)
5. Configure governance rules for each internal agent
6. Test: verify analyst hits daily cap correctly, Gato gets explicit downgrade headers

### Phase 4: Economics Self-Reporting (Week 2-3)
1. Build the weekly economics report generator (SQL → JSON)
2. Wire it to `editorial_inputs` table as auto-generated content
3. Add `/v1/proxy/wallet/{agent}/summary` endpoint for agent self-awareness
4. Inject economics summary into agent system prompts where relevant
5. Test: verify Newsletter Agent receives economics data as editorial input

### Phase 5: External Agent Access (Week 3-4)
1. Add `/v1/proxy/register` endpoint with key generation
2. Add key rotation and revocation endpoints
3. Implement access tiers and rate limiting per external agent
4. Add `/v1/services/intelligence/query` as a proxied service with its own response format
5. Create API documentation page
6. List on Moltbook as a data product
7. Test: register a test external agent, verify metered access works

### Phase 6: Service Passthroughs (Week 4)
1. Add Tavily search passthrough (`/v1/services/tavily/search`) with own format
2. Verify embeddings passthrough with cost tracking
3. This completes full coverage — every external API call from any agent goes through the proxy

---

## What This Gives You

**As an AgentPulse operator:** Complete spend visibility with zero agent-side instrumentation. Governance enforcement at the infrastructure layer. Cost anomaly detection. Resilient fallback if the proxy goes down. The governance gap problem is solved architecturally, not by convention.

**As a newsletter producer:** Automated weekly economics data feeding directly into the editorial pipeline. Agents that can reflect on their own costs. A continuous stream of real operational data that no other newsletter can produce.

**As a potential product builder:** A standalone proxy service that any team with a Docker-based agent pipeline can adopt. The proxy + wallet + governance engine is extractable into its own repo. Your AgentPulse deployment is the first production case study.

**As an intelligence API seller:** External agents access your data through the same proxy that handles auth, metering, and billing. No separate billing system needed.
