#!/bin/bash
set -e

echo "============================================"
echo "  AgentPulse Newsletter Agent Starting..."
echo "============================================"
echo "  Agent Name: newsletter"
echo "  Mode: direct OpenAI"
echo "  Model: ${NEWSLETTER_MODEL:-gpt-4o}"
echo "============================================"

# Ensure workspace dirs
mkdir -p /home/openclaw/.openclaw/workspace/agentpulse/newsletters
mkdir -p /home/openclaw/.openclaw/logs

echo "  Starting newsletter agent..."
echo "============================================"

# Run the newsletter agent directly (it polls Supabase + calls Anthropic)
exec python3 /home/openclaw/newsletter_poller.py
