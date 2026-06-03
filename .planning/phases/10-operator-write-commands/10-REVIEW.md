---
phase: 10-operator-write-commands
reviewed: 2026-06-03T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - supabase/migrations/040_operator_write_commands_schema.sql
  - supabase/migrations/041_block_body_versions_unique_open_draft.sql
  - docker/gato_brain/gato_brain.py
  - docker/processor/agentpulse_processor.py
findings:
  critical: 1
  warning: 5
  info: 2
  total: 8
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-06-03
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 10 adds four operator write commands (`/map-assign`, `/map-entry`, `/map-synth`,
`/map-tension`) across two new migrations and the two Python monoliths. Review was scoped
to the diff against `5dd91b9d^..HEAD`. The implementation is conscientious about most
project invariants — owner-gate is the first statement in every new handler, slug values
are passed as typed RPC params (never interpolated), the `fn` allowlist gates the RPC URL
before it is built, `synth_requests.status` writes stay inside the CHECK set
`{pending,processing,done,failed}`, the open-draft invariant is preserved on the forced
path, and the 23505 race is a logged benign skip rather than a fail-loud abort.

However, the review found one genuine security-boundary defect: the
`reassign_timeline_entry` RPC — which executes as `service_role` and therefore bypasses
RLS — performs NO server-side validation of its target slug, unlike its sibling
`insert_manual_timeline_entry`. Per the project's own "structural over application
enforcement" rule, the gato_brain allowlist is application-layer and cannot be the only
gate. Several robustness/fail-loud gaps in the drain poller and error-remapping logic are
also documented.

## Critical Issues

### CR-01: `reassign_timeline_entry` RPC has no server-side slug validation (RLS-bypassing write surface)

**File:** `supabase/migrations/040_operator_write_commands_schema.sql:149-191`
**Issue:**
The RPC is `SECURITY DEFINER` and executes as `service_role`, which bypasses RLS — so the
RPC body is the actual security/integrity boundary (per CLAUDE.md + MEMORY:
"structural over application enforcement … service_role bypasses RLS and is the historical
failure actor"). Yet `reassign_timeline_entry` accepts `p_block_slug` and INSERTs a new
`timeline_entries` row under it with **zero validation**:

- It does NOT reject `p_block_slug = 'unsorted'` (a reassignment to the backlog is
  nonsensical and would re-create the very state `/map-assign` exists to drain).
- It does NOT verify the slug exists in `economy_map.blocks` (unlike
  `insert_manual_timeline_entry:219-226`, which explicitly rejects `'unsorted'` and runs
  `IF NOT EXISTS (SELECT 1 FROM economy_map.blocks WHERE slug = p_slug)`).

The ONLY thing standing between an arbitrary/unknown/`'unsorted'` slug and a filed
timeline row is gato_brain's `_validate_block_slug` (`gato_brain.py:1640`), an
application-layer check. Any other `service_role` caller (a future processor path, a
direct RPC, a drift between the hardcoded `_ECONOMY_MAP_BLOCK_SLUGS` frozenset and the
DB seed) can create an orphan timeline entry under a non-existent block, silently.

**Fix:** Mirror `insert_manual_timeline_entry`'s guards inside the RPC, after the `NOT FOUND`
gate:
```sql
    IF NOT FOUND THEN
        RAISE EXCEPTION 'timeline entry % is not an unsorted, un-reassigned entry', p_entry_id;
    END IF;

    -- Reassignment target must be a real, non-backlog block (DB is the boundary; service_role bypasses RLS).
    IF p_block_slug = 'unsorted' THEN
        RAISE EXCEPTION 'cannot reassign an entry back to the unsorted backlog';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM economy_map.blocks WHERE slug = p_block_slug) THEN
        RAISE EXCEPTION 'block % not found', p_block_slug;
    END IF;
```

## Warnings

### WR-01: Synth requests stuck in `processing` are never recovered or made terminal

**File:** `docker/processor/agentpulse_processor.py:3870-3899` (claim) and `:3849-3856` (pending query)
**Issue:**
The drain claims a request by writing `status='processing'` before calling
`synthesize_block`. If the processor crashes, is restarted, or the container is rebuilt
mid-synthesis (a routine event per CLAUDE.md's `docker compose up -d --build` flow), the
row is left permanently `processing`. The pending query only reads `status=eq.pending`
(`:3851`), so a `processing` row is never re-drained and never reaches a terminal
`done`/`failed` state. This directly contradicts the module's own D-03 contract ("Every
request gets a queryable terminal status … a failed forced-synth must be as visible as a
failed autonomous cycle") — a crashed request is invisible, neither retried nor failed.
This is the "wallet bug" failure shape: a governed action silently stalls instead of
failing loud.
**Fix:** Add a stale-`processing` reclaim to the drain (e.g. re-include rows where
`status=eq.processing` and `updated_at < now()-interval '5 min'` as either retryable or
forced to `failed` with a "drain interrupted" error). At minimum, mark such rows `failed`
with an explanatory error so they remain queryable.

### WR-02: `_RPC_BLOCK_NOT_FOUND = "not found"` substring match is dangerously broad

**File:** `docker/gato_brain/gato_brain.py:2147` (used at `:2240` and `:2348`)
**Issue:**
The error-discrimination marker is the bare substring `"not found"`. It is matched against
the full `RuntimeError` text raised by `_economy_map_rpc`, which embeds `resp.text` from
PostgREST. Many unrelated PostgREST/Postgres errors contain "not found" (e.g. function
signature resolution `"Could not find the function … not found"`, schema/relation errors,
a 404 routing failure). Any such error in `/map-entry` or `/map-tension` would be
misclassified as a benign "unknown block" user message instead of surfacing the real
failure — a fail-loud regression (a genuine write failure reads as a routine validation
nudge).
**Fix:** Match the RPC's specific typed RAISE text, e.g. `f"block {slug} not found"` /
`"block " + slug + " not found"`, or a sentinel substring like `"block "` + `" not found"`
that the migration emits, rather than the generic `"not found"`.

### WR-03: RPC "not found" remap returns the wrong (misleading) user message

**File:** `docker/gato_brain/gato_brain.py:2240` and `:2348`
**Issue:**
On an RPC "not found" error, both `handle_map_entry` and `handle_map_tension` return
`_validate_block_slug("", verb)[1]`. With an empty slug, `_validate_block_slug`
(`:1660-1662`) returns `(None, f"{verb} needs a <block_slug>.")` — the *missing-arg*
message, NOT the unknown-slug message. So an operator who supplied a valid-format slug that
exists in `_ECONOMY_MAP_BLOCK_SLUGS` but is absent from the DB `blocks` table (allowlist/seed
drift) is told "/map-entry needs a <block_slug>." — confusing and wrong. The intent was
clearly the unknown-slug branch.
**Fix:** Return a purpose-built unknown-slug message, e.g.
`f"Block '{slug}' is not in the live economy map (no such block row). Run /map-status."`,
threading the actual slug rather than re-invoking the validator with `""`.

### WR-04: `reassign_timeline_entry` copy has no idempotency / single-flight guard against a duplicate filed row

**File:** `supabase/migrations/040_operator_write_commands_schema.sql:165-187`
**Issue:**
The single-winner gate relies on the source SELECT (`block_slug='unsorted' AND
reassigned_to_entry_id IS NULL`) followed by a later UPDATE that sets
`reassigned_to_entry_id`. There is no row lock (`FOR UPDATE`) between the SELECT and the
UPDATE, and the INSERT of the copy happens before the original is marked. Two concurrent
`/map-assign` calls on the same entry id (operator double-tap, or a retry) can both pass
the SELECT, both INSERT a copy under the target block, and then both UPDATE — producing
**two** filed timeline entries for one unsorted item, both pointing the original at one of
the new ids. Because `timeline_entries` is append-only, the spurious duplicate cannot be
deleted.
**Fix:** Add `FOR UPDATE` to the Step-1 SELECT so the row is locked for the duration of the
transaction, making the gate a true single-winner:
```sql
    SELECT ... INTO ...
      FROM economy_map.timeline_entries
     WHERE id = p_entry_id AND block_slug='unsorted' AND reassigned_to_entry_id IS NULL
       FOR UPDATE;
```

### WR-05: Forced-synth open-draft skip is recorded as `failed`, conflating "no-op refusal" with "error"

**File:** `docker/processor/agentpulse_processor.py:3922-3946`
**Issue:**
When a forced synth finds an existing open draft (or loses the 23505 race),
`synthesize_block` returns `status='skipped'`, and the drain maps this to
`status='failed'` with an explanatory error. The CHECK-set constraint genuinely forbids a
`'skipped'` status value, so writing `'failed'` avoids the 23514 — that reasoning is
sound. But semantically this records a *correct, expected refusal* as a *failure*, so any
operator dashboard / alerting that counts `failed` synth_requests will over-report failures
and dilute signal for genuine Sonnet/insert errors (also `failed`). The two are
indistinguishable except by parsing the free-text `error` string.
**Fix:** Either add a distinct allowed status value to the migration-040 CHECK set (e.g.
`'declined'` / `'noop'`) and write that for the open-draft case, or add a structured
discriminator column (e.g. `outcome text`) so genuine errors and expected refusals are
queryable apart. If the closed set must stay frozen, document the convention and have
consumers key off an error-prefix sentinel rather than a substring.

## Info

### IN-01: `limit` param type is inconsistent across economy_map GET call sites

**File:** `docker/processor/agentpulse_processor.py:3893` (`"limit": 1`, int) vs `docker/gato_brain/gato_brain.py:1834` (`"limit": "1"`, str) and `:3133` (`"limit": 1`, int)
**Issue:** Both forms work (httpx stringifies), but mixing int and str `limit` values across
the new and existing call sites is an avoidable inconsistency that invites confusion.
**Fix:** Standardize on the string form (`"limit": "1"`) used by the other PostgREST params,
which are all strings.

### IN-02: `totals['skipped']` is counted but the request is written `failed` — naming drift

**File:** `docker/processor/agentpulse_processor.py:3944` and summary log `:3987`
**Issue:** The in-memory `totals['skipped']` counter is incremented for requests that are
persisted as `status='failed'`, and the closing log says `"{skipped} skipped→failed"`. The
double meaning (in-memory "skipped" vs DB "failed") is explained in comments but is a
naming hazard for the next maintainer reading the metrics.
**Fix:** Rename the counter to `declined` or `noop` to match the intended semantics, or
fold it into `failed` with a sub-reason, aligning with the WR-05 resolution.

---

_Reviewed: 2026-06-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
