#!/bin/bash
set -e

echo "============================================"
echo "  AgentPulse Newsletter Agent Starting..."
echo "============================================"
echo "  Agent Name: newsletter"
echo "  Mode: headless writer"
echo "============================================"

# Ensure workspace dirs
mkdir -p /home/openclaw/.openclaw/workspace/agentpulse/{newsletters,queue/responses}
mkdir -p /home/openclaw/.openclaw/logs
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

echo "  Starting newsletter poller..."
nohup python3 /home/openclaw/newsletter_poller.py > /home/openclaw/.openclaw/logs/newsletter-poller.log 2>&1 &

echo "  Starting newsletter agent..."
echo "============================================"

# Start OpenClaw gateway for the newsletter agent (headless)
cd /app
exec pnpm run openclaw gateway --allow-unconfigured
