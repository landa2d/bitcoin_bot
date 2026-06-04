---
phase: 06-telegram-read-only-scaffolding
plan: 02
status: complete
completed: 2026-05-30
wave: 2
requirements: [CMD-01, CMD-02]
key-files:
  created: []
  modified:
    - docker/gato_brain/gato_brain.py
commits: []
---

# Plan 06-02 Summary — Operator-Approved Scoped Rebuild + Live Smoke Test

## Self-Check: PASSED

## What was done

Brought the Plan 06-01 read-only commands live on the prod host (`/root/bitcoin_bot` IS prod) via a
**scoped, operator-approved** rebuild and verified both commands against real seeded `economy_map`
data through the running stack. No code changes in this plan — it is the deploy + live-verification
checkpoint for Plan 06-01's implementation.

### Task 1 — Pre-flight (auto)
- `python3 -c "import ast; ast.parse(...)"` on `gato_brain.py` → exit 0.
- `/map-*` symbol grep ≥ 4 (handle_map_command / handle_map_status / handle_map_pending / MAP_COMMAND present).

### Task 2 — Operator-approved scoped rebuild + smoke test (checkpoint:human-verify)
Pre-deploy gates and deploy run by the orchestrator after explicit operator approval (operator chose
"Proceed — I run it"):

1. **drift-check** (`scripts/drift-check.sh`): RPC clean; all migrations ≥033 applied; the only HARD
   drift lines were `gato_brain` (code-newer-than-image — exactly what this rebuild resolves) and the
   known deferred `lab-data-provider` D-07. Expected pre-deploy state.
2. **Scoped rebuild**: `cd /root/bitcoin_bot/docker && docker compose up -d --build --no-deps gato_brain`
   → image built, `agentpulse-gato-brain` recreated and **Up (healthy)**. No other service touched
   (honors deploy-scoped-and-approved / prod-cutover-discipline).
3. **Live smoke test** (driven through the authenticated `/chat` endpoint inside the container; the
   `X-Gato-Secret` was referenced by env-var name, never printed).

## Live evidence (criterion-1 / criterion-2)

**`/map-status`** (intent `MAP_COMMAND`) — tier-grouped monospace, real pills + counts, unsorted footer:
```
SUBSTRATE
  identity-trust             ◉◉◉○○ contested  ·2 new
  memory-context             ◉○○○○ nascent  ·20 new
  payments-settlement        ◉○○○○ nascent  ·1 new
BEHAVIOR
  autonomy-control           ◉○○○○ nascent  ·8 new
  governance-accountability  ◉○○○○ nascent  ·6 new
  psychology-disposition     ◉○○○○ nascent  ·24 new
FRAME
  regulation-legal           ◉○○○○ nascent  ·7 new
```
`unsorted: 21 awaiting`

**`/map-pending`** (intent `MAP_COMMAND`) — explicit drafts empty state + unsorted entries with full
UUIDs and pre-filled forward-contract write lines:
```
DRAFTS AWAITING APPROVAL
 Nothing awaiting approval.

UNSORTED AWAITING ASSIGNMENT
 · 'SocialX: A Modular Platform …'  conf:0.3
   entry: 954db35a-d233-43fb-adce-241d2ddd219b   →  /map-assign 954db35a-… <slug>
 … (full list; capped with "…and N more (truncated)" — see Deviations)
```

**`/map-bogus`** → `Unknown map command: /map-bogus` help (intent `MAP_COMMAND`; does not reach the
intent router; no crash).

**Read-only confirmed at runtime**: container logs show only `GET` requests to `block_body_versions`
(`status=eq.draft`) and `timeline_entries` (`block_slug=eq.unsorted`) returning 200 — zero mutations.
No tracebacks; `/health` 200.

## must_haves verification
- ✓ Post-rebuild `/map-status` returns live seven-block tier-grouped message with real maturity pills,
  `·N new` counts, and the `unsorted: N awaiting` footer.
- ✓ Post-rebuild `/map-pending` returns live unsorted entries with real UUIDs + the explicit drafts
  empty state.
- ✓ Deploy was the scoped, operator-approved `docker compose up -d --build --no-deps gato_brain`
  (no blind full deploy).

## Deviations / notes
- **Unsorted list truncation**: with 21 unsorted entries, `/map-pending` rendered ~19 then
  `…and N more (truncated)` — the executor mirrored the existing `/x-` `CHAR_BUDGET` truncation
  convention (in-pattern; the downstream Gato/Node layer also splits at 4000 chars). This is a
  pragmatic length guard but means "every unsorted entry" is not literally all-shown in a single
  message when the backlog is large. Flagged for the verifier; acceptable as a v1 length-safety
  behavior consistent with the codebase, and the operator can drain the backlog via Phase 10
  `/map-assign`. Revisit if full enumeration is required (e.g. paging).
- Maturity glyphs `◉`/`○` rendered legibly in the smoke output; no substitution needed (D-02 contract
  satisfied — 5-segment fill + word label).
- No code changed in this plan → no new commit; the deploy artifact is the rebuilt running container.
  STATE/ROADMAP tracking updated by the orchestrator post-checkpoint.
