#!/usr/bin/env python3
"""
AgentPulse Processor

Background processor for AgentPulse intelligence pipelines.
Handles:
- Moltbook scraping (direct API)
- Problem extraction (OpenAI)
- Clustering and opportunity generation
- Queue processing for agent-initiated tasks
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import argparse

import httpx
import schedule
import threading
from openai import OpenAI
from supabase import create_client, Client
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

# ============================================================================
# Configuration
# ============================================================================

load_dotenv('/home/openclaw/.env')

# Paths
WORKSPACE = Path(os.getenv('OPENCLAW_DATA_DIR', '/home/openclaw/.openclaw')) / 'workspace'
QUEUE_DIR = WORKSPACE / 'agentpulse' / 'queue'
RESPONSES_DIR = QUEUE_DIR / 'responses'
OPPORTUNITIES_DIR = WORKSPACE / 'agentpulse' / 'opportunities'
CACHE_DIR = WORKSPACE / 'agentpulse' / 'cache'
LOGS_DIR = Path(os.getenv('OPENCLAW_DATA_DIR', '/home/openclaw/.openclaw')) / 'logs'

# Ensure directories exist
for d in [QUEUE_DIR, RESPONSES_DIR, OPPORTUNITIES_DIR, CACHE_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# API Configuration
# Moltbook API - hardcoded to correct endpoint (env var often has wrong value)
MOLTBOOK_API_BASE = 'https://www.moltbook.com/api/v1'
MOLTBOOK_API_TOKEN = os.getenv('MOLTBOOK_API_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('AGENTPULSE_OPENAI_MODEL', 'gpt-4o')

# Telegram (for notifications)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_OWNER_ID = os.getenv('TELEGRAM_OWNER_ID')

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / 'agentpulse.log')
    ]
)
logger = logging.getLogger('agentpulse')

# ============================================================================
# Clients
# ============================================================================

supabase: Optional[Client] = None
openai_client: Optional[OpenAI] = None

def init_clients():
    """Initialize API clients."""
    global supabase, openai_client
    
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized")
    else:
        logger.warning("Supabase not configured")
    
    if OPENAI_API_KEY:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI client initialized")
    else:
        logger.warning("OpenAI not configured")

# ============================================================================
# Moltbook Scraping
# ============================================================================

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_moltbook_posts(submolt: str = None, limit: int = 50, sort: str = 'new') -> list:
    """Fetch posts from Moltbook API."""
    if not MOLTBOOK_API_TOKEN:
        logger.error("MOLTBOOK_API_TOKEN not set")
        return []
    
    endpoint = f"{MOLTBOOK_API_BASE}/posts"
    
    headers = {
        'Authorization': f'Bearer {MOLTBOOK_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    params = {'limit': limit, 'sort': sort}
    if submolt:
        params['submolt'] = submolt
    
    with httpx.Client(timeout=30) as client:
        response = client.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        # API returns {"success": true, "posts": [...]}
        if isinstance(data, dict) and 'posts' in data:
            return data['posts']
        return data if isinstance(data, list) else []

def scrape_moltbook(submolts: list = None, posts_per_submolt: int = 50) -> dict:
    """Scrape Moltbook and store in Supabase."""
    # Note: We fetch all posts and they include submolt info
    total_posts_to_fetch = posts_per_submolt * (len(submolts) if submolts else 5)
    
    run_id = log_pipeline_start('scrape')
    total_new = 0
    total_fetched = 0
    errors = []
    
    try:
        logger.info(f"Scraping Moltbook (limit={total_posts_to_fetch})")
        posts = fetch_moltbook_posts(limit=total_posts_to_fetch)
        total_fetched = len(posts)
        
        for post in posts:
            try:
                new = store_post(post)
                if new:
                    total_new += 1
            except Exception as e:
                logger.error(f"Error storing post {post.get('id')}: {e}")
                errors.append(str(e))
                
    except Exception as e:
        logger.error(f"Error scraping Moltbook: {e}")
        errors.append(str(e))
    
    result = {
        'total_fetched': total_fetched,
        'total_new': total_new,
        'errors': errors
    }
    
    log_pipeline_end(run_id, 'completed' if not errors else 'completed_with_errors', result)
    logger.info(f"Scrape complete: {total_new} new posts from {total_fetched} fetched")
    
    return result

def store_post(post: dict, submolt_override: str = None) -> bool:
    """Store a post in Supabase. Returns True if new."""
    if not supabase:
        # Fallback to local cache
        cache_file = CACHE_DIR / f"posts_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(cache_file, 'a') as f:
            f.write(json.dumps(post) + '\n')
        return True
    
    moltbook_id = post.get('id')
    
    # Check if exists
    existing = supabase.table('moltbook_posts').select('id').eq('moltbook_id', moltbook_id).execute()
    if existing.data:
        return False
    
    # Extract submolt name from post object or use override
    submolt_obj = post.get('submolt', {})
    submolt_name = submolt_override or (submolt_obj.get('name') if isinstance(submolt_obj, dict) else submolt_obj)
    
    # Insert new post
    record = {
        'moltbook_id': moltbook_id,
        'author_name': post.get('author', {}).get('name'),
        'author_id': post.get('author', {}).get('id'),
        'title': post.get('title'),
        'content': post.get('content'),
        'submolt': submolt_name,
        'post_type': 'post',
        'upvotes': post.get('upvotes', 0),
        'downvotes': post.get('downvotes', 0),
        'comment_count': post.get('comment_count', 0),
        'moltbook_created_at': post.get('created_at'),
        'raw_json': post,
        'processed': False
    }
    
    supabase.table('moltbook_posts').insert(record).execute()
    return True

# ============================================================================
# Problem Extraction
# ============================================================================

PROBLEM_EXTRACTION_PROMPT = """You are an analyst extracting business problems from social media posts by AI agents.

Analyze these posts and extract any problems, frustrations, or unmet needs mentioned.

For each problem found, provide:
1. problem_description: Clear 1-sentence description of the problem
2. category: One of [tools, infrastructure, communication, payments, security, data, coordination, identity, other]
3. signal_phrases: The exact phrases that indicate this problem
4. severity: low, medium, or high based on frustration level
5. willingness_to_pay: none, implied, or explicit

Posts to analyze:
{posts}

Respond ONLY with valid JSON:
{{
  "problems": [
    {{
      "problem_description": "...",
      "category": "...",
      "signal_phrases": ["..."],
      "severity": "...",
      "willingness_to_pay": "...",
      "source_post_ids": ["..."]
    }}
  ]
}}

Focus on actionable problems. Ignore general complaints without clear problems."""

def extract_problems(hours_back: int = 48) -> dict:
    """Extract problems from recent posts."""
    if not supabase or not openai_client:
        logger.error("Supabase or OpenAI not configured")
        return {'error': 'Not configured'}
    
    run_id = log_pipeline_start('extract_problems')
    
    # Fetch unprocessed posts
    cutoff = datetime.utcnow() - timedelta(hours=hours_back)
    posts = supabase.table('moltbook_posts')\
        .select('*')\
        .eq('processed', False)\
        .gte('scraped_at', cutoff.isoformat())\
        .limit(25)\
        .execute()
    
    if not posts.data:
        logger.info("No unprocessed posts found")
        return {'problems_found': 0}
    
    logger.info(f"Processing {len(posts.data)} posts")
    logger.info(f"Using model: {OPENAI_MODEL} for problem extraction")
    
    # Format posts for prompt
    posts_text = "\n\n".join([
        f"[Post ID: {p['moltbook_id']}]\n{p.get('title', '')}\n{p['content']}"
        for p in posts.data
    ])
    
    # Call OpenAI
    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You extract business problems from text. Respond only with valid JSON."},
                {"role": "user", "content": PROBLEM_EXTRACTION_PROMPT.format(posts=posts_text)}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        time.sleep(2)  # Rate limiting: avoid hitting API limits
        
        result_text = response.choices[0].message.content
        # Clean up potential markdown formatting
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]
        result_text = result_text.strip()
        
        problems_data = json.loads(result_text)
        
    except Exception as e:
        logger.error(f"OpenAI extraction failed: {e}")
        log_pipeline_end(run_id, 'failed', {'error': str(e)})
        return {'error': str(e)}
    
    # Store problems
    problems_created = 0
    for problem in problems_data.get('problems', []):
        try:
            store_problem(problem)
            problems_created += 1
        except Exception as e:
            logger.error(f"Error storing problem: {e}")
    
    # Mark posts as processed
    post_ids = [p['id'] for p in posts.data]
    supabase.table('moltbook_posts')\
        .update({'processed': True})\
        .in_('id', post_ids)\
        .execute()
    
    result = {
        'posts_processed': len(posts.data),
        'problems_found': problems_created
    }
    
    log_pipeline_end(run_id, 'completed', result)
    return result

def store_problem(problem: dict):
    """Store extracted problem in Supabase."""
    if not supabase:
        return
    
    record = {
        'description': problem['problem_description'],
        'category': problem['category'],
        'signal_phrases': problem.get('signal_phrases', []),
        'source_post_ids': problem.get('source_post_ids', []),
        'frequency_count': 1,
        'metadata': {
            'severity': problem.get('severity'),
            'willingness_to_pay': problem.get('willingness_to_pay')
        }
    }
    
    supabase.table('problems').insert(record).execute()

# ============================================================================
# Opportunity Generation
# ============================================================================

OPPORTUNITY_PROMPT = """You are a startup analyst generating business opportunity briefs.

Given this problem cluster data, generate a business opportunity brief.

Problem Data:
{problem_data}

Generate a brief with these fields:
1. title: Catchy opportunity name
2. problem_summary: 2-3 sentences on the problem
3. proposed_solution: High-level solution concept
4. business_model: SaaS, API, Marketplace, or other
5. target_market: Who would buy this
6. market_size_estimate: Rough estimate
7. why_now: Why this timing makes sense
8. confidence_score: 0.0-1.0 based on signal strength

Respond ONLY with valid JSON."""

def generate_opportunities(min_frequency: int = 1, limit: int = 5) -> dict:
    """Generate opportunities from top problems."""
    if not supabase or not openai_client:
        return {'error': 'Not configured'}
    
    run_id = log_pipeline_start('generate_opportunities')
    
    # Get top problems
    problems = supabase.table('problems')\
        .select('*')\
        .gte('frequency_count', min_frequency)\
        .order('frequency_count', desc=True)\
        .limit(limit * 2)\
        .execute()
    
    if not problems.data:
        return {'opportunities_generated': 0}
    
    opportunities_created = 0
    logger.info(f"Using model: {OPENAI_MODEL} for opportunity generation")
    
    for problem in problems.data[:limit]:
        try:
            problem_data = json.dumps({
                'description': problem['description'],
                'category': problem['category'],
                'frequency': problem['frequency_count'],
                'signals': problem.get('signal_phrases', []),
                'metadata': problem.get('metadata', {})
            }, indent=2)
            
            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You generate startup opportunity briefs. Respond only with valid JSON."},
                    {"role": "user", "content": OPPORTUNITY_PROMPT.format(problem_data=problem_data)}
                ],
                temperature=0.5,
                max_tokens=2000
            )
            time.sleep(2)  # Rate limiting: avoid hitting API limits
            
            result_text = response.choices[0].message.content
            if result_text.startswith('```'):
                result_text = result_text.split('```')[1]
                if result_text.startswith('json'):
                    result_text = result_text[4:]
            
            opp_data = json.loads(result_text.strip())
            store_opportunity(opp_data, problem['id'])
            opportunities_created += 1
            
            # Also save to local file
            save_opportunity_brief(opp_data)
            
        except Exception as e:
            logger.error(f"Error generating opportunity: {e}")
    
    result = {'opportunities_generated': opportunities_created}
    log_pipeline_end(run_id, 'completed', result)
    return result

def store_opportunity(opp: dict, problem_id: str = None):
    """Store opportunity in Supabase."""
    if not supabase:
        return
    
    record = {
        'title': opp.get('title'),
        'problem_summary': opp.get('problem_summary'),
        'proposed_solution': opp.get('proposed_solution'),
        'business_model': opp.get('business_model'),
        'target_market': opp.get('target_market'),
        'market_size_estimate': opp.get('market_size_estimate'),
        'why_now': opp.get('why_now'),
        'confidence_score': opp.get('confidence_score', 0.5),
        'status': 'draft'
    }
    
    supabase.table('opportunities').insert(record).execute()

def save_opportunity_brief(opp: dict):
    """Save opportunity as local markdown file."""
    filename = f"opp_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{opp.get('title', 'untitled')[:30]}.md"
    filename = "".join(c if c.isalnum() or c in '-_.' else '_' for c in filename)
    
    content = f"""# {opp.get('title', 'Untitled Opportunity')}

**Generated:** {datetime.now().isoformat()}
**Confidence:** {opp.get('confidence_score', 'N/A')}

## Problem

{opp.get('problem_summary', 'N/A')}

## Proposed Solution

{opp.get('proposed_solution', 'N/A')}

## Business Model

{opp.get('business_model', 'N/A')}

## Target Market

{opp.get('target_market', 'N/A')}

## Market Size

{opp.get('market_size_estimate', 'N/A')}

## Why Now

{opp.get('why_now', 'N/A')}
"""
    
    (OPPORTUNITIES_DIR / filename).write_text(content)

# ============================================================================
# Pipeline Logging
# ============================================================================

def log_pipeline_start(pipeline: str) -> str:
    """Log pipeline start, return run ID."""
    if not supabase:
        return str(time.time())
    
    result = supabase.table('pipeline_runs').insert({
        'pipeline': pipeline,
        'status': 'running',
        'trigger_type': 'manual'  # or 'scheduled'
    }).execute()
    
    return result.data[0]['id'] if result.data else str(time.time())

def log_pipeline_end(run_id: str, status: str, results: dict):
    """Log pipeline completion."""
    if not supabase:
        return
    
    try:
        supabase.table('pipeline_runs').update({
            'status': status,
            'completed_at': datetime.utcnow().isoformat(),
            'results': results
        }).eq('id', run_id).execute()
    except:
        pass  # Non-critical

# ============================================================================
# Queue Processing
# ============================================================================

def process_queue():
    """Process pending tasks from the queue directory."""
    for task_file in QUEUE_DIR.glob('*.json'):
        if task_file.name.startswith('.'):
            continue
        
        logger.info(f"Processing task: {task_file.name}")
        
        try:
            task = json.loads(task_file.read_text())
            result = execute_task(task)
            
            # Write result
            result_file = RESPONSES_DIR / f"{task_file.stem}.result.json"
            result_file.write_text(json.dumps({
                'success': True,
                'task': task.get('task'),
                'result': result,
                'completed_at': datetime.utcnow().isoformat()
            }, indent=2))
            
        except Exception as e:
            logger.error(f"Task failed: {e}")
            result_file = RESPONSES_DIR / f"{task_file.stem}.result.json"
            result_file.write_text(json.dumps({
                'success': False,
                'error': str(e),
                'completed_at': datetime.utcnow().isoformat()
            }, indent=2))
        
        finally:
            task_file.unlink()  # Remove processed task

def execute_task(task: dict) -> dict:
    """Execute a queued task."""
    task_type = task.get('task')
    params = task.get('params', {})
    
    if task_type == 'scrape':
        return scrape_moltbook(
            submolts=params.get('submolts'),
            posts_per_submolt=params.get('posts_per_submolt', 50)
        )
    
    elif task_type == 'extract_problems':
        return extract_problems(hours_back=params.get('hours_back', 48))
    
    elif task_type == 'generate_opportunities':
        return generate_opportunities(
            min_frequency=params.get('min_frequency', 1),
            limit=params.get('limit', 5)
        )
    
    elif task_type == 'run_pipeline':
        # Full pipeline run
        scrape_result = scrape_moltbook()
        extract_result = extract_problems()
        opp_result = generate_opportunities(min_frequency=1)
        return {
            'scrape': scrape_result,
            'extract': extract_result,
            'opportunities': opp_result
        }
    
    elif task_type == 'get_opportunities':
        return get_current_opportunities(
            limit=params.get('limit', 5),
            min_score=params.get('min_score', 0.0)
        )
    
    elif task_type == 'status':
        return get_status()
    
    else:
        return {'error': f'Unknown task: {task_type}'}

def get_current_opportunities(limit: int = 5, min_score: float = 0.0) -> dict:
    """Get current top opportunities."""
    if not supabase:
        # Read from local files
        opps = []
        for f in sorted(OPPORTUNITIES_DIR.glob('*.md'), reverse=True)[:limit]:
            opps.append({'file': f.name, 'content': f.read_text()[:500]})
        return {'opportunities': opps, 'source': 'local'}
    
    result = supabase.table('opportunities')\
        .select('*')\
        .gte('confidence_score', min_score)\
        .eq('status', 'draft')\
        .order('confidence_score', desc=True)\
        .limit(limit)\
        .execute()
    
    return {'opportunities': result.data, 'source': 'supabase'}

def get_status() -> dict:
    """Get AgentPulse system status."""
    status = {
        'supabase_connected': supabase is not None,
        'openai_connected': openai_client is not None,
        'moltbook_configured': MOLTBOOK_API_TOKEN is not None,
        'queue_pending': len(list(QUEUE_DIR.glob('*.json'))),
        'opportunities_local': len(list(OPPORTUNITIES_DIR.glob('*.md')))
    }
    
    if supabase:
        try:
            stats = supabase.rpc('get_scrape_stats').execute()
            status['db_stats'] = stats.data
        except:
            pass
    
    return status

# ============================================================================
# Telegram Notifications
# ============================================================================

def send_telegram(message: str):
    """Send notification to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_OWNER_ID:
        return
    
    try:
        with httpx.Client() as client:
            client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={
                    'chat_id': TELEGRAM_OWNER_ID,
                    'text': message,
                    'parse_mode': 'Markdown'
                }
            )
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")

# ============================================================================
# Scheduled Tasks
# ============================================================================

def scheduled_scrape():
    """Scheduled Moltbook scraping task."""
    logger.info("Running scheduled scrape...")
    try:
        result = scrape_moltbook()
        logger.info(f"Scheduled scrape completed: {result}")
        send_telegram(f"🔄 AgentPulse scrape: {result.get('total_new', 0)} new posts")
    except Exception as e:
        logger.error(f"Scheduled scrape failed: {e}")

def scheduled_analyze():
    """Scheduled analysis task."""
    logger.info("Running scheduled analysis...")
    try:
        extract_result = extract_problems()
        opp_result = generate_opportunities()
        logger.info(f"Scheduled analysis completed: problems={extract_result}, opportunities={opp_result}")
        
        problems_found = extract_result.get('problems_found', 0)
        opps_generated = opp_result.get('opportunities_generated', 0)
        if problems_found > 0 or opps_generated > 0:
            send_telegram(f"🎯 AgentPulse analysis: {problems_found} problems, {opps_generated} opportunities")
    except Exception as e:
        logger.error(f"Scheduled analysis failed: {e}")

def scheduled_digest():
    """Send daily digest via Telegram."""
    logger.info("Running scheduled digest...")
    try:
        opps = get_current_opportunities(limit=5, min_score=0.3)
        if opps.get('opportunities'):
            digest = "📊 *AgentPulse Daily Digest*\n\n"
            for i, opp in enumerate(opps['opportunities'][:5], 1):
                title = opp.get('title', 'Untitled')
                score = opp.get('confidence_score', 0)
                digest += f"{i}. *{title}* ({int(score*100)}%)\n"
            send_telegram(digest)
        else:
            logger.info("No opportunities for digest")
    except Exception as e:
        logger.error(f"Scheduled digest failed: {e}")

def scheduled_cleanup():
    """Clean up old files and data."""
    logger.info("Running scheduled cleanup...")
    try:
        # Clean old response files (older than 7 days)
        cutoff = datetime.now() - timedelta(days=7)
        for f in RESPONSES_DIR.glob('*.json'):
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
                logger.info(f"Cleaned up old response: {f.name}")
        
        # Clean old cache files
        for f in CACHE_DIR.glob('*.jsonl'):
            if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
                logger.info(f"Cleaned up old cache: {f.name}")
    except Exception as e:
        logger.error(f"Scheduled cleanup failed: {e}")

def setup_scheduler():
    """Set up scheduled tasks."""
    # Get intervals from environment or use defaults
    scrape_interval = int(os.getenv('AGENTPULSE_SCRAPE_INTERVAL_HOURS', '6'))
    analysis_interval = int(os.getenv('AGENTPULSE_ANALYSIS_INTERVAL_HOURS', '12'))
    
    # Schedule tasks
    schedule.every(scrape_interval).hours.do(scheduled_scrape)
    schedule.every(analysis_interval).hours.do(scheduled_analyze)
    schedule.every().day.at("09:00").do(scheduled_digest)
    schedule.every().day.at("03:00").do(scheduled_cleanup)
    
    logger.info(f"Scheduler configured: scrape every {scrape_interval}h, analyze every {analysis_interval}h")
    logger.info("Daily digest at 09:00 UTC, cleanup at 03:00 UTC")

def run_scheduler():
    """Run the scheduler in a background thread."""
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='AgentPulse Processor')
    parser.add_argument('--task', choices=['scrape', 'analyze', 'opportunities', 'digest', 'cleanup', 'queue', 'watch'],
                        default='watch', help='Task to run')
    parser.add_argument('--once', action='store_true', help='Run once instead of watching')
    parser.add_argument('--no-schedule', action='store_true', help='Disable scheduled tasks in watch mode')
    args = parser.parse_args()
    
    init_clients()
    
    if args.task == 'scrape':
        result = scrape_moltbook()
        print(json.dumps(result, indent=2))
    
    elif args.task == 'analyze':
        extract_result = extract_problems()
        opp_result = generate_opportunities()
        print(json.dumps({'extract': extract_result, 'opportunities': opp_result}, indent=2))
    
    elif args.task == 'opportunities':
        result = get_current_opportunities()
        print(json.dumps(result, indent=2))
    
    elif args.task == 'digest':
        scheduled_digest()
    
    elif args.task == 'cleanup':
        scheduled_cleanup()
    
    elif args.task == 'queue':
        process_queue()
    
    elif args.task == 'watch':
        logger.info("Starting AgentPulse processor...")
        
        # Set up and start scheduler in background thread (unless disabled)
        if not args.no_schedule:
            setup_scheduler()
            scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
            scheduler_thread.start()
            logger.info("Scheduler thread started")
            
            # Run initial scrape on startup
            logger.info("Running initial scrape on startup...")
            try:
                scheduled_scrape()
            except Exception as e:
                logger.error(f"Initial scrape failed: {e}")
        
        # Main queue watching loop
        logger.info("Starting queue watcher...")
        while True:
            process_queue()
            time.sleep(5)
    
    else:
        print(f"Unknown task: {args.task}")
        sys.exit(1)

if __name__ == '__main__':
    main()
