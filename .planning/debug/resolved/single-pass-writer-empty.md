---
slug: single-pass-writer-empty
status: resolved
trigger: |
  The single-pass writer is broken in prod: claude-sonnet-4-6 returns a 200 with 4,703 output tokens but the agent parses content[0].text as empty → every generation fails. No newsletter has generated successfully since the 06-19 model swap, so the real Friday 2026-06-26 edition will fail. This is pre-existing model-swap fallout, not a Phase 26 gap. Tracked as a P1 todo + a STATE blocker + memory.
created: 2026-06-24T14:53:12Z
updated: 2026-06-24T14:53:12Z
diagnose_only: false
---

# Debug Session: single-pass-writer-empty

## Symptoms

- **Expected behavior:** The single-pass newsletter writer produces non-empty newsletter prose and saves a draft edition successfully.
- **Actual behavior:** `claude-sonnet-4-6` returns HTTP 200 with ~4,703 output tokens, but the agent parses `content[0].text` as an empty string → every single-pass generation fails (empty content surfaces as a failed/empty generation).
- **Error messages:** No hard exception reported — silent empty parse of `content[0].text`. Generation fails downstream because the writer returns empty content.
- **Timeline:** Started after the **2026-06-19** model swap to `claude-sonnet-4-6`. No newsletter has generated successfully via the single-pass path since then. Pre-existing model-swap fallout — NOT a Phase 26 gap.
- **Reproduction:** Every single-pass writer invocation. Single-pass writer is in `docker/newsletter/newsletter_poller.py` (~line 1878 per memory). Anthropic calls route through the LLM proxy `/anthropic/v1/messages` (per `reference_processor_anthropic_routing.md`).

## Impact / Stakes

- The **real Friday 2026-06-26 edition** will fail if unfixed (today is 2026-06-24).
- Block-pipeline path is the current working stopgap (`block_pipeline.enabled=true`); single-pass is the broken primary.
- Tracked as a P1 todo + a STATE blocker + memory note (`reference_newsletter_generation_state_2026_06.md`).

## Starting Hypotheses (operator-supplied / from memory)

- `content[0]` may not be the text block. With newer Claude models, when extended thinking is engaged, `content[0]` can be a non-text block (e.g. `type: "thinking"`) and `text` lives in a later block — so `content[0].text` reads empty while output tokens are non-zero.
- The proxy `/anthropic/v1/messages` response shape, large-response truncation, or `stop_reason: "max_tokens"` interaction with `TIMEOUT_ANTHROPIC=240s` may also be in play.
- Single-pass uses a larger/single response than the block path (which works) — "empty on large responses" suggests a size/structure-dependent parse path.

## Current Focus

- hypothesis: REVISED. The error "Expecting value: line 1 column 1 (char 0)" does NOT prove `content[0].text` is empty — it fires for ANY text whose first non-whitespace char is not valid JSON (e.g. a prose preamble like "Here is the newsletter:"). The large writer response likely contains real text in `content[0]` that is NOT pure JSON (preamble / un-fenced prose / multiple text blocks), while the small `editorial_prepass` reliably emits clean JSON. The "content[0] is a non-text block" theory is REFUTED by the error type (a non-text first block would raise AttributeError, not a JSON ValueError).
- test: Reproduce a large claude-sonnet-4-6 response via the proxy and log `[(b.type, len(getattr(b,'text','') or '')) for b in content]`, `stop_reason`, `usage`, and `repr(content[0].text[:300])`. Cross-check against the DB-stored failure for the real failed task.
- expecting: content[0] is a text block; either text begins with non-JSON prose, or there are multiple text blocks. NOT a thinking/non-text first block.
- next_action: AWAITING HUMAN VERIFY. Root cause confirmed (brittle JSON extraction; refuted empty/multi-block/non-text-block via 7 real-response inspections). Fix applied + deployed (scoped rebuild) + verified (22 unit + 69 regression green; live TEST A/B/C pass on rebuilt container). On operator "confirmed fixed": archive_session (mv to resolved/, commit code+test, commit docs, append knowledge-base, resolve the P1 todo). If the operator still sees a failure, capture the exact response head from the new fail-loud error_message (now logged) and resume investigation.
- reasoning_checkpoint:
- tdd_checkpoint:

## Evidence

- timestamp: 2026-06-24T15:05:00Z
  checked: both single-pass writer and the working block-pipeline parse paths
  found: BOTH use `response.content[0].text` (newsletter_poller.py:774,1049,1249,1454 and block_pipeline.py:41). The block path is NOT structurally more robust at content extraction — the operator's "block path iterates content blocks" premise is FALSE. The real difference is call SIZE: block path uses many small `max_tokens=3000` per-section calls; single-pass uses one `max_tokens=16000` call with ~83,859 input tokens.
  implication: The fix is not "copy the block path's extraction" — both are equally naive. The divergence is response-size/shape dependent.

- timestamp: 2026-06-24T15:06:00Z
  checked: proxy `proxy_anthropic` (docker/llm-proxy/proxy.py:996-1223)
  found: The proxy returns `upstream_resp.content` verbatim (line 1215-1218) — it does NOT reshape, truncate, or strip content blocks for non-streaming responses. `model="claude-sonnet-4-6"` is sent verbatim to `https://api.anthropic.com/v1/messages` (no model-name translation; MODEL_ROUTES proxy.py:72). No `thinking` param is injected by the proxy or the writer.
  implication: content[0] structure == exactly what Anthropic returns. A 200 with output tokens means the model id resolves upstream. Extended-thinking reorder is unlikely (not requested), and would anyway raise AttributeError not a JSON error.

- timestamp: 2026-06-24T15:07:00Z
  checked: error semantics of the captured failure ("Failed to parse model response as JSON: Expecting value: line 1 column 1 (char 0)") vs the todo/STATE inference that `content[0].text` is "empty"
  found: `json.loads()` raises this exact message for an empty string AND for any string starting with a non-JSON character (e.g. "Here is..."). So "content[0].text is empty" is an UNVERIFIED inference. STATE.md:89 and the P1 todo both say "do NOT fix blind; needs reproduction with response-structure logging."
  implication: Must reproduce/inspect the actual content array before fixing. The proposed "iterate text blocks" fix may be incomplete (won't help if content[0] holds prose-wrapped JSON).

## Eliminated

- hypothesis: The text lives in a non-text first content block (extended thinking / changed block ordering) so `content[0].text` reads empty.
  evidence: A non-text block (ThinkingBlock) has no `.text` attribute — `content[0].text` would raise AttributeError, not produce the observed `json.loads` ValueError at char 0. The writer never requests thinking and the proxy never injects it.
  timestamp: 2026-06-24T15:07:00Z

- hypothesis: Anthropic splits LARGE claude-sonnet-4-6 responses across multiple content/text blocks, so content[0] is empty/partial while later blocks hold the text (the P1-todo's "join text blocks" fix theory).
  evidence: REPRODUCED in-container (repro_blocks.py): a large response (5,388 output tokens, 29,229 chars) returned `num_content_blocks: 1`, `block_types_and_textlen: [('text', 29229)]`, `stop_reason: end_turn`. content[0].text starts with `{` and `json.loads` succeeds. The "join all text blocks" extraction is byte-identical to `content[0].text` here. Multi-block splitting does NOT happen.
  timestamp: 2026-06-24T15:18:00Z

- timestamp: 2026-06-24T15:08:00Z
  checked: faithful replay of a real ~83K-token newsletter input (the 2026-06-19 completed task) through generate_newsletter() with the CURRENT claude-sonnet-4-6 model, capturing the raw Anthropic response (repro_real.py)
  found: The call SUCCEEDED. Single content block ([('text', 22109)]), stop_reason=end_turn, usage_in=85591/usage_out=4890. content[0].text STARTS WITH '```json\n{...' (markdown-fenced JSON). The fence-stripping regex (newsletter_poller.py:1263-1265) stripped it and json.loads succeeded. So content[0].text reliably holds the FULL text; the model just wrapped it in ```json fences this time.
  implication: The bug is NOT structural and NOT "empty content". It is a BRITTLE JSON-extraction path. The model's output framing is stochastic: sometimes raw JSON, sometimes ```json-fenced (handled), sometimes (the failing 06-24 case) prefixed with a prose preamble. The extraction only strips fences when `text.startswith("```")`; a leading preamble (text starting with neither '{' nor '```') skips fence-stripping and makes json.loads fail at "char 0" — the exact observed error.

- timestamp: 2026-06-24T15:08:30Z
  checked: error-signature correlation
  found: Observed live error = "Expecting value: line 1 column 1 (char 0)" (a LEADING parse failure). content[0].text is reliably non-empty (proven: 22109 chars). Therefore the failing response began with non-JSON text (prose preamble or pure markdown), NOT empty and NOT a non-text block.
  implication: Root cause = the writer trusts the model to return bare/cleanly-fenced JSON. It needs robust extraction (find the JSON regardless of surrounding prose/fences) AND fail-loud-with-content when no JSON is recoverable.

- timestamp: 2026-06-24T20:35:00Z
  checked: GENUINE PROD-PATH end-to-end verification (operator-requested). Processor prepare_newsletter_data(edition_override=103) built CURRENT-week data + inserted a real write_newsletter task (dc05c1d4-46d2-43b5-8bd4-08029d84af30); the RUNNING newsletter container's poll loop claimed and drafted it with the deployed fix.
  found: PASS. Task dc05c1d4 -> status=completed (20:35:01, no error_message). Single-pass PRIMARY draft saved: newsletters id f2b9537e-e47a-403f-bc83-efba019e6f2f, edition 103, status=draft, pipeline=single-pass, content_markdown=14,255 chars ("After the Permission Layer, the Information Layer..."). Block_v1 A/B copy saved held (155a2102). Writer logged "Newsletter generated:" on BOTH the initial call and the quality-feedback retry — parse_llm_json succeeded twice. NO "Failed to parse model response as JSON" anywhere in the writer path. Nothing published (draft only). Model: claude-sonnet-4-6.
  implication: The fix resolves the live bug end-to-end through the real production path with current data. The Friday 2026-06-26 single-pass edition will generate.

- timestamp: 2026-06-24T20:35:30Z
  checked: a fail-loud line during the run — "[qualitative_review] No parseable JSON object in model response (len=3809)" -> "[QUAL REVIEW] Failed (non-blocking)"
  found: qualitative_review (secondary call, max_tokens=1024). With 16 verbose issues the response was TRUNCATED (incomplete JSON) -> genuinely unparseable -> new fail-loud raised AND caught non-blocking (returns [], generation continued + completed). The OLD code also failed to parse this same truncated response and returned [] non-blocking — NOT a regression; the new code just LOGS the content. Pre-existing condition at a DIFFERENT site than the writer bug.
  implication: Correct fail-loud behavior; zero impact on the draft. Optional follow-up (out of scope): bump qualitative_review/editorial_prepass max_tokens so verbose reviews aren't truncated.

- timestamp: 2026-06-24T15:23:00Z
  checked: ran the writer 6 MORE times on the 06-19 input (repro_loop.py) to catch the natural failure shape
  found: 6/6 SUCCEEDED. Every response began with '```json\n{' (out_tokens 4644-4989, all single text blocks). The fence regex handled them all. The failure did NOT reproduce on the 06-19 input.
  implication: The failure is DATA-DEPENDENT and STOCHASTIC. The live 06-24 failure used a DIFFERENT input (built fresh by the processor's prepare_newsletter_data from current week's data + the Option C narrative_context merge). That run produced a framing the brittle extractor couldn't handle. The exact 06-24 framing is not reproducible from stored data, but the MECHANISM is proven across 7 inspected responses: content[0].text always holds the full text; the model's surrounding framing (bare / ```json-fenced / preamble) varies. The current extractor only handles bare-or-leading-fence; any other framing → char-0 JSON error.

## Reasoning Checkpoint (pre-fix)

reasoning_checkpoint:
  hypothesis: "The single-pass writer fails because its JSON extraction is brittle: it does `text = content[0].text.strip()`, strips ```fences ONLY when `text.startswith('```')`, then `json.loads(text)`. claude-sonnet-4-6's framing of the large writer output is stochastic/data-dependent — sometimes bare JSON, usually ```json-fenced (handled), occasionally prefixed with non-JSON (a prose preamble or a fence form the regex misses). When the framing isn't bare-JSON-or-leading-```, json.loads fails at char 0. This was misdiagnosed as 'empty content[0].text'."
  confirming_evidence:
    - "Live error is 'Expecting value: line 1 column 1 (char 0)' — a LEADING (position-0) parse failure, raised as json.JSONDecodeError at newsletter_poller.py:2631 (NOT AttributeError, so content[0] IS a text block holding a string)."
    - "Direct inspection of 7 real large responses: ALWAYS a single text block ([('text', N)]), stop_reason=end_turn, content[0].text fully populated (22K+ chars / ~5K out tokens). 'Empty content' and 'multi-block split' are refuted by observation."
    - "The fence-strip only fires on text.startswith('```'); a leading preamble (text starting with neither '{' nor '```') skips stripping → json.loads on prose → char-0 error."
    - "editorial_prepass (same model, tiny focused JSON task) never fails; the giant 192K-char-user / 72K-char-system writer intermittently does — consistent with stochastic framing on a hard task, not a structural API issue."
  falsification_test: "Feed the CURRENT extraction (strip + startswith-fence + json.loads) a response whose text is a prose-preamble + JSON (or uppercase/offset fence). If it parses fine, the hypothesis is wrong. (Prediction: it raises char-0, matching the live error; the robust extractor recovers the JSON.)"
  fix_rationale: "Replace the brittle extraction with a shared robust helper: (1) join all text blocks (defensive), (2) try raw json.loads, (3) recover from a ```json/``` fenced block anywhere (case-insensitive, DOTALL), (4) recover the first balanced {...} object (string/escape-aware), (5) FAIL LOUD — raise json.JSONDecodeError with a logged content snippet — when no JSON is recoverable, never silently emitting empty. This addresses the root cause (framing variability) at every JSON parse site, and upgrades the silent/misdiagnosed failure into a diagnosable fail-loud one (operator governance rule)."
  blind_spots: "Could not reproduce the EXACT 06-24 framing (its input is gone). If the model ever emits PURE markdown prose with NO JSON object at all, robust extraction correctly fails loud but the edition still won't generate — that residual risk is mitigated, not eliminated, by extraction alone (would need prompt-hardening/prefill). The strong JSON-only instruction + 7/7 observed JSON outputs make pure-markdown unlikely. Verification will run the real writer path post-fix and a deterministic preamble test."

## Resolution

- root_cause: |
    The single-pass newsletter writer (generate_newsletter, newsletter_poller.py:1249/1263-1267)
    extracts the model's JSON with a brittle two-step: `text = response.content[0].text.strip()`,
    then strips markdown fences ONLY when `text.startswith("```")`, then `json.loads(text)`.
    claude-sonnet-4-6's framing of the LARGE writer response is stochastic and data-dependent:
    usually ```json-fenced (handled), but on some inputs it prefixes the JSON with non-JSON text
    (a prose preamble, or a fence form the regex misses). When that happens, fence-stripping is
    skipped and json.loads() fails at "char 0" — surfacing (and previously misdiagnosed) as
    "empty content". It is NOT empty, NOT a non-text/thinking block, and NOT multi-block splitting
    (all refuted by inspecting 7 real responses: always one text block, fully populated). The same
    brittle pattern exists at 3 other sites (:774 qualitative_review, :1042 editorial_prepass —
    both small/non-blocking so rarely hit; :1454 strategic_editor parses markdown not JSON).
- fix: |
    Added shared robust-extraction helpers to newsletter_poller.py (before qualitative_review):
      - response_text(response): joins ALL text blocks (defensive vs multi-block; ignores non-text
        blocks safely — never AttributeErrors on a thinking block).
      - _first_balanced_object(text): returns the first balanced {...}, string/escape-aware.
      - parse_llm_json(text, *, context): tries raw -> ```json/``` fenced block (case-insensitive,
        DOTALL) -> first balanced {...}; FAILS LOUD (raises json.JSONDecodeError + logs head/tail
        snippet) when no JSON object parses. Never returns empty/None.
    Replaced the brittle `content[0].text.strip()` + startswith-fence + json.loads at all 3 JSON
    sites: qualitative_review, editorial_prepass, and the WRITER generate_newsletter (both the
    claude and routed branches now feed parse_llm_json). strategic_editor (markdown not JSON) now
    uses response_text(...).strip() for multi-block safety; its markdown fence-strip is unchanged.
    NOT changed: prompts, model, proxy, call params. Minimal, targeted at the extraction root cause.
- verification: |
    Deterministic (tests/test_27_llm_json_extract.py, 22/22 pass): the OLD extraction provably
    raises char-0 JSONDecodeError on preamble/uppercase-fence/trailing-prose framings (the real
    failure mode); the NEW parse_llm_json recovers JSON across all framings and FAILS LOUD on
    pure-prose/empty. Regression: test_19_smartquote (36) + test_26_continuity_loader (11) green
    (69 total). (test_newsletter_quality / test_3c can't collect on this host — they import the
    processor which needs tweepy; unrelated env limit, not a regression.)
    LIVE end-to-end against the REBUILT/deployed newsletter container (verify_fix.py):
      - TEST A real ~83K-token input through generate_newsletter -> PASS (title generated).
      - TEST B same real JSON prefixed with a prose preamble (the exact failing framing that raised
        char-0 before) -> PASS, recovered end-to-end through generate_newsletter.
      - TEST C pure-prose response -> raises JSONDecodeError (fail-loud, no silent empty edition).
    Scoped rebuild `docker compose up -d --build newsletter` on the main tree (= prod); newsletter
    Up healthy, poller started clean (model=claude-sonnet-4-6). Live config block_pipeline.enabled
    =false / ab_comparison=true -> single-pass IS the primary published path, so the fix directly
    protects the Friday 2026-06-26 edition.
    GENUINE PROD-PATH (operator-requested final verify): processor prepare_newsletter_data(
    edition_override=103) created a real write_newsletter task (dc05c1d4) with CURRENT data; the
    RUNNING newsletter poller claimed + drafted it. Task -> completed (no error). Single-pass PRIMARY
    draft saved: newsletters f2b9537e-e47a-403f-bc83-efba019e6f2f, edition 103, status=draft,
    pipeline=single-pass, 14,255-char body. Writer parsed via parse_llm_json on BOTH the initial call
    and the quality retry; NO writer JSON-parse failure. Nothing published. The only fail-loud line
    was qualitative_review (secondary, non-blocking, pre-existing max_tokens=1024 truncation — not a
    regression, not the writer). PASS.
- files_changed:
    - docker/newsletter/newsletter_poller.py (robust extraction helpers + 4 site updates)
    - tests/test_27_llm_json_extract.py (new deterministic regression suite, 22 tests)
