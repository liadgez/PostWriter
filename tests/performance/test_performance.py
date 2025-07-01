#!/usr/bin/env python3
"""
Performance tests for PostWriter components
Tests speed, memory usage, and scalability of security and browser systems
"""

import os
import time
import tempfile
import pytest
import asyncio
import threading
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.postwriter.security.rate_limiter import IntelligentRateLimiter, RequestType
from src.postwriter.security.storage import SecureStorage
from src.postwriter.security.logging import get_secure_logger
from src.postwriter.testing.browser_manager import EnhancedBrowserManager, BrowserEngine


class TestSecurityPerformance:
    """Performance tests for security components"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_rate_limiter_performance(self):
        """Test rate limiter performance under load"""
        rate_limiter = IntelligentRateLimiter(storage_dir=self.test_dir)
        
        # Measure performance for many requests
        num_requests = 1000
        start_time = time.time()
        
        for i in range(num_requests):
            wait_time = rate_limiter.wait_for_request(RequestType.PAGE_LOAD, f"https://test{i}.com")
            rate_limiter.record_request(RequestType.PAGE_LOAD, f"https://test{i}.com", 200, "OK", 0.5)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Performance assertions
        assert total_time < 10.0, f"Rate limiter too slow: {total_time:.2f}s for {num_requests} requests"
        
        # Should handle at least 100 requests per second
        requests_per_second = num_requests / total_time
        assert requests_per_second > 100, f"Too slow: {requests_per_second:.1f} req/s"
        
        # Memory usage should be reasonable
        stats = rate_limiter.get_statistics()
        assert stats["total_requests"] == num_requests
    
    def test_encryption_performance(self):
        """Test encryption/decryption performance"""
        storage = SecureStorage(os.path.join(self.test_dir, 'perf_test.enc'))
        password = "performance_test_password"
        
        # Test data of various sizes
        test_sizes = [
            ("small", {"key": "value"}),
            ("medium", {"data": "x" * 1000}),  # 1KB
            ("large", {"data": "x" * 100000})  # 100KB
        ]
        
        for size_name, test_data in test_sizes:
            # Measure encryption time
            start_time = time.time()
            success = storage.store_data(test_data, password)
            encrypt_time = time.time() - start_time
            
            assert success is True
            assert encrypt_time < 5.0, f"Encryption too slow for {size_name}: {encrypt_time:.2f}s"
            
            # Measure decryption time
            start_time = time.time()
            loaded_data = storage.load_data(password)
            decrypt_time = time.time() - start_time
            
            assert loaded_data == test_data
            assert decrypt_time < 2.0, f"Decryption too slow for {size_name}: {decrypt_time:.2f}s"
    
    def test_logging_performance(self):
        """Test secure logging performance"""
        logger = get_secure_logger("performance_test")
        
        # Test logging many messages with filtering
        num_messages = 1000
        sensitive_messages = [
            f"Request {i} with password=secret{i} and token=abc{i}xyz"
            for i in range(num_messages)
        ]
        
        start_time = time.time()
        
        for message in sensitive_messages:
            logger.info(message)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should handle at least 500 log messages per second
        messages_per_second = num_messages / total_time
        assert messages_per_second > 500, f"Logging too slow: {messages_per_second:.1f} msg/s"
        assert total_time < 2.0, f"Logging took too long: {total_time:.2f}s"
    
    def test_concurrent_security_operations(self):
        """Test performance under concurrent security operations"""
        rate_limiter = IntelligentRateLimiter(storage_dir=self.test_dir)
        logger = get_secure_logger("concurrent_perf")
        
        def worker_thread(thread_id, num_operations):
            """Worker thread for concurrent operations"""
            for i in range(num_operations):
                # Rate limiting
                wait_time = rate_limiter.wait_for_request(
                    RequestType.PAGE_LOAD, f"https://test{thread_id}_{i}.com"
                )
                rate_limiter.record_request(
                    RequestType.PAGE_LOAD, f"https://test{thread_id}_{i}.com", 200, "OK", 0.5
                )
                
                # Logging with sensitive data
                logger.info(f"Thread {thread_id} operation {i} with token=secret{i}")
        
        # Run concurrent operations
        num_threads = 5
        operations_per_thread = 50
        threads = []
        
        start_time = time.time()
        
        for thread_id in range(num_threads):
            thread = threading.Thread(
                target=worker_thread, 
                args=(thread_id, operations_per_thread)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        total_operations = num_threads * operations_per_thread
        operations_per_second = total_operations / total_time
        
        # Should handle concurrent operations efficiently
        assert total_time < 30.0, f"Concurrent operations too slow: {total_time:.2f}s"
        assert operations_per_second > 20, f"Too slow under concurrency: {operations_per_second:.1f} ops/s"
        
        # Verify all operations completed
        stats = rate_limiter.get_statistics()
        assert stats["total_requests"] >= total_operations


class TestBrowserPerformance:
    """Performance tests for browser automation components"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            'testing': {'screenshots_enabled': True, 'screenshot_interval': 1},
            'directories': {'logs_dir': self.test_dir}
        }
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_browser_initialization_speed(self):
        """Test browser initialization performance"""
        browser_manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Mock browser to avoid actual browser startup time
        with patch('selenium.webdriver.Chrome') as mock_chrome:
            mock_driver = MagicMock()
            mock_chrome.return_value = mock_driver
            
            # Measure initialization time
            start_time = time.time()
            success = await browser_manager.initialize()
            init_time = time.time() - start_time
            
            assert success is True
            assert init_time < 2.0, f"Browser initialization too slow: {init_time:.2f}s"
    
    @pytest.mark.asyncio
    async def test_navigation_performance(self):
        """Test browser navigation speed"""
        browser_manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        with patch('selenium.webdriver.Chrome') as mock_chrome:
            mock_driver = MagicMock()
            mock_driver.get = MagicMock()
            mock_driver.current_url = "https://facebook.com"
            mock_driver.page_source = "<html><body>Test</body></html>"
            mock_chrome.return_value = mock_driver
            
            # Override rate limiter to avoid intentional delays
            browser_manager.rate_limiter.wait_for_request = MagicMock(return_value=0.0)
            browser_manager.rate_limiter.record_request = MagicMock(return_value=True)
            
            await browser_manager.initialize()
            
            # Measure navigation performance
            urls = [f"https://facebook.com/page{i}" for i in range(20)]
            
            start_time = time.time()
            
            for url in urls:
                success = await browser_manager.navigate_to_url(url)
                assert success is True
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Should handle navigation efficiently
            navigations_per_second = len(urls) / total_time
            assert navigations_per_second > 10, f"Navigation too slow: {navigations_per_second:.1f} nav/s"
            assert total_time < 2.0, f"Total navigation time too long: {total_time:.2f}s"
    
    @pytest.mark.asyncio
    async def test_screenshot_performance(self):
        """Test screenshot capture performance"""
        browser_manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        with patch('selenium.webdriver.Chrome') as mock_chrome:
            mock_driver = MagicMock()
            mock_driver.save_screenshot = MagicMock(return_value=True)
            mock_chrome.return_value = mock_driver
            
            await browser_manager.initialize()
            
            # Measure screenshot performance
            num_screenshots = 10
            start_time = time.time()
            
            for i in range(num_screenshots):
                screenshot_path = await browser_manager.take_screenshot(f"perf_test_{i}.png")
                assert screenshot_path.endswith(f"perf_test_{i}.png")
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Should capture screenshots efficiently
            screenshots_per_second = num_screenshots / total_time
            assert screenshots_per_second > 5, f"Screenshot capture too slow: {screenshots_per_second:.1f} ss/s"
            assert total_time < 2.0, f"Screenshot capture took too long: {total_time:.2f}s"
    
    @pytest.mark.asyncio
    async def test_state_detection_performance(self):
        """Test page state detection performance"""
        browser_manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        with patch('selenium.webdriver.Chrome') as mock_chrome:
            mock_driver = MagicMock()
            mock_driver.current_url = "https://facebook.com"
            mock_driver.page_source = "<html><body>Facebook Login</body></html>"
            mock_chrome.return_value = mock_driver
            
            await browser_manager.initialize()
            
            # Measure state detection performance
            num_detections = 100
            start_time = time.time()
            
            for i in range(num_detections):
                await browser_manager._detect_page_state()
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Should detect state efficiently
            detections_per_second = num_detections / total_time
            assert detections_per_second > 50, f"State detection too slow: {detections_per_second:.1f} det/s"
            assert total_time < 2.0, f"State detection took too long: {total_time:.2f}s"


class TestVisualPerformance:
    """Performance tests for visual validation components"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            'testing': {
                'baseline_screenshots': os.path.join(self.test_dir, 'baselines'),
                'similarity_threshold': 0.9
            },
            'directories': {'logs_dir': self.test_dir}
        }
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @patch('src.postwriter.testing.visual_validator.CV2_AVAILABLE', True)
    @patch('cv2.imread')
    @patch('src.postwriter.testing.visual_validator.ssim')
    def test_image_comparison_performance(self, mock_ssim, mock_imread):
        """Test image comparison performance"""
        from src.postwriter.testing.visual_validator import VisualValidator
        
        validator = VisualValidator(self.config)
        
        # Mock image data
        try:
            import numpy as np
            test_image = np.zeros((1080, 1920, 3), dtype=np.uint8)  # Full HD image
            mock_imread.return_value = test_image
            mock_ssim.return_value = 0.95
        except ImportError:
            pytest.skip("NumPy not available for performance testing")
        
        # Create test files
        current_path = os.path.join(self.test_dir, 'current.png')
        baseline_dir = self.config['testing']['baseline_screenshots']
        os.makedirs(baseline_dir, exist_ok=True)
        baseline_path = os.path.join(baseline_dir, 'baseline.png')
        
        with open(current_path, 'wb') as f:
            f.write(b'fake_current')
        with open(baseline_path, 'wb') as f:
            f.write(b'fake_baseline')
        
        # Measure comparison performance
        num_comparisons = 20
        start_time = time.time()
        
        for i in range(num_comparisons):
            comparison = validator.compare_screenshots(current_path, 'baseline')
            assert comparison.similarity_score == 0.95
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should handle image comparisons efficiently
        comparisons_per_second = num_comparisons / total_time
        assert comparisons_per_second > 5, f"Image comparison too slow: {comparisons_per_second:.1f} comp/s"
        assert total_time < 4.0, f"Image comparison took too long: {total_time:.2f}s"
    
    def test_ui_detection_performance(self):
        """Test UI element detection performance"""
        from src.postwriter.testing.visual_validator import VisualValidator
        
        validator = VisualValidator(self.config)
        
        # Create test screenshot
        test_screenshot = os.path.join(self.test_dir, 'test.png')
        with open(test_screenshot, 'wb') as f:
            f.write(b'fake_image')
        
        # Large page source for testing
        large_page_source = """
        <html>
        <head><title>Facebook - Log In</title></head>
        <body>
        """ + "<div>test content</div>" * 1000 + """
        <h1>Log into Facebook</h1>
        <form>
            <input type="email" placeholder="Email or phone">
            <input type="password" placeholder="Password">
        </form>
        </body>
        </html>
        """
        
        # Measure detection performance
        num_detections = 50
        start_time = time.time()
        
        for i in range(num_detections):
            detections = validator.detect_ui_elements(test_screenshot, large_page_source)
            assert len(detections) > 0
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should handle UI detection efficiently
        detections_per_second = num_detections / total_time
        assert detections_per_second > 10, f"UI detection too slow: {detections_per_second:.1f} det/s"
        assert total_time < 5.0, f"UI detection took too long: {total_time:.2f}s"


class TestScalabilityLimits:
    """Test scalability limits and stress conditions"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_rate_limiter_memory_usage(self):
        """Test rate limiter memory usage with large request history"""
        rate_limiter = IntelligentRateLimiter(storage_dir=self.test_dir)
        
        # Add many requests to test memory management
        num_requests = 10000
        
        start_time = time.time()
        
        for i in range(num_requests):
            rate_limiter.record_request(
                RequestType.PAGE_LOAD, 
                f"https://test{i}.com", 
                200, 
                "OK", 
                1.0
            )
            
            # Check that memory usage is controlled
            if i % 1000 == 0:
                history_size = len(rate_limiter.request_history)
                # Should not grow unbounded
                assert history_size < 5000, f"Request history too large: {history_size}"
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should handle large volumes efficiently
        assert total_time < 30.0, f"Large volume processing too slow: {total_time:.2f}s"
        
        # Final memory check
        final_history_size = len(rate_limiter.request_history)
        assert final_history_size < 5000, f"Final history too large: {final_history_size}"
    
    def test_encryption_large_data(self):
        """Test encryption performance with large datasets"""
        storage = SecureStorage(os.path.join(self.test_dir, 'large_test.enc'))
        password = "large_data_test"
        
        # Create large test data (1MB)
        large_data = {
            "session_data": {
                "cookies": [
                    {"name": f"cookie_{i}", "value": "x" * 1000} 
                    for i in range(1000)
                ],
                "large_content": "x" * 100000
            }
        }
        
        # Test encryption of large data
        start_time = time.time()
        success = storage.store_data(large_data, password)
        encrypt_time = time.time() - start_time
        
        assert success is True
        assert encrypt_time < 30.0, f"Large data encryption too slow: {encrypt_time:.2f}s"
        
        # Test decryption of large data
        start_time = time.time()
        loaded_data = storage.load_data(password)
        decrypt_time = time.time() - start_time
        
        assert loaded_data == large_data
        assert decrypt_time < 15.0, f"Large data decryption too slow: {decrypt_time:.2f}s"
    
    def test_concurrent_stress_test(self):
        """Stress test with high concurrency"""
        rate_limiter = IntelligentRateLimiter(storage_dir=self.test_dir)
        
        def stress_worker(thread_id, operations):
            """Stress test worker"""
            for i in range(operations):
                rate_limiter.wait_for_request(RequestType.PAGE_LOAD, f"https://stress{thread_id}_{i}.com")
                rate_limiter.record_request(RequestType.PAGE_LOAD, f"https://stress{thread_id}_{i}.com", 200, "OK", 0.1)
        
        # High concurrency stress test
        num_threads = 20
        operations_per_thread = 100
        threads = []
        
        start_time = time.time()
        
        for thread_id in range(num_threads):
            thread = threading.Thread(target=stress_worker, args=(thread_id, operations_per_thread))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=60)  # 1 minute timeout
        
        end_time = time.time()
        total_time = end_time - start_time
        
        total_operations = num_threads * operations_per_thread
        
        # Should handle high concurrency
        assert total_time < 60.0, f"Stress test too slow: {total_time:.2f}s"
        
        # Verify system stability
        stats = rate_limiter.get_statistics()
        assert stats["total_requests"] >= total_operations * 0.9  # Allow for some variance


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "-s", "--tb=short"])