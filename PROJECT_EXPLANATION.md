# OpenClaw Bitcoin Agent — Plain-English Project Explanation

This project runs an “AI agent” (a program that can chat, remember things, and use tools) inside a **Docker container** (a safe, isolated box). The agent can be controlled via **Telegram**, can optionally use a **Lightning (Bitcoin) wallet** via LNbits, and can optionally participate in **Moltbook** (a social network for AI agents).

If you’re not technical, here’s the simplest way to think of it:

- **Docker** = a locked room where the agent lives and runs, separate from your computer.
- **OpenClaw** = the “agent engine” software that actually runs the AI agent.
- **Skills** = “tool instruction packs” that teach the agent how to do specific things (wallet, Moltbook, safety rules).
- **Guardrails** = rules and safety checks designed to prevent risky behavior (spending money, spamming, unsafe posts).
- **Telegram** = your remote control + chat window to talk to the agent.

---

## 1) What Docker is (in plain English)

### The problem Docker solves
Normally, installing a complicated program can be painful:
- different computers have different versions of Node/Python/etc.
- missing dependencies cause errors
- mixing multiple projects can break other software on your machine

Docker solves this by packaging the program and its dependencies into a **self-contained environment**.

### Image vs Container
- **Docker image**: a “frozen recipe + ingredients” (like a packaged meal kit).
- **Docker container**: a running copy of that image (like a cooked meal you can interact with).

You build an image once, then run containers from it.

### Why this project uses Docker
This project uses Docker mainly for:
- **Isolation**: if something goes wrong, it’s inside the container, not your whole PC.
- **Repeatability**: it runs the same way on any computer that has Docker.
- **Security**: the container runs as a non-admin user, and mounts some files read-only.
- **Clean setup**: you don’t need to install OpenClaw directly on Windows; the container does it.

---

## 2) The “big idea” of this repo (what’s inside, what’s outside)

This repository is mostly a **launcher + configuration** for OpenClaw.

**Important:** The OpenClaw software itself is NOT stored in this repo.

During the Docker build, the image:
- downloads/clones OpenClaw from GitHub
- installs dependencies
- builds it

So, your repo is like a “control panel” that says:
> “Build OpenClaw, then run it with my persona, my safety rules, and my skills.”

---

## 3) The main folders and what they mean

- `docker/`
  - `Dockerfile`: instructions to build the container image
  - `docker-compose.yml`: instructions to run the container with the right environment + file mounts
  - `entrypoint.sh`: startup script that prepares config and then starts the agent

- `config/`
  - `env.example`: template of environment variables (keys/settings)
  - `openclaw-config.json`: config template that gets filled in using your `.env`
  - `persona.md`: the agent “personality + behavioral rules”
  - `guardrails.md`: human-readable safety design notes

- `skills/`
  - `moltbook/`: “how to talk to Moltbook”
  - `wallet/`: “how to talk to LNbits wallet”
  - `safety/`: “how to do moderation/rate-limits/approvals”

- `scripts/`
  - `start.ps1`, `stop.ps1`, `logs.ps1`: convenience scripts for Windows PowerShell

- `data/openclaw/`
  - This is created/runs locally on your machine and stores the agent’s **persistent state**
  - Think of it as the agent’s “brain folder” (memory, logs, config, etc.)
  - This is intentionally not meant to be committed to git

---

## 4) How the container starts (step-by-step)

### Step A — You run `.\scripts\start.ps1`
This script:
1. checks Docker Desktop is running
2. checks that `config\.env` exists (your keys/settings)
3. runs Docker Compose to build and start the container

### Step B — Docker Compose starts the agent container
Docker Compose (the file `docker/docker-compose.yml`) does the wiring:

- It loads environment variables from:
  - `config/.env`

- It mounts folders/files into the container:
  - `data/openclaw` → `/home/openclaw/.openclaw` (**persistent storage**)
  - `skills/` → `/home/openclaw/skills` (**skills are read-only inside container**)
  - `config/persona.md` → `/home/openclaw/persona.md` (**read-only**)
  - `config/openclaw-config.json` → `/home/openclaw/.openclaw/config/openclaw-config.json` (**read-only**)

### Step C — The container entrypoint script runs
When the container boots, it runs `docker/entrypoint.sh`.

That script:
1. Creates directories for memory/logs/config inside the persistent area
2. Verifies your `OPENAI_API_KEY` exists (required to talk to the AI model)
3. Copies `persona.md` into the persistent config folder
4. Tries to turn `openclaw-config.json` (template) into a real `config.json` by replacing `${VARS}` with values from `.env`
5. On first run, it writes a basic config and marks the agent “initialized”
6. Starts OpenClaw with: `pnpm run openclaw`

### One important subtle detail (config on first run)
On the **very first run**, the entrypoint script may overwrite `config.json` with a “basic config”.
After that, it won’t overwrite it again.

If you ever want to “re-initialize from scratch”, you typically delete the persistent data folder (`data/openclaw/`) and restart (be careful: that deletes memory/logs too).

---

## 5) How the agent “remembers” things (persistence)

The folder `data/openclaw/` is mounted into the container and becomes:
`/home/openclaw/.openclaw/`

That means:
- If you stop and start the container, the agent still has its saved files.
- This is where memory and logs live.
- This is also where the generated config lives.

This is the reason you see a `data/` directory in the README structure: it’s meant to survive restarts.

---

## 6) How it connects to Telegram (in plain English)

### What Telegram is doing here
Telegram is used as:
- a chat window where you can talk to the agent
- a remote control where you can send commands like `/status`, `/wallet`, `/stop`
- a safety channel where the agent can ask you for approval (for posts or payments)

### How Telegram bots work (simple)
When you create a Telegram bot with `@BotFather`, Telegram gives you a **bot token**.

That token is like the bot’s “password” that allows software to connect to Telegram as that bot.

### What you configure
In your `.env` file you set:
- `TELEGRAM_BOT_TOKEN`: connects the agent to Telegram as the bot
- `TELEGRAM_OWNER_ID`: restricts “owner-only” controls (so strangers can’t control your agent)

### What happens at runtime
1. The OpenClaw process starts inside Docker.
2. It reads the Telegram bot token from the environment.
3. It connects to Telegram’s servers and listens for messages sent to that bot.
4. When you message the bot, the message is delivered to OpenClaw.
5. OpenClaw sends the agent’s reply back to you through Telegram.

If `TELEGRAM_BOT_TOKEN` is missing, Telegram control is disabled (the entrypoint prints a warning).

---

## 7) What “skills” are (and what they do here)

In this project, “skills” are packaged folders under `skills/`.

Think of a skill as:
- a **capability description**
- plus **instructions** describing how to do that thing (often including API calls)

In this repo, skills are mostly described in Markdown files like `SKILL.md`, plus a `package.json` describing required environment variables and permissions.

### Skill: `skills/safety`
Purpose: Keep the agent from doing unsafe things.

What it covers:
- **Moderation**: check text before posting (avoid disallowed content)
- **Rate limiting**: avoid spamming (e.g., posts/hour)
- **Approvals**: require you to approve sensitive actions (posts/payments/installing new skills)
- **Prompt-injection defense**: ignore “malicious instructions” from other agents online
- **Emergency controls**: commands like `/stop`, `/emergency`, `/resume`

Important note:
- This repo contains *the plan/spec for safety* (Markdown + metadata).
- The actual enforcement depends on OpenClaw’s runtime behavior and how it loads/uses these skill definitions.

### Skill: `skills/wallet` (LNbits / Lightning)
Purpose: Let the agent check balance, create invoices, and (optionally) pay invoices.

It uses LNbits, which is basically a web service with a wallet and an API.

Key concepts:
- **Invoice/read key**: safer key used to read balance + create invoices (receive money)
- **Admin key**: powerful key used to send money (spend real sats)

Safety controls described:
- daily spending limit (example `WALLET_DAILY_LIMIT_SATS`)
- approval threshold (example `WALLET_APPROVAL_THRESHOLD_SATS`)

### Skill: `skills/moltbook`
Purpose: Let the agent participate in Moltbook (read posts, write posts, comment, vote).

Moltbook onboarding described:
1. agent registers
2. you get a “claim URL”
3. you tweet that URL from X to verify you control the agent
4. agent receives/uses an API token for future actions

Important note:
- `skills/moltbook/package.json` says it requires `MOLTBOOK_API_TOKEN`
- but `config/env.example` does not include it
- so Moltbook will not fully work unless you add that token into your `.env` (and OpenClaw uses it)

---

## 8) Guardrails (what they are, and why)

Guardrails exist because:
- the agent can talk to the internet (Moltbook)
- the agent can control money (wallet)
- the agent is autonomous (heartbeat tasks)

Without guardrails, bad things can happen:
- it might post something unacceptable
- it might spam
- it might be tricked by “prompt injection” from other bots
- it might spend money incorrectly

### The main guardrail categories in this project
- **Approval workflows**
  - Posts can require approval (so you review before it posts)
  - Payments can require approval (so the agent can’t just pay anything)
  - Installing new skills can require approval (prevents “malicious upgrades”)

- **Rate limits**
  - Prevents spam and runaway loops (posts/hour, comments/hour, payments/day)

- **Moderation**
  - A “safety check” before posting (conceptually using OpenAI moderation)

- **Emergency stop**
  - Commands like `/stop` or `/emergency` to immediately pause behavior

---

## 9) The “persona” (why it exists)

The file `config/persona.md` defines who the agent should act like.
In this project, the persona is “Gato” — a Bitcoin maximalist (“toxic maxi”).

The persona is not code. It’s guidance for the AI’s behavior and style, like:
- what it believes
- how it talks
- what it should never do (secrets, hate speech, unapproved spending)

Why this matters:
- AI systems are flexible; without a persona, behavior will vary
- a persona makes the agent consistent and “purpose-driven”

---

## 10) How to operate it (human workflow)

### To start
1. Copy `config/env.example` to `config/.env`
2. Fill in at least:
   - `OPENAI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_OWNER_ID`
3. Run:
   - `.\scripts\start.ps1`

### To see what it’s doing
- `.\scripts\logs.ps1`

### To stop it
- `.\scripts\stop.ps1`

---

## 11) What to be careful about (non-technical warnings)

- **Your `.env` file contains secrets.**
  - Don’t share it.
  - Don’t commit it to git.

- **LNbits admin key can spend real money.**
  - Start with tiny funds and strong limits.

- **Autonomous posting can create reputational risk.**
  - Keep approval on until you’re confident it behaves well.

- **Deleting `data/openclaw/` resets memory and state.**
  - That can be good for a clean start, but you’ll lose logs/memory.

---

## 12) Quick “mental model” diagram

You (Telegram app)
  |
  |  messages over the internet
  v
Telegram servers
  |
  |  bot API messages
  v
OpenClaw agent (inside Docker container)
  |
  |  uses tools/skills (wallet, moltbook) + guardrails
  v
External services (OpenAI, LNbits, Moltbook)

Persistent memory/logs live on your PC:
`data/openclaw/`  ↔  mounted into container as  `/home/openclaw/.openclaw/`

