#!/usr/bin/env python3
"""
Secure Browser Session Storage for PostWriter
Encrypts browser profile data including cookies, session storage, and localStorage
"""

import os
import json
import getpass
from typing import Dict, List, Any, Optional
from .storage import SecureStorage
from ..utils.exceptions import SecurityError, ConfigurationError


class SecureBrowserStorage:
    """Manages encrypted storage of browser session data"""
    
    def __init__(self, storage_name: str = "browser_sessions"):
        """Initialize secure browser storage"""
        # Create full path for the storage file
        storage_path = os.path.expanduser(f"~/.postwriter_{storage_name}")
        self.storage = SecureStorage(storage_path)
        self.session_file = None
    
    def save_session_data(self, session_data: Dict[str, Any], session_name: str = "default", password: str = None) -> bool:
        """
        Save browser session data with encryption
        
        Args:
            session_data: Dictionary containing cookies, localStorage, etc.
            session_name: Name identifier for this session
            password: Optional password (will prompt if not provided)
            
        Returns:
            bool: True if successfully saved
        """
        try:
            # Validate session data structure
            if not isinstance(session_data, dict):
                raise SecurityError("Session data must be a dictionary")
            
            # Ensure we have critical fields
            if 'cookies' not in session_data:
                session_data['cookies'] = []
            
            # Add metadata
            from datetime import datetime
            session_data['_metadata'] = {
                'session_name': session_name,
                'encrypted_at': datetime.now().isoformat(),
                'version': '1.0'
            }
            
            # Save with encryption
            try:
                self.storage.store_data(session_data, password)
                print(f"✅ Browser session '{session_name}' encrypted and stored securely")
                return True
            except SecurityError as e:
                print(f"❌ Failed to encrypt browser session '{session_name}': {e}")
                return False
                
        except Exception as e:
            print(f"❌ Error saving browser session: {e}")
            return False
    
    def load_session_data(self, session_name: str = "default", password: str = None) -> Optional[Dict[str, Any]]:
        """
        Load and decrypt browser session data
        
        Args:
            session_name: Name identifier for the session
            password: Optional password (will prompt if not provided)
            
        Returns:
            Dict containing session data or None if failed
        """
        try:
            # Load encrypted data
            session_data = self.storage.load_data(password)
            
            if session_data is None:
                return None
            
            # Validate loaded data
            if not isinstance(session_data, dict):
                raise SecurityError("Invalid session data format")
            
            # Check metadata
            metadata = session_data.get('_metadata', {})
            stored_name = metadata.get('session_name', 'unknown')
            
            if stored_name != session_name:
                print(f"⚠️ Warning: Requested session '{session_name}' but found '{stored_name}'")
            
            print(f"✅ Successfully decrypted browser session '{stored_name}'")
            return session_data
            
        except Exception as e:
            print(f"❌ Error loading browser session: {e}")
            return None
    
    def encrypt_existing_session_file(self, file_path: str, session_name: str = "default", 
                                    password: str = None, backup: bool = True) -> bool:
        """
        Encrypt an existing plaintext session file
        
        Args:
            file_path: Path to existing session.json file
            session_name: Name for this session
            password: Optional password (will prompt if not provided)
            backup: Whether to create a backup of the original file
            
        Returns:
            bool: True if successfully encrypted
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                print(f"❌ Session file not found: {file_path}")
                return False
            
            # Read existing session data
            with open(file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            print(f"📄 Read {len(json.dumps(session_data))} bytes from {file_path}")
            
            # Create backup if requested
            if backup:
                backup_path = f"{file_path}.backup"
                import shutil
                shutil.copy2(file_path, backup_path)
                print(f"💾 Created backup: {backup_path}")
            
            # Encrypt and save
            success = self.save_session_data(session_data, session_name, password)
            
            if success:
                # Securely delete original file
                self._secure_delete_file(file_path)
                print(f"🔒 Original file securely deleted: {file_path}")
                print(f"✅ Session data encrypted as '{session_name}'")
                return True
            else:
                print(f"❌ Failed to encrypt session data")
                return False
                
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in session file: {e}")
            return False
        except Exception as e:
            print(f"❌ Error encrypting session file: {e}")
            return False
    
    def get_cookies_for_requests(self, session_name: str = "default", password: str = None) -> Optional[Dict[str, str]]:
        """
        Get cookies in format suitable for requests library
        
        Args:
            session_name: Session identifier
            password: Optional password
            
        Returns:
            Dict of cookie name-value pairs or None
        """
        try:
            session_data = self.load_session_data(session_name, password)
            if not session_data:
                return None
            
            cookies = session_data.get('cookies', [])
            cookie_dict = {}
            
            for cookie in cookies:
                if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                    cookie_dict[cookie['name']] = cookie['value']
            
            print(f"🍪 Extracted {len(cookie_dict)} cookies for requests")
            return cookie_dict
            
        except Exception as e:
            print(f"❌ Error extracting cookies: {e}")
            return None
    
    def get_selenium_cookies(self, session_name: str = "default", password: str = None) -> Optional[List[Dict[str, Any]]]:
        """
        Get cookies in format suitable for Selenium WebDriver
        
        Args:
            session_name: Session identifier  
            password: Optional password
            
        Returns:
            List of cookie dictionaries or None
        """
        try:
            session_data = self.load_session_data(session_name, password)
            if not session_data:
                return None
            
            cookies = session_data.get('cookies', [])
            selenium_cookies = []
            
            for cookie in cookies:
                if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                    # Convert to Selenium format
                    selenium_cookie = {
                        'name': cookie['name'],
                        'value': cookie['value'],
                        'domain': cookie.get('domain', '.facebook.com'),
                        'path': cookie.get('path', '/'),
                        'secure': cookie.get('secure', True),
                        'httpOnly': cookie.get('httpOnly', False)
                    }
                    
                    # Add expiry if present
                    if 'expires' in cookie and cookie['expires'] != -1:
                        selenium_cookie['expiry'] = cookie['expires']
                    
                    selenium_cookies.append(selenium_cookie)
            
            print(f"🍪 Prepared {len(selenium_cookies)} cookies for Selenium")
            return selenium_cookies
            
        except Exception as e:
            print(f"❌ Error preparing Selenium cookies: {e}")
            return None
    
    def list_sessions(self) -> List[str]:
        """List all available encrypted sessions"""
        try:
            if self.storage.storage_exists():
                # For now, we only support one session per storage file
                # Could be extended to support multiple sessions
                return ["encrypted_session (password required)"]
            else:
                return []
        except Exception:
            return []
    
    def delete_session(self, session_name: str = "default", confirm: bool = False) -> bool:
        """
        Delete an encrypted session
        
        Args:
            session_name: Session to delete
            confirm: Whether deletion is confirmed
            
        Returns:
            bool: True if successfully deleted
        """
        try:
            if not confirm:
                response = input(f"⚠️ Delete session '{session_name}'? This cannot be undone. (y/N): ")
                if response.lower() != 'y':
                    print("❌ Deletion cancelled")
                    return False
            
            success = self.storage.delete_storage()
            if success:
                print(f"✅ Session '{session_name}' deleted successfully")
                return True
            else:
                print(f"❌ Failed to delete session '{session_name}'")
                return False
                
        except Exception as e:
            print(f"❌ Error deleting session: {e}")
            return False
    
    def _secure_delete_file(self, file_path: str) -> None:
        """Securely delete a file by overwriting it first"""
        try:
            if os.path.exists(file_path):
                # Get file size
                file_size = os.path.getsize(file_path)
                
                # Overwrite with random data multiple times
                with open(file_path, 'r+b') as f:
                    for _ in range(3):
                        f.seek(0)
                        f.write(os.urandom(file_size))
                        f.flush()
                        os.fsync(f.fileno())
                
                # Finally delete the file
                os.remove(file_path)
                
        except Exception as e:
            print(f"⚠️ Warning: Could not securely delete {file_path}: {e}")
            # Fallback to regular deletion
            try:
                os.remove(file_path)
            except:
                pass


class ChromeSessionManager:
    """Manages Chrome debugging session with secure storage"""
    
    def __init__(self, debug_port: int = 9222):
        self.debug_port = debug_port
        self.browser_storage = SecureBrowserStorage("chrome_sessions")
    
    def extract_and_encrypt_session(self, session_name: str = "default", password: str = None) -> bool:
        """
        Extract current Chrome session and encrypt it
        
        Args:
            session_name: Name for this session
            password: Optional password
            
        Returns:
            bool: True if successful
        """
        try:
            import requests
            import websocket
            
            # Get Chrome tabs
            response = requests.get(f"http://localhost:{self.debug_port}/json/list", timeout=5)
            tabs = response.json()
            
            # Find Facebook tab
            facebook_tab = None
            for tab in tabs:
                if 'facebook.com' in tab.get('url', ''):
                    facebook_tab = tab
                    break
            
            if not facebook_tab:
                print("❌ No Facebook tab found in Chrome")
                return False
            
            print(f"📱 Found Facebook tab: {facebook_tab['title']}")
            
            # Connect to tab debugger
            ws_url = facebook_tab['webSocketDebuggerUrl']
            ws = websocket.create_connection(ws_url)
            
            # Enable required domains
            ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
            ws.recv()
            
            ws.send(json.dumps({"id": 2, "method": "Network.enable"}))
            ws.recv()
            
            ws.send(json.dumps({"id": 3, "method": "DOMStorage.enable"}))
            ws.recv()
            
            # Get cookies
            ws.send(json.dumps({"id": 4, "method": "Network.getCookies"}))
            cookies_response = ws.recv()
            
            # Get localStorage
            ws.send(json.dumps({
                "id": 5, 
                "method": "DOMStorage.getDOMStorageItems",
                "params": {"storageId": {"securityOrigin": "https://www.facebook.com", "isLocalStorage": True}}
            }))
            localStorage_response = ws.recv()
            
            ws.close()
            
            # Parse responses
            cookies_data = json.loads(cookies_response)
            localStorage_data = json.loads(localStorage_response)
            
            # Build session data
            session_data = {
                'cookies': cookies_data.get('result', {}).get('cookies', []),
                'origins': [{
                    'origin': 'https://www.facebook.com',
                    'localStorage': []
                }]
            }
            
            # Add localStorage if available
            if 'result' in localStorage_data and 'entries' in localStorage_data['result']:
                for entry in localStorage_data['result']['entries']:
                    if len(entry) >= 2:
                        session_data['origins'][0]['localStorage'].append({
                            'name': entry[0],
                            'value': entry[1]
                        })
            
            # Save encrypted session
            success = self.browser_storage.save_session_data(session_data, session_name, password)
            
            if success:
                print(f"✅ Chrome session extracted and encrypted as '{session_name}'")
                print(f"🍪 Secured {len(session_data['cookies'])} cookies")
                print(f"💾 Secured {len(session_data['origins'][0]['localStorage'])} localStorage items")
                return True
            else:
                return False
                
        except requests.exceptions.ConnectionError:
            print(f"❌ Could not connect to Chrome debug port {self.debug_port}")
            print("   Make sure Chrome is running with --remote-debugging-port=9222")
            return False
        except Exception as e:
            print(f"❌ Error extracting Chrome session: {e}")
            return False
    
    def load_session_to_selenium(self, driver, session_name: str = "default", password: str = None) -> bool:
        """
        Load encrypted session data into Selenium WebDriver
        
        Args:
            driver: Selenium WebDriver instance
            session_name: Session to load
            password: Optional password
            
        Returns:
            bool: True if successful
        """
        try:
            # Get cookies in Selenium format
            cookies = self.browser_storage.get_selenium_cookies(session_name, password)
            if not cookies:
                return False
            
            # Navigate to Facebook first
            driver.get("https://www.facebook.com")
            
            # Add cookies to driver
            for cookie in cookies:
                try:
                    driver.add_cookie(cookie)
                except Exception as e:
                    print(f"⚠️ Warning: Could not add cookie {cookie['name']}: {e}")
            
            print(f"✅ Loaded {len(cookies)} cookies into Selenium driver")
            
            # Refresh to apply cookies
            driver.refresh()
            return True
            
        except Exception as e:
            print(f"❌ Error loading session to Selenium: {e}")
            return False


def validate_browser_security() -> Dict[str, Any]:
    """
    Validate browser security configuration
    
    Returns:
        Dict with security assessment results
    """
    results = {
        'secure_storage_available': False,
        'plaintext_sessions_found': [],
        'encrypted_sessions_found': [],
        'chrome_debug_secure': False,
        'recommendations': []
    }
    
    try:
        # Check if secure storage is available
        storage = SecureBrowserStorage()
        results['secure_storage_available'] = True
        
        # Check for plaintext session files
        common_session_paths = [
            './data/browser_profile/session.json',
            './data/session.json',
            './session.json',
            './data/cookies.json'
        ]
        
        for path in common_session_paths:
            if os.path.exists(path):
                results['plaintext_sessions_found'].append(path)
        
        # Check for encrypted sessions
        if storage.storage.storage_exists():
            results['encrypted_sessions_found'] = storage.list_sessions()
        
        # Check Chrome debug port security
        try:
            import requests
            response = requests.get("http://localhost:9222/json/list", timeout=2)
            if response.status_code == 200:
                results['chrome_debug_secure'] = False
                results['recommendations'].append("Chrome debug port is unsecured")
            else:
                results['chrome_debug_secure'] = True
        except:
            results['chrome_debug_secure'] = True
        
        # Generate recommendations
        if results['plaintext_sessions_found']:
            results['recommendations'].append("Encrypt plaintext session files immediately")
        
        if not results['encrypted_sessions_found']:
            results['recommendations'].append("No encrypted sessions found - consider setting up secure storage")
        
    except Exception as e:
        results['error'] = str(e)
    
    return results


if __name__ == "__main__":
    # Quick test/demo
    print("🔒 SecureBrowserStorage Demo")
    
    # Run security validation
    security_results = validate_browser_security()
    print(f"\n📊 Security Assessment:")
    print(f"   • Secure storage available: {security_results['secure_storage_available']}")
    print(f"   • Plaintext sessions found: {len(security_results['plaintext_sessions_found'])}")
    print(f"   • Encrypted sessions found: {len(security_results['encrypted_sessions_found'])}")
    print(f"   • Chrome debug secure: {security_results['chrome_debug_secure']}")
    
    if security_results['recommendations']:
        print(f"\n⚠️ Security Recommendations:")
        for rec in security_results['recommendations']:
            print(f"   • {rec}")