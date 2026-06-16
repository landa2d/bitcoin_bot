---
phase: 23-distinct-newsletter-excerpts
verified: 2026-06-16T10:41:41Z
status: passed
score: 3/3 must-haves verified
overrides_applied: 0
---

# Phase 23: Distinct Newsletter Excerpts — Verification Report

**Phase Goal:** The archive list stops showing the same opening words on consecutive editions — the boilerplate intro is skipped and each row shows a genuinely-distinct first sentence in the indexed-row format — with no schema or pipeline change.
**Verified:** 2026-06-16T10:41:41Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Verification Method Note

The source file `/root/bitcoin_bot/docker/web/site/app.js` contains 3 NUL bytes (the WR-01 NUL-sentinel fix for the Safari lookbehind crash). This causes `grep` without the `-a` flag to treat the file as binary and silently return no matches. All grep commands in this report used the `-a` (text mode) flag. The node-based sanity checks are unaffected. The NUL bytes are intentional: they are the sentence-boundary sentinels in `splitSentences()`.

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC#1 | Editions 29 and 30 show different preview text (boilerplate header + recap skipped; first distinct sentence shown) | VERIFIED | Live harness ran against production anon REST: ed29-tech = "This week it got specific. Researchers exposed BadHost..." (193 chars); ed30-tech = "The payments thesis crossed into consumer scale: Block kicked off Cash App's phased stablecoin rollout..." (208 chars). Strategic mode also distinct. All 7 live assertions PASS. |
| SC#2 | Archive list renders in indexed-row format: number · title · one-line summary · date | VERIFIED | `renderList()` app.js:484–497 emits `<a class="row" href="#/edition/N">` with `.num`, `.title`, `.sum`, `.date`. CSS block in style-shared.css:204–214 defines the 3-column grid (`56px 1fr auto`). `grep -ac 'class="row"'` = 1 in source and in served `/srv/app.js`. Operator visual confirmation on live site. |
| SC#3 | Strip-at-render only: no schema change, no stored summary field, no pipeline change | VERIFIED | Latest migration file is `043_economy_map_hub_and_negotiation_blocks.sql` (Phase 16). Zero migration files touched in Phase 23. `loadList()` query frozen: `.in('status', ['published','preview'])` = 2 occurrences (unchanged baseline); `.eq('status')` = 11 (unchanged). `__SUPABASE_URL__` placeholder intact in source (count=1). |

**Score:** 3/3 truths verified

---

## Per-Decision Realization Check (D-01..D-10)

| Decision | What was required | Evidence in code | Verdict |
|----------|------------------|-----------------|---------|
| D-01 | Strip the `## Read This, Skip the Rest` H2 before excerpting; no-op if absent | `extractDistinctExcerpt()` app.js:209–213: line-based splice only when heading text equals `'read this, skip the rest'` (case-insensitive); defensive no-op otherwise | VERIFIED |
| D-02 | After the header, skip recap sentence(s) and surface the "This week…" thesis | app.js:218–220: `while (sentences.length > 1 && RECAP_OPENER_RE.test(sentences[0])) sentences.shift()`. Live harness confirms ed29/ed30 thesis sentences are surfaced. | VERIFIED |
| D-03 | Match look-back recap phrases; never over-strip; keep ≥1 sentence; stacked recaps both skipped | `RECAP_OPENER_RE` app.js:149: `/^(?:last\s+(?:week|month)|for\s+weeks|for\s+(?:\d+|one|...|many)\s+editions|(?:\d+|...|many)\s+editions\s+ago)\b/i`. Loop guard `sentences.length > 1` prevents dropping the last. Offline harness tests: no-recap-keep, stacked-recap, closing-quote-split — all PASS. | VERIFIED |
| D-04 | Thin-pivot append: sentence below 40-char floor gets next sentence appended | `EXCERPT_MIN_CHARS = 40` app.js:155. app.js:222–224: `if (result.length < EXCERPT_MIN_CHARS && sentences.length > 1) result = result + ' ' + sentences[1]`. Live harness confirms ed29-tech "This week it got specific." (26 chars) → appended → 193 chars total. | VERIFIED |
| D-05 | `[text](url)` → `text`; bare URLs dropped; no leaked `(https://…)` in any summary; crude `.substring(0, 150)` removed | `cleanExcerptMarkdown()` app.js:166–169: step 1 `[text](url)→text`, step 2 bare URL drop, step 3 residual marker strip. `grep -ac 'substring(0, 150)'` = 0. ed30-tech offline + live harness: no `https://`, no `](`. | VERIFIED |
| D-06 | 2-line CSS clamp; full text stays in DOM (no hard truncation) | style-shared.css:238–247: `display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;` CSS sanity check PASS: `/-webkit-line-clamp:\s*2/.test(css)` = true. No character truncation in JS. | VERIFIED |
| D-07 | Graceful degradation: empty excerpt omits `.sum` line; never legacy 150-char clamp; never fabricated text | app.js:487: `var sumFragment = sum ? '<p class="sum">...' + escapeHtml(sum) + '...</p>' : '';` — conditional emit only on non-empty. `extractDistinctExcerpt(null) === ''` and `extractDistinctExcerpt('') === ''` (offline harness PASS). `grep -ac 'substring(0, 150)'` = 0. | VERIFIED |
| D-08 | Summary is mode-aware via `getModeContent()` | app.js:486: `var sum = extractDistinctExcerpt(getModeContent(n))`. `getModeContent()` app.js:696–699 returns `content_markdown_impact` in strategic mode. Live harness confirms different text in Technical vs Strategic for both ed29 and ed30. | VERIFIED |
| D-09 | Indexed-row grid: `num=edition_number`, `title=getModeTitle()` (Phase 22 EDITION_SUFFIX_RE reused), `date=formatDate(published_at)`; whole row is `#/edition/<n>` link | app.js:489–496: `<a href="#/edition/' + n.edition_number + '" class="row">`, `.num` = raw numeric, `.title` = `escapeHtml(getModeTitle(n))` (EDITION_SUFFIX_RE at app.js:52 intact), `.date` = `escapeHtml(formatDate(n.published_at))`. | VERIFIED |
| D-10 | Token-only CSS; zero hardcoded hex; `--line-soft`→`--line`, `--violet`→`--accent` | style-shared.css:182–268: Phase 23 block. CSS node check: `grep -ac 'var(--line-soft)\|var(--violet)'` = 0 (stale tokens appear only in comments, not in rules). Hex scan over the new block: empty. `--line-soft`/`--violet` notes documented in the comment header (line 188–190). | VERIFIED |

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docker/web/site/app.js` | RECAP_OPENER_RE + cleanExcerptMarkdown / splitSentences / extractDistinctExcerpt + rewritten renderList() | VERIFIED | 1474 lines. 3 NUL sentinel bytes (WR-01 fix). Sentinels confirmed via Read tool lines 130–227. All 5 excerpt symbols found: RECAP_OPENER_RE(2), splitSentences(2), extractDistinctExcerpt(3), cleanExcerptMarkdown(3), EXCERPT_MIN_CHARS(2). |
| `docker/web/site/style-shared.css` | .row / .num / .title / .sum (2-line clamp) / .date / .archive-label token-only grid | VERIFIED | Phase 23 block at lines 182–267. `.row` definitions (9), `.archive-label` (1). 4-property clamp at lines 243–246. CSS sanity PASS. Legacy `.article-entry` (2 rules) and `.entry-preview` (1 rule) dormant but retained. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `renderList()` | `extractDistinctExcerpt(getModeContent(n))` | mode-aware excerpt pipeline (D-02/D-08) | WIRED | app.js:486 — `var sum = extractDistinctExcerpt(getModeContent(n))` |
| `renderList()` | `escapeHtml(title)` / `escapeHtml(sum)` | XSS safety at innerHTML sink | WIRED | app.js:487, 492, 495 — title, sum, date all pass through `escapeHtml()` |
| `style-shared.css .row .sum` | `-webkit-line-clamp:2` | D-06 visual clamp, full text retained | WIRED | style-shared.css:244 — confirmed by CSS node check |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `renderList()` | `getModeContent(n)` | `loadList()` → Supabase `.from('newsletters').select('*').in('status',...)` → `window.currentNewsletterList` | Yes — Supabase query returns live `content_markdown` / `content_markdown_impact` columns; live harness confirms non-empty real prose for ed29/ed30 | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Offline 23-assertion harness | `node /tmp/excerpt_check.mjs` | ALL ASSERTIONS PASSED (all 23 ok lines printed, exit 0) | PASS |
| Live real-data harness | `node /tmp/live_excerpt_verify.mjs` | ALL LIVE-DATA ASSERTIONS PASSED (exit 0); ed29-tech 193 chars, ed30-tech 208 chars, both modes distinct, no leak | PASS |
| app.js syntax | `node --check docker/web/site/app.js` | SYNTAX OK (exit 0) | PASS |
| CSS sanity (braces balanced, no stale tokens, has clamp) | `node -e "..."` | CSS sanity: PASS | PASS |
| WR-01 closed (no lookbehind) | `grep -ac '(?<='` | 0 in source; 0 in served `/srv/app.js` | PASS |
| Deployed container healthy | `docker compose ps web` | agentpulse-web Up (6 min at time of check), ports 80/443 bound | PASS |
| Served file substituted | `docker compose exec web grep -ac '__SUPABASE_URL__' /srv/app.js` | 0 (substituted by entrypoint.sh sed; real host present via `grep -ac 'supabase.co'` = 1) | PASS |
| Served file carries indexed-row format | `docker compose exec web grep -ac 'class="row"' /srv/app.js` | 1 | PASS |
| Served file: no crude strip | `docker compose exec web grep -ac 'substring(0, 150)' /srv/app.js` | 0 | PASS |
| NUL sentinel survives entrypoint substitution | Source: 3 NUL bytes; served file size 79458 vs source 79247 (delta = URL substitution only) | 3 NUL bytes in source confirmed; served/source size delta consistent with URL subst only | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| EXCERPT-01 | 23-01-PLAN.md, 23-02-PLAN.md | Consecutive editions show distinct preview; boilerplate skipped; indexed-row format; ed29/30 different; strip-at-render, no schema change | SATISFIED | SC#1/SC#2/SC#3 all verified above; live harness run against production data confirms distinctness; 0 migrations in Phase 23 |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `docker/web/site/app.js` | 57 | `const LIVE_TENSION_PLACEHOLDER = 'TBD — set via /map-tension'` | Info | Pre-existing before Phase 23 (confirmed by `git show bbda2f4~1`). This is a runtime content placeholder for the economy map live_tension feature, not a code completion marker. Not a Phase 23 debt. |

No TBD/FIXME/XXX in Phase 23-introduced code. No stubs or placeholder text in the excerpt helpers or renderList().

---

## Human Verification Required

None. All success criteria verified programmatically and by live harness against production data. The operator's visual confirmation was captured in the 23-02 SUMMARY and REVIEW (operator "approved" on live site for indexed rows, ed29/30 both modes distinct, 2-line clamp, no regression on hero/mode toggle/deep-links/maturity pill).

---

## Actual Command Output (Key Evidence)

### Offline harness (23 assertions, all pass)
```
ok  - cleanExcerptMarkdown converts [text](url) -> text and drops the URL
ok  - splitSentences does NOT split on a colon
ok  - splitSentences does NOT split on an em-dash
ok  - splitSentences splits "A. B" into two
ok  - SC#1 Technical: ed29 != ed30
ok  - SC#1 Strategic: ed29 != ed30
ok  - D-04: ed29 tech thin-pivot append fired (starts "This week it got specific", len > 40)
ok  - D-05: ed30 tech contains "Block kicked off Cash App", no https:// and no ](
ok  - D-02/D-03: ed28 "For three editions..." recap skipped, pivot surfaced
ok  - D-03: ed29 impact closing-quote-aware split (recap ..."The End of Trust." skipped)
ok  - D-03: stacked recaps both skipped, a sentence retained
ok  - D-03: no recap match -> keep sentence 1 (no silent drop)
ok  - D-07: empty/null -> "" (caller omits .sum)
ok  - renderList emits two .row anchors
ok  - rows are #/edition/<n> deep-links
ok  - ed30 row .sum is cleaned (no leaked URL)
ok  - no legacy .article-entry markup
ok  - static Archive label present
ok  - D-07: empty excerpt omits the .sum element
ok  - D-07: no legacy 150-char ellipsis fallback
ok  - XSS: hostile title is escaped
ok  - D-08: mode flip changes the row markup
ok  - D-08: strategic mode uses the impact title

ALL ASSERTIONS PASSED
```

### Live harness (real production ed29/ed30)
```
=== TECHNICAL mode (content_markdown) ===
  [ed29 tech] (193 chars)
    "This week it got specific. Researchers exposed BadHost, a critical vulnerability in Starlette —
     a Python web framework with 325 million weekly downloads that powers countless agent deployments."
  [ed30 tech] (208 chars)
    "The payments thesis crossed into consumer scale: Block kicked off Cash App's phased stablecoin
     rollout to nearly 60 million users, deploying USDC across Solana, Ethereum, Polygon, and Arbitrum simultaneously."

=== STRATEGIC mode (content_markdown_impact) ===
  [ed29 impact] (69 chars)
    "This week the gap got more concrete, and the timing is uncomfortable."
  [ed30 impact] (47 chars)
    "This week both halves of that story moved hard."

ALL LIVE-DATA ASSERTIONS PASSED
```

### Frozen invariants
```
.in('status', ['published', 'preview']) count = 2  (unchanged)
.eq('status')                           count = 11 (unchanged)
substring(0, 150)                       count = 0  (removed)
class="article-entry" in app.js         count = 0  (removed from renderList)
__SUPABASE_URL__ in source              count = 1  (placeholder intact)
__SUPABASE_URL__ in served /srv/app.js  count = 0  (substituted by entrypoint)
lookbehind (?<= in app.js               count = 0  (WR-01 closed)
NUL bytes in source app.js              count = 3  (WR-01 NUL sentinels)
```

---

## Gaps Summary

No gaps. All 3 ROADMAP success criteria are verified. All 10 CONTEXT decisions D-01..D-10 are realized in the shipped code. The WR-01 lookbehind regression is closed. The strip-at-render constraint holds (zero migrations in Phase 23). The deployed container is healthy and serving the substituted, indexed-row-format app.js.

---

_Verified: 2026-06-16T10:41:41Z_
_Verifier: Claude (gsd-verifier)_
