"""
Pytest configuration and shared fixtures
"""
import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for test configurations"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_config():
    """Provide a sample configuration for tests"""
    return {
        'facebook': {
            'profile_url': 'https://facebook.com/test-profile'
        },
        'directories': {
            'data_dir': './test_data',
            'logs_dir': './test_logs'
        },
        'security': {
            'encryption_enabled': True,
            'rate_limiting_enabled': True
        }
    }


@pytest.fixture
def mock_posts():
    """Sample Facebook posts for testing"""
    return [
        {
            'id': '1',
            'content': 'Test post content',
            'engagement': {'likes': 10, 'shares': 5, 'comments': 2},
            'timestamp': '2024-01-01T10:00:00Z'
        },
        {
            'id': '2', 
            'content': 'Another test post',
            'engagement': {'likes': 15, 'shares': 3, 'comments': 7},
            'timestamp': '2024-01-02T15:30:00Z'
        }
    ]