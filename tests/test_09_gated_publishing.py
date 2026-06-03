#!/usr/bin/env python3
"""
Phase 9 Plan 02 — gated-publishing approval commands (standalone unit harness).

Covers the owner-gated write surface added to gato_brain in Plan 09-02 plus an explicit
GATE-01 verification against the synthesis draft writer in the processor:

  - GATE-01: economy_map_insert_block_body_version (processor) builds a POST body that
    OMITS `status` (so the DB default 'draft' applies) and targets block_body_versions
    only — never blocks or a status: 'published'/'superseded' write. Mirrors test_07's
    test_insert_block_body_version_shape; this makes GATE-01 genuinely verified.
  - T-09-06 (owner gate): /map-approve and /map-reject with access_tier != 'owner' return
    a refusal and NEVER issue an RPC POST; with access_tier == 'owner' the RPC IS called.
  - T-09-07 (UUID validation): a missing arg and a malformed (non-UUID) arg each return a
    usage hint with NO RPC call (owner tier, isolating validation from gating).
  - D-05 case (c): an RPC raise containing "not found or not in draft status" maps to the
    distinct "already published/rejected or doesn't exist" message — not a crash, not a
    success confirmation.
  - D-05 approve confirmation: a successful /map-approve returns the maturity <old>→<new>
    transition and the https://aiagentspulse.com/#/map/<slug> URL.

Run standalone (no pytest required):  python3 tests/test_09_gated_publishing.py
No live database, proxy, or network: httpx.post / the RPC helper / the economy_map GET
helpers are all stubbed.
"""
import json
import os
import sys
import types
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Stub third-party + sibling modules that gato_brain and the processor import at
# module level but which are not needed for these unit tests, so both import in a
# bare environment (mirrors test_07_synthesis's harness shape).
# ---------------------------------------------------------------------------
for _name in ("schedule", "tweepy", "resend"):
    if _name not in sys.modules:
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

os.environ.setdefault("OPENCLAW_DATA_DIR", "/tmp/openclaw_test_09")

# --- Import the processor (GATE-01 source) ---------------------------------
sys.path.insert(0, str(_ROOT / "docker" / "processor"))
import agentpulse_processor as proc  # noqa: E402

_REPO_CONFIG = json.loads((_ROOT / "config" / "agentpulse-config.json").read_text())
proc._model_config_cache = _REPO_CONFIG.get("models", {})

# --- Import gato_brain (the write surface under test) ----------------------
# gato_brain imports several heavy sibling modules at module level (anthropic,
# code_commands, cto_commands, …). Stub the ones that pull in network/SDK weight so
# the module imports in the bare test env. init_clients() is only called from __main__,
# so no live supabase/anthropic client is created on import.
for _stub in (
    "code_commands", "cto_commands", "corpus_probe", "intent_router",
    "query_templates", "web_search",
):
    if _stub not in sys.modules:
        sys.modules[_stub] = types.ModuleType(_stub)
# corpus_probe.init / web_search are referenced inside init_clients (not at import),
# so the bare ModuleType stubs are sufficient for import.
if "anthropic" not in sys.modules:
    _anth = types.ModuleType("anthropic")
    _anth.Anthropic = type("Anthropic", (), {"__init__": lambda self, *a, **k: None})
    sys.modules["anthropic"] = _anth

# fastapi / pydantic / supabase are third-party deps gato_brain imports at module level
# but which aren't needed for these unit tests (no FastAPI app exercised, no live client).
# Provide just enough stubs that `from fastapi import ...` etc. succeed.
if "fastapi" not in sys.modules:
    try:
        import fastapi  # noqa: F401
    except Exception:
        _fa = types.ModuleType("fastapi")

        class _Stub:
            def __init__(self, *a, **k):
                pass

            def __call__(self, *a, **k):
                # Allow use as a decorator: @app.get(...) -> returns the fn unchanged.
                def _deco(fn=None, *aa, **kk):
                    return fn
                return _deco

            def __getattr__(self, name):
                return _Stub()

        _fa.FastAPI = _Stub
        _fa.HTTPException = type("HTTPException", (Exception,), {"__init__": lambda self, *a, **k: None})
        _fa.Header = lambda *a, **k: None
        _fa.Query = lambda *a, **k: None
        _fa.Request = _Stub
        sys.modules["fastapi"] = _fa

if "pydantic" not in sys.modules:
    try:
        import pydantic  # noqa: F401
    except Exception:
        _pyd = types.ModuleType("pydantic")
        _pyd.BaseModel = type("BaseModel", (), {})
        sys.modules["pydantic"] = _pyd

if "supabase" not in sys.modules:
    try:
        import supabase  # noqa: F401
    except Exception:
        _sb = types.ModuleType("supabase")
        _sb.create_client = lambda *a, **k: object()
        _sb.Client = object
        sys.modules["supabase"] = _sb

# Provide the env vars gato_brain reads at module load (it only reads, init is lazy).
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "service-role-test-key")

sys.path.insert(0, str(_ROOT / "docker" / "gato_brain"))
import gato_brain as gb  # noqa: E402

_VALID_UUID = str(uuid.uuid4())


class _FakeResponse:
    """Minimal PostgREST-shaped response: status_code + json()/text."""

    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or (json.dumps(payload) if payload is not None else "")
        self.headers = {}

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


# ===========================================================================
# Stub helpers for the processor draft writer (GATE-01)
# ===========================================================================
def _install_proc_post_stub(monkey, response):
    """Patch the processor's httpx.post + agent key; capture url/headers/body."""
    captured = {}
    monkey["agent_key"] = getattr(proc, "_get_agent_api_key", None)
    monkey["httpx_post"] = proc.httpx.post
    if hasattr(proc, "_get_agent_api_key"):
        proc._get_agent_api_key = lambda: "ap_processor_test"

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        captured["url"] = url
        captured["headers"] = headers or {}
        captured["body"] = json or {}
        if isinstance(response, Exception):
            raise response
        return response

    proc.httpx.post = fake_post
    return captured


def _restore_proc_post(monkey):
    if monkey.get("agent_key") is not None:
        proc._get_agent_api_key = monkey["agent_key"]
    proc.httpx.post = monkey["httpx_post"]


# ===========================================================================
# Stub helpers for the gato_brain write surface
# ===========================================================================
def _install_gb_stubs(monkey, *, rpc_side_effect=None, draft=None, block=None):
    """Stub gb._economy_map_rpc + the two GET helpers; count RPC calls.

    rpc_side_effect: None -> success no-op; an Exception instance -> raised when the RPC
    is invoked. `draft` / `block` are the rows returned by get_draft_version_by_id /
    get_block_by_slug. Returns a `calls` dict tracking RPC invocations (fn + version_id).
    """
    calls = {"rpc": []}
    monkey["rpc"] = gb._economy_map_rpc
    monkey["get_draft"] = gb.get_draft_version_by_id
    monkey["get_block"] = gb.get_block_by_slug

    def fake_rpc(fn, version_id):
        calls["rpc"].append((fn, version_id))
        if isinstance(rpc_side_effect, Exception):
            raise rpc_side_effect
        return _FakeResponse(204)

    gb._economy_map_rpc = fake_rpc
    gb.get_draft_version_by_id = lambda vid: draft
    gb.get_block_by_slug = lambda slug: block
    return calls


def _restore_gb(monkey):
    gb._economy_map_rpc = monkey["rpc"]
    gb.get_draft_version_by_id = monkey["get_draft"]
    gb.get_block_by_slug = monkey["get_block"]


# ===========================================================================
# GATE-01 — synthesis writer is draft-only (omits status, never blocks/published)
# ===========================================================================
def test_gate01_synthesis_writer_omits_status_and_targets_versions_only():
    monkey = {}
    captured = _install_proc_post_stub(monkey, _FakeResponse(201, [{"id": "v1", "status": "draft"}]))
    try:
        row = {
            "block_slug": "identity-trust",
            "body_md": "## What it is\n...",
            "proposed_maturity": "emerging",
            "synthesized_from_through": "2026-06-01T00:00:00+00:00",
            "validator_report": {"requires_attention": False},
        }
        proc.economy_map_insert_block_body_version(row)
    finally:
        _restore_proc_post(monkey)

    # Targets the versions table, never the blocks table. endswith() pins the full
    # final path segment (IN-02: a substring check on rsplit()[-1] passes for wrong
    # URLs too, since the last segment can never contain its own leading slash).
    assert captured["url"].endswith("/block_body_versions")
    assert not captured["url"].rstrip("/").endswith("/blocks")
    assert captured["headers"].get("Content-Profile") == "economy_map"
    # GATE-01: status omitted -> DB default 'draft'. Never a published/superseded write.
    assert "status" not in captured["body"], "synthesis must NOT write a status (draft-only)"
    for forbidden in ("published_at", "current_body_version_id", "maturity"):
        assert forbidden not in captured["body"]


# ===========================================================================
# T-09-06 — owner gate: non-owner never reaches the RPC; owner does
# ===========================================================================
def test_approve_non_owner_refused_and_no_rpc():
    monkey = {}
    calls = _install_gb_stubs(monkey)
    try:
        out = gb.handle_map_command(f"/map-approve {_VALID_UUID}", access_tier="free")
    finally:
        _restore_gb(monkey)
    assert "owner" in out.lower()
    assert calls["rpc"] == [], "non-owner /map-approve must NOT call the RPC"


def test_reject_non_owner_refused_and_no_rpc():
    monkey = {}
    calls = _install_gb_stubs(monkey)
    try:
        out = gb.handle_map_command(f"/map-reject {_VALID_UUID}", access_tier="subscriber")
    finally:
        _restore_gb(monkey)
    assert "owner" in out.lower()
    assert calls["rpc"] == [], "non-owner /map-reject must NOT call the RPC"


def test_approve_owner_calls_rpc():
    monkey = {}
    calls = _install_gb_stubs(
        monkey,
        draft={"block_slug": "identity-trust", "proposed_maturity": "emerging"},
        block={"slug": "identity-trust", "maturity": "nascent"},
    )
    try:
        gb.handle_map_command(f"/map-approve {_VALID_UUID}", access_tier="owner")
    finally:
        _restore_gb(monkey)
    assert calls["rpc"] == [("publish_block_version", _VALID_UUID)]


def test_reject_owner_calls_rpc():
    monkey = {}
    calls = _install_gb_stubs(monkey, draft={"block_slug": "identity-trust"})
    try:
        gb.handle_map_command(f"/map-reject {_VALID_UUID}", access_tier="owner")
    finally:
        _restore_gb(monkey)
    assert calls["rpc"] == [("reject_block_version", _VALID_UUID)]


# ===========================================================================
# T-09-07 — UUID validation before any RPC (missing + malformed)
# ===========================================================================
def test_approve_missing_arg_usage_hint_no_rpc():
    monkey = {}
    calls = _install_gb_stubs(monkey)
    try:
        out = gb.handle_map_command("/map-approve", access_tier="owner")
    finally:
        _restore_gb(monkey)
    assert "usage" in out.lower()
    assert calls["rpc"] == [], "missing arg must NOT call the RPC"


def test_reject_missing_arg_usage_hint_no_rpc():
    # IN-01: symmetry with the approve side — a bare /map-reject must return the usage
    # hint and never reach the RPC (guards against an asymmetric future refactor).
    monkey = {}
    calls = _install_gb_stubs(monkey)
    try:
        out = gb.handle_map_command("/map-reject", access_tier="owner")
    finally:
        _restore_gb(monkey)
    assert "usage" in out.lower()
    assert calls["rpc"] == [], "missing arg must NOT call the RPC"


def test_approve_malformed_uuid_usage_hint_no_rpc():
    monkey = {}
    calls = _install_gb_stubs(monkey)
    try:
        out = gb.handle_map_command("/map-approve notauuid", access_tier="owner")
    finally:
        _restore_gb(monkey)
    assert "not a valid" in out.lower() or "usage" in out.lower()
    assert calls["rpc"] == [], "malformed uuid must NOT call the RPC"


def test_reject_malformed_uuid_usage_hint_no_rpc():
    monkey = {}
    calls = _install_gb_stubs(monkey)
    try:
        out = gb.handle_map_command("/map-reject 12345", access_tier="owner")
    finally:
        _restore_gb(monkey)
    assert "not a valid" in out.lower() or "usage" in out.lower()
    assert calls["rpc"] == []


# ===========================================================================
# D-05 case (c) — already-actioned RPC raise maps to the distinct message
# ===========================================================================
def test_approve_already_actioned_maps_to_case_c():
    monkey = {}
    raise_exc = RuntimeError(
        f"economy_map rpc publish_block_version failed (400): "
        f"version {_VALID_UUID} not found or not in draft status"
    )
    _install_gb_stubs(
        monkey, rpc_side_effect=raise_exc,
        draft={"block_slug": "identity-trust", "proposed_maturity": "emerging"},
        block={"slug": "identity-trust", "maturity": "nascent"},
    )
    try:
        out = gb.handle_map_command(f"/map-approve {_VALID_UUID}", access_tier="owner")
    finally:
        _restore_gb(monkey)
    low = out.lower()
    assert "already published/rejected or doesn't exist" in low
    # Not a crash, not a success confirmation.
    assert "command failed" not in low
    assert "✅" not in out


def test_reject_already_actioned_maps_to_case_c():
    monkey = {}
    raise_exc = RuntimeError(
        f"economy_map rpc reject_block_version failed (400): "
        f"version {_VALID_UUID} not found or not in draft status"
    )
    _install_gb_stubs(monkey, rpc_side_effect=raise_exc, draft={"block_slug": "identity-trust"})
    try:
        out = gb.handle_map_command(f"/map-reject {_VALID_UUID}", access_tier="owner")
    finally:
        _restore_gb(monkey)
    low = out.lower()
    assert "already published/rejected or doesn't exist" in low
    assert "command failed" not in low


# ===========================================================================
# D-05 case (d) — any other RPC failure falls through to fail-loud Command failed
# ===========================================================================
def test_approve_other_failure_falls_through_to_command_failed():
    monkey = {}
    raise_exc = RuntimeError("economy_map rpc publish_block_version failed (500): boom")
    _install_gb_stubs(
        monkey, rpc_side_effect=raise_exc,
        draft={"block_slug": "identity-trust", "proposed_maturity": "emerging"},
        block={"slug": "identity-trust", "maturity": "nascent"},
    )
    try:
        out = gb.handle_map_command(f"/map-approve {_VALID_UUID}", access_tier="owner")
    finally:
        _restore_gb(monkey)
    assert "command failed" in out.lower()
    assert "already published/rejected" not in out.lower()


# ===========================================================================
# D-05 approve confirmation — maturity old->new + #/map/<slug> URL
# ===========================================================================
def test_approve_success_confirmation_has_transition_and_url():
    monkey = {}
    _install_gb_stubs(
        monkey,
        draft={"block_slug": "identity-trust", "proposed_maturity": "emerging"},
        block={"slug": "identity-trust", "maturity": "nascent"},
    )
    try:
        out = gb.handle_map_command(f"/map-approve {_VALID_UUID}", access_tier="owner")
    finally:
        _restore_gb(monkey)
    assert "nascent→emerging" in out, "must show maturity old->new"
    assert "https://aiagentspulse.com/#/map/identity-trust" in out, "must show the live #/map URL"


def test_reject_success_confirmation_mentions_next_synthesis():
    monkey = {}
    _install_gb_stubs(monkey, draft={"block_slug": "identity-trust"})
    try:
        out = gb.handle_map_command(f"/map-reject {_VALID_UUID}", access_tier="owner")
    finally:
        _restore_gb(monkey)
    low = out.lower()
    assert "next synthesis" in low
    assert "no change to the live page" in low


# ===========================================================================
# D-02a — read commands remain ungated (no RPC, work at free tier)
# ===========================================================================
def test_read_commands_remain_ungated():
    monkey = {}
    calls = _install_gb_stubs(monkey)
    # Stub the read renderers so we don't hit the network.
    saved_status = gb.handle_map_status
    saved_pending = gb.handle_map_pending
    gb.handle_map_status = lambda: "STATUS_OK"
    gb.handle_map_pending = lambda: "PENDING_OK"
    try:
        assert gb.handle_map_command("/map-status", access_tier="free") == "STATUS_OK"
        assert gb.handle_map_command("/map-pending", access_tier="free") == "PENDING_OK"
    finally:
        gb.handle_map_status = saved_status
        gb.handle_map_pending = saved_pending
        _restore_gb(monkey)
    assert calls["rpc"] == [], "read commands must never call the write RPC"


# ===========================================================================
# Standalone runner (mirrors test_07 — runnable without pytest)
# ===========================================================================
if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
