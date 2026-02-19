# AgentPulse Phase 4: Review, Validation & Server Deployment

> **Upload `AGENTPULSE_PHASE4_CONTENT.md` as context.**
> **Run this as a single Cursor prompt after all 10 Phase 4 prompts are complete.**

---

## The Cursor Prompt

```
I've implemented all 10 Phase 4 prompts (source expansion + prediction tracking) across multiple parallel Cursor agents. Before pushing to git and deploying to the server, I need a thorough review of all changes to catch conflicts, missing pieces, and bugs.

Work through every section in order. Fix issues as you find them.

## SECTION 1: Merge Conflict Check

Multiple agents edited agentpulse_processor.py simultaneously. Check for:

1. Search for conflict markers:
   grep -n "<<<<<<\|======\|>>>>>>" docker/processor/agentpulse_processor.py
   If any found: resolve them manually, keeping both sides where appropriate.

2. Check for duplicate function definitions:
   grep -n "^def \|^class " docker/processor/agentpulse_processor.py | sort
   Every function name should appear exactly once. If a function is defined twice, merge them.

3. Check for duplicate imports:
   head -50 docker/processor/agentpulse_processor.py
   Remove any duplicate import lines.

4. Check the same for other files that may have had parallel edits:
   grep -n "<<<<<<\|======\|>>>>>>" docker/analyst/analyst_poller.py
   grep -n "<<<<<<\|======\|>>>>>>" docker/newsletter/newsletter_poller.py
   grep -n "<<<<<<\|======\|>>>>>>" skills/agentpulse/SKILL.md
   grep -n "<<<<<<\|======\|>>>>>>" docker/docker-compose.yml

## SECTION 2: Function Existence Check

Verify every function added in Phase 4 actually exists in the codebase.

   python3 -c "
   import ast, sys

   with open('docker/processor/agentpulse_processor.py', 'r') as f:
       tree = ast.parse(f.read())

   functions = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
   classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

   required_functions = [
       # Phase 4 additions
       'scrape_hackernews',
       'scrape_github',
       'extract_problems_multisource',
       'extract_tools_multisource',
       'extract_trending_topics_multisource',
       'create_predictions_from_newsletter',
       'gather_prediction_signals',
       'evaluate_prediction',
       'track_predictions',
       # Should still exist from earlier phases
       'scrape_moltbook',
       'extract_problems',
       'extract_tool_mentions',
       'extract_trending_topics',
       'cluster_problems',
       'generate_opportunities',
       'prepare_analysis_package',
       'prepare_newsletter_data',
       'publish_newsletter',
       'get_latest_newsletter',
       'detect_anomalies',
       'proactive_scan',
       'create_negotiation',
       'respond_to_negotiation',
       'execute_task',
       'setup_scheduler',
   ]

   print('=== Functions found ===')
   for fn in sorted(functions):
       print(f'  {fn}')

   print(f'\nTotal functions: {len(functions)}')
   print(f'\n=== Missing required functions ===')
   missing = [f for f in required_functions if f not in functions]
   if missing:
       for f in missing:
           print(f'  MISSING: {f}')
   else:
       print('  None — all required functions present')

   print(f'\n=== Classes ===')
   for c in classes:
       print(f'  {c}')
   assert 'AgentBudget' in classes, 'MISSING: AgentBudget class'
   print('\nAll classes OK')
   "

If any functions are missing, they weren't added by the parallel agents. Add them now based on the AGENTPULSE_PHASE4_CONTENT.md architecture doc.

## SECTION 3: execute_task() Routing Check

Verify all task types are registered in execute_task().

   grep -n "task_type ==" docker/processor/agentpulse_processor.py | sort

   Required Phase 4 task types (check each appears):
   - scrape_hackernews
   - scrape_github
   - extract_problems_multisource
   - extract_tools_multisource
   - extract_trending_topics_multisource
   - create_predictions
   - track_predictions
   - get_predictions
   - get_source_status
   - create_manual_prediction

   Also verify these pre-existing task types still exist:
   - run_pipeline
   - scrape
   - analyze / extract_problems
   - extract_tool_mentions
   - extract_trending_topics
   - cluster_problems
   - prepare_analysis
   - prepare_newsletter
   - publish_newsletter
   - get_latest_newsletter
   - get_budget_status
   - targeted_scrape
   - proactive_scan
   - send_alert
   - create_negotiation
   - respond_to_negotiation
   - get_active_negotiations
   - get_recent_alerts

   If any task type is missing from execute_task(), add the elif branch.

## SECTION 4: Argparse Choices Check

Verify all task types are available as CLI arguments.

   grep -A 200 "argparse\|add_argument.*--task\|choices=" docker/processor/agentpulse_processor.py | grep -o "'[a-z_]*'" | sort -u

   All task types from Section 3 should appear in the argparse choices list.
   If any are missing, add them to the choices list.

## SECTION 5: run_pipeline Flow Check

Verify the run_pipeline task includes the new sources.

   grep -A 50 "'run_pipeline'" docker/processor/agentpulse_processor.py

   The flow should be:
   1. scrape_moltbook()
   2. scrape_hackernews()           ← NEW
   3. scrape_github()               ← NEW
   4. extract_problems_multisource() ← UPDATED (was extract_problems)
   5. extract_tools_multisource()    ← UPDATED (was extract_tool_mentions)
   6. extract_trending_topics_multisource() ← UPDATED
   7. cluster_problems()
   8. prepare_analysis_package()

   Each step should be wrapped in try/except so one failure doesn't stop the pipeline.
   All results should be collected and returned.

   If run_pipeline still uses the old single-source functions, update it.

## SECTION 6: Scheduler Check

Verify all scheduled jobs are registered.

   grep -n "schedule\." docker/processor/agentpulse_processor.py

   Required scheduled jobs:
   - Moltbook scrape (every 6h) — existing
   - HN scrape (every 6h) — NEW
   - GitHub scrape (every 12h) — NEW
   - Analysis/extraction (every 12h) — should now use multisource functions
   - Tool stats update (daily) — existing
   - Opportunity digest (daily 9am) — existing
   - Prediction tracking (Monday 6:30am) — NEW
   - Newsletter data prep (Monday 7am) — existing
   - Newsletter notification (Monday 8am) — existing
   - Proactive scan (every 60 min) — existing
   - Negotiation timeout check (every 10 min) — existing

   If any scheduled job is missing, add it in setup_scheduler().

## SECTION 7: publish_newsletter Integration Check

Verify that publishing a newsletter now creates predictions.

   grep -A 30 "def publish_newsletter" docker/processor/agentpulse_processor.py

   After the existing publish logic (Telegram send, status update, appearance tracking),
   there should be:
   try:
       pred_result = create_predictions_from_newsletter(newsletter_id)
       logger.info(f"Predictions created: {pred_result}")
   except Exception as e:
       logger.error(f"Prediction creation failed: {e}")

   If missing, add it.

## SECTION 8: prepare_newsletter_data Check

Verify newsletter data package includes predictions and source stats.

   grep -A 80 "def prepare_newsletter_data" docker/processor/agentpulse_processor.py

   The input_data sent to the newsletter agent should include:
   - 'predictions': prediction data (active, confirmed, faded)
   - stats should include: hackernews_posts, github_repos, moltbook_posts counts

   If predictions aren't being gathered, add the query:
   predictions = supabase.table('predictions')\
       .select('*')\
       .in_('status', ['active', 'confirmed', 'faded'])\
       .order('current_score', desc=True)\
       .limit(10)\
       .execute()

## SECTION 9: Docker Compose Check

Verify docker-compose.yml has the GITHUB_TOKEN env var.

   grep "GITHUB_TOKEN" docker/docker-compose.yml

   Should appear in the common env anchor:
   GITHUB_TOKEN: ${GITHUB_TOKEN:-}

   If missing, add it.

## SECTION 10: Identity Templates Check

Verify the identity template files exist and have the new sections.

   # Newsletter identity should mention Prediction Tracker
   grep -i "prediction" templates/newsletter/IDENTITY.md
   # Should find references to Prediction Tracker section

   # Analyst identity should mention cross-source
   grep -i "cross-source\|cross.source\|multiple sources" templates/analyst/IDENTITY.md
   # Should find cross-source validation section

   # If either is missing, the identity update prompts (7, 8) didn't run.
   # Add the sections from AGENTPULSE_PHASE4_CONTENT.md.

## SECTION 11: SKILL.md Check

Verify skill files have new commands.

   grep -i "predictions\|sources\|predict " skills/agentpulse/SKILL.md
   # Should find /predictions, /sources, /predict commands

   If missing, add to the commands table in SKILL.md.

## SECTION 12: AGENTS.md Check

Verify AGENTS.md has the new Telegram commands.

   Check data/openclaw/workspace/AGENTS.md for:
   - /predictions command definition
   - /sources command definition
   - /predict command definition

   If missing, add them.

## SECTION 13: HN Keywords and GitHub Queries Sanity Check

Review the scraper configurations for obvious issues.

   # Check HN keywords exist
   grep -A 20 "HN_KEYWORDS" docker/processor/agentpulse_processor.py
   # Should be a list of strings, at least 10 keywords

   # Check GitHub queries exist
   grep -A 10 "GITHUB_QUERIES\|queries.*=.*\[" docker/processor/agentpulse_processor.py | grep -i "agent\|llm\|agentic"
   # Should find search query strings

   # Check GITHUB_TOKEN is read
   grep "GITHUB_TOKEN" docker/processor/agentpulse_processor.py
   # Should find: GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

## SECTION 14: Prediction Evaluation Logic Check

Review the evaluate_prediction function for correctness.

   grep -A 40 "def evaluate_prediction" docker/processor/agentpulse_processor.py

   Check:
   - Score is clamped between 0 and 1 (min/max calls)
   - Score is rounded to 2 decimals
   - Status transitions make sense: active → confirmed (score >= 0.8), active → faded (score < 0.2 after 3+ weeks)
   - Weeks_active calculation handles timezone-aware datetimes (Supabase returns Z suffixed timestamps)
   - Function returns a tuple: (status, score, notes)

   Common bugs:
   - datetime.fromisoformat() can't parse Z suffix — need .replace('Z', '+00:00') or use dateutil
   - Division by zero if no tool mentions (avg_sentiment calculation)
   - Missing try/except around individual prediction tracking

## SECTION 15: Syntax and Import Verification

Final check — does the processor actually parse and run?

   cd docker
   docker compose exec processor python3 -c "
   import sys
   sys.path.insert(0, '/home/openclaw')
   import agentpulse_processor
   print('Module loaded successfully')
   print(f'Functions: {len([x for x in dir(agentpulse_processor) if not x.startswith(\"_\")])}')
   "

   If this fails with a SyntaxError or ImportError, the error message will tell you exactly
   what line has the issue. Fix it.

   If the processor isn't built yet (running locally), use:
   python3 -c "
   import ast
   with open('docker/processor/agentpulse_processor.py', 'r') as f:
       source = f.read()
   try:
       ast.parse(source)
       print('Syntax OK')
   except SyntaxError as e:
       print(f'Syntax error at line {e.lineno}: {e.msg}')
   "

## SECTION 16: Fix Summary

Compile a summary of:
1. Everything that PASSED
2. Everything that was FIXED (what was wrong and what you changed)
3. Any remaining issues that need manual attention

Then confirm the codebase is ready for:
   git add -A
   git commit -m "Phase 4: source expansion (HN + GitHub) + prediction tracking"
   git push
```

---

## Server Deployment Instructions

After the review passes and code is pushed to git, run these on your server:

```bash
ssh root@46.224.50.251
cd ~/bitcoin_bot

# ============================================
# STEP 1: Pull latest code
# ============================================
git pull

# ============================================
# STEP 2: Deploy identity files from templates
# ============================================
bash scripts/deploy-identities.sh
# Should show:
#   Analyst identity deployed
#   Newsletter identity deployed

# ============================================
# STEP 3: Update .env with new vars
# ============================================
# Add GitHub token if not already there
grep -q "GITHUB_TOKEN" config/.env || echo "GITHUB_TOKEN=ghp_your_token_here" >> config/.env

# Verify all required env vars exist
echo "Checking .env..."
for var in SUPABASE_URL SUPABASE_KEY SUPABASE_SERVICE_KEY OPENAI_API_KEY ANTHROPIC_API_KEY TELEGRAM_BOT_TOKEN GITHUB_TOKEN AGENTPULSE_DOMAIN; do
    if grep -q "$var" config/.env; then
        echo "  $var: OK"
    else
        echo "  $var: MISSING — add it to config/.env"
    fi
done

# ============================================
# STEP 4: Run SQL migrations
# ============================================
# Open Supabase SQL Editor and run the Phase 4 schema from Prompt 1.
# Check if tables already exist first:
# SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;
# If source_posts and predictions don't exist, run the SQL.

# ============================================
# STEP 5: Rebuild and restart all services
# ============================================
cd docker
docker compose down
docker compose build --no-cache
docker compose up -d

# Wait for all services to stabilize
sleep 15
docker compose ps
# All services should show "Up" — gato, analyst, processor, newsletter, web

# ============================================
# STEP 6: Verify services started cleanly
# ============================================
echo "=== Processor ==="
docker compose logs processor | tail -10

echo "=== Analyst ==="
docker compose logs analyst | tail -10
docker compose logs analyst | grep "Identity loaded"

echo "=== Newsletter ==="
docker compose logs newsletter | tail -10
docker compose logs newsletter | grep "Identity loaded"

echo "=== Gato ==="
docker compose logs gato | tail -10

echo "=== Web ==="
docker compose logs web | tail -5

# ============================================
# STEP 7: Verify config is accessible
# ============================================
docker compose exec processor python3 -c "
import json
config = json.load(open('/home/openclaw/.openclaw/config/agentpulse-config.json'))
print(f'Models: {list(config.get(\"models\", {}).keys())}')
print(f'Budgets: {list(config.get(\"budgets\", {}).keys())}')
print(f'Negotiation: {\"allowed_pairs\" in config.get(\"negotiation\", {})}')
"

# ============================================
# STEP 8: Verify database tables
# ============================================
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))

for table in ['source_posts', 'predictions', 'moltbook_posts', 'problems', 'problem_clusters', 'opportunities', 'tool_mentions', 'tool_stats', 'agent_tasks', 'analysis_runs', 'cross_signals', 'newsletters', 'trending_topics', 'agent_daily_usage', 'agent_negotiations']:
    try:
        r = c.table(table).select('id', count='exact').limit(0).execute()
        print(f'{table}: OK ({r.count} rows)')
    except Exception as e:
        print(f'{table}: FAILED - {e}')
"

# ============================================
# STEP 9: Test scrapers
# ============================================
echo "Testing HN scraper..."
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task scrape_hackernews
# Should take 1-3 minutes

echo "Testing GitHub scraper..."
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task scrape_github
# Should take 30-60 seconds

# Verify data landed
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))
for source in ['moltbook', 'hackernews', 'github']:
    count = c.table('source_posts').select('id', count='exact').eq('source', source).execute()
    print(f'{source}: {count.count} posts')
"

# ============================================
# STEP 10: Test multi-source extraction
# ============================================
echo "Testing multi-source problem extraction..."
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task extract_problems_multisource

echo "Testing multi-source tool extraction..."
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task extract_tools_multisource

# ============================================
# STEP 11: Test prediction tracking
# ============================================
# Create a test prediction if none exist
docker compose exec processor python3 -c "
from supabase import create_client
import os, json
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))
existing = c.table('predictions').select('id', count='exact').execute()
if existing.count == 0:
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
else:
    print(f'{existing.count} predictions already exist')
"

echo "Testing prediction tracking..."
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task track_predictions

# ============================================
# STEP 12: Test full pipeline
# ============================================
echo "Running full pipeline (this takes a few minutes)..."
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task run_pipeline

# Check analyst picked up the analysis task
sleep 30
docker compose logs analyst | tail -20

# ============================================
# STEP 13: Test Telegram commands
# ============================================
echo "Test these commands on Telegram:"
echo "  /sources       — should show per-source scraping stats"
echo "  /predictions   — should show tracked predictions"
echo "  /budget        — should show daily LLM usage"
echo "  /scan          — full pipeline with all sources"
echo ""
echo "If commands don't work, restart gato:"
echo "  docker compose restart gato"

# ============================================
# STEP 14: Test newsletter generation
# ============================================
echo "Testing newsletter generation..."
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_newsletter
echo "Waiting 90 seconds for newsletter agent..."
sleep 90
docker compose logs newsletter | tail -30

# Check the draft
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))
nl = c.table('newsletters').select('edition_number, title, status, created_at').order('created_at', desc=True).limit(1).execute()
if nl.data:
    n = nl.data[0]
    print(f'Latest newsletter: Edition #{n[\"edition_number\"]} | {n[\"title\"]} | {n[\"status\"]}')
else:
    print('No newsletters found')
"

# ============================================
# STEP 15: Verify web archive
# ============================================
echo "Testing web archive..."
curl -sk https://localhost | head -5
# Or if you have a domain:
# curl -s https://yourdomain.com | head -5

# ============================================
# STEP 16: Final health check
# ============================================
echo ""
echo "========================================="
echo "  FINAL HEALTH CHECK"
echo "========================================="
echo ""

docker compose ps --format "table {{.Name}}\t{{.Status}}"

docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))

print('=== Data Coverage ===')
for source in ['moltbook', 'hackernews', 'github']:
    count = c.table('source_posts').select('id', count='exact').eq('source', source).execute()
    print(f'  {source}: {count.count} posts')

problems = c.table('problems').select('id', count='exact').execute()
print(f'  Problems extracted: {problems.count}')

tools = c.table('tool_stats').select('id', count='exact').execute()
print(f'  Tools tracked: {tools.count}')

preds = c.table('predictions').select('id', count='exact').execute()
print(f'  Predictions: {preds.count}')

newsletters = c.table('newsletters').select('id', count='exact').execute()
print(f'  Newsletters: {newsletters.count}')

print('\n=== Agent Tasks (last 24h) ===')
from datetime import datetime, timedelta
day_ago = (datetime.utcnow() - timedelta(hours=24)).isoformat()
tasks = c.table('agent_tasks').select('assigned_to, status').gte('created_at', day_ago).execute()
from collections import Counter
by_agent = Counter()
by_status = Counter()
for t in (tasks.data or []):
    by_agent[t['assigned_to']] += 1
    by_status[t['status']] += 1
for agent, count in by_agent.most_common():
    print(f'  {agent}: {count} tasks')
for status, count in by_status.most_common():
    print(f'  {status}: {count}')

print('\n=== Budget Usage Today ===')
usage = c.table('agent_daily_usage').select('*').execute()
for u in (usage.data or []):
    print(f'  {u[\"agent_name\"]}: {u[\"llm_calls_used\"]} LLM calls')

print('\nDone.')
"

echo ""
echo "========================================="
echo "  DEPLOYMENT COMPLETE"
echo "========================================="
echo ""
echo "Next: test /scan and /predictions on Telegram"
echo "Then: publish a newsletter to test prediction creation"
```

---

## Troubleshooting Quick Reference

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Service keeps restarting | Python syntax error | `docker compose logs <service> \| head -30` |
| Processor won't start | Missing import or function | Check Section 15 of review prompt |
| HN scraper returns 0 | Network blocked or keywords too narrow | Test: `docker compose exec processor python3 -c "import httpx; print(httpx.get('https://hacker-news.firebaseio.com/v0/topstories.json').status_code)"` |
| GitHub scraper hits 403 | Missing or invalid token | Check: `docker compose exec processor env \| grep GITHUB` |
| source_posts table missing | SQL not run | Run Prompt 1 SQL in Supabase |
| predictions table missing | SQL not run | Run Prompt 1 SQL in Supabase |
| Task type not found | Missing elif in execute_task | Check Section 3 of review prompt |
| Telegram command ignored | AGENTS.md not updated or gato not restarted | `docker compose restart gato` |
| Newsletter missing predictions | prepare_newsletter_data doesn't query predictions | Check Section 8 of review prompt |
| Identity not loaded | Templates not deployed | `bash scripts/deploy-identities.sh && docker compose restart analyst newsletter` |
| Web archive blank | Supabase URL not injected | `docker compose exec web cat /srv/app.js \| head -3` |
