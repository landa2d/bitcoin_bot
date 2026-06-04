---
phase: 04-hub-block-and-status-renderer
plan: 05
type: execute
wave: 5
depends_on:
  - 04-01
  - 04-02
  - 04-03
  - 04-04
files_modified:
  - docker/web/site/app.js
autonomous: true
requirements:
  - RNDR-06
tags:
  - frontend
  - spa
  - lifecycle
  - polling
must_haves:
  truths:
    - "On every entry into loadBlock(slug), startEvolutionPoll(slug) is called at the end of the success path — per D-06"
    - "The poll re-queries ONLY timeline_entries (not blocks, not block_body_versions) — per D-06"
    - "Poll cadence is exactly 60_000 ms via setInterval — per D-07"
    - "A visibilitychange listener pauses the poll work when document.visibilityState !== 'visible' (the interval keeps firing but the work is short-circuited) — per D-07"
    - "A hashchange listener calls stopEvolutionPoll() whenever the new hash does NOT start with '#/map/' — per D-07"
    - "The poll respects the timelineExpanded state from plan 04-03: if expanded, query unbounded; else .limit(30) — per D-11"
    - "Inserting a new timeline_entries row causes the Evolution section to re-render within ~60 seconds while the operator is on the block page — RNDR-06"
    - "Realtime / sb.channel() is NOT introduced (deferred to v2) — per D-05"
  artifacts:
    - path: docker/web/site/app.js
      provides: "Idle poll lifecycle: startEvolutionPoll, stopEvolutionPoll, pollEvolution, visibilitychange + hashchange wiring"
      contains: "function startEvolutionPoll"
  key_links:
    - from: "loadBlock(slug) success path"
      to: "startEvolutionPoll(slug)"
      via: "tail-call of the loader"
      pattern: "startEvolutionPoll\\("
    - from: "hashchange listener"
      to: "stopEvolutionPoll()"
      via: "guard: !window.location.hash.startsWith('#/map/')"
      pattern: "stopEvolutionPoll\\(\\)"
    - from: "pollEvolution(slug)"
      to: "renderTimelineEntries(data, timelineExpanded)"
      via: "wholesale innerHTML replacement on #evolution-entries (matches renderArticle/renderList wholesale-replace idiom — PATTERNS §'No analog found' mitigation)"
      pattern: "evolution-entries"
---

<objective>
Wire the visibility-aware 60s idle poll that updates the Evolution section on block pages so that a new `timeline_entries` insert appears within ~60 seconds without the operator navigating away and back. This satisfies RNDR-06 ("re-render is triggered by both a publish AND a timeline entry insert — Evolution section is live data") for the timeline-entry path. The publish path satisfies itself via D-05's next-navigation baseline (a new published body shows on next nav to the block page).

Purpose: Close the live-data half of RNDR-06 without introducing Realtime push (D-05 — deferred to v2). The hybrid pull + idle-poll mechanism is the simplest implementation that delivers "operator does not have to wait for the next synthesis run" with worst-case ~60 second lag.

Output: docker/web/site/app.js — module-level poll handle, three new functions (startEvolutionPoll, stopEvolutionPoll, pollEvolution), one new hashchange listener (separate from the existing routing listener), one optional visibilitychange listener, and a single new line at the end of loadBlock()'s success path calling startEvolutionPoll(slug).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/04-hub-block-and-status-renderer/04-CONTEXT.md
@.planning/phases/04-hub-block-and-status-renderer/04-PATTERNS.md
@.planning/phases/04-hub-block-and-status-renderer/04-03-block-renderer-PLAN.md
@docker/web/site/app.js
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add the idle poll lifecycle to app.js and wire it from loadBlock</name>
  <files>docker/web/site/app.js</files>
  <read_first>
    - docker/web/site/app.js (the file being modified — re-read fully; pay attention to the existing hashchange listener at line 314, the DOMContentLoaded init block at lines 309-312, the loadBlock() function added by plan 04-03 (full body of loadBlock at whatever line it lives), the timelineExpanded module var added by plan 04-03, the renderTimelineEntries function added by plan 04-03 — this plan reads and calls all of those.)
    - .planning/phases/04-hub-block-and-status-renderer/04-PATTERNS.md (§ "docker/web/site/app.js" Pattern Assignment #7 "Idle poll lifecycle" — full code skeleton; § "Shared Patterns" → "No analog found" → row for "Diffing a re-queried list against the rendered DOM" — wholesale-replacement mitigation)
    - .planning/phases/04-hub-block-and-status-renderer/04-CONTEXT.md (D-05 hybrid pull + idle-poll no Realtime; D-06 poll scope is timeline_entries only; D-07 60s + visibility-aware + hashchange cleanup; D-11 expand-state respected by poll)
    - .planning/phases/04-hub-block-and-status-renderer/04-03-block-renderer-PLAN.md (the loadBlock and renderTimelineEntries contract this plan extends)
  </read_first>
  <action>
    Five additions to app.js. ALL new code uses single quotes + var (matches the file idiom), no template literals, no async/await for the interval callback itself (the inner pollEvolution function is async; the setInterval callback is a non-async function that fires-and-forgets the async call).

    Addition 1 — Module-level state. Near the other module state vars (e.g., right after `var timelineExpanded = false;` from plan 04-03), add:
    ```
    var evolutionPollHandle = null;  // setInterval handle for the block-page Evolution refresh (D-05, D-06, D-07)
    ```

    Addition 2 — Three new functions placed BEFORE the existing `function route()` (so they sit alongside the other map-related functions). Order: stopEvolutionPoll, pollEvolution, startEvolutionPoll. Match the existing function declaration idiom (top-level `function name() { ... }`, no `var x = function ...`).

    stopEvolutionPoll():
    ```
    function stopEvolutionPoll() {
        if (evolutionPollHandle !== null) {
            clearInterval(evolutionPollHandle);
            evolutionPollHandle = null;
        }
    }
    ```

    pollEvolution(slug):
    ```
    async function pollEvolution(slug) {
        if (document.visibilityState !== 'visible') return;  // D-07 visibility guard inside the work fn
        // Defensive: if the operator navigated away after the interval fired but before this fn ran, bail.
        if (!window.location.hash.startsWith('#/map/' + slug)) return;
        var query = sb.schema('economy_map').from('timeline_entries')
            .select('block_slug,event_date,what_shifted,why_it_mattered,source_url')
            .eq('block_slug', slug)
            .order('event_date', { ascending: false });
        if (!timelineExpanded) query = query.limit(30);   // D-11 — respect the expanded state set by loadBlock + expandTimeline
        var { data, error } = await query;
        if (error || !data) return;  // graceful no-op on transient error
        window.currentTimelineEntries = data;
        var container = document.getElementById('evolution-entries');
        if (container) container.innerHTML = renderTimelineEntries(data, timelineExpanded);
        // Toggle the Show-all button visibility: if we're not expanded and the result == 30, ensure the button exists; if we're expanded, ensure it's gone.
        var btn = document.querySelector('.timeline-show-all');
        if (!timelineExpanded &amp;&amp; data.length === 30 &amp;&amp; !btn) {
            var evolutionSection = document.querySelector('.evolution');
            if (evolutionSection) {
                var newBtn = document.createElement('button');
                newBtn.className = 'timeline-show-all';
                newBtn.setAttribute('onclick', 'expandTimeline()');
                newBtn.innerHTML = 'Show all (' + data.length + ' or more) ↓';
                evolutionSection.appendChild(newBtn);
            }
        }
        if (timelineExpanded &amp;&amp; btn) {
            btn.remove();
        }
    }
    ```

    startEvolutionPoll(slug):
    ```
    function startEvolutionPoll(slug) {
        stopEvolutionPoll();  // defensive — ensure no stale handle
        evolutionPollHandle = setInterval(function() {
            pollEvolution(slug);
        }, 60000);
    }
    ```

    Addition 3 — Call site in loadBlock(). Add ONE LINE at the END of loadBlock()'s success path (after the `renderBlock(...)` call and `window.scrollTo(0,0);` call from plan 04-03):
    ```
    startEvolutionPoll(slug);
    ```
    If the executor is also editing loadBlock for some reason, NO OTHER CHANGES are permitted to plan 04-03's contract. The stub error-path (`if (blockRes.error || !blockRes.data) { ...; return; }`) does NOT call startEvolutionPoll — exit cleanly without starting the poll.

    Addition 4 — New hashchange listener. Add as a SIBLING to the existing `window.addEventListener('hashchange', route);` at line 314 (do NOT merge into the routing listener — keep idle-poll cleanup separate from main routing per PATTERNS §"#8 Init / DOMContentLoaded" notes). Place it on the next line:
    ```
    window.addEventListener('hashchange', function() {
        if (!window.location.hash.startsWith('#/map/')) {
            stopEvolutionPoll();
        }
    });
    ```
    Note: this listener fires AFTER the existing `route()` listener (browsers dispatch listeners in registration order). When the operator navigates from `#/map/identity-trust` to `#/map`, this listener stops the poll AND route() invokes loadHub() which doesn't restart it. When navigating to a different block, this listener still detects `#/map/` as a prefix match and does NOT stop the poll — but the subsequent loadBlock() call invokes `stopEvolutionPoll()` (defensively, at the top of startEvolutionPoll). That's the correct sequence.

    Addition 5 — Optional visibilitychange listener. The poll itself already short-circuits when hidden (Addition 2). The optional listener triggers an immediate refresh on becoming visible to reduce the "I just came back to this tab, where's my new entry" lag. Add as a sibling to the hashchange listener:
    ```
    window.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'visible'
            &amp;&amp; evolutionPollHandle !== null
            &amp;&amp; window.currentBlock
            &amp;&amp; window.location.hash.startsWith('#/map/')) {
            pollEvolution(window.currentBlock.slug);  // immediate refresh; the next interval tick fires 60s later
        }
    });
    ```
    This is optional per CONTEXT D-07's "Optionally: trigger an immediate refresh on becoming visible." If the executor prefers the simpler version (no immediate refresh), omit this listener — the inner visibility guard still works. RECOMMENDATION: include it; the cost is ~10 lines and it improves the perceived freshness without changing the cadence floor.

    DO NOT:
    - Import or initialize `sb.channel(...)` anywhere (D-05 — no Realtime).
    - Add a poll on the hub or status pages (D-06 — block-page-scoped).
    - Re-query `blocks` or `block_body_versions` inside the poll (D-06 — timeline-only).
    - Reduce the cadence below 60s (D-07).
    - Add a DOM-diffing layer; wholesale `innerHTML = ...` replacement is the existing-renderer idiom (PATTERNS §"No analog found" mitigation row 3).
  </action>
  <verify>
    <automated>set -e; F=docker/web/site/app.js; grep -q "var evolutionPollHandle" "$F"; grep -q "function startEvolutionPoll" "$F"; grep -q "function stopEvolutionPoll" "$F"; grep -q "async function pollEvolution" "$F"; grep -c "setInterval" "$F" | awk '$1 == 1 {print "OK: exactly 1 setInterval"; exit 0} {print "FAIL: expected 1 setInterval, got " $1; exit 1}'; grep -q "60000" "$F"; grep -c "clearInterval" "$F" | awk '$1 &gt;= 1 {print "OK: clearInterval present"; exit 0} {print "FAIL"; exit 1}'; grep -q "document.visibilityState" "$F"; grep -cE "addEventListener\(['\"]hashchange['\"]" "$F" | awk '$1 == 2 {print "OK: 2 hashchange listeners (original + poll-cleanup)"; exit 0} {print "FAIL: expected 2 hashchange listeners, got " $1; exit 1}'; grep -q "evolution-entries" "$F"; grep -q "startEvolutionPoll(slug)" "$F"; ! grep -q "sb.channel" "$F" || { echo "FAIL: Realtime sb.channel() introduced — D-05 prohibits"; exit 1; }; ! grep -q '`' "$F" || { echo "FAIL: template literal"; exit 1; }; node -e "new Function(require('fs').readFileSync('$F','utf8').replace(/window\.supabase[^;]*;?/g,'').replace(/__SUPABASE_URL__/g,'x').replace(/__SUPABASE_ANON_KEY__/g,'x'))"; echo OK</automated>
  </verify>
  <acceptance_criteria>
    - Source: exactly one `var evolutionPollHandle` declaration at module scope.
    - Source: `function startEvolutionPoll(slug)`, `function stopEvolutionPoll()`, and `async function pollEvolution(slug)` all exist as top-level function declarations (not nested inside another function).
    - Source: exactly one `setInterval` call across the whole file, and its cadence argument is exactly `60000` (D-07).
    - Source: at least one `clearInterval(evolutionPollHandle)` call (inside stopEvolutionPoll).
    - Source: pollEvolution body queries ONLY `economy_map.timeline_entries` (verifiable by grep — within the pollEvolution function body, no `from('blocks')` or `from('block_body_versions')`).
    - Source: pollEvolution body contains a `timelineExpanded` check — when `!timelineExpanded`, `.limit(30)` is chained; when expanded, no limit (D-11 respect).
    - Source: `document.visibilityState !== 'visible'` guard exists inside pollEvolution.
    - Source: exactly two `window.addEventListener('hashchange', ...)` registrations in the file (the original from line 314, the new poll-cleanup one). The new listener calls `stopEvolutionPoll()` when the hash does NOT start with `'#/map/'`.
    - Source: loadBlock()'s success path ends with `startEvolutionPoll(slug);` (verify by grep on `startEvolutionPoll(slug)`).
    - Source: ZERO occurrences of `sb.channel(` (no Realtime — D-05).
    - Source: zero template literals.
    - Source: the file still parses (Node check via the same string-substitution trick used in other plans).
    - Behavior (post-deploy, manual — verified in plan 04-06):
      a) Visit `#/map/identity-trust`. In DevTools Network, observe an initial GET to `/rest/v1/timeline_entries?...&limit=30&...`. Wait ≥ 60 seconds without navigating. Observe a SECOND identical GET fire (the interval tick).
      b) In a separate terminal, insert a row via SQL: `INSERT INTO economy_map.timeline_entries (block_slug, event_date, what_shifted, why_it_mattered, source_url, tag_confidence) VALUES ('identity-trust', '2026-05-27', 'Live update verification', 'RNDR-06 working.', NULL, 1.0);`. Within ≤60s of the insert, the Evolution section on the open block page picks up the new entry (visibly appears at the top of the list since event_date is today, newest-first).
      c) Switch tabs. Confirm in DevTools Network that the next minute's tick does NOT fire a query (visibility guard works). Return to the tab. Confirm a query fires immediately (the optional visibilitychange listener) AND the next interval tick fires ~60s later.
      d) Navigate to `#/map` (hub). Confirm in DevTools Network that no further timeline queries fire (hashchange listener stopped the interval).
      e) Click a tile to a different block (`#/map/payments-settlement`). Confirm a fresh poll starts for the new slug; the old slug's queries do NOT fire (startEvolutionPoll defensively stops any prior handle).
  </acceptance_criteria>
  <done>
    The idle poll lifecycle is wired: a single module-level handle, three new functions (start/stop/poll), one new hashchange listener and one optional visibilitychange listener — all keyed off plan 04-03's loadBlock + timelineExpanded + renderTimelineEntries contract. Poll cadence is 60s; visibility-aware; hashchange-aware; respects expand-state. No Realtime. New timeline entries appear within ~60s while the operator is on the block page.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser ↔ Supabase PostgREST | Same as plan 04-03; the poll re-uses the existing timeline_entries query shape. |
| setInterval lifecycle ↔ browser tab lifecycle | The interval handle is held in a module-level var; if the operator closes/refreshes the tab, the browser GCs everything. The visibility/hashchange guards prevent runaway cost. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-05-01 | Denial of Service (operator-side) | runaway poll consuming bandwidth/CPU | mitigate | 60s cadence is a known-acceptable cost (≤1440 reads/day per tab). `document.visibilityState !== 'visible'` guard skips the query when the tab is backgrounded. `hashchange` listener calls `stopEvolutionPoll` when the operator navigates away from any `#/map/<slug>` route. `startEvolutionPoll` defensively calls `stopEvolutionPoll` first to prevent handle leaks if loadBlock fires twice. |
| T-04-05-02 | Denial of Service (DB-side) | many operator tabs polling simultaneously | accept | 60s cadence × 7 blocks × N tabs is still well under PostgREST capacity. RLS-bounded reads are cheap. If the operator opens 10+ block tabs and leaves them visible, ~10 reads/minute per block — still trivial. |
| T-04-05-03 | Tampering (XSS) | poll re-emits timeline-entry HTML via wholesale innerHTML replacement | mitigate | The same renderTimelineEntries function from plan 04-03 is invoked — escapeHtml on every DB string, rel=noopener noreferrer on source anchors. The poll changes nothing about the markup-emission contract; only the trigger changes. |
| T-04-05-04 | Tampering (race condition) | poll fires AFTER the operator navigated to a different block but BEFORE startEvolutionPoll for the new block stopped the old handle | mitigate | pollEvolution begins with `if (!window.location.hash.startsWith('#/map/' + slug)) return;` — even if the old interval tick is in-flight, it short-circuits when the hash no longer matches its captured slug. startEvolutionPoll's `stopEvolutionPoll()` defensive call closes the window further. |
</threat_model>

<verification>
After this plan deploys (via plan 04-06):
- Visit any block page. Watch DevTools Network for ≥120 seconds. Confirm exactly two GETs to `timeline_entries` fire (initial load + one 60s tick). Confirm both have the same query shape — `eq.block_slug.<slug>&order=event_date.desc&limit=30`.
- Insert a new timeline_entries row via SQL while the page is open. Within ≤60s the row appears at the top of Evolution.
- Click "Show all" (if present); confirm subsequent ticks omit `limit=30` (URL changes accordingly).
- Switch tabs for 5 minutes. Confirm no timeline queries fire while hidden. Return — confirm an immediate query + resumption of the 60s cadence.
- Navigate to `#/map`. Confirm timeline queries stop entirely.
</verification>

<success_criteria>
- RNDR-06 satisfied: new timeline_entries rows appear in the Evolution section within ~60 seconds while the operator is on the block page.
- D-05/D-06/D-07/D-11 all honored: no Realtime, timeline-only, 60s + visibility-aware + hashchange-aware, expand-state respected.
- File still parseable; no template literals; the existing hashchange routing listener still works (we added a sibling listener, not a replacement).
</success_criteria>

<output>
After completing the task, create `.planning/phases/04-hub-block-and-status-renderer/04-05-SUMMARY.md` summarizing:
- Whether the optional visibilitychange immediate-refresh listener was included
- The final structure of pollEvolution (specifically how it handles the Show-all button presence after a poll tick — append, remove, or no-op)
- Any race conditions identified during implementation (the `#/map/<slug>` prefix re-check guard inside pollEvolution is the main one)
- The git commit hash
</output>
