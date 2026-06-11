---
phase: 21-single-scroll-landing-scroll-spy-nav
plan: 02
subsystem: web-frontend
tags: [scroll-spy, intersection-observer, scroll-restore, smooth-scroll, reduced-motion, app.js, style-base.css]
dependency_graph:
  requires:
    - "Plan 01 (SCROLL-01) two-mode router + #landing/4-section DOM: getRoute() {mode:'landing'|'detail'}, route() mode branch, showLanding()/showDetail() split, landingScrollY + landingDataLoaded module vars, the bare-anchor nav (.tab href==section id) + the four <section id> in the LOCKED order newsletter/signals/map/about"
    - "Phase 20 width/rhythm tokens (--line-strong, --space-md, --space-xl) + the body > header sticky rule — consumed, untouched"
  provides:
    - "initScrollSpy() — ONE IntersectionObserver (rootMargin -50%/-50%) over the four static-literal section ids, toggling .active + aria-current on the .tab anchors (NAV-02 a11y parity); registered once at init"
    - "showLanding() scroll-to-section (scrollIntoView, no JS behavior branch) + initial active-tab sync (Pitfall 3) BEFORE the IO takes over"
    - "route() detail->back scroll restore via window.scrollTo(0, landingScrollY) (cameFromDetail one-shot guard); explicit section anchor scrolls to that section instead"
    - "The four net-new CSS rules: html scroll-behavior:smooth + prefers-reduced-motion gate; #landing>section scroll-margin-top; #landing>section + section major rhythm"
  affects:
    - "Task 3 (orchestrator-owned): the scoped `web` rebuild + holistic live-render verify of SCROLL-01/02 + folded WIDTH-01/RHYTHM-01 — gates SCROLL-02 / plan completion on operator sign-off"
    - "Phase 25 (responsive + a11y pass): the reduced-motion gate + scroll-spy aria-current are the seam the full a11y pass extends"
tech_stack:
  added: []
  patterns:
    - "IntersectionObserver scroll-spy (rootMargin '-50% 0px -50% 0px' viewport-centre band) — the first IO usage in the codebase; wiring (one-time top-level registration, static-literal ids, .tab/.active toggle) extends house patterns"
    - "Module-var scroll restore (landingScrollY + cameFromDetail one-shot flag) over history.scrollRestoration/sessionStorage (locked choice)"
    - "Declarative CSS scroll (scroll-behavior:smooth + scroll-margin-top), reduced-motion-gated via @media — first scroll/motion CSS in the codebase"
key_files:
  created: []
  modified:
    - "docker/web/site/app.js — initScrollSpy() + setActiveTabForSection() helper + LANDING_SECTION_IDS; showLanding() initial-active sync + scrollIntoView; route() detail->back landingScrollY restore (cameFromDetail guard); initScrollSpy() registered in DOMContentLoaded"
    - "docker/web/site/style-base.css — html scroll-behavior:smooth + prefers-reduced-motion gate; #landing>section scroll-margin-top:calc(60px + var(--space-md)); #landing>section + section border-top 1px var(--line-strong) + padding-top var(--space-xl)"
decisions:
  - "Scroll-spy active = setActiveTabForSection (href==='#'+id match), replicating setActiveTab's classList.toggle('active')+aria-current pair exactly — NAV-02 a11y parity, no new .active CSS rule"
  - "Detail->back restore guarded by a cameFromDetail one-shot flag (set in the detail branch, cleared on the next landing entry) AND a raw-hash check: the ROOT landing hash ('#/'/'') restores landingScrollY; an EXPLICIT section anchor (#map/#signals/#about/#newsletter) scrolls to that section instead (no restore)"
  - "Smooth-scroll + reduced-motion + sticky offset are ALL declarative CSS (scroll-behavior + scroll-margin-top + @media) — so showLanding's programmatic scrollIntoView needs no JS reduced-motion branch (CSS owns it)"
metrics:
  duration: ~7min
  completed: 2026-06-11
  tasks: "2 of 3 (Task 3 = orchestrator/operator-owned checkpoint, PENDING)"
  files: 2
  commits: 2
---

# Phase 21 Plan 02: Scroll-Spy + Scroll-Restore (SCROLL-02) Summary

Layered the SCROLL-02 behaviors onto the Plan 01 two-mode landing: an `IntersectionObserver` scroll-spy that highlights the active nav tab as the user scrolls, declarative smooth-scroll + sticky-header offset (reduced-motion-gated CSS), and the detail→back landing scroll restore consuming `landingScrollY` — all source-only. The deploy + holistic live-render verification (Task 3) is **orchestrator/operator-owned and PENDING** (this executor's scope was the two `type="auto"` code tasks only).

## What Was Built

**Task 1 — scroll-spy IO + landing scroll/active-sync + detail→back scroll restore in `app.js` (commit `921f6dd`):**
- `LANDING_SECTION_IDS = ['newsletter','signals','map','about']` — STATIC LITERALS in the LOCKED order; these ids are passed to `getElementById`/`observe`/`scrollIntoView` and NEVER derived from `location.hash` (Security V5 / T-21-04).
- `setActiveTabForSection(sectionId)` — toggles `.active` + sets/clears `aria-current='page'` on the `.tab` anchor whose `href === '#' + sectionId`, replicating `setActiveTab`'s `classList.toggle`+`aria-current` pair exactly (NAV-02 a11y parity). Reused by both the IO and the initial sync.
- `initScrollSpy()` — ONE `IntersectionObserver` constructed with `{ rootMargin: '-50% 0px -50% 0px' }` (the canonical viewport-centre band), observing the four section elements (defensively skipping any absent); on an entry's `isIntersecting` it highlights the matching tab via `setActiveTabForSection`. Defensively no-ops if `IntersectionObserver` is unavailable. Registered ONCE in `DOMContentLoaded` after `route()`.
- `showLanding(section)` — after the show/hide + data load, sets the initial `.active` on the target section's tab (Pitfall 3 — the IO fires zero events while `#landing` was `display:none`, so a stale tab would otherwise persist on return-from-detail) BEFORE the IO takes over, then `scrollIntoView({ block: 'start' })` to the section (NO JS behavior branch — Task 2 CSS owns smoothness + the sticky offset); falls back to `window.scrollTo(0,0)` if the section is missing.
- `route()` landing branch — restores `window.scrollTo(0, landingScrollY)` on detail→back to the ROOT landing hash, guarded by a `cameFromDetail` one-shot flag (set in the detail branch, cleared on the next landing entry) AND a raw-hash re-inspect: an EXPLICIT bare section anchor (`#map`/`#signals`/`#about`/`#newsletter`) scrolls to that section (via `showLanding`'s `scrollIntoView`) instead of restoring. Module-var restore only — no `history.scrollRestoration`/`sessionStorage` (locked).
- No `setActiveTab` call on the landing (IO + the initial sync own it — Anti-Pattern avoided); no `source_posts` fetch added; the `__SUPABASE_*__` placeholders intact; no Supabase query changed.

**Task 2 — four net-new CSS rules in `style-base.css` (commit `b9bb5bc`):**
- `html { scroll-behavior: smooth; }` (single line) — declarative smooth-scroll on nav-anchor clicks.
- `@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }` — the MANDATORY reduced-motion gate (A11Y-01 must-not-regress; the net-new motion is motion-safe).
- `#landing > section { scroll-margin-top: calc(60px + var(--space-md)); }` (single line) — anchor jumps land the heading BELOW the sticky `body > header`, not clipped (Pitfall 2); the `60px` is the rendered-header estimate flagged for live-render tuning (research A7).
- `#landing > section + section { border-top: 1px solid var(--line-strong); padding-top: var(--space-xl); }` (single line) — one full-strength rule between each major landing section, extending the existing `.tier-section + .tier-section` adjacent-sibling major-boundary pattern (RHYTHM-01).
- Token-only (`--line-strong`/`--space-*`), no hex literals; compact single-line rule bodies (gate-friendly `[^}]*` matching); the existing `.tab.active` (reused by the scroll-spy) and the `body > header` sticky rule are byte-unchanged; Phase-20 width tokens untouched.

## Verification

Each task's `<verify><automated>` gate was run against live code and confirmed PASS before its commit, and re-confirmed against the committed state:
- **Task 1:** `node --check` passes; `function initScrollSpy` + `new IntersectionObserver` + `rootMargin: '-50% 0px -50% 0px'` + the static-literal array `['newsletter','signals','map','about']` + `window.scrollTo(0, landingScrollY)` + `aria-current` + the `initScrollSpy()` call present; zero `source_posts`; `const SUPABASE_URL = '__SUPABASE_URL__';` intact. **PASS.** Spot-checks: exactly ONE `IntersectionObserver`; `setActiveTab` called ONLY in the detail branch (+ its def); no `getElementById(location.hash...)`; `scrollIntoView` in `showLanding` has no behavior branch.
- **Task 2:** `html{...scroll-behavior:smooth}` + `prefers-reduced-motion: reduce` + `scroll-behavior: auto` + `#landing>section{...scroll-margin-top:calc(60px + var(--space-md))}` + `#landing>section + section{...border-top:1px solid var(--line-strong)}` present; `position:sticky` + `body > header` intact; zero raw-px `scroll-margin-top` literals. **PASS.** Spot-checks: no new `.tab.active`/`.active` CSS rule (the two `.tab.active` hits = the existing rule + a comment mention); the `body > header` / `position:sticky` rule has NO removals (byte-unchanged); no new hex literals; width tokens untouched.

Live-render verification is **Task 3 / orchestrator-owned** (post the scoped `web` rebuild) — NOT run here. Per the Phase-19 lesson ([[feedback_verify_render_bugs_end_to_end]]) the live verify must reproduce the rendered output, not infer a clean result from source bytes.

## Task 3 (deploy + holistic live-verify): PENDING — orchestrator/operator-owned

Task 3 is a `checkpoint:human-verify` (gate `blocking-human`) bundling a scoped `docker compose up -d --build web` DEPLOY + a holistic live-render verification of SCROLL-01/02 + the folded WIDTH-01/RHYTHM-01 sign-off. Both the deploy and the live verification are **worktree-unsafe and orchestrator/operator-owned** (the scoped rebuild cds to the absolute main-tree path; a worktree executor would build stale code — MEMORY scoped-rebuild-worktree-unsafe) and were **explicitly outside this executor's scope**. This executor:
- Did NOT run any `docker compose` command, any deploy, or any live-site verification.
- Did NOT mark SCROLL-02 complete and did NOT mark the plan complete — both are gated on the operator's live-render sign-off, which the orchestrator owns.

**Remaining for the orchestrator + operator (Task 3 in 21-02-PLAN.md):**
1. Prod↔main drift check FIRST; operator approval BEFORE any deploy (standing v2.2 deploy discipline).
2. Scoped rebuild ONLY the `web` SERVICE key (`cd /root/bitcoin_bot/docker && docker compose up -d --build web`, NOT the `agentpulse-web` container_name; NO `--delete`).
3. Confirm the served `app.js` is the `__SUPABASE_URL__`-substituted version over the wire (SPA loads, not a blank page).
4–14. Live-verify on a wide (~1440px) viewport: SCROLL-01 (single-scroll landing in the locked order; editions/blocks still deep-linkable via `#/edition/<n>` + `#/map/<slug>`; the `#signals` shell static, no console 401 on `source_posts`); SCROLL-02 (scroll-spy highlight on scroll, smooth-scroll-on-click landing below the sticky nav, detail→back scroll-restore, reduced-motion instant-jump); the folded WIDTH-01 (no dead gutter, ~60–70 char reading line, tiled on `--wide`, nav edges == content edges) + RHYTHM-01 (token color, major/within section rhythm); plus the regression guards (mode toggle landing-scoped + working, maturity pill not overlapping nav, deep links resolve) and no Phase 22–25 scope creep.

**Resume signal:** Operator types "approved" once the live render shows the single-scroll landing with a working scroll-spy + smooth-scroll + scroll-restore + reduced-motion gate, editions/blocks still deep-linkable, the `#signals` shell static, and WIDTH-01/RHYTHM-01 holding holistically — or describes a specific issue (e.g. a `scroll-margin-top` tune, a stale active tab on back) to fix. On approval the orchestrator finalizes this SUMMARY, marks SCROLL-02 complete, and advances STATE/ROADMAP.

## Deviations from Plan

None — Tasks 1 and 2 executed exactly as written. (Plan 01 had already declared `landingScrollY` and `landingDataLoaded`; the only net-new module var this plan added was the `cameFromDetail` one-shot guard, which is the plan's `route()` action verbatim — "guard on … a `cameFromDetail` flag set in the detail branch".)

## Known Stubs

None new. The pre-existing `#signals` static placeholder shell (Plan 01, `docker/web/site/index.html`) is unchanged here — this plan added NO `source_posts` fetch to it (SIGNAL-04 / Phase 24 owns the data + RLS). No stub introduced by Plan 02's app.js/CSS changes.

## Threat Surface Scan

No new security-relevant surface. The scroll-spy IO + `scrollIntoView` operate on STATIC-LITERAL section ids (`LANDING_SECTION_IDS` / the Plan 01 allowlisted `getRoute().section`), never raw `location.hash` (T-21-04 mitigated — no hash value reaches a DOM sink). No new fetch (`#signals` stays static — T-21-06 mitigated). The only net-new motion (smooth-scroll) is gated by `@media (prefers-reduced-motion: reduce)` (T-21-07 accepted, A11Y not regressed). Zero package installs (T-21-SC). The `__SUPABASE_*__` substitution path is untouched. Consistent with the plan's `<threat_model>` — no flags.

## Self-Check: PASSED

- Files: `21-02-SUMMARY.md`, `docker/web/site/app.js`, `docker/web/site/style-base.css` — all FOUND.
- Commits: `921f6dd` (Task 1), `b9bb5bc` (Task 2) — both FOUND in git history.
- Task 3 (deploy + holistic live-verify): PENDING — orchestrator/operator-owned, not run here (by design).
