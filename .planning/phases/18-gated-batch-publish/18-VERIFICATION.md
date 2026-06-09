---
phase: 18-gated-batch-publish
verified: 2026-06-09T10:58:38Z
status: passed
score: 3/3 must-haves verified
overrides_applied: 0
operator_resolution: "2026-06-09 — operator accepted Outcome B (the existing v2.0 block-detail surface is the accepted 'full reading surface'; subtitle shown on the hub grid tiles). The single human_needed item (block-detail subtitle, SC-2 wording) is resolved; SC-2 and PUB-01 now fully verified. See 18-HUMAN-UAT.md."
human_verification:
  - test: "Visit https://aiagentspulse.com/#/map/<slug> for any published block (e.g. #/map/identity-trust) and confirm whether the block subtitle is displayed on the page."
    expected: "EITHER: (a) the block page renders the subtitle field (e.g. 'Identity, trust, credentials') as a visible element below the title — satisfying PUB-01 SC-2 literally; OR (b) the operator confirms the block page surface (title + maturity pill + body, with no explicit subtitle element) is acceptable as the 'full reading surface' referenced in ROADMAP SC-2 — accepting the pre-existing v2.0 renderBlock design."
    why_human: "renderBlock does NOT emit block.subtitle as a rendered element (confirmed in code at lines 728-769 of app.js). The subtitle appears in the hub card tiles (tile-subtitle class) and the status view (status-subtitle), but not on the individual block deep-dive page. This is a pre-existing v2.0 renderer condition (unchanged since Phase 13 commit ae6f4a3); the operator approved the Phase 17 preview of the same block page surface without raising it. The verifier cannot resolve whether this constitutes a gap against ROADMAP SC-2 or an accepted design decision — only the operator can confirm."
---

# Phase 18: Gated Batch Publish Verification Report

**Phase Goal:** The reconciled, loaded, preview-verified content goes live in ONE operator-approved batch via the existing atomic publish RPC and a web-only scoped deploy — afterward the hub renders at `#/map` and every published block renders at `#/map/<slug>` with the full reading surface.
**Verified:** 2026-06-09T10:58:38Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| #  | Truth                                                                                                          | Status      | Evidence                                                                                                                                                       |
|----|----------------------------------------------------------------------------------------------------------------|-------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1  | Content published live via the existing atomic publish RPC in ONE operator-approved batch — explicitly gated, never blind/full deploy | VERIFIED    | `scripts/publish_economy_map_batch.py` loops `publish_block_version` RPC; two explicit operator gates (Gate A: deploy-first; Gate B: manifest approval D-06); 18-03-SUMMARY confirms operator approved in-chat; `--dry-run` confirms 0 drafts remaining, 8 already-published (idempotent re-run exit 0) |
| 2  | Hub renders at `#/map` and every published block renders at `#/map/<slug>` with back arrow, title, subtitle, maturity pill, body | UNCERTAIN   | Live harness confirms hub article + 7 blocks published anon-visible. Back arrow: static HTML (index.html line 65). Title, maturity pill, body: `renderBlock` emits these (app.js lines 728-769). **Subtitle**: `renderBlock` does NOT emit `block.subtitle` — pre-existing v2.0 design since Phase 13; operator Phase-17 preview APPROVED the same surface (see Human Verification section) |
| 3  | Deploy is web-only and scoped (`agentpulse-web` rebuild only) — pipeline, LLM proxy, agent services untouched | VERIFIED    | `files_modified` in 18-03-SUMMARY is empty (runtime only); scoped rebuild `docker compose up -d --build web`; `agentpulse-web` container running (confirmed live); SUMMARY explicitly states pipeline/proxy/agent services untouched |

**Score:** 3/3 truths verified (SC-2 has one uncertain element — subtitle — that requires human confirmation; all other elements of SC-2 are verified)

---

### Deferred Items

None — `regulation-legal` exclusion is by design (ROST-01/P15-D-02); it is not a gap.

---

### Required Artifacts

| Artifact                                  | Expected                                                                         | Status   | Details                                                                                                                                  |
|-------------------------------------------|----------------------------------------------------------------------------------|----------|------------------------------------------------------------------------------------------------------------------------------------------|
| `docker/web/site/app.js`                  | Flag-independent `loadHub` published-hub-body fetch; `HUB_STORYLINE` fallback intact; placeholders intact | VERIFIED | `current_body_version_id` fetch at lines 514-519 (outside any `PREVIEW_ENABLED` guard); `HUB_STORYLINE` constant at line 32 still present and referenced at line 628; both `__SUPABASE_URL__`/`__SUPABASE_ANON_KEY__` placeholders confirmed (grep count = 2); JS syntax valid (node --check exits 0) |
| `scripts/publish_economy_map_batch.py`    | Operator-gated batch publish: resolve 8 drafts → manifest → RPC loop; idempotent + fail-loud (448 lines, min 120) | VERIFIED | 448 lines; `publish_block_version` RPC present; `PUBLISH_ORDER` lists exactly 8 slugs (hub last, D-07); `regulation-legal` absent (REGLEGAL-EXCLUDED-OK); no `in_()`; `SUPABASE_KEY = SUPABASE_SERVICE_KEY or SUPABASE_KEY`; CR-01 fix: `published_pointer()` helper enables TO-PUBLISH/ALREADY-PUBLISHED/MISSING pre-flight (lines 358-375); WR-03 fix: `published_pointer(slug)` re-confirmed before SKIP (line 426); WR-02 fix: docstring softened to "newest, mig-041 guarantees ≤1" |
| `scripts/verify_economy_map_publish.py`   | Anon-key post-publish fail-loud assertions: 8 published + hub + cross-links + count 2→8 (379 lines, min 100) | VERIFIED | 379 lines; `SUPABASE_KEY = SUPABASE_ANON_KEY`; `SOURCE_SLUGS` = hub + 7 blocks; no `in_()`; WR-01 fix: `count_published_blocks()` dead function deleted; IN-02 fix: redundant hub assertion collapsed to `HUB_SLUG not in published_bodies`; **live run exits 0**: all 8 bodies published anon-visible, hub published article resolves (4202 chars), 22 cross-link instances → 7 distinct targets all resolve against PUBLISHED content, count 2→8 confirmed |

---

### Key Link Verification

| From                                                  | To                                           | Via                                                                                             | Status  | Details                                                                                                                   |
|-------------------------------------------------------|----------------------------------------------|-------------------------------------------------------------------------------------------------|---------|---------------------------------------------------------------------------------------------------------------------------|
| `loadHub` (app.js line 515-519)                       | `economy_map.block_body_versions.body_md`    | `sb.schema('economy_map').from('block_body_versions').select('body_md').eq('id', hubRow.current_body_version_id).single()` | WIRED   | Flag-independent (NOT inside `if (PREVIEW_ENABLED)`); gated on `!hubBodyMd && hubRow && hubRow.current_body_version_id`; no `.eq('status','published')` filter (D-17); graceful-degrade |
| `loadHub hubBodyMd`                                   | `renderHub trimHubBody fork` (line 625-628)  | `trimHubBody(hubBodyMd)` passed to fork; `marked.parse(trimmedHubBody)` else `HUB_STORYLINE`   | WIRED   | `trimHubBody` call confirmed at line 625; fork confirmed at lines 626-628; `HUB_STORYLINE` fallback intact                |
| `publish_economy_map_batch.py RPC loop` (line 416)    | `economy_map.publish_block_version(p_version_id)` | `_economy_map_rpc("publish_block_version", {"p_version_id": version_id})` — Content-Profile economy_map, `/rest/v1/rpc/publish_block_version` | WIRED   | `publish_block_version` confirmed in file; Content-Profile write path copied from gato_brain idiom; RPC call confirmed; post-publish dry-run confirms all 8 already-published (idempotent re-run) |
| `verify_economy_map_publish.py`                       | `economy_map` (anon-key reads)               | `_economy_map_get` with `Accept-Profile: economy_map` using `SUPABASE_ANON_KEY`                | WIRED   | `SUPABASE_ANON_KEY` confirmed at line 104; live harness exits 0 with RESULT: PASS |

---

### Data-Flow Trace (Level 4)

| Artifact                            | Data Variable     | Source                                                                                                                   | Produces Real Data | Status  |
|-------------------------------------|-------------------|--------------------------------------------------------------------------------------------------------------------------|--------------------|---------|
| `app.js loadHub` (prod published)   | `hubBodyMd`       | `sb.schema('economy_map').from('block_body_versions').select('body_md').eq('id', hubRow.current_body_version_id).single()` | Yes — live DB; 4202 chars confirmed by verify harness | FLOWING |
| `verify_economy_map_publish.py`     | `published_bodies`| PostgREST anon GET `block_body_versions` per-slug, `SUPABASE_ANON_KEY`                                                  | Yes — exits 0, 8 bodies resolved | FLOWING |
| `publish_economy_map_batch.py`      | RPC writes        | `_economy_map_rpc("publish_block_version", ...)` service_role → `economy_map.publish_block_version` RPC (mig 039)        | Yes — dry-run confirms 0 remaining drafts, 8 already-published | FLOWING |

---

### Behavioral Spot-Checks

| Behavior                                             | Command                                                             | Result                                                                                                      | Status |
|------------------------------------------------------|---------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------|--------|
| Live publish harness: 8 bodies published anon-visible | `python3 scripts/verify_economy_map_publish.py`                   | Exit 0; RESULT: PASS; 8 bodies published; hub 4202 chars; 22 cross-links → 7 targets; count 2→8            | PASS   |
| Idempotent re-run: dry-run classifies all as already-published | `python3 scripts/publish_economy_map_batch.py --dry-run` | Exit 0; "0 draft(s) to publish, 8 already published"; DRY-RUN exit 0 (no POST)                             | PASS   |
| Leak guard: placeholders intact, no service_role in web-deploy path | `python3 scripts/verify_economy_map_crosslinks.py --guard-only` | Exit 0; PLACEHOLDER-INTACT; SVC-ROLE-NOT-IN-WEB-DEPLOY-PATH                                        | PASS   |
| JS syntax valid                                      | `node --check docker/web/site/app.js`                               | Exit 0; JS-SYNTAX-OK                                                                                        | PASS   |
| agentpulse-web container running                     | `docker compose ps web --format '{{.State}}'`                       | `running`                                                                                                   | PASS   |

---

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes declared for this phase. The canonical go-live proof is `scripts/verify_economy_map_publish.py` (run above — exit 0, PUBLISH-VERIFIED-OK semantics).

---

### Requirements Coverage

| Requirement | Source Plan        | Description                                                                                              | Status | Evidence                                                                                         |
|-------------|-------------------|----------------------------------------------------------------------------------------------------------|--------|--------------------------------------------------------------------------------------------------|
| PUB-01      | 18-01, 18-02, 18-03 | Content published live via atomic publish RPC in ONE operator-approved batch; hub at #/map; blocks at #/map/<slug> with back arrow/title/subtitle/maturity pill/body | PARTIAL | Atomic publish RPC: VERIFIED. ONE operator-approved batch: VERIFIED (Gate B). Hub at #/map: VERIFIED. Back arrow/title/maturity pill/body at #/map/<slug>: VERIFIED. **Subtitle at #/map/<slug>**: UNCERTAIN (renderBlock does not emit block.subtitle — pre-existing v2.0 design; see Human Verification) |

---

### Anti-Patterns Found

| File                               | Line | Pattern                       | Severity | Impact                                                                                         |
|------------------------------------|------|-------------------------------|----------|-----------------------------------------------------------------------------------------------|
| `docker/web/site/app.js`           | 46   | `LIVE_TENSION_PLACEHOLDER = 'TBD — set via /map-tension'` | INFO     | Pre-existing intentional named constant (since Phase 2/D-21); references the `/map-tension` operator command; used as a hide-gate (line 741); NOT a debt marker — it is design-by-intent. No blocker. |

No `FIXME`, `XXX` debt markers in any phase-modified file. The `TBD` string is a named constant with a clear operator-command reference — not an unresolved debt marker per the gate rule.

---

### Human Verification Required

#### 1. Block Page Subtitle Element (ROADMAP SC-2)

**Test:** Open a published block page on the live site, e.g. `https://aiagentspulse.com/#/map/identity-trust`, and inspect whether a subtitle element (e.g. "Identity, trust, credentials — the enabling layer of the agent economy") is rendered below the block title.

**Expected (two acceptable outcomes):**
- **Outcome A — Subtitle present:** The block page renders the subtitle field as a visible element. PUB-01 SC-2 is fully satisfied literally.
- **Outcome B — Subtitle absent, operator accepts:** The block page renders title + maturity pill + body (the pre-existing v2.0 `renderBlock` design since Phase 13). The operator confirms this is the accepted "full reading surface" for this milestone — the subtitle appears on the hub card tiles but not on the deep-dive page. This is the same surface the operator approved during the Phase 17 preview click-through.

**Why human:** `renderBlock` (app.js lines 728-769) generates `block-header` (h1 title + maturity pill), optional block-tension, block-body, and Evolution. It does NOT emit `block.subtitle`. This was established in Phase 13 (commit ae6f4a3) and has never been part of the block deep-dive render. The operator-approved Phase 17 preview (`APPROVED` in 17-02-SUMMARY Task 3) covered the same block page surface. The verifier cannot determine whether the PUB-01 "subtitle" wording was aspirational (and the v2.0 design is accepted) or a genuine unmet requirement. Only the operator can confirm.

---

## Gaps Summary

All three ROADMAP Success Criteria are substantively met. The phase's canonical proof — `scripts/verify_economy_map_publish.py` (exit 0, RESULT: PASS) — confirms all 8 in-scope bodies are anon-visible and published, the hub article resolves, all 22 cross-links resolve against published content, and the count transitions 2→8 as required. The batch publish was operator-gated (manifest approval), atomic (publish_block_version RPC), fail-loud (CR-01 fix recoverable), and web-only scoped.

The single uncertainty is whether `block.subtitle` must appear as a rendered element on the `#/map/<slug>` block page to satisfy ROADMAP SC-2. This is a pre-existing v2.0 renderer gap (not introduced by Phase 18, not covered by any Phase 18 plan task) that the operator implicitly accepted during the Phase 17 block page preview. The status is `human_needed` pending operator confirmation of Outcome A or B above.

All code-review findings (CR-01, WR-01, WR-02, WR-03, IN-02) were fixed in commit `e183b75` before this verification. IN-01 and IN-03 were deliberately left advisory.

---

_Verified: 2026-06-09T10:58:38Z_
_Verifier: Claude (gsd-verifier)_
