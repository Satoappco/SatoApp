#!/bin/bash

################################################################################
# Quick Test Script
# Runs tests assuming PostgreSQL is already running
################################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅${NC} $1"
}

# Detect docker-compose command (v1 or v2)
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo "❌ docker-compose or docker not found. Please install Docker."
    exit 1
fi

# Set environment variables
export DATABASE_URL="sqlite:///:memory:"
export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres"
export GEMINI_API_KEY="dummy-key-for-testing"

# Check if PostgreSQL is running
if ! $DOCKER_COMPOSE -f docker-compose.test.yml exec -T postgres-test pg_isready -U postgres > /dev/null 2>&1; then
    echo "⚠️  PostgreSQL not running. Starting it..."
    $DOCKER_COMPOSE -f docker-compose.test.yml up -d

    # Wait for PostgreSQL to be ready
    echo "Waiting for PostgreSQL to be ready..."
    max_attempts=30
    attempt=0
    while ! $DOCKER_COMPOSE -f docker-compose.test.yml exec -T postgres-test pg_isready -U postgres > /dev/null 2>&1; do
        attempt=$((attempt + 1))
        if [ $attempt -eq $max_attempts ]; then
            echo "❌ PostgreSQL failed to start"
            exit 1
        fi
        echo -n "."
        sleep 1
    done
    echo ""

    # Additional wait for full initialization
    sleep 3
    echo "✅ PostgreSQL is ready"
fi

# Run tests
print_step "Running unit tests..."
pytest tests/unit/ -v --tb=short

print_step "Running integration tests..."
pytest tests/integration/ -v --tb=short

print_success "All tests passed!"
