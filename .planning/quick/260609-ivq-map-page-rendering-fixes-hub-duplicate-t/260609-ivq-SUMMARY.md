---
phase: quick-260609-ivq
plan: 01
subsystem: web-frontend
tags: [economy_map, renderer, css, app.js, style-shared.css, style-base.css, marked, sticky-nav]

# Dependency graph
requires:
  - phase: quick-260609-fpc
    provides: "renderBlock leading-title-H1 strip (commit 19115b2) — refactored here into the shared helper"
provides:
  - "renderHub now strips the hub body's duplicate leading `# The Agent Economy` title H1 (title-only — bold tagline kept)"
  - "renderBlock leading-title-H1 strip refactored into a shared stripLeadingTitleH1(md, title) helper (behavior unchanged)"
  - "Site-wide prose paragraph rhythm on --space-lg (24px) + the previously-missing .hub-storyline p rule"
  - "Sticky nav rule re-scoped to `body > header` so the in-content block-header no longer inherits sticky positioning and stops overlapping the nav"
affects: [economy_map render path, web deploy (operator-gated scoped `docker compose up -d --build web`)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared guarded markdown-strip helper reused across renderHub + renderBlock (single source of truth for the leading-title-H1 de-dup)"
    - "Child-combinator selector scoping (`body > header`) to exclude nested same-tag elements from a sticky rule"

key-files:
  created: []
  modified:
    - docker/web/site/style-shared.css
    - docker/web/site/app.js
    - docker/web/site/style-base.css

key-decisions:
  - "TITLE-ONLY de-dup (operator decision 2026-06-09): strip ONLY the duplicate leading title H1; KEEP the bold tagline first line. The chrome has no subtitle element, so the tagline is the sole instance, not a duplicate. Helper named stripLeadingTitleH1 — no subtitle-strip variant."
  - "Reuse the existing --space-lg (24px) token for prose paragraph rhythm (≈ one line of leading at 18px/1.62) rather than introduce a magic px or a parallel spacing system."
  - "Fix the maturity-overlap at the source rule by re-scoping the bare `header {` selector to `body > header {` (child combinator), NOT by adding a competing `.block-header { position: static }` override."

patterns-established:
  - "Pattern: factor the guarded inline H1-strip into a pure module-scoped helper so renderHub and renderBlock share one de-dup implementation (non-match → byte-identical no-op; never alters the DB or the args)."

requirements-completed: [MAP-FIX-01, MAP-FIX-02, MAP-FIX-03]

# Metrics
duration: ~20min
completed: 2026-06-09
---

# Phase quick-260609-ivq Plan 01: Map-page rendering fixes Summary

**Three frontend-only render fixes on the Agent Economy map surface — hub duplicate-title strip (title-only, tagline kept), site-wide prose paragraph rhythm via `--space-lg`, and a sticky-nav re-scope that stops the block-page maturity pill from overlapping the nav — each shipped as an atomic commit on `fix/map-rendering-issues`, no deploy and no merge (operator-gated).**

## Performance

- **Duration:** ~20 min
- **Tasks:** 3/3 completed
- **Files modified:** 3 (docker/web/site/style-shared.css, app.js, style-base.css)

## Accomplishments

- **Hub title de-dup (new path):** `renderHub` now strips the hub body's leading `# The Agent Economy` H1 that duplicated the chrome page-title under `marked.parse`. The bold tagline (`**Capability is solved...**`) is KEPT per the operator's title-only decision. The prior quick-task fix (260609-fpc) only covered the block path; the hub path is now covered too, via a shared helper.
- **Shared helper:** factored the guarded leading-title-H1 strip into a single pure `stripLeadingTitleH1(md, title)` and wired it into BOTH renderHub (composed after `trimHubBody`, title arg `'The Agent Economy'`) and renderBlock (pure refactor of the prior inline strip — byte-equivalent behavior).
- **Prose rhythm:** added the previously-MISSING `.hub-storyline p` paragraph-margin rule (the hub's multi-paragraph published body had been butting together with zero gap), and bumped `.block-body p/li` and `article p` from a hardcoded tight 16px to the `--space-lg` (24px) token — a full-line vertical gap. Scoped to prose containers only; nav/cards/maturity-row/tier-label/status-row/timeline/lists/pre untouched.
- **Maturity overlap:** re-scoped the bare `header { position:sticky; ... }` selector to `body > header {`. The bare type selector had also matched the in-content `<header class="block-header">` emitted by renderBlock, sticking it to viewport-top and riding the maturity pill up over the nav. The child-combinator now matches only the nav shell (the sole `<header>` direct-child of `<body>`); the block-header flows statically and scrolls under the nav.

## Task Commits

Each task was committed atomically (code only):

1. **Task 1: Prose paragraph rhythm via --space-lg + missing .hub-storyline p rule** — `cdff676` (fix)
2. **Task 2: De-dup hub + block title via shared stripLeadingTitleH1 helper (title-only, tagline kept)** — `8ea6a4d` (fix)
3. **Task 3: Re-scope sticky nav rule to body > header so block-header stops overlapping nav** — `9e350f3` (fix)

_Plan/SUMMARY/STATE docs commit is owned by the orchestrator (not the executor) per the sequential-execution constraints._

## Files Created/Modified

- `docker/web/site/style-shared.css` — Added `.hub-storyline p { margin-bottom: var(--space-lg) }` (+ `:last-child` zero-out and `h2` top-margin); changed `.block-body p,.block-body li` and `article p` `margin-bottom` from `16px` to `var(--space-lg)`.
- `docker/web/site/app.js` — Added module-scoped `stripLeadingTitleH1(md, title)` near `trimHubBody`; renderBlock branch C now calls it (refactor of the inline strip); renderHub composes `stripLeadingTitleH1(trimHubBody(hubBodyMd), 'The Agent Economy')`. Chrome `<h1 class="page-title">` + `updated` subline and the `__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` placeholders left byte-intact.
- `docker/web/site/style-base.css` — Changed the bare `header {` sticky-nav selector to `body > header {` (selector scope only; `top`/`z-index`/`background`/`backdrop-filter`/`border-bottom` values unchanged); added a scope-explaining comment.

## Verification

All 13 `<automated>` gates across the three tasks were run against the live modified files on `fix/map-rendering-issues` and the printed output confirmed (not just exit codes):

**Task 1 (style-shared.css):**
- `HUB-PARA-RULE-TOKENIZED` — `.hub-storyline p` uses `var(--space-lg)`
- `ARTICLE-P-TOKENIZED` — `article p` uses `var(--space-lg)` (awk-scoped to that rule)
- `BLOCK-P-TOKENIZED` — `.block-body p` uses `var(--space-lg)` (awk-scoped)
- `CSS-BRACES-BALANCED (125)`

**Task 2 (app.js):**
- `JS-SYNTAX-OK` (`node --check`)
- `PLACEHOLDERS-INTACT (2)`
- `RESULT: PASS` — `python3 scripts/verify_economy_map_crosslinks.py --guard-only`, exit 0 (PLACEHOLDER-INTACT + SVC-ROLE-NOT-IN-WEB-DEPLOY-PATH)
- `HELPER-WIRED-BOTH-PATHS` — `stripLeadingTitleH1` appears 4× (1 def + 2 calls + 1 comment ref) ≥3
- `NO-SUBTITLE-STRIP` — `stripLeadingTitleAndSubtitle` ABSENT

**Task 3 (style-base.css):**
- `NAV-RULE-RESCOPED` — `body > header` present
- `NO-BARE-HEADER-SELECTOR` — no `^header {`
- `STICKY-STILL-ON-NAV` — `body > header` retains `position:sticky`
- `CSS-BRACES-BALANCED (22)`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Verify-gate `grep -Pzoq` patterns required same-line declarations under ugrep**

- **Found during:** Task 1 (Gate 1) and again in Task 3 (Gate 3).
- **Issue:** The system `grep` is **ugrep 7.5.0**, not GNU grep. In ugrep's `-Pz` mode the negated character class `[^}]*` (and `.*` without `(?s)`) does NOT cross newlines by default. The plan's gate patterns (`\.hub-storyline p[^{]*\{[^}]*margin-bottom:\s*var(--space-lg)` and `body > header[^{]*\{[^}]*position:\s*sticky`) therefore require the matched declaration to sit on the SAME line as the opening brace. With the declaration on the next line (conventional multi-line CSS) the gates returned NOMATCH even though the CSS was correct (confirmed: the same pattern also fails against the pre-existing multi-line `header {` rule). This was a blocking issue: the verify gate could not pass with correctly-written multi-line CSS.
- **Fix:** Wrote the two gate-targeted rules with the relevant declaration on the same line as the brace — `.hub-storyline p { margin-bottom: var(--space-lg); }` and `body > header { position:sticky;` (rest of the nav rule unchanged on subsequent lines). Both are valid, idiomatic CSS and change no values; they simply satisfy the ugrep `[^}]*` semantics so the gate proves the intended fact.
- **Files modified:** docker/web/site/style-shared.css, docker/web/site/style-base.css
- **Commits:** cdff676 (Task 1), 9e350f3 (Task 3)
- **Note:** No behavior change vs. the plan's intent — the rules apply exactly the values the plan specified (`var(--space-lg)`; the unchanged sticky/top/z-index/background/backdrop-filter/border-bottom). Only the source formatting was adjusted so the deterministic verify gate passes under the actual toolchain.

### Authentication Gates

None.

## Known Stubs

None. All three fixes wire real behavior; no placeholder/empty-value stubs introduced.

## Out-of-scope / Operator-gated (NOT done by the executor)

- **Deploy (going live):** scoped rebuild from the MAIN tree `cd /root/bitcoin_bot/docker && docker compose up -d --build web` (service key `web`; entrypoint.sh substitutes the placeholders at container start). Owned by the orchestrator after operator `/diff` review + approval.
- **Merge of `fix/map-rendering-issues`:** operator-gated, not done here.
- **Optional body re-publish (flagged, NOT in must-have path):** the renderer strip (Task 2) fully neutralizes the duplicate title at render time, so the stored economy_map bodies do not need rewriting for the must-have. Cleaning the leading `# <Title>` out of the stored rows is an OPTIONAL, separate operator-gated step via the existing append-only canonical-body-rewrite path — flagged for operator decision, out of scope for this plan.

## Pre-existing advisory (out of scope, unchanged)

The crosslinks guard re-emits its standing ADVISORY: the service_role key's distinguishing substring is present in `.claude/settings.local.json` — a PRE-EXISTING leak (committed 2026-04-30, 0e42a5a), NOT introduced by this work and NOT in the web-deploy path. Rotation + history scrub remains a separate credentials/infra task (operator decision). The guard still returns `RESULT: PASS` / exit 0.

## Self-Check: PASSED

- Files exist: `docker/web/site/style-shared.css`, `docker/web/site/app.js`, `docker/web/site/style-base.css`, and `.planning/quick/260609-ivq-map-page-rendering-fixes-hub-duplicate-t/260609-ivq-SUMMARY.md` — all FOUND.
- Commits exist: `cdff676` (Task 1), `8ea6a4d` (Task 2), `9e350f3` (Task 3) — all FOUND on `fix/map-rendering-issues`.
- No code committed outside the three scoped files; docs artifacts (PLAN/SUMMARY/STATE/ROADMAP) intentionally left for the orchestrator per the sequential-execution constraints.
