# Phase 12: Newsletter Section Restyle - Context

**Gathered:** 2026-06-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Restyle the **Newsletter** edition-list and single-article views onto the Phase 11 design-system shell, and **relocate the Technical/Strategic mode toggle so it lives only inside the Newsletter section** — without changing any dual-mode **content** logic (only the toggle's placement + styling move, and the list/article get the new serif/light treatment).

In scope:
1. **TGL-01** — move the mode toggle out of the global `.hero` into the Newsletter section; remove it from every global/shared position.
2. **TGL-02** — active mode = filled accent + a hint line below ("Architecture, code, implementation" / "Markets, strategy, implications").
3. **Success criterion 3 / TYPE-01 completion** — edition list + single-article render in serif + the light palette with **no monospace body paragraphs** (mono stays for chrome/metadata/code only).

This phase does NOT: change `getModeTitle()`/`getModeContent()` dual-mode content selection or any fetch/data logic; touch the Agent Economy map/status views (Phase 13); add the `#/about` page content (Phase 14 — a minimal stub already shipped in Phase 11); or deploy to prod (batch-deploy, ships after Phase 14).
</domain>

<decisions>
## Implementation Decisions

Visual direction was chosen from a throwaway token-accurate HTML mockup gallery (the user picked one variant per area). Pixel-level specifics are deferred to the downstream **UI-SPEC** (`/gsd-ui-phase 12`); these decisions set the direction it must honor.

### Mode toggle (TGL-01 / TGL-02)
- **D-01: Placement = list view only.** The toggle lives at the top of the **edition-list** view. The **single-article view has NO toggle of its own** — it renders whatever mode is currently selected (mode persists via `localStorage`). Deliberate UX consequence (accepted by operator): to switch Technical↔Strategic while reading, the reader returns to the list. Less chrome in the reading column.
- **D-02: Form = segmented accent pill** (mockup variant **A1**). One pill, two segments; the active segment is a **filled violet** (`--accent`) with white text/weight-600, the inactive segment is `--ink-soft` on the surface; a **mono hint line** sits directly below it (TGL-02). (Not the two-button form.)
- **D-03: Content logic unchanged.** `setMode()` (`app.js:68`) keeps toggling `body.technical`/`body.strategic` to re-render dual content via `renderList()`/`renderArticle()` — only the **control's DOM home and styling move**. The body class no longer drives theme (Phase 11 already decoupled palette to `:root`).

### Edition list (success criterion 3)
- **D-04: Restyled rows** (mockup variant **B1**) — keep the existing `.article-entry` row anatomy (`renderList()` `app.js:164`): a **mono kicker** `EDITION #N · {date}` (add the date — currently kicker is edition-number only), a **serif title link** (`.entry-title`), and a short **serif excerpt** (`.entry-preview`). Restyle to the light palette + serif with **tightened vertical gaps** (brief §57 "minimalist but not sparse"); rows divided by a `--line` rule. Not cards, not title-only-dense.

### Article reading view (success criterion 3)
- **D-05: Richer magazine** (mockup variant **C2**) — restyle `renderArticle()` (`app.js:217`) output: a **mono kicker** (`Edition #N · {Technical|Strategic}`), a **larger serif display title**, a **byline/metadata** line, an emphasized **lead paragraph**, and styled **blockquotes** (accent-soft fill + `--accent` left border) and **code** surfaces. Body prose is **serif** (TYPE-01 — no mono paragraphs); `code`/`pre` may use `--mono` (code is on the allowed-chrome list, brief §33). The existing **PREVIEW banner** (status `preview` editions) stays, restyled to the palette.
- **D-06 (constraint on D-05):** "Magazine" must stay **within the minimalist single-serif-display system** — one serif display style, restrained hierarchy, weights 400/600 only. No second display family, no heavy ornamentation. Richer ≠ busier.

### Newsletter header (replaces the global hero for the list view)
- **D-07: Minimal header** (mockup variant **D3**) — at the top of the **list view**: a **serif page-title** (e.g. "Intelligence Brief") + a **mono metadata line** (e.g. `Latest: Edition #N · {date}`). **Drop the "WEEKLY INTELLIGENCE BRIEFING" tagline and the eyebrow** (not the eyebrow+page-title D1 variant, not the kept-hero D2 variant). The **A1 toggle pill + hint line** sit directly beneath this header. This is the D-02-from-Phase-11 hero restructure, scoped to the Newsletter list. The article view's header is the **D-05 magazine** title treatment, under the Phase-11 `← Back to Newsletter` control.

### Claude's Discretion
- Exact DOM mechanism for the hero restructure (repurpose the global `.hero` block vs. render the minimal header inside the list view, and how the global hero behaves on non-Newsletter routes that Phase 13 owns) is left to the planner/UI-SPEC — as long as the toggle ends up **only** in the Newsletter section (TGL-01) and the map/status headers aren't regressed.
- Excerpt length, exact spacing/radius values, link underline treatment, byline format — UI-SPEC/planner discretion within the chosen variants and the Phase 11 token system.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design system (reused, locked by Phase 11)
- `.planning/phases/11-design-system-nav-shell/11-UI-SPEC.md` — the locked palette hexes, serif/mono type scale (weights 400/600), spacing (4px grid) + radius (3/7/8/10) tokens, and the mono-for-chrome reservation list this phase builds on. Do not re-derive tokens.
- `docker/web/site/style-base.css` — the Phase 11 `:root` token layer + the reusable `.page-title` (`clamp(30px,5vw,46px)`/600) and `.eyebrow` (mono 11px kicker) display classes; the legacy-token compatibility bridge (article/list component tokens already map to the light palette).

### Milestone intent & requirements
- `.planning/docs/REDESIGN_BRIEF.md` §2 (mode toggle — Newsletter-only), §3 (typography — mono NEVER for paragraphs), §"newsletter list/article" + §57–58 (tighten gaps, minimalist, ~7–10px radius). Milestone goals + out-of-scope.
- `.planning/docs/agentpulse-redesign-mockup.html` — visual **intent** reference (not markup to copy) for the per-view eyebrow/page-title and toggle treatment.
- `.planning/REQUIREMENTS.md` — TGL-01, TGL-02 (this phase).
- `.planning/ROADMAP.md` §"Phase 12: Newsletter Section Restyle" — goal + 3 success criteria.

### Codebase (the surface this phase edits)
- `docker/web/site/app.js` — `setMode()` (`:68`, keep content-render logic, move the control), `updateHero()` (`:108`), `renderList()` (`:164`, the `.article-entry` rows), `renderArticle()` (`:217`, marked → `#newsletter-content`), `getModeTitle()`/`getModeContent()` (`:356`/`:361`, dual-mode selection — DO NOT change), `showView()` (the per-view chrome toggling).
- `docker/web/site/index.html` — the global `.hero` block (`hero-tagline` / `hero-headline` / `.mode-toggle` btn-technical/btn-strategic / `mode-subtitle`, lines ~32–42) to restructure; `#list-view` (`#newsletter-list`) and `#reader-view` (`#newsletter-content` article) containers.
- `docker/web/site/style-shared.css` — current `.hero`, `.mode-toggle`/`.toggle-btn`, `.article-entry`/`.section-label`/`.entry-title`/`.entry-preview`, and `article` prose rules to restyle (these consume the bridged component tokens). New Newsletter styles may live in `style-base.css` or a new section per planner discretion.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`setMode()`** (`app.js:68`) — the entire dual-mode re-render mechanism is reused verbatim; only the trigger control's markup/placement changes. It already persists to `localStorage`, updates the URL `?mode=`, toggles the body class, and re-renders the visible list/article.
- **`.page-title` / `.eyebrow`** classes (style-base.css, shipped Phase 11) — ready-made serif display + mono kicker for the minimal header (D-07) and magazine article title (D-05).
- **`renderList()` / `renderArticle()`** — already produce the list rows and the marked-parsed article; this phase restyles their output + tightens markup, not the data flow.
- **PREVIEW banner** — `renderArticle()` already emits a banner for `status === 'preview'`; restyle, don't rebuild.

### Established Patterns
- **Hand-authored CSS, no build step** — cascade order in `index.html` is the control; `style-base.css` loads first.
- **`body.technical/.strategic` = content re-render only** (decoupled from theme since Phase 11) — keep using it for `getModeTitle/Content`; never reintroduce it as a theme/palette selector.
- **No monospace body paragraphs** (TYPE-01) — serif prose; mono only for kicker/metadata/tab/button/code.

### Integration Points
- The relocated toggle markup moves from the global `.hero` (index.html) into the **Newsletter list view** rendering; its `onclick="setMode(...)"` wiring is preserved.
- The minimal Newsletter header (D-07) replaces the global hero's tagline/headline **for the list view**; planner decides whether to repurpose or hide the global `.hero` on Newsletter routes (and must not regress the map/status hero that Phase 13 owns).
- The article magazine treatment (D-05) sits under the Phase-11 `← Back to Newsletter` back-control already present in `#reader-view`.
</code_context>

<specifics>
## Specific Ideas

- Decisions were chosen from a token-accurate mockup gallery (throwaway, `/tmp/ap-mockups/index.html`): **A1** (segmented accent pill), **B1** (restyled rows), **C2** (richer magazine), **D3** (minimal header). The gallery is ephemeral — these decisions are the record.
- Toggle pill: active segment filled `--accent` (white text, 600), inactive `--ink-soft`; hint line in `--mono` `--ink-faint` directly below.
- List rows: mono kicker `EDITION #N · {date}`, serif title link (→ `--accent-ink` on hover), serif excerpt; rows separated by a `--line` divider; tightened vertical rhythm.
- Article: mono kicker, big serif display title, byline, emphasized lead, accent-soft blockquotes, mono `code` — all within one serif display style (D-06).
</specifics>

<deferred>
## Deferred Ideas

- **In-article mode switch** — explicitly out (D-01: toggle is list-only; the reading view has no toggle). If the operator later wants an in-article switch, it's a small follow-up, not this phase.
- **Agent Economy 2-col grouped card grid + `style-map.css` tier-accent/Courier cleanup** → Phase 13 (MAP-01..04, WR-02/WR-03 from the Phase 11 review).
- **Full "What is AgentPulse" page + site-wide spacing/radius polish + `backdrop-filter` fallback** → Phase 14 (ABOUT-01, POLISH-01, WR-04). A minimal `#/about` stub already shipped in Phase 11.
- **Dark mode (DARK-01), richer About w/ diagram (ABOUT-02)** → v-next, out of v2.0.

### Reviewed Todos (not folded)
- All 7 pending todos matched only by keyword and are v1.0 **backend** follow-ups (intake-classifier WR-02/04/05, economy-map telegram/synthesis, `transfer_between_agents` RPC, analyst `predictions.title`, soft spending-cap hardening, research stale-trigger files). None touch the frontend Newsletter restyle — reviewed and **not folded**, consistent with the Phase 11 decision.

</deferred>

---

*Phase: 12-newsletter-section-restyle*
*Context gathered: 2026-06-04*
