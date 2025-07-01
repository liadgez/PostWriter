#!/usr/bin/env python3
"""
PostWriter - Facebook Ads CLI Tool
A simple CLI tool for analyzing Facebook posts and generating marketing content.
"""

import argparse
import sys
import yaml
import os
from datetime import datetime

def load_config():
    """Load configuration from config.yaml"""
    try:
        with open('config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("Error: config.yaml not found. Please create it first.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing config.yaml: {e}")
        sys.exit(1)

def setup_directories(config):
    """Ensure data directories exist"""
    dirs = [
        config['directories']['data_dir'],
        config['directories']['raw_posts_dir'],
        config['directories']['logs_dir']
    ]
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)

def log_action(message, config):
    """Simple logging function"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    
    # Also log to file
    log_file = os.path.join(config['directories']['logs_dir'], 'postwriter.log')
    with open(log_file, 'a') as f:
        f.write(log_message + '\n')

def cmd_sync(args, config):
    """Sync posts from Facebook profile"""
    log_action("Starting Facebook post sync...", config)
    
    if not config['facebook']['profile_url']:
        print("Error: Please set your Facebook profile URL in config.yaml")
        return
    
    try:
        from scraper import FacebookScraper
        scraper = FacebookScraper(config)
        posts = scraper.scrape_posts()
        log_action(f"Successfully scraped {len(posts)} posts", config)
        
        # Store posts in database
        from database import PostDatabase
        db = PostDatabase(config)
        db.store_posts(posts)
        log_action(f"Stored {len(posts)} posts in database", config)
        
    except ImportError as e:
        print(f"Error: Missing dependencies. Please install: {e}")
    except Exception as e:
        print(f"Error during sync: {e}")
        log_action(f"Sync failed: {e}", config)

def cmd_topics(args, config):
    """Show leading topics from posts"""
    log_action("Analyzing topics...", config)
    
    try:
        from analyzer import PostAnalyzer
        analyzer = PostAnalyzer(config)
        topics = analyzer.analyze_topics()
        
        print("\n=== Top Topics ===")
        for i, topic in enumerate(topics, 1):
            print(f"{i}. {topic['name']} ({topic['count']} posts)")
            
    except Exception as e:
        print(f"Error analyzing topics: {e}")

def cmd_templates(args, config):
    """List available templates"""
    log_action("Loading templates...", config)
    
    try:
        from database import PostDatabase
        db = PostDatabase(config)
        templates = db.get_templates()
        
        if args.subcommand == 'list':
            print("\n=== Available Templates ===")
            for template in templates:
                print(f"ID: {template['id']} | Score: {template['success_score']:.2f}")
                print(f"Structure: {template['structure'][:100]}...")
                print("-" * 50)
                
        elif args.subcommand == 'show' and args.template_id:
            template = db.get_template(args.template_id)
            if template:
                print(f"\n=== Template {args.template_id} ===")
                print(f"Success Score: {template['success_score']}")
                print(f"Topic: {template['topic']}")
                print(f"Structure:\n{template['structure']}")
            else:
                print(f"Template {args.template_id} not found")
                
    except Exception as e:
        print(f"Error loading templates: {e}")

def cmd_idea(args, config):
    """Generate content ideas"""
    idea_text = args.idea
    log_action(f"Generating ideas for: {idea_text}", config)
    
    try:
        from analyzer import PostAnalyzer
        analyzer = PostAnalyzer(config)
        ideas = analyzer.generate_ideas(idea_text)
        
        print(f"\n=== Ideas for '{idea_text}' ===")
        for i, idea in enumerate(ideas, 1):
            print(f"{i}. {idea}")
            
    except Exception as e:
        print(f"Error generating ideas: {e}")

def cmd_chrome(args, config):
    """Connect to existing Chrome or start with debugging"""
    log_action("Setting up Chrome connection...", config)
    
    try:
        import subprocess
        import requests
        
        # First, check if Chrome is already running with debugging
        try:
            response = requests.get("http://localhost:9222/json/version", timeout=2)
            if response.status_code == 200:
                print("✅ Chrome is already running with debugging enabled!")
                print("You can now run: python3 postwriter.py sync")
                return
        except:
            pass
        
        # If Chrome is not running with debugging, give instructions
        print("Chrome needs to be started with debugging enabled.")
        print("\nOption 1 (Recommended): If you have Chrome already open:")
        print("1. Close all Chrome windows")
        print("2. Run this command in terminal:")
        print("   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
        print("3. Open Facebook and log in")
        print("4. Run: python3 postwriter.py sync")
        
        print("\nOption 2: Let me restart Chrome for you (will close current session)")
        restart = input("Restart Chrome automatically? (y/N): ").lower().strip()
        
        if restart == 'y':
            # Close existing Chrome processes
            print("Closing existing Chrome processes...")
            subprocess.run(["pkill", "-f", "Google Chrome"], capture_output=True)
            
            # Wait a moment
            import time
            time.sleep(2)
            
            # Start Chrome with debugging using default profile
            chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            cmd = [chrome_path, "--remote-debugging-port=9222"]
            
            print("Starting Chrome with debugging enabled...")
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("Chrome opened. Please navigate to Facebook and log in.")
            print("Then run: python3 postwriter.py sync")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Please manually start Chrome with: --remote-debugging-port=9222")

def cmd_login(args, config):
    """Open browser for manual login - Step 1"""
    log_action("Opening browser for manual login...", config)
    
    try:
        from scraper import FacebookScraper
        scraper = FacebookScraper(config)
        scraper.login_step()
        
    except Exception as e:
        print(f"Error during login: {e}")
        log_action(f"Login failed: {e}", config)

def cmd_export(args, config):
    """Export analysis data for content generation project"""
    log_action("Exporting analysis data...", config)
    
    try:
        from database import PostDatabase
        import json
        
        db = PostDatabase(config)
        
        # Export posts
        posts = db.get_posts()
        
        # Export templates
        templates = db.get_templates()
        
        # Export statistics
        stats = db.get_stats()
        
        # Create export data
        export_data = {
            'posts': posts,
            'templates': templates,
            'stats': stats,
            'profile_url': config['facebook']['profile_url'],
            'export_timestamp': log_action.__defaults__[0] if hasattr(log_action, '__defaults__') else "now"
        }
        
        # Save to export file
        export_file = './data/analysis_export.json'
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n=== Analysis Export Complete ===")
        print(f"Exported {len(posts)} posts")
        print(f"Exported {len(templates)} templates")
        print(f"Data saved to: {export_file}")
        print(f"Ready for content generation project!")
        
    except Exception as e:
        print(f"Error exporting data: {e}")

def cmd_analyze(args, config):
    """Run full analysis and create templates"""
    log_action("Running full post analysis...", config)
    
    try:
        from analyzer import PostAnalyzer
        analyzer = PostAnalyzer(config)
        
        # Create templates from posts
        templates_created = analyzer.analyze_and_store_templates()
        
        # Get analytics summary
        summary = analyzer.get_analytics_summary()
        
        print(f"\n=== Analysis Complete ===")
        print(f"Created {templates_created} templates")
        print(f"Total posts analyzed: {summary.get('total_posts', 0)}")
        print(f"Marketing posts: {summary.get('marketing_posts', 0)}")
        print(f"Average engagement: {summary.get('avg_engagement', 0):.2f}")
        
        if summary.get('top_hooks'):
            print(f"\nTop hook types:")
            for hook, count in summary['top_hooks'].items():
                print(f"  • {hook}: {count} posts")
        
        if summary.get('top_structures'):
            print(f"\nTop post structures:")
            for structure, count in summary['top_structures'].items():
                print(f"  • {structure}: {count} posts")
        
        print(f"\nRun 'python3 postwriter.py export' to prepare data for content generation")
        
    except Exception as e:
        print(f"Error during analysis: {e}")

def main():
    parser = argparse.ArgumentParser(description='PostWriter - Facebook Ads CLI Tool')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Chrome command  
    chrome_parser = subparsers.add_parser('chrome', help='Start Chrome with debugging (Easy Setup)')
    
    # Login command
    login_parser = subparsers.add_parser('login', help='Open browser for manual login (Alternative)')
    
    # Sync command
    sync_parser = subparsers.add_parser('sync', help='Sync posts from Facebook')
    
    # Topics command
    topics_parser = subparsers.add_parser('topics', help='Show leading topics')
    
    # Templates command
    tpl_parser = subparsers.add_parser('tpl', help='Template operations')
    tpl_subparsers = tpl_parser.add_subparsers(dest='subcommand')
    tpl_list = tpl_subparsers.add_parser('list', help='List templates')
    tpl_show = tpl_subparsers.add_parser('show', help='Show specific template')
    tpl_show.add_argument('template_id', type=int, help='Template ID to show')
    
    # Idea command
    idea_parser = subparsers.add_parser('idea', help='Generate content ideas')
    idea_parser.add_argument('idea', help='Idea or topic to explore')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Run full post analysis')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export data for content generation')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Load configuration
    config = load_config()
    setup_directories(config)
    
    # Route to appropriate command
    commands = {
        'chrome': cmd_chrome,
        'login': cmd_login,
        'sync': cmd_sync,
        'topics': cmd_topics,
        'tpl': cmd_templates,
        'idea': cmd_idea,
        'analyze': cmd_analyze,
        'export': cmd_export
    }
    
    if args.command in commands:
        commands[args.command](args, config)
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()

if __name__ == '__main__':
    main()