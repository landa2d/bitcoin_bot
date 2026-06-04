# Phase 2: `economy_map` Schema + Seven-Block Seed — Pattern Map

**Mapped:** 2026-05-26
**Files analyzed:** 3 (1 migration + 1 verification SQL + 1 verification-results doc)
**Analogs found:** 1 / 3 exact; 1 partial; 1 first-in-tree precedent
**Existing migrations scanned:** 33 (`001_initial_schema.sql` → `032_prepass_tracking_justification_and_staleness.sql`)

---

## Headline finding: three first-in-tree precedents

Before per-file pattern assignment, the planner must internalize that **Phase 2's migration introduces three patterns that do not exist anywhere in `supabase/migrations/`**. A repo-wide `grep` returned **zero hits** for any of the following:

| Pattern | grep query | Hits | Status |
|---------|------------|------|--------|
| `CREATE SCHEMA …` | `grep -n 'CREATE SCHEMA' supabase/migrations/*.sql` | 0 | first in-tree |
| `CREATE TYPE … AS ENUM` | `grep -n 'CREATE TYPE' supabase/migrations/*.sql` | 0 | first in-tree |
| `CREATE TRIGGER` / `BEFORE UPDATE` / `BEFORE DELETE` | `grep -nE 'CREATE TRIGGER\|BEFORE UPDATE\|BEFORE DELETE' supabase/migrations/*.sql` | 0 | first in-tree |
| `RAISE EXCEPTION` (typed raise in trigger body) | `grep -n 'RAISE EXCEPTION' supabase/migrations/*.sql` | 0 | first in-tree |

This confirms `01-FINDINGS.md` §4.4 (no `eu_ai_act` migration exists) and CONTEXT.md `D-04` / `D-10` ("This migration establishes the in-tree precedent…"). The planner / executor must therefore **invent these patterns** — there is no analog to copy. The migration's **loud comment block** (D-14, the "27-day wallet bug" rationale) matters because future agents will otherwise try to "simplify" the triggers away.

For the patterns where a precedent **does** exist (RPC shape, `CREATE TABLE IF NOT EXISTS` style, idempotent seed, RLS posture), the analogs are concrete and quotable below.

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `supabase/migrations/033_economy_map_schema.sql` | migration (DDL + seed + RPC + RLS + triggers) | one-shot DDL | `004_core_tables.sql` (table shape, idempotent seed), `006_rls_policies.sql` (RLS posture), `015_agent_wallets.sql` (multi-table + seed + RPC), `013_unsubscribe_rpc.sql` / `022_subscribe_rpc.sql` (`plpgsql SECURITY DEFINER` RPC shape), `003_atomic_task_claiming.sql` (atomic-mutation function — `SQL` body, not `plpgsql`) | **role-match**; no analog for `CREATE SCHEMA`, `CREATE TYPE … AS ENUM`, or `CREATE TRIGGER` |
| `.planning/phases/02-economy-map-schema-seven-block-seed/02-VERIFY.sql` | verification SQL (read-write exercise script) | request-response (SQL → assertions) | **none in-tree** — `supabase/migrations/*.sql` files are migrations, not verify scripts; `scripts/` directory has shell/Python utilities only | **no analog** — follow CONTEXT.md D-25 directly |
| `.planning/phases/02-economy-map-schema-seven-block-seed/02-VERIFY-RESULTS.md` | verification-results doc (structured proof) | document | `.planning/phases/01-render-stack-diagnostic/01-VERIFICATION.md` (front-matter + "Observable Truths" table + "Required Artifacts" table) | **partial** — Phase 1 used `VERIFICATION.md` for plan-execution verification; Phase 2 needs a **schema-exercise** results doc, similar structure |

---

## Pattern Assignments

### `supabase/migrations/033_economy_map_schema.sql` (migration, one-shot DDL)

The new migration is composite — five distinct sub-patterns, each with a different analog. Each is laid out below in the order the migration file should emit them.

---

#### 1. File header + comment block (style)

**Analog:** `supabase/migrations/004_core_tables.sql` (lines 1–3), `024_x_source_accounts.sql` (lines 1–4)

**004 header:**
```sql
-- Migration 004: Core tables missing from initial schema
-- All tables use CREATE TABLE IF NOT EXISTS for safe re-runs.
-- Schema inferred from production Python code (processor, analyst, newsletter).
```

**024 header (preferred — more current style; uses the ═══ section dividers):**
```sql
-- Migration 024: X/Twitter source accounts for research pipeline scanning
-- Curated list of high-signal individual voices on the AI agent economy.
-- Accounts stored here can be managed via DB without code changes.
```

**Section dividers (024 lines 5–7 & 33–35; reusable inside the new migration):**
```sql
-- ═══════════════════════════════════════════════════════
-- x_source_accounts — X accounts scanned as research pipeline sources
-- ═══════════════════════════════════════════════════════
```

**Recommendation:** Copy 024's `═══` divider style (current convention; 021, 024 use it). Open with a comment naming the migration purpose AND citing this phase's milestone ("Phase 2 / The Agent Economy — first isolated-schema migration; reference for future `eu_ai_act`-style work per CONTEXT.md D-04").

---

#### 2. `CREATE SCHEMA` — first in-tree precedent (no analog)

**Analog:** **None.** No prior migration creates a schema; everything has lived in `public`.

**Pattern to invent** (planner / executor):
```sql
CREATE SCHEMA IF NOT EXISTS economy_map;
GRANT USAGE ON SCHEMA economy_map TO anon, authenticated, service_role;
```

The `GRANT USAGE` is **required** for `Accept-Profile: economy_map` reads from PostgREST to resolve — without it, anon cannot enter the schema even if RLS would otherwise allow the row read.

---

#### 3. `CREATE TYPE … AS ENUM` — first in-tree precedent (no analog)

**Analog:** **None.** Repo-wide enums are encoded as `TEXT NOT NULL CHECK (col IN (…))` — e.g. `021_x_distribution_pipeline.sql` line 10:

```sql
content_type text NOT NULL CHECK (content_type IN ('sharp_take', 'newsletter_thread', 'engagement_reply', 'prediction')),
```

**Per CONTEXT.md D-03, this migration breaks from that pattern and uses a real Postgres enum:**

```sql
CREATE TYPE economy_map.maturity AS ENUM (
    'nascent',
    'emerging',
    'contested',
    'consolidating',
    'mature'
);
```

Both `blocks.maturity` and `block_body_versions.proposed_maturity` use this type (typed-not-text-+-CHECK). Migration places the `CREATE TYPE` **before** any `CREATE TABLE` that references it.

---

#### 4. `CREATE TABLE IF NOT EXISTS` — column ordering and index style

**Analog:** `supabase/migrations/004_core_tables.sql` lines 9–24 (`source_posts`) and `021_x_distribution_pipeline.sql` lines 7–31 (`x_content_candidates`)

**004 table shape (canonical — copy this style):**
```sql
CREATE TABLE IF NOT EXISTS source_posts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source          TEXT NOT NULL,                          -- hackernews, github, rss_*, thought_leader_*
    source_id       TEXT NOT NULL,                          -- Original ID from the source
    source_url      TEXT,
    source_tier     INTEGER DEFAULT 3,                      -- 1=authority, 2=curated, 3=community
    title           TEXT,
    body            TEXT,
    author          TEXT,
    score           FLOAT DEFAULT 0,                        -- HN score, GitHub stars, RSS tier
    comment_count   INTEGER DEFAULT 0,
    tags            TEXT[] DEFAULT '{}',
    metadata        JSONB,
    scraped_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_source_posts_source ON source_posts(source);
CREATE INDEX IF NOT EXISTS idx_source_posts_scraped ON source_posts(scraped_at DESC);
```

**Conventions to mirror:**
- `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` on every table.
- Column names aligned to a fixed column with whitespace padding.
- Inline comments after each column when meaning isn't obvious.
- `UNIQUE (…)` constraint at the end of the column list (inside the table body, not in a separate `ALTER TABLE`).
- Indexes follow immediately after the table body, named `idx_<table>_<column>` (021 drops the `IF NOT EXISTS` on the index, 004 keeps it — prefer `IF NOT EXISTS` for replay safety).

**Apply to `economy_map.blocks`, `economy_map.block_body_versions`, `economy_map.timeline_entries`** with the columns enumerated in CONTEXT.md D-11, D-13, and SCHM-02..04. Note: tables inside the `economy_map` schema must be created with the schema-qualified name `CREATE TABLE IF NOT EXISTS economy_map.blocks (…)`.

---

#### 5. RLS posture — anon-read with `status='published'` filter

**Analog:** `supabase/migrations/006_rls_policies.sql` (the canonical doc for this repo's RLS posture)

**Strategy comment (lines 1–9 — copy near-verbatim, adapted):**
```sql
-- Migration 006: Row-Level Security (RLS) policies
--
-- Strategy:
--   - service_role key: bypasses RLS entirely (fine for all agents — they use service_role)
--   - anon key: read-only on newsletters and spotlight_history (public web archive)
--   - anon key: NO access to agent_tasks, predictions, agent_daily_usage, or any internal tables
--
-- IMPORTANT: Test with service_role key before enabling to confirm agents are not locked out.
-- All agents already use SUPABASE_SERVICE_KEY which bypasses RLS — this is safe to enable.
```

**The published-only anon read pattern (lines 38–42 — mirror exactly for `block_body_versions`, per CONTEXT.md D-06):**
```sql
DROP POLICY IF EXISTS newsletters_anon_read ON newsletters;
CREATE POLICY newsletters_anon_read ON newsletters
    FOR SELECT
    TO anon
    USING (status = 'published');
```

**The "always-true" anon read pattern (lines 48–52 — mirror for `blocks`, per CONTEXT.md D-05):**
```sql
DROP POLICY IF EXISTS spotlight_history_anon_read ON spotlight_history;
CREATE POLICY spotlight_history_anon_read ON spotlight_history
    FOR SELECT
    TO anon
    USING (true);
```

**Per CONTEXT.md D-05 / D-06 / D-07, three policies are needed:**
- `blocks_anon_read`: `USING (true)` — all rows readable.
- `block_body_versions_anon_read`: `USING (status = 'published')` — mirrors `newsletters_anon_read` verbatim.
- `timeline_entries_anon_read`: `USING (block_slug <> 'unsorted')` — same shape, different predicate.

**ALTER TABLE … ENABLE ROW LEVEL SECURITY** is required first (per 006 lines 15–32 pattern). For schema-qualified tables, use `ALTER TABLE economy_map.blocks ENABLE ROW LEVEL SECURITY;` etc.

**SELECT grants** (PostgREST requires both RLS pass AND a SELECT GRANT — pattern not explicit in 006 because `public` schema's anon already had grants. For a new schema, the grants are required):
```sql
GRANT SELECT ON economy_map.blocks TO anon;
GRANT SELECT ON economy_map.block_body_versions TO anon;
GRANT SELECT ON economy_map.timeline_entries TO anon;
GRANT ALL ON ALL TABLES IN SCHEMA economy_map TO service_role;
```

---

#### 6. Append-only via `BEFORE UPDATE` / `BEFORE DELETE` triggers — first in-tree precedent (no analog)

**Analog:** **None.** Zero prior migrations use `CREATE TRIGGER`, `BEFORE UPDATE`, `BEFORE DELETE`, or `RAISE EXCEPTION` in a trigger body.

**This is the design-critical "first precedent" pattern.** Per CONTEXT.md D-10 / D-14 and the planner-bridge text in `<code_context>` "Established Patterns":

> "no in-tree precedent yet; this is the first table in the repo to enforce immutability at the database level. The pattern is straightforward but new for this codebase, so the migration's loud comment block matters: it documents the design rationale for the next developer who'd otherwise wonder why RLS isn't enough."

**The loud comment block is MANDATORY** (executor must include — verbatim or near-verbatim):
```sql
-- ═══════════════════════════════════════════════════════
-- APPEND-ONLY ENFORCEMENT — INTENTIONALLY NOT RLS
-- ═══════════════════════════════════════════════════════
-- Content immutability must hold AGAINST service_role, not just anon.
-- service_role bypasses RLS by design (see migration 006 strategy comment).
-- The pipeline that produced the 27-day silent wallet bug ran as service_role.
-- See `.planning/PROJECT.md` "Recent history that shapes design".
--
-- Therefore: BEFORE UPDATE / BEFORE DELETE triggers, NOT a stricter RLS policy.
-- A future developer WILL try to "simplify" this to RLS. Do not.
-- ═══════════════════════════════════════════════════════
```

**Pattern to invent (no analog — based on CONTEXT.md D-14):**
```sql
CREATE OR REPLACE FUNCTION economy_map.block_body_versions_append_only()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- DELETE is never allowed on this table.
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'block_body_versions is append-only (DELETE not permitted)';
    END IF;

    -- For UPDATE: only the lifecycle columns (status, published_at) may change.
    IF NEW.body_md IS DISTINCT FROM OLD.body_md THEN
        RAISE EXCEPTION 'block_body_versions.body_md is append-only (was %, now %)', OLD.body_md, NEW.body_md;
    END IF;
    IF NEW.synthesized_from_through IS DISTINCT FROM OLD.synthesized_from_through THEN
        RAISE EXCEPTION 'block_body_versions.synthesized_from_through is append-only';
    END IF;
    IF NEW.proposed_maturity IS DISTINCT FROM OLD.proposed_maturity THEN
        RAISE EXCEPTION 'block_body_versions.proposed_maturity is append-only';
    END IF;
    IF NEW.validator_report IS DISTINCT FROM OLD.validator_report THEN
        RAISE EXCEPTION 'block_body_versions.validator_report is append-only';
    END IF;
    IF NEW.block_slug IS DISTINCT FROM OLD.block_slug THEN
        RAISE EXCEPTION 'block_body_versions.block_slug is append-only';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER block_body_versions_append_only_trg
BEFORE UPDATE OR DELETE ON economy_map.block_body_versions
FOR EACH ROW EXECUTE FUNCTION economy_map.block_body_versions_append_only();
```

**A second trigger function** of the same shape applies to `economy_map.timeline_entries` with the pinned-column list from CONTEXT.md D-11 (`block_slug`, `event_date`, `what_shifted`, `why_it_mattered`, `source_url`, `source_edition_id`, `tag_confidence`). All columns on `timeline_entries` are pinned (it is fully append-only, with no lifecycle columns).

**Exception message convention** (CONTEXT.md "Claude's Discretion"): make the strings **grep-friendly**. The verification script (file 2 below) asserts on these by searching for substrings like `'append-only'` and `'not permitted'`.

---

#### 7. `SECURITY DEFINER` RPC functions — direct analog exists

**Analog (primary):** `supabase/migrations/013_unsubscribe_rpc.sql` (full file, 17 lines) — the minimal `LANGUAGE plpgsql SECURITY DEFINER` example. **Also see** `015_agent_wallets.sql` lines 45–65 (`record_agent_spend` — a multi-statement atomic-mutation RPC), and `003_atomic_task_claiming.sql` lines 4–24 (`LANGUAGE sql` variant — NOT preferred here because `publish_block_version` needs multi-statement plpgsql control flow with `RAISE EXCEPTION` and an `INTO` clause).

**013 minimal shape (canonical — copy this skeleton):**
```sql
CREATE OR REPLACE FUNCTION unsubscribe(subscriber_id UUID)
RETURNS void AS $$
BEGIN
    UPDATE subscribers
    SET status = 'unsubscribed',
        unsubscribed_at = NOW()
    WHERE id = subscriber_id
      AND status = 'active';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION unsubscribe(UUID) TO anon;
```

**022 even-shorter shape with explanatory comment (lines 1–3 — the "why SECURITY DEFINER" pattern):**
```sql
-- Migration 022: Subscribe RPC function
-- SECURITY DEFINER bypasses RLS so anon can upsert subscribers
-- (PostgreSQL requires SELECT permission for ON CONFLICT, which anon doesn't have)
```

**015 multi-statement plpgsql shape (lines 45–65) — closer to what `publish_block_version` needs:**
```sql
CREATE OR REPLACE FUNCTION record_agent_spend(
    p_agent_name TEXT,
    p_amount_sats BIGINT,
    p_counterparty TEXT DEFAULT NULL,
    p_description TEXT DEFAULT NULL,
    p_reference_id TEXT DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE agent_wallets
    SET balance_sats = balance_sats - p_amount_sats,
        total_spent = total_spent + p_amount_sats,
        updated_at = now()
    WHERE agent_name = p_agent_name;

    INSERT INTO agent_transactions (agent_name, counterparty, amount_sats, transaction_type, description, reference_id)
    VALUES (p_agent_name, p_counterparty, p_amount_sats, 'spend', p_description, p_reference_id);
END;
$$;
```

**Pattern to apply to `publish_block_version` (per CONTEXT.md D-17):**
```sql
CREATE OR REPLACE FUNCTION economy_map.publish_block_version(p_version_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = economy_map, public
AS $$
DECLARE
    v_slug text;
    v_maturity economy_map.maturity;
BEGIN
    UPDATE economy_map.block_body_versions
       SET status = 'published',
           published_at = NOW()
     WHERE id = p_version_id
       AND status = 'draft'
    RETURNING block_slug, proposed_maturity
      INTO v_slug, v_maturity;

    IF v_slug IS NULL THEN
        RAISE EXCEPTION 'version % not found or not in draft status', p_version_id;
    END IF;

    UPDATE economy_map.block_body_versions
       SET status = 'superseded'
     WHERE block_slug = v_slug
       AND status = 'published'
       AND id <> p_version_id;

    UPDATE economy_map.blocks
       SET current_body_version_id = p_version_id,
           maturity = v_maturity,
           last_synthesized_at = NOW()
     WHERE slug = v_slug;
END;
$$;

REVOKE ALL ON FUNCTION economy_map.publish_block_version(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION economy_map.publish_block_version(uuid) TO service_role;
```

**Same shape for `reject_block_version`** with the simpler body in D-18.

**Important convention deltas from the analogs:**

1. **`SET search_path = economy_map, public`** — none of the analogs include this. It is **required** for SECURITY DEFINER functions touching cross-schema names, and is a well-known plpgsql safety idiom (prevents schema-spoofing attacks). The planner should adopt it for both RPC functions.
2. **`GRANT EXECUTE … TO service_role` (NOT `TO anon`)** — opposite of 013 (`unsubscribe` grants to anon). Per CONTEXT.md D-19, publish/reject are service_role-only.
3. **The `REVOKE ALL … FROM PUBLIC`** — neither 013 nor 015 include this; D-19 requires it. Defense in depth: even if a future migration creates a new role, it does not inherit publish/reject access.

---

#### 8. Idempotent seed via `ON CONFLICT (…) DO NOTHING`

**Analog:** `supabase/migrations/015_agent_wallets.sql` lines 34–42 (closest — `DO NOTHING` posture), and `024_x_source_accounts.sql` lines 26–50 (multi-row `VALUES` block with column-level inline comments — preferred for the seven-block seed)

**015 shape (canonical for `DO NOTHING`):**
```sql
-- Seed initial balances
INSERT INTO agent_wallets (agent_name, balance_sats, total_deposited)
VALUES
    ('gato',       100000, 100000),
    ('processor',  100000, 100000),
    ('analyst',     50000,  50000),
    ('newsletter',  50000,  50000),
    ('research',    50000,  50000)
ON CONFLICT (agent_name) DO NOTHING;
```

**024 shape (multi-row with `-- comment` section headers, preferred for the seven-block seed):**
```sql
INSERT INTO x_source_accounts (x_handle, display_name, category, description, priority)
VALUES
    -- Macro/Strategic
    ('jvisserlabs',     'Jordi Visser',         'macro',    'AI × macro × crypto investment thesis',                7),
    ('emollick',        'Ethan Mollick',        'macro',    'AI impact on work/economy, Wharton',                   8),
    …
    -- Builder/Infrastructure
    ('swyx',            'Shawn Wang',           'builder',  'Latent Space, AI engineering, agent frameworks',        8),
    …
ON CONFLICT (x_handle) DO UPDATE SET …
```

**Recommendation:** copy 024's **layout** (multi-row VALUES with `-- Substrate / -- Behavior / -- Frame` section comments mapped to the tier groups) BUT use 015's `ON CONFLICT (slug) DO NOTHING` (NOT 024's `DO UPDATE`) — per CONTEXT.md D-20, "structural fields hardcoded in SQL", and per D-21, `live_tension` is a placeholder string that `/map-tension` populates at runtime. `DO NOTHING` is the right idempotency posture because re-running the migration must **not** clobber operator-set `live_tension` editorial copy.

**The seven rows are fully specified in CONTEXT.md D-23**, with `live_tension = 'TBD — set via /map-tension'` (or some grep-friendly variant — CONTEXT.md "Claude's Discretion" allows variation).

---

### `.planning/phases/02-economy-map-schema-seven-block-seed/02-VERIFY.sql` (verification SQL, request-response)

**Analog:** **None in-tree.** `supabase/migrations/*.sql` files do DDL/seed, never verification runs. `scripts/` contains shell/Python utilities only (`deploy.sh`, `backfill_impact.py`, PowerShell helpers), no SQL exercise scripts.

**Recommendation:** Construct this script directly from CONTEXT.md D-25's five-bullet checklist. No code to copy — instead, the planner should structure the file as labelled SQL blocks (one per D-25 sub-bullet), each with a comment-prefixed expected-result line for the verification-results doc to capture verbatim. For example:

```sql
-- ───────────────────────────────────────────────────────────
-- D-25 bullet 1: Seven blocks queryable from economy_map.blocks
-- Expected: count = 7; slugs include all from CONTEXT.md D-23
-- ───────────────────────────────────────────────────────────
SELECT COUNT(*) AS block_count FROM economy_map.blocks;
SELECT slug, tier, sort_order FROM economy_map.blocks ORDER BY sort_order;

-- ───────────────────────────────────────────────────────────
-- D-25 bullet 3 (a): Append-only UPDATE violation on body_md
-- Expected: ERROR containing 'append-only'
-- ───────────────────────────────────────────────────────────
DO $$
BEGIN
    BEGIN
        UPDATE economy_map.block_body_versions
           SET body_md = 'mutated'
         WHERE id = (SELECT id FROM economy_map.block_body_versions LIMIT 1);
        RAISE EXCEPTION 'TEST FAILED: append-only violation was not blocked';
    EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'PASS: %', SQLERRM;
    END;
END $$;
```

**Use the in-tree `DO $$ … END $$;` block pattern** from `004_core_tables.sql` lines 241–256 (the only existing example of a deferred-exception PL/pgSQL block in the repo) — adapted for trapping `EXCEPTION WHEN OTHERS THEN` and emitting `RAISE NOTICE` so the result is visible in psql / Supabase MCP output.

**004 lines 241–256 (the structural analog for wrapping risky SQL in PL/pgSQL with exception handling):**
```sql
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'predictions_spotlight_id_fkey'
          AND table_name = 'predictions'
    ) THEN
        BEGIN
            ALTER TABLE predictions
                ADD CONSTRAINT predictions_spotlight_id_fkey
                FOREIGN KEY (spotlight_id) REFERENCES spotlight_history(id);
        EXCEPTION WHEN others THEN
            NULL; -- safe: spotlight_history may not exist if 002 hasn't run yet
        END;
    END IF;
END $$;
```

**Anon-key RLS probe (D-25 bullet 5)** is **not** SQL — it requires an HTTP request with the anon key. The planner should either (a) include a `curl` invocation as a comment block in `02-VERIFY.sql` and capture the output in `02-VERIFY-RESULTS.md`, or (b) use the Supabase MCP `execute_sql` tool with appropriate role switching. Both are valid; the planner picks.

---

### `.planning/phases/02-economy-map-schema-seven-block-seed/02-VERIFY-RESULTS.md` (verification-results doc)

**Analog (partial):** `.planning/phases/01-render-stack-diagnostic/01-VERIFICATION.md` (60+ lines read; uses YAML front-matter, "Observable Truths" + "Required Artifacts" + "Requirements Coverage" + "Critical Invariants" tables)

**Phase 1 front-matter (lines 1–7 — copy this shape):**
```markdown
---
phase: 01-render-stack-diagnostic
verified: 2026-05-26T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 1: Render-Stack Diagnostic — Verification Report
```

**Phase 1 "Observable Truths" table (lines 18–26 — structural model; copy header + adapt rows):**
```markdown
| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Findings report names the service/container/framework … | VERIFIED | `01-FINDINGS.md` §1 (lines 17–114): names `web` service, … |
| 2 | … | VERIFIED | … |
```

**Phase 1 "Critical Invariants" table (lines 53–60):**
```markdown
| Invariant | Check | Result |
|-----------|-------|--------|
| Zero app code changes since phase-start commit | `git diff --name-only 36894de..HEAD \| grep -v '^\.planning/'` | Empty — PASS |
| `01-FINDINGS.md` exists with 5 sections | `grep -cE '^## [1-5]\. ' 01-FINDINGS.md` | 5 — PASS |
```

**Differences for Phase 2:**

- The "evidence" column in Phase 1 cited file:line ranges. **Phase 2's "evidence" column cites SQL query results** captured from running `02-VERIFY.sql`. Each cell of the table contains the output snippet (e.g. `block_count = 7`, `ERROR: block_body_versions.body_md is append-only`).
- One row per D-25 sub-bullet (5 rows total — bullets 1–5).
- A second table for **"Trigger fire log"** capturing each `RAISE EXCEPTION` raised during the append-only tests (the exact `SQLSTATE` and message — the grep-friendly substrings the verification asserts on).
- A **"Anon-key probe results"** section recording the HTTP status code and row count returned when `Accept-Profile: economy_map` is sent with the anon key against `/rest/v1/blocks`, `/rest/v1/block_body_versions`, `/rest/v1/timeline_entries`.

**Critical Invariants section for Phase 2** should also reference D-04 (this migration **establishes** the in-tree isolation precedent for future `eu_ai_act`-style migrations) and D-10 (this migration **establishes** the in-tree append-only-via-trigger precedent). Both invariants are validated by inspecting the migration file's content (greppable for `CREATE SCHEMA economy_map`, `CREATE TYPE economy_map.maturity AS ENUM`, `CREATE TRIGGER … BEFORE UPDATE OR DELETE`).

---

## Shared Patterns

### `IF NOT EXISTS` idempotency (universal)

**Source:** `004_core_tables.sql` (every `CREATE TABLE`, every `CREATE INDEX`)
**Apply to:** All `CREATE TABLE`, `CREATE INDEX`, `CREATE SCHEMA` in `033_economy_map_schema.sql`.

```sql
CREATE SCHEMA IF NOT EXISTS economy_map;
CREATE TABLE IF NOT EXISTS economy_map.blocks (…);
CREATE INDEX IF NOT EXISTS idx_blocks_tier ON economy_map.blocks(tier);
```

Note: `CREATE TYPE … AS ENUM` does NOT support `IF NOT EXISTS` directly — for replay safety, wrap in a `DO $$` block following the pattern from `004` lines 241–256:

```sql
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace WHERE t.typname = 'maturity' AND n.nspname = 'economy_map') THEN
        CREATE TYPE economy_map.maturity AS ENUM ('nascent','emerging','contested','consolidating','mature');
    END IF;
END $$;
```

Same for `CREATE TRIGGER` and `CREATE POLICY` (use `DROP … IF EXISTS` first, as 006 does for policies, e.g. line 38: `DROP POLICY IF EXISTS newsletters_anon_read ON newsletters;`).

---

### Service-role bypass posture (universal in this repo)

**Source:** `006_rls_policies.sql` lines 1–9 strategy comment
**Apply to:** The migration's RLS strategy comment at the top of the RLS section.

The agents already use `SUPABASE_SERVICE_KEY` which bypasses RLS — Phase 2's migration does NOT change this posture; it inherits it. The append-only triggers (D-10) are the **only** mechanism that binds service_role.

---

### Inline column comments for non-obvious fields

**Source:** `004_core_tables.sql` (whole file — examples on every column)
**Apply to:** All three `economy_map` tables.

Example pattern from 004 line 14:
```sql
source_tier     INTEGER DEFAULT 3,                          -- 1=authority, 2=curated, 3=community
```

For `economy_map.blocks`, line up the `-- comment` markers to a consistent column for readability. CONTEXT.md D-23 provides the comment text for each block field (subtitle captions etc.).

---

## No Analog Found

| File | Role | Reason | Planner should use |
|------|------|--------|--------------------|
| `02-VERIFY.sql` | verification SQL | No prior SQL exercise scripts in `supabase/` or `scripts/` | CONTEXT.md D-25 directly; structure as labeled blocks per sub-bullet |
| `CREATE SCHEMA economy_map` (sub-pattern) | DDL | First in-tree schema other than `public` | Invent — `CREATE SCHEMA IF NOT EXISTS` + `GRANT USAGE` on the three roles |
| `CREATE TYPE economy_map.maturity AS ENUM` (sub-pattern) | DDL | Repo encodes enums as `TEXT NOT NULL CHECK (col IN (…))` everywhere; this migration breaks from that style per D-03 | Invent — straight `CREATE TYPE … AS ENUM`, wrapped in a `DO $$` existence check for replay safety |
| Append-only triggers (sub-pattern) | trigger function + trigger | No `CREATE TRIGGER`, `BEFORE UPDATE`, `BEFORE DELETE`, or `RAISE EXCEPTION` anywhere in the migrations | Invent — see §6 above. **Loud comment block MANDATORY** (D-14). |

---

## Metadata

**Analog search scope:** `supabase/migrations/*.sql` (33 files, `001`–`032`), `scripts/`, `docker/web/site/app.js`, `docker/processor/*.py`, `docker/newsletter/*.py`, `docker/gato_brain/*.py`
**Files scanned:** 33 migrations + 3 application directories
**Grep queries run:** `CREATE SCHEMA`, `CREATE TRIGGER`, `BEFORE UPDATE`, `BEFORE DELETE`, `RAISE EXCEPTION`, `CREATE TYPE.*AS ENUM`, `append.only`, `append_only`, `eu_ai_act`, `economy_map`, `schema(`, `Accept-Profile`
**Pattern extraction date:** 2026-05-26
**Phase:** 02-economy-map-schema-seven-block-seed
