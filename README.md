# OpenClaw Bitcoin Agent + AgentPulse Intelligence Platform

An autonomous AI agent running in a secure Docker sandbox with Bitcoin/Lightning wallet capabilities, Moltbook integration, and the AgentPulse multi-agent intelligence system.

## Features

- **Multi-Agent Architecture**: 4 Docker services — Gato (Telegram agent), Analyst (intelligence), Newsletter (editorial), Processor (orchestrator)
- **Telegram Control**: Communicate with and control your agent via Telegram
- **Moltbook Integration**: Participate in the AI social network
- **Lightning Wallet**: Send and receive Bitcoin via Lightning Network
- **AgentPulse Intelligence**: Automated opportunity detection, investment scanning, and weekly newsletters from Moltbook data
- **Agency System**: Budget enforcement, self-correcting analysis loops, proactive monitoring, and agent-to-agent negotiation
- **Safety Guardrails**: Content moderation, rate limits, approval workflows, and per-agent budget limits
- **Security Supervisor**: Boot-time env checks, redacted audit logs, and optional Telegram alerts

## Prerequisites

1. **Docker Desktop for Windows** (local) or **Docker Engine** (Linux server) - [Docker](https://www.docker.com/products/docker-desktop/)
2. **OpenAI API Key** - [Get one here](https://platform.openai.com/api-keys)
3. **Telegram Account** - For bot creation via @BotFather
4. **X (Twitter) Account** - For Moltbook verification (optional)

## Quick Start (Local)

### 1. Configure Environment

```powershell
# Copy the example environment file
Copy-Item config\env.example config\.env

# Edit config\.env with your API keys
notepad config\.env
```

### 2. Start the Agent

```powershell
.\scripts\start.ps1
```

### 3. View Logs

```powershell
.\scripts\logs.ps1
```

### 4. Stop the Agent

```powershell
.\scripts\stop.ps1
```

## Project Structure

```
bitcoin_bot/
├── docker/
│   ├── docker-compose.yml        # Multi-service orchestration (4 containers)
│   ├── gato/                     # Telegram agent (OpenClaw + Node.js)
│   │   ├── Dockerfile
│   │   └── entrypoint.sh
│   ├── analyst/                  # Intelligence agent (Python + OpenAI)
│   │   ├── Dockerfile
│   │   ├── analyst_poller.py
│   │   └── entrypoint.sh
│   ├── newsletter/               # Newsletter writer (Python + OpenAI)
│   │   ├── Dockerfile
│   │   ├── newsletter_poller.py
│   │   └── entrypoint.sh
│   ├── processor/                # Background orchestrator (Python)
│   │   ├── Dockerfile
│   │   └── agentpulse_processor.py
│   ├── preflight.sh              # Security supervisor boot checks
│   └── moltbook_post_watcher.sh
├── config/
│   ├── .env                      # Your actual config (DO NOT COMMIT)
│   ├── env.example               # Environment template
│   ├── env.schema.json           # Env requirements (for supervisor)
│   ├── agentpulse-config.json    # AgentPulse pipeline + budget + negotiation config
│   ├── openclaw-config.json      # OpenClaw config template
│   └── persona.md                # Agent persona configuration
├── skills/
│   ├── agentpulse/               # AgentPulse command routing + docs
│   ├── analyst/                  # Analyst agent capabilities
│   ├── newsletter/               # Newsletter agent capabilities
│   ├── moltbook/                 # Moltbook integration skill
│   ├── wallet/                   # Lightning wallet skill
│   ├── safety/                   # Safety guardrails skill
│   └── security-supervisor/      # Env validation and audit
├── scripts/                      # Local dev scripts (PowerShell)
├── docs/                         # Setup guides
├── data/
│   └── openclaw/                 # Persistent agent data (memory, logs, workspace)
├── test_agency.sh                # Agency upgrade test script
├── CHANGELOG_AGENCY_UPGRADE.md   # Detailed change log
├── PROJECT_EXPLANATION.md        # Plain-English project overview
└── README.md
```

## Architecture

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│     Gato     │    │   Analyst    │    │  Newsletter  │    │  Processor   │
│  (Telegram)  │    │ (Intelligence│    │  (Editorial) │    │(Orchestrator)│
│   Node.js    │    │   Python)    │    │   Python)    │    │   Python)    │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                   │                   │
       └───────────────────┴───────────────────┴───────────────────┘
                                   │
                            ┌──────┴──────┐
                            │  Supabase   │
                            │  (Postgres) │
                            └─────────────┘
```

- **Gato**: User-facing Telegram bot, routes commands, delegates to other agents
- **Analyst**: Multi-step intelligence analysis with self-correction and budget awareness
- **Newsletter**: Weekly editorial brief with negotiation capability for data enrichment
- **Processor**: Background scraping, problem extraction, proactive monitoring, task orchestration

## Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `TELEGRAM_OWNER_ID` | Your Telegram user ID (for owner-only control and approvals) |

### Optional Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LNBITS_URL` | LNbits instance URL | `https://legend.lnbits.com` |
| `LNBITS_ADMIN_KEY` | LNbits admin key for payments | - |
| `LNBITS_INVOICE_KEY` | LNbits invoice/read key | - |
| `MOLTBOOK_API_TOKEN` | Moltbook API token (after claim) | - |
| `MAX_POSTS_PER_HOUR` | Rate limit for Moltbook posts | `5` |
| `MAX_COMMENTS_PER_HOUR` | Rate limit for comments | `10` |
| `REQUIRE_POST_APPROVAL` | Require human approval before posting | `true` |
| `WALLET_DAILY_LIMIT_SATS` | Daily spending limit (sats) | `10000` |
| `WALLET_APPROVAL_THRESHOLD_SATS` | Payments above this need approval | `1000` |

See `config/env.example` and `config/env.schema.json` for the full list.

## Security

- Container runs as non-root user
- Resource limits (4 GB RAM, 2 CPU cores)
- API keys stored in environment variables only; never put SSH keys or passphrases in `.env`
- Wallet spending limits and approval thresholds configurable
- Content moderation before posting
- **Security supervisor**: On boot, validates required env keys and writes redacted status/audit to `data/openclaw/logs/`. See [docs/security-supervisor.md](docs/security-supervisor.md).

## Running on a Remote Server (24/7)

To run the agent on a Linux server (e.g. Hetzner) so it stays up when your PC is off:

1. **Create a server** (Ubuntu 22.04/24.04, 4 GB RAM recommended).
2. **Install Docker** on the server (e.g. run `scripts/install-docker-ubuntu.sh` or the commands in it).
3. **Copy the project** to the server, e.g. from your PC:
   ```powershell
   scp -r C:\Users\landa\bitcoin_bot root@YOUR_SERVER_IP:/opt/
   ```
4. **Create `config/.env`** on the server (paste your keys; do not commit this file).
5. **Start the stack** on the server:
   ```bash
   cd /opt/bitcoin_bot/docker
   docker compose build
   docker compose up -d
   ```
6. **Validate**: `docker compose ps` should show the container **Up**. Test the bot in Telegram.

See [PROJECT_EXPLANATION.md](PROJECT_EXPLANATION.md) for more detail. Do **not** store SSH keys or passphrases in `.env`; use them only on your PC for `ssh`/`scp`.

## Making Changes After Deployment

1. **Edit files locally** (persona, skills, config, scripts, etc.).
2. **Copy to server** (if running remotely):
   ```powershell
   scp -r C:\Users\landa\bitcoin_bot root@YOUR_SERVER_IP:/opt/
   ```
   Or copy only changed files/folders, e.g. `scp config\persona.md root@YOUR_SERVER_IP:/opt/bitcoin_bot/config/`
3. **Apply on server**:
   - Config/skills/persona only: `docker compose restart`
   - After changing `.env` or Dockerfile/entrypoint: `docker compose build && docker compose up -d`

## Telegram Commands

Once paired with your agent:

### General
- Send any message to chat with the agent
- `/stop` - Pause the agent
- `/status` - Check agent status
- `/wallet` - Check wallet balance

### AgentPulse
| Command | Action |
|---------|--------|
| `/pulse_status` | System status (services, last runs, pipeline health) |
| `/opportunities` | Top 5 current business opportunities |
| `/scan` | Trigger a new opportunity scan |
| `/invest_scan` | Run investment scanner pipeline |
| `/deep_dive [topic]` | Deep analysis on a topic |
| `/newsletter_full` | Generate a full weekly newsletter |
| `/newsletter_publish` | Publish the latest newsletter |
| `/newsletter_revise [notes]` | Revise the latest newsletter draft |
| `/budget` | Per-agent daily usage vs limits |
| `/alerts` | Recent proactive anomaly alerts |
| `/negotiations` | Active agent-to-agent negotiations |
| `/crew_status` | Status of analyst and newsletter agents |

See [docs/telegram-setup.md](docs/telegram-setup.md) for initial setup.

## Moltbook Setup

1. The agent will automatically register on Moltbook (when the skill is used).
2. You'll receive a claim URL via Telegram
3. Tweet the claim URL from your X account
4. Agent becomes verified and can post

### Autonomous mode

To let the agent post and comment on Moltbook without asking you first, set `REQUIRE_POST_APPROVAL=false` in `config/.env`. Keep rate limits and `ENABLE_MODERATION=true` for safety.

## Lightning Wallet

1. Create a wallet at [legend.lnbits.com](https://legend.lnbits.com)
2. Add the API keys to your `.env` file
3. Fund with a small amount (e.g., 5000 sats)
4. Agent can send/receive Lightning payments

See [docs/lnbits-setup.md](docs/lnbits-setup.md) for details.

## Deployment

### Rebuild and restart (on server)
```bash
cd ~/bitcoin_bot/docker
docker compose build && docker compose up -d
```

### Restart without rebuild
```bash
cd ~/bitcoin_bot/docker
docker compose restart
```

### View service logs
```bash
docker compose logs -f              # all services
docker compose logs -f analyst      # analyst only
docker compose logs -f newsletter   # newsletter only
docker compose logs -f processor    # processor only
```

### Run the agency test suite
```bash
cd ~/bitcoin_bot
chmod +x test_agency.sh
./test_agency.sh
```

## Troubleshooting

### Docker not starting (local)
- Ensure Docker Desktop is running
- Check that WSL2 is properly configured

### Agent not responding
- Check logs with `.\scripts\logs.ps1` (local) or `docker compose logs -f` (server)
- Verify API keys are correct in `config/.env`
- Ensure `TELEGRAM_OWNER_ID` is set if you use owner-only access

### Telegram bot not working
- Verify bot token is correct
- Ensure you've started a chat with the bot
- Confirm `TELEGRAM_OWNER_ID` matches your user ID (e.g. from @userinfobot)

### AgentPulse services not starting
- Check that `SUPABASE_URL` and `SUPABASE_KEY` are set in `config/.env`
- Run `docker compose ps` to verify all 4 services show "Up"
- Check `docker compose logs processor` for connection errors

### Analyst/Newsletter can't read config
- Verify `docker-compose.yml` has the config volume mount: `../config:/home/openclaw/.openclaw/config:ro`
- Rebuild: `docker compose build analyst newsletter && docker compose up -d`

### Validating a remote server setup
On the server run:
```bash
docker --version && docker compose version
ls ~/bitcoin_bot/docker ~/bitcoin_bot/config
test -f ~/bitcoin_bot/config/.env && echo "OK: .env exists"
cd ~/bitcoin_bot/docker && docker compose ps
docker compose logs --tail 50
```
Then test the bot in Telegram.

## Documentation

| Document | Description |
|----------|-------------|
| [CHANGELOG_AGENCY_UPGRADE.md](CHANGELOG_AGENCY_UPGRADE.md) | Detailed log of agency upgrade changes |
| [AGENTPULSE_STATUS.md](AGENTPULSE_STATUS.md) | Deployment status and configuration reference |
| [AGENTPULSE_ARCHITECTURE.md](AGENTPULSE_ARCHITECTURE.md) | System architecture spec |
| [PROJECT_EXPLANATION.md](PROJECT_EXPLANATION.md) | Plain-English project overview |
| [docs/telegram-setup.md](docs/telegram-setup.md) | Telegram bot setup |
| [docs/lnbits-setup.md](docs/lnbits-setup.md) | Lightning wallet setup |
| [docs/security-supervisor.md](docs/security-supervisor.md) | Supervisor reports and logs |

## License

MIT
