---
phase: 15
slug: inventory-roster-reconciliation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-08
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **This is a no-write documentation/reconciliation phase.** There is no application
> code to unit-test. "Validation" here means *checkable acceptance of the documented
> contract facts against the in-tree source* (deterministic `grep`/`sed` assertions
> over the migration SQL + `app.js`) **plus operator review** of the four ROADMAP
> success criteria. Source: `15-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None for this phase (no executable deliverable). Repo runner is `pytest` (`tests/`), not exercised here. |
| **Config file** | none — no Wave 0 install needed |
| **Quick run command** | `grep`/`sed` assertions against `supabase/migrations/033_*.sql`, `039_*.sql`, `041_*.sql`, and `docker/web/site/app.js` (see map below) |
| **Full suite command** | Manual operator review of the reconciliation plan + the four success criteria (ROADMAP § Phase 15 SC 1–4) |
| **Estimated runtime** | ~1 second (assertions) + operator review |

---

## Sampling Rate

- **After each artifact (contract doc / reconciliation plan):** run the `grep` assertions in the map below — each is <1s and deterministic.
- **Phase gate (before Phase 16):** operator reviews the documented contract + the per-slug disposition table against ROADMAP SC 1–4.
- **Max feedback latency:** <1s for the automated assertions.

---

## Per-Requirement Verification Map

> Task IDs are assigned by the planner; rows here key on requirement / success criterion.
> All assertions are read-only against in-tree source — **no DB write, no migration applied in Phase 15.**

| Requirement | Behavior to confirm | Test Type | Automated Command | Status |
|-------------|---------------------|-----------|-------------------|--------|
| INV-01 / SC#1 | `blocks` columns + 3-tier CHECK documented from live SQL | assertion | `grep -n "CHECK (tier IN ('substrate','behavior','frame'))" supabase/migrations/033_economy_map_schema.sql` | ⬜ pending |
| INV-01 | append-only triggers guard `block_body_versions` + `timeline_entries` only (not `blocks`) | assertion | `grep -nc "CREATE TRIGGER" supabase/migrations/033_economy_map_schema.sql` → 2; no trigger `ON economy_map.blocks` | ⬜ pending |
| INV-01 | publish RPC is atomic, service_role-only, current body = migration 039 | assertion | `grep -n "GRANT EXECUTE ON FUNCTION economy_map.publish_block_version" supabase/migrations/039_publish_block_version_null_guard.sql` | ⬜ pending |
| INV-01 | anon sees only `status='published'` bodies | assertion | `grep -n "status = 'published'" supabase/migrations/033_economy_map_schema.sql` | ⬜ pending |
| INV-01 | hub via hardcoded `HUB_STORYLINE`; blocks via `marked.parse` gated to published | assertion | `grep -n "HUB_STORYLINE\|marked.parse" docker/web/site/app.js` | ⬜ pending |
| INV-02 / SC#2 | enum = nascent/emerging/contested/consolidating/mature; `building` absent; emerging→2; unknown→1 | assertion | enum: `grep -n "CREATE TYPE economy_map.maturity" supabase/migrations/033_economy_map_schema.sql`; pill: `grep -n "MATURITY_STAGE" docker/web/site/app.js`; confirm no `building` member | ⬜ pending |
| ROST-01 / SC#3 | regulation-legal seeded frame@7; negotiation NOT seeded; `ON CONFLICT (slug) DO NOTHING` | assertion | `grep -n "regulation-legal\|negotiation-coordination\|ON CONFLICT (slug) DO NOTHING" supabase/migrations/033_economy_map_schema.sql` | ⬜ pending |
| ROST-01 | reconciliation plan resolves all 8 slugs + hub with explicit disposition; reshuffle map collision-free {1..8} | review | per-slug disposition table present; before/after sort_order yields 8 distinct contiguous values | ⬜ pending |
| SC#4 | reconciliation plan presented for operator approval BEFORE any write | gate | plan is the deliverable; Phase 15 writes nothing to `economy_map` (no migration ≥043 applied, no PostgREST write) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase validation — no test file, fixture, or framework install needed for this no-write documentation phase. The validation is assertion-of-documented-facts (`grep` above) plus operator review of the four success criteria.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Reconciliation plan presented & approved before any Phase 16 write | SC#4 | The "read before writing, I approve" gate (EXECUTION_BRIEF §0) is an operator decision, not automatable | Operator reads the per-slug disposition table + documented contract, confirms it matches the four ROADMAP SCs, and explicitly approves before Phase 16 loads anything |
| Doc-consistency flag F-2 acknowledged | INV-02 | ROADMAP SC#2 / Phase-17 wording predates the D-01 remap (says `building`; renders `emerging`) | Operator confirms the substrate pills (slugs 1/2/3) are expected to read `emerging` (stage 2), not `building` |

---

## Validation Sign-Off

- [ ] All requirements have an `<automated>` grep assertion or a documented manual-review gate
- [ ] Sampling continuity: assertions are <1s, run per artifact
- [ ] Wave 0 covers all MISSING references — N/A (no code)
- [ ] No watch-mode flags
- [ ] Feedback latency < 1s for automated assertions
- [ ] `nyquist_compliant: true` set in frontmatter (executor flips after assertions pass)

**Approval:** pending
