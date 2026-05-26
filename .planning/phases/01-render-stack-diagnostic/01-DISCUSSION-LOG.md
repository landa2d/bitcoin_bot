# Phase 1: Render-Stack Diagnostic - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 1-render-stack-diagnostic
**Areas discussed:** Audit scope (live probes)

---

## Gray-Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Spec source-of-truth | Capture the build spec v2 text as a committed file vs. leave ephemeral and write a self-contained findings doc | (default applied) |
| Audit scope (live probes) | Just describe the path from code reading, OR actively run live probes (anon-key reads, browser CSP test, throwaway probe schema) | ✓ |
| Recommendation depth | Bare answer ("reuse SPA + new hash routes") vs. concrete bridge to Phase 4 (file-diff sketch, route structure, query shape, RLS policies) | (default applied) |
| None — use defaults | Skip discussion; apply defaults across all areas and write CONTEXT.md | |

**User's choice:** Audit scope (live probes) only — other two areas accepted default treatment.

---

## Audit scope (live probes)

| Option | Description | Selected |
|--------|-------------|----------|
| Browser CSP + Accept-Profile path | Open DevTools on the live aiagentspulse.com SPA, run a fetch against the existing eu_ai_act schema with `Accept-Profile: eu_ai_act`. Validates that the SPA can reach a non-public schema and CSP doesn't block it. ~5 min, zero writes. | |
| Anon-key read against eu_ai_act | Server-side curl from the dev machine using the anon key + `Accept-Profile`. Confirms the schema-isolation pattern returns rows for an anon role. ~10 min, zero writes. | |
| Throwaway probe schema (economy_map_probe) | Apply a tiny migration that creates `economy_map_probe.test_row` with one row and an anon-read RLS policy. Probe it. Drop after. Highest-confidence answer to "can the SPA read economy_map" before Phase 2 lands the real schema. ~20 min, one migration up + one down. | |
| Describe-only — no probes | Phase 2 will land the real schema anyway; deferring all RLS / CSP validation there is acceptable. Phase 1 stays purely diagnostic-from-reading. | ✓ |

**User's choice:** Describe-only — no probes.
**Notes:** Honors the spec's "Do not build anything" constraint strictly. Phase 2's discuss-phase should re-open RLS / `Accept-Profile` / supabase-js anon-key behavior if its schema work surfaces unexpected issues. Phase 1 findings must flag these as known unknowns so Phase 2 doesn't lose sight of them.

---

## Defaults Applied (no discussion)

### Spec source-of-truth
- **Applied:** Commit the build spec v2 text as `.planning/docs/economy-map-build-spec-v2.md`.
- **Phase 1 findings** update Section 6 of the spec **by reference** (cite path + section number); do not duplicate the spec's content into the findings doc.

### Recommendation depth
- **Applied:** Bare recommendation — the existing publish path is fully reusable.
- **Phase 1 findings** name the path (hash routes in `app.js`, supabase-js queries with `.schema('economy_map')`, no sibling Caddy route) and flag known unknowns for Phase 4.
- **Phase 1 findings** do **not** include a file-diff sketch or proposed RLS policy text — those belong to Phase 4 planning.

## Claude's Discretion

- Findings document format (Markdown structure, heading hierarchy, section ordering) — mirror the build spec's Section 6 (Hub / Block / Status / Re-render trigger) plus "Known unknowns" and "Implications for Phase 4" sections.
- Whether to include screenshots or stack diagrams in the findings — optional; include only if they materially help downstream agents.
- How prominently to surface the Supabase exposed-schemas allowlist as a Phase 2 prerequisite — recommended as a clear callout, since it's the smallest-but-easiest-to-miss requirement.

## Deferred Ideas

- **Live probes** (browser CSP test, anon-key read against `eu_ai_act`, throwaway `economy_map_probe` schema) — explicitly skipped here; revisit in Phase 2 if its schema work surfaces issues.
- **Deep-link / SEO improvements for block pages** — hash routes are SPA-appropriate but not crawlable. Pair with REQUIREMENTS.md v2 `DSGN-*` items in a future design pass.
- **Static-route generation / prerendering** — Out of v1. The SPA-only pattern is the chosen v1 path; consider only if SEO or first-paint becomes a real concern.
