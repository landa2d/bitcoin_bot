# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Agent Economy Map

**Shipped:** 2026-06-04
**Phases:** 11 (1–10 + 4.1) | **Plans:** 29 | **Tasks:** 46

### What Was Built
- An autonomous-intake, human-gated **living-reference surface** on `aiagentspulse.com`: isolated append-only `economy_map` schema (seven seeded blocks), design tokens, and hub/block/status renderers with a 60s live-on-insert poll.
- The **autonomous editorial spine**: newsletter→timeline intake classifier, per-block Sonnet synthesis loop, deterministic validation sentinels, and the atomic publish/reject autonomy boundary.
- A complete **Telegram operator control surface**: read-only (`/map-status`, `/map-pending`) and write commands (`/map-approve`, `/map-reject`, `/map-assign`, `/map-entry`, `/map-synth`, `/map-tension`).
- DB-based **llm-proxy governance** (caps, fail-loud cap-missing, cross-provider downgrade).

### What Worked
- **Structural over application enforcement** — append-only triggers, partial UNIQUE indexes, and SECURITY DEFINER RPCs (with pinned `search_path`) held the integrity boundary against `service_role`, the historical failure actor. RLS was deliberately never the gate.
- **Fail-loud governance** — every consequential path (wallet, synth requests, classify) halts loudly or records a queryable terminal status; "never a silent drop" caught real bugs in review.
- **Fix review blockers before verification** — fixing data-loss/fail-loud/structural findings inline (rather than deferring to `--gaps`) kept phases genuinely done at close. Validated again in Phase 10 (CR-01/WR-01..04 fixed pre-verify).
- **Scoped, approved deploys** — single-service `docker compose up -d --build <svc>` + drift-check, with operator approval at the prod boundary, avoided the blast radius of blind full deploys.

### What Was Inefficient
- **Prod drifted far behind main**, forcing a whole interstitial phase (4.1) to reconcile before Phase 5 could ship safely.
- **A latent OpenClaw command-forwarding allowlist bug** silently blocked the entire `/map-*` surface from reaching gato_brain over Telegram — undetected until Phase 9 because nothing exercised it end-to-end.
- **Human-smoke verification accumulated** — UAT/verification items across Phases 2, 4, 9, 10 stayed `human_needed` (single-operator Telegram bot; can't be automated), and were acknowledged as deferred at close rather than run.
- **GSD execution friction** — worktree isolation is unsafe for scoped-rebuild plans (rebuild cmd cds to the absolute main-tree path → stale builds); executors can't run gsd-sdk so they hand-edit STATE; both needed manual orchestrator compensation.

### Patterns Established
- `economy_map` access via **direct PostgREST** with `Accept-Profile`/`Content-Profile` headers — never supabase-py `.in_()`/`.schema()`/`.rpc()` (silent-failure rule).
- **SECURITY DEFINER write-RPC boilerplate**: `SET search_path = economy_map, public` + `REVOKE ALL FROM PUBLIC` + `GRANT EXECUTE TO service_role`, typed params only, `CREATE OR REPLACE` full-body re-emit.
- **Append-only trigger with lifecycle-column exemption**: content columns pinned via `IS DISTINCT FROM → RAISE`, only lifecycle columns left mutable.
- **Block pipeline** (A→prepass→B→C→D→E) for fabrication-free newsletter synthesis.
- **Migrations applied live via Supabase MCP `apply_migration`** (ref `zxzaaqfowtqvmsbitqpu`), not `supabase db push`; the orchestrator owns the apply at a human-gated checkpoint.

### Key Lessons
1. End-to-end command wiring (OpenClaw allowlist → gato_brain dispatch) must be exercised per surface — unit tests passed while the whole `/map-*` path was dead over Telegram.
2. Keep prod current with main continuously; a single large reconciliation is expensive and risky.
3. For this repo, run scoped-rebuild / live-migration phases **no-worktree, sequential**, with the orchestrator owning the prod actions (migration apply, STATE/ROADMAP writes).
4. Human-smoke verification is a standing cost for a single-operator Telegram product — budget for it or accept it as tracked-deferred explicitly.

### Cost Observations
- Model mix: predominantly **Opus** (orchestrator + executors), **Sonnet** for verification/synthesis, minimal Haiku.
- Notable: parallel-plan waves were mostly serialized in practice because consequential prod actions (migrations, rebuilds) gate on operator approval and a shared Docker daemon.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Key Change |
|-----------|--------|------------|
| v1.0 | 11 | Established the autonomy-boundary spine (intake autonomous, publish gated) and structural-enforcement discipline; introduced no-worktree execution for prod-touching phases. |

### Cumulative Quality

| Milestone | Tests | Zero-Dep Additions |
|-----------|-------|--------------------|
| v1.0 | per-phase pytest suites (intake, synthesis, gated-publishing, command handlers) | All phases added no new runtime dependencies beyond the existing stack. |

### Top Lessons (Verified Across Milestones)

1. Structural enforcement (triggers/RLS/RPC) beats application-layer checks — `service_role` bypasses RLS.
2. Fail loud on missing inputs; never silently default to a no-op ("the wallet bug").
