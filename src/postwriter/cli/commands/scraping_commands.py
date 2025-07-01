"""
PostWriter CLI - Scraping Commands
Handles Facebook content scraping with security and rate limiting
"""

import os
import subprocess
import requests
from ...security import validate_chrome_security, SecureChromeManager
from ...security.logging import get_secure_logger


def add_scraping_commands(subparsers):
    """Add scraping commands to CLI parser"""
    # Chrome setup command  
    chrome_parser = subparsers.add_parser(
        'chrome', 
        help='Setup Chrome with secure debugging'
    )
    chrome_parser.set_defaults(func=handle_chrome_command)
    
    # Login command
    login_parser = subparsers.add_parser(
        'login', 
        help='Open browser for manual Facebook login'
    )
    login_parser.set_defaults(func=handle_login_command)
    
    # Sync command
    sync_parser = subparsers.add_parser(
        'sync', 
        help='Scrape Facebook posts with rate limiting'
    )
    sync_parser.set_defaults(func=handle_sync_command)


def handle_chrome_command(args, config):
    """Setup Chrome with secure debugging"""
    logger = get_secure_logger()
    logger.info("Setting up Chrome connection...")
    
    try:
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
                    import json
                    proxy_config = {
                        'proxy_port': result['proxy_port'],
                        'auth_token': result['auth_token'],
                        'chrome_port': result['chrome_port']
                    }
                    
                    # Store in config directory
                    config_dir = config['directories']['logs_dir']
                    proxy_config_file = os.path.join(config_dir, 'chrome_proxy_config.json')
                    with open(proxy_config_file, 'w') as f:
                        json.dump(proxy_config, f, indent=2)
                    print(f"📄 Proxy config saved to: {proxy_config_file}")
                    
                else:
                    print(f"❌ Failed to start secure proxy: {result['error']}")
                    print("💡 Falling back to direct Chrome connection")
            
            print("✅ Chrome is accessible for scraping")
            print("You can now run: postwriter sync")
            return 0
        
        # If Chrome is already secured, show status
        if security_results['chrome_debug_port_open'] and security_results['chrome_debug_secured']:
            print("✅ Chrome is running with security enabled!")
            print("You can now run: postwriter sync")
            return 0
        
        # If Chrome is not running, give setup instructions
        print("\n📋 Chrome Setup Instructions:")
        print("Chrome needs to be started with debugging enabled.")
        print("\nOption 1 (Recommended): Manual Chrome setup")
        print("1. Close all Chrome windows")
        print("2. Run this command in terminal:")
        print("   /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222")
        print("3. Open Facebook and log in")
        print("4. Run: postwriter chrome (to set up secure proxy)")
        print("5. Run: postwriter sync")
        
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
            print("Then run: postwriter chrome (to set up secure proxy)")
        
        return 0
        
    except ImportError:
        print("❌ Secure Chrome proxy not available")
        print("💡 Install required packages: pip install cryptography")
        return _fallback_chrome_setup()
    except Exception as e:
        print(f"Error: {e}")
        print("💡 Falling back to basic Chrome setup")
        return _fallback_chrome_setup()


def _fallback_chrome_setup():
    """Fallback Chrome setup without security features"""
    print("Please manually start Chrome with: --remote-debugging-port=9222")
    return 1


def handle_login_command(args, config):
    """Open browser for manual Facebook login"""
    logger = get_secure_logger()
    logger.info("Opening browser for manual login...")
    
    try:
        from ...core.scraper import FacebookScraper
        scraper = FacebookScraper(config)
        scraper.login_step()
        return 0
        
    except Exception as e:
        print(f"Error during login: {e}")
        logger.error(f"Login failed: {e}")
        return 1


def handle_sync_command(args, config):
    """Sync posts from Facebook profile with security and rate limiting"""
    logger = get_secure_logger()
    logger.info("Starting Facebook post sync...")
    
    if not config['facebook']['profile_url']:
        print("Error: Please set your Facebook profile URL in config.yaml")
        return 1
    
    try:
        from ...core.scraper import FacebookHTTPScraper
        from ...core.database import PostDatabase
        
        scraper = FacebookHTTPScraper(config)
        posts = scraper.scrape_posts()
        logger.info(f"Successfully scraped {len(posts)} posts")
        
        # Store posts in database
        db = PostDatabase(config)
        db.store_posts(posts)
        logger.info(f"Stored {len(posts)} posts in database")
        
        print(f"✅ Successfully scraped and stored {len(posts)} posts")
        return 0
        
    except ImportError as e:
        print(f"Error: Missing dependencies. Please install: {e}")
        return 1
    except Exception as e:
        print(f"Error during sync: {e}")
        logger.error(f"Sync failed: {e}")
        return 1