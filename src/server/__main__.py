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

load_dotenv()

async def start_streaming_server_async():
    """Async method to start the server"""
    try:
        streaming_server = WebSocketServer()
        
        host = os.getenv("HOST", "0.0.0.0")
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
