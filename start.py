#!/usr/bin/env python3
"""
M1 Simple Passthrough Proxy - Startup Script
"""
import uvicorn
from main import app

if __name__ == "__main__":
    print("🚀 Starting M1 Simple Passthrough Proxy")
    print("📡 Forwarding requests to: https://api.anthropic.com")
    print("🏥 Health check: http://localhost:3000/health")
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=3000,
        log_level="info"
    )