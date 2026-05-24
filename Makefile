# ╔══════════════════════════════════════════════════════════════╗
# ║  MeetingMind AI — Makefile                                  ║
# ╚══════════════════════════════════════════════════════════════╝

.PHONY: help setup dev build prod stop clean logs migrate test lint

# ── Defaults ──────────────────────────────────────────────────

help: ## Show this help
	@awk 'BEGIN{FS=":.*##"} /^[a-zA-Z_-]+:.*##/{printf "\033[36m%-18s\033[0m %s\n",$$1,$$2}' $(MAKEFILE_LIST)

# ── Setup ─────────────────────────────────────────────────────

setup: ## First-time setup: copy env files
	@[ -f backend/.env ] || (cp backend/.env.example backend/.env && echo "✅ Created backend/.env — fill in your GROQ_API_KEY")
	@[ -f frontend/.env.local ] || (cp frontend/.env.example frontend/.env.local && echo "✅ Created frontend/.env.local — fill in your CLERK keys")
	@echo "\n📋 Next steps:"
	@echo "  1. Edit backend/.env   → set GROQ_API_KEY, SECRET_KEY, JWT_SECRET"
	@echo "  2. Edit frontend/.env.local → set CLERK_PUBLISHABLE_KEY, CLERK_SECRET_KEY"
	@echo "  3. Run: make dev"

# ── Development ───────────────────────────────────────────────

dev: ## Start all services in development mode
	docker compose up --build

dev-bg: ## Start all services in background
	docker compose up --build -d

dev-debug: ## Start with Flower monitoring on :5555
	docker compose --profile debug up --build

# ── Production ────────────────────────────────────────────────

prod: ## Start in production mode with NGINX
	docker compose --profile production up --build -d

# ── Individual services ────────────────────────────────────────

api: ## Start only backend API + deps
	docker compose up --build postgres redis api worker-ai worker-reports

frontend: ## Start only frontend
	docker compose up --build frontend

workers: ## Start all Celery workers
	docker compose up --build worker-ai worker-reports worker-bots

# ── Database ──────────────────────────────────────────────────

migrate: ## Run Alembic migrations
	docker compose exec api alembic upgrade head

migrate-new: ## Create a new migration (MSG="description")
	docker compose exec api alembic revision --autogenerate -m "$(MSG)"

migrate-down: ## Rollback last migration
	docker compose exec api alembic downgrade -1

db-shell: ## Open PostgreSQL shell
	docker compose exec postgres psql -U postgres meetingmind

# ── Logs ──────────────────────────────────────────────────────

logs: ## Tail all logs
	docker compose logs -f

logs-api: ## Tail API logs
	docker compose logs -f api

logs-worker: ## Tail AI worker logs
	docker compose logs -f worker-ai

logs-bots: ## Tail bot worker logs
	docker compose logs -f worker-bots

logs-frontend: ## Tail frontend logs
	docker compose logs -f frontend

# ── Testing ───────────────────────────────────────────────────

test: ## Run backend tests
	docker compose exec api pytest tests/ -v

test-local: ## Run backend tests locally (no Docker)
	cd backend && pytest tests/ -v

type-check: ## TypeScript type check frontend
	cd frontend && npm run type-check

lint: ## Lint frontend
	cd frontend && npm run lint

# ── Maintenance ───────────────────────────────────────────────

stop: ## Stop all services
	docker compose down

clean: ## Stop and remove volumes (WARNING: deletes all data)
	docker compose down -v --remove-orphans
	@echo "⚠️  All data volumes removed"

ps: ## Show running containers
	docker compose ps

health: ## Check API health
	@curl -s http://localhost:8000/api/health | python3 -m json.tool

# ── Local development (no Docker) ─────────────────────────────

local-backend: ## Run backend locally
	cd backend && uvicorn main:app --reload --port 8000

local-worker: ## Run Celery AI worker locally
	cd backend && celery -A workers.celery_app worker --queues ai --concurrency 1 --loglevel info

local-frontend: ## Run frontend locally
	cd frontend && npm run dev

local-all: ## Run backend + worker + frontend in parallel (requires tmux)
	tmux new-session -d -s mm -n api   'cd backend && uvicorn main:app --reload'
	tmux new-window  -t mm -n worker   'cd backend && celery -A workers.celery_app worker -Q ai --concurrency 1 -l info'
	tmux new-window  -t mm -n frontend 'cd frontend && npm run dev'
	tmux attach -t mm
