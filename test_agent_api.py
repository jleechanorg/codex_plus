#!/usr/bin/env python3
"""
Simple test script for agent management API endpoints
"""

import json
import requests
import sys
import time

BASE_URL = "http://localhost:10000"

def test_agent_api():
    """Test all agent management API endpoints"""
    print("🧪 Testing Agent Management API Endpoints\n")

    # Test health endpoint first
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Health endpoint working")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Could not connect to proxy: {e}")
        print("Make sure the proxy is running with: ./proxy.sh")
        return False

    # Test agent status endpoint
    print("\n2. Testing agent status endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/agents/status")
        if response.status_code == 200:
            print("✅ Agent status endpoint working")
            print(f"   Status: {response.json()}")
        else:
            print(f"❌ Agent status endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Agent status request failed: {e}")

    # Test list agents endpoint
    print("\n3. Testing list agents endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/agents")
        if response.status_code == 200:
            agents = response.json()
            print(f"✅ List agents endpoint working")
            print(f"   Found {len(agents)} agents")
            for agent in agents:
                print(f"   - {agent['id']}: {agent['name']}")
        else:
            print(f"❌ List agents endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ List agents request failed: {e}")

    # Test create agent endpoint
    print("\n4. Testing create agent endpoint...")
    test_agent = {
        "name": "Test Agent",
        "description": "A test agent for API validation",
        "tools": ["Read", "Write"],
        "model": "claude-3-5-sonnet-20241022",
        "temperature": 0.5,
        "capabilities": ["testing"],
        "tags": ["test", "api"]
    }

    try:
        response = requests.post(f"{BASE_URL}/agents", json=test_agent)
        if response.status_code == 201:
            created_agent = response.json()
            agent_id = created_agent['id']
            print(f"✅ Create agent endpoint working")
            print(f"   Created agent: {agent_id}")

            # Test get specific agent endpoint
            print("\n5. Testing get specific agent endpoint...")
            get_response = requests.get(f"{BASE_URL}/agents/{agent_id}")
            if get_response.status_code == 200:
                agent_data = get_response.json()
                print(f"✅ Get agent endpoint working")
                print(f"   Retrieved: {agent_data['name']}")
            else:
                print(f"❌ Get agent endpoint failed: {get_response.status_code}")

            # Test update agent endpoint
            print("\n6. Testing update agent endpoint...")
            update_data = {
                "description": "Updated test agent description",
                "temperature": 0.8
            }
            update_response = requests.put(f"{BASE_URL}/agents/{agent_id}", json=update_data)
            if update_response.status_code == 200:
                updated_agent = update_response.json()
                print(f"✅ Update agent endpoint working")
                print(f"   Updated description: {updated_agent['description']}")
                print(f"   Updated temperature: {updated_agent['temperature']}")
            else:
                print(f"❌ Update agent endpoint failed: {update_response.status_code}")
                print(f"   Response: {update_response.text}")

            # Test invoke agent endpoint
            print("\n7. Testing invoke agent endpoint...")
            invoke_data = {
                "task": "This is a test task for the agent",
                "working_directory": "/tmp"
            }
            invoke_response = requests.post(f"{BASE_URL}/agents/{agent_id}/invoke", json=invoke_data)
            if invoke_response.status_code == 200:
                invoke_result = invoke_response.json()
                print(f"✅ Invoke agent endpoint working")
                print(f"   Success: {invoke_result['success']}")
                print(f"   Duration: {invoke_result['duration']:.2f}s")
                if invoke_result['output']:
                    print(f"   Output preview: {invoke_result['output'][:100]}...")
            else:
                print(f"❌ Invoke agent endpoint failed: {invoke_response.status_code}")
                print(f"   Response: {invoke_response.text}")

            # Test invoke multiple agents endpoint
            print("\n8. Testing invoke multiple agents endpoint...")
            multi_invoke_data = {
                "agents": [agent_id],
                "task": "This is a test task for multiple agents",
                "working_directory": "/tmp"
            }
            multi_response = requests.post(f"{BASE_URL}/agents/invoke-multiple", json=multi_invoke_data)
            if multi_response.status_code == 200:
                multi_result = multi_response.json()
                print(f"✅ Invoke multiple agents endpoint working")
                print(f"   Results: {multi_result['successful_agents']}/{multi_result['total_agents']} successful")
                print(f"   Total duration: {multi_result['total_duration']:.2f}s")
            else:
                print(f"❌ Invoke multiple agents endpoint failed: {multi_response.status_code}")
                print(f"   Response: {multi_response.text}")

            # Test delete agent endpoint
            print("\n9. Testing delete agent endpoint...")
            delete_response = requests.delete(f"{BASE_URL}/agents/{agent_id}")
            if delete_response.status_code == 204:
                print(f"✅ Delete agent endpoint working")
                print(f"   Deleted agent: {agent_id}")
            else:
                print(f"❌ Delete agent endpoint failed: {delete_response.status_code}")
                print(f"   Response: {delete_response.text}")

        else:
            print(f"❌ Create agent endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")

    except Exception as e:
        print(f"❌ Create agent request failed: {e}")

    print("\n🎉 Agent Management API Testing Complete!")
    return True

if __name__ == "__main__":
    if test_agent_api():
        sys.exit(0)
    else:
        sys.exit(1)