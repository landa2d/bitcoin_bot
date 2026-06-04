---
phase: 04-hub-block-and-status-renderer
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docker/web/site/index.html
  - docker/web/site/style-map.css
  - docker/web/site/app.js
autonomous: true
requirements:
  - RNDR-01
  - RNDR-02
  - RNDR-03
tags:
  - frontend
  - spa
  - router
  - design-tokens
must_haves:
  truths:
    - "Visiting #/map, #/map/<slug>, or #/status flips visibility to the new view container (#map-view / #block-view / #status-view) — per D-01"
    - "The technical/strategic mode toggle is hidden on map routes and visible on list/reader routes — per D-03"
    - "Nav-left cluster shows a quiet `Map` text link between AGENTPULSE and the right-side SUBSCRIBE button — per D-04"
    - "The existing `.hero` block stays on all routes; updateHero() emits per-route headlines (HUB_STORYLINE on #/map, block.title on #/map/<slug>, 'Maturity Snapshot' on #/status) — per D-02"
    - "`MATURITY_STAGE`, `TIER_LABELS`, `HUB_STORYLINE`, `STATUS_PAGE_HEADER`, `LIVE_TENSION_PLACEHOLDER` are declared at module top in app.js — Wave 2 renderers can consume them"
    - "style-map.css contains layout selectors `.block-tile`, `.tier-label`, `.block-header`, `.block-tension`, `.block-body`, `.evolution`, `.timeline-show-all`, `.status-row`, and `.nav-map-link` that resolve `--accent-tier` via the cascade — Wave 2 renderers emit matching markup"
  artifacts:
    - path: docker/web/site/index.html
      provides: "Three new sibling view containers under <main> + Map nav link"
      contains: 'id="map-view"'
    - path: docker/web/site/style-map.css
      provides: "Layout selectors extending the Phase 3 token surface"
      contains: ".block-tile"
    - path: docker/web/site/app.js
      provides: "Router + showView + updateHero + module constants for map surface"
      contains: "case 'block':"
  key_links:
    - from: "app.js getRoute()"
      to: "the three new hash branches (#/map, #/map/<slug>, #/status)"
      via: "startsWith() — longer prefix #/map/ before #/map"
      pattern: "hash\\.startsWith\\(['\"]#/map/['\"]\\)"
    - from: "app.js showView()"
      to: "the new view containers + mode-toggle visibility"
      via: "style.display ternary on every enumerated view"
      pattern: "document\\.getElementById\\(['\"]map-view['\"]\\)\\.style\\.display"
    - from: ".block-tile, .status-row, .block-header"
      to: "--accent-tier"
      via: "the existing body.technical/body.strategic [data-accent=...] cascade in style-map.css lines 33-43"
      pattern: "var\\(--accent-tier\\)"
---

<objective>
Wire the SPA shell, design-token layout surface, and shared JS plumbing that the three map renderers (Wave 2 plans 02/03/04) will consume. After this plan, visiting #/map / #/map/<slug> / #/status flips the correct view container into visibility, the mode toggle disappears, the nav shows a Map link, and the existing hero re-uses updateHero() for per-route headlines — but the new view containers are still empty because the renderers ship in Wave 2.

Purpose: Land all cross-cutting infrastructure in a single atomic plan so that Wave 2 renderers (hub / block / status) can run in parallel without touching the same code regions. This plan is the contract Wave 2 consumes.

Output:
- docker/web/site/index.html — 3 new view containers + nav Map link
- docker/web/site/style-map.css — 9 new layout selector groups (extending the Phase 3 token surface)
- docker/web/site/app.js — module constants, router branches, showView extension, route() switch cases (loader functions stubbed to no-op so Wave 2 can plug them in)
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/04-hub-block-and-status-renderer/04-CONTEXT.md
@.planning/phases/04-hub-block-and-status-renderer/04-PATTERNS.md
@docker/web/site/index.html
@docker/web/site/style-map.css
@docker/web/site/app.js
</context>

<tasks>

<task type="auto">
  <name>Task 1: Extend index.html — add three view containers and nav Map link</name>
  <files>docker/web/site/index.html</files>
  <read_first>
    - docker/web/site/index.html (the file being modified — see current `<main>` block at lines 33-46 and `.nav-left` cluster at lines 13-17)
    - .planning/phases/04-hub-block-and-status-renderer/04-PATTERNS.md (§ "docker/web/site/index.html" — Pattern Assignment #1 "New view containers under `<main>`" + #2 "Map text link in the nav-left cluster")
    - .planning/phases/04-hub-block-and-status-renderer/04-CONTEXT.md (D-04 nav Map link styling; discretion item on "back to map" affordance inside block-view)
  </read_first>
  <action>
    Inside `<main>` (after the existing `#reader-view` div, before `</main>`), insert three sibling view containers in this order: `<div id="map-view" style="display:none"><div class="content-area"></div></div>`, `<div id="block-view" style="display:none"><div class="content-area"><a href="#/map" class="back-link">&larr; Map</a><div id="block-content"></div></div></div>`, `<div id="status-view" style="display:none"><div class="content-area" id="status-content"></div></div>`. Each wraps a `.content-area` div so the style-shared.css `.content-area` border-top/padding rule applies (matches `#list-view` line 36 and `#reader-view` line 41). The block-view's content-area includes a `← Map` back-link before `#block-content` (per CONTEXT discretion item — mirrors the `← All editions` link at index.html line 42).

    Inside `.nav-left` (lines 14-17), append `<a href="#/map" class="nav-map-link">Map</a>` as the third child after `<span class="nav-logo">AGENTPULSE</span>` and before the closing `</div>` (per D-04 — quiet text link, plain anchor, NOT a primary button, no onclick handler — the existing hashchange listener at app.js line 314 routes it).

    Do NOT change the existing nav structure, hero block, subscribe section, footer, or script tags. Do NOT add inline styling beyond `style="display:none"` (the rest comes from style-map.css selectors added in Task 2).
  </action>
  <verify>
    <automated>grep -c 'id="map-view"' docker/web/site/index.html | grep -q '^1$' &amp;&amp; grep -c 'id="block-view"' docker/web/site/index.html | grep -q '^1$' &amp;&amp; grep -c 'id="status-view"' docker/web/site/index.html | grep -q '^1$' &amp;&amp; grep -c 'class="nav-map-link"' docker/web/site/index.html | grep -q '^1$' &amp;&amp; grep -c 'id="block-content"' docker/web/site/index.html | grep -q '^1$' &amp;&amp; echo OK</automated>
  </verify>
  <acceptance_criteria>
    - Source: `docker/web/site/index.html` contains exactly one occurrence each of `id="map-view"`, `id="block-view"`, `id="status-view"`, `class="nav-map-link"`, `id="block-content"`.
    - Source: every new view container has `style="display:none"` on its outer div (so the renderer flip is the only way to make them visible — matches reader-view pattern at line 40).
    - Source: each new view container's first child is `<div class="content-area">` (so the inherited border-top + padding rule applies).
    - Source: the `← Map` back-link inside block-view uses the `back-link` class (matches index.html line 42's `← All editions` precedent).
    - Source: the `Map` nav link uses `class="nav-map-link"` (NOT `btn-subscribe-primary`, NOT any active-state class — per D-04).
    - Behavior: `python3 -c "import html.parser, pathlib; p=html.parser.HTMLParser(); p.feed(pathlib.Path('docker/web/site/index.html').read_text())"` exits 0 (parses cleanly).
  </acceptance_criteria>
  <done>
    index.html has three new sibling view containers under `<main>` (map-view, block-view, status-view), each pre-hidden via style.display:none and wrapping a .content-area div; the block-view contains a `← Map` back-link and a `#block-content` injection target. The `.nav-left` cluster gains a single quiet `<a href="#/map" class="nav-map-link">Map</a>` after the AGENTPULSE logo span. Existing structure (hero, subscribe section, footer, script tags) is untouched.
  </done>
</task>

<task type="auto">
  <name>Task 2: Extend style-map.css — add 9 layout selector groups + nav-map-link</name>
  <files>docker/web/site/style-map.css</files>
  <read_first>
    - docker/web/site/style-map.css (the file being modified — full read; current 148 lines define the Phase 3 token surface and the cascade body.technical/body.strategic × [data-accent] → --accent-tier at lines 33-43)
    - docker/web/site/style-shared.css (the cross-file analog — read `.content-area` rule lines 197-201, `.article-entry`/`.section-label`/`.entry-title`/`.entry-preview` lines 209-239, `.back-link` lines, `.hero-headline` Georgia 29px at line ~141)
    - docker/web/site/tokens-preview.html (canonical pill markup lines 78-82 and timeline-entry markup lines 114-137 — Phase 4 markup must match)
    - .planning/phases/04-hub-block-and-status-renderer/04-PATTERNS.md (§ "docker/web/site/style-map.css" — Pattern Assignments #1 "Markup-contract comment style", #2 "Tier-accent left-border stripe", #3 "Cross-file layout precedent", #4 "File-organization decision")
    - .planning/phases/04-hub-block-and-status-renderer/04-CONTEXT.md (D-04 nav-map-link styling; D-09 block-header markup; D-10 tension/body sections; D-11 timeline-show-all; D-13 tier-label; D-14 block-tile left-border stripe; D-15 status-row; D-19 file-organization)
  </read_first>
  <action>
    Append nine new selector groups to the END of `docker/web/site/style-map.css` (after the existing `.timeline-entry:not([data-source]) .timeline-source { display: none; }` rule at line 148). File-organization per D-19 + PATTERNS §4 — extend in place, do not create style-hub.css. Total file should land under ~300 lines.

    For each group below, open with `/* ── Name ──────────────── */` divider and a `/* Markup contract: ... */` block comment showing the exact HTML the renderer emits (matches the in-file precedent at lines 45-53 for `.maturity-pill`). Reference the gating decision in the comment.

    1. `.nav-map-link` — quiet nav link styling per D-04: `font-family: 'Courier New', monospace; font-size: 13px; color: var(--text-secondary); text-decoration: none; margin-left: 16px;` + a `:hover { color: var(--text-primary); }` rule. No active-state styling (deferred to v2 per Deferred Ideas).

    2. `.tier-label` (D-13) — uppercase tier heading; mirror style-shared.css `.section-label` shape: `font-family: 'Courier New', monospace; font-size: 13px; letter-spacing: 1.5px; text-transform: uppercase; color: var(--text-secondary); margin: 32px 0 16px 0;`. First-of-type margin-top reduced (e.g., `:first-of-type { margin-top: 8px; }`).

    3. `.block-tile` (D-14) — anchor-as-card with left-border accent stripe; key rules: `display: block; padding: 16px 20px 16px 24px; margin-bottom: 12px; border-left: 3px solid var(--accent-tier); text-decoration: none; color: inherit;` plus a `:hover { background: rgba(255,255,255,0.02); }` (technical) — but use the existing token surface; the `--accent-tier` cascade resolves via the `data-accent` attribute on the tile (PATTERNS §2). Tile children: `.tile-title` (Georgia 18px, matching `.entry-title` from style-shared.css lines 219-227), `.tile-subtitle` (Courier 15px var(--text-body), matching `.entry-preview` lines 232-238), `.maturity-pill` re-positioned (e.g., `margin-top: 8px; display: inline-flex;` — the pill component itself already styled by the existing rules at lines 55-75). Whole `<a>` is the link target; do NOT add link underline.

    4. `.block-header` (D-09) — flex row for `<h1>` + `.maturity-pill`: `display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin-bottom: 24px;`. The `<h1>` inside inherits the existing site H1 treatment from style-shared.css (Georgia 29px family, no new typography per TOKN-04) — pin only `margin: 0;` to avoid collapsing margins. Do NOT add a border, background, or accent decoration to the header itself — the `data-accent` on the header drives the `--accent-tier` for the pill child via the cascade.

    5. `.block-tension` (D-10) — editorial hook section: `padding: 16px 20px; margin-bottom: 32px; border-left: 3px solid var(--accent-tier); font-family: Georgia, serif; font-size: 17px; line-height: 1.6; color: var(--text-primary); font-style: italic;` (the `var(--accent-tier)` is resolved via the ancestor block-view's data-accent attribute — Wave 2 plan 03 emits the markup).

    6. `.block-body` (D-10) — synthesized prose container: `margin-bottom: 48px; line-height: 1.7;`. Inherits body Courier from style-shared.css. Inside the body, `h2` headings (from `marked.parse(body_md)`) get `font-family: Georgia, serif; font-size: 21px; margin: 32px 0 12px;`. Inside `p`, just `margin-bottom: 14px;`. Do not invent bespoke typography (TOKN-04 still in force) — these rules just scope the existing site defaults to the new container.

    7. `.evolution` (D-08, D-11) — timeline section wrapper: `margin-top: 32px;`. Add a `.evolution > h2` rule (the section title, e.g., "Evolution") matching `.tier-label` styling (Courier 13px uppercase letter-spaced var(--text-secondary)). The `.timeline-entry` children already styled by lines 96-141 — no override needed. Include an `#evolution-entries` id-target style if needed (none required; entries flow naturally).

    8. `.timeline-show-all` (D-11) — expand button: `display: block; margin: 16px 0 0 0; padding: 8px 16px; background: transparent; border: 1px solid var(--border); border-radius: 4px; font-family: 'Courier New', monospace; font-size: 13px; color: var(--accent-tier, var(--text-secondary)); cursor: pointer;` + `:hover { background: rgba(255,255,255,0.02); }`. Re-uses --accent-tier from the block-view ancestor.

    9. `.status-row` (D-15) — one-line status block: `display: flex; align-items: center; gap: 16px; padding: 12px 20px 12px 24px; margin-bottom: 8px; border-left: 3px solid var(--accent-tier);`. Children: `.status-title` (Georgia 17px), `.status-subtitle` (Courier 14px var(--text-body), `flex: 1;` to take remaining width), `.status-synth` (Courier 13px var(--text-secondary), `flex-shrink: 0;`). The `.maturity-pill` inside the row keeps its existing styling — no width override.

    Every rule that wants tier accent uses `var(--accent-tier)` — NEVER reference `var(--accent-teal-base)` or any other raw token directly (PATTERNS §2: the body.technical/body.strategic × [data-accent] cascade does the resolution). When the rule applies to an element that itself carries `data-accent` (e.g., `.block-tile[data-accent="teal"]`), the cascade still works because the body class is the outer rule.

    Do NOT modify lines 1-148 (the Phase 3 token surface). Do NOT introduce new font families, new font sizes outside the existing palette, or any per-tier hex values (TOKN-04 + PATTERNS §3 — bespoke typography is v2).
  </action>
  <verify>
    <automated>set -e; F=docker/web/site/style-map.css; grep -q "\.nav-map-link" "$F"; grep -q "\.tier-label" "$F"; grep -q "\.block-tile" "$F"; grep -q "\.block-header" "$F"; grep -q "\.block-tension" "$F"; grep -q "\.block-body" "$F"; grep -q "\.evolution" "$F"; grep -q "\.timeline-show-all" "$F"; grep -q "\.status-row" "$F"; grep -c "var(--accent-tier" "$F" | awk '$1 &gt;= 6 {print "OK"; exit 0} {print "FAIL: only " $1 " --accent-tier references"; exit 1}'; LINES=$(wc -l &lt; "$F"); [ "$LINES" -lt 350 ] || { echo "FAIL: $LINES lines exceeds soft 350 cap"; exit 1; }; ! grep -E "#[0-9A-Fa-f]{6}" "$F" | grep -v -E "(--accent-(teal|purple|coral|gray)-(base|on-dark))" | head -1 | grep -q "#" || echo "WARN: new raw hex codes detected (review)"; echo OK</automated>
  </verify>
  <acceptance_criteria>
    - Source: all nine selectors present — `.nav-map-link`, `.tier-label`, `.block-tile`, `.block-header`, `.block-tension`, `.block-body`, `.evolution`, `.timeline-show-all`, `.status-row` — each exactly once in style-map.css.
    - Source: at least 6 occurrences of `var(--accent-tier` across the new selectors (block-tile + block-tension + status-row left-borders + tension color + show-all color + at minimum one more) — proves the cascade is honored.
    - Source: NO new raw `#[0-9A-Fa-f]{6}` hex values introduced outside the existing `--accent-*-base`/`--accent-*-on-dark` definitions at lines 18-31 (bespoke typography / new colors are out of scope per TOKN-04).
    - Source: each new selector group has a `/* ── Name ── */` divider and a `/* Markup contract: ... */` comment (matches in-file precedent at lines 45-53).
    - Source: lines 1-148 (the Phase 3 token surface) are unchanged — verifiable by `git diff docker/web/site/style-map.css | grep '^-' | head` showing zero deletions.
    - Source: file total ≤ ~300 lines (D-19 / PATTERNS §4 — extend in place, do not split).
    - Behavior: `npx --yes csstree-validator docker/web/site/style-map.css` (or `python3 -c "import re; open('docker/web/site/style-map.css').read()"`) exits 0 (no syntax errors). If csstree-validator is not installed, fall back to manual `tinycss2` parse via `python3 -c "import tinycss2, pathlib; tinycss2.parse_stylesheet(pathlib.Path('docker/web/site/style-map.css').read_text())"` — exit 0 means parseable.
  </acceptance_criteria>
  <done>
    style-map.css extended with nine new layout selector groups appended after line 148, each with a divider + markup-contract comment, all consuming `var(--accent-tier)` via the existing Phase 3 cascade. No raw new hex codes, no new font families, no modifications to the Phase 3 token surface. File parses cleanly; line count stays under ~300.
  </done>
</task>

<task type="auto">
  <name>Task 3: Extend app.js — module constants, router branches, showView, route() switch (no renderers yet)</name>
  <files>docker/web/site/app.js</files>
  <read_first>
    - docker/web/site/app.js (the file being modified — full read; pay attention to MODES object at lines 11-26, updateHero() lines 82-85, getRoute() lines 89-98, showView() lines 100-104, route() lines 299-307, hashchange listener line 314)
    - .planning/phases/04-hub-block-and-status-renderer/04-PATTERNS.md (§ "docker/web/site/app.js" — Pattern Assignments #1 "Module-level constant declarations", #2 "Router branch extension", #3 "View visibility toggle", #6 "Hero update")
    - .planning/phases/04-hub-block-and-status-renderer/04-CONTEXT.md (D-01 hash routes; D-02 per-route hero headlines; D-03 mode-toggle hidden on map routes; D-12 HUB_STORYLINE; specifics §"Editorial copy that lives in `app.js`" — STATUS_PAGE_HEADER, tier labels; specifics §"Phase 4 maturity-stage mapping")
  </read_first>
  <action>
    Three edits to docker/web/site/app.js. ALL new code follows the existing idiom: `var` not `let/const` (except for top-level constants like the existing MODES `const`); single-quoted strings; `+` concatenation not template literals; no destructuring at the router level; no `async/await` at the router or showView level (loaders are async; visibility/routing is sync).

    Edit A — Module-level constants (after the existing MODES const at line 26, before `function getInitialMode()` at line 29). Add five `const` declarations matching the MODES idiom:
    - `const HUB_STORYLINE = '...';` with comment `// Editorial: edit this string + PR + redeploy to update (D-12)`. Draft text per CONTEXT discretion: keep under 200 chars, tone matches PROJECT.md ("Synthesis with editorial integrity. Eight blocks, seven shipped, one deferred — the agent economy as a living map."). Wave 2 plan 02 may revise the string; this plan supplies an initial value.
    - `const STATUS_PAGE_HEADER = 'Maturity Snapshot';` (specifics §"Editorial copy").
    - `const MATURITY_STAGE = { nascent: 1, emerging: 2, contested: 3, consolidating: 4, mature: 5 };` (specifics §"Phase 4 maturity-stage mapping").
    - `const TIER_LABELS = { substrate: 'SUBSTRATE', behavior: 'BEHAVIOR', frame: 'FRAME' };` (D-13).
    - `const LIVE_TENSION_PLACEHOLDER = 'TBD — set via /map-tension';` (specifics §"Live-tension placeholder string" — use `—` em-dash to match the Phase 2 D-21 seed exactly; document the exact-string-match contract in a comment).

    Edit B — Router branches in `getRoute()` (lines 89-98). Insert two new branches BEFORE the existing `#/edition/` and `#/unsubscribe` branches, BUT the `#/map/<slug>` branch MUST come BEFORE the `#/map` branch (PATTERNS §2 ordering note — `startsWith('#/map')` would otherwise swallow `#/map/<slug>`). New shape:
      - `if (hash.startsWith('#/map/')) { return { view: 'block', slug: hash.split('/')[2] }; }`
      - `if (hash.startsWith('#/map')) { return { view: 'map' }; }`
      - `if (hash.startsWith('#/status')) { return { view: 'status' }; }`
    Place these after the function open-brace and before the existing `#/edition/` branch at line 91 (so order is: block, map, status, edition, unsubscribe, default-list). Match the existing return-object idiom — plain object literal, no class instances.

    Edit C — Switch cases in `route()` (lines 299-307). Add three cases BEFORE the existing `default` or after `case 'unsubscribe'`:
      - `case 'map': loadHub(); break;`
      - `case 'block': loadBlock(r.slug); break;`
      - `case 'status': loadStatus(); break;`
    Define stub no-op loaders RIGHT BEFORE the `function route()` declaration so route() resolves them without ReferenceError. Each stub: `async function loadHub() { showView('map'); /* renderer in Wave 2 plan 02 */ }`, `async function loadBlock(slug) { showView('block'); /* renderer in Wave 2 plan 03 */ }`, `async function loadStatus() { showView('status'); /* renderer in Wave 2 plan 04 */ }`. Stubs MUST call showView(...) so visibility works even before renderers ship.

    Edit D — Extend `showView()` (lines 100-104). Add three lines enumerating the new view containers using the same `style.display = viewName === '...' ? 'block' : 'none'` ternary:
      - `document.getElementById('map-view').style.display = viewName === 'map' ? 'block' : 'none';`
      - `document.getElementById('block-view').style.display = viewName === 'block' ? 'block' : 'none';`
      - `document.getElementById('status-view').style.display = viewName === 'status' ? 'block' : 'none';`
    AND fold in the mode-toggle visibility per D-03 + PATTERNS §3 discretion item — add inside showView():
      - `var isMapRoute = (viewName === 'map' || viewName === 'block' || viewName === 'status');`
      - `var toggle = document.querySelector('.mode-toggle'); if (toggle) toggle.style.display = isMapRoute ? 'none' : 'inline-flex';`
      - `var subtitle = document.getElementById('mode-subtitle'); if (subtitle) subtitle.style.display = isMapRoute ? 'none' : 'block';`
    Defensive null-checks (`if (toggle)`) handle the case where index.html structure varies; existing index.html guarantees both exist.

    Do NOT modify updateHero() (lines 82-85) — it works as-is for the new routes (PATTERNS §6). Wave 2 renderers call it with the per-route headlines from D-02. Do NOT add Realtime subscriptions, setInterval, or visibilitychange listeners — those land in Wave 3 plan 05. Do NOT modify setMode(), the subscribe/unsubscribe handlers, escapeHtml(), formatDate(), getModeTitle(), getModeContent(), or the DOMContentLoaded init block.

    Note: At this point #/map and #/status routes resolve to empty content-area divs (renderers in Wave 2 inject HTML). This is intentional — Wave 2 plans 02/03/04 inject the renderer bodies and connect to data.
  </action>
  <verify>
    <automated>set -e; F=docker/web/site/app.js; grep -q "const HUB_STORYLINE" "$F"; grep -q "const STATUS_PAGE_HEADER" "$F"; grep -q "const MATURITY_STAGE" "$F"; grep -q "const TIER_LABELS" "$F"; grep -q "const LIVE_TENSION_PLACEHOLDER" "$F"; grep -q "hash.startsWith('#/map/')" "$F"; grep -q "hash.startsWith('#/map')" "$F"; grep -q "hash.startsWith('#/status')" "$F"; grep -q "case 'map':" "$F"; grep -q "case 'block':" "$F"; grep -q "case 'status':" "$F"; grep -q "async function loadHub" "$F"; grep -q "async function loadBlock" "$F"; grep -q "async function loadStatus" "$F"; grep -q "getElementById('map-view')" "$F"; grep -q "getElementById('block-view')" "$F"; grep -q "getElementById('status-view')" "$F"; grep -q "querySelector('.mode-toggle')" "$F"; node -e "new Function(require('fs').readFileSync('$F','utf8').replace(/^.*window\.supabase.*\$/m,'').replace(/__SUPABASE_URL__/g,'x').replace(/__SUPABASE_ANON_KEY__/g,'x'))" 2&gt;&amp;1 | grep -v -E "^(\$|.*window is not)" || true; echo OK</automated>
  </verify>
  <acceptance_criteria>
    - Source: five new `const` declarations present — HUB_STORYLINE, STATUS_PAGE_HEADER, MATURITY_STAGE, TIER_LABELS, LIVE_TENSION_PLACEHOLDER — each exactly once.
    - Source: HUB_STORYLINE string is non-empty and ≤ 200 chars (regex check via `python3 -c "import re,pathlib; m=re.search(r\"const HUB_STORYLINE = '([^']{1,200})'\", pathlib.Path('docker/web/site/app.js').read_text()); assert m, 'HUB_STORYLINE missing or too long'"`).
    - Source: getRoute() contains all three new `startsWith` branches AND the `#/map/` branch appears BEFORE the `#/map` branch (verify via `awk '/startsWith.*#\/map\//{print NR; exit}' docker/web/site/app.js` and `awk '/startsWith.*#\/map.[^/]/{print NR; exit}' docker/web/site/app.js` and check the first line number is less than the second).
    - Source: route()'s switch contains `case 'map':`, `case 'block':`, `case 'status':` and each calls the corresponding stub loader.
    - Source: three stub async loaders (loadHub, loadBlock, loadStatus) exist; each calls showView(...) with the correct viewName.
    - Source: showView() now enumerates all five view containers (list, reader, map, block, status) AND toggles `.mode-toggle` + `#mode-subtitle` display based on whether the viewName is a map route.
    - Behavior: serve `docker/web/site/` via `python3 -m http.server 8080 --directory docker/web/site &` then `curl -sI http://localhost:8080/app.js` returns 200, and a quick `node --check docker/web/site/app.js` (after string-replacing the SUPABASE placeholders and stubbing `window`) exits 0 — no syntax errors. (The CI-friendly version of this is to just verify `node -e "new Function(text)"` parses without SyntaxError.)
    - Behavior: in a browser at #/map, the #map-view container becomes visible (display !== 'none') and #list-view, #reader-view, #block-view, #status-view are all hidden (display === 'none'). Mode-toggle is hidden. (Verifiable manually post-deploy in Wave 4; pre-deploy via a headless smoke test if desired.)
  </acceptance_criteria>
  <done>
    app.js has five new module constants (HUB_STORYLINE, STATUS_PAGE_HEADER, MATURITY_STAGE, TIER_LABELS, LIVE_TENSION_PLACEHOLDER); getRoute() resolves #/map/<slug>, #/map, #/status to the correct view objects with #/map/ checked before #/map; route() dispatches to three new async stub loaders that call showView() with the right viewName; showView() enumerates all five view containers and hides the mode toggle on map routes. No syntax errors. No renderer bodies yet — Wave 2 plans 02/03/04 plug those in.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser ↔ Supabase REST (anon key) | This plan introduces no new reads. Routing/shell only. |
| browser ↔ DOM | No new untrusted data flows into the DOM in this plan; renderers ship in Wave 2. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-01-01 | Tampering | hash route values via window.location.hash | mitigate | `r.slug = hash.split('/')[2]` is consumed only by Wave 2 plan 03's loadBlock(), which passes it through `escapeHtml()` and `.eq('slug', slug)` parameterized query; no string concatenation into SQL or innerHTML in this plan. |
| T-04-01-02 | Information Disclosure | nav Map link reveals new app surface | accept | Hub data is intentionally public via RLS (Phase 2 D-05/D-06); discoverability is a feature, not a leak. |
| T-04-01-03 | Denial of Service | tight hashchange loop (e.g., 1000 navigations/sec) re-fires route() | accept | No state is mutated by route() in this plan; the stub loaders call showView() (cheap DOM toggles). Worst case is layout thrash on the operator's own browser. Wave 3 plan 05 adds the idle poll which has its own DoS mitigation (visibility-pause + 60s cadence). |
</threat_model>

<verification>
After all three tasks complete, manually verify in a browser:
1. Visit `#/`. List view renders as today; mode toggle is visible; nav Map link is present and styled quietly.
2. Click the nav Map link. URL becomes `#/map`; `#map-view` becomes visible; `#list-view` is hidden; the existing hero block stays visible; mode toggle is hidden.
3. Visit `#/map/identity-trust` directly. `#block-view` becomes visible (containing the `← Map` back-link + empty `#block-content`); other view containers are hidden.
4. Visit `#/status`. `#status-view` becomes visible; mode toggle is hidden.
5. Visit `#/edition/1` (any existing edition). Reader view renders as today; mode toggle is visible.
6. DevTools console shows no errors on any navigation.
</verification>

<success_criteria>
- index.html, style-map.css, and app.js extended in place (no new files created).
- All three view containers + nav Map link + nine layout CSS selectors + five JS constants + three router branches + three switch cases + three stub loaders + extended showView() shipped.
- DOM containers are correctly hidden/shown by `showView()` for every viewName.
- Mode toggle is hidden on map routes and visible on list/reader routes (D-03).
- Phase 3 token surface (style-map.css lines 1-148) is unchanged.
- updateHero() is unmodified (its current behavior already satisfies D-02 — Wave 2 renderers invoke it with the new per-route headlines).
- File line counts: style-map.css ≤ ~300; app.js stays well under any 2000-line concern.
- No JS syntax errors (parseable by `node -e "new Function(text)"` after string-replacing the SUPABASE placeholders).
</success_criteria>

<output>
After completing all tasks, create `.planning/phases/04-hub-block-and-status-renderer/04-01-SUMMARY.md` summarizing:
- What was added to each of the three files (with line-count deltas)
- Which Wave 2 plans depend on which exported symbols (HUB_STORYLINE → plan 02; MATURITY_STAGE/TIER_LABELS → plans 02+03+04; LIVE_TENSION_PLACEHOLDER → plan 03; new CSS selectors → plans 02+03+04)
- Any deviations from the plan (e.g., if the HUB_STORYLINE draft was tweaked)
- The git commit hash
</output>
