---
phase: 17-cross-link-wiring-preview
reviewed: 2026-06-09T08:05:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - docker/web/site/app.js
  - scripts/verify_economy_map_crosslinks.py
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: resolved
resolved_in: 9b18dc0
---

> **Resolution (2026-06-09, commit `9b18dc0`):** All 4 warnings + IN-03 fixed before phase verification (per the project's fix-review-blockers-before-verify discipline). WR-01 (env-quote stripping), WR-02 (case-insensitive drift regex — verified `#/map/Memory-Context` now extracts → off-roster miss), WR-03 (conflicting/unknown flags exit 3 loudly — verified), IN-03 (degenerate-key warning), WR-04 (hub non-deferred keyed off draft-body existence). 17-01 app.js gates still pass; harness still exits 0 (22→7 in-roster); production no-op preserved. IN-01/IN-02 are documentation-clarity notes (no behavior change required).

# Phase 17: Code Review Report

**Reviewed:** 2026-06-09T08:05:00Z
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Reviewed the two Phase-17 source files at standard depth, scoped to the phase's changes (preview flag, draft-fetch fallbacks, hub-body trim, preview-aware maturity in `app.js`; the new fail-loud cross-link verification harness in `verify_economy_map_crosslinks.py`).

**The KEY INVARIANT holds.** With `PREVIEW_ENABLED=false` (production: no `?preview` param), every new branch short-circuits and the deployed render is byte-for-byte identical to pre-Phase-17 behavior:
- `hubBodyMd` stays `null` → `trimHubBody(null)` returns `null` → falls back to `escapeHtml(HUB_STORYLINE)`.
- `draftMaturity` stays `null` → `previewMaturity=null` → `deferred = !b.current_body_version_id` (unchanged) and `pillArg = b` (unchanged).
- `bodyMd` stays `null` → falls through to the unchanged published-body path.

Lines 4-5 retain the `__SUPABASE_URL__` / `__SUPABASE_ANON_KEY__` placeholders (no literal key). All `.eq('status','draft')` filters are inside `if (PREVIEW_ENABLED)` blocks — the documented, gated inverse of D-17, which is acceptable as scoped. The harness honors the economy_map conventions: direct PostgREST + `Accept-Profile: economy_map`, no supabase-py `.in_()`, per-slug `eq.` filters, service_role key loaded from `config/.env` (never hardcoded), and the off-roster fail-loud `return 1` path is correctly wired (verified the 22-instance / 7-distinct-target expectation matches the actual source docs exactly).

No BLOCKER-class defects (no security vulnerabilities, no data-loss risk, no crash on the production path). Four WARNINGs and three INFO items follow — the two most consequential are the env-parser quote-handling divergence (WR-01, can cause false-negative verification on quoted `.env` values) and the drift-guard's case-sensitive regex (WR-02, lets a malformed cross-link slip extraction entirely — a false-pass against the harness's stated drift-detection purpose).

## Warnings

### WR-01: Env-file parser does not strip surrounding quotes — diverges from the shell-`source` path it documents as supported

**File:** `scripts/verify_economy_map_crosslinks.py:79-90`
**Issue:** `_load_env_file()` does `last_value[key] = val.strip()` but never strips surrounding quote characters. The module docstring (lines 40-43) and `KEY=VALUE` parsing claim to match "docker-compose `env_file` semantics" and explicitly support the `source .env && python3 ...` invocation. But shell `source` *strips* quotes, while this parser keeps them literally. If `config/.env` contains a common quoted form such as `SUPABASE_SERVICE_KEY="eyJ..."`, the in-process self-load path yields a value with literal `"` quotes. Consequences:
- The PostgREST `apikey` / `Authorization` headers carry a quoted key → auth fails → `fetch_roster()` raises `RuntimeError` → caught → `return 1`. The harness fails-loud (not catastrophic) but reports a *false negative* on a legitimately-configured repo, eroding trust in the gate.
- `_distinguishing_substring()` is computed from the quoted key, so the leak-grep needle is mis-derived (it would include/exclude quote chars inconsistently with how a real leak would appear in a tracked file).

Note the loader this harness claims to mirror (`scripts/load_economy_map_content.py`) has NO self-load parser at all — it relies entirely on shell `source`, so the harness's added parser is net-new behavior that silently diverges from the documented `source` path.
**Fix:** Strip matched surrounding quotes after `.strip()`, matching shell semantics:
```python
val = val.strip()
if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
    val = val[1:-1]
last_value[key] = val
```

### WR-02: Cross-link drift regex is case-sensitive — a malformed/case-variant target silently escapes extraction (false-pass against the harness's purpose)

**File:** `scripts/verify_economy_map_crosslinks.py:125, 205-211`
**Issue:** `CROSSLINK_RE = re.compile(r"#/map/([a-z0-9][a-z0-9-]*)")` only matches lowercase-kebab slugs. The harness exists explicitly to "fail-loud on FUTURE content drift" (docstring lines 9-11). But a drift-introduced cross-link such as `[X](#/map/Memory-Context)` or `#/map/Regulation_Legal` is NOT extracted at all — so it is never checked against the roster and the run PASSES. `marked.parse` would still render `#/map/Memory-Context` as a clickable `<a href>` that resolves to nothing in the SPA router (`getRoute()` is case-sensitive on the slug). The guard's core guarantee — "every rendered `#/map/<slug>` resolves to a real block" — does not hold for case/character-variant targets, which is precisely the kind of human-authored drift the harness is meant to catch.
**Fix:** Extract case-insensitively (and over a broader char class) so malformed targets are surfaced as off-roster misses rather than silently dropped:
```python
CROSSLINK_RE = re.compile(r"#/map/([A-Za-z0-9][\w-]*)")
# roster membership is exact-case, so an uppercase target now correctly
# registers as an off-roster miss (fail-loud) instead of being unmatched.
```

### WR-03: Contradictory / unknown CLI flags yield a silent PASS with zero verification

**File:** `scripts/verify_economy_map_crosslinks.py:490-513`
**Issue:** `main()` reads `--guard-only` and `--skip-guard` independently. Passing BOTH (or a typo'd flag combination) sets `guard_only=True` (skips the cross-link check) AND `skip_guard=True` (skips the guard), so neither check runs, `crosslink_rc`/`guard_rc` stay `0`, and the script prints `RESULT: PASS` and `sys.exit(0)`. Unrecognized flags (e.g. `--guardonly`) are also silently ignored. A fail-loud governance harness that exits 0 having run *nothing* directly violates the "never silently default to no-op" principle this script is built to enforce (MEMORY: fail_loud_governance).
**Fix:** Reject the no-op combination and unknown flags loudly:
```python
if guard_only and skip_guard:
    print("ERROR: --guard-only and --skip-guard are mutually exclusive "
          "(would run no checks — refusing to pass vacuously).")
    sys.exit(3)
unknown = [a for a in sys.argv[1:] if a not in ("--guard-only", "--skip-guard")]
if unknown:
    print(f"ERROR: unknown flag(s): {unknown}")
    sys.exit(3)
```

### WR-04: Hub card "draft-bearing" is keyed off `proposed_maturity`, not draft-body presence — inconsistent DEFERRED state vs the block page

**File:** `docker/web/site/app.js:504, 540-541`
**Issue:** In `loadHub()`, `draftMaturity[slug]` is populated only when `r.proposed_maturity` is truthy (line 504 guards `if (r.proposed_maturity)`). `renderTile()` then derives `deferred = !b.current_body_version_id && !previewMaturity` (line 541), so a block whose draft has a non-null `body_md` but a NULL `proposed_maturity` is keyed as having no preview → renders as a full-width DEFERRED card. Meanwhile `loadBlock()` (lines 644-657) sets `bodyMd` from the draft `body_md` regardless of `proposed_maturity`, so the SAME block renders full draft content on its block page. Result: in preview mode a draft-bearing-but-null-maturity block shows "DEFERRED" on the hub yet shows complete synthesized content when clicked — a confusing, self-contradictory preview. (Preview-only path; dormant in prod, so WARNING not BLOCKER.)
**Fix:** Key the hub's "not deferred" decision off the existence of a draft body row (the same signal `loadBlock` uses), independent of `proposed_maturity`. Fetch `block_slug` for every draft body and build a `draftSlugs` set, then:
```javascript
// non-deferred if a draft body exists for this slug (preview), regardless of maturity
var hasDraftBody = draftSlugs && draftSlugs.has(b.slug);
var previewMaturity = (draftMaturity && draftMaturity[b.slug]) ? draftMaturity[b.slug] : null;
var deferred = !b.current_body_version_id && !hasDraftBody;
var pillArg = previewMaturity ? { maturity: previewMaturity } : b;
```

## Info

### IN-01: `regulation_targets` is computed solely for a status print and is dead in the failure path

**File:** `scripts/verify_economy_map_crosslinks.py:275, 287-289`
**Issue:** `regulation_targets` is derived once and only echoed in the success summary. Because any off-roster `regulation-legal` cross-link is already caught by the roster-membership `misses` gate (regulation-legal IS in the roster as a deferred block, so it would NOT be a miss), this variable is a documentation echo, not an assertion. Harmless, but it reads as if it gates something it does not. The summary comment is accurate; leaving a clarifying note that this is informational-only would prevent a future reader from assuming it enforces the "none to regulation-legal" expectation.
**Fix:** Either inline the list comprehension into the print, or add a one-line comment that the "regulation-legal targeted?" line is informational and the membership gate (not this variable) is the contract.

### IN-02: Harness counts hub cross-links that the UI deliberately trims away (`trimHubBody`)

**File:** `scripts/verify_economy_map_crosslinks.py:236-257` (interaction with `docker/web/site/app.js:74-85, 583-586`)
**Issue:** The harness scans the FULL untrimmed `agent-economy` hub `body_md` and counts its 7 `#/map/<slug>` links toward the 22-instance inventory. But the rendered hub passes the body through `trimHubBody()`, which removes the entire Tier-1/Tier-2 prose block-list (and thus those 7 links) before `marked.parse` — they never appear as clickable links on the hub; click-through there is via the card grid. So the harness's "instances rendered as `<a href>`" framing (docstring lines 16-22) overstates the hub by 7 versus what the DOM actually carries. Not a correctness defect (the harness's job is roster-membership of stored targets, and the comment acknowledges card-based click-through), but the inventory semantics are slightly off and could mislead a future maintainer reconciling counts.
**Fix:** Add a note in `extract_targets`/`run_crosslink_check` that the hub body is scanned pre-trim (stored content), so its 7 links are counted even though `trimHubBody` drops them from the rendered hub.

### IN-03: `_distinguishing_substring` produces a weak needle when service_role and anon keys are misconfigured to be identical

**File:** `scripts/verify_economy_map_crosslinks.py:467-484`
**Issue:** When `service_key == anon_key` (an env misconfiguration), the divergence search finds no difference, so `div = n = len(service_key)`, clamped to `len - window` → the needle becomes the last `window` chars of the key. Since the keys are identical, that needle also belongs to the anon key — so the leak-grep would (correctly, in this degenerate case) be unable to distinguish them, but the function returns silently without flagging that its premise (distinct service/anon tokens) was violated. The `if not SUPABASE_KEY` guard (line 405) catches empty keys, so the only residual gap is the silent same-key case. Low impact (requires an env misconfiguration), hence INFO.
**Fix:** When the divergence index reaches `n` (no divergence found) and `anon_key` is non-empty, emit a loud warning that service/anon keys appear identical or one is a prefix of the other, so the operator knows the distinguishing needle is degenerate:
```python
if anon_key and div == n:
    print("WARNING: service_role and anon keys do not diverge within the "
          "shared prefix — distinguishing needle may be ambiguous. Check env.")
```

---

_Reviewed: 2026-06-09T08:05:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
