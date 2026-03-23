#!/usr/bin/env python3
"""Generate a test newsletter using DeepSeek API with latest Supabase data."""
import json, os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv("config/.env")

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL")
)

def _load_file(path: str) -> str:
    """Load a text file, return empty string if missing."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""

# Load the canonical IDENTITY.md and SKILL.md so the LLM gets the full structure
_identity = _load_file("data/openclaw/agents/newsletter/agent/IDENTITY.md")
_skill = _load_file("skills/newsletter/SKILL.md")

if _identity:
    system_prompt = f"{_identity}\n\n---\n\nSKILL REFERENCE:\n{_skill}"
else:
    # Fallback: if IDENTITY.md is missing, use inline prompt
    system_prompt = """You are Pulse, the editorial voice of AgentPulse. You write the weekly Intelligence Brief.

VOICE: Sharp, specific, structurally analytical, with practical builder takeaways. Write like the bastard child of Benedict Evans, Lenny Rachitsky, Eric Newcomer, Ben Thompson, and Om Malik. Reporter, not summarizer. Every sentence earns its place.

FILLER BLACKLIST (delete on sight): "navigating without a map", "wake-up call", "smart businesses are already", "the landscape is shifting", "builders should leverage", "as we move forward", "the evidence suggests", "in today's rapidly evolving", "it remains to be seen", "only time will tell".

STRUCTURE (sections marked conditional can be skipped if data is weak):
1. Cold open (no header) - 1-3 sentences, hook not summary
2. One Number (conditional) - **Number** - one sentence
3. Spotlight (conditional, only if spotlight data present):

## Spotlight: [Conviction-Laden Title]
**Thesis: [One-line — opinionated, specific, falsifiable. NOT a summary.]**

[Body — 3-5 paragraphs max. Lead with the strongest specific data point. Name specific companies, projects, protocols, or people. Never write "the industry" or "stakeholders" without naming who.]

### Builder Lens
[1-2 paragraphs. What this means technically — code-level, architecture-level, tooling implications. Speak to engineers.]

### Impact Lens
[1-2 paragraphs. What this means strategically — business model, investment, competitive positioning. Speak to decision-makers.]

### Prediction Scorecard Entry
- **Prediction**: [Specific, falsifiable claim]
- **Timeline**: [Concrete date or quarter]
- **Metric**: [How we'll measure if this was right or wrong]
- **Confidence**: [High / Medium / Low]

4. ## [Thesis headline] (The Big Insight) - DIFFERENT angle from Spotlight
5. ## Top Opportunities - 3-5 items
6. ## Emerging Signals - 2-4 items, all new
7. ## On Our Radar (conditional, need 3+ topics)
8. ## The Curious Corner (conditional)
9. ## Tool Radar
10. ## Prediction Tracker - use status icons
11. ## Gato's Corner - Bitcoin maximalist voice, ends with "Stay humble, stack sats."

ANTI-REPETITION: One Number stat appears ONCE. Spotlight and Big Insight must be distinct angles.
JARGON: Ground technical terms on first use.

KILL RULES — If your draft contains ANY of these, rewrite before outputting:
1. "In conclusion" or "In sum" → Cut entirely. The prediction IS the conclusion.
2. "Stakeholders" / "the industry" / "professionals and enterprises" without naming specific entities → Replace with names.
3. "Demands urgent attention" / "teaching moments" / "unique opportunities" → Delete. State the specific consequence instead.
4. Any paragraph that could appear in a generic crypto newsletter without modification → Rewrite with AgentPulse's unique data or angle.
5. Bold inline headers like "**Opportunity for Recovery**" or "**Call to Action**" → These are NOT section headers. Use proper markdown ## or ### headers.
6. A section with zero named companies, projects, or people → Add specifics or cut the section.

PREDICTIONS: Every prediction needs "By [specific date], [specific measurable outcome]." Past-due ones MUST be resolved (confirmed/wrong/revised). No past-due predictions shown as Active.

OUTPUT: Valid JSON with keys: edition, title, content_markdown, content_telegram, primary_theme"""

system_prompt += (
    "\n\nYou MUST respond with valid JSON only — no markdown fences, no extra text."
)

input_data = {
    "edition_number": 38,
    "date": "2026-03-19",
    "avoided_themes": [
        "crypto talent exodus to AI (covered in Brief 37)",
        "agent spend concentration / power law (covered in Brief 37)",
        "AI identity management growth (covered in Brief 36)"
    ],
    "stats": {
        "total_posts": 27142,
        "total_source_posts": 3297,
        "total_problems": 214,
        "total_opportunities": 43,
        "total_embeddings": 4440,
        "llm_calls_since_last_edition": 380
    },
    "spotlight": {
        "topic_name": "The Agent Tooling Cambrian Explosion Meets Bitcoin's Regulatory Clarity Moment",
        "mode": "synthesis",
        "thesis": "The SEC/CFTC joint classification framework and stablecoin bill momentum are arriving at the exact moment agent-native financial primitives (Baud, on-chain escrow, tokenized deposits) are proliferating — creating a narrow window where crypto-native agent infrastructure could become the default payment rail for autonomous economies, or miss the window entirely if TradFi rails move faster.",
        "evidence": "Three converging signals this week. First, the SEC and CFTC issued joint guidance dividing crypto tokens into five categories, while Senate Banking Committee chair Tim Scott expects a stablecoin yield compromise 'this week' — the first time both regulators and legislators have moved simultaneously on crypto clarity. Bitcoin sits at $72-75K with implied volatility remarkably stable despite the Iran conflict, suggesting the market has priced in regulatory tailwinds. Second, agent-native payment infrastructure is materializing: Baud — a feeless ledger with hash-locked escrow, milestone payments, spending policies, and agent identity registry — appeared in Moltbook discussions with detailed primitive designs. VersaBank launched real-time tokenized deposit FX conversion. Moody's put credit ratings onchain via Canton Network. Third, the GitHub signal is unmistakable: this week alone saw ClawmarketAI (autonomous agent marketplace), CORAL (multi-agent evolution), ouro-loop (autonomous agent guardrails), nulla-hive-mind (decentralized agent swarms), and Plamen (Web3 security audit agent, 97 stars). HuggingFace launched hf-agents (232 stars in 3 days) — local coding agents going mainstream.",
        "counter_argument": "The strongest counter: regulatory clarity historically triggers a 'sell the news' event, not an infrastructure buildout. The 2024 Bitcoin ETF approval saw prices crater within weeks. More fundamentally, agent payment rails don't need crypto — Stripe, PayPal, and traditional APIs handle micropayments at scale without the complexity overhead. Baud's feeless model sounds elegant but has zero production deployments. The GitHub repos are mostly weekend projects with single-digit stars. Real enterprise agent infrastructure will use fiat rails with crypto as an optional settlement layer, not the base.",
        "prediction": "By September 2026, at least two agent framework providers (from the top 10 by GitHub stars) will ship native integrations with crypto payment rails (stablecoin or Lightning) for agent-to-agent transactions, driven by the regulatory clarity window opening now.",
        "builder_implications": "If you're building agent infrastructure, the regulatory clarity means you can now design payment flows without the ambiguity tax. Implement Baud-style primitives: hash-locked escrow for task completion, milestone payments for multi-step workflows, and spending caps for bounded autonomy. The key architectural decision is whether to build on stablecoins (regulatory clarity arriving) or Lightning (already works but limited smart contract capability). Hedge by abstracting the settlement layer. Don't wait for perfect regulation — the window for establishing agent payment standards is 6-12 months before TradFi incumbents ship their own.",
        "sources_used": [
            {"url": "https://www.coindesk.com/markets/2026/03/18/bitcoin-s-progress-above-usd75-000-elusive-after-sec-cftc-crypto-guidance"},
            {"url": "https://cointelegraph.com/news/tim-scott-expects-crypto-bill-stablecoin-yield-proposal-this-week"},
            {"url": "https://github.com/BocchiDaruko/ClawmarketAI"},
            {"url": "https://github.com/huggingface/hf-agents"},
            {"url": "https://github.com/PlamenTSV/plamen"}
        ]
    },
    "section_a_opportunities": [
        {
            "title": "Agent Payment Rails Platform",
            "description": "Unified payment infrastructure for agent-to-agent transactions using stablecoin or Lightning settlement with escrow, milestones, and spending policies",
            "confidence_score": 0.88,
            "effective_score": 0.82,
            "is_returning": False,
            "appearances": 0,
            "why_now": "SEC/CFTC classification + stablecoin bill movement removes regulatory ambiguity; Baud primitives demonstrate demand for agent-native financial infrastructure"
        },
        {
            "title": "Autonomous Agent Marketplace Infrastructure",
            "description": "Platform enabling AI agents to autonomously create, price, buy and sell services/data without human intervention",
            "confidence_score": 0.80,
            "effective_score": 0.75,
            "is_returning": False,
            "appearances": 0,
            "why_now": "ClawmarketAI, CORAL, and nulla-hive-mind all launched this week — early signal of demand for agent commerce primitives"
        },
        {
            "title": "Web3 Security Audit Agent",
            "description": "Autonomous smart contract auditing powered by AI agents, reducing cost and time of security reviews",
            "confidence_score": 0.85,
            "effective_score": 0.78,
            "is_returning": False,
            "appearances": 0,
            "why_now": "Plamen (97 stars in 3 days) proves demand; regulatory clarity makes smart contract deployment more attractive, increasing audit demand"
        },
        {
            "title": "Agent Guardrail & Governance Framework",
            "description": "Structured autonomous loops with verification gates, self-reflection layers, and bounded autonomy for production agent deployments",
            "confidence_score": 0.76,
            "effective_score": 0.72,
            "is_returning": False,
            "appearances": 0,
            "why_now": "ouro-loop's 'zero dependencies' approach and Baud's spending policies show convergent demand for agent safety primitives"
        }
    ],
    "section_b_emerging": [
        {
            "description": "Stablecoins face regulatory tax threats that hinder adoption in business and agentic finance despite new SEC/CFTC clarity.",
            "category": "payments",
            "frequency_count": 1,
            "first_seen": "2026-03-15",
            "source": "moltbook",
            "severity": "high"
        },
        {
            "description": "Bitcoin infrastructure concentrated in small number of hosting providers creates systemic vulnerability despite network resilience.",
            "category": "infrastructure",
            "frequency_count": 1,
            "first_seen": "2026-03-14",
            "source": "moltbook",
            "severity": "high"
        },
        {
            "description": "OpenAI prioritizing engagement metrics over accuracy (sycophantic ChatGPT) as IPO approaches — trust erosion in commercial AI.",
            "category": "trust",
            "frequency_count": 1,
            "first_seen": "2026-03-17",
            "source": "hackernews",
            "severity": "medium"
        },
        {
            "description": "Resource consumption attacks on LLMs — adversarial inputs that induce excessive generation, degrading efficiency and increasing costs.",
            "category": "security",
            "frequency_count": 1,
            "first_seen": "2026-03-17",
            "source": "arxiv",
            "severity": "high"
        }
    ],
    "predictions": [
        {
            "text": "By April 2026, at least three major agent platforms will implement session-based memory wipe features as default behavior after enterprise security incidents.",
            "status": "open",
            "target_date": "2026-04-30",
            "is_approaching": True
        },
        {
            "text": "By April 2026, at least one major cloud provider will announce an Agent Runtime Service abstracting identity, communication, and resource management.",
            "status": "open",
            "target_date": "2026-04-30",
            "is_approaching": True
        },
        {
            "text": "At least three major agent platforms will implement persistent identity layers with cryptographic continuity verification by April 2026.",
            "status": "open",
            "target_date": "2026-04-30",
            "is_approaching": True
        },
        {
            "text": "At least three major agent framework providers will announce competing 'agent discovery protocols' by April 2026.",
            "status": "open",
            "target_date": "2026-04-30",
            "is_approaching": True
        },
        {
            "text": "At least two major framework vendors will ship MCP-compatible APIs by Q2 2026.",
            "status": "open",
            "target_date": "2026-06-30"
        },
        {
            "text": "At least three major crypto protocols will announce AI-native development initiatives or hybrid AI-crypto engineering roles as a direct talent retention strategy by Q3 2026.",
            "status": "open",
            "target_date": "2026-09-30",
            "is_new": True
        }
    ],
    "stale_prediction_ids": [],
    "approaching_predictions_note": "Four predictions target April 2026 — just 6 weeks away. Track evidence carefully this edition.",
    "trending_tools": [
        {
            "tool_name": "Baud",
            "context": "Feeless ledger for agent economies: hash-locked escrow, milestone payments, spending policies, agent identity registry. Detailed primitive designs appeared on Moltbook.",
            "sentiment": "positive",
            "is_recommendation": False
        },
        {
            "tool_name": "hf-agents (HuggingFace)",
            "context": "HF CLI extension to run local coding agents via llmfit and llama.cpp. 232 stars in 3 days.",
            "sentiment": "positive",
            "is_recommendation": True
        },
        {
            "tool_name": "Plamen",
            "context": "Autonomous Web3 security audit agent for Claude Code. 97 stars, 18 forks in 3 days.",
            "sentiment": "positive",
            "is_recommendation": True
        },
        {
            "tool_name": "ouro-loop",
            "context": "Structured autonomous loop with 5 verification gates and 3-layer self-reflection for Claude Code, Cursor, Aider. Zero dependencies.",
            "sentiment": "positive",
            "is_recommendation": True
        },
        {
            "tool_name": "Cloudflare",
            "context": "Partial outage caused silent cron job failures for 47 minutes — visibility gap for agent infrastructure.",
            "sentiment": "negative",
            "is_complaint": True
        },
        {
            "tool_name": "ERC-8170",
            "context": "Draft Ethereum standard for AI-native NFTs with on-chain memory, lifecycle, and identity.",
            "sentiment": "positive",
            "is_recommendation": False
        }
    ],
    "tool_warnings": [
        {
            "tool_name": "Cloudflare",
            "sentiment_score": -0.3,
            "reason": "Silent cron failures during partial outage highlight infrastructure fragility for always-on agent deployments"
        }
    ],
    "topic_evolution": [
        {"topic_key": "regulatory_&_adoption_barriers", "current_stage": "emerging", "latest_sentiment": 0.0, "github_repos": 0, "source_count": 6},
        {"topic_key": "infrastructure_&_security_vulnerabilities", "current_stage": "emerging", "latest_sentiment": 0.0, "github_repos": 7, "source_count": 11},
        {"topic_key": "ecosystem_talent_&_development_drain", "current_stage": "emerging", "latest_sentiment": 0.0, "github_repos": 12, "source_count": 9},
        {"topic_key": "infrastructure_security_management", "current_stage": "consolidating", "latest_sentiment": 0.0, "github_repos": 10, "source_count": 12},
        {"topic_key": "web3_blockchain_complexity", "current_stage": "consolidating", "latest_sentiment": 0.0, "github_repos": 1, "source_count": 8},
        {"topic_key": "infrastructure_scalability", "current_stage": "building", "latest_sentiment": 0.0, "github_repos": 1, "source_count": 8},
        {"topic_key": "payment_systems_economic_models", "current_stage": "declining", "latest_sentiment": 0.4, "github_repos": 3, "source_count": 11},
        {"topic_key": "security_trust_ai_systems", "current_stage": "declining", "latest_sentiment": 0.0, "github_repos": 9, "source_count": 9}
    ],
    "clusters": [
        {"theme": "Regulatory & Adoption Barriers", "description": "Stablecoin tax threats + SEC/CFTC classification creating simultaneous headwind and tailwind for crypto adoption.", "opportunity_score": 0.77, "problem_count": 1},
        {"theme": "Infrastructure & Security Vulnerabilities", "description": "Bitcoin hosting provider concentration risk + LLM resource consumption attacks.", "opportunity_score": 0.77, "problem_count": 1},
        {"theme": "Ecosystem Talent & Development Drain", "description": "Developer migration from crypto to AI continues but regulatory clarity may stem the flow.", "opportunity_score": 0.77, "problem_count": 1},
        {"theme": "Infrastructure and Security Management", "description": "Agent config/documentation gaps + Cloudflare outage visibility issues.", "opportunity_score": 0.76, "problem_count": 1},
        {"theme": "Agent Autonomy and Behavior", "description": "Agents on inherited patterns lack true autonomy, risk echo chambers. OpenAI sycophancy compounds the problem.", "opportunity_score": 0.61, "problem_count": 2}
    ],
    "analyst_insights": {
        "key_findings": [
            {
                "finding": "SEC/CFTC joint crypto classification + stablecoin bill momentum create first real regulatory clarity window for agent-native financial infrastructure.",
                "significance": "high"
            },
            {
                "finding": "GitHub agent tooling explosion (20+ new repos this week with agent-native commerce, security, and governance) signals Cambrian explosion phase — most will die but patterns are crystallizing.",
                "significance": "high"
            },
            {
                "finding": "Bitcoin implied volatility decoupling from traditional markets (VIX, OVX, MOVE all spiking while BTC vol stays flat) suggests crypto is developing independent risk pricing for the first time.",
                "significance": "medium"
            }
        ],
        "analyst_notes": "Four predictions approaching April 2026 deadline — next 2 editions must track evidence aggressively. Analyst agent deficit deepened to -130,318 sats."
    },
    "agent_economy_data": {
        "analyst_balance_sats": -130318,
        "analyst_total_spent": 180318,
        "processor_balance_sats": 99876,
        "newsletter_balance_sats": 49980,
        "gato_balance_sats": 100000,
        "research_balance_sats": 50000,
        "total_llm_calls": 246473,
        "calls_since_last_edition": 380
    },
    "freshness_rules": {
        "excluded_opportunity_ids": [],
        "max_returning": 1,
        "min_new": 3
    }
}

user_prompt = f"""TODAY'S DATE: 2026-03-19
TASK: write_newsletter
EDITION: 38

INPUT DATA:
{json.dumps(input_data, indent=2)}

Write the Intelligence Brief. Return valid JSON."""

print("Calling DeepSeek API...")
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    max_tokens=8000,
    temperature=0.7,
    response_format={"type": "json_object"}
)

result = response.choices[0].message.content
print("API response received.")

# Parse and save
data = json.loads(result)
os.makedirs("newsletters", exist_ok=True)

md_content = data.get("content_markdown", result)
with open("newsletters/brief_38_2026-03-19.md", "w", encoding="utf-8") as f:
    f.write(md_content)

print(f"\nTitle: {data.get('title')}")
print(f"Theme: {data.get('primary_theme')}")
print(f"Telegram: {data.get('content_telegram')}")
print(f"\nSaved to newsletters/brief_38_2026-03-19.md")
print(f"\n{'='*60}")
print("FULL NEWSLETTER:")
print('='*60)
print(md_content)
