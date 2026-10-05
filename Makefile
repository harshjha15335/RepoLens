.PHONY: setup dev backend frontend test test-backend test-frontend lint typecheck evaluate docker-up docker-down clean

# ─── Setup ─────────────────────────────────────────────────────

setup:
	cd backend && pip install -e ".[dev]"
	cd frontend && npm install

# ─── Development ───────────────────────────────────────────────

dev:
	@echo "Starting backend and frontend..."
	$(MAKE) backend &
	$(MAKE) frontend &
	wait

backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

# ─── Testing ───────────────────────────────────────────────────

test: test-backend test-frontend

test-backend:
	cd backend && python -m pytest tests/ -v --tb=short

test-frontend:
	cd frontend && npm test -- --passWithNoTests

# ─── Linting ───────────────────────────────────────────────────

lint:
	cd backend && ruff check app/ tests/
	cd frontend && npx eslint . --max-warnings 0 || true

typecheck:
	cd frontend && npx tsc --noEmit || true

# ─── Evaluation ────────────────────────────────────────────────

evaluate:
	cd backend && python -m app.services.evaluation.runner

# ─── Docker ────────────────────────────────────────────────────

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

# ─── Cleanup ───────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/data/ frontend/.next/ frontend/out/
