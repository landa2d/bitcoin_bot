"""
Intent router — classifies incoming messages using DeepSeek V3 + corpus probe scores.

Provides:
- route(): classify a message into one of 6 intents
- Heuristic fallback if DeepSeek fails
"""

import json
import logging
import re
import time

import httpx

logger = logging.getLogger("gato-brain")

ALLOWED_INTENTS = {
    "CORPUS_QUERY",
    "WEB_SEARCH",
    "HYBRID",
    "DIRECT",
    "STRUCTURED_QUERY",
    "FOLLOW_UP",
}

ROUTER_PROMPT = """You are an intent router for an AI intelligence platform. Given the user's message,
conversation history, and corpus probe results, classify the intent.

CORPUS PROBE RESULTS (top 3 matches from our intelligence database):
{corpus_probe_json}

CONVERSATION HISTORY (last 3 messages):
{recent_history}

USER MESSAGE: {message}

PREVIOUS RETRIEVAL CONTEXT (if follow-up):
{previous_retrieval_ids}

Classify into one of:

1. CORPUS_QUERY — Corpus probe has strong results (similarity >= 0.80).
   User is asking about topics we've covered.

2. WEB_SEARCH — Corpus probe is weak (similarity < 0.55) AND user wants factual/current info.
   User wants live information not in our corpus.

3. HYBRID — Corpus has partial results (0.55-0.80) OR user wants our analysis
   validated/enriched with current data. Run both corpus deep retrieval and web search in parallel.

4. DIRECT — Chitchat, commands, or questions answerable from conversation context alone.
   Includes: greetings, "thanks", "summarize what we discussed", slash commands.

5. STRUCTURED_QUERY — User wants specific data points from structured tables.
   Select the appropriate query template.
   Available templates: trending_tools, confirmed_predictions, refuted_predictions,
   open_predictions, topic_stage, top_opportunities, problem_clusters,
   recent_spotlights, prediction_scorecard

6. FOLLOW_UP — User is referencing content from a previous response.
   Re-hydrate previous retrieval context and optionally supplement with new retrieval.

Return ONLY valid JSON with no markdown formatting:
{{
    "intent": "CORPUS_QUERY|WEB_SEARCH|HYBRID|DIRECT|STRUCTURED_QUERY|FOLLOW_UP",
    "search_query": "optimized query for retrieval (rewritten from user message)",
    "corpus_filters": {{"source_table": ["spotlight_history"], "date_from": "2025-02-01"}},
    "template_name": "trending_tools",
    "template_params": {{"limit": 10}},
    "rehydrate_ids": ["emb_id_1", "emb_id_2"],
    "reasoning": "brief explanation of routing decision"
}}"""


# Module-level DeepSeek client (set by init())
_deepseek_client: httpx.Client | None = None


def init(client: httpx.Client) -> None:
    """Set the shared DeepSeek httpx client."""
    global _deepseek_client
    _deepseek_client = client
    logger.info("Intent router DeepSeek client initialized")


def _build_prompt(
    message: str,
    conversation_history: list[dict],
    corpus_probe_results: dict,
    previous_retrieval_context: dict | None,
) -> str:
    """Build the router prompt with actual data."""
    # Format corpus probe results
    probe_json = json.dumps(corpus_probe_results.get("results", []), indent=2, default=str)

    # Last 3 messages from history
    recent = conversation_history[-3:] if conversation_history else []
    history_text = "\n".join(
        f"{m['role']}: {m['content'][:200]}" for m in recent
    ) or "(no history)"

    # Previous retrieval IDs
    prev_ids = "(none)"
    if previous_retrieval_context:
        chunks = previous_retrieval_context.get("retrieved_chunks", [])
        if chunks:
            prev_ids = json.dumps(chunks[:5])

    return ROUTER_PROMPT.format(
        corpus_probe_json=probe_json,
        recent_history=history_text,
        message=message,
        previous_retrieval_ids=prev_ids,
    )


def _heuristic_fallback(
    corpus_probe_results: dict,
    message: str,
    conversation_history: list[dict],
) -> dict:
    """Rule-based fallback when DeepSeek is unavailable or returns invalid JSON."""
    top_score = corpus_probe_results.get("top_score", 0.0)
    msg_lower = message.lower().strip()

    # Detect greetings / chitchat
    greetings = {"hi", "hello", "hey", "thanks", "thank you", "bye", "ok", "okay", "gm", "gn"}
    if msg_lower in greetings or len(msg_lower) < 5:
        return _make_result("DIRECT", message, "Heuristic: short/greeting message")

    # Detect follow-up patterns
    follow_up_patterns = [
        "tell me more", "more about that", "what do you mean",
        "explain that", "can you elaborate", "go deeper", "expand on",
    ]
    if any(p in msg_lower for p in follow_up_patterns):
        return _make_result("FOLLOW_UP", message, "Heuristic: follow-up pattern detected")

    # Detect structured query patterns
    structured_patterns = {
        "trending_tools": ["trending tools", "popular tools", "tool mentions", "what tools"],
        "confirmed_predictions": ["confirmed prediction", "predictions confirmed", "what predictions came true"],
        "refuted_predictions": ["refuted prediction", "wrong prediction", "predictions that failed"],
        "open_predictions": ["open prediction", "unresolved prediction", "pending prediction"],
        "prediction_scorecard": ["prediction accuracy", "prediction scorecard", "how accurate"],
        "top_opportunities": ["top opportunities", "best opportunities", "business opportunities"],
        "recent_spotlights": ["recent spotlight", "latest spotlight", "latest research"],
        "problem_clusters": ["problem cluster", "problem themes"],
    }
    for template, patterns in structured_patterns.items():
        if any(p in msg_lower for p in patterns):
            return _make_result(
                "STRUCTURED_QUERY", message,
                f"Heuristic: matched template '{template}'",
                template_name=template,
            )

    # Score-based routing
    if top_score >= 0.80:
        return _make_result("CORPUS_QUERY", message, f"Heuristic: high probe score ({top_score:.2f})")
    if top_score < 0.55:
        return _make_result("WEB_SEARCH", message, f"Heuristic: low probe score ({top_score:.2f})")
    return _make_result("HYBRID", message, f"Heuristic: moderate probe score ({top_score:.2f})")


def _make_result(
    intent: str,
    search_query: str,
    reasoning: str,
    template_name: str | None = None,
    template_params: dict | None = None,
    rehydrate_ids: list | None = None,
) -> dict:
    return {
        "intent": intent,
        "search_query": search_query,
        "corpus_filters": {},
        "template_name": template_name,
        "template_params": template_params or {},
        "rehydrate_ids": rehydrate_ids or [],
        "reasoning": reasoning,
    }


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences that DeepSeek sometimes wraps around JSON."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence (possibly with language tag)
        text = re.sub(r"^```\w*\n?", "", text)
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def route(
    message: str,
    conversation_history: list[dict],
    corpus_probe_results: dict,
    previous_retrieval_context: dict | None = None,
) -> dict:
    """
    Classify a user message into one of 6 intents.

    Returns:
        {
            "intent": str,
            "search_query": str,
            "corpus_filters": dict,
            "template_name": str | None,
            "template_params": dict,
            "rehydrate_ids": list,
            "reasoning": str,
            "latency_ms": int,
            "used_fallback": bool,
        }
    """
    t0 = time.time()

    if not _deepseek_client:
        logger.warning("Intent router: DeepSeek client not initialized, using heuristic")
        result = _heuristic_fallback(corpus_probe_results, message, conversation_history)
        result["latency_ms"] = int((time.time() - t0) * 1000)
        result["used_fallback"] = True
        return result

    prompt = _build_prompt(message, conversation_history, corpus_probe_results, previous_retrieval_context)

    try:
        response = _deepseek_client.post(
            "/chat/completions",
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are an intent classification engine. Return ONLY valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
                "max_tokens": 500,
            },
        )
        response.raise_for_status()
        data = response.json()
        raw_text = data["choices"][0]["message"]["content"].strip()

        # Parse JSON (handle code fences)
        cleaned = _strip_code_fences(raw_text)
        parsed = json.loads(cleaned)

        # Validate intent
        intent = parsed.get("intent", "").upper()
        if intent not in ALLOWED_INTENTS:
            logger.warning(f"Intent router: invalid intent '{intent}' from DeepSeek, falling back")
            result = _heuristic_fallback(corpus_probe_results, message, conversation_history)
            result["latency_ms"] = int((time.time() - t0) * 1000)
            result["used_fallback"] = True
            return result

        result = {
            "intent": intent,
            "search_query": parsed.get("search_query", message),
            "corpus_filters": parsed.get("corpus_filters", {}),
            "template_name": parsed.get("template_name"),
            "template_params": parsed.get("template_params", {}),
            "rehydrate_ids": parsed.get("rehydrate_ids", []),
            "reasoning": parsed.get("reasoning", ""),
            "latency_ms": int((time.time() - t0) * 1000),
            "used_fallback": False,
        }

        logger.info(f"Intent router: {intent} ({result['latency_ms']}ms) — {result['reasoning'][:80]}")
        return result

    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Intent router: failed to parse DeepSeek response: {e}")
        result = _heuristic_fallback(corpus_probe_results, message, conversation_history)
        result["latency_ms"] = int((time.time() - t0) * 1000)
        result["used_fallback"] = True
        return result
    except Exception as e:
        logger.warning(f"Intent router: DeepSeek call failed: {e}")
        result = _heuristic_fallback(corpus_probe_results, message, conversation_history)
        result["latency_ms"] = int((time.time() - t0) * 1000)
        result["used_fallback"] = True
        return result
