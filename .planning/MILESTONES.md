# Milestones

## v1.0 Agent Economy Map (Shipped: 2026-06-04)

**Phases completed:** 11 phases (1–10 + 4.1), 29 plans, 46 tasks
**Timeline:** 2026-02-05 → 2026-06-04
**Known deferred items at close:** 14 (see STATE.md → Deferred Items → "Acknowledged at v1.0 close") — manual live-smoke UAT/verification + known follow-up todos; no blocking gaps.

**Delivered:** The Agent Economy Map — an autonomous-intake, human-gated living-reference surface on `aiagentspulse.com` plus a full Telegram operator control surface, preserving the spine throughout (intake autonomous, publishing gated; append-only data; sentinels flag-never-block; all LLM calls via `llm-proxy:8200`; all `economy_map` access via direct PostgREST).

**Key accomplishments:**

- **Schema + visible surface (Phases 1–4):** Diagnostic-confirmed reuse of the existing SPA + Caddy publish path; isolated append-only `economy_map` schema with seven seeded blocks; design-token CSS (tier accents, maturity pills, fixed timeline format); and the hub / block-page / status renderers in `app.js` with a visibility-aware 60s live-on-insert poll.
- **Governance baseline (Phase 4.1):** File→DB llm-proxy governance migration (034) with a fail-loud three-way cap contract + cross-provider downgrade, and a prod↔main reconciliation establishing a clean deploy baseline.
- **Autonomous intake (Phase 5):** A scheduled poller that classifies tier-1 newsletter events via the proxy-routed DeepSeek classifier, routes below-floor/error to `unsorted`, and INSERTs source-traceable, idempotent, append-only timeline entries — never a silent drop.
- **Operator awareness (Phase 6):** Read-only `/map-status` + `/map-pending` Telegram commands over a GET-only `economy_map` wrapper.
- **Synthesis engine (Phase 7):** A per-block synthesis cycle drafting `block_body_versions` via a single Sonnet call with hot-reloadable identity, N/T trigger eligibility, and a no-draft guard.
- **Validation sentinels (Phase 8):** Deterministic tension/length/maturity/structure flags that annotate drafts (never block) and surface on the Telegram approval card.
- **The autonomy boundary (Phase 9):** Atomic `publish_block_version` / `reject_block_version` RPCs wired to owner-gated `/map-approve` + `/map-reject`, with the watermark advancing from the approved draft's `synthesized_from_through`.
- **Operator write commands (Phase 10):** Owner-gated `/map-assign`, `/map-entry`, `/map-synth`, `/map-tension` (migrations 040–042 + a 30s processor synth-drain), completing the editorial-framing control surface — force-synth bypasses N/T but never the open-draft / human-approval invariant.

---
