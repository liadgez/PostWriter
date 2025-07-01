#!/usr/bin/env python3
"""
Pytest configuration and shared fixtures for PostWriter tests
"""

import os
import sys
import tempfile
import pytest
import asyncio
from unittest.mock import MagicMock, patch

# Add source directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Test configuration
TEST_CONFIG = {
    'directories': {
        'logs_dir': None,  # Will be set to temporary directory
        'data_dir': None,
        'output_dir': None
    },
    'testing': {
        'screenshots_enabled': True,
        'screenshot_interval': 1,
        'baseline_screenshots': None,  # Will be set to temporary directory
        'similarity_threshold': 0.9,
        'difference_threshold': 5.0
    },
    'chrome': {
        'debug_port': 9222
    },
    'security': {
        'rate_limiting_enabled': True,
        'secure_logging': True,
        'encrypt_sessions': True,
        'max_requests_per_minute': 20,
        'max_requests_per_hour': 300
    },
    'facebook': {
        'login_url': 'https://facebook.com/login',
        'base_url': 'https://facebook.com'
    }
}


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp_dir = tempfile.mkdtemp(prefix='postwriter_test_')
    yield temp_dir
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_config(temp_dir):
    """Create test configuration with temporary directories"""
    config = TEST_CONFIG.copy()
    config['directories']['logs_dir'] = temp_dir
    config['directories']['data_dir'] = os.path.join(temp_dir, 'data')
    config['directories']['output_dir'] = os.path.join(temp_dir, 'output')
    config['testing']['baseline_screenshots'] = os.path.join(temp_dir, 'baselines')
    
    # Ensure directories exist
    for dir_path in config['directories'].values():
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
    
    os.makedirs(config['testing']['baseline_screenshots'], exist_ok=True)
    
    return config


@pytest.fixture
def mock_browser_driver():
    """Mock browser driver for testing without actual browser"""
    mock_driver = MagicMock()
    mock_driver.current_url = "https://facebook.com"
    mock_driver.page_source = "<html><body>Mock Facebook Page</body></html>"
    mock_driver.get_window_size.return_value = {'width': 1920, 'height': 1080}
    mock_driver.save_screenshot.return_value = True
    mock_driver.quit.return_value = None
    
    # Mock element finding
    mock_element = MagicMock()
    mock_element.click.return_value = None
    mock_element.send_keys.return_value = None
    mock_driver.find_element.return_value = mock_element
    mock_driver.find_elements.return_value = [mock_element]
    
    return mock_driver


@pytest.fixture
def mock_requests():
    """Mock requests for network-free testing"""
    with patch('requests.get') as mock_get, \
         patch('requests.post') as mock_post:
        
        # Default successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Mock Response</body></html>"
        mock_response.json.return_value = {"status": "success"}
        
        mock_get.return_value = mock_response
        mock_post.return_value = mock_response
        
        yield {
            'get': mock_get,
            'post': mock_post,
            'response': mock_response
        }


@pytest.fixture
def mock_chrome_debug():
    """Mock Chrome debugging API"""
    with patch('requests.get') as mock_get:
        # Mock Chrome debug port response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "1",
                "title": "Facebook",
                "url": "https://facebook.com",
                "webSocketDebuggerUrl": "ws://localhost:9222/devtools/page/1"
            }
        ]
        
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_session_data():
    """Mock browser session data for testing"""
    return {
        "cookies": [
            {
                "name": "sessionid",
                "value": "test_session_123",
                "domain": ".facebook.com",
                "path": "/",
                "httpOnly": True,
                "secure": True
            },
            {
                "name": "datr",
                "value": "test_datr_456",
                "domain": ".facebook.com",
                "path": "/",
                "httpOnly": True,
                "secure": True
            }
        ],
        "origins": [
            {
                "origin": "https://facebook.com",
                "localStorage": [
                    {
                        "name": "user_preferences",
                        "value": "{'theme': 'dark', 'notifications': True}"
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_facebook_pages():
    """Sample Facebook page sources for testing"""
    return {
        'login': """
        <html>
            <head><title>Facebook - Log In or Sign Up</title></head>
            <body>
                <h1>Log into Facebook</h1>
                <form>
                    <input type="email" placeholder="Email or phone number">
                    <input type="password" placeholder="Password">
                    <button type="submit">Log In</button>
                </form>
                <a href="/recover">Forgotten password?</a>
            </body>
        </html>
        """,
        
        'home': """
        <html>
            <head><title>Facebook</title></head>
            <body>
                <nav class="facebook-nav">
                    <div class="nav-left">Facebook</div>
                    <div class="nav-right">Profile</div>
                </nav>
                <div class="newsfeed">
                    <div class="post">Post content 1</div>
                    <div class="post">Post content 2</div>
                </div>
            </body>
        </html>
        """,
        
        'profile': """
        <html>
            <head><title>Profile - Facebook</title></head>
            <body>
                <nav class="facebook-nav">Facebook</nav>
                <div class="profile-header">
                    <h1>User Profile</h1>
                    <div class="profile-info">User information</div>
                </div>
                <div class="profile-posts">
                    <div class="post">Profile post 1</div>
                </div>
            </body>
        </html>
        """,
        
        'rate_limited': """
        <html>
            <head><title>Facebook</title></head>
            <body>
                <div class="error-message">
                    <h1>Rate limit exceeded</h1>
                    <p>Too many requests. Please try again later.</p>
                </div>
            </body>
        </html>
        """,
        
        'captcha': """
        <html>
            <head><title>Security Check - Facebook</title></head>
            <body>
                <div class="security-check">
                    <h1>Security check required</h1>
                    <p>Please confirm you're human by completing this verification.</p>
                    <div class="captcha-widget">CAPTCHA goes here</div>
                </div>
            </body>
        </html>
        """,
        
        'error': """
        <html>
            <head><title>Error - Facebook</title></head>
            <body>
                <div class="error-page">
                    <h1>Something went wrong</h1>
                    <p>An error occurred while processing your request.</p>
                    <a href="/">Go back to Facebook</a>
                </div>
            </body>
        </html>
        """
    }


@pytest.fixture
def mock_cv2_image():
    """Mock OpenCV image for visual testing"""
    try:
        import numpy as np
        # Create a simple test image (480x640 RGB)
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        # Add some basic patterns for testing
        image[100:200, 100:200] = [255, 0, 0]  # Red square
        image[300:400, 300:400] = [0, 255, 0]  # Green square
        return image
    except ImportError:
        # If numpy is not available, return None
        return None


@pytest.fixture
def security_test_data():
    """Test data with various security patterns for filtering tests"""
    return {
        'sensitive_urls': [
            'https://user:password123@facebook.com/api',
            'https://facebook.com/login?token=secret_abc123',
            'https://admin:admin@internal.facebook.com/debug'
        ],
        'sensitive_logs': [
            'User logged in with password=mypassword123',
            'API call with Authorization: Bearer xyz789token',
            'Cookie: sessionid=sensitive_session_data; path=/',
            'Database connection: mysql://user:pass@localhost/db'
        ],
        'api_keys': [
            'sk-1234567890abcdef',
            'AIzaSyBxxxxxxxxxxxxxxx',
            'AKIAIOSFODNN7EXAMPLE',
            'sess_abc123xyz789'
        ],
        'safe_content': [
            'User successfully logged in',
            'Navigation to profile page completed',
            'Screenshot saved to ./logs/screenshot_001.png',
            'Rate limiting: waited 2.5 seconds before request'
        ]
    }


# Pytest hooks for custom behavior
def pytest_configure(config):
    """Configure pytest with custom settings"""
    # Add custom markers
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "browser: mark test as requiring browser automation"
    )
    config.addinivalue_line(
        "markers", "network: mark test as requiring network access"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers and organize tests"""
    # Add slow marker to tests that might take longer
    slow_keywords = ['integration', 'browser', 'visual', 'concurrent']
    browser_keywords = ['selenium', 'playwright', 'chrome', 'webdriver']
    
    for item in items:
        # Add slow marker
        if any(keyword in item.nodeid.lower() for keyword in slow_keywords):
            item.add_marker(pytest.mark.slow)
        
        # Add browser marker
        if any(keyword in item.nodeid.lower() for keyword in browser_keywords):
            item.add_marker(pytest.mark.browser)
        
        # Add integration marker for integration tests
        if 'integration' in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # Add visual marker for visual tests
        if 'visual' in item.nodeid:
            item.add_marker(pytest.mark.visual)
        
        # Add security marker for security tests
        if 'security' in item.nodeid:
            item.add_marker(pytest.mark.security)


def pytest_runtest_setup(item):
    """Setup hook run before each test"""
    # Skip browser tests if browser dependencies not available
    if item.get_closest_marker("browser"):
        try:
            import selenium
        except ImportError:
            pytest.skip("Browser automation dependencies not available")
    
    # Skip visual tests if OpenCV not available
    if item.get_closest_marker("visual"):
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not available for visual testing")


@pytest.fixture(autouse=True)
def secure_test_environment():
    """Automatically ensure secure test environment"""
    # Ensure no real credentials are used in tests
    sensitive_env_vars = [
        'FACEBOOK_EMAIL', 'FACEBOOK_PASSWORD', 'FB_ACCESS_TOKEN',
        'PRODUCTION_API_KEY', 'CHROME_PROFILE_PATH'
    ]
    
    original_values = {}
    for var in sensitive_env_vars:
        if var in os.environ:
            original_values[var] = os.environ[var]
            del os.environ[var]
    
    yield
    
    # Restore original environment
    for var, value in original_values.items():
        os.environ[var] = value


# Performance measurement fixtures
@pytest.fixture
def performance_monitor():
    """Monitor test performance"""
    import time
    start_time = time.time()
    
    yield
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Log slow tests
    if duration > 5.0:  # 5 seconds threshold
        print(f"\n⚠️  Slow test detected: {duration:.2f}s")


# Mock fixtures for external dependencies
@pytest.fixture
def mock_external_apis():
    """Mock all external API calls"""
    with patch('requests.get') as mock_get, \
         patch('requests.post') as mock_post, \
         patch('websockets.connect') as mock_ws:
        
        # Default responses
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "mocked"}
        
        mock_get.return_value = mock_response
        mock_post.return_value = mock_response
        
        # Mock WebSocket
        mock_websocket = MagicMock()
        mock_ws.return_value = mock_websocket
        
        yield {
            'http_get': mock_get,
            'http_post': mock_post,
            'websocket': mock_websocket
        }