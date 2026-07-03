#!/usr/bin/env python3
"""
Golden regression for the `eval-tier1-entity-fp` fix (debug session
.planning/debug/resolved/eval-tier1-entity-fp.md).

Freezes the FIRST real single-pass production draft ever run through
`run_deterministic_gate` — newsletter edition #104 (row 666a8dea) — together with its
`data_snapshot` fact base and the prior published edition (#33). Before the fix the gate
emitted 31 fabrication flags (verdict `held_fabrication`); 27 of them were extractor noise:

  - sentence/clause/line-initial common words capitalized only by grammar
    ("According", "Auto", "Broken", "Date", "DevOps", "Engineering", "Fallback", "Nobody",
     "Note", "Platform", "Researchers", "Timeline", "Zero"),
  - inter-quote narrative fragments captured by a straight-quote parity bug
    ("It's the difference between blaming the driver ...", "became standard for cloud
      services ...", "is now a standard item in every vendor evaluation ..."),
  - rhetorical / scare-quote terms with no groundable claim
    ("hedge ratio", "what happens if this model goes offline?"),
  - a boundary-initial `_MULTI_CAP` merge ("What Zuckerberg").

The fix (verification.py) is boundary-aware proper-noun extraction on a newline-preserving
buffer + positional quote pairing + a verifiable-token requirement for quotes. This test
locks the POST-FIX contract with EXACT expected flags:

  - the noise above is GONE, AND
  - the genuine signal SURVIVES: the 2 arXiv-membership misses (real papers absent from the
    fact base), the 6 genuinely fact-base-absent named entities that appear mid-sentence in
    the flagged body (Amazon / Amazon Web Services / Azure / Microsoft / Microsoft Azure /
    Mythos, plus Gemini / Llama in the technical body), and the cross-edition
    `duplicated_stat` mechanical flag.

Imports the REAL `deterministic_gate` (which imports the REAL `verification` engine) — a
re-implementation could pass while production regresses. NO network: `http_client=None`.
"""
import json
import sys
from pathlib import Path

import pytest

NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
if str(NL_DIR) not in sys.path:
    sys.path.insert(0, str(NL_DIR))

import deterministic_gate as gate  # noqa: E402 — the REAL production module

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "edition_104_gate_golden.json"


@pytest.fixture(scope="module")
def golden():
    return json.loads(_FIXTURE.read_text())


@pytest.fixture(scope="module")
def flags(golden):
    # The exact sequencer call: single-pass draft, its data_snapshot fact base, the prior
    # published edition, no network layer.
    return gate.run_deterministic_gate(
        golden["draft"], golden["fact_base"], golden["prior_edition"], http_client=None
    )


def _tier1_values(flags):
    return [f["value"] for f in flags["fabrication"] if f["kind"] == "tier1_entity"]


# ── The exact post-fix contract ──────────────────────────────────────────────────────────────

# The 6 + 2 genuinely fact-base-absent entities that appear mid-sentence in the flagged body.
_EXPECTED_TIER1 = {
    "Gemini": "technical",
    "Llama": "technical",
    "Amazon": "impact",
    "Amazon Web Services": "impact",
    "Azure": "impact",
    "Microsoft": "impact",
    "Microsoft Azure": "impact",
    "Mythos": "impact",
}

# Every noise value that the pre-fix extractor emitted and the fix must eliminate.
_ELIMINATED_TIER1 = {
    "According", "Auto", "Broken", "Date", "DevOps", "Engineering", "Fallback", "Nobody",
    "Note", "Platform", "Researchers", "Timeline", "Zero", "hedge ratio",
    "what happens if this model goes offline?",
}

# Substrings of the three inter-quote narrative fragments the parity bug used to capture.
_FRAGMENT_MARKERS = [
    "It's the difference between blaming",
    "became standard for cloud services",
    "is now a standard item in every vendor evaluation",
    "the same way",
]


def test_total_flag_counts_locked(flags):
    # 31 → 11 fabrication; mechanical carries the reading-mode leak + the cross-edition stat.
    assert len(flags["fabrication"]) == 11
    assert len(flags["mechanical"]) == 2
    assert flags["unverified"] == []
    assert flags["meta"]["fact_base_path"] == "input_data"
    assert flags["meta"]["tier1_count"] == {"technical": 2, "impact": 6}


def test_tier1_entities_are_exactly_the_genuine_set(flags):
    got = {(f["value"], f["version"]) for f in flags["fabrication"] if f["kind"] == "tier1_entity"}
    assert got == {(v, ver) for v, ver in _EXPECTED_TIER1.items()}


def test_no_sentence_initial_or_rhetorical_noise(flags):
    values = _tier1_values(flags)
    leaked = _ELIMINATED_TIER1.intersection(values)
    assert not leaked, f"sentence-initial / rhetorical noise leaked back in: {sorted(leaked)}"


def test_no_inter_quote_sentence_fragments(flags):
    # No flag value (any kind) may contain a captured inter-quote narrative fragment.
    all_values = [str(f.get("value") or f.get("entity") or "") for f in flags["fabrication"]]
    for marker in _FRAGMENT_MARKERS:
        assert not any(marker in v for v in all_values), f"fragment leaked: {marker!r}"


def test_arxiv_membership_flags_survive(flags):
    # The two genuine arXiv misses (real papers cited in the draft, absent from the fact base).
    arxiv = {f["id"] for f in flags["fabrication"] if f["kind"] == "arxiv"}
    assert arxiv == {"2606.06324", "2604.19784"}
    assert all(f["version"] == "technical"
               for f in flags["fabrication"] if f["kind"] == "arxiv")


def test_entity_merge_noise_dropped_plausible_kept(flags):
    merges = {f["entity"] for f in flags["fabrication"] if f["kind"] == "entity_merge"}
    # "What Zuckerberg" (a boundary-initial multi-cap) is eliminated by the fix ...
    assert "What Zuckerberg" not in merges
    # ... the plausible "Google Cloud" cross-source merge is preserved.
    assert merges == {"Google Cloud"}


def test_duplicated_stat_mechanical_survives(flags):
    dup = [f for f in flags["mechanical"] if f["kind"] == "duplicated_stat"]
    assert len(dup) == 1
    assert dup[0]["stat"] == "5 mentions"
    assert dup[0]["version"] == "technical"
    assert dup[0]["prior_edition"] == 33


def test_version_labels_match_the_body_each_value_appears_in(golden, flags):
    # The "version-attribution puzzle" resolution: every tier1 value's version label matches the
    # single body it literally appears in (case-insensitive). No cross-version mislabeling.
    tech = golden["draft"]["content_markdown"].lower()
    impact = golden["draft"]["content_markdown_impact"].lower()
    for f in flags["fabrication"]:
        if f["kind"] != "tier1_entity":
            continue
        body = tech if f["version"] == "technical" else impact
        assert f["value"].lower() in body, (
            f"{f['value']!r} labeled {f['version']} but absent from that body"
        )
