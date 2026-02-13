# AgentPulse Phase 3 Week 1: Cursor Prompts

> **Upload `AGENTPULSE_PHASE3_WEEK1.md` as context for every prompt.**

---

## Prompt 1: Security — .gitignore and Secrets Audit

```
Perform a security audit on the bitcoin_bot repository. Check for exposed secrets and fix .gitignore.

1. Check the current .gitignore file. Make sure it includes ALL of these entries (add any that are missing):

   # Secrets
   config/.env
   config/.env.*
   !config/env.example
   
   # OpenClaw auth (contains API keys)
   data/openclaw/agents/*/agent/auth-profiles.json
   
   # OpenClaw session data
   data/openclaw/agents/*/agent/session/
   data/openclaw/agents/*/agent/*.session
   
   # Runtime data
   data/openclaw/workspace/
   data/openclaw/logs/
   
   # Python
   *.pyc
   __pycache__/
   .env

2. Check if any secrets have been committed to git history. Run:
   git log --all --full-history -p -- config/.env
   git log --all --full-history -p -- "data/openclaw/agents/*/agent/auth-profiles.json"
   git log --all --full-history -p -- "*.env"
   
   If ANY results show actual API keys (not placeholders), list them so we know which keys need to be rotated.

3. Check all source files for hardcoded secrets. Search for:
   - "sk-ant-" (Anthropic key prefix)
   - "sk-" followed by long alphanumeric strings (OpenAI key prefix)
   - "eyJ" (Supabase JWT key prefix)
   - Any hardcoded URLs with keys in query parameters
   
   Run: grep -r "sk-ant-\|sk-proj-\|sk-[a-zA-Z0-9]\{20,\}\|eyJ[a-zA-Z0-9]\{20,\}" --include="*.py" --include="*.sh" --include="*.yml" --include="*.yaml" --include="*.json" --include="*.md" --include="*.js" . 
   
   Exclude: config/env.example (that's fine), node_modules/, .git/

4. Check docker-compose.yml — make sure no API keys appear as literal values. They should all be ${VARIABLE_NAME} references to .env, never raw strings.

5. Check if config/.env is properly NOT tracked:
   git status config/.env
   Should show nothing (untracked/ignored). If it shows as tracked, run:
   git rm --cached config/.env

6. Scrub architecture docs that might be committed. Check AGENTPULSE_ARCHITECTURE.md, AGENTPULSE_STATUS.md, PROJECT_OVERVIEW.md for:
   - Real server IP addresses (46.224.50.251) — replace with <SERVER_IP>
   - Real Supabase URLs — replace with <SUPABASE_URL>
   - Real bot names — replace with <BOT_NAME>
   - Real GitHub repo URLs if the repo is private (check: is the repo public or private?)
   
   Only scrub these in committed versions. Don't change your local working copies.

Report what you find. Don't change any API keys — just tell me which ones may be exposed so I can rotate them.
```

**After this:** If any keys were found in git history, rotate them:
- Anthropic: https://console.anthropic.com/
- OpenAI: https://platform.openai.com/api-keys
- Supabase: Project Settings → API (regenerate anon key)
- Telegram: @BotFather → /revoke
- Then update config/.env and all auth-profiles.json files on the server

---

## Prompt 2: Security — Supabase RLS + Service Key

> **Do the SQL part manually in Supabase SQL Editor, then use Cursor for the code changes.**

### 2A: SQL — Run in Supabase SQL Editor:

```sql
-- ================================================
-- SUPABASE ROW LEVEL SECURITY
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

-- PUBLIC ACCESS (safe for anon key / frontend)
-- Only published newsletters
CREATE POLICY "Public read published newsletters"
ON newsletters FOR SELECT
USING (status = 'published');

-- Tool stats are non-sensitive aggregates
CREATE POLICY "Public read tool stats"
ON tool_stats FOR SELECT
USING (true);

-- Note: All other tables have NO public SELECT policy,
-- so anon key cannot read them. Only service_role key can.
```

**IMPORTANT:** After enabling RLS, your processor and agents need to use the **service role key** (not anon key) to read/write data. Get the service role key from Supabase: Project Settings → API → service_role key.

### 2B: Cursor Prompt — Switch to service role key for backend

```
Update the AgentPulse system to use Supabase service role key for all backend services. Row Level Security (RLS) has been enabled, so the anon key can no longer read most tables.

1. Add a new env var to config/.env (and config/env.example as a placeholder):
   SUPABASE_SERVICE_KEY=<your-service-role-key>
   
   Keep the existing SUPABASE_KEY (anon key) — it will be used for the future web frontend.

2. Update docker/docker-compose.yml:
   In the common env anchor (&common-env), add:
   SUPABASE_SERVICE_KEY: ${SUPABASE_SERVICE_KEY}
   
   Keep SUPABASE_KEY in the anchor too (some services may need both).

3. Update docker/processor/agentpulse_processor.py:
   Change the Supabase client initialization to use SUPABASE_SERVICE_KEY instead of SUPABASE_KEY:
   
   SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY', os.getenv('SUPABASE_KEY'))
   
   Then use SUPABASE_SERVICE_KEY when creating the client:
   supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
   
   This falls back to SUPABASE_KEY if service key isn't set (backward compat).

4. Update docker/analyst/analyst_poller.py:
   Same change — use SUPABASE_SERVICE_KEY for the client.

5. Update docker/newsletter/newsletter_poller.py:
   Same change — use SUPABASE_SERVICE_KEY for the client.

Don't change any other logic — just the Supabase key used for client initialization.
```

**After this:**
```bash
# Add the service role key to .env on the server
ssh root@46.224.50.251
# Get the service_role key from Supabase dashboard: Project Settings → API
echo "SUPABASE_SERVICE_KEY=eyJ..." >> ~/bitcoin_bot/config/.env

# Rebuild and restart
cd ~/bitcoin_bot/docker
docker compose build --no-cache
docker compose up -d

# Test that services can still read/write
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task status
```

---

## Prompt 3: Security — Server Firewall

> **Run this directly on the server, no Cursor needed.**

```bash
ssh root@46.224.50.251

# Check current firewall
sudo ufw status

# If inactive, set it up:
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
# Don't add 443 yet — we'll do that when the web archive is deployed
sudo ufw enable

# Verify no Docker ports are exposed to the host
docker compose -f ~/bitcoin_bot/docker/docker-compose.yml ps
# None of the services should show port mappings (no "0.0.0.0:PORT->PORT" entries)
```

---

## Prompt 4: Content — Database Schema Updates

Run in Supabase SQL Editor:

```sql
-- ================================================
-- CONTENT UPGRADE SCHEMA
-- ================================================

-- 1. Staleness tracking on opportunities
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS newsletter_appearances INT DEFAULT 0;
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS last_featured_at TIMESTAMPTZ;
ALTER TABLE opportunities ADD COLUMN IF NOT EXISTS first_featured_at TIMESTAMPTZ;

-- 2. Trending topics table (for Curious Corner)
CREATE TABLE IF NOT EXISTS trending_topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    topic_type TEXT NOT NULL,          -- 'debate', 'cultural', 'surprising', 'meta', 'technical'
    source_post_ids TEXT[],
    engagement_score FLOAT DEFAULT 0,
    novelty_score FLOAT DEFAULT 0,
    extracted_at TIMESTAMPTZ DEFAULT NOW(),
    featured_in_newsletter BOOLEAN DEFAULT FALSE,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_trending_topics_type ON trending_topics(topic_type);
CREATE INDEX IF NOT EXISTS idx_trending_topics_extracted ON trending_topics(extracted_at DESC);

-- 3. RLS for trending_topics (public readable)
ALTER TABLE trending_topics ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read trending topics"
ON trending_topics FOR SELECT USING (true);

-- Service role needs write access (auto-granted, bypasses RLS)
```

---

## Prompt 5: Content — Trending Topics Extraction in Processor

```
Add trending topics extraction to docker/processor/agentpulse_processor.py. This is a NEW extraction step that runs alongside problem extraction, looking for interesting/curious content rather than business problems.

Reference: AGENTPULSE_PHASE3_WEEK1.md, Part 2C.

1. Add a TRENDING_TOPICS_PROMPT constant:

   "You analyze social media posts by AI agents for interesting, surprising, or culturally significant conversations. You are NOT looking for business problems or complaints — you are looking for what makes the agent economy INTERESTING.

   Look for:
   1. Debates: Agents disagreeing about approaches, philosophies, or tools
   2. Cultural moments: Community milestones, memes, inside jokes, traditions forming
   3. Surprising usage: Agents doing unexpected or creative things with tools
   4. Meta discussions: Agents talking about the nature of the agent economy itself
   5. Technical novelty: New approaches, unexpected tool combinations, emerging patterns

   Posts to analyze:
   {posts}

   For each interesting topic found, provide:
   - title: Catchy 5-8 word title
   - description: 2-3 sentences explaining what's interesting and why a reader would care
   - topic_type: One of [debate, cultural, surprising, meta, technical]
   - engagement_score: 0.0-1.0 based on how much discussion/engagement the topic has
   - novelty_score: 0.0-1.0 based on how new or unexpected this topic is
   - source_post_ids: List of relevant post moltbook_ids
   - why_interesting: One sentence hook for why someone should care

   Respond ONLY with valid JSON:
   {
     \"topics\": [
       {
         \"title\": \"...\",
         \"description\": \"...\",
         \"topic_type\": \"...\",
         \"engagement_score\": 0.0,
         \"novelty_score\": 0.0,
         \"source_post_ids\": [\"...\"],
         \"why_interesting\": \"...\"
       }
     ]
   }

   Find 3-8 topics. Quality over quantity. Skip anything boring or generic.
   These should make someone say 'huh, that's interesting' not 'yeah, obviously.'"

2. Add extract_trending_topics(hours_back=48) function that:
   - Fetches recent posts from moltbook_posts (last hours_back hours, limit 100)
   - Calls OpenAI with TRENDING_TOPICS_PROMPT (use the extraction model — gpt-4o-mini when we optimize, gpt-4o for now)
   - For each topic returned: inserts into trending_topics table with title, description, topic_type, source_post_ids, engagement_score, novelty_score
   - Logs pipeline start/end
   - Returns {posts_scanned, topics_found}

3. Add 'extract_trending_topics' to execute_task():
   elif task_type == 'extract_trending_topics':
       return extract_trending_topics(hours_back=params.get('hours_back', 48))

4. Add to the run_pipeline task flow:
   After extract_tool_mentions(), add: trending_result = extract_trending_topics()
   Include in the return dict.

5. Add to setup_scheduler():
   Schedule trending topic extraction every 12 hours (alongside analysis).
   Add a scheduled_trending_topics() function.

6. Add 'extract_trending_topics' to argparse --task choices.

Don't modify any existing functions — only add new code.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task extract_trending_topics
# Check Supabase: trending_topics table should have rows
```

---

## Prompt 6: Content — Newsletter Staleness Filtering + 3-Section Data

```
Update prepare_newsletter_data() in docker/processor/agentpulse_processor.py to gather data for the new 3-section newsletter format: Established Opportunities, Emerging Signals, and Curious Corner.

Reference: AGENTPULSE_PHASE3_WEEK1.md, Part 2F.

Changes to prepare_newsletter_data():

1. REPLACE the current opportunities query with staleness-aware selection:
   - Fetch all draft opportunities with confidence_score > 0.3
   - In Python, compute effective_score for each:
     appearances = opp.get('newsletter_appearances', 0)
     effective_score = opp['confidence_score'] * (0.7 ** appearances)
     
     # Boost if new analyst review since last featured
     last_featured = opp.get('last_featured_at')
     last_reviewed = opp.get('last_reviewed_at')
     if last_featured and last_reviewed and last_reviewed > last_featured:
         effective_score *= 1.3
   
   - Sort by effective_score descending
   - Take top 5
   - Include the effective_score and appearances count in the data sent to the newsletter agent

2. ADD an emerging_signals query:
   - Query problems where:
     first_seen >= 7 days ago AND frequency_count < 5
   - Also query problem_clusters where:
     created_at >= 7 days ago AND opportunity_score > 0.3
   - Combine and deduplicate
   - Include the raw signal_phrases from the problems
   - Limit to 10 items (Newsletter agent picks 2-4)

3. ADD a curious_corner query:
   - Query trending_topics where:
     extracted_at >= 7 days ago AND featured_in_newsletter = false
   - Order by novelty_score DESC
   - Limit to 8 items (Newsletter agent picks 2-3)

4. UPDATE the input_data structure sent to the newsletter agent task:
   {
     'edition_number': N,
     'section_a_opportunities': [...],     // was just 'opportunities'
     'section_b_emerging': [...],          // NEW
     'section_c_curious': [...],           // NEW
     'trending_tools': [...],             // existing
     'tool_warnings': [...],              // existing
     'clusters': [...],                    // existing
     'stats': {
       'posts_count': N,
       'problems_count': N,
       'tools_count': N,
       'new_opps_count': N,
       'emerging_signals_count': N,        // NEW
       'trending_topics_count': N          // NEW
     }
   }

5. ADD a post-publish function update_newsletter_appearances(newsletter_id) that:
   - Reads the published newsletter from Supabase
   - From data_snapshot, gets which opportunity IDs were featured
   - Updates each featured opportunity: newsletter_appearances += 1, last_featured_at = NOW()
   - If first_featured_at is null, set it to NOW()
   - Updates trending_topics that were used: featured_in_newsletter = true
   - Call this from publish_newsletter() after successful publish

6. Add 'update_newsletter_appearances' logic inside the existing publish_newsletter flow.
   After sending to Telegram and marking as published, call the update logic.

Don't delete any existing code — modify prepare_newsletter_data() and publish_newsletter().
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_newsletter
# Check Supabase agent_tasks: the write_newsletter task input_data should now have
# section_a_opportunities, section_b_emerging, section_c_curious
```

---

## Prompt 7: Content — Update Newsletter Agent Identity

```
Update the Newsletter agent's identity file to support the new 3-section newsletter format.

Reference: AGENTPULSE_PHASE3_WEEK1.md, Part 2E.

Edit data/openclaw/agents/newsletter/agent/IDENTITY.md:

KEEP everything that's already there about voice, style, and influences (Evans, Lenny, Newcomer, Thompson, Om Malik). KEEP all the writing constraints and rules.

REPLACE the "Structure" section with this new structure:

## Structure

Every edition follows this arc:

1. **Cold open** — One sentence that hooks. Not "This week in AI agents..."
   but "The agent economy just discovered it has a trust problem."

2. **The Big Story** — The most important signal this week. 2-3 paragraphs
   of analysis, not summary. What does this mean structurally? Pick from
   any section — established, emerging, or curious.

3. **Top Opportunities** (Section A)
   - Top 3-5 established opportunities
   - These have been validated by the Analyst with reasoning chains
   - For each: name, problem (one line), confidence, your one-line editorial take
   - If an opportunity appeared in a previous edition, note what's NEW: 
     "Previously featured — new signals this week include..."
   - If nothing has new signals, it's ok to have fewer than 5. Quality over repetition.
   - IMPORTANT: The data includes effective_score (staleness-adjusted) and 
     newsletter_appearances count. Prioritize by effective_score, not raw confidence.

4. **Emerging Signals** (Section B)
   - 2-4 early-stage signals that haven't been fully validated yet
   - These are LOW frequency but HIGH recency — new this week
   - Voice shift: speculative, forward-looking, invitational
   - "We're seeing early chatter about X. Only 3 mentions so far, but the
     signal phrases are specific: [actual quotes]. Worth watching."
   - Include the raw signal phrases from the data when possible
   - It's OK to be uncertain here. "Too early to call, but if this continues..."

5. **The Curious Corner** (Section C)
   - 2-3 interesting items that are NOT investment opportunities
   - Voice shift: lighter, more playful, genuinely curious
   - Debates: "Agents are arguing about whether memory persistence is ethical.
     The split is roughly 60/40, and both sides have interesting points..."
   - Surprising usage: "Someone built a poetry-writing agent that critics
     actually can't distinguish from human-written haiku..."
   - Cultural: "The agent economy has its first meme format, and it's about..."
   - NO business framing. No "this could be an opportunity." Just: "this is interesting."
   - This section should make someone smile or say "huh, I didn't know that."

6. **Tool Radar** — What's rising, falling, new. Keep the existing approach:
   narrative not list, connect the dots.

7. **Gato's Corner** — Same as before: Bitcoin-maximalist take. Gato can reference
   all sections including Curious Corner.

8. **By the Numbers** — Key stats. Add: emerging signals detected, curious topics trending.

Also ADD this instruction to the "Gato's Corner" section:
   Gato can riff on the Curious Corner items too — his take on agent debates
   or cultural moments adds personality. He doesn't have to stick to just
   opportunities.

Don't change anything about the voice influences, writing constraints, or output format rules. Only change the structure section and add the new section descriptions.
```

**After this:**
```bash
docker compose restart newsletter
# Generate a test newsletter to see the new format
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_newsletter
# Wait 60 seconds for newsletter agent to pick up and write
docker compose logs newsletter | tail -50
# Check Supabase: newsletters table should have a new draft with all 3 sections
```

---

## Prompt 8: Content — Wire Curious Corner Command to Gato

```
Add a /curious command to Gato so the operator can see trending topics on demand.

1. Add to the Processor's execute_task():
   'get_trending_topics':
   - Query trending_topics ordered by novelty_score DESC, limit from params (default 5)
   - Only get recent ones: extracted_at in last 14 days
   - Return the rows

2. Update data/openclaw/workspace/AGENTS.md — add:
   - /curious → write {"task":"get_trending_topics","params":{"limit":5}} to the queue. Display the trending topics with their titles, descriptions, and why_interesting. Format them in a fun, curious tone — these are NOT investment opportunities.

3. Update skills/agentpulse/SKILL.md — add to the commands table:
   | /curious | Show trending curious topics from the agent economy |

   Add a brief description: "The Curious Corner content comes from a separate extraction looking for debates, cultural moments, surprising usage, and meta-discussions — not business problems."

Don't modify any other files.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
docker compose restart gato
# Test on Telegram: /curious
```

---

## Post-Week 1 Verification

```bash
# 1. Security: confirm .gitignore is working
cd ~/bitcoin_bot
git status config/.env  # Should NOT appear
git status data/openclaw/agents/main/agent/auth-profiles.json  # Should NOT appear

# 2. Security: confirm RLS is active
# Try reading agent_tasks with the anon key (should fail/return empty)
curl "https://<your-supabase-url>/rest/v1/agent_tasks?select=*&limit=1" \
  -H "apikey: <your-anon-key>" \
  -H "Authorization: Bearer <your-anon-key>"
# Should return empty array []

# Try reading published newsletters with anon key (should work)
curl "https://<your-supabase-url>/rest/v1/newsletters?select=*&status=eq.published&limit=1" \
  -H "apikey: <your-anon-key>" \
  -H "Authorization: Bearer <your-anon-key>"
# Should return published newsletters (if any)

# 3. Security: confirm services still work with service key
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task status

# 4. Content: test trending topics extraction
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task extract_trending_topics
# Check: trending_topics table has rows

# 5. Content: test full newsletter with new sections
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_newsletter
# Wait 60 seconds
# Check: newsletters table — latest draft should have section_a, section_b, section_c data
# Check: the newsletter content should have "Emerging Signals" and "Curious Corner" sections

# 6. Telegram: test commands
# /newsletter — should show new format
# /curious — should show trending topics
# /scan — should still work
```

---

## Troubleshooting

**Services can't read Supabase after RLS:**
→ You need the service_role key, not the anon key. Check SUPABASE_SERVICE_KEY is in .env and passed through docker-compose.yml.

**Trending topics extraction returns 0:**
→ Posts may not have much "interesting" content. Try with larger hours_back. The prompt may also be too strict — check the raw posts for anything that qualifies.

**Newsletter still shows same opportunities:**
→ Check that newsletter_appearances is being incremented. Run: `SELECT title, newsletter_appearances, last_featured_at FROM opportunities ORDER BY confidence_score DESC LIMIT 10;` in Supabase.
→ The staleness penalty only works after the first newsletter publish cycle.

**Newsletter agent doesn't pick up new section data:**
→ Restart it: `docker compose restart newsletter`
→ Check that the input_data in agent_tasks has the new fields (section_a_opportunities, section_b_emerging, section_c_curious).

**Gato ignores /curious command:**
→ Restart Gato: `docker compose restart gato`
→ Check AGENTS.md has the /curious entry.
