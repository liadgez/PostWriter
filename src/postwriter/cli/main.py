#!/usr/bin/env python3
"""
PostWriter CLI Main Module
Entry point for the PostWriter command line interface
"""

import argparse
import sys
import os
from datetime import datetime

# Add src to path for imports during transition
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from ..config import load_config
from ..security.logging import get_secure_logger
from .commands import (
    browser_commands,
    chrome_proxy_commands, 
    scraping_commands,
    security_commands,
    analysis_commands,
    testing_commands
)


def log_action(message: str, config: dict):
    """Log action with timestamp"""
    logger = get_secure_logger()
    logger.info(message)
    
    # Also log to file if configured
    if 'directories' in config and 'logs_dir' in config['directories']:
        log_file = os.path.join(config['directories']['logs_dir'], 'postwriter.log')
        try:
            with open(log_file, 'a') as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {message}\n")
        except Exception:
            pass  # Fail silently for logging


def setup_directories(config: dict):
    """Ensure data directories exist (handled by config validator)"""
    # Directory creation is now handled by the config validator
    # This function is kept for backward compatibility
    pass


def create_parser():
    """Create and configure the argument parser"""
    parser = argparse.ArgumentParser(
        description='PostWriter - Secure Facebook Marketing Analysis Platform',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Security Features:
  • AES-256 encryption for browser sessions
  • Authenticated Chrome debug proxy
  • Intelligent rate limiting for Facebook
  • Secure logging with data filtering

Examples:
  postwriter validate                    # Validate configuration
  postwriter browser status              # Check browser security
  postwriter chrome-proxy start          # Start secure Chrome proxy
  postwriter sync                        # Scrape with rate limiting
  postwriter analyze                     # Generate marketing templates

For help with specific commands, use: postwriter <command> --help
        '''
    )
    
    subparsers = parser.add_subparsers(
        dest='command', 
        help='Available commands',
        metavar='<command>'
    )
    
    # Add command modules
    browser_commands.add_browser_commands(subparsers)
    chrome_proxy_commands.add_chrome_proxy_commands(subparsers)
    scraping_commands.add_scraping_commands(subparsers)
    security_commands.add_security_commands(subparsers)
    analysis_commands.add_analysis_commands(subparsers)
    testing_commands.add_testing_commands(subparsers)
    
    return parser


def main():
    """Main entry point for PostWriter CLI"""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        # Load configuration
        config = load_config()
        setup_directories(config)
        
        # Route to appropriate command handler
        if hasattr(args, 'func'):
            return args.func(args, config)
        else:
            print(f"Unknown command: {args.command}")
            parser.print_help()
            return 1
            
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())