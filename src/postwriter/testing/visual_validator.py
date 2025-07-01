#!/usr/bin/env python3
"""
Visual Validator for PostWriter
Handles screenshot comparison, UI state detection, and visual regression testing
"""

import os
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import re

try:
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    np = None

try:
    from skimage.metrics import structural_similarity as ssim
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False

from ..security.logging import get_secure_logger


class ValidationResult(Enum):
    """Visual validation results"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    ERROR = "error"


class UIElement(Enum):
    """Facebook UI elements to detect"""
    LOGIN_FORM = "login_form"
    CAPTCHA = "captcha"
    RATE_LIMIT_MESSAGE = "rate_limit_message"
    ERROR_MESSAGE = "error_message"
    POST_FEED = "post_feed"
    PROFILE_HEADER = "profile_header"
    NAVIGATION_BAR = "navigation_bar"
    LOADING_SPINNER = "loading_spinner"
    BLOCKED_MESSAGE = "blocked_message"
    TWO_FACTOR_AUTH = "two_factor_auth"


@dataclass
class VisualComparison:
    """Result of visual comparison between two images"""
    similarity_score: float
    difference_pixels: int
    total_pixels: int
    difference_percentage: float
    result: ValidationResult
    diff_image_path: Optional[str] = None
    annotations: List[str] = None
    
    def __post_init__(self):
        if self.annotations is None:
            self.annotations = []


@dataclass
class UIElementDetection:
    """Result of UI element detection"""
    element: UIElement
    detected: bool
    confidence: float
    bounding_box: Optional[Tuple[int, int, int, int]] = None
    additional_data: Dict = None
    
    def __post_init__(self):
        if self.additional_data is None:
            self.additional_data = {}


class VisualValidator:
    """
    Visual validation engine for Facebook scraping UI
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = get_secure_logger("visual_validator")
        
        # Paths
        self.baseline_dir = config.get('testing', {}).get('baseline_screenshots', './baselines')
        self.temp_dir = config.get('directories', {}).get('logs_dir', './logs')
        self.diff_dir = os.path.join(self.temp_dir, 'visual_diffs')
        
        # Validation settings
        self.similarity_threshold = config.get('testing', {}).get('similarity_threshold', 0.95)
        self.difference_threshold = config.get('testing', {}).get('difference_threshold', 5.0)
        
        # Ensure directories exist
        os.makedirs(self.baseline_dir, exist_ok=True)
        os.makedirs(self.diff_dir, exist_ok=True)
        
        # UI detection patterns
        self.ui_patterns = {
            UIElement.LOGIN_FORM: [
                r"log into facebook",
                r"email or phone",
                r"password",
                r"forgotten password",
                r"create new account"
            ],
            UIElement.CAPTCHA: [
                r"security check",
                r"confirm you're human",
                r"captcha",
                r"verify you're not a robot"
            ],
            UIElement.RATE_LIMIT_MESSAGE: [
                r"rate limit",
                r"too many requests",
                r"slow down",
                r"try again later",
                r"temporarily blocked"
            ],
            UIElement.ERROR_MESSAGE: [
                r"something went wrong",
                r"error occurred",
                r"page not found",
                r"content not available"
            ],
            UIElement.BLOCKED_MESSAGE: [
                r"account restricted",
                r"blocked",
                r"suspended",
                r"violated",
                r"community standards"
            ],
            UIElement.TWO_FACTOR_AUTH: [
                r"two-factor authentication",
                r"enter security code",
                r"verify your identity",
                r"authentication required"
            ]
        }
        
        # Color thresholds for different UI states
        self.color_signatures = {
            "facebook_blue": (66, 103, 178),  # Facebook brand blue
            "error_red": (233, 66, 66),       # Error messages
            "warning_yellow": (255, 193, 7),  # Warning messages
            "success_green": (76, 175, 80)    # Success messages
        }
        
        self.logger.info("Visual Validator initialized")

    def compare_screenshots(self, 
                          current_path: str, 
                          baseline_name: str,
                          tolerance: float = None) -> VisualComparison:
        """
        Compare current screenshot with baseline
        """
        if not CV2_AVAILABLE:
            self.logger.error("OpenCV not available for image comparison")
            return VisualComparison(0.0, 0, 0, 100.0, ValidationResult.ERROR)
        
        baseline_path = os.path.join(self.baseline_dir, f"{baseline_name}.png")
        
        # Create baseline if it doesn't exist
        if not os.path.exists(baseline_path):
            self.logger.info(f"Creating baseline: {baseline_path}")
            if os.path.exists(current_path):
                import shutil
                shutil.copy2(current_path, baseline_path)
                return VisualComparison(1.0, 0, 0, 0.0, ValidationResult.PASSED)
        
        if not os.path.exists(current_path):
            self.logger.error(f"Current screenshot not found: {current_path}")
            return VisualComparison(0.0, 0, 0, 100.0, ValidationResult.ERROR)
        
        try:
            # Load images
            current_img = cv2.imread(current_path)
            baseline_img = cv2.imread(baseline_path)
            
            if current_img is None or baseline_img is None:
                self.logger.error("Failed to load images for comparison")
                return VisualComparison(0.0, 0, 0, 100.0, ValidationResult.ERROR)
            
            # Resize images to same size if needed
            if current_img.shape != baseline_img.shape:
                height, width = baseline_img.shape[:2]
                current_img = cv2.resize(current_img, (width, height))
            
            # Calculate similarity
            if SKIMAGE_AVAILABLE:
                similarity_score = ssim(
                    cv2.cvtColor(current_img, cv2.COLOR_BGR2GRAY),
                    cv2.cvtColor(baseline_img, cv2.COLOR_BGR2GRAY)
                )
            else:
                # Fallback to simple pixel difference
                diff = cv2.absdiff(current_img, baseline_img)
                non_zero_count = np.count_nonzero(diff)
                total_pixels = diff.shape[0] * diff.shape[1] * diff.shape[2]
                similarity_score = 1.0 - (non_zero_count / total_pixels)
            
            # Calculate pixel differences
            diff_img = cv2.absdiff(current_img, baseline_img)
            diff_gray = cv2.cvtColor(diff_img, cv2.COLOR_BGR2GRAY)
            diff_pixels = np.count_nonzero(diff_gray > 10)  # Threshold for significant difference
            total_pixels = diff_gray.shape[0] * diff_gray.shape[1]
            diff_percentage = (diff_pixels / total_pixels) * 100
            
            # Generate difference image
            diff_image_path = None
            if diff_percentage > 1.0:  # Only save if significant differences
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                diff_image_path = os.path.join(self.diff_dir, f"{baseline_name}_diff_{timestamp}.png")
                
                # Create annotated difference image
                annotated_diff = self._create_diff_visualization(current_img, baseline_img, diff_img)
                cv2.imwrite(diff_image_path, annotated_diff)
            
            # Determine result
            threshold = tolerance if tolerance is not None else self.similarity_threshold
            if similarity_score >= threshold and diff_percentage <= self.difference_threshold:
                result = ValidationResult.PASSED
            elif similarity_score >= (threshold - 0.1) and diff_percentage <= (self.difference_threshold * 2):
                result = ValidationResult.WARNING
            else:
                result = ValidationResult.FAILED
            
            return VisualComparison(
                similarity_score=similarity_score,
                difference_pixels=diff_pixels,
                total_pixels=total_pixels,
                difference_percentage=diff_percentage,
                result=result,
                diff_image_path=diff_image_path
            )
            
        except Exception as e:
            self.logger.error(f"Screenshot comparison failed: {e}")
            return VisualComparison(0.0, 0, 0, 100.0, ValidationResult.ERROR)

    def _create_diff_visualization(self, current, baseline, diff):
        """Create annotated difference visualization"""
        # Create side-by-side comparison
        height, width = current.shape[:2]
        result = np.zeros((height, width * 3, 3), dtype=np.uint8)
        
        # Place images side by side
        result[:, :width] = baseline  # Baseline on left
        result[:, width:width*2] = current  # Current in middle
        
        # Highlight differences on the right
        diff_highlighted = current.copy()
        diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        diff_mask = diff_gray > 10
        diff_highlighted[diff_mask] = [0, 0, 255]  # Highlight differences in red
        result[:, width*2:] = diff_highlighted
        
        return result

    def detect_ui_elements(self, screenshot_path: str, page_source: str = "") -> List[UIElementDetection]:
        """
        Detect Facebook UI elements in screenshot and page source
        """
        detections = []
        
        if not os.path.exists(screenshot_path):
            self.logger.error(f"Screenshot not found: {screenshot_path}")
            return detections
        
        try:
            # Text-based detection from page source
            if page_source:
                text_detections = self._detect_elements_by_text(page_source)
                detections.extend(text_detections)
            
            # Visual detection from screenshot
            if CV2_AVAILABLE:
                visual_detections = self._detect_elements_by_image(screenshot_path)
                detections.extend(visual_detections)
            
            self.logger.info(f"Detected {len(detections)} UI elements")
            return detections
            
        except Exception as e:
            self.logger.error(f"UI element detection failed: {e}")
            return detections

    def _detect_elements_by_text(self, page_source: str) -> List[UIElementDetection]:
        """Detect UI elements based on text patterns"""
        detections = []
        page_lower = page_source.lower()
        
        for element, patterns in self.ui_patterns.items():
            detected = False
            confidence = 0.0
            
            matches = 0
            for pattern in patterns:
                if re.search(pattern, page_lower, re.IGNORECASE):
                    matches += 1
            
            if matches > 0:
                detected = True
                confidence = min(matches / len(patterns), 1.0)
            
            detections.append(UIElementDetection(
                element=element,
                detected=detected,
                confidence=confidence,
                additional_data={"matches": matches, "total_patterns": len(patterns)}
            ))
        
        return detections

    def _detect_elements_by_image(self, screenshot_path: str) -> List[UIElementDetection]:
        """Detect UI elements based on visual patterns"""
        detections = []
        
        try:
            img = cv2.imread(screenshot_path)
            if img is None:
                return detections
            
            # Convert to different color spaces for analysis
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # Detect loading spinners (circular patterns)
            spinner_detected = self._detect_loading_spinner(img_gray)
            detections.append(UIElementDetection(
                element=UIElement.LOADING_SPINNER,
                detected=spinner_detected,
                confidence=0.8 if spinner_detected else 0.0
            ))
            
            # Detect Facebook blue color signature
            blue_regions = self._detect_color_regions(img, self.color_signatures["facebook_blue"])
            fb_nav_detected = len(blue_regions) > 5  # Multiple blue elements suggest FB navigation
            detections.append(UIElementDetection(
                element=UIElement.NAVIGATION_BAR,
                detected=fb_nav_detected,
                confidence=min(len(blue_regions) / 10.0, 1.0)
            ))
            
            # Detect error states by color
            error_regions = self._detect_color_regions(img, self.color_signatures["error_red"])
            error_detected = len(error_regions) > 0
            detections.append(UIElementDetection(
                element=UIElement.ERROR_MESSAGE,
                detected=error_detected,
                confidence=min(len(error_regions) / 3.0, 1.0)
            ))
            
        except Exception as e:
            self.logger.error(f"Visual element detection failed: {e}")
        
        return detections

    def _detect_loading_spinner(self, img_gray) -> bool:
        """Detect circular loading spinners"""
        try:
            # Use HoughCircles to detect circular patterns
            circles = cv2.HoughCircles(
                img_gray,
                cv2.HOUGH_GRADIENT,
                dp=1,
                minDist=30,
                param1=50,
                param2=30,
                minRadius=10,
                maxRadius=50
            )
            
            return circles is not None and len(circles[0]) > 0
        except:
            return False

    def _detect_color_regions(self, img, target_color: Tuple[int, int, int], tolerance: int = 30) -> List[Tuple]:
        """Detect regions with specific color"""
        try:
            # Convert BGR to RGB for comparison
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Create color mask
            lower = np.array([max(0, c - tolerance) for c in target_color])
            upper = np.array([min(255, c + tolerance) for c in target_color])
            
            mask = cv2.inRange(img_rgb, lower, upper)
            
            # Find contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Return bounding boxes of significant regions
            regions = []
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 100:  # Minimum area threshold
                    x, y, w, h = cv2.boundingRect(contour)
                    regions.append((x, y, w, h))
            
            return regions
        except:
            return []

    def validate_page_state(self, screenshot_path: str, page_source: str, expected_state: str) -> ValidationResult:
        """
        Validate that the page is in the expected state
        """
        try:
            detections = self.detect_ui_elements(screenshot_path, page_source)
            
            # Define state validation rules
            state_rules = {
                "logged_in": {
                    "required": [UIElement.NAVIGATION_BAR],
                    "forbidden": [UIElement.LOGIN_FORM, UIElement.CAPTCHA]
                },
                "login_required": {
                    "required": [UIElement.LOGIN_FORM],
                    "forbidden": [UIElement.NAVIGATION_BAR]
                },
                "profile_page": {
                    "required": [UIElement.PROFILE_HEADER, UIElement.NAVIGATION_BAR],
                    "forbidden": [UIElement.LOGIN_FORM, UIElement.ERROR_MESSAGE]
                },
                "error": {
                    "required": [UIElement.ERROR_MESSAGE],
                    "forbidden": []
                },
                "blocked": {
                    "required": [UIElement.BLOCKED_MESSAGE],
                    "forbidden": []
                }
            }
            
            rules = state_rules.get(expected_state)
            if not rules:
                return ValidationResult.ERROR
            
            # Check required elements
            detected_elements = {d.element for d in detections if d.detected and d.confidence > 0.5}
            
            required_found = all(elem in detected_elements for elem in rules["required"])
            forbidden_found = any(elem in detected_elements for elem in rules["forbidden"])
            
            if required_found and not forbidden_found:
                return ValidationResult.PASSED
            elif required_found or not forbidden_found:
                return ValidationResult.WARNING
            else:
                return ValidationResult.FAILED
                
        except Exception as e:
            self.logger.error(f"Page state validation failed: {e}")
            return ValidationResult.ERROR

    def create_baseline(self, screenshot_path: str, baseline_name: str) -> bool:
        """Create a baseline screenshot for future comparisons"""
        try:
            baseline_path = os.path.join(self.baseline_dir, f"{baseline_name}.png")
            
            if os.path.exists(screenshot_path):
                import shutil
                shutil.copy2(screenshot_path, baseline_path)
                
                # Store metadata
                metadata = {
                    "created": datetime.now().isoformat(),
                    "original_path": screenshot_path,
                    "baseline_name": baseline_name
                }
                
                metadata_path = os.path.join(self.baseline_dir, f"{baseline_name}.json")
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                self.logger.info(f"Baseline created: {baseline_path}")
                return True
            else:
                self.logger.error(f"Source screenshot not found: {screenshot_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to create baseline: {e}")
            return False

    def get_validation_report(self, detections: List[UIElementDetection], comparisons: List[VisualComparison]) -> Dict:
        """Generate comprehensive validation report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_detections": len(detections),
                "detected_elements": len([d for d in detections if d.detected]),
                "total_comparisons": len(comparisons),
                "passed_comparisons": len([c for c in comparisons if c.result == ValidationResult.PASSED]),
                "failed_comparisons": len([c for c in comparisons if c.result == ValidationResult.FAILED])
            },
            "detections": [
                {
                    "element": d.element.value,
                    "detected": d.detected,
                    "confidence": d.confidence,
                    "bounding_box": d.bounding_box,
                    "additional_data": d.additional_data
                }
                for d in detections
            ],
            "comparisons": [
                {
                    "similarity_score": c.similarity_score,
                    "difference_percentage": c.difference_percentage,
                    "result": c.result.value,
                    "diff_image_path": c.diff_image_path
                }
                for c in comparisons
            ]
        }
        
        return report


# Example usage and testing
if __name__ == "__main__":
    def test_visual_validator():
        config = {
            'testing': {
                'baseline_screenshots': './test_baselines',
                'similarity_threshold': 0.9,
                'difference_threshold': 5.0
            },
            'directories': {
                'logs_dir': './test_logs'
            }
        }
        
        validator = VisualValidator(config)
        
        # Test with a dummy screenshot (create a simple test image)
        if CV2_AVAILABLE:
            test_img = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.rectangle(test_img, (50, 50), (200, 150), (255, 0, 0), -1)  # Blue rectangle
            test_path = './test_screenshot.png'
            cv2.imwrite(test_path, test_img)
            
            # Create baseline
            validator.create_baseline(test_path, 'test_page')
            
            # Compare with itself (should be perfect match)
            comparison = validator.compare_screenshots(test_path, 'test_page')
            print(f"Self-comparison result: {comparison.result.value}")
            print(f"Similarity: {comparison.similarity_score:.3f}")
            print(f"Difference: {comparison.difference_percentage:.2f}%")
            
            # Test UI element detection
            detections = validator.detect_ui_elements(test_path, "Login to Facebook")
            print(f"Detected {len(detections)} UI elements")
            
            # Clean up
            os.remove(test_path)
        else:
            print("OpenCV not available, skipping visual tests")
    
    test_visual_validator()