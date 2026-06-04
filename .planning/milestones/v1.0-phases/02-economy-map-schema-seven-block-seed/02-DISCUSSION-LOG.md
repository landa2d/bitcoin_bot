# Phase 2: `economy_map` Schema + Seven-Block Seed - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 02-economy-map-schema-seven-block-seed
**Areas discussed:** RLS posture, Append-only enforcement, Atomic publish-transaction interface, Block seed source

---

## RLS posture for `economy_map`

| Option | Description | Selected |
|--------|-------------|----------|
| Published-only — mirror migration 006 | Anon SELECT blocks (all), timeline_entries (all incl. unsorted), block_body_versions WHERE status='published'. service_role bypass. | ✓ (with refinement) |
| Read-all in schema | Anon SELECT on all three tables. Simpler RLS; drafts publicly visible. | |
| No anon access — SPA reads through `public`-schema filtered views | REVOKE all on `economy_map` from anon; create `public.map_blocks` / `public.map_published_bodies` views. SPA queries those; Accept-Profile becomes service-role-only. | |

**User's choice:** Published-only, with a refinement: also exclude `unsorted` entries from anon-readable timeline (`USING (block_slug != 'unsorted')`). No filtered-view option — SPA goes through `Accept-Profile: economy_map` directly.

**Notes:** Rationale was *"publish gate structurally enforced, not application-enforced"* — RLS is the structural guarantee that a draft never reaches the browser even on application bugs. The `unsorted` exclusion is consistent with the same principle: low-confidence entries shouldn't surface before operator triage.

---

## Append-only enforcement mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Trigger that raises exception | `BEFORE UPDATE` + `BEFORE DELETE` triggers comparing OLD vs NEW on pinned columns; raises typed exception. Binds service_role too. | ✓ |
| Column-level GRANT revoke | `REVOKE UPDATE (body_md, ...) FROM anon, authenticated;` — service_role still has UPDATE unless explicitly revoked. | |
| Hybrid — trigger + per-column GRANT | Belt-and-braces: trigger for agents + revoke for browser roles. Two enforcement layers, same source of truth. | |

**User's choice:** Trigger only — NOT RLS, NOT hybrid.

**Notes:** Decisive rationale — service_role bypasses RLS, and service_role (the pipeline) is exactly the actor that caused the 27-day silent wallet bug. The guarantee must hold against it. Pinned columns explicitly listed: `body_md`, `what_shifted`, `why_it_mattered`, `event_date`, `source_*`. Lifecycle columns (`status`, `published_at`) remain mutable for the publish transaction. Migration must carry a loud explanatory comment citing the silent-failure postmortem so future developers don't "simplify" the trigger back into RLS.

---

## Atomic publish-transaction interface

| Option | Description | Selected |
|--------|-------------|----------|
| Two `SECURITY DEFINER` functions | `publish_block_version(p_version_id)` + `reject_block_version(p_version_id)`, both LANGUAGE plpgsql SECURITY DEFINER. Called via `supabase.rpc(...)`. Matches `claim_agent_task` pattern. | ✓ |
| Single `publish_action(p_version_id, p_action)` function | One entry point with action discriminator. More compact; less self-documenting; one GRANT surface. | |
| Postgres procedure (CALL) instead of FUNCTION | Modern PG procedures support explicit transaction control. Weak ergonomics with supabase-py / supabase-js. | |

**User's choice:** Two SECURITY DEFINER functions, accepting the previewed function-body skeleton verbatim.

**Notes:** No caveats added — the recommended pattern matches the existing `claim_agent_task` shape directly. Functions live inside `economy_map` schema; `REVOKE ALL FROM PUBLIC` + `GRANT EXECUTE TO service_role` only. `RAISE EXCEPTION` on invalid state (version not found, version not in draft status). Reject leaves the draft's timeline entries unabsorbed so the next synthesis re-includes them.

---

## Block seed source + `live_tension` authorship

| Option | Description | Selected |
|--------|-------------|----------|
| Inline SQL INSERTs in the migration | All 7 blocks INSERTed at bottom of migration as a single statement, idempotent via ON CONFLICT. Copy is in-repo. | ✓ (with refinement) |
| INSERTs sourced from a JSON copy file | Migration reads from `.planning/docs/economy-map-seed.json` and INSERTs. Easier copy iteration; migration no longer self-contained. | |
| Empty schema + Python seed script | Migration creates tables only; separate seed script runs INSERTs. Most flexible, most ceremony, risk of forgetting the seed step. | |

**User's choice:** Inline SQL INSERTs, with `live_tension` seeded as a placeholder. Real editorial copy is set at runtime via the Phase 10 `/map-tension` command. No external YAML/JSON file.

**Notes:** Framing was *"migration owns structure; command surface owns editorial copy."* This satisfies ROADMAP success criterion 2 (every column has a value, all 7 blocks queryable) without forcing operator copy decisions to be locked in version control before launch. It also makes `/map-tension` testable from day one — populating real tensions becomes the operator's first concrete use of the Phase 10 command.

---

## Claude's Discretion

- Exact SQL formatting / column ordering inside the migration — follow `migrations/004_core_tables.sql` style.
- Trigger and helper-function naming.
- Whether to add indexes beyond PK + FK (only if there's an obvious query path).
- Exact wording of exception messages (just grep-friendly).
- Final wording of subtitles for the seven blocks (first-pass captions are in CONTEXT.md D-23; planner / executor may refine — slugs / tiers / accents / sort orders are locked).
- The literal placeholder string for `live_tension` (just obviously non-final).

## Deferred Ideas

- Per-block synthesis thresholds (`TUNE-01..03`) — v2.
- Promoting `negotiation-coordination` to its own block (`NEGB-01/02`) — v2.
- Supabase Realtime on `timeline_entries` — Phase 4's choice, not Phase 2's.
- Hybrid GRANT-revoke + trigger defense-in-depth — explicitly rejected in favor of trigger-only.
- Strict FK on `timeline_entries.source_edition_id` to `public.newsletters(id)` — keep as `text` per build spec.
- Custom SQLSTATEs for trigger raises — v2 if programmatic distinction is ever needed.
