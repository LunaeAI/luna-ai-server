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

# Configure logging for deployment
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('luna-server.log') if os.getenv('LOG_TO_FILE') else logging.NullHandler()
    ]
)

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
