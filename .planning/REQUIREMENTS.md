# Requirements — Milestone v2.2: Landing Redesign + Signals Feed

**Defined:** 2026-06-10
**Core Value:** Synthesis with editorial integrity — autonomous drafting accelerates output, but every consequential publication is gated by human approval.

**Goal:** Re-skin the public site (`aiagentspulse.com`) to the new editorial mockup across the existing separate-route SPA, fix the four live-site defects the redesign brief calls out, and add a new Signals feed of tier-1 source links.

**Source brief:** `.planning/docs/REDESIGN_CC_BRIEF.md` (7 work groups, ordered low-to-high risk) + `.planning/docs/agentpulse-redesign (1).html` (visual mockup — intent reference, not markup to copy).

**Operator decisions locked at milestone start (2026-06-10):** keep separate routes (not single-scroll) · Signals as its own `#/signals` route + nav tab · excerpts fixed strip-at-render (no schema/pipeline change) · no domain research.

---

## v2.2 Requirements

Each maps to exactly one roadmap phase (see Traceability).

### Content Integrity (smart-quote fix — Task 1)

> **Not frontend-only.** The `marked.js` renderer runs with no typographer config, so the apostrophe corruption originates in stored markdown / the write path, not the renderer. Fix forward + scoped reviewed backfill.

- [ ] **QUOTE-01**: Edition bodies render apostrophes correctly — e.g. `Cash App's`, `It's`, `world's`, `agent's` — with zero straight-double-quote corruption, on both existing editions (backfilled) and newly generated ones (write-path fixed). Root cause is documented, not just patched.
- [ ] **QUOTE-02**: The corruption cannot silently regress — a test feeds `it's` and `the agent's wallet` through the fixed path and asserts the output contains an apostrophe and zero stray `"`.

### Layout & Centering (Task 2)

- [ ] **WIDTH-01**: On a wide viewport there is no large empty band on the left — content is centered via two coexisting max-widths: narrow prose (`--measure`, ~60–70 char lines) for edition body + intro copy, and a wider container (`--wide`) for the newsletter list, map grid, Signals, and card grids.

### Article Header (Task 3)

- [ ] **HEAD-01**: An edition page shows the edition number, date, and mode (Technical/Strategic) exactly once — in the meta line below the title — with the H1 containing only the headline (no `— Edition #N | <date>` suffix). If the suffix is baked into stored data it is stripped at render, not mutated in storage.

### Agent Economy Map (Task 4)

- [ ] **GRID-01**: The Agent Economy map renders as a 3-column grid on desktop so all blocks tile cleanly, collapsing responsively (3 → 2 at ≤880px → 1 at ≤600px).
- [ ] **GRID-02**: A maturity legend appears under the map heading so the per-block bars read as a scale, not decoration; each block's filled-segment count matches its stored `economy_map` maturity value.

### About / "What is AgentPulse" (Task 5)

- [ ] **AGENTS-01**: The About page presents the pipeline agents (Processor / Analyst / Research / Newsletter) as an ordered, numbered sequence and the supporting layer (Gato / LLM proxy / web front end) as an unordered bulleted list — no orphaned single card — with the "nothing publishes without human approval" line rendered as its own distinct (violet) callout.

### Newsletter Excerpts (Task 6)

- [ ] **EXCERPT-01**: Consecutive editions show distinct preview text in the archive list — the standard "Read This, Skip the Rest" boilerplate intro is skipped and the first genuinely-distinct sentence is shown — presented in the indexed-row format (number · title · one-line summary · date). Editions 29 and 30 show different preview text. Strip-at-render; no schema change.

### Signals Feed (Task 7 — new section)

- [ ] **SIGNAL-01**: A Signals section lists tier-1 `source_posts` newest-first, capped to ~12–15, with a "view all signals" affordance so a heavy news week can't make the section enormous.
- [ ] **SIGNAL-02**: Each Signals row is an external link showing date · headline · source domain, opening off-site safely (`target="_blank"` + `rel="noopener noreferrer"`) with an `↗` hover affordance.
- [ ] **SIGNAL-03**: Signals is reachable at its own `#/signals` route via a tab in the persistent nav shell (consistent with the v2.0 nav + ← Back pattern).
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

- **WIDTH-F1**: Single-page scroll landing with scroll-spy nav (the mockup's literal form — deferred in favor of separate routes for SEO/deep-linking/lower risk).

### Theming

- **THEME-F1**: Dark-mode variant of the light palette (DARK-01, carried from v2.0).
- **THEME-F2**: Richer About page with a pipeline/architecture diagram (ABOUT-02, carried from v2.0).

---

## Out of Scope

Explicitly excluded for this milestone.

| Feature | Reason |
|---------|--------|
| Single-page scroll rebuild | Operator chose separate routes — lower risk, SEO, deep-linkable editions & block pages; mockup is intent reference only |
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
| QUOTE-01 | Phase 19 | Pending |
| QUOTE-02 | Phase 19 | Pending |
| WIDTH-01 | Phase 20 | Pending |
| RHYTHM-01 | Phase 20 | Pending |
| HEAD-01 | Phase 21 | Pending |
| GRID-01 | Phase 21 | Pending |
| GRID-02 | Phase 21 | Pending |
| AGENTS-01 | Phase 21 | Pending |
| EXCERPT-01 | Phase 22 | Pending |
| SIGNAL-01 | Phase 23 | Pending |
| SIGNAL-02 | Phase 23 | Pending |
| SIGNAL-03 | Phase 23 | Pending |
| SIGNAL-04 | Phase 23 | Pending |
| RESP-01 | Phase 24 | Pending |
| A11Y-01 | Phase 24 | Pending |

**Coverage:**
- v2.2 requirements: 15 total
- Mapped to phases: 15 ✓ (each to exactly one phase)
- Unmapped: 0 ✓ — no orphans, no duplicates

**Phase rollup:**
- Phase 19 — Smart-Quote / Apostrophe Corruption Fix: QUOTE-01, QUOTE-02 (2)
- Phase 20 — Width Tokens & Centering Foundation: WIDTH-01, RHYTHM-01 (2)
- Phase 21 — Per-Route Visual Fixes: HEAD-01, GRID-01, GRID-02, AGENTS-01 (4)
- Phase 22 — Distinct Newsletter Excerpts: EXCERPT-01 (1)
- Phase 23 — Signals Feed: SIGNAL-01, SIGNAL-02, SIGNAL-03, SIGNAL-04 (4)
- Phase 24 — Responsive & Accessibility Pass: RESP-01, A11Y-01 (2)

Cross-cutting note: RESP-01, A11Y-01 (Phase 24) and RHYTHM-01 (Phase 20) are applied across every phase but are each owned and verified holistically in exactly one phase — RHYTHM-01 at the width/token foundation it establishes, RESP-01 + A11Y-01 in the final responsive/a11y pass over the whole redesigned surface.

---
*Requirements defined: 2026-06-10*
*Last updated: 2026-06-10 — roadmap created; all 15 requirements mapped to Phases 19–24 (Traceability + Coverage filled).*
