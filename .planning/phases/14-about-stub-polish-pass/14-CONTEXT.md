# Phase 14: About Stub + Polish Pass - Context

**Gathered:** 2026-06-05
**Status:** Ready for planning

<domain>
## Phase Boundary

The **final v2.0 phase**. Two distinct, frontend-only pieces on the existing vanilla-JS SPA (`docker/web/site/`):

1. **ABOUT-01 — About stub.** Flesh out the already-wired `#/about` route + `#about-view` (a deliberately minimal Phase-11 "honesty stub", commit `7c69e2d`) into the real "What is AgentPulse" stub page using the mockup's About structure, **reconciled to the actual system**. The deeper pipeline-diagram content stays deferred (ABOUT-02, v-next).
2. **POLISH-01 — Spacing/radius consistency sweep.** Site-wide: tighten loose vertical rhythm ("minimalist but not sparse") and normalize all radii to the locked 7–10px token set, snapping the three off-grid `6px` subscribe-form radii to role-appropriate tokens.

**In scope (confirmed this discussion):**
- The About page content + the net-new agent-pill CSS, ported into the Phase-11 design-system tokens (serif/mono, light palette, radius/spacing tokens).
- A site-wide vertical-rhythm tightening (token-anchored) and a radius-normalization sweep across cards, toggle, and buttons.

**This phase does NOT:** change any backend / pipeline / Supabase / content / data; add the pipeline diagram or any richer About content (ABOUT-02); add dark mode (DARK-01); re-wire the `#/about` route (it already exists); **deploy to the live site** — the batch `agentpulse-web` rebuild + accumulated browser-UAT verification is a **separate, operator-approved ship step after** Phase 14 (D-04 below; D-01 batch-deploy from Phase 11).

</domain>

<decisions>
## Implementation Decisions

Pixel-level specifics defer to the downstream **UI-SPEC** (`/gsd-ui-phase 14`) — this phase carries `ui_phase: true` + `ui_safety_gate: true`. These decisions set the direction the UI-SPEC must honor. The mockup is an **intent reference, not markup to copy**.

### About page content (ABOUT-01)
- **D-01: Adopt the mockup's full About structure.** eyebrow ("Behind the Briefing") + `page-title` ("What is AgentPulse") + `page-sub` ("A newsletter written by a multi-agent system") + 3 prose paragraphs + the agent-pill row. Richest stub short of the deferred pipeline diagram; satisfies "minimalist but not sparse." (Mockup: `agentpulse-redesign-mockup.html:349`.)
- **D-02: Reconcile the copy to the REAL system — do NOT ship the mockup wording verbatim.** The mockup simplifies to 5 agents and is inaccurate vs. the actual 8 services. The About copy must be factually correct about how AgentPulse actually works.
- **D-03: Pill roster = content agents + infra prose line.** Render pills for the **5 content-producing agents** — Processor, Analyst, Research, Newsletter, Gato — each with an accurate one-line role, then **one accurate prose sentence** covering the supporting layer (Gato Brain routing/middleware, LLM Proxy budget/wallet governance, Web). Keeps the grid tight while staying truthful; avoids turning the stub into an architecture doc. Exact wording is a copy draft for the planner/UI-SPEC, reviewed by the operator (editorial framing stays in human hands).
- **Implementation note (not a new decision):** `.agent-row` / `.agent-pill` / `.an` / `.ad` CSS is **net-new** — it only lives in the mockup today. Port it into the Phase-11 token system (serif/mono, light surfaces, `--radius-sm/btn`, spacing tokens), not copied from the mockup's dark/standalone styles.

### Vertical rhythm (POLISH-01)
- **D-04: Tighten site-wide, token-anchored, not sparse — magnitude is UI-SPEC's call.** Direction is locked: reduce the loose vertical gaps across all sections (Newsletter, Agent Economy, About, subscribe, nav chrome) using the existing 4px-grid spacing tokens (`--space-xs..3xl`); the result must read denser/more editorial but never cramped. The exact step-downs (which gaps drop by how much) are deferred to the UI-SPEC/planner within the token system.

### Radius normalization (POLISH-01)
- **D-05: Snap off-grid radii to role-appropriate tokens.** The only off-token radii in the CSS are three hardcoded `6px` values in the subscribe form: the email **input** → `--radius-sm` (7px), the submit **button** and the secondary **button** → `--radius-btn` (8px) — matching how inputs/buttons are radiused everywhere else (`style-shared.css:765/808/852`). The sweep must confirm no other off-token radii remain (grep currently shows these 3 are the only ones); everything lands in the locked 3/7/8/10 set.

### Deploy + verification scope
- **D-06: Live deploy + batch UAT is a SEPARATE step after Phase 14 — NOT part of the phase.** Phase 14 delivers the About + polish code and verifies it **locally / in-code** (same model as Phases 11–13). The scoped `agentpulse-web` rebuild to the **live public site**, plus verification of the accumulated **browser-UAT items from Phases 11/12/13/14** (e.g. `13-HUMAN-UAT.md`), is a distinct, **operator-approved** ship step afterward. Honors the standing deploy discipline (scoped + approved + stop at the repo→prod boundary, verify a real rendered result, never auto-advance). This decouples code delivery from the prod cutover.

### Claude's Discretion
- **D-04 magnitude** (how far to tighten each surface) — explicitly handed to the UI-SPEC/planner within the token system.
- Exact About copy wording (the reconciled prose + pill roles + infra sentence) — Claude drafts in the mockup's spirit, corrected for accuracy; operator reviews in the plan/UI-SPEC.
- File organization of new About + agent-pill CSS (which stylesheet section) — mechanical planner discretion, consistent with the hand-authored-CSS / cascade-order convention.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design system (locked by Phase 11 — do not re-derive)
- `.planning/phases/11-design-system-nav-shell/11-UI-SPEC.md` — locked palette hexes, the single-accent reservation list (COLOR-02), serif/mono type scale (weights 400/600), spacing (4px grid) + radius tokens (3/7/8/10), and the `.page-title` / `.eyebrow` display classes the About page reuses.
- `docker/web/site/style-base.css` — the Phase-11 `:root` token layer (`--space-xs..3xl`, `--radius`/`--radius-sm`/`--radius-btn`/`--radius-dot`) + reusable display classes; loaded first (cascade control).
- `.planning/phases/11-design-system-nav-shell/11-CONTEXT.md` — D-01 (batch deploy, the parent of D-06), the nav-shell/back-control contract the About page inherits.
- `.planning/phases/12-newsletter-section-restyle/12-CONTEXT.md` + `.planning/phases/13-agent-economy-grid/13-CONTEXT.md` — the serif-prose + minimal-header patterns the About page reuses; D-01 carried forward each phase.

### Milestone intent & requirements
- `.planning/docs/REDESIGN_BRIEF.md` §6 "Spacing & polish" (tighten loose vertical gaps, minimalist not sparse; cards/toggle/buttons ~7–10px radius, consistent) and §"Out of scope" ("stub the [About] section with the existing copy; we'll iterate on a pipeline diagram separately").
- `.planning/docs/agentpulse-redesign-mockup.html` §"ABOUT" (`:349`) — the About **intent** reference: eyebrow + title + page-sub + 3 paragraphs + `.agent-row`/`.agent-pill` (`:355`), and the `.about p` styling (`:187`). **Copy + pill roster are reconciled to the real system per D-02/D-03 — not copied verbatim.**
- `.planning/REQUIREMENTS.md` — ABOUT-01, POLISH-01 (this phase); ABOUT-02 + DARK-01 deferred (v-next).
- `.planning/ROADMAP.md` §"Phase 14: About Stub + Polish Pass" — goal + 3 success criteria.
- `.planning/PROJECT.md` — the "editorial framing in human hands" constraint (why D-02/D-03 copy is operator-reviewed); the 8-service roster the About copy must reflect accurately (also `CLAUDE.md` "What This Is").

### Codebase (the surface this phase edits)
- `docker/web/site/index.html` — `#about-view` / `.about-stub` (`:79`) currently holds the minimal lede + "Full overview coming in Phase 14" placeholder + a `← Back to Newsletter` backlink; the subscribe section (`#subscribe-section`, `:90`+) holds the three `6px`-radius elements.
- `docker/web/site/app.js` — `#/about` route already wired: `getRoute()` returns `{view:'about'}` (`:134`), `showView()` toggles `#about-view` (`:146`), route→tab map has `about:'about'` (`:815`), `route()` `case 'about'` (`:845`). **No new routing needed** — Phase 14 fills content, it does not wire the route.
- `docker/web/site/style-shared.css` — the three off-token `6px` radii: subscribe email input (`:765`), submit button (`:808`), secondary button (`:852`); also where lightened/tightened section + About + agent-pill rules may land.
- `docker/web/site/style-base.css` — token source for D-04/D-05; About + agent-pill CSS reuse these tokens.

### Deploy (for the SEPARATE post-phase ship step — D-06)
- `.planning/phases/13-agent-economy-grid/13-HUMAN-UAT.md` (+ any 11/12 browser-UAT files) — the accumulated browser-verification items to check against the live site during the batch ship.
- Scoped rebuild: `cd /root/bitcoin_bot/docker && docker compose up -d --build agentpulse-web` (single-container, no new infra — v1.0-proven; `/root/bitcoin_bot` IS prod, local scoped rebuilds).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`#/about` route is fully wired** — `getRoute()`/`showView()`/route→tab map/`route()` all handle `about` already (`app.js:134/146/815/845`). Phase 14 only fills `#about-view` content; success criterion 1 ("reachable from nav, renders the copy") is route-satisfied today.
- **Phase 11 `.page-title` / `.eyebrow` classes** — ready-made for the About eyebrow + title (the current stub already uses them).
- **Design tokens (`style-base.css`)** — `--space-*` (4px grid) for D-04, `--radius-sm`(7)/`--radius-btn`(8) for D-05. No new tokens needed.
- **Serif-prose rules** from Phases 12/13 — the About paragraphs are body prose: serif, no monospace body (TYPE-01).

### Established Patterns
- **Hand-authored CSS, no build step** — cascade order in `index.html` (`style-base.css` first) is the control. New About/agent-pill rules and tightened spacing are just edited/added sections.
- **Whole-page hash routing** via `getRoute()`/`route()` on load + `hashchange`; the About view is shown by `showView('about')` with `window.scrollTo(0,0)`.
- **Back-control convention** — nested views carry `← Back to [section]`; the About stub already has a `← Back to Newsletter` backlink (`index.html:84`) consistent with NAV-03.

### Integration Points
- About content lands inside the existing `#about-view .about-stub` container; the agent-pill row is net-new markup + CSS within it.
- The radius/rhythm sweep touches `style-shared.css` (subscribe form + section gaps) and possibly `style-base.css` chrome paddings — all token-anchored, no per-component magic numbers.

</code_context>

<specifics>
## Specific Ideas

- About structure target = the mockup's About section (eyebrow "Behind the Briefing" → may be reconciled, title "What is AgentPulse", page-sub "A newsletter written by a multi-agent system", 3 paragraphs, agent-pill row), **with accurate copy** reflecting the real 8-service system: 5 content-agent pills (Processor/Analyst/Research/Newsletter/Gato) + one prose sentence for Gato Brain / LLM Proxy / Web.
- Polish target = denser-but-not-sparse vertical rhythm (magnitude UI-SPEC's call) + all radii in the 7–10px token set (the 3 subscribe-form `6px` outliers → input 7px / buttons 8px).
- "Minimalist but not sparse" is the north star for both pieces — tighten, but the page must not feel cramped or empty.

</specifics>

<deferred>
## Deferred Ideas

- **Richer About page with the pipeline diagram (ABOUT-02)** → v-next. Phase 14 ships the prose + agent-pill stub only; the deeper diagram content is explicitly out.
- **Dark mode (DARK-01)** → v-next, out of v2.0.
- **The live deploy + batch browser-UAT verification** → a SEPARATE operator-approved ship step AFTER Phase 14 (D-06), not a deferred capability but a deliberately decoupled next action (e.g. `/gsd-ship` or a manual scoped `agentpulse-web` rebuild, then walk the accumulated 11/12/13/14 HUMAN-UAT items against the live site).

### Reviewed Todos (not folded)
The pending todos in `.planning/todos/pending/` are all v1.0 **backend** follow-ups (analyst `predictions.title` bug, soft spending-cap hardening, `transfer_between_agents` RPC search_path, intake-classifier review follow-ups, economy-map telegram/synthesis, research stale-trigger). None touch the v2.0 frontend About/polish work — reviewed and **not folded**, consistent with the Phase 11/12/13 decision.

</deferred>

---

*Phase: 14-about-stub-polish-pass*
*Context gathered: 2026-06-05*
