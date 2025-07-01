"""
Shared cookie loading utilities
===============================

Common cookie loading functions extracted from multiple scraper modules
to eliminate duplication. Now supports secure encrypted cookie storage.
"""

import json
import os
from typing import Dict, Optional

# Import secure storage (optional for backward compatibility)
try:
    from secure_storage import CookieManager
    SECURE_STORAGE_AVAILABLE = True
except ImportError:
    SECURE_STORAGE_AVAILABLE = False


def load_cookies_dict(cookies_path: str = './data/cookies.json', use_secure: bool = True, password: str = None) -> Dict[str, str]:
    """
    Load cookies from JSON file and return as dictionary.
    Supports both regular JSON files and secure encrypted storage.
    
    Args:
        cookies_path: Path to cookies JSON file
        use_secure: Whether to try secure storage first
        password: Password for secure storage (will prompt if needed)
        
    Returns:
        Dictionary of cookie name-value pairs
    """
    # Try secure storage first if available and requested
    if use_secure and SECURE_STORAGE_AVAILABLE:
        try:
            secure_path = cookies_path.replace('.json', '.secure')
            cookie_mgr = CookieManager(secure_path)
            if cookie_mgr.has_cookies():
                print("🔒 Loading cookies from secure storage...")
                return cookie_mgr.get_cookies_for_requests(password)
        except Exception as e:
            print(f"⚠️ Secure cookie loading failed, trying regular file: {e}")
    
    # Fallback to regular file loading
    cookies_dict = {}
    try:
        with open(cookies_path, 'r') as f:
            cookies_data = json.load(f)
            
            # Handle different cookie formats
            if isinstance(cookies_data, list):
                # Array of cookie objects
                for cookie in cookies_data:
                    if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                        cookies_dict[cookie['name']] = cookie['value']
            elif isinstance(cookies_data, dict):
                # Direct name-value mapping
                cookies_dict = cookies_data
            
        print(f"📄 Loaded {len(cookies_dict)} cookies from regular file")
        return cookies_dict
        
    except FileNotFoundError:
        print(f"⚠️ Cookie file not found: {cookies_path}")
        return {}
    except Exception as e:
        print(f"❌ Error loading cookies: {e}")
        return {}


def load_cookies_session(session, cookies_path: str) -> bool:
    """
    Load cookies from JSON file into a requests session.
    Used by scraper_http.py.
    
    Args:
        session: Requests session object
        cookies_path: Path to cookies JSON file
        
    Returns:
        True if cookies loaded successfully, False otherwise
    """
    try:
        if os.path.exists(cookies_path):
            with open(cookies_path, 'r') as f:
                cookies_data = json.load(f)
                for cookie in cookies_data:
                    session.cookies.set(
                        cookie['name'], 
                        cookie['value'], 
                        domain=cookie.get('domain', '.facebook.com')
                    )
            print("✅ Loaded cookies from file")
            return True
    except Exception as e:
        print(f"⚠️ Could not load cookies: {e}")
    return False


async def load_cookies_playwright(context, cookies_path: str) -> bool:
    """
    Load cookies from JSON file into a Playwright context.
    Used by scraper_playwright_backup.py.
    
    Args:
        context: Playwright browser context
        cookies_path: Path to cookies JSON file
        
    Returns:
        True if cookies loaded successfully, False otherwise
    """
    try:
        if os.path.exists(cookies_path):
            with open(cookies_path, 'r') as f:
                cookies = json.load(f)
                await context.add_cookies(cookies)
                return True
    except Exception as e:
        print(f"Error loading cookies: {e}")
    return False