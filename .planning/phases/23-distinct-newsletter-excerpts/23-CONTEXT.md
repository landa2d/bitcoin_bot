# Phase 23: Distinct Newsletter Excerpts - Context

**Gathered:** 2026-06-13
**Status:** Ready for planning

<domain>
## Phase Boundary

The newsletter **archive list** stops showing near-identical opening text on
consecutive editions. At render, strip the boilerplate intro and show each
edition's first *genuinely-distinct* sentence, presented in the mockup's
**indexed-row format** (number · title · one-line summary · date).

**Strip-at-render only** (operator-confirmed at milestone start):
- NO `newsletters` schema change, NO stored `summary` field, NO content-pipeline
  change. The stored-`summary` path is the deferred **EXCERPT-F1** future
  requirement — explicitly out of this milestone.
- Frontend-only: `docker/web/site/app.js` (`renderList()`) + new token-only CSS
  for the row format.

**Single requirement:** EXCERPT-01. **Acceptance anchor:** editions 29 and 30
show different preview text in the list.

**NOT in scope:** a stored/generated summary field (EXCERPT-F1); Signals feed
(Phase 24); the holistic responsive/a11y pass (Phase 25 — but do not regress
a11y here); any backend, pipeline, or migration change.
</domain>

<decisions>
## Implementation Decisions

### Excerpt extraction — "the first genuinely-distinct sentence"
Observed structure (verified against the live `newsletters` rows for editions
28/29/30, both `content_markdown` and `content_markdown_impact`): every edition
opens with an `## Read This, Skip the Rest` H2 → a **recap sentence** (look-back
framing: "Last week's…", "Last week we…", "For weeks we've…", "Two editions
ago…", "For three editions…") → a **"This week…" pivot** that states the
edition's thesis → the lead story.

- **D-01 — Strip the section header.** Remove the `## Read This, Skip the Rest`
  H2 (markdown header) before excerpting. Render-only; never mutates stored data.
- **D-02 — Surface the this-week thesis (skip the recap).** After the header,
  skip the leading **recap sentence(s)** and surface the first remaining
  sentence (the "this-week" pivot — usually the best one-line summary). This is
  what SC#1 means by "the recurring header + shared intro sentence are skipped,
  and the first genuinely-distinct sentence is shown."
- **D-03 — Recap detection: match look-back phrases, never over-strip.** Only
  skip a leading sentence if it matches a recap pattern (case-insensitive opener:
  `Last week`, `Last week's`, `For weeks`, `Two editions ago`, `For N editions`
  / `For <number-word> editions`, `Last month`, and similar look-back framings —
  planner finalizes the pattern list from the observed corpus). **If no leading
  sentence matches, keep the first sentence** — do not blindly drop sentence 1.
  Rationale: a silent content-drop is the failure mode to avoid; worst case a
  stray recap shows, which is recoverable, vs. hiding a real opener (no-silent-
  loss / fail-loud spine). May need to skip MORE than one leading recap sentence
  (some editions stack two: "Last week we… For weeks we've…").
- **D-04 — Thin-pivot handling: append the next sentence.** If the chosen
  sentence is below a length floor (~40 chars — e.g. ed29's "This week it got
  specific."), append the following sentence so the row carries real substance
  (→ "This week it got specific. Researchers exposed BadHost, a critical
  vulnerability in Starlette…"). The 2-line clamp (D-06) bounds the combined
  length. Floor value is planner's discretion (~40 chars is the starting point).

### Summary line treatment
- **D-05 — Proper markdown cleanup (NOT the current crude strip).** The existing
  `content.replace(/[#*_\[\]`>]/g, '')` leaks link URLs into the text (e.g. ed30
  → "…stablecoin rollout(https://unchained…"). The new path MUST convert
  `[text](url)` → `text` (drop the URL) and strip remaining inline formatting
  markers before measuring/segmenting sentences.
- **D-06 — Clamp to 2 lines, keep full text in the DOM.** Bound the summary with
  a CSS 2-line clamp (`-webkit-line-clamp: 2` idiom) + ellipsis on overflow; the
  full extracted text stays in the DOM (a11y/SEO). 2 lines (not 1) pairs with the
  append-next-sentence rule (D-04) — a 1-line clamp would clip the appended
  substance. No hard character truncation of the actual text.

### Fallback & mode-awareness
- **D-07 — Graceful degradation, never boilerplate, never fabricate.** When
  extraction can't produce a clean distinct sentence (no `## Read This, Skip the
  Rest` header, or nothing left after cleanup): fall back to the body's **first
  cleaned sentence** (if no recap matched, this is just the first sentence). If
  even that is empty/missing, render the row as **number · title · date with NO
  summary line** — do not reintroduce the legacy 150-char clamp (it can recreate
  the exact boilerplate-leak this phase fixes) and do not error.
- **D-08 — Summary stays mode-aware.** Derive the summary from
  `content_markdown` (Technical) or `content_markdown_impact` (Strategic),
  flipping with the newsletter-scoped Technical/Strategic toggle — same as today
  (`getModeContent()`), and consistent with the row **title** which already flips
  via `getModeTitle()`. The whole row stays coherent with the reader's mode.

### Indexed-row format (NOT deep-discussed — operator deferred to the mockup)
- **D-09 — Follow the mockup's `.row` shape.** Replace the current
  `.article-entry` (section-label / entry-title / 150-char `.entry-preview`
  paragraph) with the mockup's indexed-row grid: **number · title · summary ·
  date** (mockup `#index` `.row` = `grid-template-columns: 56px 1fr auto`, with
  `.num` / nested `.title`+`.sum` / `.date`). Lives on the existing `--wide`
  axis (`#list-view > #newsletter-list.content-area.wide`).
  - `num` = `edition_number` (mockup uses the edition number: 29, 28, 27…), NOT a
    sequential row index.
  - `title` = `getModeTitle(n)` — reuse the Phase 22 `EDITION_SUFFIX_RE` strip
    chokepoint (do not regress it).
  - `date` = `formatDate(n.published_at)` — mono, right-aligned, `white-space:
    nowrap` per the mockup.
  - The whole row is the `#/edition/<n>` link (deep-link preserved).
- **D-10 — New CSS must be token-only (RHYTHM-01).** Every new rule themes from
  the existing CSS-variable system (warm off-white + violet); zero hardcoded hex.
  Port the mockup's `.row`/`.num`/`.title`/`.sum`/`.archive-label` values onto
  the live tokens (`--ink-faint`/`--ink-soft`/`--accent`/`--line`/`--line-soft`).
  Lands in `style-shared.css` (where `.article-entry` lives) or `style-base.css`
  — planner decides; the legacy `.article-entry`/`.entry-preview` rules are
  superseded (retire or leave dormant per planner).

### Claude's Discretion (planner / researcher decides — honoring D-01..D-10)
- **"Latest" featured block (NOT selected for discussion).** The mockup splits a
  featured "Latest" treatment (big `.display` title + `.lede` + "Read the edition
  →" `.readlink`) above the `.archive-label` + rows. EXCERPT-01 only requires the
  indexed-row format, and the existing hero already shows "Latest: Edition #N · 
  date". **Default:** keep all editions as uniform indexed rows; adopting the
  mockup's Latest featured block is optional polish, left to planner — if adopted
  it must not duplicate/fight the existing hero + mode toggle that Phase 21
  locked into `#newsletter`.
- The exact sentence-segmentation algorithm (handling `.` inside the markdown
  links, the `:` colon clauses, em-dashes, abbreviations); the exact recap-
  pattern regex and the length floor; whether the row uses a CSS grid or flex;
  whether the legacy `.article-entry` CSS is deleted or left dormant.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Source brief + mockup (the spec for this phase)
- `.planning/docs/REDESIGN_CC_BRIEF.md` §"TASK 6 — Newsletter list: distinct
  excerpts" (lines ~138–148) — the duplicate-excerpt defect, "skip the standard
  intro block and pull the first genuinely distinct sentence," and the
  indexed-row recommendation. NOTE: Task 6 also names the stored-`summary`
  alternative — that is the **deferred EXCERPT-F1 path**, NOT this phase.
- `.planning/docs/agentpulse-redesign (1).html` — the mockup. **INTENT reference,
  not markup to copy.** Relevant parts: `.row`/`.num`/`.title`/`.sum`/`.date` +
  `.archive-label` CSS (lines ~109–128), the `#index` section markup with the
  "Latest" treatment + archive rows (lines ~259–302), responsive row reflow
  (lines ~225–226). The mockup's `.sum` lines are *hand-crafted* one-liners — we
  produce *extracted* sentences instead (strip-at-render), so ours will be longer
  and less polished; that is accepted (EXCERPT-F1 is the polished path).

### Phase requirements
- `.planning/ROADMAP.md` §"Phase 23: Distinct Newsletter Excerpts" — goal + 3
  success criteria + the strip-at-render / EXCERPT-F1-deferred note.
- `.planning/REQUIREMENTS.md` — **EXCERPT-01** (consecutive editions show
  distinct preview text; "Read This, Skip the Rest" boilerplate skipped; indexed-
  row format; editions 29 & 30 differ; strip-at-render, no schema change).

### Code to modify / reuse
- `docker/web/site/app.js`:
  - `renderList()` (`:363-389`) — the function to rewrite (current
    `content.replace(/[#*_\[\]`>]/g,'').substring(0,150)+'...'` excerpt logic at
    `:379`; `.article-entry` emission at `:381-385`).
  - `loadList()` (`:391+`) — the Supabase read (`newsletters`, status in
    `['published','preview']`, ordered by `edition_number` desc); **do not add a
    new query or new field** (strip-at-render).
  - `getModeContent()` (`:585`) — returns `content_markdown` /
    `content_markdown_impact`; the mode-aware body source for D-08.
  - `getModeTitle()` (`:575`) + `EDITION_SUFFIX_RE` (`:52`) — the Phase 22 title
    chokepoint to reuse for the row title (don't regress).
  - `escapeHtml()` (`:553`) / `formatDate()` (`:568`) — existing sinks to reuse.
- `docker/web/site/style-shared.css` — `.article-entry` / `.section-label` /
  `.entry-title` / `.entry-preview` (`:139-174`) — the classes being superseded
  by the indexed-row format.
- `docker/web/site/style-base.css` — `:root` token layer + `.eyebrow` (`:103`);
  new row CSS must theme from these tokens (D-10).
- `docker/web/site/index.html` — `#newsletter` section → `#list-view >
  #newsletter-list.content-area.wide` (`:59-74`); the hero + mode toggle sit
  above the list (Phase 21-locked — do not move).

### Carried-forward decision contracts (prior phases)
- `.planning/phases/20-width-tokens-centering-foundation/20-CONTEXT.md` —
  `--measure`/`--wide`/`--gutter`, `.prose`/`.wide`, token-only color +
  section-rhythm baseline (RHYTHM-01) the new CSS must conform to.
- `.planning/phases/21-single-scroll-landing-scroll-spy-nav/21-CONTEXT.md` — the
  newsletter list lives in the `#newsletter` landing section; the row stays a
  deep-linkable `#/edition/<n>` link; the `body > header` sticky scoping and the
  mode toggle must not regress.
- `./CLAUDE.md` — deploy discipline (prod↔main drift check → branch → `/diff` →
  scoped `docker compose up -d --build web` (service key `web`, NO `--delete`) →
  operator approval); the web-entrypoint `__SUPABASE_URL__` sed-substitution
  (preview vs live).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`renderList()` / `loadList()`** already fetch and map the editions newest-
  first — the rewrite is localized to one render function + its excerpt helper;
  no new query (D-08 reuses `getModeContent`, title reuses `getModeTitle`).
- **Phase 20 `--wide` axis + tokens** — the list already sits in
  `#newsletter-list.content-area.wide`; the indexed-row grid drops in on that
  axis. `--ink-faint`/`--ink-soft`/`--accent`/`--line`/`--line-soft` are the
  natural row tokens (mockup `.num`→`--ink-faint`, hover→`--accent`;
  `.sum`→`--ink-soft`; row border→`--line-soft`).
- **Phase 22 `EDITION_SUFFIX_RE` + `getModeTitle()`** — the title chokepoint to
  reuse so the baked `— Edition #N | <date>` suffix never shows in the row title.

### Established Patterns
- Single hand-authored CSS, no build step. `style-base.css` loads FIRST (its
  `:root` + serif body win the cascade); `style-shared.css` is the legacy
  component layer where `.article-entry` lives. Only these two sheets are loaded.
- Markdown is rendered client-side by `marked.js` (CDN) on the reader route, but
  the LIST excerpt is extracted by hand from the raw markdown string — so this
  phase needs its OWN markdown-cleanup (D-05), independent of `marked.js`.
- The deployed `/srv/app.js` differs from repo only by the
  `__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` entrypoint substitution — not a real
  divergence.

### Integration Points
- The excerpt change is entirely inside the list render path
  (`#newsletter-list`). The hero ("Latest: Edition #N"), mode toggle, and
  `#/edition/<n>` reader route are untouched contracts the row must keep working.
- Mode-awareness (D-08) flows through the existing `currentMode` global + the
  newsletter-scoped toggle — no new state.

### Deploy (worktree-unsafe — orchestrator-owned)
- Ship via scoped `docker compose ... web` rebuild (SERVICE key `web`, not the
  `agentpulse-web` container_name); NO `--delete`; prod↔main drift check first;
  operator approval. Live-render verify of editions 29/30 (both modes) is the
  acceptance proof. (Memory: web compose service name; scoped/approved deploys.)
</code_context>

<specifics>
## Specific Ideas

- **The acceptance proof is concrete:** editions 29 and 30 must show *different*
  preview text in the list, in both Technical and Strategic modes. Verify on the
  live render (the Phase 22 pattern: reproduce against the real ed 29/30 data,
  both modes), not just in code.
- **Mockup `.sum` ≠ our output:** the mockup's archive summaries are polished
  hand-written one-liners ("Who decides which agents get to transact, and on
  whose terms."). Our strip-at-render output is the *extracted* this-week-thesis
  sentence — longer and rougher. This gap is by design; the polished stored-
  summary is EXCERPT-F1 (deferred).
</specifics>

<deferred>
## Deferred Ideas

- **Stored/generated `summary` field (EXCERPT-F1)** — the cleaner long-term path
  where the Newsletter agent emits a one-line summary at generation time
  (schema + pipeline change). Explicitly deferred out of this milestone by the
  operator's strip-at-render decision; the polished mockup `.sum` lines are what
  this would eventually enable.
- **Mockup "Latest" featured block** (big display title + lede + "Read the
  edition →") — optional polish above the archive rows; default is uniform rows
  (see Claude's Discretion). Candidate for a later iteration if the operator
  wants the magazine-style top treatment.

None of the above are in Phase 23 scope.
</deferred>

---

*Phase: 23-distinct-newsletter-excerpts*
*Context gathered: 2026-06-13*
