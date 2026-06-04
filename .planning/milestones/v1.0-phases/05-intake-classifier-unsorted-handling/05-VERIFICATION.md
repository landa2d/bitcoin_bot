---
phase: 05-intake-classifier-unsorted-handling
verified: 2026-05-28T19:55:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  note: initial verification (no prior VERIFICATION.md)
---

# Phase 5: Intake Classifier + `unsorted` Handling Verification Report

**Phase Goal:** The newsletter pipeline autonomously emits classified, fully-traceable timeline entries; low-confidence entries land in `unsorted` rather than being dropped or guessed.
**Verified:** 2026-05-28T19:55:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

Goal-backward result: the codebase delivers the phase goal. The autonomous emission path exists end-to-end and is wired into the processor schedule; the route decision routes below-floor and error events to `unsorted` (never drops); every entry carries `source_edition_id`; the append-only invariant is structurally enforced by the migration-033 trigger; and the classifier call routes through the llm-proxy (no direct DeepSeek SDK call). The "never-drop" holes found in code review (CR-01 / WR-01 / WR-03) have been closed in commit `ef310d8` (HEAD of `main`) with two added regression tests that pass.

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | When an edition's tier-1 events/clusters are finalized, a timeline candidate is emitted per event (INTK-01) | ✓ VERIFIED | `classify_intake_for_edition` (processor:3073) iterates `data_snapshot['premium_source_posts']` where `tier == 1` (3114), builds one entry per pending event, calls `economy_map_insert_timeline_entry(entry)` (3207). `classify_intake_poller` (3234) reads `.eq('status','published')` editions (3270) and runs the per-edition emit. Registered `schedule.every(30).minutes.do(scheduled_classify_intake)` inside `setup_scheduler()` (10263). |
| 2 | Classifier (DeepSeek V3) assigns block_slug + tag_confidence, routed through http://llm-proxy:8200, no direct SDK call (INTK-02 / SC-2) | ✓ VERIFIED | `classify_intake_event` (processor:2974) POSTs to `{LLM_PROXY_URL}/v1/chat/completions` (2997) with `Authorization: Bearer {_get_agent_api_key()}` (2998) and `model=get_model("extraction")` (==deepseek-chat). `routed_llm_call` is absent from the function body (grep count 0 in 2974-3013). Proxy stamps `X-Proxy-Request-Id` and records a `wallet_transactions` row per call. test_05a (6/6 pass) proves proxy routing; test_05_intake Test D (live, skips off-network) machine-verifies the wallet_transactions increment. |
| 3 | tag_confidence >= 0.6 → named block; below floor → 'unsorted' (INTK-03) | ✓ VERIFIED | Floor read from config `intake_classifier.confidence_floor=0.6` (config verified; poller 3250). Route: `if conf is not None and conf >= floor and slug in allowed_slugs: target_slug = slug else target_slug = 'unsorted'` (3178-3181). Below-floor records `tag_confidence` (flagged-not-dropped, D-05/D-07). Test `test_below_floor_routes_to_unsorted_with_recorded_confidence` PASS. |
| 4 | Every emitted entry carries source_edition_id (INTK-04, SQL-joinable traceback) | ✓ VERIFIED | Entry dict sets `'source_edition_id': edition_id` where `edition_id = str(edition.get('id'))` (3094, 3203). Column `source_edition_id TEXT` exists on `economy_map.timeline_entries` (migration 033:155). |
| 5 | UPDATE of a prior entry fails; corrections require new INSERTs (append-only, INTK-05) | ✓ VERIFIED | `economy_map.timeline_entries_append_only()` (migration 033:213) RAISEs on DELETE (220) and on every content-column UPDATE — block_slug, event_date, what_shifted, why_it_mattered, source_url, source_edition_id, tag_confidence (224-243); trigger `BEFORE UPDATE OR DELETE ON economy_map.timeline_entries` (252). No UPDATE/DELETE helper exists in the processor (write surface scoped to INSERT-only). Test `test_append_only_trigger_rejects_update_and_delete` PASS (structural); live mutation check opt-in behind `INTK05_LIVE_DB=1`. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `config/agentpulse-config.json` | `intake_classifier.confidence_floor=0.6`, `enabled=true` | ✓ VERIFIED | Parsed: floor=0.6, enabled=True. |
| `docker/processor/agentpulse_processor.py` — `economy_map_insert_timeline_entry` | INSERT helper, `Content-Profile: economy_map`, raises on non-2xx | ✓ VERIFIED | processor:573; Content-Profile header present, `Prefer: return=representation`, raises on non-2xx. No `.schema()`/`.in_()`. |
| `economy_map_edition_already_emitted` | existence-check, `Accept-Profile: economy_map`, bool | ✓ VERIFIED | processor:600; Accept-Profile header, returns bool, raises on non-2xx. |
| `economy_map_emitted_event_keys` | per-event idempotency keys (CR-01 fix) | ✓ VERIFIED | processor:629; returns `set[str]` keyed on source_url/what_shifted; enables partial-edition completion on retry. |
| `INTAKE_CLASSIFIER_PROMPT` + `INTAKE_CLASSIFIER_SYSTEM_MSG` | classify-only, anti-injection | ✓ VERIFIED | processor:1749/1779; `{event}`/`{allowed_slugs}` placeholders, SECURITY section frames event text as untrusted data (T-05-01). |
| `classify_intake_event` | proxy-routed classifier returning {block_slug, tag_confidence}, raises on failure | ✓ VERIFIED | processor:2974; routes to llm-proxy, no internal `unsorted` fallback, raises on failure. |
| `classify_intake_for_edition` | per-edition emit + floor routing + fail-loud unsorted | ✓ VERIFIED | processor:3073; field mapping D-04, floor routing INTK-03, fail-loud D-05, WR-01 range check, CR-01 partial-insert RuntimeError. |
| `classify_intake_poller` | orchestrator over published editions + WR-03 key guard | ✓ VERIFIED | processor:3234; reads `status='published'`, fail-loud agent-key guard (3258), per-edition try/except. |
| `scheduled_classify_intake` + registration | thin wrapper + one schedule line | ✓ VERIFIED | processor:9834 wrapper; `schedule.every(30).minutes.do(scheduled_classify_intake)` at 10263 inside `setup_scheduler()`. |
| `tests/test_05a_intake_classifier.py` | classifier unit tests | ✓ VERIFIED | 6/6 pass standalone. |
| `tests/test_05_intake.py` | append-only + routing + proxy-evidence tests | ✓ VERIFIED | 5 pass / 2 skip (intentional opt-in) / 0 fail standalone. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `setup_scheduler()` | `scheduled_classify_intake` | `schedule.every(30).minutes.do(...)` | WIRED | One registration, line 10263, inside setup_scheduler (10231-10348). |
| `scheduled_classify_intake` | `classify_intake_poller` | direct call in try/except | WIRED | processor:9842. |
| `classify_intake_poller` | `public.newsletters status=='published'` | `.eq('status','published')` | WIRED | processor:3270; only finalized editions read. |
| `classify_intake_poller` | `classify_intake_for_edition` | per-edition call | WIRED | processor:3280. |
| `classify_intake_for_edition` | `classify_intake_event` (proxy) | per-event call | WIRED | processor:3146. |
| `classify_intake_for_edition` | `economy_map.timeline_entries` INSERT | `economy_map_insert_timeline_entry` | WIRED | processor:3207. |
| `classify_intake_event` | `http://llm-proxy:8200/v1/chat/completions` | httpx.post + agent key | WIRED | processor:2997; no routed_llm_call (SDK) path. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `classify_intake_for_edition` | `tier1_events` | `edition.data_snapshot['premium_source_posts']` filtered `tier==1` | Yes — real published-edition snapshot rows | ✓ FLOWING |
| `classify_intake_for_edition` | `target_slug`/`tag_confidence` | `classify_intake_event` proxy response | Yes — DeepSeek via llm-proxy (live), deterministic stub in tests | ✓ FLOWING |
| INSERT entry | full row dict | mapped from event fields + derived event_date + edition id | Yes — every field populated; source_url/tag_confidence nullable by design | ✓ FLOWING |

Note (advisory, WR-05): the tier-1 source is `premium_source_posts`. When the block pipeline becomes the *primary* generation path, a `block_v1`-only snapshot may lack `premium_source_posts`, yielding zero emit. Today's saved snapshot is `{**input_data, **result_data_snapshot}` so `premium_source_posts` survives — data flows. This is a known future-state robustness follow-up (see Anti-Patterns / Known Follow-ups), not a current break.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Processor parses (no syntax error after fixes) | `python3 -c "ast.parse(...)"` | syntax OK | ✓ PASS |
| Config exposes floor + enabled | `python3 -c json.load` | floor=0.6, enabled=True | ✓ PASS |
| Classifier unit tests | `python3 tests/test_05a_intake_classifier.py` | All 6 passed | ✓ PASS |
| Spine guarantee tests | `python3 tests/test_05_intake.py` | 5 passed, 2 skipped, 0 failed | ✓ PASS |
| Below-floor → unsorted (recorded conf) | test_below_floor_routes_to_unsorted_with_recorded_confidence | PASS | ✓ PASS |
| Error → unsorted (NULL conf) | test_classifier_error_routes_to_unsorted_with_null_confidence | PASS | ✓ PASS |
| Out-of-range conf → unsorted/NULL (WR-01) | test_out_of_range_confidence_routes_unsorted_null | PASS | ✓ PASS |
| Partial-insert fails loud, retry completes (CR-01) | test_partial_insert_failure_fails_loud_then_retry_completes | PASS | ✓ PASS |
| Append-only trigger rejects UPDATE+DELETE | test_append_only_trigger_rejects_update_and_delete | PASS (structural) | ✓ PASS |
| Live append-only mutation check | INTK05_LIVE_DB=1 gate | SKIP (opt-in; production-safety) | ? SKIP |
| Live proxy-routing evidence | wallet_transactions increment | SKIP (proxy unreachable off docker net) | ? SKIP |

The two SKIPs are intentional opt-in live checks, not failures. The structural append-only proof and the offline route-decision tests fully cover criteria 3, 5, and D-05 machine-verifiably. The live proxy test made a real `agent_api_keys` HTTP 200 fetch before cleanly skipping on proxy DNS — the skip mechanism works.

### Probe Execution

No conventional `scripts/*/tests/probe-*.sh` probes are declared for this phase; verification is via the two standalone test files (run above). N/A.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| INTK-01 | 05-02 | Emit timeline candidates per finalized tier-1 event | ✓ SATISFIED | `classify_intake_for_edition` emits one row per tier-1 event; poller scheduled. Truth #1. |
| INTK-02 | 05-01 | Classifier (DeepSeek V3, via llm-proxy:8200) assigns block_slug + tag_confidence | ✓ SATISFIED | `classify_intake_event` proxy-routed. Truth #2. |
| INTK-03 | 05-02 | >=0.6 → block timeline; below → unsorted | ✓ SATISFIED | Floor routing 3178-3181; below-floor records confidence. Truth #3. |
| INTK-04 | 05-02 | Every entry carries source_edition_id | ✓ SATISFIED | Entry dict 3203; column exists. Truth #4. |
| INTK-05 | 05-03 | Append-only — corrections are new entries, never mutations | ✓ SATISFIED | Migration-033 trigger rejects UPDATE/DELETE; no UPDATE/DELETE helper. Truth #5. |

All 5 requirement IDs declared in plan frontmatter (05-01: INTK-02; 05-02: INTK-01/03/04; 05-03: INTK-05) are accounted for and map 1:1 to the REQUIREMENTS.md Phase 5 set (INTK-01..05). No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | No TBD/FIXME/XXX/HACK/PLACEHOLDER in intake code regions | — | Clean. No debt markers. |

No blocker anti-patterns. No `routed_llm_call` (SDK) in the classifier body; no `.schema()`/`.in_()` in the economy_map helpers; no UPDATE/DELETE write surface. The `'unsorted'` literal and "not used" mentions of `routed_llm_call`/`max_source_tier` appear only in docstrings/comments, not executable paths.

### Known Follow-Ups (advisory — do NOT block the phase goal)

From 05-REVIEW.md, the "never-drop" cluster (CR-01, WR-01, WR-03) is FIXED in commit `ef310d8` (HEAD of `main`) with two new passing regression tests. Three review warnings remain OPEN as advisory robustness improvements; none drops an event or breaks a success criterion, so none fails the phase goal:

- **WR-02** — `get_model("extraction")` falls back to `gpt-4o` (~10-20x cost) if the deployed config path fails to load. Cost/observability concern, not a correctness break; recommend a loud warning or pinning the classifier model. (IN-03 related: `enabled` defaults to True on config-load failure.)
- **WR-04** — `_clean_json_response` lacks a regex `{...}` fallback; a chatty model response would route to `unsorted` (not dropped) but needlessly inflate the unsorted bucket.
- **WR-05** — If the block pipeline becomes the *primary* generation path, a `block_v1`-only snapshot may lack `premium_source_posts` → silent zero emit. Currently masked by the `{**input_data, **result}` snapshot merge; recommend an observability guard when `tier1_events == []`.
- Info items IN-01 (`str(None)` id guard), IN-02 (error events double-counted in run totals) are cosmetic.

These should be tracked as follow-up work (ideally a referenced issue) but are out of scope for the Phase 5 goal as defined by the five success criteria.

### Human Verification Required

None required for goal acceptance. All five success criteria are machine-verified (structural append-only proof + offline route-decision tests + proxy-routing unit tests). The two optional live checks (`INTK05_LIVE_DB=1` mutation attempt; live proxy wallet_transactions increment) are opt-in and can be run post-deploy by the operator if a runtime end-to-end confirmation is desired, but they are not blockers — the structural and offline proofs already cover the criteria.

Operator runtime smoke (optional, post `docker compose up -d --build processor`): publish/observe an edition with tier-1 `premium_source_posts` and confirm `timeline_entries` rows appear within the 30-min poll window, each joinable via `source_edition_id`, with an llm-proxy `wallet_transactions` row per classification.

### Gaps Summary

No gaps. The phase goal is achieved in the codebase: the intake path autonomously emits classified, fully-traceable timeline entries (per published edition, per tier-1 event), routes low-confidence and classifier-error events to `unsorted` (never dropped, confidence recorded or NULL), stamps `source_edition_id` on every row, and the append-only invariant is enforced structurally by the migration-033 trigger. The classifier is proxy-routed (no direct SDK call), satisfying the governance constraint. The review-identified never-drop holes are closed and regression-tested. Remaining open review items are advisory robustness follow-ups that do not fail any of the five success criteria.

---

_Verified: 2026-05-28T19:55:00Z_
_Verifier: Claude (gsd-verifier)_
