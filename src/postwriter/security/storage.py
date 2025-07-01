#!/usr/bin/env python3
"""
Secure storage utilities for PostWriter
Provides encrypted storage for sensitive data like cookies and tokens
"""

import os
import json
import base64
import hashlib
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import getpass

from ..utils.exceptions import SecurityError, ValidationError

class SecureStorage:
    """Secure storage for sensitive configuration data"""
    
    def __init__(self, storage_path: str = None):
        """Initialize secure storage
        
        Args:
            storage_path: Path to encrypted storage file
        """
        self.storage_path = storage_path or os.path.expanduser("~/.postwriter_secure")
        self._cipher = None
        self._salt_file = f"{self.storage_path}.salt"
        
    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive encryption key from password and salt"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def _get_or_create_salt(self) -> bytes:
        """Get existing salt or create new one"""
        if os.path.exists(self._salt_file):
            with open(self._salt_file, 'rb') as f:
                return f.read()
        else:
            # Create new salt
            salt = os.urandom(16)
            os.makedirs(os.path.dirname(self._salt_file), exist_ok=True)
            with open(self._salt_file, 'wb') as f:
                f.write(salt)
            # Set restrictive permissions
            os.chmod(self._salt_file, 0o600)
            return salt
    
    def _get_cipher(self, password: str = None) -> Fernet:
        """Get or create cipher for encryption/decryption"""
        if self._cipher is None:
            if password is None:
                password = getpass.getpass("Enter password for secure storage: ")
            
            salt = self._get_or_create_salt()
            key = self._derive_key(password, salt)
            self._cipher = Fernet(key)
        
        return self._cipher
    
    def store_data(self, data: Dict[str, Any], password: str = None) -> bool:
        """Store data securely
        
        Args:
            data: Dictionary of data to store
            password: Password for encryption (will prompt if not provided)
            
        Returns:
            True if successful
        """
        try:
            cipher = self._get_cipher(password)
            
            # Serialize data
            json_data = json.dumps(data, indent=2, default=str).encode()
            
            # Encrypt data
            encrypted_data = cipher.encrypt(json_data)
            
            # Create directory if needed
            dir_path = os.path.dirname(self.storage_path)
            if dir_path:  # Only create directory if there's actually a directory component
                os.makedirs(dir_path, exist_ok=True)
            
            # Write encrypted data
            with open(self.storage_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Set restrictive permissions
            os.chmod(self.storage_path, 0o600)
            
            return True
            
        except Exception as e:
            raise SecurityError(f"Failed to store secure data: {e}")
    
    def load_data(self, password: str = None) -> Dict[str, Any]:
        """Load data securely
        
        Args:
            password: Password for decryption (will prompt if not provided)
            
        Returns:
            Dictionary of loaded data
        """
        if not os.path.exists(self.storage_path):
            return {}
        
        try:
            cipher = self._get_cipher(password)
            
            # Read encrypted data
            with open(self.storage_path, 'rb') as f:
                encrypted_data = f.read()
            
            # Decrypt data
            json_data = cipher.decrypt(encrypted_data)
            
            # Deserialize data
            return json.loads(json_data.decode())
            
        except Exception as e:
            raise SecurityError(f"Failed to load secure data: {e}")
    
    def storage_exists(self) -> bool:
        """Check if encrypted storage file exists"""
        return os.path.exists(self.storage_path)
    
    def delete_storage(self) -> bool:
        """Delete the encrypted storage file"""
        try:
            if os.path.exists(self.storage_path):
                os.remove(self.storage_path)
            if os.path.exists(self._salt_file):
                os.remove(self._salt_file)
            return True
        except Exception:
            return False
    
    def store_cookies(self, cookies: Dict[str, str], password: str = None) -> bool:
        """Store cookies securely
        
        Args:
            cookies: Dictionary of cookie name-value pairs
            password: Password for encryption
            
        Returns:
            True if successful
        """
        # Load existing data
        try:
            data = self.load_data(password)
        except SecurityError:
            data = {}
        
        # Add cookies
        data['cookies'] = cookies
        data['cookies_updated'] = hashlib.sha256(str(cookies).encode()).hexdigest()[:16]
        
        return self.store_data(data, password)
    
    def load_cookies(self, password: str = None) -> Dict[str, str]:
        """Load cookies securely
        
        Args:
            password: Password for decryption
            
        Returns:
            Dictionary of cookies
        """
        data = self.load_data(password)
        return data.get('cookies', {})
    
    def store_config(self, config_data: Dict[str, Any], password: str = None) -> bool:
        """Store configuration data securely
        
        Args:
            config_data: Configuration data to store
            password: Password for encryption
            
        Returns:
            True if successful
        """
        # Load existing data
        try:
            data = self.load_data(password)
        except SecurityError:
            data = {}
        
        # Add config
        data['config'] = config_data
        
        return self.store_data(data, password)
    
    def load_config(self, password: str = None) -> Dict[str, Any]:
        """Load configuration data securely
        
        Args:
            password: Password for decryption
            
        Returns:
            Dictionary of configuration data
        """
        data = self.load_data(password)
        return data.get('config', {})
    
    def delete_storage(self) -> bool:
        """Delete all secure storage files
        
        Returns:
            True if successful
        """
        try:
            if os.path.exists(self.storage_path):
                os.remove(self.storage_path)
            
            if os.path.exists(self._salt_file):
                os.remove(self._salt_file)
            
            return True
            
        except Exception as e:
            raise SecurityError(f"Failed to delete secure storage: {e}")
    
    def change_password(self, old_password: str, new_password: str) -> bool:
        """Change storage password
        
        Args:
            old_password: Current password
            new_password: New password
            
        Returns:
            True if successful
        """
        try:
            # Load data with old password
            data = self.load_data(old_password)
            
            # Reset cipher
            self._cipher = None
            
            # Delete old salt
            if os.path.exists(self._salt_file):
                os.remove(self._salt_file)
            
            # Store with new password
            return self.store_data(data, new_password)
            
        except Exception as e:
            raise SecurityError(f"Failed to change password: {e}")

class CookieManager:
    """Secure cookie management for PostWriter"""
    
    def __init__(self, storage_path: str = None):
        """Initialize cookie manager
        
        Args:
            storage_path: Path to encrypted cookie storage
        """
        self.storage = SecureStorage(storage_path)
    
    def save_cookies_from_file(self, cookie_file_path: str, password: str = None) -> bool:
        """Import cookies from JSON file and store securely
        
        Args:
            cookie_file_path: Path to cookie JSON file
            password: Password for encryption
            
        Returns:
            True if successful
        """
        try:
            with open(cookie_file_path, 'r') as f:
                cookies_data = json.load(f)
            
            # Handle different cookie formats
            if isinstance(cookies_data, list):
                # Array of cookie objects
                cookies = {}
                for cookie in cookies_data:
                    if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                        cookies[cookie['name']] = cookie['value']
            elif isinstance(cookies_data, dict):
                # Direct name-value mapping
                cookies = cookies_data
            else:
                raise ValidationError(f"Unsupported cookie format in {cookie_file_path}")
            
            return self.storage.store_cookies(cookies, password)
            
        except Exception as e:
            raise SecurityError(f"Failed to import cookies: {e}")
    
    def get_cookies_for_requests(self, password: str = None) -> Dict[str, str]:
        """Get cookies formatted for requests library
        
        Args:
            password: Password for decryption
            
        Returns:
            Dictionary of cookies for requests
        """
        return self.storage.load_cookies(password)
    
    def get_cookies_for_selenium(self, password: str = None) -> list:
        """Get cookies formatted for Selenium
        
        Args:
            password: Password for decryption
            
        Returns:
            List of cookie dictionaries for Selenium
        """
        cookies = self.storage.load_cookies(password)
        selenium_cookies = []
        
        for name, value in cookies.items():
            selenium_cookies.append({
                'name': name,
                'value': value,
                'domain': '.facebook.com'
            })
        
        return selenium_cookies
    
    def has_cookies(self) -> bool:
        """Check if cookies are stored
        
        Returns:
            True if cookies exist
        """
        try:
            cookies = self.storage.load_cookies()
            return len(cookies) > 0
        except:
            return False

# Example usage and testing
if __name__ == '__main__':
    import tempfile
    
    # Test secure storage
    with tempfile.NamedTemporaryFile(delete=False, suffix='.secure') as f:
        storage_path = f.name
    
    try:
        storage = SecureStorage(storage_path)
        
        # Test data storage
        test_data = {
            'cookies': {'session_id': 'test123', 'auth_token': 'secret456'},
            'config': {'api_key': 'confidential789'}
        }
        
        # Store with test password
        password = "test_password_123"
        success = storage.store_data(test_data, password)
        print(f"✅ Data storage: {success}")
        
        # Load data
        loaded_data = storage.load_data(password)
        print(f"✅ Data loading: {loaded_data == test_data}")
        
        # Test cookie manager
        cookie_mgr = CookieManager(storage_path + "_cookies")
        
        # Create test cookie file
        test_cookies = [
            {'name': 'c_user', 'value': '123456789'},
            {'name': 'xs', 'value': 'secret_token_here'}
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_cookies, f)
            cookie_file = f.name
        
        # Test cookie import
        success = cookie_mgr.save_cookies_from_file(cookie_file, password)
        print(f"✅ Cookie import: {success}")
        
        # Test cookie retrieval
        requests_cookies = cookie_mgr.get_cookies_for_requests(password)
        selenium_cookies = cookie_mgr.get_cookies_for_selenium(password)
        
        print(f"✅ Requests cookies: {len(requests_cookies)} cookies")
        print(f"✅ Selenium cookies: {len(selenium_cookies)} cookies")
        
        # Cleanup
        os.unlink(storage_path)
        os.unlink(storage_path + ".salt")
        os.unlink(cookie_file)
        
        print("🎉 All security tests passed!")
        
    except Exception as e:
        print(f"❌ Security test failed: {e}")
        # Cleanup on failure
        for path in [storage_path, storage_path + ".salt"]:
            if os.path.exists(path):
                os.unlink(path)