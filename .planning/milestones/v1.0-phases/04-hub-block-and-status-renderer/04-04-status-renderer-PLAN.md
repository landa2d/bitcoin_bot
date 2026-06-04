---
phase: 04-hub-block-and-status-renderer
plan: 04
type: execute
wave: 4
depends_on:
  - 04-01
  - 04-02
  - 04-03
files_modified:
  - docker/web/site/app.js
autonomous: true
requirements:
  - RNDR-03
  - RNDR-04
tags:
  - frontend
  - spa
  - renderer
  - status
must_haves:
  truths:
    - "Visiting #/status fires a single Supabase query — `sb.schema('economy_map').from('blocks').select(...).order('sort_order', { ascending: true })` — same source as the hub query (RNDR-04 one source of truth) — per D-15, D-16"
    - "Status page renders three tier sections (SUBSTRATE / BEHAVIOR / FRAME) — same grouping as the hub — per D-15"
    - "Each status row shows: maturity pill + title + subtitle (optional) + last_synthesized_at timestamp — per D-15"
    - "Rows are NOT links in v1 (status is the snapshot surface; hub is navigation) — per D-15 + Deferred Idea 'Status page rows linking to block pages'"
    - "Hero shows STATUS_PAGE_HEADER + 'updated <NOW>' (or omit date if undesirable) — per D-02"
    - "last_synthesized_at renders as 'synthesized <date>' when non-null, 'never synthesized' when null — per D-15"
    - "All DB strings (title, subtitle, accent, maturity) pass through escapeHtml() — per PATTERNS §'Always escape DB strings'"
  artifacts:
    - path: docker/web/site/app.js
      provides: "loadStatus() + renderStatus() — full status renderer wired to economy_map"
      contains: "function renderStatus"
  key_links:
    - from: "loadStatus()"
      to: "sb.schema('economy_map').from('blocks')"
      via: "same single query the hub uses — RNDR-04 single source of truth"
      pattern: "sb\\.schema\\(['\"]economy_map['\"]\\)\\.from\\(['\"]blocks['\"]\\)"
    - from: "renderStatus()"
      to: ".status-row markup (plan 04-01 ships the selector)"
      via: "string-concat HTML with escapeHtml on every DB string"
      pattern: 'class="status-row"'
---

<objective>
Replace the no-op `loadStatus()` stub shipped in plan 04-01 with a full status renderer: query the seven blocks once (same query shape the hub uses, demonstrating RNDR-04 single-source-of-truth), group by tier, and render one snapshot row per block showing the maturity pill + title + subtitle + last_synthesized_at affordance.

Purpose: Deliver RNDR-03 (status page) and the status half of RNDR-04 (one source of truth — verifiable by changing a block's maturity in DB and seeing both hub and status update consistently on next nav). The verification of RNDR-04 happens in plan 04-06.

Output: docker/web/site/app.js — loadStatus() performs the query and dispatches to a new renderStatus() function that emits the three-section snapshot.
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
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement loadStatus() + renderStatus() inside app.js</name>
  <files>docker/web/site/app.js</files>
  <read_first>
    - docker/web/site/app.js (the file being modified — re-read fully; loadList() at lines 135-152 is the closest no-row-target loader analog; renderList() at lines 107-133 the closest map-and-render analog; escapeHtml() at lines 274-278; formatDate() at lines 280-285. Plan 04-01 will have added stub `async function loadStatus() { showView('status'); }` — this task replaces the body.)
    - .planning/phases/04-hub-block-and-status-renderer/04-PATTERNS.md (Pattern Assignment #4 specific bullets for loadStatus; #5 renderStatus markup)
    - .planning/phases/04-hub-block-and-status-renderer/04-CONTEXT.md (D-02 status hero copy; D-15 status row composition; D-16 schema path; D-17 RLS posture)
    - .planning/phases/04-hub-block-and-status-renderer/04-02-hub-renderer-PLAN.md (read this if plan 04-02 ships first — the renderMaturityPill helper this plan uses is shared)
  </read_first>
  <action>
    Replace the stub `async function loadStatus() { showView('status'); /* renderer in Wave 2 plan 04 */ }` with a real implementation, AND add a new sync `function renderStatus(data)` immediately after it. Match the existing loader idiom from loadList() lines 135-152.

    loadStatus() shape:
    1. `showView('status');`
    2. Query: `var { data, error } = await sb.schema('economy_map').from('blocks').select('slug,title,subtitle,accent,tier,sort_order,maturity,last_synthesized_at').order('sort_order', { ascending: true });` — narrower column list than loadHub (no live_tension, no current_body_version_id) since status doesn't render those. The KEY shape — same `sb.schema('economy_map').from('blocks')` query — is the RNDR-04 contract. Per D-17 do NOT add `.eq('status', 'published')` or any defensive filter.
    3. Error guard:
       ```
       if (error || !data || data.length === 0) {
           document.getElementById('status-content').innerHTML = '<p style="color:var(--text-secondary);font-size:15px;padding:20px 24px;">Status data unavailable.</p>';
           updateHero(STATUS_PAGE_HEADER, '');
           console.error('loadStatus error:', error);
           return;
       }
       ```
    4. Stash: `window.currentStatusBlocks = data;` (mostly for symmetry with the other loaders; status doesn't currently need re-render hooks but the assignment matches the pattern).
    5. Update hero: `updateHero(STATUS_PAGE_HEADER, 'updated ' + formatDate(new Date().toISOString()));` per D-02. (If the operator finds the "updated NOW" affordance noisy, that is a CSS-only follow-up — the data is correct.)
    6. Call `renderStatus(data);`.

    renderStatus(data) shape — string-concat HTML, single quotes + `+`, no template literals:

    1. Group by tier the same way renderHub does:
       ```
       var substrateBlocks = data.filter(function(b){return b.tier === 'substrate';});
       var behaviorBlocks  = data.filter(function(b){return b.tier === 'behavior';});
       var frameBlocks     = data.filter(function(b){return b.tier === 'frame';});
       ```

    2. Emit a helper `function renderStatusRow(b)` producing a single row per D-15:
       ```
       var synthText = b.last_synthesized_at
           ? 'synthesized ' + formatDate(b.last_synthesized_at)
           : 'never synthesized';
       return '<div class="status-row" data-accent="' + escapeHtml(b.accent) + '">' +
           renderMaturityPill(b) +
           '<div class="status-title">' + escapeHtml(b.title) + '</div>' +
           (b.subtitle ? '<div class="status-subtitle">' + escapeHtml(b.subtitle) + '</div>' : '') +
           '<time class="status-synth">' + escapeHtml(synthText) + '</time>' +
       '</div>';
       ```
       The CSS for `.status-row` (plan 04-01 ships it) handles the flex layout: pill on the left, title next, subtitle taking remaining width (flex:1), synth timestamp right-aligned. The `data-accent` on the row drives the left-border stripe via the cascade. Note: D-15 explicitly says no link from status rows to block pages in v1 — this is intentional. The row is a `<div>`, not an `<a>`.

    3. Re-use the `renderMaturityPill(b)` helper defined by plan 04-02 (or plan 04-03 — whichever Wave 2 plan declares it first). If neither has shipped it yet (file ordering during merge), the executor MUST verify the helper exists and emits the canonical 5-segment markup per tokens-preview.html lines 78-82 (data-accent + data-stage from MATURITY_STAGE[b.maturity] || 1 + aria-label).

    4. Wrap each tier in `<section class="tier-section">` with a `<h2 class="tier-label">` heading, same as renderHub. Skip empty sections (defense — should never happen).

    5. Final write:
       ```
       var html =
           '<section class="tier-section">' +
               '<h2 class="tier-label">' + TIER_LABELS.substrate + '</h2>' +
               substrateBlocks.map(renderStatusRow).join('') +
           '</section>' +
           '<section class="tier-section">' +
               '<h2 class="tier-label">' + TIER_LABELS.behavior + '</h2>' +
               behaviorBlocks.map(renderStatusRow).join('') +
           '</section>' +
           '<section class="tier-section">' +
               '<h2 class="tier-label">' + TIER_LABELS.frame + '</h2>' +
               frameBlocks.map(renderStatusRow).join('') +
           '</section>';
       document.getElementById('status-content').innerHTML = html;
       window.scrollTo(0, 0);
       ```

    Notes:
    - Do NOT include a navigation back-link on the status page (D-15 + discretion: status is its own snapshot surface; the nav Map link is the way back to the hub).
    - Do NOT poll status (no live-update requirement on RNDR-06 — that requirement is scoped to the block page's Evolution section).
    - Do NOT add setMode() hooks — status doesn't depend on technical/strategic mode.
    - The `<time>` element's text content is just the synth string; do NOT add a `datetime=...` attribute in v1 (none of the existing site uses semantic `<time datetime>`; can add later as a polish).
  </action>
  <verify>
    <automated>set -e; F=docker/web/site/app.js; grep -q "async function loadStatus" "$F"; grep -q "function renderStatus" "$F"; grep -q "sb.schema('economy_map').from('blocks')" "$F"; grep -q "STATUS_PAGE_HEADER" "$F"; grep -q "TIER_LABELS.substrate" "$F"; grep -q "TIER_LABELS.behavior" "$F"; grep -q "TIER_LABELS.frame" "$F"; grep -q 'class="status-row"' "$F"; grep -q 'class="status-title"' "$F"; grep -q 'class="status-synth"' "$F"; grep -q "never synthesized" "$F"; grep -q "function renderMaturityPill" "$F"; grep -cE 'sb\.schema\(.economy_map.\)\.from\(.blocks.\)' "$F" | awk '$1 &gt;= 2 {print "OK: hub + status both query blocks (one source of truth)"; exit 0} {print "FAIL: expected 2 blocks queries (hub + status), got " $1; exit 1}'; ! grep -q '`' "$F" || { echo "FAIL: template literal"; exit 1; }; node -e "new Function(require('fs').readFileSync('$F','utf8').replace(/window\.supabase[^;]*;?/g,'').replace(/__SUPABASE_URL__/g,'x').replace(/__SUPABASE_ANON_KEY__/g,'x'))"; echo OK</automated>
  </verify>
  <acceptance_criteria>
    - Source: `async function loadStatus()` body contains `sb.schema('economy_map').from('blocks').select(...).order('sort_order', { ascending: true })` — the SAME query shape used by loadHub (RNDR-04 single source of truth).
    - Source: the select() column list for loadStatus includes (at minimum): `slug, title, subtitle, accent, tier, sort_order, maturity, last_synthesized_at`.
    - Source: NO `.eq('status', 'published')` or `.neq(...)` defensive filters anywhere in loadStatus or renderStatus.
    - Source: `function renderStatus(data)` exists and emits three `<section class="tier-section">` blocks with `<h2 class="tier-label">` headings sourced from TIER_LABELS.
    - Source: each row is a `<div class="status-row">`, NOT an `<a>` (verified by checking that `class="status-row"` is preceded by `<div` not `<a`).
    - Source: each row contains `class="status-row"`, `class="status-title"`, and `class="status-synth"`. The `class="status-subtitle"` appears conditionally on truthy subtitle.
    - Source: each row's `data-accent` value comes from `b.accent` and passes through escapeHtml.
    - Source: `renderMaturityPill(...)` is invoked inside renderStatusRow (the helper is declared exactly once in the file across all Wave 2 plans).
    - Source: every DB string (`b.title`, `b.subtitle`, `b.accent`) and the computed `synthText` passes through `escapeHtml(...)` before innerHTML.
    - Source: `'never synthesized'` literal appears in the file (the null-branch label per D-15).
    - Source: `STATUS_PAGE_HEADER` constant is referenced in the `updateHero(...)` call (D-02).
    - Source: zero template literals.
    - Source: the file contains ≥ 2 occurrences of `sb.schema('economy_map').from('blocks')` (hub + status both query the same table — RNDR-04 evidence via source duplication).
    - Behavior (post-deploy, manual — verified in plan 04-06): Visit `#/status`. Hero shows "Maturity Snapshot" + "updated <today's date>". Three tier headings render. Seven status rows render in correct order (identity-trust → … → regulation-legal). Each row shows a maturity pill on the left, the block's title and subtitle in the middle, and "never synthesized" on the right (since no synthesis has run yet). Rows are NOT clickable. DevTools Network: exactly one GET to `/rest/v1/blocks?select=...&order=sort_order.asc...` with `Accept-Profile: economy_map` header.
  </acceptance_criteria>
  <done>
    The status renderer is wired: loadStatus() queries `economy_map.blocks` with the same query shape as the hub, renderStatus() emits a tier-grouped snapshot of seven non-clickable rows showing maturity pill + title + subtitle + last_synthesized_at affordance. The two queries (hub + status) reading from the same table is the source-of-truth evidence for RNDR-04. No template literals; no RLS-redundant filters; no setMode hooks; no poll.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser ↔ Supabase PostgREST | Same as plan 04-02 — anon reads of `economy_map.blocks` via supabase-js .schema(). |
| Supabase response ↔ DOM | block.title, block.subtitle, block.accent, block.maturity flow into innerHTML. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-04-01 | Tampering (XSS) | block.title, block.subtitle, block.accent, block.maturity, formatDate(last_synthesized_at) rendered to innerHTML | mitigate | All five strings pass through `escapeHtml()` before string-concat (PATTERNS §"Always escape DB strings"). last_synthesized_at is already produced by formatDate() but the resulting string is also escapeHtml'd for defense in depth. |
| T-04-04-02 | Information Disclosure | status reveals maturity values for all seven blocks | accept | Same disposition as plan 04-02 T-04-02-03 — the seven blocks are public editorial surface; RLS authorizes anon reads. |
| T-04-04-03 | Denial of Service | tight `#/status` refresh loop | accept | No state mutation; one cheap PostgREST read per nav. RLS-bounded result set (7 rows). Same risk envelope as the hub. |
</threat_model>

<verification>
After this plan deploys (via plan 04-06):
- Visit `#/status`. Hero "Maturity Snapshot" + today's date. Three tier sections render seven rows total in correct sort_order. Each row has a 1/5 pill (since seed maturity is `nascent`). Each row reads "never synthesized" (no synthesis yet). Rows are not clickable.
- DevTools Network confirms exactly one `/rest/v1/blocks` GET with `Accept-Profile: economy_map`.
- The RNDR-04 cross-check (mutating one block's maturity in DB and seeing both hub and status reflect it) lives in plan 04-06's verification — this plan establishes the technical precondition (same query shape) but the runtime cross-check is the deploy-time activity.
</verification>

<success_criteria>
- loadStatus() and renderStatus() exist in app.js, replacing the plan 04-01 stub.
- RNDR-03 satisfied: status URL shows all seven blocks' maturity at a glance, tier-grouped.
- RNDR-04 satisfied at the source level: hub and status read from the same `sb.schema('economy_map').from('blocks')` query (verifiable by grep counting 2+ occurrences). Runtime verification by plan 04-06.
- D-15 honored: rows are non-clickable divs; pill + title + (optional) subtitle + last_synthesized_at.
- No template literals; no RLS-redundant filters.
</success_criteria>

<output>
After completing the task, create `.planning/phases/04-hub-block-and-status-renderer/04-04-SUMMARY.md` summarizing:
- The final column list passed to .select() inside loadStatus (compared to plan 04-02's loadHub column list)
- Confirmation that hub + status both call `sb.schema('economy_map').from('blocks')` (RNDR-04 source-level evidence)
- The git commit hash
</output>
