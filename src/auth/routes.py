"""
Authentication routes for Luna AI Server
FastAPI endpoints for user registration, login, and token refresh
"""

import logging
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from notion_client import Client, APIResponseError, APIErrorCode

from ..database.connection import get_database_session
from ..database.models import User
from .auth import (
    hash_password, 
    authenticate_user, 
    create_jwt_token, 
    get_user_from_token,
    is_token_expiring_soon
)

logger = logging.getLogger(__name__)

# Create router for auth endpoints
router = APIRouter(prefix="/auth", tags=["authentication"])

# Security scheme for Bearer token
security = HTTPBearer()

# Pydantic models for request/response
class UserRegistration(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Username (3-50 characters)")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    email: str = Field(..., max_length=255, description="Email address")
    tier: str = Field("free", description="User tier (free, premium, enterprise)")

class UserLogin(BaseModel):
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    tier: str

class UserResponse(BaseModel):
    id: int
    username: str
    tier: str
    email: str
    is_active: bool
    created_at: str

class RefreshRequest(BaseModel):
    token: str = Field(..., description="Current JWT token to refresh")

async def check_waitlist_status(email: str) -> bool:
    """
    Check if email is on the Notion waitlist database
    
    Args:
        email: Email address to check
        
    Returns:
        bool: True if email is on waitlist, False otherwise
        
    Raises:
        HTTPException: If there's an issue connecting to Notion or other API errors
    """
    try:
        # Get Notion credentials from environment variables
        notion_token = os.getenv("NOTION_TOKEN")
        notion_database_id = os.getenv("NOTION_DATABASE_ID")
        
        if not notion_token:
            logger.error("NOTION_TOKEN environment variable not set")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Waitlist service configuration error"
            )
        
        if not notion_database_id:
            logger.error("NOTION_DATABASE_ID environment variable not set")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Waitlist service configuration error"
            )
        
        # Initialize Notion client
        notion = Client(auth=notion_token)
        
        # Query the database for the email
        logger.info(f"Checking waitlist status for email: {email}")
        
        response = notion.databases.query(
            database_id=notion_database_id,
            filter={
                "property": "Email",  # Assuming the email column is named "Email"
                "email": {
                    "equals": email
                }
            }
        )
        
        # Check if any results were found
        results = response.get("results", [])
        is_on_waitlist = len(results) > 0
        
        if is_on_waitlist:
            logger.info(f"Email {email} found on waitlist")
        else:
            logger.info(f"Email {email} not found on waitlist")
        
        return is_on_waitlist
        
    except APIResponseError as error:
        logger.error(f"Notion API error while checking waitlist for {email}: {error}")
        
        if error.code == APIErrorCode.ObjectNotFound:
            # Database not found - this is a configuration issue
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Waitlist database not found"
            )
        elif error.code == APIErrorCode.Unauthorized:
            # Invalid token or insufficient permissions
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Waitlist service authentication error"
            )
        else:
            # Other API errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error checking waitlist status"
            )
            
    except Exception as e:
        logger.error(f"Unexpected error while checking waitlist for {email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error checking waitlist status"
        )

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegistration,
    db: Session = Depends(get_database_session)
):
    """
    Register a new user account
    
    Creates a new user with hashed password and returns JWT token
    """
    try:
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == user_data.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        
        # Check if email already exists
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
        
        # Check if email is on the waitlist
        is_waitlisted = await check_waitlist_status(user_data.email)
        if not is_waitlisted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email not found on waitlist. Please use the email address you used to sign up for the waitlist."
            )
        
        # Validate tier
        valid_tiers = ["free", "premium", "enterprise"]
        if user_data.tier not in valid_tiers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tier. Must be one of: {', '.join(valid_tiers)}"
            )
        
        # Create new user
        hashed_password = hash_password(user_data.password)
        new_user = User(
            username=user_data.username,
            password_hash=hashed_password,
            tier=user_data.tier,
            email=user_data.email,
            is_active=True
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Create JWT token
        token = create_jwt_token(new_user)
        
        logger.info(f"New user registered: {new_user.username} (ID: {new_user.id})")
        
        return TokenResponse(
            access_token=token,
            user_id=new_user.id,
            username=new_user.username,
            tier=new_user.tier
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during user registration: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during registration"
        )

@router.post("/login", response_model=TokenResponse)
async def login_user(
    login_data: UserLogin,
    db: Session = Depends(get_database_session)
):
    """
    Authenticate user and return JWT token
    """
    try:
        # Authenticate user
        user = await authenticate_user(db, login_data.username, login_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Create JWT token
        token = create_jwt_token(user)
        
        logger.info(f"User logged in: {user.username} (ID: {user.id})")
        
        return TokenResponse(
            access_token=token,
            user_id=user.id,
            username=user.username,
            tier=user.tier
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during user login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login"
        )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshRequest,
    db: Session = Depends(get_database_session)
):
    """
    Refresh JWT token using current valid token
    
    This endpoint allows clients to get a new token before the current one expires
    """
    try:
        # Get user from current token
        user = await get_user_from_token(db, refresh_data.token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Create new JWT token
        new_token = create_jwt_token(user)
        
        logger.info(f"Token refreshed for user: {user.username} (ID: {user.id})")
        
        return TokenResponse(
            access_token=new_token,
            user_id=user.id,
            username=user.username,
            tier=user.tier
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during token refresh: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during token refresh"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user(
    token: str = Depends(security),
    db: Session = Depends(get_database_session)
):
    """
    Get current user information from JWT token
    
    Useful for debugging and client-side user info display
    """
    try:
        # Extract token from Bearer scheme
        token_str = token.credentials
        
        # Get user from token
        user = await get_user_from_token(db, token_str)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        return UserResponse(
            id=user.id,
            username=user.username,
            tier=user.tier,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/check-refresh")
async def check_token_refresh(
    token: str = Depends(security),
    db: Session = Depends(get_database_session)
):
    """
    Check if token needs refresh
    
    Returns whether the current token is expiring soon and should be refreshed
    """
    try:
        # Extract token from Bearer scheme
        token_str = token.credentials
        
        # Verify token is still valid
        user = await get_user_from_token(db, token_str)
        if not user:
            return {
                "needs_refresh": True,
                "reason": "invalid_token",
                "message": "Token is invalid or expired"
            }
        
        # Check if token is expiring soon
        needs_refresh = is_token_expiring_soon(token_str)
        
        return {
            "needs_refresh": needs_refresh,
            "reason": "expiring_soon" if needs_refresh else "valid",
            "message": "Token expires soon" if needs_refresh else "Token is valid"
        }
        
    except Exception as e:
        logger.error(f"Error checking token refresh: {e}")
        return {
            "needs_refresh": True,
            "reason": "error",
            "message": "Error checking token status"
        }
