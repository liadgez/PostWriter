#!/usr/bin/env python3
"""
Connect to existing Chrome session and scrape Liran's posts
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import time
from datetime import datetime

def connect_to_chrome():
    """Connect to existing Chrome session"""
    options = Options()
    options.add_experimental_option("debuggerAddress", "localhost:9222")
    
    try:
        driver = webdriver.Chrome(options=options)
        return driver
    except Exception as e:
        print(f"Failed to connect to Chrome: {e}")
        return None

def scrape_posts(driver):
    """Scrape posts from current page"""
    print("🔍 Looking for posts...")
    
    # Wait a bit for the page to load
    time.sleep(3)
    
    posts = []
    
    try:
        # Try different selectors for Facebook posts
        post_selectors = [
            '[data-pagelet="FeedUnit_0"]',
            '[role="article"]',
            '[data-testid="post"]',
            '.userContentWrapper',
            '.story_body_container',
            '[data-ad-preview="message"]'
        ]
        
        found_posts = []
        for selector in post_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    print(f"✅ Found {len(elements)} elements with selector: {selector}")
                    found_posts.extend(elements)
                    break
            except:
                continue
        
        if not found_posts:
            # Try a more general approach - look for any div with substantial text
            all_divs = driver.find_elements(By.TAG_NAME, "div")
            for div in all_divs:
                try:
                    text = div.text.strip()
                    if len(text) > 100 and "Liran" in text:  # Filter for Liran's content
                        found_posts.append(div)
                        if len(found_posts) >= 20:
                            break
                except:
                    continue
        
        print(f"Processing {len(found_posts)} potential posts...")
        
        for i, element in enumerate(found_posts[:50]):
            try:
                post_text = element.text.strip()
                # Better filtering for actual posts
                if (len(post_text) > 50 and 
                    ("Liran" in post_text or "לירן" in post_text)):  # Much more relaxed filtering
                    
                    # Clean up the text
                    lines = post_text.split('\n')
                    clean_lines = []
                    for line in lines:
                        line = line.strip()
                        if (line and 
                            line != "Liran Galizyan" and 
                            line != "Author" and
                            line != "Like" and
                            line != "Reply" and
                            not line.startswith("http") and
                            not line.endswith("w") and  # Remove time stamps like "5w"
                            len(line) > 3):
                            clean_lines.append(line)
                    
                    clean_text = '\n'.join(clean_lines)
                    
                    if len(clean_text) > 20:
                        post_data = {
                            'id': len(posts) + 1,
                            'text': clean_text[:2000] + '...' if len(clean_text) > 2000 else clean_text,
                            'raw_text': post_text,
                            'timestamp': datetime.now().isoformat(),
                            'source': 'chrome_scraper'
                        }
                        posts.append(post_data)
                        print(f"📝 Post {len(posts)}: {clean_text[:100]}...")
                        
                        if len(posts) >= 20:
                            break
                            
            except Exception as e:
                print(f"Error processing post {i}: {e}")
                continue
        
    except Exception as e:
        print(f"Error finding posts: {e}")
    
    return posts

def main():
    print("🚀 Connecting to Chrome and scraping Liran's posts...")
    
    driver = connect_to_chrome()
    if not driver:
        print("❌ Could not connect to Chrome")
        return
    
    try:
        # Check current URL
        current_url = driver.current_url
        print(f"📍 Current URL: {current_url}")
        
        # Make sure we're on Liran's page
        if "liran.galizian" not in current_url:
            print("🔄 Navigating to Liran's profile...")
            driver.get("https://www.facebook.com/liran.galizian")
            time.sleep(5)
        
        # Scroll down more to load many posts
        print("📜 Scrolling to load more posts...")
        for i in range(10):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            print(f"Scroll {i+1}/10")
        
        # Scrape posts
        posts = scrape_posts(driver)
        
        if posts:
            print(f"\n✅ Successfully scraped {len(posts)} posts!")
            
            # Save to file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'./data/raw_posts/liran_posts_{timestamp}.json'
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(posts, f, indent=2, ensure_ascii=False)
            
            print(f"📁 Saved to {filename}")
            
            # Print first few posts
            print(f"\n📋 First 5 posts:")
            for post in posts[:5]:
                print(f"\n--- Post {post['id']} ---")
                print(post['text'][:300] + "..." if len(post['text']) > 300 else post['text'])
        else:
            print("❌ No posts found")
            
    except Exception as e:
        print(f"Error during scraping: {e}")
    
    finally:
        # Don't close the driver to keep Chrome session alive
        print("✅ Scraping complete (keeping Chrome session alive)")

if __name__ == "__main__":
    main()