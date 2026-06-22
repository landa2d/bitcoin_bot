# Phase 26: Continuity & Exemplar Context - Context

**Gathered:** 2026-06-22
**Status:** Ready for planning

<domain>
## Phase Boundary

A new `load_edition_context(supabase, limit=3, exemplar_paras=8)` loader in the **newsletter service** makes prior published editions available to three consumers that already exist and already expect this data:

1. The single-pass writer's editorial-continuity block (`newsletter_poller.py:1148`).
2. The block-prepass avoided-angles logic (`block_pipeline.py:470`, `:508`).
3. The Phase E voice check (`block_pipeline.py:404`) — currently dead (returns a "skipped / no exemplars" sentinel) — and, downstream, the Layer-2 judge (Phase 29).

The loader returns `{previous_editions:[…], exemplars:[…], empty:bool}` and is injected via `input_data.setdefault('narrative_context', ctx)` in `process_task` before generation dispatch. **Purely additive: DB reads + injection + passing an already-existing param. No new LLM call surface. No schema changes** (one optional data-hygiene backfill, below). Fail-loud-but-not-fatal: a degraded corpus warns and continues, never aborts generation.

**Scope anchor (CTX-01..05):** the loader, its injection, the Phase E resurrection, and the avoided-angles feed. Building the judge, the eval table, the gate, or the rewrite loop is **out of scope** (Phases 27–31).

</domain>

<decisions>
## Implementation Decisions

### Exemplar provenance (CTX-02)
- **D-01:** Voice exemplars are drawn **only** from editions where `data_snapshot.operator_written = true`. These are the operator's own hand-written gold-standard prose (currently editions 25–28, 30–32 = 7 editions). Pipeline-generated editions (e.g. edition 29, `pipeline_version='block_v1'`) are **excluded** — anchoring the judge/Phase E on pipeline output would re-entrench the exact tics the eval is meant to catch.
- **D-02:** **Empty operator pool → skip-and-surface, never substitute.** If zero `operator_written` editions exist, the loader does NOT silently fall back to any-published. It returns an **explicit, distinguishable marker** (not a bare `exemplars:[]`) so the downstream voice dimension is reported as a **"not scored" verdict**, never a silent `score:0` and never a quiet substitution. A WARNING is logged. This is the milestone's "NULL ≠ intent / no silent zero" invariant applied to the exemplar pool.
- **D-03:** This empty-operator-pool state is **distinct** from CTX-03's whole-corpus-empty state. When published editions exist but none are operator-written: `previous_editions` is still populated (the continuity bridge works from all published editions), only the voice-exemplar pool is empty.
- **D-04:** Phase E's current empty-exemplar branch (`block_pipeline.py:674` and `:410-411`, returning `{"score": 0, "observations": ["No exemplars provided…"]}`) must be changed to a **"not scored"** result, not a `0` — this closes the CTX-05 silent-zero gap. With operator exemplars present (7 editions today), Phase E gets a real score with ≥1 observation.

### Exemplar selection (CTX-02)
- **D-05:** From the qualifying paragraphs (≥40 words, non-header, non-list) of an operator-written edition, select in **document order, front-loaded** — take paragraphs top-to-bottom and fill down to the cap. This naturally favors the opening "Read This, Skip the Rest" essay, which is both the richest voice and the paragraphs that model the cross-edition bridge ("Last week we wrote…") the continuity judge checks for — maximizing alignment between the exemplar and what's being measured.
- **D-06:** Cap at **`exemplar_paras = 8`** paragraphs (spec 07 default confirmed), sourced from the **2 most-recent** operator-written editions, expanding to a 3rd operator edition only if needed to reach the cap. Balances voice-anchor strength against the judge's per-attempt token cost (the judge re-reads exemplars on each of up to N=2 rewrite passes in Phase 29, against the governed agent's weekly sats cap).

### Continuity metadata (CTX-01)
- **D-07:** `previous_editions[].primary_theme` ← `data_snapshot.lead_theme` when present, **else null** (never derived, never fabricated). Spec 07's `primary_theme` field is **always null in the live DB** — the real source field is `lead_theme`. Rely on `opening_excerpt` (shown right after the theme in the continuity block) to carry the edition when theme is null.
- **D-08:** The writer's continuity block (`newsletter_poller.py:1158`) currently prints `Theme: ?` on a missing theme. Change it to **omit the "Theme:" segment** when `primary_theme` is null, so older editions render a clean empty theme rather than a `?` placeholder (matches the D-07 "empty theme" intent).
- **D-09:** `weeks_ago` ← `round((now − published_at) / 7 days)`. **On null `published_at`, OMIT `weeks_ago`** for that edition — do **not** fall back to the edition-number gap. The number-gap fallback reintroduces cadence error on exactly the held / test-cycle rows most likely to have null timestamps.
- **D-10:** `opening_excerpt` = first ~300 chars of `content_markdown` after the leading header. Note: published editions have **no H1 in `content_markdown`** — the body starts directly at `## Read This, Skip the Rest` (the title lives in the separate `title` column). Strip the leading `## Read This, Skip the Rest` header before taking the excerpt so the excerpt is prose, not the section label.
- **D-11:** Corpus depth `limit = 3` (spec default confirmed) for `previous_editions` and for the avoided-angles feed. `previous_editions` is sourced from **all** published editions (continuity bridge); only the **exemplar pool** is restricted to operator-written (D-01).

### Data-hygiene backfill (folded into this phase)
- **D-12:** Backfill `data_snapshot.lead_theme` on the operator-written editions that lack it (**25, 26, 27, 28**; 30–32 already have it) and verify `published_at` is non-null on **all 7** operator-written editions in the same pass. This makes the judge's bridge-verification angle text real for those editions and keeps `weeks_ago` correct (D-09).
- **D-13:** `lead_theme` is **operator-authored editorial copy** — for editions 25–28, derive a **candidate** theme from each edition's opening thesis and present it for **operator confirmation** before applying. Apply via Supabase MCP `UPDATE` (data mutation = **worktree-unsafe, orchestrator/operator-owned on the main tree**, per the milestone's SQL/MCP discipline). This is a small live-data mutation, not a migration.

### Avoided-angles feed (CTX-04, spec 07 §4)
- **D-14:** Feed the last 3 `newsletter_prepass_tracking.chosen_angle` rows into the prepass `avoided_themes` parameter (already accepted at `block_pipeline.py:473` and `newsletter_poller.py:970`, currently unfed). Use plain `.eq()` / ordered select — no `.in_()`.

### Verification (how Phase 26 is proven done)
- **D-15:** **Both** a deterministic fixture/unit test AND one live generation trigger.
- **D-16:** Fixture/unit test must cover: correct return shape; `operator_written` filtering (D-01); ≥40-word non-header/list filtering (D-05); the CTX-03 whole-corpus-empty path (explicit `{previous_editions:[], exemplars:[], empty:true}` + WARNING, generation still completes); and the **empty-operator-pool "not scored"** path (D-02/D-03) — both degrade paths are hard to reproduce against the live 32-edition corpus, so they must be tested with fixtures.
- **D-17:** Live trigger: run one real generation against the 32 published editions and confirm end-to-end — the EDITORIAL CONTINUITY block is populated in the prompt log, the draft's opening contains a bridge to a prior edition, and Phase E returns a real score (`voice_score.score > 0`, ≥1 observation). **The live Phase E runs through the A/B comparison path** (see code_context D-19) — no need to flip `block_pipeline.enabled`.
- **D-18:** The operator reads the live generated opening bridge for **prose quality** (spec 07 human gate: "the mechanism can be correct and the prose still clumsy — framing stays in human hands"). Mechanism-correct ≠ prose-good; the human gate is unchanged.

### Claude's Discretion
- Exact paragraph-splitting heuristic for "paragraph" (blank-line split vs markdown block parse) — researcher/planner's call, as long as headers and list items are excluded and the ≥40-word filter applies.
- Output dict key naming inside the returned context, as long as the existing consumers' expected keys (`previous_editions`, `primary_theme`, `opening_excerpt`, `exemplars`) are satisfied (consumers read these names today — see D-07, code_context).
- Whether the "not scored" marker (D-02) is a boolean flag, a sentinel string, or a status enum on the returned context — planner's call, as long as it is unambiguously distinguishable from "scored 0" and from "corpus empty."

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 26 source specs
- `docs/audit/specs/07_continuity_and_exemplars.md` — **the authoritative implementation reference (audit R4)** for this phase: the loader signature, the three consumers, the injection point, Phase E resurrection, and the avoided-angles feed. NOTE the one inaccuracy corrected by discussion: it says theme comes from `primary_theme`, but the live field is `data_snapshot.lead_theme` (D-07).
- `.planning/REQUIREMENTS.md` §CTX — requirements CTX-01..05 (the locked WHAT) + the milestone spine and standing invariants.
- `.planning/ROADMAP.md` §"Phase 26" — goal, depends-on, success criteria (1–5), notes.

### Milestone context (cross-cutting, informs the downstream phases this loader feeds)
- `docs/audit/specs/01_eval_harness.md` — the eval-harness design (R5) the continuity context + exemplars feed into (judge in Phase 29). Read for how the judge consumes `previous_editions` angles + `exemplars`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **The continuity machinery is already fully built and wired — it is starved of data, not missing.**
  - Single-pass writer continuity block: `newsletter_poller.py:1148-1182` — reads `narrative_context.previous_editions`, injects the EDITORIAL CONTINUITY system-prompt block + the non-negotiable "opening MUST include a bridge" rule. Already consumes `{edition_number, title, primary_theme, opening_excerpt}`.
  - Block prepass: `block_pipeline.py:470` (`editorial_prepass_from_blocks`), uses `narrative_context.previous_editions` at `:508-510` and accepts `avoided_themes` at `:473`.
  - **`generate_from_blocks` already has an `exemplars: list[str] | None` parameter (`block_pipeline.py:567`)** — it is simply never passed by the caller. Phase E (`phase_e_voice_check`, `block_pipeline.py:404`) runs only `if exemplars:` (`:675`). Passing exemplars is the whole CTX-05 fix.

### Established Patterns
- **Injection point (D-injection):** `process_task` (`newsletter_poller.py:1996`) — call the loader and `input_data.setdefault('narrative_context', ctx)` after budget injection (~`:2034`) and before the block/single-pass branch (~`:2046`). `setdefault` ensures an upstream-provided `narrative_context` still wins (CTX-04). Both writer paths read `input_data.get('narrative_context')`, so this single injection covers both.
- **`.eq('status','published')` only — never `.in_()`** (known silent-failure bug). The loader query is `.eq('status','published').order('edition_number', desc).limit(N)`.
- Phase E `model_voice` defaults to `deepseek-chat` (`_bp_config.model_voice`) — Phase E voice scoring stays on DeepSeek; it is independent of the Sonnet judge added in Phase 29.

### Integration Points — TWO `generate_from_blocks` call sites (D-19)
- **`newsletter_poller.py:2078`** — primary block path, runs only when `block_pipeline.enabled = true`.
- **`newsletter_poller.py:2269`** — A/B comparison path, runs when single-pass is primary AND `block_pipeline.ab_comparison = true`.
- **Live config today: `enabled = false`, `ab_comparison = true`** → the A/B path (`:2269`) is the one that runs on every generation. **`exemplars=` must be passed at BOTH call sites** (pull from `input_data['narrative_context']['exemplars']`). The A/B site (`:2269`) is what makes the D-17 live Phase E verification work without flipping `enabled`.

### Live DB facts (project ref `zxzaaqfowtqvmsbitqpu`, confirmed 2026-06-22)
- `newsletters`: **32 published** (edition_number 1–32) + 17 held (25–102; edition numbers overlap because block_v1 A/B drafts are separate rows). Corpus is **non-empty** → bridge + exemplars + Phase E score all demonstrable on live data.
- Operator-written editions (`data_snapshot.operator_written='true'`): **25, 26, 27, 28, 30, 31, 32**. Edition **29** is `pipeline_version='block_v1'` (excluded from exemplars by D-01).
- `data_snapshot.lead_theme` populated only on **30, 31, 32**; null on 25–28 (→ backfill D-12). `data_snapshot.primary_theme` is **always null**.
- Recent published `content_markdown` starts directly at `## Read This, Skip the Rest` (no H1; openings already model the bridge: "Last week we wrote…", "For three editions we've tracked…").

</code_context>

<specifics>
## Specific Ideas

- The operator's emphasis throughout: **fail-loud over convenience**. Two refinements pushed past the spec/recommendation — (1) replace fallback-to-any-published with skip-and-surface a "not scored" voice verdict (D-02), and (2) omit `weeks_ago` on null `published_at` rather than fall back to the cadence-error-prone edition-number gap (D-09). Both are instances of "NULL ≠ intent; never a silent substitution or silent zero."
- The operator-written editions are treated as the canonical voice ("the voice we want"), explicitly NOT pipeline output — the exemplar corpus must never teach the judge the pipeline's own tics.

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope. (The downstream consumers of this loader — the Layer-2 judge, the `edition_evals` table, the deterministic gate, the rewrite loop, sequencer wiring, and Gato surfacing — are already scoped as Phases 27–31 and are explicitly out of scope here.)

</deferred>

---

*Phase: 26-continuity-exemplar-context*
*Context gathered: 2026-06-22*
