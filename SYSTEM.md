# AgentPulse — System Documentation

> **Last updated:** March 2026
> **Status:** Live on Hetzner (46.224.50.251). 7 services, 20 migrations applied.
> **Domain:** aiagentspulse.com

---

## 1. What Is AgentPulse

AgentPulse is an autonomous multi-agent intelligence platform that monitors the AI agent economy, detects emerging opportunities, and publishes a weekly newsletter — all without human intervention except a final publish command.

It wraps around **Gato**, a Bitcoin-maximalist Telegram bot built on the OpenClaw framework, adding four specialized AI agents, a conversational intelligence layer, a web archive, and a background processor.

### The Product

A **weekly intelligence brief** delivered to subscribers via Telegram and email. Two audience variants:

- **Builder Edition** — technical, focused on tools, repos, and implementation patterns
- **Impact Edition** — strategic, focused on market trends, investment signals, and business implications

Each edition includes:
- **Section A: Established Opportunities** — high-confidence business opportunities with staleness decay
- **Section B: Emerging Signals** — early-stage problems and clusters not yet mature enough for Section A
- **Section C: Curious Corner** — novel trending topics with high novelty scores
- **Section D: Prediction Tracker** — tracked predictions with status updates and accuracy scorecards
- **Spotlight** — a deep-dive conviction thesis from the Research agent on a selected topic
- **Radar** — topic lifecycle stages (emerging → growing → mature → fading)

### The Objective

Turn raw community noise (Moltbook posts, Hacker News, GitHub, RSS feeds, thought leader content) into actionable intelligence for builders and investors in the AI agent space. Automate the entire pipeline from data ingestion to editorial output, with human oversight only at the publish step.

---

## 2. Architecture Overview

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│     Gato     │    │   Analyst    │    │  Newsletter  │    │   Research   │
│  (Telegram)  │    │(Intelligence)│    │  (Editorial) │    │(Deep Thesis) │
│   Node.js    │    │   Python     │    │   Python     │    │   Python     │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │                   │
       │            ┌──────┴───────┐           │                   │
       │            │  Gato Brain  │           │                   │
       │            │  (FastAPI)   │           │                   │
       │            │  port 8100   │           │                   │
       │            └──────┬───────┘           │                   │
       │                   │                   │                   │
       └───────────────────┴───────────────────┴───────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │         Processor           │
                    │  (Scraper + Orchestrator)    │
                    │         Python               │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │       Supabase (Postgres)    │
                    │     + Web (Caddy + SPA)      │
                    └─────────────────────────────┘
```

All services communicate through **Supabase** (PostgreSQL). There is no direct service-to-service HTTP communication except Gato → Gato Brain. Services coordinate via the `agent_tasks` table using atomic task claiming.

### Network & Exposure

- All containers share `agentpulse-net` (Docker bridge network)
- Only the `web` service exposes external ports (80/443)
- Internal services are not reachable from the internet
- Supabase is hosted externally (Supabase cloud), accessed via HTTPS

---

## 3. The Seven Services

### 3.1 Gato (Telegram Bot)

| Property | Value |
|----------|-------|
| Container | `openclaw-gato` |
| Runtime | Node.js (OpenClaw framework) |
| Memory | 4 GB |
| LLM | Anthropic Claude (via OpenClaw auth-profiles) |

The user-facing interface. Receives Telegram commands, routes them to appropriate services, and delivers responses. Commands like `/scan`, `/newsletter_full`, `/publish` create tasks in the `agent_tasks` table. General conversation is proxied through Gato Brain.

### 3.2 Gato Brain (Conversational Intelligence)

| Property | Value |
|----------|-------|
| Container | `agentpulse-gato-brain` |
| Runtime | Python FastAPI, port 8100 |
| Memory | 512 MB |
| LLM | Anthropic / DeepSeek / OpenAI (multi-provider) |

Middleware that provides intelligent conversation capabilities to Gato. Manages conversation sessions, user profiles, usage tracking, and semantic search via embeddings. Loads its persona from `config/persona.md`.

### 3.3 Analyst (Intelligence Agent)

| Property | Value |
|----------|-------|
| Container | `agentpulse-analyst` |
| Runtime | Python, polls every 15s |
| Memory | 256 MB |
| LLM | DeepSeek (`deepseek-chat`) |
| Depends on | Processor (must be healthy) |

Polls `agent_tasks` for work. Produces analysis runs with theses, key findings, and analyst notes. Handles deep dives, opportunity reviews, and proactive scanning. Has a self-correction loop and budget awareness. Can be asked by Newsletter for data enrichment (negotiation system).

### 3.4 Newsletter (Editorial Agent)

| Property | Value |
|----------|-------|
| Container | `agentpulse-newsletter` |
| Runtime | Python, polls every 30s |
| Memory | 256 MB |
| LLM | DeepSeek (`deepseek-chat`) |
| Depends on | Processor (must be healthy) |

Polls `agent_tasks` for `write_newsletter` and `revise_newsletter` tasks. Loads IDENTITY.md + SKILL.md as its system prompt. Generates dual-audience content (builder + impact). Validates output via Pydantic schema. Can request enrichment from Analyst via the negotiation system (max 2 per newsletter). Saves as `status: draft` — never auto-publishes.

### 3.5 Research (Conviction Thesis Builder)

| Property | Value |
|----------|-------|
| Container | `agentpulse-research` |
| Runtime | Python, polls every 60s |
| Memory | 256 MB |
| LLM | Anthropic Claude Sonnet (`claude-sonnet-4-20250514`) |
| Depends on | Processor (must be healthy) |

Polls `research_queue` for spotlight candidates. Builds deep conviction theses with specific predictions and timelines. Uses thought leader content and source posts as evidence. Output goes to `spotlight_history` and feeds into the newsletter's Spotlight section.

### 3.6 Processor (Orchestrator)

| Property | Value |
|----------|-------|
| Container | `agentpulse-processor` |
| Runtime | Python (~6000+ lines) |
| Memory | 256 MB |
| LLM | DeepSeek (for extraction tasks) |

The backbone. Handles:
- **Scraping**: Moltbook, Hacker News, GitHub, RSS feeds, thought leader feeds (every 6h)
- **Extraction**: Problem detection, tool mention extraction, clustering
- **Orchestration**: Creates tasks for other agents, manages the Monday pipeline
- **Newsletter data preparation**: Gathers all data, applies freshness rules, creates the data package
- **Publishing**: Sends newsletter via Telegram + email when operator commands `/publish`
- **Email delivery**: Welcome emails to new subscribers, newsletter emails (dual-audience)
- **Verification**: Pre-publish reference checking via `verify_briefing_references()`
- **Proactive monitoring**: Anomaly detection, topic evolution tracking

### 3.7 Web (Newsletter Archive)

| Property | Value |
|----------|-------|
| Container | `agentpulse-web` |
| Runtime | Caddy + static SPA |
| Memory | 128 MB |
| Ports | 80, 443 (only externally-exposed service) |
| Domain | aiagentspulse.com |

Hosts the public newsletter archive and subscription page. Caddy handles automatic HTTPS via Let's Encrypt.

---

## 4. The Weekly Pipeline

The primary automated workflow runs weekly and produces the newsletter.

### Continuous (Every 6 Hours)

```
Processor scrapes all sources:
  ├── Moltbook API → moltbook_posts
  ├── Hacker News → source_posts (source='hackernews')
  ├── GitHub trending → source_posts (source='github')
  ├── RSS feeds → source_posts (source='rss_*')
  └── Thought leader feeds → source_posts (source='thought_leader_*')
```

### Analysis Cycle (Every 12 Hours)

```
Processor → enqueues analyse_posts task for Analyst
Analyst   → reads posts, produces analysis_run (theses, key findings)
Processor → runs problem extraction, clustering, opportunity generation
Processor → updates tool stats, topic evolution, trending topics
```

### Monday Pipeline (Newsletter Generation)

```
Step 1: Processor selects spotlight candidate → enqueues research task
Step 2: Research agent builds conviction thesis → saves to spotlight_history
Step 3: Processor runs prepare_newsletter_data():
        ├── Queries opportunities (with staleness decay + theme diversity penalty)
        ├── Queries emerging signals (problems + clusters)
        ├── Queries trending topics (curious corner)
        ├── Queries predictions (auto-expires overdue ones first)
        ├── Queries thought leader content
        ├── Queries topic evolution + radar topics
        ├── Queries latest analyst insights
        ├── Fetches spotlight for this edition
        ├── Applies freshness rules (exclusions, returning item limits)
        └── Creates write_newsletter task with full data package
Step 4: Newsletter agent receives task → generates dual-audience content
Step 5: Newsletter saves draft (status='draft') + local .md file
Step 6: Operator sends /publish via Telegram
Step 7: Processor runs verify_briefing_references() (hallucination check)
Step 8: Processor sends to Telegram + sends emails to subscribers
Step 9: Processor updates appearance counters + creates predictions
```

### Key Design Principle

The newsletter is **never auto-published**. A human must send `/publish` to deliver it. This is the single human-in-the-loop control point.

---

## 5. Data Sources

The processor ingests from multiple sources, classified by trust tier:

| Tier | Sources | Treatment |
|------|---------|-----------|
| **Tier 1 (Authority)** | a16z, HBR, MIT Tech Review | High-authority, cited directly, maximum weight |
| **Tier 1.5 (Thought Leaders)** | 6 configured feeds (GitHub profiles, personal blogs of key AI figures) | Cited by name, used for Research agent deep dives |
| **Tier 2 (Curated)** | TLDR AI, Ben's Bites, similar aggregators | Mentioned naturally, moderate weight |
| **Tier 3 (Community)** | Moltbook, Hacker News, GitHub trending | Volume signal, not cited as authorities |

### Scraping Details

- **Moltbook**: Direct API, 5 submolts (bitcoin, agents, ai, tech, general), 50 posts per submolt
- **Hacker News**: Top stories, filtered for AI/agent relevance
- **GitHub**: Trending repos, filtered for AI/agent relevance
- **RSS Feeds**: Configurable list of feeds
- **Thought Leaders**: 6 configured feeds, scraped every 6h with a 14-day window

All posts are deduplicated via `source_posts` to prevent the same story appearing twice across sources.

---

## 6. Task System & Agent Communication

Agents communicate exclusively through the `agent_tasks` Supabase table. No direct HTTP calls between agents.

### Atomic Task Claiming

Tasks are claimed atomically via PostgreSQL `FOR UPDATE SKIP LOCKED` (migration 003):

```sql
claim_agent_task(p_assigned_to TEXT, p_limit INT)   -- analyst, newsletter
claim_research_task(p_limit INT)                     -- research agent
```

This prevents race conditions — if two agent instances poll simultaneously, each gets a different task.

### Task Types

| Task Type | Assigned To | Created By | Purpose |
|-----------|-------------|------------|---------|
| `analyse_posts` | analyst | processor | Full analysis run |
| `enrich_for_newsletter` | analyst | newsletter (negotiation) | Data enrichment request |
| `write_newsletter` | newsletter | processor | Write the weekly brief |
| `revise_newsletter` | newsletter | gato (operator) | Revise a draft with feedback |
| `research_spotlight` | research | processor | Deep-dive thesis |
| `create_negotiation` | processor | newsletter | Log a negotiation record |
| `review_opportunity` | analyst | gato (operator) | Re-evaluate an opportunity |
| `deep_dive` | analyst | gato (operator) | Deep analysis on a topic |

### Agent Negotiations

When the Newsletter agent needs richer data, it can request enrichment from the Analyst:

1. Newsletter includes a `negotiation_request` in its JSON output
2. Newsletter poller creates a `create_negotiation` task for Processor
3. Newsletter poller creates an `enrich_for_newsletter` task for Analyst
4. Analyst responds with enriched data
5. Newsletter uses the enriched data in a revision pass

Max 2 negotiations per newsletter. Configurable in `agentpulse-config.json`.

---

## 7. Database Schema

**20 migrations applied.** Supabase (PostgreSQL) with Row Level Security enabled. All agents use the `service_role` key (bypasses RLS).

### Migration Map

| # | Contents |
|---|----------|
| 001 | `moltbook_posts`, `problems`, `problem_clusters`, `opportunities`, `tool_mentions`, `pipeline_runs` |
| 002 | `research_queue`, `spotlight_history`, `predictions` |
| 003 | `claim_agent_task()` and `claim_research_task()` RPC functions |
| 004 | `source_posts`, `agent_tasks`, `agent_daily_usage`, `analysis_runs`, `newsletters`, `topic_evolution`, `cross_signals`, `trending_topics`, `agent_negotiations` |
| 005 | Performance indexes on all major tables |
| 006 | Row Level Security policies |
| 007 | Staleness columns (`newsletter_appearances`, `last_featured_at`, `effective_score`) |
| 008 | `predictions.target_date` column |
| 009 | `llm_call_log` table for LLM usage tracking |
| 010 | Newsletter theme tracking columns |
| 011 | Dual-audience columns, `subscribers` table with mode preference |
| 012 | Default subscribers to `active` (no double opt-in) |
| 013 | `unsubscribe()` RPC function |
| 014 | `welcome_email_sent_at` column on subscribers |
| 015 | `agent_wallets` table |
| 016 | `embeddings` table for vector search |
| 017 | `conversation_sessions`, `conversation_messages`, `corpus_users`, `user_usage`, `query_log` |
| 018 | `content_links` table |
| 019 | `email_log` table, subscriber upsert RLS policy |
| 020 | `verification_warnings` column on newsletters |

### Core Tables

| Table | Purpose |
|-------|---------|
| `moltbook_posts` | Raw scraped Moltbook posts |
| `source_posts` | Deduplicated posts from all sources (HN, GitHub, RSS, thought leaders) |
| `problems` | Extracted problem signals with frequency counts and categories |
| `problem_clusters` | Grouped problems with opportunity scores |
| `opportunities` | Business opportunities derived from clusters (confidence scores, appearances) |
| `tool_mentions` | Individual tool/product mentions with sentiment |
| `tool_stats` | Aggregated tool statistics (mentions_7d, avg_sentiment) |
| `agent_tasks` | Task queue for all agent communication |
| `agent_daily_usage` | Per-agent budget tracking |
| `analysis_runs` | Analyst output: theses, key findings, analyst notes |
| `spotlight_history` | Research agent's conviction theses |
| `research_queue` | Queue for research tasks |
| `newsletters` | Newsletter drafts and published editions (dual-audience content) |
| `predictions` | Tracked predictions with status (active/confirmed/faded/expired/refuted) |
| `topic_evolution` | Topic lifecycle tracking (emerging → growing → mature → fading) |
| `trending_topics` | Current trending topics with novelty scores |
| `subscribers` | Email subscribers with mode_preference (builder/impact/both) |
| `email_log` | Every email sent with Resend ID and delivery status |
| `agent_wallets` | Per-agent sat balances for internal cost tracking |
| `embeddings` | Vector embeddings for semantic search |
| `conversation_sessions` | User conversation sessions (gato_brain) |
| `conversation_messages` | Individual messages within sessions |

### Staleness & Freshness System

The newsletter uses a decay formula to prevent stale content from dominating:

```
effective_score = confidence_score × 0.7 ^ newsletter_appearances
```

Additional freshness rules:
- Opportunities featured in the last 2 editions are excluded
- Returning items require new analyst review (`last_reviewed_at > last_featured_at`)
- Section B and C only accept new (never-featured) items
- Theme diversity penalty: opportunities matching recent newsletter themes get demoted
- Analyst theses overlapping with recent themes are filtered

---

## 8. Email Subscription & Delivery

### Subscription Flow

```
Web form (aiagentspulse.com) → Supabase upsert into subscribers table
  - mode_preference: 'builder', 'impact', or 'both'
  - status: 'active' (no double opt-in required)
  - Re-subscribing updates mode_preference (upsert, not duplicate error)
```

### Welcome Emails

The processor polls every ~60 seconds for active subscribers where `welcome_email_sent_at IS NULL`, sends a personalized welcome email via Resend, and marks them as sent.

### Newsletter Delivery

When an operator sends `/publish`:
- **Builder** subscribers receive the builder-themed email (dark theme, tech green accent)
- **Impact** subscribers receive the impact-themed email (light theme, warm orange accent)
- **Both** subscribers receive two separate emails

### Email Tracking

All emails are logged to `email_log` with:
- `resend_id` — cross-reference with Resend dashboard
- `status` — 'sent' or 'failed'
- `error_message` — populated on failure
- `email_type` — 'welcome' or 'newsletter'

**Provider:** Resend. From: `AgentPulse <newsletter@contact.aiagentspulse.com>`.

### Unsubscribe

`unsubscribe()` RPC function (migration 013). Frontend route: `#/unsubscribe?id=[uuid]`. One-click `List-Unsubscribe` header in all emails.

---

## 9. Model Routing & Cost Management

### Model Assignment

| Agent | Default Model | Provider | Cost (per 1M tokens in/out) |
|-------|---------------|----------|-----------------------------|
| Analyst | `deepseek-chat` | DeepSeek | $0.27 / $1.10 |
| Newsletter | `deepseek-chat` | DeepSeek | $0.27 / $1.10 |
| Research | `claude-sonnet-4-20250514` | Anthropic | $3.00 / $15.00 |
| Processor (extraction) | `deepseek-chat` | DeepSeek | $0.27 / $1.10 |
| Gato | Claude | Anthropic | Configured via OpenClaw |

Models are configurable via environment variables (`ANALYST_MODEL`, `NEWSLETTER_MODEL`, `RESEARCH_MODEL`) and `agentpulse-config.json`.

### Budget System

Every task includes a budget envelope from `agentpulse-config.json`:

```json
{
  "analyst": {
    "full_analysis": { "max_llm_calls": 8, "max_seconds": 300, "max_subtasks": 3 },
    "deep_dive": { "max_llm_calls": 5, "max_seconds": 180, "max_subtasks": 2 }
  },
  "newsletter": {
    "write_newsletter": { "max_llm_calls": 6, "max_seconds": 300, "max_subtasks": 2 }
  },
  "global": {
    "max_daily_llm_calls": 100,
    "max_daily_proactive_alerts": 5
  }
}
```

Agents track usage in `agent_daily_usage` and return `budget_usage` in their output. The analyst checks `is_daily_budget_exhausted()` before starting new work.

### Agent Wallets

Internal sat-denominated wallets track per-agent LLM spending. Each model has a sat cost in `wallet_pricing`. Wallet balances are viewable via `/wallet` and toppable via `/topup [agent] [amount]`.

---

## 10. Security Protocols

### Container Security

- All containers run as non-root user (`openclaw`)
- Resource limits enforced: 4GB (gato), 512MB (brain), 256MB (analyst/newsletter/research/processor), 128MB (web)
- Only port 80/443 exposed externally (web service only)
- All inter-service traffic stays on the Docker bridge network
- Log rotation: 10MB max per file, 3 files per service

### Secrets Management

- All secrets stored in `config/.env` (gitignored)
- `env_file:` loads secrets into containers; `environment:` only used for non-secret overrides
- Supabase `service_role` key used by agents (bypasses RLS)
- No SSH keys or passphrases in `.env`

### Security Supervisor

Boot-time validation (`docker/preflight.sh`):
- Checks all required env keys are present
- Validates safety relationships (e.g., approval thresholds)
- Writes redacted status to `data/openclaw/logs/security-supervisor-status.json`
- Appends audit log entries to `data/openclaw/logs/security-supervisor-audit.log`
- Sends Telegram alert if configured

### Content Safety

- **OpenAI Moderation API**: All outbound Moltbook content checked before posting
- **Content categories blocked**: hate, threats, self-harm, sexual, violence
- **Word blacklist**: Profanity, slurs, personal information patterns, API key patterns
- **Prompt injection defense**: External agent content wrapped in delimiters with explicit system instructions

### Rate Limiting

| Action | Limit | Period |
|--------|-------|--------|
| Moltbook posts | 5 | Per hour |
| Moltbook comments | 10 | Per hour |
| Wallet payments | 10,000 sats | Per day |
| LLM calls (global) | 100 | Per day |
| Proactive alerts | 5 | Per day |

### Approval Workflows

- **Post approval** (`REQUIRE_POST_APPROVAL=true`): Agent drafts → sends to owner via Telegram → waits for approve/deny/edit
- **Payment approval** (above threshold): Same flow for Lightning payments above `WALLET_APPROVAL_THRESHOLD_SATS`

### Emergency Controls

| Command | Effect |
|---------|--------|
| `/stop` | Pause all activity |
| `/emergency` | Stop immediately, notify owner |
| `/reset` | Clear context, restart fresh |

Auto-pause triggers: 3+ moderation blocks/hour, daily spend limit reached, 5+ API errors in 10 minutes.

### Source Integrity (Hallucination Prevention)

Three-layer defense:
1. **Identity-level rules**: All agent IDENTITY.md files include Source Attribution Standards — no composite fabrication, no unsourced metrics, mandatory hedging
2. **Pre-publish verification**: `verify_briefing_references()` cross-checks newsletter content against source data before publishing
3. **Audit trail**: Verification warnings saved to `newsletters.verification_warnings` column

---

## 11. Key File Paths

### Agent Code

| File | Service | Lines |
|------|---------|-------|
| `docker/processor/agentpulse_processor.py` | Processor | ~6000+ |
| `docker/analyst/analyst_poller.py` | Analyst | ~600 |
| `docker/newsletter/newsletter_poller.py` | Newsletter | ~1100 |
| `docker/research/research_agent.py` | Research | ~400 |
| `docker/gato_brain/gato_brain.py` | Gato Brain | ~500 |

### Identity & Skills (LLM System Prompts)

| File | Agent | Purpose |
|------|-------|---------|
| `templates/analyst/IDENTITY.md` | Analyst | Voice, analysis rules, source attribution |
| `templates/newsletter/IDENTITY.md` | Newsletter | Editorial voice, structure rules, anti-repetition |
| `templates/research/IDENTITY.md` | Research | Conviction thesis style, source integrity |
| `skills/agentpulse/SKILL.md` | Gato | Command routing table + agent persona |
| `skills/analyst/SKILL.md` | Analyst | Task handling + output format |
| `skills/newsletter/SKILL.md` | Newsletter | Section structure + validation rules |
| `config/persona.md` | Gato / Brain | Bitcoin maximalist personality |

### Configuration

| File | Purpose |
|------|---------|
| `config/.env` | All secrets (NEVER committed) |
| `config/agentpulse-config.json` | Budget limits, model routing, pipeline settings, negotiation rules |
| `config/guardrails.md` | Safety mechanisms documentation |
| `docker/docker-compose.yml` | Service definitions, volumes, health checks |

### Migrations

`supabase/migrations/001_initial_schema.sql` through `020_newsletter_verification.sql`

---

## 12. Deployment

### Infrastructure

- **Host**: Hetzner VPS (Ubuntu, 8 GB RAM)
- **IP**: 46.224.50.251
- **Domain**: aiagentspulse.com (DNS → Hetzner IP, Caddy handles HTTPS)
- **Project path on server**: `/opt/bitcoin_bot/`

### Common Operations

```bash
# Deploy all services
cd /opt/bitcoin_bot/docker
docker compose build && docker compose up -d

# Restart without rebuild (config/persona/identity changes)
docker compose restart

# Restart a single service
docker compose restart newsletter

# Rebuild + restart a single service (code changes)
docker compose build newsletter && docker compose up -d newsletter

# View logs
docker compose logs -f                # all services
docker compose logs -f processor      # single service
docker compose logs --tail 100 analyst

# Check health
docker compose ps
```

### Deployment Workflow

1. Make changes locally (edit code, config, identity files)
2. Push to git: `git push`
3. Pull on server: `cd /opt/bitcoin_bot && git pull`
4. Rebuild affected services: `cd docker && docker compose build <service> && docker compose up -d <service>`

For identity/config changes only (no code change): `docker compose restart <service>`

### After Changing IDENTITY.md

Newsletter IDENTITY.md requires a manual sync:
```bash
cp templates/newsletter/IDENTITY.md data/openclaw/agents/newsletter/agent/IDENTITY.md
docker compose restart newsletter
```

Research IDENTITY.md is directly mounted (no sync needed):
```bash
docker compose restart research
```

---

## 13. Telegram Commands

### General

| Command | Action |
|---------|--------|
| (any message) | Chat with Gato |
| `/stop` | Pause agent |
| `/status` | Agent status |
| `/wallet` | Wallet balance |

### Intelligence Pipeline

| Command | Action |
|---------|--------|
| `/scan` | Trigger scraping + analysis pipeline |
| `/invest_scan` | Run investment scanner |
| `/deep_dive [topic]` | Deep analysis on a topic |
| `/review [name]` | Re-evaluate an opportunity |
| `/thesis [topic]` | Show Analyst's thesis on a topic |

### Newsletter

| Command | Action |
|---------|--------|
| `/newsletter_full` | Generate a new newsletter (prepare data + write) |
| `/newsletter_publish` | Publish the latest draft |
| `/newsletter_revise [notes]` | Revise draft with feedback |
| `/brief` | Show latest newsletter content |

### Monitoring

| Command | Action |
|---------|--------|
| `/pulse_status` | System status |
| `/opportunities` | Top opportunities |
| `/signals` | Emerging signals |
| `/toolradar` | Tool mention stats |
| `/toolcheck [name]` | Stats for a specific tool |
| `/analysis` | Latest analyst output |
| `/predictions` | Prediction tracker |
| `/topics` | Topic lifecycle stages |
| `/freshness` | What's excluded from next newsletter |
| `/sources` | Scraping status per source |
| `/curious` | Trending topics |
| `/subscribers` | Subscriber count + mode breakdown |

### Budget & Agents

| Command | Action |
|---------|--------|
| `/budget` | Per-agent daily usage |
| `/alerts` | Recent proactive alerts |
| `/negotiations` | Active agent negotiations |
| `/wallet` | Agent wallet balances |
| `/ledger [agent]` | Last 10 transactions for an agent |
| `/topup [agent] [amount]` | Top up agent wallet |

---

## 14. Testing

```bash
pytest tests/ -v    # from project root
```

| Test File | Coverage |
|-----------|----------|
| `tests/test_schemas.py` | Pydantic schema validation |
| `tests/test_migrations.py` | Migration SQL correctness |
| `tests/test_error_paths.py` | Error handling paths |

`tests/conftest.py` pre-imports pollers at startup to avoid `sys.modules["schemas"]` conflicts.

---

## 15. Environment Variables Reference

### Required

| Variable | Used By |
|----------|---------|
| `SUPABASE_URL` | All services |
| `SUPABASE_SERVICE_KEY` | All services |
| `DEEPSEEK_API_KEY` | Analyst, Newsletter, Processor, Brain |
| `TELEGRAM_BOT_TOKEN` | Gato, Processor |
| `TELEGRAM_OWNER_ID` | Gato, Processor |

### Important

| Variable | Used By |
|----------|---------|
| `ANTHROPIC_AGENT_KEY` | Research, Gato Brain |
| `OPENAI_API_KEY` | Processor (extraction), Brain |
| `RESEND_API_KEY` | Processor (email delivery) |
| `GITHUB_TOKEN` | Processor (GitHub scraping) |
| `TAVILY_API_KEY` | Gato Brain (search) |

### Optional

| Variable | Used By | Default |
|----------|---------|---------|
| `MOLTBOOK_API_TOKEN` | Processor (Moltbook scraping) | — |
| `ANALYST_MODEL` | Analyst | `deepseek-chat` |
| `NEWSLETTER_MODEL` | Newsletter | `deepseek-chat` |
| `RESEARCH_MODEL` | Research | `claude-sonnet-4-20250514` |
| `MAX_POSTS_PER_HOUR` | Gato | `5` |
| `REQUIRE_POST_APPROVAL` | Gato | `true` |
| `WALLET_DAILY_LIMIT_SATS` | Gato | `10000` |
| `WALLET_APPROVAL_THRESHOLD_SATS` | Gato | `1000` |

---

## 16. Hard-Won Lessons

Operational learnings documented in `LEARNINGS.md`:

1. **LLM prompt rules don't enforce behavior** — Enforce constraints in code (data layer), not in prompts. Prompts are for editorial judgment.
2. **Docker `environment:` overrides `env_file:`** — Don't duplicate env vars. Use `env_file:` for secrets, `environment:` only for per-service overrides.
3. **Theme diversity requires closing ALL input vectors** — A filter on one data source doesn't filter the output. Every input path must be checked.
4. **Agent boundaries create enforcement gaps** — The agent that controls the data has the real power. Enforce at the handoff point.
5. **Cold-start problems in tracking systems** — Always include a backfill step when adding new tracking columns.
6. **Fallback models must be valid for the target API** — When routing across providers, change both client AND model name.
7. **Validators catch what prompt rules miss** — Post-generation validators (regex) are more reliable than prompt instructions for hard constraints.

---

## 17. Related Documentation

| Document | Purpose |
|----------|---------|
| `README.md` | Quick start, setup, troubleshooting |
| `ARCHITECTURE.md` | Technical architecture reference |
| `LEARNINGS.md` | Operational lessons |
| `config/guardrails.md` | Safety mechanisms |
| `docs/security-supervisor.md` | Boot-time security checks |
| `docs/telegram-setup.md` | Telegram bot setup guide |
| `docs/lnbits-setup.md` | Lightning wallet setup |

Historical planning documents (useful for context but not current):
- `AGENTPULSE_ARCHITECTURE.md` — Phase 1 planning
- `AGENTPULSE_PHASE2_ARCHITECTURE (1).md` — Phase 2 planning
- `AGENTPULSE_PHASE3_ROADMAP.md` — Phase 3-5 roadmap
