---
created: 2026-07-04T09:00:00Z
updated: 2026-07-04T09:00:00Z
title: Writer grounding constraint — stop the single-pass writer citing unsourced entities/papers (prevention)
area: newsletter
priority: P2
phase_candidate: true
files:
  - docker/newsletter/newsletter_poller.py
---

## Problem

Edition #104 (first real gate data point, 2026-07-03): the single-pass writer name-dropped 8
entities (AWS, Azure, Microsoft, Gemini, Llama, Mythos…) and cited 2 real arXiv papers
(`2606.06324`, `2604.19784`) that appear NOWHERE in the edition's sources — drawn from model
memory. Verdict `held_fabrication` (report-only). This matches the writer's historical baseline
(Edition-34 validation: 14 T1 fabrications single-pass vs 0 block-pipeline).

Prevention beats detection: if the writer stops generating ungrounded references, fabrication
holds become rare instead of weekly operator work.

## Shape

- Add an explicit grounding constraint to the single-pass writer prompt(s): every named company,
  model, tool, study, and citation must come from the provided source material; if outside
  context is needed, phrase it generically without proper nouns/IDs.
- Consider echoing the fact base's entity list into the prompt as the allowed-references set
  (the gate already derives a 223-entity set from `input_data` — same derivation can feed the
  prompt).
- Measure via the gate itself: compare tier1_entity/arxiv flag counts on the next editions
  before/after the prompt change — the eval is the regression harness for its own prevention.
- Timing: AFTER enough calibration data exists to establish the baseline (~2 editions), so the
  prompt change's effect is measurable.
