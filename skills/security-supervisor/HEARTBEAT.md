# Security Supervisor Heartbeat

This file defines periodic “supervisor checks”. The goal is to continuously verify safety requirements and alert the owner if anything becomes unsafe.

## Schedule
- Run every 60 minutes (or whatever the agent heartbeat interval is configured to).
- Additionally, send a status summary every `SUPERVISOR_STATUS_INTERVAL_HOURS` (default: 6 hours).

## Heartbeat Tasks

### Task 1: Validate environment requirements
1. Load the schema from `/home/openclaw/.openclaw/config/env.schema.json`.
2. For each group (core/telegram/wallet/moltbook), evaluate:
   - which required keys are missing
   - which optional keys are present
3. Produce a redacted summary (never include values).
4. If any **critical** requirements are missing (ex: `OPENAI_API_KEY`), alert immediately.

### Task 2: Validate safe numeric relationships
Validate common safety relationships:
- If both are set, ensure `WALLET_APPROVAL_THRESHOLD_SATS <= WALLET_DAILY_LIMIT_SATS`
- Ensure rate limits are not extreme:
  - `MAX_POSTS_PER_HOUR` should be small (default 5)
  - `MAX_COMMENTS_PER_HOUR` should be small (default 10)

If unsafe, alert the owner and recommend safer defaults.

### Task 3: Scan for obvious secret leakage patterns (defensive)
If the agent has access to recent logs or outgoing messages, scan for patterns that look like:
- OpenAI keys: `sk-...`
- Telegram bot token formats: `123456789:ABC...`
- LN invoice strings: `lnbc...`

If detected:
1. Immediately alert owner
2. Record a SECURITY incident in the audit log
3. Recommend rotating the affected key(s)

### Task 4: Emit status snapshot
Write the latest redacted status to:
- `/home/openclaw/.openclaw/logs/security-supervisor-status.json`

Append an audit entry to:
- `/home/openclaw/.openclaw/logs/security-supervisor-audit.log`

## Output examples (redacted)

Example `security-supervisor-status.json`:
```json
{
  "timestamp": "2026-01-31T12:00:00Z",
  "groups": {
    "core": { "missing": [], "present": ["OPENAI_API_KEY", "OPENAI_MODEL"] },
    "telegram": { "missing": ["TELEGRAM_OWNER_ID"], "present": ["TELEGRAM_BOT_TOKEN"] }
  },
  "notes": ["Telegram approvals degraded until TELEGRAM_OWNER_ID is set"]
}
```

