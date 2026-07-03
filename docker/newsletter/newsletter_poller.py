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

# `anthropic` is only needed at runtime when actually instantiating the Claude
# client (see init_clients). Import it softly so the module — and pure helpers
# like normalize_apostrophe_corruption — can be imported for testing in
# environments where the SDK is not installed (it IS installed in the production
# Docker image). A hard top-level import would otherwise block the QUOTE-02
# regression test from importing the real fixed function.
try:
    import anthropic
except ModuleNotFoundError:  # pragma: no cover - production always has it
    anthropic = None

from schemas import TASK_INPUT_SCHEMAS, NewsletterOutput

load_dotenv()


def require_env(names):
    """Fail loud on missing env. Each element may be 'A|B' alternatives (any non-empty satisfies)."""
    missing = [n for n in names if not any(os.getenv(alt) for alt in n.split('|'))]
    if missing:
        raise RuntimeError(f"missing required env: {', '.join(missing)}")


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
MODEL = os.getenv("NEWSLETTER_MODEL", "claude-sonnet-4-6")
STRATEGIC_MODEL = os.getenv("NEWSLETTER_STRATEGIC_MODEL", "claude-sonnet-4-6")
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
claude_client: "anthropic.Anthropic | None" = None  # str annotation: anthropic may be unimported in test env

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
    if anthropic is None:
        # Fail loud — at runtime the SDK must be present; never silently skip.
        raise RuntimeError(
            "anthropic SDK is not installed but init_clients() needs it for the "
            "strategic editor pass. Install it in the service image."
        )
    claude_client = anthropic.Anthropic(
        api_key=OPENAI_API_KEY,  # Proxy uses the agent's ap_ key
        base_url=f"{LLM_PROXY_URL}/anthropic",
    )
    logger.info(f"[INIT] Claude client initialized (proxy: {LLM_PROXY_URL}/anthropic, model: {STRATEGIC_MODEL})")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Phase 30 — pre-publish eval orchestration helpers (Plan 30-02).
#
# These are the "dumb sequencer" support surface for `run_edition_eval`: read the config
# gate, build the GOVERNED `edition_eval` identity client, alert the operator loudly on an
# eval outage, and fetch the FULL prior published edition for the gate's cross-edition
# mechanical checks. NO status flip / do_not_publish action lives here — that is Plan 30-03.
# ─────────────────────────────────────────────────────────────────────────────


def _read_edition_eval_config() -> dict:
    """Read the `edition_eval` block from agentpulse-config.json (D-15).

    Mirrors the existing block_pipeline config-read idiom (process_task, ~:2396-2400), swapping
    the block key. Callers read `.get('enabled', False)` (gates INVOCATION — rollback-safe) and
    `.get('enforce', False)` (gates the status flip — report-only) off the returned dict; the whole
    block is passed to `run_layer2`'s `config` arg. Returns {} when the file or block is absent
    (fail-safe: an absent block reads as enabled=False, so the eval simply never runs)."""
    try:
        cfg_path = Path(OPENCLAW_DATA_DIR) / "config" / "agentpulse-config.json"
        if cfg_path.exists():
            return json.loads(cfg_path.read_text()).get("edition_eval", {}) or {}
    except Exception as e:
        logger.warning(f"[EVAL] could not read edition_eval config (non-fatal): {e}")
    return {}


def _build_eval_llm_client():
    """Construct a NEW anthropic client authenticating as the GOVERNED `edition_eval` identity
    (GOV-01), or return None when the eval key is unset (the D-07 outage case).

    THE signature landmine: `run_layer2` requires an `llm_client` on the `edition_eval` wallet,
    NEVER the newsletter service's own module Claude client. Reusing that client would attribute
    eval spend to the newsletter wallet and defeat the governed-budget design. The key is read fresh
    via `edition_eval._get_eval_api_key()` (LLM_PROXY_EVAL_KEY) and passed ONLY to
    `anthropic.Anthropic(api_key=...)` — it is NEVER logged (we log a boolean only) and never lands
    in a DB row or the flags object (T-30-KEY). When the operator has not yet minted the key, return
    None — the caller treats that as an outage (error row + loud alert), NOT a fallback to the
    newsletter identity."""
    from edition_eval import _get_eval_api_key  # lazy, mirrors `from verification import verify_draft`

    eval_key = _get_eval_api_key()
    if not eval_key:
        # Loud, key-free signal (D-07): the operator has not minted LLM_PROXY_EVAL_KEY yet. Log a
        # boolean-style fact ("unset"), NEVER the key; return None so the caller fails open-but-loud.
        logger.error(
            "[EVAL] eval key unset (LLM_PROXY_EVAL_KEY) — cannot build the governed edition_eval "
            "client; the eval will not run. NOT falling back to the newsletter identity."
        )
        return None
    if anthropic is None:
        # Fail loud — the SDK must be present at runtime to build the governed client.
        raise RuntimeError(
            "anthropic SDK is not installed but _build_eval_llm_client needs it to build the "
            "governed edition_eval client. Install it in the service image."
        )
    logger.info("[EVAL] governed edition_eval client built (proxy: %s/anthropic)", LLM_PROXY_URL)
    return anthropic.Anthropic(
        api_key=eval_key,                       # the GOVERNED edition_eval identity (NOT the newsletter key)
        base_url=f"{LLM_PROXY_URL}/anthropic",
    )


def _alert_operator(message: str) -> None:
    """Loud, non-silent operator alert from the newsletter service (D-07).

    Phase 30 INTERIM path: a direct httpx POST to Telegram (mirrors the processor's send_telegram
    shape). Phase 31 (SURF) hardens/centralizes this via the shared send_telegram. Unlike the
    processor's fail-SOFT send_telegram (silent `return` on unset env), this MUST fail LOUD: if
    either TELEGRAM env is unset we ERROR-log (never a bare return) so an eval outage can never
    vanish silently. `message` is operator-facing text the caller builds from labels/counts (edition
    number, verdict, category counts) — NEVER raw draft prose (log/injection hygiene, T-30-LOG); we
    still single-line + bound it defensively before sending. The eval key is NEVER included."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    owner = os.getenv("TELEGRAM_OWNER_ID")
    safe = " ".join(str(message).split())[:1000]  # single-line + bound (log/injection hygiene)
    if not token or not owner:
        # Fail LOUD (D-07): never a silent no-op. Log a LABEL only — never the eval key.
        logger.error(
            "[EVAL-ALERT] cannot alert operator — TELEGRAM_BOT_TOKEN/TELEGRAM_OWNER_ID unset; "
            "message=%s", safe,
        )
        return
    try:
        with httpx.Client(timeout=10) as hc:
            resp = hc.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={"chat_id": owner, "text": safe},
            )
            if resp.status_code != 200:
                logger.error(
                    "[EVAL-ALERT] Telegram send failed (%s): %s", resp.status_code, resp.text[:200]
                )
    except Exception:
        # Never swallow silently — a failed alert is itself surfaced loudly (exc_info, no key).
        logger.error("[EVAL-ALERT] operator alert send failed", exc_info=True)


def _fetch_prior_published_edition() -> dict | None:
    """Fetch the FULL latest PUBLISHED edition for the gate's cross-edition mechanical checks
    (GATE-07 recycled-closer + duplicated-stat), or None.

    Plain `.eq('status','published')` — NEVER the supabase-py in-list filter (the silent-failure
    rule). The gate needs the FULL prior body (both versions), NOT `load_edition_context`'s truncated
    excerpt (contract note A3). Fail-loud-but-not-fatal: on any error log a WARNING + return None (the
    gate treats None as a clean cross-edition skip and never raises)."""
    try:
        result = (
            supabase.table("newsletters")
            .select("content_markdown, content_markdown_impact, edition_number")
            .eq("status", "published")
            .order("published_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception as e:
        logger.warning(f"[EVAL] prior-published-edition fetch failed (non-fatal): {e}")
        return None


def _summarize_flags(flags) -> str:
    """Render a flags list as category-label counts (e.g. 'github_repo x2, url_dead x1') — NEVER
    raw draft prose (T-30-LOG). Used to build fabrication/mechanical `reason` text safely."""
    from collections import Counter
    counts: "Counter[str]" = Counter()
    for f in flags or []:
        if isinstance(f, dict):
            kind = f.get("kind") or f.get("type") or f.get("check") or "flag"
        else:
            kind = "flag"
        counts[str(kind)] += 1
    return ", ".join(f"{k} x{n}" for k, n in counts.items()) or "0"


def _dim_score(judge_scores: dict, dim: str):
    """The worst-body (min) numeric score for a judge dimension, or None. `judge_scores` is
    {version: {dim: {score, evidence, ...}}} — a failing dim scores lower on the offending body."""
    vals = []
    for version in ("technical", "impact"):
        entry = (judge_scores or {}).get(version, {})
        if isinstance(entry, dict):
            cell = entry.get(dim)
            if isinstance(cell, dict) and isinstance(cell.get("score"), (int, float)):
                vals.append(cell["score"])
    return min(vals) if vals else None


def _one_line_excerpt(text, limit: int = 240) -> str:
    """Single-line + length-bounded excerpt of judge-critique text (log-injection hygiene, T-30-LOG).
    Strips all newlines to one line and truncates; returns '' for empty/None."""
    if not text:
        return ""
    return " ".join(str(text).split())[:limit]


def _find_attempt(res: dict, selected):
    """Return the run_layer2 attempt row whose `attempt` == selected (the D-11 best attempt), or the
    last attempt as a defensive fallback, or None."""
    attempts = res.get("attempts") or []
    for a in attempts:
        if a.get("attempt") == selected:
            return a
    return attempts[-1] if attempts else None


def run_edition_eval(
    supabase, draft, fact_base, prior_context, prior_edition, *,
    pipeline_version, newsletter_id, edition, config, llm_client, http_client,
    github_token=None, suppress_alerts=False,
) -> dict:
    """Sequence Layer-1 gate → fabrication short-circuit → Layer-2 judge → verdict, persisting every
    layer/attempt to `edition_evals`; fail-open-but-loud (D-06/D-07). Returns
    `{verdict, reason, details, ran}`.

    This is the single, testable eval-invocation unit; Plan 30-03 only calls it and acts on the
    returned verdict. It NEVER flips newsletter status / do-not-publish state (that is 30-03) and
    NEVER re-raises — an eval error must not block generation; the draft still reaches the Monday
    human gate. The SAME injected `http_client` reaches BOTH eval modules (D-08 live re-check), and
    `llm_client` is the GOVERNED `edition_eval` identity the caller built (GOV-01).
    `suppress_alerts=True` (the telemetry-only block_v1 shadow-row call, D-14) keeps the error /
    telemetry rows but silences operator pages so one edition is never double-paged (WR-03)."""
    try:
        # Lazy seam imports live INSIDE the try so an ImportError in any eval module is caught by
        # the fail-open handler below (the unit NEVER re-raises — WR-01), not propagated to callers.
        from deterministic_gate import run_deterministic_gate
        from judge_loop import run_layer2, _persistable_attempt
        from edition_eval import write_eval_row

        # (a) Outage (D-07): the operator has not minted the governed edition_eval key, so the caller
        # handed llm_client=None. Write a fail-loud error row, alert loudly, and return WITHOUT
        # running the gate/judge — never a silent skip, never a fallback to the newsletter identity.
        if llm_client is None:
            write_eval_row(
                supabase, newsletter_id=newsletter_id, edition_number=edition,
                pipeline_version=pipeline_version, attempt=0, layer="deterministic",
                eval_status="error",
                error="LLM_PROXY_EVAL_KEY unset — eval did not run",
            )
            if not suppress_alerts:
                _alert_operator(f"eval did not run for edition #{edition}: eval key unset")
            return {"verdict": "escalated", "reason": "eval key unset", "details": {}, "ran": False}

        # (b) Layer 1 — the no-LLM deterministic gate, with the live network re-check active (D-08:
        # the SAME injected http_client reaches both the gate and, below, the judge).
        det = run_deterministic_gate(
            draft, fact_base, prior_edition,
            http_client=http_client, github_token=github_token,
        )

        # (c) Fabrication short-circuit (D-09): a non-empty fabrication list is a HARD hold — Layer 2
        # NEVER runs (run_layer2 would ValueError on it anyway). Reason from category labels + counts,
        # NEVER raw draft prose (T-30-LOG).
        if det.get("fabrication"):
            reason = f"held_fabrication: {_summarize_flags(det['fabrication'])}"
            write_eval_row(
                supabase, newsletter_id=newsletter_id, edition_number=edition,
                pipeline_version=pipeline_version, attempt=0, layer="deterministic",
                eval_status="ok", verdict="held_fabrication", deterministic_flags=det,
            )
            return {"verdict": "held_fabrication", "reason": reason,
                    "details": {"det": det}, "ran": True}

        # (d) Layer-1 clean → write the clean deterministic row ('passed' here == "Layer-1 clean"),
        # then run Layer 2 with the GOVERNED client + the SAME injected http_client (D-08).
        write_eval_row(
            supabase, newsletter_id=newsletter_id, edition_number=edition,
            pipeline_version=pipeline_version, attempt=0, layer="deterministic",
            eval_status="ok", verdict="passed", deterministic_flags=det,
        )
        res = run_layer2(
            draft, fact_base, prior_context, det, config, llm_client,
            http_client=http_client, github_token=github_token,
        )

        # (e) Persist EVERY judge attempt (LOOP-03/D-14 telemetry) — the documented 1:1 mapping via
        # _persistable_attempt (reverify_flags→deterministic_flags, feedback→judge_feedback, etc.),
        # respecting verdict-iff-ok (an 'ok' attempt carries res['verdict']; an 'error' attempt
        # carries verdict=None + its own error).
        for a in res.get("attempts", []):
            p = _persistable_attempt(a)
            write_eval_row(
                supabase, newsletter_id=newsletter_id, edition_number=edition,
                pipeline_version=pipeline_version, attempt=p["attempt"], layer="judge",
                eval_status=p["eval_status"],
                verdict=(res["verdict"] if p["eval_status"] == "ok" else None),
                error=p.get("error"),
                deterministic_flags=p.get("reverify_flags") or {},
                judge_scores=p.get("judge_scores") or {},
                judge_feedback=p.get("feedback"),
                sats_spent=p.get("sats", 0),
                model_calls=p.get("model_calls") or [],
            )

        # (f) Build the verdict object. For held_voice (WIRE-03/D-10) the reason MUST carry each
        # failing judge dimension's NAME + its per-dimension SCORE + a bounded one-line judge_feedback
        # excerpt (sourced from the selected attempt's judge_scores + feedback) — labels-only would
        # UNDER-deliver WIRE-03's "final per-dimension scores + feedback". `details` carries the full
        # per-dimension judge_scores dict from the selected attempt. Feedback is the judge's OWN
        # critique output (NOT raw draft prose) — still single-lined + bounded (log-injection hygiene).
        verdict = res["verdict"]
        sel = _find_attempt(res, res.get("selected_attempt"))
        sel_scores = (sel or {}).get("judge_scores") or {}
        details: dict = {"judge_scores": sel_scores}

        if verdict == "held_voice":
            failing = (sel or {}).get("failing") or []
            dim_parts = []
            for dim in failing:
                _sc = _dim_score(sel_scores, dim)
                dim_parts.append(f"{dim}={_sc if _sc is not None else 'n/a'}")
            excerpt = _one_line_excerpt((sel or {}).get("feedback"))
            reason = "held_voice: " + ", ".join(dim_parts)
            if excerpt:
                reason += f" | judge_feedback: {excerpt}"
        elif verdict == "held_fabrication":
            # A rewrite that INVENTED a new entity (run_layer2 D-02) — reason from re-check flags.
            fab = ((sel or {}).get("reverify_flags") or {}).get("fabrication") or []
            reason = f"held_fabrication (rewrite): {_summarize_flags(fab)}"
        elif verdict == "escalated":
            reason = "escalated: eval un-scoreable (see edition_evals)"
        else:  # passed / any other
            reason = str(verdict)

        # D-12: an escalation loudly pages the operator (still NO status flip here — that is 30-03).
        # Suppressed for the telemetry-only shadow-row call so the primary eval pages just once (WR-03).
        if verdict == "escalated" and not suppress_alerts:
            _alert_operator(f"eval escalated for edition #{edition}: {reason}")

        return {"verdict": verdict, "reason": reason, "details": details, "ran": True}

    except Exception as e:
        # Fail-open-but-loud (D-06/D-07): NEVER re-raise — generation must continue to the Monday
        # human gate. Write a fail-loud error row + page the operator; guard each so a telemetry OR
        # alert failure inside the handler still returns (a telemetry write failure must not crash
        # generation).
        try:
            write_eval_row(
                supabase, newsletter_id=newsletter_id, edition_number=edition,
                pipeline_version=pipeline_version, attempt=0, layer="deterministic",
                eval_status="error", error=(str(e) or type(e).__name__)[:500],
            )
        except Exception:
            logger.error("[EVAL] telemetry write failed inside the fail-open handler", exc_info=True)
        if not suppress_alerts:
            try:
                _alert_operator(f"eval did not run for edition #{edition}: {type(e).__name__}")
            except Exception:
                logger.error("[EVAL] operator alert failed inside the fail-open handler", exc_info=True)
        logger.error("[EVAL] failed open for edition #%s", edition, exc_info=True)
        return {"verdict": "escalated", "reason": "eval outage", "details": {}, "ran": False}


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


# ---------------------------------------------------------------------------
# Robust LLM response extraction
#
# Root cause of the single-pass-writer-empty bug (debug 2026-06-24): the writer
# did `text = response.content[0].text.strip()`, stripped ```fences ONLY when the
# text START with "```", then json.loads(text). claude-sonnet-4-6 frames the LARGE
# writer output stochastically (bare JSON / ```json-fenced / occasionally prefixed
# with a prose preamble). Any framing that is not bare-or-leading-fence skipped the
# strip and json.loads failed at "char 0" — misdiagnosed as "empty content". These
# helpers extract the text robustly (joining all text blocks) and recover the JSON
# regardless of surrounding prose/fences, and FAIL LOUD (raise, with a logged
# snippet) when no JSON is recoverable — never silently returning empty.
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def response_text(response) -> str:
    """Concatenate the text of every text block in an Anthropic Messages response.

    For the common single-block case this equals response.content[0].text. Robust
    to (hypothetical) multi-block responses and never raises on a non-text block.
    """
    parts = []
    for block in (getattr(response, "content", None) or []):
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", "") or "")
    return "".join(parts)


def _first_balanced_object(text: str) -> str | None:
    """Return the first balanced {...} substring, respecting JSON string literals
    and escapes so braces inside string values do not confuse the matcher."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def parse_llm_json(text: str, *, context: str) -> dict:
    """Parse a JSON object from an LLM response that may be wrapped in prose or
    markdown fences. Tries, in order: (1) the raw (stripped) text, (2) the JSON
    inside the first ```json fenced block, (3) the first balanced {...} object.

    FAIL LOUD: raises json.JSONDecodeError (with a logged head/tail snippet) when
    nothing parses. NEVER returns empty/None — a genuinely unparseable response
    must surface as a loud failure, not a silent empty edition.
    """
    raw = text or ""
    candidates = []
    stripped = raw.strip()
    if stripped:
        candidates.append(stripped)
    m = _JSON_FENCE_RE.search(raw)
    if m:
        candidates.append(m.group(1).strip())
    balanced = _first_balanced_object(raw)
    if balanced:
        candidates.append(balanced)

    for cand in candidates:
        try:
            parsed = json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed

    logger.error(
        "[%s] No parseable JSON object in model response (len=%d). head=%r tail=%r",
        context, len(raw), raw[:300], raw[-200:],
    )
    raise json.JSONDecodeError(
        f"[{context}] no parseable JSON object in model response "
        f"(len={len(raw)}); head={raw[:200]!r}",
        raw if raw else "", 0,
    )


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

        result = parse_llm_json(response_text(response), context="qualitative_review")
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
        # D-08/D-09: omit Theme / weeks_ago when absent (loader sets
        # primary_theme=None and omits weeks_ago on null published_at) — no
        # literal "Theme: None" / "(?w ago)" in the angle-selection prompt.
        theme = ed.get('primary_theme')
        theme_seg = f" — Theme: {theme}" if theme else ""
        weeks = ed.get('weeks_ago')
        weeks_seg = f" ({weeks}w ago)" if weeks is not None else ""
        edition_lines.append(
            f"#{ed.get('edition_number', '?')}{weeks_seg}: "
            f"\"{ed.get('title', '?')}\"{theme_seg}"
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

        result = parse_llm_json(response_text(response), context="editorial_prepass")
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
                # D-08: omit the "Theme:" segment entirely when primary_theme is
                # null/falsy (older/null-theme editions) — the opening_excerpt
                # carries the edition (D-07 intent), no "Theme: ?" placeholder.
                theme = ed.get('primary_theme')
                theme_seg = f"— Theme: {theme} " if theme else ""
                edition_lines.append(
                    f"  {ed.get('edition_number', '?')}. \"{ed.get('title', '?')}\" "
                    f"{theme_seg}"
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
        text = response_text(response)
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
        text = response.choices[0].message.content or ""

    # Robust JSON extraction — claude-sonnet-4-6 frames the large writer output
    # stochastically (bare / ```json-fenced / occasionally prose-prefixed). Recover
    # the JSON regardless of framing; FAIL LOUD (raise, never silent-empty) if none.
    result = parse_llm_json(text, context=f"generate_newsletter:{task_type}")

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
                # WR-02 / D-08+D-09: the loader sets primary_theme=None and OMITS
                # weeks_ago on null published_at. Omit those segments entirely —
                # never emit a literal "Theme: None" / "(?w ago)" placeholder.
                theme = ed.get('primary_theme')
                theme_seg = f" — Theme: {theme}" if theme else ""
                weeks = ed.get('weeks_ago')
                weeks_seg = f" ({weeks}w ago)" if weeks is not None else ""
                edition_lines.append(
                    f"  #{ed.get('edition_number', '?')}{weeks_seg}:"
                    f" \"{ed.get('title', '?')}\""
                    f"{theme_seg}"
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
        edited = response_text(claude_response).strip()
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


# Apostrophe-position corruption in stored newsletter bodies, in two shapes — BOTH
# flanked by word characters, so genuine quotations / empty-string literals (flanked
# by whitespace or punctuation) are NEVER touched (threat T-19-03), and this is NOT
# a blanket replacement:
#
#   1. DOUBLED apostrophe (``''`` — two+ straight U+0027) standing where a SINGLE
#      apostrophe belongs (``it''s``, ``Cash App''s``, ``world''s``). This is the
#      PROVEN corruption (Phase 19 debug: 103 runs across published editions
#      26/29/30). Two adjacent apostrophes render as a VISUAL double-quote in the
#      serif body face (``it''s`` looks like ``it"s``) — the exact artifact the
#      operator saw on the live site. The model emitted ``''`` in those generation
#      runs; collapse a word-flanked run to a single U+0027.
#   2. A straight/curly DOUBLE-quote (U+0022 / U+201C / U+201D) standing mid-word
#      (``App"s``). Defensive: zero such occurrences exist today, but this is the
#      ROADMAP's literal description and a typographer recurrence would emit curly.
#
# Both map to a single straight apostrophe U+0027.
_APOSTROPHE_DOUBLED_RE = re.compile(r"(?<=[A-Za-z0-9])'{2,}(?=[A-Za-z0-9])")
_APOSTROPHE_DQ_RE = re.compile(r'(?<=[A-Za-z0-9])["“”](?=[A-Za-z0-9])')


def normalize_apostrophe_corruption(text: str, *, field: str = "<unspecified>",
                                    edition: int | str = "?") -> str:
    """Fail-loud write-path guard against apostrophe-position corruption.

    Phase 19 (QUOTE-01/QUOTE-02). The corruption the operator observed on the live
    site as ``Cash App"s`` is actually a DOUBLED apostrophe (``Cash App''s`` — two
    U+0027) emitted by the model in some generation runs: two adjacent apostrophes
    render as a visual double-quote in the serif body face. The renderer
    (``marked.parse``) has no typographer, so the fix belongs at the write path.

    This guard repairs ONLY word-flanked corruption signatures and logs loudly:
      * a doubled apostrophe ``''`` flanked by word chars -> a single U+0027
        (the proven corruption — editions 26/29/30 carried 103 occurrences);
      * defensively, a straight/curly double-quote (U+0022/U+201C/U+201D) flanked
        by word chars -> U+0027 (the ROADMAP's literal ``App"s`` shape; 0 today).

    It is a NO-OP on clean bodies and on genuine quotations / empty-string literals
    (those quotes are flanked by whitespace or punctuation, never by word chars), and
    it is NOT a blanket ``"``/``''`` -> ``'`` replacement (threat T-19-03).

    Fail-loud (project "the wallet bug" rule):
      * raises ``TypeError`` on non-``str`` input — never silently coerces;
      * ``logger.error``s with edition + field + counts whenever it rewrites, so a
        real recurrence is surfaced, not silently passed to storage.

    Args:
        text: the body string about to be stored (may be empty).
        field: which field this is (for log context).
        edition: edition number (for log context).

    Returns:
        The text with apostrophe-position corruption repaired (usually identical).
    """
    if text is None:
        # An absent body is a legitimate empty field; preserve the caller's value.
        return text
    if not isinstance(text, str):
        # Fail loud — do not silently coerce an unexpected type into storage.
        raise TypeError(
            f"normalize_apostrophe_corruption expected str for {field} "
            f"(edition {edition}), got {type(text).__name__}"
        )
    if not text:
        return text

    n_doubled = len(_APOSTROPHE_DOUBLED_RE.findall(text))
    n_dq = len(_APOSTROPHE_DQ_RE.findall(text))
    if not n_doubled and not n_dq:
        return text  # Clean — the common case. No-op.

    fixed = _APOSTROPHE_DOUBLED_RE.sub("'", text)
    fixed = _APOSTROPHE_DQ_RE.sub("'", fixed)
    # Loud surfacing: a recurrence past the (now-corrected) corpus must be visible.
    logger.error(
        "[QUOTE-FIX] Repaired apostrophe-position corruption in %s for edition %s: "
        "%d doubled-apostrophe run(s), %d mid-word double-quote(s) -> U+0027. "
        "This signals upstream corruption — investigate the generator.",
        field, edition, n_doubled, n_dq,
    )
    return fixed


def save_newsletter(result: dict, input_data: dict, blocks_data: dict | None = None) -> str | None:
    """Save newsletter to Supabase and local file. Returns inserted row UUID or None.

    Args:
        result: Generated newsletter content (title, content_markdown, etc.)
        input_data: Original task input from processor
        blocks_data: If block pipeline was used, the Phase A output for Phase D verification
    """
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

    # Phase 19 (QUOTE-01): fail-loud write-path guard against the apostrophe ->
    # straight-double-quote corruption. No-op on the (clean) corpus and on genuine
    # quotes; repairs ONLY the App"s signature; logs loudly if it ever fires. This
    # is the single shared insert for BOTH the single-pass and block-pipeline
    # write paths, so guarding here covers both. (See 19-DIAGNOSIS.md.)
    content_markdown = normalize_apostrophe_corruption(
        result.get("content_markdown", ""), field="content_markdown", edition=edition
    )
    content_markdown_impact = normalize_apostrophe_corruption(
        content_markdown_impact, field="content_markdown_impact", edition=edition
    )
    # WR-01: the same LLM emission also populates these sibling user-visible text
    # fields. Route them through the same guard so the corruption cannot recur in a
    # title or the Telegram body either (QUOTE-01 "cannot recur"). No-op on clean
    # input; never a blanket "->' replacement.
    title = normalize_apostrophe_corruption(
        result.get("title", f"Edition #{edition}"), field="title", edition=edition
    )
    title_impact = normalize_apostrophe_corruption(
        title_impact, field="title_impact", edition=edition
    )
    content_telegram = normalize_apostrophe_corruption(
        result.get("content_telegram", ""), field="content_telegram", edition=edition
    )

    # Insert into newsletters table
    row = {
        "edition_number": edition,
        "title": title,
        "title_impact": title_impact,
        "content_markdown": content_markdown,
        "content_markdown_impact": content_markdown_impact,
        "content_telegram": content_telegram,
        "data_snapshot": {**input_data, **(result.get('data_snapshot') or {})},
        "primary_theme": primary_theme,
        "status": "draft",
    }
    row_id = None
    try:
        insert_result = supabase.table("newsletters").insert(row).execute()
        row_id = insert_result.data[0]['id'] if insert_result.data else None
        logger.info(f"Saved newsletter edition #{edition} to Supabase (id={row_id}, status=draft, theme='{primary_theme}')")
    except Exception as e:
        logger.error(f"Failed to insert newsletter #{edition} into Supabase: {e}")

    # ── Phase D: Post-generation verification ──
    try:
        from verification import verify_draft
        # Verify the normalized bodies — the same bytes that were stored (Phase 19).
        tech_prose = content_markdown
        impact_prose = content_markdown_impact or ""

        # Build the fact base for verification.
        # Block pipeline path: pass blocks directly (Option B — verify against
        # exactly what the writer was given, not a reconstruction).
        # Single-pass path: use input_data as before.
        if blocks_data and blocks_data.get('blocks'):
            verification_input = {
                'blocks': blocks_data['blocks'],
                'tracked_entity_signals': blocks_data.get('tracked_entity_signals', []),
                'trending_tools': blocks_data.get('tool_stats', []),
                'predictions': blocks_data.get('predictions', []),
            }
            fact_base_source = 'blocks'
            fact_base_size = len(blocks_data['blocks'])
        else:
            verification_input = input_data
            fact_base_source = 'input_data'
            fact_base_size = len(input_data.get('premium_source_posts', []))

        logger.info(
            f"[VERIFICATION] Fact base: {fact_base_source} "
            f"({fact_base_size} items)"
        )

        tech_report = verify_draft(tech_prose, verification_input) if tech_prose else None
        impact_report = verify_draft(impact_prose, verification_input) if impact_prose else None

        verification = {
            "technical": tech_report,
            "impact": impact_report,
            "fact_base_source": fact_base_source,
            "fact_base_size": fact_base_size,
            "summary": {
                "total_ungrounded": (
                    (tech_report['summary']['ungrounded_count'] if tech_report else 0)
                    + (impact_report['summary']['ungrounded_count'] if impact_report else 0)
                ),
                "technical_count": tech_report['summary']['ungrounded_count'] if tech_report else 0,
                "impact_count": impact_report['summary']['ungrounded_count'] if impact_report else 0,
                "technical_tier1": tech_report['summary']['tier1_count'] if tech_report else 0,
                "impact_tier1": impact_report['summary']['tier1_count'] if impact_report else 0,
            }
        }

        # Always write verification report (even when clean)
        if row_id:
            supabase.table("newsletters").update({
                "verification_warnings": verification
            }).eq("id", row_id).execute()

        tech_u = tech_report['summary']['ungrounded_count'] if tech_report else 0
        impact_u = impact_report['summary']['ungrounded_count'] if impact_report else 0
        tech_t1 = tech_report['summary']['tier1_count'] if tech_report else 0
        impact_t1 = impact_report['summary']['tier1_count'] if impact_report else 0
        logger.info(
            f"[VERIFICATION] Edition #{edition}: "
            f"fact_base={fact_base_source} ({fact_base_size} items), "
            f"technical={tech_u} ungrounded (T1={tech_t1}), "
            f"impact={impact_u} ungrounded (T1={impact_t1})"
        )
    except Exception as e:
        logger.error(f"[VERIFICATION] Failed for edition #{edition}: {e}")

    # ── Phase 30 (WIRE-01/02/03/04/06): pre-publish eval + enforce-gated hold ──
    # Runs the governed two-layer eval on the PRIMARY draft this save_newsletter just
    # inserted (single_pass OR block_v1, D-13) and acts on the returned verdict. Ships
    # DORMANT: the whole block runs ONLY when edition_eval.enabled=true (rollback-safe,
    # D-03/D-15). The status flip fires ONLY under enforce=true; report-only surfaces a
    # "would-have-held" alert with NO flip (D-15). A `passed` verdict flips NOTHING — the
    # Monday human gate is unchanged (WIRE-04); `escalated` was already alerted by the
    # orchestrator (D-12). Fail-open (D-06): any eval/action error logs ERROR and continues
    # — the row is already inserted, generation must never break on the eval.
    try:
        cfg = _read_edition_eval_config()
        if cfg.get('enabled', False):
            # Reuse the fact base the Phase-D branch selected (D-13: whatever the primary
            # draft was built from). Re-derive the identical branch here so an early Phase-D
            # exception cannot leak a stale/undefined `verification_input` binding.
            if blocks_data and blocks_data.get('blocks'):
                fact_base = {
                    'blocks': blocks_data['blocks'],
                    'tracked_entity_signals': blocks_data.get('tracked_entity_signals', []),
                    'trending_tools': blocks_data.get('tool_stats', []),
                    'predictions': blocks_data.get('predictions', []),
                }
                pipeline_version = 'block_v1'
            else:
                fact_base = input_data
                pipeline_version = 'single_pass'

            draft = {
                'title': title,
                'title_impact': title_impact,
                'content_markdown': content_markdown,
                'content_markdown_impact': content_markdown_impact,
                'pipeline_version': pipeline_version,
            }
            prior_context = input_data.get('narrative_context') or {}
            prior_edition = _fetch_prior_published_edition()
            llm_client = _build_eval_llm_client()

            # ONE real httpx.Client per save point; the SAME instance reaches both eval
            # modules inside run_edition_eval (D-08 live network re-check active).
            with httpx.Client(timeout=15.0) as hc:
                verdict_obj = run_edition_eval(
                    supabase, draft, fact_base, prior_context, prior_edition,
                    pipeline_version=pipeline_version, newsletter_id=row_id,
                    edition=edition, config=cfg, llm_client=llm_client,
                    http_client=hc, github_token=os.getenv('GITHUB_TOKEN'),
                )

            verdict = verdict_obj.get('verdict')
            # `reason` is built inside run_edition_eval from category labels/counts +, for
            # held_voice, failing-dimension names + per-dim scores + a bounded judge_feedback
            # excerpt — NEVER raw draft prose (T-30-LOG). Safe to surface verbatim.
            reason = verdict_obj.get('reason', verdict)
            if verdict in ('held_fabrication', 'held_voice'):
                if cfg.get('enforce', False):
                    # Armed (enforce=true): loud escalation AND the status flip on the PRIMARY
                    # row (T-30-HOLD — only here, only this row_id).
                    _alert_operator(f"[EVAL HELD] edition #{edition} {reason}")
                    if row_id is not None:
                        supabase.table('newsletters').update({
                            'status': 'held',
                            'do_not_publish': True,
                            'do_not_publish_reason': reason,
                        }).eq('id', row_id).execute()
                        logger.warning(f"[EVAL] edition #{edition} HELD (enforce=true): {verdict}")
                    else:
                        logger.error(
                            f"[EVAL] edition #{edition} {verdict} but row_id is None — cannot "
                            "flip status (upstream insert failed)"
                        )
                else:
                    # Report-only (enforce=false, D-15): surface the would-have-held signal,
                    # NO status flip.
                    _alert_operator(f"[EVAL would-have-held] edition #{edition} {reason}")
                    logger.warning(
                        f"[EVAL] edition #{edition} would-have-held (report-only): {verdict}"
                    )
            # verdict == 'passed'    → no flip (unchanged Monday human gate, WIRE-04)
            # verdict == 'escalated' → run_edition_eval already alerted the operator (D-12)
    except Exception as e:
        logger.error(
            f"[EVAL] primary eval/action failed for edition #{edition} (non-blocking): {e}"
        )
        # Fail-open-but-LOUD (D-06/D-07): an eval-pipeline outage outside run_edition_eval's own
        # alerting (e.g. an import/packaging failure) must reach the operator, never just the logs.
        _alert_operator(
            f"[EVAL OUTAGE] edition #{edition}: primary eval pipeline failed "
            f"({type(e).__name__}) — no eval recorded; check newsletter logs"
        )

    # Save local markdown (builder version)
    md_file = NEWSLETTERS_DIR / f"brief_{edition}_{date_str}.md"
    try:
        md_file.write_text(content_markdown)
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

    return row_id


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


# ══════════════════════════════════════════════════════════════════════
# Continuity + exemplar loader (Phase 26 — audit R4)
# ══════════════════════════════════════════════════════════════════════
# Feeds the already-wired continuity consumers (single-pass writer, block
# prepass, Phase E voice check) prior-edition angles + operator-written
# voice exemplars. Behavioral twin: agentpulse_processor.py narrative-context
# builder, refined with the D-07/D-09/D-10/D-02 fail-loud deltas.
# Header / list / word-count idioms mirror verification.py:96-97 + the
# service's universal len(x.split()) word count.
_LE_SECTION_HEADER = re.compile(r'^#+\s+.*$')          # ## / ### markdown headers
_LE_BOLD_HEADER = re.compile(r'^\*\*[^*]+\*\*\s*$')     # bold-on-own-line headers
_LE_LIST_ITEM = re.compile(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)')  # - * + or 1. / 1) markers


def _le_opening_excerpt(content: str) -> str:
    """First ~300 chars of prose AFTER stripping leading markdown header line(s).

    Published bodies start directly at `## Read This, Skip the Rest` (no H1);
    the section label is not prose, so strip leading header/blank lines first
    (D-10).
    """
    lines = (content or '').lstrip().splitlines()
    idx = 0
    while idx < len(lines):
        first = lines[idx].strip()
        if not first or _LE_SECTION_HEADER.match(first):
            idx += 1
            continue
        break
    body = "\n".join(lines[idx:]).strip()
    return body[:300]


def _le_weeks_ago(published_at, now):
    """round((now - published_at) / 7 days). Returns None on null/unparseable
    published_at so the caller OMITS the key rather than falling back to the
    cadence-error-prone edition-number gap (D-09)."""
    if not published_at:
        return None
    try:
        ts = published_at
        if isinstance(ts, str):
            ts = ts.replace('Z', '+00:00')
            dt = datetime.fromisoformat(ts)
        else:
            dt = ts
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return round((now - dt).days / 7)
    except Exception:
        return None


def _le_is_exemplar_paragraph(para: str) -> bool:
    """True for a >=40-word, non-header, non-list paragraph (D-05)."""
    stripped = (para or '').strip()
    if len(stripped.split()) < 40:
        return False
    first_line = stripped.splitlines()[0].strip() if stripped.splitlines() else stripped
    if _LE_SECTION_HEADER.match(first_line) or _LE_BOLD_HEADER.match(first_line):
        return False
    if _LE_LIST_ITEM.match(first_line):
        return False
    return True


def _le_is_operator_written(data_snapshot) -> bool:
    """True iff data_snapshot marks the edition operator-written (D-01).

    LIVE DATA FIX (Phase 26 Plan 03): data_snapshot.operator_written is stored as
    a JSON BOOLEAN (true) in the live DB, NOT the string 'true' the 26-CONTEXT
    "live DB facts" assumed (that fact was read via PostgREST `->>`, which
    stringifies booleans, hiding the real type). supabase-py parses the JSONB to a
    Python bool, so the original `== 'true'` comparison was False for EVERY
    operator edition — the loader returned zero exemplars and Phase E stayed
    not_scored on live data despite 7 operator editions. Accept the boolean True
    OR the string 'true' (case-insensitive). Still excludes edition 29 / block_v1
    (operator_written absent or false).
    """
    v = (data_snapshot or {}).get('operator_written')
    return v is True or (isinstance(v, str) and v.strip().lower() == 'true')


def load_edition_context(supabase, limit=3, exemplar_paras=8):
    """Load prior-edition continuity context + operator-written voice exemplars.

    Returns a three-state dict (fail-loud-but-not-fatal — never raises into the
    generation path):
      {
        'previous_editions': [ {edition_number, title, primary_theme,
                                opening_excerpt, weeks_ago?}, ... ],  # oldest-first
        'exemplars': [str, ...],            # operator-written-only, >=40-word paras
        'exemplars_status': 'scored' | 'not_scored',   # distinguishable pool marker
        'empty': bool,
      }

    Three distinguishable states:
      - empty corpus (zero published)      → empty=True,  exemplars_status='not_scored',
                                             logs the empty-corpus WARNING sentinel
      - published but no operator-written  → empty=False, exemplars_status='not_scored'
                                             (NOT a silent score:0, NOT a fallback to
                                             any-published — D-02/D-03)
      - operator exemplars present         → empty=False, exemplars_status='scored'

    `supabase` is an explicit parameter (not the module global) so the degrade
    paths are fixture-testable without a live DB (Plan 02 depends on this).
    """
    empty_marker = {
        'previous_editions': [],
        'exemplars': [],
        'exemplars_status': 'not_scored',
        'empty': True,
    }
    try:
        # One published-set read — plain .eq() ONLY, never the `.in_` filter
        # (silent-failure bug; anti-pattern at :1792). Window of 8 surfaces 2-3
        # operator-written editions for the exemplar pool.
        recent = supabase.table('newsletters')\
            .select('edition_number, title, title_impact, content_markdown, '
                    'content_markdown_impact, data_snapshot, published_at')\
            .eq('status', 'published')\
            .order('edition_number', desc=True)\
            .limit(8)\
            .execute()
        rows = recent.data or []

        if not rows:
            # CTX-03 / D-16: whole-corpus-empty. Generation still completes.
            logger.warning("continuity context empty")
            return dict(empty_marker)

        now = datetime.now(timezone.utc)

        # ── previous_editions: ALL published, most-recent `limit`, oldest-first
        #    (continuity bridge works from every published edition — D-11) ──
        previous_editions = []
        for ed in rows[:limit]:
            ds = ed.get('data_snapshot') or {}
            lead_theme = ds.get('lead_theme')
            entry = {
                'edition_number': ed.get('edition_number'),
                'title': ed.get('title_impact') or ed.get('title') or '',
                # D-07: data_snapshot.lead_theme when present, else None. NEVER
                # data_snapshot.primary_theme (always null), NEVER title-derived.
                'primary_theme': lead_theme if lead_theme else None,
                'opening_excerpt': _le_opening_excerpt(ed.get('content_markdown') or ''),
            }
            weeks = _le_weeks_ago(ed.get('published_at'), now)
            if weeks is not None:
                entry['weeks_ago'] = weeks  # D-09: omit entirely on null published_at
            previous_editions.append(entry)
        previous_editions.reverse()  # oldest first — LLM reads the arc chronologically

        # ── exemplars: operator-written editions ONLY (D-01 anti-tic guard).
        #    operator_written is a JSON boolean in the live DB (see
        #    _le_is_operator_written) — this excludes edition 29 / block_v1. ──
        operator_rows = [
            ed for ed in rows
            if _le_is_operator_written(ed.get('data_snapshot'))
        ]
        exemplars = []
        # From the 2 most-recent operator editions, expand to a 3rd ONLY to reach
        # the cap (D-06). The cap-check at the top of each iteration stops before
        # the 3rd edition once the cap is met.
        for ed in operator_rows[:3]:
            if len(exemplars) >= exemplar_paras:
                break
            md = ed.get('content_markdown') or ''
            for para in re.split(r'\n\s*\n', md):  # blank-line paragraph split
                if len(exemplars) >= exemplar_paras:
                    break
                if _le_is_exemplar_paragraph(para):  # document order, front-loaded (D-05)
                    exemplars.append(para.strip())

        if exemplars:
            exemplars_status = 'scored'
            logger.info(
                f"Narrative context: {len(previous_editions)} edition(s), "
                f"{len(exemplars)} exemplar(s)"
            )
        else:
            # D-02/D-03: published editions exist but ZERO operator-written voice
            # exemplars → distinguishable "not scored", never a silent score:0 and
            # never a fallback to any-published.
            exemplars_status = 'not_scored'
            logger.warning(
                "continuity: no operator-written exemplars available "
                "— voice not scored (non-critical)"
            )

        return {
            'previous_editions': previous_editions,
            'exemplars': exemplars,
            'exemplars_status': exemplars_status,
            'empty': False,
        }
    except Exception as e:
        logger.warning(f"Narrative context assembly failed (non-critical): {e}")
        return dict(empty_marker)


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

    # Inject narrative context (continuity + exemplars) — covers BOTH writer
    # paths AND the prepass (all read input_data.get('narrative_context')).
    # The newsletter-service loader is AUTHORITATIVE for continuity metadata +
    # exemplars. The processor pre-populates a thinner narrative_context
    # (prepare_newsletter_data, agentpulse_processor.py:5615) with NO exemplars,
    # primary_theme from the always-null column (not data_snapshot.lead_theme),
    # positional weeks_ago, and an un-stripped opening excerpt. A plain setdefault
    # let that stale upstream win in every live trigger path, shadowing the loader
    # entirely — Phase E never scored, the lead_theme backfill never reached the
    # bridge. Merge so the loader's keys override while preserving upstream-only
    # keys (recent_spotlights, instruction). Supersedes the original
    # CTX-04/D-14 "upstream wins" — that rule guarded the now-inferior processor
    # context. (Phase 26 Plan 03, Option C.)
    ctx = load_edition_context(supabase)
    _upstream_ctx = input_data.get('narrative_context')
    if _upstream_ctx:
        _merged = {**_upstream_ctx, **ctx}
        # WR-01 fail-loud: a loader degrade (empty corpus OR a transient DB error)
        # both return empty=True with previous_editions=[]. Do NOT clobber a
        # populated upstream previous_editions (the processor reliably sets it) —
        # keep the continuity list so the bridge survives a transient loader
        # failure. The loader still contributes exemplars / exemplars_status
        # (empty -> not_scored, which is correct when no exemplars loaded).
        if ctx.get('empty') and _upstream_ctx.get('previous_editions'):
            _merged['previous_editions'] = _upstream_ctx['previous_editions']
        input_data['narrative_context'] = _merged
    else:
        input_data['narrative_context'] = ctx

    # Avoided-angles feed (D-14): the last 3 prepass angles → avoided_themes.
    # Both prepass consumers already read input_data.get('avoided_themes', [])
    # (editorial_prepass + block_pipeline prepass) but were unfed until now.
    # Plain ordered select — never the `.in_` filter. Fail-loud-but-not-fatal.
    _avoided_themes = []
    try:
        _angle_rows = supabase.table('newsletter_prepass_tracking')\
            .select('chosen_angle')\
            .order('created_at', desc=True)\
            .limit(3)\
            .execute()
        _avoided_themes = [
            r.get('chosen_angle') for r in (_angle_rows.data or [])
            if r.get('chosen_angle')
        ]
    except Exception as e:
        logger.warning(f"Avoided-themes feed failed (non-critical): {e}")
        _avoided_themes = []
    input_data.setdefault('avoided_themes', _avoided_themes)

    try:
        # ── Check block pipeline feature flag ──
        import json as _json
        _bp_config_path = Path(OPENCLAW_DATA_DIR) / "config" / "agentpulse-config.json"
        _bp_config = {}
        if _bp_config_path.exists():
            _bp_config = _json.loads(_bp_config_path.read_text()).get('block_pipeline', {})
        _use_block_pipeline = _bp_config.get('enabled', False) and task_type == 'write_newsletter'
        _blocks_data = None  # Set by block pipeline path, passed to save_newsletter

        if _use_block_pipeline:
            # ══════════════════════════════════════════════════════════
            # Block-based pipeline (primary generation path)
            # ══════════════════════════════════════════════════════════
            logger.info("[BLOCK PIPELINE] Running as primary generation path...")
            from block_selection import select_blocks
            from block_pipeline import generate_from_blocks, editorial_prepass_from_blocks

            # Phase A: select blocks (no angle constraint)
            blocks_data = select_blocks(supabase, llm_client=deepseek_client)
            _blocks_data = blocks_data

            # Block-aware prepass: pick angle FROM the blocks
            prepass_model = _bp_config.get('model_prepass', 'claude-sonnet-4-6')
            prepass_client = claude_client if prepass_model.startswith('claude') else deepseek_client
            block_editorial = editorial_prepass_from_blocks(
                blocks_data,
                narrative_context=input_data.get('narrative_context'),
                avoided_themes=input_data.get('avoided_themes', []),
                llm_client=prepass_client,
                model=prepass_model,
            )
            block_angle = (block_editorial or {}).get('chosen_angle', '')
            if not block_angle:
                # Fallback: run the original prepass for angle
                editorial_brief = editorial_prepass(input_data)
                block_angle = (editorial_brief or {}).get('chosen_angle', '')
                logger.warning(f"[BLOCK PIPELINE] Block prepass failed, using single-pass angle: {block_angle[:80]}")

            # Phase B + C + E
            prose_model = _bp_config.get('model_prose', 'claude-sonnet-4-6')
            prose_client = claude_client if prose_model.startswith('claude') else deepseek_client
            _voice_model = _bp_config.get('model_voice', 'deepseek-chat')
            _voice_client = claude_client if _voice_model.startswith('claude') else deepseek_client
            bp_result = generate_from_blocks(
                blocks_data,
                angle=block_angle,
                llm_client=prose_client,
                model_structure=_bp_config.get('model_structure', 'deepseek-chat'),
                model_prose=prose_model,
                model_voice=_voice_model,
                exemplars=(input_data.get('narrative_context') or {}).get('exemplars'),
                voice_client=_voice_client,
            )

            if bp_result.get('error'):
                logger.error(f"[BLOCK PIPELINE] Failed: {bp_result['error']}. Falling back to single-pass.")
                _use_block_pipeline = False
            else:
                # Build result dict matching NewsletterOutput schema
                edition = input_data.get('edition_number') or input_data.get('narrative_context', {}).get('edition_number', 0)
                result = {
                    'edition': edition,
                    'title': f"AgentPulse #{edition}",
                    'title_impact': f"AgentPulse #{edition}",
                    'content_markdown': bp_result.get('content_markdown', ''),
                    'content_markdown_impact': bp_result.get('content_markdown_impact', ''),
                    'content_telegram': '',
                    'data_snapshot': {
                        'pipeline_version': 'block_v1',
                        'voice_score': bp_result.get('voice_score', {}),
                        'block_summary': blocks_data.get('summary', {}),
                        'block_prepass': block_editorial,
                    },
                }
                logger.info(f"[BLOCK PIPELINE] Generation complete. Tech: {len(result['content_markdown'])} chars, "
                            f"Impact: {len(result['content_markdown_impact'])} chars")

        if not _use_block_pipeline:
            # ══════════════════════════════════════════════════════════
            # Single-pass pipeline (original generation path)
            # ══════════════════════════════════════════════════════════

            # Editorial pre-pass: choose this week's angle
            if task_type == 'write_newsletter':
                editorial_brief = editorial_prepass(input_data)
                if editorial_brief:
                    input_data['editorial_direction'] = editorial_brief

            # Generate newsletter
            raw_result = generate_newsletter(task_type, input_data, budget)
            validated = validate_llm_output(raw_result, NewsletterOutput)
            result = validated.model_dump()

        # ── Post-generation quality checks (single-pass only) ──
        if not _use_block_pipeline:
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
                continuity_phrases = ["last week", "last edition", "previously", "edition #", "editions ago"]
                has_continuity = any(p in impact_content.lower() for p in continuity_phrases)
                if not has_continuity:
                    logger.warning("QUALITY: Missing narrative continuity bridge in impact edition")
                else:
                    logger.info("QUALITY: Narrative continuity bridge detected")
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
        save_newsletter(result, input_data, blocks_data=_blocks_data)

        # ── A/B comparison: block-based pipeline (only when single-pass is primary) ──
        try:
            if not _use_block_pipeline and _bp_config.get('ab_comparison'):
                logger.info("[A/B] Running block-based pipeline for comparison...")
                from block_selection import select_blocks
                from block_pipeline import generate_from_blocks, editorial_prepass_from_blocks

                # Phase A: select blocks (NO angle constraint — blocks first)
                blocks_data = select_blocks(
                    supabase, llm_client=deepseek_client,
                )

                # Block-aware prepass: pick angle FROM the blocks
                prepass_model = _bp_config.get('model_prepass', 'claude-sonnet-4-6')
                prepass_client = claude_client if prepass_model.startswith('claude') else deepseek_client
                block_editorial = editorial_prepass_from_blocks(
                    blocks_data,
                    narrative_context=input_data.get('narrative_context'),
                    avoided_themes=input_data.get('avoided_themes', []),
                    llm_client=prepass_client,
                    model=prepass_model,
                )
                block_angle = (block_editorial or {}).get('chosen_angle', '')
                if not block_angle:
                    # Fallback: use the single-pass prepass angle
                    block_angle = input_data.get('editorial_direction', {}).get('chosen_angle', '')
                    logger.warning(f"[A/B] Block prepass failed, falling back to single-pass angle: {block_angle[:80]}")

                # Determine which client to use for prose
                prose_model = _bp_config.get('model_prose', 'claude-sonnet-4-6')
                prose_client = claude_client if prose_model.startswith('claude') else deepseek_client
                _voice_model = _bp_config.get('model_voice', 'deepseek-chat')
                _voice_client = claude_client if _voice_model.startswith('claude') else deepseek_client

                # Phase B + C + E
                bp_result = generate_from_blocks(
                    blocks_data,
                    angle=block_angle,
                    llm_client=prose_client,
                    model_structure=_bp_config.get('model_structure', 'deepseek-chat'),
                    model_prose=prose_model,
                    model_voice=_voice_model,
                    exemplars=(input_data.get('narrative_context') or {}).get('exemplars'),
                    voice_client=_voice_client,
                )

                if not bp_result.get('error'):
                    # Phase D verification on block pipeline output
                    from verification import verify_draft as _ab_verify
                    ab_verification_input = {
                        'blocks': blocks_data['blocks'],
                        'tracked_entity_signals': blocks_data.get('tracked_entity_signals', []),
                        'trending_tools': blocks_data.get('tool_stats', []),
                        'predictions': blocks_data.get('predictions', []),
                    }
                    ab_tech_report = _ab_verify(bp_result.get('content_markdown', ''), ab_verification_input)
                    ab_impact_report = _ab_verify(bp_result.get('content_markdown_impact', ''), ab_verification_input)
                    ab_verification = {
                        "technical": ab_tech_report,
                        "impact": ab_impact_report,
                        "fact_base_source": "blocks",
                        "fact_base_size": len(blocks_data['blocks']),
                        "summary": {
                            "total_ungrounded": (
                                ab_tech_report['summary']['ungrounded_count']
                                + ab_impact_report['summary']['ungrounded_count']
                            ),
                            "technical_tier1": ab_tech_report['summary']['tier1_count'],
                            "impact_tier1": ab_impact_report['summary']['tier1_count'],
                        }
                    }
                    logger.info(
                        f"[A/B] Verification: T1={ab_tech_report['summary']['tier1_count']}/{ab_impact_report['summary']['tier1_count']}, "
                        f"fact_base=blocks ({len(blocks_data['blocks'])} items)"
                    )

                    # Save as a separate held edition for comparison
                    bp_row = {
                        "edition_number": edition,
                        "title": normalize_apostrophe_corruption(
                            f"[BLOCK PIPELINE A/B] {result.get('title', '')}",
                            field="title", edition=edition),
                        "title_impact": normalize_apostrophe_corruption(
                            f"[BLOCK PIPELINE A/B] {result.get('title_impact', '')}",
                            field="title_impact", edition=edition),
                        "content_markdown": normalize_apostrophe_corruption(
                            bp_result.get('content_markdown', ''),
                            field="content_markdown", edition=edition),
                        "content_markdown_impact": normalize_apostrophe_corruption(
                            bp_result.get('content_markdown_impact', ''),
                            field="content_markdown_impact", edition=edition),
                        "status": "held",
                        # D-02: do_not_publish now has exactly ONE canonical home — the
                        # top-level migration-046 column (moved OUT of data_snapshot below).
                        # The A/B row is always-held; only the flag's HOME moves, not its
                        # hold state.
                        "do_not_publish": True,
                        "data_snapshot": {
                            "ab_comparison": True,
                            "pipeline_version": "block_v1",
                            "angle": block_angle,
                            "voice_score": bp_result.get('voice_score', {}),
                            "block_summary": blocks_data.get('summary', {}),
                            "block_prepass": block_editorial,
                        },
                        "verification_warnings": ab_verification,
                    }
                    insert_res = supabase.table("newsletters").insert(bp_row).execute()
                    bp_row_id = insert_res.data[0]['id'] if insert_res.data else None
                    logger.info(f"[A/B] Block pipeline comparison saved for edition #{edition}")

                    # ── Phase 30 (D-14): TELEMETRY-ONLY block_v1 eval ──
                    # Fully evaluate the always-held A/B shadow row for A/B trend
                    # completeness, but NEVER act on the verdict — NO status flip and NO
                    # would-have-held alert (only the PRIMARY draft's verdict drives publish
                    # state, D-13). Guarded by enabled + a real row id; fail-open via the
                    # enclosing A/B try/except-continue. The return value is intentionally
                    # discarded (telemetry rows only). suppress_alerts=True silences the
                    # orchestrator's own escalated/outage pages so a single edition is not
                    # double-paged by the shadow eval (WR-03); the error rows still persist.
                    _eval_cfg = _read_edition_eval_config()
                    if _eval_cfg.get('enabled', False) and bp_row_id is not None:
                        bp_draft = {
                            'title': bp_row['title'],
                            'title_impact': bp_row['title_impact'],
                            'content_markdown': bp_row['content_markdown'],
                            'content_markdown_impact': bp_row['content_markdown_impact'],
                            'pipeline_version': 'block_v1',
                        }
                        with httpx.Client(timeout=15.0) as hc:
                            run_edition_eval(
                                supabase, bp_draft, ab_verification_input,
                                input_data.get('narrative_context') or {},
                                _fetch_prior_published_edition(),
                                pipeline_version='block_v1', newsletter_id=bp_row_id,
                                edition=edition, config=_eval_cfg,
                                llm_client=_build_eval_llm_client(), http_client=hc,
                                github_token=os.getenv('GITHUB_TOKEN'),
                                suppress_alerts=True,
                            )
                else:
                    logger.warning(f"[A/B] Block pipeline failed: {bp_result.get('error')}")
        except Exception as e:
            logger.error(f"[A/B] Block pipeline comparison failed (non-blocking): {e}")
            # Fail-open-but-LOUD (D-06/D-07): the block_v1 telemetry eval feeds calibration —
            # losing it to a silent exception must reach the operator.
            _alert_operator(
                f"[EVAL OUTAGE] edition #{edition}: A/B block_v1 pipeline/eval failed "
                f"({type(e).__name__}) — telemetry eval lost; check newsletter logs"
            )

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
    require_env(['SUPABASE_URL', 'SUPABASE_SERVICE_KEY|SUPABASE_KEY', 'OPENAI_API_KEY',
                 'LLM_PROXY_URL'])
    main()
