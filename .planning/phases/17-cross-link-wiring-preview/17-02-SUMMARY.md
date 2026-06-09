---
phase: 17-cross-link-wiring-preview
plan: 02
subsystem: web-frontend, verification-tooling
tags: [economy-map, preview, cross-link, fail-loud, service-role-guard, harness, checkpoint]
requires:
  - "Plan 17-01: PREVIEW_ENABLED flag + draft-fetch render path in app.js"
  - "Phase 16 load: hub agent-economy + 7 block bodies present as status='draft' with proposed_maturity set in economy_map.block_body_versions"
  - "15-CONTRACT: anon RLS block_body_versions USING(status='published'); service_role bypasses RLS; blocks roster = blocks.slug"
provides:
  - "scripts/verify_economy_map_crosslinks.py — fail-loud #/map/<slug> extraction + in-roster assertion (D-05 automated half) + D-02 service_role-leak guard"
  - "Verified local-only elevated preview path (D-01/D-02) proving the loaded drafts render publish-ready"
  - "Operator click-through approval (PREV-01 / LINK-01 / HUB-01) — the last gate before Phase 18 publishes"
affects:
  - "scripts/verify_economy_map_crosslinks.py (new harness)"
  - "docker/web/site/app.js (preview-maturity deviation fix — commit 356cd05)"
tech-stack:
  added: []
  patterns:
    - "Python-service direct PostgREST + Accept-Profile: economy_map (mirrors scripts/load_economy_map_content.py; NEVER supabase-py .in_())"
    - "fail-loud sys.exit(nonzero) on any off-roster cross-link target (guards future content drift)"
    - "throwaway local preview container: distinct name/port, service_role via SUPABASE_ANON_KEY env, unchanged entrypoint.sh sed-substitution, served-not-raw-dir"
key-files:
  created:
    - "scripts/verify_economy_map_crosslinks.py — fail-loud cross-link harness + D-02 guard (commit 6ed95f9)"
    - ".planning/phases/17-cross-link-wiring-preview/deferred-items.md — DEF-17-01 pre-existing service_role leak (commit 6ed95f9)"
  modified:
    - "docker/web/site/app.js — preview-aware maturity pill + non-deferred draft cards (deviation fix, commit 356cd05)"
decisions:
  - "D-05 (fail-loud + exhaustive): harness asserts all 22 #/map/<slug> instances → 7 distinct in-roster targets, none to regulation-legal; exits non-zero on any miss"
  - "D-01/D-02 (local-only elevated preview): service_role substituted into a throwaway container only (127.0.0.1:8088), deployed image NOT rebuilt; mandatory diff guard confirms the key ships nowhere tracked"
  - "Deviation (preview-maturity): the pill must read the draft's proposed_maturity in preview (blocks.maturity is stale until the mig-038 publish watermark), and a draft-bearing block is not DEFERRED — flag-gated, prod no-op"
metrics:
  duration: ~checkpoint cycle (harness + container + 1 deviation fix + operator walk-through)
  completed: 2026-06-09
  tasks: 3
  files: 3
---

# Phase 17 Plan 02: Cross-link Verification, Local Elevated Preview & Operator Gate Summary

Stood up the fail-loud cross-link verification harness (D-05 automated half), built a local-only service_role-elevated preview container (D-01/D-02) that renders the Phase-16 loaded-but-unpublished drafts, proved the service_role key ships nowhere tracked (the mandatory T-SVC-ROLE-LEAK guard), and passed the operator's manual click-through of the full 22-instance cross-link set (PREV-01 / LINK-01 / HUB-01) — with the public live `#/map` confirmed unchanged. Two genuine bugs surfaced at the human checkpoint and were fixed before approval (below). This is the last gate before Phase 18 publishes; no `economy_map` write, no schema/RLS change, no publish performed.

## What Was Built

### Task 1 — Fail-loud cross-link harness (D-05) + D-02 service_role guard — commit `6ed95f9`
`scripts/verify_economy_map_crosslinks.py`, a standalone harness mirroring the Phase-16 loader's direct-PostgREST + `Accept-Profile: economy_map` idiom (NOT supabase-js, NOT the supabase-py `.in_()` array filter): (1) reads the live `blocks` roster; (2) reads every `status='draft'` `block_body_versions` row for the hub + 7 blocks via the service_role key from `config/.env` (no hardcoded key); (3) regex-extracts every `#/map/<slug>` href from each body's markdown; (4) **fail-loud** — asserts every target slug is in the roster, collects all misses, `sys.exit(nonzero)` on any; (5) prints the count summary on success. It ALSO runs the D-02 guard: confirms tracked `app.js` lines 4-5 keep the `__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` placeholders and the service_role key value is in none of the web-deploy-path tracked files.

Harness result (exit 0): **22 cross-link instances → 7 distinct in-roster targets, none to `regulation-legal`** (hub=7, identity-trust=2, memory-context=2, payments-settlement=1, autonomy-control=2, negotiation-coordination=2, governance-accountability=3, psychology-disposition=3). Fail-loud proven (an injected off-roster target makes it exit non-zero).

### Task 2 — Local elevated preview container (D-01/D-02) + harness run — no source commit (throwaway container)
Built image `agentpulse-web-preview17:local` from this branch's `docker/web/` and ran a throwaway container `agentpulse-web-preview17` on `127.0.0.1:8088` (loopback only — the service_role-elevated preview is never network-exposed), with `SUPABASE_ANON_KEY` set to the service_role key so the UNCHANGED `entrypoint.sh:3-4` sed substitutes it at container start. The deployed/prod `agentpulse-web` container was NOT rebuilt or touched. The served (not raw-dir) `/app.js` was confirmed substituted (0 `__SUPABASE__` placeholders, served key decodes to `role: service_role`) and carrying the 17-01 render path. Harness re-run against the live DB: exit 0.

### Task 3 — Operator manual click-through (PREV-01, LINK-01, HUB-01) — **APPROVED**
Operator opened the local preview and confirmed: HUB-01 (thesis + "How to read this map" intro above the card grid, block list once as cards, no duplicated prose list); LINK-01 (all 7 hub→block cards + the 15 in-body block→block cross-links resolve); PREV-01 (pills render the three distinct stages — emerging / contested / nascent — on the non-published preview); and the spine check (public live `aiagentspulse.com/#/map` unchanged, drafts invisible to anon). Operator response: **"approved"**.

## Deviations from Plan

Three deviations, all surfaced and resolved during execution / the human checkpoint:

1. **[Rule 1 — Bug] `config/.env` loader precedence** (folded into commit `6ed95f9`). `config/.env` carries two `SUPABASE_URL=` lines (a stale placeholder + the real host). First-wins picked the placeholder in a clean env. Fixed to docker-compose **last-wins** semantics so the harness resolves the real host.

2. **[Checkpoint bug — preview-maturity] `app.js` pills showed DEFERRED / stale maturity in preview** (fix commit `356cd05`). Root cause: 17-01 rendered draft *bodies* but the maturity pill still read the stale `blocks.maturity` (which only flips on the Phase-18 publish watermark, mig 038) and the hub cards derived `deferred = !current_body_version_id` (NULL for the 7 unpublished blocks). Verified the draft `proposed_maturity` data is 100% correct in the DB — the gap was purely in the render path. Fix (flag-gated, prod byte-for-byte no-op, no DB write): in preview the loaded draft takes precedence — `loadBlock` reads the draft's `proposed_maturity` into the pill, and the hub card grid fetches per-slug `proposed_maturity` so draft-bearing cards show the correct stage and are never DEFERRED. The preview container was rebuilt to serve the fix.

3. **[Checkpoint finding — instruction bug, no code change] preview URL position.** The flag reader uses `new URL(window.location).searchParams.get('preview')` (the app's `?mode=` query-string convention). The checkpoint instruction told the operator to open `#/map?preview=1`, which places the param *inside* the hash where `searchParams` cannot see it → `PREVIEW_ENABLED=false` and the whole preview path stayed dormant. **Correct URL: `http://127.0.0.1:8088/?preview=1#/map`** (query BEFORE the hash; persists across in-app card navigation). No code change — the idiom matches the existing convention and the router (`getRoute` `hash.split('/')[2]`) would mis-parse a slug if the query were in the hash. Documented here so future preview runs use the correct form.

## Scope + Safety Checks

- **D-02 / T-SVC-ROLE-LEAK guard (HIGH threat) holds:** tracked `app.js` lines 4-5 keep the `__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` placeholders (PLACEHOLDER-INTACT); the service_role key value is in NONE of the web-deploy-path tracked files (app.js, entrypoint.sh, Dockerfile, Caddyfile, docker-compose.yml) and never reaches the deployed image — only the throwaway container's run env carried it.
- **`docker/web/entrypoint.sh` zero diff** — the substitution mechanism was used unchanged.
- **No `economy_map` write, no schema/RLS/RPC/migration/pipeline/proxy/agent-service change.** New file: `scripts/verify_economy_map_crosslinks.py`. The only source edit beyond it is the `356cd05` preview-path deviation fix to `app.js`.
- **Throwaway preview torn down** after approval (container + image + temp Caddyfile removed); prod `agentpulse-web` untouched throughout.

## Threat Flags

- **DEF-17-01 (pre-existing, OUT OF SCOPE — logged to `deferred-items.md`):** the harness's advisory repo-wide scan found the full service_role key committed in tracked `.claude/settings.local.json` (a Bash permission-allowlist entry in git history well before this milestone — NOT introduced by Phase 17, NOT in the web-deploy path). **Recommended operator follow-up (separate credentials/infra task): rotate the service_role key, scrub it from `.claude/settings.local.json` + git history, and gitignore that file.** The phase-scoped D-02 web-deploy guard passes regardless.
- **T-17-XSS-MD (carried accept, T-04-03-01):** `marked.parse` on draft bodies has no sanitizer — same path as the live renderer; compensating control = the operator publish gate (Phase 18). Preview is local-only, so any malicious draft's blast radius is the operator's own browser.

## Self-Check: PASSED

- Created file `scripts/verify_economy_map_crosslinks.py`: FOUND; parses; uses Accept-Profile + sys.exit; no `.in_()`; exits 0 against the live DB.
- Created file `.planning/phases/17-cross-link-wiring-preview/deferred-items.md`: FOUND (DEF-17-01).
- Commit `6ed95f9` (Task 1 harness + D-02 guard): present.
- Commit `356cd05` (preview-maturity deviation fix): present; all three 17-01 app.js gates still pass; placeholders intact; no JWT in web-deploy path.
- D-02 guard: PLACEHOLDER-INTACT + service_role key absent from the web-deploy path.
- Operator approval (Task 3, blocking-human): recorded — PREV-01 / LINK-01 / HUB-01 confirmed, public live `#/map` unchanged.
