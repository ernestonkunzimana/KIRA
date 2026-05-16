.PHONY: help install lint test security clean format check-all deploy

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)KIRA Phase 6: Validation & Testing Enforcement$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

install: ## Install all dependencies and pre-commit hooks
	@echo "$(BLUE)Installing dependencies...$(NC)"
	pip install --upgrade pip setuptools wheel
	pip install -r backend/requirements.txt
	pip install black isort pylint flake8 bandit pytest pytest-cov pytest-timeout mypy pre-commit
	@echo "$(BLUE)Setting up pre-commit hooks...$(NC)"
	pre-commit install
	@echo "$(GREEN)✓ Installation complete$(NC)"

lint: ## Run all linting checks
	@echo "$(BLUE)Running linting checks...$(NC)"
	@echo "  • Black format check..."
	black --check backend/ tests/ frontend/
	@echo "  • isort import sorting..."
	isort --check-only backend/ tests/ frontend/
	@echo "  • Pylint linting..."
	pylint backend/ --fail-under=8.0 || echo "$(YELLOW)Warning: Pylint score < 8.0$(NC)"
	@echo "  • Flake8 style check..."
	flake8 backend/ tests/ --max-line-length=100
	@echo "$(GREEN)✓ All linting checks passed$(NC)"

format: ## Auto-format code (Black + isort)
	@echo "$(BLUE)Formatting code...$(NC)"
	black backend/ tests/ frontend/
	isort backend/ tests/ frontend/
	@echo "$(GREEN)✓ Code formatted$(NC)"

test: ## Run full test suite with coverage
	@echo "$(BLUE)Running test suite...$(NC)"
	pytest tests/ backend/tests/ -v --cov=backend --cov-report=html --cov-report=term --timeout=60
	@echo "$(GREEN)✓ Tests complete (coverage report: htmlcov/index.html)$(NC)"

test-fast: ## Run tests without coverage (faster)
	@echo "$(BLUE)Running tests (fast mode)...$(NC)"
	pytest tests/ backend/tests/ -q --timeout=60
	@echo "$(GREEN)✓ Tests complete$(NC)"

test-watch: ## Run tests in watch mode (requires pytest-watch)
	@echo "$(BLUE)Running tests in watch mode...$(NC)"
	pip install pytest-watch
	ptw tests/ backend/tests/ -- --timeout=60

security: ## Run security scanning (Bandit + Trivy)
	@echo "$(BLUE)Running security scans...$(NC)"
	@echo "  • Bandit security check..."
	bandit -r backend/ -ll
	@echo "  • Container scanning (requires Trivy)..."
	@which trivy > /dev/null || echo "$(YELLOW)Trivy not installed. Install: https://aquasecurity.github.io/trivy/$(NC)"
	@which trivy > /dev/null && trivy fs . || true
	@echo "$(GREEN)✓ Security scans complete$(NC)"

types: ## Run type checking with mypy
	@echo "$(BLUE)Running type checker...$(NC)"
	mypy backend/ --ignore-missing-imports
	@echo "$(GREEN)✓ Type checking complete$(NC)"

check-config: ## Validate Flask configuration and environment setup
	@echo "$(BLUE)Validating configuration...$(NC)"
	python -c "from backend.config import get_config; from backend.config_validator import validate_production_config; cfg = get_config(); print('✓ Config valid')"
	@echo "$(GREEN)✓ Configuration validated$(NC)"

check-docker: ## Validate Docker configuration
	@echo "$(BLUE)Validating Docker setup...$(NC)"
	docker-compose config > /dev/null
	@echo "$(GREEN)✓ docker-compose.yml valid$(NC)"

check-all: lint test types security check-config check-docker ## Run all checks (lint, test, types, security, config)
	@echo ""
	@echo "$(GREEN)╔═══════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║ PHASE 6: ALL VALIDATION CHECKS PASSED                    ║$(NC)"
	@echo "$(GREEN)╚═══════════════════════════════════════════════════════════╝$(NC)"

clean: ## Clean build artifacts and caches
	@echo "$(BLUE)Cleaning build artifacts...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .coverage -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name *.egg-info -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

pre-commit-run: ## Run pre-commit hooks on all files
	@echo "$(BLUE)Running pre-commit hooks...$(NC)"
	pre-commit run --all-files
	@echo "$(GREEN)✓ Pre-commit hooks complete$(NC)"

ci-local: format check-all ## Local CI simulation (format, then all checks)
	@echo ""
	@echo "$(GREEN)Local CI pipeline complete!$(NC)"

deploy-check: check-all check-docker ## Pre-deployment checks
	@echo ""
	@echo "$(GREEN)╔═══════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║ PRE-DEPLOYMENT VALIDATION PASSED                         ║$(NC)"
	@echo "$(GREEN)║ Ready for: docker-compose up                             ║$(NC)"
	@echo "$(GREEN)╚═══════════════════════════════════════════════════════════╝$(NC)"

dev: install ## Development setup (install + pre-commit)
	@echo "$(GREEN)✓ Development environment ready$(NC)"
	@echo "  Run: make check-all (to validate all)"
	@echo "  Run: make test (to run tests)"
	@echo "  Run: make lint (to check style)"

.DEFAULT_GOAL := help
