#!/usr/bin/env python3
"""
Database operations for PostWriter
Handles SQLite storage for posts and templates
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional

# Import custom exceptions
from ..utils.exceptions import DatabaseError, ValidationError

class PostDatabase:
    def __init__(self, config):
        self.db_path = config['database']['path']
        self.config = config
        self._init_database()
    
    def _init_database(self):
        """Initialize database with required tables"""
        try:
            # Ensure database directory exists
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        except OSError as e:
            raise DatabaseError(f"Failed to create database directory: {e}")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id TEXT UNIQUE,
                    content TEXT NOT NULL,
                    date_posted TEXT,
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    engagement_score REAL DEFAULT 0,
                    has_cta BOOLEAN DEFAULT 0,
                    has_link BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    raw_data TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT,
                    structure TEXT NOT NULL,
                    success_score REAL DEFAULT 0,
                    hook_type TEXT,
                    cta_type TEXT,
                    avg_engagement REAL DEFAULT 0,
                    post_count INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS generated_content (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    idea TEXT NOT NULL,
                    template_id INTEGER,
                    content TEXT NOT NULL,
                    variation_number INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (template_id) REFERENCES templates (id)
                )
            ''')
            
            conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to initialize database: {e}")
    
    def store_posts(self, posts: List[Dict]) -> int:
        """Store scraped posts in database"""
        if not posts:
            raise ValidationError("No posts provided to store")
        
        stored_count = 0
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                for post in posts:
                    try:
                        # Calculate engagement score
                        engagement = post.get('likes', 0) + post.get('comments', 0) + post.get('shares', 0)
                    
                        # Detect CTA and links
                        content = post.get('content', '').lower()
                        has_cta = any(cta in content for cta in [
                            'click', 'buy now', 'learn more', 'sign up', 'download',
                            'get started', 'contact us', 'book now', 'order now'
                        ])
                        has_link = 'http' in content or 'www.' in content
                        
                        conn.execute('''
                            INSERT OR REPLACE INTO posts 
                            (post_id, content, date_posted, likes, comments, shares, 
                             engagement_score, has_cta, has_link, raw_data)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            post.get('id', ''),
                            post.get('content', ''),
                            post.get('date', ''),
                            post.get('likes', 0),
                            post.get('comments', 0),
                            post.get('shares', 0),
                            engagement,
                            has_cta,
                            has_link,
                            json.dumps(post)
                        ))
                        stored_count += 1
                        
                    except Exception as e:
                        print(f"Error storing post: {e}")
                        continue
            
                conn.commit()
        except sqlite3.Error as e:
            raise DatabaseError(f"Failed to store posts: {e}")
        
        return stored_count
    
    def get_posts(self, min_engagement: int = 0, marketing_only: bool = False) -> List[Dict]:
        """Retrieve posts from database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = '''
                SELECT * FROM posts 
                WHERE engagement_score >= ?
            '''
            params = [min_engagement]
            
            if marketing_only:
                query += ' AND (has_cta = 1 OR has_link = 1)'
            
            query += ' ORDER BY engagement_score DESC'
            
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def store_template(self, template: Dict) -> int:
        """Store a template in database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO templates 
                (topic, structure, success_score, hook_type, cta_type, avg_engagement, post_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                template.get('topic', ''),
                template.get('structure', ''),
                template.get('success_score', 0),
                template.get('hook_type', ''),
                template.get('cta_type', ''),
                template.get('avg_engagement', 0),
                template.get('post_count', 1)
            ))
            conn.commit()
            return cursor.lastrowid
    
    def get_templates(self, limit: int = 10) -> List[Dict]:
        """Get templates ordered by success score"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM templates 
                ORDER BY success_score DESC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_template(self, template_id: int) -> Optional[Dict]:
        """Get specific template by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM templates WHERE id = ?
            ''', (template_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_template_score(self, template_id: int, new_score: float):
        """Update template success score"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE templates 
                SET success_score = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_score, template_id))
            conn.commit()
    
    def store_generated_content(self, idea: str, template_id: int, content: str, variation: int = 1):
        """Store generated content for tracking"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO generated_content 
                (idea, template_id, content, variation_number)
                VALUES (?, ?, ?, ?)
            ''', (idea, template_id, content, variation))
            conn.commit()
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}
            
            # Post count
            cursor = conn.execute('SELECT COUNT(*) FROM posts')
            stats['total_posts'] = cursor.fetchone()[0]
            
            # Marketing posts
            cursor = conn.execute('SELECT COUNT(*) FROM posts WHERE has_cta = 1 OR has_link = 1')
            stats['marketing_posts'] = cursor.fetchone()[0]
            
            # Template count
            cursor = conn.execute('SELECT COUNT(*) FROM templates')
            stats['templates'] = cursor.fetchone()[0]
            
            # Average engagement
            cursor = conn.execute('SELECT AVG(engagement_score) FROM posts')
            result = cursor.fetchone()[0]
            stats['avg_engagement'] = result if result else 0
            
            # Generated content count
            cursor = conn.execute('SELECT COUNT(*) FROM generated_content')
            stats['generated_content'] = cursor.fetchone()[0]
            
            return stats
    
    def cleanup_old_data(self, days: int = 90):
        """Remove old generated content and update timestamps"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                DELETE FROM generated_content 
                WHERE created_at < datetime('now', '-{} days')
            '''.format(days))
            conn.commit()


# Example usage and testing
if __name__ == '__main__':
    # Simple test
    config = {
        'database': {'path': './data/test.db'},
        'directories': {'data_dir': './data'}
    }
    
    db = PostDatabase(config)
    
    # Test storing a post
    test_post = {
        'id': 'test_123',
        'content': 'Check out our new product! Click here to learn more.',
        'date': '2024-01-01',
        'likes': 10,
        'comments': 5,
        'shares': 2
    }
    
    db.store_posts([test_post])
    
    # Test retrieving posts
    posts = db.get_posts()
    print(f"Stored {len(posts)} posts")
    
    # Show stats
    stats = db.get_stats()
    print("Database stats:", stats)