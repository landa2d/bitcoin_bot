#!/bin/bash
# LLM Proxy — Transparent proxy between agents and LLM providers
set -e

echo "============================================"
echo "  LLM Proxy Starting..."
echo "  Port: ${LLM_PROXY_PORT:-8200}"
echo "============================================"

mkdir -p /home/openclaw/.openclaw/logs 2>/dev/null || true

exec python3 /home/openclaw/proxy.py
