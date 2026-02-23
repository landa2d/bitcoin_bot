# Phase 4 — Test Prompts

Run each of these prompts separately in Cursor after the corresponding Phase 4 task is complete.

---

## TEST 4A: Prediction Extraction and Storage

```
Test the prediction extraction system for AgentPulse Scorecard. Write and run a Python test script that:

1. Setup — ensure test data exists:
   - Query spotlight_history for the most recent entry
   - If none exists, insert a realistic test entry with issue_number=996, a real thesis, and a prediction like: "We predict at least two major enterprise frameworks will fork MCP's core protocol by mid-2025, creating a fragmented but more resilient ecosystem."
   - Print the spotlight_id and the raw prediction text we're working with

2. Test extraction on a GOOD prediction:
   - Run the prediction extraction function on the spotlight_history entry
   - Print the extracted prediction_text
   - Verify it's a SINGLE sentence (FAIL if more than 1 sentence)
   - Verify it contains a timeframe (scan for: month names, Q1-Q4, year numbers, "by [date]", "within [X] days/weeks/months")
   - Verify it contains a specific measurable outcome (not just "will grow" or "will change")
   - Verify it was stored in the predictions table with:
     - spotlight_id linking to the correct spotlight_history entry
     - topic_id matching the spotlight's topic_id
     - issue_number matching the spotlight's issue_number
     - status = "open"
     - created_at is set
   - Print the predictions row

3. Test extraction sharpening:
   - Create a test spotlight_history entry with a VAGUE prediction:
     "This trend will likely continue to gain momentum in the coming months and could have significant implications for the industry."
   - Run the extraction
   - Print the extracted prediction
   - Verify the extraction prompt sharpened it — it should be more specific than the input
   - The extracted version should have a timeframe and measurable outcome even if the original didn't
   - WARN if the extracted version is still vague (no timeframe, no specific outcome)
   - Clean up the test entry

4. Test extraction on synthesis mode Spotlight:
   - Create a test spotlight_history entry with mode="synthesis" and a prediction that references 3 topics:
     "The convergence of local model deployment, MCP standardization, and enterprise agent budgets will produce a dominant middleware player within 6 months. Meanwhile, open-source alternatives will capture the long-tail of smaller agent deployments."
   - Run the extraction
   - Verify only ONE prediction was extracted (not two, even though the source has two claims)
   - Verify the extracted prediction is the PRIMARY claim (the one tying topics together)
   - Print: original prediction, extracted prediction, number of predictions stored
   - Clean up the test entry

5. Test idempotency:
   - Run the extraction on the same spotlight_history entry twice
   - Verify only ONE prediction row exists (not duplicated)
   - Print the count of predictions for this spotlight_id

6. Test missing prediction:
   - Create a test spotlight_history entry with an empty prediction field (or null)
   - Run the extraction
   - Verify it doesn't crash
   - Verify no predictions row was created
   - Verify a warning was logged
   - Clean up

7. Test the extraction runs at the right time:
   - Verify the extraction is wired to run AFTER newsletter generation
   - Verify it doesn't block or delay newsletter delivery
   - Print the timing: newsletter_generated_at vs prediction_extracted_at

8. Clean up ALL test data:
   - Delete predictions with issue_number in (996, or any test issue numbers used)
   - Delete test spotlight_history entries
   - Verify no test data remains

9. Print summary:
   ```
   === PREDICTION EXTRACTION TEST ===
   
   Good prediction extraction:
   - Original:  "[raw prediction from spotlight]"
   - Extracted:  "[sharpened single-sentence prediction]"
   - Has timeframe:          PASS/FAIL
   - Has measurable outcome: PASS/FAIL
   - Stored correctly:       PASS/FAIL
   
   Sharpening test:
   - Input was vague:        YES
   - Output is sharper:      PASS/FAIL/WARN
   - Extracted: "[extracted text]"
   
   Synthesis mode:
   - Multiple claims in source: YES
   - Only 1 extracted:       PASS/FAIL
   - Primary claim captured: PASS/FAIL
   
   Other checks:
   - Idempotency:            PASS/FAIL
   - Missing prediction:     PASS/FAIL (handled gracefully)
   - Timing (post-newsletter): PASS/FAIL
   - Cleanup:                PASS/FAIL
   ```
```

---

## TEST 4B: Prediction Monitoring in Analyst Cycle

```
Test the prediction monitoring system in the AgentPulse Analyst. Write and run a Python test script that:

1. Setup — create test predictions:
   
   a. CONFIRMING prediction:
   - Create a spotlight_history entry and prediction for a topic that HAS new confirming evidence in recent data
   - Pick a real topic that the Analyst has recent items for
   - Prediction text example: "[Topic X] will see major enterprise adoption by Q2 2025"
   - Status: "open"
   - Print the prediction and the recent evidence available
   
   b. CONTRADICTING prediction:
   - Create a prediction for something that recent data contradicts
   - Use a prediction that's clearly being disproven by current events
   - Status: "open"
   - Print the prediction
   
   c. NEUTRAL prediction:
   - Create a prediction for a topic with recent mentions but nothing decisive
   - Status: "open"
   - Print the prediction
   
   d. STALE prediction:
   - Create a prediction with created_at = 7 months ago (past the 180-day expiry)
   - Status: "open"
   - Print the prediction

2. Run the prediction monitoring step:
   - Trigger the Analyst's prediction monitoring function
   - Let it assess all open predictions against recent data
   - Print the LLM assessment for each prediction:
     - Direction: confirms / contradicts / neutral
     - Significance: low / medium / high
     - Evidence summary

3. Verify correct behavior for each prediction:
   
   a. CONFIRMING prediction:
   - If significance is HIGH: status should change to "flagged", evidence_notes populated, flagged_at set
   - If significance is MEDIUM/LOW: status should remain "open" (only HIGH triggers flagging)
   - Print: status before, assessment, status after
   
   b. CONTRADICTING prediction:
   - Same logic — only flag on HIGH significance
   - Print: status before, assessment, status after
   
   c. NEUTRAL prediction:
   - Status should remain "open" regardless of significance (neutral = no action)
   - Verify no evidence_notes were added
   - Print: status before, assessment, status after
   
   d. STALE prediction:
   - Should be auto-expired: status = "expired"
   - Should NOT be assessed by the LLM (save tokens)
   - Print: status before, status after

4. Verify the monitoring does NOT auto-resolve:
   - Even for HIGH significance confirming evidence, status should be "flagged" NOT "confirmed"
   - Even for HIGH significance contradicting evidence, status should be "flagged" NOT "refuted"
   - Resolution requires manual review (or Newsletter Agent in Phase 4C)
   - FAIL if any prediction was auto-resolved

5. Test evidence accumulation:
   - Run the monitoring step a SECOND time with the same predictions
   - For already-flagged predictions with new evidence: verify evidence_notes is APPENDED to, not overwritten
   - Print evidence_notes before and after second run

6. Test performance with many predictions:
   - Insert 20 test predictions with status="open"
   - Run the monitoring step
   - Measure execution time
   - Verify it completes within a reasonable time (WARN if >60 seconds, FAIL if >120 seconds)
   - Verify all 20 were assessed (or the max 20 limit was applied)
   - Print: predictions assessed, total time, average time per prediction

7. Test that monitoring doesn't block Analyst:
   - Verify the monitoring runs AFTER the normal scan and selection heuristic
   - Verify that if monitoring fails/crashes, the rest of the Analyst output (topic updates, Spotlight selection) is not affected
   - Simulate a monitoring failure (e.g., LLM timeout) and verify the Analyst cycle still completed its other tasks

8. Clean up ALL test data:
   - Delete all test predictions
   - Delete all test spotlight_history entries
   - Verify no test data remains

9. Print summary:
   ```
   === PREDICTION MONITORING TEST ===
   
   Assessment results:
   | Prediction | Direction | Significance | Status Change | Correct? |
   |-----------|-----------|-------------|---------------|----------|
   | Confirming | confirms | high/med/low | open→flagged/open | PASS/FAIL |
   | Contradicting | contradicts | high/med/low | open→flagged/open | PASS/FAIL |
   | Neutral | neutral | low | open→open | PASS/FAIL |
   | Stale | N/A (expired) | N/A | open→expired | PASS/FAIL |
   
   Behavior checks:
   - No auto-resolution:        PASS/FAIL
   - Evidence accumulation:     PASS/FAIL
   - Performance (20 preds):    PASS/FAIL ([X]s total, [Y]s avg)
   - Doesn't block Analyst:     PASS/FAIL
   - Stale expiry:              PASS/FAIL
   - Cleanup:                   PASS/FAIL
   ```
```

---

## TEST 4C: Scorecard Generation

```
Test the Scorecard "Looking Back" generation in the AgentPulse Newsletter Agent. Write and run a Python test script that:

1. Setup — create resolved predictions:
   
   a. CONFIRMED prediction:
   - Create spotlight_history entry (issue_number=993) with thesis about a real topic
   - Create prediction: specific, with timeframe, status="confirmed"
   - Set resolution_notes: "LangChain shipped their own MCP variant in April, AWS announced a compatible implementation in May."
   - Set resolved_at
   
   b. REFUTED prediction:
   - Create spotlight_history entry (issue_number=991) 
   - Create prediction: specific claim that turned out wrong, status="refuted"
   - Set resolution_notes: "Adoption stayed flat at ~5% through Q2. Enterprise interest was lower than community enthusiasm suggested."
   - Set resolved_at
   
   c. PARTIALLY CORRECT prediction:
   - Create spotlight_history entry (issue_number=990)
   - Create prediction: status="partially_correct"
   - Set resolution_notes: "The middleware consolidation happened but at the model layer first, not the agent layer as we predicted."
   - Set resolved_at
   
   d. ALREADY SCORECARDED prediction:
   - Create a prediction with status="confirmed" AND scorecard_issue already set (e.g., scorecard_issue=994)
   - This one should NOT appear in a new Scorecard
   
   e. OPEN prediction (not resolved):
   - Create a prediction with status="open"
   - This one should NOT appear in the Scorecard

2. Test Scorecard generation:
   - Call the Newsletter Agent's Scorecard generation function for issue_number=995
   - Verify it finds the resolved predictions (a, b, c) but NOT (d) already scorecarded or (e) open
   - Print the number of lookbacks generated
   - Verify max 2 lookbacks (if 3 are available, it should pick the 2 most interesting/recent)

3. Validate each generated blurb:
   
   FORMAT CHECK (for each blurb):
   - Starts with a bold "Looking Back: [headline]"
   - Is 3-4 sentences (count sentences — FAIL if fewer than 3 or more than 5)
   - References the original issue number ("In Issue #XX, we predicted...")
   - Contains the original prediction claim (paraphrased is fine)
   - Contains what actually happened
   - Contains an honest assessment
   - Total word count per blurb: 40-100 words (WARN if outside range)
   
   TONE CHECK (for each blurb):
   - CONFIRMED blurb: states it plainly, no gloating (scan for "we nailed it", "as we correctly predicted", "we were right all along" — FAIL if found)
   - REFUTED blurb: admits it directly (scan for "we got this wrong" or similar honest admission — PASS if found. Scan for defensive language: "the situation evolved differently", "circumstances changed", "couldn't have predicted" — FAIL if found)
   - PARTIALLY CORRECT blurb: specific about what hit and what missed (should contain both a positive and negative assessment — FAIL if only positive or only negative)
   - None of the blurbs contain AI phrases or hedging language

4. Test Scorecard marking:
   - After generation, verify predictions (a, b, or c — whichever were used) now have scorecard_issue=995
   - Verify they won't appear in the NEXT Scorecard (run generation for issue_number=996 and verify these predictions are excluded)

5. Test Scorecard placement in newsletter:
   - Generate a full test newsletter that includes a Scorecard
   - Verify Scorecard section appears AFTER Radar
   - Verify the section header is present
   - Print the newsletter structure:
     - Section 1: [name] at position [X]
     - Section 2: [name] at position [X]
     - Section 3: [name] at position [X]
     - Section 4: [name] at position [X]

6. Test no Scorecard scenario:
   - Delete all resolved predictions (or mark them all as already scorecarded)
   - Run Newsletter Agent generation
   - Verify Scorecard section is completely absent
   - Verify no empty "Looking Back" header appears
   - Verify newsletter ends cleanly after Radar

7. Print all generated blurbs so I can evaluate quality:
   ```
   === SCORECARD BLURBS ===
   
   ─── BLURB 1 (confirmed) ───
   [full blurb text]
   
   Sentences: [X] | Words: [X]
   References issue: PASS/FAIL
   States outcome: PASS/FAIL
   Honest assessment: PASS/FAIL
   No gloating: PASS/FAIL
   
   ─── BLURB 2 (refuted) ───
   [full blurb text]
   
   Sentences: [X] | Words: [X]
   References issue: PASS/FAIL
   Admits being wrong: PASS/FAIL
   No defensive language: PASS/FAIL
   
   ─── BLURB 3 (partially_correct) ───
   [full blurb text]
   
   Sentences: [X] | Words: [X]
   What hit + what missed: PASS/FAIL
   Balanced assessment: PASS/FAIL
   ```

8. Clean up ALL test data:
   - Delete test predictions (all test issue numbers)
   - Delete test spotlight_history entries
   - Verify no test data remains

9. Print summary:
   ```
   === SCORECARD GENERATION TEST ===
   
   Blurb generation:
   - Resolved predictions found:     [X]
   - Blurbs generated:               [X] (max 2)
   - Already-scorecarded excluded:   PASS/FAIL
   - Open predictions excluded:      PASS/FAIL
   
   Format checks:
   - Bold headline:                  PASS/FAIL
   - 3-4 sentences each:            PASS/FAIL
   - References original issue:     PASS/FAIL
   - Word count in range:           PASS/FAIL
   
   Tone checks:
   - Confirmed: no gloating:        PASS/FAIL
   - Refuted: honest admission:     PASS/FAIL
   - Partial: balanced assessment:  PASS/FAIL
   - No AI phrases:                 PASS/FAIL
   
   Integration:
   - Scorecard marking:             PASS/FAIL
   - No double-inclusion:           PASS/FAIL
   - Newsletter placement:          PASS/FAIL (after Radar)
   - No-scorecard graceful:         PASS/FAIL
   - Cleanup:                       PASS/FAIL
   ```
```

---

## INTEGRATION SMOKE TEST: Full Phase 4

Run this AFTER all individual Phase 4 tests pass.

```
Run a full Phase 4 integration test for AgentPulse that validates the complete Scorecard lifecycle: prediction extraction → monitoring → resolution → newsletter inclusion. Write and run a Python script that:

1. Simulate the complete prediction lifecycle:

   CYCLE 1 — Prediction is born:
   - Use an existing spotlight_history entry (or create one with realistic data)
   - Run the prediction extraction (4A)
   - Verify a prediction was created in the predictions table with status="open"
   - Print: "Prediction created: [prediction_text]"

   CYCLE 2 — Monitoring detects evidence:
   - Run the Analyst prediction monitoring (4B)
   - Check if any evidence was found for our prediction
   - If evidence found and significant: verify prediction was flagged
   - If no evidence: that's fine, print "No significant evidence yet" and manually flag it for testing:
     - Update status to "flagged"
     - Add evidence_notes manually with realistic text
   - Print: "Prediction status: [status], evidence: [summary]"

   CYCLE 3 — Prediction is resolved:
   - Manually resolve the prediction (simulate human review):
     - Update status to "confirmed" (or "refuted" or "partially_correct")
     - Add resolution_notes
     - Set resolved_at
   - Print: "Prediction resolved as: [status]"

   CYCLE 4 — Scorecard appears in newsletter:
   - Run the Newsletter Agent including Scorecard generation (4C)
   - Verify the Scorecard section appears in the newsletter
   - Verify it contains a lookback blurb for our resolved prediction
   - Verify the prediction is now marked with a scorecard_issue number
   - Print the Scorecard blurb

2. Verify the lifecycle is complete:
   ```
   Prediction Lifecycle:
   1. Created (4A):     ✓ — "[prediction_text]"
   2. Monitored (4B):   ✓ — [flagged/no evidence yet]
   3. Resolved:         ✓ — [confirmed/refuted/partial]
   4. In Scorecard (4C): ✓ — appears in issue #[X]
   5. Not repeated:     ✓ — excluded from next Scorecard
   ```

3. Verify integration with the full pipeline:
   - The prediction extraction doesn't interfere with newsletter delivery
   - The monitoring doesn't slow down the Analyst cycle
   - The Scorecard generation doesn't break the newsletter if no predictions are resolved
   - All database entries have correct foreign key relationships

4. Test the steady state (what it looks like after several issues):
   - Insert 5 predictions across different issues (mix of open, flagged, confirmed, refuted, expired)
   - Run the monitoring step — verify it only assesses "open" ones and skips resolved/expired
   - Run the Scorecard generation — verify it only picks up newly resolved ones
   - Print the state of all 5 predictions after the run

5. Print summary:
   ```
   === PHASE 4 INTEGRATION TEST ===
   
   Lifecycle:
   - Extraction (4A):         PASS/FAIL
   - Monitoring (4B):         PASS/FAIL
   - Scorecard gen (4C):      PASS/FAIL
   - No repeat in Scorecard:  PASS/FAIL
   
   Pipeline integration:
   - No delivery interference: PASS/FAIL
   - No Analyst slowdown:     PASS/FAIL
   - Graceful with no data:   PASS/FAIL
   - Foreign keys intact:     PASS/FAIL
   
   Steady state (5 predictions):
   - Open assessed:           [X] of [Y]
   - Resolved skipped:        PASS/FAIL
   - Expired skipped:         PASS/FAIL
   - Scorecard picks correct: PASS/FAIL
   
   PHASE 4 COMPLETE: YES/NO
   
   ═══════════════════════════════════════
   FULL AGENTPULSE ENHANCEMENT COMPLETE: YES/NO
   ═══════════════════════════════════════
   ```

Clean up all test data except for any predictions that are genuinely useful for the first real Scorecard.
```
