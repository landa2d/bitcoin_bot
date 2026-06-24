---
created: 2026-06-24T13:40:00Z
updated: 2026-06-24T13:40:00Z
title: single-pass newsletter writer parses claude-sonnet-4-6 large response as empty (breaks live generation)
area: newsletter
priority: P1
phase_candidate: false
files:
  - docker/newsletter/newsletter_poller.py
---

## Problem (P1 — blocks the real Friday edition)

Surfaced by Phase 26 Plan 03's live trigger on 2026-06-24. The single-pass newsletter writer's
`claude-sonnet-4-6` call **succeeds upstream** but the agent reads its response as empty:

- `POST https://api.anthropic.com/v1/messages → 200 OK`; `llm_call_log`: input **83,859** / output **4,703** tokens; ~322 sats settled — real content was generated.
- The agent does `text = response.content[0].text.strip()` (`newsletter_poller.py:1242`), gets `""`, then `json.loads("")` → `Failed to parse model response as JSON: Expecting value: line 1 column 1 (char 0)` → task marked `failed` (line ~2603) BEFORE the A/B path.
- The small `editorial_prepass` call (same model, ~358 output tokens, same `content[0].text` extraction at :1042) parses **fine** — so the failure is specific to the LARGE writer response.
- **No successful `write_newsletter` task since the 2026-06-19 `claude-sonnet-4-6` model swap** (quick 260619-ko8). `agent_tasks` shows the last `completed` write_newsletter on 2026-06-19 11:00 (pre-swap); everything since is 404 (mid-swap)/504/empty.

## Impact

With `block_pipeline.enabled=false` (the restored live config), the real **Friday 2026-06-26** edition
will fail identically (single-pass is primary; A/B Phase E never reached because single-pass crashes first).

## Likely cause + fix direction (do NOT fix blind)

4,703 output tokens exist but `content[0].text` is empty → the text is almost certainly NOT at
`content[0].text` (e.g. a non-text first content block, or a response-shape difference for large
`claude-sonnet-4-6` completions). Reproduce with response-structure logging
(`[(b.type, len(getattr(b,'text','') or '')) for b in response.content]`) before changing the
extraction. Candidate fix: `text = "".join(b.text for b in response.content if getattr(b,'type','')=='text').strip()`
applied at all four `content[0].text` sites (`:774, :1042, :1242, :1440`). Verify against a real generation.

## Stopgap (de-risk Friday without the fix)

Set `block_pipeline.enabled=true` in `config/agentpulse-config.json` — the block path completes and
scores Phase E (proven live 2026-06-24, edition 937, voice_score=4). Block path uses smaller per-section
Sonnet calls that parse fine. Trade-off: block-path output differs from single-pass; an editorial call.

## Not a Phase 26 gap

Phase 26 (continuity + exemplars) is verified PASSED — its mechanism is proven via the block path.
This bug is pre-existing (model-swap fallout) and independent. See `26-03-SUMMARY.md` → Issues Encountered.
