"""
Corpus probe — fast pgvector search on incoming messages.

Provides:
- probe(): fast top-3 lookup for routing decisions
- deep_corpus_retrieval(): full retrieval with one-hop graph expansion
"""

import logging
import time

from openai import OpenAI
from supabase import Client

logger = logging.getLogger("gato-brain")

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSIONS = 1536

# Module-level OpenAI client (set by init())
_openai_client: OpenAI | None = None


def init(api_key: str) -> None:
    """Initialize the cached OpenAI client."""
    global _openai_client
    _openai_client = OpenAI(api_key=api_key)
    logger.info("Corpus probe OpenAI client initialized")


def _embed(text: str) -> list[float]:
    """Embed a single text string."""
    resp = _openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[text],
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return resp.data[0].embedding


def probe(supabase: Client, message: str) -> dict:
    """
    Fast corpus probe — embed message and search top 3 results.

    Returns:
        {
            "top_score": float,
            "query_embedding": list[float],
            "results": [{"id", "source_table", "source_id", "similarity", "snippet"}, ...],
            "latency_ms": int,
        }
    """
    fallback = {"top_score": 0.0, "query_embedding": [], "results": [], "latency_ms": 0}

    if not _openai_client:
        logger.warning("Corpus probe: OpenAI client not initialized")
        return fallback

    t0 = time.time()
    try:
        embedding = _embed(message)

        resp = supabase.rpc("search_corpus", {
            "query_embedding": embedding,
            "match_count": 3,
        }).execute()

        rows = resp.data or []
        results = [
            {
                "id": str(r["id"]),
                "source_table": r["source_table"],
                "source_id": str(r["source_id"]),
                "similarity": r["similarity"],
                "snippet": (r.get("content_text") or "")[:200],
            }
            for r in rows
        ]

        top_score = results[0]["similarity"] if results else 0.0
        latency = int((time.time() - t0) * 1000)

        logger.info(f"Corpus probe: top_score={top_score:.4f}, {len(results)} results, {latency}ms")
        return {
            "top_score": top_score,
            "query_embedding": embedding,
            "results": results,
            "latency_ms": latency,
        }

    except Exception as e:
        latency = int((time.time() - t0) * 1000)
        logger.warning(f"Corpus probe failed ({latency}ms): {e}")
        return fallback


def deep_corpus_retrieval(
    supabase: Client,
    query_embedding: list[float],
    match_count: int = 10,
    source_filter: list[str] | None = None,
    date_from: str | None = None,
) -> list[dict]:
    """
    Deep retrieval with one-hop graph expansion via content_links.

    Returns list of result dicts with full content_text, metadata, etc.
    Expanded results are tagged with {"expanded": true, "link_type": "..."}.
    """
    t0 = time.time()

    # Build RPC params
    params: dict = {
        "query_embedding": query_embedding,
        "match_count": match_count,
    }
    if source_filter:
        params["source_filter"] = source_filter
    if date_from:
        params["date_from"] = date_from

    try:
        resp = supabase.rpc("search_corpus", params).execute()
        primary_results = resp.data or []
    except Exception as e:
        logger.warning(f"Deep retrieval failed: {e}")
        return []

    # One-hop graph expansion via content_links
    expanded = []
    seen_keys = {(r["source_table"], str(r["source_id"])) for r in primary_results}

    if primary_results:
        # Collect source pairs from primary results for link lookup
        for r in primary_results:
            try:
                # Find links where this content is the source
                links_resp = (
                    supabase.table("content_links")
                    .select("target_table, target_id, link_type")
                    .eq("source_table", r["source_table"])
                    .eq("source_id", r["source_id"])
                    .limit(5)
                    .execute()
                )
                links = links_resp.data or []

                # Also find links where this content is the target
                reverse_resp = (
                    supabase.table("content_links")
                    .select("source_table, source_id, link_type")
                    .eq("target_table", r["source_table"])
                    .eq("target_id", r["source_id"])
                    .limit(5)
                    .execute()
                )
                reverse_links = [
                    {"target_table": rl["source_table"], "target_id": rl["source_id"], "link_type": rl["link_type"]}
                    for rl in (reverse_resp.data or [])
                ]

                for link in links + reverse_links:
                    key = (link["target_table"], str(link["target_id"]))
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    # Fetch the linked content from embeddings
                    emb_resp = (
                        supabase.table("embeddings")
                        .select("id, source_table, source_id, content_text, metadata, edition_number")
                        .eq("source_table", link["target_table"])
                        .eq("source_id", link["target_id"])
                        .limit(1)
                        .execute()
                    )
                    if emb_resp.data:
                        row = emb_resp.data[0]
                        row["expanded"] = True
                        row["link_type"] = link["link_type"]
                        row["similarity"] = 0.0  # Not from vector search
                        expanded.append(row)

                    if len(expanded) >= 5:
                        break

            except Exception as e:
                logger.warning(f"Graph expansion failed for {r.get('source_table')}/{r.get('source_id')}: {e}")
                continue

            if len(expanded) >= 5:
                break

    all_results = primary_results + expanded
    latency = int((time.time() - t0) * 1000)
    logger.info(f"Deep retrieval: {len(primary_results)} primary + {len(expanded)} expanded, {latency}ms")
    return all_results
