---
created: 2026-05-28T11:54:47Z
updated: 2026-05-28T11:54:47Z
title: (Revisit, not a defect) Optionally harden soft spending caps — allow_negative=false
area: governance
priority: P5
phase_candidate: false
files:
  - docker/llm-proxy/proxy.py
  - supabase/migrations/
---

## Context (NOT a defect — a previously-accepted choice to revisit)

After the Phase 04.1 governance cutover, the 5 governed agents (analyst 28000/d, processor
1000/d, research 5000/wk, newsletter 2000/wk, gato 50000/d-downgrade) all have
`allow_negative=true`. In `check_governance` (proxy.py:406) that makes an over-cap call emit a
`cap_hit` event but **ALLOW** the call — i.e. the caps are SOFT (alert-only), not hard stops.
(gato is the exception — its downgrade branch fires before the allow_negative check.)

During the cutover canary, the operator **explicitly accepted soft caps as intended** (caps =
monitoring/alerting; the hard guarantee is fail-loud on MISSING/unknown caps, which IS enforced).
This todo is a parked option to revisit, not a bug.

## If hardening is later desired

- Set `agent_wallets_v2.allow_negative=false` for the capped agents (keep gato on `downgrade`).
  Over-cap then rejects (or downgrades for gato) instead of alert-and-allow.
- Note the separation: balance-reservation tolerance is driven by `access_tier=="internal"`
  (reserve_balance), NOT the `allow_negative` column — so flipping the column hardens the
  spending-cap path WITHOUT weakening mid-task balance tolerance.
- Operational cost: an agent that exceeds its window then hard-rejects until the window resets
  (e.g. processor at 1000/daily would stop for the day). Decide per-agent.

Lowest tier — revisiting an accepted decision.
