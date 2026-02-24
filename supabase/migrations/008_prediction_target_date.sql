-- Migration 008: Add target_date to predictions for stale prediction detection
-- Supports Issue #4 (Stale Predictions) and Issue #6 (Passive/Unfalsifiable)

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'predictions' AND column_name = 'target_date'
    ) THEN
        ALTER TABLE predictions ADD COLUMN target_date DATE;
    END IF;
END $$;

-- Index for efficient stale prediction queries
CREATE INDEX IF NOT EXISTS idx_predictions_target_date
    ON predictions(target_date ASC NULLS LAST)
    WHERE status IN ('active', 'open');

-- View: predictions past their target_date that are still unresolved
CREATE OR REPLACE VIEW stale_predictions AS
SELECT
    id,
    prediction_text,
    status,
    target_date,
    created_at,
    issue_number,
    CURRENT_DATE - target_date AS days_overdue
FROM predictions
WHERE target_date IS NOT NULL
  AND target_date < CURRENT_DATE
  AND status IN ('active', 'open', 'flagged')
ORDER BY target_date ASC;
