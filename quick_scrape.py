#!/usr/bin/env python3
"""
Quick Facebook scraper using requests with proper cookie handling
"""

import requests
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup
import re

# Import shared utilities to eliminate duplication
from utils.cookies import load_cookies_dict
from content_filter import ContentFilter

def scrape_liran_posts():
    """Scrape posts from Liran's profile"""
    cookies = load_cookies_dict()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    session = requests.Session()
    session.headers.update(headers)
    session.cookies.update(cookies)
    
    # Try basic mobile version first
    url = "https://mbasic.facebook.com/liran.galizian"
    print(f"Requesting: {url}")
    
    try:
        response = session.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            # Save HTML for debugging
            with open('./data/liran_page.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            # Check if we're logged in
            if 'login' in response.url.lower() or 'login' in response.text.lower():
                print("❌ Redirected to login page")
                return []
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find posts - mobile Facebook uses different selectors
            posts = []
            
            # Look for story containers
            story_elements = soup.find_all('div', {'role': 'article'}) or soup.find_all('article')
            
            if not story_elements:
                # Try other selectors
                story_elements = soup.find_all('div', class_=re.compile(r'story|post|userContent'))
            
            print(f"Found {len(story_elements)} potential post elements")
            
            # Extract posts with better content detection
            for i, element in enumerate(story_elements[:20]):  # Limit to 20 posts
                post_text = element.get_text(strip=True)
                if len(post_text) > 30:  # Initial length filter
                    posts.append({
                        'id': f'quick_post_{i + 1}',
                        'content': post_text,
                        'source': 'quick_scrape'
                    })
            
            # Apply content quality filtering
            if posts:
                content_filter = ContentFilter()
                good_posts, filtered_posts = content_filter.filter_post_list(posts)
                stats = content_filter.get_filter_stats(posts, good_posts, filtered_posts)
                
                print(f"📊 Content Quality Results:")
                print(f"   • Total found: {stats['total_posts']}")
                print(f"   • High quality: {stats['good_posts']}")
                print(f"   • Filtered out: {stats['filtered_posts']} ({stats['filter_rate']:.1f}%)")
                
                if stats['good_posts'] > 0:
                    print(f"   • Average quality: {stats['average_quality']:.1f}/10")
                    print(f"   • Content types: {dict(stats['content_types'])}")
                
                return good_posts
            
            return posts
        else:
            print(f"❌ Failed to access page: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def main():
    print("🚀 Quick scraping Liran's posts...")
    posts = scrape_liran_posts()
    
    if posts:
        print(f"✅ Found {len(posts)} posts:")
        for post in posts:
            print(f"\n--- Post {post['id']} ---")
            print(post['text'])
        
        # Save to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'./data/raw_posts/liran_posts_{timestamp}.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(posts, f, indent=2, ensure_ascii=False)
        print(f"\n📁 Saved to {filename}")
    else:
        print("❌ No posts found")

if __name__ == "__main__":
    main()