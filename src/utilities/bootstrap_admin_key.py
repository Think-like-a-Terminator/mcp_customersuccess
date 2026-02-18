#!/usr/bin/env python3
"""
Bootstrap Admin API Key Generator

This script generates the first admin API key for the Customer Success MCP Server.
Use this key to access API key management tools and generate additional keys.

Usage:
    python bootstrap_admin_key.py
    
The generated key will have created_by='admin' and can manage other API keys.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from api_key_service import APIKeyService


def main():
    """Generate bootstrap admin API key."""
    print("\n" + "=" * 60)
    print("BOOTSTRAP ADMIN API KEY GENERATOR")
    print("=" * 60)
    print("\nThis will create an admin API key with full key management access.\n")
    
    # Get key details
    name = input("Enter key name (e.g., 'Bootstrap Admin Key'): ").strip()
    if not name:
        name = "Bootstrap Admin Key"
    
    description = input("Enter description (optional): ").strip()
    if not description:
        description = "Initial admin key for API key management"
    
    expires = input("Expiration in days (leave empty for never): ").strip()
    expires_in_days = int(expires) if expires else None
    
    print("\n" + "-" * 60)
    print("Creating admin API key...")
    print("-" * 60)
    
    try:
        service = APIKeyService()
        result = service.create_api_key(
            name=name,
            description=description,
            created_by="admin",  # This is the key - created_by='admin'
            expires_in_days=expires_in_days
        )
        
        if result and result.get("api_key"):
            print("\n✅ ADMIN API KEY CREATED SUCCESSFULLY!\n")
            print("=" * 60)
            print("⚠️  SAVE THIS KEY NOW - YOU WON'T SEE IT AGAIN!")
            print("=" * 60)
            print(f"\nAPI Key: {result['api_key']}")
            print(f"\nKey ID: {result['id']}")
            print(f"Key Prefix: {result['key_prefix']}")
            print(f"Name: {result['name']}")
            print(f"Created By: admin")
            if result.get('expires_at'):
                print(f"Expires: {result['expires_at']}")
            else:
                print("Expires: Never")
            
            print("\n" + "=" * 60)
            print("NEXT STEPS:")
            print("=" * 60)
            print("1. Copy the API key above and save it securely")
            print("2. Use this key to connect to your MCP server:")
            print(f'   X-API-Key: {result["api_key"][:20]}...')
            print("3. Use this key to generate additional API keys:")
            print("   generate_api_key(name='Client Key', description='...')")
            print("4. This admin key can list, revoke, and delete other keys")
            print("\n✅ Setup complete! Your server is ready for production.\n")
            
        else:
            print(f"\n❌ Failed to create API key\n")
            return 1
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\nTroubleshooting:")
        print("- Make sure PostgreSQL is running")
        print("- Check database credentials in .env file")
        print("- Verify api_keys table exists (run init-db.sql)")
        print()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
