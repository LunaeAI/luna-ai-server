"""
Database connection management for Luna AI Server
Handles PostgreSQL connection using SQLAlchemy
"""

import os
import logging
from typing import Generator
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from .models import Base

logger = logging.getLogger(__name__)

# Global variables for database engine and session factory
_engine: Engine = None
_SessionLocal: sessionmaker = None

def get_database_url() -> str:
    """
    Construct database URL from environment variables
    
    Returns:
        Database URL string for PostgreSQL connection
        
    Environment Variables:
        DB_HOST: Database host (default: localhost)
        DB_PORT: Database port (default: 5432) 
        DB_NAME: Database name (default: luna_db)
        DB_USER: Database username (default: luna_user)
        DB_PASSWORD: Database password (required)
    """
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    database = os.getenv("DB_NAME", "luna_db")
    username = os.getenv("DB_USER", "luna_user")
    password = os.getenv("DB_PASSWORD")
    
    if not password:
        raise ValueError("DB_PASSWORD environment variable is required")
    
    return f"postgresql://{username}:{password}@{host}:{port}/{database}"

def get_database_engine() -> Engine:
    """
    Get or create the database engine
    
    Returns:
        SQLAlchemy Engine instance
    """
    global _engine
    
    if _engine is None:
        database_url = get_database_url()
        _engine = create_engine(
            database_url,
            echo=os.getenv("DB_ECHO", "false").lower() == "true",  # Enable SQL logging if DB_ECHO=true
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,   # Recycle connections every hour
        )
        logger.info("Database engine created successfully")
    
    return _engine

def get_session_factory() -> sessionmaker:
    """
    Get or create the session factory
    
    Returns:
        SQLAlchemy sessionmaker instance
    """
    global _SessionLocal
    
    if _SessionLocal is None:
        engine = get_database_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logger.info("Database session factory created successfully")
    
    return _SessionLocal

def get_database_session() -> Generator[Session, None, None]:
    """
    Get a database session (for dependency injection)
    
    Yields:
        SQLAlchemy Session instance
        
    Usage:
        Used with FastAPI's Depends() for dependency injection
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

async def init_database() -> None:
    """
    Initialize the database by creating all tables
    
    This function should be called during server startup
    """
    try:
        engine = get_database_engine()
        
        # Create all tables defined in models
        Base.metadata.create_all(bind=engine)
        
        logger.info("Database tables created successfully")
        
    except SQLAlchemyError as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {e}")
        raise

async def close_database_connections() -> None:
    """
    Close all database connections
    
    This function should be called during server shutdown
    """
    global _engine, _SessionLocal
    
    try:
        if _engine:
            _engine.dispose()
            _engine = None
            logger.info("Database engine disposed successfully")
            
        _SessionLocal = None
        
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
        raise
