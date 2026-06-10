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
import logging
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
# WR-02: the same signature with a CURLY double-quote (U+201C/U+201D) — the more
# likely typographer/smart-quote recurrence shape. Must also be absent post-fix.
_WORD_FLANKED_DQ_ANY = re.compile(r'(?<=[A-Za-z0-9])["“”](?=[A-Za-z0-9])')


def _has_real_apostrophe(s: str) -> bool:
    return any(a in s for a in APOSTROPHES)


def _stray_apostrophe_quote_count(s: str) -> int:
    return len(_WORD_FLANKED_DQ.findall(s))


def _stray_any_dq_count(s: str) -> int:
    """Word-flanked double-quote of ANY shape (straight U+0022 or curly U+201C/D)."""
    return len(_WORD_FLANKED_DQ_ANY.findall(s))


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
# REAL corruption (Phase 19 debug): a DOUBLED apostrophe ('' , two U+0027) standing
# where a single apostrophe belongs. Two adjacent apostrophes render as a VISUAL
# double-quote in the serif body face (it''s looks like it"s) — this is what the
# operator actually saw on the live site, NOT a literal double-quote character.
# Confirmed: 103 runs across published editions 26/29/30, all word-flanked.
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("corrupt,clean", [
    ("it''s", "it's"),
    ("the agent''s wallet", "the agent's wallet"),
    ("Cash App''s rollout", "Cash App's rollout"),
    ("bottleneck isn''t model perf", "bottleneck isn't model perf"),
    ("the world''s second-largest", "the world's second-largest"),
    ("we''ve been pointing", "we've been pointing"),
])
def test_doubled_apostrophe_collapsed(corrupt, clean):
    """A word-flanked doubled apostrophe ('') is collapsed to a single apostrophe."""
    out = fix(corrupt)
    assert out == clean, f"expected {clean!r}, got {out!r}"
    assert _has_real_apostrophe(out)
    # no run of 2+ apostrophes remains word-flanked
    assert not re.search(r"(?<=\w)'{2,}(?=\w)", out), f"doubled apostrophe remains in {out!r}"


def test_doubled_apostrophe_preserves_genuine_double_quotes():
    """Collapsing '' must NOT touch genuine double-quote quotations."""
    # Double-quoted Python literal so the inner '' is a real doubled apostrophe.
    body = "It''s what they call \"shipping fast\" — that''s the world''s view."
    out = fix(body)
    assert out.count('"') == 2, f"genuine double-quotes altered: {out!r}"
    assert "It's" in out and "that's" in out and "world's" in out
    assert not re.search(r"(?<=\w)'{2,}(?=\w)", out)


def test_genuine_empty_string_literal_untouched():
    """A space/punct-flanked '' (e.g. an empty-string literal) is NOT word-flanked → untouched."""
    body = "Set the value to '' when missing."
    out = fix(body)
    assert "''" in out, f"non-word-flanked '' should be preserved: {out!r}"


# ──────────────────────────────────────────────────────────────────────────────
# WR-02: curly double-quote (U+201C/U+201D) corruption is the more-likely
# typographer recurrence shape — it MUST be repaired, not silently passed through.
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("corrupt,clean", [
    ('Cash App“s', "Cash App's"),   # U+201C left curly
    ('Cash App”s', "Cash App's"),   # U+201D right curly
    ('It“s', "It's"),
    ('the agent”s wallet', "the agent's wallet"),
])
def test_quote02_curly_double_quote_corruption_repaired(corrupt, clean):
    """A mid-word CURLY double-quote standing in for an apostrophe is repaired."""
    out = fix(corrupt)
    assert _has_real_apostrophe(out), f"no real apostrophe in {out!r}"
    assert _stray_any_dq_count(out) == 0, f"stray (straight/curly) DQ remains in {out!r}"
    assert out == clean, f"expected {clean!r}, got {out!r}"


def test_genuine_curly_quotation_preserved():
    """A real curly quotation (flanked by spaces) keeps its curly quotes untouched."""
    body = "They called it “shipping fast” this week."
    out = fix(body)
    assert out == body, f"genuine curly quotes mutated: {out!r}"
    assert out.count("“") == 1 and out.count("”") == 1


# ──────────────────────────────────────────────────────────────────────────────
# Fail-loud + no-op safety
# ──────────────────────────────────────────────────────────────────────────────

def test_fail_loud_on_non_str():
    """Non-str input raises (never silently coerced into storage)."""
    with pytest.raises(TypeError):
        fix(123)


@pytest.mark.parametrize("corrupt", ['App"s', 'App“s', 'App”s', "App''s", "it''s"])
def test_repair_logs_loudly(corrupt, caplog):
    """Every repair (doubled-apostrophe, straight OR curly DQ) emits a loud error — never silent."""
    with caplog.at_level(logging.ERROR):
        out = fix(corrupt, field="content_telegram", edition=42)
    assert "'" in out or chr(0x2019) in out
    assert any("[QUOTE-FIX]" in r.message for r in caplog.records), \
        "a repair must surface a loud [QUOTE-FIX] error, not pass silently"


def test_clean_input_does_not_log(caplog):
    """A no-op on clean input emits no error (no false alarms)."""
    with caplog.at_level(logging.ERROR):
        fix("the agent's wallet", field="title", edition=42)
    assert not any("[QUOTE-FIX]" in r.message for r in caplog.records)


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
