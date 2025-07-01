#!/usr/bin/env python3
"""
Post analyzer for PostWriter
Analyzes posts for hooks, patterns, topics, and templates
"""

import re
import json
from collections import Counter, defaultdict
from typing import List, Dict, Tuple
from database import PostDatabase

class PostAnalyzer:
    def __init__(self, config):
        self.config = config
        self.db = PostDatabase(config)
        
        # Hook patterns (simple regex approach)
        self.hook_patterns = {
            'question': [
                r'\?',
                r'^(what|how|why|when|where|who|which|did you know)',
                r'(have you|do you|are you|can you|will you)'
            ],
            'urgency': [
                r'(now|today|limited|hurry|quick|fast|urgent)',
                r'(don\'t wait|act now|expires|deadline)',
                r'(last chance|final|ending soon)'
            ],
            'curiosity': [
                r'(secret|revealed|discover|find out|learn)',
                r'(amazing|shocking|surprising|incredible)',
                r'(you won\'t believe|guess what|here\'s why)'
            ],
            'social_proof': [
                r'(everyone|thousands|millions|people)',
                r'(customers love|clients say|reviews)',
                r'(testimonial|success story|case study)'
            ],
            'fear_missing_out': [
                r'(exclusive|limited|only|special)',
                r'(before it\'s gone|while supplies last)',
                r'(members only|vip|premium)'
            ],
            'benefit': [
                r'(save|earn|get|gain|achieve|improve)',
                r'(free|bonus|discount|deal)',
                r'(results|success|solution|help)'
            ]
        }
        
        # CTA patterns
        self.cta_patterns = {
            'click': [r'(click|tap|press|hit)'],
            'buy': [r'(buy|purchase|order|shop|get yours)'],
            'learn': [r'(learn more|find out|discover|read more)'],
            'signup': [r'(sign up|register|join|subscribe)'],
            'contact': [r'(contact|call|email|message|reach out)'],
            'download': [r'(download|get|grab|access)'],
            'book': [r'(book|schedule|reserve|appointment)']
        }
    
    def detect_hooks(self, text: str) -> List[str]:
        """Detect hook types in text"""
        text_lower = text.lower()
        detected_hooks = []
        
        for hook_type, patterns in self.hook_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    detected_hooks.append(hook_type)
                    break
        
        return detected_hooks
    
    def detect_cta_type(self, text: str) -> str:
        """Detect CTA type in text"""
        text_lower = text.lower()
        
        for cta_type, patterns in self.cta_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    return cta_type
        
        return 'general'
    
    def extract_structure(self, text: str) -> str:
        """Extract post structure pattern"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not lines:
            return "EMPTY"
        
        structure_parts = []
        
        # Analyze first line (usually the hook)
        first_line = lines[0]
        if '?' in first_line:
            structure_parts.append("QUESTION_HOOK")
        elif any(word in first_line.lower() for word in ['imagine', 'what if', 'picture this']):
            structure_parts.append("SCENARIO_HOOK")
        elif len(first_line) < 50 and ('!' in first_line or first_line.isupper()):
            structure_parts.append("ATTENTION_HOOK")
        else:
            structure_parts.append("STATEMENT_HOOK")
        
        # Analyze body
        if len(lines) > 2:
            structure_parts.append("BODY")
        
        # Check for CTA (usually in last few lines)
        last_lines = ' '.join(lines[-2:]).lower()
        if any(cta in last_lines for cta in ['click', 'buy', 'learn more', 'contact', 'sign up']):
            structure_parts.append("CTA")
        
        # Check for hashtags
        if any('#' in line for line in lines):
            structure_parts.append("HASHTAGS")
        
        return " + ".join(structure_parts)
    
    def calculate_engagement_score(self, post: Dict) -> float:
        """Calculate normalized engagement score"""
        likes = post.get('likes', 0)
        comments = post.get('comments', 0) * 2  # Weight comments more
        shares = post.get('shares', 0) * 3      # Weight shares most
        
        total_engagement = likes + comments + shares
        
        # Simple normalization (could be improved with follower count)
        return min(total_engagement / 10.0, 10.0)  # Scale 0-10
    
    def analyze_topics(self) -> List[Dict]:
        """Analyze and return top topics from posts"""
        posts = self.db.get_posts(marketing_only=True)
        
        # Simple topic extraction using keyword frequency
        word_counts = Counter()
        topic_posts = defaultdict(list)
        
        for post in posts:
            content = post['content'].lower()
            
            # Extract meaningful words (excluding common words)
            stop_words = {
                'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
                'a', 'an', 'is', 'was', 'are', 'were', 'be', 'been', 'being',
                'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
            }
            
            words = re.findall(r'\b[a-zA-Z]{3,}\b', content)
            meaningful_words = [word for word in words if word not in stop_words]
            
            # Count word frequency
            for word in meaningful_words:
                word_counts[word] += 1
                topic_posts[word].append(post)
        
        # Get top topics
        top_words = word_counts.most_common(10)
        topics = []
        
        for word, count in top_words:
            if count >= 2:  # Minimum threshold
                avg_engagement = sum(self.calculate_engagement_score(p) for p in topic_posts[word]) / len(topic_posts[word])
                topics.append({
                    'name': word.title(),
                    'count': count,
                    'avg_engagement': round(avg_engagement, 2)
                })
        
        return topics
    
    def analyze_and_store_templates(self) -> int:
        """Analyze posts and store templates in database"""
        posts = self.db.get_posts(min_engagement=self.config['analysis']['min_engagement'])
        
        if not posts:
            return 0
        
        # Group posts by structure
        structure_groups = defaultdict(list)
        
        for post in posts:
            structure = self.extract_structure(post['content'])
            hooks = self.detect_hooks(post['content'])
            cta_type = self.detect_cta_type(post['content'])
            engagement_score = self.calculate_engagement_score(post)
            
            structure_groups[structure].append({
                'post': post,
                'hooks': hooks,
                'cta_type': cta_type,
                'engagement_score': engagement_score
            })
        
        # Create templates from groups with multiple posts
        templates_created = 0
        
        for structure, group_posts in structure_groups.items():
            if len(group_posts) >= 2:  # Minimum 2 posts to form a template
                # Calculate template metrics
                avg_engagement = sum(p['engagement_score'] for p in group_posts) / len(group_posts)
                most_common_hook = Counter([h for p in group_posts for h in p['hooks']]).most_common(1)
                hook_type = most_common_hook[0][0] if most_common_hook else 'general'
                most_common_cta = Counter([p['cta_type'] for p in group_posts]).most_common(1)[0][0]
                
                # Determine topic from most frequent words
                all_content = ' '.join([p['post']['content'] for p in group_posts])
                words = re.findall(r'\b[a-zA-Z]{4,}\b', all_content.lower())
                topic = Counter(words).most_common(1)[0][0] if words else 'general'
                
                # Create template
                template = {
                    'topic': topic,
                    'structure': structure,
                    'success_score': avg_engagement,
                    'hook_type': hook_type,
                    'cta_type': most_common_cta,
                    'avg_engagement': avg_engagement,
                    'post_count': len(group_posts)
                }
                
                template_id = self.db.store_template(template)
                templates_created += 1
                
                print(f"Created template {template_id}: {structure} (score: {avg_engagement:.2f})")
        
        return templates_created
    
    def generate_ideas(self, topic: str) -> List[str]:
        """Generate content ideas based on topic and successful patterns"""
        # Get successful templates
        templates = self.db.get_templates(limit=5)
        
        if not templates:
            return [f"Create content about {topic}"]
        
        ideas = []
        
        # Generate ideas based on successful hook types
        hook_starters = {
            'question': [
                f"What if {topic} could change your life?",
                f"Why are more people choosing {topic}?",
                f"How does {topic} really work?"
            ],
            'curiosity': [
                f"The secret about {topic} nobody talks about",
                f"Discover what makes {topic} so effective",
                f"Here's what you need to know about {topic}"
            ],
            'social_proof': [
                f"Why thousands are switching to {topic}",
                f"Real results from {topic} users",
                f"Success stories with {topic}"
            ],
            'benefit': [
                f"Save time and money with {topic}",
                f"Get better results using {topic}",
                f"Improve your life with {topic}"
            ],
            'urgency': [
                f"Limited time offer for {topic}",
                f"Don't miss out on {topic}",
                f"Act now: {topic} opportunity"
            ]
        }
        
        # Select ideas based on successful hook types
        for template in templates:
            hook_type = template.get('hook_type', 'benefit')
            if hook_type in hook_starters:
                ideas.extend(hook_starters[hook_type][:1])  # One idea per template
        
        return ideas[:5]  # Return top 5 ideas
    
    def get_analytics_summary(self) -> Dict:
        """Get analytics summary of all posts"""
        posts = self.db.get_posts()
        
        if not posts:
            return {"error": "No posts found"}
        
        # Basic statistics
        total_posts = len(posts)
        marketing_posts = len([p for p in posts if p.get('has_cta') or p.get('has_link')])
        avg_engagement = sum(self.calculate_engagement_score(p) for p in posts) / total_posts
        
        # Hook analysis
        all_hooks = []
        for post in posts:
            all_hooks.extend(self.detect_hooks(post['content']))
        
        hook_distribution = Counter(all_hooks)
        
        # CTA analysis
        cta_types = [self.detect_cta_type(p['content']) for p in posts]
        cta_distribution = Counter(cta_types)
        
        # Structure analysis
        structures = [self.extract_structure(p['content']) for p in posts]
        structure_distribution = Counter(structures)
        
        return {
            'total_posts': total_posts,
            'marketing_posts': marketing_posts,
            'avg_engagement': round(avg_engagement, 2),
            'top_hooks': dict(hook_distribution.most_common(5)),
            'cta_distribution': dict(cta_distribution.most_common(5)),
            'top_structures': dict(structure_distribution.most_common(3))
        }

# Example usage
if __name__ == '__main__':
    # Test configuration
    config = {
        'database': {'path': './data/test.db'},
        'analysis': {'min_engagement': 5},
        'directories': {'data_dir': './data'}
    }
    
    analyzer = PostAnalyzer(config)
    
    # Test with sample post
    sample_post = {
        'content': "Are you tired of spending hours on social media marketing? Our new tool can help you save time and get better results. Click the link to learn more! #marketing #socialmedia",
        'likes': 15,
        'comments': 3,
        'shares': 2
    }
    
    hooks = analyzer.detect_hooks(sample_post['content'])
    cta = analyzer.detect_cta_type(sample_post['content'])
    structure = analyzer.extract_structure(sample_post['content'])
    
    print(f"Hooks detected: {hooks}")
    print(f"CTA type: {cta}")
    print(f"Structure: {structure}")
    print(f"Engagement score: {analyzer.calculate_engagement_score(sample_post)}")