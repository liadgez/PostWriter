#!/usr/bin/env python3
"""
Content quality filter for PostWriter
Filters out UI elements and improves post content quality
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

@dataclass
class ContentQuality:
    """Content quality assessment"""
    score: float  # 0-10 quality score
    is_valid: bool  # Whether content meets minimum standards
    issues: List[str]  # List of quality issues
    content_type: str  # Type of content (marketing, personal, ui_element, etc.)

class ContentFilter:
    """Filters and validates scraped content quality"""
    
    def __init__(self):
        # UI elements to filter out
        self.ui_elements = {
            'like', 'comment', 'share', 'reply', 'react', 'author', 'sponsored', 'promoted',
            'see more', 'see less', 'show more', 'show less', 'view more', 'view less',
            'online status indicator', 'active', 'offline', 'just now', 'minutes ago',
            'hours ago', 'days ago', 'weeks ago', 'months ago', 'years ago',
            'follow', 'unfollow', 'friend request', 'message', 'poke', 'tag',
            'edit', 'delete', 'report', 'block', 'hide', 'save', 'unsave',
            # Hebrew UI elements
            'לייק', 'תגובה', 'שיתוף', 'מענה', 'פעיל', 'מקוון'
        }
        
        # Common Facebook interface text
        self.facebook_ui = {
            'what\'s on your mind', 'write something', 'add to your post',
            'feeling/activity', 'check in', 'live video', 'photo/video',
            'create room', 'sell something', 'support nonprofit', 'celebrate',
            'ask for recommendations', 'create poll', 'watch party'
        }
        
        # Marketing indicators (positive signals)
        self.marketing_indicators = {
            'click', 'buy', 'shop', 'order', 'purchase', 'get', 'download',
            'learn more', 'find out', 'discover', 'sign up', 'register',
            'contact', 'call', 'email', 'visit', 'book', 'schedule',
            'limited time', 'offer', 'deal', 'discount', 'sale', 'free',
            'exclusive', 'special', 'new', 'launch', 'announcement'
        }
        
        # Personal post indicators
        self.personal_indicators = {
            'feeling', 'excited', 'happy', 'sad', 'grateful', 'blessed',
            'family', 'friends', 'vacation', 'trip', 'birthday', 'anniversary',
            'thank you', 'congrats', 'congratulations', 'prayers', 'thoughts'
        }
        
        # Content that's too short to be meaningful
        self.min_content_length = 50  # Increased threshold
        self.min_words = 5  # Increased word count requirement
        
    def filter_ui_elements(self, text: str) -> str:
        """Remove UI elements from text"""
        if not text:
            return ""
        
        # Convert to lowercase for comparison
        text_lower = text.lower().strip()
        
        # Check if entire text is just UI elements
        words = text_lower.split()
        ui_word_count = sum(1 for word in words if any(ui in word for ui in self.ui_elements))
        
        if len(words) > 0 and ui_word_count / len(words) > 0.7:
            return ""  # Too much UI content
        
        # Remove lines that are primarily UI elements
        lines = text.split('\n')
        filtered_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            line_lower = line.lower()
            
            # Skip lines that are just UI elements
            if any(ui_element in line_lower for ui_element in self.ui_elements):
                continue
            
            # Skip lines that are just Facebook UI
            if any(ui_text in line_lower for ui_text in self.facebook_ui):
                continue
            
            # Skip very short lines (likely UI)
            if len(line) < 5:
                continue
            
            # Skip lines with only numbers and common words
            if re.match(r'^[\d\s\w]{1,10}$', line) and len(line) < 15:
                continue
            
            filtered_lines.append(line)
        
        return '\n'.join(filtered_lines).strip()
    
    def detect_content_type(self, text: str) -> str:
        """Detect the type of content"""
        if not text:
            return "empty"
        
        text_lower = text.lower()
        lines = text.split('\n')
        
        # Check for patterns that indicate UI elements
        name_patterns = ['author', 'liran galizyan', 'moshiko gorge', 'karina gorge', 'etgar shpivak']
        time_patterns = [r'\d+[wdhms]', 'minutes ago', 'hours ago', 'days ago', 'weeks ago']
        
        # Count UI-like patterns
        ui_pattern_count = 0
        for line in lines:
            line_lower = line.strip().lower()
            
            # Check for name patterns
            if any(name in line_lower for name in name_patterns):
                ui_pattern_count += 1
            
            # Check for time patterns
            if any(re.search(pattern, line_lower) for pattern in time_patterns):
                ui_pattern_count += 1
        
        # If more than half the lines are UI patterns, it's probably UI
        if len(lines) > 0 and ui_pattern_count / len(lines) > 0.4:
            return "ui_element"
        
        # Check for marketing content
        marketing_score = sum(1 for indicator in self.marketing_indicators 
                            if indicator in text_lower)
        
        # Check for personal content
        personal_score = sum(1 for indicator in self.personal_indicators 
                           if indicator in text_lower)
        
        # Check for UI elements
        ui_score = sum(1 for ui in self.ui_elements if ui in text_lower)
        
        # Determine content type
        if ui_score > marketing_score + personal_score:
            return "ui_element"
        elif marketing_score > personal_score:
            return "marketing"
        elif personal_score > 0:
            return "personal"
        elif len(text) > 100:
            return "informational"
        else:
            return "unknown"
    
    def calculate_quality_score(self, text: str) -> float:
        """Calculate content quality score (0-10)"""
        if not text:
            return 0.0
        
        score = 5.0  # Base score
        
        # Length bonus
        if len(text) > 50:
            score += 1.0
        if len(text) > 150:
            score += 1.0
        if len(text) > 300:
            score += 0.5
        
        # Word count bonus
        words = text.split()
        if len(words) > 10:
            score += 1.0
        if len(words) > 25:
            score += 0.5
        
        # Structure bonus
        if '\n' in text and len(text.split('\n')) > 1:
            score += 0.5
        
        # Marketing content bonus
        text_lower = text.lower()
        marketing_indicators_found = sum(1 for indicator in self.marketing_indicators 
                                       if indicator in text_lower)
        if marketing_indicators_found > 0:
            score += min(marketing_indicators_found * 0.5, 2.0)
        
        # Hashtag bonus
        if '#' in text:
            hashtag_count = text.count('#')
            score += min(hashtag_count * 0.2, 1.0)
        
        # URL bonus (indicates external content)
        if 'http' in text_lower or 'www.' in text_lower:
            score += 0.5
        
        # Penalties
        ui_indicators = sum(1 for ui in self.ui_elements if ui in text_lower)
        if ui_indicators > 0:
            score -= min(ui_indicators * 0.5, 3.0)
        
        # Very short content penalty
        if len(text) < self.min_content_length:
            score -= 2.0
        
        # Too few words penalty
        if len(words) < self.min_words:
            score -= 2.0
        
        return max(0.0, min(10.0, score))
    
    def assess_content_quality(self, text: str) -> ContentQuality:
        """Comprehensive content quality assessment"""
        issues = []
        
        # Filter UI elements first
        filtered_text = self.filter_ui_elements(text)
        
        if not filtered_text:
            return ContentQuality(
                score=0.0,
                is_valid=False,
                issues=["Content is empty after filtering UI elements"],
                content_type="ui_element"
            )
        
        # Detect content type
        content_type = self.detect_content_type(filtered_text)
        
        # Calculate quality score
        quality_score = self.calculate_quality_score(filtered_text)
        
        # Check for issues
        if len(filtered_text) < self.min_content_length:
            issues.append(f"Content too short ({len(filtered_text)} chars, min {self.min_content_length})")
        
        words = filtered_text.split()
        if len(words) < self.min_words:
            issues.append(f"Too few words ({len(words)}, min {self.min_words})")
        
        if content_type == "ui_element":
            issues.append("Content appears to be UI elements")
        
        if quality_score < 3.0:
            issues.append("Low quality score")
        
        # Determine if content is valid
        is_valid = (
            len(issues) == 0 and 
            quality_score >= 3.0 and 
            content_type not in ["ui_element", "empty"]
        )
        
        return ContentQuality(
            score=quality_score,
            is_valid=is_valid,
            issues=issues,
            content_type=content_type
        )
    
    def filter_post_list(self, posts: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Filter a list of posts, returning (good_posts, filtered_out_posts)"""
        good_posts = []
        filtered_posts = []
        
        for post in posts:
            content = post.get('content', '') or post.get('text', '')
            
            # Assess quality
            quality = self.assess_content_quality(content)
            
            if quality.is_valid:
                # Update post with filtered content
                filtered_content = self.filter_ui_elements(content)
                post_copy = post.copy()
                post_copy['content'] = filtered_content
                post_copy['quality_score'] = quality.score
                post_copy['content_type'] = quality.content_type
                good_posts.append(post_copy)
            else:
                # Keep track of why it was filtered
                post_copy = post.copy()
                post_copy['filter_reason'] = quality.issues
                post_copy['quality_score'] = quality.score
                filtered_posts.append(post_copy)
        
        return good_posts, filtered_posts
    
    def get_filter_stats(self, original_posts: List[Dict], 
                        good_posts: List[Dict], 
                        filtered_posts: List[Dict]) -> Dict:
        """Get filtering statistics"""
        total = len(original_posts)
        good = len(good_posts)
        filtered = len(filtered_posts)
        
        # Calculate content type distribution
        content_types = {}
        for post in good_posts:
            content_type = post.get('content_type', 'unknown')
            content_types[content_type] = content_types.get(content_type, 0) + 1
        
        # Calculate average quality score
        if good_posts:
            avg_quality = sum(post.get('quality_score', 0) for post in good_posts) / len(good_posts)
        else:
            avg_quality = 0.0
        
        return {
            'total_posts': total,
            'good_posts': good,
            'filtered_posts': filtered,
            'filter_rate': (filtered / total * 100) if total > 0 else 0,
            'content_types': content_types,
            'average_quality': avg_quality
        }

# Example usage and testing
if __name__ == '__main__':
    filter = ContentFilter()
    
    # Test with sample posts from the project
    test_posts = [
        {
            'id': 1,
            'content': "Are you struggling with your social media marketing strategy? Most businesses waste hours creating content that gets zero engagement. Our AI-powered marketing tools help you create content that actually converts. Click the link to get started today! #marketing #AI"
        },
        {
            'id': 2,
            'content': "Author\nLiran Galizyan\n5w\nLike\nReply"
        },
        {
            'id': 3,
            'content': "Online status indicator\nActive\nMoshiko Gorge\n5w\nLike\nReply"
        },
        {
            'id': 4,
            'content': "What if I told you that 90% of marketers are doing content creation wrong? Here's the secret: successful content isn't about being creative - it's about understanding your audience's pain points. Ready to transform your marketing approach? #contentmarketing"
        }
    ]
    
    print("🔍 Testing Content Filter...")
    good_posts, filtered_posts = filter.filter_post_list(test_posts)
    stats = filter.get_filter_stats(test_posts, good_posts, filtered_posts)
    
    print(f"\n📊 Filter Results:")
    print(f"Total posts: {stats['total_posts']}")
    print(f"Good posts: {stats['good_posts']}")
    print(f"Filtered posts: {stats['filtered_posts']}")
    print(f"Filter rate: {stats['filter_rate']:.1f}%")
    print(f"Average quality: {stats['average_quality']:.2f}")
    print(f"Content types: {stats['content_types']}")
    
    print(f"\n✅ Good Posts:")
    for post in good_posts:
        print(f"  • Post {post['id']}: {post['content'][:60]}... (score: {post['quality_score']:.1f})")
    
    print(f"\n❌ Filtered Posts:")
    for post in filtered_posts:
        print(f"  • Post {post['id']}: {post.get('filter_reason', [])} (score: {post['quality_score']:.1f})")