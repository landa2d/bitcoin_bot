"""Phase 29 — Layer 2 judge + feedback-rewrite loop (PURE build-only module).

`run_layer2(draft, fact_base, prior_context, det_flags, config, llm_client, *,
            http_client=None, github_token=None) -> dict`
runs a Sonnet judge over BOTH body versions (technical + impact) of a fabrication-clean
draft, scores five exemplar-anchored voice dimensions 1-5, and (Plan 02) drives a bounded
N=2 targeted-revise loop with a per-rewrite Layer-1 re-check. It returns the final draft +
a verdict object with full per-attempt telemetry.

PURITY CONTRACT (D-09 — mirrors deterministic_gate.py):
  - NO supabase client, NO `edition_evals` write (Phase 30 owns persistence via
    the `edition_eval` row-write helper).
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
from deterministic_gate import run_deterministic_gate, _fact_base_source_texts  # D-01 per-rewrite re-check + D-07 revise guardrail

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


# ── The 5-dimension exemplar-anchored Sonnet judge (JUDGE-02/03/04/05) ─────────────────────────
# Generalizes block_pipeline.py::phase_e_voice_check from one dimension to five × two bodies,
# scored in ONE call per pipeline_version (D-08). Every dimension REQUIRES a numeric score, a
# quoted evidence sentence, and a before/after exemplar — a bare score is schema-rejected
# (JUDGE-05). Parsing is the robust `parse_llm_json` (NEVER the brittle inline fence strip).

JUDGE_SYSTEM = (
    "You are the editorial judge for AgentPulse, a weekly intelligence brief about the AI "
    "agent economy. Score BOTH draft versions (technical and impact) 1-5 on five voice "
    "dimensions. For EVERY dimension you MUST return a numeric score (1-5), a short quoted "
    "sentence of EVIDENCE from the draft, and a before/after EXEMPLAR showing the concrete "
    "fix. A score with no quoted evidence or before/after exemplar is invalid. Respond ONLY "
    "with valid JSON — no prose, no markdown fences."
)

JUDGE_PROMPT = """PRIOR EDITIONS (verify the continuity bridge is real and accurate):
{prior_editions}

EXEMPLARS (the target voice — observational, specific, concept-first professor tone):
{exemplars}

TECHNICAL BODY:
{content_markdown}

IMPACT BODY:
{content_markdown_impact}

Score these five dimensions for BOTH bodies:
- continuity: the lead MUST bridge to a prior edition's theme; a missing/absent bridge scores 1. Score the STRING "n/a" only if you are told NO prior editions exist.
- hedging_filler: penalize hedging and generic filler phrases that could appear in any business deck.
- clickbait: professor voice = concept-first, defines its terms, no second-person fear hooks; second-person clickbait/fear framing scores low.
- repeated_subtopics: penalize sub-topics recycled from the last edition.
- specificity: reward named entities, dated numbers, and a falsifiable prediction; penalize vague/unfalsifiable claims.

Return ONLY this JSON shape (a numeric score, a quoted evidence sentence, and a before/after exemplar for EVERY dimension in EACH body):
{{"technical": {{"continuity": {{"score": 4, "evidence": "...", "exemplar_before": "...", "exemplar_after": "..."}}, "hedging_filler": {{"score": 4, "evidence": "...", "exemplar_before": "...", "exemplar_after": "..."}}, "clickbait": {{"score": 4, "evidence": "...", "exemplar_before": "...", "exemplar_after": "..."}}, "repeated_subtopics": {{"score": 4, "evidence": "...", "exemplar_before": "...", "exemplar_after": "..."}}, "specificity": {{"score": 4, "evidence": "...", "exemplar_before": "...", "exemplar_after": "..."}}}}, "impact": {{"continuity": {{"score": 4, "evidence": "...", "exemplar_before": "...", "exemplar_after": "..."}}, "hedging_filler": {{"score": 4, "evidence": "...", "exemplar_before": "...", "exemplar_after": "..."}}, "clickbait": {{"score": 4, "evidence": "...", "exemplar_before": "...", "exemplar_after": "..."}}, "repeated_subtopics": {{"score": 4, "evidence": "...", "exemplar_before": "...", "exemplar_after": "..."}}, "specificity": {{"score": 4, "evidence": "...", "exemplar_before": "...", "exemplar_after": "..."}}}}}}"""

# Cap the body prose injected into the judge prompt (token budget; also bounds untrusted draft
# text embedded into the prompt — the draft is model-generated and never logged raw at INFO).
_JUDGE_BODY_CHAR_CAP = 6000


def _render_prior_editions(prior_context: dict, continuity_applicable: bool) -> str:
    """Render the last-3-editions angles for the continuity dimension, reusing the shape
    `editorial_prepass_from_blocks` consumes (block_pipeline.py:516-525). When continuity is NOT
    applicable (empty corpus, D-05), tell the judge explicitly so it scores "n/a" and does not
    fabricate a bridge."""
    if not continuity_applicable:
        return ('NO prior published editions exist — score continuity as the string "n/a" and '
                "do not invent a bridge.")
    lines = []
    for ed in prior_context.get("previous_editions") or []:
        excerpt = (ed.get("opening_excerpt") or "")[:100]
        lines.append(
            f"#{ed.get('edition_number', '?')} ({ed.get('weeks_ago', '?')}w ago): "
            f"\"{ed.get('title', '?')}\" — {excerpt}"
        )
    return "\n".join(lines) if lines else "No previous editions available."


def _build_judge_prompt(
    draft: dict, prior_context: dict, continuity_applicable: bool, cfg: dict,
) -> tuple[str, str]:
    """Build the (system, user) judge prompt. Injects the prior-editions render, the operator
    exemplars, and BOTH bodies (D-08). `str.format` only touches JUDGE_PROMPT's own braces — the
    substituted values (draft prose, exemplars) may contain braces safely."""
    prior_editions = _render_prior_editions(prior_context, continuity_applicable)
    exemplars = prior_context.get("exemplars") or []
    exemplar_text = ("\n\n---\n\n".join(str(e) for e in exemplars[:10])
                     if exemplars else "No operator exemplars available.")
    user = JUDGE_PROMPT.format(
        prior_editions=prior_editions,
        exemplars=exemplar_text,
        content_markdown=(draft.get("content_markdown") or "")[:_JUDGE_BODY_CHAR_CAP],
        content_markdown_impact=(draft.get("content_markdown_impact") or "")[:_JUDGE_BODY_CHAR_CAP],
    )
    return JUDGE_SYSTEM, user


def _validate_judge_response(parsed: dict, *, continuity_applicable: bool) -> None:
    """JUDGE-05 schema gate. Raise ValueError if the judge response is missing a body, a
    dimension, or — for any scored dimension — a numeric 1-5 `score`, a non-empty `evidence`,
    or a non-empty `exemplar_before`/`exemplar_after`. The string "n/a" is accepted for the
    `continuity` score ONLY when continuity is NOT applicable (D-05); an n/a continuity is exempt
    from the evidence/exemplar requirement (there is nothing to bridge to). A score without
    quoted evidence + a before/after exemplar is rejected — never a fabricated 0."""
    if not isinstance(parsed, dict):
        raise ValueError("judge response is not a JSON object")
    for body in ("technical", "impact"):
        body_scores = parsed.get(body)
        if not isinstance(body_scores, dict):
            raise ValueError(f"judge response missing body '{body}'")
        for dim in _DIMENSIONS:
            entry = body_scores.get(dim)
            if not isinstance(entry, dict):
                raise ValueError(f"judge response missing dimension '{dim}' in body '{body}'")
            score = entry.get("score")
            if dim == "continuity" and not continuity_applicable:
                if score != "n/a":
                    raise ValueError(
                        'continuity must be scored the string "n/a" when there are no prior '
                        "editions (D-05)"
                    )
                continue  # n/a continuity: no evidence/exemplar required
            for field in ("evidence", "exemplar_before", "exemplar_after"):
                val = entry.get(field)
                if not isinstance(val, str) or not val.strip():
                    raise ValueError(
                        f"judge dimension '{dim}' ({body}) missing non-empty '{field}' — a score "
                        "without quoted evidence/exemplars is rejected (JUDGE-05)"
                    )
            if not _is_number(score):
                raise ValueError(
                    f"judge dimension '{dim}' ({body}) score must be numeric 1-5, got {score!r}"
                )
            if not (1 <= score <= 5):
                raise ValueError(
                    f"judge dimension '{dim}' ({body}) score {score} out of range 1-5"
                )


def _judge_draft(draft: dict, prior_context: dict, llm_client, cfg: dict) -> dict:
    """Run the 5-dimension judge over BOTH bodies in ONE call (D-08), with the JUDGE-05
    schema-reject → one-retry → error contract. Returns:
      {"status": "ok", "scores": {both bodies × 5 dims}, "continuity_applicable": bool}, or
      {"status": "error", "error": str, "continuity_applicable": bool}.
    An error is NOT evidence — the caller maps it to `escalated`, never a fabricated 0."""
    continuity_applicable = not (
        prior_context.get("empty") or not prior_context.get("previous_editions")
    )
    system, user = _build_judge_prompt(draft, prior_context, continuity_applicable, cfg)
    last_err: Exception | None = None
    for attempt_i in (1, 2):  # 1 call + at most 1 retry (JUDGE-05)
        try:
            text = _llm_call(
                llm_client, cfg["judge_model"], system, user,
                temperature=cfg["judge_temperature"], max_tokens=cfg["judge_max_tokens"],
            )
            parsed = parse_llm_json(text, context="layer2_judge")  # FAILS LOUD, never silent-empty
            _validate_judge_response(parsed, continuity_applicable=continuity_applicable)
            return {"status": "ok", "scores": parsed,
                    "continuity_applicable": continuity_applicable}
        except Exception as e:  # json.JSONDecodeError (parse) or ValueError (schema)
            last_err = e
            logger.warning("layer2 judge attempt %d rejected: %s", attempt_i, e)
            continue
    return {"status": "error",
            "error": f"judge schema-invalid after retry: {last_err}",
            "continuity_applicable": continuity_applicable}


# ── The targeted revise call + the structured per-dimension feedback builder (LOOP-01/D-07/D-08) ─
# The loop re-calls the writer via a TARGETED revise (dedicated "fix exactly these issues, change
# nothing else, invent nothing" Sonnet call) — NOT a full writer re-run. ONE writer-agnostic
# function serves both single_pass and block_v1 (D-07). The revise carries the source-facts
# guardrail from `_fact_base_source_texts` (the same accessor the gate uses) and rewrites BOTH
# bodies as a unit (D-08). Parsing is the robust `parse_llm_json` (NEVER a brittle fence strip).

REVISE_SYSTEM = (
    "You are revising a published-quality newsletter draft for AgentPulse, a weekly intelligence "
    "brief about the AI agent economy. Fix EXACTLY the issues listed below and change NOTHING "
    "else. You may ONLY use entities, numbers, and claims present in SOURCE FACTS — introduce NO "
    "new entity or number and invent nothing. Rewrite BOTH the technical and the impact body "
    "together as a coherent pair. Respond ONLY with valid JSON of the shape "
    '{"content_markdown": "...", "content_markdown_impact": "..."} — no prose, no markdown fences.'
)

REVISE_PROMPT = """ISSUES TO FIX (change nothing else):
{feedback}

SOURCE FACTS (the ONLY facts you may use — introduce nothing outside this list):
{source_facts}

CURRENT TECHNICAL BODY (content_markdown):
{content_markdown}

CURRENT IMPACT BODY (content_markdown_impact):
{content_markdown_impact}

Rewrite BOTH bodies together, fixing exactly the issues above and keeping everything else intact.
Return ONLY the JSON object {{"content_markdown": "...", "content_markdown_impact": "..."}}."""

# Bound the source-facts list injected into the revise prompt (token budget; the guardrail list
# is per-source, so a cap keeps the prompt bounded on a large fact base without dropping the
# revise's ability to rewrite the whole body — bodies are passed in full, unlike the judge sample).
_REVISE_SOURCE_CAP = 150


def _worst_body_entry(judge_scores: dict, dim: str) -> dict:
    """Return the LOWER-scoring (worst) body's per-dimension entry for `dim` — the offending
    body whose evidence/exemplar drives the feedback. A failing dim always has numeric scores on
    both bodies (that is how it entered `failing`); the non-numeric guard is purely defensive."""
    tech = judge_scores["technical"][dim]
    impact = judge_scores["impact"][dim]
    ts, is_ = tech.get("score"), impact.get("score")
    if _is_number(ts) and _is_number(is_):
        return tech if ts <= is_ else impact
    return tech if _is_number(ts) else impact


def _describe_mechanical(flag: Any) -> str:
    """Render a single Layer-1 mechanical flag as a short revise note (telemetry-shaped dict →
    'kind: detail'). Defensive to unknown shapes; never raises."""
    if not isinstance(flag, dict):
        return str(flag)
    kind = flag.get("kind") or flag.get("type") or flag.get("check") or "mechanical"
    detail = (flag.get("detail") or flag.get("message") or flag.get("reason")
              or flag.get("value") or "")
    return f"{kind}: {detail}".strip() if detail else str(kind)


def _unique_filler_matches(filler_matches: dict | None) -> list[str]:
    """Flatten the per-body matched-filler-phrase map into a de-duplicated, order-preserving list
    (WR-01). `filler_matches` is `{version: [phrase, ...]}` — the exact blacklist phrases the
    deterministic pre-pass found in each body. Returns [] when nothing matched / no map given."""
    seen: set[str] = set()
    ordered: list[str] = []
    for phrases in (filler_matches or {}).values():
        for phrase in phrases or []:
            if phrase not in seen:
                seen.add(phrase)
                ordered.append(phrase)
    return ordered


def _build_feedback(
    judge_scores: dict, failing: list[str], mechanical: list[dict] | None = None,
    *, filler_matches: dict | None = None, cfg: dict | None = None,
) -> str:
    """Build STRUCTURED, SPECIFIC per-dimension revise feedback (LOOP-01). For each failing
    dimension: name it, quote the judge's offending `evidence`, and give the concrete
    before/after exemplar fix — never the vague "improve X". A failing `continuity` dim gets an
    EXPLICIT bridge-to-prior-edition instruction (D-06 — severity ≠ rewrite-eligibility). The
    optional `mechanical` list rides along as extra guidance ONLY here, and this function is
    called ONLY when `failing` is non-empty (mechanical-only never triggers a rewrite — D-12).
    Fabrication flags NEVER appear (fabrication never enters the loop — LOOP-04); the caller
    passes only the mechanical list, never the fabrication list.

    WR-01: when `hedging_filler` fails ONLY on the deterministic filler-hit combination (the
    judge's hedging SCORE is passing but a banned phrase tripped `hedging_filler_hits_max`), the
    judge's evidence/exemplar quotes a sentence it graded CLEAN — misdirecting the revise. In that
    case emit an explicit, actionable line NAMING the exact banned phrases from `filler_matches`
    instead. When the judge score itself is below `hedging_fail_below`, the existing
    evidence/exemplar behavior is preserved."""
    hedging_fail_below = ((cfg or {}).get("thresholds") or {}).get("hedging_fail_below")
    lines = [
        "Fix EXACTLY the issues below. Change nothing else. Invent no new entity or number.",
        "",
    ]
    for dim in failing:
        entry = _worst_body_entry(judge_scores, dim)
        if dim == "hedging_filler":
            worst_score = entry.get("score")
            score_below = (
                hedging_fail_below is not None
                and _is_number(worst_score)
                and worst_score < hedging_fail_below
            )
            matched = _unique_filler_matches(filler_matches)
            # Fail on banned phrases while the judge score is passing → name the phrases to remove
            # (the judge evidence here is a CLEAN sentence and would misdirect the revise — WR-01).
            if matched and not score_below:
                quoted = ", ".join(f'"{phrase}"' for phrase in matched)
                lines.append(
                    f"- hedging_filler: remove these banned filler phrases: {quoted}."
                )
                continue
        evidence = str(entry.get("evidence") or "").strip()
        before = str(entry.get("exemplar_before") or "").strip()
        after = str(entry.get("exemplar_after") or "").strip()
        if dim == "continuity":
            lines.append(
                "- continuity: the lead does NOT bridge to the prior edition. Add a lead "
                "sentence bridging to the previous edition's theme."
            )
        else:
            lines.append(f"- {dim}: this dimension fell below the voice bar and must be fixed.")
        if evidence:
            lines.append(f'    offending text: "{evidence}"')
        if before or after:
            lines.append(f'    rewrite pattern: "{before}" -> "{after}"')
    if mechanical:
        lines.append("")
        lines.append("Also address these mechanical notes if trivial (do NOT fabricate):")
        for flag in mechanical:
            lines.append(f"    - {_describe_mechanical(flag)}")
    return "\n".join(lines)


def _revise_draft(draft: dict, feedback: str, fact_base: dict, llm_client, cfg: dict) -> dict:
    """Targeted both-body revise (LOOP-01, D-07, D-08). Builds the source-facts guardrail from
    `_fact_base_source_texts` (handles BOTH fact-base shapes — one revise fn serves single_pass
    AND block_v1), sends the structured `feedback` + both current bodies + the source facts to a
    single Sonnet call, and returns a NEW draft with BOTH bodies replaced as a unit. This is NOT
    a full writer re-run; `title`/`title_impact`/`pipeline_version` pass through unchanged.
    Fail-loud: an unparseable or incomplete revise output raises (parse_llm_json + a both-bodies
    presence check) — never a silent half-rewrite."""
    source_texts = _fact_base_source_texts(fact_base)
    source_block = (
        "\n".join(f"- {t}" for t in source_texts[:_REVISE_SOURCE_CAP])
        if source_texts else "(no source facts available)"
    )
    user = REVISE_PROMPT.format(
        feedback=feedback or "(no specific feedback)",
        source_facts=source_block,
        content_markdown=draft.get("content_markdown") or "",
        content_markdown_impact=draft.get("content_markdown_impact") or "",
    )
    text = _llm_call(
        llm_client, cfg["revise_model"], REVISE_SYSTEM, user,
        temperature=cfg["revise_temperature"], max_tokens=cfg["revise_max_tokens"],
    )
    bodies = parse_llm_json(text, context="layer2_revise")  # FAILS LOUD, never silent-empty
    tech = bodies.get("content_markdown")
    impact = bodies.get("content_markdown_impact")
    if (not isinstance(tech, str) or not tech.strip()
            or not isinstance(impact, str) or not impact.strip()):
        raise ValueError(
            "layer2 revise returned an incomplete draft — both content_markdown and "
            "content_markdown_impact must be non-empty strings (D-08 both-bodies unit)"
        )
    logger.info("run_layer2: targeted revise rewrote both bodies")
    return {**draft, "content_markdown": tech, "content_markdown_impact": impact}


def _attempt_row(
    attempt: int, *, eval_status: str, error: str | None, judge_scores: dict | None,
    feedback: str | None, reverify: dict | None, model_calls: list[dict] | None = None,
    failing: list[str] | None = None, summed_score: int = 0, draft: dict | None = None,
) -> dict:
    """Per-attempt telemetry object (RESEARCH §Pattern 9) — its persistable projection
    (`_persistable_attempt`) maps 1:1 onto the `edition_eval` row-write params
    (`layer='judge', attempt=k`) that Phase 30 persists; this module never writes — D-09/D-10.
    `reverify_flags` is the
    Layer-1 gate result for the attempt (attempt-0 = the passed-in `det_flags`; a rewrite = the
    per-rewrite re-check, or None when no http_client is injected). `model_calls` is the best-effort
    per-attempt `{model, purpose}` list (per-call tokens/sats are the proxy's authoritative settle,
    A3). `failing`, `summed_score`, and `draft` are INTERNAL-only (drive the D-11 best-attempt
    selection + return the best draft; NOT persisted / NOT eval-row-write params)."""
    return {
        "attempt": attempt,
        "eval_status": eval_status,
        "error": error,
        "judge_scores": judge_scores,
        "feedback": feedback,
        "reverify_flags": reverify,
        "sats": 0,               # best-effort; the proxy's wallet_transactions settle is authoritative (A3)
        "model_calls": model_calls or [],  # best-effort {model, purpose} per attempt (tokens/sats → Phase 30 reconcile)
        "failing": failing or [],   # internal-only (D-11 primary key: fewest failing dims)
        "summed_score": summed_score,  # internal-only (D-11 tie-break: highest summed score)
        "draft": draft,             # internal-only (D-11 returns the BEST attempt's draft, not the latest)
    }


# The per-attempt telemetry Phase 30 persists via the `edition_eval` row-write helper
# (layer='judge', attempt=k). `failing`/`summed_score`/`draft` are INTERNAL-only (drive the D-11
# best-attempt selection + return the best draft) and are NOT eval-row-write params —
# `_persistable_attempt` strips them (D-10).
_INTERNAL_ATTEMPT_KEYS = ("failing", "summed_score", "draft")


def _persistable_attempt(row: dict) -> dict:
    """Project a run_layer2 attempt row onto EXACTLY the persistable telemetry Phase 30 feeds the
    `edition_eval` row-write helper: {attempt, eval_status, error, judge_scores, feedback,
    reverify_flags, sats, model_calls}. Strips the internal-only D-11 selection keys
    (failing/summed_score/draft). The module itself NEVER writes — this is the 1:1 mapping contract
    (LOOP-03/LOOP-05, D-10). The projected shape maps onto the eval-row-write params as:
    attempt→attempt, eval_status→eval_status, error→error, reverify_flags→deterministic_flags,
    judge_scores→judge_scores, feedback→judge_feedback, sats→sats_spent, model_calls→model_calls
    (the verdict is the single top-level verdict; the `attempt` column disambiguates — respecting
    verdict-iff-ok)."""
    return {k: v for k, v in row.items() if k not in _INTERNAL_ATTEMPT_KEYS}


def _summed_score(judge_scores: dict) -> int:
    """Sum every NUMERIC per-dimension score across both bodies (the D-11 tie-break signal). A
    non-numeric continuity "n/a" (D-05) contributes nothing — it is not a scored dimension."""
    total = 0
    for body in ("technical", "impact"):
        for dim in _DIMENSIONS:
            score = judge_scores[body][dim]["score"]
            if _is_number(score):
                total += score
    return total


def _select_best_attempt(ok_attempts: list[dict]) -> dict:
    """D-11 best-attempt selection (Pattern 8). Among fully-judged, non-error attempts, return
    the one with the FEWEST failing dimensions; ties break by the HIGHEST summed per-dimension
    score across both bodies, then by the LATEST attempt. attempt-0 IS a candidate — a rewrite is
    not guaranteed to beat it. `ok_attempts` is non-empty whenever the loop reaches held_voice
    (attempt-0 is always judged)."""
    return sorted(
        ok_attempts,
        key=lambda a: (len(a["failing"]), -a["summed_score"], -a["attempt"]),
    )[0]


# ── The cross-attempt dedup cache (D-01, RESEARCH §Open Q1 Option a) ───────────────────────────
# `run_deterministic_gate` builds its per-call dedup cache FRESH inside each call
# (deterministic_gate.py:214) and takes NO cache param — so a naive re-run on every rewrite
# refetches every unchanged ref (Pitfall 3). This thin wrapper memoizes the injected client's
# GET/HEAD responses on the key `(method, url)` so unchanged owner/repo + URL refs are served from
# cache ACROSS the N=2 attempts and only NEWLY-introduced refs actually hit the network.
#
# SAFE for correctness (Open Q1): only `fabrication` outcomes (404 / >20% star-drift) are
# consequential, and those are stable under caching (a 404 is never retried; a 200 stays 200). The
# only interaction — caching a transient 5xx neuters the gate's within-call retry-once — affects
# `unverified` ONLY, which never holds or aborts (D-03). A delegate that RAISES (timeout / connect
# error) is NOT cached (the assignment never completes), so a transient error propagates to the
# gate's own retry path. The wrapper adds NO raw egress of its own: it only forwards to the gate's
# SSRF-guarded fetches (T-29-SSRF).
class _CachingHTTPClient:
    """Memoizing shim over the injected httpx client, exposing the SAME `get`/`head` surface
    `run_deterministic_gate`'s network layers call (deterministic_gate.py:497 GET, :676 HEAD)."""

    def __init__(self, client):
        self._client = client
        self._cache: dict[tuple, Any] = {}

    def get(self, url, *, headers=None, timeout=None, **kwargs):
        key = ("get", url)
        if key not in self._cache:  # MISS → delegate + store (an exception is NOT cached)
            self._cache[key] = self._client.get(url, headers=headers, timeout=timeout, **kwargs)
        return self._cache[key]

    def head(self, url, *, timeout=None, follow_redirects=None, **kwargs):
        key = ("head", url)
        if key not in self._cache:  # MISS → delegate + store (an exception is NOT cached)
            self._cache[key] = self._client.head(
                url, timeout=timeout, follow_redirects=follow_redirects, **kwargs
            )
        return self._cache[key]


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

    # Continuity applicability is a property of the corpus (D-05) — constant across attempts.
    # (Same predicate `_judge_draft` computes internally; hoisted so the loop reuses it.)
    continuity_applicable = not (
        prior_context.get("empty") or not prior_context.get("previous_editions")
    )

    # Log only the label/version + bounds (never raw draft prose or feedback at INFO —
    # log-injection discipline, T-29-LOG).
    logger.info("run_layer2: judging pipeline_version=%s (max_attempts=%d)",
                draft.get("pipeline_version"), cfg["max_attempts"])

    # ── The bounded N=2 feedback-rewrite loop (LOOP-02, Pattern 5) ──────────────────────────────
    # range(0, max_attempts+1) → attempts 0,1,2: the judge scores up to 3 drafts and there are AT
    # MOST 2 targeted revises (revise only when attempt_no > 0). No best-effort publish (LOOP-02).
    #
    # D-01: ONE `_CachingHTTPClient` per run_layer2 call so the Phase-28 per-call dedup cache
    # (rebuilt fresh inside every run_deterministic_gate — deterministic_gate.py:214) persists
    # ACROSS the N=2 attempts. Constructed ONLY when an http_client is injected; when http_client
    # is None the per-rewrite re-check does NOT run (zero-egress contract — the live Phase-30 caller
    # always injects a real httpx.Client, so the re-check is always active in production).
    caching_client = _CachingHTTPClient(http_client) if http_client is not None else None

    attempts: list[dict] = []
    current = draft
    feedback: str | None = None

    for attempt_no in range(0, cfg["max_attempts"] + 1):
        # attempt-0's reverify_flags IS the passed-in Layer-1 gate result (det_flags); a rewrite's
        # is the per-rewrite re-check result (or None when no http_client is injected — no re-check).
        reverify: dict | None = det_flags if attempt_no == 0 else None
        model_calls: list[dict] = []   # best-effort {model, purpose} for the calls this attempt made (A3)

        if attempt_no > 0:
            # LOOP-01/D-07/D-08: targeted revise of BOTH bodies, fixing exactly the failing dims.
            current = _revise_draft(current, feedback, fact_base, llm_client, cfg)
            model_calls.append({"model": cfg["revise_model"], "purpose": "revise"})

            # ── D-01 per-rewrite Layer-1 re-check ──────────────────────────────────────────────
            # Re-run the SAME deterministic engine that gated entry on the untrusted rewrite BEFORE
            # re-judging it — the `specificity` dimension pushes the writer to add named
            # entities/numbers, exactly when a rewrite would fabricate (T-29-FABRW). `prior_edition
            # =None` (Open Q3): GATE-07 is mechanical-only and can NEVER cause a false
            # held_fabrication; the `fabrication` signal is what D-02 keys off. The shared caching
            # client serves unchanged refs from cache; only newly-introduced refs hit the network.
            if caching_client is not None:
                reverify = run_deterministic_gate(current, fact_base, None,  # prior_edition=None (Open Q3)
                                                  http_client=caching_client,
                                                  github_token=github_token)
                if reverify.get("fabrication"):
                    # D-02: a rewrite that INVENTS a new entity/repo/URL is a HARD abort. Keep the
                    # fabrication-clean attempt-0 draft (NEVER the fabricated rewrite); the rejected
                    # rewrite's flags/scores live in telemetry ONLY (the operator can see what was
                    # invented, but a live fabrication is never one accidental approve from publish).
                    # verdict=held_fabrication is the loudest signal ("the rewrite hallucinated").
                    attempts.append(_attempt_row(
                        attempt_no, eval_status="ok", error=None, judge_scores=None,
                        feedback=feedback, reverify=reverify, model_calls=model_calls, draft=current,
                    ))
                    logger.info(
                        "run_layer2: held_fabrication — rewrite attempt %d introduced %d "
                        "fabrication flag(s); keeping the clean attempt-0 draft",
                        attempt_no, len(reverify["fabrication"]),
                    )
                    return {"final_draft": draft, "verdict": "held_fabrication",
                            "selected_attempt": 0, "attempts": attempts}
                # D-03: `unverified` / `mechanical` on the re-check ride to the attempt's
                # `reverify_flags` telemetry ONLY — a transient error (5xx / timeout / rate-limit) is
                # NOT evidence: it NEVER aborts and NEVER holds ("an error is not evidence").
            else:
                # WR-02 fail-loud: a revise ACTUALLY occurred but NO per-rewrite Layer-1 fabrication
                # re-check will run (no http_client injected). The returned rewrite is untrusted LLM
                # output and is UNVERIFIED for fabrication — make the gap LOUD rather than a silent
                # safety no-op on a missing input (fail-loud governance). The zero-egress test suite
                # deliberately revises without http_client; the live Phase-30 caller ALWAYS injects a
                # real httpx.Client, so this warning never fires in production.
                logger.warning(
                    "run_layer2: revising attempt %d WITHOUT a per-rewrite fabrication re-check "
                    "(no http_client injected) — the returned rewrite is UNVERIFIED for fabrication",
                    attempt_no,
                )

        logger.info("run_layer2: judging attempt %d", attempt_no)
        judged = _judge_draft(current, prior_context, llm_client, cfg)
        model_calls.append({"model": cfg["judge_model"], "purpose": "judge"})

        if judged["status"] == "error":
            # JUDGE-05: an un-scoreable judge is NOT evidence — escalate (does NOT hold), never a
            # fabricated 0. Return the fabrication-clean attempt-0 draft (A2): it is the only draft
            # guaranteed clean (each rewrite's re-check above proves the returned attempt-0 clean).
            attempts.append(_attempt_row(
                attempt_no, eval_status="error", error=judged["error"], judge_scores=None,
                feedback=feedback, reverify=reverify, model_calls=model_calls, draft=current,
            ))
            return {"final_draft": draft, "verdict": "escalated",
                    "selected_attempt": attempt_no, "attempts": attempts}

        scores = judged["scores"]
        filler = {version: _count_filler_hits(current.get(field) or "", cfg["filler_blacklist"])
                  for version, field in _BODIES}
        # WR-01: also capture WHICH blacklist phrases matched per body, so a filler-only
        # hedging_filler failure (passing judge score) can name the exact phrases to remove
        # instead of quoting the judge's clean-graded evidence.
        filler_matches = {version: [p for p in cfg["filler_blacklist"]
                                    if p.lower() in (current.get(field) or "").lower()]
                          for version, field in _BODIES}
        failing = _compute_failing_dims(scores, filler, cfg,
                                        continuity_applicable=continuity_applicable)
        attempts.append(_attempt_row(
            attempt_no, eval_status="ok", error=None, judge_scores=scores, feedback=None,
            reverify=reverify, model_calls=model_calls, failing=failing,
            summed_score=_summed_score(scores), draft=current,
        ))

        if not failing:
            # A rewrite fixed every failing dimension (or attempt-0 was already clean). Mechanical
            # -only Layer-1 flags never move the verdict off `passed` (D-12).
            return {"final_draft": current, "verdict": "passed",
                    "selected_attempt": attempt_no, "attempts": attempts}

        # A dimension still fails → build targeted feedback for the next revise. The mechanical
        # Layer-1 flags ride ONLY because a judge dim independently failed (LOOP-04/D-12); the
        # fabrication list is NEVER passed (fabrication never enters the loop).
        feedback = _build_feedback(scores, failing, (det_flags.get("mechanical") or None),
                                   filler_matches=filler_matches, cfg=cfg)
        # LOOP-03: record the feedback that produced the NEXT attempt on THIS attempt's telemetry
        # (Pattern 9 — `feedback` maps to the eval row's `judge_feedback`).
        attempts[-1]["feedback"] = feedback

    # ── N=2 exhausted, a dimension still fails → held_voice, NO best-effort publish (LOOP-02).
    # Return the BEST attempt by the D-11 tie-break (fewest fails → highest summed score → latest),
    # NOT necessarily the latest — consuming the per-attempt scoring the telemetry produced.
    ok_attempts = [a for a in attempts if a["eval_status"] == "ok"]
    best = _select_best_attempt(ok_attempts)
    logger.info("run_layer2: held_voice — best attempt=%d still fails dims=%s",
                best["attempt"], best["failing"])
    return {"final_draft": best["draft"], "verdict": "held_voice",
            "selected_attempt": best["attempt"], "attempts": attempts}
