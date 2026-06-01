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
    text = json.dumps({"body_md": "## What it is\nstuff", "proposed_maturity": "contested"})
    out = proc.parse_synthesis_output(text)
    assert out["body_md"].startswith("## What it is")
    assert out["proposed_maturity"] == "contested"


def test_parse_output_fence_wrapped():
    text = "```json\n" + json.dumps({"body_md": "b", "proposed_maturity": "mature"}) + "\n```"
    out = proc.parse_synthesis_output(text)
    assert out["proposed_maturity"] == "mature"


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
        "block_slug", "body_md", "proposed_maturity", "synthesized_from_through"}


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


def _run_all():
    tests = [
        test_sonnet_call_routes_through_anthropic_messages,
        test_sonnet_call_non_2xx_raises,
        test_identity_loads_and_hot_reloads,
        test_eligibility_truth_table,
        test_assembly_orders_newest_first_and_under_cap,
        test_assembly_over_cap_keeps_newest_and_notes_omission,
        test_parse_output_valid,
        test_parse_output_fence_wrapped,
        test_parse_output_raises_on_empty_body,
        test_parse_output_raises_on_invalid_maturity,
        test_parse_output_raises_on_missing_maturity,
        test_insert_block_body_version_shape,
        test_insert_block_body_version_non_2xx_raises,
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
