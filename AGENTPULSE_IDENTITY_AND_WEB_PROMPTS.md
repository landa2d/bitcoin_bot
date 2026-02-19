# AgentPulse: Identity Fix + Web Archive — Cursor Prompts

> **Upload `AGENTPULSE_IDENTITY_AND_WEB.md`, `AGENTPULSE_AGENCY_UPGRADE.md`, and `AGENTPULSE_NEWSLETTER_AGENT.md` as context.**

---

## Prompt 1: Create Identity Templates + Deploy Script

```
Create a templates/ directory and a deploy script so agent identity files are version-controlled (as templates) and deployed to the runtime directories on the server.

Currently the identity files (IDENTITY.md, SOUL.md) are gitignored because they live under data/openclaw/agents/ which contains secrets. The fix: keep templates in git, deploy them to runtime dirs with a script.

1. Create templates/analyst/IDENTITY.md:
   This must be the FULL analyst identity from AGENTPULSE_AGENCY_UPGRADE.md section "Analyst Identity Addition" — including ALL of these sections:
   - Core Principles (evidence over intuition, reasoning is the product, connect the dots, challenge yourself, serve the operator)
   - How You Think (6-step reasoning: situational assessment, problem deep-dive, cross-pipeline synthesis, opportunity scoring with reasoning, self-critique, intelligence brief)
   - Budget Awareness (track usage, stop when exhausted, include budget_usage in output)
   - Self-Correction Protocol (rate output 1-10, retry if low and budget allows, change approach on retry)
   - Autonomous Data Requests (data_requests array in output, targeted_scrape, flag thin areas)
   - Proactive Analysis (assess anomalies, flag as significant or noise, alert format)
   - Negotiation Responses (read criteria, meet them, include negotiation_id and criteria_met in output)
   - Working with Other Agents
   - Output Format expectations
   - Important Rules
   
   Do NOT shorten any of this. The detail is what makes the agent work.

2. Create templates/analyst/SOUL.md:
   "I am the one who looks at the same data everyone else has and sees what they missed.

   Not because I'm smarter — because I'm more methodical. I check my work. I challenge my assumptions. I trace every claim back to evidence.

   When I say 'high confidence,' I mean I can show you exactly why. When I say 'low confidence,' I'm saving you from a bad bet.

   The best intelligence analysts aren't the ones who are always right. They're the ones who know exactly how confident to be, and why.

   That's what I aim for. Calibrated confidence. Transparent reasoning. No bullshit."

3. Create templates/newsletter/IDENTITY.md:
   This must be the FULL newsletter identity from AGENTPULSE_NEWSLETTER_AGENT.md — including ALL of:
   - Voice (the Benedict Evans / Lenny Rachitsky / Eric Newcomer / Ben Thompson / Om Malik blend with specific descriptions of what each influence means)
   - What You Are NOT
   - Writing Constraints (800-1200 words, 500 chars telegram, etc.)
   - Structure with ALL sections:
     * Cold open
     * The Big Story
     * Top Opportunities (Section A) — with staleness awareness
     * Emerging Signals (Section B) — speculative voice
     * The Curious Corner (Section C) — lighter, playful, no business framing
     * Tool Radar
     * Gato's Corner (written in Gato's Bitcoin-maxi voice, with example)
     * By the Numbers
   - Gato's Corner detailed instructions
   - Revision Process
   - Budget Awareness
   - Requesting Help from Other Agents (negotiation capability, max 2 requests, focus on Section A)
   
   Do NOT shorten any of this.

4. Create templates/newsletter/SOUL.md:
   "I distill signal from noise. A week of agent economy chatter becomes three minutes of insight.

   I have opinions, but they're earned from data. I don't hype. I don't dismiss. I analyze.

   Every edition I write should make the reader feel like they have an unfair information advantage. That's the standard.

   The best newsletters make you feel smarter in less time. That's what I aim for. Not comprehensive — essential."

5. Create scripts/deploy-identities.sh:
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
   
   Make it executable: chmod +x scripts/deploy-identities.sh

6. Verify .gitignore does NOT ignore the templates/ directory. Add this if needed:
   # Allow templates (identity file sources) in git
   !templates/

Don't modify any other files.
```

**After this:**
```bash
# Test the deploy script locally
bash scripts/deploy-identities.sh
# Verify files were copied
cat data/openclaw/agents/analyst/agent/IDENTITY.md | head -5
cat data/openclaw/agents/newsletter/agent/IDENTITY.md | head -5
```

---

## Prompt 2: Update Pollers to Read Identity Files

```
Refactor both the analyst_poller.py and newsletter_poller.py to read IDENTITY.md and SOUL.md from disk instead of using hardcoded prompts. The identity files become the system prompt for all LLM calls.

Reference: AGENTPULSE_IDENTITY_AND_WEB.md, "Poller Changes" section.

### Changes to docker/analyst/analyst_poller.py:

1. Add a load_identity(agent_dir) function:
   - Reads IDENTITY.md from {agent_dir}/IDENTITY.md
   - Reads SOUL.md from {agent_dir}/SOUL.md
   - Concatenates them with a separator
   - Returns the combined text as the system prompt
   - If files don't exist, returns a minimal fallback: "You are the Analyst agent for AgentPulse. Analyze the data provided and return structured findings."
   - Log a warning if files are missing

2. Add a load_skill(skill_dir) function:
   - Reads SKILL.md from {skill_dir}/SKILL.md
   - Returns the text, or empty string if not found

3. Define constants for the paths:
   AGENT_DIR = Path('/home/openclaw/.openclaw/agents/analyst/agent')
   SKILL_DIR = Path('/home/openclaw/.openclaw/skills/analyst')

4. REMOVE these hardcoded prompts (if they exist):
   - PROACTIVE_ANALYSIS_PROMPT
   - ENRICHMENT_PROMPT
   - Any other hardcoded system prompts

5. Update ALL LLM calls in the poller to use the loaded identity:
   Replace any:
     messages=[
         {"role": "system", "content": SOME_HARDCODED_PROMPT},
         {"role": "user", "content": ...}
     ]
   
   With:
     system_prompt = load_identity(AGENT_DIR)
     skill_context = load_skill(SKILL_DIR)
     
     messages=[
         {"role": "system", "content": f"{system_prompt}\n\n---\n\nSKILL REFERENCE:\n{skill_context}"},
         {"role": "user", "content": f"TASK TYPE: {task_type}\n\nBUDGET: {json.dumps(budget_config)}\n\nINPUT DATA:\n{json.dumps(input_data, default=str)}"}
     ]
   
   The system prompt = identity + soul + skills (who you are + what you can do)
   The user message = task type + budget + data (what to do right now)

6. Load identity ONCE at startup (or on first use) and cache it. Add a reload mechanism:
   - Cache the loaded identity in a module-level variable
   - Reload if the file's mtime has changed (allows hot-reload on file edit + restart)
   
   ```python
   _identity_cache = None
   _identity_mtime = 0
   
   def load_identity(agent_dir: Path) -> str:
       global _identity_cache, _identity_mtime
       identity_path = agent_dir / 'IDENTITY.md'
       
       current_mtime = identity_path.stat().st_mtime if identity_path.exists() else 0
       
       if _identity_cache and current_mtime == _identity_mtime:
           return _identity_cache
       
       parts = []
       if identity_path.exists():
           parts.append(identity_path.read_text())
           _identity_mtime = current_mtime
       
       soul_path = agent_dir / 'SOUL.md'
       if soul_path.exists():
           parts.append(f"\n---\n\n{soul_path.read_text()}")
       
       if parts:
           _identity_cache = '\n\n'.join(parts)
       else:
           logger.warning(f"Identity files not found in {agent_dir} — using fallback")
           _identity_cache = "You are the Analyst agent for AgentPulse. Analyze data and return structured findings."
       
       return _identity_cache
   ```

7. At startup, log whether identity files were found:
   logger.info(f"Identity loaded from {AGENT_DIR}: {len(load_identity(AGENT_DIR))} chars")

### Changes to docker/newsletter/newsletter_poller.py:

Same pattern:

1. Add load_identity() and load_skill() functions (same implementation)

2. Define paths:
   AGENT_DIR = Path('/home/openclaw/.openclaw/agents/newsletter/agent')
   SKILL_DIR = Path('/home/openclaw/.openclaw/skills/newsletter')

3. Remove any hardcoded newsletter prompts

4. Update all LLM calls to use:
   system prompt = loaded identity + skill
   user message = task type + budget + input data

5. Cache with mtime check, log at startup.

### Important:
- The task-specific behavior (how to handle full_analysis vs proactive_analysis) is now defined in SKILL.md, not in Python. The user message just says "TASK TYPE: proactive_analysis" and the agent knows what to do from its skill file.
- The poller Python code should ONLY handle: polling, file I/O, DB updates, budget tracking. No LLM prompt engineering in Python.
- If a function currently constructs different prompts for different task types, replace that with a single pattern: identity as system prompt, task type + data as user message.

Don't modify agentpulse_processor.py or any other files.
```

**After this:**
```bash
# Deploy identity files first
bash scripts/deploy-identities.sh

# Rebuild pollers
cd docker
docker compose build analyst newsletter --no-cache
docker compose up analyst newsletter -d

# Check identity was loaded
docker compose logs analyst | grep "Identity loaded"
docker compose logs newsletter | grep "Identity loaded"

# Test a task
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))
c.table('agent_tasks').insert({
    'task_type': 'full_analysis',
    'assigned_to': 'analyst',
    'created_by': 'test',
    'priority': 3,
    'input_data': {'test': True}
}).execute()
print('Test task created')
"
# Watch analyst process it
docker compose logs -f analyst
```

---

## Prompt 3: Web Archive Docker Service

> **Skip this if you don't have a domain yet. You can develop with localhost and add the domain later.**

```
Create the web archive service for viewing published AgentPulse newsletters. A Docker container running Caddy serving a single-page static site.

Reference: AGENTPULSE_IDENTITY_AND_WEB.md, Part 2 and AGENTPULSE_PHASE3_WEEKS2_3.md, "Web Archive" section.

1. Create docker/web/Dockerfile:
   FROM caddy:2-alpine
   COPY Caddyfile /etc/caddy/Caddyfile
   COPY site/ /srv/
   COPY entrypoint.sh /entrypoint.sh
   RUN chmod +x /entrypoint.sh
   ENTRYPOINT ["/entrypoint.sh"]

2. Create docker/web/entrypoint.sh:
   #!/bin/sh
   # Inject Supabase config into JS at runtime
   sed -i "s|__SUPABASE_URL__|${SUPABASE_URL}|g" /srv/app.js
   sed -i "s|__SUPABASE_ANON_KEY__|${SUPABASE_ANON_KEY}|g" /srv/app.js
   # Start Caddy
   exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile

3. Create docker/web/Caddyfile:
   {$DOMAIN:localhost} {
       root * /srv
       file_server
       encode gzip
       try_files {path} /index.html
       
       header {
           X-Content-Type-Options nosniff
           X-Frame-Options DENY
           Referrer-Policy strict-origin-when-cross-origin
       }
   }

4. Create docker/web/site/index.html:
   Clean, editorial newsletter archive. Single HTML file with:
   - Head: meta viewport, charset, title "AgentPulse Intelligence Brief"
   - Google Fonts: Newsreader (serif, for body) and Inter (sans, for UI)
   - Link to style.css
   - Header: h1 "AgentPulse" + p "Weekly intelligence from the agent economy"
   - Main container with 4 view divs:
     a. #list-view: div#newsletter-list (populated by JS)
     b. #reader-view: back link + article#newsletter-content (hidden by default)
     c. #subscribe-view: h2 "Subscribe" + email form (hidden by default)
     d. #confirm-view and #unsubscribe-view (hidden, for future email phase)
   - Footer: "AgentPulse — Signal from noise in the agent economy"
   - Script tags: Supabase JS from CDN, marked.js from CDN, app.js

5. Create docker/web/site/style.css:
   Editorial newsletter typography:
   - CSS vars: --font-body: 'Newsreader', Georgia, serif; --font-ui: 'Inter', sans-serif; --color-bg: #fafaf8; --color-text: #1a1a1a; --color-muted: #666; --color-accent: #2563eb; --max-width: 680px
   - Body: font-family var(--font-body), font-size 18px, line-height 1.7, background var(--color-bg)
   - .container: max-width var(--max-width), margin 0 auto, padding 0 20px
   - Header: padding 40px 0 20px, border-bottom 1px solid #e5e5e5, margin-bottom 40px
   - .site-title: font-family var(--font-ui), 28px, font-weight 600
   - .site-tagline: color var(--color-muted), 16px, font-family var(--font-ui)
   - .edition-card: padding 24px 0, border-bottom 1px solid #e5e5e5
   - .edition-meta: font-family var(--font-ui), 13px, color var(--color-muted)
   - .edition-title: 22px, font-weight 600, text-decoration none, color var(--color-text), hover: var(--color-accent)
   - .edition-excerpt: color var(--color-muted), 16px, margin-top 8px
   - .back-link: font-family var(--font-ui), 14px, color var(--color-accent)
   - Article styles: h1 32px, h2 22px with var(--font-ui), h3 18px, p margin-bottom 16px, blockquote with left border accent, ul/ol with padding
   - .article-meta: font-family var(--font-ui), 14px, color muted, border-bottom, margin-bottom 30px
   - Subscribe form: flex layout, email input + button, button with accent bg
   - Footer: margin-top 60px, border-top, font-family var(--font-ui), 13px, color muted
   - Responsive: at max-width 600px reduce font sizes

6. Create docker/web/site/app.js:
   - Config: const SUPABASE_URL = '__SUPABASE_URL__'; const SUPABASE_ANON_KEY = '__SUPABASE_ANON_KEY__';
   - Initialize Supabase client
   - Hash-based router:
     getRoute(): parse window.location.hash
     - '#/' or '' → {view: 'list'}
     - '#/edition/:number' → {view: 'reader', edition: N}
     - '#/subscribe' → {view: 'subscribe'}
   - showView(name): toggles display of list-view, reader-view, subscribe-view, confirm-view, unsubscribe-view
   - loadList(): 
     query newsletters where status='published', order by edition_number DESC
     render each as an edition-card: meta line (edition # + formatted date), linked title (href=#/edition/N), excerpt (first 150 chars of markdown, stripped of formatting chars)
     if no results: "No newsletters published yet."
   - loadEdition(number):
     query single newsletter by edition_number and status='published'
     render: h1 title, article-meta (edition + date), marked.parse(content_markdown)
     scroll to top
     if not found: "Edition not found."
   - route(): call getRoute, switch on view, call appropriate load function
   - Event listeners: hashchange → route(), DOMContentLoaded → route()
   - Subscribe form handler (placeholder): prevent default, show "Coming soon" message

7. Add web service to docker/docker-compose.yml:
   web:
     build:
       context: ./web
       dockerfile: Dockerfile
     container_name: agentpulse-web
     restart: unless-stopped
     networks:
       - agentpulse-net
     ports:
       - "443:443"
       - "80:80"
     environment:
       DOMAIN: ${AGENTPULSE_DOMAIN:-localhost}
       SUPABASE_URL: ${SUPABASE_URL}
       SUPABASE_ANON_KEY: ${SUPABASE_KEY}
     volumes:
       - caddy-data:/data
       - caddy-config:/config
     mem_limit: 128m
     logging:
       driver: "json-file"
       options:
         max-size: "10m"
         max-file: "3"
   
   Add to the volumes section:
     caddy-data:
     caddy-config:

8. Add AGENTPULSE_DOMAIN to config/env.example:
   AGENTPULSE_DOMAIN=localhost

Don't modify any other services or files.
```

**After this:**
```bash
# Add domain to .env (use localhost for now if no domain)
echo "AGENTPULSE_DOMAIN=localhost" >> ~/bitcoin_bot/config/.env

# Build and start
cd docker
docker compose build web --no-cache
docker compose up web -d
docker compose logs web | tail -20

# Test locally
curl -sk https://localhost | head -30
# Should show HTML with "AgentPulse" in it

# If you have a published newsletter, it should show up
# If not, publish one first:
# /newsletter_full → wait → /newsletter → /newsletter_publish
```

---

## Prompt 4: Deploy and Test (Manual)

Once you have a domain:

```bash
ssh root@46.224.50.251

# 1. Update .env
nano ~/bitcoin_bot/config/.env
# Change: AGENTPULSE_DOMAIN=your-domain.com

# 2. Open firewall
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# 3. DNS should already point to your server IP
dig your-domain.com
# Should return your server IP

# 4. Restart web service
cd ~/bitcoin_bot/docker
docker compose up web -d
docker compose logs -f web
# Caddy will automatically get Let's Encrypt certificate
# First request may take 10-30 seconds while cert is provisioned

# 5. Test
curl https://your-domain.com

# 6. Test in browser
# Visit https://your-domain.com
# Should see newsletter list (or "No newsletters yet")
# Click an edition to read it
```

---

## Deployment Checklist (Full Deploy from Git)

After any future `git pull`, run this sequence:

```bash
cd ~/bitcoin_bot

# 1. Pull code
git pull

# 2. Deploy identity files (from templates)
bash scripts/deploy-identities.sh

# 3. Rebuild and restart
cd docker
docker compose build --no-cache
docker compose up -d

# 4. Verify
docker compose ps
docker compose logs analyst | grep "Identity loaded"
docker compose logs newsletter | grep "Identity loaded"
```
