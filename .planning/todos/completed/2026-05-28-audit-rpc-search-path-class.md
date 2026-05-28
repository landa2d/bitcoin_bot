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

## RESOLVED (2026-05-28) — migration 037

All 8 inventoried functions fixed via `037_fix_rpc_search_paths` (one
`ALTER FUNCTION … SET search_path = pg_catalog, public` each; all non-SECURITY-DEFINER, the
migration-035 pattern). Bodies were inspected first: 7 referenced unqualified tables (live-broken;
`get_scrape_stats` confirmed 42P01 → now returns rows), `compute_opportunity_score` was benign
(pg_catalog-only) but fixed for consistency. `scripts/drift-check.sh` RPC section now reports
"no public function has an empty search_path". Detection (drift-check + `gsd_drift_audit()`) stays
standing so the class is caught structurally going forward.

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

## CONFIRMED INVENTORY (2026-05-28, via scripts/drift-check.sh / gsd_drift_audit RPC)

The class is **8 public functions with empty `search_path`** (all non-SECURITY DEFINER), not the
2 we tripped over. `claim_research_task` is NOT here (fixed in migration 035). For each, the
empty search_path is a **latent failure** — it breaks ONLY if the body references unqualified
objects (tables/types). Table-touching ones are almost certainly broken NOW; pure functions may
be benign. **Each needs body inspection (`pg_get_functiondef`) to confirm live-broken vs benign.**

| Function | Likely live-broken? (assess) | Notes |
|----------|------------------------------|-------|
| `transfer_between_agents(text,text,bigint,text,uuid)` | YES — confirmed | pay-500; agent→agent payments. See pay-500 todo. |
| `record_agent_spend(text,bigint,text,text,text)` | LIKELY — **load-bearing** | agent spend logging — core to wallet/economy. If broken, spend tracking may be silently wrong (possibly related to the rivalscope negative-balance anomaly). Assess first. |
| `search_corpus(vector,int,date,text[],int)` | LIKELY — **load-bearing** | pgvector knowledge-base search (gato_brain corpus probe, newsletter). |
| `topup_agent_wallet(text,bigint)` | LIKELY — **load-bearing** | wallet top-ups. |
| `next_newsletter_edition()` | LIKELY | newsletter edition numbering. |
| `increment_problem_frequency(uuid,uuid[])` | LIKELY | economy_map / problem tracking. |
| `get_scrape_stats()` | LIKELY | scraper stats. |
| `compute_opportunity_score(int,int,timestamptz,text,text)` | MAYBE benign | may be pure math (no table refs) — check. |

## How to audit / remediate

Detection is now automated — `scripts/drift-check.sh` (RPC section) lists them on demand.
For each function: confirm live-broken via `pg_get_functiondef`, then fix with either
`ALTER FUNCTION … SET search_path = pg_catalog, public` (non-secdef, safe — the migration-035
pattern) or schema-qualify all object references in the body (preserves hardening for secdef).
Ship corrections as tracked migrations, re-run drift-check.sh to confirm zero remain.

**Standing check now EXISTS** (`scripts/drift-check.sh` + migration 036 `gsd_drift_audit()`),
built during the 04.1 closeout — run it before every deploy. Remediating the 8 is separate
from detection.

## Why this matters

Fixing only the RPCs we've tripped over resets the clock. The class is the bug.
