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

```bash
# from repo root, serve the static site and open in a browser:
cd docker/web/site && python3 -m http.server 8080
# then visit http://127.0.0.1:8080/  (and the #/… hash routes below)
```

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
