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
from rate_limiter import get_rate_limiter, RequestType
from secure_logging import get_secure_logger

# Import custom exceptions
from exceptions import (
    ScrapingError, 
    AuthenticationError, 
    CookieError,
    FacebookAccessError,
    DataQualityError
)

# Import content quality filter
from content_filter import ContentFilter

class FacebookHTTPScraper:
    def __init__(self, config):
        self.config = config
        self.profile_url = config['facebook']['profile_url']
        self.mobile_profile_url = config['facebook'].get('mobile_profile_url', config['facebook']['profile_url'].replace('www.', 'm.'))
        self.cookies_path = config['facebook']['cookies_path']
        self.max_posts = config['scraping']['max_posts']
        self.pages_to_scrape = config['scraping'].get('pages_to_scrape', 5)
        self.retry_attempts = config['scraping'].get('retry_attempts', 3)
        
        # Initialize content filter
        self.content_filter = ContentFilter()
        
        # Initialize rate limiter and logger
        self.rate_limiter = get_rate_limiter()
        self.logger = get_secure_logger("scraper")
        
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
        self._try_extract_chrome_cookies()
    
    def _try_extract_chrome_cookies(self):
        """Try to extract cookies from Chrome debugging API"""
        try:
            # Apply rate limiting for Chrome API requests
            wait_time = self.rate_limiter.wait_for_request(RequestType.API_CALL, "http://localhost:9222/json/tabs")
            
            start_time = time.time()
            response = requests.get("http://localhost:9222/json/tabs", timeout=5)
            response_time = time.time() - start_time
            
            # Record the Chrome API request
            self.rate_limiter.record_request(
                RequestType.API_CALL,
                "http://localhost:9222/json/tabs",
                response.status_code,
                response.text[:500],
                response_time
            )
            
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
        except requests.RequestException as e:
            # Don't raise exception in initialization, just warn
            print(f"⚠️ Chrome debugging API not available: {e}")
        except (KeyError, ValueError) as e:
            print(f"⚠️ Invalid response from Chrome debugging API: {e}")
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
            # Validate profile URL
            if not self.mobile_profile_url:
                raise FacebookAccessError("No profile URL configured")
            
            # Try mbasic first (more reliable for scraping)
            mbasic_url = self.mobile_profile_url.replace('m.facebook.com', 'mbasic.facebook.com')
            url = mbasic_url
            print(f"📱 Requesting mbasic: {url}")
            
            # Get the main profile page with proper encoding handling and rate limiting
            try:
                # Apply rate limiting before request
                wait_time = self.rate_limiter.wait_for_request(RequestType.PAGE_LOAD, url)
                if wait_time > 0:
                    self.logger.info(f"⏱️ Rate limiting: waited {wait_time:.1f}s before Facebook request")
                
                # Make the request
                start_time = time.time()
                response = self.session.get(url, timeout=30)
                response_time = time.time() - start_time
                
                # Record the request for rate limiting analysis
                self.rate_limiter.record_request(
                    RequestType.PAGE_LOAD,
                    url,
                    response.status_code,
                    response.text[:1000],  # First 1000 chars for analysis
                    response_time
                )
                
            except requests.RequestException as e:
                # Record failed request
                self.rate_limiter.record_request(
                    RequestType.PAGE_LOAD,
                    url,
                    None,
                    "",
                    0.0,
                    str(e)
                )
                raise FacebookAccessError(f"Failed to connect to Facebook: {e}")
            
            if response.status_code == 404:
                raise FacebookAccessError(f"Profile not found: {url}")
            elif response.status_code == 429:
                raise FacebookAccessError("Rate limited by Facebook. Please wait and try again.")
            elif response.status_code != 200:
                raise FacebookAccessError(f"Facebook returned status {response.status_code}")
            
            # Ensure proper text decoding
            response.encoding = response.apparent_encoding or 'utf-8'
            print(f"✅ Successfully accessed Facebook mobile (encoding: {response.encoding})")
            
            # Check if we're redirected to login page
            if 'login' in response.url.lower() or 'Log into Facebook' in response.text:
                raise AuthenticationError(
                    "Authentication required. Please:\n"
                    "   1. Open Chrome with debugging: chrome --remote-debugging-port=9222\n"
                    "   2. Login to Facebook manually in that Chrome session\n"
                    "   3. Navigate to your profile page\n"
                    "   4. Run the scraper again"
                )
            
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
                
                # Request next page with rate limiting
                try:
                    # Apply intelligent rate limiting (replaces simple sleep)
                    wait_time = self.rate_limiter.wait_for_request(RequestType.PAGE_LOAD, next_url)
                    if wait_time > 0:
                        self.logger.info(f"⏱️ Rate limiting: waited {wait_time:.1f}s before pagination request")
                    
                    # Make the pagination request
                    start_time = time.time()
                    current_response = self.session.get(next_url, timeout=30)
                    response_time = time.time() - start_time
                    
                    # Record the pagination request
                    success = self.rate_limiter.record_request(
                        RequestType.PAGE_LOAD,
                        next_url,
                        current_response.status_code,
                        current_response.text[:1000],
                        response_time
                    )
                    
                    if current_response.status_code != 200:
                        self.logger.warning(f"❌ Failed to load page {pages_scraped + 1} (status: {current_response.status_code})")
                        break
                    
                    # Check if we're being rate limited
                    if not success:
                        self.logger.warning(f"⚠️ Rate limiting detected on page {pages_scraped + 1}, may slow down further requests")
                
                    
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
            
            # Apply content quality filtering
            if posts:
                print("🔍 Filtering content quality...")
                good_posts, filtered_posts = self.content_filter.filter_post_list(posts)
                stats = self.content_filter.get_filter_stats(posts, good_posts, filtered_posts)
                
                print(f"📊 Quality Filter Results:")
                print(f"   • Total scraped: {stats['total_posts']}")
                print(f"   • High quality: {stats['good_posts']}")
                print(f"   • Filtered out: {stats['filtered_posts']} ({stats['filter_rate']:.1f}%)")
                print(f"   • Average quality: {stats['average_quality']:.1f}/10")
                
                if stats['content_types']:
                    print(f"   • Content types: {dict(stats['content_types'])}")
                
                # Use filtered posts
                posts = good_posts
                
                if not posts:
                    raise DataQualityError(
                        "All scraped content was filtered out due to poor quality. "
                        "This usually means the scraper is getting UI elements instead of actual posts. "
                        "Try logging into Facebook manually and ensuring you're on the correct profile page."
                    )
            
        except Exception as e:
            if isinstance(e, (ScrapingError, AuthenticationError, FacebookAccessError, DataQualityError)):
                raise  # Re-raise our custom exceptions
            else:
                raise ScrapingError(f"Unexpected error during scraping: {e}")
        
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
        """Extract post text from mobile Facebook element with improved quality"""
        # Priority order: Try more specific selectors first
        content_candidates = []
        
        # 1. Try specific Facebook post content selectors
        specific_selectors = [
            'div[data-testid="post_message"]',
            'span[data-testid="post_message"]',
            '.userContent',
            'div[class*="userContent"]',
            '[data-ad-preview="message"]',
            'div[data-ft*="top_level_post_id"]'
        ]
        
        for selector in specific_selectors:
            try:
                elements = post_elem.select(selector)
                for elem in elements:
                    text = elem.get_text().strip()
                    if text and len(text) > 20:  # Minimum length threshold
                        content_candidates.append((text, len(text), 'specific'))
            except:
                continue
        
        # 2. Try paragraph and div elements
        text_elements = ['p', 'div[dir="auto"]', 'span[dir="auto"]']
        for selector in text_elements:
            try:
                elements = post_elem.select(selector)
                for elem in elements:
                    text = elem.get_text().strip()
                    # Check if this looks like actual content
                    if (len(text) > 30 and 
                        not self._is_ui_text(text) and
                        self._has_meaningful_content(text)):
                        content_candidates.append((text, len(text), 'element'))
            except:
                continue
        
        # 3. If still no good content, try broader extraction with filtering
        if not content_candidates:
            all_text = post_elem.get_text()
            lines = [line.strip() for line in all_text.split('\n') if line.strip()]
            
            # Build content from meaningful lines
            meaningful_lines = []
            for line in lines:
                if (len(line) > 15 and 
                    not self._is_ui_text(line) and
                    self._has_meaningful_content(line)):
                    meaningful_lines.append(line)
            
            if meaningful_lines:
                combined_text = '\n'.join(meaningful_lines[:5])  # Max 5 lines
                if len(combined_text) > 30:
                    content_candidates.append((combined_text, len(combined_text), 'extracted'))
        
        # Select best candidate
        if content_candidates:
            # Sort by priority: specific > element > extracted, then by length
            priority_order = {'specific': 3, 'element': 2, 'extracted': 1}
            content_candidates.sort(key=lambda x: (priority_order[x[2]], x[1]), reverse=True)
            best_content = content_candidates[0][0]
            return clean_text(best_content)
        
        return ""
    
    def _is_ui_text(self, text: str) -> bool:
        """Check if text appears to be UI elements"""
        text_lower = text.lower().strip()
        
        # Common UI patterns
        ui_patterns = [
            r'^\d+[wdhms]$',  # Time stamps like "5w", "2d", "3h"
            r'^(like|comment|share|reply|react)$',
            r'^(author|online status|active|offline)$',
            r'^(see more|see less|show more|show less)$',
            r'^(sponsored|promoted|ad)$',
            r'^\d+\s+(like|comment|share)s?$',  # "5 likes", "2 comments"
        ]
        
        for pattern in ui_patterns:
            if re.match(pattern, text_lower):
                return True
        
        # Check for high ratio of UI words
        ui_keywords = {
            'like', 'comment', 'share', 'reply', 'react', 'author', 'sponsored',
            'promoted', 'see more', 'see less', 'show more', 'active', 'offline'
        }
        
        words = text_lower.split()
        if len(words) > 0:
            ui_word_ratio = sum(1 for word in words if word in ui_keywords) / len(words)
            if ui_word_ratio > 0.5:
                return True
        
        return False
    
    def _has_meaningful_content(self, text: str) -> bool:
        """Check if text contains meaningful content"""
        text_lower = text.lower()
        
        # Look for content indicators
        content_indicators = {
            # Question words
            'what', 'how', 'why', 'when', 'where', 'who', 'which',
            # Marketing terms
            'get', 'buy', 'learn', 'discover', 'find', 'click', 'visit',
            # Common verbs and adjectives that indicate real content
            'amazing', 'great', 'best', 'new', 'free', 'special', 'important',
            'today', 'now', 'here', 'this', 'that', 'you', 'we', 'our'
        }
        
        # Check for sentence structure
        has_sentence_structure = ('.' in text or '!' in text or '?' in text)
        has_multiple_words = len(text.split()) >= 4
        has_content_words = any(word in text_lower for word in content_indicators)
        has_hashtags = '#' in text
        has_urls = 'http' in text_lower or 'www.' in text_lower
        
        return (has_sentence_structure or has_content_words or 
                has_hashtags or has_urls) and has_multiple_words
    
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
    
