# AgentPulse Phase 2: Clustering, Investment Scanner & Newsletter Agent

**Date:** February 7, 2026  
**Prerequisite:** Phase 1 complete (Gato, Analyst, Processor running as 3 Docker services)  
**Delegation fix:** Ensure Gato is delegating `/scan` to Analyst via `create_agent_task` before proceeding

---

## What This Phase Covers

| Feature | Priority | Description |
|---------|----------|-------------|
| Problem Clustering | P0 | Group similar problems before generating opportunities — makes Pipeline 1 actually work properly |
| Investment Scanner (Pipeline 2) | P1 | Extract tool/product mentions, sentiment, and trends from Moltbook |
| Newsletter Agent | P2 | Auto-generate weekly intelligence digests from opportunities + tool trends |

---

## Part 1: Problem Clustering

### Why This Matters

Right now, Pipeline 1 skips clustering entirely. It extracts individual problems, then generates an opportunity per problem. This means:

- Duplicate/similar problems each produce separate opportunities
- No signal aggregation (3 people complaining about the same thing should count more than 1)
- The `problem_clusters` table exists but is empty
- The `opportunity_score` formula from the architecture doc is never applied
- Opportunities aren't linked to clusters via `cluster_id`

After this fix, the pipeline becomes: **Extract → Cluster → Score → Generate Opportunities from Clusters** (not from individual problems).

### Database Changes

The `problem_clusters` table already exists. We need one new Supabase function and a small schema addition:

```sql
-- Run in Supabase SQL Editor

-- Add a clustered flag to problems so we know which have been grouped
ALTER TABLE problems ADD COLUMN IF NOT EXISTS cluster_id UUID REFERENCES problem_clusters(id);
CREATE INDEX IF NOT EXISTS idx_problems_cluster ON problems(cluster_id);

-- Function to compute opportunity score for a cluster
CREATE OR REPLACE FUNCTION compute_opportunity_score(
    p_frequency INT,
    p_max_frequency INT,
    p_last_seen TIMESTAMPTZ,
    p_wtp TEXT,        -- 'explicit', 'implied', 'none'
    p_solution_gap TEXT -- 'none', 'inadequate', 'solved'
)
RETURNS FLOAT AS $$
DECLARE
    freq_weight FLOAT;
    recency_weight FLOAT;
    wtp_weight FLOAT;
    gap_weight FLOAT;
    days_ago FLOAT;
BEGIN
    -- Frequency: log scale normalized
    IF p_max_frequency > 1 THEN
        freq_weight := ln(GREATEST(p_frequency, 1)::FLOAT) / ln(p_max_frequency::FLOAT);
    ELSE
        freq_weight := 1.0;
    END IF;

    -- Recency
    days_ago := EXTRACT(EPOCH FROM (NOW() - p_last_seen)) / 86400.0;
    IF days_ago < 7 THEN recency_weight := 1.0;
    ELSIF days_ago < 30 THEN recency_weight := 0.7;
    ELSE recency_weight := 0.3;
    END IF;

    -- Willingness to pay
    CASE p_wtp
        WHEN 'explicit' THEN wtp_weight := 1.0;
        WHEN 'implied' THEN wtp_weight := 0.5;
        ELSE wtp_weight := 0.0;
    END CASE;

    -- Solution gap
    CASE p_solution_gap
        WHEN 'none' THEN gap_weight := 1.0;
        WHEN 'inadequate' THEN gap_weight := 0.5;
        ELSE gap_weight := 0.0;
    END CASE;

    RETURN (freq_weight * 0.3) + (recency_weight * 0.2) + (wtp_weight * 0.3) + (gap_weight * 0.2);
END;
$$ LANGUAGE plpgsql;
```

### New Processor Function: `cluster_problems()`

This goes into `agentpulse_processor.py`. The approach:

1. Fetch all unclustered problems (where `cluster_id IS NULL`)
2. Send them to OpenAI with the clustering prompt (already defined in PROMPTS.md)
3. For each cluster returned: create a `problem_clusters` row, link problems to it
4. Compute `opportunity_score` using the scoring formula
5. Update `total_mentions` and `avg_recency_days`

```python
CLUSTERING_PROMPT = """You are grouping similar problems into clusters.

Given these problems, group them by underlying theme. Problems in the same cluster
should be solvable by the same product/service.

Problems:
{problems}

For each cluster, provide:
1. theme: Short name (e.g., "Agent Authentication", "Payment Settlement Delays")
2. description: 1-2 sentences explaining the common thread
3. problem_ids: List of problem IDs in this cluster
4. combined_severity: Overall severity (low/medium/high)
5. willingness_to_pay: Strongest WTP signal across problems (none/implied/explicit)
6. solution_gap: none (no solutions exist), inadequate (solutions exist but poor), solved

Respond ONLY with valid JSON:
{{
  "clusters": [
    {{
      "theme": "...",
      "description": "...",
      "problem_ids": ["..."],
      "combined_severity": "...",
      "willingness_to_pay": "...",
      "solution_gap": "..."
    }}
  ]
}}

Aim for 3-10 clusters. Merge near-duplicates. Don't create single-problem clusters
unless the problem is truly unique."""


def cluster_problems(min_problems: int = 3) -> dict:
    """Group unclustered problems into thematic clusters."""
    if not supabase or not openai_client:
        return {'error': 'Not configured'}

    run_id = log_pipeline_start('cluster_problems')

    # Fetch unclustered problems
    problems = supabase.table('problems')\
        .select('*')\
        .is_('cluster_id', 'null')\
        .order('created_at', desc=True)\
        .limit(200)\
        .execute()

    if not problems.data or len(problems.data) < min_problems:
        logger.info(f"Not enough unclustered problems ({len(problems.data or [])})")
        return {'clusters_created': 0, 'reason': 'insufficient_problems'}

    # Format for prompt
    problems_text = json.dumps([
        {
            'id': str(p['id']),
            'description': p['description'],
            'category': p['category'],
            'frequency': p['frequency_count'],
            'severity': p.get('metadata', {}).get('severity', 'medium'),
            'wtp': p.get('metadata', {}).get('willingness_to_pay', 'none')
        }
        for p in problems.data
    ], indent=2)

    # Call OpenAI for clustering
    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You cluster related problems. Respond only with valid JSON."},
                {"role": "user", "content": CLUSTERING_PROMPT.format(problems=problems_text)}
            ],
            temperature=0.3,
            max_tokens=4000
        )

        result_text = response.choices[0].message.content
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]

        cluster_data = json.loads(result_text.strip())

    except Exception as e:
        logger.error(f"Clustering failed: {e}")
        log_pipeline_end(run_id, 'failed', {'error': str(e)})
        return {'error': str(e)}

    # Store clusters and link problems
    clusters_created = 0
    # Get max frequency for scoring
    max_freq = max((p['frequency_count'] for p in problems.data), default=1)

    for cluster in cluster_data.get('clusters', []):
        try:
            problem_ids = cluster['problem_ids']

            # Get the actual problems in this cluster
            cluster_problems_data = [
                p for p in problems.data if str(p['id']) in problem_ids
            ]
            if not cluster_problems_data:
                continue

            total_mentions = sum(p['frequency_count'] for p in cluster_problems_data)
            last_seen = max(p['last_seen'] for p in cluster_problems_data)

            # Compute opportunity score
            days_ago = (datetime.utcnow() - datetime.fromisoformat(
                last_seen.replace('Z', '+00:00').replace('+00:00', '')
            )).days if last_seen else 999

            wtp = cluster.get('willingness_to_pay', 'none')
            gap = cluster.get('solution_gap', 'none')

            # Manual score computation (mirrors the SQL function)
            import math
            freq_weight = math.log(max(total_mentions, 1)) / math.log(max(max_freq, 2))
            recency_weight = 1.0 if days_ago < 7 else (0.7 if days_ago < 30 else 0.3)
            wtp_weight = {'explicit': 1.0, 'implied': 0.5}.get(wtp, 0.0)
            gap_weight = {'none': 1.0, 'inadequate': 0.5}.get(gap, 0.0)
            opp_score = (freq_weight * 0.3) + (recency_weight * 0.2) + \
                        (wtp_weight * 0.3) + (gap_weight * 0.2)

            # Insert cluster
            cluster_record = supabase.table('problem_clusters').insert({
                'theme': cluster['theme'],
                'description': cluster['description'],
                'problem_ids': problem_ids,
                'total_mentions': total_mentions,
                'avg_recency_days': days_ago,
                'opportunity_score': round(opp_score, 3),
                'market_validation': {
                    'willingness_to_pay': wtp,
                    'solution_gap': gap,
                    'combined_severity': cluster.get('combined_severity', 'medium')
                }
            }).execute()

            # Link problems to cluster
            if cluster_record.data:
                cluster_id = cluster_record.data[0]['id']
                for pid in problem_ids:
                    try:
                        supabase.table('problems')\
                            .update({'cluster_id': cluster_id})\
                            .eq('id', pid)\
                            .execute()
                    except Exception:
                        pass  # Problem ID might not match

            clusters_created += 1

        except Exception as e:
            logger.error(f"Error creating cluster: {e}")

    result = {
        'problems_processed': len(problems.data),
        'clusters_created': clusters_created
    }
    log_pipeline_end(run_id, 'completed', result)
    return result
```

### Updated `generate_opportunities()` — Now Uses Clusters

The current function generates opportunities from individual problems. It should generate from clusters instead:

```python
def generate_opportunities(min_score: float = 0.3, limit: int = 5) -> dict:
    """Generate opportunities from top-scoring problem clusters."""
    if not supabase or not openai_client:
        return {'error': 'Not configured'}

    run_id = log_pipeline_start('generate_opportunities')

    # Get top clusters that don't have opportunities yet
    clusters = supabase.table('problem_clusters')\
        .select('*')\
        .gte('opportunity_score', min_score)\
        .order('opportunity_score', desc=True)\
        .limit(limit * 2)\
        .execute()

    if not clusters.data:
        return {'opportunities_generated': 0}

    # Filter out clusters that already have opportunities
    existing_opps = supabase.table('opportunities')\
        .select('cluster_id')\
        .execute()
    existing_cluster_ids = {o['cluster_id'] for o in (existing_opps.data or []) if o['cluster_id']}

    new_clusters = [c for c in clusters.data if c['id'] not in existing_cluster_ids][:limit]

    opportunities_created = 0

    for cluster in new_clusters:
        try:
            cluster_data = json.dumps({
                'theme': cluster['theme'],
                'description': cluster['description'],
                'frequency': cluster['total_mentions'],
                'recency_days': cluster['avg_recency_days'],
                'opportunity_score': cluster['opportunity_score'],
                'market_validation': cluster.get('market_validation', {})
            }, indent=2)

            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You generate startup opportunity briefs. Respond only with valid JSON."},
                    {"role": "user", "content": OPPORTUNITY_PROMPT.format(problem_data=cluster_data)}
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

            # Store with cluster linkage
            store_opportunity(opp_data, cluster_id=cluster['id'])
            save_opportunity_brief(opp_data)
            opportunities_created += 1

        except Exception as e:
            logger.error(f"Error generating opportunity for cluster {cluster['theme']}: {e}")

    result = {'opportunities_generated': opportunities_created}
    log_pipeline_end(run_id, 'completed', result)
    return result


def store_opportunity(opp: dict, cluster_id: str = None):
    """Store opportunity in Supabase with cluster linkage."""
    if not supabase:
        return

    record = {
        'cluster_id': cluster_id,
        'title': opp.get('title'),
        'problem_summary': opp.get('problem_summary'),
        'proposed_solution': opp.get('proposed_solution'),
        'business_model': opp.get('business_model'),
        'target_market': opp.get('target_market'),
        'market_size_estimate': opp.get('market_size_estimate'),
        'why_now': opp.get('why_now'),
        'competitive_landscape': opp.get('competitive_landscape'),
        'confidence_score': opp.get('confidence_score', 0.5),
        'pitch_brief': opp.get('pitch_brief'),
        'status': 'draft'
    }

    supabase.table('opportunities').insert(record).execute()
```

### Updated Pipeline Flow

The `run_pipeline` task now includes clustering:

```python
elif task_type == 'run_pipeline':
    scrape_result = scrape_moltbook()
    extract_result = extract_problems()
    cluster_result = cluster_problems()       # NEW step
    opp_result = generate_opportunities()     # Now uses clusters
    return {
        'scrape': scrape_result,
        'extract': extract_result,
        'cluster': cluster_result,
        'opportunities': opp_result
    }
```

Also add `cluster_problems` as a standalone task in `execute_task()`:

```python
elif task_type == 'cluster_problems':
    return cluster_problems(
        min_problems=params.get('min_problems', 3)
    )
```

### Scheduled Clustering

Add to the scheduler:

```python
def setup_scheduler():
    # ... existing schedules ...
    schedule.every(12).hours.do(scheduled_cluster)  # Run after analysis

def scheduled_cluster():
    logger.info("Scheduled: clustering problems")
    cluster_problems()
```

---

## Part 2: Pipeline 2 — Investment Scanner

### What It Does

Scans Moltbook posts for mentions of specific tools, products, and services. Tracks:

- **What tools** agents are using (and how often)
- **Sentiment** — are they happy or frustrated?
- **Trends** — rising/falling popularity over time
- **Switches** — "I moved from X to Y" signals
- **Recommendations** — "you should try X" signals

### Database

The `tool_mentions` table already exists from the original migration. We need one additional table and view:

```sql
-- Run in Supabase SQL Editor

-- Aggregated tool stats (materialized periodically)
CREATE TABLE tool_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tool_name TEXT UNIQUE NOT NULL,
    total_mentions INT DEFAULT 0,
    mentions_7d INT DEFAULT 0,
    mentions_30d INT DEFAULT 0,
    avg_sentiment FLOAT DEFAULT 0.0,
    sentiment_trend FLOAT DEFAULT 0.0,     -- change in avg sentiment over 30d
    recommendation_count INT DEFAULT 0,
    complaint_count INT DEFAULT 0,
    top_alternatives TEXT[],                -- most mentioned alternatives
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tool_stats_mentions ON tool_stats(total_mentions DESC);
CREATE INDEX idx_tool_stats_name ON tool_stats(tool_name);

-- View: trending tools (rising mentions + positive sentiment)
CREATE OR REPLACE VIEW trending_tools AS
SELECT
    ts.*,
    CASE
        WHEN mentions_7d > 0 AND mentions_30d > 0
        THEN (mentions_7d::FLOAT / GREATEST(mentions_30d::FLOAT / 4.3, 1)) -- weekly rate vs monthly avg
        ELSE 0
    END as momentum_score
FROM tool_stats ts
WHERE last_seen > NOW() - INTERVAL '30 days'
ORDER BY momentum_score DESC, total_mentions DESC
LIMIT 20;

-- View: tools with negative sentiment (investment warnings)
CREATE OR REPLACE VIEW tool_warnings AS
SELECT *
FROM tool_stats
WHERE avg_sentiment < -0.3
  AND total_mentions >= 3
  AND last_seen > NOW() - INTERVAL '30 days'
ORDER BY avg_sentiment ASC;
```

### Tool Extraction Prompt

```python
TOOL_EXTRACTION_PROMPT = """You are an analyst identifying tool and product mentions in social media posts by AI agents.

Analyze these posts and extract every mention of a specific tool, product, service, platform, library, or framework.

For each mention, provide:
1. tool_name: Normalized name (e.g., "LangChain" not "langchain" or "lang chain")
2. tool_name_raw: Exactly as written in the post
3. context: The sentence or phrase where it's mentioned
4. sentiment_score: -1.0 (very negative) to 1.0 (very positive), 0.0 for neutral
5. sentiment_label: "positive", "negative", or "neutral"
6. is_recommendation: true if the author is recommending this tool to others
7. is_complaint: true if the author is complaining about this tool
8. alternative_mentioned: If they mention switching from/to another tool, note it (e.g., "switched from LangChain to LlamaIndex")
9. source_post_id: The post ID where this was found

Posts to analyze:
{posts}

Respond ONLY with valid JSON:
{{
  "tool_mentions": [
    {{
      "tool_name": "...",
      "tool_name_raw": "...",
      "context": "...",
      "sentiment_score": 0.0,
      "sentiment_label": "...",
      "is_recommendation": false,
      "is_complaint": false,
      "alternative_mentioned": null,
      "source_post_id": "..."
    }}
  ]
}}

Rules:
- Include programming languages, frameworks, APIs, platforms, SaaS tools, protocols
- Don't include generic terms like "API" or "database" unless they refer to a specific product
- Normalize names consistently (e.g., "GPT-4" not "gpt4" or "GPT 4")
- One mention per tool per post (even if mentioned multiple times)"""
```

### Processor Functions

```python
def extract_tool_mentions(hours_back: int = 48) -> dict:
    """Extract tool/product mentions from recent posts."""
    if not supabase or not openai_client:
        return {'error': 'Not configured'}

    run_id = log_pipeline_start('extract_tools')

    # Fetch posts not yet scanned for tools
    # We reuse moltbook_posts but need a separate "tools_processed" flag
    # For now, use posts from the last N hours regardless of processed status
    cutoff = datetime.utcnow() - timedelta(hours=hours_back)
    posts = supabase.table('moltbook_posts')\
        .select('*')\
        .gte('scraped_at', cutoff.isoformat())\
        .limit(100)\
        .execute()

    if not posts.data:
        return {'mentions_found': 0}

    # Format posts
    posts_text = "\n\n".join([
        f"[Post ID: {p['moltbook_id']}]\n{p.get('title', '')}\n{p['content']}"
        for p in posts.data
    ])

    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You extract tool and product mentions. Respond only with valid JSON."},
                {"role": "user", "content": TOOL_EXTRACTION_PROMPT.format(posts=posts_text)}
            ],
            temperature=0.2,
            max_tokens=4000
        )

        result_text = response.choices[0].message.content
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]

        mentions_data = json.loads(result_text.strip())

    except Exception as e:
        logger.error(f"Tool extraction failed: {e}")
        log_pipeline_end(run_id, 'failed', {'error': str(e)})
        return {'error': str(e)}

    # Store mentions
    mentions_stored = 0
    for mention in mentions_data.get('tool_mentions', []):
        try:
            # Look up the internal post UUID from moltbook_id
            post_lookup = supabase.table('moltbook_posts')\
                .select('id')\
                .eq('moltbook_id', mention.get('source_post_id', ''))\
                .limit(1)\
                .execute()

            post_uuid = post_lookup.data[0]['id'] if post_lookup.data else None

            record = {
                'tool_name': mention['tool_name'],
                'tool_name_raw': mention.get('tool_name_raw'),
                'post_id': post_uuid,
                'context': mention.get('context'),
                'sentiment_score': mention.get('sentiment_score', 0.0),
                'sentiment_label': mention.get('sentiment_label', 'neutral'),
                'is_recommendation': mention.get('is_recommendation', False),
                'is_complaint': mention.get('is_complaint', False),
                'alternative_mentioned': mention.get('alternative_mentioned'),
                'mentioned_at': datetime.utcnow().isoformat(),
                'metadata': {}
            }

            supabase.table('tool_mentions').insert(record).execute()
            mentions_stored += 1

        except Exception as e:
            logger.error(f"Error storing tool mention: {e}")

    result = {
        'posts_scanned': len(posts.data),
        'mentions_found': mentions_stored
    }
    log_pipeline_end(run_id, 'completed', result)
    return result


def update_tool_stats() -> dict:
    """Recompute aggregated tool statistics."""
    if not supabase:
        return {'error': 'Not configured'}

    run_id = log_pipeline_start('update_tool_stats')

    # Get all unique tool names
    tools = supabase.table('tool_mentions')\
        .select('tool_name')\
        .execute()

    unique_tools = list(set(t['tool_name'] for t in (tools.data or [])))

    stats_updated = 0
    now = datetime.utcnow()
    week_ago = (now - timedelta(days=7)).isoformat()
    month_ago = (now - timedelta(days=30)).isoformat()

    for tool_name in unique_tools:
        try:
            # Get all mentions for this tool
            mentions = supabase.table('tool_mentions')\
                .select('*')\
                .eq('tool_name', tool_name)\
                .execute()

            all_mentions = mentions.data or []
            if not all_mentions:
                continue

            recent_7d = [m for m in all_mentions if m.get('mentioned_at', '') >= week_ago]
            recent_30d = [m for m in all_mentions if m.get('mentioned_at', '') >= month_ago]

            avg_sentiment = sum(m.get('sentiment_score', 0) for m in all_mentions) / len(all_mentions)
            recommendations = sum(1 for m in all_mentions if m.get('is_recommendation'))
            complaints = sum(1 for m in all_mentions if m.get('is_complaint'))

            # Collect alternatives
            alternatives = [m['alternative_mentioned'] for m in all_mentions
                          if m.get('alternative_mentioned')]

            # Upsert stats
            stat_record = {
                'tool_name': tool_name,
                'total_mentions': len(all_mentions),
                'mentions_7d': len(recent_7d),
                'mentions_30d': len(recent_30d),
                'avg_sentiment': round(avg_sentiment, 3),
                'recommendation_count': recommendations,
                'complaint_count': complaints,
                'top_alternatives': list(set(alternatives))[:5],
                'first_seen': min(m.get('mentioned_at', '') for m in all_mentions),
                'last_seen': max(m.get('mentioned_at', '') for m in all_mentions),
                'updated_at': now.isoformat()
            }

            # Upsert: try update, then insert
            existing = supabase.table('tool_stats')\
                .select('id')\
                .eq('tool_name', tool_name)\
                .execute()

            if existing.data:
                supabase.table('tool_stats')\
                    .update(stat_record)\
                    .eq('tool_name', tool_name)\
                    .execute()
            else:
                supabase.table('tool_stats').insert(stat_record).execute()

            stats_updated += 1

        except Exception as e:
            logger.error(f"Error updating stats for {tool_name}: {e}")

    result = {'tools_updated': stats_updated}
    log_pipeline_end(run_id, 'completed', result)
    return result
```

### Task Routing for Pipeline 2

Add to `execute_task()`:

```python
elif task_type == 'extract_tools':
    return extract_tool_mentions(hours_back=params.get('hours_back', 48))

elif task_type == 'update_tool_stats':
    return update_tool_stats()

elif task_type == 'run_investment_scan':
    extract_result = extract_tool_mentions(hours_back=params.get('hours_back', 168))  # 7 days
    stats_result = update_tool_stats()
    return {'extract': extract_result, 'stats': stats_result}
```

### Scheduled Investment Scanning

```python
def setup_scheduler():
    # ... existing schedules ...
    schedule.every(12).hours.do(scheduled_tool_scan)
    schedule.every().day.at("06:00").do(scheduled_update_stats)

def scheduled_tool_scan():
    logger.info("Scheduled: extracting tool mentions")
    extract_tool_mentions(hours_back=12)

def scheduled_update_stats():
    logger.info("Scheduled: updating tool stats")
    update_tool_stats()
```

### Telegram Commands for Pipeline 2

Add to AGENTS.md and SKILL.md:

| Command | Action |
|---------|--------|
| `/tools` | Get top 10 trending tools |
| `/tool [name]` | Get detailed stats for a specific tool |
| `/invest-scan` | Trigger full investment scan |

---

## Part 3: Newsletter Agent

### Architecture

The Newsletter Agent is a fourth Docker service that generates weekly intelligence reports combining data from both pipelines.

```
docker-compose.yml
├── gato (Telegram, user-facing)
├── analyst (headless analysis)
├── processor (scraping, scheduling)
└── newsletter (NEW — generates weekly reports)
```

### What It Produces

A weekly "AgentPulse Intelligence Brief" containing:

1. **Top Opportunities** — from Pipeline 1 (clustered, scored)
2. **Trending Tools** — from Pipeline 2 (rising mentions, sentiment)
3. **Tool Warnings** — negative sentiment tools to watch
4. **Market Signals** — emerging themes from problem clusters
5. **Gato's Take** — Bitcoin-angle commentary (stays in character)

### Database

```sql
-- Run in Supabase SQL Editor

CREATE TABLE newsletters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    edition_number INT NOT NULL,
    title TEXT NOT NULL,
    content_markdown TEXT NOT NULL,         -- Full newsletter in markdown
    content_telegram TEXT,                  -- Condensed version for Telegram
    data_snapshot JSONB,                    -- Raw data used to generate
    status TEXT DEFAULT 'draft',            -- draft, reviewed, published
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_newsletters_status ON newsletters(status);
CREATE INDEX idx_newsletters_edition ON newsletters(edition_number DESC);

-- Track the latest edition number
CREATE OR REPLACE FUNCTION next_newsletter_edition()
RETURNS INT AS $$
BEGIN
    RETURN COALESCE(
        (SELECT MAX(edition_number) FROM newsletters),
        0
    ) + 1;
END;
$$ LANGUAGE plpgsql;
```

### Newsletter Docker Service

```yaml
# Add to docker-compose.yml
newsletter:
  build:
    context: ./newsletter
    dockerfile: Dockerfile
  container_name: agentpulse-newsletter
  restart: unless-stopped
  networks:
    - agentpulse-net
  environment:
    <<: *common-env
    AGENT_NAME: newsletter
    NEWSLETTER_SCHEDULE: "weekly"
    NEWSLETTER_DAY: "monday"
    NEWSLETTER_HOUR: "8"
  volumes:
    - workspace-data:/home/openclaw/.openclaw/workspace
    - ../data/openclaw/agents/newsletter:/home/openclaw/.openclaw/agents/newsletter
    - ../skills:/home/openclaw/.openclaw/skills:ro
    - ../config:/home/openclaw/.openclaw/config:ro
  mem_limit: 256m
  depends_on:
    - processor
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
```

### Newsletter Agent Identity

**`data/openclaw/agents/newsletter/agent/IDENTITY.md`**:

```markdown
# Newsletter — AgentPulse Intelligence Brief Writer

You write the weekly AgentPulse Intelligence Brief, a concise report on the
agent economy for builders, investors, and operators.

## Style

- Data-first: every claim backed by numbers
- Concise: the full brief should be readable in 3-5 minutes
- Actionable: each section ends with a "so what" takeaway
- Voice: professional but not corporate, informed insider tone
- Gato's commentary section is the one place for Bitcoin-angle editorializing

## Structure

Every edition follows this format:

1. **Header** — Edition #, date, one-line hook
2. **Top Opportunities** (3-5) — from Pipeline 1, confidence-ranked
3. **Tool Radar** — trending up, trending down, new entries
4. **Market Signals** — emerging themes from problem clusters
5. **Gato's Corner** — Bitcoin-angle commentary on the week's findings
6. **Numbers** — key stats (posts scraped, problems found, tools tracked)

## Output Formats

Generate two versions:
1. **Full markdown** — for blog/email, ~800-1200 words
2. **Telegram digest** — condensed to 500 chars for Telegram broadcast
```

### Newsletter Generation Logic

This can either live in the newsletter container as a standalone Python script, or be handled by the processor as another task type. Given our pattern, processor-based is cleaner:

```python
NEWSLETTER_PROMPT = """You are writing the AgentPulse Intelligence Brief, a weekly report
on the agent economy.

Here is this week's data:

TOP OPPORTUNITIES:
{opportunities}

TRENDING TOOLS:
{trending_tools}

TOOL WARNINGS:
{tool_warnings}

MARKET SIGNALS (problem clusters):
{clusters}

STATS:
- Posts scraped this week: {posts_count}
- Problems extracted: {problems_count}
- Tools tracked: {tools_count}
- New opportunities: {new_opps_count}

Write the newsletter with these sections:
1. One-line hook/headline for this edition
2. Top 3-5 Opportunities (name, problem, confidence, 1-line insight)
3. Tool Radar (trending up, trending down, new entries)
4. Market Signals (emerging themes)
5. Gato's Corner (Bitcoin-maximalist take on the week's findings — 2-3 sentences, punchy)
6. By the Numbers (key stats)

Write in markdown format. Be concise but insightful. ~800 words.

Also generate a Telegram-condensed version (under 500 characters, emoji-rich, punchy).

Respond in JSON:
{{
  "title": "Edition headline",
  "content_markdown": "Full newsletter in markdown",
  "content_telegram": "Short Telegram version"
}}"""


def generate_newsletter() -> dict:
    """Generate the weekly AgentPulse Intelligence Brief."""
    if not supabase or not openai_client:
        return {'error': 'Not configured'}

    run_id = log_pipeline_start('generate_newsletter')

    # Gather data
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

    # Top opportunities
    opps = supabase.table('opportunities')\
        .select('*')\
        .eq('status', 'draft')\
        .order('confidence_score', desc=True)\
        .limit(5)\
        .execute()

    # Trending tools
    tools = supabase.table('tool_stats')\
        .select('*')\
        .order('mentions_7d', desc=True)\
        .limit(10)\
        .execute()

    # Tool warnings
    warnings = supabase.table('tool_stats')\
        .select('*')\
        .lt('avg_sentiment', -0.3)\
        .gte('total_mentions', 3)\
        .execute()

    # Recent clusters
    clusters = supabase.table('problem_clusters')\
        .select('*')\
        .gte('created_at', week_ago)\
        .order('opportunity_score', desc=True)\
        .limit(10)\
        .execute()

    # Stats
    posts_count = supabase.table('moltbook_posts')\
        .select('id', count='exact')\
        .gte('scraped_at', week_ago)\
        .execute()

    problems_count = supabase.table('problems')\
        .select('id', count='exact')\
        .gte('first_seen', week_ago)\
        .execute()

    # Build the prompt data
    data_snapshot = {
        'opportunities': opps.data or [],
        'trending_tools': tools.data or [],
        'tool_warnings': warnings.data or [],
        'clusters': clusters.data or [],
        'posts_count': posts_count.count or 0,
        'problems_count': problems_count.count or 0,
        'tools_count': len(tools.data or []),
        'new_opps_count': len(opps.data or [])
    }

    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You write concise intelligence briefs. Respond only with valid JSON."},
                {"role": "user", "content": NEWSLETTER_PROMPT.format(
                    opportunities=json.dumps(opps.data or [], indent=2, default=str),
                    trending_tools=json.dumps(tools.data or [], indent=2, default=str),
                    tool_warnings=json.dumps(warnings.data or [], indent=2, default=str),
                    clusters=json.dumps(clusters.data or [], indent=2, default=str),
                    posts_count=data_snapshot['posts_count'],
                    problems_count=data_snapshot['problems_count'],
                    tools_count=data_snapshot['tools_count'],
                    new_opps_count=data_snapshot['new_opps_count']
                )}
            ],
            temperature=0.6,
            max_tokens=4000
        )

        result_text = response.choices[0].message.content
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]

        newsletter_data = json.loads(result_text.strip())

    except Exception as e:
        logger.error(f"Newsletter generation failed: {e}")
        log_pipeline_end(run_id, 'failed', {'error': str(e)})
        return {'error': str(e)}

    # Get next edition number
    edition = supabase.rpc('next_newsletter_edition').execute()
    edition_number = edition.data if edition.data else 1

    # Store newsletter
    record = {
        'edition_number': edition_number,
        'title': newsletter_data.get('title', f'AgentPulse Brief #{edition_number}'),
        'content_markdown': newsletter_data.get('content_markdown', ''),
        'content_telegram': newsletter_data.get('content_telegram', ''),
        'data_snapshot': data_snapshot,
        'status': 'draft'
    }

    supabase.table('newsletters').insert(record).execute()

    # Save markdown locally
    filename = f"newsletter_{edition_number}_{datetime.now().strftime('%Y%m%d')}.md"
    (WORKSPACE / 'agentpulse' / 'newsletters').mkdir(parents=True, exist_ok=True)
    (WORKSPACE / 'agentpulse' / 'newsletters' / filename).write_text(
        newsletter_data.get('content_markdown', '')
    )

    result = {
        'edition': edition_number,
        'title': newsletter_data.get('title'),
        'status': 'draft'
    }
    log_pipeline_end(run_id, 'completed', result)
    return result
```

### Task Routing

```python
elif task_type == 'generate_newsletter':
    return generate_newsletter()

elif task_type == 'publish_newsletter':
    # Publish the latest draft newsletter via Telegram
    latest = supabase.table('newsletters')\
        .select('*')\
        .eq('status', 'draft')\
        .order('created_at', desc=True)\
        .limit(1)\
        .execute()
    if latest.data:
        nl = latest.data[0]
        send_telegram(nl.get('content_telegram', 'No content'))
        supabase.table('newsletters').update({
            'status': 'published',
            'published_at': datetime.utcnow().isoformat()
        }).eq('id', nl['id']).execute()
        return {'published': nl['id'], 'edition': nl['edition_number']}
    return {'error': 'No draft newsletter found'}
```

### Scheduled Newsletter

```python
def setup_scheduler():
    # ... existing schedules ...
    schedule.every().monday.at("07:00").do(scheduled_newsletter)
    schedule.every().monday.at("08:00").do(scheduled_publish_newsletter)

def scheduled_newsletter():
    logger.info("Scheduled: generating weekly newsletter")
    generate_newsletter()

def scheduled_publish_newsletter():
    logger.info("Scheduled: publishing newsletter to Telegram")
    # Auto-publish or leave as draft for review
    # For now, just notify that a draft is ready
    send_telegram("📰 New AgentPulse Intelligence Brief is ready for review. Send /newsletter to see it.")
```

### Telegram Commands

| Command | Action |
|---------|--------|
| `/newsletter` | Show latest newsletter (Telegram-condensed version) |
| `/newsletter-full` | Trigger generation of a new newsletter |
| `/newsletter-publish` | Publish the latest draft |

---

## Summary: Complete Pipeline After Phase 2

```
Every 6 hours:
  Scrape Moltbook → moltbook_posts

Every 12 hours:
  Extract problems → problems table
  Cluster problems → problem_clusters table (NEW)
  Generate opportunities → opportunities table (now from clusters)
  Extract tool mentions → tool_mentions table (NEW)

Daily 6 AM:
  Update tool stats → tool_stats table (NEW)

Daily 9 AM:
  Send opportunity digest → Telegram

Weekly Monday 7 AM:
  Generate newsletter → newsletters table (NEW)

Weekly Monday 8 AM:
  Notify newsletter ready → Telegram
```

### Telegram Command Summary (All Commands)

| Command | Description |
|---------|-------------|
| `/pulse-status` | System status |
| `/scan` | Full pipeline scan (delegated to Analyst) |
| `/opportunities` | Top 5 opportunities |
| `/crew-status` | Agent task queue status |
| `/tools` | Top 10 trending tools (NEW) |
| `/tool [name]` | Stats for specific tool (NEW) |
| `/invest-scan` | Trigger investment scan (NEW) |
| `/newsletter` | Latest newsletter (NEW) |
| `/newsletter-full` | Generate new newsletter (NEW) |
| `/newsletter-publish` | Publish draft newsletter (NEW) |

---

*Next phases after this: Web Dashboard, REST API, Real-time Alerts*
