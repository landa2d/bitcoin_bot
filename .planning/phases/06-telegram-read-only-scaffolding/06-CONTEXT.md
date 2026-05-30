# Phase 6: Telegram Read-Only Scaffolding - Context

**Gathered:** 2026-05-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Two **read-only** Telegram commands that let the operator see the state of the `economy_map`
before any write commands exist:

- **`/map-status`** (CMD-01) — a single Telegram message listing all seven blocks with: tier,
  maturity pill, count of *unabsorbed* timeline entries, and count of *pending drafts*.
- **`/map-pending`** (CMD-02) — a Telegram message listing every draft awaiting approval (with its
  `version_id`) and every `unsorted` entry awaiting assignment (with its `entry_id`).

Both route Gato → Gato Brain in the **same pattern as the existing `/x-*` family**
(`handle_x_command()` dispatch) — no parallel infrastructure. **Neither command may mutate
`economy_map`** (read-only, verified by code review — ROADMAP criterion 4). Covers CMD-01, CMD-02.

**Already delivered (do NOT rebuild):**
- `economy_map.blocks` (migration 033): `slug`, `tier`, `sort_order`, `maturity` enum, `subtitle`,
  `accent`, `current_body_version_id`, `last_synthesized_at` — all seven seeded (Phase 2).
- `economy_map.block_body_versions` (033): `status IN ('draft','published','superseded')`, with a
  **partial index on `status='draft'`** explicitly built "for /map-pending queries" (033:110).
- `economy_map.timeline_entries` (033): `block_slug` (incl. `'unsorted'`), `event_date`,
  `tag_confidence`, `created_at`.
- The web hub/status renderer (`docker/web/site/app.js`, Phase 4) — the maturity/tier rendering
  reference to mirror in Python (NOT shared code; the DB `blocks.maturity` column is the one source
  of truth per RNDR-04).
- The processor's `economy_map` PostgREST read helpers (Accept-Profile pattern) — the proven shape
  to **port into gato_brain** (gato_brain currently uses supabase-py for the public schema only).

**Out of scope (later phases):** the actual write commands — `/map-approve`, `/map-reject`
(Phase 9, GATE-02/03, CMD-03/04); `/map-assign`, `/map-entry`, `/map-synth`, `/map-tension`
(Phase 10, CMD-05..08). Synthesis that produces drafts (Phase 7). Any renderer change (Phase 4,
shipped). A DB-level read-only role / RLS hardening (flagged to Phase 9 — see D-09).
</domain>

<decisions>
## Implementation Decisions

### `/map-status` message layout (READ surface)
- **D-01: Tier-grouped.** Three headers — **SUBSTRATE / BEHAVIOR / FRAME** — with the blocks listed
  under each (mirrors the hub page's grouping and the tier accents). Within a tier, order by
  `sort_order`. Render the body inside a **monospace block** (Telegram markdown code fence) so the
  block-name / pill / count columns align. Operator-approved preview:
  ```
  SUBSTRATE
    compute-infra        ◉◉○○○ emerging   ·3 new ·1 draft
    data-rails           ◉○○○○ nascent    ·0 new
    payments-settlement  ◉◉◉○○ contested  ·5 new ·2 draft
  ```
- **D-02: Maturity pill = 5-segment fill glyphs + word label**, e.g. `◉◉○○○ emerging`. Filled =
  `◉`, empty = `○`; number filled = the stage index of the maturity in the canonical order
  `nascent(1) → emerging(2) → contested(3) → consolidating(4) → mature(5)`. This mirrors the web
  pill's `MATURITY_STAGE` map and 5-segment markup. *(Researcher: confirm `◉`/`○` render cleanly in
  Telegram across desktop/mobile; if not, pick equivalent monospace-safe glyphs and note the
  substitution — the **5-segment + word-label** contract is what's locked, not the exact glyphs.)*
- **D-03: Per-block counts** = `·N new` (unabsorbed timeline entries, see D-05) and `·N draft`
  (pending drafts, see D-06). Omit the `·draft` segment when zero (as in the `data-rails` preview);
  always show `·N new` even at zero.

### Count semantics
- **D-04: Pending drafts** for a block = `COUNT(block_body_versions WHERE block_slug=<slug> AND
  status='draft')`. Uses the partial draft index already built for this query (033:110).
- **D-05: "Unabsorbed" timeline entries** for a block = entries **newer than the block's
  `last_synthesized_at`**; when `last_synthesized_at IS NULL` (never synthesized) → **all** the
  block's entries count. This is exactly "what the next synthesis will absorb" and matches the
  Phase 7 trigger semantics (SYNT-01 counts new entries since `last_synthesized_at`). *(Researcher:
  confirm whether the comparison column should be `created_at` or `event_date` — default
  `created_at` since absorption is about ingestion time, but reconcile with how Phase 7 SYNT-01/03
  will window entries so /map-status and the synthesis trigger agree.)*

### `unsorted` surfacing
- **D-06: `/map-status` shows the seven real blocks only, plus a compact footer line**
  `unsorted: N awaiting` (N = `COUNT(timeline_entries WHERE block_slug='unsorted')`). Surfacing the
  backlog count loudly in status fits the project's fail-loud / "silence is the enemy" ethos. The
  **full per-entry unsorted list lives in `/map-pending`** (criterion 2). *(Resolved from a "you
  decide" — operator approved adding the status footer if it reads naturally.)*

### `/map-pending` layout + identifiers
- **D-07: Full raw UUIDs, stateless.** Show the real `block_body_versions.id` (as `version:`) and
  `timeline_entries.id` (as `entry:`) verbatim — no ephemeral short-index layer. Rationale: the
  Phase 9/10 write commands (`/map-approve <version_id>`, `/map-assign <entry_id> <slug>`) consume
  the exact value with no translation, and an ephemeral per-listing index (like `/x-*` `daily_index`)
  introduces mutable state that can go stale between listing and acting — the silent-mismatch class
  the operator designs against. Operator-approved preview:
  ```
  DRAFTS AWAITING APPROVAL
   · payments-settlement
     version: 3f9a2c10-…  →  /map-approve 3f9a2c10-…

  UNSORTED AWAITING ASSIGNMENT
   · 'Foo raised $20M'  conf:0.41
     entry: a17bc930-…   →  /map-assign a17bc930-… <slug>
  ```
- **D-08: Pre-fill the intended write command** next to each identifier (a copy-paste line). The
  commands shown (`/map-approve`, `/map-assign`) do not exist until Phase 9/10. *(Planner's
  discretion: either show them plainly as the forward contract, or annotate "(available soon)". Keep
  it lightweight — do not build the write commands here.)*
- **D-08a: Empty states are explicit, not silent** — when nothing is pending, `/map-pending` says so
  in words (e.g. "Nothing awaiting approval. Nothing awaiting assignment."). Fail-loud ethos.

### Read-only enforcement (criterion 4)
- **D-09: GET-only read-only wrapper this phase; DB-level role hardening flagged to Phase 9.**
  A pure anon-key path is **insufficient** — the Phase 2 anon RLS policy **hides `'unsorted'`**, but
  `/map-pending` must read it. A dedicated read-only DB role (grants + an RLS policy that *can* see
  `unsorted`) is net-new migration work; per the operator's "you decide" fallback, defer it.
  - **This phase:** reuse the proven `service_role` + `Accept-Profile: economy_map` PostgREST path
    (port the processor's read-helper shape into gato_brain), but encapsulate all `economy_map`
    access behind a **read-only client object that exposes only GET methods** (no
    INSERT/UPDATE/DELETE methods exist on it) — a structural *code-level* boundary, stronger than
    bare verb-convention — and add a **code-review gate** confirming zero write verbs in the
    `/map-*` path (criterion 4 evidence).
  - **Flagged to Phase 9** (where writes are introduced and a privileged path is needed anyway):
    introduce a DB-level read-only role / RLS so the read path *structurally cannot* mutate at the
    database layer, and resolve the "anon hides `unsorted`" gap there.
  *(This honors "structural over application enforcement" as far as is possible without a migration
  this phase, while keeping `service_role` out of any write code path in the read commands. See
  memory `feedback-structural-over-application-enforcement` — service_role is the historical failure
  actor; the wrapper keeps it read-only by construction.)*

### Dispatch / routing
- **D-10: Route via the `handle_x_command()` pattern** in `gato_brain.py` — add `/map-*` dispatch in
  the same place `/x-*` and `/code*` are handled (before the intent router), so no parallel
  infrastructure is created (ROADMAP criterion 3). *(Planner: decide whether to add a sibling
  `handle_map_command()` dispatcher mirroring `handle_x_command()`, or extend the existing
  command-prefix branch — mirror the `/x-*` structure either way.)*

### Claude's Discretion
- Exact Telegram message formatting details within the locked contracts (whitespace, header glyphs,
  the 4000-char split behavior already standard in gato_brain — both messages should fit one
  message, but reuse the existing split helper as a safety net).
- Whether `economy_map` reads in gato_brain are issued with the sync `httpx.Client` or async
  `httpx.AsyncClient` — match the surrounding handler's sync/async style (`handle_x_command` is
  sync; mirror it).
- Whether to fetch all four data sets (blocks, draft counts, unabsorbed counts, unsorted count) in
  separate PostgREST GETs or a combined query — optimize for clarity; this is low-volume (7 blocks).
- Glyph substitution for the maturity pill if `◉`/`○` don't render cleanly (D-02).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Schema (the locked foundation — read first)
- `supabase/migrations/033_economy_map_schema.sql` — `economy_map.blocks` columns (`slug`, `tier`,
  `sort_order`, `maturity` enum + canonical order, `subtitle`, `accent`, `current_body_version_id`,
  `last_synthesized_at`); `block_body_versions` (`status` lifecycle + the partial `status='draft'`
  index at :110 built for /map-pending); `timeline_entries` (`block_slug` incl. `'unsorted'`,
  `event_date`, `created_at`, `tag_confidence`); the anon RLS policy that **hides `'unsorted'`**
  (the reason /map-pending needs the service_role read path — D-09).
- `.planning/phases/02-economy-map-schema-seven-block-seed/02-CONTEXT.md` — Phase 2 locked schema +
  seed decisions (tiers, sort_order, maturity enum, `unsorted` validity).

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — CMD-01, CMD-02 (and the forward contract for CMD-03/04 Phase 9,
  CMD-05 Phase 10 that consume the identifiers /map-pending surfaces).
- `.planning/ROADMAP.md` § "Phase 6: Telegram Read-Only Scaffolding" — goal + 4 success criteria
  (incl. criterion 3 "same pattern as `/x-*`" and criterion 4 "read-only verified by code review").

### Dispatch + Telegram surface (gato_brain — where the commands live)
- `docker/gato_brain/gato_brain.py` — `handle_x_command()` (≈:1488) dispatch pattern to mirror;
  command routing in the request handler (`handle_x_command` called ≈:1857, before
  `code_commands` ≈:1868 and `intent_router.route` ≈:1924); existing `supabase` client +
  `httpx` usage; the 4000-char Telegram split + Markdown-then-plain-text fallback convention.

### Read mechanism (economy_map via PostgREST — mandatory pattern)
- `docker/processor/agentpulse_processor.py` — the `economy_map` PostgREST **read** helpers to port
  the shape of: `economy_map_edition_already_emitted` (≈:600), `economy_map_emitted_event_keys`
  (≈:629), `_fetch_economy_map_block_slugs` (≈:3043) — all use `Accept-Profile: economy_map` GET and
  raise on non-2xx (fail-loud read). (The *write* helper `economy_map_insert_timeline_entry` :573 is
  the anti-example: the /map-* wrapper must expose NO such method.)
- `.planning/PROJECT.md` § Constraints — `economy_map` access via direct PostgREST with
  `Accept-Profile: economy_map`; NEVER supabase-py `.in_()`/`.schema()` (silent failure).

### Maturity/tier rendering reference (one source of truth = the DB column)
- `docker/web/site/app.js` (Phase 4) — `renderHub()` / `renderMaturityPill()` / `tierSection()` and
  the `MATURITY_STAGE` map + 5-segment pill markup to mirror in Python text form. RNDR-04: hub,
  status, and these commands all read maturity from `blocks.maturity` (no recomputation).
- `.planning/phases/04-hub-block-and-status-renderer/04-02-SUMMARY.md` — the renderer's tier grouping
  + maturity-stage mapping details.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `handle_x_command()` (gato_brain ≈:1488): the command-dispatch + per-handler-returns-string +
  Telegram-split pattern to clone for `/map-*`.
- Processor `economy_map` GET helpers (Accept-Profile, raise-on-non-2xx): the read shape to port
  into gato_brain (as a GET-only wrapper, D-09).
- `block_body_versions` partial `status='draft'` index (033:110): purpose-built for the /map-pending
  draft query.
- Web renderer `MATURITY_STAGE` map + 5-segment pill (app.js): the maturity→stage mapping to mirror
  in Python for the text pill.

### Established Patterns
- `economy_map` reads = direct PostgREST + `Accept-Profile: economy_map` GET (supabase-py
  `.schema()`/`.in_()` silently fail — Phase 2/5 lock).
- Telegram handlers return a string; the caller splits at 4000 chars, Markdown first then plain-text
  fallback.
- gato_brain holds `service_role` (bypasses RLS) — must be kept out of any write path; the read-only
  wrapper enforces this by construction (D-09).

### Integration Points
- Inbound: Gato → Gato Brain HTTP, dispatched in `gato_brain.py` alongside `/x-*` (D-10).
- Read side: GET `economy_map.blocks`, `block_body_versions` (draft counts), `timeline_entries`
  (unabsorbed counts + unsorted list) via PostgREST.
- Write side: **none** — this phase is read-only (criterion 4).
</code_context>

<specifics>
## Specific Ideas

- `/map-status` operator-approved layout (D-01): tier headers, monospace columns,
  `◉◉○○○ emerging  ·N new ·N draft` per block, `unsorted: N awaiting` footer.
- `/map-pending` operator-approved layout (D-07): `DRAFTS AWAITING APPROVAL` (version UUID +
  `/map-approve` line) and `UNSORTED AWAITING ASSIGNMENT` (entry UUID + `conf:` + `/map-assign`
  line); explicit empty states.
- Maturity canonical order (for stage fill): `nascent → emerging → contested → consolidating →
  mature` (matches migration 033 enum + web `MATURITY_STAGE`).
</specifics>

<deferred>
## Deferred Ideas

- **DB-level read-only role / RLS for the read path** (structural mutation-impossibility at the
  database layer) + resolving the "anon RLS hides `unsorted`" gap — **Phase 9** (writes introduced
  there; a privileged path is needed anyway). Tracked via D-09.
- The actual write commands `/map-approve`, `/map-reject` (Phase 9) and `/map-assign`, `/map-entry`,
  `/map-synth`, `/map-tension` (Phase 10) — this phase only surfaces the identifiers they consume.
- Per-block / richer status detail (e.g. last-synthesized timestamps, drill-down) — not in CMD-01/02
  scope; revisit if the operator wants it after using the basic surfaces.

*Discussion stayed within phase scope; no scope creep surfaced. None of the 5 pending todos match
this phase's scope (analyst bug, governance, payments, Phase-05 intake follow-ups, research perms) —
not folded.*
</deferred>

---

*Phase: 06-telegram-read-only-scaffolding*
*Context gathered: 2026-05-30*
