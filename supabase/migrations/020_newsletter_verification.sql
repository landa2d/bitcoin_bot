-- Migration 020: Add verification_warnings column to newsletters
-- Stores unverified references flagged by verify_briefing_references()

ALTER TABLE newsletters
  ADD COLUMN IF NOT EXISTS verification_warnings jsonb DEFAULT NULL;

COMMENT ON COLUMN newsletters.verification_warnings IS
  'List of unverified entity references detected before publish';
