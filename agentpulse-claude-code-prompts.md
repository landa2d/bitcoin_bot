# AgentPulse — Claude Code Prompts

## Execution Guide

Each prompt below is designed for a single Claude Code session. Prompts marked **PARALLEL** can run simultaneously in separate terminal sessions. Prompts marked **SEQUENTIAL** depend on outputs from previous prompts and must wait.

**Convention**: Before each prompt, verify the previous dependencies are complete by checking for the expected output files or running the verification command listed.

---

## PHASE A: Foundation — Schema & Infrastructure

> All three prompts in this phase can run in parallel. They touch completely separate concerns: Supabase SQL, Python embedding code, and a Postgres function. None depend on each other during creation.

---

### Prompt A1 — Supabase Schema Creation
**Mode**: PARALLEL (no dependencies)
**Target**: Run manually in Supabase SQL Editor (not Claude Code)

```
Run the following SQL migrations in the Supabase SQL Editor in order.

Migration 1: Enable pgvector and create embeddings table

  CREATE EXTENSION IF NOT EXISTS vector;

  CREATE TABLE embeddings (
      id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
      source_table TEXT NOT NULL,
      source_id UUID NOT NULL,
      chunk_index INTEGER DEFAULT 0,
      content_text TEXT NOT NULL,
      embedding VECTOR(3072) NOT NULL,
      metadata JSONB DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      edition_date DATE,
      edition_number INTEGER
  );

  CREATE INDEX idx_embeddings_vector ON embeddings
      USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
  CREATE INDEX idx_embeddings_source ON embeddings(source_table, source_id);
  CREATE INDEX idx_embeddings_date ON embeddings(edition_date DESC);
  CREATE INDEX idx_embeddings_edition ON embeddings(edition_number DESC);

Migration 2: Content links table

  CREATE TABLE content_links (
      id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
      source_table TEXT NOT NULL,
      source_id UUID NOT NULL,
      target_table TEXT NOT NULL,
      target_id UUID NOT NULL,
      link_type TEXT NOT NULL CHECK (link_type IN (
          'updates', 'supports', 'contradicts', 'predicts',
          'confirms', 'refutes', 'derived_from'
      )),
      created_at TIMESTAMPTZ DEFAULT NOW()
  );

  CREATE INDEX idx_content_links_source ON content_links(source_table, source_id);
  CREATE INDEX idx_content_links_target ON content_links(target_table, target_id);

Migration 3: Conversation memory tables

  CREATE TABLE conversation_sessions (
      id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
      user_id TEXT NOT NULL,
      started_at TIMESTAMPTZ DEFAULT NOW(),
      last_active_at TIMESTAMPTZ DEFAULT NOW(),
      is_active BOOLEAN DEFAULT TRUE,
      summary TEXT
  );

  CREATE TABLE conversation_messages (
      id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
      session_id UUID REFERENCES conversation_sessions(id),
      role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
      content TEXT NOT NULL,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      retrieval_context JSONB DEFAULT '{}'::jsonb
  );

  CREATE INDEX idx_conv_messages_session ON conversation_messages(session_id, created_at);
  CREATE INDEX idx_conv_sessions_user ON conversation_sessions(user_id, last_active_at DESC);

Migration 4: Multi-user and rate limiting tables

  CREATE TABLE corpus_users (
      id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
      telegram_id TEXT UNIQUE,
      access_tier TEXT DEFAULT 'free' CHECK (access_tier IN ('free', 'subscriber', 'owner')),
      created_at TIMESTAMPTZ DEFAULT NOW()
  );

  CREATE TABLE user_usage (
      id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
      user_id TEXT NOT NULL,
      usage_date DATE NOT NULL DEFAULT CURRENT_DATE,
      message_count INTEGER DEFAULT 0,
      web_search_count INTEGER DEFAULT 0,
      UNIQUE(user_id, usage_date)
  );

Migration 5: Query observability log

  CREATE TABLE query_log (
      id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
      session_id UUID REFERENCES conversation_sessions(id),
      user_id TEXT NOT NULL,
      user_query TEXT NOT NULL,
      detected_intent TEXT NOT NULL,
      corpus_probe_top_score FLOAT,
      retrieval_source TEXT,
      top_similarity_score FLOAT,
      chunks_retrieved INTEGER DEFAULT 0,
      chunks_expanded INTEGER DEFAULT 0,
      web_results_used INTEGER DEFAULT 0,
      template_name TEXT,
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

Migration 6: Seed owner account

  INSERT INTO corpus_users (telegram_id, access_tier)
  VALUES ('<DIEGO_TELEGRAM_ID>', 'owner');

After running all migrations, verify by running:
  SELECT table_name FROM information_schema.tables
  WHERE table_schema = 'public'
  ORDER BY table_name;

Confirm these new tables exist: embeddings, content_links, conversation_sessions, conversation_messages, corpus_users, user_usage, query_log.
```

---

### Prompt A2 — search_corpus() Postgres Function
**Mode**: PARALLEL with A1 (but run A1 first since this depends on the embeddings table existing)
**Target**: Run in Supabase SQL Editor after Migration 1 from A1 is complete

```
Run this in the Supabase SQL Editor after the embeddings table exists:

  CREATE OR REPLACE FUNCTION search_corpus(
      query_embedding VECTOR(3072),
      match_count INTEGER DEFAULT 10,
      date_from DATE DEFAULT NULL,
      source_filter TEXT[] DEFAULT NULL,
      min_edition INTEGER DEFAULT NULL
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

Verify by running:
  SELECT routine_name FROM information_schema.routines
  WHERE routine_schema = 'public' AND routine_name = 'search_corpus';
```

---

### Prompt A3 — embed_pipeline.py (Backfill Script)
**Mode**: PARALLEL (write the script now, run it after A1 completes)
**Target**: Claude Code

```
I need you to create a Python script `embed_pipeline.py` in my AgentPulse repo that embeds content from my Supabase database into the `embeddings` table using pgvector.

Context:
- My Supabase connection details are in my .env file (SUPABASE_URL, SUPABASE_SERVICE_KEY)
- I use the `supabase-py` client already in the project for other agents
- Embedding model: OpenAI text-embedding-3-large (3072 dimensions)
- OpenAI API key is in .env as OPENAI_API_KEY

The script should:

1. Connect to Supabase and OpenAI
2. For each target table, query for rows that don't yet have a corresponding entry in the `embeddings` table (check by source_table + source_id)
3. Chunk the content according to these rules:
   - spotlight_history: Split `full_text` at ~500 tokens per chunk with 50-token overlap. Also embed `thesis` and `prediction` fields as standalone chunks (chunk_index = -1 and -2 to distinguish them). Tag metadata with {"field": "thesis"} etc.
   - newsletters: Split `content_markdown` by section headers (## or ###). Each section becomes a chunk. Tag metadata with {"section_name": "<header text>", "edition_number": <N>}. Derive edition_number from the newsletter row's sequence (row number ordered by created_at).
   - problems: Single chunk per row. Concatenate: "{description}. Keywords: {keywords}. Signal phrases: {signal_phrases}"
   - opportunities: Single chunk. Concatenate: "{title}. {proposed_solution}. Business model: {business_model}. {pitch_brief}"
   - predictions: Single chunk. Use prediction_text. Tag metadata with {"status": "<status>"}
   - topic_evolution: Single chunk. Concatenate: "{thesis}. Current stage: {current_stage}"
   - source_posts: Only embed rows where source_tier >= 2 (or whatever the high-tier threshold is — check the data). Embed title + body.
4. Call OpenAI embeddings API in batches (max 100 texts per call to stay within limits)
5. Insert into the `embeddings` table with proper source_table, source_id, chunk_index, content_text, embedding, metadata, edition_date (from the source row's created_at), and edition_number
6. Log progress: "Embedded X chunks from spotlight_history", etc.
7. Handle errors gracefully — if one table fails, continue with the next
8. Support two modes:
   - `--backfill`: Process all rows (for initial setup)
   - `--incremental` (default): Only process rows without embeddings

Also create a simple tokenizer for chunking — use tiktoken with cl100k_base encoding to count tokens accurately.

Read the existing codebase to understand how Supabase is accessed in other agents and follow the same patterns. Check the .env file for the variable names used.

After creating the script, do a dry run: connect to Supabase, count how many rows would need embedding per table, and print a summary without actually calling OpenAI. This verifies the queries work.
```

---

## PHASE B: Eval Harness

> Sequential — depends on A1 (schema) and A3 (embeddings backfill) being complete and run.

---

### Prompt B1 — Retrieval Eval Harness
**Mode**: SEQUENTIAL (requires embeddings to be backfilled first)
**Verify before running**: `SELECT source_table, COUNT(*) FROM embeddings GROUP BY source_table;` returns rows

```
Create a Python script `eval_retrieval.py` in my AgentPulse repo that tests retrieval quality against the embeddings table.

Context:
- Embeddings are already backfilled in Supabase using text-embedding-3-large (3072 dimensions)
- The search_corpus() Postgres function exists and works
- Same Supabase and OpenAI credentials as embed_pipeline.py

The script should:

1. Define a test suite of 20-30 queries as a JSON list. Create these by looking at actual data in my spotlight_history, newsletters, predictions, problems, opportunities, and topic_evolution tables. Each test case should have:
   - query: natural language question a user would ask
   - expected_source_table: which table should appear in top results
   - expected_keywords: list of keywords that should appear in the retrieved content_text
   - min_acceptable_similarity: threshold (default 0.70)
   - Some test cases should be cross-table (e.g., a query about a prediction that was covered in a spotlight)

2. For each test query:
   - Embed the query using text-embedding-3-large
   - Call search_corpus() with match_count=5
   - Check: does the expected_source_table appear in top 5 results?
   - Check: do any expected_keywords appear in the retrieved content_text?
   - Check: is the top similarity score above min_acceptable_similarity?
   - Record pass/fail per check

3. Output a report:
   - Per-query results with similarity scores and pass/fail
   - Overall recall@5 (what % of queries found expected source table in top 5)
   - Overall keyword hit rate
   - Average top similarity score
   - List of failing queries with diagnostics (what WAS returned vs. what was expected)

4. Save the test suite as `eval_test_cases.json` so it can be versioned and updated
5. Save results as `eval_results_<timestamp>.json` for tracking over time

IMPORTANT: Read the actual content in spotlight_history, newsletters, and predictions first to write realistic test queries. Don't invent hypothetical ones — ground them in real data that exists in my database.

After creating the script, run it and share the results. If recall@5 is below 80%, analyze the failures and suggest chunking or metadata improvements.
```

---

## PHASE C: Conversation Memory

> Prompts C1 and C2 can run in parallel. C1 builds the core middleware service. C2 wires Gato to use it. They touch different codebases (new Python service vs. existing OpenClaw Node.js).

---

### Prompt C1 — gato_brain.py Core Service
**Mode**: PARALLEL with C2
**Verify before running**: All tables from A1 exist

```
Create a new Python service `gato_brain.py` in my AgentPulse repo. This is the conversational intelligence middleware that will sit between Gato's Telegram handler and the LLM.

For now, implement ONLY the conversation memory layer. We'll add RAG, routing, and web search in later prompts.

Context:
- Supabase tables exist: conversation_sessions, conversation_messages, corpus_users, user_usage, query_log
- This service will be called by Gato (Node.js/OpenClaw) via HTTP — so it needs a simple HTTP endpoint
- Use FastAPI since we're planning the intelligence API endpoint later anyway (Phase 7)

The service should:

1. Expose a POST endpoint: /chat
   Request body:
   {
     "user_id": "telegram_123",
     "message": "tell me more about MCP",
     "message_type": "text"
   }
   Response:
   {
     "response": "Here's what I know about MCP...",
     "session_id": "uuid",
     "intent": "DIRECT",
     "metadata": {}
   }

2. Session management:
   - On each message, check for an active session for this user_id
   - If the last message in the session was > 60 minutes ago, close it (set is_active=false, generate a summary via DeepSeek V3) and create a new session
   - If no active session exists, create one
   - Load the last 10 messages from the active session as conversation history

3. Message storage:
   - Save the user's message to conversation_messages
   - After generating a response, save the assistant message with retrieval_context JSONB (empty for now, will be populated when RAG is added)

4. Rate limiting:
   - Look up user in corpus_users to get access_tier
   - If user doesn't exist, auto-create with 'free' tier
   - Check user_usage for today's date against tier limits:
     - owner: no limits
     - subscriber: 100 msgs/day, 20 web searches/day
     - free: 20 msgs/day, 5 web searches/day
   - Increment counters on each interaction
   - Return a friendly rate limit message if exceeded

5. For now, the LLM call should:
   - Use Claude (anthropic SDK) for response generation
   - System prompt: load from SOUL.md / operator-context.md if they exist (check the workspace files Gato already uses), otherwise use a sensible default about being an AI intelligence agent
   - Include conversation history in the messages array
   - Temperature 0.7, max_tokens 2048

6. Configuration via .env:
   - ANTHROPIC_AGENT_KEY (for Claude)
   - DEEPSEEK_API_KEY (for session summaries — use OpenAI-compatible client pointing at DeepSeek API)
   - SUPABASE_URL, SUPABASE_SERVICE_KEY
   - GATO_BRAIN_PORT (default 8100)

7. Add a health endpoint: GET /health that returns {"status": "ok", "active_sessions": N}

8. Docker-ready: create a Dockerfile for this service. Check my existing Docker setup and follow the same patterns (docker-compose, networking, etc.)

Read my existing codebase to understand:
- How other agents connect to Supabase
- Where SOUL.md and other identity files live
- The existing Docker setup
- What Python dependencies are already in use

After creating the service, verify it starts without errors. Test the /health endpoint. Do NOT integrate with Gato yet — that's the next prompt.
```

---

### Prompt C2 — Wire Gato to gato_brain.py
**Mode**: PARALLEL with C1 (can start reading Gato's codebase), but the actual wiring needs C1 to be running
**Verify before running**: gato_brain.py starts and /health returns OK

```
I need to wire Gato's Telegram message handler to route messages through the new gato_brain.py service instead of calling GPT-4o directly.

Context:
- Gato runs on OpenClaw (Node.js), handles Telegram via polling
- Currently calls GPT-4o on every message with a 32KB+ system prompt composed from workspace files
- The new gato_brain.py service is running on port 8100 with a POST /chat endpoint
- gato_brain.py handles: session management, conversation memory, rate limiting, and LLM generation (using Claude instead of GPT-4o)

What I need:
1. Find the Telegram message handler in the OpenClaw codebase — the function that receives incoming messages and routes them to GPT-4o
2. Add a routing decision: 
   - Slash commands (/brief, /opps, /toolradar, etc.) continue to work as-is through OpenClaw's existing command handlers — don't break these
   - Free-form text messages (non-commands) get routed to gato_brain.py via HTTP POST to http://gato-brain:8100/chat (or localhost:8100 depending on Docker networking)
3. The HTTP call to gato_brain.py should send:
   {
     "user_id": "<telegram_user_id>",
     "message": "<message_text>",
     "message_type": "text"
   }
4. Take the response from gato_brain.py and send it back to the user via Telegram using Gato's existing reply mechanism
5. Add a timeout (15 seconds) and fallback: if gato_brain.py is unreachable or times out, fall back to the existing GPT-4o path so Gato doesn't go silent
6. Update the Docker compose to add the gato_brain service and connect it to the same network as Gato

Read the OpenClaw codebase carefully. Understand how the message handler works before making changes. Make the minimal changes needed — don't refactor Gato's existing architecture.

After making changes, describe how to test: send a non-command message to Gato on Telegram and verify it routes through gato_brain.py (check gato_brain logs for the incoming request).
```

---

## PHASE D: Retrieve-Then-Route

> D1 and D2 can run in parallel (corpus probe + router are separate modules). D3 depends on both being complete. D4 (structured templates) is independent and can run in parallel with everything in this phase.

---

### Prompt D1 — Corpus Probe Module
**Mode**: PARALLEL with D2 and D4
**Verify before running**: Embeddings backfilled (A3), gato_brain.py running (C1)

```
Add a corpus probe module to gato_brain.py that runs a fast pgvector search on every incoming message before any routing decision.

Context:
- The embeddings table is populated with content from spotlight_history, newsletters, predictions, problems, opportunities, topic_evolution
- The search_corpus() Postgres function exists
- Embedding model: OpenAI text-embedding-3-large (3072 dimensions)
- OPENAI_API_KEY is in .env

Create a module `corpus_probe.py` (or add to an appropriate location in the gato_brain codebase) that:

1. Takes a user message string
2. Embeds it using text-embedding-3-large (cache the OpenAI client, don't recreate per call)
3. Calls search_corpus() via Supabase RPC with match_count=3 (only top 3 for the probe — this is the fast path)
4. Returns a structured result:
   {
     "top_score": 0.87,
     "results": [
       {
         "id": "uuid",
         "source_table": "spotlight_history",
         "source_id": "uuid",
         "similarity": 0.87,
         "snippet": "first 200 chars of content_text..."
       },
       ...
     ],
     "latency_ms": 48
   }
5. If the embedding or search fails, return a fallback result with top_score=0.0 and empty results (don't crash the pipeline)
6. Log the probe latency for observability

Also add a function for DEEP retrieval (used after routing):
- deep_corpus_retrieval(query_embedding, match_count=10, source_filter=None, date_from=None)
- Returns full content_text, metadata, edition_number for each result
- After initial retrieval, performs ONE-HOP graph expansion via content_links:
  - For each retrieved chunk's (source_table, source_id), query content_links for linked content
  - Fetch those linked chunks from the embeddings table by source_table + source_id
  - Deduplicate and append to results, tagged as {"expanded": true, "link_type": "updates"}
  - Limit expansion to 5 additional chunks to avoid context bloat

Wire the corpus probe into gato_brain.py's /chat flow: it should run BEFORE the intent router (which we'll add next). Store the probe results in a variable that gets passed to the router.

Test by sending a message to /chat and checking logs for probe results and latency.
```

---

### Prompt D2 — Intent Router Module
**Mode**: PARALLEL with D1 and D4
**Verify before running**: gato_brain.py running (C1), DeepSeek API key in .env

```
Add an intent router module to gato_brain.py that classifies each incoming message using DeepSeek V3 and corpus probe scores.

Context:
- The corpus probe (from a parallel prompt) will pass results with top_score and snippets
- For now, mock the corpus probe input with a hardcoded test structure if the probe module isn't integrated yet
- DeepSeek V3 is accessed via OpenAI-compatible API (base_url: https://api.deepseek.com, model: deepseek-chat)
- DEEPSEEK_API_KEY is in .env

Create a module `intent_router.py` that:

1. Takes:
   - user_message: str
   - conversation_history: list of recent messages
   - corpus_probe_results: dict with top_score and results
   - previous_retrieval_context: dict or None (from last assistant message's retrieval_context)

2. Builds a router prompt (use the full prompt from the v2 plan — I'll paste it here):

   """
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
      Available templates: trending_tools, confirmed_predictions, refuted_predictions,
      open_predictions, topic_stage, top_opportunities, problem_clusters,
      recent_spotlights, prediction_scorecard

   6. FOLLOW_UP — User is referencing content from a previous response.
      Re-hydrate previous retrieval context and optionally supplement with new retrieval.

   Return ONLY valid JSON with no markdown formatting:
   {
       "intent": "CORPUS_QUERY|WEB_SEARCH|HYBRID|DIRECT|STRUCTURED_QUERY|FOLLOW_UP",
       "search_query": "optimized query for retrieval (rewritten from user message)",
       "corpus_filters": {"source_table": ["spotlight_history"], "date_from": "2025-02-01"},
       "template_name": "trending_tools",
       "template_params": {"limit": 10},
       "rehydrate_ids": ["emb_id_1", "emb_id_2"],
       "reasoning": "brief explanation of routing decision"
   }
   """

3. Calls DeepSeek V3 with temperature 0.0, max_tokens 500
4. Parses the JSON response (handle markdown code fences in case DeepSeek wraps it)
5. Validates the intent is one of the 6 allowed values
6. Returns the parsed routing decision + latency_ms
7. If DeepSeek fails or returns invalid JSON, fall back to a heuristic:
   - If corpus probe top_score >= 0.80 → CORPUS_QUERY
   - If corpus probe top_score < 0.55 → WEB_SEARCH
   - Otherwise → HYBRID
   - Log the fallback

Wire this into gato_brain.py's /chat flow: after the corpus probe runs, pass results to the router. Log the intent decision. For now, all intents still just go to the basic Claude response (we'll wire the actual retrieval paths in the next prompt).

Test by sending various messages and checking logs for intent classification:
- "hi" → should route DIRECT
- "what tools are trending?" → should route STRUCTURED_QUERY
- "what did the spotlight say about MCP?" → should route CORPUS_QUERY or HYBRID
- "tell me more about that" → should route FOLLOW_UP
```

---

### Prompt D3 — Wire Retrieval Paths into gato_brain.py
**Mode**: SEQUENTIAL (depends on D1 corpus probe + D2 router being integrated)
**Verify before running**: Both corpus probe and intent router are working (check logs show probe scores and intent decisions)

```
Now wire the full retrieval-then-route-then-generate pipeline in gato_brain.py.

Context:
- corpus_probe.py provides: probe() for fast top-3 lookup, deep_corpus_retrieval() for full retrieval with graph expansion
- intent_router.py provides: route() returning intent + search_query + filters
- The structured query templates exist (from parallel prompt D4)
- Tavily web search is NOT yet integrated — stub it for now

Modify gato_brain.py's /chat endpoint to implement the full flow:

1. Load session + conversation history (already done)
2. Run corpus probe (already done)
3. Run intent router with probe results (already done)
4. EXECUTE the routed path:

   CORPUS_QUERY:
   - Call deep_corpus_retrieval() with the router's search_query and corpus_filters
   - This includes one-hop graph expansion via content_links
   - Pass results to context assembly

   WEB_SEARCH:
   - For now, STUB this: return a placeholder message "Web search not yet available. Here's what I found in our corpus:" and fall back to corpus retrieval
   - Log that web search was requested but unavailable

   HYBRID:
   - For now: run corpus retrieval only (web search stubbed)
   - Structure the code so adding Tavily later is a single function swap

   DIRECT:
   - No retrieval, use conversation history only
   - Pass directly to Claude

   STRUCTURED_QUERY:
   - Execute the template from the router's template_name with template_params
   - Format results as a markdown table
   - Optionally pass to Claude for natural-language narration (if the raw data needs explanation)

   FOLLOW_UP:
   - Load previous assistant message's retrieval_context from the database
   - Re-fetch those specific embedding chunks by ID (exact lookup, NOT vector search)
   - Optionally run a supplementary corpus probe if the follow-up introduces a new topic
   - Pass re-hydrated + new context to Claude

5. CONTEXT ASSEMBLY — Build the Claude prompt:
   - System prompt from SOUL.md / operator-context.md
   - Conversation history (last 10 messages)
   - Retrieved corpus context (formatted with source_table, edition_number, similarity, link_type for expanded chunks)
   - Web search results (when available)
   - Structured query results (when applicable)
   - User's current message
   - Citation instruction: "When the user asks for sources, cite the source table, edition number, date, and original source URL if available. Otherwise respond naturally without citations."

6. GENERATE response via Claude (temperature 0.7, max_tokens 2048)

7. SAVE assistant message with retrieval_context:
   {
     "retrieved_chunks": ["emb_id_1", "emb_id_2"],
     "expanded_chunks": ["emb_id_3"],
     "web_results": [],
     "intent": "CORPUS_QUERY",
     "similarity_scores": [0.89, 0.84, 0.72],
     "structured_query": null
   }

8. LOG to query_log:
   - All fields: intent, probe score, retrieval source, chunks retrieved/expanded, latency breakdown

9. Return response to caller

Test with these scenarios and verify the full pipeline in logs:
- "what's our latest thesis on agent frameworks?" → CORPUS_QUERY → retrieval → expanded context → Claude
- "show me confirmed predictions" → STRUCTURED_QUERY → template execution → formatted response
- (after getting a corpus answer) "tell me more about that" → FOLLOW_UP → re-hydration → Claude
- "hey, how are you?" → DIRECT → no retrieval → Claude
```

---

### Prompt D4 — Structured Query Templates
**Mode**: PARALLEL with D1 and D2
**Verify before running**: Tables exist (A1)

```
Create a module `query_templates.py` in the gato_brain codebase that handles structured data queries via parameterized SQL templates.

Context:
- These templates query existing tables: tool_stats, predictions, topic_evolution, opportunities, problem_clusters, spotlight_history
- Supabase connection is already set up in the service
- The intent router will call this module with a template_name and template_params dict

The module should:

1. Define QUERY_TEMPLATES dict with these templates:

   trending_tools: "Tools with most mentions in the last 7 days"
     SELECT tool_name, mentions_7d, avg_sentiment, sentiment_trend FROM tool_stats ORDER BY mentions_7d DESC LIMIT %(limit)s
     default_params: {"limit": 10}

   confirmed_predictions: "Predictions that have been confirmed"
     SELECT prediction_text, status, created_at FROM predictions WHERE status = 'confirmed' ORDER BY created_at DESC
     default_params: {}

   refuted_predictions: "Predictions that have been refuted"
     SELECT prediction_text, status, created_at FROM predictions WHERE status = 'refuted' ORDER BY created_at DESC
     default_params: {}

   open_predictions: "Predictions still unresolved"
     SELECT prediction_text, created_at FROM predictions WHERE status = 'open' ORDER BY created_at DESC
     default_params: {}

   topic_stage: "Current lifecycle stage of a topic"
     SELECT topic, current_stage, thesis FROM topic_evolution WHERE topic ILIKE %(topic_pattern)s ORDER BY created_at DESC
     default_params: {"topic_pattern": "%%"}

   top_opportunities: "Highest confidence business opportunities"
     SELECT title, proposed_solution, business_model, confidence_score FROM opportunities ORDER BY confidence_score DESC LIMIT %(limit)s
     default_params: {"limit": 5}

   problem_clusters: "Problem themes by opportunity score"
     SELECT theme, opportunity_score, market_validation FROM problem_clusters ORDER BY opportunity_score DESC LIMIT %(limit)s
     default_params: {"limit": 10}

   recent_spotlights: "Recent research deep-dives"
     SELECT thesis, prediction, created_at FROM spotlight_history ORDER BY created_at DESC LIMIT %(limit)s
     default_params: {"limit": 5}

   prediction_scorecard: "Overall prediction accuracy stats"
     SELECT COUNT(*) FILTER (WHERE status = 'confirmed') AS confirmed, COUNT(*) FILTER (WHERE status = 'refuted') AS refuted, COUNT(*) FILTER (WHERE status = 'open') AS open, COUNT(*) AS total, ROUND(COUNT(*) FILTER (WHERE status = 'confirmed')::numeric / NULLIF(COUNT(*) FILTER (WHERE status IN ('confirmed', 'refuted')), 0) * 100, 1) AS accuracy_pct FROM predictions
     default_params: {}

2. IMPORTANT: Verify these SQL queries work against my actual schema. Read the actual table structures in Supabase (check column names, types). The column names above are based on the plan — they may not match exactly. Adjust the SQL to match reality.

3. Provide an execute_template(template_name, params) function that:
   - Looks up the template
   - Merges provided params with defaults
   - Executes via Supabase (use the RPC or direct query method the codebase already uses)
   - Returns results as a list of dicts
   - Also returns a formatted markdown table string for context injection

4. Provide a list_templates() function that returns template names and descriptions (used by the router prompt)

5. Input validation: reject unknown template names, sanitize params (only allow expected param keys per template)

Test each template by running it and printing results. Flag any templates that fail due to schema mismatches.
```

---

## PHASE E: Web Search

> Single prompt, sequential. Depends on the full pipeline from Phase D being functional.

---

### Prompt E1 — Tavily Web Search Integration
**Mode**: SEQUENTIAL (depends on D3 pipeline being wired)
**Verify before running**: Full pipeline works for CORPUS_QUERY and STRUCTURED_QUERY intents

```
Add Tavily web search to gato_brain.py, replacing the stubs from the previous prompt.

Context:
- Tavily API key needs to be added to .env as TAVILY_API_KEY
- The intent router already classifies WEB_SEARCH and HYBRID intents
- The pipeline already has stubs where web search should go
- For HYBRID mode, corpus retrieval and web search should run in parallel using asyncio

Create a module `web_search.py` that:

1. Initializes a TavilyClient (pip install tavily-python)

2. Provides a search function:
   async def tavily_search(query: str, max_results: int = 5) -> dict:
   Returns:
   {
     "results": [
       {"title": "...", "url": "...", "content": "...", "relevance_score": 0.92},
       ...
     ],
     "answer": "Tavily's built-in summary",
     "latency_ms": 340
   }
   Uses search_depth="advanced", include_raw_content=False, include_answer=True

3. Provides a format function that converts Tavily results into the context block format:
   WEB SEARCH RESULTS:
   1. [Title] — [URL] — [excerpt] — [Relevance: 0.92]
   2. ...

4. Error handling: if Tavily fails, return empty results with an error flag (don't crash the pipeline)

Now update gato_brain.py:

5. WEB_SEARCH path:
   - Call tavily_search() with the router's search_query
   - Pass web results to context assembly
   - No corpus context included (or only if probe had decent results as bonus context)

6. HYBRID path:
   - Run deep_corpus_retrieval() and tavily_search() in PARALLEL using asyncio.gather()
   - Both results go into context assembly
   - The context window clearly separates them:
     --- CORPUS INTELLIGENCE ---
     ...
     --- WEB SEARCH RESULTS ---
     ...
   - Claude decides how to weight them in its response

7. Update retrieval_context saved on assistant messages to include web_results:
   {"web_results": [{"url": "...", "title": "..."}]}

8. Update query_log to record web_results_used count

9. Update rate limiting: increment web_search_count in user_usage when Tavily is called. Check against tier limits before executing web search (owner: unlimited, subscriber: 20/day, free: 5/day). If limit exceeded, fall back to corpus-only with a note.

Test:
- "what's the latest news on Anthropic?" → should trigger WEB_SEARCH, return Tavily results
- "is our thesis on agent wallets still valid based on current news?" → should trigger HYBRID, return both corpus and web results in parallel
- Verify HYBRID latency is roughly max(corpus, web) not sum(corpus, web)
```

---

## PHASE F: Pipeline Embedding Hook

> F1 and F2 can run in parallel. F1 hooks embedding into the existing pipeline. F2 backfills the remaining tables and generates content links.

---

### Prompt F1 — Post-Pipeline Embedding Trigger
**Mode**: PARALLEL with F2
**Verify before running**: embed_pipeline.py works in incremental mode (A3)

```
Hook embed_pipeline.py into the existing AgentPulse pipeline so new content gets embedded automatically after each agent completes.

Context:
- The pipeline flow is: Processor → Analyst → Research Agent → Newsletter Agent
- Each agent's completion is tracked in pipeline_runs and/or agent_tasks tables
- embed_pipeline.py already supports --incremental mode (only embeds rows without existing embeddings)

Read the existing pipeline orchestration code to understand:
1. How agents are triggered (cron? task queue? sequential script?)
2. Where each agent signals completion
3. How to add a post-completion hook

Then:
1. Add a call to embed_pipeline.py --incremental after each relevant agent completes:
   - After Processor: embed new problems, opportunities
   - After Analyst: embed new topic_evolution
   - After Research Agent: embed new spotlight_history, predictions
   - After Newsletter Agent: embed new newsletter sections

2. The embedding step should be NON-BLOCKING — if it fails, the pipeline continues normally. Log errors but don't halt.

3. Also set up a daily cron job that runs embed_pipeline.py --incremental as a catch-all. This handles any rows that were missed (e.g., if the post-agent hook failed). Add this to the existing cron setup or Docker entrypoint.

4. Add a simple check: if embed_pipeline.py has run in the last 24 hours and processed 0 new rows across all tables, log a warning — this might indicate the pipeline isn't producing new content (like the current issue where problems/opportunities have 0 new rows in 7 days).

Don't modify the agents themselves — only add hooks at the orchestration layer.
```

---

### Prompt F2 — Backfill Remaining Tables + Content Links
**Mode**: PARALLEL with F1
**Verify before running**: embed_pipeline.py works (A3), content_links table exists (A1)

```
Two tasks:

TASK 1: Run embed_pipeline.py to backfill the remaining tables that weren't in the initial backfill.

The initial backfill (Phase A) covered spotlight_history, newsletters, predictions. Now backfill:
- problems (211 rows)
- opportunities (43 rows)
- topic_evolution (30 rows)
- source_posts with source_tier >= 2 (check how many qualify)

Run: python embed_pipeline.py --backfill

Verify with: SELECT source_table, COUNT(*) FROM embeddings GROUP BY source_table ORDER BY count DESC;

TASK 2: Generate initial content_links entries from existing data.

Create a script `generate_content_links.py` that:

1. Scans spotlight_history for references to predictions:
   - Check if spotlight thesis or full_text mentions prediction_text from the predictions table (fuzzy match or keyword overlap)
   - If match found, create a content_link: spotlight → predictions, link_type 'predicts'

2. Scans predictions for status changes:
   - If a prediction is 'confirmed' or 'refuted', look for spotlight_history entries that discuss the same topic after the prediction was created
   - Create content_link: spotlight → prediction, link_type 'confirms' or 'refutes'

3. Scans topic_evolution for chains:
   - If multiple topic_evolution rows share the same topic name, link them chronologically
   - Earlier → later, link_type 'updates'

4. Scans problem_clusters → opportunities:
   - If an opportunity's title/description overlaps with a problem_cluster's theme
   - Create content_link: problem_cluster → opportunity, link_type 'derived_from'

5. Scans newsletters for spotlight references:
   - If a newsletter's content_markdown mentions a spotlight thesis
   - Create content_link: newsletter → spotlight, link_type 'supports'

This doesn't need to be perfect — we're building the initial graph. The linking logic will improve over time as agents learn to log links during pipeline runs.

Run the script and report: how many content_links were generated, broken down by link_type.

Also run the eval harness (eval_retrieval.py) AFTER this backfill to see if retrieval quality improved with the additional embeddings. Compare recall@5 before and after.
```

---

## PHASE G: Final Integration & Testing

> Sequential. This is the integration testing and hardening phase.

---

### Prompt G1 — End-to-End Testing & Hardening
**Mode**: SEQUENTIAL (everything must be working)
**Verify before running**: All previous phases complete. Full pipeline works for all 6 intent types.

```
Run a comprehensive end-to-end test of the conversational intelligence system and fix any issues found.

Test the following scenarios by sending actual Telegram messages to Gato:

TEST 1 — Basic conversation memory:
- Send: "hi"
- Send: "what's the latest spotlight about?"
- Send: "tell me more about that"
- Verify: third message correctly references the second message's context (FOLLOW_UP intent)

TEST 2 — Corpus deep dive:
- Send: "what's our thesis on [topic from actual spotlight_history]?"
- Verify: response draws from spotlight_history, similarity scores logged, content_links expansion happened

TEST 3 — Structured queries:
- Send: "what tools are trending?"
- Send: "show me the prediction scorecard"
- Send: "any confirmed predictions?"
- Verify: each triggers STRUCTURED_QUERY, correct template executes, results are formatted

TEST 4 — Web search:
- Send: "what's the latest news on Anthropic?"
- Verify: WEB_SEARCH intent, Tavily results in context, response includes current info

TEST 5 — Hybrid:
- Send: "is our thesis on [recent topic] still valid based on current news?"
- Verify: HYBRID intent, both corpus and web results, parallel execution (check latency)

TEST 6 — Follow-up with re-hydration:
- After any corpus answer, send: "what was the source for that?"
- Verify: FOLLOW_UP intent, previous retrieval_context loaded, citations provided

TEST 7 — Session windowing:
- Check conversation_sessions table: verify sessions are created/closed correctly
- Verify last_active_at updates on each message

TEST 8 — Rate limiting:
- Create a test user with 'free' tier
- Send 21 messages (should be rate limited on the 21st)
- Verify friendly rate limit message

TEST 9 — Observability:
- Check query_log table has entries for all tests above
- Verify latency breakdown fields are populated
- Run: SELECT detected_intent, COUNT(*), AVG(corpus_probe_top_score), AVG(total_latency_ms) FROM query_log GROUP BY detected_intent;

TEST 10 — Fallback resilience:
- Temporarily break the DeepSeek API key
- Send a message — verify the router falls back to heuristic routing (not crash)
- Restore the key

For each test, log:
- What was sent
- What intent was detected
- What the response was
- Whether it was correct
- Any errors in logs

Fix any issues found. After all tests pass, provide a summary of:
- Average latency per intent type
- Any edge cases discovered
- Recommendations for tuning (similarity thresholds, session window, etc.)
```

---

## Execution Map — Visual Summary

```
Week 1:
┌─────────────────────────────────────────────────────────┐
│ A1 (SQL)  ──────►  A2 (function)                        │
│     │                                                    │
│ A3 (embed_pipeline.py) ──► Run backfill                  │
│                               │                          │
│                          B1 (eval harness) ── Run eval   │
│                                                          │
│ C1 (gato_brain.py) ─────────────────────┐                │
│ C2 (wire Gato) ──── waits for C1 ───────┤                │
└─────────────────────────────────────────────────────────┘

Week 2:
┌─────────────────────────────────────────────────────────┐
│ D1 (corpus probe)  ─┐                                    │
│ D2 (intent router)  ─┼──► D3 (wire full pipeline)        │
│ D4 (query templates) ┘                                    │
└─────────────────────────────────────────────────────────┘

Week 2-3:
┌─────────────────────────────────────────────────────────┐
│ E1 (Tavily web search) ── sequential after D3            │
│                                                          │
│ F1 (pipeline hooks)  ─┐                                  │
│ F2 (backfill + links) ┘── parallel                       │
└─────────────────────────────────────────────────────────┘

Week 3-4:
┌─────────────────────────────────────────────────────────┐
│ G1 (end-to-end testing + hardening)                      │
└─────────────────────────────────────────────────────────┘
```

**Total prompts: 12**
**Parallelizable pairs: A1+A3, C1+C2, D1+D2+D4, F1+F2**
**Critical path: A1 → A3 → B1 → C1 → D1+D2 → D3 → E1 → G1**
