# Phase 3 — Test Prompts

Run each of these prompts separately in Cursor after the corresponding Phase 3 task is complete.

---

## TEST 3A: Spotlight Template in Newsletter Agent

```
Test the Spotlight section formatting in the AgentPulse Newsletter Agent. Write and run a Python test script that:

1. Verify Spotlight data availability:
   - Query spotlight_history for the most recent entry (should exist from Phase 2 integration test)
   - Print the raw data: thesis, evidence, counter_argument, prediction, builder_implications
   - If no spotlight_history entry exists, insert a realistic test entry with issue_number=997 so we can test formatting
   - Print the issue_number being used for this test

2. Test Spotlight formatting:
   - Call the Newsletter Agent's Spotlight formatting function with the spotlight_history data
   - Capture the full formatted output
   - Print it exactly as it would appear in the newsletter

3. Validate format rules:
   
   HEADLINE CHECK:
   - First line is a bold headline
   - Headline is the thesis (or a sharpened version), NOT a topic label
   - Headline reads as a claim, not a description (should contain a verb and a position)
   - FAIL if headline is just a topic name like "MCP Protocol Update"
   
   PROSE CHECK:
   - Zero bullet points anywhere in the Spotlight (FAIL if any found)
   - Zero numbered lists (FAIL if any found)
   - Zero sub-headers within the Spotlight section (FAIL if any found — only the main headline)
   - No "Sources:" list at the bottom (FAIL if found)
   - Content is organized in paragraphs (check for at least 3 paragraph breaks)
   
   LENGTH CHECK:
   - Count total words in the Spotlight
   - PASS if 350-550 words
   - WARN if 300-349 or 551-600
   - FAIL if under 300 or over 600
   
   STRUCTURE CHECK:
   - Paragraph 1: Sets the scene / what's happening (check evidence themes appear here)
   - Paragraph 2-3: Contains the tension / counter-argument (scan for "but", "however", "yet", "although")
   - Final paragraphs: Contains the prediction and builder implications
   - Check that the prediction from spotlight_history appears in the formatted output (it shouldn't be dropped)
   - Check that builder_implications content appears (it shouldn't be dropped)
   
   TONE CHECK:
   - Scan for "we believe", "we think", "our take", "our prediction" — at least one should appear (editorial voice)
   - Scan for forbidden AI phrases: "it's worth noting", "in the rapidly evolving", "as we navigate", "in conclusion"
   - Scan for hedging: "it remains to be seen", "time will tell", "only time will tell"

4. Test that Newsletter Agent preserves the thesis:
   - Compare the thesis in spotlight_history with the headline in the formatted output
   - They should be the same claim (wording can differ slightly but the position must match)
   - FAIL if the Newsletter Agent softened, hedged, or changed the thesis direction
   - Similarly check the prediction — the specific claim and timeframe must be preserved

5. Test missing Spotlight behavior:
   - Call the Newsletter Agent's generation with NO spotlight_history entry for the target issue
   - Verify the Spotlight section is completely absent (not an empty section, not a placeholder)
   - Verify the newsletter output starts directly with Signals
   - Verify no broken formatting, no orphan headers, no "Spotlight:" label with nothing after it
   - Print the first 500 chars of the newsletter-without-Spotlight so I can verify

6. Print summary:
   ```
   === SPOTLIGHT TEMPLATE TEST ===
   
   Formatted Spotlight:
   ───────────────────────────────
   [full formatted Spotlight output]
   ───────────────────────────────
   
   Format checks:
   - Headline is a claim:       PASS/FAIL
   - No bullet points:          PASS/FAIL
   - No numbered lists:         PASS/FAIL
   - No sub-headers:            PASS/FAIL
   - No source list:            PASS/FAIL
   - Word count: [X]            PASS/WARN/FAIL
   - Paragraph structure:       PASS/FAIL
   - Thesis preserved:          PASS/FAIL
   - Prediction preserved:      PASS/FAIL
   - Editorial voice present:   PASS/FAIL
   - No AI phrases:             PASS/FAIL [list any found]
   - No hedging:                PASS/FAIL [list any found]
   - Missing Spotlight graceful: PASS/FAIL
   ```
```

---

## TEST 3B: End-to-End Pipeline

```
Test the full AgentPulse pipeline end-to-end, from data collection through newsletter delivery. Write and run a Python test script that:

1. Run the complete pipeline in sequence:
   Log timestamps at each stage so we can measure timing.

   a. SCRAPING STAGE:
      - Trigger general scrapers
      - Trigger thought leader scrapers
      - Wait for completion
      - Print: items ingested (general), items ingested (thought_leader), duration

   b. ANALYST STAGE:
      - Trigger the Analyst scan cycle
      - Wait for completion
      - Print: topics tracked, lifecycle transitions, Spotlight selection result
      - If Spotlight selected: print topic name, score, mode
      - If synthesis mode: print the 3 topics selected
      - If no selection: print reason (all on cooldown? below threshold?)

   c. RESEARCH STAGE:
      - Verify trigger file was created (if Spotlight was selected)
      - Trigger/wait for Research Agent processing
      - Print: processing duration, sources gathered, output word count
      - If Research Agent timed out or failed: print error and note that newsletter will proceed without Spotlight

   d. NEWSLETTER GENERATION STAGE:
      - Trigger the Newsletter Agent
      - Print which sections are included:
        - Spotlight: YES (thesis headline) / NO (reason)
        - Signals: YES ([count] items)
        - Radar: YES ([count] topics) / NO (insufficient emerging topics)
        - Scorecard: YES ([count] lookbacks) / NO (no resolved predictions)
      - Capture the full newsletter output

2. Validate the complete newsletter:
   
   SECTION ORDER CHECK:
   - If Spotlight present: it appears FIRST
   - Signals section follows Spotlight (or leads if no Spotlight)
   - Radar section follows Signals
   - Scorecard follows Radar (if present)
   - FAIL if sections are out of order
   
   SECTION BOUNDARY CHECK:
   - Each section is clearly delineated (verify section headers/separators between Signals, Radar, Scorecard)
   - No content from one section bleeding into another
   - No orphan headers or empty sections
   
   COMPLETENESS CHECK:
   - Newsletter has at least 2 sections (Signals should always be present)
   - Total word count is reasonable (800-2500 words for a full issue with Spotlight)
   - No placeholder text, no "TODO", no "[insert here]"
   - No raw JSON or structured data leaking into the output
   
   FORMATTING CHECK:
   - Spotlight follows prose format rules (no bullets, no sub-headers)
   - Signals items each have a brief analysis (not just headlines)
   - Radar items are each one topic + one sentence
   - Overall formatting is consistent

3. Test delivery channels:
   a. Telegram — send the newsletter to the test/dev Telegram channel
      - Verify it renders correctly in Telegram (no broken formatting, no truncation)
      - Print message length and whether it needed to be split
   b. Web archive — post to the web archive
      - Verify the page loads correctly
      - Verify all sections render properly in HTML
      - Print the archive URL

4. Test pipeline resilience — run 3 scenarios:
   
   a. HAPPY PATH (already done in step 1 — just verify it completed)
   
   b. RESEARCH AGENT FAILURE:
      - Stop/kill the Research Agent container before it completes
      - Run the Newsletter Agent anyway
      - Verify newsletter generates with Signals + Radar only
      - Verify no error messages leak into the newsletter content
      - Print: "Newsletter without Spotlight: [word count] words, [section count] sections"
   
   c. THIN DATA:
      - If possible, simulate a quiet week (few new items ingested)
      - Run the full pipeline
      - Verify the newsletter still generates even with fewer Signals items
      - Verify Radar handles having fewer emerging topics gracefully
      - Print: "Thin data newsletter: [signal count] signals, [radar count] radar items"

5. Measure pipeline timing:
   ```
   Pipeline Timing:
   - Scraping:    [X] minutes
   - Analysis:    [X] minutes
   - Research:    [X] minutes
   - Newsletter:  [X] minutes
   - Total:       [X] minutes
   
   Budget: [X] minutes used of 210 minute target (3.5 hours)
   ```

6. Print the FULL newsletter output so I can read it end to end:
   ```
   ════════════════════════════════════════════
   AGENTPULSE NEWSLETTER — TEST ISSUE
   ════════════════════════════════════════════
   
   [full newsletter content]
   
   ════════════════════════════════════════════
   ```

7. Print summary:
   ```
   === END-TO-END PIPELINE TEST ===
   Pipeline completed:          PASS/FAIL
   Total duration:              [X] minutes
   
   Sections generated:
   - Spotlight:                 PASS/SKIP (reason)
   - Signals:                  PASS/FAIL ([count] items)
   - Radar:                    PASS/SKIP ([count] items)
   - Scorecard:                PASS/SKIP (reason)
   
   Section order:               PASS/FAIL
   No content leakage:          PASS/FAIL
   No placeholder text:         PASS/FAIL
   Formatting consistent:       PASS/FAIL
   
   Delivery:
   - Telegram:                  PASS/FAIL
   - Web archive:               PASS/FAIL
   
   Resilience:
   - Happy path:                PASS/FAIL
   - Without Spotlight:         PASS/FAIL
   - Thin data:                 PASS/FAIL
   
   READY TO SHIP: YES/NO
   ```
```

---

## TEST 3C: Test Newsletter Quality Review

```
Generate 3 full test newsletters using the AgentPulse pipeline and present them for quality review. Write and run a Python script that:

This is a QUALITY review, not a functional test. The goal is to evaluate whether the enhanced newsletter is genuinely better than the pre-enhancement version and ready to ship to real readers.

1. Generate 3 newsletters with different conditions:

   NEWSLETTER A — Best case:
   - Use the current real data as-is
   - Full pipeline: Spotlight + Signals + Radar
   - This represents a normal week with good data

   NEWSLETTER B — Synthesis mode:
   - Force synthesis mode (set Spotlight threshold very high)
   - Full pipeline: Synthesis Spotlight + Signals + Radar
   - This tests whether synthesis issues are still strong

   NEWSLETTER C — No Spotlight:
   - Disable the Research Agent
   - Pipeline: Signals + Radar only
   - This tests whether the newsletter still feels complete without the deep dive

2. For each newsletter, capture and print:
   - The FULL newsletter text (every word, exactly as a reader would see it)
   - Word count per section
   - Total word count
   - Estimated read time (assume 200 words/minute)

3. Run comparative analysis:

   SPOTLIGHT COMPARISON (A vs B):
   - Print both Spotlight headlines side by side
   - Which feels more interesting? (automated check: which thesis has more tension words?)
   - Which has a more specific prediction?
   - Are they different enough to feel fresh? (no overlapping topic coverage)

   NEWSLETTER COMPLETENESS:
   - Does Newsletter C (no Spotlight) feel like a complete product? Or does it feel thin?
   - Compare word counts: A vs C — how much does the Spotlight add?
   - Does the flow from Signals → Radar still work without a Spotlight leading?

   OVERALL QUALITY:
   - For each newsletter, count: AI phrases found, hedge phrases found, bullet points in Spotlight
   - Are the Signals descriptions substantive (>15 words each) or just headlines?
   - Are the Radar items genuinely emerging (not already in Signals)?

4. Print all 3 newsletters with clear separators:
   ```
   ╔══════════════════════════════════════════════╗
   ║  NEWSLETTER A — FULL PIPELINE (Best Case)    ║
   ╠══════════════════════════════════════════════╣
   
   [full newsletter A]
   
   Word count: [X] | Read time: ~[X] min
   Sections: Spotlight ([X] words), Signals ([X] items, [X] words), Radar ([X] items)
   
   ╠══════════════════════════════════════════════╣
   ║  NEWSLETTER B — SYNTHESIS MODE               ║
   ╠══════════════════════════════════════════════╣
   
   [full newsletter B]
   
   Word count: [X] | Read time: ~[X] min
   Sections: Synthesis Spotlight ([X] words), Signals ([X] items, [X] words), Radar ([X] items)
   
   ╠══════════════════════════════════════════════╣
   ║  NEWSLETTER C — NO SPOTLIGHT                  ║
   ╠══════════════════════════════════════════════╣
   
   [full newsletter C]
   
   Word count: [X] | Read time: ~[X] min
   Sections: Signals ([X] items, [X] words), Radar ([X] items)
   
   ╚══════════════════════════════════════════════╝
   ```

5. Print quality summary:
   ```
   === NEWSLETTER QUALITY REVIEW ===
   
   |                    | Newsletter A | Newsletter B | Newsletter C |
   |--------------------|-------------|-------------|-------------|
   | Total words        | [X]         | [X]         | [X]         |
   | Read time          | ~[X] min    | ~[X] min    | ~[X] min    |
   | AI phrases found   | [X]         | [X]         | [X]         |
   | Hedge phrases      | [X]         | [X]         | [X]         |
   | Bullets in Spotlight| [X]        | [X]         | N/A         |
   | Signals substantive | [X]/[Y]    | [X]/[Y]     | [X]/[Y]     |
   | Radar unique       | YES/NO      | YES/NO      | YES/NO      |
   
   === MANUAL REVIEW QUESTIONS ===
   Read all 3 newsletters and answer:
   1. Would you subscribe to this newsletter based on Newsletter A?
   2. Would you forward the Spotlight to a colleague?
   3. Does Newsletter B (synthesis) feel as strong as A, or noticeably weaker?
   4. Does Newsletter C feel complete, or does the missing Spotlight leave a gap?
   5. Is the overall tone consistent across sections?
   6. Does the Radar section make you curious about what's coming next week?
   
   SHIP DECISION: Ready to send to real readers? YES / NO
   If NO, list what needs to improve before shipping.
   ```
```

---

## INTEGRATION SMOKE TEST: Full Phase 3

Run this AFTER all individual Phase 3 tests pass.

```
Final integration validation before shipping the first enhanced AgentPulse newsletter. Write and run a Python script that:

1. Run the COMPLETE pipeline exactly as it would run in production:
   - Use the real cron-triggered flow (or simulate it exactly)
   - Do NOT manually intervene at any stage
   - Let every component run with production settings and timeouts
   - Log everything

2. Verify production readiness:
   
   PIPELINE HEALTH:
   - All scrapers completed without errors (general + thought leader)
   - Analyst cycle completed and logged topic count and lifecycle transitions
   - Spotlight selection ran and made a decision (selected topic OR synthesis OR skip)
   - Research Agent either completed or timed out gracefully
   - Newsletter Agent generated the full newsletter
   - Delivery to Telegram succeeded
   - Web archive updated
   
   DATA INTEGRITY:
   - research_queue entry has status = "completed" (or "failed" with error logged)
   - spotlight_history has entry for this issue (if Research Agent succeeded)
   - No orphan trigger files in queue directory
   - No test data from previous phases leaking into production output (check for issue_number 997, 998, 999)
   
   CONTENT SANITY:
   - Newsletter contains no test/debug text
   - No raw JSON in the output
   - No "[TODO]" or "[placeholder]" text
   - Word count is in normal range (500-2500)
   - All links in the newsletter are valid URLs (not localhost or test URLs)

3. Compare with previous newsletter:
   - Pull the most recent pre-enhancement newsletter
   - Print side by side: section count, word count, topic coverage
   - The enhanced version should have MORE sections (Spotlight, Radar) and MORE depth

4. Final checklist:
   ```
   === PRODUCTION READINESS CHECK ===
   
   Pipeline execution:
   - Scrapers:              ✓/✗
   - Analyst:               ✓/✗
   - Spotlight selection:   ✓/✗ — [topic or synthesis or skip]
   - Research Agent:        ✓/✗ — [completed in Xs or timed out]
   - Newsletter generation: ✓/✗
   - Telegram delivery:     ✓/✗
   - Web archive:           ✓/✗
   
   Data integrity:
   - Queue state clean:     ✓/✗
   - No test data leaked:   ✓/✗
   - No orphan files:       ✓/✗
   
   Content quality:
   - No debug/test text:    ✓/✗
   - No raw data leaked:    ✓/✗
   - Word count normal:     ✓/✗ ([X] words)
   - Links valid:           ✓/✗
   
   Comparison with pre-enhancement:
   - More sections:         ✓/✗ ([X] vs [Y])
   - More depth:            ✓/✗ ([X] words vs [Y] words)
   
   ═══════════════════════════════
   SHIP FIRST ENHANCED NEWSLETTER: YES / NO
   ═══════════════════════════════
   
   If NO, list blocking issues:
   - [issue 1]
   - [issue 2]
   ```
```
