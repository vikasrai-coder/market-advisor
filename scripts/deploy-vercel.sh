#!/usr/bin/env bash
# Deploy Market Advisor to Vercel (requires: bunx or vercel CLI logged in)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Dynamic Vercel CLI resolution: check global vercel -> bunx -> npx
if [ -z "${VERCEL_CMD:-}" ]; then
  if command -v vercel >/dev/null 2>&1; then
    VERCEL="vercel"
  elif command -v bunx >/dev/null 2>&1; then
    VERCEL="bunx vercel@54.2.0"
  else
    VERCEL="npx -y vercel@54.2.0"
  fi
else
  VERCEL="$VERCEL_CMD"
fi

add_env() {
  local dir="$1" key="$2" val="$3"
  (cd "$dir" && printf '%s' "$val" | $VERCEL env add "$key" production --force --yes) >/dev/null 2>&1 || true
}

echo "==> Deploying API..."
cd "$ROOT/api"
$VERCEL link --yes 2>/dev/null || true
[[ -f .env ]] && while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" =~ ^# ]] && continue
  k="${line%%=*}"; v="${line#*=}"
  case "$k" in API_HOST|API_PORT|ADMIN_EMAIL|ADMIN_PASSWORD) continue ;; esac
  add_env "$ROOT/api" "$k" "$v"
done < .env
API_URL=$($VERCEL deploy . --prod --yes 2>&1 | grep -Eo 'https://[a-z0-9.-]+\.vercel\.app' | tail -1)
echo "API: $API_URL"

echo "==> Deploying Web..."
cd "$ROOT/web"
$VERCEL link --yes 2>/dev/null || true
[[ -f .env.local ]] && while IFS= read -r line || [[ -n "$line" ]]; do
  [[ "$line" =~ ^NEXT_PUBLIC_ ]] || continue
  k="${line%%=*}"; v="${line#*=}"
  [[ "$k" == "NEXT_PUBLIC_API_URL" ]] && v="$API_URL"
  add_env "$ROOT/web" "$k" "$v"
done < .env.local
add_env "$ROOT/api" "CORS_ORIGINS" "${WEB_URL:-},http://localhost:3000"
WEB_URL=$($VERCEL deploy . --prod --yes 2>&1 | grep -Eo 'https://[a-z0-9.-]+\.vercel\.app' | tail -1)
echo "Web: $WEB_URL"
echo "Add Supabase Auth redirect URLs: $WEB_URL/**"
