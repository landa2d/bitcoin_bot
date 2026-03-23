#!/usr/bin/env python3
"""
AgentPulse Full-Text Enricher
Usage:
    python3 full_text_enricher.py --limit 50
    python3 full_text_enricher.py --limit 20 --source rss_coindesk
    python3 full_text_enricher.py --dry-run

Requires env vars: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Install: pip install trafilatura requests --break-system-packages
"""

import argparse
import os
import re
import sys
import time
import logging
from datetime import datetime, timezone
import requests

try:
    import trafilatura
except ImportError:
    print("ERROR: pip install trafilatura --break-system-packages")
    sys.exit(1)

USER_AGENT = "AgentPulse/1.0 (newsletter enrichment bot)"
REQUEST_TIMEOUT = 20
DELAY_BETWEEN_REQUESTS = 2
MIN_USEFUL_LENGTH = 100

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("enricher")

TAG_RE = re.compile(r"<[^>]+>")
MULTI_NL = re.compile(r"\n{3,}")
MULTI_SP = re.compile(r" {2,}")
BOILERPLATE = [
    re.compile(r"Subscribe to [\w\s]+newsletter", re.I),
    re.compile(r"Share this article", re.I),
    re.compile(r"Sign up for [\w\s]+", re.I),
    re.compile(r"This (website|site) uses cookies", re.I),
    re.compile(r"Accept (all )?cookies", re.I),
    re.compile(r"Follow us on (Twitter|X|Facebook|Instagram)", re.I),
    re.compile(r"©\s*\d{4}.*$", re.I | re.M),
]

def classify_depth(length):
    if length < 10: return "empty"
    if length < 200: return "snippet"
    if length < 1000: return "partial"
    return "full"

def clean_text(raw):
    text = TAG_RE.sub("", raw)
    for p in BOILERPLATE:
        text = p.sub("", text)
    text = MULTI_NL.sub("\n\n", text)
    text = MULTI_SP.sub(" ", text)
    return text.strip()

def fetch_github_readme(url):
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/?", url)
    if not match:
        return None
    owner, repo = match.group(1), match.group(2)
    for branch in ["main", "master", "HEAD"]:
        try:
            resp = requests.get(
                f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md",
                timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}
            )
            if resp.status_code == 200 and len(resp.text) > MIN_USEFUL_LENGTH:
                return resp.text
        except requests.RequestException:
            continue
    return None

def extract_full_text(url, source):
    if "github.com" in url and source == "github":
        text = fetch_github_readme(url)
        if text:
            return clean_text(text), "github_readme"

    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
                favor_precision=False,
            )
            if text and len(text) > MIN_USEFUL_LENGTH:
                return clean_text(text), "trafilatura"
    except Exception as e:
        log.warning(f"  trafilatura failed: {e}")

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
        if resp.status_code == 200:
            text = clean_text(resp.text)
            if len(text) > MIN_USEFUL_LENGTH:
                return text[:50000], "html_fallback"
    except requests.RequestException as e:
        log.warning(f"  fallback failed: {e}")

    return None, "failed"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--source", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-improvement", type=int, default=200)
    args = parser.parse_args()

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        log.error("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars")
        sys.exit(1)

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }

    params = {
        "select": "id,source,source_url,title,body,content_depth",
        "content_depth": "in.(empty,snippet,partial)",
        "source_url": "not.is.null",
        "enriched_at": "is.null",
        "order": "content_depth.asc",
        "limit": str(args.limit),
    }
    if args.source:
        params["source"] = f"eq.{args.source}"

    resp = requests.get(f"{supabase_url}/rest/v1/source_posts", headers=headers, params=params)
    resp.raise_for_status()
    posts = resp.json()

    if not posts:
        log.info("No posts found to enrich. All caught up!")
        return

    log.info(f"Found {len(posts)} posts to enrich" + (f" (source: {args.source})" if args.source else ""))
    if args.dry_run:
        log.info("DRY RUN — no updates")

    stats = {"enriched": 0, "failed": 0, "skipped": 0, "by_method": {}}

    for i, post in enumerate(posts, 1):
        post_id = post["id"]
        source = post["source"]
        url = post["source_url"]
        title = (post.get("title") or "")[:80]
        current_body_len = len(post.get("body") or "")

        log.info(f"[{i}/{len(posts)}] {source} | {title}")
        log.info(f"  URL: {url}")
        log.info(f"  Current: {current_body_len} chars ({post['content_depth']})")

        if args.dry_run:
            stats["skipped"] += 1
            continue

        text, method = extract_full_text(url, source)

        if text is None:
            log.warning(f"  FAILED — no text extracted")
            stats["failed"] += 1
            time.sleep(DELAY_BETWEEN_REQUESTS)
            continue

        new_len = len(text)
        improvement = new_len - current_body_len

        if improvement < args.min_improvement and current_body_len > 0:
            log.info(f"  SKIPPED — {new_len} chars via {method}, only +{improvement}")
            stats["skipped"] += 1
            time.sleep(DELAY_BETWEEN_REQUESTS)
            continue

        new_depth = classify_depth(new_len)
        log.info(f"  ENRICHED — {current_body_len} -> {new_len} chars via {method} ({new_depth})")

        try:
            requests.patch(
                f"{supabase_url}/rest/v1/source_posts",
                headers={**headers, "Prefer": "return=minimal"},
                params={"id": f"eq.{post_id}"},
                json={
                    "body": text,
                    "content_depth": new_depth,
                    "enriched_at": datetime.now(timezone.utc).isoformat(),
                },
            ).raise_for_status()
            stats["enriched"] += 1
            stats["by_method"][method] = stats["by_method"].get(method, 0) + 1
        except Exception as e:
            log.error(f"  DB update failed: {e}")
            stats["failed"] += 1

        time.sleep(DELAY_BETWEEN_REQUESTS)

    log.info("=" * 50)
    log.info(f"DONE — Enriched: {stats['enriched']}, Failed: {stats['failed']}, Skipped: {stats['skipped']}")
    if stats["by_method"]:
        log.info(f"Methods: {stats['by_method']}")

if __name__ == "__main__":
    main()
