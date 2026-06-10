# Phase 17: Cross-link Wiring & Preview - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the Phase-16 loaded-but-**unpublished** content fully navigable and verifiable on a **non-published, local preview** — every `#/map/<slug>` cross-block link and every hub→block click-through resolves to the right page, maturity pills render the three distinct stages, and the hub renders as the `#/map` landing (thesis + two-tier framing intro above the card grid) **without duplicating its block list** — proving the content is publish-ready before Phase 18 publishes.

Requirements: **LINK-01** (every `#/map/<slug>` cross-link + hub→block entry resolves), **PREV-01** (loaded-but-unpublished content renders correctly on a non-published preview; live published site unchanged), **HUB-01** (hub renders as the `#/map` landing; block list appears once — cards — not duplicated as prose links + cards).

**In scope:** a local-only elevated preview of `agentpulse-web`; a read-only draft-fetch render path in `app.js` (hub + blocks); a code-trim of the hub's prose block-list; an explicit dormant-in-prod preview flag; exhaustive fail-loud cross-link verification.
**Out of scope:** the publish RPC run + scoped deploy (Phase 18); any net-new UI feature/route/component/restyle; distinct `nascent` visual treatment; any pipeline / proxy / agent-service change; any schema/RLS change.

**The live published site must stay byte-for-byte unchanged for visitors** — drafts never touch the public anon site; the preview is local-only.
</domain>

<decisions>
## Implementation Decisions

Resolved with the operator on 2026-06-08. They sit **on top of** the locked Phase-15/16 contract + load (see "Locked upstream" — do not re-litigate).

The operator chose to deep-dive two areas — **Preview mechanism** and **Link + scope rigor**. Hub-duplication (HUB-01) and `nascent` treatment were **not** deep-dived; their recorded defaults are in **Claude's Discretion** below (operator invited to override either; none requested).

### Preview mechanism (PREV-01)

- **D-01 — Local-private elevated preview.** Verification runs against a **local** `agentpulse-web` container on this branch (the `#/map` landing + `#/map/<slug>` pages), **not** the public site. The live published `#/map` is untouched until Phase 18. This honors the spine ("publishing is the gated step", "live published site unchanged"). Rejected: a live bannered `preview`-status route (would put unpublished content on the public site + touch schema/RLS); a static offline render (wouldn't exercise the real router/RLS/render path → low confidence).

- **D-02 — Read the drafts with `service_role`, substituted into the LOCAL container only.** Anon RLS exposes only `status='published'` bodies (`033:367-370`); only `service_role` bypasses that **without a schema change**. The local container substitutes the `service_role` key into `__SUPABASE_ANON_KEY__` via the **existing `docker/web/entrypoint.sh:3-4` sed-substitution** — local-only, fully reversible, **no schema/RLS change, nothing new deploys**. **Guard (mandatory):** branch + `/diff` confirms the **deployed** `app.js` keeps the real **anon** key — the `service_role` key NEVER ships. Contains the "`service_role` = historical failure actor" risk to a throwaway local container. Rejected: a temporary preview RLS policy + preview JWT (adds DB/RLS churn against "no migration beyond what reconciliation strictly requires" + must be remembered-to-remove).

- **D-03 — Read-only draft-fetch render path.** `blocks.current_body_version_id` is **NULL until publish** (it is set only by the publish RPC, `039:73-77`), so today's body fetch (`app.js:541`, by `current_body_version_id`) returns nothing for an unpublished block. Fix: when `current_body_version_id` is NULL, **fetch the latest `status='draft'` `block_body_versions` row for that slug** and `marked.parse` it — for **both** the block pages and the hub intro. **No DB writes — fully reversible.** In production with the anon key this is a **no-op** (RLS returns no draft → renders exactly as today); only the local `service_role` preview sees the draft. Rejected: temporarily pointing `current_body_version_id` at the draft via a `blocks` UPDATE (a state change to remember-to-revert; makes the row look publish-pointed — against the reversibility preference).

- **D-04 — Gate behind an explicit preview flag; the code ships DORMANT in production.** The draft-fetch path is gated behind an explicit preview flag (URL/hash param or build-time flag) set **only** on the local container. The small render path **ships in `app.js`** but stays dormant in prod — **double-safe**: no flag set + published-only RLS both independently suppress it. One reviewable `/diff`; reusable by any future preview; **stays content-scoped** (no new route/component, reuses `marked.parse` + existing templates + router). Rejected: a local-only branch that never merges (would leave Phase 18 publishing against a render path never exercised in its production form).

### Link wiring + scope rigor (LINK-01, SC#4)

- **D-05 — Exhaustive + fail-loud cross-link verification.** There are **22 cross-link instances** (hub→7 blocks + 15 block→block; full inventory in `<specifics>`), **all** targeting the 7 in-scope body-loaded blocks (none to `regulation-legal` or any off-roster slug). Verification: **programmatically extract every `#/map/<slug>` href** from the `marked.parse`-rendered hub + 7 bodies, **assert each target slug exists in the live `blocks` roster (fail-loud on any miss** — guards future content drift), **AND manually click-through the full set** on the local preview (hub→each block + the block→block links). This is the last gate before publish. Rejected: automated-extraction-only (doesn't eyeball the rendered page); spot-check sample (relies on link uniformity).

- **D-06 — Confirmed in-bounds renderer set (the SC#4 line).** **IN-BOUNDS (content-scoped fixes that make existing content render/resolve):** (a) `renderHub` fetches + `marked.parse`'s the hub draft body as the intro, **replacing the `HUB_STORYLINE` constant** (graceful fallback to `HUB_STORYLINE` pre-publish per P15-D-04); (b) the D-03 read-only draft-fetch path; (c) **code-trimming the hub's prose block-list** so it isn't duplicated by the cards (HUB-01); (d) the D-04 dormant preview flag. All reuse the existing card/block templates + `marked.parse` + router. **OUT-OF-BOUNDS (defer):** new components/routes, restyle, new nav, distinct `nascent` visual treatment. Rejected variant: resolving HUB-01 by **editing `00-hub.md` + re-loading via the rewrite path** instead of a code-trim — the operator chose the in-code trim, keeping the loaded draft untouched.

### Claude's Discretion

Two surfaced gray areas the operator chose **not** to deep-dive; recommended defaults below (planner/researcher may refine, keeping the spine + SC#4 intact). Operator was explicitly invited to override either and did not.

- **HUB-01 — render intro + cards; code-trim the hub prose block-list (recommended default).** The hub body (`00-hub.md`) contains, between its framing and its closing, a **prose list of all 7 blocks** (`## Tier 1 — The Substrate` / `## Tier 2 — The Behavior`, each block as `[Title →](#/map/<slug>)`). Rendering the **full** hub body **plus** the card grid is exactly the duplication HUB-01 forbids. **Default:** render the hub intro = the opening **thesis** + the **`## How to read this map`** two-tier framing (and **optionally** the closing **`## The thesis, restated`**), and **omit the Tier-1/Tier-2 prose block-list in code** — the block list appears **once, as the existing cards** (cards preferred, per EXECUTION_BRIEF §2/§5). Hub→block click-through is satisfied by the cards (`app.js:467` already emits `<a href="#/map/<slug>">`). Planner pins the exact cut-points (suggest splitting on the `## Tier 1`/`## Tier 2` headings or a sentinel) and whether the closing paragraph is kept. The hub `blocks` row has `tier='hub'`, which the three tier-grid filters already exclude — so **no hub card** is rendered (correct).
- **`nascent` maturity — pill-only, no distinct visual treatment (recommended default).** `negotiation-coordination` + `psychology-disposition` load as `nascent`; render with the standard maturity pill only (the REQUIREMENTS "Future Requirements" default: "pill-only unless discuss-phase decides otherwise"). No net-new visual capability (consistent with SC#4 + D-06 OUT).

### Locked upstream (Phases 15-16 — carry forward, DO NOT re-decide)

- **P15-D-01 (maturity remap):** `building → emerging` was applied **at load** for the substrate trio (`identity-trust` / `memory-context` / `payments-settlement`) — they render **`emerging`** (stage-2 pill), **not** `building`. ⚠ **Flag F-2 (verification-wording trap):** ROADMAP SC#2 / PREV-01 text says the preview pills show "`building`" — the live rendered value is **`emerging`**. The three **distinct** stages that must render are **`emerging` / `contested` / `nascent`**; verify against those, not the literal doc word `building`. (Authoritative resolution: 15-CONTRACT.md Flag F-2; do NOT "fix" the pill to say `building`.)
- **P15-D-02 (`regulation-legal`):** stays a **deferred / body-less frame card** — not previewed, not published, no body loaded. No cross-link points to it (confirmed). It continues rendering as a DEFERRED card; do not change that.
- **P15-D-04 (hub home):** the hub has a DB-served home (`tier='hub'` `blocks` row, `sort_order=0`); render reuses `marked.parse` **unchanged**; graceful fallback to the `HUB_STORYLINE` constant pre-publish. The XSS-via-markdown disposition (T-04-03-01, compensating control = operator publish gate) carries over.
- **Load state:** the 8 bodies are present as `status='draft'` rows (Phase 16); no row is published; `#/map` is unchanged for anon visitors. Phase 17 writes **nothing** to `economy_map`.
- **The spine (P15-D-06):** direct PostgREST + `Accept-Profile` (never supabase-py `.in_()`); append-only on `block_body_versions`/`timeline_entries` — corrections via canonical-body-rewrite, never a raw UPDATE (`blocks` has NO trigger); fail-loud on any missing field; **branch + `/diff` + web-only scoped `agentpulse-web` deploy** — no pipeline / proxy / agent-service change.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.** Every entry is a full relative path.

### The brief, requirements & verification target (read first)
- `.planning/docs/EXECUTION_BRIEF.md` — §2 what "live" means (hub as `#/map` landing; **cards preferred**; do **not** duplicate the block list as prose + cards), §3 sequencing (load → **preview on a non-published route** → publish; cites the `#/tokens-preview` pattern), §4 standing constraints, §5 open items (cards-vs-prose, `nascent` treatment).
- `.planning/REQUIREMENTS.md` — **LINK-01, PREV-01, HUB-01** (this phase); the spine paragraph.
- `.planning/ROADMAP.md` §"Phase 17: Cross-link Wiring & Preview" — goal + the **4 success criteria** (the verification target).

### Canonical content (metadata source of truth + the link source)
- `.planning/docs/00-hub.md` — hub `agent-economy` body. **Contains the 7 prose block-links** (`## Tier 1` / `## Tier 2`) — the HUB-01 duplication source the D-06 code-trim removes; also the thesis + two-tier framing intro.
- `.planning/docs/01-identity-trust.md … 07-psychology-disposition.md` — the 7 block bodies. **Contain the 15 block→block `#/map/<slug>` cross-links** (the LINK-01 source). Frontmatter `maturity: building` on 01/02/03 already remapped to `emerging` at load (P15-D-01) — do NOT edit the docs.

### Phase 15-16 locked inputs (the contract this phase renders against)
- `.planning/phases/15-inventory-roster-reconciliation/15-CONTRACT.md` — **the serve contract**: anon RLS (`blocks` `USING(true)` :361-364; `block_body_versions` `USING(status='published')` :367-370); body reached via `blocks.current_body_version_id` (nullable, NULL pre-publish); hub **not** DB-served today (renders `HUB_STORYLINE` constant); rows whose `tier ∉ {substrate,behavior,frame}` excluded from grids; the verified 5-member `maturity` enum; **Flag F-2** (pills render `emerging`, not `building`).
- `.planning/phases/15-inventory-roster-reconciliation/15-RECONCILIATION.md` — reconciled roster + collision-free `sort_order {0..8}`; D-04 Option-A hub home.
- `.planning/phases/15-inventory-roster-reconciliation/15-CONTEXT.md` — P15-D-01..D-06 (carried forward above).
- `.planning/phases/16-content-load-unpublished/16-CONTEXT.md` — the load: bodies are `status='draft'`; D-07 before/after anon-perspective proof; loader/migration 043 artifacts.

### The live serve path (frontend — this phase EDITS `app.js`)
- `docker/web/site/app.js` — **router** (`getRoute` :117-138 handles `#/map`/`#/map/:slug`; `route()` :834 + `hashchange` :854); **`renderHub`** (:436-503; `HUB_STORYLINE` :32 emitted :496; tier grids exclude `tier='hub'`; card `<a href="#/map/<slug>">` :467); **`loadBlock`/`renderBlock`** (:505-605; body via `current_body_version_id` :541; `marked.parse` :586); **`renderMaturityPill` / `MATURITY_STAGE`** (:38 `emerging→2`; :391; unknown→1 :396); **newsletter `preview`-status pattern** (:205, banner :232 — the *rejected-for-blocks* mirror, here for contrast).
- `docker/web/entrypoint.sh` — **the substitution mechanism** for D-02: lines 3-4 sed-substitute `__SUPABASE_URL__` / `__SUPABASE_ANON_KEY__` from env at container start. The local preview sets `SUPABASE_ANON_KEY` to the `service_role` key for that container only.
- `docker/web/site/tokens-preview.html` — the static design-reference page the brief's "preview pattern" cites; canonical maturity-pill markup source (referenced by `app.js` comments).
- `docker/web/Dockerfile`, `docker/web/Caddyfile` — local-container build/serve context.

### The live schema (RLS, status, publish RPC — do not change this phase)
- `supabase/migrations/033_economy_map_schema.sql` — anon RLS (`blocks` :361-364, `block_body_versions` published-only :367-370, `timeline_entries` :373-376); `status` CHECK `draft/published/superseded`; append-only triggers on the content tables — **`blocks` has NONE**.
- `supabase/migrations/028_newsletter_preview.sql` — the **newsletter `preview`-status RLS** pattern (anon reads `status IN ('published','preview')`) — the proven pattern we deliberately did **not** mirror for blocks (D-01/D-02 rationale).
- `supabase/migrations/039_publish_block_version_watermark_null_guard.sql` — the publish RPC (Phase 18) — sets `current_body_version_id` (:73-77), which is **why it's NULL pre-publish** and D-03 is needed.

### Project decision record
- `.planning/PROJECT.md` — Key Decisions (regulation = closing frame; append-only `block_body_versions`; schema isolation via direct PostgREST; sentinels flag-never-block; the autonomy-boundary spine).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`marked.parse(bodyMd)`** (`app.js:586` blocks, `:250` newsletter) — the live markdown render path. The hub intro (D-06) and the draft-fetch path (D-03) reuse it verbatim — **not** a net-new capability.
- **`renderHub` / tier grouping + `renderTile`** (`app.js:436-503`) — already groups by tier and emits `<a href="#/map/<slug>">` cards; `tier='hub'` is already excluded from all three grids. D-06 inserts the marked-parsed hub intro in place of the `HUB_STORYLINE` line (:496) and code-trims the body's prose block-list.
- **The router** (`getRoute` :117-138 + `hashchange` :854) — already resolves `#/map/<slug>` → `loadBlock(slug)`. Cross-links rendered by `marked.parse` become `<a href="#/map/<slug>">`; clicking changes the hash → `route()` → `loadBlock`. LINK-01 navigation should "just work"; the real gap is the **empty body** pre-publish (D-03), not routing.
- **`docker/web/entrypoint.sh:3-4`** — the env→`app.js` sed-substitution; the D-02 local `service_role` swap rides this with **zero new mechanism**.
- **`renderMaturityPill` + `MATURITY_STAGE`** (`app.js:38/:391`) — `emerging→2`, `contested→3`, `nascent→1`; renders the three distinct preview stages with **no change** (Flag F-2: they show `emerging`, not `building`).

### Established Patterns
- **RLS is the read boundary** — anon sees only `status='published'` bodies; `service_role` bypasses RLS (the D-02 local read) and a NULL-`current_body_version_id` block renders body-less. D-03's draft-fetch is a **no-op for prod anon** precisely because of this.
- **`current_body_version_id` is set only on publish** (`039:73-77`) — the load-bearing reason the renderer can't show a draft body today (D-03).
- **Append-only on `block_body_versions`, NOT on `blocks`** — Phase 17 writes nothing to `economy_map`; the read-only draft-fetch (D-03) avoids the question entirely.
- **`status='preview'` exists for `newsletters` only** (migration 028) — NOT for `economy_map.block_body_versions` (status enum is `draft/published/superseded`); mirroring it would be a schema/RLS change (rejected, D-01/D-02).

### Integration Points
- **`app.js` is the only code edited** — the draft-fetch path (`loadBlock`/`renderBlock` + `renderHub`), the hub-intro marked.parse + prose-list trim, and the dormant preview flag. No backend/schema/migration change.
- **Local container** — `agentpulse-web` rebuilt/run locally on the branch with `SUPABASE_ANON_KEY=<service_role>` for the preview; the deployed container is unchanged (anon key) and is **not** rebuilt until Phase 18.
- **Verification harness** (D-05) — an extract-and-assert over the rendered hrefs (every `#/map/<slug>` target ∈ live roster, fail-loud) + an operator manual click-through on the local preview.

### Reusable verification facts
- **22 cross-link instances, all in-roster** (D-05 / `<specifics>`) — the assertion is trivially green today; it exists to fail-loud on future drift, and the manual pass confirms the rendered pages.
</code_context>

<specifics>
## Specific Ideas

**Cross-link inventory (the LINK-01 universe — extracted from `.planning/docs/0*.md`):**

| source doc | # links | targets |
|---|---|---|
| `00-hub.md` (hub) | 7 | identity-trust, memory-context, payments-settlement, autonomy-control, negotiation-coordination, governance-accountability, psychology-disposition |
| `01-identity-trust.md` | 2 | negotiation-coordination, payments-settlement |
| `02-memory-context.md` | 2 | identity-trust, psychology-disposition |
| `03-payments-settlement.md` | 1 | negotiation-coordination |
| `04-autonomy-control.md` | 2 | governance-accountability, psychology-disposition |
| `05-negotiation-coordination.md` | 2 | identity-trust, payments-settlement |
| `06-governance-accountability.md` | 3 | autonomy-control, identity-trust |
| `07-psychology-disposition.md` | 3 | autonomy-control, memory-context, negotiation-coordination |

**Total: 22 instances → 7 distinct target slugs, all in-scope body-loaded blocks. None → `regulation-legal` or any off-roster slug.** (Per-file counts include repeats of the same target.)

**The preview happy-path the operator will verify:** open the local preview at `#/map` → hub renders thesis + two-tier framing intro + the existing card grid (no duplicated prose block-list) → click each of the 7 cards → each block page renders back-arrow + title + subtitle + maturity pill (`emerging`/`contested`/`nascent`) + body → click the in-body cross-links → each resolves to the right block page → the public live `#/map` is simultaneously confirmed unchanged.
</specifics>

<deferred>
## Deferred Ideas

- **Phase 18 (PUB-01) — gated batch publish:** the `publish_block_version` RPC run (sets `current_body_version_id`, flips draft→published) + the web-only scoped `agentpulse-web` deploy, in ONE operator-approved batch. Phase 17 publishes nothing.
- **Distinct `nascent` visual treatment** beyond the pill — defaulted to pill-only (Claude's Discretion); a future styling pass could revisit if the operator wants it. Out of SC#4.
- **HUB-01 via source-doc edit** (edit `00-hub.md` to be intro-only + reload via the rewrite path) — the rejected alternative to the in-code trim; noted in case a future content cleanup wants the DB hub body itself to exclude the prose list.
- **EU AI Act tracker → `regulation-legal` body** — the deferred frame slot (P15-D-02), fed by a future milestone (EUAI-01/02), not now.
- **Evolution timeline content** — bodies preview/publish with possibly-empty timelines; intake fills them weekly. No manual timeline authoring this milestone.

### Reviewed Todos (not folded)
The 7 pending todos (`.planning/todos/pending/`) were reviewed in Phases 15-16 — all are **v1.0 backend follow-ups** (analyst predictions title-expire, soft-cap allow-negative hardening, pay-endpoint transfer RPC, phase-05/06/07 review follow-ups, research trigger file permissions). **None overlap** the `economy_map` cross-link/preview domain; parked in the ROADMAP backlog.
</deferred>

---

*Phase: 17-cross-link-wiring-preview*
*Context gathered: 2026-06-08*
