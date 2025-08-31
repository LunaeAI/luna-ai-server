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
    
    if client_id not in _client_pending_responses and client_id not in _client_mcp_queues:
        return
    
    message_type = response_data.get("type", "")
    
    if message_type == "mcp_response":
        logger.info(f"[WEBSOCKET] MCP response received for client {client_id}: {response_data}")
        if client_id in _client_mcp_queues:
            asyncio.create_task(_client_mcp_queues[client_id].put(response_data))
        else:
            logger.error(f"[WEBSOCKET] No MCP queue for client {client_id}")
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

    # Start timing
    operation_start = asyncio.get_event_loop().time()
    logger.info(f"[{client_id}] Starting {action} operation: {request_id}")

    message = {
        "type": command_type,
        "action": action,
        "data": data or {},
        "request_id": request_id
    }

    # For 'list', 'search', and 'read' actions, wait for response
    if action in ['list', 'search', 'read']:
        future = asyncio.Future()
        _client_pending_responses[client_id][request_id] = future

        try:
            # Time the JSON serialization
            json_start = asyncio.get_event_loop().time()
            message_json = json.dumps(message)
            json_end = asyncio.get_event_loop().time()
            json_time = json_end - json_start
            logger.info(f"[{client_id}] JSON serialization took {json_time:.4f}s")

            # Time the WebSocket send
            send_start = asyncio.get_event_loop().time()
            await websocket.send_text(message_json)
            send_end = asyncio.get_event_loop().time()
            send_time = send_end - send_start
            logger.info(f"[{client_id}] WebSocket send took {send_time:.4f}s")

            # Time the response wait
            logger.info(f"[{client_id}] Waiting for response...")
            response = await asyncio.wait_for(future, timeout=15.0)
            response_received = asyncio.get_event_loop().time()
            wait_time = response_received - send_end
            total_time = response_received - operation_start

            logger.info(f"[{client_id}] Response received after {wait_time:.4f}s")
            logger.info(f"[{client_id}] Total {action} operation took {total_time:.4f}s")

            return response
        except asyncio.TimeoutError:
            timeout_time = asyncio.get_event_loop().time()
            total_time = timeout_time - operation_start
            logger.warning(f"[{client_id}] {action} TIMEOUT after {total_time:.4f}s")
            # Clean up the pending future
            if request_id in _client_pending_responses[client_id]:
                del _client_pending_responses[client_id][request_id]
            return {"status": "error", "message": "Request timeout"}
        except Exception as e:
            error_time = asyncio.get_event_loop().time()
            total_time = error_time - operation_start
            logger.error(f"[{client_id}] {action} ERROR after {total_time:.4f}s: {e}")
            # Clean up the pending future
            if request_id in _client_pending_responses[client_id]:
                del _client_pending_responses[client_id][request_id]
            return {"status": "error", "message": str(e)}
    else:
        # Fire and forget for other actions
        try:
            # Time the JSON serialization
            json_start = asyncio.get_event_loop().time()
            message_json = json.dumps(message)
            json_end = asyncio.get_event_loop().time()
            json_time = json_end - json_start
            logger.info(f"[{client_id}] JSON serialization took {json_time:.4f}s")

            # Time the WebSocket send
            send_start = asyncio.get_event_loop().time()
            await websocket.send_text(message_json)
            send_end = asyncio.get_event_loop().time()
            send_time = send_end - send_start
            total_time = send_end - operation_start

            logger.info(f"[{client_id}] Fire-and-forget {action} send took {send_time:.4f}s")
            logger.info(f"[{client_id}] Total {action} operation took {total_time:.4f}s")

            return {"status": "success"}
        except Exception as e:
            error_time = asyncio.get_event_loop().time()
            total_time = error_time - operation_start
            logger.error(f"[{client_id}] Fire-and-forget {action} ERROR after {total_time:.4f}s: {e}")
            return {"status": "error", "message": str(e)}

def get_mcp_queue(client_id: str) -> Optional[asyncio.Queue]:
    """Get the MCP response queue for a specific client"""
    global _client_mcp_queues
    return _client_mcp_queues.get(client_id)