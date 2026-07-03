---
created: 2026-07-03T08:20:00Z
updated: 2026-07-03T08:20:00Z
title: Phase 31 deferred review findings — WR-01 (edition-generation mixing) + WR-07 (hardcoded eval thresholds in gato_brain)
area: processor/gato_brain
priority: P2
phase_candidate: true
files:
  - docker/processor/agentpulse_processor.py
  - docker/gato_brain/gato_brain.py
  - docker/docker-compose.yml
---

## Context

Phase 31 code review (`.planning/phases/31-surfacing-escalation/31-REVIEW.md`, or its
v2.3 archive location after milestone close) surfaced 7 warnings. WR-03/05/06 were fixed
pre-verification and WR-02/04 in the post-phase fix pass; these two were triaged as
deferred-advisory because they only bite in specific flows.

## WR-01 — edition-keyed eval reads mix rows from multiple generations of the same edition

`edition_evals` identity is `UNIQUE (newsletter_id, layer, attempt)` (migration 045), but all
phase-31 readers (`_read_edition_evals` + `_format_notify_eval_section` in the processor;
`_eval_read_by_edition` + `_format_eval_detail` in gato_brain) filter only on `edition_number`.
Reprocessing an edition is a supported flow (`prepare_newsletter_data`'s `edition_override`,
agentpulse_processor.py:~5427), producing two `newsletters` rows with the same `edition_number`
and distinct `newsletter_id`s, each carrying its own eval rows. Consequences: the Friday notify's
`max(det_rows, key=attempt)` ties arbitrarily across generations (stale verdict/flags render);
`_format_eval_detail`'s `mech.extend`/`fab.extend` double-counts flags across generations.

**Fix direction (from review):** disambiguate by generation — the notify already has the current
draft row in hand, so filter the primary pipeline's rows on `newsletter_id`; for other reads keep
only the newest `newsletter_id` per `pipeline_version`.

**Trigger to prioritize:** the first time an edition is reprocessed via `edition_override`
during/after the calibration window.

## WR-07 — `_EVAL_FAIL_BELOW` hardcodes thresholds that are runtime-tunable

Judge thresholds are operator-tunable via `config/agentpulse-config.json → edition_eval.thresholds`
(merged in `judge_loop._merged_config`). gato_brain mirrors today's values in a hardcoded dict
(`gato_brain.py:~2429`) and has NO `../config` mount (docker-compose gato_brain mounts only the
workspace), so after any threshold tune, `/newsletter_eval`'s failing-dim detection (which gates
evidence/exemplar rendering) diverges from the judge's actual decision.

**Fix direction (from review, option b preferred):** stop re-deriving failure in gato_brain — render
evidence for any dim whose worst-body entry carries non-empty `evidence`/`exemplar_before` (the judge
only populates those for dims it flagged), which stays correct under any threshold config. Option (a):
mount `../config` ro into gato_brain and read `edition_eval.thresholds` per-call.

**Trigger to prioritize:** the first operator threshold tune (a stated Phase-29 capability, likely
during enforce calibration).
