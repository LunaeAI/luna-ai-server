from .filesystem import get_filesystem_mcp
from .external import get_google_mcp

async def get_mcp_tools():
    """Get all MCP tools, initializing filesystem tools dynamically"""
    mcp_servers = []

    filesystem_tools = await get_filesystem_mcp()
    if filesystem_tools:
        mcp_servers.append(filesystem_tools)

    # google_mcp = await get_google_mcp()
    # if google_mcp:
    #     mcp_servers.append(google_mcp)

    return mcp_servers