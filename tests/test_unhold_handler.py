#!/usr/bin/env python3
"""
Quick task 260705-ufj — /newsletter_unhold owner-gated release of a held edition.

Unit coverage for the gato_brain handler added by the pre-enforce-blocker quick task
(mirrors the tests/test_31_newsletter_eval_handler.py harness):

  - T-UNH-01 owner gate: a non-owner tier gets an owner-only refusal and NO supabase
    call ever occurs (StubSupabase.captured stays empty) — any command form.
  - Two-step confirm: bare `/newsletter_unhold <n>` PREVIEWS (hold reason + row id +
    labels/counts-only eval summary + confirm instruction) with ZERO `.update()` calls;
    only `/newsletter_unhold <n> confirm` performs the ONE targeted release update
    `{do_not_publish: False, status: 'draft', do_not_publish_reason: None}` via
    `.eq("id", row_id)` (row id, NEVER edition number).
  - Shadow exclusion: the always-held block_v1 A/B shadow row (data_snapshot
    ab_comparison truthy / "[BLOCK PIPELINE A/B]" title) is NEVER selected for
    release; a shadow-only-held edition gets the explicit "held by design, not
    releasable" message — even with `confirm`.
  - Distinct failure paths: edition-not-found, found-but-not-held (reports the
    primary's current status), supabase-error ("unhold failed: ...") — never a
    silent no-op.
  - Multiple held primaries (regenerated editions): the newest by created_at is
    targeted and the reply notes the count.
  - EVAL-03 structural: the stub query has NO `.in_()` — an accidental in-list
    filter raises AttributeError.

Run standalone (no pytest required):  python3 tests/test_unhold_handler.py
No live database / proxy / network — a `.eq()`-only StubSupabase double is the only backend.
"""
import os
import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Stub third-party + sibling modules gato_brain imports at module level but which
# are not needed for these unit tests, so it imports in a bare env (mirrors the
# test_31_newsletter_eval_handler harness shape). init_clients() is only called
# from __main__, so no live supabase/anthropic client is created on import.
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
# Multi-table `.eq()`-only StubSupabase double. The unhold handler reads BOTH
# `newsletters` (target rows) and `edition_evals` (preview summary), so the stub
# keys rows by table name. `_StubQuery.update(payload)` records the mutation into
# `captured` AND applies it to matching rows on execute so post-state is
# assertable. Structurally proves EVAL-03: NO `.in_()` method — an accidental
# in-list filter raises AttributeError.
# ===========================================================================
class _StubResult:
    def __init__(self, data):
        self.data = data


class _StubQuery:
    def __init__(self, table_name, rows, captured, raise_on_execute=False):
        self._table = table_name
        self._rows = rows  # live reference — updates mutate the table's rows
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


class StubSupabase:
    def __init__(self, tables=None, raise_on_execute=False):
        self.tables = {name: list(rows) for name, rows in (tables or {}).items()}
        self.captured = []
        self._raise = raise_on_execute

    def table(self, name):
        return _StubQuery(name, self.tables.setdefault(name, []), self.captured, self._raise)


# ===========================================================================
# Row builders
# ===========================================================================
def _primary_row(edition, *, held, row_id="prim-1", reason=None,
                 created_at="2026-07-01T00:00:00Z", status=None):
    return {
        "id": row_id,
        "edition_number": edition,
        "status": status if status is not None else ("held" if held else "draft"),
        "title": f"AgentPulse Edition {edition}",
        "do_not_publish": held,
        "do_not_publish_reason": reason,
        "data_snapshot": {"lead_theme": "agents"},
        "created_at": created_at,
    }


def _shadow_row(edition, row_id="shadow-1"):
    """The always-held block_v1 A/B shadow — held BY DESIGN, never releasable."""
    return {
        "id": row_id,
        "edition_number": edition,
        "status": "held",
        "title": f"[BLOCK PIPELINE A/B] AgentPulse Edition {edition}",
        "do_not_publish": True,
        "do_not_publish_reason": "block_v1 A/B comparison shadow",
        "data_snapshot": {"ab_comparison": True},
        "created_at": "2026-07-01T00:00:00Z",
    }


def _det_row(edition, pv="single_pass", verdict="held_fabrication", *,
             fabrication=None, unverified=None, mechanical=None):
    """Minimal edition_evals deterministic row (mirrors the test_31 _det_row shape)."""
    return {
        "edition_number": edition,
        "pipeline_version": pv,
        "layer": "deterministic",
        "attempt": 0,
        "eval_status": "ok",
        "verdict": verdict,
        "deterministic_flags": {
            "fabrication": fabrication or [],
            "unverified": unverified or [],
            "mechanical": mechanical or [],
            "meta": {},
        },
        "judge_scores": {},
    }


_HELD_REASON = "fabrication: tier1_entity=2 arxiv=1 — deterministic gate hold"


def _held_edition_stub(edition=104, *, with_evals=True, with_shadow=True):
    """A held primary (+ optional shadow) edition, optionally with eval telemetry."""
    newsletters = [_primary_row(edition, held=True, row_id="prim-104", reason=_HELD_REASON)]
    if with_shadow:
        newsletters.append(_shadow_row(edition, row_id="shadow-104"))
    evals = []
    if with_evals:
        evals = [_det_row(edition, fabrication=[
            {"kind": "tier1_entity", "value": "Gemini", "version": "technical"},
        ])]
    return StubSupabase(tables={"newsletters": newsletters, "edition_evals": evals})


# ===========================================================================
# T-UNH-01 owner gate — refusal BEFORE any read, any command form
# ===========================================================================
def test_non_owner_refused_and_no_read():
    for tier in ("free", "subscriber"):
        for cmd in ("/newsletter_unhold 104", "/newsletter_unhold 104 confirm"):
            stub = _held_edition_stub()
            out = gb.handle_newsletter_unhold(cmd, access_tier=tier, supabase_client=stub)
            assert "owner" in out.lower(), f"tier={tier} cmd={cmd}: no owner refusal"
            assert stub.captured == [], (
                f"tier={tier} cmd={cmd}: non-owner /newsletter_unhold must NOT touch the DB"
            )


# ===========================================================================
# Two-step confirm — the bare form previews and mutates NOTHING
# ===========================================================================
def test_bare_command_previews_without_mutating():
    stub = _held_edition_stub(104)
    out = gb.handle_newsletter_unhold(
        "/newsletter_unhold 104", access_tier="owner", supabase_client=stub
    )
    assert "tier1_entity" in out, "preview must surface the hold reason"
    assert "prim-104" in out, "preview must name the target row id"
    assert "confirm" in out.lower(), "preview must instruct the confirm step"
    assert not any(c[0] == "update" for c in stub.captured), "bare form must NOT mutate"
    # The primary row is untouched.
    prim = stub.tables["newsletters"][0]
    assert prim["do_not_publish"] is True and prim["status"] == "held"


def test_preview_includes_eval_flag_summary():
    # With edition_evals rows: the labels/counts-only trend line renders (fab=... counts).
    stub = _held_edition_stub(104, with_evals=True)
    out = gb.handle_newsletter_unhold(
        "/newsletter_unhold 104", access_tier="owner", supabase_client=stub
    )
    assert "fab=" in out, "preview must carry the labels/counts eval trend summary"

    # Without any edition_evals rows: the explicit no-eval-rows message.
    stub2 = _held_edition_stub(104, with_evals=False)
    out2 = gb.handle_newsletter_unhold(
        "/newsletter_unhold 104", access_tier="owner", supabase_client=stub2
    )
    assert "no eval rows recorded" in out2.lower()


# ===========================================================================
# Confirm — ONE targeted update on the PRIMARY row only; shadow untouched
# ===========================================================================
def test_confirm_releases_primary_row_only():
    stub = _held_edition_stub(104)
    out = gb.handle_newsletter_unhold(
        "/newsletter_unhold 104 confirm", access_tier="owner", supabase_client=stub
    )
    updates = [c for c in stub.captured if c[0] == "update"]
    assert len(updates) == 1, f"expected exactly ONE update, got {updates}"
    assert updates[0] == (
        "update",
        "newsletters",
        {"do_not_publish": False, "status": "draft", "do_not_publish_reason": None},
    )
    # Targeted by ROW ID, never by edition number.
    assert ("eq", "id", "prim-104") in stub.captured
    assert not any(c == ("eq", "edition_number", 104) and stub.captured[i - 1][0] == "update"
                   for i, c in enumerate(stub.captured)), "update must never target by edition"
    # Post-state: primary released, shadow UNCHANGED.
    prim = next(r for r in stub.tables["newsletters"] if r["id"] == "prim-104")
    shadow = next(r for r in stub.tables["newsletters"] if r["id"] == "shadow-104")
    assert prim["do_not_publish"] is False
    assert prim["status"] == "draft"
    assert prim["do_not_publish_reason"] is None
    assert shadow["do_not_publish"] is True
    assert shadow["status"] == "held"
    assert shadow["do_not_publish_reason"] == "block_v1 A/B comparison shadow"
    # Reply confirms the release, naming edition + row id.
    assert "104" in out and "prim-104" in out
    assert "released" in out.lower()


# ===========================================================================
# Shadow exclusion — held-by-design rows are NEVER releasable
# ===========================================================================
def test_shadow_only_edition_refused():
    # Sub-case A: a not-held primary exists; the ONLY held row is the shadow.
    stub = StubSupabase(tables={
        "newsletters": [_primary_row(105, held=False, row_id="prim-105"), _shadow_row(105, "shadow-105")],
        "edition_evals": [],
    })
    for cmd in ("/newsletter_unhold 105", "/newsletter_unhold 105 confirm"):
        out = gb.handle_newsletter_unhold(cmd, access_tier="owner", supabase_client=stub)
        assert "by design" in out.lower() and "not releasable" in out.lower(), out
        assert not any(c[0] == "update" for c in stub.captured), f"{cmd} must never mutate"

    # Sub-case B: NO primary at all — only the held shadow exists.
    stub2 = StubSupabase(tables={
        "newsletters": [_shadow_row(106, "shadow-106")],
        "edition_evals": [],
    })
    for cmd in ("/newsletter_unhold 106", "/newsletter_unhold 106 confirm"):
        out = gb.handle_newsletter_unhold(cmd, access_tier="owner", supabase_client=stub2)
        assert "by design" in out.lower() and "not releasable" in out.lower(), out
        assert not any(c[0] == "update" for c in stub2.captured)
    # The shadow row's fields are unchanged in both stubs.
    assert stub.tables["newsletters"][1]["do_not_publish"] is True
    assert stub2.tables["newsletters"][0]["do_not_publish"] is True


def test_shadow_detection_defensive_to_string_snapshot():
    """data_snapshot arriving as a JSON STRING must not raise — the title-prefix
    check is the fallback (belt-and-suspenders)."""
    row_str_snap_shadow_title = {
        "id": "s1", "title": "[BLOCK PIPELINE A/B] Edition 9", "data_snapshot": '{"ab_comparison": true}',
    }
    row_str_snap_plain_title = {
        "id": "s2", "title": "AgentPulse Edition 9", "data_snapshot": '{"foo": 1}',
    }
    row_none_snap = {"id": "s3", "title": "AgentPulse Edition 9", "data_snapshot": None}
    assert gb._unhold_is_shadow(row_str_snap_shadow_title) is True
    assert gb._unhold_is_shadow(row_str_snap_plain_title) is False
    assert gb._unhold_is_shadow(row_none_snap) is False
    assert gb._unhold_is_shadow({"id": "s4", "data_snapshot": {"ab_comparison": True}}) is True


# ===========================================================================
# Distinct failure paths — never a silent no-op
# ===========================================================================
def test_edition_not_found():
    stub = StubSupabase(tables={"newsletters": [], "edition_evals": []})
    out = gb.handle_newsletter_unhold(
        "/newsletter_unhold 999", access_tier="owner", supabase_client=stub
    )
    assert "999" in out and "not found" in out.lower()
    assert not any(c[0] == "update" for c in stub.captured)


def test_primary_not_held():
    stub = StubSupabase(tables={
        "newsletters": [_primary_row(107, held=False, row_id="prim-107", status="draft")],
        "edition_evals": [],
    })
    out = gb.handle_newsletter_unhold(
        "/newsletter_unhold 107 confirm", access_tier="owner", supabase_client=stub
    )
    assert "not held" in out.lower()
    assert "draft" in out, "not-held message must report the primary's current status"
    assert not any(c[0] == "update" for c in stub.captured)


def test_supabase_error_returns_message():
    stub = _held_edition_stub(104)
    stub._raise = True
    out = gb.handle_newsletter_unhold(
        "/newsletter_unhold 104 confirm", access_tier="owner", supabase_client=stub
    )
    assert "unhold failed" in out.lower()
    assert out.strip(), "error path must never return an empty reply"


# ===========================================================================
# Multiple held primaries (regenerated editions) — newest by created_at wins
# ===========================================================================
def test_multiple_held_primaries_targets_newest():
    older = _primary_row(108, held=True, row_id="prim-old",
                         reason="old hold", created_at="2026-06-20T00:00:00Z")
    newer = _primary_row(108, held=True, row_id="prim-new",
                         reason="new hold", created_at="2026-07-01T12:00:00Z")
    stub = StubSupabase(tables={
        "newsletters": [older, newer, _shadow_row(108, "shadow-108")],
        "edition_evals": [],
    })
    out = gb.handle_newsletter_unhold(
        "/newsletter_unhold 108 confirm", access_tier="owner", supabase_client=stub
    )
    assert ("eq", "id", "prim-new") in stub.captured
    assert ("eq", "id", "prim-old") not in stub.captured
    assert "2" in out and "prim-new" in out, "reply must note the held-row count + target id"
    # Only the newest primary is released.
    assert newer["do_not_publish"] is False and newer["status"] == "draft"
    assert older["do_not_publish"] is True and older["status"] == "held"


# ===========================================================================
# Usage — missing/non-numeric arg
# ===========================================================================
def test_usage_on_missing_or_bad_arg():
    for cmd in ("/newsletter_unhold", "/newsletter_unhold abc"):
        stub = _held_edition_stub(104)
        out = gb.handle_newsletter_unhold(cmd, access_tier="owner", supabase_client=stub)
        assert "/newsletter_unhold <edition#> [confirm]" in out, f"{cmd}: no usage message"
        assert not any(c[0] == "update" for c in stub.captured)


# ===========================================================================
# EVAL-03 structural — the stub (and thus the read/update path) has no in-list filter
# ===========================================================================
def test_stub_query_has_no_in_list_method():
    q = _StubQuery("newsletters", [], [])
    assert not hasattr(q, "in_"), "the read/update path must never rely on .in_() (EVAL-03)"


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
