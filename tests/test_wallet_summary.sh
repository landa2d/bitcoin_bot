#!/usr/bin/env bash
# Test the /v1/proxy/wallet/{agent_name}/summary endpoint
# Usage: ./tests/test_wallet_summary.sh [BRAIN_URL]
#
# Prerequisites: migration 020 applied, gato_brain running.

set -euo pipefail

BRAIN_URL="${1:-http://localhost:8100}"
ENDPOINT="$BRAIN_URL/v1/proxy/wallet"
PASS=0
FAIL=0

green() { printf "\033[32m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*"; }

assert_status() {
    local label="$1" expected="$2" actual="$3"
    if [ "$actual" = "$expected" ]; then
        green "  PASS  $label (HTTP $actual)"
        PASS=$((PASS + 1))
    else
        red   "  FAIL  $label — expected $expected, got $actual"
        FAIL=$((FAIL + 1))
    fi
}

# ── Fetch API keys from Supabase ──────────────────────────────────
echo "Fetching agent API keys from Supabase..."

if [ -f "$(dirname "$0")/../config/.env" ]; then
    source "$(dirname "$0")/../config/.env"
fi

SUPABASE_URL="${SUPABASE_URL:?Set SUPABASE_URL}"
SUPABASE_SERVICE_KEY="${SUPABASE_SERVICE_KEY:-$SUPABASE_KEY}"
SUPABASE_SERVICE_KEY="${SUPABASE_SERVICE_KEY:?Set SUPABASE_SERVICE_KEY or SUPABASE_KEY}"

fetch_key() {
    local agent="$1"
    curl -s "$SUPABASE_URL/rest/v1/agent_api_keys?agent_name=eq.$agent&select=api_key" \
        -H "apikey: $SUPABASE_SERVICE_KEY" \
        -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
        | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['api_key'])" 2>/dev/null
}

ADMIN_KEY=$(fetch_key admin)
ANALYST_KEY=$(fetch_key analyst)
NEWSLETTER_KEY=$(fetch_key newsletter)
RESEARCH_KEY=$(fetch_key research)
GATO_KEY=$(fetch_key gato)
PROCESSOR_KEY=$(fetch_key processor)

echo "  admin:      ${ADMIN_KEY:0:20}..."
echo "  analyst:    ${ANALYST_KEY:0:20}..."
echo ""

# ── 1. No auth → 401 ─────────────────────────────────────────────
echo "1. Missing auth → 401"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$ENDPOINT/analyst/summary?period=7d")
assert_status "no auth" 401 "$STATUS"

# ── 2. Bad token → 401 ───────────────────────────────────────────
echo "2. Bad token → 401"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer bad_token_xyz" \
    "$ENDPOINT/analyst/summary?period=7d")
assert_status "bad token" 401 "$STATUS"

# ── 3. Agent views own data → 200 ────────────────────────────────
echo "3. Analyst views own wallet → 200"
RESP=$(curl -s -w "\n%{http_code}" \
    -H "Authorization: Bearer $ANALYST_KEY" \
    "$ENDPOINT/analyst/summary?period=7d")
STATUS=$(echo "$RESP" | tail -1)
BODY=$(echo "$RESP" | sed '$d')
assert_status "analyst own wallet" 200 "$STATUS"
echo "  Response: $(echo "$BODY" | python3 -m json.tool 2>/dev/null | head -20)"
echo ""

# ── 4. Agent views other agent → 403 ─────────────────────────────
echo "4. Analyst views newsletter wallet → 403"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $ANALYST_KEY" \
    "$ENDPOINT/newsletter/summary?period=7d")
assert_status "cross-agent denied" 403 "$STATUS"

# ── 5. Admin views any agent → 200 ───────────────────────────────
echo "5. Admin views analyst wallet → 200"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $ADMIN_KEY" \
    "$ENDPOINT/analyst/summary?period=7d")
assert_status "admin cross-view" 200 "$STATUS"

# ── 6. Non-existent agent → 404 ──────────────────────────────────
echo "6. Non-existent agent → 404"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $ADMIN_KEY" \
    "$ENDPOINT/nonexistent/summary?period=7d")
assert_status "unknown agent" 404 "$STATUS"

# ── 7. Invalid period → 400 ──────────────────────────────────────
echo "7. Invalid period → 400"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $ANALYST_KEY" \
    "$ENDPOINT/analyst/summary?period=3d")
assert_status "bad period" 400 "$STATUS"

# ── 8. Date range query → 200 ────────────────────────────────────
echo "8. Date range query → 200"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $ANALYST_KEY" \
    "$ENDPOINT/analyst/summary?from=2026-03-01&to=2026-03-15")
assert_status "date range" 200 "$STATUS"

# ── 9. Period variants ───────────────────────────────────────────
for P in 1d 30d; do
    echo "9. Period=$P → 200"
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $ANALYST_KEY" \
        "$ENDPOINT/analyst/summary?period=$P")
    assert_status "period=$P" 200 "$STATUS"
done

# ── 10. Each agent's own key ─────────────────────────────────────
echo "10. Each agent queries own wallet"
for PAIR in "gato:$GATO_KEY" "processor:$PROCESSOR_KEY" "newsletter:$NEWSLETTER_KEY" "research:$RESEARCH_KEY"; do
    AGENT="${PAIR%%:*}"
    KEY="${PAIR#*:}"
    RESP=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer $KEY" \
        "$ENDPOINT/$AGENT/summary?period=7d")
    STATUS=$(echo "$RESP" | tail -1)
    assert_status "$AGENT own wallet" 200 "$STATUS"
done

# ── 11. Full response structure check ────────────────────────────
echo "11. Response structure validation"
RESP=$(curl -s \
    -H "Authorization: Bearer $ADMIN_KEY" \
    "$ENDPOINT/analyst/summary?period=30d")

FIELDS="agent period balance_sats balance_usd_cents spent_sats spent_usd_cents calls avg_cost_per_call_sats models_used budget_utilization_pct spending_cap_sats spending_cap_window cap_hits_in_period governance_events_in_period trend_vs_previous_period"
MISSING=""
for F in $FIELDS; do
    if ! echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert '$F' in d" 2>/dev/null; then
        MISSING="$MISSING $F"
    fi
done
if [ -z "$MISSING" ]; then
    green "  PASS  all required fields present"
    PASS=$((PASS + 1))
else
    red   "  FAIL  missing fields:$MISSING"
    FAIL=$((FAIL + 1))
fi

echo ""
echo "════════════════════════════════════════"
echo "  Results: $PASS passed, $FAIL failed"
echo "════════════════════════════════════════"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
