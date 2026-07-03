# Phase 31: Surfacing & Escalation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-02
**Phase:** 31-surfacing-escalation
**Areas discussed:** Alert-path hardening (SURF-01), Friday-notify eval summary (SURF-02), /newsletter_eval command (SURF-03), Done-boundary & rollout

---

## Alert-path hardening (SURF-01)

### Q1 — Hardened alert-path topology across processor and newsletter

| Option | Description | Selected |
|--------|-------------|----------|
| Harden each in place (Recommended) | Harden processor's send_telegram where it lives; keep newsletter's _alert_operator (already fail-loud per P30 D-07) aligned. No new files, no drift risk. | ✓ |
| One canonical helper, copied | One telegram_alert.py copied into both service images — single semantics, but two copies to keep in sync. | |
| Route all alerts via processor | Newsletter writes an alert row/queue, processor sends — adds a polling hop + new silent-failure seam. | |

**User's choice:** Harden each in place

### Q2 — What "loud" means on delivery failure

| Option | Description | Selected |
|--------|-------------|----------|
| Return bool + ERROR log (Recommended) | send_telegram returns True/False + ERROR-logs; hold/escalation callers check the return. No caller breaks. | ✓ |
| Raise on failure | Strictest, but 25-call-site blast radius; a raised alert-exception can kill the job that produced the hold. | |
| ERROR log only | Smallest diff, but callers can't distinguish delivered vs failed. | |

**User's choice:** Return bool + ERROR log

### Q3 — Which call sites check the new return value

| Option | Description | Selected |
|--------|-------------|----------|
| Hold/eval-critical only (Recommended) | Friday notify, auto-publish notifications, eval hold/escalation alerts check the return; digest/watchdog/briefing stay fire-and-forget. | ✓ |
| All call sites | Sweep all 25 sites — uniform but boilerplate with no added guarantee. | |
| You decide | Planner classifies critical vs fire-and-forget. | |

**User's choice:** Hold/eval-critical only

### Q4 — When/how hard the unset-env check fires

| Option | Description | Selected |
|--------|-------------|----------|
| Startup ERROR + send-time ERROR (Recommended) | Grep-able ERROR at container boot when TELEGRAM env unset + per failed send; service still runs. | ✓ |
| Refuse to start | Maximally fail-loud but couples pipeline uptime to an alerting credential. | |
| Send-time only | Misconfig sits silent until the first held edition needs the alert. | |

**User's choice:** Startup ERROR + send-time ERROR

---

## Friday-notify eval summary (SURF-02)

### Q1 — Which drafts the summary covers

| Option | Description | Selected |
|--------|-------------|----------|
| Primary + block_v1 (Recommended) | Primary leads (gates Monday) + one-line block_v1 telemetry verdict — the weekly A/B signal. | ✓ |
| Primary draft only | Tightest message but loses the A/B read during calibration. | |
| You decide | Planner picks by rendered noise. | |

**User's choice:** Primary + block_v1

### Q2 — Detail level per draft

| Option | Description | Selected |
|--------|-------------|----------|
| Verdict + dims + flag counts (Recommended) | Verdict, final-attempt per-dimension scores, fabrication/unverified/mechanical counts, attempts. Mechanical always shown (P29 D-12). | ✓ |
| Verdict + counts only | No per-dimension breakdown; operator must run the command to see WHY. | |
| Full detail inline | Judge feedback excerpts included — pushes against the 4000-char split. | |

**User's choice:** Verdict + dims + flag counts

### Q3 — Behavior when no eval rows exist

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit warning line (Recommended) | Always an eval section; missing rows render "⚠ no eval recorded for this draft" — distinguishable from passed-clean. | ✓ |
| Omit the section | Eval outage becomes invisible in the one place the operator reliably looks. | |
| Warn only when enabled=true | Config-aware, but adds a state where a misconfig hides the warning. | |

**User's choice:** Explicit warning line

### Q4 — Report-only would-have-held rendering

| Option | Description | Selected |
|--------|-------------|----------|
| Prominent would-have-held tag (Recommended) | "⚠ WOULD HAVE HELD (report-only)" atop that draft's block — the calibration instrument. | ✓ |
| Verdict shown plainly | Conflates "was held" with "would have been held" once enforce flips. | |
| You decide | Planner picks; must stay distinguishable. | |

**User's choice:** Prominent would-have-held tag

---

## /newsletter_eval command (SURF-03)

### Q1 — "Current edition" semantics with no args

| Option | Description | Selected |
|--------|-------------|----------|
| Latest with eval rows (Recommended) | Most recent newsletter that HAS edition_evals rows (any status); explicit message if none; optional <edition#> arg. | ✓ |
| Latest draft/pending row | Mirrors /newsletter_preview's target but goes stale after Monday publish. | |
| You decide | Planner picks; no-rows must be explicit. | |

**User's choice:** Latest with eval rows

### Q2 — Main-view rendering

| Option | Description | Selected |
|--------|-------------|----------|
| Scores + bounded excerpts (Recommended) | All dims score-lines; failing dims get quoted evidence + before/after exemplar (~300 chars each); mechanical listed even on passed; splitter handles overflow. | ✓ |
| Full judge output | Complete JSONB dump — spans several messages every time. | |
| Scores only + drill-down arg | Cleanest, but adds a subcommand the requirement doesn't ask for. | |

**User's choice:** Scores + bounded excerpts

### Q3 — What `trend` shows

| Option | Description | Selected |
|--------|-------------|----------|
| Verdict-per-edition list (Recommended) | Last ~8 editions, one line each: edition #, pipeline version, verdict, attempts, flag counts. | ✓ |
| Verdicts + dimension averages | Richer tuning signal but denser message + avg computation. | |
| You decide | Must at minimum show recent verdicts. | |

**User's choice:** Verdict-per-edition list

### Q4 — Access gating

| Option | Description | Selected |
|--------|-------------|----------|
| Owner-gated (Recommended) | Gate on access_tier like /map-approve — the view quotes pre-publication draft prose. | ✓ |
| Ungated read | Mirrors /map-status's reads-open split; accepts unpublished excerpts rendering for any bot user. | |
| You decide | Match whichever precedent fits who can reach Gato. | |

**User's choice:** Owner-gated

---

## Done-boundary & rollout

### Q1 — What "Phase 31 done" requires

| Option | Description | Selected |
|--------|-------------|----------|
| Deploy + live plumbing check (Recommended) | Code + tests + scoped deploys + live /newsletter_eval round-trip ("no eval recorded yet" counts) + manual notify invocation; Friday's real rows don't gate closure. | ✓ |
| Wait for Friday's real run | Strongest proof but couples closure to the pipeline calendar. | |
| Code-complete only | Weakest — the OpenClaw allowlist lesson argues for a live round-trip. | |

**User's choice:** Deploy + live plumbing check

### Q2 — Touch newsletter's _alert_operator this phase?

| Option | Description | Selected |
|--------|-------------|----------|
| Leave newsletter untouched (Recommended) | Already meets SURF-01's guarantee; zero risk to the calibration window; SURF-01 lands only in the processor. | ✓ |
| Align + rebuild newsletter | Consistent semantics but a mid-calibration rebuild of the observed service. | |
| Align in code, defer rebuild | Repo/container drift in the meantime. | |

**User's choice:** Leave newsletter untouched

---

## Claude's Discretion

- Exact Gato alert copy/format + alert dedup/rate-limiting (deferred from Phase 30).
- Allowlist regex shape in `inject-gato-brain.mjs` + whether the gato help text gains a `/newsletter_eval` line.
- Where the processor/gato_brain plain-select code lives (`.eq()`-only; cannot import newsletter's `edition_eval.py`).
- Exact Friday-notify layout/emoji within D-05..D-08.
- How access_tier owner-gating is threaded (mirror `handle_map_command`).

## Deferred Ideas

- Newsletter `_alert_operator` bool-return alignment — rides along with a future newsletter rebuild.
- v2.3-future: OBS-01 (eval-trend regression alerting), TUNE-01 (threshold auto-tuning), REV-01 (edition_revisions), AB-01 (quantitative A/B trend).
- Operator flips `enforce=true` after the calibration window (30-04 Task 6); REQUIREMENTS traceability nit at milestone close.
