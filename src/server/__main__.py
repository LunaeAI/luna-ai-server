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

# Import colorama for colorful logging
import colorama
from colorama import Fore, Style

# Initialize colorama
colorama.init(autoreset=False)

class ColorFormatter(logging.Formatter):
    """Custom formatter to add colors to log output"""

    def format(self, record):
        # Format time
        time_str = self.formatTime(record, self.datefmt)

        # Format level name with color
        level_str = record.levelname
        if record.levelno >= logging.ERROR:
            colored_level = f"{Fore.RED}[{level_str}]{Style.RESET_ALL}"
        elif record.levelno >= logging.WARNING:
            colored_level = f"{Fore.YELLOW}[{level_str}]{Style.RESET_ALL}"
        elif record.levelno >= logging.INFO:
            colored_level = f"{Fore.GREEN}[{level_str}]{Style.RESET_ALL}"
        else:
            colored_level = f"{Fore.BLUE}[{level_str}]{Style.RESET_ALL}"

        # Format message with white color
        message_str = record.getMessage()
        colored_message = f"{Fore.WHITE}{message_str}{Style.RESET_ALL}"

        # Format time with grey color
        colored_time = f"{Fore.LIGHTBLACK_EX}[{time_str}]{Style.RESET_ALL}"

        # Return fully formatted and colored log message
        return f"{colored_time} {colored_level} {colored_message}"

# Configure logging for deployment
logging.basicConfig(
    level=logging.INFO,
    handlers=[]  # Clear default handlers
)

# Get the root logger and configure it with our color formatter
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Remove any existing handlers
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Create console handler with color formatter
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColorFormatter())

# Add console handler to root logger
root_logger.addHandler(console_handler)

# Get logger for this module
logger = logging.getLogger(__name__)

from .runner.websocket_server import WebSocketServer

load_dotenv()

async def create_server():
    """Create and configure the multi-client server"""
    # Create WebSocketServer instance (no longer needs AgentRunner in constructor)
    websocket_server = WebSocketServer()
    
    return websocket_server

async def start_streaming_server_async():
    """Async method to start the server"""
    try:
        streaming_server = await create_server()
        
        # Get configuration from environment variables for deployment
        host = os.getenv("HOST", "0.0.0.0")  # 0.0.0.0 for deployment
        port = int(os.getenv("PORT"))
        
        logger.info(f"Starting Luna AI Multi-Client Server on {host}:{port}")
        logger.info("Ready to accept multiple concurrent client connections")
        
        await streaming_server.start_server(host=host, port=port)
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

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
