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
from secure_logging import get_secure_logger

def load_config():
    """Load and validate configuration from config.yaml"""
    try:
        from config_validator import ConfigValidator, ConfigValidationError
        
        validator = ConfigValidator('config.yaml')
        
        # Validate configuration
        if not validator.validate_all(create_dirs=True):
            print("❌ Configuration validation failed. Please fix the errors above.")
            sys.exit(1)
        
        return validator.get_config()
        
    except ConfigValidationError as e:
        print(f"❌ Configuration Error: {e}")
        sys.exit(1)
    except ImportError:
        # Fallback to basic loading if validator not available
        print("⚠️  Configuration validator not available, using basic loading...")
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
    """Ensure data directories exist (handled by config validator)"""
    # Directory creation is now handled by the config validator
    # This function is kept for backward compatibility
    pass

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
        from secure_chrome_proxy import validate_chrome_security, SecureChromeManager
        
        # Check Chrome security status
        security_results = validate_chrome_security()
        print("🔍 Chrome Security Status:")
        print(f"   • Chrome debug port open: {'✅' if security_results['chrome_debug_port_open'] else '❌'}")
        print(f"   • Chrome debug secured: {'✅' if security_results['chrome_debug_secured'] else '⚠️'}")
        print(f"   • Secure proxy available: {'✅' if security_results['proxy_available'] else '❌'}")
        
        # If Chrome is running but unsecured, recommend secure proxy
        if security_results['chrome_debug_port_open'] and not security_results['chrome_debug_secured']:
            print("\n⚠️ WARNING: Chrome debug port is unsecured!")
            print("💡 Recommendation: Use secure proxy for protection")
            
            use_proxy = input("Start secure Chrome proxy? (Y/n): ").lower().strip()
            if use_proxy != 'n':
                print("\n🔒 Starting secure Chrome proxy...")
                manager = SecureChromeManager()
                result = manager.start_secure_proxy()
                
                if result['success']:
                    logger = get_secure_logger()
                    logger.info("✅ Secure Chrome proxy started!")
                    logger.info(f"   • Secure port: {result['proxy_port']}")
                    logger.log_security_event("chrome_proxy_started", {
                        "proxy_port": result['proxy_port'],
                        "auth_token": result['auth_token'],
                        "chrome_running": result['chrome_running']
                    })
                    print(f"   • Chrome running: {result['chrome_running']}")
                    print("\n💡 Use 'chrome-proxy status' to manage the proxy")
                    print("💡 Use this secured connection for scraping operations")
                    
                    # Save proxy config for later use
                    proxy_config = {
                        'proxy_port': result['proxy_port'],
                        'auth_token': result['auth_token'],
                        'chrome_port': result['chrome_port']
                    }
                    
                    # Store in config directory
                    import json
                    config_dir = config['directories']['logs_dir']
                    proxy_config_file = os.path.join(config_dir, 'chrome_proxy_config.json')
                    with open(proxy_config_file, 'w') as f:
                        json.dump(proxy_config, f, indent=2)
                    print(f"📄 Proxy config saved to: {proxy_config_file}")
                    
                else:
                    print(f"❌ Failed to start secure proxy: {result['error']}")
                    print("💡 Falling back to direct Chrome connection")
            
            print("✅ Chrome is accessible for scraping")
            print("You can now run: python3 postwriter.py sync")
            return
        
        # If Chrome is already secured, show status
        if security_results['chrome_debug_port_open'] and security_results['chrome_debug_secured']:
            print("✅ Chrome is running with security enabled!")
            print("You can now run: python3 postwriter.py sync")
            return
        
        # If Chrome is not running, give setup instructions
        print("\n📋 Chrome Setup Instructions:")
        print("Chrome needs to be started with debugging enabled.")
        print("\nOption 1 (Recommended): Manual Chrome setup")
        print("1. Close all Chrome windows")
        print("2. Run this command in terminal:")
        print("   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
        print("3. Open Facebook and log in")
        print("4. Run: python3 postwriter.py chrome (to set up secure proxy)")
        print("5. Run: python3 postwriter.py sync")
        
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
            print("Then run: python3 postwriter.py chrome (to set up secure proxy)")
        
    except ImportError:
        print("❌ Secure Chrome proxy not available")
        print("💡 Install required packages: pip install cryptography")
        # Fallback to original Chrome setup
        _fallback_chrome_setup(config)
    except Exception as e:
        print(f"Error: {e}")
        print("💡 Falling back to basic Chrome setup")
        _fallback_chrome_setup(config)


def _fallback_chrome_setup(config):
    """Fallback Chrome setup without security features"""
    print("Please manually start Chrome with: --remote-debugging-port=9222")


def cmd_chrome_proxy(args, config):
    """Manage secure Chrome proxy"""
    log_action(f"Chrome proxy operation: {args.operation}", config)
    
    try:
        from secure_chrome_proxy import SecureChromeManager, validate_chrome_security
        
        if args.operation == 'start':
            chrome_port = getattr(args, 'chrome_port', None) or 9222
            proxy_port = getattr(args, 'proxy_port', None) or 9223
            
            print(f"🔒 Starting secure Chrome proxy...")
            print(f"   • Chrome port: {chrome_port}")
            print(f"   • Proxy port: {proxy_port}")
            
            manager = SecureChromeManager()
            result = manager.start_secure_proxy(chrome_port, proxy_port)
            
            if result['success']:
                logger = get_secure_logger()
                logger.info("✅ Secure Chrome proxy started successfully!")
                logger.info(f"   • Proxy port: {result['proxy_port']}")
                logger.log_security_event("chrome_proxy_manual_start", {
                    "proxy_port": result['proxy_port'],
                    "auth_token": result['auth_token'],
                    "chrome_running": result['chrome_running']
                })
                print(f"   • Chrome running: {result['chrome_running']}")
                print(f"\n🔑 Access URLs:")
                print(f"   • Status: {result['endpoints']['status']}")
                print(f"   • Chrome API: {result['endpoints']['chrome_api']}?auth_token=***TOKEN_REDACTED***")
                
                if not result['chrome_running']:
                    print(f"\n⚠️ Chrome is not running on port {chrome_port}")
                    print(f"💡 Start Chrome with: --remote-debugging-port={chrome_port}")
                
            else:
                print(f"❌ Failed to start proxy: {result['error']}")
        
        elif args.operation == 'stop':
            manager = SecureChromeManager()
            success = manager.stop_secure_proxy()
            
            if success:
                print("✅ Secure Chrome proxy stopped")
            else:
                print("❌ No proxy running or failed to stop")
        
        elif args.operation == 'status':
            print("🔍 Chrome Proxy Security Assessment:")
            
            # Check overall Chrome security
            security_results = validate_chrome_security()
            print(f"   • Chrome debug port open: {'✅' if security_results['chrome_debug_port_open'] else '❌'}")
            print(f"   • Chrome debug secured: {'✅' if security_results['chrome_debug_secured'] else '⚠️'}")
            print(f"   • Secure proxy available: {'✅' if security_results['proxy_available'] else '❌'}")
            
            # Check proxy status
            manager = SecureChromeManager()
            proxy_status = manager.get_proxy_status()
            
            if proxy_status['running']:
                print(f"\n🔒 Secure Proxy Status:")
                print(f"   • Running: ✅")
                print(f"   • Proxy port: {proxy_status['proxy_port']}")
                print(f"   • Chrome port: {proxy_status['chrome_port']}")
                print(f"   • Chrome accessible: {'✅' if proxy_status['chrome_running'] else '❌'}")
                print(f"   • Active sessions: {proxy_status['active_sessions']}")
                print(f"   • Active connections: {proxy_status['active_connections']}")
                logger = get_secure_logger()
                logger.log_security_event("auth_token_status_check", {
                    "auth_token": proxy_status['auth_token']
                })
                print(f"   • Auth token: ***TOKEN_AVAILABLE***")
            else:
                print(f"\n🔒 Secure Proxy Status: ❌ Not running")
            
            if security_results['recommendations']:
                print(f"\n🛡️ Security Recommendations:")
                for rec in security_results['recommendations']:
                    print(f"   • {rec}")
        
        elif args.operation == 'test':
            # Test proxy connection
            manager = SecureChromeManager()
            proxy_status = manager.get_proxy_status()
            
            if not proxy_status['running']:
                print("❌ Proxy not running. Start it first with: chrome-proxy start")
                return
            
            print(f"🧪 Testing secure proxy connection...")
            
            try:
                import requests
                
                # Test status endpoint (no auth required)
                status_url = f"http://localhost:{proxy_status['proxy_port']}/status"
                response = requests.get(status_url, timeout=5)
                
                if response.status_code == 200:
                    status_data = response.json()
                    print(f"✅ Proxy status endpoint working")
                    print(f"   • Proxy running: {status_data['proxy_running']}")
                    print(f"   • Chrome running: {status_data['chrome_running']}")
                else:
                    print(f"❌ Proxy status endpoint failed: {response.status_code}")
                
                # Test authenticated endpoint
                headers = {'X-Auth-Token': proxy_status['auth_token']}
                api_url = f"http://localhost:{proxy_status['proxy_port']}/json"
                response = requests.get(api_url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    print(f"✅ Authenticated Chrome API access working")
                    tabs = response.json()
                    print(f"   • Found {len(tabs)} Chrome tabs")
                    
                    facebook_tabs = [tab for tab in tabs if 'facebook.com' in tab.get('url', '')]
                    if facebook_tabs:
                        print(f"   • Found {len(facebook_tabs)} Facebook tabs")
                    else:
                        print(f"   • No Facebook tabs found")
                else:
                    print(f"❌ Authenticated API access failed: {response.status_code}")
                
            except Exception as e:
                print(f"❌ Proxy test failed: {e}")
        
        else:
            print(f"❌ Unknown chrome-proxy operation: {args.operation}")
            print("💡 Available operations: start, stop, status, test")
    
    except ImportError:
        print("❌ Secure Chrome proxy not available")
        print("💡 Install required packages: pip install cryptography")
    except Exception as e:
        print(f"❌ Chrome proxy error: {e}")

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

def cmd_validate(args, config):
    """Validate configuration without running any operations"""
    log_action("Validating configuration...", config)
    
    try:
        from config_validator import validate_config
        
        print("🔍 Running comprehensive configuration validation...")
        success = validate_config('config.yaml', create_dirs=False)
        
        if success:
            print("\n✅ Configuration is valid and ready to use!")
            print("You can now run other commands like 'sync', 'analyze', etc.")
        else:
            print("\n❌ Configuration validation failed!")
            print("Please fix the errors above before running other commands.")
        
    except Exception as e:
        print(f"Error during validation: {e}")

def cmd_secure(args, config):
    """Manage secure storage for cookies and sensitive data"""
    log_action(f"Secure storage operation: {args.operation}", config)
    
    try:
        from secure_storage import CookieManager, SecureStorage
        
        if args.operation == 'import-cookies':
            if not args.file:
                print("❌ Error: --file argument required for import-cookies")
                return
            
            cookie_mgr = CookieManager()
            password = getattr(args, 'password', None)
            success = cookie_mgr.save_cookies_from_file(args.file, password)
            
            if success:
                print(f"✅ Cookies imported securely from {args.file}")
                print("🔒 Cookies are now encrypted and stored safely")
            else:
                print(f"❌ Failed to import cookies from {args.file}")
        
        elif args.operation == 'status':
            cookie_mgr = CookieManager()
            
            if cookie_mgr.has_cookies():
                print("✅ Secure cookies are available")
                try:
                    cookies = cookie_mgr.get_cookies_for_requests()
                    print(f"🔒 {len(cookies)} cookies stored securely")
                except:
                    print("🔒 Secure cookies exist (password required to view)")
            else:
                print("⚠️ No secure cookies found")
            
            # Check for regular cookie files
            regular_file = config['facebook']['cookies_path']
            if os.path.exists(regular_file):
                print(f"📄 Regular cookie file exists: {regular_file}")
                print("💡 Run 'secure import-cookies --file <path>' to encrypt them")
        
        elif args.operation == 'delete':
            storage = SecureStorage()
            cookie_mgr = CookieManager()
            
            confirm = input("⚠️ This will delete all secure storage. Continue? (y/N): ")
            if confirm.lower() == 'y':
                storage.delete_storage()
                cookie_mgr.storage.delete_storage()
                print("✅ All secure storage deleted")
            else:
                print("❌ Operation cancelled")
        
        else:
            print(f"❌ Unknown secure operation: {args.operation}")
    
    except ImportError:
        print("❌ Secure storage not available. Install cryptography package.")
    except Exception as e:
        print(f"❌ Secure storage error: {e}")


def cmd_browser(args, config):
    """Manage secure browser sessions and Chrome debugging"""
    log_action(f"Browser operation: {args.operation}", config)
    
    try:
        from secure_browser_storage import SecureBrowserStorage, ChromeSessionManager, validate_browser_security
        
        if args.operation == 'encrypt-session':
            # Encrypt existing session.json file
            session_file = args.file or './data/browser_profile/session.json'
            
            if not os.path.exists(session_file):
                print(f"❌ Session file not found: {session_file}")
                print("💡 Available session files:")
                import glob
                for pattern in ['./data/browser_profile/*.json', './data/*.json', './*.json']:
                    files = glob.glob(pattern)
                    for f in files:
                        if 'session' in f or 'cookie' in f:
                            print(f"   📄 {f}")
                return
            
            browser_storage = SecureBrowserStorage()
            session_name = getattr(args, 'name', None) or 'default'
            password = getattr(args, 'password', None)
            
            success = browser_storage.encrypt_existing_session_file(
                session_file, session_name, password, backup=True
            )
            
            if success:
                print(f"🔒 Session file encrypted successfully")
                print(f"💡 Use 'browser status' to verify secure storage")
            else:
                print(f"❌ Failed to encrypt session file")
        
        elif args.operation == 'extract-chrome':
            # Extract current Chrome session and encrypt it
            session_manager = ChromeSessionManager()
            session_name = getattr(args, 'name', None) or 'default'
            password = getattr(args, 'password', None)
            
            success = session_manager.extract_and_encrypt_session(session_name, password)
            
            if success:
                print(f"✅ Chrome session extracted and encrypted")
                print(f"💡 Session saved as '{session_name}'")
            else:
                print(f"❌ Failed to extract Chrome session")
                print("💡 Make sure Chrome is running with --remote-debugging-port=9222")
                print("💡 and you have a Facebook tab open")
        
        elif args.operation == 'status':
            # Show browser security status
            print("🔍 Browser Security Assessment:")
            
            security_results = validate_browser_security()
            
            print(f"   • Secure storage available: {'✅' if security_results['secure_storage_available'] else '❌'}")
            
            if security_results['plaintext_sessions_found']:
                print(f"   • ⚠️ Plaintext sessions found:")
                for session_file in security_results['plaintext_sessions_found']:
                    print(f"     📄 {session_file}")
                print(f"     💡 Run 'browser encrypt-session --file <path>' to encrypt")
            else:
                print(f"   • ✅ No plaintext sessions found")
            
            if security_results['encrypted_sessions_found']:
                print(f"   • ✅ Encrypted sessions available:")
                for session in security_results['encrypted_sessions_found']:
                    print(f"     🔒 {session}")
            else:
                print(f"   • ⚠️ No encrypted sessions found")
            
            chrome_status = "✅ Secure" if security_results['chrome_debug_secure'] else "⚠️ Unsecured"
            print(f"   • Chrome debug port: {chrome_status}")
            
            if security_results['recommendations']:
                print(f"\n🛡️ Security Recommendations:")
                for rec in security_results['recommendations']:
                    print(f"   • {rec}")
        
        elif args.operation == 'load-session':
            # Load encrypted session (for debugging/testing)
            browser_storage = SecureBrowserStorage()
            session_name = getattr(args, 'name', None) or 'default'
            password = getattr(args, 'password', None)
            
            session_data = browser_storage.load_session_data(session_name, password)
            
            if session_data:
                print(f"✅ Successfully loaded session '{session_name}'")
                print(f"🍪 Contains {len(session_data.get('cookies', []))} cookies")
                
                origins = session_data.get('origins', [])
                if origins:
                    localStorage_items = len(origins[0].get('localStorage', []))
                    print(f"💾 Contains {localStorage_items} localStorage items")
                
                # Show some cookie names (not values for security)
                cookies = session_data.get('cookies', [])[:5]
                if cookies:
                    print(f"📋 Sample cookies: {[c.get('name', 'unknown') for c in cookies]}")
            else:
                print(f"❌ Failed to load session '{session_name}'")
        
        elif args.operation == 'delete-session':
            # Delete an encrypted session
            browser_storage = SecureBrowserStorage()
            session_name = getattr(args, 'name', None) or 'default'
            
            success = browser_storage.delete_session(session_name, confirm=False)
            
            if success:
                print(f"✅ Session '{session_name}' deleted")
            else:
                print(f"❌ Failed to delete session '{session_name}'")
        
        else:
            print(f"❌ Unknown browser operation: {args.operation}")
            print("💡 Available operations: encrypt-session, extract-chrome, status, load-session, delete-session")
    
    except ImportError as e:
        print(f"❌ Browser security not available: {e}")
        print("💡 Install required packages: pip install cryptography websocket-client")
    except Exception as e:
        print(f"❌ Browser operation error: {e}")

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
    
    # Chrome proxy command
    chrome_proxy_parser = subparsers.add_parser('chrome-proxy', help='Manage secure Chrome debug proxy')
    chrome_proxy_parser.add_argument('operation', 
                                    choices=['start', 'stop', 'status', 'test'], 
                                    help='Chrome proxy operation')
    chrome_proxy_parser.add_argument('--chrome-port', type=int, default=9222, 
                                    help='Chrome debug port (default: 9222)')
    chrome_proxy_parser.add_argument('--proxy-port', type=int, default=9223, 
                                    help='Secure proxy port (default: 9223)')
    
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
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate configuration')
    
    # Secure command
    secure_parser = subparsers.add_parser('secure', help='Manage secure storage')
    secure_parser.add_argument('operation', choices=['import-cookies', 'status', 'delete'], 
                              help='Secure storage operation')
    secure_parser.add_argument('--file', help='File path for import operations')
    secure_parser.add_argument('--password', help='Password for secure storage (will prompt if not provided)')
    
    # Browser command
    browser_parser = subparsers.add_parser('browser', help='Manage secure browser sessions')
    browser_parser.add_argument('operation', 
                               choices=['encrypt-session', 'extract-chrome', 'status', 'load-session', 'delete-session'], 
                               help='Browser operation')
    browser_parser.add_argument('--file', help='Session file path (default: ./data/browser_profile/session.json)')
    browser_parser.add_argument('--name', help='Session name (default: default)')
    browser_parser.add_argument('--password', help='Password for secure storage (will prompt if not provided)')
    
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
        'chrome-proxy': cmd_chrome_proxy,
        'login': cmd_login,
        'sync': cmd_sync,
        'topics': cmd_topics,
        'tpl': cmd_templates,
        'idea': cmd_idea,
        'analyze': cmd_analyze,
        'export': cmd_export,
        'validate': cmd_validate,
        'secure': cmd_secure,
        'browser': cmd_browser
    }
    
    if args.command in commands:
        commands[args.command](args, config)
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()

if __name__ == '__main__':
    main()