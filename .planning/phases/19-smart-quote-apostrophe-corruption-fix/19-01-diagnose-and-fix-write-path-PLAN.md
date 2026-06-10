---
phase: 19-smart-quote-apostrophe-corruption-fix
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/phases/19-smart-quote-apostrophe-corruption-fix/19-DIAGNOSIS.md
  - docker/newsletter/newsletter_poller.py
  - docker/newsletter/block_pipeline.py
  - tests/test_19_smartquote.py
autonomous: true
requirements: [QUOTE-01, QUOTE-02]

must_haves:
  truths:
    - "The root cause (storage vs render) is written down from raw stored-byte inspection of a known-corrupt edition (30), not assumed (QUOTE-01, Success Criterion #2)"
    - "The newsletter write path is fixed so newly generated editions store apostrophes correctly and the corruption stops recurring, not just hidden at render (QUOTE-01, Success Criterion #3)"
    - "A regression test feeds 'it's' and 'the agent's wallet' through the FIXED write-path function and asserts the output contains an apostrophe (U+2019 or U+0027) and zero stray straight double-quote (U+0022) standing in for an apostrophe (QUOTE-02, Success Criterion #4)"
    - "Any new normalization/encoding code halts loudly on unexpected input rather than silently passing corruption through (project fail-loud constraint)"
  artifacts:
    - path: ".planning/phases/19-smart-quote-apostrophe-corruption-fix/19-DIAGNOSIS.md"
      provides: "Documented root-cause finding: raw codepoints around an apostrophe in edition 30's stored content_markdown, the conclusion (storage vs render), and the chosen fix site"
      min_lines: 20
    - path: "docker/newsletter/newsletter_poller.py"
      provides: "Fixed write path so the corruption cannot recur (if diagnostic locates the cause here)"
      contains: "content_markdown"
    - path: "tests/test_19_smartquote.py"
      provides: "QUOTE-02 regression test importing the real fixed write-path function"
      contains: "def test_"
  key_links:
    - from: "tests/test_19_smartquote.py"
      to: "the fixed write-path function in newsletter_poller.py (or block_pipeline.py)"
      via: "import newsletter_poller as nl (conftest preloads it) — calls the REAL function, not a reimplementation"
      pattern: "import newsletter_poller"
    - from: "19-DIAGNOSIS.md"
      to: "the chosen fix site"
      via: "named function + file + line range identified by raw-byte inspection"
      pattern: "content_markdown"
---

<objective>
Diagnose where the apostrophe→straight-double-quote corruption actually lives (storage write path vs render), document the finding, fix the write path so it cannot recur, and lock it with a regression test.

The corruption signature: an apostrophe (`'` U+2019 or `'` U+0027) appearing in stored/rendered edition bodies as a stray straight double-quote `"` (U+0022). ROADMAP examples: `Cash App's` → `Cash App"s`, `It's` → `It"s`, `world's`, `agent's`.

Purpose: This is the highest-visibility live-site bug. Success Criterion #2 requires the root cause be WRITTEN DOWN from raw stored-byte inspection, not assumed. The renderer (`marked.parse` in `docker/web/site/app.js` line ~321) runs with no typographer/smartypants, so a render-layer transform is UNLIKELY — but the diagnostic must PROVE this against the actual stored bytes before any fix is chosen. The fix follows from the finding.

Output: `19-DIAGNOSIS.md` (root-cause artifact), a fixed write path, and `tests/test_19_smartquote.py` (QUOTE-02 regression).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md

# Write path (the function that stores edition bodies)
@docker/newsletter/newsletter_poller.py
# Block-pipeline writer (alternate write path)
@docker/newsletter/block_pipeline.py
# Test infrastructure — conftest preloads newsletter_poller under sys.modules so tests `import newsletter_poller as nl`
@tests/conftest.py
@tests/test_3c_newsletters.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Diagnose root cause from raw stored bytes (storage vs render)</name>
  <files>.planning/phases/19-smart-quote-apostrophe-corruption-fix/19-DIAGNOSIS.md</files>
  <read_first>
    - .planning/ROADMAP.md (Phase 19 section — the 4 Success Criteria, especially #2; the "diagnose stored bytes first" Note)
    - docker/web/site/app.js (lines ~270–330 — confirm `marked.parse(content)` is called with NO typographer/smartypants option; this is the render-layer hypothesis to refute or confirm)
    - docker/newsletter/newsletter_poller.py (lines ~798–844: `_auto_fix_stat_repetition` / `_auto_fix_empty_sections` which mutate `result['content_markdown']`; lines ~1213–1243: the main writer's `json.loads(text)` parse + code-fence strip; line ~1467–1482: `save_newsletter` building `row` and inserting into the `newsletters` table)
    - docker/newsletter/block_pipeline.py (lines ~535, ~585, ~681 — the block-pipeline writer's `json.loads` + `content_markdown`/`content_markdown_impact` assembly)
    - config/.env (for SUPABASE_URL + SUPABASE_SERVICE_KEY — load via dotenv as the existing tests do)
  </read_first>
  <action>
    Query the RAW stored body of the known-corrupt exemplar edition 30 directly from the Supabase `newsletters` table. Select `edition_number`, `status`, `content_markdown`, `content_markdown_impact`, `content_telegram` WHERE `edition_number = 30`. Use the supabase-py client exactly as tests/test_3c_newsletters.py and tests/test_newsletter_quality.py do (create_client with SUPABASE_URL + SUPABASE_SERVICE_KEY/SUPABASE_KEY from config/.env). Do NOT use a render path — read the stored string directly.

    For each known corrupt token from the ROADMAP examples (`Cash App's`, `It's`, `world's`, `agent's`), locate every occurrence in the stored `content_markdown` and `content_markdown_impact` and print the exact Unicode codepoints of the character standing where the apostrophe should be (e.g. `ord(ch)` → expect 8217 for U+2019, 39 for U+0027, or 34 for U+0022 if already corrupt). This determines whether the corruption is ALREADY in storage (write-path cause) or whether storage is clean and only render mangles it (render-layer cause).

    Write the finding to `.planning/phases/19-smart-quote-apostrophe-corruption-fix/19-DIAGNOSIS.md`. The diagnosis MUST state: (a) the codepoints found around apostrophes in stored bytes; (b) the conclusion — storage corruption (write path) or render-only; (c) IF storage is corrupt, trace BACK through the write path to identify which step introduced the U+0022 — candidate sites to inspect in order: the LLM `json.loads(text)` parse at newsletter_poller.py ~line 1231 and block_pipeline.py ~line 535 (does the model emit a literal `"` mid-word, or does a code-fence-strip regex at ~1227–1229 damage quotes?), the `_auto_fix_*` regex mutations at ~798–844, and any encode/decode/ensure_ascii handling; (d) the EXACT function + file + line range chosen as the fix site, with a one-line justification.

    Do NOT pre-decide the answer — the conclusion is whatever the bytes show. Do NOT mutate any stored data in this task (read-only).
  </action>
  <verify>
    <automated>test -f .planning/phases/19-smart-quote-apostrophe-corruption-fix/19-DIAGNOSIS.md && grep -Eq 'U\+(2019|0027|0022)|8217|ord\(|codepoint|storage|render' .planning/phases/19-smart-quote-apostrophe-corruption-fix/19-DIAGNOSIS.md && echo PASS</automated>
  </verify>
  <acceptance_criteria>
    - `.planning/phases/19-smart-quote-apostrophe-corruption-fix/19-DIAGNOSIS.md` exists and is ≥20 lines.
    - It records the actual codepoints found around apostrophes in edition 30's stored `content_markdown` (e.g. a line naming U+0022 / 34, or U+2019 / 8217, or U+0027 / 39).
    - It states a clear conclusion: corruption is in STORAGE (write path) or only at RENDER.
    - If storage-corrupt, it names the exact fix site: a function name + file path + line range (one of: newsletter_poller.py write/parse path, block_pipeline.py writer, or `_auto_fix_*` mutators).
    - The conclusion is derived from the bytes, not asserted a priori (the document shows the raw-byte evidence).
    - No stored data was mutated by this task.
  </acceptance_criteria>
  <done>Root cause documented in 19-DIAGNOSIS.md from raw stored-byte evidence of edition 30; storage-vs-render conclusion stated; the exact fix site named.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Fix the write path so the corruption cannot recur</name>
  <files>docker/newsletter/newsletter_poller.py, docker/newsletter/block_pipeline.py</files>
  <read_first>
    - .planning/phases/19-smart-quote-apostrophe-corruption-fix/19-DIAGNOSIS.md (the fix site named in Task 1 — fix THERE, not a guessed location)
    - docker/newsletter/newsletter_poller.py (the named fix site; plus `save_newsletter` ~1444–1482 to confirm the corrected string is what reaches the `newsletters` INSERT into `content_markdown` / `content_markdown_impact`)
    - docker/newsletter/block_pipeline.py (if the diagnostic named the block-pipeline writer as the/an additional site — content_markdown assembly at ~585/681)
    - MEMORY fail-loud constraint: normalization/encoding code must halt loudly on unexpected input, never silently default to a no-op ("the wallet bug all over again")
  </read_first>
  <behavior>
    - Test: a body string containing `It's`, `Cash App's`, `world's`, `the agent's wallet` passes through the fixed write-path function and the output preserves a real apostrophe (U+2019 or U+0027) at each apostrophe position.
    - Test: the output contains ZERO instances of a straight double-quote (U+0022) standing in for an apostrophe (i.e. `"` immediately flanked by word characters like `App"s`, `It"s`).
    - Edge case (do NOT damage genuine quotes): a body containing a legitimate quotation — e.g. `He said "ship it" today` — retains its real double-quotes unchanged. The fix must repair apostrophe corruption WITHOUT collapsing every `"` into `'`.
    - Fail-loud: if the fix introduces a normalization step and it receives input it cannot classify (e.g. a `"` that is ambiguous), it raises/logs loudly rather than silently passing the string through. (If the diagnostic shows the cause is upstream — e.g. a bad regex or encode step — the "fix" may instead be correcting that step so no normalization is needed; in that case fail-loud applies to the corrected step.)
  </behavior>
  <action>
    Apply the fix at the EXACT site named in 19-DIAGNOSIS.md. The fix targets the WRITE PATH that stores `content_markdown` / `content_markdown_impact` on the `newsletters` table via `save_newsletter` in docker/newsletter/newsletter_poller.py (and the block-pipeline writer in docker/newsletter/block_pipeline.py if that path is also implicated). The corruption mechanism is whatever Task 1 proved — e.g. a code-fence-strip regex at ~1227–1229 that mangles quotes, a `json.loads` consuming a malformed model emission, an `_auto_fix_*` regex at ~798–844 that rewrites a `"` mid-word, or an encode/decode/ensure_ascii mismatch.

    Constraints on the fix:
    - It MUST preserve genuine double-quotes (real `"` quotation marks). Do NOT do a blanket `"` → `'` replacement — that destroys legitimate quotes (this is a HIGH-severity correctness threat, see threat_model T-19-03). Target ONLY the corruption signature (apostrophe positions: `"` flanked by word characters, or whatever specific mechanism the diagnostic identified).
    - It MUST be fail-loud per project memory: any new normalization branch raises/logs on unexpected/ambiguous input rather than silently returning the unmodified (still-corrupt) string.
    - Keep the change scoped to the write path. Do NOT touch the renderer (docker/web/site/app.js) unless the diagnostic PROVED the cause is render-layer (it almost certainly is not — `marked.parse` has no typographer).

    Do NOT inline the implementation here — name the function being modified and the behavior; write the actual code at the fix site. Do not introduce new pip dependencies (no package installs in this phase).
  </action>
  <verify>
    <automated>python3 -c "import ast; ast.parse(open('docker/newsletter/newsletter_poller.py').read()); ast.parse(open('docker/newsletter/block_pipeline.py').read()); print('SYNTAX OK')"</automated>
  </verify>
  <acceptance_criteria>
    - The fix is applied at the exact function/line named in 19-DIAGNOSIS.md (the write path), not a guessed location.
    - `python3 -c "import ast; ast.parse(...)"` on both newsletter_poller.py and block_pipeline.py exits 0 (no syntax errors).
    - The fix does NOT contain a blanket `"`→`'` replacement; genuine double-quotes survive (verified by Task 3's edge-case test).
    - Any new normalization branch is fail-loud (raises or logs an error) on unexpected input — no silent pass-through of a still-corrupt string.
    - docker/web/site/app.js is unchanged (unless 19-DIAGNOSIS.md proved a render-layer cause).
  </acceptance_criteria>
  <done>The write-path function named in the diagnostic is corrected so a body with `It's`/`agent's` is stored with real apostrophes; genuine `"` quotes are preserved; the normalization step (if any) fails loud; both files parse.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Regression test through the real fixed function (QUOTE-02)</name>
  <files>tests/test_19_smartquote.py</files>
  <read_first>
    - tests/conftest.py (the `_preload_poller` mechanism — newsletter_poller is preloaded into sys.modules so `import newsletter_poller as nl` returns the REAL module; block_pipeline is NOT preloaded — if the fix lives there, add it to sys.path like test_3c_newsletters.py does or preload it)
    - tests/test_3c_newsletters.py (lines ~28–45 — the `sys.path.insert` + `import newsletter_poller as nl` pattern to copy)
    - docker/newsletter/newsletter_poller.py (the fixed function name from Task 2 — the test must call the REAL function, not reimplement the transform)
    - .planning/phases/19-smart-quote-apostrophe-corruption-fix/19-DIAGNOSIS.md (confirms which function is the canonical fix site to import)
  </read_first>
  <behavior>
    - Test feeds `it's` and `the agent's wallet` (the ROADMAP-mandated QUOTE-02 inputs) through the FIXED write-path function imported from newsletter_poller (or block_pipeline if that is the fix site) and asserts: output contains an apostrophe (U+2019 chr(8217) OR U+0027 chr(39)), AND output contains zero stray `"` (U+0022) standing in for an apostrophe (no `'"'` flanked by word chars).
    - Test feeds the ROADMAP examples (`Cash App's`, `It's`, `world's`, `agent's`) and asserts each round-trips with a real apostrophe.
    - Edge-case test: a body with a legitimate quotation `He said "ship it"` round-trips with its real double-quotes intact (asserts the fix did not collapse genuine `"`).
    - The test imports the REAL function (via the conftest-preloaded `newsletter_poller`), NOT a copy of the regex/transform.
  </behavior>
  <action>
    Create tests/test_19_smartquote.py. Import the fixed function from the real module: `import newsletter_poller as nl` (conftest preloads it) — or, if 19-DIAGNOSIS.md named block_pipeline.py as the fix site, import that module the way test_3c_newsletters.py wires sys.path. The test MUST exercise the real fixed function, not a reimplementation of its transform (a copy could pass while production regresses).

    Assertions per the QUOTE-02 spec: feed `it's` and `the agent's wallet` through the fixed path; assert the result contains a real apostrophe (chr(8217) or chr(39)) and contains zero occurrences of a U+0022 (`"`, chr(34)) standing where an apostrophe belongs (assert no regex match of word-char + `"` + word-char). Add the four ROADMAP example tokens as parametrized cases. Add the genuine-double-quote edge case asserting `He said "ship it"` keeps its real `"`.

    Use pytest `def test_*` functions consistent with the existing tests/ style. The test must be runnable headless without network if the fixed function is a pure string transform; if the canonical fixed function requires a live call, factor the transform into a directly-testable pure function during Task 2 and test that (still the real production function, just isolated).
  </action>
  <verify>
    <automated>cd /root/bitcoin_bot && python3 -m pytest tests/test_19_smartquote.py -v</automated>
  </verify>
  <acceptance_criteria>
    - `python3 -m pytest tests/test_19_smartquote.py -v` exits 0 with all tests passing.
    - The test imports the real fixed function from newsletter_poller (or block_pipeline) — `grep -q 'import newsletter_poller' tests/test_19_smartquote.py` (or the block_pipeline equivalent) is true; it does NOT contain a copy-pasted reimplementation of the transform.
    - A test asserts `it's` and `the agent's wallet` produce output containing chr(8217) or chr(39) and zero word-flanked chr(34).
    - A test asserts genuine double-quotes (`He said "ship it"`) survive unchanged.
    - The four ROADMAP tokens (`Cash App's`, `It's`, `world's`, `agent's`) each round-trip with a real apostrophe.
  </acceptance_criteria>
  <done>tests/test_19_smartquote.py exits 0; it calls the real fixed function; asserts apostrophe preserved + zero stray apostrophe-quote + genuine quotes intact.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| LLM writer → stored markdown | The model's JSON output crosses into the `newsletters` table via `save_newsletter`; malformed/ambiguous quote characters can be stored verbatim |
| stored markdown → render | `app.js` `marked.parse(content)` renders stored bytes to the live site (no typographer; transforms unlikely here) |
| diagnostic script → production Supabase | Read-only SELECT against `newsletters` (edition 30) — no mutation in this plan |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-19-01 | Tampering | New normalization step rewriting stored markdown | mitigate | Target ONLY the proven corruption signature (apostrophe positions); never a blanket `"`→`'`; preserve genuine quotes (Task 2 constraint + Task 3 edge-case test) |
| T-19-02 | Information disclosure / Injection | Corrected markdown later rendered via `marked.parse` | mitigate | Fix changes only apostrophe codepoints; introduces no new HTML/markdown control characters; no `<`/`>`/backtick injection. Render path (app.js) unchanged. |
| T-19-03 | Tampering (correctness) | Loss of legitimate double-quotes when "fixing" apostrophes | mitigate | The transform must not damage genuine `"` quotation marks — explicit edge-case test (`He said "ship it"`) asserts real quotes survive; HIGH-severity, blocks the plan if the test fails |
| T-19-04 | Denial of service (silent) | Fix silently passes corruption through on unexpected input | mitigate | Fail-loud per project memory — normalization raises/logs on ambiguous input rather than returning a still-corrupt string ("the wallet bug all over again") |
| T-19-05 | Repudiation | Root cause assumed, not evidenced | mitigate | 19-DIAGNOSIS.md records raw codepoints from edition 30's stored bytes; conclusion is byte-derived (Success Criterion #2) |

No package installs in this phase → Package Legitimacy Gate / supply-chain (T-19-SC) is N/A.
</threat_model>

<verification>
- 19-DIAGNOSIS.md exists, ≥20 lines, records raw codepoints + storage-vs-render conclusion + named fix site.
- `python3 -c "import ast; ast.parse(...)"` on newsletter_poller.py and block_pipeline.py exits 0.
- `python3 -m pytest tests/test_19_smartquote.py -v` exits 0; the test imports the real fixed function.
- No blanket `"`→`'` replacement; genuine quotes survive (edge-case test passes).
- docker/web/site/app.js unchanged unless the diagnostic proved a render-layer cause.
</verification>

<success_criteria>
- Root cause documented from raw stored bytes (Success Criterion #2) — NOT assumed.
- Write path fixed so newly generated editions store clean apostrophes (Success Criterion #3).
- Regression test locks `it's` / `the agent's wallet` through the real fixed function (Success Criterion #4, QUOTE-02).
- Fail-loud + genuine-quote-preservation honored (project constraints + T-19-03/04).
</success_criteria>

<output>
Create `.planning/phases/19-smart-quote-apostrophe-corruption-fix/19-01-SUMMARY.md` when done. It MUST record: the storage-vs-render conclusion, the exact fixed function (file + line range), and the canonical function name + import path the regression test uses — Plan 02's backfill transform must reuse that exact same corrected logic so the backfill repair matches the write-path fix.
</output>
