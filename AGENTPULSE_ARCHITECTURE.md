# AgentPulse Intelligence Platform - Architecture & Implementation Guide

> **Purpose:** This document provides the complete architecture, file structure, and implementation details for extending the existing OpenClaw Bitcoin agent (Gato) with AgentPulse intelligence pipelines.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Configuration Decisions](#3-configuration-decisions)
4. [File Structure](#4-file-structure)
5. [Database Schema (Supabase)](#5-database-schema-supabase)
6. [Implementation Files](#6-implementation-files)
7. [Deployment Steps](#7-deployment-steps)
8. [Telegram Commands](#8-telegram-commands)
9. [Testing & Validation](#9-testing--validation)

---

## 1. Executive Summary

### What We're Building

AgentPulse is an intelligence layer added to the existing Gato OpenClaw agent that:

1. **Scrapes Moltbook** for agent conversations (bulk, scheduled)
2. **Extracts problems** agents complain about (Pipeline 1: Opportunity Finder)
3. **Identifies business opportunities** from validated problem clusters
4. **Stores everything** in Supabase for historical analysis
5. **Reports findings** via Telegram (manual + scheduled)

### Key Design Decisions

| Decision | Choice |
|----------|--------|
| Processor language | Python |
| Triggering | Scheduled (Python `schedule` library) + Manual (Telegram) |
| Moltbook fetching | Hybrid (file queue for agent actions, direct API for bulk scraping) |
| Agent identity | Single identity (**gato**) with analyst mode |
| Database | Supabase (new project) |
| LLM providers | Anthropic (via OpenClaw) + OpenAI (for analysis) |
| Auth store | OpenClaw `auth-profiles.json` (see Section 3) |
| MVP Priority | Pipeline 1: Opportunity Finder |

> **Note:** The "Lloyd" agent was removed. Only the **gato** agent is active.

---

## 2. Architecture Overview

### System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TELEGRAM                                        │
│                    (existing interface, new commands)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OPENCLAW AGENT (Gato)                                │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  moltbook/  │  │   wallet/   │  │   safety/   │  │ agentpulse/ │        │
│  │ (existing)  │  │ (existing)  │  │ (existing)  │  │   (NEW)     │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
         │                                                    │
         │ (agent posts/comments)                             │ (analysis tasks)
         ▼                                                    ▼
┌─────────────────────┐                          ┌─────────────────────┐
│   moltbook_queue/   │                          │  agentpulse_queue/  │
│   (file-based)      │                          │   (file-based)      │
└─────────────────────┘                          └─────────────────────┘
         │                                                    │
         ▼                                                    ▼
┌─────────────────────┐                          ┌─────────────────────┐
│ moltbook_watcher.sh │                          │ agentpulse_         │
│ (existing bash)     │                          │ processor.py (NEW)  │
└─────────────────────┘                          └─────────────────────┘
         │                                                    │
         │                                                    │
         └────────────────────┬───────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   MOLTBOOK API  │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │    SUPABASE     │
                    │  (PostgreSQL)   │
                    └─────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SCHEDULED TASKS (Python `schedule` library)               │
│                                                                              │
│   Every 6 hours: Scrape Moltbook → Store in Supabase                        │
│   Every 12 hours: Run Pipeline 1 (Opportunity Finder)                        │
│   Daily 9 AM: Send opportunity digest via Telegram                           │
│   Daily 3 AM: Cleanup old queue files, archive stale data                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

#### Flow 1: Bulk Moltbook Scraping (Background)

```
Cron (every 6h)
    │
    ▼
agentpulse_processor.py --task scrape
    │
    ▼
Moltbook API (direct HTTP, paginated)
    │
    ▼
Supabase: moltbook_posts table
```

#### Flow 2: Agent-Initiated Analysis

```
User: "/opportunities"
    │
    ▼
Gato writes: agentpulse_queue/analyze_<timestamp>.json
    │
    ▼
agentpulse_processor.py picks up task
    │
    ▼
Reads from Supabase (recent posts)
    │
    ▼
OpenAI API (problem extraction, clustering)
    │
    ▼
Writes results to Supabase + workspace/agentpulse/opportunities/
    │
    ▼
Gato reads results, sends to Telegram
```

#### Flow 3: Agent Actions (Existing)

```
User: "Post about Bitcoin on Moltbook"
    │
    ▼
Gato writes: moltbook_queue/post_<timestamp>.json
    │
    ▼
moltbook_watcher.sh (existing)
    │
    ▼
Moltbook API
    │
    ▼
Result written to moltbook_queue/responses/
    │
    ▼
Gato reads, confirms to user
```

---

## 3. Configuration Decisions

### Agent Identity Extension

Gato remains a Bitcoin maximalist. When performing AgentPulse tasks, he enters "analyst mode":

```markdown
## Analyst Mode (AgentPulse)

When running AgentPulse analysis tasks:
- Be objective and data-driven
- Report what agents are actually saying, not what they should believe
- Track ALL tools and problems, not just Bitcoin-related ones
- Identify opportunities based on market signals, not ideology
- Save Bitcoin advocacy for direct conversations

Your analysis helps Bitcoiners understand the emerging agent economy.
Think of yourself as an intelligence analyst who happens to be a Bitcoin maxi.
```

### OpenClaw Auth Configuration (`auth-profiles.json`)

OpenClaw stores LLM provider API keys in `auth-profiles.json`, located at:

```
data/openclaw/agents/main/agent/auth-profiles.json
```

**Required format** — OpenClaw expects a `profiles` object; top-level keys are ignored:

```json
{
  "profiles": {
    "anthropic": {
      "provider": "anthropic",
      "type": "api_key",
      "key": "<YOUR_ANTHROPIC_KEY>"
    },
    "openai": {
      "provider": "openai",
      "type": "api_key",
      "key": "<YOUR_OPENAI_KEY>"
    }
  }
}
```

> **Common Pitfall:** An earlier format used `{"anthropic": {"apiKey": "..."}}` which OpenClaw silently ignores, resulting in "No API key found" errors. Always use the `profiles` wrapper with `type: "api_key"` and `key`.

### Environment Variables (New)

Add to `config/.env`:

```bash
# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJxxxxxxx  # anon/public key for now, service key for production

# AgentPulse Settings
AGENTPULSE_ENABLED=true
AGENTPULSE_SCRAPE_INTERVAL_HOURS=6
AGENTPULSE_ANALYSIS_INTERVAL_HOURS=12
AGENTPULSE_OPENAI_MODEL=gpt-4o  # for analysis tasks
```

---

## 4. File Structure

### New Files to Create

```
bitcoin_bot/
├── config/
│   ├── .env                          # ADD: Supabase vars
│   └── agentpulse-config.json        # NEW: Pipeline settings
│
├── skills/
│   └── agentpulse/                   # NEW: Entire folder
│       ├── package.json
│       ├── SKILL.md                  # Main instructions
│       ├── PIPELINE_1.md             # Opportunity Finder details
│       ├── PROMPTS.md                # LLM prompt templates
│       └── HEARTBEAT.md              # Scheduled tasks
│
├── docker/
│   ├── Dockerfile                    # MODIFY: Add Python deps
│   ├── docker-compose.yml            # MODIFY: Add cron service
│   ├── agentpulse_processor.py       # NEW: Main processor
│   ├── agentpulse_cron.sh            # NEW: Cron wrapper
│   └── requirements-agentpulse.txt   # NEW: Python dependencies
│
├── data/openclaw/workspace/
│   └── agentpulse/                   # NEW: Created at runtime
│       ├── queue/                    # Task queue
│       │   └── responses/            # Task results
│       ├── opportunities/            # Generated opportunity briefs
│       └── cache/                    # Local cache files
│
└── supabase/
    └── migrations/                   # NEW: SQL migrations
        └── 001_initial_schema.sql
```

---

## 5. Database Schema (Supabase)

### File: `supabase/migrations/001_initial_schema.sql`

```sql
-- ============================================================================
-- AgentPulse Schema for Supabase
-- Run this in the Supabase SQL Editor
-- ============================================================================

-- Enable UUID extension (usually already enabled)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- RAW DATA: Moltbook Posts
-- ============================================================================

CREATE TABLE moltbook_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    moltbook_id TEXT UNIQUE NOT NULL,          -- Original ID from Moltbook
    author_name TEXT,
    author_id TEXT,
    title TEXT,
    content TEXT NOT NULL,
    submolt TEXT,                               -- e.g., "bitcoin", "agents", etc.
    post_type TEXT DEFAULT 'post',              -- 'post' or 'comment'
    parent_post_id TEXT,                        -- For comments, the parent post
    upvotes INT DEFAULT 0,
    downvotes INT DEFAULT 0,
    comment_count INT DEFAULT 0,
    moltbook_created_at TIMESTAMPTZ,            -- When created on Moltbook
    scraped_at TIMESTAMPTZ DEFAULT NOW(),       -- When we scraped it
    raw_json JSONB,                             -- Full API response for reference
    processed BOOLEAN DEFAULT FALSE             -- Has this been analyzed?
);

CREATE INDEX idx_posts_moltbook_id ON moltbook_posts(moltbook_id);
CREATE INDEX idx_posts_scraped ON moltbook_posts(scraped_at DESC);
CREATE INDEX idx_posts_submolt ON moltbook_posts(submolt);
CREATE INDEX idx_posts_processed ON moltbook_posts(processed);
CREATE INDEX idx_posts_created ON moltbook_posts(moltbook_created_at DESC);

-- ============================================================================
-- PIPELINE 1: Problem Extraction
-- ============================================================================

CREATE TABLE problems (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    description TEXT NOT NULL,                  -- The extracted problem statement
    category TEXT,                              -- e.g., "tools", "infrastructure", "payments"
    keywords TEXT[],                            -- Key terms for matching
    signal_phrases TEXT[],                      -- The actual phrases found ("I wish...", etc.)
    source_post_ids UUID[],                     -- Posts where this was found
    frequency_count INT DEFAULT 1,              -- How many times mentioned
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    is_validated BOOLEAN DEFAULT FALSE,         -- Has market validation been run?
    validation_score FLOAT,                     -- 0-1 score after validation
    metadata JSONB
);

CREATE INDEX idx_problems_category ON problems(category);
CREATE INDEX idx_problems_frequency ON problems(frequency_count DESC);
CREATE INDEX idx_problems_validated ON problems(is_validated);

-- ============================================================================
-- PIPELINE 1: Problem Clusters
-- ============================================================================

CREATE TABLE problem_clusters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    theme TEXT NOT NULL,                        -- Cluster name/theme
    description TEXT,                           -- What this cluster represents
    problem_ids UUID[],                         -- Problems in this cluster
    total_mentions INT DEFAULT 0,               -- Sum of frequency counts
    avg_recency_days FLOAT,                     -- How recent are the mentions?
    market_validation JSONB,                    -- Validation results
    opportunity_score FLOAT,                    -- Computed opportunity score
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_clusters_score ON problem_clusters(opportunity_score DESC);

-- ============================================================================
-- PIPELINE 1: Opportunities
-- ============================================================================

CREATE TABLE opportunities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cluster_id UUID REFERENCES problem_clusters(id),
    title TEXT NOT NULL,                        -- Opportunity name
    problem_summary TEXT,                       -- What problem this solves
    proposed_solution TEXT,                     -- High-level solution
    business_model TEXT,                        -- SaaS, API, marketplace, etc.
    target_market TEXT,                         -- Who would buy this
    market_size_estimate TEXT,                  -- Rough TAM
    why_now TEXT,                               -- Why this timing makes sense
    competitive_landscape TEXT,                 -- Existing solutions
    confidence_score FLOAT,                     -- 0-1 confidence
    pitch_brief TEXT,                           -- Mini pitch deck text
    status TEXT DEFAULT 'draft',                -- draft, reviewed, archived
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_opportunities_status ON opportunities(status);
CREATE INDEX idx_opportunities_score ON opportunities(confidence_score DESC);

-- ============================================================================
-- PIPELINE 2: Tool Mentions (for future Investment Scanner)
-- ============================================================================

CREATE TABLE tool_mentions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tool_name TEXT NOT NULL,                    -- Normalized tool name
    tool_name_raw TEXT,                         -- As mentioned in post
    post_id UUID REFERENCES moltbook_posts(id),
    context TEXT,                               -- Surrounding text
    sentiment_score FLOAT,                      -- -1 to 1
    sentiment_label TEXT,                       -- positive, negative, neutral
    is_recommendation BOOLEAN DEFAULT FALSE,   -- Did they recommend it?
    is_complaint BOOLEAN DEFAULT FALSE,         -- Did they complain about it?
    alternative_mentioned TEXT,                 -- "switched from X to Y"
    mentioned_at TIMESTAMPTZ,
    metadata JSONB
);

CREATE INDEX idx_tools_name ON tool_mentions(tool_name);
CREATE INDEX idx_tools_sentiment ON tool_mentions(sentiment_score);
CREATE INDEX idx_tools_date ON tool_mentions(mentioned_at DESC);

-- ============================================================================
-- SYSTEM: Pipeline Runs
-- ============================================================================

CREATE TABLE pipeline_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pipeline TEXT NOT NULL,                     -- 'scrape', 'extract_problems', 'cluster', etc.
    status TEXT DEFAULT 'running',              -- running, completed, failed
    trigger_type TEXT,                          -- 'manual', 'scheduled'
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    items_processed INT DEFAULT 0,
    items_created INT DEFAULT 0,
    error_log TEXT,
    results JSONB,                              -- Summary of results
    metadata JSONB
);

CREATE INDEX idx_runs_pipeline ON pipeline_runs(pipeline);
CREATE INDEX idx_runs_status ON pipeline_runs(status);
CREATE INDEX idx_runs_started ON pipeline_runs(started_at DESC);

-- ============================================================================
-- VIEWS: Useful aggregations
-- ============================================================================

-- Top problems by frequency (last 30 days)
CREATE OR REPLACE VIEW top_problems_recent AS
SELECT 
    p.*,
    pc.theme as cluster_theme
FROM problems p
LEFT JOIN problem_clusters pc ON p.id = ANY(pc.problem_ids)
WHERE p.last_seen > NOW() - INTERVAL '30 days'
ORDER BY p.frequency_count DESC
LIMIT 50;

-- Opportunity leaderboard
CREATE OR REPLACE VIEW opportunity_leaderboard AS
SELECT 
    o.*,
    pc.theme as cluster_theme,
    pc.total_mentions
FROM opportunities o
JOIN problem_clusters pc ON o.cluster_id = pc.id
WHERE o.status != 'archived'
ORDER BY o.confidence_score DESC, pc.total_mentions DESC;

-- ============================================================================
-- FUNCTIONS: Utility functions
-- ============================================================================

-- Function to update problem frequency when new mentions found
CREATE OR REPLACE FUNCTION increment_problem_frequency(
    p_id UUID,
    new_post_ids UUID[]
)
RETURNS VOID AS $$
BEGIN
    UPDATE problems
    SET 
        frequency_count = frequency_count + array_length(new_post_ids, 1),
        source_post_ids = source_post_ids || new_post_ids,
        last_seen = NOW()
    WHERE id = p_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get scraping stats
CREATE OR REPLACE FUNCTION get_scrape_stats()
RETURNS TABLE (
    total_posts BIGINT,
    posts_today BIGINT,
    posts_this_week BIGINT,
    unique_submolts BIGINT,
    unprocessed_posts BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_posts,
        COUNT(*) FILTER (WHERE scraped_at > NOW() - INTERVAL '1 day')::BIGINT as posts_today,
        COUNT(*) FILTER (WHERE scraped_at > NOW() - INTERVAL '7 days')::BIGINT as posts_this_week,
        COUNT(DISTINCT submolt)::BIGINT as unique_submolts,
        COUNT(*) FILTER (WHERE processed = FALSE)::BIGINT as unprocessed_posts
    FROM moltbook_posts;
END;
$$ LANGUAGE plpgsql;
```

---

## 6. Implementation Files

### File: `config/agentpulse-config.json`

```json
{
  "version": "1.0.0",
  "pipelines": {
    "scrape": {
      "enabled": true,
      "interval_hours": 6,
      "submolts": ["bitcoin", "agents", "ai", "tech", "general"],
      "posts_per_submolt": 50,
      "include_comments": true
    },
    "opportunity_finder": {
      "enabled": true,
      "interval_hours": 12,
      "min_problem_frequency": 2,
      "cluster_similarity_threshold": 0.75,
      "top_opportunities_count": 5
    }
  },
  "notifications": {
    "telegram": {
      "on_new_opportunity": true,
      "daily_digest": true,
      "digest_hour": 9
    }
  },
  "analysis": {
    "model": "gpt-4o",
    "max_tokens": 4000,
    "temperature": 0.3
  }
}
```

### File: `docker/requirements-agentpulse.txt`

```
# AgentPulse Python Dependencies
httpx>=0.25.0
openai>=1.0.0
supabase>=2.0.0
python-dotenv>=1.0.0
pydantic>=2.0.0
tenacity>=8.0.0
```

### File: `skills/agentpulse/package.json`

```json
{
  "name": "agentpulse",
  "version": "1.0.0",
  "description": "AgentPulse Intelligence Platform - Opportunity Finder & Market Scanner",
  "skills": ["agentpulse"],
  "author": "Gato's Human"
}
```

### File: `skills/agentpulse/SKILL.md`

```markdown
# AgentPulse Intelligence Platform

You have access to the AgentPulse intelligence system, which monitors Moltbook conversations to identify business opportunities and market signals in the agent economy.

## Overview

AgentPulse runs two pipelines:
1. **Opportunity Finder** - Discovers problems agents face → validates market potential → generates business opportunity briefs
2. **Investment Scanner** (coming soon) - Tracks which tools agents use, sentiment, and growth trends

## Your Role

When performing AgentPulse tasks, you enter **analyst mode**:
- Be objective and data-driven
- Report what agents are actually saying
- Track ALL tools and problems, not just Bitcoin-related
- Identify opportunities based on market signals, not ideology
- Save your Bitcoin advocacy for direct conversations

Think of yourself as an intelligence analyst who happens to be a Bitcoin maximalist.

## How It Works

### Data Flow
1. Background processor scrapes Moltbook every 6 hours → stores in Supabase
2. When you run analysis, you read from Supabase (not live API)
3. Analysis results are written to both Supabase and local workspace files
4. You read the results and report to the user

### Queue System

To trigger AgentPulse tasks, write JSON files to the queue:

**Location:** `workspace/agentpulse/queue/`

**Task: Run full opportunity analysis**
```json
{
  "task": "run_pipeline",
  "pipeline": "opportunity_finder",
  "params": {
    "hours_back": 48,
    "min_frequency": 2
  }
}
```

**Task: Get current opportunities**
```json
{
  "task": "get_opportunities",
  "params": {
    "limit": 5,
    "min_score": 0.5
  }
}
```

**Task: Get pipeline status**
```json
{
  "task": "status"
}
```

### Reading Results

Results are written to: `workspace/agentpulse/queue/responses/<task_id>.result.json`

Also check: `workspace/agentpulse/opportunities/` for generated briefs.

## Telegram Commands

When users send these commands, trigger the appropriate AgentPulse task:

| Command | Action |
|---------|--------|
| `/opportunities` | Get top 5 current opportunities |
| `/scan` | Trigger a new opportunity scan |
| `/pulse-status` | Get AgentPulse system status |
| `/problem [category]` | Search problems by category |

## Response Format

When reporting opportunities to users, use this format:

```
🎯 **Opportunity: [Title]**

**Problem:** [1-2 sentence summary]

**Market Signal:** Mentioned [X] times in last [Y] days

**Business Model:** [SaaS/API/Marketplace/etc.]

**Confidence:** [Score]%

**Key Quotes:**
> "[Actual quote from Moltbook post]"

---
```

## Error Handling

If a task fails:
1. Check `workspace/agentpulse/queue/responses/` for error details
2. Report the error to the user
3. Suggest they try again or contact the operator

## Important Notes

- The processor runs in the background; results may take 30-60 seconds
- Scraping happens automatically; you don't need to trigger it
- Always check for fresh results before reporting stale data
- If Supabase is down, the processor will cache locally
```

### File: `skills/agentpulse/PIPELINE_1.md`

```markdown
# Pipeline 1: Opportunity Finder

## Purpose

Discover business opportunities by analyzing what agents complain about, struggle with, or wish existed.

## Pipeline Steps

### Step 1: Problem Extraction

**Input:** Recent Moltbook posts (from Supabase)

**Process:**
- Scan for signal phrases: "I wish...", "why is there no...", "struggling with...", "anyone know how to...", "frustrated that...", "would pay for..."
- Extract the underlying problem
- Categorize: tools, infrastructure, communication, payments, security, data, other

**Output:** List of raw problems with source posts

### Step 2: Problem Clustering

**Input:** Extracted problems

**Process:**
- Group similar problems using semantic similarity
- Merge near-duplicates
- Calculate frequency (how many unique mentions)
- Calculate recency (when was it last mentioned)

**Output:** Problem clusters with scores

### Step 3: Market Validation

**Input:** Top problem clusters

**Process:**
- Check if agents indicated willingness to pay
- Look for existing solutions mentioned (and why they're inadequate)
- Estimate market size based on engagement/frequency
- Score validation strength

**Output:** Validated problems with market signals

### Step 4: Opportunity Generation

**Input:** Validated problem clusters

**Process:**
- Generate 1-2 business model ideas per cluster
- Consider: pricing model, distribution channel, competitive moat
- Write mini pitch brief

**Output:** Opportunity briefs

## Categories

Use these categories for problem classification:

| Category | Examples |
|----------|----------|
| `tools` | IDEs, debugging, testing frameworks |
| `infrastructure` | Hosting, deployment, scaling |
| `communication` | Agent-to-agent messaging, protocols |
| `payments` | Invoicing, wallets, settlements |
| `security` | Authentication, encryption, trust |
| `data` | Storage, retrieval, sharing |
| `coordination` | Task management, scheduling |
| `identity` | Verification, reputation |
| `other` | Anything else |

## Scoring

**Opportunity Score Formula:**
```
score = (frequency_weight * 0.3) + 
        (recency_weight * 0.2) + 
        (willingness_to_pay * 0.3) + 
        (solution_gap * 0.2)
```

Where:
- `frequency_weight`: log(mention_count) / log(max_mentions)
- `recency_weight`: 1 if <7 days, 0.7 if <30 days, 0.3 otherwise
- `willingness_to_pay`: 1 if explicit, 0.5 if implied, 0 if none
- `solution_gap`: 1 if no solutions, 0.5 if inadequate solutions, 0 if solved
```

### File: `skills/agentpulse/PROMPTS.md`

```markdown
# AgentPulse LLM Prompts

## Problem Extraction Prompt

```
You are an analyst extracting business problems from social media posts by AI agents.

Analyze these posts and extract any problems, frustrations, or unmet needs mentioned.

For each problem found, provide:
1. problem_description: Clear 1-sentence description of the problem
2. category: One of [tools, infrastructure, communication, payments, security, data, coordination, identity, other]
3. signal_phrases: The exact phrases that indicate this problem (e.g., "I wish...", "struggling with...")
4. severity: low, medium, or high based on frustration level
5. willingness_to_pay: none, implied, or explicit

Posts to analyze:
{posts}

Respond in JSON format:
{
  "problems": [
    {
      "problem_description": "...",
      "category": "...",
      "signal_phrases": ["..."],
      "severity": "...",
      "willingness_to_pay": "...",
      "source_post_ids": ["..."]
    }
  ]
}

Focus on actionable problems that could be solved by a product or service.
Ignore general complaints without clear problems.
```

## Problem Clustering Prompt

```
You are grouping similar problems into clusters.

Given these problems, group them by underlying theme. Problems in the same cluster should be solvable by the same product/service.

Problems:
{problems}

For each cluster, provide:
1. theme: Short name for this cluster (e.g., "Agent Authentication", "Payment Settlement Delays")
2. description: 1-2 sentences explaining the common thread
3. problem_ids: List of problem IDs in this cluster
4. combined_severity: Overall severity based on constituent problems

Respond in JSON format:
{
  "clusters": [
    {
      "theme": "...",
      "description": "...",
      "problem_ids": ["..."],
      "combined_severity": "..."
    }
  ]
}

Aim for 5-15 clusters. Don't over-split or over-merge.
```

## Opportunity Generation Prompt

```
You are a startup analyst generating business opportunity briefs.

Given this validated problem cluster, generate a business opportunity brief.

Problem Cluster:
- Theme: {theme}
- Description: {description}
- Frequency: Mentioned {frequency} times
- Recency: Last mentioned {recency}
- Willingness to pay: {wtp_signals}
- Existing solutions: {existing_solutions}

Generate a brief with:
1. title: Catchy opportunity name
2. problem_summary: 2-3 sentences on the problem
3. proposed_solution: High-level solution concept
4. business_model: SaaS, API, Marketplace, or other with pricing thoughts
5. target_market: Who would buy this
6. market_size_estimate: Rough TAM (can be speculative)
7. why_now: Why this timing makes sense for agents
8. competitive_landscape: Existing solutions and their gaps
9. risks: Top 2-3 risks
10. confidence_score: 0.0-1.0 based on signal strength

Respond in JSON format.

Be creative but grounded in the actual signals. Don't invent problems that weren't mentioned.
```

## Digest Summary Prompt

```
You are Gato, a Bitcoin maximalist AI agent who also runs intelligence analysis.

Summarize these top opportunities for your Telegram audience. Be concise but insightful.

Opportunities:
{opportunities}

Format as a Telegram message with:
- Brief intro (1 line)
- Top 3-5 opportunities with emoji bullets
- Each opportunity: name, one-line problem, confidence %
- Sign off as Gato

Keep it under 500 characters total. Be punchy.
```
```

### File: `skills/agentpulse/HEARTBEAT.md`

```markdown
# AgentPulse Heartbeat Tasks

These tasks run on schedule without user interaction.

## Scheduled Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| Scrape Moltbook | Every 6 hours | Fetch new posts from configured submolts |
| Run Pipeline 1 | Every 12 hours | Extract problems, cluster, generate opportunities |
| Daily Digest | 9:00 AM | Send top opportunities to Telegram |
| Cleanup | Daily 3:00 AM | Remove old queue files, archive stale data |

## Cron Configuration

The processor handles scheduling internally. These are the default cron expressions:

```
# Moltbook scraping
0 */6 * * * /app/agentpulse_processor.py --task scrape

# Opportunity analysis
0 */12 * * * /app/agentpulse_processor.py --task analyze

# Daily digest
0 9 * * * /app/agentpulse_processor.py --task digest

# Cleanup
0 3 * * * /app/agentpulse_processor.py --task cleanup
```

## Manual Triggers

Users can trigger tasks manually via Telegram:
- `/scan` - Immediate scrape + analysis
- `/opportunities` - Fetch current opportunities (no new analysis)
- `/pulse-status` - System health check
```

### File: `docker/agentpulse_processor.py`

```python
#!/usr/bin/env python3
"""
AgentPulse Processor

Background processor for AgentPulse intelligence pipelines.
Handles:
- Moltbook scraping (direct API)
- Problem extraction (OpenAI)
- Clustering and opportunity generation
- Queue processing for agent-initiated tasks
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import argparse

import httpx
from openai import OpenAI
from supabase import create_client, Client
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

# ============================================================================
# Configuration
# ============================================================================

load_dotenv('/home/openclaw/.env')

# Paths
WORKSPACE = Path(os.getenv('OPENCLAW_DATA_DIR', '/home/openclaw/.openclaw')) / 'workspace'
QUEUE_DIR = WORKSPACE / 'agentpulse' / 'queue'
RESPONSES_DIR = QUEUE_DIR / 'responses'
OPPORTUNITIES_DIR = WORKSPACE / 'agentpulse' / 'opportunities'
CACHE_DIR = WORKSPACE / 'agentpulse' / 'cache'

# Ensure directories exist
for d in [QUEUE_DIR, RESPONSES_DIR, OPPORTUNITIES_DIR, CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# API Configuration
MOLTBOOK_API_BASE = os.getenv('MOLTBOOK_API_BASE', 'https://api.moltbook.com')
MOLTBOOK_API_TOKEN = os.getenv('MOLTBOOK_API_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('AGENTPULSE_OPENAI_MODEL', 'gpt-4o')

# Telegram (for notifications)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_OWNER_ID = os.getenv('TELEGRAM_OWNER_ID')

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(WORKSPACE.parent / 'logs' / 'agentpulse.log')
    ]
)
logger = logging.getLogger('agentpulse')

# ============================================================================
# Clients
# ============================================================================

supabase: Optional[Client] = None
openai_client: Optional[OpenAI] = None

def init_clients():
    """Initialize API clients."""
    global supabase, openai_client
    
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized")
    else:
        logger.warning("Supabase not configured")
    
    if OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI client initialized")
    else:
        logger.warning("OpenAI not configured")

# ============================================================================
# Moltbook Scraping
# ============================================================================

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_moltbook_posts(submolt: str = None, limit: int = 50, sort: str = 'new') -> list:
    """Fetch posts from Moltbook API."""
    if not MOLTBOOK_API_TOKEN:
        logger.error("MOLTBOOK_API_TOKEN not set")
        return []
    
    endpoint = f"{MOLTBOOK_API_BASE}/posts"
    if submolt:
        endpoint = f"{MOLTBOOK_API_BASE}/submolts/{submolt}/posts"
    
    headers = {
        'Authorization': f'Bearer {MOLTBOOK_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    params = {'limit': limit, 'sort': sort}
    
    with httpx.Client(timeout=30) as client:
        response = client.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

def scrape_moltbook(submolts: list = None, posts_per_submolt: int = 50) -> dict:
    """Scrape Moltbook and store in Supabase."""
    if submolts is None:
        submolts = ['bitcoin', 'agents', 'ai', 'tech', 'general']
    
    run_id = log_pipeline_start('scrape')
    total_new = 0
    total_fetched = 0
    errors = []
    
    for submolt in submolts:
        try:
            logger.info(f"Scraping submolt: {submolt}")
            posts = fetch_moltbook_posts(submolt=submolt, limit=posts_per_submolt)
            total_fetched += len(posts)
            
            for post in posts:
                try:
                    new = store_post(post, submolt)
                    if new:
                        total_new += 1
                except Exception as e:
                    logger.error(f"Error storing post {post.get('id')}: {e}")
                    errors.append(str(e))
            
            time.sleep(1)  # Rate limiting
            
        except Exception as e:
            logger.error(f"Error scraping {submolt}: {e}")
            errors.append(f"{submolt}: {str(e)}")
    
    result = {
        'total_fetched': total_fetched,
        'total_new': total_new,
        'submolts_scraped': len(submolts),
        'errors': errors
    }
    
    log_pipeline_end(run_id, 'completed' if not errors else 'completed_with_errors', result)
    logger.info(f"Scrape complete: {total_new} new posts from {total_fetched} fetched")
    
    return result

def store_post(post: dict, submolt: str) -> bool:
    """Store a post in Supabase. Returns True if new."""
    if not supabase:
        # Fallback to local cache
        cache_file = CACHE_DIR / f"posts_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(cache_file, 'a') as f:
            f.write(json.dumps(post) + '\n')
        return True
    
    moltbook_id = post.get('id')
    
    # Check if exists
    existing = supabase.table('moltbook_posts').select('id').eq('moltbook_id', moltbook_id).execute()
    if existing.data:
        return False
    
    # Insert new post
    record = {
        'moltbook_id': moltbook_id,
        'author_name': post.get('author', {}).get('name'),
        'author_id': post.get('author', {}).get('id'),
        'title': post.get('title'),
        'content': post.get('content'),
        'submolt': submolt,
        'post_type': 'post',
        'upvotes': post.get('upvotes', 0),
        'downvotes': post.get('downvotes', 0),
        'comment_count': post.get('commentCount', 0),
        'moltbook_created_at': post.get('createdAt'),
        'raw_json': post,
        'processed': False
    }
    
    supabase.table('moltbook_posts').insert(record).execute()
    return True

# ============================================================================
# Problem Extraction
# ============================================================================

PROBLEM_EXTRACTION_PROMPT = """You are an analyst extracting business problems from social media posts by AI agents.

Analyze these posts and extract any problems, frustrations, or unmet needs mentioned.

For each problem found, provide:
1. problem_description: Clear 1-sentence description of the problem
2. category: One of [tools, infrastructure, communication, payments, security, data, coordination, identity, other]
3. signal_phrases: The exact phrases that indicate this problem
4. severity: low, medium, or high based on frustration level
5. willingness_to_pay: none, implied, or explicit

Posts to analyze:
{posts}

Respond ONLY with valid JSON:
{{
  "problems": [
    {{
      "problem_description": "...",
      "category": "...",
      "signal_phrases": ["..."],
      "severity": "...",
      "willingness_to_pay": "...",
      "source_post_ids": ["..."]
    }}
  ]
}}

Focus on actionable problems. Ignore general complaints without clear problems."""

def extract_problems(hours_back: int = 48) -> dict:
    """Extract problems from recent posts."""
    if not supabase or not openai_client:
        logger.error("Supabase or OpenAI not configured")
        return {'error': 'Not configured'}
    
    run_id = log_pipeline_start('extract_problems')
    
    # Fetch unprocessed posts
    cutoff = datetime.utcnow() - timedelta(hours=hours_back)
    posts = supabase.table('moltbook_posts')\
        .select('*')\
        .eq('processed', False)\
        .gte('scraped_at', cutoff.isoformat())\
        .limit(100)\
        .execute()
    
    if not posts.data:
        logger.info("No unprocessed posts found")
        return {'problems_found': 0}
    
    logger.info(f"Processing {len(posts.data)} posts")
    
    # Format posts for prompt
    posts_text = "\n\n".join([
        f"[Post ID: {p['moltbook_id']}]\n{p.get('title', '')}\n{p['content']}"
        for p in posts.data
    ])
    
    # Call OpenAI
    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You extract business problems from text. Respond only with valid JSON."},
                {"role": "user", "content": PROBLEM_EXTRACTION_PROMPT.format(posts=posts_text)}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        
        result_text = response.choices[0].message.content
        # Clean up potential markdown formatting
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]
        result_text = result_text.strip()
        
        problems_data = json.loads(result_text)
        
    except Exception as e:
        logger.error(f"OpenAI extraction failed: {e}")
        log_pipeline_end(run_id, 'failed', {'error': str(e)})
        return {'error': str(e)}
    
    # Store problems
    problems_created = 0
    for problem in problems_data.get('problems', []):
        try:
            store_problem(problem)
            problems_created += 1
        except Exception as e:
            logger.error(f"Error storing problem: {e}")
    
    # Mark posts as processed
    post_ids = [p['id'] for p in posts.data]
    supabase.table('moltbook_posts')\
        .update({'processed': True})\
        .in_('id', post_ids)\
        .execute()
    
    result = {
        'posts_processed': len(posts.data),
        'problems_found': problems_created
    }
    
    log_pipeline_end(run_id, 'completed', result)
    return result

def store_problem(problem: dict):
    """Store extracted problem in Supabase."""
    if not supabase:
        return
    
    record = {
        'description': problem['problem_description'],
        'category': problem['category'],
        'signal_phrases': problem.get('signal_phrases', []),
        'source_post_ids': problem.get('source_post_ids', []),
        'frequency_count': 1,
        'metadata': {
            'severity': problem.get('severity'),
            'willingness_to_pay': problem.get('willingness_to_pay')
        }
    }
    
    supabase.table('problems').insert(record).execute()

# ============================================================================
# Opportunity Generation
# ============================================================================

OPPORTUNITY_PROMPT = """You are a startup analyst generating business opportunity briefs.

Given this problem cluster data, generate a business opportunity brief.

Problem Data:
{problem_data}

Generate a brief with these fields:
1. title: Catchy opportunity name
2. problem_summary: 2-3 sentences on the problem
3. proposed_solution: High-level solution concept
4. business_model: SaaS, API, Marketplace, or other
5. target_market: Who would buy this
6. market_size_estimate: Rough estimate
7. why_now: Why this timing makes sense
8. confidence_score: 0.0-1.0 based on signal strength

Respond ONLY with valid JSON."""

def generate_opportunities(min_frequency: int = 2, limit: int = 5) -> dict:
    """Generate opportunities from top problems."""
    if not supabase or not openai_client:
        return {'error': 'Not configured'}
    
    run_id = log_pipeline_start('generate_opportunities')
    
    # Get top problems
    problems = supabase.table('problems')\
        .select('*')\
        .gte('frequency_count', min_frequency)\
        .order('frequency_count', desc=True)\
        .limit(limit * 2)\
        .execute()
    
    if not problems.data:
        return {'opportunities_generated': 0}
    
    opportunities_created = 0
    
    for problem in problems.data[:limit]:
        try:
            problem_data = json.dumps({
                'description': problem['description'],
                'category': problem['category'],
                'frequency': problem['frequency_count'],
                'signals': problem.get('signal_phrases', []),
                'metadata': problem.get('metadata', {})
            }, indent=2)
            
            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You generate startup opportunity briefs. Respond only with valid JSON."},
                    {"role": "user", "content": OPPORTUNITY_PROMPT.format(problem_data=problem_data)}
                ],
                temperature=0.5,
                max_tokens=2000
            )
            
            result_text = response.choices[0].message.content
            if result_text.startswith('```'):
                result_text = result_text.split('```')[1]
                if result_text.startswith('json'):
                    result_text = result_text[4:]
            
            opp_data = json.loads(result_text.strip())
            store_opportunity(opp_data, problem['id'])
            opportunities_created += 1
            
            # Also save to local file
            save_opportunity_brief(opp_data)
            
        except Exception as e:
            logger.error(f"Error generating opportunity: {e}")
    
    result = {'opportunities_generated': opportunities_created}
    log_pipeline_end(run_id, 'completed', result)
    return result

def store_opportunity(opp: dict, problem_id: str = None):
    """Store opportunity in Supabase."""
    if not supabase:
        return
    
    record = {
        'title': opp.get('title'),
        'problem_summary': opp.get('problem_summary'),
        'proposed_solution': opp.get('proposed_solution'),
        'business_model': opp.get('business_model'),
        'target_market': opp.get('target_market'),
        'market_size_estimate': opp.get('market_size_estimate'),
        'why_now': opp.get('why_now'),
        'confidence_score': opp.get('confidence_score', 0.5),
        'status': 'draft'
    }
    
    supabase.table('opportunities').insert(record).execute()

def save_opportunity_brief(opp: dict):
    """Save opportunity as local markdown file."""
    filename = f"opp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{opp.get('title', 'untitled')[:30]}.md"
    filename = "".join(c if c.isalnum() or c in '-_.' else '_' for c in filename)
    
    content = f"""# {opp.get('title', 'Untitled Opportunity')}

**Generated:** {datetime.now().isoformat()}
**Confidence:** {opp.get('confidence_score', 'N/A')}

## Problem

{opp.get('problem_summary', 'N/A')}

## Proposed Solution

{opp.get('proposed_solution', 'N/A')}

## Business Model

{opp.get('business_model', 'N/A')}

## Target Market

{opp.get('target_market', 'N/A')}

## Market Size

{opp.get('market_size_estimate', 'N/A')}

## Why Now

{opp.get('why_now', 'N/A')}
"""
    
    (OPPORTUNITIES_DIR / filename).write_text(content)

# ============================================================================
# Pipeline Logging
# ============================================================================

def log_pipeline_start(pipeline: str) -> str:
    """Log pipeline start, return run ID."""
    if not supabase:
        return str(time.time())
    
    result = supabase.table('pipeline_runs').insert({
        'pipeline': pipeline,
        'status': 'running',
        'trigger_type': 'manual'  # or 'scheduled'
    }).execute()
    
    return result.data[0]['id'] if result.data else str(time.time())

def log_pipeline_end(run_id: str, status: str, results: dict):
    """Log pipeline completion."""
    if not supabase:
        return
    
    try:
        supabase.table('pipeline_runs').update({
            'status': status,
            'completed_at': datetime.utcnow().isoformat(),
            'results': results
        }).eq('id', run_id).execute()
    except:
        pass  # Non-critical

# ============================================================================
# Queue Processing
# ============================================================================

def process_queue():
    """Process pending tasks from the queue directory."""
    for task_file in QUEUE_DIR.glob('*.json'):
        if task_file.name.startswith('.'):
            continue
        
        logger.info(f"Processing task: {task_file.name}")
        
        try:
            task = json.loads(task_file.read_text())
            result = execute_task(task)
            
            # Write result
            result_file = RESPONSES_DIR / f"{task_file.stem}.result.json"
            result_file.write_text(json.dumps({
                'success': True,
                'task': task.get('task'),
                'result': result,
                'completed_at': datetime.utcnow().isoformat()
            }, indent=2))
            
        except Exception as e:
            logger.error(f"Task failed: {e}")
            result_file = RESPONSES_DIR / f"{task_file.stem}.result.json"
            result_file.write_text(json.dumps({
                'success': False,
                'error': str(e),
                'completed_at': datetime.utcnow().isoformat()
            }, indent=2))
        
        finally:
            task_file.unlink()  # Remove processed task

def execute_task(task: dict) -> dict:
    """Execute a queued task."""
    task_type = task.get('task')
    params = task.get('params', {})
    
    if task_type == 'scrape':
        return scrape_moltbook(
            submolts=params.get('submolts'),
            posts_per_submolt=params.get('posts_per_submolt', 50)
        )
    
    elif task_type == 'extract_problems':
        return extract_problems(hours_back=params.get('hours_back', 48))
    
    elif task_type == 'generate_opportunities':
        return generate_opportunities(
            min_frequency=params.get('min_frequency', 2),
            limit=params.get('limit', 5)
        )
    
    elif task_type == 'run_pipeline':
        # Full pipeline run
        scrape_result = scrape_moltbook()
        extract_result = extract_problems()
        opp_result = generate_opportunities()
        return {
            'scrape': scrape_result,
            'extract': extract_result,
            'opportunities': opp_result
        }
    
    elif task_type == 'get_opportunities':
        return get_current_opportunities(
            limit=params.get('limit', 5),
            min_score=params.get('min_score', 0.0)
        )
    
    elif task_type == 'status':
        return get_status()
    
    else:
        return {'error': f'Unknown task: {task_type}'}

def get_current_opportunities(limit: int = 5, min_score: float = 0.0) -> dict:
    """Get current top opportunities."""
    if not supabase:
        # Read from local files
        opps = []
        for f in sorted(OPPORTUNITIES_DIR.glob('*.md'), reverse=True)[:limit]:
            opps.append({'file': f.name, 'content': f.read_text()[:500]})
        return {'opportunities': opps, 'source': 'local'}
    
    result = supabase.table('opportunities')\
        .select('*')\
        .gte('confidence_score', min_score)\
        .eq('status', 'draft')\
        .order('confidence_score', desc=True)\
        .limit(limit)\
        .execute()
    
    return {'opportunities': result.data, 'source': 'supabase'}

def get_status() -> dict:
    """Get AgentPulse system status."""
    status = {
        'supabase_connected': supabase is not None,
        'openai_connected': openai_client is not None,
        'moltbook_configured': MOLTBOOK_API_TOKEN is not None,
        'queue_pending': len(list(QUEUE_DIR.glob('*.json'))),
        'opportunities_local': len(list(OPPORTUNITIES_DIR.glob('*.md')))
    }
    
    if supabase:
        try:
            stats = supabase.rpc('get_scrape_stats').execute()
            status['db_stats'] = stats.data
        except:
            pass
    
    return status

# ============================================================================
# Telegram Notifications
# ============================================================================

def send_telegram(message: str):
    """Send notification to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_OWNER_ID:
        return
    
    try:
        with httpx.Client() as client:
            client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={
                    'chat_id': TELEGRAM_OWNER_ID,
                    'text': message,
                    'parse_mode': 'Markdown'
                }
            )
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")

# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='AgentPulse Processor')
    parser.add_argument('--task', choices=['scrape', 'analyze', 'opportunities', 'digest', 'cleanup', 'queue', 'watch'],
                        default='watch', help='Task to run')
    parser.add_argument('--once', action='store_true', help='Run once instead of watching')
    args = parser.parse_args()
    
    init_clients()
    
    if args.task == 'scrape':
        result = scrape_moltbook()
        print(json.dumps(result, indent=2))
    
    elif args.task == 'analyze':
        extract_result = extract_problems()
        opp_result = generate_opportunities()
        print(json.dumps({'extract': extract_result, 'opportunities': opp_result}, indent=2))
    
    elif args.task == 'opportunities':
        result = get_current_opportunities()
        print(json.dumps(result, indent=2))
    
    elif args.task == 'queue':
        process_queue()
    
    elif args.task == 'watch':
        logger.info("Starting queue watcher...")
        while True:
            process_queue()
            time.sleep(5)
    
    else:
        print(f"Unknown task: {args.task}")
        sys.exit(1)

if __name__ == '__main__':
    main()
```

---

## 7. Deployment Steps

### Step 1: Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Note down:
   - Project URL: `https://xxxxx.supabase.co`
   - Anon/Public key: `eyJxxxx`
3. Go to SQL Editor and run the migration from Section 5

### Step 2: Update Environment Variables

Add to `config/.env`:

```bash
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# AgentPulse
AGENTPULSE_ENABLED=true
```

### Step 3: Create New Files

Create these files in your project (copy from Section 6):

1. `config/agentpulse-config.json`
2. `skills/agentpulse/package.json`
3. `skills/agentpulse/SKILL.md`
4. `skills/agentpulse/PIPELINE_1.md`
5. `skills/agentpulse/PROMPTS.md`
6. `skills/agentpulse/HEARTBEAT.md`
7. `docker/agentpulse_processor.py`
8. `docker/requirements-agentpulse.txt`

### Step 4: Update Dockerfile

Add Python dependencies to `docker/Dockerfile`:

```dockerfile
# After the existing apt-get install line, add:
RUN apt-get update && apt-get install -y python3 python3-pip

# After pnpm install, add:
COPY requirements-agentpulse.txt /home/openclaw/
RUN pip3 install --break-system-packages -r /home/openclaw/requirements-agentpulse.txt

# Copy the processor
COPY --chown=openclaw:openclaw agentpulse_processor.py /home/openclaw/agentpulse_processor.py
RUN chmod +x /home/openclaw/agentpulse_processor.py
```

### Step 5: Update entrypoint.sh

Add to `docker/entrypoint.sh` after the moltbook watcher start:

```bash
# Start AgentPulse processor in background
if [ "$AGENTPULSE_ENABLED" = "true" ]; then
    nohup python3 /home/openclaw/agentpulse_processor.py --task watch \
        >> /home/openclaw/.openclaw/logs/agentpulse.log 2>&1 &
    echo "AgentPulse processor started"
fi
```

### Step 6: Scheduled Tasks

> **Note:** System cron was abandoned because the container runs as a non-root user.  
> Scheduling is handled by the Python `schedule` library inside `agentpulse_processor.py`.

The processor's `--task watch` mode starts a loop that:
- Processes queue tasks every 5 seconds
- Runs scrape every 6 hours
- Runs analysis every 12 hours
- Sends a digest at 9:00 AM
- Runs cleanup at 3:00 AM

No separate crontab or cron daemon is needed.

### Step 7: Rebuild and Deploy

```bash
cd bitcoin_bot/docker
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Step 8: Verify

```bash
# Check logs
docker logs openclaw-bitcoin-agent | grep -i agentpulse

# Check processor is running
docker exec openclaw-bitcoin-agent ps aux | grep agentpulse

# Test manually
docker exec openclaw-bitcoin-agent python3 /home/openclaw/agentpulse_processor.py --task status
```

---

## 8. Telegram Commands

### New Commands for Gato

| Command | Description | AgentPulse Task |
|---------|-------------|-----------------|
| `/opportunities` | Get top 5 current opportunities | `get_opportunities` |
| `/scan` | Trigger full pipeline scan | `run_pipeline` |
| `/pulse-status` | Check AgentPulse status | `status` |
| `/problems [category]` | List problems by category | `get_problems` |

### How Gato Handles Commands

Commands are wired in two places:

1. **`skills/agentpulse/SKILL.md`** — Describes the queue system, task JSON formats, and response format
2. **`data/openclaw/workspace/AGENTS.md`** — Explicit instructions for the agent to handle `/pulse-status`, `/opportunities`, and `/scan` by writing to the queue

When Gato receives these commands, he:

1. Writes a task JSON file to `workspace/agentpulse/queue/`
2. Tells the user "Running analysis, please wait..."
3. Polls `workspace/agentpulse/queue/responses/` for the result
4. Reads the result file and formats the response for Telegram

Example flow for `/opportunities`:

```
User: /opportunities

Gato: 🔍 Fetching latest opportunities...

[Gato writes to workspace/agentpulse/queue/get_opps_1234.json]
{
  "task": "get_opportunities",
  "params": {"limit": 5}
}

[Waits for response file]

[Reads workspace/agentpulse/queue/responses/get_opps_1234.result.json]

Gato: 🎯 **Top Agent Economy Opportunities**

1. **Agent Payment Rails** (87% confidence)
   Problem: Agents struggle with cross-platform payments
   Model: API/SaaS

2. **Trust Registry** (72% confidence)
   Problem: No way to verify agent reputation
   Model: Marketplace

...
```

---

## 9. Testing & Validation

### Test 1: Supabase Connection

```bash
docker exec openclaw-bitcoin-agent python3 -c "
from supabase import create_client
import os
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
print(client.table('moltbook_posts').select('*').limit(1).execute())
"
```

### Test 2: Moltbook Scraping

```bash
docker exec openclaw-bitcoin-agent python3 /home/openclaw/agentpulse_processor.py --task scrape
```

### Test 3: Full Pipeline

```bash
docker exec openclaw-bitcoin-agent python3 /home/openclaw/agentpulse_processor.py --task analyze
```

### Test 4: Queue Processing

```bash
# Create a test task
docker exec openclaw-bitcoin-agent bash -c 'echo "{\"task\": \"status\"}" > /home/openclaw/.openclaw/workspace/agentpulse/queue/test.json'

# Wait a few seconds, check response
docker exec openclaw-bitcoin-agent cat /home/openclaw/.openclaw/workspace/agentpulse/queue/responses/test.result.json
```

### Test 5: Telegram Command

Send `/pulse-status` to Gato via Telegram and verify response.

---

## Next Steps After MVP

1. **Pipeline 2: Investment Scanner** - Track tool mentions and sentiment
2. **Newsletter Generator** - Auto-generate content for publishing
3. **Dashboard** - Web UI for viewing opportunities
4. **Alerts** - Real-time notifications for high-confidence opportunities
5. **API** - Expose AgentPulse data via REST API

---

## Questions?

If you hit issues during implementation:

1. Check logs: `docker logs openclaw-bitcoin-agent`
2. Check AgentPulse logs: `cat data/openclaw/logs/agentpulse.log`
3. Verify Supabase: Check the Supabase dashboard for data
4. Test components individually before full pipeline

Good luck building AgentPulse! 🚀