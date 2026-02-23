#!/usr/bin/env python3
"""
TEST 1B: Schema Verification for research_queue, spotlight_history, predictions, spotlight_cooldown.
Runs CRUD operations against each table and validates field integrity.
Cleans up ALL test data regardless of pass/fail.
"""

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

env_path = Path(__file__).resolve().parent.parent / 'config' / '.env'
load_dotenv(env_path)

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("FATAL: SUPABASE_URL or SUPABASE_KEY not set in config/.env")
    sys.exit(1)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

TEST_ISSUE_NUMBERS = [999, 990]
results = {}


def cleanup():
    """Remove ALL test data created by this script."""
    for issue in TEST_ISSUE_NUMBERS:
        try:
            sb.table('predictions').delete().eq('issue_number', issue).execute()
        except Exception:
            pass
        try:
            sb.table('spotlight_history').delete().eq('issue_number', issue).execute()
        except Exception:
            pass
    try:
        sb.table('research_queue').delete().eq('topic_id', 'test-topic').execute()
    except Exception:
        pass
    try:
        sb.table('research_queue').delete().eq('topic_id', 'test-topic-cooldown').execute()
    except Exception:
        pass


def test_research_queue():
    """Test research_queue CRUD."""
    name = 'research_queue'
    try:
        row = {
            'topic_id': 'test-topic',
            'topic_name': 'Test Topic',
            'priority_score': 0.75,
            'velocity': 0.6,
            'source_diversity': 0.8,
            'lifecycle_phase': 'debating',
            'mode': 'spotlight',
            'status': 'queued',
            'context_payload': {'key1': 'value1', 'key2': [1, 2, 3]},
            'issue_number': 999,
        }
        ins = sb.table('research_queue').insert(row).execute()
        assert ins.data, "Insert returned no data"
        rid = ins.data[0]['id']

        read = sb.table('research_queue').select('*').eq('id', rid).execute()
        assert read.data, "Read returned no data"
        r = read.data[0]
        assert r['topic_id'] == 'test-topic'
        assert r['topic_name'] == 'Test Topic'
        assert abs(r['priority_score'] - 0.75) < 0.001
        assert abs(r['velocity'] - 0.6) < 0.001
        assert abs(r['source_diversity'] - 0.8) < 0.001
        assert r['lifecycle_phase'] == 'debating'
        assert r['mode'] == 'spotlight'
        assert r['status'] == 'queued'
        assert r['context_payload']['key1'] == 'value1'
        assert r['issue_number'] == 999

        sb.table('research_queue').update({'status': 'in_progress'}).eq('id', rid).execute()
        read2 = sb.table('research_queue').select('status').eq('id', rid).execute()
        assert read2.data[0]['status'] == 'in_progress'

        sb.table('research_queue').delete().eq('id', rid).execute()
        gone = sb.table('research_queue').select('id').eq('id', rid).execute()
        assert not gone.data, "Row should be deleted"

        results[name] = 'PASS'
        print(f"  {name}: PASS")
    except Exception as e:
        results[name] = f'FAIL ({e})'
        print(f"  {name}: FAIL — {e}")


def test_spotlight_history():
    """Test spotlight_history CRUD with FK to research_queue."""
    name = 'spotlight_history'
    rq_id = None
    sh_id = None
    try:
        rq = sb.table('research_queue').insert({
            'topic_id': 'test-topic',
            'topic_name': 'Test Topic',
            'priority_score': 0.75,
            'status': 'queued',
            'issue_number': 999,
        }).execute()
        rq_id = rq.data[0]['id']

        sources_used = [{'source_name': 'TestSource', 'url': 'https://example.com', 'tier': 1, 'relevant_quote': 'A test quote'}]
        row = {
            'research_queue_id': rq_id,
            'topic_id': 'test-topic',
            'topic_name': 'Test Topic',
            'issue_number': 999,
            'mode': 'spotlight',
            'thesis': 'Test thesis',
            'evidence': 'Test evidence',
            'counter_argument': 'Test counter',
            'prediction': 'Test prediction',
            'builder_implications': 'Test implications',
            'full_output': 'Full test output',
            'sources_used': sources_used,
        }
        ins = sb.table('spotlight_history').insert(row).execute()
        assert ins.data, "Insert returned no data"
        sh_id = ins.data[0]['id']

        read = sb.table('spotlight_history').select('*').eq('id', sh_id).execute()
        assert read.data, "Read returned no data"
        r = read.data[0]
        assert r['research_queue_id'] == rq_id
        assert r['thesis'] == 'Test thesis'
        assert r['evidence'] == 'Test evidence'
        assert r['counter_argument'] == 'Test counter'
        assert r['prediction'] == 'Test prediction'
        assert r['builder_implications'] == 'Test implications'
        assert r['full_output'] == 'Full test output'
        assert isinstance(r['sources_used'], list)
        assert r['sources_used'][0]['source_name'] == 'TestSource'

        results[name] = 'PASS'
        print(f"  {name}: PASS")
    except Exception as e:
        results[name] = f'FAIL ({e})'
        print(f"  {name}: FAIL — {e}")
    finally:
        if sh_id:
            try:
                sb.table('spotlight_history').delete().eq('id', sh_id).execute()
            except Exception:
                pass
        if rq_id:
            try:
                sb.table('research_queue').delete().eq('id', rq_id).execute()
            except Exception:
                pass


def test_predictions():
    """Test predictions status transitions with spotlight FK."""
    name = 'predictions'
    rq_id = None
    sh_id = None
    pred_id = None
    try:
        rq = sb.table('research_queue').insert({
            'topic_id': 'test-topic',
            'topic_name': 'Test Topic',
            'priority_score': 0.5,
            'status': 'completed',
            'issue_number': 999,
        }).execute()
        rq_id = rq.data[0]['id']

        sh = sb.table('spotlight_history').insert({
            'research_queue_id': rq_id,
            'topic_id': 'test-topic',
            'topic_name': 'Test Topic',
            'issue_number': 999,
            'thesis': 'T', 'evidence': 'E', 'counter_argument': 'C',
            'prediction': 'P', 'full_output': 'F',
        }).execute()
        sh_id = sh.data[0]['id']

        pred = sb.table('predictions').insert({
            'spotlight_id': sh_id,
            'topic_id': 'test-topic',
            'prediction_text': 'Test prediction text',
            'issue_number': 999,
            'status': 'open',
        }).execute()
        assert pred.data, "Insert returned no data"
        pred_id = pred.data[0]['id']

        read1 = sb.table('predictions').select('*').eq('id', pred_id).execute()
        assert read1.data[0]['status'] == 'open'
        assert read1.data[0]['spotlight_id'] == sh_id
        assert read1.data[0]['prediction_text'] == 'Test prediction text'

        now_iso = datetime.now(timezone.utc).isoformat()
        sb.table('predictions').update({
            'status': 'flagged',
            'evidence_notes': 'New evidence found',
            'flagged_at': now_iso,
        }).eq('id', pred_id).execute()
        read2 = sb.table('predictions').select('status, evidence_notes, flagged_at').eq('id', pred_id).execute()
        assert read2.data[0]['status'] == 'flagged'
        assert read2.data[0]['evidence_notes'] == 'New evidence found'
        assert read2.data[0]['flagged_at'] is not None

        sb.table('predictions').update({
            'status': 'confirmed',
            'resolution_notes': 'Prediction confirmed by market data',
            'resolved_at': now_iso,
        }).eq('id', pred_id).execute()
        read3 = sb.table('predictions').select('status, resolution_notes, resolved_at').eq('id', pred_id).execute()
        assert read3.data[0]['status'] == 'confirmed'
        assert read3.data[0]['resolution_notes'] == 'Prediction confirmed by market data'
        assert read3.data[0]['resolved_at'] is not None

        results[name] = 'PASS'
        print(f"  {name}: PASS")
    except Exception as e:
        results[name] = f'FAIL ({e})'
        print(f"  {name}: FAIL — {e}")
    finally:
        if pred_id:
            try:
                sb.table('predictions').delete().eq('id', pred_id).execute()
            except Exception:
                pass
        if sh_id:
            try:
                sb.table('spotlight_history').delete().eq('id', sh_id).execute()
            except Exception:
                pass
        if rq_id:
            try:
                sb.table('research_queue').delete().eq('id', rq_id).execute()
            except Exception:
                pass


def test_spotlight_cooldown():
    """Test spotlight_cooldown view logic (last 4 issues = on cooldown)."""
    name = 'spotlight_cooldown'
    rq_id = None
    sh_ids = []
    try:
        rq = sb.table('research_queue').insert({
            'topic_id': 'test-topic-cooldown',
            'topic_name': 'Cooldown Test',
            'priority_score': 0.5,
            'status': 'completed',
            'issue_number': 999,
        }).execute()
        rq_id = rq.data[0]['id']

        sh1 = sb.table('spotlight_history').insert({
            'research_queue_id': rq_id,
            'topic_id': 'test-topic-cooldown-recent',
            'topic_name': 'Recent Cooldown Topic',
            'issue_number': 999,
            'thesis': 'T', 'evidence': 'E', 'counter_argument': 'C',
            'prediction': 'P', 'full_output': 'F',
        }).execute()
        sh_ids.append(sh1.data[0]['id'])

        sh2 = sb.table('spotlight_history').insert({
            'research_queue_id': rq_id,
            'topic_id': 'test-topic-cooldown-old',
            'topic_name': 'Old Cooldown Topic',
            'issue_number': 990,
            'thesis': 'T', 'evidence': 'E', 'counter_argument': 'C',
            'prediction': 'P', 'full_output': 'F',
        }).execute()
        sh_ids.append(sh2.data[0]['id'])

        view = sb.table('spotlight_cooldown').select('*').in_('topic_id', [
            'test-topic-cooldown-recent', 'test-topic-cooldown-old'
        ]).execute()

        recent = [r for r in view.data if r['topic_id'] == 'test-topic-cooldown-recent']
        old = [r for r in view.data if r['topic_id'] == 'test-topic-cooldown-old']

        assert recent, "Recent cooldown topic not found in view"
        assert recent[0]['on_cooldown'] is True, f"Expected on_cooldown=true, got {recent[0]['on_cooldown']}"

        assert old, "Old cooldown topic not found in view"
        assert old[0]['on_cooldown'] is False, f"Expected on_cooldown=false, got {old[0]['on_cooldown']}"

        results[name] = 'PASS'
        print(f"  {name}: PASS")
    except Exception as e:
        results[name] = f'FAIL ({e})'
        print(f"  {name}: FAIL — {e}")
    finally:
        for sid in reversed(sh_ids):
            try:
                sb.table('spotlight_history').delete().eq('id', sid).execute()
            except Exception:
                pass
        if rq_id:
            try:
                sb.table('research_queue').delete().eq('id', rq_id).execute()
            except Exception:
                pass


if __name__ == '__main__':
    print("\n=== TEST 1B: Schema Verification ===\n")

    cleanup()

    test_research_queue()
    test_spotlight_history()
    test_predictions()
    test_spotlight_cooldown()

    cleanup()

    print("\n=== SUMMARY ===")
    all_pass = True
    for table, status in results.items():
        flag = "PASS" if status == "PASS" else "FAIL"
        print(f"  {table}: {status}")
        if flag != "PASS":
            all_pass = False

    print(f"\nOverall: {'ALL PASS' if all_pass else 'SOME FAILURES'}\n")
    sys.exit(0 if all_pass else 1)
