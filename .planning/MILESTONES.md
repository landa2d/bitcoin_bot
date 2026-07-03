# Milestones

## v2.3 Pre-Publish Evaluation Step (Shipped: 2026-07-03)

**Phases completed:** 6 phases (26–31), 20 plans, 44 tasks — 2026-06-22 → 2026-07-03 (11 days, 156 commits, +8.3k LOC)

**Delivered:** An automated two-layer pre-publish evaluation between newsletter generation and publish — a deterministic fabrication/mechanical gate plus a Sonnet judge with a bounded N=2 feedback-rewrite loop — persisted per-attempt to `edition_evals`, governed through a hard-capped proxy identity, surfaced to the operator via the Friday notify and a live `/newsletter_eval` Telegram command, and armed report-only for calibration. Human publish gate unchanged.

**Key accomplishments:**

1. **Continuity + exemplar context (26):** `load_edition_context()` feeds prior-edition angles and operator voice exemplars to both writer paths and the judge; resurrected the dead Phase E voice check with a fail-loud three-state contract.
2. **Eval persistence + governance (27):** migration 045 `edition_evals` (per-attempt telemetry, `verdict-iff-ok` CHECK) + fail-loud `write_eval_row()` + the governed `edition_eval` proxy agent (hard-capped 5000 sats/weekly, reject-on-cap).
3. **Layer 1 deterministic gate (28):** no-LLM `run_deterministic_gate` — live GitHub/URL/arXiv/named-study/entity-merge fabrication checks (three-outcome classifier, SSRF-guarded) + mechanical editorial checks, proven against historical worst-offender editions.
4. **Layer 2 judge + rewrite loop (29):** pure `run_layer2` — 5-dimension exemplar-anchored Sonnet judge, config-tunable thresholds, bounded N=2 targeted revise with re-gating of every rewrite (a fabricated rewrite hard-aborts to the clean attempt-0 draft).
5. **Sequencer wiring + activation (30):** `run_edition_eval` invoked at both generation save points; enforce-gated `held`+`do_not_publish` hold action; shipped dormant then armed report-only (`enabled=true`/`enforce=false`).
6. **Surfacing & escalation (31):** hardened bool-returning `send_telegram` (+ boot config check, critical-caller alerts), Friday-notify per-draft eval summary, and the owner-gated `/newsletter_eval` (+ `trend`) command wired through the gato allowlist — all live-verified over real Telegram.

**Milestone audit:** initially `gaps_found` — the integration check caught that the newsletter image had shipped WITHOUT the three eval modules (Dockerfile COPY gap; every eval since arming crashed silently). Fixed, redeployed, and proven same-day via a real sequencer-path settled cycle (3 `edition_evals` rows + governed wallet 24998→24975), then re-scored **passed 37/37**. Calibration clock starts 2026-07-03.

**Known deferred items at close:** 13 (see STATE.md Deferred Items) — 1 audit false-positive, 3 complete-but-unmarked quick tasks, 9 pending todos (7 pre-v2.3 carries + WR-01/WR-07 review follow-ups + the enforce-flip calibration action).

Full details: [`milestones/v2.3-ROADMAP.md`](milestones/v2.3-ROADMAP.md) · [`milestones/v2.3-REQUIREMENTS.md`](milestones/v2.3-REQUIREMENTS.md) · [`milestones/v2.3-MILESTONE-AUDIT.md`](milestones/v2.3-MILESTONE-AUDIT.md)


## v2.2 Landing Redesign + Signals Feed (Shipped: 2026-06-19)

**Phases completed:** 7 phases (19–25), 17 plans, 24 tasks
**Timeline:** 2026-06-10 → 2026-06-19 (9 days)
**Git range:** `602b706` (docs(19): create phase plan) → `0350c86` (feat(25-01)) — ~1.25K production LOC across `docker/web/site/` (`app.js`, `style-base.css`, `style-shared.css`), `supabase/migrations/044`, and the `newsletter` write-path guard.
**Requirements:** 17/17 satisfied (no gaps). **Known deferred items at close:** 9 (see STATE.md → Deferred Items → "Acknowledged at v2.2 close") — all already-tracked: 1 passed UAT, 3 completed quick-tasks, 5 backlogged backend follow-ups; no blocking gaps.

**Delivered:** Re-skinned the public `aiagentspulse.com` SPA to the new editorial mockup — the four top-level sections merged into one single-scroll landing with scroll-spy nav (editions & block pages kept as deep-linkable detail routes) — fixed the four live-site defects the redesign brief called out, and added a new tier-1 Signals feed. NOT frontend-only: Phase 19 touched the newsletter write-path and Phase 24 added the milestone's one Supabase migration. The spine held throughout (gated deploys, fail-loud, append-only, all LLM via `llm-proxy:8200`).

**Key accomplishments:**

- **Smart-quote integrity (Phase 19 — QUOTE-01/02):** proved from raw stored bytes that the apostrophe→double-quote corruption was NOT in the corpus (43 rows scanned, 0 corrupt; the `marked.js` renderer has no typographer), then shipped a fail-loud, no-op-on-clean `normalize_apostrophe_corruption` write-path guard locked by a 36-case regression test — corruption can't silently recur. Confirm-and-close: no backfill needed.
- **Width & centering foundation (Phase 20 — WIDTH-01/RHYTHM-01):** two coexisting, both-centered max-widths (`--measure` narrow prose / `--wide` grids) killed the dead left gutter; the single 720px `.container` was retired and every route re-homed onto its correct axis, with a token-only color system + section-rhythm hierarchy as the shared baseline every later phase conformed to.
- **Single-scroll landing + scroll-spy (Phase 21 — SCROLL-01/02):** the four top-level sections (newsletter / signals / agent-economy / about, locked mockup order) now render on one `#landing` page with an `IntersectionObserver` scroll-spy nav; individual editions (`#/edition/<n>`) and block pages (`#/map/<slug>`) stay deep-linkable detail routes; detail→back restores landing scroll position; a two-mode `app.js` router refactor underpins it.
- **Per-section visual fixes (Phase 22 — HEAD-01/GRID-01/GRID-02/AGENTS-01):** edition H1 de-dup (baked `— Edition #N | <date>` suffix stripped at render, both modes); the Agent Economy map went 2→3-col with 3/2/1 breakpoints + a maturity legend mirroring the real 5-segment pill; the About grid became a numbered 01-04 pipeline + bulleted supporting layer with a distinct violet "nothing publishes without human approval" callout.
- **Distinct newsletter excerpts (Phase 23 — EXCERPT-01):** strip-at-render removal of the "Read This, Skip the Rest" boilerplate intro + the first genuinely-distinct sentence surfaced in the indexed-row archive format (number · title · summary · date) — no schema change; editions 29 ≠ 30 in both modes.
- **Signals feed (Phase 24 — SIGNAL-01..04):** a security-definer `public.signals_feed` view (migration 044) exposing exactly 5 whitelisted columns of tier-1 `source_posts` newest-first + `GRANT SELECT TO anon` (the column ceiling lives in the view; the base table stays fully RLS-blocked), wired to a fail-loud frontend feed with safe external links (`safeHttpUrl`-gated, `rel="noopener noreferrer"`), capped with an inline view-all — applied live via the Supabase MCP + operator-verified.
- **Responsive & accessibility pass (Phase 25 — RESP-01/A11Y-01):** holistic live-render acceptance gate — grids reflow 3→2→1, nav condenses at 600px, rows stack date-above-headline, `:focus-visible` violet outlines, `prefers-reduced-motion` suppresses the theme fade (cascade win proven live), and every navigational element audited as a real `<a>` — operator signed off.

---

## v2.1 Agent Economy Content (Shipped: 2026-06-09)

**Phases completed:** 4 phases (15–18), 10 plans
**Backfilled:** 2026-06-19 (this milestone was shipped 2026-06-09 but not formally closed at the time — record reconstructed during the v2.2 close; artifacts were preserved in `milestones/v2.1-*`).

**Delivered:** Filled the v2.0 grid with real editorial content — all 8 in-scope `economy_map` block bodies published live to `aiagentspulse.com/#/map` in ONE operator-approved batch. Content-only: no UI redesign, no pipeline/proxy/agent-service changes; `regulation-legal` kept deferred. The spine held (autonomous intake, human-gated publish, append-only via the canonical-rewrite path, all `economy_map` access via direct PostgREST + `Accept-Profile`).

**Key accomplishments:**

- **Inventory & roster reconciliation (Phase 15 — INV-01/02, ROST-01):** a no-write documentation phase — `15-CONTRACT.md` captured the live `economy_map` storage/serve contract (block columns + 3-tier CHECK, the 2 append-only triggers, the atomic `publish_block_version` RPC = migration 039, anon published-only RLS) and the verified 5-member maturity enum; `15-RECONCILIATION.md` locked the per-slug roster (added `negotiation-coordination`, kept `regulation-legal` deferred, contiguous `sort_order` reshuffle). No migration ≥043, no `app.js` edit, no `economy_map` write.
- **Content load — unpublished (Phase 16 — LOAD-01/02/03):** migration 043 (orchestrator-applied via the Supabase Management API) relaxed the tier CHECK for a `'hub'` sentinel, inserted the `agent-economy` hub + `negotiation-coordination` rows, and reshuffled `sort_order`; a standalone PostgREST loader landed all 8 canonical bodies as `status='draft'` (validate-all-then-insert, `building→emerging` remap, idempotent). Proven a visitor-facing no-op by an anon-key before/after read (published count unchanged 2→2); 3 stale drafts superseded via the `reject_block_version` RPC (never a raw UPDATE).
- **Cross-link wiring & preview (Phase 17 — LINK-01, PREV-01, HUB-01):** a dormant `?preview=1` flag-gated preview render path in `app.js` (prefers the draft body + `proposed_maturity`) + a hub intro that drops the prose block-list so blocks appear once as cards; a fail-loud `verify_economy_map_crosslinks.py` harness asserts all 22 `#/map/<slug>` links resolve to the 7 in-roster targets. Deployed/anon path a byte-for-byte no-op (flag absent + published-only RLS); operator-verified click-through.
- **Gated batch publish (Phase 18 — PUB-01):** the go-live — an operator-approved scoped `agentpulse-web` rebuild proven a visual no-op pre-publish, then a fail-loud idempotent batch flipped all 8 drafts live (7 blocks first, hub last) via the atomic `publish_block_version` RPC; `verify_economy_map_publish.py` PASSED from the anon perspective (published count 2→8, hub article + all 22 cross-links resolve against published content). Code-review blocker CR-01 (unreachable idempotent recovery) fixed pre-verify.

---

## v2.0 Frontend Redesign (Shipped: 2026-06-08)

**Phases completed:** 4 phases, 8 plans, 16 tasks

**Key accomplishments:**

- New style-base.css token layer — single light-mode violet-accent :root palette, Source Serif 4 / IBM Plex Mono typography with 18px/1.62 serif body + .page-title/.eyebrow display classes — loaded first in index.html, with the dark body.technical/strategic var blocks and body-level Courier retired from style-shared.css so the new palette actually takes effect (D-04).
- Persistent sticky 3-tab nav shell — brand · Newsletter / Agent Economy / What is AgentPulse · Subscribe — replacing the old .top-nav, with route-derived active-tab state (setActiveTab wired into the existing hash router's route()), ← Back to [section] back-controls, the retired plain Map link, and a ≤640px wrap-to-scrollable-row responsive nav, all styled against the Plan-01 :root tokens.
- Restyled every Newsletter rule in `style-shared.css` onto the Phase 11 serif/light system — TYPE-01 serif prose (no monospace body paragraphs), single serif headings, B1 `--line`-divided list rows, the A1 filled-accent segmented toggle pill + mono hint line, magazine article surfaces (accent blockquotes, code chips, emphasized lead), a token-based `.preview-banner`, and the minimal D3 header text rules.
- Wired the Newsletter list + article markup/JS onto Plan 01's CSS: relocated the Technical/Strategic toggle to the Newsletter list (TGL-01) by scoping its `.hero` host to the `list` route in `showView()`, restructured the `.hero` into the minimal D3 header, date-appended the `renderList()` kicker, gave the reader view its own escaped magazine header in `renderArticle()`, and swapped the inline-amber PREVIEW banner for the class-based `.preview-banner` — with `setMode()` requiring zero logic change and no new XSS sink introduced.
- Fleshed out the already-wired `#/about` route into the real "What is AgentPulse" page — eyebrow → title → page-sub → 3 accuracy-reconciled serif paragraphs → a 5-pill token-styled agent row — plus the net-new token-anchored `.about` / `.agent-pill` CSS, with `app.js` and the live deploy untouched.

---

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
