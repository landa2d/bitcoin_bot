# Security Supervisor (how to use it)

This project includes a “security supervisor” layer that performs boot-time checks and writes **redacted** security reports to persistent storage.

## What it does
- **On container boot** (before OpenClaw starts), it checks your environment configuration (keys present/missing, basic safety relationships) and then:
  - writes a status snapshot to disk
  - appends an audit log entry to disk
  - sends you a Telegram message (if Telegram is configured)

## Where reports are stored (persistent)

Because `docker/docker-compose.yml` mounts:
- `data/openclaw/` → `/home/openclaw/.openclaw/`

…the supervisor reports written inside the container end up on your Windows machine under:

- `data/openclaw/logs/security-supervisor-status.json`
- `data/openclaw/logs/security-supervisor-audit.log`

These files are **persistent** across restarts.

## Status snapshot file
File:
- `data/openclaw/logs/security-supervisor-status.json`

What it contains:
- timestamp
- whether the schema was loaded
- which env groups are missing keys
- redacted notes (no secret values)

## Audit log file
File:
- `data/openclaw/logs/security-supervisor-audit.log`

Format:
- JSON lines (one JSON object per line)

What it contains:
- timestamp
- severity (`INFO|WARN|CRITICAL`)
- category (`ENV|APPROVAL|THREAT|HTTP|PAYMENT|POST`)
- message
- redacted details

## Viewing the logs

### Option A: Container logs (fastest)
Run:
```powershell
.\scripts\logs.ps1
```

You should see a line like:
`[security-supervisor] Preflight done. Status: ... Audit: ...`

### Option B: Open the persistent files directly
Open these files in your editor:
- `data/openclaw/logs/security-supervisor-status.json`
- `data/openclaw/logs/security-supervisor-audit.log`

## What “redacted” means here
The supervisor never prints raw secret values (tokens/keys). It reports only:
- key names (missing/present)
- warnings about unsafe configuration

