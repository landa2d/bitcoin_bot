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
import json
import logging
import sys
from pathlib import Path

import httpx
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
# Fake injectable httpx client double (Plan 02) — mirrors the test_26/test_27
# in-memory-stub-with-call-counter pattern (PATTERNS §"In-memory stub double").
# Maps each URL → a FIFO queue of outcomes; an outcome is either a
# (status_code, json_dict) tuple OR an Exception instance to raise. `.calls`
# records every requested URL so a test can assert D-02 retry-once and D-03 dedup.
# Injected via the gate's `http_client` param — NEVER monkeypatches the real
# network, so the suite has ZERO live egress (T-28-04/T-28-06 / verification gate).
# ──────────────────────────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json


class _FakeHTTPClient:
    """A dict of {url: [outcome, ...]}. An outcome is (status_code, json) or an Exception.
    FIFO with last-element-sticky semantics (a single queued outcome is reused for every
    call to that URL — so a 5xx queued once is returned on both retry attempts)."""

    def __init__(self, responses=None):
        self._responses = {k: list(v) for k, v in (responses or {}).items()}
        self.calls = []          # every requested URL, in order (get + head)

    def _next(self, url):
        self.calls.append(url)
        queue = self._responses.get(url)
        if not queue:
            raise AssertionError(f"_FakeHTTPClient: no queued response for {url!r}")
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(outcome, Exception):
            raise outcome
        code, json_data = outcome
        return _FakeResponse(code, json_data)

    def get(self, url, *, headers=None, timeout=None, **kwargs):
        return self._next(url)

    def head(self, url, *, timeout=None, follow_redirects=None, **kwargs):
        return self._next(url)


def _gh_body(line: str) -> str:
    """A published-shaped body whose single paragraph carries a github.com ref."""
    return _body(line)


def _gh_fact_base(*refs):
    """A single-pass fact base that grounds each owner/repo verbatim (so the entity-merge
    refinement stays quiet and only the network layer drives the github_* assertions)."""
    posts = [{"title": r, "summary": f"the project {r} is real and grounded in source.",
              "source_display": "HN"} for r in refs]
    return _single_pass_fact_base(premium_source_posts=posts)


_GH_API = "https://api.github.com/repos/{}/{}"


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


# ──────────────────────────────────────────────────────────────────────────────
# Plan 02 — SSRF guard (_is_safe_public_url): the URL HEAD layer (Task 2) gate.
# Built in Task 1 so the fixtures are shared. ASVS L1 (T-28-04).
# ──────────────────────────────────────────────────────────────────────────────


def test_ssrf_guard_rejects_internal_and_private():
    # Loopback, internal-service denylist, link-local metadata IP, non-http(s) scheme,
    # RFC-1918 private ranges, bare service names, and *.internal must all be rejected.
    assert gate._is_safe_public_url("http://127.0.0.1/x") is False
    assert gate._is_safe_public_url("http://llm-proxy:8200") is False
    assert gate._is_safe_public_url("http://169.254.169.254/") is False
    assert gate._is_safe_public_url("file:///etc/passwd") is False
    assert gate._is_safe_public_url("http://10.0.0.5/admin") is False
    assert gate._is_safe_public_url("http://172.16.4.4/") is False
    assert gate._is_safe_public_url("http://192.168.1.1/") is False
    assert gate._is_safe_public_url("http://supabase/rest/v1") is False
    assert gate._is_safe_public_url("http://gato_brain:8100/x") is False
    assert gate._is_safe_public_url("http://service.internal/x") is False
    assert gate._is_safe_public_url("http://[::1]/x") is False
    assert gate._is_safe_public_url("not-a-url") is False


def test_ssrf_guard_allows_public_https():
    assert gate._is_safe_public_url("https://github.com/a/b") is True
    assert gate._is_safe_public_url("https://example.com/path") is True
    assert gate._is_safe_public_url("http://docs.python.org/3/") is True


# ──────────────────────────────────────────────────────────────────────────────
# GATE-02 — GitHub repo existence + star-drift, D-01 three outcomes,
# D-02 retry-once (404 NEVER retried), D-03 per-run dedup, token hygiene.
# ──────────────────────────────────────────────────────────────────────────────


def test_github_404_fabrication_and_no_retry():
    body = _gh_body("the project lives at github.com/ghost/missing for reference.")
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    client = _FakeHTTPClient({_GH_API.format("ghost", "missing"): [(404, {})]})
    flags = gate.run_deterministic_gate(draft, _gh_fact_base("ghost/missing"), None,
                                        http_client=client)
    gh = [f for f in flags["fabrication"] if f["kind"] == "github_repo"]
    assert any(f["ref"] == "ghost/missing" and f["version"] == "technical" for f in gh)
    # D-02: a definitive 404 is NEVER retried — exactly one call.
    assert client.calls == [_GH_API.format("ghost", "missing")]
    # D-01: a 404 is a fabrication, NEVER an unverified entry.
    assert not any(u["kind"] == "github_repo" for u in flags["unverified"])
    assert flags["meta"]["github_checked"] == 1


def test_github_403_unverified_not_fabrication():
    body = _gh_body("see github.com/acme/tool for the code.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({_GH_API.format("acme", "tool"): [(403, {})]})
    flags = gate.run_deterministic_gate(draft, _gh_fact_base("acme/tool"), None,
                                        http_client=client)
    # D-01: a 403 quota wall is UNVERIFIED, never a fabrication flag.
    assert not any(f["kind"] == "github_repo" for f in flags["fabrication"])
    unv = [u for u in flags["unverified"] if u["kind"] == "github_repo"]
    assert any(u["ref"] == "acme/tool" and u["reason"] == "rate_limit_403" for u in unv)
    # D-02: quota is not transient — not retried.
    assert len(client.calls) == 1


def test_github_5xx_unverified_after_retry_once():
    body = _gh_body("repo at github.com/acme/tool here.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({_GH_API.format("acme", "tool"): [(500, {})]})
    flags = gate.run_deterministic_gate(draft, _gh_fact_base("acme/tool"), None,
                                        http_client=client)
    unv = [u for u in flags["unverified"] if u["kind"] == "github_repo"]
    assert any(u["reason"] == "server_error_5xx" for u in unv)
    assert not any(f["kind"] == "github_repo" for f in flags["fabrication"])
    # D-02: a transient 5xx is retried exactly once → exactly two calls.
    assert len(client.calls) == 2


def test_github_timeout_unverified_after_retry_once():
    body = _gh_body("repo at github.com/acme/tool here.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({_GH_API.format("acme", "tool"): [httpx.TimeoutException("t")]})
    flags = gate.run_deterministic_gate(draft, _gh_fact_base("acme/tool"), None,
                                        http_client=client)
    unv = [u for u in flags["unverified"] if u["kind"] == "github_repo"]
    assert any(u["reason"] == "timeout" for u in unv)
    assert len(client.calls) == 2  # retry-once on transient


def test_github_stars_drift_fabrication():
    body = _gh_body("the popular repo github.com/acme/tool boasts 50000 stars today.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({_GH_API.format("acme", "tool"): [(200, {"stargazers_count": 1000})]})
    flags = gate.run_deterministic_gate(draft, _gh_fact_base("acme/tool"), None,
                                        http_client=client)
    stars = [f for f in flags["fabrication"] if f["kind"] == "github_stars"]
    assert any(f["ref"] == "acme/tool" and f["version"] == "technical" for f in stars)
    assert len(client.calls) == 1


def test_github_stars_within_band_clean():
    body = _gh_body("the repo github.com/acme/tool has 1100 stars now.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({_GH_API.format("acme", "tool"): [(200, {"stargazers_count": 1000})]})
    flags = gate.run_deterministic_gate(draft, _gh_fact_base("acme/tool"), None,
                                        http_client=client)
    # 1100 vs 1000 == 10% drift, within the 20% band → no star flag.
    assert not any(f["kind"] == "github_stars" for f in flags["fabrication"])


def test_github_existence_only_no_star_flag():
    body = _gh_body("see github.com/acme/tool for the implementation details.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({_GH_API.format("acme", "tool"): [(200, {"stargazers_count": 1000})]})
    flags = gate.run_deterministic_gate(draft, _gh_fact_base("acme/tool"), None,
                                        http_client=client)
    # No asserted count → existence-only is sufficient, no star flag, no repo fabrication.
    assert not any(f["kind"] == "github_stars" for f in flags["fabrication"])
    assert not any(f["kind"] == "github_repo" for f in flags["fabrication"])


def test_github_dedup_same_repo_one_call():
    body = _gh_body("github.com/acme/tool is great. again github.com/acme/tool. "
                    "and once more github.com/acme/tool.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({_GH_API.format("acme", "tool"): [(200, {"stargazers_count": 1000})]})
    flags = gate.run_deterministic_gate(draft, _gh_fact_base("acme/tool"), None,
                                        http_client=client)
    # D-03: the same repo referenced 3× → exactly ONE GitHub call.
    assert len(client.calls) == 1
    assert flags["meta"]["github_checked"] == 1


def test_github_token_present_flag_and_never_leaked(caplog):
    caplog.set_level(logging.INFO)
    body = _gh_body("github.com/acme/tool reference here.")
    draft = _make_draft(content_markdown=body)
    secret = "ghp_THISISASECRETTOKENVALUE1234567890"
    client = _FakeHTTPClient({_GH_API.format("acme", "tool"): [(200, {"stargazers_count": 1000})]})
    flags = gate.run_deterministic_gate(draft, _gh_fact_base("acme/tool"), None,
                                        http_client=client, github_token=secret)
    # T-28-05: meta exposes only a bool; the literal token never appears in flags or logs.
    assert flags["meta"]["github_token_present"] is True
    assert secret not in json.dumps(flags)
    assert secret not in caplog.text


# ──────────────────────────────────────────────────────────────────────────────
# GATE-03 — URL HEAD liveness, D-01 three outcomes, D-02 retry-once,
# D-03 dedup, SSRF routing (unsafe host → unverified WITHOUT fetch).
# ──────────────────────────────────────────────────────────────────────────────


def _md(line: str) -> str:
    """A published-shaped body whose single paragraph carries a markdown link / bare URL."""
    return _body(line)


def test_url_dead_404_fabrication():
    url = "https://dead.example.com/page"
    body = _md(f"the documentation lives at [docs]({url}) for now.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({url: [(404, {})]})
    flags = gate.run_deterministic_gate(draft, _single_pass_fact_base(), None, http_client=client)
    dead = [f for f in flags["fabrication"] if f["kind"] == "dead_url"]
    assert any(f["url"] == url and f["version"] == "technical" for f in dead)
    assert flags["meta"]["urls_checked"] == 1


def test_url_410_dead_fabrication():
    url = "https://gone.example.com/old"
    body = _md(f"reference: [archive]({url}).")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({url: [(410, {})]})
    flags = gate.run_deterministic_gate(draft, _single_pass_fact_base(), None, http_client=client)
    assert any(f["kind"] == "dead_url" and f["url"] == url for f in flags["fabrication"])


def test_url_timeout_unverified_after_retry_once():
    url = "https://slow.example.com/x"
    body = _md(f"see [slow]({url}) here.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({url: [httpx.TimeoutException("t")]})
    flags = gate.run_deterministic_gate(draft, _single_pass_fact_base(), None, http_client=client)
    unv = [u for u in flags["unverified"] if u["kind"] == "url"]
    assert any(u["url"] == url and u["reason"] == "timeout" for u in unv)
    assert not any(f["kind"] == "dead_url" for f in flags["fabrication"])
    assert len(client.calls) == 2  # D-02: retry-once on transient


def test_url_conn_refused_unverified():
    url = "https://refused.example.com/x"
    body = _md(f"see [r]({url}) here.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({url: [httpx.ConnectError("refused")]})
    flags = gate.run_deterministic_gate(draft, _single_pass_fact_base(), None, http_client=client)
    unv = [u for u in flags["unverified"] if u["kind"] == "url"]
    assert any(u["url"] == url and u["reason"] == "conn_refused" for u in unv)
    assert len(client.calls) == 2


def test_url_5xx_unverified():
    url = "https://err.example.com/x"
    body = _md(f"see [e]({url}) here.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({url: [(503, {})]})
    flags = gate.run_deterministic_gate(draft, _single_pass_fact_base(), None, http_client=client)
    unv = [u for u in flags["unverified"] if u["kind"] == "url"]
    assert any(u["url"] == url and u["reason"] == "server_error_5xx" for u in unv)
    assert len(client.calls) == 2  # retry-once on transient 5xx


def test_url_403_unverified_not_fabrication():
    # "An error is not evidence" (D-01): an auth/rate wall is unverified, never fabricated.
    url = "https://wall.example.com/x"
    body = _md(f"see [w]({url}) here.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({url: [(403, {})]})
    flags = gate.run_deterministic_gate(draft, _single_pass_fact_base(), None, http_client=client)
    assert not any(f["kind"] == "dead_url" for f in flags["fabrication"])
    unv = [u for u in flags["unverified"] if u["kind"] == "url"]
    assert any(u["url"] == url and u["reason"] == "http_403" for u in unv)
    assert len(client.calls) == 1  # a 4xx wall is not transient — not retried


def test_url_unsafe_internal_host_no_fetch():
    # SSRF: an internal-service host is routed to unverified WITHOUT any request (T-28-04).
    url = "http://llm-proxy:8200/admin"
    body = _md(f"see [internal]({url}) here.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({})  # nothing queued — a fetch would raise
    flags = gate.run_deterministic_gate(draft, _single_pass_fact_base(), None, http_client=client)
    unv = [u for u in flags["unverified"] if u["kind"] == "url"]
    assert any(u["url"] == url and u["reason"] == "unsafe_host" for u in unv)
    assert client.calls == []  # ZERO egress — the guard short-circuits before any fetch


def test_url_unsafe_metadata_ip_no_fetch():
    url = "http://169.254.169.254/latest/meta-data/"
    body = _md(f"see [meta]({url}) here.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({})
    flags = gate.run_deterministic_gate(draft, _single_pass_fact_base(), None, http_client=client)
    assert any(u["kind"] == "url" and u["reason"] == "unsafe_host" for u in flags["unverified"])
    assert client.calls == []


def test_url_200_clean():
    url = "https://live.example.com/ok"
    body = _md(f"see [live]({url}) here.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({url: [(200, {})]})
    flags = gate.run_deterministic_gate(draft, _single_pass_fact_base(), None, http_client=client)
    assert not any(f["kind"] == "dead_url" for f in flags["fabrication"])
    assert not any(u["kind"] == "url" for u in flags["unverified"])
    assert flags["meta"]["urls_checked"] == 1


def test_url_dedup_single_head_call():
    url = "https://dup.example.com/x"
    body = _md(f"first [a]({url}) and again [b]({url}).")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({url: [(200, {})]})
    flags = gate.run_deterministic_gate(draft, _single_pass_fact_base(), None, http_client=client)
    # D-03: a duplicate URL is HEAD-checked exactly once.
    assert client.calls == [url]
    assert flags["meta"]["urls_checked"] == 1


def test_url_github_excluded_from_head():
    # github.com/owner/repo URLs are handled by the GitHub API layer — NOT double-HEAD-checked.
    gh_url = "https://github.com/acme/tool"
    body = _md(f"the repo is at [repo]({gh_url}).")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({_GH_API.format("acme", "tool"): [(200, {"stargazers_count": 100})]})
    flags = gate.run_deterministic_gate(draft, _gh_fact_base("acme/tool"), None, http_client=client)
    # Only the GitHub API GET happened; the URL HEAD layer skipped the github.com link.
    assert client.calls == [_GH_API.format("acme", "tool")]
    assert flags["meta"]["urls_checked"] == 0
    assert flags["meta"]["github_checked"] == 1


def test_url_response_body_never_in_flags():
    # T-28-08: only the status code drives the outcome; a response body is never stored.
    url = "https://dead.example.com/x"
    body = _md(f"see [d]({url}) here.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({url: [(404, {"secret_body": "SHOULD_NEVER_APPEAR"})]})
    flags = gate.run_deterministic_gate(draft, _single_pass_fact_base(), None, http_client=client)
    assert "SHOULD_NEVER_APPEAR" not in json.dumps(flags)


# ──────────────────────────────────────────────────────────────────────────────
# GATE-06 (Plan 03) — mechanical-editorial checks: H1/title echo + reading-mode-label
# leak via the tunable READING_MODE_LABELS blacklist. These flags land under
# `mechanical` (NEVER `fabrication`) — they may feed the Phase 29 rewrite loop, never a
# hard fabrication hold. No bare-word ("impact"/"Technical") false positives.
# ──────────────────────────────────────────────────────────────────────────────


def test_mechanical_gate06_h1_in_body():
    # A single-hash `# ` H1 line in the body (bodies must start at the `##` marker, no H1).
    body = f"{gate.BODY_START_MARKER}\n\n# Some Title\n\nSome content here.\n"
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), None)
    kinds = [m["kind"] for m in flags["mechanical"]]
    assert "h1_in_body" in kinds
    assert any(m["kind"] == "h1_in_body" and m["version"] == "technical"
               for m in flags["mechanical"])


def test_mechanical_gate06_clean_body_no_h1():
    # A clean body that starts at the `## Read This, Skip the Rest` marker → no h1 flag.
    draft = _make_draft(content_markdown=_clean_body(), content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), None)
    assert not any(m["kind"] == "h1_in_body" for m in flags["mechanical"])


def test_mechanical_gate06_title_echo():
    # A header line that echoes the edition title → a title_echo mechanical flag.
    body = f"{gate.BODY_START_MARKER}\n\n## Test Edition\n\nSome content here.\n"
    draft = _make_draft(title="Test Edition", content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), None)
    echoes = [m for m in flags["mechanical"] if m["kind"] == "title_echo"]
    assert any(m["version"] == "technical" and m["value"] == "Test Edition" for m in echoes)


def test_mechanical_gate06_title_echo_impact_uses_title_impact():
    # The impact body echoing title_impact → title_echo on the impact version.
    body = f"{gate.BODY_START_MARKER}\n\n### Impact Edition Title\n\nContent.\n"
    draft = _make_draft(title="Technical Title", title_impact="Impact Edition Title",
                        content_markdown="", content_markdown_impact=body)
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), None)
    echoes = [m for m in flags["mechanical"] if m["kind"] == "title_echo"]
    assert any(m["version"] == "impact" and m["value"] == "Impact Edition Title" for m in echoes)


def test_mechanical_gate06_reading_mode_label_leak():
    # A leaked `AUDIENCE:` scaffolding label → a reading_mode_leak flag with the matched label.
    body = _body("AUDIENCE: Technical builders and infrastructure teams. The week was busy.")
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), None)
    leaks = [m for m in flags["mechanical"] if m["kind"] == "reading_mode_leak"]
    assert any(m["version"] == "technical" and m["label"] == "AUDIENCE:" for m in leaks)


def test_mechanical_gate06_bare_word_no_label_leak():
    # Bare "impact"/"Technical" in legitimate prose must NOT trip the label blacklist.
    body = _body("This release will have a big impact on Technical teams everywhere.")
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), None)
    assert not any(m["kind"] == "reading_mode_leak" for m in flags["mechanical"])


def test_mechanical_gate06_labels_are_tunable_module_constant():
    # READING_MODE_LABELS is a module-level constant; bare single words are absent from it.
    assert isinstance(gate.READING_MODE_LABELS, list)
    assert "AUDIENCE:" in gate.READING_MODE_LABELS
    # the bare-word false-positive guard: neither bare "IMPACT" nor "Technical" is blacklisted
    assert "IMPACT" not in gate.READING_MODE_LABELS
    assert "Technical" not in gate.READING_MODE_LABELS


def test_mechanical_gate06_flags_under_mechanical_not_fabrication():
    # Mechanical flags stay distinct from fabrication (never a hard hold).
    body = f"{gate.BODY_START_MARKER}\n\n# Echoed H1\n\nAUDIENCE: Technical builders.\n"
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), None)
    mech_kinds = {m["kind"] for m in flags["mechanical"]}
    assert "h1_in_body" in mech_kinds
    assert "reading_mode_leak" in mech_kinds
    # none of the mechanical kinds leaked into fabrication
    assert not any(f["kind"] in ("h1_in_body", "title_echo", "reading_mode_leak")
                   for f in flags["fabrication"])


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
