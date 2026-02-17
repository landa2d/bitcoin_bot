# AgentPulse Phase 3 Weeks 2-3: Cursor Prompts

> **Upload `AGENTPULSE_PHASE3_WEEKS2_3.md` as context for every prompt.**

---

## Prompt 1: LLM Model Routing

```
Add model routing to docker/processor/agentpulse_processor.py so different tasks use different (cheaper) models.

Reference: AGENTPULSE_PHASE3_WEEKS2_3.md, Part 1.

1. Add a get_model(task_name) helper function that:
   - Reads config/agentpulse-config.json (mounted at /home/openclaw/.openclaw/config/agentpulse-config.json)
   - Looks up models.<task_name> from the JSON
   - Falls back to models.default, then to the AGENTPULSE_OPENAI_MODEL env var
   - Caches the config in memory (read once at first call, not on every invocation)
   - If the file doesn't exist or can't be read, falls back to OPENAI_MODEL env var

2. Update config/agentpulse-config.json to include a models section:
   {
     "models": {
       "extraction": "gpt-4o-mini",
       "clustering": "gpt-4o-mini",
       "trending_topics": "gpt-4o-mini",
       "opportunity_generation": "gpt-4o",
       "digest": "gpt-4o-mini",
       "default": "gpt-4o"
     }
   }
   
   Keep any existing config entries that are already in this file.

3. Update each function to use get_model() instead of the global OPENAI_MODEL:
   - extract_problems() → model=get_model('extraction')
   - extract_tool_mentions() → model=get_model('extraction')
   - cluster_problems() → model=get_model('clustering')
   - extract_trending_topics() → model=get_model('trending_topics')
   - generate_opportunities() → model=get_model('opportunity_generation')
   - Any digest/summary functions → model=get_model('digest')
   
   Find each openai_client.chat.completions.create() call and replace the model= parameter.

4. Add a log line at startup that shows which models are configured:
   logger.info(f"Model routing: {json.dumps(get_model_config())}")

Don't change any prompts, logic, or other code — only the model selection.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
# Check the startup log for model routing
docker compose logs processor | grep "Model routing"
# Test a task to verify it uses the right model
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task extract_trending_topics
# Check logs for which model was used
docker compose logs processor | tail -20
```

---

## Prompt 2: Web Archive — Docker Service + Site

> **IMPORTANT:** You need a domain for HTTPS. If you don't have one yet, use `localhost` for now and update later. Set `AGENTPULSE_DOMAIN` in your .env file.

```
Create a web archive service for viewing published AgentPulse newsletters. This is a Docker container running Caddy (for auto-HTTPS) serving a static single-page app.

Reference: AGENTPULSE_PHASE3_WEEKS2_3.md, Part 2 "Web Archive".

Create these files:

1. docker/web/Dockerfile:
   FROM caddy:2-alpine
   COPY Caddyfile /etc/caddy/Caddyfile
   COPY site/ /srv/
   COPY entrypoint.sh /entrypoint.sh
   RUN chmod +x /entrypoint.sh
   ENTRYPOINT ["/entrypoint.sh"]

2. docker/web/entrypoint.sh:
   #!/bin/sh
   # Inject Supabase config into the JS
   sed -i "s|__SUPABASE_URL__|${SUPABASE_URL}|g" /srv/app.js
   sed -i "s|__SUPABASE_ANON_KEY__|${SUPABASE_ANON_KEY}|g" /srv/app.js
   # Start Caddy
   exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile

3. docker/web/Caddyfile:
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

4. docker/web/site/index.html:
   A clean, editorial-style newsletter archive page. Single HTML file with:
   - Header: "AgentPulse" title + "Weekly intelligence from the agent economy" tagline
   - Three views controlled by hash routing:
     a. List view (#/): Shows all published newsletters as cards (edition #, date, title, excerpt)
     b. Reader view (#/edition/:number): Full newsletter rendered from markdown
     c. Subscribe placeholder (#/subscribe): Email form (non-functional placeholder for now)
   - Footer: "AgentPulse — Signal from noise in the agent economy"
   - Load marked.js and Supabase JS client from CDN
   - Link to style.css and app.js
   - Use Google Fonts: Newsreader (body) and Inter (UI elements)

5. docker/web/site/style.css:
   Newsletter-style typography. Key design:
   - Max-width 680px, centered
   - Newsreader serif font for body text, Inter sans-serif for UI/headers
   - Background #fafaf8, text #1a1a1a
   - Edition cards with bottom border separator
   - Article styles: proper heading hierarchy, blockquote with left border, generous line-height (1.7)
   - Subscribe form: inline email + button
   - Responsive for mobile
   - Clean, minimal, editorial feel — like Stratechery or Substack reader view
   
   Copy the full CSS from AGENTPULSE_PHASE3_WEEKS2_3.md.

6. docker/web/site/app.js:
   - Supabase client initialized with placeholder URLs (replaced at runtime by entrypoint.sh)
   - Hash-based router: getRoute() parses #/ and #/edition/:number and #/subscribe
   - loadList(): queries newsletters where status='published', ordered by edition_number DESC
     Renders edition cards with: meta line (edition # + date), linked title, excerpt (first 150 chars of markdown, stripped of formatting)
   - loadEdition(number): queries single newsletter by edition_number and status='published'
     Renders with marked.parse(), shows title, meta, and full content
   - showView(): toggles which div is visible
   - Route on hashchange and DOMContentLoaded
   
   Copy the full JS from AGENTPULSE_PHASE3_WEEKS2_3.md.

7. Add the web service to docker/docker-compose.yml:
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
   
   Add caddy-data and caddy-config to the volumes section.

Don't modify any other services or files.
```

**After this:**
```bash
# Add domain to .env
echo "AGENTPULSE_DOMAIN=localhost" >> ~/bitcoin_bot/config/.env
# Or use your real domain:
# echo "AGENTPULSE_DOMAIN=pulse.yourdomain.com" >> ~/bitcoin_bot/config/.env

docker compose build web --no-cache
docker compose up web -d
docker compose logs web | tail -20

# If using localhost, test:
curl -k https://localhost
# If using a real domain, open it in your browser
```

---

## Prompt 3: Domain + HTTPS + Firewall (Manual — No Cursor)

> Skip this if you don't have a domain yet. The web archive works on localhost.

```bash
ssh root@46.224.50.251

# 1. Open ports for web traffic
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status

# 2. Update .env with your domain
nano ~/bitcoin_bot/config/.env
# Add/update: AGENTPULSE_DOMAIN=pulse.yourdomain.com

# 3. Set up DNS (do this in your domain registrar):
# A record: pulse.yourdomain.com → 46.224.50.251
# Wait for DNS propagation (5-30 minutes)

# 4. Restart the web service to pick up the domain
cd ~/bitcoin_bot/docker
docker compose up web -d
docker compose logs -f web
# Caddy will automatically get a Let's Encrypt certificate

# 5. Test
curl https://pulse.yourdomain.com
```

---

## Prompt 4: Supabase Schema for Email Service

Run in Supabase SQL Editor:

```sql
-- ================================================
-- EMAIL NEWSLETTER SCHEMA
-- ================================================

-- Subscribers
CREATE TABLE newsletter_subscribers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    subscribed_at TIMESTAMPTZ DEFAULT NOW(),
    unsubscribed_at TIMESTAMPTZ,
    status TEXT DEFAULT 'pending',
    confirmation_token UUID DEFAULT uuid_generate_v4(),
    confirmed_at TIMESTAMPTZ,
    source TEXT DEFAULT 'web',
    metadata JSONB
);

CREATE INDEX idx_subscribers_status ON newsletter_subscribers(status);
CREATE INDEX idx_subscribers_email ON newsletter_subscribers(email);

-- Delivery log
CREATE TABLE newsletter_deliveries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    newsletter_id UUID REFERENCES newsletters(id),
    subscriber_id UUID REFERENCES newsletter_subscribers(id),
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'sent',
    resend_id TEXT,
    error_message TEXT,
    metadata JSONB
);

CREATE INDEX idx_deliveries_newsletter ON newsletter_deliveries(newsletter_id);
CREATE INDEX idx_deliveries_status ON newsletter_deliveries(status);

-- RLS: subscribers and deliveries are NOT public (PII)
ALTER TABLE newsletter_subscribers ENABLE ROW LEVEL SECURITY;
ALTER TABLE newsletter_deliveries ENABLE ROW LEVEL SECURITY;
-- No public policies — only service_role can access these

-- Public policy for subscribing: allow INSERT only (email + source)
-- This lets the web form create a subscriber without needing service key
CREATE POLICY "Anyone can subscribe"
ON newsletter_subscribers FOR INSERT
WITH CHECK (status = 'pending');

-- Public policy for confirming: allow UPDATE only on status via token
CREATE POLICY "Confirm via token"
ON newsletter_subscribers FOR UPDATE
USING (true)
WITH CHECK (status IN ('active', 'unsubscribed'));
```

---

## Prompt 5: Resend Integration in Processor

> **First:** Sign up at resend.com, verify your domain, get your API key. Add to .env:
> `RESEND_API_KEY=re_xxxxx`
> `NEWSLETTER_FROM_EMAIL=pulse@yourdomain.com`

```
Add email newsletter sending to docker/processor/agentpulse_processor.py using the Resend API.

Reference: AGENTPULSE_PHASE3_WEEKS2_3.md, "Email Sending" section.

1. Add env vars at the top (near other env var reads):
   RESEND_API_KEY = os.getenv('RESEND_API_KEY')
   NEWSLETTER_FROM_EMAIL = os.getenv('NEWSLETTER_FROM_EMAIL', 'noreply@example.com')
   AGENTPULSE_DOMAIN = os.getenv('AGENTPULSE_DOMAIN', 'localhost')

2. Add RESEND_API_KEY and NEWSLETTER_FROM_EMAIL and AGENTPULSE_DOMAIN to the common env section in docker-compose.yml.

3. Add a markdown_to_html_email(markdown_text, unsubscribe_url) function:
   - Convert basic markdown to inline-styled HTML (email clients don't support CSS classes)
   - Handle: h1, h2, h3, bold, italic, bullet lists, paragraphs
   - Wrap in a centered 600px container with:
     * Header: "AgentPulse" + tagline
     * Content: the converted HTML
     * Footer: "You're receiving this because you subscribed" + unsubscribe link
   - Use inline styles everywhere (font-family, font-size, color, margin, padding)
   - Body font: Georgia, serif. UI font: sans-serif.
   - Keep it simple — email HTML is notoriously tricky, basic is better

4. Add send_newsletter_email(newsletter_id) function that:
   - Gets the newsletter from Supabase by ID
   - Gets all active subscribers: status='active'
   - For each subscriber:
     a. Builds unsubscribe URL: https://{AGENTPULSE_DOMAIN}/#/unsubscribe/{subscriber_id}
     b. Converts newsletter markdown to HTML email with that unsubscribe URL
     c. Sends via Resend API (POST https://api.resend.com/emails):
        - from: AgentPulse <{NEWSLETTER_FROM_EMAIL}>
        - to: subscriber email
        - subject: "AgentPulse #{edition_number}: {title}"
        - html: the converted content
        - headers: {"List-Unsubscribe": "<unsubscribe_url>"}
     d. Logs delivery in newsletter_deliveries table: newsletter_id, subscriber_id, status, resend_id
     e. On error: log as failed, continue to next subscriber
   - Returns {sent: N, failed: N, total_subscribers: N}
   - Use httpx for the API call with a 10 second timeout
   - Wrap individual sends in try/except so one failure doesn't stop the batch

5. UPDATE the existing publish_newsletter() function:
   After sending to Telegram and marking as published, add:
   if RESEND_API_KEY:
       email_result = send_newsletter_email(newsletter_id)
       logger.info(f"Email delivery: {email_result}")
   Include email_result in the return dict.

6. Add 'send_newsletter_email' to execute_task():
   elif task_type == 'send_newsletter_email':
       return send_newsletter_email(params.get('newsletter_id'))

7. Add 'send_newsletter_email' to argparse choices.

8. Add 'markdown' to docker/processor/requirements.txt (for better markdown conversion if available, but the basic regex approach works too — your call).

Don't modify any other functions.
```

**After this:**
```bash
# Add Resend config to .env
echo "RESEND_API_KEY=re_your_key_here" >> ~/bitcoin_bot/config/.env
echo "NEWSLETTER_FROM_EMAIL=pulse@yourdomain.com" >> ~/bitcoin_bot/config/.env

docker compose build processor --no-cache
docker compose up processor -d

# Test with a manual subscriber first
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
c.table('newsletter_subscribers').insert({
    'email': 'your-real-email@example.com',
    'status': 'active',
    'source': 'manual'
}).execute()
print('Test subscriber added')
"

# If you have a published newsletter, test email sending:
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
nl = c.table('newsletters').select('id').eq('status','published').order('created_at',desc=True).limit(1).execute()
if nl.data:
    print(f'Would send newsletter: {nl.data[0][\"id\"]}')
else:
    print('No published newsletter to test with')
"
```

---

## Prompt 6: Subscribe/Confirm/Unsubscribe in Web Archive

```
Add subscribe, confirm, and unsubscribe functionality to the web archive.

Update docker/web/site/app.js:

1. Add a subscribe handler:
   When the subscribe form is submitted:
   - Get email from input
   - Insert into newsletter_subscribers via Supabase anon client: {email, status: 'pending', source: 'web'}
   - Show success message: "Check your email to confirm your subscription!"
   - Handle errors: if email already exists, show "You're already subscribed"
   - Handle validation: basic email format check before sending

2. Add a confirm route (#/confirm/:token):
   - Parse the confirmation token from the URL
   - Update newsletter_subscribers where confirmation_token = token: set status='active', confirmed_at=NOW()
   - Show: "Subscription confirmed! You'll receive the next edition."
   - Handle errors: if token not found, show "Invalid confirmation link"

3. Add an unsubscribe route (#/unsubscribe/:id):
   - Parse the subscriber ID from the URL
   - Update newsletter_subscribers where id = id: set status='unsubscribed', unsubscribed_at=NOW()
   - Show: "You've been unsubscribed. Sorry to see you go!"
   - Handle errors gracefully

4. Update the router in route() to handle the new hash routes:
   - #/confirm/:token → show confirm view
   - #/unsubscribe/:id → show unsubscribe view

5. Add the confirm and unsubscribe views to index.html:
   <div id="confirm-view" style="display:none">
       <h2>Confirming...</h2>
       <p id="confirm-message"></p>
   </div>
   
   <div id="unsubscribe-view" style="display:none">
       <h2>Unsubscribe</h2>
       <p id="unsubscribe-message"></p>
   </div>

6. Update showView() to handle the new views.

Also update docker/web/site/index.html:
- Add a small "Subscribe" link in the header or below the tagline
- Add the confirm-view and unsubscribe-view divs

Don't modify any backend code or other services.
```

**After this:**
```bash
docker compose build web --no-cache
docker compose up web -d
# Test subscribe flow in browser:
# Visit https://yourdomain.com/#/subscribe
# Enter email and submit
# Check Supabase: newsletter_subscribers should have a row with status='pending'
```

---

## Prompt 7: Confirmation Email via Processor

```
Add a confirmation email step to the subscription flow. When a new subscriber signs up (status='pending'), the Processor should detect it and send a confirmation email via Resend.

1. Add send_confirmation_email(subscriber_id) function to docker/processor/agentpulse_processor.py:
   - Gets subscriber from newsletter_subscribers by ID
   - Builds confirmation URL: https://{AGENTPULSE_DOMAIN}/#/confirm/{subscriber.confirmation_token}
   - Sends email via Resend:
     from: AgentPulse <{NEWSLETTER_FROM_EMAIL}>
     to: subscriber email
     subject: "Confirm your AgentPulse subscription"
     html: Simple styled email with:
       "Thanks for subscribing to AgentPulse Intelligence Brief!"
       "Click below to confirm your subscription:"
       [Confirm Subscription] button/link
       "If you didn't subscribe, just ignore this email."
   - Returns success/failure

2. Add a check_pending_subscribers() function:
   - Queries newsletter_subscribers where status='pending' and confirmed_at IS NULL
   - For each: sends confirmation email, no status change (waits for click)
   - Returns {emails_sent: N}

3. Add to the watch loop or scheduler:
   - Check for pending subscribers every 5 minutes (or add to the main poll loop)
   - schedule.every(5).minutes.do(check_pending_subscribers)

4. Add 'check_pending_subscribers' to execute_task() and argparse choices.

Don't modify any other functions.
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
# Subscribe via the web form
# Check processor logs — should send confirmation email within 5 minutes
docker compose logs processor | grep -i "confirm"
```

---

## Prompt 8: Wire /subscribers Command to Gato

```
Add a /subscribers command so the operator can see subscription stats from Telegram.

1. Add to the Processor's execute_task():
   'get_subscriber_stats':
   - Query newsletter_subscribers:
     * Count where status='active'
     * Count where status='pending'
     * Count where status='unsubscribed'
     * Get 5 most recent subscribers (email, subscribed_at, status)
   - Query newsletter_deliveries:
     * Count sent in last 7 days
     * Count failed in last 7 days
   - Return all stats

2. Update data/openclaw/workspace/AGENTS.md:
   - /subscribers → write {"task":"get_subscriber_stats","params":{}} to the queue.
     Display: active count, pending count, recent signups, delivery stats.
     Format nicely for Telegram.

3. Update skills/agentpulse/SKILL.md — add to commands table:
   | /subscribers | Show email subscriber stats |
```

**After this:**
```bash
docker compose build processor --no-cache
docker compose up processor -d
docker compose restart gato
# Test: /subscribers on Telegram
```

---

## Post-Deployment Verification

```bash
# 1. All 5 services running
docker compose ps
# Expected: gato, analyst, processor, newsletter, web — all "Up"

# 2. LLM routing
docker compose logs processor | grep "Model routing"
# Should show extraction=gpt-4o-mini, opportunity_generation=gpt-4o, etc.

# 3. Web archive
curl -s https://yourdomain.com | head -20
# Should return HTML with "AgentPulse" in it

# OR if localhost:
curl -sk https://localhost | head -20

# 4. Newsletter visible on web (need at least one published newsletter)
curl -s "https://<supabase-url>/rest/v1/newsletters?status=eq.published&select=title,edition_number" \
  -H "apikey: <anon-key>" \
  -H "Authorization: Bearer <anon-key>"

# 5. Subscribe flow
# Visit /#/subscribe, enter email
# Check Supabase: newsletter_subscribers has pending row
# Wait for confirmation email
# Click confirm link
# Check Supabase: status changed to 'active'

# 6. Full publish + email test
# /newsletter-full → generate
# /newsletter → review
# /newsletter-publish → should send Telegram AND email
docker compose logs processor | grep -i "email\|resend\|delivery"

# 7. Telegram commands
# /subscribers — should show stats
```

---

## Troubleshooting

**Web archive shows blank page:**
→ Check browser console for errors
→ Verify Supabase URL was injected: `docker compose exec web cat /srv/app.js | head -5`
→ Check RLS: anon key should be able to read published newsletters

**Caddy can't get HTTPS certificate:**
→ DNS must be pointing to the server. Check: `dig pulse.yourdomain.com`
→ Port 80 must be open (Caddy uses HTTP-01 challenge): `sudo ufw allow 80/tcp`
→ Check Caddy logs: `docker compose logs web`

**Emails not sending:**
→ Check RESEND_API_KEY is set: `docker compose exec processor env | grep RESEND`
→ Check Resend dashboard for errors
→ Verify domain is verified in Resend
→ Check delivery logs: `SELECT * FROM newsletter_deliveries ORDER BY sent_at DESC LIMIT 5;`

**Subscribe form fails:**
→ RLS policy for INSERT must exist on newsletter_subscribers
→ Check browser console for Supabase error response
→ Verify anon key can insert: the "Anyone can subscribe" policy must be active

**Confirmation email never arrives:**
→ Check processor scheduler is running: `docker compose logs processor | grep "pending_subscribers"`
→ Check if the subscriber row exists with status='pending'
→ Check Resend dashboard for queued/bounced emails
→ Check spam folder

**Model routing not working:**
→ Verify config file is mounted: `docker compose exec processor cat /home/openclaw/.openclaw/config/agentpulse-config.json`
→ Check for JSON syntax errors in the config
→ The get_model() function should log which model it's using — check processor logs
