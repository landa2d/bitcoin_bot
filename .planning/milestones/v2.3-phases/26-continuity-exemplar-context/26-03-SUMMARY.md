---
phase: 26-continuity-exemplar-context
plan: 03
subsystem: newsletter
tags: [continuity, exemplars, phase-e, voice-score, llm-proxy, claude-sonnet-4-6, deepseek, supabase, live-verification]

# Dependency graph
requires:
  - phase: 26-01
    provides: load_edition_context loader, narrative_context injection, exemplars= at both generate_from_blocks call sites, Phase E not_scored resurrection
  - phase: 26-02
    provides: deterministic fixture suite for load_edition_context
provides:
  - "Operator-confirmed data_snapshot.lead_theme on editions 25-28 (live MCP backfill); published_at verified non-null on all 7 operator editions"
  - "CTX-04 proven live: continuity context reaches the writer and produces an accurate cross-edition bridge"
  - "CTX-05 proven live: loader loads 8 exemplars, injects them via merge, Phase E scores voice_score=4 with 3 exemplar-anchored observations"
  - "Four live-surfaced bug fixes deployed (loader-authoritative merge, boolean operator_written, proxy TIMEOUT_ANTHROPIC 240s, Phase E voice-client routing)"
affects: [27-eval-persistence-governed-agent, 29-layer2-judge-feedback-rewrite-loop, 30-sequencer-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Loader-authoritative narrative_context merge ({**upstream, **loader}) — newsletter loader owns continuity metadata + exemplars; upstream keeps recent_spotlights/instruction"
    - "operator_written accepts JSON boolean true OR string 'true' (live DB stores boolean)"
    - "Phase E voice_client selected by model_voice (deepseek client for deepseek-chat, not the Anthropic prose client)"

key-files:
  created: []
  modified:
    - docker/newsletter/newsletter_poller.py
    - docker/newsletter/block_pipeline.py
    - docker/llm-proxy/proxy.py
    - tests/test_26_continuity_loader.py

key-decisions:
  - "Option C (operator-approved): loader authoritative over the processor's pre-populated narrative_context; supersedes the literal CTX-04/D-14 'upstream wins'"
  - "operator_written is a JSON boolean in the live DB (26-CONTEXT 'string true' fact was wrong — derived via PostgREST ->> which stringifies booleans)"
  - "Proxy TIMEOUT_ANTHROPIC bumped 120->240s (operator-approved scope expansion) — single-pass writer call lands at ~124-128s"
  - "Captured Phase E live via block_pipeline.enabled=true toggle (operator-approved), then reverted — single-pass writer is broken so the A/B path can't be reached"

patterns-established:
  - "Live verification surfaces fixture-invisible bugs: the loader's degrade paths passed fixtures with string 'true' but live data is boolean"

requirements-completed: [CTX-04, CTX-05]

# Metrics
duration: ~160min
completed: 2026-06-24
---

# Phase 26 Plan 03: Live Verification + lead_theme Backfill Summary

**CTX-04 + CTX-05 proven live (accurate cross-edition bridge + Phase E voice_score=4 with 8 exemplars); operator-confirmed lead_theme backfilled on editions 25-28; four live-surfaced bugs fixed; one pre-existing P1 writer bug flagged.**

## Performance

- **Duration:** ~160 min (extended by a cascade of pre-existing bugs the live trigger surfaced)
- **Started:** 2026-06-24 ~06:45Z
- **Completed:** 2026-06-24 ~09:25Z
- **Tasks:** 2 (both blocking checkpoints — orchestrator/operator-owned, no executor)
- **Files modified:** 4 (3 code + 1 test); 1 live data backfill (no migration file)

## Accomplishments

- **Task 1 — lead_theme backfill (D-12/D-13):** Derived candidate `lead_theme` strings for operator editions 25-28 from each edition's own opening thesis, operator-confirmed them, and applied via a single scoped Supabase MCP `UPDATE` (matched by row id + `operator_written` + `status='published'`; no migration file). Verified `lead_theme` non-empty on 25-28 and `published_at` non-null on all 7 operator editions (25,26,27,28,30,31,32). **This is the persistent deliverable** (survives the test-artifact cleanup).
- **CTX-04 proven live:** The continuity context reaches the writer and produced an accurate cross-edition bridge: *"Edition #32 established that sovereign actors now own the permission layer above agent commerce rails — this week the White House revealed those rails themselves have a forced upgrade deadline…"* Operator read it for prose quality (D-18) and approved.
- **CTX-05 proven live:** The loader loads 8 exemplars ("Narrative context: 3 edition(s), 8 exemplar(s)"), injects them via the Option-C merge, and Phase E returns a real `voice_score.score = 4` with 3 exemplar-anchored observations (no `not_scored`/`No exemplars` sentinel).

## Task Commits

This plan's `files_modified` was `[]` (a verify + data-backfill plan). The live trigger surfaced four pre-existing bugs that blocked the requirements; each fix was committed atomically (deviations, see below). The lead_theme backfill is a live-data mutation (no commit).

1. **Option C — loader authoritative over processor narrative_context** — `80244fe` (fix)
2. **Boolean operator_written** (loader + fixture regression case) — `6b4257f` (fix)
3. **Proxy TIMEOUT_ANTHROPIC 120→240s** — `f111b02` (fix)
4. **Phase E voice-client routing** — `ad4630d` (fix)

## Files Created/Modified

- `docker/newsletter/newsletter_poller.py` — loader-authoritative merge of `narrative_context` (Option C); `_le_is_operator_written()` accepts boolean `true`; `voice_client` selected by `model_voice` at both `generate_from_blocks` call sites.
- `docker/newsletter/block_pipeline.py` — `generate_from_blocks` gains `voice_client` param; Phase E uses `voice_client or llm_client`.
- `docker/llm-proxy/proxy.py` — `TIMEOUT_ANTHROPIC` 120→240s.
- `tests/test_26_continuity_loader.py` — canonical stub uses the real boolean type; new regression test for boolean/string/False (11/11 pass).
- **Live data:** `data_snapshot.lead_theme` on editions 25-28 (MCP UPDATE, no migration).

## Decisions Made

- **Option C (operator-approved):** the processor's `prepare_newsletter_data` pre-populates a thinner `narrative_context` (no exemplars; `primary_theme` from the always-null column; positional `weeks_ago`; un-stripped excerpt) on every live trigger, so the locked `setdefault` made the 26-01 loader a no-op. Merge so the loader's keys win while preserving the upstream's `recent_spotlights`/`instruction`. Supersedes the literal CTX-04/D-14 "upstream wins" (which guarded the now-inferior processor context).
- **Capture Phase E via the block path (operator-approved):** since the single-pass writer is broken (P1 below), the A/B Phase E path is unreachable; temporarily set `block_pipeline.enabled=true` to run Phase E as the primary path, captured `voice_score=4`, then reverted to `false`.

## Deviations from Plan

The plan was `files_modified: []` (verify + backfill). The live trigger surfaced four pre-existing, fixture-invisible bugs that each blocked CTX-04/CTX-05; all four were necessary and committed. Each was operator-checkpointed where it changed locked decisions or expanded scope.

### 1. [Operator-approved] Loader shadowed by processor pre-population (Option C)
- **Found during:** Task 2 diagnostic (before the live trigger).
- **Issue:** `prepare_newsletter_data` always sets `input_data['narrative_context']`, so the poller's locked `setdefault` discarded the loader (no exemplars; backfill never reached the bridge).
- **Fix:** loader-authoritative merge `{**upstream, **ctx}`.
- **Committed in:** `80244fe`.

### 2. [Bug fix] operator_written is a JSON boolean, not a string
- **Found during:** Task 2 first live trigger — loader logged "no operator-written exemplars" despite 7 operator editions.
- **Issue:** `jsonb_typeof(data_snapshot->'operator_written')` is `boolean`; supabase-py yields Python `True`; the loader's `== 'true'` was always False. The 26-CONTEXT "string true" fact was wrong (read via `->>`, which stringifies booleans); Plan 02 fixtures used the string form and passed.
- **Fix:** `_le_is_operator_written()` accepts boolean `True` or string `'true'`; fixture now uses the real boolean type + a regression case.
- **Committed in:** `6b4257f`.

### 3. [Operator-approved scope expansion] Proxy Anthropic timeout too low
- **Found during:** Task 2 second/third live triggers — single-pass writer call 504'd at ~124-128s.
- **Issue:** `TIMEOUT_ANTHROPIC=120s` < the writer call's ~124-128s → 504 Gateway Timeout on every attempt.
- **Fix:** bumped to 240s (still under the 300s task budget).
- **Committed in:** `f111b02`.

### 4. [Bug fix] Phase E voice call routed to the wrong client
- **Found during:** Task 2 block-path trigger — Phase E ran (8 exemplars) but 400'd: "Unknown or non-Anthropic model: deepseek-chat".
- **Issue:** `generate_from_blocks` reused the single Anthropic prose client for Phase E, but `model_voice=deepseek-chat`; `_llm_call` routes by client type, so deepseek-chat hit `/anthropic`. Latent — Phase E had never run (no exemplars).
- **Fix:** `voice_client` param selected by `model_voice` at both call sites.
- **Committed in:** `ad4630d`.

---

**Total deviations:** 4 fixes (2 operator-approved decisions/scope, 2 clear bug fixes) + 1 temporary config toggle (reverted).
**Impact on plan:** All four were necessary to satisfy CTX-04/CTX-05 live. The work expanded beyond the newsletter service (one proxy timeout line) with operator approval. No silent workarounds — each was surfaced and (where it changed a locked decision or touched a second service) operator-gated.

## Issues Encountered

### ⚠️ SEPARATE P1 — single-pass newsletter writer returns empty on large claude-sonnet-4-6 responses (NOT Phase 26; blocks Friday's edition)

- **Symptom:** the single-pass writer's `claude-sonnet-4-6` call returns **200 OK with real output** (input 83,859 / **output 4,703 tokens**, 322 sats spent) but the agent reads `response.content[0].text` as **empty** → `json.loads("")` → "Failed to parse model response as JSON: Expecting value: line 1 column 1 (char 0)" → task fails before the A/B path.
- **Evidence it's pre-existing & independent of Phase 26:** exemplars go to the block path (not the single-pass prompt); Option C *shrank* the single-pass continuity context. The small `editorial_prepass` (same model, 358 output tokens) parses fine — so it's specific to the large writer response. **No successful newsletter generation since the 2026-06-19 `claude-sonnet-4-6` model swap** (only 404/504/empty).
- **Impact:** with `block_pipeline.enabled=false` restored (single-pass primary), **Friday's real edition (2026-06-26) will fail identically.** Likely a content-block extraction issue (read the `type=='text'` block, not `content[0]` blindly) — needs reproduction with response-structure logging; do NOT fix blind.
- **Stopgap option (operator's call):** setting `block_pipeline.enabled=true` makes the block path primary (it completes and scores Phase E) until the writer bug is fixed.
- **Raised separately** (see Next Phase Readiness) — out of Phase 26 scope.

### Cleanup
- Test artifacts (synthetic editions 933-937: 5 `agent_tasks` + 2 `newsletters` drafts) deleted via MCP. `block_pipeline.enabled` reverted to `false`. lead_theme backfill (25-28) verified intact. Containers rebuilt scoped `--no-deps` (newsletter ×2, llm-proxy ×1) on the main tree, deployed code == committed.

## User Setup Required

None for Phase 26. **Operator action (separate, urgent):** decide how to handle the P1 single-pass-writer bug before Friday 2026-06-26 (fix the writer extraction, or set `block_pipeline.enabled=true` as a stopgap).

## Next Phase Readiness

- **Phase 26 complete:** CTX-01..05 delivered and verified live. The loader feeds prior-edition angles (with backfilled themes) + 8 operator exemplars to both writer paths and Phase E; Phase E is genuinely resurrected (real score, not a sentinel). Phase 29's judge has a working exemplar/continuity source.
- **Blocker for the wider product (not Phase 27):** the P1 single-pass writer bug breaks live newsletter generation. Phases 27-31 (eval persistence, gate, judge, wiring) are not blocked by it, but the operator should address it before the next real edition.
- **Deployed state:** newsletter + llm-proxy running the four fixes; processor unchanged; config restored to `enabled:false`/`ab_comparison:true`.

---
*Phase: 26-continuity-exemplar-context*
*Completed: 2026-06-24*
