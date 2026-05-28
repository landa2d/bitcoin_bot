---
created: 2026-05-28T19:55:00Z
updated: 2026-05-28T19:55:00Z
title: Phase 05 code-review advisory follow-ups (WR-02, WR-04, WR-05)
area: intake-classifier
priority: P4
phase_candidate: false
files:
  - docker/processor/agentpulse_processor.py
  - docker/newsletter/newsletter_poller.py
---

## Context

Phase 05 code review (`.planning/phases/05-intake-classifier-unsorted-handling/05-REVIEW.md`)
flagged 3 advisory warnings that do NOT drop an event or break a Phase 5 success criterion,
so they were intentionally left open after the never-drop cluster (CR-01/WR-01/WR-03) was fixed
in commit `ef310d8`. Track and address when convenient.

## WR-02 — classifier silently falls back to gpt-4o (~10-20x cost) on config-load failure
`classify_intake_event` uses `get_model("extraction")`. `get_model_config()` reads a hardcoded
`/home/openclaw/.openclaw/config/agentpulse-config.json`; on read failure it caches `{}` and
`get_model("extraction")` falls through `default → OPENAI_MODEL` (gpt-4o). Bulk classification
runs every 30 min over up to 10 editions — wrong model = big cost surprise, invisible to the
offline tests (they prime `_model_config_cache`). Fix: assert/log loudly if the resolved model
is not a deepseek model, or pin the classifier to a dedicated `classification` model key read
from the deployed config.

## WR-04 — `_clean_json_response` has no regex fallback for chatty model output
Only strips a leading ```` ``` ````. If the model emits prose then a fenced block, `json.loads`
raises → the event routes to `unsorted` (not dropped, but a correctly-classifiable event is
needlessly bucketed). The test docstring even claims a "regex fallback to extract JSON from
markdown fences" that doesn't exist. Fix: add the documented `re.search(r'\{.*\}', ..., DOTALL)`
fallback before giving up.

## WR-05 — block-pipeline-primary editions may carry no `premium_source_posts` → silent zero emit
`classify_intake_for_edition` reads tier-1 events from `data_snapshot['premium_source_posts']`.
Today this survives only because the saved snapshot is `{**input_data, **result_data_snapshot}`
(newsletter_poller.py ~1475) and `input_data` carries the posts. When the block pipeline is the
PRIMARY generation path it builds a fresh `data_snapshot` (pipeline_version/voice_score/
block_summary/block_prepass) with NO `premium_source_posts` — so a pure `block_v1` snapshot would
yield `tier1_events == []` and the timeline silently stops populating. Fix: (a) log a warning when
a `published` edition has empty `premium_source_posts`, and/or (b) derive tier-1 events from the
block snapshot structures when `pipeline_version == 'block_v1'`. Relevant because the block
pipeline is the documented production direction (`block_pipeline.enabled` cutover).

Also 3 info items in the review (IN-01 id-less edition → literal 'None' key; IN-02 error events
double-counted in run totals; IN-03 `enabled` defaults True on config-load failure) — cosmetic,
no action required.
