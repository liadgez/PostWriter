#!/usr/bin/env python3
"""
Custom exceptions for PostWriter
Provides specific exception types for different error scenarios
"""

class PostWriterError(Exception):
    """Base exception for all PostWriter errors"""
    pass

class ConfigurationError(PostWriterError):
    """Configuration-related errors"""
    pass

class ScrapingError(PostWriterError):
    """Web scraping related errors"""
    pass

class AuthenticationError(ScrapingError):
    """Authentication and login errors"""
    pass

class CookieError(AuthenticationError):
    """Cookie loading and management errors"""
    pass

class DatabaseError(PostWriterError):
    """Database operation errors"""
    pass

class AnalysisError(PostWriterError):
    """Post analysis and template generation errors"""
    pass

class ContentGenerationError(PostWriterError):
    """Content generation errors"""
    pass

class ValidationError(PostWriterError):
    """Data validation errors"""
    pass

class ChromeConnectionError(ScrapingError):
    """Chrome debugging connection errors"""
    pass

class FacebookAccessError(ScrapingError):
    """Facebook access and navigation errors"""
    pass

class DataQualityError(PostWriterError):
    """Poor quality scraped data errors"""
    pass

class SecurityError(PostWriterError):
    """Security and encryption related errors"""
    pass