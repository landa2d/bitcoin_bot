"""
Gato Brain — Conversational intelligence middleware for AgentPulse.

Sits between Gato's Telegram handler and the LLM.
Handles: session management, conversation memory, rate limiting, response generation.
"""

import hmac
import json
import logging
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from contextlib import asynccontextmanager

import anthropic
import httpx
from fastapi import FastAPI, HTTPException, Header, Query, Request
from pydantic import BaseModel
from supabase import create_client, Client

import asyncio
import subprocess
import threading

import code_commands
import cto_commands
import corpus_probe
import intent_router
import query_templates
import web_search

# ─── Configuration ───────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
ANTHROPIC_AGENT_KEY = os.getenv("ANTHROPIC_AGENT_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
LLM_PROXY_URL = os.getenv("LLM_PROXY_URL", "")
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")
PORT = int(os.getenv("GATO_BRAIN_PORT", "8100"))
WALLET_AGENT_NAME = os.getenv("WALLET_AGENT_NAME", "gato")
OPENCLAW_DATA_DIR = os.getenv("OPENCLAW_DATA_DIR", "/home/openclaw/.openclaw")

SESSION_TIMEOUT_MINUTES = 60
HISTORY_LIMIT = 10

TIER_LIMITS = {
    "owner": {"messages": None, "web_searches": None},
    "subscriber": {"messages": 100, "web_searches": 20},
    "free": {"messages": 20, "web_searches": 5},
}

# ─── Logging ─────────────────────────────────────────────────────────

LOG_DIR = Path(OPENCLAW_DATA_DIR) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "gato-brain.log"),
    ],
)
logger = logging.getLogger("gato-brain")

# ─── Globals ─────────────────────────────────────────────────────────

supabase: Client | None = None
claude_client: anthropic.Anthropic | None = None
deepseek_client: httpx.Client | None = None

_system_prompt_cache: str | None = None
_system_prompt_mtime: float = 0


# ─── Models ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    user_id: str
    message: str
    message_type: str = "text"


class ChatResponse(BaseModel):
    response: str
    session_id: str
    intent: str
    metadata: dict = {}


# ─── System prompt loading ───────────────────────────────────────────

def load_system_prompt() -> str:
    """Load system prompt from SOUL.md / persona.md, caching by mtime."""
    global _system_prompt_cache, _system_prompt_mtime

    candidates = [
        Path(OPENCLAW_DATA_DIR) / "workspace" / "SOUL.md",
        Path(OPENCLAW_DATA_DIR) / "config" / "persona.md",
        Path("/home/openclaw/persona.md"),
    ]

    for path in candidates:
        if path.exists():
            mtime = path.stat().st_mtime
            if _system_prompt_cache and mtime == _system_prompt_mtime:
                return _system_prompt_cache
            _system_prompt_cache = path.read_text(encoding="utf-8")
            _system_prompt_mtime = mtime
            logger.info(f"Loaded system prompt from {path}")
            return _system_prompt_cache

    _system_prompt_cache = (
        "You are Gato, an AI intelligence agent and Bitcoin maximalist. "
        "You are knowledgeable about Bitcoin, cryptocurrency markets, AI agents, "
        "and technology. Be helpful, concise, and opinionated. "
        "Back up claims with facts. Be witty but substantive."
    )
    return _system_prompt_cache


# ─── Economics context (self-awareness) ──────────────────────────────

_economics_cache: str | None = None
_economics_fetched_at: float = 0
_ECONOMICS_TTL = 300


def fetch_economics_block() -> str:
    """Fetch Gato's spending summary from the proxy wallet endpoint.
    Non-blocking: returns empty string on any failure. 2-second timeout.
    Gato gets conversational framing so it can answer user questions about its budget."""
    global _economics_cache, _economics_fetched_at

    now = time.time()
    if _economics_cache is not None and (now - _economics_fetched_at) < _ECONOMICS_TTL:
        return _economics_cache

    if not LLM_PROXY_URL or not AGENT_API_KEY:
        return ""

    try:
        resp = httpx.get(
            f"{LLM_PROXY_URL}/v1/proxy/wallet/{WALLET_AGENT_NAME}/summary?period=7d",
            headers={"Authorization": f"Bearer {AGENT_API_KEY}"},
            timeout=5,
        )
        if resp.status_code != 200:
            logger.debug(f"Economics fetch returned {resp.status_code}")
            return _economics_cache or ""
        d = resp.json()
        cap_sats = d.get("spending_cap_sats") or 0
        cap_window = d.get("spending_cap_window") or "n/a"
        util = d.get("budget_utilization_pct")
        util_str = f"{util}%" if util is not None else "no cap"
        trend_str = d.get("trend_vs_previous_period", "flat")
        _economics_cache = (
            "\n\n---\n"
            "YOUR ECONOMICS (last 7 days) — you may share this when users ask about your costs, "
            "budget, spending, or how much you cost to run:\n"
            f"Balance: {d['balance_sats']:,} sats | Spent: {d['spent_sats']:,} sats | Calls: {d['calls']:,}\n"
            f"Budget utilization: {util_str} of {cap_sats:,} sats {cap_window} cap\n"
            f"Cap hits: {d.get('cap_hits_in_period', 0)} | Trend: {trend_str} vs prior week\n"
            "---"
        )
        _economics_fetched_at = now
        logger.info(f"Economics context refreshed: {d['spent_sats']} sats spent, {d['calls']} calls")
    except Exception as e:
        logger.debug(f"Economics fetch failed (non-critical): {e}")

    return _economics_cache or ""


# ─── Supabase helpers ────────────────────────────────────────────────

def ensure_user(user_id: str) -> dict:
    """Get or auto-create a corpus_users row. Returns the user record."""
    result = supabase.table("corpus_users").select("*").eq("telegram_id", user_id).execute()
    if result.data:
        return result.data[0]

    new_user = {"telegram_id": user_id, "access_tier": "free"}
    insert = supabase.table("corpus_users").insert(new_user).execute()
    logger.info(f"Auto-created corpus_user: {user_id} (free tier)")
    return insert.data[0]


def get_active_session(user_id: str) -> dict | None:
    """Find the user's active session, if any."""
    result = (
        supabase.table("conversation_sessions")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_last_message_time(session_id: str) -> datetime | None:
    """Get the timestamp of the most recent message in a session."""
    result = (
        supabase.table("conversation_messages")
        .select("created_at")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    return datetime.fromisoformat(result.data[0]["created_at"])


def close_session(session_id: str, messages: list[dict]) -> None:
    """Close a session: generate summary via DeepSeek, set is_active=false."""
    summary = generate_session_summary(messages)
    supabase.table("conversation_sessions").update({
        "is_active": False,
        "summary": summary,
        "last_active_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", session_id).execute()
    logger.info(f"Closed session {session_id}")


def create_session(user_id: str) -> dict:
    """Create a new active conversation session."""
    now = datetime.now(timezone.utc).isoformat()
    result = (
        supabase.table("conversation_sessions")
        .insert({
            "user_id": user_id,
            "is_active": True,
            "started_at": now,
            "last_active_at": now,
        })
        .execute()
    )
    logger.info(f"Created session {result.data[0]['id']} for {user_id}")
    return result.data[0]


def load_history(session_id: str, limit: int = HISTORY_LIMIT) -> list[dict]:
    """Load recent messages from a session."""
    result = (
        supabase.table("conversation_messages")
        .select("role, content, created_at")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    # Reverse so oldest first
    return list(reversed(result.data)) if result.data else []


def save_message(session_id: str, role: str, content: str,
                 retrieval_context: dict | None = None) -> None:
    """Save a message and update session last_active_at."""
    supabase.table("conversation_messages").insert({
        "session_id": session_id,
        "role": role,
        "content": content,
        "retrieval_context": retrieval_context or {},
    }).execute()

    supabase.table("conversation_sessions").update({
        "last_active_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", session_id).execute()


# ─── Rate limiting ───────────────────────────────────────────────────

def check_rate_limit(user_id: str, access_tier: str) -> str | None:
    """Check if user has exceeded daily limits. Returns a message if limited, else None."""
    limits = TIER_LIMITS.get(access_tier, TIER_LIMITS["free"])
    if limits["messages"] is None:
        return None  # owner — unlimited

    today = date.today().isoformat()
    result = (
        supabase.table("user_usage")
        .select("message_count, web_search_count")
        .eq("user_id", user_id)
        .eq("usage_date", today)
        .execute()
    )

    if not result.data:
        return None  # No usage today

    usage = result.data[0]
    if (usage["message_count"] or 0) >= limits["messages"]:
        return (
            f"You've reached your daily limit of {limits['messages']} messages. "
            f"Limits reset at midnight UTC. "
            f"Upgrade to subscriber for higher limits!"
        )
    return None


def check_web_search_limit(user_id: str, access_tier: str) -> str | None:
    """Check if user has exceeded daily web search limits. Returns message if limited."""
    limits = TIER_LIMITS.get(access_tier, TIER_LIMITS["free"])
    if limits["web_searches"] is None:
        return None  # owner — unlimited

    today = date.today().isoformat()
    result = (
        supabase.table("user_usage")
        .select("web_search_count")
        .eq("user_id", user_id)
        .eq("usage_date", today)
        .execute()
    )

    if not result.data:
        return None

    ws_count = result.data[0].get("web_search_count") or 0
    if ws_count >= limits["web_searches"]:
        return (
            f"Daily web search limit reached ({limits['web_searches']}). "
            f"Using corpus results instead."
        )
    return None


def increment_usage(user_id: str, messages: int = 1, web_searches: int = 0) -> None:
    """Increment daily usage counters, creating the row if needed."""
    today = date.today().isoformat()
    result = (
        supabase.table("user_usage")
        .select("id, message_count, web_search_count")
        .eq("user_id", user_id)
        .eq("usage_date", today)
        .execute()
    )

    if result.data:
        row = result.data[0]
        supabase.table("user_usage").update({
            "message_count": (row["message_count"] or 0) + messages,
            "web_search_count": (row["web_search_count"] or 0) + web_searches,
        }).eq("id", row["id"]).execute()
    else:
        supabase.table("user_usage").insert({
            "user_id": user_id,
            "usage_date": today,
            "message_count": messages,
            "web_search_count": web_searches,
        }).execute()


# ─── LLM calls ───────────────────────────────────────────────────────

def generate_session_summary(messages: list[dict]) -> str:
    """Generate a short session summary using DeepSeek V3."""
    if not messages:
        return "Empty session"

    if not DEEPSEEK_API_KEY:
        # Fallback: just use first/last message
        return f"Session with {len(messages)} messages"

    conversation = "\n".join(
        f"{m['role']}: {m['content'][:200]}" for m in messages[-10:]
    )

    try:
        response = deepseek_client.post(
            "/chat/completions",
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "Summarize this conversation in 1-2 sentences. Be concise."},
                    {"role": "user", "content": conversation},
                ],
                "temperature": 0.3,
                "max_tokens": 150,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"DeepSeek summary failed: {e}")
        return f"Session with {len(messages)} messages"


def generate_response(system_prompt: str, history: list[dict], user_message: str,
                      context_blocks: list[str] | None = None) -> tuple[str, int, int]:
    """Generate a response using Claude, with optional retrieval context injected.

    Returns: (response_text, latency_ms, output_tokens)
    """
    messages = []
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Build user message with context blocks prepended
    if context_blocks:
        context_text = "\n\n".join(context_blocks)
        full_user_msg = f"{context_text}\n\n---\nUSER MESSAGE: {user_message}"
    else:
        full_user_msg = user_message

    messages.append({"role": "user", "content": full_user_msg})

    try:
        start = time.time()
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            system=system_prompt,
            messages=messages,
            temperature=0.7,
            max_tokens=2048,
        )
        elapsed = int((time.time() - start) * 1000)
        text = response.content[0].text
        out_tokens = response.usage.output_tokens
        logger.info(f"Claude response in {elapsed}ms, {response.usage.input_tokens}+{out_tokens} tokens")
        return text, elapsed, out_tokens
    except Exception as e:
        logger.error(f"Claude generation failed: {e}")
        raise HTTPException(status_code=502, detail="LLM generation failed")


# ─── Retrieval path helpers ──────────────────────────────────────────

CITATION_INSTRUCTION = (
    "When the user asks for sources, cite the source table, edition number, date, "
    "and original source URL if available. Otherwise respond naturally without citations."
)


def format_corpus_context(results: list[dict]) -> str:
    """Format corpus retrieval results into a context block for Claude."""
    if not results:
        return ""
    lines = ["--- CORPUS INTELLIGENCE ---"]
    for i, r in enumerate(results, 1):
        source = r.get("source_table", "unknown")
        sim = r.get("similarity", 0)
        edition = r.get("edition_number")
        content = (r.get("content_text") or "")[:500]
        expanded = r.get("expanded", False)
        link_type = r.get("link_type", "")

        tag = f" [expanded via {link_type}]" if expanded else ""
        ed_tag = f" (edition #{edition})" if edition else ""
        lines.append(f"{i}. [{source}{ed_tag}] (similarity: {sim:.2f}){tag}")
        lines.append(f"   {content}")
    return "\n".join(lines)


def execute_corpus_path(route_result: dict, probe_results: dict) -> tuple[list[dict], str]:
    """CORPUS_QUERY / HYBRID: deep retrieval with graph expansion."""
    query_embedding = probe_results.get("query_embedding", [])
    if not query_embedding:
        return [], ""

    filters = route_result.get("corpus_filters", {})
    source_filter = filters.get("source_table")
    # Coerce to list — router may return a string instead of list
    if isinstance(source_filter, str):
        source_filter = [source_filter]
    date_from = filters.get("date_from")

    results = corpus_probe.deep_corpus_retrieval(
        supabase,
        query_embedding=query_embedding,
        match_count=10,
        source_filter=source_filter,
        date_from=date_from,
    )
    context_block = format_corpus_context(results)
    return results, context_block


def execute_structured_path(route_result: dict) -> tuple[dict, str]:
    """STRUCTURED_QUERY: execute a query template and format results."""
    template_name = route_result.get("template_name")
    template_params = route_result.get("template_params", {})

    if not template_name:
        return {}, ""

    result = query_templates.execute_template(supabase, template_name, template_params)
    context_block = f"--- STRUCTURED QUERY: {result['description']} ---\n{result['markdown']}"
    return result, context_block


def execute_followup_path(previous_retrieval_context: dict | None,
                          probe_results: dict) -> tuple[list[dict], str]:
    """FOLLOW_UP: re-hydrate previous retrieval chunks, optionally supplement."""
    rehydrated = []

    if previous_retrieval_context:
        # Get chunk IDs from previous response
        prev_chunks = previous_retrieval_context.get("retrieved_chunks", [])
        prev_expanded = previous_retrieval_context.get("expanded_chunks", [])
        all_ids = prev_chunks + prev_expanded

        # Re-fetch by ID (exact lookup, not vector search)
        for chunk_id in all_ids[:10]:
            try:
                resp = (
                    supabase.table("embeddings")
                    .select("id, source_table, source_id, content_text, metadata, edition_number")
                    .eq("id", chunk_id)
                    .limit(1)
                    .execute()
                )
                if resp.data:
                    row = resp.data[0]
                    row["similarity"] = 1.0  # Exact match
                    rehydrated.append(row)
            except Exception as e:
                logger.warning(f"Failed to re-hydrate chunk {chunk_id}: {e}")

    # Supplement with probe results if they had decent scores
    if probe_results.get("top_score", 0) >= 0.55 and probe_results.get("query_embedding"):
        supplement = corpus_probe.deep_corpus_retrieval(
            supabase,
            query_embedding=probe_results["query_embedding"],
            match_count=5,
        )
        seen_ids = {r.get("id") for r in rehydrated}
        for r in supplement:
            if str(r.get("id")) not in seen_ids:
                rehydrated.append(r)

    context_block = format_corpus_context(rehydrated)
    return rehydrated, context_block


# ─── Session resolution ─────────────────────────────────────────────

def resolve_session(user_id: str) -> dict:
    """Get or create the active session, closing stale ones."""
    session = get_active_session(user_id)

    if session:
        last_msg_time = get_last_message_time(session["id"])
        if last_msg_time:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
            # Ensure both are offset-aware for comparison
            if last_msg_time.tzinfo is None:
                last_msg_time = last_msg_time.replace(tzinfo=timezone.utc)
            if last_msg_time < cutoff:
                # Session is stale — close it and create a new one
                old_history = load_history(session["id"], limit=20)
                close_session(session["id"], old_history)
                session = None

    if not session:
        session = create_session(user_id)

    return session


# ─── Query logging ───────────────────────────────────────────────────

def log_query(user_id: str, session_id: str, query: str, intent: str,
              total_latency_ms: int, **kwargs) -> None:
    """Log query to query_log table with full observability fields."""
    try:
        row = {
            "user_id": user_id,
            "session_id": session_id,
            "user_query": query,
            "detected_intent": intent,
            "total_latency_ms": total_latency_ms,
        }
        # Optional observability fields
        for field in (
            "corpus_probe_top_score", "retrieval_source", "top_similarity_score",
            "chunks_retrieved", "chunks_expanded", "web_results_used",
            "template_name", "response_tokens",
            "probe_latency_ms", "router_latency_ms",
            "retrieval_latency_ms", "generation_latency_ms",
        ):
            if field in kwargs and kwargs[field] is not None:
                row[field] = kwargs[field]
        supabase.table("query_log").insert(row).execute()
    except Exception as e:
        logger.warning(f"Failed to log query: {e}")


# ─── Client initialization (sync, before uvicorn event loop) ─────────

def init_clients():
    """Initialize all API clients. Called from __main__ before uvicorn.run()."""
    global supabase, claude_client, deepseek_client

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
        raise RuntimeError("Supabase not configured")

    if not ANTHROPIC_AGENT_KEY:
        logger.error("ANTHROPIC_AGENT_KEY not set")
        raise RuntimeError("Anthropic API key not configured")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Claude client: route through proxy when available
    if LLM_PROXY_URL and AGENT_API_KEY:
        claude_client = anthropic.Anthropic(
            api_key=AGENT_API_KEY,
            base_url=f"{LLM_PROXY_URL}/anthropic",
        )
        logger.info("Claude client initialized via proxy (%s)", LLM_PROXY_URL)
    else:
        claude_client = anthropic.Anthropic(api_key=ANTHROPIC_AGENT_KEY)
        logger.warning("Claude client initialized DIRECT (no proxy) — calls will bypass spend tracking")
    logger.info("Supabase + Claude clients initialized")

    # OpenAI embeddings: route through proxy when available
    if OPENAI_API_KEY:
        if LLM_PROXY_URL and AGENT_API_KEY:
            corpus_probe.init(AGENT_API_KEY, base_url=f"{LLM_PROXY_URL}/v1")
            logger.info("Corpus probe initialized via proxy")
        else:
            corpus_probe.init(OPENAI_API_KEY)
    else:
        logger.warning("OPENAI_API_KEY not set — corpus probe disabled")

    if TAVILY_API_KEY:
        web_search.init(TAVILY_API_KEY)
    else:
        logger.warning("TAVILY_API_KEY not set — web search disabled")

    # DeepSeek client: route through proxy when available
    if DEEPSEEK_API_KEY:
        if LLM_PROXY_URL and AGENT_API_KEY:
            ds_base = f"{LLM_PROXY_URL}/v1"
            ds_key = AGENT_API_KEY
            logger.info("DeepSeek client initialized via proxy (%s)", LLM_PROXY_URL)
        else:
            ds_base = DEEPSEEK_BASE_URL
            ds_key = DEEPSEEK_API_KEY
            logger.warning("DeepSeek client initialized DIRECT (no proxy) — calls will bypass spend tracking")
        deepseek_client = httpx.Client(
            base_url=ds_base,
            headers={
                "Authorization": f"Bearer {ds_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        intent_router.init(deepseek_client)
    else:
        logger.warning("DEEPSEEK_API_KEY not set — session summaries will be basic, intent router will use heuristic")

    # Start daily embedding scheduler
    threading.Thread(target=_start_daily_embed_scheduler, daemon=True).start()
    logger.info("Daily embedding scheduler started (14:00 UTC)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Shutdown hook for cleanup."""
    yield
    if deepseek_client:
        deepseek_client.close()


app = FastAPI(title="Gato Brain", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    """Health check with active session count."""
    try:
        result = (
            supabase.table("conversation_sessions")
            .select("id", count="exact")
            .eq("is_active", True)
            .execute()
        )
        active = result.count if result.count is not None else 0
    except Exception:
        active = -1
    return {"status": "ok", "active_sessions": active}


# ─── Ops endpoint — autonomous container management ────────────────

@app.post("/ops/restart")
async def ops_restart(request: Request):
    """Restart a Docker container by service name. Called by processor watchdog."""
    body = await request.json()
    service = body.get("service", "")
    reason = body.get("reason", "unknown")
    secret = request.headers.get("X-Ops-Secret", "")

    # Auth: reuse the inter-service secret
    expected = os.getenv("CODE_SESSION_SECRET", "")
    if not expected or secret != expected:
        return {"error": "unauthorized"}

    allowed = {"newsletter", "analyst", "research", "web"}
    if service not in allowed:
        return {"error": f"service '{service}' not in allowed list: {allowed}"}

    logger.info(f"[OPS] Restart requested: {service} — reason: {reason}")
    try:
        import docker as dockerlib
        client = dockerlib.from_env()
        # Map service name to container name
        container_map = {
            "newsletter": "agentpulse-newsletter",
            "analyst": "agentpulse-analyst",
            "research": "agentpulse-research",
            "web": "agentpulse-web",
        }
        container_name = container_map.get(service, f"agentpulse-{service}")
        container = client.containers.get(container_name)
        container.restart(timeout=30)
        logger.info(f"[OPS] Restarted {container_name}")
        return {"status": "restarted", "service": service}
    except Exception as e:
        logger.error(f"[OPS] Restart failed for {service}: {e}")
        return {"error": str(e)}


@app.get("/ops/container-status/{service}")
async def ops_container_status(service: str):
    """Return container health status for a service."""
    try:
        import docker as dockerlib
        client = dockerlib.from_env()
        container_map = {
            "newsletter": "agentpulse-newsletter",
            "analyst": "agentpulse-analyst",
            "research": "agentpulse-research",
            "processor": "agentpulse-processor",
            "web": "agentpulse-web",
        }
        container_name = container_map.get(service, f"agentpulse-{service}")
        container = client.containers.get(container_name)
        return {
            "service": service,
            "status": container.status,
            "health": container.attrs.get("State", {}).get("Health", {}).get("Status", "unknown"),
        }
    except Exception as e:
        return {"service": service, "status": "not_found", "error": str(e)}


# ─── Embedding pipeline trigger ─────────────────────────────────────

_embed_lock = threading.Lock()
_last_embed_run: dict = {}


def _run_embed_pipeline(mode: str = "--incremental") -> dict:
    """Run embed_pipeline.py as a subprocess. Returns result dict."""
    if not _embed_lock.acquire(blocking=False):
        return {"status": "already_running"}

    try:
        t0 = time.time()
        result = subprocess.run(
            ["python3", "/home/openclaw/embed_pipeline.py", mode],
            capture_output=True,
            text=True,
            timeout=600,
            cwd="/home/openclaw",
        )
        elapsed = int(time.time() - t0)
        _last_embed_run.update({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "exit_code": result.returncode,
            "elapsed_s": elapsed,
            "stdout_tail": result.stdout[-500:] if result.stdout else "",
            "stderr_tail": result.stderr[-500:] if result.stderr else "",
        })

        if result.returncode == 0:
            logger.info(f"Embed pipeline ({mode}) completed in {elapsed}s")
        else:
            logger.warning(f"Embed pipeline ({mode}) failed (exit {result.returncode}) in {elapsed}s")

        return _last_embed_run
    except subprocess.TimeoutExpired:
        logger.error("Embed pipeline timed out (600s)")
        return {"status": "timeout", "mode": mode}
    except Exception as e:
        logger.error(f"Embed pipeline failed: {e}")
        return {"status": "error", "error": str(e)}
    finally:
        _embed_lock.release()


def _run_economics_report() -> str:
    """Run economics_report.py --dry-run and return the human-readable output."""
    try:
        result = subprocess.run(
            ["python3", "/root/bitcoin_bot/economics_report.py", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd="/root/bitcoin_bot",
        )
        if result.returncode == 0 and result.stdout.strip():
            # Truncate to fit Telegram's 4096 char limit with margin
            output = result.stdout.strip()
            if len(output) > 3900:
                output = output[:3900] + "\n... (truncated)"
            return output
        else:
            err = result.stderr.strip()[-300:] if result.stderr else "no output"
            logger.warning(f"/economics failed (exit {result.returncode}): {err}")
            return f"Economics report failed (exit {result.returncode}). Check logs."
    except subprocess.TimeoutExpired:
        return "Economics report timed out (30s limit)."
    except Exception as e:
        logger.error(f"/economics error: {e}")
        return f"Economics report error: {e}"


@app.post("/embed/incremental")
async def embed_incremental():
    """Trigger incremental embedding pipeline (non-blocking)."""
    def run():
        _run_embed_pipeline("--incremental")
    threading.Thread(target=run, daemon=True).start()
    return {"status": "triggered", "mode": "incremental"}


@app.post("/embed/backfill")
async def embed_backfill():
    """Trigger full backfill embedding pipeline (non-blocking)."""
    def run():
        _run_embed_pipeline("--backfill")
    threading.Thread(target=run, daemon=True).start()
    return {"status": "triggered", "mode": "backfill"}


@app.get("/embed/status")
async def embed_status():
    """Get last embedding pipeline run status."""
    return _last_embed_run or {"status": "never_run"}


def _start_daily_embed_scheduler():
    """Start a background thread that runs incremental embedding daily at 14:00 UTC."""
    import sched
    import calendar

    scheduler = sched.scheduler(time.time, time.sleep)

    def schedule_next():
        now = datetime.now(timezone.utc)
        # Next 14:00 UTC
        target = now.replace(hour=14, minute=0, second=0, microsecond=0)
        if target <= now:
            target = target + timedelta(days=1)
        delay = (target - now).total_seconds()
        logger.info(f"Next scheduled embedding run in {delay/3600:.1f}h at {target.isoformat()}")
        scheduler.enter(delay, 1, run_and_reschedule)

    def run_and_reschedule():
        logger.info("[SCHEDULED] Running daily incremental embedding pipeline")
        result = _run_embed_pipeline("--incremental")
        # Warn if 0 new rows
        stdout = result.get("stdout_tail", "")
        if "Total: 0 chunks" in stdout:
            logger.warning("[SCHEDULED] Embedding pipeline processed 0 new chunks — pipeline may not be producing content")
        schedule_next()

    schedule_next()
    scheduler.run()


# ─── X Distribution command handlers ─────────────────────────────────

def _parse_nums(text: str) -> list[int]:
    """Parse comma/space-separated integers from command arguments.
    E.g. '/x-approve 108, 109 110' → [108, 109, 110]
    """
    return [int(n) for n in re.findall(r"\d+", text)]


def _candidates_by_daily_index(daily_indexes: list[int]) -> list[dict]:
    """Look up x_content_candidates rows by daily_index values."""
    results = []
    for idx in daily_indexes:
        resp = (
            supabase.table("x_content_candidates")
            .select("id, daily_index, content_type, status, draft_content, suggested_angle, source_summary, source_url, suggested_tags")
            .eq("daily_index", idx)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            results.append(resp.data[0])
    return results


def _handle_x_approve(args: str) -> str:
    nums = _parse_nums(args)
    if not nums:
        return "Usage: /x-approve [numbers]\nExample: /x-approve 108 109"

    candidates = _candidates_by_daily_index(nums)
    if not candidates:
        return f"No candidates found with daily index {', '.join(str(n) for n in nums)}."

    approved = []
    already = []
    for c in candidates:
        if c["status"] == "approved":
            already.append(c["daily_index"])
            continue
        supabase.table("x_content_candidates").update(
            {"status": "approved"}
        ).eq("id", c["id"]).execute()
        approved.append(c["daily_index"])

    parts = []
    if approved:
        parts.append(f"Approved: {', '.join(str(n) for n in approved)}")
    if already:
        parts.append(f"Already approved: {', '.join(str(n) for n in already)}")

    missing = set(nums) - {c["daily_index"] for c in candidates}
    if missing:
        parts.append(f"Not found: {', '.join(str(n) for n in sorted(missing))}")

    return "\n".join(parts)


def _handle_x_reject(args: str) -> str:
    nums = _parse_nums(args)
    if not nums:
        return "Usage: /x-reject [numbers]\nExample: /x-reject 108 109"

    candidates = _candidates_by_daily_index(nums)
    if not candidates:
        return f"No candidates found with daily index {', '.join(str(n) for n in nums)}."

    rejected = []
    for c in candidates:
        supabase.table("x_content_candidates").update(
            {"status": "rejected"}
        ).eq("id", c["id"]).execute()
        rejected.append(c["daily_index"])

    parts = [f"Rejected: {', '.join(str(n) for n in rejected)}"]
    missing = set(nums) - {c["daily_index"] for c in candidates}
    if missing:
        parts.append(f"Not found: {', '.join(str(n) for n in sorted(missing))}")

    return "\n".join(parts)


def _generate_reply_draft(candidate: dict) -> str:
    """Auto-generate a reply draft for a candidate using Claude."""
    source = candidate.get("source_summary") or ""
    angle = candidate.get("suggested_angle") or ""
    url = candidate.get("source_url") or ""

    prompt = f"""You are an agent economy expert with a personal, opinionated X presence.
Write a ready-to-post reply tweet for the following post.

Original post: {source}
{f'URL: {url}' if url else ''}
{f'Suggested angle: {angle}' if angle else 'Pick a sharp, substantive angle.'}

Rules:
- MUST be under 280 characters
- Add value: an insight, a contrarian take, or a connection the author might not have considered
- Do NOT suck up or just agree. Be substantive, opinionated, and punchy
- Better too bold than too safe
- Output ONLY the tweet text, nothing else"""

    try:
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300,
        )
        draft = response.content[0].text.strip().strip('"')
        # Save to DB so it persists
        supabase.table("x_content_candidates").update(
            {"draft_content": draft}
        ).eq("id", candidate["id"]).execute()
        return draft
    except Exception as e:
        logger.error(f"Auto-draft generation failed: {e}")
        return "(draft generation failed — use /x-draft to write manually)"


def _handle_x_edit(args: str) -> str:
    nums = _parse_nums(args)
    if not nums:
        return "Usage: /x-edit [number]\nExample: /x-edit 108"

    candidates = _candidates_by_daily_index(nums[:1])
    if not candidates:
        return f"No candidate found with daily index {nums[0]}."

    c = candidates[0]
    draft = c.get("draft_content") or ""
    # Auto-generate draft if missing
    if not draft.strip():
        draft = _generate_reply_draft(c)
    angle = c.get("suggested_angle") or ""
    header = f"#{c['daily_index']} [{c['content_type']}] — {c['status']}"
    parts = [header]
    # Show source post for engagement replies
    if c.get("content_type") == "engagement_reply":
        source = c.get("source_summary") or ""
        url = c.get("source_url") or ""
        if source:
            parts.append(f"\nReplying to: {source}")
        if url:
            parts.append(url)
    if angle:
        parts.append(f"\nAngle: {angle}")
    parts.append(f"\n{draft}")
    parts.append(f"\nTo replace: /x-draft {c['daily_index']} [new text]")
    return "\n".join(parts)


def _handle_x_draft(args: str) -> str:
    """Replace draft_content for a candidate. Format: /x-draft [num] [new text]"""
    m = re.match(r"(\d+)\s+(.+)", args.strip(), re.DOTALL)
    if not m:
        return "Usage: /x-draft [number] [new text]\nExample: /x-draft 108 New tweet content here"

    idx = int(m.group(1))
    new_text = m.group(2).strip()
    candidates = _candidates_by_daily_index([idx])
    if not candidates:
        return f"No candidate found with daily index {idx}."

    c = candidates[0]
    supabase.table("x_content_candidates").update(
        {"draft_content": new_text, "final_content": new_text, "status": "approved"}
    ).eq("id", c["id"]).execute()
    return f"Draft replaced and approved for #{idx}. Processor will post when ready.\n\n{new_text}"


def _handle_x_arc() -> str:
    """Show the current active editorial arc, its thesis, and planned post sequence."""
    try:
        result = supabase.table("x_editorial_arc")\
            .select("*")\
            .eq("status", "active")\
            .order("week_start", desc=True)\
            .limit(1)\
            .execute()
    except Exception as e:
        return f"Failed to fetch arc: {e}"

    if not result.data:
        return "No active editorial arc.\nUse /x-arc-set [title] to create one."

    arc = result.data[0]
    sequence = arc.get("post_sequence") or []
    if isinstance(sequence, str):
        try:
            sequence = json.loads(sequence)
        except Exception:
            sequence = []

    lines = [
        "\U0001f4d6 Active Editorial Arc\n",
        f"Title: {arc.get('arc_title', '')}",
        f"Pillar: {arc.get('pillar', '')}",
        f"Week: {arc.get('week_start', '')}",
        f"Status: {arc.get('status', '')}",
        f"\nThesis: {arc.get('arc_thesis', '')}",
        f"\nOverarching: {arc.get('overarching_thesis', '')}",
    ]

    if sequence:
        lines.append("\nPost Sequence:")
        for entry in sequence:
            day = entry.get("day", "?").upper()
            angle = entry.get("angle", "")
            lines.append(f"  {day}: {angle}")

    return "\n".join(lines)


def _handle_x_arc_set(args: str) -> str:
    """Create a new active editorial arc. Usage: /x-arc-set [title]
    Uses LLM to generate arc details from the title."""
    if not args.strip():
        return "Usage: /x-arc-set [arc title]\nExample: /x-arc-set The Hidden Cost Problem"

    arc_title = args.strip()

    # Deactivate any current active arc
    try:
        active = supabase.table("x_editorial_arc")\
            .select("id")\
            .eq("status", "active")\
            .execute()
        for row in (active.data or []):
            supabase.table("x_editorial_arc").update(
                {"status": "completed"}
            ).eq("id", row["id"]).execute()
    except Exception as e:
        logger.warning(f"Failed to deactivate old arcs: {e}")

    # Determine week_start (Monday of current week)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    # Use LLM to generate arc details from the title
    arc_thesis = ""
    pillar = "economics"
    post_sequence = []

    if deepseek_client:
        try:
            prompt = f"""You are designing a weekly editorial arc for an X/Twitter presence focused on the agent economy.

Arc title: "{arc_title}"

Generate:
1. pillar: either "economics" or "trust" — whichever this arc is about
2. arc_thesis: 1-2 sentences — the argument this arc builds toward
3. post_sequence: a planned sequence of 3-5 posts across the week

Respond as JSON:
{{"pillar": "economics|trust", "arc_thesis": "...", "post_sequence": [{{"day": "mon", "angle": "hook — ..."}}, {{"day": "wed", "angle": "evidence — ..."}}, {{"day": "fri", "angle": "lesson — ..."}}]}}"""

            response = deepseek_client.post(
                "/chat/completions",
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "You output valid JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.4,
                    "max_tokens": 1000,
                },
            )
            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"].strip()
            if raw.startswith("```"):
                import re as _re
                raw = _re.sub(r'^```\w*\n?', '', raw)
                raw = _re.sub(r'\n?```$', '', raw)
            arc_data = json.loads(raw)
            pillar = arc_data.get("pillar", "economics")
            arc_thesis = arc_data.get("arc_thesis", arc_title)
            post_sequence = arc_data.get("post_sequence", [])
        except Exception as e:
            logger.warning(f"LLM arc generation failed, using defaults: {e}")
            arc_thesis = arc_title

    if not arc_thesis:
        arc_thesis = arc_title

    try:
        supabase.table("x_editorial_arc").insert({
            "arc_title": arc_title,
            "pillar": pillar,
            "arc_thesis": arc_thesis,
            "week_start": week_start.isoformat(),
            "status": "active",
            "post_sequence": post_sequence,
        }).execute()
    except Exception as e:
        return f"Failed to create arc: {e}"

    # Format confirmation
    lines = [
        "\u2705 New editorial arc activated\n",
        f"Title: {arc_title}",
        f"Pillar: {pillar}",
        f"Thesis: {arc_thesis}",
        f"Week: {week_start.isoformat()}",
    ]
    if post_sequence:
        lines.append("\nPlanned sequence:")
        for entry in post_sequence:
            lines.append(f"  {entry.get('day', '?').upper()}: {entry.get('angle', '')}")

    return "\n".join(lines)


def _handle_x_plan() -> str:
    """Show today's content candidates + any unactioned engagement replies."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    # Today's candidates (all types)
    today_resp = (
        supabase.table("x_content_candidates")
        .select("daily_index, content_type, status, suggested_angle, draft_content, verification_status, source_summary, source_url, suggested_tags, narrative_context, content_category")
        .gte("created_at", today_start.isoformat())
        .order("daily_index")
        .execute()
    )
    # All unactioned engagement replies (may be from previous days)
    engage_resp = (
        supabase.table("x_content_candidates")
        .select("daily_index, content_type, status, suggested_angle, draft_content, verification_status, source_summary, source_url, suggested_tags, narrative_context, content_category")
        .eq("status", "candidate")
        .eq("content_type", "engagement_reply")
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    # Merge, deduplicating by daily_index
    today_indexes = {c.get("daily_index") for c in (today_resp.data or [])}
    merged = list(today_resp.data or [])
    for r in (engage_resp.data or []):
        if r.get("daily_index") not in today_indexes:
            merged.append(r)
            today_indexes.add(r.get("daily_index"))

    if not merged:
        return "No X content candidates."

    # Sort: narrative first, then sharp_takes, then engagement_replies, by daily_index
    type_order = {"narrative": 0, "sharp_take": 1, "newsletter_thread": 2, "prediction": 3, "engagement_reply": 4}
    merged.sort(key=lambda c: (type_order.get(c["content_type"], 9), c.get("daily_index", 0)))

    # Telegram limit is 4096 chars — budget ~3800 to leave room for summary
    CHAR_BUDGET = 3600
    lines = ["X Content Plan\n"]
    shown = 0
    omitted = 0

    def _format_draft(raw_draft):
        """Format draft_content for display. Parses JSON thread arrays into numbered tweets."""
        if not raw_draft:
            return []
        # Try parsing as JSON array (thread format)
        try:
            tweets = json.loads(raw_draft)
            if isinstance(tweets, list):
                lines = []
                for i, t in enumerate(tweets, 1):
                    text = str(t)[:120]
                    if len(str(t)) > 120:
                        text += "..."
                    lines.append(f"   Tweet {i}: {text}")
                return lines
        except (json.JSONDecodeError, TypeError):
            pass
        # Plain string draft
        preview = raw_draft[:120]
        if len(raw_draft) > 120:
            preview += "..."
        return [f"   Draft: {preview}"]

    def _format_candidate(c):
        idx = c.get("daily_index") or "?"
        status_icon = {"candidate": "\u23f3", "approved": "\u2705", "rejected": "\u274c",
                       "posted": "\ud83d\udce4", "expired": "\ud83d\udca4", "failed": "\u26a0\ufe0f"}.get(c["status"], "\u2022")
        verif = ""
        if c.get("verification_status") == "flagged":
            verif = " \u26a0\ufe0fFLAGGED"
        angle = (c.get("suggested_angle") or "")[:60]
        if len(c.get("suggested_angle") or "") > 60:
            angle += "..."

        entry = f"{status_icon} #{idx} [{c['content_type']}]"
        if c.get("content_type") == "engagement_reply":
            source = (c.get("source_summary") or "")[:100]
            if len(c.get("source_summary") or "") > 100:
                source += "..."
            if source:
                entry += f"\n   {source}"
            if angle:
                entry += f"\n   Reply angle: {angle}"
            draft_lines = _format_draft(c.get("draft_content"))
            for line in draft_lines:
                entry += f"\n{line}"
        else:
            entry += verif
            if c.get("source_url"):
                entry += f"\n   Source: {c['source_url']}"
            if c.get("source_summary"):
                summ = (c["source_summary"])[:120]
                if len(c["source_summary"]) > 120:
                    summ += "..."
                entry += f"\n   Summary: {summ}"
            if angle:
                entry += f"\n   Angle: {angle}"
            draft_lines = _format_draft(c.get("draft_content"))
            for line in draft_lines:
                entry += f"\n{line}"
            if c.get("narrative_context"):
                nc = (c["narrative_context"])[:80]
                if len(c["narrative_context"]) > 80:
                    nc += "..."
                entry += f"\n   Arc: {nc}"
        return entry

    def _append_section(candidates, header, lines, shown, omitted):
        if not candidates:
            return shown, omitted
        lines.append(header)
        for c in candidates:
            entry = _format_candidate(c)
            if len("\n".join(lines)) + len(entry) + 200 > CHAR_BUDGET:
                omitted = len(merged) - shown
                return shown, omitted
            lines.append(entry)
            shown += 1
        return shown, omitted

    narrative = [c for c in merged if c.get("content_type") == "narrative"]
    takes = [c for c in merged if c.get("content_type") in ("sharp_take", "newsletter_thread", "prediction")]
    engage = [c for c in merged if c.get("content_type") == "engagement_reply"]

    shown, omitted = _append_section(narrative, "\U0001f4d6 NARRATIVE (today's arc post):", lines, shown, omitted)
    if not omitted:
        shown, omitted = _append_section(takes, "\n\U0001f525 TAKES:", lines, shown, omitted)
    if not omitted:
        # Build engage header — reference today's arc angle if a narrative post exists
        engage_header = "\n\U0001f4ac ENGAGE:"
        if narrative:
            # Extract angle summary from the narrative candidate's source_summary
            arc_angle = ""
            for n in narrative:
                ss = n.get("source_summary") or ""
                if ss.startswith("[ARC] "):
                    # Format: "[ARC] Arc Title: angle text"
                    parts = ss.split(": ", 1)
                    arc_angle = parts[1] if len(parts) > 1 else ss[6:]
                    break
            if arc_angle:
                # Truncate angle for header
                if len(arc_angle) > 50:
                    arc_angle = arc_angle[:50] + "..."
                engage_header = f"\n\U0001f4ac ENGAGE (related to today's arc: {arc_angle}):"
        shown, omitted = _append_section(engage, engage_header, lines, shown, omitted)

    # Summary counts
    statuses = [c["status"] for c in merged]
    summary = f"\n{len(merged)} candidates \u2014 "
    summary += f"{statuses.count('candidate')} pending, "
    summary += f"{statuses.count('approved')} approved, "
    summary += f"{statuses.count('posted')} posted"
    if omitted:
        summary += f"\n({omitted} more not shown)"
    lines.append(summary)
    return "\n".join(lines)


def _handle_x_posted() -> str:
    """Show posts posted today."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    resp = (
        supabase.table("x_content_candidates")
        .select("daily_index, content_type, draft_content, posted_at, x_post_id")
        .eq("status", "posted")
        .gte("posted_at", today_start.isoformat())
        .order("posted_at")
        .execute()
    )
    if not resp.data:
        return "No posts published today."

    lines = ["Posted Today\n"]
    for c in resp.data:
        idx = c.get("daily_index") or "?"
        preview = (c.get("draft_content") or "")[:100]
        post_id = c.get("x_post_id") or ""
        lines.append(f"📤 #{idx} [{c['content_type']}]")
        if preview:
            lines.append(f"   {preview}")
        if post_id:
            lines.append(f"   https://x.com/i/status/{post_id}")
    return "\n".join(lines)


def _handle_x_budget() -> str:
    """Show X API spend for current week."""
    today = date.today()
    # Monday of current week
    week_start = today - timedelta(days=today.weekday())
    resp = (
        supabase.table("x_api_budget")
        .select("operation_type, estimated_cost, request_count")
        .eq("week_start", week_start.isoformat())
        .execute()
    )
    if not resp.data:
        return f"No X API spend this week (week of {week_start.isoformat()})."

    total_cost = sum(float(r.get("estimated_cost") or 0) for r in resp.data)
    total_requests = sum(r.get("request_count") or 0 for r in resp.data)

    lines = [f"X API Budget — Week of {week_start.isoformat()}\n"]
    by_op: dict[str, dict] = {}
    for r in resp.data:
        op = r["operation_type"]
        if op not in by_op:
            by_op[op] = {"cost": 0.0, "requests": 0}
        by_op[op]["cost"] += float(r.get("estimated_cost") or 0)
        by_op[op]["requests"] += r.get("request_count") or 0

    for op, data in sorted(by_op.items()):
        lines.append(f"  {op}: ${data['cost']:.4f} ({data['requests']} requests)")

    lines.append(f"\nTotal: ${total_cost:.4f} / $5.00 ({total_requests} requests)")
    remaining = max(0, 5.0 - total_cost)
    lines.append(f"Remaining: ${remaining:.4f}")
    return "\n".join(lines)


def _handle_x_watch(args: str) -> str:
    """Add an X handle to the watchlist. Format: /x-watch handle [category]"""
    parts = args.strip().split(None, 1)
    if not parts:
        return "Usage: /x-watch [handle] [category]\nExample: /x-watch @elonmusk tech"

    handle = parts[0].lstrip("@")
    category = parts[1] if len(parts) > 1 else None

    row = {"x_handle": handle, "active": True}
    if category:
        row["category"] = category

    try:
        supabase.table("x_watchlist").upsert(row, on_conflict="x_handle").execute()
        cat_msg = f" (category: {category})" if category else ""
        return f"Added @{handle} to watchlist{cat_msg}."
    except Exception as e:
        logger.warning(f"x-watch failed: {e}")
        return f"Failed to add @{handle}: {e}"


def _handle_x_unwatch(args: str) -> str:
    """Remove an X handle from the watchlist."""
    handle = args.strip().lstrip("@")
    if not handle:
        return "Usage: /x-unwatch [handle]\nExample: /x-unwatch @elonmusk"

    supabase.table("x_watchlist").update(
        {"active": False}
    ).eq("x_handle", handle).execute()
    return f"Removed @{handle} from watchlist."


def _handle_x_watchlist() -> str:
    """Show active watchlist entries."""
    resp = (
        supabase.table("x_watchlist")
        .select("x_handle, display_name, category, priority")
        .eq("active", True)
        .order("priority", desc=True)
        .execute()
    )
    if not resp.data:
        return "Watchlist is empty."

    lines = ["X Watchlist\n"]
    for w in resp.data:
        name = w.get("display_name") or ""
        cat = f" [{w['category']}]" if w.get("category") else ""
        pri = f" (priority: {w['priority']})" if w.get("priority") else ""
        display = f"@{w['x_handle']}"
        if name:
            display += f" ({name})"
        lines.append(f"  {display}{cat}{pri}")

    lines.append(f"\n{len(resp.data)} accounts watched")
    return "\n".join(lines)


def handle_x_command(message: str) -> str:
    """Dispatch /x-* commands to their handlers."""
    msg = message.strip()
    # Split into command and args
    parts = msg.split(None, 1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    try:
        if cmd == "/x-approve":
            return _handle_x_approve(args)
        elif cmd == "/x-reject":
            return _handle_x_reject(args)
        elif cmd == "/x-edit":
            return _handle_x_edit(args)
        elif cmd == "/x-draft":
            return _handle_x_draft(args)
        elif cmd == "/x-plan":
            return _handle_x_plan()
        elif cmd == "/x-posted":
            return _handle_x_posted()
        elif cmd == "/x-budget":
            return _handle_x_budget()
        elif cmd == "/x-watch":
            return _handle_x_watch(args)
        elif cmd == "/x-unwatch":
            return _handle_x_unwatch(args)
        elif cmd == "/x-watchlist":
            return _handle_x_watchlist()
        elif cmd == "/x-arc":
            return _handle_x_arc()
        elif cmd == "/x-arc-set":
            return _handle_x_arc_set(args)
        else:
            return f"Unknown X command: {cmd}\nAvailable: /x-plan, /x-approve, /x-reject, /x-edit, /x-draft, /x-posted, /x-budget, /x-watch, /x-unwatch, /x-watchlist, /x-arc, /x-arc-set"
    except Exception as e:
        logger.error(f"X command failed: {cmd} — {e}")
        return f"Command failed: {e}"


# ─── Agent Wallet Summary ─────────────────────────────────────────

def _resolve_api_key(authorization: str | None) -> dict | None:
    """Look up agent_api_keys row from Bearer token. Returns None on miss."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    try:
        result = supabase.table("agent_api_keys").select("*").eq("api_key", token).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def _parse_period(period: str | None, from_date: str | None, to_date: str | None):
    """Return (start_dt, end_dt, label) or raise HTTPException(400)."""
    now = datetime.now(timezone.utc)
    if from_date and to_date:
        try:
            start = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc)
            end = datetime.fromisoformat(to_date).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
        except ValueError:
            raise HTTPException(400, "Invalid date format. Use YYYY-MM-DD.")
        return start, end, f"{from_date}_to_{to_date}"

    mapping = {"1d": 1, "7d": 7, "30d": 30}
    if period not in mapping:
        raise HTTPException(400, f"Invalid period '{period}'. Use 1d, 7d, 30d, or from/to date params.")
    days = mapping[period]
    start = now - timedelta(days=days)
    return start, now, period


@app.get("/v1/proxy/wallet/{agent_name}/summary")
async def wallet_summary(
    agent_name: str,
    period: str = Query("7d"),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    authorization: str | None = Header(None),
):
    """Agent self-awareness: spending summary for a given period."""
    # ── Auth ──
    key_row = _resolve_api_key(authorization)
    if not key_row:
        raise HTTPException(401, "Missing or invalid API key")

    if not key_row["is_admin"] and key_row["agent_name"] != agent_name:
        raise HTTPException(403, "Agents can only view their own wallet")

    # ── Agent exists? ──
    wallet_res = supabase.table("agent_wallets").select("*").eq("agent_name", agent_name).limit(1).execute()
    if not wallet_res.data:
        raise HTTPException(404, f"Agent '{agent_name}' not found")
    wallet = wallet_res.data[0]

    # ── Period ──
    start_dt, end_dt, period_label = _parse_period(period, from_date, to_date)
    iso_start = start_dt.isoformat()
    iso_end = end_dt.isoformat()

    # ── Spend in period (from agent_transactions) ──
    txns = (
        supabase.table("agent_transactions")
        .select("amount_sats")
        .eq("agent_name", agent_name)
        .eq("transaction_type", "spend")
        .gte("created_at", iso_start)
        .lte("created_at", iso_end)
        .execute()
    )
    spent_sats = sum(t["amount_sats"] for t in (txns.data or []))

    # ── LLM call log stats in period ──
    calls_data = (
        supabase.table("llm_call_log")
        .select("model, task_type, estimated_cost")
        .eq("agent_name", agent_name)
        .gte("created_at", iso_start)
        .lte("created_at", iso_end)
        .execute()
    )
    rows = calls_data.data or []
    total_calls = len(rows)
    total_cost_usd = sum(r.get("estimated_cost", 0) or 0 for r in rows)
    spent_usd_cents = round(total_cost_usd * 100)

    # Models breakdown
    models_used: dict[str, int] = {}
    for r in rows:
        m = r.get("model", "unknown")
        models_used[m] = models_used.get(m, 0) + 1

    # Task type breakdown
    top_task_types: dict[str, int] = {}
    for r in rows:
        tt = r.get("task_type")
        if tt:
            top_task_types[tt] = top_task_types.get(tt, 0) + 1

    avg_cost = spent_sats // total_calls if total_calls > 0 else 0

    # ── Balance USD (approximate: use total_cost_usd ratio) ──
    # Approximate balance in USD cents from the sats/usd ratio in this period
    if spent_sats > 0 and spent_usd_cents > 0:
        sats_per_cent = spent_sats / spent_usd_cents
        balance_usd_cents = round(wallet["balance_sats"] / sats_per_cent) if sats_per_cent > 0 else 0
    else:
        balance_usd_cents = 0

    # ── Spending cap ──
    cap_res = supabase.table("agent_spending_caps").select("*").eq("agent_name", agent_name).limit(1).execute()
    cap_row = (cap_res.data or [None])[0]
    spending_cap_sats = cap_row["cap_sats"] if cap_row else 0
    spending_cap_window = cap_row["window"] if cap_row else "daily"

    budget_util = round((spent_sats / spending_cap_sats) * 100, 1) if spending_cap_sats > 0 else 0.0

    # ── Governance events in period ──
    gov_res = (
        supabase.table("governance_events")
        .select("id", count="exact")
        .eq("agent_name", agent_name)
        .gte("created_at", iso_start)
        .lte("created_at", iso_end)
        .execute()
    )
    governance_count = gov_res.count if gov_res.count is not None else 0

    # Cap hits in period
    cap_res2 = (
        supabase.table("governance_events")
        .select("id", count="exact")
        .eq("agent_name", agent_name)
        .eq("event_type", "cap_hit")
        .gte("created_at", iso_start)
        .lte("created_at", iso_end)
        .execute()
    )
    cap_hits = cap_res2.count if cap_res2.count is not None else 0

    # ── Trend vs previous period ──
    period_length = end_dt - start_dt
    prev_start = start_dt - period_length
    prev_end = start_dt
    prev_txns = (
        supabase.table("agent_transactions")
        .select("amount_sats")
        .eq("agent_name", agent_name)
        .eq("transaction_type", "spend")
        .gte("created_at", prev_start.isoformat())
        .lt("created_at", prev_end.isoformat())
        .execute()
    )
    prev_spent = sum(t["amount_sats"] for t in (prev_txns.data or []))
    if prev_spent > 0:
        pct_change = round(((spent_sats - prev_spent) / prev_spent) * 100)
        if pct_change >= 0:
            trend = f"up_{pct_change}pct"
        else:
            trend = f"down_{abs(pct_change)}pct"
    elif spent_sats > 0:
        trend = "new_activity"
    else:
        trend = "flat"

    return {
        "agent": agent_name,
        "period": period_label,
        "balance_sats": wallet["balance_sats"],
        "balance_usd_cents": balance_usd_cents,
        "spent_sats": spent_sats,
        "spent_usd_cents": spent_usd_cents,
        "calls": total_calls,
        "avg_cost_per_call_sats": avg_cost,
        "models_used": models_used,
        "budget_utilization_pct": budget_util,
        "spending_cap_sats": spending_cap_sats,
        "spending_cap_window": spending_cap_window,
        "cap_hits_in_period": cap_hits,
        "governance_events_in_period": governance_count,
        "trend_vs_previous_period": trend,
        "top_task_types": top_task_types if top_task_types else None,
    }


_GATO_BRAIN_SECRET = os.getenv("GATO_BRAIN_SECRET", "")


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, x_gato_secret: str = Header(None, alias="X-Gato-Secret")):
    """Main chat endpoint — session management, rate limiting, response generation."""
    if not _GATO_BRAIN_SECRET or not x_gato_secret or not hmac.compare_digest(_GATO_BRAIN_SECRET, x_gato_secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    start = time.time()

    # 1. Ensure user exists, get tier
    user = ensure_user(req.user_id)
    access_tier = user.get("access_tier") or "free"

    # 2. Rate limit check
    limit_msg = check_rate_limit(req.user_id, access_tier)
    if limit_msg:
        return ChatResponse(
            response=limit_msg,
            session_id="",
            intent="RATE_LIMITED",
            metadata={"access_tier": access_tier},
        )

    # 2b. Quick command-list trigger
    _msg_lower = req.message.strip().lower()
    if _msg_lower in ("commands", "help", "menu", "what can you do", "que puedes hacer"):
        return ChatResponse(
            response=(
                "📡 AgentPulse Commands\n\n"
                "📊 INTEL\n"
                "/toolradar — Trending tools with sentiment\n"
                "/toolcheck [name] — Stats for a specific tool\n"
                "/opps — Business opportunities\n"
                "/analysis — Analyst findings & confidence\n"
                "/signals — Market signals\n"
                "/curious — Fun trending topics\n"
                "/topics — Topic lifecycle & evolution\n"
                "/thesis [topic] — Analyst thesis on a topic\n\n"
                "📰 NEWSLETTER\n"
                "/brief — Latest newsletter (Telegram)\n"
                "/newsletter_full — Generate new edition\n"
                "/newsletter_preview — Preview on web (no send)\n"
                "/newsletter_publish — Publish draft\n"
                "/newsletter_revise [text] — Send revision notes\n"
                "/freshness — Excluded from next edition\n"
                "/subscribers — Subscriber count & modes\n\n"
                "🔍 RESEARCH\n"
                "/scan — Run full data pipeline\n"
                "/invest_scan — Investment scanner (7d)\n"
                "/deep_dive [topic] — Deep research\n"
                "/review [opp] — Review an opportunity\n"
                "/predictions — Prediction scorecard\n"
                "/predict [text] — Add a prediction\n"
                "/sources — Scraping status\n\n"
                "🧠 INTELLIGENCE\n"
                "/briefing — Personal intelligence briefing\n"
                "/context — Operator context & watch topics\n"
                "/watch [topic] — Add to watch list\n"
                "/alerts — Recent proactive alerts\n"
                "/budget — Agent usage vs limits\n\n"
                "🐦 X DISTRIBUTION\n"
                "/x-plan — Today's X candidates\n"
                "/x-approve [nums] — Approve (e.g. 1,3)\n"
                "/x-reject [nums] — Reject candidates\n"
                "/x-edit [num] — View draft to edit\n"
                "/x-draft [num] [text] — Replace draft\n"
                "/x-posted — Posted today\n"
                "/x-budget — X API spend\n"
                "/x-watch [handle] [cat] — Add to watchlist\n"
                "/x-unwatch [handle] — Remove from watchlist\n"
                "/x-watchlist — Show watchlist\n"
                "/x-arc — Current editorial arc & sequence\n"
                "/x-arc-set [title] — Set new arc focus\n\n"
                "💰 AGENT ECONOMY\n"
                "/wallet — Agent wallet balances\n"
                "/ledger [agent] — Last 10 transactions\n"
                "/topup [agent] [amt] — Top up wallet (sats)\n"
                "/negotiations — Active negotiations\n\n"
                "💻 CODE ENGINE\n"
                "/code [repo] [instruction] — Start coding session\n"
                "/code-diff — View session diff\n"
                "/code-approve — Approve: commit + push + PR\n"
                "/code-reject — Reject: discard changes\n"
                "/code-merge — Merge latest PR\n"
                "/followup [instruction] — Continue session\n"
                "/repos — List registered repos\n"
                "/code-status — Session status\n\n"
                "⚙️ CORE\n"
                "/status — Agent status\n"
                "/publish — Publish newsletter\n"
                "/help — Basic help\n\n"
                "📈 ECONOMICS\n"
                "/economics — Weekly pipeline cost report"
            ),
            session_id="",
            intent="COMMANDS",
            metadata={},
        )

    # 2c-1. Economics report — run on demand, dry-run only
    if _msg_lower == "/economics":
        econ_response = _run_economics_report()
        return ChatResponse(
            response=econ_response,
            session_id="",
            intent="ECONOMICS_COMMAND",
            metadata={},
        )

    # 2c-2. Newsletter preview — set to preview status (visible on web, not distributed)
    if _msg_lower.startswith("/newsletter_preview"):
        try:
            draft = supabase.table("newsletters")\
                .select("id, edition_number")\
                .in_("status", ["draft", "pending"])\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()
            if not draft.data:
                preview_resp = "No draft newsletter found to preview."
            else:
                nl = draft.data[0]
                supabase.table("newsletters").update({"status": "preview"}).eq("id", nl["id"]).execute()
                edition = nl.get("edition_number", "?")
                preview_resp = (
                    f"📰 Newsletter #{edition} is now in preview mode.\n\n"
                    f"View it on the web before publishing.\n"
                    f"Send /newsletter_publish when ready to distribute."
                )
        except Exception as e:
            preview_resp = f"Preview failed: {e}"
        return ChatResponse(
            response=preview_resp,
            session_id="",
            intent="NEWSLETTER_COMMAND",
            metadata={},
        )

    # 2c. X Distribution commands — handle directly, skip intent router
    if _msg_lower.startswith("/x-"):
        x_response = handle_x_command(req.message)
        return ChatResponse(
            response=x_response,
            session_id="",
            intent="X_COMMAND",
            metadata={},
        )

    # 2d. Code Engine commands — handle directly, skip intent router
    _code_prefixes = ("/code", "/diff", "/code-diff", "/approve", "/code-approve", "/reject", "/code-reject", "/code-merge", "/followup", "/repos")
    if any(_msg_lower.startswith(p) for p in _code_prefixes):
        code_response = code_commands.handle_code_command(
            message=req.message,
            user_id=req.user_id,
        )
        return ChatResponse(
            response=code_response,
            session_id="",
            intent="CODE_COMMAND",
            metadata={},
        )

    # 2e. CTO commands — handle directly, skip intent router
    if _msg_lower.startswith("/cto"):
        cto_response = cto_commands.handle_cto_command(
            message=req.message,
            user_id=req.user_id,
        )
        return ChatResponse(
            response=cto_response,
            session_id="",
            intent="CTO_COMMAND",
            metadata={},
        )

    # 3. Resolve session (close stale, create new if needed)
    session = resolve_session(req.user_id)
    session_id = session["id"]

    # 4. Save user message
    save_message(session_id, "user", req.message)

    # 5. Load conversation history
    history = load_history(session_id)

    # 6. Corpus probe — fast pgvector search before routing
    probe_results = corpus_probe.probe(supabase, req.message)

    # 7. Get previous retrieval context (for follow-up detection)
    previous_retrieval_context = None
    if history:
        last_assistant = [m for m in reversed(history) if m["role"] == "assistant"]
        if last_assistant:
            # Load full message with retrieval_context
            prev_msg = (
                supabase.table("conversation_messages")
                .select("retrieval_context")
                .eq("session_id", session_id)
                .eq("role", "assistant")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if prev_msg.data and prev_msg.data[0].get("retrieval_context"):
                previous_retrieval_context = prev_msg.data[0]["retrieval_context"]

    # 8. Intent routing via DeepSeek + heuristic fallback
    route_result = intent_router.route(
        message=req.message,
        conversation_history=history,
        corpus_probe_results=probe_results,
        previous_retrieval_context=previous_retrieval_context,
    )
    intent = route_result["intent"]

    # 9. Execute the routed retrieval path
    context_blocks = []
    retrieved_chunks = []
    expanded_chunks = []
    structured_result = None
    web_results = []
    retrieval_start = time.time()

    if intent == "CORPUS_QUERY":
        results, ctx = execute_corpus_path(route_result, probe_results)
        if ctx:
            context_blocks.append(ctx)
        retrieved_chunks = [str(r.get("id", "")) for r in results if not r.get("expanded")]
        expanded_chunks = [str(r.get("id", "")) for r in results if r.get("expanded")]

    elif intent == "WEB_SEARCH":
        # Check web search rate limit
        ws_limited = check_web_search_limit(req.user_id, access_tier)
        if ws_limited or not web_search.is_available():
            logger.info(f"WEB_SEARCH: {'rate limited' if ws_limited else 'Tavily not available'} — falling back to corpus")
            results, ctx = execute_corpus_path(route_result, probe_results)
            if ctx:
                context_blocks.append(ctx)
            note = ws_limited or "Web search is not available. Results are from our intelligence corpus only."
            context_blocks.append(f"Note: {note}")
            retrieved_chunks = [str(r.get("id", "")) for r in results if not r.get("expanded")]
            expanded_chunks = [str(r.get("id", "")) for r in results if r.get("expanded")]
        else:
            search_query = route_result.get("search_query", req.message)
            ws_result = web_search.search(search_query)
            web_results = [{"url": r["url"], "title": r["title"]} for r in ws_result.get("results", [])]
            ws_ctx = web_search.format_web_results(ws_result)
            if ws_ctx:
                context_blocks.append(ws_ctx)
            # Include corpus context as bonus if probe had decent results
            if probe_results.get("top_score", 0) >= 0.55:
                results, ctx = execute_corpus_path(route_result, probe_results)
                if ctx:
                    context_blocks.append(ctx)
                retrieved_chunks = [str(r.get("id", "")) for r in results if not r.get("expanded")]
                expanded_chunks = [str(r.get("id", "")) for r in results if r.get("expanded")]
            increment_usage(req.user_id, messages=0, web_searches=1)

    elif intent == "HYBRID":
        # Check web search rate limit
        ws_limited = check_web_search_limit(req.user_id, access_tier)
        search_query = route_result.get("search_query", req.message)

        if ws_limited or not web_search.is_available():
            # Corpus only
            results, ctx = execute_corpus_path(route_result, probe_results)
            if ctx:
                context_blocks.append(ctx)
            retrieved_chunks = [str(r.get("id", "")) for r in results if not r.get("expanded")]
            expanded_chunks = [str(r.get("id", "")) for r in results if r.get("expanded")]
        else:
            # Run corpus + web in parallel
            corpus_future = asyncio.to_thread(execute_corpus_path, route_result, probe_results)
            web_future = asyncio.to_thread(web_search.search, search_query)
            (results, corpus_ctx), ws_result = await asyncio.gather(corpus_future, web_future)

            if corpus_ctx:
                context_blocks.append(corpus_ctx)
            ws_ctx = web_search.format_web_results(ws_result)
            if ws_ctx:
                context_blocks.append(ws_ctx)

            web_results = [{"url": r["url"], "title": r["title"]} for r in ws_result.get("results", [])]
            retrieved_chunks = [str(r.get("id", "")) for r in results if not r.get("expanded")]
            expanded_chunks = [str(r.get("id", "")) for r in results if r.get("expanded")]
            increment_usage(req.user_id, messages=0, web_searches=1)

    elif intent == "STRUCTURED_QUERY":
        sq_result, ctx = execute_structured_path(route_result)
        structured_result = sq_result
        if ctx:
            context_blocks.append(ctx)

    elif intent == "FOLLOW_UP":
        results, ctx = execute_followup_path(previous_retrieval_context, probe_results)
        if ctx:
            context_blocks.append(ctx)
        retrieved_chunks = [str(r.get("id", "")) for r in results if not r.get("expanded")]
        expanded_chunks = [str(r.get("id", "")) for r in results if r.get("expanded")]

    # DIRECT: no retrieval, context_blocks stays empty

    # Add citation instruction when we have retrieval context
    if context_blocks:
        context_blocks.append(CITATION_INSTRUCTION)

    retrieval_ms = int((time.time() - retrieval_start) * 1000)

    # 10. Context assembly + generate response
    system_prompt = load_system_prompt()
    system_prompt += f"\n\nToday's date is {date.today().isoformat()}."
    system_prompt += fetch_economics_block()
    response_text, generation_ms, output_tokens = generate_response(
        system_prompt, history[:-1], req.message,
        context_blocks=context_blocks if context_blocks else None,
    )

    # 11. Save assistant response with full retrieval context
    template_name = structured_result.get("template_name") if structured_result else None
    retrieval_context = {
        "intent": intent,
        "retrieved_chunks": retrieved_chunks,
        "expanded_chunks": expanded_chunks,
        "web_results": web_results,
        "structured_query": template_name,
        "similarity_scores": [r.get("similarity", 0) for r in probe_results.get("results", [])],
        "probe_top_score": probe_results["top_score"],
        "probe_latency_ms": probe_results["latency_ms"],
        "route_reasoning": route_result["reasoning"],
        "route_latency_ms": route_result["latency_ms"],
        "route_used_fallback": route_result["used_fallback"],
    }
    save_message(session_id, "assistant", response_text, retrieval_context=retrieval_context)

    # 12. Increment usage
    increment_usage(req.user_id)

    # 13. Log query with full observability
    elapsed_ms = int((time.time() - start) * 1000)
    # Best similarity from probe results
    sim_scores = [r.get("similarity", 0) for r in probe_results.get("results", [])]
    top_sim = max(sim_scores) if sim_scores else None
    log_query(
        req.user_id, session_id, req.message, intent, elapsed_ms,
        corpus_probe_top_score=probe_results["top_score"],
        retrieval_source=intent,
        top_similarity_score=top_sim,
        chunks_retrieved=len(retrieved_chunks),
        chunks_expanded=len(expanded_chunks),
        web_results_used=len(web_results),
        template_name=template_name,
        response_tokens=output_tokens,
        probe_latency_ms=probe_results["latency_ms"],
        router_latency_ms=route_result["latency_ms"],
        retrieval_latency_ms=retrieval_ms,
        generation_latency_ms=generation_ms,
    )

    return ChatResponse(
        response=response_text,
        session_id=session_id,
        intent=intent,
        metadata={
            "access_tier": access_tier,
            "probe_top_score": probe_results["top_score"],
            "probe_latency_ms": probe_results["latency_ms"],
            "route_latency_ms": route_result["latency_ms"],
            "route_reasoning": route_result["reasoning"],
            "route_used_fallback": route_result["used_fallback"],
            "chunks_retrieved": len(retrieved_chunks),
            "chunks_expanded": len(expanded_chunks),
            "web_results_count": len(web_results),
            "retrieval_latency_ms": retrieval_ms,
            "generation_latency_ms": generation_ms,
        },
    )


# ─── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Gato Brain on port {PORT}")
    init_clients()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
