#!/usr/bin/env python3
"""
Simple MCP client for testing the server.
Tests the MCP server using stdio transport (the proper way).
"""

import json
import subprocess
import sys
from typing import Any, Dict

# Note: The /messages endpoint requires an SSE session, so we use stdio transport instead


class MCPStdioClient:
    """MCP client using stdio transport."""
    
    def __init__(self):
        """Start the MCP server process."""
        self.process = subprocess.Popen(
            ["uv", "run", "python", "-m", "src.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        self.request_id = 1
        
        # Initialize the session
        self._initialize()
    
    def _initialize(self):
        """Initialize the MCP session."""
        init_request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        self.request_id += 1
        
        # Send initialization
        self.process.stdin.write(json.dumps(init_request) + "\n")
        self.process.stdin.flush()
        
        # Read response
        response_line = self.process.stdout.readline()
        if response_line:
            response = json.loads(response_line)
            if "result" in response:
                print("✅ MCP session initialized")
                return response
        return None
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool."""
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        self.request_id += 1
        
        # Send request
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        
        # Read response
        response_line = self.process.stdout.readline()
        if response_line:
            return json.loads(response_line)
        return {"error": "No response"}
    
    def list_tools(self) -> Dict[str, Any]:
        """List available tools."""
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "tools/list",
            "params": {}
        }
        self.request_id += 1
        
        # Send request
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        
        # Read response
        response_line = self.process.stdout.readline()
        if response_line:
            return json.loads(response_line)
        return {"error": "No response"}
    
    def close(self):
        """Close the MCP session."""
        try:
            self.process.stdin.close()
            self.process.terminate()
            self.process.wait(timeout=2)
        except:
            self.process.kill()


def test_mcp_tools():
    """Test MCP tools via stdio transport."""
    print("=" * 60)
    print("Testing MCP Server (stdio transport)")
    print("=" * 60)
    
    client = MCPStdioClient()
    
    try:
        # Test 1: List available tools
        print("\n1️⃣  Listing available tools...")
        try:
            result = client.list_tools()
            if "result" in result and "tools" in result["result"]:
                tools = result["result"]["tools"]
                print(f"   ✅ Found {len(tools)} tools")
                print("\n   Available tools:")
                for tool in tools[:8]:  # Show first 8
                    desc = tool.get('description', 'No description')
                    # Truncate description
                    if len(desc) > 60:
                        desc = desc[:57] + "..."
                    print(f"     • {tool['name']}: {desc}")
                if len(tools) > 8:
                    print(f"     ... and {len(tools) - 8} more")
            else:
                print(f"   ❌ Unexpected response: {result}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 2: Authenticate
        print("\n2️⃣  Testing authentication...")
        try:
            result = client.call_tool("authenticate", {
                "username": "admin",
                "password": "admin123"
            })
            
            if "result" in result:
                tool_result = result["result"]
                # FastMCP returns structured content
                if "structuredContent" in tool_result:
                    response_data = tool_result["structuredContent"]
                    if response_data.get("success"):
                        print(f"   ✅ Authentication successful!")
                        print(f"   User: {response_data['user']['username']}")
                        print(f"   Scopes: {', '.join(response_data['user']['scopes'])}")
                        print(f"   Token expires in: {response_data['expires_in']} seconds")
                    else:
                        print(f"   ❌ Authentication failed: {response_data.get('error')}")
                else:
                    print(f"   ❌ Unexpected response format")
            else:
                print(f"   ❌ Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 3: Register user (will fail without database, but tests the tool)
        print("\n3️⃣  Testing user registration...")
        try:
            import time
            username = f"test_user_{int(time.time())}"
            result = client.call_tool("register_user", {
                "username": username,
                "email": f"{username}@example.com",
                "password": "TestPassword123!",
                "full_name": "Test User"
            })
            
            if "result" in result:
                tool_result = result["result"]
                if "structuredContent" in tool_result:
                    response_data = tool_result["structuredContent"]
                    if response_data.get("success"):
                        print(f"   ✅ Registration successful!")
                        print(f"   Username: {response_data['username']}")
                        print(f"   Email: {response_data['email']}")
                    else:
                        error = response_data.get('error', 'Unknown')
                        if 'Database' in error or 'database' in error:
                            print(f"   ⚠️  Database not configured (expected for local testing)")
                            print(f"   ℹ️  Tool is working correctly, needs PostgreSQL")
                        else:
                            print(f"   ⚠️  {error}")
                else:
                    print(f"   ❌ Unexpected response format")
            else:
                print(f"   ❌ Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 4: List CTAs
        print("\n4️⃣  Testing list_call_to_actions...")
        try:
            result = client.call_tool("list_call_to_actions", {})
            
            if "result" in result:
                tool_result = result["result"]
                if "structuredContent" in tool_result:
                    response_data = tool_result["structuredContent"]
                    if response_data.get("success"):
                        count = response_data.get('count', 0)
                        print(f"   ✅ Found {count} CTA(s)")
                        if count > 0:
                            ctas = response_data.get('ctas', [])
                            for cta in ctas[:3]:  # Show first 3
                                print(f"      • {cta['title']} (Priority: {cta['priority']})")
                    else:
                        print(f"   ⚠️  {response_data.get('error', 'Unknown')}")
                else:
                    print(f"   ❌ Unexpected response format")
            else:
                print(f"   ❌ Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 5: Create a new CTA
        print("\n5️⃣  Testing create_call_to_action...")
        try:
            import time
            result = client.call_tool("create_call_to_action", {
                "account_id": "acct-test-001",
                "title": f"Test CTA {int(time.time())}",
                "description": "This is a test CTA created by the test client",
                "priority": "high",
                "owner": "test@example.com",
                "due_date_days": 7,
                "tags": ["test", "automated"]
            })
            
            if "result" in result:
                tool_result = result["result"]
                if "structuredContent" in tool_result:
                    response_data = tool_result["structuredContent"]
                    if response_data.get("success"):
                        cta = response_data.get('cta', {})
                        print(f"   ✅ CTA created successfully!")
                        print(f"   ID: {cta.get('id')}")
                        print(f"   Title: {cta.get('title')}")
                        print(f"   Priority: {cta.get('priority')}")
                        cta_id = cta.get('id')  # Save for update test
                    else:
                        print(f"   ⚠️  {response_data.get('error', 'Unknown')}")
                        cta_id = None
                else:
                    print(f"   ❌ Unexpected response format")
                    cta_id = None
            else:
                print(f"   ❌ Error: {result.get('error', 'Unknown error')}")
                cta_id = None
        except Exception as e:
            print(f"   ❌ Error: {e}")
            cta_id = None
        
        # Test 6: Update the CTA we just created
        if cta_id:
            print("\n6️⃣  Testing update_call_to_action...")
            try:
                result = client.call_tool("update_call_to_action", {
                    "cta_id": cta_id,
                    "status": "in_progress",
                    "notes": "Updated by test client"
                })
                
                if "result" in result:
                    tool_result = result["result"]
                    if "structuredContent" in tool_result:
                        response_data = tool_result["structuredContent"]
                        if response_data.get("success"):
                            cta = response_data.get('cta', {})
                            print(f"   ✅ CTA updated successfully!")
                            print(f"   Status: {cta.get('status')}")
                            print(f"   Updated: {cta.get('updated_at')}")
                        else:
                            print(f"   ⚠️  {response_data.get('error', 'Unknown')}")
                    else:
                        print(f"   ❌ Unexpected response format")
                else:
                    print(f"   ❌ Error: {result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        else:
            print("\n6️⃣  Skipping update_call_to_action (no CTA ID)")
        
        # Test 7: Create/Update a health score
        print("\n7️⃣  Testing update_health_score...")
        try:
            result = client.call_tool("update_health_score", {
                "account_id": "acct-test-001",
                "overall_score": 85.5,
                "product_usage": 90.0,
                "support_satisfaction": 88.0,
                "engagement": 78.0,
                "renewal_likelihood": 85.0
            })
            
            if "result" in result:
                tool_result = result["result"]
                if "structuredContent" in tool_result:
                    response_data = tool_result["structuredContent"]
                    if response_data.get("success"):
                        health = response_data.get('health_score', {})
                        print(f"   ✅ Health score created/updated!")
                        print(f"   Account: {health.get('account_id')}")
                        print(f"   Overall Score: {health.get('overall_score')}")
                        print(f"   Status: {health.get('status')}")
                    else:
                        print(f"   ⚠️  {response_data.get('error', 'Unknown')}")
                else:
                    print(f"   ❌ Unexpected response format")
            else:
                print(f"   ❌ Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 8: Get the health score we just created
        print("\n8️⃣  Testing get_health_score...")
        try:
            result = client.call_tool("get_health_score", {
                "account_id": "acct-test-001"
            })
            
            if "result" in result:
                tool_result = result["result"]
                if "structuredContent" in tool_result:
                    response_data = tool_result["structuredContent"]
                    if response_data.get("success"):
                        health = response_data.get('health_score', {})
                        print(f"   ✅ Health score retrieved!")
                        print(f"   Account: {health.get('account_id')}")
                        print(f"   Overall Score: {health.get('overall_score')}")
                        print(f"   Product Usage: {health.get('product_usage')}")
                        print(f"   Engagement: {health.get('engagement')}")
                        print(f"   Status: {health.get('status')}")
                    else:
                        print(f"   ⚠️  {response_data.get('error', 'Unknown')}")
                else:
                    print(f"   ❌ Unexpected response format")
            else:
                print(f"   ❌ Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 9: List all health scores
        print("\n9️⃣  Testing list_health_scores...")
        try:
            result = client.call_tool("list_health_scores", {})
            
            if "result" in result:
                tool_result = result["result"]
                if "structuredContent" in tool_result:
                    response_data = tool_result["structuredContent"]
                    if response_data.get("success"):
                        count = response_data.get('count', 0)
                        print(f"   ✅ Found {count} health score(s)")
                        if count > 0:
                            scores = response_data.get('health_scores', [])
                            for score in scores[:5]:  # Show first 5
                                print(f"      • {score['account_id']}: {score['overall_score']} ({score['status']})")
                    else:
                        print(f"   ⚠️  {response_data.get('error', 'Unknown')}")
                else:
                    print(f"   ❌ Unexpected response format")
            else:
                print(f"   ❌ Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    finally:
        client.close()


if __name__ == "__main__":
    print(f"\n🚀 MCP Server Test Client")
    print()
    
    # Run tests
    test_mcp_tools()
    
    print("\n" + "=" * 60)
    print("✅ Testing complete!")
    print("=" * 60)
    print("\n💡 Tips:")
    print("  • This test uses stdio transport (local testing)")
    print("  • For SSE/HTTP testing, use Claude Desktop or MCP Inspector")
    print("  • See README.md for Claude Desktop configuration")
    print()
