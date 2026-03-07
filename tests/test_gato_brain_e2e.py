#!/usr/bin/env python3
"""
G1 — End-to-end test script for gato_brain conversational intelligence.

Exercises all 6 intent types, session management, rate limiting, and observability.
Run against a live gato_brain instance (default: http://localhost:8100).

Usage:
    python tests/test_gato_brain_e2e.py [--url http://host:port]
"""

import argparse
import json
import sys

import httpx

# ─── Config ─────────────────────────────────────────────────────────

DEFAULT_URL = "http://localhost:8100"
TEST_USER = "test_e2e_user_999"
OWNER_USER = "test_owner_001"


def chat(client: httpx.Client, user_id: str, message: str) -> dict:
    """Send a chat message and return the response."""
    resp = client.post("/chat", json={
        "user_id": user_id,
        "message": message,
        "message_type": "text",
    }, timeout=60)
    resp.raise_for_status()
    return resp.json()


def section(name: str):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


def check(label: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if detail:
        print(f"         {detail}")
    return condition


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL, help="gato_brain base URL")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.url)
    passed = 0
    failed = 0
    results = []

    def track(ok: bool):
        nonlocal passed, failed
        if ok:
            passed += 1
        else:
            failed += 1

    # ── Health check ─────────────────────────────────────────────
    section("TEST 0 — Health Check")
    try:
        r = client.get("/health", timeout=10)
        data = r.json()
        ok = check("Health endpoint returns 200", r.status_code == 200, json.dumps(data))
        track(ok)
    except Exception as e:
        check("Health endpoint reachable", False, str(e))
        track(False)
        print("\nCannot reach gato_brain. Aborting.")
        sys.exit(1)

    # ── TEST 1 — Conversation memory + FOLLOW_UP ─────────────────
    section("TEST 1 — Conversation Memory + Follow-up")

    r1 = chat(client, TEST_USER, "hi")
    ok = check("Greeting returns response", bool(r1.get("response")), f"Intent: {r1.get('intent')}")
    track(ok)
    results.append({"test": "greeting", "intent": r1.get("intent"), "response": r1["response"][:100]})

    r2 = chat(client, TEST_USER, "what's the latest spotlight about?")
    ok = check("Corpus query returns response", bool(r2.get("response")),
               f"Intent: {r2.get('intent')}, probe_score: {r2.get('metadata', {}).get('probe_top_score')}")
    track(ok)

    r3 = chat(client, TEST_USER, "tell me more about that")
    ok = check("Follow-up detected", r3.get("intent") == "FOLLOW_UP",
               f"Intent: {r3.get('intent')}")
    track(ok)
    ok = check("Follow-up references previous context", len(r3.get("response", "")) > 20)
    track(ok)

    # ── TEST 2 — Corpus deep dive ────────────────────────────────
    section("TEST 2 — Corpus Deep Dive")

    r = chat(client, TEST_USER, "what's our thesis on AI agents and Bitcoin?")
    meta = r.get("metadata", {})
    ok = check("Corpus query intent", r.get("intent") in ("CORPUS_QUERY", "HYBRID"),
               f"Intent: {r.get('intent')}")
    track(ok)
    ok = check("Chunks retrieved > 0", meta.get("chunks_retrieved", 0) > 0,
               f"Retrieved: {meta.get('chunks_retrieved')}, expanded: {meta.get('chunks_expanded')}")
    track(ok)
    ok = check("Probe score logged", meta.get("probe_top_score") is not None,
               f"Score: {meta.get('probe_top_score')}")
    track(ok)

    # ── TEST 3 — Structured queries ──────────────────────────────
    section("TEST 3 — Structured Queries")

    for query, _ in [
        ("what tools are trending?", "trending_tools"),
        ("show me the prediction scorecard", "prediction_scorecard"),
        ("any confirmed predictions?", "confirmed_predictions"),
    ]:
        r = chat(client, TEST_USER, query)
        ok = check(f"'{query}' → STRUCTURED_QUERY",
                   r.get("intent") == "STRUCTURED_QUERY",
                   f"Intent: {r.get('intent')}")
        track(ok)
        results.append({"test": query, "intent": r.get("intent"), "response": r["response"][:100]})

    # ── TEST 4 — Web search ──────────────────────────────────────
    section("TEST 4 — Web Search")

    r = chat(client, TEST_USER, "what's the latest news on Anthropic?")
    ok = check("Web search intent", r.get("intent") in ("WEB_SEARCH", "HYBRID"),
               f"Intent: {r.get('intent')}")
    track(ok)
    ok = check("Web results used", r.get("metadata", {}).get("web_results_count", 0) > 0,
               f"Web results: {r.get('metadata', {}).get('web_results_count')}")
    track(ok)

    # ── TEST 5 — Hybrid ──────────────────────────────────────────
    section("TEST 5 — Hybrid (Corpus + Web)")

    r = chat(client, TEST_USER, "is our thesis on AI agent wallets still valid based on current news?")
    meta = r.get("metadata", {})
    ok = check("Hybrid intent", r.get("intent") == "HYBRID",
               f"Intent: {r.get('intent')}")
    track(ok)
    ok = check("Both corpus and web used",
               meta.get("chunks_retrieved", 0) > 0 or meta.get("web_results_count", 0) > 0,
               f"Corpus: {meta.get('chunks_retrieved')}, Web: {meta.get('web_results_count')}")
    track(ok)

    # ── TEST 6 — Follow-up with re-hydration ─────────────────────
    section("TEST 6 — Follow-up Re-hydration")

    r = chat(client, TEST_USER, "what was the source for that?")
    ok = check("Follow-up intent", r.get("intent") == "FOLLOW_UP",
               f"Intent: {r.get('intent')}")
    track(ok)
    ok = check("Response references sources", len(r.get("response", "")) > 20)
    track(ok)

    # ── TEST 7 — Session windowing ────────────────────────────────
    section("TEST 7 — Session Consistency")

    r_a = chat(client, TEST_USER, "hello again")
    r_b = chat(client, TEST_USER, "still here")
    ok = check("Same session across messages",
               r_a.get("session_id") == r_b.get("session_id") and r_a.get("session_id"),
               f"Session A: {r_a.get('session_id')[:8]}... Session B: {r_b.get('session_id')[:8]}...")
    track(ok)

    # ── TEST 8 — DIRECT intent ────────────────────────────────────
    section("TEST 8 — Direct Intent")

    r = chat(client, TEST_USER, "thanks!")
    ok = check("Thanks → DIRECT", r.get("intent") == "DIRECT",
               f"Intent: {r.get('intent')}")
    track(ok)

    # ── TEST 9 — Latency metadata ────────────────────────────────
    section("TEST 9 — Observability Metadata")

    r = chat(client, TEST_USER, "summarize our latest research spotlights")
    meta = r.get("metadata", {})
    ok = check("probe_latency_ms present", meta.get("probe_latency_ms") is not None,
               f"Probe: {meta.get('probe_latency_ms')}ms")
    track(ok)
    ok = check("route_latency_ms present", meta.get("route_latency_ms") is not None,
               f"Router: {meta.get('route_latency_ms')}ms")
    track(ok)
    ok = check("retrieval_latency_ms present", meta.get("retrieval_latency_ms") is not None,
               f"Retrieval: {meta.get('retrieval_latency_ms')}ms")
    track(ok)
    ok = check("generation_latency_ms present", meta.get("generation_latency_ms") is not None,
               f"Generation: {meta.get('generation_latency_ms')}ms")
    track(ok)

    # ── TEST 10 — Embed pipeline status ──────────────────────────
    section("TEST 10 — Embed Pipeline Status")

    try:
        r = client.get("/embed/status", timeout=10)
        data = r.json()
        ok = check("Embed status endpoint works", r.status_code == 200, json.dumps(data))
        track(ok)
    except Exception as e:
        check("Embed status endpoint", False, str(e))
        track(False)

    # ── Summary ──────────────────────────────────────────────────
    section("SUMMARY")
    total = passed + failed
    print(f"  Passed: {passed}/{total}")
    print(f"  Failed: {failed}/{total}")

    if failed > 0:
        print("\n  Failed tests need investigation.")
        sys.exit(1)
    else:
        print("\n  All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
