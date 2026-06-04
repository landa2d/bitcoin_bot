# Phase 1: Render-Stack Diagnostic - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Audit how `aiagentspulse.com` is served and how new content reaches production. Produce a findings report that establishes the publish path before any renderer code is written. **Zero application code changes; describe-only.** Output is a short document filed in this phase directory; downstream Phase 4 (Renderer) depends on its conclusions.

</domain>

<decisions>
## Implementation Decisions

### Spec source-of-truth
- **D-01:** Build spec v2 has been committed as `.planning/docs/economy-map-build-spec-v2.md`. Phase 1 findings update its Section 6 (Renderer contract) by reference — the findings doc cites the spec path and section number so future agents read the spec directly, not a duplicated copy.
- **D-02:** Open decisions in the spec's Section 10 were resolved during `/gsd-new-project` (negotiation = section-in-Payments, regulation = lightly-populated frame, thresholds = global N=5/T=30, evolution order = newest-first) and are annotated in the spec file. The spec is the canonical statement of intent; PROJECT.md and REQUIREMENTS.md are derivative.

### Audit scope
- **D-03:** **Describe-only — no live probes.** Phase 2 (`economy_map` Schema) will validate RLS / `Accept-Profile` / supabase-js anon-key behavior when it lands the real schema. Phase 1 stays purely diagnostic from code reading. Honors the spec's "Do not build anything" constraint strictly.
- **D-04:** Known unknowns that Phase 1 must **flag** (not validate): (a) whether the anon role can read a non-public schema via `Accept-Profile: economy_map` — `eu_ai_act` pattern exists in code but live behavior with anon key is unverified; (b) whether Caddy's existing CSP (`connect-src: 'self' https://*.supabase.co`) covers schema-isolated PostgREST calls — likely yes since same host; (c) hash-route deep-link/SEO behavior for `#/map/<slug>` — acceptable for an SPA but should be called out for Phase 4.

### Recommendation depth
- **D-05:** Bare recommendation: the existing publish path is fully reusable for block pages. The "publish path" for newsletter editions is **insert/update rows in Supabase → SPA reads on next page load** — there is no traditional publish step. Block pages reuse this verbatim via new hash routes in `docker/web/site/app.js`.
- **D-06:** Do **not** include a Phase 4 file-diff sketch in Phase 1 findings — that's Phase 4's planning work. Phase 1 names the **path** (hash routes added to existing `app.js`, queries against `economy_map` via supabase-js with `Accept-Profile`, no sibling Caddy route needed) and **flags the known unknowns** above. Phase 4 owns the design.

### Output location
- **D-07:** Findings live as `01-FINDINGS.md` inside this phase directory (`.planning/phases/01-render-stack-diagnostic/`). The findings doc references `.planning/docs/economy-map-build-spec-v2.md` Section 6 explicitly so downstream agents know where to read the source-of-truth contract.

### Claude's Discretion
- Findings report format (Markdown sections, headings, ordering) — pick what's clearest. Suggest mirroring the build spec's Section 6 structure (Hub / Block / Status / Re-render trigger) plus a "Known unknowns" appendix and an "Implications for Phase 4" section that bridges to the renderer phase without prescribing implementation.
- Whether to include screenshots or diagrams of the existing stack — optional; only if they materially help downstream agents.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Build spec (source of truth for the milestone)
- `.planning/docs/economy-map-build-spec-v2.md` — Full v2 build handoff. Section 2 defines Phase 0 (this phase). Section 6 (Renderer contract) is what Phase 1's findings inform. Section 10 contains resolved open decisions.
- `.planning/docs/economy-map-build-spec-v2.md` §2 — Phase 0 prompt: what to inspect, what to report, "do not build anything" constraint.
- `.planning/docs/economy-map-build-spec-v2.md` §6 — Renderer contract assumed by Phase 4; Phase 1 findings must confirm or revise the assumption that block pages reuse the existing publish path.

### Project & milestone context
- `.planning/PROJECT.md` — AgentPulse + milestone framing. Constraints section pins LLM-proxy mandate, schema isolation via PostgREST, autonomy boundary.
- `.planning/REQUIREMENTS.md` §"Diagnostic (Phase 0 — no code changes)" — DIAG-01..04 are the formal requirements for this phase.
- `.planning/ROADMAP.md` §"Phase 1: Render-Stack Diagnostic" — Success criteria (5 items), `UI hint: yes`.

### Existing codebase (the stack being audited)
- `docker/web/Dockerfile` — Caddy 2-alpine base image; baked-in static site (`COPY site/ /srv/`).
- `docker/web/Caddyfile` — SPA fallback (`try_files {path} /index.html`); CSP headers (`connect-src: 'self' https://*.supabase.co`); domain binding (`aiagentspulse.com`).
- `docker/web/entrypoint.sh` — Runtime injection of `SUPABASE_URL` and `SUPABASE_ANON_KEY` placeholders into `app.js` via sed.
- `docker/web/site/app.js` (314 lines) — The SPA. Hash router (`getRoute`, `route`, `window.addEventListener('hashchange', route)`), supabase-js client, edition list + reader views.
- `docker/web/site/index.html` (77 lines) — Shell; loads `style-shared.css` and `app.js`. All content rendered into DOM by JS.
- `scripts/deploy.sh` — Rsync-to-Hetzner deploy; auto-detects `docker/web/` changes and rebuilds the `web` service.
- `.planning/codebase/INTEGRATIONS.md` §"Deployment Target" — Confirms domain + Caddy reverse proxy + port mapping.
- `.planning/codebase/ARCHITECTURE.md` §"User-Facing Layer" — Web service position in the broader system.

### Reference patterns (for the spec's Accept-Profile assumption)
- `supabase/migrations/` — 27 migrations; look for `eu_ai_act` schema migration as the reference isolation pattern referenced in the build spec.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`docker/web/site/app.js` hash router** — Already implements `#/edition/N` and `#/unsubscribe` patterns. Adding `#/map`, `#/map/<slug>`, `#/status` is a localized extension, not a new pattern.
- **`supabase-js` client + anon key + Caddy CSP** — Already wired and proven for `public` schema queries. The unknown is whether the `Accept-Profile` header pattern (used by services like `eu_ai_act`) works from the browser context with the anon role.
- **`scripts/deploy.sh` auto-rebuild logic** — Already detects `docker/web/` changes and rebuilds + restarts the web service. Phase 4 deploys won't need any deploy-script changes.

### Established Patterns
- **SPA with live-data, no SSR** — The entire site is a single HTML shell + JS that queries Supabase on page load. There is no per-page-publish step. This pattern is the publish-path answer.
- **Schema isolation via `Accept-Profile` header** — Established for `eu_ai_act` schema; `economy_map` will follow. Direct PostgREST is mandated (not supabase-py `.in_()`) per PROJECT.md constraints — but the browser uses `supabase-js`, which sets `Accept-Profile` via its `.schema()` method.
- **Caddy SPA fallback** — `try_files {path} /index.html` means deep hash routes like `aiagentspulse.com/#/map/payments-settlement` work out of the box.

### Integration Points
- **`app.js` hash router** — Phase 4 adds `if (hash.startsWith('#/map'))` branches in `getRoute()` and case handlers in `route()`. No file moves, no new Caddy routes.
- **`supabase-js` client (`sb = window.supabase.createClient(...)`)** — Phase 4 uses `sb.schema('economy_map').from('blocks').select(...)` style calls. Requires the schema to be on Supabase's exposed-schemas allowlist (a settings change that lands in Phase 2).
- **`index.html`** — Will need new `<div id="map-view">`, `<div id="block-view">`, `<div id="status-view">` containers alongside the existing `#list-view` / `#reader-view`. Phase 4's concern, not Phase 1's.

</code_context>

<specifics>
## Specific Ideas

- The findings doc should make explicit that **there is no "publish page" step** — this is the most important conceptual finding for Phase 4 (renderer) and Phase 9 (gated publishing). The autonomy-boundary's "publish" action for block bodies maps to a DB transaction, not a file write or container rebuild.
- The findings doc should explicitly note that **Supabase exposed-schemas allowlist** is a Phase 2 prerequisite — without it, even a valid `Accept-Profile: economy_map` header returns nothing. Surface this as a Phase 2 dependency, not a Phase 1 blocker.

</specifics>

<deferred>
## Deferred Ideas

- **Live probes** (browser CSP test, anon-key read against `eu_ai_act`, throwaway `economy_map_probe` schema) — explicitly skipped in Phase 1. Phase 2 will validate the full read path when it lands the real schema and seed data; if Phase 2's schema work surfaces unexpected anon-role / RLS issues, Phase 2's discuss-phase should re-open these.
- **Deep-link / SEO improvements for block pages** — hash routes (`#/map/<slug>`) work for an SPA but are not crawlable or rich-link-friendly. Out of v1; revisit if/when block pages need search-engine visibility (a v2 design pass concern, paired with `DSGN-*` items in REQUIREMENTS.md v2).
- **Recommendation for prerendering or static-route generation** — Out of scope. The SPA-only pattern is the chosen v1 path; static-route generation (e.g., emitting `/map/payments-settlement/index.html` at build time) is a v2 optimization, not a v1 requirement.

</deferred>

---

*Phase: 1-render-stack-diagnostic*
*Context gathered: 2026-05-26*
