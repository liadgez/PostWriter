#!/usr/bin/env python3
"""
HTTP-based Facebook scraper for PostWriter
Uses requests-html to scrape posts from mobile Facebook
Based on the working facebook-scraper reference project
"""

import json
import os
import re
from datetime import datetime
from typing import List, Dict
from requests_html import HTMLSession
from bs4 import BeautifulSoup
import time
import requests

# Import shared utilities to eliminate duplication
from utils.cookies import load_cookies_session
from utils.text_processing import clean_text

class FacebookHTTPScraper:
    def __init__(self, config):
        self.config = config
        self.profile_url = config['facebook']['profile_url']
        self.mobile_profile_url = config['facebook'].get('mobile_profile_url', config['facebook']['profile_url'].replace('www.', 'm.'))
        self.cookies_path = config['facebook']['cookies_path']
        self.max_posts = config['scraping']['max_posts']
        self.pages_to_scrape = config['scraping'].get('pages_to_scrape', 5)
        self.retry_attempts = config['scraping'].get('retry_attempts', 3)
        
        # Setup HTTP session with proper decompression handling
        self.session = HTMLSession()
        
        # Configure session to handle compression properly
        self.session.mount('https://', requests.adapters.HTTPAdapter())
        self.session.mount('http://', requests.adapters.HTTPAdapter())
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'identity',  # Disable compression to avoid decoding issues
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Load cookies if available
        load_cookies_session(self.session, self.cookies_path)
        
        # Try to extract cookies from Chrome debugging API if file loading failed
        try:
            response = requests.get("http://localhost:9222/json/tabs", timeout=5)
            tabs = response.json()
            
            for tab in tabs:
                if 'facebook.com' in tab.get('url', ''):
                    # Get cookies from this tab
                    tab_id = tab['id']
                    runtime_response = requests.post(
                        f"http://localhost:9222/json/runtime/evaluate",
                        json={
                            "expression": "document.cookie",
                            "tabId": tab_id
                        },
                        timeout=5
                    )
                    
                    if runtime_response.status_code == 200:
                        cookie_string = runtime_response.json().get('result', {}).get('value', '')
                        if cookie_string:
                            self.parse_cookie_string(cookie_string)
                            print("✅ Extracted cookies from Chrome session")
                            return True
        except Exception as e:
            print(f"⚠️ Could not extract cookies from Chrome: {e}")
        
        return False
    
    def parse_cookie_string(self, cookie_string):
        """Parse cookie string and add to session"""
        for cookie in cookie_string.split(';'):
            if '=' in cookie:
                name, value = cookie.strip().split('=', 1)
                self.session.cookies.set(name, value, domain='.facebook.com')
    
    def scrape_posts(self) -> List[Dict]:
        """Main method to scrape posts using HTTP requests"""
        print("🌐 Starting HTTP-based Facebook scraping...")
        
        posts = []
        try:
            # Try mbasic first (more reliable for scraping)
            mbasic_url = self.mobile_profile_url.replace('m.facebook.com', 'mbasic.facebook.com')
            url = mbasic_url
            print(f"📱 Requesting mbasic: {url}")
            
            # Get the main profile page with proper encoding handling
            response = self.session.get(url, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ Failed to access Facebook. Status: {response.status_code}")
                return []
            
            # Ensure proper text decoding
            response.encoding = response.apparent_encoding or 'utf-8'
            print(f"✅ Successfully accessed Facebook mobile (encoding: {response.encoding})")
            
            # Check if we're redirected to login page
            if 'login' in response.url.lower() or 'Log into Facebook' in response.text:
                print("⚠️ Redirected to login page - authentication required")
                print("📋 To fix this:")
                print("   1. Open Chrome with debugging: chrome --remote-debugging-port=9222")
                print("   2. Login to Facebook manually in that Chrome session")
                print("   3. Navigate to your profile page")
                print("   4. Run the scraper again")
                return []
            
            # Parse posts from the response
            page_posts = self.extract_posts_from_response(response, 0)
            posts.extend(page_posts)
            print(f"📄 Page 1: Found {len(page_posts)} posts")
            
            # Try to find pagination links and follow them
            current_response = response
            pages_scraped = 1
            
            while len(posts) < self.max_posts and pages_scraped < self.pages_to_scrape:
                # Look for "See More" or pagination links
                next_url = self.find_next_page_url(current_response)
                
                if not next_url:
                    print("🛑 No more pages found")
                    break
                
                print(f"📄 Loading page {pages_scraped + 1}: {next_url[:80]}...")
                
                # Request next page
                try:
                    time.sleep(2)  # Be respectful
                    current_response = self.session.get(next_url, timeout=30)
                    
                    if current_response.status_code != 200:
                        print(f"❌ Failed to load page {pages_scraped + 1}")
                        break
                    
                    # Ensure proper text decoding for pagination
                    current_response.encoding = current_response.apparent_encoding or 'utf-8'
                    
                    page_posts = self.extract_posts_from_response(current_response, len(posts))
                    new_posts = [p for p in page_posts if not self.is_duplicate_post(p, posts)]
                    posts.extend(new_posts)
                    
                    print(f"📄 Page {pages_scraped + 1}: Found {len(new_posts)} new posts (total: {len(posts)})")
                    pages_scraped += 1
                    
                    if not new_posts:
                        print("🛑 No new posts found, stopping")
                        break
                        
                except Exception as e:
                    print(f"❌ Error loading page {pages_scraped + 1}: {e}")
                    break
            
            print(f"🎉 Scraping complete! Found {len(posts)} total posts")
            
        except Exception as e:
            print(f"❌ Error during scraping: {e}")
        
        return posts[:self.max_posts]
    
    def extract_posts_from_response(self, response, start_index) -> List[Dict]:
        """Extract posts from HTTP response"""
        posts = []
        
        try:
            # Parse the HTML using the decoded text content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Facebook post selectors - try mbasic first, then mobile
            post_selectors = [
                'div[data-ft]',  # Main mobile post selector
                'table[role="article"]',  # mbasic Facebook posts
                'div[id*="post_"]',  # mbasic post divs
                'div.story_body_container',  # Regular mobile
                'article[data-ft]',  # Article mobile posts
                'div[id*="mall_post_"]',  # Alternative mobile
                'div[class*="story_body"]'  # Fallback
            ]
            
            post_elements = []
            for selector in post_selectors:
                elements = soup.select(selector)
                if elements:
                    post_elements = elements
                    print(f"📝 Using selector: {selector} (found {len(elements)} posts)")
                    break
            
            if not post_elements:
                print("⚠️ No post elements found with any selector")
                # Debug: save HTML to file for inspection
                debug_file = f"./data/debug_html_{int(time.time())}.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(f"🔍 Debug HTML saved to: {debug_file}")
                return []
            
            for i, post_elem in enumerate(post_elements):
                try:
                    post_data = self.parse_mobile_post(post_elem, start_index + i)
                    
                    if post_data and post_data.get('content', '').strip():
                        posts.append(post_data)
                        print(f"  ✅ Post {i+1}: {post_data['content'][:60]}...")
                    else:
                        print(f"  ⚠️ Post {i+1}: Empty content")
                        
                except Exception as e:
                    print(f"  ❌ Error parsing post {i+1}: {e}")
                    continue
        
        except Exception as e:
            print(f"❌ Error extracting posts from response: {e}")
        
        return posts
    
    def parse_mobile_post(self, post_elem, post_index: int) -> Dict:
        """Parse individual mobile Facebook post"""
        try:
            # Extract text content
            content = self.extract_post_text(post_elem)
            
            # Extract engagement metrics
            engagement = self.extract_engagement_metrics(post_elem)
            
            # Extract date
            post_date = self.extract_post_date(post_elem)
            
            # Generate ID
            post_id = f"http_post_{hash(content[:50] if content else str(post_index))}_{post_index}"
            
            # Check for links and CTAs
            has_links = bool(post_elem.find_all('a', href=True))
            content_lower = content.lower() if content else ""
            has_cta = any(cta in content_lower for cta in [
                'click', 'buy', 'shop', 'learn more', 'sign up', 'download',
                'get started', 'contact', 'book', 'order', 'purchase', 'visit'
            ])
            
            return {
                'id': post_id,
                'content': content or "",
                'date': post_date,
                'likes': engagement.get('likes', 0),
                'comments': engagement.get('comments', 0),
                'shares': engagement.get('shares', 0),
                'has_links': has_links,
                'has_cta': has_cta,
                'raw_html': str(post_elem)[:1000]
            }
            
        except Exception as e:
            print(f"Error parsing mobile post: {e}")
            return None
    
    def extract_post_text(self, post_elem) -> str:
        """Extract post text from mobile Facebook element"""
        # Mobile Facebook text selectors
        text_selectors = [
            'div[data-testid="post_message"]',
            'span[data-testid="post_message"]', 
            '.userContent',
            'div[class*="userContent"]',
            'p',
            'div p',
            'span[dir="auto"]',
            'div[dir="auto"]'
        ]
        
        content = ""
        for selector in text_selectors:
            try:
                elements = post_elem.select(selector)
                for elem in elements:
                    text = elem.get_text().strip()
                    if text and len(text) > len(content):
                        content = text
            except:
                continue
        
        # If no content found, try broader search
        if not content:
            all_text = post_elem.get_text()
            lines = [line.strip() for line in all_text.split('\n') if line.strip()]
            
            # Filter out UI elements
            skip_phrases = [
                'like', 'comment', 'share', 'react', 'sponsored', 'promoted',
                'minutes ago', 'hours ago', 'days ago', 'weeks ago', 'just now'
            ]
            
            filtered_lines = []
            for line in lines:
                if len(line) > 10 and not any(skip in line.lower() for skip in skip_phrases):
                    filtered_lines.append(line)
            
            content = ' '.join(filtered_lines[:3])
        
        return clean_text(content)
    
    def extract_engagement_metrics(self, post_elem) -> Dict:
        """Extract likes, comments, shares from mobile post"""
        engagement = {'likes': 0, 'comments': 0, 'shares': 0}
        
        text_content = post_elem.get_text()
        
        # Patterns for mobile Facebook engagement
        patterns = {
            'likes': [
                r'(\d+)\s+(?:reaction|like|love|wow|haha|sad|angry)',
                r'(\d+)\s+(?:reactions?)',
                r'(\d+)\s+(?:people? reacted?)'
            ],
            'comments': [
                r'(\d+)\s+(?:comment)',
                r'(\d+)\s+(?:comments?)'
            ],
            'shares': [
                r'(\d+)\s+(?:share)',
                r'(\d+)\s+(?:shares?)'
            ]
        }
        
        for metric, metric_patterns in patterns.items():
            for pattern in metric_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    engagement[metric] = int(match.group(1))
                    break
        
        return engagement
    
    def extract_post_date(self, post_elem) -> str:
        """Extract post date from mobile element"""
        # Mobile Facebook date selectors
        date_selectors = [
            'abbr[data-utime]',
            'abbr[title]',
            'span[data-utime]',
            'time'
        ]
        
        for selector in date_selectors:
            elem = post_elem.select_one(selector)
            if elem:
                date_str = elem.get('data-utime') or elem.get('title') or elem.get_text()
                if date_str:
                    return date_str
        
        return datetime.now().strftime('%Y-%m-%d')
    
    def find_next_page_url(self, response) -> str:
        """Find pagination URL for next page"""
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Mobile Facebook pagination selectors
        pagination_selectors = [
            'a[href*="cursor"]',
            'a[href*="timestart"]',
            'a[href*="aftercursor"]',
            'a:contains("See More")',
            'a:contains("Show more")',
            '#m_more_item a'
        ]
        
        for selector in pagination_selectors:
            try:
                if ':contains(' in selector:
                    # Handle text-based selectors
                    text = selector.split(':contains("')[1].split('")')[0]
                    links = soup.find_all('a', string=re.compile(text, re.IGNORECASE))
                else:
                    links = soup.select(selector)
                
                for link in links:
                    href = link.get('href')
                    if href:
                        # Make absolute URL
                        if href.startswith('/'):
                            href = 'https://m.facebook.com' + href
                        elif not href.startswith('http'):
                            href = 'https://m.facebook.com/' + href
                        return href
            except:
                continue
        
        return None
    
    def is_duplicate_post(self, new_post: Dict, existing_posts: List[Dict]) -> bool:
        """Check if post is duplicate"""
        new_content = new_post.get('content', '').strip()
        if not new_content:
            return True
        
        for existing_post in existing_posts:
            existing_content = existing_post.get('content', '').strip()
            if existing_content and new_content == existing_content:
                return True
        
        return False
    
