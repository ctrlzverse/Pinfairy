# Pinfairy Bot Makefile
# Provides convenient commands for development and deployment

.PHONY: help setup install install-dev test lint format type-check security clean run run-enhanced docker-build docker-run

# Default target
help:
	@echo "Pinfairy Bot - Available Commands:"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  setup          - Set up development environment"
	@echo "  install        - Install production dependencies"
	@echo "  install-dev    - Install development dependencies"
	@echo ""
	@echo "Development:"
	@echo "  test           - Run all tests with coverage"
	@echo "  lint           - Run linting checks"
	@echo "  format         - Format code with black and isort"
	@echo "  type-check     - Run type checking with mypy"
	@echo "  security       - Run security checks with bandit"
	@echo "  clean          - Clean up temporary files"
	@echo ""
	@echo "Running:"
	@echo "  run            - Run original bot"
	@echo "  run-enhanced   - Run enhanced bot (recommended)"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build   - Build Docker image"
	@echo "  docker-run     - Run bot in Docker container"

# Setup development environment
setup:
	@echo "🚀 Setting up Pinfairy Bot development environment..."
	./setup.sh --dev

# Install production dependencies
install:
	pip install -r requirements.txt
	playwright install

# Install development dependencies
install-dev:
	pip install -r requirements-dev.txt
	playwright install

# Run tests with coverage
test:
	@echo "🧪 Running tests..."
	pytest tests/ -v --cov=. --cov-report=term-missing --cov-report=html

# Run linting
lint:
	@echo "🔍 Running linting checks..."
	flake8 .
	@echo "✅ Linting passed!"

# Format code
format:
	@echo "🎨 Formatting code..."
	black .
	isort .
	@echo "✅ Code formatted!"

# Type checking
type-check:
	@echo "🔍 Running type checks..."
	mypy . --ignore-missing-imports
	@echo "✅ Type checking passed!"

# Security checks
security:
	@echo "🔒 Running security checks..."
	bandit -r . -x tests/
	@echo "✅ Security checks passed!"

# Clean temporary files
clean:
	@echo "🧹 Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .pytest_cache/ .mypy_cache/
	@echo "✅ Cleanup complete!"

# Run original bot
run:
	@echo "🤖 Starting Pinfairy Bot (original)..."
	python3 bot.py

# Run enhanced bot
run-enhanced:
	@echo "🚀 Starting Pinfairy Bot (enhanced)..."
	python3 bot_enhanced.py

# Build Docker image
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -f Dockerfile.enhanced -t pinfairy-bot:latest .

# Run in Docker
docker-run:
	@echo "🐳 Running bot in Docker..."
	docker-compose up -d
