---
phase: quick-260609-ivq
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docker/web/site/style-shared.css
  - docker/web/site/app.js
  - docker/web/site/style-base.css
autonomous: true
requirements: [MAP-FIX-01, MAP-FIX-02, MAP-FIX-03]
subsystem: web-frontend
tags: [economy_map, renderer, css, bug-fix, app.js, style-shared.css, style-base.css]

must_haves:
  truths:
    - "On #/map the hub title 'The Agent Economy' appears exactly ONCE (chrome page-title), not twice; the body's leading duplicate '# The Agent Economy' H1 is stripped. The bold tagline first line is KEPT (operator decision 2026-06-09 — the chrome has NO subtitle, so the bold line is the SOLE instance, not a duplicate)."
    - "On #/map/<slug> the block title appears exactly ONCE (now via the shared helper, same behavior as the prior fix). The bold tagline first line is KEPT."
    - "Body paragraphs in the hub body, block bodies, and newsletter article bodies render with a visible full-line vertical gap (≈ a line of leading), not butted together."
    - "On #/map/<slug> the maturity dots sit BELOW the sticky nav and scroll under it — they never overlap the nav row/logo/links."
  artifacts:
    - path: "docker/web/site/style-shared.css"
      provides: "Prose paragraph rhythm via --space-lg + .hub-storyline p rule"
    - path: "docker/web/site/app.js"
      provides: "renderHub leading-title-H1 strip (new); renderBlock leading-title-H1 strip refactored into a shared helper. Title-only — the bold tagline is KEPT."
    - path: "docker/web/site/style-base.css"
      provides: "Nav header sticky rule re-scoped so it no longer matches <header class='block-header'>"
  key_links:
    - from: "renderHub() hubIntroHtml (app.js ~625-628)"
      to: "the stored hub body's leading '# The Agent Economy' H1 (title only — tagline kept)"
      via: "guarded leading-title-H1 strip before marked.parse"
      pattern: "stripLeadingTitleH1"
    - from: "bare `header` selector (style-base.css:104)"
      to: "<header class='block-header'> emitted by renderBlock (app.js:733)"
      via: "selector scoping so sticky positioning only applies to the nav shell"
      pattern: "body > header"
---

<objective>
Fix three frontend-only rendering defects on the Agent Economy map surface (#/map and #/map/<slug>) plus a site-wide prose-spacing gap. Frontend only — docker/web/site/* — no backend, no economy_map data writes in the must-have path.

1. Duplicate hub title on #/map (the hub render path the prior block-only fix never touched). Title-only strip — the bold tagline is KEPT (operator decision: chrome has no subtitle, so the tagline is the sole instance, not a duplicate).
2. Body paragraphs butt together (no vertical rhythm) site-wide — most visibly in the hub body, which has NO paragraph-margin rule at all.
3. The block-page maturity dots overlap the sticky nav.

Purpose: the map surface went live in Phase 18 (count 2→8 published); these are the visible polish defects the operator hit reading the live published bodies. The renderer strip from quick task 260609-fpc (commit 19115b2) only covered the block H1 — the hub path and the bold-subtitle line were never touched, and the spacing/overlap bugs are pre-existing.

Output: edits to style-shared.css, app.js, and style-base.css on a BRANCH, each task atomic + independently committable, plus a SUMMARY. NO deploy, NO merge, NO DB write — those are operator-gated steps owned by the orchestrator.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@docker/web/site/app.js
@docker/web/site/style-shared.css
@docker/web/site/style-base.css
@docker/web/site/index.html
@.planning/quick/260609-fpc-fix-duplicate-block-title-on-map-slug/260609-fpc-SUMMARY.md

## Branch + deploy discipline (READ FIRST — operator constraint)

- ALL work in this plan is done on a BRANCH off `main` (the orchestrator creates/owns the branch; the operator wants branch + `/diff` review + scoped deploy).
- The executor AUTHORS + COMMITS the three fixes (one commit per task) and writes the SUMMARY. The executor does NOT deploy and does NOT merge.
- GOING LIVE is a SEPARATE OPERATOR-GATED step OWNED BY THE ORCHESTRATOR, NOT this executor's task: scoped rebuild from the MAIN tree —
  `cd /root/bitcoin_bot/docker && docker compose up -d --build web`
  (service key `web`; container `agentpulse-web`; entrypoint.sh substitutes `__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` at container start — MEMORY: "Web compose service name" — use the SERVICE key `web`, NOT `agentpulse-web`).
- Keep the `__SUPABASE_URL__` / `__SUPABASE_ANON_KEY__` placeholders BYTE-INTACT in app.js (entrypoint.sh substitutes at container start).
- Reuse the existing `--space-*` token scale; do NOT introduce a parallel spacing system or a magic px.

## Inventory findings already established (do not re-discover)

ISSUE 1 — stored bodies (anon published read, verified this session):
- Hub `agent-economy` body: line[02] = `# The Agent Economy`, line[04] = `**Capability is solved. Trust and coordination are not.**` (leading H1 == chrome title; bold subtitle is the first body line).
- Block `identity-trust` body: line[02] = `# Identity & Trust`, line[04] = `**The passport-and-references layer.**` (same shape).
- Hub chrome (renderHub, app.js:630-636): hardcoded `<h1 class="page-title">The Agent Economy</h1>` + an optional `<p class="hero-date">updated <date></p>` subline. The hub chrome has NO frontmatter-subtitle line — the "subtitle" the operator sees repeated is the body's `**bold**` first line, NOT a chrome subtitle. So the hub fix = strip the body's leading `# The Agent Economy` H1 AND the immediately-following `**bold**` subtitle paragraph.
- Hub body parse site: `trimHubBody(hubBodyMd)` → `marked.parse` into `<div class="hub-storyline">` (app.js:625-628). `trimHubBody` cuts the Tier-1/Tier-2 prose block-list but does NOT touch the leading H1 or bold subtitle.
- Block body parse site: renderBlock branch C (app.js:749-778) ALREADY strips the leading H1 (commit 19115b2) but NOT the bold subtitle line.
- Block chrome (renderBlock branch A, app.js:732-736): `<header class="block-header"><h1>{title}</h1>{pill}</header>` — the block title chrome. There is no separate chrome subtitle on the block; the operator's "subtitle repeat" on the block is the body's `**bold**` first line rendering right under the chrome H1.

ISSUE 2 — spacing tokens (style-base.css:52-59): `--space-xs:4px --space-sm:8px --space-md:16px --space-lg:24px --space-xl:32px --space-2xl:48px --space-3xl:64px`. Body is serif 18px / line-height 1.62 ≈ 29px line. Current prose `p` margin: `article p` and `.block-body p` BOTH set `margin-bottom: 16px` (= --space-md, a tight gap). `.hub-storyline` (style-shared.css:232) sets a container `margin-bottom` only — there is NO `.hub-storyline p` rule, so the hub's multi-paragraph published body (11 blocks) butts together with ZERO gap. Closest token to ~1 line of leading (~29px) is `--space-lg` (24px). DECISION: standardise prose paragraph rhythm on `--space-lg` and add the missing `.hub-storyline p` rule. NOTE: `var(--space-lg)` already appears ~10× in style-shared.css and `margin-bottom: 16px` appears on `article pre` too — so the verify gates below target the SPECIFIC prose-paragraph rules, not a raw count, to avoid a false pass.

ISSUE 3 — real cause (verified): renderBlock emits `<header class="block-header">` (app.js:733). style-base.css:104 has a BARE element selector `header { position:sticky; top:0; z-index:50; ... }` intended ONLY for the nav shell `<header>` in index.html — but a bare type selector ALSO matches `<header class="block-header">`. `.block-header` (style-shared.css:338) only sets flex/margin, never `position`, so the bare rule's sticky/top/z-index wins → the block's own header sticks to viewport-top and overlaps the nav. The maturity pill lives INSIDE that block-header, so the dots ride up over the nav. CONFIRMED: the nav shell `<header>` is the ONLY `<header>` that is a direct child of `<body>` (index.html:13→15); the block-header is nested inside `.container > main > #block-view > .content-area > #block-content`; the `.nav` inner-layout rules key off `.nav` (not `header`), and the bare `header` rule is the ONLY `position:sticky` in the stylesheets. FIX (chosen): change the bare `header {` selector to `body > header {` — the child-combinator matches the nav shell only and excludes the nested block-header. No app.js/index.html markup change needed.

## Sequencing (constraint: lowest-risk first)
Task 1 = paragraph-spacing CSS (additive, lowest risk). Task 2 = title/subtitle de-dup renderer (app.js logic). Task 3 = maturity-overlap selector scope (CSS positioning). One plan, three tasks, each its own commit.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Site-wide prose paragraph rhythm via --space-lg (+ the missing .hub-storyline p rule)</name>
  <files>docker/web/site/style-shared.css</files>
  <action>
Give long-form prose body containers a full-line vertical gap between paragraphs, reusing the existing `--space-lg` (24px) token (≈ one line of leading at 18px/1.62 ≈ 29px) — the closest token to the operator's "~a full line between paragraphs" without hardcoding a magic px (per the Issue-2 inventory above). Do NOT introduce a parallel spacing system.

Scope the changes to the prose/body containers ONLY (`article` newsletter body, `.block-body` map block body, `.hub-storyline` hub body) so nav, cards, the maturity row, the tier labels, and the status rows are untouched.

1. The MISSING rule (the most visible gap): add a `.hub-storyline p` rule. The hub published body is `marked.parse`'d into `<div class="hub-storyline">` (app.js:627) and currently has NO child-paragraph margin, so its 11 paragraphs butt together. Add `.hub-storyline p { margin-bottom: var(--space-lg); }` and `.hub-storyline p:last-child { margin-bottom: 0; }` (so the container's own bottom margin is not doubled). The hub body can render an `## How to read this map` heading — add modest top spacing for it via `.hub-storyline h2 { margin-top: var(--space-lg); }` reusing the token; do NOT restyle the heading typography itself (the `.tier-label`/`.page-title` rules are siblings outside `.hub-storyline` and stay unaffected).

2. Bump the existing block + article prose paragraph rhythm from the tight hardcoded 16px to the token: change the `.block-body p, .block-body li` rule's `margin-bottom: 16px` → `margin-bottom: var(--space-lg)` (style-shared.css:389), and the `article p` rule's `margin-bottom: 16px` → `margin-bottom: var(--space-lg)` (style-shared.css:603). These replace the magic 16px with the token AND widen the gap to ~1 line as the operator wants. Leave `article ul/ol`, `article li`, `article pre`, `article table`, and the `.block-body ul/ol` container margins at their current values — do NOT widen nested-list or code-block spacing (paragraph-to-paragraph is the operator's target; over-spacing lists reads loose).

3. p→heading rhythm: the existing `article h2/h3` and `.block-body h2` already carry top margins (`var(--space-xl)` / `28px` / `var(--space-lg)`); do NOT reduce them. The new paragraph `margin-bottom: var(--space-lg)` plus those top margins gives correct p→heading separation. No extra rule needed there.

DO NOT touch: the maturity pill `.seg` gap (`--space-xs`), `.card` internal `gap`, `.tier-label` margins, `.status-row` margins, the `.nav` gap (style-base.css), or `.timeline-entry` margins. Those are NOT prose paragraphs and must keep their compact rhythm.
  </action>
  <verify>
    <automated>cd /root/bitcoin_bot && grep -Pzoq '\.hub-storyline p[^{]*\{[^}]*margin-bottom:\s*var\(--space-lg\)' docker/web/site/style-shared.css && echo HUB-PARA-RULE-TOKENIZED || { echo "FAIL: .hub-storyline p rule missing or not using var(--space-lg)"; exit 1; }</automated>
    <automated>cd /root/bitcoin_bot && awk '/^article p \{/{f=1} f&&/margin-bottom/{if($0 ~ /var\(--space-lg\)/){print "ARTICLE-P-TOKENIZED"; exit 0} else {print "FAIL: article p still hardcodes margin-bottom"; exit 1}} f&&/^\}/{print "FAIL: article p has no margin-bottom"; exit 1}' docker/web/site/style-shared.css</automated>
    <automated>cd /root/bitcoin_bot && awk '/\.block-body p,/{f=1} f&&/margin-bottom/{if($0 ~ /var\(--space-lg\)/){print "BLOCK-P-TOKENIZED"; exit 0} else {print "FAIL: .block-body p still hardcodes margin-bottom"; exit 1}} f&&/^\}/{print "FAIL: .block-body p has no margin-bottom"; exit 1}' docker/web/site/style-shared.css</automated>
    <automated>cd /root/bitcoin_bot && o=$(grep -o '{' docker/web/site/style-shared.css | wc -l); c=$(grep -o '}' docker/web/site/style-shared.css | wc -l); [ "$o" = "$c" ] && echo "CSS-BRACES-BALANCED ($o)" || { echo "FAIL: brace mismatch open=$o close=$c"; exit 1; }</automated>
  </verify>
  <done>
`.hub-storyline p` rule exists with `margin-bottom: var(--space-lg)` (+ a `:last-child` zero-out); `.block-body p` and `article p` use `var(--space-lg)` (not the hardcoded 16px); no non-prose selector (cards, pill, nav, tier-label, status-row, timeline) was widened; CSS braces balance (still parses). Hub, block, and newsletter article bodies show a full-line gap between paragraphs.
  </done>
</task>

<task type="auto">
  <name>Task 2: De-dup the hub + block TITLE in the renderer (extend the guarded leading-H1 strip to renderHub via a shared helper) — TITLE ONLY, tagline KEPT</name>
  <files>docker/web/site/app.js</files>
  <action>
The chrome title is canonical; the stored bodies still carry a leading `# <Title>` H1 (verified: hub `# The Agent Economy`; block `# Identity & Trust`). Strip ONLY that duplicate leading title H1 — defensively, mutating only a LOCAL copy of the markdown string before `marked.parse`, never the DB and never the `block`/title args.

OPERATOR DECISION (2026-06-09): KEEP the bold tagline first line (e.g. hub `**Capability is solved. Trust and coordination are not.**`, block `**The passport-and-references layer.**`). The chrome has NO subtitle element, so the bold line is the SOLE instance of the tagline — it is NOT a duplicate, and stripping it would DELETE the tagline. Do NOT strip it. This task is TITLE-H1-ONLY.

Factor a single small pure helper to avoid duplicating the logic across renderHub and renderBlock. Add a module-scoped function (near `trimHubBody`, ~app.js:74) named `stripLeadingTitleH1(md, title)` that:
  - Returns `md` unchanged on falsy input (defensive — never silently drops content it cannot bound).
  - Operates on a LOCAL split-by-`\n` copy.
  - Find the FIRST non-empty line. If it matches the leading-ATX-heading regex already used in renderBlock (`/^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$/`) AND the captured heading text equals `title` after `.trim().toLowerCase()`, splice that ONE line out. This is the EXACT guarded behavior from commit 19115b2 (preserve its safety argument: non-match → byte-identical no-op; the title is only ever used in a plain string equality, never as a regex pattern, so regex-special title chars are inherently safe). Do NOT touch any bold/`**...**` line — the tagline stays.
  - Rejoin with `\n` and return; if it did not match, the returned string is byte-equal to the input (pure no-op). Leave the following blank line + all subsequent content (including the bold tagline) intact.

Wire it in BOTH paths:
  1. renderBlock branch C (app.js:749-778): REPLACE the existing inline H1-strip block with `var renderMd = stripLeadingTitleH1(bodyMd, block.title);` then `bodyHtml = '<section class="block-body">' + marked.parse(renderMd) + '</section>';`. Net effect vs today: IDENTICAL behavior (still strips the leading title H1, still keeps the tagline) — this is a pure refactor of the inline strip into the shared helper.
  2. renderHub hubIntroHtml (app.js:625-628): the hub body currently goes `trimHubBody(hubBodyMd)` → marked.parse. Compose: `var trimmedHubBody = stripLeadingTitleH1(trimHubBody(hubBodyMd), 'The Agent Economy');`. The hub chrome `<h1>` text is the hardcoded literal `'The Agent Economy'` (app.js:631) — pass that exact string so the body's `# The Agent Economy` matches and is stripped. Keep the existing `trimmedHubBody ? marked.parse(...) : escapeHtml(HUB_STORYLINE)` fallback intact — when `hubBodyMd` is null (pre-publish / anon-no-draft) BOTH `trimHubBody` and `stripLeadingTitleH1` receive null and return null, so the HUB_STORYLINE fallback path is unchanged (provable no-op pre-publish).

Order matters in the hub: run `trimHubBody` FIRST (it cuts the Tier-1 block-list tail), THEN `stripLeadingTitleH1` on the result (it strips the leading title from the head) — composing in that order leaves the thesis prose + the bold tagline + `## How to read this map` framing intact, minus only the duplicate title.

Do NOT touch: the hub chrome `<h1 class="page-title">The Agent Economy</h1>` + `updated` subline (those carry the canonical title + timestamp and MUST stay — the operator explicitly does not want the chrome title hidden), `updateHero`, `loadBlock`/`loadHub` fetch logic, the maturity pill, CSS, economy_map data, and the `__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` placeholders (app.js:4-5, must stay byte-identical).
  </action>
  <verify>
    <automated>cd /root/bitcoin_bot && node --check docker/web/site/app.js && echo JS-SYNTAX-OK</automated>
    <automated>cd /root/bitcoin_bot && [ "$(grep -c '__SUPABASE_URL__\|__SUPABASE_ANON_KEY__' docker/web/site/app.js)" -ge 2 ] && echo PLACEHOLDERS-INTACT || { echo "FAIL: placeholders altered"; exit 1; }</automated>
    <automated>cd /root/bitcoin_bot && python3 scripts/verify_economy_map_crosslinks.py --guard-only</automated>
    <automated>cd /root/bitcoin_bot && [ "$(grep -c 'stripLeadingTitleH1' docker/web/site/app.js)" -ge 3 ] && echo HELPER-WIRED-BOTH-PATHS || { echo "FAIL: helper not defined + called in both renderHub and renderBlock (expected >=3 occurrences)"; exit 1; }</automated>
    <automated>cd /root/bitcoin_bot && ! grep -q 'stripLeadingTitleAndSubtitle' docker/web/site/app.js && echo NO-SUBTITLE-STRIP || { echo "FAIL: subtitle-strip variant present — operator decided title-only (keep tagline)"; exit 1; }</automated>
  </verify>
  <done>
A single guarded helper `stripLeadingTitleH1(md, title)` strips ONLY the leading title-matching ATX H1 (the bold tagline is KEPT); it is called from BOTH renderHub (composed after trimHubBody, title arg `'The Agent Economy'`) and renderBlock (refactoring the prior inline H1-only strip) — `stripLeadingTitleH1` appears >=3× (1 def + 2 calls). The hub chrome `<h1>` + `updated` line are untouched. Pre-publish (null body) is a provable no-op (HUB_STORYLINE fallback unchanged). `node --check` passes; placeholders intact (>=2); crosslinks guard PASS. renderBlock behavior is byte-equivalent to the prior fix (title stripped, tagline kept); renderHub now strips its duplicate title H1 too. A body whose first heading legitimately differs is never altered (non-match → byte-equal no-op).
  </done>
</task>

<task type="auto">
  <name>Task 3: Stop the block-header from sticking — re-scope the bare `header` sticky rule to the nav shell only</name>
  <files>docker/web/site/style-base.css</files>
  <action>
ROOT CAUSE (verified): renderBlock emits `<header class="block-header">` (app.js:733). The bare element selector `header { position:sticky; top:0; z-index:50; background:...; backdrop-filter:...; border-bottom:... }` at style-base.css:104 was meant ONLY for the nav shell `<header>` in index.html, but a bare type selector ALSO matches `<header class="block-header">`. `.block-header` (style-shared.css:338) sets only flex/margin and never `position`, so the bare rule's sticky/top/z-index wins → the block's own header sticks to viewport-top and rides over the nav, dragging the maturity dots (which live inside block-header) up onto the nav row.

FIX (chosen — lowest-risk, no markup change): re-scope the sticky nav rule so it targets ONLY the nav shell, which is a DIRECT CHILD of `<body>` (index.html:15), whereas the block-header is nested deep inside `.container > main > #block-view > .content-area > #block-content`. Change the selector at style-base.css:104 from `header {` to `body > header {`. The `body > header` child-combinator matches the nav shell only and excludes the nested `<header class="block-header">`. The block-header then keeps ONLY its `.block-header` rules (static flow, flex baseline), sits inside `#block-content` below the sticky nav, and scrolls under it normally — the maturity dots no longer overlap the nav.

CONFIRMED SAFE (inventory): there is exactly one `<header>` direct child of `<body>` (the nav shell, index.html:15) and one nested `<header class="block-header">` (renderBlock). `body > header` keeps the nav styling intact and drops it from the block-header. The `.nav` inner-layout rules (style-base.css:114) are unaffected (they key off `.nav`, not `header`). The bare `header` rule is the only `position:sticky` in either stylesheet.

Update the comment above the rule to note the scope: the sticky chrome is the nav shell (`body > header`) ONLY; the in-content `<header class="block-header">` must NOT inherit sticky/z-index (that was the maturity-overlap bug). Do NOT change the `top`, `z-index`, `background`, `backdrop-filter`, or `border-bottom` values — only the selector scope.

Do NOT add a `position:static` override on `.block-header` as the fix (re-scoping the source rule is cleaner and avoids a second rule fighting the first). Do NOT touch index.html markup or app.js. (An explicit `.block-header { position: static }` belt-and-suspenders is OPTIONAL and only warranted if a manual check shows residual stickiness — the `body > header` scope should fully resolve it since the only `position` declaration reaching `.block-header` is removed.)
  </action>
  <verify>
    <automated>cd /root/bitcoin_bot && grep -q 'body > header' docker/web/site/style-base.css && echo NAV-RULE-RESCOPED || { echo "FAIL: nav header rule not re-scoped to body > header"; exit 1; }</automated>
    <automated>cd /root/bitcoin_bot && ! grep -Eq '^header[[:space:]]*\{' docker/web/site/style-base.css && echo NO-BARE-HEADER-SELECTOR || { echo "FAIL: bare 'header {' selector still present — block-header will still inherit sticky"; exit 1; }</automated>
    <automated>cd /root/bitcoin_bot && grep -Pzoq 'body > header[^{]*\{[^}]*position:\s*sticky' docker/web/site/style-base.css && echo STICKY-STILL-ON-NAV || { echo "FAIL: nav lost its sticky positioning"; exit 1; }</automated>
    <automated>cd /root/bitcoin_bot && o=$(grep -o '{' docker/web/site/style-base.css | wc -l); c=$(grep -o '}' docker/web/site/style-base.css | wc -l); [ "$o" = "$c" ] && echo "CSS-BRACES-BALANCED ($o)" || { echo "FAIL: brace mismatch open=$o close=$c"; exit 1; }</automated>
  </verify>
  <done>
The sticky/`top:0`/`z-index:50` rule applies via `body > header` to the nav shell ONLY; the bare `header {` selector no longer exists, so `<header class="block-header">` no longer inherits sticky positioning. The nav stays sticky; the block-page maturity dots sit below the nav in content flow and scroll under it (no overlap). No index.html or app.js change. CSS braces balance (parses cleanly).
  </done>
</task>

</tasks>

<verification>
All three tasks must leave the main-tree gates green (the executor runs these on the BRANCH; values match the live-code checks the orchestrator will re-run):

- `cd /root/bitcoin_bot && node --check docker/web/site/app.js && echo JS-SYNTAX-OK` → JS-SYNTAX-OK (after Task 2).
- `cd /root/bitcoin_bot && grep -c '__SUPABASE_URL__\|__SUPABASE_ANON_KEY__' docker/web/site/app.js` → `2` (placeholders byte-intact).
- `cd /root/bitcoin_bot && python3 scripts/verify_economy_map_crosslinks.py --guard-only` → `RESULT: PASS` (PLACEHOLDER-INTACT + SVC-ROLE-NOT-IN-WEB-DEPLOY-PATH), exit 0.
- CSS sanity: the per-task grep/awk gates confirm `.hub-storyline p` + tokenized `article p`/`.block-body p` (Task 1) and `body > header` with no bare `header {` (Task 3), plus brace balance on both stylesheets.

NOT run by the executor (operator/orchestrator-owned): `python3 scripts/verify_economy_map_publish.py` is the post-PUBLISH anon harness — it is unrelated to these render fixes and requires the live published set; do not gate these tasks on it.
</verification>

<success_criteria>
- #/map: "The Agent Economy" renders once (chrome page-title with the `updated` line); the body's leading `# The Agent Economy` H1 no longer appears in the hub body. The bold tagline `**Capability is solved...**` is KEPT (shows once, in the body).
- #/map/<slug>: the block title renders once (chrome header); the body's leading title H1 is stripped (unchanged from the prior fix). The bold tagline (e.g. `**The passport-and-references layer.**`) is KEPT.
- Hub body, block body, and newsletter article body paragraphs show a full-line vertical gap (`--space-lg`), no butted paragraphs; nav/cards/maturity-row/status-rows unchanged.
- #/map/<slug>: maturity dots sit below the sticky nav and scroll under it — no overlap with the nav row/logo/links.
- Only docker/web/site/style-shared.css, app.js, style-base.css changed. Placeholders intact. No economy_map data write. No deploy, no merge by the executor.
- Three atomic commits (one per task) on the branch; SUMMARY written.
</success_criteria>

<deploy_and_data_notes>
OPERATOR-GATED, NOT executor work:
- Going live: from the MAIN tree, `cd /root/bitcoin_bot/docker && docker compose up -d --build web` (service key `web`; container `agentpulse-web`; entrypoint.sh substitutes the placeholders at container start; live verification is on the substituted copy). Owned by the orchestrator after operator `/diff` review + approval.
- OPTIONAL / FLAGGED — body re-publish (belt-and-suspenders): the renderer strip (Task 2) FULLY neutralizes the duplicate title + bold subtitle at render time, so the stored bodies do NOT need rewriting for the must-have. A source/body re-publish (clean the leading `# <Title>` + `**subtitle**` out of the stored economy_map rows so the markdown is canonical at rest too) is OPTIONAL and, given the renderer strip already handles it, arguably overkill — FLAGGED for operator decision, NOT baked into any executor task and NOT in the must-have path. If the operator wants it, it is a separate operator-gated step using the existing append-only canonical-body-rewrite path (scripts/load_economy_map_content.py rewrite → publish RPC), never a raw UPDATE — out of scope for this plan.
</deploy_and_data_notes>

<output>
Create `.planning/quick/260609-ivq-map-page-rendering-fixes-hub-duplicate-t/260609-ivq-SUMMARY.md` when done.
</output>
