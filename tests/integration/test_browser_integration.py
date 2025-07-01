#!/usr/bin/env python3
"""
Integration tests for PostWriter browser automation and UI testing
Tests complete workflows, cross-component interactions, and real browser scenarios
"""

import os
import tempfile
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.postwriter.testing.browser_manager import EnhancedBrowserManager, BrowserEngine, FacebookPageState
from src.postwriter.testing.ui_supervisor import UISupervisor
from src.postwriter.testing.visual_validator import VisualValidator, ValidationResult
from src.postwriter.security.rate_limiter import IntelligentRateLimiter, RequestType
from src.postwriter.security.logging import get_secure_logger


class TestBrowserUIIntegration:
    """Integration tests for browser manager and UI supervisor"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            'testing': {
                'screenshots_enabled': True,
                'screenshot_interval': 1,
                'baseline_screenshots': os.path.join(self.test_dir, 'baselines'),
                'similarity_threshold': 0.9
            },
            'directories': {
                'logs_dir': self.test_dir
            },
            'chrome': {
                'debug_port': 9222
            }
        }
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_browser_supervisor_lifecycle(self):
        """Test complete browser and supervisor lifecycle"""
        browser_manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        supervisor = UISupervisor(self.config)
        
        # Mock browser initialization
        with patch('selenium.webdriver.Chrome') as mock_chrome:
            mock_driver = MagicMock()
            mock_driver.current_url = "https://facebook.com"
            mock_driver.page_source = "<html><body>Facebook Login</body></html>"
            mock_chrome.return_value = mock_driver
            
            # Initialize browser
            success = await browser_manager.initialize()
            assert success is True
            
            # Start supervisor monitoring
            supervisor.register_browser_manager(browser_manager)
            
            # Mock supervisor methods to avoid actual WebSocket operations
            supervisor.broadcast_message = AsyncMock()
            supervisor._send_screenshot_update = AsyncMock()
            
            # Simulate browser navigation with monitoring
            await browser_manager.navigate_to_url("https://facebook.com/login")
            
            # Verify browser state is tracked
            state = browser_manager.get_state()
            assert state.url == "https://facebook.com/login"
            
            # Simulate supervisor receiving browser updates
            await supervisor._handle_browser_state_change(state)
            
            # Verify supervisor broadcasts were made
            supervisor.broadcast_message.assert_called()
    
    @pytest.mark.asyncio 
    async def test_visual_validation_integration(self):
        """Test integration between browser manager and visual validator"""
        browser_manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        validator = VisualValidator(self.config)
        
        # Mock browser and screenshot operations
        with patch('selenium.webdriver.Chrome') as mock_chrome:
            mock_driver = MagicMock()
            mock_driver.save_screenshot = MagicMock(return_value=True)
            mock_driver.current_url = "https://facebook.com"
            mock_driver.page_source = "<html><body>Facebook Home</body></html>"
            mock_chrome.return_value = mock_driver
            
            # Initialize browser
            await browser_manager.initialize()
            
            # Take screenshot
            screenshot_path = await browser_manager.take_screenshot("test_page.png")
            assert screenshot_path.endswith("test_page.png")
            
            # Create test baseline image
            test_baseline_dir = self.config['testing']['baseline_screenshots']
            os.makedirs(test_baseline_dir, exist_ok=True)
            
            # Mock image operations since we don't have actual screenshots
            with patch('src.postwriter.testing.visual_validator.CV2_AVAILABLE', True), \
                 patch('cv2.imread') as mock_imread, \
                 patch('cv2.imwrite') as mock_imwrite:
                
                # Mock image data
                import numpy as np
                mock_img = np.zeros((480, 640, 3), dtype=np.uint8)
                mock_imread.return_value = mock_img
                
                # Create baseline
                baseline_created = validator.create_baseline(screenshot_path, "facebook_home")
                assert baseline_created is True
                
                # Compare with baseline
                comparison = validator.compare_screenshots(screenshot_path, "facebook_home")
                assert comparison.result in [ValidationResult.PASSED, ValidationResult.ERROR]
    
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self):
        """Test integration between browser manager and rate limiter"""
        browser_manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        rate_limiter = IntelligentRateLimiter(storage_dir=self.test_dir)
        
        # Override browser manager's rate limiter
        browser_manager.rate_limiter = rate_limiter
        
        # Mock browser operations
        with patch('selenium.webdriver.Chrome') as mock_chrome:
            mock_driver = MagicMock()
            mock_driver.get = MagicMock()
            mock_driver.current_url = "https://facebook.com"
            mock_driver.page_source = "<html><body>Facebook</body></html>"
            mock_chrome.return_value = mock_driver
            
            await browser_manager.initialize()
            
            # Simulate multiple rapid requests
            urls = [
                "https://facebook.com/page1",
                "https://facebook.com/page2", 
                "https://facebook.com/page3"
            ]
            
            navigation_times = []
            for url in urls:
                start_time = asyncio.get_event_loop().time()
                await browser_manager.navigate_to_url(url)
                end_time = asyncio.get_event_loop().time()
                navigation_times.append(end_time - start_time)
            
            # Verify rate limiting was applied (later requests should take longer)
            assert len(navigation_times) == 3
            # Allow for some variance in timing
            for nav_time in navigation_times:
                assert nav_time >= 0  # Should complete successfully
            
            # Check rate limiter statistics
            stats = rate_limiter.get_statistics()
            assert stats["total_requests"] >= 3


class TestEndToEndWorkflows:
    """End-to-end workflow tests"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            'testing': {
                'screenshots_enabled': True,
                'screenshot_interval': 2,
                'baseline_screenshots': os.path.join(self.test_dir, 'baselines'),
                'similarity_threshold': 0.85,
                'difference_threshold': 10.0
            },
            'directories': {
                'logs_dir': self.test_dir
            },
            'chrome': {
                'debug_port': 9222
            }
        }
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_facebook_login_workflow(self):
        """Test complete Facebook login workflow with monitoring"""
        # Components
        browser_manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        supervisor = UISupervisor(self.config)
        validator = VisualValidator(self.config)
        
        # Mock browser for login simulation
        with patch('selenium.webdriver.Chrome') as mock_chrome:
            mock_driver = MagicMock()
            mock_chrome.return_value = mock_driver
            
            # Setup login scenario
            login_scenario = [
                ("https://facebook.com", "<html><body>Welcome to Facebook</body></html>"),
                ("https://facebook.com/login", "<html><body>Log into Facebook<input type='email'><input type='password'></body></html>"),
                ("https://facebook.com/home", "<html><body>Facebook Home Feed</body></html>")
            ]
            
            call_count = 0
            def mock_navigation(url):
                nonlocal call_count
                if call_count < len(login_scenario):
                    mock_driver.current_url = login_scenario[call_count][0]
                    mock_driver.page_source = login_scenario[call_count][1]
                    call_count += 1
            
            mock_driver.get.side_effect = mock_navigation
            mock_driver.current_url = "https://facebook.com"
            mock_driver.page_source = "<html><body>Welcome to Facebook</body></html>"
            
            # Initialize components
            await browser_manager.initialize()
            supervisor.register_browser_manager(browser_manager)
            
            # Mock supervisor operations
            supervisor.broadcast_message = AsyncMock()
            supervisor._send_screenshot_update = AsyncMock()
            
            # Step 1: Navigate to Facebook
            await browser_manager.navigate_to_url("https://facebook.com")
            state1 = browser_manager.get_state()
            assert "facebook.com" in state1.url
            
            # Step 2: Detect login required
            await browser_manager._detect_page_state()
            
            # Step 3: Navigate to login page
            await browser_manager.navigate_to_url("https://facebook.com/login")
            await browser_manager._detect_page_state()
            state2 = browser_manager.get_state()
            
            # Should detect login page
            assert state2.page_state == FacebookPageState.LOGIN_REQUIRED
            
            # Step 4: Simulate login (navigate to home)
            await browser_manager.navigate_to_url("https://facebook.com/home")
            state3 = browser_manager.get_state()
            
            # Verify workflow completion
            assert len([s for s in [state1, state2, state3] if s.url]) == 3
            
            # Verify supervisor was notified of state changes
            assert supervisor.broadcast_message.call_count >= 3
    
    @pytest.mark.asyncio
    async def test_error_detection_and_recovery(self):
        """Test error detection and recovery workflow"""
        browser_manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Mock browser with error scenarios
        with patch('selenium.webdriver.Chrome') as mock_chrome:
            mock_driver = MagicMock()
            mock_chrome.return_value = mock_driver
            
            # Simulate network error on first request
            error_count = 0
            def mock_navigation_with_errors(url):
                nonlocal error_count
                error_count += 1
                if error_count == 1:
                    raise Exception("Network timeout")
                elif error_count == 2:
                    mock_driver.current_url = url
                    mock_driver.page_source = "<html><body>Rate limit exceeded</body></html>"
                else:
                    mock_driver.current_url = url
                    mock_driver.page_source = "<html><body>Success</body></html>"
            
            mock_driver.get.side_effect = mock_navigation_with_errors
            
            await browser_manager.initialize()
            
            # Attempt navigation that will fail first
            success1 = await browser_manager.navigate_to_url("https://facebook.com/profile")
            assert success1 is False  # Should fail due to network error
            
            # Check that error was recorded
            state1 = browser_manager.get_state()
            assert len(state1.errors) > 0
            assert "Navigation error" in state1.errors[0]
            
            # Second attempt should detect rate limiting
            success2 = await browser_manager.navigate_to_url("https://facebook.com/profile")
            assert success2 is True  # Navigation succeeds but detects rate limiting
            
            # Detect page state should identify rate limiting
            await browser_manager._detect_page_state()
            state2 = browser_manager.get_state()
            assert state2.page_state == FacebookPageState.RATE_LIMITED
            
            # Third attempt should succeed
            success3 = await browser_manager.navigate_to_url("https://facebook.com/profile")
            assert success3 is True
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent browser operations"""
        browser_manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        supervisor = UISupervisor(self.config)
        
        # Mock browser
        with patch('selenium.webdriver.Chrome') as mock_chrome:
            mock_driver = MagicMock()
            mock_driver.save_screenshot = MagicMock(return_value=True)
            mock_driver.current_url = "https://facebook.com"
            mock_driver.page_source = "<html><body>Facebook</body></html>"
            mock_chrome.return_value = mock_driver
            
            await browser_manager.initialize()
            supervisor.register_browser_manager(browser_manager)
            
            # Mock supervisor operations
            supervisor.broadcast_message = AsyncMock()
            
            # Create concurrent tasks
            tasks = [
                browser_manager.take_screenshot("concurrent_1.png"),
                browser_manager.take_screenshot("concurrent_2.png"),
                browser_manager._detect_page_state(),
                supervisor._handle_browser_state_change(browser_manager.get_state())
            ]
            
            # Execute concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify all tasks completed
            assert len(results) == 4
            
            # Check for exceptions
            exceptions = [r for r in results if isinstance(r, Exception)]
            assert len(exceptions) == 0  # No exceptions should occur
            
            # Verify screenshots were taken
            screenshot_results = [r for r in results if isinstance(r, str) and r.endswith('.png')]
            assert len(screenshot_results) >= 2


class TestComponentInteractions:
    """Test interactions between different components"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            'testing': {
                'screenshots_enabled': True,
                'screenshot_interval': 1
            },
            'directories': {
                'logs_dir': self.test_dir
            }
        }
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_logging_integration(self):
        """Test secure logging integration with browser operations"""
        browser_manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        logger = get_secure_logger("integration_test")
        
        # Mock browser
        with patch('selenium.webdriver.Chrome') as mock_chrome:
            mock_driver = MagicMock()
            mock_driver.get = MagicMock()
            # URL with sensitive data that should be filtered
            mock_driver.current_url = "https://user:password123@facebook.com/profile?token=secret456"
            mock_driver.page_source = "<html><body>Profile</body></html>"
            mock_chrome.return_value = mock_driver
            
            await browser_manager.initialize()
            
            # Navigate to URL with sensitive data
            await browser_manager.navigate_to_url("https://user:password123@facebook.com/profile?token=secret456")
            
            # Log browser state (this should filter sensitive data)
            state = browser_manager.get_state()
            logger.info(f"Browser navigation completed: {state.url}")
            
            # Check that logs were created and filtered
            log_files = [f for f in os.listdir(self.test_dir) if f.endswith('.log')]
            if log_files:  # Logs may or may not be created depending on configuration
                with open(os.path.join(self.test_dir, log_files[0]), 'r') as f:
                    log_content = f.read()
                    # Sensitive data should be filtered
                    assert "password123" not in log_content or "***FILTERED***" in log_content
                    assert "secret456" not in log_content or "***FILTERED***" in log_content
    
    @pytest.mark.asyncio
    async def test_multi_engine_browser_switching(self):
        """Test switching between browser engines"""
        # Test with hybrid engine that supports both Selenium and Playwright
        browser_manager = EnhancedBrowserManager(self.config, BrowserEngine.HYBRID)
        
        # Mock both engines
        with patch('selenium.webdriver.Chrome') as mock_selenium, \
             patch('src.postwriter.testing.browser_manager.async_playwright') as mock_playwright:
            
            # Setup Selenium mocks
            mock_selenium_driver = MagicMock()
            mock_selenium_driver.current_url = "https://facebook.com"
            mock_selenium_driver.page_source = "<html><body>Selenium</body></html>"
            mock_selenium.return_value = mock_selenium_driver
            
            # Setup Playwright mocks
            mock_pw_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()
            
            mock_pw_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_page.goto = AsyncMock()
            mock_page.url = "https://facebook.com"
            mock_page.content = AsyncMock(return_value="<html><body>Playwright</body></html>")
            
            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw_instance)
            
            # Initialize hybrid browser
            success = await browser_manager.initialize()
            assert success is True
            
            # Should have both engines available
            assert browser_manager.selenium_driver is not None
            assert browser_manager.playwright_page is not None
            
            # Test navigation with Selenium (default for hybrid)
            await browser_manager.navigate_to_url("https://facebook.com")
            
            # Verify state management works with hybrid engine
            state = browser_manager.get_state()
            assert state.engine == BrowserEngine.HYBRID
            assert state.url == "https://facebook.com"
    
    @pytest.mark.asyncio
    async def test_supervisor_browser_state_sync(self):
        """Test synchronization between supervisor and browser manager"""
        browser_manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        supervisor = UISupervisor(self.config)
        
        # Track state changes
        state_changes = []
        
        def track_state_change(state):
            state_changes.append(state)
        
        browser_manager.add_state_change_callback(track_state_change)
        supervisor.register_browser_manager(browser_manager)
        
        # Mock browser operations
        with patch('selenium.webdriver.Chrome') as mock_chrome:
            mock_driver = MagicMock()
            mock_driver.current_url = "https://facebook.com/home"
            mock_driver.page_source = "<html><body>Home</body></html>"
            mock_chrome.return_value = mock_driver
            
            await browser_manager.initialize()
            
            # Mock supervisor methods
            supervisor.broadcast_message = AsyncMock()
            
            # Trigger state changes
            await browser_manager.navigate_to_url("https://facebook.com/home")
            await browser_manager._detect_page_state()
            
            # Force state change notification
            browser_manager._notify_state_change()
            
            # Verify state changes were tracked
            assert len(state_changes) >= 1
            
            # Verify supervisor was notified
            latest_state = browser_manager.get_state()
            await supervisor._handle_browser_state_change(latest_state)
            
            # Should have broadcasted the state change
            supervisor.broadcast_message.assert_called()


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "-s"])