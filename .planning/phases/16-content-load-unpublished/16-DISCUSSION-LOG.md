# Phase 16: Content Load (unpublished) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-08
**Phase:** 16-content-load-unpublished
**Areas discussed:** Load packaging & artifacts, Fail-loud & no-change proof

**Gray areas presented (multiSelect):** Load packaging & artifacts ✓ · Re-run / partial-failure safety (not selected) · Fields the frontmatter omits (not selected) · Fail-loud & no-change proof ✓

---

## Load packaging & artifacts

### Q1 — How should the 8 markdown BODIES be loaded into `block_body_versions`?

| Option | Description | Selected |
|--------|-------------|----------|
| Python PostgREST loader | Standalone script parses each `.md`, inserts a draft via the existing helper; bodies stay in `.md` as source of truth | ✓ |
| Inlined in migration 043 | Bodies as SQL string literals, atomic via MCP — but duplicates text, markdown-in-SQL escaping, huge migration | |
| You decide | Delegate to planner/researcher | |

**User's choice:** Python PostgREST loader.

### Q2 — Where should the negotiation blocks-row INSERT + the sort_order reshuffle live?

| Option | Description | Selected |
|--------|-------------|----------|
| In migration 043 (with the DDL) | tier-CHECK relax + new negotiation row + 3 sort_order UPDATEs, one atomic transaction, highest-first (no UNIQUE collision) | ✓ |
| Via the Python loader (PostgREST) | All writes in one script, but splits structure out of the migration + needs a blocks-write helper + hand-sequenced collision avoidance | |
| You decide | Delegate to planner | |

**User's choice:** In migration 043 (with the DDL).

### Q3 — Where should the body-load script live and how is it invoked?

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone one-shot script | Self-contained `scripts/load_economy_map_content.py` with its own ~15-line PostgREST insert fn; never wired into the scheduler — honors "no pipeline changes" | ✓ |
| Import the processor helper | sys.path-import from the processor — but triggers heavy module-level init for one function | |
| You decide | Delegate to planner | |

**User's choice:** Standalone one-shot script.

### Q4 — Confirm the artifact boundary and run order?

| Option | Description | Selected |
|--------|-------------|----------|
| 043 = all structure; loader = bodies only | 043 owns tier-relax + hub row + negotiation row + reshuffle (atomic); orchestrator applies via Supabase MCP FIRST; loader inserts the 8 bodies SECOND (FK targets exist) | ✓ |
| Loader also creates the new blocks rows | Splits "structure" across both artifacts; needs a blocks-write helper in the one-shot script | |
| You decide | Delegate to planner | |

**User's choice:** 043 = all structure; loader = bodies only.

**Notes:** Clean separation — migration owns structure, loader owns editorial copy (matches the standing placeholder pattern). Live migration apply is orchestrator-owned (MCP), not run from a worktree executor.

---

## Fail-loud & no-change proof

### Q1 — How should the loader sequence validation vs. insertion across the 8 bodies?

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-flight validate ALL, then insert | Validate all 8 up front, HALT before any insert if any fails — satisfies SC#2 "no blank/partial block" | ✓ |
| Validate-and-insert per file | Simpler loop, but a bad 6th file leaves 5 drafts landed — partial load needing recovery | |
| You decide | Delegate to planner | |

**User's choice:** Pre-flight validate ALL, then insert.

### Q2 — Which fields must the pre-flight validation require?

| Option | Description | Selected |
|--------|-------------|----------|
| Full metadata + body + maturity | slug (in roster), title, subtitle, tier/type, order, maturity(block); body non-empty after strip; post-remap maturity ∈ live enum; hub special-cased | ✓ |
| Just body + maturity | Guard only the two SC#2 examples; trust the rest of the frontmatter | |
| You decide | Delegate to planner | |

**User's choice:** Full metadata + body + maturity.

### Q3 — Should the phase include an explicit negative test?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — deliberately-broken fixture | Run the loader on broken input (empty body / null maturity), confirm it halts loud and lands nothing | ✓ |
| No — trust the raises + DB constraints | Rely on code-present guards without executing a broken-input run | |
| You decide | Delegate to planner | |

**User's choice:** Yes — deliberately-broken fixture.

### Q4 — How should the phase prove the live `#/map` is unchanged?

| Option | Description | Selected |
|--------|-------------|----------|
| Before/after anon-perspective read | Capture anon-visible state before/after (blocks + published body counts, or rendered `#/map`); show identical | ✓ |
| Reason from RLS only | Assert from the contract without an empirical snapshot | |
| You decide | Delegate to planner | |

**User's choice:** Before/after anon-perspective read.

**Notes:** Operator's "verify the guard actually fires, not just that it exists" preference drove the negative-test + empirical-snapshot choices over reasoning-only.

---

## Claude's Discretion

Two presented gray areas were **not selected** for deep-dive; captured in CONTEXT.md with recommended defaults for the planner:
- **Re-run / partial-failure idempotency** — recommend idempotent skip-if-open-draft (reuse `block_has_open_draft`), with migration 041's one-open-draft UNIQUE index as the structural backstop.
- **Fields the frontmatter omits** — `live_tension` → seed placeholder `'TBD — set via /map-tension'`; hub `proposed_maturity` → `'nascent'`; `accent` for hub/negotiation → planner picks from the CHECK set (hub example: `'gray'`); existing-row metadata → frontmatter is truth, verify-and-correct via permitted `blocks` UPDATE.

## Deferred Ideas

- Phase 17: `renderHub` body fetch + `marked.parse`, cross-link resolution, preview route, cards-vs-prose, nascent visual treatment.
- Phase 18: the `publish_block_version` RPC run + web-only scoped deploy.
- EU AI Act tracker → `regulation-legal` body (future milestone).
- Evolution timeline content (intake fills weekly; no manual authoring this milestone).
