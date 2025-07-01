"""
PostWriter CLI - Security Commands
Manages secure storage, validation, and security operations
"""

import os
from ...config import validate_config
from ...security import SecureStorage, CookieManager
from ...security.logging import get_secure_logger


def add_security_commands(subparsers):
    """Add security commands to CLI parser"""
    # Validate command
    validate_parser = subparsers.add_parser(
        'validate', 
        help='Validate configuration and security'
    )
    validate_parser.set_defaults(func=handle_validate_command)
    
    # Secure command
    secure_parser = subparsers.add_parser(
        'secure', 
        help='Manage secure storage for cookies and sensitive data'
    )
    secure_parser.add_argument(
        'operation', 
        choices=['import-cookies', 'status', 'delete'], 
        help='Secure storage operation'
    )
    secure_parser.add_argument(
        '--file', 
        help='File path for import operations'
    )
    secure_parser.add_argument(
        '--password', 
        help='Password for secure storage (will prompt if not provided)'
    )
    secure_parser.set_defaults(func=handle_secure_command)


def handle_validate_command(args, config):
    """Validate configuration without running any operations"""
    logger = get_secure_logger()
    logger.info("Validating configuration...")
    
    try:
        print("🔍 Running comprehensive configuration validation...")
        success = validate_config('config.yaml', create_dirs=False)
        
        if success:
            print("\n✅ Configuration is valid and ready to use!")
            print("You can now run other commands like 'sync', 'analyze', etc.")
            return 0
        else:
            print("\n❌ Configuration validation failed!")
            print("Please fix the errors above before running other commands.")
            return 1
        
    except Exception as e:
        print(f"Error during validation: {e}")
        return 1


def handle_secure_command(args, config):
    """Manage secure storage for cookies and sensitive data"""
    logger = get_secure_logger()
    logger.info(f"Secure storage operation: {args.operation}")
    
    try:
        if args.operation == 'import-cookies':
            return import_cookies_command(args, config)
        elif args.operation == 'status':
            return secure_status_command(args, config)
        elif args.operation == 'delete':
            return delete_secure_command(args, config)
        else:
            print(f"❌ Unknown secure operation: {args.operation}")
            return 1
    
    except ImportError:
        print("❌ Secure storage not available. Install cryptography package.")
        return 1
    except Exception as e:
        print(f"❌ Secure storage error: {e}")
        return 1


def import_cookies_command(args, config):
    """Import cookies securely"""
    if not args.file:
        print("❌ Error: --file argument required for import-cookies")
        return 1
    
    cookie_mgr = CookieManager()
    password = args.password
    success = cookie_mgr.save_cookies_from_file(args.file, password)
    
    if success:
        print(f"✅ Cookies imported securely from {args.file}")
        print("🔒 Cookies are now encrypted and stored safely")
        return 0
    else:
        print(f"❌ Failed to import cookies from {args.file}")
        return 1


def secure_status_command(args, config):
    """Show secure storage status"""
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
    
    return 0


def delete_secure_command(args, config):
    """Delete secure storage"""
    storage = SecureStorage()
    cookie_mgr = CookieManager()
    
    confirm = input("⚠️ This will delete all secure storage. Continue? (y/N): ")
    if confirm.lower() == 'y':
        storage.delete_storage()
        cookie_mgr.storage.delete_storage()
        print("✅ All secure storage deleted")
        return 0
    else:
        print("❌ Operation cancelled")
        return 1