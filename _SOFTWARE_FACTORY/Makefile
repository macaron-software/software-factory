.PHONY: setup run stop logs clean dev test

# Quick start
setup:
	@test -f .env || (cp .env.example .env && echo "Created .env -- edit it with your LLM API key")
	@echo "Run "make run" to start the platform"

run:
	docker compose up -d --build
	@echo ""
	@echo "Macaron Software Factory is starting..."
	@echo "   Open http://localhost:8090 in your browser"
	@echo "   Run "make logs" to see output"

stop:
	docker compose down

logs:
	docker compose logs -f platform

clean:
	docker compose down -v
	@echo "Removed containers and volumes"

# Development (without Docker)
dev:
	PYTHONPATH=$$(pwd) python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none --log-level info

test:
	PYTHONPATH=$$(pwd) python3 -m pytest tests/test_cache.py tests/test_auto_heal.py tests/test_vectors.py tests/test_i18n.py tests/test_demo.py -v
