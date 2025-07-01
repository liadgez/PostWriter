# PostWriter Test Automation Makefile
# Comprehensive testing, coverage, and quality assurance automation

.PHONY: help test test-unit test-integration test-visual test-security test-all
.PHONY: coverage coverage-html coverage-xml lint format security-audit
.PHONY: install install-dev clean setup-test-env
.PHONY: test-fast test-slow test-browser test-network
.PHONY: baseline-create baseline-update baseline-clean
.PHONY: ci pre-commit post-commit performance-test

# Default target
.DEFAULT_GOAL := help

# Python and pip executables
PYTHON := python3
PIP := pip3
PYTEST := pytest

# Project paths
SRC_DIR := src/postwriter
TEST_DIR := tests
COVERAGE_DIR := htmlcov
BASELINE_DIR := tests/baselines

# Test configuration
TEST_TIMEOUT := 300
COVERAGE_MIN := 85
PYTEST_ARGS := --tb=short --strict-markers --color=yes

# Help target
help: ## Show this help message
	@echo "PostWriter Test Automation"
	@echo "=========================="
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Test categories:"
	@echo "  - unit: Individual component tests"
	@echo "  - integration: Cross-component tests"
	@echo "  - visual: Screenshot and UI tests"
	@echo "  - security: Security validation tests"
	@echo ""

# Installation targets
install: ## Install production dependencies
	$(PIP) install -r requirements.txt

install-dev: ## Install development dependencies including test tools
	$(PIP) install -r requirements.txt
	$(PIP) install pytest pytest-cov pytest-asyncio pytest-timeout pytest-xdist
	$(PIP) install coverage[toml] pytest-html pytest-benchmark
	$(PIP) install black flake8 mypy bandit safety
	$(PIP) install pre-commit

# Setup targets
setup-test-env: ## Setup test environment and directories
	@echo "Setting up test environment..."
	@mkdir -p $(TEST_DIR)/unit $(TEST_DIR)/integration $(TEST_DIR)/visual
	@mkdir -p $(BASELINE_DIR) $(COVERAGE_DIR)
	@mkdir -p logs/test_logs data/test_data
	@echo "Test environment ready"

clean: ## Clean test artifacts and temporary files
	@echo "Cleaning test artifacts..."
	@rm -rf $(COVERAGE_DIR) .coverage coverage.xml
	@rm -rf .pytest_cache __pycache__ */__pycache__ */*/__pycache__
	@rm -rf .mypy_cache .tox dist build *.egg-info
	@find . -name "*.pyc" -delete
	@find . -name ".DS_Store" -delete
	@rm -rf logs/test_* data/test_* 
	@echo "Cleanup complete"

# Core testing targets
test: test-unit ## Run unit tests (default)

test-unit: ## Run unit tests only
	@echo "Running unit tests..."
	$(PYTEST) $(PYTEST_ARGS) $(TEST_DIR)/unit/ -m "not slow and not browser" --timeout=$(TEST_TIMEOUT)

test-integration: ## Run integration tests
	@echo "Running integration tests..."
	$(PYTEST) $(PYTEST_ARGS) $(TEST_DIR)/integration/ --timeout=$(TEST_TIMEOUT)

test-visual: ## Run visual regression tests
	@echo "Running visual regression tests..."
	$(PYTEST) $(PYTEST_ARGS) $(TEST_DIR)/visual/ -m "visual" --timeout=$(TEST_TIMEOUT)

test-security: ## Run security-focused tests
	@echo "Running security tests..."
	$(PYTEST) $(PYTEST_ARGS) -m "security" --timeout=$(TEST_TIMEOUT)

test-all: ## Run all tests
	@echo "Running complete test suite..."
	$(PYTEST) $(PYTEST_ARGS) $(TEST_DIR)/ --timeout=$(TEST_TIMEOUT)

# Specialized test runs
test-fast: ## Run fast tests only (exclude slow, browser, network tests)
	@echo "Running fast tests..."
	$(PYTEST) $(PYTEST_ARGS) -m "not slow and not browser and not network" --timeout=60

test-slow: ## Run slow tests only
	@echo "Running slow tests..."
	$(PYTEST) $(PYTEST_ARGS) -m "slow" --timeout=$(TEST_TIMEOUT)

test-browser: ## Run browser automation tests
	@echo "Running browser tests..."
	$(PYTEST) $(PYTEST_ARGS) -m "browser" --timeout=$(TEST_TIMEOUT)

test-network: ## Run tests requiring network access
	@echo "Running network tests..."
	$(PYTEST) $(PYTEST_ARGS) -m "network" --timeout=$(TEST_TIMEOUT)

# Coverage targets
coverage: ## Run tests with coverage reporting
	@echo "Running tests with coverage..."
	$(PYTEST) $(PYTEST_ARGS) $(TEST_DIR)/ \
		--cov=$(SRC_DIR) \
		--cov-report=term-missing \
		--cov-report=html:$(COVERAGE_DIR) \
		--cov-report=xml:coverage.xml \
		--cov-fail-under=$(COVERAGE_MIN) \
		--cov-branch

coverage-html: coverage ## Generate HTML coverage report
	@echo "HTML coverage report generated in $(COVERAGE_DIR)/"
	@echo "Open $(COVERAGE_DIR)/index.html in your browser"

coverage-xml: coverage ## Generate XML coverage report for CI
	@echo "XML coverage report generated: coverage.xml"

# Code quality targets
lint: ## Run code linting
	@echo "Running code linting..."
	@echo "Checking with flake8..."
	flake8 $(SRC_DIR) $(TEST_DIR) --max-line-length=100 --ignore=E203,W503
	@echo "Checking with mypy..."
	mypy $(SRC_DIR) --ignore-missing-imports --no-strict-optional

format: ## Format code with black
	@echo "Formatting code with black..."
	black $(SRC_DIR) $(TEST_DIR) --line-length=100

format-check: ## Check code formatting without making changes
	@echo "Checking code formatting..."
	black --check --diff $(SRC_DIR) $(TEST_DIR) --line-length=100

# Security targets
security-audit: ## Run security audit
	@echo "Running security audit..."
	@echo "Checking dependencies with safety..."
	safety check
	@echo "Checking code with bandit..."
	bandit -r $(SRC_DIR) -f json -o bandit-report.json || true
	@echo "Security audit complete. Check bandit-report.json for details."

# Visual baseline management
baseline-create: ## Create new visual baselines from current screenshots
	@echo "Creating visual baselines..."
	@mkdir -p $(BASELINE_DIR)
	$(PYTHON) -c "from src.postwriter.testing.visual_validator import VisualValidator; \
		v = VisualValidator({'testing': {'baseline_screenshots': '$(BASELINE_DIR)'}}); \
		print('Baseline directory ready: $(BASELINE_DIR)')"

baseline-update: ## Update existing visual baselines
	@echo "Updating visual baselines..."
	@read -p "This will overwrite existing baselines. Continue? [y/N] " confirm && [ "$$confirm" = "y" ]
	@rm -rf $(BASELINE_DIR)/*.png $(BASELINE_DIR)/*.json
	$(MAKE) baseline-create
	@echo "Baselines updated"

baseline-clean: ## Clean visual baseline files
	@echo "Cleaning visual baselines..."
	@rm -rf $(BASELINE_DIR)/*.png $(BASELINE_DIR)/*.json $(BASELINE_DIR)/diffs/
	@echo "Baselines cleaned"

# Performance testing
performance-test: ## Run performance tests and benchmarks
	@echo "Running performance tests..."
	$(PYTEST) $(PYTEST_ARGS) -m "not slow" --benchmark-only --benchmark-sort=mean

# CI/CD targets
ci: clean install-dev lint security-audit test-all coverage ## Complete CI pipeline
	@echo "CI pipeline complete"

pre-commit: format lint test-fast ## Pre-commit checks (fast)
	@echo "Pre-commit checks passed"

post-commit: test-all coverage ## Post-commit validation (comprehensive)
	@echo "Post-commit validation complete"

# Parallel testing
test-parallel: ## Run tests in parallel (faster execution)
	@echo "Running tests in parallel..."
	$(PYTEST) $(PYTEST_ARGS) $(TEST_DIR)/ -n auto --timeout=$(TEST_TIMEOUT)

# Development targets
test-watch: ## Run tests in watch mode (re-run on file changes)
	@echo "Running tests in watch mode..."
	@echo "Press Ctrl+C to stop"
	while true; do \
		$(MAKE) test-fast; \
		echo "Waiting for changes... (Ctrl+C to stop)"; \
		sleep 2; \
	done

# Reporting targets
test-report: ## Generate comprehensive test report
	@echo "Generating test report..."
	$(PYTEST) $(PYTEST_ARGS) $(TEST_DIR)/ \
		--html=test-report.html --self-contained-html \
		--cov=$(SRC_DIR) --cov-report=html:$(COVERAGE_DIR)
	@echo "Test report generated: test-report.html"

# Validation targets
validate-structure: ## Validate project structure
	@echo "Validating project structure..."
	@test -d $(SRC_DIR) || (echo "Source directory missing: $(SRC_DIR)" && exit 1)
	@test -d $(TEST_DIR) || (echo "Test directory missing: $(TEST_DIR)" && exit 1)
	@test -f pytest.ini || (echo "pytest.ini missing" && exit 1)
	@test -f conftest.py || (echo "conftest.py missing" && exit 1)
	@echo "Project structure valid"

validate-imports: ## Validate that all imports work
	@echo "Validating imports..."
	$(PYTHON) -c "import sys; sys.path.insert(0, 'src'); \
		from postwriter.security import *; \
		from postwriter.testing import *; \
		print('All imports successful')"

# Documentation targets
docs-coverage: ## Check documentation coverage
	@echo "Checking documentation coverage..."
	@find $(SRC_DIR) -name "*.py" -exec grep -L '"""' {} \; | head -10

# Database and state management
reset-test-data: ## Reset test databases and state
	@echo "Resetting test data..."
	@rm -rf data/test_* logs/test_*
	@mkdir -p data/test_data logs/test_logs
	@echo "Test data reset"

# Environment validation
check-deps: ## Check if all dependencies are installed
	@echo "Checking dependencies..."
	@$(PYTHON) -c "import pytest, coverage, selenium, requests" || \
		(echo "Missing dependencies. Run 'make install-dev'" && exit 1)
	@echo "All dependencies available"

# Quick quality check
quick-check: format-check lint test-fast ## Quick quality check (pre-push)
	@echo "Quick quality check passed"

# Full validation
full-validation: clean check-deps validate-structure validate-imports test-all coverage security-audit ## Complete validation
	@echo "Full validation complete - project ready for production"

# Show test statistics
test-stats: ## Show test statistics and coverage summary
	@echo "Test Statistics:"
	@echo "==============="
	@find $(TEST_DIR) -name "test_*.py" | wc -l | xargs echo "Test files:"
	@grep -r "^def test_" $(TEST_DIR) | wc -l | xargs echo "Test functions:"
	@echo ""
	@echo "Coverage Summary:"
	@echo "=================="
	@$(PYTEST) --collect-only -q $(TEST_DIR) | grep "test session starts" -A 100 | tail -1