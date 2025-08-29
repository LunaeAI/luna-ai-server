from .mcp import get_mcp_tools
from .util import util_tools

# Async function to get all tools including MCP
async def get_async_tools():
    """Get all tools including async MCP tools"""
    # mcp_tools = await get_mcp_tools()
    return util_tools