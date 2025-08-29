# filepath: src/main/services/agent/core/tools/mcp/external/google/google_mcp.py
import os
import sys
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters, StdioConnectionParams

async def get_google_mcp() -> MCPToolset:
    # from .get_credentials import get_credentials

    # await get_credentials()

    google_mcp = MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,  # Use the current Python executable (bundled or system)
                args=[
                    os.path.abspath(os.path.join(os.path.dirname(__file__), 'mcp_server.py'))  # Absolute path to mcp_server.py
                ],
                cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),  # Set to project root or appropriate dir
                env=os.environ.copy()
            ),
        )
    )

    return google_mcp

async def get_google_tools():
    """
    Get Google workspace tools as an MCP toolset.
    """
    return await get_google_mcp()
