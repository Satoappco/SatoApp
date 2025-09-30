"""
Custom exceptions for SatoApp
"""


class SatoAppException(Exception):
    """Base exception for SatoApp"""
    
    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code
        super().__init__(self.message)


class AgentException(SatoAppException):
    """Exception raised by AI agents"""
    pass


class ValidationException(SatoAppException):
    """Exception raised during validation"""
    pass


class DatabaseException(SatoAppException):
    """Exception raised during database operations"""
    pass


class ConfigurationException(SatoAppException):
    """Exception raised for configuration issues"""
    pass


class APIException(SatoAppException):
    """Exception raised for API-related issues"""
    pass
