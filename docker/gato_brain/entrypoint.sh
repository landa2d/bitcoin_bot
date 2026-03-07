#!/bin/bash
# Gato Brain — Conversational intelligence middleware
set -e

echo "============================================"
echo "  Gato Brain Starting..."
echo "  Port: ${GATO_BRAIN_PORT:-8100}"
echo "============================================"

# Ensure log dir exists
mkdir -p /home/openclaw/.openclaw/logs 2>/dev/null || true

exec python3 /home/openclaw/gato_brain.py
