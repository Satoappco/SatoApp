"""
Pytest configuration for integration tests

Sets up SQLite for integration tests to avoid PostgreSQL dependency.
"""

import os

# Set TEST_DATABASE_URL before any other imports
# This ensures integration tests use SQLite instead of requiring PostgreSQL
os.environ['TEST_DATABASE_URL'] = 'sqlite:///:memory:'
