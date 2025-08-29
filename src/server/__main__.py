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
colorama.init(autoreset=True)

class ColorFormatter(logging.Formatter):
    """Custom formatter to add colors to log output"""
    
    def format(self, record):
        # Get the original formatted message
        formatted_message = super().format(record)
        
        # Color the time (grey)
        time_str = f"[{record.asctime}]"
        colored_time = f"{Fore.LIGHTBLACK_EX}{time_str}{Style.RESET_ALL}"
        
        # Color the level name
        level_str = f"[{record.levelname}]"
        if record.levelno >= logging.ERROR:
            colored_level = f"{Fore.RED}{level_str}{Style.RESET_ALL}"
        elif record.levelno >= logging.WARNING:
            colored_level = f"{Fore.YELLOW}{level_str}{Style.RESET_ALL}"
        elif record.levelno >= logging.INFO:
            colored_level = f"{Fore.GREEN}{level_str}{Style.RESET_ALL}"
        else:
            colored_level = f"{Fore.BLUE}{level_str}{Style.RESET_ALL}"
        
        # Color the message (white)
        message_str = record.getMessage()
        colored_message = f"{Fore.WHITE}{message_str}{Style.RESET_ALL}"
        
        # Reconstruct the formatted string
        return f"{colored_time} {colored_level} {colored_message}"

# Configure logging for deployment
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create console handler with color formatter
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColorFormatter('[%(asctime)s] [%(levelname)s] %(message)s'))

# Add console handler
logger.addHandler(console_handler)

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
        port = int(os.getenv("PORT", 8765))
        
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
