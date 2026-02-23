#!/bin/bash
# AgentPulse Research Agent — Conviction-Driven Thesis Builder
set -e

echo "============================================"
echo "  AgentPulse Research Agent Starting..."
echo "  Model: ${RESEARCH_MODEL:-claude-sonnet-4-20250514}"
echo "  Poll interval: ${RESEARCH_POLL_INTERVAL:-60}s"
echo "============================================"

# Ensure log dir exists
mkdir -p /home/openclaw/.openclaw/logs 2>/dev/null || true

exec python3 /home/openclaw/research_agent.py --mode watch
