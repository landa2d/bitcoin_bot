#!/usr/bin/env python3
"""
Phase 26 / Plan 02 — deterministic fixture suite for `load_edition_context`.

Locks the loader contract (return shape, operator-written filtering, the
>=40-word non-header/non-list paragraph filter, the CTX-03 empty-corpus path,
and the empty-operator-pool "not scored" path) BEFORE the live trigger spends
real generation budget. The hard-to-reproduce degrade paths (D-16) are exercised
against an in-memory Supabase stub — no live DB, no network, no credentials
(threat T-26-T1).

This test imports the REAL production function via the conftest-preloaded
`newsletter_poller` module — it does NOT reimplement the loader. A copy could
pass while production regresses (threat T-26-T2 / the test_19_smartquote rule).

Contract under test (as actually implemented in 26-01, newsletter_poller.py):
  load_edition_context(supabase, limit=3, exemplar_paras=8) -> dict with keys
    previous_editions, exemplars, exemplars_status ('scored'|'not_scored'), empty
  Three distinguishable states:
    - empty corpus            -> empty=True,  exemplars_status='not_scored' + WARNING
    - published, no operator  -> empty=False, exemplars_status='not_scored'
    - operator exemplars      -> empty=False, exemplars_status='scored'
"""
import logging
import sys
from pathlib import Path

import pytest

# conftest.py preloads `newsletter_poller` into sys.modules with the correct
# `schemas` registered. Mirror test_19_smartquote.py:32-39's sys.path wiring as
# a belt-and-suspenders fallback so the REAL module is importable either way.
NL_DIR = Path(__file__).resolve().parent.parent / "docker" / "newsletter"
if str(NL_DIR) not in sys.path:
    sys.path.insert(0, str(NL_DIR))

import newsletter_poller as nl  # noqa: E402  — the REAL production module

# ──────────────────────────────────────────────────────────────────────────────
# In-memory Supabase stub: exposes ONLY the fluent chain the loader uses
#   .table(...).select(...).eq(...).order(...).limit(...).execute()
# `.execute()` returns an object whose `.data` is a fixture list of edition dicts.
# Per-call responses can be queued (FIFO) so a multi-query loader stays
# reproducible; the loader issues a single read today, so one response suffices.
# No network, no credentials, never touches the live project (threat T-26-T1).
# ──────────────────────────────────────────────────────────────────────────────


class _StubResult:
    def __init__(self, data):
        self.data = data


class _StubQuery:
    def __init__(self, response_queue):
        self._q = response_queue

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        # FIFO-pop while more than one response remains; the final response
        # repeats so extra `.execute()`s never IndexError.
        data = self._q.pop(0) if len(self._q) > 1 else (self._q[0] if self._q else [])
        return _StubResult(data)


class StubSupabase:
    """Minimal Supabase double. Each positional arg is the `.data` list returned
    by one successive `.execute()` call (queued FIFO)."""

    def __init__(self, *responses):
        self._q = list(responses) if responses else [[]]

    def table(self, name):
        return _StubQuery(self._q)


def _edition(edition_number, *, title="Edition Title", title_impact=None,
             content_markdown="", content_markdown_impact="",
             data_snapshot=None, published_at="2026-06-01T00:00:00Z"):
    """Build one `newsletters` row dict carrying every column the loader reads."""
    return {
        "edition_number": edition_number,
        "title": title,
        "title_impact": title_impact,
        "content_markdown": content_markdown,
        "content_markdown_impact": content_markdown_impact,
        "data_snapshot": {} if data_snapshot is None else data_snapshot,
        "published_at": published_at,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Fixture prose. Each long paragraph clears the >=40-word exemplar bar (D-05).
# ──────────────────────────────────────────────────────────────────────────────

LONG_PARA_OP = (
    "The operator written voice here is deliberately long enough to clear the forty "
    "word threshold that the exemplar paragraph filter enforces, because a genuine "
    "voice exemplar must be substantial prose rather than a terse fragment or a "
    "passing single line aside that adds little durable signal to the downstream "
    "model and would only dilute the editorial fingerprint we are trying to teach."
)

LONG_PARA_NONOP = (
    "This block version one paragraph is also written to exceed the forty word minimum "
    "so the filtering test proves exclusion is driven by operator authorship and not "
    "merely by paragraph length, which means a long machine generated paragraph from a "
    "non operator edition must never appear among the returned voice exemplars under "
    "any circumstance whatsoever for the duration of this deterministic fixture run."
)

HEADER_LINE = "## Read This, Skip the Rest"
LIST_LINE = "- a bullet item that the exemplar filter must always skip outright"
SHORT_PARA = "A short aside that sits well under the forty word minimum."
# A long paragraph whose FIRST line is a header — excluded by the header regex
# DESPITE clearing the 40-word bar. Isolates D-05's non-header rule from length.
LONG_UNDER_HEADER = "### Section Heading\n" + LONG_PARA_NONOP

MIXED_MD = "\n\n".join([HEADER_LINE, LIST_LINE, SHORT_PARA, LONG_PARA_OP, LONG_UNDER_HEADER]) + "\n"

# Canonical operator data_snapshot per D-07: theme MUST come from `lead_theme`,
# never the always-null `primary_theme`.
_OP_SNAPSHOT = {"lead_theme": "test-theme", "operator_written": "true", "primary_theme": None}


def _scored_stub():
    """A single operator-written edition with a long exemplar paragraph."""
    return StubSupabase([_edition(31, content_markdown=LONG_PARA_OP, data_snapshot=dict(_OP_SNAPSHOT))])


def _no_operator_stub():
    """Published rows, but NONE operator-written (edition-29 / block_v1 analog)."""
    return StubSupabase([
        _edition(29, content_markdown=LONG_PARA_NONOP,
                 data_snapshot={"pipeline_version": "block_v1", "lead_theme": "machine-theme"}),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# Case 1 — return shape + theme sourcing (D-07) + weeks_ago presence (D-09)
# ══════════════════════════════════════════════════════════════════════════════


def test_return_shape_has_all_contract_keys():
    """The returned dict carries every contract key; each previous_editions entry
    carries {edition_number, title, primary_theme, opening_excerpt}."""
    ctx = nl.load_edition_context(_scored_stub())
    for key in ("previous_editions", "exemplars", "exemplars_status", "empty"):
        assert key in ctx, f"missing contract key {key!r} in {ctx!r}"
    assert ctx["previous_editions"], "expected a non-empty previous_editions list"
    entry = ctx["previous_editions"][0]
    for key in ("edition_number", "title", "primary_theme", "opening_excerpt"):
        assert key in entry, f"previous_editions entry missing {key!r}: {entry!r}"


def test_primary_theme_sourced_from_lead_theme():
    """D-07: primary_theme is sourced from data_snapshot.lead_theme, NOT the
    always-null data_snapshot.primary_theme and NOT title-derived."""
    ctx = nl.load_edition_context(_scored_stub())
    entry = ctx["previous_editions"][0]
    assert entry["primary_theme"] == "test-theme", \
        f"primary_theme must come from lead_theme, got {entry['primary_theme']!r}"


def test_primary_theme_none_when_no_lead_theme():
    """D-07: with no lead_theme, primary_theme is None — never derived/fabricated."""
    stub = StubSupabase([_edition(30, content_markdown=LONG_PARA_OP,
                                  data_snapshot={"operator_written": "true"})])
    ctx = nl.load_edition_context(stub)
    assert ctx["previous_editions"][0]["primary_theme"] is None


def test_weeks_ago_present_when_published_at_set():
    """weeks_ago is present when published_at is a real timestamp."""
    ctx = nl.load_edition_context(_scored_stub())
    assert "weeks_ago" in ctx["previous_editions"][0]


def test_weeks_ago_omitted_when_published_at_null():
    """D-09: weeks_ago is OMITTED entirely for a null-published_at row (the key
    is absent, not None — no fallback to the cadence-error-prone edition gap)."""
    stub = StubSupabase([_edition(30, content_markdown=LONG_PARA_OP,
                                  data_snapshot=dict(_OP_SNAPSHOT), published_at=None)])
    ctx = nl.load_edition_context(stub)
    assert "weeks_ago" not in ctx["previous_editions"][0], \
        "weeks_ago must be omitted when published_at is null"


# ══════════════════════════════════════════════════════════════════════════════
# Case 2 — operator_written filtering (D-01)
# ══════════════════════════════════════════════════════════════════════════════


def test_operator_written_filtering_excludes_non_operator():
    """D-01: exemplars are sourced ONLY from operator-written editions; an
    edition-29 / block_v1 analog (operator_written absent) contributes none."""
    stub = StubSupabase([
        _edition(31, content_markdown=LONG_PARA_OP,
                 data_snapshot={"operator_written": "true", "lead_theme": "t"}),
        _edition(29, content_markdown=LONG_PARA_NONOP,
                 data_snapshot={"pipeline_version": "block_v1"}),
    ])
    ctx = nl.load_edition_context(stub)
    assert LONG_PARA_OP in ctx["exemplars"], "operator paragraph should be an exemplar"
    assert LONG_PARA_NONOP not in ctx["exemplars"], \
        "non-operator (block_v1) paragraph must be excluded from exemplars"
    assert ctx["exemplars_status"] == "scored"


# ══════════════════════════════════════════════════════════════════════════════
# Case 3 — >=40-word, non-header, non-list paragraph filtering (D-05)
# ══════════════════════════════════════════════════════════════════════════════


def test_paragraph_filter_keeps_only_long_prose():
    """D-05: from a body mixing a header, a list item, a short paragraph, a long
    prose paragraph, and a long paragraph under a header, ONLY the long PLAIN
    prose paragraph survives as an exemplar."""
    stub = StubSupabase([_edition(31, content_markdown=MIXED_MD,
                                  data_snapshot={"operator_written": "true"})])
    ctx = nl.load_edition_context(stub)
    assert ctx["exemplars"] == [LONG_PARA_OP], \
        f"expected only the long plain-prose paragraph, got {ctx['exemplars']!r}"
    # explicit per-kind exclusions
    assert HEADER_LINE not in ctx["exemplars"]
    assert LIST_LINE not in ctx["exemplars"]
    assert SHORT_PARA not in ctx["exemplars"]
    assert LONG_UNDER_HEADER not in ctx["exemplars"], \
        "a >=40-word paragraph whose first line is a header must still be excluded"


# ══════════════════════════════════════════════════════════════════════════════
# Case 4 — CTX-03 whole-corpus-empty: WARNING + explicit empty marker + no raise
# ══════════════════════════════════════════════════════════════════════════════


def test_empty_corpus_returns_empty_marker_and_warns(caplog):
    """CTX-03 / D-16: zero published rows -> empty=True with empty lists, a
    'continuity context empty' WARNING, and NO exception (generation still
    completes)."""
    with caplog.at_level(logging.WARNING):
        ctx = nl.load_edition_context(StubSupabase([]))  # reaching here proves no raise
    assert ctx["previous_editions"] == []
    assert ctx["exemplars"] == []
    assert ctx["empty"] is True
    assert ctx["exemplars_status"] == "not_scored"
    assert any("continuity context empty" in r.message for r in caplog.records), \
        "empty corpus must emit the literal 'continuity context empty' WARNING"


# ══════════════════════════════════════════════════════════════════════════════
# Case 5 — empty-operator-pool "not scored" (D-02/D-03), distinguishable
# ══════════════════════════════════════════════════════════════════════════════


def test_empty_operator_pool_is_not_scored_not_empty():
    """D-02/D-03: published editions exist but NONE are operator-written ->
    previous_editions non-empty, empty=False, exemplars empty, marker
    'not_scored' (never a silent score:0, never an any-published fallback)."""
    ctx = nl.load_edition_context(_no_operator_stub())
    assert ctx["empty"] is False
    assert ctx["previous_editions"], "published rows must still populate previous_editions"
    assert ctx["exemplars"] == [], "no operator-written exemplars -> empty exemplar list"
    assert ctx["exemplars_status"] == "not_scored"


def test_three_states_are_mutually_distinguishable():
    """The empty-corpus, empty-operator-pool, and scored states are pairwise
    distinguishable — the 'not_scored' marker is never confused with the
    corpus-empty state, a populated exemplar list, or a real numeric score:0."""
    empty_ctx = nl.load_edition_context(StubSupabase([]))
    no_op_ctx = nl.load_edition_context(_no_operator_stub())
    scored_ctx = nl.load_edition_context(_scored_stub())

    # corpus-empty vs empty-operator-pool: both 'not_scored' but split by `empty`
    assert empty_ctx["empty"] is True and no_op_ctx["empty"] is False
    assert empty_ctx["exemplars_status"] == no_op_ctx["exemplars_status"] == "not_scored"
    assert empty_ctx["previous_editions"] == [] and no_op_ctx["previous_editions"] != []

    # scored differs from both degrade states
    assert scored_ctx["exemplars_status"] == "scored"
    assert scored_ctx["exemplars"] != []

    # the marker is a distinguishable enum string, NOT a numeric Phase E score:0
    assert no_op_ctx["exemplars_status"] != 0
    assert no_op_ctx["exemplars"] != [0]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
