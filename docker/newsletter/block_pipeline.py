"""Block-based newsletter generation pipeline (Phases B, C, E).

Phase B: Section structure — assigns blocks to sections under an editorial angle.
Phase C: Prose rendering — per-section constrained writer.
Phase E: Voice consistency check.

This module implements the new block-based architecture. It receives
block_selection output and produces a newsletter draft where every
specific claim traces to a verified building block.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

try:
    import anthropic
except ImportError:
    anthropic = None

logger = logging.getLogger('block_pipeline')


def _llm_call(client, model: str, system: str, user: str,
              temperature: float = 0.3, max_tokens: int = 3000) -> str:
    """Unified LLM call supporting both OpenAI and Anthropic SDK clients.

    Returns the text content of the response.
    """
    # Detect Anthropic client
    if anthropic and isinstance(client, anthropic.Anthropic):
        response = client.messages.create(
            model=model,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.content[0].text

    # OpenAI-compatible client (DeepSeek, OpenAI, proxied)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content

# ═══════════════════════════════════════════════════════════════════
# Phase B: Section Structure
# ═══════════════════════════════════════════════════════════════════

PHASE_B_SYSTEM = "You are an editorial planner for a weekly newsletter about the AI agent economy. You assign verified building blocks to newsletter sections. Respond only with valid JSON."

PHASE_B_PROMPT = """Plan the section structure for this week's newsletter edition.

EDITORIAL ANGLE: {angle}

AVAILABLE BUILDING BLOCKS (each is a verified fact from this week's sources):
{blocks_json}

TOOL STATS (pass-through data, use exact numbers):
{tool_stats_json}

TRACKED ENTITY SIGNALS (non-anchorable community signals):
{signals_json}

SECTIONS TO PLAN:
1. "read_this_skip_the_rest" — 3-5 blocks for the lead section. Lead with the strongest anchorable event that supports the angle. Include supporting and contrasting blocks.
2. "emerging_signals" — 3-4 blocks showing new patterns or community attention. Mix anchorable events with tracked signals.
3. "tool_radar" — use tool_stats data directly (pass-through, don't invent metrics).
4. "gato_corner" — 1-2 blocks for the bitcoin/crypto editorial commentary.

For each section, specify:
- Which blocks to include (by extraction_id)
- Rhetorical role of each block: "lead_anchor", "supporting", "contrast", "implication", "community_signal"
- A 1-sentence rhetorical note explaining how the blocks connect

RULES:
- Every block you reference must exist in the AVAILABLE BUILDING BLOCKS list above.
- Do NOT invent blocks, entities, or statistics not in the list.
- A block can appear in at most one section.
- If fewer than 3 blocks support the angle for the lead section, report "insufficient_support": true.

Respond ONLY with valid JSON:
{{
  "insufficient_support": false,
  "sections": {{
    "read_this_skip_the_rest": {{
      "blocks": [
        {{"extraction_id": "...", "role": "lead_anchor"}},
        {{"extraction_id": "...", "role": "supporting"}}
      ],
      "rhetorical_note": "..."
    }},
    "emerging_signals": {{
      "blocks": [...],
      "rhetorical_note": "..."
    }},
    "gato_corner": {{
      "blocks": [...],
      "rhetorical_note": "..."
    }}
  }}
}}"""


def phase_b_structure(blocks_data: dict, angle: str, llm_client,
                      model: str = 'claude-sonnet-4-20250514') -> dict:
    """Phase B: Generate section structure from blocks + angle.

    Args:
        blocks_data: Output from block_selection.select_blocks()
        angle: Editorial angle string
        llm_client: Anthropic or OpenAI-compatible client
        model: Model to use

    Returns:
        Section structure dict, or dict with 'error' key on failure.
    """
    blocks = blocks_data.get('blocks', [])
    tool_stats = blocks_data.get('tool_stats', [])
    signals = blocks_data.get('tracked_entity_signals', [])

    # Compact blocks for the prompt (keep essential fields)
    compact_blocks = [
        {
            'extraction_id': b['extraction_id'],
            'description': b['description'][:200],
            'named_entities': b['named_entities'][:5],
            'source': b['source'],
            'source_url': b.get('source_url', ''),
            'type': b['type'],
            'category': b['category'],
        }
        for b in blocks
    ]

    compact_stats = [
        {
            'tool_name': t.get('tool_name', ''),
            'mentions_30d': t.get('mentions_30d', 0),
            'avg_sentiment': round(t.get('avg_sentiment', 0), 3),
        }
        for t in tool_stats[:6]
    ]

    compact_signals = [
        {
            'extraction_id': s['extraction_id'],
            'description': s['description'][:150],
            'named_entities': s.get('named_entities', [])[:3],
            'linked_entity': s.get('linked_entity', ''),
        }
        for s in signals
    ]

    prompt = PHASE_B_PROMPT.format(
        angle=angle,
        blocks_json=json.dumps(compact_blocks, indent=1),
        tool_stats_json=json.dumps(compact_stats, indent=1),
        signals_json=json.dumps(compact_signals, indent=1),
    )

    try:
        text = _llm_call(llm_client, model, PHASE_B_SYSTEM, prompt,
                         temperature=0.3, max_tokens=3000)
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        result = json.loads(text.strip())

        # Validate: all referenced extraction_ids exist in blocks
        block_ids = {b['extraction_id'] for b in blocks}
        signal_ids = {s['extraction_id'] for s in signals}
        valid_ids = block_ids | signal_ids

        for section_name, section in result.get('sections', {}).items():
            for item in section.get('blocks', []):
                eid = item.get('extraction_id', '')
                if eid and eid not in valid_ids:
                    logger.warning(f"Phase B: section '{section_name}' references unknown extraction_id {eid[:12]}...")

        return result

    except Exception as e:
        logger.error(f"Phase B failed: {e}")
        return {'error': str(e)}


# ═══════════════════════════════════════════════════════════════════
# Phase C: Prose Rendering (per-section)
# ═══════════════════════════════════════════════════════════════════

PHASE_C_SYSTEM = """You are a newsletter writer for AgentPulse, a weekly intelligence brief about the AI agent economy.

Voice: observational, building-in-public, specific over polished. You explain what happened and why it matters, without hype or abstraction. When you reference a specific event, link the primary entity or most natural anchor to the source URL using markdown: [Entity](url).

ABSOLUTE CONSTRAINTS:
- Every named entity (company, product, person) MUST come from the building blocks provided.
- Every number, percentage, date, or statistic MUST come from the building blocks.
- Every quote MUST come from the building blocks.
- You may NOT introduce any new specific claims, entities, or numbers.
- If you can't make a point without inventing a specific, skip it.

ALLOWED:
- Transitional language ("This week saw...", "Meanwhile...")
- Causal framing ("This matters because...")
- Connections between blocks ("The Stripe move complements MoonPay's launch")
- Forward-looking editorial judgment ("Expect this to accelerate")

LINK REQUIREMENTS:
- Every anchorable event: link the primary named entity on first mention to source_url.
- Direct quotes: link the speaker's name to source_url.
- One link per event reference. Don't double-link.
- Tool Radar metrics: no links (aggregate stats).
- Predictions: no links (AgentPulse's own claims)."""

PHASE_C_SECTION_PROMPT = """Write the "{section_name}" section for this week's newsletter.

EDITORIAL ANGLE: {angle}

BUILDING BLOCKS FOR THIS SECTION (use ONLY these — do not add facts not listed here):
{section_blocks_json}

RHETORICAL NOTE: {rhetorical_note}

{section_specific_instructions}

Write the section in markdown. Use the building blocks' source_url fields for inline links."""


def _section_instructions(section_name: str) -> str:
    """Return section-specific writing instructions."""
    if section_name == 'read_this_skip_the_rest':
        return """This is the lead section. 3-4 paragraphs.
- Open with the strongest event that supports the editorial angle.
- Link each event's primary entity to its source_url on first mention.
- Connect the events into a coherent narrative under the angle.
- Close with what this means for the reader."""

    elif section_name == 'emerging_signals':
        return """3-4 signal items, each 2-3 sentences.
- Each signal gets a bold header: **Signal Name**
- Describe what the community or sources are reporting.
- Link named entities to source_url where available.
- Include "First seen" timing only if the block data provides a date."""

    elif section_name == 'tool_radar':
        return """List each tool with trajectory, metrics, and an optional connecting sentence.

FORMAT per entry:
**ToolName** Trajectory: [Rising/Stable/Falling]. [metrics from tool_stats only]. [optional: one connecting sentence referencing a relevant_block if one exists for this tool].

METRICS RULES:
- Use ONLY the exact numbers from the tool_stats data provided. Do not round or estimate.
- Trajectory is determined by mentions_7d vs mentions_30d trend and sentiment direction.
- If top_alternatives is listed in tool_stats data, you may mention those names.

CONNECTING SENTENCE RULES:
- You may add ONE connecting sentence per tool entry IF and ONLY IF a matching block appears in the relevant_blocks list.
- The connecting sentence must reference specific content from that block (a quote, event, or observation).
- Do NOT invent relationships, trends, or competitive dynamics not in the block.
- If no relevant_block exists for a tool, write ONLY the metrics line. No connecting sentence.
- Do NOT add a general editorial takeaway paragraph at the end.

FORBIDDEN:
- Do NOT claim tools are "gaining traction", "competing with", or "replacing" other tools unless the block explicitly says so.
- Do NOT invent developer sentiment, frustration, or adoption claims not in a block.
- No links (aggregate stats, no single source)."""

    elif section_name == 'gato_corner':
        return """1-2 paragraphs in Gato's voice (bitcoin-maximalist, observational, sardonic).
- Connect the week's theme to bitcoin/crypto principles.
- Reference specific blocks where possible.
- Close with "Stay humble, stack sats."
- No links needed."""

    return ""


def phase_c_render(section_name: str, section_spec: dict,
                   blocks_data: dict, angle: str,
                   llm_client, model: str = 'claude-sonnet-4-20250514',
                   audience: str = 'technical') -> str:
    """Phase C: Render one section from blocks into prose.

    Args:
        section_name: Section identifier
        section_spec: Section structure from Phase B (blocks + rhetorical_note)
        blocks_data: Full block_selection output (for looking up block details)
        angle: Editorial angle
        llm_client: LLM client
        model: Model to use
        audience: 'technical' (builder-focused) or 'impact' (strategic/business)

    Returns:
        Markdown string for the section.
    """
    # Resolve block details from extraction_ids
    block_lookup = {b['extraction_id']: b for b in blocks_data.get('blocks', [])}
    signal_lookup = {s['extraction_id']: s for s in blocks_data.get('tracked_entity_signals', [])}

    section_blocks = []
    for item in section_spec.get('blocks', []):
        eid = item.get('extraction_id', '')
        block = block_lookup.get(eid) or signal_lookup.get(eid)
        if block:
            section_blocks.append({
                **block,
                'role': item.get('role', 'supporting'),
            })

    # For tool_radar, inject tool_stats + relevant blocks for connecting sentences
    if section_name == 'tool_radar':
        tool_stats = blocks_data.get('tool_stats', [])
        # Build a map of tool names mentioned in this edition's blocks
        # so the writer can add one connecting sentence per tool if a
        # relevant block exists
        tool_names = {t.get('tool_name', '').lower() for t in tool_stats}
        all_blocks = blocks_data.get('blocks', []) + blocks_data.get('tracked_entity_signals', [])
        relevant_blocks = []
        for b in all_blocks:
            block_entities = {e.lower() for e in (b.get('named_entities') or [])}
            if block_entities & tool_names:
                relevant_blocks.append({
                    'extraction_id': b.get('extraction_id', ''),
                    'description': b.get('description', '')[:200],
                    'named_entities': (b.get('named_entities') or [])[:5],
                    'source': b.get('source', ''),
                })
        section_blocks = {
            'tool_stats': tool_stats,
            'relevant_blocks': relevant_blocks,
        }

    rhetorical_note = section_spec.get('rhetorical_note', '')

    audience_prefix = ""
    if audience == 'impact':
        audience_prefix = "AUDIENCE: Business leaders and strategic decision-makers. Use accessible language. Explain technical concepts in terms of business outcomes and competitive dynamics. Avoid jargon.\n\n"
    else:
        audience_prefix = "AUDIENCE: Technical builders and infrastructure teams. Be specific about implementations, architectures, and tooling. Assume the reader builds software.\n\n"

    prompt = audience_prefix + PHASE_C_SECTION_PROMPT.format(
        section_name=section_name.replace('_', ' ').title(),
        angle=angle,
        section_blocks_json=json.dumps(section_blocks, indent=1, default=str),
        rhetorical_note=rhetorical_note,
        section_specific_instructions=_section_instructions(section_name),
    )

    try:
        text = _llm_call(llm_client, model, PHASE_C_SYSTEM, prompt,
                         temperature=0.4, max_tokens=2000)
        # Strip duplicate section headers — the template adds them,
        # so remove any leading ## headers the LLM emitted
        text = text.strip()
        text = re.sub(r'^#+\s+.*?\n+', '', text, count=1).strip()
        return text

    except Exception as e:
        logger.error(f"Phase C render failed for {section_name}: {e}")
        return f"<!-- Phase C render error for {section_name}: {e} -->"


# ═══════════════════════════════════════════════════════════════════
# Phase E: Voice Consistency Check
# ═══════════════════════════════════════════════════════════════════

PHASE_E_PROMPT = """Rate this newsletter draft's voice consistency against the exemplar paragraphs.

EXEMPLARS (these represent the target voice — observational, building-in-public, specific over polished):
{exemplars}

DRAFT TO CHECK:
{draft}

Rate on a 1-5 scale:
1 = completely different voice (academic, marketing, generic blog)
2 = recognizable but significant drift (too formal, too hype-driven)
3 = recognizably similar with notable drift in places
4 = consistent with minor variation
5 = indistinguishable from exemplars

Provide:
- score: float (1.0-5.0)
- observations: 2-3 specific observations about voice match or drift

Respond ONLY with valid JSON:
{{
  "score": 4.0,
  "observations": ["...", "..."]
}}"""


def phase_e_voice_check(draft: str, exemplars: list[str],
                        llm_client, model: str = 'deepseek-chat') -> dict:
    """Phase E: Check voice consistency against exemplar paragraphs.

    Returns: {"score": float, "observations": [str]}
    """
    if not exemplars:
        return {"score": 0, "observations": ["No exemplars provided — voice check skipped"]}

    exemplar_text = "\n\n---\n\n".join(exemplars[:10])

    prompt = PHASE_E_PROMPT.format(
        exemplars=exemplar_text,
        draft=draft[:4000],  # cap for token budget
    )

    try:
        text = _llm_call(llm_client, model,
                         "You evaluate newsletter voice consistency. Respond only with valid JSON.",
                         prompt, temperature=0.2, max_tokens=500)
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        return json.loads(text.strip())

    except Exception as e:
        logger.error(f"Phase E voice check failed: {e}")
        return {"score": 0, "observations": [f"Voice check failed: {e}"]}


# ═══════════════════════════════════════════════════════════════════
# Block-Aware Prepass (runs AFTER Phase A, BEFORE Phase B)
# ═══════════════════════════════════════════════════════════════════

BLOCK_PREPASS_SYSTEM = """You are the editor-in-chief of AgentPulse, a weekly intelligence brief about the AI agent economy. Your job is to choose THIS WEEK's editorial angle.

CRITICAL CONSTRAINT: You may ONLY reference entities, events, and facts that appear in the building blocks provided. The blocks are your entire fact base. Do not reference events or entities not in this list.

Respond with valid JSON only. No markdown, no commentary."""

BLOCK_PREPASS_PROMPT = """Choose this week's editorial angle from these verified building blocks.

BUILDING BLOCKS (these are the verified facts available for this edition):
{blocks_json}

PREVIOUS EDITIONS (avoid repeating these angles):
{editions_text}

AVOIDED THEMES: {avoided_themes}

RULES:
- The angle must be supportable by at least 3 anchorable blocks from the list above.
- Name specific entities from the blocks, not generic themes.
- A concrete event with named entities ("Stripe launched agent-to-agent payments") beats a generic theme ("payment infrastructure evolving").
- If multiple strong events compete, pick the one with the most supporting blocks.

Return JSON:
{{
  "chosen_angle": "one sentence describing this week's lead angle",
  "why_fresh": "one sentence explaining why this is different from recent editions",
  "supporting_block_ids": ["3-5 extraction_ids that support this angle"],
  "narrative_bridge": "one sentence connecting to a previous edition"
}}"""


def editorial_prepass_from_blocks(
    blocks_data: dict,
    narrative_context: dict | None = None,
    avoided_themes: list[str] | None = None,
    llm_client=None,
    model: str = 'claude-sonnet-4-20250514',
) -> dict | None:
    """Block-aware prepass: choose angle constrained to available blocks.

    Runs AFTER Phase A (block selection), BEFORE Phase B (section structure).
    The angle can only reference entities present in the selected blocks.

    Returns editorial direction dict, or None on failure.
    """
    if not llm_client:
        logger.warning("[BLOCK PREPASS] No LLM client — skipping")
        return None

    blocks = blocks_data.get('blocks', [])
    if not blocks:
        logger.warning("[BLOCK PREPASS] No blocks available — skipping")
        return None

    # Compact blocks for the prompt
    compact = [
        {
            'extraction_id': b['extraction_id'],
            'description': b['description'][:200],
            'named_entities': b['named_entities'][:5],
            'source': b['source'],
            'category': b['category'],
            'type': b.get('type', 'event'),
        }
        for b in blocks
    ]

    # Build edition history text
    editions_text = "No previous editions available."
    if narrative_context and narrative_context.get('previous_editions'):
        lines = []
        for ed in narrative_context['previous_editions']:
            excerpt = (ed.get('opening_excerpt') or '')[:100]
            lines.append(
                f"#{ed.get('edition_number', '?')} ({ed.get('weeks_ago', '?')}w ago): "
                f"\"{ed.get('title', '?')}\" — {excerpt}"
            )
        editions_text = "\n".join(lines)

    avoided = ', '.join(avoided_themes or []) or 'None'

    prompt = BLOCK_PREPASS_PROMPT.format(
        blocks_json=json.dumps(compact, indent=1),
        editions_text=editions_text,
        avoided_themes=avoided,
    )

    try:
        logger.info("[BLOCK PREPASS] Running block-aware editorial prepass...")
        text = _llm_call(llm_client, model, BLOCK_PREPASS_SYSTEM, prompt,
                         temperature=0.3, max_tokens=512)

        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        result = json.loads(text.strip())

        # Validate: supporting_block_ids should exist in the block list
        block_ids = {b['extraction_id'] for b in blocks}
        supporting = result.get('supporting_block_ids', [])
        valid_supporting = [sid for sid in supporting if sid in block_ids]

        if len(valid_supporting) < 3:
            logger.warning(
                f"[BLOCK PREPASS] Only {len(valid_supporting)} valid supporting blocks "
                f"(need 3). Angle may be weakly supported."
            )

        result['supporting_block_ids'] = valid_supporting
        logger.info(f"[BLOCK PREPASS] Chosen angle: {result.get('chosen_angle', '?')}")
        logger.info(f"[BLOCK PREPASS] Supporting blocks: {len(valid_supporting)}")

        return result

    except Exception as e:
        logger.error(f"[BLOCK PREPASS] Failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
# Full Pipeline Orchestrator
# ═══════════════════════════════════════════════════════════════════

def generate_from_blocks(
    blocks_data: dict,
    angle: str,
    llm_client,
    exemplars: list[str] | None = None,
    model_structure: str = 'deepseek-chat',
    model_prose: str = 'claude-sonnet-4-20250514',
    model_voice: str = 'deepseek-chat',
) -> dict:
    """Run the full block-based pipeline: B → C → E.

    Args:
        blocks_data: Output from block_selection.select_blocks()
        angle: Editorial angle
        llm_client: LLM client (OpenAI-compatible, routes to different models)
        exemplars: Voice exemplar paragraphs for Phase E
        model_structure: Model for Phase B
        model_prose: Model for Phase C
        model_voice: Model for Phase E

    Returns:
        {
            "content_markdown": str,
            "structure": dict (Phase B output),
            "voice_score": dict (Phase E output),
            "sections": {name: prose},
        }
    """
    # ── Phase B: Section structure (with 2-failure fallback) ──
    failed_angles = []
    structure = None

    for attempt in range(3):
        current_angle = angle
        if attempt > 0 and failed_angles:
            # Append exclusion constraint for retry
            current_angle = (
                f"{angle}\n\nDo NOT use these angles (already failed): "
                + "; ".join(failed_angles)
            )

        if attempt == 2:
            # Mechanical fallback: pick the cluster with most blocks
            category_counts: dict[str, int] = {}
            for b in blocks_data.get('blocks', []):
                cat = b.get('category', 'other')
                category_counts[cat] = category_counts.get(cat, 0) + 1
            if category_counts:
                best_cat = max(category_counts, key=category_counts.get)
                current_angle = f"Focus on {best_cat}: the category with the most events this week."
                logger.warning(f"[BLOCK PIPELINE] Phase B fallback: forced angle to '{best_cat}' after 2 failures")

        logger.info(f"[BLOCK PIPELINE] Phase B attempt {attempt + 1}: generating structure...")
        structure = phase_b_structure(blocks_data, current_angle, llm_client, model=model_structure)

        if structure.get('error'):
            return {'error': f"Phase B failed: {structure['error']}"}

        if structure.get('insufficient_support'):
            failed_angles.append(current_angle[:100])
            logger.warning(f"[BLOCK PIPELINE] Phase B: insufficient support (attempt {attempt + 1})")
            continue

        break  # success

    if not structure or structure.get('insufficient_support'):
        return {'error': 'insufficient_support_after_3_attempts', 'failed_angles': failed_angles}

    sections = structure.get('sections', {})

    # ── Phase C: Per-section prose rendering (both versions) ──
    section_order = ['read_this_skip_the_rest', 'emerging_signals', 'tool_radar', 'gato_corner']

    def _render_all_sections(audience: str) -> dict[str, str]:
        rendered = {}
        for section_name in section_order:
            if section_name not in sections and section_name != 'tool_radar':
                continue
            spec = sections.get(section_name, {'blocks': [], 'rhetorical_note': ''})
            logger.info(f"[BLOCK PIPELINE] Phase C ({audience}): rendering {section_name}...")
            prose = phase_c_render(section_name, spec, blocks_data, angle,
                                   llm_client, model=model_prose, audience=audience)
            rendered[section_name] = prose
        return rendered

    def _assemble_md(rendered: dict[str, str]) -> str:
        md_parts = []
        if 'read_this_skip_the_rest' in rendered:
            md_parts.append("## Read This, Skip the Rest\n\n" + rendered['read_this_skip_the_rest'])
        md_parts.append("---")
        if 'emerging_signals' in rendered:
            md_parts.append("## Emerging Signals\n\n" + rendered['emerging_signals'])
        md_parts.append("---")
        if 'tool_radar' in rendered:
            md_parts.append("## Tool Radar\n\n" + rendered['tool_radar'])
        md_parts.append("---")
        if 'gato_corner' in rendered:
            md_parts.append("## Gato's Corner\n\n" + rendered['gato_corner'])
        return "\n\n".join(md_parts)

    # Technical version (builder audience)
    logger.info("[BLOCK PIPELINE] Phase C: rendering technical version...")
    rendered_tech = _render_all_sections('technical')
    md_tech = _assemble_md(rendered_tech)

    # Impact version (strategic/business audience)
    logger.info("[BLOCK PIPELINE] Phase C: rendering impact version...")
    rendered_impact = _render_all_sections('impact')
    md_impact = _assemble_md(rendered_impact)

    # ── Phase E: Voice consistency check (on technical version) ──
    voice_result = {"score": 0, "observations": ["Skipped — no exemplars"]}
    if exemplars:
        logger.info("[BLOCK PIPELINE] Phase E: checking voice consistency...")
        voice_result = phase_e_voice_check(md_tech, exemplars, llm_client, model=model_voice)
        logger.info(f"[BLOCK PIPELINE] Phase E: voice score = {voice_result.get('score', 0)}")

    return {
        'content_markdown': md_tech,
        'content_markdown_impact': md_impact,
        'structure': structure,
        'voice_score': voice_result,
        'sections_technical': rendered_tech,
        'sections_impact': rendered_impact,
    }
