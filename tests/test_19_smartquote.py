#!/usr/bin/env python3
"""
QUOTE-02 regression test — Phase 19 (smart-quote / apostrophe corruption fix).

Feeds the ROADMAP-mandated inputs (`it's`, `the agent's wallet`, plus the four
named tokens) through the REAL fixed write-path function
`newsletter_poller.normalize_apostrophe_corruption` and asserts:

  * the output preserves a real apostrophe (U+2019 chr(8217) OR U+0027 chr(39))
    at each apostrophe position, AND
  * the output contains ZERO straight double-quote (U+0022 chr(34)) standing in
    for an apostrophe (no `"` flanked by word characters), AND
  * a legitimate quotation (`He said "ship it"`) keeps its real double-quotes
    (the fix is NOT a blanket `"`->`'` collapse — threat T-19-03), AND
  * the guard is fail-loud on unexpected (non-str) input.

This test imports the REAL production function via the conftest-preloaded
`newsletter_poller` module — it does NOT reimplement the transform (a copy could
pass while production regresses). Plan 02's backfill must reuse this same
function (see 19-DIAGNOSIS.md).
"""
import re
import sys
from pathlib import Path

import pytest

# conftest.py preloads `newsletter_poller` into sys.modules with the correct
# `schemas` registered. Mirror test_3c_newsletters.py's sys.path wiring as a
# belt-and-suspenders fallback so the real module is importable either way.
NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
if str(NL_DIR) not in sys.path:
    sys.path.insert(0, str(NL_DIR))

import newsletter_poller as nl  # noqa: E402  — the REAL fixed module

# The canonical fixed write-path function (named in 19-DIAGNOSIS.md).
fix = nl.normalize_apostrophe_corruption

APOSTROPHES = (chr(0x2019), chr(0x0027))  # U+2019 curly, U+0027 straight
# A straight double-quote (U+0022) standing in for an apostrophe == flanked by
# word characters. This is the corruption signature that must be absent.
_WORD_FLANKED_DQ = re.compile(r'(?<=[A-Za-z0-9])"(?=[A-Za-z0-9])')


def _has_real_apostrophe(s: str) -> bool:
    return any(a in s for a in APOSTROPHES)


def _stray_apostrophe_quote_count(s: str) -> int:
    return len(_WORD_FLANKED_DQ.findall(s))


# ──────────────────────────────────────────────────────────────────────────────
# QUOTE-02 core inputs: `it's` and `the agent's wallet`
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", ["it's", "the agent's wallet"])
def test_quote02_core_clean_inputs_preserve_apostrophe(text):
    """Clean apostrophe inputs round-trip with a real apostrophe and zero stray DQ."""
    out = fix(text)
    assert _has_real_apostrophe(out), f"no real apostrophe in {out!r}"
    assert _stray_apostrophe_quote_count(out) == 0, f"stray apostrophe-quote in {out!r}"


@pytest.mark.parametrize("text,corrupt", [
    ('it"s', "it's"),
    ('the agent"s wallet', "the agent's wallet"),
])
def test_quote02_core_corrupt_inputs_repaired(text, corrupt):
    """If the corruption signature is present, it is repaired to a real apostrophe."""
    out = fix(text)
    assert _has_real_apostrophe(out), f"no real apostrophe in {out!r}"
    assert _stray_apostrophe_quote_count(out) == 0, f"stray apostrophe-quote remains in {out!r}"
    assert out == corrupt, f"expected {corrupt!r}, got {out!r}"


# ──────────────────────────────────────────────────────────────────────────────
# The four ROADMAP example tokens — each round-trips with a real apostrophe
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("token", ["Cash App's", "It's", "world's", "agent's"])
def test_roadmap_tokens_clean_roundtrip(token):
    """The named ROADMAP tokens (clean U+0027) survive untouched with an apostrophe."""
    body = f"Yesterday {token} story led the edition."
    out = fix(body)
    assert _has_real_apostrophe(out), f"no real apostrophe in {out!r}"
    assert _stray_apostrophe_quote_count(out) == 0
    assert token in out, f"token {token!r} not preserved in {out!r}"


@pytest.mark.parametrize("corrupt,clean", [
    ('Cash App"s', "Cash App's"),
    ('It"s', "It's"),
    ('world"s', "world's"),
    ('agent"s', "agent's"),
])
def test_roadmap_tokens_corruption_repaired(corrupt, clean):
    """The corrupt form of each ROADMAP token is repaired to a real apostrophe."""
    out = fix(f"Then {corrupt} angle changed.")
    assert clean in out, f"expected {clean!r} in {out!r}"
    assert _stray_apostrophe_quote_count(out) == 0


# ──────────────────────────────────────────────────────────────────────────────
# Edge case: genuine double-quotes MUST survive (no blanket "->' collapse)
# ──────────────────────────────────────────────────────────────────────────────

def test_genuine_double_quotes_preserved():
    """A real quotation keeps its real double-quotes (threat T-19-03)."""
    body = 'He said "ship it" today.'
    out = fix(body)
    assert out == body, f"genuine quotes mutated: {out!r}"
    assert out.count('"') == 2, f"expected 2 double-quotes, got {out.count(chr(34))}"


def test_genuine_quotes_and_apostrophe_together():
    """A body mixing a real quote and an apostrophe keeps both intact."""
    body = 'It\'s what they meant by "shipping fast" this week.'
    out = fix(body)
    assert _has_real_apostrophe(out)
    assert out.count('"') == 2
    assert _stray_apostrophe_quote_count(out) == 0
    assert out == body


# ──────────────────────────────────────────────────────────────────────────────
# Fail-loud + no-op safety
# ──────────────────────────────────────────────────────────────────────────────

def test_fail_loud_on_non_str():
    """Non-str input raises (never silently coerced into storage)."""
    with pytest.raises(TypeError):
        fix(123)


def test_none_and_empty_passthrough():
    """None and empty string pass through unchanged (legitimate empty fields)."""
    assert fix(None) is None
    assert fix("") == ""


def test_clean_long_body_is_noop():
    """A realistic clean body with many apostrophes is returned byte-identical."""
    body = (
        "## Read This, Skip the Rest\n\n"
        "An agent's authority shouldn't outlive its task. There's no standard "
        "for it yet, and that's the gap Cash App's rollout exposes. It's the "
        "early innings of the world's settlement layer.\n"
    )
    out = fix(body)
    assert out == body
    assert _stray_apostrophe_quote_count(out) == 0
