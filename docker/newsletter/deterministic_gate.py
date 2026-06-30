"""Phase 28 — Layer 1 deterministic gate (no-LLM).

`run_deterministic_gate(draft, fact_base, prior_edition, *, http_client=None, github_token=None)`
runs BOTH body versions (technical + impact) and EMITS a single structured flags object —
it never acts (D-05): no DB write, no LLM call, no status flip, no verdict computation.

The flags object is the Phase 30 wiring surface, shaped to migration 045's
`deterministic_flags` JSONB:
    {fabrication: [...], unverified: [...], mechanical: [...], meta: {...}}
`unverified` is a first-class top-level key (D-01) — a transient/quota network failure is a
visible "could not verify" state, NEVER folded into `fabrication` and NEVER treated as a pass.

This plan (28-01) ships the fabrication core:
  - REUSE the calibrated `verify_draft` engine (verification.py) for tier-1 named-entity /
    tier-2 stat fabrication detection — inheriting the Edition-34-tuned ~0-tier1-FP stop-list;
    the engine is imported, never rebuilt (D-04).
  - Two net-new fabrication sub-checks layered thin ON TOP of the engine:
      * arXiv-ID membership (GATE-04) — the engine extracts-then-discards arXiv IDs
        (verification.py:287-289) and never tests membership; this closes that gap.
      * entity-merge per-source verbatim (GATE-05) — the engine's fact base is a flat union
        with no per-source provenance (verification.py:309); a composite present only
        split-across two sources is a fabricated merge.

The network layer (GATE-02/03 — GitHub repo+star, URL HEAD) and the mechanical-editorial
checks (GATE-06/07 — H1/title echo, reading-mode-label leak, recycled closer, duplicated stat)
are added by Plans 02 and 03 on top of this skeleton; the `http_client` / `github_token` seams
and the empty `unverified` / `mechanical` lists are already part of the stable contract here
(interface-first).
"""

import os
import re
import socket
import ipaddress
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from verification import verify_draft, _extract_claims_from_prose, _ARXIV_ID, _STATISTIC

logger = logging.getLogger("newsletter")

# ── Module constants (some consumed by later plans; defined here so the contract is stable) ──
# The canonical body-start marker — verbatim per block_pipeline.py:661 (two-hash, comma after
# "This"). Published bodies start here with no H1 (newsletter_poller.py:2120). Plan 03 uses it
# for the H1/title-echo mechanical check.
BODY_START_MARKER = "## Read This, Skip the Rest"

# GATE-06 reading-mode-label leak blacklist. **Operator-tunable** — confirm/adjust this exact
# membership during the Phase 30 report-only calibration window (RESEARCH open question A1);
# the constant is the single tuning point so a too-broad/too-narrow set is a one-line edit.
# Seeded from the code-derived writer scaffolding literals (`AUDIENCE:` — block_pipeline.py:347-350)
# plus the CONTEXT illustrative set. Multi-word uppercase scaffolding only — bare "IMPACT" /
# "Technical" are legitimate prose and are DELIBERATELY NOT blacklisted (they appear constantly
# in edited prose; blacklisting them would flood `mechanical` with false positives).
READING_MODE_LABELS = [
    "AUDIENCE:", "READING MODE", "BUILDER MODE", "IMPACT MODE",
    "TECHNICAL MODE", "STRATEGIC MODE", "TECHNICAL READING MODE",
    "IMPACT READING MODE", "STRATEGIC READING MODE",
    "TECHNICAL VERSION", "IMPACT VERSION", "STRATEGIC VERSION",
]

# Net-new regexes. Simple bounded character classes only — no nested quantifiers / no
# catastrophic backtracking (T-28-01 ReDoS mitigation).
_GITHUB_URL = re.compile(r'github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)', re.IGNORECASE)
_MD_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^)\s]+)\)')
# Bare http(s) URLs (the URL HEAD layer, Plan 02 Task 2). Bounded char-class only (no nested
# quantifiers — T-28-01 ReDoS mitigation); stops at whitespace and common closers.
_BARE_URL = re.compile(r'https?://[^\s)>\]]+')
# An asserted star count adjacent to a repo ref (GATE-02 star-drift). Bounded — `[\d,]+` then a
# non-overlapping optional decimal, an optional k/m magnitude, then the literal unit word.
_STAR_ASSERTION = re.compile(r'([\d,]+(?:\.\d+)?)\s*([kKmM]?)\s*(?:stars|stargazers)', re.IGNORECASE)

# GATE-06 mechanical regexes (net-new this plan). Simple line-anchored patterns — no nested
# quantifiers (T-28-09 ReDoS mitigation). `_H1_LINE` matches a single-hash `# ` H1 line (the
# `[ \t]` second char excludes the legitimate two-hash `## ` body-start marker). `_HEADER_LINE`
# captures the text of any 1–6 hash markdown header line for the title-echo comparison.
_H1_LINE = re.compile(r'^#[ \t]', re.MULTILINE)
_HEADER_LINE = re.compile(r'^#{1,6}[ \t]+(.+)$', re.MULTILINE)

# SSRF denylist (T-28-04): the compose internal-service names + localhost. A draft-supplied URL
# whose host is any of these (or a literal private/loopback/link-local IP, or a `*.internal`
# host) is routed to `unverified` (reason=unsafe_host) and is NEVER fetched.
_INTERNAL_SERVICE_HOSTS = {
    "llm-proxy", "supabase", "gato_brain", "gato-brain", "processor",
    "analyst", "research", "newsletter", "web", "lab-data-provider",
    "localhost",
}


def run_deterministic_gate(
    draft: dict,
    fact_base: dict,
    prior_edition: dict | None,
    *,
    http_client: httpx.Client | None = None,
    github_token: str | None = None,
) -> dict:
    """Run the no-LLM deterministic gate over both body versions. EMITS flags only — never
    acts (D-05): no DB write, no LLM call, no status flip, no verdict computed.

    Args:
        draft: {title, title_impact, content_markdown, content_markdown_impact,
                pipeline_version} — both bodies are processed.
        fact_base: the ALREADY-CORRECT in-memory fact base for this draft version — single-pass
            `input_data` OR a block_v1 dict {blocks, tracked_entity_signals, trending_tools,
            predictions}. The gate TRUSTS the handed dict (GATE-08); it does not re-derive which
            base to use — Phase 30 selects it via the existing poller branch.
        prior_edition: the FULL previous-published edition as
            {content_markdown, content_markdown_impact, edition_number}, or None. Drives the
            GATE-07 cross-edition mechanical checks (recycled closer + duplicated stat,
            normalized-exact per D-06): the technical body compares against `content_markdown`,
            the impact body against `content_markdown_impact`. When None (no prior edition) the
            cross-edition checks skip cleanly without raising; GATE-06 still runs. Phase 30
            supplies the FULL prior body (NOT load_edition_context's truncated excerpt — A3).
        http_client: injectable httpx client (tests inject a fake). When provided, the network
            layer (GATE-02 GitHub + GATE-03 URL HEAD) runs against it; when None, NO network
            check runs (zero egress) and the network counters stay 0. A default client is
            deliberately NOT constructed for None — Phase 30 injects a real httpx.Client.
        github_token: GitHub token override; defaults to os.getenv('GITHUB_TOKEN'). Sent only to
            api.github.com over HTTPS; never logged, never placed in the flags object (T-28-05).

    Returns:
        {fabrication: [...], unverified: [...], mechanical: [...], meta: {...}} — matching
        migration 045 deterministic_flags JSONB plus the first-class `unverified` key (D-01).
    """
    # Fail loud (carry-forward 27-CONTEXT "an error is not evidence"): a wrong/missing fact base
    # must surface, never silently verify against an empty/other base (T-28-03 / Pitfall 3).
    if not isinstance(fact_base, dict):
        raise ValueError(
            "run_deterministic_gate: fact_base must be a dict, got "
            f"{type(fact_base).__name__} — refusing to verify against a wrong/missing fact base"
        )

    # GATE-08 loud-path log: which path verify_draft will take. Log only the label (never raw
    # draft prose at INFO — T-28-02 log-injection mitigation).
    fact_base_path = "blocks" if fact_base.get("blocks") else "input_data"
    logger.info("deterministic_gate: verifying against fact_base_path=%s", fact_base_path)

    fabrication: list[dict[str, Any]] = []
    mechanical: list[dict[str, Any]] = []
    tier1_count = {"technical": 0, "impact": 0}

    # GATE-01: run BOTH body versions through the SAME engine (mirrors verify_draft tech+impact
    # at poller:1756-1757), aggregating into ONE flags object.
    versions = [
        ("technical", draft.get("content_markdown", "") or "", draft.get("title", "") or ""),
        ("impact", draft.get("content_markdown_impact", "") or "", draft.get("title_impact", "") or ""),
    ]

    # Per-source provenance for the two net-new fabrication sub-checks (GATE-04/05). Built once;
    # the flat engine union (verification.py:309) lacks this provenance.
    source_texts = _fact_base_source_texts(fact_base)

    # GATE-07 cross-edition inputs — the FULL prior-published edition body per version (a
    # Phase-30 wiring responsibility; the gate trusts the dict it is handed, A3). When
    # prior_edition is None there is no prior edition → the cross-edition checks skip cleanly.
    prior_number = prior_edition.get("edition_number") if prior_edition else None
    prior_bodies = {
        "technical": (prior_edition or {}).get("content_markdown", "") or "",
        "impact": (prior_edition or {}).get("content_markdown_impact", "") or "",
    }

    for label, body, title in versions:
        if not body.strip():
            continue

        # ── Reused engine (D-04): tier-1 named-entity fabrications (GATE-04/05 base) ──
        report = verify_draft(body, fact_base)
        for item in report.get("tier1_fabrications", []):
            fabrication.append({
                "kind": "tier1_entity",
                "value": item.get("value"),
                "version": label,
            })
        tier1_count[label] = report["summary"]["tier1_count"]

        # ── Net-new fabrication sub-checks layered ON TOP of the reused engine ──
        fabrication.extend(_check_arxiv_membership(body, source_texts, label))
        fabrication.extend(_check_entity_merge(body, source_texts, label))

        # ── Mechanical-editorial checks (GATE-06) — flag into `mechanical`, NEVER
        # `fabrication`. An H1/title echo or a leaked reading-mode/audience label is an
        # editorial miss (may feed the Phase 29 rewrite loop), not a hard fabrication hold.
        mechanical.extend(_check_h1_and_title_echo(body, title, label))
        mechanical.extend(_check_reading_mode_leak(body, label))

        # ── Cross-edition mechanical checks (GATE-07, D-06) — recycled closer + duplicated
        # stat vs the FULL prior-published edition. Normalized-exact only (no fuzzy). When
        # prior_edition is None, prior_bodies[label] is "" → _check_cross_edition skips cleanly.
        mechanical.extend(_check_cross_edition(body, prior_bodies[label], label, prior_number))

    # ── Network-liveness layer (GATE-02/03, D-01/D-02/D-03) ──────────────────────────────────
    # Runs ONLY when an http_client is injected. We deliberately do NOT construct a default
    # client when http_client is None: that preserves the Plan-01 contract (http_client=None →
    # zero egress, github/urls_checked==0) and guarantees the test suite never touches the
    # network. The Phase 30 live caller injects a real httpx.Client(timeout=5).
    unverified: list[dict[str, Any]] = []
    github_checked = 0
    urls_checked = 0
    if http_client is not None:
        # Token read from param/env ONLY; sent only to api.github.com over HTTPS; never logged,
        # never placed in the flags object (T-28-05). The per-run dedup cache (D-03) is shared
        # across the GitHub and URL layers (distinct ("gh",..) / ("url",..) key prefixes).
        effective_token = github_token or os.getenv("GITHUB_TOKEN")
        cache: dict[tuple, Any] = {}
        gh_fab, gh_unv, github_checked = _run_github_layer(
            versions, client=http_client, token=effective_token, cache=cache
        )
        fabrication.extend(gh_fab)
        unverified.extend(gh_unv)
        # GATE-03 URL HEAD layer — reuses the same `cache` (D-03) and populates `urls_checked`.
        url_fab, url_unv, urls_checked = _run_url_layer(
            versions, client=http_client, cache=cache
        )
        fabrication.extend(url_fab)
        unverified.extend(url_unv)

    return {
        "fabrication": fabrication,
        # `unverified` is a first-class top-level key (D-01) — a transient/quota network failure
        # is a visible "could not verify" state, NEVER folded into fabrication and NEVER a pass.
        "unverified": unverified,
        # Mechanical-editorial misses (GATE-06/07) — H1/title echo, reading-mode-label leak,
        # recycled closer, duplicated stat. Distinct from `fabrication`: never a hard hold.
        "mechanical": mechanical,
        "meta": {
            "fact_base_path": fact_base_path,
            "github_checked": github_checked,
            "urls_checked": urls_checked,
            "github_token_present": bool(github_token or os.getenv("GITHUB_TOKEN")),
            "tier1_count": tier1_count,
        },
    }


def _fact_base_source_texts(fact_base: dict) -> list[str]:
    """Return a PER-SOURCE (NOT unioned) list of raw text strings, mirroring the field
    accessors `_build_block_list` reads (verification.py:299-480) but keeping each item
    separate. This is the per-source provenance the flat engine union (verification.py:309)
    lacks — consumed by the arXiv-membership (GATE-04) and entity-merge (GATE-05) checks.

    Does NOT touch `_build_block_list`, `_STOP_WORDS`, or the tier classifier (FP-regression
    risk).
    """
    texts: list[str] = []

    blocks = fact_base.get("blocks") or []
    if blocks:
        # block_v1 path: each block contributes description + its named_entities.
        for block in blocks:
            ents = " ".join(str(e) for e in (block.get("named_entities") or []))
            texts.append(f"{block.get('description', '')} {ents}".strip())
        # Tracked entity signals (same shape as blocks) — block path only, mirroring the engine.
        for signal in fact_base.get("tracked_entity_signals", []) or []:
            ents = " ".join(str(e) for e in (signal.get("named_entities") or []))
            texts.append(f"{signal.get('description', '')} {ents}".strip())
    else:
        # single-pass path: each premium source post / emerging signal / cluster as its own item.
        for post in fact_base.get("premium_source_posts", []) or []:
            texts.append(
                f"{post.get('title', '')} {post.get('summary', '')} "
                f"{post.get('source_display', '')}".strip()
            )
        for signal in fact_base.get("section_b_emerging", []) or []:
            texts.append(f"{signal.get('theme', '')} {signal.get('description', '')}".strip())
        for cluster in fact_base.get("clusters", []) or []:
            texts.append(f"{cluster.get('theme', '')} {cluster.get('description', '')}".strip())

    # Tool / prediction text per item — read by the engine in BOTH paths (verification.py:407,432).
    for tool in fact_base.get("trending_tools", []) or []:
        name = tool.get("tool_name", "")
        alts = " ".join(str(a) for a in (tool.get("top_alternatives") or []))
        texts.append(f"{name} {alts}".strip())
    for pred in fact_base.get("predictions", []) or []:
        texts.append(
            str(pred.get("prediction_text", pred.get("prediction", pred.get("description", "")))).strip()
        )

    return [t for t in texts if t]


def _check_arxiv_membership(body: str, source_texts: list[str], version: str) -> list[dict]:
    """GATE-04: flag any arXiv ID in the body that does NOT appear verbatim in the concatenated
    fact-base source text. Closes the extract-then-discard gap (verification.py:287-289) — the
    engine removes arXiv IDs from the stat set but never tests membership. A real arXiv ID
    present in a source is clean (the ed-36 fake-arXiv golden fixture).
    """
    flags: list[dict] = []
    # WR-03: test membership against the SET of arXiv IDs EXTRACTED from the sources (same
    # `\b`-anchored `_ARXIV_ID` pattern used on the body), NOT a raw substring of the joined text.
    # A bare `id not in concatenated` silently grounds a fabricated ID that is a substring of a
    # longer real ID present in a source (body `2605.9999` ⊂ source `2605.99999`) or of any
    # unrelated digit run — a missed fabrication. Exact-ID set membership is anchored and
    # symmetric with the extraction boundaries.
    source_ids = {m.group(0) for s in source_texts for m in _ARXIV_ID.finditer(s)}
    seen: set[str] = set()
    for match in _ARXIV_ID.finditer(body):
        arxiv_id = match.group(0)
        if arxiv_id in seen:
            continue
        seen.add(arxiv_id)
        if arxiv_id not in source_ids:
            flags.append({
                "kind": "arxiv",
                "id": arxiv_id,
                "version": version,
                "detail": "arXiv ID not present in fact base",
            })
    return flags


def _check_entity_merge(body: str, source_texts: list[str], version: str) -> list[dict]:
    """GATE-05: the per-source verbatim entity-merge refinement (NOT a rebuild). Restrict to
    COMPOSITE entities — multi-word entities (`len(split()) >= 2`) from the reused
    `_extract_claims_from_prose`, plus any `owner/repo` token captured by `_GITHUB_URL` in the
    body. Flag a composite iff its full string does NOT appear (case-insensitive) within at
    least ONE single source string. Appearing only split-across separate sources == a fabricated
    merge (the engine's flat union + fuzzy substring match masks this — verification.py:499-514).
    Single-word entities are left entirely to the reused verify_draft tier1 path.
    """
    flags: list[dict] = []
    lowered_sources = [s.lower() for s in source_texts]

    composites: list[str] = []
    seen: set[str] = set()

    # Multi-word entities from the reused extractor (do NOT re-roll extraction).
    for entity in _extract_claims_from_prose(body).get("entities", []):
        if len(entity.split()) >= 2:
            key = entity.lower()
            if key not in seen:
                seen.add(key)
                composites.append(entity)

    # owner/repo tokens captured by the GitHub-URL regex in the body (the `/` breaks the
    # _PROPER_NOUN tokenizer, so the engine never sees these as single entities).
    for match in _GITHUB_URL.finditer(body):
        owner_repo = f"{match.group(1)}/{match.group(2)}"
        key = owner_repo.lower()
        if key not in seen:
            seen.add(key)
            composites.append(owner_repo)

    for composite in composites:
        c_lower = composite.lower()
        # (1) Grounded: the full composite appears verbatim within a SINGLE source → clean. This
        # is the only "verbatim in one source" gate; everything below is the cross-source path.
        if any(c_lower in src for src in lowered_sources):
            continue
        tokens = [t for t in c_lower.split() if t]
        # (2) A single-token composite (notably an `owner/repo` token — it has no whitespace to
        # split on) cannot be a cross-source MERGE: there are no parts to split across sources.
        # Repo liveness is the GitHub layer's job (a live repo is verified there, a dead one is
        # flagged `github_repo`); never double-flag a grounded/live repo as a fabricated merge
        # here (WR-01 case B — GATE-02 verified vs GATE-05 fabricated was contradictory).
        if len(tokens) < 2:
            continue
        # (3) Honor the docstring contract — flag ONLY a genuine cross-source merge. Every part
        # must appear in SOME source (else a wholly-absent token is a tier-1 problem the reused
        # verify_draft engine already owns — defer, don't double-flag). AND no SINGLE source may
        # contain ALL the parts: if one source supplies them all, the composite is merely phrased
        # differently within that source ("Acme's Widgets" → "Acme Widgets", WR-01 case A) — a
        # tier-1 fuzzy-match concern, NOT a fabricated cross-source merge. What survives is a
        # composite whose parts are split across ≥2 DISTINCT sources, preserving the Edition-34
        # ~0-FP calibration intent rather than introducing a new strict-verbatim FP path.
        if not all(any(tok in src for src in lowered_sources) for tok in tokens):
            continue
        if any(all(tok in src for tok in tokens) for src in lowered_sources):
            continue
        flags.append({
            "kind": "entity_merge",
            "entity": composite,
            "version": version,
        })
    return flags


# ── Network-liveness layer (GATE-02/03, D-01/D-02/D-03) + SSRF guard ─────────────────────────
# This is the security-critical surface: URLs and owner/repo refs are extracted from untrusted
# LLM-generated draft text and used to issue outbound requests. Every check is bounded
# (5s timeout, per-run dedup, sequential), routed through the injected `http_client` seam (no
# real egress in tests), and gated by the SSRF allowlist for the URL HEAD layer.


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True if an IP is in a non-public range we must NEVER fetch (loopback / RFC-1918 private /
    link-local incl. the 169.254.169.254 metadata endpoint / reserved / unspecified / multicast).
    The single predicate applied both to a literal-IP host AND to every resolved address
    (CR-01 / WR-02)."""
    return (ip.is_loopback or ip.is_private or ip.is_link_local
            or ip.is_reserved or ip.is_unspecified or ip.is_multicast)


def _resolve_host(host: str) -> list[str]:
    """Resolve a hostname to its IP string(s) via the OS resolver. Isolated as a single seam so
    the SSRF guard's resolve-then-validate step (CR-01 / WR-02) is fully mockable in tests with
    ZERO real network egress (T-28-04). Raises OSError on resolution failure — the caller treats
    that as unsafe (fail-closed)."""
    return [info[4][0] for info in socket.getaddrinfo(host, None)]


def _is_safe_public_url(url: str) -> bool:
    """SSRF guard (ASVS L1, T-28-04). Return True ONLY for an http(s) URL whose host is a
    public, non-internal destination. Reject:
      - non-http(s) schemes (file:, gopher:, data:, ...),
      - the compose internal-service denylist + `localhost`,
      - any `*.internal` host,
      - literal loopback / RFC-1918 private / link-local (incl. 169.254.169.254 metadata) /
        unique-local / reserved / unspecified / multicast IPs (IPv4 + IPv6),
      - bare single-label hostnames (no dot — treated as internal Docker DNS).
    Used to gate the URL HEAD layer: a rejected URL is routed to `unverified`
    (reason=unsafe_host) and is NEVER fetched (T-28-04 zero-egress guarantee).
    """
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    try:
        host = (parsed.hostname or "").strip().lower()
    except ValueError:
        return False
    if not host:
        return False
    # Internal-service denylist (compose service names) + localhost.
    if host in _INTERNAL_SERVICE_HOSTS:
        return False
    # `*.internal` (and a bare `internal`) — Docker/k8s internal DNS suffix.
    if host == "internal" or host.endswith(".internal"):
        return False
    # Literal (canonical) IP host → reject any non-public range directly, no resolution needed.
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        return not _is_blocked_ip(ip)
    # Not a canonical IP literal. A bare single-label name (no dot) is an internal Docker service
    # alias — reject outright (fail-closed; no resolution needed).
    if "." not in host:
        return False
    # CR-01 / WR-02 — resolve-then-validate. The host is either a registrable DNS name OR a
    # NON-canonical numeric form (127.1, 0x7f.0.0.1, 0177.0.0.1, 10.1, 0xa9.0xfe.0xa9.0xfe) that
    # ipaddress.ip_address rejects but the OS resolver (glibc getaddrinfo, used by the real
    # httpx.Client) collapses to loopback / RFC-1918 / link-local / the metadata IP. Resolve the
    # host and validate EVERY answer, so neither a shorthand/octal/hex literal NOR a public
    # hostname whose A record points at internal space can slip past the string checks. Host text
    # comes verbatim from untrusted (possibly prompt-injected) LLM draft prose, so this is the
    # guard's one job. Fail-closed: resolution failure / no answers / an unparseable answer →
    # unsafe (routed to unverified, zero egress).
    try:
        resolved = _resolve_host(host)
    except OSError:
        return False
    if not resolved:
        return False
    for addr in resolved:
        try:
            candidate = ipaddress.ip_address(addr.split("%")[0])  # strip any IPv6 %scope suffix
        except ValueError:
            return False
        if _is_blocked_ip(candidate):
            return False
    return True


def _classify_github(
    owner: str, repo: str, *, client: httpx.Client, token: str | None
) -> tuple[str, int | None, str | None]:
    """Map a GitHub `/repos/{owner}/{repo}` result into the locked three-outcome taxonomy
    (D-01) with retry-once-on-transient (D-02). Returns (outcome, stars, reason):
      - ("fabricated", None, None)   → HTTP 404 (NEVER retried — D-02).
      - ("verified", stars, None)    → HTTP 200 (stars = stargazers_count or None).
      - ("unverified", None, reason) → 403/429 quota (reason=rate_limit_403, NOT retried),
                                        >=500 (server_error_5xx, retried once),
                                        timeout (retried once), conn_refused (retried once),
                                        other 4xx (http_<code>).
    Headers/token convention copied verbatim from processor:1134-1136. The token is sent ONLY
    to api.github.com over HTTPS and is NEVER logged or returned (T-28-05).
    """
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    url = f"https://api.github.com/repos/{owner}/{repo}"
    for attempt in (1, 2):  # D-02: at most one retry, on transient failures ONLY
        try:
            resp = client.get(url, headers=headers, timeout=5)
        except httpx.TimeoutException:  # incl. PoolTimeout — transient
            if attempt == 1:
                continue
            return ("unverified", None, "timeout")
        except httpx.ConnectError:
            if attempt == 1:
                continue
            return ("unverified", None, "conn_refused")
        except httpx.TooManyRedirects:
            return ("unverified", None, "too_many_redirects")  # not transient — NOT retried
        except httpx.HTTPError:
            # CR-02: the broad transport/protocol family (ReadError, WriteError,
            # RemoteProtocolError, ProxyError, DecodingError, ...) are SIBLINGS of the two
            # specific catches above, not subclasses — uncaught they propagate out of the gate
            # and discard every already-computed fabrication/mechanical flag. Catch the base so a
            # network failure becomes a visible `unverified` ("an error is not evidence"), NEVER a
            # crash and NEVER a silent pass. Retry once like the other transient failures.
            if attempt == 1:
                continue
            return ("unverified", None, "network_error")
        code = resp.status_code
        if code == 404:
            return ("fabricated", None, None)            # D-02: definitive — NEVER retried
        if code in (403, 429):
            return ("unverified", None, "rate_limit_403")  # quota is not transient — no retry
        if code >= 500:
            if attempt == 1:
                continue                                  # D-02: retry once on transient 5xx
            return ("unverified", None, "server_error_5xx")
        if code == 200:
            try:
                stars = resp.json().get("stargazers_count")
            except (ValueError, AttributeError):
                stars = None
            return ("verified", stars, None)
        return ("unverified", None, f"http_{code}")       # other 4xx/3xx → not evidence
    return ("unverified", None, "unknown")  # pragma: no cover — loop always returns above


def _iter_github_refs(body: str) -> list[tuple[str, str]]:
    """Unique (owner, repo) tuples from a body via `_GITHUB_URL` (a trailing `.git` is
    stripped). Deduplicated within the body so each repo flags at most once per version."""
    refs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in _GITHUB_URL.finditer(body):
        owner = match.group(1)
        repo = match.group(2)
        # The repo char-class includes `.`, so a trailing sentence period
        # ("github.com/acme/tool.") is over-captured — strip it (a real GitHub repo name
        # never ends with a dot). Then strip a trailing `.git`.
        repo = repo.rstrip(".")
        if repo.lower().endswith(".git"):
            repo = repo[:-4]
        if not repo:
            continue
        key = (owner.lower(), repo.lower())
        if key not in seen:
            seen.add(key)
            refs.append((owner, repo))
    return refs


def _parse_star_count(text: str) -> int | None:
    """Parse an asserted star count adjacent to a repo ref ("50000 stars", "12,500 stars",
    "2k stars", "1.5k stargazers"). Returns the integer count, or None if none asserted."""
    match = _STAR_ASSERTION.search(text)
    if not match:
        return None
    num_str = match.group(1).replace(",", "")
    try:
        value = float(num_str)
    except ValueError:
        return None
    suffix = match.group(2).lower()
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    return int(value)


def _asserted_star_count_for_ref(body: str, owner: str, repo: str) -> int | None:
    """The star count asserted on the same line as a `github.com/owner/repo` ref, or None.
    Line-scoped adjacency (per CONTEXT "same line/sentence") avoids cross-paragraph mismatch."""
    needle = f"github.com/{owner}/{repo}".lower()
    for line in body.splitlines():
        if needle in line.lower():
            count = _parse_star_count(line)
            if count is not None:
                return count
    return None


def _run_github_layer(
    versions: list[tuple[str, str, str]], *, client: httpx.Client, token: str | None,
    cache: dict[tuple, Any],
) -> tuple[list[dict], list[dict], int]:
    """GATE-02: classify every unique owner/repo ref across both versions into the D-01 taxonomy
    (dedup via the shared per-run `cache`, D-03), and flag >20% star drift on verified repos.
    Returns (fabrication_entries, unverified_entries, unique_repos_checked)."""
    fabrication: list[dict] = []
    unverified: list[dict] = []
    checked: set[tuple[str, str]] = set()
    for label, body, _title in versions:
        if not body.strip():
            continue
        for owner, repo in _iter_github_refs(body):
            cache_key = ("gh", owner.lower(), repo.lower())
            if cache_key not in cache:
                cache[cache_key] = _classify_github(owner, repo, client=client, token=token)
                checked.add((owner.lower(), repo.lower()))
            outcome, stars, reason = cache[cache_key]
            ref_str = f"{owner}/{repo}"
            if outcome == "fabricated":
                fabrication.append({
                    "kind": "github_repo", "ref": ref_str,
                    "version": label, "detail": "GitHub 404",
                })
            elif outcome == "unverified":
                unverified.append({"kind": "github_repo", "ref": ref_str, "reason": reason})
            elif outcome == "verified":
                asserted = _asserted_star_count_for_ref(body, owner, repo)
                if asserted is not None and stars is not None:
                    if abs(asserted - stars) / max(stars, 1) > 0.20:
                        fabrication.append({
                            "kind": "github_stars", "ref": ref_str, "version": label,
                            "detail": f"asserted {asserted} vs live {stars} (>20% drift)",
                        })
    return fabrication, unverified, len(checked)


def _normalize_url(url: str) -> str:
    """Strip trailing sentence punctuation the bare-URL scan over-captures
    ("https://x.com/p." → "https://x.com/p"). Used both as the dedup-cache key and the
    fetched target."""
    return url.rstrip('.,;:!?\'")')


def _iter_urls(body: str) -> list[str]:
    """Unique normalized URLs in a body: markdown-link targets (`_MD_LINK`) plus a bare-URL
    scan (`_BARE_URL`). EXCLUDES `github.com/owner/repo` refs (handled by the GitHub API layer)
    to avoid double-checking. Deduplicated within the body."""
    urls: list[str] = []
    seen: set[str] = set()
    for match in _MD_LINK.finditer(body):
        _add_url(match.group(2), urls, seen)
    for match in _BARE_URL.finditer(body):
        _add_url(match.group(0), urls, seen)
    return urls


def _add_url(raw: str, urls: list[str], seen: set[str]) -> None:
    url = _normalize_url(raw)
    if not url or url in seen:
        return
    # Skip github.com/owner/repo URLs — the GitHub API layer already checks those.
    if _GITHUB_URL.search(url):
        return
    seen.add(url)
    urls.append(url)


def _classify_url(url: str, *, client: httpx.Client) -> tuple[str, str]:
    """Map a URL HEAD result into the locked three-outcome taxonomy (GATE-03, D-01) with
    retry-once-on-transient (D-02). Returns (outcome, reason):
      - SSRF guard FIRST: an unsafe/internal host → ("unverified", "unsafe_host") WITHOUT any
        request (T-28-04 — the host is NEVER fetched).
      - 404/410 → ("fabricated", "http_<code>").
      - timeout (retried once) → ("unverified", "timeout"); conn-refused → "conn_refused".
      - >=500 (retried once) → ("unverified", "server_error_5xx").
      - other 4xx (401/403/429) → ("unverified", "http_<code>") — an auth/rate wall is not
        evidence of fabrication ("an error is not evidence").
      - 200 / redirect-resolved-2xx → ("verified", "ok").
    Only the status code drives the outcome — the response body is never read (T-28-08)."""
    if not _is_safe_public_url(url):
        return ("unverified", "unsafe_host")  # SSRF: never fetched (T-28-04)
    for attempt in (1, 2):  # D-02: at most one retry, on transient failures ONLY
        try:
            resp = client.head(url, timeout=5, follow_redirects=True)
        except httpx.TimeoutException:  # incl. PoolTimeout — transient
            if attempt == 1:
                continue
            return ("unverified", "timeout")
        except httpx.ConnectError:
            if attempt == 1:
                continue
            return ("unverified", "conn_refused")
        except httpx.TooManyRedirects:
            # follow_redirects=True makes this a realistic outcome for parked/dead domains; a
            # redirect loop is not transient — settle on unverified WITHOUT a retry.
            return ("unverified", "too_many_redirects")
        except httpx.HTTPError:
            # CR-02: broad transport/protocol catch-all (ReadError, RemoteProtocolError,
            # ProxyError, DecodingError, WriteError, ...). HEAD-probing dead/flaky/untrusted URLs
            # is exactly the population that raises these — never let one crash the gate and throw
            # away the flags already computed; never collapse into a pass. Retry once.
            if attempt == 1:
                continue
            return ("unverified", "network_error")
        code = resp.status_code
        if code in (404, 410):
            return ("fabricated", f"http_{code}")        # D-02: definitive — NEVER retried
        if code >= 500:
            if attempt == 1:
                continue                                  # D-02: retry once on transient 5xx
            return ("unverified", "server_error_5xx")
        if 400 <= code < 500:
            return ("unverified", f"http_{code}")         # auth/rate wall — not evidence
        return ("verified", "ok")                         # 200 / resolved 2xx
    return ("unverified", "unknown")  # pragma: no cover — loop always returns above


def _run_url_layer(
    versions: list[tuple[str, str, str]], *, client: httpx.Client, cache: dict[tuple, Any],
) -> tuple[list[dict], list[dict], int]:
    """GATE-03: HEAD-check every unique non-github URL across both versions into the D-01
    taxonomy (dedup via the shared per-run `cache`, D-03). Unsafe/internal hosts route to
    `unverified` without a fetch. Returns (fabrication_entries, unverified_entries,
    unique_urls_checked)."""
    fabrication: list[dict] = []
    unverified: list[dict] = []
    checked: set[str] = set()
    for label, body, _title in versions:
        if not body.strip():
            continue
        for url in _iter_urls(body):
            cache_key = ("url", url)
            if cache_key not in cache:
                cache[cache_key] = _classify_url(url, client=client)
                checked.add(url)
            outcome, reason = cache[cache_key]
            if outcome == "fabricated":
                fabrication.append({
                    "kind": "dead_url", "url": url, "version": label,
                    "detail": reason.replace("http_", "HTTP "),
                })
            elif outcome == "unverified":
                unverified.append({"kind": "url", "url": url, "reason": reason})
            # verified → no flag
    return fabrication, unverified, len(checked)


# ── Mechanical-editorial layer (GATE-06/07, D-06) ────────────────────────────────────────────
# Pure string ops on the draft (and, for GATE-07, the FULL prior-published edition body). These
# flag editorial misses into `mechanical` — distinct from `fabrication`, never a hard hold. No
# network, no LLM. The cross-edition checks (GATE-07) use normalized-exact matching (D-06:
# lowercase + collapse whitespace + strip trailing punctuation) — NO fuzzy similarity threshold.


def _check_h1_and_title_echo(body: str, title: str, version: str) -> list[dict]:
    """GATE-06 (part 1): flag a single-hash `# ` H1 line in the body (published bodies start at
    the two-hash `## Read This, Skip the Rest` marker with no H1 — newsletter_poller.py:2120;
    the title is a SEPARATE DB column, never in the body), and flag the edition title echoed as
    a markdown header line in its own body. `title` is the version-appropriate title
    (technical→draft['title'], impact→draft['title_impact']). Whitespace-normalized,
    case-insensitive comparison."""
    flags: list[dict] = []
    if _H1_LINE.search(body):
        flags.append({"kind": "h1_in_body", "version": version})
    title_norm = re.sub(r'\s+', ' ', title).strip().lower()
    if title_norm:
        for match in _HEADER_LINE.finditer(body):
            header_norm = re.sub(r'\s+', ' ', match.group(1)).strip().lower()
            if header_norm == title_norm:
                flags.append({"kind": "title_echo", "version": version, "value": title})
                break
    return flags


def _check_reading_mode_leak(body: str, version: str) -> list[dict]:
    """GATE-06 (part 2): case-insensitive substring scan for each tunable `READING_MODE_LABELS`
    member (uppercase scaffolding tokens like `AUDIENCE:` unlikely in edited prose). On a hit
    emit a `reading_mode_leak` mechanical flag with the matched label. Bare `"IMPACT"` /
    `"Technical"` are NOT in the blacklist, so legitimate prose never trips this."""
    flags: list[dict] = []
    body_lower = body.lower()
    for label in READING_MODE_LABELS:
        if label.lower() in body_lower:
            flags.append({"kind": "reading_mode_leak", "version": version, "label": label})
    return flags


def _normalize(s: str) -> str:
    """D-06 normalized-exact key: collapse internal whitespace, strip, lowercase, strip trailing
    punctuation. Uses a simple linear `\\s+` collapse only — no nested-quantifier pattern
    (T-28-09 ReDoS mitigation). NO fuzzy/similarity transform (D-06: normalized-exact only)."""
    return re.sub(r'\s+', ' ', s).strip().lower().rstrip('.!?,:;—-')


def _closer_line(body: str) -> str:
    """The normalized last non-empty paragraph (split on blank lines) — the closer."""
    paras = [p for p in re.split(r'\n\s*\n', body) if p.strip()]
    return _normalize(paras[-1]) if paras else ""


def _stat_tokens(body: str) -> set[str]:
    """The set of normalized numeric-stat tokens in the body, reusing the engine's `_STATISTIC`
    regex (D-04 — no new number regex)."""
    return {_normalize(m.group(0)) for m in _STATISTIC.finditer(body)}


def _check_cross_edition(
    body: str, prior_body: str, version: str, prior_edition_number: int | None = None,
) -> list[dict]:
    """GATE-07: cross-edition mechanical checks vs the FULL prior-published edition body, using
    normalized-exact matching (D-06 — NO fuzzy threshold). If `prior_body` is empty/None there is
    no prior edition → return `[]` (clean skip, never raise — T-28-11). Otherwise flag:
      - `recycled_closer` iff the normalized closer line is non-empty AND equals the prior
        edition's normalized closer line;
      - `duplicated_stat` (one per token) for every normalized stat token present in BOTH bodies.
    `prior_edition_number` is recorded on each flag for the Phase-30 mapping."""
    if not prior_body:
        return []
    flags: list[dict] = []
    closer = _closer_line(body)
    if closer and closer == _closer_line(prior_body):
        flags.append({
            "kind": "recycled_closer", "version": version,
            "prior_edition": prior_edition_number,
        })
    shared_stats = _stat_tokens(body) & _stat_tokens(prior_body)
    for stat in sorted(shared_stats):
        flags.append({
            "kind": "duplicated_stat", "version": version, "stat": stat,
            "prior_edition": prior_edition_number,
        })
    return flags
