---
phase: 18-gated-batch-publish
plan: 02
subsystem: economy_map publish + verification scripts
tags: [economy-map, publish, verification, fail-loud, postgrest]
requires:
  - "economy_map.publish_block_version RPC (mig 039) — atomic draft->published, service_role only"
  - "Phase-16 loaded open drafts for the 8 in-scope slugs (hub + 7 blocks)"
  - "scripts/load_economy_map_content.py + scripts/verify_economy_map_crosslinks.py (idiom source)"
provides:
  - "scripts/publish_economy_map_batch.py — operator-gated batch publish (resolve -> manifest -> RPC loop)"
  - "scripts/verify_economy_map_publish.py — anon-key post-publish fail-loud assertions"
affects:
  - "Wave-2 go-live plan (18-03) RUNS both scripts; no live publish here"
tech-stack:
  added: []
  patterns:
    - "Direct PostgREST READ (Accept-Profile) + WRITE/RPC (Content-Profile) — no supabase-py"
    - "Validate-all-then-act pre-flight + idempotent skip + halt-and-report (fail-loud governance)"
    - "Per-slug eq. draft/body resolution (never the array-membership filter)"
key-files:
  created:
    - scripts/publish_economy_map_batch.py
    - scripts/verify_economy_map_publish.py
  modified: []
decisions:
  - "Separate anon verify harness (not extending the service_role crosslinks harness) — D-05 clean decoupling"
  - "Reworded a manifest docstring to 'the deferred legal frame' so the excluded slug appears in NO line (verify-gate compliance)"
metrics:
  duration: "~10 min"
  completed: 2026-06-09
---

# Phase 18 Plan 02: Gated Batch Publish Scripts Summary

Authored the two standalone scripts the Wave-2 go-live needs — an operator-gated batch
publisher that resolves the 8 in-scope open drafts and loops the existing
`publish_block_version` RPC (blocks first, hub last; fail-loud + idempotent), and an
anon-key post-publish verification harness that proves the published set from a real
visitor's perspective. No live publish ran; both scripts are authored only.

## What Was Built

### Task 1 — `scripts/publish_economy_map_batch.py` (375 lines)
Operator-gated batch publish (D-06/D-07/D-08):
- **Resolve (D-06 step 1):** per-slug PostgREST `eq.` reads (`block_slug=eq.<slug>`,
  `status=eq.draft`, `select=id,proposed_maturity`, `order=created_at.desc`, `limit=1`)
  build `resolved: slug -> {version_id, proposed_maturity, old_maturity}`; old maturity
  read from `blocks.maturity` per slug (mirrors `get_block_by_slug`).
- **PUBLISH_ORDER (D-07):** exactly 8 slugs — the 7 reconciled blocks FIRST
  (`identity-trust`, `memory-context`, `payments-settlement`, `autonomy-control`,
  `negotiation-coordination`, `governance-accountability`, `psychology-disposition`)
  then `agent-economy` (the hub) LAST. The deferred legal frame appears in NO line
  (P15-D-02 / D-06).
- **Pre-flight (D-08):** `missing = [s for s in PUBLISH_ORDER if s not in resolved]`;
  any miss prints the list and `sys.exit(1)` BEFORE any POST (no partial pass).
- **Manifest + single gate (D-06 step 2):** prints a manifest table
  (`# | slug | old->new maturity | version_id`) in PUBLISH_ORDER for the ONE operator
  approval (orchestrator surfaces it in-chat). `--dry-run` prints the manifest and
  skips ALL POSTs.
- **WRITE loop (D-06 step 3):** `_economy_map_rpc("publish_block_version",
  {"p_version_id": version_id})` — Content-Profile WRITE, `/rest/v1/rpc/...`,
  `json=params`, `(200, 204)` check; the gato_brain caller-controlled allowlist was
  dropped (standalone single-RPC caller). Idempotent SKIP on the
  `"not found or not in draft status"` marker; any OTHER RuntimeError HALTs and reports
  published/skipped/failed/remaining, then `sys.exit(1)`.
- **Key:** `SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")`
  — service_role required (drafts RLS-invisible to anon + RPC GRANTed to service_role
  only, mig 039:82).

### Task 2 — `scripts/verify_economy_map_publish.py` (393 lines)
Anon-key post-publish verification (D-05), a SEPARATE harness (crosslinks harness left
unchanged):
- **Key:** `SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")` — anon only, no service_role,
  no preview flag, so it proves exactly what a real visitor sees.
- **Four D-05 assertions, accumulate-then-fail-loud (`sys.exit(1)` if any):**
  (a) each of the 8 in-scope slugs has a non-null `current_body_version_id` whose
  published body the anon key can load; (b) the hub `agent-economy` published body
  resolves; (c) every `#/map/<slug>` cross-link extracted from the PUBLISHED bodies
  resolves to a slug whose published body the anon key can also load; (d) the
  anon-visible published-block count equals 8 and prints the 2->8 transition.
- **Empty-roster guard:** `fetch_roster` fails loud on an empty/anon-blocked read so the
  harness never vacuously passes.
- Per-slug / per-id `eq.` reads only (no array-membership filter).
- Module docstring notes it is RUN after the publish batch — pre-publish it correctly
  reports fewer than 8 published and exits nonzero (expected, not a defect).

## Verification

Both plan `<automated>` gates were RUN against the live authored files and produced the
exact expected output:

- **Task 1:** `python3 -c "import ast; ast.parse(...)" && ! grep -q 'regulation-legal' ... && echo REGLEGAL-EXCLUDED-OK && grep -L 'in_(' ...`
  -> printed `REGLEGAL-EXCLUDED-OK` and listed `scripts/publish_economy_map_batch.py`.
- **Task 2:** `python3 -c "import ast; ast.parse(...)" && grep -q SUPABASE_ANON_KEY ... && grep -L 'in_(' ... && echo VERIFY-HARNESS-OK`
  -> listed `scripts/verify_economy_map_publish.py` and printed `VERIFY-HARNESS-OK`.

Additional confirmations (not the live publish — deferred to 18-03):
- Both modules import cleanly (smoke-loaded via importlib).
- `PUBLISH_ORDER` is exactly 8 slugs, hub LAST, 7 blocks before it, no legal frame.
- `SOURCE_SLUGS` is the hub + 7 blocks (8); counts 2 -> 8.
- `scripts/verify_economy_map_crosslinks.py` and `scripts/load_economy_map_content.py`
  are byte-for-byte unchanged.
- No file deletions in either commit.

Per orchestrator override: NO live publish was run; the batch script was exercised only
via the `--dry-run`-capable path conceptually (no POST), and the verify harness was NOT
run live (pre-publish it correctly reports <8 published and exits nonzero — expected).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reworded a manifest docstring to satisfy the verify gate**
- **Found during:** Task 1
- **Issue:** A docstring in `print_manifest` originally referenced the excluded slug by
  its literal name to explain why it is absent. The Task-1 verify gate
  (`! grep -q 'regulation-legal'`) requires the slug to appear in NO line of the script,
  so the explanatory comment tripped the gate (the `&&` chain produced no output).
- **Fix:** Reworded the docstring to "The deferred legal frame is absent by construction
  (P15-D-02 / D-06)" — same meaning, no literal slug.
- **Files modified:** `scripts/publish_economy_map_batch.py`
- **Commit:** 6fce74b

No other deviations — the scripts were authored from the PATTERNS copy-ready excerpts and
the located analogs as written.

## Notes for Wave-2 (18-03)
- Deploy `app.js` (deploy-first, D-04) BEFORE running the batch.
- Run `python3 scripts/publish_economy_map_batch.py --dry-run` to surface the manifest for
  the operator approval gate, then re-run without `--dry-run` after approval.
- After publish, run `python3 scripts/verify_economy_map_publish.py` (anon) — it must
  print `RESULT: PASS` (8 published, hub resolves, cross-links against published, 2 -> 8).
