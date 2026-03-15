#!/usr/bin/env python3
"""
Retrieval quality evaluation for AgentPulse embeddings.

Runs a test suite of queries against search_corpus() and reports recall@5,
keyword hit rate, and similarity scores.

Usage:
    python eval_retrieval.py                    # run eval, print report
    python eval_retrieval.py --verbose          # show per-query details
    python eval_retrieval.py --test-file X.json # use custom test cases
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client
from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).resolve().parent / "config" / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSIONS = 1536
MATCH_COUNT = 5


def embed_query(client: OpenAI, text: str) -> list[float]:
    """Embed a single query string."""
    resp = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[text],
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return resp.data[0].embedding


def search_corpus(supabase: Client, embedding: list[float], match_count: int = MATCH_COUNT) -> list[dict]:
    """Call the search_corpus() Postgres function via RPC."""
    resp = supabase.rpc("search_corpus", {
        "query_embedding": embedding,
        "match_count": match_count,
    }).execute()
    return resp.data or []


def check_keywords(results: list[dict], expected_keywords: list[str]) -> dict:
    """Check which expected keywords appear in any result's content_text."""
    all_text = " ".join(r.get("content_text", "") for r in results).lower()
    hits = {}
    for kw in expected_keywords:
        hits[kw] = kw.lower() in all_text
    return hits


def run_eval(
    supabase: Client,
    openai_client: OpenAI,
    test_cases: list[dict],
    verbose: bool = False,
) -> dict:
    """Run the full evaluation. Returns results dict."""
    results = []
    total = len(test_cases)

    for i, tc in enumerate(test_cases, 1):
        query = tc["query"]
        expected_table = tc["expected_source_table"]
        expected_kws = tc.get("expected_keywords", [])
        min_sim = tc.get("min_acceptable_similarity", 0.70)

        if verbose:
            print(f"\n[{i}/{total}] {query}")

        t0 = time.time()
        embedding = embed_query(openai_client, query)
        hits = search_corpus(supabase, embedding)
        elapsed = time.time() - t0

        # Extract results
        top_sim = hits[0]["similarity"] if hits else 0.0
        found_tables = [h["source_table"] for h in hits]
        table_found = expected_table in found_tables
        table_rank = (found_tables.index(expected_table) + 1) if table_found else None

        # Keyword check
        kw_hits = check_keywords(hits, expected_kws)
        kw_hit_count = sum(1 for v in kw_hits.values() if v)
        kw_total = len(expected_kws)

        # Similarity check
        sim_pass = top_sim >= min_sim

        result = {
            "query": query,
            "expected_source_table": expected_table,
            "table_found": table_found,
            "table_rank": table_rank,
            "top_similarity": round(top_sim, 4),
            "min_acceptable_similarity": min_sim,
            "similarity_pass": sim_pass,
            "keyword_hits": kw_hits,
            "keyword_hit_rate": round(kw_hit_count / kw_total, 2) if kw_total else 1.0,
            "elapsed_s": round(elapsed, 2),
            "returned_tables": found_tables,
            "returned_previews": [
                {
                    "source_table": h["source_table"],
                    "similarity": round(h["similarity"], 4),
                    "content_preview": h["content_text"][:120],
                }
                for h in hits
            ],
        }
        results.append(result)

        if verbose:
            status = "PASS" if (table_found and sim_pass) else "FAIL"
            print(f"  {status} | top_sim={top_sim:.4f} | table_found={table_found} (rank={table_rank}) | kw={kw_hit_count}/{kw_total} | {elapsed:.2f}s")
            if not table_found or not sim_pass:
                print(f"  Expected: {expected_table}")
                print(f"  Got: {found_tables}")
                for h in hits[:3]:
                    print(f"    [{h['source_table']}] sim={h['similarity']:.4f} | {h['content_text'][:80]}")

    # Aggregate metrics
    table_recall = sum(1 for r in results if r["table_found"]) / total if total else 0
    avg_sim = sum(r["top_similarity"] for r in results) / total if total else 0
    sim_pass_rate = sum(1 for r in results if r["similarity_pass"]) / total if total else 0
    avg_kw_hit = sum(r["keyword_hit_rate"] for r in results) / total if total else 0

    failures = [r for r in results if not r["table_found"] or not r["similarity_pass"]]

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_queries": total,
        "recall_at_5": round(table_recall, 4),
        "avg_top_similarity": round(avg_sim, 4),
        "similarity_pass_rate": round(sim_pass_rate, 4),
        "avg_keyword_hit_rate": round(avg_kw_hit, 4),
        "failures_count": len(failures),
        "per_query_results": results,
    }

    return report


def print_report(report: dict):
    """Print a human-readable summary."""
    print("\n" + "=" * 60)
    print("RETRIEVAL EVAL REPORT")
    print("=" * 60)
    print(f"Timestamp:            {report['timestamp']}")
    print(f"Total queries:        {report['total_queries']}")
    print(f"Recall@5:             {report['recall_at_5']:.1%}")
    print(f"Avg top similarity:   {report['avg_top_similarity']:.4f}")
    print(f"Similarity pass rate: {report['similarity_pass_rate']:.1%}")
    print(f"Avg keyword hit rate: {report['avg_keyword_hit_rate']:.1%}")
    print(f"Failures:             {report['failures_count']}")

    failures = [r for r in report["per_query_results"] if not r["table_found"] or not r["similarity_pass"]]
    if failures:
        print("\n--- FAILING QUERIES ---")
        for f in failures:
            reasons = []
            if not f["table_found"]:
                reasons.append(f"table '{f['expected_source_table']}' not in top 5")
            if not f["similarity_pass"]:
                reasons.append(f"sim {f['top_similarity']:.4f} < {f['min_acceptable_similarity']}")
            print(f"\n  Q: {f['query']}")
            print(f"  REASON: {'; '.join(reasons)}")
            print(f"  Got tables: {f['returned_tables']}")
            for p in f["returned_previews"][:3]:
                print(f"    [{p['source_table']}] sim={p['similarity']:.4f} | {p['content_preview'][:80]}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="AgentPulse retrieval eval")
    parser.add_argument("--verbose", action="store_true", help="Show per-query results")
    parser.add_argument("--test-file", default="eval_test_cases.json", help="Path to test cases JSON")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
        sys.exit(1)
    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY not set")
        sys.exit(1)

    # Load test cases
    test_file = Path(args.test_file)
    if not test_file.is_absolute():
        test_file = Path(__file__).resolve().parent / test_file
    test_cases = json.loads(test_file.read_text())
    print(f"Loaded {len(test_cases)} test cases from {test_file.name}")

    # Init clients
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

    # Run eval
    t0 = time.time()
    report = run_eval(supabase, openai_client, test_cases, verbose=args.verbose)
    report["total_elapsed_s"] = round(time.time() - t0, 2)

    # Print report
    print_report(report)

    # Save results
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results_path = Path(__file__).resolve().parent / f"eval_results_{ts}.json"
    results_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nResults saved to {results_path.name}")


if __name__ == "__main__":
    main()
