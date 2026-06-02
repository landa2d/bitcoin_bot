# Phase 9: Gated Publishing + Approval Commands - Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the autonomy boundary (the project spine). Two **owner-gated** Telegram commands let the
operator act on the `draft` `block_body_versions` rows that Phase 7 synthesis produces and Phase 8
sentinels annotate:

- **`/map-approve <version_id>`** → runs the existing atomic publish transaction
  (`economy_map.publish_block_version`): flips that draft → `published`, supersedes the prior
  published row, repoints `blocks.current_body_version_id` + `blocks.maturity`, advances
  `last_synthesized_at`, all-or-nothing (GATE-02, CMD-03).
- **`/map-reject <version_id>`** → runs `economy_map.reject_block_version`: sets the draft →
  `superseded`, mutates nothing else; the timeline entries it consumed remain unabsorbed so the next
  synthesis re-reads them (GATE-03, CMD-04). `superseded` is terminal — never deleted (GATE-04).

GATE-01 (synthesis only ever writes `draft`, never `published`) is already TRUE from Phase 7 — this
phase only needs to **verify** it, not implement it.

**In scope:** the two write commands + their owner gate + confirmation/typed-error responses; a
migration amending the publish RPC's watermark semantics (D-01); a GATE-01 verification check.
**Out of scope (other phases):** manual `/map-synth` trigger, `unsorted` reassignment, `live_tension`
editing, forced re-synthesis (all Phase 10); bespoke per-draft approval card UI (the `/map-pending`
list from Phase 6/8 is the approval surface); the WR-01 duplicate-draft UNIQUE index (stays deferred,
see Deferred Ideas).
</domain>

<decisions>
## Implementation Decisions

### Watermark semantics — the IN-04 correctness contract
- **D-01:** **Amend `economy_map.publish_block_version` (new migration 038) to advance
  `last_synthesized_at` from the approved draft's `synthesized_from_through`, NOT `NOW()`.** The
  Phase 2 RPC (migration 033 §9, Step 4) currently sets `last_synthesized_at = NOW()`. Per the IN-04
  follow-up, this double-counts/skips timeline entries created in the window between synthesis and
  approval, because the next cycle's recency filter is `created_at > last_synthesized_at`. Fix: read
  the draft's `synthesized_from_through` (a pinned column, migration 033:101) inside the RPC and set
  `blocks.last_synthesized_at = v_synthesized_from_through`. This only touches `blocks` (a lifecycle
  update) — the `block_body_versions` append-only trigger is not implicated (it guards
  `synthesized_from_through` on that table, which we only READ). Ship as ONE operator-approved
  migration via Supabase MCP `apply_migration` (project ref `zxzaaqfowtqvmsbitqpu`), drift-check,
  scoped redeploy — consistent with the project's structural-over-application + prod-cutover
  discipline.
  - **D-01a (scope fence):** Do NOT fold the WR-01 duplicate-draft UNIQUE index into this migration
    (the operator chose watermark-only). It stays deferred to Phase 10 when manual `/map-synth` makes
    concurrent synthesis plausible. Keep migration 038 focused on the watermark amendment.

### Owner gate (SC5)
- **D-02:** **Gate the two write commands on the existing `access_tier == 'owner'` check** from
  `ensure_user` (the same identity already granted unlimited rate in gato_brain, :54/:288/:316).
  No new env var / config. A non-owner caller gets a typed refusal (see D-05), never the write path.
- **D-02a:** The **read** commands (`/map-status`, `/map-pending`) stay **ungated** as they are today
  (Phase 6 posture) — only the write commands gain the owner gate. Do not retrofit gating onto the
  read commands.

### Re-render trigger (SC2)
- **D-03:** **"Triggers a block-page re-render" is satisfied by the existing Phase 4 60s
  visibility-aware idle poll** (REQ-RENDER-LIVE). `publish_block_version` flips the row to
  `published`; the already-shipped idle poll renders it within ~60s. NO explicit re-render kick is
  built — treat the existing live-update mechanism as the trigger. (Keeps the write path minimal and
  avoids new coupling.)

### Command call mechanism + ergonomics
- **D-04:** The write path calls the **`SECURITY DEFINER` RPCs via PostgREST `POST /rpc/<fn>`** with
  `Content-Profile: economy_map` + service_role auth — NEVER a direct table write and NEVER supabase-py
  `.rpc()`/`.schema()` (consistent with the economy_map access rule). gato_brain currently has only the
  GET helper `_economy_map_get`; a small **RPC-POST helper** is the natural addition (mirror the
  processor's `economy_map_insert_block_body_version` POST style). This is the FIRST and ONLY write
  surface added to gato_brain's otherwise read-only `/map-*` commands — the two gated RPC calls are the
  entire write footprint; no other write verbs.
- **D-04a:** `<version_id>` is a **full UUID** (exactly what `/map-pending` pre-fills as
  `/map-approve <uuid>` / would print for reject). No short-prefix / index-style addressing in v1.
  Malformed/missing arg → typed error (D-05), not a silent no-op.

### Confirmation + typed-error UX (SC5)
- **D-05:** **Rich confirmation + explicit per-case typed errors.**
  - Approve success: `✓ Published <block name> — maturity <old>→<new>; live at <block url> (renders within ~60s)`.
  - Reject success: `✓ Rejected <block> draft (superseded; its timeline entries return to the next synthesis)`.
  - Explicit error cases, each a distinct human message: (a) **not owner** → refusal; (b) **missing/malformed UUID** → usage hint; (c) **RPC raises `version … not found or not in draft status`** (already actioned / concurrent loser / wrong id) → "that draft was already published/rejected or doesn't exist"; (d) **any other failure** → fail-loud `Command failed: <e>` (existing pattern). The RPC's single-winner property (033 Step 1 `WHERE status='draft'` RETURNING-empty) means a concurrent double-approve safely surfaces as case (c), not a double-publish.

### Claude's Discretion
- Exact wording/emoji of the confirmation and error strings (as long as D-05's cases are all covered
  and distinct), and how the block name / URL are resolved for the confirmation (a small lookup by
  `block_slug`).
- Whether `/map-approve` and `/map-reject` are separate handlers or one parametrized helper, and the
  exact name/signature of the new RPC-POST helper — planner's call.
- How GATE-01 is verified (a test asserting synthesis writes only `status='draft'`, and/or an
  inspection note) — the verification approach, not the guarantee, is open.
- The precise SQL form of the migration-038 amendment (variable capture in the RPC) — planner/executor.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` §"Phase 9: Gated Publishing + Approval Commands" — goal + 5 success criteria
- `.planning/REQUIREMENTS.md` — GATE-01..04 (lines ~55-58), CMD-03/CMD-04 (lines ~74-75)

### The atomic transaction this phase wires to (Phase 2 — ALREADY EXISTS)
- `supabase/migrations/033_economy_map_schema.sql` §9 (lines ~256-312) — `publish_block_version(p_version_id uuid)`:
  draft→published flip (single-winner `WHERE status='draft'`), supersede prior, update
  `blocks.current_body_version_id`/`maturity`/`last_synthesized_at`. **D-01 amends Step 4's watermark here.**
- `supabase/migrations/033_economy_map_schema.sql` §10 (lines ~315-345) — `reject_block_version(p_version_id uuid)`:
  draft→superseded, typed RAISE on not-found/not-draft. Used as-is.
- `supabase/migrations/033_economy_map_schema.sql` §8 append-only trigger (lines ~185-211) — confirms
  only lifecycle columns (`status`, `published_at`) may change on `block_body_versions` UPDATE; the
  RPCs respect this. `synthesized_from_through` pinned at line 101 (read source for D-01).

### Command surface this phase extends (Phase 6/8)
- `docker/gato_brain/gato_brain.py` — `handle_map_command` (~1902, add the two write branches),
  `_economy_map_get` (~1585, the GET helper to mirror for a new RPC-POST helper), `handle_map_pending`
  (~1837, prints the `/map-approve <uuid>` lines), `ensure_user`/`access_tier` (owner gate, D-02),
  `/chat` dispatch (~2263, `/map-` routing).

### Phase 7/8 producers of the drafts being approved
- `docker/processor/agentpulse_processor.py` — `synthesize_block` (sets `synthesized_from_through`,
  the value D-01 promotes to the watermark; GATE-01 draft-only writer to verify).

### Deferred follow-up that names the Phase 9 contract
- `.planning/todos/pending/2026-06-01-phase07-review-followups-wr01-in01-04.md` — IN-04 (the watermark
  contract, now D-01) and WR-01 (duplicate-draft UNIQUE index, stays deferred per D-01a).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`economy_map.publish_block_version` / `reject_block_version`** (migration 033): the entire atomic
  publish/reject logic already exists and is service_role-only `SECURITY DEFINER` — Phase 9 calls them,
  does not reimplement. Only the publish RPC's watermark line is amended (D-01).
- **`_economy_map_get`** (gato_brain ~1585): GET helper with `Accept-Profile: economy_map` + service_role
  headers — the template for a new sibling RPC-POST helper (`Content-Profile: economy_map`).
- **`handle_map_command`** (gato_brain ~1902): the dispatcher; today read-only with an "Unknown map
  command" fallthrough — add `/map-approve` and `/map-reject` branches here.
- **`access_tier == 'owner'`** identity (gato_brain ~54/288/316): existing owner concept reused for D-02.
- **`/map-pending`** (gato_brain ~1837): already surfaces full `version_id`s with pre-filled approve
  lines — the operator's approval surface, no new card needed.

### Established Patterns
- **economy_map access** via direct PostgREST + `Accept-Profile`/`Content-Profile: economy_map` only;
  never supabase-py `.in_()`/`.schema()`/`.rpc()`.
- **Read-only-by-construction** (Phase 6): gato_brain's `/map-*` surface was GET-only. Phase 9
  deliberately introduces exactly two gated RPC-POST write verbs (D-04) and nothing more.
- **Fail-loud** command handler: `handle_map_command`'s top-level try/except returns
  `Command failed: <e>` — D-05 layers explicit typed cases in front of this catch-all.
- **Migrations** applied via Supabase MCP `apply_migration` (ref `zxzaaqfowtqvmsbitqpu`); latest is 037,
  so the watermark amendment is **038**; run `scripts/drift-check.sh` before scoped redeploy.

### Integration Points
- New write branches slot into `handle_map_command`; owner gate sits in front of them.
- Migration 038 amends the publish RPC; the publish path then implicitly relies on the Phase 4 idle
  poll for re-render (D-03).
- The approved/rejected drafts are the rows Phase 8's `/map-pending` lists with their `validator_report`
  flags — the operator reads flags there, then approves/rejects by `version_id`.
</code_context>

<specifics>
## Specific Ideas

- Approve confirmation must show the maturity transition (`<old>→<new>`) and the live block URL, so the
  operator sees exactly what changed and where to look. Reject confirmation must state that the
  consumed timeline entries return to the next synthesis (the GATE-03 behavior made visible).
- The concurrent-double-approve case must read as "already actioned," never silently double-publish —
  relies on the RPC's single-winner `WHERE status='draft'` RETURNING-empty property (033 Step 1).
</specifics>

<deferred>
## Deferred Ideas

- **WR-01 duplicate-draft UNIQUE partial index** (`uq_block_body_versions_one_open_draft ... WHERE
  status='draft'`) — deliberately NOT folded into migration 038 (operator chose watermark-only).
  Becomes relevant in **Phase 10** when a manual `/map-synth` trigger makes concurrent synthesis
  plausible; ship it then on its own approved migration. Tracked in
  `.planning/todos/pending/2026-06-01-phase07-review-followups-wr01-in01-04.md`.
- **Manual `/map-synth`, `unsorted` reassignment, `live_tension` editing, forced re-synthesis** — all
  **Phase 10** (Operator Write Commands).
- **Bespoke per-draft approval card UI** — out of scope; `/map-pending` is the approval surface.

### Reviewed Todos (not folded)
- `2026-06-01-phase07-review-followups-wr01-in01-04.md` — IN-04 **folded** as D-01 (the watermark
  contract). WR-01 reviewed and **kept deferred** per D-01a. IN-01/IN-02/IN-03 are synthesis-input /
  read-helper quality notes, unrelated to gated publishing — left in pending.

---

*Phase: 9-gated-publishing-approval-commands*
*Context gathered: 2026-06-02*
