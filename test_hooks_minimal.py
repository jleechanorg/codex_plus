#!/usr/bin/env python3
"""
Minimal test to verify hooks work with Codex-sized payloads
"""
import requests
import json

def test_hooks_minimal():
    """Test hooks with a minimal but realistic payload"""
    
    # Minimal realistic payload similar to what Codex sends
    payload = {
        "model": "claude-3",
        "input": "help me debug this",
        "instructions": "You are a helpful coding assistant.",
        "stream": True,
        "tools": [],
        "reasoning": False
    }
    
    print(f"Testing payload size: {len(json.dumps(payload))} bytes")
    
    # Test the /responses endpoint (what Codex uses)
    try:
        response = requests.post(
            "http://localhost:3000/responses",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer dummy-token"
            },
            json=payload,
            timeout=10,
            stream=True  # Important for SSE
        )
        
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        # Check if pre-input hooks modified the request
        if response.status_code == 200:
            print("✅ Request succeeded - hooks likely working!")
            
            # Read a bit of the streaming response
            chunk_count = 0
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    chunk_count += 1
                    if chunk_count == 1:
                        print(f"First chunk: {chunk.decode('utf-8', errors='ignore')[:100]}...")
                    if chunk_count >= 3:  # Don't read too much
                        break
        else:
            print(f"❌ Request failed: {response.text[:500]}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")

if __name__ == "__main__":
    test_hooks_minimal()