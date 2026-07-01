-- Migration 046: first-class do_not_publish + do_not_publish_reason columns on newsletters
-- Phase 30 (v2.3 Pre-Publish Evaluation Step) — Sequencer Wiring, Hold Action & Activation Gate.
--
-- The single canonical home for hold state (D-01 / WIRE-02). Today `do_not_publish`
-- lives only INSIDE the `data_snapshot` JSONB on the always-held A/B block_v1 rows;
-- this migration promotes it to two first-class, queryable columns on `newsletters` so
-- the eval hold action has exactly ONE structural home and the Processor publish gate
-- can refuse a held row by reading a real column (not inferring hold from status alone).
--
-- SQL-FIRST — the operator applies this via MCP after DDL review (project ref
-- zxzaaqfowtqvmsbitqpu). The APPLY is an operator-owned MCP step in the Plan 30-04
-- activation runbook, NOT this authoring task.
-- Do NOT apply this from a worktree and do NOT run `supabase db push`.
--
-- Schema-only, re-apply-safe: both columns use ADD COLUMN IF NOT EXISTS (020 house
-- style). No data-migration backfill — `DEFAULT false` covers every new row, and the
-- historical always-held A/B shadow rows are already excluded by their `held` status,
-- so touching historical rows is unnecessary risk (D-13 discretion, leave-as-is).

ALTER TABLE newsletters
  ADD COLUMN IF NOT EXISTS do_not_publish boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS do_not_publish_reason text;

COMMENT ON COLUMN newsletters.do_not_publish IS
  'hard hold flag; the publish gate refuses to ship a row with this true (Phase 30 eval hold action)';

COMMENT ON COLUMN newsletters.do_not_publish_reason IS
  'human-readable reason the eval held this edition (fabrication categories / failing judge dimensions)';
