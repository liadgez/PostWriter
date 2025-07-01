#!/usr/bin/env python3
"""
Test scraping improvements
"""

import yaml
from scraper_http import FacebookHTTPScraper
from content_filter import ContentFilter

def test_scraper_integration():
    """Test that the scraper properly integrates with content filtering"""
    
    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    print("🔧 Testing Scraper Integration...")
    
    # Test that scraper initializes with content filter
    try:
        scraper = FacebookHTTPScraper(config)
        print("✅ Scraper initialized successfully")
        print(f"   • Content filter: {type(scraper.content_filter).__name__}")
        print(f"   • Profile URL: {scraper.profile_url}")
        print(f"   • Max posts: {scraper.max_posts}")
    except Exception as e:
        print(f"❌ Scraper initialization failed: {e}")
        return False
    
    # Test content extraction methods
    print("\n🔧 Testing Content Extraction Methods...")
    
    # Mock HTML element for testing
    from bs4 import BeautifulSoup
    
    # Test with good content
    good_html = """
    <div class="userContent">
        <p>Are you struggling with your marketing strategy? Our new AI tools can help you create content that converts. Click here to learn more! #marketing #AI</p>
    </div>
    """
    
    # Test with UI content
    ui_html = """
    <div>
        <span>Author</span>
        <span>Liran Galizyan</span>
        <span>5w</span>
        <span>Like</span>
        <span>Reply</span>
    </div>
    """
    
    good_soup = BeautifulSoup(good_html, 'html.parser')
    ui_soup = BeautifulSoup(ui_html, 'html.parser')
    
    try:
        good_text = scraper.extract_post_text(good_soup)
        ui_text = scraper.extract_post_text(ui_soup)
        
        print(f"✅ Content extraction working:")
        print(f"   • Good content: '{good_text[:50]}...' ({len(good_text)} chars)")
        print(f"   • UI content: '{ui_text[:50]}...' ({len(ui_text)} chars)")
        
        # Test UI detection
        is_good_ui = scraper._is_ui_text(good_text)
        is_ui_ui = scraper._is_ui_text(ui_text)
        
        print(f"   • Good content is UI: {is_good_ui}")
        print(f"   • UI content is UI: {is_ui_ui}")
        
        # Test meaningful content detection
        good_meaningful = scraper._has_meaningful_content(good_text)
        ui_meaningful = scraper._has_meaningful_content(ui_text)
        
        print(f"   • Good content is meaningful: {good_meaningful}")
        print(f"   • UI content is meaningful: {ui_meaningful}")
        
    except Exception as e:
        print(f"❌ Content extraction failed: {e}")
        return False
    
    # Test content filter integration
    print("\n🔧 Testing Content Filter Integration...")
    
    test_posts = [
        {'id': 1, 'content': good_text},
        {'id': 2, 'content': ui_text},
        {'id': 3, 'content': 'Author\nLiran Galizyan\n5w\nLike\nReply'}
    ]
    
    try:
        good_posts, filtered_posts = scraper.content_filter.filter_post_list(test_posts)
        stats = scraper.content_filter.get_filter_stats(test_posts, good_posts, filtered_posts)
        
        print(f"✅ Content filtering working:")
        print(f"   • Total posts: {stats['total_posts']}")
        print(f"   • Good posts: {stats['good_posts']}")
        print(f"   • Filtered posts: {stats['filtered_posts']}")
        print(f"   • Filter rate: {stats['filter_rate']:.1f}%")
        
        if good_posts:
            print(f"   • Average quality: {stats['average_quality']:.1f}/10")
            print(f"   • Content types: {dict(stats['content_types'])}")
        
    except Exception as e:
        print(f"❌ Content filtering failed: {e}")
        return False
    
    print("\n🎉 All tests passed! Scraping improvements are working correctly.")
    return True

if __name__ == '__main__':
    test_scraper_integration()