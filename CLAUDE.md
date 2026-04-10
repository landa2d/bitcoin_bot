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
