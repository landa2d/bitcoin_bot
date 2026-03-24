#!/bin/bash
# Gato Brain — Conversational intelligence middleware
set -e

echo "============================================"
echo "  Gato Brain Starting..."
echo "  Port: ${GATO_BRAIN_PORT:-8100}"
echo "============================================"

# Ensure directories exist
mkdir -p /home/openclaw/.openclaw/logs 2>/dev/null || true
mkdir -p /root/code-workspaces/.sessions 2>/dev/null || true

# Prepare openclaw user for Claude CLI (container runs as root,
# but claude --dangerously-skip-permissions refuses root)
mkdir -p /home/openclaw/.claude
cp -a /root/.claude/. /home/openclaw/.claude/
# .claude.json (auth config) lives in $HOME, not inside .claude/
cp /root/.claude.json /home/openclaw/.claude.json 2>/dev/null || true
chown -R openclaw:openclaw /home/openclaw/.claude /home/openclaw/.claude.json

# Give openclaw write access to code workspaces
# /root is 700 by default — openclaw needs traverse (o+x) to reach subdirs
chmod o+x /root
chown -R openclaw:openclaw /root/code-workspaces 2>/dev/null || true

# Allow root's git to operate on openclaw-owned repos (root runs git ops,
# openclaw owns the files after chown)
git config --global --add safe.directory '*'

# Git identity for code sessions (commit/push)
git config --global user.email "diego@aiagentspulse.com"
git config --global user.name "Diego Lancha"

exec python3 /home/openclaw/gato_brain.py
