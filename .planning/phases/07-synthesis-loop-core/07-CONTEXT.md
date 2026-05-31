# Phase 7: Synthesis Loop Core - Context

**Gathered:** 2026-05-31
**Status:** Ready for planning

<domain>
## Phase Boundary

The autonomous editorial engine. Per block, a scheduled loop evaluates a threshold trigger; when a
block is eligible it assembles input (current `published` body + new `timeline_entries` ordered by
`event_date` + `live_tension` + current `maturity`), makes **one** Claude Sonnet call routed through
`http://llm-proxy:8200` using a **hot-reloadable** `synth_identity.md` system prompt, and writes
**one new `economy_map.block_body_versions` row with `status='draft'`**, a populated `body_md`, and a
`proposed_maturity`. The live `published` row and `blocks.maturity` are NOT touched here. Covers
SYNT-01..06.

**Already delivered (do NOT rebuild):**
- `economy_map.block_body_versions` (migration 033) — columns `body_md`, `proposed_maturity` (NOT
  NULL — every synthesis MUST emit one), `synthesized_from_through`, `status` (default `draft`),
  `validator_report` (Phase 8 populates), append-only trigger on pinned columns. The partial
  `status='draft'` index exists.
- `economy_map.blocks` — `maturity` enum, `live_tension` (NOT NULL, seeded **placeholder** until
  Phase 10 `/map-tension`), `last_synthesized_at` (nullable; advanced only on PUBLISH in Phase 9),
  `current_body_version_id` (NULL until first publish).
- `economy_map.timeline_entries` (Phase 5 intake) — the entries to synthesize, incl. `event_date`,
  `created_at`, `what_shifted`, `why_it_mattered`, `source_url`, `block_slug`.
- Processor infra: the `schedule` library, `routed_llm_call()` (POSTs to llm-proxy
  `/v1/chat/completions`), the DeepSeek circuit breaker, the economy_map PostgREST read/write helpers
  (Phase 5), fail-loud patterns.
- An **mtime hot-reload pattern** in `docker/analyst/analyst_poller.py` (`_identity_cache` /
  `_identity_mtime` / `stat().st_mtime`) — the analog to reuse for `synth_identity.md` (SYNT-05).
- The newsletter Sonnet editorial path (`docker/newsletter/block_pipeline.py`,
  `claude-sonnet-4-20250514` via the `/anthropic` proxy base_url) — reference for prose quality and
  the sanctioned proxy routing, NOT the host of this loop.

**Out of scope (other phases):** validation sentinels + `validator_report` population + the Telegram
flag card (Phase 8); `/map-approve` / `/map-reject`, the atomic publish transaction, advancing
`last_synthesized_at`, re-render trigger (Phase 9); `/map-tension`, `/map-synth` force-resynth,
`/map-identity` voice editor (Phase 10). Synthesis here writes **draft only** — never `published`.
</domain>

<decisions>
## Implementation Decisions

### Placement (where the loop lives)
- **D-01: The synthesis loop lives in the PROCESSOR**, as a new scheduled poller alongside the
  Phase-5 intake classifier. Rationale: the processor is the autonomous-spine home (owns scheduled
  `schedule` jobs, the economy_map PostgREST helpers, the circuit breaker, `routed_llm_call`, and
  fail-loud conventions); keeping intake→synthesis in one service matches Phase 5's precedent
  (05-CONTEXT D-01). The newsletter `block_pipeline` is edition/dual-audience-prose-specific and not
  directly reusable; the reusable piece ("a Sonnet call through the proxy") is `routed_llm_call`.
  *(Researcher: confirm `routed_llm_call` resolves and routes `claude-sonnet-4` cleanly through
  llm-proxy `/v1/chat/completions` with a large enough `max_tokens` for a full body. If it does NOT
  handle Sonnet well, port the newsletter `anthropic`-SDK-via-`/anthropic` client into the processor
  rather than relocating the loop — placement stays the processor either way.)*

### Trigger evaluation (SYNT-01/02) — spine-critical
- **D-02: Watermark = `blocks.last_synthesized_at`** for BOTH the N-count and the T=30-day clock
  (operator choice; single column). Because `last_synthesized_at` only advances on PUBLISH (Phase 9
  `/map-approve` per GATE-02), the trigger MUST also apply:
- **D-03: "No pending draft" eligibility guard** — a block with an existing `status='draft'`
  `block_body_versions` row is **NOT eligible**. One in-flight draft per block. This is the mechanism
  that makes the `last_synthesized_at`-only choice correct (prevents duplicate drafts piling up while
  a draft awaits approval) and dovetails with Phase 9 `/map-reject` (reject → no draft → block
  re-eligible, re-feeding the same unabsorbed entries — exactly GATE-03's intent).
- **D-04: Recency compares by `created_at`** (`entry.created_at > blocks.last_synthesized_at`), NOT
  `event_date`. `last_synthesized_at` is wall-clock; `event_date` is an editorial date that can be
  **backdated** (an entry ingested today with an event_date last week would wrongly count as
  not-new). `event_date` is used ONLY for ordering entries in the prompt (D-07, SYNT-03 / RNDR-07).
- **D-05: Eligibility predicate** = `(no draft for block)` AND `(count(new entries) >= N=5` **OR**
  `(now - last_synthesized_at >= T=30d AND count(new entries) >= 1))`. N=5/T=30 are GLOBAL (no
  per-block tuning — v2-deferred). *(Researcher/planner: source N and T from
  `config/agentpulse-config.json` if a synthesis config block is added, mirroring the Phase-5
  `intake_classifier.confidence_floor` pattern; default 5 / 30 days.)*
- **D-06: Cold-start** (NULL `last_synthesized_at`, never synthesized): all the block's entries count
  as "new" → eligible at **≥5**, or **≥1 once 30 days** have passed since the block's **earliest**
  entry (`created_at`).

### Input assembly (SYNT-03)
- **D-07: Window + ordering.** Input entries = entries with `created_at > last_synthesized_at`
  (NULL → all), **ordered by `event_date`** (newest-first consistent with RNDR-07). Pass **concrete
  entry content** (`event_date`, `what_shifted`, `why_it_mattered`, `source_url`) — never bare
  cluster labels (SYNT-03 hard rule).
- **D-08: Cold-start input (no prior body).** When the block has no `published` body
  (`current_body_version_id` NULL): prompt = the entries (D-07) + current `maturity` (nascent) +
  `live_tension` (use it even if it's still the seed placeholder) + the **six-part skeleton headings**
  as the structure to produce. **No "prior body" section.** The model writes the block's first
  `body_md`. Synthesis proceeds even against a placeholder `live_tension` (the loop synthesizes; the
  operator frames later via Phase 10) — do NOT block cold-start on tension being set.
- **D-09: High-volume cap (fail-loud, never silent).** A block may have many unabsorbed entries
  (observed: 24). Feed **all** entries since the watermark, ordered by `event_date`, **bounded by a
  token budget**; if the set exceeds the budget, include the **most-recent up to the cap** and
  **log + note the omitted count** in the prompt/run log. Never silently drop entries. Preserves the
  single-call constraint (SYNT-04). *(Researcher: set the exact token budget / approximate entry
  ceiling and the output `max_tokens` for a full body.)*

### Editorial identity (SYNT-04/05/06)
- **D-10: Single Sonnet call via proxy.** Exactly ONE editorial LLM call per synthesis, Claude
  Sonnet, routed through `http://llm-proxy:8200` (NO direct SDK to `api.anthropic.com` — the
  RivalScope anti-pattern; both the processor `routed_llm_call` `/v1/chat/completions` path and the
  newsletter `/anthropic` SDK path are sanctioned proxy routes — see D-01).
- **D-11: `synth_identity.md` is a FILE with mtime hot-reload** (honors SYNT-05 literally). Ship a
  **working default** voice (consistent with the newsletter prose) at
  **`config/economy_map/synth_identity.md`**, mounted into the processor container; load it
  mtime-cached (reuse the `analyst_poller.py` pattern). Editing the file changes the next call's
  system prompt with **no restart**. **Fail-loud:** if the file is missing or empty, log loudly and
  **skip that synthesis cycle** — never synthesize voiceless. (A `/map-identity` Telegram editor that
  writes to this same file is **deferred to Phase 10**.)
- **D-12: Output = `body_md` + `proposed_maturity` from the single call.** `proposed_maturity` is NOT
  NULL on the schema, so the call MUST yield one of the five enum values
  (`nascent`/`emerging`/`contested`/`consolidating`/`mature`). Treat the exact output format
  (structured JSON `{body_md, proposed_maturity}` vs a tagged trailer) as Claude's discretion, but the
  parser MUST validate `proposed_maturity` against the enum and fail-loud (skip the write, log) on an
  invalid/missing value rather than defaulting silently.
- **D-13: Draft write.** On success, INSERT exactly one `block_body_versions` row:
  `block_slug`, `body_md`, `proposed_maturity`, `status='draft'` (default), and
  `synthesized_from_through` = the synthesis run timestamp (the through-point Phase 9 will copy into
  `last_synthesized_at` on approve). Do NOT touch the `published` row, `blocks.maturity`, or
  `blocks.current_body_version_id` (autonomy boundary — Phase 9 owns those). Append-only trigger
  already enforces no-mutation of pinned columns.

### Claude's Discretion
- Output format for D-12 (structured JSON vs tagged) and the exact prompt template / skeleton-heading
  wording (follow the newsletter prose voice + the six-part block skeleton from RNDR-02).
- Schedule cadence / poll slot among the processor's `schedule` jobs (SYNT-02 explicitly defers this
  to the executor).
- Exact token budget, output `max_tokens`, and entry ceiling for D-09.
- Whether to use `routed_llm_call` vs a ported `/anthropic` SDK client (D-01 researcher flag).
- Whether trigger eval iterates all seven blocks per cycle or batches — low volume (7 blocks).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Schema (locked foundation — read first)
- `supabase/migrations/033_economy_map_schema.sql` — `block_body_versions` (body_md,
  `proposed_maturity` NOT NULL, `synthesized_from_through`, `status` draft default, `validator_report`,
  the append-only trigger on pinned columns); `blocks` (`maturity` enum + order, `live_tension`
  NOT NULL placeholder, `last_synthesized_at`, `current_body_version_id`); `timeline_entries`
  (`event_date`, `created_at`, `what_shifted`, `why_it_mattered`, `source_url`, `block_slug`); the
  maturity enum order `nascent→emerging→contested→consolidating→mature` (≈:35-52).
- `.planning/phases/02-economy-map-schema-seven-block-seed/02-CONTEXT.md` — Phase 2 locked schema +
  seed decisions (D-11 pinned/append-only columns, D-12 lifecycle status/published_at, the atomic
  publish transaction that Phase 9 — NOT Phase 7 — runs).

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — SYNT-01..06 (and the downstream GATE-01 draft-only invariant Phase 7
  must not violate).
- `.planning/ROADMAP.md` § "Phase 7: Synthesis Loop Core" — goal + 5 success criteria.
- `.planning/PROJECT.md` § Constraints — LLM-via-proxy (RivalScope anti-pattern); `economy_map` via
  direct PostgREST `Accept-Profile: economy_map` (never supabase-py `.in_()`/`.schema()`);
  "`live_tension` and `synth_identity.md` stay operator-controlled — the loop synthesizes, the
  operator frames."

### Loop host + LLM routing (the processor)
- `docker/processor/agentpulse_processor.py` — `routed_llm_call()` (≈:506, POSTs to llm-proxy
  `/v1/chat/completions`), `get_model()` (≈:462), the `schedule`-based job registration, the
  economy_map PostgREST helpers (insert ≈:573, reads ≈:600-660, `_fetch_economy_map_block_slugs`
  ≈:3043), the Phase-5 intake poller (`classify_intake_*` ≈:3073-3276) as the structural analog for
  a new synthesis poller, and the DeepSeek circuit breaker.

### Hot-reload + editorial-voice references
- `docker/analyst/analyst_poller.py` (≈:69-120) — the mtime-cached identity-file load pattern to
  reuse for `synth_identity.md` (SYNT-05).
- `docker/newsletter/block_pipeline.py` + `docker/newsletter/newsletter_poller.py` — the Sonnet
  editorial prose path (`claude-sonnet-4-20250514` via `{LLM_PROXY_URL}/anthropic`), voice/quality
  reference and the fallback client pattern if `routed_llm_call` can't host Sonnet (D-01).
- `config/persona.md`, `config/guardrails.md` — existing mounted operator-controlled config files;
  the convention `config/economy_map/synth_identity.md` follows (D-11).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `routed_llm_call()` (processor): proxy-routed LLM dispatcher — the single Sonnet call (D-10),
  pending researcher confirmation it handles Sonnet (D-01).
- Phase-5 intake poller (processor `classify_intake_*`): structural analog for a new
  `synthesize_blocks` scheduled poller (trigger eval → assemble → call → INSERT draft).
- economy_map PostgREST helpers (processor): reads for blocks/entries/draft-existence; INSERT helper
  for the draft row (Content-Profile write, append-only-safe).
- `analyst_poller.py` mtime-cached identity loader: copy for `synth_identity.md` hot-reload (D-11).
- `block_pipeline.py` Sonnet prose path: voice reference + fallback `/anthropic` client (D-01).

### Established Patterns
- Processor scheduled jobs via `schedule` (not cron) — the synthesis poller registers here (SYNT-02).
- `economy_map` reads/writes via direct PostgREST + `Accept-Profile`/`Content-Profile: economy_map`
  (never supabase-py `.schema()`/`.in_()`).
- Config-driven thresholds in `config/agentpulse-config.json` (mirror Phase-5 floor) for N/T (D-05).
- Fail-loud: raise/log + skip on missing identity, invalid maturity, or read failure — never silent
  default or silent drop (D-09/D-11/D-12).

### Integration Points
- Read: `economy_map.blocks` (watermark, maturity, live_tension, current_body_version_id),
  `block_body_versions` (draft-existence guard + current published body), `timeline_entries`
  (the synthesis window).
- Write: INSERT ONE `block_body_versions` row, `status='draft'` (D-13) — no other economy_map writes.
- Config: N/T thresholds; mounted `config/economy_map/synth_identity.md`.
- Downstream: the `draft` row + `proposed_maturity` feed Phase 8 sentinels and Phase 9 `/map-approve`;
  `/map-pending` (Phase 6) already surfaces these drafts to the operator.
</code_context>

<specifics>
## Specific Ideas

- Eligibility predicate (D-05): `(no draft) AND (new_count >= 5 OR (age >= 30d AND new_count >= 1))`,
  new = `created_at > last_synthesized_at` (NULL → all).
- Cold-start (D-08): synthesize from entries + maturity + live_tension(placeholder OK) + 6-part
  skeleton; no prior-body section.
- Draft row (D-13): `status='draft'`, `synthesized_from_through = run timestamp`; never touch
  published / blocks.maturity / current_body_version_id.
- Maturity enum order (for proposed_maturity validation): nascent → emerging → contested →
  consolidating → mature.
- Identity file path: `config/economy_map/synth_identity.md` (working default, mounted, mtime reload).
</specifics>

<deferred>
## Deferred Ideas

- `/map-identity` Telegram command to edit `synth_identity.md` voice from the phone (writes to the
  same file) — **Phase 10** (operator write commands).
- Validation sentinels + `validator_report` population + the Telegram flag card — **Phase 8**.
- `/map-approve` / `/map-reject`, the atomic publish transaction, advancing `last_synthesized_at`,
  block-page re-render — **Phase 9**.
- Per-block N/T threshold tuning — **v2** (TUNE-01..03); Phase 7 ships global N=5/T=30 only.

*Discussion stayed within phase scope; no scope creep surfaced. None of the 6 pending todos match
this phase's scope (analyst bug, governance, payments, Phase-05/06 review follow-ups, research perms)
— not folded.*
</deferred>

---

*Phase: 07-synthesis-loop-core*
*Context gathered: 2026-05-31*
