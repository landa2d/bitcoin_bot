#!/bin/bash
# AgentPulse Analyst — Direct OpenAI intelligence agent
set -e

echo "============================================"
echo "  AgentPulse Analyst Starting..."
echo "  Mode: direct OpenAI"
echo "  Model: ${ANALYST_MODEL:-gpt-4o}"
echo "============================================"

# Ensure workspace dirs exist
mkdir -p /home/openclaw/.openclaw/workspace/agentpulse/analysis 2>/dev/null || true
mkdir -p /home/openclaw/.openclaw/logs 2>/dev/null || true

exec python3 /home/openclaw/analyst_poller.py
