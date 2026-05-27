---
phase: 04-hub-block-and-status-renderer
plan: 02
type: execute
wave: 2
depends_on:
  - 04-01
files_modified:
  - docker/web/site/app.js
autonomous: true
requirements:
  - RNDR-01
  - RNDR-04
tags:
  - frontend
  - spa
  - renderer
  - hub
must_haves:
  truths:
    - "Visiting #/map fires a single Supabase query — `sb.schema('economy_map').from('blocks').select('*').order('sort_order', { ascending: true })` — per D-13, D-16"
    - "Hub renders three tier sections in order — SUBSTRATE (3 blocks) → BEHAVIOR (3 blocks) → FRAME (1 block) — with tier-label headings — per D-13"
    - "Each block tile is an `<a href=\"#/map/{slug}\" data-accent=\"{accent}\" class=\"block-tile\">` wrapping title + subtitle + maturity pill; the whole tile is the link — per D-14"
    - "The maturity pill emits exactly 5 `<span class=\"seg\"></span>` children with data-stage resolved via MATURITY_STAGE[block.maturity] — matches tokens-preview.html pill markup contract"
    - "updateHero() is called with HUB_STORYLINE + (last-touched timestamp OR empty) — per D-02"
    - "Every DB string (block.title, block.subtitle) passes through escapeHtml() — per PATTERNS §'Always escape DB strings'"
    - "Mode toggle is hidden on #/map via the showView() extension shipped in plan 04-01 — per D-03"
    - "Hub reads `blocks.maturity` from the same single source the status page reads — RNDR-04 one source of truth"
  artifacts:
    - path: docker/web/site/app.js
      provides: "loadHub() + renderHub() — full hub renderer wired to economy_map"
      contains: "function renderHub"
  key_links:
    - from: "loadHub()"
      to: "sb.schema('economy_map').from('blocks')"
      via: "supabase-js v2 .schema() — sets Accept-Profile: economy_map automatically"
      pattern: "sb\\.schema\\(['\"]economy_map['\"]\\)\\.from\\(['\"]blocks['\"]\\)"
    - from: "renderHub()"
      to: "innerHTML on a #map-view child container"
      via: "string-concat HTML with escapeHtml() on every DB string"
      pattern: "document\\.getElementById\\(['\"]map-view['\"]\\)"
    - from: "block.maturity enum"
      to: "data-stage integer 1..5"
      via: "MATURITY_STAGE[block.maturity]"
      pattern: "MATURITY_STAGE\\["
---

<objective>
Replace the no-op `loadHub()` stub shipped in plan 04-01 with a full hub renderer: query the seven blocks once, group by tier in JS, render a tier-grouped tile grid with tier accent + maturity pill, and update the hero with the storyline header. The hub becomes operator-visible after this plan deploys.

Purpose: Deliver RNDR-01 (hub page) and the hub half of RNDR-04 (one source of truth — both hub pills and status rows read `blocks.maturity` from the same query shape).

Output: docker/web/site/app.js — loadHub() now performs the query and dispatches to a new renderHub() function that emits the three-section, seven-tile DOM.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/04-hub-block-and-status-renderer/04-CONTEXT.md
@.planning/phases/04-hub-block-and-status-renderer/04-PATTERNS.md
@.planning/phases/04-hub-block-and-status-renderer/04-01-shared-infra-and-shell-PLAN.md
@docker/web/site/app.js
@docker/web/site/tokens-preview.html
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement loadHub() + renderHub() inside app.js</name>
  <files>docker/web/site/app.js</files>
  <read_first>
    - docker/web/site/app.js (the file being modified — re-read fully; pay attention to loadList() at lines 135-152, renderList() at lines 107-133, escapeHtml() at lines 274-278, updateHero() at lines 82-85, formatDate() at lines 280-285. Plan 04-01 will have added module constants HUB_STORYLINE, MATURITY_STAGE, TIER_LABELS, and a stub `async function loadHub() { showView('map'); }` — this task replaces the stub body.)
    - docker/web/site/tokens-preview.html (canonical maturity-pill markup lines 78-82 — Phase 4 must emit matching structure)
    - .planning/phases/04-hub-block-and-status-renderer/04-PATTERNS.md (§ "docker/web/site/app.js" — Pattern Assignment #4 "Supabase query + render pair", #5 "Renderers — `renderHub()`")
    - .planning/phases/04-hub-block-and-status-renderer/04-CONTEXT.md (D-02 hub hero copy; D-12 storyline source; D-13 tier grouping 3+3+1; D-14 tile composition; D-16 schema/PostgREST path; D-17 RLS posture — no JS-side status filter)
    - .planning/phases/01-render-stack-diagnostic/01-FINDINGS.md §3 (supabase-js .schema() locks Accept-Profile: economy_map)
  </read_first>
  <action>
    Replace the stub `async function loadHub() { showView('map'); /* renderer in Wave 2 plan 02 */ }` (shipped by plan 04-01 before the `function route()` declaration) with a real implementation, AND add a new sync `function renderHub(data)` function immediately after it. Match the existing four-step loader idiom from loadList() at lines 135-152 (PATTERNS §"Shared Patterns" — `async function loadXxx() { showView(...); var { data, error } = await sb...; if (error || !data) return; render(data); }`).

    loadHub() shape (verbatim spirit, adjust identifiers):
    - First line: `showView('map');`
    - Query: `var { data, error } = await sb.schema('economy_map').from('blocks').select('slug,title,subtitle,accent,tier,sort_order,maturity,live_tension,current_body_version_id,last_synthesized_at').order('sort_order', { ascending: true });` — single query, full column list (we read all seven blocks anyway; RLS does not exclude any block row). Per D-16 use `sb.schema('economy_map')`; per D-17 do NOT add `.eq('status', 'published')` or any defensive filter — RLS is the boundary.
    - Error guard mirrors loadList() lines 143-148: `if (error || !data || data.length === 0) { document.getElementById('map-view').querySelector('.content-area').innerHTML = '<p style="color:var(--text-secondary);font-size:15px;padding:20px 24px;">Map data unavailable.</p>'; updateHero(HUB_STORYLINE, ''); return; }`. Log via `console.error('loadHub error:', error);` (matches the existing pattern at line 228 in subscribe handler).
    - Stash: `window.currentBlocks = data;` (matches the `window.currentNewsletter` / `window.currentNewsletterList` pattern at lines 70-77 and 150).
    - Call `renderHub(data);`.

    renderHub(data) shape — string-concat HTML via `data.map(function(b){ ... }).join('')` joined inside section wrappers. Single-quoted strings + `+` concatenation, NO template literals (PATTERNS §"docker/web/site/app.js" Pattern Assignment #5: "Do NOT introduce template literals — the file uses single-quoted strings + `+` concatenation throughout"). The renderer:

    1. Compute hero. Use the latest `last_synthesized_at` across all blocks as the "updated" timestamp (D-02 hub hero: `'updated ' + last-touched timestamp` or omit if all blocks have null `last_synthesized_at`). Pseudo-code: `var latest = data.map(function(b){return b.last_synthesized_at;}).filter(Boolean).sort().pop();` (string-sort ISO timestamps works). `var dateText = latest ? 'updated ' + formatDate(latest) : '';`. Call `updateHero(HUB_STORYLINE, dateText);`.

    2. Group by tier. Build three arrays: `var substrateBlocks = data.filter(function(b){return b.tier === 'substrate';});`, similarly for `behavior` and `frame`. The query is already ordered by `sort_order` ascending, so each filtered array preserves the seed order from Phase 2 D-23 (substrate sort_order 1-3, behavior 4-6, frame 7).

    3. Emit a helper `function renderTile(b)` that produces a single tile string per D-14:
       ```
       '<a href="#/map/' + encodeURIComponent(b.slug) + '" data-accent="' + escapeHtml(b.accent) + '" class="block-tile">' +
           '<h3 class="tile-title">' + escapeHtml(b.title) + '</h3>' +
           '<p class="tile-subtitle">' + escapeHtml(b.subtitle) + '</p>' +
           renderMaturityPill(b) +
       '</a>'
       ```
       Notes: `encodeURIComponent(b.slug)` defends against any future slug containing path-unsafe characters (the seeded slugs are all lowercase-hyphenated and safe today; this is defense in depth, not a behavior change). Every DB string passes through `escapeHtml()` (PATTERNS §"Always escape DB strings"). The `<a>` IS the click target; do NOT nest a button inside.

    4. Emit a helper `function renderMaturityPill(b)` that returns the canonical pill markup from tokens-preview.html lines 78-82:
       ```
       var stage = MATURITY_STAGE[b.maturity] || 1;
       return '<div class="maturity-pill" data-accent="' + escapeHtml(b.accent) + '" data-stage="' + stage + '" aria-label="Maturity: ' + escapeHtml(b.maturity) + ' (' + stage + ' of 5)">' +
              '<span class="seg"></span><span class="seg"></span><span class="seg"></span><span class="seg"></span><span class="seg"></span>' +
              '</div>';
       ```
       The pill ALWAYS emits exactly 5 seg children regardless of stage (the CSS keys fill off data-stage — style-map.css lines 71-75). The `|| 1` fallback handles an unexpected enum value gracefully (renders as nascent rather than crashing). `data-accent` on the pill itself ensures the cascade resolves even if the pill is hoisted outside a `[data-accent]` ancestor (defensive — tokens-preview.html sets it on the pill for safety).

    5. Wrap each tier in a `<section class="tier-section">` containing a `<h2 class="tier-label">` heading followed by the joined tile markup. Skip rendering a section if its filtered array is empty (defense — should never happen with the seed data, but avoids dangling section headings).

    6. Final write: combine the storyline preface + three sections, write to the #map-view's `.content-area` container:
       ```
       var html =
           '<div class="hub-storyline">' + escapeHtml(HUB_STORYLINE) + '</div>' +
           '<section class="tier-section">' +
               '<h2 class="tier-label">' + TIER_LABELS.substrate + '</h2>' +
               substrateBlocks.map(renderTile).join('') +
           '</section>' +
           '<section class="tier-section">' +
               '<h2 class="tier-label">' + TIER_LABELS.behavior + '</h2>' +
               behaviorBlocks.map(renderTile).join('') +
           '</section>' +
           '<section class="tier-section">' +
               '<h2 class="tier-label">' + TIER_LABELS.frame + '</h2>' +
               frameBlocks.map(renderTile).join('') +
           '</section>';
       document.getElementById('map-view').querySelector('.content-area').innerHTML = html;
       window.scrollTo(0, 0);
       ```

    Notes:
    - The `<div class="hub-storyline">` wrapper is a Phase-4-owned class but does NOT need its own selector — it inherits `.content-area` typography and pads through the section margins. If the operator decides it needs styling in a later iteration, that lands as a CSS-only follow-up.
    - HUB_STORYLINE is a hardcoded module constant from plan 04-01; the operator edits the string via PR. Do NOT introduce a DB query for it (D-12 explicitly defers `/map-storyline` to v2).
    - Do NOT call setMode() inside loadHub() — body mode is preserved from prior nav/localStorage. The mode-toggle visibility is already handled by showView('map') (plan 04-01's extension).
    - Do NOT touch `setMode()` re-render hooks at lines 70-77; the hub does not depend on technical/strategic mode in v1 (per D-03 — no per-mode body variant for blocks).

    Keep loadHub() and renderHub() co-located in the existing function order (placed where the stub currently lives — right before `function route()`). Do not reorganize the file.
  </action>
  <verify>
    <automated>set -e; F=docker/web/site/app.js; grep -q "async function loadHub" "$F"; grep -q "function renderHub" "$F"; grep -q "sb.schema('economy_map').from('blocks')" "$F"; grep -q "TIER_LABELS.substrate" "$F"; grep -q "TIER_LABELS.behavior" "$F"; grep -q "TIER_LABELS.frame" "$F"; grep -q "MATURITY_STAGE" "$F"; grep -q 'class="block-tile"' "$F"; grep -q 'class="maturity-pill"' "$F"; grep -cE 'span class="seg"' "$F" | awk '$1 &gt;= 5 {print "OK seg count"; exit 0} {print "FAIL: expected ≥5 seg spans in renderMaturityPill, got " $1; exit 1}'; grep -q "escapeHtml(b.title)" "$F"; grep -q "escapeHtml(b.subtitle)" "$F"; ! grep -q '`' "$F" || { echo "FAIL: template literal detected — file uses single-quote + concat"; exit 1; }; node -e "new Function(require('fs').readFileSync('$F','utf8').replace(/window\.supabase[^;]*;?/g,'').replace(/__SUPABASE_URL__/g,'x').replace(/__SUPABASE_ANON_KEY__/g,'x'))"; echo OK</automated>
  </verify>
  <acceptance_criteria>
    - Source: `async function loadHub()` body contains `showView('map');` and a `sb.schema('economy_map').from('blocks').select(...).order('sort_order', { ascending: true })` query (regex: `sb\.schema\(['"]economy_map['"]\)\.from\(['"]blocks['"]\)`).
    - Source: `loadHub()` selects (at minimum) the columns `slug, title, subtitle, accent, tier, sort_order, maturity` — verified via `grep "\.select(" docker/web/site/app.js | grep loadHub -A 1` or by reading the function body.
    - Source: NO defensive `.eq('status', 'published')` or `.neq('block_slug', 'unsorted')` filter inside loadHub() — RLS is the boundary (D-17).
    - Source: `function renderHub(data)` exists and emits three `<section class="tier-section">` blocks with `<h2 class="tier-label">` headings sourced from TIER_LABELS constants.
    - Source: every DB string (`b.title`, `b.subtitle`, `b.accent`, `b.maturity`) passes through `escapeHtml(...)` before innerHTML — verifiable via `grep -E "escapeHtml\(b\.(title|subtitle|accent|maturity)\)" docker/web/site/app.js` returning at least one match per field.
    - Source: `renderMaturityPill(...)` (or its inline equivalent) emits exactly 5 `<span class="seg"></span>` children per pill (grep count check above).
    - Source: `data-stage` value comes from `MATURITY_STAGE[b.maturity]` with a fallback (`|| 1` or equivalent guard).
    - Source: `updateHero(HUB_STORYLINE, ...)` is called inside loadHub() on the success path (D-02).
    - Source: file has zero backtick characters (no template literals introduced — PATTERNS idiom guardrail).
    - Source: render target is `document.getElementById('map-view').querySelector('.content-area')` (the container created by plan 04-01 Task 1).
    - Behavior (post-deploy, manual): Visit `https://aiagentspulse.com/#/map`. Hero shows the storyline text. Three tier headings (SUBSTRATE / BEHAVIOR / FRAME) are visible. Seven tiles render in correct order: identity-trust → memory-context → payments-settlement → autonomy-control → governance-accountability → psychology-disposition → regulation-legal. Each tile has the correct accent stripe (teal/purple/coral/gray). DevTools Network tab shows exactly one request to `/rest/v1/blocks?select=...&order=sort_order.asc.nullslast` with `Accept-Profile: economy_map` header set. DevTools Console shows zero errors. (This behavior assertion is for Plan 06's end-to-end verification, but the source assertions above are sufficient to mark Plan 02 complete.)
  </acceptance_criteria>
  <done>
    The hub renderer is wired: loadHub() queries `economy_map.blocks` once, renderHub() emits three tier sections with a hardcoded storyline preface and seven anchor-style block tiles each carrying title + subtitle + 5-segment maturity pill. All DB strings escaped; no defensive RLS-redundant filters; no template literals; supabase-js .schema('economy_map') sets Accept-Profile automatically.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser ↔ Supabase PostgREST | Anon-key reads `economy_map.blocks` via supabase-js .schema(). RLS filters server-side (Phase 2 D-05/D-06/D-07) — only public, non-secret block metadata is exposed. |
| Supabase response ↔ DOM | `blocks.title`, `blocks.subtitle`, `blocks.accent`, `blocks.maturity` strings flow into innerHTML. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-02-01 | Tampering (XSS) | block.title, block.subtitle, block.accent, block.maturity rendered to innerHTML | mitigate | All four fields pass through `escapeHtml()` before concatenation into the HTML string (PATTERNS §"Always escape DB strings"). The upstream synthesis prompt is the source of these strings; Phase 7 is the upstream sanitizer for body_md — for `title`/`subtitle`/`accent`, the Phase 2 seed values are operator-authored and the Phase 10 `/map-tension` command updates `live_tension` only (not these fields). escapeHtml() is the defensive layer regardless. |
| T-04-02-02 | Tampering | block.slug rendered into `href="#/map/{slug}"` | mitigate | `encodeURIComponent(b.slug)` defends against any slug containing path-unsafe characters. Today's seeded slugs (identity-trust, memory-context, etc.) are all lowercase-hyphenated; this is defense in depth. |
| T-04-02-03 | Information Disclosure | hub exposes the full blocks row set | accept | RLS posture (Phase 2 D-05) explicitly permits anon reads of `blocks`; the seven blocks are public editorial surface. `block_body_versions` and `timeline_entries` have their own RLS (status='published' / block_slug != 'unsorted') — this plan does not query those tables. |
| T-04-02-04 | Denial of Service | hub query returns thousands of blocks | accept | The schema has a hard cap of 7 blocks (Phase 2 seed; no INSERT path from this phase). Even adversarial seeding via direct DB access would require service_role bypass — out of this phase's threat surface. |
</threat_model>

<verification>
After this plan deploys (via plan 04-06):
- Visit `#/map`. Hero shows HUB_STORYLINE; "updated <date>" appears IF any block has `last_synthesized_at` non-null (in v1 with no synthesis run, this will be omitted — that is correct).
- Seven block tiles render in three tier sections (3 SUBSTRATE / 3 BEHAVIOR / 1 FRAME). Each tile shows title, subtitle, and a maturity pill with the correct number of filled segments.
- All seven blocks have `maturity = 'nascent'` after Phase 2 seeding, so all pills show 1/5 filled segments (the leftmost segment in tier accent color, the other four outlined only).
- Clicking any tile navigates to `#/map/<slug>` — at this point the block view shows the `← Map` back link only (plan 04-03 ships the block renderer); navigating back via the link returns to the hub.
- DevTools Network: exactly one GET to `/rest/v1/blocks?select=...&order=sort_order.asc...`. The request headers include `Accept-Profile: economy_map` (supabase-js .schema() emits this automatically — verifiable in Phase 1 FINDINGS §3 confirmation).
</verification>

<success_criteria>
- loadHub() and renderHub() exist in app.js, replacing the no-op stub from plan 04-01.
- RNDR-01 satisfied: hub URL renders storyline header + seven-block visual + per-block maturity pill linking to block pages.
- RNDR-04 (hub half) satisfied: hub reads `blocks.maturity` from `economy_map.blocks`; status page (plan 04-04) reads from the same source.
- No template literals; no defensive `status='published'` filters; no setMode() calls inside loadHub().
- Mode toggle stays hidden on `#/map` (inherited from plan 04-01's showView extension).
</success_criteria>

<output>
After completing the task, create `.planning/phases/04-hub-block-and-status-renderer/04-02-SUMMARY.md` summarizing:
- The final HUB_STORYLINE text (if revised from plan 04-01's draft)
- The exact column list passed to .select() (so plan 04-04 status can mirror or trim it)
- Any DOM container assumption that plan 04-01 did not provide (should be zero — the contract held)
- The git commit hash
</output>
