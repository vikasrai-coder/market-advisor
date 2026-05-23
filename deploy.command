#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────
#  deploy.command — Double-click to push to GitHub → Vercel
# ───────────────────────────────────────────────────────────
set -euo pipefail

# cd to the directory where this script lives
cd "$(dirname "$0")"

# ── Colors ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { printf "${CYAN}▸ %s${NC}\n" "$*"; }
ok()    { printf "${GREEN}✔ %s${NC}\n" "$*"; }
warn()  { printf "${YELLOW}⚠ %s${NC}\n" "$*"; }
fail()  { printf "${RED}✖ %s${NC}\n" "$*"; echo ""; read -rp "Press Enter to close…"; exit 1; }

# ── Pre-flight checks ──────────────────────────────────────
command -v git >/dev/null 2>&1 || fail "git is not installed"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || fail "Not inside a git repository"
cd "$REPO_ROOT"

BRANCH="$(git branch --show-current)"
[ -z "$BRANCH" ] && fail "Detached HEAD — checkout a branch first"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "Market Advisor — Deploy to GitHub + Vercel"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
info "Repository : $REPO_ROOT"
info "Branch     : $BRANCH"
info "Remote     : $(git remote get-url origin 2>/dev/null || echo 'none')"
echo ""

# ── Check for changes ──────────────────────────────────────
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    warn "Working tree is clean — nothing to deploy."
    echo ""
    read -rp "Press Enter to close…"
    exit 0
fi

# ── Show what will be committed ────────────────────────────
info "Changes to be committed:"
echo ""
git status --short
echo ""

# ── Commit message ─────────────────────────────────────────
printf "${YELLOW}Enter commit message (or press Enter for auto): ${NC}"
read -r COMMIT_MSG
[ -z "$COMMIT_MSG" ] && COMMIT_MSG="deploy: update $(date '+%Y-%m-%d %H:%M')"

# ── Stage all changes ──────────────────────────────────────
info "Staging all changes..."
git add -A
ok "Staged"

# ── Commit ─────────────────────────────────────────────────
info "Committing: \"$COMMIT_MSG\""
git commit -m "$COMMIT_MSG"
ok "Committed"

# ── Push to GitHub ─────────────────────────────────────────
info "Pushing to origin/$BRANCH..."
git push origin "$BRANCH"
ok "Pushed to GitHub"

# ── Summary ────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "Deploy complete!"
info "GitHub  : https://github.com/vikasrai-coder/market-advisor/tree/$BRANCH"
info "Vercel will auto-deploy from the push."
info "Check   : https://vercel.com/dashboard"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -rp "Press Enter to close…"
