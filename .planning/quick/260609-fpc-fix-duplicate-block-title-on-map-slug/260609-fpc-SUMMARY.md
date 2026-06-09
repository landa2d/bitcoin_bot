---
phase: quick-260609-fpc
plan: 01
subsystem: web-frontend
tags: [economy_map, renderer, bug-fix, app.js]
requires: []
provides: ["renderBlock strips the body's leading duplicate <Title> H1 (guarded) before marked.parse"]
affects: ["#/map/<slug> block detail rendering"]
tech-stack:
  added: []
  patterns: ["leading-ATX-H1 strip guarded by trimmed/case-insensitive block.title match"]
key-files:
  created: []
  modified: ["docker/web/site/app.js"]
decisions:
  - "Strip only the FIRST non-empty line when it is an ATX heading whose text == block.title (trim + case-fold); otherwise no-op."
metrics:
  duration: "~5 min"
  completed: "2026-06-09"
---

# Phase quick-260609-fpc Plan 01: Fix Duplicate Block Title on #/map/<slug> Summary

Renderer-only fix: `renderBlock` now strips the body's leading duplicate `# <Title>` H1 (guarded by a trimmed, case-insensitive match against `block.title`) before `marked.parse`, so the block title renders exactly once on `#/map/<slug>` while preserving the tagline and all other body content.

## What Changed

Single targeted edit to `docker/web/site/app.js`, body branch (C) of `renderBlock(block, bodyMd, entries)` (was app.js:749-752):

- Operates on a LOCAL copy (`renderMd`); the `bodyMd` parameter and `block` are not mutated beyond this branch.
- Splits `renderMd` into lines, finds the FIRST non-empty (non-whitespace) line.
- Tests that line against `/^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$/` (any ATX level 1-6; trailing `#*` tolerates closed ATX headings; capture group = heading text). The regex's character class is fixed, so title characters that happen to be regex-special are never interpreted as a pattern — the title only participates in a plain string equality comparison, so escaping is inherently handled.
- Compares `headingMatch[1].trim().toLowerCase()` to `String(block.title).trim().toLowerCase()` — raw markdown heading text vs. raw title (escapeHtml is NOT involved in the comparison).
- ONLY on match: `lines.splice(firstIdx, 1)` drops exactly that one heading line and rejoins; the following blank line and every subsequent line (tagline, sections, links) are left intact, preserving paragraph spacing.
- On non-match: `renderMd` stays byte-equal to `bodyMd` (pure no-op) — a body whose first heading legitimately differs from its title is never altered.
- `bodyHtml = '<section class="block-body">' + marked.parse(renderMd) + '</section>';` now parses the de-duplicated copy.

Untouched as required: header branch (A, the kept styled `<h1>` + maturity pill), tension branch (B), Evolution branch (D), compose line (E), `updateHero`, `loadBlock`, CSS, economy_map data/migrations, and the `__SUPABASE_URL__` / `__SUPABASE_ANON_KEY__` placeholders (app.js:4-5, byte-identical).

## Verification

Both plan `<automated>` gates run against the live modified file on the main tree:

1. `node --check docker/web/site/app.js && echo JS-SYNTAX-OK` → printed `JS-SYNTAX-OK`.
2. `grep -c '__SUPABASE_URL__\|__SUPABASE_ANON_KEY__' docker/web/site/app.js` → `2` (>= 2). `python3 scripts/verify_economy_map_crosslinks.py --guard-only` → `RESULT: PASS` with `PLACEHOLDER-INTACT` + `SVC-ROLE-NOT-IN-WEB-DEPLOY-PATH`, exit code `0` (confirmed separately).

`git diff --stat`: `docker/web/site/app.js` only — 27 insertions, 1 deletion. No other file changed.

Manual reasoning for `#/map/memory-context`: the styled header (A) renders `Memory & Context` once; the body's leading `# Memory & Context` line is now stripped before `marked.parse`, removing the second title; the bolded tagline paragraph (`**The does-it-learn-or-does-it-reset layer.**`) and every later section/paragraph/link render unchanged. Over-stripping is impossible because the splice is gated on exact trimmed/case-insensitive title equality.

## Over-stripping safety argument (done-criterion)

A block body whose first heading does NOT match its title is provably untouched: the only mutation (`lines.splice`) is inside the `if (headingText === ...)` branch. If the first non-empty line is not an ATX heading, `headingMatch` is `null` and the branch is skipped. If it is a heading but its text differs from `block.title` after trim + case-fold, the equality fails and the branch is skipped. In both cases `renderMd === bodyMd`, so `marked.parse` receives the original body. No economy_map data change was needed to establish this.

## Deviations from Plan

None - plan executed exactly as written.

## Deferred / Advisory (pre-existing, out of scope)

The crosslink guard reported an ADVISORY pre-existing leak: the service_role key's distinguishing substring is present in `.claude/settings.local.json` (committed 2026-04-30, 0e42a5a). This is NOT in the web-deploy path and was NOT introduced by this task. It is a separate credentials/infra concern (key rotation + history scrub) for operator decision — not addressed here.

## Deploy

NOT performed by this executor. Going live is an operator-gated step owned by the orchestrator: `cd /root/bitcoin_bot/docker && docker compose up -d --build web` (service key `web`; container `agentpulse-web`). entrypoint.sh substitutes the placeholders at container start; live verification is on the substituted copy.

## Self-Check: PASSED

- FOUND: docker/web/site/app.js (modified, syntax-valid, diff scoped)
- FOUND: .planning/quick/260609-fpc-fix-duplicate-block-title-on-map-slug/260609-fpc-SUMMARY.md
- Commit hash recorded below in completion output.
