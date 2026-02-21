# 3A — Spotlight Template in Newsletter Agent

## Phase
Phase 3 — Newsletter Integration

## Parallel/Sequential
**SEQUENTIAL** — Requires 2D (Research Agent tested and producing quality output)

## Dependencies
- 2D: Research Agent must be producing quality Spotlight content

## Prompt

Update the AgentPulse Newsletter Agent to include the Spotlight section at the top of the newsletter. The Spotlight is the editorial anchor — the reason people open the email.

### Newsletter Structure (Updated)

```
1. SPOTLIGHT (new) — One conviction-driven thesis, ~400 words
2. SIGNALS (existing) — 5-7 curated developments with brief analysis
3. RADAR (added in 1D) — 3-4 emerging topics to watch
4. SCORECARD (added in 4C) — Periodic lookback on past predictions
```

### Spotlight Formatting Requirements

The Newsletter Agent pulls from `spotlight_history` for the current issue and formats it as editorial prose.

**Structure:**
1. **Headline**: The thesis statement, formatted as a bold editorial headline. Not a topic label — a claim. Example: "MCP Is Winning the Protocol War — But Its Governance Model Will Force Enterprise Forks"
2. **Opening paragraph**: Set the scene. What's happening, why it matters right now. Weave in the evidence naturally — don't list sources, integrate them into the narrative.
3. **The tension**: The "but" or "however." This is where the counter-argument lives. Present it fairly — this is what makes the analysis credible.
4. **Our take + prediction**: The editorial position. "We believe..." followed by the specific prediction. This is the money paragraph.
5. **What this means for builders**: One paragraph, practical and direct. What should someone building in this space do differently based on this analysis?

**Formatting rules:**
- No bullet points anywhere in the Spotlight
- No sub-headers within the Spotlight (the headline is enough)
- No confidence scores or certainty language
- No "Sources: ..." list at the bottom — sources are woven into the narrative
- No more than 400-500 words total. Tighter is better.
- Paragraph breaks for readability, but no more than 5 paragraphs

**When Spotlight is missing** (Research Agent failed or timed out):
- Skip the section entirely
- Do NOT put a placeholder like "No Spotlight this week"
- The newsletter should still feel complete with just Signals + Radar

### Template Implementation

The Newsletter Agent should:

```
1. Check spotlight_history for current issue_number
2. If found:
   a. Pull the structured data (thesis, evidence, counter_argument, prediction, builder_implications)
   b. Format into editorial prose following the structure above
   c. Place at the top of the newsletter
3. If not found:
   a. Skip Spotlight section
   b. Lead with Signals instead
```

### Generation Note
The Research Agent provides the raw content (thesis, evidence, etc.) as structured data. The Newsletter Agent's job is to turn this into smooth editorial prose — connecting paragraphs, ensuring flow, adjusting tone to match the rest of the newsletter. This is a formatting/writing task, not an analysis task. The Newsletter Agent should NOT change the thesis or prediction — it should just make it read well.

### Example Output

> **MCP Is Winning the Protocol War — But Its Governance Model Will Force Enterprise Forks**
>
> Over the past two weeks, MCP adoption has accelerated beyond what even its proponents expected. Three of the top five enterprise AI platforms have announced native MCP support, and GitHub activity around MCP tooling has doubled since January. Andrew Ng's latest batch of DeepLearning.AI courses now includes MCP integration as a core module — a signal that the protocol is crossing from experimentation into standard practice.
>
> But there's a tension building beneath the surface. Simon Willison pointed out that MCP's governance remains effectively centralized, with Anthropic controlling the spec evolution. Enterprise adopters are already hitting cases where they need protocol extensions that the core team hasn't prioritized. The longer this friction builds, the more likely we see what happened with GraphQL — corporate forks that fragment the ecosystem.
>
> We think this fragmentation is inevitable and will happen faster than most expect. Our prediction: at least two major enterprise frameworks will ship their own MCP variants by mid-2025, creating a more resilient but messier ecosystem. The "one protocol to rule them all" narrative has about a six-month shelf life.
>
> If you're building agent tooling, the pragmatic move is to build against MCP's core but abstract your integration layer now. The teams that treat MCP as an interface rather than a dependency will navigate the fork transition cleanly.

### Acceptance Criteria
- [ ] Spotlight section renders at the top of the newsletter
- [ ] Headline is the thesis, formatted as an editorial claim
- [ ] Content flows as editorial prose — no bullet points, no headers, no source lists
- [ ] Word count stays within 400-500 words
- [ ] Missing Spotlight handled gracefully (section skipped, newsletter still works)
- [ ] Newsletter Agent formats the Research Agent's structured output without changing the thesis or prediction
- [ ] Output matches the quality/tone of the example above
