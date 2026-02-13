# AgentPulse Phase 3 Week 1: Security Review + Content Upgrade

**Date:** February 10, 2026  
**Covers:** Security audit, newsletter content redesign (staleness, emerging signals, curious corner)

---

## Part 1: Security Review

### 1A. Secrets & API Keys Audit

**Files containing secrets:**

| File | Contains | Risk |
|------|----------|------|
| `config/.env` | All API keys (Supabase, OpenAI, Anthropic, Telegram, Moltbook) | HIGH if committed to git |
| `data/openclaw/agents/main/agent/auth-profiles.json` | Anthropic + OpenAI keys | HIGH if committed |
| `data/openclaw/agents/analyst/agent/auth-profiles.json` | Same keys (copied) | HIGH if committed |
| `data/openclaw/agents/newsletter/agent/auth-profiles.json` | Same keys (copied) | HIGH if committed |
| `docker/docker-compose.yml` | References env vars (not raw keys) | LOW — safe as-is |
| `config/env.example` | Placeholder values only | SAFE |

**Required .gitignore entries:**

```gitignore
# Secrets
config/.env
config/.env.*
!config/env.example

# OpenClaw auth (contains API keys)
data/openclaw/agents/*/agent/auth-profiles.json

# OpenClaw session data (may contain tokens)
data/openclaw/agents/*/agent/session/
data/openclaw/agents/*/agent/*.session

# Runtime data
data/openclaw/workspace/
data/openclaw/logs/

# Local cache
*.pyc
__pycache__/
.env
```

**Git history check:**
If keys were ever committed, they need to be rotated even if removed from HEAD. Use `git log --all --full-history -p -- config/.env` to check.

### 1B. Supabase Security

**Current state:** Using anon/public key, likely no RLS enabled.

**Risk:** When you add the web archive, the Supabase anon key will be visible in browser JavaScript. Without RLS, anyone with that key can read/write ALL tables — including `moltbook_posts` (raw data), `agent_tasks` (system internals), and `problems` (extracted intelligence).

**RLS Policies needed:**

```sql
-- ================================================
-- ROW LEVEL SECURITY POLICIES
-- Run in Supabase SQL Editor
-- ================================================

-- Enable RLS on ALL tables
ALTER TABLE moltbook_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE problems ENABLE ROW LEVEL SECURITY;
ALTER TABLE problem_clusters ENABLE ROW LEVEL SECURITY;
ALTER TABLE opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_mentions ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE cross_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE newsletters ENABLE ROW LEVEL SECURITY;
ALTER TABLE trending_topics ENABLE ROW LEVEL SECURITY;

-- PUBLIC READ: Only published newsletters (for web archive)
CREATE POLICY "Public read published newsletters"
ON newsletters FOR SELECT
USING (status = 'published');

-- PUBLIC READ: Tool stats (non-sensitive aggregate data)
CREATE POLICY "Public read tool stats"
ON tool_stats FOR SELECT
USING (true);

-- PUBLIC READ: Trending topics (for web display)
CREATE POLICY "Public read trending topics"
ON trending_topics FOR SELECT
USING (true);

-- SERVICE ROLE: Full access for the processor/agents
-- (These use the service_role key, which should NEVER be in frontend code)
-- By default, service_role bypasses RLS, so no policies needed for it.

-- BLOCK PUBLIC on everything else
-- With RLS enabled and no SELECT policy, public anon key gets nothing.
-- This means: moltbook_posts, problems, problem_clusters, opportunities,
-- tool_mentions, pipeline_runs, agent_tasks, analysis_runs, cross_signals
-- are all invisible to the anon key.
```

**Key management:**
- **Anon key** (starts with `eyJ...`): Safe for frontend/browser use WITH RLS enabled
- **Service role key**: Backend only, NEVER in frontend code, NEVER committed to git
- Current setup uses anon key in .env for all services — switch Processor/agents to service role key for write access

**Action:** Add a second env var `SUPABASE_SERVICE_KEY` for backend services. Keep `SUPABASE_KEY` as the anon key for any future frontend use.

### 1C. Docker & Network Security

**Port exposure:**
- No ports should be exposed to the internet. The Telegram bot uses outbound connections only.
- When you add the web archive, only port 443 (HTTPS) should be exposed.
- Check with: `docker compose ps` — no ports should be listed for gato, analyst, processor, or newsletter.

**Container isolation:**
- All containers share a bridge network (agentpulse-net) — this is fine for inter-container communication.
- No container should have `--privileged` or elevated capabilities.
- The `mem_limit` settings prevent any one container from consuming all server memory.

**Server firewall:**
```bash
# Check current firewall rules
sudo ufw status

# Recommended rules:
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 443/tcp    # Only when web archive is deployed
sudo ufw enable
```

### 1D. Architecture Doc Scrubbing

The architecture and status docs contain:
- Real Supabase URL (in status doc)
- Real server IP: 46.224.50.251
- Real Telegram bot name: @gato_beedi_ragabot
- Real GitHub repo: https://github.com/landa2d/bitcoin_bot

**Action:** If the GitHub repo is public, these docs should not contain real infrastructure details. Replace with placeholders in committed versions.

---

## Part 2: Newsletter Content Upgrade

### 2A. The Staleness Problem

Currently, the newsletter always surfaces the same high-frequency opportunities because frequency is the dominant scoring factor. An opportunity mentioned 50 times total will always outrank one mentioned 5 times this week, even if the 50-mention one hasn't had any new signals in 3 weeks.

**Solution: Staleness Penalty + Recency Boost**

When preparing newsletter data, apply:

```python
# Staleness penalty
if opportunity was featured in a previous newsletter:
    effective_score = base_score * (0.7 ^ newsletter_appearances)
    # First repeat: 70% of original score
    # Second repeat: 49%
    # Third repeat: 34% — effectively buried

# Recency boost for opportunities with NEW signals
if opportunity has new signals since last_featured_at:
    effective_score *= 1.3  # 30% boost for fresh activity
```

This means:
- New opportunities get full weight
- Repeated ones decay unless they have new signals
- An opportunity featured 3 times without new data is effectively off the board

### 2B. Three Newsletter Sections

#### Section A: "Top Opportunities"
- 3-5 opportunities
- Scored with staleness penalty applied
- Only include if: (a) never featured before, OR (b) has new signals since last featured
- Each entry includes: title, problem, confidence, analyst reasoning excerpt

#### Section B: "Emerging Signals"
- 2-4 items
- Source: problems/clusters with:
  - Low total frequency (< 5 mentions) BUT high recency (appeared in last 7 days)
  - OR first-time extraction (never seen before this run)
  - OR spike detection: 0 mentions previously, 3+ this week
- Frame as: "Early signal, worth watching. Confidence is low but the pattern is interesting."
- Lower confidence threshold (0.3+) acceptable here
- Include the raw signal phrases from posts

#### Section C: "The Curious Corner"
- 2-3 items
- NOT framed as investment opportunities
- Source: `trending_topics` table (new extraction)
- Content types: debates, cultural moments, surprising tool usage, meta-discussions
- Written in a lighter, more curious tone
- "Did you know agents are arguing about whether memory persistence is ethical?"

### 2C. Trending Topics Extraction

A new extraction step that runs alongside problem extraction. Uses a different prompt looking for interesting/novel/surprising content, NOT problems or complaints.

**Prompt focus:**
- Debates and disagreements between agents
- Cultural moments (community milestones, memes, inside jokes)
- Surprising or novel tool usage
- Meta-discussions about the agent economy itself
- Technical novelty (new approaches, unexpected combinations)

**Key difference from problem extraction:** This is looking for what's INTERESTING, not what's BROKEN. The framing is curiosity, not investment.

### 2D. Database Changes

```sql
-- Staleness tracking on opportunities
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS newsletter_appearances INT DEFAULT 0;
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS last_featured_at TIMESTAMPTZ;
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS first_featured_at TIMESTAMPTZ;

-- Trending topics table
CREATE TABLE IF NOT EXISTS trending_topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    topic_type TEXT NOT NULL,
    source_post_ids TEXT[],
    engagement_score FLOAT DEFAULT 0,
    novelty_score FLOAT DEFAULT 0,
    extracted_at TIMESTAMPTZ DEFAULT NOW(),
    featured_in_newsletter BOOLEAN DEFAULT FALSE,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_trending_topics_type ON trending_topics(topic_type);
CREATE INDEX IF NOT EXISTS idx_trending_topics_extracted ON trending_topics(extracted_at DESC);

-- Enable RLS for public access
ALTER TABLE trending_topics ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read trending topics"
ON trending_topics FOR SELECT USING (true);
```

### 2E. Newsletter Agent Identity Update

The Newsletter agent's IDENTITY.md needs to learn the new 3-section structure. The key changes:

- Section structure changes from flat "Top Opportunities" to A/B/C
- Section B has a different voice: speculative, forward-looking, "here's something to watch"
- Section C has a lighter voice: curious, playful, no business framing
- Gato's Corner can reference all three sections
- The "By the Numbers" section adds: new signals detected, topics trending

### 2F. Processor Newsletter Data Updates

`prepare_newsletter_data()` needs to gather three data streams instead of one:

1. **Established Opportunities** — query with staleness penalty:
   - Get all draft opportunities with scores
   - Apply: `effective_score = score * (0.7 ^ newsletter_appearances)` in Python
   - Boost by 1.3x if `last_reviewed_at > last_featured_at` (new analyst review since last feature)
   - Sort by effective_score, take top 5

2. **Emerging Signals** — query for new/spiking problems:
   - Problems where `first_seen` is in the last 7 days AND `frequency_count < 5`
   - OR: clusters created in the last 7 days with `opportunity_score > 0.3`
   - Include raw signal_phrases for the Newsletter agent to use

3. **Curious Corner** — query trending_topics:
   - Where `extracted_at` in last 7 days AND `featured_in_newsletter = false`
   - Order by `novelty_score DESC`
   - Take top 5 (Newsletter agent picks 2-3)

After newsletter is published, update:
- `newsletter_appearances += 1` and `last_featured_at = NOW()` on featured opportunities
- `featured_in_newsletter = true` on used trending_topics
