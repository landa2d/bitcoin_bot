# 1A — Thought Leader Source Ingestion

## Phase
Phase 1 — Foundation

## Parallel/Sequential
**PARALLEL** — Can run simultaneously with 1B, 1C, 1D

## Dependencies
None

## Prompt

Add thought leader RSS/feed ingestion to AgentPulse. These are higher-signal sources that feed both the Analyst (for lifecycle detection) and the Research Agent (for thesis-building context).

### New Sources to Add

| Source | Type | URL/Feed | Purpose |
|--------|------|----------|---------|
| DeepLearning.AI (Andrew Ng) | Newsletter/Blog | deeplearning.ai/the-batch | When Ng teaches something, it's crossing from research to practice |
| Simon Willison's Blog | Blog + TIL | simonwillison.net | Best source for real-world agent implementation patterns |
| Latent Space | Podcast/Newsletter | latent.space | Infrastructure-level trends, the plumbing beneath agents |
| Swyx's Blog | Blog | swyx.io | Agent ecosystem analysis, developer experience trends |
| LangChain Blog (Harrison Chase) | Blog | blog.langchain.dev | Signals about tooling direction before it's obvious |
| Ethan Mollick (One Useful Thing) | Substack | oneusefulthing.substack.com | Adoption patterns, how non-technical users use agents |

### Requirements

1. **Ingestion**: Add RSS/feed scrapers for each source using the existing scraper pattern
2. **Tagging**: All items from these sources must be tagged with `source_tier: thought_leader` in the database
3. **Weighting**: These sources sit at **Tier 1.5** in the existing weighting system (between institutional Tier 1 and community Tier 2)
4. **Dual routing**: Content feeds into both:
   - The Analyst's general scan (for lifecycle signal detection)
   - A queryable pool for the Research Agent (tagged so it can pull thought-leader-only content on a specific topic)
5. **Storage**: Each ingested item should store: `source_name`, `source_tier`, `title`, `content_summary`, `url`, `published_at`, `topics_detected[]`, `ingested_at`
6. **Deduplication**: Handle cases where the same story/take appears across multiple thought leader sources
7. **Error handling**: If a feed is down or returns garbage, log the error and continue — don't block the pipeline

### Implementation Notes
- Use the same Docker/Python processor pattern as existing scrapers
- Some of these sources may require web scraping rather than pure RSS — handle both
- For podcast sources (Latent Space), ingest show notes/descriptions, not transcripts
- Run on the same cron cycle as existing scrapers

### Expected Output
- New scraper module(s) added to the existing ingestion pipeline
- Database entries tagged with `source_tier: thought_leader`
- Verification that all 6 sources are ingesting correctly
- Confirmation that the Analyst can see these in its scan and the Research Agent can query them by tier

### Acceptance Criteria
- [ ] All 6 sources ingesting successfully
- [ ] Items tagged correctly with `source_tier: thought_leader`
- [ ] Analyst sees thought leader content in its scan at Tier 1.5 weight
- [ ] Research Agent can query thought-leader-only content for a given topic
- [ ] Deduplication working across sources
- [ ] Error handling doesn't block pipeline on feed failures
