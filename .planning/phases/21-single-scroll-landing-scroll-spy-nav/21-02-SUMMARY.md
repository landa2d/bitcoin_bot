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
  duration: ~7min code + orchestrator deploy/verify
  completed: 2026-06-11
  tasks: "3 of 3 (Task 3 deploy + holistic live-verify COMPLETE — operator-approved 2026-06-11)"
  files: 3
  commits: 4
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

## Task 3 (deploy + holistic live-verify): COMPLETE — operator-approved 2026-06-11

Orchestrator-owned, run from the MAIN tree (worktree-unsafe — the scoped rebuild cds to the absolute main-tree path). Sequence executed:
1. **Prod↔main drift check (clean):** `docker/web/site/` working tree clean (all Phase 21 changes committed); the running `agentpulse-web` container predated every Phase 21 commit → drift = exactly the Phase 21 web changes. Out-of-scope uncommitted files (`.claude/settings.local.json`, untracked `.planning/docs/*`) are outside the web build context. Work group shown to operator; **deploy approved** before any rebuild (standing v2.2 deploy discipline).
2. **Scoped rebuild** ONLY the `web` SERVICE key: `cd /root/bitcoin_bot/docker && docker compose up -d --build web` (NO `--delete`, did NOT use `--remove-orphans` against the pre-existing `openclaw-rivalscope` orphan).
3. **Substitution confirmed over the wire:** served `/app.js` has no literal `__SUPABASE_*__` placeholder (real Supabase URL substituted), carries the Phase 21 code (`initScrollSpy`), 66510 bytes; SPA loads. Automated over-the-wire structural checks PASS: served section order = locked Newsletter→Signals→Agent-Economy→About; nav tabs correct; `#signals` static (no `source_posts`); scroll-spy IO + `scrollTo(0, landingScrollY)` wiring served; all 4 net-new CSS rules served; routes resolve 200.
4–14. **Operator holistic live-render sign-off: APPROVED.**

### Width-consistency fix (operator live-verify iterations)

The operator caught a holistic-assembly WIDTH issue during live verification (not visible per-route pre-merge): each landing section rendered at a different width — Newsletter widest on `--wide`, Signals/About-intro centered-narrow on the production (centered, 64ch) `.prose`. Two follow-up fixes (mockup contract = uniform `<section class="wide">` with full-band copy), redeployed + re-verified each time:
- **`77da515`** — `#signals` + `#about` content wrappers carry `.wide` (like `#newsletter`/`#map`) so all four sections frame at the same centered `--wide` band; `#landing`-scoped CSS left-aligns `.prose` + de-dupes nested `.wide`. Detail-route reading prose untouched (scoped to `#landing`).
- **`33cef15`** — lift the `--measure` (~64ch) cap on `#landing .prose` (`max-width: none`) so the landing copy spans the full band edge-to-edge (operator: "the text within is still shorter and doesn't expand to the same width"). Detail-route (edition/block) reading prose keeps the centered ~64ch measure — WIDTH-01 reading-line untouched; the wide landing copy is the operator's explicit landing-specific call.

### Post-verify code-review + scroll-spy fixes (operator-approved iterations)

After the holistic sign-off, the advisory code review (`21-REVIEW.md`, 0 blocker / 4 warning / 4 info) and one further operator live-verify surfaced fixes, each redeployed + re-verified:
- **`e4a54eb`** — resolved all 4 review WARNINGs: WR-01 (deep-link to a below-fold section scrolled before `loadList`/`loadHub` injected content → `ensureLandingDataLoaded` now returns a settle Promise; `showLanding` defers the section scroll via rAF until data renders on first show); WR-02 (legacy `#/map`+`#/about` hashes normalized to their bare-anchor section in `getRoute`, after the `#/map/<slug>` block check); WR-03 (detail→back restore now `behavior:'auto'` + `showLanding` skips its scroll when a restore is pending — no competing animation under the global `scroll-behavior:smooth`); WR-04 (restore clamps to the current document height + resets `landingScrollY`). The 4 INFO items deferred (non-blocking; IN-03 `.about-lede` is a pre-existing carry-over advisory).
- **`7e4a341`** — scroll-spy active-section detection made robust to section height. The mockup's viewport-CENTRE `rootMargin '-50% 0px -50% 0px'` mis-highlighted the SHORT `#signals` placeholder (clicking Signals scrolled to it but the taller Agent-Economy section below straddled the centre line and won). Replaced with a thin ~1px detection band a fixed ~96px below the viewport top (just under the ~60px sticky header + the 76px scroll-margin heading offset), rebuilt on resize — so the active section is whichever sits under the nav, independent of height. **NOTE for traceability:** the must_haves.truths line names `rootMargin '-50% 0px -50% 0px'` as the mechanism; that specific literal was changed for this operator-approved correctness fix, but the GOAL (scroll-spy highlights the active section as the user scrolls) is now BETTER satisfied — `rootMargin` + the single `IntersectionObserver` + static-literal ids + `.active`/`aria-current` parity all remain.

SCROLL-01 + SCROLL-02 satisfied and verified holistically on the live render (incl. the folded WIDTH-01/RHYTHM-01), with all code-review warnings resolved. Phase 21 complete.

## Deviations from Plan

None — Tasks 1 and 2 executed exactly as written. (Plan 01 had already declared `landingScrollY` and `landingDataLoaded`; the only net-new module var this plan added was the `cameFromDetail` one-shot guard, which is the plan's `route()` action verbatim — "guard on … a `cameFromDetail` flag set in the detail branch".)

## Known Stubs

None new. The pre-existing `#signals` static placeholder shell (Plan 01, `docker/web/site/index.html`) is unchanged here — this plan added NO `source_posts` fetch to it (SIGNAL-04 / Phase 24 owns the data + RLS). No stub introduced by Plan 02's app.js/CSS changes.

## Threat Surface Scan

No new security-relevant surface. The scroll-spy IO + `scrollIntoView` operate on STATIC-LITERAL section ids (`LANDING_SECTION_IDS` / the Plan 01 allowlisted `getRoute().section`), never raw `location.hash` (T-21-04 mitigated — no hash value reaches a DOM sink). No new fetch (`#signals` stays static — T-21-06 mitigated). The only net-new motion (smooth-scroll) is gated by `@media (prefers-reduced-motion: reduce)` (T-21-07 accepted, A11Y not regressed). Zero package installs (T-21-SC). The `__SUPABASE_*__` substitution path is untouched. Consistent with the plan's `<threat_model>` — no flags.

## Self-Check: PASSED

- Files: `21-02-SUMMARY.md`, `docker/web/site/app.js`, `docker/web/site/style-base.css`, `docker/web/site/index.html` — all FOUND.
- Commits: `921f6dd` (Task 1), `b9bb5bc` (Task 2), `77da515` + `33cef15` (Task 3 width-consistency fixes) — all FOUND in git history.
- Task 3 (deploy + holistic live-verify): COMPLETE — scoped `web` rebuild deployed from the main tree, substitution confirmed over the wire, operator-approved live-render sign-off 2026-06-11 (incl. two width-fix iterations).
