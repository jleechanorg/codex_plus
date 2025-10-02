#!/usr/bin/env python3
import requests

# Test the middleware
url = "http://localhost:3000/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer test-key"
}
data = {
    "model": "gpt-4",
    "messages": [
        {"role": "user", "content": "/copilot-codex 2"}
    ],
    "stream": False
}

try:
    response = requests.post(url, headers=headers, json=data, timeout=5)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")
except Exception as e:
    print(f"Error: {e}")