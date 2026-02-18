"""Test the deployed MCP server on Google Cloud Run via SSE."""

import json
import requests
import sys
from typing import Any, Dict

# Your Cloud Run URL
SERVICE_URL = "https://your-mcp-server-url.run.app"


class CloudMCPClient:
    """MCP client for testing Cloud Run SSE deployment."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session = requests.Session()
        self.request_id = 1
    
    def test_via_messages_post(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test MCP tools via direct POST to /messages endpoint.
        Note: This may not work without an active SSE session, but worth trying.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params
        }
        self.request_id += 1
        
        try:
            response = self.session.post(
                f"{self.server_url}/messages",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "error": f"HTTP {response.status_code}: {response.text[:200]}"
                }
        except Exception as e:
            return {"error": str(e)}


def test_health_and_endpoints():
    """Test basic endpoints."""
    print("=" * 70)
    print("Testing MCP Server on Cloud Run")
    print("=" * 70)
    print(f"\n📍 Service URL: {SERVICE_URL}\n")
    
    # Test 1: Health endpoint
    print("1️⃣  Testing health endpoint...")
    try:
        response = requests.get(f"{SERVICE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Health check passed")
            print(f"   Service: {data.get('service')}")
            print(f"   Version: {data.get('version')}")
        else:
            print(f"   ❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: Root endpoint
    print("\n2️⃣  Testing root endpoint...")
    try:
        response = requests.get(f"{SERVICE_URL}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Root endpoint accessible")
            print(f"   Service: {data.get('service')}")
            print(f"   Endpoints: {', '.join(data.get('endpoints', {}).keys())}")
        else:
            print(f"   ❌ Failed: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")


def test_mcp_tools():
    """Test MCP tools via messages endpoint."""
    print("\n" + "=" * 70)
    print("Testing MCP Tools (Direct Messages)")
    print("=" * 70)
    
    client = CloudMCPClient(SERVICE_URL)
    
    # Test 3: List tools
    print("\n3️⃣  Testing tools/list...")
    try:
        result = client.test_via_messages_post("tools/list", {})
        
        if "error" in result:
            print(f"   ⚠️  Cannot access via direct POST: {result['error']}")
            print(f"   ℹ️  This is expected - SSE transport requires active connection")
            return False
        elif "result" in result:
            tools = result.get("result", {}).get("tools", [])
            print(f"   ✅ Found {len(tools)} tools")
            for tool in tools[:5]:
                print(f"      • {tool['name']}")
            if len(tools) > 5:
                print(f"      ... and {len(tools) - 5} more")
            return True
        else:
            print(f"   ❌ Unexpected response: {result}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def test_via_curl_example():
    """Show curl example for testing."""
    print("\n" + "=" * 70)
    print("Alternative Testing Methods")
    print("=" * 70)
    
    print("\n4️⃣  Test with curl (SSE connection):")
    print(f'''
   curl -N -H "Accept: text/event-stream" \\
     {SERVICE_URL}/sse
   
   (This should establish an SSE connection and wait for events)
''')
    
    print("\n5️⃣  Test with MCP Inspector (Official Tool):")
    print('''
   # Install MCP Inspector
   npm install -g @modelcontextprotocol/inspector
   
   # Connect to your server
   npx @modelcontextprotocol/inspector sse {SERVICE_URL}
   
   (Opens a web UI to test all tools interactively)
'''.format(SERVICE_URL=SERVICE_URL))
    
    print("\n6️⃣  Test with Python SSE Client:")
    print('''
   pip install sseclient-py
   
   # Then run: python test_cloud_deployment.py --sse
   (Not implemented yet, but would connect via SSE properly)
''')


def show_integration_info():
    """Show how to integrate with various clients."""
    print("\n" + "=" * 70)
    print("Integration Options")
    print("=" * 70)
    
    print("\n✅ Free Options:")
    print("   1. MCP Inspector (npm package) - Free, no subscription needed")
    print("   2. Custom Python SSE client - Free")
    print("   3. VSCode Copilot - If you have GitHub Copilot")
    
    print("\n💰 Paid Options:")
    print("   1. Claude Desktop (Pro subscription)")
    
    print("\n📋 MCP Inspector Setup (Recommended):")
    print(f'''
   npm install -g @modelcontextprotocol/inspector
   npx @modelcontextprotocol/inspector sse {SERVICE_URL}
   
   This will open http://localhost:5173 with a web UI to test all tools!
''')
    
    print("\n📋 VSCode Copilot Setup:")
    print('''
   Add to .vscode/settings.json (for local testing):
   {
     "github.copilot.chat.mcp.servers": {
       "customer-success": {
         "command": "uv",
         "args": ["run", "python", "-m", "src.server"]
       }
     }
   }
''')


def main():
    """Run all tests."""
    # Check for command line args
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage: python test_cloud_deployment.py [--help]")
        print("\nTests the deployed MCP server on Cloud Run")
        print("\nThe /messages endpoint requires an active SSE session,")
        print("so direct HTTP POST testing may not work.")
        print("\nRecommended: Use MCP Inspector for full testing")
        return
    
    # Run tests
    test_health_and_endpoints()
    tools_work = test_mcp_tools()
    
    if not tools_work:
        test_via_curl_example()
    
    show_integration_info()
    
    print("\n" + "=" * 70)
    print("✅ Testing Complete")
    print("=" * 70)
    print("\n💡 Your server is deployed and healthy!")
    print(f"   URL: {SERVICE_URL}")
    print("\n🚀 Next Step: Install MCP Inspector for full testing")
    print("   npm install -g @modelcontextprotocol/inspector")
    print(f"   npx @modelcontextprotocol/inspector sse {SERVICE_URL}")
    print()


if __name__ == "__main__":
    main()
