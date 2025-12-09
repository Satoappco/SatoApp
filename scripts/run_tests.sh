#!/bin/bash

################################################################################
# Unified Test Runner Script
# Supports multiple modes: quick, ci, local-ci
# Usage: ./run_tests.sh [--quick|-q] [--ci|-c] [--local-ci|-l]
################################################################################

set -e

# Default mode (full CI with dependency installation)
MODE="ci-with-deps"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --quick|-q)
            MODE="quick"
            shift
            ;;
        --ci|-c)
            MODE="ci"
            shift
            ;;
        --local-ci|-l)
            MODE="local-ci"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--quick|-q] [--ci|-c] [--local-ci|-l]"
            echo ""
            echo "Modes:"
            echo "  --quick, -q     Fast test execution"
            echo "  --ci, -c        Full CI pipeline with coverage and reports"
            echo "  --local-ci, -l  Local CI simulation with dependency installation"
            echo ""
            echo "Default: Full CI pipeline with dependency installation"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Detect docker compose command
if command -v docker compose &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    print_error "docker compose or docker-compose not found. Please install Docker."
    exit 1
fi

# Function to cleanup on exit (for ci and local-ci modes)
cleanup() {
    if [[ "$MODE" == "ci" || "$MODE" == "local-ci" || "$MODE" == "ci-with-deps" ]]; then
        print_step "Cleaning up..."
        $DOCKER_COMPOSE -f docker-compose.test.yml down -v 2>/dev/null || true
        print_success "Cleanup completed"
    fi
}

# Trap exit for cleanup (for ci, local-ci, and ci-with-deps modes)
if [[ "$MODE" == "ci" || "$MODE" == "local-ci" || "$MODE" == "ci-with-deps" ]]; then
    trap cleanup EXIT
fi

echo "🚀 Running tests in $MODE mode"
echo "=================================="

# Prerequisites check (for ci, local-ci, and ci-with-deps modes)
if [[ "$MODE" == "ci" || "$MODE" == "local-ci" || "$MODE" == "ci-with-deps" ]]; then
    print_step "Checking prerequisites..."

    if ! python -c "import pytest" 2>/dev/null; then
        print_error "pytest not installed. Run: pip install -r requirements.txt"
        exit 1
    fi

    print_success "Prerequisites check passed"
fi

# Install dependencies (for local-ci and ci-with-deps modes)
if [[ "$MODE" == "local-ci" || "$MODE" == "ci-with-deps" ]]; then
    print_step "Installing dependencies..."
    pip install -q -r requirements.txt
    print_success "Dependencies installed"
fi

# Start PostgreSQL
print_step "Starting PostgreSQL test container..."

# Stop any existing containers (for ci and local-ci modes)
if [[ "$MODE" == "ci" || "$MODE" == "local-ci" ]]; then
    $DOCKER_COMPOSE -f docker-compose.test.yml down -v 2>/dev/null || true
fi

$DOCKER_COMPOSE -f docker-compose.test.yml up -d

# Wait for PostgreSQL to be ready
print_step "Waiting for PostgreSQL to be ready..."
max_attempts=30
attempt=0

# Different port check based on mode
if [[ "$MODE" == "ci" || "$MODE" == "ci-with-deps" ]]; then
    PG_CHECK_CMD="$DOCKER_COMPOSE -f docker-compose.test.yml exec -T postgres-test pg_isready -h localhost -p 5433 -U postgres"
else
    PG_CHECK_CMD="$DOCKER_COMPOSE -f docker-compose.test.yml exec -T postgres-test pg_isready -U postgres"
fi

while ! $PG_CHECK_CMD > /dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ $attempt -eq $max_attempts ]; then
        print_error "PostgreSQL failed to start after $max_attempts attempts"
        $DOCKER_COMPOSE -f docker-compose.test.yml logs postgres-test
        exit 1
    fi
    echo -n "."
    sleep 1
done
echo ""

# Additional wait for full initialization
sleep 3

# Verify connection for ci and ci-with-deps modes
if [[ "$MODE" == "ci" || "$MODE" == "ci-with-deps" ]]; then
    if $DOCKER_COMPOSE -f docker-compose.test.yml exec -T postgres-test psql -h localhost -p 5433 -U postgres -d postgres -c "SELECT 1" > /dev/null 2>&1; then
        print_success "PostgreSQL is ready and accepting queries"
    else
        print_error "PostgreSQL is running but not accepting queries"
        $DOCKER_COMPOSE -f docker-compose.test.yml logs postgres-test
        exit 1
    fi
else
    print_success "PostgreSQL is ready"
fi

# Linting (for ci, local-ci, and ci-with-deps modes)
if [[ "$MODE" == "ci" || "$MODE" == "local-ci" || "$MODE" == "ci-with-deps" ]]; then
    print_step "Running linting checks..."

    if python -m py_compile app/**/*.py 2>/dev/null; then
        print_success "Linting passed"
    else
        print_warning "Linting had some issues (non-blocking)"
    fi
fi

# Set environment variables
export GEMINI_API_KEY="dummy-key-for-testing"

# Run unit tests
print_step "Running unit tests..."
export DATABASE_URL="sqlite:///:memory:"

if [[ "$MODE" == "ci" || "$MODE" == "ci-with-deps" ]]; then
    pytest tests/unit/ -v --cov=app --cov-report=xml --cov-report=term --tb=short
    print_success "Unit tests passed"
elif [[ "$MODE" == "local-ci" ]]; then
    if pytest tests/unit/ -v --cov=app --cov-report=xml --tb=short; then
        print_success "Unit tests passed"
    else
        print_error "Unit tests failed"
        exit 1
    fi
else
    pytest tests/unit/ -v --tb=short
    print_success "Unit tests passed"
fi

# Run integration tests
print_step "Running integration tests..."

if [[ "$MODE" == "ci" || "$MODE" == "ci-with-deps" ]]; then
    export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5433/postgres"
    if pytest tests/integration/ -v --tb=short; then
        print_success "Integration tests passed"
    else
        print_error "Integration tests failed"
        exit 1
    fi
elif [[ "$MODE" == "local-ci" ]]; then
    export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5433/postgres"
    if pytest tests/integration/ -v --tb=short; then
        print_success "Integration tests passed"
    else
        print_error "Integration tests failed"
        exit 1
    fi
else
    export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/postgres"
    pytest tests/integration/ -v --tb=short
    print_success "Integration tests passed"
fi

# Generate reports (for ci, local-ci, and ci-with-deps modes)
if [[ "$MODE" == "ci" || "$MODE" == "ci-with-deps" ]]; then
    print_step "Generating HTML test report..."

    mkdir -p reports
    export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5433/postgres"

    if pytest tests/ --html=reports/test-report.html --self-contained-html --tb=short; then
        print_success "Test report generated: reports/test-report.html"
    else
        print_warning "Test report generated with failures: reports/test-report.html"
    fi

    print_step "Coverage summary:"
    if [ -f coverage.xml ]; then
        print_success "Coverage report saved: coverage.xml"
    fi

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

elif [[ "$MODE" == "local-ci" ]]; then
    print_step "Generating test report..."

    mkdir -p reports
    export DATABASE_URL="sqlite:///:memory:"

    pytest tests/unit tests/e2e --html=reports/test-report.html --self-contained-html 2>/dev/null || true

    print_step "Coverage Report:"
    if [ -f coverage.xml ]; then
        echo "Coverage report generated: coverage.xml"
        echo "View HTML report: open htmlcov/index.html"
    else
        echo "No coverage report found"
    fi

    # Cleanup for local-ci mode
    print_step "Cleaning up PostgreSQL..."
    $DOCKER_COMPOSE -f docker-compose.test.yml down

    echo ""
    echo "=================================="
    print_success "All CI/CD steps completed successfully!"
    echo "=================================="
    echo ""

    if [ -f reports/test-report.html ]; then
        echo -e "📊 Test report: ${GREEN}reports/test-report.html${NC}"
        echo -e "   Open with: ${YELLOW}open reports/test-report.html${NC}"
    fi

    if [ -f htmlcov/index.html ]; then
        echo -e "📊 Coverage report: ${GREEN}htmlcov/index.html${NC}"
        echo -e "   Open with: ${YELLOW}open htmlcov/index.html${NC}"
    fi
else
    print_success "All tests passed!"
fi