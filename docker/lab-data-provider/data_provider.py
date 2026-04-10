"""
Lab Data Provider — Web research service for agent-to-agent transactions.

Accepts research requests, performs Tavily web search, optionally synthesizes
findings via DeepSeek (through the LLM proxy), and returns structured results.

Pricing: basic=50 sats, deep=150 sats (paid by the calling agent).
"""

import json
import logging
import os
import time

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from tavily import TavilyClient

# ─── Configuration ────────────────────────────────────────────────────────────

AGENT_NAME = os.getenv("AGENT_NAME", "lab_data-provider")
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "")
LLM_PROXY_URL = os.getenv("LLM_PROXY_URL", "http://llm-proxy:8200")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
PORT = int(os.getenv("DATA_PROVIDER_PORT", "8300"))

PRICING = {"basic": 50, "deep": 150}

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("data-provider")

# ─── Clients ──────────────────────────────────────────────────────────────────

tavily_client: TavilyClient | None = None
app = FastAPI(title="Lab Data Provider", version="0.1.0")


@app.on_event("startup")
def startup():
    global tavily_client
    if TAVILY_API_KEY:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        logger.info("Tavily client initialized")
    else:
        logger.warning("TAVILY_API_KEY not set — web search disabled")
    logger.info(f"Data Provider ready on port {PORT}")


# ─── Web search ──────────────────────────────────────────────────────────────

def tavily_search(topic: str, max_sources: int = 5) -> list[dict]:
    """Run Tavily search, return list of source dicts."""
    if not tavily_client:
        logger.warning("Tavily not available, returning empty results")
        return []

    try:
        t0 = time.time()
        response = tavily_client.search(
            query=topic,
            search_depth="advanced",
            max_results=max_sources,
            include_raw_content=False,
            include_answer=True,
        )
        latency = int((time.time() - t0) * 1000)

        sources = []
        for r in response.get("results", []):
            sources.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "excerpt": (r.get("content") or "")[:500],
            })

        logger.info(f"Tavily: {len(sources)} results for '{topic[:60]}' in {latency}ms")
        return sources

    except Exception as e:
        logger.error(f"Tavily search failed: {e}")
        return []


# ─── LLM synthesis ───────────────────────────────────────────────────────────

def synthesize_sources(topic: str, sources: list[dict]) -> str:
    """Call DeepSeek through the proxy to synthesize web research into a summary."""
    if not sources or not AGENT_API_KEY:
        return ""

    source_text = "\n".join(
        f"- {s['title']}: {s['excerpt'][:300]}" for s in sources
    )

    try:
        resp = httpx.post(
            f"{LLM_PROXY_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {AGENT_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a research analyst. Synthesize the following web search results "
                            "into a concise 2-3 paragraph summary. Focus on key findings, trends, "
                            "and notable developments. Be specific — cite sources by name."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Topic: {topic}\n\nWeb sources:\n{source_text}",
                    },
                ],
                "max_tokens": 800,
                "temperature": 0.3,
            },
            timeout=30,
        )

        if resp.status_code != 200:
            logger.warning(f"Synthesis LLM call failed: {resp.status_code}")
            return ""

        data = resp.json()
        synthesis = data["choices"][0]["message"]["content"]
        logger.info(f"Synthesis: {len(synthesis)} chars for '{topic[:40]}'")
        return synthesis

    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        return ""


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/research")
async def research(request: Request):
    """Perform web research on a topic and return structured results."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    topic = body.get("topic")
    if not topic:
        return JSONResponse(status_code=400, content={"error": "topic is required"})

    depth = body.get("depth", "basic")
    if depth not in PRICING:
        return JSONResponse(status_code=400, content={"error": f"depth must be one of: {list(PRICING.keys())}"})

    max_sources = min(body.get("max_sources", 5), 10)
    cost_sats = PRICING[depth]

    logger.info(f"Research request: topic='{topic[:60]}', depth={depth}, max_sources={max_sources}")

    # Perform web search
    sources = tavily_search(topic, max_sources)

    # Synthesize if deep mode
    synthesis = ""
    if depth == "deep" and sources:
        synthesis = synthesize_sources(topic, sources)

    return {
        "topic": topic,
        "sources": sources,
        "synthesis": synthesis,
        "source_count": len(sources),
        "cost_sats": cost_sats,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "agent": AGENT_NAME, "tavily": tavily_client is not None}


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
