---
phase: quick-260705-ufj
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docker/gato_brain/gato_brain.py
  - docker/gato/inject-gato-brain.mjs
  - tests/test_unhold_handler.py
autonomous: true
requirements: [TODO-2026-07-04-newsletter-unhold]
must_haves:
  truths:
    - "Owner sends `/newsletter_unhold 104` over Telegram and gets a PREVIEW (hold reason + eval flag counts + confirm instruction) with ZERO database mutation"
    - "Owner sends `/newsletter_unhold 104 confirm` and the edition's PRIMARY held row is released: do_not_publish=false, status='draft', do_not_publish_reason=null — both processor publish guards accept it again with NO processor change"
    - "A non-owner caller gets an owner-only refusal BEFORE any database read"
    - "An always-held block_v1 A/B shadow row (data_snapshot.ab_comparison / [BLOCK PIPELINE A/B] title) is NEVER selected for release; an edition whose only held row is the shadow gets an explicit 'held by design, not releasable' message"
    - "Edition-not-found, found-but-not-held, and Supabase-error paths each return a distinct human-readable message — never a silent no-op"
  artifacts:
    - path: "docker/gato_brain/gato_brain.py"
      provides: "handle_newsletter_unhold handler + direct-dispatch branch before the intent router"
      contains: "def handle_newsletter_unhold"
    - path: "docker/gato/inject-gato-brain.mjs"
      provides: "distinct isNewsletterUnhold regex OR'd into isGatoBrainCommand + help-list line"
      contains: "isNewsletterUnhold"
    - path: "tests/test_unhold_handler.py"
      provides: "unit coverage mirroring tests/test_31_newsletter_eval_handler.py harness"
      min_lines: 150
  key_links:
    - from: "docker/gato/inject-gato-brain.mjs"
      to: "isGatoBrainCommand"
      via: "isNewsletterUnhold OR'd in (Phase 9 dead-command landmine)"
      pattern: "isNewsletterUnhold"
    - from: "docker/gato_brain/gato_brain.py chat dispatch"
      to: "handle_newsletter_unhold"
      via: "_msg_lower.startswith(\"/newsletter_unhold\") branch before the intent router"
      pattern: "startswith\\(\"/newsletter_unhold\"\\)"
    - from: "handle_newsletter_unhold"
      to: "newsletters row"
      via: "targeted update .eq('id', row_id) — never by edition number"
      pattern: "\\.eq\\(\"id\""
---

<objective>
Ship the `/newsletter_unhold <edition#>` owner command in gato_brain — the P1 PRE-ENFORCE
BLOCKER from `.planning/todos/pending/2026-07-04-newsletter-unhold-command.md`. Under
`enforce=true`, a false-positive fabrication hold currently silences the newsletter with no
operator escape hatch (the exact "silence" failure mode the project's core value names);
today releasing a held edition means hand-editing the database.

Purpose: give the operator an informed, two-step release path (preview → confirm) that clears
`do_not_publish` + restores `status='draft'` on the PRIMARY held row only, so both existing
processor publish guards (`agentpulse_processor.py:5886` manual, `:10965` Monday auto) accept
the row again. NO processor changes needed.

Output: handler + dispatch in `gato_brain.py`, allowlist regex in `inject-gato-brain.mjs`,
`tests/test_unhold_handler.py`, scoped `gato_brain`+`gato` rebuild verified in-container.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/todos/pending/2026-07-04-newsletter-unhold-command.md
@docker/gato_brain/gato_brain.py (regions: 2409-2804 eval handler/helpers to mirror; 3104-3168 dispatch block)
@docker/gato/inject-gato-brain.mjs (lines 36-44 help list; 107-118 allowlist)
@tests/test_31_newsletter_eval_handler.py (harness to mirror)
</context>

<interface_contracts>
Facts the executor needs (verified this session — do NOT re-derive):

- **Publish guards already refuse `do_not_publish` rows** at
  `docker/processor/agentpulse_processor.py:5886` (manual) and `:10965` (auto-publish).
  Releasing = clear the flag + `status='draft'`. The processor is NOT touched.
- **Newsletters rows per edition:** an edition can have MULTIPLE rows — the primary draft AND
  an always-held block_v1 A/B shadow row (`data_snapshot->>'ab_comparison'` truthy,
  `do_not_publish=true` BY DESIGN, title prefixed `[BLOCK PIPELINE A/B]`). Live example:
  edition 104 has primary `666a8dea-…` (status=draft) and shadow `cde45f25-…` (held,
  ab_comparison=true). **The command MUST NEVER release a shadow row.**
- **Hold metadata:** `do_not_publish_reason` column on `newsletters` (migration 046) carries
  the hold reason (labels/counts/dim-scores by construction — WIRE-03/T-30-LOG safe).
  `edition_evals` rows are read via the existing `_eval_read_by_edition(sb, edition)` helper
  (gato_brain.py:2440) and rendered labels/counts-only via `_format_eval_trend(rows)` (:2697,
  pure, takes rows).
- **Pattern to mirror:** `handle_newsletter_eval` (:2755) — owner-gate FIRST returning a
  refusal string BEFORE any read (D-12/T-31-07), `supabase_client=None` param defaulting to
  the module global (testability), one top-level try/except returning a human-readable
  failure string, `logger.info` with labels/counts only, `.eq()`-only reads (NEVER `.in_()` —
  supabase-py in-list is a silent-failure bug; the `/newsletter_preview` handler's `.in_()`
  at :3109 is the anti-pattern NOT to copy).
- **Dispatch site:** the `2c-3` block at gato_brain.py:3133-3144 (`_msg_lower.startswith
  ("/newsletter_eval")` → returns ChatResponse with intent="NEWSLETTER_COMMAND",
  `access_tier` already in scope). No prefix collision: none of `/newsletter_unhold`,
  `/newsletter_eval`, `/newsletter_preview` is a prefix of another.
- **inject-gato-brain.mjs is a TEMPLATE-LITERAL injector** — regexes are written with escaped
  slashes (`/^\\/newsletter_eval\\b/i` at :115). Mirror that EXACT escaping. The file is baked
  into the gato image at build (`RUN node /tmp/inject-gato-brain.mjs` patches bot.ts before
  `pnpm run build`) — a gato rebuild is REQUIRED, not optional.
- **Container paths for in-container verify:** gato_brain code lives at
  `/home/openclaw/gato_brain.py` in `agentpulse-gato-brain` (NOT /app); gato's patched/compiled
  OpenClaw lives under `/app` in `openclaw-gato`.
</interface_contracts>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement handle_newsletter_unhold + dispatch + gato allowlist</name>
  <files>docker/gato_brain/gato_brain.py, docker/gato/inject-gato-brain.mjs</files>
  <behavior>
    - Non-owner (any command form) → owner-only refusal string; NO supabase call occurs.
    - `/newsletter_unhold` with no/non-numeric arg → usage message ("/newsletter_unhold &lt;edition#&gt; [confirm]"), no read needed after arg parse fails (parse before DB is fine either way, but owner gate is FIRST).
    - Bare `/newsletter_unhold 104` → PREVIEW ONLY: shows edition #, target row id, status, bounded `do_not_publish_reason` (cap ~400 chars, whitespace-collapsed), a labels/counts-only eval summary from `_eval_read_by_edition` + `_format_eval_trend` (or "no eval rows recorded for this edition"), and the instruction to send `/newsletter_unhold 104 confirm`. ZERO `.update()` calls.
    - `/newsletter_unhold 104 confirm` → re-runs the same lookup, then ONE targeted update `{'do_not_publish': False, 'status': 'draft', 'do_not_publish_reason': None}` via `.eq("id", row_id)` (row id, NEVER edition number), replies with a released confirmation naming edition + row id + that Monday auto-publish/manual publish will now accept it.
    - Row selection: plain `.eq("edition_number", N)` select of explicit columns `id, edition_number, status, title, do_not_publish, do_not_publish_reason, data_snapshot, created_at` on `newsletters`; NO PostgREST JSON operators, NO `.in_()`. Partition in Python: shadow = `_unhold_is_shadow(row)` (data_snapshot dict-or-str defensive check of `ab_comparison` truthiness OR title startswith `[BLOCK PIPELINE A/B]` — belt-and-suspenders); primary = non-shadow; held = `row.get('do_not_publish')` truthy OR `status == 'held'`.
    - Distinct failure messages: (a) no rows at all → "edition #N not found"; (b) primary rows exist, none held → "found but not held" reporting the primary's current status; (c) no held primary but a held shadow exists → "only the block_v1 A/B shadow row is held — held by design, not releasable"; (d) any supabase exception → caught by the one top-level try/except, returns "⚠ unhold failed: {e}" — never a silent no-op.
    - Multiple held primaries (regenerated editions): pick newest by `created_at`, and say so in the reply ("(N held primary rows — targeting the newest, id …)"). Both preview and confirm display the row id so the release is informed and deterministic.
    - Logging: fixed label `[UNHOLD]` with edition number + row id only (T-30-LOG — never the reason text, never draft prose).
  </behavior>
  <action>
    In `docker/gato_brain/gato_brain.py`, add a new section immediately after
    `handle_newsletter_eval` (after line ~2804): a comment banner mirroring the eval one, a
    module constant `_UNHOLD_SHADOW_TITLE_PREFIX = "[BLOCK PIPELINE A/B]"`, helper
    `_unhold_is_shadow(row) -> bool` (handle `data_snapshot` being dict, JSON string, or None
    without raising — on a string, fall back to the title-prefix check only), and
    `handle_newsletter_unhold(message: str, access_tier: str = "free", supabase_client=None)
    -> str` implementing the behavior above. Mirror `handle_newsletter_eval` structure
    exactly: owner gate FIRST (refusal text: "🔒 /newsletter_unhold is owner-only — it
    releases a held edition past the fabrication gate."), `sb = supabase_client if
    supabase_client is not None else supabase`, one top-level try/except with
    `logger.error("[UNHOLD] handler failed: %s", type(e).__name__, exc_info=True)`.
    Docstring must state the two-step confirm rationale (overrides a fabrication verdict) and
    the shadow-row exclusion. Reuse `_eval_read_by_edition` + `_format_eval_trend` for the
    preview's eval summary — do NOT duplicate their logic, and do NOT use `_format_eval_detail`
    (it quotes draft prose; the preview is labels/counts only).

    Add dispatch branch `2c-4` in the chat handler directly after the `2c-3` /newsletter_eval
    block (gato_brain.py:3144): `if _msg_lower.startswith("/newsletter_unhold"):` →
    `handle_newsletter_unhold(req.message, access_tier)` → return ChatResponse with
    `intent="NEWSLETTER_COMMAND"`, `session_id=""`, `metadata={}` — identical shape to 2c-3.
    Comment the branch: owner-gated release of a held edition, dispatched BEFORE the intent
    router; two-step confirm; never touches A/B shadow rows.

    In `docker/gato/inject-gato-brain.mjs`: (1) add a help-list line after line 40's
    `/newsletter_eval` entry: `/newsletter_unhold [n] — Release a held edition (owner)`;
    (2) add `const isNewsletterUnhold = text && /^\\/newsletter_unhold\\b/i.test(text.trim());`
    beside `isNewsletterEval` (line ~115) with a comment noting the eval regex does NOT match
    it (the Phase 9 dead-command landmine); (3) OR `isNewsletterUnhold` into the
    `isGatoBrainCommand` expression (line ~116). Mirror the EXISTING backslash escaping
    verbatim — the regexes live inside a template literal.
  </action>
  <verify>
    <automated>python3 -c "import ast; ast.parse(open('/root/bitcoin_bot/docker/gato_brain/gato_brain.py').read())" && grep -c "def handle_newsletter_unhold" /root/bitcoin_bot/docker/gato_brain/gato_brain.py | grep -q 1 && grep -q 'startswith("/newsletter_unhold")' /root/bitcoin_bot/docker/gato_brain/gato_brain.py && grep -q "isNewsletterUnhold" /root/bitcoin_bot/docker/gato/inject-gato-brain.mjs && grep -q "isNewsletterEval || isNewsletterUnhold\|isNewsletterUnhold || isNewsletterEval\|isNewsletterPreview || isNewsletterEval || isNewsletterUnhold" /root/bitcoin_bot/docker/gato/inject-gato-brain.mjs && node --check /root/bitcoin_bot/docker/gato/inject-gato-brain.mjs</automated>
  </verify>
  <done>gato_brain.py parses clean with the handler + shadow helper + 2c-4 dispatch branch; inject-gato-brain.mjs parses clean with a DISTINCT isNewsletterUnhold regex OR'd into isGatoBrainCommand and a help-list line; no `.in_()` anywhere on the new read/update path.</done>
</task>

<task type="auto">
  <name>Task 2: tests/test_unhold_handler.py mirroring the test_31 harness</name>
  <files>tests/test_unhold_handler.py</files>
  <action>
    Create `tests/test_unhold_handler.py` mirroring `tests/test_31_newsletter_eval_handler.py`
    EXACTLY in harness shape: same module-stub preamble (schedule/tweepy/resend/markdown/
    sibling-module/anthropic/fastapi/pydantic/supabase stubs, SUPABASE_URL/KEY env defaults),
    same `sys.path.insert(0, str(_ROOT / "docker" / "gato_brain"))` + `import gato_brain as gb`,
    same standalone `__main__` runner. Extend the stub for this handler's needs: a
    `StubSupabase(tables={"newsletters": [...], "edition_evals": [...]})` whose `table(name)`
    returns a `_StubQuery` over that table's rows; `_StubQuery` supports select/eq/order/limit/
    execute AND `update(payload)` (record `("update", table, payload)` plus subsequent eq into
    `captured`, apply the payload to matching rows on execute so post-state is assertable);
    structurally NO `in_` method (accidental `.in_()` → AttributeError). Add an optional
    `raise_on_execute` flag for the error-path test.

    Row builders: `_primary_row(edition, *, held, row_id, reason=None, created_at=...)` and
    `_shadow_row(edition, row_id)` (data_snapshot `{"ab_comparison": True}` + title
    `[BLOCK PIPELINE A/B] …` + do_not_publish True + status "held"), plus a minimal
    edition_evals det row (reuse the test_31 `_det_row` shape) for the preview-summary test.

    Minimum test cases (all calling `gb.handle_newsletter_unhold(...)`):
    1. `test_non_owner_refused_and_no_read` — access_tier "free" AND "subscriber": refusal
       mentions owner; `stub.captured == []`.
    2. `test_bare_command_previews_without_mutating` — held primary + shadow present: reply
       contains the reason text, the row id, "confirm"; NO ("update", ...) in captured.
    3. `test_preview_includes_eval_flag_summary` — with edition_evals rows present the preview
       carries the labels/counts trend line (assert "fab=" in out); with none, the explicit
       no-eval-rows message.
    4. `test_confirm_releases_primary_row_only` — captured contains exactly one update with
       payload `{"do_not_publish": False, "status": "draft", "do_not_publish_reason": None}`
       targeted `("eq", "id", primary_id)`; the shadow row's fields are UNCHANGED after
       execute; reply confirms release.
    5. `test_shadow_only_edition_refused` — edition whose ONLY held row is the shadow (plus,
       in a second sub-case, no primary at all): "by design"/"not releasable" message, zero
       updates — even with `confirm`.
    6. `test_edition_not_found` and `test_primary_not_held` — distinct messages; not-held
       reports the primary's current status; zero updates.
    7. `test_multiple_held_primaries_targets_newest` — two held primaries with different
       created_at: the update eq targets the newest row id and the reply notes the count.
    8. `test_supabase_error_returns_message` — raise_on_execute stub: reply contains
       "unhold failed", never empty, no crash.
    9. `test_stub_query_has_no_in_list_method` — structural EVAL-03 guard (mirror test_31).
    10. `test_usage_on_missing_or_bad_arg` — `/newsletter_unhold` and `/newsletter_unhold abc`
        → usage message, zero updates.
  </action>
  <verify>
    <automated>cd /root/bitcoin_bot && python3 tests/test_unhold_handler.py && python3 tests/test_31_newsletter_eval_handler.py</automated>
  </verify>
  <done>All new unhold tests pass standalone AND the existing test_31 eval-handler suite still passes (regression on the shared module + reused helpers). No live DB/network touched.</done>
</task>

<task type="auto">
  <name>Task 3: Commit, scoped deploy (gato_brain + gato), in-container verify</name>
  <files>docker/gato_brain/gato_brain.py, docker/gato/inject-gato-brain.mjs, tests/test_unhold_handler.py</files>
  <action>
    1. Commit the three files: `feat(gato_brain): ship /newsletter_unhold owner command to release held editions` (conventional commit; body notes the two-step confirm + shadow-row exclusion + pre-enforce-blocker todo).
    2. Scoped rebuild on the MAIN tree (worktree-unsafe, operator-approved scope):
       `cd /root/bitcoin_bot/docker && docker compose up -d --build gato_brain gato`.
       Do NOT rebuild or restart the newsletter container (calibration freeze) or any other
       service. Use the SERVICE names `gato_brain`/`gato`, not container names.
    3. In-container verification (the v2.3 packaging lesson — packaging failures are invisible
       to the test suite):
       - `docker exec agentpulse-gato-brain grep -c "def handle_newsletter_unhold" /home/openclaw/gato_brain.py` → 1
       - `docker exec agentpulse-gato-brain grep -c 'startswith("/newsletter_unhold")' /home/openclaw/gato_brain.py` → 1
       - `docker exec openclaw-gato sh -c 'grep -rl "newsletter_unhold" /app --include="*.js" --include="*.ts" | head -3'` → at least one hit (the injected allowlist survived patch + compile; if only .ts hits, also confirm a compiled-output hit before passing)
       - `docker compose -f /root/bitcoin_bot/docker/docker-compose.yml ps gato_brain gato` → both Up/healthy; tail `docker compose logs --tail=20 gato_brain` for a clean startup (no traceback).
    4. Log the resolved todo: move `.planning/todos/pending/2026-07-04-newsletter-unhold-command.md` to `.planning/todos/done/` (create dir if absent) and commit as `docs(todos): resolve newsletter-unhold pre-enforce blocker` — the enforce-flip todo (`2026-07-03-flip-eval-enforce-after-calibration.md`) stays pending and is now unblocked.
  </action>
  <verify>
    <automated>docker exec agentpulse-gato-brain grep -q "def handle_newsletter_unhold" /home/openclaw/gato_brain.py && docker exec openclaw-gato sh -c 'grep -rq "newsletter_unhold" /app' && docker compose -f /root/bitcoin_bot/docker/docker-compose.yml ps gato_brain gato | grep -c "Up" | grep -q 2</automated>
    <human-check>Optional live smoke: send `/newsletter_unhold 104` from the owner Telegram chat — expect the preview (edition 104's primary is status=draft/not held, so expect the "found but not held" message naming row 666a8dea-…); confirm the A/B shadow was not offered.</human-check>
  </verify>
  <done>Both containers rebuilt and healthy carrying the new code (verified INSIDE the running containers); newsletter container untouched; work committed conventionally; todo moved to done.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Telegram user → gato_brain | untrusted chat text crosses into command dispatch; only `access_tier == "owner"` may release a hold |
| gato_brain → newsletters table | a write that OVERRIDES an automated fabrication verdict |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-UNH-01 | Elevation of privilege | handle_newsletter_unhold | mitigate | owner gate is the FIRST statement, before any read/write (D-12 pattern); test 1 proves zero DB calls for non-owner |
| T-UNH-02 | Tampering | confirm update path | mitigate | two-step confirm required to mutate; update targeted `.eq("id", row_id)` only; shadow rows structurally excluded (`_unhold_is_shadow`) |
| T-UNH-03 | Information disclosure | preview eval summary + logs | mitigate | preview reuses labels/counts-only `_format_eval_trend` (never `_format_eval_detail` prose); `[UNHOLD]` logs carry edition + row id only (T-30-LOG) |
| T-UNH-04 | Repudiation | release action | accept | reply + `[UNHOLD]` log line record edition/row id; append-only `edition_revisions` audit trail is a deferred v2.3-future item (REV-01) |
| T-UNH-05 | Denial of service (silence) | missing allowlist entry | mitigate | distinct `isNewsletterUnhold` regex OR'd into `isGatoBrainCommand` + gato rebuild + in-container grep (the Phase 9 landmine, bit twice) |
| T-UNH-SC | Tampering | dependency installs | accept | no new dependencies installed in this plan |
</threat_model>

<verification>
- `python3 tests/test_unhold_handler.py` — all cases green standalone.
- `python3 tests/test_31_newsletter_eval_handler.py` — regression green (shared module/helpers).
- In-container greps prove handler + dispatch inside `agentpulse-gato-brain` and the allowlist inside `openclaw-gato` (v2.3 packaging lesson).
- `docker compose ps` — gato_brain + gato healthy; newsletter container untouched.
- No processor diff (`git diff --stat` shows only the three planned files + todo move).
</verification>

<success_criteria>
- Owner has a working two-step Telegram escape hatch for a wrongly-held edition: preview (informed, non-mutating) → confirm (targeted release by row id).
- Released row re-enters both existing publish paths with zero processor changes.
- A/B shadow rows are provably un-releasable; non-owners provably read nothing.
- The P1 pre-enforce blocker todo is resolved; the `enforce=true` flip is unblocked.
</success_criteria>

<output>
Create `.planning/quick/260705-ufj-ship-newsletter-unhold-operator-command-/260705-ufj-SUMMARY.md` when done.
</output>
