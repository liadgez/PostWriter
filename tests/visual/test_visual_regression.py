#!/usr/bin/env python3
"""
Visual regression tests for PostWriter UI testing system
Tests screenshot comparison, baseline management, and visual validation
"""

import os
import tempfile
import pytest
import json
from unittest.mock import patch, MagicMock
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.postwriter.testing.visual_validator import VisualValidator, ValidationResult, UIElement
from src.postwriter.testing.browser_manager import EnhancedBrowserManager, BrowserEngine


class TestVisualBaselineManagement:
    """Test visual baseline creation and management"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            'testing': {
                'baseline_screenshots': os.path.join(self.test_dir, 'baselines'),
                'similarity_threshold': 0.9,
                'difference_threshold': 5.0
            },
            'directories': {
                'logs_dir': self.test_dir
            }
        }
        self.validator = VisualValidator(self.config)
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @patch('src.postwriter.testing.visual_validator.CV2_AVAILABLE', True)
    @patch('cv2.imread')
    @patch('cv2.imwrite')
    def test_baseline_creation(self, mock_imwrite, mock_imread):
        """Test creating visual baselines"""
        import numpy as np
        
        # Mock image data
        test_image = np.zeros((480, 640, 3), dtype=np.uint8)
        test_image[100:200, 100:200] = [255, 0, 0]  # Red square
        mock_imread.return_value = test_image
        
        # Create test screenshot
        test_screenshot = os.path.join(self.test_dir, 'test_page.png')
        with open(test_screenshot, 'wb') as f:
            f.write(b'fake_image_data')
        
        # Create baseline
        success = self.validator.create_baseline(test_screenshot, 'facebook_login')
        assert success is True
        
        # Verify baseline files were created
        baseline_path = os.path.join(self.config['testing']['baseline_screenshots'], 'facebook_login.png')
        metadata_path = os.path.join(self.config['testing']['baseline_screenshots'], 'facebook_login.json')
        
        assert os.path.exists(baseline_path)
        assert os.path.exists(metadata_path)
        
        # Verify metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        assert metadata['baseline_name'] == 'facebook_login'
        assert metadata['original_path'] == test_screenshot
        assert 'created' in metadata
    
    @patch('src.postwriter.testing.visual_validator.CV2_AVAILABLE', True)
    @patch('src.postwriter.testing.visual_validator.SKIMAGE_AVAILABLE', True)
    @patch('cv2.imread')
    @patch('cv2.imwrite')
    @patch('src.postwriter.testing.visual_validator.ssim')
    def test_screenshot_comparison_identical(self, mock_ssim, mock_imwrite, mock_imread):
        """Test comparing identical screenshots"""
        import numpy as np
        
        # Mock identical images
        test_image = np.zeros((480, 640, 3), dtype=np.uint8)
        test_image[50:150, 50:150] = [0, 255, 0]  # Green square
        mock_imread.return_value = test_image
        mock_ssim.return_value = 1.0  # Perfect similarity
        
        # Create test files
        current_screenshot = os.path.join(self.test_dir, 'current.png')
        baseline_dir = self.config['testing']['baseline_screenshots']
        os.makedirs(baseline_dir, exist_ok=True)
        baseline_screenshot = os.path.join(baseline_dir, 'test_baseline.png')
        
        with open(current_screenshot, 'wb') as f:
            f.write(b'fake_current_image')
        with open(baseline_screenshot, 'wb') as f:
            f.write(b'fake_baseline_image')
        
        # Compare screenshots
        comparison = self.validator.compare_screenshots(current_screenshot, 'test_baseline')
        
        assert comparison.result == ValidationResult.PASSED
        assert comparison.similarity_score == 1.0
        assert comparison.difference_percentage == 0.0
        assert comparison.diff_image_path is None  # No diff image for identical images
    
    @patch('src.postwriter.testing.visual_validator.CV2_AVAILABLE', True)
    @patch('src.postwriter.testing.visual_validator.SKIMAGE_AVAILABLE', True)
    @patch('cv2.imread')
    @patch('cv2.imwrite')
    @patch('src.postwriter.testing.visual_validator.ssim')
    def test_screenshot_comparison_different(self, mock_ssim, mock_imwrite, mock_imread):
        """Test comparing different screenshots"""
        import numpy as np
        
        # Mock different images
        baseline_image = np.zeros((480, 640, 3), dtype=np.uint8)
        baseline_image[50:150, 50:150] = [0, 255, 0]  # Green square
        
        current_image = np.zeros((480, 640, 3), dtype=np.uint8)
        current_image[100:200, 100:200] = [255, 0, 0]  # Red square (different position)
        
        mock_imread.side_effect = [current_image, baseline_image]
        mock_ssim.return_value = 0.75  # 75% similarity
        
        # Create test files
        current_screenshot = os.path.join(self.test_dir, 'current.png')
        baseline_dir = self.config['testing']['baseline_screenshots']
        os.makedirs(baseline_dir, exist_ok=True)
        baseline_screenshot = os.path.join(baseline_dir, 'test_baseline.png')
        
        with open(current_screenshot, 'wb') as f:
            f.write(b'fake_current_image')
        with open(baseline_screenshot, 'wb') as f:
            f.write(b'fake_baseline_image')
        
        # Compare screenshots
        comparison = self.validator.compare_screenshots(current_screenshot, 'test_baseline')
        
        assert comparison.result == ValidationResult.FAILED  # Below 0.9 threshold
        assert comparison.similarity_score == 0.75
        assert comparison.difference_percentage > 0
        assert comparison.diff_image_path is not None  # Should generate diff image
    
    def test_baseline_creation_without_opencv(self):
        """Test baseline creation when OpenCV is not available"""
        with patch('src.postwriter.testing.visual_validator.CV2_AVAILABLE', False):
            validator = VisualValidator(self.config)
            
            # Create test screenshot
            test_screenshot = os.path.join(self.test_dir, 'test_page.png')
            with open(test_screenshot, 'wb') as f:
                f.write(b'fake_image_data')
            
            # Create baseline should still work (just copies file)
            success = validator.create_baseline(test_screenshot, 'no_opencv_test')
            assert success is True
            
            # But comparison should return error
            comparison = validator.compare_screenshots(test_screenshot, 'no_opencv_test')
            assert comparison.result == ValidationResult.ERROR


class TestUIElementDetection:
    """Test UI element detection in screenshots"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            'testing': {
                'baseline_screenshots': os.path.join(self.test_dir, 'baselines'),
                'similarity_threshold': 0.9
            },
            'directories': {
                'logs_dir': self.test_dir
            }
        }
        self.validator = VisualValidator(self.config)
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_text_based_ui_detection(self):
        """Test UI element detection based on page text"""
        # Test different Facebook page scenarios
        test_scenarios = [
            # Login page
            {
                'page_source': '<html><body><h1>Log into Facebook</h1><input type="email" placeholder="Email or phone"><input type="password" placeholder="Password"><a href="/recover">Forgotten password?</a></body></html>',
                'expected_elements': [UIElement.LOGIN_FORM]
            },
            # CAPTCHA page
            {
                'page_source': '<html><body><div>Security check required</div><p>Please confirm you\'re human by completing this verification</p></body></html>',
                'expected_elements': [UIElement.CAPTCHA]
            },
            # Rate limited page
            {
                'page_source': '<html><body><div class="error">Rate limit exceeded</div><p>Too many requests. Please try again later.</p></body></html>',
                'expected_elements': [UIElement.RATE_LIMIT_MESSAGE]
            },
            # Error page
            {
                'page_source': '<html><body><h1>Something went wrong</h1><p>An error occurred while processing your request</p></body></html>',
                'expected_elements': [UIElement.ERROR_MESSAGE]
            },
            # Blocked account
            {
                'page_source': '<html><body><div>Your account has been restricted</div><p>You have violated our community standards</p></body></html>',
                'expected_elements': [UIElement.BLOCKED_MESSAGE]
            },
            # Two-factor auth
            {
                'page_source': '<html><body><h2>Two-factor authentication required</h2><p>Enter the security code sent to your device</p><input type="text" placeholder="Enter code"></body></html>',
                'expected_elements': [UIElement.TWO_FACTOR_AUTH]
            }
        ]
        
        # Create dummy screenshot
        test_screenshot = os.path.join(self.test_dir, 'test.png')
        with open(test_screenshot, 'wb') as f:
            f.write(b'fake_image')
        
        for scenario in test_scenarios:
            detections = self.validator.detect_ui_elements(test_screenshot, scenario['page_source'])
            
            # Check that expected elements were detected
            detected_elements = {d.element for d in detections if d.detected and d.confidence > 0.5}
            
            for expected_element in scenario['expected_elements']:
                assert expected_element in detected_elements, f"Failed to detect {expected_element} in scenario with page source: {scenario['page_source'][:100]}..."
    
    @patch('src.postwriter.testing.visual_validator.CV2_AVAILABLE', True)
    @patch('cv2.imread')
    @patch('cv2.HoughCircles')
    @patch('cv2.findContours')
    def test_visual_ui_detection(self, mock_find_contours, mock_hough_circles, mock_imread):
        """Test visual UI element detection"""
        import numpy as np
        
        # Mock image
        test_image = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_imread.return_value = test_image
        
        # Mock circular pattern detection (loading spinner)
        mock_circles = np.array([[[100, 100, 20]]])  # One circle at (100,100) with radius 20
        mock_hough_circles.return_value = mock_circles
        
        # Mock color region detection (Facebook blue navigation)
        mock_contours = [
            np.array([[10, 10], [50, 10], [50, 30], [10, 30]]),  # Rectangle contour
            np.array([[100, 100], [200, 100], [200, 150], [100, 150]])  # Another rectangle
        ]
        mock_find_contours.return_value = (mock_contours, None)
        
        # Create test screenshot
        test_screenshot = os.path.join(self.test_dir, 'visual_test.png')
        with open(test_screenshot, 'wb') as f:
            f.write(b'fake_image')
        
        # Detect UI elements
        detections = self.validator.detect_ui_elements(test_screenshot, "")
        
        # Should detect loading spinner and navigation elements
        detected_elements = {d.element for d in detections if d.detected}
        
        assert UIElement.LOADING_SPINNER in detected_elements
        assert UIElement.NAVIGATION_BAR in detected_elements
    
    def test_page_state_validation(self):
        """Test page state validation against expected states"""
        # Create test screenshot
        test_screenshot = os.path.join(self.test_dir, 'state_test.png')
        with open(test_screenshot, 'wb') as f:
            f.write(b'fake_image')
        
        # Test scenarios for different page states
        test_cases = [
            {
                'page_source': '<html><body><nav class="fb-nav">Facebook</nav><div class="home-feed">Welcome home</div></body></html>',
                'expected_state': 'logged_in',
                'should_pass': True
            },
            {
                'page_source': '<html><body><h1>Log into Facebook</h1><form><input type="email"><input type="password"></form></body></html>',
                'expected_state': 'login_required', 
                'should_pass': True
            },
            {
                'page_source': '<html><body><div class="error">Something went wrong</div></body></html>',
                'expected_state': 'error',
                'should_pass': True
            },
            {
                'page_source': '<html><body><nav class="fb-nav">Facebook</nav></body></html>',
                'expected_state': 'login_required',  # Has nav but no login form
                'should_pass': False
            }
        ]
        
        for test_case in test_cases:
            result = self.validator.validate_page_state(
                test_screenshot, 
                test_case['page_source'], 
                test_case['expected_state']
            )
            
            if test_case['should_pass']:
                assert result in [ValidationResult.PASSED, ValidationResult.WARNING], f"Failed validation for {test_case['expected_state']}"
            else:
                assert result in [ValidationResult.FAILED, ValidationResult.WARNING], f"Should have failed validation for {test_case['expected_state']}"


class TestVisualRegressionWorkflows:
    """Test complete visual regression workflows"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            'testing': {
                'baseline_screenshots': os.path.join(self.test_dir, 'baselines'),
                'similarity_threshold': 0.85,
                'difference_threshold': 10.0
            },
            'directories': {
                'logs_dir': self.test_dir
            }
        }
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_browser_visual_testing_workflow(self):
        """Test complete browser automation + visual testing workflow"""
        browser_manager = EnhancedBrowserManager(self.config, BrowserEngine.SELENIUM)
        validator = VisualValidator(self.config)
        
        # Mock browser operations
        with patch('selenium.webdriver.Chrome') as mock_chrome:
            mock_driver = MagicMock()
            mock_driver.save_screenshot = MagicMock(return_value=True)
            mock_driver.current_url = "https://facebook.com"
            mock_driver.page_source = "<html><body>Facebook Login</body></html>"
            mock_chrome.return_value = mock_driver
            
            # Initialize browser
            await browser_manager.initialize()
            
            # Step 1: Navigate and capture baseline
            await browser_manager.navigate_to_url("https://facebook.com/login")
            screenshot_path = await browser_manager.take_screenshot("facebook_login_test.png")
            
            # Create baseline
            baseline_created = validator.create_baseline(screenshot_path, "facebook_login_baseline")
            assert baseline_created is True
            
            # Step 2: Simulate UI change and capture new screenshot
            mock_driver.page_source = "<html><body>Facebook Login - Updated UI</body></html>"
            new_screenshot_path = await browser_manager.take_screenshot("facebook_login_updated.png")
            
            # Step 3: Compare with baseline
            with patch('src.postwriter.testing.visual_validator.CV2_AVAILABLE', True), \
                 patch('cv2.imread') as mock_imread, \
                 patch('src.postwriter.testing.visual_validator.ssim') as mock_ssim:
                
                import numpy as np
                # Mock slightly different images
                baseline_img = np.zeros((480, 640, 3), dtype=np.uint8)
                current_img = np.zeros((480, 640, 3), dtype=np.uint8)
                current_img[0:10, 0:10] = [255, 255, 255]  # Small white rectangle difference
                
                mock_imread.side_effect = [current_img, baseline_img]
                mock_ssim.return_value = 0.95  # High similarity but not perfect
                
                comparison = validator.compare_screenshots(new_screenshot_path, "facebook_login_baseline")
                
                # Should pass with high similarity
                assert comparison.result == ValidationResult.PASSED
                assert comparison.similarity_score >= 0.9
    
    def test_visual_regression_report_generation(self):
        """Test generation of comprehensive visual regression reports"""
        validator = VisualValidator(self.config)
        
        # Mock detection results
        from src.postwriter.testing.visual_validator import UIElementDetection, VisualComparison
        
        mock_detections = [
            UIElementDetection(UIElement.LOGIN_FORM, True, 0.9, (100, 50, 200, 150)),
            UIElementDetection(UIElement.CAPTCHA, False, 0.1),
            UIElementDetection(UIElement.NAVIGATION_BAR, True, 0.8, (0, 0, 640, 60)),
            UIElementDetection(UIElement.ERROR_MESSAGE, False, 0.0)
        ]
        
        mock_comparisons = [
            VisualComparison(0.95, 150, 10000, 1.5, ValidationResult.PASSED),
            VisualComparison(0.82, 800, 10000, 8.0, ValidationResult.WARNING, "/path/to/diff1.png"),
            VisualComparison(0.65, 2000, 10000, 20.0, ValidationResult.FAILED, "/path/to/diff2.png")
        ]
        
        # Generate report
        report = validator.get_validation_report(mock_detections, mock_comparisons)
        
        # Verify report structure
        assert 'timestamp' in report
        assert 'summary' in report
        assert 'detections' in report
        assert 'comparisons' in report
        
        # Verify summary statistics
        summary = report['summary']
        assert summary['total_detections'] == 4
        assert summary['detected_elements'] == 2  # LOGIN_FORM and NAVIGATION_BAR
        assert summary['total_comparisons'] == 3
        assert summary['passed_comparisons'] == 1
        assert summary['failed_comparisons'] == 1
        
        # Verify detection details
        detection_details = report['detections']
        assert len(detection_details) == 4
        
        login_form_detection = next((d for d in detection_details if d['element'] == 'login_form'), None)
        assert login_form_detection is not None
        assert login_form_detection['detected'] is True
        assert login_form_detection['confidence'] == 0.9
        assert login_form_detection['bounding_box'] == (100, 50, 200, 150)
        
        # Verify comparison details
        comparison_details = report['comparisons']
        assert len(comparison_details) == 3
        
        failed_comparison = next((c for c in comparison_details if c['result'] == 'failed'), None)
        assert failed_comparison is not None
        assert failed_comparison['similarity_score'] == 0.65
        assert failed_comparison['difference_percentage'] == 20.0
        assert failed_comparison['diff_image_path'] == "/path/to/diff2.png"
    
    def test_visual_testing_error_handling(self):
        """Test error handling in visual testing workflows"""
        validator = VisualValidator(self.config)
        
        # Test missing screenshot file
        comparison = validator.compare_screenshots("/nonexistent/path.png", "baseline")
        assert comparison.result == ValidationResult.ERROR
        
        # Test missing baseline
        test_screenshot = os.path.join(self.test_dir, 'test.png')
        with open(test_screenshot, 'wb') as f:
            f.write(b'fake_image')
        
        # Should create baseline if it doesn't exist
        comparison = validator.compare_screenshots(test_screenshot, "new_baseline")
        assert comparison.result == ValidationResult.PASSED  # Creates baseline on first run
        
        # Test UI detection with missing screenshot
        detections = validator.detect_ui_elements("/nonexistent/screenshot.png", "")
        assert len(detections) == 0  # Should return empty list, not crash
        
        # Test page state validation with invalid state
        result = validator.validate_page_state(test_screenshot, "<html></html>", "invalid_state")
        assert result == ValidationResult.ERROR


class TestVisualTestAutomation:
    """Test automation features for visual testing"""
    
    def setup_method(self):
        """Setup test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            'testing': {
                'baseline_screenshots': os.path.join(self.test_dir, 'baselines'),
                'similarity_threshold': 0.9,
                'difference_threshold': 5.0
            },
            'directories': {
                'logs_dir': self.test_dir
            }
        }
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_baseline_management_automation(self):
        """Test automated baseline management"""
        validator = VisualValidator(self.config)
        baseline_dir = self.config['testing']['baseline_screenshots']
        
        # Create multiple test screenshots
        test_scenarios = [
            'facebook_login',
            'facebook_home',
            'facebook_profile',
            'facebook_messages',
            'facebook_settings'
        ]
        
        created_baselines = []
        for scenario in test_scenarios:
            # Create test screenshot
            screenshot_path = os.path.join(self.test_dir, f'{scenario}.png')
            with open(screenshot_path, 'wb') as f:
                f.write(f'fake_image_data_{scenario}'.encode())
            
            # Create baseline
            success = validator.create_baseline(screenshot_path, scenario)
            if success:
                created_baselines.append(scenario)
        
        # Verify all baselines were created
        assert len(created_baselines) == len(test_scenarios)
        
        # Verify baseline files exist
        for scenario in test_scenarios:
            baseline_file = os.path.join(baseline_dir, f'{scenario}.png')
            metadata_file = os.path.join(baseline_dir, f'{scenario}.json')
            
            assert os.path.exists(baseline_file)
            assert os.path.exists(metadata_file)
            
            # Verify metadata content
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            assert metadata['baseline_name'] == scenario
    
    def test_batch_visual_comparison(self):
        """Test batch processing of visual comparisons"""
        validator = VisualValidator(self.config)
        
        # Setup baselines and test images
        test_cases = [
            ('login_page', 0.98, ValidationResult.PASSED),
            ('home_page', 0.85, ValidationResult.WARNING),
            ('profile_page', 0.70, ValidationResult.FAILED)
        ]
        
        comparison_results = []
        
        with patch('src.postwriter.testing.visual_validator.CV2_AVAILABLE', True), \
             patch('cv2.imread') as mock_imread, \
             patch('src.postwriter.testing.visual_validator.ssim') as mock_ssim:
            
            import numpy as np
            
            for baseline_name, similarity, expected_result in test_cases:
                # Create test files
                current_path = os.path.join(self.test_dir, f'current_{baseline_name}.png')
                baseline_path = os.path.join(self.config['testing']['baseline_screenshots'], f'{baseline_name}.png')
                
                os.makedirs(os.path.dirname(baseline_path), exist_ok=True)
                
                with open(current_path, 'wb') as f:
                    f.write(b'fake_current')
                with open(baseline_path, 'wb') as f:
                    f.write(b'fake_baseline')
                
                # Mock image loading and similarity
                mock_img = np.zeros((480, 640, 3), dtype=np.uint8)
                mock_imread.return_value = mock_img
                mock_ssim.return_value = similarity
                
                # Perform comparison
                comparison = validator.compare_screenshots(current_path, baseline_name)
                comparison_results.append(comparison)
                
                # Verify expected result
                assert comparison.result == expected_result
                assert abs(comparison.similarity_score - similarity) < 0.01
        
        # Verify all comparisons completed
        assert len(comparison_results) == len(test_cases)
        
        # Generate batch report
        from src.postwriter.testing.visual_validator import UIElementDetection
        mock_detections = [UIElementDetection(UIElement.LOGIN_FORM, True, 0.9)]
        
        report = validator.get_validation_report(mock_detections, comparison_results)
        
        # Verify batch report
        assert report['summary']['total_comparisons'] == 3
        assert report['summary']['passed_comparisons'] == 1
        assert report['summary']['failed_comparisons'] == 1


if __name__ == "__main__":
    # Run visual regression tests
    pytest.main([__file__, "-v", "-s"])