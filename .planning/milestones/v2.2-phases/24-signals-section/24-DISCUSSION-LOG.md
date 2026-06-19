# Phase 24: Signals Section - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-16
**Phase:** 24-signals-section
**Areas discussed:** Anon exposure surface, "View all" affordance, Row display semantics, Fail-loud surfacing

---

## Anon exposure surface (SIGNAL-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal public view | View exposing only id/title/source_url/source/scraped_at for source_tier=1; anon GRANT on the view; base table stays anon-blocked. Column-minimized + structural. | ✓ |
| Blanket row policy on the table | Anon SELECT RLS policy on source_posts WHERE source_tier=1; simplest, but exposes body/score/author/metadata of every tier-1 row. | |
| Narrowed view + RLS belt-and-suspenders | The view AND keep base-table RLS with no anon policy for defense-in-depth. | |

**User's choice:** Minimal public view
**Notes:** Operator's reasoning — RLS is row-level and can't hide columns, so the frontend selecting 4 columns is not a security boundary; narrow the exposure at the data layer. View security mode/schema/naming left to research/planner within the column ceiling.

---

## "View all" affordance (SIGNAL-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Expand in place | Render ~12–15, "View all"/"Show more" reveals the rest inline to a bounded higher cap (~50); no route. Honors the section-not-route revision. | ✓ |
| Reinstate #/signals deep route | Add a #/signals detail route listing the full feed; "view all" links there. Deep-linkable but resurrects a folded route. | |
| Link to newest source externally | "View all" links off-site; no canonical external destination — poor fit. | |

**User's choice:** Expand in place
**Notes:** Keeps the single-scroll landing intact; exact cap numbers (default ~12–15, hard ~50) left to planner.

---

## Row display semantics (SIGNAL-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Hostname from source_url | Display domain = www-stripped hostname from source_url (e.g. deepmind.google), computed at render; internal `source` as fallback. | ✓ |
| Internal source label | Show stored `source` (e.g. rss_deepmind, hackernews) — internal jargon, not a domain. | |
| Hostname + curated display-name map | Hostname with an operator-curated prettifier; nicer but adds a map to maintain — beyond this phase. | |

**User's choice:** Hostname from source_url
**Notes:** Working defaults accepted — date = scraped_at (only reliable temporal column; no published_at); rows with null source_url excluded since each row must be a safe external link. Curated display-name map noted as deferred polish.

---

## Fail-loud surfacing (SIGNAL-04)

| Option | Description | Selected |
|--------|-------------|----------|
| Distinguish by response | Non-2xx / PostgREST error → loud inline diagnostic + console.error; 200 rows → render; 200 [] → benign empty state. View makes misconfig an error, not an empty 200. | ✓ |
| Treat any empty as failure | Loud diagnostic on any empty result regardless of cause — cries wolf on a thin tier-1 week. | |
| Health-probe before render | Lightweight probe to confirm the path is alive, then fetch; adds a second request for marginal benefit. | |

**User's choice:** Distinguish by response
**Notes:** The view+grant design makes a missing migration surface as an HTTP error (not 200 []), so a broken feed fails loud while a genuinely quiet week reads as a benign empty state.

---

## Claude's Discretion

- Exact cap numbers (default ~12–15, expand hard cap ~50).
- View `security_invoker`/schema/naming, within the D-01 exposure ceiling.
- The `scraped_at` ordering tie-break column (e.g. `id`).
- Diagnostic + empty-state copy; whether expand re-queries or slices a pre-fetched batch.

## Deferred Ideas

- Curated source display-name map (hostname → pretty name) — possible later polish, below this phase's value bar.
- Surfacing the source-published date from `metadata` JSONB — deferred; `scraped_at` suffices for v1 and `metadata` is not exposed by the view.
