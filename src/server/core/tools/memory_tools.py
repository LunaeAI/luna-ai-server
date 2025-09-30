#!/usr/bin/env python3
"""
Memory management tools for Luna AI Agent
WebSocket-based communication with Electron main process
"""
from http import client
from typing import Dict, Any, Optional
from google.adk.tools import ToolContext
from ...util.websocket_communication import send_websocket_command
import json
import logging

logger = logging.getLogger(__name__)

async def save_memory(text: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Save important information to memory. This can include any preferences the user mentions 
    as well as general context knowledge that may be useful in a future conversation.
    
    Args:
        text: The information to save to memory

    Returns:
        dict: {"status": "success|error", "message": Optional[error_message]}
    """
    memory_data = {
        "text": text,
        "confidence": 0.5  # Start with medium confidence
    }
    
    client_id = tool_context.state.get("client_id")
    
    result = await send_websocket_command("memory_request", "save", memory_data, client_id)

    logger.info(f"Save memory result: {json.dumps(result)}")
    
    return result

async def get_all_memories(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Get all memories about the user from past conversations and memories. You should use this to search for any information about the user that may be relevant to the current request, and should also be called if searching Google does not work.
    If the user asks you if you remember certain information or facts, you MUST call this tool. Only say you don't remember something if this tool yields no results.
    
    Returns:
        dict: {"status": "success|error", "memories": List[Dict], "message": Optional[error_message]}
    """
    client_id = tool_context.state.get("client_id")
    
    result = await send_websocket_command("memory_request", "list", {"minConfidence": 0.1}, client_id)

    logger.info(f"Get all memories result: {json.dumps(result)}")
    
    return result

async def modify_memory(memory_id: str, new_text: Optional[str], new_confidence: Optional[float], tool_context: ToolContext) -> Dict[str, Any]:
    """
    Modify an existing memory's content or confidence. You should run get_all_memories first to fetch the relevant memory's ID, unless you already know it.
    
    Args:
        memory_id: ID of the memory to modify
        new_text: New memory text (optional)
        new_confidence: New confidence score (optional, 0.0-1.0)
        
    Returns:
        dict: {"status": "success|error", "message": Optional[error_message]}
    """
    updates = {}

    if new_text is not None:
        updates["text"] = new_text
    if new_confidence is not None:
        updates["confidence"] = new_confidence
    
    if not updates:
        return {"status": "error", "message": "No updates provided"}
    
    memory_data = {
        "id": memory_id,
        "updates": updates
    }
    
    client_id = tool_context.state.get("client_id")
    
    result = await send_websocket_command("memory_request", "update", memory_data, client_id)

    logger.info(f"Modify memory result: {json.dumps(result)}")
    
    return result

async def reinforce_memory(memory_id: str, factor: Optional[float], tool_context: ToolContext) -> Dict[str, Any]:
    """
    Reinforce a memory by increasing its confidence.
    
    Args:
        memory_id: ID of the memory to reinforce
        factor: Reinforcement factor (0.0-1.0)
        
    Returns:
        dict: {"status": "success|error", "message": Optional[error_message]}
    """
    if factor is None:
        factor = 0.1
        
    memory_data = {
        "id": memory_id,
        "factor": factor
    }
    
    client_id = tool_context.state.get("client_id")
    
    result = await send_websocket_command("memory_request", "reinforce", memory_data, client_id)

    logger.info(f"Reinforce memory result: {json.dumps(result)}")

    return result

async def weaken_memory(memory_id: str, factor: Optional[float], tool_context: ToolContext) -> Dict[str, Any]:
    """
    Weaken a memory by decreasing its confidence.
    
    Args:
        memory_id: ID of the memory to weaken
        factor: Weakening factor (0.0-1.0)
        auto_cleanup_threshold: Auto-delete if confidence drops below this
        
    Returns:
        dict: {"status": "success|error", "message": Optional[error_message]}
    """
    if factor is None:
        factor = 0.1

    memory_data = {
        "id": memory_id,
        "factor": factor,
    }
    
    client_id = tool_context.state.get("client_id")
    
    result = await send_websocket_command("memory_request", "weaken", memory_data, client_id)

    logger.info(f"Weaken memory result: {json.dumps(result)}")

    return result

async def delete_memory(memory_id: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Permanently delete a memory from the database.
    
    Args:
        memory_id: ID of the memory to delete
        
    Returns:
        dict: {"status": "success|error", "message": Optional[error_message]}
    """
    memory_data = {"id": memory_id}
    
    client_id = tool_context.state.get("client_id")
    
    result = await send_websocket_command("memory_request", "delete", memory_data, client_id)

    logger.info(f"Delete memory result: {json.dumps(result)}")
    
    return result

async def clear_all_memories(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Clear all memories from the database. Useful for debugging and cleanup.
    
    Returns:
        Dict containing the operation result
    """
    client_id = tool_context.state.get("client_id")
    
    result = await send_websocket_command("memory_request", "clear_all", {}, client_id)

    logger.info(f"Clear all memories result: {json.dumps(result)}")

    return result

memory_tools = [
    save_memory,
    get_all_memories,
    modify_memory,
    reinforce_memory,
    weaken_memory,
    delete_memory,
    clear_all_memories,
]
