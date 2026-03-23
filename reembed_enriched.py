#!/usr/bin/env python3
"""
AgentPulse Re-Embedder
======================
Re-embeds enriched source_posts content after full-text extraction.
Also cleans HTML from existing embeddings and removes junk vectors.

Usage:
    python reembed_enriched.py --limit 100
    python reembed_enriched.py --dry-run
    python reembed_enriched.py --clean-html-only
    python reembed_enriched.py --purge-junk

Requires env vars:
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    OPENAI_API_KEY

Install deps:
    pip install supabase openai requests --break-system-packages
"""

import argparse
import os
import re
import sys
import time
import logging
from datetime import datetime, timezone

try:
    from supabase import create_client
except ImportError:
    print("ERROR: supabase not installed. Run: pip install supabase --break-system-packages")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("ERROR: openai not installed. Run: pip install openai --break-system-packages")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSIONS = 1536
CHUNK_SIZE = 1000  # chars per chunk target
CHUNK_OVERLAP = 200  # chars overlap between chunks
MIN_CHUNK_LENGTH = 100  # don't embed chunks shorter than this
DELAY_BETWEEN_EMBEDS = 0.5  # seconds — to stay under rate limits

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("reembedder")

# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------
TAG_RE = re.compile(r"<[^>]+>")
MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
MULTI_SPACE_RE = re.compile(r" {2,}")

def strip_html(text: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    text = TAG_RE.sub("", text)
    text = MULTI_NEWLINE_RE.sub("\n\n", text)
    text = MULTI_SPACE_RE.sub(" ", text)
    return text.strip()

def has_html(text: str) -> bool:
    """Check if text contains HTML tags."""
    return bool(TAG_RE.search(text))

# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
def chunk_text(text: str) -> list[str]:
    """
    Split text into chunks of ~CHUNK_SIZE chars with CHUNK_OVERLAP overlap.
    Tries to split at paragraph or sentence boundaries.
    """
    if len(text) <= CHUNK_SIZE + CHUNK_OVERLAP:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + CHUNK_SIZE

        if end >= len(text):
            # Last chunk — take everything remaining
            chunk = text[start:]
            if len(chunk) >= MIN_CHUNK_LENGTH or not chunks:
                chunks.append(chunk)
            break

        # Try to find a good break point
        segment = text[start:end + 200]  # look a bit ahead

        # Priority 1: paragraph break (\n\n)
        para_break = segment.rfind("\n\n", CHUNK_SIZE - 200, len(segment))
        if para_break > 0:
            end = start + para_break + 2  # include the newlines

        # Priority 2: sentence break (. or ! or ?)
        elif (sent_break := max(
            segment.rfind(". ", CHUNK_SIZE - 200, len(segment)),
            segment.rfind("! ", CHUNK_SIZE - 200, len(segment)),
            segment.rfind("? ", CHUNK_SIZE - 200, len(segment)),
        )) > 0:
            end = start + sent_break + 2

        # Priority 3: just cut at CHUNK_SIZE
        else:
            end = start + CHUNK_SIZE

        chunk = text[start:end].strip()
        if len(chunk) >= MIN_CHUNK_LENGTH:
            chunks.append(chunk)

        # Move start forward with overlap
        start = end - CHUNK_OVERLAP if end - CHUNK_OVERLAP > start else end

    return chunks

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
def generate_embedding(client: OpenAI, text: str) -> list[float] | None:
    """Generate an embedding vector for a piece of text."""
    try:
        response = client.embeddings.create(
            input=text,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
        )
        return response.data[0].embedding
    except Exception as e:
        log.error(f"  Embedding API error: {e}")
        return None

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def reembed_enriched(sb, openai_client, limit: int, dry_run: bool):
    """Re-embed posts that have been enriched with full text."""
    log.info("=" * 60)
    log.info("RE-EMBEDDING ENRICHED POSTS")
    log.info("=" * 60)

    # Find enriched posts that need re-embedding
    result = (
        sb.table("source_posts")
        .select("id, source, title, body, content_depth")
        .eq("content_depth", "full")
        .not_.is_("enriched_at", "null")
        .limit(limit)
        .execute()
    )
    posts = result.data if result.data else []

    if not posts:
        log.info("No enriched posts found to re-embed.")
        return

    log.info(f"Found {len(posts)} enriched posts to re-embed")

    stats = {"embedded": 0, "chunks_created": 0, "failed": 0, "skipped": 0}

    for i, post in enumerate(posts, 1):
        post_id = post["id"]
        title = post.get("title", "")[:80]
        body = post.get("body", "") or ""

        log.info(f"[{i}/{len(posts)}] {title} ({len(body)} chars)")

        # Clean HTML from body
        clean_body = strip_html(body)
        if len(clean_body) < MIN_CHUNK_LENGTH:
            log.warning(f"  SKIPPED — body too short after cleaning ({len(clean_body)} chars)")
            stats["skipped"] += 1
            continue

        # Chunk the text
        chunks = chunk_text(clean_body)
        log.info(f"  {len(chunks)} chunk(s) to embed")

        if dry_run:
            for j, chunk in enumerate(chunks):
                log.info(f"  Chunk {j}: {len(chunk)} chars — {chunk[:100]}...")
            stats["skipped"] += 1
            continue

        # Delete existing embeddings for this post
        try:
            sb.table("embeddings").delete().eq(
                "source_table", "source_posts"
            ).eq("source_id", post_id).execute()
        except Exception as e:
            log.error(f"  Failed to delete old embeddings: {e}")
            stats["failed"] += 1
            continue

        # Embed each chunk
        all_ok = True
        for chunk_idx, chunk in enumerate(chunks):
            embedding = generate_embedding(openai_client, chunk)
            if embedding is None:
                all_ok = False
                break

            try:
                sb.table("embeddings").insert({
                    "source_table": "source_posts",
                    "source_id": post_id,
                    "chunk_index": chunk_idx,
                    "content_text": chunk,
                    "embedding": embedding,
                    "metadata": {
                        "source": post.get("source"),
                        "title": post.get("title"),
                        "enriched": True,
                        "reembedded_at": datetime.now(timezone.utc).isoformat(),
                    },
                }).execute()
                stats["chunks_created"] += 1
            except Exception as e:
                log.error(f"  Failed to insert chunk {chunk_idx}: {e}")
                all_ok = False
                break

            time.sleep(DELAY_BETWEEN_EMBEDS)

        if all_ok:
            stats["embedded"] += 1
            log.info(f"  OK — {len(chunks)} chunks embedded")
        else:
            stats["failed"] += 1
            log.error(f"  FAILED — partial embedding")

    log.info(f"\nDone: {stats['embedded']} posts, {stats['chunks_created']} chunks created, "
             f"{stats['failed']} failed, {stats['skipped']} skipped")


def clean_html_embeddings(sb, openai_client, dry_run: bool):
    """Find and re-embed existing embeddings that contain HTML tags."""
    log.info("=" * 60)
    log.info("CLEANING HTML FROM EXISTING EMBEDDINGS")
    log.info("=" * 60)

    # Find embeddings with HTML
    result = (
        sb.table("embeddings")
        .select("id, source_table, source_id, chunk_index, content_text")
        .eq("source_table", "source_posts")
        .like("content_text", "%<%>%")
        .limit(500)
        .execute()
    )
    rows = result.data if result.data else []

    # Filter to only those that actually have HTML
    html_rows = [r for r in rows if has_html(r.get("content_text", ""))]

    if not html_rows:
        log.info("No embeddings with HTML found.")
        return

    log.info(f"Found {len(html_rows)} embeddings with HTML to clean")

    stats = {"cleaned": 0, "failed": 0, "deleted_too_short": 0}

    for i, row in enumerate(html_rows, 1):
        emb_id = row["id"]
        old_text = row["content_text"]
        clean = strip_html(old_text)

        log.info(f"[{i}/{len(html_rows)}] {len(old_text)} -> {len(clean)} chars")

        if dry_run:
            log.info(f"  Before: {old_text[:100]}...")
            log.info(f"  After:  {clean[:100]}...")
            continue

        if len(clean) < MIN_CHUNK_LENGTH:
            # Too short after cleaning — delete the embedding
            try:
                sb.table("embeddings").delete().eq("id", emb_id).execute()
                stats["deleted_too_short"] += 1
                log.info(f"  DELETED — too short after cleaning ({len(clean)} chars)")
            except Exception as e:
                log.error(f"  Delete failed: {e}")
                stats["failed"] += 1
            continue

        # Re-embed with clean text
        embedding = generate_embedding(openai_client, clean)
        if embedding is None:
            stats["failed"] += 1
            continue

        try:
            sb.table("embeddings").update({
                "content_text": clean,
                "embedding": embedding,
            }).eq("id", emb_id).execute()
            stats["cleaned"] += 1
        except Exception as e:
            log.error(f"  Update failed: {e}")
            stats["failed"] += 1

        time.sleep(DELAY_BETWEEN_EMBEDS)

    log.info(f"\nDone: {stats['cleaned']} cleaned, {stats['deleted_too_short']} deleted (too short), "
             f"{stats['failed']} failed")


def purge_junk_embeddings(sb, dry_run: bool):
    """Remove useless embeddings (topic_evolution, very short chunks)."""
    log.info("=" * 60)
    log.info("PURGING JUNK EMBEDDINGS")
    log.info("=" * 60)

    # 1. Delete topic_evolution embeddings (avg 24 chars — useless)
    result = (
        sb.table("embeddings")
        .select("id", count="exact")
        .eq("source_table", "topic_evolution")
        .execute()
    )
    te_count = result.count or 0
    log.info(f"topic_evolution embeddings to delete: {te_count}")

    if not dry_run and te_count > 0:
        try:
            sb.table("embeddings").delete().eq("source_table", "topic_evolution").execute()
            log.info(f"  Deleted {te_count} topic_evolution embeddings")
        except Exception as e:
            log.error(f"  Delete failed: {e}")

    # 2. Count other very short embeddings (informational only)
    for source_table in ["source_posts", "newsletters", "spotlight_history", "predictions"]:
        result = sb.rpc("", {}).execute()  # Can't easily filter by length in supabase-py
        # Just log for awareness
    log.info("Consider also reviewing short embeddings in newsletters and spotlight_history")
    log.info("Done.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Re-embed enriched source_posts content")
    parser.add_argument("--limit", type=int, default=100, help="Max posts to re-embed (default: 100)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen, don't change DB")
    parser.add_argument("--clean-html-only", action="store_true", help="Only clean HTML from existing embeddings")
    parser.add_argument("--purge-junk", action="store_true", help="Remove useless embeddings")
    args = parser.parse_args()

    # Connect
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not supabase_url or not supabase_key:
        log.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars")
        sys.exit(1)

    sb = create_client(supabase_url, supabase_key)
    openai_client = None

    if not args.purge_junk:
        if not openai_key:
            log.error("Set OPENAI_API_KEY env var")
            sys.exit(1)
        openai_client = OpenAI(api_key=openai_key)

    # Dispatch
    if args.purge_junk:
        purge_junk_embeddings(sb, args.dry_run)
    elif args.clean_html_only:
        clean_html_embeddings(sb, openai_client, args.dry_run)
    else:
        reembed_enriched(sb, openai_client, args.limit, args.dry_run)

    log.info("All done.")


if __name__ == "__main__":
    main()
