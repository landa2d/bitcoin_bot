# Phase 8: Validation Sentinels - Context

**Gathered:** 2026-06-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Every synthesized draft (the `status='draft'` `block_body_versions` rows Phase 7 produces) is
annotated with four structured validation flags written into the draft's `validator_report` jsonb,
and those flags surface **loudly** on the operator's `/map-pending` Telegram listing. **Sentinels
annotate, they never block draft creation** — a flagged draft is the visible outcome (silence is the
enemy). Six requirements: VLDT-01 (tension preserved), VLDT-02 (length floor), VLDT-03 (maturity
jump guard), VLDT-04 (structure intact), VLDT-05 (annotate-not-block), VLDT-06 (loud Telegram
surfacing).

**In scope:** computing the four sentinels + a `requires_attention` rollup at synthesis time;
writing them into `validator_report`; rendering them on `/map-pending`.
**Out of scope (other phases):** `/map-approve` / `/map-reject` and the atomic publish transaction
(Phase 9); a dedicated per-draft approval card (Phase 9); any `live_tension` editing (Phase 10).
</domain>

<decisions>
## Implementation Decisions

### Structure check — gate vs. sentinel (reconciling Phase 7 WR-02)
- **D-01:** The skeleton-heading check moves from a hard parse-gate to a **VLDT-04 sentinel that
  annotates, not blocks.** Phase 7's WR-02 fix made `parse_synthesis_output` *raise* (skip the
  draft) when any of the six `SYNTH_SKELETON_HEADINGS` was missing. That BLOCKS — directly contrary
  to this phase's thesis (VLDT-04 + VLDT-05: structure problems annotate loudly, draft still lands,
  operator decides; a silent skip is itself a form of silence). **Remove the missing-headings raise
  from `parse_synthesis_output`**; keep it raising ONLY on empty `body_md` / invalid / missing
  `proposed_maturity` (genuinely unusable model output that can't be drafted). The structure sentinel
  recomputes `structure_missing = [h for h in SYNTH_SKELETON_HEADINGS if h not in body]` pre-insert.
- **D-01a (planner action):** swap the Phase 7 test `test_parse_output_raises_on_missing_skeleton`
  (in `tests/test_07_synthesis.py`) — it now asserts the OPPOSITE of the new behavior. Replace with
  a VLDT-04 sentinel test (missing-heading body → draft lands + `structure_missing` populated +
  `requires_attention=true`). The other Phase 7 parse tests (empty body, invalid/missing maturity)
  stay as-is.

### Where sentinels run + how the report is stored
- **D-02:** `validator_report` is a **pinned/append-only column** (migration 033 §5 + the
  `block_body_versions_append_only()` trigger RAISES if `validator_report` changes on UPDATE).
  Therefore sentinels CANNOT annotate a draft after it lands — they run **inside `synthesize_block`,
  between `parse_synthesis_output` and the INSERT**, building the full `validator_report` dict that
  is passed into `economy_map_insert_block_body_version` so it's written atomically at insert time.
- **D-03:** `requires_attention` lives as a **key inside the `validator_report` jsonb** — **no
  migration.** There is no `requires_attention` column today and we are not adding one (migration-
  caution; `/map-pending` fetches ≤7 drafts so no indexable column is needed). Report shape:
  `{tension_preserved: bool, length_below_floor: bool, structure_missing: [str], maturity_jump: int,
  requires_attention: bool}` (exact keys are the planner's to finalize, but these are the locked
  concepts).
- **D-04:** `requires_attention` is a **rollup — true if ANY of the four sentinels raises a
  concern:** `(not tension_preserved) or length_below_floor or (maturity_jump > 1) or
  bool(structure_missing)`. It is the single "needs a careful human look" signal the card headline
  keys off.

### Sentinel detection semantics
- **D-05:** **Tension-preserved (VLDT-01) is deterministic — no extra LLM call.** Flag
  `tension_preserved=false` when the live-tension section is absent, OR its body is below a char
  floor, OR it is effectively the placeholder (`(no live_tension set yet)`) or a verbatim echo of
  `blocks.live_tension` (synthesis didn't engage it). Catches the gross failures; the operator's
  downstream approval catches subtle "present but shallow" cases. **v2 upgrade path:** an LLM judge
  for shallow-but-present trivialization (deliberately deferred for cost — it would add a second
  Sonnet call per block per cycle against the $/week budget cap).
- **D-06:** **Length floor (VLDT-02)** uses a **character-count** ratio (`len(new_body) /
  len(prior_published_body)`); flag `length_below_floor=true` when `< 0.60`. **Cold-start (no prior
  `published` body) → length sentinel is N/A — not a flag** (don't penalize the first draft of a
  block).
- **D-07:** **Maturity jump (VLDT-03)** = **absolute ordinal distance** between `proposed_maturity`
  and the block's current `blocks.maturity` on the 5-value enum
  (`nascent→emerging→contested→consolidating→mature`); `maturity_jump > 1` stop fires the flag and
  (via D-04) `requires_attention`.

### Telegram surfacing (VLDT-06)
- **D-08:** `/map-pending` (Phase 6 `handle_map_pending` in `gato_brain.py`) is **extended** so flags
  are the visible outcome: each draft with `requires_attention=true` gets a **`⚠ REQUIRES
  ATTENTION` headline marker**, followed by an **indented per-flag detail list** with concrete detail
  (maturity direction+delta e.g. `nascent→contested (+2)`, length `48% of prior (floor 60%)`,
  `tension trivialized`, missing headings). **Serious flags ordered first**; a clean draft shows a
  quiet `✓ clean`. Read-only by construction stays intact (this is render-only; no new write verbs).

### Claude's Discretion
- The markdown heading-section splitter that extracts the live-tension section body (for D-05) and
  detects heading presence (for D-01) — approach is the planner/executor's call (a simple
  `## <heading>` line scanner over `body_md` is expected; reuse `SYNTH_SKELETON_HEADINGS`).
- Exact `validator_report` key names and the per-flag card wording, as long as D-03/D-04/D-08
  concepts hold.
- Whether the four sentinels live as one `run_sentinels(body, prior_body, block, proposed_maturity)
  -> dict` helper or separate functions — planner's call (one composable helper is the natural fit,
  mirroring the Phase 7 primitives style).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 8: Validation Sentinels" — goal + 5 success criteria (the
  must-haves; SC5 is the annotate-not-block + loud-surfacing invariant)
- `.planning/REQUIREMENTS.md` §"Validation sentinels" — VLDT-01..06 definitions

### Schema (the append-only constraint that forces D-02)
- `supabase/migrations/033_economy_map_schema.sql` §5 (lines ~94-110) — `block_body_versions`
  columns; `validator_report JSONB NOT NULL DEFAULT '{}'` is **pinned**
- `supabase/migrations/033_economy_map_schema.sql` §"append-only trigger" (lines ~177-211) — the
  `block_body_versions_append_only()` trigger RAISES on any `validator_report` change in UPDATE →
  sentinels MUST write at INSERT time

### Phase 7 code this phase modifies
- `docker/processor/agentpulse_processor.py` — `synthesize_block` (sentinels insert here, between
  parse and INSERT), `parse_synthesis_output` (remove the WR-02 missing-headings raise per D-01),
  `economy_map_insert_block_body_version` (now carries `validator_report`), `SYNTH_SKELETON_HEADINGS`
  + `SYNTH_MATURITY_ENUM` (sentinel inputs), `fetch_current_block_body` (prior body for length floor)
- `config/economy_map/synth_identity.md` — the six-heading skeleton contract the sentinels validate
  against
- `docker/gato_brain/gato_brain.py` — `handle_map_pending` (extend for flag rendering per D-08)
- `tests/test_07_synthesis.py` — `test_parse_output_raises_on_missing_skeleton` must be swapped
  (D-01a)

### Phase 7 deferred items relevant downstream (NOT this phase)
- `.planning/todos/pending/2026-06-01-phase07-review-followups-wr01-in01-04.md` — reviewed, not
  folded: WR-01 (duplicate-draft UNIQUE index) and IN-04 (Phase 9 must advance `last_synthesized_at`
  from `synthesized_from_through`) are Phase 9/10 concerns, not sentinel work
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`SYNTH_SKELETON_HEADINGS`** (processor): the six-heading list — reused directly by the structure
  sentinel (VLDT-04) and to locate the live-tension section for VLDT-01.
- **`SYNTH_MATURITY_ENUM`** (processor): the 5-value ordered maturity enum — index distance gives the
  maturity-jump delta (VLDT-03).
- **`fetch_current_block_body(current_body_version_id)`** (processor): already used by Phase 7 to
  fetch the prior body for synthesis input — reuse for the length-floor baseline (VLDT-02).
- **`economy_map_insert_block_body_version(payload)`** (processor): the single draft writer — extend
  its payload to include `validator_report` (it already targets `/block_body_versions` with
  `Content-Profile: economy_map` and omits `status`).
- **`handle_map_pending`** (gato_brain): the Phase 6 read-only inbox renderer — extend its per-draft
  formatting for flags (D-08). Read-only-by-construction; render-only change.

### Established Patterns
- **GATE-01 draft-only** (Phase 7): sentinels never touch the published row, `blocks.maturity`, or
  `blocks.current_body_version_id` — they only populate the new draft's `validator_report`.
- **Fail-loud** (project): a sentinel that itself errors must not silently swallow — but per VLDT-05
  it must ALSO never block the draft. Expected resolution: a sentinel computation error is logged
  loudly and recorded in `validator_report` (e.g. a `sentinel_errors` note) so the draft still lands
  with visible evidence the check couldn't run — NOT a silent pass. (Planner to confirm shape.)
- **economy_map access** via direct PostgREST + `Accept-Profile`/`Content-Profile: economy_map`
  (never supabase-py `.in_()`/`.schema()`).

### Integration Points
- Sentinels slot into `synthesize_block` between `parse_synthesis_output` and the draft INSERT.
- `/map-pending` rendering reads each draft's `validator_report` and formats per D-08.
</code_context>

<specifics>
## Specific Ideas

- The `/map-pending` card format is pinned to the D-08 mockup: `⚠ REQUIRES ATTENTION` headline,
  indented per-flag lines with concrete detail (`maturity jump nascent→contested (+2)`, `length 48%
  of prior (floor 60%)`, `tension trivialized`), serious flags first, `✓ clean` for unflagged drafts.
</specifics>

<deferred>
## Deferred Ideas

- **LLM judge for tension trivialization** — a second Sonnet call to catch "present but shallow"
  live-tension that the deterministic heuristic (D-05) misses. Deferred for cost; revisit as a v2
  sentinel upgrade if operator review shows the heuristic is too coarse.

### Reviewed Todos (not folded)
- `2026-06-01-phase07-review-followups-wr01-in01-04.md` — matched on keyword "synthesis" but its
  contents (WR-01 duplicate-draft UNIQUE index; IN-04 Phase 9 watermark contract) are Phase 9/10
  work, not sentinel annotation. Left in pending for those phases.
- The Phase 05 / Phase 06 review-followup todos matched only on the generic word "phase" — unrelated
  to validation sentinels; not folded.

</deferred>

---

*Phase: 8-validation-sentinels*
*Context gathered: 2026-06-01*
