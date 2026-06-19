---
quick_id: 260619-ko8
slug: swap-eol-claude-model-claude-sonnet-4-20
date: 2026-06-19
status: complete
commit: 267a6a5
---

# Quick Task 260619-ko8 — Summary

## What & why

`claude-sonnet-4-20250514` (Claude Sonnet 4) reached Anthropic **end-of-life on
June 15, 2026** and now returns `404 not_found_error`. This silently broke every
Claude-routed call system-wide since the 15th. It surfaced as "the Friday cron
didn't run": `scheduled_prepare_newsletter` **did** fire on time at 11:00 UTC and
queued the `write_newsletter` task for edition #102 — but the newsletter agent
404'd on the model and no draft was written.

Diagnosed via `/gsd-debug`-style root-cause tracing: cron fired → processor
prepared #102 → newsletter agent claimed the task → 404 on `claude-sonnet-4-20250514`
(EOL). Official drop-in replacement: `claude-sonnet-4-6` (Sonnet 4.6, same
$3/$15 pricing). Verified clean swap — no assistant prefills, no `budget_tokens`,
no extended-thinking config; the lone `temperature` is still valid on Sonnet 4.6.

## What changed

- **31 references swapped** `claude-sonnet-4-20250514` → `claude-sonnet-4-6` across
  **10 files**: `config/agentpulse-config.json`, `docker/llm-proxy/proxy.py`,
  `docker/llm-proxy/governance_config.json` (allowed_models **+** downgrade_map in
  lockstep — fail-loud governance), `docker/gato_brain/gato_brain.py`,
  `docker/newsletter/newsletter_poller.py`, `docker/newsletter/block_pipeline.py`,
  `docker/docker-compose.yml`, `docker/processor/agentpulse_processor.py`,
  `docker/research/research_agent.py`, `docker/research/entrypoint.sh` (the 10th —
  a `RESEARCH_MODEL` fallback default found by exhaustive grep, not in the original
  9-file estimate).
- Commit `267a6a5` (code + this plan). Worktrees disabled for the run (restored
  after) because the scoped Docker rebuild is worktree-unsafe.

## Verification (evidence)

- `grep -rc claude-sonnet-4-20250514 config/ docker/` → **0** remaining; new ID count 31; all JSON + Python parse.
- Scoped rebuild of `newsletter, research, processor, gato_brain, llm-proxy` — all **healthy**; newsletter init log confirms `model=claude-sonnet-4-6`.
- Re-queued edition #102 (reset the original failed cron task `eb5523d8` to `pending`). Newsletter agent re-claimed it, made **two `claude-sonnet-4-6` calls that settled with no 404**, and saved **edition #102** (`id=26ae854d-30f7-4b74-aa27-b0d0525840dc`, status=draft, 14,724 chars, theme "agent security surface cracking"). This is the live end-to-end proof the proxy→Anthropic path is restored.

## Notes / follow-ups

- The 13:08 duplicate failed task `80568762` was left as `failed` (not re-queued) to avoid a second #102 draft.
- Unrelated pre-existing bug seen in logs (not addressed here): analyst `trending_topics` insert fails with PGRST204 `why_interesting` column missing — schema-cache/migration drift, separate from this fix.
- Docs still referencing the old model ID (`CLAUDE.md`) were left untouched — not load-bearing; optional cleanup.
