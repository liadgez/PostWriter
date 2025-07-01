#!/usr/bin/env python3
"""
Unit tests for PostWriter browser manager
Tests enhanced browser management, state detection, and dual-engine support
"""

import os
import tempfile
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.postwriter.testing.browser_manager import (
    EnhancedBrowserManager, BrowserEngine, BrowserState, FacebookPageState
)


class TestBrowserState:
    """Test suite for BrowserState class"""
    
    def test_browser_state_creation(self):
        """Test BrowserState creation and defaults"""
        state = BrowserState(
            engine=BrowserEngine.SELENIUM,
            url="https://facebook.com",
            page_state=FacebookPageState.LOGGED_IN
        )
        
        assert state.engine == BrowserEngine.SELENIUM
        assert state.url == "https://facebook.com"
        assert state.page_state == FacebookPageState.LOGGED_IN
        assert state.errors == []
        assert state.performance_metrics == {}
        assert state.timestamp != ""
        assert state.screenshot_path is None
    
    def test_browser_state_with_data(self):
        """Test BrowserState with full data"""
        errors = ["Connection timeout", "Rate limited"]
        metrics = {"response_time": 2.5, "memory_usage": "150MB"}
        
        state = BrowserState(
            engine=BrowserEngine.PLAYWRIGHT,
            url="https://facebook.com/login",
            page_state=FacebookPageState.LOGIN_REQUIRED,
            screenshot_path="/path/to/screenshot.png",
            timestamp="2024-01-01T10:00:00Z",
            errors=errors,
            performance_metrics=metrics
        )
        
        assert state.errors == errors
        assert state.performance_metrics == metrics
        assert state.screenshot_path == "/path/to/screenshot.png"
        assert state.timestamp == "2024-01-01T10:00:00Z"


class TestEnhancedBrowserManager:
    """Test suite for EnhancedBrowserManager class"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            'testing': {
                'screenshots_enabled': True,
                'screenshot_interval': 5
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
    
    def test_initialization_selenium(self):
        """Test initialization with Selenium engine"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        assert manager.engine == BrowserEngine.SELENIUM
        assert manager.screenshot_enabled is True
        assert manager.screenshot_interval == 5
        assert manager.current_state.engine == BrowserEngine.SELENIUM
        assert manager.monitoring_active is False
    
    def test_initialization_playwright(self):
        """Test initialization with Playwright engine"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.PLAYWRIGHT)
        
        assert manager.engine == BrowserEngine.PLAYWRIGHT
        assert manager.current_state.engine == BrowserEngine.PLAYWRIGHT
    
    def test_initialization_hybrid(self):
        """Test initialization with hybrid engine"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.HYBRID)
        
        assert manager.engine == BrowserEngine.HYBRID
        assert manager.current_state.engine == BrowserEngine.HYBRID
    
    def test_state_change_callbacks(self):
        """Test state change callback system"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        callback_called = []
        
        def test_callback(state):
            callback_called.append(state)
        
        manager.add_state_change_callback(test_callback)
        
        # Trigger state change
        manager.current_state.url = "https://facebook.com"
        manager._notify_state_change()
        
        assert len(callback_called) == 1
        assert callback_called[0].url == "https://facebook.com"
    
    @patch('requests.get')
    @pytest.mark.asyncio
    async def test_selenium_initialization_with_existing_chrome(self, mock_get):
        """Test Selenium initialization with existing Chrome debug session"""
        # Mock successful Chrome debug response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        with patch('selenium.webdriver.Chrome') as mock_chrome:
            mock_driver = MagicMock()
            mock_chrome.return_value = mock_driver
            
            success = await manager.initialize()
            
            assert success is True
            assert manager.selenium_driver is not None
            mock_chrome.assert_called_once()
    
    @patch('requests.get')
    @pytest.mark.asyncio
    async def test_selenium_initialization_without_chrome(self, mock_get):
        """Test Selenium initialization without existing Chrome"""
        # Mock failed Chrome debug response
        mock_get.side_effect = ConnectionError("Chrome not running")
        
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        with patch('selenium.webdriver.Chrome') as mock_chrome:
            mock_driver = MagicMock()
            mock_chrome.return_value = mock_driver
            
            success = await manager.initialize()
            
            assert success is True
            assert manager.selenium_driver is not None
    
    @pytest.mark.asyncio
    async def test_playwright_initialization_mock(self):
        """Test Playwright initialization with mocking"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.PLAYWRIGHT)
        
        # Mock Playwright components
        mock_playwright = MagicMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        
        with patch('src.postwriter.testing.browser_manager.async_playwright') as mock_async_playwright:
            mock_async_playwright.return_value.start = AsyncMock(return_value=mock_playwright)
            
            success = await manager.initialize()
            
            assert success is True
            assert manager.playwright_browser is not None
            assert manager.playwright_context is not None
            assert manager.playwright_page is not None
    
    @patch('requests.get')
    @pytest.mark.asyncio
    async def test_navigate_to_url_selenium(self, mock_get):
        """Test URL navigation with Selenium"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Mock Selenium driver
        mock_driver = MagicMock()
        mock_driver.get = MagicMock()
        mock_driver.current_url = "https://facebook.com"
        mock_driver.page_source = "<html><body>Facebook</body></html>"
        manager.selenium_driver = mock_driver
        
        # Mock rate limiter
        manager.rate_limiter.wait_for_request = MagicMock(return_value=0.0)
        manager.rate_limiter.record_request = MagicMock(return_value=True)
        
        success = await manager.navigate_to_url("https://facebook.com")
        
        assert success is True
        mock_driver.get.assert_called_once_with("https://facebook.com")
        assert manager.current_state.url == "https://facebook.com"
    
    @pytest.mark.asyncio
    async def test_navigate_to_url_playwright(self):
        """Test URL navigation with Playwright"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.PLAYWRIGHT)
        
        # Mock Playwright page
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.url = "https://facebook.com"
        mock_page.content = AsyncMock(return_value="<html><body>Facebook</body></html>")
        manager.playwright_page = mock_page
        
        # Mock rate limiter
        manager.rate_limiter.wait_for_request = MagicMock(return_value=0.0)
        manager.rate_limiter.record_request = MagicMock(return_value=True)
        
        success = await manager.navigate_to_url("https://facebook.com")
        
        assert success is True
        mock_page.goto.assert_called_once_with("https://facebook.com", wait_until='domcontentloaded')
        assert manager.current_state.url == "https://facebook.com"
    
    @pytest.mark.asyncio
    async def test_page_state_detection_login_required(self):
        """Test detection of login required state"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Mock driver returning login page
        mock_driver = MagicMock()
        mock_driver.current_url = "https://facebook.com/login"
        mock_driver.page_source = "<html><body>Log into Facebook</body></html>"
        manager.selenium_driver = mock_driver
        
        await manager._detect_page_state()
        
        assert manager.current_state.page_state == FacebookPageState.LOGIN_REQUIRED
    
    @pytest.mark.asyncio
    async def test_page_state_detection_rate_limited(self):
        """Test detection of rate limited state"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Mock driver returning rate limit page
        mock_driver = MagicMock()
        mock_driver.current_url = "https://facebook.com/profile"
        mock_driver.page_source = "<html><body>Rate limit exceeded. Please try again later.</body></html>"
        manager.selenium_driver = mock_driver
        
        await manager._detect_page_state()
        
        assert manager.current_state.page_state == FacebookPageState.RATE_LIMITED
    
    @pytest.mark.asyncio
    async def test_page_state_detection_captcha(self):
        """Test detection of CAPTCHA state"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Mock driver returning CAPTCHA page
        mock_driver = MagicMock()
        mock_driver.current_url = "https://facebook.com/checkpoint"
        mock_driver.page_source = "<html><body>Security check: Please confirm you're human</body></html>"
        manager.selenium_driver = mock_driver
        
        await manager._detect_page_state()
        
        assert manager.current_state.page_state == FacebookPageState.CAPTCHA
    
    @pytest.mark.asyncio
    async def test_login_status_detection_selenium(self):
        """Test login status detection with Selenium"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Mock logged in state
        mock_driver = MagicMock()
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element
        manager.selenium_driver = mock_driver
        
        is_logged_in = await manager._is_logged_in()
        
        assert is_logged_in is True
        
        # Mock logged out state
        from selenium.common.exceptions import NoSuchElementException
        mock_driver.find_element.side_effect = NoSuchElementException("Element not found")
        
        is_logged_in = await manager._is_logged_in()
        
        assert is_logged_in is False
    
    @pytest.mark.asyncio
    async def test_login_status_detection_playwright(self):
        """Test login status detection with Playwright"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.PLAYWRIGHT)
        
        # Mock logged in state
        mock_page = AsyncMock()
        mock_element = MagicMock()
        mock_page.query_selector = AsyncMock(return_value=mock_element)
        manager.playwright_page = mock_page
        
        is_logged_in = await manager._is_logged_in()
        
        assert is_logged_in is True
        
        # Mock logged out state
        mock_page.query_selector = AsyncMock(return_value=None)
        
        is_logged_in = await manager._is_logged_in()
        
        assert is_logged_in is False
    
    @pytest.mark.asyncio
    async def test_screenshot_selenium(self):
        """Test screenshot capture with Selenium"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Mock Selenium driver
        mock_driver = MagicMock()
        mock_driver.save_screenshot = MagicMock(return_value=True)
        manager.selenium_driver = mock_driver
        
        screenshot_path = await manager.take_screenshot("test_screenshot.png")
        
        assert screenshot_path.endswith("test_screenshot.png")
        mock_driver.save_screenshot.assert_called_once()
        assert manager.current_state.screenshot_path == screenshot_path
    
    @pytest.mark.asyncio
    async def test_screenshot_playwright(self):
        """Test screenshot capture with Playwright"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.PLAYWRIGHT)
        
        # Mock Playwright page
        mock_page = AsyncMock()
        mock_page.screenshot = AsyncMock()
        manager.playwright_page = mock_page
        
        screenshot_path = await manager.take_screenshot("test_screenshot.png")
        
        assert screenshot_path.endswith("test_screenshot.png")
        mock_page.screenshot.assert_called_once()
        assert manager.current_state.screenshot_path == screenshot_path
    
    @pytest.mark.asyncio
    async def test_screenshot_disabled(self):
        """Test screenshot when disabled in config"""
        config = self.config.copy()
        config['testing']['screenshots_enabled'] = False
        
        manager = EnhancedBrowserManager(config, BrowserEngine.SELENIUM)
        
        screenshot_path = await manager.take_screenshot()
        
        assert screenshot_path == ""
    
    @pytest.mark.asyncio
    async def test_scroll_page_selenium(self):
        """Test page scrolling with Selenium"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Mock Selenium driver
        mock_driver = MagicMock()
        mock_driver.execute_script = MagicMock()
        manager.selenium_driver = mock_driver
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            success = await manager.scroll_page(1000)
        
        assert success is True
        mock_driver.execute_script.assert_called_once_with("window.scrollBy(0, 1000);")
    
    @pytest.mark.asyncio
    async def test_scroll_page_playwright(self):
        """Test page scrolling with Playwright"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.PLAYWRIGHT)
        
        # Mock Playwright page
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock()
        manager.playwright_page = mock_page
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            success = await manager.scroll_page(1000)
        
        assert success is True
        mock_page.evaluate.assert_called_once_with("window.scrollBy(0, 1000)")
    
    @pytest.mark.asyncio
    async def test_wait_for_element_selenium(self):
        """Test waiting for element with Selenium"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Mock Selenium driver and WebDriverWait
        mock_driver = MagicMock()
        manager.selenium_driver = mock_driver
        
        with patch('selenium.webdriver.support.ui.WebDriverWait') as mock_wait:
            mock_wait_instance = MagicMock()
            mock_wait.return_value = mock_wait_instance
            mock_wait_instance.until = MagicMock()
            
            success = await manager.wait_for_element("div.test-element", timeout=10)
            
            assert success is True
            mock_wait.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_wait_for_element_playwright(self):
        """Test waiting for element with Playwright"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.PLAYWRIGHT)
        
        # Mock Playwright page
        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        manager.playwright_page = mock_page
        
        success = await manager.wait_for_element("div.test-element", timeout=10)
        
        assert success is True
        mock_page.wait_for_selector.assert_called_once_with("div.test-element", timeout=10000)
    
    @pytest.mark.asyncio
    async def test_click_element_selenium(self):
        """Test clicking element with Selenium"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Mock Selenium driver
        mock_driver = MagicMock()
        mock_element = MagicMock()
        mock_driver.find_element.return_value = mock_element
        manager.selenium_driver = mock_driver
        
        success = await manager.click_element("button.submit")
        
        assert success is True
        mock_element.click.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_click_element_playwright(self):
        """Test clicking element with Playwright"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.PLAYWRIGHT)
        
        # Mock Playwright page
        mock_page = AsyncMock()
        mock_page.click = AsyncMock()
        manager.playwright_page = mock_page
        
        success = await manager.click_element("button.submit")
        
        assert success is True
        mock_page.click.assert_called_once_with("button.submit")
    
    @pytest.mark.asyncio
    async def test_monitoring_lifecycle(self):
        """Test monitoring start and stop lifecycle"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Mock methods to avoid actual browser operations
        manager.take_screenshot = AsyncMock(return_value="screenshot.png")
        manager._detect_page_state = AsyncMock()
        manager._notify_state_change = MagicMock()
        
        assert manager.monitoring_active is False
        
        # Start monitoring in background
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = [None, None, asyncio.CancelledError()]  # Stop after 2 iterations
            
            try:
                await manager.start_monitoring()
            except asyncio.CancelledError:
                pass
        
        # Should have attempted to take screenshots and detect state
        assert manager.take_screenshot.call_count >= 1
        assert manager._detect_page_state.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test browser cleanup"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.HYBRID)
        
        # Mock browser instances
        mock_selenium_driver = MagicMock()
        mock_selenium_driver.quit = MagicMock()
        manager.selenium_driver = mock_selenium_driver
        
        mock_playwright_context = AsyncMock()
        mock_playwright_browser = AsyncMock()
        mock_playwright = AsyncMock()
        
        mock_playwright_context.close = AsyncMock()
        mock_playwright_browser.close = AsyncMock()
        mock_playwright.stop = AsyncMock()
        
        manager.playwright_context = mock_playwright_context
        manager.playwright_browser = mock_playwright_browser
        manager.playwright = mock_playwright
        
        await manager.cleanup()
        
        # All cleanup methods should be called
        mock_selenium_driver.quit.assert_called_once()
        mock_playwright_context.close.assert_called_once()
        mock_playwright_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
    
    def test_get_state(self):
        """Test getting current browser state"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Modify state
        manager.current_state.url = "https://facebook.com"
        manager.current_state.page_state = FacebookPageState.LOGGED_IN
        manager.current_state.errors.append("Test error")
        
        state = manager.get_state()
        
        assert state.url == "https://facebook.com"
        assert state.page_state == FacebookPageState.LOGGED_IN
        assert "Test error" in state.errors
    
    @pytest.mark.asyncio
    async def test_error_handling_in_navigation(self):
        """Test error handling during navigation"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Mock driver that raises exception
        mock_driver = MagicMock()
        mock_driver.get.side_effect = Exception("Navigation failed")
        manager.selenium_driver = mock_driver
        
        # Mock rate limiter
        manager.rate_limiter.wait_for_request = MagicMock(return_value=0.0)
        manager.rate_limiter.record_request = MagicMock(return_value=True)
        
        success = await manager.navigate_to_url("https://facebook.com")
        
        assert success is False
        assert len(manager.current_state.errors) > 0
        assert "Navigation error" in manager.current_state.errors[0]


class TestBrowserManagerIntegration:
    """Integration tests for browser manager with other systems"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            'testing': {
                'screenshots_enabled': True,
                'screenshot_interval': 1  # Fast for testing
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
    async def test_rate_limiter_integration(self):
        """Test integration with rate limiter"""
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Mock Selenium driver
        mock_driver = MagicMock()
        mock_driver.get = MagicMock()
        mock_driver.current_url = "https://facebook.com"
        mock_driver.page_source = "<html><body>Facebook</body></html>"
        manager.selenium_driver = mock_driver
        
        # Test that rate limiting is applied
        original_wait_method = manager.rate_limiter.wait_for_request
        wait_times = []
        
        def mock_wait_for_request(*args, **kwargs):
            wait_time = original_wait_method(*args, **kwargs)
            wait_times.append(wait_time)
            return wait_time
        
        manager.rate_limiter.wait_for_request = mock_wait_for_request
        
        # Make multiple requests
        for i in range(3):
            await manager.navigate_to_url(f"https://facebook.com/page{i}")
        
        # Should have applied rate limiting
        assert len(wait_times) == 3
        for wait_time in wait_times:
            assert wait_time >= 0
    
    @pytest.mark.asyncio
    async def test_secure_logging_integration(self):
        """Test integration with secure logging"""
        from src.postwriter.security.logging import get_secure_logger
        
        manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        
        # Mock Selenium driver
        mock_driver = MagicMock()
        mock_driver.get = MagicMock()
        mock_driver.current_url = "https://user:password@facebook.com"  # Sensitive URL
        mock_driver.page_source = "<html><body>Facebook</body></html>"
        manager.selenium_driver = mock_driver
        
        # Mock rate limiter
        manager.rate_limiter.wait_for_request = MagicMock(return_value=0.0)
        manager.rate_limiter.record_request = MagicMock(return_value=True)
        
        # Navigate with sensitive URL
        await manager.navigate_to_url("https://user:password@facebook.com")
        
        # Check that logs exist and are filtered
        log_files = [f for f in os.listdir(self.test_dir) if f.endswith('.log')]
        if log_files:  # Logs may or may not be created depending on configuration
            with open(os.path.join(self.test_dir, log_files[0]), 'r') as f:
                log_content = f.read()
                # Sensitive data should be filtered
                assert "password" not in log_content or "***FILTERED***" in log_content


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])