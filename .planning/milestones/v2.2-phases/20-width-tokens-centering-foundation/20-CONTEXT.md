# Phase 20: Width Tokens & Centering Foundation - Context

**Gathered:** 2026-06-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Kill the dead left gutter and establish the shared visual baseline every later v2.2
phase sits on. Two deliverables:

- **WIDTH-01:** Two coexisting, both-centered max-widths — a narrow prose column
  (`--measure`, ~60–70 char lines) for reading copy, and a wider container
  (`--wide`) for anything tiled (newsletter list, Agent Economy map, Signals, card
  grids). On a wide monitor, no large empty band on the left.
- **RHYTHM-01:** Token-only color (no hardcoded hex — every surface themes from the
  existing CSS variable system: warm off-white + violet) and a section-rhythm
  hierarchy (one full-strength rule between major sections, `0.5px` hairline within),
  established and verified holistically HERE as the baseline later phases conform to.

Frontend-only: `style-base.css` / `style-shared.css` + `app.js` class application.
Separate routes preserved (locked at v2.2 start). The mockup is INTENT reference,
not markup to copy. NOT in scope: per-route visual fixes (Phase 21), excerpts
(Phase 22), Signals feed itself (Phase 23), the holistic responsive/a11y pass
(Phase 24) — RESP-01/A11Y-01 are owned there.
</domain>

<decisions>
## Implementation Decisions

### Width tokens (discussed)
- **D-01:** Adopt the mockup/brief width values verbatim:
  - `--measure: 64ch` — prose column (edition body + About intro), ~60–70 char lines
  - `--wide: 1080px` — wide container (newsletter list, map grid, Signals, card grids)
  - `--gutter: clamp(1.25rem, 5vw, 3.5rem)` — responsive side padding (`padding-inline`)
  These REPLACE the current single `.container { max-width:720px }`. Class shape from
  the brief: `.prose { max-width:var(--measure); margin-inline:auto; padding-inline:var(--gutter) }`
  and a wide container (`max-width:var(--wide); margin-inline:auto; padding-inline:var(--gutter)`).
  Reconcile the naming mismatch (brief calls it `--container-wide` / `.container-wide`;
  mockup uses `--wide` / `.wide`) — pick ONE and use it consistently; `--wide` / `.wide`
  preferred (shorter, matches the mockup's emitted markup).

### Nav / chrome alignment (discussed)
- **D-02:** The sticky nav widens to `--wide` (1080px) so brand/tabs align to the same
  left/right edges as the wide content below — ONE centered axis. Matches the mockup's
  `<nav class="nav wide">`. (Nav is currently `max-width:880px` in `style-base.css:125`.)

### Prose-vs-wide application (default — not deep-discussed; operator deferred to the brief)
- **D-03:** Follow the brief's explicit map: edition body + the "What is AgentPulse"
  intro → `--measure` (prose); newsletter list, Agent Economy map, Signals, and the
  agent-card grid → `--wide`. On article pages the prose stays narrow but centered.
- **D-04:** Boundary bands (hero headline/date/mode-toggle, edition-page header/metadata)
  default to: reading copy (hero subtitle, edition header text) in prose width; the
  band sits on the wide centered axis. Researcher/planner resolves the exact hero/header
  treatment — keep it centered, never left-pinned.

### Section rhythm (default — not deep-discussed; operator deferred to ROADMAP rule)
- **D-05:** Full-strength rule (`--line-strong`-weight, 1px) between MAJOR route sections
  (e.g. hero↔body, between map tiers, between About blocks); `0.5px` hairline (`--line`)
  for WITHIN-section separations (sub-sections, list rows, card-internal). Researcher
  maps "major vs within" per route. Applied site-wide but owned + verified HERE.

### Gutter root-cause (default — operator deferred, but with a firm directive)
- **D-06:** VERIFY-FIRST. The current `.container` is already `max-width:720px; margin:0 auto`
  (centered), so the "pinned center-left" gutter cause is NOT the obvious one and must be
  pinpointed before the fix is applied — likely route-specific (the map `#map-view .content-area`,
  an article's internal column, or a width override). Research MUST identify the actual
  left-pin site and confirm it, then apply `.prose`/`.wide` there. (Phase-19 lesson:
  do not assume the cause; reproduce it. Matches the brief's "read existing code → propose plan.")

### Claude's Discretion
- Exact CSS class names and where the two wrappers are applied in `app.js` (per-route
  class application) — planner decides, honoring D-01..D-06.
- Whether to retire the legacy `.container` (720px) entirely or repurpose it as `.prose`.
- The single stray hardcoded `#fff` (`style-shared.css:100`, `color:#fff`) and the nav's
  `color:#fff` — tokenize or leave as an intentional on-accent white per RHYTHM-01 judgment.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source brief + mockup (the spec for this phase)
- `.planning/docs/REDESIGN_CC_BRIEF.md` §"TASK 2 — Width tokens & centering (the dead-gutter fix)" — the prescribed `--measure`/`--gutter`/`.prose`/`.container-wide` recipe and the apply-map; also the "Dead left gutter" defect description.
- `.planning/docs/agentpulse-redesign (1).html` — INTENT reference (not markup to copy). Defines `--measure: 64ch`, `--wide: 1080px`, `.wide`/`.prose` classes, and `<nav class="nav wide">` (the nav-on-wide-axis decision).

### Phase requirements
- `.planning/ROADMAP.md` §"Phase 20: Width Tokens & Centering Foundation" — goal + 4 success criteria.
- `.planning/REQUIREMENTS.md` — WIDTH-01 (line 27), RHYTHM-01 (line 57); cross-cutting note (line 139): RHYTHM-01 owned + verified holistically in Phase 20.

### Code to modify / reuse
- `docker/web/site/style-base.css` — `:root` token layer (colors + spacing exist; `--measure`/`--wide`/`--gutter` to ADD here); `.nav` width at `:120-127`.
- `docker/web/site/style-shared.css` — legacy component layer; the `.container { max-width:720px; margin:0 auto }` at `:20`, the map `.content-area` at `:130`, card/grid rules (`:256`, `:264`, `:916`).
- `docker/web/site/app.js` — per-route render + class application (`newsletter-list`, `newsletter-content`, `#map-view .content-area`, `#block-content`).
- `docker/web/site/index.html` — `<body>` → `<header><nav class="nav">` → `<div class="container">` → hero + `<main>` structure (`:13-43`).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Token system already exists** (`style-base.css:10-66`): `--bg`/`--surface`/`--ink*`/`--line`/`--line-strong`/`--accent*` + a legacy-token compatibility bridge. RHYTHM-01's "token-only color" is mostly already true — only a `#fff` at `style-shared.css:100` and the nav's on-accent `color:#fff` are literal. `--line` / `--line-strong` are the natural rhythm-rule colors.
- **`.nav` is already centered** (`max-width:880px; margin:0 auto`) — D-02 just changes 880px → `--wide`.
- **Spacing scale** (`--space-xs..3xl`, 4px grid) is established for section rhythm spacing.

### Established Patterns
- Single hand-authored CSS, no build step. `style-base.css` loads FIRST so its `:root` + serif body win the cascade over `style-shared.css` legacy rules.
- `body > header` (NOT bare `header`) scopes the sticky chrome — do not regress the quick-task 260609-ivq maturity-overlap fix.
- The deployed `/srv/app.js` differs from repo only by the `__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` entrypoint substitution — not a real divergence.

### Integration Points
- The single `.container` (720px) currently wraps hero + `<main>` + every route. Splitting into `--measure` (prose) + `--wide` (tiled) is the core structural change; per-route class application happens in `app.js` innerHTML emission and `index.html`.
- The OTHER css files (`style.css`, etc.) are legacy/unloaded — index.html loads only `style-base.css` + `style-shared.css`.

### Deploy (worktree-unsafe — orchestrator-owned)
- Ship via scoped `docker compose ... web` rebuild (the SERVICE key `web`, not container_name); NO `--delete`; prod↔main drift check first; operator approval. (Memory: web compose service name; scoped/approved deploys.)
</code_context>

<specifics>
## Specific Ideas

- "Mockup values verbatim" — operator explicitly chose the mockup's `64ch` / `1080px` /
  `clamp(1.25rem, 5vw, 3.5rem)` rather than tuning, and the nav-on-wide-axis (`<nav class="nav wide">`).
- The mockup is INTENT reference only — reproduce the centering intent across the
  existing separate routes, do NOT lift its markup.
</specifics>

<deferred>
## Deferred Ideas

None new from this discussion — stayed within WIDTH-01 / RHYTHM-01 scope. (Per-route
visual fixes, excerpts, Signals, and the responsive/a11y pass are already their own
phases 21–24.)

### Reviewed Todos (not folded)
- `2026-05-28-pay-endpoint-500-transfer-rpc-search-path.md` — transfer_between_agents RPC blocker. Keyword-only match ("phase/before"); a backend payments item, unrelated to this CSS phase. Stays in the backend-hardening backlog.
- `2026-05-28-phase05-review-followups-wr02-wr04-wr05.md` — Phase 05 intake-classifier review follow-ups. Keyword-only match; backend, unrelated. Stays parked.
</deferred>

---

*Phase: 20-width-tokens-centering-foundation*
*Context gathered: 2026-06-10*
