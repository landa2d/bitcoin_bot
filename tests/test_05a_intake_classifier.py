#!/usr/bin/env python3
"""
Phase 5 Plan 01 — proxy-routed intake classifier (INTK-02).

Verifies classify_intake_event():
  1. Routes through the llm-proxy (HTTP POST to {LLM_PROXY_URL}/v1/chat/completions),
     NOT a direct DeepSeek SDK call (routed_llm_call).
  2. Carries Authorization: Bearer <processor agent key> and model deepseek-chat.
  3. Returns the parsed {block_slug, tag_confidence} dict on a 2xx proxy response.
  4. Raises (does NOT swallow / fall back to 'unsorted') on proxy non-2xx, network
     error, or unparseable JSON — Plan 02 owns the D-05 unsorted routing.

Run standalone (no pytest required):  python3 tests/test_05a_intake_classifier.py
"""
import json
import os
import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Stub third-party libs the processor imports at module level but that are not
# needed for these unit tests, so the module imports in a bare environment.
# (Mirrors the live-harness shape from test_phase2_integration.py, minus the DB.)
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

os.environ.setdefault("OPENCLAW_DATA_DIR", "/tmp/openclaw_test_05a")
sys.path.insert(0, str(_ROOT / "docker" / "processor"))

import agentpulse_processor as proc  # noqa: E402

# Prime the model-routing cache from the repo config so get_model("extraction")
# resolves to deepseek-chat exactly as it does in the deployed processor (the
# processor hardcodes a /home/openclaw path that is absent in CI/test).
_REPO_CONFIG = json.loads((_ROOT / "config" / "agentpulse-config.json").read_text())
proc._model_config_cache = _REPO_CONFIG.get("models", {})


ALLOWED_SLUGS = [
    "identity-trust", "memory-context", "payments-settlement",
    "autonomy-control", "governance-accountability",
    "psychology-disposition", "regulation-legal",
]

EVENT = {
    "title": "Stripe updates Link wallet for autonomous AI agent spending",
    "summary": "Link lets users authorize AI agents to spend via approval flows.",
    "url": "https://example.com/stripe-link",
}


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or (json.dumps(payload) if payload is not None else "")
        self.headers = {"X-Proxy-Request-Id": "req-test", "X-Proxy-Agent": "processor"}

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def _install_proxy_stub(monkey, response):
    """Patch _get_agent_api_key + httpx.post; record the captured request."""
    captured = {}
    monkey["agent_key"] = proc._get_agent_api_key
    monkey["httpx_post"] = proc.httpx.post

    proc._get_agent_api_key = lambda: "ap_processor_testkey"

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


def _restore(monkey):
    proc._get_agent_api_key = monkey["agent_key"]
    proc.httpx.post = monkey["httpx_post"]


def test_constants_and_function_exist():
    assert hasattr(proc, "INTAKE_CLASSIFIER_PROMPT"), "INTAKE_CLASSIFIER_PROMPT missing"
    assert "{event}" in proc.INTAKE_CLASSIFIER_PROMPT
    assert "{allowed_slugs}" in proc.INTAKE_CLASSIFIER_PROMPT
    assert hasattr(proc, "classify_intake_event"), "classify_intake_event missing"


def test_success_returns_parsed_dict_and_routes_through_proxy():
    payload = {
        "choices": [
            {"message": {"content": '{"block_slug": "payments-settlement", "tag_confidence": 0.91}'}}
        ]
    }
    monkey = {}
    captured = _install_proxy_stub(monkey, _FakeResponse(200, payload))
    try:
        result = proc.classify_intake_event(EVENT, ALLOWED_SLUGS)
    finally:
        _restore(monkey)

    assert result["block_slug"] == "payments-settlement"
    assert result["tag_confidence"] == 0.91
    # Routed through the proxy, not the SDK
    assert captured["url"].endswith("/v1/chat/completions")
    assert proc.LLM_PROXY_URL in captured["url"]
    assert captured["headers"].get("Authorization") == "Bearer ap_processor_testkey"
    assert captured["body"].get("model") == "deepseek-chat"
    assert isinstance(captured["body"].get("messages"), list) and captured["body"]["messages"]


def test_fence_wrapped_json_is_parsed():
    payload = {
        "choices": [
            {"message": {"content": '```json\n{"block_slug": "identity-trust", "tag_confidence": 0.7}\n```'}}
        ]
    }
    monkey = {}
    _install_proxy_stub(monkey, _FakeResponse(200, payload))
    try:
        result = proc.classify_intake_event(EVENT, ALLOWED_SLUGS)
    finally:
        _restore(monkey)
    assert result["block_slug"] == "identity-trust"
    assert result["tag_confidence"] == 0.7


def test_non_2xx_raises():
    monkey = {}
    _install_proxy_stub(monkey, _FakeResponse(502, None, text="bad gateway"))
    try:
        raised = False
        try:
            proc.classify_intake_event(EVENT, ALLOWED_SLUGS)
        except Exception:
            raised = True
    finally:
        _restore(monkey)
    assert raised, "classify_intake_event must raise on non-2xx proxy response"


def test_network_error_raises():
    monkey = {}
    _install_proxy_stub(monkey, RuntimeError("connection refused"))
    try:
        raised = False
        try:
            proc.classify_intake_event(EVENT, ALLOWED_SLUGS)
        except Exception:
            raised = True
    finally:
        _restore(monkey)
    assert raised, "classify_intake_event must raise on network error"


def test_unparseable_json_raises():
    payload = {"choices": [{"message": {"content": "not json at all"}}]}
    monkey = {}
    _install_proxy_stub(monkey, _FakeResponse(200, payload))
    try:
        raised = False
        try:
            proc.classify_intake_event(EVENT, ALLOWED_SLUGS)
        except Exception:
            raised = True
    finally:
        _restore(monkey)
    assert raised, "classify_intake_event must raise on unparseable JSON content"


def _run_all():
    tests = [
        test_constants_and_function_exist,
        test_success_returns_parsed_dict_and_routes_through_proxy,
        test_fence_wrapped_json_is_parsed,
        test_non_2xx_raises,
        test_network_error_raises,
        test_unparseable_json_raises,
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
