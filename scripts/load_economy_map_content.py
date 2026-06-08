#!/usr/bin/env python3
"""One-shot economy_map canonical-body loader (Phase 16, LOAD-01/02/03).

Parses the 8 numbered canonical `.md` bodies (`.planning/docs/00-hub.md` ..
`07-psychology-disposition.md`), validates the WHOLE batch up front (D-04),
halts loud before any insert if any field is missing/empty (D-05), applies the
`building -> emerging` maturity remap (P15-D-01), and inserts each as a
`block_body_versions` DRAFT via direct PostgREST with `Content-Profile:
economy_map` (D-01). It NEVER writes a `blocks` row and NEVER sets
`status`/`published_at`/`maturity`/`current_body_version_id`.

Run HOST-SIDE (NOT inside the processor container — it is not copied there;
there is no /scripts/ path in the container). It needs only SUPABASE_URL /
SUPABASE_KEY (from config/.env) + outbound HTTPS:

    source /root/bitcoin_bot/config/.env && python3 /root/bitcoin_bot/scripts/load_economy_map_content.py

Add --dry-run to validate + skip-check only (no POST):

    source /root/bitcoin_bot/config/.env && python3 /root/bitcoin_bot/scripts/load_economy_map_content.py --dry-run

Self-contained per D-01: it REPLICATES the three processor functions
(`_economy_map_get`, `block_has_open_draft`, the body-version insert) rather
than importing from the processor module (avoids triggering its module-level
init). Direct PostgREST httpx only — NO supabase-py (`.in_()` silent-fails
against economy_map; CLAUDE.md + P15-D-06).
"""

import glob
import os
import sys

import httpx
import yaml

# ── Config ──────────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

# DOCS_DIR is overridable (env or set at runtime) so the negative-path test can
# point the loader at a deliberately-broken fixture dir. The count==8 assertion
# below is gated on the DEFAULT dir only — a fixture dir may legitimately differ.
DEFAULT_DOCS_DIR = ".planning/docs"
DOCS_DIR = os.getenv("ECONOMY_MAP_DOCS_DIR", DEFAULT_DOCS_DIR)

# The 8 in-scope slugs (hub + the 7 reconciled blocks). Phase-15 locked roster.
LOCKED_ROSTER = {
    "agent-economy",
    "identity-trust",
    "memory-context",
    "payments-settlement",
    "autonomy-control",
    "negotiation-coordination",
    "governance-accountability",
    "psychology-disposition",
}

# building -> emerging at load time (P15-D-01); no ALTER TYPE, no doc edit.
# Only 01/02/03 carry `maturity: building`.
MATURITY_REMAP = {"building": "emerging"}

# The verified 5-member live enum (033:46-52). `building` is NOT a member —
# proposed_maturity is append-only (no post-insert fix path), so the post-remap
# value MUST be in this set at INSERT or the gate rejects the whole batch loud.
LIVE_MATURITY = {"nascent", "emerging", "contested", "consolidating", "mature"}

# The hub has no `maturity` in its frontmatter (D-05 special-case); seed default.
HUB_MATURITY = "nascent"

# The pinned input glob: matches EXACTLY the 8 numbered bodies (00-*..07-*) and
# excludes the three frontmatter-less docs in the same dir (EXECUTION_BRIEF.md,
# REDESIGN_BRIEF.md, economy-map-build-spec-v2.md). A bare *.md would pull those
# in and (correctly, per D-04 validate-all) halt every live run misleadingly.
INPUT_GLOB = "[0-9][0-9]-*.md"
EXPECTED_COUNT = 8


# ── PostgREST I/O (replicated from the processor per D-01, NOT imported) ──────


def _economy_map_get(table: str, params: dict) -> list:
    """GET economy_map.<table> via direct PostgREST with the schema-READ header.

    Replicates agentpulse_processor._economy_map_get (:3088). Raises RuntimeError
    on any non-2xx so a read failure is NEVER mistaken for "no rows" (which would
    pile up duplicate drafts). Note: READ uses `Accept-Profile` (not Content-).
    """
    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        params=params,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Accept-Profile": "economy_map",
        },
        timeout=10,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"economy_map {table} read failed ({resp.status_code}): {resp.text}"
        )
    rows = resp.json()
    return rows if isinstance(rows, list) else []


def block_has_open_draft(slug: str) -> bool:
    """Return True if the block already has a status='draft' body version.

    Replicates agentpulse_processor.block_has_open_draft (:3124) — the idempotent
    skip-if-open-draft fast-path for a safe re-run (Claude's Discretion in
    CONTEXT). The 041 UNIQUE-open-draft index is the structural backstop. Raises
    on read failure (a transient error must never be mistaken for "no draft").
    """
    rows = _economy_map_get(
        "block_body_versions",
        {"block_slug": f"eq.{slug}", "status": "eq.draft", "select": "id", "limit": 1},
    )
    return bool(rows)


def insert_block_body_version(row: dict) -> dict:
    """INSERT one economy_map.block_body_versions DRAFT via direct PostgREST.

    Replicates agentpulse_processor.economy_map_insert_block_body_version (:3174)
    — a SINGLE purpose-scoped writer (threat T-16-WS), NOT a generic
    schema-agnostic writer. Payload keys are exactly block_slug, body_md,
    proposed_maturity (+ optional synthesized_from_through, validator_report);
    `status` is intentionally OMITTED so the DB default 'draft' applies. NEVER
    writes a blocks row; NEVER sets published_at / current_body_version_id /
    maturity (autonomy boundary). Raises on any non-2xx.
    """
    resp = httpx.post(
        f"{SUPABASE_URL}/rest/v1/block_body_versions",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
            "Content-Profile": "economy_map",
        },
        json=row,
        timeout=10,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"economy_map block_body_versions insert failed "
            f"({resp.status_code}): {resp.text}"
        )
    rows = resp.json()
    return rows[0] if isinstance(rows, list) and rows else rows


# ── Parse + validate ─────────────────────────────────────────────────────────


def parse_doc(path: str) -> dict:
    """Parse one canonical `.md` into a record: frontmatter + body.

    Frontmatter is YAML delimited by `---` / `---`; the body is everything after
    the second `---`. The hub (00-hub.md) carries no `tier`/`maturity` (D-05);
    blocks carry slug/tier/title/subtitle/order/maturity.
    """
    text = open(path, encoding="utf-8").read()
    fm = {}
    body = text
    if text.startswith("---"):
        # split on the frontmatter fence: ['', <yaml>, <body...>]
        parts = text.split("---", 2)
        if len(parts) == 3:
            fm = yaml.safe_load(parts[1]) or {}
            body = parts[2]
    if not isinstance(fm, dict):
        fm = {}

    record = {
        "path": path,
        "slug": fm.get("slug"),
        "type": fm.get("type"),
        "tier": fm.get("tier"),
        "title": fm.get("title"),
        "subtitle": fm.get("subtitle"),
        "order": fm.get("order"),
        "raw_maturity": fm.get("maturity"),
        "body_md": body,
    }
    return record


def computed_maturity(record: dict) -> str | None:
    """The post-remap proposed_maturity for a record.

    Hub -> the seed default ('nascent'). Block -> the building->emerging remap
    applied to its raw frontmatter maturity. Returns None if a block is missing
    its maturity entirely (validate_all reports that as a failure).
    """
    if record.get("type") == "hub":
        return HUB_MATURITY
    raw = record.get("raw_maturity")
    if raw is None:
        return None
    return MATURITY_REMAP.get(raw, raw)


def validate_all(records: list) -> None:
    """Pre-flight gate (D-04/D-05): validate the WHOLE batch, then raise.

    Collects ALL failures across every record (validate-ALL, not fail-on-first)
    and raises a single ValueError listing every one if any exist. MUST run to
    completion across the batch BEFORE any POST — a broken input rejects the
    whole batch (no partial load). Checks per record:
      - slug present and in LOCKED_ROSTER
      - title, subtitle, order present
      - block: tier present, maturity present; hub: type == 'hub'
      - body_md non-empty after .strip()  (the DB NOT NULL does NOT catch '')
      - post-remap proposed_maturity in LIVE_MATURITY
    """
    failures: list[str] = []
    for record in records:
        where = record.get("path") or record.get("slug") or "<unknown>"
        slug = record.get("slug")
        rtype = record.get("type")

        if not slug:
            failures.append(f"{where}: missing slug")
        elif slug not in LOCKED_ROSTER:
            failures.append(f"{where}: slug '{slug}' not in the locked roster")

        for field in ("title", "subtitle"):
            if not record.get(field):
                failures.append(f"{where}: missing {field}")
        if record.get("order") is None:
            failures.append(f"{where}: missing order")

        if rtype == "hub":
            # hub special-case: no tier / no maturity expected (D-05).
            pass
        else:
            if not record.get("tier"):
                failures.append(f"{where}: missing tier")
            if record.get("raw_maturity") is None:
                failures.append(f"{where}: missing maturity")

        body = record.get("body_md")
        if not isinstance(body, str) or body.strip() == "":
            failures.append(f"{where}: empty body_md (whitespace-only is not allowed)")

        maturity = computed_maturity(record)
        if maturity is None:
            # block missing maturity already reported above; avoid a duplicate.
            if rtype == "hub":
                failures.append(f"{where}: hub maturity could not be resolved")
        elif maturity not in LIVE_MATURITY:
            failures.append(
                f"{where}: post-remap maturity '{maturity}' not in {sorted(LIVE_MATURITY)}"
            )

    if failures:
        raise ValueError(
            "validate_all failed — the whole batch is rejected (no partial load):\n  "
            + "\n  ".join(failures)
        )


# ── Discovery + orchestration ────────────────────────────────────────────────


def discover_docs() -> list:
    """Enumerate inputs via the pinned glob, fail loud if the default count != 8.

    The count==8 assertion is gated on the DEFAULT docs dir only — a fixture-dir
    override may legitimately yield a different count (the validate-all gate is
    what protects a fixture run).
    """
    paths = sorted(glob.glob(os.path.join(DOCS_DIR, INPUT_GLOB)))
    if DOCS_DIR == DEFAULT_DOCS_DIR and len(paths) != EXPECTED_COUNT:
        print(
            f"ERROR: expected exactly {EXPECTED_COUNT} numbered bodies in "
            f"{DOCS_DIR} (glob {INPUT_GLOB}), found {len(paths)}: {paths}"
        )
        sys.exit(1)
    return paths


def build_payload(record: dict) -> dict:
    """Build the bodies-only insert payload (status intentionally OMITTED).

    Keys are exactly block_slug, body_md, proposed_maturity. NEVER published_at /
    current_body_version_id / maturity / status.
    """
    return {
        "block_slug": record["slug"],
        "body_md": record["body_md"],
        "proposed_maturity": computed_maturity(record),
    }


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE_URL / SUPABASE_KEY not set")
        sys.exit(1)

    paths = discover_docs()
    records = [parse_doc(p) for p in paths]

    # D-04 pre-flight: validate the WHOLE batch BEFORE any insert. A single
    # failure rejects the whole batch (no partial load). Convert the raised
    # ValueError into a loud nonzero exit so the operator sees it.
    try:
        validate_all(records)
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    inserted = 0
    skipped = 0
    for record in records:
        slug = record["slug"]
        try:
            if block_has_open_draft(slug):
                print(f"SKIP {slug}: already has an open draft (idempotent re-run)")
                skipped += 1
                continue
            row = build_payload(record)
            if dry_run:
                print(f"DRY-RUN would insert draft for {slug} "
                      f"(proposed_maturity={row['proposed_maturity']})")
                continue
            insert_block_body_version(row)
            print(f"INSERTED draft for {slug} "
                  f"(proposed_maturity={row['proposed_maturity']})")
            inserted += 1
        except (ValueError, RuntimeError) as exc:
            # Fail loud on an insert/transport failure mid-batch (the re-run is
            # safe — skip-if-open-draft completes the remainder).
            print(f"ERROR inserting {slug}: {exc}")
            sys.exit(1)

    print(f"DONE: inserted={inserted} skipped={skipped} dry_run={dry_run}")


if __name__ == "__main__":
    main()
