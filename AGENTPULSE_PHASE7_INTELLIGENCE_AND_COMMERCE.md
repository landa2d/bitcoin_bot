# AgentPulse Phase 7: Personal Intelligence + Agent Commerce

**Date:** March 2026
**Goal:** Turn the data pipeline into personal intelligence for the operator, and begin experimenting with agent-to-agent transactions.

---

## Part 1: Personal Intelligence Briefing

### What It Does

A daily briefing delivered via Telegram, filtered through your personal context.
Not a newsletter — a private intelligence feed tailored to your projects, investments,
and open questions.

### Architecture

```
Every 12h (8am and 8pm):
  Processor → gathers last 12h of data (source_posts, tool_mentions, analysis_runs)
  Processor → reads config/operator-context.md
  Processor → calls LLM with personal context + recent data
  Processor → sends result to Gato's Telegram via bot API
```

### New Files

**config/operator-context.md** — your personal context file. Edit this whenever
your focus changes. The briefing system reads it fresh every run.

```markdown
# Operator Context — Diego

## Active Projects
- AgentPulse: multi-agent newsletter platform on OpenClaw + custom Python
- Using MCP conventions, Supabase coordination, Docker on Hetzner
- Tech stack: DeepSeek V3 (bulk), Claude (editorial), GPT-4o (agents)
- Current focus: Phase 6 dual-audience platform, subscriber growth

## Investment Thesis
- Long: AI infrastructure (compute, model serving, agent frameworks)
- Long: Stablecoin payment rails and agent commerce plumbing
- Long: Bitcoin and open protocols
- Short thesis: SaaS seat-based pricing, intermediation businesses
- Watching: private credit exposure to software LBOs

## Open Questions
- Will MCP become dominant or fragment into competing protocols?
- When does SaaS repricing stress private credit markets?
- Is agent memory about to consolidate? Which protocol wins?
- What's the right model for Newsletter agent after DeepSeek R2?
- When should I launch paid subscriptions for AgentPulse?

## Signals I Care About
- New MCP-related repos or protocol changes
- Agent framework adoption metrics (LangChain, CrewAI, AutoGen)
- SaaS earnings misses or pricing changes
- Stablecoin transaction volume growth
- Any mention of AgentPulse or Moltbook in Tier 1 sources
- New agent commerce or payment experiments
- Cost changes in LLM APIs (especially DeepSeek, Claude, GPT-4o)

## Career & Learning
- Need to develop: sales, distribution, go-to-market
- Want to understand: private credit mechanics, mortgage-backed securities
- Building toward: monetizable intelligence platform
```

### Implementation

**New task type: `personal_briefing`**

Add to `agentpulse_processor.py`:

```python
def generate_personal_briefing():
    """Generate a personal intelligence briefing for the operator."""

    # Load operator context
    context_path = Path('/home/openclaw/config/operator-context.md')
    if context_path.exists():
        operator_context = context_path.read_text()
    else:
        logger.warning("No operator-context.md found")
        return {'error': 'No operator context configured'}

    # Gather recent data (last 12 hours)
    twelve_hours_ago = (datetime.utcnow() - timedelta(hours=12)).isoformat()

    # Recent source posts (all sources)
    recent_posts = supabase.table('source_posts')\
        .select('source, title, body, source_tier, score, tags')\
        .gte('scraped_at', twelve_hours_ago)\
        .order('source_tier', desc=False)\
        .limit(100)\
        .execute()

    # Recent tool mentions
    recent_tools = supabase.table('tool_mentions')\
        .select('tool_name, context, sentiment_score, source')\
        .gte('created_at', twelve_hours_ago)\
        .limit(50)\
        .execute()

    # Latest analysis run
    latest_analysis = supabase.table('analysis_runs')\
        .select('key_findings, analyst_notes, metadata')\
        .eq('status', 'completed')\
        .order('completed_at', desc=True)\
        .limit(1)\
        .execute()

    # Active predictions
    predictions = supabase.table('predictions')\
        .select('topic, status, current_score, notes')\
        .eq('status', 'active')\
        .execute()

    # Topic evolution (any stage changes?)
    topics = supabase.table('topic_evolution')\
        .select('topic_key, current_stage, stage_changed_at, thesis')\
        .order('last_updated', desc=True)\
        .limit(15)\
        .execute()

    # Build the briefing prompt
    data_package = {
        'recent_posts': recent_posts.data or [],
        'recent_tools': recent_tools.data or [],
        'latest_analysis': latest_analysis.data[0] if latest_analysis.data else None,
        'active_predictions': predictions.data or [],
        'topic_evolution': topics.data or [],
        'timestamp': datetime.utcnow().isoformat()
    }

    system_prompt = f"""You are an intelligence briefing system for a specific operator.
Your job is to scan the latest data and surface what matters to THIS person based on
their context.

OPERATOR CONTEXT:
{operator_context}

RULES:
- Maximum 5 items. Each item is 1-3 sentences.
- Lead with the most actionable item.
- Flag anything that directly affects the operator's active projects.
- Flag any signals matching the operator's investment thesis.
- Flag any answers to the operator's open questions.
- If a prediction's status changed, mention it.
- If a topic changed lifecycle stage, mention it.
- If nothing significant happened, say "Quiet 12 hours. Nothing actionable." Don't pad.
- Be direct. No greetings, no filler. This is a private briefing, not a newsletter.
- End with a one-line "Action items:" if any exist (things the operator should do).

FORMAT:
Return plain text, not JSON. This goes straight to Telegram.
Use numbered items. Keep it under 500 words total.
"""

    # Call LLM (use cheap model — this is a personal tool, not editorial)
    model = get_model('personal_briefing')  # default to deepseek-v3
    response = call_llm(
        model=model,
        system=system_prompt,
        user=json.dumps(data_package, default=str),
        max_tokens=1000
    )

    # Send to Telegram
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    operator_chat_id = os.getenv('OPERATOR_TELEGRAM_CHAT_ID')

    if telegram_token and operator_chat_id:
        import requests
        header = "🔍 *AgentPulse Briefing*\n\n"
        requests.post(
            f"https://api.telegram.org/bot{telegram_token}/sendMessage",
            json={
                'chat_id': operator_chat_id,
                'text': header + response,
                'parse_mode': 'Markdown'
            }
        )

    return {'briefing_sent': True, 'length': len(response)}
```

**Schedule:** Every 12 hours (8am and 8pm server time)
**Model:** DeepSeek V3 (cheap — this is a personal tool)
**New env var:** `OPERATOR_TELEGRAM_CHAT_ID` in config/.env

**Telegram commands:**
- `/briefing` — trigger an immediate personal briefing
- `/context` — show current operator-context.md summary
- `/watch [topic]` — add a signal to the "Signals I Care About" list

---

## Part 2: Agent Commerce Experiments

### Overview

Three experiments, increasing in complexity. Each teaches you different plumbing.

### Experiment A: Gato Gets a Wallet

**Goal:** Gato holds a small balance and tracks its own spending on LLM calls.

**Not real payments yet** — this is a simulation using Supabase as the ledger.
The point is to build the accounting infrastructure before connecting real money.

```sql
CREATE TABLE agent_wallets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name TEXT UNIQUE NOT NULL,
    balance_sats BIGINT DEFAULT 0,
    total_deposited BIGINT DEFAULT 0,
    total_spent BIGINT DEFAULT 0,
    last_transaction_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE agent_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    from_agent TEXT NOT NULL,
    to_agent TEXT,
    to_external TEXT,
    amount_sats BIGINT NOT NULL,
    transaction_type TEXT NOT NULL,  -- 'llm_call', 'deposit', 'purchase', 'sale'
    description TEXT,
    reference_id TEXT,  -- task_id or external tx hash
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed Gato with initial balance
INSERT INTO agent_wallets (agent_name, balance_sats, total_deposited)
VALUES
  ('gato', 100000, 100000),        -- ~$50 worth at current prices
  ('analyst', 50000, 50000),
  ('newsletter', 50000, 50000),
  ('research', 50000, 50000);
```

**Pricing model** (approximate, for simulation):
```python
LLM_COST_SATS = {
    'deepseek-v3': 2,          # ~$0.001 per call
    'gpt-4o': 50,              # ~$0.025 per call
    'claude-sonnet': 80,       # ~$0.04 per call
}
```

**Integration:** After every LLM call in the pollers, log a transaction:

```python
def log_agent_spend(agent_name, model, task_id=None):
    cost = LLM_COST_SATS.get(model, 10)
    supabase.table('agent_transactions').insert({
        'from_agent': agent_name,
        'to_external': f'api:{model}',
        'amount_sats': cost,
        'transaction_type': 'llm_call',
        'description': f'{model} call',
        'reference_id': task_id
    }).execute()

    supabase.table('agent_wallets').update({
        'balance_sats': supabase.rpc('decrement_balance', {
            'p_agent': agent_name, 'p_amount': cost
        }),
        'total_spent': supabase.rpc('increment_spent', {
            'p_agent': agent_name, 'p_amount': cost
        }),
        'last_transaction_at': datetime.utcnow().isoformat()
    }).eq('agent_name', agent_name).execute()
```

**Telegram commands:**
- `/wallet` — show all agent balances
- `/ledger [agent]` — show last 10 transactions for an agent
- `/topup [agent] [amount]` — add sats to an agent's wallet (operator only)

**What this teaches you:** Accounting infrastructure, per-agent cost tracking,
the concept of agents as economic entities with budgets they manage.

---

### Experiment B: AgentPulse Intelligence API (Sell to Other Agents)

**Goal:** Expose AgentPulse data as a service that other agents can discover and purchase.

**Start with a simple HTTP endpoint.** Later, wrap it as an MCP server.

```python
# docker/processor/agentpulse_api.py (new file)
# A minimal Flask/FastAPI endpoint that serves intelligence

from fastapi import FastAPI, HTTPException, Header
from supabase import create_client

app = FastAPI(title="AgentPulse Intelligence API")

# Simple API key auth (or verify on-chain payment later)
API_KEYS = {
    'test-key-001': {'name': 'test-agent', 'tier': 'basic'},
}

@app.get("/catalog")
async def catalog():
    """What intelligence products are available."""
    return {
        "products": [
            {
                "id": "latest_brief",
                "name": "Latest Intelligence Brief",
                "description": "Most recent AgentPulse newsletter in structured format",
                "price_sats": 500,
                "format": "json"
            },
            {
                "id": "topic_radar",
                "name": "Topic Radar",
                "description": "Current topic lifecycle stages and evolution data",
                "price_sats": 200,
                "format": "json"
            },
            {
                "id": "tool_trends",
                "name": "Tool Trends",
                "description": "Rising/falling/new tools with signals",
                "price_sats": 200,
                "format": "json"
            },
            {
                "id": "predictions",
                "name": "Prediction Tracker",
                "description": "Active predictions with confidence scores",
                "price_sats": 100,
                "format": "json"
            }
        ]
    }

@app.get("/purchase/{product_id}")
async def purchase(product_id: str, api_key: str = Header(alias="X-API-Key")):
    """Purchase an intelligence product."""
    if api_key not in API_KEYS:
        raise HTTPException(401, "Invalid API key")

    if product_id == "latest_brief":
        nl = supabase.table('newsletters')\
            .select('edition_number, title, title_impact, content_markdown, content_markdown_impact, created_at')\
            .eq('status', 'published')\
            .order('edition_number', desc=True)\
            .limit(1)\
            .execute()
        if not nl.data:
            raise HTTPException(404, "No published brief available")

        # Log the sale
        log_agent_sale('agentpulse', API_KEYS[api_key]['name'], 500, product_id)
        return {"product": product_id, "data": nl.data[0]}

    elif product_id == "topic_radar":
        topics = supabase.table('topic_evolution')\
            .select('topic_key, current_stage, thesis, thesis_confidence, last_updated')\
            .order('last_updated', desc=True)\
            .limit(20)\
            .execute()
        log_agent_sale('agentpulse', API_KEYS[api_key]['name'], 200, product_id)
        return {"product": product_id, "data": topics.data}

    elif product_id == "tool_trends":
        tools = supabase.table('tool_mentions')\
            .select('tool_name, sentiment_score, mention_count, source')\
            .order('created_at', desc=True)\
            .limit(30)\
            .execute()
        log_agent_sale('agentpulse', API_KEYS[api_key]['name'], 200, product_id)
        return {"product": product_id, "data": tools.data}

    elif product_id == "predictions":
        preds = supabase.table('predictions')\
            .select('topic, status, current_score, notes, created_at')\
            .execute()
        log_agent_sale('agentpulse', API_KEYS[api_key]['name'], 100, product_id)
        return {"product": product_id, "data": preds.data}

    raise HTTPException(404, f"Unknown product: {product_id}")
```

**Deployment:** Run as a separate service in Docker, or add routes to the web service.
Start on an internal port only (not public) until you're ready.

**Later evolution:** Replace API key auth with on-chain payment verification.
An external agent sends sats to a Lightning invoice or stablecoins to a Solana
address, includes the tx hash in the request, and the API verifies before returning data.

**MCP Server (future):** Wrap the API as an MCP server so other Claude-based agents
can discover and use it natively:

```python
# Future: MCP server definition
tools = [
    {
        "name": "get_agentpulse_catalog",
        "description": "List available intelligence products from AgentPulse",
        "input_schema": {}
    },
    {
        "name": "purchase_intelligence",
        "description": "Purchase a specific intelligence product",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string"},
                "payment_proof": {"type": "string"}
            }
        }
    }
]
```

---

### Experiment C: Gato Buys External Intelligence

**Goal:** Gato discovers an external data source, pays for it, and integrates
the results into the newsletter pipeline.

**Start with a mock.** Build a fake "external service" that Gato can call,
pay for, and use. This proves the plumbing before involving real external services.

```python
# docker/processor/mock_external_service.py
# Simulates an external intelligence provider

MOCK_PRODUCTS = {
    'sec_filings_ai': {
        'price_sats': 300,
        'description': 'Recent SEC filings related to AI companies',
        'data': [
            {'company': 'Anthropic', 'filing': '10-K', 'date': '2026-02-15',
             'summary': 'Revenue up 340% YoY. Operating loss narrowing.'},
            {'company': 'OpenAI', 'filing': 'S-1', 'date': '2026-01-20',
             'summary': 'IPO filing indicates $8B ARR. Enterprise is 60% of revenue.'},
        ]
    },
    'patent_trends_ai': {
        'price_sats': 200,
        'description': 'AI agent patent filing trends',
        'data': [
            {'trend': 'Agent memory patents up 180% in Q1 2026',
             'top_filers': ['Google', 'Microsoft', 'Anthropic']},
        ]
    }
}
```

**The purchase flow:**

```python
def gato_purchase_intelligence(product_id, provider='mock'):
    """Gato autonomously purchases intelligence from an external provider."""

    # 1. Check Gato's wallet
    wallet = supabase.table('agent_wallets')\
        .select('balance_sats')\
        .eq('agent_name', 'gato')\
        .single()\
        .execute()

    product = MOCK_PRODUCTS[product_id]
    cost = product['price_sats']

    if wallet.data['balance_sats'] < cost:
        return {'error': 'Insufficient balance', 'balance': wallet.data['balance_sats'], 'cost': cost}

    # 2. "Pay" the external provider
    log_agent_spend('gato', f'external:{provider}:{product_id}', cost)

    # 3. Receive the data
    data = product['data']

    # 4. Store it as supplementary intelligence
    for item in data:
        supabase.table('source_posts').insert({
            'source': f'purchased:{provider}',
            'source_id': f'{provider}:{product_id}:{item.get("company", item.get("trend", ""))}',
            'title': item.get('summary', item.get('trend', '')),
            'body': json.dumps(item),
            'source_tier': 1,  # purchased data is high-authority
            'metadata': {'purchased': True, 'provider': provider, 'cost_sats': cost}
        }).execute()

    return {'purchased': product_id, 'cost': cost, 'items': len(data)}
```

**Telegram commands:**
- `/market` — show available external intelligence products and prices
- `/buy [product_id]` — Gato purchases from external provider
- `/spending` — show total spend by agent and category

---

## Part 3: Implementation Sequence

```
Phase 7A — Personal Briefing (do first, most immediately useful):
  Prompt 1: Create config/operator-context.md
  Prompt 2: Add generate_personal_briefing() to processor
  Prompt 3: Schedule + Telegram commands (/briefing, /context, /watch)

Phase 7B — Agent Wallets (foundation for commerce):
  Prompt 4: SQL schema (agent_wallets, agent_transactions)
  Prompt 5: Wallet functions + Supabase RPCs
  Prompt 6: Integrate spend logging into existing pollers
  Prompt 7: Telegram commands (/wallet, /ledger, /topup)

Phase 7C — Intelligence API (sell to other agents):
  Prompt 8: Create agentpulse_api.py with FastAPI endpoints
  Prompt 9: Docker service + routing
  Prompt 10: MCP server wrapper (future — when you're ready)

Phase 7D — External Purchases (buy from other agents):
  Prompt 11: Mock external service
  Prompt 12: Purchase flow in processor
  Prompt 13: Telegram commands (/market, /buy, /spending)
```

### What to Build First

**Phase 7A (personal briefing) is the highest-value, lowest-effort win.**
You can have this running in an afternoon. It uses your existing data pipeline,
your existing Telegram bot, and your existing LLM infrastructure. The only new
code is one function + one schedule + one Telegram command.

**Phase 7B (wallets) is the foundation for everything else.** Build this second.
Even as a simulation, it gives you the accounting infrastructure and the mental
model of agents as economic entities.

**Phase 7C and 7D are experiments.** Build them when you're curious, not when
you're under deadline. They teach you agent commerce plumbing but don't generate
immediate value. The learning is the value.

---

## Future: Real Money

Once the simulation works, connecting real money is a matter of swapping the ledger:

**Lightning Network (Bitcoin):**
- Use LNbits or LND to create wallets for each agent
- Payment verification: check the Lightning invoice was paid
- Advantage: instant settlement, low fees, Bitcoin-native (fits Gato's brand)
- Library: `lndgrpc` or `lnbits` Python SDK

**Solana / Stablecoins:**
- Use `solana-py` to create wallets
- Payment verification: check on-chain transaction
- Advantage: stablecoins avoid BTC volatility for commerce
- The Citrini article specifically mentions agents settling on Solana L2s

**Hybrid (recommended):**
- Gato holds BTC via Lightning (brand-consistent)
- Commerce happens in stablecoins (practical for pricing)
- The agent can convert between them as needed

Start with the simulation. Move to Lightning when the plumbing is solid.
The simulation teaches you the logic; the real money adds the finality.
```

---

## Env Vars to Add

```bash
# In config/.env
OPERATOR_TELEGRAM_CHAT_ID=<your personal Telegram chat ID>
```

To find your chat ID: send a message to your bot, then:
```bash
curl https://api.telegram.org/bot<TOKEN>/getUpdates | jq '.result[-1].message.chat.id'
```
