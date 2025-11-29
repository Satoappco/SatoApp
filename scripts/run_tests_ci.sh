#!/bin/bash

################################################################################
# Local CI/CD Testing Script
# Mimics the GitHub Actions workflow for testing locally
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

# Detect docker compose command (v1 or v2)
if command -v docker compose &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo "❌ docker compose or docker not found. Please install Docker."
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    print_step "Cleaning up..."
    $DOCKER_COMPOSE -f docker-compose.test.yml down -v 2>/dev/null || true
    print_success "Cleanup completed"
}

# Trap exit to ensure cleanup
trap cleanup EXIT

################################################################################
# Step 1: Check Prerequisites
################################################################################

print_step "Checking prerequisites..."

# Check if pytest is installed
if ! python -c "import pytest" 2>/dev/null; then
    print_error "pytest not installed. Run: pip install -r requirements.txt"
    exit 1
fi

print_success "Prerequisites check passed"

################################################################################
# Step 2: Start PostgreSQL Test Container
################################################################################

print_step "Starting PostgreSQL test container..."

# Stop any existing test containers
$DOCKER_COMPOSE -f docker-compose.test.yml down -v 2>/dev/null || true

# Start PostgreSQL
$DOCKER_COMPOSE -f docker-compose.test.yml up -d

# Wait for PostgreSQL to be ready
print_step "Waiting for PostgreSQL to be ready..."
max_attempts=30
attempt=0
while ! $DOCKER_COMPOSE -f docker-compose.test.yml exec -T postgres-test pg_isready -U postgres > /dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ $attempt -eq $max_attempts ]; then
        print_error "PostgreSQL failed to start after $max_attempts attempts"
        exit 1
    fi
    echo -n "."
    sleep 1
done
echo ""
print_success "PostgreSQL is ready"

################################################################################
# Step 3: Run Linting (Basic Python Compilation)
################################################################################

print_step "Running linting checks..."

# Basic Python syntax check
if python -m py_compile app/**/*.py 2>/dev/null; then
    print_success "Linting passed"
else
    print_warning "Linting had some issues (non-blocking)"
fi

################################################################################
# Step 4: Run Unit Tests
################################################################################

print_step "Running unit tests with SQLite..."

export DATABASE_URL="sqlite:///:memory:"
export GEMINI_API_KEY="dummy-key-for-testing"

if pytest tests/unit/ -v --cov=app --cov-report=xml --cov-report=term --tb=short; then
    print_success "Unit tests passed"
else
    print_error "Unit tests failed"
    exit 1
fi

################################################################################
# Step 5: Run Integration Tests
################################################################################

print_step "Running integration tests with PostgreSQL..."

export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres"
export GEMINI_API_KEY="dummy-key-for-testing"

if pytest tests/integration/ -v --tb=short; then
    print_success "Integration tests passed"
else
    print_error "Integration tests failed"
    exit 1
fi

################################################################################
# Step 6: Generate Test Report
################################################################################

print_step "Generating HTML test report..."

# Create reports directory if it doesn't exist
mkdir -p reports

# Run all tests and generate HTML report
export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres"
export GEMINI_API_KEY="dummy-key-for-testing"

if pytest tests/ --html=reports/test-report.html --self-contained-html --tb=short; then
    print_success "Test report generated: reports/test-report.html"
else
    print_warning "Test report generated with failures: reports/test-report.html"
fi

################################################################################
# Step 7: Display Coverage Summary
################################################################################

print_step "Coverage summary:"
if [ -f coverage.xml ]; then
    print_success "Coverage report saved: coverage.xml"
fi

################################################################################
# Step 8: Summary
################################################################################

echo ""
echo "================================================================================"
print_success "CI/CD Testing Complete!"
echo "================================================================================"
echo ""
echo "📊 Reports generated:"
echo "   - Test Report: reports/test-report.html"
echo "   - Coverage:    coverage.xml"
echo ""
echo "🔍 To view test report:"
echo "   open reports/test-report.html"
echo ""
echo "🧹 PostgreSQL container will be stopped automatically"
echo ""
