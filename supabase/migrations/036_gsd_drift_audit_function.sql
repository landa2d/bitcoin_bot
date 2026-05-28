-- Migration 036: gsd_drift_audit() — read-only drift detector for scripts/drift-check.sh
-- Phase 04.1 deploy-baseline guardrail.
--
-- Enables the standing pre-deploy drift check (the operator's close condition for 04.1) to
-- detect, over PostgREST, two of the three drift classes that have bitten prod:
--   - RPC class: any public function with an EMPTY search_path (the silent-RPC-failure
--     signature — see claim_research_task / transfer_between_agents, fixed in 035 / pending).
--   - migration class: which repo migrations are applied on prod.
-- (The third class — code drift, running image vs latest commit — is checked locally in the
-- script with docker+git and needs no DB access.)
--
-- This function is itself a model of the correct pattern: SECURITY DEFINER (required to read
-- the `supabase_migrations` system schema, which service_role lacks USAGE on) made SAFE by an
-- explicit, NON-EMPTY `SET search_path = pg_catalog, public` plus schema-qualifying the one
-- out-of-path object (`supabase_migrations.schema_migrations`) rather than relying on
-- search_path — exactly the hardening the silent-RPC class got wrong. It is STABLE, read-only,
-- and exposes only catalog metadata (function names + migration names) — no row data. It does
-- NOT flag itself: its search_path is non-empty.

CREATE OR REPLACE FUNCTION public.gsd_drift_audit()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $func$
  SELECT jsonb_build_object(
    'checked_at', now(),
    'empty_search_path_functions', (
      SELECT coalesce(jsonb_agg(jsonb_build_object(
                 'function', p.proname,
                 'args', pg_get_function_identity_arguments(p.oid),
                 'security_definer', p.prosecdef,
                 'config', to_jsonb(p.proconfig)
               ) ORDER BY p.proname), '[]'::jsonb)
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
      WHERE n.nspname = 'public'
        AND p.proconfig IS NOT NULL
        AND EXISTS (
          SELECT 1 FROM unnest(p.proconfig) AS c
          WHERE c = 'search_path=""' OR c = 'search_path='
        )
    ),
    'applied_migrations', (
      SELECT coalesce(jsonb_agg(m.name ORDER BY m.version), '[]'::jsonb)
      FROM supabase_migrations.schema_migrations m
    )
  );
$func$;

COMMENT ON FUNCTION public.gsd_drift_audit() IS
  'Read-only drift detector for scripts/drift-check.sh (Phase 04.1 guardrail): public functions with empty search_path + applied migration names.';
