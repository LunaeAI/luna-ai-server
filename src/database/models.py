"""
Database models for Luna AI Server
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from dataclasses import dataclass

Base = declarative_base()

@dataclass
class AgentUserContext:
    """
    Minimal user context exposed to the agent
    Contains only non-sensitive information needed for agent functionality
    """
    user_id: int
    username: str
    tier: str
    
    def __str__(self):
        return f"AgentUserContext(user_id={self.user_id}, username='{self.username}', tier='{self.tier}')"

class User(Base):
    """
    User model for storing user account information
    
    Attributes:
        id: Primary key
        username: Unique username for the user
        password_hash: Hashed password (never store plain text)
        tier: User subscription tier (e.g., 'free', 'premium', 'enterprise')
        email: User email address (optional)
        is_active: Whether the user account is active
        created_at: Timestamp when the account was created
        updated_at: Timestamp when the account was last updated
    """
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    tier = Column(String(20), nullable=False, default='free')
    email = Column(String(255), unique=True, nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', tier='{self.tier}')>"
    
    def to_agent_context(self) -> AgentUserContext:
        """
        Convert User model to minimal AgentUserContext
        Only exposes safe, non-sensitive fields to the agent
        """
        return AgentUserContext(
            user_id=self.id,
            username=self.username,
            tier=self.tier
        )
