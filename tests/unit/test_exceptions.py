"""
Tests for custom exceptions
"""

import pytest
from app.core.exceptions import (
    SatoAppException,
    AgentException,
    ValidationException,
    DatabaseException,
    ConfigurationException,
    APIException,
)


class TestSatoAppException:
    """Test SatoAppException base class"""

    def test_sato_app_exception_creation_minimal(self):
        """Test creating SatoAppException with just message"""
        exc = SatoAppException("Test error")
        assert exc.message == "Test error"
        assert exc.code is None
        assert str(exc) == "Test error"

    def test_sato_app_exception_creation_full(self):
        """Test creating SatoAppException with message and code"""
        exc = SatoAppException("Test error", "TEST_001")
        assert exc.message == "Test error"
        assert exc.code == "TEST_001"
        assert str(exc) == "Test error"

    def test_sato_app_exception_inheritance(self):
        """Test that SatoAppException inherits from Exception"""
        exc = SatoAppException("Test error")
        assert isinstance(exc, Exception)


class TestAgentException:
    """Test AgentException"""

    def test_agent_exception_creation(self):
        """Test creating AgentException"""
        exc = AgentException("Agent failed", "AGENT_001")
        assert exc.message == "Agent failed"
        assert exc.code == "AGENT_001"
        assert isinstance(exc, SatoAppException)
        assert isinstance(exc, Exception)

    def test_agent_exception_inheritance(self):
        """Test AgentException inheritance hierarchy"""
        exc = AgentException("Agent error")
        assert isinstance(exc, AgentException)
        assert isinstance(exc, SatoAppException)
        assert isinstance(exc, Exception)


class TestValidationException:
    """Test ValidationException"""

    def test_validation_exception_creation(self):
        """Test creating ValidationException"""
        exc = ValidationException("Validation failed", "VALIDATION_001")
        assert exc.message == "Validation failed"
        assert exc.code == "VALIDATION_001"
        assert isinstance(exc, SatoAppException)
        assert isinstance(exc, Exception)

    def test_validation_exception_inheritance(self):
        """Test ValidationException inheritance hierarchy"""
        exc = ValidationException("Invalid data")
        assert isinstance(exc, ValidationException)
        assert isinstance(exc, SatoAppException)
        assert isinstance(exc, Exception)


class TestDatabaseException:
    """Test DatabaseException"""

    def test_database_exception_creation(self):
        """Test creating DatabaseException"""
        exc = DatabaseException("Database error", "DB_001")
        assert exc.message == "Database error"
        assert exc.code == "DB_001"
        assert isinstance(exc, SatoAppException)
        assert isinstance(exc, Exception)

    def test_database_exception_inheritance(self):
        """Test DatabaseException inheritance hierarchy"""
        exc = DatabaseException("Connection failed")
        assert isinstance(exc, DatabaseException)
        assert isinstance(exc, SatoAppException)
        assert isinstance(exc, Exception)


class TestConfigurationException:
    """Test ConfigurationException"""

    def test_configuration_exception_creation(self):
        """Test creating ConfigurationException"""
        exc = ConfigurationException("Config error", "CONFIG_001")
        assert exc.message == "Config error"
        assert exc.code == "CONFIG_001"
        assert isinstance(exc, SatoAppException)
        assert isinstance(exc, Exception)

    def test_configuration_exception_inheritance(self):
        """Test ConfigurationException inheritance hierarchy"""
        exc = ConfigurationException("Missing config")
        assert isinstance(exc, ConfigurationException)
        assert isinstance(exc, SatoAppException)
        assert isinstance(exc, Exception)


class TestAPIException:
    """Test APIException"""

    def test_api_exception_creation(self):
        """Test creating APIException"""
        exc = APIException("API error", "API_001")
        assert exc.message == "API error"
        assert exc.code == "API_001"
        assert isinstance(exc, SatoAppException)
        assert isinstance(exc, Exception)

    def test_api_exception_inheritance(self):
        """Test APIException inheritance hierarchy"""
        exc = APIException("Request failed")
        assert isinstance(exc, APIException)
        assert isinstance(exc, SatoAppException)
        assert isinstance(exc, Exception)


class TestExceptionHierarchy:
    """Test exception hierarchy and relationships"""

    def test_all_exceptions_inherit_from_base(self):
        """Test that all custom exceptions inherit from SatoAppException"""
        exceptions = [
            AgentException("test"),
            ValidationException("test"),
            DatabaseException("test"),
            ConfigurationException("test"),
            APIException("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, SatoAppException)
            assert isinstance(exc, Exception)

    def test_exception_attributes(self):
        """Test that all exceptions have message and code attributes"""
        exc = SatoAppException("test message", "test_code")
        assert hasattr(exc, "message")
        assert hasattr(exc, "code")
        assert exc.message == "test message"
        assert exc.code == "test_code"

    def test_exception_string_representation(self):
        """Test string representation of exceptions"""
        exc = SatoAppException("Error occurred")
        assert str(exc) == "Error occurred"

        exc_with_code = SatoAppException("Error occurred", "ERR_001")
        assert str(exc_with_code) == "Error occurred"
