---
created: 2026-05-28T08:39:23Z
updated: 2026-05-28T08:55:00Z
title: Reconcile prod↔main drift and close the gap
area: tooling
phase_candidate: true
files:
  - scripts/deploy.sh
  - docker/llm-proxy/proxy.py
  - docker/llm-proxy/governance_config.json
  - supabase/migrations/023_llm_proxy_tables.sql
---

## Problem

Production (`hetzner` = 46.224.50.251, `/opt/bitcoin_bot`) has drifted behind
local `main` by multiple phases of backend work. `scripts/deploy.sh` rsyncs whole
`docker/`/`config/`/`skills/`/`templates/` from the working tree with
`--delete --checksum`, so a bare `--force-rebuild all` is unsafe. This todo
covers reconciling the gap **under approval**, not a blind deploy.

## Audit findings (2026-05-28, read-only)

**Prod DB schema is current** — `supabase_migrations.schema_migrations` shows 33
applied through `033_economy_map_schema`. The governance/proxy objects the new
code needs already exist on prod: `agent_wallets_v2`, `governance_events`, and
RPCs `get_agent_window_spending` / `reserve_agent_balance` / `settle_agent_balance`.
**So the gap is NOT un-applied migrations.** It is code + governance-data + behavior:

1. **llm-proxy governance refactor (the landmine).** Prod's running `proxy.py` reads
   per-agent caps from the file `docker/llm-proxy/governance_config.json`
   (analyst 28000/day, processor 1000/day, research 5000/wk, newsletter 2000/wk,
   gato 50000/day with `downgrade_model`). Local/main `proxy.py` instead reads
   caps from `agent_wallets_v2` (`spending_cap_sats`/`spending_cap_window`) + the
   window RPC + logs `governance_events`. But the **data in `agent_wallets_v2` is
   incomplete/inconsistent** vs the file: analyst=1000 (≠28000); processor,
   research, newsletter, gato = **null**. Deploying the new proxy.py as-is would
   tighten analyst, **drop caps entirely for processor/research/newsletter/gato**,
   and lose gato's downgrade behavior — silent governance-off.
2. **Services behind main (legit local-ahead, all committed):** `gato_brain` code
   engine (`code_commands`, `code_session`, `cto_commands`, `repo_resolver`) +
   `gato_brain.py`; `newsletter` block pipeline (`block_pipeline`, `block_selection`,
   `verification`) + poller; `processor`, `analyst`, `research`, `gato` Dockerfile/
   entrypoint; `config/x_source_accounts.json` (new); `skills/*`, `templates/*`.
3. **New service:** `lab-data-provider` exists in local `docker-compose.yml`, not on
   prod — deploying the full compose adds a new prod container. (Also note an
   unrelated anomaly: `agent_wallets_v2.rivalscope` balance is ~ -251922 sats.)

## Already done (repo-side cleanup, committed 5f6fadc — NO prod change)

- Pulled prod's `governance_config.json` into the repo → deploy no longer
  `--delete`s the file prod's current proxy depends on. The committed file is also
  the **canonical source of the per-agent caps** to reconcile into `agent_wallets_v2`.
- Removed stray tracked `docker/docker-compose.yml.save`; gitignored `*.save`.
- `deploy.sh` now excludes `*.pyc`/`__pycache__/`/`*.save` from every rsync.
- Verified: post-cleanup deploy delta contains only real tracked source (no
  governance deletion, no artifacts).

## Solution (the remaining planned phase)

Reconcile + deploy per service group, under approval, migration/data-first:

1. **llm-proxy governance — atomic unit, HARD CONSTRAINT:** ship the cap data +
   `proxy.py` as ONE atomic schema/data-then-code unit. Backfill `agent_wallets_v2`
   caps from `governance_config.json` (decide canonical values where they differ,
   e.g. analyst 1000 vs 28000) and reproduce gato's `downgrade_model` behavior in
   the new model BEFORE/with the proxy deploy. **`proxy.py` must FAIL LOUDLY** (halt
   / refuse to serve) if an expected cap is absent — it must NOT fall through to
   `wallet.get(...) is None` → ungoverned. Silent governance-off is "the wallet bug
   all over again" and is unacceptable. Then the obsolete `governance_config.json`
   can be removed as part of the same unit.
2. **Other service groups:** deploy gato_brain / newsletter / processor / analyst /
   research per group with a scoped rsync + `docker compose build/up <svc>` (never
   bare `--force-rebuild all`); review each group's behavior before shipping.
3. **lab-data-provider:** conscious decision to add the new container (or exclude it).
4. **Close the gap + guardrails:** once reconciled, prod == main; keep the deploy
   excludes; consider a deploy preflight that flags unexpected `--delete` targets and
   forbids the bare full deploy.

## Suggested entry point

`/gsd-discuss-phase` or `/gsd-add-phase "prod↔main reconciliation + llm-proxy
governance migration (file→DB) shipped atomically with fail-loud caps"` — feed this
file in as context.
