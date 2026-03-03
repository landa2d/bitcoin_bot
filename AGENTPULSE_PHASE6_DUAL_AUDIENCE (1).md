# AgentPulse Phase 6: Dual-Audience Intelligence Platform

**Date:** March 2026
**Goal:** Transform AgentPulse from a builder-focused technical newsletter into a dual-audience intelligence platform that helps both technical and non-technical readers understand the AI economic transition.

---

## The Vision

The Citrini article describes a world where AI disrupts white-collar employment, consumer spending, mortgages, and private credit — and most people don't see it coming because the signals are buried in technical language.

AgentPulse is already monitoring the agent economy. The evolution is to make that intelligence accessible to two audiences:

1. **Builders** — the current audience. They want to know what to build, which tools are rising, where the opportunities are. Technical language, framework-level thinking, code-level signals.

2. **Everyone else** — professionals, investors, policymakers, displaced workers. They need to understand what's happening and what it means for their careers, portfolios, and decisions. No jargon, financial/human implications, plain language.

Same data. Same analysis. Two lenses.

---

## Part 1: The Toggle — Dual-Mode Web Archive

### Concept

The newsletter web archive gets a toggle switch: **Builder Mode** ↔ **Impact Mode**

- **Builder Mode** (current): Technical language, framework analysis, tool radar, code-level signals. Dark background, monospace accents, sharp editorial voice. This is the AgentPulse readers already know.

- **Impact Mode** (new): Same insights rewritten for non-technical readers. What does this mean for jobs? For investments? For the economy? Warm background, serif-heavy, more accessible voice. Every technical concept gets a human translation.

The toggle is a physical switch at the top of each article. When you flip it, the entire article transforms — content, color scheme, typography, tone. The URL stays the same but the experience changes.

### Design Language

**Builder Mode:**
- Background: `#0a0a0f` (near-black with blue undertone)
- Text: `#e0e0e8` (cool off-white)
- Accent: `#00d4aa` (electric teal)
- Font body: `IBM Plex Mono` or `JetBrains Mono` (monospace)
- Font headers: `Space Grotesk` or `Outfit` (geometric sans)
- Vibe: terminal, hacker, precise. Like reading a Bloomberg terminal that has opinions.

**Impact Mode:**
- Background: `#faf8f4` (warm cream)
- Text: `#1a1a1a` (near-black)
- Accent: `#c44b2b` (warm rust/terracotta)
- Font body: `Newsreader` or `Lora` (editorial serif)
- Font headers: `Fraunces` or `Playfair Display` (distinctive display serif)
- Vibe: Economist, FT weekend, editorial long-form. Like reading a quality Sunday paper.

### The Toggle Component

```
┌─────────────────────────────────────┐
│  ⚡ Builder    ○────●    🌍 Impact  │
└─────────────────────────────────────┘
```

- Smooth CSS transition between modes (300ms)
- Colors, fonts, and content all swap
- User preference saved in a cookie / localStorage so it persists
- URL gets a query param: `?mode=impact` or `?mode=builder` (shareable)
- Default for new visitors: Impact Mode (wider audience)

### Content Architecture

Each published newsletter has TWO content columns in the database:

```sql
ALTER TABLE newsletters ADD COLUMN IF NOT EXISTS content_markdown_impact TEXT;
```

- `content_markdown` — the existing builder version
- `content_markdown_impact` — the new impact version (generated from the same data)

The web archive loads both and shows whichever the toggle selects.

### How Impact Mode Content Gets Generated

Two options:

**Option A: Newsletter agent writes both versions (recommended)**
The Newsletter agent receives the same data package and writes two versions in one pass. The impact version isn't a "dumbed down" summary — it's a reframing:

- "Agent memory persistence" → "AI systems are learning to remember past conversations — and the companies racing to build this will determine how much context AI has about your life"
- "MCP adoption growing" → "A new standard for connecting AI agents to your tools is gaining traction — this could become the USB-C of AI, or fragment into competing standards"
- "SaaS pricing compression" → "Companies that charge per-user for software are seeing their business models collapse as AI lets one person do the work of ten"

**Option B: Separate translation pass**
A second LLM call that takes the builder version and rewrites it. Cheaper but risks losing nuance.

Go with Option A. The agent already understands the data deeply — asking it to write two versions while the data is fresh in context produces better results than a cold rewrite.

### Updated Newsletter Agent Output

```json
{
  "edition": 12,
  "title": "The Memory Wars Begin",
  "title_impact": "AI Is Learning to Remember You — Here's What That Means",
  "content_markdown": "... builder version ...",
  "content_markdown_impact": "... impact version ...",
  "content_telegram": "..."
}
```

---

## Part 2: Financial Coverage Expansion

### Why

The Citrini article shows that the agent economy isn't just a tech story — it's a financial story. SaaS repricing, interchange compression, private credit defaults, mortgage stress. AgentPulse should be the place where these connections are made explicit.

### New Data Sources

Add to the RSS feed scraper:

```python
# Financial / macro sources
'matt_levine': {
    'url': 'https://www.bloomberg.com/opinion/authors/ARbTQlRLRjE/matthew-s-levine',  # If RSS available
    'tier': 1,
    'category': 'financial_analysis'
},
'stratechery': {
    'url': 'https://stratechery.com/feed/',
    'tier': 1,
    'category': 'business_analysis'
},
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
'cb_insights': {
    'url': 'https://www.cbinsights.com/research/feed/',
    'tier': 2,
    'category': 'market_research'
},
```

### New Relevance Keywords

```python
FINANCIAL_KEYWORDS = [
    'saas pricing', 'seat based', 'arr', 'net revenue retention',
    'white collar', 'displacement', 'layoff', 'headcount reduction',
    'interchange', 'stablecoin', 'payment rail', 'agent commerce',
    'private credit', 'lbo', 'software default',
    'mortgage', 'delinquency', 'consumer spending',
    'ghost gdp', 'labor share', 'wage compression',
    'ai disruption', 'business model', 'intermediation',
    'regulatory', 'ai act', 'compute tax',
]
```

### New Newsletter Sections (Impact Mode Only)

**The Economic Signal** — a section that only appears in Impact Mode:
- What's happening in the real economy because of AI agent adoption
- Job market shifts, spending patterns, business model disruptions
- Connects the technical signals from Builder Mode to financial/career implications

**Career Radar** — Impact Mode only:
- Which roles are being automated (based on tool trends and agent capabilities)
- Which skills are gaining value (based on what agents can't do yet)
- Where displaced professionals are landing (based on job market signals)

### Analyst Identity Update

Add financial analysis capability:

```markdown
## Financial Transmission Analysis

When analyzing agent economy signals, always consider the financial transmission:

1. How does this signal affect business models? (pricing pressure, margin compression, revenue decay)
2. How does this affect employment? (which roles does this automate or create?)
3. How does this affect consumer behavior? (friction removal, spending shifts, intermediation bypass)
4. How does this connect to larger systemic risks? (credit markets, housing, government revenue)

Framework: Follow the money. Every technical shift creates winners and losers.
The winners buy compute. The losers stop spending. Both effects cascade.
```

---

## Part 3: Impact Mode Newsletter Voice

### Identity Addition for Impact Mode

```markdown
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
- Kara Swisher's ability to explain tech to a business audience
- The Economist's ability to make complex topics accessible without condescension
- Morgan Housel's ability to connect financial concepts to human behavior

Example translations:

Builder: "Three new agent memory frameworks launched this week. Star velocity
suggests market is in 'building' phase. Consolidation expected by Q3."

Impact: "AI systems are racing to develop permanent memory — the ability to
remember your preferences, past conversations, and habits across sessions.
Three new approaches launched this week, and the pace suggests we'll see
a dominant approach emerge by summer. For consumers, this means AI assistants
that actually know you. For workers, it means AI that learns your job by watching
you do it — then doesn't need you anymore."
```

---

## Part 4: Web Archive Redesign

### Architecture Change

The current static SPA (index.html + app.js) needs to become more sophisticated
to handle the toggle. Still no build step, but more JavaScript.

```
docker/web/site/
├── index.html          # Updated with toggle UI
├── style-builder.css   # Builder mode styles
├── style-impact.css    # Impact mode styles
├── style-shared.css    # Shared layout, toggle component, transitions
├── app.js              # Updated: loads correct content per mode
└── toggle.js           # Toggle state management + transitions
```

### How the Toggle Works

```javascript
// toggle.js

const MODES = {
  builder: {
    stylesheet: 'style-builder.css',
    contentField: 'content_markdown',
    titleField: 'title',
    label: 'Builder',
    icon: '⚡'
  },
  impact: {
    stylesheet: 'style-impact.css',
    contentField: 'content_markdown_impact',
    titleField: 'title_impact',
    label: 'Impact',
    icon: '🌍'
  }
};

let currentMode = localStorage.getItem('agentpulse_mode') || 'impact';

function setMode(mode) {
  currentMode = mode;
  localStorage.setItem('agentpulse_mode', mode);

  // Update URL without reload
  const url = new URL(window.location);
  url.searchParams.set('mode', mode);
  history.replaceState({}, '', url);

  // Swap stylesheet
  document.getElementById('mode-stylesheet').href = MODES[mode].stylesheet;

  // Swap content (if article is loaded)
  if (window.currentNewsletter) {
    renderArticle(window.currentNewsletter, mode);
  }

  // Update toggle UI
  document.querySelector('.toggle-track').classList.toggle('impact', mode === 'impact');
  document.querySelector('.toggle-track').classList.toggle('builder', mode === 'builder');

  // Add transition class
  document.body.classList.add('mode-transitioning');
  setTimeout(() => document.body.classList.remove('mode-transitioning'), 400);
}

// Check URL param on load
const urlMode = new URL(window.location).searchParams.get('mode');
if (urlMode && MODES[urlMode]) {
  currentMode = urlMode;
}
```

### Toggle HTML Component

```html
<div class="mode-toggle" role="switch" aria-label="Toggle reading mode">
  <span class="toggle-label builder-label">⚡ Builder</span>
  <div class="toggle-track" onclick="setMode(currentMode === 'builder' ? 'impact' : 'builder')">
    <div class="toggle-thumb"></div>
  </div>
  <span class="toggle-label impact-label">🌍 Impact</span>
</div>
```

### Toggle CSS

```css
/* style-shared.css */

.mode-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: center;
  padding: 20px 0;
  user-select: none;
}

.toggle-track {
  width: 56px;
  height: 28px;
  border-radius: 14px;
  cursor: pointer;
  position: relative;
  transition: background-color 0.3s ease;
}

.toggle-track.builder {
  background-color: #00d4aa;
}

.toggle-track.impact {
  background-color: #c44b2b;
}

.toggle-thumb {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: white;
  position: absolute;
  top: 2px;
  transition: left 0.3s ease;
}

.toggle-track.builder .toggle-thumb {
  left: 2px;
}

.toggle-track.impact .toggle-thumb {
  left: 30px;
}

/* Transition between modes */
.mode-transitioning * {
  transition: color 0.3s ease, background-color 0.3s ease !important;
}

.toggle-label {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  opacity: 0.5;
  transition: opacity 0.3s ease;
}

.toggle-track.builder ~ .builder-label,
.builder-label:has(~ .toggle-track.builder) { opacity: 1; }

.toggle-track.impact ~ .impact-label { opacity: 1; }
```

---

## Part 5: Subscribe + Email Flow

While building the dual-mode site, add the email subscription flow:

### Subscribe Form (on web archive)

```html
<section id="subscribe-section">
  <h2>Get the Intelligence Brief</h2>
  <p>Weekly analysis of the AI agent economy. Choose your lens.</p>
  <div class="subscribe-form">
    <input type="email" id="subscribe-email" placeholder="you@example.com" />
    <div class="mode-preference">
      <label><input type="radio" name="pref" value="builder" /> ⚡ Builder</label>
      <label><input type="radio" name="pref" value="impact" checked /> 🌍 Impact</label>
      <label><input type="radio" name="pref" value="both" /> Both</label>
    </div>
    <button onclick="subscribe()">Subscribe</button>
  </div>
</section>
```

Subscribers choose which version they want. "Both" sends a single email with a toggle link at the top pointing to the web version.

### Database

```sql
CREATE TABLE subscribers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    mode_preference TEXT DEFAULT 'impact',  -- 'builder', 'impact', 'both'
    status TEXT DEFAULT 'pending',          -- 'pending', 'active', 'unsubscribed'
    confirmation_token TEXT,
    confirmed_at TIMESTAMPTZ,
    unsubscribed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

CREATE TABLE email_deliveries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    subscriber_id UUID REFERENCES subscribers(id),
    newsletter_id UUID REFERENCES newsletters(id),
    mode_sent TEXT,                          -- which version was sent
    status TEXT DEFAULT 'queued',            -- 'queued', 'sent', 'delivered', 'opened', 'bounced'
    sent_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,
    metadata JSONB
);
```

---

## Part 6: Newsletter Agent Changes

### Updated SKILL.md Addition

```markdown
## Task: write_newsletter (updated)

Your output now includes TWO versions of the newsletter:

### Builder Version (content_markdown)
The existing technical newsletter. No changes to voice or structure.

### Impact Version (content_markdown_impact)
Same data, different lens. For every section, translate implications:

Structure mirrors Builder but with these changes:
- Cold open: Lead with the human/economic impact, not the technical signal
- The Big Insight: Frame thesis in terms of jobs, money, or power — not tools
- Top Opportunities: Reframe as "Where the market is shifting" — what industries,
  jobs, or business models are being created/destroyed
- Emerging Signals: What should non-technical professionals watch for?
- The Economic Signal (Impact only): Connect this week's agent economy data to
  broader economic implications
- Career Radar (Impact only): What this week's signals mean for employment
- Tool Radar: Skip in Impact Mode — replace with "What's Changing" using plain language
- Prediction Tracker: Same format but add human-impact context
- Gato's Corner: Same in both versions (Gato is Gato)

### Output JSON (updated)
{
  "edition": N,
  "title": "Builder-focused headline",
  "title_impact": "Impact-focused headline — what it means for everyone",
  "content_markdown": "... builder version ...",
  "content_markdown_impact": "... impact version ...",
  "content_telegram": "..."
}
```

### Updated IDENTITY.md Addition

Add the Impact Mode Voice section from Part 3 above.

### Word Count Adjustment

With two versions, the total output is ~2x. Budget accordingly:
- Builder version: 800-1200 words (unchanged)
- Impact version: 600-1000 words (slightly shorter — clarity over completeness)
- Total output: ~1800-2200 words per newsletter

Consider increasing the newsletter agent's max_tokens to 20000 and budget to
max_llm_calls: 8 to accommodate the longer output.

---

## Implementation Sequence

```
Prompt 1:  Database changes (content_markdown_impact column, subscribers, email_deliveries)
Prompt 2:  Web archive redesign — dual CSS files, toggle component, mode-aware rendering
Prompt 3:  Newsletter agent update — write both versions, updated SKILL.md and IDENTITY.md
Prompt 4:  Financial source expansion (new RSS feeds + financial keywords)
Prompt 5:  Analyst identity update (financial transmission analysis)
Prompt 6:  Subscribe form + Supabase integration (double opt-in flow)
Prompt 7:  Email delivery (Resend API integration)
Prompt 8:  Scheduling + Telegram commands (/mode, /subscribers)
```

### Parallel Execution

```
Round 1: Prompt 1 (SQL) — alone

Round 2 (parallel):
  Agent A: Prompt 2 (web redesign — pure frontend, no Python)
  Agent B: Prompt 3 (newsletter agent — identity + skill files)
  Agent C: Prompt 4 (RSS feeds — processor Python)

Round 3 (parallel):
  Agent A: Prompt 5 (analyst identity — file only)
  Agent B: Prompt 6 (subscribe form — frontend + Supabase)

Round 4 (sequential):
  Prompt 7 (email delivery — needs subscribers table from Prompt 1)
  Prompt 8 (scheduling + commands — needs everything else)
```

---

## Success Metrics

After 4 editions with dual mode:
- What % of web visitors use Impact vs Builder mode?
- Do Impact readers share more? (track referral sources)
- Do subscribers prefer one mode? (track mode_preference distribution)
- Does the Impact version attract a different audience? (monitor subscriber growth)

If Impact Mode attracts significantly more readers, consider making it the default
and offering Builder Mode as the "deep dive" for technical subscribers. This inverts
the current product — the accessible version becomes the product, the technical
version becomes the premium feature.
