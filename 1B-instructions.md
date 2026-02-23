# 1B — What to Run Where

## STEP 1: Supabase (you do this manually)

1. Go to your Supabase Dashboard
2. Click **SQL Editor** in the left sidebar
3. Click **New Query**
4. Paste the ENTIRE contents of `1B-supabase-sql.sql`
5. Click **Run**
6. You should see the verification output at the bottom:

```
table_name         | columns
-------------------|--------
research_queue     | 13
spotlight_history  | 13
predictions        | 12
```

If you see those numbers, all tables were created correctly.

7. **Check RLS**: Go to **Authentication → Policies** in the dashboard. 
   - If your existing tables (like your sources/topics tables) have RLS enabled, uncomment the RLS section in the SQL and run it separately.
   - If your existing tables DON'T have RLS (you're using service_role key), skip it.

## STEP 2: Cursor (for application code awareness)

Give Cursor this prompt so it knows the schema exists and can reference it when building Phase 2:

---

**Prompt for Cursor:**

```
The following Supabase tables have been created for the AgentPulse Spotlight and Scorecard features. 
Add these table definitions to our database schema documentation / types so the application code 
can reference them.

Tables:

1. research_queue
   - id: UUID (PK)
   - topic_id: TEXT
   - topic_name: TEXT
   - priority_score: FLOAT
   - velocity: FLOAT
   - source_diversity: FLOAT
   - lifecycle_phase: TEXT (emerging/debating/building/mature/declining)
   - context_payload: JSONB
   - mode: TEXT (spotlight/synthesis)
   - status: TEXT (queued/in_progress/completed/failed)
   - issue_number: INTEGER
   - created_at: TIMESTAMPTZ
   - started_at: TIMESTAMPTZ
   - completed_at: TIMESTAMPTZ

2. spotlight_history
   - id: UUID (PK)
   - research_queue_id: UUID (FK → research_queue.id)
   - topic_id: TEXT
   - topic_name: TEXT
   - issue_number: INTEGER
   - mode: TEXT (spotlight/synthesis)
   - thesis: TEXT
   - evidence: TEXT
   - counter_argument: TEXT
   - prediction: TEXT
   - builder_implications: TEXT
   - full_output: TEXT
   - sources_used: JSONB
   - created_at: TIMESTAMPTZ

3. predictions
   - id: UUID (PK)
   - spotlight_id: UUID (FK → spotlight_history.id)
   - topic_id: TEXT
   - prediction_text: TEXT
   - issue_number: INTEGER
   - status: TEXT (open/flagged/confirmed/refuted/partially_correct/expired)
   - evidence_notes: TEXT
   - resolution_notes: TEXT
   - scorecard_issue: INTEGER
   - flagged_at: TIMESTAMPTZ
   - resolved_at: TIMESTAMPTZ
   - created_at: TIMESTAMPTZ

4. View: spotlight_cooldown
   - topic_id, topic_name, issue_number, created_at, on_cooldown (boolean)
   - Topics spotlighted in the last 4 issues have on_cooldown = true

Add type definitions and any Supabase client helpers needed to interact with these tables 
following our existing patterns.
```

---

## STEP 3: Verify in Cursor

After Cursor generates the types/helpers, verify:
- [ ] Type definitions match the schema above
- [ ] Supabase client can query each table without errors
- [ ] The helpers follow the same patterns as your existing database code

## Summary

| Action | Where | Time |
|--------|-------|------|
| Create tables, indexes, view | Supabase SQL Editor | 2 minutes |
| Check RLS | Supabase Dashboard | 1 minute |
| Generate types/helpers | Cursor | ~10 minutes |

**Total: ~15 minutes. Then move on to Phase 1A/1C/1D in Cursor.**
