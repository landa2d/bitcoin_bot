"""Phase D: Post-generation verification for newsletter drafts.

Deterministic verification that every named entity, statistic, date,
and quoted text in the generated prose traces to a building block
from the input data.

Returns a verification report identifying grounded and ungrounded items.
"""

import re
from typing import Any

# ── Stop list: common words that appear capitalized at sentence boundaries ──
# These are NOT entity names even when capitalized. Expanded as needed
# to keep false positive rate <5%.
_STOP_WORDS = {
    # Common sentence starters
    'a', 'an', 'the', 'this', 'that', 'these', 'those', 'it', 'its',
    'they', 'them', 'their', 'we', 'our', 'you', 'your', 'he', 'she',
    'his', 'her', 'who', 'what', 'when', 'where', 'why', 'how',
    'which', 'each', 'every', 'all', 'both', 'few', 'many', 'most',
    'some', 'any', 'no', 'not', 'but', 'and', 'or', 'if', 'then',
    'so', 'yet', 'for', 'nor', 'as', 'at', 'by', 'in', 'on', 'to',
    'of', 'up', 'with', 'from', 'into', 'over', 'after', 'before',
    'between', 'under', 'above', 'below', 'since', 'until', 'while',
    'during', 'about', 'against', 'through', 'without',
    # Common editorial/newsletter words that get capitalized
    'here', 'there', 'now', 'also', 'just', 'only', 'even', 'still',
    'already', 'again', 'once', 'never', 'always', 'often', 'perhaps',
    'maybe', 'however', 'meanwhile', 'instead', 'rather', 'therefore',
    'furthermore', 'moreover', 'nevertheless', 'nonetheless',
    'first', 'second', 'third', 'last', 'next', 'new', 'old',
    'early', 'late', 'more', 'less', 'much', 'very', 'too',
    # Domain words that appear capitalized in headers/bullets
    'trajectory', 'stable', 'rising', 'falling', 'mentions',
    'sentiment', 'target', 'audience', 'why', 'build', 'top',
    'read', 'skip', 'rest', 'opportunities', 'emerging', 'signals',
    'prediction', 'tracker', 'tool', 'radar', 'corner',
    'severity', 'high', 'medium', 'low', 'active', 'failed',
    'confirmed', 'revised', 'open', 'status', 'draft',
    # Section-schema words
    'edition', 'may', 'april', 'june', 'march', 'january', 'february',
    'july', 'august', 'september', 'october', 'november', 'december',
    # Common capitalized nouns that aren't entities
    'infrastructure', 'security', 'payments', 'commerce', 'tools',
    'regulation', 'research', 'identity', 'coordination', 'data',
    'communication', 'talent', 'geopolitics', 'other',
    'enterprise', 'enterprises', 'developer', 'developers',
    'companies', 'investors', 'users', 'teams', 'agents',
    'systems', 'platforms', 'frameworks', 'protocols', 'networks',
    'services', 'products', 'models', 'applications',
    'memory', 'state', 'context', 'compute', 'budget', 'cost',
    'deployment', 'production', 'operations', 'architecture',
    'container', 'detection', 'drive', 'identified', 'inversion',
    'manager', 'orchestrator', 'orchestrators', 'recovery',
    'five', 'hole', 'hong', 'kong', 'japan', 'instead',
    'analytics', 'intelligence',
    # Additional stop words from edition 25/26/27 false positive tuning
    'chase', 'cloud', 'costs', 'crisis', 'drift', 'engine',
    'framework', 'gap', 'gato', 'persistence', 'persistent',
    'runtime', 'service', 'stay', 'three', 'two', 'one',
    'unsustainable', 'documented', 'multiple', 'everyone',
    'temporal', 'resource', 'wall', 'hit', 'rest', 'running',
    'failures', 'long', 'agent', 'agents',
    # Common domain words from editions 25/26
    'attackers', 'current', 'dynamic', 'latency', 'management',
    'mapping', 'seven', 'storage', 'tax', 'traditional',
    'transactions', 'transaction', 'mixed', 'multi', 'cards',
    'confidence', 'trusted', 'legacy', 'honest', 'read',
    'real', 'resistant', 'liquidity', 'chain', 'supply',
    'protection', 'compromise', 'contagion', 'verification',
    # Tool Radar trajectory words
    'steady', 'rising', 'falling', 'stable',
    # Edition 29 false positives: generic words appearing capitalized
    'single', 'virtual', 'issues', 'payment', 'think',
    'alternatives', 'discover', 'consistent', 'advisory',
    'consulting', 'compression', 'maintaining', 'deployments',
    'four', 'breakthrough', 'solution', 'impact', 'business',
    'matters', 'copilot',
    # Block-pipeline common words
    'barely', 'because', 'expect', 'niche', 'quiet',
    'separately', 'start', 'critical', 'hat', 'face',
    'assistant', 'shake', 'steak', 'tank', 'sally',
    # Section header fragments that leak into entity extraction
    'emerging', 'signals', 'prediction', 'tracker',
    'opportunities', 'corner',
    # Geographic / common proper nouns that aren't entity claims
    'silicon', 'valley', 'same', 'street', 'york',
    # Programming languages and generic editorial words
    'javascript', 'python', 'java', 'typescript', 'rust',
    'classic', 'modern', 'traditional', 'institutional',
    'institutions', 'excel', 'coding', 'korean', 'koreans',
}

# ── Section header pattern: strip markdown headers before entity extraction ──
_SECTION_HEADER = re.compile(r'^#+\s+.*$', re.MULTILINE)
_BOLD_HEADER = re.compile(r'^\*\*[^*]+\*\*\s*$', re.MULTILINE)

# ── Regex patterns ──

# Proper nouns: 2+ capitalized words in sequence, or single capitalized
# word not at sentence start (preceded by lowercase/punctuation + space)
_PROPER_NOUN_MULTI = re.compile(r'(?<![.!?\n])\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')
_PROPER_NOUN_SINGLE = re.compile(r'(?<=\s)([A-Z][a-zA-Z]*(?:-[A-Z][a-zA-Z]*)*)\b')
# Also catch ALL-CAPS acronyms (3+ letters)
_ACRONYM = re.compile(r'\b([A-Z]{3,})\b')

# arXiv paper IDs: YYMM.NNNNN (e.g. 2605.12673) — not statistics
_ARXIV_ID = re.compile(r'\b\d{4}\.\d{4,6}\b')

# Numbers with context: percentages, dollar figures, counts with units
_STATISTIC = re.compile(
    r'(?:'
    r'\$[\d,.]+[BMKTbmkt]?\b'           # dollar figures: $40B, $2.5M
    r'|[\d,.]+%'                         # percentages: 30%, 3.5%
    r'|\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:mentions|stars|forks|points|comments|posts|problems|extractions|failures|cases|agents|days|hours|months|weeks|years|sats|calls|documented|reports|incidents|deployments|platforms|teams|providers)'  # counts with units
    r'|\b\d+:\d+'                        # ratios: 3:1, 5:1
    r'|\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:billion|million|thousand|trillion)'  # word-form numbers
    r')'
)

# Dates: specific dates with or without year, month+year, "Q[1-4] 20XX"
# We want to catch fabricated dates like "April 30" and "May 1" even without year
_DATE = re.compile(
    r'(?:'
    r'(?:January|February|March|April|June|July|August|September|October|November|December)\s+\d{1,2}(?:,?\s+\d{4})?'
    r'|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}'
    r'|(?:Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}(?:,?\s+\d{4})?'
    r'|Q[1-4]\s+\d{4}'
    r'|\d{4}-\d{2}-\d{2}'
    r')'
    # Note: "May" excluded from month+day pattern to avoid matching "May 1" in
    # "May 1-3 records" etc. May+year still matches. May+day only if followed by comma+year.
    r'|May\s+\d{1,2},\s+\d{4}'
)

# Quoted text: anything in double quotes or smart quotes
_QUOTED = re.compile(r'["""]([^"""]{10,})["""]')


def _extract_claims_from_prose(prose: str) -> dict[str, list[str]]:
    """Extract all verifiable claims from newsletter prose.

    Returns dict with keys: entities, statistics, dates, quotes.
    Each value is a deduplicated list of extracted strings.
    """
    entities = set()
    statistics = set()
    dates = set()
    quotes = set()

    # ── Known section headers to exclude (newsletter format, not claims) ──
    _SECTION_TITLES = {
        'read this, skip the rest', 'top opportunities', 'emerging signals',
        'tool radar', 'prediction tracker', "gato's corner", 'spotlight',
        'last week', 'this week', 'next week', 'open source', 'hacker news',
        # Impact version sub-headers
        'the business impact.', 'the memory solution.', 'why this matters now.',
        'why this matters.', 'the opportunity.', 'what changed.',
        'the bottom line.', 'what to watch.', 'the takeaway.',
    }

    # Extract entities from bold headers BEFORE stripping them
    # Distinguish between:
    #   - Inline bold (entity names within prose): **Stripe**, **OpenClaw**
    #   - Structural bold headers (signal titles, sub-headers): **AI Identity Standards Go Formal**
    # Structural headers appear on their own line or are followed by a newline.
    # Only inline bold text should be treated as entity candidates.
    _STRUCTURAL_BOLD = re.compile(r'^\s*\*\*([^*]+)\*\*\s*$', re.MULTILINE)
    structural_bold_values = {m.group(1).strip().lower() for m in _STRUCTURAL_BOLD.finditer(prose)}

    for match in re.finditer(r'\*\*([^*]+)\*\*', prose):
        candidate = match.group(1).strip()
        # Skip known section titles
        if candidate.lower() in _SECTION_TITLES:
            continue
        # Skip structural headers (bold text on its own line)
        if candidate.lower() in structural_bold_values:
            continue
        # Skip sub-header patterns (ends with colon or period, >5 words)
        if (candidate.endswith(':') or candidate.endswith('.')) and len(candidate.split()) > 3:
            continue
        if len(candidate) <= 80 and len(candidate) >= 3:
            entities.add(candidate)

    # Strip markdown section headers (they're structural, not prose claims)
    clean = _SECTION_HEADER.sub('', prose)
    clean = _BOLD_HEADER.sub('', clean)
    # Strip remaining markdown formatting
    clean = re.sub(r'[*_`\[\]()]', ' ', clean)
    # Collapse multiple spaces
    clean = re.sub(r'\s+', ' ', clean)

    # ── Extension 1: Multi-word capitalized phrases in prose ──
    # Catches "Memory Orchestrator", "Resource Recovery Tools", etc.
    _MULTI_CAP = re.compile(r'\b([A-Z][a-z]+(?:[\s-][A-Z][a-z]+){1,4})\b')
    for match in _MULTI_CAP.finditer(clean):
        candidate = match.group(1).strip()
        words = candidate.split()
        # At least one word must not be in stop list
        non_stop = [w for w in words if w.lower() not in _STOP_WORDS]
        if non_stop and len(candidate) <= 60:
            entities.add(candidate)

    # ── Single capitalized words (not at sentence start) ──
    for match in _PROPER_NOUN_SINGLE.finditer(clean):
        candidate = match.group(1).strip()
        if (len(candidate) >= 3
                and candidate.lower() not in _STOP_WORDS
                and not candidate.isupper()):
            entities.add(candidate)

    # ── ALL-CAPS acronyms ──
    _ACRONYM_SKIP = {'THE', 'AND', 'BUT', 'FOR', 'NOT', 'ALL',
                     'HAS', 'ARE', 'WAS', 'CAN', 'MAY', 'API',
                     'SDK', 'CLI', 'URL', 'LLM', 'GPU', 'CPU',
                     'RAM', 'SSD', 'DNS', 'SQL', 'RSS', 'USD',
                     'ETF', 'IPO', 'CEO', 'CTO', 'CFO', 'COO',
                     'ESG', 'DeFi', 'DEFI', 'KYC', 'AML', 'AMM'}
    for match in _ACRONYM.finditer(clean):
        candidate = match.group(1)
        if candidate not in _ACRONYM_SKIP:
            entities.add(candidate)

    # ── Statistics (standard patterns) ──
    for match in _STATISTIC.finditer(prose):
        statistics.add(match.group(0).strip())

    # ── Extension 2: Numeric claims with descriptive noun phrases ──
    # Catches "14 documented memory management failures", "12 documented cases", etc.
    # Also catches reversed form: "Documented cases: 12"
    _NUMERIC_CLAIM = re.compile(
        r'\b(\d+(?:,\d{3})*(?:\.\d+)?)\s+'
        r'((?:documented|reported|confirmed|identified|tracked|known|separate|distinct|major|critical|active|new|recent)\s+)?'
        r'([a-z]+(?:\s+[a-z]+){0,3})'
        r'(?:\b)',
        re.IGNORECASE
    )
    _REVERSED_NUMERIC = re.compile(
        r'(?:documented|reported|confirmed|identified|tracked|known)\s+\w+:\s*(\d+)',
        re.IGNORECASE
    )
    # Whitelist: edition metadata, date components, Tool Radar template fragments
    _STAT_WHITELIST_PATTERNS = re.compile(
        r'^\d+\s+(?:edition|may|april|march|june|july|august|september|october|november|december|jan|feb|am|pm'
        r'|trajectory|all\s+over|over\s+again)$',
        re.IGNORECASE
    )
    for match in _NUMERIC_CLAIM.finditer(clean):
        full = match.group(0).strip()
        number = match.group(1)
        # Skip if it's already caught by standard patterns
        if any(full.startswith(s) or s.startswith(full) for s in statistics):
            continue
        # Skip whitelist patterns
        if _STAT_WHITELIST_PATTERNS.match(full):
            continue
        # Skip very common non-claim patterns
        if int(number.replace(',', '').split('.')[0]) < 2:
            continue  # "1 sentence" etc.
        statistics.add(full)

    # Reversed form: "Documented cases: 12"
    for match in _REVERSED_NUMERIC.finditer(clean):
        full = match.group(0).strip()
        statistics.add(full)

    # ── Dates ──
    for match in _DATE.finditer(prose):
        candidate = match.group(0).strip()
        # Skip the edition's own date header
        if 'Edition' not in prose[max(0, match.start()-20):match.start()]:
            dates.add(candidate)

    # Contextual May dates: "First seen: May N", "Identified: May N", etc.
    _MAY_DATE_CONTEXT = re.compile(
        r'(?:First\s+(?:seen|reported|documented|appeared)|Identified|Published|Announced|Launched):\s*May\s+(\d{1,2})',
        re.IGNORECASE
    )
    for match in _MAY_DATE_CONTEXT.finditer(prose):
        dates.add(f"May {match.group(1)}")

    # ── Quotes ──
    for match in _QUOTED.finditer(prose):
        quotes.add(match.group(1).strip())

    # ── Filter out arXiv IDs from statistics ──
    # Pattern: YYMM.NNNNN (e.g., "2605.12673 introduces BenchJack")
    statistics = {s for s in statistics if not _ARXIV_ID.match(s.split()[0]) if s.split()}

    return {
        'entities': sorted(entities),
        'statistics': sorted(statistics),
        'dates': sorted(dates),
        'quotes': sorted(quotes),
    }


def _build_block_list(input_data: dict) -> dict[str, set[str]]:
    """Build the set of verified claims from the edition's input_data.

    Returns dict with keys: entities, statistics, dates, quotes.
    Each value is a set of strings that are considered grounded.
    """
    entities: set[str] = set()
    statistics: set[str] = set()
    dates: set[str] = set()
    quotes: set[str] = set()

    # ── Premium source posts ──
    for post in input_data.get('premium_source_posts', []):
        title = post.get('title', '')
        summary = post.get('summary', '')
        source_display = post.get('source_display', '')
        text = f"{title} {summary} {source_display}"

        # Extract proper nouns from source text
        for match in _PROPER_NOUN_MULTI.finditer(text):
            entities.add(match.group(1).strip())
        for match in _PROPER_NOUN_SINGLE.finditer(text):
            candidate = match.group(1).strip()
            if len(candidate) >= 3 and candidate.lower() not in _STOP_WORDS:
                entities.add(candidate)
        for match in _ACRONYM.finditer(text):
            if match.group(1) not in {'THE', 'AND', 'API', 'SDK'}:
                entities.add(match.group(1))

        # Extract numbers and dates from source text
        for match in _STATISTIC.finditer(text):
            statistics.add(match.group(0).strip())
        for match in _DATE.finditer(text):
            dates.add(match.group(0).strip())
        for match in _QUOTED.finditer(text):
            quotes.add(match.group(1).strip())

    # ── Emerging signals / clusters ──
    for signal in input_data.get('section_b_emerging', []):
        theme = signal.get('theme', '')
        desc = signal.get('description', '')
        text = f"{theme} {desc}"
        for match in _PROPER_NOUN_MULTI.finditer(text):
            entities.add(match.group(1).strip())
        for match in _PROPER_NOUN_SINGLE.finditer(text):
            candidate = match.group(1).strip()
            if len(candidate) >= 3 and candidate.lower() not in _STOP_WORDS:
                entities.add(candidate)
        # Problem IDs in clusters may reference extraction descriptions
        for pid_desc in signal.get('problem_descriptions', []):
            for match in _PROPER_NOUN_SINGLE.finditer(str(pid_desc)):
                candidate = match.group(1).strip()
                if len(candidate) >= 3 and candidate.lower() not in _STOP_WORDS:
                    entities.add(candidate)

    # ── Clusters ──
    for cluster in input_data.get('clusters', []):
        theme = cluster.get('theme', '')
        desc = cluster.get('description', '')
        text = f"{theme} {desc}"
        for match in _PROPER_NOUN_MULTI.finditer(text):
            entities.add(match.group(1).strip())
        for match in _PROPER_NOUN_SINGLE.finditer(text):
            candidate = match.group(1).strip()
            if len(candidate) >= 3 and candidate.lower() not in _STOP_WORDS:
                entities.add(candidate)

    # ── Tool stats ──
    for tool in input_data.get('trending_tools', []):
        tool_name = tool.get('tool_name', '')
        if tool_name:
            entities.add(tool_name)
        # Add specific metrics as grounded statistics
        for field in ['mentions_30d', 'mentions_7d', 'total_mentions',
                      'recommendation_count', 'complaint_count']:
            val = tool.get(field)
            if val is not None:
                statistics.add(f"{val} mentions")
                statistics.add(str(val))
        sentiment = tool.get('avg_sentiment')
        if sentiment is not None:
            statistics.add(str(round(sentiment, 3)))
            statistics.add(str(round(sentiment, 2)))
        # Ground common Tool Radar template numbers ("7 days", "30 days")
        # These reference the time windows used in tool_stats fields
        statistics.add('7 days')
        statistics.add('30 days')
        # Add alternatives as entities
        for alt in (tool.get('top_alternatives') or []):
            if isinstance(alt, str) and len(alt) >= 3:
                entities.add(alt)

    # ── Predictions ──
    for pred in input_data.get('predictions', []):
        text = pred.get('prediction_text', pred.get('prediction', pred.get('description', '')))
        for match in _PROPER_NOUN_MULTI.finditer(text):
            entities.add(match.group(1).strip())
        for match in _PROPER_NOUN_SINGLE.finditer(text):
            candidate = match.group(1).strip()
            if len(candidate) >= 3 and candidate.lower() not in _STOP_WORDS:
                entities.add(candidate)
        for match in _DATE.finditer(text):
            dates.add(match.group(0).strip())

    # ── Analyst insights ──
    for insight in input_data.get('analyst_insights', []):
        if isinstance(insight, dict):
            text = str(insight.get('key_findings', ''))
        else:
            text = str(insight)
        for match in _PROPER_NOUN_SINGLE.finditer(text):
            candidate = match.group(1).strip()
            if len(candidate) >= 3 and candidate.lower() not in _STOP_WORDS:
                entities.add(candidate)

    # ── Tool warnings ──
    for tool in input_data.get('tool_warnings', []):
        tool_name = tool.get('tool_name', '')
        if tool_name:
            entities.add(tool_name)

    # ── Author names from premium source posts ──
    for post in input_data.get('premium_source_posts', []):
        author = post.get('author', '')
        if author and len(author) >= 3:
            entities.add(author)

    # ── Narrative context (prior editions — entities mentioned there are grounded) ──
    ctx = input_data.get('narrative_context', {})
    for edition in ctx.get('editions', []):
        title = edition.get('title', '') + ' ' + edition.get('title_impact', '')
        for match in _PROPER_NOUN_SINGLE.finditer(title):
            candidate = match.group(1).strip()
            if len(candidate) >= 3 and candidate.lower() not in _STOP_WORDS:
                entities.add(candidate)

    return {
        'entities': entities,
        'statistics': statistics,
        'dates': dates,
        'quotes': quotes,
    }


def verify_draft(prose: str, input_data: dict) -> dict[str, Any]:
    """Run Phase D verification on a newsletter draft.

    Returns a verification report with:
    - items_checked: total verifiable items found in prose
    - verified: items that trace to building blocks
    - ungrounded: items that don't trace to any block
    - false_positive_candidates: items flagged but likely OK (for tuning)
    - summary: { total, verified_count, ungrounded_count, rate }
    """
    claims = _extract_claims_from_prose(prose)
    blocks = _build_block_list(input_data)

    verified = []
    ungrounded = []

    # ── Match entities ──
    block_entities_lower = {e.lower() for e in blocks['entities']}
    for entity in claims['entities']:
        if entity.lower() in block_entities_lower:
            verified.append({'type': 'entity', 'value': entity, 'verdict': 'VERIFIED'})
        else:
            # Fuzzy: check if entity is a substring of any block entity or vice versa
            fuzzy_match = any(
                entity.lower() in be or be in entity.lower()
                for be in block_entities_lower
                if len(be) >= 4  # don't fuzzy-match short strings
            )
            if fuzzy_match:
                verified.append({'type': 'entity', 'value': entity, 'verdict': 'VERIFIED (fuzzy)'})
            else:
                ungrounded.append({'type': 'entity', 'value': entity, 'verdict': 'UNGROUNDED'})

    # ── Match statistics ──
    block_stats_set = blocks['statistics']
    block_stats_text = ' '.join(str(s) for s in block_stats_set)
    # Build a set of all raw numbers in blocks for loose matching
    block_numbers = set()
    for s in block_stats_set:
        block_numbers.update(re.findall(r'[\d,.]+', str(s)))

    for stat in claims['statistics']:
        numbers_in_stat = re.findall(r'[\d,.]+', stat)
        # For reversed claims like "Documented cases: 12", require stricter matching:
        # the full claim text (minus the number) should appear in block descriptions too
        is_reversed = bool(re.match(r'[A-Za-z]', stat))  # starts with text, not number
        if is_reversed:
            # Strict: the full string must appear in blocks, or both the number AND
            # surrounding context words must appear
            matched = stat in block_stats_set
        else:
            # Standard: number + unit matching
            matched = (
                stat in block_stats_set
                or any(n in block_stats_set for n in numbers_in_stat)
                or any(n in block_stats_text for n in numbers_in_stat
                       if len(n) >= 2 and n not in {'10', '12', '14', '15', '20', '25', '30'})
            )
            # For common small numbers, require the unit to also match
            if not matched and numbers_in_stat:
                for n in numbers_in_stat:
                    # "N mentions" → check if N matches a tool_stats mentions field
                    if 'mentions' in stat.lower() or 'days' in stat.lower():
                        matched = n in block_numbers
                        break

        if matched:
            verified.append({'type': 'statistic', 'value': stat, 'verdict': 'VERIFIED'})
        else:
            ungrounded.append({'type': 'statistic', 'value': stat, 'verdict': 'UNGROUNDED'})

    # ── Match dates ──
    block_dates_lower = {d.lower() for d in blocks['dates']}
    for date in claims['dates']:
        if date.lower() in block_dates_lower:
            verified.append({'type': 'date', 'value': date, 'verdict': 'VERIFIED'})
        else:
            ungrounded.append({'type': 'date', 'value': date, 'verdict': 'UNGROUNDED'})

    # ── Match quotes ──
    block_quotes_text = ' '.join(blocks['quotes']).lower()
    all_source_text = ' '.join(
        f"{p.get('title', '')} {p.get('summary', '')}"
        for p in input_data.get('premium_source_posts', [])
    ).lower()
    for quote in claims['quotes']:
        # Check if substantial portion of quote appears in source text
        quote_words = quote.lower().split()
        # Match if 60%+ of words appear in source text in sequence
        if (quote.lower() in block_quotes_text
                or quote.lower() in all_source_text
                or any(quote.lower() in str(v).lower()
                       for v in input_data.get('section_b_emerging', []))):
            verified.append({'type': 'quote', 'value': quote[:80], 'verdict': 'VERIFIED'})
        else:
            ungrounded.append({'type': 'quote', 'value': quote[:80], 'verdict': 'UNGROUNDED'})

    # ── Classify ungrounded items into severity tiers ──
    tier1 = []  # Confirmed fabrications: named entities not in any source
    tier2 = []  # Likely fabrications: numbers/stats without source matches
    tier3 = []  # Possible issues: signal titles, framings, dates without exact match

    for item in ungrounded:
        if item['type'] == 'entity':
            # Bold-header entities or multi-word product names → Tier 1
            # Single common words that leaked through → Tier 3
            val = item['value']
            words = val.split()
            if len(words) >= 2 or (len(words) == 1 and val[0].isupper() and len(val) >= 4):
                tier1.append({**item, 'tier': 1, 'tier_label': 'CONFIRMED FABRICATION'})
            else:
                tier3.append({**item, 'tier': 3, 'tier_label': 'POSSIBLE ISSUE'})
        elif item['type'] == 'statistic':
            tier2.append({**item, 'tier': 2, 'tier_label': 'LIKELY FABRICATION'})
        elif item['type'] == 'date':
            tier2.append({**item, 'tier': 2, 'tier_label': 'LIKELY FABRICATION'})
        elif item['type'] == 'quote':
            tier1.append({**item, 'tier': 1, 'tier_label': 'CONFIRMED FABRICATION'})

    all_ungrounded = tier1 + tier2 + tier3
    total = len(verified) + len(all_ungrounded)

    # ── Tier 4: Link coverage check ──
    # Only check link coverage in sections that SHOULD have links:
    # Read This Skip the Rest and Emerging Signals only.
    # Tool Radar, Predictions, and Gato's Corner don't require links.
    _LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

    # Extract only linkable sections (Read This + Emerging Signals)
    _NO_LINK_SECTIONS = re.compile(
        r'##\s*(?:Tool Radar|Prediction Tracker|Gato.s Corner).*',
        re.IGNORECASE
    )

    linkable_prose = prose
    no_link_match = _NO_LINK_SECTIONS.search(prose)
    if no_link_match:
        linkable_prose = prose[:no_link_match.start()]

    inline_links = _LINK_PATTERN.findall(linkable_prose)
    # Build both exact anchor texts AND individual words from anchor texts
    # so "Khosla Ventures" matches a link on "[Khosla Ventures]" or "[Khosla]"
    link_texts = set()
    link_words = set()
    for text, url in inline_links:
        link_texts.add(text.lower())
        for w in text.lower().split():
            if len(w) >= 4:
                link_words.add(w)

    # Only check entities that appear in the linkable sections
    linkable_clean = re.sub(r'[#*_`\[\]()]', ' ', linkable_prose).lower()
    anchorable_in_linkable = [
        v for v in verified
        if v['type'] == 'entity' and v['value'].lower() in linkable_clean
    ]

    # Build set of entity names that are linked (for sub-entity dedup)
    linked_entities = set()

    # Entity is "linked" if:
    # 1. Exact entity text appears as link anchor, OR
    # 2. Entity is substring of a link anchor or vice versa, OR
    # 3. Word-level overlap between entity words and link anchor words, OR
    # 4. Entity appears within 200 chars of an inline link (context-linked)
    #
    # Sub-entity rule: if entity X is a substring of entity Y and Y is
    # linked, X is considered covered (e.g. "Ian" covered by "Ian Crosby")

    # Find link positions in linkable prose for proximity check
    link_positions = [m.start() for m in _LINK_PATTERN.finditer(linkable_prose)]

    entities_without_links = []
    for ent in anchorable_in_linkable:
        ent_lower = ent['value'].lower()
        # Check 1: exact match
        if ent_lower in link_texts:
            linked_entities.add(ent_lower)
            continue
        # Check 2: entity is a substring of a link anchor or vice versa
        if any(ent_lower in lt or lt in ent_lower for lt in link_texts if len(lt) >= 4):
            linked_entities.add(ent_lower)
            continue
        # Check 3: word-level overlap between entity words and link anchor words
        ent_words = {w for w in ent_lower.split() if len(w) >= 4}
        if ent_words and ent_words & link_words:
            linked_entities.add(ent_lower)
            continue
        # Check 4: proximity — entity appears within 200 chars of any link
        ent_pos = linkable_clean.find(ent_lower)
        if ent_pos >= 0 and any(abs(ent_pos - lp) < 200 for lp in link_positions):
            linked_entities.add(ent_lower)
            continue
        entities_without_links.append(ent['value'])

    # Sub-entity dedup: remove entities that are substrings of linked entities
    if entities_without_links:
        still_unlinked = []
        for ent_val in entities_without_links:
            ent_lower = ent_val.lower()
            # Check if this entity is a substring of any linked entity
            if any(ent_lower in le or le in ent_lower
                   for le in linked_entities if len(le) >= 4):
                continue
            still_unlinked.append(ent_val)
        entities_without_links = still_unlinked

    tier4 = {
        'total_inline_links': len(inline_links),
        'linkable_entities_checked': len(anchorable_in_linkable),
        'entities_without_links': entities_without_links,
        'link_coverage_rate': round(
            1 - len(entities_without_links) / max(len(anchorable_in_linkable), 1), 2
        ),
    }

    return {
        'items_checked': total,
        'verified': verified,
        'tier1_fabrications': tier1,
        'tier2_likely': tier2,
        'tier3_possible': tier3,
        'all_ungrounded': all_ungrounded,
        'tier4_link_coverage': tier4,
        'summary': {
            'total': total,
            'verified_count': len(verified),
            'ungrounded_count': len(all_ungrounded),
            'ungrounded_rate': round(len(all_ungrounded) / total, 2) if total > 0 else 0,
            'tier1_count': len(tier1),
            'tier2_count': len(tier2),
            'tier3_count': len(tier3),
            'link_coverage': tier4['link_coverage_rate'],
        },
        'block_entities_available': len(blocks['entities']),
        'block_stats_available': len(blocks['statistics']),
    }
