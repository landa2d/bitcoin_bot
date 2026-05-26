# Architecture

> Last mapped: 2026-05-26

## Pattern

**Microservice architecture** — 8 Docker services behind a single `docker-compose.yml`, communicating via HTTP APIs and a shared Supabase (Postgres) database. No message broker; coordination is poll-based or schedule-driven.

## Services and Layers

### User-Facing Layer
- **Gato** (`docker/gato/`) — Node.js Telegram bot (OpenClaw framework). Forwards all messages to Gato Brain via HTTP. No business logic.
- **Web** (`docker/web/`) — Static site served via Caddy. `docker/web/site/app.js` is the frontend.

### Intelligence Layer
- **Gato Brain** (`docker/gato_brain/gato_brain.py`, 2101 lines) — FastAPI on port 8100. Handles Telegram command dispatch, intent routing, conversation management, code engine, and CTO commands.
  - `intent_router.py` (286 lines) — DeepSeek-based classification into 6 intents: CORPUS_QUERY, WEB_SEARCH, HYBRID, DIRECT, STRUCTURED_QUERY, FOLLOW_UP
  - `corpus_probe.py` (200 lines) — pgvector similarity search against embeddings table
  - `web_search.py` (109 lines) — Tavily web search integration
  - `code_commands.py` (405 lines) — `/code*` command handlers
  - `code_session.py` (1285 lines) — Claude CLI session management for code engine
  - `cto_commands.py` (365 lines) — Docker status/logs via mounted socket
  - `query_templates.py` (339 lines) — Structured query templates (trending_tools, predictions, etc.)

### Processing Layer
- **Processor** (`docker/processor/agentpulse_processor.py`, 10079 lines) — The monolith. Contains:
  - RSS/HN/Moltbook/X scrapers
  - Problem/signal extraction (LLM-based)
  - Content surfacing and X posting pipeline
  - Newsletter data preparation
  - Queue processing for agent-initiated tasks
  - 120+ scheduled jobs via `schedule` library
  - All config: RSS feed definitions, keyword filters, model routing

### Analysis Layer
- **Analyst** (`docker/analyst/analyst_poller.py`, 1213 lines) — Polls Supabase for analysis tasks. Runs trend detection, opportunity scoring, and structured analysis using LLM calls.
- **Research** (`docker/research/research_agent.py`, 999 lines) — Deep-dive research on selected topics. Uses Tavily for web enrichment.

### Newsletter Layer
- **Newsletter** (`docker/newsletter/`) — 4 files totaling 4249 lines:
  - `newsletter_poller.py` (2258 lines) — Main orchestrator. Single-pass writer + block pipeline.
  - `block_selection.py` (535 lines) — Phase A: selects 25-35 blocks from source_posts
  - `block_pipeline.py` (687 lines) — Phases B/C/E: section structure, prose render, voice check
  - `verification.py` (719 lines) — Phase D: deterministic claim extraction + block matching

### Infrastructure Layer
- **LLM Proxy** (`docker/llm-proxy/proxy.py`, 1424 lines) — FastAPI on port 8200. Routes LLM calls to DeepSeek/OpenAI/Anthropic. Handles per-agent API keys (`ap_<agent>_<hash>`), wallet reserve/settle, rate limiting, streaming.
- **Lab Data Provider** (`docker/lab-data-provider/data_provider.py`, 191 lines) — Lightweight data API for lab/experimental use.

## Data Flow

```
[RSS/HN/X/Moltbook] → Processor (scrapers) → source_posts table
                                                    ↓
                                             Processor (extraction)
                                                    ↓
                                         analysis_runs / embeddings
                                                    ↓
                              ┌──────────────┬──────┴──────────────┐
                           Analyst        Research           Newsletter
                              ↓              ↓                    ↓
                        analysis_runs   research reports    newsletter editions
                                                                  ↓
                                                         Resend (email delivery)

[Telegram] → Gato → Gato Brain → Intent Router → corpus_probe / web_search / LLM
                                       ↓
                                  LLM Proxy → DeepSeek / OpenAI / Anthropic

[X Pipeline] Processor → x_content_candidates → operator review (Telegram) → tweepy post
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
