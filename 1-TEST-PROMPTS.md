# Phase 1 — Test Prompts

Run each of these prompts separately in Cursor after the corresponding Phase 1 task is complete.

---

## TEST 1B: Schema Verification

```
Test the new Supabase tables for the AgentPulse Spotlight and Scorecard features. Write and run a Python test script that:

1. Connects to Supabase using our existing credentials/client setup
2. Tests research_queue:
   - Insert a test row with all fields populated (use realistic fake data: topic_id="test-topic", topic_name="Test Topic", priority_score=0.75, velocity=0.6, source_diversity=0.8, lifecycle_phase="debating", mode="spotlight", status="queued", context_payload as a JSON object with a few keys, issue_number=999)
   - Read it back and verify all fields match
   - Update status to "in_progress" and verify
   - Delete the test row
3. Tests spotlight_history:
   - Insert a test row referencing the research_queue test row (create it first, delete both after). Populate all fields: topic_id, topic_name, issue_number=999, thesis="Test thesis", evidence="Test evidence", counter_argument="Test counter", prediction="Test prediction", builder_implications="Test implications", full_output="Full test output", sources_used as a JSONB array with one object
   - Read it back, verify all fields including the JSONB sources_used
   - Delete the test row
4. Tests predictions:
   - Insert a test row referencing a spotlight_history test row. Populate: topic_id, prediction_text="Test prediction text", issue_number=999, status="open"
   - Update status to "flagged", set evidence_notes and flagged_at
   - Update status to "confirmed", set resolution_notes and resolved_at
   - Verify each status transition
   - Delete the test row
5. Tests spotlight_cooldown view:
   - Insert 2 spotlight_history rows with issue_number=999 and issue_number=990
   - Query spotlight_cooldown view
   - Verify issue 999 has on_cooldown=true and issue 990 has on_cooldown=false
   - Clean up test rows
6. Print a summary: PASS/FAIL for each table and the view

Clean up ALL test data after running (delete any rows with issue_number=999 or 990). The script should never leave test data behind.
```

---

## TEST 1A: Source Ingestion

```
Test the thought leader source ingestion for AgentPulse. Write and run a Python test script that:

1. Triggers a manual run of the thought leader scrapers (or calls the scraping functions directly)
2. After scraping completes, query the database and verify:
   a. Items exist with source_tier = 'thought_leader' for each of the 6 sources:
      - DeepLearning.AI (Andrew Ng)
      - Simon Willison's blog
      - Latent Space
      - Swyx's blog
      - LangChain blog (Harrison Chase)
      - Ethan Mollick (One Useful Thing)
   b. For each source, print: source_name, number of items ingested, most recent item title, most recent ingested_at timestamp
   c. Verify each item has the required fields: source_name, source_tier, title, content_summary, url, published_at, topics_detected, ingested_at
   d. Check that source_tier is set to 'thought_leader' (not 'institutional' or 'community')
3. Test dual routing:
   a. Verify the Analyst can query these items in its normal scan (query them the same way the Analyst does)
   b. Verify items can be filtered by source_tier='thought_leader' specifically (this is how the Research Agent will query them)
4. Test deduplication:
   a. Run the scrapers again on the same data
   b. Verify no duplicate items were created (count before and after should match)
5. Test error handling:
   a. If possible, simulate one feed being unavailable (e.g., temporarily point one source URL to a bad address)
   b. Verify the other sources still ingest successfully and the pipeline doesn't crash
6. Print a summary table:

   | Source | Items | Latest Item | Status |
   |--------|-------|-------------|--------|
   | DeepLearning.AI | 5 | "Title..." | PASS |
   | ... | ... | ... | ... |

   Plus: Dual routing test: PASS/FAIL, Dedup test: PASS/FAIL, Error handling test: PASS/FAIL
```

---

## TEST 1C: Research Agent Prompt

```
Test the Research Agent system prompt quality for AgentPulse. Write and run a Python script that:

1. Takes a real trending topic from our Analyst's current data. Query the topic lifecycle tracker and pick the highest-velocity topic currently in "debating" or "building" phase. If no good candidate exists, use the topic with the highest velocity regardless of phase.

2. Build a realistic context payload for that topic:
   - Pull all recent items mentioning this topic from general sources (last 7 days)
   - Pull all recent items from thought_leader sources on this topic (last 14 days)
   - Format this as the context_payload the Research Agent would receive

3. Call the LLM (Anthropic Claude) with our Research Agent system prompt and this context. Capture the full response.

4. Parse the response and validate the output structure:
   - Has a "thesis" field that is a single sentence (not a paragraph)
   - Has an "evidence" field (at least 100 words)
   - Has a "counter_argument" field (at least 50 words)
   - Has a "prediction" field that contains a timeframe (look for words like "month", "quarter", "Q1-Q4", "week", "2025", "2026", or specific dates)
   - Has a "builder_implications" field (at least 30 words)
   - Has a "key_sources" field with at least 2 source URLs

5. Run automated quality checks on the content:
   - THESIS CHECK: Does the thesis contain a tension word ("but", "however", "despite", "yet", "although")? Flag if missing.
   - HEDGE CHECK: Scan for hedging phrases ("it remains to be seen", "time will tell", "it could go either way", "it's worth noting", "in the rapidly evolving"). Flag any found.
   - AI VOICE CHECK: Scan for AI-sounding phrases ("in the rapidly evolving landscape", "it's important to note", "as we navigate", "at the end of the day", "a myriad of"). Flag any found.
   - SPECIFICITY CHECK: Does the prediction contain a number, a named entity, or a specific timeframe? Flag if none found.
   - BULLET CHECK: Does any section contain bullet points or numbered lists? Flag if found.

6. Print the full output so I can read it, followed by a quality report:

   ```
   === RESEARCH AGENT TEST OUTPUT ===
   Topic: [topic name]
   Phase: [lifecycle phase]
   Sources used: [count general] general, [count thought_leader] thought leader

   THESIS: [full thesis]
   EVIDENCE: [full evidence]  
   COUNTER-ARGUMENT: [full counter-argument]
   PREDICTION: [full prediction]
   BUILDER IMPLICATIONS: [full implications]

   === QUALITY CHECKS ===
   Structure: PASS/FAIL (list any missing fields)
   Thesis tension: PASS/FAIL
   Hedge language: PASS/FAIL (list any found)
   AI voice: PASS/FAIL (list any found)
   Prediction specificity: PASS/FAIL
   No bullet points: PASS/FAIL
   
   === MANUAL REVIEW NEEDED ===
   Read the output above and ask yourself:
   1. Would I forward this to a smart friend in AI? 
   2. Is the thesis specific enough to be wrong?
   3. Does the counter-argument make me think "huh, maybe they're wrong"?
   4. Would a builder change their plans based on the implications?
   ```

Do NOT iterate on the prompt in this test — just run it once and show me the results so I can evaluate quality myself.
```

---

## TEST 1D: Radar Section

```
Test the Radar section addition to the AgentPulse Newsletter Agent. Write and run a Python script that:

1. Query the topic lifecycle tracker for topics in "emerging" phase, ordered by velocity descending:
   - Print all emerging topics found: topic_name, velocity, source count
   - If fewer than 3, also query "early debating" phase topics as fallback
   - Print how many total Radar candidates are available

2. Check for overlap prevention:
   - Query what would be in the current Signals section
   - Verify none of the Radar candidates overlap with Signals topics
   - Print any overlaps found

3. Generate a test Radar section:
   - Take the top 3-4 candidates
   - Run them through the Newsletter Agent's Radar generation (the part that creates the one-sentence "why it's worth watching" descriptions)
   - Print the generated Radar section exactly as it would appear in the newsletter

4. Validate the format:
   - Each item should be: bold topic name + one sentence (not two, not a paragraph)
   - Count the words in each description — flag any over 30 words (they should be punchy)
   - Verify there are 3-4 items (not more, not fewer unless insufficient data)

5. Test the fallback behavior:
   - Temporarily filter out all "emerging" topics (simulate empty state)
   - Verify it falls back to early "debating" phase topics
   - If still not enough topics, verify the section is skipped entirely (returns None or empty)

6. Trigger a full test newsletter generation and verify:
   - The Radar section appears in the output
   - It's positioned after Signals
   - The formatting is correct in the full newsletter context

7. Print summary:
   ```
   === RADAR SECTION TEST ===
   Emerging topics available: [count]
   Fallback topics used: yes/no
   Candidates after dedup with Signals: [count]
   
   Generated Radar:
   [the actual rendered section]
   
   Format checks:
   - Item count (3-4): PASS/FAIL
   - All items single sentence: PASS/FAIL  
   - No items over 30 words: PASS/FAIL
   - No overlap with Signals: PASS/FAIL
   - Fallback behavior: PASS/FAIL
   - Appears in full newsletter: PASS/FAIL
   ```
```

---

## INTEGRATION SMOKE TEST: Full Phase 1

Run this AFTER all individual tests pass.

```
Run a full AgentPulse pipeline smoke test to verify all Phase 1 additions work together. This is NOT a full newsletter generation — it's a quick check that the pieces connect.

Write and run a Python script that:

1. Check source ingestion:
   - Query for thought_leader sources ingested in the last 24 hours
   - Print count per source
   - FAIL if any source has 0 items

2. Check Analyst awareness:
   - Run a lightweight Analyst scan (or simulate one) on recent items
   - Verify thought_leader items are included in the scan with Tier 1.5 weighting
   - FAIL if thought_leader items are not weighted correctly

3. Check schema readiness:
   - Insert and immediately delete a test row in research_queue
   - Insert and immediately delete a test row in spotlight_history  
   - Insert and immediately delete a test row in predictions
   - FAIL if any insert/delete errors

4. Check Radar generation:
   - Query emerging topics
   - Generate Radar section
   - FAIL if Radar returns empty when emerging topics exist

5. Check Research Agent prompt (dry run):
   - Build a context payload from real data
   - Call the Research Agent LLM with the prompt
   - Verify output has all required fields
   - FAIL if output structure is wrong

6. Print final summary:
   ```
   === PHASE 1 INTEGRATION SMOKE TEST ===
   Thought leader ingestion:  PASS/FAIL
   Analyst sees new sources:  PASS/FAIL
   Schema operational:        PASS/FAIL
   Radar generation:          PASS/FAIL
   Research Agent prompt:     PASS/FAIL
   
   READY FOR PHASE 2: YES/NO
   ```

If any test fails, print the specific error so I can debug it. Do not continue to Phase 2 until all tests pass.
```
