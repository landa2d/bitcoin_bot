#!/usr/bin/env python3
"""
One-shot backfill: generate Impact Mode versions for all existing newsletters.

Run inside the processor container:
    docker compose exec processor python3 /scripts/backfill_impact.py

Or with --dry-run to preview what would be processed:
    docker compose exec processor python3 /scripts/backfill_impact.py --dry-run
"""

import json
import os
import re
import sys
import time

from openai import OpenAI
from supabase import create_client

# ── Config ──────────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

MODEL = os.getenv("BACKFILL_MODEL", "deepseek-chat")

# ── Impact Mode rewrite prompt ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are rewriting an AI/agent economy newsletter from "Builder Mode" (technical) into "Impact Mode" (accessible to non-technical readers).

You are NOT dumbing things down. You are translating implications.

The reader is smart but not technical. They might be:
- A product manager worried about their job
- An investor trying to understand portfolio risk
- A policymaker trying to write regulation
- A parent trying to advise their college-age kid on career choices

Rules:
- Replace jargon with consequences: "MCP adoption" → "a new standard that lets AI access your tools directly"
- Every insight must answer "what does this mean for ME?"
- Lead with the human impact, then explain the technical mechanism
- Use analogies from domains the reader already understands
- Include specific actions: "If you work in X, here's what to do"
- Keep the same section structure (## headings) but rewrite section titles in plain language
- Gato's Corner stays IDENTICAL — do not change it at all
- Keep roughly the same length (±15%)

Voice references:
- Kara Swisher explaining tech to a business audience
- The Economist making complex topics accessible without condescension
- Morgan Housel connecting financial concepts to human behavior

Output ONLY the rewritten markdown. No preamble, no explanation, no fences."""

TITLE_PROMPT = """Rewrite this technical newsletter title for a non-technical audience.
The reader cares about jobs, money, careers, and what AI means for their life — not frameworks or tools.

Original title: "{title}"

Rules:
- Make it about human/economic impact, not technology
- Keep it punchy (under 12 words)
- No jargon

Output ONLY the new title, nothing else."""


def main():
    dry_run = "--dry-run" in sys.argv

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_KEY not set")
        sys.exit(1)
    if not dry_run and not OPENAI_API_KEY and not DEEPSEEK_API_KEY:
        print("ERROR: Need OPENAI_API_KEY or DEEPSEEK_API_KEY for LLM calls")
        sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Set up LLM client
    if DEEPSEEK_API_KEY and "deepseek" in MODEL.lower():
        llm = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        print(f"Using DeepSeek ({MODEL})")
    elif OPENAI_API_KEY:
        llm = OpenAI(api_key=OPENAI_API_KEY)
        print(f"Using OpenAI ({MODEL})")
    else:
        llm = None

    # Fetch newsletters missing impact content
    result = sb.table("newsletters") \
        .select("id, edition_number, title, content_markdown, title_impact, content_markdown_impact") \
        .order("edition_number", desc=False) \
        .execute()

    newsletters = [
        n for n in (result.data or [])
        if n.get("content_markdown")
        and not n.get("content_markdown_impact")
    ]

    if not newsletters:
        print("All newsletters already have impact versions. Nothing to do.")
        return

    print(f"Found {len(newsletters)} newsletter(s) to backfill:\n")
    for n in newsletters:
        print(f"  Edition #{n['edition_number']}: {n['title']}")

    if dry_run:
        print("\n--dry-run: no changes made.")
        return

    print()

    for n in newsletters:
        edition = n["edition_number"]
        title = n["title"]
        content = n["content_markdown"]
        print(f"── Edition #{edition}: {title}")

        # Generate impact title
        print("   Generating impact title...", end=" ", flush=True)
        t0 = time.time()
        title_resp = llm.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": TITLE_PROMPT.format(title=title)}],
            max_tokens=100,
            temperature=0.7,
        )
        impact_title = title_resp.choices[0].message.content.strip().strip('"')
        elapsed = time.time() - t0
        print(f"done ({elapsed:.1f}s) → \"{impact_title}\"")

        # Generate impact content
        print("   Generating impact content...", end=" ", flush=True)
        t0 = time.time()
        content_resp = llm.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            max_tokens=8192,
            temperature=0.7,
        )
        impact_content = content_resp.choices[0].message.content.strip()
        # Strip markdown fences if LLM wrapped output
        if impact_content.startswith("```"):
            impact_content = re.sub(r"^```(?:markdown)?\s*", "", impact_content)
            impact_content = re.sub(r"\s*```$", "", impact_content)
        elapsed = time.time() - t0
        tokens = content_resp.usage.total_tokens if content_resp.usage else 0
        print(f"done ({elapsed:.1f}s, {tokens} tokens, {len(impact_content)} chars)")

        # Update database
        print("   Saving to Supabase...", end=" ", flush=True)
        sb.table("newsletters").update({
            "title_impact": impact_title,
            "content_markdown_impact": impact_content,
        }).eq("id", n["id"]).execute()
        print("done")

        print()
        # Small delay to avoid rate limits
        time.sleep(1)

    print(f"Backfill complete: {len(newsletters)} edition(s) updated.")


if __name__ == "__main__":
    main()
