"""
PostWriter - Facebook Marketing Analysis Platform
A secure, production-ready tool for analyzing Facebook posts and generating marketing content.
"""

__version__ = "2.0.0"
__author__ = "PostWriter Development Team"
__description__ = "Secure Facebook marketing analysis platform with enterprise-grade security"

# Security and compliance
__security_version__ = "2.0.0"
__last_security_audit__ = "2025-07-01"

# Core exports
from .utils.exceptions import (
    PostWriterError,
    SecurityError,
    ConfigurationError,
    ScrapingError,
    ValidationError,
    AuthenticationError,
    FacebookAccessError
)

__all__ = [
    "__version__",
    "__author__", 
    "__description__",
    "PostWriterError",
    "SecurityError",
    "ConfigurationError", 
    "ScrapingError",
    "ValidationError",
    "AuthenticationError",
    "FacebookAccessError"
]