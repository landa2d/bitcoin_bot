#!/bin/bash
# Security Supervisor - boot-time preflight checks
#
# Goals:
# - Validate environment requirements (based on env.schema.json when available)
# - Emit a redacted status snapshot + audit log to persistent storage
# - Send a Telegram alert to the owner (if Telegram is configured)
# - Never print secret values

set -e

LOG_DIR="/home/openclaw/.openclaw/logs"
CONFIG_DIR="/home/openclaw/.openclaw/config"
SCHEMA_PATH="${CONFIG_DIR}/env.schema.json"
STATUS_PATH="${LOG_DIR}/security-supervisor-status.json"
AUDIT_PATH="${LOG_DIR}/security-supervisor-audit.log"

mkdir -p "${LOG_DIR}" "${CONFIG_DIR}"

now_iso() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

telegram_send() {
  # Send a Telegram message if TELEGRAM_BOT_TOKEN + TELEGRAM_OWNER_ID exist.
  # Never prints secrets, and suppresses curl output.
  local text="$1"

  if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_OWNER_ID:-}" ]; then
    return 0
  fi

  # Use --data-urlencode to avoid escaping issues.
  curl -sS --fail \
    --data-urlencode "chat_id=${TELEGRAM_OWNER_ID}" \
    --data-urlencode "text=${text}" \
    "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    >/dev/null 2>&1 || true
}

append_audit() {
  local severity="$1"
  local category="$2"
  local message="$3"
  local details_json="$4"

  printf '%s\n' "$(node -e "
const entry = {
  timestamp: process.env.NOW_ISO,
  severity: process.env.SEVERITY,
  category: process.env.CATEGORY,
  message: process.env.MESSAGE,
  details: JSON.parse(process.env.DETAILS_JSON || '{}')
};
process.stdout.write(JSON.stringify(entry));
" \
    NOW_ISO="$(now_iso)" \
    SEVERITY="${severity}" \
    CATEGORY="${category}" \
    MESSAGE="${message}" \
    DETAILS_JSON="${details_json}" \
  )" >> "${AUDIT_PATH}"
}

build_status_json() {
  # Produces a JSON status snapshot to stdout.
  if [ ! -f "${SCHEMA_PATH}" ]; then
    node -e "
process.stdout.write(JSON.stringify({
  timestamp: new Date().toISOString(),
  schemaLoaded: false,
  groups: {},
  notes: ['env.schema.json not found; running minimal checks only']
}, null, 2));
"
    return 0
  fi

  node -e "
const fs = require('fs');

const schemaPath = process.env.SCHEMA_PATH;
const schema = JSON.parse(fs.readFileSync(schemaPath, 'utf8'));

function present(key) {
  const v = process.env[key];
  return typeof v === 'string' && v.length > 0;
}

const groups = {};
const notes = [];

for (const g of schema.groups || []) {
  const missing = [];
  const presentKeys = [];

  for (const k of g.required || []) {
    if (present(k)) presentKeys.push(k);
    else missing.push(k);
  }
  for (const k of g.optional || []) {
    if (present(k)) presentKeys.push(k);
  }

  groups[g.id] = {
    missing,
    present: presentKeys
  };

  if (g.id === 'telegram' && (missing || []).length > 0) {
    notes.push('Telegram approvals degraded until TELEGRAM_BOT_TOKEN and TELEGRAM_OWNER_ID are set.');
  }
  if (g.id === 'moltbook' && (missing || []).length > 0) {
    notes.push('Moltbook not configured; MOLTBOOK_API_TOKEN is missing.');
  }
}

// Numeric safety relationships
function asInt(key) {
  const v = process.env[key];
  if (!v) return null;
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : null;
}

const daily = asInt('WALLET_DAILY_LIMIT_SATS');
const threshold = asInt('WALLET_APPROVAL_THRESHOLD_SATS');
if (daily !== null && threshold !== null && threshold > daily) {
  notes.push('Unsafe wallet settings: WALLET_APPROVAL_THRESHOLD_SATS is greater than WALLET_DAILY_LIMIT_SATS.');
}

process.stdout.write(JSON.stringify({
  timestamp: new Date().toISOString(),
  schemaLoaded: true,
  groups,
  notes
}, null, 2));
"
}

main() {
  local ts
  ts="$(now_iso)"

  # Build status snapshot
  local status_json
  status_json="$(SCHEMA_PATH="${SCHEMA_PATH}" build_status_json)"
  printf '%s\n' "${status_json}" > "${STATUS_PATH}"

  # Minimal critical checks (do not print secret values)
  local critical_missing=()
  local warnings=()

  if [ -z "${OPENAI_API_KEY:-}" ]; then
    critical_missing+=("OPENAI_API_KEY")
  fi

  if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_OWNER_ID:-}" ]; then
    warnings+=("Telegram not fully configured (approvals/alerts may be degraded).")
  fi

  if [ -n "${LNBITS_ADMIN_KEY:-}" ] && [ -z "${WALLET_DAILY_LIMIT_SATS:-}" ]; then
    warnings+=("LNBITS_ADMIN_KEY is set but WALLET_DAILY_LIMIT_SATS is not set (consider setting a daily spend limit).")
  fi

  if [ -n "${LNBITS_ADMIN_KEY:-}" ] && [ -z "${WALLET_APPROVAL_THRESHOLD_SATS:-}" ]; then
    warnings+=("LNBITS_ADMIN_KEY is set but WALLET_APPROVAL_THRESHOLD_SATS is not set (approval gating should be explicit).")
  fi

  if [ -n "${MOLTBOOK_API_TOKEN:-}" ] && [ "${REQUIRE_POST_APPROVAL:-true}" != "true" ]; then
    warnings+=("Moltbook is configured but REQUIRE_POST_APPROVAL is not 'true' (consider enabling approvals).")
  fi

  # Audit log entry
  if [ "${#critical_missing[@]}" -gt 0 ]; then
    append_audit "CRITICAL" "ENV" "Missing critical environment keys" "$(node -e "process.stdout.write(JSON.stringify({ missing: (process.env.MISSING || '').split(',').filter(Boolean) }))" MISSING="$(IFS=,; echo "${critical_missing[*]}")")"
  else
    append_audit "INFO" "ENV" "Preflight environment check completed" "$(node -e "process.stdout.write(JSON.stringify({ ok: true }))")"
  fi

  # Build Telegram message (redacted)
  local msg="Security Supervisor preflight completed.\n\n"
  if [ "${#critical_missing[@]}" -gt 0 ]; then
    msg="${msg}CRITICAL: Missing required key(s): ${critical_missing[*]}\n"
  else
    msg="${msg}Core requirements: OK\n"
  fi

  if [ "${#warnings[@]}" -gt 0 ]; then
    msg="${msg}\nWarnings:\n"
    for w in "${warnings[@]}"; do
      msg="${msg}- ${w}\n"
    done
  fi

  msg="${msg}\nStatus written to:\n- ${STATUS_PATH}\n- ${AUDIT_PATH}"

  telegram_send "${msg}"

  # Also print a short, redacted summary to container logs
  echo "[security-supervisor] Preflight done. Status: ${STATUS_PATH} Audit: ${AUDIT_PATH}"
  if [ "${#critical_missing[@]}" -gt 0 ]; then
    echo "[security-supervisor] CRITICAL missing keys: ${critical_missing[*]}"
  fi
  if [ "${#warnings[@]}" -gt 0 ]; then
    echo "[security-supervisor] WARNINGS:"
    for w in "${warnings[@]}"; do
      echo "  - ${w}"
    done
  fi
}

main "$@"

