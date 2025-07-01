#!/usr/bin/env python3
"""
Dashboard API for PostWriter
FastAPI-based backend for the real-time monitoring dashboard
"""

import asyncio
import os
import json
import base64
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.requests import Request
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = None
    WebSocket = None
    HTTPException = None

from ..browser_manager import EnhancedBrowserManager, BrowserState
from ..ui_supervisor import UISupervisor
from ..visual_validator import VisualValidator
from ...security.logging import get_secure_logger


class DashboardAPI:
    """
    FastAPI-based dashboard for real-time PostWriter monitoring
    """
    
    def __init__(self, config: Dict, browser_manager: EnhancedBrowserManager, supervisor: UISupervisor):
        if not FASTAPI_AVAILABLE:
            raise ImportError("FastAPI not available. Install with: pip install fastapi uvicorn")
        
        self.config = config
        self.browser_manager = browser_manager
        self.supervisor = supervisor
        self.logger = get_secure_logger("dashboard_api")
        
        # FastAPI app
        self.app = FastAPI(
            title="PostWriter Dashboard",
            description="Real-time monitoring for Facebook scraping",
            version="2.0.0"
        )
        
        # Dashboard settings
        self.host = config.get('testing', {}).get('dashboard_host', '127.0.0.1')
        self.port = config.get('testing', {}).get('dashboard_port', 8000)
        
        # Static files and templates
        current_dir = Path(__file__).parent
        self.templates = Jinja2Templates(directory=current_dir / "templates")
        
        # Mount static files
        self.app.mount("/static", StaticFiles(directory=current_dir / "static"), name="static")
        
        # Active WebSocket connections
        self.websocket_connections: List[WebSocket] = []
        
        # Setup routes
        self._setup_routes()
        
        self.logger.info("Dashboard API initialized")

    def _setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Main dashboard page"""
            return self.templates.TemplateResponse("dashboard.html", {
                "request": request,
                "websocket_url": f"ws://{self.host}:{self.supervisor.websocket_port}",
                "dashboard_title": "PostWriter Real-Time Monitor"
            })
        
        @self.app.get("/api/status")
        async def get_status():
            """Get current system status"""
            try:
                browser_state = self.browser_manager.get_state()
                supervisor_info = self.supervisor.get_connection_info()
                
                return {
                    "status": "running",
                    "timestamp": datetime.now().isoformat(),
                    "browser": {
                        "engine": browser_state.engine.value,
                        "url": browser_state.url,
                        "page_state": browser_state.page_state.value,
                        "errors": browser_state.errors
                    },
                    "supervisor": supervisor_info,
                    "dashboard": {
                        "host": self.host,
                        "port": self.port,
                        "active_connections": len(self.websocket_connections)
                    }
                }
            except Exception as e:
                self.logger.error(f"Status API error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/screenshots")
        async def list_screenshots():
            """List available screenshots"""
            try:
                screenshot_dir = self.config.get('directories', {}).get('logs_dir', './logs')
                screenshots = []
                
                if os.path.exists(screenshot_dir):
                    for file in os.listdir(screenshot_dir):
                        if file.endswith('.png'):
                            file_path = os.path.join(screenshot_dir, file)
                            stat = os.stat(file_path)
                            screenshots.append({
                                "filename": file,
                                "path": file_path,
                                "size": stat.st_size,
                                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                            })
                
                # Sort by creation time (newest first)
                screenshots.sort(key=lambda x: x['created'], reverse=True)
                
                return {"screenshots": screenshots}
                
            except Exception as e:
                self.logger.error(f"Screenshots API error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/screenshot/{filename}")
        async def get_screenshot(filename: str):
            """Get specific screenshot as base64"""
            try:
                screenshot_dir = self.config.get('directories', {}).get('logs_dir', './logs')
                file_path = os.path.join(screenshot_dir, filename)
                
                if not os.path.exists(file_path) or not filename.endswith('.png'):
                    raise HTTPException(status_code=404, detail="Screenshot not found")
                
                with open(file_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                return {
                    "filename": filename,
                    "data": image_data,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                self.logger.error(f"Screenshot API error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/commands/{command}")
        async def execute_command(command: str, params: Dict = None):
            """Execute supervisor command"""
            try:
                if params is None:
                    params = {}
                
                # Send command to supervisor via WebSocket
                command_message = {
                    "command": command,
                    "params": params
                }
                
                # This would typically go through the supervisor's command handler
                # For now, we'll return a placeholder response
                return {
                    "command": command,
                    "params": params,
                    "status": "executed",
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                self.logger.error(f"Command API error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates"""
            await websocket.accept()
            self.websocket_connections.append(websocket)
            
            try:
                # Send initial state
                await websocket.send_json({
                    "type": "connected",
                    "data": {
                        "message": "Connected to PostWriter Dashboard",
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                # Keep connection alive and handle incoming messages
                while True:
                    try:
                        data = await websocket.receive_json()
                        await self._handle_websocket_message(websocket, data)
                    except WebSocketDisconnect:
                        break
                    
            except Exception as e:
                self.logger.error(f"WebSocket error: {e}")
            finally:
                if websocket in self.websocket_connections:
                    self.websocket_connections.remove(websocket)

    async def _handle_websocket_message(self, websocket: WebSocket, data: Dict):
        """Handle incoming WebSocket messages"""
        try:
            message_type = data.get('type')
            
            if message_type == 'command':
                command = data.get('command')
                params = data.get('params', {})
                
                # Execute command (this would integrate with supervisor)
                result = await self._execute_dashboard_command(command, params)
                
                await websocket.send_json({
                    "type": "command_result",
                    "data": result
                })
                
            elif message_type == 'request_screenshot':
                # Take screenshot and send back
                screenshot_path = await self.browser_manager.take_screenshot()
                if screenshot_path and os.path.exists(screenshot_path):
                    with open(screenshot_path, 'rb') as f:
                        image_data = base64.b64encode(f.read()).decode('utf-8')
                    
                    await websocket.send_json({
                        "type": "screenshot",
                        "data": {
                            "image": image_data,
                            "path": screenshot_path,
                            "timestamp": datetime.now().isoformat()
                        }
                    })
            
        except Exception as e:
            self.logger.error(f"WebSocket message handling error: {e}")
            await websocket.send_json({
                "type": "error",
                "data": {"error": str(e)}
            })

    async def _execute_dashboard_command(self, command: str, params: Dict) -> Dict:
        """Execute dashboard command"""
        try:
            if command == "take_screenshot":
                screenshot_path = await self.browser_manager.take_screenshot()
                return {"success": True, "screenshot_path": screenshot_path}
                
            elif command == "navigate":
                url = params.get('url')
                if url:
                    success = await self.browser_manager.navigate_to_url(url)
                    return {"success": success, "url": url}
                else:
                    return {"success": False, "error": "URL required"}
                    
            elif command == "scroll":
                pixels = params.get('pixels', 1000)
                success = await self.browser_manager.scroll_page(pixels)
                return {"success": success, "pixels": pixels}
                
            elif command == "get_state":
                state = self.browser_manager.get_state()
                return {"success": True, "state": state.__dict__}
                
            else:
                return {"success": False, "error": f"Unknown command: {command}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def broadcast_to_websockets(self, message: Dict):
        """Broadcast message to all connected WebSocket clients"""
        if not self.websocket_connections:
            return
        
        disconnected = []
        for websocket in self.websocket_connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                self.logger.warning(f"Failed to send to WebSocket client: {e}")
                disconnected.append(websocket)
        
        # Remove disconnected clients
        for websocket in disconnected:
            self.websocket_connections.remove(websocket)

    async def start_server(self):
        """Start the dashboard server"""
        try:
            config = uvicorn.Config(
                app=self.app,
                host=self.host,
                port=self.port,
                log_level="info"
            )
            server = uvicorn.Server(config)
            
            self.logger.info(f"Starting dashboard server on http://{self.host}:{self.port}")
            await server.serve()
            
        except Exception as e:
            self.logger.error(f"Failed to start dashboard server: {e}")
            raise

    def run(self):
        """Run the dashboard server (blocking)"""
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )

    def get_dashboard_url(self) -> str:
        """Get dashboard URL"""
        return f"http://{self.host}:{self.port}"


# Example usage
if __name__ == "__main__":
    async def test_dashboard():
        from ..browser_manager import BrowserEngine
        
        config = {
            'testing': {
                'dashboard_host': '127.0.0.1',
                'dashboard_port': 8000,
                'websocket_port': 8765,
                'screenshots_enabled': True
            },
            'directories': {
                'logs_dir': './test_logs'
            }
        }
        
        # Create browser manager and supervisor
        browser_manager = EnhancedBrowserManager(config, BrowserEngine.SELENIUM)
        await browser_manager.initialize()
        
        supervisor = UISupervisor(config, browser_manager)
        await supervisor.start_server()
        
        # Create dashboard
        dashboard = DashboardAPI(config, browser_manager, supervisor)
        
        print(f"Dashboard will be available at: {dashboard.get_dashboard_url()}")
        print("Starting dashboard server...")
        
        # Start server
        await dashboard.start_server()
    
    if FASTAPI_AVAILABLE:
        asyncio.run(test_dashboard())
    else:
        print("FastAPI not available for testing")