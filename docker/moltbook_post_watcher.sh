#!/bin/bash
# Moltbook queue watcher.
# Polls workspace/moltbook_queue for .json files;
# performs POST/GET to Moltbook API and writes result to moltbook_queue/responses/<name>.result.json
# Supports: post_*.json (create post), comment_*.json (create comment), fetch_*.json (GET requests)

# NOTE: Do NOT use "set -e" here - transient curl/jq errors should not kill the watcher
QUEUE_DIR="${OPENCLAW_DATA_DIR:-/home/openclaw/.openclaw}/workspace/moltbook_queue"
RESPONSES_DIR="$QUEUE_DIR/responses"
API_BASE="https://www.moltbook.com/api/v1"
POLL_INTERVAL=5

mkdir -p "$QUEUE_DIR" "$RESPONSES_DIR" 2>/dev/null || true

log() { echo "[moltbook_watcher] $*" 2>/dev/null || true; }

process_file() {
    local f="$1"
    local base=$(basename "$f" .json)
    local result_file="$RESPONSES_DIR/${base}.result.json"
    log "processing: $f"

    if [ -z "$MOLTBOOK_API_TOKEN" ]; then
        echo '{"success":false,"error":"MOLTBOOK_API_TOKEN not set"}' > "$result_file" 2>/dev/null || true
        rm -f "$f" 2>/dev/null || true
        return
    fi

    if [[ "$base" == post_* ]]; then
        local payload
        payload=$(jq -c '{submolt: (.submolt // "bitcoin"), title: .title, content: .content}' "$f" 2>/dev/null) || true
        if [ -z "$payload" ]; then
            echo '{"success":false,"error":"invalid JSON or missing title/content"}' > "$result_file" 2>/dev/null || true
            rm -f "$f" 2>/dev/null || true
            return
        fi
        local output code body
        output=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/posts" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $MOLTBOOK_API_TOKEN" \
            -d "$payload" 2>/dev/null) || true
        code=$(echo "$output" | tail -n1)
        body=$(echo "$output" | sed '$d')
        if [ "$code" = "200" ] || [ "$code" = "201" ]; then
            echo "$body" > "$result_file" 2>/dev/null || true
        else
            (echo "$body" | jq -c '. + {success: false, error: ("HTTP " + "'"$code"'")}' 2>/dev/null) > "$result_file" 2>/dev/null || echo "{\"success\":false,\"error\":\"HTTP $code\"}" > "$result_file" 2>/dev/null || true
        fi
    elif [[ "$base" == comment_* ]]; then
        local postId
        postId=$(jq -r '.postId // ""' "$f" 2>/dev/null)
        if [ -z "$postId" ]; then
            echo '{"success":false,"error":"missing postId"}' > "$result_file" 2>/dev/null || true
            rm -f "$f" 2>/dev/null || true
            return
        fi
        local payload output code body
        payload=$(jq -c '{content: .content}' "$f" 2>/dev/null) || true
        if [ -z "$payload" ]; then
            echo '{"success":false,"error":"invalid JSON or missing content"}' > "$result_file" 2>/dev/null || true
            rm -f "$f" 2>/dev/null || true
            return
        fi
        output=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE/posts/$postId/comments" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $MOLTBOOK_API_TOKEN" \
            -d "$payload" 2>/dev/null) || true
        code=$(echo "$output" | tail -n1)
        body=$(echo "$output" | sed '$d')
        if [ "$code" = "200" ] || [ "$code" = "201" ]; then
            echo "$body" > "$result_file" 2>/dev/null || true
        else
            (echo "$body" | jq -c '. + {success: false, error: ("HTTP " + "'"$code"'")}' 2>/dev/null) > "$result_file" 2>/dev/null || echo "{\"success\":false,\"error\":\"HTTP $code\"}" > "$result_file" 2>/dev/null || true
        fi
    elif [[ "$base" == fetch_* ]]; then
        # GET request: {"endpoint":"posts","params":{"sort":"new","limit":10}}
        local endpoint params_json query_string url output code body
        endpoint=$(jq -r '.endpoint // "posts"' "$f" 2>/dev/null)
        if [ -z "$endpoint" ]; then
            echo '{"success":false,"error":"missing endpoint"}' > "$result_file" 2>/dev/null || true
            rm -f "$f" 2>/dev/null || true
            return
        fi
        # Build query string from params object
        params_json=$(jq -r '.params // {}' "$f" 2>/dev/null)
        query_string=$(echo "$params_json" | jq -r 'to_entries | map("\(.key)=\(.value|tostring)") | join("&")' 2>/dev/null) || true
        if [ -n "$query_string" ]; then
            url="$API_BASE/$endpoint?$query_string"
        else
            url="$API_BASE/$endpoint"
        fi
        output=$(curl -s -w "\n%{http_code}" -X GET "$url" \
            -H "Authorization: Bearer $MOLTBOOK_API_TOKEN" 2>/dev/null) || true
        code=$(echo "$output" | tail -n1)
        body=$(echo "$output" | sed '$d')
        if [ "$code" = "200" ]; then
            echo "$body" > "$result_file" 2>/dev/null || true
        else
            (echo "$body" | jq -c '. + {success: false, error: ("HTTP " + "'"$code"'")}' 2>/dev/null) > "$result_file" 2>/dev/null || echo "{\"success\":false,\"error\":\"HTTP $code\"}" > "$result_file" 2>/dev/null || true
        fi
    else
        echo '{"success":false,"error":"unknown type (use post_*, comment_*, or fetch_*)"}' > "$result_file" 2>/dev/null || true
    fi
    rm -f "$f" 2>/dev/null || true
    log "done: $base -> $result_file"
}

log "starting (queue=$QUEUE_DIR)"
shopt -s nullglob
while true; do
    for f in "$QUEUE_DIR"/*.json; do
        [ -f "$f" ] || continue
        process_file "$f"
    done
    sleep "$POLL_INTERVAL"
done
