---
phase: 04-hub-block-and-status-renderer
plan: 03
type: execute
wave: 3
depends_on:
  - 04-01
  - 04-02
files_modified:
  - docker/web/site/app.js
autonomous: true
requirements:
  - RNDR-02
  - RNDR-07
tags:
  - frontend
  - spa
  - renderer
  - block
  - timeline
must_haves:
  truths:
    - "Visiting #/map/<slug> fires three queries: blocks row (by slug), timeline_entries (eq block_slug, order event_date desc, limit 30), and conditionally block_body_versions (by current_body_version_id) — per D-08, D-16, D-17"
    - "Block-page composition order is Title → live tension → body_md → Evolution — per D-08"
    - "Maturity pill is inline in the title row, right-aligned, with 5 segments and data-stage from MATURITY_STAGE[block.maturity] — per D-09"
    - "Tension card is hidden when live_tension === LIVE_TENSION_PLACEHOLDER (the 'TBD — set via /map-tension' seed) — per D-10"
    - "Body section is hidden when current_body_version_id is null — per D-10"
    - "Evolution renders newest-first via .order('event_date', { ascending: false }) — RNDR-07"
    - "Evolution caps at 30 entries; a 'Show all (N) ↓' button appears only when initial result count === 30; clicking it re-queries unbounded and replaces the list (one-shot, no re-collapse) — per D-11"
    - "All timeline-entry strings (what_shifted, why_it_mattered, source_url) pass through escapeHtml(); body_md goes through marked.parse() — per D-18 and PATTERNS §'Always escape DB strings'"
    - "Timeline entries with null source_url omit the data-source attribute and the <a class='timeline-source'> element entirely — matches Phase 3 tokens-preview.html lines 127-137"
    - "Timeline-source anchors carry rel='noopener noreferrer' target='_blank' — threat model T-04-03-02"
    - "A module-level `var timelineExpanded` is set to false on each loadBlock() entry — Wave 3 plan 05 reads it to decide between limit(30) and unbounded during the idle poll"
  artifacts:
    - path: docker/web/site/app.js
      provides: "loadBlock(slug) + renderBlock() + renderTimelineEntries() + show-all expand handler"
      contains: "function renderBlock"
  key_links:
    - from: "loadBlock(slug)"
      to: "Promise.all over the three economy_map tables"
      via: "supabase-js .schema('economy_map').from(...)"
      pattern: "Promise\\.all"
    - from: "block.live_tension"
      to: "tension section render guard"
      via: "exact-string match against LIVE_TENSION_PLACEHOLDER"
      pattern: "LIVE_TENSION_PLACEHOLDER"
    - from: "timeline result count === 30"
      to: ".timeline-show-all button"
      via: "conditional emit"
      pattern: 'class="timeline-show-all"'
    - from: "body_md"
      to: ".block-body innerHTML"
      via: "marked.parse() — same precedent as renderArticle() line 169"
      pattern: "marked\\.parse"
---

<objective>
Replace the no-op `loadBlock(slug)` stub shipped in plan 04-01 with a full block-page renderer: query the blocks row, the published body version (if any), and the 30 newest timeline entries; emit the six-part-skeleton composition (Title → tension → body → Evolution) with empty-state hiding and the "Show all" expand button. After this plan deploys, every block page is operator-visible — even with no body and placeholder tension, the title + maturity pill + Evolution scaffold renders.

Purpose: Deliver RNDR-02 (six-part block page skeleton) and RNDR-07 (Evolution newest-first ordering). Also lays the show-all expand-state mechanism that Wave 3 plan 05 reads during the idle poll.

Output: docker/web/site/app.js — loadBlock(slug) performs the three queries, renderBlock() emits the wrapper composition, renderTimelineEntries(entries, expanded) emits the Evolution section (factored out so the idle poll in plan 05 can re-use it), and a click handler on `.timeline-show-all` swaps the limited list for an unbounded re-query.
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
@docker/web/site/style-map.css
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement loadBlock(slug) + renderBlock() inside app.js</name>
  <files>docker/web/site/app.js</files>
  <read_first>
    - docker/web/site/app.js (the file being modified — re-read fully; loadEdition() at lines 173-193 is the closest single-row loader analog; renderArticle() at lines 156-171 is the closest body-markdown renderer; escapeHtml() at lines 274-278; formatDate() at lines 280-285. Plan 04-01 will have added `async function loadBlock(slug) { showView('block'); }` as a stub — this task replaces the body.)
    - docker/web/site/style-map.css (the CSS contract — full read; pay attention to lines 78-148 timeline-entry markup contract; plan 04-01 will have appended `.block-header`, `.block-tension`, `.block-body`, `.evolution`, `.timeline-show-all` selectors)
    - docker/web/site/tokens-preview.html (canonical timeline-entry markup with source: lines 114-125; without source: lines 128-137; pill markup: lines 78-82)
    - .planning/phases/04-hub-block-and-status-renderer/04-PATTERNS.md (Pattern Assignment #4 "Supabase query + render pair" specific bullets for loadBlock; #5 renderBlock and timeline-entry markup; Shared Patterns "Markup matches tokens-preview.html exactly")
    - .planning/phases/04-hub-block-and-status-renderer/04-CONTEXT.md (D-02 block-page hero; D-08 composition order; D-09 maturity pill inline; D-10 empty-state hide; D-11 30-cap + show-all + expand-state; D-16 schema path; D-17 RLS posture; D-18 marked.parse)
    - .planning/phases/02-economy-map-schema-seven-block-seed/02-CONTEXT.md D-21 (live_tension placeholder string exact form: `'TBD — set via /map-tension'` — em-dash matters)
  </read_first>
  <action>
    Add a module-level state variable near the other top-level state vars (e.g., right after `var currentMode = getInitialMode();` at line 40): `var timelineExpanded = false;` with the comment `// D-11: whether Show all was clicked; reset on each loadBlock() entry; read by the Wave 3 idle poll.` This var is the contract for plan 04-05.

    Replace the stub `async function loadBlock(slug) { showView('block'); /* renderer in Wave 2 plan 03 */ }` with a real implementation. Match the loadEdition() shape (lines 173-193) but adapted for three coordinated queries. Single-quoted strings + `+` concat, no template literals.

    loadBlock(slug) shape:
    1. `showView('block');`
    2. `timelineExpanded = false;` (reset expand state on every entry into a block page)
    3. Fire the blocks-row + timeline-entries queries in parallel via Promise.all:
       ```
       var [blockRes, timelineRes] = await Promise.all([
           sb.schema('economy_map').from('blocks').select('*').eq('slug', slug).single(),
           sb.schema('economy_map').from('timeline_entries').select('block_slug,event_date,what_shifted,why_it_mattered,source_url').eq('block_slug', slug).order('event_date', { ascending: false }).limit(30)
       ]);
       ```
       Per D-17 do NOT add `.eq('status', 'published')` on the blocks query; do NOT add `.neq('block_slug', 'unsorted')` on the timeline query — RLS already filters. The timeline `.eq('block_slug', slug)` filter is functional, not security (it scopes to this block's entries).
    4. Error guard:
       ```
       if (blockRes.error || !blockRes.data) {
           document.getElementById('block-content').innerHTML = '<p style="color:var(--text-secondary);">Block not found.</p>';
           updateHero('Block Not Found', '');
           console.error('loadBlock error:', blockRes.error);
           return;
       }
       ```
       Timeline query failures degrade gracefully (block still renders without Evolution entries): `var timelineEntries = (timelineRes.error || !timelineRes.data) ? [] : timelineRes.data;`.
    5. Conditionally fetch the published body if `blockRes.data.current_body_version_id` is non-null:
       ```
       var bodyMd = null;
       if (blockRes.data.current_body_version_id) {
           var bodyRes = await sb.schema('economy_map').from('block_body_versions').select('body_md').eq('id', blockRes.data.current_body_version_id).single();
           if (!bodyRes.error && bodyRes.data) bodyMd = bodyRes.data.body_md;
       }
       ```
       Per D-17 do NOT add `.eq('status', 'published')` — RLS only exposes published versions to anon. If the FK target row doesn't satisfy RLS (e.g., it was rejected), this query returns null/empty and we treat it as no body (graceful fall-through to D-10's hide-when-null).
    6. Stash on `window.currentBlock = blockRes.data;` and `window.currentTimelineEntries = timelineEntries;` (plan 04-05 reads these during idle poll).
    7. Update hero per D-02: `var dateText = blockRes.data.last_synthesized_at ? 'synthesized ' + formatDate(blockRes.data.last_synthesized_at) : '';` then `updateHero(blockRes.data.title, dateText);`.
    8. Call `renderBlock(blockRes.data, bodyMd, timelineEntries);` and `window.scrollTo(0, 0);`.

    Add `function renderBlock(block, bodyMd, entries)` immediately after loadBlock. Build the composition (D-08 order Title → tension → body → Evolution):

    A. Header (always renders) — D-09 inline pill, right-aligned. The header itself carries `data-accent` so the cascade on `.block-header` resolves `--accent-tier` for the pill (and for any decorative use):
       ```
       var headerHtml =
           '<header class="block-header" data-accent="' + escapeHtml(block.accent) + '">' +
               '<h1>' + escapeHtml(block.title) + '</h1>' +
               renderMaturityPill(block) +
           '</header>';
       ```
       Re-use a `renderMaturityPill(block)` helper. If plan 04-02 already defined it at module scope, this plan calls it. If plan 04-02 inlined it inside renderHub, define a separate `renderMaturityPill(b)` near the top of the renderers section that emits the canonical markup (tokens-preview.html lines 78-82): 5 segs, data-accent from `b.accent`, data-stage from `MATURITY_STAGE[b.maturity] || 1`, aria-label `'Maturity: ' + escapeHtml(b.maturity) + ' (' + stage + ' of 5)'`. To minimize duplication, the executor should declare `function renderMaturityPill(b)` once at module top alongside the other helpers (lines ~280-290) — both plans 04-02 and 04-04 reference it.

    B. Tension (conditional) — D-10 quiet hide when placeholder:
       ```
       var tensionHtml = '';
       if (block.live_tension &amp;&amp; block.live_tension !== LIVE_TENSION_PLACEHOLDER) {
           tensionHtml = '<section class="block-tension">' + escapeHtml(block.live_tension) + '</section>';
       }
       ```
       The exact-string match against LIVE_TENSION_PLACEHOLDER is the contract from CONTEXT specifics §"Live-tension placeholder string". Per Phase 2 D-21 the seed value is the literal string `'TBD — set via /map-tension'` with an em-dash — the module constant in plan 04-01 mirrors that exactly.

    C. Body (conditional) — D-10 hide when null/missing; D-18 marked.parse:
       ```
       var bodyHtml = '';
       if (bodyMd) {
           bodyHtml = '<section class="block-body">' + marked.parse(bodyMd) + '</section>';
       }
       ```
       Per Phase 4 PATTERNS the only path that bypasses escapeHtml is body_md → marked.parse. This is the same pattern as renderArticle() line 169. (Threat note: this assumes the Phase 7 synthesis prompt + Phase 8 validator are the upstream sanitizers; treat the residual XSS risk as a known acceptance under T-04-03-01 in the threat model below.)

    D. Evolution (always renders, even with zero entries) — newest-first per RNDR-07, 30-cap + show-all per D-11. Factor the entry list into a sibling function `function renderTimelineEntries(entries, expanded)` that returns the inner HTML for `#evolution-entries`. renderBlock() emits the wrapper:
       ```
       var evolutionHtml =
           '<section class="evolution">' +
               '<h2>Evolution</h2>' +
               '<div id="evolution-entries">' + renderTimelineEntries(entries, timelineExpanded) + '</div>' +
               (entries.length === 30 &amp;&amp; !timelineExpanded
                   ? '<button class="timeline-show-all" onclick="expandTimeline()">Show all (' + entries.length + ' or more) &darr;</button>'
                   : '') +
           '</section>';
       ```
       Note on the count label: when the result hits the 30 cap, we don't yet know the total; the label reads "Show all (30 or more)" — matches D-11's intent. After expansion, the executor can pass the unbounded count.

    E. Compose final innerHTML write target:
       ```
       document.getElementById('block-content').innerHTML = headerHtml + tensionHtml + bodyHtml + evolutionHtml;
       ```
       The `← Map` back-link lives in the static markup from plan 04-01 (sibling to `#block-content` inside the same `.content-area`); the renderer does not need to emit it.

    Add `function renderTimelineEntries(entries, expanded)` — emits the timeline-entry markup matching tokens-preview.html lines 114-125 (with source) and lines 128-137 (without source). Newest-first ordering is already in the array (the .order() clause on the query). For each entry:
    - If `e.source_url` is a non-empty string: open `<article class="timeline-entry" data-source="' + escapeHtml(e.source_url) + '">`. Emit the line1 with date + sep + what_shifted; line2 with why_it_mattered + `<a class="timeline-source" href="' + escapeHtml(e.source_url) + '" target="_blank" rel="noopener noreferrer">source &uarr;</a>` (the `&uarr;` is the ↗ glyph per TOKN-03; if the existing CSS uses literal `↗`, use that — verify against style-map.css line ~88 in the markup-contract comment).
    - If `e.source_url` is null/empty: open `<article class="timeline-entry">` (NO data-source attribute, omit the entire `<a class="timeline-source">` element — Phase 3 contract from style-map.css lines 91-94).
    - Date renders via `formatDate(e.event_date)` for consistent display.
    - All four strings (event_date already passed through formatDate but defensively escapeHtml the result; what_shifted; why_it_mattered; source_url in both href and data-source) pass through escapeHtml().
    - If entries.length === 0, return `'<p style="color:var(--text-secondary);">No timeline entries yet.</p>'` (graceful empty state — distinct from D-10 hide-section behavior; Evolution always renders per D-08, just with an empty-state message).

    Add `function expandTimeline()` (called from the onclick on `.timeline-show-all`). Shape:
    ```
    async function expandTimeline() {
        if (!window.currentBlock) return;
        timelineExpanded = true;
        var slug = window.currentBlock.slug;
        var { data, error } = await sb.schema('economy_map').from('timeline_entries').select('block_slug,event_date,what_shifted,why_it_mattered,source_url').eq('block_slug', slug).order('event_date', { ascending: false });
        if (error || !data) return;
        window.currentTimelineEntries = data;
        document.getElementById('evolution-entries').innerHTML = renderTimelineEntries(data, true);
        var btn = document.querySelector('.timeline-show-all');
        if (btn) btn.remove();  // one-shot per D-11
    }
    ```
    Window-scoping: `expandTimeline` must be assignable via `window.expandTimeline = expandTimeline;` at the bottom of the file (or declared at module top-level without strict mode — the file is non-module classic script, so top-level declarations are global; verify by checking the existing functions like `scrollToSubscribe` at line 236 which are also called from inline onclick handlers). The simplest path: declare as `function expandTimeline()` at top level (no var), matching scrollToSubscribe / handleSubscribe pattern.

    Do NOT add a `setInterval` here — that lives in Wave 3 plan 05. Do NOT add visibilitychange or hashchange listeners — plan 04-05 owns those. Do NOT mutate any database row — block pages are read-only in this phase. Do NOT trigger setMode() re-renders — body mode is preserved.

    Important: the renderMaturityPill helper might be declared either by this plan or by plan 04-02 (whichever runs second declares it; whichever runs first declares it. Since they run in the same Wave 2 in parallel, this is a real merge concern). Mitigation: BOTH plans 04-02 and 04-03 are expected to add the helper, but the EXECUTOR for whichever plan runs second checks if `function renderMaturityPill` already exists and skips the declaration. Acceptance criteria below cover both cases by checking the function exists in the final file.
  </action>
  <verify>
    <automated>set -e; F=docker/web/site/app.js; grep -q "async function loadBlock" "$F"; grep -q "function renderBlock" "$F"; grep -q "function renderTimelineEntries" "$F"; grep -q "function expandTimeline\|window.expandTimeline" "$F"; grep -q "var timelineExpanded" "$F"; grep -q "Promise.all" "$F"; grep -q "sb.schema('economy_map').from('blocks').select.*eq('slug'" "$F" || grep -q "from('blocks').select" "$F"; grep -q "from('timeline_entries').select" "$F"; grep -q ".order('event_date', { ascending: false }).limit(30)" "$F"; grep -q "from('block_body_versions').select" "$F"; grep -q "LIVE_TENSION_PLACEHOLDER" "$F"; grep -q "marked.parse(bodyMd)" "$F"; grep -q "rel=\"noopener noreferrer\"" "$F"; grep -q 'class="timeline-show-all"' "$F"; grep -q 'class="block-header"' "$F"; grep -q 'class="block-tension"' "$F"; grep -q 'class="block-body"' "$F"; grep -q 'class="evolution"' "$F"; grep -q "function renderMaturityPill" "$F"; ! grep -q '`' "$F" || { echo "FAIL: template literal detected"; exit 1; }; node -e "new Function(require('fs').readFileSync('$F','utf8').replace(/window\.supabase[^;]*;?/g,'').replace(/__SUPABASE_URL__/g,'x').replace(/__SUPABASE_ANON_KEY__/g,'x'))"; echo OK</automated>
  </verify>
  <acceptance_criteria>
    - Source: `async function loadBlock(slug)` exists and contains the three-query pattern: a `blocks` query with `.eq('slug', slug).single()`, a `timeline_entries` query with `.eq('block_slug', slug).order('event_date', { ascending: false }).limit(30)`, and a conditional `block_body_versions` query keyed by `current_body_version_id`.
    - Source: `Promise.all([...])` wraps at minimum the blocks + timeline queries.
    - Source: `var timelineExpanded = false;` exists at module scope (NOT inside a function); it is set back to false at the top of loadBlock().
    - Source: NO defensive RLS-redundant filters: zero occurrences of `.eq('status', 'published')` AND zero occurrences of `.neq('block_slug', 'unsorted')` in loadBlock or renderTimelineEntries.
    - Source: `function renderBlock(block, bodyMd, entries)` emits `<header class="block-header">`, then conditionally `<section class="block-tension">` (gated by `block.live_tension !== LIVE_TENSION_PLACEHOLDER`), then conditionally `<section class="block-body">` (gated by `bodyMd` truthiness), then unconditionally `<section class="evolution">`.
    - Source: body_md is rendered via `marked.parse(bodyMd)` — same precedent as renderArticle() line 169. Verify via `grep "marked.parse(bodyMd)" docker/web/site/app.js`.
    - Source: every `escapeHtml(...)` call on a timeline-entry field — what_shifted, why_it_mattered, source_url — is present. Verify at least 3 escapeHtml calls inside renderTimelineEntries via grep.
    - Source: timeline-source anchors carry `target="_blank"` AND `rel="noopener noreferrer"`. Verify both substrings present.
    - Source: timeline-show-all button is conditional on `entries.length === 30` AND `!timelineExpanded` — verify via grep on the conditional expression.
    - Source: `function renderMaturityPill` exists exactly once in the final file (after both plans 04-02 and 04-03 have shipped). If the function appears in both plans' diffs, this is a merge defect — fix by deleting the duplicate.
    - Source: `function expandTimeline` exists at top level (not nested) — it must be callable from inline `onclick="expandTimeline()"` so it needs global scope. Verify via grep.
    - Source: `window.currentBlock = ...` and `window.currentTimelineEntries = ...` assignments exist inside loadBlock — plan 04-05 reads these.
    - Source: zero template literals (no backticks).
    - Behavior (post-deploy, manual — verified in plan 04-06): Visit `#/map/identity-trust`. Header shows "Identity & Trust" (or whatever Phase 2 D-23 seeded) with a 1/5 maturity pill right-aligned (nascent = stage 1). Tension section is HIDDEN (because seed value is the placeholder). Body section is HIDDEN (because `current_body_version_id` is null). Evolution section is VISIBLE with the message "No timeline entries yet." (because Phase 5 hasn't shipped intake yet). The `← Map` back-link is present (from plan 04-01 static markup). DevTools Network: exactly 2 GETs initially (blocks single + timeline_entries query) since `current_body_version_id` is null — the body query is skipped.
  </acceptance_criteria>
  <done>
    loadBlock(slug) and renderBlock() fully replace the plan 04-01 stub: three-query orchestration via Promise.all + conditional body fetch, six-part composition with empty-state hide for tension and body, Evolution section always present with newest-first 30-cap and the Show all expand mechanism wired through a module-level `timelineExpanded` flag. All DB strings escaped except body_md which goes through marked.parse. Timeline source anchors are noopener-noreferrer + _blank. No template literals; no RLS-redundant filters; no setInterval (Wave 3).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser ↔ Supabase PostgREST | Anon reads on blocks (single-row by slug), timeline_entries (by block_slug, ordered, capped 30), block_body_versions (by id, published-only via RLS). |
| Supabase response ↔ DOM (innerHTML) | block.title/subtitle/live_tension; timeline_entries.what_shifted/why_it_mattered/source_url; block_body_versions.body_md. |
| timeline_entries.source_url ↔ outbound nav | `<a class="timeline-source" href="{source_url}" target="_blank">` opens an attacker-controllable URL. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-03-01 | Tampering (XSS via markdown) | body_md → marked.parse() → innerHTML | accept (with residual flag) | body_md flows from Phase 7 synthesis (Claude Sonnet output) and is treated as trusted editorial content; the gated publish in Phase 9 is the human approval boundary. Phase 4 inherits the upstream sanitization assumption — marked is configured at marked@latest defaults which escape `<script>` tags but allow inline HTML in markdown by default. RESIDUAL CONCERN: a future malicious synthesis prompt injection could embed inline event handlers (e.g., `<img onerror>`); the operator-as-final-arbiter (publish gate) is the compensating control. Phase 4 does NOT switch marked to a sanitizer here — that is a Phase 7/8 sanitization concern. Document this acceptance in the SUMMARY. |
| T-04-03-02 | Tampering (open redirect via source_url) | `<a class="timeline-source" href="{source_url}">` | mitigate | Anchor is emitted with `rel="noopener noreferrer" target="_blank"`. Window opener is severed; referrer is not leaked. Phase 5 (intake) is the upstream URL-hygiene owner — this plan does NOT validate scheme (per planning_context's stated mitigation). Residual: a malicious link still resolves on click; the operator manually approves intake via Phase 5/6 flow. |
| T-04-03-03 | Tampering (XSS via plain DB strings) | block.title/subtitle/live_tension, timeline_entries.what_shifted/why_it_mattered, source_url in data-source attribute | mitigate | All seven non-body strings pass through `escapeHtml()` before string-concat. The data-source attribute also passes through escapeHtml — defensive even though the CSS selector treats it as a presence-check. |
| T-04-03-04 | Denial of Service (huge timeline) | timeline_entries query returns millions of rows after expandTimeline() | mitigate (bounded by data volume; flag for v2) | Initial query is `.limit(30)`. expandTimeline() removes the limit — could fetch all entries for a block. Today no block has more than a handful (Phase 5 hasn't shipped intake yet). Once Phase 5 lands, monitor for blocks accumulating 1000+ entries; the build spec §6 follow-up considers paginated expansion or a sub-route (CONTEXT Deferred Ideas: "Block-page sub-route `/map/<slug>/timeline` for full timeline history"). Accept for v1. |
| T-04-03-05 | Information Disclosure | published body_md and timeline entries leak via anon-key reads | accept | RLS posture (Phase 2 D-06/D-07) explicitly permits anon reads of `status='published'` body versions and `block_slug != 'unsorted'` entries — these are intentionally public. The newsletter editions themselves are also public; this is consistent. |
</threat_model>

<verification>
After this plan deploys (via plan 04-06):
- Visit `#/map/identity-trust`. Header "Identity & Trust" with 1/5 teal pill right-aligned. No tension card. No body section. Evolution heading + "No timeline entries yet." message.
- Click `← Map`. Returns to hub.
- Visit `#/map/regulation-legal`. Same shape but with the gray accent on the pill.
- Manually insert a timeline_entries row via Supabase SQL (e.g., `INSERT INTO economy_map.timeline_entries (block_slug, event_date, what_shifted, why_it_mattered, source_url, tag_confidence) VALUES ('identity-trust', '2026-05-27', 'Test entry', 'Verifies renderer.', 'https://example.com', 1.0);`). Reload `#/map/identity-trust`. The Evolution section shows the entry with `2026-05-27 · Test entry` on line 1 and `Verifies renderer. source ↗` on line 2 (the source link opening in a new tab, rel noopener).
- Insert 31 rows. Reload. Initial render shows 30 entries (newest first by event_date). A "Show all (30 or more) ↓" button appears below. Click it. The list refreshes to show all 31 entries; the button disappears.
- Insert a row with `source_url = NULL`. Reload. That entry renders without a `source ↗` link and without the data-source attribute (verifiable in DevTools Elements inspector).
</verification>

<success_criteria>
- loadBlock(slug), renderBlock(), renderTimelineEntries(), and expandTimeline() exist in app.js, replacing the plan 04-01 stub.
- RNDR-02 satisfied: block page shows Title + maturity pill (inline right-aligned), and conditionally tension + body + always Evolution.
- RNDR-07 satisfied: timeline entries render newest-first via `.order('event_date', { ascending: false })`.
- D-10 empty-state behavior holds: tension hidden when placeholder, body hidden when null body version.
- D-11 expand mechanism works: limit 30 by default, "Show all" button appears at the cap, click expands and persists the expanded state on `timelineExpanded`.
- `window.currentBlock` and `window.currentTimelineEntries` are populated for plan 04-05's idle poll.
- Timeline source anchors are noopener-noreferrer + _blank.
- No template literals; no defensive `status='published'` or `block_slug != 'unsorted'` filters.
</success_criteria>

<output>
After completing the task, create `.planning/phases/04-hub-block-and-status-renderer/04-03-SUMMARY.md` summarizing:
- Whether renderMaturityPill was already defined by plan 04-02 (so this plan referenced it) or this plan added the definition
- The exact em-dash character used in LIVE_TENSION_PLACEHOLDER's exact-match comparison (must match Phase 2 D-21 — single character `—` U+2014)
- A note on the T-04-03-01 residual XSS-via-markdown concern (operator/Phase 9 approval is the compensating control)
- The git commit hash
</output>
