"""
OAuth 2.1 Authorization Server for MCP.

Implements:
  - RFC8414  : OAuth 2.0 Authorization Server Metadata
  - RFC9728  : OAuth 2.0 Protected Resource Metadata
  - RFC7591  : Dynamic Client Registration
  - OAuth 2.1 Authorization Code + PKCE (required for all public clients)
  - Refresh token rotation
"""

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.db_service import db_service

logger = logging.getLogger(__name__)


class OAuthService:
    """
    Full OAuth 2.1 authorization server.

    Supports:
      - Authorization Code grant with PKCE (S256 required)
      - Refresh token grant
      - Dynamic client registration (RFC7591)
      - Server metadata discovery (RFC8414)
    """

    ACCESS_TOKEN_LIFETIME = 3600          # 1 hour
    REFRESH_TOKEN_LIFETIME = 86400 * 30   # 30 days
    AUTH_CODE_LIFETIME = 300              # 5 minutes

    # ─── Server Metadata (RFC8414) ───────────────────────────────────────────

    def get_server_metadata(self, base_url: str) -> Dict[str, Any]:
        """Return OAuth 2.0 Authorization Server Metadata (RFC8414)."""
        return {
            "issuer": base_url,
            "authorization_endpoint": f"{base_url}/authorize",
            "token_endpoint": f"{base_url}/token",
            "registration_endpoint": f"{base_url}/register",
            "scopes_supported": ["read", "write", "admin"],
            "response_types_supported": ["code"],
            "response_modes_supported": ["query"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_basic"],
            "revocation_endpoint": f"{base_url}/revoke",
        }

    def get_protected_resource_metadata(self, base_url: str) -> Dict[str, Any]:
        """Return OAuth 2.0 Protected Resource Metadata (RFC9728)."""
        return {
            "resource": base_url,
            "authorization_servers": [base_url],
            "scopes_supported": ["read", "write", "admin"],
            "bearer_methods_supported": ["header"],
        }

    # ─── Dynamic Client Registration (RFC7591) ───────────────────────────────

    def register_client(
        self,
        client_name: str,
        redirect_uris: List[str],
        grant_types: Optional[List[str]] = None,
        response_types: Optional[List[str]] = None,
        scope: Optional[str] = None,
        token_endpoint_auth_method: str = "none",
    ) -> Dict[str, Any]:
        """Register a new OAuth 2.1 client (RFC7591 Dynamic Client Registration)."""
        # Validate redirect URIs per OAuth 2.1 security requirements
        for uri in redirect_uris:
            if not (
                uri.startswith("http://localhost")
                or uri.startswith("http://127.0.0.1")
                or uri.startswith("https://")
                or "://" not in uri  # custom scheme e.g. myapp://callback
            ):
                raise ValueError(
                    f"Invalid redirect_uri '{uri}'. "
                    "Must be localhost, 127.0.0.1, HTTPS, or a custom scheme."
                )

        client_id = f"mcp_{secrets.token_urlsafe(16)}"
        client_secret = None
        if token_endpoint_auth_method != "none":
            client_secret = secrets.token_urlsafe(32)

        grant_types = grant_types or ["authorization_code"]
        response_types = response_types or ["code"]
        scope = scope or "read write"

        result = db_service.execute_query(
            """
            INSERT INTO oauth_clients
                (id, client_secret, client_name, redirect_uris, grant_types,
                 response_types, scope, token_endpoint_auth_method)
            VALUES
                (%(id)s, %(secret)s, %(name)s, %(redirect_uris)s, %(grant_types)s,
                 %(response_types)s, %(scope)s, %(auth_method)s)
            RETURNING id, client_name, redirect_uris, grant_types,
                      response_types, scope, token_endpoint_auth_method, created_at
            """,
            {
                "id": client_id,
                "secret": client_secret,
                "name": client_name,
                "redirect_uris": redirect_uris,
                "grant_types": grant_types,
                "response_types": response_types,
                "scope": scope,
                "auth_method": token_endpoint_auth_method,
            },
        )

        client = result["results"][0]
        response: Dict[str, Any] = {
            "client_id": client["id"],
            "client_name": client["client_name"],
            "redirect_uris": client["redirect_uris"],
            "grant_types": client["grant_types"],
            "response_types": client["response_types"],
            "scope": client["scope"],
            "token_endpoint_auth_method": client["token_endpoint_auth_method"],
            "client_id_issued_at": int(datetime.utcnow().timestamp()),
        }
        if client_secret:
            response["client_secret"] = client_secret
            response["client_secret_expires_at"] = 0  # 0 = never expires (RFC7591)

        logger.info(f"Registered OAuth client: {client_id} ({client_name})")
        return response

    def get_client(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a registered client by ID."""
        result = db_service.execute_query(
            "SELECT * FROM oauth_clients WHERE id = %(id)s",
            {"id": client_id},
        )
        if result["results"]:
            return result["results"][0]
        return None

    # ─── Authorization Code ───────────────────────────────────────────────────

    def create_auth_code(
        self,
        client_id: str,
        user_id: int,
        redirect_uri: str,
        scope: str,
        code_challenge: str,
        code_challenge_method: str = "S256",
    ) -> str:
        """Create a short-lived single-use authorization code."""
        code = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(seconds=self.AUTH_CODE_LIFETIME)

        db_service.execute_query(
            """
            INSERT INTO oauth_auth_codes
                (code, client_id, user_id, redirect_uri, scope,
                 code_challenge, code_challenge_method, expires_at)
            VALUES
                (%(code)s, %(client_id)s, %(user_id)s, %(redirect_uri)s, %(scope)s,
                 %(challenge)s, %(method)s, %(expires_at)s)
            """,
            {
                "code": code,
                "client_id": client_id,
                "user_id": user_id,
                "redirect_uri": redirect_uri,
                "scope": scope,
                "challenge": code_challenge,
                "method": code_challenge_method,
                "expires_at": expires_at,
            },
        )
        return code

    def _verify_pkce(
        self, code_verifier: str, code_challenge: str, method: str
    ) -> bool:
        """Verify PKCE code_verifier against stored code_challenge."""
        if method == "S256":
            digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
            computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
            return computed == code_challenge
        if method == "plain":
            return code_verifier == code_challenge
        return False

    def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: str,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Exchange an authorization code for access + refresh tokens (OAuth 2.1 §4.1.3)."""
        result = db_service.execute_query(
            """
            SELECT * FROM oauth_auth_codes
            WHERE code = %(code)s AND used = FALSE
            """,
            {"code": code},
        )

        if not result["results"]:
            raise ValueError("Invalid or already-used authorization code")

        auth_code = result["results"][0]

        # Resolve client_id from the auth code record if not provided
        if not client_id:
            client_id = auth_code["client_id"]
            logger.info(f"Resolved client_id from auth code: {client_id}")

        # Validate expiry
        expires = auth_code["expires_at"]
        if hasattr(expires, "tzinfo") and expires.tzinfo is not None:
            from datetime import timezone
            now = datetime.now(timezone.utc)
        else:
            now = datetime.utcnow()
        if now > expires.replace(tzinfo=None) if hasattr(expires, "tzinfo") else now > expires:
            raise ValueError("Authorization code has expired")

        if auth_code["client_id"] != client_id:
            raise ValueError("client_id mismatch")

        if auth_code["redirect_uri"] != redirect_uri:
            raise ValueError("redirect_uri mismatch")

        if not self._verify_pkce(
            code_verifier,
            auth_code["code_challenge"],
            auth_code["code_challenge_method"],
        ):
            raise ValueError("PKCE verification failed — invalid code_verifier")

        # Mark code as used (single-use)
        db_service.execute_query(
            "UPDATE oauth_auth_codes SET used = TRUE WHERE code = %(code)s",
            {"code": code},
        )

        return self._issue_tokens(
            client_id=client_id,
            user_id=auth_code["user_id"],
            scope=auth_code["scope"],
        )

    # ─── Token Issuance & Validation ─────────────────────────────────────────

    def _issue_tokens(
        self, client_id: str, user_id: int, scope: str
    ) -> Dict[str, Any]:
        """Create and store a new access + refresh token pair."""
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)

        access_expires = datetime.utcnow() + timedelta(seconds=self.ACCESS_TOKEN_LIFETIME)
        refresh_expires = datetime.utcnow() + timedelta(seconds=self.REFRESH_TOKEN_LIFETIME)

        access_hash = hashlib.sha256(access_token.encode()).hexdigest()
        refresh_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        db_service.execute_query(
            """
            INSERT INTO oauth_tokens
                (access_token_hash, refresh_token_hash, client_id, user_id, scope,
                 access_token_expires_at, refresh_token_expires_at)
            VALUES
                (%(a_hash)s, %(r_hash)s, %(client_id)s, %(user_id)s, %(scope)s,
                 %(a_exp)s, %(r_exp)s)
            """,
            {
                "a_hash": access_hash,
                "r_hash": refresh_hash,
                "client_id": client_id,
                "user_id": user_id,
                "scope": scope,
                "a_exp": access_expires,
                "r_exp": refresh_expires,
            },
        )

        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": self.ACCESS_TOKEN_LIFETIME,
            "refresh_token": refresh_token,
            "scope": scope,
        }

    def validate_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate a Bearer access token.
        Returns a dict with user info if valid, None otherwise.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        result = db_service.execute_query(
            """
            SELECT t.id, t.client_id, t.scope,
                   u.id AS user_id, u.username, u.email, u.scopes AS user_scopes
            FROM oauth_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.access_token_hash = %(hash)s
              AND t.revoked = FALSE
              AND t.access_token_expires_at > NOW()
            """,
            {"hash": token_hash},
        )

        if not result["results"]:
            return None
        return result["results"][0]

    def refresh_access_token(
        self, refresh_token: str, client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Issue a new token pair using a refresh token (rotation — old token revoked)."""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        result = db_service.execute_query(
            """
            SELECT * FROM oauth_tokens
            WHERE refresh_token_hash = %(hash)s
              AND revoked = FALSE
              AND refresh_token_expires_at > NOW()
            """,
            {"hash": token_hash},
        )

        if not result["results"]:
            raise ValueError("Invalid or expired refresh token")

        record = result["results"][0]

        # Resolve client_id from token record if not provided
        if not client_id:
            client_id = record["client_id"]
            logger.info(f"Resolved client_id from refresh token: {client_id}")

        if record["client_id"] != client_id:
            raise ValueError("client_id mismatch")

        # Revoke old token (rotation)
        db_service.execute_query(
            "UPDATE oauth_tokens SET revoked = TRUE WHERE refresh_token_hash = %(hash)s",
            {"hash": token_hash},
        )

        return self._issue_tokens(
            client_id=client_id,
            user_id=record["user_id"],
            scope=record["scope"],
        )

    def revoke_token(self, token: str) -> bool:
        """Revoke an access or refresh token."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        result = db_service.execute_query(
            """
            UPDATE oauth_tokens
            SET revoked = TRUE
            WHERE access_token_hash = %(hash)s OR refresh_token_hash = %(hash)s
            RETURNING id
            """,
            {"hash": token_hash},
        )
        return bool(result.get("results"))


# Global singleton
oauth_service = OAuthService()
