#!/usr/bin/env python3
"""
PostWriter - Production-Ready Entry Point
Main CLI entry point using the new modular structure
"""

import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run the new CLI
from postwriter.cli.main import main

if __name__ == '__main__':
    sys.exit(main())