---
phase: 04-hub-block-and-status-renderer
plan: 06
verified_on: 2026-05-28
deployer: AgentPulse <landa2d@gmail.com>
deploy_commit: e5e31d5162a04d8e3c1f664ef5c4f37b3847538a
status: verified
---

# Phase 4 Deploy & Verification Log

Verification of all five Phase 4 ROADMAP Success Criteria against the live site
`https://aiagentspulse.com` after deploying the Wave 1–5 SPA renderers.

## Deploy

**Method (deviation from plan — see note):** scoped rsync of `docker/web/` only,
followed by a web-container rebuild/restart. The plan prescribed
`scripts/deploy.sh --force-rebuild web`, but a dry-run revealed production had
drifted far behind local `main`: the script's directory-level rsync (`--delete
--checksum` over `docker/`, `config/`, `skills/`, `templates/`) would have
deleted `llm-proxy/governance_config.json`, pushed stray artifacts
(`docker-compose.yml.save`, multiple `__pycache__/*.pyc`), synced unrelated WIP
(`processor`, `gato_brain`, `llm-proxy`, `newsletter`, `research`), and — via the
`docker-compose.yml` delta — restarted all 7 services. Operator chose a scoped
web-only deploy to honor RNDR-05 ("zero new infrastructure") without that blast
radius.

Commands run:
```
rsync -rvz --checksum docker/web/  root@<host>:/opt/bitcoin_bot/docker/web/
ssh root@<host> 'cd /opt/bitcoin_bot/docker && docker compose build web && docker compose up -d web'
```
Files synced: `Caddyfile`, `site/app.js`, `site/index.html`, `site/style-map.css`
(new), `site/style-shared.css`, `site/tokens-preview.html` (new) — the Phase 3 +
Phase 4 web surface. No other service touched.

Deploy commit (head of `main` at deploy time): `e5e31d5`.

**PASS evidence:**
- `curl -sI https://aiagentspulse.com/app.js` → `HTTP/2 200`
- `curl -s https://aiagentspulse.com/app.js | grep -c HUB_STORYLINE` → `4` (the
  Wave 1 constant is in the served bundle)
- In-container `/srv/{app.js,index.html,style-map.css,tokens-preview.html}` all
  timestamped at the rebuild.

### Prerequisite fix discovered during verification — economy_map schema exposure

The first live data query returned `PGRST106 — Invalid schema: economy_map`
(HTTP 406): production PostgREST exposed only `public, graphql_public, lab,
rivalscope`. The `economy_map` schema existed with seeded data (7 blocks, RLS
enabled + anon SELECT grants on all 3 tables) but was never added to the
PostgREST `db_schemas` list. Applied (operator-authorized, reversible) via
Supabase MCP:
```sql
ALTER ROLE authenticator SET pgrst.db_schemas =
  'public, graphql_public, lab, rivalscope, economy_map';
NOTIFY pgrst, 'reload schema';
NOTIFY pgrst, 'reload config';
```
RLS (verified enabled with policies on `blocks`, `timeline_entries`,
`block_body_versions`) gates anon reads, so exposure is safe.

## Pre-deploy checks (Task 1)

| # | Check | Result |
|---|-------|--------|
| 1 | JS parse (`node --check app.js`; `new Function` is a known false-positive on top-level `const`) | PASS |
| 2 | No stub bodies (`stub`/`TODO Phase 4`) remain | PASS |
| 3 | All six loaders/renderers present (loadHub/loadBlock/loadStatus + renderHub/renderBlock/renderStatus) | PASS |
| 4 | Idle poll wired (`startEvolutionPoll` + 2 `hashchange` listeners) | PASS |
| 5 | View containers `#map-view`/`#block-view`/`#status-view` present | PASS |
| 6 | Nine CSS layout selectors present in style-map.css | PASS |
| 7 | No redundant RLS `.eq('status','published')` on economy_map queries (only doc comments) | PASS |
| 8 | No Realtime (`sb.channel`) | PASS |
| 9 | No template literals (1 backtick = pre-existing regex char-class, not a template literal) | PASS |

## RNDR-01 Hub — `https://aiagentspulse.com/#/map`

Data path (machine-verified): one GET to
`/rest/v1/blocks?select=slug,tier,maturity,sort_order&order=sort_order.asc`
with `Accept-Profile: economy_map` → **HTTP 200**, 7 rows in sort order:
identity-trust (substrate, contested), memory-context (substrate, nascent),
payments-settlement (substrate, nascent), autonomy-control (behavior, nascent),
governance-accountability (behavior, nascent), psychology-disposition (behavior,
nascent), regulation-legal (frame, nascent).

Browser (operator-verified 2026-05-28): hero shows HUB_STORYLINE; SUBSTRATE /
BEHAVIOR / FRAME sections; 7 tiles in seed order; pills reflect maturity
(identity-trust 3/5 contested, rest 1/5 nascent) with tier accents; tile click →
`#/map/<slug>`; mode toggle hidden; "Map" nav link present. **PASS**

## RNDR-02 Block page — three representative slugs

Data path (machine-verified): `blocks?...slug=eq.<slug>&limit=1` +
`timeline_entries?...&order=event_date.desc&limit=30` → HTTP 200;
`block_body_versions` GET skipped when `current_body_version_id` is null.

| Slug (tier) | Title + inline pill | Tension card | Body | Evolution | Back-link | Result |
|-------------|--------------------|--------------|------|-----------|-----------|--------|
| identity-trust (substrate) | yes | hidden (placeholder) | hidden (no body) | heading shown | works | PASS |
| autonomy-control (behavior) | yes | hidden | hidden | heading shown | works | PASS |
| regulation-legal (frame) | yes | hidden | hidden | heading shown | works | PASS |

Operator-verified 2026-05-28. **PASS**

## RNDR-03 Status — `https://aiagentspulse.com/#/status`

Data path: one GET to `blocks?...order=sort_order.asc` (same shape as hub) →
HTTP 200. Browser (operator-verified): "Maturity Snapshot" hero; three tier
sections; 7 rows in same order as hub; each row pill + title + subtitle +
"never synthesized"; rows not clickable. **PASS**

## RNDR-04 Cross-surface (maturity mutation test)

Single-source-of-truth: hub and status read the identical `blocks` row.
- BEFORE: `memory-context` = `nascent` (1/5 on both surfaces).
- SQL: `UPDATE economy_map.blocks SET maturity='emerging' WHERE slug='memory-context';`
- AFTER: hub `#/map`, status `#/status`, and block `#/map/memory-context` all
  show `memory-context` at 2/5 (emerging) on reload.
- RESTORE: `UPDATE economy_map.blocks SET maturity='nascent' WHERE slug='memory-context';`
  → both surfaces return to 1/5.

Operator-verified 2026-05-28; production state restored. **PASS**

## RNDR-06 Live-data (timeline insert test) — `#/map/payments-settlement`

- INSERT: `INSERT INTO economy_map.timeline_entries (block_slug,event_date,what_shifted,why_it_mattered,source_url,tag_confidence) VALUES ('payments-settlement','2026-05-28','Phase 4 RNDR-06 verification entry','Confirms the 60s idle poll picks up new inserts.','https://example.com',1.0);`
- The Evolution section picked up the new entry within the 60-second visibility-aware idle poll, without navigating away.
- DELETE: `DELETE FROM economy_map.timeline_entries WHERE what_shifted='Phase 4 RNDR-06 verification entry';` → Evolution returned to empty state.

Operator-verified 2026-05-28; production timeline restored. **PASS**

## RNDR-05 Publish path

`docker ps` on the production host shows a single `agentpulse-web` container
(image `docker-web`), no sibling/new container. `scripts/deploy.sh`'s mechanism
(scoped web rebuild) was the only deploy action; no new infrastructure. Phase 1
FINDINGS §3 ("block pages reuse the existing publish path") satisfied. **PASS**

## Acceptance

All five Phase 4 ROADMAP Success Criteria verified on 2026-05-28 — deploy +
data-path machine-verified by the orchestrator; visual/interactive steps
(RNDR-01/02/03 rendering, RNDR-04 cross-surface, RNDR-06 60s live poll)
operator-verified ("all checks passed"). Production state restored after the
RNDR-04/06 mutation tests.

Signed off: AgentPulse <landa2d@gmail.com>, 2026-05-28.
