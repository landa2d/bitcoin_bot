"""
Web search via Tavily — live information retrieval for WEB_SEARCH and HYBRID intents.

Provides:
- search(): run a Tavily web search and return structured results
- format_web_results(): format results into a context block for Claude
"""

import logging
import time

from tavily import TavilyClient

logger = logging.getLogger("gato-brain")

# Module-level Tavily client (set by init())
_tavily_client: TavilyClient | None = None


def init(api_key: str) -> None:
    """Initialize the cached Tavily client."""
    global _tavily_client
    _tavily_client = TavilyClient(api_key=api_key)
    logger.info("Tavily web search client initialized")


def is_available() -> bool:
    """Check if web search is initialized."""
    return _tavily_client is not None


def search(query: str, max_results: int = 5) -> dict:
    """
    Run a Tavily web search.

    Returns:
        {
            "results": [{"title", "url", "content", "relevance_score"}, ...],
            "answer": str | None,
            "latency_ms": int,
            "error": str | None,
        }
    """
    fallback = {"results": [], "answer": None, "latency_ms": 0, "error": None}

    if not _tavily_client:
        fallback["error"] = "Tavily client not initialized"
        return fallback

    t0 = time.time()
    try:
        response = _tavily_client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_raw_content=False,
            include_answer=True,
        )

        results = []
        for r in response.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "relevance_score": r.get("score", 0.0),
            })

        latency = int((time.time() - t0) * 1000)
        answer = response.get("answer")

        logger.info(f"Tavily search: {len(results)} results, {latency}ms, query='{query[:60]}'")
        return {
            "results": results,
            "answer": answer,
            "latency_ms": latency,
            "error": None,
        }

    except Exception as e:
        latency = int((time.time() - t0) * 1000)
        logger.warning(f"Tavily search failed ({latency}ms): {e}")
        fallback["latency_ms"] = latency
        fallback["error"] = str(e)
        return fallback


def format_web_results(search_result: dict) -> str:
    """Format Tavily results into a context block for Claude."""
    results = search_result.get("results", [])
    if not results:
        return ""

    lines = ["--- WEB SEARCH RESULTS ---"]

    answer = search_result.get("answer")
    if answer:
        lines.append(f"Summary: {answer}")
        lines.append("")

    for i, r in enumerate(results, 1):
        title = r.get("title", "Untitled")
        url = r.get("url", "")
        content = (r.get("content") or "")[:300]
        score = r.get("relevance_score", 0)
        lines.append(f"{i}. [{title}] — {url} — Relevance: {score:.2f}")
        lines.append(f"   {content}")

    return "\n".join(lines)
