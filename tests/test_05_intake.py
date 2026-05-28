#!/usr/bin/env python3
"""
Phase 5 Plan 03 — spine guarantees for the intake classifier / unsorted handling.

Proves three things the phase must uphold, as machine checks:

  Test A  append_only (INTK-05 / ROADMAP criterion 5): the Phase-2 migration-033
          trigger rejects UPDATE and DELETE on economy_map.timeline_entries content
          columns. Proven STRUCTURALLY (default, no DB access) by asserting the
          migration-033 SQL defines timeline_entries_append_only() — RAISEing on
          DELETE and on each pinned content-column UPDATE — wired via a
          BEFORE UPDATE OR DELETE trigger. This is the mitigation for threat T-05-10
          (a future "simplify to RLS" regression would fail this assertion). An
          OPTIONAL live UPDATE/DELETE-fail check against an existing row runs only
          when INTK05_LIVE_DB=1 is set (default skip — this host is production and
          the operator preferred not issuing live mutations against the shared
          append-only table; the structural check is the default proof).

  Test B  below-floor routing (ROADMAP criterion 3): a below-floor classification
          routes the event to 'unsorted' while RECORDING tag_confidence. Driven
          deterministically by monkeypatching classify_intake_event to return a
          low-confidence result, then calling Plan 02's classify_intake_for_edition
          (the route decision lives there) and capturing the INSERT payload. Offline.

  Test C  error-path NULL confidence (D-05): a classifier exception routes the event
          to 'unsorted' with tag_confidence = NULL — never dropped. Same capture
          approach as Test B. Offline.

  Test D  proxy-routing evidence (ROADMAP criterion 2 / SC-2): a LIVE classification
          through http://llm-proxy:8200 via Plan 01's classify_intake_event leaves
          durable proxy-side evidence — the per-call wallet_transactions row the
          proxy records. Asserts the processor agent's wallet_transactions count
          increments. Skips cleanly without the proxy/agent-key secrets.

Run standalone (pytest is NOT installed here):  python3 tests/test_05_intake.py
The file is also pytest-collectable if pytest is ever present.
"""
import json
import os
import sys
import time
import types
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Load config/.env (live-Supabase / live-proxy secrets) BEFORE importing the
# processor, so the module-level SUPABASE_URL/SUPABASE_KEY reads pick them up.
# Mirrors tests/test_phase2_integration.py.
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / "config" / ".env")
except Exception:
    pass

# ---------------------------------------------------------------------------
# Stub heavy third-party libs the processor imports at module level but that are
# not needed for these tests, so the module imports in a bare environment.
# Mirrors tests/test_05a_intake_classifier.py.
# ---------------------------------------------------------------------------
for _name in ("schedule", "tweepy", "resend"):
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

os.environ.setdefault("OPENCLAW_DATA_DIR", "/tmp/openclaw_test_05")
sys.path.insert(0, str(_ROOT / "docker" / "processor"))

import agentpulse_processor as proc  # noqa: E402
import httpx  # noqa: E402

# Prime the model-routing cache from the repo config so get_model("extraction")
# resolves to deepseek-chat exactly as in the deployed processor (which reads a
# hardcoded /home/openclaw path that is absent here).
_REPO_CONFIG = json.loads((_ROOT / "config" / "agentpulse-config.json").read_text())
proc._model_config_cache = _REPO_CONFIG.get("models", {})


# ---------------------------------------------------------------------------
# Skip plumbing: works standalone (raises _Skip, runner prints SKIP) and under
# pytest (raises pytest.skip's Skipped) — so the suite never ERRORs on absent
# secrets, it SKIPs.
# ---------------------------------------------------------------------------
class _Skip(Exception):
    """Raised to signal a clean skip when required secrets are absent."""


def _skip(reason: str):
    try:
        import pytest  # type: ignore
        pytest.skip(reason)
    except ImportError:
        raise _Skip(reason)


ALLOWED_SLUGS = list(proc.INTAKE_BLOCK_SLUGS_FALLBACK)  # the seven seeded slugs

EVENT = {
    "title": "Stripe updates Link wallet for autonomous AI agent spending",
    "summary": "Link lets users authorize AI agents to spend via approval flows.",
    "url": "https://example.com/stripe-link",
}

FLOOR = float(
    _REPO_CONFIG.get("intake_classifier", {}).get("confidence_floor", 0.6)
)


def _have_supabase() -> bool:
    return bool(proc.SUPABASE_URL and proc.SUPABASE_KEY)


def _economy_map_headers(extra: dict | None = None) -> dict:
    h = {
        "apikey": proc.SUPABASE_KEY,
        "Authorization": f"Bearer {proc.SUPABASE_KEY}",
    }
    if extra:
        h.update(extra)
    return h


# ===========================================================================
# Test A — append-only INSERT -> UPDATE -> DELETE (INTK-05 / criterion 5)
# ===========================================================================
_MIGRATION_033 = _ROOT / "supabase" / "migrations" / "033_economy_map_schema.sql"


def _normalize_ws(text: str) -> str:
    return " ".join(text.split())


def test_append_only_trigger_rejects_update_and_delete():
    """STRUCTURAL proof (default, no DB access): migration 033 defines the
    timeline_entries append-only trigger that RAISEs on DELETE and on each pinned
    content-column UPDATE, wired BEFORE UPDATE OR DELETE. This is the INTK-05 /
    criterion-5 guarantee and the T-05-10 regression guard — a future change that
    weakened the trigger (e.g. "simplify to RLS") would fail here.

    This host is production and the operator preferred not issuing live UPDATE/DELETE
    against the shared append-only table, so the live attempt is opt-in only
    (test_append_only_live_update_and_delete_fail, gated on INTK05_LIVE_DB=1)."""
    assert _MIGRATION_033.exists(), "migration 033 missing"
    sql = _MIGRATION_033.read_text(encoding="utf-8")
    flat = _normalize_ws(sql)

    # The append-only trigger FUNCTION exists for timeline_entries.
    assert "economy_map.timeline_entries_append_only()" in flat, (
        "timeline_entries_append_only() trigger function missing from migration 033"
    )
    # DELETE is rejected.
    assert "TG_OP = 'DELETE'" in flat and "append-only (DELETE not permitted)" in flat, (
        "trigger must RAISE on DELETE"
    )
    # Each pinned content column rejects UPDATE (RAISE on IS DISTINCT FROM).
    for col in ("block_slug", "event_date", "what_shifted", "why_it_mattered",
                "source_url", "source_edition_id", "tag_confidence"):
        assert f"NEW.{col} IS DISTINCT FROM OLD.{col}" in flat, (
            f"trigger must guard UPDATE of pinned column {col}"
        )
        assert f"timeline_entries.{col} is append-only" in flat, (
            f"trigger must RAISE the append-only message for {col}"
        )
    # The trigger is wired BEFORE UPDATE OR DELETE on the table.
    assert "BEFORE UPDATE OR DELETE ON economy_map.timeline_entries" in flat, (
        "trigger must be wired BEFORE UPDATE OR DELETE on timeline_entries"
    )
    assert "EXECUTE FUNCTION economy_map.timeline_entries_append_only()" in flat, (
        "trigger must EXECUTE the append-only function"
    )


def _read_existing_timeline_row_id() -> str | None:
    """Return the id of one EXISTING timeline_entries row, or None if the table is
    empty. Direct PostgREST read (Accept-Profile: economy_map), no mutation."""
    resp = httpx.get(
        f"{proc.SUPABASE_URL}/rest/v1/timeline_entries",
        params={"select": "id", "limit": 1},
        headers=_economy_map_headers({"Accept-Profile": "economy_map"}),
        timeout=10,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"timeline_entries read failed ({resp.status_code}): {resp.text}")
    rows = resp.json()
    if isinstance(rows, list) and rows:
        return rows[0].get("id")
    return None


def test_append_only_live_update_and_delete_fail():
    """OPT-IN live proof (INTK05_LIVE_DB=1): attempt UPDATE and DELETE against an
    EXISTING timeline_entries row and assert both fail (4xx) at the trigger.

    NON-DESTRUCTIVE: the trigger fires BEFORE UPDATE OR DELETE and RAISEs, so the row
    is never actually changed or removed — the operation is rejected before any
    mutation. No row is inserted. Default SKIP because this host is production and
    the structural check above is the default proof; set INTK05_LIVE_DB=1 to run it.
    """
    if os.getenv("INTK05_LIVE_DB") != "1":
        _skip("live append-only UPDATE/DELETE check is opt-in (set INTK05_LIVE_DB=1); "
              "structural proof in test_append_only_trigger_rejects_update_and_delete "
              "is the default — this host is production")
    if not _have_supabase():
        _skip("live check needs SUPABASE_URL + SUPABASE_SERVICE_KEY")

    row_id = _read_existing_timeline_row_id()
    if not row_id:
        _skip("no existing timeline_entries row to target non-destructively (table empty)")

    update_resp = httpx.patch(
        f"{proc.SUPABASE_URL}/rest/v1/timeline_entries",
        params={"id": f"eq.{row_id}"},
        headers=_economy_map_headers({
            "Content-Type": "application/json",
            "Content-Profile": "economy_map",
            "Prefer": "return=minimal",
        }),
        json={"what_shifted": f"APPEND-ONLY-PROBE-{uuid.uuid4()} (must be rejected)"},
        timeout=10,
    )
    assert update_resp.status_code >= 400, (
        f"UPDATE of what_shifted should FAIL (append-only trigger), "
        f"got {update_resp.status_code}: {update_resp.text}"
    )

    delete_resp = httpx.delete(
        f"{proc.SUPABASE_URL}/rest/v1/timeline_entries",
        params={"id": f"eq.{row_id}"},
        headers=_economy_map_headers({
            "Content-Profile": "economy_map",
            "Prefer": "return=minimal",
        }),
        timeout=10,
    )
    assert delete_resp.status_code >= 400, (
        f"DELETE should FAIL (append-only trigger), "
        f"got {delete_resp.status_code}: {delete_resp.text}"
    )


# ===========================================================================
# Tests B/C harness — drive Plan 02's classify_intake_for_edition offline by
# stubbing the classifier + idempotency check and capturing the INSERT payload.
# ===========================================================================
def _synthetic_edition() -> dict:
    return {
        "id": f"test-edition-{uuid.uuid4()}",
        "published_at": "2026-05-28T11:00:00+00:00",
        "data_snapshot": {
            "premium_source_posts": [
                {
                    "tier": 1,
                    "title": EVENT["title"],
                    "summary": EVENT["summary"],
                    "url": EVENT["url"],
                },
            ],
        },
    }


def _run_edition_with_classifier(classifier_stub):
    """Call classify_intake_for_edition with classify_intake_event stubbed and the
    INSERT helper captured. Returns the list of INSERT payloads handed to the helper.

    economy_map_emitted_event_keys is stubbed to an empty set so the edition is
    processed offline (no live read) with no events considered already-emitted;
    classify_intake_event is replaced by classifier_stub.
    """
    captured: list[dict] = []
    saved = {
        "classify": proc.classify_intake_event,
        "keys": proc.economy_map_emitted_event_keys,
        "insert": proc.economy_map_insert_timeline_entry,
    }
    proc.classify_intake_event = classifier_stub
    proc.economy_map_emitted_event_keys = lambda _eid: set()
    proc.economy_map_insert_timeline_entry = lambda entry: captured.append(dict(entry)) or {"id": "captured"}
    try:
        proc.classify_intake_for_edition(_synthetic_edition(), ALLOWED_SLUGS, FLOOR)
    finally:
        proc.classify_intake_event = saved["classify"]
        proc.economy_map_emitted_event_keys = saved["keys"]
        proc.economy_map_insert_timeline_entry = saved["insert"]
    return captured


# ===========================================================================
# Test B — below-floor routing (criterion 3, via Plan 02 route decision)
# ===========================================================================
def test_below_floor_routes_to_unsorted_with_recorded_confidence():
    """A below-floor classification routes to 'unsorted' but RECORDS tag_confidence
    (flagged-not-dropped). Stubs classify_intake_event to return a valid named slug
    at a confidence below the config floor; asserts the INSERT payload built by
    classify_intake_for_edition lands in 'unsorted' with the stubbed confidence."""
    below = round(FLOOR - 0.2, 3)  # deterministically below the floor

    def stub(event, allowed_slugs):
        # A valid named slug, but confidence below the floor → must route to unsorted.
        return {"block_slug": "payments-settlement", "tag_confidence": below}

    captured = _run_edition_with_classifier(stub)
    assert len(captured) == 1, f"expected exactly one INSERT, got {len(captured)}"
    entry = captured[0]
    assert entry["block_slug"] == "unsorted", (
        f"below-floor must route to 'unsorted', got {entry['block_slug']!r}"
    )
    assert entry["tag_confidence"] is not None, "below-floor must RECORD confidence (not NULL)"
    assert abs(float(entry["tag_confidence"]) - below) < 1e-9, (
        f"recorded confidence {entry['tag_confidence']!r} != stubbed {below!r}"
    )


# ===========================================================================
# Test C — error-path NULL confidence (D-05, via Plan 02 route decision)
# ===========================================================================
def test_classifier_error_routes_to_unsorted_with_null_confidence():
    """A classifier exception routes the event to 'unsorted' with tag_confidence
    NULL — the event is NEVER dropped (D-05). Stubs classify_intake_event to raise."""

    def stub(event, allowed_slugs):
        raise RuntimeError("simulated classifier/proxy failure")

    captured = _run_edition_with_classifier(stub)
    assert len(captured) == 1, f"expected exactly one INSERT (never dropped), got {len(captured)}"
    entry = captured[0]
    assert entry["block_slug"] == "unsorted", (
        f"classifier error must route to 'unsorted', got {entry['block_slug']!r}"
    )
    assert entry["tag_confidence"] is None, (
        f"classifier error must record NULL confidence, got {entry['tag_confidence']!r}"
    )
    # The event content still survives (not silently dropped).
    assert entry["what_shifted"] == EVENT["title"]
    assert entry["source_edition_id"], "source_edition_id must be set even on error path"


# ===========================================================================
# Test B2 — out-of-range confidence is untrusted (WR-01 regression)
# ===========================================================================
def test_out_of_range_confidence_routes_unsorted_null():
    """WR-01: an out-of-range tag_confidence (e.g. a percentage 91 instead of 0.91)
    must NOT overflow NUMERIC(3,2) / spuriously clear the floor. The event is preserved
    (never dropped) but routed to 'unsorted' with NULL confidence — the malformed score
    is treated as untrusted, not fabricated into a clamped/confident value."""

    def stub(event, allowed_slugs):
        # A valid named slug but a junk confidence (percentage style) — out of [0,1].
        return {"block_slug": "payments-settlement", "tag_confidence": 91}

    captured = _run_edition_with_classifier(stub)
    assert len(captured) == 1, f"out-of-range confidence must NOT drop the event, got {len(captured)}"
    entry = captured[0]
    assert entry["block_slug"] == "unsorted", (
        f"out-of-range confidence must route to 'unsorted', got {entry['block_slug']!r}"
    )
    assert entry["tag_confidence"] is None, (
        f"out-of-range confidence must be recorded as NULL (untrusted), got {entry['tag_confidence']!r}"
    )


# ===========================================================================
# Test C2 — partial-emit fails loud then retry completes (CR-01 regression)
# ===========================================================================
def test_partial_insert_failure_fails_loud_then_retry_completes():
    """CR-01: a transient insert failure mid-edition must (a) fail loud (raise) so the
    edition is NOT silently marked done, and (b) on a later run, per-event idempotency
    skips the rows that already landed and retries ONLY the failed event — the event is
    eventually emitted, never lost, and never duplicated on the append-only table."""
    ev1 = {"tier": 1, "title": "Event one", "summary": "S1", "url": "https://example.com/1"}
    ev2 = {"tier": 1, "title": "Event two", "summary": "S2", "url": "https://example.com/2"}
    edition = {
        "id": f"test-edition-{uuid.uuid4()}",
        "published_at": "2026-05-28T11:00:00+00:00",
        "data_snapshot": {"premium_source_posts": [ev1, ev2]},
    }
    saved = {
        "classify": proc.classify_intake_event,
        "keys": proc.economy_map_emitted_event_keys,
        "insert": proc.economy_map_insert_timeline_entry,
    }
    landed: list[dict] = []  # rows that "made it into" the append-only table

    # Idempotency reads back exactly what landed (keyed on source_url, else what_shifted).
    proc.economy_map_emitted_event_keys = lambda _eid: {
        (r.get("source_url") or r.get("what_shifted")) for r in landed
    }
    proc.classify_intake_event = lambda e, slugs: {"block_slug": "unsorted", "tag_confidence": 0.1}
    try:
        # Run 1: ev1 inserts; ev2's insert raises a transient error.
        def insert_run1(entry):
            if entry["source_url"] == ev2["url"]:
                raise RuntimeError("simulated transient PostgREST 503")
            landed.append(dict(entry))
            return {"id": "ok"}
        proc.economy_map_insert_timeline_entry = insert_run1

        raised = False
        try:
            proc.classify_intake_for_edition(edition, ALLOWED_SLUGS, FLOOR)
        except RuntimeError:
            raised = True
        assert raised, "partial insert failure must fail loud (raise), not return silently"
        assert [r["source_url"] for r in landed] == [ev1["url"]], (
            f"only ev1 should have landed in run 1, got {landed!r}"
        )

        # Run 2 (retry): inserts now succeed. Per-event idempotency must skip ev1 and
        # emit ONLY ev2 — no duplicate of ev1, and the previously-failed event completes.
        attempted: list[str] = []
        def insert_run2(entry):
            attempted.append(entry["source_url"])
            landed.append(dict(entry))
            return {"id": "ok"}
        proc.economy_map_insert_timeline_entry = insert_run2
        proc.classify_intake_for_edition(edition, ALLOWED_SLUGS, FLOOR)
        assert attempted == [ev2["url"]], (
            f"retry must insert ONLY the previously-failed event, got {attempted!r}"
        )
        assert sorted(r["source_url"] for r in landed) == [ev1["url"], ev2["url"]], (
            "both events must end up emitted exactly once after retry (never dropped, never duped)"
        )
    finally:
        proc.classify_intake_event = saved["classify"]
        proc.economy_map_emitted_event_keys = saved["keys"]
        proc.economy_map_insert_timeline_entry = saved["insert"]


# ===========================================================================
# Test D — live proxy-routing evidence (criterion 2 / SC-2, Plan 01 classifier)
# ===========================================================================
def _processor_wallet_txn_count() -> int:
    """Count wallet_transactions rows for the processor agent (public schema,
    direct PostgREST, exact-count header). Returns the integer count."""
    resp = httpx.get(
        f"{proc.SUPABASE_URL}/rest/v1/wallet_transactions",
        params={"agent_name": "eq.processor", "select": "id"},
        headers=_economy_map_headers({"Prefer": "count=exact", "Range": "0-0"}),
        timeout=10,
    )
    if resp.status_code not in (200, 206):
        raise RuntimeError(f"wallet_transactions count failed ({resp.status_code}): {resp.text}")
    # PostgREST returns the exact count in Content-Range: "0-0/<total>" (or "*/<total>").
    content_range = resp.headers.get("content-range", "")
    if "/" in content_range:
        total = content_range.rsplit("/", 1)[-1]
        if total.isdigit():
            return int(total)
    # Fallback: length of returned rows (only the requested range).
    rows = resp.json()
    return len(rows) if isinstance(rows, list) else 0


def test_live_classifier_leaves_proxy_routing_evidence():
    """A LIVE classify_intake_event call through http://llm-proxy:8200 leaves durable
    proxy-side evidence: the per-call wallet_transactions row the proxy records
    (proxy.py async_log_transaction). Asserts the processor agent's
    wallet_transactions count increments — proving the call is actually ROUTED
    through the proxy per classification (ROADMAP criterion 2 / the RivalScope
    governance lesson), not merely shaped to POST a proxy URL.

    Skips cleanly when the live secrets are absent (SUPABASE for the wallet read,
    AGENT_API_KEY + a reachable proxy for the classification) — so the suite runs
    in CI without secrets.
    """
    if not _have_supabase():
        _skip("Test D needs SUPABASE_URL + SUPABASE_SERVICE_KEY (wallet_transactions read)")

    proc.init_clients()
    agent_key = proc._get_agent_api_key()
    if not agent_key:
        _skip("Test D needs the processor AGENT_API_KEY (proxy auth) — absent")

    # Probe proxy reachability; skip (do not error) if the proxy is unreachable
    # (e.g. running on the host where 'llm-proxy' does not resolve).
    proxy_url = proc.LLM_PROXY_URL
    try:
        httpx.get(f"{proxy_url}/health", timeout=3)
    except Exception:
        try:
            httpx.get(proxy_url, timeout=3)
        except Exception as e:
            _skip(f"Test D needs a reachable llm-proxy at {proxy_url} — {e}")

    before = _processor_wallet_txn_count()
    # Live classification through the proxy (Plan 01 path).
    result = proc.classify_intake_event(EVENT, ALLOWED_SLUGS)
    assert isinstance(result, dict) and "block_slug" in result, (
        f"live classify_intake_event returned unexpected shape: {result!r}"
    )

    # The proxy writes wallet_transactions via an async batched flush, so poll a
    # short window for the increment rather than reading once.
    deadline = time.time() + 20
    after = before
    while time.time() < deadline:
        after = _processor_wallet_txn_count()
        if after > before:
            break
        time.sleep(2)

    assert after > before, (
        "proxy-routing evidence missing: processor wallet_transactions count did not "
        f"increment ({before} -> {after}) after a live classify_intake_event call — "
        "the classification did not traverse the proxy (criterion 2 regression)."
    )


# ---------------------------------------------------------------------------
# Standalone runner (pytest is not installed in this environment).
# ---------------------------------------------------------------------------
def _run_all():
    tests = [
        test_append_only_trigger_rejects_update_and_delete,
        test_append_only_live_update_and_delete_fail,
        test_below_floor_routes_to_unsorted_with_recorded_confidence,
        test_classifier_error_routes_to_unsorted_with_null_confidence,
        test_out_of_range_confidence_routes_unsorted_null,
        test_partial_insert_failure_fails_loud_then_retry_completes,
        test_live_classifier_leaves_proxy_routing_evidence,
    ]
    failures = []
    skipped = []
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except _Skip as s:
            skipped.append((t.__name__, str(s)))
            print(f"SKIP  {t.__name__}: {s}")
        except Exception as e:
            failures.append((t.__name__, e))
            print(f"FAIL  {t.__name__}: {e}")
    print(
        f"\n{len(tests) - len(failures) - len(skipped)} passed, "
        f"{len(skipped)} skipped, {len(failures)} failed"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run_all())
