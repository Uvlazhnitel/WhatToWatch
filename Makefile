.PHONY: help install test lint format run-bot run-api migrate clean

help:
	@echo "WhatToWatch - Development Commands"
	@echo ""
	@echo "install       Install dependencies"
	@echo "test          Run tests"
	@echo "test-cov      Run tests with coverage report"
	@echo "lint          Run linting checks"
	@echo "format        Format code with black and ruff"
	@echo "typecheck     Run type checking with mypy"
	@echo "run-bot       Start the Telegram bot"
	@echo "run-api       Start the FastAPI server"
	@echo "run-worker    Start the embedding worker"
	@echo "migrate       Run database migrations"
	@echo "migrate-new   Create a new migration"
	@echo "db-up         Start database with docker-compose"
	@echo "db-down       Stop database"
	@echo "clean         Remove cache files"

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=app --cov-report=html --cov-report=term

lint:
	ruff check app/
	black --check app/
	
format:
	ruff check --fix app/
	black app/

typecheck:
	mypy app/

run-bot:
	python -m app.bot.run

run-api:
	uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000

run-worker:
	python -m app.jobs.embedding_worker

migrate:
	alembic upgrade head

migrate-new:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

db-up:
	docker-compose up -d
	@echo "Waiting for database to be ready..."
	@sleep 5

db-down:
	docker-compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov/ .coverage 2>/dev/null || true
