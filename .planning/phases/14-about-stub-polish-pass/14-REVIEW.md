---
phase: 14-about-stub-polish-pass
reviewed: 2026-06-07T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - docker/web/site/index.html
  - docker/web/site/style-shared.css
findings:
  critical: 0
  warning: 1
  info: 3
  total: 4
status: issues_found
---

# Phase 14: Code Review Report

**Reviewed:** 2026-06-07T00:00:00Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Phase 14 ships a net-new static About page (`index.html`: eyebrow → title → page-sub → 3 prose paragraphs → 5 static agent-pills) and net-new token-anchored CSS (`style-shared.css`: `.about`, `.about-stub .page-sub`, `.agent-row`, `.agent-pill`, `.an`, `.ad`), plus a CSS-only "consistency sweep" snapping off-grid spacing/radii literals onto `--space-*` / `--radius-*` tokens.

This is a frontend-only, static change. I verified:

- **Markup is well-formed** — all tags balance (validated via `html.parser`), no stray/unclosed elements in the new About block.
- **No XSS / injection surface** — the About content is static literal HTML rendered directly from `index.html`; no `innerHTML`, no user input, no template interpolation reaches these surfaces (`app.js` only toggles `display` on `#about-view`). Security scope is clean.
- **All design tokens referenced exist** — every `var(--space-*)`, `var(--radius-*)`, `var(--ink*)`, `var(--accent*)`, `var(--serif/--mono)` used in the diff is defined in `style-base.css:10-66`. No undefined-variable cascade fallbacks.
- **New selectors resolve** — `.about p`, `.about p.body-soft`, `.about-stub .page-sub`, `.agent-row`, `.agent-pill .an`, `.agent-pill .ad` all match the new markup. No orphan selectors among the net-new rules.
- **Grid does not overflow** — `.agent-row` `repeat(auto-fit, minmax(150px, 1fr))` fits ≤4 columns in the 672px content column; 5 pills wrap cleanly (4 + 1), no horizontal overflow at desktop or the ≤600px single-column collapse.
- **Routing is intact** — `getRoute()`/`showView()`/`setActiveTab()` correctly map `#/about` → `about` view → `about` tab; `scrollTo(0,0)` on entry.

One real defect: the consistency sweep deleted the only consumer of `.about-lede` in the same commit, leaving a dead CSS rule (WR-01). The remaining items are informational: a pre-existing cascade override the diff brushes against, the value-changing nature of the "token swap" sweep, and a minor naming legibility note on the new pill classes.

## Warnings

### WR-01: Dead CSS rule `.about-lede` left behind after its only consumer was deleted

**File:** `docker/web/site/style-base.css:238-245`
**Issue:** The Phase 14 HTML change replaced the old About stub markup. The previous stub used `<p class="about-lede">…</p>` (confirmed in `c7b8632:docker/web/site/index.html:83`); the new markup uses `<div class="about">` with `<p class="body-soft">` instead. After this diff, `grep` finds **zero** references to `about-lede` in any `.html`, `.js`, or other consumer — the only remaining hit is the rule definition itself. The `.about-lede` block (font-family, font-size 17px, max-width 60ch, etc.) is now dead code.

Note: `style-base.css` is not in the Phase 14 changed-file set, but the *deletion of its consumer* in `index.html` (which IS in scope) is what stranded this rule. A polish pass whose stated goal is consistency should not leave an orphaned rule for a class it just removed.

**Fix:** Delete the orphaned rule:
```css
/* REMOVE — no remaining consumer after the ABOUT-01 markup swap */
.about-lede {
  font-family: var(--serif);
  font-size: 17px;
  line-height: 1.6;
  color: var(--ink-soft);
  max-width: 60ch;
  margin: var(--space-lg) 0 var(--space-2xl);
}
```

## Info

### IN-01: `.about-stub` intended top padding is overridden by `.content-area`; this diff changed the winning value (20px → 24px)

**File:** `docker/web/site/style-shared.css:130-134` (and the loser at `style-base.css:232-234`)
**Issue:** The About container carries both classes: `<div class="content-area about-stub">` (`index.html:84`). Both `.content-area` (`style-shared.css:133`, `padding-top: var(--space-lg)` = 24px) and `.about-stub` (`style-base.css:233`, `padding-top: var(--space-2xl)` = 48px) are single-class selectors (specificity 0,0,1,0). Because `style-shared.css` loads *after* `style-base.css` (`index.html:10-11`), `.content-area`'s `padding-top` wins — so the About page's intended 48px top padding silently renders as 24px. This override predates Phase 14, but this diff edited the winning declaration's value (`padding-top: 20px` → `var(--space-lg)` = 24px), shifting the actual About top gap from 20px to 24px while the `.about-stub` 48px intent stays inert.

**Fix:** If 48px top padding is intended for the About page, raise specificity or scope it so it is not shadowed:
```css
.about-view .about-stub,           /* or */
#about-view .content-area {
    padding-top: var(--space-2xl); /* 48px, now wins */
}
```
If 24px is actually desired, delete the now-inert `.about-stub { padding-top: var(--space-2xl); }` to remove the misleading dead intent.

### IN-02: "Token consistency sweep" swaps are value-changing, not 1:1 — confirm grid-snaps are intended

**File:** `docker/web/site/style-shared.css` (multiple: lines 131-133, 223, 258, 406, 584, 593, 656, 736, 765, 768, 808, 821, 853)
**Issue:** The phase framing calls this a literals→tokens "consistency sweep," which can read as value-preserving. It is not — most swaps deliberately snap off-grid values onto the nearest grid token, changing rendered metrics:
- `#subscribe-section` padding `40px` → `var(--space-xl)` (32px) — a 20% reduction in the subscribe section's vertical breathing room (most visible change).
- `.content-area` padding-top `20px` → `var(--space-lg)` (24px).
- `.card` padding `20px 20px 16px` → `24px 24px 16px`.
- `.tier-label` / `.block-body h2` margin third value `12px` → `var(--space-sm)` (8px).
- `article h2` margin-bottom `12px` → 8px; `article h3` margin-top `20px` → 24px; `article blockquote` margin `20px` → 24px.
- `#subscribe-email` radius `6px` → `var(--radius-sm)` (7px), margin-bottom `12px` → 8px; `#subscribe-btn` / `.btn-subscribe-secondary` radius `6px` → `var(--radius-btn)` (8px); `.subscribe-status` margin-top `12px` → 8px.

These appear consistent with the documented 4px-grid-snap intent, so I am not flagging them as bugs. Flagging only so the operator confirms the visual deltas (especially the subscribe section padding drop) are deliberate and not an unintended side effect of treating the swap as cosmetic.

**Fix:** No code change required if the grid-snaps are intended. If any specific literal was meant to be preserved exactly (e.g., 40px subscribe padding), keep the literal or pick a token that matches.

### IN-03: New `.an` / `.ad` pill class names are terse and low-legibility

**File:** `docker/web/site/style-shared.css:923, 931` and `index.html:95-112`
**Issue:** The agent-pill child classes are named `.an` (agent name) and `.ad` (agent description). Two-letter, non-self-describing class names diverge from the otherwise descriptive convention in this stylesheet (`.tile-title`, `.tile-subtitle`, `.status-synth`, `.timeline-what`, `.timeline-why`). `.ad` in particular risks confusion with "advertisement" and is a common target for ad-blocker cosmetic filters, which could hide the agent role text for some users. Purely a maintainability/robustness note, not a correctness bug.

**Fix:** Rename to self-describing classes in both files, e.g.:
```css
.agent-pill .agent-name { … }   /* was .an */
.agent-pill .agent-role { … }   /* was .ad */
```
```html
<span class="agent-name">Processor</span>
<span class="agent-role">Background scheduler — …</span>
```

---

_Reviewed: 2026-06-07T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
