# AgentPulse Heartbeat Tasks

These tasks run on schedule without user interaction.

## Scheduled Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| Scrape Moltbook | Every 6 hours | Fetch new posts from configured submolts |
| Run Pipeline 1 | Every 12 hours | Extract problems, cluster, generate opportunities |
| Daily Digest | 9:00 AM | Send top opportunities to Telegram |
| Cleanup | Daily 3:00 AM | Remove old queue files, archive stale data |

## Cron Configuration

The processor handles scheduling internally. These are the default cron expressions:

```
# Moltbook scraping
0 */6 * * * python3 /home/openclaw/agentpulse_processor.py --task scrape

# Opportunity analysis
0 */12 * * * python3 /home/openclaw/agentpulse_processor.py --task analyze

# Daily digest
0 9 * * * python3 /home/openclaw/agentpulse_processor.py --task digest

# Cleanup
0 3 * * * python3 /home/openclaw/agentpulse_processor.py --task cleanup
```

## Manual Triggers

Users can trigger tasks manually via Telegram:
- `/scan` - Immediate scrape + analysis
- `/opportunities` - Fetch current opportunities (no new analysis)
- `/pulse_status` - System health check
