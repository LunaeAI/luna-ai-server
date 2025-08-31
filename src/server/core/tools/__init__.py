from .mcp import get_mcp_tools
from .util import util_tools

async def get_async_tools(client_id: str):
    """Get all tools including async MCP tools"""
    mcp_tools = await get_mcp_tools(client_id)
    
    return util_tools + mcp_tools