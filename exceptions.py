"""
Custom exceptions for the AdGuard rewrite sync application
"""


class ConfigurationError(Exception):
    """Raised when configuration validation fails"""
    pass


class AuthenticationError(Exception):
    """Raised when authentication fails after all retry attempts"""
    pass
