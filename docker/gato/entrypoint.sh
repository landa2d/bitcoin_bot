#!/bin/bash
# OpenClaw Gato — Container Entrypoint Script
# User-facing Bitcoin agent with Telegram bot and Moltbook posting.
# AgentPulse processor now runs as a separate service.

set -e

echo "============================================"
echo "  OpenClaw Gato Agent Starting..."
echo "============================================"

# Create necessary directories (ignore errors if they exist or have permission issues)
mkdir -p /home/openclaw/.openclaw/memory 2>/dev/null || true
mkdir -p /home/openclaw/.openclaw/logs 2>/dev/null || true
mkdir -p /home/openclaw/.openclaw/config 2>/dev/null || true
mkdir -p /home/openclaw/.openclaw/workspace/moltbook_queue 2>/dev/null || true
mkdir -p /home/openclaw/.openclaw/workspace/moltbook_queue/responses 2>/dev/null || true
mkdir -p /home/openclaw/.openclaw/workspace/agentpulse/queue 2>/dev/null || true
mkdir -p /home/openclaw/.openclaw/workspace/agentpulse/queue/responses 2>/dev/null || true
mkdir -p /home/openclaw/.openclaw/workspace/agentpulse/opportunities 2>/dev/null || true
mkdir -p /home/openclaw/.openclaw/workspace/agentpulse/cache 2>/dev/null || true

# Security supervisor preflight (redacted checks + alerts)
if [ -x /home/openclaw/preflight.sh ]; then
    echo "Running security supervisor preflight..."
    /home/openclaw/preflight.sh || echo "WARNING: Security supervisor preflight failed"
fi

# Check required environment variables
if [ -z "$OPENAI_API_KEY" ]; then
    echo "ERROR: OPENAI_API_KEY is not set"
    exit 1
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "WARNING: TELEGRAM_BOT_TOKEN is not set - Telegram control disabled"
fi

# Export environment variables for OpenClaw
export OPENAI_API_KEY="$OPENAI_API_KEY"
export TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN"

# Expose custom skills to OpenClaw: symlink /home/openclaw/skills into /app/skills
# so the agent loads moltbook, wallet, security-supervisor, safety (otherwise only bundled skills load)
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

# Copy persona configuration if available (ignore permission errors on Windows bind mounts)
if [ -f /home/openclaw/persona.md ]; then
    echo "Loading persona configuration..."
    cp /home/openclaw/persona.md /home/openclaw/.openclaw/config/persona.md 2>/dev/null || echo "Note: Using mounted persona.md directly"
fi

# Process config template with environment variables
if [ -f /home/openclaw/.openclaw/config/openclaw-config.json ]; then
    echo "Processing configuration template..."
    envsubst < /home/openclaw/.openclaw/config/openclaw-config.json > /home/openclaw/.openclaw/config.json 2>/dev/null || echo "Note: Config template processing skipped"
fi

# Initialize OpenClaw if not already done
if [ ! -f /home/openclaw/.openclaw/.initialized ]; then
    echo "First run - initializing OpenClaw..."
    
    # Run onboarding in non-interactive mode
    cd /app
    
    # Create a basic config if onboarding is interactive (handle permission errors)
    cat > /home/openclaw/.openclaw/config.json 2>/dev/null << EOF || echo "Note: Using default config"
{
  "agent": {
    "name": "${AGENT_NAME:-Gato}",
    "description": "${AGENT_DESCRIPTION:-A Bitcoin maximalist AI agent}"
  },
  "llm": {
    "provider": "openai",
    "model": "${OPENAI_MODEL:-gpt-4o}",
    "maxTokens": ${OPENAI_MAX_TOKENS:-4096}
  },
  "channels": {
    "telegram": {
      "enabled": true
    }
  }
}
EOF
    
    touch /home/openclaw/.openclaw/.initialized 2>/dev/null || true
    echo "Initialization complete!"
fi

echo ""
echo "Agent Name: ${AGENT_NAME:-Gato}"
echo "LLM Provider: OpenAI (${OPENAI_MODEL:-gpt-4o})"
echo "Telegram: $([ -n "$TELEGRAM_BOT_TOKEN" ] && echo "Enabled" || echo "Disabled")"
echo "Lightning Wallet: $([ -n "$LNBITS_ADMIN_KEY" ] && echo "Enabled" || echo "Disabled")"
echo ""
echo "============================================"
echo "  Starting agent loop..."
echo "============================================"

# Start Moltbook post-by-write queue watcher in background (if token set)
if [ -n "$MOLTBOOK_API_TOKEN" ] && [ -x /home/openclaw/moltbook_post_watcher.sh ]; then
    export OPENCLAW_DATA_DIR="${OPENCLAW_DATA_DIR:-/home/openclaw/.openclaw}"
    nohup /home/openclaw/moltbook_post_watcher.sh >> /home/openclaw/.openclaw/logs/moltbook_watcher.log 2>&1 &
    echo "Moltbook queue watcher started"
fi

# NOTE: AgentPulse processor now runs as a separate Docker service (processor container).
# It is no longer started here via nohup.

# Run doctor to fix any configuration issues
cd /app
echo "Running OpenClaw doctor..."
pnpm run openclaw doctor --fix 2>/dev/null || echo "Doctor fix completed or skipped"

# Start OpenClaw gateway (the main agent service)
echo "Starting OpenClaw gateway..."
exec pnpm run openclaw gateway --allow-unconfigured
