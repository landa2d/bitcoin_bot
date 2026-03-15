# AgentPulse — Conversational Intelligence Layer (v2)

## Plan: RAG + Memory + Web Search for Gato

### The Problem

Gato delivers intelligence briefings on Telegram but is stateless — no conversation memory, no access to the underlying corpus, no ability to search the web. Follow-up questions hit a wall. The goal is to turn Gato from a broadcast endpoint into an interactive intelligence interface.

---

## Architecture Overview

Four capabilities layered on top of the existing pipeline. The key architectural change from the original design: **retrieval happens before routing, not after.** The intent router receives corpus probe results and makes informed decisions rather than guessing blind.

```
User Question (Telegram)
        │
        ▼
┌─────────────────────────┐
│    Session Manager       │  ← Conversation memory (Supabase)
│  (last N messages +      │
│   retrieval metadata)    │  ← Stores what context was used per response
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│    Corpus Probe          │  ← Fast pgvector lookup, top 3 results + scores
│    (~50ms, always runs)  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│    Intent Router         │  ← Now sees: message + history + corpus probe scores
│    (DeepSeek V3)         │  ← Informed routing, not blind classification
└────────┬────────────────┘
         │
    ┌────┴──────┬───────────────┬──────────────┐
    ▼           ▼               ▼              ▼
┌────────┐ ┌─────────┐  ┌──────────┐  ┌─────────────┐
│Corpus  │ │  Web    │  │  Direct  │  │ Structured  │
│Deep    │ │ Search  │  │ Response │  │ Query       │
│Retriev.│ │(Tavily) │  │ (no RAG) │  │ (templates) │
│+expand │ │         │  │          │  │             │
└───┬────┘ └────┬────┘  └────┬─────┘  └──────┬──────┘
    │           │             │               │
    └─────┬─────┘             │               │
          ▼                   │               │
┌─────────────────────┐       │               │
│  Context Assembly    │◄──────┴───────────────┘
│  + LLM Generation    │
│  (Claude)            │
└────────┬────────────┘
         │
         ▼
   Telegram Response
   (+ save to session with retrieval metadata)
   (+ log to query_log)
```

### How "Retrieve-Then-Route" Works

Every incoming message triggers a lightweight corpus probe — a fast pgvector search returning only the top 3 results with similarity scores. This probe costs ~50ms and tells the router whether the corpus has relevant content before any routing decision is made.

The router then sees:

```json
{
    "user_message": "is agent interop still a thing?",
    "conversation_history": ["...last 3 messages..."],
    "corpus_probe": {
        "top_score": 0.87,
        "results": [
            {"source": "spotlight_history", "similarity": 0.87, "snippet": "Agent interop protocols..."},
            {"source": "topic_evolution", "similarity": 0.74, "snippet": "..."},
            {"source": "newsletter", "similarity": 0.68, "snippet": "..."}
        ]
    }
}
```

Routing rules become score-aware:
- **top_score >= 0.80** → Corpus has strong context. Route CORPUS unless temporal signals override.
- **top_score 0.55–0.80** → Corpus has partial context. Default to HYBRID (corpus + web in parallel).
- **top_score < 0.55** → Corpus is weak. Route WEB_SEARCH or DIRECT depending on query type.
- **STRUCTURED** and **DIRECT** intents override score-based routing when pattern-matched (commands, chitchat, explicit data requests).

This eliminates the most common failure mode of the original design: the router blindly choosing CORPUS_QUERY when the corpus has nothing relevant, producing hallucinated answers grounded on weak context.

---

## Component 1: Conversation Memory

### Schema

```sql
CREATE TABLE conversation_sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL,             -- Telegram user ID
    started_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    summary TEXT                        -- LLM-generated one-liner for older sessions
);

CREATE TABLE conversation_messages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id UUID REFERENCES conversation_sessions(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    retrieval_context JSONB DEFAULT '{}'::jsonb
    -- Stores what was used to generate this response:
    -- {
    --   "retrieved_chunks": ["emb_id_1", "emb_id_2"],
    --   "web_results": [{"url": "...", "title": "..."}],
    --   "intent": "HYBRID",
    --   "similarity_scores": [0.89, 0.84, 0.72],
    --   "structured_query": "trending_tools"
    -- }
);

CREATE INDEX idx_conv_messages_session ON conversation_messages(session_id, created_at);
CREATE INDEX idx_conv_sessions_user ON conversation_sessions(user_id, last_active_at DESC);
```

### Session Windowing Logic

- Messages within the last **60 minutes** of each other belong to the same session
- If gap > 60 min, close the old session and open a new one
- Inject the **last 10 messages** from the active session as conversation history
- For older sessions: store a one-line LLM-generated summary in `conversation_sessions.summary` so the agent can reference "earlier today you asked about X" without carrying full history

### Follow-Up Context Re-Hydration

When a user sends a follow-up ("tell me more about that second point", "expand on the MCP thing"), the system checks whether the user is referencing previous context before running a new retrieval:

1. Load the previous assistant message's `retrieval_context`
2. If the follow-up references prior content (detected by the router), re-fetch those specific chunks by embedding ID (exact lookup, no vector search needed)
3. Include re-hydrated chunks alongside any new retrieval results in the context window

This makes multi-turn deep-dives actually work — the LLM can expand on previous answers because it has the same underlying evidence, not just its own prior output.

### Why Not Just Use OpenClaw's Existing Memory?

OpenClaw has MEMORY.md but it's a static file, not conversational context. The file-based approach doesn't scale to multi-user, doesn't support session windowing, and can't carry per-conversation state. The Supabase approach integrates with the rest of the pipeline and supports the multi-user future.

---

## Component 2: Corpus RAG (pgvector)

### What to Embed

Not everything is worth embedding. Prioritize by information density and query relevance:

| Table | Embed? | Rationale |
|-------|--------|-----------|
| `spotlight_history` | **Yes — Priority 1** | Richest content: thesis, evidence, counter-arguments, predictions. These are the deep-dives users will most want to explore. |
| `newsletters` | **Yes — Priority 2** | `content_markdown` gives full edition context. Users will ask "what did last week's newsletter say about X?" |
| `problems` | **Yes — Priority 3** | `description` + `keywords` + `signal_phrases` — compact, high-signal chunks. |
| `opportunities` | **Yes — Priority 3** | `title` + `proposed_solution` + `pitch_brief` — actionable intelligence. |
| `topic_evolution` | **Yes — Priority 3** | `thesis` + `current_stage` — temporal context for "is X growing or declining?" |
| `source_posts` | **Selective** | Only embed posts with `source_tier` >= threshold (institutional sources). 1,448 rows is manageable but 20K moltbook_posts is not — and raw scrapes are noisy. |
| `moltbook_posts` | **No** | Too noisy, too voluminous. The structured analysis layer already distills these. If a user needs raw source, the RAG can retrieve the structured analysis which links back. |
| `tool_mentions` / `tool_stats` | **No** | Better served by structured query templates (see Component 4). Gato already has `/toolradar`. |
| `predictions` | **Yes** | Small table, high value. Users will ask "what predictions have you made about X?" |

### Embedding Schema

```sql
-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Unified embeddings table with source polymorphism
CREATE TABLE embeddings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    source_table TEXT NOT NULL,          -- 'spotlight_history', 'newsletters', etc.
    source_id UUID NOT NULL,             -- FK to source row (not enforced, for flexibility)
    chunk_index INTEGER DEFAULT 0,       -- For long content split into chunks
    content_text TEXT NOT NULL,           -- The actual text that was embedded
    embedding VECTOR(3072) NOT NULL,     -- text-embedding-3-large dimensions
    metadata JSONB DEFAULT '{}'::jsonb,  -- source_tier, date, topic, section_name, etc.
    created_at TIMESTAMPTZ DEFAULT NOW(),
    edition_date DATE,                   -- For temporal filtering ("last 3 weeks")
    edition_number INTEGER               -- For deterministic tier-based filtering
);

CREATE INDEX idx_embeddings_vector ON embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX idx_embeddings_source ON embeddings(source_table, source_id);
CREATE INDEX idx_embeddings_date ON embeddings(edition_date DESC);
CREATE INDEX idx_embeddings_edition ON embeddings(edition_number DESC);
```

### Why text-embedding-3-large Instead of Small

The cost difference is negligible at this volume (~$0.40/month vs ~$0.20/month). The corpus is domain-specific — AI agents, agent economy, tooling, crypto-adjacent terminology — and `text-embedding-3-large` (3072 dimensions) performs meaningfully better on specialized vocabulary than the small variant. "MCP interop" and "agent wallet satoshi ledger" aren't phrases the small model was optimized for. At this price delta, optimizing for embedding cost over retrieval quality is the wrong tradeoff.

### Chunking Strategy

- **Spotlight history**: Split `full_text` at ~500 tokens per chunk, overlapping 50 tokens. Keep `thesis` and `prediction` as standalone chunks (they're high-signal, often queried directly).
- **Newsletters**: Split `content_markdown` by section headers (Big Insight, Spotlight, Signals, Predictions, etc.). Each section becomes 1-2 chunks. Tag metadata with `section_name` and `edition_number`.
- **Problems / Opportunities / Predictions**: Small enough to embed as single chunks. Concatenate key fields: e.g., for problems → `"{description}. Keywords: {keywords}. Signal phrases: {signal_phrases}"`.
- **Topic Evolution**: Embed `thesis` + `current_stage` as a single chunk per row.
- **Source Posts** (selective): Embed `title + body` for high-tier posts only.

### Content Links (Cross-Document Relationships)

Vanilla vector search retrieves chunks independently, but the real intelligence in this corpus is the *temporal arc* — how a thesis evolved over weeks, which predictions were confirmed, what evidence accumulated. Without cross-document linking, the RAG retrieves isolated fragments and misses the narrative thread.

```sql
CREATE TABLE content_links (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    source_table TEXT NOT NULL,
    source_id UUID NOT NULL,
    target_table TEXT NOT NULL,
    target_id UUID NOT NULL,
    link_type TEXT NOT NULL CHECK (link_type IN (
        'updates',       -- spotlight updates a previous spotlight's thesis
        'supports',      -- evidence supports a prediction or thesis
        'contradicts',   -- new evidence contradicts previous analysis
        'predicts',      -- spotlight/newsletter makes a prediction (→ predictions table)
        'confirms',      -- evidence confirms a prediction
        'refutes',       -- evidence refutes a prediction
        'derived_from'   -- opportunity derived from problem cluster
    )),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_content_links_source ON content_links(source_table, source_id);
CREATE INDEX idx_content_links_target ON content_links(target_table, target_id);
```

**How it's populated:** During the existing pipeline — when the Research Agent writes a spotlight that references a previous prediction, log the link. When a prediction gets confirmed/refuted, link it to the evidence. The analyst agent can also generate links during its cross_signals work. This is pipeline metadata, not a new agent.

**How it's used at retrieval time:** After the initial pgvector search returns top chunks, do a one-hop graph expansion:

```sql
-- Given initial retrieved chunk IDs, expand via content links
SELECT DISTINCT e.*
FROM content_links cl
JOIN embeddings e ON (
    (e.source_table = cl.target_table AND e.source_id = cl.target_id)
    OR (e.source_table = cl.source_table AND e.source_id = cl.source_id)
)
WHERE
    (cl.source_table = ANY($source_tables) AND cl.source_id = ANY($source_ids))
    OR (cl.target_table = ANY($source_tables) AND cl.target_id = ANY($source_ids));
```

This turns "what's our thesis on MCP?" from a single-chunk answer into a narrative: the original thesis, the subsequent update, the prediction it generated, and whether that prediction was confirmed. The generation LLM receives the full arc.

### Embedding Pipeline

Add an embedding step to the existing pipeline, triggered after each agent completes its work:

```
Processor finishes → embed new problems, opportunities
Analyst finishes   → embed new topic_evolution + generate content_links
Research finishes   → embed new spotlight_history, predictions + generate content_links
Newsletter finishes → embed new newsletter sections (tagged with edition_number)
```

Implementation: A Python script (`embed_pipeline.py`) that:
1. Queries each target table for rows without a corresponding entry in `embeddings`
2. Chunks the content
3. Calls the embedding API (OpenAI `text-embedding-3-large` — $0.13/1M tokens, ~$0.40/month at current volume)
4. Inserts into the `embeddings` table with `edition_number` derived from the latest newsletter
5. Generates `content_links` entries where relationships are detectable (e.g., spotlight references a prediction by ID, topic_evolution updates a previous stage)
6. Runs as a cron job or triggered post-pipeline

### Retrieval Function

```sql
CREATE OR REPLACE FUNCTION search_corpus(
    query_embedding VECTOR(3072),
    match_count INTEGER DEFAULT 10,
    date_from DATE DEFAULT NULL,
    source_filter TEXT[] DEFAULT NULL,
    min_edition INTEGER DEFAULT NULL    -- For free-tier filtering
)
RETURNS TABLE (
    id UUID,
    source_table TEXT,
    source_id UUID,
    content_text TEXT,
    metadata JSONB,
    edition_number INTEGER,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.source_table,
        e.source_id,
        e.content_text,
        e.metadata,
        e.edition_number,
        1 - (e.embedding <=> query_embedding) AS similarity
    FROM embeddings e
    WHERE
        (date_from IS NULL OR e.edition_date >= date_from)
        AND (source_filter IS NULL OR e.source_table = ANY(source_filter))
        AND (min_edition IS NULL OR e.edition_number >= min_edition)
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;
```

### Retrieval Quality Evaluation Harness

Before exposing RAG to users (especially multi-user), retrieval quality must be measurable. Create a test suite of 20-30 queries with expected results:

```json
[
    {
        "query": "what's our thesis on MCP adoption?",
        "expected_source_table": "spotlight_history",
        "expected_keywords": ["MCP", "protocol", "adoption"],
        "min_acceptable_similarity": 0.75
    },
    {
        "query": "which agent frameworks are declining?",
        "expected_source_table": "topic_evolution",
        "expected_stage": "declining",
        "min_acceptable_similarity": 0.70
    },
    {
        "query": "what predictions have been confirmed?",
        "expected_source_table": "predictions",
        "expected_status": "confirmed",
        "min_acceptable_similarity": 0.70
    }
]
```

Implementation: A Python script (`eval_retrieval.py`) that:
1. Embeds each test query
2. Runs `search_corpus()` and captures top results
3. Checks whether expected source table / keywords / metadata appear in top-K results
4. Outputs a recall@K score and per-query diagnostics
5. Run after any change to chunking strategy, embedding model, or retrieval parameters

This prevents tuning blind. Without it, the only signal that retrieval quality degraded is a user complaint.

---

## Component 3: Web Search (Tavily)

### Why Tavily

- **Built for agents**: Returns clean, structured JSON with extracted content — no HTML parsing needed
- **Search + Extract in one call**: Can return page content alongside results, saving a second fetch step
- **Relevance scoring**: Each result comes with a score, making it easy to filter before injecting into context
- **Affordable**: 1,000 free searches/month on their basic plan, $0.01/search after
- **Context-window friendly**: Results come pre-chunked and summarized, unlike raw Google results via SerpAPI which need heavy post-processing

### Integration Pattern

Tavily becomes a tool available to the orchestrator, invoked when the intent router calls for WEB_SEARCH or HYBRID:

```python
from tavily import TavilyClient

def web_search(query: str, max_results: int = 5) -> list[dict]:
    client = TavilyClient(api_key=TAVILY_API_KEY)
    response = client.search(
        query=query,
        search_depth="advanced",
        max_results=max_results,
        include_raw_content=False,
        include_answer=True
    )
    return response["results"]
```

### When Web Search Fires

Determined by the intent router using corpus probe scores:
- **Corpus probe top_score < 0.55** and query isn't chitchat/command → WEB_SEARCH
- **Corpus probe top_score 0.55–0.80** and temporal signals present → HYBRID (parallel corpus + web)
- **Query explicitly asks to search**: "look up," "search for," "what's happening with" → WEB_SEARCH regardless of corpus score
- **HYBRID mode**: Corpus and web search run in parallel. The generation LLM receives both and decides how to weight them.

---

## Component 4: Intent Router

This is the decision layer that sits between the corpus probe and the retrieval systems. Implemented as a lightweight LLM call (DeepSeek V3 to keep costs minimal).

### Why LLM Routing Instead of Regex/Heuristics

Intent classification is genuinely ambiguous — "is agent interop still a thing?" could be corpus, web, or hybrid. A fast LLM call (~200ms with DeepSeek V3) handles edge cases that regex can't, and keeps the routing logic updatable via prompt changes rather than code changes.

### Router Prompt

```
You are an intent router for an AI intelligence platform. Given the user's message,
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
   Available templates: {template_names}

6. FOLLOW_UP — User is referencing content from a previous response.
   Re-hydrate previous retrieval context and optionally supplement with new retrieval.

Return JSON:
{
    "intent": "CORPUS_QUERY|WEB_SEARCH|HYBRID|DIRECT|STRUCTURED_QUERY|FOLLOW_UP",
    "search_query": "optimized query for retrieval (rewritten from user message)",
    "corpus_filters": {"source_table": ["spotlight_history"], "date_from": "2025-02-01"},
    "template_name": "trending_tools",
    "template_params": {"limit": 10},
    "rehydrate_ids": ["emb_id_1", "emb_id_2"],
    "reasoning": "brief explanation of routing decision"
}
```

### Routing Logic

```
CORPUS_QUERY    → Deep corpus retrieval (top 10) + one-hop graph expansion → context assembly → Claude
WEB_SEARCH      → Tavily search → context assembly → Claude
HYBRID          → Corpus retrieval + Tavily search (parallel) → merge context → Claude
DIRECT          → Conversation history only → Claude
STRUCTURED      → Execute query template → format results → Claude (optional)
FOLLOW_UP       → Re-hydrate previous chunks by ID + optional new retrieval → context assembly → Claude
```

---

## Component 5: Structured Query Templates

Instead of generating SQL dynamically (a known hazard: incorrect JOINs, wrong columns, injection risk), pre-define parameterized query templates for known structured data requests.

```python
QUERY_TEMPLATES = {
    "trending_tools": {
        "description": "Tools with most mentions in the last 7 days",
        "sql": """
            SELECT tool_name, mentions_7d, avg_sentiment, sentiment_trend
            FROM tool_stats
            ORDER BY mentions_7d DESC
            LIMIT %(limit)s
        """,
        "default_params": {"limit": 10}
    },
    "confirmed_predictions": {
        "description": "Predictions that have been confirmed",
        "sql": """
            SELECT prediction_text, status, created_at
            FROM predictions
            WHERE status = 'confirmed'
            ORDER BY created_at DESC
        """,
        "default_params": {}
    },
    "refuted_predictions": {
        "description": "Predictions that have been refuted",
        "sql": """
            SELECT prediction_text, status, created_at
            FROM predictions
            WHERE status = 'refuted'
            ORDER BY created_at DESC
        """,
        "default_params": {}
    },
    "open_predictions": {
        "description": "Predictions still unresolved",
        "sql": """
            SELECT prediction_text, created_at
            FROM predictions
            WHERE status = 'open'
            ORDER BY created_at DESC
        """,
        "default_params": {}
    },
    "topic_stage": {
        "description": "Current lifecycle stage of a topic",
        "sql": """
            SELECT topic, current_stage, thesis
            FROM topic_evolution
            WHERE topic ILIKE %(topic_pattern)s
            ORDER BY created_at DESC
        """,
        "default_params": {"topic_pattern": "%%"}
    },
    "top_opportunities": {
        "description": "Highest confidence business opportunities",
        "sql": """
            SELECT title, proposed_solution, business_model, confidence_score
            FROM opportunities
            ORDER BY confidence_score DESC
            LIMIT %(limit)s
        """,
        "default_params": {"limit": 5}
    },
    "problem_clusters": {
        "description": "Problem themes by opportunity score",
        "sql": """
            SELECT theme, opportunity_score, market_validation
            FROM problem_clusters
            ORDER BY opportunity_score DESC
            LIMIT %(limit)s
        """,
        "default_params": {"limit": 10}
    },
    "recent_spotlights": {
        "description": "Recent research deep-dives",
        "sql": """
            SELECT thesis, prediction, created_at
            FROM spotlight_history
            ORDER BY created_at DESC
            LIMIT %(limit)s
        """,
        "default_params": {"limit": 5}
    },
    "prediction_scorecard": {
        "description": "Overall prediction accuracy stats",
        "sql": """
            SELECT
                COUNT(*) FILTER (WHERE status = 'confirmed') AS confirmed,
                COUNT(*) FILTER (WHERE status = 'refuted') AS refuted,
                COUNT(*) FILTER (WHERE status = 'open') AS open,
                COUNT(*) AS total,
                ROUND(
                    COUNT(*) FILTER (WHERE status = 'confirmed')::numeric /
                    NULLIF(COUNT(*) FILTER (WHERE status IN ('confirmed', 'refuted')), 0) * 100,
                    1
                ) AS accuracy_pct
            FROM predictions
        """,
        "default_params": {}
    }
}
```

The router selects the template name and extracts parameters. Execution uses parameterized queries (no SQL injection). Results are formatted as markdown tables and optionally narrated by Claude for natural-language presentation.

**Fallback:** If a user asks a structured question that doesn't match any template, fall back to CORPUS_QUERY. Novel structured queries can be added as new templates over time based on query_log analysis.

---

## Component 6: Context Assembly & Generation

### Context Window Construction

The final LLM call (routed to Claude for editorial quality) receives a structured context:

```
[System Prompt — from SOUL.md / operator-context.md]

[Conversation History — last 10 messages from session]

[Retrieved Context — from RAG and/or web search]
---
CORPUS INTELLIGENCE (from AgentPulse database):
Source: spotlight_history (2025-03-01) | Edition #34 | Similarity: 0.89
"MCP protocol adoption is accelerating among mid-tier agent frameworks..."

Source: newsletter #34 — Signals section | Similarity: 0.84
"Three new agent-to-agent payment protocols announced this week..."

LINKED CONTEXT (related content via content_links):
Source: predictions (2025-02-15) | Link type: predicts → confirmed
"Prediction: MCP will see >50% adoption among top-20 frameworks by Q2..."

Source: spotlight_history (2025-02-01) | Link type: updates
"Previous thesis: MCP adoption was stalling due to lack of reference implementations..."
---

[Web Search Results — if applicable]
---
WEB SEARCH RESULTS:
1. [Title] — [URL] — [Tavily excerpt] — [Relevance: 0.92]
2. ...
---

[Structured Query Results — if applicable]
---
STRUCTURED DATA:
Template: trending_tools
| tool_name | mentions_7d | avg_sentiment | sentiment_trend |
| ...       | ...         | ...           | ...             |
---

[User's Current Message]
```

### Citation Handling

Citations are available on request, not by default. The system prompt includes:

> When the user asks for sources or where information came from, cite specifically:
> the source table, edition number, date, and original source URL if available in metadata.
> Otherwise, respond naturally without citations.

### LLM Routing for Generation

- **Corpus Probe**: pgvector direct (no LLM, ~50ms)
- **Intent Router**: DeepSeek V3 (fast, cheap, classification only)
- **Embedding**: OpenAI text-embedding-3-large (better domain-specific retrieval)
- **Response Generation**: Claude (editorial quality, matches newsletter voice)
- **Session Summaries**: DeepSeek V3 (simple summarization, runs async)

---

## Component 7: Observability

### Query Log

Every interaction is logged for debugging, quality analysis, and usage pattern detection:

```sql
CREATE TABLE query_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id UUID REFERENCES conversation_sessions(id),
    user_id TEXT NOT NULL,
    user_query TEXT NOT NULL,
    detected_intent TEXT NOT NULL,
    corpus_probe_top_score FLOAT,        -- Pre-routing signal quality
    retrieval_source TEXT,                -- 'corpus', 'web', 'hybrid', 'direct', 'structured', 'follow_up'
    top_similarity_score FLOAT,          -- Post-retrieval best match
    chunks_retrieved INTEGER DEFAULT 0,
    chunks_expanded INTEGER DEFAULT 0,   -- Via content_links graph expansion
    web_results_used INTEGER DEFAULT 0,
    template_name TEXT,                  -- If structured query
    response_tokens INTEGER,
    total_latency_ms INTEGER,
    probe_latency_ms INTEGER,
    router_latency_ms INTEGER,
    retrieval_latency_ms INTEGER,
    generation_latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_query_log_user ON query_log(user_id, created_at DESC);
CREATE INDEX idx_query_log_intent ON query_log(detected_intent);
CREATE INDEX idx_query_log_quality ON query_log(corpus_probe_top_score);
```

### What This Enables

- **Corpus gap detection**: Queries with low probe scores reveal topics the pipeline isn't covering
- **Router accuracy monitoring**: Track how often HYBRID is chosen (indicates ambiguity) vs. clean CORPUS/WEB splits
- **Latency profiling**: Per-component latency breakdown to identify bottlenecks
- **Usage patterns**: Which templates are popular, what topics users ask about most, peak hours
- **Retrieval quality trending**: Track average top_similarity_score over time — if it drops, chunking or corpus freshness may need attention

---

## Multi-User Considerations

### Access Control

```sql
CREATE TABLE corpus_users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    telegram_id TEXT UNIQUE,
    access_tier TEXT DEFAULT 'free' CHECK (access_tier IN ('free', 'subscriber', 'owner')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Tiered Access

All tiers have access to the full historical corpus — no restriction based on join date. Differentiation is on throughput and features:

| Tier | Conversation Memory | Corpus RAG | Web Search | Rate Limit |
|------|-------------------|------------|------------|------------|
| Owner | Full history | Full corpus, all editions | Unlimited | None |
| Subscriber | Full history | Full corpus, all editions | 20/day | 100 msgs/day |
| Free | Last 5 messages | Full corpus, all editions | 5/day | 20 msgs/day |

### Rate Limiting

```sql
CREATE TABLE user_usage (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL,
    usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
    message_count INTEGER DEFAULT 0,
    web_search_count INTEGER DEFAULT 0,
    UNIQUE(user_id, usage_date)
);
```

Increment on each interaction. Check against tier limits before processing. Simple, no Redis needed at this scale.

### Query Isolation

- Conversation sessions are scoped by `user_id`
- Corpus RAG is read-only, shared across all users (the intelligence is the product)
- Query logs are per-user for analytics

---

## Implementation Sequence

### Phase A: Foundation (Week 1)
1. Enable `pgvector` extension in Supabase
2. Create schema: `embeddings`, `content_links`, `conversation_sessions`, `conversation_messages`, `corpus_users`, `user_usage`, `query_log`
3. Write `embed_pipeline.py` — backfill embeddings for existing `spotlight_history`, `newsletters`, `predictions`
4. Write `search_corpus()` Postgres function
5. Create initial `content_links` entries from existing data (spotlight → prediction references, topic_evolution chains)
6. Test: manually embed a query and verify retrieval quality against eval harness

### Phase B: Eval Harness (Week 1)
1. Write `eval_retrieval.py` with 20-30 test queries covering all source tables
2. Run baseline evaluation against backfilled embeddings
3. Tune chunking strategy and re-run until recall@5 is acceptable (target: 80%+ of test queries return expected source in top 5)
4. This becomes the regression test for any future changes

### Phase C: Conversation Memory (Week 1-2)
1. Create `gato_brain.py` — the conversational middleware service
2. Implement session windowing (60-min gap detection)
3. Implement `retrieval_context` storage on assistant messages
4. Wire Gato's Telegram handler to pass messages through `gato_brain.py`
5. Test: multi-turn conversations with follow-up references

### Phase D: Retrieve-Then-Route (Week 2)
1. Implement corpus probe (fast pgvector top-3 lookup)
2. Implement intent router (DeepSeek V3 classification with probe scores)
3. Implement FOLLOW_UP detection and context re-hydration
4. Implement corpus deep retrieval with one-hop graph expansion via `content_links`
5. Implement structured query template library and execution
6. Wire all paths into `gato_brain.py`
7. Test: "what did the spotlight say about X?" and "tell me more about that" sequences

### Phase E: Web Search (Week 2-3)
1. Add Tavily API integration
2. Implement WEB_SEARCH and HYBRID paths
3. For HYBRID: run corpus retrieval and Tavily in parallel (asyncio)
4. Add web result formatting for context injection
5. Test: "what's the latest on X?" queries, hybrid queries, low-probe-score fallback to web

### Phase F: Pipeline Embedding Hook (Week 3)
1. Add post-pipeline trigger to run `embed_pipeline.py` incrementally
2. Add `content_links` generation to pipeline agents (Research Agent, Analyst Agent)
3. Set up cron job as fallback (daily catch-up embedding)
4. Backfill remaining tables: problems, opportunities, topic_evolution, high-tier source_posts

### Phase G: Multi-User & Observability (Week 3-4)
1. Seed `corpus_users` with owner account
2. Add access tier checks and rate limiting to `gato_brain.py`
3. Wire `query_log` inserts into every interaction path
4. Build a simple dashboard query (or Supabase view) for observability metrics
5. Test with a second Telegram account

---

## Key Architectural Decisions

### Why retrieve-then-route instead of route-then-retrieve?

The original design had the router making blind decisions — classifying intent without knowing whether the corpus had relevant content. This leads to the most common RAG failure: confidently routing to corpus retrieval when the corpus has nothing useful, producing hallucinated answers grounded on weak context. The ~50ms cost of a corpus probe is negligible compared to the DeepSeek routing call, and it transforms routing from guesswork into an informed decision.

### Why a unified `embeddings` table instead of per-table embedding columns?

- Single search function works across all content types
- Chunking means one source row → multiple embedding rows (can't do that with a column)
- Easier to re-embed or change models (drop and rebuild one table)
- Metadata filtering works uniformly

### Why content_links instead of just vector similarity?

Vector similarity finds topically related content. But for a conviction-driven publication, the *temporal narrative* matters: which thesis came first, what updated it, which prediction it generated, whether that prediction was confirmed. Content links provide the causal/temporal graph that pure semantic search cannot. Without this, RAG answers feel like isolated facts rather than evolving analysis.

### Why query templates instead of LLM-generated SQL?

LLM-generated SQL against production tables is a well-documented hazard — wrong JOINs, incorrect column names, accidentally expensive queries, injection risk. The structured questions users will ask are predictable and map to a finite set of patterns. Templates are safe, fast, and debuggable. Novel queries fall back to corpus RAG.

### Why Tavily over Brave/SerpAPI?

- Brave is cheaper but returns raw results needing parsing — extra latency and code
- SerpAPI is most comprehensive but expensive ($50/mo) and returns Google's HTML-heavy format
- Tavily returns agent-ready structured content, includes relevance scoring, and the free tier covers likely volume during development

### Why text-embedding-3-large over small?

$0.20/month more for meaningfully better domain-specific retrieval. The corpus uses specialized vocabulary (MCP, agent wallets, satoshi ledgers, interop protocols) that benefits from a higher-dimensional embedding space. This is not the cost line to optimize.

### Why not embed moltbook_posts?

- 20K rows and growing fast — index quality degrades with noisy data
- The structured analysis layer (problems, opportunities, topic_evolution) already distills the signal
- If a user query needs raw source material, the structured layer's metadata can link back

### Why DeepSeek for routing instead of regex/heuristics?

Intent classification is genuinely ambiguous — "is agent interop still a thing?" could be corpus, web, or hybrid. A fast LLM call handles edge cases regex can't, and routing logic stays updatable via prompt changes rather than code changes. Now that the router also receives corpus probe scores, the classification is even more reliable.

---

## Cost Estimate (Monthly, At Current Volume)

| Component | Cost |
|-----------|------|
| Embedding (text-embedding-3-large, ~10M tokens/mo) | ~$0.40 |
| Intent routing (DeepSeek V3, ~500 queries/mo) | ~$0.10 |
| Response generation (Claude, ~500 queries/mo) | ~$5-8 |
| Web search (Tavily, ~200 searches/mo) | Free tier (1,000/mo) |
| Supabase pgvector | Already on your plan |
| **Total incremental cost** | **~$6-9/mo** |

---

## Answered Design Questions

1. **Embedding model match across query and corpus?** Yes — use `text-embedding-3-large` for both. Asymmetric embedding adds complexity with marginal gain at this scale. The eval harness will catch quality issues if this needs revisiting.

2. **Preserve existing Gato commands?** Yes — slash commands (`/brief`, `/opps`, `/toolradar`) route through DIRECT or STRUCTURED_QUERY via the intent router. They continue to work as-is, but now have the conversation memory and corpus context available if the user follows up.

3. **Historical access for subscribers?** All tiers get full historical corpus access. No restriction based on join date. The intelligence corpus is the product — restricting it undermines the value proposition. Differentiation is on throughput (rate limits) and features (web search budget, memory depth).

4. **Session window timing?** Start with 60 minutes. The `query_log` will reveal actual usage patterns — if users frequently return after 2-3 hours to the same topic, adjust the window or add a "resume last session" command. The session summary mechanism means old sessions aren't lost, just compressed.
