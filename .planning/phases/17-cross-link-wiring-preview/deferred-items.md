# Phase 17 — Deferred / Out-of-Scope Items

Items discovered during execution that are NOT caused by this phase's changes and
are out of scope per the SCOPE BOUNDARY rule. Logged here for the operator; not
fixed in-plan.

---

## DEF-17-01 — [HIGH / SECURITY] Pre-existing service_role key leak in a tracked file

- **Discovered during:** Plan 17-02, Task 1 (the D-02 / T-SVC-ROLE-LEAK guard in
  `scripts/verify_economy_map_crosslinks.py`).
- **Finding:** The full Supabase **service_role** JWT (full RLS bypass) is committed
  in a tracked file, `.claude/settings.local.json`, as a literal Bash
  permission-allowlist entry:
  `"Bash(SUPABASE_SERVICE_KEY=\"<service_role JWT>\" SUPABASE_URL=\"...\" python3 generate_strategic_edition18.py)"`.
- **Where:** `.claude/settings.local.json` (the Claude Code permissions file).
- **Provenance:** Committed **2026-04-30** in commit `0e42a5a`
  ("chore: add tool permissions for docker cp, file reads"). Present in **both HEAD
  and the working tree**. The file is **NOT gitignored**.
- **Why OUT OF SCOPE for this plan:**
  - It is **pre-existing** (39+ days old) and **NOT introduced by Phase 17** — the
    Phase-17 harness loads the key from `config/.env` (gitignored) and hardcodes
    nothing; the deployed `docker/web/site/app.js` keeps the `__SUPABASE_ANON_KEY__`
    placeholder.
  - It is in an **unrelated file** (Claude Code settings), NOT in the
    economy_map / web-preview deploy path this plan governs.
  - The plan's mandate is "the only new file is `scripts/verify_economy_map_crosslinks.py`";
    rotating the key + scrubbing git history is a **credentials/infra operation**
    (Rule 4 — architectural/security decision) that requires an **explicit operator
    decision**, not an in-plan auto-fix.
- **The phase-scoped D-02 gate PASSES regardless:** the harness confirms the
  service_role key appears in **none** of the web-deploy-path tracked files
  (`docker/web/site/app.js`, `entrypoint.sh`, `Dockerfile`, `Caddyfile`,
  `docker-compose.yml`) and that app.js retains the placeholder. The advisory
  repo-wide scan is what surfaced this pre-existing leak.
- **Recommended remediation (separate task, operator-owned):**
  1. **Rotate** the Supabase service_role key (Supabase dashboard → API → roll the
     service_role key), since the current value is in git history.
  2. Update `config/.env` (gitignored) + restart the affected services.
  3. Remove the key-bearing line from `.claude/settings.local.json` and consider
     adding `.claude/settings.local.json` to `.gitignore` (it is a per-machine
     local settings file).
  4. Optionally scrub the key from git history (`git filter-repo` / BFG) if the
     repo is or will be shared.

---
