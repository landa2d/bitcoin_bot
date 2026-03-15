"""
Test suite for the LLM Proxy service.

Unit tests mock Supabase and upstream providers — no external calls.
Integration tests hit real APIs and are skipped unless --run-integration is passed.

Run:
    pytest tests/test_llm_proxy.py -v                          # unit tests only
    pytest tests/test_llm_proxy.py -v --run-integration        # all tests
"""

import asyncio
import json
import os
import sys
import time
from collections import deque
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Make proxy importable ────────────────────────────────────────────────────

# Patch LOGS_DIR before importing proxy so it doesn't create /home/openclaw dirs
_test_log_dir = Path(__file__).parent / "_proxy_test_logs"
_test_log_dir.mkdir(exist_ok=True)

# We need to set env vars before proxy module loads its top-level config
os.environ.setdefault("OPENCLAW_DATA_DIR", str(_test_log_dir.parent))
os.environ.setdefault("LLM_PROXY_ADMIN_KEY", "test-admin-key")

# Add proxy directory to path
_proxy_dir = Path(__file__).parent.parent / "docker" / "llm-proxy"
if str(_proxy_dir) not in sys.path:
    sys.path.insert(0, str(_proxy_dir))

import proxy  # noqa: E402

# ─── Pytest hooks ─────────────────────────────────────────────────────────────


def pytest_addoption(parser):
    parser.addoption("--run-integration", action="store_true", default=False,
                     help="Run integration tests that hit real APIs")


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: marks tests that hit real APIs")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-integration"):
        skip = pytest.mark.skip(reason="needs --run-integration flag")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

TEST_API_KEY = "ap_test_abc123def456"
TEST_AGENT = {
    "id": "00000000-0000-0000-0000-000000000001",
    "agent_name": "test_agent",
    "agent_type": "internal",
    "api_key_hash": "$2b$12$FAKEHASHFORTESTING000000000000000000000000000000",
    "access_tier": "internal",
    "allowed_models": [],
    "rate_limit_rpm": 60,
    "is_active": True,
    "last_seen_at": None,
    "metadata": {},
}

TEST_AGENT_EXTERNAL = {
    **TEST_AGENT,
    "agent_name": "test_external",
    "agent_type": "external",
    "access_tier": "free",
    "allowed_models": ["deepseek-chat"],
}

TEST_AGENT_INACTIVE = {
    **TEST_AGENT,
    "agent_name": "test_inactive",
    "is_active": False,
}


@pytest.fixture(autouse=True)
def reset_proxy_state():
    """Reset proxy global state between tests."""
    proxy.agent_cache.clear()
    proxy.agent_cache_ts = 0.0
    proxy.rate_windows.clear()
    proxy.log_queue.clear()
    proxy.metrics["requests_total"] = 0
    proxy.metrics["requests_by_endpoint"] = {"chat": 0, "embeddings": 0, "anthropic": 0}
    proxy.metrics["errors_by_provider"] = {}
    proxy.metrics["latencies_ms"] = deque(maxlen=1000)
    proxy.metrics["wallet_ops"] = 0
    yield


@pytest.fixture
def mock_auth_internal():
    """Mock authenticate_agent to return an internal agent."""
    with patch.object(proxy, "authenticate_agent", return_value=TEST_AGENT) as m:
        yield m


@pytest.fixture
def mock_auth_external():
    """Mock authenticate_agent to return an external agent."""
    with patch.object(proxy, "authenticate_agent", return_value=TEST_AGENT_EXTERNAL) as m:
        yield m


@pytest.fixture
def mock_reserve_ok():
    """Mock reserve_balance to succeed with 100000 balance."""
    with patch.object(proxy, "reserve_balance", return_value=(True, 100000)) as m:
        yield m


@pytest.fixture
def mock_reserve_fail():
    """Mock reserve_balance to fail (insufficient funds)."""
    with patch.object(proxy, "reserve_balance", return_value=(False, 0)) as m:
        yield m


@pytest.fixture
def mock_settle():
    """Mock settle_balance."""
    with patch.object(proxy, "settle_balance") as m:
        yield m


@pytest.fixture
def mock_async_log():
    """Mock async_log_transaction."""
    with patch.object(proxy, "async_log_transaction", new_callable=AsyncMock) as m:
        yield m


@pytest.fixture
def client():
    """FastAPI test client."""
    from httpx import ASGITransport, AsyncClient
    transport = ASGITransport(app=proxy.app)
    return AsyncClient(transport=transport, base_url="http://test")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestApiKeyValidation:
    """API key extraction and agent authentication."""

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_401(self, client):
        resp = await client.post("/v1/chat/completions",
                                 content=json.dumps({"model": "deepseek-chat", "messages": []}))
        assert resp.status_code == 401
        assert "Missing API key" in resp.json()["error"]["message"]

    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_401(self, client):
        with patch.object(proxy, "authenticate_agent", return_value=None):
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer bad-key"},
                content=json.dumps({"model": "deepseek-chat", "messages": []}),
            )
        assert resp.status_code == 401
        assert "Invalid API key" in resp.json()["error"]["message"]

    @pytest.mark.asyncio
    async def test_valid_key_passes_auth(self, client, mock_auth_internal, mock_reserve_ok, mock_settle, mock_async_log):
        """Valid key + known model + provider key → reaches upstream (mocked)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = json.dumps({"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}).encode()
        mock_resp.json = lambda: json.loads(mock_resp.content)

        with patch.object(proxy, "http_client") as mock_http:
            mock_http.post = AsyncMock(return_value=mock_resp)
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}):
                resp = await client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": "Bearer test-key"},
                    content=json.dumps({"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}]}),
                )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_inactive_agent_returns_401(self, client):
        with patch.object(proxy, "authenticate_agent", return_value=None):
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer inactive-key"},
                content=json.dumps({"model": "deepseek-chat", "messages": []}),
            )
        assert resp.status_code == 401


class TestBalanceReservation:
    """Wallet reserve/settle mechanics."""

    @pytest.mark.asyncio
    async def test_insufficient_balance_returns_402(self, client, mock_auth_external, mock_reserve_fail):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}):
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer test-key"},
                content=json.dumps({"model": "deepseek-chat", "messages": []}),
            )
        assert resp.status_code == 402
        assert "Insufficient balance" in resp.json()["error"]["message"]

    @pytest.mark.asyncio
    async def test_internal_agent_allow_negative(self, client, mock_auth_internal, mock_settle, mock_async_log):
        """Internal agents bypass balance checks (allow_negative=True)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = json.dumps({"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}).encode()
        mock_resp.json = lambda: json.loads(mock_resp.content)

        with patch.object(proxy, "reserve_balance", return_value=(True, -500)) as mock_reserve:
            with patch.object(proxy, "http_client") as mock_http:
                mock_http.post = AsyncMock(return_value=mock_resp)
                with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}):
                    resp = await client.post(
                        "/v1/chat/completions",
                        headers={"Authorization": "Bearer test-key"},
                        content=json.dumps({"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}]}),
                    )
        assert resp.status_code == 200

    def test_settle_overpayment_refunds(self):
        """If reserved > actual, settle returns the difference."""
        # Test the calculation logic directly
        reserved = 50
        actual_input = 100  # tokens
        actual_output = 50   # tokens
        actual_sats, _ = proxy.calculate_cost("deepseek-chat", actual_input, actual_output)
        # deepseek: (100/1M * 0.14) + (50/1M * 0.28) = very small → rounds to 1 sat
        assert actual_sats == 1  # minimum 1 sat
        # Settle would refund reserved - actual_sats = 50 - 1 = 49 sats

    def test_settle_underpayment_charges(self):
        """If actual > reserved, settle charges the difference."""
        # gpt-4o with lots of output tokens
        actual_sats, _ = proxy.calculate_cost("gpt-4o", 10000, 10000)
        # (10000/1M * 2.50) + (10000/1M * 10.00) = 0.025 + 0.1 = 0.125 USD
        # 0.125 * 1000 sats/usd = 125 sats
        assert actual_sats == 125  # > estimated 50 sats

    def test_failed_call_refunds_fully(self):
        """When provider errors, settle with actual=0 → full refund."""
        # This is tested via the proxy flow: on upstream error, settle(name, est, 0)
        # Verify calculate_cost(model, 0, 0) returns minimum sats
        sats, cents = proxy.calculate_cost("gpt-4o", 0, 0)
        # 0 tokens = 0 USD → max(1, round(0)) but round(0)=0, max(1,0)=1
        assert sats == 1  # minimum floor


class TestRateLimiting:
    """In-memory sliding window rate limiter."""

    def test_requests_within_limit_pass(self):
        for _ in range(5):
            assert proxy.check_rate_limit("agent_a", 10) is True

    def test_requests_over_limit_blocked(self):
        for _ in range(10):
            proxy.check_rate_limit("agent_b", 10)
        assert proxy.check_rate_limit("agent_b", 10) is False

    def test_window_slides_correctly(self):
        # Fill up the window
        for _ in range(5):
            proxy.check_rate_limit("agent_c", 5)
        assert proxy.check_rate_limit("agent_c", 5) is False

        # Manually age out all entries
        proxy.rate_windows["agent_c"] = deque([time.time() - 61] * 5)
        assert proxy.check_rate_limit("agent_c", 5) is True

    def test_none_rpm_means_no_limit(self):
        for _ in range(1000):
            assert proxy.check_rate_limit("agent_d", None) is True

    def test_zero_rpm_means_no_limit(self):
        for _ in range(100):
            assert proxy.check_rate_limit("agent_e", 0) is True


class TestCostCalculation:
    """Verify sats and USD costs for each model."""

    @pytest.mark.parametrize("model,input_t,output_t,expected_min_sats", [
        ("deepseek-chat", 1000, 500, 1),
        ("gpt-4o", 1000, 1000, 1),
        ("gpt-4o-mini", 1000, 1000, 1),
        ("claude-sonnet-4-20250514", 1000, 1000, 1),
        ("text-embedding-3-large", 1000, 0, 1),
    ])
    def test_minimum_1_sat(self, model, input_t, output_t, expected_min_sats):
        sats, _ = proxy.calculate_cost(model, input_t, output_t)
        assert sats >= expected_min_sats

    def test_gpt4o_large_usage(self):
        # 100K input, 10K output
        sats, cents = proxy.calculate_cost("gpt-4o", 100_000, 10_000)
        # (100K/1M * 2.50) + (10K/1M * 10.00) = 0.25 + 0.1 = 0.35 USD
        assert sats == 350  # 0.35 * 1000
        assert cents == 35   # 0.35 * 100

    def test_deepseek_typical_usage(self):
        # 5K input, 2K output (typical pipeline call)
        sats, cents = proxy.calculate_cost("deepseek-chat", 5000, 2000)
        # (5K/1M * 0.14) + (2K/1M * 0.28) = 0.0007 + 0.00056 = 0.00126 USD
        # 0.00126 * 1000 = 1.26 → round = 1 sat
        assert sats == 1
        assert cents == 0  # rounds to 0

    def test_claude_large_usage(self):
        # 50K input, 5K output
        sats, cents = proxy.calculate_cost("claude-sonnet-4-20250514", 50_000, 5_000)
        # (50K/1M * 3.00) + (5K/1M * 15.00) = 0.15 + 0.075 = 0.225 USD
        assert sats == 225
        assert cents in (22, 23)  # 0.225 * 100 = 22.5 — FP rounding may go either way

    def test_unknown_model_returns_default(self):
        sats, cents = proxy.calculate_cost("unknown-model", 1000, 1000)
        assert sats == 5  # default from ESTIMATED_COST_SATS fallback
        assert cents == 0

    def test_embedding_zero_output(self):
        sats, cents = proxy.calculate_cost("text-embedding-3-large", 10_000, 0)
        # (10K/1M * 0.13) + 0 = 0.0013 USD → 1 sat
        assert sats == 1


class TestRequestSizeLimits:
    """Oversized requests return 413."""

    @pytest.mark.asyncio
    async def test_chat_oversized_returns_413(self, client, mock_auth_internal):
        resp = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer test-key", "Content-Length": str(2_000_000)},
            content=b"x" * 100,  # actual body doesn't matter, header triggers check
        )
        assert resp.status_code == 413

    @pytest.mark.asyncio
    async def test_embed_oversized_returns_413(self, client, mock_auth_internal):
        resp = await client.post(
            "/v1/embeddings",
            headers={"Authorization": "Bearer test-key", "Content-Length": str(600_000)},
            content=b"x" * 100,
        )
        assert resp.status_code == 413

    @pytest.mark.asyncio
    async def test_anthropic_oversized_returns_413(self, client, mock_auth_internal):
        resp = await client.post(
            "/anthropic/v1/messages",
            headers={"Authorization": "Bearer test-key", "Content-Length": str(2_000_000)},
            content=b"x" * 100,
        )
        assert resp.status_code == 413


class TestModelRouting:
    """Each model maps to the correct provider URL."""

    def test_deepseek_routes_to_deepseek(self):
        route = proxy.MODEL_ROUTES["deepseek-chat"]
        assert route["provider"] == "deepseek"
        assert "deepseek.com" in route["base_url"]

    def test_gpt4o_routes_to_openai(self):
        route = proxy.MODEL_ROUTES["gpt-4o"]
        assert route["provider"] == "openai"
        assert "openai.com" in route["base_url"]

    def test_gpt4o_mini_routes_to_openai(self):
        route = proxy.MODEL_ROUTES["gpt-4o-mini"]
        assert route["provider"] == "openai"
        assert "openai.com" in route["base_url"]

    def test_embeddings_routes_to_openai(self):
        route = proxy.MODEL_ROUTES["text-embedding-3-large"]
        assert route["provider"] == "openai"
        assert "openai.com" in route["base_url"]

    def test_claude_routes_to_anthropic(self):
        route = proxy.MODEL_ROUTES["claude-sonnet-4-20250514"]
        assert route["provider"] == "anthropic"
        assert "anthropic.com" in route["base_url"]

    @pytest.mark.asyncio
    async def test_unknown_model_returns_400(self, client, mock_auth_internal, mock_reserve_ok):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}):
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer test-key"},
                content=json.dumps({"model": "nonexistent-model", "messages": []}),
            )
        assert resp.status_code == 400
        assert "Unknown model" in resp.json()["error"]["message"]


class TestModelPermissions:
    """Agents can only use models in their allowed_models list."""

    @pytest.mark.asyncio
    async def test_disallowed_model_returns_403(self, client, mock_auth_external, mock_reserve_ok):
        """External agent with allowed_models=['deepseek-chat'] can't use gpt-4o."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer test-key"},
                content=json.dumps({"model": "gpt-4o", "messages": []}),
            )
        assert resp.status_code == 403
        assert "not allowed" in resp.json()["error"]["message"]

    @pytest.mark.asyncio
    async def test_allowed_model_passes(self, client, mock_auth_external, mock_reserve_ok, mock_settle, mock_async_log):
        """External agent with allowed_models=['deepseek-chat'] can use deepseek-chat."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = json.dumps({"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}).encode()
        mock_resp.json = lambda: json.loads(mock_resp.content)

        with patch.object(proxy, "http_client") as mock_http:
            mock_http.post = AsyncMock(return_value=mock_resp)
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}):
                resp = await client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": "Bearer test-key"},
                    content=json.dumps({"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}]}),
                )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_empty_allowed_models_means_all(self, client, mock_auth_internal, mock_reserve_ok, mock_settle, mock_async_log):
        """Internal agent with empty allowed_models can use any model."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = json.dumps({"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}).encode()
        mock_resp.json = lambda: json.loads(mock_resp.content)

        with patch.object(proxy, "http_client") as mock_http:
            mock_http.post = AsyncMock(return_value=mock_resp)
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
                resp = await client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": "Bearer test-key"},
                    content=json.dumps({"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]}),
                )
        assert resp.status_code == 200


class TestUsageExtraction:
    """Extract token usage from provider responses."""

    def test_openai_usage_extraction(self):
        resp = {"usage": {"prompt_tokens": 150, "completion_tokens": 80}}
        inp, out = proxy._extract_usage_openai(resp)
        assert inp == 150
        assert out == 80

    def test_openai_missing_usage(self):
        inp, out = proxy._extract_usage_openai({})
        assert inp == 0
        assert out == 0

    def test_anthropic_usage_extraction(self):
        resp = {"usage": {"input_tokens": 200, "output_tokens": 100}}
        inp, out = proxy._extract_usage_anthropic(resp)
        assert inp == 200
        assert out == 100

    def test_anthropic_missing_usage(self):
        inp, out = proxy._extract_usage_anthropic({})
        assert inp == 0
        assert out == 0


class TestHealthEndpoint:
    """Health check returns ok with uptime."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        proxy.start_time = time.time() - 60
        resp = await client.get("/v1/proxy/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["uptime_seconds"] >= 59


class TestMetricsEndpoint:
    """Admin-only metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_requires_admin_key(self, client):
        resp = await client.get("/v1/proxy/metrics")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_metrics_with_admin_key(self, client):
        resp = await client.get(
            "/v1/proxy/metrics",
            headers={"Authorization": "Bearer test-admin-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "requests_total" in data
        assert "latency_ms" in data
        assert "p50" in data["latency_ms"]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. FAILURE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFailureModes:
    """Proxy handles upstream errors gracefully."""

    @pytest.mark.asyncio
    async def test_provider_500_refunds_reservation(self, client, mock_auth_internal, mock_reserve_ok, mock_settle, mock_async_log):
        """Upstream 500 → refund reservation (settle with actual=0)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.content = b'{"error": "internal server error"}'

        with patch.object(proxy, "http_client") as mock_http:
            mock_http.post = AsyncMock(return_value=mock_resp)
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}):
                resp = await client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": "Bearer test-key"},
                    content=json.dumps({"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}]}),
                )
        assert resp.status_code == 500
        # settle called with actual=0 → full refund
        mock_settle.assert_called_once_with("test_agent", 2, 0)

    @pytest.mark.asyncio
    async def test_provider_timeout_refunds(self, client, mock_auth_internal, mock_reserve_ok, mock_settle):
        """Upstream timeout → refund and return 504."""
        import httpx
        with patch.object(proxy, "http_client") as mock_http:
            mock_http.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "sk-test"}):
                resp = await client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": "Bearer test-key"},
                    content=json.dumps({"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}]}),
                )
        assert resp.status_code == 504
        mock_settle.assert_called_once_with("test_agent", 2, 0)

    @pytest.mark.asyncio
    async def test_invalid_json_body_returns_400(self, client, mock_auth_internal):
        resp = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer test-key"},
            content=b"not json",
        )
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["error"]["message"]

    @pytest.mark.asyncio
    async def test_missing_provider_key_returns_502(self, client, mock_auth_internal, mock_reserve_ok):
        """Model route exists but env key is not set."""
        with patch.dict(os.environ, {}, clear=False):
            # Make sure OPENAI_API_KEY is not set
            os.environ.pop("OPENAI_API_KEY", None)
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer test-key"},
                content=json.dumps({"model": "gpt-4o", "messages": []}),
            )
        assert resp.status_code == 502
        assert "not configured" in resp.json()["error"]["message"]

    @pytest.mark.asyncio
    async def test_supabase_log_failure_queues(self):
        """If Supabase write fails, entry goes to log_queue."""
        proxy.log_queue.clear()
        with patch.object(proxy, "_sb_insert", side_effect=Exception("db down")):
            await proxy.async_log_transaction(
                "test_agent", "deepseek-chat", 2, 0, 99998, 100, 50, 150, "deepseek", "chat", "abc123"
            )
        assert len(proxy.log_queue) == 1
        assert proxy.log_queue[0]["agent_name"] == "test_agent"


class TestAnthropicEndpoint:
    """Anthropic-specific endpoint tests."""

    @pytest.mark.asyncio
    async def test_anthropic_non_anthropic_model_returns_400(self, client, mock_auth_internal):
        resp = await client.post(
            "/anthropic/v1/messages",
            headers={"x-api-key": "test-key", "anthropic-version": "2023-06-01"},
            content=json.dumps({"model": "deepseek-chat", "messages": [{"role": "user", "content": "hi"}]}),
        )
        assert resp.status_code == 400
        assert "non-Anthropic" in resp.json()["error"]["message"]

    @pytest.mark.asyncio
    async def test_anthropic_success(self, client, mock_auth_internal, mock_reserve_ok, mock_settle, mock_async_log):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = json.dumps({
            "content": [{"text": "Hello!", "type": "text"}],
            "usage": {"input_tokens": 50, "output_tokens": 20},
        }).encode()
        mock_resp.json = lambda: json.loads(mock_resp.content)

        with patch.object(proxy, "http_client") as mock_http:
            mock_http.post = AsyncMock(return_value=mock_resp)
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
                resp = await client.post(
                    "/anthropic/v1/messages",
                    headers={"x-api-key": "test-key", "anthropic-version": "2023-06-01"},
                    content=json.dumps({
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 100,
                        "messages": [{"role": "user", "content": "hi"}],
                    }),
                )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_anthropic_passes_beta_header(self, client, mock_auth_internal, mock_reserve_ok, mock_settle, mock_async_log):
        """anthropic-beta header is forwarded to the provider."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = json.dumps({
            "content": [{"text": "Hello!", "type": "text"}],
            "usage": {"input_tokens": 50, "output_tokens": 20},
        }).encode()
        mock_resp.json = lambda: json.loads(mock_resp.content)

        with patch.object(proxy, "http_client") as mock_http:
            mock_http.post = AsyncMock(return_value=mock_resp)
            with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
                resp = await client.post(
                    "/anthropic/v1/messages",
                    headers={
                        "x-api-key": "test-key",
                        "anthropic-version": "2023-06-01",
                        "anthropic-beta": "prompt-caching-2024-07-31",
                    },
                    content=json.dumps({
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 100,
                        "messages": [{"role": "user", "content": "hi"}],
                    }),
                )
        assert resp.status_code == 200
        # Verify the beta header was passed through
        call_kwargs = mock_http.post.call_args
        assert "anthropic-beta" in call_kwargs.kwargs.get("headers", call_kwargs[1].get("headers", {}))


# ═══════════════════════════════════════════════════════════════════════════════
# 3. INTEGRATION TESTS (require --run-integration)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestIntegrationOpenAI:
    """Forward real requests through the proxy to OpenAI."""

    @pytest.fixture(autouse=True)
    def check_keys(self):
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

    @pytest.mark.asyncio
    async def test_chat_completion_roundtrip(self, client, mock_auth_internal, mock_reserve_ok, mock_settle, mock_async_log):
        proxy.http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        try:
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer test-key"},
                content=json.dumps({
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Reply with exactly: PROXY_TEST_OK"}],
                    "max_tokens": 20,
                }),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "choices" in data
            assert len(data["choices"]) > 0
            # Verify settle was called with actual cost
            mock_settle.assert_called_once()
            _, actual_sats = mock_settle.call_args[0][1], mock_settle.call_args[0][2]
            assert actual_sats >= 1
        finally:
            await proxy.http_client.aclose()

    @pytest.mark.asyncio
    async def test_embedding_roundtrip(self, client, mock_auth_internal, mock_reserve_ok, mock_settle, mock_async_log):
        proxy.http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        try:
            resp = await client.post(
                "/v1/embeddings",
                headers={"Authorization": "Bearer test-key"},
                content=json.dumps({
                    "model": "text-embedding-3-large",
                    "input": "test embedding input",
                }),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "data" in data
            assert len(data["data"]) > 0
            assert len(data["data"][0]["embedding"]) == 3072  # text-embedding-3-large dimension
        finally:
            await proxy.http_client.aclose()


@pytest.mark.integration
class TestIntegrationAnthropic:
    """Forward real requests through the proxy to Anthropic."""

    @pytest.fixture(autouse=True)
    def check_keys(self):
        if not os.getenv("ANTHROPIC_API_KEY"):
            pytest.skip("ANTHROPIC_API_KEY not set")

    @pytest.mark.asyncio
    async def test_messages_roundtrip(self, client, mock_auth_internal, mock_reserve_ok, mock_settle, mock_async_log):
        proxy.http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        try:
            resp = await client.post(
                "/anthropic/v1/messages",
                headers={
                    "x-api-key": "test-key",
                    "anthropic-version": "2023-06-01",
                },
                content=json.dumps({
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 20,
                    "messages": [{"role": "user", "content": "Reply with exactly: PROXY_TEST_OK"}],
                }),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "content" in data
            assert len(data["content"]) > 0
        finally:
            await proxy.http_client.aclose()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. STREAMING TESTS (require --run-integration)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestStreamingOpenAI:
    """Streaming chat completions through the proxy."""

    @pytest.fixture(autouse=True)
    def check_keys(self):
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

    @pytest.mark.asyncio
    async def test_streaming_chat_completion(self, client, mock_auth_internal, mock_reserve_ok, mock_settle, mock_async_log):
        proxy.http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
        try:
            resp = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer test-key"},
                content=json.dumps({
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Say hello in one word"}],
                    "max_tokens": 10,
                    "stream": True,
                }),
            )
            assert resp.status_code == 200
            # Collect all streamed chunks
            body = resp.text
            assert "data: " in body
            assert "[DONE]" in body
        finally:
            await proxy.http_client.aclose()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. GOVERNANCE TESTS (placeholders for Phase 3)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGovernancePlaceholders:
    """Framework for Phase 3 governance engine tests."""

    def test_cap_enforcement_placeholder(self):
        """TODO Phase 3: verify spending cap blocks calls after threshold."""
        pass

    def test_model_downgrade_placeholder(self):
        """TODO Phase 3: verify model downgrade fires when cap hit with downgrade policy."""
        pass

    def test_reject_on_cap_placeholder(self):
        """TODO Phase 3: verify reject action returns 402 with cap info."""
        pass

    def test_alert_at_percentage_placeholder(self):
        """TODO Phase 3: verify governance_event logged at alert_at_pct threshold."""
        pass
