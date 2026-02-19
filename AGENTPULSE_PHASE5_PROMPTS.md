# AgentPulse Phase 5: Editorial Intelligence — Cursor Prompts

> **Upload `AGENTPULSE_PHASE5_EDITORIAL.md` as context for every prompt.**

---

## Parallel Execution Map

```
Round 1 (sequential — everything depends on this):
  Prompt 1: SQL schema

Round 2 (parallel — independent additions):
  Agent A: Prompt 2 (RSS scraper)
  Agent B: Prompt 3 (source tier weighting)
  Agent C: Prompt 5 (topic evolution tracking)

Round 3 (parallel — depend on Round 2 being done):
  Agent A: Prompt 4 (anti-repetition) — needs Prompt 3's tier concept
  Agent B: Prompt 6 (analyst identity) — needs Prompt 5's topic evolution concept
  Agent C: Prompt 7 (newsletter identity) — independent file edit

Round 4 (sequential — references many prior changes):
  Prompt 8 (prepare_newsletter_data update) — needs 4, 5

Round 5 (parallel — wiring):
  Agent A: Prompt 9 (scheduling)
  Agent B: Prompt 10 (Telegram commands)
```

**Conflict warning:** Prompts 2, 3, 4, 5, 8, 9 all edit `agentpulse_processor.py`. If running in parallel, stagger agents that touch this file. Prompts 6 and 7 only edit identity templates (safe in parallel with everything).

---

## Prompt 1: Database Schema

Run in Supabase SQL Editor:

```sql
-- ================================================
-- PHASE 5: EDITORIAL INTELLIGENCE
-- ================================================

-- 1. Source tiers
ALTER TABLE source_posts ADD COLUMN IF NOT EXISTS source_tier INT DEFAULT 3;
CREATE INDEX IF NOT EXISTS idx_source_posts_tier ON source_posts(source_tier);

-- 2. Source weight on problems
ALTER TABLE problems ADD COLUMN IF NOT EXISTS max_source_tier INT DEFAULT 3;

-- 3. Topic evolution tracking
CREATE TABLE topic_evolution (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_key TEXT NOT NULL,
    snapshots JSONB DEFAULT '[]',
    current_stage TEXT DEFAULT 'emerging',
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_topic_evolution_key ON topic_evolution(topic_key);
CREATE INDEX IF NOT EXISTS idx_topic_evolution_stage ON topic_evolution(current_stage);

-- 4. RLS
ALTER TABLE topic_evolution ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read topic evolution" ON topic_evolution FOR SELECT USING (true);
```

**Verify:** Check `topic_evolution` table exists. Check `source_posts` has `source_tier` column.

---

## Prompt 2: RSS Feed Scraper

```
Add an RSS feed scraper for premium sources to docker/processor/agentpulse_processor.py.

Reference: AGENTPULSE_PHASE5_EDITORIAL.md, "RSS Feed Architecture" and "RSS Scraper" sections.

1. Add 'feedparser' to docker/processor/requirements-agentpulse.txt (or whichever requirements file the processor uses):
   feedparser>=6.0.0

2. Add a RSS_FEEDS constant near the top of the file:
   RSS_FEEDS = {
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

3. Add RSS_RELEVANCE_KEYWORDS constant:
   RSS_RELEVANCE_KEYWORDS = [
       'agent', 'agentic', 'llm', 'ai tool', 'autonomous',
       'multi-agent', 'function call', 'ai startup',
       'foundation model', 'gpt', 'claude', 'anthropic',
       'openai', 'copilot', 'automation', 'ai infrastructure',
       'rag', 'vector', 'embedding', 'mcp', 'langchain'
   ]

4. Add scrape_rss_feeds() function:
   - Imports feedparser
   - Iterates over RSS_FEEDS
   - For each feed: parse with feedparser, take first 30 entries
   - For each entry: check relevance by searching title + summary (lowercased) for any RSS_RELEVANCE_KEYWORDS
   - For relevant entries, build post_data:
     {
       'source': f'rss_{feed_name}',
       'source_id': entry.get('id') or entry.get('link', ''),
       'source_url': entry.get('link', ''),
       'title': entry.get('title', ''),
       'body': entry.get('summary', '')[:1000],
       'author': entry.get('author', feed_name),
       'score': feed_config['tier'],
       'comment_count': 0,
       'tags': [feed_config['category'], f"tier_{feed_config['tier']}"],
       'source_tier': feed_config['tier'],
       'metadata': {
         'feed_name': feed_name,
         'tier': feed_config['tier'],
         'category': feed_config['category'],
         'published': entry.get('published', ''),
         'feed_url': feed_config['url']
       }
     }
   - Upsert each into source_posts (on_conflict='source,source_id')
   - Wrap each feed in try/except so one broken feed doesn't stop the others
   - Log pipeline start/end
   - Return {'source': 'rss', 'feeds_scraped': N, 'results': {feed_name: count, ...}}

5. Add 'scrape_rss' to execute_task():
   elif task_type == 'scrape_rss':
       return scrape_rss_feeds()

6. Add 'scrape_rss' to argparse choices.

Don't modify any existing functions.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task scrape_rss
# Check Supabase: source_posts should have rows with source like 'rss_tldr_ai', 'rss_a16z', etc.
```

---

## Prompt 3: Source Tier Weighting in Extraction

```
Update the multi-source extraction to include source tier information so the Analyst can weight evidence by authority.

Reference: AGENTPULSE_PHASE5_EDITORIAL.md, "Source Weight in Extraction" section.

Changes to docker/processor/agentpulse_processor.py:

1. Add a SOURCE_DESCRIPTIONS constant:
   SOURCE_DESCRIPTIONS = {
       'hackernews': ('TIER 3 — COMMUNITY', 'Technical discussion forum. Volume is high, per-post signal varies.'),
       'github': ('TIER 4 — CODE', 'Repository listings. Code is commitment — stars indicate real interest.'),
       'moltbook': ('TIER 3 — COMMUNITY', 'Agent social network. Direct from AI agents building in the space.'),
   }

2. Add a get_source_tier_label(source, source_tier) helper function:
   - If source is in SOURCE_DESCRIPTIONS, return that
   - If source starts with 'rss_' and source_tier == 1: return ('TIER 1 — AUTHORITY', 'Institutional research and analysis. Single mention = high signal.')
   - If source starts with 'rss_' and source_tier == 2: return ('TIER 2 — CURATED', 'Human-curated newsletter. Pre-filtered for relevance.')
   - Default: return (f'TIER {source_tier}', 'Unknown source type')

3. Update extract_problems_multisource() — when formatting posts for the extraction prompt:
   Group posts by source as before, but use the tier-aware headers:
   
   For each source group:
     feed_display_name = source.replace('rss_', '').upper()
     tier_label, tier_desc = get_source_tier_label(source, posts[0].get('source_tier', 3))
     formatted += f"\n\n=== SOURCE: {feed_display_name} ({tier_label}) ===\n"
     formatted += f"({tier_desc})\n"

4. When storing extracted problems, set max_source_tier:
   Track the minimum tier number (= highest authority) seen in the batch being processed.
   For each extracted problem, set: problem['max_source_tier'] = best_tier_in_batch

5. Apply the same tier-aware formatting to extract_tools_multisource() and extract_trending_topics_multisource().

Don't modify the original single-source extraction functions.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task scrape_rss
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task extract_problems_multisource
```

---

## Prompt 4: Anti-Repetition System

```
Add an anti-repetition system to prevent the newsletter from featuring the same content repeatedly.

Reference: AGENTPULSE_PHASE5_EDITORIAL.md, "Anti-Repetition System" section.

Changes to docker/processor/agentpulse_processor.py:

1. Add get_excluded_opportunity_ids(editions_back=2) function:
   - Queries the last N published newsletters (ordered by edition_number DESC)
   - From each newsletter's data_snapshot, extracts the IDs of the top 2 items from section_a_opportunities
   - Returns a set of UUIDs that are EXCLUDED from the next newsletter's Section A
   - Handle missing data_snapshot or missing section_a_opportunities gracefully (return empty set)

2. Add get_previously_featured_titles(editions_back=4) function:
   - Queries the last N published newsletters
   - From each data_snapshot, collects titles/descriptions from ALL sections (a, b, c)
   - Returns a set of title fragments (first 50 chars, lowercased) for deduplication

3. UPDATE prepare_newsletter_data():
   
   REPLACE the Section A opportunity selection with freshness-aware logic:
   a. Fetch all opportunities as before (with staleness penalty)
   b. Get excluded_ids = get_excluded_opportunity_ids(2)
   c. Split into:
      - never_featured: newsletter_appearances == 0
      - returning_eligible: newsletter_appearances > 0 AND id NOT in excluded_ids
        AND has new data (last_reviewed_at > last_featured_at)
   d. Build section_a:
      - Start with up to 3 never_featured items (sorted by effective_score)
      - Add up to 2 returning_eligible items (sorted by effective_score)
      - Sort final list by effective_score
      - Cap at 5
   
   UPDATE the Section B selection:
   e. After fetching emerging signals, filter out any whose description[:50].lower() 
      appears in get_previously_featured_titles(4)
   
   ADD freshness metadata to the input_data:
   f. input_data['freshness_rules'] = {
        'excluded_opportunity_ids': [str(id) for id in excluded_ids],
        'max_returning_items_section_a': 2,
        'min_new_items_section_a': 1,
        'section_b_new_only': True,
        'section_c_new_only': True,
        'returning_items_require_new_angle': True
      }

4. For each opportunity in section_a, add flags:
   opp['is_returning'] = opp.get('newsletter_appearances', 0) > 0
   opp['last_edition_featured'] = opp.get('last_featured_at')

Don't modify any other functions. Keep all existing staleness penalty logic.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_newsletter
```

---

## Prompt 5: Topic Evolution Tracking

```
Add topic evolution tracking that monitors how topics develop through lifecycle stages over time.

Reference: AGENTPULSE_PHASE5_EDITORIAL.md, "Temporal Analysis Engine" section.

Add to docker/processor/agentpulse_processor.py:

1. Add normalize_topic_key(theme) function:
   - Takes a cluster theme string
   - Lowercase, strip whitespace, replace spaces with underscores
   - Remove common stop words: 'the', 'a', 'an', 'for', 'in', 'of', 'and', 'or', 'with'
   - Truncate to 100 chars
   - Return the normalized key

2. Add count_mentions_for_topic(topic_key, days=7) function:
   - Query problems from the last N days
   - Count how many have the topic_key keywords in their description or title (case-insensitive Python filtering)
   - Return the count

3. Add avg_sentiment_for_topic(topic_key, days=7) function:
   - Query tool_mentions from the last N days
   - Filter for mentions where the topic keywords appear in tool_name or context
   - Return average sentiment_score (0 if none found, handle division by zero)

4. Add unique_sources_for_topic(topic_key, days=7) function:
   - Query source_posts from the last N days
   - Filter for posts where topic keywords appear in title or body
   - Return list of unique source values

5. Add github_repos_for_topic(topic_key, days=7) function:
   - Query source_posts where source='github' from the last N days
   - Filter for repos where topic keywords appear in title, body, or tags
   - Return count

6. Add detect_topic_stage(snapshots) function:
   Takes a list of weekly snapshot dicts, returns lifecycle stage string.
   Logic (check in this order):
   - If < 2 snapshots: return 'emerging'
   - DECLINING: last 3 snapshots show consistent drop AND recent < 50% of average
   - MATURE: last 4 snapshots low variance (max-min < 30% of avg) AND recent mentions > 5
   - CONSOLIDATING: recent github > 0 AND recent mentions < average AND recent sources >= 2
   - BUILDING: any github repos in recent snapshots
   - DEBATING: recent mentions > average AND recent sources >= 2
   - Default: 'emerging'

7. Add update_topic_evolution() function:
   - Queries problem_clusters ordered by opportunity_score DESC, limit 30
   - For each cluster:
     a. Normalize theme to topic_key
     b. Gather weekly signals: mentions, sentiment, sources, github repos
     c. Build snapshot: {date, mentions, sentiment, sources, source_count, github_repos}
     d. Upsert into topic_evolution: if exists, append snapshot (keep last 12), detect stage; if new, insert
     e. If stage changed, update stage_changed_at
   - Return {'topics_updated': N}

8. Add 'update_topic_evolution' to execute_task() and argparse choices.

Don't modify any existing functions.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task update_topic_evolution
# Check Supabase: topic_evolution should have rows
```

---

## Prompt 6: Update Analyst Identity for Insights

```
Update the Analyst's identity template to support source weighting and insight/thesis generation.

Edit templates/analyst/IDENTITY.md — ADD these sections. Keep everything already there.

1. ADD after the "Cross-Source Validation" section:

   ## Source Weighting

   Not all sources carry equal weight:

   - Tier 1 (HBR, BCG, a16z, MIT Tech Review): A single mention here is a strong signal.
     These are edited, researched publications. If they're writing about a topic,
     it's past the "is this real?" phase.
   - Tier 2 (TLDR AI, TLDR Founders, Ben's Bites): Human-curated newsletters.
     Pre-filtered for relevance. A mention means someone with editorial judgment thought it mattered.
   - Tier 3 (Hacker News, Moltbook): Raw community signal. Individual posts are noisy,
     but patterns across many posts are meaningful.
   - Tier 4 (GitHub): Code is commitment. A trending repo is stronger than
     100 discussion posts because someone invested real time building it.

   When scoring opportunities and forming insights:
   - "Featured in a16z blog" > "50 Moltbook mentions"
   - "3 Tier 1 sources discussing this" = near-certain market signal
   - "Only seen on Moltbook" = flag as single-source, lower confidence

2. ADD a new section:

   ## Insight Generation

   You don't just report signals — you interpret them. When you receive topic_evolution
   data, you can see how topics have developed over weeks. Use this to form theses.

   ### How to Form a Thesis

   1. Look at the evolution snapshots. What stage is this topic in?
      Stages: emerging → debating → building → consolidating → mature → declining
   2. Is there a historical parallel? (e.g., "This mirrors the containerization debate —
      lots of competing approaches, about to consolidate")
   3. What would need to happen for this to progress to the next stage?
   4. What's the most likely outcome? Why?
   5. What would change your mind?

   ### Thesis Format

   For each major insight, provide in your output:
   - thesis: One clear sentence stating your position
   - evidence: 2-3 specific data points supporting it
   - confidence: 0.0-1.0 with explanation
   - timeframe: When you expect this to play out
   - counter_argument: The strongest case against your thesis
   - invalidation_trigger: Specific observable event that would change your mind

   ### Rules for Insights

   - Every thesis MUST cite specific evidence from the data
   - NEVER present speculation as fact
   - ALWAYS include uncertainty and counter-arguments
   - It's better to have 1 well-reasoned insight than 5 vague observations
   - If the data doesn't support forming a thesis, say so explicitly:
     "Not enough signal yet to form a view. Watching for: [specific things]"
   - Your theses will be tracked by the prediction system. Be honest about confidence.

3. Update the output format section to include:
   - 'insights': array of thesis objects with the format above
   - 'topic_stages': dict of topic_key → current_stage from evolution data

Don't modify SOUL.md or any other files.
```

**After this:**
```bash
bash scripts/deploy-identities.sh
docker compose restart analyst
```

---

## Prompt 7: Update Newsletter Identity

```
Update the Newsletter agent's identity template with the new structure, anti-repetition rules, and Big Insight section.

Edit templates/newsletter/IDENTITY.md — REPLACE the Structure section and ADD new sections. Keep voice guidelines, writing constraints, and everything else intact.

1. REPLACE the Structure section with:

   ## Structure

   Every edition follows this arc:

   1. **Cold open** — One sentence hook. NEVER repeat the same structure from last edition.
      Not "This week in AI agents..." but "The agent economy just hit its first inflection point."

   2. **The Big Insight** — NOT just "what happened" but "what it means."
      One major thesis per edition. Structure:
      a. The thesis (bold, one sentence)
      b. The evidence trail (how did we get here? What evolved over recent weeks?)
      c. What happens next (specific prediction with timeframe)
      d. The counter-argument (strongest case against)
      e. What we're watching (specific signals that would confirm or refute)
      If Analyst provided insights/theses, use the strongest one.
      This section should make someone want to share the newsletter.

   3. **Top Opportunities** (Section A) — 3-5 items.
      For returning items (is_returning=true): MUST state what's new.
      Lead with fresh content when possible.

   4. **Emerging Signals** (Section B) — 2-4 items, ALL new.

   5. **The Curious Corner** (Section C) — 2-3 items, ALL new.

   6. **Tool Radar** — what's rising, falling, new.

   7. **Prediction Tracker** (Section D) — 🟢🟡🔴 format.
      ALWAYS include faded predictions. Max 6 predictions.

   8. **Gato's Corner** — Bitcoin-maxi take. Can riff on the Big Insight.

   9. **By the Numbers** — Sources tracked, posts scanned, active predictions, topic stages.

2. ADD:

   ## Freshness Rules (NON-NEGOTIABLE)

   The data includes freshness_rules. Follow strictly:
   1. HARD EXCLUSION: IDs in excluded_opportunity_ids CANNOT appear in Section A.
   2. Max 2 returning items in Section A. Each MUST state what's new.
   3. Min 1 brand new item in Section A.
   4. Sections B, C: everything new. Shorter is better than recycled.
   5. NEVER same cold open structure or lead topic two editions in a row.

3. ADD:

   ## Source Authority

   When referencing evidence, note source tier when it adds credibility:
   - "According to a16z's latest analysis..." (Tier 1)
   - "TLDR AI flagged this trend last week..." (Tier 2)
   - Don't cite-drop Moltbook or HN — community sources, not authorities
   - GitHub is action signal: "Three new repos this week" (code > talk)

Don't modify SOUL.md or any other files.
```

**After this:**
```bash
bash scripts/deploy-identities.sh
docker compose restart newsletter
```

---

## Prompt 8: Update prepare_newsletter_data

```
Update prepare_newsletter_data() to include topic evolution data, source stats, and analyst insights.

Changes to docker/processor/agentpulse_processor.py:

1. ADD topic evolution data gathering in prepare_newsletter_data():

   topic_evolution = supabase.table('topic_evolution')\
       .select('*')\
       .order('last_updated', desc=True)\
       .limit(15)\
       .execute()
   
   Add to input_data: 'topic_evolution': topic_evolution.data or []

2. ADD source breakdown stats:

   week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
   source_stats = {}
   
   # Count each source type
   for source_name in ['moltbook', 'hackernews', 'github']:
       count = supabase.table('source_posts')\
           .select('id', count='exact')\
           .eq('source', source_name)\
           .gte('scraped_at', week_ago)\
           .execute()
       source_stats[source_name] = count.count or 0
   
   # Count all RSS sources together
   rss_count = supabase.table('source_posts')\
       .select('id', count='exact')\
       .like('source', 'rss_%')\
       .gte('scraped_at', week_ago)\
       .execute()
   source_stats['rss_premium'] = rss_count.count or 0
   
   Add to stats: stats['source_breakdown'] = source_stats
   Add to stats: stats['total_posts_all_sources'] = sum(source_stats.values())

3. ADD topic stage summary:

   stages = {}
   for topic in (topic_evolution.data or []):
       stage = topic.get('current_stage', 'unknown')
       stages[stage] = stages.get(stage, 0) + 1
   stats['topic_stages'] = stages

4. ADD analyst insights:

   latest_analysis = supabase.table('analysis_runs')\
       .select('key_findings, analyst_notes, metadata')\
       .eq('status', 'completed')\
       .order('completed_at', desc=True)\
       .limit(1)\
       .execute()
   
   if latest_analysis.data:
       analysis = latest_analysis.data[0]
       input_data['analyst_insights'] = {
           'key_findings': analysis.get('key_findings'),
           'analyst_notes': analysis.get('analyst_notes'),
           'theses': (analysis.get('metadata') or {}).get('insights', [])
       }

Don't modify any other functions.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task update_topic_evolution
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_newsletter
```

---

## Prompt 9: Scheduling Updates

```
Update the Processor's scheduler for RSS scraping and topic evolution tracking.

Changes to docker/processor/agentpulse_processor.py:

1. ADD scheduled RSS scraping in setup_scheduler():
   schedule.every(6).hours.do(scheduled_scrape_rss)
   
   Add the wrapper:
   def scheduled_scrape_rss():
       try:
           result = scrape_rss_feeds()
           logger.info(f"Scheduled RSS scrape: {result}")
       except Exception as e:
           logger.error(f"Scheduled RSS scrape failed: {e}")

2. ADD topic evolution update:
   schedule.every().monday.at("06:00").do(scheduled_update_evolution)
   
   def scheduled_update_evolution():
       try:
           result = update_topic_evolution()
           logger.info(f"Topic evolution update: {result}")
       except Exception as e:
           logger.error(f"Topic evolution update failed: {e}")

3. UPDATE run_pipeline in execute_task():
   Add RSS scraping (after GitHub scrape, before extraction):
   try:
       rss_result = scrape_rss_feeds()
       results['rss'] = rss_result
   except Exception as e:
       logger.error(f"RSS scrape failed in pipeline: {e}")
       results['rss'] = {'error': str(e)}
   
   Add topic evolution (before prepare_analysis_package):
   try:
       evolution_result = update_topic_evolution()
       results['topic_evolution'] = evolution_result
   except Exception as e:
       logger.error(f"Topic evolution failed in pipeline: {e}")
       results['topic_evolution'] = {'error': str(e)}

4. UPDATE prepare_analysis_package() to include topic evolution:
   topic_evolution = supabase.table('topic_evolution')\
       .select('*')\
       .order('last_updated', desc=True)\
       .limit(20)\
       .execute()
   data_package['topic_evolution'] = topic_evolution.data or []

Don't modify any other functions.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task run_pipeline
docker compose logs processor | grep -i "rss\|evolution"
```

---

## Prompt 10: Wire Telegram Commands

```
Add new Telegram commands for topic evolution, theses, and freshness status.

1. Add to docker/processor/agentpulse_processor.py execute_task():

   'get_topic_evolution':
   - Query topic_evolution ordered by last_updated DESC
   - Limit from params (default 10)
   - Return rows

   'get_topic_thesis':
   - Takes params.topic as a search string
   - Query topic_evolution where topic_key ILIKE '%{topic}%'
   - If found: return thesis, confidence, stage, recent snapshots
   - If not found: return {'error': f'No topic found matching "{topic}"'}

   'get_freshness_status':
   - Call get_excluded_opportunity_ids(2)
   - Query those opportunity IDs to get their titles
   - Call get_previously_featured_titles(4)
   - Return {
       'excluded_from_next_edition': [titles],
       'recently_featured_count': N,
       'editions_checked': 4
     }

2. Add all three to argparse choices.

3. Update data/openclaw/workspace/AGENTS.md:

   /topics → write {"task":"get_topic_evolution","params":{"limit":8}} to the queue.
   Display topics with lifecycle stage:
   🌱 = emerging, ⚖️ = debating, 🔨 = building, 🏗️ = consolidating, ✅ = mature, 📉 = declining

   /thesis [topic] → write {"task":"get_topic_thesis","params":{"topic":"<user_input>"}} to the queue.
   Display thesis, confidence, evidence, counter-argument.
   If none: "No thesis formed yet for this topic."

   /freshness → write {"task":"get_freshness_status","params":{}} to the queue.
   Display what's excluded from the next newsletter and why.

4. Update skills/agentpulse/SKILL.md — add to commands table:
   | /topics | Show topic lifecycle stages and evolution |
   | /thesis [topic] | Show Analyst's thesis on a specific topic |
   | /freshness | Show what's excluded from the next newsletter |

Don't modify any other files.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
docker compose restart gato
# Test: /topics, /thesis memory, /freshness
```

---

## End-to-End Verification

```bash
# 1. All services running
docker compose ps

# 2. Test RSS scraping
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task scrape_rss

# 3. Check source coverage
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))

print('=== Source Coverage ===')
sources = c.rpc('', {}).execute()  # Won't work — use direct queries instead

from collections import Counter
all_posts = c.table('source_posts').select('source, source_tier').execute()
source_counts = Counter()
tier_counts = Counter()
for p in (all_posts.data or []):
    source_counts[p['source']] += 1
    tier_counts[f\"tier_{p.get('source_tier', 3)}\"] += 1

for source, count in source_counts.most_common():
    print(f'  {source}: {count} posts')
print()
for tier, count in tier_counts.most_common():
    print(f'  {tier}: {count} posts')
"

# 4. Test topic evolution
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task update_topic_evolution
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))
topics = c.table('topic_evolution').select('topic_key, current_stage, thesis').order('last_updated', desc=True).limit(10).execute()
for t in (topics.data or []):
    stage = t.get('current_stage', '?')
    thesis = (t.get('thesis') or 'No thesis yet')[:80]
    print(f'  {t[\"topic_key\"]}: {stage} | {thesis}')
"

# 5. Test anti-repetition
docker compose exec processor python3 -c "
import sys
sys.path.insert(0, '/home/openclaw')
from agentpulse_processor import get_excluded_opportunity_ids, get_previously_featured_titles, init_clients
init_clients()
excluded = get_excluded_opportunity_ids(2)
featured = get_previously_featured_titles(4)
print(f'Excluded opportunity IDs: {len(excluded)}')
print(f'Previously featured titles: {len(featured)}')
for t in list(featured)[:5]:
    print(f'  \"{t}\"')
"

# 6. Full pipeline
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task run_pipeline
# Wait for analyst
sleep 60
docker compose logs analyst | tail -20

# 7. Generate newsletter
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_newsletter
sleep 90
docker compose logs newsletter | tail -20

# 8. Check newsletter draft
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))
nl = c.table('newsletters').select('edition_number, title, status, content_markdown').order('created_at', desc=True).limit(1).execute()
if nl.data:
    n = nl.data[0]
    print(f'Edition #{n[\"edition_number\"]}: {n[\"title\"]} ({n[\"status\"]})')
    content = n.get('content_markdown', '')
    has_insight = 'insight' in content.lower() or 'thesis' in content.lower()
    has_prediction = 'prediction' in content.lower() or '🟢' in content or '🟡' in content
    has_emerging = 'emerging' in content.lower()
    has_curious = 'curious' in content.lower()
    print(f'  Has Big Insight section: {has_insight}')
    print(f'  Has Prediction Tracker: {has_prediction}')
    print(f'  Has Emerging Signals: {has_emerging}')
    print(f'  Has Curious Corner: {has_curious}')
    print(f'  Total length: {len(content)} chars')
"

# 9. Telegram commands
echo "Test on Telegram:"
echo "  /topics     — lifecycle stages"
echo "  /thesis memory — thesis on memory topic"
echo "  /freshness  — what's excluded from next edition"
echo "  /sources    — per-source stats"
echo "  /scan       — full pipeline with all sources"
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| RSS scraper returns 0 for all feeds | Network blocked or feedparser not installed | `docker compose exec processor pip list \| grep feedparser` |
| RSS scraper returns 0 for specific feed | Feed URL changed or doesn't exist | Test URL in browser, update RSS_FEEDS |
| Topic evolution shows all 'emerging' | Only 1 snapshot exists (needs 2+ weeks of data) | Run `update_topic_evolution` again next week |
| No theses in analyst output | Analyst identity not updated | `bash scripts/deploy-identities.sh && docker compose restart analyst` |
| Newsletter missing Big Insight | analyst_insights not in input_data | Check Section 8 — prepare_newsletter_data must query analysis_runs |
| Anti-repetition not working | get_excluded_opportunity_ids returns empty | Need 2+ published newsletters with data_snapshot containing section_a_opportunities |
| /topics command fails | get_topic_evolution not in execute_task | Check Prompt 10 was applied |
| feedparser import error | Not in requirements.txt | Add `feedparser>=6.0.0` and rebuild processor |
| Source tier always 3 | source_tier not being set on insert | Check scrape_rss_feeds sets source_tier field |
