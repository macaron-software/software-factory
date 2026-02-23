.PHONY: setup run stop logs clean dev test install-hooks install-deps quality quality-full test-coverage test-skills

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

# Git Hooks + Quality Tools
install-hooks:
	@echo "Installing Git hooks + quality tools..."
	@bash scripts/quality/install_hooks.sh

install-deps:
	@echo "Installing development dependencies..."
	@bash scripts/quality/install_dependencies.sh

quality:
	@echo "Running quality checks on staged files..."
	@bash scripts/quality/pre-commit || true

quality-full:
	@echo "Running full quality scan (all files)..."
	@command -v ruff &> /dev/null && ruff check . || echo "⚠️  Ruff not installed"
	@command -v eslint &> /dev/null && eslint . --ext .js,.ts,.jsx,.tsx || echo "⚠️  ESLint not installed"
	@command -v bandit &> /dev/null && bandit -r platform/ skills_injection/ || echo "⚠️  Bandit not installed"

test-coverage:
	@echo "Running tests with coverage report..."
	@PYTHONPATH=$$(pwd) pytest --cov=platform --cov=skills_injection --cov-report=html --cov-report=term
	@echo ""
	@echo "Coverage report generated: htmlcov/index.html"

# Skills Injection Testing
test-skills:
	@echo "Testing skills injection with real missions..."
	@PYTHONPATH=$$(pwd) python3 -m skills_injection.test_real_missions

test-skills-verbose:
	@echo "Testing skills injection (verbose)..."
	@PYTHONPATH=$$(pwd) python3 -m skills_injection.test_real_missions --verbose

load-demo-skills:
	@echo "Loading demo skills from skills/ directory..."
	@PYTHONPATH=$$(pwd) python3 -m skills_injection.load_demo_skills

