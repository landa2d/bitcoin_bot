---
phase: 23-distinct-newsletter-excerpts
plan: 02
subsystem: web-frontend
tags: [deploy, scoped-rebuild, web, live-verify, excerpt, orchestrator-owned, worktree-unsafe]
requires:
  - "Plan 23-01 source changes (excerpt helpers + renderList indexed-row rewrite + .row CSS) committed on main"
  - "config/.env present on the main tree (anon SUPABASE_URL/KEY) — absent in worktrees, hence worktree-unsafe"
  - "the web entrypoint __SUPABASE_*__ sed-substitution (renders at container start)"
provides:
  - "Phase 23 excerpt render deployed live to aiagentspulse.com via scoped web rebuild"
  - "operator-confirmed live proof of EXCERPT-01 (ed29 ≠ ed30 in both modes, indexed-row format, no leaked URLs)"
affects:
  - "running agentpulse-web container (recreated from rebuilt docker-web image; no other service touched)"
tech-stack:
  added: []
  patterns:
    - "scoped `docker compose up -d --build web` from the absolute main tree (SERVICE key web, NO --delete, NO full deploy.sh)"
    - "verify the SUBSTITUTED /srv/app.js on the deployed container, not raw source bytes (Phase 22 reproduce-on-live lesson)"
    - "orchestrator-owned real-data pre-check: shipped extractDistinctExcerpt run against live anon-REST ed29/ed30 before the human-verify gate"
key-files:
  created:
    - "/tmp/live_excerpt_verify.mjs (orchestrator-authored live real-data harness — NOT shipped/committed)"
  modified: []
decisions:
  - "Ran the whole phase no-worktree / sequential on the main tree: Plan 23-02's deploy is worktree-unsafe (config/.env gitignored → absent in worktrees; build context + deployed container live on the main tree). The workflow's per-plan submodule gate would not have caught this (no submodules), so it was applied deliberately per the plan + the Phase 20–22 precedent."
  - "Pre-deploy gate satisfied: prod↔main drift shown (running container 3 days old, serving stale app.js with class=\"row\" count 0), /diff confirmed scoped to docker/web/site/{app.js,style-shared.css} only (0 migrations, 0 other-service files, 0 __SUPABASE_* placeholder-line changes); operator selected approve-deploy."
  - "Augmented the human-verify gate with an orchestrator real-data check: fetched editions 29 & 30 via the anon REST endpoint and ran the shipped extractDistinctExcerpt — ed29≠ed30 in BOTH modes, no boilerplate / recap / URL leak, D-04 thin-pivot append fired on ed29-tech. Visual layout/regression confirmed by the operator on the live site."
metrics:
  duration: ~9min
  tasks: 3
  files: 0
  completed: 2026-06-15
---

# Phase 23 Plan 02: Ship + Live-Verify Distinct Excerpts

## What shipped

The Phase 23 excerpt changes are **live on aiagentspulse.com**. The newsletter
archive now renders the strip-at-render indexed-row format (number · title ·
one-line summary · date), with each edition's first genuinely-distinct
"This week…" sentence surfaced — boilerplate header + recap intro skipped,
link URLs cleaned, 2-line clamped, mode-aware. **EXCERPT-01 is proven on the
real ed29/ed30 data in both modes.**

## Tasks

| Task | Type | Result |
|------|------|--------|
| 1. Pre-deploy gate (drift + /diff + approval) | checkpoint:decision | ✅ Approved — scope confirmed (2 web files, 0 migrations, 0 other services, placeholders untouched); running container shown stale |
| 2. Scoped `web` rebuild from main tree | auto | ✅ `docker compose up -d --build web` — agentpulse-web Up; served /srv/app.js substituted (0 `__SUPABASE_URL__` literal, real host baked in), `class="row"`=1, `substring(0,150)`=0, CSS clamp present; no `--delete`, only `web` rebuilt |
| 3. Live-render verification | checkpoint:human-verify | ✅ Operator approved on the live site (indexed rows, ed29≠ed30 both modes, 2-line clamp, no regression on hero / mode toggle / #/edition deep-links / maturity pill) |

## Live real-data proof (orchestrator pre-check, before the human gate)

Ran the shipped `extractDistinctExcerpt` against editions 29 & 30 fetched from
the production anon REST endpoint:

- **Technical** — ed29: "This week it got specific. Researchers exposed BadHost…" · ed30: "The payments thesis crossed into consumer scale: Block kicked off Cash App's phased stablecoin rollout…"
- **Strategic** — ed29: "This week the gap got more concrete, and the timing is uncomfortable." · ed30: "This week both halves of that story moved hard."

All assertions passed: ed29 ≠ ed30 in both modes; no "Read This, Skip the Rest",
no "Last week…" recap, no leaked `(https://…)` URL, no `](`; D-04 thin-pivot
append fired on ed29-tech.

## Deploy discipline

- Scoped `docker compose up -d --build web` from `/root/bitcoin_bot/docker`
  (SERVICE key `web`, **no** `--delete`, **no** `scripts/deploy.sh`).
- Verified the **substituted** `/srv/app.js` on the running container (not raw
  source bytes); `__SUPABASE_URL__` literal count 0, real Supabase host present.
- Pre-existing `openclaw-rivalscope` orphan-container warning ignored
  (`--remove-orphans` deliberately NOT passed — minimal blast radius).

## Deviations

None. Plan executed as written. Drove the plan inline as the orchestrator
(rather than a spawned executor) because it is orchestrator-owned and
worktree-unsafe (live `docker compose` + operator gates).

## Self-Check: PASSED

- SC#1 (live): ed29 ≠ ed30 in both Technical and Strategic modes — proven on real data + operator-confirmed visually.
- SC#2 (live): indexed-row format (number · title · summary · date), 2-line clamp, no leaked URLs — operator-confirmed.
- SC#3: strip-at-render only — 0 migrations, loadList byte-identical (`.in('status')`=2, `.eq('status')`=11), no stored summary field, no pipeline change.
- Deploy discipline + substituted-render verification satisfied; no regression.
