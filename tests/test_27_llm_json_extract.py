#!/usr/bin/env python3
"""Regression suite for the robust LLM JSON extraction added to fix the
single-pass-writer-empty bug (debug 2026-06-24).

Root cause: the writer did `text = response.content[0].text.strip()`, stripped
```fences ONLY when text.startswith("```"), then json.loads(text). When
claude-sonnet-4-6 framed the large writer output as anything other than
bare-JSON-or-leading-fence (e.g. a prose preamble before the fence), json.loads
failed at "char 0" — misdiagnosed as "empty content".

These tests:
  1. Prove the OLD brittle extraction FAILS on the real failing framings
     (so we know we are testing the actual failure mode, not a strawman).
  2. Lock the NEW parse_llm_json contract: recover JSON across framings and
     FAIL LOUD (raise) on genuinely unparseable output — never silent-empty.
  3. Lock response_text: join all text blocks, ignore non-text blocks.

Imports the REAL production helpers via the conftest-preloaded newsletter_poller
module (the test_19/test_26 rule: a reimplemented copy could pass while prod
regresses).
"""
import json
import re
import sys
from pathlib import Path

import pytest

NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
if str(NL_DIR) not in sys.path:
    sys.path.insert(0, str(NL_DIR))

import newsletter_poller as nl  # noqa: E402 — the REAL production module


# ── minimal fakes mirroring the anthropic SDK response shape ──────────────────
class _Block:
    def __init__(self, type_, text=None, **extra):
        self.type = type_
        if text is not None:
            self.text = text
        for k, v in extra.items():
            setattr(self, k, v)


class _Resp:
    def __init__(self, blocks):
        self.content = blocks


def _text_resp(s):
    return _Resp([_Block("text", text=s)])


# A realistic newsletter-ish JSON payload.
_PAYLOAD = {
    "edition": 33,
    "title": "The Attack Surface Is the Product",
    "primary_theme": "agent security infrastructure gap",
    # a value containing braces + quotes, to stress the balanced-brace scanner
    "content_markdown": 'Use `{"role": "user"}` carefully. Nested {braces} inside "strings".',
}
_JSON = json.dumps(_PAYLOAD, indent=2)


# The OLD brittle extraction, reproduced verbatim so we can prove it failed.
def _old_extract(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


# Framings the model can emit. (label, raw_text, old_should_fail)
_RECOVERABLE = [
    ("bare", _JSON, False),
    ("fenced_json", f"```json\n{_JSON}\n```", False),
    ("fenced_plain", f"```\n{_JSON}\n```", False),
    # ── the real failure modes (OLD logic fails) ──
    ("preamble_then_fence", f"Here is the edition:\n\n```json\n{_JSON}\n```", True),
    ("preamble_then_bare", f"Sure! Here's the JSON:\n\n{_JSON}", True),
    ("uppercase_fence", f"```JSON\n{_JSON}\n```", True),
    ("trailing_prose_after_json", f"{_JSON}\n\nThat's the edition!", True),
    ("fenced_with_trailing_note", f"```json\n{_JSON}\n```\n\nLet me know if you want changes.", True),
]


@pytest.mark.parametrize("label,raw,old_should_fail", _RECOVERABLE)
def test_new_extractor_recovers_all_framings(label, raw, old_should_fail):
    """parse_llm_json recovers the JSON object for every plausible framing."""
    result = nl.parse_llm_json(raw, context=f"test:{label}")
    assert result == _PAYLOAD, f"{label}: payload mismatch"


@pytest.mark.parametrize("label,raw,old_should_fail", _RECOVERABLE)
def test_old_logic_failure_mode_is_real(label, raw, old_should_fail):
    """Confirm the framings we claim were broken DID break the old extraction
    (and the ones we claim worked DID work) — so the fix targets the real bug."""
    if old_should_fail:
        with pytest.raises(json.JSONDecodeError):
            _old_extract(raw)
    else:
        assert _old_extract(raw) == _PAYLOAD


def test_char_zero_error_signature_matches_live_bug():
    """The live failure was 'Expecting value: line 1 column 1 (char 0)'. Prove a
    prose-preamble framing produced exactly that under the OLD logic."""
    raw = f"Here is the edition:\n\n```json\n{_JSON}\n```"
    with pytest.raises(json.JSONDecodeError) as ei:
        _old_extract(raw)
    assert ei.value.pos == 0
    assert "char 0" in str(ei.value)


def test_fail_loud_on_pure_prose_no_json():
    """Genuinely unparseable output (no JSON object) must FAIL LOUD — raise, not
    return empty/None — so it can never become a silent empty edition."""
    raw = "## Read This, Skip the Rest\n\nThe security reckoning arrives...\n(no JSON here)"
    with pytest.raises(json.JSONDecodeError):
        nl.parse_llm_json(raw, context="test:pure_prose")


def test_fail_loud_on_empty():
    with pytest.raises(json.JSONDecodeError):
        nl.parse_llm_json("", context="test:empty")
    with pytest.raises(json.JSONDecodeError):
        nl.parse_llm_json("   \n  ", context="test:whitespace")


def test_response_text_single_block():
    assert nl.response_text(_text_resp(_JSON)) == _JSON


def test_response_text_joins_and_ignores_nontext():
    resp = _Resp([
        _Block("thinking", thinking="...reasoning..."),  # no .text — must be skipped
        _Block("text", text='{"a":'),
        _Block("text", text=' 1}'),
    ])
    joined = nl.response_text(resp)
    assert joined == '{"a": 1}'
    assert nl.parse_llm_json(joined, context="test:multiblock") == {"a": 1}


def test_balanced_object_respects_strings():
    """Braces inside string values must not terminate the object early."""
    raw = 'noise {"k": "a } b { c", "n": {"x": 1}} trailing'
    obj = nl._first_balanced_object(raw)
    assert json.loads(obj) == {"k": "a } b { c", "n": {"x": 1}}
