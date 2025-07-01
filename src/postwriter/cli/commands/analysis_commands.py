"""
PostWriter CLI - Analysis Commands  
Handles content analysis, template generation, and export functionality
"""

import json
import os
from datetime import datetime
from ...security.logging import get_secure_logger


def add_analysis_commands(subparsers):
    """Add analysis commands to CLI parser"""
    # Topics command
    topics_parser = subparsers.add_parser(
        'topics', 
        help='Show leading topics from analyzed posts'
    )
    topics_parser.set_defaults(func=handle_topics_command)
    
    # Templates command
    tpl_parser = subparsers.add_parser(
        'tpl', 
        help='Template operations'
    )
    tpl_subparsers = tpl_parser.add_subparsers(dest='subcommand')
    tpl_list = tpl_subparsers.add_parser('list', help='List available templates')
    tpl_show = tpl_subparsers.add_parser('show', help='Show specific template')
    tpl_show.add_argument('template_id', type=int, help='Template ID to show')
    tpl_parser.set_defaults(func=handle_templates_command)
    
    # Idea command
    idea_parser = subparsers.add_parser(
        'idea', 
        help='Generate content ideas based on successful patterns'
    )
    idea_parser.add_argument('idea', help='Topic or idea to explore')
    idea_parser.set_defaults(func=handle_idea_command)
    
    # Analyze command
    analyze_parser = subparsers.add_parser(
        'analyze', 
        help='Run comprehensive post analysis and create templates'
    )
    analyze_parser.set_defaults(func=handle_analyze_command)
    
    # Export command
    export_parser = subparsers.add_parser(
        'export', 
        help='Export analysis data for content generation'
    )
    export_parser.set_defaults(func=handle_export_command)


def handle_topics_command(args, config):
    """Show leading topics from posts"""
    logger = get_secure_logger()
    logger.info("Analyzing topics...")
    
    try:
        from ...core.analysis import PostAnalyzer
        analyzer = PostAnalyzer(config)
        topics = analyzer.analyze_topics()
        
        print("\n=== Top Topics ===")
        for i, topic in enumerate(topics, 1):
            print(f"{i}. {topic['name']} ({topic['count']} posts)")
        
        return 0
        
    except Exception as e:
        print(f"Error analyzing topics: {e}")
        return 1


def handle_templates_command(args, config):
    """List and manage templates"""
    logger = get_secure_logger()
    logger.info("Loading templates...")
    
    try:
        from ...core.database import PostDatabase
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
                return 1
        
        return 0
        
    except Exception as e:
        print(f"Error loading templates: {e}")
        return 1


def handle_idea_command(args, config):
    """Generate content ideas"""
    idea_text = args.idea
    logger = get_secure_logger()
    logger.info(f"Generating ideas for: {idea_text}")
    
    try:
        from ...core.analysis import PostAnalyzer
        analyzer = PostAnalyzer(config)
        ideas = analyzer.generate_ideas(idea_text)
        
        print(f"\n=== Ideas for '{idea_text}' ===")
        for i, idea in enumerate(ideas, 1):
            print(f"{i}. {idea}")
        
        return 0
        
    except Exception as e:
        print(f"Error generating ideas: {e}")
        return 1


def handle_analyze_command(args, config):
    """Run full analysis and create templates"""
    logger = get_secure_logger()
    logger.info("Running full post analysis...")
    
    try:
        from ...core.analysis import PostAnalyzer
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
        
        print(f"\nRun 'postwriter export' to prepare data for content generation")
        return 0
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        return 1


def handle_export_command(args, config):
    """Export analysis data for content generation project"""
    logger = get_secure_logger()
    logger.info("Exporting analysis data...")
    
    try:
        from ...core.database import PostDatabase
        
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
            'export_timestamp': datetime.now().isoformat()
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
        
        return 0
        
    except Exception as e:
        print(f"Error exporting data: {e}")
        return 1