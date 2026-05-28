---
created: 2026-05-28T11:54:47Z
updated: 2026-05-28T11:54:47Z
title: Audit EVERY postgres function for broken search_path (silent-RPC-failure class)
area: tooling
priority: P3
phase_candidate: true
files:
  - supabase/migrations/
---

## Problem

The `claim_research_task` drift (fixed in migration 035) is the **third+ instance of one
recurring signature**, not a coincidence:
1. the governance "wallet bug" (silent governance-off),
2. the `system_audit` event_type CHECK drift (would have silently dropped a live event type),
3. `claim_research_task` `search_path=""` → silent 404/42P01, stalled research's queue since April,
4. `transfer_between_agents` `search_path=""` → `/v1/proxy/pay` 500 (see the pay-500 todo).

The common mechanism: the 2026-04-01 `fix_function_search_paths` hardening migration set
`search_path=""` on functions whose bodies reference tables **unqualified**, so they raise
`relation "x" does not exist` at call time. PostgREST surfaces this as a confusing 404/500, and
callers often swallow it — exactly the silent-failure class the operator wants eliminated.

## Scope (IMPORTANT — broader than SECURITY DEFINER)

Operator asked to audit "every SECURITY DEFINER RPC for SET search_path". Evidence refines this:
**both confirmed broken functions are NOT SECURITY DEFINER.** So the audit must cover **every
function with `proconfig` containing `search_path=""` (or any search_path that omits the schema
its body references)** — secdef and non-secdef alike.

## How to audit

```sql
SELECT n.nspname, p.proname, p.prosecdef, p.proconfig,
       pg_get_function_identity_arguments(p.oid) AS args
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname IN ('public')
  AND p.proconfig IS NOT NULL
  AND EXISTS (SELECT 1 FROM unnest(p.proconfig) c WHERE c LIKE 'search_path=%')
ORDER BY p.proname;
```

For each: either `SET search_path = pg_catalog, public` (non-secdef, safe) or schema-qualify all
object references in the body (preserves hardening for secdef). Ship corrections as tracked
migrations. Then add a **standing pre-deploy check** (see the prod==main reconcile closeout) so
the next drift is caught structurally, not by tripping over it in prod.

## Why this matters

Fixing only the RPCs we've tripped over resets the clock. The class is the bug.
