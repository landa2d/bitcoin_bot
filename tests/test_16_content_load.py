"""Phase 16 — negative-path test for the economy_map body loader (D-06).

Proves the loader's pre-flight validate-all gate (D-04/D-05) fires on a
deliberately-broken fixture and LANDS NOTHING — zero INSERT POSTs reach the DB.
The "lands nothing" test sets DUMMY SUPABASE_URL/SUPABASE_KEY first so the
env-gate PASSES and `validate_all` is the gate that actually halts the load
(otherwise the empty-POST assertion would pass for the wrong reason — the
env-gate short-circuit, not the validation gate).

All DB I/O is monkeypatched / never reached — the harness requires NO live DB.

Run standalone (no pytest required):  python3 tests/test_16_content_load.py
"""
import os
import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Stub optional third-party libs at module level so the loader imports in a bare
# environment (mirrors test_07_synthesis.py:23-52). The loader only needs yaml +
# httpx, but we stub the usual suspects defensively in case the import chain
# grows. yaml/httpx are real deps and must NOT be stubbed.
# ---------------------------------------------------------------------------
for _name in ("schedule", "tweepy", "resend"):
    try:
        __import__(_name)
    except Exception:
        sys.modules[_name] = types.ModuleType(_name)

sys.path.insert(0, str(_ROOT / "scripts"))
import load_economy_map_content as loader  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture builders — small dicts mirroring the parsed-record shape (the input to
# validate_all), plus a tmp-dir writer for the end-to-end main() test.
# ---------------------------------------------------------------------------
def _good_block(slug="identity-trust", tier="substrate", order=1, maturity="emerging"):
    return {
        "path": f"<{slug}>",
        "slug": slug,
        "type": "block",
        "tier": tier,
        "title": "Title",
        "subtitle": "Subtitle",
        "order": order,
        "raw_maturity": maturity,
        "body_md": "# Heading\n\nReal body content here.\n",
    }


def _good_hub():
    return {
        "path": "<agent-economy>",
        "slug": "agent-economy",
        "type": "hub",
        "tier": None,
        "title": "The Agent Economy",
        "subtitle": "Capability is solved.",
        "order": 0,
        "raw_maturity": None,  # hub has no maturity (D-05 special-case)
        "body_md": "# The Agent Economy\n\nHub body.\n",
    }


def _valid_batch():
    """A small but fully-valid batch (hub + one block) — the positive control."""
    return [_good_hub(), _good_block()]


# ---------------------------------------------------------------------------
# Test A — validate_all halts loud on an empty body_md.
# ---------------------------------------------------------------------------
def test_load_halts_on_empty_body():
    batch = _valid_batch()
    broken = _good_block(slug="memory-context", order=2)
    broken["body_md"] = "   "  # whitespace-only — DB NOT NULL does NOT catch this
    batch.append(broken)

    raised = False
    try:
        loader.validate_all(batch)
    except (ValueError, RuntimeError, SystemExit):
        raised = True
    assert raised, "must halt loud on an empty body_md"


# ---------------------------------------------------------------------------
# Test B — validate_all halts loud on an out-of-enum (post-remap) maturity.
# ---------------------------------------------------------------------------
def test_load_halts_on_invalid_maturity():
    batch = _valid_batch()
    broken = _good_block(slug="payments-settlement", order=3, maturity="legendary")
    batch.append(broken)

    raised = False
    try:
        loader.validate_all(batch)
    except (ValueError, RuntimeError, SystemExit):
        raised = True
    assert raised, "must halt loud on an out-of-enum post-remap maturity"


# ---------------------------------------------------------------------------
# Test C — the loader lands NOTHING because the VALIDATION gate fired.
#
# CRITICAL: dummy env is set FIRST so the env-gate PASSES — then the empty
# captured-POST list proves the VALIDATION gate (not the env-gate short-circuit)
# stopped the load (D-04/D-06).
# ---------------------------------------------------------------------------
def test_load_lands_nothing_when_gate_fires(tmp_path, monkeypatch):
    # Write a broken fixture dir the pinned [0-9][0-9]-*.md glob will pick up:
    # a valid hub + an empty-body block. validate_all MUST reject the batch.
    (tmp_path / "00-hub.md").write_text(
        "---\nslug: agent-economy\ntype: hub\ntitle: The Agent Economy\n"
        "subtitle: Cap.\norder: 0\n---\n\n# The Agent Economy\n\nHub body.\n",
        encoding="utf-8",
    )
    (tmp_path / "01-broken.md").write_text(
        "---\nslug: identity-trust\ntype: block\ntier: substrate\n"
        "title: Identity\nsubtitle: Sub.\norder: 1\nmaturity: building\n---\n\n   \n",
        encoding="utf-8",
    )

    # dummy env so the env-gate PASSES and validate_all is the gate that fires.
    monkeypatch.setenv("SUPABASE_URL", "http://fake")
    monkeypatch.setenv("SUPABASE_KEY", "fake")
    # loader read its env at import — push the dummy values onto the module too.
    monkeypatch.setattr(loader, "SUPABASE_URL", "http://fake", raising=False)
    monkeypatch.setattr(loader, "SUPABASE_KEY", "fake", raising=False)
    # point DOCS_DIR at the broken fixture dir (the count==8 assert is gated on
    # the DEFAULT dir, so a fixture dir is exempt — validate_all is the gate).
    monkeypatch.setattr(loader, "DOCS_DIR", str(tmp_path), raising=False)

    captured = {"posts": []}
    monkey_post = loader.httpx.post
    loader.httpx.post = lambda url, **kw: captured["posts"].append(url)
    raised = False
    try:
        try:
            loader.main()
        except (SystemExit, ValueError, RuntimeError):
            raised = True
    finally:
        loader.httpx.post = monkey_post

    assert raised, "the validation gate must fire on the broken fixture"
    assert captured["posts"] == [], (
        "no INSERT POSTs when any input fails the gate (D-04/D-06) — "
        "the load lands nothing BECAUSE the validation gate halted it"
    )


# ---------------------------------------------------------------------------
# Test D — positive control: a fully-valid batch passes validate_all unraised
# (proves the gate is not always-raise).
# ---------------------------------------------------------------------------
def test_valid_batch_passes_gate():
    good_batch = _valid_batch()
    # Should return normally (None) without raising.
    result = loader.validate_all(good_batch)
    assert result is None, "validate_all on a valid batch must not raise"


if __name__ == "__main__":
    test_load_halts_on_empty_body()
    test_load_halts_on_invalid_maturity()
    test_valid_batch_passes_gate()
    print("validate_all gate tests passed (run via pytest for the tmp_path test)")
