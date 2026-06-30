# Phase 28: Layer 1 Deterministic Gate - Research

**Researched:** 2026-06-30
**Domain:** No-LLM deterministic fabrication + mechanical-editorial gate (Python, newsletter service)
**Confidence:** HIGH (all three code-verification TODOs resolved against source with line citations)

## Summary

Phase 28 ships a standalone, no-LLM module `docker/newsletter/deterministic_gate.py` exposing `run_deterministic_gate(draft, fact_base, prior_edition) -> flags`, plus a pytest golden-draft suite with mocked network. The gate **only emits a structured flags object** (matching migration 045's `deterministic_flags` JSONB) — it never wires into the poller, never writes `edition_evals`, never rebuilds the container (all Phase 30). It composes three layers: (1) **reuse** `verify_draft()` (verification.py) for tier-1 entity / tier-2 stat fabrication detection — inheriting the Edition-34-calibrated ~0-FP stop-list; (2) **thin additions on top** — a live-network layer (GitHub repo+star, URL HEAD) and a fact-base membership check for arXiv IDs and an entity-merge refinement; (3) **mechanical checks** (H1/title echo, reading-mode-label leak, recycled closer, duplicated stat vs the previous edition).

The three TODOs resolved: **(1) GATE-05** — `verify_draft` tier-1 is **any/union-of-all-sources + fuzzy substring** (verification.py:299-480, 499-514), NOT single-source-verbatim, so a thin per-source verbatim refinement for composite entities is required on top (do NOT rebuild). **(2) GATE-08** — `verify_draft(prose, input_data)` takes **one dict** and dispatches internally on `input_data.get('blocks')` (verification.py:315); the canonical block_v1 adapter already exists at newsletter_poller.py:1737-1749 (wrap as `{'blocks':[...], 'tracked_entity_signals':..., 'trending_tools':..., 'predictions':...}`), single-pass passes `input_data` verbatim. **(3) GATE-06** — body-start marker `## Read This, Skip the Rest` is **verbatim** (block_pipeline.py:661; newsletter_poller.py:602, 2120); there is **no single canonical "READING MODE" literal in the body today** — the realistic leak vectors are the writer audience-prefix `AUDIENCE:` literals (block_pipeline.py:348,350) and the marketing/web mode labels (`BUILDER MODE`/`IMPACT MODE` processor:10047; `Technical`/`Strategic` web toggle index.html:65-66) — so a curated blacklist is needed and the exact list is the one genuine operator decision.

**Primary recommendation:** Build a single `deterministic_gate.py` that imports `verify_draft`, `_extract_claims_from_prose`, and the `_ARXIV_ID` / `_STATISTIC` regexes from `verification.py`; adds a network layer (sync `httpx`, matching the processor's GitHub convention) with the D-01..D-03 three-outcome semantics; adds a per-source verbatim entity-merge refinement; and emits `{fabrication:[...], unverified:[...], mechanical:[...], meta:{...}}` with `unverified` as a first-class key. Verdict computation and action stay in Phase 30.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Claim extraction + tier-1/tier-2 fabrication | Newsletter service (reuse `verification.py`) | — | Calibrated engine already lives here; the fact base only exists in-process in this container |
| GitHub repo + star-drift check (GATE-02) | Newsletter service (new network layer) | GitHub API (external) | Deterministic existence/count check; matches processor's existing `api.github.com` convention |
| URL liveness HEAD check (GATE-03) | Newsletter service (new network layer) | Target hosts (external) | Sync `httpx.head`, 5s timeout |
| arXiv-ID + named-study fact-base check (GATE-04) | Newsletter service (thin addition) | — | Reuses `_ARXIV_ID`; adds a membership test the engine currently lacks |
| Entity-merge refinement (GATE-05) | Newsletter service (thin addition) | — | Per-source verbatim check the flattened engine can't do |
| Mechanical checks H1/leak/closer/stat (GATE-06/07) | Newsletter service (new, regex-only) | — | Pure string ops on draft + prior edition |
| Flags object → `deterministic_flags` JSONB | Newsletter service (contract) | Phase 30 sequencer / `edition_eval.write_eval_row` | Phase 28 emits; Phase 30 persists + computes verdict |

All capabilities are single-tier (the newsletter Python service). There is no browser/API/DB tier split — the gate is an in-process pure function plus outbound HTTP to GitHub and arbitrary URLs.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01 (network-failure semantics):** Three distinct deterministic outcomes per network check — do NOT collapse:
  - **confirmed-fabricated** → HTTP 404/410 (and GitHub API 404 for a repo) → a fabrication flag.
  - **unverified** → timeout, connection-refused, 5xx, GitHub rate-limit/403-quota → a distinct, **visible** state on the flags object; surfaces as `escalated`/error — **never** a fabrication flag and **never** folded into "pass."
  - **verified-ok** → 200 (and, for GitHub, star-count within the >20% band when the draft asserts a count).
  - Overrides GATE-03's literal "connection failure or 4xx/5xx → flag" wording (a transient 5xx/rate-limit is unverified, not fabricated).
- **D-02:** Retry **once** on a *transient* failure (timeout / 5xx / connection error) before settling on `unverified`. **Never** retry a definitive 404.
- **D-03:** Dedup + per-run cache: extract the unique set of owner/repo refs and URLs, check each **exactly once**, reuse for every occurrence. Checks run **sequentially**. GitHub token from env if present (5000/hr) else unauthenticated.
- **D-04:** **Reuse `verify_draft()`** as the fabrication engine — tier-1 (named entity not in any source), tier-2 (stats), existing arXiv-ID pattern cover GATE-04/05. Inherits the calibrated ~0-tier-1-FP stop-list (Edition-34-tuned). Phase 28 adds ONLY the network-liveness layer (D-01..D-03) + a GATE-08 fact-base adapter on top. Do NOT rebuild claim extraction or duplicate the stop-list.
- **D-05:** **Build-only.** Ship a standalone module — e.g. `run_deterministic_gate(draft, fact_base, prior_edition) -> flags` — whose flags object matches migration 045's `deterministic_flags` JSONB, plus a golden-draft test suite (mocked network). **No** `newsletter_poller` wiring, **no** `edition_evals` write, **no** container rebuild. Worktree-safe.
- **D-06:** Recycled-closer / duplicated-stat uses **normalized-exact** matching against the **previous published edition**: lowercase + collapse whitespace + strip trailing punctuation, then exact-match the closer line and each numeric-stat token (number+unit). **No fuzzy similarity threshold.**

### Claude's Discretion
- Internal shape of the flags object beyond matching `deterministic_flags` JSONB (per-check sub-keys; how `unverified` is represented vs `fabricated`).
- The golden-draft test fixtures (seed at least: ed-36 invented "MCP authentication" study, ed-34 "GroupMemBench", a fake arXiv ID, a dead URL/404 repo, a transient-5xx→unverified case, a recycled closer, a leaked reading-mode label) with mocked network responses.
- Sequential network execution (chosen over a concurrency pool).

### Deferred Ideas (OUT OF SCOPE)
- Acting on verdicts (status flips, `do_not_publish`, Gato escalation), the `enforce` flag, the sequencer invocation at the two save points, `edition_evals` persistence of the deterministic layer → **Phase 30 (WIRE-01..06)**.
- The LLM judge + feedback-rewrite loop → **Phase 29 (JUDGE/LOOP)**.
- Fuzzy/similarity-based recycling detection — explicitly rejected this phase.
- Bounded-concurrency network checks — deferred; sequential is sufficient.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GATE-01 | Gate runs on every edition (both versions) before any LLM judge/rewrite; short-circuits to hold+escalate on any fabrication flag with zero LLM/rewrite attempts. | Module is a pure no-LLM function; Phase 28 emits flags only — the short-circuit *action* is Phase 30. Gate must run both `content_markdown` + `content_markdown_impact` (mirrors verify_draft tech+impact at poller:1756-1757). |
| GATE-02 | Every owner/repo + `github.com/owner/repo` ref checked against live GitHub API (token via env, else unauthenticated): 404→fabricated; 200 with draft star-count differing >20% from `stargazers_count`→flag. | New network layer; reuse processor convention (processor:1134-1136 headers, `httpx.Client`). Use `/repos/{owner}/{repo}` (not search). D-01 three-outcome mapping. |
| GATE-03 | Every URL gets a HEAD request (5s timeout); D-01 reinterprets: 404/410→fabricated, timeout/5xx/conn-refused→unverified. | `httpx.head(url, timeout=5, follow_redirects=True)`; matches poller:235-239 sync httpx convention. |
| GATE-04 | Every named study/benchmark/paper title + arXiv ID cross-checked against the fact base; no matching source→fabricated. | tier-1 entity check (existing) covers CamelCase benchmark names ("GroupMemBench"); **arXiv IDs need a NEW membership check** — the existing `_ARXIV_ID` regex currently DISCARDS them (verification.py:287-289), it does not verify them. |
| GATE-05 | Entity-merge: a named entity not present verbatim in any single source is flagged; attributes from two sources must not be merged. | TODO-1 VERDICT below: existing tier-1 is union+fuzzy (not single-source) → thin per-source verbatim refinement required on top. |
| GATE-06 | Mechanical: H1/edition title echoed in body flagged (body must start at `## Read This, Skip the Rest`); leaked reading-mode labels flagged. | TODO-3 VERDICT below: marker verbatim-confirmed; reading-mode-label set is a curated blacklist (operator decision on exact list). |
| GATE-07 | Mechanical: recycled closer lines + numeric stats duplicated verbatim from the previous published edition flagged. | New cross-edition check (existing `validate_stat_repetition` is intra-edition + One-Number-specific, NOT reusable). Reuse `_STATISTIC` regex for stat tokens; normalized-exact per D-06. |
| GATE-08 | Gate verifies against the **correct** fact base — `blocks` for block_v1, `input_data` for single-pass. | TODO-2 VERDICT below: `verify_draft` takes one dict, dispatches on `.get('blocks')`; adapter exists at poller:1737-1749. Gate's `fact_base` param accepts the already-correct dict per version. |

</phase_requirements>

---

## The Three Code-Verification TODOs (resolved)

### TODO 1 — GATE-05 single-source semantics

**VERDICT: CONFIRMED — `verify_draft()` tier-1 is "present in the UNION of all sources" + a permissive fuzzy substring match, NOT "present verbatim in a single source." A thin per-source verbatim entity-merge refinement must be added ON TOP. Do NOT rebuild the engine.**

Evidence (verification.py):
- `_build_block_list(input_data)` (lines 299-480) accumulates **one flat `entities: set[str]`** (declared line 309) populated from **every** source/block/signal — block `named_entities` (319-321), block descriptions (325-339), `premium_source_posts` (354-368), `section_b_emerging` (378-392), `clusters` (395-404), tools/predictions/insights/narrative (407-473). There is **zero per-source provenance** — once merged, you cannot tell which source an entity came from.
- `verify_draft` entity matching (lines 499-514): `block_entities_lower = {e.lower() for e in blocks['entities']}` then `if entity.lower() in block_entities_lower` → VERIFIED. The **else** branch does a fuzzy match (lines 505-512): `any(entity.lower() in be or be in entity.lower() for be in block_entities_lower if len(be) >= 4)` → VERIFIED (fuzzy).

Why this fails GATE-05: a merged entity like `Acme/widgets` (where source A mentions org "Acme" and source B mentions repo "widgets" from a *different* org) is not in the union verbatim, but the fuzzy rule `be in entity.lower()` matches because "acme" (≥4 chars, from source A) is a substring of "acme/widgets" → **fuzzy-VERIFIED, fabrication slips through.** Note also that slash-joined `owner/repo` tokens are not even captured as single entities by `_PROPER_NOUN_*` (the `/` breaks the token), so owner/repo merges are caught primarily by the GATE-02 network layer; GATE-05's refinement is the broader backstop for multi-word product entities.

**Thin refinement to add (NOT a rebuild):**
1. Build a list of **per-source raw text strings** (do NOT flatten): each `premium_source_posts` post's `title+summary+source_display`; each block's `description` + joined `named_entities`; each signal's text. (Reuse the same field accessors `_build_block_list` already reads — just keep them per-item instead of unioning.)
2. Take the set of **composite entities** that tier-1 would pass via the union/fuzzy path — i.e. multi-word entities (`len(words) >= 2`) and any `owner/repo` token extracted from GitHub URLs (GATE-02 already extracts these).
3. For each, flag **entity-merge fabrication** iff the full composite string does **not** appear verbatim (case-insensitive) within **at least one single** per-source text string. (Appearing only *split across* sources = merge.)
4. Emit under `fabrication` with `kind:"entity_merge"`. Does NOT touch `_extract_claims_from_prose`, the stop-list, or the tier classifier → no FP-regression risk.

---

### TODO 2 — Block fact-base shape (GATE-08)

**VERDICT: CONFIRMED — `verify_draft(prose, input_data)` takes ONE dict and dispatches internally on `input_data.get('blocks')`. The gate's `fact_base` param must be the already-correctly-shaped dict per draft version. The block_v1 adapter already exists verbatim in production at newsletter_poller.py:1737-1749 — reuse its shape; do NOT invent a new one.**

Evidence:
- `verify_draft` signature: `def verify_draft(prose: str, input_data: dict)` (verification.py:483). It calls `_build_block_list(input_data)` (line 494).
- `_build_block_list` dispatch (verification.py:315-352): `blocks = input_data.get('blocks', [])` → `if blocks:` use the **block-pipeline path** (extract from `block['named_entities']` + `block['description']`, plus `input_data['tracked_entity_signals']`); `else:` use the **single-pass path** (`premium_source_posts`, `section_b_emerging`, `clusters`).

**Concrete in-memory shapes (both consumed by the SAME `verify_draft`):**

*Single-pass fact base* = the raw `input_data` dict (passed verbatim — poller:1747). Keys `_build_block_list` reads:
```
{
  'premium_source_posts': [{title, summary, source_display, author}, ...],
  'section_b_emerging':   [{theme, description, problem_descriptions[]}, ...],
  'clusters':             [{theme, description}, ...],
  'trending_tools':       [{tool_name, mentions_30d, mentions_7d, total_mentions,
                            recommendation_count, complaint_count, avg_sentiment,
                            top_alternatives[]}, ...],
  'predictions':          [{prediction_text|prediction|description}, ...],
  'analyst_insights':     [...], 'tool_warnings': [{tool_name}, ...],
  'narrative_context':    {editions:[{title, title_impact}, ...]},
  'stats': {...}, 'spotlight': {...}, 'edition_number': N, 'stale_prediction_ids': [...]
}
```

*block_v1 fact base* = the adapter dict built at poller:1737-1743 from `blocks_data` (the Phase A output):
```python
verification_input = {
    'blocks': blocks_data['blocks'],                          # [{description, named_entities[]}, ...]
    'tracked_entity_signals': blocks_data.get('tracked_entity_signals', []),
    'trending_tools': blocks_data.get('tool_stats', []),      # NB: source key is 'tool_stats'
    'predictions': blocks_data.get('predictions', []),
}
```
Note the rename: `blocks_data['tool_stats']` → `verification_input['trending_tools']` (so `_build_block_list`'s `trending_tools` accessor at line 407 finds it). The presence of a non-empty `blocks` list is what flips `_build_block_list` to the block path.

**Implication for the gate:** `run_deterministic_gate(draft, fact_base, prior_edition)` — the caller (Phase 30 sequencer) is responsible for passing the **already-correct** `fact_base` dict, exactly as poller:1737-1749 selects. The gate passes `fact_base` straight to `verify_draft`. The gate does NOT need to re-derive which fact base to use (the poller's existing `if blocks_data and blocks_data.get('blocks')` branch decides). **Recommendation:** the gate should *defensively assert* the fact_base is a dict and log which path `verify_draft` will take (presence of `fact_base.get('blocks')`), so a wrong-fact-base wiring bug in Phase 30 surfaces loudly rather than silently verifying against the wrong base. For Phase 28 tests, both shapes are stubbed directly.

---

### TODO 3 — GATE-06 concrete strings

**VERDICT (body-start marker): CONFIRMED VERBATIM — `## Read This, Skip the Rest`** (two-hash `##`, comma after "This", capital each word).
- Produced (block_v1): `block_pipeline.py:661` → `md_parts.append("## Read This, Skip the Rest\n\n" + ...)`.
- Required (single-pass writer instruction): `newsletter_poller.py:602` ("Use the ## header: '## Read This, Skip the Rest'"), reinforced at :1398.
- Confirmed as the body start with **no H1**: `newsletter_poller.py:2120` ("Published bodies start directly at `## Read This, Skip the Rest` (no H1)").

**VERDICT (edition-title / H1 echo): CONFIRMED — the title is a SEPARATE DB column, never in the body.** `save_newsletter` stores `title` and `title_impact` as their own `newsletters` columns (poller:1709-1710); the body (`content_markdown`) starts at `## Read This, Skip the Rest`. So the H1/title-echo check is: **(a) the body must NOT contain a top-level `# ` (single-hash) H1 line; (b) the `draft['title']` / `draft['title_impact']` string must NOT appear as a header line in its corresponding body.** The gate therefore needs the title fields on the `draft` object (not just the bodies).

**VERDICT (reading-mode-label leak): GENUINE AMBIGUITY — there is NO single canonical "READING MODE" literal emitted into the body in current code.** The CONTEXT examples ("IMPACT/STRATEGIC/TECHNICAL READING MODE") are illustrative, not code-derived. The actual mode/audience label strings in the codebase are:
- **Writer audience-prefix literals (the most realistic leak vector):** `block_pipeline.py:348` → `"AUDIENCE: Business leaders and strategic decision-makers..."` and `:350` → `"AUDIENCE: Technical builders and infrastructure teams..."`. If the model echoes its instruction scaffolding, the prose contains the literal token `AUDIENCE:`. The single-pass equivalent is the `STRATEGIC_EDITOR_PROMPT` framing (poller:1374).
- **Marketing / onboarding email labels:** `BUILDER MODE` and `IMPACT MODE` (processor:10047 and the dual-view block ~10043-10052) — these belong to a *static welcome email*, not a per-edition body.
- **Web frontend toggle labels:** `Technical` / `Strategic` buttons (web/site/index.html:65-66, `setMode('technical'|'strategic')`).

**Recommendation:** implement a curated, case-insensitive **blacklist scan** over the body, seeded from the code-derived strings + the CONTEXT illustrative set:
`["AUDIENCE:", "BUILDER MODE", "IMPACT MODE", "TECHNICAL MODE", "STRATEGIC MODE", "READING MODE", "TECHNICAL READING MODE", "IMPACT READING MODE", "STRATEGIC READING MODE", "TECHNICAL VERSION", "IMPACT VERSION", "STRATEGIC VERSION"]`.
**Flag for operator confirmation:** the exact blacklist membership (this is the one GATE-06 item that is a judgment call, not a code fact). Keep the list as a module-level constant so the operator can tune it during the Phase 30 report-only window. False-positive risk is low because these are uppercase scaffolding tokens unlikely in edited prose, but `"IMPACT"` alone must NOT be blacklisted (it appears in legitimate prose) — only the multi-word labels.

---

## Standard Stack

No new external packages. Everything required is already a newsletter-service dependency.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` | >=0.25.0 (already in `docker/newsletter/requirements.txt`) | Sync GitHub API + URL HEAD checks | Already the service's HTTP client (poller:17,235); processor uses `httpx.Client` for GitHub (processor:1157) |
| `re` (stdlib) | 3.12 | Reuse `_ARXIV_ID`, `_STATISTIC`, claim extraction | Engine is pure-regex |
| `verification` (in-repo module) | — | `verify_draft`, `_extract_claims_from_prose`, `_ARXIV_ID`, `_STATISTIC` | D-04 reuse mandate |
| `pytest` | repo standard | Golden-draft suite | `tests/` + `conftest.py` already configured |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` `monkeypatch` / a fake httpx client | bundled | Mock network in tests | Inject a fake client/callable so no real GitHub/URL calls |
| `os` (stdlib) | 3.12 | `os.getenv('GITHUB_TOKEN')` | Token-via-env per GATE-02/D-03 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sync `httpx` | `requests` | `requests` is NOT a newsletter dep; would add a package and diverge from the processor/poller convention. Use httpx. |
| sync sequential checks | `httpx.AsyncClient` + gather | D-03 explicitly chose sequential; async adds complexity with no latency need this phase. |
| Reusing `validate_stat_repetition` for GATE-07 | new cross-edition stat check | `validate_stat_repetition` is intra-edition and keyed on a "One Number" section that current editions don't have → effectively a no-op. Not reusable; write a new cross-edition check. |

**Installation:** none — no new packages. (Verified: `docker/newsletter/requirements.txt` already lists `httpx>=0.25.0`; `re`/`os` are stdlib.)

## Package Legitimacy Audit

**Not applicable — Phase 28 installs zero new external packages.** All dependencies (`httpx`, `pytest`, stdlib `re`/`os`, in-repo `verification`) are already present in the service. No registry verification or slopcheck run is required because nothing new is added to `requirements.txt`.

## Architecture Patterns

### System Architecture Diagram

```
                 ┌─────────────────────────────────────────────────────────┐
   draft ───────►│  run_deterministic_gate(draft, fact_base, prior_edition) │
 (title,         │                                                          │
  title_impact,  │   per body in [content_markdown, content_markdown_impact]│
  content_md,    │        │                                                 │
  content_md_    │        ▼                                                 │
  impact,        │  ┌──────────────┐  reuse   ┌────────────────────────┐    │
  pipeline_ver)  │  │ verify_draft │◄─────────│ verification.py (D-04) │    │
                 │  │ (prose,      │          │  tier1 entity / tier2  │    │
 fact_base ─────►│  │  fact_base)  │          │  stat / claim extract  │    │
 (input_data OR  │  └──────┬───────┘          └────────────────────────┘    │
  {blocks:...})  │         │ tier1/tier2 ungrounded                         │
                 │         ▼                                                │
                 │  ┌──────────────────────────── thin additions ───────┐  │
                 │  │ arXiv-ID membership (GATE-04, new)                 │  │
                 │  │ entity-merge per-source verbatim (GATE-05, new)   │  │
                 │  └───────────────────────────────────────────────────┘  │
                 │         │                                                │
   GitHub API ◄──┼─────────┤ network layer (GATE-02/03): dedup → per-run    │
 (api.github.com)│         │ cache → retry-once-on-transient → D-01 outcome │
   URL HEAD   ◄──┼─────────┘   { 404/410→fabricated | timeout/5xx/refused→  │
 (arbitrary host)│              unverified | 200→verified-ok / star-band }  │
                 │         │                                                │
 prior_edition ─►│  ┌──────▼─────── mechanical (regex-only) ────────────┐  │
 (content_md of  │  │ H1/title echo (GATE-06) │ reading-mode leak (06)  │  │
  prev published)│  │ recycled closer (GATE-07)│ duplicated stat (07)   │  │
                 │  └───────────────────────────────────────────────────┘  │
                 │         │                                                │
                 │         ▼                                                │
                 │   flags = { fabrication:[...], unverified:[...],         │
                 │             mechanical:[...], meta:{...} }   ───────────► returns
                 └─────────────────────────────────────────────────────────┘
                          (Phase 28 STOPS here — emit only, never acts.
                           Phase 30 computes verdict + writes edition_evals.)
```

### Recommended Project Structure
```
docker/newsletter/
├── deterministic_gate.py     # NEW — run_deterministic_gate() + sub-checks + label blacklist
├── verification.py           # REUSED unchanged — verify_draft, _ARXIV_ID, _STATISTIC, _extract_claims_from_prose
└── edition_eval.py           # EXISTING (Phase 27) — write_eval_row; NOT called this phase
tests/
└── test_28_deterministic_gate.py   # NEW — golden-draft suite, mocked network
```

### Pattern 1: Reuse-then-refine (do not rebuild)
**What:** Import the calibrated engine; add thin layers only.
**When to use:** Every fabrication check.
**Example:**
```python
# Source: docker/newsletter/verification.py:483 (verify_draft), :109 (_ARXIV_ID), :112 (_STATISTIC)
from verification import verify_draft, _extract_claims_from_prose, _ARXIV_ID, _STATISTIC
report = verify_draft(prose, fact_base)          # tier1/tier2 from the calibrated engine
tier1 = report['tier1_fabrications']             # named-entity fabrications (GATE-04/05 base)
```

### Pattern 2: Network three-outcome classifier (D-01)
**What:** Map every network result into exactly one of {fabricated, unverified, verified-ok}.
**When to use:** GATE-02 (GitHub) and GATE-03 (URL).
**Example:**
```python
# GitHub repo existence — uses /repos/{owner}/{repo}, matching processor:1134-1136 header convention
# Source: docker/processor/agentpulse_processor.py:1134-1167 (header + 403 handling pattern)
def _classify_github(owner, repo, *, client, token):
    headers = {'Accept': 'application/vnd.github.v3+json'}
    if token:
        headers['Authorization'] = f'token {token}'
    for attempt in (1, 2):                                   # D-02: retry once on transient only
        try:
            r = client.get(f'https://api.github.com/repos/{owner}/{repo}', headers=headers, timeout=5)
        except (httpx.TimeoutException, httpx.ConnectError):
            if attempt == 1: continue
            return ('unverified', None)                      # D-01: transient → unverified
        if r.status_code == 404:
            return ('fabricated', None)                      # D-01: definitive → fabricated (NEVER retried)
        if r.status_code in (403, 429) or r.status_code >= 500:
            if attempt == 1 and r.status_code >= 500: continue
            return ('unverified', None)                      # D-01: rate-limit/5xx → unverified
        if r.status_code == 200:
            return ('verified', r.json().get('stargazers_count'))
        return ('unverified', None)
```

### Pattern 3: Per-run dedup cache (D-03)
**What:** Extract the unique owner/repo + URL set, check each exactly once, reuse for all occurrences.
**Example:** a `dict` keyed by `('gh', owner, repo)` / `('url', normalized_url)` populated on first check; sequential iteration.

### Anti-Patterns to Avoid
- **Re-implementing claim extraction or the stop-list** — re-introduces tier-1 false positives the Edition-34 calibration eliminated (verification.py:16-93 is the calibrated list). Import, never copy.
- **Folding `unverified` into the `fabrication` list or dropping it** — violates D-01 and the operator's explicit "unverified must never be silently treated as a pass." Keep `unverified` a top-level key.
- **Retrying a 404** — D-02 forbids it (a 404 is definitive evidence of fabrication).
- **Blacklisting bare `"IMPACT"`/`"Technical"`** — they appear in legitimate prose; only multi-word mode labels go in the GATE-06 blacklist.
- **Deciding which fact base to use inside the gate** — the poller's existing branch (poller:1737) owns that; the gate trusts the `fact_base` it's handed (and logs which path it triggers).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Named-entity / stat fabrication detection | A new extractor + stop-list | `verify_draft()` (verification.py:483) | Edition-34-calibrated to ~0 tier-1 FP; re-rolling regresses FP rate |
| arXiv-ID regex | A new pattern | `_ARXIV_ID` (verification.py:109) | Already battle-tested; only the *membership check* is new |
| Numeric-stat token extraction (GATE-07) | A new number regex | `_STATISTIC` (verification.py:112-120) | Consistent token shape with the engine; covers $/%/units/ratios |
| HTTP client | `requests` / urllib | `httpx` (sync) | Already a dep; matches processor + poller convention |
| Markdown section splitting | A new parser | `_extract_sections` (poller:338) if needed for closer extraction | Existing `##`-header splitter |

**Key insight:** The entire fabrication core already exists and is calibrated. Phase 28's *net-new* code is small: the network layer, the arXiv membership check, the entity-merge per-source check, and four regex-only mechanical checks. The risk is in *adding on top correctly*, not in building from scratch.

## Common Pitfalls

### Pitfall 1: arXiv IDs are extracted-then-discarded today (NOT verified)
**What goes wrong:** Assuming `verify_draft` already verifies arXiv IDs because it has an `_ARXIV_ID` pattern.
**Why it happens:** The pattern's only current use is to **remove** arXiv IDs from the statistics set so they don't trigger false stat-fabrication flags — verification.py:287-289: `statistics = {s for s in statistics if not _ARXIV_ID.match(s.split()[0]) ...}`. There is no membership test against the fact base.
**How to avoid:** GATE-04 must add a NEW step: extract arXiv IDs from each body with `_ARXIV_ID`, and flag fabrication for any ID not present (verbatim) in the concatenated fact-base source text. This is exactly the ed-36 "fake arXiv ID" golden fixture.
**Warning signs:** A fake arXiv ID passes the gate clean — means the membership check is missing.

### Pitfall 2: Fuzzy entity match masks entity-merge
**What goes wrong:** A merged/fabricated multi-word entity is fuzzy-VERIFIED because one of its words exists in the union fact base.
**Why it happens:** verification.py:505-512 fuzzy `be in entity.lower()`.
**How to avoid:** The TODO-1 per-source verbatim refinement; run it on composite entities the engine marked VERIFIED-fuzzy *and* on tier-1-eligible multi-word entities.

### Pitfall 3: Wrong fact base silently verifies (GATE-08)
**What goes wrong:** Passing single-pass `input_data` for a block_v1 draft (or vice versa) — `_build_block_list` happily runs the other path and produces a *plausible but wrong* grounding set.
**Why it happens:** `verify_draft` never errors on shape; it just branches on `.get('blocks')`.
**How to avoid:** The gate logs the chosen path; Phase 30 passes the correct base via the existing poller:1737 branch. For Phase 28, the golden suite includes one block_v1 fixture (`fact_base={'blocks':[...]}`) and one single-pass fixture to lock both paths.

### Pitfall 4: `prior_edition` source has no closer/stats from `load_edition_context`
**What goes wrong:** Wiring GATE-07 to `load_edition_context()` output, which only exposes `opening_excerpt` (first 300 chars), `title`, `primary_theme`, `weeks_ago` (poller:2242-2253) — **no closer line, no stats, no full body.**
**Why it happens:** Phase 26's loader was built for continuity bridging (the *opening*), not closer/stat recycling.
**How to avoid:** The gate takes `prior_edition` as a param expecting the **full** previous-published `content_markdown` (+ `content_markdown_impact`) so it can extract the closer and stat tokens itself. **Flag for Phase 30:** the sequencer must fetch the previous published edition's full content via a plain `.eq('status','published').order('edition_number', desc=True).limit(1)` select returning `content_markdown` — NOT reuse `load_edition_context`'s truncated excerpt. Phase 28 stubs `prior_edition` directly.

### Pitfall 5: GitHub unauthenticated rate limit (60/hr) during tests or live
**What goes wrong:** Real GitHub calls in tests, or hitting the 60/hr unauthenticated cap live, producing spurious `unverified`.
**Why it happens:** No token in env, or tests not mocking.
**How to avoid:** Tests MUST mock the httpx client (inject a fake) — never hit the network. Live: token from `os.getenv('GITHUB_TOKEN')` (present in `config/.env`; the newsletter container loads it via compose `env_file: ../config/.env` — confirm passthrough in Phase 30). D-01 correctly maps 403/429 quota → `unverified`, not fabricated.

## Code Examples

### Recommended module signature + flags shape
```python
# docker/newsletter/deterministic_gate.py
from typing import Any, Callable
import os, re, logging
import httpx
from verification import verify_draft, _extract_claims_from_prose, _ARXIV_ID, _STATISTIC

logger = logging.getLogger("newsletter")

BODY_START_MARKER = "## Read This, Skip the Rest"          # verbatim — block_pipeline.py:661
READING_MODE_LABELS = [                                    # GATE-06 blacklist (operator-tunable)
    "AUDIENCE:", "READING MODE", "BUILDER MODE", "IMPACT MODE",
    "TECHNICAL MODE", "STRATEGIC MODE", "TECHNICAL READING MODE",
    "IMPACT READING MODE", "STRATEGIC READING MODE",
    "TECHNICAL VERSION", "IMPACT VERSION", "STRATEGIC VERSION",
]
_GITHUB_URL = re.compile(r'github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)', re.IGNORECASE)
_MD_LINK   = re.compile(r'\[([^\]]+)\]\((https?://[^)\s]+)\)')

def run_deterministic_gate(
    draft: dict,                # {title, title_impact, content_markdown, content_markdown_impact, pipeline_version}
    fact_base: dict,            # single-pass input_data  OR  {'blocks':[...], 'tracked_entity_signals':..., 'trending_tools':..., 'predictions':...}
    prior_edition: dict | None, # {content_markdown, content_markdown_impact, edition_number}  (full body; None if no prior)
    *,
    http_client: httpx.Client | None = None,   # injectable for tests
    github_token: str | None = None,           # defaults to os.getenv('GITHUB_TOKEN')
) -> dict:
    """No-LLM deterministic gate. EMITS flags only — never acts (D-05). Runs both
    body versions; aggregates into one flags object matching migration 045
    deterministic_flags JSONB ({fabrication, mechanical}) + the first-class
    `unverified` key (D-01)."""
    ...
    return {
        "fabrication": [   # held_fabrication territory (Phase 30)
            # {"kind":"github_repo","ref":"acme/widgets","version":"technical","detail":"GitHub 404"}
            # {"kind":"dead_url","url":"...","version":"impact","detail":"HTTP 410"}
            # {"kind":"arxiv","id":"2605.99999","version":"technical","detail":"not in fact base"}
            # {"kind":"entity_merge","entity":"Acme/widgets","version":"technical"}
            # {"kind":"tier1_entity","value":"GroupMemBench","version":"technical"}  # from verify_draft
        ],
        "unverified": [    # D-01 first-class visible state — NEVER folded into pass, NEVER fabrication
            # {"kind":"github_repo","ref":"foo/bar","reason":"rate_limit_403"}
            # {"kind":"url","url":"...","reason":"timeout"}
        ],
        "mechanical": [    # mechanical-only; may feed Phase 29 rewrite loop (LOOP-04), never holds as fabrication
            # {"kind":"h1_in_body","version":"technical"}
            # {"kind":"title_echo","version":"impact","value":"<title>"}
            # {"kind":"reading_mode_leak","version":"technical","label":"AUDIENCE:"}
            # {"kind":"recycled_closer","version":"technical","prior_edition":N}
            # {"kind":"duplicated_stat","version":"technical","stat":"42%","prior_edition":N}
        ],
        "meta": {
            "fact_base_path": "blocks" if fact_base.get("blocks") else "input_data",
            "github_checked": 5, "urls_checked": 12, "github_token_present": bool(github_token),
            "tier1_count": {"technical": 0, "impact": 0},
        },
    }
```

### GATE-07 normalized-exact closer + stat check (D-06)
```python
def _normalize(s: str) -> str:                      # D-06: lowercase + collapse ws + strip trailing punct
    return re.sub(r'\s+', ' ', s).strip().lower().rstrip('.!?,:;—-')

def _closer_line(body: str) -> str:
    paras = [p for p in re.split(r'\n\s*\n', body) if p.strip()]
    return _normalize(paras[-1]) if paras else ""

def _stat_tokens(body: str) -> set[str]:            # reuse the engine's stat regex
    return {_normalize(m.group(0)) for m in _STATISTIC.finditer(body)}

# recycled closer: _closer_line(cur) == _closer_line(prior)  → mechanical flag
# duplicated stat: _stat_tokens(cur) & _stat_tokens(prior)    → mechanical flag per token
```

## Runtime State Inventory

Not applicable — Phase 28 is a greenfield additive module (build-only, D-05). No rename/refactor/migration. No stored data, live-service config, OS-registered state, secrets, or build artifacts are changed. (The only env read is `GITHUB_TOKEN`, already present in `config/.env`; no new secret is introduced this phase.)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `validate_fabrication_signals` (poller:660) — substring-in-`json.dumps(input_data)` heuristic | `verify_draft` tiered claim engine (verification.py) | Block-pipeline ship 2026-05-15 | The gate reuses the tiered engine, not the older heuristic |
| arXiv IDs filtered from stats only | (Phase 28) arXiv-ID **membership** check | This phase | Closes the "fake arXiv ID" gap (ed-36 fixture) |
| `validate_stat_repetition` intra-edition / One-Number | (Phase 28) cross-edition normalized-exact stat check | This phase | GATE-07 compares vs the PREVIOUS edition, a different semantic |

**Deprecated/outdated:**
- `validate_stat_repetition` (poller:367) keys on a "One Number" section absent from current editions → effectively a no-op; do not reuse for GATE-07.
- `claude-sonnet-4-20250514` (spec-01) is EOL — irrelevant to Phase 28 (no LLM) but noted: anything that touches a model id uses `claude-sonnet-4-6`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The exact reading-mode-label blacklist for GATE-06. Code shows `AUDIENCE:` (block_pipeline.py:348,350), `BUILDER MODE`/`IMPACT MODE` (processor:10047, marketing email only), `Technical`/`Strategic` (web toggle). No single canonical body literal exists. | TODO-3 / GATE-06 | Over-broad list → mechanical false positives; under-broad → a real leak passes. Mitigated by operator-tunable constant + report-only window. **Needs operator confirmation.** |
| A2 | A clean-but-`unverified` edition's deterministic *verdict* mapping (passed+surfaced vs escalated) is a Phase 30 decision; Phase 28 only guarantees `unverified` is first-class on the flags object. | Flags shape | If the operator wants the gate itself to pre-compute a verdict, the contract widens — but D-05 says emit-only, so low risk. **Confirm at Phase 30, not blocking Phase 28.** |
| A3 | `prior_edition` is supplied as a full-body dict by the Phase 30 caller (not `load_edition_context`'s excerpt). | GATE-07 / Pitfall 4 | If Phase 30 wires the truncated excerpt, closer/stat checks under-fire. Flagged as a Phase 30 wiring requirement. |
| A4 | The newsletter container actually receives `GITHUB_TOKEN` at runtime (it loads `config/.env` via compose `env_file`, comment at docker-compose.yml:5). | GATE-02 / Pitfall 5 | If not passed, GitHub checks run unauthenticated (60/hr) → more `unverified`, never wrong fabrication. Verify in Phase 30. |

**These are the only items needing confirmation.** All structural facts (engine semantics, fact-base shapes, body marker, save points) are VERIFIED from code with line citations above.

## Open Questions

1. **GATE-06 reading-mode-label blacklist membership (A1).**
   - What we know: code-derived candidates are `AUDIENCE:`, `BUILDER MODE`, `IMPACT MODE`, `Technical`/`Strategic` toggle labels; CONTEXT's "...READING MODE" strings are illustrative.
   - What's unclear: which exact strings the operator wants flagged as a body leak.
   - Recommendation: ship the seeded list as a tunable module constant; confirm/adjust during Phase 30 report-only calibration. Not a Phase 28 blocker.

2. **Deterministic verdict for clean+unverified (A2).**
   - What we know: D-01 says `unverified` must be visible and never a silent pass; the verdict taxonomy has only `passed/held_fabrication/held_voice/escalated`.
   - What's unclear: whether a no-fabrication-but-has-unverified edition maps to `passed` (with `unverified` surfaced) or to `escalated`.
   - Recommendation: Phase 28 emits the `unverified` list and does NOT compute the verdict (emit-only, D-05). Phase 30 decides the mapping. Make `unverified` first-class so either choice is supported.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `httpx` | GATE-02/03 network checks | ✓ | >=0.25.0 (newsletter requirements.txt) | — |
| `verification.py` module | D-04 reuse (GATE-04/05) | ✓ | in-repo (docker/newsletter/) | — |
| `pytest` | golden-draft suite | ✓ | repo standard (tests/ + conftest.py) | — |
| `GITHUB_TOKEN` env | GATE-02 (5000/hr) | ✓ in `config/.env` | — | unauthenticated 60/hr (per GATE-02/D-03) |
| Network egress to api.github.com + arbitrary hosts | live GATE-02/03 | n/a this phase | — | **Tests mock the client — no live egress in Phase 28** |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** GitHub token may be absent in some environments → unauthenticated mode (graceful, per spec).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (repo standard; `tests/conftest.py` configured) |
| Config file | `tests/conftest.py` (sys.path + schemas-collision workaround) |
| Quick run command | `python3 -m pytest tests/test_28_deterministic_gate.py -x` |
| Full suite command | `cd /root/bitcoin_bot && python3 -m pytest tests/` |

**Import pattern for the new test** (mirror test_26_continuity_loader.py:33-37):
```python
import sys
from pathlib import Path
NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
if str(NL_DIR) not in sys.path:
    sys.path.insert(0, str(NL_DIR))
import deterministic_gate as gate          # the REAL module — never re-implement
```
Note: `verification.py` is NOT currently imported by any test; the gate's test will be the first direct consumer. `conftest.py` preloads `newsletter_poller` but not `verification`/`deterministic_gate` — the explicit `sys.path.insert` above (belt-and-suspenders, exactly as test_26 does) makes both importable. `deterministic_gate` imports `verification` by bare `from verification import ...`, which resolves once `NL_DIR` is on the path.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GATE-02 | repo 404 → fabricated; star-drift >20% → flag; 200 in-band → clean | unit (mock client) | `pytest tests/test_28_deterministic_gate.py -k github -x` | ❌ Wave 0 |
| GATE-03 | URL 404/410 → fabricated; timeout/5xx → unverified (after 1 retry) | unit (mock client) | `pytest ... -k url -x` | ❌ Wave 0 |
| GATE-04 | fake arXiv ID + invented study → fabricated; real ones clean | unit | `pytest ... -k arxiv -x` | ❌ Wave 0 |
| GATE-05 | entity-merge (split-across-sources) → fabricated; single-source verbatim clean | unit | `pytest ... -k merge -x` | ❌ Wave 0 |
| GATE-06 | H1 in body / title echo / leaked label → mechanical | unit | `pytest ... -k mechanical -x` | ❌ Wave 0 |
| GATE-07 | recycled closer + duplicated stat vs prior edition → mechanical | unit | `pytest ... -k recycled -x` | ❌ Wave 0 |
| GATE-08 | block_v1 fact base verified against blocks; single-pass against input_data | unit | `pytest ... -k factbase -x` | ❌ Wave 0 |
| D-01 | transient → `unverified` (first-class), 404 → `fabrication`; never collapsed | unit | `pytest ... -k unverified -x` | ❌ Wave 0 |
| D-02 | 404 never retried; transient retried exactly once | unit (call-count assert) | `pytest ... -k retry -x` | ❌ Wave 0 |
| D-03 | duplicate refs/URLs checked exactly once (cache hit assert) | unit | `pytest ... -k dedup -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_28_deterministic_gate.py -x`
- **Per wave merge:** `python3 -m pytest tests/test_28_deterministic_gate.py tests/test_27_edition_eval.py tests/test_26_continuity_loader.py`
- **Phase gate:** full `python3 -m pytest tests/` green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_28_deterministic_gate.py` — covers GATE-01..08 + D-01..D-03. Includes the golden fixtures from CONTEXT's Discretion: ed-36 invented "MCP authentication" study, ed-34 "GroupMemBench", a fake arXiv ID, a dead-URL/404 repo, a transient-5xx→unverified case, a recycled closer, a leaked reading-mode label.
- [ ] Fake httpx client double (queue of `(status_code, json)` per URL; raises `httpx.TimeoutException`/`ConnectError` on demand) + a call-counter to assert dedup (D-03) and retry-once (D-02). Inject via the `http_client` param — no `monkeypatch` of the real network needed.
- [ ] No framework install needed — pytest + conftest already present.

*Golden-draft fixture design:* hand-author small markdown bodies (start with `## Read This, Skip the Rest`) embedding each offender, paired with a minimal `fact_base` dict (a few `premium_source_posts` for single-pass; a few `blocks` for block_v1) that does/does not contain the entity/arXiv/repo. Stub `prior_edition` with a body whose closer line + one stat match the current draft for the GATE-07 case.

## Security Domain

`security_enforcement: true`, ASVS level 1. Phase 28 makes **outbound** HTTP requests to GitHub and to arbitrary URLs drawn from generated drafts — this is the relevant attack surface (SSRF / response handling), not auth/session.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No user auth in this module |
| V3 Session Management | no | Stateless pure function |
| V4 Access Control | no | No resource access decisions |
| V5 Input Validation / Output Encoding | yes | Validate extracted URLs before HEAD; constrain GitHub owner/repo to `[A-Za-z0-9._-]`; never `eval`/shell the draft content; cap response read size |
| V6 Cryptography | no | No crypto; `GITHUB_TOKEN` only read from env, sent over TLS (`https://`), never logged |
| V12 Files/Resources (egress) | yes | 5s timeout on every request; per-run dedup bounds request count; `follow_redirects` with a cap; treat draft URLs as untrusted |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SSRF via a draft-supplied URL pointing at internal hosts (e.g. `http://llm-proxy:8200`, `169.254.169.254`) | Information disclosure / Elevation | Restrict GATE-03 to `http(s)` schemes; consider skipping/flagging private/loopback/link-local hosts as `unverified` rather than fetching; never include response bodies in flags |
| Token leakage | Information disclosure | `GITHUB_TOKEN` read from env, sent only to `api.github.com` over HTTPS, never written to logs or the flags object (`meta.github_token_present` is a bool only) |
| DoS via a link-heavy draft | Denial of service | D-03 dedup + sequential + 5s timeout bound total time; per-edition link count is small |
| ReDoS on adversarial draft text | Denial of service | Reused regexes are linear/bounded; the new `_GITHUB_URL`/`_MD_LINK` patterns are simple character classes — avoid nested quantifiers |
| Logging untrusted content | Tampering (log injection) | Log counts/refs, not raw draft prose, at INFO |

**Recommendation:** add a small `_is_safe_public_url(url)` helper (scheme in {http,https}, host not loopback/private/link-local/`*.internal`/known service names like `llm-proxy`,`supabase`) and route any rejected URL to `unverified` (reason `"unsafe_host"`) rather than fetching it. This is an SSRF guard appropriate to ASVS L1 and costs ~10 lines.

## Sources

### Primary (HIGH confidence) — in-repo source, line-cited
- `docker/newsletter/verification.py` — `verify_draft`:483; `_build_block_list` union+dispatch:299-352; entity match + fuzzy:499-514; `_ARXIV_ID`:109 + discard-from-stats:287-289; `_STATISTIC`:112-120; tier classifier:580-601; calibrated stop-list:16-93.
- `docker/newsletter/newsletter_poller.py` — dual-fact-base adapter:1737-1749; `save_newsletter`:1658; verify_draft tech+impact calls:1756-1757; body-start "no H1" note:2120 + `_le_opening_excerpt`:2117-2133; `load_edition_context` return shape:2186-2298 (no closer/stats exposed); `validate_required_sections`:589; `validate_fabrication_signals`:660; `validate_stat_repetition`:367 (intra-edition, no-op now); `_extract_sections`:338; httpx sync convention:235-239; required body marker text:602,1398.
- `docker/newsletter/block_pipeline.py` — body assembly + `## Read This, Skip the Rest`:661; section set:644,664-670; audience-prefix literals:348,350; technical/impact render:673-681.
- `docker/processor/agentpulse_processor.py` — GitHub API header/token/403 convention:1125-1167; `stargazers_count` field:1177; `GITHUB_TOKEN = os.getenv(...)`:96; marketing `BUILDER MODE`/`IMPACT MODE` email:10043-10052.
- `docker/web/site/index.html` — `Technical`/`Strategic` toggle labels:65-66.
- `supabase/migrations/045_edition_evals.sql` — `deterministic_flags JSONB ... {fabrication:[...], mechanical:[...]}`:47; verdict-iff-ok CHECK:43-46; verdict taxonomy:41.
- `tests/conftest.py` (schemas-collision preload) + `tests/test_26_continuity_loader.py`:33-90 (in-memory stub + real-module-import fixture pattern to mirror).
- `.planning/REQUIREMENTS.md` §GATE-01..08:23-30, verdict taxonomy:88-95, thresholds (star-drift >20%, HEAD 5s, token-via-env).
- `.planning/phases/28-layer-1-deterministic-gate/28-CONTEXT.md` (D-01..D-06, Discretion, TODOs) and `27-CONTEXT.md` (fail-loud / "an error is not evidence").

### Secondary (MEDIUM confidence)
- `docs/audit/specs/01_eval_harness.md` — verify_draft reuse (cites verification.py:483-719), the two save points, dual-fact-base wiring (superseded by REQUIREMENTS.md on DDL/taxonomy).

### Tertiary (LOW confidence)
- None — all claims are code-cited or from locked CONTEXT/REQUIREMENTS.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; httpx/pytest/verification all present and version-confirmed in `requirements.txt` + tests dir.
- Architecture / TODO resolutions: HIGH — each verdict cites exact source lines; engine semantics read in full.
- GATE-06 label blacklist: MEDIUM — body marker + H1/title facts are HIGH; the exact reading-mode-label set is the one operator-decision (A1).
- Pitfalls: HIGH — arXiv-discard (287-289), fuzzy-merge (505-512), no-closer-in-loader (2242-2253), stat-repetition no-op (367) all directly verified.

**Research date:** 2026-06-30
**Valid until:** 2026-07-30 (stable — in-repo code; only churn risk is the GitHub REST `/repos` contract, which is long-stable)

---

## RESEARCH COMPLETE

**Phase:** 28 - Layer 1 Deterministic Gate
**Confidence:** HIGH

### Key Findings
- **TODO-1 (GATE-05):** `verify_draft` tier-1 is union-of-all-sources + fuzzy substring (verification.py:299-480, 505-512), NOT single-source-verbatim. Add a thin per-source verbatim entity-merge refinement on top for composite/owner-repo entities. Do NOT rebuild.
- **TODO-2 (GATE-08):** `verify_draft(prose, input_data)` is one dict, dispatching on `input_data.get('blocks')` (verification.py:315). The block_v1 adapter already exists at newsletter_poller.py:1737-1749; single-pass passes `input_data` verbatim. The gate trusts the `fact_base` it's handed and logs the path.
- **TODO-3 (GATE-06):** `## Read This, Skip the Rest` confirmed verbatim (block_pipeline.py:661); title is a separate DB column (no body H1 — poller:2120). NO single canonical "READING MODE" body literal exists — recommend a tunable blacklist seeded from `AUDIENCE:` (block_pipeline.py:348,350) + `BUILDER/IMPACT MODE` + `Technical/Strategic`; exact membership is the one operator decision.
- **Net-new gap found:** arXiv IDs are extracted-then-DISCARDED today (verification.py:287-289), never verified — GATE-04 needs a NEW fact-base membership check (the ed-36 fixture). `validate_stat_repetition` is intra-edition + One-Number-keyed (a no-op now) → NOT reusable for GATE-07's cross-edition check.
- **Flags shape:** `{fabrication:[...], unverified:[...], mechanical:[...], meta:{...}}` — `unverified` first-class per D-01; verdict computation stays in Phase 30. No new packages; SSRF guard recommended for the URL HEAD layer (ASVS L1).

### File Created
`/root/bitcoin_bot/.planning/phases/28-layer-1-deterministic-gate/28-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | No new deps; httpx/pytest/verification confirmed present |
| Architecture (TODO verdicts) | HIGH | Each cited to exact source lines |
| Pitfalls | HIGH | arXiv-discard, fuzzy-merge, loader-no-closer, stat no-op all verified in code |
| GATE-06 label set | MEDIUM | Marker/H1 facts HIGH; exact blacklist needs operator confirm (A1) |

### Open Questions (operator decisions, non-blocking)
1. Exact GATE-06 reading-mode-label blacklist membership (A1) — ship tunable, confirm in Phase 30 report-only.
2. Verdict mapping for clean-but-unverified editions (A2) — Phase 28 emits-only; Phase 30 decides.
3. Phase 30 must supply `prior_edition` as a FULL body (not `load_edition_context`'s excerpt) (A3), and verify `GITHUB_TOKEN` passthrough to the newsletter container (A4).

### Ready for Planning
Research complete. The planner can author PLAN.md task(s) for `docker/newsletter/deterministic_gate.py` + `tests/test_28_deterministic_gate.py` directly from the per-GATE map, the flags-object shape, the module signature, and the Wave 0 fixture plan above.
