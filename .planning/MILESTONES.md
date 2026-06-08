# Milestones

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
