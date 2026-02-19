# AgentPulse: Identity Files Fix + Web Archive

**Date:** February 17, 2026

---

## Part 1: Identity Files as Source of Truth

### The Problem

The analyst_poller.py and newsletter_poller.py have system prompts hardcoded in Python:
- `PROACTIVE_ANALYSIS_PROMPT` in analyst_poller.py
- `ENRICHMENT_PROMPT` in analyst_poller.py
- Any system prompts in newsletter_poller.py

This means:
- Editing IDENTITY.md does nothing — the pollers ignore it
- Tuning voice/reasoning requires code changes + container rebuild
- The OpenClaw agents load IDENTITY.md for their session, but the pollers bypass that for LLM calls
- Two sources of truth = they'll drift apart

### The Fix

Make the pollers **read identity files at runtime** instead of using hardcoded prompts. The pollers should:

1. Load IDENTITY.md and SOUL.md from the agent's identity directory
2. Use them as the system prompt for all LLM calls
3. Append task-specific instructions (what to do with THIS task) as the user message
4. Fall back to a minimal hardcoded prompt only if the files don't exist

This way:
- Edit IDENTITY.md → restart agent → new personality
- No code changes needed for voice tuning
- Single source of truth per agent

### Identity File Deployment

Since the identity files are gitignored (they contain the agent's "soul" and shouldn't be in version control alongside API keys), they need a deployment mechanism. Options:

**Option A: Deploy script on the server (recommended)**
A small script that writes/updates identity files from templates. Templates live in the repo (without secrets), actual identity files live on the server.

**Option B: Bake into Docker image**
Copy identity files during build. But then they're not hot-reloadable — requires rebuild.

**Option C: Separate config repo**
Overkill for now.

We'll go with Option A: a deploy script + template files in the repo.

### File Structure

```
bitcoin_bot/
├── templates/                           # NEW — identity templates (in git)
│   ├── analyst/
│   │   ├── IDENTITY.md
│   │   └── SOUL.md
│   ├── newsletter/
│   │   ├── IDENTITY.md
│   │   └── SOUL.md
│   └── analyst-skill/
│       └── SKILL.md
├── scripts/
│   └── deploy-identities.sh            # NEW — copies templates to runtime dirs
├── data/openclaw/agents/               # gitignored — runtime files
│   ├── analyst/agent/IDENTITY.md       # written by deploy script
│   ├── newsletter/agent/IDENTITY.md    # written by deploy script
│   └── ...
```

### deploy-identities.sh

```bash
#!/bin/bash
# Deploy agent identity files from templates to runtime directories
# Run after git pull, before docker compose restart

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

# Copy auth-profiles.json if missing (but never overwrite — it has secrets)
for agent in analyst newsletter; do
    AUTH_FILE="$BASE_DIR/data/openclaw/agents/$agent/agent/auth-profiles.json"
    if [ ! -f "$AUTH_FILE" ]; then
        if [ -f "$BASE_DIR/data/openclaw/agents/main/agent/auth-profiles.json" ]; then
            cp "$BASE_DIR/data/openclaw/agents/main/agent/auth-profiles.json" "$AUTH_FILE"
            echo "  $agent auth-profiles.json copied from main"
        else
            echo "  WARNING: No auth-profiles.json source found for $agent"
        fi
    fi
done

# Skills
cp "$BASE_DIR/templates/analyst-skill/SKILL.md" "$BASE_DIR/skills/analyst/SKILL.md" 2>/dev/null || true
cp "$BASE_DIR/templates/newsletter-skill/SKILL.md" "$BASE_DIR/skills/newsletter/SKILL.md" 2>/dev/null || true

echo "Done. Restart agents to pick up changes:"
echo "  cd docker && docker compose restart analyst newsletter"
```

### Poller Changes

Both pollers need to read identity files instead of using hardcoded prompts.

**Pattern for both pollers:**

```python
def load_identity(agent_dir: str) -> str:
    """Load IDENTITY.md and SOUL.md as the system prompt."""
    identity_path = Path(agent_dir) / 'IDENTITY.md'
    soul_path = Path(agent_dir) / 'SOUL.md'
    
    parts = []
    
    if identity_path.exists():
        parts.append(identity_path.read_text())
    
    if soul_path.exists():
        parts.append(f"\n---\n\n{soul_path.read_text()}")
    
    if parts:
        return '\n\n'.join(parts)
    
    # Fallback: minimal prompt if files don't exist
    return "You are an AI agent. Follow the task instructions carefully."


def load_skill(skill_dir: str) -> str:
    """Load SKILL.md for task-specific instructions."""
    skill_path = Path(skill_dir) / 'SKILL.md'
    if skill_path.exists():
        return skill_path.read_text()
    return ""


# At startup
AGENT_DIR = '/home/openclaw/.openclaw/agents/analyst/agent'
SKILL_DIR = '/home/openclaw/.openclaw/skills/analyst'

# When making LLM calls
system_prompt = load_identity(AGENT_DIR)
skill_context = load_skill(SKILL_DIR)

response = openai_client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": f"{system_prompt}\n\n---\n\nSKILL REFERENCE:\n{skill_context}"},
        {"role": "user", "content": f"TASK: {task_type}\n\nINPUT DATA:\n{json.dumps(input_data, default=str)}"}
    ],
    temperature=0.3,
    max_tokens=4000
)
```

**Key change:** The hardcoded `PROACTIVE_ANALYSIS_PROMPT`, `ENRICHMENT_PROMPT`, etc. get REMOVED from the poller code. The identity file + skill file contain all the instructions the agent needs. The poller only provides the task type and input data.

Task-specific behavior (how to handle `full_analysis` vs `proactive_analysis` vs `enrich_for_newsletter`) is defined in SKILL.md, not in Python code. This is the correct separation:

- **IDENTITY.md** = who you are, how you think, your principles
- **SOUL.md** = your core motivation (short, philosophical)
- **SKILL.md** = what tasks you handle, input/output formats, protocols
- **Poller Python** = infrastructure only (polling, file I/O, DB updates, budget tracking)

---

## Part 2: Web Archive

### Domain

You need a domain before deploying with HTTPS. While you're buying one, you can develop and test locally using `localhost`.

Recommended: buy a short domain related to your project. Something like:
- `agentpulse.xyz` (~$3/year)
- `agentpulse.dev` (~$12/year)
- `agentpulse.io` (~$30/year)
- Or a subdomain of a domain you already own

After purchase:
1. Add an A record pointing to your Hetzner IP (46.224.50.251)
2. Wait 5-30 min for DNS propagation
3. Caddy handles HTTPS automatically

### Architecture

```
docker/web/
├── Dockerfile           # Caddy + static files
├── Caddyfile           # Reverse proxy config with auto-HTTPS
├── entrypoint.sh       # Injects Supabase config into JS
└── site/
    ├── index.html      # Single-page app
    ├── style.css       # Editorial typography
    └── app.js          # Supabase client + routing
```

Single HTML file, no framework, no build step. Reads published newsletters from Supabase using the anon key (RLS allows only published newsletters to be read publicly).

### Design

- Max-width 680px centered column
- Serif body font (Newsreader) for editorial feel
- Sans-serif (Inter) for UI elements
- Clean, minimal — inspired by Stratechery/Substack reader
- Mobile responsive
- Subscribe form placeholder (wired up in email phase)

---

## Implementation Sequence

```
Prompt 1: Create identity templates + deploy script
Prompt 2: Update pollers to read identity files instead of hardcoded prompts
Prompt 3: Web archive Docker service (Caddy + HTML/CSS/JS)
Prompt 4: Deploy and test (manual)
```
