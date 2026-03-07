"""
Gato Brain — Conversational intelligence middleware for AgentPulse.

Sits between Gato's Telegram handler and the LLM.
Handles: session management, conversation memory, rate limiting, response generation.
"""

import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from contextlib import asynccontextmanager

import anthropic
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client

import asyncio
import subprocess
import threading

import corpus_probe
import intent_router
import query_templates
import web_search

# ─── Configuration ───────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
PORT = int(os.getenv("GATO_BRAIN_PORT", "8100"))
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
                      context_blocks: list[str] | None = None) -> str:
    """Generate a response using Claude, with optional retrieval context injected."""
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
        logger.info(f"Claude response in {elapsed}ms, {response.usage.input_tokens}+{response.usage.output_tokens} tokens")
        return text
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

def log_query(user_id: str, session_id: str, query: str, intent: str, response_ms: int) -> None:
    """Log query to query_log table."""
    try:
        supabase.table("query_log").insert({
            "user_id": user_id,
            "session_id": session_id,
            "user_query": query,
            "detected_intent": intent,
            "total_latency_ms": response_ms,
        }).execute()
    except Exception as e:
        logger.warning(f"Failed to log query: {e}")


# ─── Client initialization (sync, before uvicorn event loop) ─────────

def init_clients():
    """Initialize all API clients. Called from __main__ before uvicorn.run()."""
    global supabase, claude_client, deepseek_client

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
        raise RuntimeError("Supabase not configured")

    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set")
        raise RuntimeError("Anthropic API key not configured")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    logger.info("Supabase + Claude clients initialized")

    if OPENAI_API_KEY:
        corpus_probe.init(OPENAI_API_KEY)
    else:
        logger.warning("OPENAI_API_KEY not set — corpus probe disabled")

    if TAVILY_API_KEY:
        web_search.init(TAVILY_API_KEY)
    else:
        logger.warning("TAVILY_API_KEY not set — web search disabled")

    if DEEPSEEK_API_KEY:
        deepseek_client = httpx.Client(
            base_url=DEEPSEEK_BASE_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        intent_router.init(deepseek_client)
        logger.info("DeepSeek client initialized")
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


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Main chat endpoint — session management, rate limiting, response generation."""
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

    # 10. Context assembly + generate response
    system_prompt = load_system_prompt()
    response_text = generate_response(
        system_prompt, history[:-1], req.message,
        context_blocks=context_blocks if context_blocks else None,
    )

    # 11. Save assistant response with full retrieval context
    retrieval_context = {
        "intent": intent,
        "retrieved_chunks": retrieved_chunks,
        "expanded_chunks": expanded_chunks,
        "web_results": web_results,
        "structured_query": structured_result.get("template_name") if structured_result else None,
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

    # 13. Log query with full details
    elapsed_ms = int((time.time() - start) * 1000)
    log_query(req.user_id, session_id, req.message, intent, elapsed_ms)

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
        },
    )


# ─── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Gato Brain on port {PORT}")
    init_clients()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
