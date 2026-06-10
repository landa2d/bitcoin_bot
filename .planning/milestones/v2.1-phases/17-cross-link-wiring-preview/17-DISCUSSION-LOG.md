# Phase 17: Cross-link Wiring & Preview - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-08
**Phase:** 17-cross-link-wiring-preview
**Areas discussed:** Preview mechanism, Link + scope rigor

---

## Gray-area selection

| Area | Description | Selected for deep-dive |
|------|-------------|------------------------|
| Preview mechanism | How/where to verify draft content given anon RLS hides drafts + NULL `current_body_version_id` | ✓ |
| Hub duplication (HUB-01) | Hub body lists 7 blocks as prose links; cards duplicate them | (default recorded) |
| Nascent treatment | Distinct visual treatment vs pill-only | (default recorded) |
| Link + scope rigor | LINK-01 verification bar + SC#4 content-scoped boundary | ✓ |

**User's choice:** Preview mechanism, Link + scope rigor.
**Notes:** Hub-duplication and Nascent left to recorded Claude's-discretion defaults (cards + code-trim; pill-only). Operator invited to override either; none requested.

---

## Preview mechanism

### Q1 — Where preview runs / how it reads drafts

| Option | Description | Selected |
|--------|-------------|----------|
| Local-private elevated | Local `agentpulse-web` on the branch with a draft-reading credential + a preview render path; live site untouched | ✓ |
| Live bannered preview route | Mirror newsletter migration 028 (`status='preview'` + anon RLS + banner) on the public site | |
| Static offline render | Render markdown into a tokens-preview.html-style static page | |

**User's choice:** Local-private elevated.
**Notes:** Best honors the spine — drafts never touch the public site.

### Q2 — Local read credential

| Option | Description | Selected |
|--------|-------------|----------|
| service_role, local-only | Substitute service_role for anon in the LOCAL container only (entrypoint sed); guarded by branch + /diff; never ships | ✓ |
| Temporary preview RLS policy | Scoped authenticated/preview RLS + JWT, dropped after | |
| You decide | Planner pins the credential | |

**User's choice:** service_role, local-only.
**Notes:** No schema/RLS change; reversible; nothing new deploys. Risk contained to a throwaway local container.

### Q3 — Draft-body render path (current_body_version_id is NULL pre-publish)

| Option | Description | Selected |
|--------|-------------|----------|
| Read-only draft fetch | When current_body_version_id NULL, fetch latest status='draft' body + marked.parse; no DB writes; no-op for prod anon | ✓ |
| Point current_body_version_id at draft | Temporarily UPDATE blocks to point at the draft, then revert | |
| You decide | Planner pins the query/gating | |

**User's choice:** Read-only draft fetch.
**Notes:** Fully reversible; RLS makes it a prod no-op.

### Q4 — Preview gating + ship posture

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit flag, ships dormant | Gate behind a preview flag set only locally; code ships dormant in prod (double-safe) | ✓ |
| Local-only, nothing ships | Preview code stays on a local branch, never merged | |
| You decide | Planner picks | |

**User's choice:** Explicit flag, ships dormant.
**Notes:** One reviewable /diff; content-scoped; reusable for future previews.

---

## Link + scope rigor

### Q1 — LINK-01 verification bar

| Option | Description | Selected |
|--------|-------------|----------|
| Exhaustive + fail-loud | Extract every `#/map/<slug>` href, assert each target ∈ roster (fail-loud), + manual click-through full set on preview | ✓ |
| Automated extraction only | Extract + assert programmatically; skip manual clicking | |
| Spot-check sample | Manually click the hub's 7 + a few cross-links | |

**User's choice:** Exhaustive + fail-loud.
**Notes:** 22 cross-link instances, all in-roster; assertion guards future drift; last gate before publish.

### Q2 — SC#4 scope boundary

| Option | Description | Selected |
|--------|-------------|----------|
| Confirm in-bounds set | Hub marked.parse intro (replacing HUB_STORYLINE w/ fallback) + read-only draft-fetch + code-trim hub prose list + dormant flag; reuse templates/router | ✓ |
| Tighter — trim via doc edit | Same set but resolve HUB-01 by editing 00-hub.md + reloading via rewrite path | |
| You decide | Planner pins the in/out set + hub-trim mechanism | |

**User's choice:** Confirm in-bounds set.
**Notes:** Hub block-list trimmed IN CODE; loaded draft left untouched. Out-of-bounds: new components/routes/restyle/nav, distinct nascent treatment.

---

## Claude's Discretion

- **HUB-01:** render hub intro (thesis + two-tier framing, optionally the closing "thesis, restated") + cards; code-trim the hub's prose block-list so it isn't duplicated. Cards preferred (EXECUTION_BRIEF §2/§5). Planner pins the exact cut-points.
- **Nascent maturity:** pill-only, no distinct visual treatment (REQUIREMENTS deferred default).
- Exact preview-flag form (URL param vs hash) + which routes it covers — planner.

## Deferred Ideas

- Phase 18 (PUB-01): gated batch publish via the publish RPC + web-only scoped deploy.
- Distinct nascent visual treatment beyond the pill — future styling pass.
- HUB-01 via source-doc edit — the rejected alternative, noted for a future content cleanup.
- EU AI Act tracker → `regulation-legal` body — future milestone (EUAI-01/02).
- Evolution timeline content — intake fills weekly; no manual authoring this milestone.
- 7 pending v1.0 backend todos — reviewed, none overlap; parked in ROADMAP backlog.
