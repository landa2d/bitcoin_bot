---
phase: 05-intake-classifier-unsorted-handling
reviewed: 2026-05-28T19:20:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - config/agentpulse-config.json
  - docker/processor/agentpulse_processor.py
  - tests/test_05a_intake_classifier.py
  - tests/test_05_intake.py
findings:
  critical: 1
  warning: 5
  info: 3
  total: 9
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-05-28T19:20:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the Phase 5 intake-classifier + unsorted-handling code: the new
`classify_intake_event()` (proxy-routed classifier), `economy_map_insert_timeline_entry()` /
`economy_map_edition_already_emitted()` PostgREST helpers, the per-edition route logic in
`classify_intake_for_edition()`, the `classify_intake_poller()` orchestrator, the
`scheduled_classify_intake()` wrapper + 30-min `schedule` registration, and the
`intake_classifier` config block. Cross-referenced against migration `033_economy_map_schema.sql`
(timeline_entries column types + append-only trigger) and the newsletter snapshot producers.

**Positive findings (held up under adversarial tracing):**
- Proxy routing is correct — `classify_intake_event` POSTs to `{LLM_PROXY_URL}/v1/chat/completions`
  with the processor agent key, not a direct SDK call (CLAUDE.md constraint satisfied; the tests
  prove it and the live wallet-transaction evidence test backs criterion 2).
- economy_map writes/reads use direct PostgREST with `Content-Profile` / `Accept-Profile:
  economy_map` headers and the service key — no `.schema()`/`.in_()` (constraint satisfied).
- Prompt-injection surface is reasonably mitigated: untrusted event text is JSON-serialized as data
  inside a system+user prompt that explicitly de-instructs it (`INTAKE_CLASSIFIER_SYSTEM_MSG`), and
  the returned `block_slug` is allow-list-validated (`slug in allowed_slugs`) before being used as a
  write target, so an injected/hallucinated slug routes to `unsorted` rather than being trusted
  (T-05-05 handled).
- PostgREST filter/body values are passed via httpx `params=`/`json=` (URL-encoded / JSON-bodied),
  not string-interpolated — no PostgREST/SQL injection via `source_edition_id` etc.
- The below-floor and classifier-error paths route to `unsorted` and the tests confirm
  flagged-not-dropped (recorded confidence) and NULL-confidence-on-error behavior.

**Key concern:** the "never drop an event" invariant has a real hole on the *transient insert
failure* path (CR-01) that the accepted D-08 tradeoff does not cover, plus an out-of-range
`tag_confidence` value can trigger a schema-level INSERT rejection that silently drops the event
(WR-01).

## Critical Issues

### CR-01: Partial-insert failure permanently drops events — idempotency skips the edition on the next run

**File:** `docker/processor/agentpulse_processor.py:3063-3067, 3134-3142`
**Issue:**
`classify_intake_for_edition` does an edition-granular idempotency skip:

```python
if economy_map_edition_already_emitted(edition_id):
    logger.info(f"[INTAKE] edition {edition_id} already emitted — skipping (D-08)")
    counts['already_emitted'] = True
    return counts
```

`economy_map_edition_already_emitted` returns `True` if **any** `timeline_entries` row carries the
edition id. Per-event inserts each have their own try/except that only logs on failure:

```python
try:
    economy_map_insert_timeline_entry(entry)
    counts['emitted'] += 1
except Exception as e:
    logger.error(f"[INTAKE] insert failed for edition {edition_id} (slug={target_slug}): {e}")
```

Consider an edition with 5 tier-1 events: events 1-2 INSERT successfully, then a transient PostgREST
error (timeout / 5xx / overflow per WR-01) fails events 3-5. The function returns; events 3-5 were
never written. On the next 30-min poll, `economy_map_edition_already_emitted(edition_id)` sees the 2
rows that *did* land, returns `True`, and the **whole edition is skipped forever**. Events 3-5 are
silently and permanently dropped — a direct violation of the phase's "never drop an event" spine
(D-05) and ROADMAP criterion. The accepted D-08 tradeoff in 05-CONTEXT.md is narrowly about an
edition *regenerated with different events*, not about transient insert failures mid-edition; this
gap is not covered.

The same window exists if the processor crashes / is redeployed mid-edition after the first insert.

**Fix:** Make the "drop an event" boundary fail loud and make idempotency event-aware. Minimum
viable fix: if any insert in the edition fails, do NOT let the edition be treated as fully emitted —
either raise after the loop so the run is recorded as failed and the edition is retried, or make the
idempotency check per-event (skip only events whose `source_edition_id`+`source_url`/`what_shifted`
already exist) so a re-run completes the missing rows. Example fail-loud guard:

```python
insert_failures = 0
for event in tier1_events:
    ...
    try:
        economy_map_insert_timeline_entry(entry)
        counts['emitted'] += 1
    except Exception as e:
        insert_failures += 1
        logger.error(f"[INTAKE] insert failed for edition {edition_id} (slug={target_slug}): {e}")

# Do not let a partially-emitted edition be marked done — it would be skipped forever (D-08)
# and the failed events would be dropped. Surface it so the next poll retries.
if insert_failures:
    raise RuntimeError(
        f"edition {edition_id}: {insert_failures}/{len(tier1_events)} timeline inserts failed; "
        "edition is partially emitted and will be skipped on re-run — failing loud to force retry"
    )
```

A cleaner long-term fix is per-event idempotency (existence check keyed on
`source_edition_id` + `source_url`) so partial editions complete on retry instead of being skipped.

## Warnings

### WR-01: `tag_confidence` is never clamped/validated — an out-of-range LLM value overflows `NUMERIC(3,2)` and drops the event

**File:** `docker/processor/agentpulse_processor.py:3098-3110, 3132` (and migration `033_economy_map_schema.sql:156`)
**Issue:** The classifier output confidence is consumed with `conf = float(conf)` and stored
verbatim, with no range clamp:

```python
conf = parsed.get('tag_confidence')
conf = float(conf) if conf is not None else None
tag_confidence = conf
if conf is not None and conf >= floor and slug in allowed_slugs:
    target_slug = slug
```

The schema column is `tag_confidence NUMERIC(3,2)` (migration 033 line 156). The comment claims
"0.00..1.00" but there is **no CHECK constraint** — and `NUMERIC(3,2)` only holds values with
magnitude < 10 (max 9.99). The LLM output is untrusted; a model that returns a percentage-style
value (`"tag_confidence": 91` instead of `0.91`) or any value `>= 10` produces a numeric-overflow on
INSERT. The insert then raises, is caught by the per-event try/except (line 3137), logged, and the
event is **not** emitted — i.e. silently dropped (compounding CR-01: the edition may then be marked
emitted and the event lost forever). A value like `5.0` would also incorrectly pass `conf >= floor`
and persist a named slug with a nonsensical confidence.

**Fix:** Clamp/validate confidence before using it for routing and before persisting:

```python
raw_conf = parsed.get('tag_confidence')
conf = None
if raw_conf is not None:
    try:
        conf = float(raw_conf)
    except (TypeError, ValueError):
        conf = None
    if conf is not None:
        # NUMERIC(3,2) + semantic range: a valid confidence is in [0,1]; clamp the rest.
        conf = max(0.0, min(1.0, conf))
tag_confidence = conf
```

This keeps the event emittable (routes to `unsorted` when the model misbehaves) instead of letting a
bad value reach the column and drop the row.

### WR-02: Classifier silently uses `gpt-4o` (20x cost) when the model config fails to load — comment asserts the opposite

**File:** `docker/processor/agentpulse_processor.py:2966` (with `get_model` at 462-465 and `get_model_config` at 440-459)
**Issue:** The classifier sends `"model": get_model("extraction")` with an inline comment
`# == deepseek-chat`. But `get_model_config()` reads a **hardcoded** path
`/home/openclaw/.openclaw/config/agentpulse-config.json`; on any read failure it caches `{}` and
`get_model("extraction")` falls through to `config.get('default', OPENAI_MODEL)` →
`OPENAI_MODEL` (`gpt-4o`). Per `config/agentpulse-config.json` pricing, gpt-4o is $2.50/$10.00 vs
deepseek-chat $0.27/$1.10 — ~10-20x more for a bulk classification task that runs every 30 minutes
over up to 10 editions. This contradicts the "DeepSeek V3 for bulk classification (cost-efficient)"
constraint and the inline comment, and would not be caught by the offline tests (they prime
`_model_config_cache` from the repo config).

**Fix:** Either resolve the model explicitly for this cost-sensitive path, or assert the resolved
model is a deepseek model and log loudly if not. Minimum:

```python
model = get_model("extraction")
if model != "deepseek-chat":
    logger.warning(f"[INTAKE] classifier model resolved to {model}, expected deepseek-chat "
                   "(model config likely failed to load) — bulk classification cost will be higher")
```

Better: pin the classifier to a config-read that points at the deployed config (or a dedicated
`classification` model key) rather than relying on the `extraction` → `default` → `OPENAI_MODEL`
fallback chain.

### WR-03: A missing/empty processor agent key silently routes ALL events to `unsorted` instead of failing loud

**File:** `docker/processor/agentpulse_processor.py:2964` (with `_get_agent_api_key` at 6373-6385)
**Issue:** `classify_intake_event` builds `headers={"Authorization": f"Bearer {_get_agent_api_key()}"}`.
`_get_agent_api_key()` returns `""` on lookup failure (swallowed exception). With an empty bearer
token the proxy returns 401 → `RuntimeError` → caught by the edition handler → every event routes to
`unsorted` with NULL confidence. The pipeline keeps running and "emits" rows, so the failure is
invisible: an entire run can dump 100% of events into `unsorted` with no alert. This is exactly the
fail-loud-governance posture the project flagged ("halt loudly on missing inputs, never silently
default to no-op — the wallet bug all over again", MEMORY.md). It is not a dropped-event (events are
recorded), so it is a WARNING rather than a BLOCKER, but it degrades the classifier to a no-op
silently.

**Fix:** Guard the key at the top of `classify_intake_poller()` (before the loop) and halt the run
loudly if absent, rather than letting every per-event classify fail:

```python
if not _get_agent_api_key():
    logger.error("[INTAKE] processor agent API key unavailable — aborting run (would route all "
                 "events to 'unsorted'); not a silent no-op")
    log_pipeline_end(run_id, 'failed', {'error': 'missing agent api key'})
    return {'error': 'missing agent api key'}
```

### WR-04: `_clean_json_response` is fragile for the classifier's untrusted output

**File:** `docker/processor/agentpulse_processor.py:2931-2937` (used by `classify_intake_event` at 2978-2979)
**Issue:** The fence stripper only handles a leading ` ``` `:

```python
if text.startswith('```'):
    text = text.split('```')[1]
    if text.startswith('json'):
        text = text[4:]
return text.strip()
```

If the model emits leading prose then a fenced block (e.g. `Here is the JSON:\n```json\n{...}\n````),
`startswith('```')` is False and the raw prose is handed to `json.loads`, which raises. The classify
path then routes the event to `unsorted` (acceptable — not dropped), but it needlessly forfeits
correctly-classified events whenever the model is chatty, inflating the `unsorted` bucket. The
docstring in test_05a even claims "regex fallback to extract JSON from markdown fences" (the
documented pattern), but this helper has no regex fallback.

**Fix:** Add the regex JSON-extraction fallback the codebase documents (match the first `{...}`
object) before `json.loads`, e.g.:

```python
cleaned = _clean_json_response(content)
try:
    return json.loads(cleaned)
except json.JSONDecodeError:
    import re
    m = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    raise
```

### WR-05: Block-pipeline-as-primary will produce editions with no `premium_source_posts`, silently emitting zero timeline entries

**File:** `docker/processor/agentpulse_processor.py:3075-3078` (consumer) vs `docker/newsletter/newsletter_poller.py:1960-1973`
**Issue:** `classify_intake_for_edition` reads tier-1 events from
`data_snapshot['premium_source_posts']` where `tier == 1`. Today this survives because the saved
snapshot is `{**input_data, **result_data_snapshot}` (newsletter_poller.py:1475) and `input_data`
carries `premium_source_posts`. But when the block pipeline is the *primary* generation path it
builds `result['data_snapshot']` as a fresh dict containing only
`pipeline_version`/`voice_score`/`block_summary`/`block_prepass` (lines 1967-1973) — no
`premium_source_posts`. The current merge masks this only because `input_data` happens to be the
base; per project memory the block pipeline is the documented production direction
(`block_pipeline.enabled` cutover), and a pure `block_v1` snapshot would yield `tier1_events == []`.
The poller would then log "0 emitted ... from 0 tier-1 events" and the timeline would silently stop
populating for every published edition — a quiet failure of the intake spine.

**Fix:** Don't depend on snapshot shape coincidence. Either (a) assert/log when a `published`
edition has an empty `premium_source_posts` so the silent-zero case is visible, or (b) derive tier-1
events from the block snapshot's structures when `pipeline_version == 'block_v1'`. At minimum, add
an observability guard:

```python
if not tier1_events:
    logger.warning(f"[INTAKE] edition {edition_id}: 0 tier-1 events in data_snapshot "
                   f"(pipeline_version={snapshot.get('pipeline_version')}) — nothing to emit")
```

## Info

### IN-01: `str(edition.get('id'))` yields the literal `'None'` when id is missing

**File:** `docker/processor/agentpulse_processor.py:3060`
**Issue:** `edition_id = str(edition.get('id'))` — if a row ever lacks `id`, this becomes the string
`'None'`, and the idempotency check / `source_edition_id` would key on literal `'None'`, conflating
unrelated id-less editions. DB rows always have `id`, so this is defensive only.
**Fix:** Guard `if not edition.get('id'): logger.warning(...); return counts` (or skip) before
deriving `edition_id`.

### IN-02: Error-path events are double-counted in the run totals

**File:** `docker/processor/agentpulse_processor.py:3122-3123, 3191-3193`
**Issue:** On the classifier-error path, both `counts['errors']` and `counts['unsorted']` are
incremented for the same event, and the poller sums both into `totals`. The log line then reports
the same event under "unsorted" and "classify errors". This is intentional (an errored event *is*
unsorted) but the totals are not disjoint, which can mislead when reading run summaries.
**Fix:** Document the overlap in the log line, or track `unsorted` as `below_floor + errors` so the
buckets are clearly nested rather than appearing additive.

### IN-03: `intake_classifier.enabled` defaults to `True` when config load fails

**File:** `docker/processor/agentpulse_processor.py:3163-3164`
**Issue:** `cfg = get_full_config().get('intake_classifier', {})` then `if not cfg.get('enabled', True)`.
If `get_full_config()` returns `{}` (hardcoded path missing), the feature defaults to enabled with
floor 0.6. That is a reasonable default, but it means a missing config silently runs the pipeline
(and, per WR-02, possibly on gpt-4o). Acceptable, but worth noting the default-on posture for a path
that has cost implications.
**Fix:** None required; if a fail-safe-off posture is preferred, default `enabled` to a value tied to
a successfully-loaded config.

---

_Reviewed: 2026-05-28T19:20:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
