# AgentPulse Phase 2: Cursor Prompts

> **How to use:** Run these prompts in order. Upload `AGENTPULSE_PHASE2_ARCHITECTURE.md` and `AGENTPULSE_MULTIAGENT_PLAN_v2.md` as context. Test between each prompt.

> **IMPORTANT:** Before starting, make sure the delegation fix is working. Send `/scan` to Gato on Telegram — it should say "Scan initiated, Analyst is working on it..." and the processor logs should show a `create_agent_task` being processed. If Gato is still running the pipeline directly, restart it: `docker compose restart gato`

---

## Prompt 1: Supabase Schema Updates (Manual — SQL Editor)

Run this in your Supabase SQL Editor. No Cursor needed.

```sql
-- ================================================
-- PHASE 2 SCHEMA UPDATES
-- Run in Supabase SQL Editor
-- ================================================

-- 1. Add cluster linkage to problems
ALTER TABLE problems ADD COLUMN IF NOT EXISTS cluster_id UUID REFERENCES problem_clusters(id);
CREATE INDEX IF NOT EXISTS idx_problems_cluster ON problems(cluster_id);

-- 2. Opportunity score function
CREATE OR REPLACE FUNCTION compute_opportunity_score(
    p_frequency INT,
    p_max_frequency INT,
    p_last_seen TIMESTAMPTZ,
    p_wtp TEXT,
    p_solution_gap TEXT
)
RETURNS FLOAT AS $$
DECLARE
    freq_weight FLOAT;
    recency_weight FLOAT;
    wtp_weight FLOAT;
    gap_weight FLOAT;
    days_ago FLOAT;
BEGIN
    IF p_max_frequency > 1 THEN
        freq_weight := ln(GREATEST(p_frequency, 1)::FLOAT) / ln(p_max_frequency::FLOAT);
    ELSE
        freq_weight := 1.0;
    END IF;

    days_ago := EXTRACT(EPOCH FROM (NOW() - p_last_seen)) / 86400.0;
    IF days_ago < 7 THEN recency_weight := 1.0;
    ELSIF days_ago < 30 THEN recency_weight := 0.7;
    ELSE recency_weight := 0.3;
    END IF;

    CASE p_wtp
        WHEN 'explicit' THEN wtp_weight := 1.0;
        WHEN 'implied' THEN wtp_weight := 0.5;
        ELSE wtp_weight := 0.0;
    END CASE;

    CASE p_solution_gap
        WHEN 'none' THEN gap_weight := 1.0;
        WHEN 'inadequate' THEN gap_weight := 0.5;
        ELSE gap_weight := 0.0;
    END CASE;

    RETURN (freq_weight * 0.3) + (recency_weight * 0.2) + (wtp_weight * 0.3) + (gap_weight * 0.2);
END;
$$ LANGUAGE plpgsql;

-- 3. Tool stats table (aggregated from tool_mentions)
CREATE TABLE tool_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tool_name TEXT UNIQUE NOT NULL,
    total_mentions INT DEFAULT 0,
    mentions_7d INT DEFAULT 0,
    mentions_30d INT DEFAULT 0,
    avg_sentiment FLOAT DEFAULT 0.0,
    sentiment_trend FLOAT DEFAULT 0.0,
    recommendation_count INT DEFAULT 0,
    complaint_count INT DEFAULT 0,
    top_alternatives TEXT[],
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tool_stats_mentions ON tool_stats(total_mentions DESC);
CREATE INDEX idx_tool_stats_name ON tool_stats(tool_name);

-- 4. Trending tools view
CREATE OR REPLACE VIEW trending_tools AS
SELECT
    ts.*,
    CASE
        WHEN mentions_7d > 0 AND mentions_30d > 0
        THEN (mentions_7d::FLOAT / GREATEST(mentions_30d::FLOAT / 4.3, 1))
        ELSE 0
    END as momentum_score
FROM tool_stats ts
WHERE last_seen > NOW() - INTERVAL '30 days'
ORDER BY momentum_score DESC, total_mentions DESC
LIMIT 20;

-- 5. Tool warnings view
CREATE OR REPLACE VIEW tool_warnings AS
SELECT *
FROM tool_stats
WHERE avg_sentiment < -0.3
  AND total_mentions >= 3
  AND last_seen > NOW() - INTERVAL '30 days'
ORDER BY avg_sentiment ASC;

-- 6. Newsletters table
CREATE TABLE newsletters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    edition_number INT NOT NULL,
    title TEXT NOT NULL,
    content_markdown TEXT NOT NULL,
    content_telegram TEXT,
    data_snapshot JSONB,
    status TEXT DEFAULT 'draft',
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_newsletters_status ON newsletters(status);
CREATE INDEX idx_newsletters_edition ON newsletters(edition_number DESC);

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

**Verify:** Check Supabase Table Editor — you should see `tool_stats` and `newsletters` as new tables, and `problems` should now have a `cluster_id` column.

---

## Prompt 2: Add Problem Clustering to Processor

```
I need to add problem clustering to docker/processor/agentpulse_processor.py. This is the missing step between problem extraction and opportunity generation.

Reference: AGENTPULSE_PHASE2_ARCHITECTURE.md, Part 1.

Add these things to agentpulse_processor.py:

1. Add a CLUSTERING_PROMPT constant (near the other prompts like PROBLEM_EXTRACTION_PROMPT and OPPORTUNITY_PROMPT). The prompt should:
   - Take a list of problems as JSON
   - Group them into 3-10 thematic clusters
   - For each cluster return: theme, description, problem_ids, combined_severity, willingness_to_pay (none/implied/explicit), solution_gap (none/inadequate/solved)
   - Respond only with valid JSON

2. Add a cluster_problems(min_problems=3) function that:
   - Fetches unclustered problems from Supabase where cluster_id IS NULL
   - If fewer than min_problems, returns early
   - Formats them for the prompt (id, description, category, frequency, severity, wtp)
   - Calls OpenAI with the clustering prompt
   - For each returned cluster:
     a. Computes opportunity_score using the formula:
        score = (frequency_weight * 0.3) + (recency_weight * 0.2) + (wtp_weight * 0.3) + (gap_weight * 0.2)
        Where: freq_weight = log(total_mentions)/log(max_frequency), recency 1.0/<7d 0.7/<30d 0.3/else, wtp explicit=1/implied=0.5/none=0, gap none=1/inadequate=0.5/solved=0
     b. Inserts into problem_clusters table with theme, description, problem_ids, total_mentions, avg_recency_days, opportunity_score, market_validation JSONB
     c. Updates each problem's cluster_id to link it to the cluster
   - Logs pipeline start/end
   - Returns {problems_processed, clusters_created}
   - Add `import math` at the top if not already there

3. REWRITE the existing generate_opportunities() function to work from clusters instead of individual problems:
   - Query problem_clusters ordered by opportunity_score DESC
   - Filter out clusters that already have opportunities (check opportunities table for existing cluster_id matches)
   - For each new cluster, generate an opportunity using the existing OPPORTUNITY_PROMPT
   - Pass the cluster data (theme, description, total_mentions, recency, market_validation) as the problem_data
   - Store with cluster_id linkage: update store_opportunity() to accept cluster_id and include it in the record
   - Remove the old min_frequency parameter — it's now min_score (float, default 0.3) filtering on opportunity_score

4. Update the run_pipeline task in execute_task() to include clustering:
   scrape → extract_problems → cluster_problems → generate_opportunities
   Return all 4 results.

5. Add 'cluster_problems' as a standalone task in execute_task():
   elif task_type == 'cluster_problems':
       return cluster_problems(min_problems=params.get('min_problems', 3))

6. Add clustering to the scheduler in setup_scheduler():
   schedule.every(12).hours.do(scheduled_cluster)
   And add a scheduled_cluster() function that calls cluster_problems().

Don't modify any other existing functions (scrape_moltbook, extract_problems, fetch_moltbook_posts, etc.) except generate_opportunities() and store_opportunity() as described above.
```

**After this:** Deploy and test:
```bash
cd bitcoin_bot/docker
docker compose build processor --no-cache
docker compose up processor -d
# Test clustering
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task analyze
# Check Supabase — problem_clusters should now have rows
# Check that problems now have cluster_id values
```

---

## Prompt 3: Add Pipeline 2 — Investment Scanner

```
Add Pipeline 2 (Investment Scanner) to docker/processor/agentpulse_processor.py. This extracts tool/product mentions from Moltbook posts and tracks sentiment and trends.

Reference: AGENTPULSE_PHASE2_ARCHITECTURE.md, Part 2.

Add these things:

1. Add a TOOL_EXTRACTION_PROMPT constant. The prompt should:
   - Take posts as text
   - Extract every tool, product, service, platform, library, or framework mention
   - For each: tool_name (normalized, e.g. "LangChain" not "langchain"), tool_name_raw (as written), context (surrounding sentence), sentiment_score (-1.0 to 1.0), sentiment_label, is_recommendation (bool), is_complaint (bool), alternative_mentioned (e.g. "switched from X to Y" or null), source_post_id
   - Rules: include languages/frameworks/APIs/platforms/SaaS, normalize names, one mention per tool per post, skip generic terms like "API" or "database" unless specific product
   - Respond only with valid JSON

2. Add extract_tool_mentions(hours_back=48) function that:
   - Fetches posts from moltbook_posts from the last hours_back hours (use scraped_at, limit 100)
   - Sends to OpenAI with TOOL_EXTRACTION_PROMPT
   - For each mention: looks up the internal post UUID from moltbook_id, inserts into tool_mentions table
   - Logs pipeline start/end
   - Returns {posts_scanned, mentions_found}

3. Add update_tool_stats() function that:
   - Gets all unique tool_name values from tool_mentions
   - For each tool: computes total_mentions, mentions_7d, mentions_30d, avg_sentiment, recommendation_count, complaint_count, top_alternatives (up to 5), first_seen, last_seen
   - Upserts into tool_stats table (check if exists by tool_name, update or insert)
   - Logs pipeline start/end
   - Returns {tools_updated}

4. Add these task types to execute_task():
   - 'extract_tools' → extract_tool_mentions(hours_back)
   - 'update_tool_stats' → update_tool_stats()
   - 'run_investment_scan' → extract_tool_mentions(hours_back=168) then update_tool_stats(), return both results

5. Add to setup_scheduler():
   - schedule.every(12).hours.do(scheduled_tool_scan)  # extract tool mentions
   - schedule.every().day.at("06:00").do(scheduled_update_stats)  # recompute stats
   And the corresponding scheduled_tool_scan() and scheduled_update_stats() functions.

6. Add 'extract_tools', 'update_tool_stats', and 'run_investment_scan' to the argparse --task choices.

Don't modify any existing functions — only add new code.
```

**After this:** Deploy and test:
```bash
docker compose build processor --no-cache
docker compose up processor -d
# Test tool extraction
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task extract_tools
# Check Supabase — tool_mentions should have rows
# Test stats computation
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task update_tool_stats
# Check tool_stats table
```

---

## Prompt 4: Refactor Newsletter — Processor Delegates to Newsletter Agent

> **CONTEXT:** You already ran the old Prompt 4 which added `generate_newsletter()` that calls OpenAI directly from the processor. We're changing the architecture: the processor should only gather data and delegate the actual writing to a separate Newsletter agent (an OpenClaw agent with its own editorial voice). This prompt removes the old approach and replaces it.

```
Refactor the newsletter code in docker/processor/agentpulse_processor.py. The old design had the processor generating the newsletter directly via OpenAI. The new design has the processor gather data and delegate writing to a Newsletter agent via the agent_tasks table.

Reference: AGENTPULSE_NEWSLETTER_AGENT.md for the new architecture.

HERE'S WHAT TO CHANGE:

1. REMOVE these things that were added by the old Prompt 4:
   - Remove the NEWSLETTER_PROMPT constant (the Newsletter agent has its own voice/prompts via its IDENTITY.md)
   - Remove the generate_newsletter() function entirely
   - Remove the 'generate_newsletter' case from execute_task()
   - Remove scheduled_newsletter() if it calls generate_newsletter()
   - Remove 'generate_newsletter' from the argparse --task choices
   - Keep publish_newsletter and get_latest_newsletter if they exist — those are still needed
   - Keep the newsletters table interaction code (store/query) — the newsletter agent will write to it, and the processor reads from it for publishing

2. ADD a new prepare_newsletter_data() function that:
   - Gathers all data the Newsletter agent needs from Supabase (last 7 days):
     * Top 5 opportunities (ordered by confidence_score DESC)
     * Top 10 tools from tool_stats (ordered by mentions_7d DESC)
     * Tool warnings (avg_sentiment < -0.3 AND total_mentions >= 3)
     * Recent problem clusters (last 7 days, ordered by opportunity_score DESC, limit 10)
     * Stats: post count this week (moltbook_posts where scraped_at in last 7d), problems count (problems where first_seen in last 7d), tools tracked count (from tool_stats), new opportunities count
   - Gets next edition number via supabase.rpc('next_newsletter_edition')
   - Creates an agent_task for the Newsletter agent:
     {
       'task_type': 'write_newsletter',
       'assigned_to': 'newsletter',
       'created_by': 'processor',
       'priority': 3,
       'input_data': {
         'edition_number': edition_number,
         'opportunities': opportunities_data,
         'trending_tools': tools_data,
         'tool_warnings': warnings_data,
         'clusters': clusters_data,
         'stats': {
           'posts_count': N,
           'problems_count': N,
           'tools_count': N,
           'new_opps_count': N
         }
       }
     }
   - IMPORTANT: Use json.dumps with default=str when serializing any datetime objects before inserting into agent_tasks
   - Logs pipeline start/end
   - Returns {'edition_number': N, 'task_id': '<uuid>', 'status': 'delegated_to_newsletter'}

3. ADD/KEEP a publish_newsletter() function (keep it if it already exists, add if not):
   - Queries newsletters table for latest row where status='draft', ordered by created_at DESC
   - If found: sends content_telegram via send_telegram(), updates status to 'published' and sets published_at
   - Returns {'published': id, 'edition': edition_number}
   - If no draft: returns {'error': 'No draft newsletter found'}

4. ADD/KEEP a get_latest_newsletter() function:
   - Queries newsletters table ordered by created_at DESC, limit 1
   - Returns the full row data

5. UPDATE execute_task() — replace old newsletter tasks with:
   - 'prepare_newsletter' → prepare_newsletter_data()
   - 'publish_newsletter' → publish_newsletter()
   - 'get_latest_newsletter' → get_latest_newsletter()
   - Remove 'generate_newsletter' if it still exists

6. UPDATE setup_scheduler():
   - Replace any scheduled_newsletter that calls generate_newsletter with:
     schedule.every().monday.at("07:00").do(scheduled_prepare_newsletter)
   - Keep or add:
     schedule.every().monday.at("08:00").do(scheduled_notify_newsletter)
   - scheduled_prepare_newsletter() calls prepare_newsletter_data()
   - scheduled_notify_newsletter() calls send_telegram("📰 New AgentPulse Brief is ready for review. Send /newsletter to see it.")

7. UPDATE argparse --task choices:
   - Remove 'generate_newsletter' if present
   - Add 'prepare_newsletter' if not present
   - Keep 'publish_newsletter'

The key conceptual change: the processor NO LONGER calls OpenAI to write the newsletter. It gathers data and creates a task for the Newsletter agent. The Newsletter agent (a separate OpenClaw container with Anthropic) does the actual writing with its own editorial voice.

Don't modify any other existing functions — only change newsletter-related code.
```

**After this:** Deploy and test:
```bash
docker compose build processor --no-cache
docker compose up processor -d

# Test the new delegation flow
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_newsletter

# Check Supabase:
# - agent_tasks table should have a NEW row with:
#   task_type='write_newsletter', assigned_to='newsletter', status='pending'
#   input_data should contain opportunities, tools, clusters, stats
#
# - The Newsletter agent (once running from Prompt 5) will pick this up and write the brief
# - For now, the task will just sit as 'pending' until the Newsletter container is deployed

# Verify old code is gone:
docker compose exec processor grep -n "NEWSLETTER_PROMPT\|generate_newsletter" /home/openclaw/agentpulse_processor.py
# Should return nothing (or only the argparse/execute_task references to prepare_newsletter)
```

---

## Prompt 5: Newsletter Agent — Full OpenClaw Agent with Editorial Voice

> **IMPORTANT:** This is a real OpenClaw agent, not a lightweight worker. It has its own editorial voice controlled by identity files. Upload AGENTPULSE_NEWSLETTER_AGENT.md as additional context for this prompt.

```
Create the Newsletter agent as a full OpenClaw agent with editorial capabilities. This agent writes the weekly AgentPulse Intelligence Brief with a distinctive voice inspired by Benedict Evans, Lenny Rachitsky, Eric Newcomer, Ben Thompson, and Om Malik.

Reference: AGENTPULSE_NEWSLETTER_AGENT.md for the full architecture and persona details.

1. Create docker/newsletter/Dockerfile:
   - Based on node:22-slim (IMPORTANT: must be 22+, OpenClaw requires Node >= 22.12.0)
   - Install git, curl, bash, jq, python3, python3-pip
   - Create openclaw user
   - Install OpenClaw via npm
   - Install Python requirements (httpx, supabase, python-dotenv)
   - Copy entrypoint.sh AND newsletter_poller.py
   - ENTRYPOINT: entrypoint.sh

2. Create docker/newsletter/newsletter_poller.py:
   This is a sidecar script that bridges the agent_tasks Supabase table to the file-based queue that the OpenClaw agent reads from. It:
   - Polls agent_tasks every 30 seconds for tasks where assigned_to='newsletter' and status='pending'
   - For each task: marks it as in_progress, writes a JSON file to workspace/agentpulse/queue/ with the task data
   - Also watches workspace/agentpulse/queue/responses/ for newsletter_*.result.json files
   - When it finds a response: reads it, updates the agent_tasks row as completed/failed with output_data/error_message, deletes the response file
   - Runs in an infinite loop with try/except so it doesn't crash on transient errors
   - Logs to stdout

3. Create docker/newsletter/entrypoint.sh:
   - Creates workspace dirs (agentpulse/newsletters, agentpulse/queue/responses)
   - Creates logs dir
   - Starts newsletter_poller.py in the background (nohup, log to newsletter-poller.log)
   - Starts OpenClaw with: exec openclaw start --agent newsletter --headless

4. Create docker/newsletter/requirements.txt:
   httpx>=0.25.0
   supabase>=2.0.0
   python-dotenv>=1.0.0

5. Add the newsletter service to docker/docker-compose.yml:
   - Same pattern as analyst service
   - container_name: agentpulse-newsletter
   - Environment: common env vars + ANTHROPIC_API_KEY + AGENT_NAME=newsletter
   - Volumes:
     * ../data/openclaw/agents/newsletter mounted to /home/openclaw/.openclaw/agents/newsletter
     * shared workspace-data volume
     * ../skills read-only
     * ../config read-only
   - mem_limit: 512m (it uses Anthropic for writing)
   - depends_on: processor
   - restart: unless-stopped
   - Same logging config as other services

6. Create data/openclaw/agents/newsletter/agent/IDENTITY.md:
   Copy the FULL content from AGENTPULSE_NEWSLETTER_AGENT.md section "Newsletter Agent Identity" — this is the detailed persona with voice guidelines, writing constraints, structure, and Gato's Corner instructions. Do NOT shorten or summarize it — the detail is what makes the voice work.

7. Create data/openclaw/agents/newsletter/agent/SOUL.md:
   "I distill signal from noise. A week of agent economy chatter becomes three minutes of insight. I have opinions, but they're earned from data. I don't hype. I don't dismiss. I analyze. Every edition I write should make the reader feel like they have an unfair information advantage. That's the standard. The best newsletters make you feel smarter in less time. That's what I aim for. Not comprehensive — essential."

8. Copy auth-profiles.json:
   cp data/openclaw/agents/main/agent/auth-profiles.json data/openclaw/agents/newsletter/agent/auth-profiles.json

9. Create skills/newsletter/package.json:
   {
     "name": "newsletter",
     "version": "1.0.0",
     "description": "Newsletter agent skills for writing AgentPulse Intelligence Briefs",
     "skills": ["newsletter"],
     "author": "AgentPulse"
   }

10. Create skills/newsletter/SKILL.md:
    Copy the full SKILL.md content from AGENTPULSE_NEWSLETTER_AGENT.md — it describes the write_newsletter and revise_newsletter task types, output formats, and how the agent reads from the file queue and writes responses.

11. Update data/openclaw/openclaw.json to include the newsletter agent:
    agents array should have: gato, analyst, newsletter (all enabled)

Don't modify any existing files except docker-compose.yml and openclaw.json.
```

**After this:**
```bash
docker compose build newsletter --no-cache
docker compose up -d
docker compose ps  # Should show 4 services: gato, analyst, processor, newsletter
docker compose logs newsletter | tail -30
# Verify it starts without the Node version error (should be 22+)
```

---

## Prompt 6: Update Gato's Instructions for New Commands

```
Update Gato's instruction files to add all the new Phase 2 commands. These files are volume-mounted so changes take effect after restarting gato.

1. Update data/openclaw/workspace/AGENTS.md — add these to the command mapping section:

   New Pipeline 2 commands:
   - /tools → write {"task":"get_tool_stats","params":{"limit":10}} to the queue
   - /tool [name] → write {"task":"get_tool_detail","params":{"tool_name":"<name>"}} to the queue
   - /invest-scan → Delegate to Analyst: write {"task":"create_agent_task","params":{"task_type":"run_investment_scan","assigned_to":"analyst","created_by":"gato","input_data":{"hours_back":168}}} to the queue. Tell user "Investment scan initiated..."

   New Newsletter commands:
   - /newsletter → write {"task":"get_latest_newsletter","params":{}} to the queue. Display the content_telegram version. If no newsletter exists yet, tell the user.
   - /newsletter-full → Delegate: write {"task":"create_agent_task","params":{"task_type":"prepare_newsletter","assigned_to":"processor","created_by":"gato","input_data":{}}} to the queue. This triggers processor to gather data and delegate writing to the Newsletter agent. Tell user "Generating newsletter... the Newsletter agent will write it."
   - /newsletter-publish → write {"task":"publish_newsletter","params":{}} to the queue. Tell user "Publishing..."
   - /newsletter-revise [feedback] → Delegate: write {"task":"create_agent_task","params":{"task_type":"revise_newsletter","assigned_to":"newsletter","created_by":"gato","input_data":{"feedback":"<user's feedback text>"}}} to the queue. Tell user "Sending revision feedback to the Newsletter agent..."

2. Update skills/agentpulse/SKILL.md — add to the Telegram Commands table:
   | /tools | Get top 10 trending tools |
   | /tool [name] | Get stats for a specific tool |
   | /invest-scan | Trigger investment scan (delegated to Analyst) |
   | /newsletter | Show latest newsletter |
   | /newsletter-full | Generate new newsletter (processor gathers data → newsletter agent writes) |
   | /newsletter-publish | Publish draft newsletter to Telegram |
   | /newsletter-revise [feedback] | Send revision feedback to Newsletter agent |

   Also add a "Pipeline 2: Investment Scanner" section explaining:
   - Tool mentions are extracted from Moltbook posts automatically
   - Stats are aggregated daily
   - /tools shows trending tools with sentiment and momentum
   - /invest-scan triggers a manual scan

   And a "Newsletter" section explaining:
   - Weekly intelligence brief written by a dedicated Newsletter agent with its own editorial voice
   - Generated every Monday: processor gathers data, Newsletter agent writes it
   - /newsletter shows the condensed Telegram version
   - /newsletter-publish sends it out
   - /newsletter-revise lets you give feedback to the Newsletter agent to rewrite

3. Also add these task handlers to the processor. In execute_task(), add:

   'get_tool_stats':
   - Query tool_stats ordered by total_mentions DESC, limit from params (default 10)
   - Return the rows

   'get_tool_detail':
   - Query tool_stats where tool_name = params['tool_name']
   - Also query recent tool_mentions for that tool (last 30 days, limit 10)
   - Return {stats: row, recent_mentions: [...]}

   'get_latest_newsletter':
   - Query newsletters ordered by created_at DESC, limit 1
   - Return the row

Don't modify anything else.
```

**After this:**
```bash
# Rebuild processor for new task handlers
docker compose build processor --no-cache
docker compose up processor -d

# Restart gato to pick up new instructions
docker compose restart gato

# Test on Telegram:
# /tools — should return tool stats (may be empty until first scan runs)
# /invest-scan — should delegate to analyst
# /newsletter — should return latest newsletter (or "none yet")
```

---

## Post-Phase 2 Verification Checklist

Run these after all prompts are deployed:

```bash
# 1. All services running
docker compose ps
# Expected: gato, analyst, processor, newsletter — all "Up"

# 2. Full pipeline test (clustering + opportunities from clusters)
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task analyze
# Check Supabase: problem_clusters should have rows, opportunities should reference cluster_ids

# 3. Investment scanner test
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task run_investment_scan
# Check Supabase: tool_mentions and tool_stats should have rows

# 4. Newsletter test — this is a multi-step flow now
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_newsletter
# Check Supabase: agent_tasks should have a write_newsletter task assigned to 'newsletter'
# Wait 30-60 seconds for the newsletter agent to pick it up
docker compose logs newsletter | tail -30
# Check Supabase: newsletters table should have a draft

# 5. Telegram commands
# Send these to @gato_beedi_ragabot:
# /pulse-status    → system status
# /scan            → should delegate to analyst
# /tools           → tool stats
# /invest-scan     → should delegate to analyst
# /newsletter      → latest newsletter
# /crew-status     → agent task summary

# 6. Check all tables have data
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY'))
for table in ['moltbook_posts','problems','problem_clusters','opportunities','tool_mentions','tool_stats','newsletters','agent_tasks']:
    try:
        r = c.table(table).select('id', count='exact').limit(0).execute()
        print(f'{table}: {r.count} rows')
    except Exception as e:
        print(f'{table}: ERROR - {e}')
"
```

---

## Troubleshooting

**Clustering produces 0 clusters:**
→ Check that there are unclustered problems: query `problems` where `cluster_id IS NULL`
→ The min_problems default is 3 — you need at least 3 unclustered problems

**Tool extraction finds nothing:**
→ Check that posts have content about tools (some posts may be purely opinion/meme)
→ Try with a larger hours_back: `--task extract_tools` uses 48h default, try manually with 168h (7 days)

**Newsletter generation fails:**
→ It needs data from both pipelines. Run a full scan first (`--task analyze` then `--task run_investment_scan`) before generating

**Gato ignores new commands:**
→ Restart gato: `docker compose restart gato`
→ OpenClaw caches instruction files at session start

**Newsletter container exits:**
→ Check logs: `docker compose logs newsletter`
→ If Node version error: make sure Dockerfile uses node:22-slim not node:20-slim
→ If OpenClaw --headless not supported: check the analyst container — if analyst works, newsletter should too

**Newsletter task stays pending:**
→ Check newsletter poller is running: `docker compose exec newsletter ps aux | grep poller`
→ Check poller logs: `docker compose exec newsletter cat /home/openclaw/.openclaw/logs/newsletter-poller.log`
→ The poller bridges agent_tasks to the file queue — if it's not running, the OpenClaw agent never sees the task

**Newsletter quality is bad:**
→ Edit data/openclaw/agents/newsletter/agent/IDENTITY.md to adjust voice
→ Restart: `docker compose restart newsletter`
→ Use /newsletter-revise with specific feedback
