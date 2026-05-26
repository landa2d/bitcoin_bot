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
