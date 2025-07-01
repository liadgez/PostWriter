#!/usr/bin/env python3
"""
Facebook scraper for PostWriter
Uses HTTP requests to scrape posts from mobile Facebook
"""

import json
import os
from datetime import datetime
from typing import List, Dict
from scraper_http import FacebookHTTPScraper

class FacebookScraper:
    def __init__(self, config):
        """Initialize with HTTP-based scraper"""
        self.config = config
        self.http_scraper = FacebookHTTPScraper(config)
    
    def scrape_posts(self) -> List[Dict]:
        """Main method to scrape posts (synchronous wrapper)"""
        if not self.config['facebook']['profile_url']:
            raise ValueError("Profile URL not configured")
        
        # Save to raw posts directory
        raw_posts_dir = self.config['directories']['raw_posts_dir']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        try:
            # Use HTTP scraper
            posts = self.http_scraper.scrape_posts()
            
            # Save raw data
            raw_file = os.path.join(raw_posts_dir, f'posts_{timestamp}.json')
            with open(raw_file, 'w', encoding='utf-8') as f:
                json.dump(posts, f, indent=2, ensure_ascii=False)
            
            print(f"📁 Raw posts saved to {raw_file}")
            return posts
            
        except Exception as e:
            print(f"❌ Scraping failed: {e}")
            return []
    
    def login_step(self):
        """Placeholder for login step - not needed for HTTP scraper"""
        print("ℹ️ HTTP scraper uses saved cookies. Make sure you're logged into Facebook in Chrome.")
        print("Run: python3 postwriter.py sync")

# Example usage
if __name__ == '__main__':
    # Test configuration
    config = {
        'facebook': {
            'profile_url': 'https://www.facebook.com/your-profile',
            'mobile_profile_url': 'https://m.facebook.com/your-profile',
            'cookies_path': './data/cookies.json'
        },
        'scraping': {
            'max_posts': 10,
            'pages_to_scrape': 3,
            'retry_attempts': 3
        },
        'directories': {
            'raw_posts_dir': './data/raw_posts'
        }
    }
    
    scraper = FacebookScraper(config)
    posts = scraper.scrape_posts()
    print(f"✅ Scraped {len(posts)} posts")