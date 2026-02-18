#!/usr/bin/env python3
"""
Test API Key Authentication on Deployed Server

This script tests API key authentication against the deployed Cloud Run server.
Use this to verify that API keys are working correctly in production.

Usage:
    python test_cloud_api_key.py <api_key>
    
Example:
    python test_cloud_api_key.py csm_live_AbCdEfGhIjKlMnOpQrStUvWxYz123456
"""

import sys
import httpx
import asyncio
from typing import Optional


# Your deployed Cloud Run URL
SERVER_URL = "https://customer-success-mcp-316962419897.us-central1.run.app"


async def test_health_endpoint():
    """Test health endpoint (no auth required)."""
    print("=" * 60)
    print("Test 1: Health Check (No Auth Required)")
    print("=" * 60)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{SERVER_URL}/health")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed")
                print(f"   Status: {data.get('status')}")
                print(f"   Service: {data.get('service')}")
                print(f"   Version: {data.get('version')}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


async def test_sse_without_key():
    """Test SSE endpoint without API key (should fail)."""
    print("\n" + "=" * 60)
    print("Test 2: SSE Without API Key (Should Fail with 401)")
    print("=" * 60)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{SERVER_URL}/sse")
            
            if response.status_code == 401:
                print(f"✅ Correctly rejected request without API key")
                print(f"   Status: 401 Unauthorized")
                return True
            else:
                print(f"❌ Unexpected status code: {response.status_code}")
                print(f"   Expected: 401 (authentication required)")
                return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


async def test_sse_with_invalid_key():
    """Test SSE endpoint with invalid API key (should fail)."""
    print("\n" + "=" * 60)
    print("Test 3: SSE With Invalid API Key (Should Fail with 401)")
    print("=" * 60)
    
    try:
        headers = {"X-API-Key": "csm_live_INVALID1234567890"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{SERVER_URL}/sse",
                headers=headers
            )
            
            if response.status_code == 401:
                print(f"✅ Correctly rejected invalid API key")
                print(f"   Status: 401 Unauthorized")
                return True
            else:
                print(f"❌ Unexpected status code: {response.status_code}")
                print(f"   Expected: 401 (invalid key)")
                return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


async def test_sse_with_valid_key(api_key: str):
    """Test SSE endpoint with valid API key (should succeed)."""
    print("\n" + "=" * 60)
    print("Test 4: SSE With Valid API Key (Should Succeed)")
    print("=" * 60)
    
    try:
        headers = {"X-API-Key": api_key}
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{SERVER_URL}/sse",
                headers=headers
            )
            
            if response.status_code == 200:
                print(f"✅ Successfully authenticated with API key")
                print(f"   Status: 200 OK")
                print(f"   Content-Type: {response.headers.get('content-type')}")
                return True
            elif response.status_code == 401:
                print(f"❌ API key rejected (401)")
                print(f"   This key may be invalid, revoked, or expired")
                return False
            else:
                print(f"❌ Unexpected status code: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


async def test_root_endpoint():
    """Test root endpoint (shows available endpoints)."""
    print("\n" + "=" * 60)
    print("Test 5: Root Endpoint (No Auth Required)")
    print("=" * 60)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{SERVER_URL}/")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Root endpoint accessible")
                print(f"   Service: {data.get('service')}")
                print(f"   Endpoints:")
                for name, path in data.get('endpoints', {}).items():
                    print(f"      {name}: {path}")
                return True
            else:
                print(f"❌ Root endpoint failed: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


async def main(api_key: Optional[str] = None):
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 5 + "CLOUD API KEY AUTHENTICATION TEST" + " " * 19 + "║")
    print("╚" + "=" * 58 + "╝")
    print(f"\nTesting server: {SERVER_URL}\n")
    
    all_passed = True
    
    # Test 1: Health check
    if not await test_health_endpoint():
        all_passed = False
    
    # Test 2: SSE without key
    if not await test_sse_without_key():
        all_passed = False
    
    # Test 3: SSE with invalid key
    if not await test_sse_with_invalid_key():
        all_passed = False
    
    # Test 4: SSE with valid key (if provided)
    if api_key:
        if not await test_sse_with_valid_key(api_key):
            all_passed = False
    else:
        print("\n" + "=" * 60)
        print("Test 4: SKIPPED (No API key provided)")
        print("=" * 60)
        print("ℹ️  To test with a valid API key, run:")
        print(f"   python {sys.argv[0]} <your-api-key>")
    
    # Test 5: Root endpoint
    if not await test_root_endpoint():
        all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    if all_passed:
        print("✅ All tests passed!")
        
        if api_key:
            print("\n✅ API key authentication is working correctly!")
            print("\nYour server is ready for production use.")
            print("\nNext steps:")
            print("1. Configure LibreChat with X-API-Key header")
            print("2. Update Claude Desktop config with API key")
            print("3. Test MCP Inspector with: npx @modelcontextprotocol/inspector")
            print("   sse " + SERVER_URL + " --header \"X-API-Key: <your-key>\"")
        else:
            print("\n⚠️  You didn't provide an API key to test.")
            print("\nTo fully test authentication:")
            print("1. Generate an API key using the generate_api_key tool")
            print("2. Run this script again with the key:")
            print(f"   python {sys.argv[0]} csm_live_...")
    else:
        print("❌ Some tests failed")
        print("\nTroubleshooting:")
        print("- Check server logs: gcloud run logs read --service customer-success-mcp")
        print("- Verify deployment: gcloud run services describe customer-success-mcp")
        print("- Check API key is valid and not expired")
        print("- See API_KEY_SETUP.md for configuration help")
    
    print("=" * 60)
    print()


if __name__ == "__main__":
    api_key = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not api_key:
        print("\n⚠️  No API key provided. Running partial tests only.")
        print(f"Usage: python {sys.argv[0]} <api_key>\n")
    
    asyncio.run(main(api_key))
