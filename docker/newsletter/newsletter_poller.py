#!/usr/bin/env python3
"""
Newsletter agent — direct Anthropic integration.

Polls Supabase agent_tasks for write_newsletter tasks, calls the Anthropic API
to generate the newsletter, saves results to Supabase, and marks the task done.
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from pydantic import ValidationError
from supabase import create_client, Client
from openai import OpenAI
import anthropic

from schemas import TASK_INPUT_SCHEMAS, NewsletterOutput

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
AGENT_NAME = os.getenv("AGENT_NAME", "newsletter")
OPENCLAW_DATA_DIR = os.getenv("OPENCLAW_DATA_DIR", "/home/openclaw/.openclaw")
POLL_INTERVAL = int(os.getenv("NEWSLETTER_POLL_INTERVAL", "30"))
MODEL = os.getenv("NEWSLETTER_MODEL", "claude-sonnet-4-20250514")
STRATEGIC_MODEL = os.getenv("NEWSLETTER_STRATEGIC_MODEL", "claude-sonnet-4-20250514")
LLM_PROXY_URL = os.getenv("LLM_PROXY_URL", "http://llm-proxy:8200")

WORKSPACE = Path(OPENCLAW_DATA_DIR) / "workspace"
NEWSLETTERS_DIR = WORKSPACE / "agentpulse" / "newsletters"

# Logging
LOG_DIR = Path(OPENCLAW_DATA_DIR) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "newsletter-poller.log"),
    ],
)
logger = logging.getLogger("newsletter-agent")

supabase: Client | None = None
client: OpenAI | None = None
deepseek_client: OpenAI | None = None
claude_client: anthropic.Anthropic | None = None

# ---------------------------------------------------------------------------
# Identity + Skill loading (from disk, with mtime caching)
# ---------------------------------------------------------------------------

AGENT_DIR = Path(OPENCLAW_DATA_DIR) / "agents" / "newsletter" / "agent"
SKILL_DIR = Path(OPENCLAW_DATA_DIR) / "skills" / "newsletter"

_identity_cache: str | None = None
_identity_mtime: float = 0

_skill_cache: str | None = None
_skill_mtime: float = 0

_strategic_voice_cache: str | None = None
_strategic_voice_mtime: float = 0


def load_identity(agent_dir: Path) -> str:
    """Load IDENTITY.md + SOUL.md from agent_dir, caching by mtime."""
    global _identity_cache, _identity_mtime
    identity_path = agent_dir / "IDENTITY.md"

    current_mtime = identity_path.stat().st_mtime if identity_path.exists() else 0

    if _identity_cache and current_mtime == _identity_mtime:
        return _identity_cache

    parts = []
    if identity_path.exists():
        parts.append(identity_path.read_text(encoding="utf-8"))
        _identity_mtime = current_mtime

    soul_path = agent_dir / "SOUL.md"
    if soul_path.exists():
        parts.append(f"\n---\n\n{soul_path.read_text(encoding='utf-8')}")

    if parts:
        _identity_cache = "\n\n".join(parts)
    else:
        logger.warning(f"Identity files not found in {agent_dir} — using fallback")
        _identity_cache = (
            "You are Pulse, the editorial voice of AgentPulse. "
            "Write the weekly Intelligence Brief as valid JSON."
        )

    return _identity_cache


def load_skill(skill_dir: Path) -> str:
    """Load SKILL.md from skill_dir, caching by mtime."""
    global _skill_cache, _skill_mtime
    skill_path = skill_dir / "SKILL.md"

    current_mtime = skill_path.stat().st_mtime if skill_path.exists() else 0

    if _skill_cache is not None and current_mtime == _skill_mtime:
        return _skill_cache

    if skill_path.exists():
        _skill_cache = skill_path.read_text(encoding="utf-8")
        _skill_mtime = current_mtime
    else:
        logger.warning(f"SKILL.md not found in {skill_dir}")
        _skill_cache = ""

    return _skill_cache


def load_strategic_voice(agent_dir: Path) -> str:
    """Load STRATEGIC_VOICE.md from agent_dir, caching by mtime."""
    global _strategic_voice_cache, _strategic_voice_mtime
    voice_path = agent_dir / "STRATEGIC_VOICE.md"

    current_mtime = voice_path.stat().st_mtime if voice_path.exists() else 0

    if _strategic_voice_cache is not None and current_mtime == _strategic_voice_mtime:
        return _strategic_voice_cache

    if voice_path.exists():
        _strategic_voice_cache = voice_path.read_text(encoding="utf-8")
        _strategic_voice_mtime = current_mtime
    else:
        logger.warning(f"STRATEGIC_VOICE.md not found in {agent_dir}")
        _strategic_voice_cache = ""

    return _strategic_voice_cache


_brief_template_cache: str | None = None
_brief_template_mtime: float = 0


def load_brief_template(agent_dir: Path) -> str:
    """Load BRIEF_TEMPLATE.md from agent_dir, caching by mtime."""
    global _brief_template_cache, _brief_template_mtime
    path = agent_dir / "BRIEF_TEMPLATE.md"

    current_mtime = path.stat().st_mtime if path.exists() else 0

    if _brief_template_cache is not None and current_mtime == _brief_template_mtime:
        return _brief_template_cache

    if path.exists():
        _brief_template_cache = path.read_text(encoding="utf-8")
        _brief_template_mtime = current_mtime
    else:
        logger.warning(f"BRIEF_TEMPLATE.md not found in {agent_dir}")
        _brief_template_cache = ""

    return _brief_template_cache


# ---------------------------------------------------------------------------
# Economics context (self-awareness)
# ---------------------------------------------------------------------------

LLM_PROXY_URL = os.getenv("LLM_PROXY_URL", "http://llm-proxy:8200")
_agent_api_key: str | None = os.getenv("AGENT_API_KEY") or None

_economics_cache: str | None = None
_economics_fetched_at: float = 0
_ECONOMICS_TTL = 300


def _get_agent_api_key() -> str:
    """Return cached API key, or look it up from Supabase on first call."""
    global _agent_api_key
    if _agent_api_key:
        return _agent_api_key
    try:
        result = supabase.table("agent_api_keys").select("api_key").eq("agent_name", AGENT_NAME).limit(1).execute()
        if result.data:
            _agent_api_key = result.data[0]["api_key"]
            return _agent_api_key
    except Exception:
        pass
    return ""


def fetch_economics_block() -> str:
    """Fetch spending summary from the proxy and format as a system prompt block.
    Non-blocking: returns empty string on any failure. 2-second timeout."""
    global _economics_cache, _economics_fetched_at

    now = time.time()
    if _economics_cache is not None and (now - _economics_fetched_at) < _ECONOMICS_TTL:
        return _economics_cache

    api_key = _get_agent_api_key()
    if not api_key:
        return ""

    try:
        resp = httpx.get(
            f"{LLM_PROXY_URL}/v1/proxy/wallet/{AGENT_NAME}/summary?period=7d",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
        )
        if resp.status_code != 200:
            logger.debug(f"Economics fetch returned {resp.status_code}")
            return _economics_cache or ""
        d = resp.json()
        cap_sats = d.get("spending_cap_sats") or 0
        cap_window = d.get("spending_cap_window") or "n/a"
        util = d.get("budget_utilization_pct")
        util_str = f"{util}%" if util is not None else "no cap"
        trend_str = d.get("trend_vs_previous_period", "flat")
        _economics_cache = (
            "\n\n---\n"
            "YOUR ECONOMICS (last 7 days):\n"
            f"Balance: {d['balance_sats']:,} sats | Spent: {d['spent_sats']:,} sats | Calls: {d['calls']:,}\n"
            f"Budget utilization: {util_str} of {cap_sats:,} sats {cap_window} cap\n"
            f"Cap hits: {d.get('cap_hits_in_period', 0)} | Trend: {trend_str} vs prior week\n"
            "---"
        )
        _economics_fetched_at = now
        logger.info(f"Economics context refreshed: {d['spent_sats']} sats spent, {d['calls']} calls")
    except Exception as e:
        logger.debug(f"Economics fetch failed (non-critical): {e}")

    return _economics_cache or ""


def init():
    global supabase, client, deepseek_client, claude_client
    logger.info(f"[INIT] NEWSLETTER_MODEL={MODEL}")
    logger.info(f"[INIT] DEEPSEEK_API_KEY={'set (' + DEEPSEEK_API_KEY[:8] + '...)' if DEEPSEEK_API_KEY else 'NOT SET'}")
    logger.info(f"[INIT] DEEPSEEK_BASE_URL={DEEPSEEK_BASE_URL}")
    logger.info(f"[INIT] OPENAI_API_KEY={'set' if OPENAI_API_KEY else 'NOT SET'}")
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Supabase not configured (SUPABASE_URL / SUPABASE_KEY missing)")
        return False
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set — cannot generate newsletters")
        return False
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    client_kwargs = {"api_key": OPENAI_API_KEY}
    if OPENAI_BASE_URL:
        client_kwargs["base_url"] = OPENAI_BASE_URL
    client = OpenAI(**client_kwargs)
    if DEEPSEEK_API_KEY:
        deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        logger.info("[INIT] DeepSeek client initialized successfully")
    else:
        logger.warning("[INIT] DEEPSEEK_API_KEY missing — all DeepSeek calls will fall back to OpenAI")
    # Claude client via LLM proxy (for strategic editor pass)
    claude_client = anthropic.Anthropic(
        api_key=OPENAI_API_KEY,  # Proxy uses the agent's ap_ key
        base_url=f"{LLM_PROXY_URL}/anthropic",
    )
    logger.info(f"[INIT] Claude client initialized (proxy: {LLM_PROXY_URL}/anthropic, model: {STRATEGIC_MODEL})")
    return True


def ensure_dirs():
    NEWSLETTERS_DIR.mkdir(parents=True, exist_ok=True)


def fetch_pending_tasks(limit: int = 5) -> list[dict]:
    """Atomically claim up to `limit` pending tasks via FOR UPDATE SKIP LOCKED."""
    result = supabase.rpc(
        "claim_agent_task",
        {"p_assigned_to": AGENT_NAME, "p_limit": limit},
    ).execute()
    return result.data or []


def validate_task_input(task_type: str, input_data: dict) -> None:
    """Validate inbound task input. Raises ValidationError on bad input (fail fast)."""
    schema = TASK_INPUT_SCHEMAS.get(task_type)
    if schema is None:
        logger.warning(f"No input schema for task_type='{task_type}', skipping validation")
        return
    schema.model_validate(input_data)


def validate_llm_output(raw: dict, model_cls: type) -> object:
    """Validate LLM output. On failure, constructs partial model and logs."""
    try:
        return model_cls.model_validate(raw)
    except ValidationError as e:
        logger.warning(f"LLM output validation errors ({model_cls.__name__}): {e}")
        valid_fields = {k: raw[k] for k in model_cls.model_fields if k in raw}
        return model_cls.model_construct(**valid_fields)


# ---------------------------------------------------------------------------
# Post-generation quality validators
# ---------------------------------------------------------------------------

def _extract_sections(md: str) -> dict[str, str]:
    """Split markdown into named sections based on ## headers."""
    sections: dict[str, str] = {}
    current = "_preamble"
    lines: list[str] = []
    for line in md.split("\n"):
        m = re.match(r"^#{1,3}\s+(.+)", line)
        if m:
            if lines:
                sections[current] = "\n".join(lines)
            current = m.group(1).strip()
            lines = []
        else:
            lines.append(line)
    if lines:
        sections[current] = "\n".join(lines)
    return sections


def _find_one_number_stat(sections: dict[str, str]) -> str | None:
    """Extract the primary stat from the One Number section."""
    for key, val in sections.items():
        if "one number" in key.lower():
            match = re.search(r'\*\*([^*]+)\*\*', val)
            if match:
                return match.group(1).strip()
    return None


def validate_stat_repetition(content_md: str) -> list[dict]:
    """Issue #1: Check that the One Number stat doesn't repeat across sections."""
    issues = []
    sections = _extract_sections(content_md)
    stat = _find_one_number_stat(sections)
    if not stat:
        return issues

    stat_normalized = stat.replace(",", "").replace("$", "").strip()

    occurrences = []
    for key, val in sections.items():
        if "one number" in key.lower():
            continue
        if stat in val or stat_normalized in val.replace(",", ""):
            occurrences.append(key)

    if occurrences:
        issues.append({
            "severity": "warning",
            "issue": "stat_repetition",
            "section": "One Number",
            "detail": f"Stat '{stat}' repeated in: {', '.join(occurrences)}",
        })
    return issues


def validate_section_echo(content_md: str) -> list[dict]:
    """Issue #2: Check that Spotlight and the next major section don't echo each other."""
    issues = []
    sections = _extract_sections(content_md)

    spotlight_text = ""
    insight_text = ""
    insight_key = ""

    for key, val in sections.items():
        if "spotlight" in key.lower():
            spotlight_text = val.lower()
        elif (key != "_preamble"
              and "one number" not in key.lower()
              and "spotlight" not in key.lower()
              and not insight_text):
            insight_text = val.lower()
            insight_key = key

    if not spotlight_text or not insight_text:
        return issues

    stop_words = {
        "about", "which", "their", "these", "being", "would", "could",
        "should", "other", "where", "there", "agent", "agents", "between",
        "through", "because", "before", "after", "while", "might", "still",
    }

    def sig_words(text: str) -> set[str]:
        return set(re.findall(r'\b[a-z]{5,}\b', text)) - stop_words

    spot_words = sig_words(spotlight_text)
    insight_words = sig_words(insight_text)

    if spot_words and insight_words:
        overlap = spot_words & insight_words
        overlap_ratio = len(overlap) / min(len(spot_words), len(insight_words))
        if overlap_ratio > 0.5:
            issues.append({
                "severity": "warning",
                "issue": "section_echo",
                "section": f"Spotlight vs {insight_key}",
                "detail": (f"Overlap ratio {overlap_ratio:.0%} — sections may echo "
                           f"each other. Shared: {', '.join(list(overlap)[:5])}"),
            })
    return issues


def validate_stale_predictions(content_md: str, input_data: dict) -> list[dict]:
    """Issue #4: Check for stale predictions published without resolution."""
    issues = []
    stale_ids = input_data.get('stale_prediction_ids', [])
    if not stale_ids:
        return issues

    sections = _extract_sections(content_md)
    pred_section = ""
    for key, val in sections.items():
        if "prediction" in key.lower() or "tracker" in key.lower():
            pred_section = val
            break

    if not pred_section:
        return issues

    stale_predictions = [
        p for p in input_data.get('predictions', [])
        if p.get('id') in stale_ids
    ]

    for pred in stale_predictions:
        title = (pred.get('title') or pred.get('prediction_text', ''))[:40]
        if title and title.lower() in pred_section.lower():
            issues.append({
                "severity": "critical",
                "issue": "stale_prediction",
                "section": "Prediction Tracker",
                "detail": (f"Prediction '{title}...' is past target_date "
                           f"({pred.get('target_date')}) — must be resolved"),
            })
    return issues


def validate_prediction_format(content_md: str) -> list[dict]:
    """Issue #6: Check predictions have specific dates and falsifiable outcomes."""
    issues = []
    sections = _extract_sections(content_md)

    pred_section = ""
    for key, val in sections.items():
        if "prediction" in key.lower() or "tracker" in key.lower():
            pred_section = val
            break

    if not pred_section:
        return issues

    # Match prediction lines: emoji + bold text
    pred_lines = re.findall(
        r'[\U0001f7e2\U0001f7e1\U0001f534\u2705\u274c\U0001f504]\s*\*\*(.+?)\*\*',
        pred_section)

    date_pattern = re.compile(
        r'(?:by|before|within)\s+(?:Q[1-4]\s+\d{4}|'
        r'(?:January|February|March|April|May|June|July|August|September|'
        r'October|November|December)\s+\d{4}|'
        r'(?:year[- ]?end|end\s+of)\s+\d{4}|\d+\s+months?)',
        re.IGNORECASE
    )

    for pred_text in pred_lines:
        if not date_pattern.search(pred_text):
            issues.append({
                "severity": "warning",
                "issue": "unfalsifiable_prediction",
                "section": "Prediction Tracker",
                "detail": f"Prediction lacks specific date: '{pred_text[:60]}'",
            })
    return issues


def validate_prediction_dates(content_md: str) -> list[dict]:
    """Check that no prediction references a date in the past."""
    issues = []
    sections = _extract_sections(content_md)

    pred_section = ""
    for key, val in sections.items():
        if "prediction" in key.lower() or "tracker" in key.lower():
            pred_section = val
            break

    if not pred_section:
        return issues

    today = datetime.now(timezone.utc).date()

    # Match prediction lines: emoji + bold text
    pred_lines = re.findall(
        r'[\U0001f7e2\U0001f7e1\U0001f534\u2705\u274c\U0001f504]\s*\*\*(.+?)\*\*',
        pred_section)

    month_to_num = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
    }

    for pred_text in pred_lines:
        parsed_date = None

        # Quarter pattern: "Q1 2025", "Q4 2025"
        q_match = re.search(r'Q([1-4])\s+(\d{4})', pred_text, re.IGNORECASE)
        if q_match:
            quarter, year = int(q_match.group(1)), int(q_match.group(2))
            month = quarter * 3
            day = 31 if month in (3, 12) else 30
            from datetime import date
            parsed_date = date(year, month, day)

        # Month + year: "June 2025", "December 2025"
        if not parsed_date:
            m_match = re.search(
                r'(?:by|before|within)\s+(January|February|March|April|May|June|July|August|'
                r'September|October|November|December)\s+(\d{4})',
                pred_text, re.IGNORECASE
            )
            if m_match:
                month_num = month_to_num[m_match.group(1).lower()]
                year = int(m_match.group(2))
                import calendar
                from datetime import date
                day = calendar.monthrange(year, month_num)[1]
                parsed_date = date(year, month_num, day)

        # "year-end 2025" / "end of 2025"
        if not parsed_date:
            ye_match = re.search(r'(?:year[- ]?end|end\s+of)\s+(\d{4})', pred_text, re.IGNORECASE)
            if ye_match:
                from datetime import date
                parsed_date = date(int(ye_match.group(1)), 12, 31)

        if parsed_date and parsed_date < today:
            issues.append({
                "severity": "critical",
                "issue": "past_date_prediction",
                "section": "Prediction Tracker",
                "detail": (f"Prediction has a past date ({parsed_date.isoformat()}): "
                           f"'{pred_text[:80]}'. Resolve it as Confirmed/Wrong/Revised "
                           f"or replace with a future-dated prediction."),
            })

    return issues


def validate_required_sections(content_md: str, input_data: dict) -> list[dict]:
    """Check that all required canonical sections are present."""
    issues = []
    sections = _extract_sections(content_md)
    section_names_lower = [k.lower() for k in sections.keys()]

    # "Read This, Skip the Rest" is always required
    has_read_this = any("read this" in s for s in section_names_lower)
    if not has_read_this:
        issues.append({
            "severity": "critical", "issue": "missing_section",
            "section": "Read This, Skip the Rest",
            "detail": "Missing 'Read This, Skip the Rest' section. This is the primary section "
                      "and MUST be present. Use the ## header: '## Read This, Skip the Rest'."
        })

    # Spotlight required only if spotlight data is present and not null
    spotlight = input_data.get('spotlight')
    if spotlight:
        has_spotlight = any("spotlight" in s for s in section_names_lower)
        if not has_spotlight:
            issues.append({
                "severity": "critical", "issue": "missing_section",
                "section": "Spotlight",
                "detail": "Spotlight data was provided but no Spotlight section was written. "
                          "Write the full Spotlight section with Thesis, Builder Lens, and Impact Lens."
            })

    # These sections are always required
    required = [
        ("top opportunities", "Top Opportunities"),
        ("emerging signal", "Emerging Signals"),
        ("tool radar", "Tool Radar"),
        ("prediction tracker", "Prediction Tracker"),
        ("gato", "Gato's Corner"),
    ]
    for pattern, label in required:
        if not any(pattern in s for s in section_names_lower):
            issues.append({
                "severity": "critical", "issue": "missing_section",
                "section": label,
                "detail": f"Missing '{label}' section. This is a required section in every edition. "
                          f"Write it using ## header and follow the Canonical Edition Structure."
            })

    return issues


def validate_output_length(content_md: str) -> list[dict]:
    """Check that the output meets minimum length thresholds."""
    issues = []
    word_count = len(content_md.split())
    if word_count < 300:
        issues.append({
            "severity": "critical", "issue": "truncated_output",
            "section": "Newsletter",
            "detail": f"Newsletter is only {word_count} words — minimum is 600. "
                      "The output appears truncated. Write ALL required sections: "
                      "Read This Skip the Rest, Top Opportunities, Emerging Signals, "
                      "Tool Radar, Prediction Tracker, Gato's Corner."
        })
    elif word_count < 600:
        issues.append({
            "severity": "warning", "issue": "short_output",
            "section": "Newsletter",
            "detail": f"Newsletter is only {word_count} words — expected 800+. "
                      "Ensure all sections have substantive content."
        })
    return issues


def validate_fabrication_signals(content_md: str, input_data: dict) -> list[dict]:
    """Detect likely fabrications: named entities not present in input data."""
    issues = []
    inp_str = json.dumps(input_data, default=str).lower()

    # Check for specific number claims like "eighty-five data points", "137 sources"
    number_claims = re.findall(
        r'(?:sourcing|analyzed|across|from)\s+'
        r'((?:[\w-]+)\s+(?:data points?|sources?|signals?|reports?))',
        content_md, re.IGNORECASE
    )
    for claim in number_claims:
        # Check if the number word or digit is grounded in stats
        words = claim.lower().split()
        number_word = words[0] if words else ""
        stats = input_data.get('stats', {})
        stat_values = [str(v) for v in stats.values() if isinstance(v, (int, float))]
        if number_word not in inp_str and number_word not in stat_values:
            issues.append({
                "severity": "warning", "issue": "potential_fabrication",
                "section": "Newsletter",
                "detail": f"Claim '{claim}' uses a number/quantity not found in input data. "
                          "Use actual stats from the data package (e.g. stats.total_posts_all_sources, "
                          "stats.posts_count) instead of inventing numbers."
            })

    # Check for capitalized proper nouns that aren't in the input data
    # (company/product names the LLM might invent)
    proper_nouns = re.findall(r'\b([A-Z][a-z]{2,15})\b', content_md)
    # Filter out common English words and known section headers
    common_words = {
        "The", "This", "That", "These", "Those", "While", "When", "Where",
        "What", "Which", "Whether", "Why", "How", "Read", "Skip", "Rest",
        "Top", "Tool", "Radar", "Prediction", "Tracker", "Emerging",
        "Signals", "Spotlight", "Builder", "Impact", "Lens", "Corner",
        "Active", "Rising", "Falling", "Stable", "Confirmed", "Failed",
        "January", "February", "March", "April", "May", "June", "July",
        "August", "September", "October", "November", "December",
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
        "Stay", "Bitcoin", "Gato", "AgentPulse", "Pulse",
    }
    suspicious = []
    for noun in set(proper_nouns) - common_words:
        if noun.lower() not in inp_str and len(noun) > 3:
            suspicious.append(noun)

    if suspicious:
        issues.append({
            "severity": "warning", "issue": "ungrounded_entities",
            "section": "Newsletter",
            "detail": f"Proper nouns not found in input data: {', '.join(sorted(suspicious)[:8])}. "
                      "Verify these are real — do not invent company names, product names, or entities. "
                      "Only reference sources and entities present in the data package."
        })

    return issues


def qualitative_review(content_md: str, input_data: dict) -> list[dict]:
    """LLM-based qualitative review: checks grounding, fabrication, tone, structure.

    Uses Claude Sonnet for a fast review pass. Returns list of issue dicts.
    """
    if not claude_client:
        return []

    stats = input_data.get('stats', {})
    sources = set()
    for p in input_data.get('premium_source_posts', []):
        sources.add(p.get('source_display') or p.get('source', ''))
    clusters = [c.get('theme', '') for c in input_data.get('clusters', [])[:10]]
    emerging = [s.get('theme', '') for s in input_data.get('section_b_emerging', [])[:10]]

    review_prompt = (
        "You are a fact-checker for an AI newsletter. Review the draft below against "
        "the ground truth data summary. Report ONLY concrete problems.\n\n"
        "GROUND TRUTH SUMMARY:\n"
        f"- Stats: {json.dumps(stats)}\n"
        f"- Premium sources: {', '.join(sorted(sources))}\n"
        f"- Cluster themes: {', '.join(clusters)}\n"
        f"- Emerging signals: {', '.join(emerging)}\n\n"
        "CHECK FOR:\n"
        "1. FABRICATED ENTITIES: Company names, product names, or people not in the data\n"
        "2. FABRICATED NUMBERS: Statistics, percentages, growth figures not in ground truth\n"
        "3. MISSING SECTIONS: Required sections are Read This Skip the Rest, Top Opportunities, "
        "Emerging Signals, Tool Radar, Prediction Tracker, Gato's Corner\n"
        "4. BANNED PHRASES: 'navigating without a map', 'wake-up call', 'smart businesses are already', "
        "'it remains to be seen', 'in today's rapidly evolving'\n"
        "5. VAGUE CLAIMS: Sentences with no specific data point, company name, or evidence\n\n"
        "Return valid JSON: {\"issues\": [{\"severity\": \"critical\"|\"warning\", "
        "\"issue\": \"short_label\", \"detail\": \"explanation\"}]}\n"
        "If no issues found, return {\"issues\": []}"
    )

    try:
        logger.info("[QUAL REVIEW] Running qualitative review...")
        _t0 = time.time()
        response = claude_client.messages.create(
            model=STRATEGIC_MODEL,
            max_tokens=1024,
            system=review_prompt,
            messages=[{"role": "user", "content": f"DRAFT:\n{content_md}"}],
        )

        class _Usage:
            def __init__(self, inp, out):
                self.prompt_tokens = inp
                self.completion_tokens = out
                self.total_tokens = inp + out
                self.input_tokens = inp
                self.output_tokens = out
        usage = _Usage(response.usage.input_tokens, response.usage.output_tokens)
        log_llm_call("newsletter", "qualitative_review", response.model, usage, int((time.time() - _t0) * 1000))

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        result = json.loads(text)
        issues = result.get('issues', [])
        logger.info(f"[QUAL REVIEW] Found {len(issues)} issue(s)")
        return issues
    except Exception as e:
        logger.error(f"[QUAL REVIEW] Failed (non-blocking): {e}")
        return []


def run_quality_checks(result: dict, input_data: dict) -> list[dict]:
    """Run all post-generation quality checks. Returns list of issues."""
    content = result.get('content_markdown', '')
    if not content:
        return [{"severity": "critical", "issue": "empty_content",
                 "section": "Newsletter", "detail": "No content_markdown"}]

    all_issues: list[dict] = []

    # Missing impact edition is critical — triggers retry
    impact = result.get('content_markdown_impact', '')
    if not impact or not impact.strip():
        all_issues.append({
            "severity": "critical", "issue": "empty_impact",
            "section": "Impact Edition",
            "detail": "content_markdown_impact is empty. You MUST generate the impact/strategic "
                      "version. Include it in the JSON as content_markdown_impact."
        })

    # Structural gates — catch truncated/lazy outputs
    all_issues.extend(validate_output_length(content))
    all_issues.extend(validate_required_sections(content, input_data))

    # Fabrication detection
    all_issues.extend(validate_fabrication_signals(content, input_data))

    all_issues.extend(validate_stat_repetition(content))
    all_issues.extend(validate_section_echo(content))
    all_issues.extend(validate_stale_predictions(content, input_data))
    all_issues.extend(validate_prediction_format(content))
    all_issues.extend(validate_prediction_dates(content))
    return all_issues


def _auto_fix_stat_repetition(result: dict) -> dict:
    """Auto-fix: remove duplicate One Number stats from later sections."""
    content = result.get('content_markdown', '')
    if not content:
        return result

    sections = _extract_sections(content)
    stat = _find_one_number_stat(sections)
    if not stat:
        return result

    stat_pattern = re.escape(stat)
    matches = list(re.finditer(stat_pattern, content))

    if len(matches) <= 1:
        return result

    fixed = content
    for match in reversed(matches[1:]):
        start, end = match.span()
        fixed = fixed[:start] + "the figure highlighted above" + fixed[end:]

    if fixed != content:
        result['content_markdown'] = fixed
        logger.info(f"Auto-fixed: removed {len(matches) - 1} duplicate stat occurrence(s)")
    return result


def _auto_fix_empty_sections(result: dict) -> dict:
    """Remove sections whose body is just 'N/A', empty, or has no real content."""
    na_pattern = re.compile(
        r'(^## .+\n)'           # section header
        r'(\s*N/?A\.?\s*\n?)',  # body is just "N/A" or "N/A." with optional whitespace
        re.MULTILINE
    )
    count = 0
    for field in ('content_markdown', 'content_markdown_impact'):
        content = result.get(field, '')
        if not content:
            continue
        fixed = na_pattern.sub('', content)
        if fixed != content:
            result[field] = fixed.strip() + '\n'
            count += 1
    if count:
        logger.info("Auto-fixed: removed empty N/A section(s) from newsletter")
    return result


def mark_task_status(task_id: str, status: str, **fields):
    payload = {"status": status, **fields}
    supabase.table("agent_tasks").update(payload).eq("id", task_id).execute()


def _track_prepass(input_data: dict, result: dict, headline_lines: list, cluster_lines: list):
    """Record prepass angle to newsletter_prepass_tracking for Fix 3a monitoring."""
    try:
        angle = result.get('chosen_angle', '')
        edition = input_data.get('edition_number') or input_data.get('narrative_context', {}).get('edition_number')

        # Detect primary named entity
        big4 = ['Anthropic', 'OpenAI', 'Google', 'Amazon', 'Microsoft', 'Meta']
        primary_entity = None
        for entity in big4:
            if entity.lower() in angle.lower():
                primary_entity = entity
                break

        # Classify angle source: does the angle text match a headline or a cluster?
        angle_lower = angle.lower()
        from_headline = any(
            h.split('] ')[-1].split('\n')[0].lower()[:40] in angle_lower
            for h in headline_lines if '] ' in h
        ) if headline_lines else False
        clusters_emphasized = result.get('clusters_to_emphasize', [])
        from_cluster = bool(clusters_emphasized)

        if from_headline and from_cluster:
            angle_source = 'mixed'
        elif from_headline:
            angle_source = 'headline'
        elif from_cluster:
            angle_source = 'cluster'
        else:
            angle_source = 'unknown'

        headline_justification = result.get('headline_justification')

        # Flag stale cluster angles (avg_recency_days > 14)
        stale_cluster = False
        if angle_source in ('cluster', 'mixed'):
            clusters = input_data.get('clusters', [])
            emphasized = [c.lower() for c in clusters_emphasized]
            for c in clusters:
                if c.get('theme', '').lower() in emphasized:
                    if c.get('avg_recency_days', 0) > 14:
                        stale_cluster = True
                        break

        supabase.table('newsletter_prepass_tracking').insert({
            'edition_number': edition,
            'chosen_angle': angle,
            'primary_entity': primary_entity,
            'angle_source': angle_source,
            'headline_justification': headline_justification,
            'stale_cluster_flag': stale_cluster,
        }).execute()
        logger.info(f"[EDITORIAL] Tracked prepass: entity={primary_entity}, source={angle_source}, stale_cluster={stale_cluster}")
    except Exception as e:
        logger.warning(f"[EDITORIAL] Prepass tracking failed (non-blocking): {e}")


def editorial_prepass(input_data: dict) -> dict | None:
    """Editor-in-chief pre-pass: choose this week's angle based on editorial history.

    Uses Claude Sonnet for a lightweight judgment call before the main generation.
    Returns a JSON dict with editorial direction, or None on failure.
    """
    if not claude_client:
        logger.warning("[EDITORIAL] Claude client not available — skipping pre-pass")
        return None

    narrative_ctx = input_data.get('narrative_context')
    if not narrative_ctx or not narrative_ctx.get('previous_editions'):
        logger.info("[EDITORIAL] No narrative context — skipping pre-pass")
        return None

    # Build compact context for the editor-in-chief
    editions = narrative_ctx['previous_editions']
    edition_lines = []
    for ed in editions:
        excerpt = (ed.get('opening_excerpt') or '')[:150]
        edition_lines.append(
            f"#{ed.get('edition_number', '?')} ({ed.get('weeks_ago', '?')}w ago): "
            f"\"{ed.get('title', '?')}\" — Theme: {ed.get('primary_theme', '?')}"
            f"\n  Excerpt: {excerpt}"
        )

    clusters = input_data.get('clusters', [])
    cluster_lines = []
    for c in clusters[:10]:
        cluster_lines.append(
            f"- {c.get('theme', '?')} (score: {c.get('opportunity_score', 0):.2f})"
        )

    spotlight = input_data.get('spotlight')
    spotlight_str = f"Spotlight topic: {spotlight.get('topic_name', '?')}" if spotlight else "No spotlight this week."

    avoided = input_data.get('avoided_themes', [])

    # Build headline context from premium source posts
    premium = input_data.get('premium_source_posts', [])
    headline_lines = []
    for p in premium[:15]:
        src = p.get('source_display') or p.get('source', '?')
        title = p.get('title', '?')
        summary = (p.get('summary') or '')[:150].strip()
        headline_lines.append(f"- [{src}] {title}\n  {summary}")

    system_prompt = (
        "You are the editor-in-chief of AgentPulse, a weekly intelligence brief about "
        "the AI agent economy. Your job is to choose THIS WEEK's editorial angle.\n\n"
        "You must pick an angle that:\n"
        "1. Is genuinely different from the last 3 editions' lead themes\n"
        "2. Draws from the strongest clusters OR from a specific high-authority headline\n"
        "3. Connects to the ongoing narrative (builds on what readers already know)\n"
        "4. Would make a smart executive stop scrolling\n\n"
        "If a specific high-authority headline this week is a stronger lead than any "
        "cluster theme, choose the headline as the angle. The angle should be specific "
        "and time-bound when the data warrants — a concrete event with named entities "
        "(\"Anthropic launched an agent-on-agent commerce marketplace this week\") is "
        "preferable to a generic theme (\"agent coordination challenges\") when both "
        "are available.\n\n"
        "Cluster scores are statistical artifacts and should not override a fresh, "
        "time-bound headline anchor. If you choose a cluster theme, justify why no "
        "headline this week is a stronger lead.\n\n"
        "Respond with valid JSON only. No markdown, no commentary."
    )

    user_msg = (
        f"PREVIOUS EDITIONS (oldest first):\n" + "\n".join(edition_lines) +
        f"\n\nTHIS WEEK'S CLUSTERS (by score):\n" + "\n".join(cluster_lines)
    )
    if headline_lines:
        user_msg += (
            f"\n\nRECENT HIGH-AUTHORITY HEADLINES (Tier 1 sources, consider as potential leads):\n"
            + "\n".join(headline_lines)
        )
    user_msg += (
        f"\n\n{spotlight_str}" +
        f"\n\nAVOIDED THEMES (already covered recently): {', '.join(avoided)}" +
        f"\n\nChoose this week's angle. Return JSON:\n"
        "{\n"
        '  "chosen_angle": "one sentence describing this week\'s lead angle",\n'
        '  "why_fresh": "one sentence explaining why this is different from recent editions",\n'
        '  "clusters_to_emphasize": ["2-3 cluster themes to draw from"],\n'
        '  "clusters_to_avoid": ["cluster themes already well-covered"],\n'
        '  "narrative_bridge": "one sentence connecting to a previous edition",\n'
        '  "headline_justification": "if cluster-based, explain why no headline was a stronger lead"\n'
        "}"
    )

    try:
        logger.info("[EDITORIAL] Running editor-in-chief pre-pass...")
        _t0 = time.time()
        response = claude_client.messages.create(
            model=STRATEGIC_MODEL,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )

        class _Usage:
            def __init__(self, inp, out):
                self.prompt_tokens = inp
                self.completion_tokens = out
                self.total_tokens = inp + out
        usage = _Usage(response.usage.input_tokens, response.usage.output_tokens)
        log_llm_call("newsletter", "editorial_prepass", response.model, usage, int((time.time() - _t0) * 1000))

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        result = json.loads(text)
        logger.info(f"[EDITORIAL] Chosen angle: {result.get('chosen_angle', '?')}")
        logger.info(f"[EDITORIAL] Why fresh: {result.get('why_fresh', '?')}")
        logger.info(f"[EDITORIAL] Clusters to emphasize: {result.get('clusters_to_emphasize', [])}")
        logger.info(f"[EDITORIAL] Narrative bridge: {result.get('narrative_bridge', '?')}")

        # Fix 3a monitoring: track prepass angle for entity skew + source analysis
        _track_prepass(input_data, result, headline_lines, cluster_lines)

        return result
    except Exception as e:
        logger.error(f"[EDITORIAL] Pre-pass failed (non-blocking): {e}")
        return None


def generate_newsletter(task_type: str, input_data: dict, budget_config: dict) -> dict:
    """Call OpenAI with identity + skill as system prompt, task + data as user message."""

    identity = load_identity(AGENT_DIR)
    skill = load_skill(SKILL_DIR)
    brief_template = load_brief_template(AGENT_DIR)

    system_prompt = f"{identity}\n\n---\n\nSKILL REFERENCE:\n{skill}"
    if brief_template:
        system_prompt += f"\n\n---\n\nBRIEF TEMPLATE REFERENCE:\n{brief_template}"
    system_prompt += (
        "\n\nYou MUST respond with valid JSON only — no markdown fences, no extra text."
        "\n\nCRITICAL RULES — CHECK BEFORE WRITING EACH SECTION:"
        "\n0. NARRATIVE CONTINUITY (HIGHEST PRIORITY): The FIRST sentence of your"
        " content_markdown_impact opening paragraph MUST bridge to a previous edition."
        " Use phrasing like: 'Last week we explored [topic]. This week, [transition].'"
        " or 'Two editions ago we covered [topic]. The situation just changed.'"
        " Check the EDITORIAL CONTINUITY section below for recent edition titles and"
        " themes. This is NON-NEGOTIABLE — an impact edition without a continuity"
        " bridge is a failed edition."
        "\n1. SPOTLIGHT: If `spotlight` is null OR missing from input_data, OMIT the"
        " ENTIRE section — no header, no placeholder, no explanation."
        " If spotlight exists but `has_prediction` is false or `prediction` key is"
        " absent, write the Spotlight section WITHOUT the Prediction Scorecard Entry —"
        " skip it entirely. NEVER invent a prediction."
        "\n2. CANONICAL SECTION ORDER: Read This Skip the Rest (## header, 3 paragraphs),"
        " Spotlight (conditional), Top Opportunities, Emerging Signals, Tool Radar,"
        " Prediction Tracker, Gato's Corner. Write every required section in order."
        " The brief is ALWAYS first — before Spotlight. No separate Lede or Board Brief."
        " NEVER stop before Gato's Corner — it is the last section and mandatory."
        "\n3. GATO'S CORNER: ALWAYS write this. NEVER omit it."
        " A newsletter without Gato's Corner is a failed newsletter."
        "\n4. SPOTLIGHT WORD COUNT: If Spotlight IS present, body MUST be 400–500 words."
        " Under 350 is a hard failure — STOP and expand before continuing."
        "\n5. NO PLACEHOLDER TEXT: Never write 'Watch for...', 'investigation underway',"
        " 'N/A', or any trailing incomplete sentence. If a section has no content,"
        " OMIT THE ENTIRE SECTION — no header, no 'N/A', no placeholder."
        "\n6. FILLER PHRASES BANNED: 'navigating without a map', 'wake-up call',"
        " 'smart businesses are already', 'sifting through the narrative', 'elevated"
        " urgency', 'in today's rapidly evolving', 'it remains to be seen'."
        " Write like a reporter, not a business deck."
        "\n7. JARGON GROUNDING: Every technical concept must be grounded on first"
        " use: name it, explain it in one sentence, then give a specific real-world"
        " scenario. Write for a smart founder, not an AI engineer."
        "\n8. STALE PREDICTIONS: Check input_data for stale_prediction_ids. Any"
        " prediction whose target_date has passed MUST be resolved as ✅ Confirmed,"
        " 🔴 Failed, or updated — with honest explanation. NEVER publish a"
        " past-due prediction as Active."
        "\n9. PREDICTION FORMAT: Every new prediction must follow: 'By [specific"
        " date], [specific measurable outcome].' Target dates must be at least 4"
        " weeks in the future FROM TODAY'S DATE (shown in user message). NEVER"
        " use dates in the past. Check TODAY'S DATE before writing any prediction."
        "\n10. GATO'S CORNER STRUCTURE: 1 paragraph. Must reference something specific"
        " from this edition's data. End with 'Stay humble, stack sats.'"
        "\n11. THEME DIVERSITY: Check input_data for `avoided_themes`. These are"
        " the primary themes from the last 3 editions. Your Spotlight"
        " framing and lede MUST explore a DIFFERENT macro-theme. If the"
        " data naturally points to a recent theme, find a genuinely fresh angle."
        " NEVER lead with the same thesis as a recent edition."
        "\n12. PRIMARY THEME: You MUST include a `primary_theme` field in your"
        " JSON response — a 2-5 word label for this edition's dominant theme"
        " (e.g. 'agent memory management', 'protocol governance fragmentation')."
        "\n13. SPOTLIGHT STRUCTURE: If Spotlight is present, use the EXACT format:"
        " `## Spotlight: [Conviction-Laden Title]` then `**Thesis: [one-line]**`"
        " then body paragraphs (3 max), then `### Builder Lens` (technical implications),"
        " then `### Impact Lens` (strategic implications), then"
        " `### Prediction Scorecard Entry` with Prediction/Timeline/Metric/Confidence."
        " Use proper markdown ## and ### headers — NEVER bold inline headers like"
        " `**Builder Lens**`. Bold text is NOT a section header."
        "\n14. SOURCE ATTRIBUTION: input_data includes `premium_source_posts`"
        " (Tier 1 AUTHORITY + Tier 2 CURATED sources like a16z, MIT Tech Review,"
        " Simon Willison, Latent Space, Andrew Ng, etc). Reference these by name"
        " in your analysis. Prefer citing premium sources over generic 'HN discussion'."
        " Also check `section_b_emerging` for `source_names` and `source_tier_label`."
        "\n15. TOOL RADAR: Each entry MUST include: name, trajectory (Rising/Falling/Stable),"
        " mention count in past 30 days, average sentiment score, and 1-2 sentence analysis."
        " Entries without quantitative data are a failure."
        "\n16. PREDICTION TRACKER: Each prediction in input_data has an `emoji_status`"
        " field (🟢 Active / 🟡 At Risk / 🔴 Failed / ✅ Confirmed). Use this EXACT"
        " status — do NOT override it. Format: emoji + bold prediction text + 1-2"
        " sentences on progress or evidence. Entries without context are a failure."
        "\n17. KILL RULES: 'In conclusion'/'In sum' → cut. 'Stakeholders'/'the industry'"
        " without names → replace. Bold inline headers → use proper ## headers."
        " Any generic paragraph → rewrite with specific data."
    )

    # Inject editorial continuity from narrative_context (promoted to system prompt)
    narrative_ctx = input_data.get('narrative_context')
    if narrative_ctx:
        editions_list = narrative_ctx.get('previous_editions', [])
        spotlights_list = narrative_ctx.get('recent_spotlights', [])
        if editions_list:
            edition_lines = []
            for ed in editions_list:
                edition_lines.append(
                    f"  {ed.get('edition_number', '?')}. \"{ed.get('title', '?')}\" "
                    f"— Theme: {ed.get('primary_theme', '?')} "
                    f"— {ed.get('opening_excerpt', '')[:200]}"
                )
            system_prompt += (
                "\n\nEDITORIAL CONTINUITY — READ BEFORE WRITING:"
                "\nHere is what you covered in recent editions:"
                "\n" + "\n".join(edition_lines)
            )
            if spotlights_list:
                system_prompt += "\n\nRecent spotlights (deep-dived previously): " + ", ".join(spotlights_list)
            system_prompt += (
                "\n\nRULES (non-negotiable):"
                "\n1. Your opening paragraph MUST include a one-sentence bridge to a"
                " previous edition. Examples: \"Last week we mapped the payment"
                " infrastructure gap. This week, something shifted.\" or \"Two"
                " editions ago we explained why agents can't verify each other."
                " The problem just got more expensive.\""
                "\n2. Do NOT repeat the same lead angle as the last 3 editions."
                " Find what's NEW in this week's data."
                "\n3. In the impact edition (content_markdown_impact), use bold inline"
                " markers like **The credential problem.** to introduce sub-topics"
                " within your main essay. These create scannability. Every impact"
                " edition needs 3-4 of these markers woven into the flowing prose."
            )
            logger.info(f"Injected editorial continuity into system prompt ({len(editions_list)} editions)")

    # Inject editorial direction from pre-pass
    editorial_dir = input_data.get('editorial_direction')
    if editorial_dir:
        system_prompt += (
            "\n\nEDITORIAL DIRECTION (from editor-in-chief):"
            f"\nLead angle: {editorial_dir.get('chosen_angle', '?')}"
            f"\nWhy this is fresh: {editorial_dir.get('why_fresh', '?')}"
            f"\nDraw from these clusters: {', '.join(editorial_dir.get('clusters_to_emphasize', []))}"
            f"\nAvoid leading with: {', '.join(editorial_dir.get('clusters_to_avoid', []))}"
            f"\nNarrative bridge: {editorial_dir.get('narrative_bridge', '?')}"
            "\n\nFollow this direction. The editor has reviewed the past 8 editions"
            " and chosen this angle specifically because it hasn't been covered recently."
        )
        logger.info("Injected editorial direction into system prompt")

    # Inject quality feedback on retry
    quality_feedback = input_data.pop('_quality_feedback', None)
    if quality_feedback:
        system_prompt += (
            "\n\nQUALITY ISSUES FROM PREVIOUS ATTEMPT — FIX THESE:"
            + "".join(f"\n- {issue}" for issue in quality_feedback)
        )

    system_prompt += fetch_economics_block()

    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    user_msg = (
        f"TODAY'S DATE: {today}\n\n"
        f"TASK TYPE: {task_type}\n\n"
        f"BUDGET: {json.dumps(budget_config)}\n\n"
        f"INPUT DATA:\n{json.dumps(input_data, indent=2, default=str)}"
    )

    logger.info(f"Calling {MODEL} for {task_type}...")

    _t0 = time.time()
    if MODEL.startswith("claude") and claude_client:
        # Use Anthropic client for Claude models
        response = claude_client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        class _Usage:
            def __init__(self, inp, out):
                self.prompt_tokens = inp
                self.completion_tokens = out
                self.total_tokens = inp + out
                self.input_tokens = inp
                self.output_tokens = out
        usage = _Usage(response.usage.input_tokens, response.usage.output_tokens)
        log_llm_call("newsletter", task_type, response.model, usage, int((time.time() - _t0) * 1000))
        text = response.content[0].text.strip()
    else:
        response = routed_llm_call(
            MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=16000,
            response_format={"type": "json_object"},
        )
        log_llm_call("newsletter", task_type, response.model, response.usage, int((time.time() - _t0) * 1000))
        text = response.choices[0].message.content.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    result = json.loads(text)

    # The LLM may wrap content in a "result" key following the SKILL.md output format
    if "result" in result and isinstance(result["result"], dict):
        inner = result["result"]
        # Merge budget_usage and negotiation_request to top level if present
        for extra_key in ("budget_usage", "negotiation_request"):
            if extra_key in result:
                inner[extra_key] = result[extra_key]
        result = inner

    logger.info(f"Newsletter generated: \"{result.get('title', '?')}\"")
    return result


# ---------------------------------------------------------------------------
# Strategic Editor — second-pass rewrite for non-technical readers
# ---------------------------------------------------------------------------

STRATEGIC_EDITOR_PROMPT = """You are editing an AI-industry intelligence newsletter for a non-technical business audience: C-suite executives, portfolio managers, board members, and strategy leads. These readers make investment and resource allocation decisions. They do not write code or manage infrastructure.

Your job is to review the draft and apply these transformations. Preserve every insight — change only the packaging.

IMPORTANT: Gato's Corner has been removed from this input before sending to you. Do not generate a Gato's Corner section. Do not check for its presence. It will be re-attached verbatim after your edit. Focus only on editing the sections present in the input.

## Rules

1. **Jargon scan.** Rewrite any term that requires AI/ML, crypto, or software engineering background to understand. If you cannot rewrite it without losing meaning, add a parenthetical explanation of 10 words or fewer.

2. **Metric translation.** Convert all technical metrics to business equivalents:
   - Token counts → dollar costs or human-equivalent time
   - Cluster scores / severity ratings → plain language (high/medium/low risk with one-sentence explanation)
   - GitHub contributor counts → "engineering team size" or "active developer count"
   - On-chain metrics → plain financial equivalents where possible

3. **"So what" test.** Every paragraph's first sentence must be understandable by a CFO with no technical background. If not, rewrite the opening sentence.

4. **Analogy injection.** Where a technical concept has a direct business-world parallel, add it:
   - Agent coordination problems → "like managing a consulting team with no project manager"
   - Settlement layers → "like Visa's network, but for AI agent transactions"
   - Attack vectors → "security vulnerabilities" or "points of failure"

5. **Structure check.** Verify:
   - "Read This, Skip the Rest" section exists at the top (## header, not # header — use ##). Zero jargon.
   - Prediction Tracker entries are understandable without technical context

6. **PRESERVE (critical):**
   - Any sentence referencing previous editions ("Last week we...", "Two editions ago...") — this is narrative continuity. Do NOT remove or rewrite it.
   - Bold inline markers like **The trust problem.** — these create scannability. If the draft has them, keep them. If it doesn't have at least 3, ADD them to introduce sub-topics within the flowing prose.
   - The two-section structure: "Read This, Skip the Rest" (main essay), "Prediction Tracker". Do NOT add extra ## sections.

7. **Do NOT:**
   - Remove any substantive insight or prediction
   - Add hedging language that weakens conviction (the editorial voice is deliberately opinionated)
   - Increase word count by more than 15%
   - Remove the Prediction Tracker section
   - Change any prediction wording, timeline, or confidence level
   - Add "Decision Framework" tables, "Board Brief", "Opportunity Radar", "Gato's Corner", or any other section structure — the impact edition is ONE flowing essay plus predictions
   - Generate or fabricate any section not present in the input

8. **PREDICTIONS:** Do not rewrite, reformat, or summarize predictions. Use the exact prediction text, dates, status emojis (🟢/🟡/🔴/✅), and status labels from the PREDICTION GROUND TRUTH data provided after the draft. Add a one-sentence plain-language explanation before each prediction for non-technical readers, but preserve the prediction entry itself exactly as provided.

## Output

Return ONLY the full edited markdown. No commentary, no explanations, no wrapper text. Just the edited newsletter text ready for publication."""


def edit_strategic_mode(content_markdown_impact: str, input_data: dict = None) -> str:
    """Second-pass editor: rewrites Impact mode content for non-technical readers.

    Takes raw Impact mode markdown from generate_newsletter(), returns edited version.
    On failure, raises exception — caller handles graceful degradation.
    """
    if not content_markdown_impact or not content_markdown_impact.strip():
        return content_markdown_impact

    # Extract Gato's Corner BEFORE sending to editor — editor never sees it
    gato_corner_original = None
    content_for_editor = content_markdown_impact
    gato_split = re.split(r"(## Gato.s Corner)", content_markdown_impact, maxsplit=1)
    if len(gato_split) == 3:
        # gato_split: [before, "## Gato's Corner", after]
        content_for_editor = gato_split[0].rstrip()
        gato_corner_original = gato_split[1] + gato_split[2]
        logger.info(f"[GATO] Extracted Gato's Corner ({len(gato_corner_original)} chars) — will not send to editor")
        logger.info(f"[GATO PRE-EDIT] {gato_corner_original[:300]}")
    else:
        logger.warning("[GATO] No Gato's Corner found in content — nothing to protect")

    logger.info("Running strategic editor second pass...")

    # Build system prompt: base editor rules + strategic voice guide
    strategic_voice = load_strategic_voice(AGENT_DIR)
    system_prompt = STRATEGIC_EDITOR_PROMPT
    if strategic_voice:
        system_prompt += f"\n\n---\n\nSTRATEGIC VOICE GUIDE:\n{strategic_voice}"

    # Inject editorial continuity into the editor pass (full context)
    narrative_ctx = (input_data or {}).get('narrative_context')
    if narrative_ctx:
        editions_list = narrative_ctx.get('previous_editions', [])
        spotlights_list = narrative_ctx.get('recent_spotlights', [])
        if editions_list:
            edition_lines = []
            for ed in editions_list:
                excerpt = ed.get('opening_excerpt', '')
                excerpt_str = f"\n    Excerpt: {excerpt[:200]}" if excerpt else ""
                edition_lines.append(
                    f"  #{ed.get('edition_number', '?')} ({ed.get('weeks_ago', '?')}w ago):"
                    f" \"{ed.get('title', '?')}\""
                    f" — Theme: {ed.get('primary_theme', '?')}"
                    f"{excerpt_str}"
                )
            system_prompt += (
                "\n\n---\n\nEDITORIAL CONTINUITY (preserve or add during editing):"
                "\nRecent editions (oldest first):\n" + "\n".join(edition_lines)
            )
            if spotlights_list:
                system_prompt += "\n\nRecent spotlights: " + ", ".join(spotlights_list)
            system_prompt += (
                "\n\nDuring editing, PRESERVE any narrative bridge to previous editions."
                " If none exists, ADD one to the opening paragraph (e.g. \"Last week"
                " we explored X. This week...\")."
                "\nEnsure the text uses bold inline markers like **The trust problem.**"
                " to introduce sub-topics — at least 3 markers throughout the essay."
            )

    # Inject editorial direction into strategic editor pass
    editorial_dir = (input_data or {}).get('editorial_direction')
    if editorial_dir:
        system_prompt += (
            "\n\n---\n\nEDITORIAL DIRECTION (from editor-in-chief — preserve this angle):"
            f"\nLead angle: {editorial_dir.get('chosen_angle', '?')}"
            f"\nClusters emphasized: {', '.join(editorial_dir.get('clusters_to_emphasize', []))}"
            f"\nNarrative bridge: {editorial_dir.get('narrative_bridge', '?')}"
            "\nPreserve the editorial angle during editing. Do not drift toward a different theme."
        )

    # Build user message with prediction ground truth
    predictions_json = json.dumps(
        (input_data or {}).get('predictions', []),
        indent=2, default=str,
    )
    user_message = (
        f"Here is the impact edition draft to edit:\n\n"
        f"{content_for_editor}\n\n"
        f"---\n\n"
        f"PREDICTION GROUND TRUTH — use these exact predictions, dates, and status."
        f" Do not invent or modify predictions:\n\n"
        f"{predictions_json}"
    )

    # Log what we're sending (truncated for readability)
    pred_count = len((input_data or {}).get('predictions', []))
    logger.info(
        f"[STRATEGIC EDITOR] User message: {len(user_message)} chars, "
        f"predictions ground truth: {pred_count} entries, "
        f"system prompt: {len(system_prompt)} chars"
    )
    logger.info(f"[STRATEGIC EDITOR] Predictions JSON preview: {predictions_json[:300]}")

    _t0 = time.time()
    if claude_client:
        logger.info(f"[ROUTING] Strategic editor using {STRATEGIC_MODEL} via Claude proxy")
        claude_response = claude_client.messages.create(
            model=STRATEGIC_MODEL,
            max_tokens=8192,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message},
            ],
        )
        # Build a minimal usage-compatible object for logging
        class _Usage:
            def __init__(self, inp, out):
                self.prompt_tokens = inp
                self.completion_tokens = out
                self.total_tokens = inp + out
        usage = _Usage(claude_response.usage.input_tokens, claude_response.usage.output_tokens)
        log_llm_call("newsletter", "strategic_editor", claude_response.model, usage, int((time.time() - _t0) * 1000))
        edited = claude_response.content[0].text.strip()
    else:
        logger.warning("[ROUTING] Claude client not available — falling back to MODEL for strategic editor")
        response = routed_llm_call(
            MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=16000,
        )
        log_llm_call("newsletter", "strategic_editor", response.model, response.usage, int((time.time() - _t0) * 1000))
        edited = response.choices[0].message.content.strip()

    # Strip markdown fences if the LLM wraps its response
    if edited.startswith("```"):
        edited = re.sub(r"^```(?:markdown)?\s*", "", edited)
        edited = re.sub(r"\s*```$", "", edited)

    logger.info(f"Strategic editor pass completed ({len(edited)} chars)")

    # Append original Gato's Corner back (editor never saw it, so it's unchanged)
    if gato_corner_original:
        if re.search(r"## Gato.s Corner", edited, re.IGNORECASE):
            logger.warning("[GATO] Editor generated a Gato's Corner despite instructions — stripping before appending original")
            edited = re.split(r"## Gato.s Corner", edited, maxsplit=1, flags=re.IGNORECASE)[0].rstrip()
        edited = edited.rstrip() + "\n\n" + gato_corner_original.strip() + "\n"
        logger.info(f"[GATO POST-EDIT] {gato_corner_original[:300]}")
        logger.info("[GATO] Appended original Gato's Corner — editor never saw it, zero drift possible")

    return edited


def save_newsletter(result: dict, input_data: dict):
    """Save newsletter to Supabase and local file."""
    edition = result.get("edition", input_data.get("edition_number", 0))
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Extract primary_theme from LLM response, with fallback to title
    primary_theme = result.get("primary_theme")
    if not primary_theme:
        title = result.get("title", "")
        if title:
            primary_theme = title.lower().strip()[:100]
            logger.info(f"primary_theme not in LLM response; falling back to title: '{primary_theme}'")

    # Dual-audience fields (gracefully handle older format without impact content)
    title_impact = result.get("title_impact", result.get("title", ""))
    content_markdown_impact = result.get("content_markdown_impact", "")

    # Upsert into newsletters table
    row = {
        "edition_number": edition,
        "title": result.get("title", f"Edition #{edition}"),
        "title_impact": title_impact,
        "content_markdown": result.get("content_markdown", ""),
        "content_markdown_impact": content_markdown_impact,
        "content_telegram": result.get("content_telegram", ""),
        "data_snapshot": input_data,
        "primary_theme": primary_theme,
        "status": "draft",
    }
    try:
        supabase.table("newsletters").insert(row).execute()
        logger.info(f"Saved newsletter edition #{edition} to Supabase (status=draft, theme='{primary_theme}')")
    except Exception as e:
        logger.error(f"Failed to insert newsletter #{edition} into Supabase: {e}")

    # Save local markdown (builder version)
    md_file = NEWSLETTERS_DIR / f"brief_{edition}_{date_str}.md"
    try:
        md_file.write_text(result.get("content_markdown", ""))
        logger.info(f"Saved local file: {md_file.name}")
    except OSError as e:
        logger.error(f"Failed to write newsletter file {md_file}: {e}")

    # Save local markdown (impact version)
    if content_markdown_impact:
        impact_file = NEWSLETTERS_DIR / f"brief_{edition}_{date_str}_impact.md"
        try:
            impact_file.write_text(content_markdown_impact)
            logger.info(f"Saved impact file: {impact_file.name}")
        except OSError as e:
            logger.error(f"Failed to write impact file {impact_file}: {e}")


# ---------------------------------------------------------------------------
# Negotiation request handling
# ---------------------------------------------------------------------------

def handle_negotiation_request(result: dict, task_id: str):
    """If the Newsletter agent requests enrichment, create the negotiation and task."""
    if not supabase:
        return

    negotiation_req = result.get("negotiation_request")
    if not negotiation_req:
        return
    if not isinstance(negotiation_req, dict):
        logger.warning(f"negotiation_request is not a dict (got {type(negotiation_req).__name__}) — skipping")
        return

    target_agent = negotiation_req.get("target_agent", "analyst")
    request_summary = negotiation_req.get("request", "")
    quality_criteria = negotiation_req.get("min_quality", "")
    needed_by = negotiation_req.get("needed_by")
    enrichment_task_type = negotiation_req.get("task_type", "enrich_for_newsletter")
    enrichment_input = negotiation_req.get("input_data", {})

    try:
        # Create the negotiation record via the processor task type
        neg_result = supabase.table("agent_tasks").insert({
            "task_type": "create_negotiation",
            "assigned_to": "processor",
            "created_by": AGENT_NAME,
            "priority": 2,
            "input_data": {
                "requesting_agent": AGENT_NAME,
                "responding_agent": target_agent,
                "request_task_id": task_id,
                "request_summary": request_summary,
                "quality_criteria": quality_criteria,
                "needed_by": needed_by,
            },
        }).execute()
        logger.info(f"Created create_negotiation task for {AGENT_NAME} → {target_agent}")

        # Create the enrichment task for the target agent
        supabase.table("agent_tasks").insert({
            "task_type": enrichment_task_type,
            "assigned_to": target_agent,
            "created_by": AGENT_NAME,
            "priority": 2,
            "input_data": {
                **enrichment_input,
                "negotiation_request": {
                    "requesting_agent": AGENT_NAME,
                    "request_summary": request_summary,
                    "quality_criteria": quality_criteria,
                    "needed_by": needed_by,
                },
            },
        }).execute()
        logger.info(f"Created {enrichment_task_type} task for {target_agent}")

    except Exception as e:
        logger.error(f"Failed to handle negotiation request: {e}")


# ---------------------------------------------------------------------------
# Scorecard — "Looking Back" blurb generation
# ---------------------------------------------------------------------------

LOOKBACK_PROMPT = """You are writing a brief lookback for the AgentPulse newsletter. Be honest and direct. No defensive language. If the prediction was wrong, say so plainly. If right, state it without gloating. Keep it to 3-4 sentences maximum.

Original thesis: "{thesis}"
Our prediction (Issue #{issue_number}): "{prediction_text}"
What actually happened: "{resolution_notes}"
Assessment: {status}

Write the lookback blurb. Start with "In Issue #{issue_number}, we predicted..." or similar. End with an honest one-sentence assessment of what we got right and wrong. Output ONLY the blurb text, no JSON, no formatting."""

MAX_LOOKBACKS_PER_ISSUE = 2


def generate_scorecard(current_issue_number: int) -> list[str]:
    """Fetch resolved predictions and generate Looking Back blurbs. Returns list of blurb strings."""
    try:
        resolved = supabase.table("predictions")\
            .select("*, spotlight_history(*)")\
            .in_("status", ["confirmed", "refuted", "partially_correct"])\
            .is_("scorecard_issue", "null")\
            .order("resolved_at", desc=True)\
            .limit(MAX_LOOKBACKS_PER_ISSUE)\
            .execute()
    except Exception as e:
        logger.error(f"Failed to fetch resolved predictions for scorecard: {e}")
        return []

    if not resolved.data:
        logger.info("No resolved predictions — skipping Scorecard")
        return []

    logger.info(f"Generating scorecard for {len(resolved.data)} resolved predictions")
    blurbs = []

    for prediction in resolved.data:
        pred_id = prediction.get("id", "")
        pred_text = prediction.get("prediction_text", "")
        issue_num = prediction.get("issue_number", "?")
        status = prediction.get("status", "unknown")
        resolution_notes = prediction.get("resolution_notes", "No details available.")

        spotlight = prediction.get("spotlight_history") or {}
        thesis = spotlight.get("thesis", pred_text)

        blurb = generate_lookback_blurb(
            thesis=thesis,
            prediction_text=pred_text,
            issue_number=issue_num,
            resolution_notes=resolution_notes,
            status=status,
        )

        if blurb:
            blurbs.append(blurb)
            try:
                supabase.table("predictions").update({
                    "scorecard_issue": current_issue_number,
                }).eq("id", pred_id).execute()
                logger.info(f"Marked prediction {pred_id[:8]} as included in scorecard (issue {current_issue_number})")
            except Exception as e:
                logger.error(f"Failed to mark prediction {pred_id[:8]} scorecard_issue: {e}")

    return blurbs


def generate_lookback_blurb(thesis: str, prediction_text: str, issue_number, resolution_notes: str, status: str) -> str | None:
    """Generate a single Looking Back blurb via LLM."""
    prompt = LOOKBACK_PROMPT.format(
        thesis=thesis,
        issue_number=issue_number,
        prediction_text=prediction_text,
        resolution_notes=resolution_notes,
        status=status,
    )

    try:
        _t0 = time.time()
        response = routed_llm_call(
            MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.4,
        )
        log_llm_call("newsletter", "lookback_blurb", response.model, response.usage, int((time.time() - _t0) * 1000))

        blurb = response.choices[0].message.content.strip()

        if blurb.startswith('"') and blurb.endswith('"'):
            blurb = blurb[1:-1]

        tokens = response.usage.total_tokens if response.usage else 0
        logger.info(f"Lookback blurb generated ({tokens} tokens): {blurb[:60]}...")
        return blurb

    except Exception as e:
        logger.error(f"Failed to generate lookback blurb for issue #{issue_number}: {e}")
        return None


def format_scorecard_section(blurbs: list[str]) -> str:
    """Format scorecard blurbs into the Looking Back newsletter section."""
    if not blurbs:
        return ""

    parts = ["\n\n---\n\n## Looking Back\n"]
    for blurb in blurbs:
        parts.append(f"\n{blurb}\n")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------

def _load_pricing() -> dict:
    """Load pricing config from agentpulse-config.json."""
    config_path = Path(OPENCLAW_DATA_DIR) / "config" / "agentpulse-config.json"
    try:
        if config_path.exists():
            with open(config_path) as f:
                pricing = json.load(f).get("pricing", {})
                return pricing
        else:
            logger.warning(f"[ROUTING] Config file not found at {config_path} — provider lookup will default to openai")
    except Exception as e:
        logger.warning(f"[ROUTING] Failed to load pricing config: {e}")
    return {}


def _load_wallet_pricing() -> dict:
    """Load wallet pricing config from agentpulse-config.json."""
    config_path = Path(OPENCLAW_DATA_DIR) / "config" / "agentpulse-config.json"
    try:
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f).get("wallet_pricing", {})
    except Exception:
        pass
    return {}


def log_llm_call(agent_name, task_type, model, usage, duration_ms=0):
    """Log an LLM call with token counts and estimated cost."""
    try:
        pricing = _load_pricing().get(model, {})
        input_tok = getattr(usage, 'input_tokens', 0) or getattr(usage, 'prompt_tokens', 0) or 0
        output_tok = getattr(usage, 'output_tokens', 0) or getattr(usage, 'completion_tokens', 0) or 0
        total_tok = input_tok + output_tok
        cost = (input_tok * pricing.get("input", 0) + output_tok * pricing.get("output", 0)) / 1_000_000

        supabase.table("llm_call_log").insert({
            "agent_name": agent_name,
            "task_type": task_type,
            "model": model,
            "provider": pricing.get("provider", "unknown"),
            "input_tokens": input_tok,
            "output_tokens": output_tok,
            "total_tokens": total_tok,
            "estimated_cost": round(cost, 6),
            "duration_ms": duration_ms,
        }).execute()

    except Exception as e:
        logger.warning(f"Failed to log LLM call: {e}")


DEEPSEEK_MAX_TOKENS = 8192  # DeepSeek API hard limit


def routed_llm_call(model, messages, **kwargs):
    """Route LLM call to correct provider. DeepSeek falls back to OpenAI."""
    pricing = _load_pricing()
    provider = pricing.get(model, {}).get("provider", "openai")
    logger.info(f"[ROUTING] model={model} provider={provider} deepseek_client={'yes' if deepseek_client else 'NO'}")
    if provider == "deepseek":
        # Clamp max_tokens to DeepSeek's limit
        if "max_tokens" in kwargs and kwargs["max_tokens"] > DEEPSEEK_MAX_TOKENS:
            logger.info(f"[ROUTING] Clamping max_tokens {kwargs['max_tokens']} → {DEEPSEEK_MAX_TOKENS} for DeepSeek")
            kwargs["max_tokens"] = DEEPSEEK_MAX_TOKENS
        if deepseek_client:
            try:
                resp = deepseek_client.chat.completions.create(model=model, messages=messages, **kwargs)
                logger.info(f"[ROUTING] DeepSeek call succeeded — model used: {resp.model}")
                return resp
            except Exception as e:
                logger.warning(f"[ROUTING] DeepSeek call FAILED: {e} — falling back to gpt-4o-mini")
                return client.chat.completions.create(model="gpt-4o-mini", messages=messages, **kwargs)
        else:
            logger.warning(f"[ROUTING] DeepSeek client is None — falling back {model} → gpt-4o-mini")
            return client.chat.completions.create(model="gpt-4o-mini", messages=messages, **kwargs)
    return client.chat.completions.create(model=model, messages=messages, **kwargs)


# ---------------------------------------------------------------------------
# Task processing
# ---------------------------------------------------------------------------

def get_budget_config(agent_name: str, task_type: str) -> dict:
    """Read budget limits for a given agent + task type from agentpulse-config.json."""
    defaults = {
        "max_llm_calls": 8,
        "max_seconds": 300,
        "max_subtasks": 2,
        "max_retries": 2,
    }

    config_path = Path(OPENCLAW_DATA_DIR) / "config" / "agentpulse-config.json"
    try:
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
        else:
            return defaults
    except Exception:
        return defaults

    budgets = config.get("budgets", {})
    task_budget = budgets.get(agent_name, {}).get(task_type, {})
    return {k: task_budget.get(k, defaults[k]) for k in defaults}


def process_task(task: dict):
    """Process a single newsletter task."""
    task_id = task["id"]
    task_type = task.get("task_type", "unknown")
    input_data = task.get("input_data", {}) or {}

    logger.info(f"Processing task {task_id}: {task_type}")

    # Task is already in_progress — claimed atomically by fetch_pending_tasks()

    supported = {"write_newsletter", "revise_newsletter"}
    if task_type not in supported:
        error = f"Unknown task type: {task_type}"
        logger.error(error)
        mark_task_status(
            task_id,
            "failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=error,
        )
        return

    # Validate input schema (fail fast on malformed input)
    try:
        validate_task_input(task_type, input_data)
    except ValidationError as e:
        error = f"Input validation: {e}"
        logger.error(error)
        mark_task_status(
            task_id, "failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=error,
        )
        return

    # Inject budget constraints
    budget = get_budget_config(AGENT_NAME, task_type)
    input_data["budget"] = budget
    logger.info(f"Budget for {task_type}: {budget}")

    try:
        # Editorial pre-pass: choose this week's angle
        if task_type == 'write_newsletter':
            editorial_brief = editorial_prepass(input_data)
            if editorial_brief:
                input_data['editorial_direction'] = editorial_brief

        # Generate newsletter
        raw_result = generate_newsletter(task_type, input_data, budget)
        validated = validate_llm_output(raw_result, NewsletterOutput)
        result = validated.model_dump()

        # ── Post-generation quality checks ──
        quality_issues = run_quality_checks(result, input_data)
        critical_issues = [i for i in quality_issues if i["severity"] == "critical"]
        warning_issues = [i for i in quality_issues if i["severity"] == "warning"]

        if critical_issues:
            logger.warning(
                f"Newsletter has {len(critical_issues)} critical quality issue(s): "
                f"{critical_issues}"
            )
            retries = budget.get('max_retries', 2)
            if retries > 0:
                logger.info("Retrying newsletter generation due to critical quality issues...")
                input_data['_quality_feedback'] = [i["detail"] for i in critical_issues]
                budget['max_retries'] = retries - 1
                raw_result = generate_newsletter(task_type, input_data, budget)
                validated = validate_llm_output(raw_result, NewsletterOutput)
                result = validated.model_dump()
                quality_issues = run_quality_checks(result, input_data)
                critical_issues = [i for i in quality_issues if i["severity"] == "critical"]
                warning_issues = [i for i in quality_issues if i["severity"] == "warning"]
                if critical_issues:
                    logger.warning(f"Critical issues persist after retry: {critical_issues}")

        if warning_issues:
            logger.info(f"Newsletter quality warnings: {warning_issues}")

        # Auto-fix: strip duplicate stats where possible
        result = _auto_fix_stat_repetition(result)

        # Auto-fix: strip sections that only contain "N/A" or are empty
        result = _auto_fix_empty_sections(result)

        # Store quality warnings in result
        all_warnings = [i["detail"] for i in quality_issues]
        if all_warnings:
            result["quality_warnings"] = all_warnings

        # Qualitative review pass — LLM checks for fabrication, tone, grounding
        if result.get('content_markdown') and claude_client:
            try:
                review = qualitative_review(result['content_markdown'], input_data)
                if review:
                    hard_fails = [r for r in review if r.get('severity') == 'critical']
                    soft_warns = [r for r in review if r.get('severity') == 'warning']
                    if hard_fails:
                        logger.warning(f"[QUAL REVIEW] {len(hard_fails)} critical issue(s): {hard_fails}")
                        retries_left = budget.get('max_retries', 0)
                        if retries_left > 0:
                            logger.info("[QUAL REVIEW] Retrying due to critical qualitative issues...")
                            input_data['_quality_feedback'] = [r['detail'] for r in hard_fails]
                            budget['max_retries'] = retries_left - 1
                            raw_result = generate_newsletter(task_type, input_data, budget)
                            validated = validate_llm_output(raw_result, NewsletterOutput)
                            result = validated.model_dump()
                            result = _auto_fix_stat_repetition(result)
                            result = _auto_fix_empty_sections(result)
                    if soft_warns:
                        logger.info(f"[QUAL REVIEW] {len(soft_warns)} warning(s): {soft_warns}")
                        existing = result.get("quality_warnings", [])
                        result["quality_warnings"] = existing + [r['detail'] for r in soft_warns]
            except Exception as e:
                logger.error(f"[QUAL REVIEW] Review failed (non-blocking): {e}")

        # Strategic editor second pass
        if result.get("content_markdown_impact"):
            try:
                edited_impact = edit_strategic_mode(result["content_markdown_impact"], input_data)
                result["content_markdown_impact"] = edited_impact
                logger.info("Strategic editor pass applied to content_markdown_impact")
            except Exception as e:
                logger.error(f"Strategic editor pass failed, using original: {e}")

        # ── Impact edition quality checks (log-only) ──
        impact_content = result.get("content_markdown_impact", "")
        if impact_content:
            # Check narrative continuity bridge
            continuity_phrases = ["last week", "last edition", "previously", "edition #", "editions ago"]
            has_continuity = any(p in impact_content.lower() for p in continuity_phrases)
            if not has_continuity:
                logger.warning("QUALITY: Missing narrative continuity bridge in impact edition")
            else:
                logger.info("QUALITY: Narrative continuity bridge detected")

            # Check bold inline markers (**Text.**)
            bold_marker_count = len(re.findall(r'\*\*[A-Z][^*]{3,60}\.\*\*', impact_content))
            if bold_marker_count < 2:
                logger.warning(f"QUALITY: Missing bold inline markers in impact edition (found {bold_marker_count}, need ≥2)")
            else:
                logger.info(f"QUALITY: Found {bold_marker_count} bold inline markers")
        elif input_data.get('narrative_context'):
            logger.warning("QUALITY: content_markdown_impact is empty — impact edition not generated")

        # Generate scorecard (Looking Back) if resolved predictions exist
        edition = result.get("edition", input_data.get("edition_number", 0))
        try:
            scorecard_blurbs = generate_scorecard(edition)
            if scorecard_blurbs:
                scorecard_md = format_scorecard_section(scorecard_blurbs)
                if result.get("content_markdown"):
                    result["content_markdown"] += scorecard_md
                if result.get("content_markdown_impact"):
                    result["content_markdown_impact"] += scorecard_md
                if result.get("content_telegram"):
                    result["content_telegram"] += scorecard_md
                logger.info(f"Appended {len(scorecard_blurbs)} Looking Back blurb(s) to newsletter")
        except Exception as e:
            logger.error(f"Scorecard generation failed (non-blocking): {e}")

        # Save to Supabase + local file
        save_newsletter(result, input_data)

        # Handle negotiation requests (e.g. enrichment from Analyst)
        handle_negotiation_request(result, task_id)

        # Mark task completed
        mark_task_status(
            task_id,
            "completed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            output_data=result,
        )
        logger.info(f"Task {task_id} completed successfully")

    except json.JSONDecodeError as e:
        error = f"Failed to parse model response as JSON: {e}"
        logger.error(error)
        mark_task_status(
            task_id,
            "failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=error,
        )
    except Exception as e:
        error = f"Unexpected error: {e}"
        logger.error(error)
        mark_task_status(
            task_id,
            "failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=str(e),
        )


def main():
    ensure_dirs()
    if not init():
        logger.error("Initialization failed — exiting")
        return

    logger.info(f"Newsletter agent started (model={MODEL}, poll={POLL_INTERVAL}s)")

    identity_text = load_identity(AGENT_DIR)
    logger.info(f"Identity loaded from {AGENT_DIR}: {len(identity_text)} chars")
    skill_text = load_skill(SKILL_DIR)
    logger.info(f"Skill loaded from {SKILL_DIR}: {len(skill_text)} chars")

    while True:
        try:
            tasks = fetch_pending_tasks()
            for task in tasks:
                process_task(task)
        except Exception as e:
            logger.error(f"Poll loop error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
