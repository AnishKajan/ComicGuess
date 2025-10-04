# ComicGuess Development Makefile

.PHONY: help dev dev-frontend dev-backend install install-frontend install-backend db-smoke db-init db-status test clean

# Default target
help:
	@echo "ComicGuess Development Commands"
	@echo "==============================="
	@echo ""
	@echo "Development:"
	@echo "  make dev              - Run both frontend and backend in development mode"
	@echo "  make dev-frontend     - Run only frontend (Next.js on :3000)"
	@echo "  make dev-backend      - Run only backend (FastAPI on :8000)"
	@echo ""
	@echo "Installation:"
	@echo "  make install          - Install all dependencies"
	@echo "  make install-frontend - Install frontend dependencies"
	@echo "  make install-backend  - Install backend dependencies"
	@echo ""
	@echo "Database:"
	@echo "  make db-smoke         - Quick Cosmos DB connection test"
	@echo "  make db-init          - Initialize database containers"
	@echo "  make db-status        - Show database status"
	@echo ""
	@echo "Testing:"
	@echo "  make test             - Run all tests"
	@echo "  make test-frontend    - Run frontend tests"
	@echo "  make test-backend     - Run backend tests"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean            - Clean build artifacts"

# Development commands
dev:
	@echo "🚀 Starting ComicGuess development servers..."
	@echo "Frontend: http://localhost:3000"
	@echo "Backend:  http://localhost:8000"
	@echo "Press Ctrl+C to stop both servers"
	@trap 'kill %1 %2' INT; \
	make dev-backend & \
	make dev-frontend & \
	wait

dev-frontend:
	@echo "🎨 Starting Next.js frontend on :3000..."
	cd frontend && npm run dev

dev-backend:
	@echo "⚡ Starting FastAPI backend on :8000..."
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Installation commands
install: install-frontend install-backend
	@echo "✅ All dependencies installed"

install-frontend:
	@echo "📦 Installing frontend dependencies..."
	cd frontend && npm install

install-backend:
	@echo "🐍 Installing backend dependencies..."
	cd backend && pip install -r requirements.txt

# Database commands
db-smoke:
	@echo "🔍 Running Cosmos DB smoke test..."
	cd backend && python test_cosmos_connection.py

db-init:
	@echo "🗄️  Initializing database..."
	cd backend && python manage_db.py init

db-status:
	@echo "📊 Checking database status..."
	cd backend && python manage_db.py status

# Testing commands
test: test-frontend test-backend
	@echo "✅ All tests completed"

test-frontend:
	@echo "🧪 Running frontend tests..."
	cd frontend && npm test

test-backend:
	@echo "🧪 Running backend tests..."
	cd backend && python -m pytest

# Utility commands
clean:
	@echo "🧹 Cleaning build artifacts..."
	cd frontend && rm -rf .next out node_modules/.cache
	cd backend && find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	cd backend && find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Clean completed"

# Check if required tools are installed
check-deps:
	@echo "🔍 Checking dependencies..."
	@command -v node >/dev/null 2>&1 || { echo "❌ Node.js is required but not installed."; exit 1; }
	@command -v npm >/dev/null 2>&1 || { echo "❌ npm is required but not installed."; exit 1; }
	@command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 is required but not installed."; exit 1; }
	@command -v pip >/dev/null 2>&1 || { echo "❌ pip is required but not installed."; exit 1; }
	@echo "✅ All required tools are installed"