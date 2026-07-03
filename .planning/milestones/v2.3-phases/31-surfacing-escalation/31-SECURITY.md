---
phase: 31
slug: surfacing-escalation
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-03
---

# Phase 31 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Scope: SURF-01 (send_telegram fail-loud hardening), SURF-02 (Friday-notify eval
> section), SURF-03 (owner-gated /newsletter_eval command), and the deploy/live-verify
> boundary. Verified against CURRENT code including the two post-summary fix passes
> (WR-03/05/06 then WR-02/04) recorded in 31-REVIEW.md.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| env config → processor | `TELEGRAM_BOT_TOKEN`/`TELEGRAM_OWNER_ID` may be unset at boot | bot credentials (secret) |
| processor → Telegram API | outbound alert delivery can fail (network/4xx/5xx) | operator alert text |
| edition_evals (DB) → processor notify | eval rows carry judge evidence/exemplars (unpublished draft prose) | pre-publication prose, counts, scores |
| Telegram user (any chat) → gato → gato_brain /chat | untrusted caller; /chat gated behind X-Gato-Secret HMAC | command text |
| edition_evals (DB) → /newsletter_eval response | the deep view quotes UNPUBLISHED draft prose (evidence + exemplars) | pre-publication prose |
| main-tree deploy → live containers | worktree executors would build stale code; deploy is orchestrator-owned | container images |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation (verified control) | Status |
|-----------|----------|-----------|-------------|-------------------------------|--------|
| T-31-01 | Information disclosure | send_telegram ERROR logs | mitigate | `agentpulse_processor.py:9647-9653` — env-unset path logs bounded label `len=%d head=%r` with `safe[:80]` (WR-06); terminal-failure logs bounded `resp.text[:200]` (9683/9706); exception logs `{e}` only. No bot token, no full draft prose. | closed |
| T-31-02 | Denial of service | alerting gap on unset env | mitigate | `_check_telegram_config()` `:9615-9628` ERROR-logs `[TELEGRAM-CONFIG]`, returns False, never raises; wired into `init_clients()` at `:435` (runs at boot, service continues). `send_telegram` returns bool on every path, never raises (`:9647-9711`). | closed |
| T-31-03 | Repudiation | failed critical auto-publish alert | mitigate | `scheduled_auto_publish_newsletter` `:10964-10971` — `if not send_telegram(...): logger.critical("[EVAL-ALERT] CRITICAL — auto-publish notification delivery FAILED ...")` (edition number only). | closed |
| T-31-04 | Information disclosure | notify eval section | mitigate | `_format_notify_eval_section` `:10752-10848` + `_notify_worst_dim_score` `:10728-10749` read ONLY `.get("score")` and `len()` of flag lists — never `evidence`/`exemplar_*`. WR-03 error line bounded `str(error_rows[-1].get("error"))[:200]` at `:10811-10813` (recorded eval error reason, not draft prose). | closed |
| T-31-05 | Tampering (silent failure) | edition_evals reads (processor) | mitigate | `_read_edition_evals` `:10707-10725` is `.eq("edition_number")`-only; no `.in_(` in the function body (structurally excluded by StubSupabase test). | closed |
| T-31-06 | Denial (missing/errored eval hidden) | notify render | mitigate | Missing rows render `⚠ no eval recorded for this draft` `:10783`; eval-section build wrapped fail-open-but-loud `[EVAL-NOTIFY]` `:10894-10902`; WR-05 supabase-None ERROR `:10871` + success-gated INFO `:10910-10911`. | closed |
| T-31-07 | Info disclosure / Elevation | /newsletter_eval reads pre-pub prose | mitigate | `handle_newsletter_eval` `:2744-2749` — `if access_tier != "owner": return refusal` BEFORE `sb=` and any `.table()` read; dispatch threads `access_tier` at `:3115-3116`. | closed |
| T-31-08 | Information disclosure | handler ERROR logs | mitigate | Handler logs labels/counts only (`rows=%d`/`edition=%d` `:2760/2768/2775`; exception logs `type(e).__name__` `:2780`, not `str(e)`). Evidence/exemplars bounded to 300 chars via `_eval_excerpt` (`:2434`, `:2525-2529`), returned ONLY inside the owner-gated response. | closed |
| T-31-09 | Denial of service | malformed edition arg | mitigate | Integer-parse `arg.lstrip("#").isdigit()` → `int(...)` `:2763-2766`; top-level try/except `:2751/2779-2781` returns human-readable failure string, never raises. | closed |
| T-31-10 | Tampering (silent failure) | edition_evals reads (gato_brain) | mitigate | Three `.eq()`-only readers `:2439-2516`; WR-02 restructured `_eval_read_trend` into a two-stage per-edition `.eq()` read (`:2486-2516`) — remained `.in_()`-free. Only `.in_(` in file is the pre-existing `/newsletter_preview` handler `:3087`, not an eval reader. | closed |
| T-31-11 | Information disclosure | live /newsletter_eval owner-gate | mitigate | Source gate present (`:2744`) + mjs allowlist `isNewsletterEval` (`inject-gato-brain.mjs:115-116`); live-confirmed in running image via 31-03 unit-test refusal assertion + operator live round-trip ("eval-live", 31-04-SUMMARY). | closed |
| T-31-12 | Tampering | rebuilding wrong/too-many services | mitigate | Scoped rebuild named exactly `processor gato_brain gato`; newsletter NOT recreated (D-14) — operator-attested (31-04-SUMMARY: newsletter Created/Started timestamps unchanged). Deploy-action gate, not code-governed. | closed |
| T-31-13 | Denial | bad deploy takes down ingestion | mitigate | Syntax (`ast.parse`) + full phase suite green BEFORE rebuild (re-verified: 54/54 pass); no `--delete`; services run even with Telegram env unset (`_check_telegram_config` never raises, `init_clients` continues past `:435`). | closed |
| T-31-SC | Tampering (supply chain) | package installs | accept | No npm/pip/cargo installs in this phase — `git diff 32c3662..HEAD` shows only 3 implementation files (processor, gato_brain, inject-gato-brain.mjs) + 3 test files; zero dependency manifests (requirements.txt / package.json / Dockerfile / pyproject / Cargo) changed. See Accepted Risks Log. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Mitigation-Locking Tests (evidence the controls hold)

| Threat | Test (file::name) | Result |
|--------|-------------------|--------|
| T-31-01 | `test_31_send_telegram.py::test_env_unset_log_is_bounded_label_not_prose` | pass |
| T-31-02 | `test_31_send_telegram.py::test_boot_config_check_error_logs_when_unset`, `test_exception_path_returns_false_and_does_not_raise` | pass |
| T-31-03 | `test_31_send_telegram.py::test_auto_publish_critical_logs_on_delivery_failure` | pass |
| T-31-04 | `test_31_notify_eval.py::test_formatter_leaks_no_evidence_or_exemplar_prose`, `test_notify_error_reason_bounded_to_200_chars` | pass |
| T-31-05 | `test_31_notify_eval.py::test_edition_evals_query_has_no_in_filter`, `test_read_edition_evals_returns_rows_and_uses_eq` | pass |
| T-31-06 | `test_31_notify_eval.py::test_missing_pipeline_version_prints_no_eval_line`, `test_notify_fail_open_on_eval_read_exception`, `test_notify_no_supabase_guard_returns` | pass |
| T-31-07 | `test_31_newsletter_eval_handler.py::test_non_owner_refused_and_no_read`, `test_non_owner_subscriber_refused` | pass |
| T-31-08 | `test_31_newsletter_eval_handler.py::test_held_voice_detail_all_dims_and_bounded_evidence`, `test_detail_error_reason_bounded_to_200_chars` | pass |
| T-31-09 | `test_31_newsletter_eval_handler.py::test_edition_arg_reads_by_edition_eq` (+ handler try/except) | pass |
| T-31-10 | `test_31_newsletter_eval_handler.py::test_stub_query_has_no_in_list_method`, `test_trend_boundary_edition_never_truncated_to_wrong_verdict` | pass |

Full phase suite re-run during this audit: `test_31_send_telegram.py` + `test_31_notify_eval.py` + `test_31_newsletter_eval_handler.py` → **54 passed**.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-31-SC | T-31-SC (plans 01/02/03/04) | No new dependencies introduced this phase. `git diff 32c3662..HEAD` confirms only `docker/processor/agentpulse_processor.py`, `docker/gato_brain/gato_brain.py`, `docker/gato/inject-gato-brain.mjs`, and three `tests/test_31_*.py` files changed — no requirements.txt / package.json / Dockerfile / pyproject / Cargo touched. Scoped rebuilds reuse existing pinned images. RESEARCH package-legitimacy gate N/A. | gsd-security-auditor | 2026-07-03 |

*Accepted risks do not resurface in future audit runs.*

---

## Unregistered Flags

None. No `## Threat Flags` section appears in any of the four 31-0N-SUMMARY.md files. (31-02-SUMMARY has a `## Threat Surface` prose section that only restates the plan's existing threat register — no new attack surface.) No new attack surface appeared during implementation without a threat mapping.

---

## Auditor Notes

- **Post-summary fix passes verified against CURRENT code**, not against the original plan wording:
  - **WR-06** (`2a00a6f`): env-unset log strengthened from `[:1000]` to bounded `len=%d head=%r` (`safe[:80]`). Verified — this is the CLOSED evidence for T-31-01 (no drift flagged from the plan's original `[:1000]`).
  - **WR-03** (`d712578`): bounded `⚠ eval ERROR: {reason[:200]}` line added in both formatters; verified the 200-char bound holds and the text is the recorded `error` column (`error_rows[-1].get("error")`), not draft prose — processor `:10811-10813`, gato_brain `:2622-2625`.
  - **WR-05** (`7528a4d`): supabase-None ERROR + success-gated INFO — processor `:10871`, `:10910-10911`.
  - **WR-02** (`9e41cef`): `_eval_read_trend` two-stage per-edition `.eq()` read — verified `.in_()`-free (gato_brain `:2486-2516`).
  - **WR-04** (`1588945`): `plain=True` skips Markdown for the eval-bearing notify — not a threat mitigation itself but does not weaken any control.
- **T-31-11/12/13** are deploy/live-verify (`checkpoint:human-verify`) gates. The code-level mitigations (owner-gate source, mjs allowlist, boot-check-never-raises, syntax/test-green) are grep- and test-verifiable and confirmed here. The deploy-action portions (running-image gate confirmation, newsletter-not-rebuilt, no `--delete`) are inherently operator-attested and recorded in 31-04-SUMMARY (operator signals "deployed" / "eval-live" / "notify-verified"). This is the appropriate evidence type for a human-action checkpoint.
- **Deferred backlog (out of scope for this phase's threat register, NOT security gaps):** 31-REVIEW.md WR-01 (edition-keyed reads mix multiple generations of an edition) and WR-07 (gato_brain hardcodes judge thresholds it cannot read live) remain deferred todos. Neither is a declared threat in the phase register; both are correctness/calibration-fidelity concerns, not confidentiality/integrity/availability mitigations owed by this phase. Recorded here for traceability; they do not block this phase.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-03 | 13 + T-31-SC | 13 + T-31-SC | 0 | gsd-security-auditor |

*(13 distinct mitigate threats T-31-01..T-31-13 across plans 01–04, plus the shared T-31-SC accept disposition.)*

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-03
