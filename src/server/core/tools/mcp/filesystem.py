import logging
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StreamableHTTPConnectionParams

logger = logging.getLogger(__name__)

async def get_filesystem_mcp() -> MCPToolset | None:
    """Get filesystem MCP toolset with dynamic port"""
    try:
        port_mapping = {}

        logger.info(f"Port mapping: {port_mapping}")
            
        filesystem_port = port_mapping.get("filesystem")

        if not filesystem_port:
            logger.error("Filesystem MCP port not found in mapping")
            return None

        return MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=f"http://localhost:{filesystem_port}/mcp",
                timeout=10.0,
                sse_read_timeout=30.0,
                terminate_on_close=False
            )
        )
    except Exception as e:
        logger.error(f"Failed to configure filesystem MCP toolset: {e}")
        logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
        return None