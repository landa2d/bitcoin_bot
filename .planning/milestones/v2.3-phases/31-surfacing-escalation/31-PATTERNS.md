# Phase 31: Surfacing & Escalation - Pattern Map

**Mapped:** 2026-07-02
**Files analyzed:** 3 modified files (5 distinct code sites) + 1 new local read-helper + tests
**Analogs found:** 6 / 6 (all sites have a strong in-repo analog)

> This phase creates **no new files** — it modifies three existing files. Every new
> behavior copies an analog that already lives in this repo. Services are self-contained
> (no cross-container imports): the `edition_eval.py` read functions are the **semantics to
> mirror**, re-implemented locally as `.eq()`-only selects — NOT importable.

## File Classification

| Modified File / Site | Role | Data Flow | Closest Analog | Match Quality |
|----------------------|------|-----------|----------------|---------------|
| `agentpulse_processor.py` :: `send_telegram` (:9611) | utility | request-response | `newsletter_poller.py` :: `_alert_operator` (:365) | exact (fail-loud contract) |
| `agentpulse_processor.py` :: `scheduled_notify_newsletter` (:10632) | service (scheduled job) | CRUD-read + transform | self (static) + `scheduled_auto_publish_newsletter` (:10641) for the row lookup | role-match |
| `agentpulse_processor.py` :: `scheduled_auto_publish_newsletter` (:10641) | service (scheduled job) | CRUD | self — already calls `send_telegram` at :10683 (critical caller) | exact |
| `agentpulse_processor.py` :: new local eval-read helper | utility | CRUD-read | `edition_eval.py` :: `read_evals_by_newsletter` (:186) / `read_eval_trend` (:198) | exact (semantics, not importable) |
| `gato_brain.py` :: new `/newsletter_eval` handler | route/controller | request-response + CRUD-read | `/newsletter_preview` handler (:2708) + `handle_map_command` (:2366) | exact (dispatch) + role-match (gating) |
| `inject-gato-brain.mjs` :: `isGatoBrainCommand` allowlist (:107-112) | middleware/config | request-response (routing) | `isNewsletterPreview` regex (:111) | exact |

---

## Pattern Assignments

### `agentpulse_processor.py` :: `send_telegram` hardening (utility, request-response)

**Current implementation** (`docker/processor/agentpulse_processor.py:9611-9657`) — the fail-SOFT
paths to harden. Two problems: bare `return` on unset env (:9613-9614), and no bool return:

```python
def send_telegram(message: str):
    """Send notification to Telegram, splitting if over 4096 chars."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_OWNER_ID:
        return                                          # <-- SURF-01: silent no-op → must be ERROR + return False
    MAX_LEN = 4000  # leave margin under Telegram's 4096 limit
    # ... 4000-char newline-boundary splitting (KEEP verbatim, :9618-9632) ...
    try:
        with httpx.Client() as client:
            for chunk in chunks:
                resp = client.post( ... 'parse_mode': 'Markdown' ... )
                if resp.status_code != 200:
                    logger.warning(f"Telegram Markdown failed ({resp.status_code}), retrying as plain text")
                    resp = client.post( ... )           # plain-text fallback (KEEP)
                    if resp.status_code != 200:
                        logger.error(f"Telegram send failed ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")      # <-- currently returns None → must return False
```

**Analog for the "loud" contract** — `docker/newsletter/newsletter_poller.py:365-397` (`_alert_operator`,
already fail-loud per P30 D-07; left UNTOUCHED this phase per D-01/D-14, but its shape is the target):

```python
def _alert_operator(message: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    owner = os.getenv("TELEGRAM_OWNER_ID")
    safe = " ".join(str(message).split())[:1000]  # single-line + bound (log/injection hygiene)
    if not token or not owner:
        # Fail LOUD (D-07): never a silent no-op. Log a LABEL only — never the eval key.
        logger.error(
            "[EVAL-ALERT] cannot alert operator — TELEGRAM_BOT_TOKEN/TELEGRAM_OWNER_ID unset; "
            "message=%s", safe,
        )
        return
    try:
        with httpx.Client(timeout=10) as hc:
            resp = hc.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": owner, "text": safe})
            if resp.status_code != 200:
                logger.error("[EVAL-ALERT] Telegram send failed (%s): %s", resp.status_code, resp.text[:200])
    except Exception:
        logger.error("[EVAL-ALERT] operator alert send failed", exc_info=True)  # never swallow silently
```

**What to copy / change (D-02, D-04):**
- Change signature to `def send_telegram(message: str) -> bool:`; return `True` on success, `False` on any failure.
- Replace the bare `return` (:9614) with `logger.error("<fixed grep-able label> TELEGRAM_BOT_TOKEN/TELEGRAM_OWNER_ID unset ...")` then `return False`.
- Upgrade the delivery-failure paths from `logger.warning`/bare log to a `False` return; the ERROR log at :9655 already exists — ensure it always returns `False` on failure and `True` at the end.
- **Startup ERROR (D-04):** add a fixed grep-able label ERROR at module init / `init_clients` time (mirror the `TELEGRAM_BOT_TOKEN`/`TELEGRAM_OWNER_ID` env read at `:396-397`) if either env is unset — visible at container boot, not first-alert-time. The service still runs (never `raise`).
- **25 existing call sites assume it never raises** — do NOT raise; bool return is additive/backward-compatible.

**Env + client init** (`docker/processor/agentpulse_processor.py:396-397`, and `httpx.Client()` used inline):
```python
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_OWNER_ID = os.getenv('TELEGRAM_OWNER_ID')
```

---

### `agentpulse_processor.py` :: `scheduled_notify_newsletter` extension (service, CRUD-read + transform)

**Current implementation** (`docker/processor/agentpulse_processor.py:10632-10638`) — a static one-liner:

```python
def scheduled_notify_newsletter():
    """Notify owner that a new newsletter may be ready for review."""
    logger.info("[PIPELINE] Newsletter notification sent")
    send_telegram(
        "📰 New AgentPulse Brief is ready for review. "
        "Send /newsletter_publish to publish, or it will auto-publish at 13:00 UTC."
    )
```

**Schedule wiring** (`docker/processor/agentpulse_processor.py:11380-11381`) — Friday 12:00 UTC hook, unchanged:
```python
schedule.every().friday.at("12:00").do(scheduled_notify_newsletter)
schedule.every().monday.at("11:00").do(scheduled_auto_publish_newsletter)
```

**Row-lookup analog** — how to locate the current draft(s), from `scheduled_auto_publish_newsletter`
(`docker/processor/agentpulse_processor.py:10650-10661`). NOTE this uses `.in_('status', ...)` on the
`newsletters` table (existing, works) — but the NEW `edition_evals` selects must be `.eq()`-only:

```python
draft = supabase.table('newsletters')\
    .select('*')\
    .in_('status', ['draft', 'pending'])\
    .order('created_at', desc=True)\
    .limit(1)\
    .execute()
if not draft.data:
    logger.info("[PIPELINE] No draft to auto-publish")
    return
newsletter = draft.data[0]
```

**What to build (D-05..D-08):**
- After the existing static notify text, append a per-draft eval section for the current edition covering **both** `pipeline_version`s (`single_pass` primary leads, then `block_v1` telemetry).
- Read `edition_evals` via the NEW local `.eq()`-only helper (see next section) — NO LLM, NO retry state (the Processor stays a dumb sequencer / STATE invariant "no LLM in the Processor").
- **D-06 detail per draft** (~5-6 lines): verdict + final-attempt per-dimension judge scores + fabrication/unverified/mechanical flag counts + attempts used. **Mechanical count ALWAYS shown even on `passed`** (honors P29 D-12).
- **D-07:** missing eval rows → explicit `⚠ no eval recorded for this draft` line; the section is NEVER omitted (NULL ≠ intent, fail-loud).
- **D-08:** while `enforce=false`, `held_fabrication`/`held_voice` verdicts render as `⚠ WOULD HAVE HELD (report-only)` at the top of that draft's block.
- **Critical-caller return check (D-03):** this is a hold/eval-critical site — check `send_telegram`'s bool return and CRITICAL-log on `False`.
- `guard`: `if not supabase: return` (mirror `:10644`).

---

### `agentpulse_processor.py` :: `scheduled_auto_publish_newsletter` return-check (service, CRUD)

**Analog = self** — it already calls `send_telegram` at `docker/processor/agentpulse_processor.py:10683-10686`:
```python
if result.get('published'):
    logger.info("[PIPELINE] Auto-published newsletter #%s", newsletter.get('edition_number'))
    send_telegram(
        f"📰 Newsletter #{newsletter.get('edition_number')} was auto-published "
        f"(no manual publish within review window)."
    )
```
**What to change (D-03):** wrap this call to check the bool return and CRITICAL-log if the auto-publish
notification failed to deliver (this is an eval/hold-critical caller). The `do_not_publish` structural
hold guard already present at `:10666-10671` stays.

---

### `agentpulse_processor.py` :: NEW local eval-read helper (utility, CRUD-read)

**Analog (semantics to mirror — NOT importable across containers):**
`docker/newsletter/edition_eval.py:186-217`:

```python
def read_evals_by_newsletter(supabase, newsletter_id) -> list:
    """Return all eval rows for one newsletter, ordered by attempt — `.eq()` only (EVAL-03)."""
    result = (
        supabase.table("edition_evals")
        .select("*")
        .eq("newsletter_id", newsletter_id)
        .order("attempt")
        .execute()
    )
    return result.data or []

def read_eval_trend(supabase, pipeline_version, limit=8) -> list:
    """Return the recent verdict trend for one pipeline_version, newest edition first."""
    result = (
        supabase.table("edition_evals")
        .select("edition_number, pipeline_version, layer, attempt, eval_status, "
                "verdict, judge_scores, sats_spent, created_at")
        .eq("pipeline_version", pipeline_version)
        .order("edition_number", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []
```

**Secondary `.eq()`-only precedent inside the newsletter service** — `_fetch_prior_published_edition`
(`docker/newsletter/newsletter_poller.py:400-403`): "Plain `.eq('status','published')` — NEVER the
supabase-py in-list filter (the silent-failure ...)".

**Row shape to consume** (from `edition_evals`, migration `045_edition_evals.sql:32-54` + `write_eval_row`
`edition_eval.py:136-150`): `layer` (`deterministic`|`judge`), `attempt` (0=initial, 1/2=rewrite),
`eval_status` (`ok`|`error`), `verdict` (`passed`|`held_fabrication`|`held_voice`|`escalated`),
`deterministic_flags` JSONB `{fabrication:[...], mechanical:[...]}`, `judge_scores` JSONB
`{continuity:1, filler:4, ...}` + before/after exemplars, `judge_feedback` TEXT, `sats_spent`,
`UNIQUE(newsletter_id, layer, attempt)`, verdict-iff-ok CHECK (a verdict exists iff the eval ran).

**What to build:** two small module-level functions in the processor (e.g. `_read_edition_evals(newsletter_id)`
and `_read_eval_trend(pipeline_version, limit=8)`) re-implementing the above `.eq()`-only. Both consumed by
`scheduled_notify_newsletter` (per-draft) and — mirrored again — by the gato_brain handler. **Must be
`.eq()`-only** — the `/newsletter_preview` handler's `.in_()` (:2712) is the ANTI-pattern.

---

### `gato_brain.py` :: NEW `/newsletter_eval` handler (route/controller, request-response + CRUD-read)

**Dispatch-shape analog** — `/newsletter_preview` (`docker/gato_brain/gato_brain.py:2708-2734`).
Copy this direct-dispatch shape (prefix match BEFORE the intent router, `ChatResponse` with a fixed
intent tag). **CAVEAT: the `.in_()` at :2712 is the anti-pattern — the new selects are `.eq()`-only:**

```python
# 2c-2. Newsletter preview — set to preview status (visible on web, not distributed)
if _msg_lower.startswith("/newsletter_preview"):
    try:
        draft = supabase.table("newsletters")\
            .select("id, edition_number")\
            .in_("status", ["draft", "pending"])\        # <-- ANTI-pattern: do NOT copy .in_()
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        if not draft.data:
            preview_resp = "No draft newsletter found to preview."
        else:
            nl = draft.data[0]
            ...
            preview_resp = ( ... )
    except Exception as e:
        preview_resp = f"Preview failed: {e}"
    return ChatResponse(response=preview_resp, session_id="", intent="NEWSLETTER_COMMAND", metadata={})
```

**Insertion point** — the `/chat` dispatch chain, `docker/gato_brain/gato_brain.py:2600-2757`.
`access_tier` is computed once at `:2608-2609` and threaded to gated handlers:

```python
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, x_gato_secret: str = Header(None, alias="X-Gato-Secret")):
    ...
    user = ensure_user(req.user_id)
    access_tier = user.get("access_tier") or "free"     # :2608-2609
    ...
    _msg_lower = req.message.strip().lower()             # :2622
    ...
    if _msg_lower.startswith("/newsletter_preview"):     # :2708  <-- slot /newsletter_eval as a NEW branch near here
        ...
    if _msg_lower.startswith("/x-"): ...                 # :2737
    if _msg_lower.startswith("/map-"):                   # :2750 — access_tier threaded here
        map_response = handle_map_command(req.message, access_tier)
```

**Owner-gating analog (D-12)** — `handle_map_command` (`docker/gato_brain/gato_brain.py:2366-2405`)
plus the per-verb gate used by every write handler (`docker/gato_brain/gato_brain.py:2037`, `:2088`, etc.):

```python
def handle_map_command(message: str, access_tier: str = "free") -> str:
    msg = message.strip()
    parts = msg.split(None, 1)
    cmd = parts[0].lower()
    try:
        if cmd == "/map-status":
            return handle_map_status()
        elif cmd == "/map-approve":
            return handle_map_approve(parts, access_tier)   # gated inside
        ...
    except Exception as e:
        logger.error(f"Map command failed: {cmd} — {e}")

# and the gate itself (handle_map_approve :2037):
if access_tier != "owner":
    return "..."   # owner-only refusal
```

**What to build (D-09..D-12):**
- New branch `if _msg_lower.startswith("/newsletter_eval"):` BEFORE the intent router (near :2708).
- **Owner-gate the WHOLE handler** on `access_tier == "owner"` (D-12) — the view quotes pre-publication
  draft prose (judge evidence + exemplars) that must not leak to a non-owner chat. Thread `access_tier`
  into the handler exactly like the `/map-` branch (:2751).
- Parse optional args: `trend` and/or an `<edition#>` (e.g. `/newsletter_eval trend`, `/newsletter_eval 31`).
- **No-args (D-09):** target the latest newsletter that HAS `edition_evals` rows (any status); if none
  exist anywhere, say so explicitly.
- **Main view (D-10):** per-dimension score lines for all dims; for FAILING dims, the judge's quoted
  evidence + before/after exemplar, excerpt-bounded (~300 chars each); passing dims score-only. Mechanical
  flags listed even on `passed` (P29 D-12).
- **`trend` (D-11):** verdict-per-edition list, last ~8 editions, one line each (mirror `read_eval_trend`,
  limit 8 per pipeline_version).
- Reads via a LOCAL `.eq()`-only select (mirror `read_evals_by_newsletter`/`read_eval_trend`). Module-global
  `supabase` client exists (`gato_brain.py:83`, init at `:621`).
- Return `ChatResponse(..., intent="NEWSLETTER_COMMAND", metadata={})`; the 4000-char splitter downstream
  handles overflow.

---

### `inject-gato-brain.mjs` :: `isGatoBrainCommand` allowlist (middleware/config, routing)

**Analog** — `docker/gato/inject-gato-brain.mjs:107-112`. The command is DEAD over Telegram until it
matches `isGatoBrainCommand` AND gato is rebuilt (the Phase 9 `/map-*` lesson):

```javascript
const isXCommand = text && /^\/x-/i.test(text.trim());
const isMapCommand = text && /^\/map-/i.test(text.trim());
const isCodeCommand = text && /^\/(code|diff|code-diff|code-approve|approve|code-reject|reject|code-merge|followup|repos)\b/i.test(text.trim());
const isCtoCommand = text && /^\/cto\b/i.test(text.trim());
const isNewsletterPreview = text && /^\/newsletter_preview\b/i.test(text.trim());
const isGatoBrainCommand = isXCommand || isMapCommand || isCodeCommand || isCtoCommand || isNewsletterPreview;
```

**What to change (SURF-03):**
- Add `const isNewsletterEval = text && /^\/newsletter_eval\b/i.test(text.trim());` — note
  `/^\/newsletter_preview\b/` will NOT match `/newsletter_eval`, so a NEW regex is required (per D-Discretion).
- Add `isNewsletterEval` to the `isGatoBrainCommand` OR-chain.
- Optionally add a `/newsletter_eval` line to the help text (the block already lists `/newsletter_*` — see
  the help around `:37-39`, `:100-101`).
- **Fall-through safety already handled** (`:142-152`): a gato-brain command that returns nothing / errors
  gets a fixed reply and never falls through to OpenClaw.
- **Deploy (worktree-UNSAFE, orchestrator-owned, D-13):** `docker compose up -d --build gato` on the main
  tree, operator-approved, no `--delete`.

---

## Shared Patterns

### Fail-loud operator alert (SURF-01 contract)
**Source:** `docker/newsletter/newsletter_poller.py:365-397` (`_alert_operator`)
**Apply to:** processor `send_telegram` hardening; every critical caller checks the bool return.
- "Loud" = ERROR-log (never `warning`, never bare `return`) on env-unset AND on send failure; never `raise`.
- Log a fixed grep-able LABEL + bounded single-line message; **never** raw draft prose or the eval key (T-30-LOG).
- `safe = " ".join(str(message).split())[:1000]` single-line + bound before send.

### `.eq()`-only reads (EVAL-03 / milestone invariant)
**Source:** `docker/newsletter/edition_eval.py:186-217`; `newsletter_poller.py:400-403`.
**Apply to:** every NEW `edition_evals` / `newsletters` select in the processor and gato_brain.
- NEVER the supabase-py in-list filter (`.in_()`) — it silently fails. The `/newsletter_preview` handler's
  `.in_()` (`gato_brain.py:2712`) and `scheduled_auto_publish_newsletter`'s `.in_()` (`processor.py:10652`)
  are pre-existing and NOT the pattern to copy for new eval reads.
- `return result.data or []` (never None-propagate).

### Direct command dispatch before the intent router
**Source:** `docker/gato_brain/gato_brain.py:2698-2757` (the `/economics`, `/newsletter_preview`, `/x-`,
`/map-`, `/code`, `/cto` chain).
**Apply to:** the new `/newsletter_eval` branch — `if _msg_lower.startswith(...)` → `ChatResponse(...,
intent="NEWSLETTER_COMMAND")`, returns before `intent_router` runs.

### access_tier owner-gating (autonomy boundary)
**Source:** `handle_map_command` (`gato_brain.py:2366`) + per-verb `if access_tier != "owner":`
(`:2037`, `:2088`, `:2191`, `:2240`, `:2291`, `:2337`). `access_tier` computed at `chat` (`:2608-2609`).
**Apply to:** the whole `/newsletter_eval` handler (D-12) — it exposes unpublished draft prose.

### Telegram 4000-char split + Markdown-first / plain fallback
**Source:** `send_telegram` (`processor.py:9616-9655`); the mjs client-side truncate (`inject-gato-brain.mjs:132-137`).
**Apply to:** both new surfaces inherit this convention; keep the processor splitter logic verbatim during hardening.

### Self-contained services (no cross-container import)
**Source:** milestone invariant (STATE.md); `edition_eval.py` docstring.
**Apply to:** the processor and gato_brain each get their OWN small `.eq()`-only read functions mirroring
`read_evals_by_newsletter`/`read_eval_trend` — they CANNOT `import docker/newsletter/edition_eval.py`.

---

## Test Patterns

**Analog:** `tests/test_27_edition_eval.py:54-146` — the in-memory `StubSupabase` double for `.eq()`-only
read/insert paths, imported via `sys.path.insert` (the REAL module, no re-implementation). Key structural
detail: **`_StubQuery` defines NO in-list method — an accidental `.in_()` raises `AttributeError`,
documenting the EVAL-03 contract structurally** (:87-88):

```python
class _StubQuery:
    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def order(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def execute(self):
        if self._is_insert: return _StubResult([{"id": INSERT_ID}])
        return _StubResult(self._read_data)
    # NOTE: NO in-list filter method — accidental use raises AttributeError (EVAL-03).

class StubSupabase:
    def __init__(self, read_data=None):
        self.captured = []
        self._read_data = read_data if read_data is not None else []
    def table(self, name):
        return _StubQuery(self.captured, self._read_data)
```

**Apply to:**
- Processor eval-read helpers + the notify eval-section formatter: unit-test with `StubSupabase(read_data=[...eval rows...])`; assert D-06/D-07/D-08 render (mechanical count on `passed`, `⚠ no eval recorded`, `WOULD HAVE HELD`). A `StubSupabase` whose `_StubQuery` lacks `.in_()` structurally proves `.eq()`-only.
- `send_telegram` hardening: monkeypatch env unset → assert returns `False` + ERROR logged (mirror `test_30_orchestration.py:133` `monkeypatch.setattr(nl, "_alert_operator", lambda m: alerts.append(m))` for capturing alert calls; and `test_30`'s `caplog`/label-assertion style for the fail-loud log).
- gato_brain `/newsletter_eval` handler: two options — (a) unit-test the formatter/select with the stub (mirror test_27), and/or (b) live-http round-trip (mirror `tests/test_gato_brain_e2e.py:25` `chat(client, user, message)` helper). D-13's live Telegram round-trip is the acceptance gate.
- `orchestration`-style seam test (`tests/test_30_orchestration.py:1-30`): imports the REAL module (conftest-preloaded), monkeypatches `_alert_operator` / lazy-imported attrs — the template for asserting the notify path calls `send_telegram` and checks its return.

**conftest note:** `tests/conftest.py` has the schemas-collision module-loader; `edition_eval.py` needs
none (stdlib + `supabase` param only). The processor (`agentpulse_processor.py`) imports schemas — a new
processor unit test likely needs the conftest preload path (see `test_30_orchestration.py:22-30`), OR
extract the pure formatter into a stub-testable function that takes `supabase` + rows as params (mirrors
`edition_eval.py`'s "supabase is the FIRST positional param, no module-global" design).

---

## No Analog Found

None. Every site has a strong in-repo analog. The only "new" file-level surface is the `/newsletter_eval`
command handler, which copies `/newsletter_preview`'s dispatch + `handle_map_command`'s gating.

---

## Metadata

**Analog search scope:** `docker/processor/`, `docker/gato_brain/`, `docker/gato/`, `docker/newsletter/`,
`supabase/migrations/`, `tests/`
**Files scanned:** 7 (processor, gato_brain, inject-gato-brain.mjs, edition_eval.py, newsletter_poller.py,
045_edition_evals.sql, test_27_edition_eval.py) + grep sweeps across `tests/`
**Pattern extraction date:** 2026-07-02
