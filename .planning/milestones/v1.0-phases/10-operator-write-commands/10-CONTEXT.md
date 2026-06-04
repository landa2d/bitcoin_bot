# Phase 10: Operator Write Commands - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Complete the `/map-*` control surface with the operator's four editorial-framing levers — all
**owner-gated** Telegram commands routed through the same Gato → Gato Brain → owner-gate → economy_map
pattern Phase 9 established for `/map-approve`/`/map-reject`:

- **`/map-assign <entry_id> <block_slug>`** — move an `unsorted` timeline entry to a named block,
  implemented as a NEW entry referencing the prior (never an UPDATE of content); the original leaves
  the `/map-pending` unsorted backlog immediately (CMD-05 / REQ-CMD-ASSIGN).
- **`/map-entry <block_slug> <text>`** — manual timeline drop for things the pipeline missed; creates a
  new append-only `timeline_entries` row with `what_shifted` + `why_it_mattered` populated (CMD-06 /
  REQ-CMD-ENTRY).
- **`/map-synth <block_slug>`** — force re-synthesis NOW for one block, ignoring the `N`/`T` eligibility
  thresholds; a new `draft` row appears shortly after (CMD-07 / REQ-CMD-SYNTH).
- **`/map-tension <block_slug> <text>`** — update a block's `live_tension` (the editorial framing
  reserved for humans); visible on the next render of the block page (CMD-08 / REQ-CMD-TENSION).

**In scope:** the four write commands + their owner gate + confirmation/typed-error responses; the
cross-service synth-request mechanism (new table + processor drain poller); the `/map-assign`
reassignment migration (mutable lifecycle pointer + RPC); the `/map-entry` and `/map-tension` write
paths (RPCs); the WR-01 duplicate-draft unique index (its own migration) + benign-skip handling in the
processor's synthesize_block.

**Out of scope (other phases / done):** `/map-approve`/`/map-reject` (Phase 9, shipped); bespoke
per-command card UIs (`/map-pending` is the surface); any new autonomy that publishes without
`/map-approve` (the spine — intake autonomous, publish gated, stays intact). No new capability beyond
the four roadmap'd commands.
</domain>

<decisions>
## Implementation Decisions

### `/map-synth` cross-service trigger (the central architecture decision)
- **D-01:** **DB request-queue + short processor poll.** The processor is a pure `schedule` loop with
  NO HTTP surface (healthcheck is `pgrep`), so gato_brain cannot call synthesis directly. gato_brain
  INSERTs a synth-request row into a NEW `economy_map` table; the processor gains a short-interval
  `schedule` job (~30–60s, planner picks the exact cadence — reuse an existing tick if natural) that
  drains pending requests and runs `synthesize_block` **bypassing `is_block_eligible`** (the N/T
  thresholds). Fits the standing architecture constraint (single server, no message broker, DB-polling
  + HTTP only) and adds no new port. Rejected: an HTTP endpoint on the processor (new surface/port + a
  30–60s Sonnet call as a synchronous Telegram wait is timeout-fragile) and replicating synthesis in
  gato_brain (DRY + `synth_identity.md` location).
- **D-02:** **Respect the one-open-draft-per-block invariant — refuse, don't force.** If the target
  block already has an open `draft` awaiting approval, `/map-synth` returns a pointer
  ("this block already has a pending draft — approve or reject it first via `/map-pending`") and does
  NOT enqueue. "Ignoring N and T" bypasses ONLY the eligibility thresholds, never the open-draft guard
  (D-03 from Phase 7). The WR-01 unique index (D-07) is the structural backstop for the check-then-act
  race. Rejected: force a second draft (violates the invariant, would hit the unique index); auto-supersede
  the existing draft (silently discards an unreviewed draft — against the human-gated spine).
- **D-03:** **Request-row status lifecycle + fail-loud, synchronous validate-and-ack.** The request row
  carries a status (`pending` → `processing` → `done` with resulting `version_id` / `failed` with
  error). gato_brain validates the slug (seven-block allowlist) and the open-draft precondition
  **synchronously** before enqueuing, then returns an ack ("Queued — draft appears within ~Ns; check
  `/map-pending`"). The processor marks `done`/`failed`; a failed forced-synth must be **queryable**,
  never a silent drop (consistent with the `pipeline_runs` fail-loud pattern and the project's fail-loud
  governance value). Rejected: fire-and-forget (a failed synth vanishes silently).

### `/map-assign` append-only reassignment
- **D-04:** **Mutable lifecycle pointer on the original + reference link on the copy, set atomically by
  an RPC.** `timeline_entries` is currently 100% append-only (every content column trigger-guarded).
  Add a nullable **mutable** column `reassigned_to_entry_id` (and a `reassigned_from_entry_id` on the
  copy) to `timeline_entries` and exempt ONLY those lifecycle columns from the append-only trigger —
  the SAME precedent as `block_body_versions`' mutable `status`/`published_at` lifecycle columns
  (migration 033 §8). Content columns stay fully append-only. A `SECURITY DEFINER` RPC (e.g.
  `reassign_timeline_entry(p_entry_id, p_block_slug)`) atomically (a) INSERTs the new row under the
  target slug carrying `reassigned_from_entry_id → prior` and (b) sets `reassigned_to_entry_id` on the
  original. Unsorted reads (`get_unsorted_entries`/`get_unsorted_count` in gato_brain) add
  `reassigned_to_entry_id IS NULL` so the reassigned original leaves the `/map-pending` backlog
  immediately (SC1). Rejected: pure append-only via NOT-EXISTS view/RPC (PostgREST can't express the
  anti-join cleanly; every unsorted read pays a subquery).
- **D-05:** **The reassigned copy preserves provenance; operator assignment is authoritative.** Copy the
  original's `event_date` (the event happened when it happened — NOT today), `what_shifted`,
  `why_it_mattered`, `source_url`, `source_edition_id` verbatim (keeps REQ-INTAKE-TRACE traceability).
  `tag_confidence` is set to reflect operator authority (NULL or 1.0 — planner's call; it is not a
  classifier score). Validation: target `block_slug` must be in the seven-block allowlist (reject
  `unsorted`/unknown); reject if the entry is not currently `unsorted` (already filed / already
  reassigned) with a typed error.

### `/map-entry` argument ergonomics
- **D-06:** **Stateless single-shot with a delimiter.** `/map-entry <slug> <what_shifted> | <why_it_mattered>`
  — split on a delimiter (e.g. ` | `). BOTH fields are required (`NOT NULL` in schema); if the delimiter
  or second part is missing, return a usage hint showing the format — this satisfies SC2's "prompts for"
  without introducing session state into a `/map-*` surface that is otherwise entirely stateless.
  `event_date` defaults to **today**; `source_url`/`source_edition_id` = NULL and `tag_confidence` = NULL
  (manual drop, no classifier). Slug validated against the seven-block allowlist. Rejected: a
  conversational follow-up prompt (adds `conversation_state` machinery to the write path; statefully
  fragile).

### `/map-tension` write mechanism
- **D-08:** **A `SECURITY DEFINER` RPC** (e.g. `set_block_live_tension(p_slug, p_text)`), consistent with
  the Phase 9 locked write-path and the standing structural-over-application enforcement preference.
  `blocks.live_tension` is `TEXT NOT NULL` and freely mutable (the `blocks` table has no append-only
  trigger; migration 033:73 already annotates it "mutated via /map-tension"), so a direct PostgREST
  PATCH would also work — but the RPC keeps every economy_map write behind a `SECURITY DEFINER` function
  and the allowlist-guarded POST helper. Low-gray; planner may confirm RPC vs PATCH but RPC is the default.

### WR-01 duplicate-draft unique index (now in scope)
- **D-07:** **Ship the partial unique index as its OWN operator-approved migration**, separate from the
  synth-request / reassign / tension schema changes (per the WR-01 todo's "own approved migration track"
  + the scoped-approved-deploys / prod-cutover discipline). SQL:
  `CREATE UNIQUE INDEX IF NOT EXISTS uq_block_body_versions_one_open_draft ON economy_map.block_body_versions (block_slug) WHERE status = 'draft';`
  The processor's `synthesize_block` keeps `block_has_open_draft` as the cheap fast-path and catches the
  resulting `23505` unique-violation on INSERT as a **logged benign skip** ("race lost"), NEVER a
  fail-loud abort. This is the structural backstop the new `/map-synth` + scheduled-poller concurrency
  now requires.

### Write-path plumbing (carried from Phase 9, applies to all four commands)
- **D-09:** All four commands are **owner-gated on `access_tier == 'owner'`, checked FIRST** before any
  write (Phase 9 D-02). Writes go through a `SECURITY DEFINER` RPC via PostgREST `POST /rpc/<fn>` with
  `Content-Profile: economy_map`, allowlist-guarded `fn`, parameterized JSON body, fail-loud on non-2xx
  (Phase 9 D-04) — never a direct table write, never supabase-py `.rpc()`/`.schema()`/`.in_()`. The
  existing `_economy_map_rpc(fn, version_id)` helper is hardcoded to `{"p_version_id": ...}`; it must be
  **generalized to accept an arbitrary parameter dict** while keeping the allowlist (add the new RPC
  names: `reassign_timeline_entry`, the `/map-entry` insert RPC, `set_block_live_tension`, and the
  synth-request enqueue if done via RPC).
- **D-10:** Typed, distinct error UX per the Phase 9 D-05 pattern: not-owner refusal / missing-or-malformed
  arg usage hint / unknown-or-`unsorted` slug / already-actioned or precondition-failed / generic
  fail-loud `Command failed: <e>`. New command branches slot into `handle_map_command`'s dispatch
  (gato_brain ~2127) and the "Available:" fallthrough list is extended.

### Claude's Discretion
- Exact synth-poll cadence and the synth-request table's column set (within D-01/D-03's lifecycle +
  fail-loud + structural-enforcement constraints).
- `tag_confidence` value for the reassigned copy (NULL vs 1.0) and for `/map-entry` (NULL assumed).
- Exact delimiter for `/map-entry` and the precise usage-hint wording.
- `/map-tension` RPC vs direct PATCH (RPC is the default per D-08).
- Whether the four new commands are separate handlers or parametrized; the new RPC names/signatures;
  the generalized `_economy_map_rpc` signature; migration grouping of the non-WR-01 schema changes
  (one vs a few migrations) — planner's call.
- All confirmation/emoji wording (must cover the D-10 cases distinctly).

### Folded Todos
- **WR-01** (`.planning/todos/pending/2026-06-01-phase07-review-followups-wr01-in01-04.md`) — the
  duplicate-draft unique index, deferred from Phase 7→9→**this phase** because `/map-synth` makes
  concurrent synthesis plausible. Folded as **D-07**. (IN-01..04 from the same todo are synthesis-input /
  read-helper quality notes, unrelated to the write commands — left in pending.)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 10: Operator Write Commands" (lines ~275-288) — goal + 5 success criteria
- `.planning/REQUIREMENTS.md` / `.planning/PROJECT.md` — REQ-CMD-ASSIGN, REQ-CMD-ENTRY, REQ-CMD-SYNTH,
  REQ-CMD-TENSION (CMD-05..08)

### The write-command pattern this phase extends (Phase 9 — the template)
- `.planning/phases/09-gated-publishing-approval-commands/09-CONTEXT.md` — D-02 (owner gate), D-04 (RPC
  via PostgREST POST), D-05 (typed-error UX). All four Phase 10 commands follow this pattern.
- `docker/gato_brain/gato_brain.py`:
  - `_economy_map_rpc` (~1615) — the allowlist-guarded RPC-POST helper to **generalize** for arbitrary
    params (D-09); `_ECONOMY_MAP_RPC_ALLOWLIST` (~1612) gets the new RPC names.
  - `_economy_map_get` (~1583) — read helper (Accept-Profile) for slug/open-draft validation.
  - `handle_map_command` (~2112) dispatch + "Available:" fallthrough (~2137) — add four branches.
  - `handle_map_approve`/`handle_map_reject` (~2023/~2075) + `_validate_version_id` (~2000) — owner-gate +
    arg-validation + already-actioned handling to mirror.
  - `get_unsorted_entries` (~1770) / `get_unsorted_count` (~1793) — add `reassigned_to_entry_id IS NULL`
    (D-04).
  - `ensure_user`/`access_tier` (~191/~285) — the owner concept reused for the gate.

### The schema this phase amends (Phase 2 — migration 033)
- `supabase/migrations/033_economy_map_schema.sql`:
  - `economy_map.blocks` (~65-73) — `live_tension TEXT NOT NULL`, annotated "mutated via /map-tension";
    `blocks` has NO append-only trigger (D-08).
  - `economy_map.timeline_entries` (~148-161) — columns + append-only trigger
    `timeline_entries_append_only()` (~213-253). D-04 adds mutable `reassigned_to_entry_id` /
    `reassigned_from_entry_id` and exempts ONLY them.
  - `block_body_versions` partial draft index (~107-110, non-unique) — D-07 adds the UNIQUE partial index;
    `status`/`published_at` lifecycle-column precedent (~88, §8) cited for D-04's mutable-column pattern.

### The synthesis path `/map-synth` drives (Phase 7)
- `docker/processor/agentpulse_processor.py`:
  - `synthesize_block` (~3587) + `is_block_eligible` (~3217) — drained-request path calls
    `synthesize_block` bypassing eligibility (D-01); `block_has_open_draft` fast-path + 23505 benign-skip
    (D-02/D-07).
  - `synthesize_blocks_poller` (~3666) — the autonomous cycle (the second racer for WR-01); the new
    drain poller mirrors its fail-loud structure.
  - `economy_map_insert_block_body_version` (~3174) — purpose-scoped draft INSERT (the 23505 site).
  - `economy_map_insert_timeline_entry` (~573) — append-only timeline INSERT helper (template for
    `/map-entry` / `/map-assign` writes if done processor-side; gato_brain writes via RPC per D-09).
- `docker/processor/agentpulse_processor.py` `synth_identity` / `load_synth_identity` — the voice file
  the drained synth must load (fail-loud if None).

### Cross-service forwarding (already handled — DO NOT re-touch)
- `docker/gato/inject-gato-brain.mjs` (~106-149) — `isMapCommand = /^\/map-/i` is a **wildcard**; the four
  new commands forward to gato_brain automatically. No allowlist change (the Phase 9 lesson is baked in).

### Standing constraints / memory
- `.planning/PROJECT.md` §Constraints — economy_map via direct PostgREST + `Accept/Content-Profile`
  header only (no supabase-py `.in_()`); LLM via `llm-proxy:8200`; single-server, no broker; append-only
  + draft-then-approve spine.
- WR-01 todo: `.planning/todos/pending/2026-06-01-phase07-review-followups-wr01-in01-04.md`.
- Deploy discipline: migrations via Supabase MCP `apply_migration` (ref `zxzaaqfowtqvmsbitqpu`); latest is
  **039**, so Phase 10 migrations start at **040**; run `scripts/drift-check.sh`, scoped per-service
  rebuild, operator-approved.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`_economy_map_rpc` + `_ECONOMY_MAP_RPC_ALLOWLIST`** (gato_brain ~1612/1615): the exact write helper
  to generalize for the new RPCs (D-09) — keep the allowlist + parameterized JSON + fail-loud non-2xx.
- **`handle_map_approve` / `_validate_version_id`** (gato_brain ~2023/~2000): owner-gate-first +
  strict-arg-validate + already-actioned typed handling — the template for all four new handlers.
- **`get_unsorted_entries` / `get_unsorted_count`** (gato_brain ~1770/~1793): the unsorted backlog reads
  that gain the `reassigned_to_entry_id IS NULL` filter so reassignment is visible immediately.
- **`synthesize_block` / `synthesize_blocks_poller` / `economy_map_insert_block_body_version`** (processor
  ~3587/~3666/~3174): the synthesis path the drain poller reuses; the 23505 benign-skip site.
- **`economy_map_insert_timeline_entry`** (processor ~573): append-only timeline INSERT helper.
- **migration 033 §8 lifecycle-column precedent** (`block_body_versions.status`/`published_at`): the
  pattern D-04's mutable `reassigned_*` columns follow.

### Established Patterns
- **economy_map access** via direct PostgREST + `Accept-Profile`/`Content-Profile: economy_map` only;
  `SECURITY DEFINER` RPCs for writes; never supabase-py `.in_()`/`.schema()`/`.rpc()`.
- **Owner-gated, read-only-by-construction `/map-*` surface** (Phase 6/9): writes are explicit, gated,
  allowlisted RPC verbs and nothing more.
- **Fail-loud governance**: a failed write/synth must surface (logged + queryable run/request row),
  never degrade to a silent no-op (D-03; the "wallet bug" lesson).
- **Structural-over-application enforcement**: triggers/RPC/unique-index over app-layer checks (D-04,
  D-07, D-08).
- **Scoped, approved, drift-checked migrations + per-service rebuilds** (no blind full deploy).

### Integration Points
- Four new branches in `handle_map_command` (gato_brain), each owner-gated, calling a generalized
  `_economy_map_rpc`.
- New `economy_map` synth-request table + a new short-interval `schedule` job in the processor that
  drains it (bypassing eligibility) and updates request status.
- Migration(s) 040+: synth-request table; `timeline_entries.reassigned_*` columns + trigger exemption +
  `reassign_timeline_entry` RPC; `/map-entry` insert RPC; `set_block_live_tension` RPC; and a SEPARATE
  migration for the WR-01 unique index.
- The published/re-synthesized blocks rely on the existing Phase 4 60s idle poll for re-render (no new
  render kick) — same as Phase 9 D-03; `/map-tension` is visible on the next block-page render.
</code_context>

<specifics>
## Specific Ideas

- "Ignoring N and T" means ONLY the eligibility thresholds — the one-open-draft invariant and the
  human-approval gate stay intact (D-02). The operator forcing a synth never bypasses review.
- A reassignment is a *filing* action, not a new event: the copy keeps the original `event_date` and
  source provenance so the timeline and REQ-INTAKE-TRACE stay honest (D-05).
- A failed forced-synth must be as visible as a failed autonomous cycle — queryable, not a silent drop
  (D-03), mirroring the `pipeline_runs` fail-loud pattern.
</specifics>

<deferred>
## Deferred Ideas

- **Bespoke per-command card UIs** — out of scope; `/map-pending` + `/map-status` remain the surfaces.
- **Per-block synthesis threshold tuning** — still a v2 PROJECT.md out-of-scope item; `/map-synth` is the
  manual escape hatch, not per-block config.
- **A general HTTP/control surface on the processor** — explicitly rejected for `/map-synth` (D-01);
  revisit only if a future need can't be met by DB-polling.

### Reviewed Todos (not folded)
- `2026-06-01-phase07-review-followups-wr01-in01-04.md` — **WR-01 folded** as D-07. **IN-01/IN-02/IN-03/IN-04**
  reviewed and left in pending: synthesis-input token-budget and read-helper quality notes, unrelated to
  the operator write commands (IN-04's watermark contract was already resolved as Phase 9 D-01).

</deferred>

---

*Phase: 10-operator-write-commands*
*Context gathered: 2026-06-03*
