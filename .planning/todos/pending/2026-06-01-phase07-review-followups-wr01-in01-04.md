---
created: 2026-06-01
area: economy-map-synthesis
source: 07-REVIEW.md
resolves_phase:
severity: advisory
---

# Phase 07 code-review deferred follow-ups (WR-01 migration + IN-01..04)

Phase 07 (synthesis loop core) code review returned **0 Critical, 5 Warning, 4 Info**. The four
code-only fail-loud / observability warnings (WR-02/03/04/05) were fixed before phase verification
(commit `60e9fc6`). The remaining items are deferred here: WR-01 because it is a **schema migration
with deploy implications** (operator-approved track, not bundled to clear a review warning), and the
Info items because they are latent or future-phase contracts.

## WR-01 — DB-level guard against duplicate open drafts (migration, operator-approved)

**File:** `docker/processor/agentpulse_processor.py` (`block_has_open_draft`, `synthesize_block`);
schema `supabase/migrations/033_economy_map_schema.sql:107-110`

The "one open draft per block" invariant (D-03) is enforced **only** by an application-layer
`block_has_open_draft` read at the top of `synthesize_block`, with no transaction/lock around the
later INSERT. The schema's partial index `idx_block_body_versions_status ... WHERE status='draft'` is
**non-unique**. A check-then-insert race (manual `/map-synth`, a re-entrant scheduled run, any future
concurrent caller) could write two `draft` rows for one block — the docstrings/tests assert a
guarantee the DB does not provide.

**Why deferred, not fixed in Phase 07:**
- Latent today — single-threaded daily `schedule` loop, draft-only/operator-gated writer (a worst-case
  duplicate draft surfaces in `/map-pending` for a human; it never reaches publish).
- The loop is not deployed/running yet. Concurrency becomes plausible only when the **Phase 10**
  manual `/map-synth` trigger lands — that is the right moment to ship the migration deliberately.
- Matches the recorded **structural-over-application enforcement** preference — but on its own
  approved migration track, consistent with **scoped, approved deploys / prod-cutover discipline**.

**Fix when Phase 9/10 makes synthesis manually triggerable:**
```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_block_body_versions_one_open_draft
    ON economy_map.block_body_versions (block_slug)
    WHERE status = 'draft';
```
Then treat the resulting unique-violation on INSERT as a benign skip (race lost), keeping
`block_has_open_draft` as the cheap fast-path. Apply via Supabase MCP `apply_migration`
(project ref `zxzaaqfowtqvmsbitqpu`), drift-check, scoped processor rebuild.

## Info (latent / awareness — no Phase 07 action)

- **IN-01** (`assemble_synthesis_input` ~3296-3320) — the token-budget loop drops timeline entries
  oldest-first but never trims the `PRIOR PUBLISHED BODY`, so a large prior body can shed real new
  evidence down to a single entry while the bloat stays. Draft-quality only (omission is noted
  in-prompt). Consider counting the prior body toward the budget / raising the entry floor.
- **IN-02** (`assemble_synthesis_input` ~3296, ~3312) — `len(text)//4` is a coarse token proxy
  (under/over-counts for non-English, URLs, code). Acceptable best-effort cap; swap in a real
  tokenizer if precision ever matters.
- **IN-03** (`_economy_map_get` ~3045-3066) — read helper accepts only HTTP 200; PostgREST uses
  `206 Partial Content` for range/count reads. Latent (no caller requests ranges; block set is 7
  rows). If range/count reads are added, broaden to `(200, 206)` (the insert helper already accepts
  `(200, 201)`).
- **IN-04** (`synthesize_block` ~3281-3290) — `synthesized_from_through` is the run wall-clock while
  the next cycle's recency filter is `created_at > last_synthesized_at`. Phase 07 correctly never
  sets `last_synthesized_at` (Phase 9's job). **Phase 9 contract:** the publish RPC MUST advance
  `last_synthesized_at` from the approved draft's `synthesized_from_through` (not the newest entry
  date), or entries created between synthesis and approval are double-counted/skipped.
