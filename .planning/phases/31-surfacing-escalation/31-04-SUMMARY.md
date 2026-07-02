---
phase: 31-surfacing-escalation
plan: 04
subsystem: deploy-verification
tags: [deploy, live-verify, telegram, eval-surfacing]
requirements: [SURF-01, SURF-02, SURF-03]
dependencies:
  plans: ["31-01", "31-02", "31-03"]
status: complete
completed: 2026-07-02
duration: ~25min (including operator Telegram round-trips)
---

# Plan 31-04 Summary — Deploy + Live Verification (D-13 done-boundary)

Closed the Phase 31 done-boundary: SURF-01/02/03 code scoped-rebuilt onto the live
processor, gato_brain, and gato containers; `/newsletter_eval` verified over real
Telegram; the Friday-notify eval path exercised end-to-end and confirmed delivered.

## Task 1 — Scoped rebuild (checkpoint:human-action, operator approved "Deploy now")

Pre-flight (all green before rebuild):
- `ast.parse` clean on `docker/processor/agentpulse_processor.py` and `docker/gato_brain/gato_brain.py`; `node --check` clean on `docker/gato/inject-gato-brain.mjs`
- Phase suite 41/41: `test_31_send_telegram.py` (10) + `test_31_notify_eval.py` (20) + `test_31_newsletter_eval_handler.py` (11)
- Full-suite failure set byte-identical to the pre-phase baseline (19 pre-existing env/stale failures; zero regressions)
- All 31-01/02/03 merge commits confirmed on main (`5f6e54e`, `daac513`, `38e0b99`)

Deploy: `cd /root/bitcoin_bot/docker && docker compose up -d --build processor gato_brain gato`
- processor, gato_brain, gato recreated and healthy (verified 2026-07-02 ~22:31 UTC)
- **newsletter NOT recreated** (D-14): container Created/Started timestamps unchanged (2026-07-02T13:59/14:00Z) — calibration window protected
- No `[TELEGRAM-CONFIG]` boot ERROR (env set — correct absence)
- Running-image checks: `isNewsletterEval` present ×2 in gato's injected `/tmp/inject-gato-brain.mjs`; `handle_newsletter_eval` present in gato_brain's `/home/openclaw/gato_brain.py`

## Task 2 — Live `/newsletter_eval` round-trip (checkpoint:human-verify, operator: "eval-live")

- `/newsletter_eval` over real Telegram replied **"No eval has run for any edition yet."** — the explicit no-eval answer, which D-13 counts: it proves allowlist → gato_brain handler → `.eq()` select wired end-to-end (no OpenClaw fall-through).
- `edition_evals` is genuinely empty (eval armed report-only 2026-07-02; no edition generated since), so this is the correct live answer.
- Owner-gate confirmed via the 31-03 unit-test refusal assertion (no non-owner chat used).

## Task 3 — Friday-notify path (checkpoint:human-verify, operator: "notify-verified")

First invocation (`docker exec -w /home/openclaw agentpulse-processor python -c "import agentpulse_processor as p; p.init_clients(); p.scheduled_notify_newsletter()"`):
- Static notify delivered (Markdown 400 → documented plain-text fallback → 200 OK); no `[EVAL-ALERT]`/`[EVAL-NOTIFY]` logs; processor healthy.
- Operator received static line WITHOUT eval section. **Diagnosed as designed behavior, not a bug**: `newsletters` has NO draft/pending row today (all published/held), so the eval section — keyed to the current draft's edition_number — is skipped. Verified: `.in_('status',['draft','pending'])` returns `[]`.

Second invocation (same render+send path, edition pinned to latest real edition #33 since no draft row exists):
- `_read_edition_evals` + `_format_notify_eval_section` rendered: `🧪 Pre-publish eval (report-only)` header, single_pass block first (D-05), `⚠ no eval recorded for this draft` for both pipeline_versions (D-07).
- `send_telegram` returned `True` (200 OK first try). Operator confirmed arrival in Telegram.

## Verification result

- SURF-01: hardened `send_telegram` live (boot check silent with env set; bool-return path exercised on both notify sends).
- SURF-02: notify eval section renders + delivers live; no-draft edge behaves fail-open as designed.
- SURF-03: `/newsletter_eval` + trend live over Telegram, owner-gated.
- D-14 held: newsletter container untouched.

## Notes for verifier

- The Friday notify's eval section is only observable with a draft/pending newsletter present; the next real Friday cycle (with a fresh draft) is the first fully-organic render. The pinned-edition invocation covered render+delivery of the exact same functions.
- Pre-existing quirk (out of scope, unchanged by this phase): `scheduled_notify_newsletter` sends the static "Brief is ready" line even when no draft exists.

## Self-Check: PASSED
