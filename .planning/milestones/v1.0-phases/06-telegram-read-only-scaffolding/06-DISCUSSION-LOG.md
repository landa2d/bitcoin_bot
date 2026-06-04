# Phase 6: Telegram Read-Only Scaffolding - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-30
**Phase:** 6-telegram-read-only-scaffolding
**Areas discussed:** /map-status layout, "Unabsorbed" semantics + unsorted surfacing, ID display in /map-pending, Read-only enforcement

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| /map-status layout | Tier-grouping vs flat; maturity pill text rendering | ✓ |
| 'Unabsorbed' semantics | What counts as unabsorbed; where unsorted appears | ✓ |
| ID display in /map-pending | Raw UUID vs short index vs prefix | ✓ |
| Read-only enforcement | Read-scoped key vs verb discipline | ✓ |

**User's choice:** All four selected.

---

## /map-status layout

### Block ordering / grouping

| Option | Description | Selected |
|--------|-------------|----------|
| Grouped by tier | SUBSTRATE / BEHAVIOR / FRAME headers; most scannable for 7 items | ✓ |
| Flat by sort_order | Single 1–7 list, tier as a per-line label | |

**User's choice:** Grouped by tier (approved the monospace-aligned preview with per-block pill + counts).

### Maturity pill rendering

| Option | Description | Selected |
|--------|-------------|----------|
| Filled/empty blocks + label | `◉◉○○○ emerging` — 5-segment fill + word | ✓ |
| Word label only | Just the maturity word | |
| You decide | Pick what reads best; flag glyphs for researcher | |

**User's choice:** Filled/empty blocks + label.
**Notes:** Column alignment implies a monospace/code-block render. Exact glyphs (`◉`/`○`) flagged for
researcher to confirm Telegram rendering; the 5-segment + word-label contract is what's locked.

---

## "Unabsorbed" semantics + unsorted surfacing

### What counts as "unabsorbed"

| Option | Description | Selected |
|--------|-------------|----------|
| Since last_synthesized_at | Entries after blocks.last_synthesized_at; NULL → all. Matches Phase 7 SYNT-01 trigger | ✓ |
| All entries for block | Total entries regardless of synthesis | |

**User's choice:** Since last_synthesized_at (NULL → all).

### Where unsorted appears

| Option | Description | Selected |
|--------|-------------|----------|
| /map-pending only | Status = 7 real blocks; unsorted only in pending | |
| Both (status footer too) | Add an 'unsorted: N awaiting' footer to /map-status | |
| You decide | Default to pending-only; add status footer if it reads naturally | ✓ |

**User's choice:** You decide → resolved to: footer count line in /map-status + full per-entry list in
/map-pending (fail-loud backlog visibility).

---

## ID display in /map-pending

| Option | Description | Selected |
|--------|-------------|----------|
| Raw UUID (full) | Show real version_id/entry_id verbatim; stateless; write commands take exact value | ✓ |
| Short ephemeral index | 1,2,3… per run like /x-* daily_index; mutable state, stale-mismatch risk | |
| Short UUID prefix | First 8 chars; resolve by prefix; collision/ambiguity risk | |

**User's choice:** Raw UUID (full), with a pre-filled copy-paste command line per identifier.
**Notes:** Chosen to avoid the ephemeral-index silent-mismatch class and to feed Phase 9/10 write
commands the exact value with no translation layer.

---

## Read-only enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Read-scoped key/role | Read-only credential so mutation is structurally impossible at DB layer | |
| GET-only verb discipline | Reuse service_role + Accept-Profile; handlers issue only GET; code-review verified | |
| You decide | Strongest option without new infra/migration this phase; else GET-only + flag role hardening | ✓ |

**User's choice:** You decide → resolved to: reuse service_role + Accept-Profile, but encapsulate
economy_map access behind a GET-only read-only wrapper (no write methods) + code-review gate this
phase; flag a DB-level read-only role / RLS to Phase 9. Rationale: a pure anon path can't work because
anon RLS hides 'unsorted' which /map-pending must read, and a proper read-only role is net-new
migration work.

---

## Claude's Discretion

- Unsorted surfacing in /map-status (resolved: footer count line).
- Read-only enforcement mechanism (resolved: GET-only wrapper + code-review; DB role → Phase 9).
- Exact Telegram formatting within locked contracts; sync vs async httpx (match surrounding handler);
  combined vs separate PostgREST GETs; maturity glyph substitution if needed; sibling
  `handle_map_command()` vs extending the existing dispatch branch.

## Deferred Ideas

- DB-level read-only role / RLS + "anon hides unsorted" resolution → Phase 9.
- Write commands /map-approve, /map-reject (Phase 9); /map-assign, /map-entry, /map-synth,
  /map-tension (Phase 10).
- Richer status detail (timestamps, drill-down) — out of CMD-01/02 scope.

*None of the 5 pending todos matched this phase's scope; none folded.*
