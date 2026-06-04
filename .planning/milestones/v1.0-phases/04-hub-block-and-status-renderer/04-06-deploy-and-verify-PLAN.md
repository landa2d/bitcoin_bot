---
phase: 04-hub-block-and-status-renderer
plan: 06
type: execute
wave: 6
depends_on:
  - 04-01
  - 04-02
  - 04-03
  - 04-04
  - 04-05
files_modified: []
autonomous: false
requirements:
  - RNDR-04
  - RNDR-05
tags:
  - deploy
  - verification
  - end-to-end
must_haves:
  truths:
    - "scripts/deploy.sh web rule rebuilds and restarts the web container after the Wave 1-3 changes — RNDR-05"
    - "https://aiagentspulse.com/#/map renders the live hub with seven block tiles read from Supabase production — RNDR-01 confirmed end-to-end"
    - "https://aiagentspulse.com/#/map/<slug> renders the live block page for every seeded slug — RNDR-02 confirmed end-to-end"
    - "https://aiagentspulse.com/#/status renders the live status snapshot — RNDR-03 confirmed end-to-end"
    - "Changing one block's blocks.maturity in production Supabase and reloading both #/map and #/status shows the new maturity reflected on BOTH surfaces — RNDR-04 cross-surface verification"
    - "Inserting a new timeline_entries row while the operator is on the affected block page causes the Evolution section to update within 60 seconds — RNDR-06 live-data verification"
    - "Block pages publish via the existing aiagentspulse.com path with zero new infrastructure — RNDR-05 confirmed via Phase 1 §3"
    - "After verification, the production state is restored: the test maturity change is reverted; the test timeline_entries row is left in place IF inserted by Phase 5 intake; manually-inserted test rows are deleted via the same SQL session that inserted them"
  artifacts:
    - path: .planning/phases/04-hub-block-and-status-renderer/04-06-VERIFY.md
      provides: "Verification log — every RNDR criterion check with timestamp, expected vs actual, pass/fail, screenshots or curl output paste"
      contains: "RNDR-01"
  key_links:
    - from: "scripts/deploy.sh web rule"
      to: "rebuilt web Docker container with the new app.js + index.html + style-map.css"
      via: "git push or local exec of the deploy script — same as Phase 3 plan 03-03"
      pattern: "scripts/deploy\\.sh"
    - from: "production aiagentspulse.com"
      to: "live economy_map data"
      via: "anon-key supabase-js .schema('economy_map') reads"
      pattern: "Accept-Profile: economy_map"
---

<objective>
Deploy the Wave 1-3 SPA changes to production via the existing `scripts/deploy.sh` web rule and verify every Phase 4 ROADMAP success criterion against the live site. This plan is the operator's final gate — it converts plan-level "the code is written" into roadmap-level "the operator can use it." No new code; only deployment, manual verification, and an artifact that documents the verification.

Purpose: Deliver RNDR-05 (block pages publish via existing aiagentspulse.com path) and the runtime half of RNDR-04 (hub and status maturity reflect the same DB source under mutation). All five ROADMAP Phase 4 success criteria are end-to-end checked here.

Output: `.planning/phases/04-hub-block-and-status-renderer/04-06-VERIFY.md` — verification log with timestamps, curl output, and pass/fail per criterion.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/04-hub-block-and-status-renderer/04-CONTEXT.md
@.planning/phases/01-render-stack-diagnostic/01-FINDINGS.md
@.planning/phases/03-design-tokens/03-03-PLAN.md
@scripts/deploy.sh
</context>

<tasks>

<task type="auto">
  <name>Task 1: Pre-deploy sanity check (build verifications, no unfinished stubs)</name>
  <files></files>
  <read_first>
    - docker/web/site/app.js (full read — verify all six renderers/loaders are wired and no stub bodies remain)
    - docker/web/site/index.html (verify view containers + nav link are present)
    - docker/web/site/style-map.css (verify the nine new selectors are present)
    - .planning/phases/04-hub-block-and-status-renderer/04-01-shared-infra-and-shell-PLAN.md acceptance_criteria
    - .planning/phases/04-hub-block-and-status-renderer/04-02-hub-renderer-PLAN.md acceptance_criteria
    - .planning/phases/04-hub-block-and-status-renderer/04-03-block-renderer-PLAN.md acceptance_criteria
    - .planning/phases/04-hub-block-and-status-renderer/04-04-status-renderer-PLAN.md acceptance_criteria
    - .planning/phases/04-hub-block-and-status-renderer/04-05-idle-poll-lifecycle-PLAN.md acceptance_criteria
  </read_first>
  <action>
    Run the following pre-deploy checks. If ANY fails, do NOT proceed to Task 2 — fix the failing plan first.

    1. JS parse: `node -e "new Function(require('fs').readFileSync('docker/web/site/app.js','utf8').replace(/window\\.supabase[^;]*;?/g,'').replace(/__SUPABASE_URL__/g,'x').replace(/__SUPABASE_ANON_KEY__/g,'x'))"` exits 0.
    2. No stub bodies remain: `grep -E "renderer in Wave 2 plan|stub|TODO" docker/web/site/app.js` returns zero matches (every stub was replaced in Wave 2).
    3. Required loaders/renderers exist: `grep -q "async function loadHub" && grep -q "async function loadBlock" && grep -q "async function loadStatus" && grep -q "function renderHub" && grep -q "function renderBlock" && grep -q "function renderStatus"` all exit 0.
    4. Idle poll wired: `grep -q "function startEvolutionPoll" && grep -q "startEvolutionPoll(slug);" && grep -c "addEventListener.'hashchange" docker/web/site/app.js` returns exactly 2.
    5. View containers present: `grep -q 'id="map-view"' docker/web/site/index.html && grep -q 'id="block-view"' docker/web/site/index.html && grep -q 'id="status-view"' docker/web/site/index.html`.
    6. CSS layout selectors present: `for s in .nav-map-link .tier-label .block-tile .block-header .block-tension .block-body .evolution .timeline-show-all .status-row; do grep -q "$s" docker/web/site/style-map.css || { echo "MISSING $s"; exit 1; }; done`.
    7. No defensive RLS-redundant filters: `! grep -E "\\.eq\\(['\\\"]status['\\\"], *['\\\"]published['\\\"]\\)" docker/web/site/app.js | grep -v "in\\(['\\\"]status['\\\"]" || echo OK`. (The existing `loadList` and `loadEdition` use `.in('status', [...])` on the `newsletters` table — those stay. Only economy_map queries should be free of redundant filters.)
    8. No Realtime: `! grep -q "sb.channel(" docker/web/site/app.js`.
    9. No template literals: `! grep -q '`' docker/web/site/app.js`.

    Record the output of each check in a scratch buffer; the verification artifact in Task 3 references this.
  </action>
  <verify>
    <automated>set -e; cd /root/bitcoin_bot; node -e "new Function(require('fs').readFileSync('docker/web/site/app.js','utf8').replace(/window\.supabase[^;]*;?/g,'').replace(/__SUPABASE_URL__/g,'x').replace(/__SUPABASE_ANON_KEY__/g,'x'))"; ! grep -E "renderer in Wave 2 plan|stub renderer|TODO Phase 4" docker/web/site/app.js; grep -q "async function loadHub" docker/web/site/app.js; grep -q "async function loadBlock" docker/web/site/app.js; grep -q "async function loadStatus" docker/web/site/app.js; grep -q "function renderHub" docker/web/site/app.js; grep -q "function renderBlock" docker/web/site/app.js; grep -q "function renderStatus" docker/web/site/app.js; grep -q "function startEvolutionPoll" docker/web/site/app.js; grep -q "startEvolutionPoll(slug);" docker/web/site/app.js; HC=$(grep -cE "addEventListener\(['\"]hashchange" docker/web/site/app.js); [ "$HC" = "2" ] || { echo "FAIL: expected 2 hashchange listeners, got $HC"; exit 1; }; grep -q 'id="map-view"' docker/web/site/index.html; grep -q 'id="block-view"' docker/web/site/index.html; grep -q 'id="status-view"' docker/web/site/index.html; for s in nav-map-link tier-label block-tile block-header block-tension block-body evolution timeline-show-all status-row; do grep -q "\.$s" docker/web/site/style-map.css || { echo "MISSING .$s"; exit 1; }; done; ! grep -q "sb.channel(" docker/web/site/app.js; ! grep -q '`' docker/web/site/app.js; echo OK</automated>
  </verify>
  <acceptance_criteria>
    - All nine pre-deploy checks pass (the single combined bash command exits 0).
    - If any check fails, the executor logs the failure and routes back to the responsible plan (01 for HTML/CSS issues; 02/03/04 for renderer issues; 05 for poll issues) for fix before resuming.
  </acceptance_criteria>
  <done>
    Pre-deploy sanity check completed. The combined verification command exits 0; no stub bodies remain; all loaders/renderers/poll wiring present; CSS selectors present; no Realtime; no template literals.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Deploy via scripts/deploy.sh web rule and operator-verify on live site</name>
  <read_first>
    - scripts/deploy.sh (full read — confirm the real CLI signature: `--dry-run`, `--force-rebuild [service]`, `-h|--help`; required env vars `DEPLOY_HOST` (no default), `DEPLOY_USER` (default root), `DEPLOY_DIR` (default /opt/bitcoin_bot), optional `DEPLOY_SSH_KEY`. The script rsyncs docker/, config/, skills/, templates/ then maps changed paths to services; `docker/web/` changes auto-flag the `web` service for rebuild. `--force-rebuild web` forces the rebuild even if rsync detects no changes.)
    - .planning/phases/01-render-stack-diagnostic/01-FINDINGS.md §3 (publish path confirmation)
    - .planning/phases/03-design-tokens/03-03-PLAN.md (Phase 3 deploy precedent — same script invocation pattern)
  </read_first>
  <what-built>
    Wave 1-3 introduces three new SPA routes (#/map, #/map/<slug>, #/status), a quiet "Map" nav link, and a 60-second visibility-aware idle poll on block pages. No new container, no new build step, no schema migration — the existing `scripts/deploy.sh --force-rebuild web` invocation rebuilds and restarts the `web` Docker container with the new app.js / index.html / style-map.css baked in. RNDR-05 ("block pages publish via existing aiagentspulse.com path") is satisfied by reusing this rule with zero changes.
  </what-built>
  <how-to-verify>
    Execute the deploy and then perform the five-criterion ROADMAP success verification on the live site. Each step has an explicit pass condition.

    Step 1 — Deploy.
      Run `DEPLOY_HOST=<production-host> bash /root/bitcoin_bot/scripts/deploy.sh --force-rebuild web` (the script parses `--dry-run`, `--force-rebuild [service]`, and `-h|--help` — there is no positional `web` argument; `--force-rebuild web` is the correct way to force a rebuild of just the web service). `DEPLOY_HOST` is mandatory (`set -euo pipefail` aborts without it); see `scripts/deploy.sh` lines 8-12 for the full env-var contract (`DEPLOY_USER` default root, `DEPLOY_DIR` default /opt/bitcoin_bot, optional `DEPLOY_SSH_KEY`). Phase 3 plan 03-03 used the same script. The script SSHes to the Hetzner host, pulls latest, rebuilds the web Docker image with the new site/ files, restarts the `web` container. Confirm the script exits 0. (If the project deploys via `git push` triggering a hook, the equivalent is `git push origin main` after committing the Wave 1-3 changes — adapt to the project's actual deploy idiom; Phase 1 §3 documents the exact path.)
      PASS: deploy script exits 0; `curl -sI https://aiagentspulse.com/app.js | head -1` returns `HTTP/2 200`; `curl -s https://aiagentspulse.com/app.js | head -50 | grep -q "const HUB_STORYLINE"` returns 0 (the new constant from plan 04-01 is in the served bundle).

    Step 2 — RNDR-01 hub verification (ROADMAP SC#1).
      Open https://aiagentspulse.com/#/map in a desktop browser. Observe:
        a) Hero shows the HUB_STORYLINE text (not the default site tagline).
        b) Below the hero, three tier-labeled sections render: SUBSTRATE / BEHAVIOR / FRAME.
        c) Seven block tiles render across the three sections in the order: identity-trust → memory-context → payments-settlement → autonomy-control → governance-accountability → psychology-disposition → regulation-legal (matches Phase 2 D-23 seed order).
        d) Each tile shows a title (Georgia 18px-ish), a subtitle (Courier 15px-ish), and a maturity pill on the right. All pills show 1/5 filled (nascent) with the tier accent color (teal for substrate, purple for behavior, coral for psychology, gray for regulation).
        e) Clicking a tile navigates to `#/map/<slug>` (verifiable in URL bar).
        f) The technical/strategic mode toggle is HIDDEN (D-03).
        g) The nav "Map" link is visible to the right of AGENTPULSE.
        h) DevTools Network: exactly one GET to `/rest/v1/blocks?select=...&order=sort_order.asc...` with response header `Content-Profile: economy_map` (server-side echo of Accept-Profile).
      PASS: all eight sub-criteria pass.

    Step 3 — RNDR-02 block-page verification (ROADMAP SC#2).
      Click the identity-trust tile (or visit https://aiagentspulse.com/#/map/identity-trust directly).
        a) Hero shows the block.title (e.g., "Identity & Trust").
        b) Title row in the main area shows the same title + an inline right-aligned 1/5 maturity pill.
        c) NO tension card (because seed value is the placeholder).
        d) NO body section (because current_body_version_id is null).
        e) Evolution section heading visible with the message "No timeline entries yet." (or 0 entries).
        f) The `← Map` back-link is visible and returns to the hub when clicked.
        g) Mode toggle still hidden.
        h) DevTools Network: exactly two GETs — `blocks?select=*&slug=eq.identity-trust&limit=1` and `timeline_entries?...&block_slug=eq.identity-trust&order=event_date.desc&limit=30`. NO `block_body_versions` query (the conditional was skipped because current_body_version_id is null). Repeat for each of the seven slugs.
      PASS: all eight sub-criteria pass for at least three slugs (one per tier).

    Step 4 — RNDR-03 status verification (ROADMAP SC#3, hub-side).
      Visit https://aiagentspulse.com/#/status.
        a) Hero shows "Maturity Snapshot" + "updated <today's date>".
        b) Three tier sections render with the same labels.
        c) Seven status rows render in the same order as the hub.
        d) Each row shows: maturity pill (left), block title, optional subtitle, "never synthesized" (right).
        e) Rows are NOT clickable (no hover cursor change, no href).
        f) DevTools Network: exactly one GET to `/rest/v1/blocks?...` — same query shape as the hub.
      PASS: all six sub-criteria pass.

    Step 5 — RNDR-04 cross-surface verification (ROADMAP SC#3, hub+status one-source-of-truth).
      Via Supabase MCP or the Supabase SQL Editor, run: `UPDATE economy_map.blocks SET maturity = 'emerging' WHERE slug = 'identity-trust';`. (Record the prior value for restoration.)
        a) Reload https://aiagentspulse.com/#/map. The identity-trust tile's pill now shows 2/5 filled.
        b) Reload https://aiagentspulse.com/#/status. The identity-trust row's pill also shows 2/5 filled.
        c) Visit https://aiagentspulse.com/#/map/identity-trust. The inline pill in the title row also shows 2/5 filled.
        d) Run `UPDATE economy_map.blocks SET maturity = 'nascent' WHERE slug = 'identity-trust';` (restore).
        e) Reload both surfaces — both return to 1/5.
      PASS: all five sub-criteria pass (proves RNDR-04 single source of truth).

    Step 6 — RNDR-06 live-data verification (ROADMAP SC#4).
      Keep https://aiagentspulse.com/#/map/payments-settlement open in the browser (focused, visible).
        a) Note the Evolution section state (likely "No timeline entries yet.").
        b) In Supabase SQL Editor, run: `INSERT INTO economy_map.timeline_entries (block_slug, event_date, what_shifted, why_it_mattered, source_url, tag_confidence) VALUES ('payments-settlement', '2026-05-27', 'Phase 4 RNDR-06 verification entry', 'Confirms the 60s idle poll picks up new inserts.', 'https://example.com', 1.0);`.
        c) Wait up to 60 seconds without touching the browser. Observe the Evolution section update to show the new entry: `2026-05-27 · Phase 4 RNDR-06 verification entry` on line 1, `Confirms the 60s idle poll picks up new inserts. source ↗` on line 2.
        d) Confirm in DevTools Network that the GET to `/rest/v1/timeline_entries?...` fired on a 60s cadence (initial load + ≥1 follow-up tick).
        e) Click the `source ↗` link. New tab opens to https://example.com (verify rel=noopener via `window.opener === null` in the new tab's DevTools console).
        f) Run `DELETE FROM economy_map.timeline_entries WHERE what_shifted = 'Phase 4 RNDR-06 verification entry';` (cleanup).
        g) Switch tabs for >60s. Return. Confirm the idle poll is still running and picks up the deletion (Evolution returns to "No timeline entries yet.").
      PASS: all seven sub-criteria pass (proves RNDR-06 live-data).

    Step 7 — RNDR-05 confirmation (ROADMAP SC#5).
      No new container appears in `docker ps` on the Hetzner host. The `web` container's image is rebuilt but its name/service are unchanged. `scripts/deploy.sh` was the only deploy invocation. Phase 1 FINDINGS §3's recommendation "block pages reuse the existing publish path" is satisfied — there is no sibling route.
      PASS: confirmed via `docker ps | grep web` showing one `web` container with no siblings.

    If ANY step fails, do NOT mark the checkpoint approved. Capture the failure mode, route back to the responsible plan (01-05), and resume from this checkpoint after a fix is shipped.
  </how-to-verify>
  <resume-signal>
    Type "approved" if all seven verification steps PASS and the production maturity change in Step 5 has been restored to 'nascent'. Otherwise describe which step failed and which plan needs revision.
  </resume-signal>
</task>

<task type="auto">
  <name>Task 3: Write the verification log artifact</name>
  <files>
    .planning/phases/04-hub-block-and-status-renderer/04-06-VERIFY.md
  </files>
  <read_first>
    - .planning/phases/04-hub-block-and-status-renderer/04-CONTEXT.md (re-confirm the requirements being verified)
    - .planning/ROADMAP.md (Phase 4 Success Criteria section — copy the five SCs verbatim into the artifact)
  </read_first>
  <action>
    Create `.planning/phases/04-hub-block-and-status-renderer/04-06-VERIFY.md` with the following structure:

    1. Frontmatter: phase, verified_on (today's date in ISO format), deployer (operator identity, e.g., the git author email).
    2. § "Deploy" — capture the exact deploy command run and the `curl` output proving the new app.js shipped (Step 1 from Task 2).
    3. § "Pre-deploy checks" — list the nine sanity checks from Task 1 and their pass/fail status.
    4. § "RNDR-01 Hub" — paste the verification result for each sub-criterion from Step 2; include the exact PostgREST URL captured from DevTools Network for the blocks query.
    5. § "RNDR-02 Block page" — for each of three representative slugs (one substrate, one behavior, one frame: identity-trust, autonomy-control, regulation-legal), record the pass/fail of each sub-criterion from Step 3.
    6. § "RNDR-03 Status" — record the pass/fail per sub-criterion from Step 4.
    7. § "RNDR-04 Cross-surface (maturity mutation test)" — record the BEFORE state, the SQL run, the AFTER state on both hub and status, and the RESTORE SQL. Include screenshots IF the operator captured them; otherwise describe observation in prose.
    8. § "RNDR-06 Live-data (timeline insert test)" — record the INSERT SQL, the wait duration before the page picked up the change, the DELETE SQL, and the post-delete state.
    9. § "RNDR-05 Publish path" — record `docker ps` output showing the single `web` container, plus a note that scripts/deploy.sh was the only deploy invocation.
    10. § "Acceptance" — a sign-off line: "All five Phase 4 ROADMAP Success Criteria verified on <date> at <time>." Followed by the operator's identity.

    Do NOT include any production secrets in the artifact (SUPABASE_ANON_KEY is in the URL query path of supabase-js — redact `apikey=` query params from any pasted URL).
  </action>
  <verify>
    <automated>set -e; F=.planning/phases/04-hub-block-and-status-renderer/04-06-VERIFY.md; test -f "$F"; for k in RNDR-01 RNDR-02 RNDR-03 RNDR-04 RNDR-05 RNDR-06; do grep -q "$k" "$F" || { echo "FAIL: $k not documented"; exit 1; }; done; ! grep -qE "apikey=[A-Za-z0-9._-]{20,}" "$F" || { echo "FAIL: anon key leaked in verify log"; exit 1; }; grep -q "All five Phase 4 ROADMAP Success Criteria verified" "$F"; echo OK</automated>
  </verify>
  <acceptance_criteria>
    - File `.planning/phases/04-hub-block-and-status-renderer/04-06-VERIFY.md` exists.
    - All six RNDR IDs (RNDR-01..RNDR-06) appear as section headings or labels in the file.
    - No anon-key leakage: zero occurrences of `apikey=<20+ char value>` (the supabase-js URL pattern).
    - The sign-off line appears with a date and operator identity.
    - All five ROADMAP Phase 4 Success Criteria are individually documented as PASS with evidence.
  </acceptance_criteria>
  <done>
    The verification log artifact is committed to the phase directory; every Phase 4 RNDR-* requirement is documented as verified with on-page evidence; production state is restored (maturity reverted, test timeline row deleted).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Operator ↔ Production Supabase | Maturity mutation (Step 5) and timeline insert (Step 6) use service-role access via Supabase SQL Editor — operator-scoped, NOT exposed to the browser. The browser still reads via anon-key + RLS. |
| scripts/deploy.sh ↔ Hetzner web container | SSH-based deploy; assumes the project's existing deploy hardening (key-based auth, no password). Out of scope to harden in Phase 4. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-06-01 | Tampering | scripts/deploy.sh executes arbitrary code on production via SSH | accept | Same risk envelope as Phase 3 plan 03-03 (TOKN-01..04 deploy). Project-level constraint; out of Phase 4 scope. |
| T-04-06-02 | Information Disclosure | verification log artifact accidentally captures the anon key from DevTools Network URLs | mitigate | Acceptance criterion forbids `apikey=` literal in the file (grep gate). Operator pastes only the path + query-keys, not values. |
| T-04-06-03 | Tampering | maturity mutation in Step 5 not restored — production state drifts | mitigate | Acceptance criterion explicitly requires `UPDATE blocks SET maturity = 'nascent' WHERE slug = 'identity-trust';` restoration; the operator captures the restore SQL in the verify log. The mutation is reversible (Phase 2 D-13: `blocks.maturity` is mutable; not append-only — so the restore writes a real value back, not a new row). |
| T-04-06-04 | Tampering | test timeline_entries row in Step 6 not deleted — production timeline gets polluted | mitigate | Acceptance criterion requires the DELETE SQL. Phase 2 D-04 says `timeline_entries` is append-only, but the append-only enforcement is on UPDATE — DELETE may still succeed depending on the trigger shape. If DELETE is also blocked (Phase 2 prerequisite verification), the executor uses an alternate "what_shifted" identifier (e.g., 'TEST-DELETEME-04-06') and routes a follow-up Phase 5 intake hardening to handle the test marker. PRE-CHECK: confirm DELETE is permitted via service-role before running the test; if blocked, abort Step 6 and treat it as a known-limitation note in the verify log (RNDR-06 then verified by waiting for the operator's next real intake event). |
</threat_model>

<verification>
This plan is itself a verification plan; its "verification" is the verify log artifact in Task 3.
</verification>

<success_criteria>
- scripts/deploy.sh web rule deploys cleanly; live site serves the new app.js with HUB_STORYLINE constant visible in the bundle.
- All five ROADMAP Phase 4 Success Criteria verified end-to-end on the live site.
- RNDR-04 cross-surface mutation test passes (hub + status both reflect a maturity change, then both reflect the restoration).
- RNDR-06 live-data insert test passes (Evolution updates within 60s).
- Verify log artifact committed; production state restored (maturity reverted, test timeline row deleted).
- No application-code changes shipped in this plan (files_modified is empty per the frontmatter).
</success_criteria>

<output>
The artifact created by Task 3 (`04-06-VERIFY.md`) IS the output. The phase SUMMARY after this plan completes summarizes:
- Deploy date/time
- Any deviation from expected behavior during verification (and the resolution)
- The git commit hash that the deploy shipped (the head of main at deploy time)
- Confirmation that all Phase 4 ROADMAP success criteria are verified
- The git commit hash for the VERIFY.md artifact
</output>
