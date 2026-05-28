---
created: 2026-05-28T11:54:47Z
updated: 2026-05-28T11:54:47Z
title: /v1/proxy/pay returns 500 — transfer_between_agents RPC search_path="" (active in prod)
area: tooling
priority: P1
phase_candidate: false
files:
  - docker/llm-proxy/proxy.py
  - docker/research/research_agent.py
  - supabase/migrations/
---

## Problem

`POST /v1/proxy/pay` is returning **500 Internal Server Error** in production, actively.
The `research` agent is the only caller (`research_agent.py:265`, paying `lab_data-provider`
for web research). Observed 5/5 calls → 500 in a 3h window on 2026-05-28, and the rate will
rise now that research's poll queue was just unblocked (see the claim_research_task fix,
migration 035).

## Root cause (confirmed) — same silent-RPC class

The `/pay` handler (proxy.py:1513) calls the `transfer_between_agents` RPC. That function has
`search_path=""` (and is NOT SECURITY DEFINER), set by the 2026-04-01 `fix_function_search_paths`
hardening migration. With an empty search_path its unqualified table references fail to resolve →
the RPC raises → the handler returns an unhandled 500. This is the **same signature** as the
`claim_research_task` drift fixed in migration 035 (and conceptually the same class as the
governance "wallet bug" and the `system_audit` CHECK drift).

## Impact

Agent-to-agent payments are broken: research is NOT paying lab_data-provider for data. Research
itself continues (it uses the data anyway — the failure is logged non-fatally), so no functional
outage, but the agent-economy payment integrity is silently broken. For an "AI agent economy"
platform this is a real correctness gap, just not a crash.

## Fix direction

- Mirror migration 035: `ALTER FUNCTION public.transfer_between_agents(text, text, bigint, text, uuid) SET search_path = pg_catalog, public;` (or schema-qualify the body). Ship as a tracked migration + apply to prod under approval.
- Then confirm a real research run produces a `/v1/proxy/pay → 200` and a `wallet_transactions` transfer.
- **Do this as part of, or alongside, the RPC search_path audit (see the audit todo) — this is instance #4 of the class.**
