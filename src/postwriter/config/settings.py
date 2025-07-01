#!/usr/bin/env python3
"""
PostWriter settings management
Handles configuration loading and environment-specific settings
"""

import os
import yaml
import sys
from typing import Dict, Any, Optional

from .validator import ConfigValidator, ConfigValidationError
from ..utils.exceptions import ConfigurationError


def load_config(config_path: str = "config.yaml", environment: str = None) -> Dict[str, Any]:
    """
    Load and validate configuration from config.yaml
    
    Args:
        config_path: Path to configuration file
        environment: Environment name (development, staging, production)
        
    Returns:
        Dict containing validated configuration
    """
    try:
        # Determine environment
        if environment is None:
            environment = os.getenv('POSTWRITER_ENV', 'development')
        
        # Try environment-specific config first
        env_config_path = f"config/{environment}.yaml"
        if os.path.exists(env_config_path):
            config_path = env_config_path
        
        # Load and validate configuration
        validator = ConfigValidator(config_path)
        
        if not validator.validate_all(create_dirs=True):
            raise ConfigurationError("Configuration validation failed")
        
        config = validator.get_config()
        
        # Add environment metadata
        config['_environment'] = environment
        config['_config_path'] = config_path
        
        return config
        
    except ConfigValidationError as e:
        raise ConfigurationError(f"Configuration validation error: {e}")
    except FileNotFoundError:
        raise ConfigurationError(f"Configuration file not found: {config_path}")
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in configuration: {e}")
    except Exception as e:
        raise ConfigurationError(f"Failed to load configuration: {e}")


def get_environment_config(environment: str) -> Dict[str, Any]:
    """
    Get configuration for specific environment
    
    Args:
        environment: Environment name
        
    Returns:
        Environment-specific configuration
    """
    return load_config(environment=environment)


def validate_production_config(config: Dict[str, Any]) -> bool:
    """
    Validate configuration for production deployment
    
    Args:
        config: Configuration dictionary
        
    Returns:
        True if production-ready
    """
    production_requirements = [
        # Security requirements
        ('security', 'encrypt_sessions', True),
        ('security', 'rate_limiting_enabled', True), 
        ('security', 'secure_chrome_proxy', True),
        
        # Database requirements
        ('database', 'backup_enabled', True),
        ('database', 'encryption_enabled', True),
        
        # Logging requirements
        ('logging', 'security_events', True),
        ('logging', 'audit_trail', True)
    ]
    
    missing_requirements = []
    
    for section, key, required_value in production_requirements:
        if section not in config:
            missing_requirements.append(f"{section} section missing")
            continue
            
        if key not in config[section]:
            missing_requirements.append(f"{section}.{key} missing")
            continue
            
        if config[section][key] != required_value:
            missing_requirements.append(f"{section}.{key} must be {required_value}")
    
    if missing_requirements:
        raise ConfigurationError(
            f"Production configuration requirements not met: {', '.join(missing_requirements)}"
        )
    
    return True


def create_environment_config(environment: str, base_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create environment-specific configuration based on base config
    
    Args:
        environment: Target environment
        base_config: Base configuration to modify
        
    Returns:
        Environment-specific configuration
    """
    config = base_config.copy()
    
    if environment == 'development':
        # Development overrides
        config.setdefault('logging', {})['level'] = 'DEBUG'
        config.setdefault('security', {})['strict_validation'] = False
        config.setdefault('scraping', {})['max_posts'] = 10  # Limit for dev
        
    elif environment == 'staging':
        # Staging overrides
        config.setdefault('logging', {})['level'] = 'INFO'
        config.setdefault('security', {})['strict_validation'] = True
        config.setdefault('scraping', {})['max_posts'] = 50
        
    elif environment == 'production':
        # Production overrides
        config.setdefault('logging', {})['level'] = 'WARNING'
        config.setdefault('security', {})['strict_validation'] = True
        config.setdefault('security', {})['encrypt_sessions'] = True
        config.setdefault('security', {})['rate_limiting_enabled'] = True
        config.setdefault('scraping', {})['max_requests_per_minute'] = 15  # Conservative
        
        # Validate production requirements
        validate_production_config(config)
    
    config['_environment'] = environment
    return config