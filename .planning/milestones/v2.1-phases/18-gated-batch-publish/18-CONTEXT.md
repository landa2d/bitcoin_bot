# Phase 18: Gated Batch Publish - Context

**Gathered:** 2026-06-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Flip the Phase-16 loaded-but-unpublished content live: publish the hub `agent-economy` body + the 7 block bodies via the existing atomic `publish_block_version` RPC in ONE operator-approved batch, deploy the web change via the scoped `agentpulse-web` rebuild, and verify the live result programmatically. This is the last phase of the v2.1 milestone — the gated go-live the whole milestone built toward.

**In scope:** the batch publish of the 8 in-scope drafts; a small `app.js` change to render the published hub body as a framing article in prod; the scoped web deploy; programmatic post-publish verification.

**Out of scope (deferred — see `<deferred>`):** hub-article auto-evolution when a pillar changes (synthesis/pipeline capability); a UI to browse historical article versions; any net-new block content; any pipeline / proxy / agent-service change; publishing `regulation-legal` (stays deferred per P15-D-02).
</domain>

<decisions>
## Implementation Decisions

### Hub render in production (the one new `app.js` change)
- **D-01:** The hub `agent-economy` body IS published as part of the batch, and its **published** body renders as a first-class framing article at `#/map` in production (above the pillar cards). This requires ungating the hub *published*-body fetch: today `loadHub` only fetches the hub body behind `PREVIEW_ENABLED`, so prod shows the hardcoded `HUB_STORYLINE` constant even after publish. The change adds a prod path that fetches the hub row's `current_body_version_id` body (mirroring the block published-body path in `loadBlock`), independent of the flag. The preview *draft*-fetch added in Phase 17 stays flag-gated and unchanged.
- **D-02:** The published hub article renders **trimmed** — reuse Phase-17's `trimHubBody()` to drop the duplicative Tier-1/Tier-2 prose pillar-list, so the hub reads as a framing article (thesis + "How to read this map" + restated thesis) with the 7 pillar **cards** below as the deep-dive. Satisfies HUB-01 (pillar list appears once). `HUB_STORYLINE` remains the graceful **pre-publish fallback** (it is NOT deleted; shown when the hub has no published body yet).
- **D-03:** Operator framing (the WHY, for the planner): the hub article is the *primary* framing piece of the agent economy, with the 7 blocks as pillars to deep-dive into — not a table-of-contents intro. The trim-and-render approach above delivers the article-first framing within HUB-01.

### Deploy & verification
- **D-04:** **Deploy-first sequencing.** Ship the new `app.js` to prod via the scoped `agentpulse-web` rebuild FIRST — it is a visual no-op pre-publish (hub `current_body_version_id` is still NULL → `HUB_STORYLINE` fallback; the 5 unpublished blocks stay deferred; the 2 already-published blocks render their existing v2.0 bodies unchanged). Verify the deploy changed nothing visible, THEN run the gated publish batch as the single "go-live" that flips all 8 (hub article + 7 blocks) live at once. One clean cutover; the deploy is provably safe before any content goes live.
- **D-05:** **Post-publish verification is PROGRAMMATIC only.** An anon-key read (no service_role, no preview flag) confirms: all 8 in-scope bodies are `status='published'`, the hub renders its published article, every `#/map/<slug>` cross-link resolves against PUBLISHED content, and the published-block count goes from 2 → 8 (+ hub). No separate operator manual live walk-through — the human gate is (a) the operator's approval of the publish batch itself and (b) the Phase-17 preview click-through the operator already completed on content-identical drafts. The cross-link harness (`scripts/verify_economy_map_crosslinks.py`) can be reused/adapted to read the published set.

### Batch publish mechanism (Claude's Discretion — operator delegated)
- **D-06:** A standalone, operator-approved batch **script** (e.g. `scripts/publish_economy_map_batch.py`) — NOT a new gato_brain/Telegram command (a service change would violate the v2.1 "no agent-service changes" constraint; the Phase-16 loader set the standalone-script precedent). The script: (1) resolves the 8 open-draft `block_body_versions.id` for the hub `agent-economy` + the 7 blocks (explicitly NOT `regulation-legal`) via direct PostgREST + `Accept-Profile`; (2) prints a confirmation **manifest** (slug → version_id → proposed_maturity) for a SINGLE operator approval gate; (3) on approval loops the **existing** `economy_map.publish_block_version(p_version_id)` RPC (service_role) over each — reusing the sanctioned atomic publish path, never raw UPDATE. Idempotent: the RPC raises on a non-draft version, so a re-run treats already-published as skip/success.

### Ordering & failure recovery (Claude's Discretion — operator delegated)
- **D-07:** **Publish the 7 blocks FIRST, the hub LAST** — so when the hub framing article goes live, every pillar it references already resolves to a published page (no window where the hub is live but a pillar it frames is still deferred/body-less).
- **D-08:** **Fail-loud halt-and-report** — per-block publish is atomic (the RPC); if any one fails mid-batch, HALT immediately and report which succeeded/failed. Never continue silently to a partial-pass (MEMORY: fail_loud_governance). **Pre-flight:** before publishing anything, verify all 8 expected open drafts exist and resolve; if any is missing, halt before publishing. **Recovery:** fix the cause and re-run — the idempotent script completes a halted batch.

### Claude's Discretion
- The exact script CLI shape, the manifest print format, and how the single operator-approval gate is surfaced (orchestrator-in-chat approval, mirroring the Phase-16 migration-apply + loader pattern) are the planner's call within D-06.
- The precise `loadHub`/`renderHub` code shape for the published-body fetch (D-01/D-02) is the planner's call, provided the prod path renders the published hub article (trimmed) and keeps `HUB_STORYLINE` as the pre-publish fallback, and the deployed render stays a no-op until the hub body is published.
- Whether the programmatic verification (D-05) extends the existing harness or is a separate check is the planner's call.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Publish mechanism (the sanctioned path — reuse, do not rebuild)
- `supabase/migrations/038_publish_block_version_watermark.sql` — the `economy_map.publish_block_version(p_version_id uuid)` RPC: atomic draft→published flip, supersede prior published version for the block, point `blocks.current_body_version_id` at the new version, sync `blocks.maturity := proposed_maturity`, advance the watermark. service_role only; RAISEs on a non-draft version.
- `supabase/migrations/039_publish_block_version_watermark_null_guard.sql` — the null-guarded re-emit of the same RPC (the live version per 15-CONTRACT).
- `docker/gato_brain/gato_brain.py` §`/map-approve` (~:2048) + `_economy_map_rpc` (~:1613) — the existing owner-gated single-block publish path that calls `publish_block_version`. Reference for the RPC call shape; the batch script reuses the RPC directly (not this command).

### Contracts & requirements
- `.planning/REQUIREMENTS.md` — PUB-01 (the phase requirement + acceptance: hub renders at `#/map`, every published block renders with back arrow/title/subtitle/maturity pill/body).
- `.planning/phases/15-inventory-roster-reconciliation/15-CONTRACT.md` — the storage/serve contract: append-only `block_body_versions`, anon published-only RLS (`033:367-370`), `blocks.current_body_version_id` body pointer, the publish RPC = mig 039, the 3-tier model, `regulation-legal` deferred.
- `.planning/docs/EXECUTION_BRIEF.md` §3 (load → preview → publish sequencing) + §4 (standing constraints).

### Phase-17 preview artifacts (what was validated; what the deploy ships)
- `.planning/phases/17-cross-link-wiring-preview/17-CONTEXT.md` — D-06 (the in-bounds renderer set; the `renderHub` intent to replace `HUB_STORYLINE`), Flag F-2 (pills render `emerging`, not `building`).
- `.planning/phases/17-cross-link-wiring-preview/17-02-SUMMARY.md` — the operator-approved preview click-through (the human gate already completed on content-identical drafts); the preview URL gotcha (`?preview=1` before the `#`); DEF-17-01 (pre-existing service_role leak — out of scope, recommend rotation).
- `scripts/verify_economy_map_crosslinks.py` — the fail-loud cross-link harness (direct PostgREST + `Accept-Profile`, never `.in_()`); adapt/reuse for the D-05 published-content verification.
- `scripts/load_economy_map_content.py` — the Phase-16 standalone loader; the precedent + idiom (config/.env loading, PostgREST + Accept-Profile, validate-all-then-act, idempotent) the D-06 batch publish script mirrors.

### The web change site
- `docker/web/site/app.js` — `loadHub`/`renderHub` (the hub fetch + `trimHubBody` + `HUB_STORYLINE` fallback) and `loadBlock` (the published-body path to mirror for the hub). The Phase-17 preview path is dormant in prod (verified byte-for-byte no-op).
- `docker/web/entrypoint.sh` + `docker/web/Dockerfile` + `docker/docker-compose.yml` — the scoped `agentpulse-web` build/serve context for the deploy.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`economy_map.publish_block_version(uuid)` RPC** (mig 038/039) — the atomic per-block publish. The batch script loops it; no new publish logic.
- **`trimHubBody(md)`** (`app.js`) — already drops the duplicative pillar list; reuse verbatim for the published hub article render (D-02).
- **`loadBlock` published-body path** (`app.js` ~:611, fetch by `current_body_version_id`, ungated) — the exact pattern to mirror for the hub's published-body fetch (D-01).
- **`scripts/verify_economy_map_crosslinks.py`** — the fail-loud cross-link harness; adapt to assert against the PUBLISHED set for D-05.
- **`scripts/load_economy_map_content.py`** — the standalone-script + config/.env + PostgREST idiom the publish batch script mirrors.

### Established Patterns
- **Append-only + atomic publish RPC** — never raw UPDATE; the RPC supersedes prior versions and syncs maturity. Historical versions are retained automatically (relevant to the deferred version-viewer).
- **Scoped `agentpulse-web` rebuild + branch + `/diff` + approval** — the only sanctioned deploy path (MEMORY: deploy_scoped_and_approved; never a blind full `scripts/deploy.sh`).
- **`docker compose --build` is worktree-unsafe** (MEMORY: scoped_rebuild_worktree_unsafe) — the deploy task runs no-worktree/sequential from the main tree; the orchestrator owns any live DB action (MCP / Management API), not a worktree executor.
- **After publish, `blocks.maturity := proposed_maturity`** — so prod pills/bodies render correctly via the ungated published path; the Phase-17 preview-maturity fix was preview-only.

### Integration Points
- The publish batch writes only `economy_map` (via the RPC) — no schema/migration change (highest migration stays 043).
- The `app.js` hub-render change ships through the scoped web rebuild; deploy-first means it is a visual no-op until the publish batch runs.
- The 2 already-published blocks (`identity-trust`, `governance-accountability`) are SUPERSEDED to their new Phase-16 bodies by the RPC — the live site content for those two changes at publish.
</code_context>

<specifics>
## Specific Ideas

- **Operator's hub vision (the framing intent behind D-01..D-03):** "I want the hub body to be an actual article, not an intro to the 7 blocks — the most important article that frames the agent economy — and then users deep-dive into the different pillars." The published hub article is the primary surface; the 7 cards are the deep-dive. The "if a pillar evolves, the main article evolves" and "store/view historical versions" parts of the vision are deferred (below) — but the publish + article-first render in this phase is the foundation they build on.
</specifics>

<deferred>
## Deferred Ideas

- **Hub-article auto-evolution on pillar change** — re-synthesize the hub `agent-economy` article when a constituent block updates (a synthesis *dependency*). This is a pipeline/synthesis capability, and v2.1 explicitly excludes pipeline/agent-service changes → belongs in a future backend milestone (alongside the parked per-block tuning / synthesis-loop work).
- **Historical-version viewer on the site** — a frontend surface to browse past versions of the hub article (and blocks). The data already exists (append-only `block_body_versions` retains every version); only the viewer UI is new → future frontend phase.
- **Richer hub-article content authoring** — if the operator wants the hub body to read as a more substantial standalone article than `00-hub.md` currently provides, that is a content-authoring task (re-synthesis / canonical-body-rewrite), separate from the publish mechanics here.

### Reviewed Todos (not folded)
The `todo.match-phase 18` keyword matcher surfaced carried-forward backend v1.0 todos (analyst predictions title-expire bug; soft-cap allow-negative hardening; pay-endpoint 500 E2E; phase-05 intake review follow-ups; research trigger file permissions). All are **out of v2.1 content scope** (false keyword matches on generic terms like "phase"/"candidate"/"predictions") and stay parked in the ROADMAP backlog for a future backend milestone — not folded into Phase 18.

</deferred>

---

*Phase: 18-gated-batch-publish*
*Context gathered: 2026-06-09*
