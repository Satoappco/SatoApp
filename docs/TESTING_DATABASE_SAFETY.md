# Testing Database Safety Guide

## ⚠️ CRITICAL: Production Database Protection

This document explains how we prevent tests from accidentally destroying production data.

## The Incident (November 29, 2025)

Running `pytest tests/integration/ -v --tb=short` **ERASED THE ENTIRE PRODUCTION DATABASE** because:

1. The test fixture `get_test_database_url()` was checking `DATABASE_URL` (production) first
2. Integration tests ran `BaseModel.metadata.drop_all()` on teardown
3. All production tables were dropped

## Safety Measures Now in Place

### 1. NEVER Use `DATABASE_URL` for Tests

The test configuration (`tests/conftest.py`) now:
- **NEVER** uses `DATABASE_URL` environment variable
- **ONLY** uses `TEST_DATABASE_URL` for integration tests
- Uses SQLite in-memory databases for unit tests

### 2. Safety Checks on Test Database URLs

If you set `TEST_DATABASE_URL`, it must either:
- Contain `localhost` or `127.0.0.1` (local databases only)
- Contain `test` in the database name

If neither condition is met, tests will **REFUSE TO RUN** and throw:
```
RuntimeError: SAFETY ERROR: TEST_DATABASE_URL appears to point to a production database!
```

### 3. Separate Test Database

Integration tests now default to: `postgresql://postgres:postgres@localhost:5432/sato_test`

**NOT** the production database name.

## How to Run Tests Safely

### Unit Tests (No database needed)
```bash
pytest tests/unit/ -v
```
Uses SQLite in-memory databases automatically.

### Integration Tests (Requires local PostgreSQL)

**Step 1:** Create a separate test database
```bash
# Connect to PostgreSQL
psql -U postgres

# Create test database
CREATE DATABASE sato_test;
\q
```

**Step 2:** Set TEST_DATABASE_URL (optional, has safe default)
```bash
export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/sato_test"
```

**Step 3:** Run integration tests
```bash
pytest tests/integration/ -v
```

### E2E Tests
```bash
pytest tests/e2e/ -v
```

## Environment Variables

### Production
```bash
DATABASE_URL=postgresql://user:pass@production-host:5432/sato_production
```
- Used by the application
- **NEVER** used by tests

### Testing
```bash
# Optional - only if you want to override the default
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sato_test
```
- Used by integration tests only
- Must point to local database or contain "test" in name
- Has safety checks to prevent production database usage

### Not Set
If `TEST_DATABASE_URL` is not set:
- Integration tests use: `postgresql://postgres:postgres@localhost:5432/sato_test`
- Unit tests use: `sqlite:///:memory:`

## CI/CD Considerations

In CI environments (GitHub Actions, etc.):

```yaml
env:
  TEST_DATABASE_URL: postgresql://postgres:postgres@localhost:5432/sato_test
  # Never set DATABASE_URL in test runs
```

## What If I Need to Test Against a Remote Database?

**DON'T.** Integration tests should always run against local databases.

If you absolutely must test against a remote test database:
1. Ensure the database name contains "test"
2. Set `TEST_DATABASE_URL` with the "test" database
3. The safety check will allow it

## Checklist Before Running Tests

- [ ] Am I running tests in production environment? (If yes, **STOP**)
- [ ] Is `TEST_DATABASE_URL` set correctly? (Should be local or contain "test")
- [ ] Do I have a separate test database created? (For integration tests)
- [ ] Have I backed up production data? (Always a good idea)

## Recovery from Database Loss

If the production database is lost:

1. **Restore from backup** (check with your database administrator)
2. **Run Alembic migrations** to recreate schema:
   ```bash
   alembic upgrade head
   ```
3. **Restore data** from backups
4. **Review this document** to understand what went wrong

## Code References

- Test configuration: `/workspace/tests/conftest.py:29-57`
- Safety check: `/workspace/tests/conftest.py:42-50`
- Test fixture: `/workspace/tests/conftest.py:56-84`

## Questions?

If you're unsure about running tests safely, ask before running:
- Integration tests in production environments
- Tests with `DATABASE_URL` set
- Tests against remote databases
