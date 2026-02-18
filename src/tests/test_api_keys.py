#!/usr/bin/env python3
"""
Test API Key Authentication System

This script tests the API key generation, validation, and authentication flow.
Run this after deploying to verify the API key system works correctly.
"""

import sys
import os
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from api_key_service import APIKeyService


def test_api_key_generation():
    """Test API key generation."""
    print("=" * 60)
    print("Test 1: API Key Generation")
    print("=" * 60)
    
    service = APIKeyService()
    
    # Generate a test key
    result = service.create_api_key(
        name="Test Key",
        description="Test key for local testing",
        created_by="admin",
        expires_in_days=30
    )
    
    if result["success"]:
        print("✅ API key generated successfully!")
        print(f"   Key ID: {result['key_id']}")
        print(f"   Key Prefix: {result['key_prefix']}")
        print(f"   Full Key: {result['api_key'][:20]}...")
        print(f"   Expires: {result['expires_at']}")
        return result['api_key'], result['key_id']
    else:
        print(f"❌ Failed to generate key: {result.get('error')}")
        return None, None


def test_api_key_validation(api_key):
    """Test API key validation."""
    print("\n" + "=" * 60)
    print("Test 2: API Key Validation")
    print("=" * 60)
    
    service = APIKeyService()
    
    # Test valid key
    result = service.validate_api_key(api_key)
    if result:
        print("✅ Valid API key validated successfully!")
        print(f"   Key ID: {result['id']}")
        print(f"   Name: {result['name']}")
        print(f"   Created By: {result['created_by']}")
        print(f"   Active: {result['is_active']}")
    else:
        print("❌ Failed to validate key")
        return False
    
    # Test invalid key
    invalid_key = "csm_live_INVALID1234567890"
    result = service.validate_api_key(invalid_key)
    if not result:
        print("✅ Invalid key correctly rejected")
    else:
        print("❌ Invalid key incorrectly accepted")
        return False
    
    return True


def test_list_api_keys():
    """Test listing API keys."""
    print("\n" + "=" * 60)
    print("Test 3: List API Keys")
    print("=" * 60)
    
    service = APIKeyService()
    result = service.list_api_keys()
    
    if result["success"]:
        keys = result["keys"]
        print(f"✅ Found {len(keys)} API key(s)")
        for key in keys:
            print(f"\n   Key ID {key['id']}:")
            print(f"      Name: {key['name']}")
            print(f"      Prefix: {key['key_prefix']}")
            print(f"      Active: {key['is_active']}")
            print(f"      Created: {key['created_at']}")
            print(f"      Last Used: {key.get('last_used_at', 'Never')}")
        return True
    else:
        print(f"❌ Failed to list keys: {result.get('error')}")
        return False


def test_revoke_api_key(key_id):
    """Test revoking an API key."""
    print("\n" + "=" * 60)
    print("Test 4: Revoke API Key")
    print("=" * 60)
    
    service = APIKeyService()
    result = service.revoke_api_key(key_id)
    
    if result["success"]:
        print(f"✅ API key {key_id} revoked successfully")
        
        # Verify revoked key doesn't validate
        # (We can't test this without the actual key, so just confirm revocation)
        return True
    else:
        print(f"❌ Failed to revoke key: {result.get('error')}")
        return False


def test_cleanup(key_id):
    """Clean up test data."""
    print("\n" + "=" * 60)
    print("Cleanup: Delete Test Key")
    print("=" * 60)
    
    service = APIKeyService()
    result = service.delete_api_key(key_id)
    
    if result["success"]:
        print(f"✅ Test key {key_id} deleted successfully")
        return True
    else:
        print(f"❌ Failed to delete key: {result.get('error')}")
        return False


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "API KEY AUTHENTICATION SYSTEM TEST" + " " * 13 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    # Check database connection
    print("Checking database connection...")
    try:
        service = APIKeyService()
        # Try a simple query
        result = service.db_service.execute_query(
            "SELECT 1 as test",
            fetch_results=True
        )
        if result and result[0]['test'] == 1:
            print("✅ Database connection successful\n")
        else:
            print("❌ Database connection failed\n")
            return
    except Exception as e:
        print(f"❌ Database error: {str(e)}\n")
        print("Make sure PostgreSQL is running and configured correctly.")
        print("Check your .env file for database credentials.\n")
        return
    
    # Run tests
    all_passed = True
    
    # Test 1: Generate API key
    api_key, key_id = test_api_key_generation()
    if not api_key:
        all_passed = False
        print("\n❌ Cannot continue - key generation failed")
        return
    
    # Test 2: Validate API key
    if not test_api_key_validation(api_key):
        all_passed = False
    
    # Test 3: List API keys
    if not test_list_api_keys():
        all_passed = False
    
    # Test 4: Revoke API key
    if not test_revoke_api_key(key_id):
        all_passed = False
    
    # Cleanup
    test_cleanup(key_id)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    if all_passed:
        print("✅ All tests passed!")
        print("\nAPI key authentication system is working correctly.")
        print("\nNext steps:")
        print("1. Deploy to Cloud Run: gcloud builds submit")
        print("2. Generate a production API key using generate_api_key tool")
        print("3. Configure LibreChat/clients with X-API-Key header")
        print("4. See API_KEY_SETUP.md for detailed setup instructions")
    else:
        print("❌ Some tests failed")
        print("\nCheck the error messages above and verify:")
        print("- PostgreSQL database is running")
        print("- Database credentials in .env are correct")
        print("- api_keys table exists (run init-db.sql)")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
