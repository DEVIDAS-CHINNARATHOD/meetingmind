#!/usr/bin/env bash
# ── MeetingMind AI — Local Startup Script ─────────────────────
# Starts all services using the correct Python virtualenv.
# Usage: ./start.sh [backend|worker|frontend|all]

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
VENV="$BACKEND_DIR/.venv/bin"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

check_venv() {
  if [ ! -f "$VENV/python" ]; then
    echo -e "${RED}ERROR: Virtual environment not found at $VENV${NC}"
    echo "Run: python3 -m venv backend/.venv && source backend/.venv/bin/activate && pip install -r backend/requirements.txt"
    exit 1
  fi
}

free_port() {
  local port=$1
  if fuser "${port}/tcp" &>/dev/null; then
    echo -e "${YELLOW}⚠ Port ${port} in use — killing process...${NC}"
    fuser -k "${port}/tcp" 2>/dev/null
    sleep 1
    echo -e "${GREEN}✓ Port ${port} freed${NC}"
  fi
}

start_infra() {
  echo -e "${CYAN}▶ Starting Postgres + Redis...${NC}"
  docker compose up -d postgres redis
  echo -e "${GREEN}✓ Infrastructure running${NC}"
}

start_backend() {
  check_venv
  free_port 8000
  echo -e "${CYAN}▶ Starting FastAPI backend on :8000...${NC}"
  cd "$BACKEND_DIR"
  "$VENV/uvicorn" main:app --reload --port 8000
}

start_worker() {
  check_venv
  echo -e "${CYAN}▶ Starting Celery worker (concurrency=1, queues: ai,reports,bots)...${NC}"
  cd "$BACKEND_DIR"
  "$VENV/celery" -A workers.celery_app worker \
    --queues ai,reports,bots \
    --concurrency 1 \
    --loglevel info
}

start_frontend() {
  free_port 3000
  echo -e "${CYAN}▶ Starting Next.js frontend on :3000...${NC}"
  cd "$FRONTEND_DIR"
  npm run dev
}

CMD="${1:-all}"

case "$CMD" in
  infra)
    start_infra ;;
  backend)
    start_infra
    start_backend ;;
  worker)
    start_worker ;;
  frontend)
    start_frontend ;;
  all)
    echo -e "${YELLOW}━━━ MeetingMind AI — Starting All Services ━━━${NC}"
    start_infra
    echo ""
    echo -e "${YELLOW}Open 3 separate terminals and run:${NC}"
    echo -e "  ${GREEN}Terminal 1 (backend):${NC}  ./start.sh backend"
    echo -e "  ${GREEN}Terminal 2 (worker): ${NC}  ./start.sh worker"
    echo -e "  ${GREEN}Terminal 3 (frontend):${NC} ./start.sh frontend"
    echo ""
    echo -e "  ${CYAN}Frontend:${NC} http://localhost:3000"
    echo -e "  ${CYAN}API:     ${NC} http://localhost:8000"
    ;;
  *)
    echo "Usage: $0 [infra|backend|worker|frontend|all]"
    exit 1 ;;
esac
