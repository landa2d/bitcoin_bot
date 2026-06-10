---
phase: 19-smart-quote-apostrophe-corruption-fix
plan: 02
type: execute
wave: 2
depends_on: ["19-01"]
files_modified:
  - .planning/phases/19-smart-quote-apostrophe-corruption-fix/19-BACKFILL-REVIEW.md
autonomous: false
requirements: [QUOTE-01]

must_haves:
  truths:
    - "Edition 30 (and other backfilled editions) render Cash App's, It's, world's, agent's correctly on the live site — zero straight-double-quote-in-place-of-apostrophe corruption in the body (QUOTE-01, Success Criterion #1)"
    - "Existing editions are corrected via a scoped, reviewed UPDATE shown before/after on ONE edition first (edition 30) for operator approval — NEVER a blind table-wide find-replace (QUOTE-01 spine constraint)"
    - "The backfill repair reuses the exact same corrected logic as the write-path fix from Plan 01 — the stored bytes after backfill match what the fixed write path would now produce"
    - "The table-wide UPDATE and the container rebuild run against the absolute main-tree path (worktree-unsafe), are operator-gated, and the live DB apply is orchestrator-owned"
  artifacts:
    - path: ".planning/phases/19-smart-quote-apostrophe-corruption-fix/19-BACKFILL-REVIEW.md"
      provides: "Before/after diff of edition 30's content_markdown + content_markdown_impact, the list of affected editions, and the exact scoped UPDATE plan presented for operator approval"
      min_lines: 25
  key_links:
    - from: "the backfill transform"
      to: "the Plan 01 corrected write-path logic"
      via: "imports/reuses the same canonical function — not a second, divergent regex"
      pattern: "newsletter_poller|block_pipeline"
    - from: "the operator approval checkpoint"
      to: "the table-wide scoped UPDATE"
      via: "the table-wide UPDATE runs ONLY after explicit operator approval of the single-edition before/after"
      pattern: "approved"
---

<objective>
Correct the apostrophe corruption already baked into existing stored editions via a SCOPED, REVIEWED UPDATE — shown before/after on ONE edition (edition 30) first for operator approval — then apply to the affected editions, and roll out by rebuilding the content service. Because the cause is in stored markdown (per Plan 01's diagnostic), correcting the stored bytes fixes the live render directly; no web rebuild is needed unless Plan 01 proved a render-layer cause.

Purpose: Success Criterion #1 — the highest-visibility live bug is gone on existing editions. The spine (PROJECT.md): the backfill is a scoped reviewed UPDATE shown before/after on ONE edition first, NEVER a blind table-wide find-replace. This is a live-data mutation against production Supabase, so it is operator-gated and orchestrator-owned.

Output: `19-BACKFILL-REVIEW.md` (the before/after + affected-edition list + UPDATE plan), an operator approval gate, and the applied backfill + scoped service rebuild.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md

# The diagnostic + the corrected write-path logic this backfill must reuse
@.planning/phases/19-smart-quote-apostrophe-corruption-fix/19-DIAGNOSIS.md
@.planning/phases/19-smart-quote-apostrophe-corruption-fix/19-01-SUMMARY.md
@docker/newsletter/newsletter_poller.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Identify affected editions + build the single-edition before/after review (edition 30)</name>
  <files>.planning/phases/19-smart-quote-apostrophe-corruption-fix/19-BACKFILL-REVIEW.md</files>
  <read_first>
    - .planning/phases/19-smart-quote-apostrophe-corruption-fix/19-DIAGNOSIS.md (the proven corruption signature + the canonical corrected logic to reuse)
    - .planning/phases/19-smart-quote-apostrophe-corruption-fix/19-01-SUMMARY.md (the exact fixed function name + import path — the backfill MUST reuse this, not a divergent regex)
    - docker/newsletter/newsletter_poller.py (the fixed write-path function — import/reuse it for the repair so the backfill output matches the write-path fix)
    - .planning/STATE.md (edition status memory: edition 30 corrupt exemplar; 25–29, 32 held; 34 draft)
    - config/.env (SUPABASE_URL + SUPABASE_SERVICE_KEY for the read)
  </read_first>
  <action>
    Read-only scan of the `newsletters` table to enumerate which editions carry the corruption signature. For every edition, check `content_markdown`, `content_markdown_impact`, and `content_telegram` for the proven signature from 19-DIAGNOSIS.md (a U+0022 `"` standing in for an apostrophe — e.g. word-char + `"` + word-char, or whatever exact pattern the diagnostic defined). Record the affected `edition_number` list and, per edition, which of the three columns are affected and the occurrence counts.

    For edition 30 specifically, compute the REPAIRED bytes by running each affected column's stored value through the SAME canonical corrected logic produced in Plan 01 (reuse the fixed function / its extracted pure transform — do NOT write a second, divergent regex; a divergent transform could repair differently than the write-path fix, reintroducing drift). Produce a precise before/after for edition 30: for each of the four ROADMAP tokens present (`Cash App's`, `It's`, `world's`, `agent's`) and every other occurrence, show the BEFORE substring (with the stray `"`) and the AFTER substring (with the real apostrophe), plus the total replacement count per column.

    Write `.planning/phases/19-smart-quote-apostrophe-corruption-fix/19-BACKFILL-REVIEW.md` containing: (a) the affected-edition list with per-column occurrence counts; (b) the edition-30 before/after diff; (c) the exact scoped UPDATE plan — which editions, which columns, that the WHERE clause targets specific `edition_number` values (NOT a table-wide unconditional UPDATE), and that genuine double-quotes are untouched (the transform only repairs the apostrophe signature, per T-19-03). Do NOT mutate any data in this task (read + compute only).
  </action>
  <verify>
    <automated>test -f .planning/phases/19-smart-quote-apostrophe-corruption-fix/19-BACKFILL-REVIEW.md && grep -Eq "edition.?30|Edition 30" .planning/phases/19-smart-quote-apostrophe-corruption-fix/19-BACKFILL-REVIEW.md && grep -Eqi "before|after" .planning/phases/19-smart-quote-apostrophe-corruption-fix/19-BACKFILL-REVIEW.md && echo PASS</automated>
  </verify>
  <acceptance_criteria>
    - `19-BACKFILL-REVIEW.md` exists, ≥25 lines.
    - It lists the affected editions with per-column (`content_markdown` / `content_markdown_impact` / `content_telegram`) occurrence counts.
    - It shows a concrete before/after for edition 30 covering the ROADMAP tokens present, with a per-column replacement count.
    - The repair was computed by REUSING the Plan 01 corrected logic (named in 19-01-SUMMARY.md), not a new divergent regex.
    - The documented UPDATE plan targets specific `edition_number` values (scoped WHERE), explicitly NOT a table-wide unconditional find-replace.
    - The review states genuine double-quotes are left untouched.
    - No data was mutated in this task.
  </acceptance_criteria>
  <done>19-BACKFILL-REVIEW.md presents the affected-edition list + edition-30 before/after computed via the Plan 01 fix + a scoped (per-edition) UPDATE plan; no mutation yet.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking-human">
  <name>Task 2: Operator approval of the single-edition before/after backfill review</name>
  <files>.planning/phases/19-smart-quote-apostrophe-corruption-fix/19-BACKFILL-REVIEW.md</files>
  <action>PAUSE for operator review — do NOT run any UPDATE until the operator approves. Present `19-BACKFILL-REVIEW.md` (the affected-edition list + edition-30 before/after + scoped UPDATE plan). Approval here is what authorizes the scoped backfill UPDATE in Task 3; without it, Task 3 must not run. This checkpoint is blocking-human and is never auto-approved.</action>
  <what-built>
    A read-only backfill review (`19-BACKFILL-REVIEW.md`) showing: the list of corrupt editions, and a concrete BEFORE/AFTER of edition 30's `content_markdown` + `content_markdown_impact` (and `content_telegram` if corrupt) with the stray `"` repaired to a real apostrophe — computed by reusing the Plan 01 write-path fix. NO data has been mutated yet.
  </what-built>
  <how-to-verify>
    1. Open `.planning/phases/19-smart-quote-apostrophe-corruption-fix/19-BACKFILL-REVIEW.md`.
    2. Confirm the edition-30 BEFORE column shows the corruption (e.g. `Cash App"s`, `It"s`) and the AFTER column shows the correct apostrophe (`Cash App's`, `It's`).
    3. Confirm the affected-edition list looks right (edition 30 present; spot-check that the count is plausible against held editions 25–29/32 and draft 34).
    4. Confirm the UPDATE plan is SCOPED (targets specific `edition_number` values), not a table-wide find-replace, and that genuine double-quotes are reported as untouched.
    5. This is a live mutation against production Supabase and is worktree-unsafe — the apply (Task 3) is orchestrator-owned from the absolute main tree.
  </how-to-verify>
  <verify><human-check>Operator confirms the edition-30 before/after is correct, the affected-edition list is right, and the UPDATE is scoped (not table-wide) before authorizing Task 3.</human-check></verify>
  <acceptance_criteria>
    - The operator has explicitly approved (resume signal "approved") before any UPDATE runs.
    - The review presented is scoped per `edition_number` (not a table-wide find-replace).
    - No data has been mutated at the point this checkpoint is reached.
  </acceptance_criteria>
  <done>Operator has reviewed the edition-30 before/after and the scoped UPDATE plan and typed "approved" (or requested changes). No mutation occurs before approval.</done>
  <resume-signal>Type "approved" to authorize the scoped backfill UPDATE on the listed editions, or describe required changes (e.g. narrow the edition list / fix the transform).</resume-signal>
</task>

<task type="auto">
  <name>Task 3: Apply the scoped backfill + scoped content-service rebuild (orchestrator-owned, no-worktree)</name>
  <files>.planning/phases/19-smart-quote-apostrophe-corruption-fix/19-BACKFILL-REVIEW.md</files>
  <read_first>
    - .planning/phases/19-smart-quote-apostrophe-corruption-fix/19-BACKFILL-REVIEW.md (the approved affected-edition list + the exact repaired values to write)
    - .planning/phases/19-smart-quote-apostrophe-corruption-fix/19-01-SUMMARY.md (the fixed function — the rebuild ships this so newly generated editions are clean)
    - CLAUDE.md (Build & Run: `cd /root/bitcoin_bot/docker && docker compose up -d --build <service>`)
    - MEMORY reference_scoped_rebuild_worktree_unsafe + project_executor_edits_state_directly: rebuild + live DB apply run against the absolute main-tree path, orchestrator-owned, never a worktree executor
  </read_first>
  <action>
    GATED: run ONLY after the Task 2 operator approval. This task performs the live mutation and rebuild and is worktree-unsafe — run against the absolute path `/root/bitcoin_bot`, NOT a worktree; the live Supabase apply is orchestrator-owned.

    1. Apply the scoped UPDATE to the `newsletters` table for ONLY the approved `edition_number` values, writing the repaired `content_markdown` / `content_markdown_impact` / `content_telegram` (only the columns flagged corrupt per edition). The UPDATE WHERE clause MUST target specific `edition_number` values — NEVER an unconditional table-wide statement. Write the repaired value computed by the Plan 01 corrected logic (do not re-derive a new transform). Do not touch the `block_body_versions` / `publish_block_version` machinery — `newsletters` is a separate table with no versioning RPC; a scoped reviewed UPDATE is the sanctioned correction path here per the ROADMAP Notes.

    2. Verify post-UPDATE: re-read the affected editions and assert the corruption signature count is now zero in the updated columns and the four ROADMAP tokens contain real apostrophes; assert genuine double-quotes elsewhere are unchanged (compare against the BEFORE counts in 19-BACKFILL-REVIEW.md).

    3. Roll out the write-path fix so newly generated editions are clean: scoped rebuild of the content service that owns the write path — `cd /root/bitcoin_bot/docker && docker compose up -d --build newsletter` (add `processor` ONLY if 19-DIAGNOSIS.md placed the fixed function in the processor). Do NOT rebuild `web` — the renderer is unchanged (the fix is in stored bytes); correcting storage fixes the live render directly.
  </action>
  <verify>
    <automated>cd /root/bitcoin_bot/docker && docker compose ps newsletter --format '{{.State}}' | grep -q running && echo "REBUILD OK"</automated>
  </verify>
  <acceptance_criteria>
    - The scoped UPDATE ran ONLY against the operator-approved `edition_number` values (scoped WHERE), never table-wide.
    - Post-UPDATE re-read of edition 30 shows zero corruption-signature occurrences in the updated columns and real apostrophes in `Cash App's` / `It's` / `world's` / `agent's`.
    - Genuine double-quotes in the affected editions are unchanged vs the BEFORE counts.
    - `docker compose ps newsletter` reports the `newsletter` service running after the scoped rebuild.
    - `web` was NOT rebuilt (unless the diagnostic proved a render-layer cause).
    - The apply + rebuild ran against `/root/bitcoin_bot` (absolute main tree), not a worktree.
  </acceptance_criteria>
  <done>Approved editions backfilled with real apostrophes via a scoped per-edition UPDATE; post-UPDATE re-read confirms zero corruption + intact genuine quotes; the content service rebuilt to ship the write-path fix; web untouched.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| backfill script → production Supabase `newsletters` | A live UPDATE mutates stored edition bodies — highest blast-radius surface in this phase |
| stored markdown → live render | Corrected stored bytes render directly via `marked.parse` (no web rebuild needed) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-19-10 | Tampering (blast radius) | Scoped backfill UPDATE over-matching / corrupting good data | mitigate | HIGH severity. Single-edition (30) before/after review FIRST + blocking operator approval gate; UPDATE WHERE targets specific `edition_number` values (never unconditional); repair reuses the Plan 01 fix (anchored to the apostrophe signature only); post-UPDATE re-read verifies zero corruption + intact genuine quotes. Blocks the plan if the review is not approved. |
| T-19-11 | Tampering (correctness) | Loss of legitimate `"` quotes during backfill | mitigate | The repair transform only touches the apostrophe signature; before/after review surfaces any genuine-quote change; post-UPDATE assertion compares genuine-quote counts against BEFORE. |
| T-19-12 | Elevation / wrong-tree apply | Live DB apply or rebuild from a stale worktree | mitigate | Apply + rebuild are orchestrator-owned from the absolute `/root/bitcoin_bot` main tree, never a worktree executor (project memory reference_scoped_rebuild_worktree_unsafe). |
| T-19-13 | Repudiation | Blind table-wide find-replace | mitigate | Prohibited by the spine; UPDATE is scoped per approved `edition_number`; the review documents the exact scope; checkpoint is `blocking-human` (never auto-approved). |
| T-19-14 | Denial of service | Rebuilding `web` unnecessarily / wrong service | mitigate | Rebuild scoped to `newsletter` (the write-path owner) by service key; `web` explicitly not rebuilt since the fix is in stored bytes. |

No package installs → no supply-chain threat.
</threat_model>

<verification>
- 19-BACKFILL-REVIEW.md exists (≥25 lines) with affected-edition list + edition-30 before/after + scoped UPDATE plan.
- Operator approval recorded before any UPDATE (blocking-human checkpoint).
- Post-UPDATE re-read of edition 30: zero corruption signature in updated columns, real apostrophes in the four ROADMAP tokens, genuine quotes intact.
- `docker compose ps newsletter` running after scoped rebuild; `web` not rebuilt.
- Apply + rebuild ran from the absolute main tree.
</verification>

<success_criteria>
- Existing editions (incl. 30) render apostrophes correctly on the live site — zero stray-quote corruption (Success Criterion #1, QUOTE-01).
- Correction was a scoped reviewed UPDATE, before/after on edition 30 first, operator-approved — never a blind find-replace (spine).
- The content service rebuilt so the write-path fix is live for new editions.
</success_criteria>

<output>
Create `.planning/phases/19-smart-quote-apostrophe-corruption-fix/19-02-SUMMARY.md` when done. Record: the final affected-edition list, the per-edition/per-column replacement counts, confirmation of the operator approval, the post-UPDATE zero-corruption verification, and which service(s) were rebuilt.
</output>
