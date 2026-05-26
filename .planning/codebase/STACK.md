# Technology Stack

**Analysis Date:** 2026-05-26

## Languages

**Primary:**
- Python 3.12 - Backend microservices (processor, gato_brain, analyst, newsletter, research, llm-proxy, lab-data-provider)
- Node.js 22 - User-facing Telegram agent (Gato) via OpenClaw framework

**Secondary:**
- Bash - Deployment, health checks, entrypoint scripts
- TypeScript/JavaScript - OpenClaw codebase (compiled from Node.js)

## Runtime

**Environment:**
- Docker 20+ for containerized services (7 services in docker-compose)
- Python 3.12-slim (official image) for all Python services
- Node.js 22-slim for Gato
- Caddy 2-alpine for web server

**Package Manager:**
- Python: pip (dependencies in `requirements.txt` per service)
- Node.js: pnpm (managed in OpenClaw container build)

## Frameworks

**Core:**
- FastAPI 0.115+ - API middleware services (gato_brain, llm-proxy, lab-data-provider)
- OpenClaw v2026.3.7 - Telegram agent framework (Node.js-based, cloned in gato Dockerfile)
- Anthropic SDK 0.80+ - Claude API client (gato_brain, newsletter, research)
- OpenAI SDK 1.50+ - GPT API client (all Python services)
- Supabase Python SDK 2.0+ - PostgreSQL client (all backend services)

**Scraping & Feeds:**
- feedparser 6.0+ - RSS feed parsing (`docker/processor/agentpulse_processor.py`)
- httpx 0.25+ - Async HTTP client for all services
- tweepy 4.14+ - X/Twitter API v2 client (`docker/processor/agentpulse_processor.py`)
- Tavily Python SDK 0.5+ - Web search API (`docker/gato_brain/gato_brain.py`)

**Task Scheduling:**
- schedule 1.2+ - In-process scheduler for background jobs (processor runs 120+ scheduled tasks)
- asyncio - Async concurrency in FastAPI services

**Email & Notifications:**
- resend 2.0+ - Email delivery API (`docker/processor/agentpulse_processor.py`)

**Utilities:**
- pydantic 2.0+ - Data validation (all Python services)
- python-dotenv 1.0+ - Environment variable loading
- tenacity 8.0+ - Retry logic with exponential backoff (processor)
- bcrypt 4.0+ - Password hashing for LLM proxy authentication (`docker/llm-proxy/proxy.py`)
- markdown 3.5+ - Markdown parsing in processor
- uvicorn 0.30+ - ASGI server for FastAPI apps
- docker 7.0+ - Docker API client (gato_brain CTO commands for container status)

## Key Dependencies

**Critical:**
- **Supabase (Postgres)** - Central database (27 migrations in `supabase/migrations/`)
  - Tables: source_posts, analysis_runs, x_content_candidates, x_editorial_arc, agent_wallets, agent_transactions, embeddings (pgvector), conversation_state, research_queue
- **OpenAI/DeepSeek/Anthropic** - LLM providers (routed through llm-proxy)
- **X (Twitter) API v2** - Content posting and search
- **Tavily** - Web search API
- **Resend** - Email delivery

**Infrastructure:**
- **LLM Proxy** (`docker/llm-proxy/proxy.py`) - Transparent proxy handling auth, wallet reserve/settle, rate limiting (routes to deepseek-chat, gpt-4o, claude-sonnet-4-20250514)
- **Moltbook** - Social platform integration (posting/comments)
- **LNbits** - Bitcoin Lightning wallet (optional, for payment flows)

## Configuration

**Environment:**
- Loaded from `config/.env` (never committed)
- Schema defined in `config/env.schema.json`
- Per-service overrides via docker-compose environment blocks

**Key Config Files:**
- `config/agentpulse-config.json` - Model routing, budget limits, pipeline intervals, LLM pricing (deepseek-chat: $0.27/$1.10, gpt-4o: $2.50/$10.00, claude-sonnet-4-20250514: $3.00/$15.00)
- `config/openclaw-config.json` - OpenClaw agent configuration
- `config/persona.md` - Gato's system prompt/personality
- `config/guardrails.md` - Safety and moderation guidelines
- `config/operator-context.md` - Telegram operator instructions
- `config/x_source_accounts.json` - X account sources for scraping (14 accounts seeded)

**Build:**
- `docker/docker-compose.yml` - Multi-service orchestration with health checks
- Individual `Dockerfile` per service with layer caching
- `.env` file required at runtime (loads secrets: OPENAI_API_KEY, SUPABASE_URL/KEY, X_BEARER_TOKEN, TELEGRAM_BOT_TOKEN, RESEND_API_KEY, TAVILY_API_KEY, DEEPSEEK_API_KEY, MOLTBOOK_API_TOKEN)

## Platform Requirements

**Development:**
- Docker and Docker Compose
- Python 3.12+ (for syntax checking before build)
- Git (cloning OpenClaw in Gato Dockerfile)
- Bash (entrypoint scripts)

**Production:**
- Linux server (single-machine deployment, port 80/443 for web, 8200 for llm-proxy)
- 4GB+ total memory (gato: 4GB, others: 256-1536MB per docker-compose.yml)
- Supabase SaaS (project ref: zxzaaqfowtqvmsbitqpu)
- External LLM providers (OpenAI, DeepSeek, Anthropic accounts)
- X (Twitter) API v2 credentials with $5/week read budget
- Telegram Bot Token from @BotFather
- Optional: LNbits instance for Lightning payments

---

*Stack analysis: 2026-05-26*
