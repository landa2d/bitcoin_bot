#!/bin/sh
# Fail loud if Supabase config is missing — never sed placeholders into a dead SPA (WS-24)
: "${SUPABASE_URL:?must be set}"
: "${SUPABASE_ANON_KEY:?must be set}"

# Inject Supabase config into the JS at runtime
sed -i "s|__SUPABASE_URL__|${SUPABASE_URL}|g" /srv/app.js
sed -i "s|__SUPABASE_ANON_KEY__|${SUPABASE_ANON_KEY}|g" /srv/app.js

# Start Caddy
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
