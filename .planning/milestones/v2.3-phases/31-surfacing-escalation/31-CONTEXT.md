# Phase 31: Surfacing & Escalation - Context

**Gathered:** 2026-07-02
**Status:** Ready for planning

<domain>
## Phase Boundary

The final v2.3 phase (SURF-01..03): make the now-live (report-only) eval's outputs **visible** and its alerts **trustworthy**. Three deliverables:

1. **SURF-01** — harden the processor's `send_telegram` so a held edition never silently fails to alert (today: bare `return` on unset env, warning-level on delivery failure).
2. **SURF-02** — the Friday newsletter notify (`scheduled_notify_newsletter`, today a static one-liner at Friday 12:00 UTC) gains a compact per-draft eval summary read from `edition_evals` via a plain select (no LLM in the Processor).
3. **SURF-03** — a live `/newsletter_eval` (+ `trend`) Gato command: handler in `gato_brain`, added to the `isGatoBrainCommand` allowlist in `inject-gato-brain.mjs`, plus the gato rebuild (worktree-UNSAFE, orchestrator-owned) — otherwise it's a dead command over Telegram.

**In scope:** processor `send_telegram` hardening + critical-caller return checks; the Friday-notify eval section; the `gato_brain` command handler + gato allowlist + rebuilds; a live Telegram plumbing round-trip.

**Out of scope:** the newsletter service (`_alert_operator` already meets the SURF-01 guarantee — untouched this phase, protecting the calibration window); flipping `enforce=true` (operator, 30-04 Task 6); eval-trend regression alerting (OBS-01), threshold auto-tuning (TUNE-01), `edition_revisions` (REV-01), quantitative A/B trend (AB-01) — all deferred v2.3-future items.
</domain>

<decisions>
## Implementation Decisions

### Alert-path hardening (SURF-01)
- **D-01: Harden each service's path in place.** The processor's `send_telegram` is hardened where it lives; the newsletter's `_alert_operator` (already fail-loud per P30 D-07) is **left untouched this phase** — no shared/copied helper file, no cross-service routing. Matches the self-contained-service convention; zero rebuild risk to the calibration window.
- **D-02: "Loud" = return bool + ERROR log, never raise.** `send_telegram` returns `True`/`False` and ERROR-logs (not warns) on env-unset or delivery failure. No caller breaks (25 existing call sites assume it never raises); a failed alert always leaves an unmissable trace.
- **D-03: Only hold/eval-critical call sites check the return** and escalate the failure (e.g. CRITICAL log): the Friday notify, auto-publish notifications, and the new eval hold/escalation alerts. Digest/watchdog/briefing sites stay fire-and-forget — they still get the ERROR log for free.
- **D-04: Startup ERROR + send-time ERROR.** The processor ERROR-logs a fixed grep-able label at startup if `TELEGRAM_BOT_TOKEN`/`TELEGRAM_OWNER_ID` is unset (visible at container boot, not first-alert-time), and again per failed send. The service still runs — an alerting gap must never take down ingestion/generation.

### Friday-notify eval summary (SURF-02)
- **D-05: Covers primary + block_v1.** The publishable primary draft leads (its verdict gates Monday); a one-line block_v1 telemetry verdict follows — the weekly single-pass vs block_v1 A/B signal.
- **D-06: Detail = verdict + final-attempt per-dimension judge scores + fabrication/unverified/mechanical flag counts + attempts used** (~5-6 lines per draft). The **mechanical count is ALWAYS shown, even on `passed`** — this satisfies the operator-flagged P29 D-12 dependency in the notify itself.
- **D-07: Missing eval rows render as an explicit warning line** ("⚠ no eval recorded for this draft") — the notify always includes an eval section; a missing eval is distinguishable from passed-clean (fail-loud, NULL ≠ intent). During the armed era a silently-not-running eval is the exact failure mode to surface.
- **D-08: Report-only holds are prominent.** While `enforce=false`, `held_fabrication`/`held_voice` verdicts render as "⚠ WOULD HAVE HELD (report-only)" at the top of that draft's block — the notify is the operator's calibration instrument for deciding when to flip `enforce=true`, and the tag stays unambiguous once enforce flips.

### /newsletter_eval command (SURF-03)
- **D-09: No-args targets the latest newsletter that HAS `edition_evals` rows** (any status) — the command always answers about the most recent eval that ran; if none exist anywhere, say so explicitly. Optionally accept `/newsletter_eval <edition#>` for a specific edition.
- **D-10: Main view = per-dimension score lines for all dims; bounded evidence for failures.** For each FAILING dimension: the judge's quoted evidence + before/after exemplar, excerpt-bounded (~300 chars each); passing dims stay score-only. Mechanical flags listed even on `passed` (P29 D-12). The existing 4000-char Telegram splitter handles overflow.
- **D-11: `trend` = verdict-per-edition list** — last ~8 editions, one line each: edition #, pipeline version, final verdict, attempts used, flag counts (mirrors `read_eval_trend`'s shape: limit 8 per pipeline_version).
- **D-12: Owner-gated** (gate on `access_tier`, like `/map-approve`) — the view quotes pre-publication draft prose (judge evidence + exemplar excerpts) that must not leak to any non-owner chat the bot lands in. Read-only, but what it reads is unpublished.

### Done-boundary & rollout
- **D-13: Done = code + tests + scoped deploys + a live Telegram plumbing round-trip.** Send `/newsletter_eval` over real Telegram (the explicit "no eval recorded yet" answer counts — it proves allowlist + handler + select) and invoke the notify path manually. Friday's real rows (first arrive 2026-07-03) enrich the surface but do NOT gate phase-done — consistent with the 27–30 build-then-activate posture. The gato rebuild + live checks are worktree-UNSAFE, orchestrator-owned on the main tree.
- **D-14: The newsletter container is NOT rebuilt this phase** (follows D-01). Nothing lands mid-calibration in the service whose behavior is being observed.

### Claude's Discretion
- Exact Gato alert copy/format and any alert dedup/rate-limiting (deferred here from Phase 30) — planner-level detail.
- The allowlist regex shape in `inject-gato-brain.mjs` (note `/^\/newsletter_preview\b/` will NOT match `/newsletter_eval` — a new pattern is needed) and whether the gato help text (which already lists `/newsletter_*` commands) gets a `/newsletter_eval` line.
- Where the processor's/gato_brain's plain-select code lives (services are self-contained — they cannot import `docker/newsletter/edition_eval.py`; a small local select mirroring `read_evals_by_newsletter`/`read_eval_trend` semantics is expected). Must be `.eq()`-only — the existing `/newsletter_preview` handler's `.in_()` usage is NOT the pattern to copy.
- Exact Friday-notify message layout/emoji, subject to D-05..D-08.
- How `access_tier` owner-gating is threaded for the new handler (mirror `handle_map_command`'s dispatch).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & carried-forward dependencies
- `.planning/REQUIREMENTS.md` §SURF-01..03 (lines ~70-72) — the three locked requirements; also the verdict taxonomy (lines ~88-95) and the activation note (report-only calibration).
- `.planning/phases/29-layer-2-judge-feedback-rewrite-loop/29-CONTEXT.md` §deferred — the **operator-flagged P29 D-12 dependency**: SURF-02/03 MUST surface mechanical-only Layer-1 flags even on a `passed` verdict.
- `.planning/phases/30-sequencer-wiring-hold-action-activation-gate/30-CONTEXT.md` — the deferred alert copy/dedup items and the `_alert_operator`-is-interim note (D-01/D-14 here resolve it: newsletter path stays as-is this phase); the enabled/enforce semantics (D-15 there) that D-08 renders.
- `.planning/STATE.md` §"Standing milestone invariants" + §"Session Continuity" — no LLM in the Processor, `.eq()`-only, fail-loud, worktree-unsafe steps orchestrator-owned; the calibration window is OPEN (eval armed report-only 2026-07-02).

### Code to modify
- `docker/processor/agentpulse_processor.py` — `send_telegram` (~:9611, the fail-soft path to harden); `scheduled_notify_newsletter` (~:10632, the static Friday notify to extend); `scheduled_auto_publish_newsletter` (~:10641, a critical caller); schedule wiring (`friday.at("12:00")` ~:11380). NOTE: `docker/agentpulse_processor.py` is a stale root-level copy NOT used by the Dockerfile (`docker/processor/Dockerfile` copies from `docker/processor/`) — do not edit it.
- `docker/gato_brain/gato_brain.py` — the `/newsletter_preview` direct-dispatch handler (~:2708) is the insertion-pattern for `/newsletter_eval` (dispatch BEFORE the intent router); `handle_map_command` (~:2366) shows access_tier-gated dispatch; module-level `supabase` client exists.
- `docker/gato/inject-gato-brain.mjs` — `isGatoBrainCommand` (~:112) + the per-command regexes (~:107-111); the command is DEAD over Telegram until added here + gato rebuilt (the Phase 9 `/map-*` lesson).

### Read-model reference (semantics to mirror, NOT importable)
- `docker/newsletter/edition_eval.py` — `read_evals_by_newsletter` (:186) + `read_eval_trend` (:198): the `.eq()`-only read semantics the processor/gato_brain selects mirror; `write_eval_row` documents the row shape (`layer`, `attempt`, `eval_status`, `verdict`, `deterministic_flags`, `judge_scores`, `judge_feedback`).
- `docker/newsletter/newsletter_poller.py` — `_alert_operator` (~:365): the P30 fail-loud alert contract SURF-01 matches (label-only logging, never the eval key, bounded single-line message, T-30-LOG hygiene); untouched this phase per D-01/D-14.
- `supabase/migrations/045_edition_evals.sql` — the `edition_evals` schema both new read surfaces select from (JSONB `deterministic_flags`/`judge_scores`, `UNIQUE(newsletter_id, layer, attempt)`, verdict-iff-ok CHECK).

### Implementation reference
- `docs/audit/specs/01_eval_harness.md` — the eval-harness spec (R5); surfacing sections are reference-only; REQUIREMENTS.md overrides on conflict.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `send_telegram` (processor ~:9611) — already handles 4000-char newline-boundary splitting + Markdown→plain-text fallback; the hardening changes its failure semantics (bool return + ERROR), not its delivery mechanics.
- The `/newsletter_preview` handler (gato_brain ~:2708) — the exact direct-dispatch shape for `/newsletter_eval` (prefix match before the intent router, ChatResponse with a fixed intent tag). Caveat: its `.in_()` call is the anti-pattern; new selects are `.eq()`-only.
- `handle_map_command` (gato_brain ~:2366) — the access_tier-threaded, owner-gated dispatch pattern for D-12.
- `read_eval_trend` / `read_evals_by_newsletter` (newsletter `edition_eval.py`) — the query semantics to mirror locally (services can't import across container boundaries).
- Telegram messages split at 4000 chars with Markdown-first/plain-fallback — both new surfaces inherit this convention.

### Established Patterns
- Command forwarding: gato_brain `/command` handlers are dead over Telegram until the command matches `isGatoBrainCommand` in `inject-gato-brain.mjs` + gato is rebuilt (bit the whole `/map-*` surface in Phase 9) — SURF-03's live round-trip check exists because of this.
- Scoped rebuilds use compose SERVICE names (`docker compose up -d --build processor gato_brain gato`), operator-approved, no `--delete`; worktree-unsafe steps run on the main tree, orchestrator-owned.
- Fail-loud: NULL ≠ intent; a missing eval row is rendered as an explicit warning, never omitted (D-07); no bare excepts; log labels/counts, never raw draft prose or keys (T-30-LOG).
- The Processor stays a dumb sequencer — SURF-02 is a plain select + string formatting; no LLM, no retry state.

### Integration Points
- `scheduled_notify_newsletter` (processor) — the Friday 12:00 UTC hook where the eval summary is appended; it must locate the current drafts' `newsletters` rows and select their `edition_evals` rows (both `pipeline_version`s).
- gato_brain `/chat` dispatch chain (~:2700-2760) — `/newsletter_eval` slots in as a new direct handler before the intent router.
- `inject-gato-brain.mjs` `isGatoBrainCommand` — new regex + gato rebuild.
- Live-verify: one real Telegram round-trip of `/newsletter_eval` + a manual invocation of the notify path (D-13).
</code_context>

<specifics>
## Specific Ideas

- The Friday notify is the operator's **calibration instrument**: the "WOULD HAVE HELD (report-only)" tag (D-08) exists so the ~2-edition window produces a legible flip-`enforce` decision without digging into the DB.
- "A missing eval must look different from a passing eval" — the explicit ⚠ no-eval-recorded line (D-07) is the operator's standing no-silent-no-op posture applied to the read surface.
- The P29 D-12 promise is honored in BOTH surfaces: mechanical flags appear in the Friday notify counts (D-06) and in the `/newsletter_eval` view (D-10) even when the verdict is `passed`.
</specifics>

<deferred>
## Deferred Ideas

- **Newsletter `_alert_operator` bool-return alignment** — deliberately not done this phase (D-01/D-14, calibration-window protection); if a future phase rebuilds the newsletter container anyway, aligning the return contract can ride along.
- **v2.3-future (already in STATE Deferred Items):** eval-trend regression alerting (OBS-01), per-dimension threshold auto-tuning (TUNE-01), `edition_revisions` operator-edit trail (REV-01), quantitative A/B comparison trend (AB-01).
- **Milestone close follow-ups (not this phase):** operator flips `enforce=true` after the calibration window (30-04 Task 6); REQUIREMENTS traceability nit (deferred REV/AB/TUNE/OBS IDs absent from the table).

### Reviewed Todos (not folded)
Same three keyword matches as Phases 28–30; same verdict — unrelated backend backlog, none folded:
- `2026-05-28-harden-soft-caps-allow-negative.md` — soft-cap hardening for the *other* agents (governance backlog); `edition_eval` is already `allow_negative=false`.
- `2026-05-28-pay-endpoint-500-transfer-rpc-search-path.md` — agent→agent payments RPC; unrelated.
- `2026-05-28-phase05-review-followups-wr02-wr04-wr05.md` — intake-classifier follow-ups; unrelated.

</deferred>

---

*Phase: 31-surfacing-escalation*
*Context gathered: 2026-07-02*
