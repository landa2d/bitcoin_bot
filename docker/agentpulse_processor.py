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
import math
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
# Problem Clustering
# ============================================================================

CLUSTERING_PROMPT = """You are an analyst grouping business problems into thematic clusters.

Given these extracted problems, group them into 3-10 thematic clusters.
Problems that describe the same underlying issue (even with different wording) should be in the same cluster.

Problems:
{problems}

For each cluster, provide:
1. theme: Short name for the cluster (e.g. "API Reliability", "Payment Infrastructure")
2. description: 2-3 sentence summary of the common problem
3. problem_ids: Array of problem IDs that belong to this cluster
4. combined_severity: low, medium, or high (based on the worst severity in the group)
5. willingness_to_pay: none, implied, or explicit (based on the strongest signal in the group)
6. solution_gap: none (no solutions exist), inadequate (solutions exist but are poor), or solved (good solutions exist)

Respond ONLY with valid JSON:
{{
  "clusters": [
    {{
      "theme": "...",
      "description": "...",
      "problem_ids": ["..."],
      "combined_severity": "...",
      "willingness_to_pay": "...",
      "solution_gap": "..."
    }}
  ]
}}

Group aggressively — prefer fewer clusters with more problems over many tiny clusters.
Only create a cluster if it contains problems that share a genuine common theme."""


def cluster_problems(min_problems: int = 3) -> dict:
    """Cluster unclustered problems into thematic groups with opportunity scores."""
    if not supabase or not openai_client:
        logger.error("Supabase or OpenAI not configured")
        return {'error': 'Not configured'}

    run_id = log_pipeline_start('cluster_problems')

    # Fetch unclustered problems
    problems = supabase.table('problems')\
        .select('*')\
        .is_('cluster_id', 'null')\
        .execute()

    if not problems.data or len(problems.data) < min_problems:
        logger.info(f"Not enough unclustered problems ({len(problems.data) if problems.data else 0} < {min_problems})")
        return {'problems_processed': 0, 'clusters_created': 0}

    logger.info(f"Clustering {len(problems.data)} unclustered problems")
    logger.info(f"Using model: {OPENAI_MODEL} for clustering")

    # Format problems for prompt
    problems_text = json.dumps([
        {
            'id': p['id'],
            'description': p['description'],
            'category': p['category'],
            'frequency': p.get('frequency_count', 1),
            'severity': p.get('metadata', {}).get('severity', 'low'),
            'willingness_to_pay': p.get('metadata', {}).get('willingness_to_pay', 'none')
        }
        for p in problems.data
    ], indent=2)

    # Call OpenAI for clustering
    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You group business problems into thematic clusters. Respond only with valid JSON."},
                {"role": "user", "content": CLUSTERING_PROMPT.format(problems=problems_text)}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        time.sleep(2)  # Rate limiting

        result_text = response.choices[0].message.content
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]
        result_text = result_text.strip()

        clusters_data = json.loads(result_text)

    except Exception as e:
        logger.error(f"OpenAI clustering failed: {e}")
        log_pipeline_end(run_id, 'failed', {'error': str(e)})
        return {'error': str(e)}

    # Build a lookup for problems by ID
    problems_by_id = {p['id']: p for p in problems.data}

    # Find max frequency for normalization
    max_frequency = max((p.get('frequency_count', 1) for p in problems.data), default=1)
    if max_frequency < 1:
        max_frequency = 1

    clusters_created = 0
    total_problems_clustered = 0

    for cluster in clusters_data.get('clusters', []):
        try:
            problem_ids = cluster.get('problem_ids', [])
            if not problem_ids:
                continue

            # Compute aggregate stats from the cluster's problems
            cluster_problems_data = [problems_by_id[pid] for pid in problem_ids if pid in problems_by_id]
            if not cluster_problems_data:
                continue

            total_mentions = sum(p.get('frequency_count', 1) for p in cluster_problems_data)

            # Compute average recency in days
            now = datetime.utcnow()
            recency_days = []
            for p in cluster_problems_data:
                created = p.get('created_at')
                if created:
                    try:
                        created_dt = datetime.fromisoformat(created.replace('Z', '+00:00').replace('+00:00', ''))
                        recency_days.append((now - created_dt).days)
                    except:
                        recency_days.append(30)
                else:
                    recency_days.append(30)
            avg_recency = sum(recency_days) / len(recency_days) if recency_days else 30

            # Compute opportunity_score
            # frequency_weight: log(total_mentions) / log(max_frequency), capped at 1.0
            if max_frequency > 1 and total_mentions > 0:
                freq_weight = min(math.log(max(total_mentions, 1)) / math.log(max(max_frequency, 2)), 1.0)
            else:
                freq_weight = min(total_mentions / max(max_frequency, 1), 1.0)

            # recency_weight: 1.0 if < 7 days, 0.7 if < 30 days, 0.3 otherwise
            if avg_recency < 7:
                recency_weight = 1.0
            elif avg_recency < 30:
                recency_weight = 0.7
            else:
                recency_weight = 0.3

            # willingness_to_pay weight
            wtp = cluster.get('willingness_to_pay', 'none')
            wtp_weight = {'explicit': 1.0, 'implied': 0.5, 'none': 0.0}.get(wtp, 0.0)

            # solution_gap weight
            gap = cluster.get('solution_gap', 'none')
            gap_weight = {'none': 1.0, 'inadequate': 0.5, 'solved': 0.0}.get(gap, 0.5)

            opportunity_score = (freq_weight * 0.3) + (recency_weight * 0.2) + (wtp_weight * 0.3) + (gap_weight * 0.2)

            # Insert cluster into problem_clusters table
            cluster_record = {
                'theme': cluster['theme'],
                'description': cluster['description'],
                'problem_ids': problem_ids,
                'total_mentions': total_mentions,
                'avg_recency_days': round(avg_recency, 1),
                'opportunity_score': round(opportunity_score, 3),
                'market_validation': {
                    'combined_severity': cluster.get('combined_severity', 'low'),
                    'willingness_to_pay': wtp,
                    'solution_gap': gap
                }
            }
            insert_result = supabase.table('problem_clusters').insert(cluster_record).execute()
            cluster_id = insert_result.data[0]['id'] if insert_result.data else None

            if cluster_id:
                # Update each problem's cluster_id
                valid_ids = [pid for pid in problem_ids if pid in problems_by_id]
                if valid_ids:
                    supabase.table('problems')\
                        .update({'cluster_id': cluster_id})\
                        .in_('id', valid_ids)\
                        .execute()
                    total_problems_clustered += len(valid_ids)

            clusters_created += 1

        except Exception as e:
            logger.error(f"Error creating cluster '{cluster.get('theme', '?')}': {e}")

    result = {
        'problems_processed': len(problems.data),
        'clusters_created': clusters_created,
        'problems_clustered': total_problems_clustered
    }

    log_pipeline_end(run_id, 'completed', result)
    logger.info(f"Clustering complete: {clusters_created} clusters from {len(problems.data)} problems")
    return result


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

def generate_opportunities(min_score: float = 0.3, limit: int = 5) -> dict:
    """Generate opportunities from top problem clusters."""
    if not supabase or not openai_client:
        return {'error': 'Not configured'}

    run_id = log_pipeline_start('generate_opportunities')

    # Get top clusters ordered by opportunity_score
    clusters = supabase.table('problem_clusters')\
        .select('*')\
        .gte('opportunity_score', min_score)\
        .order('opportunity_score', desc=True)\
        .limit(limit * 2)\
        .execute()

    if not clusters.data:
        logger.info("No clusters found above min_score threshold")
        return {'opportunities_generated': 0}

    # Filter out clusters that already have opportunities
    existing_opps = supabase.table('opportunities')\
        .select('cluster_id')\
        .not_.is_('cluster_id', 'null')\
        .execute()
    existing_cluster_ids = {o['cluster_id'] for o in (existing_opps.data or [])}

    new_clusters = [c for c in clusters.data if c['id'] not in existing_cluster_ids]

    if not new_clusters:
        logger.info("All top clusters already have opportunities")
        return {'opportunities_generated': 0}

    opportunities_created = 0
    logger.info(f"Using model: {OPENAI_MODEL} for opportunity generation from {len(new_clusters)} clusters")

    for cluster in new_clusters[:limit]:
        try:
            problem_data = json.dumps({
                'theme': cluster['theme'],
                'description': cluster['description'],
                'total_mentions': cluster.get('total_mentions', 0),
                'avg_recency_days': cluster.get('avg_recency_days', 0),
                'opportunity_score': cluster.get('opportunity_score', 0),
                'market_validation': cluster.get('market_validation', {})
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
            time.sleep(2)  # Rate limiting

            result_text = response.choices[0].message.content
            if result_text.startswith('```'):
                result_text = result_text.split('```')[1]
                if result_text.startswith('json'):
                    result_text = result_text[4:]

            opp_data = json.loads(result_text.strip())
            store_opportunity(opp_data, cluster_id=cluster['id'])
            opportunities_created += 1

            # Also save to local file
            save_opportunity_brief(opp_data)

        except Exception as e:
            logger.error(f"Error generating opportunity for cluster '{cluster.get('theme', '?')}': {e}")

    result = {'opportunities_generated': opportunities_created}
    log_pipeline_end(run_id, 'completed', result)
    return result


def store_opportunity(opp: dict, cluster_id: str = None):
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
    if cluster_id:
        record['cluster_id'] = cluster_id

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
# Pipeline 2: Investment Scanner (Tool Mentions & Stats)
# ============================================================================

TOOL_EXTRACTION_PROMPT = """You are an analyst identifying tool and product mentions in social media posts by AI agents.

Analyze these posts and extract every mention of a specific tool, product, service, platform, library, or framework.

For each mention, provide:
1. tool_name: Normalized name (e.g., "LangChain" not "langchain" or "lang chain")
2. tool_name_raw: Exactly as written in the post
3. context: The sentence or phrase where it's mentioned
4. sentiment_score: -1.0 (very negative) to 1.0 (very positive), 0.0 for neutral
5. sentiment_label: "positive", "negative", or "neutral"
6. is_recommendation: true if the author is recommending this tool to others
7. is_complaint: true if the author is complaining about this tool
8. alternative_mentioned: If they mention switching from/to another tool, note it (e.g., "switched from LangChain to LlamaIndex"), or null
9. source_post_id: The post ID where this was found

Posts to analyze:
{posts}

Respond ONLY with valid JSON:
{{
  "tool_mentions": [
    {{
      "tool_name": "...",
      "tool_name_raw": "...",
      "context": "...",
      "sentiment_score": 0.0,
      "sentiment_label": "...",
      "is_recommendation": false,
      "is_complaint": false,
      "alternative_mentioned": null,
      "source_post_id": "..."
    }}
  ]
}}

Rules:
- Include programming languages, frameworks, APIs, platforms, SaaS tools, protocols
- Don't include generic terms like "API" or "database" unless they refer to a specific product
- Normalize names consistently (e.g., "GPT-4" not "gpt4" or "GPT 4")
- One mention per tool per post (even if mentioned multiple times)"""


def extract_tool_mentions(hours_back: int = 48) -> dict:
    """Extract tool/product mentions from recent posts (Pipeline 2)."""
    if not supabase or not openai_client:
        logger.error("Supabase or OpenAI not configured")
        return {'error': 'Not configured'}

    run_id = log_pipeline_start('extract_tools')

    # Fetch posts from the last N hours (regardless of processed status —
    # tool extraction is independent from problem extraction)
    cutoff = datetime.utcnow() - timedelta(hours=hours_back)
    posts = supabase.table('moltbook_posts')\
        .select('*')\
        .gte('scraped_at', cutoff.isoformat())\
        .limit(100)\
        .execute()

    if not posts.data:
        logger.info("No posts found for tool extraction")
        return {'posts_scanned': 0, 'mentions_found': 0}

    logger.info(f"Scanning {len(posts.data)} posts for tool mentions")
    logger.info(f"Using model: {OPENAI_MODEL} for tool extraction")

    # Format posts for prompt
    posts_text = "\n\n".join([
        f"[Post ID: {p['moltbook_id']}]\n{p.get('title', '')}\n{p['content']}"
        for p in posts.data
    ])

    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You extract tool and product mentions. Respond only with valid JSON."},
                {"role": "user", "content": TOOL_EXTRACTION_PROMPT.format(posts=posts_text)}
            ],
            temperature=0.2,
            max_tokens=4000
        )
        time.sleep(2)  # Rate limiting

        result_text = response.choices[0].message.content
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]
        result_text = result_text.strip()

        mentions_data = json.loads(result_text)

    except Exception as e:
        logger.error(f"Tool extraction failed: {e}")
        log_pipeline_end(run_id, 'failed', {'error': str(e)})
        return {'error': str(e)}

    # Store mentions
    mentions_stored = 0
    for mention in mentions_data.get('tool_mentions', []):
        try:
            # Look up the internal post UUID from moltbook_id
            post_lookup = supabase.table('moltbook_posts')\
                .select('id')\
                .eq('moltbook_id', mention.get('source_post_id', ''))\
                .limit(1)\
                .execute()

            post_uuid = post_lookup.data[0]['id'] if post_lookup.data else None

            record = {
                'tool_name': mention['tool_name'],
                'tool_name_raw': mention.get('tool_name_raw'),
                'post_id': post_uuid,
                'context': mention.get('context'),
                'sentiment_score': mention.get('sentiment_score', 0.0),
                'sentiment_label': mention.get('sentiment_label', 'neutral'),
                'is_recommendation': mention.get('is_recommendation', False),
                'is_complaint': mention.get('is_complaint', False),
                'alternative_mentioned': mention.get('alternative_mentioned'),
                'mentioned_at': datetime.utcnow().isoformat(),
                'metadata': {}
            }

            supabase.table('tool_mentions').insert(record).execute()
            mentions_stored += 1

        except Exception as e:
            logger.error(f"Error storing tool mention '{mention.get('tool_name', '?')}': {e}")

    result = {
        'posts_scanned': len(posts.data),
        'mentions_found': mentions_stored
    }
    log_pipeline_end(run_id, 'completed', result)
    logger.info(f"Tool extraction complete: {mentions_stored} mentions from {len(posts.data)} posts")
    return result


def update_tool_stats() -> dict:
    """Recompute aggregated tool statistics from all tool_mentions."""
    if not supabase:
        logger.error("Supabase not configured")
        return {'error': 'Not configured'}

    run_id = log_pipeline_start('update_tool_stats')

    # Get all unique tool names
    tools = supabase.table('tool_mentions')\
        .select('tool_name')\
        .execute()

    unique_tools = list(set(t['tool_name'] for t in (tools.data or [])))

    if not unique_tools:
        logger.info("No tool mentions found for stats computation")
        return {'tools_updated': 0}

    logger.info(f"Updating stats for {len(unique_tools)} tools")

    stats_updated = 0
    now = datetime.utcnow()
    week_ago = (now - timedelta(days=7)).isoformat()
    month_ago = (now - timedelta(days=30)).isoformat()

    for tool_name in unique_tools:
        try:
            # Get all mentions for this tool
            mentions = supabase.table('tool_mentions')\
                .select('*')\
                .eq('tool_name', tool_name)\
                .execute()

            all_mentions = mentions.data or []
            if not all_mentions:
                continue

            recent_7d = [m for m in all_mentions if m.get('mentioned_at', '') >= week_ago]
            recent_30d = [m for m in all_mentions if m.get('mentioned_at', '') >= month_ago]

            avg_sentiment = sum(m.get('sentiment_score', 0) for m in all_mentions) / len(all_mentions)
            recommendations = sum(1 for m in all_mentions if m.get('is_recommendation'))
            complaints = sum(1 for m in all_mentions if m.get('is_complaint'))

            # Collect alternatives
            alternatives = [m['alternative_mentioned'] for m in all_mentions
                            if m.get('alternative_mentioned')]

            # Build stat record
            stat_record = {
                'tool_name': tool_name,
                'total_mentions': len(all_mentions),
                'mentions_7d': len(recent_7d),
                'mentions_30d': len(recent_30d),
                'avg_sentiment': round(avg_sentiment, 3),
                'recommendation_count': recommendations,
                'complaint_count': complaints,
                'top_alternatives': list(set(alternatives))[:5],
                'first_seen': min(m.get('mentioned_at', '') for m in all_mentions),
                'last_seen': max(m.get('mentioned_at', '') for m in all_mentions),
                'updated_at': now.isoformat()
            }

            # Upsert: check if exists, then update or insert
            existing = supabase.table('tool_stats')\
                .select('id')\
                .eq('tool_name', tool_name)\
                .execute()

            if existing.data:
                supabase.table('tool_stats')\
                    .update(stat_record)\
                    .eq('tool_name', tool_name)\
                    .execute()
            else:
                supabase.table('tool_stats').insert(stat_record).execute()

            stats_updated += 1

        except Exception as e:
            logger.error(f"Error updating stats for '{tool_name}': {e}")

    result = {'tools_updated': stats_updated}
    log_pipeline_end(run_id, 'completed', result)
    logger.info(f"Tool stats update complete: {stats_updated} tools updated")
    return result


# ============================================================================
# Newsletter (Data Prep + Publish — writing delegated to Newsletter agent)
# ============================================================================

def prepare_newsletter_data() -> dict:
    """Gather data for the Newsletter agent and create a write_newsletter task."""
    if not supabase:
        logger.error("Supabase not configured")
        return {'error': 'Not configured'}

    run_id = log_pipeline_start('prepare_newsletter')
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

    try:
        # Top 5 opportunities by confidence_score
        opps = supabase.table('opportunities')\
            .select('*')\
            .order('confidence_score', desc=True)\
            .limit(5)\
            .execute()
        opportunities_data = opps.data or []

        # Top 10 tools by mentions_7d
        tools = supabase.table('tool_stats')\
            .select('*')\
            .order('mentions_7d', desc=True)\
            .limit(10)\
            .execute()
        tools_data = tools.data or []

        # Tool warnings: negative sentiment + enough mentions
        warnings = supabase.table('tool_stats')\
            .select('*')\
            .lt('avg_sentiment', -0.3)\
            .gte('total_mentions', 3)\
            .execute()
        warnings_data = warnings.data or []

        # Recent problem clusters (last 7 days)
        clusters = supabase.table('problem_clusters')\
            .select('*')\
            .gte('created_at', week_ago)\
            .order('opportunity_score', desc=True)\
            .limit(10)\
            .execute()
        clusters_data = clusters.data or []

        # Stats
        posts_count_result = supabase.table('moltbook_posts')\
            .select('id', count='exact')\
            .gte('scraped_at', week_ago)\
            .execute()
        posts_count = posts_count_result.count if posts_count_result.count else 0

        # problems table has no created_at/first_seen in schema — use total count
        problems_count_result = supabase.table('problems')\
            .select('id', count='exact')\
            .execute()
        problems_count = problems_count_result.count if problems_count_result.count else 0

        tools_count_result = supabase.table('tool_stats')\
            .select('id', count='exact')\
            .execute()
        tools_count = tools_count_result.count if tools_count_result.count else 0

        new_opps_result = supabase.table('opportunities')\
            .select('id', count='exact')\
            .gte('created_at', week_ago)\
            .execute()
        new_opps_count = new_opps_result.count if new_opps_result.count else 0

        # Get next edition number
        try:
            edition_result = supabase.rpc('next_newsletter_edition').execute()
            edition_number = edition_result.data if edition_result.data else 1
        except Exception:
            # Fallback: count existing newsletters + 1
            existing = supabase.table('newsletters')\
                .select('id', count='exact')\
                .execute()
            edition_number = (existing.count or 0) + 1

        # Build input_data for the Newsletter agent
        input_data = {
            'edition_number': edition_number,
            'opportunities': opportunities_data,
            'trending_tools': tools_data,
            'tool_warnings': warnings_data,
            'clusters': clusters_data,
            'stats': {
                'posts_count': posts_count,
                'problems_count': problems_count,
                'tools_count': tools_count,
                'new_opps_count': new_opps_count
            }
        }

        # Create agent_task for the Newsletter agent
        # Use json.dumps with default=str to handle any datetime objects
        serialized_input = json.loads(json.dumps(input_data, default=str))

        new_task = supabase.table('agent_tasks').insert({
            'task_type': 'write_newsletter',
            'assigned_to': 'newsletter',
            'created_by': 'processor',
            'priority': 3,
            'input_data': serialized_input
        }).execute()

        task_id = new_task.data[0]['id'] if new_task.data else None

        result = {
            'edition_number': edition_number,
            'task_id': task_id,
            'status': 'delegated_to_newsletter',
            'data_summary': {
                'opportunities': len(opportunities_data),
                'tools': len(tools_data),
                'warnings': len(warnings_data),
                'clusters': len(clusters_data)
            }
        }

        log_pipeline_end(run_id, 'completed', result)
        logger.info(f"Newsletter data prepared: edition #{edition_number}, task {task_id}")
        return result

    except Exception as e:
        logger.error(f"Newsletter data preparation failed: {e}")
        log_pipeline_end(run_id, 'failed', {'error': str(e)})
        return {'error': str(e)}


def publish_newsletter() -> dict:
    """Publish the latest draft newsletter via Telegram."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    try:
        # Get latest draft newsletter
        draft = supabase.table('newsletters')\
            .select('*')\
            .eq('status', 'draft')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()

        if not draft.data:
            return {'error': 'No draft newsletter found'}

        newsletter = draft.data[0]
        telegram_content = newsletter.get('content_telegram') or newsletter.get('content_markdown', '')[:4000]

        if telegram_content:
            send_telegram(telegram_content)

        # Update status to published
        supabase.table('newsletters').update({
            'status': 'published',
            'published_at': datetime.utcnow().isoformat()
        }).eq('id', newsletter['id']).execute()

        logger.info(f"Newsletter #{newsletter.get('edition_number', '?')} published")
        return {
            'published': newsletter['id'],
            'edition': newsletter.get('edition_number')
        }

    except Exception as e:
        logger.error(f"Newsletter publish failed: {e}")
        return {'error': str(e)}


def get_latest_newsletter() -> dict:
    """Get the latest newsletter (any status)."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    try:
        result = supabase.table('newsletters')\
            .select('*')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()

        if result.data:
            return result.data[0]
        return {'error': 'No newsletters found'}

    except Exception as e:
        logger.error(f"Get latest newsletter failed: {e}")
        return {'error': str(e)}


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
        # Skip files belonging to other agents (e.g. newsletter_*.json)
        if task_file.name.startswith('newsletter_'):
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
            min_score=params.get('min_score', 0.3),
            limit=params.get('limit', 5)
        )
    
    elif task_type == 'cluster_problems':
        return cluster_problems(min_problems=params.get('min_problems', 3))
    
    elif task_type == 'run_pipeline':
        # Full pipeline run: scrape → extract → cluster → generate
        scrape_result = scrape_moltbook()
        extract_result = extract_problems()
        cluster_result = cluster_problems()
        opp_result = generate_opportunities(min_score=0.3)
        return {
            'scrape': scrape_result,
            'extract': extract_result,
            'cluster': cluster_result,
            'opportunities': opp_result
        }
    
    elif task_type == 'extract_tools':
        return extract_tool_mentions(hours_back=params.get('hours_back', 48))
    
    elif task_type == 'update_tool_stats':
        return update_tool_stats()
    
    elif task_type == 'run_investment_scan':
        # Full investment scanner: extract tool mentions (7 days) then recompute stats
        extract_result = extract_tool_mentions(hours_back=168)
        stats_result = update_tool_stats()
        return {
            'extract_tools': extract_result,
            'tool_stats': stats_result
        }
    
    elif task_type == 'prepare_newsletter':
        return prepare_newsletter_data()
    
    elif task_type == 'publish_newsletter':
        return publish_newsletter()
    
    elif task_type == 'get_latest_newsletter':
        return get_latest_newsletter()
    
    elif task_type == 'get_opportunities':
        return get_current_opportunities(
            limit=params.get('limit', 5),
            min_score=params.get('min_score', 0.0)
        )
    
    elif task_type == 'status':
        return get_status()
    
    elif task_type == 'create_agent_task':
        # Gato (or another agent) asks processor to create a task for delegation
        if not supabase:
            return {'error': 'Supabase not configured'}
        new_task = supabase.table('agent_tasks').insert({
            'task_type': params['task_type'],
            'assigned_to': params.get('assigned_to', 'analyst'),
            'created_by': params.get('created_by', 'gato'),
            'input_data': params.get('input_data', {}),
            'priority': params.get('priority', 5)
        }).execute()
        return {'task_created': new_task.data[0]['id'] if new_task.data else None}
    
    elif task_type == 'check_task':
        # Check the status of an existing agent_task
        if not supabase:
            return {'error': 'Supabase not configured'}
        task_record = supabase.table('agent_tasks')\
            .select('*')\
            .eq('id', params['task_id'])\
            .single()\
            .execute()
        return task_record.data
    
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
# Database Task Processing (Multi-Agent)
# ============================================================================

def process_db_tasks(agent_name: str = 'analyst'):
    """Process pending tasks from the agent_tasks Supabase table."""
    if not supabase:
        return
    
    try:
        tasks = supabase.table('agent_tasks')\
            .select('*')\
            .eq('status', 'pending')\
            .eq('assigned_to', agent_name)\
            .order('priority', desc=False)\
            .order('created_at', desc=False)\
            .limit(5)\
            .execute()
    except Exception as e:
        logger.error(f"[{agent_name}] Failed to fetch tasks: {e}")
        return
    
    for task in tasks.data or []:
        task_id = task['id']
        task_type = task.get('task_type', 'unknown')
        logger.info(f"[{agent_name}] Processing task {task_id}: {task_type}")
        
        try:
            # Mark in progress
            supabase.table('agent_tasks').update({
                'status': 'in_progress',
                'started_at': datetime.utcnow().isoformat()
            }).eq('id', task_id).execute()
            
            # Execute using existing task router
            result = execute_task({
                'task': task_type,
                'params': task.get('input_data', {})
            })
            
            # Write file-based response too (backward compat for Gato)
            response_file = RESPONSES_DIR / f"task_{task_id}.result.json"
            response_file.write_text(json.dumps({
                'success': True,
                'task': task_type,
                'result': result,
                'completed_at': datetime.utcnow().isoformat()
            }, indent=2))
            
            # Mark completed in DB
            supabase.table('agent_tasks').update({
                'status': 'completed',
                'completed_at': datetime.utcnow().isoformat(),
                'output_data': result
            }).eq('id', task_id).execute()
            
            logger.info(f"[{agent_name}] Task {task_id} completed")
        
        except Exception as e:
            logger.error(f"[{agent_name}] Task {task_id} failed: {e}")
            try:
                supabase.table('agent_tasks').update({
                    'status': 'failed',
                    'completed_at': datetime.utcnow().isoformat(),
                    'error_message': str(e)
                }).eq('id', task_id).execute()
            except Exception as update_err:
                logger.error(f"[{agent_name}] Failed to update task {task_id} status: {update_err}")

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

def scheduled_cluster():
    """Scheduled clustering task."""
    logger.info("Running scheduled clustering...")
    try:
        result = cluster_problems()
        logger.info(f"Scheduled clustering completed: {result}")
        clusters_created = result.get('clusters_created', 0)
        if clusters_created > 0:
            send_telegram(f"🔬 AgentPulse clustering: {clusters_created} new clusters identified")
    except Exception as e:
        logger.error(f"Scheduled clustering failed: {e}")

def scheduled_tool_scan():
    """Scheduled tool mention extraction."""
    logger.info("Running scheduled tool scan...")
    try:
        result = extract_tool_mentions(hours_back=48)
        logger.info(f"Scheduled tool scan completed: {result}")
        mentions = result.get('mentions_found', 0)
        if mentions > 0:
            send_telegram(f"🔧 AgentPulse tool scan: {mentions} tool mentions extracted")
    except Exception as e:
        logger.error(f"Scheduled tool scan failed: {e}")

def scheduled_update_stats():
    """Scheduled tool stats recomputation."""
    logger.info("Running scheduled tool stats update...")
    try:
        result = update_tool_stats()
        logger.info(f"Scheduled tool stats completed: {result}")
        updated = result.get('tools_updated', 0)
        if updated > 0:
            send_telegram(f"📈 AgentPulse tool stats: {updated} tools updated")
    except Exception as e:
        logger.error(f"Scheduled tool stats update failed: {e}")

def scheduled_prepare_newsletter():
    """Scheduled: gather data and delegate newsletter writing to Newsletter agent."""
    logger.info("Running scheduled newsletter preparation...")
    try:
        result = prepare_newsletter_data()
        logger.info(f"Scheduled newsletter prep completed: {result}")
        edition = result.get('edition_number', '?')
        send_telegram(f"📝 Newsletter #{edition} data prepared and sent to Newsletter agent for writing.")
    except Exception as e:
        logger.error(f"Scheduled newsletter prep failed: {e}")

def scheduled_notify_newsletter():
    """Notify owner that a new newsletter may be ready for review."""
    send_telegram("📰 New AgentPulse Brief is ready for review. Send /newsletter to see it.")

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
    schedule.every(12).hours.do(scheduled_cluster)
    schedule.every(12).hours.do(scheduled_tool_scan)
    schedule.every().day.at("06:00").do(scheduled_update_stats)
    schedule.every().monday.at("07:00").do(scheduled_prepare_newsletter)
    schedule.every().monday.at("08:00").do(scheduled_notify_newsletter)
    schedule.every().day.at("09:00").do(scheduled_digest)
    schedule.every().day.at("03:00").do(scheduled_cleanup)
    
    logger.info(f"Scheduler configured: scrape every {scrape_interval}h, analyze every {analysis_interval}h, cluster every 12h, tool scan every 12h")
    logger.info("Daily: tool stats at 06:00, digest at 09:00, cleanup at 03:00 UTC")
    logger.info("Weekly: newsletter prep Mon 07:00, newsletter notify Mon 08:00 UTC")

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
    parser.add_argument('--task', choices=['scrape', 'analyze', 'cluster', 'opportunities', 'extract_tools', 'update_tool_stats', 'run_investment_scan', 'prepare_newsletter', 'publish_newsletter', 'digest', 'cleanup', 'queue', 'watch', 'create_agent_task', 'check_task'],
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
        cluster_result = cluster_problems()
        opp_result = generate_opportunities()
        print(json.dumps({'extract': extract_result, 'cluster': cluster_result, 'opportunities': opp_result}, indent=2))
    
    elif args.task == 'cluster':
        result = cluster_problems()
        print(json.dumps(result, indent=2))
    
    elif args.task == 'opportunities':
        result = get_current_opportunities()
        print(json.dumps(result, indent=2))
    
    elif args.task == 'extract_tools':
        result = extract_tool_mentions()
        print(json.dumps(result, indent=2))
    
    elif args.task == 'update_tool_stats':
        result = update_tool_stats()
        print(json.dumps(result, indent=2))
    
    elif args.task == 'run_investment_scan':
        extract_result = extract_tool_mentions(hours_back=168)
        stats_result = update_tool_stats()
        print(json.dumps({'extract_tools': extract_result, 'tool_stats': stats_result}, indent=2))
    
    elif args.task == 'prepare_newsletter':
        result = prepare_newsletter_data()
        print(json.dumps(result, default=str, indent=2))
    
    elif args.task == 'publish_newsletter':
        result = publish_newsletter()
        print(json.dumps(result, default=str, indent=2))
    
    elif args.task == 'digest':
        scheduled_digest()
    
    elif args.task == 'cleanup':
        scheduled_cleanup()
    
    elif args.task == 'queue':
        process_queue()
    
    elif args.task == 'watch':
        logger.info("Starting AgentPulse processor...")
        
        # Set up scheduler (unless disabled)
        if not args.no_schedule:
            setup_scheduler()
            
            # Run initial scrape on startup
            logger.info("Running initial scrape on startup...")
            try:
                scheduled_scrape()
            except Exception as e:
                logger.error(f"Initial scrape failed: {e}")
        
        # Main loop: file queue + DB tasks + scheduled tasks
        logger.info("Starting queue watcher (multi-agent mode)...")
        while True:
            process_queue()                   # legacy file-based queue
            process_db_tasks('analyst')       # analyst tasks from agent_tasks table
            process_db_tasks('processor')     # processor-specific tasks
            # NOTE: newsletter tasks are handled by the newsletter container's poller,
            # NOT by the processor. Don't add process_db_tasks('newsletter') here.
            schedule.run_pending()            # scheduled scrape/analyze/digest/cleanup
            time.sleep(5)
    
    else:
        print(f"Unknown task: {args.task}")
        sys.exit(1)

if __name__ == '__main__':
    main()
