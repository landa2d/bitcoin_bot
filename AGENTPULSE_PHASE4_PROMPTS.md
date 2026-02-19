# AgentPulse Phase 4: Content Quality — Cursor Prompts

> **Upload `AGENTPULSE_PHASE4_CONTENT.md` as context for every prompt.**
> **Your server needs outbound network access to HN and GitHub APIs.**

---

## Prompt 1: Database Schema

Run in Supabase SQL Editor:

```sql
-- ================================================
-- PHASE 4: SOURCE EXPANSION + PREDICTION TRACKING
-- ================================================

-- 1. Unified multi-source posts table
CREATE TABLE source_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_url TEXT,
    title TEXT,
    body TEXT,
    author TEXT,
    score INT,
    comment_count INT,
    tags TEXT[],
    scraped_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    processing_type TEXT,
    metadata JSONB,
    UNIQUE(source, source_id)
);

CREATE INDEX idx_source_posts_source ON source_posts(source);
CREATE INDEX idx_source_posts_scraped ON source_posts(scraped_at DESC);
CREATE INDEX idx_source_posts_processed ON source_posts(processed);
CREATE INDEX idx_source_posts_score ON source_posts(score DESC);

-- 2. Add source tracking to existing tables
ALTER TABLE problems ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'moltbook';
ALTER TABLE problems ADD COLUMN IF NOT EXISTS source_post_ids TEXT[];
CREATE INDEX IF NOT EXISTS idx_problems_source ON problems(source);

ALTER TABLE tool_mentions ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'moltbook';
CREATE INDEX IF NOT EXISTS idx_tool_mentions_source ON tool_mentions(source);

ALTER TABLE trending_topics ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'moltbook';

-- 3. Predictions table
CREATE TABLE predictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prediction_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    initial_confidence FLOAT NOT NULL,
    newsletter_edition INT,
    opportunity_id UUID REFERENCES opportunities(id),
    cluster_id UUID REFERENCES problem_clusters(id),
    status TEXT DEFAULT 'active',
    current_score FLOAT,
    tracking_history JSONB DEFAULT '[]',
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_tracked TIMESTAMPTZ,
    metadata JSONB
);

CREATE INDEX idx_predictions_status ON predictions(status);
CREATE INDEX idx_predictions_created ON predictions(created_at DESC);
CREATE INDEX idx_predictions_type ON predictions(prediction_type);

-- 4. RLS
ALTER TABLE source_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;

-- Predictions are public (appear in newsletter / web archive)
CREATE POLICY "Public read predictions" ON predictions FOR SELECT USING (true);

-- source_posts are internal only (no public policy)
```

**Verify:** Check Supabase Table Editor — `source_posts` and `predictions` should exist. `problems` should have `source` column.

---

## Prompt 2: Hacker News Scraper

```
Add a Hacker News scraper to docker/processor/agentpulse_processor.py.

Reference: AGENTPULSE_PHASE4_CONTENT.md, "Hacker News Scraper" section.

1. Add HN_KEYWORDS constant at the top of the file:
   HN_KEYWORDS = [
       'agent', 'ai agent', 'llm', 'gpt', 'claude', 'anthropic', 'openai',
       'autonomous', 'multi-agent', 'agentic', 'tool use', 'function calling',
       'rag', 'retrieval', 'embedding', 'vector', 'langchain', 'langgraph',
       'autogen', 'crewai', 'openclaw', 'mcp', 'model context protocol',
       'ai startup', 'ai tool', 'ai framework', 'ai infrastructure',
       'chatbot', 'copilot', 'assistant', 'automation'
   ]

2. Add scrape_hackernews(limit=200) function:
   - Uses httpx to call the HN Firebase API (https://hacker-news.firebaseio.com/v0/)
   - Fetches /topstories.json, takes first `limit` IDs
   - For each story: fetch /item/{id}.json
   - Skip if type != 'story' or title is None
   - Check relevance: any keyword from HN_KEYWORDS appears in the title (case-insensitive)
   - For relevant stories: fetch up to 20 comments (story['kids'][:20])
     - For each comment: fetch /item/{comment_id}.json, collect author + text
     - sleep(0.2) between comment fetches (be polite)
   - Build post_data dict:
     {
       'source': 'hackernews',
       'source_id': str(story_id),
       'source_url': story url OR f"https://news.ycombinator.com/item?id={story_id}",
       'title': story title,
       'body': all comment texts joined with \n\n,
       'author': story 'by' field or 'anon',
       'score': story 'score' or 0,
       'comment_count': story 'descendants' or 0,
       'tags': ['show_hn'] if title starts with 'show hn' else [],
       'metadata': {
         'hn_url': f"https://news.ycombinator.com/item?id={story_id}",
         'comments': first 10 comment dicts [{author, text, score}],
         'is_show_hn': bool
       }
     }
   - sleep(0.5) between stories
   - After collecting all relevant posts: upsert each into source_posts table (on_conflict='source,source_id')
   - Wrap individual story fetches in try/except so one failure doesn't stop the batch
   - Log pipeline start/end
   - Return {'source': 'hackernews', 'posts_found': N, 'total_scanned': N}

3. Add 'scrape_hackernews' to execute_task():
   elif task_type == 'scrape_hackernews':
       return scrape_hackernews(limit=params.get('limit', 200))

4. Add 'scrape_hackernews' to argparse --task choices.

Don't modify any existing functions.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task scrape_hackernews
# Check Supabase: source_posts should have rows with source='hackernews'
# This might take 2-5 minutes depending on how many relevant stories there are
```

---

## Prompt 3: GitHub Scraper

```
Add a GitHub scraper to docker/processor/agentpulse_processor.py.

Reference: AGENTPULSE_PHASE4_CONTENT.md, "GitHub Scraper" section.

1. Add GITHUB_TOKEN env var reading at the top:
   GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

2. Add GITHUB_TOKEN to the common env section in docker-compose.yml (so the processor can read it):
   GITHUB_TOKEN: ${GITHUB_TOKEN:-}

3. Add scrape_github(days_back=7) function:
   - Uses httpx to call GitHub Search API (https://api.github.com/search/repositories)
   - Headers: Accept: application/vnd.github.v3+json
   - If GITHUB_TOKEN is set: add Authorization: token {GITHUB_TOKEN} header
   - Calculate cutoff date: days_back days ago, formatted as YYYY-MM-DD
   - Run multiple search queries:
     * f'ai agent created:>{cutoff} stars:>5'
     * f'llm agent created:>{cutoff} stars:>5'
     * f'autonomous agent created:>{cutoff} stars:>3'
     * f'agentic created:>{cutoff} stars:>3'
     * f'multi-agent created:>{cutoff} stars:>3'
     * f'mcp server created:>{cutoff} stars:>3'
   - For each query: GET /search/repositories?q={query}&sort=stars&order=desc&per_page=30
   - If 403 response: log "GitHub rate limit hit", break out of query loop
   - Deduplicate by repo ID across queries (use a seen_repos set)
   - For each unique repo, build post_data:
     {
       'source': 'github',
       'source_id': str(repo['id']),
       'source_url': repo['html_url'],
       'title': repo['full_name'],
       'body': (description or '') + '\n\nStars: {stars} | Forks: {forks} | Language: {language} | Created: {created_at}',
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
   - sleep(2) between queries (respect rate limits)
   - Upsert all into source_posts (on_conflict='source,source_id')
   - Log pipeline start/end
   - Return {'source': 'github', 'repos_found': N, 'queries_run': N}

4. Add 'scrape_github' to execute_task():
   elif task_type == 'scrape_github':
       return scrape_github(days_back=params.get('days_back', 7))

5. Add 'scrape_github' to argparse --task choices.

Don't modify any existing functions.
```

**After this:**
```bash
# Make sure GITHUB_TOKEN is in .env
docker compose build processor --no-cache
docker compose up processor -d
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task scrape_github
# Check Supabase: source_posts should have rows with source='github'
```

---

## Prompt 4: Multi-Source Extraction

```
Update the extraction functions to work with the unified source_posts table instead of only moltbook_posts.

Reference: AGENTPULSE_PHASE4_CONTENT.md, "Unified Extraction" section.

1. Add extract_problems_multisource(hours_back=48) function:
   - Queries source_posts where processed=false AND scraped_at >= hours_back ago
   - Orders by score DESC, limit 200
   - Groups posts by source for context
   - Formats them for the extraction prompt with source headers:
     "=== SOURCE: HACKERNEWS ===" with note "(Technical discussion forum — comments are the main signal)"
     "=== SOURCE: GITHUB ===" with note "(Repository listings — descriptions and stars indicate market interest)"
     "=== SOURCE: MOLTBOOK ===" with note "(Agent social network — direct from AI agents)"
   - For each post: include [source_id] title, body (truncated to 500 chars), score, tags
   - Calls OpenAI with the existing EXTRACTION_PROMPT (or problem extraction prompt) + the formatted multi-source data
   - Uses model=get_model('extraction')
   - For each extracted problem: set source='multi' (or the specific source if identifiable), store via existing store_problem or insert logic
   - Marks all processed posts as processed=true, processing_type='problem_extraction'
   - Returns {'processed': N, 'problems_found': N, 'sources': [list of sources processed]}

2. Add extract_tools_multisource(hours_back=48) function:
   - Same pattern: query source_posts where processed is false (or use a separate processed flag — actually, a post can be processed for problems AND tools, so use processing_type tracking)
   
   ACTUALLY — simpler approach: don't rely on the processed flag for tool extraction. Instead:
   - Query source_posts from the last hours_back hours regardless of processed flag
   - Run tool extraction prompt
   - Mark posts with processing_type including 'tool_extraction'
   - This way a post can contribute to both problem and tool extraction
   
   Same source header formatting as above.
   For extracted tool mentions: set source column to the post's source.

3. Add extract_trending_topics_multisource(hours_back=48) function:
   - Same pattern: query recent source_posts
   - Use the existing TRENDING_TOPICS_PROMPT
   - For extracted topics: set source column

4. IMPORTANT: Keep the existing single-source functions (extract_problems, extract_tool_mentions, extract_trending_topics) as-is. They're the fallback. The new multisource functions work alongside them.

5. Add all three to execute_task():
   - 'extract_problems_multisource' → extract_problems_multisource()
   - 'extract_tools_multisource' → extract_tools_multisource()
   - 'extract_trending_topics_multisource' → extract_trending_topics_multisource()

6. Add all three to argparse --task choices.

Don't modify existing extraction functions — add new ones alongside them.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d

# First make sure there's data to extract from
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task scrape_hackernews
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task scrape_github

# Then extract
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task extract_problems_multisource
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task extract_tools_multisource

# Check Supabase:
# - problems table should have new rows with source != 'moltbook'
# - tool_mentions table should have new rows with source != 'moltbook'
# - source_posts should have some rows with processed=true
```

---

## Prompt 5: Prediction Creation

```
Add automatic prediction creation when a newsletter is published.

Reference: AGENTPULSE_PHASE4_CONTENT.md, "Creating Predictions" section.

1. Add create_predictions_from_newsletter(newsletter_id) function to docker/processor/agentpulse_processor.py:
   - Gets the newsletter by ID from Supabase
   - Reads data_snapshot from the newsletter row
   - Gets the edition_number
   
   From Section A opportunities (section_a_opportunities in data_snapshot):
   - For each of the top 5 opportunities:
     - Upsert into predictions table (on_conflict on opportunity_id if present):
       prediction_type='opportunity'
       title=opportunity title
       description=opportunity description (truncate to 500 chars)
       initial_confidence=opportunity confidence_score
       newsletter_edition=edition number
       opportunity_id=opportunity id (if present)
       status='active'
       current_score=confidence_score
       tracking_history=JSON array with one entry: {date, event: 'created', confidence, notes: 'Featured in edition #N'}
   
   From Section B emerging signals (section_b_emerging in data_snapshot):
   - For each of the top 4 emerging signals:
     - Insert into predictions:
       prediction_type='emerging_signal'
       title=signal description (first 100 chars)
       description=signal_phrases as JSON string (truncate to 500 chars)
       initial_confidence=0.3 (emerging signals start low)
       newsletter_edition=edition number
       cluster_id=cluster id (if present)
       status='active'
       current_score=0.3
       tracking_history=JSON array with one entry: {date, event: 'created', confidence: 0.3, notes: 'Emerging signal in edition #N'}
   
   - Handle missing fields gracefully (data_snapshot format may vary)
   - Use json.dumps with default=str for any datetime serialization
   - Return {'predictions_created': N}

2. Update the existing publish_newsletter() function:
   After marking the newsletter as published (after the existing Telegram send and appearance updates), add:
   try:
       pred_result = create_predictions_from_newsletter(newsletter_id)
       logger.info(f"Predictions created: {pred_result}")
   except Exception as e:
       logger.error(f"Prediction creation failed: {e}")
       # Don't fail the publish — predictions are non-critical

3. Add 'create_predictions' to execute_task():
   elif task_type == 'create_predictions':
       return create_predictions_from_newsletter(params.get('newsletter_id'))

4. Add 'create_predictions' to argparse choices.

Don't modify any other functions.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d

# If you have a published newsletter, test prediction creation manually:
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))
nl = c.table('newsletters').select('id').eq('status','published').order('created_at', desc=True).limit(1).execute()
if nl.data:
    print(f'Latest published newsletter: {nl.data[0][\"id\"]}')
else:
    print('No published newsletters — publish one first with /newsletter_publish')
"

# If you have a newsletter ID:
# docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task create_predictions --params '{"newsletter_id": "<UUID>"}'
# Or just publish a newsletter — predictions will be created automatically
```

---

## Prompt 6: Prediction Tracking

```
Add weekly prediction tracking that evaluates active predictions against current data.

Reference: AGENTPULSE_PHASE4_CONTENT.md, "Tracking Predictions" section.

1. Add gather_prediction_signals(pred) function:
   Takes a prediction dict, returns signal metrics.
   - Extract keywords from the prediction title (split, take first 3 meaningful words, lowercase)
   - Query problems from the last 7 days: check if any keyword appears in problem description or title (case-insensitive Python filtering after fetching)
   - Query tool_mentions from the last 7 days: check if any keyword appears in tool_name
   - Query source_posts with source='github' from the last 7 days: check if any keyword appears in title or body
   - Return {
       'mentions_7d': count of matching problems,
       'avg_sentiment': average sentiment of matching tool mentions (0 if none),
       'new_tools': list of matching tool names (max 5),
       'github_repos': count of matching github posts,
       'github_stars': total stars of matching github repos
     }

2. Add evaluate_prediction(pred, signals) function:
   Takes a prediction and its current signals. Returns (new_status, new_score, notes).
   
   Logic:
   - Calculate weeks_active from pred['created_at'] to now
   - mentions = signals['mentions_7d']
   - github = signals['github_repos']
   
   Decision tree:
   - If mentions >= 5 AND github >= 2: score up 0.15, notes="Strong signals", status='confirmed' if score >= 0.8 else 'active'
   - Elif mentions >= 2 OR github >= 1: score up 0.05, notes="Developing", status='active'
   - Elif mentions == 0 AND weeks_active >= 3: score down 0.2, notes="No mentions for 3+ weeks", status='faded' if score < 0.2 else 'active'
   - Elif mentions == 0 AND weeks_active >= 1: score down 0.1, notes="Quiet week", status='active'
   - Else: score unchanged, notes="Stable", status='active'
   
   Clamp score between 0 and 1. Round to 2 decimals.

3. Add track_predictions() function:
   - Queries predictions where status='active'
   - For each: calls gather_prediction_signals, then evaluate_prediction
   - Appends to tracking_history JSON array: {date, event: 'tracked', mentions_this_week, mentions_total, sentiment, new_tools, github_repos, score, notes}
   - Updates the prediction: current_score, tracking_history, last_tracked
   - If status changed: update status, and if resolved (confirmed/faded/wrong) set resolved_at and resolution_notes
   - Returns {'tracked': N, 'confirmed': N, 'faded': N, 'active': N}

4. Add 'track_predictions' to execute_task():
   elif task_type == 'track_predictions':
       return track_predictions()

5. Add 'track_predictions' to argparse choices.

Don't modify any other functions.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d

# You need active predictions first — either publish a newsletter or create test ones:
docker compose exec processor python3 -c "
from supabase import create_client
import os, json
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))
c.table('predictions').insert({
    'prediction_type': 'opportunity',
    'title': 'Agent Memory Tooling',
    'description': 'Growing demand for persistent memory in agent systems',
    'initial_confidence': 0.72,
    'newsletter_edition': 1,
    'status': 'active',
    'current_score': 0.72,
    'tracking_history': json.dumps([{'date': '2026-02-10', 'event': 'created', 'confidence': 0.72}])
}).execute()
print('Test prediction created')
"

# Run tracking
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task track_predictions
# Check Supabase: predictions table — tracking_history should have a new entry
```

---

## Prompt 7: Update Newsletter Data Package + Identity

```
Update the newsletter data preparation to include prediction data, and update the Newsletter agent's identity for the new Prediction Tracker section.

Reference: AGENTPULSE_PHASE4_CONTENT.md, "Newsletter Section: Prediction Tracker" and "Updated Newsletter Data Package" sections.

1. Update prepare_newsletter_data() in docker/processor/agentpulse_processor.py:
   
   Add prediction data to the gathering:
   - Query predictions where status IN ('active', 'confirmed', 'faded') AND (last_tracked IS NOT NULL OR status != 'active')
   - Order by: confirmed first, then active (by current_score DESC), then faded
   - Limit 10
   - Add to the input_data sent to the newsletter agent:
     'predictions': predictions_data
   
   Also add source stats:
   - Count source_posts by source for the last 7 days
   - Add to stats: {'hackernews_posts': N, 'github_repos': N, 'moltbook_posts': N}

2. Update templates/newsletter/IDENTITY.md — ADD a new section to the Structure:

   Between "Tool Radar" and "Gato's Corner", add:

   ## Prediction Tracker (Section D — NEW)
   
   Track record of our previous calls. This section builds trust through honesty.
   
   Format:
   🟢 CONFIRMED — predictions with status='confirmed' (current_score >= 0.8)
     "Title (Edition #N, initial confidence X.XX)"
     "Now: Y.YY — [specific evidence: N mentions, N repos, etc.]. This one landed."
   
   🟡 DEVELOPING — predictions with status='active' and positive trajectory
     "Title (Edition #N, initial confidence X.XX)"  
     "Now: Y.YY — [what's happening]. Worth watching."
   
   🔴 FADED — predictions with status='faded' (current_score < 0.2)
     "Title (Edition #N, initial confidence X.XX)"
     "Now: Y.YY — [what happened]. We got this one wrong."
   
   Rules:
   - ALWAYS include faded/wrong predictions. Hiding failures destroys trust.
   - Be specific about evidence: "3 new GitHub repos" not "growing interest"
   - Keep each prediction to 2 lines max
   - If no predictions to track yet, skip this section entirely
   - Max 6 predictions shown (2 per category). Prioritize the most dramatic changes.
   
   Voice: matter-of-fact, honest. Celebrate wins briefly, acknowledge misses without excuses.

3. Also update the "By the Numbers" section description to include:
   - Sources tracked: N (Moltbook, HN, GitHub)
   - Posts scanned this week: N across all sources
   - Active predictions: N
   - Prediction accuracy: N% (confirmed / (confirmed + faded) if any resolved)

Don't modify any code files other than the processor and the newsletter identity template.
```

**After this:**
```bash
# Deploy updated identity
bash scripts/deploy-identities.sh
docker compose build processor --no-cache
docker compose up processor -d
docker compose restart newsletter

# Test the full flow
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_newsletter
# Wait 60 seconds for newsletter agent
docker compose logs newsletter | tail -30
# Check the newsletter draft in Supabase — should include prediction tracker section
```

---

## Prompt 8: Update Analyst Identity for Cross-Source Validation

```
Update the Analyst's identity template to understand multi-source data and cross-source validation.

1. Edit templates/analyst/IDENTITY.md — ADD this section after "Cross-Pipeline Synthesis":

   ## Cross-Source Validation
   
   You now receive data from multiple sources: Moltbook (agent social network),
   Hacker News (technical discussions), and GitHub (code repositories).
   
   Cross-source signals are significantly more reliable:
   
   - Problem on Moltbook + discussion on HN = high confidence signal
     "Real users are complaining AND the technical community is debating solutions"
   
   - Tool trending on GitHub + complaints on Moltbook = disruption signal
     "New solution gaining traction while incumbent faces criticism"
   
   - New repo on GitHub + "Show HN" post = product launch event
     "Someone built something and is actively promoting it"
   
   - HN discussion + no Moltbook mentions = early-stage, developer-facing only
     "Technically interesting but hasn't reached the agent community yet"
   
   - Moltbook only = single-source signal (note this in your reasoning)
     "Only seen on Moltbook — may be echo chamber effect"
   
   When reporting findings, ALWAYS note source diversity:
   - "Corroborated across 3 sources" = highest confidence
   - "Seen on 2 sources" = strong signal
   - "Single source only" = flag as lower confidence
   
   The source_posts data in your input includes a 'source' field for each post.
   Count unique sources for each finding to assess corroboration.

2. Also update the "Situational Assessment" step to include:
   "How many sources contributed data this cycle? Any sources missing or thin?"

3. Update the "Intelligence Brief" output to include:
   - source_breakdown: {moltbook: N, hackernews: N, github: N}
   - For each finding: source_count (how many sources corroborate it)

Don't modify any other files.
```

**After this:**
```bash
bash scripts/deploy-identities.sh
docker compose restart analyst
```

---

## Prompt 9: Scheduling Updates

```
Update the Processor's scheduler for multi-source scraping, multi-source extraction, and prediction tracking.

Update setup_scheduler() in docker/processor/agentpulse_processor.py:

1. ADD scheduled scraping for new sources:
   - schedule.every(6).hours.do(scheduled_scrape_hackernews)
   - schedule.every(12).hours.do(scheduled_scrape_github)
   
   Create the scheduled functions:
   def scheduled_scrape_hackernews():
       try:
           result = scrape_hackernews(limit=200)
           logger.info(f"Scheduled HN scrape: {result}")
       except Exception as e:
           logger.error(f"Scheduled HN scrape failed: {e}")
   
   def scheduled_scrape_github():
       try:
           result = scrape_github(days_back=7)
           logger.info(f"Scheduled GitHub scrape: {result}")
       except Exception as e:
           logger.error(f"Scheduled GitHub scrape failed: {e}")

2. UPDATE the existing scheduled analysis flow to use multi-source extraction.
   The scheduled_analyze() function (or equivalent) should now run:
   - extract_problems_multisource() instead of (or in addition to) extract_problems()
   - extract_tools_multisource() instead of (or in addition to) extract_tool_mentions()
   - extract_trending_topics_multisource() instead of (or in addition to) extract_trending_topics()
   
   Keep the old single-source functions as fallbacks. If the multisource function fails, catch the exception and run the single-source version.

3. ADD prediction tracking before newsletter generation:
   - schedule.every().monday.at("06:30").do(scheduled_track_predictions)
   
   def scheduled_track_predictions():
       try:
           result = track_predictions()
           logger.info(f"Prediction tracking: {result}")
       except Exception as e:
           logger.error(f"Prediction tracking failed: {e}")

4. UPDATE the run_pipeline task in execute_task() to include new sources:
   Current flow: scrape_moltbook → extract → cluster → prepare_analysis
   New flow:
   - scrape_moltbook()
   - scrape_hackernews()
   - scrape_github()
   - extract_problems_multisource()
   - extract_tools_multisource()
   - extract_trending_topics_multisource()
   - cluster_problems()
   - prepare_analysis_package()
   
   Wrap each in try/except so one failure doesn't stop the pipeline. Collect all results.

Don't modify any functions other than setup_scheduler(), the scheduled_ wrappers, and the run_pipeline section of execute_task().
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d

# Test the full pipeline with all sources
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task run_pipeline
# This will take a few minutes — it scrapes 3 sources, extracts, clusters, then delegates to analyst

# Check logs
docker compose logs processor | tail -50
# Should show HN scrape, GitHub scrape, multi-source extraction, etc.
```

---

## Prompt 10: Wire Telegram Commands

```
Add new Telegram commands for predictions and source status.

1. Add to docker/processor/agentpulse_processor.py execute_task():

   'get_predictions':
   - Query predictions ordered by: status='confirmed' first, then 'active' (by current_score DESC), then 'faded'
   - Limit from params (default 10)
   - Return the rows

   'get_source_status':
   - For each source ('moltbook', 'hackernews', 'github'):
     * Count total posts in source_posts
     * Count posts from last 24 hours
     * Get the most recent scraped_at timestamp
   - Also count moltbook_posts separately (legacy table)
   - Return per-source stats

   'create_manual_prediction':
   - Takes: title, description, prediction_type (default 'manual'), initial_confidence (default 0.5)
   - Inserts into predictions table
   - Returns the created prediction

2. Add all three to argparse choices.

3. Update data/openclaw/workspace/AGENTS.md — add:

   - /predictions → write {"task":"get_predictions","params":{"limit":8}} to the queue.
     Display predictions grouped by status:
     🟢 Confirmed, 🟡 Active/Developing, 🔴 Faded
     For each: title, edition #, initial → current confidence, latest notes

   - /sources → write {"task":"get_source_status","params":{}} to the queue.
     Display per-source scraping status:
     Source | Total Posts | Last 24h | Last Scrape
     Show a summary of data coverage.

   - /predict [description] → write {"task":"create_manual_prediction","params":{"title":"<description>","description":"<description>","initial_confidence":0.5}} to the queue.
     Tell user "Prediction recorded. It will be tracked in future newsletters."

4. Update skills/agentpulse/SKILL.md — add to commands table:
   | /predictions | Show prediction tracking status |
   | /sources | Show scraping status per data source |
   | /predict [text] | Manually add a prediction to track |

Don't modify any other files.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
docker compose restart gato

# Test on Telegram:
# /sources — should show scraping stats per source
# /predictions — should show tracked predictions
# /predict "MCP will become the standard agent protocol by Q3" — should record it
```

---

## End-to-End Verification

```bash
# 1. All services running
docker compose ps

# 2. Scrape all sources
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task scrape_hackernews
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task scrape_github

# 3. Check source_posts
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))
for source in ['moltbook', 'hackernews', 'github']:
    count = c.table('source_posts').select('id', count='exact').eq('source', source).execute()
    print(f'{source}: {count.count} posts')
"

# 4. Multi-source extraction
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task extract_problems_multisource
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task extract_tools_multisource

# 5. Full pipeline (does everything)
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task run_pipeline

# 6. Track predictions (need active predictions first)
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task track_predictions

# 7. Generate newsletter with predictions + multi-source data
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_newsletter
# Wait 60 seconds
# Check Supabase: newsletters table should have draft with predictions section

# 8. Telegram commands
# /sources
# /predictions
# /scan — full pipeline with all sources
```

---

## Troubleshooting

**HN scraper returns 0 posts:**
→ Keywords might be too narrow. Check: `docker compose exec processor python3 -c "import httpx; ids = httpx.get('https://hacker-news.firebaseio.com/v0/topstories.json').json()[:5]; print(ids)"` — if this fails, outbound network is blocked.
→ Try broadening keywords or increasing the limit.

**GitHub scraper hits rate limit:**
→ Add GITHUB_TOKEN to .env. Without it, you get 10 req/min. With it, 30 req/min.
→ Check: `docker compose exec processor env | grep GITHUB_TOKEN`

**Multi-source extraction processes 0 posts:**
→ Check source_posts has unprocessed rows: `SELECT source, count(*), count(*) FILTER (WHERE processed=false) as unprocessed FROM source_posts GROUP BY source;`
→ The processed flag might already be set from a previous run.

**Predictions not created on publish:**
→ The newsletter must have data_snapshot with section_a_opportunities and section_b_emerging. Check the newsletter row in Supabase.
→ Create predictions manually to test tracking: use the test command from Prompt 6.

**Prediction tracking finds no signals:**
→ Keyword matching is basic (title word splitting). If prediction titles are long phrases, the keywords may be too specific.
→ Check what keywords are being used: add logging to gather_prediction_signals.

**Newsletter doesn't show Prediction Tracker section:**
→ Check that predictions data was included in the newsletter agent's input_data.
→ Check the Newsletter identity was updated: `cat data/openclaw/agents/newsletter/agent/IDENTITY.md | grep -i "prediction"`
→ Restart newsletter agent: `docker compose restart newsletter`
