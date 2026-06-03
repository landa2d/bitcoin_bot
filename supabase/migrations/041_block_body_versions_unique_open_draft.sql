-- Migration 041: WR-01 partial UNIQUE open-draft index.
-- Phase 10 operator-write-commands / Plan 10-01.
--
-- Ships the WR-01 duplicate-draft structural backstop as its OWN operator-approved
-- migration (D-07 / the WR-01 todo's "own approved migration track" + the
-- scoped-approved-deploys discipline). Deliberately SEPARATE from migration 040 — do NOT
-- fold it in.
--
-- This UNIQUE partial index guarantees at most one open ('draft') block_body_version per
-- block_slug. It is the structural backstop for the /map-synth + scheduled-poller
-- check-then-act race (D-02/D-07): the cheap block_has_open_draft fast-path in the
-- processor stays, and the processor catches the resulting 23505 unique-violation on
-- INSERT as a LOGGED BENIGN SKIP ("race lost"), never a fail-loud abort.
--
-- Analog: the existing NON-unique partial index migration 033:109-110
--   CREATE INDEX IF NOT EXISTS idx_block_body_versions_status
--       ON economy_map.block_body_versions(status) WHERE status = 'draft';
-- This migration adds the UNIQUE upgrade keyed on block_slug (the per-block invariant).

CREATE UNIQUE INDEX IF NOT EXISTS uq_block_body_versions_one_open_draft
    ON economy_map.block_body_versions (block_slug) WHERE status = 'draft';
