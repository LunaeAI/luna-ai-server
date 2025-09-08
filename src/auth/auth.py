"""
Authentication module for Luna AI Server
Handles JWT token creation, validation, and password hashing
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
import bcrypt
from sqlalchemy.orm import Session

from ..database.models import User

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = int(os.getenv("JWT_EXPIRATION_DAYS", "30"))

def get_jwt_secret_key() -> str:
    """
    Get JWT secret key from environment variable
    
    Returns:
        JWT secret key string
        
    Raises:
        ValueError: If JWT_SECRET_KEY is not set
    """
    if not JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY environment variable is required")
    return JWT_SECRET_KEY

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash
    
    Args:
        password: Plain text password
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    password_bytes = password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)

def create_jwt_token(user: User) -> str:
    """
    Create a JWT token for a user
    
    Args:
        user: User model instance
        
    Returns:
        JWT token string
    """
    now = datetime.now(timezone.utc)
    expiration = now + timedelta(days=JWT_EXPIRATION_DAYS)
    
    payload = {
        "user_id": user.id,
        "username": user.username,
        "tier": user.tier,
        "iat": now,
        "exp": expiration
    }
    
    secret_key = get_jwt_secret_key()
    token = jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)
    
    logger.info(f"Created JWT token for user {user.username} (ID: {user.id}), expires: {expiration}")
    return token

def verify_jwt_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT token
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload if valid, None if invalid
    """
    try:
        secret_key = get_jwt_secret_key()
        payload = jwt.decode(token, secret_key, algorithms=[JWT_ALGORITHM])
        
        # Check if token is expired (jwt.decode handles this, but let's be explicit)
        exp_timestamp = payload.get("exp")
        if exp_timestamp:
            exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
            if datetime.now(timezone.utc) > exp_datetime:
                logger.warning("JWT token is expired")
                return None
                
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error verifying JWT token: {e}")
        return None

def is_token_expiring_soon(token: str, days_threshold: int = 7) -> bool:
    """
    Check if a JWT token is expiring soon
    
    Args:
        token: JWT token string
        days_threshold: Number of days before expiration to consider "soon"
        
    Returns:
        True if token expires within the threshold, False otherwise
    """
    try:
        payload = verify_jwt_token(token)
        if not payload:
            return True  # Invalid token should be refreshed
            
        exp_timestamp = payload.get("exp")
        if not exp_timestamp:
            return True
            
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        threshold_datetime = datetime.now(timezone.utc) + timedelta(days=days_threshold)
        
        return exp_datetime <= threshold_datetime
        
    except Exception as e:
        logger.error(f"Error checking token expiration: {e}")
        return True  # Assume expired on error

async def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate a user with username and password
    
    Args:
        db: Database session
        username: Username
        password: Plain text password
        
    Returns:
        User model if authentication successful, None otherwise
    """
    try:
        # Find user by username
        user = db.query(User).filter(User.username == username).first()
        if not user:
            logger.warning(f"Authentication failed: User '{username}' not found")
            return None
        
        # Check if user is active
        if not user.is_active:
            logger.warning(f"Authentication failed: User '{username}' is deactivated")
            return None
        
        # Verify password
        if not verify_password(password, user.password_hash):
            logger.warning(f"Authentication failed: Invalid password for user '{username}'")
            return None
        
        logger.info(f"User '{username}' authenticated successfully")
        return user
        
    except Exception as e:
        logger.error(f"Error during authentication for user '{username}': {e}")
        return None

async def get_user_from_token(db: Session, token: str) -> Optional[User]:
    """
    Get user from JWT token
    
    Args:
        db: Database session
        token: JWT token string
        
    Returns:
        User model if token is valid and user exists, None otherwise
    """
    try:
        payload = verify_jwt_token(token)
        if not payload:
            return None
        
        user_id = payload.get("user_id")
        if not user_id:
            logger.warning("JWT token missing user_id")
            return None
        
        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"User with ID {user_id} from JWT token not found in database")
            return None
        
        # Check if user is still active
        if not user.is_active:
            logger.warning(f"User '{user.username}' from JWT token is deactivated")
            return None
        
        return user
        
    except Exception as e:
        logger.error(f"Error getting user from token: {e}")
        return None
