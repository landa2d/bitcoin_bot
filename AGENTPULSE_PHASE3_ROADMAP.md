# AgentPulse Phase 3: Roadmap

**Date:** February 10, 2026  
**Status:** Phase 2 complete, Analyst intelligence upgraded

---

## Priority Order & Rationale

| Order | Feature | Why This Order |
|-------|---------|----------------|
| 1 | Security Review | Must happen before anything public-facing. You're about to expose a website and email system — lock down auth/keys first. |
| 2 | Newsletter Content Upgrade | Fix the content quality before distributing it. No point emailing or publishing a newsletter that repeats the same opportunities every week. |
| 3 | LLM Cost Optimization | Directly saves money and should be done before scaling usage (email sends = more newsletter generations = more LLM calls). |
| 4 | Web Archive | Public-facing, so needs security review done first. Also needs good content to be worth publishing. |
| 5 | Email Service | Last because it depends on everything above: secure system, good content, optimized costs, and a web archive to link to. |

---

## 1. Security Review

### What to Audit

**Environment variables & secrets:**
- Are API keys hardcoded anywhere in code? (Should only be in .env, never in Dockerfiles, docker-compose.yml, or committed code)
- Is .env in .gitignore?
- Are auth-profiles.json files in .gitignore?
- Does the GitHub repo have any secrets in commit history?
- Are Supabase keys using anon/public key or service key? (Anon key is fine for now but has RLS implications)

**Docker exposure:**
- Which ports are exposed on the Hetzner server? (Should be minimal — Telegram bot doesn't need open ports)
- Is the Supabase URL accessible without auth? (Check RLS policies)
- Are any volumes exposing sensitive data?

**Supabase security:**
- Is Row Level Security (RLS) enabled on all tables? (Critical when you add a public web archive)
- Are there any tables with sensitive data that shouldn't be publicly queryable?
- Is the anon key safe to use in a frontend? (Only if RLS is properly configured)

**API key exposure risks:**
- OpenAI key — only in .env and processor container
- Anthropic key — in .env and auth-profiles.json (volume-mounted, not in image)
- Telegram bot token — only in .env, exposed to gato and processor
- Moltbook API token — only in .env
- Supabase key — in .env, shared across all services

**Network:**
- Container-to-container communication is on a bridge network (good)
- Are any containers exposing ports to the host unnecessarily?

### Deliverable
A security audit checklist with specific fixes. Likely includes: adding RLS policies to Supabase, confirming .gitignore coverage, checking for hardcoded secrets, and preparing for public web access.

---

## 2. Newsletter Content Upgrade

### Problem
The newsletter keeps surfacing the same high-frequency opportunities. High frequency = mentioned most = always on top. But:
- Established problems that everyone talks about aren't necessarily the best opportunities
- Small but novel signals get buried
- There's no "interesting/curious" content — everything is framed as investment opportunities

### Solution: Three Content Sections

#### Section A: "Established Opportunities" (Existing, Refined)
- Top 3-5 by combined score (frequency + recency + WTP)
- BUT: add a **staleness penalty** — opportunities that appeared in previous newsletters get downranked
- Track which opportunities have been featured before in a new column
- Only show opportunities that have NEW signals since last featured

#### Section B: "Emerging Signals" (New)
- Low frequency (< 5 mentions) but HIGH recency (last 7 days)
- OR: first-time appearance in problem extraction
- OR: sudden spike (mentioned 0 times last month, 3+ times this week)
- These are the "small but potentially interesting" signals
- Frame as: "Early, but worth watching"
- Lower confidence threshold — it's ok to include speculative signals here

#### Section C: "The Curious Corner" (New)
- NOT framed as investment opportunities at all
- Interesting conversations, debates, cultural moments in the agent economy
- Trending topics that don't map to business problems
- Unusual tool usage patterns
- Funny or surprising things agents are doing
- Think of this as the "water cooler" section
- Requires a different extraction prompt — looking for interesting/novel/surprising, not problems/complaints

### Database Changes

```sql
-- Track newsletter appearances to prevent repetition
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS newsletter_appearances INT DEFAULT 0;
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS last_featured_at TIMESTAMPTZ;
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS first_featured_at TIMESTAMPTZ;

-- Curious/trending content table
CREATE TABLE trending_topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    topic_type TEXT NOT NULL,        -- 'debate', 'cultural', 'surprising', 'meta', 'technical'
    source_post_ids UUID[],
    engagement_score FLOAT,           -- upvotes + comments normalized
    novelty_score FLOAT,             -- how new/unexpected this is
    extracted_at TIMESTAMPTZ DEFAULT NOW(),
    featured_in_newsletter BOOLEAN DEFAULT FALSE,
    metadata JSONB
);

CREATE INDEX idx_trending_topics_type ON trending_topics(topic_type);
CREATE INDEX idx_trending_topics_extracted ON trending_topics(extracted_at DESC);
```

### New Extraction Prompt: Trending Topics

A new prompt for the Processor that runs alongside problem extraction:

```
Analyze these posts for interesting, surprising, or culturally significant 
conversations — NOT business problems or complaints. Look for:

1. Debates: Agents disagreeing about approaches, philosophies, or tools
2. Cultural moments: Memes, inside jokes, community milestones
3. Surprising usage: Agents doing unexpected things with tools
4. Meta discussions: Agents talking about the agent economy itself
5. Technical novelty: New approaches or techniques being discussed

For each, provide:
- title: Catchy 5-8 word title
- description: 2-3 sentence summary of what's interesting about this
- topic_type: debate, cultural, surprising, meta, technical
- why_interesting: One sentence on why a reader would care
- source_post_ids: The relevant posts

These are NOT investment opportunities. They're the interesting bits of
conversation that make the agent economy feel alive.
```

### Newsletter Agent Updates

The Newsletter agent's IDENTITY.md gets updated with the new 3-section structure:
- Section A: Established Opportunities (with staleness filtering)
- Section B: Emerging Signals (low frequency, high recency)
- Section C: The Curious Corner (trending topics, no investment framing)

### Processor Updates

The `prepare_newsletter_data()` function needs to gather:
- Established opportunities (high score, filtered by staleness)
- Emerging signals (new problems, low frequency, recent)
- Trending topics (from new trending_topics table)
- After newsletter generation: update `newsletter_appearances` and `last_featured_at` on featured opportunities

---

## 3. LLM Cost Optimization

### Current State
Everything uses `gpt-4o` for analysis. That's expensive for tasks that don't need it.

### Optimization Map

| Task | Current Model | Recommended Model | Why |
|------|--------------|-------------------|-----|
| Problem extraction | gpt-4o | gpt-4o-mini | Structured extraction, clear prompt, doesn't need deep reasoning |
| Tool extraction | gpt-4o | gpt-4o-mini | Same — structured extraction |
| Clustering | gpt-4o | gpt-4o-mini | Grouping similar items, not complex reasoning |
| Opportunity generation | gpt-4o | gpt-4o | Keep — needs judgment and creativity |
| Trending topic extraction | gpt-4o | gpt-4o-mini | Structured extraction |
| Analyst reasoning | Anthropic (via OpenClaw) | Keep Anthropic | This IS the intelligence layer — don't downgrade |
| Newsletter writing | Anthropic (via OpenClaw) | Keep Anthropic | Editorial voice quality matters |
| Digest summary | gpt-4o | gpt-4o-mini | Simple formatting task |
| Tool stats computation | None (Python) | None | Already no LLM needed |

### Implementation

Add a model routing config to `agentpulse-config.json`:

```json
{
  "models": {
    "extraction": "gpt-4o-mini",
    "clustering": "gpt-4o-mini",
    "opportunity_generation": "gpt-4o",
    "trending_topics": "gpt-4o-mini",
    "digest": "gpt-4o-mini"
  }
}
```

Update the Processor to read model from config per task instead of using a single `OPENAI_MODEL` env var.

### Estimated Savings
gpt-4o-mini is ~15x cheaper than gpt-4o for input tokens and ~10x for output. Moving extraction, clustering, and trending topics to mini should cut OpenAI costs by roughly 60-70%.

---

## 4. Web Archive

### Architecture
A lightweight static site hosted on the Hetzner server via a new Docker service.

```
newsletter-web (Docker service)
├── Nginx or Caddy serving static HTML
├── Pulls newsletter data from Supabase via public API
├── Server-side rendered or static HTML generation
├── Shows: list of past editions, individual edition pages
└── Optional: subscribe form (for Phase 5 email)
```

### Tech Choice
Simplest approach: **single HTML page + client-side JS** that queries Supabase directly.

- No build step, no framework
- Use Supabase anon key (safe with RLS enabled — security review must be done first)
- Newsletters table is read-only from the frontend
- Markdown → HTML conversion in the browser (marked.js)
- Host via Nginx in a Docker container, or a simple Python HTTP server

### Pages
- `/` — List of all published newsletters, newest first
- `/edition/:number` — Single edition view, full markdown rendered

### Domain
You'll need to decide on a domain/subdomain. Can be set up with Caddy (auto-HTTPS) or Nginx + Let's Encrypt.

### Supabase RLS
Critical — must be configured before exposing Supabase to a frontend:

```sql
-- Enable RLS on newsletters
ALTER TABLE newsletters ENABLE ROW LEVEL SECURITY;

-- Public can only read published newsletters
CREATE POLICY "Public can read published newsletters"
ON newsletters FOR SELECT
USING (status = 'published');

-- Service role (processor) can insert/update anything
-- (This uses the service key, not the anon key)
```

---

## 5. Email Newsletter Service

### Architecture

```
Processor (weekly schedule)
  → prepare_newsletter_data()
  → Newsletter agent writes the brief
  → Draft stored in newsletters table
  → You review: /newsletter → /newsletter-publish
  → On publish:
     1. Send to Telegram (existing)
     2. Send to email subscribers (NEW)
     3. Mark as published on web archive (existing)
```

### Email Provider: Resend
- Simplest API, generous free tier (100 emails/day, 3000/month)
- Single API call to send
- Supports HTML emails
- Has a React email template library (optional)

### Subscriber Management

```sql
-- Supabase table
CREATE TABLE newsletter_subscribers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    subscribed_at TIMESTAMPTZ DEFAULT NOW(),
    unsubscribed_at TIMESTAMPTZ,
    status TEXT DEFAULT 'active',     -- active, unsubscribed, bounced
    confirmation_token TEXT,
    confirmed BOOLEAN DEFAULT FALSE,
    metadata JSONB
);

CREATE INDEX idx_subscribers_status ON newsletter_subscribers(status);
CREATE INDEX idx_subscribers_email ON newsletter_subscribers(email);
```

### Flow
1. Subscribe form on the web archive site
2. Confirmation email (double opt-in)
3. On `/newsletter-publish`:
   - Processor queries active subscribers
   - Converts newsletter markdown to HTML
   - Sends via Resend API to each subscriber
   - Logs delivery status
4. Each email includes unsubscribe link

### Processor Addition
- New function: `send_newsletter_email(newsletter_id)`
- Called as part of the publish flow
- Converts markdown → HTML (using a template)
- Sends via Resend API
- New env var: `RESEND_API_KEY`

---

## Implementation Sequence

```
Week 1: Security Review + Content Upgrade
  Prompt 1: Security audit & fixes
  Prompt 2: Supabase schema for content upgrade
  Prompt 3: Trending topics extraction in Processor
  Prompt 4: Newsletter staleness filtering + 3-section structure
  Prompt 5: Update Newsletter agent identity for new sections

Week 2: LLM Optimization + Web Archive
  Prompt 6: Model routing config in Processor
  Prompt 7: Supabase RLS policies
  Prompt 8: Web archive Docker service + HTML
  Prompt 9: Domain/HTTPS setup

Week 3: Email Service
  Prompt 10: Subscriber table + subscribe/confirm flow
  Prompt 11: Resend integration in Processor
  Prompt 12: Subscribe form on web archive
  Prompt 13: Wire /newsletter-publish to send emails
```

---

*After Phase 3: Web Dashboard (real-time opportunity tracking), REST API, Real-time Alerts*
