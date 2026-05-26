# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

AgentPulse — a multi-agent intelligence platform for the AI agent economy. Eight Docker services: a Telegram-facing bot (Gato), a conversational middleware (Gato Brain), background processor, analyst, newsletter writer, research agent, LLM proxy, and web frontend. Controlled via Telegram commands. Deployed on a single Linux server.

## Build & Run Commands

```bash

# Start/rebuild everything

cd /root/bitcoin_bot/docker && docker compose up -d --build

# Rebuild specific service(s) after code changes

cd /root/bitcoin_bot/docker && docker compose up -d --build processor gato_brain

# View logs

docker compose -f /root/bitcoin_bot/docker/docker-compose.yml logs -f processor
docker compose -f /root/bitcoin_bot/docker/docker-compose.yml logs -f gato_brain

# Apply Supabase migration (use MCP tool or manually)

# Project ref: zxzaaqfowtqvmsbitqpu

# Syntax-check Python before rebuilding

python3 -c "import ast; ast.parse(open('docker/processor/agentpulse_processor.py').read())"

# Run tests

cd /root/bitcoin_bot && python3 -m pytest tests/
python3 -m pytest tests/test_llm_proxy.py -v  # single test file
```

## Architecture

### Service Communication Flow

```
Telegram → Gato (Node.js/OpenClaw) → Gato Brain (FastAPI :8100) → LLM Proxy (:8200) → DeepSeek/OpenAI/Anthropic
                                           ↕
                                    Supabase (Postgres)
                                           ↕
                                   Processor (background scheduler)
                                   Analyst / Newsletter / Research (pollers)
```

All LLM calls route through **llm-proxy** which handles auth (per-agent API keys), wallet reserve/settle, rate limiting, and streaming. Direct LLM calls from services go through `routed_llm_call()` in the processor.

### Key Files (by service)

- **Processor** (`docker/processor/agentpulse_processor.py`, ~9000 lines): The monolith. Contains all pipelines: scraping (RSS, HN, Moltbook, X), analysis, content surfacing, X posting, newsletter generation, personal briefings, queue processing, and 120+ scheduled jobs.
- **Gato Brain** (`docker/gato_brain/gato_brain.py`, ~1800 lines): FastAPI app handling Telegram command dispatch, session management, Claude-based response generation. `/x-*` commands handled in `handle_x_command()`. Code engine commands in `code_commands.py`. Intent routing via `intent_router.py` (DeepSeek-based classification into 6 intents).
- **LLM Proxy** (`docker/llm-proxy/`): Transparent proxy on :8200. Agent keys prefixed `ap_<agent>_<hash>`.
- **Config** (`config/agentpulse-config.json`): Model routing, per-agent budget limits, pipeline intervals, negotiation rules, LLM pricing.

### Telegram Command Dispatch (Gato Brain)

1. `/x-*` commands → `handle_x_command()` → direct handlers (no intent router)
2. `/code*` commands → `code_commands.handle_code_command()`
3. Everything else → `intent_router.route()` → corpus probe + LLM response

### X Distribution Pipeline

1. `surface_x_content_candidates()` runs every 6 hours — generates `sharp_take`, `narrative`, `engagement_reply`, `prediction` candidates in `x_content_candidates` table
2. Operator reviews via Telegram: `/x-plan` (view), `/x-approve` (approve), `/x-draft` (edit), `/x-reject`
3. `post_approved_x_content()` posts approved candidates via tweepy. Threads auto-split for content >280 chars.
4. **Editorial arc system**: `x_editorial_arc` table drives narrative-driven content. `_get_todays_arc_entry()` matches day+week from `post_sequence` JSON. Supports `continuity`, `cta`, `engagement_keywords` per entry.

### Database

Supabase (Postgres). Migrations in `supabase/migrations/` (001-027). Key tables:

- `source_posts` — ingested content from all scrapers
- `analysis_runs` — analyst findings
- `x_content_candidates` — X posting pipeline (content_type, status, daily_index, narrative_context, content_category)
- `x_editorial_arc` — editorial arc planning (post_sequence JSONB with day/week/angle/continuity/cta/engagement_keywords)
- `agent_wallets`, `agent_transactions` — per-agent budget tracking
- `embeddings` — pgvector knowledge base
- `conversation_state` — session management

### LLM Model Routing

Models configured in `config/agentpulse-config.json` under `models`. Default is `deepseek-chat`. GPT-4o used for analysis and narrative arc posts. Claude Sonnet for research agent. `get_model(task_type)` resolves which model to use.

## Environment

- All secrets in `config/.env` (loaded by docker-compose `env_file`).
- The `.env` file contains Supabase, OpenAI, DeepSeek, Anthropic, X/Twitter, Resend, Tavily, and inter-service auth keys.
- X API weekly budget cap: $5/week, tracked in `x_api_budget` table.

## Conventions

- Processor uses `schedule` library for cron-like jobs (not system cron).
- Queue-based task dispatch: JSON files in `/home/openclaw/.openclaw/workspace/agentpulse/queue/`, responses in `responses/`.
- Telegram messages split at 4000 chars (Telegram limit is 4096). Markdown sent first, falls back to plain text.
- `daily_index` on candidates is ephemeral — reassigned each morning, used for `/x-approve 1,3` style commands.
- Content candidates go through verification gate (`verify_briefing_references`) before surfacing.

<!-- GSD:project-start source:PROJECT.md -->

## Project

**AgentPulse**

A multi-agent intelligence platform for the AI agent economy: eight cooperating Docker services (Telegram-facing bot, conversational middleware, background processor, analyst, newsletter writer, research agent, LLM proxy, web frontend) that ingest content, synthesize findings, and publish daily-to-weekly outputs (newsletters, X posts, briefings) for the operator. Controlled via Telegram commands; deployed on a single Linux server with Supabase as the shared data store.

**Core Value:** **Synthesis with editorial integrity.** Autonomous ingestion and drafting accelerate the operator's output, but every consequential publication is gated by human approval — silence and homogenization are the failure modes to design against.

### Constraints

- **Architecture**: Single Linux server, Docker Compose orchestration, Supabase as shared store — no Kubernetes, no message broker, no external cache. New work integrates here.
- **LLM access**: All model calls route through `http://llm-proxy:8200`. Direct provider SDK calls are forbidden (budget governance + the RivalScope lesson).
- **Schema access**: `economy_map` tables accessed via direct PostgREST HTTP with `Accept-Profile: economy_map` header. Do not use supabase-py `.in_()` (silent failure).
- **Synthesis model**: Claude Sonnet for editorial synthesis (consistent with newsletter prose). DeepSeek V3 for bulk classification (cost-efficient). Both routed via proxy.
- **Publish path**: Block pages must reuse the existing `aiagentspulse.com` publish mechanism. Phase 0 diagnostic confirms the path before renderer design.
- **Autonomy boundary (the spine)**: Intake is autonomous; publishing is gated. Every design choice serves this rule. Append-only data structures + draft-then-approve flow + flagged-not-blocked validation.
- **Editorial framing in human hands**: `live_tension` and synthesis prompt voice (via `synth_identity.md`) stay operator-controlled; the loop synthesizes, the operator frames.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Languages

- Python 3.12 - Backend microservices (processor, gato_brain, analyst, newsletter, research, llm-proxy, lab-data-provider)
- Node.js 22 - User-facing Telegram agent (Gato) via OpenClaw framework
- Bash - Deployment, health checks, entrypoint scripts
- TypeScript/JavaScript - OpenClaw codebase (compiled from Node.js)

## Runtime

- Docker 20+ for containerized services (7 services in docker-compose)
- Python 3.12-slim (official image) for all Python services
- Node.js 22-slim for Gato
- Caddy 2-alpine for web server
- Python: pip (dependencies in `requirements.txt` per service)
- Node.js: pnpm (managed in OpenClaw container build)

## Frameworks

- FastAPI 0.115+ - API middleware services (gato_brain, llm-proxy, lab-data-provider)
- OpenClaw v2026.3.7 - Telegram agent framework (Node.js-based, cloned in gato Dockerfile)
- Anthropic SDK 0.80+ - Claude API client (gato_brain, newsletter, research)
- OpenAI SDK 1.50+ - GPT API client (all Python services)
- Supabase Python SDK 2.0+ - PostgreSQL client (all backend services)
- feedparser 6.0+ - RSS feed parsing (`docker/processor/agentpulse_processor.py`)
- httpx 0.25+ - Async HTTP client for all services
- tweepy 4.14+ - X/Twitter API v2 client (`docker/processor/agentpulse_processor.py`)
- Tavily Python SDK 0.5+ - Web search API (`docker/gato_brain/gato_brain.py`)
- schedule 1.2+ - In-process scheduler for background jobs (processor runs 120+ scheduled tasks)
- asyncio - Async concurrency in FastAPI services
- resend 2.0+ - Email delivery API (`docker/processor/agentpulse_processor.py`)
- pydantic 2.0+ - Data validation (all Python services)
- python-dotenv 1.0+ - Environment variable loading
- tenacity 8.0+ - Retry logic with exponential backoff (processor)
- bcrypt 4.0+ - Password hashing for LLM proxy authentication (`docker/llm-proxy/proxy.py`)
- markdown 3.5+ - Markdown parsing in processor
- uvicorn 0.30+ - ASGI server for FastAPI apps
- docker 7.0+ - Docker API client (gato_brain CTO commands for container status)

## Key Dependencies

- **Supabase (Postgres)** - Central database (27 migrations in `supabase/migrations/`)
- **OpenAI/DeepSeek/Anthropic** - LLM providers (routed through llm-proxy)
- **X (Twitter) API v2** - Content posting and search
- **Tavily** - Web search API
- **Resend** - Email delivery
- **LLM Proxy** (`docker/llm-proxy/proxy.py`) - Transparent proxy handling auth, wallet reserve/settle, rate limiting (routes to deepseek-chat, gpt-4o, claude-sonnet-4-20250514)
- **Moltbook** - Social platform integration (posting/comments)
- **LNbits** - Bitcoin Lightning wallet (optional, for payment flows)

## Configuration

- Loaded from `config/.env` (never committed)
- Schema defined in `config/env.schema.json`
- Per-service overrides via docker-compose environment blocks
- `config/agentpulse-config.json` - Model routing, budget limits, pipeline intervals, LLM pricing (deepseek-chat: $0.27/$1.10, gpt-4o: $2.50/$10.00, claude-sonnet-4-20250514: $3.00/$15.00)
- `config/openclaw-config.json` - OpenClaw agent configuration
- `config/persona.md` - Gato's system prompt/personality
- `config/guardrails.md` - Safety and moderation guidelines
- `config/operator-context.md` - Telegram operator instructions
- `config/x_source_accounts.json` - X account sources for scraping (14 accounts seeded)
- `docker/docker-compose.yml` - Multi-service orchestration with health checks
- Individual `Dockerfile` per service with layer caching
- `.env` file required at runtime (loads secrets: OPENAI_API_KEY, SUPABASE_URL/KEY, X_BEARER_TOKEN, TELEGRAM_BOT_TOKEN, RESEND_API_KEY, TAVILY_API_KEY, DEEPSEEK_API_KEY, MOLTBOOK_API_TOKEN)

## Platform Requirements

- Docker and Docker Compose
- Python 3.12+ (for syntax checking before build)
- Git (cloning OpenClaw in Gato Dockerfile)
- Bash (entrypoint scripts)
- Linux server (single-machine deployment, port 80/443 for web, 8200 for llm-proxy)
- 4GB+ total memory (gato: 4GB, others: 256-1536MB per docker-compose.yml)
- Supabase SaaS (project ref: zxzaaqfowtqvmsbitqpu)
- External LLM providers (OpenAI, DeepSeek, Anthropic accounts)
- X (Twitter) API v2 credentials with $5/week read budget
- Telegram Bot Token from @BotFather
- Optional: LNbits instance for Lightning payments

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

## Language and Style

- **Python 3.11+** throughout (f-strings, `str | None` union syntax, `match` not used)
- **snake_case** for all functions, variables, and module names
- **UPPER_SNAKE_CASE** for constants (API keys, config values, prompt templates)
- No enforced linter/formatter — no `.flake8`, `pyproject.toml[tool.ruff]`, or `black` config detected
- No pre-commit hooks configured

## Function Design

- Functions are long — many 100-300+ line functions in the processor and newsletter modules
- Top-level functions preferred over classes (processor has zero classes; gato_brain uses FastAPI app)
- LLM proxy uses classes for domain concepts: `RateLimiter`, wallet operations
- Test files mix class-based grouping (`class TestApiKeyValidation`) and flat `def test_*()` functions

## Error Handling

- **Broad `except Exception:` throughout** — 223 except clauses in the processor alone
- Pattern: try/except around entire pipeline functions, log error, continue
- `code_session.py` is particularly aggressive — 10+ bare `except Exception:` blocks
- No custom exception hierarchy
- No structured error types returned to callers
- LLM calls use `tenacity` retry with exponential backoff in the processor

## Logging

- Standard `logging` module everywhere
- Logger names: `"agentpulse"` (processor), `"gato-brain"` (gato_brain), `"llm-proxy"` (proxy)
- Log format: plain text, no structured/JSON logging
- Heavy use of `logger.info()` for pipeline progress tracking
- `logger.error()` with `exc_info=True` for exception logging

## Configuration

- `config/.env` for secrets (loaded via `dotenv`)
- `config/agentpulse-config.json` for model routing, budgets, pipeline intervals
- Config loaded at module level (not injected) — global variables throughout
- `get_model(task_type)` resolves model from config JSON

## LLM Call Patterns

- All LLM calls route through `routed_llm_call()` in processor or via LLM proxy HTTP API
- Prompts defined as module-level string constants (e.g., `ROUTER_PROMPT`, `MULTISOURCE_EXTRACTION_PROMPT`)
- JSON output parsing: `json.loads()` with regex fallback to extract JSON from markdown fences
- Temperature and max_tokens specified per-call, not centralized

## Database Access

- Direct Supabase client calls (`supabase.table("x").select("*").execute()`)
- No ORM, no repository pattern
- Supabase client initialized at module level as global
- Migrations are raw SQL in `supabase/migrations/`
- No migration runner in code — applied via Supabase CLI or MCP tool

## Async vs Sync

- **Gato Brain**: async FastAPI with `async def` handlers
- **LLM Proxy**: async FastAPI with `httpx.AsyncClient` for upstream calls
- **Processor**: synchronous — `schedule` library + `httpx.Client` (sync)
- **Analyst/Newsletter/Research**: synchronous poll loops with `time.sleep()`

## Import Patterns

- `sys.path.insert()` used to import across service boundaries (especially in tests)
- conftest.py has elaborate module-loading workaround for `schemas.py` name collisions
- No shared library or package — each service is self-contained
- Common dependencies: `httpx`, `supabase`, `openai`, `schedule`, `tenacity`

## Message Formatting

- Telegram messages split at 4000 chars (limit is 4096)
- Markdown sent first via `parse_mode="Markdown"`, falls back to plain text on failure
- Newsletter uses HTML for email delivery via Resend

<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

## Pattern

## Services and Layers

### User-Facing Layer

- **Gato** (`docker/gato/`) — Node.js Telegram bot (OpenClaw framework). Forwards all messages to Gato Brain via HTTP. No business logic.
- **Web** (`docker/web/`) — Static site served via Caddy. `docker/web/site/app.js` is the frontend.

### Intelligence Layer

- **Gato Brain** (`docker/gato_brain/gato_brain.py`, 2101 lines) — FastAPI on port 8100. Handles Telegram command dispatch, intent routing, conversation management, code engine, and CTO commands.

### Processing Layer

- **Processor** (`docker/processor/agentpulse_processor.py`, 10079 lines) — The monolith. Contains:

### Analysis Layer

- **Analyst** (`docker/analyst/analyst_poller.py`, 1213 lines) — Polls Supabase for analysis tasks. Runs trend detection, opportunity scoring, and structured analysis using LLM calls.
- **Research** (`docker/research/research_agent.py`, 999 lines) — Deep-dive research on selected topics. Uses Tavily for web enrichment.

### Newsletter Layer

- **Newsletter** (`docker/newsletter/`) — 4 files totaling 4249 lines:

### Infrastructure Layer

- **LLM Proxy** (`docker/llm-proxy/proxy.py`, 1424 lines) — FastAPI on port 8200. Routes LLM calls to DeepSeek/OpenAI/Anthropic. Handles per-agent API keys (`ap_<agent>_<hash>`), wallet reserve/settle, rate limiting, streaming.
- **Lab Data Provider** (`docker/lab-data-provider/data_provider.py`, 191 lines) — Lightweight data API for lab/experimental use.

## Data Flow

```

```

## Key Abstractions

- **`routed_llm_call()`** (processor) — Central LLM call dispatcher with model routing from config
- **`get_model(task_type)`** (processor) — Resolves model name from `agentpulse-config.json`
- **Intent Router** (gato_brain) — Classifies user messages into 6 intents, routes to appropriate handler
- **Block Pipeline** (newsletter) — 5-phase pipeline: A (selection) → prepass (angle) → B (structure) → C (prose) → D (verification) → E (voice)
- **Agent Wallets** — Per-agent budget tracking with reserve/settle pattern in LLM proxy

## Entry Points

| Service | Entry Point | Port |
|---------|------------|------|
| Gato | `inject-gato-brain.mjs` (Node.js) | — |
| Gato Brain | `gato_brain.py` (uvicorn) | 8100 |
| Processor | `agentpulse_processor.py` (schedule loop) | — |
| Analyst | `analyst_poller.py` (poll loop) | — |
| Newsletter | `newsletter_poller.py` (poll loop) | — |
| Research | `research_agent.py` (poll loop) | — |
| LLM Proxy | `proxy.py` (uvicorn) | 8200 |
| Web | Caddy static serve | 443 |

## Constraints

- Single-server deployment (no k8s/swarm)
- All services share one Supabase instance
- No message broker — all coordination via DB polling or HTTP
- Processor is a monolith (~10K lines) containing most business logic
- LLM Proxy is the single gateway for all AI model calls
- X API budget capped at $5/week

<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
