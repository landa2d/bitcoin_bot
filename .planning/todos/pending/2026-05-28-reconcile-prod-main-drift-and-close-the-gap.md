---
created: 2026-05-28T08:39:23Z
title: Reconcile prod↔main drift and close the gap
area: tooling
files:
  - scripts/deploy.sh
  - docker/docker-compose.yml
  - docker/llm-proxy/governance_config.json
---

## Problem

During the Phase 4 deploy (2026-05-28), a `scripts/deploy.sh --dry-run` against
the production host (`hetzner` → `46.224.50.251`, `/opt/bitcoin_bot`) revealed
production has drifted **far** behind local `main`. The deploy script does a
directory-level `rsync -avz --delete --checksum` over `docker/`, `config/`,
`skills/`, `templates/` from the local working tree, so running the prescribed
`--force-rebuild web` would have pushed the entire accumulated delta and
restarted nearly the whole stack — not just the web container.

We sidestepped it for Phase 4 with a scoped web-only deploy (rsync `docker/web/`
only + `docker compose build web && up -d web`). The underlying drift is
**unaddressed** and will bite the next person who runs the full deploy script.

Concrete drift observed in the dry-run (itemized `rsync`):
- **`*deleting docker/llm-proxy/governance_config.json`** — exists on prod, absent
  locally; `--delete` would remove it. Could break the llm-proxy. Decide whether
  prod's copy is authoritative (pull it back into the repo) or intentionally gone.
- **`docker/docker-compose.yml` differs** — the script maps a compose change to
  "restart ALL 7 services" (lines 104-109). Any full deploy restarts everything.
- **Stray artifacts that should never deploy:** `docker/docker-compose.yml.save`,
  multiple `__pycache__/*.pyc` (gato_brain, newsletter). Likely want a
  `.deployignore`/rsync `--exclude` or `.gitignore` + cleanup.
- **Unreviewed service code ahead of prod:** `processor/agentpulse_processor.py`,
  all of `gato_brain/` (new `code_commands.py`, `code_session.py`, `cto_commands.py`,
  `repo_resolver.py`), `llm-proxy/proxy.py`, `newsletter/` (new `block_pipeline.py`,
  `block_selection.py`, `verification.py`), `research/research_agent.py`,
  `analyst/`, plus `config/x_source_accounts.json` (new), skills/templates changes.
- Also note: `config/agentpulse-config.json` has an uncommitted local change
  (`block_pipeline.ab_comparison` false→true) that a full deploy would push.

Related: prod Supabase PostgREST was also missing the `economy_map` schema in its
`db_schemas` exposure list (fixed during Phase 4 via MCP). Worth auditing whether
other prod-side config (PostgREST schemas, env, container state) has silently
diverged from what the repo assumes.

## Solution

Four-step reconciliation (do NOT just run the full deploy):

1. **Diagnose** — capture the full `scripts/deploy.sh --dry-run --force-rebuild all`
   itemized output; diff each differing file local↔prod (`ssh hetzner` +
   `git show`/`rsync -n`). Build an inventory: per file, is local or prod the
   intended source of truth?
2. **Classify** each delta as one of: (a) legit local-ahead work that *should*
   deploy, (b) stale/abandoned local change, (c) prod-only state that must be
   pulled back into the repo (e.g. `governance_config.json`), (d) artifact that
   should never deploy (`.save`, `.pyc` — add excludes/gitignore).
3. **Reconcile under approval** — per the operator's standing preference,
   present the classified inventory and get explicit go/no-go per service (or
   per group) before any prod-affecting action. No blind full-stack deploy.
4. **Close the drift gap** — once reconciled, do a clean full deploy (or commit
   prod-only files back + redeploy) so `main` == prod, then add guardrails so it
   stops recurring: rsync `--exclude` for `*.pyc`/`*.save`/`__pycache__`, a
   `--dry-run`-first habit, and possibly a CI/deploy check that fails on
   unexpected `--delete` targets.

Until then: prefer scoped per-service deploys (as done for Phase 4 web) over the
bare `scripts/deploy.sh --force-rebuild`. TBD on whether to automate a
drift-detection check.
