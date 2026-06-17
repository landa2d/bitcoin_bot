---
phase: 24-signals-section
plan: 03
subsystem: ops
tags: [supabase, mcp, apply-migration, anon-rest, deploy, scoped-rebuild, fail-loud, signals]

# Dependency graph
requires:
  - phase: 24-signals-section (Plan 01)
    provides: "supabase/migrations/044_signals_anon_view.sql — the security-definer view + anon GRANT this plan applies live"
  - phase: 24-signals-section (Plan 02)
    provides: "the fetchSignals/renderSignals frontend this plan rebuilds into the live web container"
provides:
  - "migration 044 applied LIVE to project zxzaaqfowtqvmsbitqpu via the Supabase MCP apply_migration tool (recorded version 20260617085700)"
  - "live anon read path proof: signals_feed reachable (HTTP 200), bounded to exactly the 5 whitelisted columns, tier-1 newest-first rows, base source_posts still anon-blocked"
  - "Phase 24 frontend deployed via an operator-approved scoped `docker compose up -d --build web` (no --delete); substituted /srv/app.js verified live"
  - "operator-verified SIGNAL-01..04 on the live site; REQUIREMENTS marked Complete"
affects: [25-responsive-accessibility-pass]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Orchestrator-owned, worktree-unsafe live apply: migration via Supabase MCP apply_migration from the main tree (NOT supabase db push, NOT a worktree executor)"
    - "Bounded-anon-read live proof: assert column ceiling + row scope + base-table block against the LIVE view with the anon key, not just the source SQL"
    - "Scoped, operator-approved deploy: /diff the changed web files → approval → `docker compose up -d --build web` (service key web, no --delete) → verify the SUBSTITUTED /srv build"

key-files:
  created: []
  modified: []   # no source files — this plan applies + deploys + verifies the Plan 01/02 outputs

key-decisions:
  - "Applied ONLY migration 044 (the milestone's only migration); pre-existing unapplied 043 left untouched — out of Phase 24 plan scope, surfaced as a carry-over"
  - "Deployed without --remove-orphans — the openclaw-rivalscope orphan warning is pre-existing and unrelated; a scoped deploy must not delete out-of-scope containers"

patterns-established:
  - "Prove the security boundary against the live view (anon select=* key set + anon select=body error + base-table anon block), not the source migration, before sign-off"

requirements-completed: [SIGNAL-01, SIGNAL-02, SIGNAL-03, SIGNAL-04]

# Metrics
duration: live-apply + deploy + operator verify
completed: 2026-06-17
---

# Phase 24 Plan 03: Signals Section — Live Apply + Deploy + Verify

**Took the Plan 24-01 migration and Plan 24-02 frontend live (orchestrator-owned, worktree-unsafe): applied migration 044 via the Supabase MCP `apply_migration` tool, proved the anon read path is reachable AND column/row-bounded against the live view, ran an operator-approved scoped `web` rebuild, and operator-verified SIGNAL-01..04 + fail-loud + no regression on the live site.**

## Tasks

### Task 1 — [BLOCKING] Apply migration 044 live + prove the bounded anon read path — PASSED
- Migration `044_signals_anon_view` applied to live project `zxzaaqfowtqvmsbitqpu` via the **Supabase MCP `apply_migration` tool** (`{"success":true}`); confirmed in the migrations list as version `20260617085700`. Not `supabase db push`, not a worktree executor — orchestrator from the main tree.
- Live anon-key REST proofs (anon key + URL from `config/.env`; no secrets recorded):

  | Assertion | Endpoint (anon key) | Result |
  |-----------|---------------------|--------|
  | SIGNAL-04 reachability gate | `GET /rest/v1/signals_feed?select=id&limit=1` | **HTTP 200** (rows) — never 4xx |
  | D-01 column ceiling | `GET .../signals_feed?select=*&limit=1` | keys exactly `id, scraped_at, source, source_url, title` (the 5 whitelisted) |
  | D-01 column ceiling | `GET .../signals_feed?select=body&limit=1` | **HTTP 400** `42703 column signals_feed.body does not exist` |
  | Row scope | `GET .../signals_feed?...&limit=5` | 5 rows, newest-first `scraped_at DESC` confirmed, all `source_url` non-null (tier-1 arxiv/RSS) |
  | T-24-10 base-table block | `GET .../source_posts?select=body&limit=1` (anon) | **HTTP 200 `[]`** — RLS filters all rows, no `body` leaked |

  → The BLOCKING gate passed: the anon key reads tier-1 source links through `public.signals_feed`, bounded to exactly the 5 columns / tier-1 rows, with the base table still anon-blocked (T-24-09 / T-24-10 / T-24-11 mitigated against the live view).

### Task 2 — Pre-deploy gate + scoped web rebuild (main tree, worktree-unsafe) — PASSED
- prod↔main drift: `/root/bitcoin_bot` IS prod (local scoped rebuild, no remote rsync target). The `agentpulse-web` container was running the pre-24 build (up 22h).
- `/diff` of the three changed web files (`app.js +109`, `style-shared.css +33`, `index.html` placeholder removal) presented for review; **operator approved** the scoped rebuild (AskUserQuestion → "Approve & rebuild web").
- Ran `docker compose up -d --build web` (SERVICE key `web`, **NO `--delete`**, no full deploy script) from `/root/bitcoin_bot/docker`. `agentpulse-web` recreated and **healthy** (`Up`, image `docker-web`). No other service rebuilt or deleted; deployed WITHOUT `--remove-orphans` (the pre-existing `openclaw-rivalscope` orphan is unrelated and out of scope — T-24-12 scoped blast radius preserved).
- Verified the **substituted** `/srv/app.js` inside the running container (not source — Phase 22 lesson): `0` literal `__SUPABASE_URL__` remaining, live `supabase.co` host substituted in, `fetchSignals`×5, `signals_feed`×2, `0` "Coming soon." in `/srv/index.html`. Caddy serves (`HTTP 308` HTTP→HTTPS redirect).

### Task 3 — Live-render verification of SIGNAL-01..04 + fail-loud + no regression — PASSED
- Operator verified on the live site (`aiagentspulse.com`, substituted build) and responded **"approved"**:
  - SIGNAL-01: capped tier-1 feed newest-first + working inline "View all" (no route).
  - SIGNAL-02: rows are external `<a>` (date · headline · domain), `target="_blank"` + `rel="noopener noreferrer"` + `↗`.
  - SIGNAL-03: `#signals` reachable via scroll-spy + `#signals` deep-link.
  - SIGNAL-04: feed renders with the migration applied; fail-loud diagnostic + `console.error` is the broken-path branch, benign empty on a thin week — not a silent empty feed.
  - No Phase 21/22/23 regression observed.

## Files Created/Modified
None — this plan applies (migration 044), deploys (scoped `web` rebuild), and verifies the Plan 24-01 / 24-02 outputs. The only tracked writes are the SUMMARY + REQUIREMENTS/STATE/ROADMAP tracking updates.

## Decisions Made
- **Applied only migration 044.** The migrations list shows the live DB jumps 042 → 044 — pre-existing **migration 043 (`economy_map_hub_and_negotiation_blocks`) is unapplied**. Plan 24-03's scope is "the milestone's ONLY migration" (044); 043 is a carry-over advisory (noted in STATE.md), NOT a Phase 24 plan task, so it was deliberately left untouched. Surfaced for a future decision.
- **No `--remove-orphans`.** A scoped deploy must not delete out-of-scope containers; the `openclaw-rivalscope` orphan warning is pre-existing and unrelated.

## Deviations from Plan
None. Each task executed exactly as written. (The migration apply used the MCP `apply_migration` tool as the plan mandates; the deploy was scoped and operator-gated as the plan mandates.)

## Issues Encountered
- Initial bash anon-REST probe tripped on the shell snapshot's `set -u` (`ZSH_VERSION` unbound) and malformed quote-stripping; re-ran the proofs cleanly in Python (urllib) — no impact on result.
- `grep -c` produced no stdout under the sandbox for some counts; confirmed all source/substitution assertions with Python `str.count()` instead (deterministic).

## Carry-overs / Notes
- **Migration 043 unapplied on live** — out of Phase 24 scope; candidate for a follow-up (the audit milestone / economy_map work).
- Pre-existing orphan container `openclaw-rivalscope` (unrelated to v2.2).

## Self-Check: PASSED
- Migration 044 in the live migrations list (version `20260617085700`) — CONFIRMED.
- Anon `signals_feed` GET → 200; `select=*` → exactly 5 keys; `select=body` → 400; base `source_posts` body anon-unreadable — ALL CONFIRMED live.
- `agentpulse-web` healthy; substituted `/srv/app.js` carries the live config + signals code — CONFIRMED.
- Operator approved the live SIGNAL-01..04 + no-regression verification — CONFIRMED.
- SIGNAL-01..04 marked Complete in REQUIREMENTS.md — CONFIRMED.

---
*Phase: 24-signals-section*
*Completed: 2026-06-17*
