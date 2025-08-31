import logging
import os
import sys
from typing import List
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StreamableHTTPConnectionParams, StdioConnectionParams, StdioServerParameters

logger = logging.getLogger(__name__)

async def get_filesystem_mcp(client_id: str) -> MCPToolset | None:
    """Get filesystem MCP toolset via proxy"""
    try:
        port = os.environ.get("PORT")
        url = f"http://localhost:{port}/mcp/{client_id}/filesystem"
        
        logger.info(f"Connecting filesystem MCP via proxy: {url}")
        
        return MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=url,
                timeout=10.0,
                sse_read_timeout=30.0,
                terminate_on_close=False
            )
        )
    except Exception as e:
        logger.error(f"Failed to configure filesystem MCP toolset: {e}")
        return None

async def get_google_workspace_mcp(client_id: str) -> MCPToolset | None:
    """Get google workspace MCP toolset via proxy"""
    try:
        port = os.environ.get("PORT")
        url = f"http://localhost:{port}/mcp/{client_id}/google"
        
        logger.info(f"Connecting google workspace MCP via proxy: {url}")
        
        return MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=url,
                timeout=10.0,
                sse_read_timeout=30.0,
                terminate_on_close=False
            )
        )
    except Exception as e:
        logger.error(f"Failed to configure google workspace MCP toolset: {e}")
        return None

async def get_mcp_tools(client_id: str) -> List[MCPToolset]:
    """Get all MCP tools for a client"""
    tools = []
    
    filesystem_tool = await get_filesystem_mcp(client_id)
    if filesystem_tool:
        tools.append(filesystem_tool)
    
    google_tool = await get_google_workspace_mcp(client_id)

    if google_tool:
        tools.append(google_tool)
    
    return tools
