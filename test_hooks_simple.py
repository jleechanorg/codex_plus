#!/usr/bin/env python3
"""
Simple test to verify hooks work with smaller payloads
"""
import requests
import json

def test_small_payload():
    """Test hooks with a small payload that won't hit size limits"""
    
    # Small test payload
    payload = {
        "model": "claude-3-sonnet",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False
    }
    
    # Test via proxy
    response = requests.post(
        "http://localhost:3000/v1/models",  # Non-streaming endpoint
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=10
    )
    
    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    if response.text:
        print(f"Body: {response.text[:200]}...")
    
    # Check for hook header
    if "X-Hooked" in response.headers:
        print("✅ Post-output hook applied successfully!")
    else:
        print("❌ Post-output hook not found")

if __name__ == "__main__":
    test_small_payload()