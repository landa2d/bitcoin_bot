#!/usr/bin/env python3
"""
Phase 28 / Plan 01 — golden-draft fixture suite for `run_deterministic_gate`.

Locks the Layer-1 deterministic-gate contract BEFORE any Phase 30 caller wires it into
`newsletter_poller`:
  - GATE-01: BOTH body versions (technical + impact) are processed into ONE flags object,
  - the flags object has EXACTLY the four first-class top-level keys
    {fabrication, unverified, mechanical, meta} — `unverified` is never folded away (D-01),
  - GATE-08: the gate TRUSTS the handed fact_base and logs which path verify_draft will
    take (`meta.fact_base_path` == 'blocks' for block_v1, 'input_data' for single-pass),
  - GATE-04: a fake arXiv ID absent from the fact-base source text → a `kind=='arxiv'`
    fabrication; a real arXiv ID present in a source is clean,
  - GATE-05: a composite entity present only split-across two separate sources → a
    `kind=='entity_merge'` fabrication; a composite present verbatim in ONE source is clean,
  - named-study / benchmark fabrications (ed-36 "MCP authentication", ed-34 "GroupMemBench")
    surface via the reused verify_draft tier1 path.

This test imports the REAL `deterministic_gate` module (no re-implementation — the
test_19_smartquote rule). A copy could pass while production regresses. `deterministic_gate`
imports `verification` (which imports only stdlib `re`/`typing`) and takes `fact_base` as a
parameter, so a plain sys.path insert makes both the gate and its engine importable — no
conftest preload required. NO network: every assertion runs with `http_client=None` against
in-memory fixture dicts — never the live DB, never GitHub, never the network.
"""
import logging
import sys
from pathlib import Path

import pytest

# Put docker/newsletter on sys.path and import the REAL production module. The gate's bare
# `from verification import ...` resolves once NL_DIR is on the path (verification.py imports
# only `re`/`typing` — no `schemas` collision, so no conftest preload is needed).
NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
if str(NL_DIR) not in sys.path:
    sys.path.insert(0, str(NL_DIR))

import deterministic_gate as gate  # noqa: E402  — the REAL production module


# ──────────────────────────────────────────────────────────────────────────────
# Fixture builders — small helpers that build the draft + fact_base dicts carrying
# every field the gate / engine reads. Hand-authored markdown bodies start with the
# canonical body-start marker (no H1), mirroring published bodies.
# ──────────────────────────────────────────────────────────────────────────────


def _make_draft(*, title="Test Edition", title_impact="Test Edition (Impact)",
                content_markdown="", content_markdown_impact="",
                pipeline_version="block_v1"):
    """Build a draft dict with the title/body fields the gate reads for both versions."""
    return {
        "title": title,
        "title_impact": title_impact,
        "content_markdown": content_markdown,
        "content_markdown_impact": content_markdown_impact,
        "pipeline_version": pipeline_version,
    }


def _single_pass_fact_base(*, premium_source_posts=None, section_b_emerging=None,
                           clusters=None, trending_tools=None, predictions=None):
    """Single-pass fact base (no `blocks` key → verify_draft takes the input_data path)."""
    return {
        "premium_source_posts": premium_source_posts or [],
        "section_b_emerging": section_b_emerging or [],
        "clusters": clusters or [],
        "trending_tools": trending_tools or [],
        "predictions": predictions or [],
    }


def _block_fact_base(*, blocks=None, tracked_entity_signals=None,
                     trending_tools=None, predictions=None):
    """block_v1 fact base (non-empty `blocks` → verify_draft takes the block path)."""
    return {
        "blocks": blocks or [{"description": "", "named_entities": []}],
        "tracked_entity_signals": tracked_entity_signals or [],
        "trending_tools": trending_tools or [],
        "predictions": predictions or [],
    }


def _body(sentence: str) -> str:
    """A minimal published-shaped body: the canonical marker (no H1) then one paragraph."""
    return f"{gate.BODY_START_MARKER}\n\n{sentence}\n"


def _clean_body() -> str:
    """A benign body with no capitalized non-stop entities (low fabrication noise)."""
    return _body("This week brought steady progress across the ecosystem with no surprises.")


def _body_with_study(name: str) -> str:
    """A body naming an invented multi-word benchmark (→ a tier1 fabrication when ungrounded)."""
    return _body(f"The newly released **{name} Benchmark Suite** reportedly outperforms the rest.")


# ──────────────────────────────────────────────────────────────────────────────
# GATE-01 + flags-shape contract
# ──────────────────────────────────────────────────────────────────────────────


def test_shape_has_four_top_level_keys():
    draft = _make_draft(content_markdown=_clean_body(), content_markdown_impact=_clean_body())
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), None)
    assert set(flags.keys()) == {"fabrication", "unverified", "mechanical", "meta"}
    # unverified is first-class and stays empty this plan (D-01 — never folded into fabrication)
    assert flags["unverified"] == []
    assert flags["mechanical"] == []
    assert isinstance(flags["fabrication"], list)


def test_factbase_meta_keys_present():
    draft = _make_draft(content_markdown=_clean_body(), content_markdown_impact=_clean_body())
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), None)
    meta = flags["meta"]
    for key in ("fact_base_path", "github_checked", "urls_checked",
                "github_token_present", "tier1_count"):
        assert key in meta
    # network counters are zero this plan (no network layer until Plan 02)
    assert meta["github_checked"] == 0
    assert meta["urls_checked"] == 0
    assert set(meta["tier1_count"].keys()) == {"technical", "impact"}


def test_gate01_both_versions_processed():
    # An invented study in BOTH bodies → the single flags object carries both version labels.
    draft = _make_draft(
        content_markdown=_body_with_study("TechBenchAlpha"),
        content_markdown_impact=_body_with_study("ImpactBenchBeta"),
    )
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), None)
    versions = {f["version"] for f in flags["fabrication"]}
    assert "technical" in versions
    assert "impact" in versions
    # both versions recorded a tier1 count in meta
    assert flags["meta"]["tier1_count"]["technical"] >= 1
    assert flags["meta"]["tier1_count"]["impact"] >= 1


def test_gate01_no_network_call_with_client_none():
    # The whole Plan-01 path runs with http_client=None and never touches the network.
    draft = _make_draft(content_markdown=_clean_body(), content_markdown_impact=_clean_body())
    flags = gate.run_deterministic_gate(draft, _single_pass_fact_base(), None, http_client=None)
    # No network means the network counters stay zero and unverified stays empty.
    assert flags["unverified"] == []
    assert flags["meta"]["github_checked"] == 0


# ──────────────────────────────────────────────────────────────────────────────
# GATE-08 — fact-base path is trusted + logged, both shapes run without error
# ──────────────────────────────────────────────────────────────────────────────


def test_gate08_factbase_path_blocks():
    draft = _make_draft(content_markdown=_clean_body(), content_markdown_impact=_clean_body())
    fb = _block_fact_base(blocks=[{"description": "OpenClaw ships a framework.",
                                   "named_entities": ["OpenClaw"]}])
    flags = gate.run_deterministic_gate(draft, fb, None)
    assert flags["meta"]["fact_base_path"] == "blocks"


def test_gate08_factbase_path_input_data():
    draft = _make_draft(content_markdown=_clean_body(), content_markdown_impact=_clean_body())
    fb = _single_pass_fact_base(premium_source_posts=[
        {"title": "OpenClaw ships", "summary": "A framework.", "source_display": "HN"},
    ])
    flags = gate.run_deterministic_gate(draft, fb, None)
    assert flags["meta"]["fact_base_path"] == "input_data"


def test_gate08_both_paths_run_without_error():
    draft = _make_draft(content_markdown=_clean_body(), content_markdown_impact=_clean_body())
    # Neither shape may raise — verify_draft branches internally on .get('blocks').
    gate.run_deterministic_gate(draft, _block_fact_base(), None)
    gate.run_deterministic_gate(draft, _single_pass_fact_base(), None)


def test_gate08_non_dict_factbase_fails_loud():
    # Fail loud (carry-forward 27-CONTEXT "an error is not evidence"): a wrong/missing
    # fact base must raise, never silently verify against an empty base.
    draft = _make_draft(content_markdown=_clean_body())
    with pytest.raises(ValueError):
        gate.run_deterministic_gate(draft, None, None)


# ──────────────────────────────────────────────────────────────────────────────
# GATE-04 / GATE-05 — named-study tier1, arXiv-ID membership, entity-merge per-source
# ──────────────────────────────────────────────────────────────────────────────


def test_study_groupmem_tier1_fabrication():
    # ed-34 invented benchmark — caught by the reused verify_draft tier1 path.
    body = _body("Researchers introduced **GroupMemBench**, a memory benchmark, this week.")
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), None)
    values = [f.get("value") for f in flags["fabrication"] if f["kind"] == "tier1_entity"]
    assert "GroupMemBench" in values


def test_study_mcp_auth_fabrication():
    # ed-36 invented "MCP authentication" study — a multi-word tier1 fabrication.
    body = _body("The **MCP Authentication Security Study** claims a breakthrough, with no source.")
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), None)
    values = [f.get("value") for f in flags["fabrication"] if f["kind"] == "tier1_entity"]
    assert "MCP Authentication Security Study" in values


def test_arxiv_fake_id_fabrication():
    # A fake arXiv ID absent from the fact-base source text → a kind=='arxiv' fabrication.
    body = _body("A new method in arXiv 2605.99999 changes everything, allegedly.")
    fb = _single_pass_fact_base(premium_source_posts=[
        {"title": "Real work", "summary": "Discusses methods.", "source_display": "arXiv"},
    ])
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, fb, None)
    arxiv_flags = [f for f in flags["fabrication"] if f["kind"] == "arxiv"]
    assert any(f["id"] == "2605.99999" and f["version"] == "technical" for f in arxiv_flags)


def test_arxiv_real_id_clean():
    # A real arXiv ID present verbatim in a source summary → NO arxiv fabrication flag.
    body = _body("The paper arXiv 2605.12673 is discussed in depth here.")
    fb = _single_pass_fact_base(premium_source_posts=[
        {"title": "Paper roundup", "summary": "Covers arXiv 2605.12673 in detail.",
         "source_display": "arXiv"},
    ])
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, fb, None)
    arxiv_flags = [f for f in flags["fabrication"] if f["kind"] == "arxiv"]
    assert arxiv_flags == []


def test_entity_merge_split_across_sources_fabrication():
    # Source A names "Acme", source B names "widgets"; neither contains "Acme Widgets"
    # verbatim → a kind=='entity_merge' fabrication (the fabricated cross-source merge).
    body = _body("The new tool **Acme Widgets** launched to great fanfare this week.")
    fb = _single_pass_fact_base(premium_source_posts=[
        {"title": "Acme raises funding", "summary": "Acme is an organization doing things.",
         "source_display": "HN"},
        {"title": "Widgets are popular", "summary": "Many widgets shipped recently.",
         "source_display": "HN"},
    ])
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, fb, None)
    merge_flags = [f for f in flags["fabrication"] if f["kind"] == "entity_merge"]
    assert any(f["entity"] == "Acme Widgets" for f in merge_flags)


def test_entity_merge_single_source_verbatim_clean():
    # The composite appears verbatim within ONE source → NO entity_merge flag.
    body = _body("The new tool **Acme Widgets** launched to great fanfare this week.")
    fb = _single_pass_fact_base(premium_source_posts=[
        {"title": "Acme Widgets launches", "summary": "Acme Widgets is a single product.",
         "source_display": "HN"},
    ])
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, fb, None)
    merge_flags = [f for f in flags["fabrication"] if f["kind"] == "entity_merge"]
    assert not any(f["entity"] == "Acme Widgets" for f in merge_flags)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
