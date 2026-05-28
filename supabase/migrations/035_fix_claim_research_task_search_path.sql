-- Migration 035: fix claim_research_task search_path (prod-drift repair)
-- Phase 04.1 / Prod↔Main Reconciliation.
--
-- ROOT CAUSE: the `fix_function_search_paths` hardening migration (2026-04-01) set
-- `search_path=""` on claim_research_task(integer). The function body references
-- `research_queue` UNQUALIFIED, so with an empty search_path it raises
-- `relation "research_queue" does not exist` (SQLSTATE 42P01) on every call —
-- silently breaking the research agent's poll loop since April (PostgREST surfaces it
-- as a 404 on /rpc/claim_research_task). The RPC and the table both exist; only the
-- search_path is wrong.
--
-- WHY SAFE: claim_research_task is NOT SECURITY DEFINER (prosecdef=false), so the
-- empty search_path provides no injection-hardening benefit here — it only breaks
-- name resolution. Restoring `pg_catalog, public` makes the unqualified `research_queue`
-- reference resolve again with no logic change. (claim_agent_task, used by the other
-- pollers, was never given an empty search_path, which is why it kept working.)
--
-- Idempotent: ALTER FUNCTION ... SET is safe to re-run.

ALTER FUNCTION public.claim_research_task(integer)
    SET search_path = pg_catalog, public;
