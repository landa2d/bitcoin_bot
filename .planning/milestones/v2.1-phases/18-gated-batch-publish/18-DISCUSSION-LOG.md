# Phase 18: Gated Batch Publish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-09
**Phase:** 18-gated-batch-publish
**Areas discussed:** Hub intro in prod, Deploy + live verify (Batch mechanism + Ordering/recovery delegated to Claude's Discretion)

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Hub intro in prod | Published hub body as the #/map intro vs HUB_STORYLINE constant | ✓ |
| Batch publish mechanism | Telegram batch command vs script vs 8× /map-approve | (delegated) |
| Ordering & failure recovery | Order + halt/continue on mid-batch failure | (delegated) |
| Deploy + live verify | Deploy sequencing + post-publish verification | ✓ |

**Notes:** Operator chose to discuss the hub render and deploy/verify; delegated the batch mechanism and failure recovery to Claude's Discretion.

---

## Hub intro in prod

| Option | Description | Selected |
|--------|-------------|----------|
| Published hub body | Ungate the hub fetch so prod renders the published agent-economy body as the intro; HUB_STORYLINE becomes pre-publish fallback | ✓ (refined) |
| Keep HUB_STORYLINE | Don't render the hub body in prod; publish only the 7 blocks | |
| You decide | Default to published hub body | |

**User's choice:** Free-text — "I want the hub body to be an actual article, not an intro to the 7 blocks, but the most important article that frames the agent economy, and then users can deep dive into the different pillars, and if one of the pillars evolve then this main article evolves as well, and then I want historical versions of this article stored for later views."

**Notes:** Reflected back and split into scope:
- **In scope (Phase 18):** render the *published* hub body as a first-class framing article at `#/map` (article-first, pillars as deep-dive cards).
- **Already supported:** version *storage* — `block_body_versions` is append-only, every version retained.
- **Deferred (new capabilities):** hub-article auto-evolution on pillar change (pipeline → future backend milestone); a historical-version *viewer* (future frontend).

Follow-up — render shape:

| Option | Description | Selected |
|--------|-------------|----------|
| Article, drop pillar list | Render the published hub article but trim the duplicative Tier-1/Tier-2 prose pillar-list (reuse trimHubBody); cards are the deep-dive (HUB-01) | ✓ |
| Full article, keep everything | Render the entire body untrimmed; pillars appear twice (prose links + cards) | |
| You decide | Default to article-drop-pillar-list | |

**User's choice:** Article, drop pillar list.

---

## Deploy + live verify

### Sequencing

| Option | Description | Selected |
|--------|-------------|----------|
| Deploy first, then publish | Ship new app.js (no-op pre-publish), verify, then the gated publish batch is the single go-live | ✓ |
| Publish first, then deploy | Blocks go live on the old app.js, then deploy brings the hub article live | |

**User's choice:** Deploy first, then publish.

### Verification gate

| Option | Description | Selected |
|--------|-------------|----------|
| Operator walk + programmatic | Programmatic published-content/cross-link check AND operator manual live-site click-through | |
| Programmatic only | Automated published-content + cross-link assertion against the live anon read; no manual walk | ✓ |
| Operator walk only | Manual live-site click-through only | |

**User's choice:** Programmatic only.
**Notes:** The human gate is the operator's approval of the publish batch + the Phase-17 preview click-through already completed on content-identical drafts — so a separate live manual walk is redundant.

---

## Claude's Discretion

- **Batch publish mechanism (D-06):** standalone operator-approved batch script looping the existing `publish_block_version` RPC over the 8 open drafts (not a gato_brain command — avoids a v2.1-excluded agent-service change; mirrors the Phase-16 loader). Single approval gate via a confirmation manifest; idempotent.
- **Ordering & recovery (D-07/D-08):** publish 7 blocks first, hub last; fail-loud halt-and-report on any per-block failure; pre-flight verifies all 8 drafts exist; idempotent re-run completes a halted batch.
- Script CLI/manifest shape, the `loadHub`/`renderHub` published-body code shape, and whether D-05 verification extends the existing harness — all planner's call within the locked decisions.

## Deferred Ideas

- Hub-article auto-evolution when a pillar changes (synthesis/pipeline → future backend milestone).
- Historical-version viewer on the site (data already stored append-only; only the viewer is new → future frontend phase).
- Richer hub-article content authoring (re-synthesis / canonical-body-rewrite), separate from the publish mechanics.
- Reviewed-not-folded: carried-forward backend v1.0 todos (analyst predictions title-expire, soft-cap hardening, pay-endpoint E2E, phase-05 intake follow-ups, research trigger permissions) — out of v2.1 content scope, parked in backlog.
