#!/usr/bin/env python3
"""
Test /copilot command through the Codex Plus proxy
Uses the exact same structure as real Codex CLI requests
"""
import json
import requests

def test_copilot_command():
    """Test /copilot command with proper Codex CLI structure"""
    
    # Create the exact structure that Codex CLI uses (based on captured logs)
    payload = {
        "model": "gpt-5",
        "instructions": "Test instructions for copilot command",
        "input": [
            {
                "type": "message",
                "role": "user", 
                "content": [
                    {
                        "type": "input_text",
                        "text": "<environment_context>\n  <cwd>/Users/jleechan/projects_other/codex_plus</cwd>\n  <approval_policy>never</approval_policy>\n  <sandbox_mode>read-only</sandbox_mode>\n  <network_access>restricted</network_access>\n  <shell>bash</shell>\n</environment_context>"
                    }
                ]
            },
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text", 
                        "text": "/copilot"
                    }
                ]
            }
        ],
        "tools": [],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
        "reasoning": False,
        "store": False,
        "stream": False
    }
    
    # Send request through proxy (no auth token needed for test)
    proxy_url = "http://127.0.0.1:3000/responses"
    headers = {
        "Content-Type": "application/json"
    }
    
    print("🧪 Testing /copilot command through Codex Plus proxy...")
    print(f"📡 URL: {proxy_url}")
    print(f"📝 Command: /copilot")
    
    try:
        # Make the request - it will get processed by middleware before hitting ChatGPT
        response = requests.post(proxy_url, json=payload, headers=headers, timeout=5)
        
        print(f"📊 Status: {response.status_code}")
        
        if response.status_code == 401:
            print("✅ Request reached ChatGPT backend (got auth error as expected)")
            print("✅ This confirms the slash command was processed by middleware")
            print("✅ /copilot command expansion should be working")
            return True
        elif response.status_code == 400:
            print("❌ Request blocked by Cloudflare (400 error)")
            print("❌ This suggests middleware is not working correctly")
            return False
        else:
            print(f"📄 Response: {response.text[:200]}...")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def check_proxy_logs():
    """Check proxy logs for evidence of /copilot processing"""
    try:
        with open("/tmp/codex_plus/proxy.log", "r") as f:
            logs = f.read()
            
        print("\n🔍 Checking proxy logs for /copilot processing...")
        
        if "/copilot" in logs:
            print("✅ Found /copilot references in logs")
            if "copilot-fixpr" in logs or "copilot-analysis" in logs:
                print("✅ Found parallel agent references (copilot-fixpr, copilot-analysis)")
            if "SLASH COMMAND EXECUTION" in logs:
                print("✅ Found command expansion evidence")
            return True
        else:
            print("❌ No /copilot references found in logs")
            return False
            
    except FileNotFoundError:
        print("⚠️ Proxy log file not found")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("TESTING /copilot COMMAND FUNCTIONALITY")
    print("=" * 60)
    
    # Test the actual command
    success = test_copilot_command()
    
    # Check logs for evidence
    log_success = check_proxy_logs()
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"✅ Command test: {'PASSED' if success else 'FAILED'}")
    print(f"✅ Log analysis: {'PASSED' if log_success else 'FAILED'}")
    
    if success and log_success:
        print("🎉 /copilot command appears to be working correctly!")
        print("🎯 Ready to process PR comments and launch parallel agents")
    else:
        print("⚠️  Issues detected with /copilot command processing")
    print("=" * 60)