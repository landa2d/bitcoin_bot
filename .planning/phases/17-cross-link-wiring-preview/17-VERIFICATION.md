---
phase: 17-cross-link-wiring-preview
verified: 2026-06-09T00:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 17: Cross-link Wiring & Preview Verification Report

**Phase Goal:** The loaded-but-unpublished content renders correctly and is fully navigable on a non-published preview route — every `#/map/<slug>` cross-block link and every hub→block click-through resolves to the right page, maturity pills render the three values, and the hub presents as the `#/map` landing without a duplicated block list — proving the content is publish-ready before any publish.
**Verified:** 2026-06-09
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                                                                 | Status     | Evidence                                                                                                                                                              |
|----|-------------------------------------------------------------------------------------------------------------------------------------------------------|------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1  | Every `#/map/<slug>` cross-block link resolves to the correct block page; hub block entries are clickable through to their deep-dive pages (SC-1)     | VERIFIED   | Harness `scripts/verify_economy_map_crosslinks.py` exits 0 — 22 instances to 7 distinct in-roster targets, none to regulation-legal. Operator click-through: APPROVED |
| 2  | Loaded-but-unpublished content renders on a non-published preview route — pills show three distinct values, cross-links and hub→block click-through work end-to-end; live site unchanged (SC-2) | VERIFIED   | Operator approved Task 3 gate in 17-02-SUMMARY: pills render emerging/contested/nascent; all 7 hub→block cards + 15 block→block links resolve; public `#/map` confirmed unchanged. Maturity "building" maps to "emerging" per P15-D-01 / Flag F-2 — this is the correct canonical pill value, not a discrepancy |
| 3  | Hub renders as `#/map` landing: thesis + two-tier framing intro above the card grid; block list appears once (cards), not duplicated as prose links (SC-3 / HUB-01) | VERIFIED   | `trimHubBody()` against 00-hub.md: drops `## Tier 1`/`## Tier 2` prose block-list (0 prose `#/map` links remaining), keeps thesis + How-to-read framing + restated-thesis tail. `renderHub` confirmed in code: `marked.parse(trimmedHubBody)` else `escapeHtml(HUB_STORYLINE)` fallback |
| 4  | No net-new UI feature introduced; existing v2.0 renderer reused (SC-4)                                                                               | VERIFIED   | Commits 0c5b82b/124d792/d241210/356cd05/9b18dc0 touch only `docker/web/site/app.js` + `scripts/verify_economy_map_crosslinks.py`. No new route, view, component, or `showView` branch added. No migration/schema/proxy/pipeline file modified |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact                                          | Expected                                                                              | Status     | Details                                                                                        |
|---------------------------------------------------|---------------------------------------------------------------------------------------|------------|------------------------------------------------------------------------------------------------|
| `docker/web/site/app.js`                          | PREVIEW_ENABLED flag; draft-fetch fallback in loadBlock; hub-body fetch + renderHub trim | VERIFIED   | All three plan gates PASS. Flag at lines 57-60; `trimHubBody()` at lines 74-85; loadBlock draft path at lines 655-668; renderHub hub-intro at lines 594-597 |
| `scripts/verify_economy_map_crosslinks.py`        | Fail-loud #/map/<slug> extraction + in-roster assertion                                | VERIFIED   | Parses; uses `Accept-Profile: economy_map` + `sys.exit`; no supabase-py `.in_()`; exits 0 against live DB |

---

### Key Link Verification

| From                                              | To                                                       | Via                                                                 | Status   | Details                                                                         |
|---------------------------------------------------|----------------------------------------------------------|---------------------------------------------------------------------|----------|---------------------------------------------------------------------------------|
| `app.js loadBlock`                                | `economy_map.block_body_versions (status='draft')`       | `sb.schema('economy_map')` draft-fetch, gated by `PREVIEW_ENABLED` | WIRED    | Gate B-1 PASS: `block_body_versions` + `.eq('block_slug')` + `.eq('status','draft')` + `.order('created_at')` + `.limit(1)` present; NOT `.single()` |
| `app.js renderHub`                                | `marked.parse(trimmedHubBody)`                           | hub-intro render replacing HUB_STORYLINE line with graceful fallback | WIRED   | Gate C PASS: `agent-economy` fetched, `marked.parse` used, `HUB_STORYLINE` fallback retained, `## Tier 1` cut-point present |
| `scripts/verify_economy_map_crosslinks.py`        | `economy_map.block_body_versions + economy_map.blocks`   | direct PostgREST + `Accept-Profile: economy_map`                    | WIRED    | Harness run exits 0: 9-slug roster loaded, 8 draft bodies read, 22 cross-links extracted and asserted in-roster |

---

### Data-Flow Trace (Level 4)

| Artifact                        | Data Variable     | Source                                                              | Produces Real Data | Status    |
|---------------------------------|-------------------|---------------------------------------------------------------------|--------------------|-----------|
| `app.js renderHub` (preview)    | `hubBodyMd`       | `sb.schema('economy_map').from('block_body_versions').eq('block_slug','agent-economy').eq('status','draft').limit(1)` | Yes — live DB query | FLOWING  |
| `app.js loadBlock` (preview)    | `bodyMd`          | `sb.schema('economy_map').from('block_body_versions').eq('block_slug',slug).eq('status','draft').limit(1)` | Yes — live DB query | FLOWING  |
| `verify_economy_map_crosslinks.py` | `roster` / `bodies` | direct PostgREST + Accept-Profile, service_role key from config/.env | Yes — exits 0, 22→7 | FLOWING  |

---

### Behavioral Spot-Checks (Step 7b)

| Behavior                                                                   | Command                                              | Result                                                                                      | Status  |
|----------------------------------------------------------------------------|------------------------------------------------------|---------------------------------------------------------------------------------------------|---------|
| Harness exits 0; 22 cross-links resolve to 7 in-roster targets             | `python3 scripts/verify_economy_map_crosslinks.py`   | Exit 0; PASS: 22→7 distinct targets, none to regulation-legal; D-02 guard PLACEHOLDER-INTACT | PASS    |
| Plan gates A/B/C all pass (PREVIEW_ENABLED, draft filters, hub trim)        | inline node -e gate script (17-01 PLAN verify blocks) | Gate A: PASS; Gate B-1: PASS; Gate C: PASS                                                 | PASS    |
| `trimHubBody` against 00-hub.md drops prose block-list                      | node -e (extract + run function against live file)   | keeps thesis: true; drops Tier 1/2: true; 0 prose #/map links remaining; keeps restated thesis | PASS  |
| Placeholders intact in tracked app.js (D-02 guard)                          | `git grep __SUPABASE_ANON_KEY__ docker/web/site/app.js` | line 5: `const SUPABASE_ANON_KEY = '__SUPABASE_ANON_KEY__';`                              | PASS    |
| No JWT literal in app.js                                                    | grep "eyJ" docker/web/site/app.js                    | 0 matches                                                                                   | PASS    |

---

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes declared or found for this phase. The fail-loud harness `scripts/verify_economy_map_crosslinks.py` serves as the automated verification contract; it was run above (exit 0).

---

### Requirements Coverage

| Requirement | Source Plan       | Description                                                                                                                                      | Status      | Evidence                                                                                 |
|-------------|-------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|-------------|------------------------------------------------------------------------------------------|
| LINK-01     | 17-01, 17-02      | Every `#/map/<slug>` cross-block link resolves + hub block entries clickable to deep-dive pages                                                   | SATISFIED   | Harness: 22 instances → 7 in-roster targets, exit 0. Operator click-through: APPROVED (all 7 hub→block + 15 block→block). Wired via `marked.parse(bodyMd)` in `renderBlock` (unchanged) |
| PREV-01     | 17-01, 17-02      | Loaded-but-unpublished content renders on a non-published preview route — pills show three values, cross-links + hub→block work end-to-end; live site unchanged | SATISFIED   | Operator approved Task 3. Preview path flag-gated (PREVIEW_ENABLED). Throwaway container (since torn down) confirmed render. Code review confirmed prod no-op. |
| HUB-01      | 17-01, 17-02      | Hub renders as `#/map` landing: thesis + two-tier framing intro above block grid; block list once (cards), not duplicated                         | SATISFIED   | `trimHubBody()` verified: 0 prose block-links in trimmed output. `renderHub` code: hub intro via `marked.parse`, falls back to `HUB_STORYLINE`. Operator click-through: APPROVED |

No orphaned requirements. PUB-01 is correctly assigned to Phase 18 (out of scope for Phase 17).

---

### Anti-Patterns Found

| File                                    | Line | Pattern              | Severity | Impact                                                                                                          |
|-----------------------------------------|------|----------------------|----------|-----------------------------------------------------------------------------------------------------------------|
| `docker/web/site/app.js`                | 46   | `TBD` marker         | INFO     | `LIVE_TENSION_PLACEHOLDER = 'TBD — set via /map-tension'` — **pre-existing** (present before the first Phase 17 commit `0c5b82b`); formal placeholder name with a command reference. Not introduced by this phase. Not a blocker. |

No TBD/FIXME/XXX markers in `scripts/verify_economy_map_crosslinks.py`. The single TBD in `app.js` is pre-existing and references the `/map-tension` command as formal follow-up work.

---

### Human Verification Required

The operator manual click-through was the blocking-human checkpoint at 17-02 Task 3 and was **completed and approved** before this verification. No further human verification is needed for this phase.

The local elevated preview container was a throwaway (127.0.0.1:8088, torn down after approval — expected per plan design). The behavioral evidence is:
- The harness run (exit 0, verified above)
- The recorded operator approval in 17-02-SUMMARY.md: "approved" after confirming HUB-01, LINK-01, PREV-01, and the spine check

---

### Key Invariant Verification

The deployed/production path (PREVIEW_ENABLED = false, no `?preview` param) is a byte-for-byte no-op:

- `PREVIEW_ENABLED` is an IIFE reading `searchParams.get('preview')`, returning `false` when the param is absent
- All three new branches (`loadHub` hub-body fetch, `loadHub` draftMaturity fetch, `loadBlock` draft-body fetch) are inside `if (PREVIEW_ENABLED)` blocks — three gates confirmed
- `hubBodyMd = null` → `trimHubBody(null)` returns `null` → `renderHub` falls back to `escapeHtml(HUB_STORYLINE)` (unchanged behavior)
- `draftMaturity = null`, `draftSlugs = null` → `renderTile` reverts to `deferred = !b.current_body_version_id` (pre-change logic)
- `bodyMd = null` → falls through to unchanged published-body path
- No economy_map write, no schema/RLS/migration change, no net-new UI feature
- `__SUPABASE_URL__` and `__SUPABASE_ANON_KEY__` placeholders intact in tracked `app.js` (git-confirmed)
- Zero JWT-shaped tokens in `app.js`

### Deferred Items

| Item                                                                      | Addressed In | Evidence                                                              |
|---------------------------------------------------------------------------|--------------|-----------------------------------------------------------------------|
| PUB-01: Gated batch publish (content not yet published live)               | Phase 18     | Phase 18 goal + SC-1: "published live via the existing atomic publish RPC in ONE operator-approved batch" |
| DEF-17-01: Pre-existing service_role key in `.claude/settings.local.json` | Out-of-scope | Not introduced by this phase; tracked in `deferred-items.md` for operator-owned credentials rotation |

---

### Gaps Summary

No gaps. All four roadmap success criteria are verified. All three requirement IDs (LINK-01, PREV-01, HUB-01) are satisfied. The production no-op invariant holds. The fail-loud harness exits 0 against the live database. Code review findings WR-01..04 + IN-03 were fixed before verification per project discipline (commit 9b18dc0, confirmed in 17-REVIEW.md status: resolved).

---

_Verified: 2026-06-09_
_Verifier: Claude (gsd-verifier)_
