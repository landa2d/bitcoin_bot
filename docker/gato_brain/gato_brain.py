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

import corpus_probe

# ─── Configuration ───────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
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


def generate_response(system_prompt: str, history: list[dict], user_message: str) -> str:
    """Generate a response using Claude."""
    messages = []
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

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

    if DEEPSEEK_API_KEY:
        deepseek_client = httpx.Client(
            base_url=DEEPSEEK_BASE_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        logger.info("DeepSeek client initialized")
    else:
        logger.warning("DEEPSEEK_API_KEY not set — session summaries will be basic")


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

    # 7. Generate response (intent routing will be added in D2/D3)
    intent = "DIRECT"
    system_prompt = load_system_prompt()
    response_text = generate_response(system_prompt, history[:-1], req.message)

    # 8. Save assistant response with probe context
    retrieval_context = {
        "probe_top_score": probe_results["top_score"],
        "probe_results": probe_results["results"],
        "probe_latency_ms": probe_results["latency_ms"],
    }
    save_message(session_id, "assistant", response_text, retrieval_context=retrieval_context)

    # 9. Increment usage
    increment_usage(req.user_id)

    # 10. Log query
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
        },
    )


# ─── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Gato Brain on port {PORT}")
    init_clients()
    uvicorn.run(app, host="0.0.0.0", port=PORT)
