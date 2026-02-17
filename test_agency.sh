#!/bin/bash
# AgentPulse Agency Upgrade — Comprehensive Test Script
# Run this on the remote server from ~/bitcoin_bot/docker/
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0
FAILURES=""

pass() { echo -e "${GREEN}  PASS: $1${NC}"; PASS=$((PASS+1)); }
fail() { echo -e "${RED}  FAIL: $1${NC}"; FAIL=$((FAIL+1)); FAILURES="$FAILURES\n  - $1"; }
warn() { echo -e "${YELLOW}  WARN: $1${NC}"; WARN=$((WARN+1)); }
section() { echo -e "\n${CYAN}═══════════════════════════════════════════${NC}"; echo -e "${CYAN}  SECTION $1${NC}"; echo -e "${CYAN}═══════════════════════════════════════════${NC}"; }

cd ~/bitcoin_bot/docker

# ═══════════════════════════════════════════
section "0: Services Running"
# ═══════════════════════════════════════════

for svc in processor analyst newsletter gato; do
    if docker compose ps --status running | grep -q "$svc"; then
        pass "$svc container is running"
    else
        fail "$svc container is NOT running"
    fi
done

# ═══════════════════════════════════════════
section "1: Config Validation"
# ═══════════════════════════════════════════

docker compose exec -T processor python3 -c "
import json, sys
try:
    config = json.load(open('/home/openclaw/.openclaw/config/agentpulse-config.json'))
    print('CONFIG_VALID')
except Exception as e:
    print(f'CONFIG_INVALID: {e}')
    sys.exit(1)

errors = []

models = config.get('models', {})
if 'extraction' not in models: errors.append('Missing models.extraction')
if 'default' not in models: errors.append('Missing models.default')
print(f'Models: {list(models.keys())}')

budgets = config.get('budgets', {})
if 'analyst' not in budgets: errors.append('Missing budgets.analyst')
if 'newsletter' not in budgets: errors.append('Missing budgets.newsletter')
if 'global' not in budgets: errors.append('Missing budgets.global')
print(f'Budgets: analyst tasks={list(budgets.get(\"analyst\", {}).keys())}, newsletter tasks={list(budgets.get(\"newsletter\", {}).keys())}')
print(f'Global limits: {budgets.get(\"global\", {})}')

negotiation = config.get('negotiation', {})
if 'allowed_pairs' not in negotiation: errors.append('Missing negotiation.allowed_pairs')
print(f'Negotiation: {negotiation}')

if errors:
    for e in errors:
        print(f'ERROR: {e}')
    sys.exit(1)
else:
    print('ALL_SECTIONS_OK')
" && pass "Config validation" || fail "Config validation"

# Check analyst can read config too
docker compose exec -T analyst python3 -c "
import json
from pathlib import Path
p = Path('/home/openclaw/.openclaw/config/agentpulse-config.json')
if p.exists():
    c = json.load(open(p))
    b = c.get('budgets', {}).get('analyst', {})
    print(f'ANALYST_CONFIG_OK: {list(b.keys())}')
else:
    print('ANALYST_CONFIG_MISSING')
    exit(1)
" && pass "Analyst can read config" || fail "Analyst cannot read config (config volume not mounted)"

# ═══════════════════════════════════════════
section "2: Database Tables"
# ═══════════════════════════════════════════

docker compose exec -T processor python3 -c "
from supabase import create_client
import os, sys

c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))

results = {}

# New tables
for table in ['agent_daily_usage', 'agent_negotiations']:
    try:
        r = c.table(table).select('*').limit(0).execute()
        results[table] = 'OK'
    except Exception as e:
        results[table] = f'FAILED: {e}'

# Opportunities new columns
try:
    r = c.table('opportunities').select('analyst_reasoning, signal_sources, last_reviewed_at, review_count').limit(1).execute()
    results['opportunities_columns'] = 'OK'
except Exception as e:
    results['opportunities_columns'] = f'FAILED: {e}'

# Existing tables
for table in ['moltbook_posts', 'problems', 'problem_clusters', 'opportunities', 'tool_mentions', 'tool_stats', 'agent_tasks', 'analysis_runs', 'cross_signals', 'newsletters', 'trending_topics']:
    try:
        r = c.table(table).select('id', count='exact').limit(0).execute()
        results[table] = f'OK ({r.count} rows)'
    except Exception as e:
        results[table] = f'FAILED: {e}'

for k, v in results.items():
    print(f'{k}: {v}')

failed = [k for k, v in results.items() if 'FAILED' in str(v)]
if failed:
    print(f'TABLES_FAILED: {failed}')
    sys.exit(1)
else:
    print('ALL_TABLES_OK')
" && pass "Database tables" || fail "Database tables (see output above)"

# ═══════════════════════════════════════════
section "3: Budget System"
# ═══════════════════════════════════════════

docker compose exec -T processor python3 -c "
import sys, time
sys.path.insert(0, '/home/openclaw')

# Test 1: Imports
try:
    from agentpulse_processor import AgentBudget, get_budget_config, check_daily_budget, increment_daily_usage, get_daily_usage
    print('Budget imports: OK')
except ImportError as e:
    print(f'Budget imports: FAILED - {e}')
    sys.exit(1)

# Test 2: Create budget (NOTE: AgentBudget takes 2 args: task_type, agent_name)
try:
    budget = AgentBudget('full_analysis', 'analyst')
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
    print(f'Daily budget check: {result}')
except Exception as e:
    print(f'Daily budget check: FAILED - {e}')

# Test 5: Increment daily usage
try:
    increment_daily_usage('test_agent', llm_calls=5, subtasks=1)
    usage = get_daily_usage('test_agent')
    print(f'Daily usage after increment: {usage}')
except Exception as e:
    print(f'Daily usage increment: FAILED - {e}')

print('BUDGET_TESTS_DONE')
" && pass "Budget system" || fail "Budget system"

# ═══════════════════════════════════════════
section "4: Model Routing"
# ═══════════════════════════════════════════

docker compose exec -T processor python3 -c "
import sys
sys.path.insert(0, '/home/openclaw')

try:
    from agentpulse_processor import get_model

    extraction = get_model('extraction')
    clustering = get_model('clustering')
    opp = get_model('opportunity_generation')
    default = get_model('nonexistent_task')

    print(f'extraction: {extraction}')
    print(f'clustering: {clustering}')
    print(f'opportunity_generation: {opp}')
    print(f'default (fallback): {default}')

    assert 'mini' in extraction, f'extraction should use mini, got {extraction}'
    assert 'mini' in clustering, f'clustering should use mini, got {clustering}'
    assert 'mini' not in opp, f'opp should NOT use mini, got {opp}'
    print('MODEL_ROUTING_OK')
except ImportError:
    print('get_model function not found')
    sys.exit(1)
except Exception as e:
    print(f'Model routing: FAILED - {e}')
    sys.exit(1)
" && pass "Model routing" || fail "Model routing"

# ═══════════════════════════════════════════
section "5: Processor Task Routing"
# ═══════════════════════════════════════════

docker compose exec -T processor python3 -c "
import sys, inspect
sys.path.insert(0, '/home/openclaw')

from agentpulse_processor import execute_task
source = inspect.getsource(execute_task)

new_tasks = [
    'get_budget_status',
    'get_budget_config',
    'targeted_scrape',
    'can_create_subtask',
    'proactive_scan',
    'send_alert',
    'create_negotiation',
    'respond_to_negotiation',
    'get_active_negotiations',
    'check_negotiation_timeouts',
    'get_recent_alerts',
    'prepare_analysis',
]

missing = []
for task in new_tasks:
    if task in source:
        print(f'{task}: registered')
    else:
        print(f'{task}: MISSING')
        missing.append(task)

if missing:
    print(f'ROUTING_FAILED: missing {missing}')
    sys.exit(1)
else:
    print('ALL_TASKS_REGISTERED')
" && pass "Task routing" || fail "Task routing"

# ═══════════════════════════════════════════
section "6: Proactive Monitoring"
# ═══════════════════════════════════════════

docker compose exec -T processor python3 -c "
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
    print('detect_anomalies not found')
    sys.exit(1)
except Exception as e:
    print(f'detect_anomalies: FAILED - {e}')
    sys.exit(1)

# Test proactive budget check
try:
    from agentpulse_processor import check_proactive_budget
    result = check_proactive_budget()
    print(f'Proactive budget available: {result}')
except ImportError:
    print('check_proactive_budget not found')
except Exception as e:
    print(f'check_proactive_budget: FAILED - {e}')

# Test proactive cooldown
try:
    from agentpulse_processor import check_proactive_cooldown
    result = check_proactive_cooldown()
    print(f'Proactive cooldown clear: {result}')
except ImportError:
    print('check_proactive_cooldown not found')
except Exception as e:
    print(f'check_proactive_cooldown: FAILED - {e}')

# Test full proactive scan
try:
    from agentpulse_processor import proactive_scan
    result = proactive_scan()
    print(f'Proactive scan result: {result}')
    print('PROACTIVE_OK')
except Exception as e:
    print(f'proactive_scan: FAILED - {e}')
    sys.exit(1)
" && pass "Proactive monitoring" || fail "Proactive monitoring"

# ═══════════════════════════════════════════
section "7: Analyst Poller"
# ═══════════════════════════════════════════

echo "  Checking analyst process..."
docker compose exec -T analyst pgrep -f analyst_poller.py > /dev/null 2>&1 && pass "Analyst poller process running" || fail "Analyst poller process NOT running"

echo "  Checking analyst logs (last 10 lines)..."
docker compose logs analyst 2>&1 | tail -10

echo ""
echo "  Checking analyst can read budget config..."
docker compose exec -T analyst python3 -c "
import json
from pathlib import Path
p = Path('/home/openclaw/.openclaw/config/agentpulse-config.json')
if p.exists():
    c = json.load(open(p))
    b = c.get('budgets', {}).get('analyst', {}).get('full_analysis', {})
    print(f'Analyst budget for full_analysis: {b}')
    if b:
        print('ANALYST_BUDGET_OK')
    else:
        print('ANALYST_BUDGET_EMPTY (using defaults)')
else:
    print('CONFIG_NOT_FOUND — config volume not mounted')
    exit(1)
" && pass "Analyst budget config accessible" || fail "Analyst cannot access budget config"

# ═══════════════════════════════════════════
section "8: Newsletter Poller"
# ═══════════════════════════════════════════

docker compose exec -T newsletter pgrep -f newsletter_poller.py > /dev/null 2>&1 && pass "Newsletter poller process running" || fail "Newsletter poller process NOT running"

echo "  Newsletter logs (last 5 lines):"
docker compose logs newsletter 2>&1 | tail -5

# ═══════════════════════════════════════════
section "9: Negotiation System"
# ═══════════════════════════════════════════

docker compose exec -T processor python3 -c "
import sys
sys.path.insert(0, '/home/openclaw')
from agentpulse_processor import execute_task

# Test 1: Create negotiation (valid pair: newsletter -> analyst)
try:
    result = execute_task({'task': 'create_negotiation', 'params': {
        'requesting_agent': 'newsletter',
        'responding_agent': 'analyst',
        'request_summary': 'Test negotiation: need stronger opportunities',
        'quality_criteria': 'At least 3 opportunities above 0.6'
    }})
    print(f'Create negotiation: {result}')
    if 'error' in str(result).lower() and 'pair' not in str(result).lower():
        print('CREATE_NEGOTIATION_FAILED')
        sys.exit(1)
    print('CREATE_NEGOTIATION_OK')
except Exception as e:
    print(f'Create negotiation: FAILED - {e}')
    sys.exit(1)

# Test 2: Get active negotiations
try:
    result = execute_task({'task': 'get_active_negotiations', 'params': {}})
    print(f'Active negotiations: {result}')
    print('GET_NEGOTIATIONS_OK')
except Exception as e:
    print(f'Get negotiations: FAILED - {e}')

# Test 3: Pair validation (processor should NOT be allowed to ask anyone)
try:
    result = execute_task({'task': 'create_negotiation', 'params': {
        'requesting_agent': 'processor',
        'responding_agent': 'analyst',
        'request_summary': 'This should fail',
        'quality_criteria': 'N/A'
    }})
    if 'error' in str(result).lower() or 'not allowed' in str(result).lower():
        print(f'Pair validation works: processor correctly blocked')
        print('PAIR_VALIDATION_OK')
    else:
        print(f'Pair validation FAILED: processor was allowed (result: {result})')
except Exception as e:
    print(f'Pair validation: {e}')
" && pass "Negotiation system" || fail "Negotiation system"

# ═══════════════════════════════════════════
section "10: Quick Smoke Test (no full pipeline)"
# ═══════════════════════════════════════════

echo "  Testing budget status command..."
docker compose exec -T processor python3 -c "
import sys
sys.path.insert(0, '/home/openclaw')
from agentpulse_processor import execute_task

# Budget status
result = execute_task({'task': 'get_budget_status', 'params': {}})
print(f'Budget status: {result}')

# Budget config
result = execute_task({'task': 'get_budget_config', 'params': {}})
print(f'Budget config keys: {list(result.keys()) if isinstance(result, dict) else result}')

# Recent alerts
result = execute_task({'task': 'get_recent_alerts', 'params': {}})
print(f'Recent alerts: {result}')

print('SMOKE_TEST_OK')
" && pass "Smoke test commands" || fail "Smoke test commands"

# ═══════════════════════════════════════════
section "SUMMARY"
# ═══════════════════════════════════════════

echo ""
echo -e "${GREEN}  PASSED: $PASS${NC}"
echo -e "${RED}  FAILED: $FAIL${NC}"
echo -e "${YELLOW}  WARNINGS: $WARN${NC}"

if [ $FAIL -gt 0 ]; then
    echo -e "\n${RED}  Failures:${NC}"
    echo -e "$FAILURES"
fi

echo ""
if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}  All tests passed! Ready for end-to-end pipeline test.${NC}"
    echo "  Next: docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task run_pipeline"
else
    echo -e "${RED}  Fix the failures above, then re-run this script.${NC}"
fi
