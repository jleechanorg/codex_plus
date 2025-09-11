#!/usr/bin/env python3
"""
Test script for LLM execution middleware
Tests whether instructing the LLM to execute commands works better than expanding them
"""
import json
from codex_plus.llm_execution_middleware import LLMExecutionMiddleware

def test_execution_instruction():
    """Test that we generate proper execution instructions"""
    
    middleware = LLMExecutionMiddleware("https://api.openai.com")
    
    # Test detecting slash commands
    test_cases = [
        ("/test auth.py", [("test", "auth.py")]),
        ("/search TODO", [("search", "TODO")]),
        ("/git status", [("git", "status")]),
        ("/explain /refactor code", [("explain", "/refactor code")]),
        ("Run /test and then /lint", [("test", "and then"), ("lint", "")]),
    ]
    
    print("🧪 Testing slash command detection:")
    for text, expected in test_cases:
        detected = middleware.detect_slash_commands(text)
        status = "✅" if detected == expected else "❌"
        print(f"  {status} '{text}' -> {detected}")
    
    print("\n📝 Testing execution instruction generation:")
    
    # Test with a simple command
    commands = [("test", "auth.py")]
    instruction = middleware.create_execution_instruction(commands)
    print(f"\nFor command: /test auth.py")
    print("Generated instruction:")
    print("-" * 40)
    print(instruction[:500] + "..." if len(instruction) > 500 else instruction)
    print("-" * 40)
    
    print("\n🔧 Testing request modification:")
    
    # Test with Codex format
    codex_request = {
        "input": [{
            "type": "message",
            "role": "user",
            "content": [{
                "type": "input_text",
                "text": "/test auth.py"
            }]
        }]
    }
    
    modified = middleware.inject_execution_behavior(codex_request.copy())
    
    print("\nOriginal request:")
    print(json.dumps(codex_request, indent=2)[:200] + "...")
    
    print("\nModified request:")
    print(json.dumps(modified, indent=2)[:500] + "...")
    
    # Test with standard format
    standard_request = {
        "messages": [
            {"role": "user", "content": "/search TODO in the codebase"}
        ]
    }
    
    modified_standard = middleware.inject_execution_behavior(standard_request.copy())
    
    print("\n\nStandard format test:")
    print("Original:", json.dumps(standard_request, indent=2))
    print("\nModified (with system instruction):")
    print(json.dumps(modified_standard, indent=2)[:500] + "...")
    
    print("\n✅ Test complete!")
    
    # Show what the LLM would receive
    print("\n🤖 What the LLM sees:")
    print("=" * 50)
    if "messages" in modified_standard:
        for msg in modified_standard["messages"]:
            print(f"\n[{msg['role'].upper()}]:")
            print(msg['content'][:300] + "..." if len(msg['content']) > 300 else msg['content'])
    print("=" * 50)

if __name__ == "__main__":
    test_execution_instruction()
