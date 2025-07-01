"""
Shared cookie loading utilities
===============================

Common cookie loading functions extracted from multiple scraper modules
to eliminate duplication.
"""

import json
import os
from typing import Dict, Optional


def load_cookies_dict(cookies_path: str = './data/cookies.json') -> Dict[str, str]:
    """
    Load cookies from JSON file and return as dictionary.
    Used by quick_scrape.py.
    
    Args:
        cookies_path: Path to cookies JSON file
        
    Returns:
        Dictionary of cookie name-value pairs
    """
    cookies_dict = {}
    try:
        with open(cookies_path, 'r') as f:
            cookies_data = json.load(f)
            for cookie in cookies_data:
                cookies_dict[cookie['name']] = cookie['value']
        return cookies_dict
    except Exception as e:
        print(f"Error loading cookies: {e}")
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