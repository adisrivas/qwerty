# Developer entry points. Run `make help` to list them.

.DEFAULT_GOAL := help
BACKEND := backend
FRONTEND := frontend

.PHONY: help setup lint test run run-backend run-frontend refresh-data docker-up docker-down openapi

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Install backend (uv) and frontend (npm) dependencies
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && npm ci

lint: ## Lint, format-check, type-check and verify layering on both sides
	cd $(BACKEND) && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports
	cd $(FRONTEND) && npm run lint && npm run typecheck && npm run format:check

test: ## Run backend and frontend test suites
	cd $(BACKEND) && uv run pytest
	cd $(FRONTEND) && npm test -- --run

run-backend: ## Start the API with auto-reload on :8000
	cd $(BACKEND) && uv run uvicorn app.main:app --reload --port 8000

run-frontend: ## Start the Vite dev server on :5173 (proxies /api to :8000)
	cd $(FRONTEND) && npm run dev

run: ## Start backend and frontend together (Ctrl-C stops both)
	$(MAKE) -j2 run-backend run-frontend

refresh-data: ## Re-download the January 2026 snapshot from Elexon
	cd $(BACKEND) && uv run python -m scripts.refresh_snapshot

openapi: ## Regenerate frontend API types from the backend OpenAPI schema
	cd $(BACKEND) && uv run python -c "import json; from app.main import create_app; print(json.dumps(create_app().openapi(), indent=2))" > ../$(FRONTEND)/openapi.json
	cd $(FRONTEND) && npx openapi-typescript openapi.json -o src/api/schema.d.ts && npx prettier --write src/api/schema.d.ts

docker-up: ## Build and start the full stack (frontend on :8080, backend on :8000)
	docker compose up --build

docker-down: ## Stop the stack
	docker compose down
