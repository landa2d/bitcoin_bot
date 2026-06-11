# Phase 22: Per-Section Visual Fixes - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Three independent, non-conflicting visual fixes — one per requirement cluster, no
file contention — on the assembled single-scroll landing + the edition detail route:

- **HEAD-01** — edition-header de-dup on the **detail route** (`#reader-view` /
  `renderArticle` in `app.js`): the H1 carries only the headline; edition number,
  date, and mode appear exactly once, in the byline below it.
- **GRID-01 / GRID-02** — the **`#map` landing section** (`renderHub` in `app.js`):
  the tier card grids go 3-col with a maturity legend under the heading.
- **AGENTS-01** — the **`#about` landing section** (static markup in `index.html`):
  the agent grid splits into a numbered pipeline + a bulleted supporting layer with
  a violet approval callout.

**Frontend-only.** Files: `docker/web/site/app.js`, `docker/web/site/index.html`,
`docker/web/site/style-shared.css` (+ `style-base.css` if a token is needed). No
backend, no schema, no migration, no content/data mutation.

**Out of scope (other phases):** the holistic responsive + a11y pass incl.
`:focus-visible` / `prefers-reduced-motion` / real-`<a>` audit = Phase 25 (this phase
must not regress a11y and should ship the prescribed breakpoints, but the full pass
is Phase 25); newsletter excerpts = Phase 23; Signals data + RLS = Phase 24; the
single-scroll/scroll-spy navigation architecture = Phase 21 (already shipped). This
phase changes section CONTENT/LAYOUT, not navigation.
</domain>

<decisions>
## Implementation Decisions

### HEAD-01 — edition header de-duplication (detail route)
- **D-01 (eyebrow — DISCUSSED):** **Drop the eyebrow entirely.** The reader chrome
  today (`renderArticle`, `app.js:430-435`) has BOTH an eyebrow `Edition #N · Mode`
  ABOVE the title and a byline `Edition #N · date · Mode` BELOW it — duplication
  inside the chrome itself, independent of any title suffix. After the fix: H1 =
  headline only; **one** byline below carries edition/date/mode. No non-edition kicker
  is added (operator rejected keeping the eyebrow slot).
- **D-02 (byline — DISCUSSED):** Keep the EXISTING byline format/order verbatim —
  `Edition #N · date · Mode` (the `·` U+00B7 separator + `formatDate()` + `MODES[mode].label`
  already at `app.js:434`). The only header change is removing the eyebrow line + the
  title-suffix strip below.
- **D-03 (title suffix — strip-at-render, NEVER storage):** Strip a baked
  `— Edition #N | <date>`-style suffix from the title **at render only**, in
  `getModeTitle()` (`app.js:563`) so it covers BOTH `data.title` and `data.title_impact`
  (Technical + Strategic). Apply the regex **unconditionally/defensively** (a no-op
  when no suffix is present) so a future edition that bakes the suffix is also covered.
  **No stored-data mutation** (consistent with v2.0 append-at-render; HEAD-01 requirement).
- **D-04 (research must confirm the stored format — Phase-19 discipline):** Before
  writing the regex, query the raw stored `newsletters.title` / `title_impact` bytes
  for a known-bad edition (e.g. 30) to confirm (a) whether the suffix is actually baked
  in and (b) its EXACT separator/pattern (em-dash vs `—`, `|` vs `·`, date format). The
  brief's example pattern ` — Edition #\d+ \| .*$` is a STARTING point — match reality,
  do not assume. (Phase-19 lesson: reproduce the stored bytes, don't infer.)

### GRID-01 / GRID-02 — Agent Economy map 3-col + maturity legend (`#map` section)
- **D-05 (keep tier grouping — confirmed by the mockup):** KEEP the three
  `tier-section`s (`renderHub`, `app.js:753`) with their `tier-label` headings
  (SUBSTRATE / BEHAVIOR / FRAME); do NOT flatten to one grid. The mockup
  (`agentpulse-redesign (1).html:377-418`) renders exactly this shape — a `tier-label`
  above each per-tier `map-grid`. Canonical `economy_map` taxonomy (3 tiers), never the
  mockup's placeholder blocks.
- **D-06 (3-col grid — from requirement):** Each tier `.grid` (`style-shared.css:261`)
  goes from `repeat(2,1fr)` → `repeat(3,1fr)`, collapsing responsively **3 → 2 at
  ≤880px → 1 at ≤600px** (replacing the single `@max-width:640px` rule at
  `style-shared.css:339`). Note: the `behavior` tier has 4 blocks, so it naturally wraps
  3 + 1 in a 3-col grid — acceptable (the mockup's Behaviour tier does the same).
- **D-07 (legend — DISCUSSED, 5-segment):** The maturity legend mirrors the **real
  5-segment pill** the cards use (`renderMaturityPill`, `app.js:578` — exactly 5 `.seg`,
  `style-shared.css:192-212`), NOT the mockup's illustrative 3-bar sketch. Form:
  `Maturity  ■ □ □ □ □   nascent → established`. The legend's scale must equal the
  cards' scale — that IS the point of GRID-02. Placed **once**, under the main
  "The Agent Economy" `page-title` in the `.prose` header (`renderHub`, `app.js:795-800`),
  not per-tier. New CSS class (e.g. `.legend`); token-only colors (RHYTHM-01).
- **D-08 (deferred card — DISCUSSED, keep full-width):** The `frame` tier is a single
  deferred block (`regulation-legal`, no body) rendered today as a full-width card
  (`.card-deferred { grid-column: 1 / -1 }`, `style-shared.css:317`). KEEP it full-width
  in the 3-col grid — it reads as the map's "lightly-populated closing frame" (a PROJECT
  decision) rather than one orphaned narrow card with two empty columns beside it. No
  change to the deferred-detection logic (`!current_body_version_id`, `app.js:734`).
- **D-09 (maturity values — read-only):** Each block's filled-segment count already
  comes from stored `economy_map` maturity via `MATURITY_STAGE[b.maturity]`
  (`app.js:583`); GRID-02's "fill matches stored value" is ALREADY TRUE in code. No
  schema change, no new query, no `.in_()` — `renderHub`'s single `sb.schema('economy_map')`
  read is unchanged. Verification is a read-only check that pill fill == stored maturity.

### AGENTS-01 — About agent grid (`#about` section) — NOT discussed; locked to mockup + my recommendation
- **D-10 (layout — locked by requirement + mockup):** Replace the current uniform
  5-pill `.agent-row` (`index.html:131-152`) with the mockup's `made-cols` 2-col
  (`agentpulse-redesign (1).html:429-490`):
  - LEFT "The pipeline · in order": **numbered 01–04** — Processor / Analyst / Research
    / Newsletter (a real sequence; numbering justified).
  - RIGHT "The supporting layer": **bulleted** (dot, NOT numbered) — Gato / LLM proxy /
    web front end.
  - A violet **`.approval` callout**: "**Nothing publishes without human approval.**
    Every edition is drafted by the system and shipped only after an operator signs off."
  Static `index.html` markup edit + net-new token-anchored CSS (analog: existing
  `.agent-row`/`.agent-pill`, `style-shared.css:921-958`). Collapses 2-col → 1-col on
  mobile. Option B from the brief (uniform 3×2 grid) is NOT taken — AGENTS-01 mandates
  the pipeline/supporting split.
- **D-11 (approval line de-dup):** Pull the "nothing publishes without human approval"
  clause OUT of intro prose P2 (`index.html:126`) now that it lives in the callout —
  avoid stating it twice.
- **D-12 (copy accuracy — flag for operator review at plan/verify):** The mockup folds
  the conversational middleware ("Gato Brain") into a single supporting-layer entry
  "Gato". v2.0's accuracy bar (D-02/D-03) distinguished Gato (Telegram interface) from
  Gato Brain (middleware) and locked "eight cooperating services". The plan should use
  the mockup's draft copy but SURFACE this Gato-vs-Gato-Brain wording (and the
  service-count phrasing) as an operator-reviewable accuracy point — do not silently
  drop Gato Brain. Pull-forward: this is copy, not structure; structure is locked.

### Claude's Discretion
- Exact new CSS class names + the precise legend markup/sizing (mirror the pill).
- The exact strip-at-render regex (after D-04 confirms the stored format).
- Where the 3→2→880 / 2→1→600 breakpoints live (consolidate with the existing
  `@640px` rule vs add new media queries) — planner's call, honoring D-06.
- Final About supporting-layer descriptions, subject to the D-12 accuracy review.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design contract (the spec for this phase — brief + mockup)
- `.planning/docs/REDESIGN_CC_BRIEF.md` — §"TASK 3 — Article header de-duplication"
  (HEAD-01), §"TASK 4 — Agent Economy map: 3-col grid + maturity legend" (GRID-01/02,
  incl. the legend markup), §"TASK 5 — What is AgentPulse agent grid" (AGENTS-01).
- `.planning/docs/agentpulse-redesign (1).html` — INTENT/FORM reference: map section
  `:362-419` (tier-label + 3-col `map-grid` + 3-bar legend `:369-375`), About/"How it's
  made" `:421-491` (`made-cols`, numbered `.idx` pipeline, bulleted `.dot` supporting,
  `.approval` callout `:486-488`). Reference for intent — canonical block list/copy comes
  from `economy_map` + the operator accuracy bar, NOT the mockup's placeholder taxonomy.

### Phase requirements + goal
- `.planning/REQUIREMENTS.md` — HEAD-01 (line 38), GRID-01 (42), GRID-02 (43),
  AGENTS-01 (47); cross-cutting RESP-01/A11Y-01 (Phase 25), RHYTHM-01 (token-only color).
- `.planning/ROADMAP.md` — §"Phase 22: Per-Section Visual Fixes" goal + 3 success
  criteria + notes; Phases 23–25 (so the plan respects later-phase ownership).

### Code to modify / reuse (the implementation targets)
- `docker/web/site/app.js` — `renderArticle` (`:408-439`, HEAD-01 header), `getModeTitle`
  (`:563`, title-suffix strip site), `renderMaturityPill` (`:578`, the 5-seg pill the
  legend mirrors), `renderHub`/`renderTile`/`tierSection` (`:702-807`, the map grid +
  where the legend inserts), the `.prose` hub header wrap (`:795-800`).
- `docker/web/site/index.html` — `#about` section static markup (`:117-156`, the
  `.agent-row` → `made-cols` rewrite); `#map` section (`:102-106`).
- `docker/web/site/style-shared.css` — `.grid` (`:261`, 2→3 col), `@640px` collapse
  (`:339`, → 3/2/1 breakpoints), `.card-deferred` (`:317`), `.maturity-pill`/`.seg`
  (`:192-212`, legend analog), `.agent-row`/`.agent-pill` (`:921-958`, About analog).
- `docker/web/site/style-base.css` — `:root` token layer (add a token only if needed;
  RHYTHM-01 token-only color discipline).

### Phase prior context + conventions
- `.planning/phases/21-single-scroll-landing-scroll-spy-nav/21-CONTEXT.md` — the
  single-scroll landing the `#map`/`#about` sections now live in; the scope guard (must
  not regress Phase 20 width/rhythm, the sticky-header maturity-overlap fix, the toggle).
- `.planning/phases/20-width-tokens-centering-foundation/20-CONTEXT.md` — `.prose`/`.wide`
  axes + `--measure`/`--wide`/`--gutter` tokens the new markup must sit on.
- `./CLAUDE.md` — deploy discipline; web container `__SUPABASE_URL__` entrypoint
  substitution (preview vs live); scoped rebuild SERVICE key is `web` (not `agentpulse-web`).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`renderMaturityPill(b, deferred)`** (`app.js:578`) — emits exactly 5 `.seg`;
  CSS keys fill off `data-stage` (`MATURITY_STAGE[b.maturity] || 1`). The legend
  (D-07) is a static 5-seg copy of this markup + a label; no new fill logic needed.
- **`.card` / `.grid` / `.card-deferred`** (`style-shared.css:261-319`) — the card
  grid is already built; GRID-01 is a column-count + breakpoint change, not a rebuild.
- **`.agent-row` / `.agent-pill` / `.an` / `.ad`** (`style-shared.css:921-958`) — the
  About grid's existing token-anchored analog to port from for the `made-cols` rewrite.
- **`MODES[mode].label`** (used at `app.js:429,434`) — the Technical/Strategic label is
  already resolved from a constant, not hardcoded; the byline reuses it.

### Established Patterns
- Single hand-authored CSS, no build step. `style-base.css` loads first (`:root` +
  serif body win the cascade); `style-shared.css` is the legacy component layer.
- Map markup is JS-generated in `renderHub` (`app.js`); About markup is STATIC in
  `index.html`. So GRID-* edits `app.js`+CSS; AGENTS-01 edits `index.html`+CSS;
  HEAD-01 edits `app.js`(`renderArticle`/`getModeTitle`). Three different files →
  the brief's "non-conflicting, parallelizable" claim holds.
- `economy_map` reads use `sb.schema('economy_map')` (Accept-Profile set automatically),
  NO defensive `.eq('status',…)` filter (RLS is the boundary), never `.in_()`.

### Integration Points
- `#map` / `#about` sections render INSIDE the Phase-21 single-scroll `#landing`; the
  edition page is a Phase-21 DETAIL route (`#reader-view`). Changes are intra-section —
  they must not touch the scroll-spy / two-mode router or the Phase-20 width axes.
- The map `.prose` header (page-title + subline + intro) is where the legend inserts;
  the tier grids render OUTSIDE the `.prose` wrap on the `--wide` band (`app.js:795-803`).

### Deploy (worktree-unsafe — orchestrator-owned)
- Ship via scoped `docker compose ... web` rebuild (SERVICE key `web`, NOT the
  `agentpulse-web` container_name); NO `--delete`; prod↔main drift check first;
  branch + `/diff` per work group + operator approval. Worktree executors build stale
  code on a `--build` task → run no-worktree/sequential, orchestrator owns the live
  rebuild + verify (memory: scoped-rebuild → worktree-unsafe; web compose service name).
</code_context>

<specifics>
## Specific Ideas

- **The brief + mockup ARE the design contract** for this phase (UI-SPEC posture for
  v2.2 visual phases) — plan with `--skip-ui` (no separate UI-SPEC); the mockup +
  brief + this CONTEXT are the design spec. Two of the three fixes (map tier-grid,
  About `made-cols`) are confirmed verbatim by the mockup; HEAD-01 follows the brief.
- The mockup is INTENT/FORM reference for the map + About SHAPE, but the canonical
  block list/grouping and the About copy come from `economy_map` + the operator
  accuracy bar — never the mockup's placeholder blocks (Discovery/Orchestration/etc.).
- D-04 carries the Phase-19 discipline forward: confirm the stored title bytes before
  writing the strip regex; don't assume the brief's example pattern matches reality.
</specifics>

<deferred>
## Deferred Ideas

None new from this discussion — stayed within HEAD-01 / GRID-01 / GRID-02 / AGENTS-01
scope. (Excerpts = Phase 23; Signals data + RLS = Phase 24; holistic responsive/a11y
incl. `:focus-visible` / `prefers-reduced-motion` / `<a>` audit = Phase 25.)

The Gato-vs-"Gato Brain" About copy accuracy (D-12) is NOT deferred — it's an in-phase
operator-reviewable point at plan/verify, not a separate phase.
</deferred>

---

*Phase: 22-per-section-visual-fixes*
*Context gathered: 2026-06-11*
