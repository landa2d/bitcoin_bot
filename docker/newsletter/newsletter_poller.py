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

from dotenv import load_dotenv
from pydantic import ValidationError
from supabase import create_client, Client
from openai import OpenAI

from schemas import TASK_INPUT_SCHEMAS, NewsletterOutput

load_dotenv()

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
AGENT_NAME = os.getenv("AGENT_NAME", "newsletter")
OPENCLAW_DATA_DIR = os.getenv("OPENCLAW_DATA_DIR", "/home/openclaw/.openclaw")
POLL_INTERVAL = int(os.getenv("NEWSLETTER_POLL_INTERVAL", "30"))
MODEL = os.getenv("NEWSLETTER_MODEL", "gpt-4o")

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

# ---------------------------------------------------------------------------
# Identity + Skill loading (from disk, with mtime caching)
# ---------------------------------------------------------------------------

AGENT_DIR = Path(OPENCLAW_DATA_DIR) / "agents" / "newsletter" / "agent"
SKILL_DIR = Path(OPENCLAW_DATA_DIR) / "skills" / "newsletter"

_identity_cache: str | None = None
_identity_mtime: float = 0

_skill_cache: str | None = None
_skill_mtime: float = 0


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


def init():
    global supabase, client, deepseek_client
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Supabase not configured (SUPABASE_URL / SUPABASE_KEY missing)")
        return False
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set — cannot generate newsletters")
        return False
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    client = OpenAI(api_key=OPENAI_API_KEY)
    if DEEPSEEK_API_KEY:
        deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        logger.info("DeepSeek client initialized")
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
    """Issue #2: Check that Spotlight and Big Insight don't echo each other."""
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


def run_quality_checks(result: dict, input_data: dict) -> list[dict]:
    """Run all post-generation quality checks. Returns list of issues."""
    content = result.get('content_markdown', '')
    if not content:
        return [{"severity": "critical", "issue": "empty_content",
                 "section": "Newsletter", "detail": "No content_markdown"}]

    all_issues: list[dict] = []
    all_issues.extend(validate_stat_repetition(content))
    all_issues.extend(validate_section_echo(content))
    all_issues.extend(validate_stale_predictions(content, input_data))
    all_issues.extend(validate_prediction_format(content))
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


def mark_task_status(task_id: str, status: str, **fields):
    payload = {"status": status, **fields}
    supabase.table("agent_tasks").update(payload).eq("id", task_id).execute()


def generate_newsletter(task_type: str, input_data: dict, budget_config: dict) -> dict:
    """Call OpenAI with identity + skill as system prompt, task + data as user message."""

    identity = load_identity(AGENT_DIR)
    skill = load_skill(SKILL_DIR)

    system_prompt = f"{identity}\n\n---\n\nSKILL REFERENCE:\n{skill}"
    system_prompt += (
        "\n\nYou MUST respond with valid JSON only — no markdown fences, no extra text."
        "\n\nCRITICAL RULES — CHECK BEFORE WRITING EACH SECTION:"
        "\n1. SPOTLIGHT: If `spotlight` is null OR missing from input_data, OMIT the"
        " ENTIRE section — no header, no placeholder, no explanation. Go straight from"
        " Cold open / One Number to The Big Insight."
        "\n2. ON OUR RADAR: If `radar_topics` has fewer than 3 items, OMIT the ENTIRE"
        " section — no header, no 'nothing to report' note."
        "\n3. SECTION ORDER: Write every required section in order and complete it before"
        " moving on. Required every edition: Cold open, The Big Insight, Top Opportunities,"
        " Emerging Signals, Tool Radar, Prediction Tracker, Gato's Corner."
        " Conditional (include only when data supports): One Number, Spotlight,"
        " On Our Radar, The Curious Corner, Who's Moving."
        " NEVER stop before Gato's Corner — it is the last section and mandatory."
        "\n4. THE BIG INSIGHT: Use a descriptive headline (e.g. `## The Agent Memory"
        " Market Is About to Consolidate`), not the literal text '## The Big Insight'."
        " The first body line MUST be the thesis in **bold markdown**. Thesis must be"
        " falsifiable — a claim that could be wrong, not a vague observation."
        "\n5. GATO'S CORNER: ALWAYS write this. NEVER omit it."
        " A newsletter without Gato's Corner is a failed newsletter."
        "\n6. SPOTLIGHT WORD COUNT: If Spotlight IS present, body MUST be 400–500 words."
        " Under 350 is a hard failure — STOP and expand before continuing."
        "\n7. ONE NUMBER: Include as `## One Number` only if a striking, real data point"
        " exists in input_data. NEVER fabricate. Skip entirely if nothing is remarkable."
        "\n8. WHO'S MOVING: Include `## Who's Moving` only if at least 1 real entry can"
        " be sourced from analyst_insights, clusters, or trending_tools. Skip if not."
        "\n9. NO PLACEHOLDER TEXT: Never write 'Watch for...', 'investigation underway',"
        " or any trailing incomplete sentence. Complete every entry or cut the section."
        "\n10. FILLER PHRASES BANNED: 'navigating without a map', 'wake-up call',"
        " 'smart businesses are already', 'sifting through the narrative', 'elevated"
        " urgency', 'in today's rapidly evolving', 'it remains to be seen'."
        " Write like a reporter, not a business deck."
        "\n11. ONE NUMBER REPETITION: The One Number stat appears with its full figure"
        " ONCE in the One Number section. Later sections reference it by description"
        " only ('the incident spike', 'the cost figure above'), NEVER re-quote the"
        " exact number."
        "\n12. SPOTLIGHT vs BIG INSIGHT: Before writing Big Insight, state what"
        " Spotlight already covered. Then choose a DIFFERENT angle: second-order"
        " effects, security implications, business model impact, supply chain"
        " consequences, regulatory risk, or a contrarian take."
        "\n13. JARGON GROUNDING: Every technical concept must be grounded on first"
        " use: name it, explain it in one sentence, then give a specific real-world"
        " scenario. Write for a smart founder, not an AI engineer."
        "\n14. STALE PREDICTIONS: Check input_data for stale_prediction_ids. Any"
        " prediction whose target_date has passed MUST be resolved as ✅ Confirmed,"
        " ❌ Wrong, or 🔄 Revised — with honest explanation. NEVER publish a"
        " past-due prediction as Active or Developing."
        "\n15. PREDICTION FORMAT: Every new prediction must follow: 'By [specific"
        " date], [specific measurable outcome].' Target dates must be at least 4"
        " weeks in the future FROM TODAY'S DATE (shown in user message). NEVER"
        " use dates in the past. Check TODAY'S DATE before writing any prediction."
        "\n16. GATO'S CORNER STRUCTURE: (1) Reference the week's main theme,"
        " (2) draw a genuine parallel to Bitcoin/decentralization that feels earned,"
        " (3) deliver an actionable insight. End with 'Stay humble, stack sats.'"
    )

    # Inject quality feedback on retry
    quality_feedback = input_data.pop('_quality_feedback', None)
    if quality_feedback:
        system_prompt += (
            "\n\nQUALITY ISSUES FROM PREVIOUS ATTEMPT — FIX THESE:"
            + "".join(f"\n- {issue}" for issue in quality_feedback)
        )

    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    user_msg = (
        f"TODAY'S DATE: {today}\n\n"
        f"TASK TYPE: {task_type}\n\n"
        f"BUDGET: {json.dumps(budget_config)}\n\n"
        f"INPUT DATA:\n{json.dumps(input_data, indent=2, default=str)}"
    )

    logger.info(f"Calling {MODEL} for {task_type}...")

    _t0 = time.time()
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


def save_newsletter(result: dict, input_data: dict):
    """Save newsletter to Supabase and local file."""
    edition = result.get("edition", input_data.get("edition_number", 0))
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Upsert into newsletters table
    row = {
        "edition_number": edition,
        "title": result.get("title", f"Edition #{edition}"),
        "content_markdown": result.get("content_markdown", ""),
        "content_telegram": result.get("content_telegram", ""),
        "data_snapshot": input_data,
        "status": "draft",
    }
    try:
        supabase.table("newsletters").insert(row).execute()
        logger.info(f"Saved newsletter edition #{edition} to Supabase (status=draft)")
    except Exception as e:
        logger.error(f"Failed to insert newsletter #{edition} into Supabase: {e}")

    # Save local markdown
    md_file = NEWSLETTERS_DIR / f"brief_{edition}_{date_str}.md"
    try:
        md_file.write_text(result.get("content_markdown", ""))
        logger.info(f"Saved local file: {md_file.name}")
    except OSError as e:
        logger.error(f"Failed to write newsletter file {md_file}: {e}")


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
                return json.load(f).get("pricing", {})
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


def routed_llm_call(model, messages, **kwargs):
    """Route LLM call to correct provider. DeepSeek falls back to OpenAI."""
    provider = _load_pricing().get(model, {}).get("provider", "openai")
    if provider == "deepseek" and deepseek_client:
        try:
            return deepseek_client.chat.completions.create(model=model, messages=messages, **kwargs)
        except Exception as e:
            logger.warning(f"DeepSeek failed: {e} — falling back to OpenAI")
            return client.chat.completions.create(model="gpt-4o", messages=messages, **kwargs)
    return client.chat.completions.create(model=model, messages=messages, **kwargs)


# ---------------------------------------------------------------------------
# Task processing
# ---------------------------------------------------------------------------

def get_budget_config(agent_name: str, task_type: str) -> dict:
    """Read budget limits for a given agent + task type from agentpulse-config.json."""
    defaults = {
        "max_llm_calls": 6,
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
        # Generate newsletter via OpenAI
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

        # Store quality warnings in result
        all_warnings = [i["detail"] for i in quality_issues]
        if all_warnings:
            result["quality_warnings"] = all_warnings

        # Generate scorecard (Looking Back) if resolved predictions exist
        edition = result.get("edition", input_data.get("edition_number", 0))
        try:
            scorecard_blurbs = generate_scorecard(edition)
            if scorecard_blurbs:
                scorecard_md = format_scorecard_section(scorecard_blurbs)
                if result.get("content_markdown"):
                    result["content_markdown"] += scorecard_md
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
