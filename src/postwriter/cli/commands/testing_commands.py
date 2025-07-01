"""
PostWriter CLI - Testing Commands
Handles real-time UI testing and monitoring functionality
"""

import asyncio
import os
import sys
from typing import Dict

from ...security.logging import get_secure_logger
from ...testing import EnhancedBrowserManager, UISupervisor, VisualValidator
from ...testing.browser_manager import BrowserEngine


def add_testing_commands(subparsers):
    """Add testing commands to CLI parser"""
    
    # Main test-ui command
    test_ui_parser = subparsers.add_parser(
        'test-ui',
        help='Start real-time UI testing and monitoring dashboard'
    )
    test_ui_parser.add_argument(
        '--engine',
        choices=['selenium', 'playwright', 'hybrid'],
        default='hybrid',
        help='Browser engine to use (default: hybrid)'
    )
    test_ui_parser.add_argument(
        '--dashboard-port',
        type=int,
        default=8000,
        help='Dashboard web interface port (default: 8000)'
    )
    test_ui_parser.add_argument(
        '--websocket-port',
        type=int,
        default=8765,
        help='WebSocket server port (default: 8765)'
    )
    test_ui_parser.add_argument(
        '--auto-screenshot',
        action='store_true',
        help='Enable automatic screenshot capture'
    )
    test_ui_parser.add_argument(
        '--screenshot-interval',
        type=int,
        default=5,
        help='Screenshot capture interval in seconds (default: 5)'
    )
    test_ui_parser.set_defaults(func=handle_test_ui_command)
    
    # Visual testing command
    visual_test_parser = subparsers.add_parser(
        'visual-test',
        help='Run visual regression tests'
    )
    visual_test_parser.add_argument(
        '--baseline',
        required=True,
        help='Baseline screenshot name for comparison'
    )
    visual_test_parser.add_argument(
        '--current',
        required=True,
        help='Current screenshot path to compare'
    )
    visual_test_parser.add_argument(
        '--tolerance',
        type=float,
        default=0.95,
        help='Similarity tolerance (0.0-1.0, default: 0.95)'
    )
    visual_test_parser.set_defaults(func=handle_visual_test_command)
    
    # Create baseline command
    baseline_parser = subparsers.add_parser(
        'create-baseline',
        help='Create baseline screenshot for visual testing'
    )
    baseline_parser.add_argument(
        '--name',
        required=True,
        help='Baseline name identifier'
    )
    baseline_parser.add_argument(
        '--url',
        required=True,
        help='URL to capture for baseline'
    )
    baseline_parser.add_argument(
        '--engine',
        choices=['selenium', 'playwright'],
        default='selenium',
        help='Browser engine to use (default: selenium)'
    )
    baseline_parser.set_defaults(func=handle_create_baseline_command)


def handle_test_ui_command(args, config: Dict):
    """Start real-time UI testing dashboard"""
    logger = get_secure_logger()
    logger.info("Starting real-time UI testing dashboard...")
    
    # Update config with command line arguments
    if 'testing' not in config:
        config['testing'] = {}
    
    config['testing'].update({
        'dashboard_port': args.dashboard_port,
        'websocket_port': args.websocket_port,
        'screenshots_enabled': True,
        'screenshot_interval': args.screenshot_interval,
        'auto_screenshot': args.auto_screenshot
    })
    
    # Determine browser engine
    engine_map = {
        'selenium': BrowserEngine.SELENIUM,
        'playwright': BrowserEngine.PLAYWRIGHT,
        'hybrid': BrowserEngine.HYBRID
    }
    engine = engine_map[args.engine]
    
    try:
        # Check required dependencies
        missing_deps = []
        
        if engine in [BrowserEngine.PLAYWRIGHT, BrowserEngine.HYBRID]:
            try:
                import playwright
            except ImportError:
                missing_deps.append("playwright")
        
        try:
            import fastapi
            import uvicorn
            import websockets
        except ImportError:
            if 'fastapi' not in str(sys.modules):
                missing_deps.append("fastapi")
            if 'uvicorn' not in str(sys.modules):
                missing_deps.append("uvicorn")
            if 'websockets' not in str(sys.modules):
                missing_deps.append("websockets")
        
        if missing_deps:
            print(f"❌ Missing required dependencies: {', '.join(missing_deps)}")
            print("💡 Install with: pip install " + " ".join(missing_deps))
            return 1
        
        # Run the async dashboard
        return asyncio.run(_run_ui_testing_dashboard(config, engine))
        
    except KeyboardInterrupt:
        print("\n🛑 UI testing dashboard stopped by user")
        return 0
    except Exception as e:
        logger.error(f"UI testing dashboard failed: {e}")
        print(f"❌ Failed to start UI testing dashboard: {e}")
        return 1


async def _run_ui_testing_dashboard(config: Dict, engine: BrowserEngine):
    """Run the UI testing dashboard (async)"""
    logger = get_secure_logger()
    
    try:
        # Initialize browser manager
        print(f"🔧 Initializing browser manager with {engine.value} engine...")
        browser_manager = EnhancedBrowserManager(config, engine)
        
        if not await browser_manager.initialize():
            print("❌ Failed to initialize browser manager")
            return 1
        
        print("✅ Browser manager initialized")
        
        # Initialize UI supervisor
        print("🔧 Starting UI supervisor...")
        supervisor = UISupervisor(config, browser_manager)
        
        if not await supervisor.start_server():
            print("❌ Failed to start UI supervisor WebSocket server")
            await browser_manager.cleanup()
            return 1
        
        print(f"✅ UI supervisor started on port {config['testing']['websocket_port']}")
        
        # Initialize dashboard API
        print("🔧 Starting web dashboard...")
        try:
            from ...testing.web_dashboard import DashboardAPI
            dashboard = DashboardAPI(config, browser_manager, supervisor)
            
            dashboard_url = dashboard.get_dashboard_url()
            websocket_url = f"ws://localhost:{config['testing']['websocket_port']}"
            
            print("\n" + "="*60)
            print("🎉 UI Testing Dashboard Started Successfully!")
            print("="*60)
            print(f"📊 Dashboard URL: {dashboard_url}")
            print(f"🔌 WebSocket URL: {websocket_url}")
            print(f"🎛️  Browser Engine: {engine.value}")
            print(f"📸 Auto Screenshots: {'Enabled' if config['testing']['auto_screenshot'] else 'Disabled'}")
            print("="*60)
            print("\n💡 Open the dashboard URL in your browser to start monitoring!")
            print("💡 Press Ctrl+C to stop the dashboard")
            print()
            
            # Start dashboard server (this will block)
            await dashboard.start_server()
            
        except ImportError as e:
            print(f"❌ Dashboard dependencies missing: {e}")
            print("💡 Install with: pip install fastapi uvicorn jinja2")
            return 1
        
    except Exception as e:
        logger.error(f"Dashboard startup error: {e}")
        print(f"❌ Dashboard startup failed: {e}")
        return 1
    
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        try:
            if 'supervisor' in locals():
                await supervisor.stop_server()
            if 'browser_manager' in locals():
                await browser_manager.cleanup()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        
        print("✅ Cleanup complete")
        return 0


def handle_visual_test_command(args, config: Dict):
    """Run visual regression test"""
    logger = get_secure_logger()
    logger.info(f"Running visual test: {args.baseline} vs {args.current}")
    
    try:
        validator = VisualValidator(config)
        
        if not os.path.exists(args.current):
            print(f"❌ Current screenshot not found: {args.current}")
            return 1
        
        # Perform comparison
        comparison = validator.compare_screenshots(
            args.current,
            args.baseline,
            tolerance=args.tolerance
        )
        
        print(f"\n📊 Visual Test Results:")
        print(f"   Baseline: {args.baseline}")
        print(f"   Current: {args.current}")
        print(f"   Similarity: {comparison.similarity_score:.3f}")
        print(f"   Difference: {comparison.difference_percentage:.2f}%")
        print(f"   Result: {comparison.result.value.upper()}")
        
        if comparison.diff_image_path:
            print(f"   Diff Image: {comparison.diff_image_path}")
        
        if comparison.result.value in ['passed']:
            print("✅ Visual test PASSED")
            return 0
        elif comparison.result.value in ['warning']:
            print("⚠️ Visual test WARNING")
            return 0
        else:
            print("❌ Visual test FAILED")
            return 1
            
    except Exception as e:
        logger.error(f"Visual test failed: {e}")
        print(f"❌ Visual test error: {e}")
        return 1


def handle_create_baseline_command(args, config: Dict):
    """Create baseline screenshot"""
    logger = get_secure_logger()
    logger.info(f"Creating baseline: {args.name} from {args.url}")
    
    # Determine browser engine
    engine = BrowserEngine.SELENIUM if args.engine == 'selenium' else BrowserEngine.PLAYWRIGHT
    
    try:
        # Run the async baseline creation
        return asyncio.run(_create_baseline_async(config, engine, args.name, args.url))
        
    except KeyboardInterrupt:
        print("\n🛑 Baseline creation stopped by user")
        return 0
    except Exception as e:
        logger.error(f"Baseline creation failed: {e}")
        print(f"❌ Failed to create baseline: {e}")
        return 1


async def _create_baseline_async(config: Dict, engine: BrowserEngine, name: str, url: str):
    """Create baseline screenshot (async)"""
    browser_manager = None
    
    try:
        # Initialize browser
        print(f"🔧 Initializing {engine.value} browser...")
        browser_manager = EnhancedBrowserManager(config, engine)
        
        if not await browser_manager.initialize():
            print("❌ Failed to initialize browser")
            return 1
        
        # Navigate to URL
        print(f"🌐 Navigating to {url}...")
        if not await browser_manager.navigate_to_url(url):
            print(f"❌ Failed to navigate to {url}")
            return 1
        
        # Wait for page to load
        print("⏳ Waiting for page to load...")
        await asyncio.sleep(3)
        
        # Take screenshot
        print("📸 Taking screenshot...")
        screenshot_path = await browser_manager.take_screenshot()
        
        if not screenshot_path:
            print("❌ Failed to take screenshot")
            return 1
        
        # Create baseline
        validator = VisualValidator(config)
        if validator.create_baseline(screenshot_path, name):
            print(f"✅ Baseline '{name}' created successfully")
            print(f"📁 Screenshot: {screenshot_path}")
            return 0
        else:
            print(f"❌ Failed to create baseline '{name}'")
            return 1
            
    finally:
        if browser_manager:
            await browser_manager.cleanup()


# Example usage information
def get_testing_help():
    """Get help information for testing commands"""
    return """
PostWriter UI Testing Commands:

🎛️  test-ui              Start real-time monitoring dashboard
📊 visual-test          Compare screenshots for visual regression
📸 create-baseline      Create baseline screenshot for testing

Examples:
  postwriter test-ui --engine hybrid --dashboard-port 8000
  postwriter create-baseline --name login_page --url https://facebook.com/login
  postwriter visual-test --baseline login_page --current ./current_screenshot.png

For detailed help on any command:
  postwriter <command> --help
"""