-- Migration 037: fix the empty-search_path RPC class (prod-drift repair, batch)
-- Phase 04.1 follow-up / Prod↔Main Reconciliation.
--
-- ROOT CAUSE: the `fix_function_search_paths` hardening migration (2026-04-01) set
-- `search_path=""` on a class of public functions. Every function whose body references
-- objects UNQUALIFIED then raises `relation "x" does not exist` (SQLSTATE 42P01) at call
-- time — the silent-RPC-failure signature this project keeps tripping over (the wallet bug,
-- the system_audit CHECK drift, claim_research_task fixed in 035). PostgREST surfaces these
-- as confusing 404/500 and callers swallow them. `scripts/drift-check.sh` (migration 036
-- gsd_drift_audit) inventoried the remaining class as these 8 public functions.
--
-- CONFIRMED LIVE-BROKEN (body inspection, pg_get_functiondef):
--   get_scrape_stats        -> moltbook_posts                 (confirmed 42P01)
--   search_corpus           -> embeddings + pgvector <=> op   (load-bearing: gato corpus probe)
--   topup_agent_wallet      -> agent_wallets, agent_transactions   (load-bearing: wallet top-ups)
--   record_agent_spend      -> agent_wallets, agent_transactions   (broken; currently no caller)
--   transfer_between_agents -> agent_wallets_v2, wallet_transactions (pay-500; agent payments)
--   increment_problem_frequency -> problems
--   next_newsletter_edition     -> newsletters
-- BENIGN (fixed for consistency / to clear the standing drift check):
--   compute_opportunity_score   -> pure math, only pg_catalog builtins (works even with "")
--
-- WHY SAFE: all 8 are NOT SECURITY DEFINER (prosecdef=false), so the empty search_path
-- provides no injection-hardening benefit — it only breaks name resolution. Restoring
-- `pg_catalog, public` makes the unqualified references (tables + the public pgvector `<=>`
-- operator) resolve again with no logic change. This is the migration-035 pattern.
--
-- Idempotent: ALTER FUNCTION ... SET is safe to re-run.

ALTER FUNCTION public.get_scrape_stats()
    SET search_path = pg_catalog, public;

ALTER FUNCTION public.search_corpus(vector, integer, date, text[], integer)
    SET search_path = pg_catalog, public;

ALTER FUNCTION public.topup_agent_wallet(text, bigint)
    SET search_path = pg_catalog, public;

ALTER FUNCTION public.record_agent_spend(text, bigint, text, text, text)
    SET search_path = pg_catalog, public;

ALTER FUNCTION public.transfer_between_agents(text, text, bigint, text, uuid)
    SET search_path = pg_catalog, public;

ALTER FUNCTION public.increment_problem_frequency(uuid, uuid[])
    SET search_path = pg_catalog, public;

ALTER FUNCTION public.next_newsletter_edition()
    SET search_path = pg_catalog, public;

ALTER FUNCTION public.compute_opportunity_score(integer, integer, timestamp with time zone, text, text)
    SET search_path = pg_catalog, public;
