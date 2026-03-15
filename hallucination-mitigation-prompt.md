# Task: Implement Hallucination Mitigation for AgentPulse Intelligence Briefings

## Problem

Our intelligence briefing pipeline recently surfaced a fabricated claim: it presented `spideystreet/clix` as a real 58-star GitHub MCP tool for posting to X from the terminal. In reality, `spideystreet` is just an X account, `clix` is an unrelated push notification platform, and the tool described doesn't exist. The model synthesized multiple real signals into a false composite claim with a fabricated star count.

This is a trust-critical bug — if subscribers can't trust the intelligence, the product fails.

## Architecture Context

- **Processor** (Python) is the hardcoded orchestrator — no LLM reasoning in routing/decisions
- **Analyst Agent** (Python, GPT-4o) and **Newsletter Agent** (GPT-4o) generate briefing content
- **Research Agent** (Python, Claude) does deep analysis
- Agent system prompts live in **identity files in the repo** (`.md` or `.txt` files)
- Content sources are ingested from RSS, GitHub, HN, arXiv, SEC filings, VC blogs
- Email delivery via Resend, operator notifications via Telegram/Gato

## What to Implement (Two Phases)

### Phase 1: Prompt-Level Source Attribution Enforcement

Find the agent identity files for the **Analyst Agent** and **Newsletter Agent** (and Research Agent if it contributes to briefing content). Add source attribution requirements to their system prompts. The key instruction to embed:

> Every specific tool, repository, product, or project you reference must include the exact source URL where the information was found. If you cannot point to a specific ingested source for a claim, do not include it. Never synthesize a claim by combining attributes from different sources into a single entity — if Source A mentions "spideystreet" and Source B mentions "clix MCP server", do not merge them into "spideystreet/clix". Fabricating repository names, star counts, funding amounts, or other specific metrics is strictly prohibited. When uncertain, use hedging language ("reports suggest", "appears to be") rather than asserting false specificity.

Integrate this naturally into the existing voice/identity of each agent file — don't just append it as a disclaimer block. It should read as part of the agent's editorial standards.

### Phase 2: Deterministic Verification Gate in the Processor

**First, trace the pipeline flow** from content generation to publish. Find where the newsletter/briefing output is finalized and identify whether there's an existing pre-publish step or if output goes directly to delivery (Resend/Telegram). This determines where to insert the verification gate.

Then implement a verification function in the Processor that runs **after content generation, before publish/delivery**:

1. **Extract references**: Parse the generated briefing content for GitHub repo references (patterns like `owner/repo`, `github.com/owner/repo`), and any other URLs mentioned.

2. **Verify GitHub repos**: For each extracted repo reference, hit `https://api.github.com/repos/{owner}/{repo}`:
   - If 404 → flag as fabricated
   - If 200 → compare any star count claims against actual `stargazers_count` (flag if discrepancy > 20%)
   - Use unauthenticated requests (60/hr limit is fine for our volume; add GitHub token auth as env var if available for 5,000/hr)

3. **Verify URLs**: For any non-GitHub URLs referenced, do a HEAD request with a 5-second timeout:
   - If connection fails or returns 4xx/5xx → flag as potentially fabricated

4. **Produce a validation report**: Structure as a dict/object with:
   - `verified`: list of references that passed
   - `flagged`: list of references that failed, with reason
   - `timestamp`: when validation ran

5. **Action on flags**:
   - If any references are flagged, **do not auto-strip them**. Instead:
     - Log the full validation report
     - Send a Telegram notification via Gato (or however alerts currently reach the operator) with a summary: "Briefing verification found {n} flagged references: {list}. Review before publish."
     - If there's a staging/queue mechanism, hold the briefing for manual review
     - If output currently goes straight to delivery, you'll need to add a hold/approval step — use a Supabase table field like `verification_status` on the briefing record if one exists, or propose the minimal schema change needed

## Implementation Guidelines

- **Do not introduce new agents or LLM calls** for verification. This is deterministic code in the Processor.
- **Do not break existing pipeline flow**. The verification gate should be additive — if it fails or times out, the briefing should still be deliverable (log the failure, don't block).
- **Use existing patterns**: Follow the project's existing code style, error handling, and logging conventions.
- **Rate limiting**: Be respectful of GitHub API limits. Batch requests if needed, add exponential backoff on 429s.
- **Environment variable**: Add `GITHUB_TOKEN` as an optional env var for authenticated API access. The gate should work without it (unauthenticated, lower rate limit).

## Sequencing

1. First: Read and understand the current pipeline flow end-to-end (generation → delivery)
2. Second: Update agent identity files (Phase 1)
3. Third: Implement and integrate the verification gate (Phase 2)
4. Fourth: Test with the known bad case — a briefing mentioning `spideystreet/clix` with 58 stars should trigger a flag
