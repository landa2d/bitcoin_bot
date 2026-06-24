# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## single-pass-writer-empty — single-pass newsletter writer parsed claude-sonnet-4-6 large response as "empty"
- **Date:** 2026-06-24
- **Error patterns:** Failed to parse model response as JSON, Expecting value: line 1 column 1 (char 0), content[0].text empty, newsletter generation fails, claude-sonnet-4-6, write_newsletter, JSONDecodeError
- **Root cause:** Brittle JSON extraction — `response.content[0].text.strip()`, strip markdown fences ONLY when `text.startswith("```")`, then `json.loads()`. claude-sonnet-4-6 frames large single-shot JSON output stochastically (bare / ```json-fenced / occasionally prose-prefixed); any framing that wasn't bare-or-leading-fence skipped the strip and `json.loads` failed at "char 0". NOT empty content, NOT a non-text/thinking block, NOT multi-block splitting — verified by inspecting 7 real responses (always one fully-populated text block). The "char 0" JSONDecodeError fires for ANY non-JSON leading char, not just empty; a non-text block would raise AttributeError instead.
- **Fix:** Shared `response_text()` (joins text blocks) + `parse_llm_json()` (raw → ```json/``` fenced [case-insensitive, DOTALL] → first balanced `{...}` [string/escape-aware]; FAIL LOUD with logged head/tail when nothing parses — never silent-empty). Applied at qualitative_review, editorial_prepass, and the writer (both branches); strategic_editor uses response_text() for multi-block safety.
- **Files changed:** docker/newsletter/newsletter_poller.py, tests/test_27_llm_json_extract.py
---
