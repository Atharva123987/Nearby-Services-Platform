.DEFAULT_GOAL := help
.PHONY: help env up down logs ps restart clean install migrate seed backend-dev frontend-dev lint format typecheck test precommit

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

env: ## Create .env from .env.example (if missing)
	@test -f .env || cp .env.example .env

up: ## Build and start all services, waiting until healthy
	docker compose up -d --build --wait

down: ## Stop services (keeps volumes)
	docker compose down

clean: ## Stop services and delete volumes
	docker compose down -v

logs: ## Follow logs
	docker compose logs -f

ps: ## Service status
	docker compose ps

restart: down up ## Restart all services

install: ## Install backend + frontend deps and git hooks
	cd backend && uv sync
	cd frontend && npm ci
	uvx pre-commit install

migrate: ## Apply DB migrations (alembic upgrade head) inside the api container
	docker compose exec api alembic upgrade head

seed: ## Load dev seed data (200 services in Nashik + Mumbai); safe to re-run
	docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"' < db/seeds/0001_nashik_mumbai.sql

backend-dev: ## Run the API on the host with reload
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend-dev: ## Run Next.js on the host
	cd frontend && npm run dev

lint: ## Lint backend and frontend
	cd backend && uv run ruff check . && uv run black --check .
	cd frontend && npm run lint && npm run format:check

format: ## Auto-format backend and frontend
	cd backend && uv run ruff check --fix . && uv run black .
	cd frontend && npm run format

typecheck: ## mypy + tsc
	cd backend && uv run mypy
	cd frontend && npm run typecheck

test: ## Backend tests
	cd backend && uv run pytest

precommit: ## Run all pre-commit hooks on every file
	uvx pre-commit run --all-files
