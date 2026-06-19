# Phase 25: Responsive & Accessibility Pass - Context

**Gathered:** 2026-06-17
**Status:** Ready for planning

<domain>
## Phase Boundary

A holistic, cross-cutting **conformance pass** over the assembled single-scroll landing — closing RESP-01 (grids/rows reflow, nav condenses) and A11Y-01 (visible focus, `prefers-reduced-motion` respected, every link a real `<a>`). Most pieces were built incrementally in Phases 20–24; this phase **verifies them holistically on the live render and fixes the named gaps** — it does not rebuild conforming surfaces or expand into a broad WCAG audit.

Frontend-only, CSS-led: changes land in `docker/web/site/style-base.css` and `style-shared.css`. `app.js` is expected to stay untouched (rows already render as real `<a>`). Deploy is orchestrator-owned (scoped `web` rebuild, worktree-unsafe).
</domain>

<decisions>
## Implementation Decisions

### Pass Scope & Ceiling
- **D-01:** **Strict to the brief's named items** (the 3 reflow + 3 a11y points) **plus obvious regressions found en route.** Explicitly OUT of scope: new ARIA landmarks/roles, skip-to-content link, contrast-ratio audit, alt-text/screen-reader pass. Those would be their own a11y-hardening phase.
- **D-02:** The one named regression to fix: `#subscribe-email:focus { outline: none; }` (`style-shared.css:918`) currently swaps the outline for a border-color change on `:focus` (not `:focus-visible`). Apply the **standard `:focus-visible` violet-outline pattern** used by `.row` / `.view-all` / `.card` so every interactive element has a visible keyboard focus indicator.
- **D-03:** RESP-01/A11Y-01 are largely implemented already (Phases 20–24). This pass **verifies holistically** and closes the gaps below; it does not redo conforming pieces.

### Breakpoints
- **D-04:** **Two-tier breakpoint system — mobile = 600px, tablet = 880px — as the only two breakpoints.** Map / about-grid stay 3→2 @880, →1 @600 (already correct, `style-shared.css:391/470/471`, `.made-cols:1132`).
- **D-05:** **Move the nav condense breakpoint 640px → 600px** (`style-base.css:254`) so the nav condenses at the same line rows stack — removes the 40px band where the nav has condensed but rows haven't.
- **D-06:** Breakpoints are **aligned literal px values + a documented convention, NOT CSS custom properties.** The site is raw CSS, no build step, and `@media` queries cannot read custom properties. Don't promise `var(--bp)` in a media query.

### Mobile Row Stacking
- **D-07:** Below 600px, both archive rows (`renderList`, `app.js:495`) and signal rows (`renderSignals`, `app.js:631`) restack so the **date is a mono kicker line ABOVE the headline** (title below) — matching the brief's "date above headline." Replaces the current behavior (date dropped into `grid-column: 2` with `margin-top`, BELOW the title — `style-shared.css:265-266`).
- **D-08:** The **left affordance column stays** on mobile (archive index num / signal ↗) — only the date/title order within the content column changes. Not dropping the affordance.
- **D-09:** **Single source of truth:** the change lands once on the shared `.row` 600px rule; both row types inherit it. No per-render-function JS change.

### Reduced Motion
- **D-10:** Replace the current scroll-only gate (`style-base.css:308-312`) with the **canonical global reset:** `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; } }`. All motion (incl. the `!important` theme transition + hover transitions) honors the preference. One well-known rule; minimal-touch.
- **D-11:** Plan/research **MUST verify the reset wins over the existing `!important` theme transition at `style-shared.css:32`** (both `!important` — the reset must come later in the cascade and/or out-specify it). This is the one cascade pitfall of D-10.

### Nav Condense Behavior
- **D-12:** Keep the **existing wrap-tabs-to-scrollable-row condense** (`style-base.css:255-263`) — no hamburger, no relabeling. Only its breakpoint moves (640→600, per D-05). The brief says only "nav condenses on mobile"; minimal-touch satisfies it. (Operator-confirmed default.)

### Claude's Discretion
- **Live-render verification viewports:** planner/verifier picks the canonical widths (suggest ~375px mobile, ~768px tablet, ~1280px desktop) and any fine-tuning of the nav breakpoint if 600px still leaves an overflow — within the two-tier intent (D-04).
- **"Every link is a real `<a>`" audit:** rows + map blocks already render as `<a>` (`renderList:495`, `renderSignals:631`, blocks `app.js:999`); `view-all` is correctly a `<button>` (action, not navigation). Verify no click-handler `<div>`-as-link slipped in; no JS change expected.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design contract (the literal RESP-01 / A11Y-01 spec)
- `.planning/docs/REDESIGN_CC_BRIEF.md` §"Responsive / Accessibility" (work group 7, ~lines 168–172) — "grids collapse 3→2→1; nav condenses on mobile; signal/archive rows reflow (date above headline)" + "visible keyboard focus (`:focus-visible` outline in violet), `prefers-reduced-motion` respected, real `<a>` elements."
- `.planning/docs/agentpulse-redesign (1).html` — visual mockup; the IntersectionObserver scroll-spy intent reference (~line 231). Intent reference only.

### Requirements & roadmap
- `.planning/ROADMAP.md` → Phase 25 entry + Success Criteria (the 3→2→1 / nav / rows / focus / motion / `<a>` checklist).
- `.planning/REQUIREMENTS.md` → RESP-01 (line 62), A11Y-01 (line 63).

### Prior-phase foundations this pass verifies (context, not re-decided)
- `.planning/phases/20-width-tokens-centering-foundation/20-CONTEXT.md` — width/rhythm tokens; RHYTHM-01 token-only-color baseline (verify, don't redefine).
- `.planning/phases/21-single-scroll-landing-scroll-spy-nav/21-CONTEXT.md` — scroll-spy + the original reduced-motion scroll gate this phase generalizes.
- `.planning/phases/24-signals-section/24-CONTEXT.md` — the signal `.row` + `.view-all` focus + 600px reflow added there (now re-checked holistically).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`.row` family** (`style-shared.css:206-267`): shared grid (`56px 1fr auto`) + `:focus-visible` violet outline (`:257`) + the existing 600px reflow (`:264-267`). Both archive (`renderList`) and signal (`renderSignals`) rows use it — the mobile date-above-headline change (D-07) lands here once for both.
- **`.grid`** (`style-shared.css:391`, reflow `:470/:471`): already 3→2 @880, →1 @600 for map + about-grid. Verify-only.
- **`.tabs` / `.nav` responsive rule** (`style-base.css:251-264`) @640: move to 600 (D-05); keep the wrap-to-scrollable-row behavior (D-12).
- **Reduced-motion block** (`style-base.css:308-312`): currently scroll-only — generalize to the global reset (D-10).
- **`:focus-visible` violet-outline pattern** (`.row:257`, `.view-all:296`, `.card:440`): the canonical focus treatment to apply to `#subscribe-email` (D-02).

### Established Patterns
- **Token-only color** (RHYTHM-01) — every value a `var(--…)` token; zero new hex. Raw CSS, served as-is (no preprocessor, no build) → no custom properties inside `@media` (D-06).
- **`app.js` contains NUL-byte sentinels** (Phase 23 excerpt split) — `grep` treats it as binary; use `grep -a`. `Read` renders NUL as a space.
- **Links are already real `<a>`** for rows + map blocks; `view-all` is a `<button>` (correct). A11Y-01's "real `<a>`" is largely satisfied — verify, don't rebuild.

### Integration Points
- All changes expected in `style-base.css` + `style-shared.css` (CSS-only). `app.js` untouched.
- Deploy: orchestrator-owned scoped `docker compose up -d --build web` from the main tree (worktree-unsafe), gated by branch + `/diff` per work group + prod↔main drift check + operator approval (no `--delete`).
- Verification is live-render at the canonical viewports — this is a `ui_phase`; visual sign-off is the gate, not container-up.
</code_context>

<specifics>
## Specific Ideas

- The brief's work group 7 is the literal contract to satisfy verbatim: 3→2→1 grids, nav condenses on mobile, signal/archive rows reflow with **date above headline**, `:focus-visible` violet outline, `prefers-reduced-motion` respected, real `<a>` links.
- The redesign mockup `agentpulse-redesign (1).html` is the scroll-spy IntersectionObserver intent reference (Phase 21 implemented it) — re-verify it is keyboard- and motion-safe on the assembled landing.
</specifics>

<deferred>
## Deferred Ideas

- **Broader WCAG / a11y hardening** — contrast-ratio audit, ARIA landmarks/roles, alt text, skip-to-content link, screen-reader pass. Explicitly OUT of this phase per D-01; candidate for a future dedicated a11y-hardening effort if the operator wants it.

None other — discussion stayed within phase scope.
</deferred>

---

*Phase: 25-Responsive & Accessibility Pass*
*Context gathered: 2026-06-17*
