# AgentPulse Phase 5: Editorial Intelligence

**Date:** February 19, 2026  
**Goal:** Make the newsletter feel like it's written by a sharp analyst with strong opinions, not a summarization bot

---

## Three Problems, One Solution

These three features are deeply connected:

1. **Premium sources** → gives the Analyst higher-quality input to form opinions from
2. **Anti-repetition** → forces the system to find new angles even on recurring topics
3. **Insight generation** → turns pattern recognition across time into forward-looking theses

Together they create **editorial intelligence**: the system doesn't just report what happened — it interprets what it means and where it's going.

---

## Part 1: Premium Source Integration

### Source Tier System

Not all sources are equal. Introduce a tiered weighting system:

| Tier | Sources | Weight | Why |
|------|---------|--------|-----|
| Tier 1: Authority | HBR, BCG, McKinsey, Sequoia, a16z blogs | 3x | Edited, researched, institutional credibility |
| Tier 2: Curated | TLDR AI, TLDR Founders, The Batch (Andrew Ng), Ben's Bites, Import AI | 2x | Human-curated newsletters with editorial judgment |
| Tier 3: Community | Hacker News, Moltbook | 1x | Raw community signal, high volume, lower per-post quality |
| Tier 4: Code | GitHub | 1x (but different signal type) | Actions not words — code is commitment |

The weight multiplier affects how the Analyst values signals from each source. A single BCG article mentioning agent memory is worth as much as 3 Moltbook posts on the same topic.

### RSS Feed Architecture

Most premium sources have RSS feeds. No scraping headaches, no API keys, no rate limits.

```
RSS Feeds to monitor:
  TLDR AI:          https://tldr.tech/ai/rss
  TLDR Founders:    https://tldr.tech/founders/rss
  Ben's Bites:      https://bensbites.beehiiv.com/feed
  Import AI:        https://importai.substack.com/feed
  The Batch:        https://www.deeplearning.ai/the-batch/feed/
  a16z blog:        https://a16z.com/feed/
  Sequoia blog:     https://www.sequoiacap.com/feed/
  HBR (tech):       https://hbr.org/topic/technology/feed
  MIT Tech Review:  https://www.technologyreview.com/feed/
```

### RSS Scraper

```python
def scrape_rss_feeds() -> dict:
    """Scrape premium RSS feeds for agent/AI relevant content."""
    import feedparser  # pip install feedparser
    
    FEEDS = {
        'tldr_ai': {
            'url': 'https://tldr.tech/ai/rss',
            'tier': 2,
            'category': 'curated_newsletter'
        },
        'tldr_founders': {
            'url': 'https://tldr.tech/founders/rss', 
            'tier': 2,
            'category': 'curated_newsletter'
        },
        'bens_bites': {
            'url': 'https://bensbites.beehiiv.com/feed',
            'tier': 2,
            'category': 'curated_newsletter'
        },
        'a16z': {
            'url': 'https://a16z.com/feed/',
            'tier': 1,
            'category': 'authority'
        },
        'hbr_tech': {
            'url': 'https://hbr.org/topic/technology/feed',
            'tier': 1,
            'category': 'authority'
        },
        'mit_tech_review': {
            'url': 'https://www.technologyreview.com/feed/',
            'tier': 1,
            'category': 'authority'
        },
    }
    
    results = {}
    
    for feed_name, feed_config in FEEDS.items():
        try:
            feed = feedparser.parse(feed_config['url'])
            relevant = []
            
            for entry in feed.entries[:30]:
                title = (entry.get('title') or '').lower()
                summary = (entry.get('summary') or '').lower()
                combined = title + ' ' + summary
                
                # Relevance check — broader than HN since these are pre-curated
                if any(kw in combined for kw in [
                    'agent', 'agentic', 'llm', 'ai tool', 'autonomous',
                    'multi-agent', 'function call', 'ai startup',
                    'foundation model', 'gpt', 'claude', 'anthropic',
                    'openai', 'copilot', 'automation', 'ai infrastructure',
                    'rag', 'vector', 'embedding', 'mcp', 'langchain'
                ]):
                    post_data = {
                        'source': f'rss_{feed_name}',
                        'source_id': entry.get('id') or entry.get('link', ''),
                        'source_url': entry.get('link', ''),
                        'title': entry.get('title', ''),
                        'body': entry.get('summary', '')[:1000],  # RSS summaries, not full articles
                        'author': entry.get('author', feed_name),
                        'score': feed_config['tier'],  # Use tier as score weight
                        'comment_count': 0,
                        'tags': [feed_config['category'], f'tier_{feed_config["tier"]}'],
                        'metadata': {
                            'feed_name': feed_name,
                            'tier': feed_config['tier'],
                            'category': feed_config['category'],
                            'published': entry.get('published', ''),
                            'feed_url': feed_config['url']
                        }
                    }
                    relevant.append(post_data)
            
            # Upsert
            for post in relevant:
                supabase.table('source_posts').upsert(
                    post, on_conflict='source,source_id'
                ).execute()
            
            results[feed_name] = len(relevant)
            
        except Exception as e:
            logger.error(f"RSS scrape error for {feed_name}: {e}")
            results[feed_name] = f"error: {e}"
    
    return {'source': 'rss', 'feeds_scraped': len(FEEDS), 'results': results}
```

### Source Weight in Extraction

When the multi-source extraction runs, it now includes tier information:

```
=== SOURCE: RSS_A16Z (TIER 1 — AUTHORITY) ===
(Institutional research and analysis. Single mention here = high signal.)

=== SOURCE: RSS_TLDR_AI (TIER 2 — CURATED) ===
(Human-curated AI newsletter. Pre-filtered for relevance.)

=== SOURCE: HACKERNEWS (TIER 3 — COMMUNITY) ===
(Technical discussion forum. Volume is high, per-post signal varies.)
```

### Analyst Weight Awareness

Add to Analyst identity:

```
## Source Weighting

Not all sources carry equal weight:

- Tier 1 (HBR, BCG, a16z, MIT): A single mention here is a strong signal.
  These are edited, researched publications. If they're writing about a topic,
  it's past the "is this real?" phase.

- Tier 2 (TLDR, Ben's Bites): Human-curated. Pre-filtered for relevance.
  A mention here means someone with editorial judgment thought it mattered.

- Tier 3 (HN, Moltbook): Raw community signal. Individual posts are noisy,
  but patterns across many posts are meaningful.

- Tier 4 (GitHub): Code is commitment. A trending repo is stronger than 
  100 discussion posts because someone invested real time building it.

When scoring opportunities and forming insights, weight your evidence:
- "Featured in a16z blog" > "50 Moltbook mentions"
- "3 Tier 1 sources discussing this" = near-certain market signal
- "Only seen on Moltbook" = flag as single-source, lower confidence
```

### Database Changes

```sql
-- Add tier tracking to source_posts
ALTER TABLE source_posts ADD COLUMN IF NOT EXISTS source_tier INT DEFAULT 3;
CREATE INDEX IF NOT EXISTS idx_source_posts_tier ON source_posts(source_tier);

-- Add source tier to problems for weighted scoring
ALTER TABLE problems ADD COLUMN IF NOT EXISTS max_source_tier INT DEFAULT 3;
```

---

## Part 2: Anti-Repetition System

### The Problem

The staleness penalty from Phase 3 reduces scores of repeated opportunities, but it's not enough. The newsletter still gravitates toward the same topics because:

1. High-frequency topics keep generating new mentions (so staleness resets)
2. The system optimizes for "strongest signal" not "most interesting to read"
3. There's no concept of "the reader already knows about this"

### The Solution: Editorial Freshness Rules

Three mechanisms working together:

#### Mechanism 1: Hard Exclusion Window

If an opportunity was the lead story (Section A, position 1-2) in the last 2 editions, it CANNOT appear in Section A of the next edition. Period. No score override.

```python
def get_excluded_opportunity_ids(editions_back: int = 2) -> set:
    """Get opportunity IDs that were featured prominently in recent editions."""
    recent = supabase.table('newsletters')\
        .select('data_snapshot')\
        .eq('status', 'published')\
        .order('edition_number', desc=True)\
        .limit(editions_back)\
        .execute()
    
    excluded = set()
    for nl in (recent.data or []):
        snapshot = nl.get('data_snapshot', {})
        # Top 2 from Section A are excluded
        for opp in (snapshot.get('section_a_opportunities') or [])[:2]:
            if opp.get('id'):
                excluded.add(opp['id'])
    
    return excluded
```

#### Mechanism 2: Angle Requirement

When an opportunity appears again, it MUST have a new angle. The Newsletter agent gets explicit instructions:

```
If an opportunity appeared in a previous edition, you may ONLY include it if:
1. There is genuinely new data (new source, new signals, score change)
2. You frame it from a DIFFERENT angle than last time
3. You explicitly state what's new: "Previously covered in Edition #N. 
   Since then: [specific new development]."

If you can't articulate what's new in one sentence, skip it.
```

#### Mechanism 3: Diversity Quota

The newsletter MUST include minimum diversity:

```
Section A (Top Opportunities):
  - Max 2 returning items (must have new angle)
  - Min 1 item that has NEVER appeared before
  - Max 5 items total

Section B (Emerging Signals):
  - ALL items must be new (never appeared in any previous edition)
  - If no new signals exist, section is shorter — that's OK

Section C (Curious Corner):
  - ALL items must be new
  - No exceptions
```

### Implementation

Update `prepare_newsletter_data()`:

```python
def prepare_newsletter_data():
    # ... existing code ...
    
    # Get exclusion list
    excluded_ids = get_excluded_opportunity_ids(editions_back=2)
    
    # Section A: Apply hard exclusion + diversity
    all_opps = # ... fetch and score as before ...
    
    # Split into new vs returning
    never_featured = [o for o in all_opps if o.get('newsletter_appearances', 0) == 0]
    previously_featured = [o for o in all_opps 
                          if o.get('newsletter_appearances', 0) > 0 
                          and o.get('id') not in excluded_ids]
    
    # Apply diversity quota
    section_a = []
    # At least 1 new item (ideally lead with it)
    section_a.extend(never_featured[:3])
    # Up to 2 returning items with new data
    returning_with_new_data = [o for o in previously_featured 
                               if o.get('last_reviewed_at') and o.get('last_featured_at')
                               and o['last_reviewed_at'] > o['last_featured_at']]
    section_a.extend(returning_with_new_data[:2])
    # Sort by effective score
    section_a.sort(key=lambda x: x.get('effective_score', 0), reverse=True)
    section_a = section_a[:5]
    
    # Section B: ONLY new signals
    emerging = # ... fetch as before ...
    # Filter out anything that appeared in previous newsletters
    featured_titles = get_previously_featured_titles(editions_back=4)
    emerging = [s for s in emerging if s.get('description', '')[:50] not in featured_titles]
    
    # Section C: ONLY new trending topics
    # Already filtered by featured_in_newsletter=false
    
    # Include freshness metadata for the Newsletter agent
    input_data['freshness_rules'] = {
        'excluded_opportunity_ids': list(excluded_ids),
        'max_returning_items_section_a': 2,
        'min_new_items_section_a': 1,
        'section_b_new_only': True,
        'section_c_new_only': True
    }
```

### Newsletter Agent Instructions

Add to IDENTITY.md:

```
## Freshness Rules (NON-NEGOTIABLE)

These rules prevent the newsletter from feeling repetitive:

1. HARD EXCLUSION: Opportunities listed in freshness_rules.excluded_opportunity_ids
   CANNOT appear in Section A. The system already filtered these out — if they somehow
   appear in your data, skip them.

2. RETURNING ITEMS: Maximum 2 returning opportunities in Section A. Each MUST:
   - Have a genuinely new angle (new data, new source, score change)
   - State explicitly what's new: "Since we last covered this: [new development]"
   - If you can't say what's new in one sentence, drop it

3. NEW ITEMS: At least 1 opportunity in Section A must be brand new (never featured).
   Lead with fresh content when possible — returning items support, they don't lead.

4. SECTIONS B & C: Everything must be new. No exceptions. If there aren't enough
   new items, make the section shorter rather than recycling old content.

5. GENERAL: Never use the same cold open structure two editions in a row.
   Never lead with the same topic two editions in a row.
   If you catch yourself writing something that sounds like last week: stop and find a new angle.
```

---

## Part 3: Insight Generation

### What "Insights" Actually Means

There are three levels of analytical output:

1. **Observation:** "Agent memory was discussed 15 times this week" ← you already have this
2. **Analysis:** "Agent memory discussions shifted from 'is this needed?' to 'which solution?'" ← cross-referencing signals
3. **Insight:** "Agent memory is following the same adoption curve as container orchestration in 2015. Based on signal trajectory, expect a dominant framework to emerge within 3 months. The winner will likely be the one that solves persistence across sessions, which is the unsolved pain point in 73% of complaints." ← original thinking based on patterns

Level 3 is what makes a newsletter worth reading. It requires:
- **Temporal awareness:** seeing how topics evolve across weeks/months
- **Pattern matching:** recognizing structural similarities to past market developments
- **Thesis formation:** taking a position on what happens next
- **Honest uncertainty:** being clear about what's speculation vs data

### Temporal Analysis Engine

The Analyst needs a "memory" of how topics evolved. This isn't just prediction tracking (which tracks individual calls) — it's tracking the shape of conversation over time.

```sql
-- Topic evolution tracking
CREATE TABLE topic_evolution (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_key TEXT NOT NULL,                -- normalized topic identifier
    
    -- Weekly snapshots (appended each analysis run)
    snapshots JSONB DEFAULT '[]',           -- Array of weekly {date, mentions, sentiment, sources, key_phrases, stage}
    
    -- Current assessment
    current_stage TEXT,                     -- 'emerging', 'debating', 'building', 'consolidating', 'mature', 'declining'
    stage_changed_at TIMESTAMPTZ,
    
    -- Analyst thesis
    thesis TEXT,                            -- Current analytical position
    thesis_confidence FLOAT,
    thesis_updated_at TIMESTAMPTZ,
    
    -- Connections
    related_topics TEXT[],
    related_opportunity_ids UUID[],
    
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX idx_topic_evolution_key ON topic_evolution(topic_key);
CREATE INDEX idx_topic_evolution_stage ON topic_evolution(current_stage);
```

### Topic Lifecycle Stages

```
EMERGING     → First mentions. Few sources. Vague language.
               "Some people are starting to talk about X"

DEBATING     → Growing mentions. Multiple viewpoints. Questions forming.
               "The community is divided on whether X matters"

BUILDING     → GitHub repos appearing. Tools being built. Solutions proposed.
               "People aren't just talking about X — they're building for it"

CONSOLIDATING → Fewer but more specific mentions. Winners emerging.
               "The market is converging on Y as the approach for X"

MATURE       → Established. Mentions stabilize. New entrants harder.
               "X is now table stakes. The interesting question is what's next"

DECLINING    → Falling mentions. Being replaced or absorbed.
               "X is being overtaken by Z. Last month's 20 mentions are now 3"
```

### How Topic Evolution Works

Weekly (before newsletter generation), the Processor snapshots each active topic:

```python
def update_topic_evolution() -> dict:
    """Update topic evolution tracking with latest weekly data."""
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    
    # Get current problem clusters as topic proxies
    clusters = supabase.table('problem_clusters')\
        .select('*')\
        .order('opportunity_score', desc=True)\
        .limit(30)\
        .execute()
    
    updated = 0
    
    for cluster in (clusters.data or []):
        topic_key = normalize_topic_key(cluster['theme'])
        
        # Gather this week's signals
        mentions = count_mentions_for_topic(topic_key, days=7)
        sentiment = avg_sentiment_for_topic(topic_key, days=7)
        sources = unique_sources_for_topic(topic_key, days=7)
        github_activity = github_repos_for_topic(topic_key, days=7)
        
        snapshot = {
            'date': datetime.utcnow().isoformat(),
            'mentions': mentions,
            'sentiment': round(sentiment, 2),
            'sources': sources,
            'source_count': len(sources),
            'github_repos': github_activity,
            'key_phrases': extract_key_phrases(topic_key, days=7)
        }
        
        # Upsert topic evolution
        existing = supabase.table('topic_evolution')\
            .select('*')\
            .eq('topic_key', topic_key)\
            .execute()
        
        if existing.data:
            # Append snapshot to history
            topic = existing.data[0]
            snapshots = json.loads(topic.get('snapshots', '[]'))
            snapshots.append(snapshot)
            # Keep last 12 weeks
            snapshots = snapshots[-12:]
            
            # Detect stage
            stage = detect_topic_stage(snapshots)
            
            update = {
                'snapshots': json.dumps(snapshots, default=str),
                'last_updated': datetime.utcnow().isoformat()
            }
            
            if stage != topic.get('current_stage'):
                update['current_stage'] = stage
                update['stage_changed_at'] = datetime.utcnow().isoformat()
            
            supabase.table('topic_evolution').update(update)\
                .eq('id', topic['id']).execute()
        else:
            # New topic
            supabase.table('topic_evolution').insert({
                'topic_key': topic_key,
                'snapshots': json.dumps([snapshot], default=str),
                'current_stage': 'emerging',
                'related_opportunity_ids': [cluster.get('id')],
                'first_seen': datetime.utcnow().isoformat(),
                'last_updated': datetime.utcnow().isoformat()
            }).execute()
        
        updated += 1
    
    return {'topics_updated': updated}


def detect_topic_stage(snapshots: list) -> str:
    """Determine topic lifecycle stage from snapshot history."""
    if len(snapshots) < 2:
        return 'emerging'
    
    recent = snapshots[-1]
    previous = snapshots[-2] if len(snapshots) >= 2 else None
    oldest = snapshots[0]
    
    mentions_trend = [s.get('mentions', 0) for s in snapshots]
    source_counts = [s.get('source_count', 0) for s in snapshots]
    github_trend = [s.get('github_repos', 0) for s in snapshots]
    
    recent_mentions = recent.get('mentions', 0)
    avg_mentions = sum(mentions_trend) / len(mentions_trend) if mentions_trend else 0
    max_mentions = max(mentions_trend) if mentions_trend else 0
    recent_github = recent.get('github_repos', 0)
    recent_sources = recent.get('source_count', 0)
    
    # Declining: mentions dropping consistently
    if len(snapshots) >= 3:
        last_three = mentions_trend[-3:]
        if all(last_three[i] >= last_three[i+1] for i in range(len(last_three)-1)) and recent_mentions < avg_mentions * 0.5:
            return 'declining'
    
    # Mature: stable mentions, no growth
    if len(snapshots) >= 4:
        variance = max(mentions_trend[-4:]) - min(mentions_trend[-4:])
        if variance < avg_mentions * 0.3 and recent_mentions > 5:
            return 'mature'
    
    # Consolidating: mentions decreasing but GitHub increasing
    if recent_github > 0 and recent_mentions < avg_mentions and recent_sources >= 2:
        return 'consolidating'
    
    # Building: GitHub repos appearing
    if recent_github > 0 and sum(github_trend) > 0:
        return 'building'
    
    # Debating: growing mentions, multiple sources
    if recent_mentions > avg_mentions and recent_sources >= 2:
        return 'debating'
    
    return 'emerging'
```

### Insight Generation: The Analyst's Thesis Engine

The Analyst doesn't just report — it forms theses. This happens during `full_analysis` when topic evolution data is available.

Add to the Analyst's data package:

```python
# In prepare_analysis_package():
topic_evolution = supabase.table('topic_evolution')\
    .select('*')\
    .order('last_updated', desc=True)\
    .limit(20)\
    .execute()

data_package['topic_evolution'] = topic_evolution.data or []
```

Add to the Analyst's identity:

```markdown
## Insight Generation

You don't just report signals — you interpret them. When you receive topic_evolution
data, you can see how topics have developed over weeks. Use this to form theses.

### How to Form a Thesis

1. Look at the evolution snapshots. What stage is this topic in?
2. Is there a historical parallel? (e.g., "This looks like the containerization debate
   of 2015 — lots of competing approaches, about to consolidate")
3. What would need to happen for this to progress to the next stage?
4. What's the most likely outcome? Why?
5. What would change your mind?

### Thesis Format

For each major insight, provide:
- **Thesis:** One clear sentence stating your position
- **Evidence:** 2-3 specific data points supporting it
- **Confidence:** 0.0-1.0 with explanation
- **Timeframe:** When you expect this to play out
- **Counter-argument:** The strongest case against your thesis
- **What would change your mind:** Specific observable events

Example:
"Thesis: Agent memory persistence will consolidate around 2-3 major frameworks
within 3 months. Evidence: Topic moved from 'emerging' to 'building' in 4 weeks,
3 GitHub repos with >500 stars each appeared, and HN discussion shifted from
'should we do this?' to 'which approach is best?' Confidence: 0.65. Timeframe:
Q2 2026. Counter: The problem may be too tightly coupled to specific LLM providers
to allow a general framework. Would change my mind: If major LLM providers release
built-in memory features, making third-party frameworks unnecessary."

### Rules for Insights

- Every thesis must cite specific evidence from the data
- Never present speculation as fact
- Always include uncertainty and counter-arguments
- Track your theses over time — the prediction system will hold you accountable
- It's better to have 1 well-reasoned insight than 5 vague observations
- If the data doesn't support forming a thesis, say so: "Not enough signal yet to
  form a view. Watching for: [specific things]"
```

### Newsletter Section: Insights

Replace "The Big Story" with a richer section:

```
## The Big Insight

Not just "what happened" but "what it means."

This is the section that makes the newsletter worth reading. One major
thesis per edition, supported by evidence from multiple sources and
temporal analysis.

Structure:
1. The thesis (bold, one sentence)
2. The evidence trail (how did we get here? What evolved?)
3. What happens next (specific prediction with timeframe)
4. The counter-argument (the strongest case against)
5. What we're watching (specific signals that would confirm or refute)

Example:
"**The agent memory market is about to consolidate.**

Four weeks ago, 'memory persistence' was a scattered complaint across
Moltbook. Two weeks ago, three GitHub repos appeared with competing
approaches. This week, a16z published a deep dive on agent memory
architectures, and HN debated the merits of each approach for 200+ comments.

This is the classic build → debate → consolidate cycle. Based on signal
trajectory, we expect a dominant approach to emerge by Q2 2026. The winner
will likely solve cross-session persistence — the unsolved pain in 73% of
memory-related complaints.

The counter-argument: LLM providers might ship native memory, making
third-party solutions irrelevant. We'd change our view if OpenAI or
Anthropic announce built-in persistent memory in the next month.

Tracking this as a prediction. Initial confidence: 0.65."
```

---

## Updated Newsletter Structure

```
1. Cold open (one sentence hook — never repeat structure from last edition)
2. The Big Insight (thesis + evidence + prediction — NEW, replaces Big Story)
3. Top Opportunities (Section A — max 2 returning, min 1 new)
4. Emerging Signals (Section B — all new, always)
5. The Curious Corner (Section C — all new, always)
6. Tool Radar (what's rising/falling)
7. Prediction Tracker (🟢🟡🔴 from Phase 4)
8. Gato's Corner (can riff on the Big Insight too)
9. By the Numbers
```

---

## Database Changes Summary

```sql
-- Source tiers
ALTER TABLE source_posts ADD COLUMN IF NOT EXISTS source_tier INT DEFAULT 3;
CREATE INDEX IF NOT EXISTS idx_source_posts_tier ON source_posts(source_tier);

-- Topic evolution
CREATE TABLE topic_evolution (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_key TEXT NOT NULL,
    snapshots JSONB DEFAULT '[]',
    current_stage TEXT,
    stage_changed_at TIMESTAMPTZ,
    thesis TEXT,
    thesis_confidence FLOAT,
    thesis_updated_at TIMESTAMPTZ,
    related_topics TEXT[],
    related_opportunity_ids UUID[],
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX idx_topic_evolution_key ON topic_evolution(topic_key);
CREATE INDEX idx_topic_evolution_stage ON topic_evolution(current_stage);

-- RLS
ALTER TABLE topic_evolution ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read topic evolution" ON topic_evolution FOR SELECT USING (true);

-- Source weight on problems
ALTER TABLE problems ADD COLUMN IF NOT EXISTS max_source_tier INT DEFAULT 3;
```

---

## Scheduling Update

```
Every 6h:   Scrape Moltbook
Every 6h:   Scrape Hacker News
Every 6h:   Scrape RSS feeds (NEW — premium sources)
Every 12h:  Scrape GitHub
Every 12h:  Multi-source extraction (problems, tools, trending topics)
Every 12h:  Delegate full analysis to Analyst (now includes topic evolution data)
Every 60m:  Proactive anomaly scan

Weekly Monday:
  6:00am  Update topic evolution snapshots (NEW)
  6:30am  Track predictions
  7:00am  Prepare newsletter data (includes evolution + freshness rules)
  7:01am  Newsletter agent writes (with Big Insight + anti-repetition rules)
  8:00am  Notify ready
```

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/topics` (NEW) | Show topic evolution stages (emerging → building → etc) |
| `/thesis [topic]` (NEW) | Show the Analyst's current thesis on a topic |
| `/freshness` (NEW) | Show what's excluded from next newsletter |

---

## Implementation Sequence

```
Prompt 1:  Database schema (source_tier, topic_evolution table)
Prompt 2:  RSS feed scraper + feedparser dependency
Prompt 3:  Source tier weighting in extraction
Prompt 4:  Anti-repetition system (exclusion, diversity quota, freshness rules)
Prompt 5:  Topic evolution tracking (snapshots, stage detection)
Prompt 6:  Insight generation in Analyst identity
Prompt 7:  Newsletter identity update (Big Insight, freshness rules, new structure)
Prompt 8:  Update prepare_newsletter_data for evolution + freshness
Prompt 9:  Scheduling updates
Prompt 10: Wire Telegram commands (/topics, /thesis, /freshness)
```
