#!/usr/bin/env python3
"""
Enhanced Browser Manager for PostWriter
Provides dual Playwright/Selenium control with real-time monitoring capabilities
"""

import asyncio
import time
import json
import os
from datetime import datetime
from typing import Dict, Optional, Union, List, Callable
from dataclasses import dataclass
from enum import Enum

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException

try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Browser = None
    Page = None
    BrowserContext = None

from ..security.logging import get_secure_logger
from ..security.rate_limiter import get_rate_limiter, RequestType


class BrowserEngine(Enum):
    """Available browser engines"""
    SELENIUM = "selenium"
    PLAYWRIGHT = "playwright"
    HYBRID = "hybrid"


class FacebookPageState(Enum):
    """Facebook page states"""
    UNKNOWN = "unknown"
    LOGIN_REQUIRED = "login_required"
    LOGGED_IN = "logged_in"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"
    CAPTCHA = "captcha"
    PROFILE_PAGE = "profile_page"
    FEED_PAGE = "feed_page"
    ERROR_PAGE = "error_page"


@dataclass
class BrowserState:
    """Current browser state information"""
    engine: BrowserEngine
    url: str
    page_state: FacebookPageState
    screenshot_path: Optional[str] = None
    timestamp: str = ""
    errors: List[str] = None
    performance_metrics: Dict = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.performance_metrics is None:
            self.performance_metrics = {}
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class EnhancedBrowserManager:
    """
    Enhanced browser manager providing dual engine support with real-time monitoring
    """
    
    def __init__(self, config: Dict, engine: BrowserEngine = BrowserEngine.HYBRID):
        self.config = config
        self.engine = engine
        self.logger = get_secure_logger("browser_manager")
        self.rate_limiter = get_rate_limiter()
        
        # Browser instances
        self.selenium_driver: Optional[webdriver.Chrome] = None
        self.playwright_browser: Optional[Browser] = None
        self.playwright_context: Optional[BrowserContext] = None
        self.playwright_page: Optional[Page] = None
        self.playwright = None
        
        # State tracking
        self.current_state = BrowserState(
            engine=engine,
            url="",
            page_state=FacebookPageState.UNKNOWN
        )
        
        # Monitoring settings
        self.screenshot_enabled = config.get('testing', {}).get('screenshots_enabled', True)
        self.screenshot_interval = config.get('testing', {}).get('screenshot_interval', 5)
        self.screenshot_dir = config.get('directories', {}).get('logs_dir', './logs')
        self.monitoring_active = False
        
        # Callbacks for state changes
        self.state_change_callbacks: List[Callable] = []
        
        # Ensure screenshot directory exists
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
        self.logger.info(f"Enhanced Browser Manager initialized with engine: {engine.value}")

    def add_state_change_callback(self, callback: Callable[[BrowserState], None]):
        """Add callback to be called when browser state changes"""
        self.state_change_callbacks.append(callback)
    
    def _notify_state_change(self):
        """Notify all callbacks of state change"""
        for callback in self.state_change_callbacks:
            try:
                callback(self.current_state)
            except Exception as e:
                self.logger.error(f"State change callback error: {e}")

    async def initialize(self) -> bool:
        """Initialize browser engines based on configuration"""
        try:
            if self.engine in [BrowserEngine.SELENIUM, BrowserEngine.HYBRID]:
                await self._initialize_selenium()
            
            if self.engine in [BrowserEngine.PLAYWRIGHT, BrowserEngine.HYBRID]:
                if PLAYWRIGHT_AVAILABLE:
                    await self._initialize_playwright()
                else:
                    self.logger.warning("Playwright not available, falling back to Selenium only")
                    self.engine = BrowserEngine.SELENIUM
            
            self.logger.info("Browser initialization complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Browser initialization failed: {e}")
            return False

    async def _initialize_selenium(self):
        """Initialize Selenium WebDriver"""
        options = ChromeOptions()
        
        # Connect to existing Chrome debug session if available
        chrome_debug_port = self.config.get('chrome', {}).get('debug_port', 9222)
        
        try:
            # Check if Chrome debug is available
            response = requests.get(f"http://localhost:{chrome_debug_port}/json/version", timeout=5)
            if response.status_code == 200:
                options.add_experimental_option("debuggerAddress", f"localhost:{chrome_debug_port}")
                self.logger.info("Connected to existing Chrome debug session")
            else:
                # Launch new Chrome instance
                options.add_argument("--remote-debugging-port=9222")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                self.logger.info("Starting new Chrome instance with debugging")
                
        except requests.RequestException:
            # Chrome debug not available, use normal mode
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            self.logger.info("Starting Chrome in normal mode")
        
        # Additional Chrome options for better automation
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        try:
            self.selenium_driver = webdriver.Chrome(options=options)
            self.selenium_driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.logger.info("Selenium WebDriver initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Selenium: {e}")
            raise

    async def _initialize_playwright(self):
        """Initialize Playwright browser"""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright not available")
        
        self.playwright = await async_playwright().start()
        
        # Launch browser with similar settings to Selenium
        self.playwright_browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--window-size=1920,1080'
            ]
        )
        
        # Create context with stealth settings
        self.playwright_context = await self.playwright_browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # Add stealth scripts
        await self.playwright_context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        """)
        
        self.playwright_page = await self.playwright_context.new_page()
        self.logger.info("Playwright browser initialized successfully")

    async def navigate_to_url(self, url: str) -> bool:
        """Navigate to URL using available browser engine"""
        try:
            # Apply rate limiting
            wait_time = self.rate_limiter.wait_for_request(RequestType.PAGE_LOAD, url)
            if wait_time > 0:
                self.logger.info(f"Rate limiting: waiting {wait_time:.1f}s before navigation")
                await asyncio.sleep(wait_time)
            
            start_time = time.time()
            
            if self.selenium_driver:
                self.selenium_driver.get(url)
                success = True
            elif self.playwright_page:
                await self.playwright_page.goto(url, wait_until='domcontentloaded')
                success = True
            else:
                raise RuntimeError("No browser engine available")
            
            response_time = time.time() - start_time
            
            # Record request for rate limiting
            self.rate_limiter.record_request(
                RequestType.PAGE_LOAD,
                url,
                200,  # Assume success
                "",
                response_time
            )
            
            # Update state
            self.current_state.url = url
            await self._detect_page_state()
            
            self.logger.info(f"Successfully navigated to {url}")
            self._notify_state_change()
            
            return success
            
        except Exception as e:
            self.logger.error(f"Navigation failed for {url}: {e}")
            self.current_state.errors.append(f"Navigation error: {e}")
            self._notify_state_change()
            return False

    async def _detect_page_state(self):
        """Detect current Facebook page state"""
        try:
            current_url = self.get_current_url()
            page_source = await self.get_page_source()
            
            # State detection logic
            if "login" in current_url.lower():
                self.current_state.page_state = FacebookPageState.LOGIN_REQUIRED
            elif "facebook.com/login" in current_url:
                self.current_state.page_state = FacebookPageState.LOGIN_REQUIRED
            elif "We're sorry, but something went wrong" in page_source:
                self.current_state.page_state = FacebookPageState.ERROR_PAGE
            elif "captcha" in page_source.lower():
                self.current_state.page_state = FacebookPageState.CAPTCHA
            elif "blocked" in page_source.lower():
                self.current_state.page_state = FacebookPageState.BLOCKED
            elif "rate limit" in page_source.lower():
                self.current_state.page_state = FacebookPageState.RATE_LIMITED
            elif "/profile.php" in current_url or "/people/" in current_url:
                self.current_state.page_state = FacebookPageState.PROFILE_PAGE
            elif "facebook.com" in current_url and "feed" in current_url:
                self.current_state.page_state = FacebookPageState.FEED_PAGE
            elif "facebook.com" in current_url:
                # Check if we're logged in by looking for user elements
                if await self._is_logged_in():
                    self.current_state.page_state = FacebookPageState.LOGGED_IN
                else:
                    self.current_state.page_state = FacebookPageState.LOGIN_REQUIRED
            else:
                self.current_state.page_state = FacebookPageState.UNKNOWN
                
            self.logger.info(f"Detected page state: {self.current_state.page_state.value}")
            
        except Exception as e:
            self.logger.error(f"Page state detection failed: {e}")
            self.current_state.page_state = FacebookPageState.UNKNOWN

    async def _is_logged_in(self) -> bool:
        """Check if user is logged into Facebook"""
        try:
            if self.selenium_driver:
                # Look for common logged-in elements
                logged_in_selectors = [
                    '[data-testid="blue_bar_profile_link"]',
                    '[aria-label="Account"]',
                    '[data-testid="left_nav_menu_item"]',
                    '.fb_logo'
                ]
                
                for selector in logged_in_selectors:
                    try:
                        element = self.selenium_driver.find_element(By.CSS_SELECTOR, selector)
                        if element:
                            return True
                    except:
                        continue
                        
            elif self.playwright_page:
                # Playwright version
                logged_in_selectors = [
                    '[data-testid="blue_bar_profile_link"]',
                    '[aria-label="Account"]',
                    '[data-testid="left_nav_menu_item"]'
                ]
                
                for selector in logged_in_selectors:
                    element = await self.playwright_page.query_selector(selector)
                    if element:
                        return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Login status check failed: {e}")
            return False

    async def take_screenshot(self, filename: Optional[str] = None) -> str:
        """Take screenshot using available browser engine"""
        if not self.screenshot_enabled:
            return ""
        
        try:
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
                filename = f"screenshot_{timestamp}.png"
            
            screenshot_path = os.path.join(self.screenshot_dir, filename)
            
            if self.selenium_driver:
                self.selenium_driver.save_screenshot(screenshot_path)
            elif self.playwright_page:
                await self.playwright_page.screenshot(path=screenshot_path, full_page=True)
            else:
                raise RuntimeError("No browser engine available for screenshot")
            
            self.current_state.screenshot_path = screenshot_path
            self.logger.info(f"Screenshot saved: {screenshot_path}")
            
            return screenshot_path
            
        except Exception as e:
            self.logger.error(f"Screenshot failed: {e}")
            return ""

    async def get_page_source(self) -> str:
        """Get current page source"""
        try:
            if self.selenium_driver:
                return self.selenium_driver.page_source
            elif self.playwright_page:
                return await self.playwright_page.content()
            else:
                return ""
        except Exception as e:
            self.logger.error(f"Failed to get page source: {e}")
            return ""

    def get_current_url(self) -> str:
        """Get current URL"""
        try:
            if self.selenium_driver:
                return self.selenium_driver.current_url
            elif self.playwright_page:
                return self.playwright_page.url
            else:
                return ""
        except Exception as e:
            self.logger.error(f"Failed to get current URL: {e}")
            return ""

    async def scroll_page(self, pixels: int = 1000) -> bool:
        """Scroll page by specified pixels"""
        try:
            if self.selenium_driver:
                self.selenium_driver.execute_script(f"window.scrollBy(0, {pixels});")
            elif self.playwright_page:
                await self.playwright_page.evaluate(f"window.scrollBy(0, {pixels})")
            else:
                return False
            
            await asyncio.sleep(2)  # Wait for content to load
            return True
            
        except Exception as e:
            self.logger.error(f"Scroll failed: {e}")
            return False

    async def start_monitoring(self):
        """Start real-time monitoring with periodic screenshots"""
        self.monitoring_active = True
        self.logger.info("Started real-time monitoring")
        
        while self.monitoring_active:
            try:
                # Take periodic screenshot
                await self.take_screenshot()
                
                # Update page state
                await self._detect_page_state()
                
                # Notify callbacks
                self._notify_state_change()
                
                # Wait for next interval
                await asyncio.sleep(self.screenshot_interval)
                
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(5)  # Wait before retry

    def stop_monitoring(self):
        """Stop real-time monitoring"""
        self.monitoring_active = False
        self.logger.info("Stopped real-time monitoring")

    async def cleanup(self):
        """Clean up browser resources"""
        try:
            self.stop_monitoring()
            
            if self.selenium_driver:
                self.selenium_driver.quit()
                self.logger.info("Selenium driver closed")
            
            if self.playwright_context:
                await self.playwright_context.close()
            
            if self.playwright_browser:
                await self.playwright_browser.close()
            
            if self.playwright:
                await self.playwright.stop()
            
            self.logger.info("Browser cleanup complete")
            
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")

    def get_state(self) -> BrowserState:
        """Get current browser state"""
        return self.current_state

    async def wait_for_element(self, selector: str, timeout: int = 10) -> bool:
        """Wait for element to be present"""
        try:
            if self.selenium_driver:
                wait = WebDriverWait(self.selenium_driver, timeout)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                return True
                
            elif self.playwright_page:
                await self.playwright_page.wait_for_selector(selector, timeout=timeout * 1000)
                return True
                
            return False
            
        except (TimeoutException, Exception) as e:
            self.logger.warning(f"Element wait timeout for {selector}: {e}")
            return False

    async def click_element(self, selector: str) -> bool:
        """Click element by selector"""
        try:
            if self.selenium_driver:
                element = self.selenium_driver.find_element(By.CSS_SELECTOR, selector)
                element.click()
                return True
                
            elif self.playwright_page:
                await self.playwright_page.click(selector)
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Click failed for {selector}: {e}")
            return False


# Example usage and testing
if __name__ == "__main__":
    async def test_browser_manager():
        config = {
            'testing': {
                'screenshots_enabled': True,
                'screenshot_interval': 3
            },
            'directories': {
                'logs_dir': './test_logs'
            }
        }
        
        manager = EnhancedBrowserManager(config, BrowserEngine.SELENIUM)
        
        # Add state change callback
        def on_state_change(state: BrowserState):
            print(f"State changed: {state.page_state.value} at {state.url}")
        
        manager.add_state_change_callback(on_state_change)
        
        try:
            await manager.initialize()
            await manager.navigate_to_url("https://facebook.com")
            
            # Start monitoring in background
            monitor_task = asyncio.create_task(manager.start_monitoring())
            
            # Let it monitor for 30 seconds
            await asyncio.sleep(30)
            
            manager.stop_monitoring()
            await monitor_task
            
        finally:
            await manager.cleanup()
    
    # Run test
    asyncio.run(test_browser_manager())