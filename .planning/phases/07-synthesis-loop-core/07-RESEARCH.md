# Phase 7: Synthesis Loop Core - Research

**Researched:** 2026-05-31
**Domain:** Autonomous editorial synthesis loop in the AgentPulse processor (scheduled poller → trigger eval → input assembly → ONE Claude Sonnet call via llm-proxy → INSERT one `draft` block_body_versions row)
**Confidence:** HIGH (all findings verified against repo code, live config, and the live Supabase economy_map data)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** The synthesis loop lives in the PROCESSOR, a new scheduled poller alongside the Phase-5 intake classifier. Placement stays the processor regardless of which Sonnet call mechanism is chosen.
- **D-02:** Watermark = `blocks.last_synthesized_at` for BOTH the N-count and the T=30-day clock (single column). It only advances on PUBLISH (Phase 9), so the trigger MUST also apply D-03.
- **D-03:** "No pending draft" eligibility guard — a block with an existing `status='draft'` row is NOT eligible. One in-flight draft per block.
- **D-04:** Recency compares by `created_at` (`entry.created_at > blocks.last_synthesized_at`), NOT `event_date`. `event_date` is used ONLY for ordering entries in the prompt.
- **D-05:** Eligibility predicate = `(no draft for block)` AND `(count(new entries) >= N=5` OR `(now - last_synthesized_at >= T=30d AND count(new entries) >= 1))`. N=5/T=30 are GLOBAL. Source N and T from `config/agentpulse-config.json` (mirror the Phase-5 `intake_classifier.confidence_floor` pattern); default 5 / 30 days.
- **D-06:** Cold-start (NULL `last_synthesized_at`): all entries count as "new" → eligible at ≥5, or ≥1 once 30 days passed since the block's earliest entry `created_at`.
- **D-07:** Input entries = `created_at > last_synthesized_at` (NULL → all), ordered by `event_date` newest-first. Pass concrete entry content (`event_date`, `what_shifted`, `why_it_mattered`, `source_url`) — never bare cluster labels.
- **D-08:** Cold-start input (no prior body, `current_body_version_id` NULL): prompt = entries + current `maturity` (nascent) + `live_tension` (use placeholder if still seeded) + the six-part skeleton headings. No "prior body" section. Do NOT block cold-start on tension being set.
- **D-09:** High-volume cap (fail-loud, never silent). Feed all entries since the watermark ordered by `event_date`, bounded by a token budget; if the set exceeds the budget include the most-recent up to the cap and log + note the omitted count in the prompt/run log. Never silently drop. (Researcher: set the exact token budget / entry ceiling and output `max_tokens` — see Section "D-09 Resolution".)
- **D-10:** Single Sonnet call via proxy. Exactly ONE editorial LLM call per synthesis, Claude Sonnet, routed through `http://llm-proxy:8200` (NO direct SDK to `api.anthropic.com`). Both the processor `routed_llm_call` `/v1/chat/completions` path and the newsletter `/anthropic` SDK path are *described* as sanctioned proxy routes — see D-01 Resolution for the correction.
- **D-11:** `synth_identity.md` is a FILE with mtime hot-reload at `config/economy_map/synth_identity.md`, mounted into the processor, loaded mtime-cached (reuse `analyst_poller.py`). Fail-loud: missing/empty → log loudly + skip that synthesis cycle.
- **D-12:** Output = `body_md` + `proposed_maturity` from the single call. `proposed_maturity` is NOT NULL; must be one of `nascent`/`emerging`/`contested`/`consolidating`/`mature`. Parser MUST validate against the enum and fail-loud (skip write, log) on invalid/missing — never default silently. Output format (structured JSON vs tagged trailer) is Claude's discretion.
- **D-13:** Draft write — INSERT exactly one `block_body_versions` row: `block_slug`, `body_md`, `proposed_maturity`, `status='draft'` (default), `synthesized_from_through` = the synthesis run timestamp. Do NOT touch `published` row, `blocks.maturity`, or `blocks.current_body_version_id`.

### Claude's Discretion
- Output format for D-12 (structured JSON vs tagged) and the exact prompt template / skeleton-heading wording (follow newsletter prose voice + six-part block skeleton from RNDR-02).
- Schedule cadence / poll slot among the processor's `schedule` jobs (SYNT-02 defers to executor).
- Exact token budget, output `max_tokens`, and entry ceiling for D-09 (this research recommends concrete values; planner finalizes).
- Whether to use `routed_llm_call` vs a ported `/anthropic` SDK client (resolved below — neither; use raw httpx to `/anthropic/v1/messages`).
- Whether trigger eval iterates all seven blocks per cycle or batches (low volume — 7 blocks; iterate all).

### Deferred Ideas (OUT OF SCOPE)
- `/map-identity` Telegram command to edit `synth_identity.md` — Phase 10.
- Validation sentinels + `validator_report` population + Telegram flag card — Phase 8.
- `/map-approve` / `/map-reject`, atomic publish transaction, advancing `last_synthesized_at`, block-page re-render — Phase 9.
- Per-block N/T threshold tuning — v2 (TUNE-01..03). Phase 7 ships global N=5/T=30 only.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SYNT-01 | Trigger eval: eligible when ≥N=5 new entries since `last_synthesized_at` OR ≥T=30d with ≥1 new | Watermark column confirmed nullable (migration 033 :76); recency-by-`created_at` query pattern given (Sec. Trigger). Config-driven N/T mirrors `intake_classifier` block. |
| SYNT-02 | Trigger runs on a schedule | `schedule.every(...).do(scheduled_*)` registration confirmed (processor :10238-10297); `scheduled_classify_intake` thin-wrapper analog (:9834). |
| SYNT-03 | Input assembly: published body + entries since watermark (ordered by `event_date`) + `live_tension` + `maturity` — concrete entries | PostgREST read helpers + exact column names confirmed (migration 033 §4/§5/§7). Concrete-entry rule honored. |
| SYNT-04 | Single editorial LLM call, Claude Sonnet, via `llm-proxy:8200`, no direct Anthropic SDK | **D-01 Resolution**: use `httpx.post` to `/anthropic/v1/messages`. Proxy Anthropic route verified (:992-1227). |
| SYNT-05 | Prompt in `economy_map/synth_identity.md`, hot-reloaded via mtime | mtime-cache pattern confirmed (`analyst_poller.py` :82-110). Mount path resolved. |
| SYNT-06 | Output = rewritten `body_md` + `proposed_maturity` | Enum + NOT NULL constraint confirmed (migration 033 :46-52, :100). Validation/fail-loud pattern given. |
</phase_requirements>

## Summary

Phase 7 is a single new processor poller that structurally clones the Phase-5 intake poller (`classify_intake_poller`): a guard → fetch loop → per-block trigger eval → input assembly → ONE Sonnet call → ONE PostgREST INSERT, all fail-loud. Every supporting primitive already exists in the processor (the `schedule` registry, the economy_map PostgREST read/write idiom with `Accept-Profile`/`Content-Profile: economy_map`, the agent-key getter, the mtime hot-reload pattern in the analyst). The schema is locked and append-only-trigger-protected; a plain `status='draft'` INSERT does not touch any pinned-immutable column and cannot violate the trigger.

The one place CONTEXT.md is factually wrong is **D-01's premise**, and it matters because it's spine-critical. CONTEXT.md states `routed_llm_call()` "POSTs to llm-proxy `/v1/chat/completions`." It does not — `routed_llm_call` calls the OpenAI/DeepSeek **SDK clients directly** and has no Anthropic support at all (processor `agentpulse_processor.py` :506-533). Worse, the proxy's own `/v1/chat/completions` endpoint cannot host Sonnet either: it posts the request body verbatim to `{route.base_url}/chat/completions`, and for `claude-sonnet-4-20250514` that base_url is `https://api.anthropic.com`, which has no `/chat/completions` route (Anthropic uses `/v1/messages`). The ONLY working Sonnet route is the proxy's dedicated `/anthropic/v1/messages` endpoint (proxy `proxy.py` :992-1227, route registered :1275). The CONTEXT.md fallback instinct ("port the newsletter `/anthropic` client") is correct; the cleanest implementation is a raw `httpx.post` to `{LLM_PROXY_URL}/anthropic/v1/messages` (the exact transport the processor already uses for the intake classifier), which adds **no new dependency** — the `anthropic` SDK is NOT currently in the processor's requirements.

**Primary recommendation:** Make the single Sonnet call with a raw `httpx.post` to `{LLM_PROXY_URL}/anthropic/v1/messages` carrying an Anthropic Messages body (`model`, `system`, `messages`, `max_tokens`), `Authorization: Bearer {_get_agent_api_key()}`. Input budget: cap at **22 entries** (~3k input tokens) with a hard token budget of **~12,000 input tokens** for the assembled prompt; output `max_tokens` = **8000**. Build the synthesis poller as a structural clone of `classify_intake_poller`, with N/T sourced from a new `synthesis` config block (default N=5 / T=30d).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Schedule the synthesis cycle | Processor (`schedule` loop) | — | Processor owns all scheduled jobs (`schedule.every().do()`, :10238-10297). |
| Trigger eligibility eval (N/T + no-draft guard) | Processor | Database (PostgREST reads) | Counting/comparison is Python; the source of truth (`blocks`, `block_body_versions`, `timeline_entries`) is the DB. |
| Input assembly | Processor | Database | Reads three economy_map tables, formats the prompt. |
| Editorial generation | LLM Proxy (`/anthropic/v1/messages`) | Anthropic (upstream) | All model calls route through the proxy (RivalScope constraint); proxy owns auth/wallet/rate-limit. |
| Identity (voice) load | Processor (mtime cache) | Config volume (mounted file) | `synth_identity.md` is operator-controlled config, hot-reloaded by the processor. |
| Draft persistence | Database (append-only `block_body_versions`) | Processor (INSERT via PostgREST) | The draft row is the autonomy-boundary artifact; the DB trigger enforces immutability. |
| Maturity validation | Processor (parse + enum check) | Database (enum type) | Fail-loud in Python before the INSERT; the DB enum is the backstop. |

## Standard Stack

### Core (all already present — no new packages required)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` | >=0.25.0 [VERIFIED: docker/processor/requirements.txt] | Sync HTTP for proxy + PostgREST calls | Already the processor's transport for the intake classifier and economy_map helpers. |
| `schedule` | >=1.2.0 [VERIFIED: requirements.txt] | In-process cron for the synthesis poller | The processor's established scheduler (120+ jobs). |
| `supabase` | >=2.0.0 [VERIFIED: requirements.txt] | `newsletters`/`agent_api_keys` public-schema reads | Used by intake poller for editions + agent key. economy_map itself uses raw PostgREST, NOT supabase-py. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `json` (stdlib) | — | Parse Anthropic response + structured `{body_md, proposed_maturity}` output | Output parsing (D-12). |
| `pathlib.Path` (stdlib) | — | mtime check on `synth_identity.md` | Hot-reload (D-11, mirrors analyst). |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Raw `httpx.post` to `/anthropic/v1/messages` | Porting the `anthropic` SDK client (newsletter pattern) | The SDK is NOT in the processor's `requirements.txt` and the processor never imports it — adding it is a new dependency + Dockerfile rebuild surface for zero functional gain. Raw httpx mirrors the existing in-processor `classify_intake_event` transport exactly. **Recommend raw httpx.** |
| `routed_llm_call()` | (nothing — it cannot route Sonnet) | `routed_llm_call` uses the OpenAI/DeepSeek SDK clients directly and has no Anthropic branch (`:506-533`). Using it for Sonnet is impossible. |

**Installation:** None. No new packages. (If the planner instead chooses the SDK path, add `anthropic>=0.80` to `docker/processor/requirements.txt` and rebuild the processor image — not recommended.)

**Version verification:** No new packages to verify. All three core libraries are already pinned in `docker/processor/requirements.txt` [VERIFIED: file read].

## Package Legitimacy Audit

> Phase 7 installs **no external packages** (the recommended path reuses `httpx`/`schedule`/`supabase`/stdlib already present). Package Legitimacy Gate not applicable.

If the planner chooses the (not recommended) SDK path: `anthropic` is the official Anthropic Python SDK [CITED: pypi.org/project/anthropic], already used by `docker/newsletter` and `docker/research` in this repo, and listed in CLAUDE.md's stack (Anthropic SDK 0.80+) — but it is absent from the processor's requirements today.

## D-01 Resolution (spine-critical) — Sonnet routing

**CONTEXT.md premise is incorrect.** Verified facts:

1. **`routed_llm_call()` does NOT route through the proxy and cannot host Sonnet.** [VERIFIED: docker/processor/agentpulse_processor.py:506-533]
   - It resolves a provider via `get_provider(model)`, picks `deepseek_client` or `openai_client`, and calls `client.chat.completions.create(...)` on the **SDK client directly**. There is no `anthropic` branch — an unknown/anthropic provider falls through to `openai_client` and would fail.
   - The processor's clients: `openai_client = OpenAI(api_key=OPENAI_API_KEY)` with **no `base_url`** (so it would hit real `api.openai.com` with an `ap_processor_` key); `deepseek_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)` where `DEEPSEEK_BASE_URL=http://llm-proxy:8200/v1` [VERIFIED: agentpulse_processor.py:409-429; docker-compose.yml:263-264]. So in the processor, only the *DeepSeek* SDK client is actually proxy-routed; the OpenAI client is not. Neither supports Anthropic.

2. **The proxy `/v1/chat/completions` endpoint cannot host Sonnet either.** [VERIFIED: docker/llm-proxy/proxy.py:741-989]
   - `proxy_openai_compatible` builds `upstream_url = f"{route['base_url']}/chat/completions"` and POSTs the body verbatim (`:878-879, :939-942`). For `claude-sonnet-4-20250514`, `route['base_url'] == "https://api.anthropic.com"` [VERIFIED: proxy.py:72-76], so it would POST to `https://api.anthropic.com/chat/completions` — a nonexistent route. It also never translates the OpenAI body shape to the Anthropic Messages shape.

3. **The ONLY sanctioned Sonnet route is `/anthropic/v1/messages`.** [VERIFIED: proxy.py:992-1227, route registered :1275 `@app.post("/anthropic/v1/messages")`; also a `/v1/messages` back-compat alias :1280]
   - `proxy_anthropic` validates the model is an Anthropic provider, reserves/settles wallet, and proxies to `{route['base_url']}/v1/messages` with `x-api-key` + `anthropic-version` headers (`:1121-1133`). This is exactly what the newsletter uses via `anthropic.Anthropic(base_url=f"{LLM_PROXY_URL}/anthropic")` [VERIFIED: docker/newsletter/newsletter_poller.py:270-274].

4. **`max_tokens` for a full body is fine.** The proxy passes the body through unmodified; the only cap is `MAX_CHAT_BODY = 1MB` request-body size and `TIMEOUT_CHAT = 120.0s` [VERIFIED: proxy.py:101, :105]. The newsletter already sends Sonnet calls with `max_tokens=16000` and `8192` [VERIFIED: newsletter_poller.py:1200, :1397, :1420]. An 8000-token body is well within limits.

5. **No model-allowlist blocker.** The proxy gates on `agent.get("allowed_models")`, but the `agent_api_keys` table has **no `allowed_models` column** [VERIFIED: live PostgREST 42703 error], so `allowed` is empty → no per-model restriction. The processor agent key `ap_processor_bbf3520a2c38065dc95c8d16a37df978` is already wired in docker-compose env and is the same key the intake classifier uses successfully [VERIFIED: docker-compose.yml:262-266].

### RECOMMENDATION (D-01)
**Do NOT use `routed_llm_call`. Do NOT relocate the loop (it stays in the processor per D-01). Make the single Sonnet call with a raw `httpx.post` to `{LLM_PROXY_URL}/anthropic/v1/messages`** — the same transport the processor already uses for `classify_intake_event`, but pointed at the Anthropic route with an Anthropic Messages body. This requires no new dependency and no Dockerfile change.

**Concrete call snippet (planner reference — Anthropic Messages body shape):**
```python
# Mirrors classify_intake_event's transport (agentpulse_processor.py:2996-3013),
# but uses the Anthropic Messages endpoint + body. Sonnet is ONLY reachable here.
resp = httpx.post(
    f"{LLM_PROXY_URL}/anthropic/v1/messages",
    headers={
        "Authorization": f"Bearer {_get_agent_api_key()}",  # proxy accepts ap_ key here too
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    },
    json={
        "model": "claude-sonnet-4-20250514",   # source from config 'synthesis_model'
        "system": synth_identity_text,          # the hot-reloaded synth_identity.md
        "max_tokens": 8000,                      # D-09 output budget (see below)
        "temperature": 0.4,                      # match newsletter prose temp
        "messages": [{"role": "user", "content": assembled_prompt}],
    },
    timeout=120,   # match proxy TIMEOUT_CHAT
)
if resp.status_code not in (200, 201):
    raise RuntimeError(f"synthesis Sonnet call failed ({resp.status_code}): {resp.text}")
# Anthropic Messages response shape: {"content": [{"type":"text","text": "..."}], ...}
text = resp.json()["content"][0]["text"]
```
> Note: `_get_agent_api_key()` returns the `ap_processor` key (`:6467-6479`); the proxy's `_extract_api_key` accepts it on the anthropic route. The newsletter sets the Anthropic SDK `api_key` to the same `ap_` key (`newsletter_poller.py:271` comment: "Proxy uses the agent's ap_ key"), so a `Bearer`/`x-api-key` carrying the `ap_` key authenticates. **Planner: add a test that asserts the call targets `/anthropic/v1/messages` and carries the agent key (mirror `test_05a` assertions).** If the proxy's `_extract_api_key` only reads `x-api-key` on the anthropic path, also send `x-api-key: {_get_agent_api_key()}` — verify against `_extract_api_key` during planning (LOW-risk detail; both headers can be sent safely).

## D-09 Resolution — token budgets

**Grounded in live data** [VERIFIED: live economy_map.timeline_entries query, 68 rows, 2026-05-31]:
- Per-block entry counts: psychology-disposition **24**, memory-context 20, autonomy-control 8, regulation-legal 7, governance-accountability 6, identity-trust 2, payments-settlement 1.
- Per-entry size (`what_shifted` + `why_it_mattered` + `source_url`): **min 105 / median 415 / mean 409 / max 542 chars** → ≈ **median 103 / max 135 tokens** per entry (chars/4 heuristic). With JSON/markdown field labels and `event_date`, budget **~160 tokens per formatted entry**.
- Worst observed case (24 entries) ≈ 24 × 160 ≈ **3,840 tokens** of entry content — comfortably small.

The real input-size driver is the **prior published `body_md`** (a full synthesized block article, expected multi-thousand words once published). The newsletter's full-body Sonnet prose calls run `max_tokens` 8192–16000 [VERIFIED: newsletter_poller.py], so a block body is in the low-thousands of tokens.

### RECOMMENDED concrete values (planner writes these into `config/agentpulse-config.json` `synthesis` block)
| Knob | Recommended default | Rationale |
|------|---------------------|-----------|
| `max_input_entries` (entry ceiling, D-09 cap) | **22** | Above the observed max-relevant volume but bounded; if a block ever exceeds this, keep the **most-recent 22 by `event_date`** and log + note `omitted_count` in the prompt + run log (never silent). |
| `max_input_tokens` (assembled-prompt budget) | **12000** | Headroom for prior body (~6–8k) + 22 entries (~3.5k) + tension + skeleton. Estimate tokens as `len(text)//4`; if assembled prompt exceeds this, drop oldest entries first (keep newest) and record the omitted count. |
| `output_max_tokens` | **8000** | A full block body (six-part skeleton); matches the newsletter's mid-range Sonnet body budget. Comfortably under the proxy's 1MB/120s limits. |
| `synthesis_model` | `"claude-sonnet-4-20250514"` | The single Sonnet model already routed by the proxy + priced in config (`pricing` block has this key) [VERIFIED: config]. |
| `temperature` | `0.4` | Matches the newsletter prose pass. |

**Fail-loud cap behavior (D-09):** when `len(entries) > max_input_entries` OR estimated tokens `> max_input_tokens`, include the most-recent entries up to the cap, set `omitted_count = total - included`, append a line to the prompt (e.g. `[NOTE: {omitted_count} older entries omitted for length — synthesize from the {included} most recent]`) AND `logger.warning(...)`. Never drop without both signals. Preserves the single-call constraint (SYNT-04).

## Architecture Patterns

### System Architecture Diagram
```
processor schedule loop (schedule.every(...).do(scheduled_synthesize_blocks))
        │
        ▼
synthesize_blocks_poller()                         ── guard: supabase set? synthesis.enabled? identity present?
        │
        ├─► _fetch_economy_map_blocks()            ── PostgREST GET /blocks (Accept-Profile: economy_map)
        │        (slug, maturity, live_tension, last_synthesized_at, current_body_version_id)
        │
        └─ for each block ─────────────────────────────────────────────────────────────────────────┐
             │                                                                                       │
             ├─► eligible?  (D-03 no-draft guard) AND (D-05 N/T predicate, recency by created_at)    │
             │        ├─ GET /block_body_versions?block_slug=eq.<slug>&status=eq.draft&limit=1        │
             │        └─ GET /timeline_entries?block_slug=eq.<slug>&created_at=gt.<watermark>         │
             │   not eligible → skip (continue)                                                       │
             │                                                                                        │
             ├─► assemble input (D-07/D-08/D-09)                                                      │
             │        prior body (GET current published body_md, or none for cold-start)              │
             │        + entries ordered by event_date desc, capped (D-09)                             │
             │        + live_tension + maturity + six-part skeleton headings                          │
             │                                                                                        │
             ├─► load_synth_identity()  ── mtime-cached read of config/economy_map/synth_identity.md  │
             │        missing/empty → logger.error + skip cycle (fail-loud, D-11)                     │
             │                                                                                        │
             ├─► ONE Sonnet call ── httpx.post {LLM_PROXY}/anthropic/v1/messages  (D-10/SYNT-04)      │
             │        proxy → api.anthropic.com/v1/messages → wallet settle + X-Proxy-* headers       │
             │                                                                                        │
             ├─► parse {body_md, proposed_maturity}; validate maturity ∈ enum (D-12)                  │
             │        invalid/missing → logger.error + skip this block (no INSERT)                    │
             │                                                                                        │
             └─► INSERT ONE block_body_versions row (D-13)                                            │
                      POST /block_body_versions (Content-Profile: economy_map)                        │
                      {block_slug, body_md, proposed_maturity, synthesized_from_through=run_ts}       │
                      status defaults 'draft'. NEVER touch published / blocks.* (autonomy boundary)   ┘
```

### Recommended Project Structure (where new code lands)
```
docker/processor/agentpulse_processor.py
├── SYNTHESIS_SYSTEM_PROMPT / skeleton constants   # near INTAKE_CLASSIFIER_* (~:2940)
├── load_synth_identity()                          # mtime-cached, mirrors analyst_poller:82-110
├── economy_map_* read helpers (blocks, entries, draft-existence, current body)
│       # mirror _fetch_economy_map_block_slugs (:3043) + economy_map_emitted_event_keys (:629)
├── economy_map_insert_block_body_version(row)     # mirror economy_map_insert_timeline_entry (:573)
├── synthesize_block(block, ...) -> dict           # eligibility + assemble + call + parse
├── synthesize_blocks_poller() -> dict             # orchestrator, mirrors classify_intake_poller (:3234)
└── scheduled_synthesize_blocks()                  # thin wrapper, mirrors scheduled_classify_intake (:9834)
    # registered in main():  schedule.every(<cadence>).do(scheduled_synthesize_blocks)  near :10263
```
> Convention: the processor is a single ~10k-line module with no sub-modules; new functions are top-level, snake_case, near their analogs. Do NOT add a new file unless the planner explicitly prefers it.

### Pattern 1: Proxy-routed LLM call from the processor (raw httpx)
**What:** POST to the proxy with the agent Bearer key; raise on non-2xx.
**When to use:** the single Sonnet synthesis call (D-10).
**Example:** see the D-01 Resolution snippet. Source transport pattern: `classify_intake_event` [agentpulse_processor.py:2996-3013].

### Pattern 2: economy_map PostgREST read with Accept-Profile
**What:** direct `httpx.get` to `/rest/v1/<table>` with `apikey`/`Authorization: {SUPABASE_KEY}` and `Accept-Profile: economy_map`; raise on non-2xx.
**When to use:** all economy_map reads (blocks, entries, draft existence, current body).
**Example (draft-existence guard, D-03):**
```python
# Source pattern: _fetch_economy_map_block_slugs (:3043), economy_map_edition_already_emitted (:600)
resp = httpx.get(
    f"{SUPABASE_URL}/rest/v1/block_body_versions",
    params={"block_slug": f"eq.{slug}", "status": "eq.draft", "select": "id", "limit": 1},
    headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
             "Accept-Profile": "economy_map"},
    timeout=10,
)
if resp.status_code != 200:
    raise RuntimeError(f"draft-existence check failed ({resp.status_code}): {resp.text}")
has_draft = bool(resp.json())   # non-empty list → block NOT eligible (D-03)
```

### Pattern 3: economy_map PostgREST INSERT with Content-Profile (D-13)
**What:** `httpx.post` to `/rest/v1/block_body_versions` with `Content-Profile: economy_map`, `Prefer: return=representation`; raise on non-2xx.
**When to use:** the single draft write.
**Example:** clone `economy_map_insert_timeline_entry` [:573-597], changing the table to `block_body_versions` and the payload to `{block_slug, body_md, proposed_maturity, synthesized_from_through}`. `status` omitted → DB default `'draft'`.
> Note on the existing helper comment (`:570-572`): the current insert helper is "scoped to ONLY timeline_entries … no generic schema-agnostic writer, to keep the service_role write surface tight." Honor that by adding a **second purpose-scoped** `economy_map_insert_block_body_version()` rather than a generic writer.

### Pattern 4: mtime hot-reload of the identity file (D-11, SYNT-05)
**What:** module-global `_synth_identity_cache` + `_synth_identity_mtime`; re-read only when `stat().st_mtime` changes.
**Example (reusable snippet, adapted from analyst_poller.py:82-110):**
```python
SYNTH_IDENTITY_PATH = Path("/home/openclaw/.openclaw/config/economy_map/synth_identity.md")
_synth_identity_cache: str | None = None
_synth_identity_mtime: float = 0.0

def load_synth_identity() -> str | None:
    """Load synth_identity.md, mtime-cached. Returns None if missing/empty (fail-loud caller skips)."""
    global _synth_identity_cache, _synth_identity_mtime
    p = SYNTH_IDENTITY_PATH
    current_mtime = p.stat().st_mtime if p.exists() else 0.0
    if _synth_identity_cache is not None and current_mtime == _synth_identity_mtime:
        return _synth_identity_cache
    if not p.exists():
        logger.error(f"[SYNTH] synth_identity.md missing at {p} — skipping synthesis cycle (D-11)")
        return None
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        logger.error(f"[SYNTH] synth_identity.md is empty — skipping synthesis cycle (D-11)")
        return None
    _synth_identity_cache, _synth_identity_mtime = text, current_mtime
    return text
```
> **Mount:** the processor already mounts `../config:/home/openclaw/.openclaw/config:ro` [VERIFIED: docker-compose.yml:268-269], so a file committed to `config/economy_map/synth_identity.md` is visible at `/home/openclaw/.openclaw/config/economy_map/synth_identity.md` with **no docker-compose change**. mtime propagates through the `:ro` bind mount on host edits, so hot-reload works without a restart. (The `:ro` is fine — Phase 7 only reads. Phase 10's `/map-identity` writer is a separate, deferred concern; do not change the mount now.)

### Pattern 5: scheduled poller orchestration (SYNT-02)
**What:** thin `scheduled_*()` try/except wrapper registered with `schedule.every(...).do(...)` in `main()`.
**Example:** `scheduled_classify_intake` [:9834] wraps `classify_intake_poller`; registered `schedule.every(30).minutes.do(scheduled_classify_intake)` [:10263]. Synthesis cadence is Claude's discretion — recommend a daily or 6-hourly slot (low volume, 7 blocks); avoid the same minute as other heavy jobs.

### Anti-Patterns to Avoid
- **Using `routed_llm_call` or `/v1/chat/completions` for Sonnet** — neither can reach Anthropic (see D-01). Use `/anthropic/v1/messages`.
- **supabase-py for economy_map** — `.schema()`/`.in_()` silently fail against the isolated schema (CLAUDE.md + PROJECT.md constraint). Use raw PostgREST with the profile headers.
- **Silently dropping entries over the cap** — D-09 requires log + in-prompt note.
- **Defaulting `proposed_maturity` on parse failure** — D-12 requires fail-loud skip.
- **Touching `published` / `blocks.maturity` / `blocks.current_body_version_id`** — autonomy boundary; Phase 9 owns those. The append-only trigger blocks UPDATEs to pinned columns anyway, but the INSERT-only draft write avoids the issue entirely.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Anthropic auth / wallet / rate-limit | A direct `api.anthropic.com` client | The proxy `/anthropic/v1/messages` route | RivalScope anti-pattern; proxy owns budget governance + records `wallet_transactions`. |
| Append-only immutability | App-layer "don't update" checks | The DB BEFORE-UPDATE/DELETE trigger (migration 033 §8) | Structural enforcement binds even service_role; app checks don't (MEMORY: structural-over-application). |
| Atomic publish / supersede / maturity sync | A multi-step writer in Phase 7 | `economy_map.publish_block_version` RPC (Phase 9) | Phase 7 writes draft only; publish is a locked Phase-9 SECURITY DEFINER RPC. |
| Config caching | A bespoke loader | `get_full_config()` (:542) | Already caches `agentpulse-config.json`; read the `synthesis` block via `get_full_config().get('synthesis', {})` (mirror intake `:3245`). |
| Agent API key lookup | Re-querying `agent_api_keys` | `_get_agent_api_key()` (:6467) | Cached getter already used by the intake classifier. |

**Key insight:** Every primitive Phase 7 needs already exists in the processor as a Phase-5 artifact. The work is composition, not construction.

## Runtime State Inventory

> Greenfield-feature phase (new poller, new draft rows). Not a rename/refactor. Section included for completeness:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | New `block_body_versions` rows with `status='draft'` will be created by this loop. No existing data renamed. | None (additive). |
| Live service config | New `synthesis` block in `config/agentpulse-config.json`; new `config/economy_map/synth_identity.md` file. | Add config + ship default identity file (committed to repo, auto-mounted). |
| OS-registered state | None — the poller registers via the in-process `schedule` library, not OS cron. | None. |
| Secrets/env vars | None new. Reuses `AGENT_API_KEY`/`ap_processor` key + `SUPABASE_KEY` already in processor env. | None. |
| Build artifacts | None if raw-httpx path is used (no new dependency, no image rebuild beyond normal code deploy). | Standard `docker compose up -d --build processor`. |

**Nothing found requiring data migration.** Verified: Phase 7 is additive — one new scheduled job + one new draft-row writer.

## Common Pitfalls

### Pitfall 1: Treating `routed_llm_call`/`/v1/chat/completions` as the Sonnet path
**What goes wrong:** the call 404s/errors against `api.anthropic.com/chat/completions`, or routes to OpenAI.
**Why it happens:** CONTEXT.md D-01/D-10 mis-describe `routed_llm_call` as proxy-routed and imply `/v1/chat/completions` is a sanctioned Sonnet route.
**How to avoid:** use `/anthropic/v1/messages` with the Anthropic body shape (D-01 Resolution).
**Warning signs:** a 400 "Unknown or non-Anthropic model" from the proxy, or a response that isn't `{"content":[{"text":...}]}`.

### Pitfall 2: Watermark recency by the wrong column
**What goes wrong:** a backdated `event_date` entry is wrongly counted as not-new (or vice versa).
**Why it happens:** `event_date` is editorial and can be backdated; `last_synthesized_at` is wall-clock.
**How to avoid:** count/filter "new" by `created_at > last_synthesized_at` (D-04); order the prompt by `event_date` desc (D-07).
**Warning signs:** trigger fires too often/never on blocks that received backdated entries.

### Pitfall 3: Duplicate drafts piling up
**What goes wrong:** every cycle creates another draft for the same unabsorbed entries because `last_synthesized_at` only advances on PUBLISH.
**Why it happens:** missing the D-03 no-draft guard.
**How to avoid:** the draft-existence query (Pattern 2) MUST gate eligibility before assembly/call. This also dovetails with Phase-9 reject (reject → no draft → re-eligible).
**Warning signs:** multiple `status='draft'` rows per `block_slug` (the partial index `idx_block_body_versions_status` makes this query cheap).

### Pitfall 4: PostgREST timestamp comparison format
**What goes wrong:** `created_at=gt.<watermark>` filters silently mis-compare if the timestamp string isn't a valid ISO-8601 PostgREST value.
**Why it happens:** hand-formatting timestamps.
**How to avoid:** pass `last_synthesized_at` straight through as the ISO string PostgREST returns it; for NULL watermark, omit the filter (cold-start = all entries, D-06). Read it back from the same `/blocks` row, don't reconstruct it.
**Warning signs:** zero or all entries returned regardless of dates.

### Pitfall 5: `synthesized_from_through` semantics
**What goes wrong:** writing the newest entry's `created_at` instead of the run timestamp.
**Why it happens:** ambiguity in what "through" means.
**How to avoid:** D-13 says `synthesized_from_through` = the **synthesis run timestamp** (`now()`), which Phase 9 copies into `last_synthesized_at` on approve. Use the run's wall-clock `datetime.now(timezone.utc).isoformat()`.
**Warning signs:** Phase-9 approve advances the watermark to an editorial/backdated time, re-feeding already-synthesized entries.

## Code Examples

### Parse + validate output (D-12)
```python
MATURITY_ENUM = {"nascent", "emerging", "contested", "consolidating", "mature"}

def parse_synthesis_output(text: str) -> dict:
    """Expect structured JSON {body_md, proposed_maturity}. Fail-loud on invalid maturity."""
    parsed = json.loads(_clean_json_response(text))   # reuse _clean_json_response (:~2960)
    body_md = (parsed.get("body_md") or "").strip()
    maturity = (parsed.get("proposed_maturity") or "").strip().lower()
    if not body_md:
        raise ValueError("synthesis returned empty body_md")
    if maturity not in MATURITY_ENUM:
        raise ValueError(f"invalid proposed_maturity {maturity!r} — must be one of {sorted(MATURITY_ENUM)}")
    return {"body_md": body_md, "proposed_maturity": maturity}
# Caller: wrap in try/except → logger.error + skip THIS block's INSERT (never default).
```
> **Recommendation (D-12 format):** prefer **structured JSON** `{"body_md": "...", "proposed_maturity": "emerging"}` requested explicitly in the system prompt + reuse the processor's existing `_clean_json_response` fence-stripper (the intake classifier already relies on it). This is more robust to parse than a tagged trailer and matches the intake pattern the test harness already exercises.

### Eligibility predicate (D-05/D-06)
```python
from datetime import datetime, timezone, timedelta
def is_eligible(block, new_entries, has_draft, N=5, T_days=30) -> bool:
    if has_draft:                      # D-03
        return False
    n = len(new_entries)
    ws = block.get("last_synthesized_at")
    if ws is None:                     # D-06 cold-start
        if n >= N:
            return True
        # ≥1 and 30d since earliest entry created_at
        if n >= 1:
            earliest = min(e["created_at"] for e in new_entries)
            age = datetime.now(timezone.utc) - _parse_iso(earliest)
            return age >= timedelta(days=T_days)
        return False
    if n >= N:                         # D-05
        return True
    if n >= 1:
        age = datetime.now(timezone.utc) - _parse_iso(ws)
        return age >= timedelta(days=T_days)
    return False
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Direct provider SDK calls | All LLM via `llm-proxy:8200` | Pre-Phase-5 (RivalScope lesson) | Phase 7 must route Sonnet through `/anthropic/v1/messages`. |
| `routed_llm_call` as "the proxy path" | It is NOT proxy-routed for OpenAI; only DeepSeek is, via `DEEPSEEK_BASE_URL`. Intake uses explicit `httpx.post` to the proxy. | Phase 5 | Phase 7 follows the explicit-httpx-to-proxy precedent, not `routed_llm_call`. |

**Deprecated/outdated:**
- The CONTEXT.md claim that `routed_llm_call()` "POSTs to llm-proxy `/v1/chat/completions`" — incorrect; corrected in D-01 Resolution.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Proxy `_extract_api_key` accepts the `ap_processor` Bearer token on the `/anthropic` route (newsletter uses the same key as the Anthropic SDK `api_key`). | D-01 Resolution | If the anthropic path only reads `x-api-key`, the call 401s. Mitigation: send both `Authorization: Bearer` and `x-api-key`; verify against `_extract_api_key` during planning. LOW. |
| A2 | A published `body_md` is in the low-thousands of tokens (drives the 12k input / 8k output budget). | D-09 Resolution | No `published` rows exist yet (cold-start state today), so body size is inferred from the newsletter's Sonnet body budgets, not measured. If real bodies run larger, raise `max_input_tokens`/`output_max_tokens`. MEDIUM. |
| A3 | chars/4 token heuristic for entry sizing. | D-09 Resolution | Underestimates for code/URL-heavy text; the 22-entry + 12k-token dual cap leaves ample margin. LOW. |
| A4 | `synth_identity.md` placed under the already-mounted `config/` tree needs no docker-compose change. | Pattern 4 mount note | Verified the mount exists (`../config:...:ro`); risk only if planner places the file outside `config/`. LOW. |

## Open Questions (RESOLVED)

1. **Does the proxy's `_extract_api_key` read `Authorization: Bearer` on the `/anthropic` path, or only `x-api-key`?**
   - What we know: the newsletter SDK sets `api_key=ap_...` against `base_url=.../anthropic` and works; the Anthropic SDK sends `x-api-key`.
   - What's unclear: whether a raw `Authorization: Bearer ap_...` is also accepted there.
   - RESOLVED: send BOTH headers in the synthesis call (harmless) and add a test asserting a 2xx. Confirmed during planning by reading `proxy.py:728` `_extract_api_key` — it reads `Authorization: Bearer` first, falling back to `x-api-key`. Plan 07-01 Task 2 sends both.

2. **Synthesis cadence (SYNT-02, Claude's discretion).**
   - What we know: low volume (7 blocks), per-block no-draft guard makes frequent polling cheap.
   - RESOLVED: daily or every 6h, avoiding the Friday newsletter-generation slot. Plan 07-02 Task 2 owns the concrete `schedule` registration per SYNT-02's executor-discretion clause.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| llm-proxy `/anthropic/v1/messages` | Sonnet call (SYNT-04) | ✓ | route registered proxy.py:1275 | — |
| `claude-sonnet-4-20250514` route | SYNT-04 | ✓ | MODEL_ROUTES + pricing present | — |
| `ANTHROPIC_AGENT_KEY` (proxy upstream key) | proxy → Anthropic | Assumed set in proxy env (newsletter Sonnet path is in production per MEMORY) | — | If absent, proxy 502 "Anthropic key not configured" — fail-loud surfaces it. |
| economy_map schema + tables | reads/writes | ✓ | migration 033 applied (live query returned rows) | — |
| `config/` volume mount on processor | synth_identity.md load | ✓ | docker-compose.yml:268 | — |
| `httpx`/`schedule`/`supabase` | all | ✓ | requirements.txt pinned | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `ANTHROPIC_AGENT_KEY` presence not directly verified this session, but the newsletter Sonnet path is live in production (MEMORY: Block Pipeline SHIPPED), so it is set.

## Validation Architecture

> `.planning/config.json` not inspected for `nyquist_validation`; treating as enabled. Tests use a standalone-runnable + pytest-compatible pattern (no framework config file).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (plain `def test_*` + module-level `_run_all()` for standalone) [VERIFIED: tests/test_05a_intake_classifier.py] |
| Config file | none — `tests/conftest.py` only (module-loading workarounds) |
| Quick run command | `python3 tests/test_07_synthesis.py` (standalone, no DB) |
| Full suite command | `cd /root/bitcoin_bot && python3 -m pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SYNT-04 | Sonnet call targets `/anthropic/v1/messages`, carries agent key, model `claude-sonnet-4`, raises on non-2xx | unit (httpx.post stub) | `python3 tests/test_07_synthesis.py` | ❌ Wave 0 |
| SYNT-01/05 | Eligibility predicate (N/T, cold-start, no-draft guard) | unit | same | ❌ Wave 0 |
| SYNT-03/D-09 | Input assembly orders by event_date desc, caps at ceiling, logs+notes omissions | unit | same | ❌ Wave 0 |
| SYNT-05/D-11 | mtime reload returns None on missing/empty (caller skips) | unit (tmp file) | same | ❌ Wave 0 |
| SYNT-06/D-12 | Output parse validates maturity enum, raises on invalid/missing | unit | same | ❌ Wave 0 |
| D-13 | Draft INSERT hits `/block_body_versions` with Content-Profile, status omitted (defaults draft), no published touch | unit (httpx.post stub) | same | ❌ Wave 0 |

**Test harness pattern to mirror** [VERIFIED: tests/test_05a_intake_classifier.py]: stub `schedule`/`tweepy`/`resend`/`markdown` modules before `import agentpulse_processor`; set `OPENCLAW_DATA_DIR`; prime `proc._model_config_cache` from the repo config; monkeypatch `proc.httpx.post`/`proc.httpx.get` + `proc._get_agent_api_key` with a `_FakeResponse`; assert on the captured URL/headers/body. The synthesis test should add a `_FakeResponse` whose `json()` returns the Anthropic `{"content":[{"text": "..."}]}` shape.

### Sampling Rate
- **Per task commit:** `python3 tests/test_07_synthesis.py`
- **Per wave merge:** `python3 -m pytest tests/test_07_synthesis.py tests/test_05a_intake_classifier.py -q`
- **Phase gate:** `python3 -c "import ast; ast.parse(open('docker/processor/agentpulse_processor.py').read())"` then full `pytest tests/` green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_07_synthesis.py` — covers SYNT-01..06 + D-03/D-09/D-12/D-13 (mirror `test_05a` harness)
- [ ] `config/economy_map/synth_identity.md` — working default voice (D-11), committed so it auto-mounts
- [ ] `synthesis` block in `config/agentpulse-config.json` — `enabled`, `N`, `T_days`, `synthesis_model`, `max_input_entries`, `max_input_tokens`, `output_max_tokens`, `temperature`

## Project Constraints (from CLAUDE.md)
- LLM calls route through `http://llm-proxy:8200` — NO direct Anthropic SDK to `api.anthropic.com`. (Phase 7: `/anthropic/v1/messages`.)
- economy_map accessed via direct PostgREST with `Accept-Profile`/`Content-Profile: economy_map` headers — never supabase-py `.in_()`/`.schema()`.
- Python 3.11+/3.12; snake_case functions; top-level functions (processor has zero classes); broad `except Exception:` + `logger.error(..., exc_info=True)`; module-level prompt string constants; `json.loads()` with regex fence-fallback (`_clean_json_response`).
- Processor uses `schedule` (not cron); config-driven thresholds in `config/agentpulse-config.json`.
- Syntax-check before rebuild: `python3 -c "import ast; ast.parse(open('docker/processor/agentpulse_processor.py').read())"`.
- Fail-loud governance (MEMORY): halt loudly on missing inputs, never silently default to no-op. Applies to missing identity (D-11), invalid maturity (D-12), over-cap entries (D-09).
- Structural over application enforcement (MEMORY): rely on the append-only DB trigger, not app checks, for immutability.

## Security Domain

> `security_enforcement` not found in config; including a scoped review.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Proxy authenticates the `ap_processor` agent key; reuse `_get_agent_api_key()`. |
| V3 Session Management | no | No sessions (server-to-server). |
| V4 Access Control | yes | RLS + append-only triggers (migration 033 §8/§11); service_role write surface kept tight via purpose-scoped insert helper. |
| V5 Input Validation | yes | Validate `proposed_maturity` against the enum (D-12); the DB enum + NOT NULL is the backstop. |
| V6 Cryptography | no | None hand-rolled. |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection from timeline entry text into the synthesis prompt | Tampering | Entries are operator/classifier-sourced (not anonymous user input); output is `draft` only and human-gated (Phase 9). Low blast radius. Treat entry text as data, not instructions, in the prompt template. |
| LLM returns junk/oversized `proposed_maturity` | Tampering | Enum validation + fail-loud skip (D-12); mirrors the intake `tag_confidence` clamp defense (WR-01, newsletter_poller:3149). |
| Silent entry drop over cap | Repudiation/Info loss | D-09 log + in-prompt note. |
| Over-broad service_role write | Elevation | Purpose-scoped `economy_map_insert_block_body_version` only; no generic writer (mirrors :570-572 rationale). |
| Budget runaway (Sonnet is the priciest model) | DoS/cost | Proxy wallet reserve/settle + governance + per-block no-draft guard caps calls to ≤7/cycle. |

## Sources

### Primary (HIGH confidence)
- `docker/processor/agentpulse_processor.py` — `routed_llm_call` :506-533; `get_model`/`get_provider` :462-470; `get_full_config` :542; economy_map insert helper :573-597, reads :600-660; `_fetch_economy_map_block_slugs` :3043; `classify_intake_event` :2974-3013; `classify_intake_for_edition`/`classify_intake_poller` :3073-3288; `_get_agent_api_key` :6467-6479; `scheduled_classify_intake` :9834; schedule registration :10238-10297.
- `docker/llm-proxy/proxy.py` — MODEL_ROUTES + sonnet route :60-93; `MAX_CHAT_BODY`/`TIMEOUT_CHAT` :101-105; `proxy_openai_compatible` :741-989; `proxy_anthropic` :992-1227; route registrations :1265-1283.
- `docker/newsletter/newsletter_poller.py` — Anthropic client via proxy :270-274; Sonnet max_tokens :1200/:1397/:1420.
- `docker/newsletter/block_pipeline.py` — `_llm_call` Anthropic/OpenAI dual path :26-51; phase prose max_tokens.
- `docker/analyst/analyst_poller.py` — mtime identity cache :82-110.
- `supabase/migrations/033_economy_map_schema.sql` — full schema, enum, append-only triggers, RPCs.
- `docker/docker-compose.yml` — processor service env + mounts :251-282.
- `config/agentpulse-config.json` — models/pricing/intake_classifier blocks.
- `tests/test_05a_intake_classifier.py` — proxy-call test harness pattern.
- Live Supabase economy_map.timeline_entries query (2026-05-31, 68 rows) — entry counts + size stats grounding D-09.

### Secondary (MEDIUM confidence)
- `.planning/phases/07-synthesis-loop-core/07-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `CLAUDE.md`, MEMORY.md.

### Tertiary (LOW confidence)
- None. All load-bearing claims verified against repo code or live data.

## Metadata

**Confidence breakdown:**
- D-01 Sonnet routing: HIGH — verified the SDK clients, both proxy endpoints, and route table directly.
- D-09 budgets: HIGH on entry sizing (live data); MEDIUM on body-size assumption (no published rows exist yet).
- Architecture/patterns: HIGH — all primitives read from current code with file:line refs.
- Pitfalls: HIGH — derived from the locked decisions + verified schema constraints.

**Research date:** 2026-05-31
**Valid until:** 2026-06-30 (stable repo; re-verify proxy `_extract_api_key` header handling and re-measure body sizes once the first blocks are published).
