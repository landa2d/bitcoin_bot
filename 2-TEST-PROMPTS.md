# Phase 2 — Test Prompts

Run each of these prompts separately in Cursor after the corresponding Phase 2 task is complete.

---

## TEST 2A: Research Agent Core Processor

```
Test the Research Agent processor for AgentPulse. Write and run a Python test script that:

1. Setup — insert a test item into research_queue:
   - Pick a real topic from the Analyst's current data (highest velocity in "debating" or "building" phase)
   - Build a realistic context_payload using actual recent source data for that topic
   - Insert into research_queue with status="queued", mode="spotlight", issue_number=998
   - Print the topic selected and the context_payload summary

2. Test queue pickup:
   - Call the Research Agent's queue polling function
   - Verify it picks up the test item (the one with highest priority and status="queued")
   - Verify it updates status to "in_progress" and sets started_at
   - Query the database to confirm the status change

3. Test source gathering:
   - Call the Research Agent's source gathering function with the test topic
   - Print counts: general sources found, thought_leader sources found, github signals found
   - Verify at least 1 general source was found (FAIL if 0)
   - Verify thought_leader sources are included when available (WARN if 0, not FAIL — topic may not have thought leader coverage)
   - Print the top 3 sources by relevance so I can eyeball quality

4. Test thesis generation:
   - Call the Research Agent's LLM thesis-building chain with the gathered sources
   - Capture the full response
   - Time the execution (print duration in seconds)
   - Verify the output parses into the expected structure:
     - thesis: string, single sentence (FAIL if more than 2 sentences)
     - evidence: string, at least 100 words
     - counter_argument: string, at least 50 words
     - prediction: string, contains a timeframe
     - builder_implications: string, at least 30 words
     - key_sources: array with at least 2 entries
   - Print the full parsed output

5. Test storage:
   - Verify a row was created in spotlight_history with all fields populated
   - Verify research_queue_id links correctly to the queue item
   - Verify full_output is the concatenated text of all sections
   - Verify sources_used is valid JSONB with at least 1 entry
   - Print the spotlight_history row id

6. Test completion:
   - Verify research_queue status updated to "completed"
   - Verify completed_at is set and is after started_at
   - Print the total processing time (completed_at - started_at)

7. Test synthesis mode:
   - Insert a NEW research_queue item with mode="synthesis" and context_payload containing 3 topics
   - Run the Research Agent on this item
   - Verify the output has mode="synthesis" in spotlight_history
   - Verify the thesis connects the 3 topics (check that all 3 topic names appear somewhere in the evidence or full_output)
   - Print the synthesis thesis so I can evaluate quality

8. Test error handling:
   a. Bad context — insert a queue item with empty context_payload. Run the agent.
      Verify it either produces a result using whatever data it can find, or marks the item as "failed" with an error message. It should NOT crash.
   b. Verify that after a failure, the queue item has status="failed" and an error is logged.

9. Clean up ALL test data:
   - Delete spotlight_history rows with issue_number=998
   - Delete research_queue rows with issue_number=998
   - Verify no test data remains

10. Print summary:
    ```
    === RESEARCH AGENT CORE TEST ===
    Topic tested: [topic name]
    
    Queue pickup:          PASS/FAIL
    Source gathering:       PASS/FAIL ([X] general, [Y] thought_leader, [Z] github)
    Thesis generation:     PASS/FAIL (took [X]s)
    Output structure:      PASS/FAIL (list any missing/invalid fields)
    Storage:               PASS/FAIL
    Completion lifecycle:  PASS/FAIL (total time: [X]s)
    Synthesis mode:        PASS/FAIL
    Error handling:        PASS/FAIL
    Cleanup:               PASS/FAIL
    
    === GENERATED SPOTLIGHT (for manual review) ===
    THESIS: [thesis]
    EVIDENCE: [first 200 chars]...
    COUNTER: [first 200 chars]...
    PREDICTION: [prediction]
    BUILDER: [first 200 chars]...
    
    === SYNTHESIS OUTPUT (for manual review) ===
    THESIS: [synthesis thesis]
    ```
```

---

## TEST 2B: Analyst Selection Heuristic

```
Test the Spotlight topic selection heuristic in the AgentPulse Analyst. Write and run a Python test script that:

1. Query current topic landscape:
   - Pull all tracked topics with their velocity, source_diversity, and lifecycle_phase
   - Print the top 10 topics ranked by the raw spotlight_score formula: velocity × source_diversity × lifecycle_bonus
   - Print each topic's breakdown: name, velocity, source_diversity, lifecycle_phase, lifecycle_bonus, raw_score

2. Test lifecycle bonus multipliers:
   - Verify the multipliers are applied correctly:
     - emerging = 1.0x
     - debating = 1.5x
     - building = 1.3x
     - mature = 0.5x
     - declining = 0.2x
   - For the top 10 topics, print: raw_score (without bonus) vs final_score (with bonus)
   - Verify the ranking changes after applying lifecycle bonuses (debating topics should move up)

3. Test cooldown filter:
   - Insert 2 fake spotlight_history rows: one for issue_number = current_issue - 1 (recent, should be on cooldown) and one for issue_number = current_issue - 10 (old, should NOT be on cooldown)
   - Run the selection heuristic
   - Verify the recent topic is excluded from candidates
   - Verify the old topic is NOT excluded
   - Clean up fake rows

4. Test minimum signal filters:
   - Verify topics with fewer than 3 mentions in the last 7 days are excluded
   - Print any topics that were excluded by this filter and their mention count
   - Verify topics mentioned by only 1 source tier are excluded
   - Print any topics that were excluded by the single-tier filter

5. Test the full selection:
   - Run the complete selection heuristic (scoring + filtering + cooldown)
   - Print the winning topic and its score breakdown
   - Verify a row was written to research_queue with correct fields:
     - topic_id and topic_name match the winner
     - priority_score matches the calculated score
     - velocity and source_diversity are populated
     - lifecycle_phase is correct
     - context_payload contains recent_mentions and contrarian_signals
     - mode is "spotlight"
     - status is "queued"
   - Delete the test research_queue row

6. Test synthesis fallback:
   - Temporarily set min_score_threshold very high (e.g., 99.0) so no topic qualifies
   - Run the selection heuristic
   - Verify it triggers synthesis mode:
     - research_queue row has mode="synthesis"
     - context_payload contains data for 3 topics (not 1)
   - Print the 3 topics selected for synthesis and their scores
   - Reset threshold and clean up

7. Test edge cases:
   a. All topics on cooldown — verify synthesis mode triggers (or graceful skip)
   b. No topics in the database at all — verify no crash, no queue entry written
   c. Only 1 topic exists — verify it's selected if it meets minimum filters

8. Print summary:
    ```
    === SELECTION HEURISTIC TEST ===
    Total topics evaluated:     [count]
    Passed minimum filters:     [count]
    Passed cooldown filter:     [count]
    
    Top 5 candidates:
    1. [topic] — score: [X] (velocity: [V], diversity: [D], phase: [P], bonus: [B]x)
    2. ...
    
    Winner: [topic] (score: [X])
    
    Lifecycle bonuses:         PASS/FAIL
    Cooldown filter:           PASS/FAIL
    Minimum signal filters:    PASS/FAIL
    Full selection:            PASS/FAIL
    Queue entry written:       PASS/FAIL
    Context payload complete:  PASS/FAIL
    Synthesis fallback:        PASS/FAIL
    Edge cases:                PASS/FAIL
    Cleanup:                   PASS/FAIL
    ```
```

---

## TEST 2C: Analyst → Research Agent Handoff

```
Test the handoff wiring between the Analyst and Research Agent in AgentPulse. Write and run a Python test script that:

1. Test trigger file creation:
   - Run the Analyst's Spotlight selection (or simulate it by calling the selection function)
   - Verify a trigger file was created in the queue directory (e.g., /queue/research-trigger-{timestamp}.json)
   - Read the trigger file and verify its contents:
     - trigger_type = "research_request"
     - research_queue_id matches the database entry
     - topic_name is populated
     - mode is "spotlight" or "synthesis"
     - triggered_at is a valid timestamp
   - Print the trigger file contents

2. Test Research Agent picks up trigger:
   - With the trigger file in place, start/call the Research Agent's polling mechanism
   - Verify it detects the trigger file
   - Verify it reads the correct research_queue_id from the trigger
   - Verify it starts processing (status changes to "in_progress")
   - Print timestamps: trigger created, agent detected, processing started

3. Test trigger cleanup:
   - After the Research Agent completes (or simulate completion by updating status to "completed")
   - Verify the trigger file is removed from the queue directory
   - Verify no orphan trigger files remain
   - List remaining files in queue directory

4. Test end-to-end handoff timing:
   - Time the full sequence: Analyst selection → trigger write → Research Agent pickup → processing → completion
   - Print each stage's duration:
     - Selection: [X]s
     - Trigger write: [X]s  
     - Agent pickup delay: [X]s
     - Research processing: [X]s
     - Total handoff: [X]s
   - WARN if total exceeds 90 minutes (the timeout threshold from the pipeline design)

5. Test duplicate trigger prevention:
   - Manually create a trigger file in the queue directory
   - Run the Analyst selection again
   - Verify it does NOT create a second trigger file (or overwrites cleanly)
   - Clean up

6. Test timeout/resilience:
   - Create a trigger file but DON'T start the Research Agent
   - Simulate the Newsletter Agent checking for a completed Spotlight for the current issue
   - Verify the Newsletter Agent finds no spotlight_history entry and proceeds without a Spotlight section
   - Verify the newsletter would still generate correctly (Signals + Radar only)
   - Print what the Newsletter Agent would do: "Spotlight found: yes/no"

7. Test Research Agent failure:
   - Insert a research_queue item that will cause the Research Agent to fail (e.g., invalid topic_id or empty context)
   - Trigger the Research Agent
   - Verify status updates to "failed" (not stuck on "in_progress")
   - Verify the trigger file is still cleaned up even on failure
   - Verify the Newsletter Agent can proceed without a Spotlight

8. Clean up all test data:
   - Delete test research_queue rows
   - Delete test spotlight_history rows
   - Remove any remaining test trigger files
   - Verify clean state

9. Print summary:
    ```
    === HANDOFF WIRING TEST ===
    Trigger file creation:      PASS/FAIL
    Trigger file contents:      PASS/FAIL
    Research Agent pickup:      PASS/FAIL
    Trigger cleanup:            PASS/FAIL
    End-to-end timing:          [X]s (PASS if <90min, WARN if >90min)
    Duplicate prevention:       PASS/FAIL
    Timeout resilience:         PASS/FAIL
    Failure handling:           PASS/FAIL
    Newsletter without Spotlight: PASS/FAIL
    Cleanup:                    PASS/FAIL
    ```
```

---

## TEST 2D: Research Agent Quality Iteration

```
Test the Research Agent output quality across multiple topic types for AgentPulse. Write and run a Python script that:

This is a QUALITY test, not a functional test. The goal is to evaluate whether the Research Agent produces genuinely interesting, opinionated analysis across different topic types.

1. Select 5 test topics from the current data:
   - Topic A: Highest velocity topic in "debating" phase (ideal case — lots of signal)
   - Topic B: A topic in "emerging" phase with the fewest mentions (thin signal stress test)
   - Topic C: A technical/infrastructure topic (e.g., tooling, protocols, frameworks)
   - Topic D: A topic where thought leader sources have different takes than general sources (contrarian test)
   - Topic E: Synthesis mode — pick the top 3 emerging topics
   
   For each, print: topic_name, lifecycle_phase, velocity, mention_count, source_tier_breakdown
   
   If any category has no good candidate, note it and skip that test.

2. For each topic, run the full Research Agent pipeline:
   - Build context payload from real data
   - Call the Research Agent
   - Capture the full output
   - Time the execution

3. For each output, run automated quality checks:

   STRUCTURE CHECKS:
   - All required fields present (thesis, evidence, counter_argument, prediction, builder_implications)
   - Thesis is 1-2 sentences max
   - Evidence is 100+ words
   - Counter-argument is 50+ words
   - Prediction contains a timeframe
   - Builder implications is 30+ words

   VOICE CHECKS:
   - Scan for hedging phrases: "it remains to be seen", "time will tell", "it could go either way", "may or may not", "only time will tell", "the jury is still out"
   - Scan for AI phrases: "in the rapidly evolving landscape", "it's worth noting", "as we navigate", "at the end of the day", "a myriad of", "it's important to understand", "in conclusion", "there are several factors"
   - Scan for weak openings: "This is an interesting development", "There are several", "It's important to"
   - Scan for bullet points or numbered lists anywhere in the output

   CONVICTION CHECKS:
   - Thesis contains a tension word: "but", "however", "despite", "yet", "although", "while", "even though"
   - Prediction contains a specific: number, named entity, quarter (Q1-Q4), month name, year, or "by [date]"
   - Counter-argument is at least 40% the length of the evidence (not a throwaway)
   - No "both sides" language without taking a position: "on one hand... on the other hand" without a "we believe" or "our take"

   SOURCE CHECKS:
   - key_sources has at least 2 URLs
   - For Topic D specifically: at least one thought_leader source referenced
   - Sources span at least 2 different source tiers

4. For synthesis mode (Topic E):
   - All 3 topic names appear in the evidence or full_output
   - The thesis is a SINGLE claim (not three separate statements joined by "and")
   - Test: remove one topic name from the thesis — does it still make sense? If yes, it's not truly synthesized. Flag this.

5. Print ALL outputs in full so I can review them manually:

   ```
   ============================================================
   TOPIC A: [name] (debating, velocity: [X], [Y] sources)
   Processing time: [X]s
   ============================================================
   
   THESIS: [full thesis]
   
   EVIDENCE:
   [full evidence]
   
   COUNTER-ARGUMENT:
   [full counter-argument]
   
   PREDICTION: [full prediction]
   
   BUILDER IMPLICATIONS:
   [full builder implications]
   
   QUALITY SCORES:
   - Structure:   PASS/FAIL [details]
   - Voice:       PASS/FAIL [any flagged phrases]
   - Conviction:  PASS/FAIL [details]
   - Sources:     PASS/FAIL [count and tiers]
   
   ============================================================
   [repeat for each topic]
   ============================================================
   ```

6. Print comparative summary:

   ```
   === RESEARCH AGENT QUALITY REPORT ===
   
   | Topic | Type | Structure | Voice | Conviction | Sources | Overall |
   |-------|------|-----------|-------|------------|---------|---------|
   | A     | debating | PASS | PASS | PASS | PASS | PASS |
   | B     | emerging | PASS | FAIL | PASS | WARN | MIXED |
   | ...   | ... | ... | ... | ... | ... | ... |
   
   Common issues across all outputs:
   - [list any quality check that failed on 2+ topics]
   
   Prompt improvement suggestions:
   - [based on failures, suggest specific prompt changes]
   
   READY FOR PHASE 3: YES / NO (yes only if 4/5 topics pass overall)
   ```

Print everything — I need to read every output to judge whether these are genuinely good enough to publish.
```

---

## INTEGRATION SMOKE TEST: Full Phase 2

Run this AFTER all individual Phase 2 tests pass.

```
Run a full Phase 2 integration test for AgentPulse that simulates a complete newsletter cycle from Analyst selection through Research Agent output. Write and run a Python script that:

1. Simulate a full Analyst cycle:
   - Run the Analyst scan (or trigger it)
   - Verify topic lifecycle updates completed
   - Verify the Spotlight selection heuristic ran
   - Print the selected topic and its score

2. Verify handoff:
   - Confirm research_queue has a new entry with status="queued"
   - Confirm trigger file was created
   - Print the trigger file path and contents

3. Run the Research Agent:
   - Let it pick up the trigger and process
   - Wait for completion (with a timeout of 5 minutes for this test)
   - Verify spotlight_history has a new entry

4. Validate the Spotlight output:
   - Pull the spotlight_history row
   - Run the quality checks from TEST 2D (structure, voice, conviction, sources)
   - Print the full Spotlight content

5. Verify pipeline state is clean:
   - research_queue item status = "completed"
   - Trigger file removed
   - spotlight_history row has all fields populated
   - No orphan data

6. Verify Newsletter Agent readiness:
   - Query spotlight_history for the current issue
   - Confirm the Newsletter Agent would find and use this Spotlight
   - Query emerging topics for Radar section
   - Print what the full newsletter would contain:
     - "Spotlight: [thesis headline] — READY"
     - "Signals: [count] items — READY"  
     - "Radar: [count] emerging topics — READY"

7. Print summary:
    ```
    === PHASE 2 INTEGRATION TEST ===
    Analyst selection:          PASS/FAIL — selected: [topic]
    Research queue entry:       PASS/FAIL
    Trigger handoff:            PASS/FAIL
    Research Agent processing:  PASS/FAIL (took [X]s)
    Spotlight quality:          PASS/FAIL
    Pipeline state clean:       PASS/FAIL
    Newsletter Agent ready:     PASS/FAIL
    
    Newsletter would contain:
    - Spotlight: [thesis, first 80 chars]...
    - Signals: [X] items
    - Radar: [X] topics
    
    READY FOR PHASE 3: YES/NO
    ```

Do NOT clean up the test data from this run — leave the spotlight_history entry so Phase 3 tests can use it as real input. Just note the issue_number used so Phase 3 knows which one to look for.
```
