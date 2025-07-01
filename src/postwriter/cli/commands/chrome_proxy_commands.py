"""
PostWriter CLI - Chrome Proxy Commands
Manages secure Chrome debug proxy with authentication
"""

from ...security import SecureChromeManager, validate_chrome_security
from ...security.logging import get_secure_logger


def add_chrome_proxy_commands(subparsers):
    """Add Chrome proxy commands to CLI parser"""
    chrome_proxy_parser = subparsers.add_parser(
        'chrome-proxy', 
        help='Manage secure Chrome debug proxy'
    )
    chrome_proxy_parser.add_argument(
        'operation', 
        choices=['start', 'stop', 'status', 'test'], 
        help='Chrome proxy operation'
    )
    chrome_proxy_parser.add_argument(
        '--chrome-port', 
        type=int, 
        default=9222, 
        help='Chrome debug port (default: 9222)'
    )
    chrome_proxy_parser.add_argument(
        '--proxy-port', 
        type=int, 
        default=9223, 
        help='Secure proxy port (default: 9223)'
    )
    chrome_proxy_parser.set_defaults(func=handle_chrome_proxy_command)


def handle_chrome_proxy_command(args, config):
    """Handle Chrome proxy management commands"""
    logger = get_secure_logger()
    logger.info(f"Chrome proxy operation: {args.operation}")
    
    try:
        if args.operation == 'start':
            return start_proxy_command(args, config)
        elif args.operation == 'stop':
            return stop_proxy_command(args, config)
        elif args.operation == 'status':
            return proxy_status_command(args, config)
        elif args.operation == 'test':
            return test_proxy_command(args, config)
        else:
            print(f"❌ Unknown chrome-proxy operation: {args.operation}")
            return 1
            
    except ImportError:
        print("❌ Secure Chrome proxy not available")
        print("💡 Install required packages: pip install cryptography")
        return 1
    except Exception as e:
        print(f"❌ Chrome proxy error: {e}")
        return 1


def start_proxy_command(args, config):
    """Start secure Chrome proxy"""
    chrome_port = args.chrome_port
    proxy_port = args.proxy_port
    
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
        
        return 0
    else:
        print(f"❌ Failed to start proxy: {result['error']}")
        return 1


def stop_proxy_command(args, config):
    """Stop secure Chrome proxy"""
    manager = SecureChromeManager()
    success = manager.stop_secure_proxy()
    
    if success:
        print("✅ Secure Chrome proxy stopped")
        return 0
    else:
        print("❌ No proxy running or failed to stop")
        return 1


def proxy_status_command(args, config):
    """Show Chrome proxy security status"""
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
    
    return 0


def test_proxy_command(args, config):
    """Test proxy connection"""
    manager = SecureChromeManager()
    proxy_status = manager.get_proxy_status()
    
    if not proxy_status['running']:
        print("❌ Proxy not running. Start it first with: chrome-proxy start")
        return 1
    
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
        
        return 0
        
    except Exception as e:
        print(f"❌ Proxy test failed: {e}")
        return 1