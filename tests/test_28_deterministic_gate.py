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


@pytest.fixture(autouse=True)
def _stub_dns(monkeypatch):
    """Default resolver stub for the SSRF guard's resolve-then-validate step (CR-01 / WR-02).

    The guard now RESOLVES every non-denylisted dotted host (so a non-canonical numeric form or a
    public hostname pointing at internal space cannot slip past the string checks). Without a stub
    every URL-layer test would perform REAL DNS — live egress (T-28-04) and flaky/offline-hostile.
    This autouse fixture makes every hostname resolve to ONE public IP by default, so the suite
    has ZERO live egress. The SSRF-specific tests below override gate._resolve_host on the SAME
    monkeypatch instance to point a host at a loopback / RFC-1918 / link-local / metadata IP."""
    monkeypatch.setattr(gate, "_resolve_host", lambda host: ["93.184.216.34"])  # a public IP


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


def test_gate_non_dict_draft_fails_loud():
    # WR-04: `draft` must be validated symmetrically with `fact_base` — a None/non-dict draft
    # raises a clear ValueError, not a bare AttributeError deep in the body.
    with pytest.raises(ValueError):
        gate.run_deterministic_gate(None, _block_fact_base(), None)
    with pytest.raises(ValueError):
        gate.run_deterministic_gate("not a draft", _block_fact_base(), None)


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


def test_arxiv_fake_id_substring_of_real_id_still_flagged():
    # WR-03: a fabricated 4-fraction ID (2605.9999) that is a SUBSTRING of a longer real ID in a
    # source (2605.99999) must still be flagged — the old unanchored `in concatenated` test
    # silently grounded it. Anchored set membership keeps it a fabrication.
    body = _body("A new method in arXiv 2605.9999 changes everything, allegedly.")
    fb = _single_pass_fact_base(premium_source_posts=[
        {"title": "Real paper", "summary": "Covers arXiv 2605.99999 in detail.",
         "source_display": "arXiv"},
    ])
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, fb, None)
    arxiv = [f for f in flags["fabrication"] if f["kind"] == "arxiv"]
    assert any(f["id"] == "2605.9999" and f["version"] == "technical" for f in arxiv)


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


def test_entity_merge_noncontiguous_within_single_source_clean():
    # WR-01 case A: both parts live in ONE source but not contiguously ("Acme's Widgets" — the
    # apostrophe-s breaks the verbatim match). This is a phrasing variant the tier-1 fuzzy path
    # owns, NOT a fabricated cross-source merge → must NOT be flagged entity_merge (hard-hold FP).
    body = _body("The new tool **Acme Widgets** launched to great fanfare this week.")
    fb = _single_pass_fact_base(premium_source_posts=[
        {"title": "Acme news", "summary": "Acme's Widgets are popular.", "source_display": "HN"},
    ])
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, fb, None)
    assert not any(f["kind"] == "entity_merge" and f["entity"] == "Acme Widgets"
                   for f in flags["fabrication"])


def test_entity_merge_live_repo_not_double_flagged():
    # WR-01 case B: a github.com/owner/repo ref the GitHub layer verifies LIVE (HTTP 200) must
    # never simultaneously be branded a fabricated entity_merge, even when the text fact base
    # lacks the literal "owner/repo" token.
    body = _body("the kernel lives at github.com/torvalds/linux for reference.")
    fb = _single_pass_fact_base(premium_source_posts=[
        {"title": "Kernel news", "summary": "The linux kernel keeps shipping.",
         "source_display": "HN"},
    ])
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    client = _FakeHTTPClient({_GH_API.format("torvalds", "linux"): [(200, {"stargazers_count": 1})]})
    flags = gate.run_deterministic_gate(draft, fb, None, http_client=client)
    # GATE-02 verified it live → no github_repo fabrication ...
    assert not any(f["kind"] == "github_repo" for f in flags["fabrication"])
    # ... and GATE-05 must NOT contradict that by flagging it a fabricated merge.
    assert not any(f["kind"] == "entity_merge" and f["entity"] == "torvalds/linux"
                   for f in flags["fabrication"])


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


def test_ssrf_guard_rejects_noncanonical_ip_encodings(monkeypatch):
    # CR-01: shorthand / octal / hex numeric hosts that ipaddress.ip_address rejects but the OS
    # resolver collapses to loopback / RFC-1918 / the 169.254.169.254 metadata IP. The guard must
    # resolve-then-validate and reject every one (the OLD string-only guard returned True for all).
    mapping = {
        "127.1": "127.0.0.1",                  # shorthand loopback
        "0x7f.0.0.1": "127.0.0.1",             # hex loopback
        "0177.0.0.1": "127.0.0.1",             # octal loopback
        "10.1": "10.0.0.1",                    # shorthand RFC-1918
        "0xa9.0xfe.0xa9.0xfe": "169.254.169.254",  # hex cloud-metadata IP
    }
    monkeypatch.setattr(gate, "_resolve_host", lambda host: [mapping[host]])
    for host in mapping:
        assert gate._is_safe_public_url(f"http://{host}/") is False, host


def test_ssrf_guard_rejects_public_hostname_pointing_internal(monkeypatch):
    # WR-02 (DNS rebinding / public name → internal A record): a dotted public-looking hostname
    # whose resolved address is loopback / RFC-1918 / link-local must be rejected.
    monkeypatch.setattr(gate, "_resolve_host", lambda host: ["127.0.0.1"])
    assert gate._is_safe_public_url("http://attacker-controlled.example.com/") is False
    monkeypatch.setattr(gate, "_resolve_host", lambda host: ["10.5.5.5"])
    assert gate._is_safe_public_url("http://rebind.example.org/x") is False
    monkeypatch.setattr(gate, "_resolve_host", lambda host: ["169.254.169.254"])
    assert gate._is_safe_public_url("http://metadata.example.net/latest/") is False


def test_ssrf_guard_rejects_if_any_resolved_addr_is_internal(monkeypatch):
    # Multi-homed: if ANY resolved address is internal the host is unsafe (a public answer must
    # not launder an internal one).
    monkeypatch.setattr(gate, "_resolve_host", lambda host: ["93.184.216.34", "10.0.0.9"])
    assert gate._is_safe_public_url("http://multi.example.com/") is False


def test_ssrf_guard_fail_closed_on_resolution_failure(monkeypatch):
    # Fail-closed: an unresolvable host (OSError) routes to unsafe — never fetched (zero egress).
    def _boom(host):
        raise OSError("name resolution failed")
    monkeypatch.setattr(gate, "_resolve_host", _boom)
    assert gate._is_safe_public_url("http://nonexistent.invalid/") is False


def test_ssrf_guard_url_layer_rejects_noncanonical_loopback_no_fetch(monkeypatch):
    # End-to-end: a non-canonical loopback host in a draft URL routes to unverified=unsafe_host
    # through run_deterministic_gate WITHOUT any fetch (T-28-04 zero egress).
    url = "http://127.1/admin"
    body = _md(f"see [internal]({url}) here.")
    draft = _make_draft(content_markdown=body)
    monkeypatch.setattr(gate, "_resolve_host", lambda host: ["127.0.0.1"])
    client = _FakeHTTPClient({})  # nothing queued — any fetch would raise
    flags = gate.run_deterministic_gate(draft, _single_pass_fact_base(), None, http_client=client)
    assert any(u["kind"] == "url" and u["url"] == url and u["reason"] == "unsafe_host"
               for u in flags["unverified"])
    assert client.calls == []


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


# ──────────────────────────────────────────────────────────────────────────────
# GATE-07 (Plan 03) — cross-edition mechanical checks vs the FULL prior published
# edition: recycled closer line + verbatim-duplicated numeric stat. D-06 normalized-
# exact matching (lowercase + collapse whitespace + strip trailing punctuation) — NO
# fuzzy threshold. prior_edition=None is a clean skip (no flags, no raise).
# ──────────────────────────────────────────────────────────────────────────────


def _prior_edition(*, content_markdown="", content_markdown_impact="", edition_number=42):
    """A stubbed FULL prior-published edition dict (Phase-30 supplies the real one)."""
    return {
        "content_markdown": content_markdown,
        "content_markdown_impact": content_markdown_impact,
        "edition_number": edition_number,
    }


def test_mechanical_gate07_recycled_closer():
    closer = "Until next week, keep building the future."
    prior = _prior_edition(content_markdown=_body(f"Last week was eventful.\n\n{closer}"),
                           edition_number=42)
    body = _body(f"This week had a different lead story.\n\n{closer}")
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), prior)
    rc = [m for m in flags["mechanical"] if m["kind"] == "recycled_closer"]
    assert any(m["version"] == "technical" and m["prior_edition"] == 42 for m in rc)


def test_mechanical_gate07_recycled_closer_normalized_match():
    # Differ ONLY by trailing punctuation, casing, and whitespace → still matches (D-06).
    prior = _prior_edition(content_markdown=_body("Lead.\n\nUntil next week, keep building."),
                           edition_number=7)
    body = _body("Other lead.\n\nuntil   next week,   KEEP building")
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), prior)
    assert any(m["kind"] == "recycled_closer" for m in flags["mechanical"])


def test_mechanical_gate07_recycled_closer_distinct_no_flag():
    prior = _prior_edition(content_markdown=_body("Lead.\n\nUntil next week, keep building."),
                           edition_number=7)
    body = _body("Other lead.\n\nSee you in a fortnight, friends.")
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), prior)
    assert not any(m["kind"] == "recycled_closer" for m in flags["mechanical"])


def test_mechanical_gate07_duplicated_stat():
    prior = _prior_edition(content_markdown=_body("Adoption hit 42% last week."),
                           edition_number=42)
    body = _body("This quarter adoption reached 42% across the board, a fresh milestone.")
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), prior)
    dup = [m for m in flags["mechanical"] if m["kind"] == "duplicated_stat"]
    assert any(m["stat"] == "42%" and m["version"] == "technical"
               and m["prior_edition"] == 42 for m in dup)


def test_mechanical_gate07_duplicated_stat_current_only_no_flag():
    prior = _prior_edition(content_markdown=_body("Nothing numeric in here at all."),
                           edition_number=42)
    body = _body("This quarter adoption reached 42% across the board.")
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), prior)
    assert not any(m["kind"] == "duplicated_stat" for m in flags["mechanical"])


def test_mechanical_gate07_cross_edition_impact_version():
    # The impact body compares against prior_edition['content_markdown_impact'].
    closer = "That is the impact view for this edition."
    prior = _prior_edition(content_markdown_impact=_body(f"Impact lead.\n\n{closer}"),
                           edition_number=11)
    body = _body(f"A different impact lead.\n\n{closer}")
    draft = _make_draft(content_markdown="", content_markdown_impact=body)
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), prior)
    rc = [m for m in flags["mechanical"] if m["kind"] == "recycled_closer"]
    assert any(m["version"] == "impact" and m["prior_edition"] == 11 for m in rc)


def test_mechanical_gate07_prior_none_skips_cleanly():
    # prior_edition=None → no GATE-07 flags and no raise (GATE-06 still runs).
    body = _body("Adoption reached 42%. Until next week, keep building.")
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), None)
    assert not any(m["kind"] in ("recycled_closer", "duplicated_stat")
                   for m in flags["mechanical"])


def test_mechanical_gate07_no_fuzzy_threshold():
    # A near-but-not-normalized-equal closer must NOT match (normalized-exact only, D-06).
    prior = _prior_edition(content_markdown=_body("Lead.\n\nUntil next week, keep building."),
                           edition_number=7)
    body = _body("Other.\n\nUntil next week, keep building great things.")  # extra words
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, _block_fact_base(), prior)
    assert not any(m["kind"] == "recycled_closer" for m in flags["mechanical"])


# ──────────────────────────────────────────────────────────────────────────────
# Task 3 (Plan 03) — combined golden-draft integration suite. ONE realistic offender
# draft per fact-base path (single-pass input_data + block_v1 blocks) embeds EVERY
# historical worst offender at once, run end-to-end through the REAL gate with the
# injected fake httpx client (zero live egress). Asserts the AGGREGATED flags object:
#   - fabrication: the ed-36 study, the ed-34 benchmark, a fake arXiv, a 404 github repo, a dead URL
#   - unverified: a transient 5xx (NON-EMPTY, DISTINCT from fabrication — the D-01 headline invariant)
#   - mechanical: a recycled closer, a duplicated stat, a leaked AUDIENCE: label
#   - meta: the correct fact_base_path, the github/url counts, github_token_present as a bool
#   - top-level keys EXACTLY {fabrication, unverified, mechanical, meta}; NO verdict (emit-only, D-05)
# locking the object to migration 045's deterministic_flags JSONB before Phase 30 wires it.
# ──────────────────────────────────────────────────────────────────────────────


# The named offenders embedded in one body: ed-36 "MCP Authentication Security Study",
# ed-34 "GroupMemBench", a fake arXiv ID, a 404 github repo, a dead URL, a transient-5xx URL,
# a recycled closer (matches the prior edition), a duplicated stat ("42%"), a leaked AUDIENCE:.
_GOLDEN_DEAD_URL = "https://dead.example.com/page"
_GOLDEN_5XX_URL = "https://flaky.example.com/x"


def _golden_offender_body():
    return (
        f"{gate.BODY_START_MARKER}\n\n"
        "AUDIENCE: Technical builders and infrastructure teams.\n\n"
        "The **MCP Authentication Security Study** and the **GroupMemBench** benchmark "
        "dominated the week, per arXiv 2699.88888. Adoption reached 42% across teams. "
        "The code lives at github.com/ghost/missing and the docs at "
        f"{_GOLDEN_DEAD_URL} with a mirror at {_GOLDEN_5XX_URL} for redundancy.\n\n"
        "Until next week, keep building the future.\n"
    )


def _golden_prior():
    return _prior_edition(
        content_markdown=(
            f"{gate.BODY_START_MARKER}\n\n"
            "Last week adoption was at 42% as builders shipped steadily.\n\n"
            "Until next week, keep building the future.\n"
        ),
        content_markdown_impact="",
        edition_number=101,
    )


def _golden_client():
    # ghost/missing → 404 (fabrication); dead URL → 404 (fabrication);
    # flaky URL → 503 (unverified after retry-once). A single queued outcome is sticky.
    return _FakeHTTPClient({
        _GH_API.format("ghost", "missing"): [(404, {})],
        _GOLDEN_DEAD_URL: [(404, {})],
        _GOLDEN_5XX_URL: [(503, {})],
    })


def _assert_golden_flags(flags, client, *, expected_fact_base_path):
    """The single aggregated assertion for a golden offender draft (shared by both paths)."""
    # ── top-level shape: EXACTLY the four migration-045-compatible keys; emit-only (no verdict) ──
    assert set(flags.keys()) == {"fabrication", "unverified", "mechanical", "meta"}
    assert "verdict" not in flags

    # ── fabrication: study + benchmark (tier1) + fake arXiv + github 404 + dead URL ──
    tier1_values = {f.get("value") for f in flags["fabrication"] if f["kind"] == "tier1_entity"}
    assert "MCP Authentication Security Study" in tier1_values  # ed-36
    assert "GroupMemBench" in tier1_values                      # ed-34
    assert any(f["kind"] == "arxiv" and f["id"] == "2699.88888" for f in flags["fabrication"])
    assert any(f["kind"] == "github_repo" and f["ref"] == "ghost/missing"
               for f in flags["fabrication"])
    assert any(f["kind"] == "dead_url" and f["url"] == _GOLDEN_DEAD_URL
               for f in flags["fabrication"])

    # ── unverified: the transient 5xx — NON-EMPTY and DISTINCT from fabrication (D-01 headline) ──
    assert flags["unverified"], "unverified must be non-empty (the transient 5xx is visible)"
    assert any(u["kind"] == "url" and u["url"] == _GOLDEN_5XX_URL
               and u["reason"] == "server_error_5xx" for u in flags["unverified"])
    # the transient failure is NEVER a fabrication ("an error is not evidence")
    assert not any(f.get("url") == _GOLDEN_5XX_URL for f in flags["fabrication"])

    # ── mechanical: recycled closer + duplicated stat + leaked label ──
    assert any(m["kind"] == "recycled_closer" for m in flags["mechanical"])
    assert any(m["kind"] == "duplicated_stat" and m["stat"] == "42%"
               for m in flags["mechanical"])
    assert any(m["kind"] == "reading_mode_leak" and m["label"] == "AUDIENCE:"
               for m in flags["mechanical"])

    # ── meta: correct fact-base path, counts, token-present bool ──
    meta = flags["meta"]
    assert meta["fact_base_path"] == expected_fact_base_path
    assert meta["github_checked"] == 1            # ghost/missing only
    assert meta["urls_checked"] == 2              # dead + flaky (github ref excluded)
    assert isinstance(meta["github_token_present"], bool)

    # ── zero live egress: every fetch went through the injected fake client ──
    assert set(client.calls) == {
        _GH_API.format("ghost", "missing"), _GOLDEN_DEAD_URL, _GOLDEN_5XX_URL,
    }


def test_golden_offender_single_pass_input_data_end_to_end():
    # GATE-08 single-pass path: the gate verifies against input_data (no `blocks` key).
    fb = _single_pass_fact_base(premium_source_posts=[
        {"title": "Weekly roundup", "summary": "General ecosystem coverage, no specific claims.",
         "source_display": "HN"},
    ])
    draft = _make_draft(content_markdown=_golden_offender_body(), content_markdown_impact="")
    client = _golden_client()
    flags = gate.run_deterministic_gate(draft, fb, _golden_prior(), http_client=client)
    _assert_golden_flags(flags, client, expected_fact_base_path="input_data")


def test_golden_offender_block_v1_end_to_end():
    # GATE-08 block_v1 path: the gate verifies against `blocks`.
    fb = _block_fact_base(blocks=[
        {"description": "General ecosystem coverage, no specific claims.",
         "named_entities": ["SomeRealProject"]},
    ])
    draft = _make_draft(content_markdown=_golden_offender_body(), content_markdown_impact="",
                        pipeline_version="block_v1")
    client = _golden_client()
    flags = gate.run_deterministic_gate(draft, fb, _golden_prior(), http_client=client)
    _assert_golden_flags(flags, client, expected_fact_base_path="blocks")


def test_golden_flags_object_is_json_serializable():
    # The whole flags object must serialize cleanly (Phase 30 maps it into 045's JSONB column).
    fb = _single_pass_fact_base()
    draft = _make_draft(content_markdown=_golden_offender_body(), content_markdown_impact="")
    flags = gate.run_deterministic_gate(draft, fb, _golden_prior(), http_client=_golden_client())
    dumped = json.loads(json.dumps(flags))  # round-trips → JSONB-compatible
    assert set(dumped.keys()) == {"fabrication", "unverified", "mechanical", "meta"}


# ──────────────────────────────────────────────────────────────────────────────
# CR-02 — broad httpx transport/protocol errors must yield `unverified`, NEVER crash
# the gate (which would discard every already-computed flag) and NEVER collapse into a
# pass. ReadError/RemoteProtocolError/ProxyError/DecodingError are siblings of
# Timeout/Connect (not subclasses); TooManyRedirects is realistic with follow_redirects.
# Every case must still return the full {fabrication, unverified, mechanical, meta} dict.
# ──────────────────────────────────────────────────────────────────────────────


_TRANSPORT_ERRORS = [
    (httpx.ReadError("connection reset mid-read"), "network_error", 2),
    (httpx.RemoteProtocolError("server disconnected"), "network_error", 2),
    (httpx.ProxyError("bad proxy"), "network_error", 2),
    (httpx.DecodingError("bad content-encoding"), "network_error", 2),
    (httpx.WriteError("write failed"), "network_error", 2),
    (httpx.TooManyRedirects("redirect loop"), "too_many_redirects", 1),  # not transient → no retry
]


@pytest.mark.parametrize("exc,expected_reason,expected_calls", _TRANSPORT_ERRORS)
def test_url_transport_error_unverified_full_dict(exc, expected_reason, expected_calls):
    url = "https://transport-fail.example.com/x"
    body = _md(f"see [x]({url}) here.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({url: [exc]})
    flags = gate.run_deterministic_gate(draft, _single_pass_fact_base(), None, http_client=client)
    # The gate never crashed — the full four-key dict is still returned.
    assert set(flags.keys()) == {"fabrication", "unverified", "mechanical", "meta"}
    unv = [u for u in flags["unverified"] if u["kind"] == "url"]
    assert any(u["url"] == url and u["reason"] == expected_reason for u in unv)
    # An error is NEVER a fabrication ("an error is not evidence").
    assert not any(f["kind"] == "dead_url" for f in flags["fabrication"])
    assert len(client.calls) == expected_calls


@pytest.mark.parametrize("exc,expected_reason,expected_calls", _TRANSPORT_ERRORS)
def test_github_transport_error_unverified_full_dict(exc, expected_reason, expected_calls):
    body = _gh_body("repo at github.com/acme/tool here.")
    draft = _make_draft(content_markdown=body)
    client = _FakeHTTPClient({_GH_API.format("acme", "tool"): [exc]})
    flags = gate.run_deterministic_gate(draft, _gh_fact_base("acme/tool"), None, http_client=client)
    assert set(flags.keys()) == {"fabrication", "unverified", "mechanical", "meta"}
    unv = [u for u in flags["unverified"] if u["kind"] == "github_repo"]
    assert any(u["ref"] == "acme/tool" and u["reason"] == expected_reason for u in unv)
    assert not any(f["kind"] == "github_repo" for f in flags["fabrication"])
    assert len(client.calls) == expected_calls


def test_transport_error_preserves_other_flags():
    # A single malformed/dead URL that raises a transport error must NOT abort the gate: the
    # tier1 study fabrication and the mechanical label leak computed for the same draft survive.
    url = "https://transport-fail.example.com/x"
    body = _body(
        "AUDIENCE: Technical builders.\n\n"
        f"Researchers introduced **GroupMemBench**, a memory benchmark. Mirror at {url}."
    )
    draft = _make_draft(content_markdown=body, content_markdown_impact="")
    client = _FakeHTTPClient({url: [httpx.ReadError("reset")]})
    flags = gate.run_deterministic_gate(draft, _single_pass_fact_base(), None, http_client=client)
    # the transport error surfaced as unverified ...
    assert any(u["kind"] == "url" and u["reason"] == "network_error" for u in flags["unverified"])
    # ... and the other layers' flags were preserved (gate did not crash before building them).
    assert "GroupMemBench" in {f.get("value") for f in flags["fabrication"]
                               if f["kind"] == "tier1_entity"}
    assert any(m["kind"] == "reading_mode_leak" and m["label"] == "AUDIENCE:"
               for m in flags["mechanical"])


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
