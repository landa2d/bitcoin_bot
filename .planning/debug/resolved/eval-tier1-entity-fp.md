---
status: resolved
trigger: "Deterministic gate tier1_entity extraction misfires on real single-pass drafts — 27 of 31 fabrication flags on edition #104 are noise (sentence-initial words, sentence fragments, version-mislabeled entities); would have wrongly held the edition under enforce=true"
created: 2026-07-03T15:55:00Z
updated: 2026-07-03T19:00:00Z
---

## Symptoms

DATA_START
**Expected:** `run_deterministic_gate` on a real single-pass draft flags only genuine fabrication signals. For edition #104 that means: the 2 arXiv membership misses (`2606.06324`, `2604.19784` — cited in the draft, absent from the fact base, both real papers on arxiv.org) and genuinely fact-base-absent big-name entities IF they actually appear in the flagged version's body. Common words and sentence fragments are never entities.

**Actual:** 31 fabrication flags, verdict `held_fabrication` (report-only, so no status flip). Breakdown:
- `tier1_entity` ×27 — values include "According", "Auto", "Broken", "Date", "DevOps", "Engineering", "Fallback", "Nobody", "Note", "Platform", "Researchers", "Timeline", "Zero", "hedge ratio", and WHOLE SENTENCE FRAGMENTS: "It's the difference between blaming the driver for an accident that was actually", "became standard for cloud services after the early outages at Amazon Web Service", "is now a standard item in every vendor evaluation, the same way", "what happens if this model goes offline?". Also "Amazon", "Amazon Web Services", "Azure", "Microsoft", "Microsoft Azure", "Gemini", "Llama", "Mythos".
- VERSION ATTRIBUTION PUZZLE: "Amazon Web Services" is flagged `version: technical` but the literal string is NOT in the technical body (`content_markdown`) — orchestrator grep-verified. Extraction may run against different/concatenated text, or version labeling is wrong.
- `arxiv` ×2 — believed GENUINE (must survive any fix).
- `entity_merge` ×2 — "Google Cloud" (plausible) and "What Zuckerberg" (extraction noise).
- `mechanical` reading_mode_leak flags label "AUDIENCE:" `version: technical`, but "AUDIENCE:" is NOT in `content_markdown` — likely same extraction-source puzzle.
- `mechanical` duplicated_stat "5 mentions" vs prior edition 33 — plausible, low stakes.

**Errors:** none — silent miscalibration, exactly what the report-only window exists to catch.

**Timeline:** first-ever eval of a REAL single-pass draft (2026-07-03). Phase 28's golden-draft calibration suite used editions 34/36 via the block-pipeline-era verify_draft path; a real single-pass production draft was never in the fixture set. Never worked correctly on this input class; nothing regressed.

**Reproduction (deterministic, no LLM, no network needed for the entity checks):** draft = `newsletters` row id `666a8dea…` (edition_number=104, status='draft'): `{title, title_impact, content_markdown, content_markdown_impact, pipeline_version:'single_pass'}`. fact_base = that row's `data_snapshot` (verbatim `input_data` — see `newsletter_poller.py:2028`). Call `run_deterministic_gate(draft, fact_base, prior_edition, http_client=<mock or real>)` from `docker/newsletter/` (tests conftest inserts it on sys.path) or inside the `agentpulse-newsletter` container. The persisted flags are in `edition_evals` (edition_number=104, layer='deterministic').
DATA_END

## Constraints (from operator-approved scope)

- Fix lives in `docker/newsletter/verification.py` (the reused `verify_draft` entity-extraction engine) and/or `docker/newsletter/deterministic_gate.py`. Root-cause the extractor; don't just grow the stop-list unless the root cause genuinely is stop-list coverage.
- MUST NOT recalibrate away real signal: the 2 arXiv flags, the duplicated_stat mechanical flag, and genuine fact-base-absent entity detection must survive. The gate's reason to exist is catching exactly these.
- Freeze edition #104 as a golden regression fixture (draft + data_snapshot snapshot in tests/, mirroring the Phase 28 golden-suite pattern) with exact expected-flag assertions.
- Resolve the version-attribution puzzle (flags labeled `technical` for text seemingly only in the impact body) — per-version labels feed the operator's `/newsletter_eval` and Friday-notify views.
- Packaging lesson (v2.3 audit): after the fix, the deploy step is a scoped `docker compose up -d --build newsletter` on the main tree + verifying behavior INSIDE the running container. Deploy is orchestrator/operator-owned — the debugger agent must NOT run docker builds.
- Existing suites must stay green: tests/test_28_*, tests/test_27_*, tests/test_30_*, tests/test_31_*.

## Evidence

- timestamp: 2026-07-03T15:42Z — Real sequencer-path eval of edition #104 (real draft + recovered data_snapshot fact base) via `run_edition_eval`: verdict held_fabrication, flags {fabrication: 31, mechanical: 2, unverified: 0}; single `edition_evals` row (layer=deterministic, attempt=0, eval_status=ok) holds the full flag payload.
- timestamp: 2026-07-03T15:50Z — Orchestrator verification: both arXiv IDs cited in `content_markdown` AND live-200 on arxiv.org (real papers, absent from fact base → genuine grounding flags). "AUDIENCE:" NOT in `content_markdown`. "Amazon Web Services" NOT in `content_markdown` despite version:technical flag.

## Evidence (continued)

- timestamp: 2026-07-03T17:56Z — Offline repro built (newsletters row 666a8dea + data_snapshot as fact_base, prior_edition=None) reproduces the persisted payload EXACTLY: 31 fabrication (27 tier1_entity + 2 arxiv + 2 entity_merge), meta.tier1_count {technical:16, impact:11}, fact_base_path input_data. Full flag parity confirmed vs edition_evals.deterministic_flags.
- timestamp: 2026-07-03T18:00Z — VERSION PUZZLE RESOLVED (no bug). Every flag's `version` label correctly matches the body it was extracted from. "Amazon Web Services" is labeled `impact` in BOTH persisted data and repro (the symptom's "flagged technical" note was a transcription slip) and IS present only in content_markdown_impact. reading_mode_leak "AUDIENCE:" is labeled `technical` and IS present in content_markdown as the substring "Target audience:" (case-insensitive match) — the orchestrator's grep was case-sensitive for uppercase "AUDIENCE:" and missed "Target audience:". No extraction-source/concatenation bug exists.
- timestamp: 2026-07-03T18:05Z — ROOT CAUSE A (sentence/clause/line-initial capitalized words). `_PROPER_NOUN_SINGLE` (verification.py:104) fires on any capitalized word preceded by whitespace and relies ENTIRELY on `_STOP_WORDS` to reject non-entities. Its own comment claims "not at sentence start" but the regex never enforces it. Compounding: `_extract_claims_from_prose` collapses `\s+`→single-space (line 192) BEFORE the proper-noun regexes, destroying the newline/sentence boundaries the sibling `_PROPER_NOUN_MULTI` lookbehind `(?<![.!?\n])` relies on. Confirmed contexts: According/Auto/Broken/Fallback/Nobody/Note/Timeline/Researchers preceded by `. `; Date/Zero line-initial (`\n\n`); Platform/Engineering after `audience:` colon; "What Zuckerberg" (entity_merge) is a line-initial `_MULTI_CAP` whose first word "What" is a stop-word. Genuine entities Amazon/Azure/Microsoft/Gemini/Llama/Mythos are ALL mid-sentence (preceded by at/or/with/and/comma) and confirmed absent from the 223-entity fact base → genuine signal.
- timestamp: 2026-07-03T18:08Z — ROOT CAUSE B (straight-quote mis-pairing + rhetorical quotes). `_QUOTED` char class is three identical ASCII `"` (no smart-quote support) with a `{10,}` content minimum. In the impact body `"harness."` (8 chars < 10) fails to consume its opening quote, shifting the odd/even parity of all following quotes so the regex captures the UNQUOTED narrative BETWEEN real quotes as 498/2048/63-char "quotes" (then truncated to 80 via quote[:80]) → the 3 sentence fragments. Positional pairing (match any length, filter length after) recovers the real quotes cleanly. Remaining real quotes ("hedge ratio", "what happens if this model goes offline?", "what's your uptime guarantee?", "don't rely on just one AI vendor") are rhetorical/term/scare quotes with NO verifiable token (proper noun / acronym≥3 / number) — they assert nothing groundable and must not be classed as fabrications; the one real attributed quote "From Failed Trajectories to Reliable LLM Agents" DOES carry proper nouns and stays checked (grounded).

## Eliminated

- hypothesis: Version labels are wrong / extraction runs against a concatenated or mismatched text buffer.
  evidence: Every persisted flag's version matches the single body it was extracted from; "AUDIENCE:" (technical) is really "Target audience:" in content_markdown; "Amazon Web Services" is labeled impact (not technical) and lives only in the impact body. The verify_draft loop binds `label` to the exact body passed. No mislabeling.
  timestamp: 2026-07-03T18:00Z

## Resolution

root_cause: Two independent extractor defects in docker/newsletter/verification.py, both amplified by whitespace collapse that erases boundary info. (A) `_PROPER_NOUN_SINGLE`/`_MULTI_CAP` treat grammatical (sentence/clause/line-initial) capitalization as a named entity, relying on an unwinnable stop-list; (B) `_QUOTED` mis-pairs ambiguous straight quotes (a sub-10-char quote shifts parity) and treats rhetorical/term quotes as fabrications. Together they emit ordinary sentence-opening words + inter-quote narrative fragments as tier-1 fabrications. arXiv membership, duplicated_stat, and genuine ungrounded-entity detection are untouched by the defects and by the fix. VERSION-ATTRIBUTION PUZZLE: not a bug — every flag's version label matches the single body it was extracted from; the confusion was a case-sensitive grep of "AUDIENCE:" missing "Target audience:" in content_markdown, plus a transcription slip on "Amazon Web Services" (labeled impact, present in the impact body).

fix: (verification.py) Fix A — added `_is_boundary_initial()` and a newline-preserving `clean_nl` buffer; `_PROPER_NOUN_SINGLE` skips boundary-initial single words, `_MULTI_CAP` skips a phrase that opens a sentence/line when its first word is a stop word (kills "What Zuckerberg"). Fix B — `_QUOTED` changed from `{10,}` inline minimum to positional pairing (`"([^"]*)"`) with length filtered AFTER matching, plus `_quote_has_verifiable_token()` requiring a number/proper-noun/3+-acronym so rhetorical/scare quotes are not fabrications. Fix C — one targeted stop-word add: `devops` (a mid-sentence generic role term with no boundary signal). No change to _check_arxiv_membership, _check_cross_edition (duplicated_stat), or _build_block_list (the grounding set).

verification: Offline repro (tests conftest sys.path) on the frozen edition-104 fixture: fabrication 31→11 (8 genuine tier1_entity {Gemini,Llama,Amazon,Amazon Web Services,Azure,Microsoft,Microsoft Azure,Mythos} + 2 arxiv {2606.06324,2604.19784} + 1 entity_merge {Google Cloud}); mechanical 2 (reading_mode_leak + duplicated_stat "5 mentions" vs ed-33). Zero sentence-initial words, zero fragments, zero rhetorical quotes. New golden suite tests/test_28_edition_104_golden.py (8 tests) + full affected suites GREEN: 217 passed (test_27/28/29/30/31). HUMAN-VERIFIED LIVE 2026-07-03: newsletter container rebuilt with 5ca2ac0 (_PROPER_NOUN_SINGLE fix confirmed in running image), old noisy edition_evals row deleted, run_edition_eval re-run in-container on edition #104 with its real data_snapshot fact base — persisted result matches the golden fixture exactly (held_fabrication; tier1_entity ×8, arxiv ×2, entity_merge ×1 Google Cloud, mechanical ×2, unverified 0). All noise gone, all genuine signal preserved.

files_changed: [docker/newsletter/verification.py, tests/fixtures/edition_104_gate_golden.json, tests/test_28_edition_104_golden.py]

## Current Focus

reasoning_checkpoint:
  hypothesis: "The 27 tier1_entity FPs are produced by two extractor defects — boundary-blind capitalized-token extraction (A) and straight-quote mis-pairing + rhetorical-quote grading (B) — NOT by version mislabeling or the arXiv/duplicated_stat checks."
  confirming_evidence:
    - "Offline repro reproduces the persisted 31 flags exactly; instrumenting the extractor shows every noise value traces to _PROPER_NOUN_SINGLE/_MULTI_CAP boundary-blindness or _QUOTED parity-shift (498/2048/63-char captured spans)."
    - "All noise words sit at a sentence/clause/line boundary; all 6 surviving genuine entities sit mid-sentence and are absent from the fact base; the 2 arXiv flags cite real papers absent from the fact base."
  falsification_test: "After the boundary + quote fixes, run the offline repro: if the 6 genuine entities (Amazon/Azure/Microsoft/Gemini/Llama/Mythos), 2 arXiv flags, or duplicated_stat disappear, or if any sentence-initial word / fragment remains, the hypothesis is wrong."
  fix_rationale: "Boundary-aware extraction implements the code's own documented intent ('not at sentence start') on a newline-preserving buffer; positional quote pairing + a verifiable-token requirement address the root mis-pairing and the rhetorical-quote miscategorization. Neither touches _check_arxiv_membership, cross-edition duplicated_stat, nor the fact-base grounding set — so genuine signal is preserved by construction."
  blind_spots: "Recall loss for a genuine single-word entity that ONLY ever appears sentence-initially (accepted per the <5% FP precision goal). DevOps is a mid-sentence generic term with no boundary signal — resolved via a single targeted stop-word add. reading_mode_leak on 'Target audience:' is a separate operator-tunable mechanical (not fabrication) concern, left as-is."

test: DONE — fix applied + committed (5ca2ac0); offline repro on the frozen fixture confirms fabrication 31→11 with all genuine signal intact; 217 tests green.
expecting: DONE — matched exactly (see Resolution.verification).
next_action: NONE — human-verified live (container rebuilt with 5ca2ac0, in-container re-eval of edition #104 matches the golden fixture exactly). Session resolved and archived.
