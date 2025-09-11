#!/usr/bin/env python3
"""
Luna AI Multi-Client Streaming Server - Standalone Entry Point
This script runs the streaming server as a standalone executable supporting multiple clients
"""
import logging
import sys
import asyncio
import os
from dotenv import load_dotenv

import colorama
from colorama import Fore, Style

colorama.init(autoreset=False)

class ColorFormatter(logging.Formatter):
    """Custom formatter to add colors to log output"""

    def format(self, record):
        time_str = self.formatTime(record, self.datefmt)

        level_str = record.levelname
        if record.levelno >= logging.ERROR:
            colored_level = f"{Fore.RED}[{level_str}]{Style.RESET_ALL}"
        elif record.levelno >= logging.WARNING:
            colored_level = f"{Fore.YELLOW}[{level_str}]{Style.RESET_ALL}"
        elif record.levelno >= logging.INFO:
            colored_level = f"{Fore.GREEN}[{level_str}]{Style.RESET_ALL}"
        else:
            colored_level = f"{Fore.BLUE}[{level_str}]{Style.RESET_ALL}"

        message_str = record.getMessage()
        colored_message = f"{Fore.WHITE}{message_str}{Style.RESET_ALL}"

        colored_time = f"{Fore.LIGHTBLACK_EX}[{time_str}]{Style.RESET_ALL}"

        return f"{colored_time} {colored_level} {colored_message}"

# Configure logging for deployment
logging.basicConfig(
    level=logging.INFO,
    handlers=[]  # Clear default handlers
)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColorFormatter(datefmt="%H:%M:%S"))

root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)

from .runner.websocket_server import WebSocketServer
from ..database import init_database, close_database_connections
from ..auth import auth_router

load_dotenv()

def validate_environment():
    """Validate that all required environment variables are set"""
    required_vars = {
        "JWT_SECRET_KEY": "JWT secret key for token signing",
        "DB_PASSWORD": "Database password"
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"  {var}: {description}")
    
    # Check for PORT but don't require it (Cloud Run provides this automatically)
    if not os.getenv("PORT"):
        logger.warning("PORT not set in environment, using default 8080")
    
    if missing_vars:
        logger.error("Missing required environment variables:")
        for var in missing_vars:
            logger.error(var)
        logger.error("Please create a .env file based on .env.example")
        raise ValueError("Missing required environment variables")
    
    # Validate JWT_SECRET_KEY length (should be at least 32 characters for security)
    jwt_secret = os.getenv("JWT_SECRET_KEY")
    if len(jwt_secret) < 32:
        logger.error("JWT_SECRET_KEY must be at least 32 characters long for security")
        raise ValueError("JWT_SECRET_KEY too short")
    
    logger.info("Environment validation passed")

async def start_streaming_server_async():
    """Async method to start the server"""
    try:
        # Validate environment variables first
        validate_environment()
        
        # Initialize database
        logger.info("Initializing database...")
        await init_database()
        
        streaming_server = WebSocketServer()
        
        # Include auth routes
        streaming_server.app.include_router(auth_router)
        
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8080"))
        
        logger.info(f"Starting Luna AI Multi-Client Server on {host}:{port}")
        logger.info("Ready to accept multiple concurrent client connections")
        
        await streaming_server.start_server(host=host, port=port)
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)
    finally:
        # Close database connections on shutdown
        try:
            await close_database_connections()
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")

def main():
    """Main entry point for the standalone server"""
    try:
        asyncio.run(start_streaming_server_async())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
