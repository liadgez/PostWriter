"""
PostWriter CLI - Browser Management Commands
Handles secure browser session management and encryption
"""

import os
import glob
from ...security import SecureBrowserStorage, validate_browser_security
from ...security.logging import get_secure_logger


def add_browser_commands(subparsers):
    """Add browser management commands to CLI parser"""
    browser_parser = subparsers.add_parser(
        'browser', 
        help='Manage secure browser sessions'
    )
    browser_parser.add_argument(
        'operation', 
        choices=['encrypt-session', 'extract-chrome', 'status', 'load-session', 'delete-session'], 
        help='Browser operation'
    )
    browser_parser.add_argument(
        '--file', 
        help='Session file path (default: ./data/browser_profile/session.json)'
    )
    browser_parser.add_argument(
        '--name', 
        help='Session name (default: default)'
    )
    browser_parser.add_argument(
        '--password', 
        help='Password for secure storage (will prompt if not provided)'
    )
    browser_parser.set_defaults(func=handle_browser_command)


def handle_browser_command(args, config):
    """Handle browser management commands"""
    logger = get_secure_logger()
    logger.info(f"Browser operation: {args.operation}")
    
    try:
        if args.operation == 'encrypt-session':
            return encrypt_session_command(args, config)
        elif args.operation == 'extract-chrome':
            return extract_chrome_command(args, config)
        elif args.operation == 'status':
            return browser_status_command(args, config)
        elif args.operation == 'load-session':
            return load_session_command(args, config)
        elif args.operation == 'delete-session':
            return delete_session_command(args, config)
        else:
            print(f"❌ Unknown browser operation: {args.operation}")
            return 1
            
    except ImportError as e:
        print(f"❌ Browser security not available: {e}")
        print("💡 Install required packages: pip install cryptography websocket-client")
        return 1
    except Exception as e:
        print(f"❌ Browser operation error: {e}")
        return 1


def encrypt_session_command(args, config):
    """Encrypt existing session.json file"""
    session_file = args.file or './data/browser_profile/session.json'
    
    if not os.path.exists(session_file):
        print(f"❌ Session file not found: {session_file}")
        print("💡 Available session files:")
        for pattern in ['./data/browser_profile/*.json', './data/*.json', './*.json']:
            files = glob.glob(pattern)
            for f in files:
                if 'session' in f or 'cookie' in f:
                    print(f"   📄 {f}")
        return 1
    
    browser_storage = SecureBrowserStorage()
    session_name = args.name or 'default'
    password = args.password
    
    success = browser_storage.encrypt_existing_session_file(
        session_file, session_name, password, backup=True
    )
    
    if success:
        print(f"🔒 Session file encrypted successfully")
        print(f"💡 Use 'browser status' to verify secure storage")
        return 0
    else:
        print(f"❌ Failed to encrypt session file")
        return 1


def extract_chrome_command(args, config):
    """Extract current Chrome session and encrypt it"""
    from ...security.browser_storage import ChromeSessionManager
    
    session_manager = ChromeSessionManager()
    session_name = args.name or 'default'
    password = args.password
    
    success = session_manager.extract_and_encrypt_session(session_name, password)
    
    if success:
        print(f"✅ Chrome session extracted and encrypted")
        print(f"💡 Session saved as '{session_name}'")
        return 0
    else:
        print(f"❌ Failed to extract Chrome session")
        print("💡 Make sure Chrome is running with --remote-debugging-port=9222")
        print("💡 and you have a Facebook tab open")
        return 1


def browser_status_command(args, config):
    """Show browser security status"""
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
    
    return 0


def load_session_command(args, config):
    """Load encrypted session (for debugging/testing)"""
    browser_storage = SecureBrowserStorage()
    session_name = args.name or 'default'
    password = args.password
    
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
        return 0
    else:
        print(f"❌ Failed to load session '{session_name}'")
        return 1


def delete_session_command(args, config):
    """Delete an encrypted session"""
    browser_storage = SecureBrowserStorage()
    session_name = args.name or 'default'
    
    success = browser_storage.delete_session(session_name, confirm=False)
    
    if success:
        print(f"✅ Session '{session_name}' deleted")
        return 0
    else:
        print(f"❌ Failed to delete session '{session_name}'")
        return 1