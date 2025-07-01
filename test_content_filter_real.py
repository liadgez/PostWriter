#!/usr/bin/env python3
"""
Test content filter with real scraped data
"""

import json
import os
from content_filter import ContentFilter

def test_with_real_data():
    """Test content filter with actual scraped posts"""
    
    # Load real scraped data
    data_dir = './data/raw_posts/'
    if not os.path.exists(data_dir):
        print("❌ No scraped data found in ./data/raw_posts/")
        return
    
    # Find the most recent scraped file
    scraped_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    if not scraped_files:
        print("❌ No JSON files found in ./data/raw_posts/")
        return
    
    # Load the newest file
    latest_file = sorted(scraped_files)[-1]
    file_path = os.path.join(data_dir, latest_file)
    
    print(f"📁 Loading scraped data from: {latest_file}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            posts = json.load(f)
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return
    
    if not posts:
        print("❌ No posts found in file")
        return
    
    print(f"📊 Found {len(posts)} posts in file")
    
    # Apply content filter
    content_filter = ContentFilter()
    good_posts, filtered_posts = content_filter.filter_post_list(posts)
    stats = content_filter.get_filter_stats(posts, good_posts, filtered_posts)
    
    print(f"\n🔍 Content Filter Results:")
    print(f"   • Total posts: {stats['total_posts']}")
    print(f"   • High quality: {stats['good_posts']}")
    print(f"   • Filtered out: {stats['filtered_posts']} ({stats['filter_rate']:.1f}%)")
    
    if stats['good_posts'] > 0:
        print(f"   • Average quality: {stats['average_quality']:.1f}/10")
        print(f"   • Content types: {dict(stats['content_types'])}")
    
    # Show examples
    print(f"\n✅ HIGH QUALITY POSTS ({len(good_posts)}):")
    for i, post in enumerate(good_posts[:3]):
        content = post.get('content', '')[:100]
        quality = post.get('quality_score', 0)
        content_type = post.get('content_type', 'unknown')
        print(f"   {i+1}. [{content_type}, {quality:.1f}/10] {content}...")
    
    print(f"\n❌ FILTERED OUT POSTS ({len(filtered_posts)}):")
    for i, post in enumerate(filtered_posts[:5]):
        original_content = post.get('content', '') or post.get('text', '')
        reasons = post.get('filter_reason', [])
        quality = post.get('quality_score', 0)
        print(f"   {i+1}. [{quality:.1f}/10] '{original_content[:50]}...' - {reasons}")
    
    # If we have good posts, save them
    if good_posts:
        output_file = f'./data/filtered_posts_{len(good_posts)}_high_quality.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(good_posts, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved {len(good_posts)} high-quality posts to: {output_file}")
    
    return good_posts, filtered_posts, stats

if __name__ == '__main__':
    test_with_real_data()