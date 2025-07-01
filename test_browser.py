#!/usr/bin/env python3
"""
Test browser launching to debug the issue
"""

import asyncio
from playwright.async_api import async_playwright

async def test_browser():
    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=False)
        print("Browser launched successfully")
        
        context = await browser.new_context()
        print("Context created")
        
        page = await context.new_page()
        print("Page created")
        
        print("Navigating to Google...")
        await page.goto("https://www.google.com")
        print("Navigation complete")
        
        print("Waiting 5 seconds...")
        await page.wait_for_timeout(5000)
        
        print("Closing browser...")
        await browser.close()
        print("Done")

if __name__ == "__main__":
    asyncio.run(test_browser())