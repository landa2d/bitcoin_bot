# External Integrations

**Analysis Date:** 2026-05-26

## APIs & External Services

**LLM Providers:**
- DeepSeek (deepseek-chat) - Primary model, routed via llm-proxy
  - SDK: OpenAI SDK (compatible endpoint)
  - Auth: `DEEPSEEK_API_KEY` env var
  - Used by: processor, analyst, gato_brain, newsletter

- OpenAI (gpt-4o, gpt-4o-mini) - Analysis and narrative generation
  - SDK: openai>=1.50.0
  - Auth: `OPENAI_API_KEY` env var
  - Used by: all services via llm-proxy

- Anthropic (claude-sonnet-4-20250514) - Newsletter prose, research agent, block pipeline
  - SDK: anthropic>=0.80.0
  - Auth: via llm-proxy (set as `ANTHROPIC_API_KEY` in env)
  - Used by: newsletter, research, gato_brain

**Content & Search:**
- Tavily - Web search API
  - SDK: tavily-python>=0.5.0
  - Auth: `TAVILY_API_KEY` env var
  - Used by: gato_brain web_search module, lab-data-provider
  - Fallback: corpus_probe if unavailable

- X/Twitter (formerly Twitter) - Content posting and search
  - SDK: tweepy 4.14+
  - Auth: `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`, `X_BEARER_TOKEN`
  - Budget: `X_WEEKLY_BUDGET` ($5/week hard cap tracked in x_api_budget table)
  - Used by: processor for post_approved_x_content() and X source scraping
  - Rate limiting: `X_SEARCH_COST_ESTIMATE` ($0.01/request estimate)

- Moltbook - Social platform (posting, comments, reading)
  - SDK: Custom HTTP via httpx
  - Auth: `MOLTBOOK_API_TOKEN` env var
  - Base URL: `MOLTBOOK_API_BASE` (https://www.moltbook.com/api/v1)
  - Used by: Gato agent for posting/commenting
  - Health monitoring via heartbeat (optional integration package.json)

- RSS Feeds - Content ingestion
  - SDK: feedparser 6.0+
  - Source tier categories: AUTHORITY (tier 1), CURATED (tier 2), COMMUNITY (tier 3)
  - 15+ feeds configured in `docker/processor/agentpulse_processor.py` (a16z, HBR Tech, MIT Tech Review, TLDR AI, Ben's Bites, etc.)
  - `filter_exempt: True` on 12 tier-1 feeds (skip keyword filter, narrowly-focused sources)
  - Scraping: every 6 hours via processor scheduler

- GitHub - Code access
  - SDK: via httpx
  - Auth: `GITHUB_TOKEN` env var (optional)
  - Used by: gato_brain code_session for repo resolver, CTO commands

## Data Storage

**Databases:**
- **Supabase (Postgres)** - Primary data store
  - Connection: `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` (backend services use service role key for RLS bypass)
  - Client: supabase>=2.0.0
  - Migrations: 27 files in `supabase/migrations/` (001 through 027)
  - Key tables:
    - `source_posts` — ingested content from all scrapers (tier, category, publish_date, content)
    - `analysis_runs` — analyst findings and extracted opportunities
    - `x_content_candidates` — X posting pipeline (content_type, status, daily_index, narrative_context, content_category)
    - `x_editorial_arc` — editorial arc planning (post_sequence JSONB with day/week/angle/continuity/cta/engagement_keywords)
    - `agent_wallets` — per-agent budget tracking
    - `agent_transactions` — per-agent spend history
    - `research_queue` — async research task queue (status: queued/started/complete)
    - `x_api_budget` — weekly X API spend tracking
    - `embeddings` — pgvector knowledge base (recursive embedding/search)
    - `conversation_state` — Telegram session management
    - `newsletter_editions` — finalized newsletter content with status (draft/published/held)

**File Storage:**
- Local filesystem only
  - `/root/bitcoin_bot/data/openclaw/workspace/` — shared agent workspace (mounted across services)
  - `/root/bitcoin_bot/data/openclaw/agents/{agent_name}/` — per-agent persistent state
  - `/home/openclaw/.openclaw/queue/` — JSON-based task queue (OpenClaw workspace)
  - Logs: `/home/openclaw/.openclaw/logs/` (per-service .log files)

**Caching:**
- In-memory caching in processor (no external cache layer; all state in Supabase or filesystem)
- Embeddings cached in `embeddings` table (pgvector search via Supabase)

## Authentication & Identity

**Auth Provider:**
- Custom (no OAuth/OIDC)
  - Telegram ownership: `TELEGRAM_OWNER_ID` (single user, verified per chat session)
  - LLM Proxy authentication: per-agent API keys prefixed `ap_<agent>_<hash>` (bcrypt hashed in proxy.py)
  - Supabase RLS: service role key for backend, anon key for frontend (if exposed)
  - LNbits wallet auth: `LNBITS_ADMIN_KEY` (admin) + `LNBITS_INVOICE_KEY` (invoice/read-only)

**Identity Sources:**
- Telegram: user verification via `TELEGRAM_BOT_TOKEN` and owner check
- LLM Proxy: agent names embedded in request auth header (ap_<agent>_<hash>)

## Monitoring & Observability

**Error Tracking:**
- None detected (no Sentry, Rollbar, or similar)
- Local logging to stdout + file (`/home/openclaw/.openclaw/logs/*.log`)

**Logs:**
- Service logs: docker-compose json-file driver (10MB max, 3 files rotation)
- Application logs: Python logging to stdout + file handlers (FastAPI services via Uvicorn)
- Log level: configurable via `LOG_LEVEL` env var (default: info)
- Audit: SQL changes in Supabase audit log (built-in)

**Health Checks:**
- Docker container health: each service has HEALTHCHECK
  - Gato: `pgrep -f "node"`
  - Gato Brain: HTTP GET `/health` (FastAPI endpoint at :8100)
  - LLM Proxy: HTTP GET `/v1/proxy/health` (FastAPI endpoint at :8200)
  - Analyst/Newsletter/Research: `pgrep -f "<poller>.py"`
  - Processor: `pgrep -f "agentpulse_processor.py"`
- Startup checks: `preflight.sh` security supervisor script (env validation, secret redaction)

## CI/CD & Deployment

**Hosting:**
- Single Linux server (self-hosted)
- docker-compose orchestration (no Kubernetes)
- Supabase cloud (managed database)

**CI Pipeline:**
- None detected (.github/ directory does not exist)
- Manual deployment via `scripts/deploy.sh` and `scripts/deploy-identities.sh`
- Build: `cd /root/bitcoin_bot/docker && docker compose up -d --build [service]`
- Python syntax check before rebuild: `python3 -c "import ast; ast.parse(open('docker/processor/agentpulse_processor.py').read())"`

**Deployment Target:**
- Domain: `aiagentspulse.com` (web frontend via Caddy reverse proxy)
- Ports: 80/443 (web), 127.0.0.1:8200 (llm-proxy, internal only)
- Logs viewable via: `docker compose logs -f <service>`

## Environment Configuration

**Required env vars (from config/.env):**
- `OPENAI_API_KEY` — OpenAI API access
- `TELEGRAM_BOT_TOKEN` — Telegram bot control
- `TELEGRAM_OWNER_ID` — Owner verification
- `SUPABASE_URL` — Database endpoint
- `SUPABASE_SERVICE_KEY` — Backend database auth
- `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`, `X_BEARER_TOKEN` — Twitter/X posting
- `DEEPSEEK_API_KEY` — DeepSeek LLM access
- `ANTHROPIC_API_KEY` — Claude API access
- `RESEND_API_KEY` — Email delivery
- `TAVILY_API_KEY` — Web search
- `MOLTBOOK_API_TOKEN` — Social platform posting
- `LLM_PROXY_ADMIN_KEY` — Proxy authentication
- `GITHUB_TOKEN` — GitHub repo access (optional)
- Optional: `LNBITS_URL`, `LNBITS_ADMIN_KEY`, `LNBITS_INVOICE_KEY` — Bitcoin Lightning wallet

**Optional Config:**
- `LOG_LEVEL` (default: info)
- `X_WEEKLY_BUDGET` (default: $5.0)
- `X_SEARCH_COST_ESTIMATE` (default: $0.01/request)
- `X_SUBSCRIBE_URL` (default: https://aiagentspulse.com/#/subscribe)
- `AGENTPULSE_SCRAPE_INTERVAL_HOURS` (default: 6)
- `AGENTPULSE_ANALYSIS_INTERVAL_HOURS` (default: 12)

**Secrets location:**
- `config/.env` file (never committed, loaded by docker-compose `env_file`)
- Docker secrets: passed as environment variables to containers
- LLM Proxy admin key: `LLM_PROXY_ADMIN_KEY` (for `/v1/proxy/admin/*` endpoints)

## Webhooks & Callbacks

**Incoming:**
- Telegram Bot API → Gato (Telegram long-polling, no webhooks)
- Moltbook events: integrated via OpenClaw skill (post_watcher job)
- LNbits payment callbacks: optional (not actively used)

**Outgoing:**
- X (Twitter) API: POST to create tweets via tweepy
- Resend: POST to send emails via `resend.Emails.send()`
- Supabase: RPC calls for stored procedures and real-time subscriptions (not webhooks)
- LNbits: invoice creation (LNBITS_URL/api/v1/payments)

---

*Integration audit: 2026-05-26*
