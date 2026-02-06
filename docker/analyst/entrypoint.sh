#!/bin/bash
# OpenClaw Analyst — Headless analysis worker entrypoint
# No Telegram, no user interaction. Polls agent_tasks for work.

set -e

echo "============================================"
echo "  OpenClaw Analyst Agent Starting..."
echo "============================================"

# Ensure workspace dirs exist
mkdir -p /home/openclaw/.openclaw/workspace/agentpulse/queue/responses 2>/dev/null || true
mkdir -p /home/openclaw/.openclaw/workspace/agentpulse/opportunities 2>/dev/null || true
mkdir -p /home/openclaw/.openclaw/workspace/agentpulse/cache 2>/dev/null || true
mkdir -p /home/openclaw/.openclaw/logs 2>/dev/null || true
mkdir -p /home/openclaw/.openclaw/memory 2>/dev/null || true

# Expose custom skills to OpenClaw
if [ -d /home/openclaw/skills ]; then
    for dir in /home/openclaw/skills/*/; do
        [ -d "$dir" ] || continue
        name=$(basename "$dir")
        if [ -n "$name" ] && [ ! -e "/app/skills/$name" ]; then
            ln -sf "$dir" "/app/skills/$name" 2>/dev/null || true
        fi
    done
    echo "Custom skills linked into /app/skills"
fi

echo ""
echo "Agent Name: analyst"
echo "Mode: headless worker"
echo ""
echo "============================================"
echo "  Starting analyst loop..."
echo "============================================"

# Start OpenClaw gateway for the analyst agent (headless — no Telegram token configured)
# Without TELEGRAM_BOT_TOKEN, the gateway runs without a Telegram provider.
#
# NOTE: If a true headless/worker mode is needed later, this can be replaced
# with a Python polling loop that processes agent_tasks directly.
# See AGENTPULSE_MULTIAGENT_PLAN_v2.md Phase 3C for the fallback.
cd /app
exec pnpm run openclaw gateway --allow-unconfigured
