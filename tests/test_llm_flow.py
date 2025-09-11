#!/usr/bin/env python3
"""
Test the full LLM execution flow
Simulates what would happen when Codex CLI sends a slash command
"""
import json
import asyncio
from codex_plus.llm_execution_middleware import LLMExecutionMiddleware

async def simulate_request():
    """Simulate a request from Codex CLI with a slash command"""
    
    print("🚀 Testing LLM Execution Flow")
    print("=" * 60)
    
    # Create middleware instance
    middleware = LLMExecutionMiddleware("https://chatgpt.com/backend-api/codex")
    
    # Test cases to try
    test_commands = [
        "/hello Claude",
        "/test auth.py",
        "/search TODO",
        "/explain this code:\ndef foo(x):\n    return x * 2"
    ]
    
    for command in test_commands:
        print(f"\n📝 Testing command: {command}")
        print("-" * 40)
        
        # Simulate Codex CLI request format
        codex_request = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": command}
            ],
            "stream": True
        }
        
        # Process through middleware
        modified = middleware.inject_execution_behavior(codex_request.copy())
        
        # Show what gets sent to the LLM
        print("\n🤖 Instructions sent to LLM:")
        if "messages" in modified:
            system_msg = modified["messages"][0]
            if system_msg["role"] == "system":
                # Show just the key parts of the system instruction
                instruction = system_msg["content"]
                lines = instruction.split('\n')
                
                # Show first 10 lines and last 5 lines
                if len(lines) > 20:
                    preview = '\n'.join(lines[:10]) + "\n...\n" + '\n'.join(lines[-5:])
                else:
                    preview = instruction
                
                print(preview)
        
        print("\n💬 User sees: " + command)
        print()
    
    print("=" * 60)
    print("\n✅ Test complete!")
    print("\n💡 Key insight: The LLM now receives behavioral instructions")
    print("   to execute commands rather than just expanded text.")
    print("\n🎯 Benefits:")
    print("   1. LLM understands it should execute, not converse")
    print("   2. Original slash command preserved for clarity")
    print("   3. LLM can use its training on command execution patterns")
    print("   4. More similar to how Claude Code CLI works")

if __name__ == "__main__":
    asyncio.run(simulate_request())
