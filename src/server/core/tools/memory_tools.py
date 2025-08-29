#!/usr/bin/env python3
"""
Memory management tools for Luna AI Agent
WebSocket-based communication with Electron main process
"""
from http import client
from typing import Dict, Any, Optional
from google.adk.tools import ToolContext
from ...util.websocket_communication import send_websocket_command

async def search_memory(query: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Search through past conversations and memories. You should use this to search for any information about the user that may be relevant to the current request, and should also be called if searching Google does not work.
    If the user asks you if you remember certain information or facts, you MUST call this tool. Only say you don't remember something if this tool yields no results.
    
    Args:
        query: What to search your memories for.
        
    Returns:
        dict: {"status": "success|no_memories|error", "memories": formatted_memories, "message": Optional[error_message]}
    """
    search_data = {
        "query": query,
        "minConfidence": 0.3
    }

    client_id = tool_context.state.get("client_id")
    
    result = await send_websocket_command("memory_request", "search", search_data, client_id)
    
    if result.get("status") == "success":
        memories = result.get("data", {}).get("memories", [])
        
        if memories:
            # Format memories for display
            memory_context = "\n".join([
                f"- {memory['memory']} (confidence: {memory['confidence']:.2f})" 
                for memory in memories
            ])
            return {"status": "success", "memories": memory_context}
        else:
            return {"status": "no_memories", "message": "No relevant memories found"}
    else:
        return {"status": "error", "message": result.get("message", "Failed to search memories")}

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
    
    # Send command via WebSocket
    result = await send_websocket_command("memory_request", "save", memory_data, client_id)
    
    if result.get("status") == "success":
        return {"status": "success", "message": "Memory saved successfully"}
    else:
        return {"status": "error", "message": result.get("message", "Failed to save memory")}

async def get_all_memories(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Get all memories from the database.
        
    Returns:
        dict: {"status": "success|error", "memories": List[Dict], "message": Optional[error_message]}
    """
    client_id = tool_context.state.get("client_id")
    
    # Send command via WebSocket and wait for response
    result = await send_websocket_command("memory_request", "list", {"minConfidence": 0.1}, client_id)
    
    if result.get("status") == "success":
        # Return in the expected format with memories data
        return {
            "status": "success",
            "memories": result.get("data", {}).get("memories", []),
            "count": result.get("data", {}).get("total", 0),
            "message": result.get("message", "Memories retrieved successfully")
        }
    else:
        return {"status": "error", "message": result.get("message", "Failed to retrieve memories"), "memories": []}

async def modify_memory(memory_id: str, new_text: Optional[str], new_confidence: Optional[float], tool_context: ToolContext) -> Dict[str, Any]:
    """
    Modify an existing memory's content or confidence.
    
    Args:
        memory_id: ID of the memory to modify
        new_text: New memory text (optional)
        new_confidence: New confidence score (optional, 0.0-1.0)
        
    Returns:
        dict: {"status": "success|error", "message": Optional[error_message]}
    """
    if new_confidence is not None and (new_confidence < 0.0 or new_confidence > 1.0):
        return {"status": "error", "message": "Confidence must be between 0.0 and 1.0"}
    
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
    
    # Send command via WebSocket
    result = await send_websocket_command("memory_request", "update", memory_data, client_id)
    
    if result.get("status") == "success":
        return {"status": "success", "message": f"Memory {memory_id} updated successfully"}
    else:
        return {"status": "error", "message": result.get("message", "Failed to update memory")}

async def reinforce_memory(memory_id: str, factor: Optional[float], tool_context: ToolContext) -> Dict[str, Any]:
    """
    Reinforce a memory by increasing its confidence.
    
    Args:
        memory_id: ID of the memory to reinforce
        factor: Reinforcement factor (0.0-1.0)
        
    Returns:
        dict: {"status": "success|error", "message": Optional[error_message]}
    """
    # Use default value if not provided
    if factor is None:
        factor = 0.1
        
    memory_data = {
        "id": memory_id,
        "factor": factor
    }
    
    client_id = tool_context.state.get("client_id")
    
    # Send command via WebSocket
    result = await send_websocket_command("memory_request", "reinforce", memory_data, client_id)
    return result

async def weaken_memory(memory_id: str, factor: Optional[float], auto_cleanup_threshold: Optional[float], tool_context: ToolContext) -> Dict[str, Any]:
    """
    Weaken a memory by decreasing its confidence.
    
    Args:
        memory_id: ID of the memory to weaken
        factor: Weakening factor (0.0-1.0)
        auto_cleanup_threshold: Auto-delete if confidence drops below this
        
    Returns:
        dict: {"status": "success|error", "message": Optional[error_message]}
    """
    # Use default values if not provided
    if factor is None:
        factor = 0.2
    if auto_cleanup_threshold is None:
        auto_cleanup_threshold = 0.1
        
    memory_data = {
        "id": memory_id,
        "factor": factor,
        "autoCleanupThreshold": auto_cleanup_threshold
    }
    
    client_id = tool_context.state.get("client_id")
    
    # Send command via WebSocket
    result = await send_websocket_command("memory_request", "weaken", memory_data, client_id)
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
    
    # Send command via WebSocket
    result = await send_websocket_command("memory_request", "delete", memory_data, client_id)
    return result

async def clear_all_memories(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Clear all memories from the database. Useful for debugging and cleanup.
    
    Returns:
        Dict containing the operation result
    """
    client_id = tool_context.state.get("client_id")
    
    # Send command via WebSocket
    result = await send_websocket_command("memory_request", "clear_all", {}, client_id)
    return result

memory_tools = [
    search_memory,
    save_memory,
    get_all_memories,
    modify_memory,
    reinforce_memory,
    weaken_memory,
    delete_memory,
    clear_all_memories,
]
