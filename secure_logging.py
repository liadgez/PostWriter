#!/usr/bin/env python3
"""
Secure Logging System for PostWriter
Provides security-aware logging that filters sensitive information
"""

import os
import re
import json
import logging
import hashlib
from typing import Any, Dict, List, Union, Optional
from datetime import datetime
from dataclasses import dataclass

from exceptions import SecurityError


@dataclass
class SensitivePattern:
    """Definition of a sensitive data pattern"""
    pattern: str
    replacement: str
    description: str
    severity: str  # 'high', 'medium', 'low'


class SecurityLogFilter:
    """Filters sensitive information from log messages"""
    
    def __init__(self):
        """Initialize security filter with predefined patterns"""
        self.sensitive_patterns = [
            # Authentication and tokens
            SensitivePattern(
                pattern=r'(?i)(token|auth|bearer|api[_-]?key)\s*[=:]\s*["\']?([a-zA-Z0-9_\-\.]{20,})["\']?',
                replacement=r'\1=***TOKEN_REDACTED***',
                description='Authentication tokens and API keys',
                severity='high'
            ),
            
            # Passwords
            SensitivePattern(
                pattern=r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']?([^"\'\s]{6,})["\']?',
                replacement=r'\1=***PASSWORD_REDACTED***',
                description='Password fields',
                severity='high'
            ),
            
            # Session IDs and cookies
            SensitivePattern(
                pattern=r'(?i)(session[_-]?id|sid|sess)\s*[=:]\s*["\']?([a-zA-Z0-9_\-]{16,})["\']?',
                replacement=r'\1=***SESSION_REDACTED***',
                description='Session identifiers',
                severity='high'
            ),
            
            # Facebook cookies (specific patterns)
            SensitivePattern(
                pattern=r'(?i)(sb|datr|c_user|xs|fr)\s*[=:]\s*["\']?([^"\'\s&;]{10,})["\']?',
                replacement=r'\1=***FB_COOKIE_REDACTED***',
                description='Facebook authentication cookies',
                severity='high'
            ),
            
            # Generic cookie values
            SensitivePattern(
                pattern=r'(?i)cookie[s]?\s*[=:]\s*["\']?([^"\'\s]{20,})["\']?',
                replacement='cookies=***COOKIES_REDACTED***',
                description='Generic cookie values',
                severity='medium'
            ),
            
            # URLs with sensitive parameters
            SensitivePattern(
                pattern=r'(https?://[^?\s]+\?)([^"\s]+)',
                replacement=r'\1***PARAMS_REDACTED***',
                description='URL parameters that may contain sensitive data',
                severity='medium'
            ),
            
            # Email addresses
            SensitivePattern(
                pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                replacement='***EMAIL_REDACTED***',
                description='Email addresses',
                severity='low'
            ),
            
            # Credit card numbers (basic pattern)
            SensitivePattern(
                pattern=r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
                replacement='***CARD_REDACTED***',
                description='Credit card numbers',
                severity='high'
            ),
            
            # Phone numbers
            SensitivePattern(
                pattern=r'\b\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
                replacement='***PHONE_REDACTED***',
                description='Phone numbers',
                severity='medium'
            ),
            
            # JSON structures with sensitive keys
            SensitivePattern(
                pattern=r'(?i)(["\'](?:token|password|auth|key|secret|cookie)["\'])\s*:\s*["\']([^"\']{6,})["\']',
                replacement=r'\1: "***REDACTED***"',
                description='JSON sensitive key-value pairs',
                severity='high'
            )
        ]
        
        # Compiled patterns for performance
        self.compiled_patterns = [
            (re.compile(pattern.pattern), pattern.replacement, pattern)
            for pattern in self.sensitive_patterns
        ]
    
    def filter_message(self, message: str) -> tuple[str, List[str]]:
        """
        Filter sensitive information from a log message
        
        Args:
            message: Original log message
            
        Returns:
            tuple: (filtered_message, list_of_detected_patterns)
        """
        filtered_message = message
        detected_patterns = []
        
        for compiled_pattern, replacement, pattern_info in self.compiled_patterns:
            matches = compiled_pattern.findall(filtered_message)
            if matches:
                filtered_message = compiled_pattern.sub(replacement, filtered_message)
                detected_patterns.append(pattern_info.description)
        
        return filtered_message, detected_patterns
    
    def add_custom_pattern(self, pattern: SensitivePattern):
        """Add a custom sensitive data pattern"""
        self.sensitive_patterns.append(pattern)
        self.compiled_patterns.append((
            re.compile(pattern.pattern),
            pattern.replacement,
            pattern
        ))


class SecureLogger:
    """Security-aware logger for PostWriter"""
    
    def __init__(self, name: str = "postwriter", log_file: str = None, level: int = logging.INFO):
        """
        Initialize secure logger
        
        Args:
            name: Logger name
            log_file: Optional log file path
            level: Logging level
        """
        self.name = name
        self.filter = SecurityLogFilter()
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Prevent duplicate handlers
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # Console handler with security filtering
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self._create_formatter())
        console_handler.addFilter(self._create_log_filter())
        self.logger.addHandler(console_handler)
        
        # File handler if specified
        if log_file:
            try:
                os.makedirs(os.path.dirname(log_file), exist_ok=True)
                file_handler = logging.FileHandler(log_file)
                file_handler.setFormatter(self._create_detailed_formatter())
                file_handler.addFilter(self._create_log_filter())
                self.logger.addHandler(file_handler)
            except Exception as e:
                self.logger.warning(f"Could not create file handler for {log_file}: {e}")
        
        # Security incident logging
        self.security_incidents = []
    
    def _create_formatter(self) -> logging.Formatter:
        """Create console log formatter"""
        return logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def _create_detailed_formatter(self) -> logging.Formatter:
        """Create detailed file log formatter"""
        return logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def _create_log_filter(self):
        """Create logging filter that applies security filtering"""
        class SecurityLogFilter(logging.Filter):
            def __init__(self, security_filter):
                super().__init__()
                self.security_filter = security_filter
            
            def filter(self, record):
                # Apply security filtering to the message
                filtered_msg, detected = self.security_filter.filter_message(record.getMessage())
                
                # Replace the message with filtered version
                record.msg = filtered_msg
                record.args = ()
                
                # Log security incidents if sensitive data was detected
                if detected:
                    incident = {
                        'timestamp': datetime.now().isoformat(),
                        'level': record.levelname,
                        'logger': record.name,
                        'function': record.funcName,
                        'line': record.lineno,
                        'detected_patterns': detected,
                        'message_hash': hashlib.sha256(str(record.msg).encode()).hexdigest()[:16]
                    }
                    # Note: We don't store the actual message for security
                
                return True
        
        return SecurityLogFilter(self.filter)
    
    def log_operation(self, operation: str, details: Dict[str, Any] = None, level: int = logging.INFO):
        """
        Log an operation with automatic security filtering
        
        Args:
            operation: Operation description
            details: Optional operation details
            level: Log level
        """
        if details:
            # Filter details dictionary
            safe_details = self._filter_dict(details)
            message = f"{operation} - Details: {safe_details}"
        else:
            message = operation
        
        self.logger.log(level, message)
    
    def log_security_event(self, event_type: str, details: Dict[str, Any]):
        """
        Log a security-related event
        
        Args:
            event_type: Type of security event
            details: Event details (will be filtered)
        """
        safe_details = self._filter_dict(details)
        message = f"SECURITY_EVENT: {event_type} - {safe_details}"
        self.logger.warning(message)
        
        # Store security incident
        incident = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'details': safe_details
        }
        self.security_incidents.append(incident)
    
    def log_data_operation(self, operation: str, data_type: str, count: int = None, details: Dict[str, Any] = None):
        """
        Log a data operation (scraping, storage, etc.)
        
        Args:
            operation: Operation type (e.g., 'scrape', 'store', 'encrypt')
            data_type: Type of data (e.g., 'posts', 'cookies', 'session')
            count: Number of items processed
            details: Additional details
        """
        message_parts = [f"DATA_OP: {operation}"]
        
        if count is not None:
            message_parts.append(f"{count} {data_type}")
        else:
            message_parts.append(data_type)
        
        if details:
            safe_details = self._filter_dict(details)
            message_parts.append(f"Details: {safe_details}")
        
        self.logger.info(" - ".join(message_parts))
    
    def _filter_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter sensitive information from a dictionary"""
        if not isinstance(data, dict):
            return data
        
        filtered = {}
        for key, value in data.items():
            # Check if key indicates sensitive data
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in ['password', 'token', 'auth', 'cookie', 'secret', 'key']):
                if isinstance(value, str) and len(value) > 4:
                    filtered[key] = f"***{value[:2]}...{value[-2:]}***"
                else:
                    filtered[key] = "***REDACTED***"
            elif isinstance(value, dict):
                filtered[key] = self._filter_dict(value)
            elif isinstance(value, list):
                filtered[key] = [self._filter_dict(item) if isinstance(item, dict) else item for item in value[:5]]  # Limit list size
                if len(value) > 5:
                    filtered[key].append(f"... and {len(value) - 5} more items")
            elif isinstance(value, str):
                # Apply string filtering
                filtered_str, _ = self.filter.filter_message(value)
                filtered[key] = filtered_str
            else:
                filtered[key] = value
        
        return filtered
    
    def info(self, message: str, *args, **kwargs):
        """Log info message with security filtering"""
        self.logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message with security filtering"""
        self.logger.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log error message with security filtering"""
        self.logger.error(message, *args, **kwargs)
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message with security filtering"""
        self.logger.debug(message, *args, **kwargs)
    
    def get_security_incidents(self) -> List[Dict[str, Any]]:
        """Get list of detected security incidents"""
        return self.security_incidents.copy()
    
    def export_security_report(self, filepath: str):
        """Export security incidents to a file"""
        try:
            report = {
                'generated_at': datetime.now().isoformat(),
                'logger_name': self.name,
                'total_incidents': len(self.security_incidents),
                'incidents': self.security_incidents
            }
            
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2)
            
            self.info(f"Security report exported to {filepath}")
            
        except Exception as e:
            self.error(f"Failed to export security report: {e}")


# Global secure logger instance
_global_logger = None


def get_secure_logger(name: str = "postwriter", log_file: str = None) -> SecureLogger:
    """
    Get or create a secure logger instance
    
    Args:
        name: Logger name
        log_file: Optional log file path
        
    Returns:
        SecureLogger instance
    """
    global _global_logger
    
    if _global_logger is None:
        _global_logger = SecureLogger(name, log_file)
    
    return _global_logger


def secure_print(message: str, level: int = logging.INFO):
    """
    Secure replacement for print() function
    
    Args:
        message: Message to print/log
        level: Log level
    """
    logger = get_secure_logger()
    logger.logger.log(level, message)


def audit_log_security(directory: str = ".") -> Dict[str, Any]:
    """
    Audit Python files for potential logging security issues
    
    Args:
        directory: Directory to audit
        
    Returns:
        Audit results dictionary
    """
    results = {
        'files_audited': 0,
        'potential_issues': [],
        'unsafe_patterns': [
            r'print\s*\([^)]*(?:password|token|auth|cookie|secret|key)',
            r'log\.(?:info|debug|warning|error)\s*\([^)]*(?:password|token|auth|cookie|secret|key)',
            r'print\s*\([^)]*\{.*\}',  # Print statements with dict formatting
            r'f["\'][^"\']*\{[^}]*(?:password|token|auth|cookie|secret|key)[^}]*\}',  # f-strings with sensitive vars
        ],
        'recommendations': []
    }
    
    import glob
    
    # Find all Python files
    python_files = glob.glob(os.path.join(directory, "**/*.py"), recursive=True)
    results['files_audited'] = len(python_files)
    
    for filepath in python_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                for pattern in results['unsafe_patterns']:
                    if re.search(pattern, line, re.IGNORECASE):
                        results['potential_issues'].append({
                            'file': filepath,
                            'line': line_num,
                            'content': line.strip(),
                            'pattern': pattern,
                            'severity': 'high' if any(word in line.lower() for word in ['password', 'token', 'auth']) else 'medium'
                        })
        
        except Exception as e:
            results['potential_issues'].append({
                'file': filepath,
                'line': 0,
                'content': f"Error reading file: {e}",
                'pattern': 'file_error',
                'severity': 'low'
            })
    
    # Generate recommendations
    high_severity_count = sum(1 for issue in results['potential_issues'] if issue['severity'] == 'high')
    
    if high_severity_count > 0:
        results['recommendations'].append(f"Replace {high_severity_count} high-severity logging statements with secure_print() or SecureLogger")
    
    if len(results['potential_issues']) > 0:
        results['recommendations'].append("Implement comprehensive secure logging across the application")
        results['recommendations'].append("Add security filters to all logging operations")
        results['recommendations'].append("Review and sanitize all error messages and debug output")
    
    return results


if __name__ == "__main__":
    # Demo and test secure logging
    print("🔒 Secure Logging System Demo")
    
    # Create secure logger
    logger = get_secure_logger("demo", "demo_secure.log")
    
    # Test various logging scenarios
    print("\n📋 Testing sensitive data filtering:")
    
    # Test cases that should be filtered
    test_messages = [
        "User logged in with password=mypassword123",
        "Auth token: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "Cookie: session_id=abc123def456ghi789; auth=xyz789",
        "Facebook cookie sb=PINhaBDqaLUO-ktjAuo_RZgT datr=abc123",
        "API call to https://api.example.com/data?token=secret123&user=admin",
        "User email: user@example.com phone: +1-555-123-4567"
    ]
    
    for msg in test_messages:
        logger.info(f"Original: {msg}")
    
    # Test structured logging
    logger.log_data_operation(
        operation="scrape",
        data_type="facebook_posts",
        count=25,
        details={
            "profile_url": "https://facebook.com/user123",
            "session_token": "secret_token_12345",
            "cookies": {"auth": "sensitive_cookie_value"},
            "timestamp": datetime.now().isoformat()
        }
    )
    
    # Test security event logging
    logger.log_security_event(
        event_type="authentication_attempt",
        details={
            "user": "admin",
            "password": "attempted_password",
            "source_ip": "192.168.1.100",
            "success": False
        }
    )
    
    # Audit current directory for logging security issues
    print("\n🔍 Auditing current directory for logging security issues...")
    audit_results = audit_log_security(".")
    
    print(f"Files audited: {audit_results['files_audited']}")
    print(f"Potential issues found: {len(audit_results['potential_issues'])}")
    
    if audit_results['potential_issues']:
        print("\n⚠️ Security Issues Found:")
        for issue in audit_results['potential_issues'][:5]:  # Show first 5
            print(f"   {issue['severity'].upper()}: {issue['file']}:{issue['line']}")
            print(f"      {issue['content']}")
    
    if audit_results['recommendations']:
        print(f"\n💡 Recommendations:")
        for rec in audit_results['recommendations']:
            print(f"   • {rec}")
    
    # Export security report
    logger.export_security_report("security_audit_report.json")
    print(f"\n✅ Security report generated")