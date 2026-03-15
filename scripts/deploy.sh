#!/bin/bash
# deploy.sh — Sync local files to Hetzner server and rebuild changed services
set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
REMOTE_USER="${DEPLOY_USER:-root}"
REMOTE_HOST="${DEPLOY_HOST:?Set DEPLOY_HOST (e.g. 1.2.3.4 or myserver)}"
REMOTE_DIR="${DEPLOY_DIR:-/opt/bitcoin_bot}"
SSH_KEY="${DEPLOY_SSH_KEY:-}"   # optional: -i /path/to/key

DRY_RUN=false
FORCE_REBUILD=""

# ── Argument parsing ──────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)   DRY_RUN=true; shift ;;
        --force-rebuild)
            shift
            FORCE_REBUILD="${1:-all}"
            shift
            ;;
        -h|--help)
            echo "Usage: deploy.sh [--dry-run] [--force-rebuild [service]]"
            echo ""
            echo "  --dry-run              Show what would change without syncing"
            echo "  --force-rebuild [svc]  Force rebuild of a service (or 'all')"
            echo ""
            echo "Environment variables:"
            echo "  DEPLOY_HOST   (required) Server hostname or IP"
            echo "  DEPLOY_USER   (default: root)"
            echo "  DEPLOY_DIR    (default: /opt/bitcoin_bot)"
            echo "  DEPLOY_SSH_KEY Optional path to SSH key"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── SSH / rsync helpers ───────────────────────────────────────────
SSH_OPTS="-o StrictHostKeyChecking=accept-new -o ConnectTimeout=10"
[[ -n "$SSH_KEY" ]] && SSH_OPTS="$SSH_OPTS -i $SSH_KEY"

ssh_cmd() { ssh $SSH_OPTS "${REMOTE_USER}@${REMOTE_HOST}" "$@"; }

rsync_dir() {
    local src="$1" dest="$2"
    shift 2
    local flags=(-avz --delete --checksum -e "ssh $SSH_OPTS" "$@")
    if $DRY_RUN; then
        flags+=(--dry-run)
    fi
    rsync "${flags[@]}" "$src" "${REMOTE_USER}@${REMOTE_HOST}:${dest}"
}

# ── Sync directories ─────────────────────────────────────────────
echo "=== Deploying to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR} ==="
echo ""

CHANGED_FILES=$(mktemp)
trap 'rm -f "$CHANGED_FILES"' EXIT

sync_one() {
    local label="$1" src="$2" dest="$3"
    shift 3
    echo "── Syncing $label ──"
    rsync_dir "$src" "$dest" "$@" | tee -a "$CHANGED_FILES"
    echo ""
}

sync_one "docker/"    "$BASE_DIR/docker/"    "$REMOTE_DIR/docker/"    --exclude='.env'
sync_one "config/"    "$BASE_DIR/config/"    "$REMOTE_DIR/config/"    --exclude='.env'
sync_one "skills/"    "$BASE_DIR/skills/"    "$REMOTE_DIR/skills/"
sync_one "templates/" "$BASE_DIR/templates/" "$REMOTE_DIR/templates/"

if $DRY_RUN; then
    echo "=== Dry run complete — no changes made ==="
    exit 0
fi

# ── Map changed files → services ─────────────────────────────────
declare -A NEED_REBUILD

map_service() {
    local pattern="$1" service="$2"
    if grep -qE "$pattern" "$CHANGED_FILES" 2>/dev/null; then
        NEED_REBUILD["$service"]=1
    fi
}

map_service 'docker/gato/'                         gato
map_service 'docker/preflight\.sh'                  gato
map_service 'docker/moltbook_post_watcher\.sh'      gato
map_service 'docker/gato_brain/'                     gato_brain
map_service 'docker/processor/'                      processor
map_service 'docker/analyst/'                        analyst
map_service 'docker/newsletter/'                     newsletter
map_service 'docker/research/'                       research
map_service 'docker/web/'                            web

# docker-compose.yml change → rebuild everything that was also touched
if grep -qE 'docker-compose\.yml' "$CHANGED_FILES" 2>/dev/null; then
    echo "docker-compose.yml changed — marking all services for restart"
    for svc in gato gato_brain processor analyst newsletter research web; do
        NEED_REBUILD["$svc"]=1
    done
fi

# config/ or templates/ changes don't require a rebuild but services that
# volume-mount them need a restart
if grep -qE '(config/|templates/|skills/)' "$CHANGED_FILES" 2>/dev/null; then
    echo "Config/templates changed — marking dependent services for restart"
    # All services mount config/.env; processor/analyst/newsletter/research mount templates
    for svc in gato gato_brain processor analyst newsletter research; do
        NEED_REBUILD["$svc"]=1
    done
fi

# ── Force rebuild override ────────────────────────────────────────
if [[ -n "$FORCE_REBUILD" ]]; then
    if [[ "$FORCE_REBUILD" == "all" ]]; then
        for svc in gato gato_brain processor analyst newsletter research web; do
            NEED_REBUILD["$svc"]=1
        done
    else
        NEED_REBUILD["$FORCE_REBUILD"]=1
    fi
fi

# ── Rebuild + restart ─────────────────────────────────────────────
SERVICES="${!NEED_REBUILD[*]}"

if [[ -z "$SERVICES" ]]; then
    echo "=== No services need rebuilding ==="
    exit 0
fi

echo "=== Rebuilding: $SERVICES ==="
ssh_cmd "cd $REMOTE_DIR/docker && docker compose build $SERVICES && docker compose up -d $SERVICES"

# ── Verify ────────────────────────────────────────────────────────
echo ""
echo "=== Post-deploy status ==="
ssh_cmd "cd $REMOTE_DIR/docker && docker compose ps"
echo ""
echo "=== Deploy complete ==="
