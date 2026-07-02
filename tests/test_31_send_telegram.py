#!/usr/bin/env python3
"""
Phase 31 / Plan 01 — SURF-01 unit suite for the processor's hardened `send_telegram`
fail-loud contract (D-01/D-02/D-04) plus the auto-publish critical-caller return check (D-03).

Locks the contract in place (D-01 — the processor's `send_telegram` is hardened where it
lives; the newsletter's `_alert_operator` is NOT touched this phase):

  - env unset (either TELEGRAM_BOT_TOKEN or TELEGRAM_OWNER_ID falsy): returns False AND
    ERROR-logs a fixed grep-able `[TELEGRAM-SEND]` label — never a silent bare return (D-02).
  - happy path (every httpx POST returns 200): returns True.
  - delivery failure (Markdown POST !=200 then plain-text POST !=200): returns False AND
    ERROR-logs; the httpx-exception path also returns False AND ERROR-logs — neither raises.
  - boot-time config check: with either env var unset, ERROR-logs a fixed `[TELEGRAM-CONFIG]`
    label and returns False; the process still runs (never raises) (D-04).
  - auto-publish notification (D-03): a hold/eval-critical caller that checks send_telegram's
    bool return and CRITICAL-logs `[EVAL-ALERT] CRITICAL` on delivery failure.

Imports the REAL `agentpulse_processor` module (the test_09 harness bootstrap) — no
re-implementation (the test_19 rule; a copy could pass while production regresses).
ZERO live egress, ZERO live DB: httpx.Client is a fake, supabase is an in-memory stub.

Run:  python3 -m pytest tests/test_31_send_telegram.py -q
"""
import logging
import os
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Stub third-party modules the processor imports at module level but which are
# not needed for these unit tests, so the processor imports in a bare env
# (mirrors tests/test_09_gated_publishing.py's harness shape).
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

os.environ.setdefault("OPENCLAW_DATA_DIR", "/tmp/openclaw_test_31")

sys.path.insert(0, str(_ROOT / "docker" / "processor"))
import agentpulse_processor as proc  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes: a minimal httpx.Client double and a chainable supabase stub.
# ---------------------------------------------------------------------------
class _FakeResp:
    def __init__(self, status_code, text="ok"):
        self.status_code = status_code
        self.text = text


class _FakeClient:
    """Context-manager httpx.Client double. Every .post returns `status_code`
    (so a non-200 makes BOTH the Markdown attempt and the plain-text fallback
    fail), or raises `raise_on_post` to exercise the exception path."""

    def __init__(self, status_code=200, raise_on_post=None, record=None):
        self._status = status_code
        self._raise = raise_on_post
        self.record = record if record is not None else []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, data=None, **kw):
        self.record.append((url, data))
        if self._raise is not None:
            raise self._raise
        return _FakeResp(self._status)


def _fake_httpx(status_code=200, raise_on_post=None):
    """A stand-in for the module-level `httpx` exposing only `.Client`."""
    return types.SimpleNamespace(
        Client=lambda *a, **k: _FakeClient(status_code=status_code, raise_on_post=raise_on_post)
    )


class _Chain:
    def __init__(self, data):
        self._data = data

    def select(self, *a, **k):
        return self

    # NOTE: this pre-existing newsletters lookup path DOES use .in_() (status filter);
    # the NEW edition_evals reads (SURF-02/03, later plans) are .eq()-only.
    def in_(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        return types.SimpleNamespace(data=self._data)


class _FakeSupabase:
    def __init__(self, data):
        self._data = data

    def table(self, name):
        return _Chain(self._data)


def _has_record(caplog, substr, level=None):
    for r in caplog.records:
        if substr in r.getMessage():
            if level is None or r.levelno == level:
                return True
    return False


# ===========================================================================
# Task 1 — send_telegram fail-loud contract (D-01/D-02)
# ===========================================================================
def test_env_unset_returns_false_and_error_logs(monkeypatch, caplog):
    """Either env var falsy → returns False AND ERROR-logs `[TELEGRAM-SEND]` — never a bare return."""
    monkeypatch.setattr(proc, "TELEGRAM_BOT_TOKEN", None)
    monkeypatch.setattr(proc, "TELEGRAM_OWNER_ID", "owner-123")
    caplog.set_level(logging.DEBUG)

    result = proc.send_telegram("held: edition 31 would-have-held")

    assert result is False
    assert _has_record(caplog, "[TELEGRAM-SEND]", level=logging.ERROR)
    assert _has_record(caplog, "TELEGRAM_BOT_TOKEN/TELEGRAM_OWNER_ID unset")


def test_happy_path_returns_true(monkeypatch, caplog):
    """Every httpx POST returns 200 → returns True."""
    monkeypatch.setattr(proc, "TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setattr(proc, "TELEGRAM_OWNER_ID", "owner-123")
    monkeypatch.setattr(proc, "httpx", _fake_httpx(status_code=200))
    caplog.set_level(logging.DEBUG)

    result = proc.send_telegram("all good")

    assert result is True


def test_multi_chunk_all_200_returns_true(monkeypatch):
    """A >4000-char message splits on newline boundaries; multi-chunk all-200 still returns True."""
    monkeypatch.setattr(proc, "TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setattr(proc, "TELEGRAM_OWNER_ID", "owner-123")
    seen = _FakeClient(status_code=200)
    monkeypatch.setattr(proc, "httpx", types.SimpleNamespace(Client=lambda *a, **k: seen))

    long_msg = "\n".join(["line %d" % i for i in range(2000)])  # >4000 chars, multi-chunk
    result = proc.send_telegram(long_msg)

    assert result is True
    assert len(seen.record) >= 2  # split into multiple chunks


def test_delivery_failure_returns_false_and_error_logs(monkeypatch, caplog):
    """Markdown POST !=200 then plain-text POST !=200 → returns False AND ERROR-logs `[TELEGRAM-SEND]`."""
    monkeypatch.setattr(proc, "TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setattr(proc, "TELEGRAM_OWNER_ID", "owner-123")
    monkeypatch.setattr(proc, "httpx", _fake_httpx(status_code=500))
    caplog.set_level(logging.DEBUG)

    result = proc.send_telegram("delivery will fail")

    assert result is False
    assert _has_record(caplog, "[TELEGRAM-SEND]", level=logging.ERROR)


def test_exception_path_returns_false_and_does_not_raise(monkeypatch, caplog):
    """An httpx exception is caught → returns False AND ERROR-logs; the exception never propagates."""
    monkeypatch.setattr(proc, "TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setattr(proc, "TELEGRAM_OWNER_ID", "owner-123")
    monkeypatch.setattr(proc, "httpx", _fake_httpx(raise_on_post=RuntimeError("network down")))
    caplog.set_level(logging.DEBUG)

    result = proc.send_telegram("boom")  # must NOT raise

    assert result is False
    assert _has_record(caplog, "[TELEGRAM-SEND]", level=logging.ERROR)


def test_send_telegram_signature_is_bool():
    """The hardened signature returns bool (additive/backward-compatible; never raises — D-02)."""
    import inspect
    sig = inspect.signature(proc.send_telegram)
    assert sig.return_annotation is bool


# ===========================================================================
# Task 1 — boot-time Telegram-config ERROR (D-04)
# ===========================================================================
def test_boot_config_check_error_logs_when_unset(monkeypatch, caplog):
    """Boot-time check: either env var unset → ERROR-logs `[TELEGRAM-CONFIG]`, returns False, never raises."""
    monkeypatch.setattr(proc, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(proc, "TELEGRAM_OWNER_ID", "owner-123")
    caplog.set_level(logging.DEBUG)

    ok = proc._check_telegram_config()

    assert ok is False
    assert _has_record(caplog, "[TELEGRAM-CONFIG]", level=logging.ERROR)


def test_boot_config_check_silent_when_configured(monkeypatch, caplog):
    """Both env vars set → returns True, NO `[TELEGRAM-CONFIG]` ERROR."""
    monkeypatch.setattr(proc, "TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setattr(proc, "TELEGRAM_OWNER_ID", "owner-123")
    caplog.set_level(logging.DEBUG)

    ok = proc._check_telegram_config()

    assert ok is True
    assert not _has_record(caplog, "[TELEGRAM-CONFIG]")


# ===========================================================================
# Task 2 — auto-publish notification checks send_telegram's return (D-03)
# ===========================================================================
def _draft_row(edition=99):
    """A draft row old enough to auto-publish (age >= 1h), not held."""
    created = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    return {
        "id": "nl-1",
        "edition_number": edition,
        "status": "draft",
        "created_at": created,
        "do_not_publish": False,
    }


def test_auto_publish_critical_logs_on_delivery_failure(monkeypatch, caplog):
    """When the auto-publish notification send_telegram returns False, the caller CRITICAL-logs
    a `[EVAL-ALERT] CRITICAL` labeled failure (D-03) — a lost alert leaves an unmissable trace."""
    monkeypatch.setattr(proc, "supabase", _FakeSupabase([_draft_row(edition=99)]))
    monkeypatch.setattr(proc, "publish_newsletter", lambda: {"published": True})
    monkeypatch.setattr(proc, "send_telegram", lambda *a, **k: False)
    caplog.set_level(logging.DEBUG)

    proc.scheduled_auto_publish_newsletter()

    assert _has_record(caplog, "[EVAL-ALERT] CRITICAL", level=logging.CRITICAL)


def test_auto_publish_no_critical_when_delivery_ok(monkeypatch, caplog):
    """When the notification delivers (True), NO CRITICAL log fires — the publish path is unchanged."""
    monkeypatch.setattr(proc, "supabase", _FakeSupabase([_draft_row(edition=100)]))
    monkeypatch.setattr(proc, "publish_newsletter", lambda: {"published": True})
    monkeypatch.setattr(proc, "send_telegram", lambda *a, **k: True)
    caplog.set_level(logging.DEBUG)

    proc.scheduled_auto_publish_newsletter()

    assert not _has_record(caplog, "[EVAL-ALERT] CRITICAL")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
