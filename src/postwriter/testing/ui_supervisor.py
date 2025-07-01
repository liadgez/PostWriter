#!/usr/bin/env python3
"""
UI Supervisor for PostWriter
Handles real-time UI monitoring, screenshot streaming, and interactive control
"""

import asyncio
import json
import base64
import time
import os
from datetime import datetime
from typing import Dict, List, Optional, Callable, Set
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WebSocketServerProtocol = None

from .browser_manager import EnhancedBrowserManager, BrowserState, FacebookPageState
from ..security.logging import get_secure_logger


class SupervisorCommand(Enum):
    """Available supervisor commands"""
    PAUSE = "pause"
    RESUME = "resume"
    TAKE_SCREENSHOT = "take_screenshot"
    NAVIGATE = "navigate"
    SCROLL = "scroll"
    CLICK = "click"
    GET_STATE = "get_state"
    START_SCRAPING = "start_scraping"
    STOP_SCRAPING = "stop_scraping"


class SupervisorEvent(Enum):
    """Supervisor event types"""
    STATE_CHANGE = "state_change"
    SCREENSHOT_TAKEN = "screenshot_taken"
    ERROR = "error"
    LOG = "log"
    SCRAPING_PROGRESS = "scraping_progress"
    COMMAND_RESULT = "command_result"


@dataclass
class SupervisorMessage:
    """Message structure for WebSocket communication"""
    event: str
    data: Dict
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))


class UISupervisor:
    """
    Real-time UI supervisor providing WebSocket-based monitoring and control
    """
    
    def __init__(self, config: Dict, browser_manager: EnhancedBrowserManager):
        self.config = config
        self.browser_manager = browser_manager
        self.logger = get_secure_logger("ui_supervisor")
        
        # WebSocket settings
        self.websocket_host = config.get('testing', {}).get('websocket_host', 'localhost')
        self.websocket_port = config.get('testing', {}).get('websocket_port', 8765)
        self.websocket_server = None
        
        # Client connections
        self.connected_clients: Set[WebSocketServerProtocol] = set()
        
        # State management
        self.is_paused = False
        self.is_scraping = False
        self.scraping_progress = {"current": 0, "total": 0, "status": "idle"}
        
        # Event handlers
        self.command_handlers = {
            SupervisorCommand.PAUSE: self._handle_pause,
            SupervisorCommand.RESUME: self._handle_resume,
            SupervisorCommand.TAKE_SCREENSHOT: self._handle_take_screenshot,
            SupervisorCommand.NAVIGATE: self._handle_navigate,
            SupervisorCommand.SCROLL: self._handle_scroll,
            SupervisorCommand.CLICK: self._handle_click,
            SupervisorCommand.GET_STATE: self._handle_get_state,
            SupervisorCommand.START_SCRAPING: self._handle_start_scraping,
            SupervisorCommand.STOP_SCRAPING: self._handle_stop_scraping,
        }
        
        # Register browser state change callback
        self.browser_manager.add_state_change_callback(self._on_browser_state_change)
        
        # Threading
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        self.logger.info("UI Supervisor initialized")

    async def start_server(self):
        """Start WebSocket server for real-time communication"""
        if not WEBSOCKETS_AVAILABLE:
            self.logger.error("WebSockets not available. Install websockets package.")
            return False
        
        try:
            self.websocket_server = await websockets.serve(
                self._handle_websocket_connection,
                self.websocket_host,
                self.websocket_port
            )
            
            self.logger.info(f"WebSocket server started on {self.websocket_host}:{self.websocket_port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start WebSocket server: {e}")
            return False

    async def stop_server(self):
        """Stop WebSocket server"""
        if self.websocket_server:
            self.websocket_server.close()
            await self.websocket_server.wait_closed()
            self.logger.info("WebSocket server stopped")

    async def _handle_websocket_connection(self, websocket: WebSocketServerProtocol, path: str):
        """Handle new WebSocket connection"""
        self.connected_clients.add(websocket)
        client_addr = websocket.remote_address
        self.logger.info(f"Client connected: {client_addr}")
        
        # Send initial state
        await self._send_to_client(websocket, SupervisorMessage(
            event=SupervisorEvent.STATE_CHANGE.value,
            data={"browser_state": asdict(self.browser_manager.get_state())}
        ))
        
        try:
            async for message in websocket:
                await self._process_client_message(websocket, message)
                
        except Exception as e:
            self.logger.error(f"WebSocket error for {client_addr}: {e}")
        finally:
            self.connected_clients.discard(websocket)
            self.logger.info(f"Client disconnected: {client_addr}")

    async def _process_client_message(self, websocket: WebSocketServerProtocol, message: str):
        """Process incoming message from client"""
        try:
            data = json.loads(message)
            command = data.get('command')
            params = data.get('params', {})
            
            if command in [cmd.value for cmd in SupervisorCommand]:
                handler = self.command_handlers.get(SupervisorCommand(command))
                if handler:
                    result = await handler(params)
                    await self._send_to_client(websocket, SupervisorMessage(
                        event=SupervisorEvent.COMMAND_RESULT.value,
                        data={"command": command, "result": result}
                    ))
                else:
                    await self._send_error_to_client(websocket, f"No handler for command: {command}")
            else:
                await self._send_error_to_client(websocket, f"Unknown command: {command}")
                
        except json.JSONDecodeError as e:
            await self._send_error_to_client(websocket, f"Invalid JSON: {e}")
        except Exception as e:
            await self._send_error_to_client(websocket, f"Message processing error: {e}")

    async def _send_to_client(self, websocket: WebSocketServerProtocol, message: SupervisorMessage):
        """Send message to specific client"""
        try:
            await websocket.send(message.to_json())
        except Exception as e:
            self.logger.error(f"Failed to send message to client: {e}")

    async def _send_error_to_client(self, websocket: WebSocketServerProtocol, error: str):
        """Send error message to client"""
        await self._send_to_client(websocket, SupervisorMessage(
            event=SupervisorEvent.ERROR.value,
            data={"error": error}
        ))

    async def broadcast_message(self, message: SupervisorMessage):
        """Broadcast message to all connected clients"""
        if not self.connected_clients:
            return
        
        # Send to all connected clients
        disconnected = set()
        for client in self.connected_clients:
            try:
                await self._send_to_client(client, message)
            except Exception as e:
                self.logger.warning(f"Failed to send to client, marking for removal: {e}")
                disconnected.add(client)
        
        # Remove disconnected clients
        self.connected_clients -= disconnected

    def _on_browser_state_change(self, state: BrowserState):
        """Handle browser state changes"""
        # Convert to async and broadcast
        asyncio.create_task(self.broadcast_message(SupervisorMessage(
            event=SupervisorEvent.STATE_CHANGE.value,
            data={"browser_state": asdict(state)}
        )))

    # Command Handlers
    async def _handle_pause(self, params: Dict) -> Dict:
        """Handle pause command"""
        self.is_paused = True
        self.logger.info("Supervisor paused")
        return {"success": True, "message": "Supervisor paused"}

    async def _handle_resume(self, params: Dict) -> Dict:
        """Handle resume command"""
        self.is_paused = False
        self.logger.info("Supervisor resumed")
        return {"success": True, "message": "Supervisor resumed"}

    async def _handle_take_screenshot(self, params: Dict) -> Dict:
        """Handle screenshot command"""
        try:
            screenshot_path = await self.browser_manager.take_screenshot()
            
            # Convert screenshot to base64 for web display
            screenshot_data = None
            if screenshot_path and os.path.exists(screenshot_path):
                with open(screenshot_path, 'rb') as f:
                    screenshot_data = base64.b64encode(f.read()).decode('utf-8')
            
            # Broadcast screenshot to all clients
            await self.broadcast_message(SupervisorMessage(
                event=SupervisorEvent.SCREENSHOT_TAKEN.value,
                data={
                    "screenshot_path": screenshot_path,
                    "screenshot_data": screenshot_data
                }
            ))
            
            return {"success": True, "screenshot_path": screenshot_path}
            
        except Exception as e:
            error_msg = f"Screenshot failed: {e}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}

    async def _handle_navigate(self, params: Dict) -> Dict:
        """Handle navigation command"""
        url = params.get('url')
        if not url:
            return {"success": False, "error": "URL required"}
        
        try:
            success = await self.browser_manager.navigate_to_url(url)
            return {"success": success, "url": url}
        except Exception as e:
            error_msg = f"Navigation failed: {e}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}

    async def _handle_scroll(self, params: Dict) -> Dict:
        """Handle scroll command"""
        pixels = params.get('pixels', 1000)
        
        try:
            success = await self.browser_manager.scroll_page(pixels)
            return {"success": success, "pixels": pixels}
        except Exception as e:
            error_msg = f"Scroll failed: {e}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}

    async def _handle_click(self, params: Dict) -> Dict:
        """Handle click command"""
        selector = params.get('selector')
        if not selector:
            return {"success": False, "error": "Selector required"}
        
        try:
            success = await self.browser_manager.click_element(selector)
            return {"success": success, "selector": selector}
        except Exception as e:
            error_msg = f"Click failed: {e}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}

    async def _handle_get_state(self, params: Dict) -> Dict:
        """Handle get state command"""
        try:
            state = self.browser_manager.get_state()
            return {
                "success": True,
                "state": asdict(state),
                "supervisor_state": {
                    "is_paused": self.is_paused,
                    "is_scraping": self.is_scraping,
                    "scraping_progress": self.scraping_progress,
                    "connected_clients": len(self.connected_clients)
                }
            }
        except Exception as e:
            error_msg = f"Get state failed: {e}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}

    async def _handle_start_scraping(self, params: Dict) -> Dict:
        """Handle start scraping command"""
        if self.is_scraping:
            return {"success": False, "error": "Scraping already in progress"}
        
        try:
            self.is_scraping = True
            self.scraping_progress = {"current": 0, "total": params.get('target_posts', 50), "status": "starting"}
            
            # Broadcast scraping start
            await self.broadcast_message(SupervisorMessage(
                event=SupervisorEvent.SCRAPING_PROGRESS.value,
                data=self.scraping_progress
            ))
            
            # TODO: Integrate with actual scraping logic
            self.logger.info("Scraping started")
            return {"success": True, "message": "Scraping started"}
            
        except Exception as e:
            self.is_scraping = False
            error_msg = f"Start scraping failed: {e}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}

    async def _handle_stop_scraping(self, params: Dict) -> Dict:
        """Handle stop scraping command"""
        if not self.is_scraping:
            return {"success": False, "error": "No scraping in progress"}
        
        try:
            self.is_scraping = False
            self.scraping_progress["status"] = "stopped"
            
            # Broadcast scraping stop
            await self.broadcast_message(SupervisorMessage(
                event=SupervisorEvent.SCRAPING_PROGRESS.value,
                data=self.scraping_progress
            ))
            
            self.logger.info("Scraping stopped")
            return {"success": True, "message": "Scraping stopped"}
            
        except Exception as e:
            error_msg = f"Stop scraping failed: {e}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}

    async def update_scraping_progress(self, current: int, total: int, status: str = "running"):
        """Update scraping progress and broadcast to clients"""
        self.scraping_progress = {
            "current": current,
            "total": total,
            "status": status,
            "percentage": (current / total * 100) if total > 0 else 0
        }
        
        await self.broadcast_message(SupervisorMessage(
            event=SupervisorEvent.SCRAPING_PROGRESS.value,
            data=self.scraping_progress
        ))

    async def log_message(self, message: str, level: str = "info"):
        """Send log message to connected clients"""
        await self.broadcast_message(SupervisorMessage(
            event=SupervisorEvent.LOG.value,
            data={"message": message, "level": level}
        ))

    async def start_automatic_screenshots(self, interval: int = 5):
        """Start automatic screenshot capture"""
        while not self.is_paused and self.connected_clients:
            try:
                await self._handle_take_screenshot({})
                await asyncio.sleep(interval)
            except Exception as e:
                self.logger.error(f"Automatic screenshot error: {e}")
                await asyncio.sleep(interval * 2)  # Back off on error

    def get_connection_info(self) -> Dict:
        """Get connection information for clients"""
        return {
            "websocket_url": f"ws://{self.websocket_host}:{self.websocket_port}",
            "connected_clients": len(self.connected_clients),
            "status": "running" if self.websocket_server else "stopped"
        }


# Example usage and testing
if __name__ == "__main__":
    async def test_ui_supervisor():
        from .browser_manager import BrowserEngine
        
        config = {
            'testing': {
                'websocket_host': 'localhost',
                'websocket_port': 8765,
                'screenshots_enabled': True,
                'screenshot_interval': 3
            },
            'directories': {
                'logs_dir': './test_logs'
            }
        }
        
        # Create browser manager
        browser_manager = EnhancedBrowserManager(config, BrowserEngine.SELENIUM)
        await browser_manager.initialize()
        
        # Create supervisor
        supervisor = UISupervisor(config, browser_manager)
        
        # Start WebSocket server
        await supervisor.start_server()
        
        print(f"UI Supervisor started: {supervisor.get_connection_info()}")
        print("Connect to the WebSocket to interact with the browser")
        
        # Navigate to a test page
        await browser_manager.navigate_to_url("https://facebook.com")
        
        # Start automatic screenshots
        screenshot_task = asyncio.create_task(supervisor.start_automatic_screenshots())
        
        try:
            # Keep running for demonstration
            await asyncio.sleep(60)
        finally:
            screenshot_task.cancel()
            await supervisor.stop_server()
            await browser_manager.cleanup()
    
    # Run test
    asyncio.run(test_ui_supervisor())