#!/usr/bin/env python3
"""
Phase 7 Plan 01 — per-block synthesis loop primitives (Wave-0 unit harness).

Covers the standalone building blocks added to the processor in Plan 07-01:
  - SYNT-04/D-10: synthesis_sonnet_call routes through {LLM_PROXY_URL}/anthropic/v1/messages,
    carries the agent key in BOTH Authorization and x-api-key, uses model
    claude-sonnet-4-20250514, and RAISES on a non-2xx proxy response.
  - SYNT-05/D-11: load_synth_identity hot-reloads by mtime and fails loud (None) on a
    missing OR empty file.
  - SYNT-01/D-03/D-05/D-06: is_block_eligible truth table (no-draft guard, N threshold,
    T-day clock, cold-start NULL watermark using earliest created_at).
  - SYNT-03/D-07/D-09: assemble_synthesis_input orders entries event_date-desc, caps at
    max_input_entries keeping the newest, sets omitted_count and an in-prompt note (never
    a silent drop); under-cap sets omitted_count 0.
  - SYNT-06/D-12: parse_synthesis_output validates the maturity enum and raises on empty
    body_md / invalid maturity / missing proposed_maturity.
  - D-13: economy_map_insert_block_body_version POSTs to /block_body_versions with
    Content-Profile: economy_map, omits the `status` key, and never targets blocks/published.

Run standalone (no pytest required):  python3 tests/test_07_synthesis.py
"""
import json
import os
import sys
import time
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Stub third-party libs the processor imports at module level but that are not
# needed for these unit tests, so the module imports in a bare environment.
# (Mirrors the test_05a_intake_classifier harness shape.)
# ---------------------------------------------------------------------------
for _name in ("schedule", "tweepy", "resend"):
    try:
        __import__(_name)
    except Exception:
        sys.modules[_name] = types.ModuleType(_name)
try:
    import markdown  # noqa: F401
except Exception:
    _m = types.ModuleType("markdown")
    _m.markdown = lambda *a, **k: ""
    sys.modules["markdown"] = _m

os.environ.setdefault("OPENCLAW_DATA_DIR", "/tmp/openclaw_test_07")
sys.path.insert(0, str(_ROOT / "docker" / "processor"))

import agentpulse_processor as proc  # noqa: E402

# Prime the model-routing cache from the repo config (mirrors test_05a).
_REPO_CONFIG = json.loads((_ROOT / "config" / "agentpulse-config.json").read_text())
proc._model_config_cache = _REPO_CONFIG.get("models", {})

# The synthesis config block as shipped (used for assembly cap + Sonnet call config).
SYNTH_CFG = _REPO_CONFIG.get("synthesis", {})

# A body_md carrying all six required RNDR-02 skeleton headings — parse_synthesis_output now
# rejects bodies missing any section (WR-02), so poller/parse fixtures must use a full skeleton.
_FULL_SKELETON_BODY = "\n\n".join(f"## {h}\nbody for {h}." for h in proc.SYNTH_SKELETON_HEADINGS)


class _FakeResponse:
    """Anthropic Messages-shaped response: json() -> {'content': [{'type','text'}]}."""

    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or (json.dumps(payload) if payload is not None else "")
        self.headers = {"X-Proxy-Request-Id": "req-test", "X-Proxy-Agent": "processor"}

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _anthropic_payload(body_md="A body.", maturity="emerging"):
    """Build an Anthropic Messages payload whose text is the stringified synthesis JSON."""
    inner = json.dumps({"body_md": body_md, "proposed_maturity": maturity})
    return {"content": [{"type": "text", "text": inner}]}


def _install_post_stub(monkey, response):
    """Patch _get_agent_api_key + httpx.post; capture url/headers/body. Returns captured."""
    captured = {}
    monkey["agent_key"] = proc._get_agent_api_key
    monkey["httpx_post"] = proc.httpx.post
    proc._get_agent_api_key = lambda: "ap_processor_test"

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        captured["url"] = url
        captured["headers"] = headers or {}
        captured["body"] = json or {}
        captured["timeout"] = timeout
        if isinstance(response, Exception):
            raise response
        return response

    proc.httpx.post = fake_post
    return captured


def _restore_post(monkey):
    proc._get_agent_api_key = monkey["agent_key"]
    proc.httpx.post = monkey["httpx_post"]


# ===========================================================================
# SYNT-04 / D-10 — Sonnet call routes through /anthropic/v1/messages
# ===========================================================================
def test_sonnet_call_routes_through_anthropic_messages():
    monkey = {}
    captured = _install_post_stub(monkey, _FakeResponse(200, _anthropic_payload()))
    try:
        text = proc.synthesis_sonnet_call("SYSTEM VOICE", "USER PROMPT", SYNTH_CFG)
    finally:
        _restore_post(monkey)

    # The literal route substring — fails if code ever reverts to /v1/chat/completions.
    assert captured["url"].endswith("/anthropic/v1/messages"), captured["url"]
    assert proc.LLM_PROXY_URL in captured["url"]
    # Agent key carried in BOTH headers (RESEARCH A1).
    assert captured["headers"].get("Authorization") == "Bearer ap_processor_test"
    assert captured["headers"].get("x-api-key") == "ap_processor_test"
    # Anthropic Messages body shape.
    assert captured["body"].get("model") == "claude-sonnet-4-20250514"
    assert captured["body"].get("system") == "SYSTEM VOICE"
    assert captured["body"]["messages"][0]["role"] == "user"
    assert captured["body"]["messages"][0]["content"] == "USER PROMPT"
    # Returns the Anthropic-shaped content text (not choices[0].message.content).
    parsed = json.loads(text)
    assert parsed["body_md"] == "A body."


def test_sonnet_call_non_2xx_raises():
    monkey = {}
    _install_post_stub(monkey, _FakeResponse(502, None, text="bad gateway"))
    try:
        raised = False
        try:
            proc.synthesis_sonnet_call("S", "U", SYNTH_CFG)
        except Exception:
            raised = True
    finally:
        _restore_post(monkey)
    assert raised, "synthesis_sonnet_call must raise on non-2xx proxy response"


def test_sonnet_call_raises_on_empty_content():
    """A 200 whose `content` is empty (refusal / stop_reason != end_turn) must raise a
    descriptive error, not an opaque IndexError/KeyError (WR-03)."""
    monkey = {}
    _install_post_stub(monkey, _FakeResponse(200, {"content": [], "stop_reason": "max_tokens"}))
    try:
        raised = False
        try:
            proc.synthesis_sonnet_call("S", "U", SYNTH_CFG)
        except RuntimeError as e:
            raised = "no content" in str(e)
    finally:
        _restore_post(monkey)
    assert raised, "must raise a descriptive 'no content' error on an empty 200 body"


# ===========================================================================
# SYNT-05 / D-11 — identity hot-reload, fail-loud on missing/empty
# ===========================================================================
def test_identity_loads_and_hot_reloads(tmp_path_factory=None):
    tmpdir = Path(os.environ["OPENCLAW_DATA_DIR"]) / "identity_test"
    tmpdir.mkdir(parents=True, exist_ok=True)
    f = tmpdir / "synth_identity.md"

    orig_path = proc.SYNTH_IDENTITY_PATH
    orig_cache = proc._synth_identity_cache
    orig_mtime = proc._synth_identity_mtime
    try:
        proc.SYNTH_IDENTITY_PATH = f
        proc._synth_identity_cache = None
        proc._synth_identity_mtime = 0.0

        # Missing file -> None (fail-loud, D-11).
        if f.exists():
            f.unlink()
        assert proc.load_synth_identity() is None, "missing file must return None"

        # Empty-after-strip file -> None (fail-loud, D-11).
        f.write_text("   \n\t  ", encoding="utf-8")
        proc._synth_identity_cache = None
        proc._synth_identity_mtime = 0.0
        assert proc.load_synth_identity() is None, "empty file must return None"

        # Real content -> returns stripped text.
        f.write_text("Voice one.\n", encoding="utf-8")
        proc._synth_identity_cache = None
        proc._synth_identity_mtime = 0.0
        assert proc.load_synth_identity() == "Voice one."

        # Edit the file (advance mtime) -> re-reads (is-not-None cache guard).
        time.sleep(0.01)
        os.utime(f, (time.time() + 2, time.time() + 2))
        f.write_text("Voice two.\n", encoding="utf-8")
        os.utime(f, (time.time() + 3, time.time() + 3))
        assert proc.load_synth_identity() == "Voice two.", "edited file must hot-reload"
    finally:
        proc.SYNTH_IDENTITY_PATH = orig_path
        proc._synth_identity_cache = orig_cache
        proc._synth_identity_mtime = orig_mtime


# ===========================================================================
# SYNT-01 / D-03 / D-05 / D-06 — eligibility truth table
# ===========================================================================
def _entries(n, created_iso="2026-05-30T00:00:00+00:00"):
    return [{"created_at": created_iso, "event_date": "2026-05-30",
             "what_shifted": "x", "why_it_mattered": "y", "source_url": None} for _ in range(n)]


def test_eligibility_truth_table():
    block_warm = {"slug": "s", "last_synthesized_at": "2026-05-01T00:00:00+00:00"}
    block_cold = {"slug": "s", "last_synthesized_at": None}

    # has_draft True => never eligible (D-03), even at n >= N.
    assert proc.is_block_eligible(block_warm, _entries(10), True, N=5, T_days=30) is False

    # n >= N => eligible (D-05).
    assert proc.is_block_eligible(block_warm, _entries(5), False, N=5, T_days=30) is True

    # 1..4 entries, recent watermark (age < T) => not eligible.
    recent = {"slug": "s", "last_synthesized_at": proc.datetime.now(proc.timezone.utc).isoformat()}
    assert proc.is_block_eligible(recent, _entries(3), False, N=5, T_days=30) is False

    # 1..4 entries, old watermark (age >= T) => eligible.
    old = {"slug": "s", "last_synthesized_at": "2026-01-01T00:00:00+00:00"}
    assert proc.is_block_eligible(old, _entries(2), False, N=5, T_days=30) is True

    # 0 entries => not eligible regardless of age.
    assert proc.is_block_eligible(old, _entries(0), False, N=5, T_days=30) is False

    # Cold-start (NULL watermark): n>=1 but earliest entry < 30d old => not eligible.
    near_now = proc.datetime.now(proc.timezone.utc).isoformat()
    assert proc.is_block_eligible(block_cold, _entries(1, near_now), False, N=5, T_days=30) is False

    # Cold-start: n>=1 and earliest entry >= 30d old => eligible (age clock = earliest created_at).
    assert proc.is_block_eligible(
        block_cold, _entries(1, "2026-01-01T00:00:00+00:00"), False, N=5, T_days=30) is True

    # Cold-start: n>=N => eligible.
    assert proc.is_block_eligible(block_cold, _entries(5, near_now), False, N=5, T_days=30) is True


# ===========================================================================
# SYNT-03 / D-07 / D-09 — assembly ordering + fail-loud cap
# ===========================================================================
def _dated_entry(event_date, label):
    return {"event_date": event_date, "what_shifted": label,
            "why_it_mattered": f"why-{label}", "source_url": f"https://x/{label}",
            "created_at": f"{event_date}T00:00:00+00:00"}


def test_assembly_orders_newest_first_and_under_cap():
    block = {"slug": "memory-context", "maturity": "nascent", "live_tension": "the open Q",
             "last_synthesized_at": None}
    entries = [_dated_entry("2026-01-01", "old"),
               _dated_entry("2026-05-30", "new"),
               _dated_entry("2026-03-15", "mid")]
    cfg = {"max_input_entries": 22, "max_input_tokens": 12000}
    result = proc.assemble_synthesis_input(block, entries, None, cfg)

    assert result["omitted_count"] == 0
    assert result["included_count"] == 3
    p = result["prompt"]
    # newest-first: 'new' (May) appears before 'mid' (Mar) before 'old' (Jan).
    assert p.index("what_shifted: new") < p.index("what_shifted: mid") < p.index("what_shifted: old")
    # Concrete entry fields present (never bare cluster labels).
    assert "why_it_mattered: why-new" in p
    assert "source_url: https://x/new" in p
    # Live tension carried through.
    assert "the open Q" in p
    # Cold-start: no prior-body section.
    assert "PRIOR PUBLISHED BODY" not in p


def test_assembly_over_cap_keeps_newest_and_notes_omission():
    block = {"slug": "psychology-disposition", "maturity": "nascent",
             "live_tension": "t", "last_synthesized_at": None}
    # 25 entries with ascending dates; cap at 22 must keep the 22 newest.
    entries = [_dated_entry(f"2026-04-{day:02d}", f"e{day:02d}") for day in range(1, 26)]
    cfg = {"max_input_entries": 22, "max_input_tokens": 12000}
    result = proc.assemble_synthesis_input(block, entries, None, cfg)

    assert result["total_count"] == 25
    assert result["included_count"] == 22
    assert result["omitted_count"] == 3
    p = result["prompt"]
    # In-prompt omitted-count note present (no silent drop, D-09).
    assert "3 older entries omitted" in p
    # The 3 oldest (e01,e02,e03) dropped; the newest (e25) kept.
    assert "what_shifted: e01" not in p
    assert "what_shifted: e25" in p


# ===========================================================================
# SYNT-06 / D-12 — output parse + maturity-enum validation
# ===========================================================================
def test_parse_output_valid():
    text = json.dumps({"body_md": _FULL_SKELETON_BODY, "proposed_maturity": "contested"})
    out = proc.parse_synthesis_output(text)
    assert out["body_md"].startswith("## What it is")
    assert out["proposed_maturity"] == "contested"


def test_parse_output_fence_wrapped():
    text = "```json\n" + json.dumps({"body_md": _FULL_SKELETON_BODY,
                                     "proposed_maturity": "mature"}) + "\n```"
    out = proc.parse_synthesis_output(text)
    assert out["proposed_maturity"] == "mature"


def test_parse_output_keeps_partial_skeleton():
    """D-01 (Phase 8): the WR-02 missing-skeleton HARD raise is REMOVED — a body that drops
    headings now LANDS as a draft (the structure problem becomes a VLDT-04 sentinel that
    annotates, never blocks; a silent skip is itself a form of silence — VLDT-05)."""
    out = proc.parse_synthesis_output(json.dumps(
        {"body_md": "## What it is\nonly one section", "proposed_maturity": "emerging"}))
    assert out["body_md"].startswith("## What it is")
    assert out["proposed_maturity"] == "emerging"


# ===========================================================================
# Phase 8 VLDT-01..05 — run_sentinels (deterministic, pure compute, never blocks)
# ===========================================================================
def test_sentinel_flags_missing_structure():
    """VLDT-04 + D-04: a missing-heading body lands but structure_missing is populated and
    the requires_attention rollup fires."""
    report = proc.run_sentinels(
        "## What it is\nonly one section", None,
        {"maturity": "emerging", "live_tension": "some prior tension framing"}, "emerging")
    assert report["structure_missing"]            # populated — headings absent
    assert report["requires_attention"] is True   # D-04 rollup fires
    assert "sentinel_errors" not in report        # clean compute, no error note


def test_sentinel_full_skeleton_clean():
    """A full skeleton with a real, engaged live-tension section and no maturity jump is clean."""
    body = "\n\n".join(
        f"## {h}\n{'engaged tension content that is clearly above the char floor here' if h == 'The live tension' else f'body for {h}.'}"
        for h in proc.SYNTH_SKELETON_HEADINGS
    )
    report = proc.run_sentinels(
        body, None, {"maturity": "emerging", "live_tension": "prior framing"}, "emerging")
    assert report["structure_missing"] == []
    assert report["tension_preserved"] is True
    assert report["length_below_floor"] is False  # cold-start N/A
    assert report["maturity_jump"] == 0
    assert report["requires_attention"] is False


def _skeleton_with_tension(tension_body: str) -> str:
    parts = []
    for h in proc.SYNTH_SKELETON_HEADINGS:
        body = tension_body if h == "The live tension" else f"body for {h}."
        parts.append(f"## {h}\n{body}")
    return "\n\n".join(parts)


def test_sentinel_tension_absent_section():
    """VLDT-01: live-tension section entirely absent -> tension_preserved False."""
    body = "\n\n".join(
        f"## {h}\nbody for {h}." for h in proc.SYNTH_SKELETON_HEADINGS
        if h != "The live tension"
    )
    report = proc.run_sentinels(
        body, None, {"maturity": "emerging", "live_tension": "x"}, "emerging")
    assert report["tension_preserved"] is False
    assert report["requires_attention"] is True


def test_sentinel_tension_placeholder():
    """VLDT-01: a live-tension section that is just the seed placeholder -> not preserved."""
    body = _skeleton_with_tension("TBD — set via /map-tension")
    report = proc.run_sentinels(
        body, None, {"maturity": "emerging", "live_tension": "x"}, "emerging")
    assert report["tension_preserved"] is False


def test_sentinel_tension_verbatim_echo():
    """VLDT-01: a live-tension section that verbatim-echoes block.live_tension -> not engaged."""
    prior = "The unresolved fight is whether identity is portable across agents or platform-bound."
    body = _skeleton_with_tension(prior)
    report = proc.run_sentinels(
        body, None, {"maturity": "emerging", "live_tension": prior}, "emerging")
    assert report["tension_preserved"] is False


def test_sentinel_length_below_floor():
    """VLDT-02: new body under 60% of prior published body -> length_below_floor True."""
    prior = "x" * 1000
    body = _skeleton_with_tension("a genuinely engaged tension section well above the char floor")
    # body is far shorter than 600 chars only if skeleton small; make prior dominate.
    report = proc.run_sentinels("short", prior, {"maturity": "emerging", "live_tension": ""},
                                "emerging")
    assert report["length_below_floor"] is True
    assert report["requires_attention"] is True
    # Sanity: a comparable-length body is not flagged.
    report2 = proc.run_sentinels("x" * 900, prior, {"maturity": "emerging", "live_tension": ""},
                                 "emerging")
    assert report2["length_below_floor"] is False


def test_sentinel_length_coldstart_na():
    """VLDT-02 / D-06: cold-start (no prior body) -> length sentinel N/A, never a flag."""
    report = proc.run_sentinels("short", None, {"maturity": "emerging", "live_tension": ""},
                                "emerging")
    assert report["length_below_floor"] is False
    report_empty = proc.run_sentinels("short", "   ", {"maturity": "emerging", "live_tension": ""},
                                      "emerging")
    assert report_empty["length_below_floor"] is False


def test_sentinel_maturity_jump():
    """VLDT-03 / D-07: ordinal distance > 1 sets requires_attention."""
    full = _skeleton_with_tension("a genuinely engaged tension section above the char floor here")
    # nascent (0) -> contested (2): jump = 2
    report = proc.run_sentinels(full, None, {"maturity": "nascent", "live_tension": "p"},
                                "contested")
    assert report["maturity_jump"] == 2
    assert report["requires_attention"] is True
    # Adjacent step (jump = 1) does not by itself fire attention.
    report1 = proc.run_sentinels(full, None, {"maturity": "nascent", "live_tension": "p"},
                                 "emerging")
    assert report1["maturity_jump"] == 1
    assert report1["requires_attention"] is False


def test_parse_output_raises_on_empty_body():
    raised = False
    try:
        proc.parse_synthesis_output(json.dumps({"body_md": "  ", "proposed_maturity": "emerging"}))
    except ValueError:
        raised = True
    assert raised, "must raise on empty body_md"


def test_parse_output_raises_on_invalid_maturity():
    raised = False
    try:
        proc.parse_synthesis_output(json.dumps({"body_md": "b", "proposed_maturity": "legendary"}))
    except ValueError:
        raised = True
    assert raised, "must raise on out-of-enum maturity"


def test_parse_output_raises_on_missing_maturity():
    raised = False
    try:
        proc.parse_synthesis_output(json.dumps({"body_md": "b"}))
    except ValueError:
        raised = True
    assert raised, "must raise on missing proposed_maturity"


# ===========================================================================
# D-13 — draft INSERT shape (Content-Profile, status omitted, never blocks/published)
# ===========================================================================
def test_insert_block_body_version_shape():
    monkey = {}
    captured = _install_post_stub(monkey, _FakeResponse(201, [{"id": "v1", "status": "draft"}]))
    try:
        row = {
            "block_slug": "identity-trust",
            "body_md": "## What it is\n...",
            "proposed_maturity": "emerging",
            "synthesized_from_through": "2026-06-01T00:00:00+00:00",
            "validator_report": {
                "tension_preserved": True,
                "length_below_floor": False,
                "structure_missing": [],
                "maturity_jump": 0,
                "requires_attention": False,
            },
        }
        out = proc.economy_map_insert_block_body_version(row)
    finally:
        _restore_post(monkey)

    assert out["id"] == "v1"
    assert captured["url"].endswith("/block_body_versions")
    assert "/blocks" not in captured["url"].rsplit("/", 1)[-1]  # never the blocks table
    assert captured["headers"].get("Content-Profile") == "economy_map"
    # status omitted -> DB default 'draft' (D-13).
    assert "status" not in captured["body"]
    # Never references published/blocks mutation columns.
    for forbidden in ("published_at", "current_body_version_id", "maturity"):
        assert forbidden not in captured["body"]
    assert set(captured["body"].keys()) == {
        "block_slug", "body_md", "proposed_maturity", "synthesized_from_through",
        "validator_report"}


def test_insert_block_body_version_non_2xx_raises():
    monkey = {}
    _install_post_stub(monkey, _FakeResponse(400, None, text="bad request"))
    try:
        raised = False
        try:
            proc.economy_map_insert_block_body_version({"block_slug": "s", "body_md": "b",
                                                        "proposed_maturity": "nascent",
                                                        "synthesized_from_through": "t"})
        except Exception:
            raised = True
    finally:
        _restore_post(monkey)
    assert raised, "insert must raise on non-2xx"


# ===========================================================================
# Plan 07-02 — end-to-end synthesize_blocks_poller (draft-only GATE-01 + fail-loud)
# ===========================================================================
# These drive the full orchestrator with stubbed economy_map reads (proc.httpx.get),
# stubbed Sonnet + INSERT writes (proc.httpx.post), and stubbed identity/key/run-logging.
# The central assertions: an eligible block makes exactly ONE Sonnet POST + ONE draft
# INSERT and NEVER targets /blocks or a published row (GATE-01); the no-draft guard and
# the fail-loud identity/key aborts make zero Sonnet calls; one bad block is isolated.


class _GetResponse:
    """Minimal PostgREST-shaped GET response: json() -> list of rows, status 200."""

    def __init__(self, rows, status_code=200):
        self.status_code = status_code
        self._rows = rows
        self.text = json.dumps(rows)

    def json(self):
        return self._rows


def _install_poller_stubs(monkey, *, blocks, get_router=None, sonnet_payload=None,
                          identity="VOICE", agent_key="ap_processor_test"):
    """Stub the poller's whole I/O surface: supabase guard, run-logging, identity, key,
    httpx.get (economy_map reads), httpx.post (Sonnet call + draft INSERT).

    `blocks` is the list returned by fetch_economy_map_blocks. `get_router(table, params)`
    returns the row list for the per-block reads (block_body_versions draft check,
    timeline_entries new-entries, block_body_versions current body); when None, a default
    router returns: no draft, 5 cold-start entries, no prior body. Returns a `captured` dict
    with lists of every POST url/body so tests can assert call counts and targets.
    """
    captured = {"posts": [], "gets": []}

    monkey["supabase"] = proc.supabase
    monkey["log_start"] = proc.log_pipeline_start
    monkey["log_end"] = proc.log_pipeline_end
    monkey["identity"] = proc.load_synth_identity
    monkey["agent_key"] = proc._get_agent_api_key
    monkey["httpx_get"] = proc.httpx.get
    monkey["httpx_post"] = proc.httpx.post

    proc.supabase = object()  # truthy guard pass; run-logging is stubbed so it's never used
    proc.log_pipeline_start = lambda pipeline: "run-test"
    proc.log_pipeline_end = lambda run_id, status, results: None
    proc.load_synth_identity = (lambda: identity) if identity is not None else (lambda: None)
    proc._get_agent_api_key = (lambda: agent_key) if agent_key else (lambda: "")

    def _default_router(table, params):
        if table == "block_body_versions" and params.get("status") == "eq.draft":
            return []  # no open draft
        if table == "timeline_entries":
            # 5 cold-start entries (>= N) => eligible.
            return [{"event_date": "2026-05-30", "what_shifted": f"e{i}",
                     "why_it_mattered": "y", "source_url": None,
                     "created_at": "2026-05-30T00:00:00+00:00"} for i in range(5)]
        if table == "block_body_versions":
            return []  # current body fetch (cold-start => empty)
        return []

    router = get_router or _default_router

    def fake_get(url, params=None, headers=None, timeout=None, **kw):
        params = params or {}
        table = url.rsplit("/", 1)[-1]
        captured["gets"].append({"table": table, "params": params})
        if table == "blocks":
            return _GetResponse(blocks)
        return _GetResponse(router(table, params))

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        captured["posts"].append({"url": url, "headers": headers or {},
                                  "body": json or {}})
        if url.endswith("/anthropic/v1/messages"):
            payload = sonnet_payload or _anthropic_payload(body_md=_FULL_SKELETON_BODY,
                                                           maturity="emerging")
            return _FakeResponse(200, payload)
        # block_body_versions INSERT
        return _FakeResponse(201, [{"id": "v-new", "status": "draft"}])

    proc.httpx.get = fake_get
    proc.httpx.post = fake_post
    return captured


def _restore_poller(monkey):
    proc.supabase = monkey["supabase"]
    proc.log_pipeline_start = monkey["log_start"]
    proc.log_pipeline_end = monkey["log_end"]
    proc.load_synth_identity = monkey["identity"]
    proc._get_agent_api_key = monkey["agent_key"]
    proc.httpx.get = monkey["httpx_get"]
    proc.httpx.post = monkey["httpx_post"]


def _one_block(slug="memory-context"):
    return [{"slug": slug, "maturity": "nascent", "live_tension": "the open Q",
             "last_synthesized_at": None, "current_body_version_id": None}]


def test_poller_eligible_block_drafts_one_row_no_published_write():
    """Eligible cold-start block => exactly ONE Sonnet POST + ONE draft INSERT;
    zero requests target /blocks or a published row (GATE-01 draft-only invariant)."""
    monkey = {}
    captured = _install_poller_stubs(monkey, blocks=_one_block())
    try:
        totals = proc.synthesize_blocks_poller()
    finally:
        _restore_poller(monkey)

    assert totals["synthesized"] == 1, totals
    assert totals["eligible"] == 1
    assert totals["skipped"] == 0
    assert totals["failed"] == 0

    sonnet_posts = [p for p in captured["posts"] if p["url"].endswith("/anthropic/v1/messages")]
    insert_posts = [p for p in captured["posts"] if p["url"].endswith("/block_body_versions")]
    assert len(sonnet_posts) == 1, f"expected exactly one Sonnet call, got {len(sonnet_posts)}"
    assert len(insert_posts) == 1, f"expected exactly one draft INSERT, got {len(insert_posts)}"

    # GATE-01: no POST/PATCH ever targets the blocks table or a published-row mutation.
    for p in captured["posts"]:
        assert not p["url"].rstrip("/").endswith("/blocks"), p["url"]
    ins = insert_posts[0]
    assert ins["headers"].get("Content-Profile") == "economy_map"
    assert "status" not in ins["body"], "status must be omitted (DB default draft, D-13)"
    for forbidden in ("published_at", "current_body_version_id", "maturity"):
        assert forbidden not in ins["body"], forbidden
    # synthesized_from_through is the RUN wall-clock, present and ISO-ish (Pitfall 5).
    assert "synthesized_from_through" in ins["body"]
    assert ins["body"]["synthesized_from_through"]


def test_poller_open_draft_block_makes_zero_calls():
    """A block with an existing open draft => zero Sonnet calls, zero INSERTs (D-03 guard)."""
    def router(table, params):
        if table == "block_body_versions" and params.get("status") == "eq.draft":
            return [{"id": "existing-draft"}]  # has open draft
        if table == "timeline_entries":
            return [{"event_date": "2026-05-30", "what_shifted": "e", "why_it_mattered": "y",
                     "source_url": None, "created_at": "2026-05-30T00:00:00+00:00"}
                    for _ in range(9)]
        return []

    monkey = {}
    captured = _install_poller_stubs(monkey, blocks=_one_block(), get_router=router)
    try:
        totals = proc.synthesize_blocks_poller()
    finally:
        _restore_poller(monkey)

    assert totals["skipped"] == 1, totals
    assert totals["synthesized"] == 0
    assert not any(p["url"].endswith("/anthropic/v1/messages") for p in captured["posts"])
    assert not any(p["url"].endswith("/block_body_versions") for p in captured["posts"])


def test_poller_aborts_loud_on_none_identity():
    """load_synth_identity() None => poller aborts loudly, zero Sonnet calls (D-11)."""
    monkey = {}
    captured = _install_poller_stubs(monkey, blocks=_one_block(), identity=None)
    try:
        result = proc.synthesize_blocks_poller()
    finally:
        _restore_poller(monkey)

    assert "error" in result and "identity" in result["error"], result
    assert captured["posts"] == [], "no Sonnet/INSERT calls when identity is None"


def test_poller_aborts_loud_on_missing_key():
    """Missing agent key => poller aborts loudly, zero Sonnet calls (fail-loud governance)."""
    monkey = {}
    captured = _install_poller_stubs(monkey, blocks=_one_block(), agent_key="")
    try:
        result = proc.synthesize_blocks_poller()
    finally:
        _restore_poller(monkey)

    assert "error" in result and "key" in result["error"], result
    assert captured["posts"] == [], "no Sonnet/INSERT calls when the agent key is missing"


def test_poller_isolates_one_failing_block():
    """One block's read raises => that block counted failed, others still synthesized."""
    good, bad = "memory-context", "identity-trust"

    def router(table, params):
        if table == "block_body_versions" and params.get("status") == "eq.draft":
            # Make the draft-check read raise for the bad block only.
            if params.get("block_slug") == f"eq.{bad}":
                raise RuntimeError("simulated read failure")
            return []
        if table == "timeline_entries":
            return [{"event_date": "2026-05-30", "what_shifted": "e", "why_it_mattered": "y",
                     "source_url": None, "created_at": "2026-05-30T00:00:00+00:00"}
                    for _ in range(5)]
        return []

    blocks = [
        {"slug": bad, "maturity": "nascent", "live_tension": "t",
         "last_synthesized_at": None, "current_body_version_id": None},
        {"slug": good, "maturity": "nascent", "live_tension": "t",
         "last_synthesized_at": None, "current_body_version_id": None},
    ]
    monkey = {}
    captured = _install_poller_stubs(monkey, blocks=blocks, get_router=router)
    try:
        totals = proc.synthesize_blocks_poller()
    finally:
        _restore_poller(monkey)

    assert totals["failed"] == 1, totals
    assert totals["synthesized"] == 1, totals  # the good block still processed
    sonnet_posts = [p for p in captured["posts"] if p["url"].endswith("/anthropic/v1/messages")]
    assert len(sonnet_posts) == 1, "only the good block reaches the Sonnet call"


def test_poller_eligible_block_failure_counts_eligible():
    """An eligible block that fails mid-synthesis (Sonnet non-2xx) is counted failed AND
    eligible — 'eligible' tracks the decision, not just successes, so the run record can
    show 'eligible but failed' (WR-04)."""
    def post_router_502(url, headers=None, json=None, timeout=None, **kw):
        # Sonnet call fails; this is post-eligibility, so the block is eligible-but-failed.
        return _FakeResponse(502, None, text="bad gateway")

    monkey = {}
    captured = _install_poller_stubs(monkey, blocks=_one_block())
    # Override the post stub so the (eligible) block's Sonnet call returns non-2xx.
    proc.httpx.post = post_router_502
    try:
        totals = proc.synthesize_blocks_poller()
    finally:
        _restore_poller(monkey)

    assert totals["failed"] == 1, totals
    assert totals["eligible"] == 1, f"eligible must count the decision, not the outcome: {totals}"
    assert totals["synthesized"] == 0, totals


def _run_all():
    tests = [
        test_sonnet_call_routes_through_anthropic_messages,
        test_sonnet_call_non_2xx_raises,
        test_sonnet_call_raises_on_empty_content,
        test_identity_loads_and_hot_reloads,
        test_eligibility_truth_table,
        test_assembly_orders_newest_first_and_under_cap,
        test_assembly_over_cap_keeps_newest_and_notes_omission,
        test_parse_output_valid,
        test_parse_output_fence_wrapped,
        test_parse_output_keeps_partial_skeleton,
        test_parse_output_raises_on_empty_body,
        test_parse_output_raises_on_invalid_maturity,
        test_parse_output_raises_on_missing_maturity,
        test_sentinel_flags_missing_structure,
        test_sentinel_full_skeleton_clean,
        test_sentinel_tension_absent_section,
        test_sentinel_tension_placeholder,
        test_sentinel_tension_verbatim_echo,
        test_sentinel_length_below_floor,
        test_sentinel_length_coldstart_na,
        test_sentinel_maturity_jump,
        test_insert_block_body_version_shape,
        test_insert_block_body_version_non_2xx_raises,
        test_poller_eligible_block_drafts_one_row_no_published_write,
        test_poller_eligible_block_failure_counts_eligible,
        test_poller_open_draft_block_makes_zero_calls,
        test_poller_aborts_loud_on_none_identity,
        test_poller_aborts_loud_on_missing_key,
        test_poller_isolates_one_failing_block,
    ]
    failures = []
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as e:
            failures.append((t.__name__, e))
            print(f"FAIL  {t.__name__}: {e}")
    if failures:
        print(f"\n{len(failures)}/{len(tests)} FAILED")
        return 1
    print(f"\nAll {len(tests)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(_run_all())
