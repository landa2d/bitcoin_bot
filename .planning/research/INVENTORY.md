# Pre-Publish Evaluation Step — System Inventory

**Date:** 2026-06-22 · **Purpose:** Diagnostic map before proposing the milestone plan (operator-mandated: "produce a system map before touching anything").
**Method:** 3 parallel code-reading agents over the live tree + live Supabase reads (project `zxzaaqfowtqvmsbitqpu`) + the existing audit specs. All file:line refs verified against the working tree.

> **Headline:** This milestone is the operator's already-scoped audit item **R5 — "Edition eval harness (+ auto-hold + edit capture)"** (`docs/audit/specs/01_eval_harness.md`), *plus* a new **Layer-2 LLM-judge → feedback-rewrite loop** the milestone command adds on top. R5 depends on **R4** (`docs/audit/specs/07_continuity_and_exemplars.md` — continuity + exemplar loader), which the Layer-2 continuity/voice judge needs. The live data resolves the operator's central warning ("Phase D verified against the wrong fact base") decisively — see §2 and §5.

---

## 1. Pipeline flow → the precise pre-publish insertion point

Generation lives in the **newsletter service**; publish/delivery lives in the **processor**. They communicate only through `agent_tasks` + `newsletters` (Supabase).

```
Fri 11:00 UTC  processor.scheduled_prepare_newsletter()  →  inserts agent_tasks row {task_type:'write_newsletter'}
                  ↓ (newsletter service polls)
newsletter.process_task()                                                      (newsletter_poller.py:1996)
   ├─ single-pass path: editorial_prepass() + generate_newsletter()           (:2122)  ← PRODUCTION published draft
   └─ block path: generate_from_blocks()  (only if block_pipeline.enabled)     (block_pipeline.py:563)
   ↓
save_newsletter(...)  →  INSERT newsletters {status:'draft', both versions}    (:1551 def / :1613 insert / called :2234)
   ├─ verify_draft() runs here (Phase D) → writes verification_warnings        (:1630-1686)  [flag-not-block]
   └─ [A/B] generate_from_blocks() side-run → 2nd INSERT {status:'held', do_not_publish:true}  (:2238-2340)
   ↓
Fri 12:00 UTC  processor.scheduled_notify_newsletter()  →  Telegram "ready for review"   (:10620)
   ↓ (review window Fri→Mon — operator may publish early / preview / do nothing)
Mon 11:00 UTC  processor.scheduled_auto_publish_newsletter()  →  publish_newsletter()     (:10629 → :5858)
                  publish_newsletter():  fetch latest unpublished  →  verify_briefing_references() [flag-not-block]
                                         →  send_telegram + send_email (Resend)  →  UPDATE status='published'  (:5907)
```

**The "finalized draft exists, not yet published" window opens at `save_newsletter` (`newsletter_poller.py:1613`, `status='draft'`) and closes at the `publish_newsletter` status-flip (`agentpulse_processor.py:5907`).** Two candidate insertion points:

- **(A) Generation-time — `newsletter_poller.py:2234`, right after `save_newsletter()`.** Reached on **every** edition (both paths converge here). **This is the only point where the true source fact base is in memory** (`input_data` for single-pass, `blocks_data` for block path). It is exactly where Phase D already runs.
- **(B) Publish-time gate — `agentpulse_processor.py:5875-5897`, inside `publish_newsletter()`**, after the draft is fetched and before send/flip. Single convergence for both manual + auto publish; can hard-**block**. **But the fact base is gone by here** (only `data_snapshot` remains — see §4).

**Auto-publish is BY DESIGN and is opt-out, not opt-in:** the Monday job publishes the latest `['draft','pending']` edition unless the operator moved it to `preview`/`held` or it's <1h old. The "Monday review" is the human gate. (Stale copy bug noted: notify text says "13:00 UTC" but the job runs Monday 11:00.)

---

## 2. Existing Phase D verification (`docker/newsletter/verification.py`, 719 lines)

**Entry:** `verify_draft(prose: str, input_data: dict) -> dict` (`:483`). Extracts claims from the prose (`_extract_claims_from_prose`, `:141-296`) and matches them against a fact base built by `_build_block_list(input_data)` (`:299-480`).

**What it checks:** entities (bold `**X**`, multi-word caps, proper nouns, acronyms — large `_STOP_WORDS` list at `:16-93`); statistics (`$`/`%`/counts/ratios/word-numbers); dates; quotes (≥10 chars). Severity tiers: **Tier 1 CONFIRMED FABRICATION** (multi-word entities + quotes), Tier 2 LIKELY (stats/dates), Tier 3 POSSIBLE; plus **Tier 4 link-coverage** (anchorable entities need a nearby inline link, 200-char proximity). Returns `tier1_fabrications`, `tier2_likely`, `tier3_possible`, `tier4_link_coverage`, `summary{}`.

**What it does NOT do (gaps for the new deterministic layer):**
- **No live GitHub repo check** (no `api.github.com/repos/{owner}/{repo}`, no star-count compare).
- **No live URL liveness check** (no HEAD request).
- **arXiv IDs are deliberately stripped, never validated** (`_ARXIV_ID`, `:109`, filtered at `:287-289`) — a fabricated `2605.12673` passes unflagged.
- **No typed study/paper/benchmark field** — named studies are untyped entities (see §5).
- **No entity-merge / "verbatim in a single source" check** — matching is fuzzy substring.
- **No mechanical editorial checks** (H1-echo-in-body, reading-mode-label leak, recycled closer vs prior edition, stat duplicated-verbatim-from-prior-edition).

These six gaps are precisely the Layer-1 additions the milestone command specifies.

**When it runs:** `verify_draft` runs **unconditionally on every saved edition** inside `save_newsletter` (`:1619-1686`), in a try/except that logs-and-continues, writing `verification_warnings`. It is **not** behind a flag. **It is flag-not-block** — it annotates, never holds.

---

## 3. `edition_evals` table — DOES NOT EXIST (design-only)

Live check across **all schemas**: `edition_evals`, `newsletter_evals`, `eval_runs` → **none exist** (`information_schema.tables` returned `[]`; the 49-table `public` list has no eval table). It exists only as DDL in `docs/audit/specs/01_eval_harness.md` (`045_edition_evals.sql`, never applied).

**Migration numbering:** highest **applied** migration is **044** (`044_signals_anon_view`). On disk `043_economy_map_hub_and_negotiation_blocks.sql` exists but is **NOT applied** (live list jumps 042→044 — a known carry-over). **The next new migration number is `045`.** (Spec 01 already reserves `045_edition_evals.sql`.)

**`newsletters` columns (verified):** `id uuid`, `edition_number int`, `title text`, `content_markdown text`, `content_telegram text`, `data_snapshot jsonb`, `status text` (freeform — **no CHECK**), `published_at timestamptz`, `created_at timestamptz`, `primary_theme text`, `content_markdown_impact text`, `title_impact text`, `verification_warnings jsonb`.
- **No `do_not_publish` column and no `do_not_publish_reason` column.** Today `do_not_publish` lives only inside `data_snapshot` JSONB (set by the A/B path). Marking a *main* edition `held` programmatically (the milestone's Layer-1 action) is **net-new** — no code path currently does it (the operator has set `held` by hand via DB/MCP).
- **Dual versions** = separate columns on one row: `title`/`content_markdown` (technical) + `title_impact`/`content_markdown_impact` (strategic). Not separate rows.
- `held` status blocks both publish paths by exclusion (manual selects `['draft','pending','preview']`; auto selects `['draft','pending']`).

---

## 4. The CORRECT fact base — the crux (resolves the "wrong fact base" warning)

**The building blocks are NOT a table.** `select_blocks()` (`block_selection.py:30`) reconstructs them at generation time from the **`problems`** table (the extraction pool, 5,356 rows) over a `NOW()-7d` window — **non-deterministic** (DeepSeek picks tier-2/3 items) and the pool mutates, so it is **not reproducible after the fact**. There is **no edition→blocks foreign key.**

**What IS persisted per edition** = `newsletters.data_snapshot` (column comment: "input_data used to generate it"):

| Generation path | `data_snapshot` contains | Phase D `fact_base_source` |
|---|---|---|
| **single-pass** (production published) | full `input_data` (`premium_source_posts`, `clusters`, `predictions`, …) — **fully retrievable** | `input_data` |
| **block_v1** (A/B held copy) | only `block_summary` (counts) — **the actual `blocks[]` array is NOT stored** | `blocks` |

**Live confirmation (editions 99–102, each generated as a pair):** every row has `snap_has_blocks = false`. The single-pass row carries `premium_source_posts` + `fact_base_source='input_data'`; the block row carries `block_summary` + `fact_base_source='blocks'`.

```
ed 102 held  premium_sources=t  block_summary=f  fact_base=input_data     ← single-pass draft
ed 102 held  premium_sources=f  block_summary=t  fact_base=blocks         ← block_v1 A/B draft
(same shape for 101, 100, 99 …)   snap_has_blocks = false on ALL rows
```

**Resolution of the warning:** Phase D's *blocks* branch (`verification.py:314`, comment "Option B: verify against exactly what the writer was given") **is** the correct fact base — but it only populates when `blocks_data` is in memory, i.e. **at generation time** (`newsletter_poller.py:2234`). It is **unrecoverable at publish time.** Therefore the deterministic gate that needs the true fact base **must run inline at the two generation save points** (where `input_data`/`blocks_data` exist) — *not* in the processor at publish time. This is the single most important architectural consequence (see Decisions).

**Production reality:** with `config/agentpulse-config.json → block_pipeline.enabled = false, ab_comparison = true`, the **published** edition is **single-pass** (verify against `input_data`); `block_v1` is a throwaway `held` A/B copy (verify against `blocks`). So "the fact base the writer was given" = `input_data` for the edition that actually ships today.

---

## 5. Named studies / benchmarks / papers — representation

**No typed study/paper/benchmark/arXiv field anywhere.** The extraction LLM emits an untyped `named_entities[]` (`MULTISOURCE_EXTRACTION_PROMPT`, processor `:1673`) stored into **`problems.keywords` (TEXT[])** (`:4455`); `select_blocks` maps it back to `block['named_entities']` (`block_selection.py:383`). A fabricated study ("MCP authentication security study", "GroupMemBench") is catchable **only** as a Tier-1 entity fabrication when it appears in neither `block['named_entities']` nor the block `description` text. There is **no positive list of real paper/benchmark titles** and **no arXiv validation**. A robust "named study not in any single source → flag" check is net-new and depends on the in-memory fact base from §4.

**Acceptance-test fixtures located (held editions in the DB):**
- **Edition 36** (held, 2026-05-22) — contains **"MCP authentication"** → the spec's named "MCP authentication security study" edition.
- **Edition 34** (held, 2026-05-15) — contains **"GroupMemBench"**.
Both are real held rows usable as known-fabricated fixtures for acceptance criterion #2.

---

## 6. Gato notification mechanism (processor → operator)

**One synchronous helper: `send_telegram(message)` (`agentpulse_processor.py:9599`)** — a **direct Telegram Bot API call** (`httpx.Client()` POST to `api.telegram.org/.../sendMessage`), **not** via gato_brain and **not** via the queue files. Resolves the destination internally from module globals `TELEGRAM_BOT_TOKEN` + `TELEGRAM_OWNER_ID` (`:396-397`, from `config/.env`). Auto-splits at 4000 chars. Callable from sync `schedule` jobs (already used by `scheduled_notify_newsletter`, health checks, digest).

**Reliability = fail-SOFT (a governance gap to harden):** silent `return` if either env var is unset (`:9601`); on send failure it falls back Markdown→plain then `logger.error`s and continues — no raise, no success signal. **There is no existing "edition held / fabrication" Telegram alert** — that wiring is net-new. Useful adjacent patterns: per-check cooldown (`_health_check_cooldown_ok` `:10980`) and proactive-alert budget (`increment_daily_usage(...alerts=1)` `:7999`).

---

## 7. Alignment with the existing audit plan

This milestone **is** audit roadmap **R5** (`01_eval_harness.md`, "HIGHEST leverage", closes G-01/G-06/G-07/WS-04/WS-05), which **depends on R4** (`07_continuity_and_exemplars.md`, closes G-05/WS-17/WS-18). Where the milestone command and spec 01 **agree**: two-layer eval, deterministic fabrication reusing `verify_draft` against the same fact base, `edition_evals` persistence, run in the newsletter service at the two save points, governed `edition_eval` agent via the proxy (own wallet, `allow_negative=false`, hard cap), report-only activation gate, fail-loud (`eval_status='error'` never a silent zero), `/newsletter_eval` Gato command (+ allowlist landmine).

Where the milestone command **extends** spec 01 (new scope to plan):
- **Layer-2 LLM-judge → feedback-rewrite loop, N=2 max** (spec 01 was report-only; no auto-rewrite). Requires per-attempt telemetry → a different `edition_evals` shape (attempt_number, layer, scores jsonb, feedback, verdict) than spec 01's one-row-per-draft.
- **Live GitHub + URL liveness checks** and **entity-merge / verbatim-single-source** check in Layer 1 (beyond `verify_draft`).
- **Mechanical editorial regex checks** (H1-echo, mode-label leak, recycled closer, dup-stat-vs-prior).
- **Hard short-circuit:** any fabrication flag → `held` + escalate, **never** enters the rewrite loop.

The model id `claude-sonnet-4-20250514` in spec 01's DDL is **EOL** — use **`claude-sonnet-4-6`** (per quick task 260619-ko8). The editorial-synthesis model constraint stands; all LLM via `llm-proxy:8200`.

---

## 8. Decisions this inventory forces (for operator approval before the plan)

1. **Where the eval runs (vs. the milestone command's "Layer 1 runs in the Processor").** The true fact base only exists in-memory in the **newsletter service** at the two generation save points (§4); it is gone by publish time. **Recommendation:** run *both* layers in the newsletter service at `save_newsletter` return (the `newsletter_poller` is the dumb sequencer that calls Layer-1, then the Layer-2 module, and acts on verdicts). The **literal Processor** keeps its role unchanged — triggers generation, owns the publish gate, surfaces eval results in the Friday notify via a plain select — **no LLM, no retry-state in the processor**, honoring every architectural rule. (Alternative: literally in the processor → requires persisting `blocks_data` to the DB so the processor can reload it. More work, weaker — not recommended.)
2. **Fold in R4 (spec 07 continuity + exemplar loader) as the first phase.** The Layer-2 continuity dimension ("bridge to edition N-1", judge given last-3 editions' angles) and the exemplar-anchored voice prompts both **require** the prior-edition/exemplar loader, which does not exist yet. **Recommendation:** yes — Phase 1 of this milestone.
3. **`edition_evals` schema = per-attempt telemetry** (supports the rewrite loop): `(edition id/number, attempt_number, layer, deterministic flags jsonb, judge scores jsonb, judge feedback text, verdict)`. **SQL-first — proposed in the plan, applied by operator via MCP after approval.** Next migration number = **045**.
4. **Authority:** treat the **milestone command as authoritative**; audit spec 01/07 as the implementation reference (wiring points, `verify_draft` reuse, agent/wallet seeding pattern, fail-loud rules). Milestone version proposed: **v2.3**.
