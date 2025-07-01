#!/usr/bin/env python3
"""
Visual regression tests package for PostWriter
Tests screenshot comparison, UI detection, and visual validation
"""

from .test_visual_regression import *

__all__ = [
    'TestVisualBaselineManagement',
    'TestUIElementDetection',
    'TestVisualRegressionWorkflows',
    'TestVisualTestAutomation'
]