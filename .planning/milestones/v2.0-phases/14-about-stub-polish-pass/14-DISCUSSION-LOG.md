# Phase 14: About Stub + Polish Pass - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-05
**Phase:** 14-about-stub-polish-pass
**Areas discussed:** About copy depth, Vertical rhythm, Radius normalization, Deploy + UAT scope

---

## About copy depth

### How rich should the About stub be?

| Option | Description | Selected |
|--------|-------------|----------|
| Mockup copy + agent pills | Full mockup About: eyebrow + title + page-sub + 3 paragraphs + 5-agent pill row | ✓ |
| Prose-only (no pills) | Mockup's 3 paragraphs + page-sub, drop the agent-pill row | |
| Minimal finalize | Keep current single lede, just finalize 2-3 sentences | |

**User's choice:** Mockup copy + agent pills
**Notes:** Agent pills are static content (not the deferred pipeline diagram), so they fit "stub with existing copy" and "minimalist but not sparse." Agent-pill CSS is net-new (mockup-only today) — must be ported into the design-system tokens.

### Use the mockup's About copy verbatim, or reconcile it to the actual architecture?

| Option | Description | Selected |
|--------|-------------|----------|
| Verbatim mockup copy | Ship the mockup's exact wording — 5 curated pills + 3 paragraphs | |
| Reconcile to real system | Adjust copy/pills to reflect the true 8-service roster | ✓ |
| You decide / draft it | Claude drafts, lightly corrected for accuracy | |

**User's choice:** Reconcile to real system
**Notes:** The mockup simplifies to 5 agents and is inaccurate vs. the actual 8 services; the About copy must be factually correct.

### How should the agent-pill roster reflect the real 8 services?

| Option | Description | Selected |
|--------|-------------|----------|
| All 8 as pills | One pill per service (Gato, Gato Brain, Processor, Analyst, Newsletter, Research, LLM Proxy, Web) | |
| Content agents + infra line | Pills for the 5 content agents + one prose sentence for the supporting layer | ✓ |
| You decide / draft it | Claude drafts the accurate roster + prose | |

**User's choice:** Content agents + infra line
**Notes:** 5 content-producing-agent pills (Processor/Analyst/Research/Newsletter/Gato) + one accurate prose sentence covering Gato Brain (routing), LLM Proxy (budget/wallet), Web. Keeps the grid tight while staying truthful; avoids an architecture doc.

---

## Vertical rhythm

### How aggressive should the vertical-rhythm tightening be?

| Option | Description | Selected |
|--------|-------------|----------|
| Noticeable / denser | Meaningfully tighten section + card + element gaps | |
| Subtle / one notch | Drop only the largest section gaps by ~one step | |
| You decide / UI-SPEC | Defer exact degree to the UI-SPEC; lock only the direction | ✓ |

**User's choice:** You decide / UI-SPEC
**Notes:** Direction locked — tighter, token-anchored (4px-grid `--space-*`), site-wide, not sparse. Exact magnitude (which gaps drop by how much) deferred to UI-SPEC/planner.

---

## Radius normalization

### What should the three off-grid 6px radii snap to?

| Option | Description | Selected |
|--------|-------------|----------|
| Role-appropriate tokens | Input → --radius-sm (7px), buttons → --radius-btn (8px) | ✓ |
| Uniform 7px | All three subscribe-form elements → --radius-sm (7px) | |
| You decide / UI-SPEC | Lock only "all radii in the 7–10px token set" | |

**User's choice:** Role-appropriate tokens
**Notes:** Matches how inputs/buttons are radiused everywhere else. Sweep confirms the 3 subscribe-form `6px` values (`style-shared.css:765/808/852`) are the only off-token radii.

---

## Deploy + UAT scope

### Should the live deploy + batch browser-UAT verification be part of Phase 14, or a separate step after?

| Option | Description | Selected |
|--------|-------------|----------|
| Separate ship step after | Phase 14 = code + local/in-code verification; live rebuild + batch UAT is a distinct operator-approved step after | ✓ |
| Folded into Phase 14 | Phase 14's final task runs the scoped rebuild to live + verifies UAT | |
| You decide | Claude picks + records rationale | |

**User's choice:** Separate ship step after
**Notes:** Honors standing deploy discipline (scoped + approved + boundary-stop, verify a real rendered result, never auto-advance). Decouples code delivery from the prod cutover. The accumulated 11/12/13/14 HUMAN-UAT items are walked against the live site during that separate ship step.

---

## Claude's Discretion

- Vertical-rhythm tightening **magnitude** — handed to the UI-SPEC/planner within the token system (direction locked).
- Exact About **copy wording** (reconciled prose + pill roles + infra sentence) — Claude drafts in the mockup's spirit, corrected for accuracy; operator reviews in the plan/UI-SPEC.
- File organization of new About + agent-pill CSS — mechanical planner discretion (hand-authored CSS, cascade-order convention).

## Deferred Ideas

- Richer About page with the pipeline diagram (ABOUT-02) → v-next.
- Dark mode (DARK-01) → v-next.
- The live deploy + batch browser-UAT verification → a separate operator-approved ship step AFTER Phase 14 (deliberately decoupled, per D-06).
