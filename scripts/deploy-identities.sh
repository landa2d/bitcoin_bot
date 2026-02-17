#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"

echo "Deploying agent identity files..."

# Analyst
mkdir -p "$BASE_DIR/data/openclaw/agents/analyst/agent"
cp "$BASE_DIR/templates/analyst/IDENTITY.md" "$BASE_DIR/data/openclaw/agents/analyst/agent/IDENTITY.md"
cp "$BASE_DIR/templates/analyst/SOUL.md" "$BASE_DIR/data/openclaw/agents/analyst/agent/SOUL.md"
echo "  Analyst identity deployed"

# Newsletter
mkdir -p "$BASE_DIR/data/openclaw/agents/newsletter/agent"
cp "$BASE_DIR/templates/newsletter/IDENTITY.md" "$BASE_DIR/data/openclaw/agents/newsletter/agent/IDENTITY.md"
cp "$BASE_DIR/templates/newsletter/SOUL.md" "$BASE_DIR/data/openclaw/agents/newsletter/agent/SOUL.md"
echo "  Newsletter identity deployed"

# Copy auth-profiles.json if missing (never overwrite — has secrets)
for agent in analyst newsletter; do
    AUTH_FILE="$BASE_DIR/data/openclaw/agents/$agent/agent/auth-profiles.json"
    if [ ! -f "$AUTH_FILE" ]; then
        if [ -f "$BASE_DIR/data/openclaw/agents/main/agent/auth-profiles.json" ]; then
            cp "$BASE_DIR/data/openclaw/agents/main/agent/auth-profiles.json" "$AUTH_FILE"
            echo "  $agent auth-profiles.json copied from main"
        else
            echo "  WARNING: No auth-profiles.json found for $agent"
        fi
    fi
done

echo ""
echo "Done. Restart agents to pick up changes:"
echo "  cd docker && docker compose restart analyst newsletter"
