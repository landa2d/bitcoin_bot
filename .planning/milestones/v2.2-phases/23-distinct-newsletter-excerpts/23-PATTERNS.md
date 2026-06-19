# Phase 23: Distinct Newsletter Excerpts - Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 3 modified (`app.js`, one CSS sheet, `index.html` likely untouched)
**Analogs found:** 3 / 3 (all in-codebase; 2 net-new idioms flagged)

This is a frontend-only, strip-at-render phase. There are no new files — every
change is an in-place edit to the existing `docker/web/site/` SPA. The work is:
(1) new **pure string helpers** in `app.js` (markdown-cleanup + recap-detection /
sentence-extraction), (2) a **rewrite of `renderList()`** to emit the indexed-row
markup, and (3) **net-new token-only CSS** for the `.row` grid + 2-line clamp.
Every piece has a strong same-author, same-file analog already in the codebase.

## File Classification

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---------------|------|-----------|----------------|---------------|
| `docker/web/site/app.js` — new excerpt/cleanup helpers | utility (pure fn) | transform | `trimHubBody()` / `stripLeadingTitleH1()` (`app.js:85-96`, `:112-128`) | exact (same file, same author, same render-only spine) |
| `docker/web/site/app.js` — `renderList()` rewrite | component (render) | transform + request-response | `renderHub()`/`renderTile()` (`app.js:719-763`), `renderTimelineEntries()` (`app.js:986-1020`) | exact (same `.map().join('')` → innerHTML idiom) |
| `docker/web/site/style-shared.css` (or `style-base.css`) — `.row` grid + clamp | config (presentation) | n/a | `.made-cols`/`.agent` grid-row (`style-shared.css:1003-1012`); `.tier-label`/`.legend-label` mono chrome (`:217-237`) | role-match (grid-row analog exact; 2-line clamp net-new) |
| `docker/web/site/index.html` — `#newsletter-list` container | template | n/a | reused verbatim (`index.html:71-73`) | no change (markup is JS-emitted) |

## Pattern Assignments

### `app.js` — new pure helpers: markdown-cleanup + recap-detection / sentence-extraction (utility, transform)

**Analog:** `trimHubBody(md)` (`app.js:85-96`) and `stripLeadingTitleH1(md, title)` (`app.js:112-128`)

These two are the house template for a render-only string transform. Match their
shape exactly: a module-level `function`, a heavy contract comment above it, a
falsy-input guard, operation on a LOCAL copy of the string (never the DB / args),
and — critically — a **defensive no-op when the pattern is absent** rather than a
silent content drop. That last property IS decisions D-03 and D-07 ("if no leading
sentence matches, keep the first sentence … a silent content-drop is the failure
mode to avoid").

**The render-only / never-over-strip spine** (`app.js:85-96`):
```javascript
function trimHubBody(md) {
    if (!md) return md;                   // falsy guard, returns input unchanged
    var TIER1 = '## Tier 1';
    var RESTATED = '## The thesis, restated';
    var cut = md.indexOf(TIER1);
    if (cut === -1) return md;            // cut-point absent → leave body intact (no silent drop)
    var head = md.slice(0, cut).replace(/\s*(?:---\s*)?$/, '').trimEnd();
    var tailIdx = md.indexOf(RESTATED, cut);
    if (tailIdx === -1) return head;
    var tail = md.slice(tailIdx).trimEnd();
    return head + '\n\n' + tail + '\n';
}
```
**Follow this pattern:** the recap-skip helper returns the first sentence unchanged
when no recap opener matches (mirror the `if (cut === -1) return md;` line). The
markdown-cleanup helper returns input unchanged on falsy. Document the contract in
a comment block like `:73-84` / `:98-111`.

**The line-by-line / local-mutation defensive idiom** (`app.js:112-128`) — for any
helper that walks the markdown structurally:
```javascript
function stripLeadingTitleH1(md, title) {
    if (!md || !title) return md;
    var lines = md.split('\n');           // operate on a LOCAL copy
    var firstIdx = -1;
    for (var li = 0; li < lines.length; li++) {
        if (lines[li].trim() !== '') { firstIdx = li; break; }
    }
    if (firstIdx === -1) return md;
    var headingMatch = lines[firstIdx].match(/^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$/);
    if (!headingMatch) return md;         // not the targeted shape → byte-identical no-op
    // ...drop exactly the one matched line, keep everything else...
    lines.splice(firstIdx, 1);
    return lines.join('\n');
}
```
**Follow this pattern:** strip the `## Read This, Skip the Rest` H2 (D-01) the same
way — match the heading line defensively, splice only it, leave the rest. A body
with a different/absent header is a no-op (D-07 graceful degradation).

**The named-anchored-regex-constant idiom** for the recap pattern list (D-03) —
analog `EDITION_SUFFIX_RE` (`app.js:52`):
```javascript
// HEAD-01 / D-03 / D-04: render-only strip ... Anchored to `$` ... case-insensitive.
// Applied UNCONDITIONALLY ... a no-op when no suffix is present ...
const EDITION_SUFFIX_RE = /\s*[—–-]\s*Edition\s*#\d+\s*\|.*$/i;
```
**Follow this pattern:** declare the recap-opener regex as a module-level `const`
(e.g. `RECAP_OPENER_RE`) anchored to the sentence START (`^`), case-insensitive
(`i`), with a comment listing the corpus phrases it covers (`Last week`,
`Last week's`, `For weeks`, `Two editions ago`, `For N editions`, `Last month`).
Same place in the file as the other `const` regexes (`:43-57`).

**Mode-aware body source (D-08)** — reuse, do not reimplement (`app.js:585-588`):
```javascript
function getModeContent(data) {
    if (currentMode === 'strategic' && data.content_markdown_impact) return data.content_markdown_impact;
    return data.content_markdown || '';
}
```
The new excerpt pipeline takes its raw markdown from `getModeContent(n)` (already
called at `app.js:378`), so it flips Technical/Strategic with the toggle for free.

---

### `app.js` — `renderList()` rewrite (component, transform + request-response)

**Analog:** `renderHub()`/`renderTile()` (`app.js:719-763`), `renderTimelineEntries()` (`app.js:986-1020`)

**Current code being replaced** (`app.js:376-388`) — note the crude strip at `:379`
(the D-05 defect: leaks `[text](url)` URLs) and the legacy `.article-entry` markup:
```javascript
var html = data.map(function(n) {
    var title = getModeTitle(n);
    var content = getModeContent(n);
    var excerpt = content.replace(/[#*_\[\]`>]/g, '').substring(0, 150) + '...';  // ← D-05 defect

    return '<div class="article-entry">' +
        '<div class="section-label">EDITION #' + n.edition_number + ' · ' + formatDate(n.published_at) + '</div>' +
        '<a href="#/edition/' + n.edition_number + '" class="entry-title">' + escapeHtml(title) + '</a>' +
        '<p class="entry-preview">' + escapeHtml(excerpt) + '</p>' +
        '</div>';
}).join('');
document.getElementById('newsletter-list').innerHTML = html;
```

**The whole-`<a>`-is-the-click-target row builder** — analog `renderTile()` (`app.js:758-762`):
```javascript
return '<a href="#/map/' + encodeURIComponent(b.slug) + '" class="' + cls + '">' +
           '<h3 class="tile-title">' + escapeHtml(b.title) + '</h3>' +
           '<p class="tile-subtitle">' + escapeHtml(b.subtitle) + '</p>' +
           dotsRow +
       '</a>';
```
**Follow this pattern:** emit each row as one `<a href="#/edition/' + n.edition_number + '" class="row">` wrapping `<span class="num">` / a nested `<span>` with `<p class="title">` + `<p class="sum">` / `<span class="date">` (the mockup row shape, D-09, mockup markup at `agentpulse-redesign (1).html:270-277`). escapeHtml every DB string (`title`, the extracted `sum`); interpolate the numeric `n.edition_number` raw (existing precedent `:382-383`, and `renderMaturityPill` interpolates `data-stage` raw at `:604`). The `num` is `n.edition_number` (NOT a sequential index, D-09).

**Conditional-fragment composition** for the D-04/D-07 cases (append-next-sentence,
or omit the `.sum` line entirely) — analog `renderTile()`'s `dotsRow`/`deferred`
ternary (`app.js:749-757`) and `renderTimelineEntries()`'s `hasSource` branch
(`app.js:1009-1017`):
```javascript
var line2Inner = '<span class="timeline-why">' + escapeHtml(e.why_it_mattered) + '</span>';
if (hasSource) {
    line2Inner += '<a class="timeline-source" href="' + escapeHtml(safeUrl) + '" ...>source ↗</a>';
}
```
**Follow this pattern:** build the `.sum` fragment conditionally — empty string when
extraction yields nothing (D-07: render `num · title · date` with NO summary line,
never the legacy 150-char fallback).

**Empty-state guard + hero update** — preserve verbatim from current `renderList`
(`app.js:364-374`); these are unchanged contracts:
```javascript
if (!data || data.length === 0) {
    document.getElementById('newsletter-list').innerHTML = '<div class="content-area">...No newsletters...</div>';
    updateHero('AI Agents Pulse', ''); return;
}
var latest = data[0];
updateHero('AI Agents Pulse', 'Latest: Edition #' + latest.edition_number + ' · ' + formatDate(latest.published_at));
```

**The `.map(...).join('')` → single `.innerHTML` assignment** (`app.js:386-388`,
`:830-841`, `:1019`) is the universal list-render idiom here — keep it.

**Do NOT touch `loadList()`** (`app.js:391-415`): no new query, no new field, no new
status filter (D-08, strip-at-render). It already fetches `select('*')` newest-first;
`renderList` works entirely from the existing rows.

---

### CSS — `.row` / `.num` / `.title` / `.sum` / `.date` / `.archive-label` (config, presentation)

**Analog:** Phase 22 `.made-cols`/`.agent` grid-row block (`style-shared.css:1003-1012`)

This is the closest existing pattern by every axis: same author, net-new + token-only
(RHYTHM-01), an **indexed grid-row with a fixed-width index column**, `align-items:
baseline`, a `border-bottom: 1px solid var(--line)` divider, compact one-line rule
bodies, and a `@media (max-width: 880px)` single-column collapse.
```css
.made-cols { display:grid; grid-template-columns:1fr 1fr; gap:0 var(--space-2xl); margin-top:var(--space-lg); }
.made-head { font-family:var(--mono); font-size:11px; font-weight:600; color:var(--ink-faint); letter-spacing:.08em; text-transform:uppercase; margin:0 0 var(--space-md); }
.agent { display:grid; grid-template-columns:26px 1fr; gap:0 var(--space-md); align-items:baseline; padding:var(--space-sm) 0; border-bottom:1px solid var(--line); }
.agent .idx  { font-family:var(--serif); font-size:14px; color:var(--ink-faint); }
.agent .name { font-family:var(--mono); font-size:14px; font-weight:500; color:var(--ink); margin:0; }
.agent .desc { font-size:14px; color:var(--ink-soft); margin:var(--space-xs) 0 0; line-height:1.5; }
@media (max-width: 880px) { .made-cols { grid-template-columns: 1fr; } }
```
**Follow this pattern:** port the mockup `.row` (`agentpulse-redesign (1).html:116-128`)
onto this exact structure — `grid-template-columns: 56px 1fr auto; gap: 0 var(--space-lg); align-items: baseline; border-bottom: 1px solid var(--line);`. The `.num`/`.title`/`.sum` map to `.idx`/`.name`/`.desc` family choices. Responsive reflow per mockup `:225-226` (`.row { grid-template-columns: 40px 1fr; } .row .date { grid-column: 2; }`).

**Mono chrome label** for `.archive-label` — analog `.tier-label` (`style-shared.css:217-225`) and `.legend-label` (`:237`):
```css
.tier-label { font-family: var(--mono); font-size: 11px; font-weight: 600; color: var(--ink-faint); letter-spacing: .18em; text-transform: uppercase; margin: var(--space-xl) 0 var(--space-sm); }
```
**Follow this pattern:** `.archive-label` is the same mono-11px-uppercase-`--ink-faint`
recipe with the mockup's `border-bottom: 1px solid var(--line); padding-bottom`.

**Hover-on-link-row** — analog `.entry-title:hover` (`:170-172`) and `.card:hover`
(`:314-318`); the mockup uses `.row:hover { padding-left: 8px; } .row:hover .num { color: var(--violet); }`. Map `--violet` → `--accent` per D-10.

**`:focus-visible`** — analog `.card:focus-visible` (`:320-323`); the mockup also has a
`.row:focus-visible` rule (`agentpulse-redesign (1).html:234-236`). Keep a focus
outline so a11y does not regress (Phase 25 boundary note in CONTEXT).

**The 2-line clamp (D-06) — NET-NEW idiom, no existing analog.** No `-webkit-line-clamp`
or `-webkit-box` exists anywhere in either stylesheet (verified). Use the standard
four-property idiom, token-only elsewhere:
```css
.row .sum { display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
```
The full extracted text stays in the DOM (clamp is visual only) — satisfies D-06
(a11y/SEO) and D-07 (no hard character truncation).

**Where it lands:** planner's choice between `style-shared.css` (where the superseded
`.article-entry` family lives, `:139-180`) and `style-base.css` (D-10). The legacy
`.article-entry`/`.section-label`/`.entry-title`/`.entry-preview` rules (`style-shared.css:139-180`)
are superseded — retire or leave dormant (planner's discretion, D-10).

---

## Shared Patterns

### Render-only, never-mutate-stored-data spine (D-01/D-03/D-07)
**Source:** `trimHubBody`/`stripLeadingTitleH1` comments (`app.js:73-128`), `getModeTitle` comment (`app.js:575-583`), `EDITION_SUFFIX_RE` comment (`app.js:43-52`)
**Apply to:** every new helper. The cardinal rule from CONTEXT (and the codebase's
memory): if the pattern (header / recap) is absent, NO-OP — keep the original text.
Never silently drop content you cannot bound. Operate on local string copies.

### escapeHtml at every DB sink; numeric raw
**Source:** `escapeHtml()` (`app.js:554-558`); usage at `:383-384`, `:759-760`, `:1006`
**Apply to:** the row `title` and extracted `sum` (DB-derived). `edition_number` is
numeric → interpolated raw (precedent `:382`, `:604`). The reader route is the only
place markdown bypasses escaping (`marked.parse`, `:449`) — the LIST never calls
`marked.parse`; the excerpt is hand-extracted from the raw string (CONTEXT code_context).

### Mode-aware accessor pattern (D-08)
**Source:** `getModeContent()`/`getModeTitle()` (`app.js:575-588`) + `currentMode` global (`:142`) + re-render-on-toggle (`setMode` → `renderList`, `app.js:201-203`)
**Apply to:** the whole row. Title via `getModeTitle(n)` (reuses the `EDITION_SUFFIX_RE`
strip chokepoint — do NOT regress, D-09), summary derived from `getModeContent(n)`.
`setMode()` already re-renders the list when visible (`:201-203`), so the row flips
modes with zero new state.

### Token-only CSS (RHYTHM-01 / D-10) + mockup→prod token mapping
**Source:** `:root` (`style-base.css:10-79`); Phase 22 AGENTS-01 mapping note (`style-shared.css:998-1002`)
**Apply to:** every new CSS value is a `var(--…)`; zero hardcoded hex.
| Mockup token | Prod token | Note |
|--------------|-----------|------|
| `--violet` (#4b3fd6) | `--accent` (#5b3df5) | per D-10 hover→`--accent`; `--accent-ink` (#4a2fd6) is the nearer hex if a darker hover is wanted |
| `--ink-faint` | `--ink-faint` | 1:1 (`.num`, `.date`, `.archive-label`) |
| `--ink-soft` | `--ink-soft` | 1:1 (`.sum`) |
| `--serif` / `--mono` | `--serif` / `--mono` | 1:1 |
| `--line` (mockup, `.archive-label` border) | `--line` | prod `--line` is the soft hairline |
| **`--line-soft`** (mockup, `.row` border) | **`--line`** | ⚠ see warning below |

---

## No Analog Found

| Need | Why no analog | Planner guidance |
|------|---------------|------------------|
| 2-line `-webkit-line-clamp` CSS (D-06) | No `-webkit-box`/`line-clamp` anywhere in either sheet | Net-new four-property idiom (excerpt above). Mockup `.row .sum` has no clamp either — this is our addition because extracted sentences are longer than the mockup's hand-written ones (CONTEXT specifics). |
| `[text](url)` → `text` markdown-link cleanup (D-05) | No existing link-text extraction; the crude `:379` strip is the defect being removed; `marked.js` handles real rendering on the reader route only | Net-new regex helper; structure it like `trimHubBody` (pure, defensive, commented). Convert `[text](url)`→`text`, drop bare URLs, then strip residual `#*_\`>` markers — in that order, BEFORE sentence segmentation. |
| Recap-pattern sentence segmentation (D-02/D-03/D-04) | No sentence-level text processing exists in the codebase | Algorithm is net-new (planner derives the regex + length floor from the ed 28/29/30 corpus). Its STRUCTURE follows `trimHubBody`/`stripLeadingTitleH1`; its no-match behavior is the D-07 keep-sentence-1 spine. Consult `.planning/docs/REDESIGN_CC_BRIEF.md` §TASK 6 if a code example is needed. |

---

## ⚠ Critical Gotcha for the Planner

**`--line-soft` does NOT exist in prod `:root`.** CONTEXT D-10 lists `--line-soft`
as a "live token", but `style-base.css:17-18` defines only `--line` (#e7e2da) and
`--line-strong` (#d8d2c7). The mockup's `.row` border uses `var(--line-soft)`
(`agentpulse-redesign (1).html:119`). Porting it verbatim would resolve to an
**invalid/empty custom property → the row divider silently drops** — a token-only-
discipline + fail-loud violation (and exactly the kind of silent visual no-op
memory flags). **Map mockup `--line-soft` → prod `--line`** for the `.row`
`border-bottom`. (`--line` is prod's lightest hairline; `--line-strong` is reserved
for major section boundaries per `style-shared.css:131`, `:243`, `:763`.)

---

## Metadata

**Analog search scope:** `docker/web/site/` (`app.js`, `style-base.css`, `style-shared.css`, `index.html`) + `.planning/docs/agentpulse-redesign (1).html` mockup
**Files scanned:** 5
**Net-new idioms (no in-codebase analog):** 3 (2-line clamp CSS, markdown-link cleanup, recap sentence segmentation)
**Pattern extraction date:** 2026-06-15
</content>
</invoke>
