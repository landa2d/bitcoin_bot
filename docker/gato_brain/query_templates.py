"""
Structured query templates — parameterized data queries for the intent router.

Provides:
- execute_template(supabase, template_name, params) → results + markdown table
- list_templates() → available templates with descriptions
"""

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone

from supabase import Client

logger = logging.getLogger("gato-brain")

# ─── Template definitions ────────────────────────────────────────────

TEMPLATES = {
    "trending_tools": {
        "description": "Tools with most mentions in the last 7 days",
        "default_params": {"limit": 10},
        "allowed_params": {"limit"},
    },
    "confirmed_predictions": {
        "description": "Predictions that have been confirmed",
        "default_params": {},
        "allowed_params": set(),
    },
    "refuted_predictions": {
        "description": "Predictions that have been refuted",
        "default_params": {},
        "allowed_params": set(),
    },
    "open_predictions": {
        "description": "Predictions still unresolved",
        "default_params": {},
        "allowed_params": set(),
    },
    "topic_stage": {
        "description": "Current lifecycle stage of a topic",
        "default_params": {"topic_pattern": "%"},
        "allowed_params": {"topic_pattern"},
    },
    "top_opportunities": {
        "description": "Highest confidence business opportunities",
        "default_params": {"limit": 5},
        "allowed_params": {"limit"},
    },
    "problem_clusters": {
        "description": "Problem themes by opportunity score",
        "default_params": {"limit": 10},
        "allowed_params": {"limit"},
    },
    "recent_spotlights": {
        "description": "Recent research deep-dives",
        "default_params": {"limit": 5},
        "allowed_params": {"limit"},
    },
    "prediction_scorecard": {
        "description": "Overall prediction accuracy stats",
        "default_params": {},
        "allowed_params": set(),
    },
}


def list_templates() -> list[dict]:
    """Return template names and descriptions for the router prompt."""
    return [
        {"name": name, "description": t["description"]}
        for name, t in TEMPLATES.items()
    ]


def _merge_params(template_name: str, user_params: dict) -> dict:
    """Merge user params with defaults, filtering to allowed keys."""
    tmpl = TEMPLATES[template_name]
    merged = dict(tmpl["default_params"])
    for k, v in user_params.items():
        if k in tmpl["allowed_params"]:
            merged[k] = v
    return merged


def _to_markdown_table(rows: list[dict], columns: list[str] | None = None) -> str:
    """Convert a list of dicts to a markdown table string."""
    if not rows:
        return "_No results found._"

    cols = columns or list(rows[0].keys())
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    lines = [header, sep]
    for row in rows:
        vals = []
        for c in cols:
            v = row.get(c, "")
            if v is None:
                v = ""
            # Truncate long values
            s = str(v)
            if len(s) > 120:
                s = s[:117] + "..."
            # Escape pipes in values
            s = s.replace("|", "\\|")
            vals.append(s)
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


# ─── Template executors ──────────────────────────────────────────────

def _exec_trending_tools(sb: Client, params: dict) -> tuple[list[dict], list[str]]:
    limit = int(params.get("limit", 10))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    resp = (
        sb.table("tool_mentions")
        .select("tool_name, sentiment_score")
        .gte("mentioned_at", cutoff)
        .execute()
    )
    rows = resp.data or []

    # Aggregate in Python
    counts: Counter = Counter()
    sentiments: dict[str, list[float]] = {}
    for r in rows:
        name = r["tool_name"]
        counts[name] += 1
        if r.get("sentiment_score") is not None:
            sentiments.setdefault(name, []).append(r["sentiment_score"])

    results = []
    for name, count in counts.most_common(limit):
        scores = sentiments.get(name, [])
        avg_sent = round(sum(scores) / len(scores), 2) if scores else None
        results.append({
            "tool_name": name,
            "mentions_7d": count,
            "avg_sentiment": avg_sent,
        })

    return results, ["tool_name", "mentions_7d", "avg_sentiment"]


def _exec_predictions_by_status(sb: Client, status: str) -> tuple[list[dict], list[str]]:
    resp = (
        sb.table("predictions")
        .select("prediction_text, status, created_at")
        .eq("status", status)
        .order("created_at", desc=True)
        .execute()
    )
    results = []
    for r in (resp.data or []):
        results.append({
            "prediction_text": r.get("prediction_text") or r.get("title") or "",
            "status": r["status"],
            "created_at": (r.get("created_at") or "")[:10],
        })
    return results, ["prediction_text", "status", "created_at"]


def _exec_topic_stage(sb: Client, params: dict) -> tuple[list[dict], list[str]]:
    pattern = params.get("topic_pattern", "%")
    query = sb.table("topic_evolution").select("topic_key, current_stage, last_updated")

    if pattern != "%":
        query = query.ilike("topic_key", f"%{pattern}%")

    resp = query.order("last_updated", desc=True).execute()

    results = []
    for r in (resp.data or []):
        results.append({
            "topic": r["topic_key"],
            "stage": r["current_stage"],
            "last_updated": (r.get("last_updated") or "")[:10],
        })
    return results, ["topic", "stage", "last_updated"]


def _exec_top_opportunities(sb: Client, params: dict) -> tuple[list[dict], list[str]]:
    limit = int(params.get("limit", 5))
    resp = (
        sb.table("opportunities")
        .select("title, proposed_solution, business_model, confidence_score")
        .order("confidence_score", desc=True)
        .limit(limit)
        .execute()
    )
    results = []
    for r in (resp.data or []):
        results.append({
            "title": r["title"],
            "proposed_solution": r.get("proposed_solution") or "",
            "business_model": r.get("business_model") or "",
            "confidence": r.get("confidence_score"),
        })
    return results, ["title", "proposed_solution", "business_model", "confidence"]


def _exec_problem_clusters(sb: Client, params: dict) -> tuple[list[dict], list[str]]:
    limit = int(params.get("limit", 10))
    resp = (
        sb.table("problem_clusters")
        .select("theme, opportunity_score, market_validation")
        .order("opportunity_score", desc=True)
        .limit(limit)
        .execute()
    )
    results = []
    for r in (resp.data or []):
        mv = r.get("market_validation")
        mv_str = ""
        if isinstance(mv, dict):
            mv_str = mv.get("summary", str(mv)[:80])
        elif mv:
            mv_str = str(mv)[:80]
        results.append({
            "theme": r["theme"],
            "opportunity_score": r.get("opportunity_score"),
            "market_validation": mv_str,
        })
    return results, ["theme", "opportunity_score", "market_validation"]


def _exec_recent_spotlights(sb: Client, params: dict) -> tuple[list[dict], list[str]]:
    limit = int(params.get("limit", 5))
    resp = (
        sb.table("spotlight_history")
        .select("topic_name, thesis, prediction, created_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    results = []
    for r in (resp.data or []):
        results.append({
            "topic": r.get("topic_name") or "",
            "thesis": r.get("thesis") or "",
            "prediction": r.get("prediction") or "",
            "date": (r.get("created_at") or "")[:10],
        })
    return results, ["topic", "thesis", "prediction", "date"]


def _exec_prediction_scorecard(sb: Client, _params: dict) -> tuple[list[dict], list[str]]:
    resp = sb.table("predictions").select("status").execute()
    rows = resp.data or []

    counts: Counter = Counter()
    for r in rows:
        counts[r["status"]] += 1

    confirmed = counts.get("confirmed", 0)
    refuted = counts.get("refuted", 0)
    opn = counts.get("open", 0)
    total = sum(counts.values())
    resolved = confirmed + refuted
    accuracy = round(confirmed / resolved * 100, 1) if resolved > 0 else None

    results = [{
        "confirmed": confirmed,
        "refuted": refuted,
        "open": opn,
        "total": total,
        "accuracy_pct": accuracy,
    }]
    return results, ["confirmed", "refuted", "open", "total", "accuracy_pct"]


# ─── Dispatcher ──────────────────────────────────────────────────────

_EXECUTORS = {
    "trending_tools": _exec_trending_tools,
    "confirmed_predictions": lambda sb, p: _exec_predictions_by_status(sb, "confirmed"),
    "refuted_predictions": lambda sb, p: _exec_predictions_by_status(sb, "refuted"),
    "open_predictions": lambda sb, p: _exec_predictions_by_status(sb, "open"),
    "topic_stage": _exec_topic_stage,
    "top_opportunities": _exec_top_opportunities,
    "problem_clusters": _exec_problem_clusters,
    "recent_spotlights": _exec_recent_spotlights,
    "prediction_scorecard": _exec_prediction_scorecard,
}


def execute_template(
    supabase: Client,
    template_name: str,
    params: dict | None = None,
) -> dict:
    """
    Execute a structured query template.

    Returns:
        {
            "template_name": str,
            "description": str,
            "results": list[dict],
            "markdown": str,
            "row_count": int,
        }
    """
    if template_name not in TEMPLATES:
        logger.warning(f"Unknown template: {template_name}")
        return {
            "template_name": template_name,
            "description": "Unknown template",
            "results": [],
            "markdown": f"_Unknown template: {template_name}_",
            "row_count": 0,
        }

    merged = _merge_params(template_name, params or {})
    executor = _EXECUTORS[template_name]

    try:
        results, columns = executor(supabase, merged)
        md = _to_markdown_table(results, columns)
        logger.info(f"Template '{template_name}': {len(results)} rows")
        return {
            "template_name": template_name,
            "description": TEMPLATES[template_name]["description"],
            "results": results,
            "markdown": md,
            "row_count": len(results),
        }
    except Exception as e:
        logger.warning(f"Template '{template_name}' failed: {e}")
        return {
            "template_name": template_name,
            "description": TEMPLATES[template_name]["description"],
            "results": [],
            "markdown": f"_Query failed: {e}_",
            "row_count": 0,
        }
