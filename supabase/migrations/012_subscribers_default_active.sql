-- Migration 012: Default subscribers to active (no double opt-in)
-- The confirmation email flow was never implemented, so pending subscribers
-- are real subscribers who should be active.

ALTER TABLE subscribers ALTER COLUMN status SET DEFAULT 'active';

-- Activate any existing pending subscribers
UPDATE subscribers SET status = 'active', confirmed_at = NOW()
WHERE status = 'pending';
