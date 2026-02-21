# 2D — Testing and Iteration

## Phase
Phase 2 — Research Agent Core

## Parallel/Sequential
**SEQUENTIAL** — Requires 2C (full handoff working)

## Dependencies
- 2C: End-to-end Analyst → Research Agent pipeline must be operational

## Prompt

Test the Research Agent with real topics to evaluate output quality and iterate on the system prompt. Run 3-5 tests with different topic types to stress-test the thesis-building chain.

### Test Topics (select from current trending or use these archetypes)

**Test 1 — High-signal debating topic** (ideal case):
Pick the highest-velocity topic currently in "debating" phase. This is the happy path — lots of sources, clear tension, multiple perspectives. Evaluate whether the agent finds the real tension or settles for surface-level analysis.

**Test 2 — Emerging topic with thin signal**:
Pick a topic in "emerging" phase with only 5-6 mentions. Test whether the agent can form a thesis with limited data or if it defaults to vague summary. This tests the conviction engine.

**Test 3 — Technical infrastructure topic**:
Pick something like agent tooling, protocol development, or framework evolution. Test whether the agent can make this accessible and interesting to non-infrastructure people while still being substantive.

**Test 4 — Synthesis mode**:
Manually trigger synthesis mode with 3 emerging topics. Evaluate whether the agent can find a connecting thread or if it just summarizes each one separately.

**Test 5 — Topic where thought leaders disagree**:
Find a topic where Andrew Ng, Simon Willison, or other thought leaders have different takes from mainstream coverage. Test whether the agent surfaces and amplifies the disagreement.

### Evaluation Criteria

For each test output, ask:

1. **The forwarding test**: Would I forward this to a smart friend working in AI? If not, why not?
2. **The thesis test**: Can I state the thesis in one sentence? Is it specific enough to be wrong?
3. **The prediction test**: Is the prediction falsifiable? Could I check in 3 months whether it came true?
4. **The voice test**: Does it sound like a sharp analyst or a language model? Look for:
   - AI-sounding phrases (flag and remove from prompt)
   - Hedging language (tighten the prompt's conviction requirements)
   - Generic observations that could apply to anything
5. **The counter-argument test**: Does the steelman feel real or performative? A good counter-argument should make the reader think "huh, maybe they're wrong."
6. **The builder test**: Would a builder change their plans based on the "so what"? Or is it too abstract?

### Iteration Protocol

After each test:

1. Score the output 1-5 on each criterion above
2. Identify the weakest area
3. Adjust the system prompt to address the weakness
4. Re-run the same topic to verify improvement
5. Then move to the next test topic

### Common Failure Modes and Prompt Fixes

| Failure | Symptom | Prompt Fix |
|---------|---------|------------|
| Summary mode | Thesis sounds like "X is growing" | Add: "Your thesis must contain a 'but', 'however', or 'despite'. If you can't find one, you haven't looked hard enough." |
| Vague prediction | "This trend will continue" | Add: "Your prediction must include a specific number, timeframe, or named entity. 'More adoption' is not a prediction." |
| AI voice | "In the rapidly evolving landscape..." | Add the full forbidden phrases list to the system prompt. Add: "Write as if you're sending this to your smartest colleague, not presenting at a conference." |
| Weak counter-argument | Strawman opposition | Add: "The counter-argument should make you uncomfortable. If it doesn't, you picked the wrong one." |
| No thought leader integration | Only uses general sources | Add: "You MUST reference at least one thought leader perspective. If a thought leader disagrees with your thesis, lead with that tension." |
| Synthesis = separate summaries | Three topics listed, not connected | Add: "The synthesis thesis must be a SINGLE claim that only makes sense when all three topics are considered together. If you can remove one topic and the thesis still works, you haven't synthesized." |

### Documentation

After all 5 tests and iterations:
1. Record the final system prompt version
2. Document which prompt adjustments had the biggest impact on quality
3. Save the best test output as a reference example for future quality benchmarking
4. Note any remaining weaknesses to address in future iterations

### Acceptance Criteria
- [ ] At least 5 test runs completed with different topic types
- [ ] System prompt iterated at least 3 times based on test results
- [ ] Final outputs pass the "forwarding test" — genuinely interesting and sharp
- [ ] Synthesis mode produces a connected thesis, not three separate summaries
- [ ] No AI-sounding language in final outputs
- [ ] All predictions are specific and falsifiable
- [ ] Final system prompt version documented
- [ ] Best test output saved as quality benchmark
