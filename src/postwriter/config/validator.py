#!/usr/bin/env python3
"""
Configuration validation for PostWriter
Validates config.yaml structure and required fields
"""

import os
import yaml
import sys
from typing import Dict, List, Any

class ConfigValidationError(Exception):
    """Custom exception for configuration validation errors"""
    pass

class ConfigValidator:
    """Validates PostWriter configuration"""
    
    # Required configuration structure
    REQUIRED_CONFIG = {
        'facebook': {
            'profile_url': str,
            'mobile_profile_url': str,
            'mbasic_profile_url': str,
            'cookies_path': str,
            'use_mobile': bool
        },
        'database': {
            'path': str
        },
        'scraping': {
            'max_posts': int,
            'scroll_delay': (int, float),
            'login_wait_time': int,
            'pre_scrape_delay': int,
            'browser_profile_dir': str,
            'use_existing_chrome': bool,
            'chrome_debug_port': int,
            'pages_to_scrape': int,
            'posts_per_page': int,
            'retry_attempts': int,
            'use_mobile_selectors': bool
        },
        'analysis': {
            'min_engagement': int,
            'max_templates': int
        },
        'generation': {
            'default_variations': int,
            'max_length': int
        },
        'directories': {
            'data_dir': str,
            'raw_posts_dir': str,
            'logs_dir': str
        }
    }
    
    def __init__(self, config_path: str = 'config.yaml'):
        self.config_path = config_path
        self.config = None
        self.errors = []
        self.warnings = []
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            return self.config
        except FileNotFoundError:
            raise ConfigValidationError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ConfigValidationError(f"Invalid YAML in configuration file: {e}")
    
    def validate_structure(self) -> bool:
        """Validate configuration structure against required schema"""
        if not self.config:
            self.load_config()
        
        return self._validate_section(self.config, self.REQUIRED_CONFIG, "")
    
    def _validate_section(self, config: Dict, required: Dict, path: str) -> bool:
        """Recursively validate configuration section"""
        valid = True
        
        for key, expected_type in required.items():
            current_path = f"{path}.{key}" if path else key
            
            if key not in config:
                self.errors.append(f"Missing required configuration: {current_path}")
                valid = False
                continue
            
            value = config[key]
            
            if isinstance(expected_type, dict):
                # Nested configuration section
                if not isinstance(value, dict):
                    self.errors.append(f"Configuration '{current_path}' must be a dictionary")
                    valid = False
                else:
                    valid &= self._validate_section(value, expected_type, current_path)
            else:
                # Type validation
                if isinstance(expected_type, tuple):
                    # Multiple allowed types
                    if not isinstance(value, expected_type):
                        self.errors.append(f"Configuration '{current_path}' must be one of types: {expected_type}")
                        valid = False
                else:
                    # Single type
                    if not isinstance(value, expected_type):
                        self.errors.append(f"Configuration '{current_path}' must be of type: {expected_type.__name__}")
                        valid = False
        
        return valid
    
    def validate_paths(self) -> bool:
        """Validate file and directory paths"""
        valid = True
        
        if not self.config:
            self.load_config()
        
        # Check if Facebook URLs are valid
        facebook_config = self.config.get('facebook', {})
        profile_url = facebook_config.get('profile_url', '')
        
        if profile_url and not profile_url.startswith('https://'):
            self.errors.append("Facebook profile URL must start with 'https://'")
            valid = False
        
        if 'facebook.com' not in profile_url:
            self.errors.append("Facebook profile URL must contain 'facebook.com'")
            valid = False
        
        # Check database path directory exists
        db_path = self.config.get('database', {}).get('path', '')
        if db_path:
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                self.warnings.append(f"Database directory does not exist: {db_dir}")
        
        # Check cookies path directory exists
        cookies_path = facebook_config.get('cookies_path', '')
        if cookies_path:
            cookies_dir = os.path.dirname(cookies_path)
            if cookies_dir and not os.path.exists(cookies_dir):
                self.warnings.append(f"Cookies directory does not exist: {cookies_dir}")
        
        return valid
    
    def validate_values(self) -> bool:
        """Validate configuration values are reasonable"""
        valid = True
        
        if not self.config:
            self.load_config()
        
        scraping_config = self.config.get('scraping', {})
        
        # Check reasonable limits
        max_posts = scraping_config.get('max_posts', 0)
        if max_posts > 10000:
            self.warnings.append(f"max_posts ({max_posts}) is very high - this may take a long time")
        
        if max_posts <= 0:
            self.errors.append("max_posts must be greater than 0")
            valid = False
        
        # Check Chrome debug port
        chrome_port = scraping_config.get('chrome_debug_port', 9222)
        if not (1024 <= chrome_port <= 65535):
            self.errors.append(f"chrome_debug_port ({chrome_port}) must be between 1024 and 65535")
            valid = False
        
        # Check generation config
        generation_config = self.config.get('generation', {})
        max_length = generation_config.get('max_length', 0)
        if max_length > 100000:
            self.warnings.append(f"max_length ({max_length}) is very high")
        
        if max_length <= 0:
            self.errors.append("generation.max_length must be greater than 0")
            valid = False
        
        return valid
    
    def create_directories(self) -> bool:
        """Create required directories if they don't exist"""
        try:
            if not self.config:
                self.load_config()
            
            directories = self.config.get('directories', {})
            
            for dir_key, dir_path in directories.items():
                if dir_path and not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
                    print(f"✅ Created directory: {dir_path}")
            
            # Also create parent directories for database and cookies
            db_path = self.config.get('database', {}).get('path', '')
            if db_path:
                db_dir = os.path.dirname(db_path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                    print(f"✅ Created database directory: {db_dir}")
            
            cookies_path = self.config.get('facebook', {}).get('cookies_path', '')
            if cookies_path:
                cookies_dir = os.path.dirname(cookies_path)
                if cookies_dir and not os.path.exists(cookies_dir):
                    os.makedirs(cookies_dir, exist_ok=True)
                    print(f"✅ Created cookies directory: {cookies_dir}")
            
            return True
        except Exception as e:
            self.errors.append(f"Failed to create directories: {e}")
            return False
    
    def validate_all(self, create_dirs: bool = True) -> bool:
        """Run all validation checks"""
        try:
            self.load_config()
        except ConfigValidationError as e:
            print(f"❌ Configuration Error: {e}")
            return False
        
        # Run all validations
        structure_valid = self.validate_structure()
        paths_valid = self.validate_paths()
        values_valid = self.validate_values()
        
        if create_dirs:
            self.create_directories()
        
        # Report results
        if self.errors:
            print("❌ Configuration Validation Errors:")
            for error in self.errors:
                print(f"   • {error}")
        
        if self.warnings:
            print("⚠️  Configuration Warnings:")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        is_valid = structure_valid and paths_valid and values_valid
        
        if is_valid:
            print("✅ Configuration validation passed!")
        else:
            print("❌ Configuration validation failed!")
        
        return is_valid
    
    def get_config(self) -> Dict[str, Any]:
        """Get the validated configuration"""
        if not self.config:
            self.load_config()
        return self.config

def validate_config(config_path: str = 'config.yaml', create_dirs: bool = True) -> bool:
    """Convenience function to validate configuration"""
    validator = ConfigValidator(config_path)
    return validator.validate_all(create_dirs)

def main():
    """Command-line interface for configuration validation"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate PostWriter configuration')
    parser.add_argument('--config', default='config.yaml', help='Path to configuration file')
    parser.add_argument('--no-create-dirs', action='store_true', help='Don\'t create missing directories')
    
    args = parser.parse_args()
    
    success = validate_config(args.config, not args.no_create_dirs)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()