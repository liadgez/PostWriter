#!/usr/bin/env python3
"""
Intelligent Rate Limiter for PostWriter Facebook Scraping
Protects user accounts from being flagged by respecting Facebook's rate limits
"""

import time
import random
import json
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import hashlib

from secure_logging import get_secure_logger
from exceptions import SecurityError


class RequestType(Enum):
    """Types of Facebook requests"""
    PAGE_LOAD = "page_load"
    SCROLL = "scroll"
    CLICK = "click"
    API_CALL = "api_call"
    LOGIN = "login"
    PROFILE_ACCESS = "profile_access"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    # Base delays (seconds)
    min_request_delay: float = 2.0
    max_request_delay: float = 8.0
    
    # Scroll-specific delays
    scroll_delay: float = 3.0
    scroll_delay_variance: float = 1.5
    
    # Page load delays
    page_load_delay: float = 5.0
    page_load_variance: float = 2.0
    
    # Between-post delays
    post_processing_delay: float = 1.5
    post_processing_variance: float = 0.8
    
    # Burst limits
    max_requests_per_minute: int = 20
    max_requests_per_hour: int = 300
    
    # Backoff configuration
    initial_backoff: float = 30.0
    max_backoff: float = 1800.0  # 30 minutes
    backoff_multiplier: float = 2.0
    
    # Rate limit detection
    rate_limit_keywords: List[str] = None
    
    def __post_init__(self):
        if self.rate_limit_keywords is None:
            self.rate_limit_keywords = [
                "rate limit",
                "too many requests",
                "temporarily blocked",
                "please try again later",
                "unusual traffic",
                "verification required",
                "checkpoint",
                "suspicious activity"
            ]


@dataclass
class RequestRecord:
    """Record of a single request"""
    timestamp: datetime
    request_type: RequestType
    url: str
    response_status: Optional[int]
    response_time: float
    success: bool
    rate_limited: bool = False
    error_message: Optional[str] = None


class RateLimitDetector:
    """Detects rate limiting from various signals"""
    
    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.logger = get_secure_logger("rate_limiter")
    
    def analyze_response(self, response_text: str, status_code: int, response_time: float) -> Tuple[bool, str]:
        """
        Analyze response for rate limiting indicators
        
        Args:
            response_text: HTML/text response content
            status_code: HTTP status code
            response_time: Response time in seconds
            
        Returns:
            tuple: (is_rate_limited, reason)
        """
        # Check HTTP status codes
        if status_code in [429, 503, 420]:
            return True, f"HTTP {status_code} - Rate limit status code"
        
        # Check for redirects that might indicate blocking
        if status_code in [302, 301] and response_time < 0.5:
            return True, "Suspicious fast redirect - possible blocking"
        
        # Check response content for rate limiting keywords
        if response_text:
            response_lower = response_text.lower()
            for keyword in self.config.rate_limit_keywords:
                if keyword in response_lower:
                    return True, f"Rate limit keyword detected: {keyword}"
        
        # Check for unusually fast responses (possible cached error pages)
        if response_time < 0.3 and status_code == 200:
            return True, "Unusually fast response - possible cached error"
        
        # Check for empty or minimal content
        if response_text and len(response_text.strip()) < 100:
            return True, "Minimal content - possible error page"
        
        # Check for Facebook-specific blocking indicators
        if response_text:
            facebook_blocks = [
                "temporarily blocked from posting",
                "we limit how often you can post",
                "this feature isn't available right now",
                "please verify your identity",
                "unusual activity on your account"
            ]
            
            for block_indicator in facebook_blocks:
                if block_indicator in response_lower:
                    return True, f"Facebook blocking indicator: {block_indicator}"
        
        return False, "No rate limiting detected"
    
    def analyze_request_pattern(self, recent_requests: List[RequestRecord]) -> Tuple[bool, str]:
        """
        Analyze recent request patterns for rate limiting
        
        Args:
            recent_requests: List of recent request records
            
        Returns:
            tuple: (should_slow_down, reason)
        """
        if not recent_requests:
            return False, "No requests to analyze"
        
        now = datetime.now()
        last_minute = [r for r in recent_requests if (now - r.timestamp).total_seconds() < 60]
        last_hour = [r for r in recent_requests if (now - r.timestamp).total_seconds() < 3600]
        
        # Check burst limits
        if len(last_minute) > self.config.max_requests_per_minute:
            return True, f"Exceeded {self.config.max_requests_per_minute} requests per minute"
        
        if len(last_hour) > self.config.max_requests_per_hour:
            return True, f"Exceeded {self.config.max_requests_per_hour} requests per hour"
        
        # Check for high failure rate
        recent_failures = [r for r in last_minute if not r.success or r.rate_limited]
        if len(last_minute) > 5 and len(recent_failures) / len(last_minute) > 0.3:
            return True, f"High failure rate: {len(recent_failures)}/{len(last_minute)} in last minute"
        
        # Check for consistent rate limiting
        rate_limited_count = sum(1 for r in last_hour if r.rate_limited)
        if rate_limited_count > 3:
            return True, f"Multiple rate limit detections: {rate_limited_count} in last hour"
        
        return False, "Request pattern appears normal"


class IntelligentRateLimiter:
    """Intelligent rate limiter for Facebook scraping"""
    
    def __init__(self, config: RateLimitConfig = None, storage_file: str = None):
        """
        Initialize rate limiter
        
        Args:
            config: Rate limiting configuration
            storage_file: File to persist rate limiting data
        """
        self.config = config or RateLimitConfig()
        self.detector = RateLimitDetector(self.config)
        self.logger = get_secure_logger("rate_limiter")
        
        # Request tracking
        self.request_history: List[RequestRecord] = []
        self.last_request_time: Optional[datetime] = None
        self.current_backoff: float = 0.0
        self.consecutive_failures: int = 0
        
        # Storage
        self.storage_file = storage_file or os.path.expanduser("~/.postwriter_rate_limits")
        self.lock = threading.Lock()
        
        # Load persistent state
        self._load_state()
    
    def wait_for_request(self, request_type: RequestType, url: str = "") -> float:
        """
        Wait appropriate time before making a request
        
        Args:
            request_type: Type of request being made
            url: URL being requested (for logging)
            
        Returns:
            float: Actual wait time in seconds
        """
        with self.lock:
            now = datetime.now()
            
            # Calculate base delay
            base_delay = self._calculate_base_delay(request_type)
            
            # Check if we need backoff
            backoff_delay = self._calculate_backoff_delay()
            
            # Calculate minimum time since last request
            time_since_last = 0.0
            if self.last_request_time:
                time_since_last = (now - self.last_request_time).total_seconds()
            
            # Determine total wait time needed
            min_delay = max(base_delay, backoff_delay)
            wait_time = max(0, min_delay - time_since_last)
            
            # Add random variance to appear more human
            variance = random.uniform(0.8, 1.2)
            wait_time *= variance
            
            # Log rate limiting decision
            self.logger.log_data_operation(
                operation="rate_limit_wait",
                data_type=f"{request_type.value}_request",
                details={
                    "url_hash": hashlib.sha256(url.encode()).hexdigest()[:16] if url else None,
                    "base_delay": base_delay,
                    "backoff_delay": backoff_delay,
                    "time_since_last": time_since_last,
                    "final_wait_time": wait_time,
                    "consecutive_failures": self.consecutive_failures
                }
            )
            
            # Actually wait
            if wait_time > 0:
                self.logger.info(f"⏱️ Rate limiting: waiting {wait_time:.1f}s for {request_type.value}")
                time.sleep(wait_time)
            
            # Update last request time
            self.last_request_time = datetime.now()
            
            return wait_time
    
    def record_request(self, request_type: RequestType, url: str, response_status: Optional[int], 
                      response_text: str = "", response_time: float = 0.0, 
                      error_message: Optional[str] = None) -> bool:
        """
        Record a request and its outcome
        
        Args:
            request_type: Type of request made
            url: URL that was requested
            response_status: HTTP status code
            response_text: Response content
            response_time: Time taken for response
            error_message: Error message if request failed
            
        Returns:
            bool: True if request appears successful, False if rate limited
        """
        with self.lock:
            now = datetime.now()
            
            # Detect rate limiting
            is_rate_limited, rate_limit_reason = self.detector.analyze_response(
                response_text, response_status or 0, response_time
            )
            
            # Determine if request was successful
            success = (response_status is not None and 
                      200 <= response_status < 300 and 
                      not is_rate_limited and 
                      error_message is None)
            
            # Create request record
            record = RequestRecord(
                timestamp=now,
                request_type=request_type,
                url=url,
                response_status=response_status,
                response_time=response_time,
                success=success,
                rate_limited=is_rate_limited,
                error_message=error_message
            )
            
            # Add to history
            self.request_history.append(record)
            
            # Clean old history (keep last 24 hours)
            cutoff = now - timedelta(hours=24)
            self.request_history = [r for r in self.request_history if r.timestamp > cutoff]
            
            # Update failure tracking
            if success:
                self.consecutive_failures = 0
                self.current_backoff = 0.0
            else:
                self.consecutive_failures += 1
                if is_rate_limited:
                    self._increase_backoff()
            
            # Log the request
            self.logger.log_data_operation(
                operation="request_recorded",
                data_type=f"{request_type.value}_request",
                details={
                    "success": success,
                    "rate_limited": is_rate_limited,
                    "rate_limit_reason": rate_limit_reason if is_rate_limited else None,
                    "response_status": response_status,
                    "response_time": response_time,
                    "consecutive_failures": self.consecutive_failures,
                    "url_hash": hashlib.sha256(url.encode()).hexdigest()[:16]
                }
            )
            
            # Log security event for rate limiting
            if is_rate_limited:
                self.logger.log_security_event("rate_limit_detected", {
                    "reason": rate_limit_reason,
                    "request_type": request_type.value,
                    "consecutive_failures": self.consecutive_failures,
                    "current_backoff": self.current_backoff
                })
            
            # Check request patterns
            should_slow_down, pattern_reason = self.detector.analyze_request_pattern(
                self.request_history[-50:]  # Last 50 requests
            )
            
            if should_slow_down:
                self.logger.log_security_event("rate_pattern_warning", {
                    "reason": pattern_reason,
                    "total_requests": len(self.request_history),
                    "recent_failures": self.consecutive_failures
                })
                self._increase_backoff()
            
            # Save state
            self._save_state()
            
            return success and not is_rate_limited
    
    def _calculate_base_delay(self, request_type: RequestType) -> float:
        """Calculate base delay for request type"""
        if request_type == RequestType.SCROLL:
            base = self.config.scroll_delay
            variance = self.config.scroll_delay_variance
        elif request_type == RequestType.PAGE_LOAD:
            base = self.config.page_load_delay
            variance = self.config.page_load_variance
        elif request_type == RequestType.LOGIN:
            base = self.config.max_request_delay  # Be extra careful with login
            variance = 2.0
        else:
            base = random.uniform(self.config.min_request_delay, self.config.max_request_delay)
            variance = 1.0
        
        # Add variance
        return base + random.uniform(-variance, variance)
    
    def _calculate_backoff_delay(self) -> float:
        """Calculate current backoff delay"""
        if self.current_backoff <= 0:
            return 0.0
        
        # Add some randomness to backoff to avoid thundering herd
        variance = random.uniform(0.8, 1.2)
        return self.current_backoff * variance
    
    def _increase_backoff(self):
        """Increase backoff delay due to failures"""
        if self.current_backoff <= 0:
            self.current_backoff = self.config.initial_backoff
        else:
            self.current_backoff = min(
                self.current_backoff * self.config.backoff_multiplier,
                self.config.max_backoff
            )
        
        self.logger.log_security_event("backoff_increased", {
            "new_backoff": self.current_backoff,
            "consecutive_failures": self.consecutive_failures,
            "max_backoff": self.config.max_backoff
        })
    
    def get_statistics(self) -> Dict:
        """Get rate limiting statistics"""
        now = datetime.now()
        last_hour = [r for r in self.request_history if (now - r.timestamp).total_seconds() < 3600]
        last_minute = [r for r in self.request_history if (now - r.timestamp).total_seconds() < 60]
        
        successful_requests = [r for r in last_hour if r.success]
        rate_limited_requests = [r for r in last_hour if r.rate_limited]
        
        return {
            "total_requests_hour": len(last_hour),
            "total_requests_minute": len(last_minute),
            "successful_requests_hour": len(successful_requests),
            "rate_limited_requests_hour": len(rate_limited_requests),
            "success_rate_hour": len(successful_requests) / max(len(last_hour), 1),
            "consecutive_failures": self.consecutive_failures,
            "current_backoff": self.current_backoff,
            "last_request_time": self.last_request_time.isoformat() if self.last_request_time else None,
            "request_types": {rt.value: sum(1 for r in last_hour if r.request_type == rt) 
                           for rt in RequestType}
        }
    
    def reset_backoff(self):
        """Manually reset backoff (after user intervention)"""
        with self.lock:
            old_backoff = self.current_backoff
            self.current_backoff = 0.0
            self.consecutive_failures = 0
            
            self.logger.log_security_event("backoff_manual_reset", {
                "old_backoff": old_backoff,
                "reset_at": datetime.now().isoformat()
            })
    
    def _save_state(self):
        """Save rate limiter state to disk"""
        try:
            state = {
                "last_request_time": self.last_request_time.isoformat() if self.last_request_time else None,
                "current_backoff": self.current_backoff,
                "consecutive_failures": self.consecutive_failures,
                "request_history": [
                    {
                        "timestamp": r.timestamp.isoformat(),
                        "request_type": r.request_type.value,
                        "url_hash": hashlib.sha256(r.url.encode()).hexdigest()[:16],
                        "response_status": r.response_status,
                        "response_time": r.response_time,
                        "success": r.success,
                        "rate_limited": r.rate_limited
                    }
                    for r in self.request_history[-100:]  # Keep last 100 requests
                ]
            }
            
            with open(self.storage_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            self.logger.warning(f"Failed to save rate limiter state: {e}")
    
    def _load_state(self):
        """Load rate limiter state from disk"""
        try:
            if not os.path.exists(self.storage_file):
                return
            
            with open(self.storage_file, 'r') as f:
                state = json.load(f)
            
            # Restore basic state
            if state.get("last_request_time"):
                self.last_request_time = datetime.fromisoformat(state["last_request_time"])
            
            self.current_backoff = state.get("current_backoff", 0.0)
            self.consecutive_failures = state.get("consecutive_failures", 0)
            
            # Restore recent request history
            history = state.get("request_history", [])
            cutoff = datetime.now() - timedelta(hours=24)
            
            for record_data in history:
                try:
                    timestamp = datetime.fromisoformat(record_data["timestamp"])
                    if timestamp > cutoff:
                        record = RequestRecord(
                            timestamp=timestamp,
                            request_type=RequestType(record_data["request_type"]),
                            url=f"<hash:{record_data['url_hash']}>",  # Don't store actual URLs
                            response_status=record_data.get("response_status"),
                            response_time=record_data.get("response_time", 0.0),
                            success=record_data.get("success", False),
                            rate_limited=record_data.get("rate_limited", False)
                        )
                        self.request_history.append(record)
                except Exception:
                    continue  # Skip invalid records
            
            self.logger.info(f"Loaded rate limiter state: {len(self.request_history)} recent requests")
            
        except Exception as e:
            self.logger.warning(f"Failed to load rate limiter state: {e}")


# Global rate limiter instance
_global_rate_limiter = None


def get_rate_limiter(config: RateLimitConfig = None) -> IntelligentRateLimiter:
    """Get or create global rate limiter instance"""
    global _global_rate_limiter
    
    if _global_rate_limiter is None:
        _global_rate_limiter = IntelligentRateLimiter(config)
    
    return _global_rate_limiter


if __name__ == "__main__":
    # Demo and test rate limiter
    print("⏱️ Intelligent Rate Limiter Demo")
    
    # Create rate limiter with aggressive settings for demo
    config = RateLimitConfig(
        min_request_delay=1.0,
        max_request_delay=3.0,
        max_requests_per_minute=5,
        initial_backoff=10.0
    )
    
    limiter = IntelligentRateLimiter(config)
    
    print("\n📋 Testing rate limiting behavior:")
    
    # Simulate normal requests
    for i in range(3):
        wait_time = limiter.wait_for_request(RequestType.PAGE_LOAD, f"https://facebook.com/page{i}")
        print(f"Request {i+1}: waited {wait_time:.1f}s")
        
        # Simulate successful response
        limiter.record_request(
            RequestType.PAGE_LOAD,
            f"https://facebook.com/page{i}",
            200,
            "<html>Valid Facebook page content</html>",
            1.5
        )
    
    print("\n⚠️ Simulating rate limit detection:")
    
    # Simulate rate limited response
    wait_time = limiter.wait_for_request(RequestType.API_CALL, "https://facebook.com/api")
    limiter.record_request(
        RequestType.API_CALL,
        "https://facebook.com/api",
        429,
        "Rate limit exceeded. Please try again later.",
        0.1
    )
    
    # Check statistics
    stats = limiter.get_statistics()
    print(f"\n📊 Statistics:")
    print(f"   • Total requests (hour): {stats['total_requests_hour']}")
    print(f"   • Success rate: {stats['success_rate_hour']:.1%}")
    print(f"   • Current backoff: {stats['current_backoff']:.1f}s")
    print(f"   • Consecutive failures: {stats['consecutive_failures']}")
    
    # Test next request with backoff
    print(f"\n⏱️ Next request with backoff:")
    wait_time = limiter.wait_for_request(RequestType.SCROLL, "https://facebook.com/scroll")
    print(f"Waited {wait_time:.1f}s due to rate limiting")
    
    print("\n✅ Rate limiter demo complete")