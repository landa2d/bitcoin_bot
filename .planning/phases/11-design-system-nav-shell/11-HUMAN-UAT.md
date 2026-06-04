---
status: partial
phase: 11-design-system-nav-shell
source: [11-VERIFICATION.md]
started: 2026-06-04T22:10:00Z
updated: 2026-06-04T22:10:00Z
---

## Current Test

[awaiting human testing]

## How to test locally (no deploy — D-01 batch-deploy)

IMPORTANT: do NOT serve `docker/web/site/` raw — `app.js` hardcodes
`__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` placeholders that `docker/web/entrypoint.sh`
substitutes at container start. Served raw, `createClient('__SUPABASE_URL__', …)` throws at
module load and the whole SPA goes dead (every click inert, no tab highlight). Substitute first:

```bash
# build a substituted preview copy (mirrors entrypoint.sh) and serve it
rm -rf /tmp/ap-preview && mkdir -p /tmp/ap-preview
cp docker/web/site/*.html docker/web/site/*.css docker/web/site/*.js /tmp/ap-preview/
SUPABASE_URL=$(grep -E '^SUPABASE_URL=' config/.env | cut -d= -f2- | tr -d '"'"'"'"')
SUPABASE_ANON_KEY=$(grep -E '^SUPABASE_ANON_KEY=' config/.env | cut -d= -f2- | tr -d '"'"'"'"')
sed -i "s|__SUPABASE_URL__|${SUPABASE_URL}|g; s|__SUPABASE_ANON_KEY__|${SUPABASE_ANON_KEY}|g" /tmp/ap-preview/app.js
cd /tmp/ap-preview && python3 -m http.server 8090   # → http://127.0.0.1:8090/
```

(A valid stub URL like `https://stub.supabase.co` also stops the crash — the shell renders,
data views just stay empty, which is sufficient to verify the Phase 11 nav/palette/typography.)

## Tests

### 1. Light palette + serif body + sticky header (COLOR-01, TYPE-01)
expected: At `#/`, page background is warm off-white (#faf8f5); body text renders in a serif (Source Serif 4); no dark/black background anywhere; the sticky header is present at the top.
result: [pending]

### 2. Route-derived active tab (NAV-02)
expected: On `#/` and `#/edition/1` the **Newsletter** tab is highlighted (accent-soft bg, accent-ink text). On `#/map` the **Agent Economy** tab is highlighted. On `#/about` no tab highlights and the list view shows (documented Phase 14 deferral — not a bug).
result: [pending]

### 3. Back-controls on nested pages (NAV-03)
expected: `#/edition/1` shows `← Back to Newsletter` (top-left, IBM Plex Mono 12.5px); `#/map/<slug>` and `#/status` show `← Back to the map`. Links are visually distinct from serif body text.
result: [pending]

### 4. Subscribe reuses scrollToSubscribe() (NAV-01)
expected: Clicking the header **Subscribe** button scrolls smoothly to the subscribe section. No new modal/page opens.
result: [pending]

### 5. Responsive nav wrap at ≤640px (D-03)
expected: At ≤640px viewport, brand (AGENTPULSE + dot) and Subscribe stay on the top row; the three tabs wrap to a full-width, horizontally-scrollable row below.
result: [pending]

### 6. Serif vs mono differentiation (TYPE-02/03)
expected: Headings/titles render serif; tab labels, SUBSCRIBE, and the back-links render IBM Plex Mono. (Article-body paragraphs still render mono — that is the known Phase 12 deferral, NOT a Phase 11 bug.)
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
