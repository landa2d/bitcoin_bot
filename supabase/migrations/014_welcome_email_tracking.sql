-- Migration 014: Track welcome email delivery
-- Adds a timestamp column so the processor only sends the welcome email once.

ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS welcome_email_sent_at TIMESTAMPTZ;
