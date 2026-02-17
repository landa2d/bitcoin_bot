# AgentPulse Agency Upgrade: Full Testing & Debugging Prompt

> **Use this as a single Cursor prompt after pushing to git and deploying on the server.**
> **Upload `AGENTPULSE_AGENCY_UPGRADE.md` as context.**

---

## Pre-Test: Server Deployment

Run these on your server before starting the Cursor testing prompt:

```bash
ssh root@46.224.50.251
cd ~/bitcoin_bot

# Pull latest code
git pull

# Rebuild ALL services (agency changes touch everything)
cd docker
docker compose down
docker compose build --no-cache
docker compose up -d

# Confirm all services are up
docker compose ps
# Expected: gato, analyst, processor, newsletter — all "Up"
# (web too if you've deployed it)

# Quick health check
docker compose logs processor | tail -10
docker compose logs analyst | tail -10
docker compose logs newsletter | tail -10
docker compose logs gato | tail -10
```

If any service is crashing or restarting, fix that first before running the Cursor prompt.

---

## The Cursor Prompt

```
I've just deployed the Agency Upgrade for AgentPulse. This includes: budget system, self-correcting analyst loops, autonomous data requests, proactive monitoring, and agent-to-agent negotiation. Nothing has been tested yet.

I need you to systematically test every new component, identify failures, fix them, and verify the fixes. Work through each section in order. If something fails, debug and fix it before moving to the next section.

Reference: AGENTPULSE_AGENCY_UPGRADE.md for the full architecture.

The system runs on a remote server. The code is in ~/bitcoin_bot/. Docker services are in ~/bitcoin_bot/docker/. All services should already be running (docker compose up -d was run).

## SECTION 1: Config Validation

Test that the config file is properly structured and readable by all services.

1. Check agentpulse-config.json exists and is valid JSON:
   docker compose exec processor cat /home/openclaw/.openclaw/config/agentpulse-config.json | python3 -m json.tool

2. Verify it has all required sections:
   docker compose exec processor python3 -c "
   import json
   config = json.load(open('/home/openclaw/.openclaw/config/agentpulse-config.json'))
   
   # Check models
   models = config.get('models', {})
   assert 'extraction' in models, 'Missing models.extraction'
   assert 'default' in models, 'Missing models.default'
   print(f'Models OK: {list(models.keys())}')
   
   # Check budgets
   budgets = config.get('budgets', {})
   assert 'analyst' in budgets, 'Missing budgets.analyst'
   assert 'newsletter' in budgets, 'Missing budgets.newsletter'
   assert 'global' in budgets, 'Missing budgets.global'
   print(f'Budgets OK: analyst tasks={list(budgets[\"analyst\"].keys())}, newsletter tasks={list(budgets[\"newsletter\"].keys())}')
   print(f'Global limits: {budgets[\"global\"]}')
   
   # Check negotiation
   negotiation = config.get('negotiation', {})
   assert 'allowed_pairs' in negotiation, 'Missing negotiation.allowed_pairs'
   print(f'Negotiation OK: {negotiation}')
   
   print('\nConfig validation PASSED')
   "

If any assertion fails, fix agentpulse-config.json. The complete schema is in AGENTPULSE_AGENCY_UPGRADE.md under "Budget Config Location".

## SECTION 2: Database Tables

Verify all new tables exist and have the correct columns.

   docker compose exec processor python3 -c "
   from supabase import create_client
   import os
   c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))
   
   # Test agent_daily_usage
   try:
       r = c.table('agent_daily_usage').select('*').limit(0).execute()
       print('agent_daily_usage: OK')
   except Exception as e:
       print(f'agent_daily_usage: FAILED - {e}')
   
   # Test agent_negotiations
   try:
       r = c.table('agent_negotiations').select('*').limit(0).execute()
       print('agent_negotiations: OK')
   except Exception as e:
       print(f'agent_negotiations: FAILED - {e}')
   
   # Test that opportunities has new columns
   try:
       r = c.table('opportunities').select('analyst_reasoning, signal_sources, last_reviewed_at, review_count, newsletter_appearances, last_featured_at').limit(1).execute()
       print('opportunities columns: OK')
   except Exception as e:
       print(f'opportunities columns: FAILED - {e}')
   
   # Test existing tables still work
   for table in ['moltbook_posts', 'problems', 'problem_clusters', 'opportunities', 'tool_mentions', 'tool_stats', 'agent_tasks', 'analysis_runs', 'cross_signals', 'newsletters', 'trending_topics']:
       try:
           r = c.table(table).select('id', count='exact').limit(0).execute()
           print(f'{table}: OK ({r.count} rows)')
       except Exception as e:
           print(f'{table}: FAILED - {e}')
   "

If any table is missing, run the corresponding CREATE TABLE SQL from AGENTPULSE_AGENCY_UPGRADE.md Prompt 1 in the Supabase SQL Editor.

## SECTION 3: Budget System

Test the AgentBudget class and daily tracking.

   docker compose exec processor python3 -c "
   import sys
   sys.path.insert(0, '/home/openclaw')
   
   # Test 1: Can we import and create a budget?
   try:
       from agentpulse_processor import AgentBudget, get_budget_config, check_daily_budget, increment_daily_usage, get_daily_usage
       print('Budget imports: OK')
   except ImportError as e:
       print(f'Budget imports: FAILED - {e}')
       print('The AgentBudget class or helper functions are missing from agentpulse_processor.py')
       sys.exit(1)
   
   # Test 2: Create a budget object
   try:
       budget = AgentBudget('full_analysis', 'analyst', get_budget_config('analyst', 'full_analysis'))
       print(f'Budget created: max_llm={budget.max_llm_calls}, max_seconds={budget.max_seconds}, max_subtasks={budget.max_subtasks}')
       assert budget.can_call_llm(), 'Fresh budget should allow LLM calls'
       assert budget.can_create_subtask(), 'Fresh budget should allow subtasks'
       assert budget.can_retry(), 'Fresh budget should allow retries'
       print('Budget methods: OK')
   except Exception as e:
       print(f'Budget creation: FAILED - {e}')
       sys.exit(1)
   
   # Test 3: Budget enforcement
   try:
       budget.use_llm_call()
       budget.use_llm_call()
       print(f'After 2 LLM calls: remaining={budget.remaining()}')
       assert budget.llm_calls_used == 2, f'Expected 2 calls used, got {budget.llm_calls_used}'
       print('Budget tracking: OK')
   except Exception as e:
       print(f'Budget tracking: FAILED - {e}')
   
   # Test 4: Daily budget check
   try:
       result = check_daily_budget('analyst')
       print(f'Daily budget check: {result} (should be True initially)')
   except Exception as e:
       print(f'Daily budget check: FAILED - {e}')
   
   # Test 5: Increment daily usage
   try:
       increment_daily_usage('test_agent', llm_calls=5, subtasks=1)
       usage = get_daily_usage('test_agent')
       print(f'Daily usage after increment: {usage}')
   except Exception as e:
       print(f'Daily usage increment: FAILED - {e}')
       print('This might be an upsert issue with agent_daily_usage table')
   
   print('\nBudget system tests complete')
   "

Common issues:
- If AgentBudget class doesn't exist: it wasn't added to agentpulse_processor.py. Check Prompt 2 from the agency prompts.
- If get_budget_config fails: the config file path might be wrong. Check that /home/openclaw/.openclaw/config/agentpulse-config.json exists inside the container.
- If increment_daily_usage fails: likely the UNIQUE constraint on (agent_name, date) isn't set up properly, or the upsert logic is wrong. Fix the function to handle insert-or-update properly.

## SECTION 4: Model Routing

Test that different tasks use different models.

   docker compose exec processor python3 -c "
   import sys
   sys.path.insert(0, '/home/openclaw')
   
   try:
       from agentpulse_processor import get_model
       
       extraction_model = get_model('extraction')
       clustering_model = get_model('clustering')
       opp_model = get_model('opportunity_generation')
       default_model = get_model('nonexistent_task')
       
       print(f'extraction: {extraction_model}')
       print(f'clustering: {clustering_model}')
       print(f'opportunity_generation: {opp_model}')
       print(f'default (fallback): {default_model}')
       
       assert 'mini' in extraction_model, f'extraction should use mini, got {extraction_model}'
       assert 'mini' in clustering_model, f'clustering should use mini, got {clustering_model}'
       assert 'mini' not in opp_model, f'opportunity_generation should NOT use mini, got {opp_model}'
       
       print('\nModel routing: PASSED')
   except ImportError:
       print('get_model function not found in agentpulse_processor.py')
   except Exception as e:
       print(f'Model routing: FAILED - {e}')
   "

## SECTION 5: Processor Task Routing

Test that all new task types are registered in execute_task().

   docker compose exec processor python3 -c "
   import sys
   sys.path.insert(0, '/home/openclaw')
   
   new_tasks = [
       'get_budget_status',
       'targeted_scrape',
       'can_create_subtask',
       'proactive_scan',
       'send_alert',
       'create_negotiation',
       'respond_to_negotiation',
       'get_active_negotiations',
       'prepare_analysis',
   ]
   
   from agentpulse_processor import execute_task
   import inspect
   source = inspect.getsource(execute_task)
   
   for task in new_tasks:
       if task in source:
           print(f'{task}: registered in execute_task ✓')
       else:
           print(f'{task}: NOT FOUND in execute_task ✗')
   "

If any task is missing, add the corresponding elif branch to execute_task() in agentpulse_processor.py.

## SECTION 6: Proactive Monitoring

Test anomaly detection (no LLM calls — pure Python).

   docker compose exec processor python3 -c "
   import sys
   sys.path.insert(0, '/home/openclaw')
   
   # Test detect_anomalies
   try:
       from agentpulse_processor import detect_anomalies
       anomalies = detect_anomalies()
       print(f'Anomalies detected: {len(anomalies)}')
       for a in anomalies:
           print(f'  {a[\"type\"]}: {a[\"description\"]}')
       print('detect_anomalies: OK')
   except ImportError:
       print('detect_anomalies function not found')
   except Exception as e:
       print(f'detect_anomalies: FAILED - {e}')
   
   # Test proactive budget check
   try:
       from agentpulse_processor import check_proactive_budget
       result = check_proactive_budget()
       print(f'Proactive budget available: {result}')
   except ImportError:
       print('check_proactive_budget function not found')
   except Exception as e:
       print(f'check_proactive_budget: FAILED - {e}')
   
   # Test proactive cooldown
   try:
       from agentpulse_processor import check_proactive_cooldown
       result = check_proactive_cooldown()
       print(f'Proactive cooldown clear: {result}')
   except ImportError:
       print('check_proactive_cooldown function not found')
   except Exception as e:
       print(f'check_proactive_cooldown: FAILED - {e}')
   
   # Test full proactive scan
   try:
       from agentpulse_processor import proactive_scan
       result = proactive_scan()
       print(f'Proactive scan result: {result}')
   except Exception as e:
       print(f'proactive_scan: FAILED - {e}')
   "

## SECTION 7: Analyst Poller

Test that the analyst poller is running, includes budget in tasks, and handles responses.

   # Is the poller running?
   docker compose exec analyst ps aux | grep poller
   
   # Check poller logs
   docker compose exec analyst cat /home/openclaw/.openclaw/logs/analyst-poller.log | tail -30
   
   # Test: create a task and verify the poller picks it up with budget
   docker compose exec processor python3 -c "
   from supabase import create_client
   import os, json, time
   c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))
   
   # Create a test analysis task
   result = c.table('agent_tasks').insert({
       'task_type': 'full_analysis',
       'assigned_to': 'analyst',
       'created_by': 'test',
       'priority': 3,
       'input_data': {'test': True, 'note': 'agency_test_run'}
   }).execute()
   task_id = result.data[0]['id']
   print(f'Created test task: {task_id}')
   
   # Wait for poller to pick it up
   print('Waiting 20 seconds for poller...')
   time.sleep(20)
   
   # Check if it was picked up
   task = c.table('agent_tasks').select('*').eq('id', task_id).execute()
   status = task.data[0]['status'] if task.data else 'NOT FOUND'
   print(f'Task status: {status}')
   
   if status == 'pending':
       print('PROBLEM: Poller did not pick up the task')
       print('Check: docker compose exec analyst cat /home/openclaw/.openclaw/logs/analyst-poller.log')
   elif status == 'in_progress':
       print('OK: Poller picked up the task, analyst is working on it')
   elif status == 'completed':
       print('OK: Task already completed')
       output = task.data[0].get('output_data', {})
       print(f'Output preview: {json.dumps(output, default=str)[:300]}')
   elif status == 'failed':
       print(f'FAILED: {task.data[0].get(\"error_message\", \"unknown\")}')
   "

   # Check if the task file includes budget
   docker compose exec analyst ls /home/openclaw/.openclaw/workspace/agentpulse/queue/
   # If there's an analyst_*.json file, check its contents:
   docker compose exec analyst cat /home/openclaw/.openclaw/workspace/agentpulse/queue/analyst_*.json 2>/dev/null || echo "No pending task files (task may have been processed already)"

Common issues:
- Poller not running: check entrypoint.sh starts it. Check `docker compose logs analyst | head -20` for startup errors.
- Poller can't connect to Supabase: check SUPABASE_SERVICE_KEY is passed to the analyst service in docker-compose.yml.
- Task files don't include budget: the poller's poll() function needs to read the budget config and include it.

## SECTION 8: Newsletter Poller

Same checks for the newsletter poller.

   docker compose exec newsletter ps aux | grep poller
   docker compose exec newsletter cat /home/openclaw/.openclaw/logs/newsletter-poller.log | tail -30

## SECTION 9: Negotiation System

Test negotiation creation and timeout.

   docker compose exec processor python3 -c "
   import sys
   sys.path.insert(0, '/home/openclaw')
   
   # Test negotiation creation
   try:
       from agentpulse_processor import execute_task
       
       result = execute_task('create_negotiation', {
           'requesting_agent': 'newsletter',
           'responding_agent': 'analyst',
           'request_summary': 'Test negotiation: need stronger opportunities',
           'quality_criteria': 'At least 3 opportunities above 0.6'
       })
       print(f'Create negotiation: {result}')
   except Exception as e:
       print(f'Create negotiation: FAILED - {e}')
   
   # Test getting active negotiations
   try:
       result = execute_task('get_active_negotiations', {})
       print(f'Active negotiations: {result}')
   except Exception as e:
       print(f'Get negotiations: FAILED - {e}')
   
   # Test negotiation pair validation (processor shouldn't be able to ask anyone)
   try:
       result = execute_task('create_negotiation', {
           'requesting_agent': 'processor',
           'responding_agent': 'analyst',
           'request_summary': 'This should fail',
           'quality_criteria': 'N/A'
       })
       if 'error' in str(result).lower():
           print(f'Pair validation works: processor correctly blocked')
       else:
           print(f'Pair validation FAILED: processor was allowed to negotiate (should be blocked)')
   except Exception as e:
       print(f'Pair validation: {e}')
   "

## SECTION 10: End-to-End Pipeline Test

The big test. Run a full pipeline and verify all agency features activate.

   # 1. Run full pipeline (scrape → extract → cluster → delegate to analyst)
   docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task run_pipeline
   
   # 2. Wait for analyst to process
   echo "Waiting 60 seconds for analyst..."
   sleep 60
   
   # 3. Check results
   docker compose exec processor python3 -c "
   from supabase import create_client
   import os, json
   c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))
   
   # Check analysis runs (self-correcting loops)
   runs = c.table('analysis_runs').select('*').order('started_at', desc=True).limit(1).execute()
   if runs.data:
       r = runs.data[0]
       print(f'Latest analysis run:')
       print(f'  Type: {r[\"run_type\"]}')
       print(f'  Status: {r[\"status\"]}')
       print(f'  Confidence: {r.get(\"confidence_level\", \"N/A\")}')
       print(f'  Caveats: {r.get(\"caveats\", [])}')
       if r.get('analyst_notes'):
           print(f'  Notes: {r[\"analyst_notes\"][:200]}...')
   else:
       print('NO analysis runs found — analyst may not have completed')
   
   # Check cross signals
   signals = c.table('cross_signals').select('*').order('first_detected', desc=True).limit(3).execute()
   print(f'\nCross-signals: {len(signals.data or [])}')
   for s in (signals.data or []):
       print(f'  {s[\"signal_type\"]}: {s[\"description\"][:80]}')
   
   # Check budget usage
   usage = c.table('agent_daily_usage').select('*').execute()
   print(f'\nDaily budget usage:')
   for u in (usage.data or []):
       print(f'  {u[\"agent_name\"]}: {u[\"llm_calls_used\"]} LLM calls, {u[\"subtasks_created\"]} subtasks, {u[\"proactive_alerts_sent\"]} alerts')
   
   # Check if any data requests were made
   data_requests = c.table('agent_tasks').select('*').eq('task_type', 'targeted_scrape').order('created_at', desc=True).limit(3).execute()
   print(f'\nData requests (targeted scrapes): {len(data_requests.data or [])}')
   for d in (data_requests.data or []):
       print(f'  {d[\"status\"]} | created by: {d[\"created_by\"]} | {d.get(\"input_data\", {}).get(\"reason\", \"N/A\")[:60]}')
   
   # Check opportunities have reasoning
   opps = c.table('opportunities').select('title, confidence_score, analyst_reasoning, review_count').order('confidence_score', desc=True).limit(3).execute()
   print(f'\nTop opportunities:')
   for o in (opps.data or []):
       has_reasoning = 'YES' if o.get('analyst_reasoning') else 'no'
       print(f'  {o[\"title\"]}: {o[\"confidence_score\"]} | reasoning: {has_reasoning} | reviews: {o.get(\"review_count\", 0)}')
   "

## SECTION 11: Telegram Commands

Test all new commands work. Run these one at a time on Telegram and verify responses:

   /budget       — Should show per-agent usage for today
   /alerts       — Should show recent proactive alerts (may be empty if no anomalies)
   /negotiations — Should show active negotiations (may be empty)
   /scan         — Should trigger full pipeline with agency features
   /analysis     — Should show latest analyst reasoning
   /signals      — Should show cross-pipeline signals

If any command doesn't work:
- Restart gato: docker compose restart gato
- Check AGENTS.md has the command: docker compose exec gato grep "budget\|alerts\|negotiations" /home/openclaw/.openclaw/workspace/AGENTS.md

## SECTION 12: Fix Summary

After running all sections, compile a summary:

1. List everything that PASSED
2. List everything that FAILED with the error
3. For each failure, apply the fix
4. Re-test the fixed components
5. Report final status

If you encounter errors that require code changes, make the change, rebuild the affected service (docker compose build <service> --no-cache && docker compose up <service> -d), and re-test.

The most common issues will be:
- Missing imports in agentpulse_processor.py
- Missing task types in execute_task()
- Supabase table/column mismatches
- Poller not starting (check entrypoint.sh)
- Config file not mounted correctly (check docker-compose.yml volumes)
- SUPABASE_SERVICE_KEY not passed to a service

After all tests pass, run one final end-to-end:
   docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task run_pipeline
   # Wait 2 minutes
   docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_newsletter
   # Wait 1 minute
   # Send /newsletter on Telegram — should show the new format with all sections
```

---

## Quick Reference: What Each Section Tests

| Section | Tests | Depends On |
|---------|-------|------------|
| 1. Config | agentpulse-config.json structure | File exists |
| 2. Database | All new tables + columns exist | SQL was run |
| 3. Budget | AgentBudget class, daily tracking | Section 1, 2 |
| 4. Model Routing | get_model() returns correct models | Section 1 |
| 5. Task Routing | All new tasks registered in execute_task | Code changes |
| 6. Proactive | Anomaly detection, budget/cooldown checks | Section 2, 3 |
| 7. Analyst Poller | Running, picks up tasks, includes budget | Section 1, 3 |
| 8. Newsletter Poller | Running, picks up tasks | Service running |
| 9. Negotiation | Create, validate, timeout | Section 2, 5 |
| 10. End-to-End | Full pipeline with all agency features | All above |
| 11. Telegram | All new commands work | Section 5, gato restart |
| 12. Fix Summary | Compile results, fix failures | All above |
