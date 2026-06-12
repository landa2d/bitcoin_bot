---
phase: quick-260612-kh9
plan: 01
subsystem: governance
tags: [llm-proxy, docker-compose, fail-loud, ws-01, ws-02, ws-14, ws-24, ws-25]
requires: []
provides:
  - x-proxy-env compose anchor (single source of proxy wiring for 6 Python services)
  - fail-loud require_env guards in all 5 Python service mains
  - proxy-only LLM clients (zero direct-SDK fallback paths)
affects: [docker-compose, processor, gato_brain, research, analyst, newsletter, web-entrypoint]
key-files:
  modified:
    - docker/docker-compose.yml
    - docker/web/entrypoint.sh
    - docker/processor/agentpulse_processor.py
    - docker/gato_brain/gato_brain.py
    - docker/research/research_agent.py
    - docker/analyst/analyst_poller.py
    - docker/newsletter/newsletter_poller.py
    - .claude/settings.local.json
decisions:
  - "docker/.env -> ../config/.env symlink as compose interpolation source (planner-verified gap; gitignored, host-bootstrap fact)"
  - "processor health check re-pointed from api.deepseek.com/api.openai.com to llm-proxy health endpoint (LLM path is proxy-only now)"
metrics:
  duration: ~14min
  completed: 2026-06-12T15:11:00Z
  tasks: 3
  commits: 2
---

# Quick Task 260612-kh9: Audit Spec 02 — Proxy Governance Wiring Summary

**One-liner:** All LLM traffic structurally proxy-routed — x-proxy-env compose anchor + ${LLM_PROXY_*_KEY:?} interpolations replace 4 hardcoded ap_ literals, direct-SDK fallbacks deleted from gato_brain/research, processor OpenAI traffic governed (proven end-to-end), require_env fail-loud guards in all 5 service mains.

## Task Commits

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Compose single-sourcing + web guards + key-literal scrub | `9587ca6` | docker-compose.yml, web/entrypoint.sh, .claude/settings.local.json (+ docker/.env symlink, gitignored) |
| 2 | Fail-loud code guards, proxy-only clients | `1fd56ca` | agentpulse_processor.py, gato_brain.py, research_agent.py, analyst_poller.py, newsletter_poller.py |
| 3 | Sequential rebuilds + live acceptance | no commit (deploy/verify only) | — |

## ORCHESTRATOR HANDOFF — Governed-Call Proof (AC-2 / WS-01)

- **Request timestamp (UTC):** `2026-06-12T15:09:37Z`
- **Model:** gpt-4o-mini via `routed_llm_call()` inside the rebuilt processor container
- **Printed completion:** `governed`
- **Response id:** `chatcmpl-Dpxntb4mQ6eLRG9Zktvyjnb2v3wWY`
- **Request path observed:** `POST http://llm-proxy:8200/v1/chat/completions "HTTP/1.1 200 OK"` (from inside processor)
- **Proxy-side evidence (15:09:43–44 UTC):** `PATCH .../agent_registry?agent_name=eq.processor 200` + `GET .../agent_wallets_v2?...agent_name=eq.processor 200` (auth + wallet reserve path for agent `processor`)
- **Orchestrator action:** verify the settled `wallet_transactions` row for agent `processor` at/after the timestamp above via MCP. Executor did NOT query Supabase (per plan).

## Startup-Guard Proof (AC-3 / WS-24)

```
timeout 30 docker compose run --rm --no-deps -e LLM_PROXY_URL= processor \
  python3 /home/openclaw/agentpulse_processor.py --task health_check
exit=1
RuntimeError: missing required env: LLM_PROXY_URL
```

Exit non-zero within ~5s; empty string correctly treated as missing.

## Verification Results (trimmed)

**Task 1 gate** — all conditions pass:
- `docker compose config --quiet` passes; with `env -i` (clean shell), all 6 `AGENT_API_KEY` values resolve to ap_ keys via the `docker/.env -> ../config/.env` symlink (no contingency needed — symlink parsed fine).
- Rendered processor env: `OPENAI_BASE_URL: http://llm-proxy:8200/v1`, `DEEPSEEK_BASE_URL: http://llm-proxy:8200/v1`, `LLM_PROXY_URL: http://llm-proxy:8200`.
- Anchor merged into exactly 6 services (analyst, gato_brain, lab-data-provider, newsletter, processor, research); llm-proxy/gato/web untouched (llm-proxy keeps `DEEPSEEK_BASE_URL: https://api.deepseek.com` from env_file — intended, real provider).
- `git grep -E 'ap_[a-z_-]+_[0-9a-f]{32}' -- ':!*.md' | wc -l` = **0**.
- `sh -n entrypoint.sh` OK; settings.local.json valid JSON (1 entry removed, 94 remain).

**Task 2 gate** — `PASS` (all 5 files parse; `def require_env` exactly once per file; ANTHROPIC_AGENT_KEY gone from gato_brain+research; claude_client gone from research; every `OpenAI(`/`anthropic.Anthropic(` construction carries explicit `base_url`; `api.deepseek.com` gone from processor).

**Task 3 gate** — `PASS`. Final `docker compose ps`: all 5 healthchecked services (processor, gato_brain, research, analyst, newsletter) healthy; lab-data-provider healthy; llm-proxy healthy; web Up >15s serving (entrypoint guards passed). Startup logs confirm: processor "OpenAI/DeepSeek client initialized via proxy", gato_brain "Claude/Corpus probe/DeepSeek client initialized via proxy", research "Proxy-routed Anthropic client initialized".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2] Processor health check probed real providers the processor no longer talks to**
- **Found during:** Task 2 (gate `! grep -q 'api.deepseek.com'` failed on line ~11022)
- **Issue:** `run_health_checks()` did TCP-reachability probes against `api.deepseek.com` / `api.openai.com` — not LLM client URLs (no keys sent), but stale dependencies after the proxy-only cutover.
- **Fix:** replaced both with one probe of `{LLM_PROXY_URL}/v1/proxy/health` (the processor's actual LLM dependency); `x_api` probe kept (tweepy IS a direct dependency). Results dict keys are consumed generically (summary counts + alert lines), so no downstream breakage.
- **Commit:** `1fd56ca`

### Verification-gate false positives (documented, not code changes)

**2. Task 1 awk extraction is degenerate:** `awk '/^  processor:/,/^  [a-z-]+:$/'` — the start line itself matches the end pattern, collapsing the range to a single line (always 0 matches). Verified the intent with an explicit line-range extraction instead: processor rendered env DOES contain `OPENAI_BASE_URL: http://llm-proxy:8200/v1`.

### Observations (no action)

**3. llm-proxy recreated during the rebuild sequence** (twice) — one-time config-hash convergence after introducing docker/.env as the interpolation source (running container predated it). Healthy after each; `docker compose up -d --dry-run` now shows NO pending recreate for llm-proxy. Brief proxy restarts (~seconds) during the window.

**4. gato has a pending config recreate** (dry-run shows it) — deliberately NOT recreated: gato is out of this plan's rebuild list, and AC-4 (gato Telegram round-trip) is operator-owned. Next full `docker compose up -d` will recreate it.

**5. Pre-existing research trigger-file permission errors** in research logs (`Permission denied: .../queue/research/research-trigger-*.json`) — known P4 carry-over ("research trigger file permissions"), untouched.

**6. settings.local.json line ~54** still contains the pre-existing Supabase service_role JWT literal inside a permitted-command string — that is the already-logged DEF-17-01 advisory (v2.1) and was explicitly out of this plan's scrub scope (plan removed only the ap_ entry).

## Host-Bootstrap Facts (not in git)

- `docker/.env -> ../config/.env` symlink created (`ln -sfn`); gitignored via `.gitignore:4` (`*.env`). Required for compose `${LLM_PROXY_*_KEY:?}` interpolation independent of shell state. **If the host is ever re-provisioned, this symlink must be recreated.**

## Operator Follow-ups

- **AC-4 (not attempted, per plan):** gato Telegram round-trip — send a message to Gato, confirm a gato_brain-generated reply (validates the tightened `${LLM_PROXY_GATO_KEY:?}` + proxy-only gato_brain clients end-to-end).
- gato container recreate pending (see Observation 4).
- Key ROTATION to new ap_ values remains deferred (LD-1); git history still contains the old literals until rotation.

## Pre-existing churn committed

`.claude/settings.local.json` had uncommitted drift before this task (permission-allowlist accumulation); committed as-is in `9587ca6` together with the ap_analyst entry scrub, per plan instruction.

## Self-Check: PASSED

- docker/docker-compose.yml, docker/web/entrypoint.sh, all 5 Python files, .claude/settings.local.json — FOUND
- Commits 9587ca6, 1fd56ca — FOUND in git log
- docker/.env symlink — FOUND (gitignored)
- All 7 plan-listed services rebuilt and Up/healthy
