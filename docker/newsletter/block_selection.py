"""Phase A: Block selection for newsletter generation.

Selects 25-35 verified building blocks from the extraction pool for an
edition window. Blocks include anchorable extractions, tool stats,
predictions, and quotes.

Output is the block list that Phase B+C consume. Ships standalone for
inspection before integration.
"""

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger('block_selection')

# 7 core categories for diversity fill
CORE_CATEGORIES = ['payments', 'security', 'infrastructure', 'tools',
                   'research', 'regulation', 'commerce']


def _source_cap(tier: int) -> int:
    """Per-source cap: 5 for tier 1, 3 for tier 2-3."""
    return 5 if tier == 1 else 3


def select_blocks(
    supabase_client,
    window_start: str | None = None,
    window_end: str | None = None,
    prepass_angle: str | None = None,
    llm_client=None,
) -> dict[str, Any]:
    """Select 25-35 verified building blocks from the extraction pool.

    Args:
        supabase_client: Supabase client instance
        window_start: ISO timestamp for window start (default: NOW - 7 days)
        window_end: ISO timestamp for window end (default: NOW)
        prepass_angle: Editorial angle from prepass (used for LLM-aligned selection)
        llm_client: OpenAI-compatible client for DeepSeek (optional; skips LLM step if None)

    Returns:
        Block list dict with blocks, tool_stats, predictions, and summary.
    """
    sb = supabase_client
    now = datetime.now(timezone.utc)

    if not window_start:
        window_start = (now - timedelta(days=7)).isoformat()
    if not window_end:
        window_end = now.isoformat()

    # ══════════════════════════════════════════════════════════════
    # Step 1: Query all anchorable extractions in the window
    # ══════════════════════════════════════════════════════════════
    all_anchorable = []
    try:
        result = sb.table('problems')\
            .select('id, description, category, source, max_source_tier, keywords, metadata, first_seen, source_post_ids')\
            .eq('metadata->>anchorable', 'true')\
            .gte('first_seen', window_start)\
            .lte('first_seen', window_end)\
            .order('first_seen', desc=True)\
            .limit(600)\
            .execute()
        all_anchorable = result.data or []
    except Exception as e:
        logger.error(f"Block selection: failed to query anchorable extractions: {e}")

    logger.info(f"Block selection: {len(all_anchorable)} anchorable extractions in window")

    # Build URL lookup: source_post UUID → source_url
    # Collect all source_post_ids referenced by extractions
    all_sp_ids = set()
    for ext in all_anchorable:
        for sp_id in (ext.get('source_post_ids') or []):
            if sp_id:
                all_sp_ids.add(sp_id)

    url_lookup: dict[str, str] = {}
    if all_sp_ids:
        # Batch lookup in chunks of 50
        sp_id_list = list(all_sp_ids)
        for i in range(0, len(sp_id_list), 50):
            chunk = sp_id_list[i:i+50]
            try:
                url_result = sb.table('source_posts')\
                    .select('id, source_url')\
                    .in_('id', chunk)\
                    .execute()
                for row in (url_result.data or []):
                    if row.get('source_url'):
                        url_lookup[row['id']] = row['source_url']
            except Exception as e:
                logger.warning(f"Block selection: URL lookup failed for chunk: {e}")

    # ══════════════════════════════════════════════════════════════
    # Step 2: Auto-include tier 1 anchorable events
    # Max 5 per source for tier 1, max 3 for tier 2-3
    # Max 15 total auto-included, most recent first
    # ══════════════════════════════════════════════════════════════
    tier1 = [e for e in all_anchorable if e.get('max_source_tier') == 1]

    auto_blocks = []
    source_counts: dict[str, int] = {}
    auto_ids: set[str] = set()

    for ext in tier1:
        src = ext.get('source', 'unknown')
        if source_counts.get(src, 0) >= _source_cap(1):
            continue
        if len(auto_blocks) >= 15:
            break
        auto_blocks.append(_format_block(ext, 'auto_include', 'Tier 1 anchorable event', url_lookup))
        source_counts[src] = source_counts.get(src, 0) + 1
        auto_ids.add(ext['id'])

    logger.info(f"Block selection: {len(auto_blocks)} auto-included (tier 1), {len(source_counts)} sources")

    # ══════════════════════════════════════════════════════════════
    # Step 2b: Angle-entity boosting
    # If the prepass angle mentions a specific entity by name,
    # auto-include any anchorable extraction with that entity
    # ══════════════════════════════════════════════════════════════
    if prepass_angle:
        angle_lower = prepass_angle.lower()
        for ext in all_anchorable:
            if ext['id'] in auto_ids:
                continue
            ext_entities = ext.get('keywords') or []
            for ent in ext_entities:
                if len(ent) >= 4 and ent.lower() in angle_lower:
                    src = ext.get('source', 'unknown')
                    tier = ext.get('max_source_tier', 3)
                    if source_counts.get(src, 0) < _source_cap(tier):
                        auto_blocks.append(_format_block(
                            ext, 'angle_boost',
                            f"Entity '{ent}' mentioned in editorial angle",
                            url_lookup
                        ))
                        source_counts[src] = source_counts.get(src, 0) + 1
                        auto_ids.add(ext['id'])
                        logger.info(f"Block selection: angle-boosted '{ent}' from {src}")
                    break  # one match per extraction is enough

    # ══════════════════════════════════════════════════════════════
    # Step 3: LLM-aligned selection (tier 2-3 + remaining tier 1)
    # ══════════════════════════════════════════════════════════════
    remaining = [e for e in all_anchorable if e['id'] not in auto_ids]

    llm_blocks = []
    if llm_client and remaining:
        llm_blocks = _llm_select(
            remaining, prepass_angle, llm_client,
            source_counts, target=15, url_lookup=url_lookup
        )

    # Update source counts
    for block in llm_blocks:
        src = block.get('source', 'unknown')
        source_counts[src] = source_counts.get(src, 0) + 1

    llm_ids = {b['extraction_id'] for b in llm_blocks}
    logger.info(f"Block selection: {len(llm_blocks)} LLM-aligned selections")

    # ══════════════════════════════════════════════════════════════
    # Step 4: Diversity fill
    # For each core category with 0 blocks, add top anchorable
    # ══════════════════════════════════════════════════════════════
    selected_ids = auto_ids | llm_ids
    all_selected = auto_blocks + llm_blocks

    categories_covered = {b.get('category') for b in all_selected}
    diversity_blocks = []

    for cat in CORE_CATEGORIES:
        if cat in categories_covered:
            continue
        if len(diversity_blocks) >= 5:
            break
        # Find best unselected extraction in this category
        candidates = [
            e for e in all_anchorable
            if e.get('category') == cat
            and e['id'] not in selected_ids
            and source_counts.get(e.get('source', 'unknown'), 0) < _source_cap(e.get('max_source_tier', 3))
        ]
        if candidates:
            ext = candidates[0]  # already sorted by recency
            diversity_blocks.append(_format_block(ext, 'diversity_fill',
                                                  f'Diversity fill for category: {cat}', url_lookup))
            src = ext.get('source', 'unknown')
            source_counts[src] = source_counts.get(src, 0) + 1
            selected_ids.add(ext['id'])

    logger.info(f"Block selection: {len(diversity_blocks)} diversity fills")

    # ══════════════════════════════════════════════════════════════
    # Step 5: Tracked entity signals (non-anchorable items linked
    # to entities in primary blocks)
    # ══════════════════════════════════════════════════════════════
    all_blocks = auto_blocks + llm_blocks + diversity_blocks

    # Build entity set from all selected blocks
    block_entities = set()
    block_entity_to_id: dict[str, str] = {}  # entity → block extraction_id
    for b in all_blocks:
        for ent in (b.get('named_entities') or []):
            ent_lower = ent.lower()
            if len(ent) >= 3:
                block_entities.add(ent_lower)
                block_entity_to_id[ent_lower] = b['extraction_id']

    # Query non-anchorable extractions in the window
    non_anchorable = []
    try:
        result = sb.table('problems')\
            .select('id, description, category, source, max_source_tier, keywords, metadata, source_post_ids')\
            .eq('metadata->>anchorable', 'false')\
            .gte('first_seen', window_start)\
            .lte('first_seen', window_end)\
            .order('first_seen', desc=True)\
            .limit(300)\
            .execute()
        non_anchorable = result.data or []
    except Exception as e:
        logger.error(f"Block selection: failed to query non-anchorable extractions: {e}")

    # Add non-anchorable source_post_ids to URL lookup
    for ext in non_anchorable:
        for sp_id in (ext.get('source_post_ids') or []):
            if sp_id and sp_id not in url_lookup:
                all_sp_ids.add(sp_id)
    # Fetch any new IDs not already looked up
    new_ids = [sp_id for sp_id in all_sp_ids if sp_id not in url_lookup]
    for i in range(0, len(new_ids), 50):
        chunk = new_ids[i:i+50]
        try:
            url_result = sb.table('source_posts').select('id, source_url').in_('id', chunk).execute()
            for row in (url_result.data or []):
                if row.get('source_url'):
                    url_lookup[row['id']] = row['source_url']
        except Exception:
            pass

    # Count entity frequency across non-anchorable extractions
    # Use both exact and word-level matching for multi-word entities
    entity_freq: dict[str, int] = {}
    for ext in non_anchorable:
        for ent in (ext.get('keywords') or []):
            if len(ent) >= 3:
                ent_lower = ent.lower()
                entity_freq[ent_lower] = entity_freq.get(ent_lower, 0) + 1
                # Also count each word of multi-word entities (for substring matching)
                for word in ent_lower.split():
                    if len(word) >= 4:  # skip short words
                        entity_freq[word] = entity_freq.get(word, 0) + 1

    # Trending entities: appear 3+ times but not in primary blocks
    # Check both exact match and substring containment
    trending_entities = set()
    for ent, count in entity_freq.items():
        if count < 3:
            continue
        # Skip if already in block entities (exact or substring)
        in_blocks = ent in block_entities or any(ent in be or be in ent for be in block_entities if len(be) >= 4)
        if not in_blocks:
            trending_entities.add(ent)

    tracked_signals = []
    seen_signal_ids = set()
    for ext in non_anchorable:
        if len(tracked_signals) >= 8:
            break
        ext_entities = {e.lower() for e in (ext.get('keywords') or []) if len(e) >= 3}

        # Match: overlaps with block entities OR mentions a trending entity
        overlap = ext_entities & block_entities
        trending_overlap = ext_entities & trending_entities

        if (overlap or trending_overlap) and ext['id'] not in seen_signal_ids:
            if overlap:
                linked = next(iter(overlap))
                reason = f"Mentions '{linked}' which appears in primary blocks"
                linked_block = block_entity_to_id.get(linked, '')
            else:
                linked = next(iter(trending_overlap))
                reason = f"Trending entity '{linked}' ({entity_freq.get(linked, 0)} mentions across signals)"
                linked_block = ''

            # Resolve URL for the signal
            sig_url = ''
            for sp_id in (ext.get('source_post_ids') or []):
                if sp_id and sp_id in url_lookup:
                    sig_url = url_lookup[sp_id]
                    break

            tracked_signals.append({
                'extraction_id': ext['id'],
                'description': ext.get('description', ''),
                'named_entities': ext.get('keywords') or [],
                'source': ext.get('source', 'unknown'),
                'source_url': sig_url,
                'category': ext.get('category', 'other'),
                'linked_entity': linked,
                'linked_to_block': linked_block,
                'selection_reason': reason,
            })
            seen_signal_ids.add(ext['id'])

    logger.info(f"Block selection: {len(tracked_signals)} tracked entity signals")

    # ══════════════════════════════════════════════════════════════
    # Step 6: Query tool stats and predictions (pass-through)
    # ══════════════════════════════════════════════════════════════
    tool_stats = []
    try:
        result = sb.table('tool_stats')\
            .select('*')\
            .order('mentions_7d', desc=True)\
            .limit(10)\
            .execute()
        tool_stats = result.data or []
    except Exception as e:
        logger.error(f"Block selection: failed to query tool_stats: {e}")

    predictions = []
    try:
        result = sb.table('predictions')\
            .select('*')\
            .in_('status', ['open', 'at_risk', 'failed', 'confirmed', 'refuted'])\
            .order('created_at', desc=True)\
            .limit(10)\
            .execute()
        predictions = result.data or []
    except Exception as e:
        logger.error(f"Block selection: failed to query predictions: {e}")

    # ══════════════════════════════════════════════════════════════
    # Assemble output
    # ══════════════════════════════════════════════════════════════
    final_categories = {b.get('category') for b in all_blocks}

    return {
        'blocks': all_blocks,
        'tracked_entity_signals': tracked_signals,
        'tool_stats': tool_stats,
        'predictions': predictions,
        'summary': {
            'total_blocks': len(all_blocks),
            'auto_included': len(auto_blocks),
            'llm_aligned': len(llm_blocks),
            'diversity_fills': len(diversity_blocks),
            'tracked_signals': len(tracked_signals),
            'categories_covered': sorted(final_categories),
            'sources_used': sorted(source_counts.keys()),
            'source_counts': source_counts,
            'anchorable_pool_size': len(all_anchorable),
        }
    }


def _format_block(extraction: dict, method: str, justification: str,
                   url_lookup: dict[str, str] | None = None) -> dict:
    """Format an extraction record into a block."""
    meta = extraction.get('metadata', {}) or {}

    # Resolve source_url from the first source_post_id
    source_url = ''
    if url_lookup:
        for sp_id in (extraction.get('source_post_ids') or []):
            if sp_id and sp_id in url_lookup:
                source_url = url_lookup[sp_id]
                break

    return {
        'extraction_id': extraction['id'],
        'description': extraction.get('description', ''),
        'named_entities': extraction.get('keywords') or [],
        'source': extraction.get('source', 'unknown'),
        'source_tier': extraction.get('max_source_tier', 3),
        'source_url': source_url,
        'type': meta.get('type', 'problem'),
        'category': extraction.get('category', 'other'),
        'selection_method': method,
        'justification': justification,
    }


def _llm_select(
    candidates: list[dict],
    angle: str | None,
    llm_client,
    existing_source_counts: dict[str, int],
    target: int = 15,
    url_lookup: dict[str, str] | None = None,
) -> list[dict]:
    """Use DeepSeek to select the most relevant extractions for the angle.

    Respects cumulative per-source cap.
    """
    # Build candidate summaries for the LLM (keep token budget manageable)
    # Prioritize tier 2 items (underrepresented in auto-include) and ensure
    # all core categories have candidates visible to the LLM
    tier2_items = [e for e in candidates if e.get('max_source_tier') == 2]
    tier3_items = [e for e in candidates if e.get('max_source_tier') == 3]
    tier1_overflow = [e for e in candidates if e.get('max_source_tier') == 1]

    # Always include ALL tier 2 anchorable items (typically ~50, manageable)
    flat = list(tier2_items[:60])

    # Add tier 3 items (up to 10)
    flat.extend(tier3_items[:10])

    # Fill remaining budget with tier 1 overflow, diversified by category
    # Boost categories mentioned in the angle text
    angle_lower = (angle or '').lower()
    angle_cats = {cat for cat in CORE_CATEGORIES if cat in angle_lower}

    by_cat: dict[str, list] = {}
    for ext in tier1_overflow:
        cat = ext.get('category', 'other')
        if cat not in by_cat:
            by_cat[cat] = []
        cap = 6 if cat in angle_cats else 3
        if len(by_cat[cat]) < cap:
            by_cat[cat].append(ext)
    for cat_exts in by_cat.values():
        flat.extend(cat_exts)

    candidates_text = json.dumps([
        {
            'id': e['id'],
            'description': e.get('description', '')[:200],
            'category': e.get('category', 'other'),
            'source': e.get('source', 'unknown'),
            'tier': e.get('max_source_tier', 3),
            'entities': (e.get('keywords') or [])[:5],
        }
        for e in flat
    ], indent=1)

    angle_text = angle or "Select the most newsworthy and diverse items."

    # Build per-source cap info for the prompt
    cap_info = {src: f"{cnt}/{_source_cap(1)}" for src, cnt in existing_source_counts.items()}

    prompt = f"""You are selecting building blocks for a newsletter about the AI agent economy.

Editorial angle for this edition: {angle_text}

Select the {target} most relevant extractions from the candidates below.

RANKING CRITERIA (in priority order):
1. ANGLE RELEVANCE — How directly does this item support, complicate, or advance the editorial angle? This is the primary criterion. When multiple extractions from the same person or source cover related topics, pick the one whose description most directly supports or complicates the editorial angle, even if it's older.
2. SPECIFICITY — Items with named entities, concrete details, and verifiable claims rank higher than abstract descriptions.
3. DIVERSITY — Spread across different sources and categories. Don't cluster selections in one domain.
4. SIGNIFICANCE — Events that affect the agent economy broadly, not niche tooling updates.

IMPORTANT: Recency is a tiebreaker, NOT a primary criterion. An older item that directly supports the angle beats a newer item that's tangentially related.

Per-source caps (tier 1: max 5, tier 2-3: max 3). Already-selected: {json.dumps(cap_info)}

Candidates:
{candidates_text}

Respond ONLY with valid JSON:
{{
  "selected": [
    {{
      "id": "extraction UUID",
      "justification": "1 sentence why this was selected"
    }}
  ]
}}"""

    try:
        response = llm_client.chat.completions.create(
            model='deepseek-chat',
            messages=[
                {"role": "system", "content": "You select newsworthy items for a newsletter. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=3000,
        )

        text = response.choices[0].message.content
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        result = json.loads(text.strip())

        # Map selected IDs back to full extraction records
        ext_by_id = {e['id']: e for e in flat}
        blocks = []
        source_counts = dict(existing_source_counts)

        for sel in result.get('selected', []):
            sid = sel.get('id', '')
            ext = ext_by_id.get(sid)
            if not ext:
                continue
            src = ext.get('source', 'unknown')
            tier = ext.get('max_source_tier', 3)
            if source_counts.get(src, 0) >= _source_cap(tier):
                continue
            blocks.append(_format_block(ext, 'llm_aligned', sel.get('justification', ''), url_lookup))
            source_counts[src] = source_counts.get(src, 0) + 1
            if len(blocks) >= target:
                break

        return blocks

    except Exception as e:
        logger.error(f"LLM block selection failed: {e}")
        # Fallback: take top N by recency, respecting source caps
        blocks = []
        source_counts = dict(existing_source_counts)
        for ext in candidates:
            src = ext.get('source', 'unknown')
            tier = ext.get('max_source_tier', 3)
            if source_counts.get(src, 0) >= _source_cap(tier):
                continue
            blocks.append(_format_block(ext, 'llm_aligned_fallback',
                                        'Fallback: selected by recency after LLM failure', url_lookup))
            source_counts[src] = source_counts.get(src, 0) + 1
            if len(blocks) >= target:
                break
        return blocks
