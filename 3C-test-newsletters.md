# 3C — Test Newsletter Generation

## Phase
Phase 3 — Newsletter Integration

## Parallel/Sequential
**SEQUENTIAL** — Final validation step, requires 3B (full pipeline wired)

## Dependencies
- 3B: End-to-end pipeline must be operational

## Prompt

Generate 2-3 full test newsletters using the complete pipeline. Review quality across all sections and iterate on any issues before shipping the first real enhanced newsletter.

### Test Runs

**Test Run 1 — Happy Path:**
Run the full pipeline with real current data. Evaluate:
- Does the Spotlight topic feel like the right pick? (Is the selection heuristic choosing well?)
- Does the Spotlight thesis read as opinionated and interesting?
- Do Signals complement the Spotlight without overlapping?
- Does Radar feel like a genuine preview of what's coming?
- Does the newsletter flow well as a complete reading experience?

**Test Run 2 — Synthesis Mode:**
Manually set the threshold high so no single topic qualifies, forcing synthesis mode. Evaluate:
- Does the synthesis Spotlight connect topics in a non-obvious way?
- Does it feel as strong as a single-topic Spotlight, or weaker?
- Is the synthesis thesis a real claim or just "these three things are happening"?

**Test Run 3 — Missing Spotlight:**
Kill the Research Agent before it completes to simulate a failure. Evaluate:
- Does the newsletter generate correctly without the Spotlight?
- Does it feel complete, or is there an obvious gap?
- Is there any broken formatting or references to a missing section?

### Quality Checklist (for each test run)

**Spotlight:**
- [ ] Thesis is a specific, falsifiable claim (not a topic label)
- [ ] Evidence comes from multiple source types
- [ ] Counter-argument is genuinely strong (not a strawman)
- [ ] Prediction has a timeframe and specificity
- [ ] Builder implications are practical, not theoretical
- [ ] No AI-sounding language
- [ ] No bullet points
- [ ] 400-500 words
- [ ] Reads like it was written by a sharp analyst

**Signals:**
- [ ] 5-7 items, no overlap with Spotlight topic
- [ ] Each item has brief analysis, not just a headline
- [ ] Mix of source types represented
- [ ] Anti-repetition working (no topics from recent issues dominating)

**Radar:**
- [ ] 3-4 items, all in emerging phase
- [ ] No overlap with Signals
- [ ] Each item is one topic + one sentence (no more)
- [ ] Sentences hint at why the topic matters without going deep

**Overall:**
- [ ] Newsletter flows as a coherent reading experience
- [ ] Estimated read time: 5-8 minutes
- [ ] Tone is consistent across all sections
- [ ] No formatting artifacts or broken structure
- [ ] Telegram delivery renders correctly
- [ ] Web archive displays correctly

### Iteration Based on Test Results

If quality issues are found:

1. **Spotlight quality issues** → Go back to 2D, iterate on Research Agent prompt
2. **Selection heuristic issues** → Adjust scoring weights or thresholds in 2B
3. **Formatting issues** → Fix Newsletter Agent template in 3A
4. **Pipeline timing issues** → Adjust cron schedule in 3B
5. **Missing data issues** → Check source ingestion in 1A

### Ship Decision

The first enhanced newsletter is ready to ship when:
- [ ] At least 2 out of 3 test runs produce a newsletter you'd be proud to send
- [ ] The Spotlight passes the "forwarding test" in both test runs where it's present
- [ ] No critical formatting or pipeline issues remain
- [ ] You've read the full newsletter yourself and it feels like a step up from current issues

### Acceptance Criteria
- [ ] 3 test runs completed (happy path, synthesis mode, missing Spotlight)
- [ ] Quality checklist passed for all sections in happy path run
- [ ] Synthesis mode produces acceptable quality
- [ ] Missing Spotlight degradation is graceful
- [ ] Any issues found have been iterated on and fixed
- [ ] Ship decision criteria met
