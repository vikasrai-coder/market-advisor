#!/usr/bin/env bash
# Deploy Market Advisor API + Web to Vercel (requires: npx vercel login)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Deploying API (Python)..."
cd "$ROOT/api"
API_URL=$(npx vercel@latest deploy --prod --yes 2>&1 | tail -1)
echo "API deployed: $API_URL"

echo "==> Deploying Web (Next.js)..."
cd "$ROOT/web"
export NEXT_PUBLIC_API_URL="${API_URL}"
npx vercel@latest deploy --prod --yes \
  --env "NEXT_PUBLIC_API_URL=$API_URL" \
  --env "NEXT_PUBLIC_SUPABASE_URL=${NEXT_PUBLIC_SUPABASE_URL:-}" \
  --env "NEXT_PUBLIC_SUPABASE_ANON_KEY=${NEXT_PUBLIC_SUPABASE_ANON_KEY:-}"

echo ""
echo "Add to Supabase Auth > URL Configuration:"
echo "  Site URL: <your-web-vercel-url>"
echo "  Redirect URLs: <your-web-vercel-url>/**"
