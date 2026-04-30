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
import re
import time
import math
import logging
import tweepy
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
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
import resend
import markdown as md_lib

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
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('AGENTPULSE_OPENAI_MODEL', 'gpt-4o')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
LLM_PROXY_URL = os.getenv("LLM_PROXY_URL", "http://llm-proxy:8200")
_agent_api_key: str | None = os.getenv("AGENT_API_KEY") or None

# Hacker News
HN_API_BASE = 'https://hacker-news.firebaseio.com/v0'
HN_KEYWORDS = [
    # AI / Agent keywords
    'agent', 'ai agent', 'llm', 'gpt', 'claude', 'anthropic', 'openai',
    'autonomous', 'multi-agent', 'agentic', 'tool use', 'function calling',
    'rag', 'retrieval', 'embedding', 'vector', 'langchain', 'langgraph',
    'autogen', 'crewai', 'openclaw', 'mcp', 'model context protocol',
    'ai startup', 'ai tool', 'ai framework', 'ai infrastructure',
    'chatbot', 'copilot', 'assistant', 'automation',
    # Bitcoin / Crypto keywords
    'bitcoin', 'btc', 'lightning network', 'nostr', 'satoshi',
    'blockchain', 'crypto', 'defi', 'web3', 'smart contract',
    'layer 2', 'stablecoin', 'tokenization', 'ordinals',
]

# GitHub
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

# X (Twitter) API
X_BEARER_TOKEN = os.getenv('X_BEARER_TOKEN')
X_API_KEY = os.getenv('X_API_KEY')
X_API_SECRET = os.getenv('X_API_SECRET')
X_ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
X_ACCESS_TOKEN_SECRET = os.getenv('X_ACCESS_TOKEN_SECRET')
X_WEEKLY_BUDGET = float(os.getenv('X_WEEKLY_BUDGET', '5.0'))
X_SEARCH_COST_ESTIMATE = float(os.getenv('X_SEARCH_COST_ESTIMATE', '0.01'))  # $/request
X_SUBSCRIBE_URL = os.getenv('X_SUBSCRIBE_URL', 'https://aiagentspulse.com/#/subscribe')

# RSS Feeds
RSS_FEEDS = {
    'tldr_ai': {
        'url': 'https://tldr.tech/ai/rss',
        'tier': 2,
        'category': 'curated_newsletter'
    },
    'tldr_founders': {
        'url': 'https://tldr.tech/founders/rss',
        'tier': 2,
        'category': 'curated_newsletter'
    },
    'bens_bites': {
        'url': 'https://bensbites.beehiiv.com/feed',
        'tier': 2,
        'category': 'curated_newsletter'
    },
    'a16z': {
        'url': 'https://a16z.com/feed/',
        'tier': 1,
        'category': 'authority'
    },
    'hbr_tech': {
        'url': 'https://hbr.org/topic/technology/feed',
        'tier': 1,
        'category': 'authority'
    },
    'mit_tech_review': {
        'url': 'https://www.technologyreview.com/feed/',
        'tier': 1,
        'category': 'authority'
    },
    'andrew_ng': {
        'url': 'https://www.deeplearning.ai/the-batch/feed',
        'tier': 1,
        'category': 'thought_leader'
    },
    'simon_willison': {
        'url': 'https://simonwillison.net/atom/everything/',
        'tier': 1,
        'category': 'thought_leader'
    },
    'latent_space': {
        'url': 'https://www.latent.space/feed',
        'tier': 1,
        'category': 'thought_leader'
    },
    'swyx': {
        'url': 'https://www.swyx.io/rss.xml',
        'tier': 1,
        'category': 'thought_leader'
    },
    'langchain_blog': {
        'url': 'https://blog.langchain.dev/rss/',
        'tier': 1,
        'category': 'thought_leader'
    },
    'ethan_mollick': {
        'url': 'https://www.oneusefulthing.org/feed',
        'tier': 1,
        'category': 'thought_leader'
    },
    # Bitcoin / Crypto authority sources
    'bitcoin_magazine': {
        'url': 'https://bitcoinmagazine.com/feed',
        'tier': 1,
        'category': 'authority'
    },
    'coindesk': {
        'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
        'tier': 1,
        'category': 'authority'
    },
    'blockworks': {
        'url': 'https://blockworks.co/feed',
        'tier': 1,
        'category': 'authority'
    },
    'decrypt': {
        'url': 'https://decrypt.co/feed',
        'tier': 1,
        'category': 'authority'
    },
    'cointelegraph': {
        'url': 'https://cointelegraph.com/rss',
        'tier': 2,
        'category': 'curated_newsletter'
    },
    'unchained': {
        'url': 'https://unchainedcrypto.com/feed/',
        'tier': 1,
        'category': 'authority'
    },
    # AI / Tech journalism authority sources
    'techcrunch_ai': {
        'url': 'https://techcrunch.com/category/artificial-intelligence/feed/',
        'tier': 1,
        'category': 'authority'
    },
    'venturebeat_ai': {
        'url': 'https://venturebeat.com/category/ai/feed/',
        'tier': 1,
        'category': 'authority'
    },
    'the_verge_ai': {
        'url': 'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml',
        'tier': 1,
        'category': 'authority'
    },
    'wired_ai': {
        'url': 'https://www.wired.com/feed/tag/ai/latest/rss',
        'tier': 1,
        'category': 'authority'
    },
    'ars_technica': {
        'url': 'https://feeds.arstechnica.com/arstechnica/technology-lab',
        'tier': 1,
        'category': 'authority'
    },
    # AI research lab sources
    'openai_blog': {
        'url': 'https://openai.com/blog/rss.xml',
        'tier': 1,
        'category': 'authority'
    },
    'anthropic_news': {
        'url': 'https://www.anthropic.com/rss.xml',
        'tier': 1,
        'category': 'authority'
    },
    'deepmind_blog': {
        'url': 'https://deepmind.google/blog/rss.xml',
        'tier': 1,
        'category': 'authority'
    },
    # Financial / Macro research sources
    'citrini': {
        'url': 'https://www.citriniresearch.com/feed',
        'tier': 1,
        'category': 'macro_research'
    },
    'byrne_hobart': {
        'url': 'https://www.thediff.co/feed',
        'tier': 1,
        'category': 'financial_analysis'
    },
    'stratechery': {
        'url': 'https://stratechery.com/feed/',
        'tier': 1,
        'category': 'business_analysis'
    },
    'cb_insights': {
        'url': 'https://www.cbinsights.com/research/feed/',
        'tier': 2,
        'category': 'market_research'
    },
    # ── Agentic AI infrastructure ──────────────────────────────────
    'crewai_blog': {
        'url': 'https://blog.crewai.com/feed',
        'tier': 1,
        'category': 'authority'
    },
    'huggingface_blog': {
        'url': 'https://huggingface.co/blog/feed.xml',
        'tier': 1,
        'category': 'authority'
    },
    'replit_blog': {
        'url': 'https://blog.replit.com/feed.xml',
        'tier': 1,
        'category': 'authority'
    },
    'vercel_blog': {
        'url': 'https://vercel.com/atom',
        'tier': 1,
        'category': 'authority'
    },
    # ── Enterprise AI / VC strategy ────────────────────────────────
    'sequoia_blog': {
        'url': 'https://www.sequoiacap.com/feed/',
        'tier': 1,
        'category': 'authority'
    },
    # ── AI safety & governance ─────────────────────────────────────
    'alignment_forum': {
        'url': 'https://www.alignmentforum.org/feed.xml',
        'tier': 1,
        'category': 'authority'
    },
    # ── Crypto primary data / research ─────────────────────────────
    'messari': {
        'url': 'https://messari.io/rss',
        'tier': 1,
        'category': 'authority'
    },
    'chainalysis': {
        'url': 'https://blog.chainalysis.com/feed/',
        'tier': 1,
        'category': 'authority'
    },
    # ── arXiv academic feeds ───────────────────────────────────────
    'arxiv_cs_ai': {
        'url': 'https://rss.arxiv.org/rss/cs.AI',
        'tier': 1,
        'category': 'authority'
    },
    'arxiv_cs_ma': {
        'url': 'https://rss.arxiv.org/rss/cs.MA',
        'tier': 1,
        'category': 'authority'
    },
    'arxiv_cs_cr': {
        'url': 'https://rss.arxiv.org/rss/cs.CR',
        'tier': 1,
        'category': 'authority'
    },
    'arxiv_cs_cl': {
        'url': 'https://rss.arxiv.org/rss/cs.CL',
        'tier': 1,
        'category': 'authority'
    },
    # ── Regulatory feeds ───────────────────────────────────────────
    'sec_press': {
        'url': 'https://www.sec.gov/news/pressreleases.rss',
        'tier': 1,
        'category': 'authority'
    },
    'bis_speeches': {
        'url': 'https://www.bis.org/doclist/cbspeeches.rss',
        'tier': 1,
        'category': 'authority'
    },
    'fsb_publications': {
        'url': 'https://www.fsb.org/feed/',
        'tier': 1,
        'category': 'authority'
    },
}

RSS_RELEVANCE_KEYWORDS = [
    # AI / Agent keywords
    'agent', 'agentic', 'llm', 'ai tool', 'autonomous',
    'multi-agent', 'function call', 'ai startup',
    'foundation model', 'gpt', 'claude', 'anthropic',
    'openai', 'copilot', 'automation', 'ai infrastructure',
    'rag', 'vector', 'embedding', 'mcp', 'langchain',
    'orchestration', 'tool use', 'agent protocol',
    # AI safety / governance keywords
    'alignment', 'guardrails', 'red team', 'ai safety',
    'ai governance', 'ai policy', 'ai act',
    # Bitcoin / Crypto keywords
    'bitcoin', 'btc', 'lightning', 'nostr', 'blockchain',
    'crypto', 'defi', 'web3', 'smart contract', 'tokenization',
    'ordinals', 'layer 2', 'digital asset', 'on-chain',
    'tvl', 'protocol', 'stablecoin', 'l2',
    # Regulatory keywords
    'virtual currency', 'distributed ledger', 'fintech',
    'stablecoin regulation', 'money transmission', 'securities offering',
    # Financial / Macro keywords
    'saas pricing', 'seat based', 'arr', 'net revenue retention',
    'white collar', 'displacement', 'layoff', 'headcount reduction',
    'interchange', 'payment rail', 'agent commerce',
    'private credit', 'lbo', 'software default',
    'mortgage', 'delinquency', 'consumer spending',
    'ghost gdp', 'labor share', 'wage compression',
    'compute tax', 'ai regulation', 'intermediation',
]

THOUGHT_LEADER_FEEDS = {
    'deeplearning_ai': {
        'url': 'https://www.deeplearning.ai/the-batch/feed',
        'name': 'DeepLearning.AI (Andrew Ng)',
        'purpose': 'Research-to-practice crossing signals',
    },
    'simon_willison': {
        'url': 'https://simonwillison.net/atom/everything/',
        'name': 'Simon Willison',
        'purpose': 'Real-world agent implementation patterns',
    },
    'latent_space': {
        'url': 'https://www.latent.space/feed',
        'name': 'Latent Space',
        'purpose': 'Infrastructure-level trends beneath agents',
    },
    'swyx': {
        'url': 'https://www.swyx.io/rss.xml',
        'name': 'Swyx',
        'purpose': 'Agent ecosystem analysis, DX trends',
    },
    'langchain_blog': {
        'url': 'https://blog.langchain.dev/rss/',
        'name': 'LangChain Blog (Harrison Chase)',
        'purpose': 'Tooling direction signals before obvious',
    },
    'ethan_mollick': {
        'url': 'https://www.oneusefulthing.org/feed',
        'name': 'Ethan Mollick (One Useful Thing)',
        'purpose': 'Adoption patterns, non-technical agent usage',
    },
}

THOUGHT_LEADER_TIER = 1.5

# Telegram (for notifications)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_OWNER_ID = os.getenv('TELEGRAM_OWNER_ID')

# Resend (for email newsletters)
RESEND_API_KEY = os.getenv('RESEND_API_KEY')
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

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
deepseek_client: Optional[OpenAI] = None

def init_clients():
    """Initialize API clients."""
    global supabase, openai_client, deepseek_client

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

    if DEEPSEEK_API_KEY:
        deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        logger.info("DeepSeek client initialized")
    else:
        logger.info("DeepSeek not configured — bulk tasks will use OpenAI fallback")

# ============================================================================
# Model Routing
# ============================================================================

_model_config_cache = None

def get_model_config() -> dict:
    """Load and cache model routing config from agentpulse-config.json."""
    global _model_config_cache
    if _model_config_cache is not None:
        return _model_config_cache

    config_path = Path('/home/openclaw/.openclaw/config/agentpulse-config.json')
    try:
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            _model_config_cache = config.get('models', {})
        else:
            logger.warning(f"Config file not found: {config_path}, using env defaults")
            _model_config_cache = {}
    except Exception as e:
        logger.warning(f"Failed to read model config: {e}, using env defaults")
        _model_config_cache = {}

    return _model_config_cache


def get_model(task_name: str) -> str:
    """Get the model for a given task, with fallback chain."""
    config = get_model_config()
    return config.get(task_name, config.get('default', OPENAI_MODEL))


def get_provider(model: str) -> str:
    """Determine provider from pricing config."""
    return get_full_config().get("pricing", {}).get(model, {}).get("provider", "openai")


# ============================================================================
# DeepSeek Circuit Breaker
# ============================================================================

_deepseek_failures: list = []
_circuit_open_until: float = 0.0


def _is_deepseek_available() -> bool:
    """Return False if circuit breaker is open (5+ failures in 10 min window)."""
    global _circuit_open_until
    now = time.time()
    if now < _circuit_open_until:
        return False
    # Prune failures older than 10 minutes
    cutoff = now - 600
    while _deepseek_failures and _deepseek_failures[0] < cutoff:
        _deepseek_failures.pop(0)
    return len(_deepseek_failures) < 5


def _record_deepseek_failure():
    """Record a DeepSeek failure; open circuit breaker if threshold reached."""
    global _circuit_open_until
    _deepseek_failures.append(time.time())
    cutoff = time.time() - 600
    while _deepseek_failures and _deepseek_failures[0] < cutoff:
        _deepseek_failures.pop(0)
    if len(_deepseek_failures) >= 5:
        _circuit_open_until = time.time() + 300
        logger.warning("Circuit breaker OPEN — routing DeepSeek tasks to OpenAI for 5 minutes")


def routed_llm_call(model, messages, temperature=0.3, max_tokens=4000, **kwargs):
    """Route LLM call to correct provider with DeepSeek→OpenAI fallback."""
    provider = get_provider(model)
    actual_model = model

    # If DeepSeek requested but unavailable, fall back to OpenAI
    if provider == "deepseek" and (not deepseek_client or not _is_deepseek_available()):
        actual_model = "gpt-4o-mini"
        provider = "openai"
        logger.info(f"Routing {model} → {actual_model} (circuit breaker or no client)")

    client = deepseek_client if provider == "deepseek" else openai_client

    try:
        return client.chat.completions.create(
            model=actual_model, messages=messages,
            temperature=temperature, max_tokens=max_tokens, **kwargs
        )
    except Exception as e:
        if provider == "deepseek":
            _record_deepseek_failure()
            fallback = "gpt-4o-mini"
            logger.warning(f"DeepSeek failed: {e} — falling back to {fallback}")
            return openai_client.chat.completions.create(
                model=fallback, messages=messages,
                temperature=temperature, max_tokens=max_tokens, **kwargs
            )
        raise


# ============================================================================
# Full Config Loading
# ============================================================================

_full_config_cache = None

def get_full_config() -> dict:
    """Load and cache the full agentpulse-config.json."""
    global _full_config_cache
    if _full_config_cache is not None:
        return _full_config_cache

    config_path = Path('/home/openclaw/.openclaw/config/agentpulse-config.json')
    try:
        if config_path.exists():
            with open(config_path) as f:
                _full_config_cache = json.load(f)
        else:
            logger.warning(f"Config file not found: {config_path}, using empty config")
            _full_config_cache = {}
    except Exception as e:
        logger.warning(f"Failed to read full config: {e}, using empty config")
        _full_config_cache = {}

    return _full_config_cache


# ============================================================================
# Budget Enforcement System
# ============================================================================

class AgentBudget:
    """Tracks and enforces budget limits for a single agent task."""

    def __init__(self, task_type: str, agent_name: str):
        config = get_budget_config(agent_name, task_type)
        self.agent_name = agent_name
        self.task_type = task_type
        self.max_llm_calls = config.get('max_llm_calls', 5)
        self.max_seconds = config.get('max_seconds', 180)
        self.max_subtasks = config.get('max_subtasks', 2)
        self.max_retries = config.get('max_retries', 1)

        self.llm_calls_used = 0
        self.subtasks_created = 0
        self.retries_used = 0
        self.start_time = time.time()

    def can_call_llm(self) -> bool:
        return (self.llm_calls_used < self.max_llm_calls and
                self.elapsed_seconds() < self.max_seconds)

    def can_create_subtask(self) -> bool:
        return self.subtasks_created < self.max_subtasks

    def can_retry(self) -> bool:
        return self.retries_used < self.max_retries

    def use_llm_call(self):
        self.llm_calls_used += 1

    def use_subtask(self):
        self.subtasks_created += 1

    def use_retry(self):
        self.retries_used += 1

    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    def remaining(self) -> dict:
        return {
            'llm_calls': self.max_llm_calls - self.llm_calls_used,
            'seconds': max(0, self.max_seconds - self.elapsed_seconds()),
            'subtasks': self.max_subtasks - self.subtasks_created,
            'retries': self.max_retries - self.retries_used
        }

    def exhausted_reason(self) -> str:
        if self.elapsed_seconds() >= self.max_seconds:
            return 'time_limit'
        if self.llm_calls_used >= self.max_llm_calls:
            return 'llm_call_limit'
        if self.subtasks_created >= self.max_subtasks:
            return 'subtask_limit'
        if self.retries_used >= self.max_retries:
            return 'retry_limit'
        return None

    def to_dict(self) -> dict:
        return {
            'agent_name': self.agent_name,
            'task_type': self.task_type,
            'limits': {
                'max_llm_calls': self.max_llm_calls,
                'max_seconds': self.max_seconds,
                'max_subtasks': self.max_subtasks,
                'max_retries': self.max_retries
            },
            'usage': {
                'llm_calls_used': self.llm_calls_used,
                'subtasks_created': self.subtasks_created,
                'retries_used': self.retries_used,
                'elapsed_seconds': round(self.elapsed_seconds(), 2)
            },
            'remaining': {
                'llm_calls': self.max_llm_calls - self.llm_calls_used,
                'seconds': round(max(0, self.max_seconds - self.elapsed_seconds()), 2),
                'subtasks': self.max_subtasks - self.subtasks_created,
                'retries': self.max_retries - self.retries_used
            },
            'exhausted_reason': self.exhausted_reason()
        }


def get_budget_config(agent_name: str, task_type: str) -> dict:
    """Read budget config for a specific agent and task type, with defaults."""
    config = get_full_config()
    budgets = config.get('budgets', {})
    agent_budgets = budgets.get(agent_name, {})
    task_budget = agent_budgets.get(task_type, {})

    defaults = {
        'max_llm_calls': 5,
        'max_seconds': 180,
        'max_subtasks': 2,
        'max_retries': 1
    }

    return {k: task_budget.get(k, defaults[k]) for k in defaults}


def check_daily_budget(agent_name: str) -> bool:
    """Check if the agent has LLM call budget remaining for today."""
    if not supabase:
        return True

    today = datetime.now(timezone.utc).date().isoformat()
    try:
        usage = supabase.table('agent_daily_usage')\
            .select('*')\
            .eq('agent_name', agent_name)\
            .eq('date', today)\
            .execute()

        if not usage.data:
            return True

        daily = usage.data[0]
        global_config = get_full_config().get('budgets', {}).get('global', {})
        max_daily = global_config.get('max_daily_llm_calls', 100)

        return daily.get('llm_calls_used', 0) < max_daily

    except Exception as e:
        logger.error(f"Failed to check daily budget for {agent_name}: {e}")
        return True


def increment_daily_usage(agent_name: str, llm_calls: int = 0, subtasks: int = 0, alerts: int = 0):
    """Upsert today's usage row for the given agent."""
    if not supabase:
        return

    today = datetime.now(timezone.utc).date().isoformat()
    try:
        existing = supabase.table('agent_daily_usage')\
            .select('*')\
            .eq('agent_name', agent_name)\
            .eq('date', today)\
            .execute()

        if existing.data:
            row = existing.data[0]
            supabase.table('agent_daily_usage').update({
                'llm_calls_used': (row.get('llm_calls_used', 0) or 0) + llm_calls,
                'subtasks_created': (row.get('subtasks_created', 0) or 0) + subtasks,
                'proactive_alerts_sent': (row.get('proactive_alerts_sent', 0) or 0) + alerts
            }).eq('id', row['id']).execute()
        else:
            supabase.table('agent_daily_usage').insert({
                'agent_name': agent_name,
                'date': today,
                'llm_calls_used': llm_calls,
                'subtasks_created': subtasks,
                'proactive_alerts_sent': alerts,
                'total_cost_estimate': 0
            }).execute()

    except Exception as e:
        logger.error(f"Failed to increment daily usage for {agent_name}: {e}")


def log_llm_call(agent_name, task_type, model, usage, duration_ms=0):
    """Log an LLM call with token counts and estimated cost."""
    try:
        pricing = get_full_config().get("pricing", {}).get(model, {})
        input_tok = getattr(usage, 'input_tokens', 0) or getattr(usage, 'prompt_tokens', 0) or 0
        output_tok = getattr(usage, 'output_tokens', 0) or getattr(usage, 'completion_tokens', 0) or 0
        total_tok = input_tok + output_tok
        cost = (input_tok * pricing.get("input", 0) + output_tok * pricing.get("output", 0)) / 1_000_000

        supabase.table("llm_call_log").insert({
            "agent_name": agent_name,
            "task_type": task_type,
            "model": model,
            "provider": pricing.get("provider", "unknown"),
            "input_tokens": input_tok,
            "output_tokens": output_tok,
            "total_tokens": total_tok,
            "estimated_cost": round(cost, 6),
            "duration_ms": duration_ms,
        }).execute()

        # v1 wallet accounting retired — proxy handles via v2 reserve/settle

    except Exception as e:
        logger.warning(f"Failed to log LLM call: {e}")


def get_daily_usage(agent_name: str = None) -> dict:
    """Return today's usage, optionally filtered by agent."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    today = datetime.now(timezone.utc).date().isoformat()
    try:
        query = supabase.table('agent_daily_usage')\
            .select('*')\
            .eq('date', today)

        if agent_name:
            query = query.eq('agent_name', agent_name)

        result = query.execute()

        global_config = get_full_config().get('budgets', {}).get('global', {})
        max_daily_llm = global_config.get('max_daily_llm_calls', 100)
        max_daily_alerts = global_config.get('max_daily_proactive_alerts', 5)

        usage_rows = result.data or []
        total_llm = sum(r.get('llm_calls_used', 0) or 0 for r in usage_rows)
        total_subtasks = sum(r.get('subtasks_created', 0) or 0 for r in usage_rows)
        total_alerts = sum(r.get('proactive_alerts_sent', 0) or 0 for r in usage_rows)

        return {
            'date': today,
            'agents': usage_rows,
            'totals': {
                'llm_calls_used': total_llm,
                'subtasks_created': total_subtasks,
                'proactive_alerts_sent': total_alerts
            },
            'limits': {
                'max_daily_llm_calls': max_daily_llm,
                'max_daily_proactive_alerts': max_daily_alerts
            },
            'remaining': {
                'llm_calls': max_daily_llm - total_llm,
                'proactive_alerts': max_daily_alerts - total_alerts
            }
        }

    except Exception as e:
        logger.error(f"Failed to get daily usage: {e}")
        return {'error': str(e)}


# ============================================================================
# Moltbook Scraping
# ============================================================================

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_moltbook_posts(submolt: str = None, limit: int = 25, sort: str = 'new') -> list:
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

def scrape_moltbook(submolts: list = None, posts_per_submolt: int = 25) -> dict:
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
    
    try:
        supabase.table('moltbook_posts').insert(record).execute()
        return True
    except Exception as e:
        logger.error(f"store_post: failed to insert post {moltbook_id}: {e}")
        return None

# ============================================================================
# Hacker News Scraping
# ============================================================================

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def scrape_hackernews(limit: int = 100) -> dict:
    """Scrape top HN stories, filter for AI/agent relevance, store in source_posts."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    logger.info(f"HN scrape: scanning top {limit} stories...")
    with httpx.Client(timeout=15) as client:
        try:
            resp = client.get(f"{HN_API_BASE}/topstories.json")
            resp.raise_for_status()
            story_ids = resp.json()[:limit]
        except Exception as e:
            logger.error(f"HN scrape: failed to fetch top stories: {e}")
            return {'error': str(e)}

        relevant_posts = []
        total_scanned = 0

        for story_id in story_ids:
            try:
                story_resp = client.get(f"{HN_API_BASE}/item/{story_id}.json")
                story_resp.raise_for_status()
                story = story_resp.json()

                if not story or story.get('type') != 'story' or not story.get('title'):
                    continue

                total_scanned += 1
                title_lower = story['title'].lower()

                if not any(kw in title_lower for kw in HN_KEYWORDS):
                    continue

                comments = []
                comment_ids = (story.get('kids') or [])[:20]
                for cid in comment_ids:
                    try:
                        c_resp = client.get(f"{HN_API_BASE}/item/{cid}.json")
                        c_resp.raise_for_status()
                        c = c_resp.json()
                        if c and c.get('text'):
                            comments.append({
                                'author': c.get('by', 'anon'),
                                'text': c['text'],
                                'score': c.get('score', 0)
                            })
                        time.sleep(0.2)
                    except Exception:
                        continue

                is_show_hn = title_lower.startswith('show hn')
                post_data = {
                    'source': 'hackernews',
                    'source_id': str(story_id),
                    'source_url': story.get('url') or f"https://news.ycombinator.com/item?id={story_id}",
                    'source_tier': 3,
                    'title': story['title'],
                    'body': '\n\n'.join(c['text'] for c in comments),
                    'author': story.get('by', 'anon'),
                    'score': story.get('score', 0),
                    'comment_count': story.get('descendants', 0),
                    'tags': ['show_hn'] if is_show_hn else [],
                    'metadata': {
                        'hn_url': f"https://news.ycombinator.com/item?id={story_id}",
                        'comments': comments[:10],
                        'is_show_hn': is_show_hn
                    }
                }
                relevant_posts.append(post_data)
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"HN scrape error for {story_id}: {e}")
                continue

        for post in relevant_posts:
            try:
                supabase.table('source_posts').upsert(
                    post, on_conflict='source,source_id'
                ).execute()
            except Exception as e:
                logger.error(f"HN upsert error for {post.get('source_id')}: {e}")

    logger.info(f"HN scrape complete: {len(relevant_posts)} relevant out of {total_scanned} scanned")
    return {
        'source': 'hackernews',
        'posts_found': len(relevant_posts),
        'total_scanned': total_scanned
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def scrape_github(days_back: int = 7) -> dict:
    """Scrape GitHub for new AI/agent repos, store in source_posts."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    logger.info(f"GitHub scrape: searching repos created in last {days_back} days...")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime('%Y-%m-%d')

    headers = {'Accept': 'application/vnd.github.v3+json'}
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'

    queries = [
        # AI / Agent queries
        f'ai agent created:>{cutoff} stars:>5',
        f'llm agent created:>{cutoff} stars:>5',
        f'autonomous agent created:>{cutoff} stars:>3',
        f'agentic created:>{cutoff} stars:>3',
        f'multi-agent created:>{cutoff} stars:>3',
        f'mcp server created:>{cutoff} stars:>3',
        # Bitcoin + AI intersection queries
        f'bitcoin ai created:>{cutoff} stars:>3',
        f'bitcoin llm created:>{cutoff} stars:>3',
        f'blockchain agent created:>{cutoff} stars:>3',
        f'lightning network ai created:>{cutoff} stars:>2',
    ]

    seen_repos = set()
    all_posts = []
    queries_run = 0

    with httpx.Client(timeout=15) as client:
        for query in queries:
            try:
                resp = client.get(
                    'https://api.github.com/search/repositories',
                    params={'q': query, 'sort': 'stars', 'order': 'desc', 'per_page': 20},
                    headers=headers,
                )
                if resp.status_code == 403:
                    logger.warning("GitHub rate limit hit")
                    break
                resp.raise_for_status()
                queries_run += 1

                for repo in resp.json().get('items', []):
                    if repo['id'] in seen_repos:
                        continue
                    seen_repos.add(repo['id'])

                    description = repo.get('description') or ''
                    stars = repo['stargazers_count']
                    forks = repo['forks_count']
                    language = repo.get('language') or 'N/A'
                    created_at = repo['created_at']

                    post_data = {
                        'source': 'github',
                        'source_id': str(repo['id']),
                        'source_url': repo['html_url'],
                        'source_tier': 3,
                        'title': repo['full_name'],
                        'body': f"{description}\n\nStars: {stars} | Forks: {forks} | Language: {language} | Created: {created_at}",
                        'author': repo['owner']['login'],
                        'score': stars,
                        'comment_count': repo.get('open_issues_count', 0),
                        'tags': repo.get('topics', []),
                        'metadata': {
                            'full_name': repo['full_name'],
                            'description': repo.get('description'),
                            'language': repo.get('language'),
                            'stars': stars,
                            'forks': forks,
                            'created_at': created_at,
                            'updated_at': repo['updated_at'],
                            'topics': repo.get('topics', []),
                            'is_fork': repo.get('fork', False),
                            'license': repo.get('license', {}).get('spdx_id') if repo.get('license') else None,
                        },
                    }
                    all_posts.append(post_data)

                time.sleep(2)
            except httpx.HTTPStatusError as e:
                logger.error(f"GitHub search error: {e}")
                continue
            except Exception as e:
                logger.error(f"GitHub search error: {e}")
                continue

    for post in all_posts:
        try:
            supabase.table('source_posts').upsert(
                post, on_conflict='source,source_id'
            ).execute()
        except Exception as e:
            logger.error(f"GitHub upsert error for {post.get('source_id')}: {e}")

    logger.info(f"GitHub scrape complete: {len(all_posts)} repos found across {queries_run} queries")
    return {'source': 'github', 'repos_found': len(all_posts), 'queries_run': queries_run}


def scrape_rss_feeds() -> dict:
    """Scrape RSS feeds for AI/agent-relevant articles, store in source_posts."""
    import feedparser

    if not supabase:
        return {'error': 'Supabase not configured'}

    run_id = log_pipeline_start('scrape_rss')
    feeds_scraped = 0
    results = {}

    for feed_name, feed_config in RSS_FEEDS.items():
        try:
            logger.info(f"RSS scrape: parsing {feed_name} ({feed_config['url']})")
            feed = feedparser.parse(feed_config['url'])
            relevant_count = 0

            for entry in feed.entries[:30]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                text_lower = (title + ' ' + summary).lower()

                if not any(kw in text_lower for kw in RSS_RELEVANCE_KEYWORDS):
                    continue

                post_data = {
                    'source': f'rss_{feed_name}',
                    'source_id': entry.get('id') or entry.get('link', ''),
                    'source_url': entry.get('link', ''),
                    'title': title,
                    'body': summary[:1000],
                    'author': entry.get('author', feed_name),
                    'score': feed_config['tier'],
                    'source_tier': feed_config['tier'],
                    'comment_count': 0,
                    'tags': [feed_config['category'], f"tier_{feed_config['tier']}"],
                    'metadata': {
                        'feed_name': feed_name,
                        'tier': feed_config['tier'],
                        'category': feed_config['category'],
                        'published': entry.get('published', ''),
                        'feed_url': feed_config['url'],
                    },
                }

                try:
                    supabase.table('source_posts').upsert(
                        post_data, on_conflict='source,source_id'
                    ).execute()
                    relevant_count += 1
                except Exception as e:
                    logger.error(f"RSS upsert error for {feed_name}/{post_data['source_id']}: {e}")

            results[feed_name] = relevant_count
            feeds_scraped += 1
            logger.info(f"RSS scrape: {feed_name} — {relevant_count} relevant articles")

        except Exception as e:
            logger.error(f"RSS scrape failed for {feed_name}: {e}")
            results[feed_name] = {'error': str(e)}

    total_articles = sum(v for v in results.values() if isinstance(v, int))
    log_pipeline_end(run_id, 'completed', {'feeds_scraped': feeds_scraped, 'total_articles': total_articles})
    logger.info(f"RSS scrape complete: {feeds_scraped} feeds, {total_articles} articles")
    return {'source': 'rss', 'feeds_scraped': feeds_scraped, 'results': results}


# ============================================================================
# Thought Leader Ingestion
# ============================================================================

def _detect_topics(text: str) -> list:
    """Lightweight keyword-based topic detection for thought leader content."""
    topic_map = {
        'agents': ['agent', 'agentic', 'multi-agent', 'autonomous'],
        'llm': ['llm', 'large language model', 'foundation model', 'gpt', 'claude', 'gemini'],
        'rag': ['rag', 'retrieval', 'vector', 'embedding'],
        'tooling': ['langchain', 'llamaindex', 'autogen', 'crewai', 'mcp', 'function call', 'tool use'],
        'infrastructure': ['inference', 'gpu', 'deployment', 'serving', 'fine-tun', 'training'],
        'adoption': ['enterprise', 'adoption', 'production', 'real-world', 'case study'],
        'safety': ['alignment', 'safety', 'guardrail', 'hallucination', 'eval'],
        'developer_experience': ['developer', 'dx', 'sdk', 'api', 'framework'],
        'open_source': ['open source', 'open-source', 'hugging face', 'ollama', 'llama'],
        'startups': ['startup', 'funding', 'yc', 'seed', 'series a', 'venture'],
        'bitcoin': ['bitcoin', 'btc', 'satoshi', 'lightning network', 'nostr', 'ordinals'],
        'crypto': ['blockchain', 'crypto', 'defi', 'web3', 'smart contract', 'tokenization'],
    }
    text_lower = text.lower()
    return [topic for topic, keywords in topic_map.items() if any(kw in text_lower for kw in keywords)]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def scrape_thought_leaders() -> dict:
    """Ingest thought leader RSS feeds as Tier 1.5 sources with topic detection and dedup."""
    import feedparser

    if not supabase:
        return {'error': 'Supabase not configured'}

    run_id = log_pipeline_start('scrape_thought_leaders')
    feeds_scraped = 0
    results = {}

    existing_urls = set()
    try:
        recent = supabase.table('source_posts')\
            .select('source_url')\
            .like('source', 'thought_leader_%')\
            .gte('scraped_at', (datetime.now(timezone.utc) - timedelta(days=14)).isoformat())\
            .execute()
        existing_urls = {r['source_url'] for r in (recent.data or []) if r.get('source_url')}
    except Exception as e:
        logger.warning(f"Could not pre-fetch existing thought leader URLs: {e}")

    for feed_key, feed_config in THOUGHT_LEADER_FEEDS.items():
        try:
            logger.info(f"Thought leader scrape: parsing {feed_config['name']} ({feed_config['url']})")
            try:
                with httpx.Client(timeout=15, follow_redirects=True) as client:
                    resp = client.get(feed_config['url'], headers={'User-Agent': 'AgentPulse/1.0'})
                feed = feedparser.parse(resp.text)
            except Exception as fetch_err:
                logger.warning(f"Feed {feed_key} fetch failed: {fetch_err}")
                results[feed_key] = {'error': f'Fetch failed: {fetch_err}'}
                continue

            if feed.bozo and not feed.entries:
                logger.warning(f"Feed {feed_key} returned errors and no entries — skipping")
                results[feed_key] = {'error': 'Feed parse failed / empty'}
                continue

            ingested_count = 0

            for entry in feed.entries[:20]:
                url = entry.get('link', '')
                if url in existing_urls:
                    continue

                title = entry.get('title', '')
                summary = entry.get('summary', entry.get('description', ''))
                content = entry.get('content', [{}])[0].get('value', '') if entry.get('content') else ''
                full_text = f"{title} {summary} {content}"

                published = entry.get('published', entry.get('updated', ''))

                topics = _detect_topics(full_text)

                source_id = entry.get('id') or url

                post_data = {
                    'source': f'thought_leader_{feed_key}',
                    'source_id': source_id,
                    'source_url': url,
                    'source_tier': 2,
                    'title': title,
                    'body': (summary or content)[:2000],
                    'author': feed_config['name'],
                    'score': THOUGHT_LEADER_TIER,
                    'comment_count': 0,
                    'tags': topics + ['thought_leader', f'tl_{feed_key}'],
                    'metadata': {
                        'feed_key': feed_key,
                        'source_name': feed_config['name'],
                        'source_tier': 'thought_leader',
                        'tier_numeric': THOUGHT_LEADER_TIER,
                        'purpose': feed_config['purpose'],
                        'published_at': published,
                        'topics_detected': topics,
                        'content_summary': (summary or content)[:500],
                        'feed_url': feed_config['url'],
                    },
                }

                try:
                    supabase.table('source_posts').upsert(
                        post_data, on_conflict='source,source_id'
                    ).execute()
                    existing_urls.add(url)
                    ingested_count += 1
                except Exception as e:
                    logger.error(f"Thought leader upsert error for {feed_key}/{source_id}: {e}")

            results[feed_key] = ingested_count
            feeds_scraped += 1
            logger.info(f"Thought leader scrape: {feed_config['name']} — {ingested_count} articles ingested")

        except Exception as e:
            logger.error(f"Thought leader scrape failed for {feed_key} ({feed_config['name']}): {e}")
            results[feed_key] = {'error': str(e)}

    total_articles = sum(v for v in results.values() if isinstance(v, int))
    summary = {
        'source': 'thought_leaders',
        'feeds_scraped': feeds_scraped,
        'total_articles': total_articles,
        'results': results,
    }
    log_pipeline_end(run_id, 'completed', summary)
    logger.info(f"Thought leader scrape complete: {feeds_scraped}/{len(THOUGHT_LEADER_FEEDS)} feeds, {total_articles} articles")
    return summary


# ============================================================================
# X/Twitter Source Account Scanning
# ============================================================================

# Config file path (fallback if DB table not yet created)
_X_SOURCE_ACCOUNTS_CONFIG = Path(__file__).resolve().parent.parent.parent / 'config' / 'x_source_accounts.json'
X_SOURCE_ACCOUNT_TIER = 1.5  # Same tier as thought leaders — high-signal individual voices


def _load_x_source_accounts() -> list:
    """Load active X source accounts from Supabase, falling back to config file."""
    # Try DB first
    if supabase:
        try:
            result = supabase.table('x_source_accounts')\
                .select('x_handle, display_name, category, description, priority')\
                .eq('active', True)\
                .order('priority', desc=True)\
                .execute()
            if result.data:
                logger.info(f"Loaded {len(result.data)} X source accounts from DB")
                return result.data
        except Exception as e:
            logger.warning(f"Could not load X source accounts from DB (table may not exist yet): {e}")

    # Fallback to config file
    try:
        if _X_SOURCE_ACCOUNTS_CONFIG.exists():
            config = json.loads(_X_SOURCE_ACCOUNTS_CONFIG.read_text())
            accounts = config.get('accounts', [])
            # Normalize to same shape as DB rows
            normalized = []
            for a in accounts:
                normalized.append({
                    'x_handle': a['handle'],
                    'display_name': a.get('name', a['handle']),
                    'category': a.get('category', 'uncategorized'),
                    'description': a.get('description', ''),
                    'priority': 5,
                })
            logger.info(f"Loaded {len(normalized)} X source accounts from config file")
            return normalized
    except Exception as e:
        logger.warning(f"Could not load X source accounts config file: {e}")

    return []


def scrape_x_source_accounts() -> dict:
    """Scan curated X/Twitter accounts and ingest tweets into source_posts.

    Uses X API v2 search with from:<handle> queries, batched in groups of 5
    using OR to minimize API calls. Respects X API budget.
    """
    if not supabase:
        return {'error': 'Supabase not configured'}

    if not X_BEARER_TOKEN:
        logger.warning("X_BEARER_TOKEN not set — skipping X source account scan")
        return {'skipped': True, 'reason': 'no_bearer_token'}

    if not _check_x_budget():
        logger.info("X API weekly budget exhausted — skipping X source account scan")
        return {'skipped': True, 'reason': 'budget_exhausted'}

    run_id = log_pipeline_start('scrape_x_source_accounts')
    accounts = _load_x_source_accounts()

    if not accounts:
        log_pipeline_end(run_id, 'completed', {'accounts': 0, 'tweets_ingested': 0})
        return {'accounts': 0, 'tweets_ingested': 0}

    # Dedup against recently ingested tweets
    existing_ids = set()
    try:
        recent = supabase.table('source_posts')\
            .select('source_id')\
            .like('source', 'x_source_%')\
            .gte('scraped_at', (datetime.now(timezone.utc) - timedelta(days=7)).isoformat())\
            .execute()
        existing_ids = {r['source_id'] for r in (recent.data or []) if r.get('source_id')}
    except Exception as e:
        logger.warning(f"Could not pre-fetch existing X source post IDs: {e}")

    # Build handle→account lookup
    handle_map = {a['x_handle'].lower(): a for a in accounts}
    handles = [a['x_handle'] for a in accounts]

    total_ingested = 0
    results_by_category = {}

    # Batch handles in groups of 5 for efficient OR queries
    for i in range(0, len(handles), 5):
        if not _check_x_budget():
            logger.info("X API budget exhausted mid-scan — stopping")
            break

        batch = handles[i:i+5]
        query = ' OR '.join(f'from:{h}' for h in batch)
        # Exclude retweets and replies to get original content only
        query += ' -is:retweet -is:reply'

        tweets = _x_api_search(query, max_results=20)

        for tw in tweets:
            tweet_id = tw.get('id', '')
            if tweet_id in existing_ids:
                continue

            username = tw.get('author_username', '').lower()
            account_info = handle_map.get(username, {})
            category = account_info.get('category', 'uncategorized')
            display_name = account_info.get('display_name', username)

            # Skip very short tweets (likely noise)
            text = tw.get('text', '')
            if len(text) < 30:
                continue

            topics = _detect_topics(text)
            metrics = tw.get('public_metrics', {})

            post_data = {
                'source': f'x_source_{username}',
                'source_id': tweet_id,
                'source_url': f'https://x.com/{tw.get("author_username", username)}/status/{tweet_id}',
                'source_tier': 2,
                'title': f'@{tw.get("author_username", username)}: {text[:100]}',
                'body': text,
                'author': display_name,
                'score': X_SOURCE_ACCOUNT_TIER,
                'comment_count': metrics.get('reply_count', 0),
                'tags': topics + ['x_source', f'x_cat_{category}', f'x_{username}'],
                'metadata': {
                    'x_handle': tw.get('author_username', username),
                    'display_name': display_name,
                    'category': category,
                    'description': account_info.get('description', ''),
                    'source_tier': 'x_source_account',
                    'tier_numeric': X_SOURCE_ACCOUNT_TIER,
                    'tweet_id': tweet_id,
                    'created_at': tw.get('created_at', ''),
                    'topics_detected': topics,
                    'metrics': {
                        'likes': metrics.get('like_count', 0),
                        'retweets': metrics.get('retweet_count', 0),
                        'replies': metrics.get('reply_count', 0),
                        'quotes': metrics.get('quote_count', 0),
                    },
                },
            }

            try:
                supabase.table('source_posts').upsert(
                    post_data, on_conflict='source,source_id'
                ).execute()
                existing_ids.add(tweet_id)
                total_ingested += 1
                results_by_category[category] = results_by_category.get(category, 0) + 1
            except Exception as e:
                logger.error(f"X source post upsert error for {username}/{tweet_id}: {e}")

    # Update last_scanned_at for accounts in DB
    if supabase and handles:
        try:
            supabase.table('x_source_accounts').update({
                'last_scanned_at': datetime.now(timezone.utc).isoformat()
            }).in_('x_handle', handles).execute()
        except Exception:
            pass  # Table may not exist yet

    summary = {
        'source': 'x_source_accounts',
        'accounts_scanned': len(handles),
        'tweets_ingested': total_ingested,
        'by_category': results_by_category,
    }
    log_pipeline_end(run_id, 'completed', summary)
    logger.info(f"X source account scan complete: {len(handles)} accounts, {total_ingested} tweets ingested")
    return summary


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
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
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
    extraction_model = get_model('extraction')
    logger.info(f"Using model: {extraction_model} for problem extraction")
    
    # Format posts for prompt
    posts_text = "\n\n".join([
        f"[Post ID: {p['moltbook_id']}]\n{p.get('title', '')}\n{p['content']}"
        for p in posts.data
    ])
    
    # Call LLM (routed to DeepSeek or OpenAI based on config)
    try:
        _t0 = time.time()
        response = routed_llm_call(
            extraction_model,
            messages=[
                {"role": "system", "content": "You extract business problems from text. Respond only with valid JSON."},
                {"role": "user", "content": PROBLEM_EXTRACTION_PROMPT.format(posts=posts_text)}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        log_llm_call("processor", "extraction", response.model, response.usage, int((time.time() - _t0) * 1000))
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
        'source': problem.get('source', 'unknown'),
        'max_source_tier': problem.get('max_source_tier', 3),
        'signal_phrases': problem.get('signal_phrases', []),
        'source_post_ids': problem.get('source_post_ids', []),
        'frequency_count': 1,
        'metadata': {
            'severity': problem.get('severity'),
            'willingness_to_pay': problem.get('willingness_to_pay'),
            'max_source_tier': problem.get('max_source_tier', 3),
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
    clustering_model = get_model('clustering')
    logger.info(f"Using model: {clustering_model} for clustering")

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

    # Call LLM for clustering
    try:
        _t0 = time.time()
        response = routed_llm_call(
            clustering_model,
            messages=[
                {"role": "system", "content": "You group business problems into thematic clusters. Respond only with valid JSON."},
                {"role": "user", "content": CLUSTERING_PROMPT.format(problems=problems_text)}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        log_llm_call("processor", "clustering", response.model, response.usage, int((time.time() - _t0) * 1000))
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
            now = datetime.now(timezone.utc)
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

            # tier_weight: boost clusters sourced from authority sources
            cluster_tiers = [
                p.get('metadata', {}).get('max_source_tier', 3)
                for p in cluster_problems_data
            ]
            best_tier = min(cluster_tiers) if cluster_tiers else 3
            tier_weight = {1: 1.0, 2: 0.7}.get(best_tier, 0.4)

            opportunity_score = (freq_weight * 0.25) + (recency_weight * 0.15) + (wtp_weight * 0.25) + (gap_weight * 0.15) + (tier_weight * 0.20)

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
                    'solution_gap': gap,
                    'max_source_tier': best_tier,
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
    opp_model = get_model('opportunity_generation')
    logger.info(f"Using model: {opp_model} for opportunity generation from {len(new_clusters)} clusters")

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

            _t0 = time.time()
            response = routed_llm_call(
                opp_model,
                messages=[
                    {"role": "system", "content": "You generate startup opportunity briefs. Respond only with valid JSON."},
                    {"role": "user", "content": OPPORTUNITY_PROMPT.format(problem_data=problem_data)}
                ],
                temperature=0.5,
                max_tokens=2000
            )
            log_llm_call("processor", "opportunity_generation", response.model, response.usage, int((time.time() - _t0) * 1000))
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


def _normalize_title(title: str) -> str:
    """Normalize a title for fuzzy comparison: lowercase, strip punctuation, collapse whitespace."""
    import re as _re
    t = title.lower().strip()
    t = _re.sub(r'[^a-z0-9\s]', '', t)
    t = _re.sub(r'\s+', ' ', t).strip()
    return t


def find_similar_opportunity(title: str) -> dict | None:
    """Find an existing opportunity with a matching or similar title.

    Returns the matching row dict or None.
    Strategy:
      1. Exact case-insensitive ILIKE match
      2. Python-side fuzzy match: normalized title containment or high overlap
    """
    if not supabase or not title:
        return None

    # 1. Exact case-insensitive match
    exact = supabase.table('opportunities')\
        .select('id, title, confidence_score, review_count')\
        .ilike('title', title.strip())\
        .limit(1)\
        .execute()

    if exact.data:
        return exact.data[0]

    # 2. Fuzzy match — fetch all active opportunities and compare
    all_opps = supabase.table('opportunities')\
        .select('id, title, confidence_score, review_count')\
        .execute()

    if not all_opps.data:
        return None

    norm_new = _normalize_title(title)
    if not norm_new:
        return None

    # Extract the "core" words (words with 4+ chars) for overlap comparison
    new_words = set(w for w in norm_new.split() if len(w) >= 4)

    best_match = None
    best_score = 0.0

    for row in all_opps.data:
        existing_title = row.get('title', '')
        norm_existing = _normalize_title(existing_title)
        if not norm_existing:
            continue

        # Check containment: one title contains the other
        if norm_new in norm_existing or norm_existing in norm_new:
            return row

        # Word overlap: if 60%+ of meaningful words match, it's a dup
        existing_words = set(w for w in norm_existing.split() if len(w) >= 4)
        if not new_words or not existing_words:
            continue

        overlap = len(new_words & existing_words)
        union = len(new_words | existing_words)
        score = overlap / union if union > 0 else 0

        if score > best_score:
            best_score = score
            best_match = row

    if best_score >= 0.6:
        return best_match

    return None


def store_opportunity(opp: dict, cluster_id: str = None):
    """Store opportunity in Supabase, merging with existing if title matches."""
    if not supabase:
        return

    title = (opp.get('title') or '').strip()
    if not title:
        logger.warning("Skipping opportunity with empty title")
        return

    # Check for existing similar opportunity
    existing = find_similar_opportunity(title)

    if existing:
        row_id = existing['id']
        update = {
            'confidence_score': max(
                opp.get('confidence_score', 0.5),
                existing.get('confidence_score', 0) or 0
            ),
            'problem_summary': opp.get('problem_summary'),
            'proposed_solution': opp.get('proposed_solution'),
            'business_model': opp.get('business_model'),
            'target_market': opp.get('target_market'),
            'market_size_estimate': opp.get('market_size_estimate'),
            'why_now': opp.get('why_now'),
            'last_reviewed_at': datetime.now(timezone.utc).isoformat(),
            'review_count': (existing.get('review_count') or 0) + 1,
        }
        if cluster_id:
            update['cluster_id'] = cluster_id

        supabase.table('opportunities').update(update).eq('id', row_id).execute()
        logger.info(f"Merged duplicate opportunity into {row_id}: '{title}' (matched '{existing.get('title')}')")
        return

    # No match — insert new record
    record = {
        'title': title,
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
    logger.info(f"Created new opportunity: '{title}'")

def save_opportunity_brief(opp: dict):
    """Save opportunity as local markdown file, overwriting if a file for the same title exists."""
    title = opp.get('title', 'untitled')
    slug = title[:40].strip()
    slug = "".join(c if c.isalnum() or c in '-_' else '_' for c in slug)
    slug = slug.strip('_')

    # Check for existing file with matching title slug (overwrite instead of creating new)
    canonical_name = f"opp_{slug}.md"
    target_path = OPPORTUNITIES_DIR / canonical_name

    # Also remove any old timestamped variants for the same title
    norm_slug = slug.lower()
    for existing_file in OPPORTUNITIES_DIR.glob('opp_*.md'):
        # Normalize the existing filename for comparison
        existing_norm = existing_file.stem.lower()
        # Strip the opp_ prefix and any timestamp prefix (opp_YYYYMMDD_HHMMSS_)
        stripped = existing_norm
        if stripped.startswith('opp_'):
            stripped = stripped[4:]
        # Remove leading timestamp if present (20260206_210624_)
        import re as _re
        stripped = _re.sub(r'^\d{8}_\d{6}_?', '', stripped)
        # Check if remaining slug matches
        if stripped and norm_slug and (stripped in norm_slug or norm_slug in stripped):
            if existing_file != target_path:
                existing_file.unlink()
                logger.info(f"Removed duplicate local file: {existing_file.name}")

    content = f"""# {opp.get('title', 'Untitled Opportunity')}

**Last Updated:** {datetime.now().isoformat()}
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
    
    target_path.write_text(content)
    logger.info(f"Saved opportunity brief: {canonical_name}")


def deduplicate_opportunities() -> dict:
    """One-time cleanup: find and merge duplicate opportunities in Supabase and local files."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    all_opps = supabase.table('opportunities')\
        .select('*')\
        .order('created_at', desc=False)\
        .execute()

    if not all_opps.data:
        return {'duplicates_found': 0, 'records_deleted': 0}

    # Group by normalized title
    groups: dict[str, list] = {}
    for opp in all_opps.data:
        norm = _normalize_title(opp.get('title', ''))
        if not norm:
            continue
        if norm not in groups:
            groups[norm] = []
        groups[norm].append(opp)

    # Also group by fuzzy match (merge groups with 60%+ word overlap)
    merged_groups: dict[str, list] = {}
    norm_keys = list(groups.keys())
    assigned = set()

    for i, key_a in enumerate(norm_keys):
        if key_a in assigned:
            continue
        merged_groups[key_a] = list(groups[key_a])
        assigned.add(key_a)
        words_a = set(w for w in key_a.split() if len(w) >= 4)

        for key_b in norm_keys[i + 1:]:
            if key_b in assigned:
                continue
            words_b = set(w for w in key_b.split() if len(w) >= 4)
            if not words_a or not words_b:
                continue

            # Check containment or word overlap
            overlap = len(words_a & words_b)
            union = len(words_a | words_b)
            score = overlap / union if union > 0 else 0

            if score >= 0.6 or key_a in key_b or key_b in key_a:
                merged_groups[key_a].extend(groups[key_b])
                assigned.add(key_b)

    duplicates_found = 0
    records_deleted = 0
    merge_log = []

    for norm_title, opps in merged_groups.items():
        if len(opps) <= 1:
            continue

        duplicates_found += 1

        # Keep the record with the highest confidence score (tie-break: oldest)
        opps.sort(key=lambda o: (-1 * (o.get('confidence_score') or 0), o.get('created_at', '')))
        keeper = opps[0]
        to_delete = opps[1:]

        # Merge: take the max confidence and highest review count
        max_confidence = max((o.get('confidence_score') or 0) for o in opps)
        total_reviews = sum((o.get('review_count') or 0) for o in opps)

        try:
            supabase.table('opportunities').update({
                'confidence_score': max_confidence,
                'review_count': total_reviews,
                'last_reviewed_at': datetime.now(timezone.utc).isoformat(),
            }).eq('id', keeper['id']).execute()

            for dup in to_delete:
                supabase.table('opportunities').delete().eq('id', dup['id']).execute()
                records_deleted += 1

            merge_log.append({
                'kept': keeper['id'],
                'title': keeper.get('title'),
                'deleted': [d['id'] for d in to_delete],
                'merged_confidence': max_confidence,
            })

            logger.info(
                f"Dedup: kept '{keeper.get('title')}' ({keeper['id']}), "
                f"deleted {len(to_delete)} duplicates"
            )

        except Exception as e:
            logger.error(f"Error deduplicating '{keeper.get('title')}': {e}")

    # Clean up local files too
    local_cleaned = _deduplicate_local_files()

    result = {
        'duplicates_found': duplicates_found,
        'records_deleted': records_deleted,
        'local_files_removed': local_cleaned,
        'merge_log': merge_log,
    }
    logger.info(f"Deduplication complete: {result}")
    return result


def _deduplicate_local_files() -> int:
    """Remove duplicate local opportunity markdown files, keeping one per normalized title."""
    import re as _re

    files = list(OPPORTUNITIES_DIR.glob('opp_*.md'))
    if not files:
        return 0

    # Group files by normalized title extracted from filename
    groups: dict[str, list] = {}
    for f in files:
        stem = f.stem.lower()
        if stem.startswith('opp_'):
            stem = stem[4:]
        # Strip timestamp prefix
        stem = _re.sub(r'^\d{8}_\d{6}_?', '', stem)
        stem = stem.strip('_')
        if not stem:
            continue
        if stem not in groups:
            groups[stem] = []
        groups[stem].append(f)

    removed = 0
    for slug, file_list in groups.items():
        if len(file_list) <= 1:
            continue
        # Keep the newest file, remove the rest
        file_list.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        for old_file in file_list[1:]:
            old_file.unlink()
            removed += 1
            logger.info(f"Removed duplicate local file: {old_file.name}")

    return removed


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
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    posts = supabase.table('moltbook_posts')\
        .select('*')\
        .gte('scraped_at', cutoff.isoformat())\
        .limit(100)\
        .execute()

    if not posts.data:
        logger.info("No posts found for tool extraction")
        return {'posts_scanned': 0, 'mentions_found': 0}

    logger.info(f"Scanning {len(posts.data)} posts for tool mentions")
    tool_model = get_model('extraction')
    logger.info(f"Using model: {tool_model} for tool extraction")

    # Format posts for prompt
    posts_text = "\n\n".join([
        f"[Post ID: {p['moltbook_id']}]\n{p.get('title', '')}\n{p['content']}"
        for p in posts.data
    ])

    try:
        _t0 = time.time()
        response = routed_llm_call(
            tool_model,
            messages=[
                {"role": "system", "content": "You extract tool and product mentions. Respond only with valid JSON."},
                {"role": "user", "content": TOOL_EXTRACTION_PROMPT.format(posts=posts_text)}
            ],
            temperature=0.2,
            max_tokens=4000
        )
        log_llm_call("processor", "tool_extraction", response.model, response.usage, int((time.time() - _t0) * 1000))
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
                'mentioned_at': datetime.now(timezone.utc).isoformat(),
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
    now = datetime.now(timezone.utc)
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
# Trending Topics Extraction
# ============================================================================

TRENDING_TOPICS_PROMPT = """You analyze social media posts by AI agents for interesting, surprising, or culturally significant conversations. You are NOT looking for business problems or complaints — you are looking for what makes the agent economy INTERESTING.

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
{{
  "topics": [
    {{
      "title": "...",
      "description": "...",
      "topic_type": "...",
      "engagement_score": 0.0,
      "novelty_score": 0.0,
      "source_post_ids": ["..."],
      "why_interesting": "..."
    }}
  ]
}}

Find 3-8 topics. Quality over quantity. Skip anything boring or generic.
These should make someone say 'huh, that's interesting' not 'yeah, obviously.'"""


def extract_trending_topics(hours_back: int = 48) -> dict:
    """Extract trending/interesting topics from recent posts."""
    if not supabase or not openai_client:
        logger.error("Supabase or OpenAI not configured")
        return {'error': 'Not configured'}

    run_id = log_pipeline_start('extract_trending_topics')

    # Fetch recent posts
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    posts = supabase.table('moltbook_posts')\
        .select('*')\
        .gte('scraped_at', cutoff.isoformat())\
        .limit(100)\
        .execute()

    if not posts.data:
        logger.info("No posts found for trending topics extraction")
        log_pipeline_end(run_id, 'completed', {'posts_scanned': 0, 'topics_found': 0})
        return {'posts_scanned': 0, 'topics_found': 0}

    logger.info(f"Scanning {len(posts.data)} posts for trending topics")
    trending_model = get_model('trending_topics')
    logger.info(f"Using model: {trending_model} for trending topics extraction")

    # Format posts for prompt
    posts_text = "\n\n".join([
        f"[Post ID: {p['moltbook_id']}]\n{p.get('title', '')}\n{p['content']}"
        for p in posts.data
    ])

    try:
        _t0 = time.time()
        response = routed_llm_call(
            trending_model,
            messages=[
                {"role": "system", "content": "You identify interesting and culturally significant conversations in AI agent communities. Respond only with valid JSON."},
                {"role": "user", "content": TRENDING_TOPICS_PROMPT.format(posts=posts_text)}
            ],
            temperature=0.5,
            max_tokens=4000
        )
        log_llm_call("processor", "trending_topics", response.model, response.usage, int((time.time() - _t0) * 1000))
        time.sleep(2)  # Rate limiting

        result_text = response.choices[0].message.content
        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]
        result_text = result_text.strip()

        topics_data = json.loads(result_text)

    except Exception as e:
        logger.error(f"Trending topics extraction failed: {e}")
        log_pipeline_end(run_id, 'failed', {'error': str(e)})
        return {'error': str(e)}

    # Store topics
    topics_stored = 0
    for topic in topics_data.get('topics', []):
        try:
            record = {
                'title': topic['title'],
                'description': topic.get('description'),
                'topic_type': topic.get('topic_type', 'technical'),
                'source_post_ids': topic.get('source_post_ids', []),
                'engagement_score': topic.get('engagement_score', 0.0),
                'novelty_score': topic.get('novelty_score', 0.0),
                'why_interesting': topic.get('why_interesting'),
                'metadata': {}
            }

            supabase.table('trending_topics').insert(record).execute()
            topics_stored += 1

        except Exception as e:
            logger.error(f"Error storing trending topic '{topic.get('title', '?')}': {e}")

    result = {
        'posts_scanned': len(posts.data),
        'topics_found': topics_stored
    }
    log_pipeline_end(run_id, 'completed', result)
    logger.info(f"Trending topics extraction complete: {topics_stored} topics from {len(posts.data)} posts")
    return result


# ============================================================================
# Multi-Source Extraction
# ============================================================================

SOURCE_CONTEXT = {
    'hackernews': '(Technical discussion forum — comments are the main signal)',
    'github': '(Repository listings — descriptions and stars indicate market interest)',
    'moltbook': '(Agent social network — direct from AI agents)',
}


def _format_multisource_posts(posts: list) -> str:
    """Group posts by source and format with source context headers."""
    by_source: dict[str, list] = {}
    for post in posts:
        src = post.get('source', 'unknown')
        if src not in by_source:
            by_source[src] = []
        by_source[src].append(post)

    formatted = ""
    for source, source_posts in by_source.items():
        formatted += f"\n\n=== SOURCE: {source.upper()} ===\n"
        context = SOURCE_CONTEXT.get(source, '')
        if not context and source.startswith('rss_'):
            feed_config = RSS_FEEDS.get(source[4:], {})
            tier = feed_config.get('tier', 3)
            context = f'(Tier {tier} {feed_config.get("category", "unknown")} source)'
        formatted += context + "\n"
        for post in source_posts:
            tier = post.get('source_tier', 3)
            tier_label = {1: 'AUTHORITY', 2: 'CURATED'}.get(tier, 'COMMUNITY')
            formatted += f"\n[{post.get('source_id', 'unknown')}] [{tier_label}] {post.get('title', 'Untitled')}\n"
            body = post.get('body') or ''
            if body:
                formatted += f"{body[:500]}\n"
            if post.get('score'):
                formatted += f"Score/Stars: {post['score']}\n"
            tags = post.get('tags') or []
            if tags:
                formatted += f"Tags: {', '.join(tags)}\n"
    return formatted


def _clean_json_response(text: str) -> str:
    """Strip markdown code fences from LLM JSON output."""
    if text.startswith('```'):
        text = text.split('```')[1]
        if text.startswith('json'):
            text = text[4:]
    return text.strip()


def extract_problems_multisource(hours_back: int = 48) -> dict:
    """Extract problems from all sources in source_posts."""
    if not supabase or not openai_client:
        return {'error': 'Not configured'}

    run_id = log_pipeline_start('extract_problems_multisource')

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    posts = supabase.table('source_posts')\
        .select('*')\
        .eq('processed', False)\
        .gte('scraped_at', cutoff)\
        .order('score', desc=True)\
        .limit(200)\
        .execute()

    if not posts.data:
        logger.info("No unprocessed source_posts found for problem extraction")
        log_pipeline_end(run_id, 'completed', {'processed': 0, 'problems_found': 0})
        return {'processed': 0, 'problems_found': 0, 'sources': []}

    sources_seen = list({p.get('source') for p in posts.data})
    best_tier_in_batch = min(p.get('source_tier', 3) for p in posts.data)
    logger.info(f"Multi-source problem extraction: {len(posts.data)} posts from {sources_seen}, best tier={best_tier_in_batch}")

    posts_text = _format_multisource_posts(posts.data)
    extraction_model = get_model('extraction')

    try:
        _t0 = time.time()
        response = routed_llm_call(
            extraction_model,
            messages=[
                {"role": "system", "content": "You extract business problems from text. Respond only with valid JSON."},
                {"role": "user", "content": PROBLEM_EXTRACTION_PROMPT.format(posts=posts_text)}
            ],
            temperature=0.3,
            max_tokens=4000
        )
        log_llm_call("processor", "extraction_multisource", response.model, response.usage, int((time.time() - _t0) * 1000))
        time.sleep(2)
        problems_data = json.loads(_clean_json_response(response.choices[0].message.content))
    except Exception as e:
        logger.error(f"Multi-source problem extraction failed: {e}")
        log_pipeline_end(run_id, 'failed', {'error': str(e)})
        return {'error': str(e)}

    # Build lookup for per-problem source attribution
    post_by_source_id = {p.get('source_id'): p for p in posts.data}
    post_by_uuid = {p.get('id'): p for p in posts.data}

    problems_created = 0
    for problem in problems_data.get('problems', []):
        try:
            # Resolve source and tier from the problem's source_post_ids
            src_ids = problem.get('source_post_ids', [])
            best_tier = 3
            source_name = 'multi'
            for sid in src_ids:
                post = post_by_source_id.get(sid) or post_by_uuid.get(sid)
                if post:
                    tier = post.get('source_tier', 3)
                    if tier < best_tier:
                        best_tier = tier
                        source_name = post.get('source', 'multi')
            problem['source'] = source_name
            problem['max_source_tier'] = best_tier
            store_problem(problem)
            problems_created += 1
        except Exception as e:
            logger.error(f"Error storing problem: {e}")

    post_ids = [p['id'] for p in posts.data]
    for pid in post_ids:
        try:
            supabase.table('source_posts').update({
                'processed': True,
                'processing_type': 'problem_extraction'
            }).eq('id', pid).execute()
        except Exception as e:
            logger.error(f"Error marking post {pid} processed: {e}")

    result = {'processed': len(posts.data), 'problems_found': problems_created, 'sources': sources_seen}
    log_pipeline_end(run_id, 'completed', result)
    logger.info(f"Multi-source problem extraction complete: {problems_created} problems from {len(posts.data)} posts")
    return result


def extract_tools_multisource(hours_back: int = 48) -> dict:
    """Extract tool mentions from all sources in source_posts."""
    if not supabase or not openai_client:
        return {'error': 'Not configured'}

    run_id = log_pipeline_start('extract_tools_multisource')

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    posts = supabase.table('source_posts')\
        .select('*')\
        .gte('scraped_at', cutoff)\
        .order('score', desc=True)\
        .limit(200)\
        .execute()

    if not posts.data:
        logger.info("No source_posts found for tool extraction")
        log_pipeline_end(run_id, 'completed', {'posts_scanned': 0, 'mentions_found': 0})
        return {'posts_scanned': 0, 'mentions_found': 0, 'sources': []}

    sources_seen = list({p.get('source') for p in posts.data})
    logger.info(f"Multi-source tool extraction: {len(posts.data)} posts from {sources_seen}")

    posts_text = _format_multisource_posts(posts.data)
    tool_model = get_model('extraction')

    try:
        _t0 = time.time()
        response = routed_llm_call(
            tool_model,
            messages=[
                {"role": "system", "content": "You extract tool and product mentions. Respond only with valid JSON."},
                {"role": "user", "content": TOOL_EXTRACTION_PROMPT.format(posts=posts_text)}
            ],
            temperature=0.2,
            max_tokens=4000
        )
        log_llm_call("processor", "tool_extraction_multisource", response.model, response.usage, int((time.time() - _t0) * 1000))
        time.sleep(2)
        mentions_data = json.loads(_clean_json_response(response.choices[0].message.content))
    except Exception as e:
        logger.error(f"Multi-source tool extraction failed: {e}")
        log_pipeline_end(run_id, 'failed', {'error': str(e)})
        return {'error': str(e)}

    post_source_map = {p.get('source_id'): p.get('source', 'unknown') for p in posts.data}
    post_uuid_map = {p.get('source_id'): p.get('id') for p in posts.data}

    mentions_stored = 0
    for mention in mentions_data.get('tool_mentions', []):
        try:
            src_post_id = mention.get('source_post_id', '')
            record = {
                'tool_name': mention['tool_name'],
                'tool_name_raw': mention.get('tool_name_raw'),
                'post_id': post_uuid_map.get(src_post_id),
                'context': mention.get('context'),
                'sentiment_score': mention.get('sentiment_score', 0.0),
                'sentiment_label': mention.get('sentiment_label', 'neutral'),
                'is_recommendation': mention.get('is_recommendation', False),
                'is_complaint': mention.get('is_complaint', False),
                'alternative_mentioned': mention.get('alternative_mentioned'),
                'mentioned_at': datetime.now(timezone.utc).isoformat(),
                'source': post_source_map.get(src_post_id, 'multi'),
                'metadata': {}
            }
            supabase.table('tool_mentions').insert(record).execute()
            mentions_stored += 1
        except Exception as e:
            logger.error(f"Error storing tool mention '{mention.get('tool_name', '?')}': {e}")

    result = {'posts_scanned': len(posts.data), 'mentions_found': mentions_stored, 'sources': sources_seen}
    log_pipeline_end(run_id, 'completed', result)
    logger.info(f"Multi-source tool extraction complete: {mentions_stored} mentions from {len(posts.data)} posts")
    return result


def extract_trending_topics_multisource(hours_back: int = 48) -> dict:
    """Extract trending topics from all sources in source_posts."""
    if not supabase or not openai_client:
        return {'error': 'Not configured'}

    run_id = log_pipeline_start('extract_trending_topics_multisource')

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
    posts = supabase.table('source_posts')\
        .select('*')\
        .gte('scraped_at', cutoff)\
        .order('score', desc=True)\
        .limit(200)\
        .execute()

    if not posts.data:
        logger.info("No source_posts found for trending topics extraction")
        log_pipeline_end(run_id, 'completed', {'posts_scanned': 0, 'topics_found': 0})
        return {'posts_scanned': 0, 'topics_found': 0, 'sources': []}

    sources_seen = list({p.get('source') for p in posts.data})
    logger.info(f"Multi-source trending topics extraction: {len(posts.data)} posts from {sources_seen}")

    posts_text = _format_multisource_posts(posts.data)
    trending_model = get_model('trending_topics')

    try:
        _t0 = time.time()
        response = routed_llm_call(
            trending_model,
            messages=[
                {"role": "system", "content": "You identify interesting and culturally significant conversations in AI agent communities. Respond only with valid JSON."},
                {"role": "user", "content": TRENDING_TOPICS_PROMPT.format(posts=posts_text)}
            ],
            temperature=0.5,
            max_tokens=4000
        )
        log_llm_call("processor", "trending_topics_multisource", response.model, response.usage, int((time.time() - _t0) * 1000))
        time.sleep(2)
        topics_data = json.loads(_clean_json_response(response.choices[0].message.content))
    except Exception as e:
        logger.error(f"Multi-source trending topics extraction failed: {e}")
        log_pipeline_end(run_id, 'failed', {'error': str(e)})
        return {'error': str(e)}

    post_source_map = {p.get('source_id'): p.get('source', 'unknown') for p in posts.data}

    topics_stored = 0
    for topic in topics_data.get('topics', []):
        try:
            src_ids = topic.get('source_post_ids', [])
            topic_sources = list({post_source_map.get(sid, 'unknown') for sid in src_ids})
            record = {
                'title': topic['title'],
                'description': topic.get('description'),
                'topic_type': topic.get('topic_type', 'technical'),
                'source_post_ids': src_ids,
                'engagement_score': topic.get('engagement_score', 0.0),
                'novelty_score': topic.get('novelty_score', 0.0),
                'why_interesting': topic.get('why_interesting'),
                'source': ','.join(topic_sources) if topic_sources else 'multi',
                'metadata': {}
            }
            supabase.table('trending_topics').insert(record).execute()
            topics_stored += 1
        except Exception as e:
            logger.error(f"Error storing trending topic '{topic.get('title', '?')}': {e}")

    result = {'posts_scanned': len(posts.data), 'topics_found': topics_stored, 'sources': sources_seen}
    log_pipeline_end(run_id, 'completed', result)
    logger.info(f"Multi-source trending topics complete: {topics_stored} topics from {len(posts.data)} posts")
    return result


# ============================================================================
# Topic Evolution Tracking
# ============================================================================

TOPIC_STOP_WORDS = {'the', 'a', 'an', 'for', 'in', 'of', 'and', 'or', 'with'}


def normalize_topic_key(theme: str) -> str:
    """Normalize a cluster theme into a stable topic key."""
    key = theme.lower().strip()
    key = '_'.join(w for w in key.split() if w not in TOPIC_STOP_WORDS)
    return key[:100]


def count_mentions_for_topic(topic_key: str, days: int = 7) -> int:
    """Count how many recent problems mention this topic's keywords."""
    if not supabase:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    problems = supabase.table('problems')\
        .select('description')\
        .gte('last_seen', cutoff)\
        .execute()
    if not problems.data:
        return 0
    keywords = [w for w in topic_key.split('_') if len(w) >= 3]
    if not keywords:
        return 0
    count = 0
    for p in problems.data:
        desc = (p.get('description') or '').lower()
        if any(kw in desc for kw in keywords):
            count += 1
    return count


def avg_sentiment_for_topic(topic_key: str, days: int = 7) -> float:
    """Average sentiment score for tool mentions related to this topic."""
    if not supabase:
        return 0.0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    mentions = supabase.table('tool_mentions')\
        .select('tool_name, context, sentiment_score')\
        .gte('mentioned_at', cutoff)\
        .execute()
    if not mentions.data:
        return 0.0
    keywords = [w for w in topic_key.split('_') if len(w) >= 3]
    if not keywords:
        return 0.0
    scores = []
    for m in mentions.data:
        text = ((m.get('tool_name') or '') + ' ' + (m.get('context') or '')).lower()
        if any(kw in text for kw in keywords):
            scores.append(m.get('sentiment_score', 0) or 0)
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def unique_sources_for_topic(topic_key: str, days: int = 7) -> list:
    """List unique sources that mention this topic in recent source_posts."""
    if not supabase:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    posts = supabase.table('source_posts')\
        .select('source, title, body')\
        .gte('scraped_at', cutoff)\
        .execute()
    if not posts.data:
        return []
    keywords = [w for w in topic_key.split('_') if len(w) >= 3]
    if not keywords:
        return []
    sources = set()
    for p in posts.data:
        text = ((p.get('title') or '') + ' ' + (p.get('body') or '')).lower()
        if any(kw in text for kw in keywords):
            sources.add(p.get('source', 'unknown'))
    return list(sources)


def github_repos_for_topic(topic_key: str, days: int = 7) -> int:
    """Count GitHub repos mentioning this topic in recent source_posts."""
    if not supabase:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    posts = supabase.table('source_posts')\
        .select('title, body, tags')\
        .eq('source', 'github')\
        .gte('scraped_at', cutoff)\
        .execute()
    if not posts.data:
        return 0
    keywords = [w for w in topic_key.split('_') if len(w) >= 3]
    if not keywords:
        return 0
    count = 0
    for p in posts.data:
        text = ((p.get('title') or '') + ' ' + (p.get('body') or '')).lower()
        tags_str = ' '.join(p.get('tags') or []).lower()
        if any(kw in text or kw in tags_str for kw in keywords):
            count += 1
    return count


def detect_topic_stage(snapshots: list) -> str:
    """Determine lifecycle stage from a list of weekly snapshot dicts."""
    if len(snapshots) < 2:
        return 'emerging'

    mention_counts = [s.get('mentions', 0) for s in snapshots]
    avg_mentions = sum(mention_counts) / len(mention_counts) if mention_counts else 0
    recent = mention_counts[-1] if mention_counts else 0

    # DECLINING: last 3 show consistent drop AND recent < 50% of average
    if len(mention_counts) >= 3:
        last3 = mention_counts[-3:]
        if all(last3[i] >= last3[i + 1] for i in range(len(last3) - 1)) and avg_mentions > 0 and recent < avg_mentions * 0.5:
            return 'declining'

    # MATURE: last 4 low variance AND recent mentions > 5
    if len(mention_counts) >= 4:
        last4 = mention_counts[-4:]
        spread = max(last4) - min(last4)
        avg4 = sum(last4) / 4
        if avg4 > 0 and spread < avg4 * 0.3 and recent > 5:
            return 'mature'

    recent_github = snapshots[-1].get('github_repos', 0) if snapshots else 0
    recent_source_count = snapshots[-1].get('source_count', 0) if snapshots else 0

    # CONSOLIDATING: recent github > 0 AND recent mentions < average AND recent sources >= 2
    if recent_github > 0 and avg_mentions > 0 and recent < avg_mentions and recent_source_count >= 2:
        return 'consolidating'

    # BUILDING: any github repos in recent snapshots
    if any(s.get('github_repos', 0) > 0 for s in snapshots[-3:]):
        return 'building'

    # DEBATING: recent mentions > average AND recent sources >= 2
    if avg_mentions > 0 and recent > avg_mentions and recent_source_count >= 2:
        return 'debating'

    return 'emerging'


def update_topic_evolution() -> dict:
    """Update topic evolution tracking from problem_clusters data."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    clusters = supabase.table('problem_clusters')\
        .select('*')\
        .order('opportunity_score', desc=True)\
        .limit(30)\
        .execute()

    if not clusters.data:
        logger.info("No clusters found for topic evolution")
        return {'topics_updated': 0}

    topics_updated = 0
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    for cluster in clusters.data:
        theme = cluster.get('theme', '')
        if not theme:
            continue

        topic_key = normalize_topic_key(theme)
        if not topic_key:
            continue

        try:
            mentions = count_mentions_for_topic(topic_key)
            sentiment = avg_sentiment_for_topic(topic_key)
            sources = unique_sources_for_topic(topic_key)
            github = github_repos_for_topic(topic_key)

            snapshot = {
                'date': today,
                'mentions': mentions,
                'sentiment': round(sentiment, 3),
                'sources': sources,
                'source_count': len(sources),
                'github_repos': github
            }

            existing = supabase.table('topic_evolution')\
                .select('id, snapshots, current_stage')\
                .eq('topic_key', topic_key)\
                .limit(1)\
                .execute()

            if existing.data:
                row = existing.data[0]
                snapshots = row.get('snapshots') or []
                snapshots.append(snapshot)
                snapshots = snapshots[-12:]

                new_stage = detect_topic_stage(snapshots)
                update_data = {
                    'snapshots': snapshots,
                    'current_stage': new_stage,
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }
                if new_stage != row.get('current_stage'):
                    update_data['stage_changed_at'] = datetime.now(timezone.utc).isoformat()

                supabase.table('topic_evolution')\
                    .update(update_data)\
                    .eq('id', row['id'])\
                    .execute()
            else:
                new_stage = detect_topic_stage([snapshot])
                supabase.table('topic_evolution').insert({
                    'topic_key': topic_key,
                    'snapshots': [snapshot],
                    'current_stage': new_stage,
                    'first_seen': datetime.now(timezone.utc).isoformat(),
                    'last_updated': datetime.now(timezone.utc).isoformat()
                }).execute()

            topics_updated += 1

        except Exception as e:
            logger.error(f"Error updating topic evolution for '{topic_key}': {e}")

    logger.info(f"Topic evolution update complete: {topics_updated} topics")
    return {'topics_updated': topics_updated}


# ============================================================================
# Newsletter (Data Prep + Publish — writing delegated to Newsletter agent)
# ============================================================================

def get_excluded_opportunity_ids(editions_back: int = 2) -> set:
    """Get IDs of top opportunities from recent newsletters to avoid repeating them."""
    if not supabase:
        return set()
    try:
        recent = supabase.table('newsletters')\
            .select('data_snapshot')\
            .eq('status', 'published')\
            .order('edition_number', desc=True)\
            .limit(editions_back)\
            .execute()
        excluded = set()
        for nl in (recent.data or []):
            snapshot = nl.get('data_snapshot') or {}
            for opp in (snapshot.get('section_a_opportunities') or [])[:2]:
                if opp.get('id'):
                    excluded.add(opp['id'])
        return excluded
    except Exception as e:
        logger.error(f"get_excluded_opportunity_ids failed: {e}")
        return set()


def get_previously_featured_titles(editions_back: int = 4) -> set:
    """Get title fragments from recent newsletters for deduplication."""
    if not supabase:
        return set()
    try:
        recent = supabase.table('newsletters')\
            .select('data_snapshot')\
            .eq('status', 'published')\
            .order('edition_number', desc=True)\
            .limit(editions_back)\
            .execute()
        titles = set()
        for nl in (recent.data or []):
            snapshot = nl.get('data_snapshot') or {}
            for section_key in ('section_a_opportunities', 'section_b_emerging', 'section_c_curious'):
                for item in (snapshot.get(section_key) or []):
                    title = item.get('title') or item.get('description') or item.get('theme') or ''
                    if title:
                        titles.add(title[:50].lower())
        return titles
    except Exception as e:
        logger.error(f"get_previously_featured_titles failed: {e}")
        return set()


def get_recent_newsletter_themes(editions_back: int = 3) -> list[str]:
    """Get primary_theme values from recent newsletters for diversity enforcement."""
    if not supabase:
        return []
    try:
        recent = supabase.table('newsletters')\
            .select('primary_theme, edition_number')\
            .eq('status', 'published')\
            .not_.is_('primary_theme', 'null')\
            .order('edition_number', desc=True)\
            .limit(editions_back)\
            .execute()
        themes = []
        for row in (recent.data or []):
            theme = row.get('primary_theme', '')
            if theme and theme.strip():
                themes.append(theme.strip().lower())
        return themes
    except Exception as e:
        logger.warning(f"get_recent_newsletter_themes failed: {e}")
        return []


def _fetch_latest_spotlight_for_newsletter(edition_number: int) -> dict | None:
    """Fetch the latest completed spotlight for the newsletter, with a 90-minute timeout check.

    If the Research Agent hasn't completed within 90 minutes of the trigger,
    returns None so the newsletter proceeds without the Spotlight section.
    """
    if not supabase:
        return None

    try:
        result = supabase.table('spotlight_history')\
            .select('*')\
            .gte('issue_number', edition_number)\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()

        if not result.data:
            logger.info(f"No spotlight for edition #{edition_number} — newsletter will skip Spotlight")
            return None

        spotlight = result.data[0]
        created_at = spotlight.get('created_at', '')
        if created_at:
            if created_at.endswith('Z'):
                created_at = created_at.replace('Z', '+00:00')
            try:
                created_dt = datetime.fromisoformat(created_at)
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                age_hours = (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600
                if age_hours > 168:
                    logger.info(f"Latest spotlight is {age_hours:.0f}h old — too stale, skipping")
                    return None
            except (ValueError, TypeError) as e:
                logger.warning(f"Spotlight age parse skipped: {e}")

        queued_item = supabase.table('research_queue')\
            .select('status, started_at')\
            .eq('status', 'in_progress')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()

        if queued_item.data:
            started_at = queued_item.data[0].get('started_at', '')
            if started_at:
                if started_at.endswith('Z'):
                    started_at = started_at.replace('Z', '+00:00')
                try:
                    started_dt = datetime.fromisoformat(started_at)
                    if started_dt.tzinfo is None:
                        started_dt = started_dt.replace(tzinfo=timezone.utc)
                    elapsed_min = (datetime.now(timezone.utc) - started_dt).total_seconds() / 60
                    if elapsed_min > 90:
                        logger.warning(f"Research Agent in_progress for {elapsed_min:.0f}m (>90m timeout) — proceeding without Spotlight")
                        return None
                except (ValueError, TypeError) as e:
                    logger.warning(f"Research queue start_at parse skipped: {e}")

        prediction = (spotlight.get('prediction') or '').strip()
        has_prediction = bool(prediction) and 'no prediction' not in prediction.lower()

        logger.info(f"Spotlight found: '{spotlight.get('topic_name', '?')}' (mode={spotlight.get('mode', '?')}, prediction={'yes' if has_prediction else 'NONE'})")
        result = {
            'topic_name': spotlight.get('topic_name', ''),
            'mode': spotlight.get('mode', 'spotlight'),
            'thesis': spotlight.get('thesis', ''),
            'evidence': spotlight.get('evidence', ''),
            'counter_argument': spotlight.get('counter_argument', ''),
            'builder_implications': spotlight.get('builder_implications', ''),
            'sources_used': spotlight.get('sources_used', []),
            'has_prediction': has_prediction,
        }
        if has_prediction:
            result['prediction'] = prediction
        # Omit 'prediction' key entirely when empty — prevents LLM from echoing placeholder text
        return result

    except Exception as e:
        logger.warning(f"Failed to fetch spotlight for newsletter: {e}")
        return None


def prepare_newsletter_data(edition_override: int = None) -> dict:
    """Gather data for the Newsletter agent and create a write_newsletter task."""
    if not supabase:
        logger.error("Supabase not configured")
        return {'error': 'Not configured'}

    # Guard: skip if a write_newsletter task already exists this week AND produced a draft (unless edition_override)
    if not edition_override:
        # Use Friday-based window: newsletters draft on Friday, so the cycle is Friday-to-Thursday
        now_utc = datetime.now(timezone.utc)
        days_since_friday = (now_utc.weekday() - 4) % 7  # Friday=4
        week_start = (now_utc - timedelta(days=days_since_friday)).replace(hour=0, minute=0, second=0, microsecond=0)
        existing = supabase.table('agent_tasks').select('id,status').eq('task_type', 'write_newsletter').gte('created_at', week_start.isoformat()).execute()
        if existing.data:
            # Check if any task is still pending/in-progress (don't duplicate)
            active = [t for t in existing.data if t.get('status') in ('pending', 'in_progress')]
            if active:
                logger.info(f"[PIPELINE] Newsletter task in progress this week (task {active[0]['id']}), skipping")
                return {'status': 'already_exists', 'task_id': active[0]['id']}
            # Check if a newsletter draft was actually created this week
            draft = supabase.table('newsletters').select('id').gte('created_at', week_start.isoformat()).execute()
            if draft.data:
                logger.info(f"[PIPELINE] Newsletter draft already exists this week (newsletter {draft.data[0]['id']}), skipping")
                return {'status': 'already_exists', 'task_id': existing.data[0]['id']}
            # Tasks completed but no draft — allow retry
            logger.warning(f"[PIPELINE] Found {len(existing.data)} completed newsletter task(s) this week but no draft in newsletters table — allowing retry")

    run_id = log_pipeline_start('prepare_newsletter')
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    try:
        # ── Bootstrap: backfill primary_theme for old newsletters ──
        try:
            null_themes = supabase.table('newsletters')\
                .select('id, title')\
                .is_('primary_theme', 'null')\
                .order('edition_number', desc=True)\
                .limit(5)\
                .execute()
            for nl in (null_themes.data or []):
                if nl.get('title'):
                    supabase.table('newsletters').update({
                        'primary_theme': nl['title'].lower().strip()[:100]
                    }).eq('id', nl['id']).execute()
            if null_themes.data:
                logger.info(f"Backfilled primary_theme for {len(null_themes.data)} newsletter(s)")
        except Exception as e:
            logger.warning(f"Theme backfill failed (non-critical): {e}")

        # ── Theme diversity: compute avoided theme words ──
        _theme_stopwords = {'the', 'and', 'for', 'in', 'of', 'a', 'an', 'is', 'to', 'ai', 'agent', 'agents'}
        avoided_themes = get_recent_newsletter_themes(3)
        avoided_theme_words = set()
        for theme in avoided_themes:
            avoided_theme_words.update(w for w in theme.split() if w not in _theme_stopwords)

        # ── Section A: Established Opportunities (freshness-aware) ──
        opps = supabase.table('opportunities')\
            .select('*')\
            .eq('status', 'draft')\
            .gte('confidence_score', 0.3)\
            .execute()
        opps_raw = opps.data or []

        # Compute effective_score with staleness decay + theme diversity penalty
        for opp in opps_raw:
            appearances = opp.get('newsletter_appearances', 0) or 0
            effective_score = opp.get('confidence_score', 0) * (0.7 ** appearances)

            last_featured = opp.get('last_featured_at')
            last_reviewed = opp.get('last_reviewed_at')
            if last_featured and last_reviewed and last_reviewed > last_featured:
                effective_score *= 1.3

            # Theme diversity penalty: demote opportunities matching recent themes
            if avoided_theme_words:
                opp_title = opp.get('title', '').lower()
                opp_words = set(opp_title.split()) - _theme_stopwords
                theme_overlap = opp_words & avoided_theme_words
                if len(theme_overlap) >= 2:
                    effective_score *= 0.3
                    logger.info(f"Opp theme penalty (heavy): '{opp_title[:40]}' overlaps {theme_overlap}")
                elif len(theme_overlap) == 1:
                    effective_score *= 0.7

            opp['effective_score'] = round(effective_score, 4)
            opp['appearances'] = appearances
            opp['is_returning'] = appearances > 0
            opp['last_edition_featured'] = last_featured

        opps_raw.sort(key=lambda x: x.get('effective_score', 0), reverse=True)

        excluded_ids = get_excluded_opportunity_ids(2)
        never_featured = [o for o in opps_raw if (o.get('newsletter_appearances', 0) or 0) == 0]
        returning_eligible = [
            o for o in opps_raw
            if (o.get('newsletter_appearances', 0) or 0) > 0
            and o.get('id') not in excluded_ids
            and o.get('last_reviewed_at') and o.get('last_featured_at')
            and o['last_reviewed_at'] > o['last_featured_at']
        ]

        opportunities_data = never_featured[:3] + returning_eligible[:2]
        opportunities_data.sort(key=lambda x: x.get('effective_score', 0), reverse=True)
        opportunities_data = opportunities_data[:5]

        # ── Section B: Emerging Signals ──
        # Recent problems with low frequency (early signals)
        emerging_problems = supabase.table('problems')\
            .select('*')\
            .gte('first_seen', week_ago)\
            .lt('frequency_count', 5)\
            .order('first_seen', desc=True)\
            .limit(10)\
            .execute()
        emerging_problems_data = emerging_problems.data or []

        # Recent high-potential clusters
        emerging_clusters = supabase.table('problem_clusters')\
            .select('*')\
            .gte('created_at', week_ago)\
            .gte('opportunity_score', 0.3)\
            .order('opportunity_score', desc=True)\
            .limit(10)\
            .execute()
        emerging_clusters_data = emerging_clusters.data or []

        # Combine into emerging signals list (deduplicated by theme)
        seen_themes = set()
        emerging_signals = []
        for cluster in emerging_clusters_data:
            theme = cluster.get('theme', '')
            if theme not in seen_themes:
                seen_themes.add(theme)
                emerging_signals.append({
                    'type': 'cluster',
                    'theme': theme,
                    'description': cluster.get('description'),
                    'opportunity_score': cluster.get('opportunity_score'),
                    'problem_ids': cluster.get('problem_ids', []),
                    'market_validation': cluster.get('market_validation', {})
                })
        for problem in emerging_problems_data:
            desc = problem.get('description', '')
            if desc not in seen_themes:
                seen_themes.add(desc)
                meta = problem.get('metadata', {})
                tier = meta.get('max_source_tier', 3)
                tier_label = {1: 'AUTHORITY', 2: 'CURATED'}.get(tier, 'COMMUNITY')
                # Look up source names from source_post_ids
                source_names = []
                post_ids = problem.get('source_post_ids') or []
                if post_ids:
                    try:
                        src_rows = supabase.table('source_posts')\
                            .select('source')\
                            .in_('id', post_ids[:5])\
                            .execute()
                        source_names = list({r['source'] for r in (src_rows.data or [])})
                    except Exception:
                        pass
                emerging_signals.append({
                    'type': 'problem',
                    'theme': desc,
                    'description': desc,
                    'category': problem.get('category'),
                    'signal_phrases': problem.get('signal_phrases', []),
                    'frequency_count': problem.get('frequency_count', 1),
                    'metadata': meta,
                    'source_tier': tier,
                    'source_tier_label': tier_label,
                    'source_names': source_names,
                })
        emerging_signals = emerging_signals[:10]

        # Filter Section B against previously featured titles
        previously_featured = get_previously_featured_titles(4)
        if previously_featured:
            emerging_signals = [
                s for s in emerging_signals
                if (s.get('description') or s.get('theme') or '')[:50].lower() not in previously_featured
            ]

        # ── Section C: Curious Corner (trending topics) ──
        curious_topics = supabase.table('trending_topics')\
            .select('*')\
            .gte('extracted_at', week_ago)\
            .eq('featured_in_newsletter', False)\
            .order('novelty_score', desc=True)\
            .limit(8)\
            .execute()
        curious_data = curious_topics.data or []

        # ── Existing data: tools, warnings, clusters ──
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

        # Recent problem clusters (last 7 days) with theme diversity penalty
        clusters = supabase.table('problem_clusters')\
            .select('*')\
            .gte('created_at', week_ago)\
            .order('opportunity_score', desc=True)\
            .limit(10)\
            .execute()
        clusters_data = clusters.data or []

        # Apply theme diversity penalty to clusters (tiered: 1 word = 0.7x, 2+ words = 0.4x)
        if avoided_theme_words and clusters_data:
            for cluster in clusters_data:
                cluster_theme = (cluster.get('theme') or '').lower()
                cluster_words = set(cluster_theme.split()) - _theme_stopwords
                theme_overlap = cluster_words & avoided_theme_words
                original = cluster.get('opportunity_score', 0)
                if len(theme_overlap) >= 2:
                    cluster['opportunity_score'] = round(original * 0.4, 4)
                    logger.info(f"Cluster theme penalty (heavy): '{cluster_theme[:40]}' overlaps {theme_overlap}, score {original}->{cluster['opportunity_score']}")
                elif len(theme_overlap) == 1:
                    cluster['opportunity_score'] = round(original * 0.7, 4)
                    logger.info(f"Cluster theme penalty (light): '{cluster_theme[:40]}' overlaps {theme_overlap}, score {original}->{cluster['opportunity_score']}")
            clusters_data.sort(key=lambda c: c.get('opportunity_score', 0), reverse=True)

        # ── Section D: Prediction Tracker ──
        # Lifecycle: update prediction statuses based on target_date vs today
        today_str = datetime.now(timezone.utc).date().isoformat()
        today_date = datetime.now(timezone.utc).date()
        try:
            lifecycle_preds = supabase.table('predictions')\
                .select('id, target_date, status')\
                .in_('status', ['open', 'at_risk'])\
                .not_.is_('target_date', 'null')\
                .execute()
            failed_count = 0
            at_risk_count = 0
            for pred in (lifecycle_preds.data or []):
                target = pred.get('target_date')
                if not target:
                    continue
                from datetime import date as date_type
                if isinstance(target, str):
                    target_d = date_type.fromisoformat(target)
                else:
                    target_d = target
                days_remaining = (target_d - today_date).days
                if days_remaining < 0:
                    # Past due → failed
                    supabase.table('predictions').update({
                        'status': 'failed',
                        'resolution_notes': (
                            f"Auto-failed: target_date {target} passed "
                            f"with no confirming evidence (today={today_str})"
                        ),
                        'resolved_at': datetime.now(timezone.utc).isoformat(),
                    }).eq('id', pred['id']).execute()
                    failed_count += 1
                elif days_remaining <= 14 and pred.get('status') != 'at_risk':
                    # Due within 14 days → at_risk
                    supabase.table('predictions').update({
                        'status': 'at_risk',
                    }).eq('id', pred['id']).execute()
                    at_risk_count += 1
            if failed_count or at_risk_count:
                logger.info(
                    f"Prediction lifecycle: {failed_count} → failed, "
                    f"{at_risk_count} → at_risk"
                )
        except Exception as e:
            logger.warning(f"Prediction lifecycle update failed: {e}")

        # Fetch predictions for newsletter (include failed so LLM can write resolutions)
        predictions_result = supabase.table('predictions')\
            .select('*')\
            .in_('status', ['open', 'at_risk', 'failed', 'confirmed', 'refuted'])\
            .order('status', desc=False)\
            .order('created_at', desc=True)\
            .limit(10)\
            .execute()
        predictions_data = predictions_result.data or []

        # Add emoji_status for the newsletter LLM
        _STATUS_EMOJI = {
            'open': '🟢 Active',
            'at_risk': '🟡 At Risk',
            'failed': '🔴 Failed',
            'confirmed': '✅ Confirmed',
            'refuted': '🔴 Failed',
        }
        stale_prediction_ids = []
        for pred in predictions_data:
            pred['emoji_status'] = _STATUS_EMOJI.get(pred.get('status', 'open'), '🟢 Active')
            if pred.get('status') == 'failed':
                stale_prediction_ids.append(pred.get('id'))

        if stale_prediction_ids:
            logger.info(f"{len(stale_prediction_ids)} failed prediction(s) flagged as stale for newsletter")

        # ── Thought Leader Content ──
        tl_posts = supabase.table('source_posts')\
            .select('*')\
            .like('source', 'thought_leader_%')\
            .gte('scraped_at', week_ago)\
            .order('scraped_at', desc=True)\
            .limit(20)\
            .execute()
        thought_leader_data = tl_posts.data or []

        # ── Topic Evolution ──
        topic_evolution = supabase.table('topic_evolution')\
            .select('*')\
            .order('last_updated', desc=True)\
            .limit(15)\
            .execute()
        topic_evolution_data = topic_evolution.data or []

        # ── Stats ──
        posts_count_result = supabase.table('moltbook_posts')\
            .select('id', count='exact')\
            .gte('scraped_at', week_ago)\
            .execute()
        posts_count = posts_count_result.count if posts_count_result.count else 0

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

        # Source breakdown (last 7 days)
        source_stats = {}
        for source_name in ['moltbook', 'hackernews', 'github']:
            src_count = supabase.table('source_posts')\
                .select('id', count='exact')\
                .eq('source', source_name)\
                .gte('scraped_at', week_ago)\
                .execute()
            source_stats[source_name] = src_count.count or 0

        rss_count = supabase.table('source_posts')\
            .select('id', count='exact')\
            .like('source', 'rss_%')\
            .gte('scraped_at', week_ago)\
            .execute()
        source_stats['rss_premium'] = rss_count.count or 0

        tl_count = supabase.table('source_posts')\
            .select('id', count='exact')\
            .like('source', 'thought_leader_%')\
            .gte('scraped_at', week_ago)\
            .execute()
        source_stats['thought_leaders'] = tl_count.count or 0

        hn_posts = source_stats.get('hackernews', 0)
        gh_repos = source_stats.get('github', 0)
        mb_posts = source_stats.get('moltbook', 0)

        # Topic stage summary
        topic_stages = {}
        for topic in topic_evolution_data:
            stage = topic.get('current_stage', 'unknown')
            topic_stages[stage] = topic_stages.get(stage, 0) + 1

        # ── Radar: emerging topics not already in Signals ──
        signals_themes = {(s.get('theme') or '').lower() for s in emerging_signals}
        radar_candidates = [
            t for t in topic_evolution_data
            if t.get('current_stage') == 'emerging'
            and t.get('topic_key', '').replace('_', ' ') not in signals_themes
        ]
        radar_candidates.sort(
            key=lambda t: (t.get('snapshots') or [{}])[-1].get('mentions', 0),
            reverse=True
        )
        if len(radar_candidates) < 3:
            debating_fill = [
                t for t in topic_evolution_data
                if t.get('current_stage') == 'debating'
                and t.get('topic_key', '').replace('_', ' ') not in signals_themes
                and t not in radar_candidates
            ]
            radar_candidates.extend(debating_fill)
        radar_topics = radar_candidates[:4]

        # Prediction accuracy stats
        confirmed_count = sum(1 for p in predictions_data if p.get('status') == 'confirmed')
        faded_count = sum(1 for p in predictions_data if p.get('status') == 'faded')
        active_preds = sum(1 for p in predictions_data if p.get('status') == 'active')
        resolved = confirmed_count + faded_count
        prediction_accuracy = round(confirmed_count / resolved * 100) if resolved > 0 else None

        # Get next edition number (or use override for reprocessing)
        if edition_override:
            edition_number = edition_override
            logger.info(f"[PIPELINE] Using edition override: #{edition_number}")
        else:
            try:
                edition_result = supabase.rpc('next_newsletter_edition').execute()
                edition_number = edition_result.data if edition_result.data else 1
            except Exception:
                # Fallback: count existing newsletters + 1
                existing = supabase.table('newsletters')\
                    .select('id', count='exact')\
                    .execute()
                edition_number = (existing.count or 0) + 1

        # ── Premium Source Posts (Tier 1 & 2 RSS for attribution) ──
        # Fetch wider pool, then cap per-source to avoid arXiv/Cointelegraph floods
        _MAX_PER_SOURCE = 3
        premium_pool = supabase.table('source_posts')\
            .select('source, source_tier, title, body, source_url, scraped_at')\
            .in_('source_tier', [1, 2])\
            .gte('scraped_at', week_ago)\
            .order('scraped_at', desc=True)\
            .limit(100)\
            .execute()
        # Apply per-source cap: keep at most _MAX_PER_SOURCE from any single source
        _source_counts: dict[str, int] = {}
        capped_posts = []
        for p in (premium_pool.data or []):
            src = p.get('source', '')
            _source_counts[src] = _source_counts.get(src, 0) + 1
            if _source_counts[src] <= _MAX_PER_SOURCE:
                capped_posts.append(p)
        # Take top 20 from the diversified pool (already sorted by scraped_at desc)
        premium_posts_data = capped_posts[:20]
        # Monitor: alert if any source exceeds 5 slots (cap should prevent >3)
        _final_counts: dict[str, int] = {}
        for p in premium_posts_data:
            s = p.get('source', '')
            _final_counts[s] = _final_counts.get(s, 0) + 1
        for s, cnt in _final_counts.items():
            if cnt > 5:
                logger.error(f"[ALERT] premium_source_posts cap failure: {s} has {cnt} slots (max expected: 3)")

        _source_display_names = {
            'a16z': 'a16z', 'hbr_tech': 'Harvard Business Review',
            'mit_tech_review': 'MIT Technology Review', 'andrew_ng': 'Andrew Ng (The Batch)',
            'simon_willison': 'Simon Willison', 'latent_space': 'Latent Space',
            'swyx': 'swyx', 'langchain_blog': 'LangChain Blog',
            'ethan_mollick': 'Ethan Mollick', 'bitcoin_magazine': 'Bitcoin Magazine',
            'coindesk': 'CoinDesk', 'tldr_ai': 'TLDR AI', 'tldr_founders': 'TLDR Founders',
            'bens_bites': "Ben's Bites",
            'arxiv_cs_ai': 'arXiv AI', 'arxiv_cs_cl': 'arXiv NLP',
            'arxiv_cs_cr': 'arXiv Crypto', 'arxiv_cs_ma': 'arXiv Multi-Agent',
            'alignment_forum': 'Alignment Forum',
            'techcrunch_ai': 'TechCrunch AI', 'the_verge_ai': 'The Verge AI',
            'wired_ai': 'Wired AI', 'decrypt': 'Decrypt', 'unchained': 'Unchained',
            'cointelegraph': 'Cointelegraph', 'openai_blog': 'OpenAI Blog',
            'replit_blog': 'Replit Blog', 'vercel_blog': 'Vercel Blog',
            'huggingface_blog': 'Hugging Face Blog', 'sequoia_blog': 'Sequoia',
            'cb_insights': 'CB Insights', 'chainalysis': 'Chainalysis',
            'messari': 'Messari', 'citrini': 'Citrini',
            'bis_speeches': 'BIS Speeches', 'fsb_publications': 'FSB',
        }
        premium_source_posts = []
        for p in premium_posts_data:
            src = p.get('source', '')
            # Resolve human-readable source name
            display_name = src
            if src.startswith('rss_'):
                feed_key = src[4:]
                display_name = _source_display_names.get(feed_key, feed_key.replace('_', ' ').title())
            elif src.startswith('thought_leader_'):
                display_name = src[15:].replace('_', ' ').title()
            tier_label = {1: 'AUTHORITY', 2: 'CURATED'}.get(
                p.get('source_tier', 3), 'COMMUNITY'
            )
            premium_source_posts.append({
                'source': src,
                'source_display': display_name,
                'tier': p.get('source_tier'),
                'tier_label': tier_label,
                'title': p.get('title', ''),
                'summary': (p.get('body') or '')[:300],
                'url': p.get('source_url', ''),
            })

        # Build input_data for the Newsletter agent
        input_data = {
            'edition_number': edition_number,
            'section_a_opportunities': opportunities_data,
            'section_b_emerging': emerging_signals,
            'section_c_curious': curious_data,
            'predictions': predictions_data,
            'trending_tools': tools_data,
            'tool_warnings': warnings_data,
            'clusters': clusters_data,
            'stats': {
                'posts_count': posts_count,
                'problems_count': problems_count,
                'tools_count': tools_count,
                'new_opps_count': new_opps_count,
                'emerging_signals_count': len(emerging_signals),
                'trending_topics_count': len(curious_data),
                'hackernews_posts': hn_posts,
                'github_repos': gh_repos,
                'moltbook_posts': mb_posts,
                'active_predictions': active_preds,
                'prediction_accuracy': prediction_accuracy,
                'source_breakdown': source_stats,
                'total_posts_all_sources': sum(source_stats.values()),
                'topic_stages': topic_stages,
            },
            'thought_leader_content': thought_leader_data,
            'premium_source_posts': premium_source_posts,
            'topic_evolution': topic_evolution_data,
            'radar_topics': radar_topics,
            'spotlight': _fetch_latest_spotlight_for_newsletter(edition_number),
            'stale_prediction_ids': stale_prediction_ids,
            'freshness_rules': {
                'excluded_opportunity_ids': [str(eid) for eid in excluded_ids],
                'max_returning_items_section_a': 2,
                'min_new_items_section_a': 1,
                'section_b_new_only': True,
                'section_c_new_only': True,
                'returning_items_require_new_angle': True
            },
            'avoided_themes': get_recent_newsletter_themes(3),
        }

        # Analyst insights from latest completed analysis run
        latest_analysis = supabase.table('analysis_runs')\
            .select('key_findings, analyst_notes, metadata')\
            .eq('status', 'completed')\
            .order('completed_at', desc=True)\
            .limit(1)\
            .execute()
        if latest_analysis.data:
            analysis = latest_analysis.data[0]
            theses = (analysis.get('metadata') or {}).get('insights', [])

            # Filter analyst theses that overlap with recently used themes
            if avoided_theme_words and theses:
                filtered_theses = []
                for thesis in theses:
                    thesis_words = set(thesis.lower().split()) - _theme_stopwords
                    if len(thesis_words & avoided_theme_words) < 2:
                        filtered_theses.append(thesis)
                    else:
                        logger.info(f"Filtered analyst thesis (theme overlap): '{thesis[:60]}'")
                theses = filtered_theses or theses[:1]  # Keep at least 1 if all filtered

            input_data['analyst_insights'] = {
                'key_findings': analysis.get('key_findings'),
                'analyst_notes': analysis.get('analyst_notes'),
                'theses': theses
            }

        # ── Narrative Context: editorial history for continuity ──
        try:
            recent_editions = supabase.table('newsletters')\
                .select('edition_number, title, title_impact, primary_theme, content_markdown_impact, content_markdown')\
                .eq('status', 'published')\
                .order('edition_number', desc=True)\
                .limit(8)\
                .execute()
            previous_editions = []
            for i, ed in enumerate(recent_editions.data or []):
                # Use impact title/content if available, fall back to standard
                title = ed.get('title_impact') or ed.get('title') or ''
                content = ed.get('content_markdown_impact') or ed.get('content_markdown') or ''
                previous_editions.append({
                    'edition_number': ed.get('edition_number'),
                    'title': title,
                    'primary_theme': ed.get('primary_theme') or '',
                    'opening_excerpt': content[:300],
                    'weeks_ago': i + 1,
                })
            # Oldest first so the LLM reads the arc chronologically
            previous_editions.reverse()
            # Recent spotlights (last 4 editions) for cooldown awareness
            recent_spotlights = []
            try:
                spotlights = supabase.table('spotlight_history')\
                    .select('topic_name, issue_number')\
                    .order('created_at', desc=True)\
                    .limit(4)\
                    .execute()
                recent_spotlights = [
                    s.get('topic_name', '') for s in (spotlights.data or [])
                    if s.get('topic_name')
                ]
            except Exception as e:
                logger.warning(f"Recent spotlights fetch failed (non-critical): {e}")

            if previous_editions or recent_spotlights:
                input_data['narrative_context'] = {
                    'previous_editions': previous_editions,
                    'recent_spotlights': recent_spotlights,
                    'instruction': (
                        'Use this context to build narrative continuity. '
                        'Reference previous themes briefly ("Last week we explored X. '
                        'This week, something shifted:"). Avoid repeating the same lead '
                        'angle as recent editions. Evolve the story — if you covered the '
                        'trust problem before, this week cover what changed about it or '
                        'move to a different facet of the agent economy. '
                        'Topics in recent_spotlights were deep-dived in recent editions — '
                        'reference them as previously covered rather than introducing them as new.'
                    ),
                }
                logger.info(f"Narrative context: {len(previous_editions)} edition(s), {len(recent_spotlights)} spotlight(s)")
        except Exception as e:
            logger.warning(f"Narrative context assembly failed (non-critical): {e}")

        # Create agent_task for the Newsletter agent
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
                'emerging_signals': len(emerging_signals),
                'curious_topics': len(curious_data),
                'predictions': len(predictions_data),
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


def create_predictions_from_newsletter(newsletter_id: str) -> dict:
    """Create trackable predictions from a published newsletter."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    try:
        nl = supabase.table('newsletters').select('*').eq('id', newsletter_id).single().execute()
        if not nl.data:
            return {'error': 'Newsletter not found'}

        data = nl.data.get('data_snapshot') or {}
        edition = nl.data.get('edition_number')
        created = 0

        for opp in (data.get('section_a_opportunities') or [])[:5]:
            try:
                conf = opp.get('confidence_score', 0.5)
                record = {
                    'prediction_type': 'opportunity',
                    'title': opp.get('title', 'Unknown'),
                    'description': (opp.get('description') or '')[:500],
                    'initial_confidence': conf,
                    'newsletter_edition': edition,
                    'opportunity_id': opp.get('id'),
                    'status': 'active',
                    'current_score': conf,
                    'tracking_history': json.dumps([{
                        'date': datetime.now(timezone.utc).isoformat(),
                        'event': 'created',
                        'confidence': conf,
                        'notes': f'Featured in edition #{edition}'
                    }], default=str)
                }
                target = extract_target_date(opp.get('description', ''))
                if target:
                    record['target_date'] = target.isoformat()
                supabase.table('predictions').upsert(
                    record, on_conflict='opportunity_id'
                ).execute()
                created += 1
            except Exception as e:
                logger.error(f"Failed to upsert opportunity prediction: {e}")

        for signal in (data.get('section_b_emerging') or [])[:4]:
            try:
                supabase.table('predictions').insert({
                    'prediction_type': 'emerging_signal',
                    'title': (signal.get('description') or 'Unknown signal')[:100],
                    'description': json.dumps(signal.get('signal_phrases', []), default=str)[:500],
                    'initial_confidence': 0.3,
                    'newsletter_edition': edition,
                    'cluster_id': signal.get('cluster_id'),
                    'status': 'active',
                    'current_score': 0.3,
                    'tracking_history': json.dumps([{
                        'date': datetime.now(timezone.utc).isoformat(),
                        'event': 'created',
                        'confidence': 0.3,
                        'notes': f'Emerging signal in edition #{edition}'
                    }], default=str)
                }).execute()
                created += 1
            except Exception as e:
                logger.error(f"Failed to insert emerging signal prediction: {e}")

        logger.info(f"Created {created} predictions from newsletter #{edition}")
        return {'predictions_created': created}

    except Exception as e:
        logger.error(f"Prediction creation failed: {e}")
        return {'error': str(e)}


def verify_briefing_references(newsletter: dict) -> dict:
    """Cross-check newsletter content against its source data_snapshot.

    Extracts named entities (GitHub repos, tool names, specific numbers) from
    the newsletter text and verifies each one traces back to the input data.
    Returns a dict with 'ok' bool, 'warnings' list, and 'unverified' list.
    """
    content = (newsletter.get('content_markdown') or '') + ' ' + (
        newsletter.get('content_markdown_impact') or '')
    snapshot = newsletter.get('data_snapshot') or newsletter.get('input_data') or {}

    if not content.strip() or not snapshot:
        return {'ok': True, 'warnings': [], 'unverified': [],
                'reason': 'No content or snapshot to verify'}

    # ── Build a corpus of known names from the snapshot ──
    known_names: set[str] = set()

    def _collect_names(obj, depth=0):
        """Recursively harvest string values likely to be entity names."""
        if depth > 6:
            return
        if isinstance(obj, str):
            cleaned = obj.strip().lower()
            if 3 <= len(cleaned) <= 120:
                known_names.add(cleaned)
                # Also add last path segment for URLs / repo paths
                if '/' in cleaned:
                    known_names.add(cleaned.rsplit('/', 1)[-1])
        elif isinstance(obj, dict):
            for key in ('title', 'name', 'tool_name', 'theme', 'description',
                        'repo', 'url', 'source', 'signal_phrases', 'topic',
                        'category', 'author', 'key_findings', 'analyst_notes'):
                val = obj.get(key)
                if val:
                    if isinstance(val, list):
                        for item in val:
                            _collect_names(item, depth + 1)
                    else:
                        _collect_names(val, depth + 1)
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    _collect_names(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                _collect_names(item, depth + 1)

    _collect_names(snapshot)

    warnings = []
    unverified = []

    # ── Check 1: GitHub-style repo references (org/repo) ──
    gh_refs = set(re.findall(r'(?:github\.com/)?([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)', content))
    for ref in gh_refs:
        ref_lower = ref.lower()
        # Skip common false positives
        if ref_lower in ('e.g./', 'i.e./') or ref_lower.startswith('section_'):
            continue
        if (ref_lower not in known_names
                and ref_lower.split('/')[-1] not in known_names
                and ref_lower.split('/')[0] not in known_names):
            unverified.append(f"GitHub ref: {ref}")

    # ── Check 2: Specific numbers that look like metrics ──
    # Match patterns like "58-star", "1,234 downloads", "$2.5M", "10k users"
    metric_patterns = re.findall(
        r'(\d[\d,]*(?:\.\d+)?)\s*(?:[-\s]?(?:star|fork|download|user|subscriber|'
        r'install|mention|repo|project|contributor|commit)s?)',
        content, re.IGNORECASE
    )
    dollar_patterns = re.findall(r'\$(\d[\d,]*(?:\.\d+)?[MmBbKk]?)', content)
    all_metrics = metric_patterns + dollar_patterns

    # Build a set of numbers that appear in the snapshot
    snapshot_text = json.dumps(snapshot, default=str)
    snapshot_numbers = set(re.findall(r'\b(\d[\d,]*(?:\.\d+)?)\b', snapshot_text))

    for metric in all_metrics:
        cleaned = metric.replace(',', '')
        if cleaned not in snapshot_numbers and metric not in snapshot_numbers:
            # Check if the raw number appears anywhere in the snapshot text
            if cleaned not in snapshot_text and metric not in snapshot_text:
                unverified.append(f"Metric: {metric}")

    # ── Check 3: Bold entity names (likely tool/project names) ──
    bold_names = set(re.findall(r'\*\*([A-Za-z][A-Za-z0-9_ .-]{2,40})\*\*', content))
    generic_bold = {'section', 'warning', 'note', 'update', 'new', 'top', 'key',
                    'edition', 'builder', 'impact', 'emerging', 'prediction',
                    'signal', 'curious', 'spotlight', 'tracker', 'weekly',
                    'trend', 'takeaway', 'bottom line', 'the bottom line',
                    'what changed', 'why it matters', 'action', 'watch'}
    for name in bold_names:
        name_lower = name.lower().strip()
        if name_lower in generic_bold or len(name_lower) < 3:
            continue
        if name_lower not in known_names:
            # Fuzzy: check if any known name contains this or vice versa
            found = any(name_lower in kn or kn in name_lower for kn in known_names)
            if not found:
                unverified.append(f"Bold entity: {name}")

    ok = len(unverified) == 0
    if unverified:
        warnings.append(
            f"{len(unverified)} reference(s) in newsletter content could not be "
            f"traced to source data — possible hallucination"
        )
        for item in unverified[:10]:
            logger.warning(f"Unverified reference in newsletter: {item}")

    return {'ok': ok, 'warnings': warnings, 'unverified': unverified}


def publish_newsletter() -> dict:
    """Publish the latest draft newsletter via Telegram and email."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    try:
        # Get latest unpublished newsletter (draft or pending)
        draft = supabase.table('newsletters')\
            .select('*')\
            .in_('status', ['draft', 'pending', 'preview'])\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()

        if not draft.data:
            return {'error': 'No draft newsletter found'}

        newsletter = draft.data[0]

        # Verify references before publishing
        verification = verify_briefing_references(newsletter)
        if not verification['ok']:
            logger.warning(
                "Newsletter #%s has %d unverified reference(s): %s",
                newsletter.get('edition_number', '?'),
                len(verification['unverified']),
                '; '.join(verification['unverified'][:5])
            )
            # Store verification warnings on the record for audit trail
            try:
                supabase.table('newsletters').update({
                    'verification_warnings': verification['unverified']
                }).eq('id', newsletter['id']).execute()
            except Exception as e:
                logger.warning(f"Could not save verification warnings: {e}")

        telegram_content = newsletter.get('content_telegram') or newsletter.get('content_markdown', '')[:4000]

        if telegram_content:
            send_telegram(telegram_content)

        # Send email to all active subscribers
        try:
            email_result = send_email_newsletter(newsletter)
            logger.info("Email delivery result: %s", email_result)
        except Exception as e:
            logger.error("Email delivery failed (non-blocking): %s", e)

        # Update status to published
        supabase.table('newsletters').update({
            'status': 'published',
            'published_at': datetime.now(timezone.utc).isoformat()
        }).eq('id', newsletter['id']).execute()

        # Update appearance counters for featured opportunities and trending topics
        update_newsletter_appearances(newsletter)

        try:
            pred_result = create_predictions_from_newsletter(newsletter['id'])
            logger.info(f"Predictions created: {pred_result}")
        except Exception as e:
            logger.error(f"Prediction creation failed: {e}")

        # Generate X thread draft from the spotlight
        try:
            thread_result = generate_newsletter_thread(newsletter)
            logger.info(f"Newsletter thread draft: {thread_result}")
        except Exception as e:
            logger.error(f"Newsletter thread generation failed: {e}")

        logger.info(f"Newsletter #{newsletter.get('edition_number', '?')} published")
        return {
            'published': newsletter['id'],
            'edition': newsletter.get('edition_number')
        }

    except Exception as e:
        logger.error(f"Newsletter publish failed: {e}")
        return {'error': str(e)}


def preview_newsletter() -> dict:
    """Set latest draft/pending newsletter to 'preview' — visible on web but not distributed."""
    if not supabase:
        return {'error': 'Supabase not configured'}
    try:
        draft = supabase.table('newsletters')\
            .select('id, edition_number')\
            .in_('status', ['draft', 'pending', 'preview'])\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
        if not draft.data:
            return {'error': 'No draft newsletter found'}
        newsletter = draft.data[0]
        supabase.table('newsletters').update({
            'status': 'preview'
        }).eq('id', newsletter['id']).execute()
        logger.info(f"Newsletter #{newsletter.get('edition_number')} set to preview")
        return {'previewed': newsletter['id'], 'edition': newsletter.get('edition_number')}
    except Exception as e:
        logger.error(f"Newsletter preview failed: {e}")
        return {'error': str(e)}


def update_newsletter_appearances(newsletter: dict):
    """Update appearance counters for opportunities and trending topics featured in the newsletter."""
    if not supabase:
        return

    now = datetime.now(timezone.utc).isoformat()

    try:
        # Get the data snapshot from the newsletter's input or stored data
        data_snapshot = newsletter.get('data_snapshot') or newsletter.get('input_data') or {}

        # Update featured opportunities
        featured_opps = data_snapshot.get('section_a_opportunities') or data_snapshot.get('opportunities') or []
        for opp in featured_opps:
            opp_id = opp.get('id')
            if not opp_id:
                continue

            try:
                # Read current values
                current = supabase.table('opportunities')\
                    .select('newsletter_appearances, first_featured_at')\
                    .eq('id', opp_id)\
                    .limit(1)\
                    .execute()

                if current.data:
                    current_appearances = current.data[0].get('newsletter_appearances', 0) or 0
                    update_data = {
                        'newsletter_appearances': current_appearances + 1,
                        'last_featured_at': now
                    }
                    # Set first_featured_at if not already set
                    if not current.data[0].get('first_featured_at'):
                        update_data['first_featured_at'] = now

                    supabase.table('opportunities')\
                        .update(update_data)\
                        .eq('id', opp_id)\
                        .execute()

            except Exception as e:
                logger.error(f"Failed to update appearances for opportunity {opp_id}: {e}")

        # Update featured trending topics
        featured_topics = data_snapshot.get('section_c_curious') or []
        for topic in featured_topics:
            topic_id = topic.get('id')
            if not topic_id:
                continue

            try:
                supabase.table('trending_topics')\
                    .update({'featured_in_newsletter': True})\
                    .eq('id', topic_id)\
                    .execute()
            except Exception as e:
                logger.error(f"Failed to mark trending topic {topic_id} as featured: {e}")

        opp_count = len([o for o in featured_opps if o.get('id')])
        topic_count = len([t for t in featured_topics if t.get('id')])
        logger.info(f"Newsletter appearances updated: {opp_count} opportunities, {topic_count} trending topics")

    except Exception as e:
        logger.error(f"Failed to update newsletter appearances: {e}")


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
# Analysis Package Assembly (delegates to Analyst agent)
# ============================================================================

def prepare_analysis_package(hours_back: int = 48) -> dict:
    """Gather all data the Analyst needs and create an analysis task."""
    if not supabase:
        return {'error': 'Not configured'}

    run_id = log_pipeline_start('prepare_analysis')
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()

    try:
        # Gather data from all sources
        problems = supabase.table('problems')\
            .select('*')\
            .gte('first_seen', cutoff)\
            .order('frequency_count', desc=True)\
            .limit(200)\
            .execute()

        clusters = supabase.table('problem_clusters')\
            .select('*')\
            .order('opportunity_score', desc=True)\
            .limit(50)\
            .execute()

        tool_mentions = supabase.table('tool_mentions')\
            .select('*')\
            .gte('mentioned_at', cutoff)\
            .order('mentioned_at', desc=True)\
            .limit(200)\
            .execute()

        tool_stats = supabase.table('tool_stats')\
            .select('*')\
            .order('total_mentions', desc=True)\
            .limit(50)\
            .execute()

        existing_opps = supabase.table('opportunities')\
            .select('*')\
            .eq('status', 'draft')\
            .order('confidence_score', desc=True)\
            .limit(20)\
            .execute()

        # Get previous analysis run for comparison
        prev_run = supabase.table('analysis_runs')\
            .select('*')\
            .eq('status', 'completed')\
            .order('completed_at', desc=True)\
            .limit(1)\
            .execute()

        # Stats
        total_posts = supabase.table('moltbook_posts')\
            .select('id', count='exact')\
            .gte('scraped_at', cutoff)\
            .execute()

        thought_leader_posts = supabase.table('source_posts')\
            .select('*')\
            .like('source', 'thought_leader_%')\
            .gte('scraped_at', cutoff)\
            .order('scraped_at', desc=True)\
            .limit(50)\
            .execute()

        data_package = {
            'timeframe_hours': hours_back,
            'gathered_at': datetime.now(timezone.utc).isoformat(),
            'problems': problems.data or [],
            'clusters': clusters.data or [],
            'tool_mentions': tool_mentions.data or [],
            'tool_stats': tool_stats.data or [],
            'existing_opportunities': existing_opps.data or [],
            'previous_run': prev_run.data[0] if prev_run.data else None,
            'thought_leader_content': thought_leader_posts.data or [],
            'stats': {
                'posts_in_window': total_posts.count or 0,
                'problems_in_window': len(problems.data or []),
                'tools_tracked': len(tool_stats.data or []),
                'existing_opportunities': len(existing_opps.data or []),
                'thought_leader_posts': len(thought_leader_posts.data or [])
            }
        }

        # Create analysis task for the Analyst agent
        # Serialize with default=str to handle datetimes
        serialized = json.loads(json.dumps(data_package, default=str))

        task_result = supabase.table('agent_tasks').insert({
            'task_type': 'full_analysis',
            'assigned_to': 'analyst',
            'created_by': 'processor',
            'priority': 2,
            'input_data': serialized
        }).execute()

        task_id = task_result.data[0]['id'] if task_result.data else None

        result = {
            'task_id': task_id,
            'data_summary': {
                'problems': len(problems.data or []),
                'clusters': len(clusters.data or []),
                'tool_mentions': len(tool_mentions.data or []),
                'tools': len(tool_stats.data or []),
                'opportunities': len(existing_opps.data or [])
            },
            'delegated_to': 'analyst'
        }

        log_pipeline_end(run_id, 'completed', result)
        logger.info(f"Analysis package assembled and delegated to analyst (task {task_id})")
        return result

    except Exception as e:
        logger.error(f"Analysis package assembly failed: {e}")
        log_pipeline_end(run_id, 'failed', {'error': str(e)})
        return {'error': str(e)}


# ============================================================================
# Proactive Monitoring
# ============================================================================

def detect_anomalies() -> list:
    """Check for data anomalies. No LLM calls — just SQL and math."""
    if not supabase:
        return []

    anomalies = []
    now = datetime.now(timezone.utc)
    hour_ago = (now - timedelta(hours=1)).isoformat()
    day_ago = (now - timedelta(days=1)).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()

    # 1. Problem frequency spike by category
    try:
        recent_problems = supabase.table('problems')\
            .select('category')\
            .gte('first_seen', hour_ago)\
            .execute()

        baseline_problems = supabase.table('problems')\
            .select('category')\
            .gte('first_seen', week_ago)\
            .lt('first_seen', day_ago)\
            .execute()

        if recent_problems.data and baseline_problems.data:
            recent_counts = Counter(p['category'] for p in recent_problems.data)
            baseline_counts = Counter(p['category'] for p in baseline_problems.data)
            baseline_hours = 24 * 6  # 6 days of baseline

            for category, count in recent_counts.items():
                baseline_hourly = baseline_counts.get(category, 0) / max(baseline_hours, 1)
                if baseline_hourly > 0 and count > baseline_hourly * 3:
                    anomalies.append({
                        'type': 'frequency_spike',
                        'category': category,
                        'current': count,
                        'baseline_hourly': round(baseline_hourly, 2),
                        'multiplier': round(count / baseline_hourly, 1),
                        'description': f"{category} problems spiked {round(count / baseline_hourly, 1)}x above baseline"
                    })
    except Exception as e:
        logger.error(f"Anomaly detection (frequency spike) failed: {e}")

    # 2. Tool sentiment crash
    try:
        recent_sentiment = supabase.table('tool_mentions')\
            .select('tool_name, sentiment_score')\
            .gte('mentioned_at', day_ago)\
            .execute()

        if recent_sentiment.data:
            tool_sentiments = defaultdict(list)
            for m in recent_sentiment.data:
                tool_sentiments[m['tool_name']].append(m.get('sentiment_score', 0))

            for tool_name, scores in tool_sentiments.items():
                avg_recent = sum(scores) / len(scores)
                try:
                    stats = supabase.table('tool_stats')\
                        .select('avg_sentiment')\
                        .eq('tool_name', tool_name)\
                        .execute()
                    if stats.data:
                        historical_avg = stats.data[0].get('avg_sentiment', 0)
                        if historical_avg - avg_recent > 0.5:
                            anomalies.append({
                                'type': 'sentiment_crash',
                                'tool_name': tool_name,
                                'current_avg': round(avg_recent, 2),
                                'historical_avg': round(historical_avg, 2),
                                'drop': round(historical_avg - avg_recent, 2),
                                'description': f"{tool_name} sentiment dropped {round(historical_avg - avg_recent, 2)} points"
                            })
                except Exception as e:
                    logger.error(f"Sentiment comparison failed for {tool_name}: {e}")
    except Exception as e:
        logger.error(f"Anomaly detection (sentiment crash) failed: {e}")

    # 3. Volume anomaly
    try:
        recent_post_count = supabase.table('moltbook_posts')\
            .select('id', count='exact')\
            .gte('scraped_at', hour_ago)\
            .execute()

        baseline_post_count = supabase.table('moltbook_posts')\
            .select('id', count='exact')\
            .gte('scraped_at', week_ago)\
            .lt('scraped_at', day_ago)\
            .execute()

        recent_count = recent_post_count.count or 0
        baseline_count = baseline_post_count.count or 0

        if recent_count and baseline_count:
            baseline_hourly_posts = baseline_count / (24 * 6)
            if baseline_hourly_posts > 0:
                ratio = recent_count / baseline_hourly_posts
                if ratio > 2.5 or ratio < 0.3:
                    anomalies.append({
                        'type': 'volume_anomaly',
                        'current': recent_count,
                        'baseline_hourly': round(baseline_hourly_posts, 1),
                        'ratio': round(ratio, 1),
                        'direction': 'spike' if ratio > 2.5 else 'drop',
                        'description': f"Post volume {'spiked' if ratio > 2.5 else 'dropped'} to {round(ratio, 1)}x baseline"
                    })
    except Exception as e:
        logger.error(f"Anomaly detection (volume) failed: {e}")

    return anomalies


def check_proactive_budget() -> bool:
    """Check if proactive alerts budget has remaining capacity for today."""
    if not supabase:
        return True

    today = datetime.now(timezone.utc).date().isoformat()
    try:
        usage = supabase.table('agent_daily_usage')\
            .select('proactive_alerts_sent')\
            .eq('agent_name', 'system')\
            .eq('date', today)\
            .execute()

        global_config = get_full_config().get('budgets', {}).get('global', {})
        max_daily = global_config.get('max_daily_proactive_alerts', 5)

        if not usage.data:
            return True
        return (usage.data[0].get('proactive_alerts_sent', 0) or 0) < max_daily

    except Exception as e:
        logger.error(f"Failed to check proactive budget: {e}")
        return True


def check_proactive_cooldown() -> bool:
    """Ensure minimum time between proactive scans."""
    if not supabase:
        return True

    global_config = get_full_config().get('budgets', {}).get('global', {})
    cooldown_minutes = global_config.get('cooldown_between_proactive_scans_minutes', 60)

    try:
        last_scan = supabase.table('pipeline_runs')\
            .select('completed_at')\
            .eq('pipeline', 'proactive_scan')\
            .order('completed_at', desc=True)\
            .limit(1)\
            .execute()

        if not last_scan.data:
            return True

        completed_at = last_scan.data[0].get('completed_at')
        if not completed_at:
            return True

        if completed_at.endswith('Z'):
            completed_at = completed_at.replace('Z', '+00:00')
        last_time = datetime.fromisoformat(completed_at)
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)

        elapsed_minutes = (datetime.now(timezone.utc) - last_time).total_seconds() / 60
        return elapsed_minutes >= cooldown_minutes

    except Exception as e:
        logger.error(f"Failed to check proactive cooldown: {e}")
        return True


def proactive_scan() -> dict:
    """Periodic scan for anomalies. No LLM unless anomaly found."""
    if not check_proactive_budget():
        logger.info("Proactive scan: daily budget exhausted")
        return {'skipped': 'daily_budget_exhausted'}

    if not check_proactive_cooldown():
        logger.info("Proactive scan: cooldown active")
        return {'skipped': 'cooldown_active'}

    run_id = log_pipeline_start('proactive_scan')

    try:
        anomalies = detect_anomalies()

        if not anomalies:
            logger.info("Proactive scan: no anomalies detected")
            log_pipeline_end(run_id, 'completed', {'anomalies': 0})
            return {'anomalies': 0, 'analysis_requested': False}

        logger.info(f"Proactive scan: {len(anomalies)} anomalies detected")

        # Pre-check analyst daily budget before creating a task that would immediately fail
        if not check_daily_budget('analyst'):
            logger.debug("Proactive scan: analyst daily budget exhausted, skipping task creation")
            log_pipeline_end(run_id, 'completed', {'anomalies': len(anomalies), 'analysis_requested': False, 'reason': 'analyst_budget_exhausted'})
            return {'anomalies': len(anomalies), 'analysis_requested': False, 'reason': 'analyst_budget_exhausted'}

        # Create a focused analysis task for the Analyst
        budget = get_budget_config('analyst', 'proactive_scan')

        if supabase:
            supabase.table('agent_tasks').insert({
                'task_type': 'proactive_analysis',
                'assigned_to': 'analyst',
                'created_by': 'processor',
                'priority': 2,
                'input_data': {
                    'anomalies': anomalies,
                    'budget': budget
                }
            }).execute()

        result = {'anomalies': len(anomalies), 'analysis_requested': True}
        log_pipeline_end(run_id, 'completed', result)
        return result

    except Exception as e:
        logger.error(f"Proactive scan failed: {e}")
        log_pipeline_end(run_id, 'failed', {'error': str(e)})
        return {'error': str(e)}


# ============================================================================
# Agent-to-Agent Negotiation
# ============================================================================

def create_negotiation(
    requesting_agent: str,
    responding_agent: str,
    request_task_id: str,
    request_summary: str,
    quality_criteria: str,
    needed_by: str = None,
) -> dict:
    """Create a negotiation between two agents, with guardrail checks."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    config = get_full_config().get('negotiation', {})

    # Check if this agent pair is allowed
    allowed_pairs = config.get('allowed_pairs', {})
    allowed_key = f"{requesting_agent}_can_ask"
    allowed_targets = allowed_pairs.get(allowed_key, [])
    if responding_agent not in allowed_targets:
        reason = f"{requesting_agent} is not allowed to negotiate with {responding_agent}"
        logger.warning(f"Negotiation blocked: {reason}")
        return {'error': reason}

    # Check max active negotiations for the requesting agent
    max_active = config.get('max_active_negotiations_per_agent', 3)
    try:
        active = supabase.table('agent_negotiations')\
            .select('id', count='exact')\
            .eq('requesting_agent', requesting_agent)\
            .in_('status', ['open', 'follow_up'])\
            .execute()
        active_count = active.count or 0
        if active_count >= max_active:
            reason = f"{requesting_agent} already has {active_count} active negotiations (max {max_active})"
            logger.warning(f"Negotiation blocked: {reason}")
            return {'error': reason}
    except Exception as e:
        logger.error(f"Failed to check active negotiations: {e}")
        return {'error': str(e)}

    # Create the negotiation
    try:
        record = {
            'requesting_agent': requesting_agent,
            'responding_agent': responding_agent,
            'status': 'open',
            'round': 1,
            'request_summary': request_summary,
            'quality_criteria': quality_criteria,
        }
        if request_task_id:
            record['request_task_id'] = request_task_id
        if needed_by:
            record['needed_by'] = needed_by

        result = supabase.table('agent_negotiations').insert(record).execute()
        negotiation_id = result.data[0]['id'] if result.data else None
        logger.info(f"Negotiation created: {negotiation_id} ({requesting_agent} → {responding_agent})")
        return {'negotiation_id': negotiation_id}

    except Exception as e:
        logger.error(f"Failed to create negotiation: {e}")
        return {'error': str(e)}


def respond_to_negotiation(
    negotiation_id: str,
    response_task_id: str,
    criteria_met: bool,
    response_summary: str,
) -> dict:
    """Record a response to a negotiation and advance its state."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    config = get_full_config().get('negotiation', {})
    max_rounds = config.get('max_rounds_per_negotiation', 2)

    try:
        # Fetch current negotiation
        neg = supabase.table('agent_negotiations')\
            .select('*')\
            .eq('id', negotiation_id)\
            .single()\
            .execute()

        if not neg.data:
            return {'error': f'Negotiation {negotiation_id} not found'}

        current = neg.data
        current_round = current.get('round', 1)
        now = datetime.now(timezone.utc).isoformat()

        update = {
            'criteria_met': criteria_met,
            'response_summary': response_summary,
        }
        if response_task_id:
            update['response_task_id'] = response_task_id

        if criteria_met:
            update['status'] = 'closed'
            update['closed_at'] = now
        elif current_round < max_rounds:
            update['status'] = 'follow_up'
            update['round'] = current_round + 1
        else:
            update['status'] = 'closed'
            update['closed_at'] = now

        supabase.table('agent_negotiations')\
            .update(update)\
            .eq('id', negotiation_id)\
            .execute()

        logger.info(
            f"Negotiation {negotiation_id} updated: "
            f"criteria_met={criteria_met}, status={update.get('status')}, round={update.get('round', current_round)}"
        )
        return {
            'negotiation_id': negotiation_id,
            'status': update.get('status', current.get('status')),
            'round': update.get('round', current_round),
            'criteria_met': criteria_met,
        }

    except Exception as e:
        logger.error(f"Failed to respond to negotiation {negotiation_id}: {e}")
        return {'error': str(e)}


def check_negotiation_timeouts():
    """Time out negotiations that have been open too long."""
    if not supabase:
        return

    config = get_full_config().get('negotiation', {})
    timeout_minutes = config.get('negotiation_timeout_minutes', 30)
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)).isoformat()

    try:
        stale = supabase.table('agent_negotiations')\
            .select('*')\
            .in_('status', ['open', 'follow_up'])\
            .lt('created_at', cutoff)\
            .execute()

        now = datetime.now(timezone.utc).isoformat()
        for neg in stale.data or []:
            supabase.table('agent_negotiations')\
                .update({'status': 'timed_out', 'closed_at': now})\
                .eq('id', neg['id'])\
                .execute()
            logger.warning(
                f"Negotiation {neg['id']} timed out "
                f"({neg['requesting_agent']} → {neg['responding_agent']})"
            )

    except Exception as e:
        logger.error(f"Failed to check negotiation timeouts: {e}")


# ============================================================================
# Prediction Tracking
# ============================================================================

def gather_prediction_signals(pred: dict) -> dict:
    """Gather current signals relevant to a prediction's topic."""
    title = pred.get('title', '')
    keywords = [w.lower() for w in title.split() if len(w) > 2][:3]
    if not keywords:
        return {'mentions_7d': 0, 'avg_sentiment': 0, 'new_tools': [], 'github_repos': 0, 'github_stars': 0}

    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    recent_problems = supabase.table('problems')\
        .select('*')\
        .gte('last_seen', week_ago)\
        .execute()
    matching_problems = [
        p for p in (recent_problems.data or [])
        if any(kw in (p.get('description', '') + ' ' + p.get('title', '')).lower() for kw in keywords)
    ]

    recent_tools = supabase.table('tool_mentions')\
        .select('*')\
        .gte('mentioned_at', week_ago)\
        .execute()
    matching_tools = [
        t for t in (recent_tools.data or [])
        if any(kw in t.get('tool_name', '').lower() for kw in keywords)
    ]

    github_posts = supabase.table('source_posts')\
        .select('*')\
        .eq('source', 'github')\
        .gte('scraped_at', week_ago)\
        .execute()
    matching_github = [
        g for g in (github_posts.data or [])
        if any(kw in (g.get('title', '') + ' ' + g.get('body', '')).lower() for kw in keywords)
    ]

    avg_sentiment = (
        sum(t.get('sentiment_score', 0) for t in matching_tools) / len(matching_tools)
        if matching_tools else 0
    )

    return {
        'mentions_7d': len(matching_problems),
        'avg_sentiment': round(avg_sentiment, 3),
        'new_tools': [t['tool_name'] for t in matching_tools[:5]],
        'github_repos': len(matching_github),
        'github_stars': sum(g.get('score', 0) for g in matching_github),
    }


def evaluate_prediction(pred: dict, signals: dict) -> tuple:
    """Evaluate a prediction's status based on current signals.

    Returns (new_status, new_score, notes).
    """
    current = pred.get('current_score', pred.get('initial_confidence', 0.5))

    # Check target_date-based expiry first
    target_date_str = pred.get('target_date')
    if target_date_str:
        try:
            target_dt = datetime.fromisoformat(str(target_date_str)).date()
            today = datetime.now(timezone.utc).date()
            if target_dt < today:
                days_overdue = (today - target_dt).days
                notes = (f"Target date {target_date_str} passed "
                         f"({days_overdue} days ago) — requires resolution")
                return ('expired', max(round(current - 0.3, 2), 0), notes)
        except (ValueError, TypeError):
            pass

    created_str = pred.get('created_at', datetime.now(timezone.utc).isoformat())
    created_dt = datetime.fromisoformat(created_str.replace('Z', '+00:00')).replace(tzinfo=None)
    weeks_active = (datetime.now(timezone.utc) - created_dt).days / 7

    mentions = signals.get('mentions_7d', 0)
    github = signals.get('github_repos', 0)

    if mentions >= 5 and github >= 2:
        score = min(current + 0.15, 1.0)
        notes = f"Strong signals: {mentions} mentions, {github} GitHub repos"
        status = 'confirmed' if score >= 0.8 else 'active'
    elif mentions >= 2 or github >= 1:
        score = min(current + 0.05, 1.0)
        notes = f"Developing: {mentions} mentions, {github} GitHub repos"
        status = 'active'
    elif mentions == 0 and weeks_active >= 3:
        score = max(current - 0.2, 0)
        notes = "No mentions for 3+ weeks"
        status = 'faded' if score < 0.2 else 'active'
    elif mentions == 0 and weeks_active >= 1:
        score = max(current - 0.1, 0)
        notes = "Quiet week"
        status = 'active'
    else:
        score = current
        notes = "Stable"
        status = 'active'

    return (status, round(score, 2), notes)


def track_predictions() -> dict:
    """Check active predictions against current data and update their scores."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    # First, auto-expire any predictions with past target dates
    today_str = datetime.now(timezone.utc).date().isoformat()
    expired_count = 0
    try:
        overdue = supabase.table('predictions')\
            .select('id, target_date, title')\
            .in_('status', ['active', 'open', 'developing'])\
            .not_.is_('target_date', 'null')\
            .lt('target_date', today_str)\
            .execute()
        for pred in (overdue.data or []):
            supabase.table('predictions').update({
                'status': 'expired',
                'resolution_notes': (
                    f"Auto-expired: target_date {pred.get('target_date')} "
                    f"has passed (today={today_str})"
                ),
                'resolved_at': datetime.now(timezone.utc).isoformat(),
            }).eq('id', pred['id']).execute()
            expired_count += 1
        if expired_count:
            logger.info(f"track_predictions: auto-expired {expired_count} overdue prediction(s)")
    except Exception as e:
        logger.warning(f"track_predictions: auto-expire failed: {e}")

    active = supabase.table('predictions')\
        .select('*')\
        .eq('status', 'active')\
        .execute()

    if not active.data:
        return {'tracked': 0, 'confirmed': 0, 'faded': 0, 'active': 0, 'expired': expired_count}

    counts = {'tracked': 0, 'confirmed': 0, 'faded': 0, 'active': 0, 'expired': expired_count}

    for pred in active.data:
        try:
            signals = gather_prediction_signals(pred)
            new_status, new_score, notes = evaluate_prediction(pred, signals)

            history = json.loads(pred.get('tracking_history', '[]') or '[]')
            history.append({
                'date': datetime.now(timezone.utc).isoformat(),
                'event': 'tracked',
                'mentions_this_week': signals.get('mentions_7d', 0),
                'mentions_total': signals.get('mentions_7d', 0),
                'sentiment': signals.get('avg_sentiment', 0),
                'new_tools': signals.get('new_tools', []),
                'github_repos': signals.get('github_repos', 0),
                'score': new_score,
                'notes': notes,
            })

            update = {
                'current_score': new_score,
                'tracking_history': json.dumps(history, default=str),
                'last_tracked': datetime.now(timezone.utc).isoformat(),
            }

            if new_status != pred['status']:
                update['status'] = new_status
                if new_status in ('confirmed', 'faded', 'wrong'):
                    update['resolved_at'] = datetime.now(timezone.utc).isoformat()
                    update['resolution_notes'] = notes

            supabase.table('predictions').update(update).eq('id', pred['id']).execute()
            counts['tracked'] += 1
            counts[new_status] = counts.get(new_status, 0) + 1
        except Exception as e:
            logger.error(f"Error tracking prediction {pred.get('id')}: {e}")
            continue

    logger.info(f"Prediction tracking complete: {counts}")
    return counts


# ============================================================================
# Research Queue / Spotlight / Scorecard Helpers
# ============================================================================

def queue_research_topic(topic_id: str, topic_name: str, priority_score: float,
                         velocity: float = None, source_diversity: float = None,
                         lifecycle_phase: str = None, context_payload: dict = None,
                         mode: str = 'spotlight', issue_number: int = None) -> dict:
    """Add a topic to the research queue for the Research Agent to pick up."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    record = {
        'topic_id': topic_id,
        'topic_name': topic_name,
        'priority_score': priority_score,
        'status': 'queued',
        'mode': mode,
    }
    if velocity is not None:
        record['velocity'] = velocity
    if source_diversity is not None:
        record['source_diversity'] = source_diversity
    if lifecycle_phase:
        record['lifecycle_phase'] = lifecycle_phase
    if context_payload:
        record['context_payload'] = context_payload
    if issue_number is not None:
        record['issue_number'] = issue_number

    result = supabase.table('research_queue').insert(record).execute()
    logger.info(f"Queued research topic '{topic_name}' (mode={mode}, priority={priority_score})")
    return result.data[0] if result.data else {}


def get_research_queue(status: str = 'queued', limit: int = 5) -> list:
    """Fetch research queue items filtered by status, ordered by priority."""
    if not supabase:
        return []

    result = supabase.table('research_queue')\
        .select('*')\
        .eq('status', status)\
        .order('priority_score', desc=True)\
        .limit(limit)\
        .execute()
    return result.data or []


def update_research_status(queue_id: str, status: str, **extra) -> dict:
    """Update a research queue item's status (queued -> in_progress -> completed/failed)."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    update = {'status': status}
    if status == 'in_progress':
        update['started_at'] = datetime.now(timezone.utc).isoformat()
    elif status in ('completed', 'failed'):
        update['completed_at'] = datetime.now(timezone.utc).isoformat()
    update.update(extra)

    result = supabase.table('research_queue').update(update).eq('id', queue_id).execute()
    return result.data[0] if result.data else {}


def store_spotlight(research_queue_id: str, topic_id: str, topic_name: str,
                    issue_number: int, thesis: str, evidence: str,
                    counter_argument: str, prediction: str,
                    builder_implications: str = None, full_output: str = '',
                    sources_used: list = None, mode: str = 'spotlight') -> dict:
    """Store a completed Spotlight analysis."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    record = {
        'research_queue_id': research_queue_id,
        'topic_id': topic_id,
        'topic_name': topic_name,
        'issue_number': issue_number,
        'mode': mode,
        'thesis': thesis,
        'evidence': evidence,
        'counter_argument': counter_argument,
        'prediction': prediction,
        'builder_implications': builder_implications or '',
        'full_output': full_output,
        'sources_used': sources_used or [],
    }

    result = supabase.table('spotlight_history').insert(record).execute()
    spotlight = result.data[0] if result.data else {}

    if spotlight and prediction:
        create_spotlight_prediction(
            spotlight_id=spotlight['id'],
            topic_id=topic_id,
            prediction_text=prediction,
            issue_number=issue_number,
        )

    logger.info(f"Stored spotlight for '{topic_name}' (issue #{issue_number})")
    return spotlight


def get_latest_spotlight(issue_number: int = None) -> dict:
    """Get the latest spotlight, optionally for a specific issue."""
    if not supabase:
        return {}

    query = supabase.table('spotlight_history').select('*')
    if issue_number is not None:
        query = query.eq('issue_number', issue_number)
    result = query.order('created_at', desc=True).limit(1).execute()
    return result.data[0] if result.data else {}


# ---------------------------------------------------------------------------
# Target-date extraction for predictions
# ---------------------------------------------------------------------------

_MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
}

_DATE_PATTERNS: list[tuple] = [
    # "by Q1 2026" -> end of quarter
    (r'(?:by|before)\s+Q([1-4])\s+(\d{4})',
     lambda m: datetime(int(m.group(2)), int(m.group(1)) * 3, 28).date()),
    # "by March 2026" / "before April 2026"
    (r'(?:by|before)\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
     lambda m: datetime(int(m.group(2)), _MONTH_MAP[m.group(1).lower()], 28).date()),
    # "within N months"
    (r'within\s+(\d+)\s+months?',
     lambda m: (datetime.now(timezone.utc) + timedelta(days=int(m.group(1)) * 30)).date()),
    # "by year-end" / "by end of 2026"
    (r'(?:by|before)\s+(?:year[- ]?end|end\s+of)\s+(\d{4})',
     lambda m: datetime(int(m.group(1)), 12, 31).date()),
    # "by mid-2026"
    (r'(?:by|before)\s+mid[- ](\d{4})',
     lambda m: datetime(int(m.group(1)), 6, 30).date()),
]


def extract_target_date(prediction_text: str):
    """Extract a target date from prediction text.

    Supports: 'by Q3 2026', 'before July 2026', 'within 6 months',
    'by year-end 2026', 'by mid-2026'.
    Returns a date or None.
    """
    if not prediction_text:
        return None
    for pattern, resolver in _DATE_PATTERNS:
        match = re.search(pattern, prediction_text, re.IGNORECASE)
        if match:
            try:
                return resolver(match)
            except (ValueError, TypeError):
                continue
    return None


def create_spotlight_prediction(spotlight_id: str, topic_id: str,
                                prediction_text: str, issue_number: int) -> dict:
    """Create a prediction record linked to a spotlight for scorecard tracking."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    record = {
        'spotlight_id': spotlight_id,
        'prediction_type': 'spotlight',
        'title': prediction_text[:100],
        'prediction_text': prediction_text,
        'topic_id': topic_id,
        'issue_number': issue_number,
        'newsletter_edition': issue_number,
        'status': 'open',
        'initial_confidence': 0.6,
        'current_score': 0.6,
        'tracking_history': json.dumps([{
            'date': datetime.now(timezone.utc).isoformat(),
            'event': 'created_from_spotlight',
            'confidence': 0.6,
        }], default=str),
    }

    # Extract target_date from prediction text
    target = extract_target_date(prediction_text)
    if target:
        record['target_date'] = target.isoformat()
    else:
        logger.warning(f"No target_date extracted from spotlight prediction: {prediction_text[:80]}")

    result = supabase.table('predictions').insert(record).execute()
    return result.data[0] if result.data else {}


def flag_prediction(prediction_id: str, evidence_notes: str) -> dict:
    """Flag a prediction with new evidence (Analyst uses this during tracking)."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    pred = supabase.table('predictions').select('*').eq('id', prediction_id).execute()
    if not pred.data:
        return {'error': 'Prediction not found'}

    existing = pred.data[0]
    history = json.loads(existing.get('tracking_history') or '[]')
    history.append({
        'date': datetime.now(timezone.utc).isoformat(),
        'event': 'flagged',
        'notes': evidence_notes,
    })

    update = {
        'status': 'flagged',
        'evidence_notes': evidence_notes,
        'flagged_at': datetime.now(timezone.utc).isoformat(),
        'tracking_history': json.dumps(history, default=str),
    }

    result = supabase.table('predictions').update(update).eq('id', prediction_id).execute()
    return result.data[0] if result.data else {}


def resolve_prediction(prediction_id: str, status: str, resolution_notes: str,
                       scorecard_issue: int = None) -> dict:
    """Resolve a prediction (confirmed/refuted/partially_correct/expired)."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    pred = supabase.table('predictions').select('*').eq('id', prediction_id).execute()
    if not pred.data:
        return {'error': 'Prediction not found'}

    existing = pred.data[0]
    history = json.loads(existing.get('tracking_history') or '[]')
    history.append({
        'date': datetime.now(timezone.utc).isoformat(),
        'event': f'resolved_{status}',
        'notes': resolution_notes,
    })

    update = {
        'status': status,
        'resolution_notes': resolution_notes,
        'resolved_at': datetime.now(timezone.utc).isoformat(),
        'tracking_history': json.dumps(history, default=str),
    }
    if scorecard_issue is not None:
        update['scorecard_issue'] = scorecard_issue

    result = supabase.table('predictions').update(update).eq('id', prediction_id).execute()
    return result.data[0] if result.data else {}


def get_spotlight_cooldown() -> list:
    """Get topics on cooldown (spotlighted in last 4 issues)."""
    if not supabase:
        return []

    result = supabase.table('spotlight_cooldown')\
        .select('*')\
        .eq('on_cooldown', True)\
        .execute()
    return result.data or []


def get_scorecard(limit: int = 20) -> dict:
    """Build a scorecard summary of prediction accuracy."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    result = supabase.table('predictions')\
        .select('*')\
        .order('created_at', desc=True)\
        .limit(limit)\
        .execute()

    preds = result.data or []
    total = len(preds)
    by_status = {}
    for p in preds:
        s = p.get('status', 'unknown')
        by_status[s] = by_status.get(s, 0) + 1

    confirmed = by_status.get('confirmed', 0)
    refuted = by_status.get('refuted', 0)
    resolved = confirmed + refuted + by_status.get('partially_correct', 0) + by_status.get('expired', 0)
    accuracy = (confirmed / resolved * 100) if resolved > 0 else None

    return {
        'total': total,
        'by_status': by_status,
        'resolved': resolved,
        'accuracy_pct': round(accuracy, 1) if accuracy is not None else None,
        'predictions': preds,
    }


# ============================================================================
# Spotlight Selection Heuristic
# ============================================================================

LIFECYCLE_BONUS = {
    'emerging': 1.0,
    'debating': 1.5,
    'building': 1.3,
    'consolidating': 1.0,
    'mature': 0.5,
    'declining': 0.2,
}


def _get_spotlight_config() -> dict:
    """Load spotlight selection config, with defaults."""
    config = get_full_config().get('spotlight_selection', {})
    return {
        'min_score_threshold': config.get('min_score_threshold', 0.3),
        'cooldown_issues': config.get('cooldown_issues', 4),
        'min_mentions': config.get('min_mentions', 2),
        'min_source_tiers': config.get('min_source_tiers', 2),
        'max_queue_items': config.get('max_queue_items', 1),
    }


def _compute_velocity(topic: dict, days: int = 7) -> float:
    """Compute normalized mention velocity from recent snapshots (0-1).

    Denominator is 8 (not 20) to match observed data distribution where
    most topics see 0-6 mentions per snapshot window.
    """
    snapshots = topic.get('snapshots') or []
    if not snapshots:
        return 0.0
    recent = snapshots[-1]
    mentions = recent.get('mentions', 0)
    return min(mentions / 8.0, 1.0)


def _compute_source_diversity(topic: dict) -> float:
    """Compute source tier diversity (0-1) using actual source_tier values."""
    snapshots = topic.get('snapshots') or []
    if not snapshots:
        return 0.0
    recent = snapshots[-1]
    sources = recent.get('sources', [])
    if not sources:
        return 0.0

    tier_set = set()

    if supabase:
        # Query actual source_tier values from the database
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        try:
            for src in set(sources):
                posts = supabase.table('source_posts')\
                    .select('source_tier')\
                    .eq('source', src)\
                    .gte('scraped_at', week_ago)\
                    .limit(1)\
                    .execute()
                if posts.data:
                    tier_val = posts.data[0].get('source_tier', 3)
                    if tier_val == 1:
                        tier_set.add('authority')
                    elif tier_val == 2:
                        tier_set.add('curated')
                    else:
                        tier_set.add('community')
                else:
                    # Source not found in DB, infer from name
                    if src.startswith('rss_') or src.startswith('thought_leader_'):
                        tier_set.add('authority')
                    else:
                        tier_set.add('community')
        except Exception as e:
            logger.warning(f"Source diversity DB lookup failed: {e}")
            # Fallback to name-based heuristic
            for src in sources:
                if src.startswith('rss_') or src.startswith('thought_leader_'):
                    tier_set.add('authority')
                else:
                    tier_set.add('community')
    else:
        # No DB — fallback to name-based heuristic
        for src in sources:
            if src.startswith('rss_') or src.startswith('thought_leader_'):
                tier_set.add('authority')
            else:
                tier_set.add('community')

    # Also check thought leaders via keyword matching
    topic_key = topic.get('topic_key', '')
    keywords = [w for w in topic_key.split('_') if len(w) >= 3]
    if keywords and supabase:
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        try:
            tl_posts = supabase.table('source_posts')\
                .select('title, body')\
                .like('source', 'thought_leader_%')\
                .gte('scraped_at', week_ago)\
                .limit(50)\
                .execute()
            for p in (tl_posts.data or []):
                text = ((p.get('title') or '') + ' ' + (p.get('body') or '')).lower()
                if any(kw in text for kw in keywords):
                    tier_set.add('thought_leader')
                    break
        except Exception as e:
            logger.warning(f"Source diversity TL lookup skipped: {e}")

    return min(len(tier_set) / 3.0, 1.0)


def _get_recent_mentions_for_context(topic_key: str, days: int = 7, limit: int = 5) -> list:
    """Get recent source_posts mentioning this topic for the context payload."""
    if not supabase:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    posts = supabase.table('source_posts')\
        .select('source, source_tier, title, body, source_url')\
        .gte('scraped_at', cutoff)\
        .order('score', desc=True)\
        .limit(200)\
        .execute()
    if not posts.data:
        return []
    keywords = [w for w in topic_key.split('_') if len(w) >= 3]
    if not keywords:
        return []
    matches = []
    for p in posts.data:
        text = ((p.get('title') or '') + ' ' + (p.get('body') or '')).lower()
        if any(kw in text for kw in keywords):
            matches.append({
                'source': p.get('source', 'unknown'),
                'tier': p.get('source_tier', 3),
                'title': p.get('title', ''),
                'summary': (p.get('body') or '')[:200],
                'url': p.get('source_url', ''),
            })
        if len(matches) >= limit:
            break
    return matches


RESEARCH_TRIGGER_DIR = QUEUE_DIR / 'research'
RESEARCH_TRIGGER_DIR.mkdir(parents=True, exist_ok=True)


def _write_research_trigger(queue_id: str, topic_name: str, mode: str) -> str | None:
    """Write a trigger file for the Research Agent. Returns filename or None on duplicate."""
    existing = list(RESEARCH_TRIGGER_DIR.glob('research-trigger-*.json'))
    for f in existing:
        try:
            data = json.loads(f.read_text())
            if data.get('research_queue_id') == queue_id:
                logger.info(f"Duplicate trigger skipped for queue_id={queue_id}")
                return None
        except Exception as e:
            logger.warning(f"Duplicate trigger check skipped: {e}")

    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    filename = f'research-trigger-{ts}.json'
    trigger_path = RESEARCH_TRIGGER_DIR / filename

    trigger_data = {
        'trigger_type': 'research_request',
        'research_queue_id': queue_id,
        'topic_name': topic_name,
        'mode': mode,
        'triggered_at': datetime.now(timezone.utc).isoformat() + 'Z',
        'triggered_by': 'analyst',
    }

    trigger_path.write_text(json.dumps(trigger_data, indent=2))
    logger.info(f"Research trigger written: {filename} (queue_id={queue_id})")
    return filename


def select_spotlight_topic() -> dict:
    """Run the Spotlight selection heuristic and queue the best topic for research."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    config = _get_spotlight_config()
    logger.info(f"Spotlight selection: config={config}")

    topics = supabase.table('topic_evolution')\
        .select('*')\
        .order('last_updated', desc=True)\
        .limit(50)\
        .execute()

    if not topics.data:
        logger.info("Spotlight selection: no topics found")
        return {'selected': None, 'reason': 'no topics'}

    cooldown_topics = set()
    try:
        cooldown = get_spotlight_cooldown()
        cooldown_topics = {c.get('topic_id') for c in cooldown}
    except Exception as e:
        logger.warning(f"Could not fetch cooldown: {e}")

    # Theme diversity: penalize topics overlapping with recent newsletter themes
    recent_themes = get_recent_newsletter_themes(3)
    _stopwords = {'the', 'and', 'for', 'in', 'of', 'a', 'an', 'is', 'to', 'ai', 'agent', 'agents'}
    recent_theme_words = set()
    for theme in recent_themes:
        recent_theme_words.update(w for w in theme.split() if w not in _stopwords)

    candidates = []
    for topic in topics.data:
        topic_key = topic.get('topic_key', '')
        topic_id = topic.get('id', '')
        phase = topic.get('current_stage', 'emerging')

        if topic_id in cooldown_topics:
            continue

        velocity = _compute_velocity(topic)
        snapshots = topic.get('snapshots') or []
        recent_mentions = snapshots[-1].get('mentions', 0) if snapshots else 0
        recent_sources = snapshots[-1].get('sources', []) if snapshots else []

        if recent_mentions < config['min_mentions']:
            continue
        if len(set(recent_sources)) < config['min_source_tiers']:
            continue

        source_diversity = _compute_source_diversity(topic)
        lifecycle_bonus = LIFECYCLE_BONUS.get(phase, 1.0)
        spotlight_score = velocity * source_diversity * lifecycle_bonus

        # Theme diversity penalty: penalize topics that overlap with recent editions
        if recent_theme_words:
            topic_words = set(topic_key.lower().replace('-', '_').split('_')) - _stopwords
            theme_overlap = topic_words & recent_theme_words
            if len(theme_overlap) >= 2:
                spotlight_score *= 0.3
                logger.info(
                    f"Spotlight theme penalty (heavy) for '{topic_key}': "
                    f"overlaps recent themes on {theme_overlap}"
                )
            elif len(theme_overlap) == 1:
                spotlight_score *= 0.7
                logger.info(
                    f"Spotlight theme penalty (mild) for '{topic_key}': "
                    f"overlaps recent themes on {theme_overlap}"
                )

        related_keys = []
        for other in topics.data:
            if other.get('topic_key') == topic_key:
                continue
            other_kws = set(other.get('topic_key', '').split('_'))
            topic_kws = set(topic_key.split('_'))
            if len(topic_kws & other_kws) >= 1 and len(topic_kws & other_kws) / max(len(topic_kws | other_kws), 1) > 0.3:
                related_keys.append(other.get('topic_key'))

        candidates.append({
            'topic': topic,
            'topic_key': topic_key,
            'phase': phase,
            'velocity': round(velocity, 3),
            'source_diversity': round(source_diversity, 3),
            'lifecycle_bonus': lifecycle_bonus,
            'spotlight_score': round(spotlight_score, 3),
            'recent_mentions': recent_mentions,
            'related_topics': related_keys[:5],
        })

    candidates.sort(key=lambda c: c['spotlight_score'], reverse=True)

    # Observability: log filter funnel every run
    logger.info(
        f"Spotlight selection: {len(topics.data)} topics evaluated, "
        f"{len(candidates)} passed filters (min_mentions={config['min_mentions']}, "
        f"min_source_tiers={config['min_source_tiers']}), "
        f"cooldown_excluded={len(cooldown_topics)}"
    )
    if candidates:
        top5 = candidates[:5]
        for i, c in enumerate(top5):
            logger.info(
                f"  candidate #{i+1}: {c['topic_key']} "
                f"score={c['spotlight_score']} phase={c['phase']} "
                f"mentions={c['recent_mentions']} velocity={c['velocity']} "
                f"diversity={c['source_diversity']}"
            )

    if not candidates:
        # Fallback: pick highest-scoring topic ignoring mention/diversity minimums
        logger.warning("No topics passed eligibility filters — trying fallback selection")
        fallback_candidates = []
        for topic in topics.data:
            topic_key = topic.get('topic_key', '')
            topic_id = topic.get('id', '')
            if topic_id in cooldown_topics:
                continue
            velocity = _compute_velocity(topic)
            source_diversity = _compute_source_diversity(topic)
            phase = topic.get('current_stage', 'emerging')
            lifecycle_bonus = LIFECYCLE_BONUS.get(phase, 1.0)
            spotlight_score = velocity * source_diversity * lifecycle_bonus
            if spotlight_score > 0:
                fallback_candidates.append({
                    'topic': topic,
                    'topic_key': topic_key,
                    'phase': phase,
                    'velocity': round(velocity, 3),
                    'source_diversity': round(source_diversity, 3),
                    'lifecycle_bonus': lifecycle_bonus,
                    'spotlight_score': round(spotlight_score, 3),
                    'recent_mentions': (topic.get('snapshots') or [{}])[-1].get('mentions', 0) if topic.get('snapshots') else 0,
                    'related_topics': [],
                })
        if fallback_candidates:
            fallback_candidates.sort(key=lambda c: c['spotlight_score'], reverse=True)
            candidates = fallback_candidates
            logger.info(f"Fallback found {len(candidates)} candidates, best: {candidates[0]['topic_key']} (score={candidates[0]['spotlight_score']})")
        else:
            logger.info("Spotlight selection: no eligible candidates even with fallback")
            return {'selected': None, 'reason': 'all filtered out'}

    best = candidates[0]

    if best['spotlight_score'] >= config['min_score_threshold']:
        recent_mentions_data = _get_recent_mentions_for_context(best['topic_key'])
        context_payload = {
            'topic_id': best['topic_key'],
            'topic_name': best['topic_key'].replace('_', ' ').title(),
            'priority_score': best['spotlight_score'],
            'velocity': best['velocity'],
            'source_diversity': best['source_diversity'],
            'lifecycle_phase': best['phase'],
            'recent_mentions': recent_mentions_data,
            'contrarian_signals': [],
            'related_topics': best['related_topics'],
            'last_spotlighted': None,
        }

        queued = queue_research_topic(
            topic_id=best['topic_key'],
            topic_name=context_payload['topic_name'],
            priority_score=best['spotlight_score'],
            velocity=best['velocity'],
            source_diversity=best['source_diversity'],
            lifecycle_phase=best['phase'],
            context_payload=context_payload,
            mode='spotlight',
        )

        logger.info(f"Spotlight selected: '{best['topic_key']}' (score={best['spotlight_score']}, phase={best['phase']})")

        trigger_file = None
        if queued.get('id'):
            trigger_file = _write_research_trigger(
                queued['id'], context_payload['topic_name'], 'spotlight')

        return {
            'selected': best['topic_key'],
            'mode': 'spotlight',
            'score': best['spotlight_score'],
            'phase': best['phase'],
            'queue_id': queued.get('id'),
            'trigger_file': trigger_file,
            'candidates_evaluated': len(candidates),
        }

    else:
        top3 = candidates[:3]
        synthesis_topics = []
        all_mentions = []
        for c in top3:
            mentions = _get_recent_mentions_for_context(c['topic_key'], limit=3)
            all_mentions.extend(mentions)
            synthesis_topics.append({
                'topic_id': c['topic_key'],
                'topic_name': c['topic_key'].replace('_', ' ').title(),
                'score': c['spotlight_score'],
                'phase': c['phase'],
                'velocity': c['velocity'],
            })

        context_payload = {
            'topics': synthesis_topics,
            'recent_mentions': all_mentions[:10],
            'synthesis_reason': f"No single topic scored above {config['min_score_threshold']}. "
                                f"Top score was {best['spotlight_score']}.",
        }

        queued = queue_research_topic(
            topic_id='synthesis',
            topic_name='Landscape Synthesis',
            priority_score=best['spotlight_score'],
            context_payload=context_payload,
            mode='synthesis',
        )

        logger.info(f"Spotlight: synthesis mode — top 3 topics queued (best score={best['spotlight_score']})")

        trigger_file = None
        if queued.get('id'):
            trigger_file = _write_research_trigger(
                queued['id'], 'Landscape Synthesis', 'synthesis')

        return {
            'selected': [c['topic_key'] for c in top3],
            'mode': 'synthesis',
            'best_score': best['spotlight_score'],
            'threshold': config['min_score_threshold'],
            'queue_id': queued.get('id'),
            'trigger_file': trigger_file,
            'candidates_evaluated': len(candidates),
        }


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
            'completed_at': datetime.now(timezone.utc).isoformat(),
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
        
        # Peek at the task to decide routing — only skip files that are
        # direct agent work (write_newsletter, analyst tasks). Queue files
        # from Gato containing create_agent_task or other processor tasks
        # must NOT be skipped even if the filename starts with 'newsletter_'.
        try:
            _peek = json.loads(task_file.read_text())
            _peek_task = _peek.get('task', '')
            _peek_type = _peek.get('params', {}).get('task_type', '')
            if task_file.name.startswith('analyst_') and _peek_task not in ('create_agent_task', 'check_task'):
                continue
        except Exception as e:
            logger.warning(f"Task type peek skipped: {e}")
        
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
                'completed_at': datetime.now(timezone.utc).isoformat()
            }, indent=2))
            
        except Exception as e:
            logger.error(f"Task failed: {e}")
            result_file = RESPONSES_DIR / f"{task_file.stem}.result.json"
            result_file.write_text(json.dumps({
                'success': False,
                'error': str(e),
                'completed_at': datetime.now(timezone.utc).isoformat()
            }, indent=2))
        
        finally:
            task_file.unlink()  # Remove processed task

def _get_agent_api_key() -> str:
    """Return cached API key, or look it up from Supabase on first call."""
    global _agent_api_key
    if _agent_api_key:
        return _agent_api_key
    try:
        result = supabase.table("agent_api_keys").select("api_key").eq("agent_name", "processor").limit(1).execute()
        if result.data:
            _agent_api_key = result.data[0]["api_key"]
            return _agent_api_key
    except Exception:
        pass
    return ""


_economics_cache: str = ""
_economics_fetched_at: float = 0
_ECONOMICS_TTL = 300


def fetch_economics_block() -> str:
    """Fetch processor economics from proxy, cache it, log it.
    Non-blocking: returns empty string on any failure. 2-second timeout."""
    global _economics_cache, _economics_fetched_at

    now = time.time()
    if _economics_cache and (now - _economics_fetched_at) < _ECONOMICS_TTL:
        return _economics_cache

    api_key = _get_agent_api_key()
    if not api_key:
        return ""

    try:
        resp = httpx.get(
            f"{LLM_PROXY_URL}/v1/proxy/wallet/processor/summary?period=7d",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
        )
        if resp.status_code != 200:
            return _economics_cache
        d = resp.json()
        cap_sats = d.get("spending_cap_sats") or 0
        cap_window = d.get("spending_cap_window") or "n/a"
        util = d.get("budget_utilization_pct")
        util_str = f"{util}%" if util is not None else "no cap"
        trend_str = d.get("trend_vs_previous_period", "flat")
        _economics_cache = (
            "\n\n---\n"
            "YOUR ECONOMICS (last 7 days):\n"
            f"Balance: {d['balance_sats']:,} sats | Spent: {d['spent_sats']:,} sats | Calls: {d['calls']:,}\n"
            f"Budget utilization: {util_str} of {cap_sats:,} sats {cap_window} cap\n"
            f"Cap hits: {d.get('cap_hits_in_period', 0)} | Trend: {trend_str} vs prior week\n"
            "---"
        )
        _economics_fetched_at = now
        logger.info(
            f"[ECONOMICS] Balance: {d['balance_sats']:,} sats | "
            f"Spent: {d['spent_sats']:,} sats | Calls: {d['calls']:,} | "
            f"Utilization: {util_str} | Trend: {trend_str}"
        )
    except Exception as e:
        logger.debug(f"Economics fetch failed (non-critical): {e}")

    return _economics_cache


def log_economics_context():
    """Periodic scheduler hook — fetch and log economics."""
    fetch_economics_block()


def get_agent_wallets() -> dict:
    """Return all agent wallet balances."""
    if not supabase:
        return {'error': 'Supabase not configured'}
    try:
        result = supabase.table('agent_wallets_v2').select('*').order('agent_name').execute()
        return {'wallets': result.data or []}
    except Exception as e:
        return {'error': str(e)}


def get_agent_ledger(agent_name: str, limit: int = 10) -> dict:
    """Return recent transactions for an agent."""
    if not supabase:
        return {'error': 'Supabase not configured'}
    try:
        result = supabase.table('wallet_transactions') \
            .select('*') \
            .eq('agent_name', agent_name) \
            .order('created_at', desc=True) \
            .limit(limit) \
            .execute()
        return {'agent': agent_name, 'transactions': result.data or []}
    except Exception as e:
        return {'error': str(e)}


def topup_agent(agent_name: str, amount_sats: int) -> dict:
    """Top up an agent's wallet."""
    if not supabase:
        return {'error': 'Supabase not configured'}
    try:
        supabase.rpc('topup_agent_wallet', {
            'p_agent_name': agent_name,
            'p_amount_sats': amount_sats,
        }).execute()
        # Return updated balance
        result = supabase.table('agent_wallets').select('*').eq('agent_name', agent_name).execute()
        wallet = (result.data or [None])[0]
        return {'agent': agent_name, 'topped_up': amount_sats, 'wallet': wallet}
    except Exception as e:
        return {'error': str(e)}


def execute_task(task: dict) -> dict:
    """Execute a queued task."""
    task_type = task.get('task')
    params = task.get('params', {})
    
    if task_type == 'scrape':
        return scrape_moltbook(
            submolts=params.get('submolts'),
            posts_per_submolt=params.get('posts_per_submolt', 25)
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
    
    elif task_type == 'extract_trending_topics':
        return extract_trending_topics(hours_back=params.get('hours_back', 48))
    
    elif task_type == 'run_pipeline':
        # Full pipeline: scrape all sources → extract (multisource) → cluster → delegate analysis
        results = {}

        try:
            results['scrape_moltbook'] = scrape_moltbook()
        except Exception as e:
            logger.error(f"Pipeline scrape_moltbook failed: {e}")
            results['scrape_moltbook'] = {'error': str(e)}

        try:
            results['scrape_hackernews'] = scrape_hackernews()
        except Exception as e:
            logger.error(f"Pipeline scrape_hackernews failed: {e}")
            results['scrape_hackernews'] = {'error': str(e)}

        try:
            results['scrape_github'] = scrape_github()
        except Exception as e:
            logger.error(f"Pipeline scrape_github failed: {e}")
            results['scrape_github'] = {'error': str(e)}

        try:
            rss_result = scrape_rss_feeds()
            results['rss'] = rss_result
        except Exception as e:
            logger.error(f"RSS scrape failed in pipeline: {e}")
            results['rss'] = {'error': str(e)}

        try:
            results['thought_leaders'] = scrape_thought_leaders()
        except Exception as e:
            logger.error(f"Thought leader scrape failed in pipeline: {e}")
            results['thought_leaders'] = {'error': str(e)}

        try:
            results['x_source_accounts'] = scrape_x_source_accounts()
        except Exception as e:
            logger.error(f"X source account scan failed in pipeline: {e}")
            results['x_source_accounts'] = {'error': str(e)}

        try:
            results['extract'] = extract_problems_multisource()
        except Exception as e:
            logger.warning(f"Pipeline multisource problem extraction failed, falling back: {e}")
            try:
                results['extract'] = extract_problems()
            except Exception as e2:
                logger.error(f"Pipeline extract_problems fallback failed: {e2}")
                results['extract'] = {'error': str(e2)}

        try:
            results['tools'] = extract_tools_multisource()
        except Exception as e:
            logger.warning(f"Pipeline multisource tool extraction failed, falling back: {e}")
            try:
                results['tools'] = extract_tool_mentions()
            except Exception as e2:
                logger.error(f"Pipeline extract_tool_mentions fallback failed: {e2}")
                results['tools'] = {'error': str(e2)}

        try:
            results['trending'] = extract_trending_topics_multisource()
        except Exception as e:
            logger.warning(f"Pipeline multisource trending extraction failed, falling back: {e}")
            try:
                results['trending'] = extract_trending_topics()
            except Exception as e2:
                logger.error(f"Pipeline extract_trending_topics fallback failed: {e2}")
                results['trending'] = {'error': str(e2)}

        try:
            results['cluster'] = cluster_problems()
        except Exception as e:
            logger.error(f"Pipeline cluster_problems failed: {e}")
            results['cluster'] = {'error': str(e)}

        try:
            evolution_result = update_topic_evolution()
            results['topic_evolution'] = evolution_result
        except Exception as e:
            logger.error(f"Topic evolution failed in pipeline: {e}")
            results['topic_evolution'] = {'error': str(e)}

        try:
            results['spotlight_selection'] = select_spotlight_topic()
        except Exception as e:
            logger.error(f"Spotlight selection failed in pipeline: {e}")
            results['spotlight_selection'] = {'error': str(e)}

        try:
            results['analysis'] = prepare_analysis_package()
        except Exception as e:
            logger.error(f"Pipeline prepare_analysis_package failed: {e}")
            results['analysis'] = {'error': str(e)}

        return results
    
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
    
    elif task_type == 'prepare_analysis':
        return prepare_analysis_package(hours_back=params.get('hours_back', 48))
    
    elif task_type == 'prepare_newsletter':
        return prepare_newsletter_data()
    
    elif task_type == 'publish_newsletter':
        return publish_newsletter()

    elif task_type == 'retry_failed_emails':
        return retry_failed_emails(edition=params.get('edition'))

    elif task_type == 'create_predictions':
        return create_predictions_from_newsletter(params.get('newsletter_id'))
    
    elif task_type == 'get_latest_newsletter':
        return get_latest_newsletter()
    
    elif task_type == 'get_tool_stats':
        if not supabase:
            return {'error': 'Supabase not configured'}
        limit = params.get('limit', 10)
        result = supabase.table('tool_stats') \
            .select('*') \
            .order('total_mentions', desc=True) \
            .limit(limit) \
            .execute()
        return {'tools': result.data or []}
    
    elif task_type == 'get_tool_detail':
        if not supabase:
            return {'error': 'Supabase not configured'}
        tool_name = params.get('tool_name', '')
        stats = supabase.table('tool_stats') \
            .select('*') \
            .ilike('tool_name', tool_name) \
            .limit(1) \
            .execute()
        mentions = supabase.table('tool_mentions') \
            .select('*') \
            .ilike('tool_name', tool_name) \
            .order('created_at', desc=True) \
            .limit(10) \
            .execute()
        return {
            'stats': stats.data[0] if stats.data else None,
            'recent_mentions': mentions.data or []
        }
    
    elif task_type == 'get_trending_topics':
        if not supabase:
            return {'error': 'Supabase not configured'}
        limit = params.get('limit', 5)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        result = supabase.table('trending_topics') \
            .select('*') \
            .gte('extracted_at', cutoff) \
            .order('novelty_score', desc=True) \
            .limit(limit) \
            .execute()
        return {'topics': result.data or [], 'count': len(result.data or [])}
    
    elif task_type == 'get_latest_analysis':
        if not supabase:
            return {'error': 'Supabase not configured'}
        result = supabase.table('analysis_runs') \
            .select('*') \
            .eq('status', 'completed') \
            .order('completed_at', desc=True) \
            .limit(1) \
            .execute()
        if result.data:
            return result.data[0]
        return {'error': 'No completed analysis runs found'}
    
    elif task_type == 'get_cross_signals':
        if not supabase:
            return {'error': 'Supabase not configured'}
        limit = params.get('limit', 10)
        result = supabase.table('cross_signals') \
            .select('*') \
            .eq('status', 'active') \
            .order('strength', desc=True) \
            .limit(limit) \
            .execute()
        return {'signals': result.data or [], 'count': len(result.data or [])}
    
    elif task_type == 'get_opportunities':
        return get_current_opportunities(
            limit=params.get('limit', 5),
            min_score=params.get('min_score', 0.0)
        )
    
    elif task_type == 'get_topic_evolution':
        if not supabase:
            return {'error': 'Supabase not configured'}
        limit = params.get('limit', 10)
        result = supabase.table('topic_evolution') \
            .select('*') \
            .order('last_updated', desc=True) \
            .limit(limit) \
            .execute()
        return {'topics': result.data or [], 'count': len(result.data or [])}
    
    elif task_type == 'get_topic_thesis':
        if not supabase:
            return {'error': 'Supabase not configured'}
        topic = params.get('topic', '')
        result = supabase.table('topic_evolution') \
            .select('*') \
            .ilike('topic_key', f'%{topic}%') \
            .limit(1) \
            .execute()
        if result.data:
            row = result.data[0]
            return {
                'topic_key': row.get('topic_key'),
                'thesis': row.get('thesis'),
                'confidence': row.get('confidence'),
                'stage': row.get('stage'),
                'snapshots': row.get('snapshots', [])[-5:],
            }
        return {'error': f'No topic found matching "{topic}"'}
    
    elif task_type == 'get_freshness_status':
        if not supabase:
            return {'error': 'Supabase not configured'}
        excluded_ids = get_excluded_opportunity_ids(2)
        excluded_titles = []
        if excluded_ids:
            id_list = list(excluded_ids)
            rows = supabase.table('opportunities') \
                .select('title') \
                .in_('id', id_list) \
                .execute()
            excluded_titles = [r['title'] for r in (rows.data or [])]
        featured_titles = list(get_previously_featured_titles(4))
        return {
            'excluded_from_next_edition': excluded_titles,
            'recently_featured_count': len(featured_titles),
            'editions_checked': 4
        }
    
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
    
    elif task_type == 'targeted_scrape':
        submolts = params.get('submolts', [])[:3]
        posts_per = min(params.get('posts_per_submolt', 25), 25)
        reason = params.get('reason', 'agent_request')

        results = {}
        for submolt in submolts:
            try:
                posts = fetch_moltbook_posts(submolt=submolt, limit=posts_per)
                new_count = 0
                for post in posts:
                    try:
                        if store_post(post, submolt_override=submolt):
                            new_count += 1
                    except Exception as e:
                        logger.error(f"Error storing targeted post: {e}")
                results[submolt] = {'fetched': len(posts), 'new': new_count}
            except Exception as e:
                logger.error(f"Targeted scrape failed for submolt '{submolt}': {e}")
                results[submolt] = {'error': str(e)}

        extract_result = extract_problems(hours_back=1)

        return {
            'scrape': results,
            'extract': extract_result,
            'triggered_by': reason
        }
    
    elif task_type == 'can_create_subtask':
        if not supabase:
            return {'can_create': True, 'pending_tasks': 0, 'reason': 'no_supabase'}
        pending = supabase.table('agent_tasks')\
            .select('id', count='exact')\
            .eq('status', 'pending')\
            .execute()
        count = pending.count or 0
        return {
            'can_create': count < 10,
            'pending_tasks': count,
            'reason': 'processor_overloaded' if count >= 10 else 'ok'
        }
    
    elif task_type == 'send_alert':
        message = params.get('alert_message', 'Unknown alert')
        send_telegram(f"⚠️ Proactive Alert\n\n{message}")
        increment_daily_usage('system', alerts=1)
        return {'sent': True}
    
    elif task_type == 'proactive_scan':
        return proactive_scan()
    
    elif task_type == 'create_negotiation':
        return create_negotiation(
            requesting_agent=params.get('requesting_agent', ''),
            responding_agent=params.get('responding_agent', ''),
            request_task_id=params.get('request_task_id', ''),
            request_summary=params.get('request_summary', ''),
            quality_criteria=params.get('quality_criteria', ''),
            needed_by=params.get('needed_by'),
        )
    
    elif task_type == 'respond_to_negotiation':
        return respond_to_negotiation(
            negotiation_id=params.get('negotiation_id', ''),
            response_task_id=params.get('response_task_id', ''),
            criteria_met=params.get('criteria_met', False),
            response_summary=params.get('response_summary', ''),
        )
    
    elif task_type == 'get_active_negotiations':
        if not supabase:
            return {'error': 'Supabase not configured'}
        agent = params.get('agent_name')
        query = supabase.table('agent_negotiations')\
            .select('*')\
            .in_('status', ['open', 'follow_up'])\
            .order('created_at', desc=True)
        if agent:
            query = query.or_(f"requesting_agent.eq.{agent},responding_agent.eq.{agent}")
        result = query.execute()
        return {'negotiations': result.data or [], 'count': len(result.data or [])}
    
    elif task_type == 'check_negotiation_timeouts':
        check_negotiation_timeouts()
        return {'checked': True}
    
    elif task_type == 'get_recent_alerts':
        if not supabase:
            return {'error': 'Supabase not configured'}
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        result = supabase.table('agent_tasks')\
            .select('id, created_at, input_data, output_data')\
            .eq('task_type', 'send_alert')\
            .gte('created_at', cutoff)\
            .order('created_at', desc=True)\
            .limit(10)\
            .execute()
        alerts = []
        for row in result.data or []:
            input_d = row.get('input_data') or {}
            alerts.append({
                'timestamp': row.get('created_at'),
                'message': input_d.get('alert_message', ''),
                'anomaly_type': input_d.get('anomaly_type'),
            })
        return {'alerts': alerts, 'count': len(alerts)}
    
    elif task_type == 'get_budget_status':
        return get_daily_usage()
    
    elif task_type == 'get_budget_config':
        return get_full_config().get('budgets', {})
    
    elif task_type == 'deduplicate_opportunities':
        return deduplicate_opportunities()
    
    elif task_type == 'scrape_hackernews':
        return scrape_hackernews(limit=params.get('limit', 200))
    
    elif task_type == 'scrape_github':
        return scrape_github(days_back=params.get('days_back', 7))
    
    elif task_type == 'get_predictions':
        if not supabase:
            return {'error': 'Supabase not configured'}
        limit = params.get('limit', 10)
        result = supabase.table('predictions') \
            .select('*') \
            .order('status', desc=False) \
            .order('created_at', desc=True) \
            .limit(limit) \
            .execute()
        return {'predictions': result.data or []}
    
    elif task_type == 'get_source_status':
        if not supabase:
            return {'error': 'Supabase not configured'}
        now = datetime.now(timezone.utc)
        day_ago = (now - timedelta(hours=24)).isoformat()
        sources_status = {}
        for src in ('moltbook', 'hackernews', 'github'):
            total_result = supabase.table('source_posts') \
                .select('id', count='exact') \
                .eq('source', src) \
                .execute()
            recent_result = supabase.table('source_posts') \
                .select('id', count='exact') \
                .eq('source', src) \
                .gte('scraped_at', day_ago) \
                .execute()
            latest_result = supabase.table('source_posts') \
                .select('scraped_at') \
                .eq('source', src) \
                .order('scraped_at', desc=True) \
                .limit(1) \
                .execute()
            sources_status[src] = {
                'total_posts': total_result.count or 0,
                'last_24h': recent_result.count or 0,
                'last_scraped': latest_result.data[0]['scraped_at'] if latest_result.data else None,
            }
        legacy_result = supabase.table('moltbook_posts') \
            .select('id', count='exact') \
            .execute()
        sources_status['moltbook_legacy'] = {
            'total_posts': legacy_result.count or 0,
        }
        tl_total = supabase.table('source_posts') \
            .select('id', count='exact') \
            .like('source', 'thought_leader_%') \
            .execute()
        tl_recent = supabase.table('source_posts') \
            .select('id', count='exact') \
            .like('source', 'thought_leader_%') \
            .gte('scraped_at', day_ago) \
            .execute()
        sources_status['thought_leaders'] = {
            'total_posts': tl_total.count or 0,
            'last_24h': tl_recent.count or 0,
            'tier': 1.5,
        }
        return {'sources': sources_status}
    
    elif task_type == 'create_manual_prediction':
        if not supabase:
            return {'error': 'Supabase not configured'}
        title = params.get('title', 'Untitled prediction')
        description = params.get('description', '')
        pred_type = params.get('prediction_type', 'manual')
        confidence = params.get('initial_confidence', 0.5)
        result = supabase.table('predictions').insert({
            'prediction_type': pred_type,
            'title': title,
            'description': description[:500],
            'initial_confidence': confidence,
            'current_score': confidence,
            'status': 'active',
            'tracking_history': json.dumps([{
                'date': datetime.now(timezone.utc).isoformat(),
                'event': 'created',
                'confidence': confidence,
                'notes': 'Manually created prediction'
            }], default=str)
        }).execute()
        return {'prediction': result.data[0] if result.data else None}
    
    elif task_type == 'scrape_rss':
        return scrape_rss_feeds()

    elif task_type == 'scrape_thought_leaders':
        return scrape_thought_leaders()

    elif task_type == 'scrape_x_source_accounts':
        return scrape_x_source_accounts()

    elif task_type == 'track_predictions':
        return track_predictions()
    
    elif task_type == 'extract_problems_multisource':
        return extract_problems_multisource(hours_back=params.get('hours_back', 48))
    
    elif task_type == 'extract_tools_multisource':
        return extract_tools_multisource(hours_back=params.get('hours_back', 48))
    
    elif task_type == 'extract_trending_topics_multisource':
        return extract_trending_topics_multisource(hours_back=params.get('hours_back', 48))
    
    elif task_type == 'update_topic_evolution':
        return update_topic_evolution()
    
    elif task_type == 'queue_research':
        return queue_research_topic(
            topic_id=params.get('topic_id', ''),
            topic_name=params.get('topic_name', ''),
            priority_score=params.get('priority_score', 0.5),
            velocity=params.get('velocity'),
            source_diversity=params.get('source_diversity'),
            lifecycle_phase=params.get('lifecycle_phase'),
            context_payload=params.get('context_payload'),
            mode=params.get('mode', 'spotlight'),
            issue_number=params.get('issue_number'),
        )

    elif task_type == 'get_research_queue':
        return {'queue': get_research_queue(
            status=params.get('status', 'queued'),
            limit=params.get('limit', 5),
        )}

    elif task_type == 'get_spotlight':
        return get_latest_spotlight(issue_number=params.get('issue_number'))

    elif task_type == 'get_scorecard':
        return get_scorecard(limit=params.get('limit', 20))

    elif task_type == 'get_spotlight_cooldown':
        return {'cooldown_topics': get_spotlight_cooldown()}

    elif task_type == 'select_spotlight':
        return select_spotlight_topic()

    elif task_type == 'run_research':
        import subprocess
        result = subprocess.run(
            ['python3', '-c',
             'import sys; sys.path.insert(0, "/home/openclaw"); '
             'from research_agent import init, run_once; init(); run_once()'],
            capture_output=True, text=True, timeout=360,
        )
        return {
            'stdout': result.stdout[-2000:] if result.stdout else '',
            'stderr': result.stderr[-2000:] if result.stderr else '',
            'returncode': result.returncode,
        }

    elif task_type == 'flag_prediction':
        return flag_prediction(
            prediction_id=params.get('prediction_id', ''),
            evidence_notes=params.get('evidence_notes', ''),
        )

    elif task_type == 'resolve_prediction':
        return resolve_prediction(
            prediction_id=params.get('prediction_id', ''),
            status=params.get('resolution_status', 'confirmed'),
            resolution_notes=params.get('resolution_notes', ''),
            scorecard_issue=params.get('scorecard_issue'),
        )

    elif task_type == 'get_subscriber_stats':
        if not supabase:
            return {'error': 'Supabase not configured'}
        total = supabase.table('subscribers').select('id', count='exact').execute()
        active = supabase.table('subscribers').select('id', count='exact').eq('status', 'active').execute()
        pending = supabase.table('subscribers').select('id', count='exact').eq('status', 'pending').execute()
        builder_pref = supabase.table('subscribers').select('id', count='exact').eq('mode_preference', 'builder').eq('status', 'active').execute()
        impact_pref = supabase.table('subscribers').select('id', count='exact').eq('mode_preference', 'impact').eq('status', 'active').execute()
        both_pref = supabase.table('subscribers').select('id', count='exact').eq('mode_preference', 'both').eq('status', 'active').execute()
        return {
            'total': total.count or 0,
            'active': active.count or 0,
            'pending': pending.count or 0,
            'mode_breakdown': {
                'builder': builder_pref.count or 0,
                'impact': impact_pref.count or 0,
                'both': both_pref.count or 0,
            }
        }

    elif task_type == 'personal_briefing':
        return generate_personal_briefing()

    elif task_type == 'get_operator_context':
        return get_operator_context()

    elif task_type == 'add_watch_topic':
        topic = params.get('topic', '')
        if not topic:
            return {'error': 'No topic provided'}
        return add_watch_topic(topic)

    elif task_type == 'get_agent_wallets':
        return get_agent_wallets()

    elif task_type == 'get_agent_ledger':
        return get_agent_ledger(
            agent_name=params.get('agent_name', 'processor'),
            limit=params.get('limit', 10),
        )

    elif task_type == 'topup_agent':
        agent = params.get('agent_name', '')
        amount = params.get('amount_sats', 0)
        if not agent or not amount:
            return {'error': 'agent_name and amount_sats required'}
        return topup_agent(agent, int(amount))

    # ── X Distribution Pipeline ──
    # NOTE: /x-* operator commands (approve, reject, draft, plan, etc.) are handled
    # directly by gato_brain. Only pipeline tasks remain here.
    elif task_type == 'surface_x_candidates':
        return surface_x_content_candidates()

    elif task_type == 'post_approved_x':
        return post_approved_x_content()

    else:
        return {'error': f'Unknown task: {task_type}'}

# ============================================================================
# X Content Distribution Pipeline
# ============================================================================

def _get_x_week_start() -> str:
    """Return the Monday date string for the current tracking week."""
    today = datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())
    return monday.isoformat()


def get_x_budget_status() -> dict:
    """Get current X API budget usage for the week and month."""
    if not supabase:
        return {'error': 'Supabase not configured'}
    week_start = _get_x_week_start()
    try:
        week_rows = supabase.table('x_api_budget')\
            .select('estimated_cost, request_count')\
            .eq('week_start', week_start)\
            .execute()
        week_spent = sum(float(r.get('estimated_cost', 0)) for r in (week_rows.data or []))
        week_calls = sum(int(r.get('request_count', 0)) for r in (week_rows.data or []))

        # Monthly total (last 4 weeks)
        month_ago = (datetime.now(timezone.utc).date() - timedelta(days=28)).isoformat()
        month_rows = supabase.table('x_api_budget')\
            .select('estimated_cost')\
            .gte('week_start', month_ago)\
            .execute()
        month_spent = sum(float(r.get('estimated_cost', 0)) for r in (month_rows.data or []))

        return {
            'week_start': week_start,
            'week_spent': round(week_spent, 4),
            'week_limit': X_WEEKLY_BUDGET,
            'week_calls': week_calls,
            'week_remaining': round(X_WEEKLY_BUDGET - week_spent, 4),
            'month_spent': round(month_spent, 4),
            'month_limit': 20.0,
            'budget_ok': week_spent < X_WEEKLY_BUDGET,
        }
    except Exception as e:
        logger.error(f"X budget check failed: {e}")
        return {'error': str(e)}


def _check_x_budget() -> bool:
    """Return True if we still have X API budget this week."""
    status = get_x_budget_status()
    return status.get('budget_ok', False)


def _log_x_api_cost(operation_type: str, endpoint: str, cost: float, notes: str = ''):
    """Log a single X API call cost to x_api_budget."""
    if not supabase:
        return
    try:
        supabase.table('x_api_budget').insert({
            'week_start': _get_x_week_start(),
            'operation_type': operation_type,
            'endpoint': endpoint,
            'estimated_cost': cost,
            'request_count': 1,
            'notes': notes,
        }).execute()
    except Exception as e:
        logger.warning(f"Failed to log X API cost: {e}")


def _x_api_search(query: str, max_results: int = 10) -> list:
    """Search X API v2 for recent tweets. Returns list of tweet dicts or empty list."""
    if not X_BEARER_TOKEN:
        logger.warning("X_BEARER_TOKEN not set — skipping X search")
        return []

    if not _check_x_budget():
        logger.info("X API weekly budget exhausted — skipping search")
        return []

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                'https://api.x.com/2/tweets/search/recent',
                headers={'Authorization': f'Bearer {X_BEARER_TOKEN}'},
                params={
                    'query': query,
                    'max_results': min(max_results, 100),
                    'tweet.fields': 'created_at,public_metrics,author_id,text',
                    'expansions': 'author_id',
                    'user.fields': 'username,name',
                },
            )
            _log_x_api_cost('search', '/2/tweets/search/recent', X_SEARCH_COST_ESTIMATE,
                            f"query: {query[:80]}")

            if resp.status_code != 200:
                logger.error(f"X search failed ({resp.status_code}): {resp.text[:200]}")
                return []

            data = resp.json()
            tweets = data.get('data', [])
            # Attach author usernames from includes
            users_by_id = {}
            for u in (data.get('includes', {}).get('users', [])):
                users_by_id[u['id']] = u
            for tw in tweets:
                author = users_by_id.get(tw.get('author_id'), {})
                tw['author_username'] = author.get('username', '')
                tw['author_name'] = author.get('name', '')
            return tweets
    except Exception as e:
        logger.error(f"X API search error: {e}")
        return []


def _post_tweet(text: str, reply_to: str = None) -> dict:
    """Post a tweet via X API v2 using tweepy. Returns {'id': ..., 'text': ...} or {'error': ...}."""
    if not X_API_KEY or not X_API_SECRET or not X_ACCESS_TOKEN or not X_ACCESS_TOKEN_SECRET:
        return {'error': 'X API credentials not configured'}

    try:
        import tweepy

        client = tweepy.Client(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_TOKEN_SECRET,
        )

        kwargs = {'text': text}
        if reply_to:
            kwargs['in_reply_to_tweet_id'] = reply_to

        resp = client.create_tweet(**kwargs)

        _log_x_api_cost('post', '/2/tweets', 0.0, f"post: {text[:50]}")

        tweet_data = resp.data
        logger.info(f"Tweet posted: {tweet_data['id']}")
        return {'id': str(tweet_data['id']), 'text': text}

    except tweepy.errors.TweepyException as e:
        logger.error(f"Tweet post failed: {e}")
        return {'error': str(e)}
    except Exception as e:
        logger.error(f"Tweet post error: {e}")
        return {'error': str(e)}


def _get_active_editorial_arc() -> dict | None:
    """Fetch the current active editorial arc, if any."""
    if not supabase:
        return None
    try:
        result = supabase.table('x_editorial_arc')\
            .select('*')\
            .eq('status', 'active')\
            .order('week_start', desc=True)\
            .limit(1)\
            .execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.warning(f"Failed to fetch active editorial arc: {e}")
        return None


def _get_todays_arc_entry(arc: dict) -> dict | None:
    """Return the full post_sequence entry for today, if any.

    Supports week-aware sequences: {"day": "wed", "week": 1, "angle": "...",
    "continuity": "...", "engagement_keywords": [...], "cta": "..."}
    Calculates current week number relative to arc's week_start.
    If entries have no 'week' field, matches on day only (backwards-compatible).
    """
    if not arc:
        return None
    sequence = arc.get('post_sequence') or []
    if isinstance(sequence, str):
        try:
            sequence = json.loads(sequence)
        except Exception:
            return None

    now = datetime.now(timezone.utc)
    day_abbr = now.strftime('%a').lower()[:3]

    # Calculate current week number (1-based) relative to week_start
    week_start = arc.get('week_start')
    current_week = 1
    if week_start:
        try:
            if isinstance(week_start, str):
                ws = datetime.strptime(week_start, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            else:
                ws = datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc)
            days_elapsed = (now - ws).days
            current_week = max(1, (days_elapsed // 7) + 1)
        except Exception:
            current_week = 1

    # First try matching day + week
    for entry in sequence:
        entry_day = entry.get('day', '').lower()[:3]
        entry_week = entry.get('week')
        if entry_day == day_abbr:
            if entry_week is not None and int(entry_week) == current_week:
                return entry

    # Fallback: match day only (for entries without a week field)
    for entry in sequence:
        entry_day = entry.get('day', '').lower()[:3]
        if entry_day == day_abbr and entry.get('week') is None:
            return entry

    return None


def surface_x_content_candidates() -> dict:
    """Daily content candidate surfacing for X distribution.

    Runs each morning: scans analyst output, engagement targets, and predictions
    to create x_content_candidates rows for operator review.
    Arc-aware: reads the active editorial arc to generate narrative + opportunistic posts.
    """
    if not supabase:
        return {'error': 'Supabase not configured'}

    day_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    candidates_created = 0

    # ── Load active editorial arc ──
    active_arc = _get_active_editorial_arc()
    arc_context = ''
    if active_arc:
        arc_context = (
            f"\n\nACTIVE EDITORIAL ARC:\n"
            f"Pillar: {active_arc.get('pillar', '')}\n"
            f"Title: {active_arc.get('arc_title', '')}\n"
            f"Thesis: {active_arc.get('arc_thesis', '')}\n"
            f"Overarching thesis: {active_arc.get('overarching_thesis', '')}\n"
        )
        todays_entry = _get_todays_arc_entry(active_arc)
        if todays_entry:
            arc_context += f"Today's planned angle: {todays_entry.get('angle', '')}\n"

    # ── Source 1: Sharp takes from recent analysis and source posts ──
    try:
        # Get recent high-signal source posts
        recent_posts = supabase.table('source_posts')\
            .select('title, source_url, source, body')\
            .gte('scraped_at', day_ago)\
            .order('scraped_at', desc=True)\
            .limit(20)\
            .execute()
        posts = recent_posts.data or []

        # Get latest analyst insights
        latest_analysis = supabase.table('analysis_runs')\
            .select('key_findings, analyst_notes, metadata')\
            .eq('status', 'completed')\
            .order('completed_at', desc=True)\
            .limit(1)\
            .execute()
        analyst_context = ''
        if latest_analysis.data:
            a = latest_analysis.data[0]
            analyst_context = f"\nAnalyst findings: {a.get('key_findings', '')}\nNotes: {a.get('analyst_notes', '')}"

        if posts:
            # Use DeepSeek to pick top 3-5 and generate take angles
            post_text = '\n'.join(
                f"- [{p.get('source', '?')}] {p.get('title', '')}: {(p.get('body') or '')[:200]} | URL: {p.get('source_url', '')}"
                for p in posts[:15]
            )

            arc_instructions = ''
            if active_arc:
                arc_instructions = f"""
IMPORTANT — EDITORIAL ARC CONTEXT:
{arc_context}

You must classify each candidate as either "narrative" or "opportunistic":
- "narrative": directly advances the active arc's thesis on '{active_arc.get('pillar', '')}'. Prioritize news items related to the arc pillar and thesis.
- "opportunistic": trending/notable news that you can tie back to the overarching thesis: "{active_arc.get('overarching_thesis', '')}"

For EACH candidate, include a "narrative_context" field (1-2 sentences) explaining how this post advances or connects to the editorial arc.
Target: 1-2 narrative posts + 1-2 opportunistic posts."""

            prompt = f"""You are writing X/Twitter posts for @diegolancha. He writes about the agent economy — the economics and trust infrastructure of autonomous AI agents.
From these recent items, select the 3-5 most notable for the agent economy space.
For each, provide a sharp take angle — not a news summary, but an opinion on WHY this matters.
{analyst_context}
{arc_instructions}

Recent items:
{post_text}

Respond as JSON array:
[{{"source_url": "...", "source_summary": "1-2 sentence summary", "suggested_angle": "your opinionated take angle", "draft_content": ["tweet 1 text", "tweet 2 text"], "suggested_tags": ["handle1", "handle2"], "content_category": "narrative|opportunistic", "narrative_context": "how this advances the arc"}}]

Rules:
- Only select items genuinely notable for the AI agent ecosystem
- Take angles should be provocative, insightful, or contrarian — not bland summaries
- draft_content must be a JSON array of 2 tweet strings forming a thread:
  TWEET 1 (the take — NO outbound links):
  - Open with what happened or what was found, in plain language (1-2 sentences of context)
  - Then give the opinionated take — why this matters for agent economics or trust
  - Under 280 characters. No hashtags, no emojis.
  TWEET 2 (the punch + source):
  - The sharpest single-sentence conclusion or implication
  - End with: Source: <source_url>
  - Under 280 characters
- VOICE:
  - First person where natural ("I think", "this is why I built")
  - Conversational, like explaining to a smart friend — not presenting to a conference
  - Short sentences. Break up dense ideas.
  - Replace jargon with plain language: "burning compute on chaos" > "suboptimal resource allocation"
  - Be opinionated and direct, not neutral
  - Never use: "game-changer", "paradigm shift", "deep dive", "here's the thing", "buckle up", "let that sink in"
  - Hedging is fine when genuine: "so far", "I'm still figuring this out", "early signal but"
- suggested_tags: X handles of people/orgs mentioned (without @), or empty array
- If fewer than 3 items are notable, return fewer. Quality over quantity.
- content_category and narrative_context are required if an editorial arc is active."""

            model = get_model('extraction')
            response = routed_llm_call(model, [
                {'role': 'system', 'content': 'You output valid JSON arrays only.'},
                {'role': 'user', 'content': prompt},
            ], temperature=0.4, max_tokens=2000)

            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if raw.startswith('```'):
                raw = re.sub(r'^```\w*\n?', '', raw)
                raw = re.sub(r'\n?```$', '', raw)
            takes = json.loads(raw)

            # Build set of known source URLs from ingested posts
            known_source_urls = {p.get('source_url') for p in posts if p.get('source_url')}

            for take in takes[:5]:
                # Enforce source_url: must exist and match an actual ingested post
                candidate_url = (take.get('source_url') or '').strip()
                if not candidate_url or candidate_url not in known_source_urls:
                    logger.warning(f"Skipping sharp_take candidate — no valid source_url: {take.get('source_summary', '')[:80]}")
                    continue

                # Run through verification gate
                v_status = 'pending'
                v_notes = None
                verification = verify_briefing_references({
                    'content_markdown': f"**{take.get('source_summary', '')}** {take.get('suggested_angle', '')}",
                    'data_snapshot': {'source_posts': posts},
                })
                if not verification['ok']:
                    v_status = 'flagged'
                    v_notes = '; '.join(verification.get('unverified', [])[:3])

                # Normalize draft_content: if it's a list, JSON-encode for thread storage
                raw_draft = take.get('draft_content', '')
                if isinstance(raw_draft, list):
                    draft_content = json.dumps(raw_draft)
                else:
                    draft_content = str(raw_draft) if raw_draft else ''

                insert_data = {
                    'content_type': 'sharp_take',
                    'source_url': candidate_url,
                    'source_summary': take.get('source_summary'),
                    'suggested_angle': take.get('suggested_angle'),
                    'draft_content': draft_content,
                    'suggested_tags': take.get('suggested_tags', []),
                    'verification_status': v_status,
                    'verification_notes': v_notes,
                }
                # Add arc-aware fields if arc is active
                if active_arc:
                    insert_data['narrative_context'] = take.get('narrative_context', '')
                    insert_data['content_category'] = take.get('content_category', 'opportunistic')

                supabase.table('x_content_candidates').insert(insert_data).execute()
                candidates_created += 1

    except Exception as e:
        logger.error(f"X sharp take surfacing failed: {e}")

    # ── Source 1b: Narrative posts from arc post_sequence ──
    todays_entry = None
    if active_arc:
        try:
            todays_entry = _get_todays_arc_entry(active_arc)
            if todays_entry:
                todays_angle = todays_entry.get('angle', '')
                continuity = todays_entry.get('continuity')
                cta = todays_entry.get('cta')

                continuity_instruction = ''
                if continuity:
                    continuity_instruction = f"""
CONTINUITY: This post follows a previous one. Open with this callback context:
"{continuity}"
Weave it naturally into the first line — don't just paste it verbatim."""

                cta_instruction = ''
                if cta:
                    cta_instruction = f"""
CTA: End the post (or final tweet in a thread) with this call-to-action:
"{cta}"
Integrate it naturally as the closer — not a jarring ad."""

                narrative_prompt = f"""You are writing an X/Twitter post for @diegolancha about his own experience building an AI agent pipeline called AgentPulse.

EDITORIAL ARC:
Title: {active_arc.get('arc_title', '')}
Pillar: {active_arc.get('pillar', '')}
ARC THESIS: {active_arc.get('arc_thesis', '')}
Overarching thesis: {active_arc.get('overarching_thesis', '')}

TODAY'S ANGLE: {todays_angle}
{analyst_context}
{continuity_instruction}
{cta_instruction}

Write a 2-3 tweet thread:

TWEET 1:
- If continuity was provided above, open with a natural callback (not "as I mentioned" — more like "Last week I showed you X. Today it gets worse.")
- State what you did or found, with specific numbers if in the angle
- Under 280 characters

TWEET 2:
- The insight or lesson — what this means beyond your own pipeline
- Connect to the broader agent economy
- Under 280 characters

TWEET 3 (only if a CTA was provided above):
- The CTA, framed naturally: "I wrote up the full technical breakdown in this week's AgentPulse: [link]"
- Under 280 characters

Respond as JSON:
{{"draft_content": ["tweet 1", "tweet 2"] or ["tweet 1", "tweet 2", "tweet 3"], "suggested_angle": "the angle executed", "narrative_context": "how this advances the arc"}}

VOICE RULES:
- First person always — this is your personal experience
- "I built", "I found", "my agent did X" — not "one might observe"
- Specific > general: "13,000 API calls per day" > "excessive API usage"
- Honest about uncertainty: "I'm not sure this scales" > "this is the future"
- Short paragraphs. One idea per tweet. Breathing room between thoughts.
- Never use: "game-changer", "paradigm shift", "deep dive", "here's the thing", "buckle up", "let that sink in"
- No hashtags. No emojis."""

                # Use GPT-4o for editorial quality on narrative posts
                response = routed_llm_call('gpt-4o', [
                    {'role': 'system', 'content': 'You output valid JSON only.'},
                    {'role': 'user', 'content': narrative_prompt},
                ], temperature=0.5, max_tokens=1000)

                raw = response.choices[0].message.content.strip()
                if raw.startswith('```'):
                    raw = re.sub(r'^```\w*\n?', '', raw)
                    raw = re.sub(r'\n?```$', '', raw)
                narrative = json.loads(raw)

                raw_draft = narrative.get('draft_content', '')
                if isinstance(raw_draft, list):
                    draft_content = json.dumps(raw_draft)
                else:
                    draft_content = str(raw_draft) if raw_draft else ''

                supabase.table('x_content_candidates').insert({
                    'content_type': 'narrative',
                    'source_summary': f"[ARC] {active_arc.get('arc_title', '')}: {todays_angle}",
                    'suggested_angle': narrative.get('suggested_angle', todays_angle),
                    'draft_content': draft_content,
                    'suggested_tags': [],
                    'verification_status': 'verified',
                    'narrative_context': narrative.get('narrative_context', ''),
                    'content_category': 'narrative',
                }).execute()
                candidates_created += 1
                logger.info(f"Generated narrative arc post for: {todays_angle}")

        except Exception as e:
            logger.error(f"X narrative arc post generation failed: {e}")

    # ── Source 2: Engagement targets from X API search ──
    if _check_x_budget():
        try:
            # Watchlist batch scan
            watchlist = supabase.table('x_watchlist')\
                .select('x_handle, priority')\
                .eq('active', True)\
                .order('priority', desc=True)\
                .execute()
            handles = [w['x_handle'] for w in (watchlist.data or [])]

            if handles:
                # Batch into groups of 5 for OR queries
                for i in range(0, len(handles), 5):
                    batch = handles[i:i+5]
                    query = ' OR '.join(f'from:{h}' for h in batch)
                    tweets = _x_api_search(query, max_results=10)
                    for tw in tweets:
                        metrics = tw.get('public_metrics', {})
                        engagement = (metrics.get('like_count', 0) +
                                      metrics.get('retweet_count', 0) +
                                      metrics.get('reply_count', 0))
                        if engagement < 5:
                            continue  # Skip low-engagement posts
                        supabase.table('x_content_candidates').insert({
                            'content_type': 'engagement_reply',
                            'source_url': f"https://x.com/{tw.get('author_username')}/status/{tw.get('id')}",
                            'source_summary': f"@{tw.get('author_username')}: {tw.get('text', '')[:200]}",
                            'suggested_angle': '',  # Will be filled by LLM below
                            'suggested_tags': [tw.get('author_username', '')],
                            'verification_status': 'verified',
                        }).execute()
                        candidates_created += 1

                # Update last_checked_at
                supabase.table('x_watchlist').update({
                    'last_checked_at': datetime.now(timezone.utc).isoformat()
                }).in_('x_handle', handles).execute()

            # Keyword scan — use arc engagement_keywords if available, plus generic fallbacks
            arc_keywords = []
            if todays_entry and todays_entry.get('engagement_keywords'):
                arc_keywords = todays_entry['engagement_keywords']

            generic_keywords = ['"MCP server"', '"AI agent framework"', '"agent infrastructure"', '"agentic AI"', '"agent economy"']

            if arc_keywords:
                # Arc keywords first (topically aligned with today's narrative post)
                arc_query = ' OR '.join(f'"{kw}"' if ' ' in kw else kw for kw in arc_keywords)
                arc_keyword_tweets = _x_api_search(arc_query, max_results=10)
                for tw in arc_keyword_tweets:
                    metrics = tw.get('public_metrics', {})
                    engagement = (metrics.get('like_count', 0) +
                                  metrics.get('retweet_count', 0))
                    if engagement < 5:
                        continue
                    supabase.table('x_content_candidates').insert({
                        'content_type': 'engagement_reply',
                        'source_url': f"https://x.com/{tw.get('author_username')}/status/{tw.get('id')}",
                        'source_summary': f"@{tw.get('author_username')}: {tw.get('text', '')[:200]}",
                        'suggested_angle': '',
                        'suggested_tags': [tw.get('author_username', '')],
                        'verification_status': 'verified',
                    }).execute()
                    candidates_created += 1

            # Generic keywords (always run as fallback)
            keyword_query = ' OR '.join(generic_keywords)
            keyword_tweets = _x_api_search(keyword_query, max_results=10)
            for tw in keyword_tweets:
                metrics = tw.get('public_metrics', {})
                engagement = (metrics.get('like_count', 0) +
                              metrics.get('retweet_count', 0))
                if engagement < 10:
                    continue
                supabase.table('x_content_candidates').insert({
                    'content_type': 'engagement_reply',
                    'source_url': f"https://x.com/{tw.get('author_username')}/status/{tw.get('id')}",
                    'source_summary': f"@{tw.get('author_username')}: {tw.get('text', '')[:200]}",
                    'suggested_angle': '',
                    'suggested_tags': [tw.get('author_username', '')],
                    'verification_status': 'verified',
                }).execute()
                candidates_created += 1

        except Exception as e:
            logger.error(f"X engagement surfacing failed: {e}")
    else:
        budget_status = get_x_budget_status()
        send_telegram(
            f"⏸️ X API weekly budget reached "
            f"(${budget_status.get('week_spent', 0):.2f}/${X_WEEKLY_BUDGET:.2f}). "
            f"Engagement surfacing paused until next Monday."
        )

    # ── Generate reply angles for engagement candidates missing them ──
    try:
        pending_replies = supabase.table('x_content_candidates')\
            .select('id, source_summary, suggested_tags')\
            .eq('content_type', 'engagement_reply')\
            .eq('status', 'candidate')\
            .eq('suggested_angle', '')\
            .gte('created_at', day_ago)\
            .execute()

        if pending_replies.data:
            reply_texts = '\n'.join(
                f"[{r['id'][:8]}] {r.get('source_summary', '')}"
                for r in pending_replies.data[:10]
            )
            prompt = f"""You are writing X/Twitter replies from @diegolancha. Diego writes about agent economics and trust infrastructure.

For each tweet below, write a single reply tweet:
- Add a NEW angle or insight to the conversation — don't just agree or disagree
- Connect their topic to agent economics or trust if possible, but don't force it
- Be respectful but direct — challenge ideas, not people
- Under 280 characters
- No hashtags, no emojis
- Don't start with "Great point!" or "This!" or "Interesting!" — just make your point

VOICE: Conversational, opinionated, like a smart reply from someone who's actually building in the space.

Tweets:
{reply_texts}

Respond as JSON object mapping the bracket ID to an object with "angle" and "draft":
{{"abc12345": {{"angle": "Your suggested angle here", "draft": "Ready-to-post reply text (under 280 chars)"}}, ...}}

The draft is a plain string (single tweet only), under 280 characters."""

            model = get_model('extraction')
            response = routed_llm_call(model, [
                {'role': 'system', 'content': 'You output valid JSON only.'},
                {'role': 'user', 'content': prompt},
            ], temperature=0.5, max_tokens=1500)

            raw = response.choices[0].message.content.strip()
            if raw.startswith('```'):
                raw = re.sub(r'^```\w*\n?', '', raw)
                raw = re.sub(r'\n?```$', '', raw)
            angles = json.loads(raw)

            for r in pending_replies.data:
                entry = angles.get(r['id'][:8], '')
                # Support both old format (plain string) and new format (dict with angle+draft)
                if isinstance(entry, dict):
                    angle = entry.get('angle', '')
                    draft = entry.get('draft', '')
                else:
                    angle = str(entry) if entry else ''
                    draft = ''
                if angle:
                    update_data = {'suggested_angle': angle}
                    if draft:
                        update_data['draft_content'] = draft
                    supabase.table('x_content_candidates').update(
                        update_data
                    ).eq('id', r['id']).execute()

    except Exception as e:
        logger.error(f"X reply angle generation failed: {e}")

    # ── Source 4: Prediction posts ──
    try:
        recent_predictions = supabase.table('predictions')\
            .select('id, prediction_text, target_date, status')\
            .gte('created_at', day_ago)\
            .in_('status', ['active', 'open'])\
            .execute()
        for pred in (recent_predictions.data or []):
            draft = (
                f"Prediction: {pred.get('prediction_text', '')}\n\n"
                f"Tracking accountability in AgentPulse's public scorecard.\n"
                f"{X_SUBSCRIBE_URL}"
            )
            supabase.table('x_content_candidates').insert({
                'content_type': 'prediction',
                'source_summary': pred.get('prediction_text', '')[:200],
                'suggested_angle': 'New prediction — public accountability',
                'draft_content': draft,
                'verification_status': 'verified',
            }).execute()
            candidates_created += 1

        # Resolved predictions
        recently_resolved = supabase.table('predictions')\
            .select('id, prediction_text, status, resolution_notes')\
            .gte('resolved_at', day_ago)\
            .in_('status', ['confirmed', 'refuted'])\
            .execute()
        for pred in (recently_resolved.data or []):
            outcome = 'Right' if pred['status'] == 'confirmed' else 'Wrong'
            draft = (
                f"Prediction update: I said \"{pred.get('prediction_text', '')[:150]}\"\n\n"
                f"Result: {outcome}. {pred.get('resolution_notes', '')[:100]}\n\n"
                f"Full scorecard: {X_SUBSCRIBE_URL}"
            )
            supabase.table('x_content_candidates').insert({
                'content_type': 'prediction',
                'source_summary': f"Prediction resolved: {pred.get('prediction_text', '')[:200]}",
                'suggested_angle': f'Prediction {outcome.lower()} — accountability update',
                'draft_content': draft,
                'verification_status': 'verified',
            }).execute()
            candidates_created += 1

    except Exception as e:
        logger.error(f"X prediction surfacing failed: {e}")

    # ── Assign daily index numbers to today's candidates ──
    # Narrative posts get lowest numbers (shown first), then by creation time
    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()
        todays = supabase.table('x_content_candidates')\
            .select('id, content_type')\
            .eq('status', 'candidate')\
            .gte('created_at', today_start)\
            .order('created_at', desc=False)\
            .execute()
        # Sort: narrative first, then sharp_take, then rest
        type_order = {'narrative': 0, 'sharp_take': 1, 'newsletter_thread': 2, 'prediction': 3, 'engagement_reply': 4}
        sorted_candidates = sorted(
            todays.data or [],
            key=lambda c: type_order.get(c.get('content_type', ''), 9)
        )
        for idx, row in enumerate(sorted_candidates, start=1):
            supabase.table('x_content_candidates').update({
                'daily_index': idx,
            }).eq('id', row['id']).execute()
    except Exception as e:
        logger.warning(f"Failed to assign daily indexes: {e}")

    logger.info(f"X content surfacing complete: {candidates_created} candidates created")
    return {'candidates_created': candidates_created}


def generate_newsletter_thread(newsletter: dict) -> dict:
    """Generate a thread draft from the newsletter's spotlight section."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    snapshot = newsletter.get('data_snapshot') or newsletter.get('input_data') or {}
    spotlight = snapshot.get('spotlight')
    if not spotlight:
        return {'skipped': 'No spotlight in this edition'}

    title = newsletter.get('title', '')
    edition = newsletter.get('edition_number', '?')
    spotlight_thesis = spotlight.get('thesis', spotlight.get('conviction_thesis', ''))
    spotlight_evidence = spotlight.get('evidence', spotlight.get('key_evidence', []))
    spotlight_prediction = spotlight.get('prediction', '')

    prompt = f"""Turn this newsletter spotlight into a compelling 4-6 tweet thread for X/Twitter.

Newsletter: "{title}" (Edition #{edition})
Thesis: {spotlight_thesis}
Evidence: {json.dumps(spotlight_evidence, default=str)[:1000]}
Prediction: {spotlight_prediction}

Structure:
- Tweet 1: Hook — the conviction thesis as a provocative statement (max 280 chars)
- Tweets 2-4: Evidence and reasoning, one idea per tweet (max 280 chars each)
- Tweet 5: The prediction with specific, trackable claim (max 280 chars)
- Tweet 6: CTA — "Full analysis and prediction scorecard in this week's AgentPulse: {X_SUBSCRIBE_URL}" (max 280 chars)

Respond as JSON array of strings: ["tweet 1 text", "tweet 2 text", ...]

Rules:
- Each tweet must be under 280 characters
- Write like a confident analyst, not a brand account
- No hashtags. Minimal emojis.
- Be specific — vague threads get no engagement"""

    try:
        response = routed_llm_call('gpt-4o', [
            {'role': 'system', 'content': 'You output valid JSON arrays only.'},
            {'role': 'user', 'content': prompt},
        ], temperature=0.5, max_tokens=2000)

        raw = response.choices[0].message.content.strip()
        if raw.startswith('```'):
            raw = re.sub(r'^```\w*\n?', '', raw)
            raw = re.sub(r'\n?```$', '', raw)
        thread_tweets = json.loads(raw)

        # Run verification
        v_status = 'pending'
        v_notes = None
        thread_text = ' '.join(thread_tweets)
        verification = verify_briefing_references({
            'content_markdown': thread_text,
            'data_snapshot': snapshot,
        })
        if not verification['ok']:
            v_status = 'flagged'
            v_notes = '; '.join(verification.get('unverified', [])[:3])

        supabase.table('x_content_candidates').insert({
            'content_type': 'newsletter_thread',
            'source_summary': f"Newsletter #{edition}: {title}",
            'suggested_angle': spotlight_thesis[:200] if spotlight_thesis else '',
            'draft_content': json.dumps(thread_tweets),
            'verification_status': v_status,
            'verification_notes': v_notes,
        }).execute()

        logger.info(f"Newsletter thread draft created ({len(thread_tweets)} tweets)")
        return {'thread_tweets': len(thread_tweets)}

    except Exception as e:
        logger.error(f"Newsletter thread generation failed: {e}")
        return {'error': str(e)}


def send_x_morning_briefing():
    """Send the daily X content plan to the operator via Telegram."""
    if not supabase:
        return

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()

    try:
        # Fetch today's sharp takes/threads/predictions
        today_candidates = supabase.table('x_content_candidates')\
            .select('*')\
            .eq('status', 'candidate')\
            .gte('created_at', today_start)\
            .order('daily_index', desc=False)\
            .execute()

        # Fetch ALL unactioned engagement replies (may span multiple days)
        all_engagement = supabase.table('x_content_candidates')\
            .select('*')\
            .eq('status', 'candidate')\
            .eq('content_type', 'engagement_reply')\
            .order('created_at', desc=True)\
            .limit(20)\
            .execute()

        # Merge: today's candidates + any older engagement replies not already included
        today_ids = {c['id'] for c in (today_candidates.data or [])}
        merged = list(today_candidates.data or [])
        for r in (all_engagement.data or []):
            if r['id'] not in today_ids:
                merged.append(r)

        candidates_data = type('obj', (object,), {'data': merged})()
        candidates = candidates_data

        if not candidates.data:
            return

        # Verification gate: flag any candidate missing a source_url
        for c in candidates.data:
            if not (c.get('source_url') or '').strip():
                if c.get('verification_status') != 'flagged':
                    supabase.table('x_content_candidates').update({
                        'verification_status': 'flagged',
                        'verification_notes': 'No source URL \u2014 unverifiable claim',
                    }).eq('id', c['id']).execute()
                    c['verification_status'] = 'flagged'
                    c['verification_notes'] = 'No source URL \u2014 unverifiable claim'

        takes = [c for c in candidates.data if c['content_type'] == 'sharp_take']
        replies = [c for c in candidates.data if c['content_type'] == 'engagement_reply']
        threads = [c for c in candidates.data if c['content_type'] == 'newsletter_thread']
        predictions = [c for c in candidates.data if c['content_type'] == 'prediction']

        lines = [f"📋 *X Content Plan — {datetime.now(timezone.utc).strftime('%b %d')}*\n"]

        if takes:
            lines.append("🔥 *TAKES* (pick 1-2 to post):")
            for t in takes:
                idx = t.get('daily_index', '?')
                v = '⚠️ Flagged' if t.get('verification_status') == 'flagged' else '✅'
                lines.append(f"{idx}. {t.get('source_summary', '')[:80]}")
                lines.append(f"   → {t.get('suggested_angle', '')[:100]}")
                if t.get('verification_notes'):
                    lines.append(f"   {v}: {t['verification_notes'][:60]}")
                else:
                    lines.append(f"   {v}")

        if replies:
            shown = replies[:10]
            lines.append(f"\n💬 *ENGAGE* (top {len(shown)} of {len(replies)}):")
            for r in shown:
                idx = r.get('daily_index', '?')
                lines.append(f"{idx}. {r.get('source_summary', '')[:100]}")
                if r.get('suggested_angle'):
                    lines.append(f"   → Reply: {r['suggested_angle'][:80]}")

        if threads:
            lines.append("\n🧵 *THREAD*:")
            for th in threads:
                idx = th.get('daily_index', '?')
                lines.append(f"{idx}. Newsletter thread draft — {th.get('source_summary', '')[:60]}")

        if predictions:
            lines.append("\n🎯 *PREDICTIONS*:")
            for p in predictions:
                idx = p.get('daily_index', '?')
                lines.append(f"{idx}. {p.get('source_summary', '')[:80]}")

        # Budget status
        budget = get_x_budget_status()
        lines.append(
            f"\n💰 Budget: ${budget.get('week_spent', 0):.2f}/${X_WEEKLY_BUDGET:.2f} this week"
        )

        lines.append("\nReply: `/x-approve 1,3` | `/x-edit 2` | `/x-reject 4`")

        send_telegram('\n'.join(lines))

    except Exception as e:
        logger.error(f"X morning briefing failed: {e}")


def approve_x_candidate(daily_indexes: list, final_content: str = None) -> dict:
    """Approve X content candidates by daily index number."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    approved = []
    errors = []

    for idx in daily_indexes:
        try:
            row = supabase.table('x_content_candidates')\
                .select('*')\
                .eq('daily_index', idx)\
                .eq('status', 'candidate')\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()
            if not row.data:
                errors.append(f"#{idx}: not found or already processed")
                continue

            candidate = row.data[0]
            update = {'status': 'approved'}
            if final_content:
                update['final_content'] = final_content
            elif candidate.get('draft_content'):
                update['final_content'] = candidate['draft_content']

            supabase.table('x_content_candidates').update(update)\
                .eq('id', candidate['id']).execute()
            approved.append(idx)

        except Exception as e:
            errors.append(f"#{idx}: {e}")

    return {'approved': approved, 'errors': errors}


def reject_x_candidate(daily_indexes: list, notes: str = '') -> dict:
    """Reject X content candidates by daily index number."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    rejected = []

    for idx in daily_indexes:
        try:
            row = supabase.table('x_content_candidates')\
                .select('id')\
                .eq('daily_index', idx)\
                .eq('status', 'candidate')\
                .order('created_at', desc=True)\
                .limit(1)\
                .execute()
            if row.data:
                supabase.table('x_content_candidates').update({
                    'status': 'rejected',
                    'operator_notes': notes or None,
                }).eq('id', row.data[0]['id']).execute()
                rejected.append(idx)
        except Exception as e:
            logger.error(f"X reject #{idx} failed: {e}")

    return {'rejected': rejected}


def edit_x_candidate(daily_index: int, new_content: str) -> dict:
    """Replace draft content for a candidate by daily index."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    try:
        row = supabase.table('x_content_candidates')\
            .select('id, content_type')\
            .eq('daily_index', daily_index)\
            .eq('status', 'candidate')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
        if not row.data:
            return {'error': f'Candidate #{daily_index} not found'}

        supabase.table('x_content_candidates').update({
            'final_content': new_content,
        }).eq('id', row.data[0]['id']).execute()

        return {'updated': daily_index, 'content_type': row.data[0].get('content_type')}

    except Exception as e:
        return {'error': str(e)}


def post_approved_x_content() -> dict:
    """Pick up approved x_content_candidates and post them to X."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    try:
        approved = supabase.table('x_content_candidates')\
            .select('*')\
            .eq('status', 'approved')\
            .order('created_at', desc=False)\
            .limit(5)\
            .execute()

        if not approved.data:
            return {'posted': 0}

        posted = []
        failed = []

        for candidate in approved.data:
            content = candidate.get('final_content') or candidate.get('draft_content', '')
            if not content:
                failed.append({'id': candidate['id'], 'error': 'No content'})
                continue

            ctype = candidate.get('content_type')

            if ctype == 'newsletter_thread':
                # Post as thread
                try:
                    tweets = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    tweets = [content]

                prev_id = None
                thread_ids = []
                for tweet_text in tweets:
                    result = _post_tweet(tweet_text, reply_to=prev_id)
                    if 'error' in result:
                        failed.append({'id': candidate['id'], 'error': result['error']})
                        break
                    prev_id = result.get('id')
                    thread_ids.append(prev_id)
                    time.sleep(1)  # Brief pause between thread tweets

                if thread_ids:
                    supabase.table('x_content_candidates').update({
                        'status': 'posted',
                        'posted_at': datetime.now(timezone.utc).isoformat(),
                        'x_post_id': thread_ids[0],
                    }).eq('id', candidate['id']).execute()
                    posted.append(candidate['id'])
                    send_telegram(
                        f"✅ Thread posted ({len(thread_ids)} tweets): "
                        f"https://x.com/i/status/{thread_ids[0]}"
                    )
            else:
                # Check if content is a JSON thread array (or plain text over 280 chars)
                thread_tweets = None
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, list) and all(isinstance(t, str) for t in parsed):
                        thread_tweets = parsed
                except (json.JSONDecodeError, TypeError):
                    pass

                # If plain text over 280 chars, split into thread on double-newlines
                if not thread_tweets and len(content) > 280:
                    parts = [p.strip() for p in content.split('\n\n') if p.strip()]
                    if len(parts) > 1:
                        thread_tweets = parts

                if thread_tweets and len(thread_tweets) > 1:
                    # Post as thread
                    prev_id = None
                    thread_ids = []
                    for tweet_text in thread_tweets:
                        result = _post_tweet(tweet_text, reply_to=prev_id)
                        if 'error' in result:
                            failed.append({'id': candidate['id'], 'error': result['error']})
                            break
                        prev_id = result.get('id')
                        thread_ids.append(prev_id)
                        time.sleep(1)

                    if thread_ids:
                        supabase.table('x_content_candidates').update({
                            'status': 'posted',
                            'posted_at': datetime.now(timezone.utc).isoformat(),
                            'x_post_id': thread_ids[0],
                        }).eq('id', candidate['id']).execute()
                        posted.append(candidate['id'])
                        send_telegram(
                            f"✅ Thread posted ({len(thread_ids)} tweets): "
                            f"https://x.com/i/status/{thread_ids[0]}"
                        )
                    continue

                # Single tweet — for engagement replies, extract reply-to ID from source_url
                reply_to_id = None
                if ctype == 'engagement_reply' and candidate.get('source_url'):
                    # source_url format: https://x.com/{user}/status/{tweet_id}
                    url_parts = candidate['source_url'].rstrip('/').split('/')
                    if len(url_parts) >= 2 and url_parts[-2] == 'status':
                        reply_to_id = url_parts[-1]
                result = _post_tweet(content, reply_to=reply_to_id)
                if 'error' in result:
                    supabase.table('x_content_candidates').update({
                        'status': 'failed',
                        'operator_notes': f"Post failed: {result['error'][:200]}",
                    }).eq('id', candidate['id']).execute()
                    failed.append({'id': candidate['id'], 'error': result['error']})
                    send_telegram(f"❌ Post failed: {result['error'][:100]}")
                else:
                    tweet_id = result.get('id', '')
                    supabase.table('x_content_candidates').update({
                        'status': 'posted',
                        'posted_at': datetime.now(timezone.utc).isoformat(),
                        'x_post_id': tweet_id,
                    }).eq('id', candidate['id']).execute()
                    posted.append(candidate['id'])
                    send_telegram(
                        f"✅ Posted: {content[:50]}... — "
                        f"https://x.com/i/status/{tweet_id}"
                    )

        return {'posted': len(posted), 'failed': len(failed)}

    except Exception as e:
        logger.error(f"X posting failed: {e}")
        return {'error': str(e)}


def expire_old_x_candidates():
    """Expire candidates older than 48 hours that were never approved."""
    if not supabase:
        return
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    try:
        supabase.table('x_content_candidates').update({
            'status': 'expired',
        }).eq('status', 'candidate').lt('created_at', cutoff).execute()
    except Exception as e:
        logger.warning(f"X candidate expiry failed: {e}")


def manage_x_watchlist(action: str, handle: str = '', category: str = '', notes: str = '') -> dict:
    """Add/remove/list X watchlist accounts."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    if action == 'add':
        handle = handle.lstrip('@').strip()
        if not handle:
            return {'error': 'Handle required'}
        try:
            supabase.table('x_watchlist').upsert({
                'x_handle': handle,
                'category': category or None,
                'notes': notes or None,
                'active': True,
            }, on_conflict='x_handle').execute()
            return {'added': handle}
        except Exception as e:
            return {'error': str(e)}

    elif action == 'remove':
        handle = handle.lstrip('@').strip()
        try:
            supabase.table('x_watchlist').update({
                'active': False,
            }).eq('x_handle', handle).execute()
            return {'deactivated': handle}
        except Exception as e:
            return {'error': str(e)}

    elif action == 'list':
        try:
            rows = supabase.table('x_watchlist')\
                .select('x_handle, priority, category, active')\
                .eq('active', True)\
                .order('priority', desc=True)\
                .execute()
            return {'watchlist': rows.data or []}
        except Exception as e:
            return {'error': str(e)}

    return {'error': f'Unknown action: {action}'}


def get_x_posted_today() -> dict:
    """Get today's posted X content."""
    if not supabase:
        return {'error': 'Supabase not configured'}
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()
    try:
        rows = supabase.table('x_content_candidates')\
            .select('content_type, final_content, draft_content, posted_at, x_post_id')\
            .eq('status', 'posted')\
            .gte('posted_at', today_start)\
            .execute()
        return {'posted': rows.data or []}
    except Exception as e:
        return {'error': str(e)}


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
        except Exception as e:
            logger.warning(f"get_scrape_stats skipped: {e}")
    
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
                'started_at': datetime.now(timezone.utc).isoformat()
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
                'completed_at': datetime.now(timezone.utc).isoformat()
            }, indent=2))
            
            # Mark completed in DB
            supabase.table('agent_tasks').update({
                'status': 'completed',
                'completed_at': datetime.now(timezone.utc).isoformat(),
                'output_data': result
            }).eq('id', task_id).execute()
            
            logger.info(f"[{agent_name}] Task {task_id} completed")
        
        except Exception as e:
            logger.error(f"[{agent_name}] Task {task_id} failed: {e}")
            try:
                supabase.table('agent_tasks').update({
                    'status': 'failed',
                    'completed_at': datetime.now(timezone.utc).isoformat(),
                    'error_message': str(e)
                }).eq('id', task_id).execute()
            except Exception as update_err:
                logger.error(f"[{agent_name}] Failed to update task {task_id} status: {update_err}")

# ============================================================================
# Telegram Notifications
# ============================================================================

def send_telegram(message: str):
    """Send notification to Telegram, splitting if over 4096 chars."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_OWNER_ID:
        return

    MAX_LEN = 4000  # leave margin under Telegram's 4096 limit

    # Split long messages on newline boundaries
    chunks = []
    if len(message) <= MAX_LEN:
        chunks = [message]
    else:
        current = ""
        for line in message.split('\n'):
            if len(current) + len(line) + 1 > MAX_LEN:
                if current:
                    chunks.append(current)
                current = line
            else:
                current = current + '\n' + line if current else line
        if current:
            chunks.append(current)

    try:
        with httpx.Client() as client:
            for chunk in chunks:
                resp = client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    data={
                        'chat_id': TELEGRAM_OWNER_ID,
                        'text': chunk,
                        'parse_mode': 'Markdown'
                    }
                )
                if resp.status_code != 200:
                    logger.warning(f"Telegram Markdown failed ({resp.status_code}), retrying as plain text")
                    resp = client.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                        data={
                            'chat_id': TELEGRAM_OWNER_ID,
                            'text': chunk,
                        }
                    )
                    if resp.status_code != 200:
                        logger.error(f"Telegram send failed ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")

# ============================================================================
# Email Newsletter Delivery (Resend)
# ============================================================================

def render_newsletter_html(title: str, content_markdown: str, unsubscribe_url: str, edition_number: int = None, mode: str = "builder") -> str:
    """Convert newsletter markdown to a styled HTML email."""
    body_html = md_lib.markdown(content_markdown, extensions=['tables', 'fenced_code'])
    edition_label = f"Edition #{edition_number}" if edition_number else "AgentPulse Intelligence Brief"

    if mode == "impact":
        bg_outer = "#e8e4de"
        bg_inner = "#faf8f4"
        color_text = "#0a0a0f"
        color_accent = "#7c3aed"
        color_muted = "#6b6560"
        color_border = "#e5e0d8"
        color_title = "#0a0a0f"
        color_link = "#7c3aed"
    else:
        bg_outer = "#0a0a0a"
        bg_inner = "#111"
        color_text = "#ffffff"
        color_accent = "#00e5a0"
        color_muted = "#888"
        color_border = "#333"
        color_title = "#ffffff"
        color_link = "#00e5a0"

    # Inject inline heading styles into markdown-generated HTML
    heading_style = f'style="font-family:Courier New,monospace;font-size:15px;font-weight:700;color:{color_accent};letter-spacing:2px;text-transform:uppercase;margin:28px 0 12px;"'
    body_html = body_html.replace('<h2>', f'<h2 {heading_style}>')
    body_html = body_html.replace('<h3>', f'<h3 {heading_style}>')

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:{bg_outer};font-family:'Segoe UI',Helvetica,Arial,sans-serif;">
  <div style="max-width:640px;margin:0 auto;padding:32px 24px;background:{bg_inner};color:{color_text};">
    <div style="border-bottom:1px solid {color_border};padding-bottom:16px;margin-bottom:24px;">
      <h1 style="color:{color_accent};font-size:14px;letter-spacing:2px;margin:0;">AGENTPULSE</h1>
      <p style="color:{color_muted};font-size:12px;margin:4px 0 0;">{edition_label}</p>
    </div>
    <h2 style="color:{color_title};font-size:22px;margin:0 0 24px;">{title}</h2>
    <div style="line-height:1.7;font-size:15px;color:{color_text};">
      {body_html}
    </div>
    <div style="border-top:1px solid {color_border};margin-top:32px;padding-top:16px;text-align:center;">
      <p style="color:{color_muted};font-size:12px;">
        You received this because you subscribed to AgentPulse Intelligence Brief.
        <br><a href="{unsubscribe_url}" style="color:{color_link};text-decoration:underline;">Unsubscribe</a>
        &nbsp;&middot;&nbsp;
        <a href="https://aiagentspulse.com" style="color:{color_link};text-decoration:underline;">Web Archive</a>
      </p>
    </div>
  </div>
</body>
</html>"""


def _build_email_params(from_addr, to_email, subject, html, unsub_url, edition, mode):
    """Build Resend email params dict."""
    return {
        "from": from_addr,
        "to": [to_email],
        "subject": subject,
        "html": html,
        "headers": {
            "List-Unsubscribe": "<" + unsub_url + ">",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"
        },
        "tags": [
            {"name": "edition", "value": str(edition)},
            {"name": "mode", "value": mode}
        ]
    }


def send_email_newsletter(newsletter: dict) -> dict:
    """Send newsletter via email to all active subscribers using Resend."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping email delivery")
        return {'skipped': 'no_api_key'}

    if not supabase:
        return {'error': 'Supabase not configured'}

    try:
        result = supabase.table('subscribers')\
            .select('id, email, mode_preference')\
            .eq('status', 'active')\
            .execute()

        subscribers = result.data or []
        if not subscribers:
            logger.info("No active subscribers — skipping email delivery")
            return {'sent': 0}

        edition = newsletter.get('edition_number', '?')
        builder_title = newsletter.get('title', 'AgentPulse Intelligence Brief')
        builder_md = newsletter.get('content_markdown', '')
        impact_title = newsletter.get('title_impact') or builder_title
        impact_md = newsletter.get('content_markdown_impact') or builder_md
        from_addr = "AgentPulse <newsletter@contact.aiagentspulse.com>"

        sent = 0
        errors = 0

        def _send_with_throttle(params, sub_id, email, subject, mode, edition):
            """Send one email via Resend with rate-limit throttling (max 2 req/s)."""
            nonlocal sent
            last_err = None
            for attempt in range(3):
                try:
                    resp = resend.Emails.send(params)
                    rid = resp.get('id') if isinstance(resp, dict) else getattr(resp, 'id', None)
                    _log_email(sub_id, email, 'newsletter', subject, mode=mode, edition=edition, resend_id=rid)
                    sent += 1
                    time.sleep(0.6)  # stay under Resend's 2 req/s limit
                    return
                except Exception as e:
                    last_err = e
                    if 'rate' in str(e).lower() or '429' in str(e):
                        logger.warning("Resend rate limit hit, backing off (attempt %d/3): %s", attempt + 1, e)
                        time.sleep(2 ** attempt)  # 1s, 2s, 4s backoff
                    else:
                        raise
            raise last_err

        for sub in subscribers:
            pref = sub.get('mode_preference', 'impact')
            email = sub['email']
            sub_id = sub['id']
            unsub_url = "https://aiagentspulse.com/#/unsubscribe?id=" + str(sub_id)

            try:
                if pref == 'both':
                    # Send builder version
                    subject_b = "AgentPulse #" + str(edition) + " [Builder]: " + builder_title
                    html_b = render_newsletter_html(builder_title, builder_md, unsub_url, edition, mode="builder")
                    _send_with_throttle(_build_email_params(from_addr, email, subject_b, html_b, unsub_url, edition, "builder"),
                                        sub_id, email, subject_b, 'builder', edition)
                    # Send impact version
                    subject_i = "AgentPulse #" + str(edition) + " [Strategic]: " + impact_title
                    html_i = render_newsletter_html(impact_title, impact_md, unsub_url, edition, mode="impact")
                    _send_with_throttle(_build_email_params(from_addr, email, subject_i, html_i, unsub_url, edition, "impact"),
                                        sub_id, email, subject_i, 'impact', edition)
                else:
                    if pref == 'builder':
                        title, content = builder_title, builder_md
                    else:
                        title, content = impact_title, impact_md

                    subject = "AgentPulse #" + str(edition) + ": " + title
                    html = render_newsletter_html(title, content, unsub_url, edition, mode=pref)
                    _send_with_throttle(_build_email_params(from_addr, email, subject, html, unsub_url, edition, pref),
                                        sub_id, email, subject, pref, edition)

            except Exception as e:
                _log_email(sub_id, email, 'newsletter', f"AgentPulse #{edition}", mode=pref, edition=edition, status='failed', error_message=str(e))
                logger.error("Failed to send email to %s: %s", email, e)
                errors += 1

        logger.info("Email delivery: %d sent, %d errors, %d subscribers", sent, errors, len(subscribers))
        return {'sent': sent, 'errors': errors, 'total_subscribers': len(subscribers)}

    except Exception as e:
        logger.error("Email newsletter delivery failed: %s", e)
        return {'error': str(e)}


def retry_failed_emails(edition: int | None = None) -> dict:
    """Retry all failed email_log entries. If edition is None, retries the latest edition with failures."""
    if not RESEND_API_KEY or not supabase:
        return {'error': 'Resend or Supabase not configured'}

    try:
        # Find failed emails
        query = supabase.table('email_log').select('*').eq('status', 'failed')
        if edition:
            query = query.eq('edition_number', edition)
        else:
            # Find the latest edition with failures
            latest = supabase.table('email_log').select('edition_number')\
                .eq('status', 'failed').order('created_at', desc=True).limit(1).execute()
            if not latest.data:
                return {'retried': 0, 'message': 'No failed emails found'}
            edition = latest.data[0]['edition_number']
            query = query.eq('edition_number', edition)

        failed = query.execute()
        if not failed.data:
            return {'retried': 0, 'message': 'No failed emails found'}

        # Get the newsletter content for this edition
        nl = supabase.table('newsletters').select('*')\
            .eq('edition_number', edition).limit(1).execute()
        if not nl.data:
            return {'error': f'Newsletter #{edition} not found'}
        newsletter = nl.data[0]

        builder_title = newsletter.get('title', 'AgentPulse Intelligence Brief')
        builder_md = newsletter.get('content_markdown', '')
        impact_title = newsletter.get('title_impact') or builder_title
        impact_md = newsletter.get('content_markdown_impact') or builder_md
        from_addr = "AgentPulse <newsletter@contact.aiagentspulse.com>"

        retried = 0
        errors = 0

        for entry in failed.data:
            email = entry['email']
            sub_id = entry['subscriber_id']
            mode = entry.get('mode', 'impact')
            failed_log_id = entry['id']
            unsub_url = "https://aiagentspulse.com/#/unsubscribe?id=" + str(sub_id)

            try:
                if mode == 'builder':
                    title, content = builder_title, builder_md
                elif mode == 'impact':
                    title, content = impact_title, impact_md
                else:
                    # 'both' failed — need to figure out which email failed; resend both
                    for m, t, c in [('builder', builder_title, builder_md), ('impact', impact_title, impact_md)]:
                        subj = f"AgentPulse #{edition} [{m.title()}]: {t}"
                        html = render_newsletter_html(t, c, unsub_url, edition, mode=m)
                        resend.Emails.send(_build_email_params(from_addr, email, subj, html, unsub_url, edition, m))
                        _log_email(sub_id, email, 'newsletter', subj, mode=m, edition=edition, resend_id=None)
                        retried += 1
                        time.sleep(0.6)
                    # Mark original failure as retried
                    supabase.table('email_log').update({'status': 'retried'}).eq('id', failed_log_id).execute()
                    continue

                subject = f"AgentPulse #{edition}: {title}"
                html = render_newsletter_html(title, content, unsub_url, edition, mode=mode)
                resp = resend.Emails.send(_build_email_params(from_addr, email, subject, html, unsub_url, edition, mode))
                rid = resp.get('id') if isinstance(resp, dict) else getattr(resp, 'id', None)
                _log_email(sub_id, email, 'newsletter', subject, mode=mode, edition=edition, resend_id=rid)
                # Mark original failure as retried
                supabase.table('email_log').update({'status': 'retried'}).eq('id', failed_log_id).execute()
                retried += 1
                time.sleep(0.6)

            except Exception as e:
                logger.error("Retry failed for %s: %s", email, e)
                errors += 1

        logger.info("Email retry: %d retried, %d errors", retried, errors)
        send_telegram(f"📧 Email retry complete: {retried} resent, {errors} errors (edition #{edition})")
        return {'retried': retried, 'errors': errors, 'edition': edition}

    except Exception as e:
        logger.error("Email retry failed: %s", e)
        return {'error': str(e)}


# ============================================================================
# Welcome Email (sent once to new subscribers)
# ============================================================================

def _render_welcome_email_html(unsubscribe_url: str) -> str:
    """Render the welcome email as email-client-safe HTML (table layout, inline styles)."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Welcome to AgentPulse</title>
</head>
<body style="margin:0;padding:0;background-color:#0a0a0f;color:#c8c8d0;font-family:Georgia,'Times New Roman',serif;line-height:1.7;-webkit-font-smoothing:antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#0a0a0f;">
<tr><td align="center">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;padding:40px 24px;">

  <!-- Header -->
  <tr><td style="border-bottom:1px solid #1a1a2e;padding-bottom:32px;">
    <div style="font-family:'Courier New',Courier,monospace;font-size:13px;letter-spacing:4px;text-transform:uppercase;color:#00e5a0;margin-bottom:6px;">AGENTPULSE</div>
    <div style="font-family:'Courier New',Courier,monospace;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#555568;">Weekly Intelligence Brief</div>
  </td></tr>

  <!-- Hero -->
  <tr><td style="padding:36px 0 0;">
    <h1 style="font-family:Georgia,serif;font-size:28px;font-weight:400;color:#efefef;line-height:1.3;margin:0 0 16px 0;">You're in. Here's what <em style="color:#00e5a0;font-style:italic;">this actually is.</em></h1>
    <p style="font-size:17px;color:#9999aa;margin:0;line-height:1.7;">AgentPulse isn't another AI newsletter that summarizes what happened last week. It's a conviction-driven intelligence brief on the emerging agent economy &mdash; the infrastructure, capital flows, and builder decisions shaping a world where software agents do real work.</p>
  </td></tr>

  <!-- Divider -->
  <tr><td style="padding:36px 0 0;border-top:1px solid #1a1a2e;"></td></tr>

  <!-- What you're getting -->
  <tr><td>
    <div style="font-family:'Courier New',monospace;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:#00e5a0;margin-bottom:14px;">WHAT YOU'RE GETTING</div>
    <p style="font-size:16px;color:#b0b0be;margin:0 0 14px 0;">Every week, a single brief. Not a link dump. Not a hype recap. Each edition takes a position &mdash; a thesis about where the agent economy is headed &mdash; and commits to it publicly. We track our predictions over time and publish the scorecard. <strong style="color:#e0e0e8;font-weight:600;">Being wrong is a feature, not a bug.</strong></p>
    <p style="font-size:16px;color:#b0b0be;margin:0 0 14px 0;">The brief is structured to give you signal without the noise, with each section serving a distinct purpose:</p>
  </td></tr>

  <!-- Section Map -->
  <tr><td style="padding:24px 0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0f0f1a;border:1px solid #1a1a2e;border-radius:4px;">
      <tr><td style="padding:28px 24px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="width:28px;vertical-align:top;padding-top:2px;font-family:'Courier New',monospace;font-size:12px;color:#00e5a0;">01</td>
            <td style="padding-bottom:20px;">
              <div style="font-family:'Courier New',monospace;font-size:14px;color:#e0e0e8;margin-bottom:4px;letter-spacing:0.5px;">The Big Insight</div>
              <p style="font-size:14px;color:#7a7a8e;line-height:1.6;margin:0;">The macro thesis of the week. One argument, fully committed. Not "on one hand / on the other" &mdash; a stake in the ground.</p>
            </td>
          </tr>
          <tr>
            <td style="width:28px;vertical-align:top;padding-top:2px;font-family:'Courier New',monospace;font-size:12px;color:#00e5a0;">02</td>
            <td style="padding-bottom:20px;">
              <div style="font-family:'Courier New',monospace;font-size:14px;color:#e0e0e8;margin-bottom:4px;letter-spacing:0.5px;">Spotlight</div>
              <p style="font-size:14px;color:#7a7a8e;line-height:1.6;margin:0;">A deep-dive research piece on a single inflection point. Original analysis, not regurgitated press releases.</p>
            </td>
          </tr>
          <tr>
            <td style="width:28px;vertical-align:top;padding-top:2px;font-family:'Courier New',monospace;font-size:12px;color:#00e5a0;">03</td>
            <td style="padding-bottom:20px;">
              <div style="font-family:'Courier New',monospace;font-size:14px;color:#e0e0e8;margin-bottom:4px;letter-spacing:0.5px;">Signal vs. Noise</div>
              <p style="font-size:14px;color:#7a7a8e;line-height:1.6;margin:0;">Quick-hit classification of the week's developments. What actually matters, what's just marketing.</p>
            </td>
          </tr>
          <tr>
            <td style="width:28px;vertical-align:top;padding-top:2px;font-family:'Courier New',monospace;font-size:12px;color:#00e5a0;">04</td>
            <td>
              <div style="font-family:'Courier New',monospace;font-size:14px;color:#e0e0e8;margin-bottom:4px;letter-spacing:0.5px;">Prediction Tracker</div>
              <p style="font-size:14px;color:#7a7a8e;line-height:1.6;margin:0;">Our open ledger of past calls. New predictions posted, old ones scored. Full accountability.</p>
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
  </td></tr>

  <!-- Divider -->
  <tr><td style="border-top:1px solid #1a1a2e;padding-top:36px;"></td></tr>

  <!-- Where the intelligence comes from -->
  <tr><td>
    <div style="font-family:'Courier New',monospace;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:#00e5a0;margin-bottom:14px;">WHERE THE INTELLIGENCE COMES FROM</div>
    <p style="font-size:16px;color:#b0b0be;margin:0 0 14px 0;">AgentPulse is built on a multi-agent system that continuously monitors the agent ecosystem. Not a human scanning Twitter &mdash; a pipeline of specialized AI agents that scrape, classify, extract signals, and synthesize across sources that matter:</p>
  </td></tr>

  <!-- Source Tags -->
  <tr><td style="padding:14px 0 18px;">
    <table role="presentation" cellpadding="0" cellspacing="0"><tr>
      <td style="font-family:'Courier New',monospace;font-size:11px;letter-spacing:1px;color:#7a7a8e;background:#0f0f1a;border:1px solid #1a1a2e;border-radius:3px;padding:5px 10px;margin-right:8px;">a16z</td>
      <td width="8"></td>
      <td style="font-family:'Courier New',monospace;font-size:11px;letter-spacing:1px;color:#7a7a8e;background:#0f0f1a;border:1px solid #1a1a2e;border-radius:3px;padding:5px 10px;">GitHub</td>
      <td width="8"></td>
      <td style="font-family:'Courier New',monospace;font-size:11px;letter-spacing:1px;color:#7a7a8e;background:#0f0f1a;border:1px solid #1a1a2e;border-radius:3px;padding:5px 10px;">Hacker News</td>
      <td width="8"></td>
      <td style="font-family:'Courier New',monospace;font-size:11px;letter-spacing:1px;color:#7a7a8e;background:#0f0f1a;border:1px solid #1a1a2e;border-radius:3px;padding:5px 10px;">arXiv</td>
    </tr></table>
    <table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:8px;"><tr>
      <td style="font-family:'Courier New',monospace;font-size:11px;letter-spacing:1px;color:#7a7a8e;background:#0f0f1a;border:1px solid #1a1a2e;border-radius:3px;padding:5px 10px;">Infrastructure blogs</td>
      <td width="8"></td>
      <td style="font-family:'Courier New',monospace;font-size:11px;letter-spacing:1px;color:#7a7a8e;background:#0f0f1a;border:1px solid #1a1a2e;border-radius:3px;padding:5px 10px;">Developer ecosystems</td>
    </tr></table>
  </td></tr>

  <tr><td>
    <p style="font-size:16px;color:#b0b0be;margin:0 0 14px 0;">Raw signal gets routed through editorial analysis before it reaches you. The agents find the data. <strong style="color:#e0e0e8;font-weight:600;">The editorial layer decides what it means.</strong></p>
  </td></tr>

  <!-- Divider -->
  <tr><td style="border-top:1px solid #1a1a2e;padding-top:36px;"></td></tr>

  <!-- Why this exists -->
  <tr><td>
    <div style="font-family:'Courier New',monospace;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:#00e5a0;margin-bottom:14px;">WHY THIS EXISTS</div>
    <p style="font-size:16px;color:#b0b0be;margin:0 0 14px 0;">The agent economy is moving faster than any single person can track. Capital is flowing. Infrastructure is shifting. New primitives &mdash; agent-to-agent commerce, tool-use protocols, autonomous workflows &mdash; are emerging weekly.</p>
    <p style="font-size:16px;color:#b0b0be;margin:0 0 14px 0;">Most coverage oscillates between hype and dismissal. AgentPulse exists in the gap: <strong style="color:#e0e0e8;font-weight:600;">rigorous analysis with the conviction to actually say something.</strong> If you're building in this space, investing in it, or making career decisions around it &mdash; this is the brief that treats you like you can handle a real argument.</p>
  </td></tr>

  <!-- Divider -->
  <tr><td style="border-top:1px solid #1a1a2e;padding-top:36px;"></td></tr>

  <!-- Two reading modes -->
  <tr><td>
    <div style="font-family:'Courier New',monospace;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:#00e5a0;margin-bottom:14px;">TWO WAYS TO READ IT</div>
    <p style="font-size:16px;color:#b0b0be;margin:0 0 14px 0;">Not everyone needs the same level of depth. Each edition ships in two versions &mdash; same intelligence, different lens. Pick the one that fits how you think:</p>
  </td></tr>

  <!-- Dual View Box -->
  <tr><td style="padding:24px 0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0f0f1a;border:1px solid #1a1a2e;border-radius:4px;">
      <tr>
        <td width="50%" style="padding:24px 16px;vertical-align:top;">
          <div style="background:#0a0a12;border:1px solid #1a1a2e;border-radius:4px;padding:16px;">
            <span style="font-family:'Courier New',monospace;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#00e5a0;border:1px solid rgba(0,229,160,0.2);padding:3px 8px;border-radius:2px;display:inline-block;margin-bottom:10px;">BUILDER MODE</span>
            <p style="font-size:13px;color:#7a7a8e;line-height:1.6;margin:0;">Technical framing. Architecture decisions, protocol-level shifts, infrastructure bets, code-adjacent analysis. Written for people who ship agents, not just read about them.</p>
          </div>
        </td>
        <td width="50%" style="padding:24px 16px;vertical-align:top;">
          <div style="background:#0a0a12;border:1px solid #1a1a2e;border-radius:4px;padding:16px;">
            <span style="font-family:'Courier New',monospace;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#e5a000;border:1px solid rgba(229,160,0,0.2);padding:3px 8px;border-radius:2px;display:inline-block;margin-bottom:10px;">IMPACT MODE</span>
            <p style="font-size:13px;color:#7a7a8e;line-height:1.6;margin:0;">Strategic framing. Market dynamics, workforce implications, capital flows, adoption patterns. Written for decision-makers who need to understand what's changing and why it matters.</p>
          </div>
        </td>
      </tr>
    </table>
  </td></tr>

  <tr><td>
    <p style="font-size:16px;color:#b0b0be;margin:0 0 14px 0;">Same underlying research. Same convictions. Just tuned for <strong style="color:#e0e0e8;font-weight:600;">how you'll use the information.</strong></p>
  </td></tr>

  <!-- CTA -->
  <tr><td style="text-align:center;padding:36px 0;border-top:1px solid #1a1a2e;border-bottom:1px solid #1a1a2e;">
    <p style="font-size:16px;color:#9999aa;margin:0 0 8px 0;">Your first edition arrives next week.</p>
    <span style="font-family:'Courier New',monospace;font-size:13px;color:#00e5a0;letter-spacing:1px;">No action needed &mdash; you're already on the list.</span>
  </td></tr>

  <!-- Footer -->
  <tr><td style="padding-top:24px;text-align:center;">
    <p style="font-family:'Courier New',monospace;font-size:11px;color:#444458;letter-spacing:1px;margin:0 0 6px 0;">AgentPulse &middot; Weekly Intelligence Brief</p>
    <p style="font-family:'Courier New',monospace;font-size:11px;color:#444458;letter-spacing:1px;margin:0;">
      <a href="{unsubscribe_url}" style="color:#555568;text-decoration:none;">Unsubscribe</a>
      &middot;
      <a href="https://aiagentspulse.com" style="color:#555568;text-decoration:none;">View in browser</a>
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def _log_email(subscriber_id, email, email_type, subject, mode=None, edition=None, resend_id=None, status='sent', error_message=None):
    """Log an email send attempt to the email_log table."""
    if not supabase:
        return
    try:
        row = {
            'subscriber_id': subscriber_id,
            'email': email,
            'email_type': email_type,
            'subject': subject,
            'mode': mode,
            'edition_number': edition,
            'resend_id': resend_id,
            'status': status,
            'error_message': error_message,
        }
        supabase.table('email_log').insert(row).execute()
    except Exception as e:
        logger.warning("Failed to log email to email_log: %s", e)


def send_welcome_email(subscriber: dict) -> bool:
    """Send a one-time welcome email to a new subscriber. Returns True on success."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping welcome email")
        return False

    email = subscriber['email']
    sub_id = subscriber['id']
    unsub_url = "https://aiagentspulse.com/#/unsubscribe?id=" + str(sub_id)
    subject = "You're in. Here's what this actually is."

    try:
        html = _render_welcome_email_html(unsub_url)
        resp = resend.Emails.send({
            "from": "AgentPulse <newsletter@contact.aiagentspulse.com>",
            "to": [email],
            "subject": subject,
            "html": html,
            "headers": {
                "List-Unsubscribe": "<" + unsub_url + ">",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"
            },
            "tags": [{"name": "type", "value": "welcome"}]
        })
        resend_id = resp.get('id') if isinstance(resp, dict) else getattr(resp, 'id', None)
        _log_email(sub_id, email, 'welcome', subject, resend_id=resend_id)
        logger.info("Welcome email sent to %s (resend_id=%s)", email, resend_id)
        return True
    except Exception as e:
        _log_email(sub_id, email, 'welcome', subject, status='failed', error_message=str(e))
        logger.error("Failed to send welcome email to %s: %s", email, e)
        return False


def process_pending_welcome_emails():
    """Check for new subscribers who haven't received a welcome email and send one."""
    if not supabase or not RESEND_API_KEY:
        return

    try:
        result = supabase.table('subscribers')\
            .select('id, email, mode_preference')\
            .eq('status', 'active')\
            .is_('welcome_email_sent_at', 'null')\
            .limit(10)\
            .execute()

        pending = result.data or []
        if not pending:
            return

        logger.info("Sending welcome emails to %d new subscriber(s)", len(pending))
        for sub in pending:
            if send_welcome_email(sub):
                supabase.table('subscribers').update({
                    'welcome_email_sent_at': datetime.now(timezone.utc).isoformat()
                }).eq('id', sub['id']).execute()
    except Exception as e:
        logger.warning("Welcome email check failed: %s", e)


# ============================================================================
# Personal Intelligence Briefing (Phase 7A)
# ============================================================================

def generate_personal_briefing() -> dict:
    """Generate a personal intelligence briefing for the operator."""
    if not supabase:
        return {'error': 'Supabase not configured'}

    # Load operator context
    context_path = Path('/home/openclaw/.openclaw/config/operator-context.md')
    if not context_path.exists():
        logger.warning("No operator-context.md found at %s", context_path)
        return {'error': 'No operator context configured'}
    operator_context = context_path.read_text()

    # Load extra watch topics from workspace (added via /watch command)
    watch_path = Path('/home/openclaw/.openclaw/workspace/agentpulse/watch_topics.json')
    extra_signals = []
    if watch_path.exists():
        try:
            extra_signals = json.loads(watch_path.read_text())
        except Exception:
            pass
    if extra_signals:
        operator_context += "\n\n## Dynamic Watch List (added via /watch)\n"
        for topic in extra_signals:
            operator_context += f"- {topic}\n"

    # Gather recent data (last 12 hours)
    twelve_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()

    try:
        recent_posts = supabase.table('source_posts')\
            .select('source, title, body, source_tier, score, tags')\
            .gte('scraped_at', twelve_hours_ago)\
            .order('source_tier', desc=False)\
            .limit(100)\
            .execute()
    except Exception as e:
        logger.warning("Briefing: failed to fetch source_posts: %s", e)
        recent_posts = type('R', (), {'data': []})()

    try:
        recent_tools = supabase.table('tool_mentions')\
            .select('tool_name, context, sentiment_score, source')\
            .gte('created_at', twelve_hours_ago)\
            .limit(50)\
            .execute()
    except Exception as e:
        logger.warning("Briefing: failed to fetch tool_mentions: %s", e)
        recent_tools = type('R', (), {'data': []})()

    try:
        latest_analysis = supabase.table('analysis_runs')\
            .select('key_findings, analyst_notes, metadata')\
            .eq('status', 'completed')\
            .order('completed_at', desc=True)\
            .limit(1)\
            .execute()
    except Exception as e:
        logger.warning("Briefing: failed to fetch analysis_runs: %s", e)
        latest_analysis = type('R', (), {'data': []})()

    try:
        predictions = supabase.table('predictions')\
            .select('topic, status, current_score, notes')\
            .in_('status', ['active', 'open'])\
            .execute()
    except Exception as e:
        logger.warning("Briefing: failed to fetch predictions: %s", e)
        predictions = type('R', (), {'data': []})()

    try:
        topics = supabase.table('topic_evolution')\
            .select('topic_key, current_stage, stage_changed_at, thesis')\
            .order('last_updated', desc=True)\
            .limit(15)\
            .execute()
    except Exception as e:
        logger.warning("Briefing: failed to fetch topic_evolution: %s", e)
        topics = type('R', (), {'data': []})()

    data_package = {
        'recent_posts': recent_posts.data or [],
        'recent_tools': recent_tools.data or [],
        'latest_analysis': latest_analysis.data[0] if latest_analysis.data else None,
        'active_predictions': predictions.data or [],
        'topic_evolution': topics.data or [],
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

    system_prompt = f"""You are an intelligence briefing system for a specific operator.
Your job is to scan the latest data and surface what matters to THIS person based on
their context.

OPERATOR CONTEXT:
{operator_context}

RULES:
- Maximum 5 items. Each item is 1-3 sentences.
- Lead with the most actionable item.
- Flag anything that directly affects the operator's active projects.
- Flag any signals matching the operator's investment thesis.
- Flag any answers to the operator's open questions.
- If a prediction's status changed, mention it.
- If a topic changed lifecycle stage, mention it.
- If nothing significant happened, say "Quiet 12 hours. Nothing actionable." Don't pad.
- Be direct. No greetings, no filler. This is a private briefing, not a newsletter.
- End with a one-line "Action items:" if any exist (things the operator should do).

FORMAT:
Return plain text, not JSON. This goes straight to Telegram.
Use numbered items. Keep it under 500 words total."""
    system_prompt += fetch_economics_block()

    model = get_model('personal_briefing')
    try:
        response = routed_llm_call(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(data_package, default=str)}
            ],
            max_tokens=1000,
            temperature=0.3
        )
        briefing_text = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("Personal briefing LLM call failed: %s", e)
        return {'error': f'LLM call failed: {e}'}

    # Send to Telegram via existing send_telegram()
    header = "AGENTPULSE BRIEFING\n\n"
    send_telegram(header + briefing_text)

    logger.info("Personal briefing sent (%d chars)", len(briefing_text))
    return {'briefing_sent': True, 'length': len(briefing_text)}


def get_operator_context() -> dict:
    """Return the current operator context for display."""
    context_path = Path('/home/openclaw/.openclaw/config/operator-context.md')
    if not context_path.exists():
        return {'error': 'No operator-context.md found'}
    content = context_path.read_text()

    # Include dynamic watch topics
    watch_path = Path('/home/openclaw/.openclaw/workspace/agentpulse/watch_topics.json')
    extra = []
    if watch_path.exists():
        try:
            extra = json.loads(watch_path.read_text())
        except Exception:
            pass

    return {'context': content, 'dynamic_watch_topics': extra}


def add_watch_topic(topic: str) -> dict:
    """Add a topic to the dynamic watch list."""
    watch_path = Path('/home/openclaw/.openclaw/workspace/agentpulse/watch_topics.json')
    watch_path.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if watch_path.exists():
        try:
            existing = json.loads(watch_path.read_text())
        except Exception:
            pass

    topic = topic.strip()
    if topic in existing:
        return {'already_watching': topic, 'total': len(existing)}

    existing.append(topic)
    watch_path.write_text(json.dumps(existing, indent=2))
    logger.info("Added watch topic: %s", topic)
    return {'added': topic, 'total': len(existing)}


def scheduled_personal_briefing():
    """Scheduled wrapper for personal briefing (runs at 8am and 8pm UTC)."""
    try:
        result = generate_personal_briefing()
        if result.get('error'):
            logger.warning("Scheduled briefing failed: %s", result['error'])
    except Exception as e:
        logger.error("Scheduled briefing exception: %s", e)


# ============================================================================
# Full Newsletter Pipeline (manual / cron backup)
# ============================================================================

def run_full_newsletter_pipeline():
    """Run the complete newsletter pipeline end-to-end with monitoring.

    Phases:
        1. Data collection (scrape all sources)
        2. Analysis (extract, cluster, topic evolution, spotlight selection)
        3. Wait for Research Agent (poll spotlight_history)
        4. Newsletter generation
    """
    pipeline_start = time.time()
    logger.info("[PIPELINE] ========== Full pipeline started ==========")

    results = {}

    # ── Phase 1: Data Collection ──
    logger.info("[PIPELINE] Phase 1: Data Collection")
    for label, fn in [
        ("moltbook", scrape_moltbook),
        ("hackernews", scrape_hackernews),
        ("github", scrape_github),
        ("rss", scrape_rss_feeds),
        ("thought_leaders", scrape_thought_leaders),
    ]:
        try:
            r = fn()
            results[f"scrape_{label}"] = r
            count = r.get('total_new', r.get('items_stored', r.get('feeds_scraped', '?')))
            logger.info(f"[PIPELINE] Scrape {label}: {count} items")
        except Exception as e:
            logger.error(f"[PIPELINE] Scrape {label} failed: {e}")
            results[f"scrape_{label}"] = {'error': str(e)}

    elapsed_p1 = time.time() - pipeline_start
    logger.info(f"[PIPELINE] Phase 1 complete in {elapsed_p1:.0f}s")

    # ── Phase 2: Analysis ──
    logger.info("[PIPELINE] Phase 2: Analysis")
    for label, fn in [
        ("extract_problems", lambda: extract_problems_multisource()),
        ("extract_tools", lambda: extract_tools_multisource()),
        ("extract_trending", lambda: extract_trending_topics_multisource()),
        ("cluster", cluster_problems),
        ("topic_evolution", update_topic_evolution),
        ("track_predictions", track_predictions),
    ]:
        try:
            r = fn()
            results[label] = r
            logger.info(f"[PIPELINE] {label}: done")
        except Exception as e:
            logger.error(f"[PIPELINE] {label} failed: {e}")
            results[label] = {'error': str(e)}

    # Spotlight selection (writes trigger for Research Agent)
    try:
        spotlight_result = select_spotlight_topic()
        results['spotlight_selection'] = spotlight_result
        selected = spotlight_result.get('selected')
        mode = spotlight_result.get('mode', '?')
        score = spotlight_result.get('score') or spotlight_result.get('best_score', 0)
        if selected:
            logger.info(f"[PIPELINE] Spotlight selected: '{selected}' (score={score}, mode={mode})")
        else:
            logger.info(f"[PIPELINE] No spotlight selected: {spotlight_result.get('reason', '?')}")
    except Exception as e:
        logger.error(f"[PIPELINE] Spotlight selection failed: {e}")
        results['spotlight_selection'] = {'error': str(e)}

    elapsed_p2 = time.time() - pipeline_start
    logger.info(f"[PIPELINE] Phase 2 complete in {elapsed_p2:.0f}s")

    # ── Phase 3: Wait for Research Agent ──
    logger.info("[PIPELINE] Phase 3: Waiting for Research Agent...")
    spotlight_result = results.get('spotlight_selection', {})
    queue_id = spotlight_result.get('queue_id') if isinstance(spotlight_result, dict) else None
    research_timeout = 300
    research_start = time.time()
    spotlight_ready = False

    if queue_id:
        while (time.time() - research_start) < research_timeout:
            try:
                q = supabase.table('research_queue').select('status')\
                    .eq('id', queue_id).execute()
                if q.data and q.data[0].get('status') in ('completed', 'failed'):
                    status = q.data[0]['status']
                    elapsed = time.time() - research_start
                    logger.info(f"[PIPELINE] Research Agent {status} in {elapsed:.0f}s")
                    spotlight_ready = status == 'completed'
                    break
            except Exception as e:
                logger.warning(f"Research queue status check skipped: {e}")
            time.sleep(15)
        else:
            elapsed = time.time() - research_start
            logger.warning(f"[PIPELINE] Research Agent timeout after {elapsed:.0f}s — proceeding without Spotlight")
    else:
        logger.info("[PIPELINE] No research queued — proceeding without Spotlight")

    results['research_completed'] = spotlight_ready

    # ── Phase 4: Newsletter Generation ──
    logger.info("[PIPELINE] Phase 4: Newsletter Generation")
    try:
        nl_result = prepare_newsletter_data()
        results['newsletter'] = nl_result
        edition = nl_result.get('edition_number', '?')

        sections = []
        if nl_result.get('input_data', {}).get('spotlight') if isinstance(nl_result.get('input_data'), dict) else False:
            sections.append("Spotlight")
        sections.extend(["Signals", "Radar"])
        logger.info(f"[PIPELINE] Newsletter #{edition} prepared — sections: {', '.join(sections)}")
    except Exception as e:
        logger.error(f"[PIPELINE] Newsletter generation failed: {e}")
        results['newsletter'] = {'error': str(e)}

    # ── Summary ──
    total_elapsed = time.time() - pipeline_start
    logger.info(f"[PIPELINE] ========== Pipeline completed in {total_elapsed:.0f}s ==========")

    errors = [k for k, v in results.items() if isinstance(v, dict) and 'error' in v]
    if errors:
        logger.warning(f"[PIPELINE] Components with errors: {errors}")
    else:
        logger.info("[PIPELINE] All components succeeded")

    print(json.dumps({
        'pipeline_elapsed_seconds': round(total_elapsed, 1),
        'spotlight_ready': spotlight_ready,
        'errors': errors,
        'results': {k: ('ok' if isinstance(v, dict) and 'error' not in v else v)
                    for k, v in results.items()},
    }, indent=2, default=str))


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
    """Scheduled analysis task — gathers data then delegates to Analyst agent."""
    logger.info("Running scheduled analysis...")
    try:
        try:
            extract_result = extract_problems_multisource()
        except Exception as e:
            logger.warning(f"Multisource problem extraction failed, falling back to single-source: {e}")
            extract_result = extract_problems()

        try:
            tool_result = extract_tools_multisource()
        except Exception as e:
            logger.warning(f"Multisource tool extraction failed, falling back to single-source: {e}")
            tool_result = extract_tool_mentions()

        try:
            trending_result = extract_trending_topics_multisource()
        except Exception as e:
            logger.warning(f"Multisource trending extraction failed, falling back to single-source: {e}")
            trending_result = extract_trending_topics()

        cluster_result = cluster_problems()
        analysis_result = prepare_analysis_package()  # delegates to Analyst

        problems_found = extract_result.get('problems_found', 0)
        clusters_created = cluster_result.get('clusters_created', 0)
        task_id = analysis_result.get('task_id', '?')
        logger.info(f"Scheduled analysis completed: problems={problems_found}, clusters={clusters_created}, delegated to analyst (task {task_id})")

        send_telegram(
            f"🎯 AgentPulse analysis: {problems_found} problems extracted, "
            f"{clusters_created} clusters created, analysis delegated to Analyst (task {task_id})"
        )
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

def scheduled_trending_topics():
    """Scheduled trending topics extraction."""
    logger.info("Running scheduled trending topics extraction...")
    try:
        result = extract_trending_topics(hours_back=48)
        logger.info(f"Scheduled trending topics completed: {result}")
        topics = result.get('topics_found', 0)
        if topics > 0:
            send_telegram(f"🔥 AgentPulse trending: {topics} interesting topics found")
    except Exception as e:
        logger.error(f"Scheduled trending topics extraction failed: {e}")

def scheduled_prepare_newsletter():
    """Scheduled: gather data and delegate newsletter writing to Newsletter agent."""
    logger.info("[PIPELINE] Running newsletter preparation...")
    try:
        result = prepare_newsletter_data()

        # Guard already handled — don't notify for duplicates
        if result.get('status') == 'already_exists':
            logger.info(f"[PIPELINE] Newsletter task already exists (task {result.get('task_id')}), skipping notification")
            return
        if result.get('error'):
            logger.error(f"[PIPELINE] Newsletter prep returned error: {result.get('error')}")
            return

        edition = result.get('edition_number', '?')
        spotlight_present = result.get('input_data', {}).get('spotlight') is not None if isinstance(result.get('input_data'), dict) else False

        sections = []
        if spotlight_present:
            sections.append("Spotlight")
        sections.append("Signals")

        logger.info(f"[PIPELINE] Newsletter #{edition} data prepared, sections: {', '.join(sections)}")
        send_telegram(f"📝 Newsletter #{edition} data prepared and sent to Newsletter agent for writing.")
    except Exception as e:
        logger.error(f"[PIPELINE] Newsletter prep failed: {e}")

def scheduled_notify_newsletter():
    """Notify owner that a new newsletter may be ready for review."""
    logger.info("[PIPELINE] Newsletter notification sent")
    send_telegram(
        "📰 New AgentPulse Brief is ready for review. "
        "Send /newsletter_publish to publish, or it will auto-publish at 13:00 UTC."
    )


def scheduled_auto_publish_newsletter():
    """Auto-publish the latest draft if it wasn't manually published within the review window."""
    logger.info("[PIPELINE] Auto-publish check...")
    if not supabase:
        return
    try:
        # Only auto-publish draft/pending — NOT preview (preview = operator reviewing on web)
        draft = supabase.table('newsletters')\
            .select('id, edition_number, created_at')\
            .in_('status', ['draft', 'pending'])\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()

        if not draft.data:
            logger.info("[PIPELINE] No draft to auto-publish")
            return

        newsletter = draft.data[0]
        created = datetime.fromisoformat(newsletter['created_at'].replace('Z', '+00:00'))
        age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600

        if age_hours < 1:
            logger.info("[PIPELINE] Draft too fresh (%.1fh old), skipping auto-publish", age_hours)
            return

        result = publish_newsletter()
        if result.get('published'):
            logger.info("[PIPELINE] Auto-published newsletter #%s", newsletter.get('edition_number'))
            send_telegram(
                f"📰 Newsletter #{newsletter.get('edition_number')} was auto-published "
                f"(no manual publish within review window)."
            )
        else:
            logger.warning("[PIPELINE] Auto-publish failed: %s", result)
    except Exception as e:
        logger.error("[PIPELINE] Auto-publish failed: %s", e)

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

def refresh_workspace_cache():
    """Dump latest data to workspace cache files so Gato can read them directly."""
    if not supabase:
        logger.warning("Cannot refresh workspace cache — Supabase not configured")
        return

    try:
        # Tool stats
        tool_stats = supabase.table('tool_stats') \
            .select('*') \
            .order('total_mentions', desc=True) \
            .limit(20) \
            .execute()
        cache_file = CACHE_DIR / 'tool_stats_latest.json'
        cache_file.write_text(json.dumps({
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'tools': tool_stats.data or []
        }, indent=2, default=str))

        # Latest opportunities
        opps = supabase.table('opportunities') \
            .select('*') \
            .order('confidence_score', desc=True) \
            .limit(10) \
            .execute()
        cache_file = CACHE_DIR / 'opportunities_latest.json'
        cache_file.write_text(json.dumps({
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'opportunities': opps.data or []
        }, indent=2, default=str))

        # Latest newsletter
        newsletter = supabase.table('newsletters') \
            .select('*') \
            .order('created_at', desc=True) \
            .limit(1) \
            .execute()
        cache_file = CACHE_DIR / 'newsletter_latest.json'
        cache_file.write_text(json.dumps({
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'newsletter': newsletter.data[0] if newsletter.data else None
        }, indent=2, default=str))

        # Latest analysis run
        analysis = supabase.table('analysis_runs') \
            .select('*') \
            .eq('status', 'completed') \
            .order('completed_at', desc=True) \
            .limit(1) \
            .execute()
        cache_file = CACHE_DIR / 'analysis_latest.json'
        cache_file.write_text(json.dumps({
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'analysis': analysis.data[0] if analysis.data else None
        }, indent=2, default=str))

        # Active cross-signals
        signals = supabase.table('cross_signals') \
            .select('*') \
            .eq('status', 'active') \
            .order('strength', desc=True) \
            .limit(20) \
            .execute()
        cache_file = CACHE_DIR / 'signals_latest.json'
        cache_file.write_text(json.dumps({
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'signals': signals.data or []
        }, indent=2, default=str))

        # System status summary
        status = get_status()
        cache_file = CACHE_DIR / 'status_latest.json'
        cache_file.write_text(json.dumps({
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'status': status
        }, indent=2, default=str))

        logger.info("Workspace cache refreshed (tool_stats, opportunities, newsletter, analysis, signals, status)")
    except Exception as e:
        logger.error(f"Failed to refresh workspace cache: {e}")


def scheduled_refresh_cache():
    try:
        refresh_workspace_cache()
    except Exception as e:
        logger.error(f"Scheduled cache refresh failed: {e}")


def scheduled_proactive_scan():
    """Scheduled proactive anomaly detection."""
    logger.info("Running scheduled proactive scan...")
    try:
        result = proactive_scan()
        logger.info(f"Scheduled proactive scan completed: {result}")
    except Exception as e:
        logger.error(f"Scheduled proactive scan failed: {e}")


def scheduled_check_negotiation_timeouts():
    """Scheduled check for timed-out negotiations."""
    try:
        check_negotiation_timeouts()
    except Exception as e:
        logger.error(f"Scheduled negotiation timeout check failed: {e}")


def scheduled_scrape_hackernews():
    """Scheduled Hacker News scraping task."""
    try:
        result = scrape_hackernews(limit=200)
        logger.info(f"Scheduled HN scrape: {result}")
    except Exception as e:
        logger.error(f"Scheduled HN scrape failed: {e}")


def scheduled_scrape_github():
    """Scheduled GitHub scraping task."""
    try:
        result = scrape_github(days_back=7)
        logger.info(f"Scheduled GitHub scrape: {result}")
    except Exception as e:
        logger.error(f"Scheduled GitHub scrape failed: {e}")


def scheduled_scrape_rss():
    """Scheduled RSS feed scraping task."""
    try:
        result = scrape_rss_feeds()
        logger.info(f"Scheduled RSS scrape: {result}")
    except Exception as e:
        logger.error(f"Scheduled RSS scrape failed: {e}")


def scheduled_scrape_thought_leaders():
    """Scheduled thought leader feed ingestion."""
    try:
        result = scrape_thought_leaders()
        logger.info(f"Scheduled thought leader scrape: {result}")
    except Exception as e:
        logger.error(f"Scheduled thought leader scrape failed: {e}")


def scheduled_scrape_x_source_accounts():
    """Scheduled X/Twitter source account scanning."""
    try:
        result = scrape_x_source_accounts()
        logger.info(f"Scheduled X source account scan: {result}")
    except Exception as e:
        logger.error(f"Scheduled X source account scan failed: {e}")


def scheduled_update_evolution():
    """Scheduled topic evolution update."""
    try:
        result = update_topic_evolution()
        logger.info(f"[PIPELINE] Topic evolution: {result}")
    except Exception as e:
        logger.error(f"[PIPELINE] Topic evolution failed: {e}")


def scheduled_select_spotlight():
    """Scheduled spotlight selection — runs after topic evolution, before newsletter."""
    logger.info("[PIPELINE] Running spotlight selection heuristic...")
    try:
        result = select_spotlight_topic()
        selected = result.get('selected')
        mode = result.get('mode', '?')
        score = result.get('score') or result.get('best_score', 0)
        trigger = result.get('trigger_file')

        if selected:
            logger.info(f"[PIPELINE] Spotlight selected: '{selected}' (score={score}, mode={mode})")
            if trigger:
                logger.info(f"[PIPELINE] Research trigger written: {trigger}")
            send_telegram(
                f"🎯 Spotlight selected: {selected} (score={score}, mode={mode})\n"
                f"Research Agent will generate thesis."
            )
        else:
            reason = result.get('reason', 'unknown')
            logger.info(f"[PIPELINE] No spotlight selected: {reason}")
    except Exception as e:
        logger.error(f"[PIPELINE] Spotlight selection failed: {e}")


def scheduled_track_predictions():
    """Scheduled prediction tracking — runs before newsletter generation."""
    try:
        result = track_predictions()
        logger.info(f"Prediction tracking: {result}")
    except Exception as e:
        logger.error(f"Prediction tracking failed: {e}")


def scheduled_surface_x_candidates():
    """Daily X content candidate surfacing — runs morning CET (~7am CET = 06:00 UTC)."""
    try:
        expire_old_x_candidates()
        result = surface_x_content_candidates()
        logger.info(f"X candidate surfacing: {result}")
        # Send morning briefing after surfacing
        send_x_morning_briefing()
    except Exception as e:
        logger.error(f"X candidate surfacing failed: {e}")


def scheduled_post_approved_x():
    """Poll for approved X content and post it."""
    try:
        result = post_approved_x_content()
        if result.get('posted', 0) > 0:
            logger.info(f"X posting: {result}")
    except Exception as e:
        logger.error(f"X posting failed: {e}")


def scheduled_x_newsletter_thread():
    """Generate newsletter thread after auto-publish (Monday after publish)."""
    if not supabase:
        return
    try:
        latest = supabase.table('newsletters')\
            .select('*')\
            .eq('status', 'published')\
            .order('published_at', desc=True)\
            .limit(1)\
            .execute()
        if latest.data:
            result = generate_newsletter_thread(latest.data[0])
            logger.info(f"Newsletter thread: {result}")
    except Exception as e:
        logger.error(f"Newsletter thread generation failed: {e}")


# ============================================================================
# Health Checks
# ============================================================================

_health_cooldowns: dict = {}  # check_name → last_alert_time


def _health_check_cooldown_ok(check_name: str, cooldown_minutes: int = 60) -> bool:
    """Return True if enough time has passed since the last alert for this check."""
    now = datetime.now(timezone.utc)
    last = _health_cooldowns.get(check_name)
    if last and (now - last) < timedelta(minutes=cooldown_minutes):
        return False
    return True


def _mark_health_cooldown(check_name: str):
    """Record that an alert was just sent for this check."""
    _health_cooldowns[check_name] = datetime.now(timezone.utc)


def run_health_checks() -> dict:
    """Run all system health checks and return results dict."""
    results = {}
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Supabase connectivity
    try:
        supabase.table('pipeline_runs').select('id').limit(1).execute()
        results['supabase'] = {'status': 'ok'}
    except Exception as e:
        results['supabase'] = {'status': 'fail', 'error': str(e)}

    # 2. Subscribe RPC (insert test email, then delete)
    test_email = 'healthcheck@test.agentpulse.internal'
    try:
        supabase.rpc('subscribe', {'p_email': test_email, 'p_mode': 'email'}).execute()
        supabase.table('subscribers').delete().eq('email', test_email).execute()
        results['subscribe_rpc'] = {'status': 'ok'}
    except Exception as e:
        # Clean up just in case
        try:
            supabase.table('subscribers').delete().eq('email', test_email).execute()
        except Exception:
            pass
        results['subscribe_rpc'] = {'status': 'fail', 'error': str(e)}

    # 3-5. External API reachability (just TCP connect, any response = ok)
    api_endpoints = {
        'deepseek': 'https://api.deepseek.com',
        'openai': 'https://api.openai.com',
        'x_api': 'https://api.twitter.com',
    }
    for name, url in api_endpoints.items():
        try:
            with httpx.Client(timeout=10) as client:
                client.get(url)
            results[name] = {'status': 'ok'}
        except httpx.ConnectError as e:
            results[name] = {'status': 'fail', 'error': str(e)}
        except Exception:
            # Any response (4xx, 5xx) means the host is reachable
            results[name] = {'status': 'ok'}

    # 6. gato_brain internal health
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get('http://gato_brain:8100/health')
        if resp.status_code == 200:
            results['gato_brain'] = {'status': 'ok'}
        else:
            results['gato_brain'] = {'status': 'fail', 'error': f'HTTP {resp.status_code}'}
    except Exception as e:
        results['gato_brain'] = {'status': 'fail', 'error': str(e)}

    # 7. Web frontend
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get('http://web:8080/health')
        if resp.status_code < 400:
            results['web'] = {'status': 'ok'}
        else:
            results['web'] = {'status': 'fail', 'error': f'HTTP {resp.status_code}'}
    except Exception as e:
        results['web'] = {'status': 'fail', 'error': str(e)}

    # 8. Task queue depth
    try:
        pending = supabase.table('agent_tasks')\
            .select('id', count='exact')\
            .eq('status', 'pending')\
            .execute()
        count = pending.count if pending.count is not None else len(pending.data or [])
        if count >= 50:
            results['task_queue'] = {'status': 'fail', 'error': f'{count} pending tasks (>= 50)'}
        else:
            results['task_queue'] = {'status': 'ok', 'pending': count}
    except Exception as e:
        results['task_queue'] = {'status': 'fail', 'error': str(e)}

    # 9. X API budget
    try:
        budget = get_x_budget_status()
        remaining = budget.get('week_remaining', 999)
        if remaining <= 0.50:
            results['x_budget'] = {'status': 'fail', 'error': f'${remaining:.2f} remaining'}
        else:
            results['x_budget'] = {'status': 'ok', 'remaining': remaining}
    except Exception as e:
        results['x_budget'] = {'status': 'fail', 'error': str(e)}

    # ── Write cache file ──────────────────────────────────────────
    output = {
        'timestamp': now_iso,
        'checks': results,
        'summary': {
            'total': len(results),
            'passed': sum(1 for r in results.values() if r['status'] == 'ok'),
            'failed': sum(1 for r in results.values() if r['status'] != 'ok'),
        }
    }
    cache_path = CACHE_DIR / 'health_latest.json'
    try:
        cache_path.write_text(json.dumps(output, indent=2))
    except Exception as e:
        logger.warning(f"Failed to write health cache: {e}")

    # ── Alert on failures (with cooldown) ─────────────────────────
    failures = {k: v['error'] for k, v in results.items() if v['status'] != 'ok'}
    if failures:
        lines = [f"  {k}: {v}" for k, v in failures.items()]
        # Only alert for checks that haven't alerted recently
        alertable = [k for k in failures if _health_check_cooldown_ok(k)]
        if alertable:
            alert_lines = [f"  {k}: {failures[k]}" for k in alertable]
            msg = "\u26a0\ufe0f Health Check Failures:\n" + "\n".join(alert_lines)
            send_telegram(msg)
            for k in alertable:
                _mark_health_cooldown(k)
        logger.warning(f"Health check failures: {failures}")
    else:
        logger.info(f"All {len(results)} health checks passed")

    return output


def scheduled_health_check():
    """Scheduler wrapper for health checks."""
    try:
        run_health_checks()
    except Exception as e:
        logger.error(f"Health check run failed: {e}")


# ============================================================================
# Pipeline Watchdog — Autonomous Self-Healing
# ============================================================================

_watchdog_cooldowns: dict = {}  # action_key → last_action_time


def _watchdog_cooldown_ok(key: str, cooldown_minutes: int = 120) -> bool:
    """Prevent the same auto-fix from firing more than once per cooldown period."""
    now = datetime.now(timezone.utc)
    last = _watchdog_cooldowns.get(key)
    if last and (now - last).total_seconds() < cooldown_minutes * 60:
        return False
    _watchdog_cooldowns[key] = now
    return True


def _ops_restart_service(service: str, reason: str) -> bool:
    """Ask gato_brain to restart a container via the /ops/restart endpoint."""
    secret = os.getenv("CODE_SESSION_SECRET", "")
    try:
        with httpx.Client(timeout=40) as client:
            resp = client.post(
                "http://gato_brain:8100/ops/restart",
                json={"service": service, "reason": reason},
                headers={"X-Ops-Secret": secret},
            )
        data = resp.json()
        if data.get("status") == "restarted":
            logger.info(f"[WATCHDOG] Restarted {service}: {reason}")
            return True
        else:
            logger.warning(f"[WATCHDOG] Restart request for {service} returned: {data}")
            return False
    except Exception as e:
        logger.error(f"[WATCHDOG] Failed to restart {service}: {e}")
        return False


def _ops_get_container_health(service: str) -> dict:
    """Check container status via gato_brain."""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"http://gato_brain:8100/ops/container-status/{service}")
        return resp.json()
    except Exception:
        return {"status": "unreachable"}


def run_pipeline_watchdog():
    """Detect and auto-fix pipeline failures. Runs every 15 minutes."""
    if not supabase:
        return

    now = datetime.now(timezone.utc)
    actions_taken = []

    # ── 1. Stuck tasks: in_progress for >30 minutes ──────────────────
    try:
        cutoff = (now - timedelta(minutes=30)).isoformat()
        stuck = supabase.table('agent_tasks')\
            .select('id, task_type, assigned_to, started_at')\
            .eq('status', 'in_progress')\
            .lt('started_at', cutoff)\
            .execute()

        for task in (stuck.data or []):
            task_id = task['id']
            assigned = task.get('assigned_to', 'unknown')
            task_type = task.get('task_type', 'unknown')
            key = f"stuck_task_{task_id}"

            if _watchdog_cooldown_ok(key, cooldown_minutes=60):
                # Reset to pending so the agent picks it up again
                supabase.table('agent_tasks').update({
                    'status': 'pending',
                    'started_at': None,
                    'error_message': f'Reset by watchdog: stuck in_progress since {task["started_at"]}',
                }).eq('id', task_id).execute()
                actions_taken.append(f"Reset stuck task {task_id[:8]} ({task_type} → {assigned})")
                logger.warning(f"[WATCHDOG] Reset stuck task {task_id} ({task_type})")
    except Exception as e:
        logger.error(f"[WATCHDOG] Stuck task check failed: {e}")

    # ── 2. Agent service health (newsletter, analyst, research) ──────
    for service in ['newsletter', 'analyst', 'research']:
        try:
            health = _ops_get_container_health(service)
            container_status = health.get('status', 'unknown')
            container_health = health.get('health', 'unknown')

            if container_status == 'running' and container_health == 'healthy':
                continue

            key = f"restart_{service}"
            if _watchdog_cooldown_ok(key, cooldown_minutes=120):
                reason = f"container {container_status}, health {container_health}"
                if _ops_restart_service(service, reason):
                    actions_taken.append(f"Restarted {service} ({reason})")
                else:
                    actions_taken.append(f"FAILED to restart {service} ({reason})")
        except Exception as e:
            logger.error(f"[WATCHDOG] Service check for {service} failed: {e}")

    # ── 3. Repeated poll errors (agent_tasks table missing, etc.) ────
    # Check if newsletter/analyst can actually claim tasks
    for service in ['newsletter', 'analyst']:
        try:
            test = supabase.rpc(
                'claim_agent_task',
                {'p_assigned_to': f'__watchdog_test_{service}__', 'p_limit': 1},
            ).execute()
            # If we get here without exception, the RPC works
        except Exception as e:
            error_str = str(e)
            key = f"rpc_broken_{service}"
            if _watchdog_cooldown_ok(key, cooldown_minutes=240):
                actions_taken.append(f"CRITICAL: claim_agent_task RPC broken — {error_str[:100]}")
                logger.error(f"[WATCHDOG] claim_agent_task RPC broken: {e}")

    # ── 4. Friday newsletter pipeline guard ──────────────────────────
    if now.weekday() == 4 and now.hour >= 13:
        # It's Friday after 13:00 UTC — newsletter should exist
        try:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            tasks = supabase.table('agent_tasks')\
                .select('id, status, error_message')\
                .eq('task_type', 'write_newsletter')\
                .gte('created_at', today_start)\
                .execute()

            if not tasks.data:
                key = "newsletter_missing_friday"
                if _watchdog_cooldown_ok(key, cooldown_minutes=240):
                    logger.warning("[WATCHDOG] No newsletter task found on Friday after 13:00 — triggering")
                    try:
                        scheduled_prepare_newsletter()
                        actions_taken.append("Triggered missing Friday newsletter preparation")
                    except Exception as prep_err:
                        actions_taken.append(f"FAILED to trigger newsletter: {prep_err}")
            else:
                # Check if all tasks failed
                all_failed = all(t.get('status') == 'failed' for t in tasks.data)
                if all_failed and len(tasks.data) < 3:
                    key = "newsletter_retry_friday"
                    if _watchdog_cooldown_ok(key, cooldown_minutes=240):
                        last_error = tasks.data[0].get('error_message', 'unknown')
                        logger.warning(f"[WATCHDOG] All newsletter tasks failed ({last_error}), retrying")

                        # Restart the newsletter service and re-trigger
                        _ops_restart_service('newsletter', f'all tasks failed: {last_error[:80]}')
                        time.sleep(10)  # brief pause for container to come up
                        scheduled_prepare_newsletter()
                        actions_taken.append(f"Retried newsletter after all tasks failed: {last_error[:60]}")
        except Exception as e:
            logger.error(f"[WATCHDOG] Newsletter pipeline check failed: {e}")

    # ── 5. Failed tasks piling up — alert for code-level fixes ───────
    try:
        recent_cutoff = (now - timedelta(hours=6)).isoformat()
        failed = supabase.table('agent_tasks')\
            .select('task_type, assigned_to, error_message', count='exact')\
            .eq('status', 'failed')\
            .gte('created_at', recent_cutoff)\
            .execute()

        fail_count = failed.count if failed.count is not None else len(failed.data or [])
        if fail_count >= 5:
            key = "many_failures"
            if _watchdog_cooldown_ok(key, cooldown_minutes=360):
                # Group by error pattern
                error_summary = {}
                for t in (failed.data or [])[:10]:
                    err = (t.get('error_message') or 'unknown')[:80]
                    error_summary[err] = error_summary.get(err, 0) + 1

                summary_lines = [f"  {k}: {v}x" for k, v in error_summary.items()]
                actions_taken.append(
                    f"ESCALATE: {fail_count} failed tasks in 6h — may need code fix:\n"
                    + "\n".join(summary_lines)
                )
    except Exception as e:
        logger.error(f"[WATCHDOG] Failed task check failed: {e}")

    # ── Report ───────────────────────────────────────────────────────
    if actions_taken:
        msg = "🔧 Pipeline Watchdog Actions:\n\n" + "\n".join(f"• {a}" for a in actions_taken)
        send_telegram(msg)
        logger.info(f"[WATCHDOG] {len(actions_taken)} actions taken")
    else:
        logger.debug("[WATCHDOG] All clear, no actions needed")


def scheduled_pipeline_watchdog():
    """Scheduler wrapper for pipeline watchdog."""
    try:
        run_pipeline_watchdog()
    except Exception as e:
        logger.error(f"[WATCHDOG] Pipeline watchdog run failed: {e}")


def setup_scheduler():
    """Set up scheduled tasks."""
    # Get intervals from environment or use defaults
    scrape_interval = int(os.getenv('AGENTPULSE_SCRAPE_INTERVAL_HOURS', '6'))
    analysis_interval = int(os.getenv('AGENTPULSE_ANALYSIS_INTERVAL_HOURS', '12'))
    
    # Schedule tasks
    schedule.every(scrape_interval).hours.do(scheduled_scrape)
    schedule.every(6).hours.do(scheduled_scrape_hackernews)
    schedule.every(12).hours.do(scheduled_scrape_github)
    schedule.every(6).hours.do(scheduled_scrape_rss)
    schedule.every(6).hours.do(scheduled_scrape_thought_leaders)
    schedule.every(6).hours.do(scheduled_scrape_x_source_accounts)
    # Newsletter pipeline (times in UTC, CET = UTC+1):
    # GENERATION — Friday (ready by 15:00 CET / 14:00 UTC for weekend review)
    #   08:00 — Topic evolution update (lifecycle phases)
    #   08:30 — Spotlight selection heuristic → writes research trigger
    #   08:30 — Research Agent picks up trigger (runs in its own container)
    #   08:30 — Prediction tracking (before newsletter)
    #   11:00 — Newsletter preparation (allows ~2.5h for Research Agent)
    #   12:00 — Newsletter notification (= 13:00 CET, draft ready for review)
    # PUBLISHING — Monday (12:00 CET / 11:00 UTC, after weekend review)
    #   11:00 — Auto-publish newsletter
    #   11:15 — Retry failed emails
    schedule.every().friday.at("08:00").do(scheduled_update_evolution)
    schedule.every().friday.at("08:30").do(scheduled_select_spotlight)
    schedule.every().friday.at("08:30").do(scheduled_track_predictions)
    schedule.every().friday.at("11:00").do(scheduled_prepare_newsletter)
    schedule.every().friday.at("12:00").do(scheduled_notify_newsletter)
    schedule.every().monday.at("11:00").do(scheduled_auto_publish_newsletter)
    schedule.every().monday.at("11:15").do(lambda: retry_failed_emails())

    # Recurring analysis & extraction
    schedule.every(analysis_interval).hours.do(scheduled_analyze)
    schedule.every(12).hours.do(scheduled_cluster)
    schedule.every(12).hours.do(scheduled_tool_scan)
    schedule.every(12).hours.do(scheduled_trending_topics)
    schedule.every().day.at("06:00").do(scheduled_update_stats)

    # Daily & periodic
    schedule.every().day.at("09:00").do(scheduled_digest)
    schedule.every().day.at("03:00").do(scheduled_cleanup)

    # Personal intelligence briefing (Phase 7A) — twice daily
    schedule.every().day.at("08:00").do(scheduled_personal_briefing)
    schedule.every().day.at("20:00").do(scheduled_personal_briefing)
    schedule.every(1).hours.do(scheduled_refresh_cache)
    schedule.every(60).minutes.do(scheduled_proactive_scan)
    schedule.every(10).minutes.do(scheduled_check_negotiation_timeouts)

    # X Distribution Pipeline
    #   06:00 UTC daily — surface candidates (= ~7am CET)
    #   Every 5 min — post approved content (quick poll)
    #   Monday 11:30 — generate newsletter thread (after auto-publish at 11:00)
    schedule.every().day.at("06:00").do(scheduled_surface_x_candidates)
    schedule.every(5).minutes.do(scheduled_post_approved_x)
    schedule.every().monday.at("11:30").do(scheduled_x_newsletter_thread)

    # Health checks — every 30 min
    schedule.every(30).minutes.do(scheduled_health_check)

    # Pipeline watchdog — autonomous self-healing every 15 min
    schedule.every(15).minutes.do(scheduled_pipeline_watchdog)

    schedule.every(6).hours.do(log_economics_context)

    logger.info(f"Scheduler configured: scrape every {scrape_interval}h, analyze every {analysis_interval}h, cluster every 12h, tool scan every 12h, trending every 12h")
    logger.info("Multi-source: HN scrape every 6h, GitHub scrape every 12h, RSS scrape every 6h, thought leaders every 6h")
    logger.info("Daily: tool stats at 06:00, digest at 09:00, cleanup at 03:00 UTC")
    logger.info("Monday pipeline: evolution 06:00, spotlight+predictions 06:30, newsletter 09:00, notify 10:00, auto-publish 13:00 UTC")
    logger.info("Hourly: workspace cache refresh, proactive anomaly scan")
    logger.info("Every 10min: negotiation timeout check")
    logger.info("Personal briefing: 08:00 and 20:00 UTC daily")
    logger.info("X distribution: candidates at 06:00 daily, approved posting every 5min, newsletter thread Monday 11:30")
    logger.info("Newsletter: generation Friday 08:00-12:00 UTC, publish Monday 11:00 UTC")
    logger.info("Health checks: every 30min with 60min alert cooldown")
    logger.info("Pipeline watchdog: every 15min — auto-restart, stuck task reset, newsletter guard")

    # Catch-up: if today is Monday and we missed the newsletter trigger
    _check_missed_newsletter()


def _check_missed_newsletter():
    """On startup, check if we missed the Friday newsletter trigger."""
    now = datetime.now(timezone.utc)
    if now.weekday() != 4:  # Not Friday
        return
    if now.hour < 11:  # Before trigger time
        return
    if not supabase:
        return
    try:
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        existing = supabase.table('agent_tasks')\
            .select('id')\
            .eq('task_type', 'write_newsletter')\
            .gte('created_at', today_start)\
            .execute()
        if not existing.data:
            logger.info("[PIPELINE] Catch-up: missed Friday newsletter trigger, running now")
            scheduled_prepare_newsletter()
    except Exception as e:
        logger.error(f"[PIPELINE] Catch-up check failed: {e}")


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
    parser.add_argument('--task', choices=['scrape', 'analyze', 'cluster', 'opportunities', 'extract_tools', 'extract_trending_topics', 'update_tool_stats', 'run_investment_scan', 'prepare_analysis', 'prepare_newsletter', 'preview_newsletter', 'publish_newsletter', 'create_predictions', 'digest', 'cleanup', 'queue', 'watch', 'create_agent_task', 'check_task', 'get_budget_status', 'targeted_scrape', 'can_create_subtask', 'proactive_scan', 'send_alert', 'create_negotiation', 'respond_to_negotiation', 'get_active_negotiations', 'get_recent_alerts', 'deduplicate_opportunities', 'scrape_hackernews', 'scrape_github', 'track_predictions', 'extract_problems_multisource', 'extract_tools_multisource', 'extract_trending_topics_multisource', 'get_predictions', 'get_source_status', 'create_manual_prediction', 'scrape_rss', 'scrape_thought_leaders', 'update_topic_evolution', 'get_topic_evolution', 'get_topic_thesis', 'get_freshness_status', 'queue_research', 'get_research_queue', 'get_spotlight', 'get_scorecard', 'get_spotlight_cooldown', 'select_spotlight', 'flag_prediction', 'resolve_prediction', 'run_research', 'run_full_pipeline', 'get_subscriber_stats', 'personal_briefing', 'get_agent_wallets', 'get_agent_ledger', 'topup_agent', 'surface_x_candidates', 'x_approve', 'x_reject', 'x_edit', 'x_draft', 'post_approved_x', 'get_x_plan', 'get_x_posted', 'get_x_budget', 'x_watch', 'x_unwatch', 'x_watchlist', 'health_check'],
                        default='watch', help='Task to run')
    parser.add_argument('--once', action='store_true', help='Run once instead of watching')
    parser.add_argument('--no-schedule', action='store_true', help='Disable scheduled tasks in watch mode')
    parser.add_argument('--edition', type=int, help='Override edition number for newsletter preparation')
    args = parser.parse_args()
    
    init_clients()
    logger.info(f"Model routing: {json.dumps(get_model_config())}")
    
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
    
    elif args.task == 'extract_trending_topics':
        result = extract_trending_topics()
        print(json.dumps(result, indent=2))
    
    elif args.task == 'update_tool_stats':
        result = update_tool_stats()
        print(json.dumps(result, indent=2))
    
    elif args.task == 'run_investment_scan':
        extract_result = extract_tool_mentions(hours_back=168)
        stats_result = update_tool_stats()
        print(json.dumps({'extract_tools': extract_result, 'tool_stats': stats_result}, indent=2))
    
    elif args.task == 'prepare_analysis':
        result = prepare_analysis_package()
        print(json.dumps(result, default=str, indent=2))
    
    elif args.task == 'prepare_newsletter':
        result = prepare_newsletter_data(edition_override=args.edition)
        print(json.dumps(result, default=str, indent=2))
    
    elif args.task == 'preview_newsletter':
        result = preview_newsletter()
        print(json.dumps(result, default=str, indent=2))

    elif args.task == 'publish_newsletter':
        result = publish_newsletter()
        print(json.dumps(result, default=str, indent=2))
    
    elif args.task == 'create_predictions':
        newsletter_id = input("Newsletter ID: ").strip() if not sys.stdin.isatty() else None
        if not newsletter_id:
            latest = supabase.table('newsletters').select('id').order('created_at', desc=True).limit(1).execute()
            newsletter_id = latest.data[0]['id'] if latest.data else None
        if newsletter_id:
            result = create_predictions_from_newsletter(newsletter_id)
            print(json.dumps(result, default=str, indent=2))
        else:
            print(json.dumps({'error': 'No newsletter found'}, indent=2))
    
    elif args.task == 'digest':
        scheduled_digest()
    
    elif args.task == 'cleanup':
        scheduled_cleanup()
    
    elif args.task == 'get_budget_status':
        result = get_daily_usage()
        print(json.dumps(result, default=str, indent=2))
    
    elif args.task == 'deduplicate_opportunities':
        result = deduplicate_opportunities()
        print(json.dumps(result, default=str, indent=2))
    
    elif args.task == 'scrape_hackernews':
        result = scrape_hackernews()
        print(json.dumps(result, default=str, indent=2))
    
    elif args.task == 'scrape_github':
        result = scrape_github()
        print(json.dumps(result, default=str, indent=2))

    elif args.task == 'scrape_thought_leaders':
        result = scrape_thought_leaders()
        print(json.dumps(result, default=str, indent=2))
    
    elif args.task == 'track_predictions':
        result = track_predictions()
        print(json.dumps(result, default=str, indent=2))
    
    elif args.task == 'extract_problems_multisource':
        result = extract_problems_multisource()
        print(json.dumps(result, default=str, indent=2))
    
    elif args.task == 'extract_tools_multisource':
        result = extract_tools_multisource()
        print(json.dumps(result, default=str, indent=2))
    
    elif args.task == 'extract_trending_topics_multisource':
        result = extract_trending_topics_multisource()
        print(json.dumps(result, default=str, indent=2))
    
    elif args.task == 'update_topic_evolution':
        result = update_topic_evolution()
        print(json.dumps(result, default=str, indent=2))
    
    elif args.task == 'select_spotlight':
        result = select_spotlight_topic()
        print(json.dumps(result, default=str, indent=2))

    elif args.task == 'run_full_pipeline':
        run_full_newsletter_pipeline()

    elif args.task == 'personal_briefing':
        result = generate_personal_briefing()
        print(json.dumps(result, indent=2))

    elif args.task == 'get_agent_wallets':
        result = get_agent_wallets()
        print(json.dumps(result, default=str, indent=2))

    elif args.task == 'get_agent_ledger':
        result = get_agent_ledger('processor')
        print(json.dumps(result, default=str, indent=2))

    elif args.task == 'topup_agent':
        result = topup_agent('processor', 10000)
        print(json.dumps(result, default=str, indent=2))

    elif args.task == 'surface_x_candidates':
        result = surface_x_content_candidates()
        print(json.dumps(result, default=str, indent=2))

    elif args.task == 'post_approved_x':
        result = post_approved_x_content()
        print(json.dumps(result, default=str, indent=2))

    elif args.task == 'get_x_plan':
        send_x_morning_briefing()
        print("Morning briefing sent to Telegram")

    elif args.task == 'get_x_posted':
        result = get_x_posted_today()
        print(json.dumps(result, default=str, indent=2))

    elif args.task == 'get_x_budget':
        result = get_x_budget_status()
        print(json.dumps(result, default=str, indent=2))

    elif args.task == 'x_watchlist':
        result = manage_x_watchlist(action='list')
        print(json.dumps(result, default=str, indent=2))

    elif args.task == 'health_check':
        result = run_health_checks()
        print(json.dumps(result, default=str, indent=2))

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
            
            # Populate workspace cache immediately so Gato can read data
            logger.info("Populating workspace cache...")
            try:
                refresh_workspace_cache()
            except Exception as e:
                logger.error(f"Initial cache refresh failed: {e}")
        
        # Log economics at startup
        log_economics_context()

        # Main loop: file queue + DB tasks + scheduled tasks
        logger.info("Starting queue watcher (multi-agent mode)...")
        welcome_check_counter = 0
        while True:
            process_queue()                   # legacy file-based queue
            process_db_tasks('processor')     # processor-specific tasks
            # NOTE: analyst tasks are handled by the analyst container's poller.
            # NOTE: newsletter tasks are handled by the newsletter container's poller.
            schedule.run_pending()            # scheduled scrape/analyze/digest/cleanup

            # Check for pending welcome emails every ~60s (12 iterations * 5s)
            welcome_check_counter += 1
            if welcome_check_counter >= 12:
                welcome_check_counter = 0
                process_pending_welcome_emails()

            time.sleep(5)
    
    else:
        print(f"Unknown task: {args.task}")
        sys.exit(1)

if __name__ == '__main__':
    main()
