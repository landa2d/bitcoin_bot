# Task: Implement X Content Distribution Pipeline for AgentPulse

## Purpose

Build a pipeline that helps the operator (Diego) maintain an active X/Twitter presence to grow AgentPulse newsletter subscriptions. The pipeline handles research, candidate surfacing, and draft generation. The operator handles voice, selection, and approval. Nothing posts without explicit operator approval via Telegram.

This system connects to Diego's **personal X account** (not a brand account). Authenticity is the priority — the pipeline suggests, the operator decides.

## Architecture Context

- **Processor** (Python) is the hardcoded orchestrator — no LLM reasoning in routing/decisions
- **Gato** (OpenClaw, Node.js) handles Telegram interactions with the operator
- **Analyst Agent** (Python, GPT-4o) already scans agent economy sources daily
- **Supabase** is the data layer (pgvector for RAG corpus, task tables for coordination)
- **DeepSeek V3** for bulk/processing tasks, **GPT-4o** for analyst functions, **Claude** for editorial
- **Telegram slash commands** feed an `editorial_inputs` table for operator steering
- **Resend** handles email delivery
- Agent identity files (`.md`) define agent behavior
- Existing pattern: agents are Python pollers that read identity files and coordinate via Supabase task tables

**X API Tier: Pay-as-you-go** (launched Feb 2026). No fixed monthly plan. Each operation (post, search, read) has a per-request cost. The free tier's 1,500 posts/month still applies for write operations, which is more than enough for our volume (~60-90 posts/month). The pay-as-you-go billing applies primarily to **read/search operations** used for engagement target discovery (watchlist monitoring, keyword search).

**Hard budget constraint: $20/month, distributed as $5/week.** The pipeline must track API spend and enforce this weekly cap. See Section 6 below for the budget tracking system.

**IMPORTANT**: A hallucination verification gate is being implemented separately (or may already be in place). Any content this pipeline generates that references GitHub repos, tools, or products **must** pass through that verification gate before reaching the operator. Check if the verification gate exists and integrate with it. If it doesn't exist yet, flag references for manual verification in the Telegram summary.

## What to Build

### 1. Supabase Schema: `x_content_candidates` Table

Create a table to store surfaced content candidates and track their lifecycle:

```
x_content_candidates
├── id (uuid, primary key)
├── created_at (timestamptz)
├── content_type (text) — enum: 'sharp_take', 'newsletter_thread', 'engagement_reply', 'prediction'
├── status (text) — enum: 'candidate', 'approved', 'rejected', 'posted', 'expired'
├── source_url (text, nullable) — the news item, post, or repo that triggered this candidate
├── source_summary (text) — brief summary of what happened / what the source says
├── suggested_angle (text) — pipeline's suggested framing or take angle
├── suggested_tags (text[], nullable) — X accounts to mention or tag
├── draft_content (text, nullable) — pipeline-generated draft (for threads: JSON array of tweet texts)
├── final_content (text, nullable) — operator-edited final version (set after approval)
├── scheduled_for (timestamptz, nullable) — when to post (null = post immediately on approval)
├── posted_at (timestamptz, nullable) — when actually posted
├── x_post_id (text, nullable) — ID of the posted tweet for tracking
├── verification_status (text, default 'pending') — 'pending', 'verified', 'flagged'
├── verification_notes (text, nullable) — details from the verification gate
├── operator_notes (text, nullable) — Diego's notes on why approved/rejected
├── engagement_data (jsonb, nullable) — post-publish metrics if tracked later
└── language (text, default 'en') — 'en' or 'es'
```

Add indexes on `status` and `content_type` for the poller queries.

### 2. Content Candidate Surfacing (runs daily, in the Processor or as part of the Analyst Agent's cycle)

This step runs once daily (morning, timed for ~7-8am CET so candidates are ready when Diego starts his day). It produces candidates for the `x_content_candidates` table.

**Source 1: Agent economy news scan**
- The Analyst Agent already ingests and clusters news from RSS, HN, GitHub, etc.
- Add a step (or extend the existing analyst cycle) that selects the top 3-5 most notable items from the last 24 hours relevant to the agent economy
- For each, generate a candidate with `content_type: 'sharp_take'`, including the source URL, a 1-2 sentence summary, and a suggested take angle
- The suggested angle should frame why this matters, not just what happened — think "what would an opinionated analyst say about this"
- Use DeepSeek V3 for this generation (it's a bulk/processing task, not editorial)

**Source 2: Engagement targets (via X API search, budget-constrained)**
- Use the X API v2 search endpoint to find high-signal posts from the agent economy space
- Two search strategies, run daily:
  - **Watchlist scan**: For each active account in `x_watchlist`, fetch their most recent 1-2 posts from the last 24 hours. Batch these efficiently — use the `from:handle1 OR from:handle2 OR from:handle3` query syntax to combine multiple accounts into fewer API calls.
  - **Keyword scan**: Search for recent posts matching agent economy keywords: `"MCP server" OR "AI agent framework" OR "agent infrastructure" OR "agentic AI" OR "agent economy"`. One query, fetch top 5-10 results by engagement.
- **Budget-aware execution**: Before making any search API call, check the `x_api_budget` table (see Section 6) for current week's spend. If the weekly $5 cap has been reached, skip engagement surfacing entirely and notify via Telegram: "⏸️ X API weekly budget reached ($5.00/$5.00). Engagement surfacing paused until [next Monday]. Manual engagement only this week."
- For each high-signal post found, generate a candidate with `content_type: 'engagement_reply'`, including the source tweet URL, what the person said, and a suggested reply angle
- Log API cost of each search call to `x_api_budget` table
- **Efficiency priority**: Minimize API calls. Combine watchlist accounts into batched queries. Cache results. If 15 watchlist accounts can be covered in 3 batched search calls instead of 15 individual ones, do that.

**Source 3: Newsletter thread drafts (runs on newsletter publish day only)**
- After a newsletter edition is finalized, generate a thread draft from the spotlight section
- Structure as a JSON array of 4-6 tweet texts:
  - Tweet 1: Hook — the conviction thesis as a provocative statement
  - Tweets 2-4: Evidence and reasoning, one idea per tweet
  - Tweet 5: The prediction with specific, trackable claim
  - Tweet 6: CTA — "Full analysis and prediction scorecard in this week's AgentPulse: [subscribe link]"
- Store as a single candidate with `content_type: 'newsletter_thread'`
- Use GPT-4o for thread drafting (editorial quality matters here)

**Source 4: Prediction posts (triggered manually via Telegram or when newsletter contains new predictions)**
- When a new prediction is added to the prediction tracker, generate a candidate with `content_type: 'prediction'`
- Format: "Prediction: [specific claim] by [date]. Tracking accountability in AgentPulse's public scorecard. [link]"
- These should also be generated when a prediction is resolved (right or wrong): "Prediction update: I said [X] by [date]. [Result]. Here's what I got right/wrong: [brief]. Full scorecard: [link]"

### 3. Telegram Approval Flow (via Gato)

**Morning briefing message (daily, after candidate surfacing completes):**

Gato sends a Telegram message to Diego with the day's candidates. Format:

```
📋 X Content Plan — [date]

🔥 TAKES (pick 1-2 to post):
1. [source headline] → Suggested angle: [angle]
   ⚠️ Flagged: [verification issue, if any]
2. [source headline] → Suggested angle: [angle]
   ✅ Verified

💬 ENGAGE (reply to these):
3. @[handle]: "[brief quote of their post]" → Reply angle: [angle]
4. @[handle]: "[brief quote of their post]" → Reply angle: [angle]

🧵 THREAD (if newsletter day):
5. Newsletter thread draft ready — [spotlight title]

Reply with numbers to approve (e.g. "1, 3, 5")
Or: /x-edit 1 to rewrite before posting
Or: /x-reject 2 to skip
Or: /x-draft 1 [your version] to replace the draft with your own text
```

**New Telegram slash commands to add:**
- `/x-approve [numbers]` — approve candidates by their daily index numbers
- `/x-reject [numbers]` — mark as rejected
- `/x-edit [number]` — Gato responds with the current draft, operator sends back edited version
- `/x-draft [number] [text]` — replace pipeline draft with operator's own text
- `/x-plan` — show today's candidates again
- `/x-posted` — show what's been posted today with any available engagement data

These commands should write to the `x_content_candidates` table (update status, final_content) and trigger the posting step when appropriate.

### 4. X Posting via MCP Server

**Setup:**
- Integrate an X MCP server for posting. Recommended: `@enescinar/twitter-mcp` (simplest, `post_tweet` and `search_tweets` tools) or `@mbelinky/x-mcp-server` (adds OAuth 2.0, media uploads)
- Store X API credentials as environment variables: `X_API_KEY`, `X_API_SECRET`, `X_BEARER_TOKEN`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`
- The MCP server should be accessible from the Processor (Python) — either via subprocess call to npx, or by wrapping the MCP client protocol in Python
- **API tier**: Using pay-as-you-go billing. Posting uses the free write allocation (1,500 posts/month — our volume is ~60-90/month, well within limits). Search/read operations are billed per-request under pay-as-you-go. Set a **spending cap of $20/month** in the X Developer Dashboard as a hard backstop, in addition to the pipeline's own weekly budget tracking.

**Posting flow (triggered by operator approval):**
1. Operator approves a candidate via Telegram
2. Gato writes approval to `x_content_candidates` (status → 'approved', final_content set)
3. Processor picks up approved candidates (poll or event-driven, follow existing patterns)
4. For single tweets: call `post_tweet` with the final content
5. For threads: post first tweet, capture tweet ID, reply to it with each subsequent tweet in sequence
6. Update `x_content_candidates` with `posted_at` and `x_post_id`
7. Send confirmation to Diego via Telegram: "✅ Posted: [first 50 chars...] — [link to tweet]"

**Error handling:**
- If posting fails (rate limit, API error), update status to 'failed', notify via Telegram with error details
- Do not retry automatically — let the operator decide

### 5. X Watchlist Table

```
x_watchlist
├── id (uuid, primary key)
├── x_handle (text, unique) — without @ prefix
├── display_name (text, nullable)
├── priority (int, default 5) — 1-10, higher = more important
├── category (text, nullable) — e.g. 'builder', 'investor', 'researcher', 'media'
├── notes (text, nullable) — why this account matters
├── active (boolean, default true)
├── created_at (timestamptz)
└── last_checked_at (timestamptz, nullable)
```

Seed with 15-20 initial accounts. Find these by searching the codebase for any existing lists of agent economy accounts, or use the Analyst Agent's existing source list as a starting point. If no existing list, leave the table empty with a note for the operator to populate via Telegram command `/x-watch [handle] [category]`.

**Additional Telegram commands for watchlist management:**
- `/x-watch [handle] [category]` — add account to watchlist
- `/x-unwatch [handle]` — deactivate account from watchlist
- `/x-watchlist` — show current watchlist

### 6. API Budget Tracking System

This is critical. The X API is on pay-as-you-go billing with a hard budget of **$20/month distributed as $5/week** (Monday-Sunday). The pipeline must self-enforce this budget so we never get surprise bills.

**Supabase table: `x_api_budget`**

```
x_api_budget
├── id (uuid, primary key)
├── created_at (timestamptz)
├── week_start (date) — Monday of the tracking week
├── operation_type (text) — 'search', 'user_lookup', 'tweet_read', 'post' (posts are free but track anyway)
├── endpoint (text) — the specific API endpoint called
├── estimated_cost (numeric(10,6)) — estimated cost of this call in USD
├── request_count (int, default 1) — number of API requests in this call
├── notes (text, nullable) — what this call was for (e.g. 'watchlist batch scan', 'keyword search')
```

**Budget enforcement logic (in the Processor):**

1. Before ANY X API read/search call, query `x_api_budget` for the current week's total:
   `SELECT COALESCE(SUM(estimated_cost), 0) FROM x_api_budget WHERE week_start = [current Monday's date]`

2. If current week spend >= $5.00 → **block the call**, skip engagement surfacing, notify operator via Telegram

3. After each API call, log the cost to `x_api_budget`. To estimate cost:
   - Check the X API pay-as-you-go pricing page for per-request costs at implementation time (these may change)
   - If exact pricing is unclear, use a conservative estimate (e.g. $0.01 per search request, $0.005 per tweet read) and document the assumptions
   - The exact costs matter less than having the tracking infrastructure — we can calibrate later

4. Weekly summary (Monday morning, alongside the content plan): Gato sends budget status:
   ```
   💰 X API Budget — Week of [date]
   Spent: $X.XX / $5.00
   Calls: N search, N reads
   Monthly total: $XX.XX / $20.00
   ```

5. Add Telegram command: `/x-budget` — shows current week and month spend

**Cost optimization strategies to implement:**
- Batch watchlist accounts into combined `from:` queries (5 accounts per query instead of 1 each)
- Cache search results — don't re-query within the same day
- Prioritize high-priority watchlist accounts first; if budget is tight, skip lower-priority accounts
- On weeks where newsletter publishing generates a thread (which drives inbound engagement naturally), reduce search spend since organic engagement will come to you

## Implementation Guidelines

- **Follow existing patterns**: This should look like the other Python pollers in the repo. Read the existing agent implementations before building.
- **Identity file**: Create an identity file for the content surfacing step (if it's a new agent) that defines the editorial lens — focused on agent economy, conviction-driven, opinionated, not news summaries.
- **Model routing**: DeepSeek V3 for candidate surfacing and take angle generation. GPT-4o for newsletter thread drafts. Do not use Claude for automated X content generation (cost).
- **Gato integration**: The Telegram slash commands need to be added to Gato's command handling. Trace the existing slash command pattern (e.g. `/share`, `/flag`, `/queue`, `/priority`) and follow the same integration approach with the `editorial_inputs` table or direct Supabase writes.
- **No autonomous posting**: Nothing ever posts without explicit operator approval via Telegram. This is a hard rule. The pipeline surfaces and suggests; the operator decides and approves.
- **Graceful degradation**: If the X MCP server is unavailable, the surfacing and approval flow should still work. Just flag that posting will need to be manual.
- **Don't over-build**: The engagement monitoring (tracking likes/retweets after posting) is a nice-to-have. Skip it in v1 unless it's trivial to add. Focus on the surfacing → approval → posting loop.

## Sequencing

1. First: Read the existing agent implementations, Gato's command handling, and the editorial_inputs flow to understand patterns
2. Second: Create Supabase schema migrations (`x_content_candidates`, `x_watchlist`, `x_api_budget`) — run these first
3. Third: Implement the budget tracking module in the Processor (this must exist before any search calls are made)
4. Fourth: Implement the content candidate surfacing step in the Processor/Analyst Agent (with budget checks on search calls)
5. Fifth: Add Telegram slash commands to Gato for the approval flow (including `/x-budget`)
6. Sixth: Integrate the X MCP server for posting
7. Seventh: Wire the full loop end-to-end and test with a real candidate cycle

## Dependencies

- The hallucination verification gate (separate task) should be integrated if it exists. Any candidate with GitHub repo references or tool mentions should pass through verification before being surfaced to the operator. Check for its existence and integrate accordingly.
- X Developer Portal account with pay-as-you-go billing enabled and a $20/month spending cap set in the dashboard (operator sets this up manually)
- X API credentials as environment variables on the Hetzner server
- The X MCP server npm package needs to be installable on the Hetzner server
- Check current X API pay-as-you-go per-request pricing at implementation time and document the rates used for cost estimation in the budget tracker
