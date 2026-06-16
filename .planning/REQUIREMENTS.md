# Requirements — Milestone v2.2: Landing Redesign + Signals Feed

**Defined:** 2026-06-10
**Core Value:** Synthesis with editorial integrity — autonomous drafting accelerates output, but every consequential publication is gated by human approval.

**Goal:** Re-skin the public site (`aiagentspulse.com`) to the new editorial mockup — including its single-scroll landing + scroll-spy nav for the top-level sections (REVISED 2026-06-11; editions/blocks stay deep-linkable routes) — fix the four live-site defects the redesign brief calls out, and add a new Signals feed of tier-1 source links.

**Source brief:** `.planning/docs/REDESIGN_CC_BRIEF.md` (7 work groups, ordered low-to-high risk) + `.planning/docs/agentpulse-redesign (1).html` (visual mockup — single-scroll + `IntersectionObserver` scroll-spy; now the form reference for Phase 21, not just intent).

**Operator decisions (locked 2026-06-10; layout REVISED 2026-06-11):** ~~keep separate routes~~ → **hybrid single-scroll landing** (top-level sections scroll + scroll-spy nav; editions/blocks stay deep-linkable routes) · ~~Signals as its own `#/signals` route + tab~~ → **Signals as a `#signals` section in the landing** · excerpts fixed strip-at-render (no schema/pipeline change) · no domain research.

---

## v2.2 Requirements

Each maps to exactly one roadmap phase (see Traceability).

### Content Integrity (smart-quote fix — Task 1)

> **Not frontend-only.** The `marked.js` renderer runs with no typographer config, so the apostrophe corruption originates in stored markdown / the write path, not the renderer. Fix forward + scoped reviewed backfill.

- [x] **QUOTE-01**: Edition bodies render apostrophes correctly — e.g. `Cash App's`, `It's`, `world's`, `agent's` — with zero straight-double-quote corruption, on both existing editions (backfilled) and newly generated ones (write-path fixed). Root cause is documented, not just patched. _(Plan 01: root cause documented + write-path guard shipped — diagnosis proved storage is already clean. Plan 02: independent live scan reproduced storage-clean (43 rows, 0 corrupt corpus-wide) → confirm-and-close, no backfill UPDATE needed; operator approved "Close + rebuild newsletter" and the write-path guard shipped live via the newsletter rebuild. SATISFIED.)_
- [x] **QUOTE-02**: The corruption cannot silently regress — a test feeds `it's` and `the agent's wallet` through the fixed path and asserts the output contains an apostrophe and zero stray `"`.

### Layout & Centering (Task 2)

- [ ] **WIDTH-01**: On a wide viewport there is no large empty band on the left — content is centered via two coexisting max-widths: narrow prose (`--measure`, ~60–70 char lines) for edition body + intro copy, and a wider container (`--wide`) for the newsletter list, map grid, Signals, and card grids.

### Single-Scroll Landing (REVISED 2026-06-11 — formerly deferred WIDTH-F1)

> Layout direction reversed mid-milestone: the mockup is a single-page scroll with `IntersectionObserver` scroll-spy. The four top-level sections merge into one scroll page; editions/blocks stay deep-linkable routes (keeps SEO/deep-linking).

- [x] **SCROLL-01**: The four top-level sections (newsletter list, about, agent-economy, signals) render on ONE single-scroll landing page (stacked sections with anchors), replacing the separate top-level routes. Individual editions (`#/<edition>`) and block pages (`#/map/<slug>`) remain deep-linkable detail routes.
- [x] **SCROLL-02**: The persistent nav is a scroll-spy — it smooth-scrolls to a section on click and highlights the active section as the user scrolls (`IntersectionObserver`). Opening a detail route (edition/block) leaves the landing; returning ("← Back" / nav) restores the landing with scroll position preserved. Scroll-spy degrades safely under `prefers-reduced-motion` (verified holistically in Phase 25).

### Article Header (Task 3)

- [x] **HEAD-01**: An edition page shows the edition number, date, and mode (Technical/Strategic) exactly once — in the meta line below the title — with the H1 containing only the headline (no `— Edition #N | <date>` suffix). If the suffix is baked into stored data it is stripped at render, not mutated in storage.

### Agent Economy Map (Task 4)

- [x] **GRID-01**: The Agent Economy map renders as a 3-column grid on desktop so all blocks tile cleanly, collapsing responsively (3 → 2 at ≤880px → 1 at ≤600px).
- [x] **GRID-02**: A maturity legend appears under the map heading so the per-block bars read as a scale, not decoration; each block's filled-segment count matches its stored `economy_map` maturity value.

### About / "What is AgentPulse" (Task 5)

- [x] **AGENTS-01**: The About page presents the pipeline agents (Processor / Analyst / Research / Newsletter) as an ordered, numbered sequence and the supporting layer (Gato / LLM proxy / web front end) as an unordered bulleted list — no orphaned single card — with the "nothing publishes without human approval" line rendered as its own distinct (violet) callout.

### Newsletter Excerpts (Task 6)

- [x] **EXCERPT-01**: Consecutive editions show distinct preview text in the archive list — the standard "Read This, Skip the Rest" boilerplate intro is skipped and the first genuinely-distinct sentence is shown — presented in the indexed-row format (number · title · one-line summary · date). Editions 29 and 30 show different preview text. Strip-at-render; no schema change.

### Signals Feed (Task 7 — new section)

- [ ] **SIGNAL-01**: A Signals section lists tier-1 `source_posts` newest-first, capped to ~12–15, with a "view all signals" affordance so a heavy news week can't make the section enormous.
- [ ] **SIGNAL-02**: Each Signals row is an external link showing date · headline · source domain, opening off-site safely (`target="_blank"` + `rel="noopener noreferrer"`) with an `↗` hover affordance.
- [ ] **SIGNAL-03**: Signals is reachable as a `#signals` section in the single-scroll landing via the scroll-spy nav (consistent with the other landing sections), deep-linkable at `#signals`. _(REVISED 2026-06-11 — was its own `#/signals` route + tab.)_
- [ ] **SIGNAL-04**: tier-1 `source_posts` are readable by the anon key via a new, read-only, tier-1-scoped Supabase RLS policy (the table is currently RLS-blocked from anon) — fail-loud if the policy is absent rather than silently rendering an empty feed.

### Cross-Cutting (all groups)

- [ ] **RESP-01**: All grids and rows reflow responsively — map 3→2→1, nav condenses on mobile, and signal/archive rows stack (date above headline) below the mobile breakpoint.
- [ ] **A11Y-01**: Keyboard focus is visible (`:focus-visible` violet outline), `prefers-reduced-motion` is respected, and every link is a real `<a>` element.
- [ ] **RHYTHM-01**: No hardcoded colors — every surface themes from the existing CSS variable system (warm off-white + violet); section rhythm uses one full-strength rule between major sections and hairline (`0.5px`) rules within.

---

## Future Requirements

Deferred to a later release. Tracked, not in this roadmap.

### Excerpts

- **EXCERPT-F1**: Stored `summary` field on `newsletters`, emitted by the Newsletter agent at generation time (the "cleaner long-term" excerpt path — deferred in favor of strip-at-render this milestone; touches schema + pipeline + backfill).

### Signals

- **SIGNAL-F1**: A full Signals archive page behind the "view all signals" affordance (if the capped feed proves insufficient).

### Layout

- ~~**WIDTH-F1**~~: Single-page scroll landing with scroll-spy nav — **PROMOTED into v2.2 (2026-06-11)** as SCROLL-01/SCROLL-02 (Phase 21), in hybrid form (top-level sections scroll; editions/blocks stay deep-linkable routes).

### Theming

- **THEME-F1**: Dark-mode variant of the light palette (DARK-01, carried from v2.0).
- **THEME-F2**: Richer About page with a pipeline/architecture diagram (ABOUT-02, carried from v2.0).

---

## Out of Scope

Explicitly excluded for this milestone.

| Feature | Reason |
|---------|--------|
| ~~Single-page scroll rebuild~~ | **REVISED 2026-06-11 — now IN scope (Phase 21, SCROLL-01/02)** as a hybrid: top-level sections become a single-scroll landing + scroll-spy; editions & block pages stay deep-linkable routes (keeps the SEO/deep-link benefit) |
| Stored `summary` field / pipeline change for excerpts | Operator chose strip-at-render; no schema or content-pipeline change for the excerpt fix (see EXCERPT-F1) |
| Dark mode | Deferred since v2.0; ship the single light-mode violet system (see THEME-F1) |
| Richer About / pipeline diagram | About ships as the v2.0 stub with the agent-grid fix only (see THEME-F2) |
| New brand / color system | Keep the existing token palette (Source Serif 4 / IBM Plex Mono / off-white + violet); the mockup's `:root` matches it |
| Backend changes beyond Task 1 + Task 7 | The only backend touches are the smart-quote write-path fix + backfill and the `source_posts` anon RLS policy — no pipeline/proxy/agent-service refactors |
| Mockup's placeholder block taxonomy | The map uses the canonical `economy_map` block list, not the mockup's illustrative blocks (consistent with v2.0/v2.1) |
| Carried-forward backend todos | analyst title-expire, soft-cap hardening, pay-endpoint E2E, intake review follow-ups, research file perms — remain parked (`.planning/todos/pending/`) |
| EU AI Act tracker / per-block synthesis tuning / negotiation graduation | Parked backend items kept in separate milestones |

---

## Traceability

Which phases cover which requirements. Mapped at roadmap creation (2026-06-10).

| Requirement | Phase | Status |
|-------------|-------|--------|
| QUOTE-01 | Phase 19 | Complete (P01 fix-forward + P02 confirm-and-close; storage clean, guard live) |
| QUOTE-02 | Phase 19 | Complete |
| WIDTH-01 | Phase 20 | Complete (P01 .prose/.wide axes + tokens, 720px .container retired, nav on wide axis; deployed live 2026-06-11; holistic visual re-verify carried into Phase 21) |
| RHYTHM-01 | Phase 20 | Complete (P02 on-accent token + D-05 rhythm; deployed live 2026-06-11) |
| SCROLL-01 | Phase 21 | Pending (NEW 2026-06-11 — single-scroll landing) |
| SCROLL-02 | Phase 21 | Pending (NEW 2026-06-11 — scroll-spy nav + detail-route coexistence) |
| HEAD-01 | Phase 22 | Complete |
| GRID-01 | Phase 22 | Complete |
| GRID-02 | Phase 22 | Complete |
| AGENTS-01 | Phase 22 | Complete |
| EXCERPT-01 | Phase 23 | Complete |
| SIGNAL-01 | Phase 24 | Pending |
| SIGNAL-02 | Phase 24 | Pending |
| SIGNAL-03 | Phase 24 | Pending |
| SIGNAL-04 | Phase 24 | Pending |
| RESP-01 | Phase 25 | Pending |
| A11Y-01 | Phase 25 | Pending |

**Coverage:**

- v2.2 requirements: 17 total (15 original + SCROLL-01/SCROLL-02 added 2026-06-11)
- Mapped to phases: 17 ✓ (each to exactly one phase)
- Unmapped: 0 ✓ — no orphans, no duplicates

**Phase rollup:**

- Phase 19 — Smart-Quote / Apostrophe Corruption Fix: QUOTE-01, QUOTE-02 (2)
- Phase 20 — Width Tokens & Centering Foundation: WIDTH-01, RHYTHM-01 (2)
- Phase 21 — Single-Scroll Landing + Scroll-Spy Nav: SCROLL-01, SCROLL-02 (2)
- Phase 22 — Per-Section Visual Fixes: HEAD-01, GRID-01, GRID-02, AGENTS-01 (4)
- Phase 23 — Distinct Newsletter Excerpts: EXCERPT-01 (1)
- Phase 24 — Signals Section: SIGNAL-01, SIGNAL-02, SIGNAL-03, SIGNAL-04 (4)
- Phase 25 — Responsive & Accessibility Pass: RESP-01, A11Y-01 (2)

Cross-cutting note: RESP-01, A11Y-01 (Phase 25) and RHYTHM-01 (Phase 20) are applied across every phase but are each owned and verified holistically in exactly one phase — RHYTHM-01 at the width/token foundation it establishes, RESP-01 + A11Y-01 in the final responsive/a11y pass over the whole redesigned surface (now including scroll-spy behavior).

---
*Requirements defined: 2026-06-10*
*Last updated: 2026-06-11 — layout direction REVISED to hybrid single-scroll landing; SCROLL-01/02 added (Phase 21, from promoted WIDTH-F1); Phases 22–25 renumbered; Phase 20 (WIDTH-01/RHYTHM-01) complete + deployed. 17 requirements mapped to Phases 19–25.*
