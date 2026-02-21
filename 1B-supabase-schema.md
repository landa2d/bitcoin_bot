# 1B — Supabase Schema Additions

## Phase
Phase 1 — Foundation

## Parallel/Sequential
**PARALLEL** — Can run simultaneously with 1A, 1C, 1D

## Dependencies
None

## Prompt

Add the following Supabase tables to support the Spotlight, Research Agent, and Scorecard features in AgentPulse.

### Tables to Create

#### `research_queue`
The handoff mechanism between the Analyst and the Research Agent. Analyst writes here, Research Agent reads.

```sql
-- Topics selected by the Analyst for deep research
research_queue (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic_id        TEXT NOT NULL,              -- reference to existing topic tracking
  topic_name      TEXT NOT NULL,
  priority_score  FLOAT NOT NULL,             -- velocity × source_diversity × lifecycle_bonus
  velocity        FLOAT,                      -- rate of new mentions
  source_diversity FLOAT,                     -- how many source tiers mention it
  lifecycle_phase TEXT,                        -- emerging / debating / building / mature / declining
  context_payload JSONB,                      -- key sources, recent mentions summary, relevant quotes
  mode            TEXT DEFAULT 'spotlight',    -- 'spotlight' or 'synthesis' (fallback mode)
  status          TEXT DEFAULT 'queued',       -- queued / in_progress / completed / failed
  issue_number    INTEGER,                    -- target newsletter issue
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  started_at      TIMESTAMPTZ,
  completed_at    TIMESTAMPTZ
)
```

#### `spotlight_history`
Stores completed Spotlight outputs for the Newsletter Agent and for Scorecard tracking.

```sql
-- Completed Spotlight analyses
spotlight_history (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  research_queue_id UUID REFERENCES research_queue(id),
  topic_id          TEXT NOT NULL,
  topic_name        TEXT NOT NULL,
  issue_number      INTEGER NOT NULL,
  mode              TEXT DEFAULT 'spotlight',   -- 'spotlight' or 'synthesis'
  thesis            TEXT NOT NULL,              -- one-sentence sharp claim
  evidence          TEXT NOT NULL,              -- supporting evidence paragraphs
  counter_argument  TEXT NOT NULL,              -- steelman against the thesis
  prediction        TEXT NOT NULL,              -- forward-looking prediction
  builder_implications TEXT,                   -- "so what" for builders
  full_output       TEXT NOT NULL,              -- complete formatted Spotlight text
  sources_used      JSONB,                     -- array of source references used
  created_at        TIMESTAMPTZ DEFAULT NOW()
)
```

#### `predictions`
Tracks the falsifiable predictions extracted from Spotlights for Scorecard accountability.

```sql
-- Extracted predictions for tracking and accountability
predictions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  spotlight_id    UUID REFERENCES spotlight_history(id),
  topic_id        TEXT NOT NULL,
  prediction_text TEXT NOT NULL,               -- the specific falsifiable claim
  issue_number    INTEGER NOT NULL,            -- when this prediction was made
  status          TEXT DEFAULT 'open',         -- open / flagged / confirmed / refuted / partially_correct
  evidence_notes  TEXT,                        -- accumulated evidence for/against
  resolution_notes TEXT,                       -- final assessment when resolved
  flagged_at      TIMESTAMPTZ,                -- when Analyst flagged new evidence
  resolved_at     TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT NOW()
)
```

#### `spotlight_cooldown` (view or tracking)
Prevents re-spotlighting topics too soon.

```sql
-- Track which topics have been spotlighted and when (could also be a view on spotlight_history)
CREATE VIEW spotlight_cooldown AS
SELECT
  topic_id,
  topic_name,
  issue_number,
  created_at,
  -- Topics spotlighted in last 4 issues are on cooldown
  CASE WHEN issue_number >= (SELECT MAX(issue_number) FROM spotlight_history) - 3
       THEN true ELSE false END AS on_cooldown
FROM spotlight_history
ORDER BY issue_number DESC;
```

### Indexes

```sql
CREATE INDEX idx_research_queue_status ON research_queue(status);
CREATE INDEX idx_research_queue_priority ON research_queue(priority_score DESC);
CREATE INDEX idx_spotlight_history_topic ON spotlight_history(topic_id);
CREATE INDEX idx_spotlight_history_issue ON spotlight_history(issue_number DESC);
CREATE INDEX idx_predictions_status ON predictions(status);
CREATE INDEX idx_predictions_topic ON predictions(topic_id);
```

### Requirements
1. Create all tables with proper foreign keys and indexes
2. The `spotlight_cooldown` view should work correctly with the selection heuristic in Phase 2B
3. `context_payload` in `research_queue` is JSONB to allow flexible data passing between Analyst and Research Agent
4. `sources_used` in `spotlight_history` should store an array of objects: `[{source_name, url, tier, relevant_quote}]`
5. All tables should have RLS policies consistent with existing Supabase setup
6. Add any necessary foreign keys to existing topic tracking tables

### Acceptance Criteria
- [ ] All tables created and accessible
- [ ] Foreign keys working correctly
- [ ] Indexes in place
- [ ] `spotlight_cooldown` view returns correct cooldown status
- [ ] JSONB fields accept and return structured data correctly
- [ ] RLS policies consistent with existing setup
