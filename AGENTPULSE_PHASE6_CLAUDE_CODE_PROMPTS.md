# AgentPulse Phase 6: Dual-Audience Platform — Claude Code Prompts

> **Context files to reference:** `ARCHITECTURE.md`, `AGENTPULSE_PHASE6_DUAL_AUDIENCE.md`
> **Run each prompt from the project root:** `cd ~/bitcoin_bot`
> **Claude Code can read your files directly — point it at the right ones.**

---

## How Claude Code Prompts Differ from Cursor

- Claude Code has full filesystem + terminal access. It can read, edit, run, and test.
- Give it the full context upfront: which files to read, what to change, what to verify.
- Let it run tests and verify its own work.
- One prompt can span multiple files — no need to split by file.

---

## Parallel Execution Map

```
Round 1: Prompt 1 (SQL) — run manually in Supabase

Round 2 (parallel — different files, no conflicts):
  Terminal A: Prompt 2 (web redesign — docker/web/ only)
  Terminal B: Prompt 3 (newsletter agent — templates/ + skills/ only)
  Terminal C: Prompt 4 (financial sources — docker/processor/ only)

Round 3 (parallel — different files):
  Terminal A: Prompt 5 (analyst identity — templates/analyst/ only)
  Terminal B: Prompt 6 (subscribe form — docker/web/ only, after Prompt 2)

Round 4 (sequential — depends on everything):
  Prompt 7 (newsletter poller + processor updates)
  Prompt 8 (scheduling + Telegram commands)
```

---

## Prompt 1: Database Schema

Run this SQL directly in the Supabase SQL Editor:

```sql
-- ================================================
-- PHASE 6: DUAL-AUDIENCE PLATFORM
-- ================================================

-- 1. Impact mode content column on newsletters
ALTER TABLE newsletters ADD COLUMN IF NOT EXISTS content_markdown_impact TEXT;
ALTER TABLE newsletters ADD COLUMN IF NOT EXISTS title_impact TEXT;

-- 2. Subscribers table
CREATE TABLE IF NOT EXISTS subscribers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    mode_preference TEXT DEFAULT 'impact',
    status TEXT DEFAULT 'pending',
    confirmation_token TEXT,
    confirmed_at TIMESTAMPTZ,
    unsubscribed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_subscribers_status ON subscribers(status);
CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email);

-- 3. Email deliveries table
CREATE TABLE IF NOT EXISTS email_deliveries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subscriber_id UUID REFERENCES subscribers(id),
    newsletter_id UUID REFERENCES newsletters(id),
    mode_sent TEXT,
    status TEXT DEFAULT 'queued',
    sent_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_deliveries_newsletter ON email_deliveries(newsletter_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_status ON email_deliveries(status);

-- 4. RLS
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_deliveries ENABLE ROW LEVEL SECURITY;

-- Subscribers can only be read/written by service role (no public access)
-- Email deliveries same
```

**Verify:** Check Supabase Table Editor — `subscribers` and `email_deliveries` exist, `newsletters` has `content_markdown_impact` and `title_impact` columns.

---

## Prompt 2: Web Archive Redesign with Toggle

```
Read these files first:
- docker/web/site/index.html
- docker/web/site/style.css
- docker/web/site/app.js
- AGENTPULSE_PHASE6_DUAL_AUDIENCE.md (Part 4: Web Archive Redesign)

Redesign the web archive to support a dual-mode toggle between Builder Mode and Impact Mode. The toggle switches the entire reading experience: colors, typography, and content.

Here's exactly what to do:

1. Replace docker/web/site/style.css with THREE separate CSS files:

   docker/web/site/style-shared.css:
   - Base layout, container, toggle component, transitions, responsive breakpoints
   - The toggle bar: flex row with "⚡ Builder" label, toggle track (56x28px rounded), "🌍 Impact" label
   - Toggle thumb animates left↔right with cubic-bezier spring
   - .mode-transitioning class adds 400ms transition to all color/bg properties
   - Mode indicator: fixed bottom-right pill that flashes on toggle
   - Footer, subscribe section layout
   - Media queries for mobile

   docker/web/site/style-builder.css:
   - body.builder styles
   - Background: #0a0a0f, text: #e0e0e8, accent: #00d4aa
   - Font body: 'JetBrains Mono', monospace (14.5px)
   - Font display: 'Outfit', sans-serif
   - Section headers: uppercase, letter-spacing 0.06em, accent color, prefixed with "// "
   - Monospace feel, terminal-like, sharp edges
   - Gato corner: left border #f7931a, dark bitcoin-orange tint
   - Edition meta: monospace, accent color, small

   docker/web/site/style-impact.css:
   - body.impact styles
   - Background: #faf8f4, text: #1a1a1a, accent: #c44b2b
   - Font body: 'Newsreader', Georgia, serif (18px)
   - Font display: 'Fraunces', Georgia, serif
   - Section headers: normal case, border-bottom, warm feel
   - Editorial, magazine-like, generous spacing
   - Gato corner: subtle background, rounded corners
   - Edition meta: small serif, muted

2. Update docker/web/site/index.html:
   - Add Google Fonts link for: JetBrains Mono, Outfit, Newsreader, Fraunces
   - Link all three CSS files (shared always, builder/impact via id="mode-stylesheet")
   - Add the toggle bar HTML between header and content:
     <div class="toggle-bar">
       <span class="toggle-label builder-lbl" onclick="setMode('builder')">⚡ Builder</span>
       <div class="toggle-track" onclick="toggleMode()"><div class="toggle-thumb"></div></div>
       <span class="toggle-label impact-lbl" onclick="setMode('impact')">🌍 Impact</span>
     </div>
   - Add a mode indicator div (fixed position, bottom right)
   - Add a subscribe section at the bottom with email input + mode preference radio (builder/impact/both) + submit button

3. Update docker/web/site/app.js:
   - Add mode state management:
     * Read mode from localStorage ('agentpulse_mode') or URL param (?mode=builder)
     * Default to 'impact' for new visitors
     * setMode(mode) function that: updates body class, swaps active stylesheet href,
       updates toggle UI, updates URL param without reload, saves to localStorage,
       flashes mode indicator, and re-renders current article if loaded
   - Update loadEdition(number) to be mode-aware:
     * After fetching newsletter from Supabase, check if content_markdown_impact exists
     * If current mode is 'impact' AND content_markdown_impact exists: render that
     * Otherwise: render content_markdown (builder version, or fallback)
     * Same for title vs title_impact
     * Store the full newsletter object on window.currentNewsletter so toggle can re-render without refetching
   - Update loadList() to show titles based on current mode
   - Add toggleMode() function
   - Add subscribe form handler (POST to Supabase subscribers table via anon key + RLS)

4. Update the Supabase query in app.js to also select content_markdown_impact and title_impact columns.

5. Add the subscribe RLS policy — allow anonymous inserts to subscribers (for the subscribe form):
   NOTE: Don't run SQL from here. Just add a comment in the code noting this RLS policy is needed:
   -- CREATE POLICY "Allow public subscribe" ON subscribers FOR INSERT WITH CHECK (true);

After making all changes, verify:
- Open docker/web/site/index.html in a browser locally
- Toggle should switch colors, fonts, and overall feel
- URL should update with ?mode=builder or ?mode=impact
- Refreshing should remember the last mode

Don't modify any Python files, Docker configs, or files outside docker/web/site/.
```

---

## Prompt 3: Newsletter Agent — Write Both Versions

```
Read these files first:
- templates/newsletter/IDENTITY.md
- skills/newsletter/SKILL.md
- AGENTPULSE_PHASE6_DUAL_AUDIENCE.md (Part 3: Impact Mode Voice, Part 6: Newsletter Agent Changes)

Update the Newsletter agent's identity and skill files so it produces TWO versions of each newsletter: a Builder version (current) and an Impact version (new).

1. Edit templates/newsletter/IDENTITY.md — ADD a new section after "Source Authority":

   ## Impact Mode Voice

   When writing the Impact Mode version, you are NOT dumbing things down.
   You are translating implications.

   The reader is smart but not technical. They might be:
   - A product manager worried about their job
   - An investor trying to understand portfolio risk
   - A policymaker trying to write regulation
   - A parent trying to advise their college-age kid on career choices

   Rules:
   - Replace jargon with consequences: "MCP adoption" → "a new standard that lets AI access your tools directly"
   - Every insight must answer "what does this mean for ME?"
   - Lead with the human impact, then explain the technical mechanism
   - Use analogies from domains the reader already understands
   - Include specific actions: "If you work in X, here's what to do"

   Voice references:
   - Kara Swisher explaining tech to a business audience
   - The Economist making complex topics accessible without condescension
   - Morgan Housel connecting financial concepts to human behavior

   Example translation:

   Builder: "Three new agent memory frameworks launched. Star velocity suggests
   'building' phase. Consolidation expected by Q3."

   Impact: "AI systems are racing to develop permanent memory — the ability to
   remember your preferences, past conversations, and habits. Three new approaches
   launched this week, and the pace suggests a dominant approach by summer. For
   consumers, this means AI that knows you. For workers, it means AI that learns
   your job by watching you — then doesn't need you anymore."

2. Edit skills/newsletter/SKILL.md — UPDATE the "Task: write_newsletter" section:

   Add this to the "What You Do" subsection:

   5. Write the Impact Mode version of the full brief:
      - Same data, different lens
      - Reframe every section for non-technical readers
      - Add two Impact-only sections: "The Economic Signal" and "Career Radar"
      - Replace "Tool Radar" with "What's Changing" in plain language
      - Gato's Corner stays the same in both versions

   UPDATE the "Output JSON" subsection to:

   Your response MUST be valid JSON with this structure:
   {
     "edition": <number>,
     "title": "<builder-focused headline>",
     "title_impact": "<impact-focused headline — what it means for everyone>",
     "content_markdown": "<full builder brief>",
     "content_markdown_impact": "<full impact brief>",
     "content_telegram": "<condensed version, under 500 chars>"
   }

   Add a new subsection after the output JSON:

   ### Impact Mode Section Guide

   The Impact version mirrors the Builder structure with these changes:

   **Cold open:** Lead with human/economic impact, not technical signal.
   **One Number:** Same number, but explain why a non-technical person should care.
   **Spotlight:** Same thesis, but explain the implications for jobs, money, and power.
   **The Big Insight:** Frame thesis in terms of careers, portfolios, industries — not tools.
   **Top Opportunities:** Reframe as "Where the Market Is Shifting" — what industries and
   business models are being created or destroyed.
   **Emerging Signals:** What should professionals watch for? Frame as career/industry intelligence.
   **The Economic Signal (Impact only):** Connect this week's agent data to broader economic
   implications — spending patterns, job market shifts, business model disruptions.
   **Career Radar (Impact only):** What this week's signals mean for employment. Which roles
   are being automated? Which skills are gaining value? Where are displaced professionals landing?
   **What's Changing (replaces Tool Radar):** Same tools, plain language. "A new open-source tool
   gained 1,200 developers in two days" instead of "1,200 GitHub stars in 48h."
   **Prediction Tracker:** Same format, add human-impact context.
   **Gato's Corner:** Same in both versions. Gato is Gato.

   Word counts:
   - Builder version: 800-1200 words (unchanged)
   - Impact version: 600-1000 words
   - Budget: increase max_llm_calls to 8 to accommodate dual output

3. After making changes, verify:
   - cat templates/newsletter/IDENTITY.md | grep -c "Impact Mode"  (should be >= 1)
   - cat skills/newsletter/SKILL.md | grep "content_markdown_impact"  (should appear)
   - cat skills/newsletter/SKILL.md | grep "title_impact"  (should appear)

Don't modify any Python files, processor code, or files outside templates/ and skills/.
```

---

## Prompt 4: Financial Source Expansion

```
Read these files first:
- docker/processor/agentpulse_processor.py (search for RSS_FEEDS and scrape_rss_feeds)
- AGENTPULSE_PHASE6_DUAL_AUDIENCE.md (Part 2: Financial Coverage Expansion)

Add financial and macro sources to the RSS feed scraper in docker/processor/agentpulse_processor.py.

1. Find the RSS_FEEDS dict and ADD these entries:

   'citrini': {
       'url': 'https://www.citriniresearch.com/feed',
       'tier': 1,
       'category': 'macro_research'
   },
   'byrne_hobart': {
       'url': 'https://www.thediff.co/feed',
       'tier': 1,
       'category': 'financial_analysis'
   },
   'stratechery': {
       'url': 'https://stratechery.com/feed/',
       'tier': 1,
       'category': 'business_analysis'
   },
   'cb_insights': {
       'url': 'https://www.cbinsights.com/research/feed/',
       'tier': 2,
       'category': 'market_research'
   },

2. Find the relevance keywords list (RSS_RELEVANCE_KEYWORDS or similar) and ADD financial keywords:

   'saas pricing', 'seat based', 'arr', 'net revenue retention',
   'white collar', 'displacement', 'layoff', 'headcount reduction',
   'interchange', 'stablecoin', 'payment rail', 'agent commerce',
   'private credit', 'lbo', 'software default',
   'mortgage', 'delinquency', 'consumer spending',
   'ghost gdp', 'labor share', 'wage compression',
   'compute tax', 'ai regulation', 'intermediation'

   Keep all existing keywords. Just extend the list.

3. Verify by searching for the new feeds:
   grep -c "citrini\|byrne_hobart\|stratechery\|cb_insights" docker/processor/agentpulse_processor.py
   # Should return at least 4

   grep "saas pricing\|interchange\|private credit" docker/processor/agentpulse_processor.py
   # Should find the new keywords

Don't modify any other functions or files. Only add to RSS_FEEDS and the keywords list.
```

---

## Prompt 5: Analyst Identity — Financial Transmission Analysis

```
Read this file first:
- templates/analyst/IDENTITY.md

Add financial transmission analysis capability to the Analyst.

Edit templates/analyst/IDENTITY.md — ADD this section after "Source Weighting" (or at the end, before any output format section):

## Financial Transmission Analysis

When analyzing agent economy signals, always consider the financial transmission
chain. Every technical shift creates economic ripple effects.

For each major finding, trace the chain:

1. **Business Model Impact:** How does this signal affect revenue models?
   - Seat-based pricing under pressure? (SaaS disruption)
   - Friction-based revenue threatened? (intermediation bypass)
   - Cost structure shifting from labor to compute? (OpEx substitution)

2. **Employment Impact:** Which roles does this automate or create?
   - Direct displacement: "This tool replaces the work of X role"
   - Indirect displacement: "This reduces demand for the service Y provides"
   - New roles: "This creates demand for people who can Z"

3. **Consumer Behavior:** How does this change spending patterns?
   - Friction removal: agents comparison-shopping, auto-canceling subscriptions
   - Spending shifts: where does displaced income go?
   - Intermediation bypass: agents routing around toll booths (interchange, commissions, fees)

4. **Systemic Risk:** Does this connect to larger financial structures?
   - Credit markets: private credit exposure to AI-disrupted sectors
   - Housing: white-collar income impairment affecting mortgage assumptions
   - Government revenue: tax base shrinking as labor share declines

Framework: Follow the money. Every technical shift creates winners and losers.
The winners buy compute. The losers stop spending. Both effects cascade.

When forming theses, always include the financial transmission in your reasoning.
A thesis about "agent memory consolidation" should also note "which businesses lose
revenue when memory becomes commoditized, and what happens to their employees."

Include in your output:
- 'financial_impact': For each major finding, a one-sentence financial transmission note
- 'employment_signals': Which roles are being automated/created based on this week's data

After making changes, run:
   grep "Financial Transmission" templates/analyst/IDENTITY.md
   # Should find the section header

Don't modify any other files.
```

---

## Prompt 6: Subscribe Form + Supabase Integration

```
Read these files first:
- docker/web/site/index.html (after Prompt 2 changes)
- docker/web/site/app.js (after Prompt 2 changes)
- docker/web/entrypoint.sh

Add a working subscription form to the web archive that writes to Supabase.

1. The subscribe section should already exist in index.html from Prompt 2.
   If not, add it before the footer:

   <section id="subscribe-section" class="container">
     <h2>Get the Intelligence Brief</h2>
     <p class="subscribe-tagline">Weekly analysis of the AI agent economy. Choose your lens.</p>
     <div class="subscribe-form">
       <input type="email" id="subscribe-email" placeholder="you@example.com" required />
       <div class="mode-preference">
         <label><input type="radio" name="pref" value="builder" /> ⚡ Builder</label>
         <label><input type="radio" name="pref" value="impact" checked /> 🌍 Impact</label>
         <label><input type="radio" name="pref" value="both" /> Both</label>
       </div>
       <button id="subscribe-btn" onclick="handleSubscribe()">Subscribe</button>
       <p id="subscribe-status" class="subscribe-status"></p>
     </div>
   </section>

2. Add subscribe form styles to docker/web/site/style-shared.css:

   #subscribe-section {
     margin: 60px auto;
     padding: 40px 24px;
     text-align: center;
     border-top: 1px solid var(--border);
   }
   #subscribe-section h2 {
     font-family: var(--font-display);
     margin-bottom: 8px;
   }
   .subscribe-tagline {
     color: var(--text-muted);
     margin-bottom: 24px;
   }
   .subscribe-form {
     max-width: 400px;
     margin: 0 auto;
   }
   #subscribe-email {
     width: 100%;
     padding: 12px 16px;
     font-size: 16px;
     border: 1px solid var(--border);
     border-radius: 6px;
     background: var(--bg-surface);
     color: var(--text);
     margin-bottom: 12px;
     font-family: var(--font-body);
   }
   .mode-preference {
     display: flex;
     justify-content: center;
     gap: 16px;
     margin-bottom: 16px;
     font-family: var(--font-display);
     font-size: 14px;
   }
   .mode-preference label {
     cursor: pointer;
     color: var(--text-muted);
   }
   #subscribe-btn {
     padding: 12px 32px;
     background: var(--accent);
     color: white;
     border: none;
     border-radius: 6px;
     font-family: var(--font-display);
     font-size: 14px;
     font-weight: 600;
     cursor: pointer;
     letter-spacing: 0.03em;
   }
   #subscribe-btn:hover {
     opacity: 0.9;
   }
   .subscribe-status {
     margin-top: 12px;
     font-size: 14px;
     min-height: 20px;
   }

3. Add handleSubscribe() to docker/web/site/app.js:

   async function handleSubscribe() {
     const email = document.getElementById('subscribe-email').value.trim();
     const pref = document.querySelector('input[name="pref"]:checked');
     const status = document.getElementById('subscribe-status');
     const btn = document.getElementById('subscribe-btn');

     if (!email || !email.includes('@')) {
       status.textContent = 'Please enter a valid email.';
       status.style.color = 'var(--accent)';
       return;
     }

     btn.disabled = true;
     btn.textContent = 'Subscribing...';

     try {
       const token = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
       const { data, error } = await supabase
         .from('subscribers')
         .insert({
           email: email,
           mode_preference: pref ? pref.value : 'impact',
           status: 'pending',
           confirmation_token: token
         });

       if (error) {
         if (error.code === '23505') { // unique violation
           status.textContent = 'This email is already subscribed.';
           status.style.color = 'var(--text-muted)';
         } else {
           throw error;
         }
       } else {
         status.textContent = 'Subscribed! Check your email to confirm.';
         status.style.color = 'var(--accent)';
         document.getElementById('subscribe-email').value = '';
       }
     } catch (err) {
       console.error('Subscribe error:', err);
       status.textContent = 'Something went wrong. Try again.';
       status.style.color = 'var(--accent)';
     }

     btn.disabled = false;
     btn.textContent = 'Subscribe';
   }

4. Make sure the Supabase anon key is injected via entrypoint.sh (it should already be from the existing web setup). The anon key is used for the subscribe insert — we need an RLS policy to allow it.

   Add a comment at the top of app.js:
   // NOTE: Requires RLS policy on subscribers: CREATE POLICY "Allow public subscribe" ON subscribers FOR INSERT WITH CHECK (true);

After making changes:
- Open the page locally and test the subscribe form
- Check that it writes to Supabase (or errors gracefully if RLS policy isn't set)

Don't modify any Python files or Docker configs.
```

---

## Prompt 7: Newsletter Poller + Processor Updates

```
Read these files first:
- docker/newsletter/newsletter_poller.py
- docker/processor/agentpulse_processor.py (search for prepare_newsletter_data and publish_newsletter)
- AGENTPULSE_PHASE6_DUAL_AUDIENCE.md (Part 1 and Part 6)

Update the newsletter poller to handle the new dual-output format, and update the processor to store and serve both versions.

1. Edit docker/newsletter/newsletter_poller.py:

   Find where the newsletter agent's JSON output is parsed (after the OpenAI call).
   The agent now returns:
   {
     "edition": N,
     "title": "...",
     "title_impact": "...",
     "content_markdown": "...",
     "content_markdown_impact": "...",
     "content_telegram": "..."
   }

   Update the code that saves to the newsletters table to also save:
   - title_impact from the agent's output
   - content_markdown_impact from the agent's output

   Handle gracefully if title_impact or content_markdown_impact are missing (older format):
   title_impact = output.get('title_impact', output.get('title', ''))
   content_markdown_impact = output.get('content_markdown_impact', '')

   Also save the impact version to a separate .md file in the workspace:
   If the current file is saved as f"edition_{edition}.md", save the impact version as
   f"edition_{edition}_impact.md" in the same directory.

2. If there's a Pydantic schema (NewsletterOutput or similar) that validates the agent's JSON,
   add the new optional fields:
   title_impact: Optional[str] = None
   content_markdown_impact: Optional[str] = None

3. Edit docker/processor/agentpulse_processor.py:

   Find get_latest_newsletter() or equivalent function that returns newsletter data.
   Make sure it includes content_markdown_impact and title_impact in the response.

   Find prepare_newsletter_data(). The budget for the newsletter task should be increased
   since the agent now writes two versions:
   Change max_llm_calls from 6 to 8 (or whatever the current value is, increase by ~30%).

   Find publish_newsletter(). No changes needed here — the impact content is already in the
   newsletters table from step 1.

4. Verify:
   grep "content_markdown_impact\|title_impact" docker/newsletter/newsletter_poller.py
   # Should find both fields

   grep "content_markdown_impact\|title_impact" docker/processor/agentpulse_processor.py
   # Should find in get_latest_newsletter

Don't modify identity files, skill files, web files, or docker-compose.yml.
```

---

## Prompt 8: Scheduling + Telegram Commands

```
Read these files first:
- docker/processor/agentpulse_processor.py (search for setup_scheduler, execute_task, and RSS_FEEDS)
- data/openclaw/workspace/AGENTS.md (or wherever Gato's command routing is defined)
- skills/agentpulse/SKILL.md

Wire up scheduling for the new financial sources and add subscriber management commands.

1. Edit docker/processor/agentpulse_processor.py:

   Add 'get_subscriber_stats' to execute_task():
   elif task_type == 'get_subscriber_stats':
       total = supabase.table('subscribers').select('id', count='exact').execute()
       active = supabase.table('subscribers').select('id', count='exact').eq('status', 'active').execute()
       pending = supabase.table('subscribers').select('id', count='exact').eq('status', 'pending').execute()

       # Mode preference breakdown
       builder_pref = supabase.table('subscribers').select('id', count='exact').eq('mode_preference', 'builder').eq('status', 'active').execute()
       impact_pref = supabase.table('subscribers').select('id', count='exact').eq('mode_preference', 'impact').eq('status', 'active').execute()
       both_pref = supabase.table('subscribers').select('id', count='exact').eq('mode_preference', 'both').eq('status', 'active').execute()

       return {
           'total': total.count or 0,
           'active': active.count or 0,
           'pending': pending.count or 0,
           'mode_breakdown': {
               'builder': builder_pref.count or 0,
               'impact': impact_pref.count or 0,
               'both': both_pref.count or 0
           }
       }

   Add 'get_subscriber_stats' to argparse choices.

2. Verify the scrape_rss_feeds schedule exists in setup_scheduler() (should be from Phase 5).
   The new financial feeds added in Prompt 4 are in RSS_FEEDS and will be picked up automatically
   by the existing scrape_rss_feeds() function — no scheduler changes needed for them.

3. Update data/openclaw/workspace/AGENTS.md (or wherever Gato's command definitions live):

   Add:
   /subscribers → write {"task":"get_subscriber_stats","params":{}} to the queue.
   Display subscriber stats:
   "📊 Subscribers: N total (N active, N pending)
    Mode: N ⚡ Builder | N 🌍 Impact | N Both"

4. Update skills/agentpulse/SKILL.md — add to the commands table:
   | /subscribers | Show subscriber count and mode preference breakdown |

5. Verify:
   grep "get_subscriber_stats" docker/processor/agentpulse_processor.py
   grep "subscribers" skills/agentpulse/SKILL.md
   grep "subscribers" data/openclaw/workspace/AGENTS.md

Don't modify web files, newsletter poller, or identity/skill templates.
```

---

## Deployment to Server

After all prompts pass locally:

```bash
# Commit and push
git add -A
git commit -m "Phase 6: dual-audience platform with builder/impact toggle"
git push

# On server
ssh root@46.224.50.251
cd ~/bitcoin_bot
git pull

# Run SQL migration (Prompt 1) in Supabase SQL Editor
# Also add the RLS policy for subscribers:
# CREATE POLICY "Allow public subscribe" ON subscribers FOR INSERT WITH CHECK (true);

# Deploy identity files
bash scripts/deploy-identities.sh

# Rebuild everything
cd docker
docker compose down
docker compose build --no-cache
docker compose up -d

# Wait and verify
sleep 15
docker compose ps

# Test web toggle
curl -s https://yourdomain.com | grep "toggle"

# Test subscriber stats
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task get_subscriber_stats

# Test newsletter with dual output
docker compose exec processor python3 /home/openclaw/agentpulse_processor.py --task prepare_newsletter
sleep 90
docker compose logs newsletter | tail -30

# Check newsletter has impact content
docker compose exec processor python3 -c "
from supabase import create_client
import os
c = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_KEY'))
nl = c.table('newsletters').select('edition_number, title, title_impact, content_markdown_impact').order('created_at', desc=True).limit(1).execute()
if nl.data:
    n = nl.data[0]
    print(f'Edition #{n[\"edition_number\"]}')
    print(f'Builder title: {n[\"title\"]}')
    print(f'Impact title: {n.get(\"title_impact\", \"MISSING\")}')
    print(f'Impact content: {\"YES\" if n.get(\"content_markdown_impact\") else \"MISSING\"} ({len(n.get(\"content_markdown_impact\", \"\"))} chars)')
"

# Test on Telegram
# /subscribers — should show stats
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Toggle doesn't switch content | app.js not loading both content fields | Check Supabase query selects content_markdown_impact |
| Toggle switches colors but not text | content_markdown_impact is null in DB | Newsletter hasn't been generated with new prompts yet |
| Subscribe form fails | RLS policy missing | Run: CREATE POLICY "Allow public subscribe" ON subscribers FOR INSERT WITH CHECK (true) |
| Newsletter output missing impact version | SKILL.md not updated or agent didn't follow new format | Check skills/newsletter/SKILL.md has content_markdown_impact in output JSON |
| New RSS feeds return 0 | Feed URLs may have changed or require auth | Test: python3 -c "import feedparser; print(feedparser.parse('URL').entries[:1])" |
| Financial keywords matching too broadly | Too many generic matches | Add minimum score threshold or tighten keyword list |
| /subscribers command not working | Not in execute_task or AGENTS.md | Check both files for get_subscriber_stats |
