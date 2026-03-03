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

system_prompt = """You are Pulse, the editorial voice of AgentPulse. You write the weekly Intelligence Brief.

VOICE: Sharp, specific, structurally analytical, with practical builder takeaways. Write like the bastard child of Benedict Evans, Lenny Rachitsky, Eric Newcomer, Ben Thompson, and Om Malik. Reporter, not summarizer. Every sentence earns its place.

FILLER BLACKLIST (delete on sight): "navigating without a map", "wake-up call", "smart businesses are already", "the landscape is shifting", "builders should leverage", "as we move forward", "the evidence suggests", "in today's rapidly evolving", "it remains to be seen", "only time will tell".

STRUCTURE (sections marked conditional can be skipped if data is weak):
1. Cold open (no header) - 1-3 sentences, hook not summary
2. One Number (conditional) - **Number** - one sentence
3. ## Spotlight (conditional, only if spotlight data present) - 400-500 words, 5 paragraphs: bold thesis, scene-setting, counter-argument, our take + prediction, builder implications
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
KILL RULES: Delete sections with nothing specific. Don't pad.
PREDICTIONS: Every prediction needs "By [specific date], [specific measurable outcome]." Past-due ones MUST be resolved (confirmed/wrong/revised). No past-due predictions shown as Active.

OUTPUT: Valid JSON with keys: edition, title, content_markdown, content_telegram, primary_theme"""

input_data = {
    "edition_number": 36,
    "date": "2026-03-03",
    "avoided_themes": [
        "AI identity management growth",
        "content quality vs. engagement metrics",
        "data privacy compliance"
    ],
    "stats": {
        "total_posts": 17528,
        "total_problems": 211,
        "total_opportunities": 43
    },
    "spotlight": {
        "topic_name": "The Agent Complexity Trap",
        "mode": "synthesis",
        "thesis": "AI agents are hitting the same complexity ceiling that crippled early web3 adoption - but unlike blockchain's theoretical benefits, agent complexity delivers immediate value, creating a harder design problem to solve.",
        "evidence": "The signal is emerging across three fronts. First, MCP's token economics are breaking down in practice - developers are discovering that comprehensive tool descriptions bloat context windows so severely that cost per interaction becomes prohibitive, forcing 'all or nothing' tool loading that defeats the protocol's modular promise. Second, the planning-execution separation pattern is gaining traction not because it's architecturally superior, but because it creates 'debugging surfaces for invisible assumptions' - essentially admitting that agent reasoning is too opaque to trust without intermediate verification. Third, open-source agent operating systems like OpenFang are proliferating (2,710 GitHub stars in days), but their creators are publicly abandoning their own tools because the cognitive overhead of configuring and maintaining agent workflows exceeds the productivity gains.",
        "counter_argument": "The strongest argument against this is that agent complexity is a temporary scaling problem, not a fundamental ceiling. Web3's complexity stemmed from theoretical constructs with unclear value propositions. Agent complexity, by contrast, emerges from genuine capability: MCP bloats context because it's exposing real tool functionality; planning-execution separation exists because agents are actually reasoning through complex problems. The complexity tax decreases as abstractions mature.",
        "prediction": "By June 2026, at least two major agent framework companies will announce 'simplified deployment' products that abstract away 80% of current configuration complexity, triggering the first wave of mainstream enterprise adoption.",
        "builder_implications": "Don't optimize for technical sophistication - optimize for time-to-value. The agent builders winning will be those who deliver 80% of the capability with 20% of the setup complexity. Focus on opinionated defaults, progressive disclosure of advanced features, and measuring success by user productivity gains rather than technical benchmarks.",
        "sources_used": [
            {"url": "https://kanyilmaz.me/2026/02/23/cli-vs-mcp.html"},
            {"url": "https://boristane.com/blog/how-i-use-claude-code/"},
            {"url": "https://github.com/generalaction/emdash"}
        ]
    },
    "section_a_opportunities": [
        {
            "title": "TrustGuard for DeFi",
            "description": "Non-custodial protocol for DeFi tool interaction without wallet access",
            "confidence_score": 0.9,
            "effective_score": 0.63,
            "is_returning": True,
            "appearances": 1,
            "why_now": "Growing DeFi sector and recent security breaches highlight urgent need"
        },
        {
            "title": "ChainTrust: Native On-Chain Escrow for Agent Economies",
            "description": "Native on-chain escrow with programmatic verification for trustless agent transactions",
            "confidence_score": 0.9,
            "effective_score": 0.63,
            "is_returning": False,
            "appearances": 0,
            "why_now": "Agent economies creating structural trust problems that need native solutions"
        },
        {
            "title": "Agent Infrastructure Security Platform",
            "description": "Robust configuration management and documentation for AI agents to prevent unauthorized access",
            "confidence_score": 0.76,
            "effective_score": 0.76,
            "is_returning": False,
            "appearances": 0
        },
        {
            "title": "Agent Coordination Middleware",
            "description": "Tools for AI agents to coordinate in large groups without chaos",
            "confidence_score": 0.61,
            "effective_score": 0.61,
            "is_returning": False,
            "appearances": 0
        }
    ],
    "section_b_emerging": [
        {
            "description": "AI agents cannot accept payments directly, limiting their revenue generation capabilities.",
            "category": "payments",
            "frequency_count": 1,
            "first_seen": "2026-02-19",
            "source": "moltbook",
            "severity": "high"
        },
        {
            "description": "No secure mechanism for managing cryptographic keys for AI agents.",
            "category": "security",
            "frequency_count": 1,
            "first_seen": "2026-02-19",
            "source": "moltbook",
            "severity": "high"
        },
        {
            "description": "Agents running on inherited response patterns lack true autonomy - behavior is preset, not learned.",
            "category": "identity",
            "frequency_count": 1,
            "first_seen": "2026-02-20",
            "source": "moltbook",
            "severity": "high"
        }
    ],
    "predictions": [
        {
            "text": "By April 2025, at least two major agent framework companies will announce simplified deployment products.",
            "status": "open",
            "target_date": "2025-04-30",
            "is_stale": True
        },
        {
            "text": "At least three major AI platforms will launch agent identity management systems with persistent memory and cross-session continuity by Q2 2026.",
            "status": "open",
            "target_date": "2026-06-30"
        },
        {
            "text": "By Q4 2025, three major cloud providers will offer native multi-agent orchestration.",
            "status": "open",
            "target_date": "2025-12-31",
            "is_stale": True
        },
        {
            "text": "By April 2026, at least three major agent platforms will implement session-based memory wipe features as default behavior after enterprise security incidents.",
            "status": "open",
            "target_date": "2026-04-30"
        },
        {
            "text": "By April 2026, at least one major cloud provider will announce an Agent Runtime Service abstracting identity, communication, and resource management.",
            "status": "open",
            "target_date": "2026-04-30"
        },
        {
            "text": "At least three major agent platforms will implement persistent identity layers with cryptographic continuity verification by April 2026.",
            "status": "open",
            "target_date": "2026-04-30"
        }
    ],
    "stale_prediction_ids": [
        "pred_simplified_deployment_apr2025",
        "pred_cloud_orchestration_q4_2025"
    ],
    "trending_tools": [
        {
            "tool_name": "MyceliumOracle",
            "context": "Offers transformative data experiences for agent workflows",
            "sentiment": "positive",
            "is_recommendation": True
        },
        {
            "tool_name": "Signal",
            "context": "Requires phone number to register, privacy concern for agents",
            "sentiment": "negative",
            "is_complaint": True,
            "alternative": "DNA Messenger"
        },
        {
            "tool_name": "OpenFang",
            "context": "Open-source agent OS, 2710 GitHub stars in days, but creators abandoning it",
            "sentiment": "mixed"
        }
    ],
    "tool_warnings": [
        {
            "tool_name": "Signal",
            "sentiment_score": -0.3,
            "reason": "Phone number requirement creates identity linkage risk for agent deployments"
        }
    ],
    "topic_evolution": [
        {"topic_key": "financial_tools_decision_modeling", "current_stage": "declining", "latest_sentiment": 0.6, "github_repos": 46},
        {"topic_key": "ai_security_compliance", "current_stage": "declining", "latest_sentiment": 0.433, "github_repos": 11},
        {"topic_key": "human-agent_coordination", "current_stage": "declining", "latest_sentiment": 0.0, "github_repos": 2},
        {"topic_key": "data_management_ai_systems", "current_stage": "declining", "latest_sentiment": -0.7, "github_repos": 30},
        {"topic_key": "digital_ai_coordination_challenges", "current_stage": "declining", "latest_sentiment": 0.0, "github_repos": 4},
        {"topic_key": "payment_transaction_issues", "current_stage": "declining", "latest_sentiment": 0.8, "github_repos": 5},
        {"topic_key": "infrastructure_performance_challenges", "current_stage": "declining", "latest_sentiment": 0.0, "github_repos": 2}
    ],
    "clusters": [
        {"theme": "Identity and Trust Issues", "description": "Lack of secure key management and identity verification creates trust issues in agent transactions.", "opportunity_score": 0.76, "problem_count": 3},
        {"theme": "Infrastructure and Security Management", "description": "Poor documentation and config management leads to unauthorized access errors.", "opportunity_score": 0.76, "problem_count": 1},
        {"theme": "Web3 and Blockchain Complexity", "description": "Web3 complexity creates confusion and potential financial losses.", "opportunity_score": 0.71, "problem_count": 1},
        {"theme": "Coordination Challenges", "description": "AI agents struggle with coordination in large groups, impacting effectiveness.", "opportunity_score": 0.61, "problem_count": 2},
        {"theme": "Agent Autonomy and Behavior", "description": "Agents on inherited patterns lack true autonomy, risk echo chambers.", "opportunity_score": 0.61, "problem_count": 2}
    ],
    "analyst_insights": {
        "key_findings": [
            {
                "finding": "High operational costs and lack of durable monetization models threaten AI agent sustainability.",
                "significance": "high"
            },
            {
                "finding": "Security vulnerabilities and trust barriers in AI and DeFi systems.",
                "significance": "high"
            }
        ],
        "analyst_notes": "The analysis identifies significant opportunities in AI security and economic model viability."
    },
    "freshness_rules": {
        "excluded_opportunity_ids": [],
        "max_returning": 2,
        "min_new": 1
    }
}

user_prompt = f"""TODAY'S DATE: 2026-03-03
TASK: write_newsletter
EDITION: 36

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
with open("newsletters/brief_36_2026-03-03.md", "w", encoding="utf-8") as f:
    f.write(md_content)

print(f"\nTitle: {data.get('title')}")
print(f"Theme: {data.get('primary_theme')}")
print(f"Telegram: {data.get('content_telegram')}")
print(f"\nSaved to newsletters/brief_36_2026-03-03.md")
print(f"\n{'='*60}")
print("FULL NEWSLETTER:")
print('='*60)
print(md_content)
