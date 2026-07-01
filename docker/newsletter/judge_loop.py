"""Phase 29 — Layer 2 judge + feedback-rewrite loop (PURE build-only module).

`run_layer2(draft, fact_base, prior_context, det_flags, config, llm_client, *,
            http_client=None, github_token=None) -> dict`
runs a Sonnet judge over BOTH body versions (technical + impact) of a fabrication-clean
draft, scores five exemplar-anchored voice dimensions 1-5, and (Plan 02) drives a bounded
N=2 targeted-revise loop with a per-rewrite Layer-1 re-check. It returns the final draft +
a verdict object with full per-attempt telemetry.

PURITY CONTRACT (D-09 — mirrors deterministic_gate.py):
  - NO supabase client, NO `edition_evals` write (Phase 30 owns persistence via
    `edition_eval.write_eval_row`).
  - NO live proxy client construction. The caller INJECTS `llm_client`, which MUST already
    authenticate as the governed `edition_eval` identity (`edition_eval._get_eval_api_key()`
    → the LLM_PROXY_EVAL_KEY getter, GOV-01). This module NEVER reuses the newsletter
    service's own default LLM client or its provider-key identity — that would bill the wrong
    wallet (Pitfall 4).
  - NO container rebuild, NO status flip, NO verdict action (all Phase 30).

Every LLM call routes through `block_pipeline._llm_call` (proxied Anthropic/OpenAI-compatible);
every judge/revise parse uses `newsletter_poller.parse_llm_json` (raw → fenced → first
balanced object, FAIL LOUD) — NEVER the brittle inline triple-backtick fence strip that
produced the Phase-26 char-0 failure. The Layer-1 re-check reuses
`deterministic_gate.run_deterministic_gate` verbatim (D-01) — the same engine that gated entry.
"""

import json
import re  # noqa: F401 — used by later plans (revise render); imported here for a stable module surface
import logging
from typing import Any

from newsletter_poller import parse_llm_json
from block_pipeline import _llm_call
from deterministic_gate import run_deterministic_gate, _fact_base_source_texts  # noqa: F401 — Plan 02 re-check + revise guardrail

logger = logging.getLogger("newsletter")


# ── Module constants ─────────────────────────────────────────────────────────────────────────
# The filler-phrase blacklist, seeded VERBATIM from the newsletter identity file
# (data/openclaw/agents/newsletter/agent/IDENTITY.md:12-16). The deterministic filler pre-pass
# (`_count_filler_hits`) is a free string match; its hit-count combines with the Sonnet hedging
# score per the D-04 threshold (score < hedging_fail_below OR hits >= hedging_filler_hits_max).
DEFAULT_FILLER_BLACKLIST = [
    "navigating without a map", "wake-up call", "smart businesses are already",
    "sifting through the narrative", "elevated urgency", "the landscape is shifting",
    "builders should leverage", "as we move forward", "the evidence suggests",
    "in today's rapidly evolving", "it remains to be seen", "only time will tell",
]

# The two audience body renderings scored/revised as a coherent unit (D-08). Each tuple is
# (version_label, draft_field). One judge call per pipeline_version scores BOTH.
_BODIES = (("technical", "content_markdown"), ("impact", "content_markdown_impact"))

# The five exemplar-anchored voice dimensions (JUDGE-02/03/04).
_DIMENSIONS = ("continuity", "hedging_filler", "clickbait", "repeated_subtopics", "specificity")

# Per-dimension "fails below" config key (D-04). `hedging_filler` ALSO fails on the deterministic
# filler-hit combination (see `_compute_failing_dims`).
_FAIL_BELOW_KEY = {
    "continuity": "continuity_fail_below",
    "hedging_filler": "hedging_fail_below",
    "clickbait": "clickbait_fail_below",
    "repeated_subtopics": "repeated_subtopics_fail_below",
    "specificity": "specificity_fail_below",
}

# DEFAULT_CONFIG mirrors the `edition_eval` block in config/agentpulse-config.json so a
# partial/absent `config['edition_eval']` still yields a fully-populated merged config
# (RESEARCH A4). `_merged_config` deep-merges the caller's block over this.
DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "enforce": False,
    "max_attempts": 2,
    "judge_model": "claude-sonnet-4-6",
    "judge_temperature": 0.2,
    "judge_max_tokens": 1500,
    "revise_model": "claude-sonnet-4-6",
    "revise_temperature": 0.3,
    "revise_max_tokens": 3000,
    "thresholds": {
        "continuity_fail_below": 4,
        "hedging_fail_below": 3,
        "hedging_filler_hits_max": 3,
        "clickbait_fail_below": 3,
        "repeated_subtopics_fail_below": 3,
        "specificity_fail_below": 3,
        "warn_below": 4,
    },
    "filler_blacklist": [],
}


# ── Judge output SCHEMA CONTRACT (Task 2's `_judge_draft` produces EXACTLY this shape) ─────────
# {
#   "technical": {
#       "continuity":         {"score": int|"n/a", "evidence": str,
#                              "exemplar_before": str, "exemplar_after": str},
#       "hedging_filler":     {"score": int, "evidence": str, "exemplar_before": str, "exemplar_after": str},
#       "clickbait":          {...}, "repeated_subtopics": {...}, "specificity": {...}
#   },
#   "impact": { ...the same five dimensions... }
# }
# - Every dimension carries a numeric `score` 1-5 (JUDGE-05 rejects a bare score with no
#   quoted evidence / before-after exemplar).
# - `continuity.score` MAY be the string "n/a" ONLY when continuity is not applicable
#   (no prior published edition — D-05); `_compute_failing_dims` then excludes it entirely.


def _merged_config(config: dict | None) -> dict:
    """Deep-merge `config['edition_eval']` over DEFAULT_CONFIG so the pure function is robust to
    a partial/absent config (RESEARCH A4). The `thresholds` sub-dict is merged key-by-key;
    `filler_blacklist` falls back to DEFAULT_FILLER_BLACKLIST when the caller's value is
    empty/absent (an operator who wants to DISABLE filler detection sets thresholds, not an
    empty list)."""
    user = (config or {}).get("edition_eval", {}) or {}
    merged: dict[str, Any] = dict(DEFAULT_CONFIG)
    for key, value in user.items():
        if key == "thresholds":
            continue
        merged[key] = value
    merged["thresholds"] = {**DEFAULT_CONFIG["thresholds"], **(user.get("thresholds") or {})}
    fb = user.get("filler_blacklist") or merged.get("filler_blacklist")
    merged["filler_blacklist"] = fb if fb else DEFAULT_FILLER_BLACKLIST
    return merged


def _count_filler_hits(text: str, blacklist: list[str]) -> int:
    """D-04 deterministic filler pre-pass: case-insensitive count of every blacklist phrase
    occurrence in `text`. A free string match (no LLM) that combines with the Sonnet hedging
    score in `_compute_failing_dims`."""
    low = (text or "").lower()
    return sum(low.count(phrase.lower()) for phrase in (blacklist or []))


def _dim_score(judge_scores: dict, body: str, dim: str) -> Any:
    """Read a single body/dimension `score` out of the both-bodies judge schema."""
    return judge_scores[body][dim]["score"]


def _compute_failing_dims(
    judge_scores: dict, filler_hits: dict, cfg: dict, *, continuity_applicable: bool,
) -> list[str]:
    """The config-tunable, both-bodies threshold engine (JUDGE-04, D-04/D-05/D-08) — the pure
    input Plan 02's verdict loop consumes. Returns the list of failing dimension names.

    Rules:
      - A dimension fails for the pipeline_version if EITHER body fails → worst-case via
        `min(technical_score, impact_score) < <dim>_fail_below` (D-08).
      - `continuity` is EXCLUDED entirely when `continuity_applicable` is False (D-05) — never a
        fail, never counted. A stray non-numeric score on an applicable dimension is likewise
        skipped defensively (schema validation, not this function, owns rejection).
      - `hedging_filler` ALSO fails when the deterministic filler count trips the threshold:
        `max(technical_hits, impact_hits) >= hedging_filler_hits_max` (the D-04 combination),
        independent of the hedging score.
      - Mechanical Layer-1 flags are NEVER read here (they never enter `failing` — D-12).
    """
    thresholds = cfg["thresholds"]
    failing: list[str] = []
    for dim in _DIMENSIONS:
        if dim == "continuity" and not continuity_applicable:
            continue  # D-05: excluded on an empty corpus — never a fail
        tech = _dim_score(judge_scores, "technical", dim)
        impact = _dim_score(judge_scores, "impact", dim)
        # Defensive: a non-numeric score on an APPLICABLE dimension (e.g. a stray "n/a") must not
        # crash `min()`. Schema validation is the gate that rejects it; here we simply skip.
        if not _is_number(tech) or not _is_number(impact):
            continue
        worst = min(tech, impact)
        dim_fails = worst < thresholds[_FAIL_BELOW_KEY[dim]]
        if dim == "hedging_filler":
            max_hits = max(int(filler_hits.get("technical", 0)), int(filler_hits.get("impact", 0)))
            dim_fails = dim_fails or (max_hits >= thresholds["hedging_filler_hits_max"])
        if dim_fails:
            failing.append(dim)
    return failing


def _is_number(value: Any) -> bool:
    """A real numeric score (int/float) — excludes bool (which is an int subclass) and the
    string "n/a"."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def run_layer2(
    draft: dict,
    fact_base: dict,
    prior_context: dict,
    det_flags: dict,
    config: dict,
    llm_client,
    *,
    http_client=None,
    github_token=None,
) -> dict:
    """Run Layer 2 (judge + N=2 rewrite loop) over a FABRICATION-CLEAN draft.

    Args:
        draft: {title, title_impact, content_markdown, content_markdown_impact,
                pipeline_version} — both bodies are judged/revised as a unit (D-08).
        fact_base: the ALREADY-CORRECT in-memory fact base (single-pass `input_data` OR a
            block_v1 dict) — trusted verbatim, passed to the per-rewrite gate re-check + the
            revise guardrail (Plan 02).
        prior_context: `load_edition_context()` output — {previous_editions, exemplars,
            exemplars_status, empty}. Drives the continuity dimension + the D-05 n/a exclusion.
        det_flags: the Layer-1 gate result for attempt 0
            ({fabrication, unverified, mechanical, meta}). A NON-EMPTY `fabrication` is a
            mis-wired caller (Layer 1 must short-circuit first) → hard ValueError (JUDGE-01).
        config: full agentpulse config; the `edition_eval` block is merged over DEFAULT_CONFIG.
        llm_client: INJECTED proxied client authenticating as the governed `edition_eval`
            identity (GOV-01). REQUIRED — never constructed here (D-09).
        http_client: injectable httpx client for the per-rewrite Layer-1 re-check (Plan 02).
        github_token: GitHub token override for the re-check (Plan 02).

    Returns:
        {final_draft, verdict, selected_attempt, attempts:[...]} — see the per-attempt telemetry
        shape in `_attempt_row`. `verdict` ∈ {passed, held_fabrication, held_voice, escalated}.
    """
    # Fail loud (carry-forward "an error is not evidence"): a wrong/missing draft, fact base,
    # prior_context, or det_flags surfaces as a clear contract error — never a bare AttributeError
    # deep in the body (mirrors deterministic_gate.py:132-141).
    if not isinstance(draft, dict):
        raise ValueError(
            "run_layer2: draft must be a dict, got "
            f"{type(draft).__name__} — refusing to judge a wrong/missing draft"
        )
    if not isinstance(fact_base, dict):
        raise ValueError(
            "run_layer2: fact_base must be a dict, got "
            f"{type(fact_base).__name__} — refusing to verify against a wrong/missing fact base"
        )
    if not isinstance(prior_context, dict):
        raise ValueError(
            "run_layer2: prior_context must be a dict, got "
            f"{type(prior_context).__name__} — refusing to judge without continuity context"
        )
    if not isinstance(det_flags, dict):
        raise ValueError(
            "run_layer2: det_flags must be a dict, got "
            f"{type(det_flags).__name__} — refusing to run without the Layer-1 gate result"
        )

    # JUDGE-01 entry guard: Layer 2 must NEVER run on a fabricated draft. Layer 1's short-circuit
    # (Phase 30) is the primary gate; this refuses a mis-wired caller loudly rather than judging
    # (and potentially auto-revising) a draft that carries a live fabrication.
    if det_flags.get("fabrication"):
        raise ValueError(
            "run_layer2 called with a non-empty fabrication list — "
            "Layer 1 must short-circuit before Layer 2 (mis-wired caller)"
        )

    cfg = _merged_config(config)

    # ── Attempt-0 + the N=2 rewrite loop are implemented in Task 2 / Plan 02. This scaffold locks
    # the signature, the entry guard, the config merge, the filler pre-pass, and the threshold
    # engine on a stable base. Shipping a wrong verdict here would be worse than an explicit stub.
    raise NotImplementedError(
        "run_layer2 attempt-0 + N=2 rewrite loop — implemented in Task 2 / Plan 02"
    )
