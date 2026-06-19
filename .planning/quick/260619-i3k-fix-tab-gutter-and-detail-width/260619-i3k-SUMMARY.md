---
quick_id: 260619-i3k
slug: fix-tab-gutter-and-detail-width
date: 2026-06-19
mode: quick
status: complete
subsystem: web-frontend
description: Restored the side gutter on all .content-area tabs/sections and widened the agent-economy deep-dives + newsletter editions to the main --wide band
files_changed:
  - docker/web/site/style-shared.css
  - docker/web/site/index.html
commits:
  - abeaa43 fix(260619-i3k): restore side gutter on .content-area (block-only padding)
  - 8e0dd6d fix(260619-i3k): widen edition reader + block deep-dive to --wide band
tags: [css, layout, gutter, width, rhythm-01]
---

# Quick Task 260619-i3k: Tab gutter + detail-route width — Summary

Two operator-reported live-site defects fixed with a CSS/HTML-only change: text was sitting flush against the band edge on every tab/section, and the edition reader + agent-economy block deep-dives rendered narrower than the landing main tabs.

## What changed

### Task 1 — Restore the side gutter (`style-shared.css`)
Root cause: `.content-area` used the physical shorthand `padding: 0 0 var(--space-xl)` plus a separate `padding-top: var(--space-lg)`, which forced `padding-left/right: 0`. Because `style-shared.css` loads *after* `style-base.css`, that physical zero overrode the logical `padding-inline: var(--gutter)` set by `.wide`/`.prose`, killing the side gutter on every `.content-area.*` wrapper.

- `.content-area` (`:129`): now `padding-block: var(--space-lg) var(--space-xl);` + `border-top: 1px solid var(--line-strong);` (dropped the physical `padding` shorthand and the redundant `padding-top` line). Inline padding is now left to `.wide`/`.prose` → gutter restored.
- Mobile override (`@media max-width:600px`, now `:1113`): `.content-area { padding-block: 16px 24px; }` (was `padding: 0 0 24px; padding-top: 16px;`).

The `#landing .prose` (style-base.css:347) and `#landing .wide .wide` (style-base.css:351) neutralizers still zero nested wrappers, so no double-guttering on landing sections.

### Task 2 — Widen detail routes to `--wide` (`index.html`)
- `#reader-view` (`:164`) and `#block-view` (`:172`): wrapper changed from `class="content-area prose"` → `class="content-area wide"`. Editions + block deep-dives now render on the 1080px `--wide` band, matching the landing main tabs (and `#status-view`, already wide).
- `#status-view` and the landing sections were left untouched.

## Verification (PLAN greps)

| Check | Result |
| --- | --- |
| `.content-area` rules use `padding-block`, no inline-zeroing `padding:`/`padding-top:` | PASS — `:129` block-only `padding-block`, `:1113` `padding-block: 16px 24px`; no `padding: 0 0` / `padding-top` resets remain |
| `index.html` reader/block/status wrappers all `content-area wide` | PASS — `:164`, `:172`, `:180` all `content-area wide` |
| No remaining `content-area prose` in `index.html` | PASS — 0 occurrences |
| `style-base.css` untouched (real `padding-inline` declarations intact) | PASS — `git diff --name-only HEAD~2 HEAD` shows only `index.html` + `style-shared.css`; the 4 actual `padding-inline` decls (lines 121, 127, 347, 351) are present |
| No NEW hex literals (RHYTHM-01, token-only) | PASS — changed lines are token-based padding + class attributes only; zero hex added |

## Deviations from Plan

None affecting code. One spec-wording clarification: the PLAN's verify said `grep -c "padding-inline" docker/web/site/style-base.css` "still 4", but `grep -c` returns **6** because two of those lines (74, 116) are prose comments that mention "padding-inline", not declarations. The 4 actual CSS declarations are unchanged and the file was never edited — verify intent (style-base.css untouched) is satisfied.

## Out of scope / handoff
- `app.js` was NOT edited (avoids parse-time SyntaxError on the raw-served SPA).
- Deploy is orchestrator-owned + operator-gated: prod↔main drift check, `/diff`, operator approval, then `docker compose up -d --build web` (no `--delete`/`--remove-orphans`) from the main tree, followed by operator live-render confirmation. NOT part of this executor's task.

## Self-Check: PASSED
- `docker/web/site/style-shared.css` — FOUND, both `.content-area` rules use `padding-block`
- `docker/web/site/index.html` — FOUND, reader/block/status all `content-area wide`
- Commit `abeaa43` — FOUND in `git log`
- Commit `8e0dd6d` — FOUND in `git log`
