#!/usr/bin/env python3
"""
Multi-client WebSocket communication module for Luna AI Agent
Unified WebSocket communication functions used by all tool modules
"""
import asyncio
import json
import uuid
import logging
from typing import Dict, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Multi-client WebSocket state
_client_websockets: Dict[str, WebSocket] = {}
_client_pending_responses: Dict[str, Dict[str, asyncio.Future]] = {}

def set_websocket_connection(client_id: str, websocket: WebSocket):
    """Set the WebSocket connection reference for a specific client"""
    global _client_websockets, _client_pending_responses
    _client_websockets[client_id] = websocket
    if client_id not in _client_pending_responses:
        _client_pending_responses[client_id] = {}
    logger.debug(f"WebSocket connection set for client {client_id}")

def remove_websocket_connection(client_id: str):
    """Remove the WebSocket connection reference for a specific client"""
    global _client_websockets, _client_pending_responses
    if client_id in _client_websockets:
        del _client_websockets[client_id]
    if client_id in _client_pending_responses:
        # Cancel any pending futures for this client
        for future in _client_pending_responses[client_id].values():
            if not future.done():
                future.cancel()
        del _client_pending_responses[client_id]
    logger.debug(f"WebSocket connection removed for client {client_id}")

def handle_websocket_response(client_id: str, response_data: Dict[str, Any]):
    """Handle incoming WebSocket response and resolve pending futures for a specific client"""
    global _client_pending_responses
    
    if client_id not in _client_pending_responses:
        return
    
    request_id = response_data.get("request_id")
    
    if request_id and request_id in _client_pending_responses[client_id]:
        future = _client_pending_responses[client_id].pop(request_id)
        if not future.done():
            future.set_result(response_data)

async def send_websocket_command(command_type: str, action: str, data: Optional[Dict[str, Any]] = None, client_id: str = None) -> Dict[str, Any]:
    """
    Send a command to the main process via WebSocket for a specific client.
    For 'list' and 'search' actions, waits for response with 15 second timeout.
    For other actions, fires and forgets.
    
    Args:
        command_type: The type of command (e.g., "memory_request", "reminder_request")
        action: The specific action to perform (e.g., "save", "search", "list", "delete")
        data: Optional data payload for the command
        client_id: The unique identifier for the client (required - from ToolContext)
        
    Returns:
        dict: {"status": "success|error", "message": Optional[error_message], "data": Optional[response_data]}
    """
    global _client_websockets, _client_pending_responses
    
    # client_id is now required (from ToolContext)
    if not client_id:
        return {"status": "error", "message": "client_id is required (from ToolContext)"}
    
    if client_id not in _client_websockets:
        return {"status": "error", "message": f"No WebSocket connection available for client {client_id}"}
    
    websocket = _client_websockets[client_id]
    request_id = str(uuid.uuid4())
    message = {
        "type": command_type,
        "action": action,
        "data": data or {},
        "request_id": request_id
        # Removed client_id from message payload - routing handled by WebSocket connection
    }
    
    # For 'list', 'search', and 'read' actions, wait for response
    if action in ['list', 'search', 'read']:
        future = asyncio.Future()
        _client_pending_responses[client_id][request_id] = future
        
        try:
            await websocket.send_text(json.dumps(message))
            response = await asyncio.wait_for(future, timeout=15.0)
            return response
        except asyncio.TimeoutError:
            # Clean up the pending future
            if request_id in _client_pending_responses[client_id]:
                del _client_pending_responses[client_id][request_id]
            return {"status": "error", "message": "Request timeout"}
        except Exception as e:
            # Clean up the pending future
            if request_id in _client_pending_responses[client_id]:
                del _client_pending_responses[client_id][request_id]
            return {"status": "error", "message": str(e)}
    else:
        # Fire and forget for other actions
        try:
            await websocket.send_text(json.dumps(message))
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}