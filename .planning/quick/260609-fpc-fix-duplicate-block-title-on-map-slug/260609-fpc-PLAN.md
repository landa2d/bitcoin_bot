---
phase: quick-260609-fpc
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: [docker/web/site/app.js]
autonomous: true
requirements: [FPC-DUP-TITLE]
must_haves:
  truths:
    - "On #/map/<slug> the block title renders EXACTLY ONCE (the styled renderBlock header), not twice"
    - "The maturity pill still renders inside the block header"
    - "The body tagline line and ALL other body content (sections, links, paragraphs) still render intact"
    - "A block body whose first heading is NOT the block title is left untouched (no over-stripping)"
  artifacts:
    - path: "docker/web/site/app.js"
      provides: "renderBlock strips the body's leading duplicate <Title> H1 before marked.parse"
      contains: "renderBlock"
  key_links:
    - from: "renderBlock"
      to: "marked.parse(bodyMd)"
      via: "leading-H1 strip guarded by case-insensitive trimmed match against block.title"
      pattern: "marked\\.parse"
---

<objective>
Fix the duplicate block title shown on the LIVE Agent Economy block detail page (`#/map/<slug>`).

The operator sees the title twice on e.g. `#/map/memory-context`:
1. `Memory & Context` — the styled `renderBlock` header `<h1>` (app.js:734)
2. `Memory & Context` — the body's own leading `# Memory & Context` H1, rendered by `marked.parse(bodyMd)` (app.js:751)

then the tagline (`The does-it-learn-or-does-it-reset layer.`) once. The duplication only became visible after Phase 18 published the rich canonical bodies (pre-publish the bodies were empty/absent, so the body H1 never rendered).

INVESTIGATION ALREADY CONFIRMED (do not re-derive — act on it):
- `updateHero(blockRes.data.title, ...)` at app.js:716 is NOT a visible source. `showView('block')` sets `.hero { display:none }` for every view except `list` (app.js:201-202; comment app.js:198-200). The hero `<h1 id="hero-headline">` carrying `block.title` is HIDDEN on the block route. `updateHero` only mutates hidden DOM text. The TWO visible titles are BOTH inside `#block-content`: the `renderBlock` header H1 (KEEP) and the body's leading H1 (STRIP).
- The canonical body for memory-context (`.planning/docs/02-memory-context.md`) begins `# Memory & Context` (line 11) then a separate bolded tagline paragraph `**The does-it-learn-or-does-it-reset layer.**` (line 13). The published `body_md` mirrors this. The 8 block bodies follow the same shape (leading `# <Title>` then tagline).

FIX (renderer-only, in `renderBlock`): before `marked.parse(bodyMd)`, strip the body's FIRST markdown ATX heading line IF AND ONLY IF its heading text matches `block.title` (trimmed, case-insensitive). Keep the styled `renderBlock` header as the single title + maturity pill. Preserve the tagline and all other body content. A legitimately different first heading must NEVER be removed.

Purpose: title renders exactly once on every published block detail page, with maturity pill and body/tagline intact, without re-authoring or re-publishing any of the 8 bodies.
Output: a single targeted edit to `docker/web/site/app.js` (`renderBlock` body branch) + a SUMMARY.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@docker/web/site/app.js
@.planning/docs/02-memory-context.md
@.planning/phases/18-gated-batch-publish/18-01-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Strip the body's leading duplicate title H1 in renderBlock</name>
  <files>docker/web/site/app.js</files>
  <action>
In `renderBlock(block, bodyMd, entries)` (app.js ~728-770), modify ONLY the Body branch (the `if (bodyMd) { ... }` block around app.js:749-752). Do NOT touch the header branch (A, app.js:732-736), the tension branch (B), the Evolution branch (D), the compose line (E, app.js:769), `updateHero`, `loadBlock`, or any other function.

Before the existing `bodyHtml = '<section class="block-body">' + marked.parse(bodyMd) + '</section>';` line, derive a local de-duplicated body string from `bodyMd` and parse THAT instead. Strip the body's FIRST markdown ATX heading line if (and only if) its heading text equals `block.title` after trimming and case-folding:

  1. Operate on a LOCAL copy (e.g. `var renderMd = bodyMd;`). Do NOT mutate the `bodyMd` parameter in place beyond this branch, and do NOT mutate `block`.
  2. Skip any leading blank lines / pure whitespace lines, then inspect the FIRST non-empty line.
  3. Match a leading ATX heading of ANY level on that first non-empty line: a regex anchored to start that allows optional leading whitespace, one-or-more `#`, at least one space, then the heading text — e.g. test the first non-empty line against `/^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$/` (the trailing `#*` tolerates closed ATX headings; the captured group is the heading text).
  4. Compare the captured heading text to `block.title` using trimmed, case-insensitive equality (`heading.trim().toLowerCase() === String(block.title).trim().toLowerCase()`). escapeHtml is NOT involved in the comparison — compare the raw markdown heading text to the raw title.
  5. ONLY if they match: remove that single first-non-empty heading line from `renderMd` (drop exactly that one line; leave every subsequent line — the tagline and all other content — untouched, including the blank line that followed the heading, so paragraph spacing is preserved). If they do NOT match, leave `renderMd` exactly equal to `bodyMd` (no-op).
  6. Then: `bodyHtml = '<section class="block-body">' + marked.parse(renderMd) + '</section>';`.

Rationale to encode in a short inline comment (cite the bug): the styled `renderBlock` header (A) already renders `block.title`; the published canonical bodies begin with their own `# <Title>` H1 (Phase 16 load / Phase 18 publish), so `marked.parse` was rendering a SECOND identical title. Guarding the strip on a trimmed/case-insensitive title match means a block whose body legitimately opens with a DIFFERENT first heading is never altered.

DO NOT: re-author or re-publish any block body; touch economy_map data or any migration; alter `loadBlock`'s draft/published fetch logic (app.js ~688-707); change `updateHero`; modify CSS files; or alter the `__SUPABASE_URL__` / `__SUPABASE_ANON_KEY__` placeholders at app.js:4-5 (they must remain byte-identical for entrypoint.sh substitution).

Note: `trimHubBody()` is HUB-specific (storyline trimming) and is NOT the right tool here — implement the targeted leading-title-H1 strip inline in the block body branch as described.
  </action>
  <verify>
    <automated>cd /root/bitcoin_bot && node --check docker/web/site/app.js && echo JS-SYNTAX-OK</automated>
    <automated>cd /root/bitcoin_bot && grep -c '__SUPABASE_URL__\|__SUPABASE_ANON_KEY__' docker/web/site/app.js && python3 scripts/verify_economy_map_crosslinks.py --guard-only</automated>
  </verify>
  <done>
- `renderBlock`'s body branch parses a leading-title-H1-stripped copy of `bodyMd` (guarded by trimmed/case-insensitive `block.title` match); the header branch, tension branch, Evolution branch, compose line, and `updateHero` are unchanged.
- `node --check docker/web/site/app.js` prints `JS-SYNTAX-OK`.
- The grep gate still counts the two `__SUPABASE_URL__` / `__SUPABASE_ANON_KEY__` placeholders (>= 2) and the crosslink guard script exits 0.
- A block body whose first heading does NOT match its title is provably untouched (the strip is a no-op on non-match — reason about the regex/comparison; no data change required).
  </done>
</task>

</tasks>

<verification>
Both gates run on the MAIN tree (where `config/.env` and the guard script exist):
1. `cd /root/bitcoin_bot && node --check docker/web/site/app.js && echo JS-SYNTAX-OK`
2. `cd /root/bitcoin_bot && grep -c '__SUPABASE_URL__\|__SUPABASE_ANON_KEY__' docker/web/site/app.js && python3 scripts/verify_economy_map_crosslinks.py --guard-only`

Manual reasoning (no live deploy by the executor): on `#/map/memory-context`, the styled header renders `Memory & Context` once; the body's leading `# Memory & Context` line is stripped before `marked.parse`, so the second title is gone; the bolded tagline paragraph (`**The does-it-learn-or-does-it-reset layer.**`) and every later section/paragraph/link render unchanged.
</verification>

<success_criteria>
- The block title renders EXACTLY ONCE on `#/map/<slug>` (styled `renderBlock` header), with the maturity pill intact.
- Tagline and all other body content preserved; over-stripping impossible (strip guarded by exact trimmed/case-insensitive title match).
- Only `docker/web/site/app.js` changed; no data/migration/CSS/placeholder changes.
- Both `<automated>` gates pass on the main tree.
</success_criteria>

<deploy_ownership>
GOING LIVE IS A SEPARATE, OPERATOR-GATED STEP OWNED BY THE ORCHESTRATOR — NOT part of this executor's task.

The executor authors + commits the `app.js` fix and writes the SUMMARY only. It does NOT run any `docker compose` build and does NOT deploy.

After operator approval, the ORCHESTRATOR performs the scoped go-live from the MAIN tree:
`cd /root/bitcoin_bot/docker && docker compose up -d --build web`
(service KEY `web`; container name `agentpulse-web` — per the Phase 18 planner gotcha, the compose command targets the service key `web`, NOT `agentpulse-web`). entrypoint.sh substitutes the `__SUPABASE_URL__` / `__SUPABASE_ANON_KEY__` placeholders at container start, so live verification is on the substituted copy. This is worktree-unsafe (`docker compose up -d --build` cds to the absolute main-tree path) — run from the main tree, orchestrator-owned.
</deploy_ownership>

<output>
Create `.planning/quick/260609-fpc-fix-duplicate-block-title-on-map-slug/260609-fpc-SUMMARY.md` when done.
</output>
