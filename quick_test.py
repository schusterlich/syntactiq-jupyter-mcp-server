#!/usr/bin/env python3
"""
Quick test script for get_notebook_info functionality.
Assumes Docker containers are already running.
"""

import asyncio
import httpx
import json

async def test_get_notebook_info():
    """Test the get_notebook_info tool directly."""
    
    print("🔸 Testing get_notebook_info tool...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test the MCP server health first
            health_response = await client.get("http://localhost:4040/api/healthz")
            if health_response.status_code != 200:
                print(f"❌ MCP Server not healthy: {health_response.status_code}")
                return
            
            health_data = health_response.json()
            print(f"✅ MCP Server healthy: {health_data.get('message', 'OK')}")
            
            # Now test the get_notebook_info tool
            tool_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "get_notebook_info",
                    "arguments": {}
                }
            }
            
            print("🔸 Calling get_notebook_info tool...")
            response = await client.post(
                "http://localhost:4040/mcp",
                json=tool_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )
            
            print(f"📝 Response status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    # Parse Server-Sent Events format
                    response_text = response.text.strip()
                    if "event: message" in response_text and "data: " in response_text:
                        # Extract JSON from SSE format
                        lines = response_text.split('\n')
                        json_str = ""
                        for line in lines:
                            if line.startswith("data: "):
                                json_str = line[6:]  # Remove "data: " prefix
                                break
                        
                        if json_str:
                            result = json.loads(json_str)
                        else:
                            print("❌ Could not find JSON data in SSE response")
                            print(f"📄 Raw response: {response_text}")
                            return
                    else:
                        # Try parsing as direct JSON
                        result = response.json()
                    
                    print(f"📄 Parsed result: {json.dumps(result, indent=2)}")
                    
                    # Check if there's an error in the response
                    if "result" in result:
                        result_data = result["result"]
                        
                        if result_data.get("isError", False):
                            content = result_data.get("content", [])
                            if content and len(content) > 0:
                                error_msg = content[0].get("text", "Unknown error")
                                print(f"❌ Tool error: {error_msg}")
                                
                                # Check for specific error patterns
                                if "_doc" in str(error_msg):
                                    print("🚨 CONFIRMED: This is the '_doc' attribute error!")
                                if "NoneType" in str(error_msg):
                                    print("🚨 CONFIRMED: notebook_connection is None!")
                            else:
                                print("❌ Error response but no content found")
                        else:
                            # Success case
                            content = result_data.get("content", [])
                            if content and len(content) > 0:
                                text_content = content[0].get("text", "")
                                try:
                                    tool_result = json.loads(text_content)
                                    print(f"✅ Tool succeeded! Result: {tool_result}")
                                    
                                    # Validate the result structure
                                    if isinstance(tool_result, dict):
                                        if "room_id" in tool_result and "total_cells" in tool_result:
                                            print("✅ Result has expected structure!")
                                        else:
                                            print("⚠️  Result missing expected fields")
                                    else:
                                        print(f"⚠️  Result is not a dict: {type(tool_result)}")
                                except json.JSONDecodeError:
                                    print(f"✅ Tool succeeded with text result: {text_content}")
                    else:
                        print(f"⚠️  Unexpected response structure: {result}")
                        
                except json.JSONDecodeError as e:
                    print(f"❌ Failed to parse JSON response: {e}")
                    print(f"📄 Raw response: {response.text}")
                    
            else:
                print(f"❌ HTTP error: {response.status_code}")
                print(f"📄 Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

async def test_debug_connection():
    """Test the debug_connection_status tool to get more info."""
    
    print("\n🔸 Testing debug_connection_status tool...")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            tool_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call", 
                "params": {
                    "name": "debug_connection_status",
                    "arguments": {}
                }
            }
            
            response = await client.post(
                "http://localhost:4040/mcp",
                json=tool_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )
            
            if response.status_code == 200:
                # Parse Server-Sent Events format
                response_text = response.text.strip()
                if "event: message" in response_text and "data: " in response_text:
                    # Extract JSON from SSE format
                    lines = response_text.split('\n')
                    json_str = ""
                    for line in lines:
                        if line.startswith("data: "):
                            json_str = line[6:]  # Remove "data: " prefix
                            break
                    
                    if json_str:
                        result = json.loads(json_str)
                        print(f"📄 Debug result: {json.dumps(result, indent=2)}")
                    else:
                        print("❌ Could not find JSON data in debug response")
                        print(f"📄 Raw response: {response_text}")
                else:
                    # Try parsing as direct JSON
                    result = response.json()
                    print(f"📄 Debug result: {json.dumps(result, indent=2)}")
            else:
                print(f"❌ Debug tool failed: {response.status_code}")
                print(f"📄 Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Debug test failed: {e}")

async def main():
    """Run all tests."""
    print("=" * 60)
    print("           Quick get_notebook_info Test")
    print("=" * 60)
    print()
    
    print("📋 Assumptions:")
    print("   • Docker containers are running")
    print("   • JupyterLab is accessible on localhost:8888") 
    print("   • MCP Server is accessible on localhost:4040")
    print("   • notebook.ipynb is open in JupyterLab")
    print()
    
    await test_debug_connection()
    await test_get_notebook_info()
    
    print()
    print("=" * 60)
    print("                    Test Complete")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main()) 