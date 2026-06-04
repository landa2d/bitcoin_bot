---
status: partial
phase: 02-economy-map-schema-seven-block-seed
source: [02-VERIFICATION.md]
started: 2026-05-27T16:10:00Z
updated: 2026-05-27T16:10:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Anon-key `Accept-Profile: economy_map` resolves at PostgREST runtime (Probe 5.1)
expected: HTTP 200 + 7 JSON objects in D-23 sort_order (identity-trust, memory-context, payments-settlement, autonomy-control, governance-accountability, psychology-disposition, regulation-legal)
result: pending — PostgREST runtime cache has not yet propagated the new `db_schema` allowlist. Persisted Management API config correctly includes `economy_map`.

How to run:
```bash
PROJECT_URL=https://zxzaaqfowtqvmsbitqpu.supabase.co
ANON_KEY="<your anon key>"
curl -sS -w "\nHTTP_STATUS:%{http_code}\n" \
  -H "apikey: $ANON_KEY" -H "Accept-Profile: economy_map" \
  "$PROJECT_URL/rest/v1/blocks?select=slug,tier,accent,sort_order&order=sort_order.asc"
```

### 2. Anon-key probe to `block_body_versions` returns only published rows (Probe 5.2)
expected: HTTP 200 + exactly 1 JSON object: `{"id":"8aafdd9a-c619-44cb-bd84-784730a85389","block_slug":"identity-trust","status":"published"}` — v1 (status='superseded') and any draft rows are hidden by the RLS predicate `USING (status = 'published')`
result: pending

How to run:
```bash
curl -sS -w "\nHTTP_STATUS:%{http_code}\n" \
  -H "apikey: $ANON_KEY" -H "Accept-Profile: economy_map" \
  "$PROJECT_URL/rest/v1/block_body_versions?select=id,block_slug,status"
```

### 3. Anon-key probe to `timeline_entries` filters `unsorted` (Probe 5.3)
expected: HTTP 200 + exactly 1 JSON object: the `identity-trust` entry from Plan 02-02 step 3.e — the `unsorted` entry from step 3.g must be HIDDEN by the RLS predicate `USING (block_slug <> 'unsorted')`
result: pending

How to run:
```bash
curl -sS -w "\nHTTP_STATUS:%{http_code}\n" \
  -H "apikey: $ANON_KEY" -H "Accept-Profile: economy_map" \
  "$PROJECT_URL/rest/v1/timeline_entries?select=id,block_slug"
```

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

None — all three pending items are config-level correct (Management API `db_schema` includes `economy_map`); only PostgREST runtime container restart is awaited. This is a Supabase Cloud platform constraint, not a code defect.

## Background poll status

A background poll runs every 5 minutes for up to 60 minutes (orchestrator task #8), probing `/rest/v1/blocks` with `Accept-Profile: economy_map`. As of last check (T+20min), still HTTP 406 PGRST106. The poll will notify when HTTP 200 lands; at that point, run all three probes above, paste the outputs into `02-VERIFY-RESULTS.md §Anon-key Probe Results`, and the phase becomes fully verified.

If 60 minutes elapses without propagation, options:
1. Open a Supabase support ticket requesting a PostgREST restart on project `zxzaaqfowtqvmsbitqpu`.
2. Wait longer — Supabase's eventual config-refresh cycle will pick it up.
3. Accept the runtime-pending status; phase structural verification is complete (8/9 must-haves, all SCHM-01..08 requirements covered).
