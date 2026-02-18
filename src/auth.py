"""Authentication and authorization functionality."""

from datetime import datetime, timedelta
from typing import Optional, Dict
import bcrypt
from jose import JWTError, jwt
from src.config import settings
from src.models import User, TokenData

# Pre-computed password hashes using bcrypt (generated offline)

# DEPRECATED: Mock user database (kept for backward compatibility)
# New users are stored in PostgreSQL via user_service.py
USERS_DB: Dict[str, Dict] = {

}


def verify_password(plain_password: str, hashed_password: bytes | str) -> bool:
    """Verify a password against its hash."""
    # Handle both bytes and string hashed passwords
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password)


def get_password_hash(password: str) -> bytes:
    """Generate password hash."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())


def get_user(username: str) -> Optional[User]:
    """
    Retrieve user from database.
    First tries PostgreSQL, falls back to hardcoded users if DB unavailable.
    """
    # Try to get from database first
    try:
        from src.user_service import UserService
        user_service = UserService()
        user_dict = user_service.get_user_by_username(username)
        
        if user_dict:
            # Remove hashed_password from dict before creating User object
            user_data = user_dict.copy()
            user_data.pop("hashed_password", None)
            return User(**user_data)
    except Exception as e:
        # Database not available, fall back to hardcoded users
        print(f"Database unavailable, using fallback auth: {e}")
    
    # Fallback to hardcoded users
    if username in USERS_DB:
        user_dict = USERS_DB[username].copy()
        user_dict.pop("hashed_password", None)
        return User(**user_dict)
    
    return None


def authenticate_user(username: str, password: str) -> Optional[User]:
    """
    Authenticate a user with username and password.
    Tries PostgreSQL first, falls back to hardcoded users.
    """
    # Try database authentication first
    try:
        from src.user_service import UserService
        user_service = UserService()
        user_dict = user_service.get_user_by_username(username)
        
        if user_dict:
            # Check if user is disabled
            if user_dict.get("disabled", False):
                return None
            
            # Verify password
            if verify_password(password, user_dict["hashed_password"]):
                # Return User object without password
                user_data = user_dict.copy()
                user_data.pop("hashed_password", None)
                return User(**user_data)
            return None
    except Exception as e:
        # Database not available, fall back to hardcoded users
        print(f"Database unavailable, using fallback auth: {e}")
    
    # Fallback to hardcoded users
    if username not in USERS_DB:
        return None
    
    user_data = USERS_DB[username]
    if not verify_password(password, user_data["hashed_password"]):
        return None
    
    return get_user(username)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """Decode and validate JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        username: str = payload.get("sub")
        if username is None:
            return None
        
        scopes = payload.get("scopes", [])
        token_data = TokenData(username=username, scopes=scopes)
        return token_data
    
    except JWTError:
        return None


def has_scope(token_data: TokenData, required_scope: str) -> bool:
    """Check if token has required scope."""
    return required_scope in token_data.scopes
