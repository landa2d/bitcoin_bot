#!/usr/bin/env python3
"""Operator-gated economy_map batch publish (Phase 18, PUB-01 / D-06/D-07/D-08).

Flips the Phase-16 loaded-but-unpublished economy_map content LIVE in ONE
operator-approved batch. It resolves the 8 in-scope OPEN drafts (the hub
`agent-economy` + the 7 reconciled blocks — NEVER the deferred legal frame,
P15-D-02 / D-06), prints a confirmation MANIFEST for a SINGLE operator approval
gate, then loops the EXISTING atomic `economy_map.publish_block_version(p_version_id)`
RPC (migration 039) over each draft — the 7 blocks FIRST and the hub LAST (D-07)
so that when the hub framing article goes live every pillar it references already
resolves to a published page.

It reuses the sanctioned publish path verbatim (never a raw UPDATE), mirroring:
  - scripts/load_economy_map_content.py — the standalone-script + config/.env +
    direct-PostgREST + Accept-Profile READ + validate-all-then-act idiom; and
  - docker/gato_brain/gato_brain.py::_economy_map_rpc / handle_map_approve — the
    WRITE/RPC POST shape (Content-Profile, /rpc/<fn>, json=params, check 200/204)
    and the "already actioned" idempotency marker.

KEY (service_role required): drafts are RLS-invisible to anon AND
`publish_block_version` is GRANTed to service_role ONLY (mig 039:82). So this
script reads + writes with the SERVICE_ROLE key from config/.env — never a
hardcoded key. Prefer the explicit SUPABASE_SERVICE_KEY; fall back to
SUPABASE_KEY (the loader's fallback).

FAIL-LOUD GOVERNANCE (D-08, MEMORY: fail_loud_governance):
  - PRE-FLIGHT: every one of the 8 expected slugs MUST resolve to exactly one
    open draft BEFORE any POST. If any is missing, print the missing list and
    sys.exit(1) — no partial pass.
  - MID-BATCH: the RPC's typed RAISE `version % not found or not in draft status`
    (mig 039:59) is the idempotency signal — an already-published version is an
    idempotent SKIP/success (so a re-run completes a halted batch). Any OTHER
    RuntimeError HALTs immediately, reports which slugs published / which remain,
    and sys.exit(1) — never continue silently to a partial-pass.

Run HOST-SIDE from the main tree (needs config/.env + outbound HTTPS). The script
self-loads config/.env if the env vars are not already exported, so a bare
`python3 scripts/publish_economy_map_batch.py` from the repo root works (the plan
`<automated>` gate runs it that way). Add --dry-run to print the manifest and skip
ALL POSTs (no live publish):

    python3 scripts/publish_economy_map_batch.py --dry-run

NEVER uses supabase-py / the array-membership filter (CLAUDE.md + P15-D-06: it
silent-fails against economy_map) — every draft is resolved by a per-slug
PostgREST `eq.` read.
"""

import os
import sys

import httpx

# ── Repo + config location ────────────────────────────────────────────────────

# scripts/ -> repo root
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(REPO_ROOT, "config", ".env")


def _load_env_file(path: str) -> None:
    """Populate os.environ from config/.env, matching docker-compose env_file semantics.

    config/.env may carry the SAME key on multiple lines (e.g. a placeholder
    SUPABASE_URL early + the real one later). Both docker-compose `env_file` and a
    shell `source` resolve duplicates as **LAST occurrence wins** — so this parser
    MUST too, or a clean-env run would pick the stale early placeholder. We:
      1. read every KEY=VALUE line, keeping the LAST value seen per key, then
      2. apply to os.environ only for keys NOT already exported (a value already in
         the real shell environment — e.g. from `source .env &&` — already reflects
         last-wins and must take precedence over the file).
    Minimal parser (no export prefix, no interpolation). Never raises if the file
    is absent; the SUPABASE_* presence check below fails loud instead.
    """
    if not os.path.isfile(path):
        return
    last_value: dict = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key:
                val = val.strip()
                # Strip matched surrounding quotes to match shell `source` semantics
                # (a quoted SUPABASE_SERVICE_KEY="eyJ..." otherwise yields a quoted
                # value → auth fails).
                if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                    val = val[1:-1]
                last_value[key] = val  # LAST wins (overwrite)
    for key, val in last_value.items():
        if key not in os.environ:
            os.environ[key] = val


_load_env_file(ENV_PATH)

# ── Config ────────────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL")
# service_role REQUIRED: drafts are RLS-invisible to anon AND publish_block_version
# is GRANTed to service_role only (mig 039:82). Prefer explicit SERVICE_KEY, fall
# back to KEY (the loader's fallback). NEVER hardcode a key value.
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

# The 8 in-scope slugs in PUBLISH order (D-07): the 7 reconciled blocks FIRST, then
# the hub `agent-economy` LAST — so when the hub framing article goes live every
# pillar it references already resolves to a published page. The deferred legal
# frame (P15-D-02 / D-06) is EXPLICITLY excluded — it appears in NO line here.
PUBLISH_ORDER = [
    "identity-trust",
    "memory-context",
    "payments-settlement",
    "autonomy-control",
    "negotiation-coordination",
    "governance-accountability",
    "psychology-disposition",
    "agent-economy",  # the hub — LAST (D-07)
]

# The hub slug (LAST in PUBLISH_ORDER) — named for the manifest annotation.
HUB_SLUG = "agent-economy"

# The RPC's typed RAISE substring (mig 039:59) — the idempotency signal. Matched as
# a substring of the raised RuntimeError; an already-published version is a SKIP.
_RPC_ALREADY_ACTIONED = "not found or not in draft status"


# ── PostgREST READ idiom (direct httpx + Accept-Profile) ──────────────────────


def _economy_map_get(table: str, params: dict) -> list:
    """GET economy_map.<table> via direct PostgREST with the schema-READ header.

    Copied verbatim from scripts/load_economy_map_content.py._economy_map_get (the
    Phase-16 loader idiom). Raises RuntimeError on any non-2xx so a read failure is
    NEVER mistaken for "no rows" (which would make pre-flight falsely report a
    missing draft). READ uses `Accept-Profile` (NOT Content-Profile). Per-key
    filters use the PostgREST `eq.` operator — NEVER the supabase-py
    array-membership filter (CLAUDE.md silent-fail rule).
    """
    resp = httpx.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        params=params,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Accept-Profile": "economy_map",
        },
        timeout=15,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"economy_map {table} read failed ({resp.status_code}): {resp.text}"
        )
    rows = resp.json()
    return rows if isinstance(rows, list) else []


# ── PostgREST WRITE/RPC idiom (direct httpx + Content-Profile + /rpc/) ─────────


def _economy_map_rpc(fn: str, params: dict) -> httpx.Response:
    """POST a parameterized RPC against economy_map via PostgREST (the WRITE surface).

    Copied from docker/gato_brain/gato_brain.py::_economy_map_rpc (:1636-1669) with
    the gato_brain caller-controlled allowlist DROPPED — this is a standalone
    single-RPC caller that only ever invokes the literal "publish_block_version".
    WRITE uses the schema-WRITE header Content-Profile: economy_map (NOT
    Accept-Profile), the /rpc/<fn> endpoint, and `json=params` (values are NEVER
    interpolated into the URL path or body). publish_block_version RETURNS void →
    the (200, 204) check covers it. On any non-2xx this RAISES RuntimeError carrying
    resp.text so the DB's typed RAISE is preserved for the idempotency match
    (fail-loud — a failed write must never read as a benign no-op).
    """
    resp = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Content-Profile": "economy_map",
        },
        json=params,
        timeout=15,
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(
            f"economy_map rpc {fn} failed ({resp.status_code}): {resp.text}"
        )
    return resp


# ── Draft resolution (D-06 step 1) ────────────────────────────────────────────


def resolve_open_draft(slug: str) -> dict | None:
    """Return {version_id, proposed_maturity} for a slug's latest OPEN draft, or None.

    Per-slug PostgREST `eq.` read (mirrors verify_economy_map_crosslinks.py::
    fetch_draft_body :189-209 but selects id,proposed_maturity instead of body_md).
    Migration 041 guarantees at most ONE open draft per slug, so this returns 0 or 1
    row. NEVER a supabase-py array-membership filter (CLAUDE.md silent-fail).
    """
    rows = _economy_map_get(
        "block_body_versions",
        {
            "block_slug": f"eq.{slug}",
            "status": "eq.draft",
            "select": "id,proposed_maturity",
            "order": "created_at.desc",
            "limit": 1,
        },
    )
    if rows and rows[0].get("id"):
        return {
            "version_id": rows[0]["id"],
            "proposed_maturity": rows[0].get("proposed_maturity"),
        }
    return None


def read_old_maturity(slug: str) -> str | None:
    """Return the block's CURRENT maturity (the old→new manifest column).

    Mirrors docker/gato_brain/gato_brain.py::get_block_by_slug (:1697-1716): a
    per-slug `eq.` read of `economy_map.blocks.maturity`. Read-only; raises on a
    non-2xx (fail-loud) via _economy_map_get. Returns None when no block row exists.
    """
    rows = _economy_map_get(
        "blocks",
        {
            "select": "slug,maturity",
            "slug": f"eq.{slug}",
            "limit": 1,
        },
    )
    if rows:
        return rows[0].get("maturity")
    return None


def resolve_all() -> dict:
    """Resolve every PUBLISH_ORDER slug to its open draft + old/new maturity.

    Returns `resolved`: slug -> {version_id, proposed_maturity, old_maturity}. A slug
    with no open draft is simply absent from the mapping (the D-08 pre-flight below
    computes the missing set against PUBLISH_ORDER). A READ failure raises (fail-loud
    — never mistaken for "no draft").
    """
    resolved: dict = {}
    for slug in PUBLISH_ORDER:
        draft = resolve_open_draft(slug)
        if draft is None:
            continue
        resolved[slug] = {
            "version_id": draft["version_id"],
            "proposed_maturity": draft.get("proposed_maturity"),
            "old_maturity": read_old_maturity(slug),
        }
    return resolved


# ── Manifest (D-06 step 2) ────────────────────────────────────────────────────


def print_manifest(resolved: dict) -> None:
    """Print the single-approval manifest (slug -> version_id -> old→new maturity).

    Printed in PUBLISH_ORDER (blocks first, hub last) for the ONE operator approval;
    the orchestrator surfaces the gate in-chat (mirrors the Phase-16 loader /
    migration-apply pattern). The deferred legal frame is absent by construction
    (P15-D-02 / D-06).
    """
    print("===== economy_map batch-publish MANIFEST (D-06 / D-07) =====")
    print(f"{'#':>2}  {'slug':<28}  {'maturity':<24}  version_id")
    print(f"{'-' * 2}  {'-' * 28}  {'-' * 24}  {'-' * 36}")
    for i, slug in enumerate(PUBLISH_ORDER, start=1):
        entry = resolved[slug]
        old = entry.get("old_maturity") or "?"
        new = entry.get("proposed_maturity") or "?"
        transition = f"{old}→{new}"
        tag = "  (hub — LAST)" if slug == HUB_SLUG else ""
        print(f"{i:>2}  {slug:<28}  {transition:<24}  {entry['version_id']}{tag}")
    print(
        f"\n{len(PUBLISH_ORDER)} in-scope draft(s) to publish — 7 blocks FIRST, the "
        f"hub `{HUB_SLUG}` LAST (D-07)."
    )


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    unknown = [a for a in sys.argv[1:] if a != "--dry-run"]
    if unknown:
        print(f"ERROR: unknown flag(s): {unknown}")
        sys.exit(3)

    if not SUPABASE_URL or not SUPABASE_KEY:
        print(
            "ERROR: SUPABASE_URL / SUPABASE_SERVICE_KEY (or SUPABASE_KEY) not set "
            f"(looked in env + {ENV_PATH}). service_role is REQUIRED — drafts are "
            "RLS-invisible to anon and the publish RPC is GRANTed to service_role only."
        )
        sys.exit(1)

    # Step 1 (D-06): resolve every expected slug's open draft. A read failure raises
    # and is surfaced as a loud nonzero exit (never mistaken for "no draft").
    try:
        resolved = resolve_all()
    except RuntimeError as exc:
        print(f"ERROR resolving open drafts: {exc}")
        sys.exit(1)

    # Step 2 (D-08 PRE-FLIGHT): every expected slug MUST resolve to exactly one open
    # draft BEFORE any POST. Collect ALL misses, print them, and halt — no partial
    # pass (MEMORY: fail_loud_governance).
    missing = [s for s in PUBLISH_ORDER if s not in resolved]
    if missing:
        print(
            f"ERROR: pre-flight failed — no open draft resolved for: {missing}. "
            f"Halting BEFORE publishing anything (no partial pass)."
        )
        sys.exit(1)

    # Step 3 (D-06 step 2): print the manifest for the ONE operator approval gate.
    print_manifest(resolved)

    if dry_run:
        print(
            "\nDRY-RUN: manifest printed, NO publish RPC called. Re-run without "
            "--dry-run after operator approval to publish the batch."
        )
        return

    # Step 4 (D-06 step 3 / D-07): loop the EXISTING publish RPC over PUBLISH_ORDER —
    # 7 blocks FIRST, the hub LAST. Idempotent skip on already-published; HALT and
    # report succeeded/remaining on any OTHER error (D-08, fail-loud).
    published: list = []
    skipped: list = []
    for idx, slug in enumerate(PUBLISH_ORDER):
        version_id = resolved[slug]["version_id"]
        try:
            _economy_map_rpc("publish_block_version", {"p_version_id": version_id})
            published.append(slug)
            print(f"PUBLISHED {slug} ({version_id})")
        except RuntimeError as exc:
            if _RPC_ALREADY_ACTIONED in str(exc):
                # already published/rejected → idempotent SKIP (a re-run completes a
                # halted batch). The RPC is the authoritative draft-status gate.
                skipped.append(slug)
                print(f"SKIP {slug}: already published (idempotent re-run)")
                continue
            # any OTHER failure: HALT immediately — report succeeded / remaining,
            # never continue silently to a partial pass (MEMORY: fail_loud_governance).
            remaining = PUBLISH_ORDER[idx + 1:]
            print(
                f"HALT at {slug}: {exc}\n"
                f"  published so far: {published}\n"
                f"  skipped (already published): {skipped}\n"
                f"  FAILED at: {slug}\n"
                f"  remaining (NOT attempted): {remaining}\n"
                f"  Fix the cause and re-run — the idempotent skip completes the batch."
            )
            sys.exit(1)

    print(f"\nDONE: published={published} skipped={skipped}")


if __name__ == "__main__":
    main()
