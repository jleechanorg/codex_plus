#!/usr/bin/env python3
"""
LiteLLM Proxy Server for Codex-Plus
Handles multi-provider LLM routing with cost tracking, load balancing, and streaming
"""

import os
import sys
import asyncio
import uvicorn
from pathlib import Path

# Import LiteLLM proxy app
try:
    from litellm.proxy.proxy_server import app, initialize
except ImportError as e:
    print(f"Error importing LiteLLM proxy: {e}")
    print("Please install LiteLLM with proxy support: pip install 'litellm[proxy]'")
    sys.exit(1)

def main():
    """Start LiteLLM proxy server"""
    
    # Configuration
    config_path = Path(__file__).parent / "config" / "litellm_config.yaml"
    host = os.getenv("LITELLM_HOST", "127.0.0.1")
    port = int(os.getenv("LITELLM_PORT", "4000"))
    
    print(f"🚀 Starting LiteLLM Proxy Server")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Config: {config_path}")
    
    # Verify config file exists
    if not config_path.exists():
        print(f"❌ Configuration file not found: {config_path}")
        print("   Creating a basic configuration...")
        config_path.parent.mkdir(exist_ok=True)
        
        # Create minimal config
        basic_config = """model_list:
  - model_name: gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY

general_settings:
  cost_tracking: true
  stream: true
"""
        config_path.write_text(basic_config)
        print(f"✅ Created basic config at {config_path}")
    
    # Initialize the proxy with our configuration
    try:
        # Set config file path
        os.environ["LITELLM_CONFIG_PATH"] = str(config_path)
        
        # Initialize LiteLLM
        initialize(
            config=str(config_path),
            telemetry=False,
            server_host=host,
            server_port=port
        )
        
        print(f"✅ LiteLLM Proxy initialized")
        print(f"   Health check: http://{host}:{port}/health")
        print(f"   OpenAI compatible: http://{host}:{port}/v1/chat/completions")
        
        # Start the server
        uvicorn.run(
            app,
            host=host,
            port=port,
            access_log=True,
            log_level="info"
        )
        
    except Exception as e:
        print(f"❌ Failed to start LiteLLM proxy: {e}")
        print(f"   Check your configuration in {config_path}")
        sys.exit(1)

if __name__ == "__main__":
    main()