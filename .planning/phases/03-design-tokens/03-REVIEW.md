---
phase: 03-design-tokens
reviewed: 2026-05-27T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - docker/web/site/style-map.css
  - docker/web/site/tokens-preview.html
  - docker/web/site/index.html
findings:
  critical: 0
  warning: 0
  info: 3
  total: 3
status: clean
---

# Phase 03: Code Review Report

**Reviewed:** 2026-05-27
**Depth:** standard
**Files Reviewed:** 3
**Status:** clean (no Critical or Warning findings; 3 Info-level observations)

## Summary

Phase 03 ships a CSS-and-static-HTML deliverable: `docker/web/site/style-map.css` (148 lines), `docker/web/site/tokens-preview.html` (169 lines), and a one-line `<link>` insertion in `docker/web/site/index.html`. All three were reviewed for selector-scope correctness, XSS surface, deployment soundness against the Caddy stack, and quality.

The code matches the plan precisely. Key correctness properties hold:

- **D-06 isolation:** Every rule in `style-map.css` is gated either by a `[data-accent="..."]` attribute selector (the eight `--accent-tier` resolution rules and `:not([data-source])` rule) or by class selectors (`.maturity-pill`, `.seg`, `.timeline-entry`, `.timeline-*`) that do not appear anywhere in `style-shared.css` or `index.html`. Grep against `style-shared.css` confirms zero collisions on `.seg`, `.swatch`, `.maturity-pill`, `.timeline-entry`, `.preview-section`. Edition pages (`#list-view`, `#reader-view`, `.article-entry`) are unaffected.
- **TOKN-04 honored in `style-map.css`:** zero `font-family:` declarations, zero `max-width:` declarations, zero page-chrome rules. Inline `font-family` rules in `tokens-preview.html` are scoped to preview-only helper classes (`.preview-section h2/h3`, `.swatch-label`, etc.) and do not affect the shipped token surface or the SPA.
- **CSP compliance:** Caddyfile sets `script-src 'self' 'unsafe-inline'` and `style-src 'self' 'unsafe-inline'`. The preview's inline `<script>`, inline `<style>` block, inline `onclick="setMode(...)"` handlers, and inline `style="..."` attributes all fall within this policy.
- **XSS surface:** `tokens-preview.html` is fully static — no user input, no DOM injection, no fetch/eval/innerHTML, no template substitution. `setMode(mode)` validates input against a fixed allow-list (`'technical'|'strategic'`) before mutating `document.body.classList`.
- **Deployment correctness:** The Caddyfile orders `file_server` before `try_files {path} /index.html`. The new `/style-map.css` and `/srv/tokens-preview.html` are served as static files before the SPA fallback fires (Phase 1 §1 confirmed pattern). `entrypoint.sh` only `sed`-substitutes `app.js`, so the preview file is never touched by the runtime config injection.
- **Secrets/credentials:** None present in either new file. `grep` confirms zero references to `__SUPABASE_URL__`, `__SUPABASE_ANON_KEY__`, `/app.js`, or `supabase-js` in `tokens-preview.html`. The page deliberately bypasses the SPA wiring.
- **Cross-page collisions:** `tokens-preview.html` uses `id="btn-technical"` / `id="btn-strategic"` matching IDs in `index.html`, but the documents are loaded on different routes; no runtime DOM collision is possible.

The three Info-level findings below are quality observations, not defects.

## Info

### IN-01: `:not([data-source])` rule fails silently if `data-source=""` is ever emitted

**File:** `docker/web/site/style-map.css:146-148`
**Issue:** The empty-source rule `.timeline-entry:not([data-source]) .timeline-source { display: none; }` uses attribute-presence semantics. If a future renderer (Phase 4) accidentally emits `data-source=""` (empty string) instead of omitting the attribute entirely, the attribute is still present and the rule does not hide the `<a class="timeline-source">` element — a broken `source ↗` link with `href=""` would render. The markup contract (style-map.css line 90-93 and CONTEXT.md "Other Claude discretions") explicitly states Phase 4 must omit both the attribute and the `<a>` element, so this is currently safe. Worth noting as a defensive boundary the Phase 4 renderer must respect.
**Fix:** Document in the comment block above the rule that `data-source=""` is treated as "present" by the selector and the renderer contract requires full attribute omission, OR (more defensive) use `.timeline-entry:not([data-source]), .timeline-entry[data-source=""] .timeline-source { display: none; }` to cover the empty-string case too.

### IN-02: `.timeline-source` has no `:focus` style — keyboard users see only the browser default outline

**File:** `docker/web/site/style-map.css:132-141`
**Issue:** `.timeline-source` overrides `text-decoration` (none, with underline-on-hover) and styles the color via `var(--accent-tier, var(--accent))`. There is no explicit `:focus` or `:focus-visible` rule, so keyboard users navigating via Tab rely on the browser default focus ring, which the unset `outline` property does not remove. This is not a regression (the existing `style-shared.css` has the same pattern on `.back-link`, `.entry-title`, etc.), but adding a `:focus-visible` rule with underline + outline would improve keyboard accessibility for the timeline source links Phase 4 will surface.
**Fix:**
```css
.timeline-entry .timeline-source:focus-visible {
    text-decoration: underline;
    outline: 2px solid var(--accent-tier, var(--accent));
    outline-offset: 2px;
}
```

### IN-03: Empty `<span></span>` placeholder in pill-grid is unlabeled

**File:** `docker/web/site/tokens-preview.html:70`
**Issue:** The pill-grid's first cell (`<span></span>` on line 70, before the five column headers) is empty so the CSS grid lines up correctly. Screen readers will announce it as an empty/silent cell, which is harmless but slightly noisy on a verification page that already uses `aria-label` aggressively on the pill elements. This is preview-only markup, not part of any shipped component.
**Fix:** Add `aria-hidden="true"` to the placeholder span (`<span aria-hidden="true"></span>`) or replace with `&nbsp;` to make the grid-layout intent explicit.

## Per-File Disposition

| File | Status | Notes |
|------|--------|-------|
| `docker/web/site/style-map.css` | clean | TOKN-04 enforced (zero font-family/max-width); D-06 scope correct; 2 Info findings (IN-01 empty-source defensiveness, IN-02 focus-visible) |
| `docker/web/site/tokens-preview.html` | clean | Static, no XSS surface; setMode allow-lists input; no SPA/Supabase wiring leak; 1 Info finding (IN-03 unlabeled placeholder span) |
| `docker/web/site/index.html` | clean | Single-line `<link rel="stylesheet" href="/style-map.css">` insertion at line 8, immediately after `/style-shared.css`. Order is correct (map layers onto shared); inserted before all `<script>` tags; no other changes |

---

_Reviewed: 2026-05-27_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
