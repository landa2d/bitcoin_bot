"""
LLM Proxy — Transparent proxy between agents and LLM providers.

Handles authentication, wallet reserve/settle, rate limiting, streaming,
and async logging. Agents send requests here instead of directly to providers.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
import uuid
from collections import Counter, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import bcrypt
import httpx
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

# ─── Configuration ────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
LLM_PROXY_PORT = int(os.getenv("LLM_PROXY_PORT", "8200"))
LLM_PROXY_ADMIN_KEY = os.getenv("LLM_PROXY_ADMIN_KEY", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()

LOGS_DIR = Path(os.getenv("OPENCLAW_DATA_DIR", "/home/openclaw/.openclaw")) / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "llm_proxy.log"),
    ],
)
logger = logging.getLogger("llm-proxy")

# ─── Model routing table ─────────────────────────────────────────────────────

MODEL_ROUTES: dict[str, dict] = {
    "deepseek-chat": {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
    },
    "gpt-4o": {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
    },
    "gpt-4o-mini": {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
    },
    "text-embedding-3-large": {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
    },
    "claude-sonnet-4-20250514": {
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com",
        "env_key": "ANTHROPIC_AGENT_KEY",
    },
}

# Estimated cost in sats per call (for reservation)
ESTIMATED_COST_SATS: dict[str, int] = {
    "deepseek-chat": 2,
    "gpt-4o-mini": 5,
    "gpt-4o": 50,
    "claude-sonnet-4-20250514": 80,
    "text-embedding-3-large": 1,
}

# Per-token USD pricing (input/output per 1M tokens)
TOKEN_PRICING_USD: dict[str, dict[str, float]] = {
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "text-embedding-3-large": {"input": 0.13, "output": 0.0},
}

# Rough sats-per-USD conversion (updated periodically, good enough for cost tracking)
SATS_PER_USD = 1000  # ~$100k/BTC

# Request size limits
MAX_CHAT_BODY = 1_048_576  # 1MB
MAX_EMBED_BODY = 524_288   # 512KB

# Timeouts per endpoint type
TIMEOUT_CHAT = 120.0
TIMEOUT_EMBED = 10.0
TIMEOUT_ANTHROPIC = 120.0

# ─── Global state ─────────────────────────────────────────────────────────────

supabase = None
http_client: httpx.AsyncClient | None = None
start_time: float = 0.0

# Agent registry cache: api_key_hash -> agent record
agent_cache: dict[str, dict] = {}
agent_cache_ts: float = 0.0
AGENT_CACHE_TTL = 30.0  # seconds

# Rate limiting: agent_name -> deque of request timestamps
rate_windows: dict[str, deque] = {}

# Async log queue — NO maxlen so records are never silently dropped
log_queue: deque[dict] = deque()
settle_retry_queue: deque[dict] = deque()
LOG_BATCH_SIZE = 50        # flush when this many records accumulate
LOG_FLUSH_INTERVAL = 5.0   # or every N seconds, whichever comes first
LOG_FALLBACK_FILE = LOGS_DIR / "transaction_overflow.jsonl"

# Wallet governance cache: agent_name -> wallet record
wallet_cache: dict[str, dict] = {}
wallet_cache_ts: dict[str, float] = {}
WALLET_CACHE_TTL = 15.0  # seconds

# Governance event dedup: prevent spamming the same event
_gov_event_sent: dict[str, float] = {}  # "agent:event_type" -> timestamp
GOV_EVENT_COOLDOWN = 300.0  # 5 minutes between duplicate events

# Metrics counters
metrics = {
    "requests_total": 0,
    "requests_by_endpoint": {"chat": 0, "embeddings": 0, "anthropic": 0},
    "errors_by_provider": {},
    "latencies_ms": deque(maxlen=1000),
    "wallet_ops": 0,
    "log_queue_depth": 0,
    "settle_failures": 0,
    "settle_retries_ok": 0,
}


# ─── Supabase helpers ─────────────────────────────────────────────────────────

def init_supabase():
    global supabase
    if SUPABASE_URL and SUPABASE_KEY:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized")
    else:
        logger.error("SUPABASE_URL / SUPABASE_SERVICE_KEY not set — proxy cannot function")


def _sb_rpc(fn_name: str, params: dict) -> Any:
    """Call a Supabase RPC function synchronously."""
    result = supabase.rpc(fn_name, params).execute()
    return result.data


def _sb_insert(table: str, record: dict):
    """Insert a record into a Supabase table."""
    supabase.table(table).insert(record).execute()


def _sb_update(table: str, data: dict, match: dict):
    """Update records matching conditions."""
    q = supabase.table(table).update(data)
    for k, v in match.items():
        q = q.eq(k, v)
    q.execute()


# ─── Agent auth ───────────────────────────────────────────────────────────────

def _refresh_agent_cache():
    """Load agent registry into memory cache."""
    global agent_cache, agent_cache_ts
    now = time.time()
    if now - agent_cache_ts < AGENT_CACHE_TTL:
        return
    try:
        result = supabase.table("agent_registry").select("*").eq("is_active", True).execute()
        new_cache = {}
        for row in result.data or []:
            new_cache[row["api_key_hash"]] = row
            if row.get("previous_key_hash") and row.get("previous_key_expires_at"):
                expires = datetime.fromisoformat(row["previous_key_expires_at"].replace("Z", "+00:00"))
                if expires > datetime.now(timezone.utc):
                    new_cache[row["previous_key_hash"]] = row
        agent_cache.update(new_cache)
        agent_cache_ts = now
        logger.debug(f"Agent cache refreshed: {len(new_cache)} entries")
    except Exception as e:
        logger.warning(f"Failed to refresh agent cache: {e}")


def authenticate_agent(api_key: str) -> dict | None:
    """Look up an agent by API key. Returns agent record or None."""
    _refresh_agent_cache()

    # Check each cached hash against the provided key
    for key_hash, agent in agent_cache.items():
        try:
            if bcrypt.checkpw(api_key.encode(), key_hash.encode()):
                # Update last_seen_at (fire-and-forget)
                try:
                    _sb_update(
                        "agent_registry",
                        {"last_seen_at": datetime.now(timezone.utc).isoformat()},
                        {"agent_name": agent["agent_name"]},
                    )
                except Exception:
                    pass
                return agent
        except Exception:
            continue
    return None


# ─── Rate limiting ────────────────────────────────────────────────────────────

def check_rate_limit(agent_name: str, rpm_limit: int | None) -> bool:
    """Returns True if the request is allowed, False if rate-limited."""
    if rpm_limit is None or rpm_limit <= 0:
        return True
    now = time.time()
    window = rate_windows.setdefault(agent_name, deque())
    # Purge entries older than 60s
    while window and window[0] < now - 60:
        window.popleft()
    if len(window) >= rpm_limit:
        return False
    window.append(now)
    return True


# ─── Governance ──────────────────────────────────────────────────────────────

def _get_wallet(agent_name: str) -> dict | None:
    """Get wallet record with caching."""
    now = time.time()
    if agent_name in wallet_cache and now - wallet_cache_ts.get(agent_name, 0) < WALLET_CACHE_TTL:
        return wallet_cache[agent_name]
    try:
        result = supabase.table("agent_wallets_v2").select("*").eq("agent_name", agent_name).execute()
        if result.data:
            wallet_cache[agent_name] = result.data[0]
            wallet_cache_ts[agent_name] = now
            return result.data[0]
    except Exception as e:
        logger.warning(f"Failed to fetch wallet for {agent_name}: {e}")
    return wallet_cache.get(agent_name)


def _emit_governance_event(agent_name: str, event_type: str, details: dict):
    """Log a governance event (with dedup cooldown)."""
    key = f"{agent_name}:{event_type}"
    now = time.time()
    if now - _gov_event_sent.get(key, 0) < GOV_EVENT_COOLDOWN:
        return  # already emitted recently
    _gov_event_sent[key] = now
    try:
        _sb_insert("governance_events", {
            "agent_name": agent_name,
            "event_type": event_type,
            "details": details,
        })
        logger.info(f"[GOVERNANCE] {event_type} for {agent_name}: {details}")
    except Exception as e:
        logger.warning(f"Failed to log governance event {event_type} for {agent_name}: {e}")


def _get_spending_window_total(agent_name: str, window: str) -> int:
    """Get total sats spent by an agent in the current spending window."""
    if window == "daily":
        interval = "1 day"
    elif window == "weekly":
        interval = "7 days"
    elif window == "monthly":
        interval = "30 days"
    else:
        return 0
    try:
        result = supabase.rpc("get_agent_window_spending", {
            "p_agent_name": agent_name,
            "p_interval": interval,
        }).execute()
        if result.data is not None:
            if isinstance(result.data, list) and result.data:
                return int(result.data[0].get("total", 0))
            elif isinstance(result.data, (int, float)):
                return int(result.data)
        return 0
    except Exception:
        # Fallback: query directly
        try:
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days={"daily": 1, "weekly": 7, "monthly": 30}.get(window, 1))
            result = (
                supabase.table("wallet_transactions")
                .select("amount_sats")
                .eq("agent_name", agent_name)
                .eq("transaction_type", "llm_call")
                .gte("created_at", cutoff.isoformat())
                .execute()
            )
            return sum(abs(r["amount_sats"]) for r in (result.data or []))
        except Exception as e2:
            logger.warning(f"Failed to get window spending for {agent_name}: {e2}")
            return 0


def check_governance(agent_name: str, model: str, balance_after: int) -> dict:
    """
    Run governance checks AFTER reserve_balance succeeds.
    Returns dict with 'action' key: 'allow', 'reject', or 'downgrade'.
    Governance events fire regardless of action.
    """
    wallet = _get_wallet(agent_name)
    if not wallet:
        return {"action": "allow"}

    total_deposited = wallet.get("total_deposited_sats", 0)

    # --- Balance threshold events ---
    if balance_after <= 0:
        _emit_governance_event(agent_name, "balance_exhausted", {
            "balance_sats": balance_after,
            "allow_negative": wallet.get("allow_negative", False),
        })
    elif total_deposited > 0 and balance_after < total_deposited * 0.2:
        _emit_governance_event(agent_name, "balance_low", {
            "balance_sats": balance_after,
            "threshold_sats": int(total_deposited * 0.2),
            "total_deposited_sats": total_deposited,
        })

    # --- Spending cap check ---
    cap_sats = wallet.get("spending_cap_sats")
    cap_window = wallet.get("spending_cap_window", "daily")
    if cap_sats and cap_sats > 0:
        window_total = _get_spending_window_total(agent_name, cap_window)
        if window_total >= cap_sats:
            _emit_governance_event(agent_name, "cap_hit", {
                "spending_cap_sats": cap_sats,
                "window": cap_window,
                "window_total_sats": window_total,
                "model": model,
            })
            # For internal agents (allow_negative), alert but don't reject
            if not wallet.get("allow_negative", False):
                return {"action": "reject", "reason": f"Spending cap exceeded ({window_total}/{cap_sats} sats in {cap_window} window)"}
            # Internal agents: log but allow through

    return {"action": "allow"}


# ─── Wallet operations ───────────────────────────────────────────────────────

def reserve_balance(agent_name: str, estimated_sats: int, allow_negative: bool) -> tuple[bool, int]:
    """Reserve balance atomically. Returns (success, current_balance)."""
    metrics["wallet_ops"] += 1
    try:
        result = _sb_rpc("reserve_agent_balance", {
            "p_agent_name": agent_name,
            "p_amount_sats": estimated_sats,
            "p_allow_negative": allow_negative,
        })
        if result and len(result) > 0:
            row = result[0]
            return row["success"], row["current_balance"]
        return False, 0
    except Exception as e:
        logger.error(f"Reserve balance failed for {agent_name}: {e}")
        # For internal agents, allow through on DB error
        if allow_negative:
            return True, 0
        return False, 0


def settle_balance(agent_name: str, reserved_sats: int, actual_sats: int):
    """Settle the difference between reserved and actual cost."""
    metrics["wallet_ops"] += 1
    try:
        _sb_rpc("settle_agent_balance", {
            "p_agent_name": agent_name,
            "p_reserved_sats": reserved_sats,
            "p_actual_sats": actual_sats,
        })
    except Exception as e:
        metrics["settle_failures"] += 1
        logger.error(
            "settle_balance FAILED for %s: reserved=%d, actual=%d, error=%s — queued for retry",
            agent_name, reserved_sats, actual_sats, e,
        )
        settle_retry_queue.append({
            "agent_name": agent_name,
            "reserved_sats": reserved_sats,
            "actual_sats": actual_sats,
            "attempts": 1,
        })


# ─── Cost calculation ─────────────────────────────────────────────────────────

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> tuple[int, int]:
    """Calculate actual cost in (sats, usd_cents) from token usage."""
    pricing = TOKEN_PRICING_USD.get(model)
    if not pricing:
        return ESTIMATED_COST_SATS.get(model, 5), 0

    input_cost_usd = (input_tokens / 1_000_000) * pricing["input"]
    output_cost_usd = (output_tokens / 1_000_000) * pricing["output"]
    total_usd = input_cost_usd + output_cost_usd
    usd_cents = round(total_usd * 100)
    sats = max(1, round(total_usd * SATS_PER_USD))
    return sats, usd_cents


# ─── Async logging ────────────────────────────────────────────────────────────

async def async_log_transaction(
    agent_name: str,
    model: str,
    amount_sats: int,
    amount_usd_cents: int,
    balance_after: int,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    provider: str,
    endpoint: str,
    request_id: str,
):
    """Enqueue a transaction record for batched write to wallet_transactions."""
    record = {
        "agent_name": agent_name,
        "transaction_type": "llm_call",
        "amount_sats": amount_sats,
        "amount_usd_cents": amount_usd_cents,
        "balance_after_sats": balance_after,
        "metadata": {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "provider": provider,
            "endpoint": endpoint,
            "request_id": request_id,
        },
    }
    log_queue.append(record)
    metrics["log_queue_depth"] = len(log_queue)
    # Trigger immediate flush if batch is full
    if len(log_queue) >= LOG_BATCH_SIZE:
        asyncio.create_task(_flush_batch())


def _write_fallback(records: list[dict]):
    """Append records to local JSONL file as a fallback when Supabase is down."""
    try:
        with open(LOG_FALLBACK_FILE, "a") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        logger.warning(f"Wrote {len(records)} records to fallback file {LOG_FALLBACK_FILE}")
    except Exception as e:
        logger.error(f"CRITICAL: fallback file write failed: {e} — {len(records)} records lost")


async def _flush_batch():
    """Flush queued records to Supabase in a single batch insert."""
    if not log_queue:
        return
    batch = []
    while log_queue and len(batch) < LOG_BATCH_SIZE:
        batch.append(log_queue.popleft())
    if not batch:
        return
    try:
        await asyncio.to_thread(_sb_batch_insert, "wallet_transactions", batch)
        logger.debug(f"Batch-logged {len(batch)} transactions")
    except Exception as e:
        logger.warning(f"Batch insert failed ({len(batch)} records): {e} — writing to fallback file")
        _write_fallback(batch)
    metrics["log_queue_depth"] = len(log_queue)


def _sb_batch_insert(table: str, records: list[dict]):
    """Insert multiple records into a Supabase table in one call."""
    supabase.table(table).insert(records).execute()


async def flush_log_queue():
    """Periodically flush queued log entries in batches."""
    while True:
        await asyncio.sleep(LOG_FLUSH_INTERVAL)
        while log_queue:
            await _flush_batch()


SETTLE_RETRY_INTERVAL = 30.0  # seconds between retry sweeps
SETTLE_MAX_ATTEMPTS = 5


async def flush_settle_retries():
    """Periodically retry failed settle_balance calls."""
    while True:
        await asyncio.sleep(SETTLE_RETRY_INTERVAL)
        if not settle_retry_queue:
            continue
        pending = len(settle_retry_queue)
        logger.info("Retrying %d failed settle operations", pending)
        remaining: list[dict] = []
        while settle_retry_queue:
            item = settle_retry_queue.popleft()
            try:
                await asyncio.to_thread(
                    _sb_rpc,
                    "settle_agent_balance",
                    {
                        "p_agent_name": item["agent_name"],
                        "p_reserved_sats": item["reserved_sats"],
                        "p_actual_sats": item["actual_sats"],
                    },
                )
                metrics["settle_retries_ok"] += 1
                logger.info(
                    "Settle retry OK for %s: actual=%d sats",
                    item["agent_name"], item["actual_sats"],
                )
            except Exception as e:
                item["attempts"] += 1
                if item["attempts"] < SETTLE_MAX_ATTEMPTS:
                    remaining.append(item)
                    logger.warning(
                        "Settle retry %d/%d failed for %s: %s",
                        item["attempts"], SETTLE_MAX_ATTEMPTS, item["agent_name"], e,
                    )
                else:
                    logger.error(
                        "Settle ABANDONED for %s after %d attempts: reserved=%d, actual=%d — wallet drift of %d sats",
                        item["agent_name"], SETTLE_MAX_ATTEMPTS,
                        item["reserved_sats"], item["actual_sats"], item["actual_sats"],
                    )
        for item in remaining:
            settle_retry_queue.append(item)


async def drain_log_queue():
    """Drain all remaining records on shutdown — write to DB or fallback file."""
    if not log_queue:
        return
    remaining = len(log_queue)
    logger.info(f"Draining {remaining} queued log entries before shutdown...")
    while log_queue:
        batch = []
        while log_queue and len(batch) < LOG_BATCH_SIZE:
            batch.append(log_queue.popleft())
        try:
            _sb_batch_insert("wallet_transactions", batch)
        except Exception:
            _write_fallback(batch)
    logger.info(f"Drain complete: {remaining} entries processed")


# ─── Streaming helpers ────────────────────────────────────────────────────────

def _extract_usage_openai(response_json: dict) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from an OpenAI response."""
    usage = response_json.get("usage", {})
    return usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


def _extract_usage_anthropic(response_json: dict) -> tuple[int, int]:
    """Extract (input_tokens, output_tokens) from an Anthropic response."""
    usage = response_json.get("usage", {})
    return usage.get("input_tokens", 0), usage.get("output_tokens", 0)


async def _stream_openai_response(
    upstream_response: httpx.Response,
) -> tuple:
    """
    Stream SSE chunks from an OpenAI-compatible provider.
    Returns an async iterator of chunks plus extracted usage.
    We capture usage from the final chunk that contains it.
    """
    input_tokens = 0
    output_tokens = 0

    async def generate():
        nonlocal input_tokens, output_tokens
        async for line in upstream_response.aiter_lines():
            if line.startswith("data: "):
                data = line[6:]
                if data.strip() == "[DONE]":
                    yield f"data: [DONE]\n\n"
                    break
                try:
                    chunk = json.loads(data)
                    usage = chunk.get("usage")
                    if usage:
                        input_tokens = usage.get("prompt_tokens", input_tokens)
                        output_tokens = usage.get("completion_tokens", output_tokens)
                except json.JSONDecodeError:
                    pass
                yield f"{line}\n\n"
            elif line.strip():
                yield f"{line}\n\n"

    class AsyncIteratorWrapper:
        def __init__(self):
            self._gen = generate()

        def __aiter__(self):
            return self._gen.__aiter__()

    wrapper = AsyncIteratorWrapper()
    return wrapper, lambda: (input_tokens, output_tokens)


async def _stream_anthropic_response(
    upstream_response: httpx.Response,
) -> tuple:
    """Stream SSE events from Anthropic and capture usage from message_delta."""
    input_tokens = 0
    output_tokens = 0

    async def generate():
        nonlocal input_tokens, output_tokens
        async for line in upstream_response.aiter_lines():
            if line.startswith("data: "):
                data = line[6:]
                try:
                    event = json.loads(data)
                    event_type = event.get("type", "")
                    if event_type == "message_start":
                        usage = event.get("message", {}).get("usage", {})
                        input_tokens = usage.get("input_tokens", 0)
                    elif event_type == "message_delta":
                        usage = event.get("usage", {})
                        output_tokens = usage.get("output_tokens", 0)
                except json.JSONDecodeError:
                    pass
            yield f"{line}\n\n" if not line.endswith("\n") else f"{line}\n"

    class AsyncIteratorWrapper:
        def __init__(self):
            self._gen = generate()

        def __aiter__(self):
            return self._gen.__aiter__()

    wrapper = AsyncIteratorWrapper()
    return wrapper, lambda: (input_tokens, output_tokens)


# ─── Core proxy logic ─────────────────────────────────────────────────────────

def _extract_api_key(request: Request) -> str | None:
    """Extract API key from Authorization header or x-api-key."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.headers.get("x-api-key")


def _get_provider_key(env_key: str) -> str | None:
    """Get the actual provider API key from environment."""
    return os.getenv(env_key)


async def proxy_openai_compatible(
    request: Request,
    endpoint_type: str,  # "chat" or "embeddings"
) -> Response:
    """Handle OpenAI-compatible requests (chat completions + embeddings)."""
    request_id = str(uuid.uuid4())[:8]
    req_start = time.time()

    # Size limit check
    content_length = int(request.headers.get("content-length", 0))
    max_size = MAX_CHAT_BODY if endpoint_type == "chat" else MAX_EMBED_BODY
    if content_length > max_size:
        return JSONResponse(
            status_code=413,
            content={"error": {"message": f"Request body too large. Max {max_size} bytes.", "type": "proxy_error"}},
        )

    # Auth
    api_key = _extract_api_key(request)
    if not api_key:
        return JSONResponse(status_code=401, content={"error": {"message": "Missing API key", "type": "auth_error"}})

    agent = authenticate_agent(api_key)
    if not agent:
        return JSONResponse(status_code=401, content={"error": {"message": "Invalid API key", "type": "auth_error"}})

    agent_name = agent["agent_name"]

    # Rate limit
    if not check_rate_limit(agent_name, agent.get("rate_limit_rpm")):
        return JSONResponse(
            status_code=429,
            content={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
        )

    # Parse body to get model
    body_bytes = await request.body()
    try:
        body = json.loads(body_bytes)
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"error": {"message": "Invalid JSON body", "type": "invalid_request"}})

    model = body.get("model", "")
    route = MODEL_ROUTES.get(model)
    if not route:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": f"Unknown model: {model}. Available: {list(MODEL_ROUTES.keys())}", "type": "invalid_request"}},
        )

    # Check allowed models
    allowed = agent.get("allowed_models") or []
    if allowed and model not in allowed:
        return JSONResponse(
            status_code=403,
            content={"error": {"message": f"Model {model} not allowed for agent {agent_name}", "type": "permission_error"}},
        )

    provider_key = _get_provider_key(route["env_key"])
    if not provider_key:
        return JSONResponse(
            status_code=502,
            content={"error": {"message": f"Provider key not configured for {route['provider']}", "type": "proxy_error"}},
        )

    # Reserve balance
    estimated_sats = ESTIMATED_COST_SATS.get(model, 5)
    allow_negative = agent.get("access_tier") == "internal"
    success, balance = reserve_balance(agent_name, estimated_sats, allow_negative)
    if not success:
        return JSONResponse(
            status_code=402,
            content={"error": {"message": f"Insufficient balance ({balance} sats)", "type": "balance_error"}},
        )

    # Governance checks (spending caps, balance thresholds)
    gov = check_governance(agent_name, model, balance - estimated_sats)
    if gov["action"] == "reject":
        settle_balance(agent_name, estimated_sats, 0)  # refund the reservation
        return JSONResponse(
            status_code=429,
            content={"error": {"message": gov.get("reason", "Governance limit reached"), "type": "governance_error"}},
        )

    # Check if streaming
    is_streaming = body.get("stream", False) and endpoint_type == "chat"

    # Inject stream_options for usage tracking if streaming with OpenAI-compatible
    if is_streaming and route["provider"] in ("openai", "deepseek"):
        body["stream_options"] = {"include_usage": True}

    # Build upstream request
    if endpoint_type == "chat":
        upstream_url = f"{route['base_url']}/chat/completions"
        timeout = TIMEOUT_CHAT
    else:
        upstream_url = f"{route['base_url']}/embeddings"
        timeout = TIMEOUT_EMBED

    headers = {
        "Authorization": f"Bearer {provider_key}",
        "Content-Type": "application/json",
    }

    metrics["requests_total"] += 1
    metrics["requests_by_endpoint"][endpoint_type] += 1

    try:
        if is_streaming:
            upstream_resp = await http_client.send(
                http_client.build_request(
                    "POST", upstream_url,
                    headers=headers,
                    content=json.dumps(body).encode(),
                ),
                stream=True,
                timeout=timeout,  # type: ignore[arg-type]
            )
            if upstream_resp.status_code != 200:
                body_text = await upstream_resp.aread()
                settle_balance(agent_name, estimated_sats, 0)  # refund
                metrics["errors_by_provider"][route["provider"]] = metrics["errors_by_provider"].get(route["provider"], 0) + 1
                return Response(content=body_text, status_code=upstream_resp.status_code, media_type="application/json")

            stream_iter, get_usage = await _stream_openai_response(upstream_resp)

            async def streaming_body():
                async for chunk in stream_iter:
                    yield chunk
                # After stream ends, settle and log
                inp, out = get_usage()
                actual_sats, actual_usd_cents = calculate_cost(model, inp, out)
                settle_balance(agent_name, estimated_sats, actual_sats)
                latency_ms = int((time.time() - req_start) * 1000)
                metrics["latencies_ms"].append(latency_ms)
                asyncio.create_task(async_log_transaction(
                    agent_name, model, actual_sats, actual_usd_cents,
                    balance - estimated_sats + (estimated_sats - actual_sats),
                    inp, out, latency_ms, route["provider"], endpoint_type, request_id,
                ))

            return StreamingResponse(
                streaming_body(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Proxy-Request-Id": request_id,
                    "X-Proxy-Agent": agent_name,
                },
            )

        else:
            # Non-streaming
            upstream_resp = await http_client.post(
                upstream_url,
                headers=headers,
                content=json.dumps(body).encode(),
                timeout=timeout,
            )

            latency_ms = int((time.time() - req_start) * 1000)
            metrics["latencies_ms"].append(latency_ms)

            if upstream_resp.status_code != 200:
                settle_balance(agent_name, estimated_sats, 0)  # refund
                metrics["errors_by_provider"][route["provider"]] = metrics["errors_by_provider"].get(route["provider"], 0) + 1
                return Response(
                    content=upstream_resp.content,
                    status_code=upstream_resp.status_code,
                    media_type="application/json",
                )

            resp_json = upstream_resp.json()
            input_tokens, output_tokens = _extract_usage_openai(resp_json)
            actual_sats, actual_usd_cents = calculate_cost(model, input_tokens, output_tokens)
            settle_balance(agent_name, estimated_sats, actual_sats)

            # Async log
            asyncio.create_task(async_log_transaction(
                agent_name, model, actual_sats, actual_usd_cents,
                balance - estimated_sats + (estimated_sats - actual_sats),
                input_tokens, output_tokens, latency_ms,
                route["provider"], endpoint_type, request_id,
            ))

            return Response(
                content=upstream_resp.content,
                status_code=200,
                media_type="application/json",
                headers={
                    "X-Proxy-Request-Id": request_id,
                    "X-Proxy-Agent": agent_name,
                },
            )

    except httpx.TimeoutException:
        settle_balance(agent_name, estimated_sats, 0)
        metrics["errors_by_provider"][route["provider"]] = metrics["errors_by_provider"].get(route["provider"], 0) + 1
        return JSONResponse(status_code=504, content={"error": {"message": "Upstream provider timeout", "type": "proxy_error"}})
    except httpx.HTTPError as e:
        settle_balance(agent_name, estimated_sats, 0)
        metrics["errors_by_provider"][route["provider"]] = metrics["errors_by_provider"].get(route["provider"], 0) + 1
        logger.error(f"HTTP error proxying to {route['provider']}: {e}")
        return JSONResponse(status_code=502, content={"error": {"message": "Upstream provider error", "type": "proxy_error"}})


async def proxy_anthropic(request: Request) -> Response:
    """Handle Anthropic Messages API requests."""
    request_id = str(uuid.uuid4())[:8]
    req_start = time.time()

    # Size limit (same as chat)
    content_length = int(request.headers.get("content-length", 0))
    if content_length > MAX_CHAT_BODY:
        return JSONResponse(
            status_code=413,
            content={"error": {"message": f"Request body too large. Max {MAX_CHAT_BODY} bytes.", "type": "proxy_error"}},
        )

    # Auth — Anthropic uses x-api-key header
    api_key = _extract_api_key(request)
    if not api_key:
        return JSONResponse(status_code=401, content={"error": {"message": "Missing API key", "type": "auth_error"}})

    agent = authenticate_agent(api_key)
    if not agent:
        return JSONResponse(status_code=401, content={"error": {"message": "Invalid API key", "type": "auth_error"}})

    agent_name = agent["agent_name"]

    if not check_rate_limit(agent_name, agent.get("rate_limit_rpm")):
        return JSONResponse(status_code=429, content={"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}})

    body_bytes = await request.body()
    try:
        body = json.loads(body_bytes)
    except json.JSONDecodeError:
        return JSONResponse(status_code=400, content={"error": {"message": "Invalid JSON body", "type": "invalid_request"}})

    model = body.get("model", "claude-sonnet-4-20250514")
    route = MODEL_ROUTES.get(model)
    if not route or route["provider"] != "anthropic":
        return JSONResponse(
            status_code=400,
            content={"error": {"message": f"Unknown or non-Anthropic model: {model}", "type": "invalid_request"}},
        )

    allowed = agent.get("allowed_models") or []
    if allowed and model not in allowed:
        return JSONResponse(
            status_code=403,
            content={"error": {"message": f"Model {model} not allowed for agent {agent_name}", "type": "permission_error"}},
        )

    provider_key = _get_provider_key(route["env_key"])
    if not provider_key:
        return JSONResponse(
            status_code=502,
            content={"error": {"message": "Anthropic key not configured", "type": "proxy_error"}},
        )

    estimated_sats = ESTIMATED_COST_SATS.get(model, 80)
    allow_negative = agent.get("access_tier") == "internal"
    success, balance = reserve_balance(agent_name, estimated_sats, allow_negative)
    if not success:
        return JSONResponse(
            status_code=402,
            content={"error": {"message": f"Insufficient balance ({balance} sats)", "type": "balance_error"}},
        )

    # Governance checks
    gov = check_governance(agent_name, model, balance - estimated_sats)
    if gov["action"] == "reject":
        settle_balance(agent_name, estimated_sats, 0)
        return JSONResponse(
            status_code=429,
            content={"error": {"message": gov.get("reason", "Governance limit reached"), "type": "governance_error"}},
        )

    is_streaming = body.get("stream", False)

    # Build upstream headers — Anthropic uses x-api-key + anthropic-version
    upstream_url = f"{route['base_url']}/v1/messages"
    headers = {
        "x-api-key": provider_key,
        "content-type": "application/json",
        "anthropic-version": request.headers.get("anthropic-version", "2023-06-01"),
    }
    # Pass through anthropic-beta if present
    if "anthropic-beta" in request.headers:
        headers["anthropic-beta"] = request.headers["anthropic-beta"]

    metrics["requests_total"] += 1
    metrics["requests_by_endpoint"]["anthropic"] += 1

    try:
        if is_streaming:
            upstream_resp = await http_client.send(
                http_client.build_request(
                    "POST", upstream_url,
                    headers=headers,
                    content=json.dumps(body).encode(),
                ),
                stream=True,
                timeout=TIMEOUT_ANTHROPIC,  # type: ignore[arg-type]
            )

            if upstream_resp.status_code != 200:
                body_text = await upstream_resp.aread()
                settle_balance(agent_name, estimated_sats, 0)
                metrics["errors_by_provider"]["anthropic"] = metrics["errors_by_provider"].get("anthropic", 0) + 1
                return Response(content=body_text, status_code=upstream_resp.status_code, media_type="application/json")

            stream_iter, get_usage = await _stream_anthropic_response(upstream_resp)

            async def streaming_body():
                async for chunk in stream_iter:
                    yield chunk
                inp, out = get_usage()
                actual_sats, actual_usd_cents = calculate_cost(model, inp, out)
                settle_balance(agent_name, estimated_sats, actual_sats)
                latency_ms = int((time.time() - req_start) * 1000)
                metrics["latencies_ms"].append(latency_ms)
                asyncio.create_task(async_log_transaction(
                    agent_name, model, actual_sats, actual_usd_cents,
                    balance - estimated_sats + (estimated_sats - actual_sats),
                    inp, out, latency_ms, "anthropic", "anthropic", request_id,
                ))

            return StreamingResponse(
                streaming_body(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Proxy-Request-Id": request_id,
                    "X-Proxy-Agent": agent_name,
                },
            )

        else:
            upstream_resp = await http_client.post(
                upstream_url,
                headers=headers,
                content=json.dumps(body).encode(),
                timeout=TIMEOUT_ANTHROPIC,
            )

            latency_ms = int((time.time() - req_start) * 1000)
            metrics["latencies_ms"].append(latency_ms)

            if upstream_resp.status_code != 200:
                settle_balance(agent_name, estimated_sats, 0)
                metrics["errors_by_provider"]["anthropic"] = metrics["errors_by_provider"].get("anthropic", 0) + 1
                return Response(
                    content=upstream_resp.content,
                    status_code=upstream_resp.status_code,
                    media_type="application/json",
                )

            resp_json = upstream_resp.json()
            input_tokens, output_tokens = _extract_usage_anthropic(resp_json)
            actual_sats, actual_usd_cents = calculate_cost(model, input_tokens, output_tokens)
            settle_balance(agent_name, estimated_sats, actual_sats)

            asyncio.create_task(async_log_transaction(
                agent_name, model, actual_sats, actual_usd_cents,
                balance - estimated_sats + (estimated_sats - actual_sats),
                input_tokens, output_tokens, latency_ms,
                "anthropic", "anthropic", request_id,
            ))

            return Response(
                content=upstream_resp.content,
                status_code=200,
                media_type="application/json",
                headers={
                    "X-Proxy-Request-Id": request_id,
                    "X-Proxy-Agent": agent_name,
                },
            )

    except httpx.TimeoutException:
        settle_balance(agent_name, estimated_sats, 0)
        metrics["errors_by_provider"]["anthropic"] = metrics["errors_by_provider"].get("anthropic", 0) + 1
        return JSONResponse(status_code=504, content={"error": {"message": "Upstream provider timeout", "type": "proxy_error"}})
    except httpx.HTTPError as e:
        settle_balance(agent_name, estimated_sats, 0)
        metrics["errors_by_provider"]["anthropic"] = metrics["errors_by_provider"].get("anthropic", 0) + 1
        logger.error(f"HTTP error proxying to Anthropic: {e}")
        return JSONResponse(status_code=502, content={"error": {"message": "Upstream provider error", "type": "proxy_error"}})


# ─── FastAPI app ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, start_time
    start_time = time.time()

    init_supabase()

    http_client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        follow_redirects=True,
    )

    # Start log queue flusher and settle retry loop
    flush_task = asyncio.create_task(flush_log_queue())
    settle_task = asyncio.create_task(flush_settle_retries())

    logger.info(f"LLM Proxy ready on port {LLM_PROXY_PORT}")
    yield

    flush_task.cancel()
    settle_task.cancel()
    await drain_log_queue()
    await http_client.aclose()
    logger.info("LLM Proxy shutting down")


app = FastAPI(title="AgentPulse LLM Proxy", version="0.1.0", lifespan=lifespan)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    return await proxy_openai_compatible(request, "chat")


@app.post("/v1/embeddings")
async def embeddings(request: Request):
    return await proxy_openai_compatible(request, "embeddings")


@app.post("/anthropic/v1/messages")
async def anthropic_messages(request: Request):
    return await proxy_anthropic(request)


@app.post("/v1/messages")
async def anthropic_messages_compat(request: Request):
    """Backward-compat route for agents using /v1/messages directly."""
    return await proxy_anthropic(request)


@app.get("/v1/proxy/health")
async def health():
    return {"status": "ok", "uptime_seconds": round(time.time() - start_time, 1)}


@app.get("/v1/proxy/metrics")
async def proxy_metrics(request: Request):
    # Require admin key
    admin_key = _extract_api_key(request)
    if not LLM_PROXY_ADMIN_KEY or admin_key != LLM_PROXY_ADMIN_KEY:
        return JSONResponse(status_code=401, content={"error": "Admin key required"})

    latencies = sorted(metrics["latencies_ms"])
    n = len(latencies)

    def percentile(p):
        if not latencies:
            return 0
        idx = int(n * p / 100)
        return latencies[min(idx, n - 1)]

    return {
        "requests_total": metrics["requests_total"],
        "requests_by_endpoint": dict(metrics["requests_by_endpoint"]),
        "errors_by_provider": dict(metrics["errors_by_provider"]),
        "latency_ms": {
            "p50": percentile(50),
            "p95": percentile(95),
            "p99": percentile(99),
        },
        "wallet_ops": metrics["wallet_ops"],
        "log_queue_depth": len(log_queue),
        "settle_failures": metrics["settle_failures"],
        "settle_retries_ok": metrics["settle_retries_ok"],
        "settle_retry_queue": len(settle_retry_queue),
        "uptime_seconds": round(time.time() - start_time, 1),
    }


# ─── Wallet summary endpoint ─────────────────────────────────────────────────

_PERIOD_RE = re.compile(r"^(\d+)d$")


def _parse_period(period: str | None, from_param: str | None, to_param: str | None):
    """Return (start, end, label) or raise ValueError."""
    now = datetime.now(timezone.utc)
    if from_param and to_param:
        try:
            start = datetime.fromisoformat(from_param).replace(tzinfo=timezone.utc)
            end = datetime.fromisoformat(to_param).replace(tzinfo=timezone.utc)
        except ValueError:
            raise ValueError("Invalid date format for from/to — use ISO 8601 (e.g. 2026-03-20)")
        if end <= start:
            raise ValueError("'to' must be after 'from'")
        label = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
        return start, end, label
    p = period or "7d"
    m = _PERIOD_RE.match(p)
    if not m or int(m.group(1)) not in (1, 7, 30):
        raise ValueError(f"Invalid period '{p}'. Use 1d, 7d, 30d, or from=/to= query params.")
    days = int(m.group(1))
    return now - timedelta(days=days), now, p


def _wallet_summary_sync(agent_name: str, start, end, period_label: str) -> dict:
    """Run all Supabase queries synchronously (called via to_thread)."""
    # Wallet info
    wallet_result = supabase.table("agent_wallets_v2").select("*").eq("agent_name", agent_name).execute()
    if not wallet_result.data:
        return None  # agent doesn't exist

    wallet = wallet_result.data[0]

    # Compute previous period
    duration = end - start
    prev_start = start - duration
    prev_end = start

    # Current period transactions
    cur_txs = (
        supabase.table("wallet_transactions")
        .select("amount_sats, metadata, created_at")
        .eq("agent_name", agent_name)
        .gte("created_at", start.isoformat())
        .lt("created_at", end.isoformat())
        .execute()
    ).data or []

    # Previous period transactions
    prev_txs = (
        supabase.table("wallet_transactions")
        .select("amount_sats")
        .eq("agent_name", agent_name)
        .gte("created_at", prev_start.isoformat())
        .lt("created_at", prev_end.isoformat())
        .execute()
    ).data or []

    # Governance events in period
    gov_result = (
        supabase.table("governance_events")
        .select("event_type")
        .eq("agent_name", agent_name)
        .gte("created_at", start.isoformat())
        .lt("created_at", end.isoformat())
        .execute()
    ).data or []

    # Aggregate current period
    spent_sats = 0
    models_used = Counter()
    task_types = Counter()
    for tx in cur_txs:
        spent_sats += abs(tx.get("amount_sats") or 0)
        meta = tx.get("metadata") or {}
        models_used[meta.get("model", "unknown")] += 1
        tt = meta.get("task_type")
        if tt:
            task_types[tt] += 1

    calls = len(cur_txs)
    avg_cost = round(spent_sats / calls) if calls else 0

    # Previous period total
    prev_spent = sum(abs(tx.get("amount_sats") or 0) for tx in prev_txs)
    if prev_spent > 0:
        trend_pct = ((spent_sats - prev_spent) / prev_spent) * 100
        trend_str = f"{trend_pct:+.0f}%"
    elif spent_sats > 0:
        trend_str = "+100%"
    else:
        trend_str = "0%"

    # Budget utilization — current spending window
    cap_sats = wallet.get("spending_cap_sats")
    cap_window = wallet.get("spending_cap_window")
    utilization = None
    if cap_sats and cap_sats > 0:
        window_spent = _get_spending_window_total(agent_name, cap_window or "daily")
        utilization = round((window_spent / cap_sats) * 100, 1)

    # Governance event counts
    gov_total = len(gov_result)
    cap_hits = sum(1 for e in gov_result if e["event_type"] == "cap_hit")

    # Estimated USD cents from wallet
    # Use the usd_cents columns if available, else estimate
    balance_usd_cents = wallet.get("balance_usd_cents") or 0
    spent_usd_cents = wallet.get("total_spent_usd_cents") or 0

    result = {
        "agent": agent_name,
        "period": period_label,
        "balance_sats": wallet["balance_sats"],
        "balance_usd_cents": balance_usd_cents,
        "spent_sats": spent_sats,
        "spent_usd_cents": round(spent_sats * (100 / SATS_PER_USD)),  # convert sats to usd cents
        "calls": calls,
        "avg_cost_per_call_sats": avg_cost,
        "models_used": dict(models_used.most_common()),
        "budget_utilization_pct": utilization,
        "spending_cap_sats": cap_sats,
        "spending_cap_window": cap_window,
        "cap_hits_in_period": cap_hits,
        "governance_events_in_period": gov_total,
        "trend_vs_previous_period": trend_str,
    }

    if task_types:
        result["top_task_types"] = dict(task_types.most_common(10))

    return result


@app.get("/v1/proxy/wallet/{agent_name}/summary")
async def wallet_summary(agent_name: str, request: Request):
    api_key = _extract_api_key(request)
    if not api_key:
        return JSONResponse(status_code=401, content={"error": {"message": "Missing API key", "type": "auth_error"}})

    # Admin key can view any agent
    is_admin = LLM_PROXY_ADMIN_KEY and api_key == LLM_PROXY_ADMIN_KEY
    if not is_admin:
        agent = authenticate_agent(api_key)
        if not agent:
            return JSONResponse(status_code=401, content={"error": {"message": "Invalid API key", "type": "auth_error"}})
        if agent["agent_name"] != agent_name:
            return JSONResponse(
                status_code=403,
                content={"error": {"message": f"API key belongs to '{agent['agent_name']}', not '{agent_name}'", "type": "permission_error"}},
            )

    # Parse period
    params = request.query_params
    try:
        start, end, period_label = _parse_period(
            params.get("period"), params.get("from"), params.get("to"),
        )
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": {"message": str(e), "type": "invalid_request"}})

    # Run queries off the event loop
    try:
        result = await asyncio.to_thread(_wallet_summary_sync, agent_name, start, end, period_label)
    except Exception as e:
        logger.error(f"Wallet summary query failed for {agent_name}: {e}")
        return JSONResponse(status_code=500, content={"error": {"message": "Internal error querying wallet data", "type": "proxy_error"}})

    if result is None:
        return JSONResponse(status_code=404, content={"error": {"message": f"Agent '{agent_name}' not found", "type": "not_found"}})

    return result


# ─── Agent-to-agent payment endpoint ─────────────────────────────────────────

@app.post("/v1/proxy/pay")
async def agent_pay(request: Request):
    """Transfer sats between two agent wallets atomically."""
    api_key = _extract_api_key(request)
    if not api_key:
        return JSONResponse(status_code=401, content={"error": {"message": "Missing API key", "type": "auth_error"}})

    # Admin key can initiate payments on behalf of any agent
    is_admin = LLM_PROXY_ADMIN_KEY and api_key == LLM_PROXY_ADMIN_KEY
    if not is_admin:
        agent = authenticate_agent(api_key)
        if not agent:
            return JSONResponse(status_code=401, content={"error": {"message": "Invalid API key", "type": "auth_error"}})

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": {"message": "Invalid JSON body", "type": "invalid_request"}})

    from_agent = body.get("from_agent")
    to_agent = body.get("to_agent")
    amount_sats = body.get("amount_sats")
    reason = body.get("reason")
    reference_id = body.get("reference_id")

    if not from_agent or not to_agent or not amount_sats:
        return JSONResponse(status_code=400, content={"error": {"message": "from_agent, to_agent, and amount_sats are required", "type": "invalid_request"}})

    if not is_admin and agent["agent_name"] != from_agent:
        return JSONResponse(
            status_code=403,
            content={"error": {"message": f"API key belongs to '{agent['agent_name']}', not '{from_agent}'", "type": "permission_error"}},
        )

    if amount_sats <= 0:
        return JSONResponse(status_code=400, content={"error": {"message": "amount_sats must be positive", "type": "invalid_request"}})

    if from_agent == to_agent:
        return JSONResponse(status_code=400, content={"error": {"message": "Cannot pay yourself", "type": "invalid_request"}})

    try:
        result = await asyncio.to_thread(
            _sb_rpc, "transfer_between_agents", {
                "p_from_agent": from_agent,
                "p_to_agent": to_agent,
                "p_amount_sats": amount_sats,
                "p_reason": reason,
                "p_reference_id": reference_id,
            }
        )
        if isinstance(result, list) and result:
            result = result[0]
        if not result or not result.get("success"):
            error = result.get("error", "transfer failed") if result else "no result"
            logger.warning(f"[PAY] Transfer failed {from_agent} → {to_agent}: {error}")
            return JSONResponse(status_code=402, content={"error": {"message": str(error), "type": "payment_error"}})

        logger.info(f"[PAY] {from_agent} → {to_agent}: {amount_sats} sats (reason={reason})")
        return result

    except Exception as e:
        logger.error(f"[PAY] Transfer error {from_agent} → {to_agent}: {e}")
        return JSONResponse(status_code=500, content={"error": {"message": "Internal payment error", "type": "proxy_error"}})


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=LLM_PROXY_PORT,
        log_level=LOG_LEVEL.lower(),
    )
