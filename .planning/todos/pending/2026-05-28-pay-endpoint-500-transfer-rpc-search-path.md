---
created: 2026-05-28T11:54:47Z
updated: 2026-05-28T12:06:00Z
title: transfer_between_agents RPC broken (search_path="", class instance #4) — blocker BEFORE enabling agent→agent payments
area: tooling
priority: P2
phase_candidate: false
files:
  - docker/llm-proxy/proxy.py
  - docker/research/research_agent.py
  - supabase/migrations/
---

## STATUS (2026-05-28): RPC root cause FIXED in migration 037 — residual is activation-time E2E only

The structural blocker is cleared: migration 037 (`037_fix_rpc_search_paths`) applied
`ALTER FUNCTION public.transfer_between_agents(text, text, bigint, text, uuid) SET search_path = pg_catalog, public;`
to prod (verified: function now carries a non-empty search_path; drift-check RPC section clean).
The ONLY thing left on this todo is the activation-time acceptance check — verify `/v1/proxy/pay → 200`
plus a real `wallet_transactions` transfer — which can only be exercised once agent→agent payments
are actually turned on. Kept in pending purely as that activation reminder; not outstanding work today.

## Severity: blocker-on-activation — NOT urgent, NOT currently breaking anything

The agent→agent payment rail is **structurally broken**, but **agent payments are not in use
yet.** The only caller observed — research (`research_agent.py:265`, paying `lab_data-provider`
for web research) — was an **experiment, not a flow anyone depends on.** So the 500s harm nothing
today: research uses the data anyway and logs the failure non-fatally. Do NOT read this as
"P1, actively breaking payments" — that would mislead. The accurate framing: **the rail is
broken and MUST be fixed before agent→agent payments are ever turned on for real** (a
blocker-on-activation), and it is instance #4 of the silent-RPC `search_path` class.

## Problem

`POST /v1/proxy/pay` returns **500 Internal Server Error**. The handler (proxy.py:1513) calls
the `transfer_between_agents` RPC, which raises.

## Root cause (confirmed) — same silent-RPC class

The `/pay` handler (proxy.py:1513) calls the `transfer_between_agents` RPC. That function has
`search_path=""` (and is NOT SECURITY DEFINER), set by the 2026-04-01 `fix_function_search_paths`
hardening migration. With an empty search_path its unqualified table references fail to resolve →
the RPC raises → the handler returns an unhandled 500. This is the **same signature** as the
`claim_research_task` drift fixed in migration 035 (and conceptually the same class as the
governance "wallet bug" and the `system_audit` CHECK drift).

## Fix direction (do before enabling agent→agent payments)

- Mirror migration 035: `ALTER FUNCTION public.transfer_between_agents(text, text, bigint, text, uuid) SET search_path = pg_catalog, public;` (or schema-qualify the body). Ship as a tracked migration + apply under approval.
- Verify with a `/v1/proxy/pay → 200` + a `wallet_transactions` transfer once payments are actually exercised.
- Fold into the RPC `search_path` audit (see that todo) — this is class instance #4. The audit matters regardless of whether any single instance is currently load-bearing.
