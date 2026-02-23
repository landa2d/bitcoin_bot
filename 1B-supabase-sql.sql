-- ============================================================================
-- 1B: Research Queue, Spotlight History, Predictions Extensions, Cooldown View
-- Run this in Supabase SQL Editor
-- ============================================================================

-- 1. research_queue: Analyst -> Research Agent handoff
CREATE TABLE IF NOT EXISTS research_queue (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic_id        TEXT NOT NULL,
  topic_name      TEXT NOT NULL,
  priority_score  FLOAT NOT NULL,
  velocity        FLOAT,
  source_diversity FLOAT,
  lifecycle_phase TEXT,
  context_payload JSONB,
  mode            TEXT DEFAULT 'spotlight',
  status          TEXT DEFAULT 'queued',
  issue_number    INTEGER,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  started_at      TIMESTAMPTZ,
  completed_at    TIMESTAMPTZ
);

-- 2. spotlight_history: Completed Spotlight analyses
CREATE TABLE IF NOT EXISTS spotlight_history (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  research_queue_id UUID REFERENCES research_queue(id),
  topic_id          TEXT NOT NULL,
  topic_name        TEXT NOT NULL,
  issue_number      INTEGER NOT NULL,
  mode              TEXT DEFAULT 'spotlight',
  thesis            TEXT NOT NULL,
  evidence          TEXT NOT NULL,
  counter_argument  TEXT NOT NULL,
  prediction        TEXT NOT NULL,
  builder_implications TEXT,
  full_output       TEXT NOT NULL,
  sources_used      JSONB,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Extend existing predictions table with spotlight/scorecard columns
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'predictions' AND column_name = 'spotlight_id') THEN
    ALTER TABLE predictions ADD COLUMN spotlight_id UUID REFERENCES spotlight_history(id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'predictions' AND column_name = 'prediction_text') THEN
    ALTER TABLE predictions ADD COLUMN prediction_text TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'predictions' AND column_name = 'evidence_notes') THEN
    ALTER TABLE predictions ADD COLUMN evidence_notes TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'predictions' AND column_name = 'resolution_notes') THEN
    ALTER TABLE predictions ADD COLUMN resolution_notes TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'predictions' AND column_name = 'scorecard_issue') THEN
    ALTER TABLE predictions ADD COLUMN scorecard_issue INTEGER;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'predictions' AND column_name = 'flagged_at') THEN
    ALTER TABLE predictions ADD COLUMN flagged_at TIMESTAMPTZ;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'predictions' AND column_name = 'resolved_at') THEN
    ALTER TABLE predictions ADD COLUMN resolved_at TIMESTAMPTZ;
  END IF;
END $$;

-- 4. spotlight_cooldown view
CREATE OR REPLACE VIEW spotlight_cooldown AS
SELECT
  topic_id,
  topic_name,
  issue_number,
  created_at,
  CASE WHEN issue_number >= (SELECT COALESCE(MAX(issue_number), 0) FROM spotlight_history) - 3
       THEN true ELSE false END AS on_cooldown
FROM spotlight_history
ORDER BY issue_number DESC;

-- 5. Indexes
CREATE INDEX IF NOT EXISTS idx_research_queue_status ON research_queue(status);
CREATE INDEX IF NOT EXISTS idx_research_queue_priority ON research_queue(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_spotlight_history_topic ON spotlight_history(topic_id);
CREATE INDEX IF NOT EXISTS idx_spotlight_history_issue ON spotlight_history(issue_number DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(status);
CREATE INDEX IF NOT EXISTS idx_predictions_topic ON predictions(topic_id);

-- 6. Verification query
SELECT
  t.table_name,
  COUNT(c.column_name) AS columns
FROM information_schema.tables t
JOIN information_schema.columns c ON c.table_name = t.table_name AND c.table_schema = t.table_schema
WHERE t.table_schema = 'public'
  AND t.table_name IN ('research_queue', 'spotlight_history', 'predictions')
GROUP BY t.table_name
ORDER BY t.table_name;
