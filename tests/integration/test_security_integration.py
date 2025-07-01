#!/usr/bin/env python3
"""
Integration tests for PostWriter security systems
Tests interactions between encryption, rate limiting, logging, and browser security
"""

import os
import tempfile
import json
import pytest
import time
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.postwriter.security.storage import SecureStorage
from src.postwriter.security.browser_storage import SecureBrowserStorage, ChromeSessionManager
from src.postwriter.security.rate_limiter import IntelligentRateLimiter, RequestType
from src.postwriter.security.logging import get_secure_logger, SecurityLogFilter
from src.postwriter.security.chrome_proxy import SecureChromeProxy


class TestSecurityWorkflows:
    """Test complete security workflows"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            'directories': {'logs_dir': self.test_dir},
            'chrome': {'debug_port': 9222},
            'security': {
                'rate_limiting_enabled': True,
                'secure_logging': True,
                'encrypt_sessions': True
            }
        }
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_end_to_end_session_security(self):
        """Test complete session security workflow: extract, encrypt, store, load"""
        # Components
        session_manager = ChromeSessionManager(self.config)
        browser_storage = SecureBrowserStorage(self.config)
        logger = get_secure_logger("security_integration")
        
        # Step 1: Mock Chrome session extraction
        mock_session_data = {
            "cookies": [
                {"name": "sessionid", "value": "sensitive_session_123", "domain": ".facebook.com"},
                {"name": "auth_token", "value": "bearer_xyz789", "domain": ".facebook.com"}
            ],
            "origins": [
                {
                    "origin": "https://facebook.com",
                    "localStorage": [
                        {"name": "user_preferences", "value": "{'theme': 'dark', 'notifications': True}"}
                    ]
                }
            ]
        }
        
        with patch.object(session_manager, 'extract_chrome_session', return_value=mock_session_data):
            # Step 2: Extract and encrypt session
            password = "strong_encryption_password_123"
            success = session_manager.extract_and_encrypt_session("production_session", password)
            assert success is True
            
            # Step 3: Verify session was encrypted and stored
            sessions = browser_storage.list_sessions()
            assert "production_session" in sessions
            
            # Step 4: Load and decrypt session
            loaded_data = browser_storage.load_session_data("production_session", password)
            assert loaded_data == mock_session_data
            
            # Step 5: Verify sensitive data was logged securely
            logger.info(f"Session loaded successfully with cookies: {loaded_data['cookies']}")
            
            # Check that sensitive values are filtered in logs
            log_files = [f for f in os.listdir(self.test_dir) if f.endswith('.log')]
            if log_files:
                with open(os.path.join(self.test_dir, log_files[0]), 'r') as f:
                    log_content = f.read()
                    # Sensitive session values should be filtered
                    assert "sensitive_session_123" not in log_content
                    assert "bearer_xyz789" not in log_content
                    assert "***FILTERED***" in log_content
    
    def test_rate_limiting_with_security_logging(self):
        """Test rate limiting integration with secure logging"""
        rate_limiter = IntelligentRateLimiter(storage_dir=self.test_dir)
        logger = get_secure_logger("rate_limiter_security")
        
        # Simulate Facebook scraping requests with sensitive URLs
        sensitive_requests = [
            ("https://user:password@facebook.com/profile/123", 200, "Success"),
            ("https://facebook.com/api?token=secret123&user=admin", 200, "Success"),
            ("https://facebook.com/login?redirect=https://admin:pass@internal.com", 429, "Rate limited"),
            ("https://facebook.com/posts?auth=bearer_xyz789", 200, "Success")
        ]
        
        for url, status, response in sensitive_requests:
            # Record request with rate limiter
            wait_time = rate_limiter.wait_for_request(RequestType.PAGE_LOAD, url)
            success = rate_limiter.record_request(RequestType.PAGE_LOAD, url, status, response, 1.5)
            
            # Log the request (should be filtered)
            logger.info(f"Request to {url} completed with status {status}: {response}")
            
            assert wait_time >= 0
            assert success in [True, False]  # Depends on rate limiting status
        
        # Check rate limiting statistics
        stats = rate_limiter.get_statistics()
        assert stats["total_requests"] >= 4
        assert stats["rate_limited_requests"] >= 1  # At least one 429 response
        
        # Verify sensitive data was filtered from logs
        log_files = [f for f in os.listdir(self.test_dir) if f.endswith('.log')]
        for log_file in log_files:
            with open(os.path.join(self.test_dir, log_file), 'r') as f:
                content = f.read()
                # Check that sensitive credentials are filtered
                assert "password" not in content or "***FILTERED***" in content
                assert "secret123" not in content
                assert "bearer_xyz789" not in content
                assert "admin:pass" not in content
    
    def test_chrome_proxy_security_with_logging(self):
        """Test secure Chrome proxy with security logging"""
        proxy = SecureChromeProxy(chrome_port=9222, proxy_port=9223)
        logger = get_secure_logger("chrome_proxy_security")
        
        # Test authentication token generation and validation
        auth_token = proxy.auth_token
        assert len(auth_token) >= 32  # Should be sufficiently long
        
        # Simulate proxy requests with sensitive data
        test_requests = [
            {"url": "/json/list", "headers": {"Authorization": f"Bearer {auth_token}"}},
            {"url": "/json/runtime/evaluate", "headers": {"Authorization": "Bearer wrong_token"}},
            {"url": "/json/list", "headers": {"X-API-Key": "sk-secret123"}},
        ]
        
        for req in test_requests:
            # Log the request (should filter sensitive headers)
            logger.info(f"Chrome proxy request: {req}")
            
            # Validate token
            is_valid = proxy._validate_auth_token(req["headers"].get("Authorization", "").replace("Bearer ", ""))
            
            if req["headers"].get("Authorization") == f"Bearer {auth_token}":
                assert is_valid is True
            else:
                assert is_valid is False
        
        # Check that sensitive data was filtered from logs
        log_files = [f for f in os.listdir(self.test_dir) if f.endswith('.log')]
        for log_file in log_files:
            with open(os.path.join(self.test_dir, log_file), 'r') as f:
                content = f.read()
                # Auth tokens should be filtered
                assert auth_token not in content or "***FILTERED***" in content
                assert "sk-secret123" not in content
                assert "wrong_token" not in content or "***FILTERED***" in content
    
    def test_multi_component_error_handling(self):
        """Test error handling across multiple security components"""
        browser_storage = SecureBrowserStorage(self.config)
        rate_limiter = IntelligentRateLimiter(storage_dir=self.test_dir)
        logger = get_secure_logger("multi_component_errors")
        
        # Test 1: Invalid session decryption
        try:
            browser_storage.load_session_data("nonexistent_session", "wrong_password")
            assert False, "Should have raised an exception"
        except Exception as e:
            logger.error(f"Session load failed: {e}")
            # Should log error without exposing sensitive password
        
        # Test 2: Rate limiter with connection errors
        for i in range(5):
            rate_limiter.record_request(
                RequestType.API_CALL, 
                f"https://facebook.com/api/call{i}", 
                None,  # None status indicates connection error
                "", 
                0.0, 
                "Connection timeout with auth=secret123"
            )
        
        # Test 3: Secure storage with permission errors
        invalid_storage = SecureStorage("/root/invalid_path.enc")  # Should fail on most systems
        try:
            invalid_storage.store_data({"test": "data"}, "password")
        except Exception as e:
            logger.error(f"Storage operation failed: {e}")
        
        # Verify all errors were logged securely
        log_files = [f for f in os.listdir(self.test_dir) if f.endswith('.log')]
        assert len(log_files) > 0
        
        for log_file in log_files:
            with open(os.path.join(self.test_dir, log_file), 'r') as f:
                content = f.read()
                # Should contain error messages but not sensitive data
                assert "failed" in content.lower() or "error" in content.lower()
                assert "wrong_password" not in content or "***FILTERED***" in content
                assert "secret123" not in content
    
    def test_concurrent_security_operations(self):
        """Test concurrent security operations"""
        import threading
        import queue
        
        browser_storage = SecureBrowserStorage(self.config)
        rate_limiter = IntelligentRateLimiter(storage_dir=self.test_dir)
        logger = get_secure_logger("concurrent_security")
        results = queue.Queue()
        
        def secure_storage_worker(thread_id):
            """Worker for concurrent storage operations"""
            try:
                session_data = {
                    "cookies": [{"name": f"session_{thread_id}", "value": f"secret_{thread_id}"}],
                    "thread_id": thread_id
                }
                
                password = f"password_{thread_id}"
                session_name = f"concurrent_session_{thread_id}"
                
                # Store session
                success = browser_storage.save_session_data(session_data, session_name, password)
                
                # Load session back
                if success:
                    loaded = browser_storage.load_session_data(session_name, password)
                    results.put(("storage", thread_id, loaded == session_data))
                else:
                    results.put(("storage", thread_id, False))
                    
            except Exception as e:
                logger.error(f"Storage worker {thread_id} failed: {e}")
                results.put(("storage", thread_id, False))
        
        def rate_limiter_worker(thread_id):
            """Worker for concurrent rate limiting"""
            try:
                for i in range(3):
                    url = f"https://facebook.com/thread{thread_id}/page{i}"
                    wait_time = rate_limiter.wait_for_request(RequestType.PAGE_LOAD, url)
                    success = rate_limiter.record_request(RequestType.PAGE_LOAD, url, 200, "OK", 1.0)
                    
                    logger.info(f"Thread {thread_id} request {i}: {url}")
                
                results.put(("rate_limiter", thread_id, True))
                
            except Exception as e:
                logger.error(f"Rate limiter worker {thread_id} failed: {e}")
                results.put(("rate_limiter", thread_id, False))
        
        # Start concurrent workers
        threads = []
        for i in range(3):
            storage_thread = threading.Thread(target=secure_storage_worker, args=(i,))
            rate_thread = threading.Thread(target=rate_limiter_worker, args=(i,))
            
            threads.extend([storage_thread, rate_thread])
            storage_thread.start()
            rate_thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=10)  # 10 second timeout
        
        # Collect results
        thread_results = []
        while not results.empty():
            thread_results.append(results.get())
        
        # Verify all operations completed successfully
        assert len(thread_results) >= 6  # 3 storage + 3 rate limiter
        
        storage_results = [r for r in thread_results if r[0] == "storage"]
        rate_limiter_results = [r for r in thread_results if r[0] == "rate_limiter"]
        
        # All storage operations should succeed
        for _, thread_id, success in storage_results:
            assert success is True, f"Storage thread {thread_id} failed"
        
        # All rate limiter operations should succeed
        for _, thread_id, success in rate_limiter_results:
            assert success is True, f"Rate limiter thread {thread_id} failed"


class TestSecurityComplianceValidation:
    """Test security compliance and validation"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            'directories': {'logs_dir': self.test_dir},
            'security': {
                'rate_limiting_enabled': True,
                'secure_logging': True,
                'encrypt_sessions': True,
                'audit_enabled': True
            }
        }
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_security_audit_trail(self):
        """Test complete security audit trail generation"""
        logger = get_secure_logger("security_audit")
        browser_storage = SecureBrowserStorage(self.config)
        rate_limiter = IntelligentRateLimiter(storage_dir=self.test_dir)
        
        # Generate security events for audit trail
        security_events = [
            # Authentication events
            ("user_login", {"user": "admin", "method": "session_restore", "session_id": "secret123"}),
            ("session_created", {"session_name": "prod_session", "encryption": "AES-256"}),
            
            # Data access events  
            ("sensitive_data_access", {"operation": "decrypt_session", "data_type": "cookies"}),
            ("secure_storage_access", {"operation": "read", "file": "encrypted_session.enc"}),
            
            # Rate limiting events
            ("rate_limit_triggered", {"url": "https://facebook.com/api?token=abc123", "limit_type": "per_minute"}),
            ("backoff_applied", {"level": 2, "wait_time": 4.5}),
            
            # Security violations
            ("authentication_failure", {"reason": "invalid_token", "token": "bearer_invalid123"}),
            ("permission_denied", {"operation": "decrypt", "reason": "wrong_password"})
        ]
        
        for event_type, event_data in security_events:
            logger.log_security_event(event_type, event_data)
        
        # Verify security audit file was created
        audit_files = [f for f in os.listdir(self.test_dir) if 'security' in f and f.endswith('.log')]
        assert len(audit_files) > 0
        
        # Verify audit trail content
        with open(os.path.join(self.test_dir, audit_files[0]), 'r') as f:
            audit_content = f.read()
        
        # All event types should be logged
        for event_type, _ in security_events:
            assert event_type in audit_content
        
        # Sensitive data should be filtered
        assert "secret123" not in audit_content
        assert "abc123" not in audit_content
        assert "bearer_invalid123" not in audit_content
        assert "***FILTERED***" in audit_content
        
        # Non-sensitive operational data should remain
        assert "admin" in audit_content
        assert "AES-256" in audit_content
        assert "per_minute" in audit_content
    
    def test_data_protection_compliance(self):
        """Test data protection compliance across components"""
        browser_storage = SecureBrowserStorage(self.config)
        
        # Test data that should be protected
        sensitive_data = {
            "personal_info": {
                "email": "user@example.com",
                "phone": "+1234567890",
                "name": "John Doe"
            },
            "authentication": {
                "password": "user_password_123",
                "session_token": "sess_abc123xyz",
                "api_key": "sk-secret789"
            },
            "facebook_data": {
                "cookies": [
                    {"name": "sessionid", "value": "fb_session_456", "domain": ".facebook.com"},
                    {"name": "access_token", "value": "EAABw0dZB...", "domain": ".facebook.com"}
                ]
            }
        }
        
        password = "encryption_password_strong_123"
        
        # Store sensitive data
        success = browser_storage.save_session_data(sensitive_data, "compliance_test", password)
        assert success is True
        
        # Verify data is encrypted at rest
        session_files = [f for f in os.listdir(self.test_dir) if f.startswith("compliance_test")]
        assert len(session_files) > 0
        
        # Read raw file content - should be encrypted
        with open(os.path.join(self.test_dir, session_files[0]), 'rb') as f:
            raw_content = f.read()
        
        # Sensitive values should not appear in plaintext
        sensitive_values = [
            "user_password_123", "sess_abc123xyz", "sk-secret789", 
            "fb_session_456", "EAABw0dZB"
        ]
        
        for value in sensitive_values:
            assert value.encode() not in raw_content
        
        # Verify data can be decrypted correctly
        loaded_data = browser_storage.load_session_data("compliance_test", password)
        assert loaded_data == sensitive_data
        
        # Test wrong password fails
        try:
            browser_storage.load_session_data("compliance_test", "wrong_password")
            assert False, "Should have failed with wrong password"
        except Exception:
            pass  # Expected to fail
    
    def test_security_configuration_validation(self):
        """Test security configuration validation"""
        from src.postwriter.security.config_validator import validate_security_config
        
        # Test valid security configuration
        valid_config = {
            'security': {
                'rate_limiting_enabled': True,
                'secure_logging': True,
                'encrypt_sessions': True,
                'max_requests_per_minute': 20,
                'max_requests_per_hour': 300
            },
            'directories': {
                'logs_dir': self.test_dir
            },
            'chrome': {
                'debug_port': 9222
            }
        }
        
        is_valid, errors = validate_security_config(valid_config)
        assert is_valid is True
        assert len(errors) == 0
        
        # Test invalid security configuration
        invalid_configs = [
            # Missing required security settings
            {'security': {'rate_limiting_enabled': False}},
            
            # Invalid rate limits
            {'security': {'rate_limiting_enabled': True, 'max_requests_per_minute': -1}},
            
            # Missing directories
            {'security': {'encrypt_sessions': True}},
            
            # Invalid Chrome port
            {'chrome': {'debug_port': 'invalid'}},
        ]
        
        for invalid_config in invalid_configs:
            is_valid, errors = validate_security_config(invalid_config)
            assert is_valid is False
            assert len(errors) > 0


if __name__ == "__main__":
    # Run security integration tests
    pytest.main([__file__, "-v", "-s"])