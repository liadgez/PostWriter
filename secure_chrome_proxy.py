#!/usr/bin/env python3
"""
Secure Chrome Debug Proxy for PostWriter
Adds authentication and security to Chrome's remote debugging port
"""

import os
import json
import socket
import threading
import hmac
import hashlib
import time
import secrets
from typing import Dict, Optional, Any
import http.server
import socketserver
import urllib.parse
import urllib.request
import ssl
from datetime import datetime, timedelta

from exceptions import SecurityError
from secure_logging import get_secure_logger


class SecureChromeProxy:
    """Secure proxy for Chrome debug connection with authentication"""
    
    def __init__(self, chrome_port: int = 9222, proxy_port: int = 9223, auth_token: str = None):
        """
        Initialize secure Chrome proxy
        
        Args:
            chrome_port: Chrome debug port (usually 9222)
            proxy_port: Secure proxy port (default 9223)
            auth_token: Authentication token (generated if not provided)
        """
        self.chrome_port = chrome_port
        self.proxy_port = proxy_port
        self.auth_token = auth_token or self._generate_auth_token()
        self.server = None
        self.running = False
        
        # Session management
        self.active_sessions = {}
        self.session_timeout = 300  # 5 minutes
        
        # Security settings
        self.allowed_origins = ['localhost', '127.0.0.1']
        self.max_connections = 5
        self.active_connections = 0
        
    def _generate_auth_token(self) -> str:
        """Generate secure authentication token"""
        return secrets.token_urlsafe(32)
    
    def _verify_auth_token(self, provided_token: str) -> bool:
        """Verify authentication token using secure comparison"""
        if not provided_token:
            return False
        return hmac.compare_digest(self.auth_token.encode(), provided_token.encode())
    
    def _create_session(self, client_ip: str) -> str:
        """Create authenticated session"""
        session_id = secrets.token_urlsafe(16)
        self.active_sessions[session_id] = {
            'client_ip': client_ip,
            'created_at': datetime.now(),
            'last_activity': datetime.now()
        }
        return session_id
    
    def _validate_session(self, session_id: str, client_ip: str) -> bool:
        """Validate session and update activity"""
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        
        # Check if session expired
        if datetime.now() - session['last_activity'] > timedelta(seconds=self.session_timeout):
            del self.active_sessions[session_id]
            return False
        
        # Check IP consistency
        if session['client_ip'] != client_ip:
            return False
        
        # Update activity
        session['last_activity'] = datetime.now()
        return True
    
    def _cleanup_expired_sessions(self):
        """Remove expired sessions"""
        now = datetime.now()
        expired_sessions = []
        
        for session_id, session in self.active_sessions.items():
            if now - session['last_activity'] > timedelta(seconds=self.session_timeout):
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.active_sessions[session_id]
    
    def _is_chrome_running(self) -> bool:
        """Check if Chrome debug port is accessible"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(2)
                result = sock.connect_ex(('localhost', self.chrome_port))
                return result == 0
        except:
            return False
    
    def _proxy_request(self, path: str, method: str = 'GET', data: bytes = None) -> tuple:
        """
        Proxy request to Chrome debug port
        
        Returns:
            tuple: (status_code, headers, body)
        """
        try:
            url = f"http://localhost:{self.chrome_port}{path}"
            
            if method == 'GET':
                with urllib.request.urlopen(url, timeout=10) as response:
                    return response.getcode(), dict(response.headers), response.read()
            
            elif method == 'POST':
                req = urllib.request.Request(url, data=data, method='POST')
                req.add_header('Content-Type', 'application/json')
                with urllib.request.urlopen(req, timeout=10) as response:
                    return response.getcode(), dict(response.headers), response.read()
            
            else:
                return 405, {}, b'Method not allowed'
                
        except urllib.error.HTTPError as e:
            return e.code, {}, e.read()
        except Exception as e:
            return 500, {}, f"Proxy error: {e}".encode()


class SecureProxyHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for secure Chrome proxy"""
    
    def __init__(self, request, client_address, server, proxy_instance):
        self.proxy = proxy_instance
        super().__init__(request, client_address, server)
    
    def log_message(self, format, *args):
        """Override to control logging"""
        # Use secure logging
        logger = get_secure_logger("chrome_proxy")
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        message = f"[{timestamp}] {self.client_address[0]} - {format % args}"
        logger.info(f"Chrome Proxy: {message}")
    
    def _send_error_response(self, code: int, message: str):
        """Send error response"""
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        error_response = json.dumps({'error': message, 'code': code})
        self.wfile.write(error_response.encode())
    
    def _send_json_response(self, data: Any, status_code: int = 200):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        response = json.dumps(data, indent=2)
        self.wfile.write(response.encode())
    
    def _authenticate_request(self) -> Optional[str]:
        """
        Authenticate request and return session ID if valid
        
        Returns:
            Session ID if authenticated, None otherwise
        """
        # Check for auth token in header or query parameter
        auth_token = self.headers.get('X-Auth-Token')
        
        if not auth_token:
            # Check query parameters
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            auth_token = query_params.get('auth_token', [None])[0]
        
        if not auth_token:
            return None
        
        # Verify token
        if not self.proxy._verify_auth_token(auth_token):
            return None
        
        # Check for existing session
        session_id = self.headers.get('X-Session-ID')
        
        if session_id and self.proxy._validate_session(session_id, self.client_address[0]):
            return session_id
        
        # Create new session
        return self.proxy._create_session(self.client_address[0])
    
    def do_GET(self):
        """Handle GET requests"""
        try:
            # Clean up expired sessions
            self.proxy._cleanup_expired_sessions()
            
            # Check connection limit
            if self.proxy.active_connections >= self.proxy.max_connections:
                self._send_error_response(503, "Too many connections")
                return
            
            self.proxy.active_connections += 1
            
            try:
                # Handle authentication endpoint
                if self.path == '/auth':
                    auth_response = {
                        'message': 'Provide auth_token parameter or X-Auth-Token header',
                        'proxy_port': self.proxy.proxy_port,
                        'chrome_port': self.proxy.chrome_port,
                        'status': 'ready' if self.proxy._is_chrome_running() else 'chrome_not_running'
                    }
                    self._send_json_response(auth_response)
                    return
                
                # Handle status endpoint
                if self.path == '/status':
                    status_response = {
                        'proxy_running': True,
                        'chrome_running': self.proxy._is_chrome_running(),
                        'active_sessions': len(self.proxy.active_sessions),
                        'active_connections': self.proxy.active_connections,
                        'auth_required': True
                    }
                    self._send_json_response(status_response)
                    return
                
                # Authenticate request
                session_id = self._authenticate_request()
                if not session_id:
                    self._send_error_response(401, "Authentication required")
                    return
                
                # Check if Chrome is running
                if not self.proxy._is_chrome_running():
                    self._send_error_response(503, "Chrome debug port not accessible")
                    return
                
                # Proxy request to Chrome
                status_code, headers, body = self.proxy._proxy_request(self.path)
                
                # Send response
                self.send_response(status_code)
                for header_name, header_value in headers.items():
                    if header_name.lower() not in ['content-length', 'connection']:
                        self.send_header(header_name, header_value)
                
                self.send_header('X-Session-ID', session_id)
                self.send_header('X-Proxy-Auth', 'verified')
                self.end_headers()
                self.wfile.write(body)
                
            finally:
                self.proxy.active_connections -= 1
                
        except Exception as e:
            self._send_error_response(500, f"Internal server error: {e}")
    
    def do_POST(self):
        """Handle POST requests"""
        try:
            # Authenticate request
            session_id = self._authenticate_request()
            if not session_id:
                self._send_error_response(401, "Authentication required")
                return
            
            # Check if Chrome is running
            if not self.proxy._is_chrome_running():
                self._send_error_response(503, "Chrome debug port not accessible")
                return
            
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else None
            
            # Proxy request to Chrome
            status_code, headers, body = self.proxy._proxy_request(self.path, 'POST', post_data)
            
            # Send response
            self.send_response(status_code)
            for header_name, header_value in headers.items():
                if header_name.lower() not in ['content-length', 'connection']:
                    self.send_header(header_name, header_value)
            
            self.send_header('X-Session-ID', session_id)
            self.send_header('X-Proxy-Auth', 'verified')
            self.end_headers()
            self.wfile.write(body)
            
        except Exception as e:
            self._send_error_response(500, f"Internal server error: {e}")
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'X-Auth-Token, X-Session-ID, Content-Type')
        self.end_headers()


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Threaded HTTP server for handling multiple connections"""
    daemon_threads = True
    allow_reuse_address = True


def create_proxy_handler(proxy_instance):
    """Factory function to create handler with proxy instance"""
    class ProxyHandlerWithInstance(SecureProxyHandler):
        def __init__(self, request, client_address, server):
            super().__init__(request, client_address, server, proxy_instance)
    return ProxyHandlerWithInstance


class SecureChromeManager:
    """Manager for secure Chrome operations"""
    
    def __init__(self):
        self.proxy = None
        self.proxy_thread = None
    
    def start_secure_proxy(self, chrome_port: int = 9222, proxy_port: int = 9223) -> Dict[str, Any]:
        """
        Start secure Chrome proxy
        
        Args:
            chrome_port: Chrome debug port
            proxy_port: Secure proxy port
            
        Returns:
            Dict with proxy configuration
        """
        try:
            if self.proxy and self.proxy.running:
                return {
                    'success': False,
                    'error': 'Proxy already running',
                    'proxy_port': self.proxy.proxy_port,
                    'auth_token': self.proxy.auth_token
                }
            
            # Create proxy instance
            self.proxy = SecureChromeProxy(chrome_port, proxy_port)
            
            # Create and start server
            handler_class = create_proxy_handler(self.proxy)
            self.proxy.server = ThreadedHTTPServer(('localhost', proxy_port), handler_class)
            
            # Start proxy in background thread
            self.proxy_thread = threading.Thread(
                target=self._run_proxy_server,
                daemon=True
            )
            self.proxy_thread.start()
            
            self.proxy.running = True
            
            # Wait a moment to ensure server started
            time.sleep(0.5)
            
            return {
                'success': True,
                'proxy_port': proxy_port,
                'auth_token': self.proxy.auth_token,
                'chrome_port': chrome_port,
                'chrome_running': self.proxy._is_chrome_running(),
                'endpoints': {
                    'status': f'http://localhost:{proxy_port}/status',
                    'auth': f'http://localhost:{proxy_port}/auth',
                    'chrome_api': f'http://localhost:{proxy_port}/json'
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _run_proxy_server(self):
        """Run proxy server in background thread"""
        try:
            logger = get_secure_logger("chrome_proxy")
            logger.info(f"🔒 Secure Chrome proxy running on port {self.proxy.proxy_port}")
            logger.log_security_event("proxy_started", {
                "proxy_port": self.proxy.proxy_port,
                "auth_token": self.proxy.auth_token,
                "chrome_port": self.proxy.chrome_port
            })
            self.proxy.server.serve_forever()
        except Exception as e:
            logger = get_secure_logger("chrome_proxy")
            logger.error(f"❌ Proxy server error: {e}")
            self.proxy.running = False
    
    def stop_secure_proxy(self) -> bool:
        """Stop secure Chrome proxy"""
        try:
            logger = get_secure_logger("chrome_proxy")
            if self.proxy and self.proxy.server:
                self.proxy.server.shutdown()
                self.proxy.server.server_close()
                self.proxy.running = False
                logger.info("✅ Secure Chrome proxy stopped")
                return True
            return False
        except Exception as e:
            logger = get_secure_logger("chrome_proxy")
            logger.error(f"❌ Error stopping proxy: {e}")
            return False
    
    def get_proxy_status(self) -> Dict[str, Any]:
        """Get current proxy status"""
        if not self.proxy:
            return {'running': False, 'error': 'Proxy not initialized'}
        
        return {
            'running': self.proxy.running,
            'proxy_port': self.proxy.proxy_port,
            'chrome_port': self.proxy.chrome_port,
            'chrome_running': self.proxy._is_chrome_running(),
            'active_sessions': len(self.proxy.active_sessions),
            'active_connections': self.proxy.active_connections,
            'auth_token': self.proxy.auth_token if self.proxy.running else None
        }


def validate_chrome_security() -> Dict[str, Any]:
    """
    Validate Chrome security configuration
    
    Returns:
        Dict with security assessment
    """
    results = {
        'chrome_debug_port_open': False,
        'chrome_debug_secured': False,
        'proxy_available': False,
        'recommendations': []
    }
    
    try:
        # Check if Chrome debug port is open (unsecured)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', 9222))
            results['chrome_debug_port_open'] = (result == 0)
        
        if results['chrome_debug_port_open']:
            # Check if it's a secured proxy by looking for auth requirements
            try:
                import urllib.request
                response = urllib.request.urlopen('http://localhost:9222/json', timeout=2)
                if response.getcode() == 200:
                    results['chrome_debug_secured'] = False
                    results['recommendations'].append("Chrome debug port is unsecured - start secure proxy")
            except:
                # If we can't access it directly, it might be secured
                results['chrome_debug_secured'] = True
        
        # Check if secure proxy is available
        try:
            manager = SecureChromeManager()
            results['proxy_available'] = True
        except:
            results['proxy_available'] = False
            results['recommendations'].append("Install required packages for secure proxy")
        
        if not results['chrome_debug_port_open']:
            results['recommendations'].append("Start Chrome with debug port to use proxy")
        
    except Exception as e:
        results['error'] = str(e)
    
    return results


if __name__ == "__main__":
    # Demo/test the secure Chrome proxy
    print("🔒 Secure Chrome Proxy Demo")
    
    # Validate Chrome security
    security_results = validate_chrome_security()
    print(f"\n📊 Chrome Security Assessment:")
    print(f"   • Chrome debug port open: {security_results['chrome_debug_port_open']}")
    print(f"   • Chrome debug secured: {security_results['chrome_debug_secured']}")
    print(f"   • Proxy available: {security_results['proxy_available']}")
    
    if security_results['recommendations']:
        print(f"\n⚠️ Security Recommendations:")
        for rec in security_results['recommendations']:
            print(f"   • {rec}")
    
    # Start proxy if Chrome is running
    if security_results['chrome_debug_port_open'] and not security_results['chrome_debug_secured']:
        print(f"\n🚀 Starting secure proxy...")
        manager = SecureChromeManager()
        result = manager.start_secure_proxy()
        
        if result['success']:
            logger = get_secure_logger("chrome_proxy")
            logger.info(f"✅ Secure proxy started!")
            logger.info(f"   • Proxy port: {result['proxy_port']}")
            logger.log_security_event("auth_token_generated", {
                "proxy_port": result['proxy_port'],
                "auth_token": result['auth_token'],
                "chrome_running": result['chrome_running']
            })
            logger.info(f"   • Chrome running: {result['chrome_running']}")
            logger.info(f"\n💡 Usage:")
            logger.info(f"   curl -H 'X-Auth-Token: ***TOKEN_REDACTED***' http://localhost:{result['proxy_port']}/json")
            
            # Keep running for demo
            try:
                input("\nPress Enter to stop proxy...")
            except KeyboardInterrupt:
                pass
            
            manager.stop_secure_proxy()
        else:
            print(f"❌ Failed to start proxy: {result['error']}")