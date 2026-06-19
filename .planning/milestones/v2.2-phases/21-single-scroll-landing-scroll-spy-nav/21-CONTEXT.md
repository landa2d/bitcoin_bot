# Phase 21: Single-Scroll Landing + Scroll-Spy Nav - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning
**Source:** Resume-session decisions + 21-RESEARCH.md (no separate discuss-phase — operator chose "plan directly")

<domain>
## Phase Boundary

Convert the four TOP-LEVEL sections (newsletter list / signals / agent-economy / about) from separate hash routes into ONE single-scroll landing with a scroll-spy nav. Individual **editions** (`#/<edition>`) and **block pages** (`#/map/<slug>`) STAY deep-linkable detail routes. This is a two-mode router refactor of `app.js` (`mode:'landing'|'detail'`), reusing the existing top-level view DOMs as stacked `<section>` anchors. Frontend-only: `app.js`, `style-base.css`, `style-shared.css`.

**In scope:** navigation STRUCTURE — the single-scroll landing, the IntersectionObserver scroll-spy, smooth-scroll-on-click, detail-route coexistence + back-to-landing scroll restore, the `#signals` placeholder section SHELL.

**Out of scope (later phases):** per-section VISUAL fixes (3-col map, About agent grid, edition-header de-dup) = Phase 22; the Signals DATA + anon RLS migration = Phase 24; the holistic responsive/a11y + scroll-spy a11y pass = Phase 25. Phase 21 does NOT change section CONTENT, only how it's navigated.
</domain>

<decisions>
## Implementation Decisions (LOCKED)

### Section order (operator-locked 2026-06-11)
- **Mockup order:** Newsletter → Signals → Agent-Economy → About. The DOM order, nav-link order, and the scroll-spy section array MUST all match this single order. (Operator picked the mockup order over the roadmap-text order; this puts the new Signals feed 2nd, by design.)

### Anchor ids
- Use clear semantic anchor ids; prefer `#about` over the mockup's literal `#made` (research-flagged as cosmetic). Newsletter/agent-economy/signals anchors should be self-describing (e.g. `#newsletter`/`#signals`/`#map`/`#about`). Planner's discretion on exact strings provided they are stable + deep-linkable.

### Router two-mode model (from 21-RESEARCH.md, recommended path)
- Add a `mode:'landing'|'detail'` discriminator to the existing `getRoute()`/`route()`/`showView()` shape — additive, lowest-risk. Reuse the four top-level `#*-view` DOMs as stacked `<section>` anchors inside one `#landing` container.
- **Namespace split is critical:** test slashed/detail patterns (`#/<edition>`, `#/map/<slug>`) FIRST so editions/blocks stay deep-linkable; bare anchors (`#signals` etc.) resolve to landing sections.
- Deep-linking to a section anchor on load scrolls to that section.
- Scroll-spy: IntersectionObserver per the mockup (`rootMargin:'-50% 0px -50% 0px'`), accounting for the sticky-header offset; nav clicks smooth-scroll.
- Detail→Back scroll restore: stash `window.scrollY` in a module var (matches codebase idiom); `history.scrollRestoration` is a flagged low-risk fallback.

### Signals shell seam
- Ship `#signals` as a STATIC placeholder section. Phase 24 fills it with data + the anon RLS migration. A premature data fetch here would violate fail-loud/SIGNAL-04 — placeholder only.

### Must NOT change (scope guard)
- Phase 20 width/rhythm foundation (`.prose`/`.wide` axes, `--measure`/`--wide`/`--gutter`, section-rhythm tokens).
- The `body > header { position:sticky }` scoping (maturity-overlap fix — Pitfall 1).
- The Technical/Strategic mode toggle (newsletter-scoped) and the subscribe form.
- SEO / deep-linkability of editions + block pages.
- The web entrypoint `__SUPABASE_URL__` sed-substitution path (preview vs live).

### Claude's Discretion
- Exact anchor id strings; the precise IntersectionObserver threshold tuning; whether the landing renders all four sections eagerly (recommended) vs lazily; the module-var-vs-`history.scrollRestoration` choice for scroll restore (research recommends module var).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Implementation target (the code being refactored)
- `docker/web/site/app.js` — the SPA hash router (`getRoute`/`route`/`showView`), per-route render fns, nav active-state, ← Back, mode toggle. THE file refactored.
- `docker/web/site/index.html` — nav markup, per-route view containers, Phase 20 `.wide`/`.prose` wrappers.
- `docker/web/site/style-base.css`, `docker/web/site/style-shared.css` — Phase 20 width tokens, sticky nav, section-rhythm.

### Design + decision contract
- `.planning/phases/21-single-scroll-landing-scroll-spy-nav/21-RESEARCH.md` — current-architecture map, router-refactor approach, scroll-spy pattern, scroll-restore, Signals seam, 7 pitfalls, assumptions, threat note.
- `.planning/docs/agentpulse-redesign (1).html` — the mockup: single-scroll + `IntersectionObserver` scroll-spy. PATTERN reference (not markup to copy); canonical content comes from app.js + economy_map.
- `.planning/REQUIREMENTS.md` — SCROLL-01, SCROLL-02 (+ cross-cutting RHYTHM-01/RESP-01/A11Y-01).
- `.planning/ROADMAP.md` — Phase 21 goal/success-criteria/notes; Phases 22–25 (so the plan respects later-phase ownership).
- `./CLAUDE.md` — deploy discipline, web container substitution, scoped rebuild service key `web`.
</canonical_refs>

<specifics>
## Specific Ideas

- WIDTH-01 + RHYTHM-01 are re-verified HOLISTICALLY on the assembled landing here (Phase 20's per-route visual sign-off was folded into this phase). The live-render verify is orchestrator-owned/worktree-unsafe: scoped `docker compose up -d --build web` (service key `web`, no `--delete`) → prod↔main drift check → operator approval.
- No new packages, no backend, no migration (confirmed by research).
</specifics>

<deferred>
## Deferred Ideas

- Signals data + anon tier-1 RLS migration on `source_posts` → Phase 24.
- Per-section visual fixes (3-col map, About agent grid, edition-header de-dup) → Phase 22.
- Newsletter excerpts → Phase 23.
- Holistic responsive + a11y (incl. scroll-spy a11y, `prefers-reduced-motion` smooth-scroll suppression) → Phase 25 (this phase must not regress a11y, but the full pass is Phase 25).
</deferred>

---

*Phase: 21-single-scroll-landing-scroll-spy-nav*
*Context captured: 2026-06-11 (resume-session decisions + research)*
