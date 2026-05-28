---
created: 2026-05-28T11:54:47Z
updated: 2026-05-28T11:54:47Z
title: research agent — stale trigger files cause Permission denied on file-queue path
area: research
priority: P4
phase_candidate: false
files:
  - docker/research/research_agent.py
---

## Problem

On each poll, research logs several `ERROR: Error processing trigger
research-trigger-YYYYMMDD...json: [Errno 13] Permission denied:
/home/openclaw/.openclaw/workspace/agentpulse/queue/research/research-trigger-*.json`.

These are stale file-based trigger files (back to 2026-04-06) that research can't delete due to
filesystem ownership/permissions on the mounted queue volume.

## Triage

Non-blocking. The DB-queue path (`claim_research_task`, now fixed) works and is the primary
mechanism; research completes governed cycles regardless. The file-trigger path is a legacy
fallback. Effect is log noise + the stale files never clear.

## Fix direction

- Fix ownership/permissions on `…/queue/research/` so research (user `openclaw`) can read+unlink
  its trigger files, OR
- Clear the stale trigger backlog and/or make the file-trigger processing tolerant of
  permission errors (skip + warn once, don't error every cycle), OR
- If the DB queue has fully superseded file triggers, retire the file-trigger path.

Low priority — cosmetic/log-noise, no functional impact.
