# AgentPulse Phase 3 Weeks 2-3: LLM Optimization, Web Archive, Email Service

**Date:** February 13, 2026  
**Prerequisite:** Phase 3 Week 1 complete (security + content upgrade)

---

## Week 2: LLM Cost Optimization + Web Archive

### Part 1: LLM Cost Optimization

#### Current State
Every OpenAI call uses `gpt-4o` via the `AGENTPULSE_OPENAI_MODEL` env var. This is expensive for tasks that are essentially structured extraction with clear prompts.

#### Model Routing

| Task | Current | Target | Savings | Rationale |
|------|---------|--------|---------|-----------|
| Problem extraction | gpt-4o | gpt-4o-mini | ~90% | Structured extraction, clear schema, doesn't need reasoning |
| Tool extraction | gpt-4o | gpt-4o-mini | ~90% | Same — pattern matching and classification |
| Clustering | gpt-4o | gpt-4o-mini | ~90% | Grouping by similarity, not complex judgment |
| Trending topics | gpt-4o | gpt-4o-mini | ~90% | Content identification, clear criteria |
| Opportunity generation | gpt-4o | gpt-4o | 0% | Needs creativity and business judgment — keep quality |
| Digest summary | gpt-4o | gpt-4o-mini | ~90% | Formatting/summarization task |
| Tool stats | No LLM | No LLM | N/A | Pure Python computation |
| Analyst reasoning | Anthropic | Anthropic | N/A | This IS the intelligence — never downgrade |
| Newsletter writing | Anthropic | Anthropic | N/A | Editorial voice quality matters |

**Net effect:** ~60-70% reduction in OpenAI spend. Anthropic costs unchanged.

#### Implementation

Add a model config to `config/agentpulse-config.json`:

```json
{
  "models": {
    "extraction": "gpt-4o-mini",
    "clustering": "gpt-4o-mini",
    "trending_topics": "gpt-4o-mini",
    "opportunity_generation": "gpt-4o",
    "digest": "gpt-4o-mini",
    "default": "gpt-4o"
  },
  "pipeline": {
    "scrape_interval_hours": 6,
    "analysis_interval_hours": 12,
    "digest_hour": "09:00",
    "newsletter_day": "monday",
    "newsletter_hour": "07:00"
  }
}
```

The Processor reads the model config at startup and uses the appropriate model per task. A helper function:

```python
def get_model(task_name: str) -> str:
    """Get the appropriate model for a task from config."""
    config_path = Path('/home/openclaw/.openclaw/config/agentpulse-config.json')
    if config_path.exists():
        config = json.loads(config_path.read_text())
        models = config.get('models', {})
        return models.get(task_name, models.get('default', OPENAI_MODEL))
    return OPENAI_MODEL
```

Then each function uses `model=get_model('extraction')` instead of `model=OPENAI_MODEL`.

---

### Part 2: Web Archive

#### Architecture

A lightweight Docker service running Caddy (auto-HTTPS reverse proxy) serving a single-page HTML app that reads newsletters from Supabase.

```
agentpulse-web (new Docker service)
├── Caddy (reverse proxy, auto-HTTPS via Let's Encrypt)
├── Static HTML/CSS/JS
├── Reads from Supabase via anon key (RLS protects everything except published newsletters)
└── Single page: list of editions + individual edition rendering
```

#### Why Caddy
- Auto-HTTPS with Let's Encrypt (zero config)
- Tiny footprint (~30MB)
- Single binary, single config file
- Perfect for serving static files + reverse proxy

#### Tech Stack
- **No framework.** Single HTML file with vanilla JS.
- **marked.js** for markdown → HTML rendering (CDN)
- **Supabase JS client** for data fetching (CDN)
- Minimal CSS — clean, readable, newsletter-style typography

#### Pages
The site is a single HTML file with client-side routing:

- `/#/` — List of published newsletters, newest first. Shows: edition number, title, date, short excerpt.
- `/#/edition/:number` — Full newsletter rendered from markdown. Clean reading experience.
- `/#/subscribe` — Email subscription form (placeholder until Week 3).

#### Design Principles
- Newsletter-style layout: centered column, max-width 680px, generous line-height
- Serif font for body text (Georgia or similar) — feels editorial, not techy
- Clean header with AgentPulse branding
- Each edition shows publish date and edition number
- Responsive — works on mobile
- Fast — no framework, no build step, loads in < 1 second

#### Docker Setup

```yaml
# Add to docker-compose.yml
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

# Add to volumes:
volumes:
  workspace-data:
  caddy-data:
  caddy-config:
```

#### Caddy Configuration

```
# docker/web/Caddyfile
{$DOMAIN:localhost} {
    root * /srv
    file_server
    encode gzip

    # SPA fallback — serve index.html for all routes
    try_files {path} /index.html

    # Security headers
    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Referrer-Policy strict-origin-when-cross-origin
        Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://*.supabase.co; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; connect-src https://*.supabase.co; img-src 'self' data:"
    }
}
```

#### Web Dockerfile

```dockerfile
FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile
COPY site/ /srv/
```

#### Site Structure

```
docker/web/
├── Dockerfile
├── Caddyfile
└── site/
    ├── index.html      # Single-page app (list + reader)
    ├── style.css        # Newsletter typography
    └── app.js           # Supabase client + routing + rendering
```

#### index.html (Key Structure)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AgentPulse Intelligence Brief</title>
    <link rel="stylesheet" href="/style.css">
    <link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,wght@0,400;0,600;1,400&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
</head>
<body>
    <header>
        <div class="container">
            <h1 class="site-title">AgentPulse</h1>
            <p class="site-tagline">Weekly intelligence from the agent economy</p>
        </div>
    </header>

    <main class="container">
        <!-- List view -->
        <div id="list-view">
            <div id="newsletter-list"></div>
        </div>

        <!-- Reader view -->
        <div id="reader-view" style="display:none">
            <a href="#/" class="back-link">&larr; All editions</a>
            <article id="newsletter-content"></article>
        </div>

        <!-- Subscribe placeholder -->
        <div id="subscribe-view" style="display:none">
            <h2>Subscribe</h2>
            <p>Get the AgentPulse Intelligence Brief delivered to your inbox every week.</p>
            <form id="subscribe-form">
                <input type="email" placeholder="your@email.com" required>
                <button type="submit">Subscribe</button>
            </form>
        </div>
    </main>

    <footer>
        <div class="container">
            <p>AgentPulse — Signal from noise in the agent economy</p>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="/app.js"></script>
</body>
</html>
```

#### style.css (Key Styles)

```css
:root {
    --font-body: 'Newsreader', Georgia, serif;
    --font-ui: 'Inter', -apple-system, sans-serif;
    --color-bg: #fafaf8;
    --color-text: #1a1a1a;
    --color-muted: #666;
    --color-accent: #2563eb;
    --color-border: #e5e5e5;
    --max-width: 680px;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: var(--font-body);
    color: var(--color-text);
    background: var(--color-bg);
    line-height: 1.7;
    font-size: 18px;
}

.container {
    max-width: var(--max-width);
    margin: 0 auto;
    padding: 0 20px;
}

/* Header */
header {
    padding: 40px 0 20px;
    border-bottom: 1px solid var(--color-border);
    margin-bottom: 40px;
}

.site-title {
    font-family: var(--font-ui);
    font-size: 28px;
    font-weight: 600;
    letter-spacing: -0.5px;
}

.site-tagline {
    color: var(--color-muted);
    font-size: 16px;
    font-family: var(--font-ui);
    margin-top: 4px;
}

/* Newsletter list */
.edition-card {
    padding: 24px 0;
    border-bottom: 1px solid var(--color-border);
}

.edition-card:hover { background: rgba(0,0,0,0.01); }

.edition-meta {
    font-family: var(--font-ui);
    font-size: 13px;
    color: var(--color-muted);
    margin-bottom: 6px;
}

.edition-title {
    font-size: 22px;
    font-weight: 600;
    color: var(--color-text);
    text-decoration: none;
    line-height: 1.3;
}

.edition-title:hover { color: var(--color-accent); }

.edition-excerpt {
    color: var(--color-muted);
    font-size: 16px;
    margin-top: 8px;
    line-height: 1.5;
}

/* Reader */
.back-link {
    font-family: var(--font-ui);
    font-size: 14px;
    color: var(--color-accent);
    text-decoration: none;
    display: inline-block;
    margin-bottom: 30px;
}

article h1 { font-size: 32px; line-height: 1.2; margin-bottom: 8px; }
article h2 { font-size: 22px; margin-top: 36px; margin-bottom: 12px; font-family: var(--font-ui); }
article h3 { font-size: 18px; margin-top: 24px; margin-bottom: 8px; font-family: var(--font-ui); }
article p { margin-bottom: 16px; }
article ul, article ol { margin-bottom: 16px; padding-left: 24px; }
article li { margin-bottom: 8px; }
article blockquote {
    border-left: 3px solid var(--color-accent);
    padding-left: 16px;
    color: var(--color-muted);
    font-style: italic;
    margin: 20px 0;
}

.article-meta {
    font-family: var(--font-ui);
    font-size: 14px;
    color: var(--color-muted);
    margin-bottom: 30px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--color-border);
}

/* Subscribe */
#subscribe-form {
    display: flex;
    gap: 8px;
    max-width: 400px;
    margin-top: 16px;
}

#subscribe-form input {
    flex: 1;
    padding: 10px 14px;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    font-size: 16px;
    font-family: var(--font-ui);
}

#subscribe-form button {
    padding: 10px 20px;
    background: var(--color-accent);
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-family: var(--font-ui);
    font-weight: 500;
    cursor: pointer;
}

#subscribe-form button:hover { background: #1d4ed8; }

/* Footer */
footer {
    margin-top: 60px;
    padding: 20px 0;
    border-top: 1px solid var(--color-border);
    font-family: var(--font-ui);
    font-size: 13px;
    color: var(--color-muted);
}

/* Responsive */
@media (max-width: 600px) {
    body { font-size: 16px; }
    .edition-title { font-size: 19px; }
    article h1 { font-size: 26px; }
}
```

#### app.js (Core Logic)

```javascript
// Config — injected at build time or hardcoded (anon key is safe with RLS)
const SUPABASE_URL = '__SUPABASE_URL__';
const SUPABASE_ANON_KEY = '__SUPABASE_ANON_KEY__';

const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// Simple hash-based router
function getRoute() {
    const hash = window.location.hash || '#/';
    if (hash.startsWith('#/edition/')) {
        return { view: 'reader', edition: parseInt(hash.split('/')[2]) };
    }
    if (hash === '#/subscribe') {
        return { view: 'subscribe' };
    }
    return { view: 'list' };
}

function showView(viewName) {
    document.getElementById('list-view').style.display = viewName === 'list' ? 'block' : 'none';
    document.getElementById('reader-view').style.display = viewName === 'reader' ? 'block' : 'none';
    document.getElementById('subscribe-view').style.display = viewName === 'subscribe' ? 'block' : 'none';
}

// Load newsletter list
async function loadList() {
    showView('list');
    const { data, error } = await supabase
        .from('newsletters')
        .select('edition_number, title, content_markdown, published_at')
        .eq('status', 'published')
        .order('edition_number', { ascending: false });

    if (error || !data) {
        document.getElementById('newsletter-list').innerHTML = '<p>No newsletters yet.</p>';
        return;
    }

    const html = data.map(n => {
        const date = new Date(n.published_at).toLocaleDateString('en-US', {
            year: 'numeric', month: 'long', day: 'numeric'
        });
        // Extract first ~150 chars as excerpt
        const excerpt = (n.content_markdown || '').replace(/[#*_\[\]]/g, '').substring(0, 150) + '...';

        return `
            <div class="edition-card">
                <div class="edition-meta">Edition #${n.edition_number} · ${date}</div>
                <a href="#/edition/${n.edition_number}" class="edition-title">${n.title}</a>
                <p class="edition-excerpt">${excerpt}</p>
            </div>
        `;
    }).join('');

    document.getElementById('newsletter-list').innerHTML = html || '<p>No newsletters published yet.</p>';
}

// Load single edition
async function loadEdition(editionNumber) {
    showView('reader');
    const { data, error } = await supabase
        .from('newsletters')
        .select('*')
        .eq('edition_number', editionNumber)
        .eq('status', 'published')
        .single();

    if (error || !data) {
        document.getElementById('newsletter-content').innerHTML = '<p>Edition not found.</p>';
        return;
    }

    const date = new Date(data.published_at).toLocaleDateString('en-US', {
        year: 'numeric', month: 'long', day: 'numeric'
    });

    const rendered = marked.parse(data.content_markdown || '');

    document.getElementById('newsletter-content').innerHTML = `
        <h1>${data.title}</h1>
        <div class="article-meta">Edition #${data.edition_number} · Published ${date}</div>
        ${rendered}
    `;

    // Scroll to top
    window.scrollTo(0, 0);
}

// Router
function route() {
    const r = getRoute();
    switch (r.view) {
        case 'list': loadList(); break;
        case 'reader': loadEdition(r.edition); break;
        case 'subscribe': showView('subscribe'); break;
    }
}

window.addEventListener('hashchange', route);
window.addEventListener('DOMContentLoaded', route);
```

#### Supabase URL Injection

The `app.js` file has placeholder values for `SUPABASE_URL` and `SUPABASE_ANON_KEY`. These get replaced at container startup. Add to the Dockerfile or entrypoint:

```bash
#!/bin/sh
# Replace placeholders with actual env vars
sed -i "s|__SUPABASE_URL__|${SUPABASE_URL}|g" /srv/app.js
sed -i "s|__SUPABASE_ANON_KEY__|${SUPABASE_ANON_KEY}|g" /srv/app.js

# Start Caddy
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
```

#### Domain Setup

You'll need a domain pointing to your Hetzner server. Options:

1. **Buy a domain** (e.g., `agentpulse.io`, `pulse.yourdomain.com`)
2. **Add an A record** pointing to your server IP
3. **Update .env:** `AGENTPULSE_DOMAIN=agentpulse.yourdomain.com`
4. **Open port 443:** `sudo ufw allow 443/tcp`
5. Caddy handles Let's Encrypt automatically — just set the domain in the Caddyfile

---

## Week 3: Email Newsletter Service

### Architecture

```
On newsletter publish:
  Processor → converts markdown to HTML email
  Processor → queries active subscribers
  Processor → sends via Resend API
  Processor → logs delivery
```

### Why Resend
- Simplest API: one HTTP call to send
- 100 emails/day free, 3000/month
- Built-in analytics (opens, clicks)
- No complex setup — just an API key and a verified domain

### Database

```sql
-- Subscribers table
CREATE TABLE newsletter_subscribers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    subscribed_at TIMESTAMPTZ DEFAULT NOW(),
    unsubscribed_at TIMESTAMPTZ,
    status TEXT DEFAULT 'pending',       -- pending, active, unsubscribed, bounced
    confirmation_token UUID DEFAULT uuid_generate_v4(),
    confirmed_at TIMESTAMPTZ,
    source TEXT DEFAULT 'web',           -- web, manual, telegram
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
    status TEXT DEFAULT 'sent',          -- sent, delivered, opened, bounced, failed
    resend_id TEXT,                      -- Resend's message ID for tracking
    error_message TEXT,
    metadata JSONB
);

CREATE INDEX idx_deliveries_newsletter ON newsletter_deliveries(newsletter_id);
CREATE INDEX idx_deliveries_status ON newsletter_deliveries(status);

-- RLS: subscribers table is NOT public (email addresses are PII)
ALTER TABLE newsletter_subscribers ENABLE ROW LEVEL SECURITY;
ALTER TABLE newsletter_deliveries ENABLE ROW LEVEL SECURITY;
-- No public SELECT policies — only service_role can access
```

### Subscription Flow

```
1. User visits web archive → clicks "Subscribe"
2. Enters email → frontend calls Supabase Edge Function or direct insert
3. Row created: status='pending', confirmation_token generated
4. Processor detects new pending subscriber → sends confirmation email via Resend
5. Email contains link: https://yourdomain.com/#/confirm/<token>
6. User clicks → frontend calls Supabase to update: status='active', confirmed_at=NOW()
7. User now receives newsletters
```

### Unsubscribe Flow

```
1. Every email footer contains: https://yourdomain.com/#/unsubscribe/<subscriber_id>
2. User clicks → frontend updates: status='unsubscribed', unsubscribed_at=NOW()
3. User no longer receives newsletters
```

### Email Sending (Processor)

```python
import httpx

RESEND_API_KEY = os.getenv('RESEND_API_KEY')
NEWSLETTER_FROM_EMAIL = os.getenv('NEWSLETTER_FROM_EMAIL', 'pulse@yourdomain.com')

def send_newsletter_email(newsletter_id: str) -> dict:
    """Send a published newsletter to all active subscribers."""
    if not supabase or not RESEND_API_KEY:
        return {'error': 'Not configured'}

    # Get the newsletter
    nl = supabase.table('newsletters')\
        .select('*')\
        .eq('id', newsletter_id)\
        .single()\
        .execute()

    if not nl.data:
        return {'error': 'Newsletter not found'}

    newsletter = nl.data

    # Convert markdown to HTML
    html_content = markdown_to_html_email(newsletter['content_markdown'])

    # Get active subscribers
    subs = supabase.table('newsletter_subscribers')\
        .select('*')\
        .eq('status', 'active')\
        .execute()

    if not subs.data:
        return {'sent': 0, 'reason': 'no_active_subscribers'}

    sent = 0
    failed = 0

    for subscriber in subs.data:
        try:
            response = httpx.post(
                'https://api.resend.com/emails',
                headers={
                    'Authorization': f'Bearer {RESEND_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'from': f'AgentPulse <{NEWSLETTER_FROM_EMAIL}>',
                    'to': subscriber['email'],
                    'subject': f"AgentPulse #{newsletter['edition_number']}: {newsletter['title']}",
                    'html': html_content,
                    'headers': {
                        'List-Unsubscribe': f'<https://yourdomain.com/#/unsubscribe/{subscriber["id"]}>'
                    }
                },
                timeout=10
            )

            resend_data = response.json()

            # Log delivery
            supabase.table('newsletter_deliveries').insert({
                'newsletter_id': newsletter_id,
                'subscriber_id': subscriber['id'],
                'status': 'sent' if response.status_code == 200 else 'failed',
                'resend_id': resend_data.get('id'),
                'error_message': resend_data.get('message') if response.status_code != 200 else None
            }).execute()

            if response.status_code == 200:
                sent += 1
            else:
                failed += 1

        except Exception as e:
            logger.error(f"Failed to send to {subscriber['email']}: {e}")
            failed += 1

    return {'sent': sent, 'failed': failed, 'total_subscribers': len(subs.data)}


def markdown_to_html_email(markdown_text: str) -> str:
    """Convert newsletter markdown to a styled HTML email."""
    # Use a simple markdown → HTML conversion
    # Could use the 'markdown' pip package or manual conversion
    import re

    html = markdown_text

    # Basic markdown → HTML conversions
    # Headers
    html = re.sub(r'^### (.+)$', r'<h3 style="font-family:sans-serif;font-size:18px;margin-top:24px;">\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2 style="font-family:sans-serif;font-size:22px;margin-top:32px;border-bottom:1px solid #eee;padding-bottom:8px;">\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1 style="font-family:sans-serif;font-size:28px;">\1</h1>', html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

    # Paragraphs (double newlines)
    paragraphs = html.split('\n\n')
    html = ''.join(
        f'<p style="line-height:1.6;margin-bottom:16px;">{p.strip()}</p>'
        for p in paragraphs if p.strip() and not p.strip().startswith('<h')
    )

    # Wrap in email template
    return f"""
    <div style="max-width:600px;margin:0 auto;font-family:Georgia,serif;font-size:17px;color:#1a1a1a;background:#fafaf8;padding:32px 24px;">
        <div style="text-align:center;margin-bottom:32px;padding-bottom:16px;border-bottom:1px solid #e5e5e5;">
            <h1 style="font-family:sans-serif;font-size:24px;margin:0;">AgentPulse</h1>
            <p style="color:#666;font-size:14px;font-family:sans-serif;">Weekly intelligence from the agent economy</p>
        </div>
        {html}
        <div style="margin-top:40px;padding-top:16px;border-top:1px solid #e5e5e5;font-size:13px;color:#999;font-family:sans-serif;">
            <p>You're receiving this because you subscribed to AgentPulse Intelligence Brief.</p>
            <p><a href="{{{{unsubscribe_url}}}}" style="color:#666;">Unsubscribe</a></p>
        </div>
    </div>
    """
```

### Updated Publish Flow

When `/newsletter-publish` is triggered:
1. Send to Telegram (existing)
2. Send to email subscribers (new)
3. Mark as published
4. Update newsletter_appearances on opportunities
5. Log everything

### Web Archive Updates for Subscribe/Confirm/Unsubscribe

The `app.js` needs new routes:
- `#/subscribe` — form that inserts into `newsletter_subscribers`
- `#/confirm/:token` — confirms subscription
- `#/unsubscribe/:id` — unsubscribes

These need Supabase Edge Functions or a simple API since the anon key can't write to `newsletter_subscribers` (RLS blocks it). Options:
1. **Supabase Edge Function** (recommended) — a small Deno function that handles subscribe/confirm/unsubscribe
2. **Add a public INSERT policy** with strict validation — simpler but less secure
3. **Route through the Processor** — subscriber writes to a web form, Processor picks it up

The Edge Function approach is cleanest:

```typescript
// supabase/functions/subscribe/index.ts
import { createClient } from '@supabase/supabase-js'

Deno.serve(async (req) => {
  const { email } = await req.json()

  if (!email || !email.includes('@')) {
    return new Response(JSON.stringify({ error: 'Invalid email' }), { status: 400 })
  }

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  )

  const { data, error } = await supabase
    .from('newsletter_subscribers')
    .upsert({ email, status: 'pending' }, { onConflict: 'email' })
    .select()
    .single()

  if (error) {
    return new Response(JSON.stringify({ error: error.message }), { status: 500 })
  }

  // TODO: trigger confirmation email via Resend

  return new Response(JSON.stringify({ success: true }), { status: 200 })
})
```

### Resend Setup

1. Sign up at resend.com
2. Add and verify your domain (DNS TXT + DKIM records)
3. Get API key
4. Add to .env: `RESEND_API_KEY=re_...`
5. Add to .env: `NEWSLETTER_FROM_EMAIL=pulse@yourdomain.com`

### Telegram Commands

| Command | Action |
|---------|--------|
| `/subscribers` (NEW) | Show subscriber count and recent signups |
| `/newsletter-publish` (updated) | Now also sends email to subscribers |

---

## Implementation Sequence

```
Week 2:
  Prompt 1: LLM model routing in Processor
  Prompt 2: Web archive Docker service + Caddy + HTML/CSS/JS
  Prompt 3: Domain + HTTPS setup (manual)
  Prompt 4: Open firewall port 443 (manual)

Week 3:
  Prompt 5: Supabase schema for subscribers + deliveries
  Prompt 6: Resend integration in Processor
  Prompt 7: Subscribe/confirm/unsubscribe in web archive
  Prompt 8: Update publish flow to include email
  Prompt 9: Wire /subscribers command to Gato
```
