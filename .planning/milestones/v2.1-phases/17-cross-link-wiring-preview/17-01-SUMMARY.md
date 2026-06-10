---
phase: 17-cross-link-wiring-preview
plan: 01
subsystem: web-frontend
tags: [economy-map, preview, draft-render, cross-link, app.js, dormant-flag]
requires:
  - "Phase 16 load: 8 canonical bodies present as status='draft' in economy_map.block_body_versions (hub agent-economy + 7 blocks)"
  - "15-CONTRACT: anon RLS block_body_versions USING(status='published'); created_at append-ordering column; migration 041 one-open-draft-per-slug invariant"
provides:
  - "PREVIEW_ENABLED dormant-in-prod flag (app.js) gating both draft-fetch fallbacks"
  - "loadBlock read-only draft-fetch fallback (D-03) — renders status='draft' block bodies in preview, no-op in prod"
  - "renderHub hub-intro render via marked.parse + trimHubBody() prose-block-list trim (D-06a/c, HUB-01)"
affects:
  - "docker/web/site/app.js (the only source file modified)"
tech-stack:
  added: []
  patterns:
    - "supabase-js sb.schema('economy_map') .eq().order().limit(1)+array draft fetch (frontend; NOT the Python httpx PostgREST path)"
    - "URL-param feature gate via new URL(window.location).searchParams.get('preview') (getInitialMode idiom)"
    - "pre-marked.parse markdown string trim (deterministic literal-heading cut, no DOM surgery)"
key-files:
  created: []
  modified:
    - "docker/web/site/app.js — PREVIEW_ENABLED flag; trimHubBody() helper; loadBlock draft fallback; loadHub hub-draft fetch + renderHub marked.parse intro"
decisions:
  - "D-04 (dormant flag): PREVIEW_ENABLED reads ?preview=1|true, defaults false — double-safe (no flag + published-only RLS both suppress the path in prod)"
  - "D-03 (draft fetch): supabase-js .eq('block_slug').eq('status','draft').order('created_at',desc).limit(1)+array; the deliberate flag-gated INVERSE of the D-17-forbidden published filter"
  - "D-06c (hub trim, Claude's Discretion default kept): trimHubBody cuts on literal '## Tier 1', re-appends '## The thesis, restated' — block list appears once, as cards (HUB-01)"
metrics:
  duration: ~7min
  completed: 2026-06-08
  tasks: 3
  files: 1
---

# Phase 17 Plan 01: Cross-link Wiring & Preview Render Path Summary

Added the content-scoped, dormant-in-prod preview render path to `docker/web/site/app.js` so the Phase-16 loaded-but-unpublished `economy_map` draft bodies (hub + 7 blocks) render on a local preview — gated behind an explicit `PREVIEW_ENABLED` flag, reusing the existing `marked.parse` + supabase-js + card-link patterns, with the deployed anon-key path left a byte-for-byte no-op (double-safe). The hub draft intro renders above the card grid with its Tier-1/Tier-2 prose block-list code-trimmed so the block list appears once (as cards). No DB write, no schema/RLS change, no literal key in app.js.

## What Was Built

### Task 1 — Dormant `PREVIEW_ENABLED` flag (D-04) — commit `0c5b82b`
A module-scoped `const PREVIEW_ENABLED` near the Phase-4 economy-map constants, resolved via `new URL(window.location).searchParams.get('preview')` (the same idiom as `getInitialMode()` at app.js:49), true only when the param is `'1'` or `'true'`, defaulting `false` when absent. No new route/view/component — a boolean read gating both Task 2 and Task 3 draft fetches.

### Task 2 — `loadBlock` read-only draft-fetch fallback (D-03, LINK-01) — commit `124d792`
After the existing `current_body_version_id` published-body fetch, when `bodyMd` is still null AND `PREVIEW_ENABLED`, fetch the latest `status='draft'` body for the slug via `sb.schema('economy_map').from('block_body_versions').select('body_md').eq('block_slug', slug).eq('status','draft').order('created_at',{ascending:false}).limit(1)`, assigning `bodyMd` only on a non-empty array result (`.limit(1)` + array, NOT `.single()`). Graceful-degrade to body-less on any error/empty — never throws. `renderBlock` is unmodified; its existing `marked.parse` (:586) turns the in-body `#/map/<slug>` cross-links into real `<a href>` elements (LINK-01). The pre-existing published-body fetch keeps its no-`.eq('status','published')` posture (D-17 unchanged).

### Task 3 — `renderHub` hub-intro render + prose-block-list trim (D-06a/c, HUB-01) — commit `d241210`
- **Fetch:** `loadHub` fetches the `agent-economy` `status='draft'` body the same way as Task 2 (behind `PREVIEW_ENABLED`), passing it into `renderHub(data, hubBodyMd)`.
- **Trim:** a pure helper `trimHubBody(md)` cuts the markdown string at the literal `## Tier 1` heading (dropping the Tier-1/Tier-2 prose block-list — the 7 `[Title →](#/map/<slug>)` links that duplicate the cards) and re-appends the closing `## The thesis, restated` tail. Defensive: returns the input unchanged if `## Tier 1` is absent (never silently drops unbounded content).
- **Render:** the `HUB_STORYLINE` html-assembly line is replaced with `marked.parse(trimmedHubBody)` when a hub draft body is present, falling back to the existing `escapeHtml(HUB_STORYLINE)` form otherwise (`HUB_STORYLINE` is NOT deleted). The card grid, `renderTile`, and the three tier filters are untouched — no hub card (`tier='hub'` already excluded); the block list renders once, as cards (HUB-01).

## Verification — all three plan `<automated>` gates PASS

Run against the live edited `docker/web/site/app.js` (comments stripped before regex, per the gate harness):

```
===== GATE A (Task 1: PREVIEW_ENABLED) =====
PASS
===== GATE B-1 (Task 2: draft-fetch filters) =====
PASS
===== GATE B-2 (Task 2: parse) =====
PASS: app.js parses
===== GATE C (Task 3: hub intro + trim) =====
PASS
```

- **Gate A** — `PREVIEW_ENABLED` defined AND `searchParams.get('preview')` present.
- **Gate B-1** — draft fetch has `block_body_versions` + `.eq('block_slug')` + `.eq('status','draft')` + `.order('created_at')` + `.limit(1)`, and does NOT use `.single()` on the draft path.
- **Gate B-2** — app.js parses (advisory; the full harness is in 17-02).
- **Gate C** — `agent-economy` fetched + `marked.parse` used + `HUB_STORYLINE` fallback retained + `## Tier 1` cut-point referenced.

### Functional trim proof (`trimHubBody` against `.planning/docs/00-hub.md`)
```
keeps thesis (Capability is solved): true
keeps How to read this map: true
drops ## Tier 1: true
drops ## Tier 2: true
prose #/map block-links remaining (expect 0): 0  []
keeps ## The thesis, restated: true
```
The trim keeps the thesis + two-tier framing intro, drops all 7 prose `#/map/<slug>` block-links (HUB-01), and re-appends the restated thesis.

### Scope + safety checks
- **Lines 4-5 placeholders intact (no literal key):**
  ```
  const SUPABASE_URL = '__SUPABASE_URL__';
  const SUPABASE_ANON_KEY = '__SUPABASE_ANON_KEY__';
  ```
- **No JWT-shaped token** (`eyJ...`) anywhere in app.js (0 matches); the only `service_role` occurrence is comment text on line 54 describing the 17-02 preview mechanism. T-SVC-ROLE-LEAK mitigation holds — this plan introduces no key value.
- **Single source file:** `git diff --name-only HEAD~3 HEAD` → `docker/web/site/app.js` (only). No migration/schema/RLS/RPC/proxy/pipeline/agent-service file modified.
- **`00-hub.md` untouched** — the trim is in code (the rejected variant was a doc edit + reload), keeping the loaded draft reversible.

## Deviations from Plan

None — plan executed exactly as written. All three tasks implemented per the pinned D-03/D-04/D-06a/c shapes from 17-PATTERNS; no auto-fixes, no architectural changes, no auth gates.

## Known Stubs

None. The `PREVIEW_ENABLED`-gated paths are intentionally dormant in production (D-04 double-safe design, not a stub) and are exercised behind the explicit preview flag. The behavioral + no-op + service_role-leak-guard proofs against the running local preview container are deliberately deferred to plan 17-02 per the plan's acceptance criteria — this plan is a pure JS edit.

## Threat Flags

None. No new network endpoint, auth path, file-access pattern, or schema change introduced. The draft-fetch reads (block + hub) are gated by `PREVIEW_ENABLED` and bounded by anon published-only RLS in prod (double-safe, T-17-DRAFT-EXPOSE mitigation per the plan's threat_model); the `marked.parse` XSS surface is the carried-accept disposition T-17-XSS-MD (compensating control = the operator publish gate), unchanged from the live `renderBlock`/`renderArticle` path.

## Self-Check: PASSED

- Created file `.planning/phases/17-cross-link-wiring-preview/17-01-SUMMARY.md`: FOUND (this file).
- Commit `0c5b82b` (Task 1): present on HEAD~3.
- Commit `124d792` (Task 2): present on HEAD~2.
- Commit `d241210` (Task 3): present on HEAD~1.
- All three modify only `docker/web/site/app.js`.
