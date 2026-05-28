---
id: cr-01-source-url-scheme-validation
created: 2026-05-28
severity: critical
source: 04-REVIEW.md (CR-01)
resolves_phase: 5
tags: [security, xss, frontend]
---

# CR-01: Validate timeline_entries.source_url scheme before rendering

**Where:** `docker/web/site/app.js` — `renderTimelineEntries()` (~lines 561, 567)

**Problem:** `timeline_entries.source_url` is rendered into an anchor `href` (and a
`data-source` attribute) with only `escapeHtml()`. HTML-entity escaping does NOT
block `javascript:` or `data:text/html` URIs, so such a URL executes on click.
Unlike `body_md` (gated by the Phase 9 operator publish gate), timeline rows are
surfaced live via the 60s idle poll and are NOT gated — so the "everything is
escaped" invariant does not hold for this sink.

**Why not yet exploitable:** Phase 4 inserts no untrusted timeline data; the only
rows are operator/test rows with `https://` URLs. The vector becomes live once
Phase 5 intake writes timeline entries from external sources.

**Fix:** Add a `safeHttpUrl(url)` helper that returns the URL only when it matches
`^https?://`, else returns null; in `renderTimelineEntries()` omit the anchor (and
`data-source`) when the URL fails validation. Also correct the inline comment that
currently asserts `source_url` is "escaped" (it overstates the guarantee).

**Deadline:** Resolve before Phase 5 (intake) ships. Re-run `/gsd-code-review 04`
after the fix to confirm CR-01 clears, then redeploy the web container.
