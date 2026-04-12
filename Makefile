# Makefile - Commandes standardisées pour UI-Pro

.PHONY: help install lint typecheck test test-cov clean run run-api run-ui check

help:
	@echo "UI-Pro Commands"
	@echo "============="
	@echo "make install    - Install dependencies"
	@echo "make lint      - Run flake8 linting"
	@echo "make typecheck - Run mypy type checking"
	@echo "make test     - Run tests"
	@echo "make test-cov  - Run tests with coverage"
	@echo "make clean    - Clean cache files"
	@echo "make run      - Run all services"
	@echo "make run-api  - Run FastAPI only"
	@echo "make run-ui  - Run Gradio dashboard"
	@echo "make check   - Run ALL quality checks"

install:
	pip install -r requirements.txt

lint:
	flake8 . --max-line-length=120 --exclude=.git,__pycache__,.venv,build,dist

typecheck:
	mypy . --config-file=.mypy.ini

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=ui-pro --cov-report=term-missing --cov-report=html

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache htmlcov .coverage

run:
	python run.py

run-api:
	python run.py --api

run-ui:
	python run.py --ui

check: lint typecheck test
	@echo "All checks passed!"