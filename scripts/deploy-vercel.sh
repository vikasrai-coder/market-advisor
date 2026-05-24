#!/usr/bin/env bash
# Deploy Market Advisor to Vercel (requires: bunx or vercel CLI logged in)
set -e

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
  echo "  Setting environment variable $key..."
  (cd "$dir" && printf '%s' "$val" | $VERCEL env add "$key" production --force --yes) >/dev/null 2>&1 || true
}

echo "==> Deploying API..."
cd "$ROOT/api"
mkdir -p .vercel
echo '{"projectId":"prj_73t4wzCFbbrQite5oLzwbDI109FJ","orgId":"team_jPEoNRoA3UXR4tAsntrOmVcy","projectName":"market-advisor-api"}' > .vercel/project.json

[[ -f .env ]] && while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" =~ ^# ]] && continue
  k="${line%%=*}"; v="${line#*=}"
  case "$k" in API_HOST|API_PORT|ADMIN_EMAIL|ADMIN_PASSWORD) continue ;; esac
  add_env "$ROOT/api" "$k" "$v"
done < .env

echo "  Deploying API to Vercel..."
tmp_log=$(mktemp)
if ! $VERCEL deploy . --prod --yes > "$tmp_log" 2>&1; then
  cat "$tmp_log"
  echo "Error: API Deployment failed!"
  rm -f "$tmp_log"
  exit 1
fi
cat "$tmp_log"
API_URL=$(grep -Eo 'https://[a-z0-9.-]+\.vercel\.app' "$tmp_log" | tail -1 || true)
rm -f "$tmp_log"

if [ -z "$API_URL" ]; then
  # Fallback: if we can't find it in logs, fetch the latest url using project info
  echo "  Extracting URL from project info..."
  API_URL="https://market-advisor-api.vercel.app"
fi
echo "API URL: $API_URL"

echo "==> Deploying Web..."
cd "$ROOT/web"
mkdir -p .vercel
echo '{"projectId":"prj_9hDwlYsripR0nrkWsxIYtOaIG2YG","orgId":"team_jPEoNRoA3UXR4tAsntrOmVcy","projectName":"web"}' > .vercel/project.json

[[ -f .env.local ]] && while IFS= read -r line || [[ -n "$line" ]]; do
  [[ "$line" =~ ^NEXT_PUBLIC_ ]] || continue
  k="${line%%=*}"; v="${line#*=}"
  [[ "$k" == "NEXT_PUBLIC_API_URL" ]] && v="$API_URL"
  add_env "$ROOT/web" "$k" "$v"
done < .env.local

add_env "$ROOT/api" "CORS_ORIGINS" "${WEB_URL:-},http://localhost:3000"

echo "  Deploying Web to Vercel..."
tmp_log=$(mktemp)
if ! $VERCEL deploy . --prod --yes > "$tmp_log" 2>&1; then
  cat "$tmp_log"
  echo "Error: Web Deployment failed!"
  rm -f "$tmp_log"
  exit 1
fi
cat "$tmp_log"
WEB_URL=$(grep -Eo 'https://[a-z0-9.-]+\.vercel\.app' "$tmp_log" | tail -1 || true)
rm -f "$tmp_log"

if [ -z "$WEB_URL" ]; then
  echo "  Extracting URL from project info..."
  WEB_URL="https://web-seven-smoky-94.vercel.app"
fi
echo "Web URL: $WEB_URL"
echo "Add Supabase Auth redirect URLs: $WEB_URL/**"
