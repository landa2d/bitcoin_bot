---
phase: quick-260706-lim
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - supabase/migrations/047_promote_block_edition.sql
  - docker/gato_brain/gato_brain.py
  - docker/gato/inject-gato-brain.mjs
  - tests/test_promote_handler.py
autonomous: true
requirements: [QUICK-260706-LIM]

must_haves:
  truths:
    - "Owner sends `/newsletter_promote <edition#>` over Telegram and gets a zero-mutation preview: shadow+primary row ids, suggested public edition number, eval verdict (or explicit no-eval warning), and the exact confirm command"
    - "Owner sends `/newsletter_promote <edition#> confirm` and the block-pipeline A/B shadow row atomically becomes public edition N: title prefix stripped, status='draft', do_not_publish=false, promotion stamps in data_snapshot; the single-pass primary flips to status='held' with superseded_by — all in ONE transaction or NOTHING"
    - "A non-owner caller is refused before any database read"
    - "Any RPC validation failure (missing shadow, missing primary, edition-number collision) rolls the whole transaction back and the handler surfaces the error verbatim with a nothing-was-mutated note"
    - "Migration 047 is AUTHORED but NOT applied by the executor (orchestrator/MCP owns apply)"
  artifacts:
    - path: "supabase/migrations/047_promote_block_edition.sql"
      provides: "Atomic promote_block_edition RPC + the operator's durable bridge-scope/marker-inventory/limitation record"
      contains: "SECURITY DEFINER"
      min_lines: 80
    - path: "docker/gato_brain/gato_brain.py"
      provides: "handle_newsletter_promote handler + 2c-5 dispatch branch"
      contains: "def handle_newsletter_promote"
    - path: "docker/gato/inject-gato-brain.mjs"
      provides: "isNewsletterPromote allowlist regex OR'd into isGatoBrainCommand + help-list line"
      contains: "isNewsletterPromote"
    - path: "tests/test_promote_handler.py"
      provides: "Bridge-scope sanity tests (~4-5 cases) on the REAL handler vs a stub Supabase"
      min_lines: 100
  key_links:
    - from: "docker/gato_brain/gato_brain.py"
      to: "promote_block_edition RPC"
      via: "sb.rpc('promote_block_edition', {...}) on confirm"
      pattern: "rpc\\(['\\\"]promote_block_edition"
    - from: "docker/gato/inject-gato-brain.mjs"
      to: "gato_brain /chat dispatch"
      via: "isNewsletterPromote OR'd into isGatoBrainCommand"
      pattern: "isNewsletterPromote"
    - from: "gato_brain dispatch (~:3297 region)"
      to: "handle_newsletter_promote"
      via: "_msg_lower.startswith('/newsletter_promote') branch before the intent router"
      pattern: "startswith\\(\\\"/newsletter_promote\\\"\\)"
---

<objective>
Ship `/newsletter_promote <edition#> [confirm]` as a BRIDGE-scope owner command: an atomic
Postgres RPC (migration 047, authored-not-applied) plus an owner-gated gato_brain handler
that promotes the weekly block-pipeline A/B shadow row to the public edition series and
supersedes the single-pass primary — replacing the operator's error-prone manual SQL
promotion workflow (which missed the migration-046 `do_not_publish` column and blocked
edition #34's auto-publish on 2026-07-06).

**Design is operator-approved and LOCKED (2026-07-06).** Execute exactly the specification
below — do not redesign, do not add mutations beyond the locked lists, do not extend test
scope beyond bridge-scope sanity.

Purpose: eliminate the multi-marker manual promotion footgun during the bridge window
(until `block_pipeline.enabled=true` cut-over, target 2026-08-01).
Output: migration 047 (authored), handler + dispatch + allowlist, ~4-5 sanity tests,
scoped gato_brain+gato rebuild verified in-container.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@docker/gato_brain/gato_brain.py            (unhold handler ~:2806-2941 is the EXACT pattern to mirror; `_unhold_is_shadow` :2826; dispatch branches 2c-3/2c-4 :3275-3297; `_eval_read_by_edition` :2440)
@supabase/migrations/046_do_not_publish_columns.sql   (house style: header banner, SQL-first apply discipline)
@tests/test_unhold_handler.py               (harness + StubSupabase pattern to reuse; bridge scope = FAR less coverage than this file)
@docker/gato/inject-gato-brain.mjs          (allowlist region ~:113-120; help list ~:37-43)
</context>

<constraints>
- Python 3.12, snake_case, logger `"gato-brain"`, fixed log label `[PROMOTE]` carrying ids/edition numbers ONLY — never draft prose or reason text (T-30-LOG).
- Plain `.eq()` reads only — NEVER supabase-py `.in_()` (silent-failure anti-pattern, EVAL-03).
- Migration 047 is AUTHORED in Task 1; APPLYING it is orchestrator-owned via MCP (project ref zxzaaqfowtqvmsbitqpu). The executor must NOT attempt to apply it, run `supabase db push`, or use any Supabase MCP apply tool.
- Task 3 rebuild: `gato_brain` and `gato` services ONLY. NEVER rebuild the `newsletter` container (calibration freeze). Rebuild runs on the main tree at /root/bitcoin_bot (worktree-unsafe; operator-approved).
- Conventional commits, one commit per task.
</constraints>

<tasks>

<task type="auto">
  <name>Task 1: Author migration 047 — atomic promote_block_edition RPC + durable bridge-scope header</name>
  <files>supabase/migrations/047_promote_block_edition.sql</files>
  <action>
Author `supabase/migrations/047_promote_block_edition.sql` (next number after 046). AUTHORED ONLY — the apply is an orchestrator-owned MCP step; state this in the file banner exactly like 046's SQL-FIRST banner (do NOT apply from this task, do NOT `supabase db push`).

**Function signature (exact):**
`CREATE OR REPLACE FUNCTION promote_block_edition(p_shadow_id uuid, p_primary_id uuid, p_new_edition_number int, p_reason text) RETURNS jsonb`
with `SECURITY DEFINER` and `SET search_path = public` on the function definition. The `SET search_path = public` clause is MANDATORY — the earlier `transfer_between_agents` RPC broke on an empty search_path; do not repeat that trap. `LANGUAGE plpgsql`.

**Validations (each `RAISE EXCEPTION` with a descriptive message — a raise rolls back the whole transaction, which is the atomicity contract):**
1. Shadow row `p_shadow_id` exists AND is actually a shadow: `(data_snapshot->>'ab_comparison' = 'true' OR title LIKE '[BLOCK PIPELINE A/B]%')`. Raise if missing or not-a-shadow.
2. Primary row `p_primary_id` exists. Raise if missing.
3. `p_new_edition_number` is not already used by any published row: raise if `EXISTS (SELECT 1 FROM newsletters WHERE edition_number = p_new_edition_number AND status = 'published')`.

**Mutations (one transaction — plpgsql function body is inherently atomic):**
- Shadow row (`id = p_shadow_id`):
  - `title` and `title_impact`: strip the leading `'[BLOCK PIPELINE A/B] '` prefix (prefix + trailing space) from each — e.g. `title = CASE WHEN title LIKE '[BLOCK PIPELINE A/B] %' THEN substring(title from 22) ELSE title END` or equivalent; same for `title_impact` (which may be NULL — handle it).
  - `edition_number = p_new_edition_number`
  - `status = 'draft'`
  - `do_not_publish = false` (the migration-046 COLUMN — the canonical home; this is the exact marker the manual workflow missed)
  - `data_snapshot = (data_snapshot - 'ab_comparison' - 'do_not_publish') || jsonb_build_object('promoted_at', now(), 'promotion_reason', p_reason, 'promoted_from_held', true, 'replaces_single_pass_draft', p_primary_id::text)` — these four stamp keys match the operator's existing manual promotion metadata schema exactly; do not rename them.
  - Do NOT touch `do_not_publish_reason` or add any other mutation — the locked design enumerates exactly the above; the publish gate reads only the boolean + status, so a stale reason string is cosmetic and deliberately left alone.
- Primary row (`id = p_primary_id`):
  - `status = 'held'`
  - `data_snapshot = data_snapshot || jsonb_build_object('superseded_by', p_shadow_id::text)`

**Return:** `jsonb_build_object('shadow_id', p_shadow_id, 'new_edition_number', p_new_edition_number, 'primary_id', p_primary_id, 'primary_status', 'held')` — the handler's confirm reply renders this summary.

**MANDATORY header comment block** (this is the operator's durable record — include the substance of all three sections verbatim):

1. BRIDGE SCOPE: this command is designed to be RETIRED when `block_pipeline.enabled=true`. Cut-over criteria: (1) two consecutive Fridays with symmetric evals on both paths, no crashes; (2) block pipeline Phase D fabrications entirely stop-list FPs on both weeks; (3) block fact-base persistence shipped; (4) block pipeline angles meet the "editing not rewriting" threshold; (5) live-proof of the block-primary eval path. Target flip: 2026-08-01; if criteria don't hold by then, reassess upgrading this command to keeper scope.

2. DEFINITIVE SHADOW-MARKER INVENTORY (6): status='held'; title prefix '[BLOCK PIPELINE A/B]' on title+title_impact; do_not_publish COLUMN (canonical since migration 046, 2026-07-02); data_snapshot.do_not_publish (retired pre-046 location); data_snapshot.ab_comparison; content_telegram absent (not a hold marker — see limitation below). HISTORY NOTE: migration 046 moved do_not_publish's canonical home from data_snapshot to the column; the operator's manual promotion workflow tracked the old location and missed the column, which blocked edition #34's auto-publish on 2026-07-06.

3. KNOWN LIMITATION (decided 2026-07-06): promoted rows have no content_telegram; publish falls back to content_markdown[:4000]. Generating it at promotion would duplicate that fallback byte-for-byte, so it is deliberately NOT done at bridge scope; a proper Telegram digest is keeper/LLM work.

Commit: `feat(quick-260706-lim): author migration 047 promote_block_edition atomic RPC`
  </action>
  <verify>
    <automated>test -f supabase/migrations/047_promote_block_edition.sql && grep -c "SECURITY DEFINER" supabase/migrations/047_promote_block_edition.sql && grep -c "SET search_path = public" supabase/migrations/047_promote_block_edition.sql && grep -c "RAISE EXCEPTION" supabase/migrations/047_promote_block_edition.sql && grep -ci "BRIDGE SCOPE" supabase/migrations/047_promote_block_edition.sql && grep -ci "SHADOW-MARKER INVENTORY" supabase/migrations/047_promote_block_edition.sql && grep -ci "KNOWN LIMITATION" supabase/migrations/047_promote_block_edition.sql && grep -c "replaces_single_pass_draft" supabase/migrations/047_promote_block_edition.sql && grep -c "superseded_by" supabase/migrations/047_promote_block_edition.sql</automated>
  </verify>
  <done>Migration 047 authored with the exact 4-param SECURITY DEFINER + search_path signature, all 3 validations raising, the locked shadow/primary mutation sets, the jsonb return summary, and the full 3-section header record (bridge scope + marker inventory/history + content_telegram limitation). File NOT applied. Committed.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: handle_newsletter_promote handler + dispatch + gato allowlist + bridge-scope sanity tests</name>
  <files>docker/gato_brain/gato_brain.py, docker/gato/inject-gato-brain.mjs, tests/test_promote_handler.py</files>
  <behavior>
    - Test 1 (owner gate): tiers "free"/"subscriber", both bare and confirm forms → owner-only refusal AND `stub.captured == []` (refused BEFORE any read).
    - Test 2 (preview happy path): owner + `/newsletter_promote 104` on a stub holding a shadow row (id "shadow-104", title "[BLOCK PIPELINE A/B] …", data_snapshot.ab_comparison=True), a primary sibling (id "prim-104"), a published row with edition_number 42, and an edition_evals row keyed newsletter_id="shadow-104" → reply contains "shadow-104", "prim-104", suggested number "43" (max published 42 + 1), the eval verdict, and the exact confirm command `/newsletter_promote 104 confirm`; NO `update` and NO `rpc` in `stub.captured`.
    - Test 3 (confirm happy path): owner + `/newsletter_promote 104 confirm` → exactly ONE rpc call captured as `("rpc", "promote_block_edition", params)` with `p_shadow_id="shadow-104"`, `p_primary_id="prim-104"`, `p_new_edition_number=43`, `p_reason="promoted via /newsletter_promote by operator"`; reply renders the RPC's returned summary AND reminds that `/newsletter_publish` is the next step.
    - Test 4 (shadow not found): edition whose rows contain NO shadow (primary only) → clear "no shadow row" error, zero rpc; when the primary's data_snapshot carries `superseded_by`, the error says the shadow was already promoted.
    - Test 5 (no eval recorded): preview on a shadow with zero edition_evals rows → reply contains the explicit "⚠ no eval recorded for this row" line (never a silent omission).
  </behavior>
  <action>
**Tests first** (`tests/test_promote_handler.py`): reuse the `tests/test_unhold_handler.py` harness verbatim (module stubs, env defaults, `sys.path` insert, standalone `__main__` runner) and its `_StubQuery`/`StubSupabase` double, EXTENDED with an `rpc(fn_name, params)` method on `StubSupabase` that appends `("rpc", fn_name, dict(params))` to `captured` and returns an object whose `.execute()` yields a `_StubResult` with the canned jsonb summary dict (`{"shadow_id": ..., "new_edition_number": ..., "primary_id": ..., "primary_status": "held"}`). Keep the NO-`.in_()` structural property. BRIDGE SCOPE: the ~5 cases in `<behavior>` and NOTHING more — explicitly do NOT port test_unhold_handler.py's full matrix. Add a module docstring noting the deliberately-skipped edge coverage (multi-shadow editions, republish collisions, concurrent promotion) as iterate-live known unknowns — these ALSO go in the SUMMARY.

**Handler** (`docker/gato_brain/gato_brain.py`, place directly after `handle_newsletter_unhold` ~:2941, mirroring its shape):

`def handle_newsletter_promote(message: str, access_tier: str = "free", supabase_client=None) -> str:`

- Docstring: bridge-scope note (retired at `block_pipeline.enabled=true` cut-over) + pointer to migration 047's header for the definitive shadow-marker inventory and cut-over criteria.
- Owner gate FIRST — non-owner returns a refusal BEFORE any database read (mirror T-UNH-01).
- Parse `<edition#> [confirm]` exactly like unhold (`lstrip("#").isdigit()`, usage string `Usage: /newsletter_promote <edition#> [confirm]`).
- Lookup by the SHADOW row's CURRENT edition number (the Friday number, e.g. 104): one `.eq("edition_number", edition)` select on `newsletters` (columns: id, edition_number, status, title, do_not_publish, data_snapshot, created_at). Split rows using the existing `_unhold_is_shadow` predicate (reuse it directly — do not duplicate). Clear, distinct errors: edition not found / no shadow row for this edition / no primary sibling (non-shadow row, same edition_number). "Shadow already promoted" detection: when no shadow row matches but a primary's `data_snapshot` (dict-guarded, may be str/None) carries `superseded_by`, say the edition's shadow was already promoted — not an anonymous "no shadow". If multiple shadow or primary candidates exist, target the newest by `created_at` (mirror the unhold multi-row posture).
- **Preview (bare form — mutates NOTHING, calls NO rpc):** reply with shadow row id + primary row id; computed suggested public number = (max `edition_number` among `status='published'` rows) + 1, read via `.eq("status", "published").order("edition_number", desc=True).limit(1)`; the shadow row's eval verdict(s) from `edition_evals` via `.eq("newsletter_id", <shadow row id>)` (labels/verdicts only — reuse/mirror the trend formatter style, NEVER draft prose) or the explicit line `⚠ no eval recorded for this row`; the exact confirm command `/newsletter_promote <edition> confirm`. State plainly "This is a PREVIEW — nothing was changed." Log `logger.info("[PROMOTE] preview edition=%s shadow=%s primary=%s suggested=%s", ...)` — ids/numbers only.
- **Confirm:** `sb.rpc("promote_block_edition", {"p_shadow_id": <shadow id>, "p_primary_id": <primary id>, "p_new_edition_number": <computed suggested number>, "p_reason": "promoted via /newsletter_promote by operator"}).execute()`; reply renders the RPC's returned jsonb summary (new edition number, shadow id now draft, primary id now held) + reminder that `/newsletter_publish` is the next step. Log `[PROMOTE] promoted ...` ids/numbers only.
- **RPC exception:** surface the exception message, fail loud, and state explicitly that NOTHING was mutated — the RPC is atomic, a raise rolled the whole transaction back (that atomicity is the entire point of the RPC; say so in the error reply). Wrap the handler body in the same try/except-return shape as unhold (`⚠ promote failed: {e}` + `logger.error("[PROMOTE] handler failed: %s", type(e).__name__, exc_info=True)`).
- Reads are plain `.eq()` ONLY — never `.in_()`.

**Dispatch** (gato_brain.py, new `2c-5` branch immediately after the 2c-4 unhold branch ~:3297, BEFORE `/x-`): `if _msg_lower.startswith("/newsletter_promote"):` → `handle_newsletter_promote(req.message, access_tier)` → `ChatResponse(intent="NEWSLETTER_COMMAND")`, exactly like 2c-4. Add the no-prefix-collision comment: "/newsletter_promote" does not start with "/newsletter_preview", "/newsletter_eval", or "/newsletter_unhold" (and vice versa), so branch order among them is safe — but keep 2c-5 after 2c-4 for reading order.

**Allowlist** (`docker/gato/inject-gato-brain.mjs`, ~:113-120 region): add a DISTINCT `const isNewsletterPromote = text && /^\/newsletter_promote\b/i.test(text.trim());` with the Phase-9 dead-command-landmine comment, OR it into `isGatoBrainCommand`, and add the help-list line `/newsletter_promote [n] — Promote block A/B row to public edition (owner)` in the ~:37-43 command list. VERIFY no prefix collisions with the existing `/newsletter_preview` and `/newsletter_publish` regexes: all use `\b`-anchored distinct literals, and `/newsletter_promote` shares only the `/newsletter_p` stem — the full literals differ, so none of the three regexes matches another's command. Match the escaping style of the surrounding lines exactly (the file uses `\\/` inside a template/backtick context — copy the neighboring `isNewsletterUnhold` line's exact escaping).

Run the new tests, then the unhold regression. Commit in two conventional commits: `test(quick-260706-lim): add bridge-scope sanity tests for /newsletter_promote` then `feat(gato_brain): ship /newsletter_promote bridge command promoting the block A/B row`.
  </action>
  <verify>
    <automated>python3 tests/test_promote_handler.py && python3 tests/test_unhold_handler.py && python3 -c "import ast; ast.parse(open('docker/gato_brain/gato_brain.py').read())" && grep -c "isNewsletterPromote" docker/gato/inject-gato-brain.mjs && grep -c "def handle_newsletter_promote" docker/gato_brain/gato_brain.py && grep -c 'startswith("/newsletter_promote")' docker/gato_brain/gato_brain.py</automated>
  </verify>
  <done>Handler + 2c-5 dispatch + allowlist landed; `isNewsletterPromote` appears at least twice in the mjs (declaration + isGatoBrainCommand OR); all new sanity tests pass (owner gate / preview-no-mutation / confirm-rpc-params / shadow-not-found / no-eval line); unhold regression green; committed.</done>
</task>

<task type="auto">
  <name>Task 3: Scoped rebuild gato_brain + gato and in-container verification</name>
  <files>docker/gato_brain/gato_brain.py</files>
  <action>
Deploy the two touched services on the MAIN tree (operator-approved; this step is worktree-unsafe — absolute paths under /root/bitcoin_bot only). NEVER touch the `newsletter` service (calibration freeze).

1. Pre-build syntax check: `python3 -c "import ast; ast.parse(open('/root/bitcoin_bot/docker/gato_brain/gato_brain.py').read())"`.
2. Scoped rebuild: `cd /root/bitcoin_bot/docker && docker compose up -d --build gato_brain gato` (service names, NOT container names — the Phase-18 lesson).
3. In-container verification (the v2.3 packaging lesson: verify INSIDE the running container, packaging bugs are invisible to the test suite; gato_brain code lives at `/home/openclaw/gato_brain.py`, NOT `/app`):
   - `docker compose -f /root/bitcoin_bot/docker/docker-compose.yml exec -T gato_brain grep -c "def handle_newsletter_promote" /home/openclaw/gato_brain.py` → ≥ 1
   - `docker compose -f /root/bitcoin_bot/docker/docker-compose.yml exec -T gato_brain grep -c "newsletter_promote" /home/openclaw/gato_brain.py` → ≥ 2 (handler + dispatch)
   - Verify the gato container carries the allowlist: grep the built OpenClaw injection for `isNewsletterPromote` inside the gato container (locate the injected file the same way the 260705-ufj task did; if the source mjs is baked at build time, grepping the container's copy of `inject-gato-brain.mjs` suffices).
4. Container health: `docker compose -f /root/bitcoin_bot/docker/docker-compose.yml ps gato_brain gato` shows both Up/healthy; tail `docker compose ... logs --tail=30 gato_brain` for a clean uvicorn start (no ImportError/SyntaxError).
5. Migration apply is NOT this task's job — migration 047 remains authored-only; the orchestrator applies it via MCP. Record this handoff explicitly in the SUMMARY (the command's confirm path will 404 on the missing RPC until 047 is applied — expected, note it).

Commit (docs-only if no code changed in this task): `docs(quick-260706-lim): ship /newsletter_promote bridge command` with the SUMMARY.
  </action>
  <verify>
    <automated>docker compose -f /root/bitcoin_bot/docker/docker-compose.yml exec -T gato_brain grep -c "def handle_newsletter_promote" /home/openclaw/gato_brain.py && docker compose -f /root/bitcoin_bot/docker/docker-compose.yml ps gato_brain gato | grep -c "Up"</automated>
  </verify>
  <done>gato_brain + gato rebuilt from the main tree and healthy; handler + dispatch proven present INSIDE the running gato_brain container; allowlist proven in the gato container; newsletter container untouched; SUMMARY records the orchestrator-owned 047 MCP-apply handoff + the iterate-live known unknowns (multi-shadow editions, republish collisions, concurrent promotion).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Telegram → gato_brain | Untrusted user text crosses into the command handler; only `access_tier` from the caller identity gates mutation |
| gato_brain → Postgres RPC | SECURITY DEFINER function executes with definer privileges on operator data |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-PROM-01 | Elevation of privilege | handle_newsletter_promote | mitigate | Owner gate checked BEFORE any read/write (mirrors T-UNH-01); tests assert zero DB traffic for non-owner |
| T-PROM-02 | Tampering | promote_block_edition RPC | mitigate | All three validations RAISE EXCEPTION inside one plpgsql transaction — partial promotion is impossible; edition-number collision with published rows rejected in-function |
| T-PROM-03 | Tampering | SECURITY DEFINER search_path | mitigate | `SET search_path = public` on the function definition (the transfer_between_agents empty-search_path trap) |
| T-PROM-04 | Information disclosure | [PROMOTE] logs / replies | mitigate | Fixed label, ids/edition numbers/verdict labels only — never draft prose or reason text (T-30-LOG) |
| T-PROM-05 | Repudiation | manual-promotion drift | accept | Bridge scope; promotion stamps (promoted_at/promotion_reason/promoted_from_held/replaces_single_pass_draft) in data_snapshot are the audit trail |
| T-PROM-SC | Tampering | package installs | accept | No new packages installed — existing supabase-py/httpx only |
</threat_model>

<verification>
- `python3 tests/test_promote_handler.py` and `python3 tests/test_unhold_handler.py` both green.
- `grep -c "SECURITY DEFINER" supabase/migrations/047_promote_block_edition.sql` ≥ 1; header carries BRIDGE SCOPE + SHADOW-MARKER INVENTORY + KNOWN LIMITATION sections.
- In-container: `handle_newsletter_promote` present in `/home/openclaw/gato_brain.py` of the RUNNING gato_brain container; `isNewsletterPromote` in the gato container's injection file; both containers Up.
- Migration 047 NOT applied (no MCP apply call, no `supabase db push` in the transcript) — apply is the orchestrator's handoff item.
</verification>

<success_criteria>
- Owner preview and confirm flows work exactly per the locked design (two-step, atomic RPC, fail-loud on any validation error with a nothing-was-mutated reply).
- Migration 047 is a complete, reviewable artifact containing the operator's durable bridge-scope/marker-inventory/limitation record.
- Command is live over Telegram after the scoped rebuild (allowlist + dispatch both verified in-container); newsletter container untouched.
- SUMMARY documents: 047 MCP-apply handoff, the confirm-path-404-until-applied expectation, and the deliberately-skipped edge coverage as iterate-live items.
</success_criteria>

<output>
Create `.planning/quick/260706-lim-ship-newsletter-promote-bridge-command-a/260706-lim-SUMMARY.md` when done.
</output>
