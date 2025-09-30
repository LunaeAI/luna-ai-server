#!/usr/bin/env python3
"""
Workspace management tools for Luna AI Agent
WebSocket-based communication with Electron main process
"""
import json
from typing import List, Dict, Any, Optional
from google.adk.tools import ToolContext
from ...util.websocket_communication import send_websocket_command
import logging

logger = logging.getLogger(__name__)

async def create_workspace(name: str, programs: Optional[List[str]] = None, description: Optional[str] = None, links: Optional[List[str]] = None, tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    Create a new workspace by finding and saving the specified programs and browser links.
    The workspace is saved to the database for future use. Use launch_workspace() to actually launch it.

    After creating the workspace, ask the user: "Would you like me to launch this workspace now?"
    If they say yes, use launch_workspace() to start the programs and open the links.
    
    Args:
        name: Name for the workspace
        programs: List of program names to search for and include in the workspace (optional)
        description: Optional description for the workspace
        links: List of browser links/URLs to open in the default browser (optional)

    Returns:
        Dict containing workspace creation results (does not launch programs/links)
    """
    workspace_data = {
        "programs": programs or [],
        "name": name,
        "description": description,
        "links": links or []
    }
    
    client_id = tool_context.state.get("client_id") if tool_context else None
    
    # Send command via WebSocket
    result = await send_websocket_command("workspace_request", "create", workspace_data, client_id)
    logger.info(f"Create workspace result: {json.dumps(result)}")
    return result

async def launch_workspace(id: str, tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    Launch an existing workspace. You should call list_workspaces first to see the corresponding ID of the workspace the user wants to launch.
    
    Args:
        id: ID of the workspace to launch
        
    Returns:
        Dict containing launch results
    """
    workspace_data = {"id": id}
    
    client_id = tool_context.state.get("client_id") if tool_context else None
    
    result = await send_websocket_command("workspace_request", "launch", workspace_data, client_id)

    logger.info(f"Launch workspace result: {json.dumps(result)}")
    
    return result

async def list_workspaces(tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    List all saved workspaces.
    
    Returns:
        Dict containing list of workspaces
    """
    client_id = tool_context.state.get("client_id") if tool_context else None
    
    result = await send_websocket_command("workspace_request", "list", {}, client_id)

    logger.info(f"List workspaces result: {json.dumps(result)}")
    
    return result

async def search_workspaces(query: str, tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    Search for workspaces by name, description, programs, or links.
    
    Args:
        query: Search query
        
    Returns:
        Dict containing search results
    """
    search_data = {"query": query}
    
    client_id = tool_context.state.get("client_id") if tool_context else None
    
    result = await send_websocket_command("workspace_request", "search", search_data, client_id)

    logger.info(f"Search workspaces result: {json.dumps(result)}")
    
    return result

async def delete_workspace(name: str, tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    Delete a workspace by name.
    
    Args:
        name: Name of the workspace to delete
        
    Returns:
        Dict containing deletion result
    """
    workspace_data = {"name": name}
    
    client_id = tool_context.state.get("client_id") if tool_context else None
    
    result = await send_websocket_command("workspace_request", "delete", workspace_data, client_id)

    logger.info(f"Delete workspace result: {json.dumps(result)}")

    return result

async def clear_all_workspaces(tool_context: ToolContext = None) -> Dict[str, Any]:
    """
    Clear all workspaces from the database. Useful for debugging and cleanup.
    
    Returns:
        Dict containing the operation result
    """
    client_id = tool_context.state.get("client_id") if tool_context else None
    
    result = await send_websocket_command("workspace_request", "clear_all", {}, client_id)

    logger.info(f"Clear all workspaces result: {json.dumps(result)}")

    return result


workspace_tools = [
    create_workspace,
    launch_workspace,
    list_workspaces,
    search_workspaces,
    delete_workspace,
    clear_all_workspaces,
]
