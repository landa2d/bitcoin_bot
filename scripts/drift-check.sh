#!/usr/bin/env bash
# drift-check.sh — standing pre-deploy drift detector (Phase 04.1 deploy-baseline guardrail).
#
# Catches the three drift classes that have actually bitten this prod, so the NEXT one is
# caught structurally instead of by tripping over it in production:
#   1. CODE      — a running container is older than the latest commit to its docker/<svc>/ dir
#   2. RPC       — a public postgres function has an EMPTY search_path (the silent-RPC class:
#                  claim_research_task, transfer_between_agents, …)
#   3. MIGRATION — a recent repo migration (>=033, prefix-consistent era) isn't applied on prod
#
# Read-only. Mutates nothing. Exit non-zero if any HARD drift (code or RPC) is found.
# DB checks (RPC, migration) require the gsd_drift_audit() function (migration 036) + Supabase
# REST creds in config/.env; they degrade gracefully (SKIP) if unavailable.
#
# Usage:  scripts/drift-check.sh        (run before any deploy; wire into a scheduled job if desired)
set -uo pipefail
cd "$(dirname "$0")/.."

HARD_DRIFT=0

echo "════════════════════════════════════════════════════════"
echo " DRIFT CHECK — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "════════════════════════════════════════════════════════"

# ── 1. CODE DRIFT (running image vs latest commit per service) ──────────────
echo
echo "[1] CODE DRIFT (running image vs latest commit per docker/<svc>/)"
# compose service -> running container name. lab-data-provider intentionally tracked too,
# though its deploy is deferred (D-07); web included for completeness.
SERVICES="gato_brain:agentpulse-gato-brain newsletter:agentpulse-newsletter processor:agentpulse-processor analyst:agentpulse-analyst research:agentpulse-research gato:openclaw-gato llm-proxy:agentpulse-llm-proxy web:agentpulse-web lab-data-provider:agentpulse-lab-data-provider"
for pair in $SERVICES; do
  svc="${pair%%:*}"; cname="${pair##*:}"
  img=$(docker inspect "$cname" --format '{{.Created}}' 2>/dev/null) || { printf "    ?   %-18s container %s not running\n" "$svc" "$cname"; continue; }
  commit=$(git log -1 --format='%cI' -- "docker/$svc" 2>/dev/null)
  [ -z "$commit" ] && { printf "    ?   %-18s no commits under docker/%s\n" "$svc" "$svc"; continue; }
  if [[ "$commit" > "$img" ]]; then
    printf "  DRIFT %-18s code %s  >  image %s\n" "$svc" "${commit:0:19}" "${img:0:19}"
    HARD_DRIFT=1
  else
    printf "    ok  %-18s image current\n" "$svc"
  fi
done

# ── DB checks (RPC + migration) via gsd_drift_audit() over PostgREST ─────────
echo
set -a; [ -f config/.env ] && . ./config/.env 2>/dev/null; set +a
KEY="${SUPABASE_SERVICE_KEY:-${SUPABASE_KEY:-}}"
if [ -z "${SUPABASE_URL:-}" ] || [ -z "$KEY" ]; then
  echo "[2/3] DB DRIFT — SKIP (SUPABASE_URL / service key not in config/.env)"
else
  RESP=$(curl -s -X POST "${SUPABASE_URL}/rest/v1/rpc/gsd_drift_audit" \
    -H "apikey: ${KEY}" -H "Authorization: Bearer ${KEY}" \
    -H "Content-Type: application/json" -d '{}' 2>/dev/null)
  if printf '%s' "$RESP" | grep -qiE 'PGRST202|could not find the function|"code":"42883"|not exist'; then
    echo "[2/3] DB DRIFT — SKIP: gsd_drift_audit() not on prod. Apply migration 036 to enable."
  else
    # 2. RPC empty-search_path class (HARD). Pass RESP via env var, not stdin: a heredoc
    #    script (python3 <<PY) overrides a piped stdin, so json.load(sys.stdin) would read empty.
    echo "[2] RPC DRIFT (public functions with empty search_path — silent-RPC class)"
    if GSD_RESP="$RESP" python3 <<'PY'
import os, json, sys
try:
    d = json.loads(os.environ["GSD_RESP"])
except Exception as e:
    print("  ?   could not parse gsd_drift_audit response:", e); sys.exit(0)
fns = d.get("empty_search_path_functions", [])
if not fns:
    print("    ok  no public function has an empty search_path"); sys.exit(0)
for f in fns:
    print("  DRIFT %s(%s)  search_path empty  (secdef=%s)" % (f["function"], f["args"], f["security_definer"]))
sys.exit(7)
PY
    then :; else HARD_DRIFT=1; fi

    # 3. Migration drift — recent (>=033) repo files not applied on prod (advisory)
    echo
    echo "[3] MIGRATION DRIFT (recent repo migrations >=033 not applied on prod — advisory)"
    APPLIED=$(printf '%s' "$RESP" | python3 -c "import sys,json; print('\n'.join(json.load(sys.stdin).get('applied_migrations',[])))" 2>/dev/null)
    found_any=0
    for f in supabase/migrations/*.sql; do
      base=$(basename "$f" .sql); num="${base%%_*}"
      case "$num" in ''|*[!0-9]*) continue;; esac
      [ "$num" -lt 33 ] 2>/dev/null && continue   # pre-033 prod names are inconsistent; skip to avoid false positives
      if printf '%s' "$APPLIED" | grep -qx "$base"; then
        printf "    ok  %s applied\n" "$base"
      else
        printf "  REVIEW %s NOT found in prod applied migrations (apply it, or naming differs)\n" "$base"; found_any=1
      fi
    done
    [ "$found_any" = 0 ] && echo "    ok  all recent (>=033) migrations applied"
  fi
fi

echo
echo "────────────────────────────────────────────────────────"
if [ "$HARD_DRIFT" = 0 ]; then
  echo " RESULT: no hard drift (code + RPC clean). Safe to deploy."
else
  echo " RESULT: HARD DRIFT detected (see DRIFT lines above). Resolve before deploying."
fi
echo "────────────────────────────────────────────────────────"
exit "$HARD_DRIFT"
