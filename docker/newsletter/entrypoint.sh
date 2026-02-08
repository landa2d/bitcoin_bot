#!/bin/bash
set -e

echo "============================================"
echo "  AgentPulse Newsletter Agent Starting..."
echo "============================================"
echo "  Agent Name: newsletter"
echo "  Mode: direct Anthropic"
echo "  Model: ${NEWSLETTER_MODEL:-claude-sonnet-4-20250514}"
echo "============================================"

# Ensure workspace dirs
mkdir -p /home/openclaw/.openclaw/workspace/agentpulse/newsletters
mkdir -p /home/openclaw/.openclaw/logs

echo "  Starting newsletter agent..."
echo "============================================"

# Run the newsletter agent directly (it polls Supabase + calls Anthropic)
exec python3 /home/openclaw/newsletter_poller.py
