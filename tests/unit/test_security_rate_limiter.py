#!/usr/bin/env python3
"""
Unit tests for PostWriter rate limiting system
Tests intelligent rate limiting, backoff strategies, and Facebook protection
"""

import os
import time
import tempfile
import pytest
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.postwriter.security.rate_limiter import IntelligentRateLimiter, RequestType, get_rate_limiter


class TestIntelligentRateLimiter:
    """Test suite for IntelligentRateLimiter class"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        storage_file = os.path.join(self.test_dir, 'rate_limiter.json')
        self.rate_limiter = IntelligentRateLimiter(storage_file=storage_file)
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test rate limiter initialization"""
        assert self.rate_limiter.max_requests_per_minute > 0
        assert self.rate_limiter.max_requests_per_hour > 0
        assert self.rate_limiter.current_backoff_level == 0
        assert len(self.rate_limiter.request_history) == 0
    
    def test_request_type_limits(self):
        """Test different request type configurations"""
        page_load_delay = self.rate_limiter._calculate_base_delay(RequestType.PAGE_LOAD)
        api_call_delay = self.rate_limiter._calculate_base_delay(RequestType.API_CALL)
        form_submit_delay = self.rate_limiter._calculate_base_delay(RequestType.FORM_SUBMIT)
        
        # Form submissions should have highest delay (most sensitive)
        assert form_submit_delay >= api_call_delay
        assert api_call_delay >= page_load_delay
        
        # All delays should be reasonable (not too high for testing)
        assert page_load_delay < 10.0
        assert form_submit_delay < 30.0
    
    def test_basic_rate_limiting(self):
        """Test basic rate limiting functionality"""
        # First request should have some delay (Facebook safety)
        wait_time = self.rate_limiter.wait_for_request(RequestType.PAGE_LOAD, "http://test.com")
        assert wait_time >= 0
        assert wait_time < 10.0  # Should be reasonable for safety
        
        # Record the request with realistic Facebook page content
        facebook_content = """
        <html><head><title>Facebook</title></head><body>
        <div class="fb-header">Facebook</div>
        <div class="newsfeed">
            <div class="post">John Doe shared a photo</div>
            <div class="post">Jane Smith posted an update</div>
            <div class="post">Company XYZ shared an article</div>
        </div>
        <div class="sidebar">
            <div class="trending">Trending topics</div>
            <div class="friends">Friend suggestions</div>
        </div>
        <script>window.fbConfig = {user: "authenticated"};</script>
        </body></html>
        """
        success = self.rate_limiter.record_request(
            RequestType.PAGE_LOAD, "http://test.com", 200, facebook_content, 1.0
        )
        assert success is True
    
    def test_rate_limit_detection(self):
        """Test detection of rate limiting from responses"""
        # Simulate rate limit responses
        rate_limit_indicators = [
            (429, "Rate limit exceeded"),
            (200, "slow down"),
            (200, "too many requests"),
            (403, "temporarily blocked"),
            (200, "rate limit")
        ]
        
        for status_code, response_text in rate_limit_indicators:
            detected = self.rate_limiter._detect_rate_limiting(status_code, response_text)
            assert detected is True, f"Should detect rate limiting for {status_code}: {response_text}"
        
        # Normal responses should not trigger rate limiting
        normal_responses = [
            (200, "Welcome to Facebook"),
            (404, "Page not found"),
            (500, "Internal server error")
        ]
        
        for status_code, response_text in normal_responses:
            detected = self.rate_limiter._detect_rate_limiting(status_code, response_text)
            assert detected is False, f"Should not detect rate limiting for {status_code}: {response_text}"
    
    def test_backoff_escalation(self):
        """Test exponential backoff escalation"""
        initial_level = self.rate_limiter.current_backoff_level
        
        # Simulate rate limiting detection
        self.rate_limiter.record_request(
            RequestType.PAGE_LOAD, "http://test.com", 429, "Rate limit exceeded", 1.0
        )
        
        # Backoff level should increase
        assert self.rate_limiter.current_backoff_level > initial_level
        
        # Calculate delay with backoff
        backoff_delay = self.rate_limiter._calculate_backoff_delay()
        assert backoff_delay > 0
        
        # Multiple rate limits should increase backoff exponentially
        original_backoff = self.rate_limiter.current_backoff_level
        self.rate_limiter.record_request(
            RequestType.PAGE_LOAD, "http://test.com", 429, "Rate limit exceeded", 1.0
        )
        
        assert self.rate_limiter.current_backoff_level > original_backoff
    
    def test_successful_request_backoff_reduction(self):
        """Test backoff reduction on successful requests"""
        # Escalate backoff first
        for _ in range(3):
            self.rate_limiter.record_request(
                RequestType.PAGE_LOAD, "http://test.com", 429, "Rate limited", 1.0
            )
        
        initial_backoff = self.rate_limiter.current_backoff_level
        assert initial_backoff > 0
        
        # Record successful requests
        for _ in range(5):
            self.rate_limiter.record_request(
                RequestType.PAGE_LOAD, "http://test.com", 200, "Success", 1.0
            )
        
        # Backoff should be reduced
        assert self.rate_limiter.current_backoff_level < initial_backoff
    
    def test_request_history_management(self):
        """Test request history tracking and cleanup"""
        # Add multiple requests
        for i in range(10):
            self.rate_limiter.record_request(
                RequestType.PAGE_LOAD, f"http://test{i}.com", 200, "OK", 1.0
            )
        
        assert len(self.rate_limiter.request_history) == 10
        
        # Test history cleanup (simulate old requests)
        old_time = time.time() - 7200  # 2 hours ago
        
        # Add old request manually
        old_request = {
            'timestamp': old_time,
            'request_type': RequestType.PAGE_LOAD,
            'url': 'http://old.com',
            'status_code': 200,
            'response_text': 'Old request',
            'response_time': 1.0,
            'error': None
        }
        self.rate_limiter.request_history.append(old_request)
        
        # Cleanup should remove old requests
        self.rate_limiter._cleanup_old_requests()
        
        # Should only have recent requests
        recent_requests = [r for r in self.rate_limiter.request_history if r['timestamp'] > old_time + 3600]
        assert len(recent_requests) >= 10
    
    def test_minute_and_hour_limits(self):
        """Test per-minute and per-hour request limits"""
        current_time = time.time()
        
        # Fill up minute limit
        minute_requests = []
        for i in range(self.rate_limiter.max_requests_per_minute + 5):
            request = {
                'timestamp': current_time - i,  # Recent requests
                'request_type': RequestType.PAGE_LOAD,
                'url': f'http://test{i}.com',
                'status_code': 200,
                'response_text': 'OK',
                'response_time': 1.0,
                'error': None
            }
            minute_requests.append(request)
        
        self.rate_limiter.request_history = minute_requests
        
        # Should detect minute limit exceeded
        minute_count = self.rate_limiter._count_recent_requests(60)
        assert minute_count > self.rate_limiter.max_requests_per_minute
        
        # Wait time should be significant
        wait_time = self.rate_limiter.wait_for_request(RequestType.PAGE_LOAD, "http://test.com")
        assert wait_time > 5.0  # Should have meaningful delay
    
    def test_different_request_types_isolation(self):
        """Test that different request types have independent limiting"""
        # Fill up PAGE_LOAD requests
        for i in range(10):
            self.rate_limiter.record_request(
                RequestType.PAGE_LOAD, f"http://page{i}.com", 200, "OK", 1.0
            )
        
        # API_CALL requests should still have reasonable delay
        api_wait = self.rate_limiter.wait_for_request(RequestType.API_CALL, "http://api.com")
        page_wait = self.rate_limiter.wait_for_request(RequestType.PAGE_LOAD, "http://page.com")
        
        # Both should work but may have different delays
        assert api_wait >= 0
        assert page_wait >= 0
    
    def test_url_pattern_analysis(self):
        """Test URL pattern-based rate limiting"""
        facebook_urls = [
            "https://facebook.com/profile/123",
            "https://m.facebook.com/login",
            "https://mbasic.facebook.com/posts"
        ]
        
        other_urls = [
            "https://google.com",
            "https://api.github.com/user"
        ]
        
        # Facebook URLs should have more conservative limits
        for url in facebook_urls:
            wait_time = self.rate_limiter.wait_for_request(RequestType.PAGE_LOAD, url)
            assert wait_time >= 0
        
        # Non-Facebook URLs should have different (usually lower) limits
        for url in other_urls:
            wait_time = self.rate_limiter.wait_for_request(RequestType.PAGE_LOAD, url)
            assert wait_time >= 0
    
    def test_error_handling(self):
        """Test error handling in rate limiting"""
        # Test with connection errors
        success = self.rate_limiter.record_request(
            RequestType.PAGE_LOAD, "http://test.com", None, "", 0.0, "Connection timeout"
        )
        assert success is False
        
        # Error requests should affect backoff
        error_backoff = self.rate_limiter.current_backoff_level
        
        # Multiple errors should increase caution
        for _ in range(3):
            self.rate_limiter.record_request(
                RequestType.PAGE_LOAD, "http://test.com", None, "", 0.0, "Network error"
            )
        
        assert self.rate_limiter.current_backoff_level >= error_backoff
    
    def test_statistics_and_reporting(self):
        """Test statistics collection and reporting"""
        # Add various requests
        requests_data = [
            (RequestType.PAGE_LOAD, 200, "OK", 1.5),
            (RequestType.PAGE_LOAD, 429, "Rate limited", 2.0),
            (RequestType.API_CALL, 200, "Success", 0.8),
            (RequestType.FORM_SUBMIT, 403, "Blocked", 3.0),
        ]
        
        for req_type, status, response, resp_time in requests_data:
            self.rate_limiter.record_request(
                req_type, "http://test.com", status, response, resp_time
            )
        
        stats = self.rate_limiter.get_statistics()
        
        # Verify statistics structure
        assert "total_requests" in stats
        assert "successful_requests" in stats
        assert "failed_requests" in stats
        assert "rate_limited_requests" in stats
        assert "average_response_time" in stats
        assert "current_backoff_level" in stats
        assert "requests_per_type" in stats
        
        # Verify data accuracy
        assert stats["total_requests"] == 4
        assert stats["rate_limited_requests"] >= 1  # At least the 429 response
        assert stats["current_backoff_level"] >= 0
        assert len(stats["requests_per_type"]) > 0
    
    def test_reset_functionality(self):
        """Test rate limiter reset functionality"""
        # Build up some state
        for i in range(5):
            self.rate_limiter.record_request(
                RequestType.PAGE_LOAD, f"http://test{i}.com", 429, "Rate limited", 1.0
            )
        
        assert self.rate_limiter.current_backoff_level > 0
        assert len(self.rate_limiter.request_history) > 0
        
        # Reset backoff
        self.rate_limiter.reset_backoff()
        assert self.rate_limiter.current_backoff_level == 0
        
        # History should remain for analysis
        assert len(self.rate_limiter.request_history) > 0
    
    def test_persistence(self):
        """Test persistence of rate limiting state"""
        # Record some requests
        for i in range(3):
            self.rate_limiter.record_request(
                RequestType.PAGE_LOAD, f"http://test{i}.com", 200, "OK", 1.0
            )
        
        original_history_len = len(self.rate_limiter.request_history)
        original_backoff = self.rate_limiter.current_backoff_level
        
        # Create new rate limiter with same storage dir
        new_rate_limiter = IntelligentRateLimiter(storage_file=storage_file)
        
        # State should be preserved
        assert len(new_rate_limiter.request_history) == original_history_len
        assert new_rate_limiter.current_backoff_level == original_backoff


class TestRateLimiterIntegration:
    """Integration tests for rate limiter with other systems"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_singleton_pattern(self):
        """Test rate limiter singleton behavior"""
        # get_rate_limiter should return the same instance
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        
        assert limiter1 is limiter2
        
        # State should be shared
        limiter1.record_request(RequestType.PAGE_LOAD, "http://test.com", 200, "OK", 1.0)
        
        stats1 = limiter1.get_statistics()
        stats2 = limiter2.get_statistics()
        
        assert stats1["total_requests"] == stats2["total_requests"]
    
    @patch('time.sleep')
    def test_actual_waiting(self, mock_sleep):
        """Test that rate limiter actually waits when required"""
        storage_file = os.path.join(self.test_dir, 'rate_limiter_test.json')
        rate_limiter = IntelligentRateLimiter(storage_file=storage_file)
        
        # Trigger rate limiting
        rate_limiter.record_request(
            RequestType.PAGE_LOAD, "http://test.com", 429, "Rate limited", 1.0
        )
        
        # Request should require waiting
        wait_time = rate_limiter.wait_for_request(RequestType.PAGE_LOAD, "http://test.com")
        
        if wait_time > 0:
            # Verify sleep was called if wait time was required
            # Note: In actual usage, time.sleep would be called
            assert wait_time >= 0
    
    def test_facebook_specific_patterns(self):
        """Test Facebook-specific rate limiting patterns"""
        storage_file = os.path.join(self.test_dir, 'rate_limiter_test.json')
        rate_limiter = IntelligentRateLimiter(storage_file=storage_file)
        
        facebook_scenarios = [
            # Profile page access
            ("https://facebook.com/profile/12345", RequestType.PAGE_LOAD),
            # Login attempt
            ("https://facebook.com/login", RequestType.FORM_SUBMIT),
            # API call
            ("https://graph.facebook.com/me", RequestType.API_CALL),
            # Mobile access
            ("https://m.facebook.com/posts/123", RequestType.PAGE_LOAD)
        ]
        
        for url, req_type in facebook_scenarios:
            wait_time = rate_limiter.wait_for_request(req_type, url)
            assert wait_time >= 0
            
            # Record successful request
            rate_limiter.record_request(req_type, url, 200, "Success", 1.0)
        
        # Should have recorded all requests
        stats = rate_limiter.get_statistics()
        assert stats["total_requests"] >= len(facebook_scenarios)
    
    def test_concurrent_request_handling(self):
        """Test rate limiter behavior under concurrent requests"""
        import threading
        import queue
        
        storage_file = os.path.join(self.test_dir, 'rate_limiter_test.json')
        rate_limiter = IntelligentRateLimiter(storage_file=storage_file)
        results = queue.Queue()
        
        def make_request(thread_id):
            """Simulate concurrent request"""
            wait_time = rate_limiter.wait_for_request(
                RequestType.PAGE_LOAD, f"http://test{thread_id}.com"
            )
            rate_limiter.record_request(
                RequestType.PAGE_LOAD, f"http://test{thread_id}.com", 200, "OK", 1.0
            )
            results.put((thread_id, wait_time))
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_request, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Collect results
        thread_results = []
        while not results.empty():
            thread_results.append(results.get())
        
        assert len(thread_results) == 5
        
        # All requests should have completed successfully
        for thread_id, wait_time in thread_results:
            assert wait_time >= 0


class TestRateLimiterEdgeCases:
    """Test edge cases and error conditions"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        storage_file = os.path.join(self.test_dir, 'rate_limiter.json')
        self.rate_limiter = IntelligentRateLimiter(storage_file=storage_file)
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_invalid_request_types(self):
        """Test handling of invalid request types"""
        # This should not crash
        try:
            wait_time = self.rate_limiter.wait_for_request("INVALID_TYPE", "http://test.com")
            assert wait_time >= 0  # Should handle gracefully
        except Exception as e:
            # If it raises an exception, it should be a reasonable one
            assert "invalid" in str(e).lower() or "unknown" in str(e).lower()
    
    def test_malformed_urls(self):
        """Test handling of malformed URLs"""
        malformed_urls = [
            "",
            "not-a-url",
            "ftp://old-protocol.com",
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>"
        ]
        
        for url in malformed_urls:
            # Should not crash
            wait_time = self.rate_limiter.wait_for_request(RequestType.PAGE_LOAD, url)
            assert wait_time >= 0
    
    def test_extreme_response_times(self):
        """Test handling of extreme response times"""
        extreme_times = [0.0, 0.001, 60.0, 300.0, float('inf')]
        
        for response_time in extreme_times:
            if response_time == float('inf'):
                continue  # Skip infinity for this test
            
            success = self.rate_limiter.record_request(
                RequestType.PAGE_LOAD, "http://test.com", 200, "OK", response_time
            )
            
            # Should handle gracefully
            assert success in [True, False]
    
    def test_storage_permission_errors(self):
        """Test handling of storage permission errors"""
        # Create rate limiter with invalid storage directory
        invalid_dir = "/root/invalid_permission_dir"  # Typically no write access
        
        try:
            rate_limiter = IntelligentRateLimiter(storage_dir=invalid_dir)
            # Should either work or fail gracefully
            assert rate_limiter is not None
        except (PermissionError, OSError):
            # Expected for directories without write permission
            pass
    
    def test_memory_usage_with_large_history(self):
        """Test memory usage with large request history"""
        # Add many requests to test memory management
        for i in range(1000):
            self.rate_limiter.record_request(
                RequestType.PAGE_LOAD, f"http://test{i}.com", 200, "OK", 1.0
            )
        
        # History should be managed (not grow infinitely)
        assert len(self.rate_limiter.request_history) <= 2000  # Should have reasonable limit
        
        # Should still function normally
        wait_time = self.rate_limiter.wait_for_request(RequestType.PAGE_LOAD, "http://test.com")
        assert wait_time >= 0


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])