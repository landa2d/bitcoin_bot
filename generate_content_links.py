#!/usr/bin/env python3
"""
Generate content_links entries from existing data relationships.

Scans tables for semantic/structural relationships and creates graph edges
used by corpus_probe.py for one-hop graph expansion during retrieval.

Usage:
    python generate_content_links.py
"""

import logging
import os
import re
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent / "config" / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("content-links")


def normalize(text: str) -> set[str]:
    """Extract lowercase keyword tokens from text."""
    return set(re.findall(r'[a-z]{3,}', text.lower()))


def keyword_overlap(text_a: str, text_b: str, min_overlap: int = 3) -> float:
    """Return Jaccard-like overlap score between two texts."""
    tokens_a = normalize(text_a)
    tokens_b = normalize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    overlap = len(tokens_a & tokens_b)
    if overlap < min_overlap:
        return 0.0
    return overlap / len(tokens_a | tokens_b)


_existing_links: set[tuple] = set()


def load_existing_links(sb):
    """Pre-load all existing links to avoid duplicates."""
    global _existing_links
    rows = fetch_all(sb, "content_links", "source_table, source_id, target_table, target_id, link_type")
    _existing_links = {
        (r["source_table"], str(r["source_id"]), r["target_table"], str(r["target_id"]), r["link_type"])
        for r in rows
    }
    logger.info(f"Loaded {len(_existing_links)} existing content links")


def upsert_link(sb, source_table, source_id, target_table, target_id, link_type, **_kwargs):
    """Insert a content link, skipping duplicates via in-memory set."""
    key = (source_table, str(source_id), target_table, str(target_id), link_type)
    if key in _existing_links:
        return False
    try:
        sb.table("content_links").insert({
            "source_table": source_table,
            "source_id": str(source_id),
            "target_table": target_table,
            "target_id": str(target_id),
            "link_type": link_type,
        }).execute()
        _existing_links.add(key)
        return True
    except Exception as e:
        logger.warning(f"Failed to insert link {source_table}/{source_id} -> {target_table}/{target_id}: {e}")
        return False


def fetch_all(sb, table, select, extra_filter=None):
    """Fetch all rows from a table with pagination."""
    rows = []
    page_size = 1000
    offset = 0
    while True:
        query = sb.table(table).select(select)
        if extra_filter:
            query = extra_filter(query)
        resp = query.range(offset, offset + page_size - 1).execute()
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def link_spotlights_to_predictions(sb, spotlights, predictions):
    """Link spotlights that reference predictions (keyword overlap on thesis/prediction_text)."""
    count = 0
    for s in spotlights:
        s_text = f"{s.get('thesis', '')} {s.get('full_output', '')}"
        if not s_text.strip():
            continue
        for p in predictions:
            p_text = p.get("prediction_text") or ""
            if not p_text:
                continue
            score = keyword_overlap(s_text, p_text, min_overlap=4)
            if score >= 0.15:
                if upsert_link(sb, "spotlight_history", s["id"], "predictions", p["id"],
                               "predicts", confidence=min(score * 3, 1.0)):
                    count += 1
    logger.info(f"  spotlight -> predictions (predicts): {count} links")
    return count


def link_predictions_status_to_spotlights(sb, spotlights, predictions):
    """Link confirmed/refuted predictions back to spotlights covering the same topic."""
    count = 0
    resolved = [p for p in predictions if p.get("status") in ("confirmed", "refuted")]
    for p in resolved:
        p_text = p.get("prediction_text") or ""
        if not p_text:
            continue
        link_type = "confirms" if p["status"] == "confirmed" else "refutes"
        for s in spotlights:
            s_text = f"{s.get('thesis', '')} {s.get('full_output', '')}"
            score = keyword_overlap(s_text, p_text, min_overlap=4)
            if score >= 0.15:
                # Only link spotlights created AFTER the prediction
                s_date = s.get("created_at", "")
                p_date = p.get("created_at", "")
                if s_date > p_date:
                    if upsert_link(sb, "spotlight_history", s["id"], "predictions", p["id"],
                                   link_type, confidence=min(score * 3, 1.0)):
                        count += 1
    logger.info(f"  spotlight -> predictions (confirms/refutes): {count} links")
    return count


def link_topic_evolution_chains(sb, topics):
    """Link topic_evolution rows with the same topic_key chronologically."""
    count = 0
    by_key: dict[str, list] = {}
    for t in topics:
        key = t.get("topic_key", "")
        if key:
            by_key.setdefault(key, []).append(t)

    for key, items in by_key.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda x: x.get("last_updated") or x.get("created_at") or "")
        for i in range(len(items) - 1):
            if upsert_link(sb, "topic_evolution", items[i]["id"], "topic_evolution", items[i + 1]["id"],
                           "updates", confidence=1.0, metadata={"topic_key": key}):
                count += 1
    logger.info(f"  topic_evolution -> topic_evolution (updates): {count} links")
    return count


def link_clusters_to_opportunities(sb, clusters, opportunities):
    """Link problem_clusters to opportunities based on theme/title overlap."""
    count = 0
    for c in clusters:
        c_text = f"{c.get('theme', '')} {c.get('description', '')}"
        if not c_text.strip():
            continue
        for o in opportunities:
            o_text = f"{o.get('title', '')} {o.get('problem_summary', '')} {o.get('proposed_solution', '')}"
            score = keyword_overlap(c_text, o_text, min_overlap=3)
            if score >= 0.12:
                if upsert_link(sb, "problem_clusters", c["id"], "opportunities", o["id"],
                               "derived_from", confidence=min(score * 4, 1.0)):
                    count += 1
    logger.info(f"  problem_clusters -> opportunities (derived_from): {count} links")
    return count


def link_newsletters_to_spotlights(sb, newsletters, spotlights):
    """Link newsletters that reference spotlight theses."""
    count = 0
    for n in newsletters:
        n_text = n.get("content_markdown") or ""
        if not n_text:
            continue
        for s in spotlights:
            thesis = s.get("thesis") or ""
            if not thesis:
                continue
            score = keyword_overlap(n_text, thesis, min_overlap=5)
            if score >= 0.10:
                if upsert_link(sb, "newsletters", n["id"], "spotlight_history", s["id"],
                               "supports", confidence=min(score * 3, 1.0)):
                    count += 1
    logger.info(f"  newsletters -> spotlights (supports): {count} links")
    return count


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
        return

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info("Connected to Supabase")

    # Fetch all relevant data
    logger.info("Fetching data...")
    spotlights = fetch_all(sb, "spotlight_history", "id, thesis, full_output, created_at")
    predictions = fetch_all(sb, "predictions", "id, prediction_text, status, created_at")
    topics = fetch_all(sb, "topic_evolution", "id, topic_key, last_updated, created_at")
    clusters = fetch_all(sb, "problem_clusters", "id, theme, description")
    opportunities = fetch_all(sb, "opportunities", "id, title, problem_summary, proposed_solution")
    newsletters = fetch_all(sb, "newsletters", "id, content_markdown")

    logger.info(f"Loaded: {len(spotlights)} spotlights, {len(predictions)} predictions, "
                f"{len(topics)} topics, {len(clusters)} clusters, "
                f"{len(opportunities)} opportunities, {len(newsletters)} newsletters")

    # Load existing links for deduplication
    load_existing_links(sb)

    # Generate links
    totals = Counter()
    logger.info("\nGenerating content links...")

    totals["predicts"] = link_spotlights_to_predictions(sb, spotlights, predictions)
    totals["confirms/refutes"] = link_predictions_status_to_spotlights(sb, spotlights, predictions)
    totals["updates"] = link_topic_evolution_chains(sb, topics)
    totals["derived_from"] = link_clusters_to_opportunities(sb, clusters, opportunities)
    totals["supports"] = link_newsletters_to_spotlights(sb, newsletters, spotlights)

    total = sum(totals.values())
    logger.info(f"\nDone. Total content links generated: {total}")
    for link_type, count in totals.items():
        logger.info(f"  {link_type}: {count}")


if __name__ == "__main__":
    main()
