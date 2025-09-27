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
_client_mcp_queues: Dict[str, asyncio.Queue] = {}

def set_websocket_connection(client_id: str, websocket: WebSocket):
    """Set the WebSocket connection reference for a specific client"""
    global _client_websockets, _client_pending_responses, _client_mcp_queues
    _client_websockets[client_id] = websocket
    if client_id not in _client_pending_responses:
        _client_pending_responses[client_id] = {}
    if client_id not in _client_mcp_queues:
        _client_mcp_queues[client_id] = asyncio.Queue()
    logger.debug(f"WebSocket connection set for client {client_id}")

def remove_websocket_connection(client_id: str):
    """Remove the WebSocket connection reference for a specific client"""
    global _client_websockets, _client_pending_responses, _client_mcp_queues
    if client_id in _client_websockets:
        del _client_websockets[client_id]
    if client_id in _client_pending_responses:
        # Cancel any pending futures for this client
        for future in _client_pending_responses[client_id].values():
            if not future.done():
                future.cancel()
        del _client_pending_responses[client_id]
    if client_id in _client_mcp_queues:
        del _client_mcp_queues[client_id]
    logger.debug(f"WebSocket connection removed for client {client_id}")

def handle_websocket_response(client_id: str, response_data: Dict[str, Any]):
    """Handle incoming WebSocket response and resolve pending futures for a specific client"""
    global _client_pending_responses, _client_mcp_queues
    
    # Handle null response data gracefully
    if response_data is None:
        logger.error(f"[WEBSOCKET] Received null response data for client {client_id}")
        return
    
    message_type = response_data.get("type", "")
    payload = response_data.get("payload", "")

    if "response" in message_type:
        request_id = payload.get("request_id")
        data = payload.get("data", {})
    
        if message_type == "mcp_response" and data is not None:
            logger.info(f"[WEBSOCKET] MCP response received for client {client_id}: {data}")
            asyncio.create_task(_client_mcp_queues[client_id].put(data))
            return
        
        if request_id and request_id in _client_pending_responses[client_id]:
            future = _client_pending_responses[client_id].pop(request_id)
            if not future.done():
                future.set_result(data)

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

    websocket = _client_websockets[client_id]
    request_id = str(uuid.uuid4())

    message = {
        "type": command_type,
        "action": action,
        "data": data or {},
        "request_id": request_id
    }

    future = asyncio.Future()
    _client_pending_responses[client_id][request_id] = future

    try:
        message_json = json.dumps(message)

        await websocket.send_text(message_json)

        response = await asyncio.wait_for(future, timeout=15.0)

        return response
    except Exception as e:
        logger.error(f"[{client_id}] {action} ERROR: {e}")

        if request_id in _client_pending_responses[client_id]:
            del _client_pending_responses[client_id][request_id]
            
        return {"status": "error", "message": str(e)}
    

def get_mcp_queue(client_id: str) -> Optional[asyncio.Queue]:
    """Get the MCP response queue for a specific client"""
    global _client_mcp_queues
    return _client_mcp_queues.get(client_id)