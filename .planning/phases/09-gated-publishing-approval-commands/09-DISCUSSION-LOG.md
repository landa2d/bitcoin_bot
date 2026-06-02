# Phase 9: Gated Publishing + Approval Commands - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-02
**Phase:** 9-gated-publishing-approval-commands
**Areas discussed:** Watermark semantics, Owner gate, Re-render trigger, Response UX

---

## Watermark semantics (last_synthesized_at)

| Option | Description | Selected |
|--------|-------------|----------|
| Amend RPC → synthesized_from_through | New migration sets last_synthesized_at from the draft's synthesized_from_through, closing the IN-04 double-count/skip gap | ✓ |
| Keep NOW(), accept the gap | Ship RPC as-is; document the window | |
| Amend RPC + also fold WR-01 unique-draft index | Watermark + the deferred duplicate-draft UNIQUE index in one migration | |

**User's choice:** Amend RPC → synthesized_from_through (Recommended)
**Notes:** WR-01 stays deferred to Phase 10 (D-01a). Migration is watermark-only, number 038.

---

## Owner gate

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse access_tier == 'owner' | Gate writes on the existing ensure_user owner tier; no new config | ✓ |
| Dedicated owner Telegram ID env var | New OWNER_TELEGRAM_ID compared against req.user_id | |
| Gate ALL /map-* commands to owner | Extend gating to the read commands too | |

**User's choice:** Reuse access_tier == 'owner' (Recommended)
**Notes:** Read commands (/map-status, /map-pending) stay ungated as in Phase 6 (D-02a).

---

## Re-render trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Rely on existing 60s idle poll | publish flips status; Phase 4 idle poll renders within ~60s, no new coupling | ✓ |
| Explicit re-render trigger on approve | gato_brain kicks the render path immediately after publish | |

**User's choice:** Rely on existing 60s idle poll (Recommended)
**Notes:** Confirmation copy tells the operator the page renders within ~60s.

---

## Response UX

| Option | Description | Selected |
|--------|-------------|----------|
| Rich confirm + explicit typed errors | Maturity-transition + URL on success; distinct messages for not-owner / bad UUID / RPC not-found-or-not-draft / generic | ✓ |
| Minimal confirm + passthrough errors | Short "✓ approved/rejected"; errors via the existing Command failed: <e> path | |

**User's choice:** Rich confirm + explicit typed errors (Recommended)
**Notes:** Concurrent double-approve safely surfaces as the RPC not-found/not-draft case (single-winner property), never a double-publish.

---

## Claude's Discretion

- Exact confirmation/error string wording and emoji (all D-05 cases must remain distinct).
- Separate handlers vs one parametrized helper; name/signature of the new RPC-POST helper.
- GATE-01 verification approach (test and/or inspection).
- Precise SQL form of the migration-038 watermark amendment.

## Deferred Ideas

- WR-01 duplicate-draft UNIQUE partial index → Phase 10 (when manual /map-synth makes concurrency plausible).
- Manual /map-synth, unsorted reassignment, live_tension editing, forced re-synthesis → Phase 10.
- Bespoke per-draft approval card UI → out of scope; /map-pending is the approval surface.
