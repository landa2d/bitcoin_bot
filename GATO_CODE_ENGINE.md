# Gato Code Engine — Code from Telegram

**Deployed**: 2026-03-23
**What it does**: Lets you code from your phone via Telegram slash commands. Send an instruction, Claude Code runs headless, you review the diff, then approve or reject.

---

## Commands

| Command | What it does | Timing |
|---------|-------------|--------|
| `/code <repo> <instruction>` | Start a coding session | Async (1-15 min). Returns ack immediately, pushes result when done |
| `/diff` | Show diff from latest session | Sync (instant) |
| `/approve` | Commit + push + create GitHub PR | Sync (5-30s) |
| `/reject` | Discard all changes, delete branch | Sync (instant) |
| `/followup <instruction>` | Continue session with new instruction | Async (1-15 min) |
| `/repos` | List registered repos | Sync (instant) |
| `/code-status` | Show latest session status | Sync (instant) |

All commands default to the latest session — no need to type UUIDs.

---

## Example Flow

```
You:  /code lab create a hello world script
Gato: Starting code session on lab... I'll push the result when it's done.

[2 minutes later, Gato pushes:]
Gato: Code session complete. [shows diff + summary]

You:  /diff
Gato: [shows full diff]

You:  /followup add error handling and a docstring
Gato: Running followup... I'll push when done.

You:  /approve
Gato: Approved. PR: https://github.com/...

-- OR --

You:  /reject
Gato: Rejected. Changes discarded, branch deleted.
```

---

## Architecture: What Was Built

### The Problem
- `code_session.py` (the Claude Code CLI wrapper) existed on the host at `~/lab/results/code-repos-registry/`
- It shells out to `claude --dangerously-skip-permissions --print` which needs Node.js
- Gato Brain runs in a Python 3.12-slim Docker container with no Node.js
- Needed to bridge Telegram messages to the code engine

### The Solution

**Installed Node.js + Claude CLI inside the gato_brain container.** This keeps everything self-contained.

### Files Created

| File | Purpose |
|------|---------|
| `docker/gato_brain/code_commands.py` | Telegram command handlers. Dispatches `/code`, `/diff`, etc. Long-running ops use background threads + Telegram push for results |
| `docker/gato_brain/code_session.py` | Copied from lab, adapted paths for container (`ENV_PATH`, `LOCAL_SESSIONS_DIR`). Removed `su labuser` logic and `notify_telegram()` calls (code_commands.py handles notifications) |
| `docker/gato_brain/repo_resolver.py` | Copied from lab, adapted `ENV_PATH` for container |
| `supabase/migrations/025_code_sessions.sql` | DDL for `code_sessions` table (applied to Supabase) |

### Files Modified

| File | What changed |
|------|-------------|
| `docker/gato_brain/Dockerfile` | Added Node.js 22, git, `npm install -g @anthropic-ai/claude-code`. Removed `USER openclaw` (needs root for repo write access + Claude credentials). Added COPY for code engine files |
| `docker/gato_brain/entrypoint.sh` | Added `mkdir -p /root/code-workspaces/.sessions` |
| `docker/gato_brain/requirements.txt` | Added `bcrypt>=4.0.0` (used by code_session.py wallet creation) |
| `docker/gato_brain/gato_brain.py` | Added `import code_commands`. Added routing block after `/x-*` commands (line ~1512): prefix-matches `/code`, `/diff`, `/approve`, `/reject`, `/followup`, `/repos` and dispatches to `code_commands.handle_code_command()`. Updated `/commands` help text |
| `docker/gato/inject-gato-brain.mjs` | Added `isCodeCommand` regex to route code commands to gato_brain (not OpenClaw). Updated fallthrough guards. Added CODE ENGINE section to `/commands` help. Bumped timeout 30s -> 45s |
| `docker/docker-compose.yml` | Added volume mounts: `/root/.claude` (Claude credentials), `/root/lab`, `/root/bitcoin_bot`, `/root/code-workspaces`. Bumped memory 512m -> 1536m |

### How It Works (Data Flow)

```
1. Telegram message "/code bot fix the bug"
      |
2. grammY middleware (inject-gato-brain.mjs)
   - Regex matches /code → isCodeCommand = true
   - POSTs to http://gato_brain:8100/chat
      |
3. gato_brain.py /chat endpoint
   - Prefix check: "/code".startswith(any of _code_prefixes) → true
   - Calls code_commands.handle_code_command(message, user_id)
      |
4. code_commands.py _handle_code_start()
   - Checks admin (TELEGRAM_OWNER_ID)
   - Acquires _code_lock (prevents concurrent sessions)
   - Returns "Starting code session..." immediately (shown in Telegram)
   - Spawns background thread:
        |
5. Background thread runs:
   subprocess.run(["python3", "code_session.py", "start", "--repo", "bot", ...])
        |
6. code_session.py
   - Resolves repo via repo_resolver.py (Supabase code_repos table)
   - Creates git branch
   - Creates proxy wallet for cost tracking
   - Runs: claude --dangerously-skip-permissions --print --max-budget-usd 3.00 "..."
   - Captures diff, summary, files changed
   - Updates code_sessions table in Supabase
   - Prints results to stdout
        |
7. Background thread captures stdout
   - Pushes result to Telegram via Bot API (sendMessage)
   - Releases _code_lock
```

### Key Design Decisions

1. **Container runs as root** — needed for Claude credentials at `/root/.claude/` and write access to repos at `/root/lab/`, `/root/bitcoin_bot/`
2. **Long commands use background threads** — `/code` and `/followup` return an ack instantly, push results via Telegram API when done (avoids 30s middleware timeout)
3. **Short commands are synchronous** — `/diff`, `/approve`, `/reject`, `/repos` return directly in the HTTP response
4. **No session ID required** — all commands default to the latest session, so you don't have to type UUIDs on your phone
5. **One session at a time** — `threading.Lock()` prevents concurrent Claude Code runs
6. **Removed duplicate notifications** — code_session.py's `notify_telegram()` calls were removed since code_commands.py handles pushing results

### Supabase Tables

- `code_repos` — repo registry (alias, local_path, github_remote, etc.)
- `code_sessions` — session state (status, instruction, diff, PR URL, cost, etc.)

### Security

Only `TELEGRAM_OWNER_ID` can use code commands. All others get "Code commands are restricted to the operator."
