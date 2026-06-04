# Phase 5: Intake Classifier + `unsorted` Handling - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

<domain>
## Phase Boundary

When a newsletter edition's tier-1 events are finalized, classify each event (DeepSeek V3,
routed through `llm-proxy:8200`) to an `economy_map` `block_slug` + a `tag_confidence` score,
and INSERT a row into `economy_map.timeline_entries`: confidence ≥ floor → the named block's
timeline; below floor → `'unsorted'`. Every entry carries `source_edition_id` for traceback.
Covers INTK-01..05.

**Already delivered by Phase 2 (do NOT rebuild):** the `economy_map.timeline_entries` table and
its columns, the append-only enforcement (BEFORE UPDATE/DELETE trigger — **INTK-05 is structurally
satisfied**), `'unsorted'` as a valid non-FK `block_slug`, `source_edition_id` as TEXT, and
newest-first indexing. Phase 5 builds **only the INSERT path** (emit → classify → route → insert)
and a test proving append-only still holds.

**Out of scope (other phases):** operator `/map-*` commands incl. `/map-assign` for reassigning
`unsorted` entries (Phase 10); per-block synthesis of `block_body_versions` (Phase 7); any renderer
change (Phase 4, shipped).
</domain>

<decisions>
## Implementation Decisions

### Emit trigger (INTK-01)
- **D-01:** Classification runs as a **scheduled poller in the processor**, not inline in the
  newsletter service. Rationale: matches existing architecture (processor owns scheduled
  DB-polling + `routed_llm_call` + the DeepSeek circuit breaker), and decouples classification so a
  slow or failing classifier never blocks newsletter generation. Intake is the autonomous side of
  the project's autonomy boundary — background processing fits the processor.
- **D-02:** The poller classifies editions in a **finalized/published state only — NOT
  in-progress or `'held'` drafts** — so events from abandoned/unpublished drafts are not ingested.
  *(Researcher must confirm the exact `public.newsletters` status value(s) that mean "finalized" —
  e.g. `published` vs a save/complete marker — and the column name. This default protects the
  gating spine; adjust only if the schema dictates otherwise.)*
- **D-03:** The classification unit is the **tier-1 events** of an edition (per ROADMAP success
  criterion 1 and INTK-01). Tier-1 events are identified in the block pipeline by
  `max_source_tier == 1` (see `block_selection.py`). One timeline candidate per tier-1 event.

### Entry composition (INTK-01/02)
- **D-04:** **Extract + classify-only.** The timeline entry's prose fields
  (`what_shifted`, `why_it_mattered`, `source_url`, `event_date`) are pulled from the newsletter
  event's already-extracted/verified fields; the LLM call does **only** `block_slug` +
  `tag_confidence`. Rationale: keeps timeline prose grounded in Phase-D-verified content (0
  fabrications), is cheaper (classification-only DeepSeek call), and avoids a second generation
  step that could reintroduce fabrication. *(Researcher: confirm which event fields map to
  `what_shifted` / `why_it_mattered` / `source_url` / `event_date`; the timeline display contract
  is `<event_date> · <what_shifted> / <why_it_mattered> [source ↗]`.)*

### Confidence floor + failure handling (INTK-03) — spine-critical
- **D-05:** **Flagged, never dropped.** Below floor → write to `'unsorted'` with `tag_confidence`
  recorded. Classifier error / DeepSeek circuit-break → **also** write to `'unsorted'` with
  `tag_confidence = NULL`, so an event that came in is never silently lost. Matches the project's
  core failure-mode design (silence is the enemy; a flagged entry beats a missing one) and
  fail-loud governance.
- **D-06:** The confidence floor is **config-driven** (in `config/agentpulse-config.json`),
  **default 0.6**, so it can be tuned without a redeploy.
- **D-07:** The classifier's **best-guess slug for below-floor entries is NOT persisted** — only
  `tag_confidence` is recorded (the Phase 2 `timeline_entries` schema is locked and has no spare
  metadata column). The operator re-decides the block later via reassignment (Phase 10). Do NOT
  add a column to the Phase 2 schema for this.

### Idempotency (INTK-01 robustness)
- **D-08:** Exactly-once emission via a **pre-emit existence check on `source_edition_id`**: before
  emitting an edition's entries, check whether any `timeline_entries` already carry that
  `source_edition_id`; skip if so. Uses the INTK-04 key already required, needs no new
  infrastructure, and is append-only-safe. Accepted trade-off: an edition regenerated with
  *different* events will not re-emit (acceptable — re-emission would risk duplicating the map).

### Claude's Discretion
- Exact prompt text + JSON output schema for the DeepSeek classifier (researcher/planner; follow
  the `MULTISOURCE_EXTRACTION_PROMPT` pattern and JSON-with-regex-fallback parsing).
- Poller interval / schedule slot among the processor's existing `schedule` jobs.
- Whether classification batches multiple events per LLM call or one-per-call (cost vs latency).
- Which of the 7 block slugs are presented to the classifier as the allowed label set (likely all
  seven from `economy_map.blocks`, fetched via Accept-Profile PostgREST).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Schema (the locked foundation — read first)
- `supabase/migrations/033_economy_map_schema.sql` — `economy_map.timeline_entries` columns
  (`block_slug`, `event_date`, `what_shifted`, `why_it_mattered`, `source_url`,
  `source_edition_id` TEXT, `tag_confidence` NUMERIC(3,2), `id`, `created_at`), the
  `timeline_entries_append_only()` trigger (INTK-05, already enforced), `'unsorted'` validity, and
  the anon RLS policy that hides `'unsorted'`.
- `.planning/phases/02-economy-map-schema-seven-block-seed/02-CONTEXT.md` — Phase 2 locked schema
  decisions (D-07 unsorted, D-11 pinned/append-only columns, D-12 lifecycle, D-13 seven blocks).

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — INTK-01..05.
- `.planning/ROADMAP.md` § "Phase 5: Intake Classifier + `unsorted` Handling" — goal + 5 success
  criteria (incl. the append-only acceptance test and the `source_edition_id` join check).

### Emit source (the newsletter pipeline)
- `docker/newsletter/newsletter_poller.py` — where editions are generated/saved; the poller reads
  finalized editions from here / `public.newsletters`.
- `docker/newsletter/block_selection.py` — tier-1 event identification (`max_source_tier == 1`),
  event field shape (`named_entities`, `source_url`, description).
- `docker/newsletter/block_pipeline.py` — `generate_from_blocks` output shape.

### Classification mechanism (LLM via proxy — mandatory)
- `docker/processor/agentpulse_processor.py` — `routed_llm_call()`, the `MULTISOURCE_EXTRACTION_PROMPT`
  prompt-constant pattern, the DeepSeek circuit breaker (`_is_deepseek_available` /
  `_record_deepseek_failure`), and the `schedule`-based job registration.
- `docker/llm-proxy/proxy.py` — the mandatory gateway on port 8200 (per-agent key, reserve/settle).
- `.planning/PROJECT.md` § Constraints — LLM-via-proxy rule (RivalScope anti-pattern); `economy_map`
  access via direct PostgREST with `Accept-Profile: economy_map` (never supabase-py `.in_()`).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `economy_map.timeline_entries` (migration 033): target table — all needed columns exist,
  including `tag_confidence NUMERIC(3,2)` explicitly annotated "populated by Phase 5 classifier".
- `timeline_entries_append_only()` trigger: INTK-05 already enforced — Phase 5 only needs a test
  asserting UPDATE/DELETE fails.
- `routed_llm_call()` (processor): the proxy-routed LLM dispatcher — use for the DeepSeek call.
- DeepSeek circuit breaker (processor): reuse to drive D-05's "error → unsorted with NULL
  confidence" path.
- `MULTISOURCE_EXTRACTION_PROMPT` (processor): the module-level prompt-constant + JSON-parse pattern
  to mirror for the classifier prompt.

### Established Patterns
- Processor scheduled jobs via the `schedule` library (not system cron) — the poller registers here.
- `economy_map` reads/writes via direct PostgREST + `Accept-Profile: economy_map` header (NOT
  supabase-py `.in_()`, which silently fails) — INSERTs to `timeline_entries` follow this.
- Tier-aware event handling already exists in `block_selection.py` (tier-1 = `max_source_tier == 1`).

### Integration Points
- Read side: finalized editions + their tier-1 events from `public.newsletters` / newsletter
  pipeline output.
- Write side: INSERT into `economy_map.timeline_entries` (service_role) via PostgREST.
- Config: floor threshold in `config/agentpulse-config.json`.
</code_context>

<specifics>
## Specific Ideas

- Timeline display contract (from Phase 3 tokens, must be satisfiable by the extracted fields):
  `<event_date> · <what_shifted> / <why_it_mattered> [source ↗]`.
- Default confidence floor: **0.6** (matches ROADMAP success criterion 3; now config-tunable).
</specifics>

<deferred>
## Deferred Ideas

- Operator reassignment of `unsorted` entries (`/map-assign`) and the rest of the `/map-*` command
  surface — Phase 10.
- Persisting the classifier's below-floor best-guess slug — intentionally deferred (would require a
  schema change to the locked Phase 2 table; revisit only if operator reassignment proves it's
  needed).
- Per-block synthesis triggered by new timeline entries — Phase 7.

*Discussion stayed within phase scope; no scope creep surfaced.*
</deferred>

---

*Phase: 05-intake-classifier-unsorted-handling*
*Context gathered: 2026-05-28*
