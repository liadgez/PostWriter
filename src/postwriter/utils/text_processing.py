"""
Shared text processing utilities
===============================

Common text processing functions extracted from multiple scraper modules
to eliminate duplication.
"""

import re


def clean_text(text: str) -> str:
    """
    Clean and normalize text content.
    Used by both scraper_http.py and scraper_playwright_backup.py.
    
    Args:
        text: Raw text content to clean
        
    Returns:
        Cleaned and normalized text
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Remove Facebook-specific artifacts
    text = re.sub(r'See more|See less', '', text)
    text = re.sub(r'\d+\s*(likes?|comments?|shares?)', '', text, flags=re.IGNORECASE)
    
    # Clean up line breaks
    text = text.replace('\\n', '\n').strip()
    
    return text