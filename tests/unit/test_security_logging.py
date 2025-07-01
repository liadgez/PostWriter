#!/usr/bin/env python3
"""
Unit tests for PostWriter secure logging system
Tests log filtering, security event tracking, and sensitive data protection
"""

import os
import tempfile
import json
import pytest
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.postwriter.security.logging import SecureLogger, get_secure_logger, SecurityLogFilter


class TestSecurityLogFilter:
    """Test suite for SecurityLogFilter class"""
    
    def setup_method(self):
        """Setup test environment"""
        self.filter = SecurityLogFilter()
    
    def test_password_filtering(self):
        """Test filtering of password patterns"""
        test_cases = [
            ("password=secret123", "secret123", "***PASSWORD_REDACTED***"),
            ("pwd: mypassword", "mypassword", "***PASSWORD_REDACTED***"), 
            ("authentication with password='complex_pass'", "complex_pass", "***PASSWORD_REDACTED***"),
            ('{"password": "test123"}', "test123", "***REDACTED***")
        ]
        
        for original, sensitive_value, expected_redaction in test_cases:
            filtered, detected_patterns = self.filter.filter_message(original)
            
            # Check that sensitive values are removed
            assert sensitive_value not in filtered
            
            # Check that appropriate redaction occurred
            assert expected_redaction in filtered
            
            # Should detect patterns
            assert len(detected_patterns) > 0
    
    def test_token_filtering(self):
        """Test filtering of authentication tokens"""
        test_cases = [
            ("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc123", "Bearer ***FILTERED***"),
            ("auth_token=abc123def456", "auth_token=***FILTERED***"),
            ("Authorization: Token sk-1234567890abcdef", "Authorization: Token ***FILTERED***"),
            ("X-API-Key: AIzaSyC1234567890", "X-API-Key: ***FILTERED***"),
            ("sessionToken: sess_1234567890", "sessionToken: ***FILTERED***")
        ]
        
        for original, expected in test_cases:
            filtered, _ = self.filter.filter_message(original)
            # Check that actual token values are not present
            assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc123" not in filtered
            assert "abc123def456" not in filtered
            assert "sk-1234567890abcdef" not in filtered
            assert "AIzaSyC1234567890" not in filtered
            assert "sess_1234567890" not in filtered
            assert "***FILTERED***" in filtered
    
    def test_cookie_filtering(self):
        """Test filtering of cookie values"""
        test_cases = [
            ("Set-Cookie: sessionid=abc123; path=/", "Set-Cookie: sessionid=***FILTERED***; path=/"),
            ("Cookie: user_token=xyz789; theme=dark", "Cookie: user_token=***FILTERED***; theme=dark"),
            ("document.cookie = 'auth=secret123'", "document.cookie = 'auth=***FILTERED***'"),
            ('cookies: {"sessionid": "value123", "theme": "dark"}', 'cookies: {"sessionid": "***FILTERED***", "theme": "dark"}')
        ]
        
        for original, expected in test_cases:
            filtered, _ = self.filter.filter_message(original)
            assert "abc123" not in filtered
            assert "xyz789" not in filtered  
            assert "secret123" not in filtered
            assert "value123" not in filtered
            assert "***FILTERED***" in filtered
            # Non-sensitive values should remain
            assert "dark" in filtered
    
    def test_api_key_filtering(self):
        """Test filtering of API keys"""
        test_cases = [
            ("api_key=sk-1234567890abcdef", "api_key=***FILTERED***"),
            ("OPENAI_API_KEY=sk-proj-xyz123", "OPENAI_API_KEY=***FILTERED***"),
            ("key: AIzaSyBxxxxxxxxxxxxxxx", "key: ***FILTERED***"),
            ("access_key_id=AKIAIOSFODNN7EXAMPLE", "access_key_id=***FILTERED***")
        ]
        
        for original, expected in test_cases:
            filtered, _ = self.filter.filter_message(original)
            assert "sk-1234567890abcdef" not in filtered
            assert "sk-proj-xyz123" not in filtered
            assert "AIzaSyBxxxxxxxxxxxxxxx" not in filtered
            assert "AKIAIOSFODNN7EXAMPLE" not in filtered
            assert "***FILTERED***" in filtered
    
    def test_url_credential_filtering(self):
        """Test filtering of credentials in URLs"""
        test_cases = [
            ("https://user:pass@api.example.com", "https://user:***FILTERED***@api.example.com"),
            ("mysql://admin:secret@localhost:3306/db", "mysql://admin:***FILTERED***@localhost:3306/db"),
            ("ftp://username:password123@ftp.server.com", "ftp://username:***FILTERED***@ftp.server.com")
        ]
        
        for original, expected in test_cases:
            filtered, _ = self.filter.filter_message(original)
            assert "pass" not in filtered or "***FILTERED***" in filtered
            assert "secret" not in filtered or "***FILTERED***" in filtered
            assert "password123" not in filtered
            assert "***FILTERED***" in filtered
    
    def test_json_credential_filtering(self):
        """Test filtering of credentials in JSON structures"""
        test_cases = [
            ('{"username": "admin", "password": "secret"}', '{"username": "admin", "password": "***FILTERED***"}'),
            ('{"auth_token": "abc123", "user_id": 456}', '{"auth_token": "***FILTERED***", "user_id": 456}'),
            ('{"config": {"api_key": "sk-123", "timeout": 30}}', '{"config": {"api_key": "***FILTERED***", "timeout": 30}}')
        ]
        
        for original, expected in test_cases:
            filtered, _ = self.filter.filter_message(original)
            assert "secret" not in filtered or "***FILTERED***" in filtered
            assert "abc123" not in filtered
            assert "sk-123" not in filtered
            assert "***FILTERED***" in filtered
            # Non-sensitive data should remain
            assert "admin" in filtered
            assert "456" in filtered
            assert "30" in filtered
    
    def test_false_positives(self):
        """Test that normal content is not incorrectly filtered"""
        safe_messages = [
            "User logged in successfully",
            "Processing 123 items",
            "Error: Connection timeout",
            "Starting browser automation",
            "Screenshot saved to ./logs/screenshot.png",
            "Rate limiting: waited 2.5s before request",
            "Found 5 posts on page"
        ]
        
        for message in safe_messages:
            filtered, _ = self.filter.filter_message(message)
            assert filtered == message  # Should be unchanged
    
    def test_pattern_detection_reporting(self):
        """Test that detected patterns are properly reported"""
        test_message = "Login with password=secret123 and token=abc789"
        filtered, detected_patterns = self.filter.filter_message(test_message)
        
        assert len(detected_patterns) >= 2  # Should detect both password and token
        assert any("password" in pattern.lower() for pattern in detected_patterns)
        assert any("token" in pattern.lower() for pattern in detected_patterns)
    
    def test_complex_filtering_scenarios(self):
        """Test complex real-world filtering scenarios"""
        complex_cases = [
            # Chrome debugging session
            (
                "Chrome session: cookies={'sessionid': 'abc123', 'datr': 'xyz789'} for https://user:pass@facebook.com",
                ["sessionid", "datr", "pass"]  # Should filter these values
            ),
            # Rate limiting log
            (
                "Rate limited request to https://api.facebook.com?access_token=EAABw... with response: {\"error\": \"rate_limit\"}",
                ["EAABw"]  # Should filter token
            ),
            # Configuration loading
            (
                "Loaded config: {'facebook': {'cookies_path': './data'}, 'auth': {'api_key': 'sk-123', 'secret': 'hidden'}}",
                ["sk-123", "hidden"]  # Should filter sensitive config values
            )
        ]
        
        for original, should_be_filtered in complex_cases:
            filtered, detected_patterns = self.filter.filter_message(original)
            
            for sensitive_value in should_be_filtered:
                assert sensitive_value not in filtered, f"'{sensitive_value}' should be filtered from: {filtered}"
            
            assert "***FILTERED***" in filtered
            assert len(detected_patterns) > 0


class TestSecureLogger:
    """Test suite for SecureLogger class"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.test_dir, "test.log")
        self.logger = SecureLogger("test_logger", log_file=self.log_file)
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_basic_logging(self):
        """Test basic logging functionality"""
        self.logger.info("Test info message")
        self.logger.warning("Test warning message")
        self.logger.error("Test error message")
        
        # Check that log file was created and contains messages
        assert os.path.exists(self.log_file)
        
        with open(self.log_file, 'r') as f:
            log_content = f.read()
        
        assert "Test info message" in log_content
        assert "Test warning message" in log_content
        assert "Test error message" in log_content
        assert "INFO" in log_content
        assert "WARNING" in log_content
        assert "ERROR" in log_content
    
    def test_sensitive_data_filtering(self):
        """Test that sensitive data is filtered in logs"""
        sensitive_messages = [
            "User login with password=secret123",
            "API call with token=abc789xyz",
            "Cookie value: sessionid=user_session_123"
        ]
        
        for message in sensitive_messages:
            self.logger.info(message)
        
        # Read log file and verify filtering
        with open(self.log_file, 'r') as f:
            log_content = f.read()
        
        # Sensitive values should not appear in logs
        assert "secret123" not in log_content
        assert "abc789xyz" not in log_content
        assert "user_session_123" not in log_content
        
        # But filtered indicators should be present
        assert "***FILTERED***" in log_content
    
    def test_security_event_logging(self):
        """Test security event logging"""
        event_type = "failed_login"
        event_data = {
            "user": "admin",
            "ip": "192.168.1.100",
            "timestamp": "2024-01-01T10:00:00Z",
            "password_attempt": "wrong_password"  # This should be filtered
        }
        
        self.logger.log_security_event(event_type, event_data)
        
        # Check security events file
        security_file = self.log_file.replace('.log', '_security.log')
        assert os.path.exists(security_file)
        
        with open(security_file, 'r') as f:
            security_content = f.read()
        
        assert "SECURITY_EVENT" in security_content
        assert event_type in security_content
        assert "admin" in security_content
        assert "192.168.1.100" in security_content
        
        # Sensitive data should be filtered
        assert "wrong_password" not in security_content
        assert "***FILTERED***" in security_content
    
    def test_log_rotation(self):
        """Test log file rotation when size limit is reached"""
        # Create a logger with small max file size for testing
        small_logger = SecureLogger("test_rotation", log_file=self.log_file, max_file_size=1024)  # 1KB
        
        # Write enough data to trigger rotation
        large_message = "A" * 200  # 200 character message
        for i in range(10):  # 2KB total
            small_logger.info(f"Large message {i}: {large_message}")
        
        # Should have created backup files
        backup_files = [f for f in os.listdir(self.test_dir) if f.endswith('.log.1')]
        assert len(backup_files) > 0
    
    def test_concurrent_logging(self):
        """Test thread-safe logging"""
        import threading
        import time
        
        def log_messages(thread_id):
            for i in range(10):
                self.logger.info(f"Thread {thread_id} message {i}")
                time.sleep(0.01)  # Small delay to encourage race conditions
        
        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=log_messages, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all messages were logged
        with open(self.log_file, 'r') as f:
            log_content = f.read()
        
        # Should have messages from all threads
        for thread_id in range(3):
            assert f"Thread {thread_id}" in log_content
    
    def test_log_level_filtering(self):
        """Test log level filtering"""
        # Create logger with WARNING level
        warning_logger = SecureLogger("warning_test", log_file=self.log_file, level="WARNING")
        
        warning_logger.debug("Debug message")
        warning_logger.info("Info message")
        warning_logger.warning("Warning message")
        warning_logger.error("Error message")
        
        with open(self.log_file, 'r') as f:
            log_content = f.read()
        
        # Only WARNING and ERROR should appear
        assert "Debug message" not in log_content
        assert "Info message" not in log_content
        assert "Warning message" in log_content
        assert "Error message" in log_content
    
    def test_structured_logging(self):
        """Test structured logging with additional data"""
        extra_data = {
            "user_id": "12345",
            "action": "login_attempt",
            "ip_address": "192.168.1.1",
            "api_key": "sk-secret123"  # Should be filtered
        }
        
        self.logger.info("User action performed", extra=extra_data)
        
        with open(self.log_file, 'r') as f:
            log_content = f.read()
        
        assert "user_id" in log_content
        assert "12345" in log_content
        assert "login_attempt" in log_content
        assert "192.168.1.1" in log_content
        
        # Sensitive data should be filtered
        assert "sk-secret123" not in log_content
    
    def test_exception_logging(self):
        """Test exception logging and formatting"""
        try:
            raise ValueError("Test exception with sensitive data: password=secret")
        except Exception as e:
            self.logger.exception("An error occurred", exc_info=e)
        
        with open(self.log_file, 'r') as f:
            log_content = f.read()
        
        assert "ValueError" in log_content
        assert "An error occurred" in log_content
        
        # Sensitive data in exception should be filtered
        assert "password=secret" not in log_content or "***FILTERED***" in log_content
    
    def test_performance_metrics(self):
        """Test performance impact of secure logging"""
        import time
        
        # Measure time for regular logging
        start_time = time.time()
        for i in range(100):
            self.logger.info(f"Performance test message {i}")
        regular_time = time.time() - start_time
        
        # Measure time for logging with sensitive data (requires filtering)
        start_time = time.time()
        for i in range(100):
            self.logger.info(f"Performance test with password=secret{i} and token=abc{i}")
        filtered_time = time.time() - start_time
        
        # Filtering should not cause excessive performance degradation
        # Allow up to 5x slower for filtering (should be much better in practice)
        assert filtered_time < regular_time * 5


class TestSecureLoggerIntegration:
    """Integration tests for secure logger with other systems"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_get_secure_logger_singleton(self):
        """Test get_secure_logger singleton behavior"""
        logger1 = get_secure_logger("test_module")
        logger2 = get_secure_logger("test_module")
        
        # Should return the same instance for the same name
        assert logger1 is logger2
        
        # Different names should return different instances
        logger3 = get_secure_logger("different_module")
        assert logger1 is not logger3
    
    def test_integration_with_rate_limiter(self):
        """Test secure logging integration with rate limiter"""
        from src.postwriter.security.rate_limiter import IntelligentRateLimiter, RequestType
        
        logger = get_secure_logger("rate_limiter_test")
        rate_limiter = IntelligentRateLimiter(storage_dir=self.test_dir)
        
        # Simulate rate limiter using secure logger
        sensitive_url = "https://user:password@facebook.com/api?token=secret123"
        
        logger.info(f"Making request to {sensitive_url}")
        rate_limiter.record_request(RequestType.PAGE_LOAD, sensitive_url, 200, "OK", 1.0)
        
        # Get statistics and log them
        stats = rate_limiter.get_statistics()
        logger.info("Rate limiter stats", extra=stats)
        
        # Verify sensitive data was filtered
        log_files = [f for f in os.listdir(self.test_dir) if f.endswith('.log')]
        assert len(log_files) > 0
        
        for log_file in log_files:
            with open(os.path.join(self.test_dir, log_file), 'r') as f:
                content = f.read()
                assert "password" not in content or "***FILTERED***" in content
                assert "secret123" not in content
    
    def test_browser_automation_logging(self):
        """Test secure logging in browser automation context"""
        logger = get_secure_logger("browser_automation")
        
        # Simulate browser automation logs with sensitive data
        session_data = {
            "cookies": [
                {"name": "sessionid", "value": "secret_session_123"},
                {"name": "auth_token", "value": "bearer_xyz789"}
            ],
            "user_agent": "PostWriter Bot 1.0"
        }
        
        logger.info("Browser session established", extra=session_data)
        logger.info("Navigating to https://user:pass@facebook.com/login")
        logger.warning("Authentication required, cookies: sessionid=abc123")
        
        # All sensitive data should be filtered while preserving useful information
        log_files = [f for f in os.listdir(self.test_dir) if f.endswith('.log')]
        for log_file in log_files:
            with open(os.path.join(self.test_dir, log_file), 'r') as f:
                content = f.read()
                
                # Sensitive values should be filtered
                assert "secret_session_123" not in content
                assert "bearer_xyz789" not in content
                assert "pass" not in content or "***FILTERED***" in content
                assert "abc123" not in content
                
                # Useful information should remain
                assert "PostWriter Bot 1.0" in content
                assert "Browser session established" in content
    
    def test_audit_trail_generation(self):
        """Test generation of security audit trails"""
        logger = get_secure_logger("audit_test")
        
        # Simulate security-relevant events
        security_events = [
            ("authentication_success", {"user": "admin", "method": "password"}),
            ("privilege_escalation", {"user": "admin", "action": "access_secure_storage"}),
            ("data_access", {"user": "admin", "resource": "encrypted_sessions", "api_key": "secret123"}),
            ("security_violation", {"event": "rate_limit_exceeded", "details": "password=attempt123"})
        ]
        
        for event_type, event_data in security_events:
            logger.log_security_event(event_type, event_data)
        
        # Check security audit file
        security_files = [f for f in os.listdir(self.test_dir) if 'security' in f and f.endswith('.log')]
        assert len(security_files) > 0
        
        with open(os.path.join(self.test_dir, security_files[0]), 'r') as f:
            security_content = f.read()
        
        # All events should be logged
        for event_type, _ in security_events:
            assert event_type in security_content
        
        # Sensitive data should be filtered
        assert "secret123" not in security_content
        assert "attempt123" not in security_content
        assert "***FILTERED***" in security_content
        
        # Non-sensitive data should remain
        assert "admin" in security_content
        assert "encrypted_sessions" in security_content


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])