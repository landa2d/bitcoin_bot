---
phase: 01-render-stack-diagnostic
requirements: [DIAG-01, DIAG-02, DIAG-03, DIAG-04]
status: complete
---

# Phase 1 — Render-Stack Findings

This is the canonical Phase 1 findings document for the Render-Stack Diagnostic
phase. It informs `.planning/docs/economy-map-build-spec-v2.md` §6 (Renderer
contract) **by reference** — per CONTEXT.md D-01, the build spec is annotated to
cite this file rather than absorbing its contents. The work is **describe-only**:
no live probes were run, no shell commands hit the network, no Supabase queries
were issued. Every claim below is derived from reading existing repo artifacts
(`docker/web/`, `scripts/deploy.sh`, `supabase/migrations/`, `.planning/docs/…`).

## 1. Stack (DIAG-01)

The `aiagentspulse.com` site is a **client-rendered single-page application**
served by Caddy from a baked-in static image. There is no server-side rendering
and no per-page template engine.

**Service / container.** The `web` service defined in `docker/docker-compose.yml`
is built from `docker/web/Dockerfile`. The Dockerfile base image is
`caddy:2-alpine`; the static site lives at `docker/web/site/` and is COPY'd into
the image at build time:

```dockerfile
FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile
COPY site/ /srv/
COPY entrypoint.sh /entrypoint.sh
```

(`docker/web/Dockerfile` lines 1–5.)

**Framework / web server.** Caddy 2 (alpine). The relevant `docker/web/Caddyfile`
directives:

```caddyfile
aiagentspulse.com {
    root * /srv
    file_server
    encode gzip

    # SPA fallback — serve index.html for all routes
    try_files {path} /index.html
    ...
}
```

(`docker/web/Caddyfile` lines 6–13.) A separate internal `:8080 /health` endpoint
exists for health checks (lines 1–4). The `try_files {path} /index.html` directive
is the **SPA fallback** — every URL that doesn't resolve to a static file is
served the shell document. Hash routes therefore never reach Caddy.

**HTML emission point.** The site has exactly **one HTML file**:
`docker/web/site/index.html` (77 lines). It is served by Caddy's `file_server`.
All page content is rendered into the DOM by `docker/web/site/app.js` after page
load — e.g. `document.getElementById('newsletter-list').innerHTML = html` (`app.js`
line 132). The `<script src="/app.js">` tag at the bottom of `index.html` (line 75)
is the SPA entry point. **There is no server-rendered HTML emission for content
pages** — the only HTML emitted by the server is the static shell.

**Runtime config injection.** `docker/web/entrypoint.sh` performs two `sed`
substitutions on `/srv/app.js` at container start, then starts Caddy:

```sh
sed -i "s|__SUPABASE_URL__|${SUPABASE_URL}|g" /srv/app.js
sed -i "s|__SUPABASE_ANON_KEY__|${SUPABASE_ANON_KEY}|g" /srv/app.js

# Start Caddy
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
```

(`docker/web/entrypoint.sh` lines 3–7.) The placeholders `__SUPABASE_URL__` and
`__SUPABASE_ANON_KEY__` appear verbatim in `docker/web/site/app.js` lines 4–5
and are replaced with real env values at container boot.

**Client-side data path.** The shell loads `@supabase/supabase-js@2` from CDN
(`index.html` line 73: `https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2`) and
constructs an anon-key client at module top:

```js
const sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
```

(`docker/web/site/app.js` line 7.) Every page view queries Supabase from the
browser at render time — `loadList()` calls `sb.from('newsletters').select(...)`
on every navigation to `#/`, and `loadEdition(N)` calls
`sb.from('newsletters').select('*').eq('edition_number', N)` on every navigation
to `#/edition/N`. The `supabase-js` library is loaded from CDN, not bundled.

**Routing model.** `app.js` implements a **hash router**:

```js
function getRoute() {
    var hash = window.location.hash || '#/';
    if (hash.startsWith('#/edition/')) {
        return { view: 'reader', edition: parseInt(hash.split('/')[2]) };
    }
    if (hash.startsWith('#/unsubscribe')) {
        return { view: 'unsubscribe' };
    }
    return { view: 'list' };
}
```

(`app.js` lines 89–98.) The dispatcher `route()` (lines 299–307) and
`window.addEventListener('hashchange', route)` (line 314) re-dispatch on every
hash change. Combined with Caddy's `try_files {path} /index.html`, deep hash
URLs like `aiagentspulse.com/#/edition/34` deliver `index.html` unconditionally
and the hash is processed client-side — Caddy never sees the hash.

## 2. Publish Mechanism (DIAG-02)

The most important conceptual finding of this phase: there is **no per-page publish step**. New edition "pages" are not files emitted to disk by any
process; they are **rows inserted/updated in the Supabase `newsletters` table
with `status='published'` (or `'preview'`)**. The SPA reads those rows on every
page load and renders whatever it finds. The publish-path question for a new
edition page therefore reduces to "what writes to the `newsletters` table?" —
the newsletter pipeline (`docker/newsletter/`), not anything in `docker/web/`.

**The discovery query.** `loadList()` in `docker/web/site/app.js` is the entire
"publish discovery" path:

```js
var { data, error } = await sb
    .from('newsletters')
    .select('*')
    .in('status', ['published', 'preview'])
    .order('edition_number', { ascending: false });
```

(`app.js` lines 137–141.) `loadEdition(N)` is the per-edition read (`app.js`
lines 176–181) — same table, same anon-key client, filtered by
`edition_number`.

**File write path:** none. The act of publishing an edition is a DB write
performed by the newsletter pipeline, not a write to `docker/web/site/`. The
static SPA shell (`index.html`, `app.js`, `style-shared.css`) is baked into the
container image at build time and only changes when SPA code itself is modified.

**Cache invalidation:** none required by the SPA pattern. The Caddyfile contains
no `Cache-Control` directives (`docker/web/Caddyfile` lines 1–21, full file); the
client fetches Supabase data on every navigation. Supabase / network-layer
caching exists but is out-of-scope here and does not depend on a publish step.

**Deploy trigger (SPA shell changes only).** `scripts/deploy.sh` detects
modifications under `docker/web/` via its service-map rule:

```bash
map_service 'docker/web/'                            web
```

(`scripts/deploy.sh` line 101.) When triggered, the script SSHes to the Hetzner
host and runs:

```bash
ssh_cmd "cd $REMOTE_DIR/docker && docker compose build $SERVICES && docker compose up -d $SERVICES"
```

(`scripts/deploy.sh` line 141.) For the `web` service specifically, the
substituted commands are `docker compose build web` followed by
`docker compose up -d web`. This rebuilds the Caddy image with the new
`site/` baked in and restarts the `web` container. **This deploy trigger is
only relevant when the SPA shell itself changes — publishing a new edition to
the live site requires zero deploy actions.**

**Implication for Phase 9 (`/map-approve`).** The autonomy-boundary "publish"
action for a block body is not a file write or container rebuild; it is the
atomic Postgres transaction defined in build spec v2 §3.2 (flip
`block_body_versions.status` to `published`, supersede prior, update
`blocks.current_body_version_id` and `blocks.maturity`). The next SPA page load
reads the new state. This is the same architectural shape as edition
publishing — DB write upstream, SPA read on next load downstream — applied to a
different table.

## 3. Block-Page Publish Path Recommendation (DIAG-03)

**Recommendation: the existing publish path is fully reusable for block, hub,
and status pages. No sibling route is needed.** Phase 4 (Renderer) extends the
existing SPA in-place.

### Named path

- **New hash routes** added to the existing `docker/web/site/app.js` hash router:
  `#/map`, `#/map/<slug>`, `#/status`. (Build spec §6 offers `/` or `/map` as
  the hub URL — Phase 4 picks one.) The pattern is identical to the existing
  `#/edition/N` and `#/unsubscribe` routes — a new `if (hash.startsWith('#/map'))`
  branch in `getRoute()` and a corresponding case in `route()`.
- **Queries** against the `economy_map` schema via the **same** `supabase-js`
  anon-key client that is already wired (`sb` at `app.js` line 7). The library
  exposes `.schema('economy_map')` for schema-isolated calls
  (e.g. `sb.schema('economy_map').from('blocks').select(...)`); under the hood
  this sets the `Accept-Profile: economy_map` header on PostgREST requests —
  the supabase-js equivalent of the direct-PostgREST pattern mandated by
  `CLAUDE.md` / `PROJECT.md` for backend services.
- **No Caddy changes.** `try_files {path} /index.html` (`Caddyfile` line 12)
  already routes every URL to the SPA shell; hash routes are processed
  client-side and never reach Caddy. The CSP `connect-src https://*.supabase.co`
  already permits the supabase-js network traffic (same host, regardless of
  `Accept-Profile`).
- **No new container.** The existing `web` service serves the new pages.
- **No new deploy path.** `scripts/deploy.sh`'s existing `map_service
  'docker/web/' web` rule (line 101) already handles SPA-shell changes when
  Phase 4 modifies `app.js` / `index.html`.

### Rationale

- The SPA-only pattern means the "publish step" is already a DB write (per §2).
  Block bodies become rows in `economy_map.block_body_versions`; the SPA reads
  them on the next page load. This is **identical** to how editions work — same
  architectural shape, different table.
- A sibling route (e.g., a separate Caddy site, a server-rendered service, or
  static-file generation per slug) would introduce new infrastructure without
  solving anything the SPA pattern doesn't already solve.
- Build spec §8 ("substance over design") explicitly defers crawlable URLs,
  SEO, and SSR to v2. Hash-routed deep links are the v1-appropriate choice.

### Out of scope for this recommendation

Per CONTEXT.md D-06, the following are **Phase 4's** decisions, not Phase 1's:

- Exact code changes to `app.js` (new view functions, new `getRoute()` branches,
  new `route()` cases).
- DOM container structure in `index.html` (new view containers for map / block /
  status views).
- CSS / token integration (depends on Phase 3 — Design Tokens — landing first).
- Whether to use Supabase Realtime subscriptions for instant Evolution re-render
  vs. relying on next-navigation reads.

Phase 4's `discuss-phase` and `plan-phase` own those choices. This finding names
the path; it does not sketch the implementation.

## 4. Known Unknowns (flagged for Phase 2)

This phase is describe-only (D-03). The following items are **flagged**, not
validated — Phase 2 (`economy_map` Schema) owns the live validation when it
lands the real schema and seed data. No live commands or scripts are proposed
here; the build spec also defers all live-behavior checks to that phase.

### 4.1 Anon-role read of non-public schema via Accept-Profile

The supabase-js client supports `.schema('<name>').from(...)` which sets the
`Accept-Profile: <name>` header on the underlying PostgREST request. The build
spec (§3 of `economy-map-build-spec-v2.md`) asserts that the anon role can read
`economy_map` tables via this mechanism, mirroring the `eu_ai_act` pattern.
**Live behavior with the browser anon key is unverified.** **Phase 2 will
validate** — once the schema, RLS policies, and seed rows exist, a browser
session against the deployed `web` container will exercise the read path and
confirm rows come back (and that RLS allows what's intended).

### 4.2 Caddy CSP coverage for schema-isolated PostgREST

The existing Caddyfile CSP (`docker/web/Caddyfile` line 19) includes:

```
connect-src https://*.supabase.co
```

PostgREST calls to `economy_map` go to the same `*.supabase.co` host that
existing `newsletters` queries hit — `Accept-Profile` is a request header, not a
new origin — so the CSP **likely** already covers the schema-isolated calls.
Unverified from the browser context. **Phase 2 will validate** when block-page
renderer probes are run end-to-end against a live `economy_map` table.

### 4.3 Hash-route deep-link / SEO behavior for `#/map/<slug>`

Hash-routed deep links such as `aiagentspulse.com/#/map/payments-settlement`
work for the SPA — the hash drives `getRoute()` and the page renders — but they
are not crawlable by search engines and they do not produce rich-link previews
(the hash never reaches the server, so server-rendered metadata is the shell's
metadata regardless of slug). Acceptable for v1 per build spec §8 ("substance
over design"). **Flagged for Phase 4** so the renderer planner is aware;
**out of v1 scope** per the deferred-ideas section of CONTEXT.md — revisit only
if a v2 design pass requires crawlability or share-card fidelity.

### 4.4 In-tree precedent for the `eu_ai_act` isolation pattern

The build spec, `.planning/PROJECT.md`, and `CLAUDE.md` all reference
`eu_ai_act` as the **precedent** for schema isolation via `Accept-Profile`.
A scan of `supabase/migrations/` (files `001_initial_schema.sql` through
`032_prepass_tracking_justification_and_staleness.sql` as of 2026-05-26)
shows **no `eu_ai_act` migration in this repo**. The pattern exists in
*specification form* (CLAUDE.md / PROJECT.md / build spec) but it has not yet
landed as actual SQL in `supabase/migrations/`. **Phase 2 will establish the
in-tree precedent** when it adds the `economy_map` migration — there is no prior
isolated-schema migration to copy from; the migration itself becomes the first
canonical example.

### 4.5 Supabase exposed-schemas allowlist (Phase 2 prerequisite)

Per CONTEXT.md §"Specific Ideas", a non-`public` Postgres schema must be on
Supabase's PostgREST **exposed-schemas allowlist** for browser-side reads to
succeed even with a valid `Accept-Profile` header. This is a one-time settings
change in the Supabase Dashboard (project ref `zxzaaqfowtqvmsbitqpu` —
Settings → API → Exposed schemas), not a SQL migration. **Phase 2 prerequisite,
not a Phase 1 blocker** — flagged here so it isn't forgotten when Phase 2 lands
the schema and tries to read it from the browser for the first time.
