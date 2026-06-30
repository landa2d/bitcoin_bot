"""Phase 28 — Layer 1 deterministic gate (no-LLM).

`run_deterministic_gate(draft, fact_base, prior_edition, *, http_client=None, github_token=None)`
runs BOTH body versions (technical + impact) and EMITS a single structured flags object —
it never acts (D-05): no DB write, no LLM call, no status flip, no verdict computation.

The flags object is the Phase 30 wiring surface, shaped to migration 045's
`deterministic_flags` JSONB:
    {fabrication: [...], unverified: [...], mechanical: [...], meta: {...}}
`unverified` is a first-class top-level key (D-01) — a transient/quota network failure is a
visible "could not verify" state, NEVER folded into `fabrication` and NEVER treated as a pass.

This plan (28-01) ships the fabrication core:
  - REUSE the calibrated `verify_draft` engine (verification.py) for tier-1 named-entity /
    tier-2 stat fabrication detection — inheriting the Edition-34-tuned ~0-tier1-FP stop-list;
    the engine is imported, never rebuilt (D-04).
  - Two net-new fabrication sub-checks layered thin ON TOP of the engine:
      * arXiv-ID membership (GATE-04) — the engine extracts-then-discards arXiv IDs
        (verification.py:287-289) and never tests membership; this closes that gap.
      * entity-merge per-source verbatim (GATE-05) — the engine's fact base is a flat union
        with no per-source provenance (verification.py:309); a composite present only
        split-across two sources is a fabricated merge.

The network layer (GATE-02/03 — GitHub repo+star, URL HEAD) and the mechanical-editorial
checks (GATE-06/07 — H1/title echo, reading-mode-label leak, recycled closer, duplicated stat)
are added by Plans 02 and 03 on top of this skeleton; the `http_client` / `github_token` seams
and the empty `unverified` / `mechanical` lists are already part of the stable contract here
(interface-first).
"""

import os
import re
import logging
from typing import Any

import httpx

from verification import verify_draft, _extract_claims_from_prose, _ARXIV_ID, _STATISTIC

logger = logging.getLogger("newsletter")

# ── Module constants (some consumed by later plans; defined here so the contract is stable) ──
# The canonical body-start marker — verbatim per block_pipeline.py:661 (two-hash, comma after
# "This"). Published bodies start here with no H1 (newsletter_poller.py:2120). Plan 03 uses it
# for the H1/title-echo mechanical check.
BODY_START_MARKER = "## Read This, Skip the Rest"

# GATE-06 reading-mode-label leak blacklist (operator-tunable; Plan 03 consumes it). Seeded
# from the code-derived writer scaffolding literals (`AUDIENCE:` — block_pipeline.py:347-350)
# plus the CONTEXT illustrative set. Multi-word uppercase scaffolding only — bare "IMPACT" /
# "Technical" are legitimate prose and are deliberately NOT blacklisted.
READING_MODE_LABELS = [
    "AUDIENCE:", "READING MODE", "BUILDER MODE", "IMPACT MODE",
    "TECHNICAL MODE", "STRATEGIC MODE", "TECHNICAL READING MODE",
    "IMPACT READING MODE", "STRATEGIC READING MODE",
    "TECHNICAL VERSION", "IMPACT VERSION", "STRATEGIC VERSION",
]

# Net-new regexes. Simple bounded character classes only — no nested quantifiers / no
# catastrophic backtracking (T-28-01 ReDoS mitigation).
_GITHUB_URL = re.compile(r'github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)', re.IGNORECASE)
_MD_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^)\s]+)\)')


def run_deterministic_gate(
    draft: dict,
    fact_base: dict,
    prior_edition: dict | None,
    *,
    http_client: httpx.Client | None = None,
    github_token: str | None = None,
) -> dict:
    """Run the no-LLM deterministic gate over both body versions. EMITS flags only — never
    acts (D-05): no DB write, no LLM call, no status flip, no verdict computed.

    Args:
        draft: {title, title_impact, content_markdown, content_markdown_impact,
                pipeline_version} — both bodies are processed.
        fact_base: the ALREADY-CORRECT in-memory fact base for this draft version — single-pass
            `input_data` OR a block_v1 dict {blocks, tracked_entity_signals, trending_tools,
            predictions}. The gate TRUSTS the handed dict (GATE-08); it does not re-derive which
            base to use — Phase 30 selects it via the existing poller branch.
        prior_edition: the FULL previous-published edition body (+ _impact) or None. Unused this
            plan (the recycled-closer / duplicated-stat checks are Plan 03); part of the
            interface-first contract.
        http_client: injectable httpx client (tests inject a fake). Unused this plan — the
            network layer (GATE-02/03) is Plan 02.
        github_token: GitHub token override; defaults to os.getenv('GITHUB_TOKEN'). Unused this
            plan; Plan 02 uses it.

    Returns:
        {fabrication: [...], unverified: [...], mechanical: [...], meta: {...}} — matching
        migration 045 deterministic_flags JSONB plus the first-class `unverified` key (D-01).
    """
    # Fail loud (carry-forward 27-CONTEXT "an error is not evidence"): a wrong/missing fact base
    # must surface, never silently verify against an empty/other base (T-28-03 / Pitfall 3).
    if not isinstance(fact_base, dict):
        raise ValueError(
            "run_deterministic_gate: fact_base must be a dict, got "
            f"{type(fact_base).__name__} — refusing to verify against a wrong/missing fact base"
        )

    # GATE-08 loud-path log: which path verify_draft will take. Log only the label (never raw
    # draft prose at INFO — T-28-02 log-injection mitigation).
    fact_base_path = "blocks" if fact_base.get("blocks") else "input_data"
    logger.info("deterministic_gate: verifying against fact_base_path=%s", fact_base_path)

    fabrication: list[dict[str, Any]] = []
    tier1_count = {"technical": 0, "impact": 0}

    # GATE-01: run BOTH body versions through the SAME engine (mirrors verify_draft tech+impact
    # at poller:1756-1757), aggregating into ONE flags object.
    versions = [
        ("technical", draft.get("content_markdown", "") or "", draft.get("title", "") or ""),
        ("impact", draft.get("content_markdown_impact", "") or "", draft.get("title_impact", "") or ""),
    ]

    # Per-source provenance for the two net-new fabrication sub-checks (GATE-04/05). Built once;
    # the flat engine union (verification.py:309) lacks this provenance.
    source_texts = _fact_base_source_texts(fact_base)

    for label, body, _title in versions:
        if not body.strip():
            continue

        # ── Reused engine (D-04): tier-1 named-entity fabrications (GATE-04/05 base) ──
        report = verify_draft(body, fact_base)
        for item in report.get("tier1_fabrications", []):
            fabrication.append({
                "kind": "tier1_entity",
                "value": item.get("value"),
                "version": label,
            })
        tier1_count[label] = report["summary"]["tier1_count"]

        # ── Net-new fabrication sub-checks layered ON TOP of the reused engine ──
        fabrication.extend(_check_arxiv_membership(body, source_texts, label))
        fabrication.extend(_check_entity_merge(body, source_texts, label))

    return {
        "fabrication": fabrication,
        # Network (Plan 02) populates `unverified`; mechanical (Plan 03) populates `mechanical`.
        # They stay empty here — and `unverified` is NEVER folded into fabrication/pass (D-01).
        "unverified": [],
        "mechanical": [],
        "meta": {
            "fact_base_path": fact_base_path,
            "github_checked": 0,
            "urls_checked": 0,
            "github_token_present": bool(github_token or os.getenv("GITHUB_TOKEN")),
            "tier1_count": tier1_count,
        },
    }


def _fact_base_source_texts(fact_base: dict) -> list[str]:
    """Return a PER-SOURCE (NOT unioned) list of raw text strings, mirroring the field
    accessors `_build_block_list` reads (verification.py:299-480) but keeping each item
    separate. This is the per-source provenance the flat engine union (verification.py:309)
    lacks — consumed by the arXiv-membership (GATE-04) and entity-merge (GATE-05) checks.

    Does NOT touch `_build_block_list`, `_STOP_WORDS`, or the tier classifier (FP-regression
    risk).
    """
    texts: list[str] = []

    blocks = fact_base.get("blocks") or []
    if blocks:
        # block_v1 path: each block contributes description + its named_entities.
        for block in blocks:
            ents = " ".join(str(e) for e in (block.get("named_entities") or []))
            texts.append(f"{block.get('description', '')} {ents}".strip())
        # Tracked entity signals (same shape as blocks) — block path only, mirroring the engine.
        for signal in fact_base.get("tracked_entity_signals", []) or []:
            ents = " ".join(str(e) for e in (signal.get("named_entities") or []))
            texts.append(f"{signal.get('description', '')} {ents}".strip())
    else:
        # single-pass path: each premium source post / emerging signal / cluster as its own item.
        for post in fact_base.get("premium_source_posts", []) or []:
            texts.append(
                f"{post.get('title', '')} {post.get('summary', '')} "
                f"{post.get('source_display', '')}".strip()
            )
        for signal in fact_base.get("section_b_emerging", []) or []:
            texts.append(f"{signal.get('theme', '')} {signal.get('description', '')}".strip())
        for cluster in fact_base.get("clusters", []) or []:
            texts.append(f"{cluster.get('theme', '')} {cluster.get('description', '')}".strip())

    # Tool / prediction text per item — read by the engine in BOTH paths (verification.py:407,432).
    for tool in fact_base.get("trending_tools", []) or []:
        name = tool.get("tool_name", "")
        alts = " ".join(str(a) for a in (tool.get("top_alternatives") or []))
        texts.append(f"{name} {alts}".strip())
    for pred in fact_base.get("predictions", []) or []:
        texts.append(
            str(pred.get("prediction_text", pred.get("prediction", pred.get("description", "")))).strip()
        )

    return [t for t in texts if t]


def _check_arxiv_membership(body: str, source_texts: list[str], version: str) -> list[dict]:
    """GATE-04: flag any arXiv ID in the body that does NOT appear verbatim in the concatenated
    fact-base source text. Closes the extract-then-discard gap (verification.py:287-289) — the
    engine removes arXiv IDs from the stat set but never tests membership. A real arXiv ID
    present in a source is clean (the ed-36 fake-arXiv golden fixture).
    """
    flags: list[dict] = []
    concatenated = " ".join(source_texts)
    seen: set[str] = set()
    for match in _ARXIV_ID.finditer(body):
        arxiv_id = match.group(0)
        if arxiv_id in seen:
            continue
        seen.add(arxiv_id)
        if arxiv_id not in concatenated:
            flags.append({
                "kind": "arxiv",
                "id": arxiv_id,
                "version": version,
                "detail": "arXiv ID not present in fact base",
            })
    return flags


def _check_entity_merge(body: str, source_texts: list[str], version: str) -> list[dict]:
    """GATE-05: the per-source verbatim entity-merge refinement (NOT a rebuild). Restrict to
    COMPOSITE entities — multi-word entities (`len(split()) >= 2`) from the reused
    `_extract_claims_from_prose`, plus any `owner/repo` token captured by `_GITHUB_URL` in the
    body. Flag a composite iff its full string does NOT appear (case-insensitive) within at
    least ONE single source string. Appearing only split-across separate sources == a fabricated
    merge (the engine's flat union + fuzzy substring match masks this — verification.py:499-514).
    Single-word entities are left entirely to the reused verify_draft tier1 path.
    """
    flags: list[dict] = []
    lowered_sources = [s.lower() for s in source_texts]

    composites: list[str] = []
    seen: set[str] = set()

    # Multi-word entities from the reused extractor (do NOT re-roll extraction).
    for entity in _extract_claims_from_prose(body).get("entities", []):
        if len(entity.split()) >= 2:
            key = entity.lower()
            if key not in seen:
                seen.add(key)
                composites.append(entity)

    # owner/repo tokens captured by the GitHub-URL regex in the body (the `/` breaks the
    # _PROPER_NOUN tokenizer, so the engine never sees these as single entities).
    for match in _GITHUB_URL.finditer(body):
        owner_repo = f"{match.group(1)}/{match.group(2)}"
        key = owner_repo.lower()
        if key not in seen:
            seen.add(key)
            composites.append(owner_repo)

    for composite in composites:
        c_lower = composite.lower()
        if not any(c_lower in src for src in lowered_sources):
            flags.append({
                "kind": "entity_merge",
                "entity": composite,
                "version": version,
            })
    return flags
