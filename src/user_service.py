"""User management service for registration and verification."""

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import bcrypt
from src.db_service import DatabaseService
from src.email_service import email_service
from src.config import settings


class UserService:
    """Service for managing user registration and authentication."""
    
    def __init__(self):
        """Initialize the user service."""
        self.db = DatabaseService()
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    
    def verify_admin(self, email: str, password: str) -> Dict[str, Any]:
        """
        Verify if a user is an admin by email and password.
        
        Checks the Cloud SQL database (customer_success.public.users) for:
        - Email exists
        - Password matches hashed_password
        - admin column is True
        
        Args:
            email: Admin's email address
            password: Admin's password
            
        Returns:
            Dict with success status and admin info or error message
        """
        try:
            # Query the users table for admin verification
            query = """
                SELECT email, hashed_password, scopes, username, full_name
                FROM users
                WHERE email = %(email)s
            """
            
            result = self.db.execute_query(query, {"email": email})
            
            if not result or not result.get("results"):
                return {
                    "success": False,
                    "error": "Email not found in the system"
                }
            
            user = result["results"][0]
            
            # Verify password
            if not self.verify_password(password, user['hashed_password']):
                return {
                    "success": False,
                    "error": "Invalid password"
                }
            
            # Check if user has admin scope
            user_scopes = user.get('scopes', [])
            if 'admin' not in user_scopes:
                return {
                    "success": False,
                    "error": "User is not an admin. Admin access required for this operation."
                }
            
            return {
                "success": True,
                "email": user['email'],
                "username": user.get('username'),
                "full_name": user.get('full_name'),
                "is_admin": True
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Admin verification failed: {str(e)}"
            }
    
    def generate_verification_token(self) -> str:
        """Generate a secure verification token."""
        return secrets.token_urlsafe(32)
    
    def register_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        admin: bool = False,
        send_verification_email: bool = True,
    ) -> Dict[str, Any]:
        """
        Register a new user.
        
        Args:
            username: Desired username (must be unique)
            email: User's email address (must be unique)
            password: Plain text password (will be hashed)
            full_name: Optional full name
            admin: Whether to grant admin privileges (default False)
            send_verification_email: Whether to send verification email (default True)
            
        Returns:
            Dict with user info and status
            
        Raises:
            Exception if username or email already exists
        """
        # Validate input
        if len(username) < 3:
            raise ValueError("Username must be at least 3 characters")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        if '@' not in email:
            raise ValueError("Invalid email address")
        
        # Check if username or email exists
        check_query = """
            SELECT username, email FROM users 
            WHERE username = %(username)s OR email = %(email)s
        """
        existing = self.db.execute_query(
            check_query,
            {"username": username, "email": email}
        )
        
        if existing and existing.get("results"):
            if existing["results"][0]['username'] == username:
                raise ValueError(f"Username '{username}' is already taken")
            if existing["results"][0]['email'] == email:
                raise ValueError(f"Email '{email}' is already registered")
        
        # Hash password
        hashed_password = self.hash_password(password)
        
        # Generate verification token
        verification_token = self.generate_verification_token()
        token_expires = datetime.utcnow() + timedelta(hours=24)
        
        # Build scopes
        scopes = ['read', 'write']
        if admin:
            scopes.append('admin')
        
        # Insert user
        insert_query = """
            INSERT INTO users (
                username, email, full_name, hashed_password, 
                verification_token, verification_token_expires,
                email_verified, scopes
            ) VALUES (
                %(username)s, %(email)s, %(full_name)s, %(hashed_password)s,
                %(verification_token)s, %(verification_token_expires)s,
                false, %(scopes)s
            )
            RETURNING id, username, email, full_name, scopes, created_at
        """
        
        result = self.db.execute_query(
            insert_query,
            {
                "username": username,
                "email": email,
                "full_name": full_name or username,
                "hashed_password": hashed_password,
                "verification_token": verification_token,
                "verification_token_expires": token_expires,
                "scopes": scopes,
            }
        )
        
        if not result or not result.get("results"):
            raise Exception("Failed to create user")
        
        user_info = result["results"][0]
        is_admin = 'admin' in (user_info.get('scopes') or [])
        
        # Send verification email (if requested and email provider is configured)
        email_status = {"sent": False, "reason": "not requested"}
        if send_verification_email:
            email_status = {"sent": False, "reason": "not attempted"}
            try:
                email_status = self._send_verification_email(email, verification_token, username)
            except Exception as e:
                # Don't fail registration if email fails
                print(f"Warning: Failed to send verification email: {e}")
                email_status = {"sent": False, "reason": str(e)}
        
        return {
            "id": user_info['id'],
            "username": user_info['username'],
            "email": user_info['email'],
            "full_name": user_info['full_name'],
            "admin": is_admin,
            "scopes": user_info.get('scopes', scopes),
            "email_verified": False,
            "verification_email": email_status,
            "created_at": user_info['created_at'].isoformat(),
            "message": "Registration successful!" + (
                " Verification email sent — check your inbox."
                if email_status.get("sent")
                else " No verification email sent (email provider not configured)."
            ),
        }
    
    def _send_verification_email(
        self,
        email: str,
        token: str,
        username: str,
    ) -> dict:
        """Send verification email to user via configured email provider.
        
        Uses SMTP or AWS SES if configured. Returns status dict.
        If no email provider is configured, logs a warning and returns gracefully.
        """
        if not email_service.is_configured:
            print(f"[INFO] No email provider configured. Skipping verification email for {username}.")
            return {
                "sent": False,
                "reason": "No email provider configured (set SMTP_HOST or AWS credentials)",
            }
        
        result = email_service.send_verification_email(
            to_email=email,
            username=username,
            verification_token=token,
        )
        
        if result["success"]:
            print(f"[INFO] Verification email sent to {email} via {result['provider']}")
        else:
            print(f"[WARN] Failed to send verification email to {email}: {result.get('error')}")
        
        return {
            "sent": result["success"],
            "provider": result.get("provider"),
            "error": result.get("error"),
        }
    
    def verify_email(self, token: str) -> Dict[str, Any]:
        """
        Verify a user's email address using their verification token.
        
        Args:
            token: The verification token from the email
            
        Returns:
            Dict with verification status
            
        Raises:
            Exception if token is invalid or expired
        """
        # Find user with this token
        query = """
            SELECT id, username, email, verification_token_expires, email_verified
            FROM users
            WHERE verification_token = %(token)s
        """
        
        result = self.db.execute_query(query, {"token": token})
        
        if not result or not result.get("results"):
            raise ValueError("Invalid verification token")
        
        user = result["results"][0]
        
        if user['email_verified']:
            return {
                "success": True,
                "message": "Email already verified",
                "username": user['username'],
            }
        
        # Check if token expired
        if datetime.utcnow() > user['verification_token_expires']:
            raise ValueError("Verification token has expired. Please request a new one.")
        
        # Update user as verified
        update_query = """
            UPDATE users
            SET email_verified = true,
                verification_token = NULL,
                verification_token_expires = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %(user_id)s
        """
        
        self.db.execute_query(update_query, {"user_id": user['id']})
        
        return {
            "success": True,
            "message": "Email verified successfully! You can now use all features.",
            "username": user['username'],
            "email": user['email'],
        }
    
    def resend_verification_email(self, email: str) -> Dict[str, Any]:
        """
        Resend verification email to a user.
        
        Args:
            email: User's email address
            
        Returns:
            Dict with status
        """
        # Find user
        query = """
            SELECT id, username, email, email_verified
            FROM users
            WHERE email = %(email)s
        """
        
        result = self.db.execute_query(query, {"email": email})
        
        if not result or not result.get("results"):
            raise ValueError("No account found with this email")
        
        user = result["results"][0]
        
        if user['email_verified']:
            return {
                "success": False,
                "message": "Email is already verified",
            }
        
        # Generate new token
        verification_token = self.generate_verification_token()
        token_expires = datetime.utcnow() + timedelta(hours=24)
        
        # Update token
        update_query = """
            UPDATE users
            SET verification_token = %(token)s,
                verification_token_expires = %(expires)s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %(user_id)s
        """
        
        self.db.execute_query(
            update_query,
            {
                "token": verification_token,
                "expires": token_expires,
                "user_id": user['id'],
            }
        )
        
        # Send email (we'll implement this async in the actual call)
        return {
            "success": True,
            "message": "Verification email sent! Please check your inbox.",
            "token": verification_token,  # For internal use
            "username": user['username'],
        }
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get user by username for authentication.
        
        Args:
            username: The username to look up
            
        Returns:
            User dict or None if not found
        """
        query = """
            SELECT id, username, email, full_name, hashed_password,
                   disabled, scopes, email_verified, created_at
            FROM users
            WHERE username = %(username)s
        """
        
        result = self.db.execute_query(query, {"username": username})
        
        # Check if query was successful and has results
        if not result.get("success") or not result.get("results"):
            return None
        
        user = result["results"][0]
        return {
            "username": user['username'],
            "email": user['email'],
            "full_name": user['full_name'],
            "hashed_password": user['hashed_password'],
            "disabled": user['disabled'],
            "scopes": user['scopes'],
            "email_verified": user['email_verified'],
        }
    
    def update_user(
        self,
        username: str,
        email: Optional[str] = None,
        password: Optional[str] = None,
        full_name: Optional[str] = None,
        disabled: Optional[bool] = None,
        admin: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing user's attributes.
        
        Args:
            username: Username of the user to update (required, used to identify user)
            email: New email address (optional)
            password: New password - will be hashed (optional)
            full_name: New full name (optional)
            disabled: Set disabled status (optional)
            admin: Set admin status - modifies scopes (optional)
            
        Returns:
            Updated user info
            
        Raises:
            ValueError if user not found or email already in use
        """
        # Check if user exists
        existing = self.get_user_by_username(username)
        if not existing:
            raise ValueError(f"User '{username}' not found")
        
        # Build dynamic update query
        updates = []
        params = {"username": username}
        
        if email is not None:
            # Check if email is already used by another user
            check_query = """
                SELECT username FROM users WHERE email = %(email)s AND username != %(username)s
            """
            check_result = self.db.execute_query(check_query, {"email": email, "username": username})
            if check_result.get("results"):
                raise ValueError(f"Email '{email}' is already in use by another user")
            updates.append("email = %(email)s")
            params["email"] = email
        
        if password is not None:
            if len(password) < 8:
                raise ValueError("Password must be at least 8 characters")
            hashed = self.hash_password(password)
            updates.append("hashed_password = %(hashed_password)s")
            params["hashed_password"] = hashed
        
        if full_name is not None:
            updates.append("full_name = %(full_name)s")
            params["full_name"] = full_name
        
        if disabled is not None:
            updates.append("disabled = %(disabled)s")
            params["disabled"] = disabled
        
        if admin is not None:
            # Modify scopes based on admin flag
            current_scopes = existing.get("scopes", ["read", "write"])
            if admin:
                # Add admin scope if not present
                if "admin" not in current_scopes:
                    current_scopes.append("admin")
            else:
                # Remove admin scope if present
                current_scopes = [s for s in current_scopes if s != "admin"]
            updates.append("scopes = %(scopes)s")
            params["scopes"] = current_scopes
        
        if not updates:
            raise ValueError("No fields to update")
        
        # Add updated_at
        updates.append("updated_at = NOW()")
        
        update_query = f"""
            UPDATE users
            SET {', '.join(updates)}
            WHERE username = %(username)s
            RETURNING id, username, email, full_name, disabled, scopes, updated_at
        """
        
        result = self.db.execute_query(update_query, params)
        
        if not result.get("success") or not result.get("results"):
            raise Exception(f"Failed to update user: {result.get('error', 'Unknown error')}")
        
        updated_user = result["results"][0]
        user_scopes = updated_user.get("scopes", [])
        return {
            "id": updated_user["id"],
            "username": updated_user["username"],
            "email": updated_user["email"],
            "full_name": updated_user["full_name"],
            "disabled": updated_user["disabled"],
            "admin": "admin" in user_scopes,
            "scopes": user_scopes,
            "updated_at": updated_user["updated_at"].isoformat() if updated_user.get("updated_at") else None,
        }
    
    def list_users(self, admin_only: bool = False) -> list[Dict[str, Any]]:
        """
        List all users (admin function).
        
        Args:
            admin_only: If True, only return admin users
            
        Returns:
            List of user dicts (without passwords)
        """
        if admin_only:
            query = """
                SELECT id, username, email, full_name, disabled, scopes, 
                       email_verified, created_at
                FROM users
                WHERE 'admin' = ANY(scopes)
                ORDER BY created_at DESC
            """
        else:
            query = """
                SELECT id, username, email, full_name, disabled, scopes,
                       email_verified, created_at
                FROM users
                ORDER BY created_at DESC
            """
        
        result = self.db.execute_query(query, {})
        
        if not result.get("success"):
            raise Exception(f"Failed to list users: {result.get('error', 'Unknown error')}")
        
        users = []
        for user in result.get("results", []):
            user_scopes = user.get("scopes", [])
            users.append({
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "full_name": user["full_name"],
                "disabled": user["disabled"],
                "admin": "admin" in user_scopes,
                "scopes": user_scopes,
                "email_verified": user["email_verified"],
                "created_at": user["created_at"].isoformat() if user.get("created_at") else None,
            })
        
        return users
