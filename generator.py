#!/usr/bin/env python3
"""
Content generator for PostWriter
Generates marketing content based on templates and ideas
"""

import random
import re
from typing import List, Dict, Tuple
from database import PostDatabase
from analyzer import PostAnalyzer

class ContentGenerator:
    def __init__(self, config):
        self.config = config
        self.db = PostDatabase(config)
        self.analyzer = PostAnalyzer(config)
        
        # Template placeholders and variations
        self.placeholder_variations = {
            'HOOK': [
                "Did you know that {topic}",
                "What if I told you that {topic}",
                "Here's something amazing about {topic}",
                "The secret about {topic}",
                "Why {topic} is changing everything"
            ],
            'BENEFIT': [
                "can save you time and money",
                "will improve your results dramatically",
                "makes everything easier",
                "gives you the edge you need",
                "transforms your approach completely"
            ],
            'CTA': [
                "Click the link to learn more!",
                "Get started today - limited time offer!",
                "Don't miss out - contact us now!",
                "Take action and see the difference!",
                "Ready to transform? Let's talk!"
            ],
            'SOCIAL_PROOF': [
                "Join thousands of satisfied customers",
                "See why experts recommend this",
                "Trusted by industry leaders",
                "Proven results for our clients",
                "Success stories speak for themselves"
            ]
        }
        
        # Hook variations by type
        self.hook_templates = {
            'question': [
                "Are you struggling with {topic}?",
                "What if {topic} could be easier?",
                "Did you know {topic} can change your life?",
                "Why do most people fail at {topic}?",
                "How would your life change with better {topic}?"
            ],
            'curiosity': [
                "The secret about {topic} nobody talks about",
                "Here's what you need to know about {topic}",
                "Discover the truth about {topic}",
                "What they don't tell you about {topic}",
                "The surprising reality of {topic}"
            ],
            'social_proof': [
                "Why thousands are choosing {topic}",
                "See what our customers say about {topic}",
                "Real results from {topic} users",
                "Join the {topic} success stories",
                "Trusted by experts in {topic}"
            ],
            'urgency': [
                "Limited time: {topic} opportunity",
                "Don't miss out on {topic}",
                "Last chance for {topic}",
                "Act now: {topic} special offer",
                "Hurry - {topic} ends soon"
            ],
            'benefit': [
                "Transform your {topic} today",
                "Get better {topic} results",
                "Improve your {topic} instantly",
                "Achieve {topic} success",
                "Master {topic} once and for all"
            ]
        }
        
        # CTA variations by type
        self.cta_templates = {
            'click': [
                "Click here to learn more!",
                "Tap the link for details!",
                "Click to get started today!"
            ],
            'buy': [
                "Order now and save!",
                "Get yours today!",
                "Buy now - limited stock!"
            ],
            'learn': [
                "Learn more about this solution",
                "Discover how it works",
                "Find out the details"
            ],
            'signup': [
                "Sign up for free access",
                "Join our community today",
                "Register now for updates"
            ],
            'contact': [
                "Contact us for a consultation",
                "Reach out to learn more",
                "Get in touch today"
            ]
        }
    
    def find_best_template(self, idea: str) -> Dict:
        """Find the best template match for an idea"""
        templates = self.db.get_templates(limit=10)
        
        if not templates:
            # Return a default template if none exist
            return {
                'id': 0,
                'structure': 'QUESTION_HOOK + BODY + CTA',
                'hook_type': 'question',
                'cta_type': 'learn',
                'success_score': 5.0,
                'topic': 'general'
            }
        
        # Simple matching: find template with highest success score
        # In a more sophisticated version, this would use semantic similarity
        best_template = max(templates, key=lambda t: t.get('success_score', 0))
        
        return best_template
    
    def generate_hook(self, hook_type: str, topic: str) -> str:
        """Generate a hook based on type and topic"""
        if hook_type in self.hook_templates:
            template = random.choice(self.hook_templates[hook_type])
            return template.format(topic=topic)
        else:
            # Default hook
            return f"Discover the power of {topic}"
    
    def generate_body(self, topic: str, hook_type: str) -> str:
        """Generate body content"""
        body_templates = {
            'question': [
                f"Many people struggle with {topic}, but there's a better way. Our solution addresses the core challenges and delivers real results.",
                f"If you're like most people, {topic} has been a challenge. We've developed an approach that changes everything.",
                f"The problem with traditional {topic} methods is they're outdated. Here's what actually works today."
            ],
            'curiosity': [
                f"What we discovered about {topic} will surprise you. The conventional wisdom is wrong, and we can prove it.",
                f"After studying {topic} for years, we found something remarkable. This changes everything we thought we knew.",
                f"The real truth about {topic} is simpler than you think. Once you understand this, success becomes inevitable."
            ],
            'social_proof': [
                f"Our {topic} solution has helped thousands of clients achieve their goals. The results speak for themselves.",
                f"Industry leaders trust our approach to {topic}. Here's why it works when others fail.",
                f"Real customers, real results. See how our {topic} solution transforms businesses every day."
            ],
            'benefit': [
                f"Imagine if {topic} could be effortless. With our approach, it is. Save time, reduce stress, get better results.",
                f"Transform your {topic} experience completely. More efficiency, better outcomes, less hassle.",
                f"Stop struggling with {topic}. Our solution makes it simple, effective, and profitable."
            ],
            'urgency': [
                f"This {topic} opportunity won't last forever. Smart businesses are already taking advantage.",
                f"While others hesitate, you can get ahead with {topic}. The window is closing fast.",
                f"Don't let another day pass without addressing your {topic} challenges. Act now."
            ]
        }
        
        if hook_type in body_templates:
            return random.choice(body_templates[hook_type])
        else:
            return f"Our {topic} solution delivers exceptional results through proven methods and expert guidance."
    
    def generate_cta(self, cta_type: str) -> str:
        """Generate call-to-action based on type"""
        if cta_type in self.cta_templates:
            return random.choice(self.cta_templates[cta_type])
        else:
            return "Contact us to learn more!"
    
    def validate_content(self, content: str) -> Tuple[bool, List[str]]:
        """Validate generated content against platform requirements"""
        issues = []
        
        # Check length
        max_length = self.config['generation']['max_length']
        if len(content) > max_length:
            issues.append(f"Content too long: {len(content)} chars (max {max_length})")
        
        # Check first line engagement
        first_line = content.split('\n')[0]
        if len(first_line) > 125:
            issues.append("First line too long for Facebook preview")
        
        # Check for excessive emojis
        emoji_count = len(re.findall(r'[^\w\s,.]', content))
        if emoji_count > 10:
            issues.append(f"Too many special characters/emojis: {emoji_count}")
        
        # Check for CTA presence
        cta_indicators = ['click', 'buy', 'learn more', 'contact', 'sign up', 'get', 'download']
        has_cta = any(indicator in content.lower() for indicator in cta_indicators)
        if not has_cta:
            issues.append("No clear call-to-action found")
        
        return len(issues) == 0, issues
    
    def create_variation(self, base_content: str, variation_type: str = 'hook') -> str:
        """Create a variation of existing content"""
        lines = base_content.split('\n')
        
        if variation_type == 'hook' and lines:
            # Replace first line (hook)
            original_hook = lines[0]
            # Extract topic from original hook
            words = re.findall(r'\b[a-zA-Z]{4,}\b', original_hook.lower())
            topic = words[0] if words else 'success'
            
            # Generate new hook
            hook_types = ['question', 'curiosity', 'benefit']
            new_hook_type = random.choice(hook_types)
            new_hook = self.generate_hook(new_hook_type, topic)
            
            lines[0] = new_hook
            return '\n'.join(lines)
        
        elif variation_type == 'cta' and lines:
            # Replace last line (CTA)
            cta_types = ['click', 'learn', 'contact']
            new_cta_type = random.choice(cta_types)
            new_cta = self.generate_cta(new_cta_type)
            
            lines[-1] = new_cta
            return '\n'.join(lines)
        
        return base_content
    
    def generate_content(self, idea: str, num_variations: int = 3) -> List[Dict]:
        """Generate content variations based on idea"""
        # Extract topic from idea
        words = re.findall(r'\b[a-zA-Z]{3,}\b', idea.lower())
        topic = ' '.join(words[:2]) if len(words) >= 2 else words[0] if words else idea
        
        # Find best template
        template = self.find_best_template(idea)
        
        # Generate base content
        hook = self.generate_hook(template['hook_type'], topic)
        body = self.generate_body(topic, template['hook_type'])
        cta = self.generate_cta(template['cta_type'])
        
        base_content = f"{hook}\n\n{body}\n\n{cta}"
        
        # Validate base content
        is_valid, issues = self.validate_content(base_content)
        
        variations = []
        
        # Add base version
        variations.append({
            'text': base_content,
            'template_id': template['id'],
            'hook_type': template['hook_type'],
            'cta_type': template['cta_type'],
            'score': template['success_score'],
            'variation_type': 'original',
            'is_valid': is_valid,
            'issues': issues
        })
        
        # Generate variations
        for i in range(1, num_variations):
            if i % 2 == 1:
                # Hook variation
                varied_content = self.create_variation(base_content, 'hook')
                variation_type = 'hook_variation'
            else:
                # CTA variation
                varied_content = self.create_variation(base_content, 'cta')
                variation_type = 'cta_variation'
            
            is_valid, issues = self.validate_content(varied_content)
            
            variations.append({
                'text': varied_content,
                'template_id': template['id'],
                'hook_type': template['hook_type'],
                'cta_type': template['cta_type'],
                'score': template['success_score'],
                'variation_type': variation_type,
                'is_valid': is_valid,
                'issues': issues
            })
        
        # Store generated content in database
        for i, variation in enumerate(variations):
            self.db.store_generated_content(
                idea=idea,
                template_id=template['id'],
                content=variation['text'],
                variation=i + 1
            )
        
        return variations
    
    def improve_content(self, content: str) -> str:
        """Improve existing content based on best practices"""
        lines = content.split('\n')
        improved_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                improved_lines.append('')
                continue
            
            # First line improvements (hook)
            if i == 0:
                # Add question mark if it seems like a question
                if any(word in line.lower() for word in ['what', 'how', 'why', 'are you', 'do you']):
                    if not line.endswith('?'):
                        line += '?'
                
                # Ensure first line is engaging
                if len(line) < 20:
                    line = "🔥 " + line
            
            # Last line improvements (CTA)
            elif i == len(lines) - 1:
                # Ensure CTA has action word
                action_words = ['click', 'contact', 'learn', 'get', 'buy', 'join']
                if not any(word in line.lower() for word in action_words):
                    line += " Contact us to learn more!"
                
                # Add urgency if missing
                if 'now' not in line.lower() and 'today' not in line.lower():
                    line += " Don't wait!"
            
            improved_lines.append(line)
        
        return '\n'.join(improved_lines)

# Example usage
if __name__ == '__main__':
    # Test configuration
    config = {
        'database': {'path': './data/test.db'},
        'generation': {'max_length': 2000, 'default_variations': 3},
        'directories': {'data_dir': './data'}
    }
    
    generator = ContentGenerator(config)
    
    # Test content generation
    idea = "AI-powered marketing automation tool"
    variations = generator.generate_content(idea, 2)
    
    print(f"Generated {len(variations)} variations for: {idea}")
    for i, variation in enumerate(variations):
        print(f"\n--- Variation {i+1} ({variation['variation_type']}) ---")
        print(variation['text'])
        print(f"Valid: {variation['is_valid']}")
        if variation['issues']:
            print(f"Issues: {', '.join(variation['issues'])}")
        print(f"Template score: {variation['score']}")
        print("-" * 50)