.PHONY: up down logs shell test lint dev clean frontend frontend-bench frontend-quick

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

shell:
	docker compose exec api bash

test:
	docker compose exec api pytest tests/ -v

test-cov:
	docker compose exec api pytest tests/ -v --cov=src --cov-report=term-missing

test-integration:
	docker compose exec api pytest tests/integration/ -v

test-unit:
	docker compose exec api pytest tests/unit/ -v

lint:
	docker compose exec api ruff check src/

lint-fix:
	docker compose exec api ruff check --fix src/

format:
	docker compose exec api black src/ tests/

dev:
	docker compose up --watch

clean:
	docker compose down -v
	docker system prune -f

# Frontend targets
frontend:
	cd tauri_frontend/event_agent_frontend && npm run dev

frontend-full:
	cd tauri_frontend/event_agent_frontend && npm run tauri dev

frontend-bench:
	@echo "=== Frontend Build Benchmarks ==="
	@echo ""
	@echo "--- Vite dev server (JS only, no Rust) ---"
	@time (cd tauri_frontend/event_agent_frontend && timeout 10 npm run dev 2>&1 | head -5 || true)
	@echo ""
	@echo "--- Rust incremental build (cached) ---"
	@time (cd tauri_frontend/event_agent_frontend/src-tauri && cargo build 2>&1 | tail -1)
	@echo ""
	@echo "--- Rust fresh build (target deleted) ---"
	@rm -rf tauri_frontend/event_agent_frontend/src-tauri/target
	@time (cd tauri_frontend/event_agent_frontend/src-tauri && cargo build 2>&1 | tail -1)

frontend-quick:
	@echo "=== Frontend Build Benchmarks ==="
	@echo ""
	@echo "1. Vite dev server (JS only, no Rust)"
	@cd tauri_frontend/event_agent_frontend && time npm run dev & VITE_PID=$$!; sleep 5; kill $$VITE_PID 2>/dev/null; wait $$VITE_PID 2>/dev/null
	@echo ""
	@echo "2. Rust incremental build (cached)"
	@cd tauri_frontend/event_agent_frontend/src-tauri && time cargo build 2>&1 | tail -1
	@echo ""
	@echo "3. Rust fresh build (target deleted)"
	@rm -rf tauri_frontend/event_agent_frontend/src-tauri/target
	@cd tauri_frontend/event_agent_frontend/src-tauri && time cargo build 2>&1 | tail -1
