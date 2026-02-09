#!/usr/bin/env python3
"""
Analyst task poller — bridges agent_tasks (Supabase) to the file queue
for the OpenClaw analyst agent.

POLLING:
  Every 15 seconds, queries agent_tasks where assigned_to='analyst' AND status='pending'.
  Orders by priority ASC, created_at ASC, limit 3.
  For each task: marks as in_progress, writes a JSON file to the OpenClaw workspace queue.

RESPONSE HANDLING:
  Watches workspace/agentpulse/queue/responses/ for analyst_*.result.json files.
  When found, persists the analysis results to Supabase (analysis_runs, opportunities,
  cross_signals) and updates the agent_tasks row.
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

from supabase import create_client

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WORKSPACE = Path('/home/openclaw/.openclaw/workspace')
QUEUE_DIR = WORKSPACE / 'agentpulse' / 'queue'
RESPONSES_DIR = QUEUE_DIR / 'responses'
ANALYSIS_DIR = WORKSPACE / 'agentpulse' / 'analysis'

POLL_INTERVAL = int(os.getenv('ANALYST_POLL_INTERVAL', '15'))

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('analyst-poller')

# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

supabase = None


def init():
    """Initialise the Supabase client."""
    global supabase
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')
    if not url or not key:
        logger.error('SUPABASE_URL / SUPABASE_KEY not set — cannot start')
        raise SystemExit(1)
    supabase = create_client(url, key)
    logger.info('Supabase client initialised')


# ---------------------------------------------------------------------------
# Polling — pick up pending analyst tasks
# ---------------------------------------------------------------------------

def poll():
    """Check for pending analyst tasks and write them to the file queue."""
    try:
        tasks = (
            supabase.table('agent_tasks')
            .select('*')
            .eq('status', 'pending')
            .eq('assigned_to', 'analyst')
            .order('priority', desc=False)
            .order('created_at', desc=False)
            .limit(3)
            .execute()
        )
    except Exception as e:
        logger.error(f'Error querying agent_tasks: {e}')
        return

    for task in tasks.data or []:
        task_id = task['id']
        task_type = task.get('task_type', 'unknown')
        logger.info(f'Found task {task_id}: {task_type}')

        # Mark as in_progress
        try:
            supabase.table('agent_tasks').update({
                'status': 'in_progress',
                'started_at': datetime.now(timezone.utc).isoformat()
            }).eq('id', task_id).execute()
        except Exception as e:
            logger.error(f'Failed to mark task {task_id} in_progress: {e}')
            continue

        # Write the task to the file queue for OpenClaw
        queue_file = QUEUE_DIR / f'analyst_{task_id}.json'
        payload = {
            'task': task_type,
            'task_id': task_id,
            'params': task.get('input_data', {}),
            'created_by': task.get('created_by', 'system')
        }
        try:
            queue_file.write_text(json.dumps(payload, indent=2, default=str))
            logger.info(f'Queued task {task_id} → {queue_file.name}')
        except Exception as e:
            logger.error(f'Failed to write queue file for task {task_id}: {e}')


# ---------------------------------------------------------------------------
# Response handling — process completed analyses
# ---------------------------------------------------------------------------

def check_responses():
    """Check for completed analysis results and persist to Supabase."""
    for response_file in RESPONSES_DIR.glob('analyst_*.result.json'):
        try:
            raw = response_file.read_text()
            result = json.loads(raw)
            task_id = result.get('task_id')
            if not task_id:
                logger.warning(f'Response file {response_file.name} has no task_id — skipping')
                response_file.unlink(missing_ok=True)
                continue

            logger.info(f'Processing response for task {task_id}')

            success = result.get('success', False)
            analysis = result.get('result', {})

            # ----- a) Persist analysis results -----
            if success and analysis:
                _persist_analysis_run(analysis)
                _update_opportunities(analysis)
                _persist_cross_signals(analysis)

            # ----- b) Update agent_tasks row -----
            update_payload = {
                'status': 'completed' if success else 'failed',
                'completed_at': datetime.now(timezone.utc).isoformat(),
            }
            if success:
                update_payload['output_data'] = analysis
            else:
                update_payload['error_message'] = result.get('error', 'Unknown error')

            supabase.table('agent_tasks').update(
                update_payload
            ).eq('id', task_id).execute()

            # ----- c) Delete the response file -----
            response_file.unlink(missing_ok=True)
            logger.info(f'Completed processing for task {task_id}')

        except Exception as e:
            logger.error(f'Error processing response {response_file.name}: {e}')


def _persist_analysis_run(analysis: dict):
    """Insert a row into analysis_runs."""
    try:
        self_critique = analysis.get('self_critique', {})
        supabase.table('analysis_runs').insert({
            'run_type': analysis.get('run_type', 'full_analysis'),
            'trigger': 'task',
            'status': 'completed',
            'reasoning_steps': analysis.get('reasoning_steps'),
            'key_findings': analysis.get('key_findings'),
            'analyst_notes': analysis.get('executive_summary'),
            'confidence_level': self_critique.get('confidence_level', 'medium'),
            'caveats': self_critique.get('caveats', []),
            'flags': self_critique.get('additional_data_needed', []),
            'completed_at': datetime.now(timezone.utc).isoformat()
        }).execute()
        logger.info('Inserted analysis_runs row')
    except Exception as e:
        logger.error(f'Failed to insert analysis_runs: {e}')


def _update_opportunities(analysis: dict):
    """Update opportunities with analyst reasoning."""
    for opp in analysis.get('opportunities', []):
        opp_id = opp.get('id')
        if not opp_id:
            continue
        try:
            # Read current review_count so we can increment
            current = supabase.table('opportunities').select('review_count').eq('id', opp_id).limit(1).execute()
            current_count = (current.data[0].get('review_count') or 0) if current.data else 0

            supabase.table('opportunities').update({
                'confidence_score': opp.get('confidence_score'),
                'analyst_reasoning': opp.get('reasoning_chain'),
                'analyst_confidence_notes': json.dumps(opp.get('downgrade_factors', [])),
                'signal_sources': opp.get('signal_sources'),
                'last_reviewed_at': datetime.now(timezone.utc).isoformat(),
                'review_count': current_count + 1
            }).eq('id', opp_id).execute()
            logger.info(f'Updated opportunity {opp_id}')
        except Exception as e:
            logger.error(f'Failed to update opportunity {opp_id}: {e}')


def _persist_cross_signals(analysis: dict):
    """Insert cross-pipeline signals."""
    for signal in analysis.get('cross_signals', []):
        try:
            row = {
                'signal_type': signal.get('type'),
                'description': signal.get('description'),
                'strength': signal.get('strength'),
                'reasoning': signal.get('reasoning'),
            }
            # Optional foreign keys — only include if present
            if signal.get('cluster_id'):
                row['problem_cluster_id'] = signal['cluster_id']
            if signal.get('tool_name'):
                row['tool_name'] = signal['tool_name']
            if signal.get('opportunity_id'):
                row['opportunity_id'] = signal['opportunity_id']

            supabase.table('cross_signals').insert(row).execute()
            logger.info(f"Inserted cross_signal: {signal.get('type')}")
        except Exception as e:
            logger.error(f'Failed to insert cross_signal: {e}')


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    logger.info('=' * 50)
    logger.info('  Analyst Poller Starting')
    logger.info(f'  Poll interval: {POLL_INTERVAL}s')
    logger.info('=' * 50)

    # Ensure directories exist
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    init()

    while True:
        try:
            poll()
            check_responses()
        except Exception as e:
            logger.error(f'Unhandled poll loop error: {e}')
        time.sleep(POLL_INTERVAL)
