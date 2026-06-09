#!/usr/bin/env python3
"""Anon-key post-publish economy_map verification harness (Phase 18, D-05).

Proves — from the perspective of a real, unprivileged site visitor — that the
Phase-18 batch publish actually landed: it reads with the ANON key (NO
service_role, NO preview flag) so it sees EXACTLY what production exposes. With
the anon key, RLS returns ONLY `status='published'` body versions (033:367-370),
so a body that failed to publish simply will not come back — which the assertions
below catch fail-loud.

It is a SEPARATE harness from scripts/verify_economy_map_crosslinks.py (which reads
DRAFTS with the service_role key) — kept decoupled so the anon published-read path
never couples to the service_role draft-read path (Claude's-Discretion default,
D-05). The existing crosslinks harness is NOT modified.

WHEN TO RUN: this is RUN FOR REAL *after* the publish batch
(scripts/publish_economy_map_batch.py) completes. PRE-PUBLISH it will correctly
report FEWER than the expected published bodies and exit nonzero — that is the
authored fail-loud contract, NOT a defect of authoring.

It asserts (D-05), accumulating ALL failures then sys.exit(1) if any:
  (a) each of the 8 in-scope slugs (hub `agent-economy` + the 7 reconciled blocks)
      has a non-null `blocks.current_body_version_id` whose PUBLISHED body the anon
      key can actually load;
  (b) the hub `agent-economy` specifically resolves its published body (the hub
      renders its published article, not a NULL pointer);
  (c) every `#/map/<slug>` cross-link extracted from the PUBLISHED bodies resolves
      to a slug whose published body the anon key can also load (not merely an
      in-roster slug);
  (d) the anon-visible published-block count is 8 (hub + 7), UP from the pre-phase 2
      (`identity-trust`, `governance-accountability` were the only published blocks)
      — prints the 2 → 8 transition.

The READ idiom mirrors scripts/verify_economy_map_crosslinks.py: direct PostgREST
httpx + `Accept-Profile: economy_map`, raising on any non-2xx so a read failure is
never mistaken for "no rows". NEVER the supabase-py array-membership filter
(CLAUDE.md + P15-D-06: it silent-fails against economy_map) — every body is read by
a per-slug / per-id PostgREST `eq.` query. An empty roster read fails LOUD (never a
vacuous pass).

Run HOST-SIDE (needs config/.env + outbound HTTPS). The script self-loads
config/.env if the env vars are not already exported, so a bare
`python3 scripts/verify_economy_map_publish.py` from the repo root works (the plan
`<automated>` gate runs it that way).
"""

import os
import re
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
                # Strip matched surrounding quotes to match shell `source` semantics.
                if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                    val = val[1:-1]
                last_value[key] = val  # LAST wins (overwrite)
    for key, val in last_value.items():
        if key not in os.environ:
            os.environ[key] = val


_load_env_file(ENV_PATH)

# ── Config ────────────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL")
# D-05: prove EXACTLY what a real visitor sees — the ANON key, NOT service_role,
# NOT a preview flag. With anon, RLS exposes ONLY status='published' body versions
# (033:367-370), so a body that failed to publish never comes back (caught
# fail-loud below). NEVER hardcode a key value.
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")

# The hub + the 7 in-scope reconciled block slugs (Phase-15 locked roster). These
# are the bodies we assert are PUBLISHED (anon-loadable) and whose cross-links we
# resolve against published content. The deferred legal frame is NOT in this set.
SOURCE_SLUGS = [
    "agent-economy",  # the hub
    "identity-trust",
    "memory-context",
    "payments-settlement",
    "autonomy-control",
    "negotiation-coordination",
    "governance-accountability",
    "psychology-disposition",
]

# The hub slug — asserted separately (D-05b: the hub renders its published article).
HUB_SLUG = "agent-economy"

# Expected published-block count AFTER the batch (D-05d): the hub + 7 blocks = 8,
# UP from the pre-phase 2 (only identity-trust + governance-accountability were
# published). The harness prints the 2 → 8 transition.
EXPECTED_PUBLISHED_COUNT = 8
PRE_PHASE_PUBLISHED_COUNT = 2

# The #/map/<slug> href pattern (identical to the crosslinks harness :135). A
# canonical-doc cross-link is `[text](#/map/<slug>)`; we extract over the RAW
# published markdown (the same target set the rendered DOM carries). Broad char
# class so a drift-introduced variant is SURFACED as an off-published miss
# (fail-loud) rather than silently escaping extraction.
CROSSLINK_RE = re.compile(r"#/map/([A-Za-z0-9][\w-]*)")


# ── PostgREST READ idiom (direct httpx + Accept-Profile, ANON key) ────────────


def _economy_map_get(table: str, params: dict) -> list:
    """GET economy_map.<table> via direct PostgREST with the schema-READ header.

    Copied verbatim from scripts/verify_economy_map_crosslinks.py._economy_map_get
    (:141-166). Direct httpx, `Accept-Profile: economy_map`, raises RuntimeError on
    any non-2xx so a read failure is NEVER mistaken for "no rows" (fail-loud). It is
    header-agnostic to which key is passed — here SUPABASE_KEY is the ANON key, so
    RLS returns only published body versions. NO supabase-py array-membership filter
    (CLAUDE.md silent-fail); per-key filters use the PostgREST `eq.` operator.
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


def fetch_roster() -> set:
    """Return the anon-visible `economy_map.blocks` slug roster (cross-link targets).

    Adapts verify_economy_map_crosslinks.py::fetch_roster (:169-186): an EMPTY roster
    is never correct against the live DB — fail loud rather than vacuously "pass"
    every membership check. anon RLS on `blocks` is USING(true) (033:361-364), so the
    roster includes deferred / body-less rows too (the published-body load below is
    what proves a slug actually rendered).
    """
    rows = _economy_map_get("blocks", {"select": "slug"})
    roster = {r["slug"] for r in rows if r.get("slug")}
    if not roster:
        raise RuntimeError(
            "blocks roster came back EMPTY — refusing to verify against an empty "
            "roster (would vacuously pass). Check the anon key / schema / network."
        )
    return roster


def fetch_published_body(slug: str) -> str | None:
    """Return the anon-visible PUBLISHED body_md for a slug, or None if not published.

    Two-step per-slug `eq.` read (NEVER a supabase-py array-membership filter):
      1. read the block row's `current_body_version_id` (the published-body pointer
         the prod site uses); a non-null pointer is required (D-05a);
      2. read that body version by id with the anon key — RLS exposes ONLY published
         versions, so a body that did not publish returns nothing here (caught
         fail-loud by the caller). Mirrors the prod `loadBlock`/`loadHub`
         fetch-by-current_body_version_id path (app.js) and
         verify_economy_map_crosslinks.py's per-slug eq. read shape.
    Returns the published body_md, or None if the pointer is null OR its body is not
    anon-visible (i.e. not published).
    """
    block_rows = _economy_map_get(
        "blocks",
        {
            "select": "slug,current_body_version_id",
            "slug": f"eq.{slug}",
            "limit": 1,
        },
    )
    if not block_rows:
        return None
    version_id = block_rows[0].get("current_body_version_id")
    if not version_id:
        # D-05a: a null pointer means no published body — the visitor sees nothing.
        return None
    body_rows = _economy_map_get(
        "block_body_versions",
        {
            "id": f"eq.{version_id}",
            "select": "body_md,status",
            "limit": 1,
        },
    )
    # anon RLS returns only published versions; a non-published / missing body → None.
    if body_rows and body_rows[0].get("body_md"):
        return body_rows[0]["body_md"]
    return None


def count_published_blocks() -> int:
    """Count the anon-visible blocks whose published body the anon key can load.

    A block is "published" from the visitor's perspective iff its
    current_body_version_id resolves to an anon-visible (published) body. Counting
    via fetch_published_body keeps the count consistent with the per-slug
    assertions (a non-null pointer to a non-published body does NOT count). Counts
    across the in-scope roster — exactly the set whose 2 → 8 transition D-05d asserts.
    """
    n = 0
    for slug in SOURCE_SLUGS:
        if fetch_published_body(slug) is not None:
            n += 1
    return n


# ── Cross-link extraction ─────────────────────────────────────────────────────


def extract_targets(body_md: str) -> list:
    """Every #/map/<slug> target slug in a published body's raw markdown (with repeats).

    Returns a list (NOT a set) so per-source instance counts (which include repeats)
    are preserved. Identical to verify_economy_map_crosslinks.py::extract_targets.
    """
    return CROSSLINK_RE.findall(body_md or "")


# ── The fail-loud post-publish verification (D-05) ────────────────────────────


def run_publish_verification() -> int:
    """The D-05 post-publish assertions (anon). Returns a process exit code.

    Accumulates ALL failures across (a)-(d), prints each, and returns 1 if ANY —
    the accumulate-then-fail-loud shape of verify_economy_map_crosslinks.py::
    run_crosslink_check. Returns 0 only when every in-scope body is published, the
    hub published body resolves, every cross-link resolves against published
    content, and the published-block count equals 8.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        print(
            "ERROR: SUPABASE_URL / SUPABASE_ANON_KEY not set "
            f"(looked in env + {ENV_PATH}). This harness reads with the ANON key — "
            "no service_role, no preview flag (D-05)."
        )
        return 1

    # Fail-loud against an empty/anon-blocked roster read (never vacuous-pass).
    try:
        roster = fetch_roster()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"Anon-visible blocks roster ({len(roster)} slugs): {sorted(roster)}")

    # Resolve every in-scope published body once (anon); reuse for (a)-(d).
    published_bodies: dict = {}  # slug -> body_md (only for those that published)
    missing_published: list = []  # slugs with no anon-visible published body (D-05a/b)

    for slug in SOURCE_SLUGS:
        try:
            body = fetch_published_body(slug)
        except RuntimeError as exc:
            print(f"ERROR reading published body for {slug}: {exc}")
            return 1
        if body is None:
            missing_published.append(slug)
            print(f"  {slug}: NO anon-visible PUBLISHED body (not published)")
        else:
            published_bodies[slug] = body
            print(f"  {slug}: published body resolves ({len(body)} chars)")

    failures: list = []

    # (a) all 8 in-scope slugs have a non-null current_body_version_id whose
    #     published body the anon key can load.
    if missing_published:
        failures.append(
            f"(a) in-scope slug(s) with NO anon-visible published body: "
            f"{missing_published}"
        )

    # (b) the hub agent-economy specifically resolves its published body.
    if HUB_SLUG in missing_published or HUB_SLUG not in published_bodies:
        failures.append(
            f"(b) the hub `{HUB_SLUG}` has NO anon-visible published body — the hub "
            f"would render a NULL pointer / the HUB_STORYLINE fallback, not its "
            f"published article."
        )

    # (c) every cross-link extracted from the PUBLISHED bodies resolves to a slug
    #     whose published body the anon key can also load.
    crosslink_misses: list = []  # (source_slug, target_slug, reason)
    total_instances = 0
    distinct_targets: set = set()
    for slug, body in published_bodies.items():
        targets = extract_targets(body)
        total_instances += len(targets)
        for target in targets:
            distinct_targets.add(target)
            if target not in roster:
                crosslink_misses.append((slug, target, "not in roster"))
            elif fetch_published_body(target) is None:
                crosslink_misses.append(
                    (slug, target, "in roster but NO published body")
                )
    if crosslink_misses:
        for source_slug, target, reason in crosslink_misses:
            failures.append(
                f"(c) {source_slug} -> #/map/{target}: {reason} "
                f"(cross-link does not resolve against published content)"
            )

    # (d) the anon-visible published-block count equals 8 (hub + 7), up from 2.
    published_count = len(published_bodies)
    print(
        f"\nPublished-block transition (D-05d): "
        f"{PRE_PHASE_PUBLISHED_COUNT} -> {published_count} "
        f"(expected {PRE_PHASE_PUBLISHED_COUNT} -> {EXPECTED_PUBLISHED_COUNT})"
    )
    if published_count != EXPECTED_PUBLISHED_COUNT:
        failures.append(
            f"(d) anon-visible published-block count is {published_count}, "
            f"expected {EXPECTED_PUBLISHED_COUNT} (hub + 7)."
        )

    if failures:
        print("\nFAIL: post-publish verification did not pass (anon perspective):")
        for f in failures:
            print(f"  {f}")
        return 1

    print(
        f"\nPASS: all {EXPECTED_PUBLISHED_COUNT} in-scope bodies published (anon-visible), "
        f"the hub `{HUB_SLUG}` published article resolves, all {total_instances} "
        f"cross-link instance(s) -> {len(distinct_targets)} distinct target(s) resolve "
        f"against PUBLISHED content, and the published-block count is "
        f"{PRE_PHASE_PUBLISHED_COUNT} -> {published_count}."
    )
    print(f"  distinct cross-link targets: {sorted(distinct_targets)}")
    return 0


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    unknown = [a for a in sys.argv[1:]]
    if unknown:
        print(f"ERROR: unknown flag(s): {unknown} (this harness takes no flags)")
        sys.exit(3)

    print("===== D-05 post-publish verification (anon, fail-loud) =====")
    rc = run_publish_verification()
    if rc:
        print(f"\nRESULT: FAIL (rc={rc})")
        sys.exit(rc)
    print("\nRESULT: PASS — the published set is live and visitor-visible.")
    sys.exit(0)


if __name__ == "__main__":
    main()
