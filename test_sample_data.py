#!/usr/bin/env python3
"""
Create sample Facebook posts for testing the analysis system
"""

import json
import os
from datetime import datetime, timedelta
from database import PostDatabase
import yaml

# Sample posts that simulate Liran's marketing content
sample_posts = [
    {
        'id': 'post_1',
        'content': """Are you struggling with your social media marketing strategy? 

Most businesses waste hours creating content that gets zero engagement. But there's a better way.

Our AI-powered marketing tools help you create content that actually converts. Join thousands of businesses already seeing 300% better results.

Click the link to get started today! 🚀 #marketing #AI #socialmedia""",
        'date': '2024-06-15',
        'likes': 45,
        'comments': 12,
        'shares': 8,
        'has_links': True,
        'has_cta': True
    },
    {
        'id': 'post_2', 
        'content': """What if I told you that 90% of marketers are doing content creation wrong?

Here's the secret: successful content isn't about being creative - it's about understanding your audience's pain points and addressing them directly.

Ready to transform your marketing approach? Download our free guide and see the difference.

#contentmarketing #strategy #business""",
        'date': '2024-06-10',
        'likes': 32,
        'comments': 8,
        'shares': 5,
        'has_links': True,
        'has_cta': True
    },
    {
        'id': 'post_3',
        'content': """The secret about Facebook ads that nobody talks about...

Most people focus on targeting and budgets. But the real game-changer? Your hook.

The first 3 seconds determine if someone stops scrolling or keeps going. Master your hooks, and everything else becomes easier.

Contact us to learn our proven hook formulas that generate 5x more engagement. Limited spots available this month.

#facebookads #marketing #hooks""",
        'date': '2024-06-05',
        'likes': 67,
        'comments': 18,
        'shares': 12,
        'has_links': False,
        'has_cta': True
    },
    {
        'id': 'post_4',
        'content': """Why thousands of businesses are switching to automated marketing...

Traditional marketing: 40 hours/week, inconsistent results, constant stress.
Automated marketing: 2 hours/week, predictable growth, peace of mind.

Which would you choose?

Book a free consultation and see how automation can transform your business. Don't wait - spots fill up fast!

#automation #marketing #productivity""",
        'date': '2024-06-01',
        'likes': 28,
        'comments': 6,
        'shares': 3,
        'has_links': True,
        'has_cta': True
    },
    {
        'id': 'post_5',
        'content': """Here's what you need to know about content that converts...

❌ Generic posts that sound like everyone else
❌ Posting without understanding your audience  
❌ Focusing on features instead of benefits

✅ Content that addresses specific pain points
✅ Clear, compelling calls-to-action
✅ Proven frameworks that drive engagement

Save time and get better results with our content templates. Get instant access below.

#content #marketing #conversion""",
        'date': '2024-05-28',
        'likes': 51,
        'comments': 14,
        'shares': 9,
        'has_links': True,
        'has_cta': True
    },
    {
        'id': 'post_6',
        'content': """Real results from our marketing automation clients:

Sarah (E-commerce): "Increased sales by 240% in 3 months"
Michael (SaaS): "Cut marketing time by 75%, doubled leads"  
Lisa (Consulting): "Went from 10 to 100 qualified leads per month"

Success stories like these happen when you stop doing marketing the hard way and start working smarter.

Ready to join them? Let's talk about your goals.

#success #automation #results""",
        'date': '2024-05-25',
        'likes': 73,
        'comments': 22,
        'shares': 15,
        'has_links': False,
        'has_cta': True
    },
    {
        'id': 'post_7',
        'content': """Did you know that 80% of your marketing results come from just 20% of your content?

The problem? Most businesses don't know which 20% is working.

Our analytics dashboard shows you exactly which posts drive engagement, which hooks get attention, and which CTAs convert best.

Stop guessing. Start knowing. Get access to our analytics suite today.

#analytics #marketing #data""",
        'date': '2024-05-20',
        'likes': 39,
        'comments': 11,
        'shares': 6,
        'has_links': True,
        'has_cta': True
    },
    {
        'id': 'post_8',
        'content': """The biggest marketing mistake I see entrepreneurs make?

Trying to be everywhere at once.

Instead of posting random content on 5 platforms, master ONE platform first. Create a system that works, then scale it.

Focus beats scattered effort every time.

Want help building your focused marketing system? Send me a message.

#focus #strategy #entrepreneurship""",
        'date': '2024-05-15',
        'likes': 44,
        'comments': 16,
        'shares': 7,
        'has_links': False,
        'has_cta': True
    },
    {
        'id': 'post_9',
        'content': """How to write hooks that stop the scroll:

1. Start with a question that creates curiosity
2. Share a surprising statistic or fact
3. Make a bold, controversial statement
4. Promise a specific benefit or outcome

The first line determines everything. Make it count.

Download our complete hook library with 100+ proven examples that you can use right away.

#copywriting #hooks #marketing""",
        'date': '2024-05-10',
        'likes': 85,
        'comments': 28,
        'shares': 18,
        'has_links': True,
        'has_cta': True
    },
    {
        'id': 'post_10',
        'content': """What would your business look like if marketing was effortless?

Imagine: Content that writes itself. Campaigns that optimize automatically. Leads that convert while you sleep.

This isn't fantasy - it's what happens when you implement the right marketing automation systems.

Ready to make marketing effortless? Let's build your automated system together.

#automation #marketing #business""",
        'date': '2024-05-05',
        'likes': 56,
        'comments': 19,
        'shares': 11,
        'has_links': False,
        'has_cta': True
    }
]

def create_sample_data():
    """Create sample data for testing"""
    
    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize database
    db = PostDatabase(config)
    
    # Store sample posts
    stored_count = db.store_posts(sample_posts)
    
    print(f"Created {stored_count} sample posts for testing")
    
    # Create raw backup file
    raw_posts_dir = config['directories']['raw_posts_dir']
    os.makedirs(raw_posts_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    raw_file = os.path.join(raw_posts_dir, f'sample_posts_{timestamp}.json')
    
    with open(raw_file, 'w', encoding='utf-8') as f:
        json.dump(sample_posts, f, indent=2, ensure_ascii=False)
    
    print(f"Sample data backup saved to {raw_file}")
    
    # Show stats
    stats = db.get_stats()
    print(f"\nDatabase Statistics:")
    print(f"Total posts: {stats['total_posts']}")
    print(f"Marketing posts: {stats['marketing_posts']}")
    print(f"Average engagement: {stats['avg_engagement']:.1f}")

if __name__ == '__main__':
    create_sample_data()