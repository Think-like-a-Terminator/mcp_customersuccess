"""API Key service for managing API key authentication."""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from src.db_service import DatabaseService


class APIKeyService:
    """Service for managing API keys."""
    
    def __init__(self):
        """Initialize the API key service."""
        self.db = DatabaseService()
    
    def generate_api_key(self) -> str:
        """
        Generate a secure API key.
        Format: csm_live_{32_random_bytes}
        
        Returns:
            The plaintext API key (show this once to user)
        """
        random_bytes = secrets.token_urlsafe(32)
        return f"csm_live_{random_bytes}"
    
    def hash_api_key(self, api_key: str) -> str:
        """
        Hash an API key for storage.
        
        Args:
            api_key: The plaintext API key
            
        Returns:
            SHA256 hash of the API key
        """
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def get_key_prefix(self, api_key: str) -> str:
        """
        Get the prefix of an API key for display purposes.
        
        Args:
            api_key: The plaintext API key
            
        Returns:
            First 12 characters of the key (e.g., "csm_live_abc1")
        """
        return api_key[:12] if len(api_key) >= 12 else api_key
    
    def create_api_key(
        self,
        name: str,
        description: Optional[str] = None,
        created_by: Optional[str] = None,
        expires_in_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a new API key.
        
        Args:
            name: Name/label for the API key
            description: Optional description
            created_by: Username who created the key
            expires_in_days: Optional expiration in days
            
        Returns:
            Dict with the plaintext API key and metadata
        """
        # Generate API key
        api_key = self.generate_api_key()
        key_hash = self.hash_api_key(api_key)
        key_prefix = self.get_key_prefix(api_key)
        
        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        # Insert into database
        query = """
            INSERT INTO api_keys (
                key_hash, key_prefix, name, description, 
                created_by, expires_at, is_active
            ) VALUES (
                %(key_hash)s, %(key_prefix)s, %(name)s, %(description)s,
                %(created_by)s, %(expires_at)s, true
            )
            RETURNING id, key_prefix, name, created_at, expires_at
        """
        
        result = self.db.execute_query(
            query,
            {
                "key_hash": key_hash,
                "key_prefix": key_prefix,
                "name": name,
                "description": description,
                "created_by": created_by,
                "expires_at": expires_at,
            }
        )
        
        if not result or not result.get("results"):
            raise Exception("Failed to create API key")
        
        key_info = result["results"][0]
        
        return {
            "api_key": api_key,  # ONLY TIME THIS IS SHOWN
            "id": key_info['id'],
            "key_prefix": key_info['key_prefix'],
            "name": key_info['name'],
            "created_at": key_info['created_at'].isoformat(),
            "expires_at": key_info['expires_at'].isoformat() if key_info['expires_at'] else None,
            "warning": "Save this API key now. You won't be able to see it again!",
        }
    
    def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Validate an API key and return its information if valid.
        
        Args:
            api_key: The plaintext API key to validate
            
        Returns:
            API key info dict if valid, None if invalid
        """
        key_hash = self.hash_api_key(api_key)
        
        query = """
            SELECT id, key_prefix, name, created_by, 
                   is_active, expires_at, last_used_at
            FROM api_keys
            WHERE key_hash = %(key_hash)s
        """
        
        result = self.db.execute_query(query, {"key_hash": key_hash})
        
        if not result or not result.get("results"):
            return None
        
        key_info = result["results"][0]
        
        # Check if active
        if not key_info['is_active']:
            return None
        
        # Check if expired
        if key_info['expires_at'] and datetime.utcnow() > key_info['expires_at']:
            return None
        
        # Update last_used_at
        self._update_last_used(key_info['id'])
        
        return {
            "id": key_info['id'],
            "key_prefix": key_info['key_prefix'],
            "name": key_info['name'],
            "created_by": key_info['created_by'],
        }
    
    def _update_last_used(self, key_id: int) -> None:
        """Update the last_used_at timestamp for an API key."""
        query = """
            UPDATE api_keys
            SET last_used_at = CURRENT_TIMESTAMP
            WHERE id = %(key_id)s
        """
        self.db.execute_query(query, {"key_id": key_id})
    
    def list_api_keys(self, created_by: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all API keys (without plaintext keys).
        
        Args:
            created_by: Optional filter by creator username
            
        Returns:
            List of API key info dicts
        """
        if created_by:
            query = """
                SELECT id, key_prefix, name, description, created_by,
                       is_active, last_used_at, expires_at, created_at
                FROM api_keys
                WHERE created_by = %(created_by)s
                ORDER BY created_at DESC
            """
            params = {"created_by": created_by}
        else:
            query = """
                SELECT id, key_prefix, name, description, created_by,
                       is_active, last_used_at, expires_at, created_at
                FROM api_keys
                ORDER BY created_at DESC
            """
            params = {}
        
        results = self.db.execute_query(query, params)
        
        return [
            {
                "id": row['id'],
                "key_prefix": row['key_prefix'],
                "name": row['name'],
                "description": row['description'],
                "created_by": row['created_by'],
                "is_active": row['is_active'],
                "last_used_at": row['last_used_at'].isoformat() if row['last_used_at'] else None,
                "expires_at": row['expires_at'].isoformat() if row['expires_at'] else None,
                "created_at": row['created_at'].isoformat(),
            }
            for row in results
        ]
    
    def revoke_api_key(self, key_id: int, revoked_by: Optional[str] = None) -> bool:
        """
        Revoke (deactivate) an API key.
        
        Args:
            key_id: The ID of the API key to revoke
            revoked_by: Username who revoked the key
            
        Returns:
            True if successful, False if not found
        """
        query = """
            UPDATE api_keys
            SET is_active = false,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %(key_id)s
            RETURNING id
        """
        
        result = self.db.execute_query(query, {"key_id": key_id})
        return bool(result)
    
    def delete_api_key(self, key_id: int) -> bool:
        """
        Permanently delete an API key.
        
        Args:
            key_id: The ID of the API key to delete
            
        Returns:
            True if successful, False if not found
        """
        query = """
            DELETE FROM api_keys
            WHERE id = %(key_id)s
            RETURNING id
        """
        
        result = self.db.execute_query(query, {"key_id": key_id})
        return bool(result)
