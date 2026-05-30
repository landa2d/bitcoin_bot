---
created: 2026-05-30
area: economy-map-telegram
source: 06-REVIEW.md
resolves_phase:
severity: advisory
---

# Phase 06 code-review advisory follow-ups (WR-01, WR-02, IN-01..04)

Phase 06 (`/map-status`, `/map-pending`) code review returned **0 Critical, 2 Warning, 4 Info**.
None met the "fix before verify" bar (silent data loss / fail-loud violation), so they were captured
here rather than blocking phase verification. Read-only-by-construction, enum mapping, and fail-loud
reads all held up under review.

## Warnings

- **WR-01 (`docker/gato_brain/gato_brain.py` ~1838-1841)** — `cmd = parts[0].lower()` runs OUTSIDE
  the handler's try/except; an empty/whitespace `/map-` message would make `split()` return `[]` →
  `IndexError` → 500, bypassing the "Command failed" string contract. **Currently shielded** by the
  `/chat` routing guard (`startswith("/map-")`), so it is NOT reachable in Phase 6 usage. **Fix when
  Phase 9/10 wires the write commands** (`/map-approve`, `/map-assign`, …) that call these handlers
  as a direct public entry point — that is exactly when the shield drops. One-line fix: guard empty
  `parts` / move the index access inside the try.

- **WR-02 (`docker/gato_brain/gato_brain.py` ~1730-1735)** — `handle_map_status` issues 7 per-block
  unabsorbed-count GETs inside the render loop with no per-block isolation; one transient read
  failure raises and blanks the entire status view (10 all-or-nothing failure points). This *upholds*
  fail-loud (raises rather than rendering wrong data — the locked must-have), but hurts availability.
  Consider per-block try/except that renders a `·? new` placeholder for a failed block while still
  showing the rest, OR a single batched count query. Revisit if operators hit transient blanks.

## Info

- **IN-01** — `/map-pending` unsorted list orders by `created_at.desc`; the schema's canonical
  newest-first index is `event_date DESC` (033 / RNDR-07). Reconcile ordering for consistency with
  the renderer's timeline order.
- **IN-02** — `/map-status` unabsorbed count uses `last_synthesized_at` (wall-clock) while Phase 7
  SYNT-01/03 will window entries by `synthesized_from_through` (watermark). Reconcile the two when
  Phase 7 lands so the status count and the synthesis trigger agree (already flagged in 06-CONTEXT
  D-05).
- **IN-03** — `/map-pending` unsorted truncation is **signaled, not silent** (appends
  `"…and N more (truncated)"`, stateless full UUIDs). Acceptable v1; add paging only if full
  enumeration of a large backlog is needed.
- **IN-04** — cosmetic `tag_confidence` rendering nit.

**Why:** keeps the intake/read surface honest as it grows; WR-01 in particular has a natural home in
Phase 9/10. **How to apply:** fold WR-01 into the Phase 9/10 write-command plan; address WR-02/IN-01
opportunistically or when operators report it. See [[feedback-fix-review-blockers-before-verification]].
