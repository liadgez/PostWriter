#!/usr/bin/env python3
"""
Unit tests for PostWriter security storage modules
Tests encryption, secure storage, and browser session management
"""

import os
import tempfile
import json
import pytest
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.postwriter.security.storage import SecureStorage
from src.postwriter.security.browser_storage import SecureBrowserStorage, ChromeSessionManager
from src.postwriter.utils.exceptions import SecurityError


class TestSecureStorage:
    """Test suite for SecureStorage class"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.test_dir, 'test_storage.enc')
        self.password = "test_password_123"
        self.storage = SecureStorage(self.storage_path)
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_get_or_create_salt(self):
        """Test salt generation and persistence"""
        # First call should create salt
        salt1 = self.storage._get_or_create_salt()
        
        # Second call should return same salt (persistence)
        salt2 = self.storage._get_or_create_salt()
        
        assert len(salt1) == 16  # Salt length from implementation
        assert salt1 == salt2  # Should be same (persisted)
        
        # Different storage should have different salt
        storage2 = SecureStorage(os.path.join(self.test_dir, 'storage2.enc'))
        salt3 = storage2._get_or_create_salt()
        assert salt1 != salt3  # Should be unique
    
    def test_derive_key(self):
        """Test key derivation from password"""
        salt = self.storage._get_or_create_salt()
        key1 = self.storage._derive_key(self.password, salt)
        key2 = self.storage._derive_key(self.password, salt)
        
        assert len(key1) == 44  # Base64 encoded 32-byte key
        assert key1 == key2  # Same password + salt = same key
        
        # Different salt should produce different key
        different_salt = os.urandom(16)
        key3 = self.storage._derive_key(self.password, different_salt)
        assert key1 != key3
    
    def test_encrypt_decrypt_cycle(self):
        """Test full encryption/decryption cycle"""
        test_data = {
            "username": "test_user",
            "tokens": ["token1", "token2"],
            "settings": {"enabled": True, "count": 42}
        }
        
        # Store data
        success = self.storage.store_data(test_data, self.password)
        assert success is True
        assert os.path.exists(self.storage_path)
        
        # Load data
        loaded_data = self.storage.load_data(self.password)
        assert loaded_data == test_data
    
    def test_wrong_password(self):
        """Test that wrong password fails to decrypt"""
        test_data = {"secret": "classified"}
        
        self.storage.store_data(test_data, self.password)
        
        # Try with wrong password
        with pytest.raises(SecurityError):
            self.storage.load_data("wrong_password")
    
    def test_corrupted_data(self):
        """Test handling of corrupted encrypted data"""
        test_data = {"test": "data"}
        self.storage.store_data(test_data, self.password)
        
        # Corrupt the file
        with open(self.storage_path, 'r+b') as f:
            f.seek(10)
            f.write(b'corrupted')
        
        with pytest.raises(SecurityError):
            self.storage.load_data(self.password)
    
    def test_storage_exists(self):
        """Test storage existence check"""
        assert not self.storage.storage_exists()
        
        self.storage.store_data({"test": "data"}, self.password)
        assert self.storage.storage_exists()
    
    def test_delete_storage(self):
        """Test storage deletion"""
        self.storage.store_data({"test": "data"}, self.password)
        assert self.storage.storage_exists()
        
        success = self.storage.delete_storage()
        assert success is True
        assert not self.storage.storage_exists()
    
    def test_cookie_storage(self):
        """Test cookie-specific storage methods"""
        cookies = {
            "session_id": "abc123",
            "auth_token": "xyz789",
            "user_pref": "dark_mode"
        }
        
        success = self.storage.store_cookies(cookies, self.password)
        assert success is True
        
        loaded_cookies = self.storage.load_cookies(self.password)
        assert loaded_cookies == cookies
    
    def test_large_data_storage(self):
        """Test storage of large data sets"""
        # Create large test data (simulate large session data)
        large_data = {
            "cookies": [{"name": f"cookie_{i}", "value": f"value_{i}" * 100} for i in range(1000)],
            "localStorage": {f"key_{i}": f"value_{i}" * 50 for i in range(500)},
            "metadata": {"timestamp": "2024-01-01", "user": "test"}
        }
        
        success = self.storage.store_data(large_data, self.password)
        assert success is True
        
        loaded_data = self.storage.load_data(self.password)
        assert loaded_data == large_data
        assert len(loaded_data["cookies"]) == 1000
        assert len(loaded_data["localStorage"]) == 500


class TestSecureBrowserStorage:
    """Test suite for SecureBrowserStorage class"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        config = {'directories': {'logs_dir': self.test_dir}}
        self.browser_storage = SecureBrowserStorage(config)
        self.session_name = "test_session"
        self.password = "test_password_123"
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_save_and_load_session_data(self):
        """Test saving and loading session data"""
        session_data = {
            "cookies": [
                {"name": "sessionid", "value": "abc123", "domain": ".facebook.com"},
                {"name": "datr", "value": "xyz789", "domain": ".facebook.com"}
            ],
            "origins": [
                {
                    "origin": "https://facebook.com",
                    "localStorage": [
                        {"name": "user_pref", "value": "dark_mode"}
                    ]
                }
            ]
        }
        
        # Save session data
        success = self.browser_storage.save_session_data(
            session_data, self.session_name, self.password
        )
        assert success is True
        
        # Load session data
        loaded_data = self.browser_storage.load_session_data(
            self.session_name, self.password
        )
        assert loaded_data == session_data
    
    def test_list_sessions(self):
        """Test listing available sessions"""
        # Create multiple sessions
        session_data = {"cookies": []}
        
        self.browser_storage.save_session_data(session_data, "session1", self.password)
        self.browser_storage.save_session_data(session_data, "session2", self.password)
        self.browser_storage.save_session_data(session_data, "session3", self.password)
        
        sessions = self.browser_storage.list_sessions()
        assert len(sessions) == 3
        assert "session1" in sessions
        assert "session2" in sessions  
        assert "session3" in sessions
    
    def test_delete_session(self):
        """Test session deletion"""
        session_data = {"cookies": []}
        self.browser_storage.save_session_data(session_data, self.session_name, self.password)
        
        assert self.session_name in self.browser_storage.list_sessions()
        
        success = self.browser_storage.delete_session(self.session_name, confirm=False)
        assert success is True
        assert self.session_name not in self.browser_storage.list_sessions()
    
    def test_encrypt_existing_session_file(self):
        """Test encrypting existing plaintext session file"""
        # Create a plaintext session file
        plaintext_session = {
            "cookies": [
                {"name": "test_cookie", "value": "test_value", "domain": ".example.com"}
            ]
        }
        
        plaintext_file = os.path.join(self.test_dir, "session.json")
        with open(plaintext_file, 'w') as f:
            json.dump(plaintext_session, f)
        
        # Encrypt the file
        success = self.browser_storage.encrypt_existing_session_file(
            plaintext_file, self.session_name, self.password, backup=True
        )
        assert success is True
        
        # Verify backup was created
        backup_file = plaintext_file + ".backup"
        assert os.path.exists(backup_file)
        
        # Verify encrypted session can be loaded
        loaded_data = self.browser_storage.load_session_data(self.session_name, self.password)
        assert loaded_data == plaintext_session
    
    def test_get_session_info(self):
        """Test getting session metadata"""
        session_data = {
            "cookies": [{"name": "test", "value": "data"}],
            "origins": []
        }
        
        self.browser_storage.save_session_data(session_data, self.session_name, self.password)
        
        info = self.browser_storage.get_session_info(self.session_name)
        assert info is not None
        assert info["session_name"] == self.session_name
        assert "created_at" in info
        assert "file_size" in info
        assert info["encrypted"] is True


class TestChromeSessionManager:
    """Test suite for ChromeSessionManager class"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        config = {'directories': {'logs_dir': self.test_dir}}
        self.session_manager = ChromeSessionManager(config)
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @patch('requests.get')
    def test_extract_chrome_session_success(self, mock_get):
        """Test successful Chrome session extraction"""
        # Mock Chrome debugging API responses
        mock_tabs_response = MagicMock()
        mock_tabs_response.status_code = 200
        mock_tabs_response.json.return_value = [
            {
                "id": "1",
                "url": "https://facebook.com/profile",
                "webSocketDebuggerUrl": "ws://localhost:9222/devtools/page/1"
            }
        ]
        
        mock_session_response = MagicMock()
        mock_session_response.status_code = 200
        mock_session_response.json.return_value = {
            "cookies": [
                {"name": "sessionid", "value": "test123", "domain": ".facebook.com"}
            ],
            "origins": [
                {
                    "origin": "https://facebook.com",
                    "localStorage": [
                        {"name": "user_setting", "value": "test_value"}
                    ]
                }
            ]
        }
        
        mock_get.side_effect = [mock_tabs_response, mock_session_response]
        
        session_data = self.session_manager.extract_chrome_session()
        
        assert session_data is not None
        assert "cookies" in session_data
        assert "origins" in session_data
        assert len(session_data["cookies"]) == 1
        assert session_data["cookies"][0]["name"] == "sessionid"
    
    @patch('requests.get')
    def test_extract_chrome_session_no_facebook_tabs(self, mock_get):
        """Test Chrome session extraction with no Facebook tabs"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": "1", "url": "https://google.com"}
        ]
        
        mock_get.return_value = mock_response
        
        session_data = self.session_manager.extract_chrome_session()
        assert session_data is None
    
    @patch('requests.get')
    def test_extract_chrome_session_connection_error(self, mock_get):
        """Test Chrome session extraction with connection error"""
        mock_get.side_effect = ConnectionError("Chrome not running")
        
        session_data = self.session_manager.extract_chrome_session()
        assert session_data is None
    
    @patch.object(ChromeSessionManager, 'extract_chrome_session')
    def test_extract_and_encrypt_session(self, mock_extract):
        """Test extracting and encrypting Chrome session"""
        # Mock session data
        mock_session_data = {
            "cookies": [{"name": "test", "value": "data", "domain": ".facebook.com"}]
        }
        mock_extract.return_value = mock_session_data
        
        success = self.session_manager.extract_and_encrypt_session("test_session", "password123")
        
        assert success is True
        mock_extract.assert_called_once()
        
        # Verify session was encrypted and stored
        browser_storage = SecureBrowserStorage({'directories': {'logs_dir': self.test_dir}})
        loaded_data = browser_storage.load_session_data("test_session", "password123")
        assert loaded_data == mock_session_data


class TestSecurityIntegration:
    """Integration tests for security modules working together"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config = {'directories': {'logs_dir': self.test_dir}}
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_full_security_workflow(self):
        """Test complete security workflow: extract, encrypt, store, load"""
        # Step 1: Create mock session data (as if extracted from Chrome)
        session_data = {
            "cookies": [
                {"name": "sessionid", "value": "secure123", "domain": ".facebook.com"},
                {"name": "datr", "value": "device456", "domain": ".facebook.com"}
            ],
            "origins": [
                {
                    "origin": "https://facebook.com",
                    "localStorage": [
                        {"name": "user_preferences", "value": "{'theme': 'dark', 'lang': 'en'}"}
                    ]
                }
            ]
        }
        
        # Step 2: Store with encryption
        browser_storage = SecureBrowserStorage(self.config)
        success = browser_storage.save_session_data(session_data, "production_session", "strong_password")
        assert success is True
        
        # Step 3: Verify it's encrypted (file exists but not readable as JSON)
        sessions = browser_storage.list_sessions()
        assert "production_session" in sessions
        
        # Step 4: Load and decrypt
        loaded_data = browser_storage.load_session_data("production_session", "strong_password")
        assert loaded_data == session_data
        
        # Step 5: Verify data integrity
        assert len(loaded_data["cookies"]) == 2
        assert loaded_data["cookies"][0]["name"] == "sessionid"
        assert loaded_data["origins"][0]["origin"] == "https://facebook.com"
    
    def test_password_security(self):
        """Test password security requirements"""
        browser_storage = SecureBrowserStorage(self.config)
        session_data = {"cookies": []}
        
        # Test various password strengths
        passwords_to_test = [
            ("weak", True),  # Should work but not recommended
            ("", False),      # Empty password should fail
            ("very_strong_password_with_numbers_123", True),
            ("🔒💪🛡️", True)  # Unicode passwords should work
        ]
        
        for password, should_succeed in passwords_to_test:
            try:
                success = browser_storage.save_session_data(session_data, f"test_{len(password)}", password)
                if should_succeed:
                    assert success is True
                    # Verify it can be loaded back
                    loaded = browser_storage.load_session_data(f"test_{len(password)}", password)
                    assert loaded == session_data
                else:
                    assert success is False
            except Exception as e:
                if should_succeed:
                    pytest.fail(f"Password '{password}' should have worked but failed: {e}")


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])