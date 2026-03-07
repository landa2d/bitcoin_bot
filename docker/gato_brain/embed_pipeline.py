#!/usr/bin/env python3
"""
Embedding pipeline — embeds AgentPulse content into pgvector via OpenAI text-embedding-3-large.

Usage:
    python embed_pipeline.py                 # incremental (default)
    python embed_pipeline.py --backfill      # process all rows
    python embed_pipeline.py --dry-run       # count rows without calling OpenAI
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import traceback
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
EMBEDDING_DIMENSIONS = 1536  # pgvector HNSW/ivfflat index max is 2000; 1536 is the sweet spot
BATCH_SIZE = 100  # max texts per OpenAI embeddings call

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("embed-pipeline")


def count_tokens(text: str) -> int:
    """Approximate token count for cl100k_base (~4 chars per token)."""
    return len(text) // 4


# ---------------------------------------------------------------------------
# Chunking helpers
# ---------------------------------------------------------------------------

def chunk_by_tokens(text: str, max_tokens: int = 500, overlap: int = 50) -> list[str]:
    """Split text into chunks of ~max_tokens with overlap, using word boundaries."""
    if count_tokens(text) <= max_tokens:
        return [text]

    # Use char-based chunking mapped from token estimate (4 chars ~ 1 token)
    max_chars = max_tokens * 4
    overlap_chars = overlap * 4
    words = text.split()

    chunks = []
    current_chunk: list[str] = []
    current_len = 0

    for word in words:
        word_len = len(word) + 1  # +1 for space
        if current_len + word_len > max_chars and current_chunk:
            chunks.append(' '.join(current_chunk))
            # Keep overlap: walk back ~overlap_chars worth of words
            overlap_words: list[str] = []
            overlap_len = 0
            for w in reversed(current_chunk):
                if overlap_len + len(w) + 1 > overlap_chars:
                    break
                overlap_words.insert(0, w)
                overlap_len += len(w) + 1
            current_chunk = overlap_words
            current_len = overlap_len
        current_chunk.append(word)
        current_len += word_len

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks


def chunk_by_sections(markdown: str) -> list[tuple[str, str]]:
    """Split markdown by ## or ### headers. Returns [(section_name, section_text), ...]."""
    # Split on lines starting with ## or ###
    pattern = r'^(#{2,3})\s+(.+)$'
    lines = markdown.split('\n')

    sections = []
    current_header = "Introduction"
    current_lines = []

    for line in lines:
        match = re.match(pattern, line)
        if match:
            # Save previous section if it has content
            content = '\n'.join(current_lines).strip()
            if content:
                sections.append((current_header, content))
            current_header = match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Save last section
    content = '\n'.join(current_lines).strip()
    if content:
        sections.append((current_header, content))

    return sections


# ---------------------------------------------------------------------------
# Per-table chunking strategies
# ---------------------------------------------------------------------------

def chunks_for_spotlight(row: dict) -> list[dict]:
    """Chunk spotlight_history: full_output by tokens, plus thesis and prediction as standalone."""
    chunks = []
    source_id = row["id"]
    created_at = row.get("created_at")

    # Thesis as standalone chunk (index -1)
    thesis = (row.get("thesis") or "").strip()
    if thesis:
        chunks.append({
            "source_id": source_id,
            "chunk_index": -1,
            "content_text": thesis,
            "metadata": {"field": "thesis", "topic_name": row.get("topic_name", "")},
            "edition_date": created_at,
        })

    # Prediction as standalone chunk (index -2)
    prediction = (row.get("prediction") or "").strip()
    if prediction:
        chunks.append({
            "source_id": source_id,
            "chunk_index": -2,
            "content_text": prediction,
            "metadata": {"field": "prediction", "topic_name": row.get("topic_name", "")},
            "edition_date": created_at,
        })

    # full_output split by tokens
    full_text = (row.get("full_output") or "").strip()
    if full_text:
        text_chunks = chunk_by_tokens(full_text, max_tokens=500, overlap=50)
        for i, chunk_text in enumerate(text_chunks):
            chunks.append({
                "source_id": source_id,
                "chunk_index": i,
                "content_text": chunk_text,
                "metadata": {"field": "full_output", "topic_name": row.get("topic_name", ""), "chunk_of": len(text_chunks)},
                "edition_date": created_at,
            })

    return chunks


def chunks_for_newsletter(row: dict) -> list[dict]:
    """Chunk newsletters: split content_markdown by section headers."""
    chunks = []
    source_id = row["id"]
    created_at = row.get("created_at")
    edition_number = row.get("edition_number")

    content = (row.get("content_markdown") or "").strip()
    if not content:
        return chunks

    sections = chunk_by_sections(content)
    for i, (section_name, section_text) in enumerate(sections):
        if not section_text:
            continue
        chunks.append({
            "source_id": source_id,
            "chunk_index": i,
            "content_text": section_text,
            "metadata": {"section_name": section_name, "edition_number": edition_number},
            "edition_date": created_at,
            "edition_number": edition_number,
        })

    return chunks


def chunks_for_problem(row: dict) -> list[dict]:
    """Single chunk: description + keywords + signal_phrases."""
    description = row.get("description") or ""
    keywords = row.get("keywords") or []
    signal_phrases = row.get("signal_phrases") or []

    parts = [description.strip()]
    if keywords:
        parts.append(f"Keywords: {', '.join(keywords)}")
    if signal_phrases:
        parts.append(f"Signal phrases: {', '.join(signal_phrases)}")

    text = ". ".join(p for p in parts if p)
    if not text:
        return []

    return [{
        "source_id": row["id"],
        "chunk_index": 0,
        "content_text": text,
        "metadata": {"category": row.get("category", "")},
        "edition_date": row.get("first_seen") or row.get("last_seen"),
    }]


def chunks_for_opportunity(row: dict) -> list[dict]:
    """Single chunk: title + proposed_solution + business_model + pitch_brief."""
    parts = [
        (row.get("title") or "").strip(),
        (row.get("proposed_solution") or "").strip(),
    ]
    bm = (row.get("business_model") or "").strip()
    if bm:
        parts.append(f"Business model: {bm}")
    pb = (row.get("pitch_brief") or "").strip()
    if pb:
        parts.append(pb)

    text = ". ".join(p for p in parts if p)
    if not text:
        return []

    return [{
        "source_id": row["id"],
        "chunk_index": 0,
        "content_text": text,
        "metadata": {"status": row.get("status", ""), "confidence_score": row.get("confidence_score")},
        "edition_date": row.get("created_at"),
    }]


def chunks_for_prediction(row: dict) -> list[dict]:
    """Single chunk: prediction_text."""
    text = (row.get("prediction_text") or "").strip()
    if not text:
        return []

    return [{
        "source_id": row["id"],
        "chunk_index": 0,
        "content_text": text,
        "metadata": {"status": row.get("status", ""), "topic_id": row.get("topic_id", "")},
        "edition_date": row.get("created_at"),
    }]


def chunks_for_topic_evolution(row: dict) -> list[dict]:
    """Single chunk: thesis + current_stage."""
    thesis = (row.get("thesis") or "").strip()
    stage = (row.get("current_stage") or "").strip()

    parts = []
    if thesis:
        parts.append(thesis)
    if stage:
        parts.append(f"Current stage: {stage}")

    text = ". ".join(parts)
    if not text:
        return []

    return [{
        "source_id": row["id"],
        "chunk_index": 0,
        "content_text": text,
        "metadata": {"topic_key": row.get("topic_key", ""), "current_stage": stage},
        "edition_date": row.get("created_at"),
    }]


def chunks_for_source_post(row: dict) -> list[dict]:
    """Single chunk: title + body (only tier >= 2)."""
    title = (row.get("title") or "").strip()
    body = (row.get("body") or "").strip()

    parts = [p for p in [title, body] if p]
    text = ". ".join(parts)
    if not text:
        return []

    return [{
        "source_id": row["id"],
        "chunk_index": 0,
        "content_text": text,
        "metadata": {"source": row.get("source", ""), "source_tier": row.get("source_tier")},
        "edition_date": row.get("created_at"),
    }]


# ---------------------------------------------------------------------------
# Table configs
# ---------------------------------------------------------------------------

TABLE_CONFIGS = [
    {
        "table": "spotlight_history",
        "select": "id, topic_name, thesis, prediction, full_output, created_at",
        "chunker": chunks_for_spotlight,
    },
    {
        "table": "newsletters",
        "select": "id, edition_number, content_markdown, created_at",
        "chunker": chunks_for_newsletter,
    },
    {
        "table": "problems",
        "select": "id, description, category, keywords, signal_phrases, first_seen, last_seen",
        "chunker": chunks_for_problem,
    },
    {
        "table": "opportunities",
        "select": "id, title, proposed_solution, business_model, pitch_brief, status, confidence_score, created_at",
        "chunker": chunks_for_opportunity,
    },
    {
        "table": "predictions",
        "select": "id, prediction_text, status, topic_id, created_at",
        "chunker": chunks_for_prediction,
    },
    {
        "table": "topic_evolution",
        "select": "id, topic_key, thesis, current_stage, created_at",
        "chunker": chunks_for_topic_evolution,
    },
    {
        "table": "source_posts",
        "select": "id, title, body, source, source_tier, created_at",
        "chunker": chunks_for_source_post,
        "filter": lambda q: q.gte("source_tier", 2),
    },
]


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def get_existing_ids(supabase: Client, table_name: str) -> set[tuple[str, int]]:
    """Return set of (source_id, chunk_index) already embedded for a table."""
    existing = set()
    page_size = 1000
    offset = 0
    while True:
        resp = (
            supabase.table("embeddings")
            .select("source_id, chunk_index")
            .eq("source_table", table_name)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = resp.data or []
        for r in rows:
            existing.add((r["source_id"], r["chunk_index"]))
        if len(rows) < page_size:
            break
        offset += page_size
    logger.info(f"  get_existing_ids({table_name}): {len(existing)} already embedded")
    return existing


def get_embedded_source_ids(supabase: Client, table_name: str) -> set[str]:
    """Return set of source_ids that have at least one embedding."""
    ids = set()
    page_size = 1000
    offset = 0
    while True:
        resp = (
            supabase.table("embeddings")
            .select("source_id")
            .eq("source_table", table_name)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = resp.data or []
        for r in rows:
            ids.add(r["source_id"])
        if len(rows) < page_size:
            break
        offset += page_size
    return ids


def fetch_rows(supabase: Client, config: dict, backfill: bool) -> list[dict]:
    """Fetch rows from source table, optionally filtering already-embedded ones."""
    table_name = config["table"]
    select_cols = config["select"]

    query = supabase.table(table_name).select(select_cols)

    # Apply table-specific filter (e.g., source_tier >= 2)
    if "filter" in config:
        query = config["filter"](query)

    if not backfill:
        # Get source_ids already embedded and exclude them
        embedded_ids = get_embedded_source_ids(supabase, table_name)
        if embedded_ids:
            # Supabase-py: fetch all and filter client-side for NOT IN
            # (supabase-py doesn't support .not_.in_() well on uuid arrays)
            all_rows = []
            page_size = 1000
            offset = 0
            while True:
                resp = query.range(offset, offset + page_size - 1).execute()
                rows = resp.data or []
                all_rows.extend(rows)
                if len(rows) < page_size:
                    break
                offset += page_size
            return [r for r in all_rows if r["id"] not in embedded_ids]

    # Fetch all (backfill or no existing embeddings)
    all_rows = []
    page_size = 1000
    offset = 0
    while True:
        resp = query.range(offset, offset + page_size - 1).execute()
        rows = resp.data or []
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return all_rows


def embed_texts(openai_client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API in batches of BATCH_SIZE."""
    all_embeddings = []
    total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        logger.info(f"  OpenAI batch {batch_num}/{total_batches}: {len(batch)} texts")
        t0 = time.time()
        resp = openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        elapsed = time.time() - t0
        logger.info(f"  OpenAI batch {batch_num} done in {elapsed:.1f}s, got {len(resp.data)} embeddings (dim={len(resp.data[0].embedding)})")
        all_embeddings.extend([d.embedding for d in resp.data])
    return all_embeddings


def insert_embeddings(supabase: Client, records: list[dict]) -> int:
    """Insert embedding records into Supabase. Returns count inserted."""
    inserted = 0
    batch_size = 50
    total_batches = (len(records) + batch_size - 1) // batch_size
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        batch_num = i // batch_size + 1
        rows = []
        for rec in batch:
            row = {
                "source_table": rec["source_table"],
                "source_id": rec["source_id"],
                "chunk_index": rec["chunk_index"],
                "content_text": rec["content_text"],
                "embedding": rec["embedding"],
                "metadata": rec.get("metadata", {}),
            }
            if rec.get("edition_date"):
                ed = rec["edition_date"]
                if isinstance(ed, str) and "T" in ed:
                    row["edition_date"] = ed[:10]
                else:
                    row["edition_date"] = str(ed)[:10] if ed else None
            if rec.get("edition_number") is not None:
                row["edition_number"] = rec["edition_number"]
            rows.append(row)

        logger.info(f"  Inserting batch {batch_num}/{total_batches}: {len(rows)} rows")
        t0 = time.time()
        try:
            resp = supabase.table("embeddings").upsert(
                rows, on_conflict="source_table,source_id,chunk_index"
            ).execute()
            elapsed = time.time() - t0
            batch_inserted = len(resp.data) if resp.data else 0
            logger.info(f"  Insert batch {batch_num} done in {elapsed:.1f}s: {batch_inserted} rows returned")
            if batch_inserted == 0:
                logger.warning(f"  Insert returned 0 rows! resp.data={resp.data!r}")
            inserted += batch_inserted
        except Exception as e:
            elapsed = time.time() - t0
            logger.error(f"  Insert batch {batch_num} FAILED after {elapsed:.1f}s: {e}")
            logger.error(traceback.format_exc())
            # Log a sample row (without the full embedding vector)
            sample = {k: v for k, v in rows[0].items() if k != "embedding"}
            sample["embedding_len"] = len(rows[0].get("embedding", []))
            logger.error(f"  Sample row (no embedding): {json.dumps(sample, default=str)}")
            raise

    return inserted


def process_table(
    supabase: Client,
    openai_client: OpenAI | None,
    config: dict,
    backfill: bool,
    dry_run: bool,
) -> int:
    """Process one table: fetch, chunk, embed, insert. Returns chunk count."""
    table_name = config["table"]
    chunker = config["chunker"]

    logger.info(f"{'='*60}")
    logger.info(f"Processing table: {table_name}")

    try:
        t0 = time.time()
        rows = fetch_rows(supabase, config, backfill)
        logger.info(f"  Fetched {len(rows)} rows from {table_name} in {time.time()-t0:.1f}s")
        if rows:
            logger.info(f"  Sample row keys: {list(rows[0].keys())}")
            logger.info(f"  Sample row id: {rows[0].get('id')}")
    except Exception as e:
        logger.error(f"Failed to fetch rows from {table_name}: {e}")
        logger.error(traceback.format_exc())
        return 0

    if not rows:
        logger.info(f"{table_name}: 0 rows to process")
        return 0

    # Generate chunks
    all_chunks = []
    existing = set()
    if backfill:
        existing = get_existing_ids(supabase, table_name)

    chunk_errors = 0
    skipped_existing = 0
    for row in rows:
        try:
            chunks = chunker(row)
        except Exception as e:
            chunk_errors += 1
            logger.warning(f"Chunking failed for {table_name} row {row.get('id')}: {e}")
            logger.warning(traceback.format_exc())
            continue

        for chunk in chunks:
            key = (chunk["source_id"], chunk["chunk_index"])
            if backfill and key in existing:
                skipped_existing += 1
                continue
            chunk["source_table"] = table_name
            all_chunks.append(chunk)

    logger.info(f"  Chunking done: {len(all_chunks)} new chunks, {skipped_existing} skipped (existing), {chunk_errors} errors")

    if not all_chunks:
        logger.info(f"{table_name}: 0 new chunks to embed")
        return 0

    # Sanity check: print first chunk
    first = all_chunks[0]
    logger.info(f"  First chunk: source_id={first['source_id']}, idx={first['chunk_index']}, "
                f"text={first['content_text'][:100]!r}...")

    total_tokens = sum(count_tokens(c["content_text"]) for c in all_chunks)

    if dry_run:
        logger.info(
            f"{table_name}: {len(rows)} rows -> {len(all_chunks)} chunks "
            f"({total_tokens:,} tokens) [DRY RUN]"
        )
        return len(all_chunks)

    logger.info(
        f"{table_name}: embedding {len(all_chunks)} chunks ({total_tokens:,} tokens)..."
    )

    # Embed
    texts = [c["content_text"] for c in all_chunks]
    try:
        embeddings = embed_texts(openai_client, texts)
        logger.info(f"  Got {len(embeddings)} embeddings total")
    except Exception as e:
        logger.error(f"OpenAI embedding failed for {table_name}: {e}")
        logger.error(traceback.format_exc())
        return 0

    # Attach embeddings to records
    for chunk, emb in zip(all_chunks, embeddings):
        chunk["embedding"] = emb

    # Insert
    try:
        inserted = insert_embeddings(supabase, all_chunks)
        logger.info(f"  RESULT: Embedded {inserted} chunks from {table_name}")
    except Exception as e:
        logger.error(f"Insert failed for {table_name}: {e}")
        logger.error(traceback.format_exc())
        return 0

    return len(all_chunks)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="AgentPulse embedding pipeline")
    parser.add_argument("--backfill", action="store_true", help="Process all rows (initial setup)")
    parser.add_argument("--incremental", action="store_true", help="Only new rows (default)")
    parser.add_argument("--dry-run", action="store_true", help="Count chunks without calling OpenAI")
    args = parser.parse_args()

    backfill = args.backfill
    dry_run = args.dry_run

    # Init Supabase
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
        sys.exit(1)

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    logger.info(f"Supabase client initialized (URL={SUPABASE_URL[:40]}...)")

    # Verify connection: count embeddings table
    try:
        test = supabase.table("embeddings").select("id", count="exact").limit(1).execute()
        logger.info(f"Supabase connection OK. Embeddings table current count: {test.count}")
    except Exception as e:
        logger.error(f"Supabase connection test FAILED: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

    # Init OpenAI (skip for dry run)
    openai_client = None
    if not dry_run:
        if not OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY not set")
            sys.exit(1)
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info(f"OpenAI client initialized (key=...{OPENAI_API_KEY[-4:]})")

        # Verify OpenAI with a tiny test embedding
        try:
            t0 = time.time()
            test_resp = openai_client.embeddings.create(
                model=EMBEDDING_MODEL, input=["test"], dimensions=EMBEDDING_DIMENSIONS
            )
            logger.info(f"OpenAI test OK in {time.time()-t0:.1f}s: dim={len(test_resp.data[0].embedding)}")
        except Exception as e:
            logger.error(f"OpenAI test embedding FAILED: {e}")
            logger.error(traceback.format_exc())
            sys.exit(1)

    # Process each table
    mode = "BACKFILL" if backfill else "INCREMENTAL"
    logger.info(f"Starting embedding pipeline ({mode}{'  DRY RUN' if dry_run else ''})")

    total_chunks = 0
    for config in TABLE_CONFIGS:
        try:
            count = process_table(supabase, openai_client, config, backfill, dry_run)
            total_chunks += count
        except Exception as e:
            logger.error(f"Table {config['table']} failed: {e}")
            continue

    logger.info(f"Done. Total: {total_chunks} chunks {'would be ' if dry_run else ''}embedded.")


if __name__ == "__main__":
    main()
