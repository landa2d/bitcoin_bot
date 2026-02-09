#!/bin/bash
# OpenClaw Analyst — Intelligent analysis agent entrypoint
# Starts the Python task poller in the background, then runs OpenClaw headless.

set -e

echo "============================================"
echo "  AgentPulse Analyst Starting..."
echo "  Mode: Intelligent Analysis Agent"
echo "============================================"

# Ensure workspace dirs exist
mkdir -p /home/openclaw/.openclaw/workspace/agentpulse/queue/responses 2>/dev/null || true
mkdir -p /home/openclaw/.openclaw/workspace/agentpulse/analysis 2>/dev/null || true
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

# Start the analyst task poller in the background
echo "Starting analyst poller..."
nohup python3 /home/openclaw/analyst_poller.py \
    >> /home/openclaw/.openclaw/logs/analyst-poller.log 2>&1 &
echo "Analyst poller started (PID: $!)"

echo ""
echo "Agent Name: analyst"
echo "Mode: headless worker + task poller"
echo ""
echo "============================================"
echo "  Starting OpenClaw headless gateway..."
echo "============================================"

# Start OpenClaw gateway for the analyst agent (headless — no Telegram token)
cd /app
exec pnpm run openclaw gateway --allow-unconfigured
