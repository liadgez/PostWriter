#!/usr/bin/env python3
"""
Extract cookies from Chrome debugging session
"""

import requests
import json
import websocket

def get_chrome_tabs():
    """Get list of Chrome tabs"""
    response = requests.get("http://localhost:9222/json/list")
    return response.json()

def extract_cookies_from_tab(tab_url):
    """Extract cookies from a specific tab"""
    tabs = get_chrome_tabs()
    facebook_tab = None
    
    for tab in tabs:
        if 'facebook.com' in tab.get('url', ''):
            facebook_tab = tab
            break
    
    if not facebook_tab:
        print("No Facebook tab found")
        return None
    
    # Connect to the tab's debugger
    ws_url = facebook_tab['webSocketDebuggerUrl']
    ws = websocket.create_connection(ws_url)
    
    # Enable Runtime and Network domains
    ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
    ws.recv()
    
    ws.send(json.dumps({"id": 2, "method": "Network.enable"}))
    ws.recv()
    
    # Get cookies
    ws.send(json.dumps({"id": 3, "method": "Network.getCookies"}))
    response = ws.recv()
    
    ws.close()
    
    cookies_data = json.loads(response)
    if 'result' in cookies_data and 'cookies' in cookies_data['result']:
        return cookies_data['result']['cookies']
    
    return None

def main():
    print("Extracting cookies from Chrome...")
    cookies = extract_cookies_from_tab("facebook.com")
    
    if cookies:
        # Filter for Facebook cookies
        fb_cookies = [c for c in cookies if 'facebook.com' in c.get('domain', '')]
        
        # Save to cookies.json format
        cookie_dict = {}
        for cookie in fb_cookies:
            cookie_dict[cookie['name']] = cookie['value']
        
        # Save cookies
        with open('./data/cookies.json', 'w') as f:
            json.dump(cookie_dict, f, indent=2)
        
        print(f"✅ Extracted {len(fb_cookies)} Facebook cookies")
        print("Saved to ./data/cookies.json")
        
        # Also show current tab URL
        tabs = get_chrome_tabs()
        for tab in tabs:
            if 'facebook.com' in tab.get('url', ''):
                print(f"Current Facebook URL: {tab['url']}")
                break
    else:
        print("❌ Failed to extract cookies")

if __name__ == "__main__":
    main()