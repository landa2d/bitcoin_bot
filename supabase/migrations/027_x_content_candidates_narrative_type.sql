-- Migration 027: Add 'narrative' to x_content_candidates content_type
-- Supports editorial arc posts (building-in-public, first-person narrative)

ALTER TABLE x_content_candidates DROP CONSTRAINT IF EXISTS x_content_candidates_content_type_check;
ALTER TABLE x_content_candidates ADD CONSTRAINT x_content_candidates_content_type_check
  CHECK (content_type IN ('sharp_take', 'newsletter_thread', 'engagement_reply', 'prediction', 'narrative'));
