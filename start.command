#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────
#  start.command — Double-click to start Market Advisor locally
# ───────────────────────────────────────────────────────────
set -euo pipefail

# cd to the directory where this script lives
cd "$(dirname "$0")"

# ── Colors ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'
BOLD='\033[1m'

info()  { printf "${CYAN}▸ %s${NC}\n" "$*"; }
ok()    { printf "${GREEN}✔ %s${NC}\n" "$*"; }
warn()  { printf "${YELLOW}⚠ %s${NC}\n" "$*"; }
fail()  { printf "${RED}✖ %s${NC}\n" "$*"; echo ""; read -rp "Press Enter to close…"; exit 1; }

echo ""
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}         MARKET ADVISOR LOCAL STARTUP${NC}"
echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ── Pre-flight checks ──────────────────────────────────────
info "Performing pre-flight checks..."

# Check Python
if ! command -v python3 >/dev/null 2>&1; then
    fail "python3 is not installed or not in PATH."
fi

# Check Node/NPM
if ! command -v npm >/dev/null 2>&1; then
    fail "npm/node is not installed or not in PATH."
fi

# Check backend .env exists
if [ ! -f "api/.env" ]; then
    if [ -f "api/.env.example" ]; then
        warn "api/.env not found. Copying from api/.env.example..."
        cp api/.env.example api/.env
    else
        fail "api/.env is missing and api/.env.example was not found."
    fi
fi

# Check frontend .env.local exists
if [ ! -f "web/.env.local" ]; then
    if [ -f "web/.env.local.example" ]; then
        warn "web/.env.local not found. Copying from web/.env.local.example..."
        cp web/.env.local.example web/.env.local
    elif [ -f ".env.example" ]; then
        warn "web/.env.local not found. Copying from .env.example..."
        cp .env.example web/.env.local
    else
        warn "web/.env.local not found. Application might need configuration."
    fi
fi

ok "Pre-flight checks passed."
echo ""

# ── Kill existing processes on ports 3000 and 8000 ────────
info "Checking ports 8000 and 3000..."

# Port 8000 (Backend)
PID_8000=$(lsof -t -i:8000 2>/dev/null || true)
if [ -n "$PID_8000" ]; then
    warn "Port 8000 is occupied. Stopping old backend (PID: $PID_8000)..."
    kill -9 "$PID_8000" 2>/dev/null || true
fi

# Port 3000 (Frontend)
PID_3000=$(lsof -t -i:3000 2>/dev/null || true)
if [ -n "$PID_3000" ]; then
    warn "Port 3000 is occupied. Stopping old frontend (PID: $PID_3000)..."
    kill -9 "$PID_3000" 2>/dev/null || true
fi

# ── Start Backend ──────────────────────────────────────────
info "Starting Python FastAPI Backend server..."
if [ ! -d "api/.venv" ]; then
    warn "Virtual environment 'api/.venv' not found. Creating..."
    python3 -m venv api/.venv
    info "Installing python dependencies..."
    api/.venv/bin/pip install -r api/requirements.txt
fi

# Run backend in background
cd api
source .venv/bin/activate
uvicorn main:app --port 8000 > ../backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# ── Start Frontend ─────────────────────────────────────────
info "Starting Next.js Frontend server..."
# Check node_modules
if [ ! -d "web/node_modules" ]; then
    warn "web/node_modules not found. Running npm install..."
    cd web
    npm install
    cd ..
fi

# Run frontend in background
cd web
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# ── Shutdown Trap ──────────────────────────────────────────
cleanup() {
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    info "Shutting down servers gracefully..."
    kill "$BACKEND_PID" 2>/dev/null || true
    kill "$FRONTEND_PID" 2>/dev/null || true
    rm -f backend.log frontend.log
    ok "Done. Bye!"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}
trap cleanup EXIT

# ── Wait for servers to become active ──────────────────────
info "Waiting for services to boot..."
sleep 3

# Simple health check loop
BACKEND_READY=false
for i in {1..10}; do
    if curl -s http://localhost:8000/health >/dev/null; then
        BACKEND_READY=true
        break
    fi
    sleep 1
done

if [ "$BACKEND_READY" = true ]; then
    ok "FastAPI Backend is online at http://localhost:8000"
else
    warn "FastAPI Backend is taking a while to boot. Check backend.log for details."
fi

# Open frontend in the default browser
ok "Next.js Frontend is online at http://localhost:3000"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}       🎉 MARKET ADVISOR IS RUNNING SUCCESSFULLY!${NC}"
echo -e "       Frontend: ${CYAN}http://localhost:3000${NC}"
echo -e "       Backend:  ${CYAN}http://localhost:8000${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
info "Opening application in browser..."
open http://localhost:3000

echo ""
echo -e "${BOLD}Press [Ctrl+C] to stop all servers and exit.${NC}"
echo ""

# Keep script running to show logs/stay active
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
    sleep 1
done
