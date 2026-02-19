# AgentPulse Phase 4: Content Quality — Source Expansion + Prediction Tracking

**Date:** February 17, 2026  
**Priority:** Content quality — make the newsletter worth reading  
**Goal:** Richer data from multiple sources + accountability for past calls

---

## Overview

Two features that compound each other:

1. **Source Expansion** — Add Hacker News and GitHub as data sources alongside Moltbook. The Analyst gets 3x the signal to reason about, and cross-source validation makes findings stronger.

2. **Prediction Tracking** — When the newsletter highlights an opportunity or emerging signal, track what actually happens. "4 weeks ago we flagged agent memory as an emerging opportunity. Here's what happened since." This is rare in AI newsletters and builds credibility.

---

## Part 1: Source Expansion

### Architecture

```
CURRENT:
  Moltbook → Processor → Problems/Tools → Analyst → Newsletter

AFTER:
  Moltbook  ─┐
  HN         ├→ Processor → Unified Problems/Tools/Signals → Analyst → Newsletter
  GitHub    ─┘
  
  Each source has its own scraper but feeds into the same extraction pipeline.
  The Analyst sees cross-source signals: "This tool was complained about on Moltbook
  AND discussed on HN AND has a trending competitor on GitHub."
```

### Why These Sources

**Hacker News:**
- Public API (no auth needed): https://hacker-news.firebaseio.com/v0/
- Agent/AI posts get heavy discussion
- Comments contain real user opinions (problems, tool complaints, tool praise)
- "Show HN" posts reveal new tools entering the market
- High signal-to-noise for technical topics

**GitHub:**
- Public API + trending page (no auth for read, optional token for higher rate limits)
- Trending repos show what developers are actually building
- Star velocity = market interest signal
- New repos in agent/AI categories = emerging tools
- README descriptions = what problems they claim to solve

### Data Model

#### Unified Source Table

Instead of separate tables per source, add a `source` column to track where data came from:

```sql
-- New: multi-source posts table
CREATE TABLE source_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source TEXT NOT NULL,                  -- 'moltbook', 'hackernews', 'github'
    source_id TEXT NOT NULL,               -- Original ID from the source
    source_url TEXT,                       -- Link to original
    
    -- Content
    title TEXT,
    body TEXT,
    author TEXT,
    
    -- Metadata varies by source
    score INT,                             -- HN points, GitHub stars, Moltbook upvotes
    comment_count INT,
    tags TEXT[],                           -- HN tags, GitHub topics, Moltbook submolts
    
    -- Processing state
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    processing_type TEXT,                  -- 'problem_extraction', 'tool_extraction', 'trending_topics'
    
    -- Source-specific metadata
    metadata JSONB,                        -- Flexible per-source data
    
    UNIQUE(source, source_id)
);

CREATE INDEX idx_source_posts_source ON source_posts(source);
CREATE INDEX idx_source_posts_scraped ON source_posts(scraped_at DESC);
CREATE INDEX idx_source_posts_processed ON source_posts(processed);
CREATE INDEX idx_source_posts_score ON source_posts(score DESC);
```

#### Update Existing Tables

```sql
-- Add source tracking to problems
ALTER TABLE problems ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'moltbook';
ALTER TABLE problems ADD COLUMN IF NOT EXISTS source_post_ids TEXT[];   -- if not already present
CREATE INDEX IF NOT EXISTS idx_problems_source ON problems(source);

-- Add source tracking to tool_mentions
ALTER TABLE tool_mentions ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'moltbook';
CREATE INDEX IF NOT EXISTS idx_tool_mentions_source ON tool_mentions(source);

-- Add source tracking to trending_topics
ALTER TABLE trending_topics ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'moltbook';
```

### Hacker News Scraper

**API:** https://hacker-news.firebaseio.com/v0/
- `/topstories.json` — top 500 story IDs
- `/newstories.json` — newest 500
- `/item/{id}.json` — individual item (story or comment)
- No auth, no rate limit (be polite — 1 req/sec)

**Strategy:**
1. Every 6 hours: fetch top 200 stories
2. Filter for AI/agent relevance by checking title + URL against keywords
3. For relevant stories: fetch top 20 comments (the real signal)
4. Store in source_posts with source='hackernews'

**Keywords for filtering:**
```python
HN_KEYWORDS = [
    'agent', 'ai agent', 'llm', 'gpt', 'claude', 'anthropic', 'openai',
    'autonomous', 'multi-agent', 'agentic', 'tool use', 'function calling',
    'rag', 'retrieval', 'embedding', 'vector', 'langchain', 'langgraph',
    'autogen', 'crewai', 'openclaw', 'mcp', 'model context protocol',
    'ai startup', 'ai tool', 'ai framework', 'ai infrastructure',
    'chatbot', 'copilot', 'assistant', 'automation'
]
```

**What we extract from HN:**
- Story titles + URLs → tool mentions, new product launches
- Comments → problems, opinions, tool sentiment, recommendations
- "Show HN" posts → new tools entering the market
- Upvotes + comment count → engagement/interest signal

```python
def scrape_hackernews(limit: int = 200) -> dict:
    """Scrape HN for agent/AI relevant posts and comments."""
    import httpx
    
    HN_API = 'https://hacker-news.firebaseio.com/v0'
    
    # Get top stories
    top_ids = httpx.get(f'{HN_API}/topstories.json', timeout=10).json()[:limit]
    
    relevant_posts = []
    
    for story_id in top_ids:
        try:
            story = httpx.get(f'{HN_API}/item/{story_id}.json', timeout=10).json()
            if not story or story.get('type') != 'story':
                continue
            
            title = (story.get('title') or '').lower()
            
            # Check relevance
            if not any(kw in title for kw in HN_KEYWORDS):
                continue
            
            # Fetch top comments
            comment_ids = (story.get('kids') or [])[:20]
            comments = []
            for cid in comment_ids:
                try:
                    comment = httpx.get(f'{HN_API}/item/{cid}.json', timeout=10).json()
                    if comment and comment.get('text'):
                        comments.append({
                            'author': comment.get('by', 'anon'),
                            'text': comment['text'],
                            'score': comment.get('score', 0)
                        })
                    time.sleep(0.2)  # Be polite
                except:
                    continue
            
            # Store
            post_data = {
                'source': 'hackernews',
                'source_id': str(story_id),
                'source_url': story.get('url') or f"https://news.ycombinator.com/item?id={story_id}",
                'title': story.get('title'),
                'body': '\n\n'.join([c['text'] for c in comments]),
                'author': story.get('by', 'anon'),
                'score': story.get('score', 0),
                'comment_count': story.get('descendants', 0),
                'tags': ['show_hn'] if title.startswith('show hn') else [],
                'metadata': {
                    'hn_url': f"https://news.ycombinator.com/item?id={story_id}",
                    'comments': comments[:10],  # Store top 10 for extraction
                    'is_show_hn': title.startswith('show hn')
                }
            }
            
            relevant_posts.append(post_data)
            time.sleep(0.5)  # Be polite
            
        except Exception as e:
            logger.error(f"HN scrape error for {story_id}: {e}")
            continue
    
    # Upsert into source_posts
    for post in relevant_posts:
        supabase.table('source_posts').upsert(
            post, on_conflict='source,source_id'
        ).execute()
    
    return {'source': 'hackernews', 'posts_found': len(relevant_posts)}
```

### GitHub Scraper

**APIs:**
- Search API: `GET https://api.github.com/search/repositories?q=...&sort=stars&order=desc`
- Trending: Scrape `https://github.com/trending?since=weekly` (no official API)
- Rate limit: 10 req/min unauthenticated, 30 req/min with token

**Strategy:**
1. Every 12 hours: search for recently created repos with agent/AI topics
2. Every 12 hours: check trending repos for the week
3. For each relevant repo: grab name, description, stars, star velocity, topics, README excerpt
4. Store in source_posts with source='github'

**Search queries:**
```python
GITHUB_QUERIES = [
    'ai agent created:>2026-02-01',
    'llm agent framework created:>2026-02-01',
    'autonomous agent created:>2026-02-01',
    'agentic ai created:>2026-02-01',
    'multi-agent created:>2026-02-01',
    'mcp server created:>2026-02-01',        # Model Context Protocol
    'function calling llm created:>2026-02-01',
    'ai tool created:>2026-02-01 stars:>10',  # Min star threshold
]
```

**What we extract from GitHub:**
- Repo name + description → tool/framework identification
- Stars + star velocity → market interest
- Topics/tags → categorization
- README first 500 chars → what problem it claims to solve
- Created date → new vs established
- Recent repos with fast star growth = emerging tools

```python
def scrape_github(days_back: int = 7) -> dict:
    """Scrape GitHub for new/trending agent/AI repos."""
    import httpx
    
    GITHUB_API = 'https://api.github.com'
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # Optional but recommended
    
    headers = {'Accept': 'application/vnd.github.v3+json'}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    
    cutoff = (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    
    seen_repos = set()
    relevant_repos = []
    
    queries = [
        f'ai agent created:>{cutoff} stars:>5',
        f'llm agent created:>{cutoff} stars:>5',
        f'autonomous agent created:>{cutoff} stars:>3',
        f'agentic created:>{cutoff} stars:>3',
        f'multi-agent created:>{cutoff} stars:>3',
        f'mcp server created:>{cutoff} stars:>3',
    ]
    
    for query in queries:
        try:
            resp = httpx.get(
                f'{GITHUB_API}/search/repositories',
                params={'q': query, 'sort': 'stars', 'order': 'desc', 'per_page': 30},
                headers=headers,
                timeout=15
            )
            
            if resp.status_code == 403:
                logger.warning("GitHub rate limit hit, stopping")
                break
            
            data = resp.json()
            
            for repo in data.get('items', []):
                repo_id = str(repo['id'])
                if repo_id in seen_repos:
                    continue
                seen_repos.add(repo_id)
                
                post_data = {
                    'source': 'github',
                    'source_id': repo_id,
                    'source_url': repo['html_url'],
                    'title': repo['full_name'],
                    'body': (repo.get('description') or '') + '\n\n' + 
                            f"Stars: {repo['stargazers_count']} | Forks: {repo['forks_count']} | " +
                            f"Language: {repo.get('language', 'N/A')} | Created: {repo['created_at']}",
                    'author': repo['owner']['login'],
                    'score': repo['stargazers_count'],
                    'comment_count': repo.get('open_issues_count', 0),
                    'tags': repo.get('topics', []),
                    'metadata': {
                        'full_name': repo['full_name'],
                        'description': repo.get('description'),
                        'language': repo.get('language'),
                        'stars': repo['stargazers_count'],
                        'forks': repo['forks_count'],
                        'created_at': repo['created_at'],
                        'updated_at': repo['updated_at'],
                        'topics': repo.get('topics', []),
                        'is_fork': repo.get('fork', False),
                        'license': repo.get('license', {}).get('spdx_id') if repo.get('license') else None
                    }
                }
                
                relevant_repos.append(post_data)
            
            time.sleep(2)  # Respect rate limits
            
        except Exception as e:
            logger.error(f"GitHub scrape error for query '{query}': {e}")
            continue
    
    # Upsert into source_posts
    for repo in relevant_repos:
        supabase.table('source_posts').upsert(
            repo, on_conflict='source,source_id'
        ).execute()
    
    return {'source': 'github', 'repos_found': len(relevant_repos)}
```

### Unified Extraction

The existing `extract_problems()` and `extract_tool_mentions()` functions need to work on multi-source data. Instead of querying `moltbook_posts`, they query `source_posts` where `processed = false`.

The extraction prompt gets a small addition: the source context.

```python
def extract_problems_multisource(hours_back: int = 48) -> dict:
    """Extract problems from all sources."""
    cutoff = (datetime.utcnow() - timedelta(hours=hours_back)).isoformat()
    
    # Get unprocessed posts from ALL sources
    posts = supabase.table('source_posts')\
        .select('*')\
        .eq('processed', False)\
        .gte('scraped_at', cutoff)\
        .order('score', desc=True)\
        .limit(200)\
        .execute()
    
    if not posts.data:
        return {'processed': 0, 'problems': 0}
    
    # Group by source for context
    by_source = {}
    for post in posts.data:
        source = post['source']
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(post)
    
    # Format for extraction prompt — include source context
    formatted = ""
    for source, source_posts in by_source.items():
        formatted += f"\n\n=== SOURCE: {source.upper()} ===\n"
        if source == 'hackernews':
            formatted += "(Technical discussion forum — comments are the main signal)\n"
        elif source == 'github':
            formatted += "(Repository listings — descriptions and stars indicate market interest)\n"
        elif source == 'moltbook':
            formatted += "(Agent social network — direct from AI agents)\n"
        
        for post in source_posts:
            formatted += f"\n[{post['source_id']}] {post.get('title', 'Untitled')}\n"
            if post.get('body'):
                formatted += f"{post['body'][:500]}\n"
            if post.get('score'):
                formatted += f"Score/Stars: {post['score']}"
            if post.get('tags'):
                formatted += f" | Tags: {', '.join(post['tags'][:5])}"
            formatted += "\n"
    
    # Use existing extraction prompt but with source context
    result = call_openai(
        model=get_model('extraction'),
        system_prompt=EXTRACTION_PROMPT,
        user_content=formatted
    )
    
    # Store problems with source tracking
    problems_created = 0
    for problem in result.get('problems', []):
        problem['source'] = 'multi'  # or track the specific source
        store_problem(problem)
        problems_created += 1
    
    # Mark posts as processed
    for post in posts.data:
        supabase.table('source_posts').update({
            'processed': True,
            'processing_type': 'problem_extraction'
        }).eq('id', post['id']).execute()
    
    return {'processed': len(posts.data), 'problems': problems_created, 'sources': list(by_source.keys())}
```

### Cross-Source Signal Boost

The Analyst gets a powerful new signal: when the SAME problem or tool appears across multiple sources. This is strong validation.

Add to the Analyst's identity:

```
## Cross-Source Validation

When you see the same signal from multiple sources, that's significantly 
more reliable than a single-source signal:

- Problem mentioned on Moltbook AND discussed on HN = high confidence
- Tool trending on GitHub AND complained about on Moltbook = disruption signal  
- New repo on GitHub AND "Show HN" post = product launch event
- Single source only = normal confidence (note: "single source")

Always note in your reasoning: "Corroborated across N sources" or "Single source only."
```

### Scheduling

```python
# Updated scheduler
schedule.every(6).hours.do(scheduled_scrape_moltbook)
schedule.every(6).hours.do(scheduled_scrape_hackernews)    # NEW
schedule.every(12).hours.do(scheduled_scrape_github)        # NEW
schedule.every(12).hours.do(scheduled_extract_multisource)  # UPDATED
schedule.every(12).hours.do(scheduled_extract_tools_multisource)  # UPDATED
```

---

## Part 2: Prediction Tracking

### Concept

Every time the newsletter features an opportunity or emerging signal, we record a "prediction." Subsequent analysis runs check whether those predictions materialized, improved, or faded.

### How It Works

```
Week 1: Newsletter says "Agent memory tooling is an emerging opportunity (0.72)"
         → System records prediction: {what, confidence, date, source_signals}

Week 3: Analyst runs and checks:
         → Has this topic been mentioned more or less since the prediction?
         → Have new tools appeared in this space?
         → Has sentiment changed?
         → Result: "GROWING — mentions up 3x, 2 new GitHub repos, sentiment stable"

Week 5: Newsletter includes a "Prediction Tracker" section:
         "🟢 Agent Memory (predicted Week 1, confidence 0.72): CONFIRMED
          Mentions grew 3x. Two new tools launched. Market forming."
         "🟡 Protocol Bridges (predicted Week 2, confidence 0.55): DEVELOPING
          Mentions stable but GitHub activity increasing."
         "🔴 Chain Analytics (predicted Week 1, confidence 0.45): FADED
          Mentions dropped to zero after week 2. False signal."
```

### Data Model

```sql
-- Predictions table
CREATE TABLE predictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- What was predicted
    prediction_type TEXT NOT NULL,          -- 'opportunity', 'emerging_signal', 'tool_trend', 'market_shift'
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    initial_confidence FLOAT NOT NULL,      -- Original confidence score
    
    -- Source
    newsletter_edition INT,
    opportunity_id UUID REFERENCES opportunities(id),
    cluster_id UUID REFERENCES problem_clusters(id),
    
    -- Tracking
    status TEXT DEFAULT 'active',           -- 'active', 'confirmed', 'developing', 'faded', 'wrong'
    current_score FLOAT,                    -- Updated by tracking runs
    
    -- Signal history (appended by each tracking run)
    tracking_history JSONB DEFAULT '[]',    -- Array of {date, mentions, sentiment, tools, score, notes}
    
    -- Resolution
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_tracked TIMESTAMPTZ,
    metadata JSONB
);

CREATE INDEX idx_predictions_status ON predictions(status);
CREATE INDEX idx_predictions_created ON predictions(created_at DESC);
CREATE INDEX idx_predictions_type ON predictions(prediction_type);

-- RLS
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
-- Public can read predictions (they appear in the newsletter)
CREATE POLICY "Public read predictions" ON predictions FOR SELECT USING (true);
```

### Creating Predictions

When `publish_newsletter()` runs, the Processor automatically creates predictions from the featured content:

```python
def create_predictions_from_newsletter(newsletter_id: str):
    """Create trackable predictions from a published newsletter."""
    nl = supabase.table('newsletters').select('*').eq('id', newsletter_id).single().execute()
    if not nl.data:
        return
    
    data = nl.data.get('data_snapshot', {})
    edition = nl.data.get('edition_number')
    
    # Section A: Opportunities → predictions
    for opp in data.get('section_a_opportunities', [])[:5]:
        supabase.table('predictions').upsert({
            'prediction_type': 'opportunity',
            'title': opp.get('title', 'Unknown'),
            'description': opp.get('description', ''),
            'initial_confidence': opp.get('confidence_score', 0.5),
            'newsletter_edition': edition,
            'opportunity_id': opp.get('id'),
            'status': 'active',
            'current_score': opp.get('confidence_score', 0.5),
            'tracking_history': json.dumps([{
                'date': datetime.utcnow().isoformat(),
                'event': 'created',
                'confidence': opp.get('confidence_score', 0.5),
                'notes': f'Featured in edition #{edition}'
            }])
        }, on_conflict='opportunity_id').execute()
    
    # Section B: Emerging signals → predictions
    for signal in data.get('section_b_emerging', [])[:4]:
        supabase.table('predictions').insert({
            'prediction_type': 'emerging_signal',
            'title': signal.get('description', 'Unknown signal')[:100],
            'description': json.dumps(signal.get('signal_phrases', []))[:500],
            'initial_confidence': 0.3,  # Emerging signals start low
            'newsletter_edition': edition,
            'cluster_id': signal.get('cluster_id'),
            'status': 'active',
            'current_score': 0.3,
            'tracking_history': json.dumps([{
                'date': datetime.utcnow().isoformat(),
                'event': 'created',
                'confidence': 0.3,
                'notes': f'Emerging signal in edition #{edition}'
            }])
        }).execute()
    
    return {'predictions_created': True}
```

### Tracking Predictions

A weekly job (before newsletter generation) that checks the current state of each active prediction:

```python
def track_predictions() -> dict:
    """Check active predictions against current data."""
    active = supabase.table('predictions')\
        .select('*')\
        .eq('status', 'active')\
        .execute()
    
    if not active.data:
        return {'tracked': 0}
    
    tracked = 0
    
    for pred in active.data:
        # Gather current signals for this prediction
        signals = gather_prediction_signals(pred)
        
        # Determine new status
        new_status, new_score, notes = evaluate_prediction(pred, signals)
        
        # Append to tracking history
        history = json.loads(pred.get('tracking_history', '[]'))
        history.append({
            'date': datetime.utcnow().isoformat(),
            'event': 'tracked',
            'mentions_this_week': signals.get('mentions_7d', 0),
            'mentions_total': signals.get('mentions_total', 0),
            'sentiment': signals.get('avg_sentiment', 0),
            'new_tools': signals.get('new_tools', []),
            'github_repos': signals.get('github_repos', 0),
            'score': new_score,
            'notes': notes
        })
        
        update = {
            'current_score': new_score,
            'tracking_history': json.dumps(history, default=str),
            'last_tracked': datetime.utcnow().isoformat()
        }
        
        if new_status != pred['status']:
            update['status'] = new_status
            if new_status in ('confirmed', 'faded', 'wrong'):
                update['resolved_at'] = datetime.utcnow().isoformat()
                update['resolution_notes'] = notes
        
        supabase.table('predictions').update(update).eq('id', pred['id']).execute()
        tracked += 1
    
    return {'tracked': tracked}


def gather_prediction_signals(pred: dict) -> dict:
    """Gather current data about a prediction's topic."""
    title = pred['title'].lower()
    keywords = title.split()[:3]  # Simple keyword match
    
    # Check recent mentions across sources
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    
    # Problems mentioning this topic
    # (simplified — could use full-text search for better matching)
    recent_problems = supabase.table('problems')\
        .select('*')\
        .gte('last_seen', week_ago)\
        .execute()
    
    matching_problems = [p for p in (recent_problems.data or [])
                        if any(kw in (p.get('description', '') + p.get('title', '')).lower() 
                              for kw in keywords)]
    
    # Tool mentions
    recent_tools = supabase.table('tool_mentions')\
        .select('*')\
        .gte('mentioned_at', week_ago)\
        .execute()
    
    matching_tools = [t for t in (recent_tools.data or [])
                     if any(kw in t.get('tool_name', '').lower() for kw in keywords)]
    
    # GitHub repos (from source_posts)
    github_posts = supabase.table('source_posts')\
        .select('*')\
        .eq('source', 'github')\
        .gte('scraped_at', week_ago)\
        .execute()
    
    matching_github = [g for g in (github_posts.data or [])
                      if any(kw in (g.get('title', '') + g.get('body', '')).lower()
                            for kw in keywords)]
    
    return {
        'mentions_7d': len(matching_problems),
        'mentions_total': len(matching_problems),  # Would need historical query
        'avg_sentiment': sum(t.get('sentiment_score', 0) for t in matching_tools) / max(len(matching_tools), 1),
        'new_tools': [t['tool_name'] for t in matching_tools[:5]],
        'github_repos': len(matching_github),
        'github_stars': sum(g.get('score', 0) for g in matching_github)
    }


def evaluate_prediction(pred: dict, signals: dict) -> tuple:
    """Evaluate a prediction's status based on current signals.
    
    Returns: (new_status, new_score, notes)
    """
    initial = pred['initial_confidence']
    current = pred.get('current_score', initial)
    weeks_active = (datetime.utcnow() - datetime.fromisoformat(
        pred['created_at'].replace('Z', '+00:00')
    ).replace(tzinfo=None)).days / 7
    
    mentions = signals.get('mentions_7d', 0)
    github = signals.get('github_repos', 0)
    sentiment = signals.get('avg_sentiment', 0)
    
    # Scoring logic
    if mentions >= 5 and github >= 2:
        new_score = min(current + 0.15, 1.0)
        notes = f"Strong signals: {mentions} mentions, {github} GitHub repos"
        status = 'confirmed' if new_score >= 0.8 else 'active'
    elif mentions >= 2 or github >= 1:
        new_score = min(current + 0.05, 1.0)
        notes = f"Developing: {mentions} mentions, {github} GitHub repos"
        status = 'active'
    elif mentions == 0 and weeks_active >= 3:
        new_score = max(current - 0.2, 0)
        notes = f"No mentions for 3+ weeks"
        status = 'faded' if new_score < 0.2 else 'active'
    elif mentions == 0 and weeks_active >= 1:
        new_score = max(current - 0.1, 0)
        notes = f"Quiet week — no new mentions"
        status = 'active'
    else:
        new_score = current
        notes = f"Stable: {mentions} mentions"
        status = 'active'
    
    return (status, round(new_score, 2), notes)
```

### Newsletter Section: Prediction Tracker

Add a new section to the newsletter between "Tool Radar" and "Gato's Corner":

```
## Prediction Tracker

🟢 CONFIRMED
Agent Memory Tooling (Edition #3, initial confidence 0.72)
  Now: 0.91 — 15 mentions this month, 4 new GitHub repos, 2 product launches.
  This one landed.

🟡 DEVELOPING
Protocol Bridges (Edition #5, initial confidence 0.55)
  Now: 0.60 — Mentions stable, 1 new repo. Worth watching.

🔴 FADED
Chain Analytics (Edition #3, initial confidence 0.45)
  Now: 0.15 — Zero mentions since week 2. We got this one wrong.
```

The Newsletter agent receives prediction data in its data package and writes this section. The voice should be honest — celebrate correct calls, acknowledge wrong ones. This builds trust.

### Updated Newsletter Data Package

`prepare_newsletter_data()` adds:

```python
# Prediction tracking data
active_predictions = supabase.table('predictions')\
    .select('*')\
    .in_('status', ['active', 'confirmed', 'faded'])\
    .order('current_score', desc=True)\
    .limit(10)\
    .execute()

# Add to input_data
'predictions': active_predictions.data or [],
```

### Scheduling

```python
# Add to scheduler — track predictions before newsletter generation
schedule.every().monday.at("06:30").do(track_predictions)
# Newsletter data gathered at 07:00, so predictions are fresh
```

---

## Updated Pipeline After Phase 4

```
Every 6h:   Scrape Moltbook
Every 6h:   Scrape Hacker News (NEW)
Every 12h:  Scrape GitHub (NEW)
Every 12h:  Extract problems (multi-source) → Cluster → Extract tools (multi-source)
Every 12h:  Extract trending topics (multi-source)
Every 12h:  Delegate full analysis to Analyst
Every 60m:  Proactive anomaly scan
Daily 6am:  Update tool stats
Daily 9am:  Send opportunity digest

Weekly Monday:
  6:30am  Track predictions (NEW)
  7:00am  Prepare newsletter data (includes predictions)
  7:01am  Newsletter agent writes brief (includes Prediction Tracker section)
  8:00am  Notify newsletter ready
```

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/predictions` (NEW) | Show active predictions with current status |
| `/predict [topic]` (NEW) | Manually add a prediction to track |
| `/sources` (NEW) | Show scraping status per source (last scrape, post counts) |

---

## Implementation Sequence

```
Prompt 1: Database schema (source_posts, predictions tables, ALTER existing tables)
Prompt 2: HN scraper
Prompt 3: GitHub scraper
Prompt 4: Multi-source extraction (update extract_problems, extract_tools)
Prompt 5: Prediction creation (from newsletter publish)
Prompt 6: Prediction tracking (weekly evaluation)
Prompt 7: Update newsletter data package + agent identity for new sections
Prompt 8: Update Analyst identity for cross-source validation
Prompt 9: Scheduling updates
Prompt 10: Wire Telegram commands (/predictions, /sources)
```
