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

## Milestone: v2.0 — Frontend Redesign

**Shipped:** 2026-06-08
**Phases:** 4 (11–14) | **Plans:** 8 | **Tasks:** 16

### What Was Built
- A **UI-only redesign** of the public `aiagentspulse.com` SPA, deployed live via the scoped `agentpulse-web` cutover: a `style-base.css` :root design-token layer (single light-mode violet palette, Source Serif 4 / IBM Plex Mono), a persistent stateful 3-tab nav shell with `← Back` controls and route-derived active state, the Newsletter list/article restyled with a section-scoped Technical/Strategic toggle, the Agent Economy re-rendered as a responsive grouped card grid (`style-map.css` retired → 2-sheet cascade), and a real "What is AgentPulse" About page + a site-wide radius/spacing token sweep.
- Frontend-only — zero backend/pipeline/Supabase/content change; the dual-mode content logic was untouched (only the toggle's placement + styling moved).

### What Worked
- **Foundation-first discipline** (Phase 11 = the shared shell every later phase reused) mirrored v1.0 and paid off: phases 12–14 were pure restyle-on-tokens with no re-litigation of palette/typography.
- **Token-anchored verification gates** made CSS phases deterministically checkable — `grep` gates for "no raw-px radius / no off-grid spacing / no literal hex" turned subjective polish into pass/fail, and they re-ran cleanly verbatim at verify time.
- **Delete-and-fold** (Phase 13 retiring `style-map.css` into the shared sheet) shrank the cascade to 2 sheets without behavior change.
- **Non-destructive preview before the prod cutover**: replicating the entrypoint substitution into a temp dir + serving on a high port verified the substituted SPA boot + content over HTTP without a browser and without touching the live container — then the cutover was a clean image-swap.

### What Was Inefficient
- **Single-plan waves** (each Phase-14 wave had exactly one plan) gained nothing from worktree isolation; running them no-worktree-sequential avoided the known cleanup-SUMMARY-collision for zero parallelism loss — worth detecting earlier and defaulting.
- **No headless browser in the environment** meant the perceptual/visual UAT items (render quality, "minimalist but not sparse") could not be closed in-session; they correctly stayed as operator browser-walk items but mean the milestone closes with visual sign-off still pending.
- A crude `awk` window during verification false-flagged "interactive attrs" in the agent-row (bled into the shared subscribe section) — re-extracting the exact block resolved it, but a tighter boundary would have avoided the detour.

### Patterns Established
- **Substituted-preview + `--resolve` live-vhost verification** for the Caddy-served SPA (see the web-static-preview-substitution reference): verify served bytes + JS routing logic when no browser exists; verify the live TLS vhost with `curl --resolve domain:443:127.0.0.1` (SNI must equal the cert domain).
- **D-06 deploy-fenced phases**: frontend phases deliberately fence out the live deploy + browser-UAT so the whole milestone ships in one operator-approved batch cutover rather than per-phase.

### Key Lessons
- For CSS/HTML phases, **grep-able token gates are the unit of truth**; perceptual quality is a separate human gate that genuinely needs a browser — don't conflate them or let "not visually signed off" block a code-verified, deployed milestone.
- **Scope the deploy to the one changed service.** `agentpulse-web` maps `80/443`, so `compose up -d web` IS the public cutover — capture a rollback image ref, run `drift-check.sh` first (web-pending + the accepted lab-data-provider D-07 are the expected non-zero lines), build the image non-destructively, then swap.

### Cost Observations
- Model mix: **Opus** orchestrator + executors, **Sonnet** for phase verification + the code review. 4 phases executed in a single session resume → deploy → close chain.
- Notable: each wave was a single plan, so execution was inherently serial; the cost was dominated by the executor/verifier/reviewer subagents, not orchestration.

---

## Milestone: v2.1 — Agent Economy Content

> **Retrospective gap (acknowledged):** v2.1 (Phases 15–18, shipped 2026-06-09) was completed and its phases archived to `milestones/v2.1-phases/`, but it was never formally closed via `/gsd-complete-milestone` — no MILESTONES.md entry, no RETROSPECTIVE section, no `v2.1` git tag were generated (the operator ran `/gsd-new-milestone` to start v2.2 directly). The phase/roadmap/requirements artifacts are preserved (`milestones/v2.1-ROADMAP.md`, `milestones/v2.1-REQUIREMENTS.md`). A backfill of the v2.1 record is offered as a follow-up to the v2.2 close. **What shipped:** all 8 in-scope `economy_map` block bodies published live to `aiagentspulse.com/#/map` in one operator-approved batch (migration 043 + a standalone PostgREST loader + the atomic `publish_block_version` RPC), content-only, with `regulation-legal` kept deferred.

---

## Milestone: v2.2 — Landing Redesign + Signals Feed

**Shipped:** 2026-06-19
**Phases:** 7 (19–25) | **Plans:** 17 | **Tasks:** 24

### What Was Built
- A **second public-site redesign** of `aiagentspulse.com`, deployed live via gated scoped `agentpulse-web` rebuilds: the four top-level sections merged into ONE single-scroll landing with an `IntersectionObserver` scroll-spy nav (`app.js` two-mode router refactor) while editions/blocks stayed deep-linkable detail routes; two coexisting both-centered max-widths (`--measure`/`--wide`) killed the dead left gutter on a token-only color + section-rhythm baseline.
- The **four brief defects fixed**: edition-header de-dup (suffix stripped at render), Agent Economy 3-col grid + maturity legend, About pipeline-vs-supporting agent grid + violet approval callout, and distinct strip-at-render newsletter excerpts in an indexed-row archive.
- A **new tier-1 Signals feed**: a security-DEFINER `public.signals_feed` view (migration 044) exposing 5 whitelisted columns of tier-1 `source_posts` + anon grant, with a fail-loud frontend feed of safe external links — the base table left fully RLS-blocked.
- A **smart-quote content-integrity fix** (the only other backend touch): raw-byte diagnosis proved the corpus already clean, so a fail-loud write-path guard + 36-case regression test prevent recurrence (confirm-and-close, no backfill).

### What Worked
- **Foundation-first held again** — Phase 20's layout-agnostic width/token/rhythm baseline survived a mid-milestone layout reversal (see below) unchanged; every later phase conformed to it rather than re-litigating it.
- **Diagnose before patching** — Phase 19 queried raw stored bytes first; the corpus was clean, so the fix became a recurrence-guard, not a risky table-wide backfill. The `marked.js`-has-no-typographer fact ruled out a render-layer cause up front.
- **The column ceiling lives in the data layer** — anon Signals reads go through a security-DEFINER view that exposes exactly 5 columns (RLS can't hide columns); the frontend never sees `body`/`score`/`author`. Fail-loud if the view/grant is absent → never a silent empty feed.
- **`source-authored ≠ requirement-satisfied`** — requirements stayed UNCHECKED until the orchestrator-owned live apply + operator render proof, mirroring v2.0's D-06 deploy-fence; kept "done" honest.
- **Token-only grep gates + scoped gated deploys** carried over from v2.0 and stayed deterministic across all six CSS phases.

### What Was Inefficient
- **A mid-milestone direction reversal** (2026-06-11: "keep separate routes" → hybrid single-scroll landing) re-scoped Phases 21–25 and promoted a deferred future requirement (WIDTH-F1 → SCROLL-01/02). Survivable only because the Phase 20 foundation was layout-agnostic — but it cost a re-plan of the milestone's back half.
- **The Phase 19 first diagnosis was wrong** — it searched for a literal `"` (U+0022) and spot-checked one clean string, concluding "storage clean / nothing to fix"; the operator caught at live verification that the real signature was a *doubled* apostrophe (`''`, 103 occurrences) rendering as a visual double-quote. Re-diagnosis + corrected guard + scoped backfill of editions 26/29/30 followed. (Lesson: verify render bugs end-to-end against the actual rendered output.)
- **Stale requirement markers at close** — WIDTH-01/RHYTHM-01 checkboxes and SCROLL-01/02 traceability status lagged the actual (live, deployed) state and had to be reconciled at milestone close. The phase-level `[x]` and the requirement-list `[ ]` drifted apart.
- **The audit/close hygiene slipped a milestone** — v2.1 was never formally closed (no MILESTONES/retro/tag), surfacing only at v2.2 close.

### Patterns Established
- **Hybrid single-scroll landing**: top-level sections as one scroll page + `IntersectionObserver` scroll-spy, with detail (edition/block) routes kept deep-linkable; a two-mode (`landing`/`detail`) hash router with detail-prefixes-tested-first + an anchored bare-anchor allowlist.
- **Security-DEFINER view as an anon column-ceiling** (NOT `security_invoker`): an invoker view would run as anon, hit RLS-with-no-anon-policy, and return zero rows forever — the definer inversion is load-bearing.
- **Three-way fail-loud fetch split**: `error` → loud diagnostic + `console.error`; `200 []` → benign empty state; rows → render. Distinguishes "policy/view absent" from "genuinely no data."
- **Confirm-and-close**: when a feared data defect proves absent on inspection, ship the recurrence-guard and document the clean scan rather than running a blind backfill.

### Key Lessons
1. **Verify render bugs end-to-end** — reproduce the actual rendered output; don't infer a corpus is clean from a wrong-signature search or one spot-check (the doubled-apostrophe miss).
2. A **mid-milestone reversal is survivable** when the foundation phase is deliberately layout-agnostic — invest in the layout-independent baseline first.
3. **Put the column ceiling in the database** (a whitelisted view), not the frontend — "RLS can't hide columns."
4. **Close milestones promptly** — skipping `/gsd-complete-milestone` (v2.1) loses the tag/retro/record and compounds at the next close.

### Cost Observations
- Model mix: **Opus** orchestrator + executors, **Sonnet** for verification + code review; DeepSeek only in the (untouched) runtime classifier path.
- Notable: the six CSS phases were largely source-then-deploy, so wall-clock was gated by the operator-approved scoped `web` rebuilds (the single shared public cutover), not by executor parallelism.

---

## Milestone: v2.3 — Pre-Publish Evaluation Step

**Shipped:** 2026-07-03
**Phases:** 6 (26–31) | **Plans:** 20 | **Tasks:** 44 | **Timeline:** 11 days (2026-06-22 → 2026-07-03), 156 commits

### What Was Built

A two-layer automated pre-publish evaluation between newsletter generation and publish: continuity/exemplar
context loader (26), `edition_evals` persistence + governed hard-capped `edition_eval` proxy agent (27), the
no-LLM deterministic fabrication/mechanical gate (28), the 5-dimension Sonnet judge + bounded N=2
feedback-rewrite loop (29), sequencer wiring with the enforce-gated hold action (30), and the operator
surfacing layer — hardened `send_telegram`, Friday-notify eval summary, live `/newsletter_eval` command (31).
Armed report-only; human publish gate unchanged.

### What Worked

- **Build-pure-then-wire ordering** (26→29 standalone modules, 30 wiring, 31 surfacing): every phase was
  independently shippable and rollback-safe; the wiring phase was small because the modules' contracts
  (emit-only flags, verdict taxonomy, write-row params) were locked earlier.
- **Fix-review-blockers-before-verify** (validated again): WR-03/05/06 in Phase 31 and CR-01/02 in Phase 28
  were fixed pre-verification with locking tests, keeping VERIFICATION.md honest.
- **The milestone-level integration audit earned its keep**: six green phase verifications and a green test
  suite coexisted with a 100%-reproducible production outage that only a cross-phase runtime check caught.
- Structural invariants (verdict-iff-ok CHECK, `.in_()`-free readers proven by stub tests) made whole bug
  classes unrepresentable rather than merely tested-against.

### What Was Inefficient

- **The Dockerfile packaging gap** (the headline miss): three phases added modules to `docker/newsletter/`
  and none added COPY lines; the suite imports from the source tree so nothing failed; deploy verification
  grepped strings instead of importing inside the container; the governed-cycle "proofs" bypassed the real
  caller path via manual httpx. The eval was dead in prod from arming until the milestone audit.
- Phase 31's D-14 ("never rebuild newsletter during calibration") froze a broken image — freeze decisions
  need an image-goodness check *before* they take effect.
- 31-04's live verify accepted "No eval has run yet" as the correct empty-state answer without asking *why*
  the table was empty when an edition had been generated post-arming (it hadn't yet at that moment, but the
  check had no way to distinguish outage from not-yet-run).

### Patterns Established

- **Container-import verification**: a new module isn't shipped until `docker exec <svc> python -c "import X"`
  passes in the running container. Added to deploy checklists via memory.
- **Sequencer-path proof**: governance/settlement claims must be proven through the real caller entrypoint
  (`run_edition_eval`), not a manual bypass against the proxy.
- **Fail-open-but-LOUD at every layer**: outer catch blocks around eval invocations now page the operator
  (`[EVAL OUTAGE]` labels), not just log.

### Key Lessons

1. Packaging is part of shipping — schema+code+**image** atomically, or it didn't ship.
2. Per-phase verification composes to less than milestone verification: runtime wiring needs its own audit.
3. An empty-table "correct answer" can mask an outage; empty-state checks should assert the *reason* for
   emptiness when a producer should have run.

### Cost Observations

- Model mix: opus executors/reviewers/fixers, sonnet verifier/integration-checker (per model_profile=quality).
- Sessions: phase 31 executed in one orchestrated session (3 worktree executors, 1 reviewer, 1 fixer ×2,
  1 security auditor, 1 verifier, 1 integration checker); close ran same-day.
- Notable: the integration checker (~186k tokens) found the outage that six verifiers (~1M+ tokens combined)
  structurally could not — budget for cross-phase runtime checks at every milestone close.

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Key Change |
|-----------|--------|------------|
| v1.0 | 11 | Established the autonomy-boundary spine (intake autonomous, publish gated) and structural-enforcement discipline; introduced no-worktree execution for prod-touching phases. |
| v2.0 | 4 | Foundation-first CSS phases on token-only grep gates; D-06 deploy-fence (whole milestone ships in one operator-approved cutover); substituted-preview verification without a browser. |
| v2.1 | 4 | Content-only milestone on the v2.0 surface; gated batch publish via the atomic RPC; **closed informally (no tag/retro) — process gap.** |
| v2.2 | 7 | Two backend touches (write-path + RLS view) deliberately isolated from six CSS phases; survived a mid-milestone layout reversal via a layout-agnostic foundation; `source-authored ≠ satisfied` deploy discipline. |

### Cumulative Quality

| Milestone | Tests | Zero-Dep Additions |
|-----------|-------|--------------------|
| v1.0 | per-phase pytest suites (intake, synthesis, gated-publishing, command handlers) | All phases added no new runtime dependencies beyond the existing stack. |
| v2.0 | token-only grep gates (no raw-px radius / off-grid spacing / literal hex) | No new runtime deps; cascade shrunk to 2 sheets (`style-map.css` retired). |
| v2.1 | anon-key before/after read proofs + a fail-loud cross-link verification harness | No new runtime deps; one migration (043). |
| v2.2 | 36-case smart-quote regression suite + offline excerpt/render harnesses + grep token gates | No new runtime deps; one migration (044, security-definer view). |

### Top Lessons (Verified Across Milestones)

1. Structural enforcement (triggers/RLS/RPC/views) beats application-layer checks — `service_role` bypasses RLS, and a view (not the frontend) is where an anon column-ceiling belongs.
2. Fail loud on missing inputs; never silently default to a no-op ("the wallet bug"; the Signals empty-feed-on-missing-policy guard).
3. Verify render/visual bugs end-to-end against the actual rendered output — storage bytes and wrong-signature searches lie (the doubled-apostrophe miss).
4. Close milestones promptly via `/gsd-complete-milestone` — the v2.1 skip lost its tag/retro and surfaced only at the v2.2 close.
