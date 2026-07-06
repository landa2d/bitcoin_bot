#!/usr/bin/env python3
"""
Quick task 260706-lim — /newsletter_promote bridge-scope sanity tests.

BRIDGE SCOPE (deliberately ~5 cases, NOT the test_unhold_handler.py full matrix):
this command is designed to be RETIRED at the `block_pipeline.enabled=true`
cut-over (target 2026-08-01; criteria in migration 047's header). Coverage is
the locked design's happy paths + owner gate + the two loud failure modes.

Deliberately-SKIPPED edge coverage — iterate-live known unknowns (also recorded
in the task SUMMARY):
  - multi-shadow editions (several A/B shadow rows on one edition number; the
    handler targets the newest by created_at, unproven here)
  - republish collisions (promoting into an edition number that later gets
    published concurrently; the RPC's published-collision raise is the guard)
  - concurrent promotion (two operators confirming at once; last-write posture
    unexamined — the RPC's validations bound the damage)

Cases:
  1. Owner gate: non-owner tiers refused BEFORE any DB read (captured == []).
  2. Preview happy path: shadow+primary ids, suggested public number
     (max published + 1), eval verdict, exact confirm command — zero mutation,
     zero rpc.
  3. Confirm happy path: exactly ONE rpc("promote_block_edition", ...) with the
     locked params; reply renders the RPC summary + /newsletter_publish reminder.
  4. Shadow not found: clear "no shadow row" error, zero rpc; a primary carrying
     data_snapshot.superseded_by upgrades the error to "already promoted".
  5. No eval recorded: the explicit "⚠ no eval recorded for this row" line.

Run standalone (no pytest required):  python3 tests/test_promote_handler.py
No live database / proxy / network — a `.eq()`-only StubSupabase double is the
only backend (EVAL-03 structural: the stub has NO `.in_()`).
"""
import os
import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Stub third-party + sibling modules gato_brain imports at module level but which
# are not needed for these unit tests (harness reused verbatim from
# tests/test_unhold_handler.py). init_clients() is only called from __main__,
# so no live supabase/anthropic client is created on import.
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

for _stub in (
    "code_commands", "cto_commands", "corpus_probe", "intent_router",
    "query_templates", "web_search",
):
    if _stub not in sys.modules:
        sys.modules[_stub] = types.ModuleType(_stub)

if "anthropic" not in sys.modules:
    _anth = types.ModuleType("anthropic")
    _anth.Anthropic = type("Anthropic", (), {"__init__": lambda self, *a, **k: None})
    sys.modules["anthropic"] = _anth

if "fastapi" not in sys.modules:
    try:
        import fastapi  # noqa: F401
    except Exception:
        _fa = types.ModuleType("fastapi")

        class _Stub:
            def __init__(self, *a, **k):
                pass

            def __call__(self, *a, **k):
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

os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "service-role-test-key")

sys.path.insert(0, str(_ROOT / "docker" / "gato_brain"))
import gato_brain as gb  # noqa: E402


# ===========================================================================
# `.eq()`-only StubSupabase double (test_unhold_handler.py's, EXTENDED with
# `rpc(fn_name, params)`: captures ("rpc", fn_name, dict(params)) and returns
# an object whose .execute() yields the canned jsonb summary dict the real
# promote_block_edition RPC returns). Structurally proves EVAL-03: NO `.in_()`
# method — an accidental in-list filter raises AttributeError.
# ===========================================================================
class _StubResult:
    def __init__(self, data):
        self.data = data


class _StubQuery:
    def __init__(self, table_name, rows, captured, raise_on_execute=False):
        self._table = table_name
        self._rows = rows
        self._captured = captured
        self._raise = raise_on_execute
        self._eq = []
        self._orders = []
        self._limit = None
        self._update_payload = None

    def select(self, *a, **k):
        return self

    def eq(self, col, val):
        self._eq.append((col, val))
        self._captured.append(("eq", col, val))
        return self

    def order(self, col, desc=False, **k):
        self._orders.append((col, desc))
        self._captured.append(("order", col, desc))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def update(self, payload):
        self._update_payload = dict(payload)
        self._captured.append(("update", self._table, dict(payload)))
        return self

    def execute(self):
        if self._raise:
            raise RuntimeError("stub supabase unavailable")
        rows = [r for r in self._rows if all(r.get(c) == v for c, v in self._eq)]
        if self._update_payload is not None:
            for r in rows:
                r.update(self._update_payload)
            return _StubResult([dict(r) for r in rows])
        for col, desc in reversed(self._orders):
            rows = sorted(rows, key=lambda r: (r.get(col) is None, r.get(col)), reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return _StubResult(rows)

    # NOTE: NO in_ method — accidental `.in_()` raises AttributeError (EVAL-03).


class _StubRpc:
    def __init__(self, summary):
        self._summary = summary

    def execute(self):
        return _StubResult(self._summary)


class StubSupabase:
    def __init__(self, tables=None, raise_on_execute=False):
        self.tables = {name: list(rows) for name, rows in (tables or {}).items()}
        self.captured = []
        self._raise = raise_on_execute

    def table(self, name):
        return _StubQuery(name, self.tables.setdefault(name, []), self.captured, self._raise)

    def rpc(self, fn_name, params):
        self.captured.append(("rpc", fn_name, dict(params)))
        return _StubRpc({
            "shadow_id": params.get("p_shadow_id"),
            "new_edition_number": params.get("p_new_edition_number"),
            "primary_id": params.get("p_primary_id"),
            "primary_status": "held",
        })


# ===========================================================================
# Row builders
# ===========================================================================
def _shadow_row(edition, row_id="shadow-104"):
    return {
        "id": row_id,
        "edition_number": edition,
        "status": "held",
        "title": f"[BLOCK PIPELINE A/B] AgentPulse Edition {edition}",
        "do_not_publish": True,
        "data_snapshot": {"ab_comparison": True},
        "created_at": "2026-07-03T00:00:00Z",
    }


def _primary_row(edition, row_id="prim-104", snapshot=None):
    return {
        "id": row_id,
        "edition_number": edition,
        "status": "draft",
        "title": f"AgentPulse Edition {edition}",
        "do_not_publish": False,
        "data_snapshot": snapshot if snapshot is not None else {"lead_theme": "agents"},
        "created_at": "2026-07-03T00:00:00Z",
    }


def _published_row(edition, row_id="pub-42"):
    return {
        "id": row_id,
        "edition_number": edition,
        "status": "published",
        "title": f"AgentPulse Edition {edition}",
        "do_not_publish": False,
        "data_snapshot": {},
        "created_at": "2026-06-27T00:00:00Z",
    }


def _eval_row(newsletter_id, verdict="passed"):
    return {
        "newsletter_id": newsletter_id,
        "edition_number": 104,
        "pipeline_version": "block_v1",
        "layer": "judge",
        "attempt": 0,
        "eval_status": "ok",
        "verdict": verdict,
        "deterministic_flags": {},
        "judge_scores": {},
    }


def _promotable_stub(*, with_eval=True):
    """Edition 104: A/B shadow + single-pass primary; edition 42 published."""
    evals = [_eval_row("shadow-104")] if with_eval else []
    return StubSupabase(tables={
        "newsletters": [_shadow_row(104), _primary_row(104), _published_row(42)],
        "edition_evals": evals,
    })


# ===========================================================================
# Test 1 — owner gate: refusal BEFORE any read, both command forms
# ===========================================================================
def test_non_owner_refused_and_no_read():
    for tier in ("free", "subscriber"):
        for cmd in ("/newsletter_promote 104", "/newsletter_promote 104 confirm"):
            stub = _promotable_stub()
            out = gb.handle_newsletter_promote(cmd, access_tier=tier, supabase_client=stub)
            assert "owner" in out.lower(), f"tier={tier} cmd={cmd}: no owner refusal"
            assert stub.captured == [], (
                f"tier={tier} cmd={cmd}: non-owner /newsletter_promote must NOT touch the DB"
            )


# ===========================================================================
# Test 2 — preview happy path: zero mutation, zero rpc
# ===========================================================================
def test_preview_happy_path_zero_mutation():
    stub = _promotable_stub()
    out = gb.handle_newsletter_promote(
        "/newsletter_promote 104", access_tier="owner", supabase_client=stub
    )
    assert "shadow-104" in out, "preview must name the shadow row id"
    assert "prim-104" in out, "preview must name the primary row id"
    assert "43" in out, "preview must show the suggested public number (max published 42 + 1)"
    assert "passed" in out, "preview must surface the eval verdict"
    assert "/newsletter_promote 104 confirm" in out, "preview must give the exact confirm command"
    assert not any(c[0] == "update" for c in stub.captured), "preview must NOT mutate"
    assert not any(c[0] == "rpc" for c in stub.captured), "preview must NOT call the RPC"


# ===========================================================================
# Test 3 — confirm happy path: exactly ONE rpc with the locked params
# ===========================================================================
def test_confirm_calls_rpc_with_locked_params():
    stub = _promotable_stub()
    out = gb.handle_newsletter_promote(
        "/newsletter_promote 104 confirm", access_tier="owner", supabase_client=stub
    )
    rpcs = [c for c in stub.captured if c[0] == "rpc"]
    assert len(rpcs) == 1, f"expected exactly ONE rpc call, got {rpcs}"
    _, fn_name, params = rpcs[0]
    assert fn_name == "promote_block_edition"
    assert params == {
        "p_shadow_id": "shadow-104",
        "p_primary_id": "prim-104",
        "p_new_edition_number": 43,
        "p_reason": "promoted via /newsletter_promote by operator",
    }
    # No direct table mutation — the RPC is the ONLY mutation path.
    assert not any(c[0] == "update" for c in stub.captured)
    # Reply renders the RPC summary + the next-step reminder.
    assert "43" in out and "shadow-104" in out and "prim-104" in out
    assert "held" in out.lower()
    assert "/newsletter_publish" in out, "confirm reply must remind the publish next step"


# ===========================================================================
# Test 4 — shadow not found: clear error, zero rpc; superseded_by upgrades it
# ===========================================================================
def test_no_shadow_row_errors_without_rpc():
    # Sub-case A: primary only, never promoted — plain "no shadow row" error.
    stub = StubSupabase(tables={
        "newsletters": [_primary_row(104)],
        "edition_evals": [],
    })
    out = gb.handle_newsletter_promote(
        "/newsletter_promote 104 confirm", access_tier="owner", supabase_client=stub
    )
    assert "no shadow row" in out.lower(), out
    assert not any(c[0] == "rpc" for c in stub.captured)
    assert not any(c[0] == "update" for c in stub.captured)

    # Sub-case B: the primary carries superseded_by — the shadow was ALREADY promoted.
    stub2 = StubSupabase(tables={
        "newsletters": [_primary_row(
            104, snapshot={"lead_theme": "agents", "superseded_by": "shadow-104"}
        )],
        "edition_evals": [],
    })
    out2 = gb.handle_newsletter_promote(
        "/newsletter_promote 104", access_tier="owner", supabase_client=stub2
    )
    assert "already promoted" in out2.lower(), out2
    assert not any(c[0] == "rpc" for c in stub2.captured)


# ===========================================================================
# Test 5 — no eval recorded: the explicit warning line, never a silent omission
# ===========================================================================
def test_preview_warns_when_no_eval_recorded():
    stub = _promotable_stub(with_eval=False)
    out = gb.handle_newsletter_promote(
        "/newsletter_promote 104", access_tier="owner", supabase_client=stub
    )
    assert "⚠ no eval recorded for this row" in out, out
    assert not any(c[0] == "rpc" for c in stub.captured)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import traceback

    _tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    _failed = 0
    for _t in _tests:
        try:
            _t()
            print(f"PASS {_t.__name__}")
        except Exception:
            _failed += 1
            print(f"FAIL {_t.__name__}")
            traceback.print_exc()
    print(f"\n{len(_tests) - _failed}/{len(_tests)} passed")
    sys.exit(1 if _failed else 0)
